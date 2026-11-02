@echo off
chcp 65001 >nul
title LÀM MỚI COOKIE GEMINI WEB API
echo ========================================================
echo  ĐANG LÀM MỚI COOKIES CHO TẤT CẢ DỰ ÁN GEMINI TRÊN MÁY...
echo ========================================================
"C:\Users\vuong\AppData\Local\Programs\Python\Python312\python.exe" "c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG\gemini_cookie_daemon.py" --once
echo.
if %ERRORLEVEL% EQU 0 (
    echo [THÀNH CÔNG] Tất cả ứng dụng Gemini đã được đồng bộ cookie mới nhất!
) else (
    echo [CẢNH BÁO] Có lỗi xảy ra trong quá trình làm mới cookie.
)
echo.
pause
