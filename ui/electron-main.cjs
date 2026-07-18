const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess;

function startBackend() {
  const isPackaged = app.isPackaged;
  let backendPath;
  
  if (isPackaged) {
    // In packaged app, the backend binary is copied to the resources folder
    backendPath = path.join(process.resourcesPath, 'backend.exe');
  } else {
    // During development, look in the parent directory
    backendPath = path.join(__dirname, '..', 'JustDial_Scraper.exe');
    if (!require('fs').existsSync(backendPath)) {
      backendPath = path.join(__dirname, '..', 'backend.exe');
    }
  }

  console.log('Starting backend at:', backendPath);
  backendProcess = spawn(backendPath, [], {
    cwd: path.dirname(backendPath),
    env: { ...process.env, PORT: '8000' }
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend]: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error]: ${data}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "JustDial Scraper",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Wait for backend server to start up, then load the port
  setTimeout(() => {
    mainWindow.loadURL('http://127.0.0.1:8000');
  }, 2500);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.on('ready', () => {
  startBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  if (backendProcess) {
    try {
      backendProcess.kill();
    } catch (e) {
      console.error('Failed to kill backend:', e);
    }
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
