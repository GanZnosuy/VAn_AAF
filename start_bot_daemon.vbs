Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"
WshShell.Run """c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG\.venv\Scripts\pythonw.exe"" ""c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG\discord_remote_controller.py""", 0, False
