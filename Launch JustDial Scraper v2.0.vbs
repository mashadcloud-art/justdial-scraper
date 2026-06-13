Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

pythonPath = "C:\Users\PC\AppData\Local\Programs\Python\Python310\pythonw.exe"
scriptPath = scriptDir & "\ModernScraperApp.pyw"
WshShell.Run """" & pythonPath & """ """ & scriptPath & """", 0, False

