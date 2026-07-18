const { app, BrowserWindow, Tray, Menu, Notification, nativeImage } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");
const { pathToFileURL } = require("url");

// Must match app_config.py / config.py (API_PORT) — the FastAPI backend
// listens on 8000, not 8080.
const LOOPBACK = "127.0.0.1";
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://${LOOPBACK}:${BACKEND_PORT}`;
const BACKEND_HEALTH_URL = `${BACKEND_URL}/health`;
const BACKEND_READY_TIMEOUT_MS = 30000;

// TanStack Start build output is an SSR fetch handler (dist/server/server.js),
// not a static index.html — it has to be served by a Node HTTP server, not
// loaded as a local file.
const FRONTEND_PORT = 8080;
const FRONTEND_URL = `http://${LOOPBACK}:${FRONTEND_PORT}`;

const MIME_TYPES = {
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

let mainWindow = null;
let tray = null;
let backendProcess = null;
let frontendServer = null;
let logStream = null;

const backendLogLines = [];
const MAX_BACKEND_LOG_LINES = 200;

// ─── Logging ────────────────────────────────────────────────────────────
// Packaged Windows apps have no visible console, so this is the only way to
// see why backend.exe didn't start — write everything to a log file too.
function getLogFilePath() {
  return path.join(app.getPath("userData"), "logs", "main.log");
}

function initLogging() {
  const logFile = getLogFilePath();
  fs.mkdirSync(path.dirname(logFile), { recursive: true });
  logStream = fs.createWriteStream(logFile, { flags: "a" });
  log(`===== JustDial Pro starting @ ${new Date().toISOString()} =====`);
  log(`app.isPackaged=${app.isPackaged} resourcesPath=${process.resourcesPath}`);
}

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  console.log(line);
  logStream?.write(line + "\n");
}

function recordBackendOutput(source, data) {
  const text = data.toString();
  log(`[backend:${source}] ${text.trim()}`);
  for (const line of text.split(/\r?\n/)) {
    if (!line) continue;
    backendLogLines.push(line);
    if (backendLogLines.length > MAX_BACKEND_LOG_LINES) backendLogLines.shift();
  }
}

// ─── Paths ──────────────────────────────────────────────────────────────
function getBackendExePath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend.exe")
    : path.join(__dirname, "..", "dist", "backend.exe");
}

function getClientDir() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "ui", "dist", "client")
    : path.join(__dirname, "dist", "client");
}

function getServerEntryPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "ui", "dist", "server", "server.js")
    : path.join(__dirname, "dist", "server", "server.js");
}

// ─── Backend process ────────────────────────────────────────────────────
function startBackend() {
  const exePath = getBackendExePath();
  log(`Resolved backend.exe path: ${exePath}`);

  if (!fs.existsSync(exePath)) {
    log(`ERROR: backend.exe not found at ${exePath}`);
    return;
  }

  try {
    backendProcess = spawn(exePath, ["--host", LOOPBACK, "--port", String(BACKEND_PORT)], {
      cwd: path.dirname(exePath),
    });
  } catch (err) {
    log(`ERROR: failed to spawn backend.exe: ${err.message}`);
    return;
  }

  backendProcess.stdout?.on("data", (data) => recordBackendOutput("stdout", data));
  backendProcess.stderr?.on("data", (data) => recordBackendOutput("stderr", data));
  backendProcess.on("error", (err) => log(`ERROR: backend process error: ${err.message}`));
  backendProcess.on("exit", (code, signal) => log(`backend.exe exited (code=${code}, signal=${signal})`));
}

// ─── Frontend server ────────────────────────────────────────────────────
// The frontend, when run under Vite (dev/preview), reaches the backend via
// Vite's dev-server "/api" proxy (see vite.config.ts). The packaged SSR
// bundle has no such proxy, so this server has to forward "/api/*" itself.
function proxyToBackend(req, res) {
  const proxyReq = http.request(
    { host: LOOPBACK, port: BACKEND_PORT, path: req.url, method: req.method, headers: req.headers },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    },
  );
  proxyReq.on("error", (err) => {
    log(`ERROR: [frontend] backend proxy error: ${err.message}`);
    res.writeHead(502);
    res.end("Backend unavailable");
  });
  req.pipe(proxyReq);
}

function serveStatic(filePath, res) {
  const stream = fs.createReadStream(filePath);
  stream.on("error", () => {
    res.writeHead(404);
    res.end("Not found");
  });
  stream.once("open", () => {
    res.writeHead(200, { "Content-Type": MIME_TYPES[path.extname(filePath)] || "application/octet-stream" });
    stream.pipe(res);
  });
}

let ssrHandlerPromise;
function getSsrHandler() {
  if (!ssrHandlerPromise) {
    ssrHandlerPromise = import(pathToFileURL(getServerEntryPath()).href).then((m) => m.default ?? m);
  }
  return ssrHandlerPromise;
}

async function handleSsr(req, res) {
  try {
    const handler = await getSsrHandler();
    const url = `http://${req.headers.host || `${LOOPBACK}:${FRONTEND_PORT}`}${req.url}`;
    const init = { method: req.method, headers: req.headers };
    if (req.method !== "GET" && req.method !== "HEAD") {
      init.body = req;
      init.duplex = "half";
    }
    const response = await handler.fetch(new Request(url, init), {}, {});
    res.writeHead(response.status, Object.fromEntries(response.headers));
    if (!response.body) {
      res.end();
      return;
    }
    const reader = response.body.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(value);
    }
    res.end();
  } catch (err) {
    log(`ERROR: [frontend] SSR handler error: ${err.stack || err.message}`);
    res.writeHead(500, { "Content-Type": "text/plain" });
    res.end("Internal Server Error");
  }
}

