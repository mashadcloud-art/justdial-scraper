const { app, BrowserWindow, Tray, Menu, shell, Notification, nativeImage } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

// Must match app_config.py / config.py (API_PORT) — the FastAPI backend
// listens on 8000, not 8080.
const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = 8000;
const APP_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

let mainWindow = null;
let tray = null;
let backendProcess = null;

function getBackendExePath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend.exe")
    : path.join(__dirname, "..", "dist", "backend.exe");
}

function startBackend() {
  const exePath = getBackendExePath();
  backendProcess = spawn(exePath, ["--host", BACKEND_HOST, "--port", String(BACKEND_PORT)], {
    cwd: path.dirname(exePath),
  });

  backendProcess.stdout?.on("data", (data) => console.log(`[backend] ${data}`.trim()));
  backendProcess.stderr?.on("data", (data) => console.error(`[backend] ${data}`.trim()));
  backendProcess.on("error", (err) => console.error("[backend] failed to start:", err));
  backendProcess.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
}

function waitForBackend(url, callback, attempt = 0) {
  const maxAttempts = 60; // ~30s at 500ms intervals
  http
    .get(url, (res) => {
      res.resume();
      callback();
    })
    .on("error", () => {
      if (attempt >= maxAttempts) {
        console.error("[backend] did not become ready in time, opening window anyway");
        callback();
        return;
      }
      setTimeout(() => waitForBackend(url, callback, attempt + 1), 500);
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

  mainWindow.loadURL(APP_URL);

  mainWindow.on("close", (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
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
  createTray();
  waitForBackend(APP_URL, createWindow);
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
});
