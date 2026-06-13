Set WshShell = CreateObject("WScript.Shell")
pythonPath = "C:\Users\PC\AppData\Local\Programs\Python\Python310\pythonw.exe"
scriptPath = WshShell.CurrentDirectory & "\ModernScraperApp.pyw"
WshShell.Run """" & pythonPath & """ """ & scriptPath & """", 0, False
