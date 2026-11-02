@echo off
setlocal
chcp 65001 >nul
title KHOI DONG ANTIGRAVITY AUTO-CONTINUE ENGINE
cls
echo ===============================================================================
echo   ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE (v1.0)
echo   Che do: Background Daemon Shield - Non-Stop Execution - Unbounded Tokens
echo ===============================================================================
echo.

cd /d "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"

:: 1. Kiem tra va khoi dong qua VBScript (Silent / Background)
echo [*] Dang khoi dong Daemon chay ngam qua start_auto_continue_daemon.vbs...
wscript.exe "start_auto_continue_daemon.vbs"

ping -n 3 127.0.0.1 >nul

:: 2. Kiem tra tien trinh
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*.exe') -and ($_.CommandLine -like '*antigravity_auto_continue_engine.py*') }; if ($procs) { Write-Host '[OK] DAEMON DA DUOC KICH HOAT VA DANG CHAY NGAM THANH CONG!' -ForegroundColor Green; foreach ($p in $procs) { Write-Host ('    -> PID: ' + $p.ProcessId + ' | Khoi tao: ' + $p.CreationDate) -ForegroundColor Cyan } } else { Write-Host '[WARN] Khong tim thay tien trinh daemon. Vui long kiem tra file log.' -ForegroundColor Yellow }"

echo.
echo ===============================================================================
echo  Tep nhat ky theo doi (Real-time Logs):
echo     logs\auto_continue_engine.log
echo.
echo  De dung Daemon: Chay DUNG_AUTO_CONTINUE_ENGINE.bat
echo ===============================================================================
echo.
ping -n 4 127.0.0.1 >nul
