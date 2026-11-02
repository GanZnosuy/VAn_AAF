@echo off
setlocal
chcp 65001 >nul
title DUNG ANTIGRAVITY AUTO-CONTINUE ENGINE
cls
echo ===============================================================================
echo   DUNG ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE
echo ===============================================================================
echo.

cd /d "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*.exe') -and ($_.CommandLine -like '*antigravity_auto_continue_engine.py*') }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('[OK] Da dung tien trinh PID: ' + $p.ProcessId) -ForegroundColor Green } } else { Write-Host '[INFO] Khong co tien trinh Auto-Continue Engine nao dang chay.' -ForegroundColor Yellow }"

if exist "logs\auto_continue_engine.pid" (
    del /f /q "logs\auto_continue_engine.pid" >nul 2>&1
)

echo.
echo [OK] Da hoan tat giai phong Mutex va dung Daemon.
echo.
ping -n 3 127.0.0.1 >nul
