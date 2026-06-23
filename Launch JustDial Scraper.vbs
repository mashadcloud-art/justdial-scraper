Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

WshShell.CurrentDirectory = scriptDir
' Launch run_app.py in the background using pythonw (no cmd window will show)
WshShell.Run "pythonw run_app.py", 0, False
