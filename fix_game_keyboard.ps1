# ==============================================================================
# GAME MODE & INSTANT KEYBOARD FIX (VALORANT / FPS 0ms INPUT LAG)
# ==============================================================================

Write-Host "⚡ Đang kích hoạt Chế độ Game (Fix trễ phím & kẹt phím WASD)..." -ForegroundColor Cyan

# 1. Dừng các tiến trình chiếm Hook bàn phím & ngốn CPU ngầm
Stop-Process -Name "cua-driver" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "ffmpeg" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "FluentFlyout" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "TFTAcademy" -Force -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process -Filter "Name like 'python%'" | ForEach-Object {
    if ($_.CommandLine -match "process_bilibili_vietsub|daily_shorts_autopilot") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# 2. Đặt UniKey về chế độ Tiếng Anh [E] + Tắt ClipboardConvert & SpellCheck để không nuốt phím WASD
Stop-Process -Name "UniKeyNT" -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Software\PkLong\UniKey" -Name "Vietnamese" -Value 0 -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Software\PkLong\UniKey" -Name "ClipboardConvert" -Value 0 -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Software\PkLong\UniKey" -Name "SpellCheckEnabled" -Value 0 -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Software\PkLong\UniKey" -Name "AutoNonVnRestore" -Value 0 -ErrorAction SilentlyContinue

$ukPath = "C:\Users\vuong\Downloads\unikey46RC2-230919-win64\UniKeyNT.exe"
if (Test-Path $ukPath) {
    Start-Process -FilePath $ukPath
}

# 3. Hạ LowLevelHooksTimeout từ 1000ms xuống 50ms (Chống kẹt chuỗi Hook bàn phím Windows)
Set-ItemProperty -Path "HKCU:\Control Panel\Desktop" -Name "LowLevelHooksTimeout" -Value 50 -Type DWord -ErrorAction SilentlyContinue

# 4. Tắt Filter Keys, Sticky Keys, Toggle Keys & Tối ưu tốc độ phản hồi phím
Set-ItemProperty -Path "HKCU:\Control Panel\Accessibility\Keyboard Response" -Name "Flags" -Value "122" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Control Panel\Accessibility\StickyKeys" -Name "Flags" -Value "506" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Control Panel\Accessibility\ToggleKeys" -Name "Flags" -Value "58" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Control Panel\Keyboard" -Name "KeyboardDelay" -Value "0" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Control Panel\Keyboard" -Name "KeyboardSpeed" -Value "31" -ErrorAction SilentlyContinue

# 5. Hạ ưu tiên các app nền ngốn CPU và tăng ưu tiên cho Game (VALORANT)
Get-Process -Name "SignalRgb", "wallpaper32" -ErrorAction SilentlyContinue | ForEach-Object { $_.PriorityClass = "Idle" }
Get-Process -Name "VALORANT-Win64-Shipping" -ErrorAction SilentlyContinue | ForEach-Object { $_.PriorityClass = "High" }

Write-Host "✅ Đã tối ưu bàn phím 0ms & giải phóng CPU cho Game thành công!" -ForegroundColor Green
