@echo off
chcp 65001 >nul
title ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE
cls
echo ===============================================================================
echo   🚀 ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE (v1.0)
echo   Chế độ: Background Daemon Shield • Non-Stop Execution • Unbounded Tokens
echo ===============================================================================
echo.

cd /d "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"

:: 1. Kiểm tra môi trường Python
set "PYTHON_EXE="
if exist "C:\Users\vuong\AppData\Local\Programs\Python\Python312\pythonw.exe" (
    set "PYTHON_EXE=C:\Users\vuong\AppData\Local\Programs\Python\Python312\pythonw.exe"
) else if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHON_EXE=.venv\Scripts\pythonw.exe"
)

if "%PYTHON_EXE%"=="" (
    echo [!] Không tìm thấy Python runtime (pythonw.exe)!
    echo Vui lòng kiểm tra lại môi trường Python.
    pause
    exit /b 1
)

:: 2. Khởi động tiến trình ngầm qua VBScript (Silent / Không chiếm cửa sổ)
echo [*] Đang kích hoạt Daemon ngầm qua start_auto_continue_daemon.vbs...
wscript.exe "start_auto_continue_daemon.vbs"

timeout /t 2 /nobreak >nul

:: 3. Kiểm tra tiến trình
echo.
powershell -NoProfile -Command ^
    "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*antigravity_auto_continue_engine.py*' }; if ($procs) { Write-Host '[✓] DAEMON ĐÃ ĐƯỢC KÍCH HOẠT VÀ ĐANG CHẠY NGẦM THÀNH CÔNG!' -ForegroundColor Green; $procs | ForEach-Object { Write-Host ('    -> PID: ' + $_.ProcessId + ' | Khoi tao: ' + $_.CreationDate) -ForegroundColor Cyan } } else { Write-Host '[!] Khong phat hien tien trinh daemon chay. Kiem tra lai file log.' -ForegroundColor Yellow }"

echo.
echo ===============================================================================
echo  📋 Tệp nhật ký theo dõi (Real-time Logs):
echo     logs\auto_continue_engine.log
echo.
echo  🛑 Để dừng Daemon: Chạy DUNG_AUTO_CONTINUE_ENGINE.bat
echo ===============================================================================
echo.
timeout /t 4 >nul
