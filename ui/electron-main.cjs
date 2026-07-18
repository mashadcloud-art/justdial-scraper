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

function startBackend() {
  const exePath = getBackendExePath();
  backendProcess = spawn(exePath, ["--host", LOOPBACK, "--port", String(BACKEND_PORT)], {
    cwd: path.dirname(exePath),
  });

  backendProcess.stdout?.on("data", (data) => console.log(`[backend] ${data}`.trim()));
  backendProcess.stderr?.on("data", (data) => console.error(`[backend] ${data}`.trim()));
  backendProcess.on("error", (err) => console.error("[backend] failed to start:", err));
  backendProcess.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
}

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
    console.error("[frontend] backend proxy error:", err);
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
    console.error("[frontend] SSR handler error:", err);
    res.writeHead(500, { "Content-Type": "text/plain" });
    res.end("Internal Server Error");
  }
}

function startFrontendServer(onListening) {
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
  frontendServer.on("error", (err) => console.error("[frontend] server error:", err));
  frontendServer.listen(FRONTEND_PORT, LOOPBACK, onListening);
}

function waitFor(url, callback, attempt = 0, maxAttempts = 60) {
  http
    .get(url, (res) => {
      res.resume();
      callback();
    })
    .on("error", () => {
      if (attempt >= maxAttempts) {
        console.error(`[startup] ${url} did not become ready in time, opening window anyway`);
        callback();
        return;
      }
      setTimeout(() => waitFor(url, callback, attempt + 1, maxAttempts), 500);
    });
}

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

  // Give backend.exe and the frontend server a moment to come up, then swap
  // the loading screen for the real app once both respond.
  setTimeout(() => {
    waitFor(BACKEND_URL, () => {
      waitFor(FRONTEND_URL, () => {
        mainWindow?.loadURL(FRONTEND_URL);
      });
    });
  }, 3000);
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

  autoUpdater.on("error", (err) => console.error("[autoUpdater]", err));

  autoUpdater.checkForUpdates().catch((err) => console.error("[autoUpdater] check failed:", err));
}

app.whenReady().then(() => {
  startBackend();
  startFrontendServer();
  createTray();
  createWindow();
  checkForUpdates();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
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
