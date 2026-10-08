# ==============================================================================
# SCRIPT DANG KY LICH HEN GIO 10H TOI (22:00) HANG NGAY TREN WINDOWS
# ==============================================================================

$taskName = "AutoEdu_Nightly_Homework_Solver"
$projectDir = "C:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"
$scriptPath = Join-Path $projectDir "auto_nightly_worker.py"
$logPath = Join-Path $projectDir "logs\nightly_solver.log"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "THIET LAP TU DONG LAM BAI TAP VE NHA LUC 22:00 HANG NGAY" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Kiem tra file script
if (-not (Test-Path $scriptPath)) {
    Write-Host "[X] Loi: Khong tim thay file $scriptPath" -ForegroundColor Red
    exit 1
}

# 2. Dinh nghia Action chay ngam qua powershell
$actionArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"Set-Location '$projectDir'; uv run python '$scriptPath'`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs -WorkingDirectory $projectDir

# 3. Dinh nghia Trigger: 22:00 hang ngay
$trigger = New-ScheduledTaskTrigger -Daily -At "10:00PM"

# 4. Dinh nghia Cai dat nang cao:
# - WakeToRun: Danh thuc may neu dang Sleep
# - StartWhenAvailable: Neu 10h toi tat may, khi bat may se tu dong chay bu ngay
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# 5. Dang ky Task vao Windows Task Scheduler
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Tu dong kiem tra va giai bai tap tren Onluyen.vn luc 22:00 hang ngay" | Out-Null

    Write-Host "`n[v] DA CAI DAT THANH CONG TAC VU VAO WINDOWS TASK SCHEDULER!" -ForegroundColor Green
    Write-Host "    - Ten tac vu:   $taskName" -ForegroundColor White
    Write-Host "    - Lich chay:    Dung 22:00 (10:00 PM) moi toi" -ForegroundColor White
    Write-Host "    - Co che:       Chay ngam (Headless), khong hien cua so che man hinh" -ForegroundColor White
    Write-Host "    - Chay bu:      Co (Tu dong chay ngay khi mo may neu luc 22:00 tat may)" -ForegroundColor White
    Write-Host "    - Danh thuc:    Co (Tu danh thuc may tinh neu dang o che do Sleep)" -ForegroundColor White
    Write-Host "    - Nhat ky luu:  $logPath" -ForegroundColor Gray

    Write-Host "`nCAC LENH HO TRO NHANH:" -ForegroundColor Cyan
    Write-Host "  1. Chay thu nghiem ngay lap tuc de kiem tra:" -ForegroundColor Yellow
    Write-Host "     Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
    Write-Host "  2. Xem trang thai tac vu:" -ForegroundColor Yellow
    Write-Host "     Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
    Write-Host "  3. Huy bo tac vu (khi khong muon tu lam nua):" -ForegroundColor Yellow
    Write-Host "     Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor White
    Write-Host "======================================================================`n" -ForegroundColor Cyan
} catch {
    Write-Host "[X] Loi khi dang ky Task Scheduler: $_" -ForegroundColor Red
}
