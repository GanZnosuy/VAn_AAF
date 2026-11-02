' start_auto_continue_daemon.vbs
' Khoi dong Antigravity Autonomous Auto-Continue Engine chay ngam (Zero-Window / Silent Background)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"
WshShell.CurrentDirectory = projectDir

pythonwPath = "C:\Users\vuong\AppData\Local\Programs\Python\Python312\pythonw.exe"
If Not fso.FileExists(pythonwPath) Then
    pythonwPath = "C:\Users\vuong\.agent-reach-venv\Scripts\pythonw.exe"
End If
If Not fso.FileExists(pythonwPath) Then
    pythonwPath = projectDir & "\.venv\Scripts\pythonw.exe"
End If
If Not fso.FileExists(pythonwPath) Then
    pythonwPath = "pythonw.exe"
End If

scriptPath = projectDir & "\antigravity_auto_continue_engine.py"

cmd = """" & pythonwPath & """ """ & scriptPath & """ --daemon"
WshShell.Run cmd, 0, False
