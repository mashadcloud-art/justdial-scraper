Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

pythonwPath = "C:\Users\PC\AppData\Local\Programs\Python\Python310\pythonw.exe"

' 1. Start Streamlit Dashboard in the background (runs silently, opens browser automatically)
streamlitCmd = """" & pythonwPath & """ -m streamlit run """ & scriptDir & "\frontend.py"" --server.port 8502"
WshShell.Run streamlitCmd, 0, False

' 2. Start Modern Desktop Scraper UI
appCmd = """" & pythonwPath & """ """ & scriptDir & "\ModernScraperApp.pyw"""
WshShell.Run appCmd, 0, False


