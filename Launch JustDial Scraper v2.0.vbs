Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

pythonwPath = "C:\Users\PC\AppData\Local\Programs\Python\Python310\pythonw.exe"

' Start Modern Desktop Scraper UI with unified launcher
appCmd = """" & pythonwPath & """ """ & scriptDir & "\run_app.py"""
WshShell.Run appCmd, 0, False


