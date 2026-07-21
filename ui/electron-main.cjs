const { app, BrowserWindow } = require('electron');
const path = require('path');
const http = require('http');
const { spawn, execSync } = require('child_process');

let mainWindow;
let backendProcess;

const BACKEND_URL = 'http://127.0.0.1:8000';
const READY_POLL_INTERVAL_MS = 500;
const READY_MAX_WAIT_MS = 120000; // give the packaged (onefile) backend plenty of time to self-extract + migrate

const LOADING_HTML = `data:text/html;charset=utf-8,${encodeURIComponent(`
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>JustDial Scraper</title>
<style>
  body { margin:0; height:100vh; display:flex; align-items:center; justify-content:center;
         background:#0f172a; color:#e2e8f0; font-family:-apple-system,Segoe UI,Arial,sans-serif; }
  .box { text-align:center; }
  .spinner { width:36px; height:36px; margin:0 auto 16px; border-radius:50%;
             border:3px solid #334155; border-top-color:#38bdf8; animation:spin 0.9s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
</style>
</head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <div>Starting JustDial Scraper…</div>
  </div>
</body>
</html>
`)}`;

const ERROR_HTML = `data:text/html;charset=utf-8,${encodeURIComponent(`
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>JustDial Scraper</title>
<style>
  body { margin:0; height:100vh; display:flex; align-items:center; justify-content:center;
         background:#0f172a; color:#e2e8f0; font-family:-apple-system,Segoe UI,Arial,sans-serif; }
  .box { text-align:center; max-width:420px; }
  button { margin-top:16px; padding:8px 20px; border-radius:6px; border:none;
           background:#38bdf8; color:#0f172a; font-weight:600; cursor:pointer; }
</style>
</head>
<body>
  <div class="box">
    <div>The backend server did not start in time.</div>
    <div style="opacity:0.7; margin-top:8px; font-size:13px;">Check that antivirus isn't blocking backend.exe, then retry.</div>
    <button onclick="location.reload()">Retry</button>
  </div>
</body>
</html>
`)}`;

// If a previous run of this app crashed or was force-killed, its backend.exe
// child can be left orphaned and still listening on our port. When that
// happens the readiness poll below talks to that stale process instead of
// the one we're about to spawn — and depending on what folder it was
// launched from, it may not be serving the built frontend at all (e.g. the
// bare-API JSON fallback). Clear anything already on the port before we
// start our own backend so every launch begins from a clean slate.
function freeStaleBackendPort() {
  if (process.platform !== 'win32') return;
  try {
    const netstatOut = execSync('netstat -ano -p tcp', { encoding: 'utf8' });
    const pids = new Set();
    for (const line of netstatOut.split('\n')) {
      if (!line.includes(':8000') || !/LISTENING/i.test(line)) continue;
      const parts = line.trim().split(/\s+/);
      const pid = parts[parts.length - 1];
      if (pid && /^\d+$/.test(pid)) pids.add(pid);
    }
    for (const pid of pids) {
      try {
        const tasklistOut = execSync(`tasklist /FI "PID eq ${pid}" /FO CSV /NH`, { encoding: 'utf8' });
        if (!/^"backend\.exe"/i.test(tasklistOut.trim())) continue; // only ever touch our own backend
        execSync(`taskkill /F /PID ${pid}`);
        console.log(`Killed stale backend.exe (PID ${pid}) left over from a previous run.`);
      } catch (e) {
        console.error(`Could not inspect/kill PID ${pid} on port 8000:`, e.message);
      }
    }
  } catch (e) {
    console.error('Could not check port 8000 for stale processes:', e.message);
  }
}

function startBackend() {
  freeStaleBackendPort();

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
    env: { ...process.env, PORT: '8000', ELECTRON_RUN: '1' }
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend]: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error]: ${data}`);
  });

  backendProcess.on('error', (err) => {
    console.error('Failed to launch backend process:', err);
  });
}

// A 200 from the port alone isn't proof the real frontend is being served —
// the backend answers "/" with a JSON status stub until ui/dist/client is
// found (and a stale process from a previous run could be answering with
// anything at all). Only treat the app as ready once the response is
// actually the SPA's HTML shell, so we never load raw API JSON into the window.
function isBackendUp() {
  return new Promise((resolve) => {
    const req = http.get(BACKEND_URL, (res) => {
      const contentType = res.headers['content-type'] || '';
      res.resume();
      resolve(res.statusCode === 200 && contentType.includes('text/html'));
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForBackendAndLoad() {
  const deadline = Date.now() + READY_MAX_WAIT_MS;

  while (Date.now() < deadline) {
    if (!mainWindow) return; // window was closed while waiting
    if (await isBackendUp()) {
      try {
        await mainWindow.loadURL(BACKEND_URL);
        return;
      } catch (err) {
        console.error('loadURL failed after backend reported ready, retrying:', err);
      }
    }
    await new Promise((resolve) => setTimeout(resolve, READY_POLL_INTERVAL_MS));
  }

  console.error('Backend did not become ready within the timeout window.');
  if (mainWindow) {
    mainWindow.loadURL(ERROR_HTML);
  }
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

  // Show an in-app loading screen immediately instead of a blank/chrome-error window
  mainWindow.loadURL(LOADING_HTML);

  waitForBackendAndLoad();

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