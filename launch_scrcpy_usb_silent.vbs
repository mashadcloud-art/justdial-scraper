Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\PC\Documents\trae_projects\Scapre for thozil\scrcpy-win64-v4.1"
' USB connection uses default maximum quality and forces USB target (-d)
WshShell.Run "scrcpy.exe -d --window-title ""Galaxy S8 (USB - Full Quality)""", 0, False
