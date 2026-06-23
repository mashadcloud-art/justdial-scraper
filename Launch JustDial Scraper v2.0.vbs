Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
pythonPath = "C:\Users\PC\AppData\Local\Programs\Python\Python310\pythonw.exe"

' 1. Start FastAPI backend (stays running independently)
backendCmd = """" & pythonPath & """ -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
WshShell.Run backendCmd, 0, False

' 2. Start Vite + open Chrome app window
WshShell.CurrentDirectory = scriptDir
appCmd = """" & pythonPath & """ """ & scriptDir & "\run_app.py"""
WshShell.Run appCmd, 0, False