function startFrontendServer() {
  return new Promise((resolve) => {
    const clientDir = getClientDir();
    frontendServer = http.createServer((req, res) => {
      const pathname = req.url.split("?")[0];
      if (pathname.startsWith("/api/")) {
        proxyToBackend(req, res);
        return;
      }
      if (pathname.startsWith("/assets/")) {
        const filePath = path.join(clientDir, pathname);
        if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
          serveStatic(filePath, res);
          return;
        }
      }
      handleSsr(req, res);
    });
    frontendServer.on("error", (err) => {
      log(`ERROR: frontend server error: ${err.message}`);
      resolve(false);
    });
    frontendServer.listen(FRONTEND_PORT, LOOPBACK, () => {
      log(`Frontend server listening on ${FRONTEND_URL}`);
      resolve(true);
    });
  });
}

// ─── Readiness polling ──────────────────────────────────────────────────
function pollUntilReady(url, timeoutMs, intervalMs = 500) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    const tryOnce = () => {
      http
        .get(url, (res) => {
          res.resume();
          resolve(true);
        })
        .on("error", () => {
          if (Date.now() >= deadline) {
            resolve(false);
            return;
          }
          setTimeout(tryOnce, intervalMs);
        });
    };
    tryOnce();
  });
}

// ─── Windows ────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    icon: path.join(__dirname, "electron-resources", "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "electron-resources", "loading.html"));

  mainWindow.on("close", (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  return mainWindow;
}

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showErrorScreen(message) {
  log(`Showing startup error screen: ${message}`);
  const recentLogs = backendLogLines.slice(-50).join("\n") || "(no backend output captured)";
  const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>JustDial Pro</title>
    <style>
      body { margin: 0; padding: 24px; background: #0f172a; color: #e2e8f0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
      h1 { font-size: 16px; color: #f87171; }
      p { font-size: 13px; color: #94a3b8; }
      pre { background: #1e293b; color: #cbd5e1; padding: 12px; border-radius: 8px; font-size: 11px; white-space: pre-wrap; word-break: break-word; max-height: 50vh; overflow-y: auto; }
    </style>
  </head>
  <body>
    <h1>JustDial Pro failed to start</h1>
    <p>${escapeHtml(message)}</p>
    <p>Full log file: ${escapeHtml(getLogFilePath())}</p>
    <p>Recent backend output:</p>
    <pre>${escapeHtml(recentLogs)}</pre>
  </body>
</html>`;
  mainWindow?.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
}

async function bootApp() {
  createWindow();

  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    if (validatedURL.startsWith("data:")) return; // avoid looping on our own error page
    showErrorScreen(`Failed to load ${validatedURL}: ${errorDescription} (${errorCode})`);
  });

  log(`Waiting up to ${BACKEND_READY_TIMEOUT_MS / 1000}s for backend health check at ${BACKEND_HEALTH_URL}`);
  const backendReady = await pollUntilReady(BACKEND_HEALTH_URL, BACKEND_READY_TIMEOUT_MS);
  if (!backendReady) {
    showErrorScreen(`Backend did not respond at ${BACKEND_HEALTH_URL} within ${BACKEND_READY_TIMEOUT_MS / 1000} seconds.`);
    return;
  }
  log("Backend is responding.");

  const frontendReady = await pollUntilReady(FRONTEND_URL, 5000);
  if (!frontendReady) {
    showErrorScreen(`Frontend server did not respond at ${FRONTEND_URL}.`);
    return;
  }

  log(`Loading ${FRONTEND_URL}`);
  mainWindow.loadURL(FRONTEND_URL);
}

function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, "electron-resources", "tray-icon.png"));
  tray = new Tray(icon);
  tray.setToolTip("JustDial Pro");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: "Open JustDial Pro",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      { type: "separator" },
      {
        label: "Quit",
        click: () => {
          app.isQuitting = true;
          if (backendProcess) backendProcess.kill();
          if (frontendServer) frontendServer.close();
          app.quit();
        },
      },
    ]),
  );
  tray.on("click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function checkForUpdates() {
  autoUpdater.autoDownload = false;

  autoUpdater.on("update-available", () => {
    const notification = new Notification({
      title: "JustDial Pro",
      body: "Update available - click to install",
    });
    notification.on("click", () => {
      autoUpdater.downloadUpdate();
    });
    notification.show();
  });

  autoUpdater.on("update-downloaded", () => {
    app.isQuitting = true;
    autoUpdater.quitAndInstall();
  });

  autoUpdater.on("error", (err) => log(`ERROR: [autoUpdater] ${err.message}`));

  autoUpdater.checkForUpdates().catch((err) => log(`ERROR: [autoUpdater] check failed: ${err.message}`));
}

app.whenReady().then(async () => {
  initLogging();

  process.on("uncaughtException", (err) => log(`ERROR: uncaughtException: ${err.stack || err.message}`));
  process.on("unhandledRejection", (err) => log(`ERROR: unhandledRejection: ${err?.stack || err}`));

  startBackend();
  await startFrontendServer();
  createTray();
  await bootApp();
  checkForUpdates();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) bootApp();
    else mainWindow?.show();
  });
});

app.on("window-all-closed", () => {
  // Keep running in the tray on all platforms — the tray Quit action is
  // the only way to fully exit, per the system-tray requirement.
});

app.on("before-quit", () => {
  app.isQuitting = true;
  if (backendProcess) backendProcess.kill();
  if (frontendServer) frontendServer.close();
});
