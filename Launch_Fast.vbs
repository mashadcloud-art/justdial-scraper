Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

pythonPath = "C:\Users\PC\AppData\Local\Programs\Python\Python310\pythonw.exe"

' 1. Start FastAPI backend silently (port 8000)
backendCmd = """" & pythonPath & """ -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
WshShell.Run backendCmd, 0, False

' 2. Start Vite dev server silently (port 8082)
viteCmd = "cmd /c ""cd ui && npm run dev"""
WshShell.Run viteCmd, 0, False

' 3. Wait a brief moment (1.5 seconds) for servers to spin up
WScript.Sleep 1500

' 4. Open in the default web browser (not App Mode)
WshShell.Run "cmd /c start http://localhost:8082", 0, False
