@echo off
chcp 65001 >nul 2>&1
title AUTOEDU - Tu Dong Lam Bai Tap Onluyen Hourly

set "PY=C:\Users\vuong\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
    set "PY=python"
)

"%PY%" "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG\auto_worker_menu.py"

if %ERRORLEVEL% neq 0 (
    echo.
    echo Da dung hoac co loi. Nhan phim bat ky de thoat...
    pause >nul
)
