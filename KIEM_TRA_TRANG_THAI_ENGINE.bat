@echo off
chcp 65001 >nul
title KIỂM TRA TRẠNG THÁI AUTO-CONTINUE ENGINE
cls
echo ===============================================================================
echo   🔍 KIỂM TRA TRẠNG THÁI ANTIGRAVITY AUTO-CONTINUE ENGINE
echo ===============================================================================
echo.

cd /d "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"

powershell -NoProfile -Command ^
    "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*antigravity_auto_continue_engine.py*' }; if ($procs) { Write-Host '[✓] ENGINE ĐANG HOẠT ĐỘNG (ACTIVE / RUNNING):' -ForegroundColor Green; foreach ($p in $procs) { Write-Host ('    • PID: ' + $p.ProcessId + ' | Dung luong RAM: ' + [math]::Round($p.WorkingSetSize / 1MB, 2) + ' MB') -ForegroundColor Cyan } } else { Write-Host '[!] Engine hiện KHÔNG hoạt động.' -ForegroundColor Yellow }"

echo.
echo ===============================================================================
echo  📜 15 DÒNG NHẬT KÝ GẦN NHẤT (logs\auto_continue_engine.log):
echo ===============================================================================
if exist "logs\auto_continue_engine.log" (
    powershell -NoProfile -Command "Get-Content 'logs\auto_continue_engine.log' -Tail 15"
) else (
    echo Chưa có tệp nhật ký.
)

echo.
echo ===============================================================================
pause
