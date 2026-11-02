@echo off
setlocal
chcp 65001 >nul
title KIEM TRA TRANG THAI AUTO-CONTINUE ENGINE
cls
echo ===============================================================================
echo   KIEM TRA TRANG THAI ANTIGRAVITY AUTO-CONTINUE ENGINE
echo ===============================================================================
echo.

cd /d "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*.exe') -and ($_.CommandLine -like '*antigravity_auto_continue_engine.py*') }; if ($procs) { Write-Host '[OK] ENGINE DANG HOAT DONG (ACTIVE / RUNNING):' -ForegroundColor Green; foreach ($p in $procs) { Write-Host ('    * PID: ' + $p.ProcessId + ' | RAM: ' + [math]::Round($p.WorkingSetSize / 1MB, 2) + ' MB') -ForegroundColor Cyan } } else { Write-Host '[INFO] Engine hien KHONG hoat dong.' -ForegroundColor Yellow }"

echo.
echo ===============================================================================
echo  15 DONG NHAT KY GAN NHAT (logs\auto_continue_engine.log):
echo ===============================================================================
if exist "logs\auto_continue_engine.log" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content 'logs\auto_continue_engine.log' -Tail 15"
) else (
    echo Chua co tep nhat ky.
)

echo.
echo ===============================================================================
pause
