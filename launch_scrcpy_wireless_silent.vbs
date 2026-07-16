Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = "C:\Users\PC\Documents\trae_projects\Scapre for thozil\ip.txt"

If objFSO.FileExists(strPath) Then
    Set objFile = objFSO.OpenTextFile(strPath, 1)
    strIP = Trim(objFile.ReadLine)
    objFile.Close
    
    Set WshShell = CreateObject("WScript.Shell")
    ' Run adb connect in the background
    WshShell.Run """C:\Users\PC\Documents\trae_projects\Scapre for thozil\platform-tools\adb.exe"" connect " & strIP & ":5555", 0, True
    
    ' Run scrcpy
    WshShell.CurrentDirectory = "C:\Users\PC\Documents\trae_projects\Scapre for thozil\scrcpy-win64-v4.1"
    WshShell.Run "scrcpy.exe -e --window-title ""Galaxy S8 (Wireless)""", 0, False
Else
    MsgBox "Please run 'launch_scrcpy_wireless.bat' once first to set up and detect your phone's IP address.", 48, "Wireless Setup Required"
End If
