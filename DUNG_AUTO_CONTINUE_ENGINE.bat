@echo off
chcp 65001 >nul
title DỪNG ANTIGRAVITY AUTO-CONTINUE ENGINE
cls
echo ===============================================================================
echo   🛑 DỪNG ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE
echo ===============================================================================
echo.

cd /d "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"

powershell -NoProfile -Command ^
    "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*antigravity_auto_continue_engine.py*' }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force; Write-Host ('[✓] Đã dừng tiến trình Daemon PID: ' + $p.ProcessId) -ForegroundColor Green } } else { Write-Host '[i] Không có tiến trình Auto-Continue Engine nào đang chạy.' -ForegroundColor Yellow }"

if exist "logs\auto_continue_engine.pid" (
    del /f /q "logs\auto_continue_engine.pid" >nul 2>&1
)

echo.
echo [✓] Đã hoàn tất giải phóng Mutex và dừng Daemon.
echo.
timeout /t 3 >nul
