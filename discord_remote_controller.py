# -*- coding: utf-8 -*-
"""
discord_remote_controller.py (v4.0 - Interactive Mobile PC Remote & AI Hub)
================================================================================
Hệ thống điều khiển máy tính & tương tác Antigravity 2 chiều qua Discord Bot.
Nâng cấp toàn diện với:
1. 🛡️ Single-Instance Kernel Mutex: Chống triệt để việc mở trùng lặp bot (loại bỏ 100% hiện tượng gửi lặp 2 tin nhắn).
2. ⚡ Discord Gateway WebSocket (discord.py): Nhận tương tác siêu tốc < 0.1s, không polling HTTP gây lag CPU.
3. 📱 Lệnh duy nhất `!ask`: Hiển thị Trung tâm Điều khiển Tương tác gồm Menu ô lựa chọn (Dropdown) & Nút bấm (Buttons)
   -> Chỉ cần 1 click trên điện thoại là thực thi ngay, KHÔNG CẦN PHẢI GÕ LỆNH `!`.
4. 💬 Hộp thoại tương tác (Modal Popup): Bấm nút "Hỏi đáp AI" sẽ hiện popup trên điện thoại để nhập câu hỏi cho AI.
5. 🔄 Hỗ trợ đầy đủ các lệnh cũ và ngôn ngữ tự nhiên.
"""

import os
import re
import sys
import time
import json
import socket
import asyncio
import ctypes
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import deque

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

BOT_RUNNER_LOG = LOG_DIR / "discord_bot_runner.log"
SCREENSHOT_TEMP = RESULTS_DIR / "remote_desktop_screen.png"
GDRIVE_EXE = Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "plugin_data" / "gdrive" / "bin" / "gdrive-986250228.exe"

# Thiết lập an toàn cho stdout và stderr (đặc biệt khi chạy nền qua pythonw.exe)
if sys.platform == "win32":
    if sys.stdout is None:
        try:
            sys.stdout = open(BOT_RUNNER_LOG, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stdout = open(os.devnull, "w")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:
            pass

    if sys.stderr is None:
        try:
            sys.stderr = open(BOT_RUNNER_LOG, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stderr = open(os.devnull, "w")
    else:
        try:
            sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:
            pass

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ==============================================================================
# 1. BẢO VỆ ĐỘC QUYỀN TIẾN TRÌNH (SINGLE INSTANCE KERNEL MUTEX)
# ==============================================================================

import psutil
import msvcrt

_LOCK_FILE = None
_MUTEX_HANDLE = None
LOCK_FILE_PATH = LOG_DIR / "discord_bot.lock"

def cleanup_other_bot_instances():
    """Dọn dẹp triệt để bất kỳ tiến trình bot discord nào khác đang chạy trên hệ thống."""
    my_pid = os.getpid()
    my_ppid = os.getppid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid in (my_pid, my_ppid):
                continue
            pname = (proc.info.get('name') or '').lower()
            if 'python' in pname:
                cmdline = proc.info.get('cmdline') or []
                cmd_str = ' '.join(cmdline).lower()
                if 'discord_remote_controller.py' in cmd_str:
                    print(f"[!] Dọn dẹp tiến trình bot cũ (PID {proc.pid})...")
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def acquire_single_instance_lock() -> bool:
    """
    Bảo đảm TUYỆT ĐỐI chỉ có DUY NHẤT 1 BOT được phép chạy trên máy tính.
    Sử dụng Windows Kernel Mutex kết hợp dọn dẹp tiến trình cũ.
    Loại bỏ 100% nguyên nhân gửi lặp 2 tin nhắn và lag máy do nhiều tiến trình bot chạy song song.
    """
    global _MUTEX_HANDLE, _LOCK_FILE
    my_pid = os.getpid()

    # Bước 1: Quét dọn các tiến trình bot cũ
    cleanup_other_bot_instances()
    time.sleep(0.5)

    # Bước 2: Chiếm giữ Windows Kernel Mutex
    ERROR_ALREADY_EXISTS = 183
    mutex_name = "Global\\Antigravity_Discord_Remote_Controller_Kernel_Mutex"
    _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_err = ctypes.windll.kernel32.GetLastError()
    if last_err == ERROR_ALREADY_EXISTS:
        print("[!] Đã có phiên bản Discord Remote Controller khác đang chạy độc quyền. Thoát ngay.")
        return False

    # Bước 3: Ghi nhận PID vào lock file
    try:
        LOCK_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_FILE = open(LOCK_FILE_PATH, "w", encoding="utf-8")
        _LOCK_FILE.write(f"{my_pid}\n")
        _LOCK_FILE.flush()
    except Exception:
        pass

    print(f"[✓] Đã kích hoạt bảo vệ Single-Instance Mutex thành công (PID: {my_pid}).")
    return True

# ==============================================================================
# 2. LOAD THƯ VIỆN & CẤU HÌNH ANTIGRAVITY / DISCORD
# ==============================================================================

from discord_notifier import (
    load_env_discord,
    send_discord_message,
    send_discord_photo,
    notify_task_completed,
    notify_interrupted_or_disconnected,
    get_iso_timestamp
)
from discord_antigravity_watcher import (
    DEFAULT_BRAIN_DIR,
    find_latest_transcript,
    extract_user_goal,
    clean_agent_summary,
    AntigravityWatcher
)

try:
    from autoedu.ai.gemini_web import GeminiWebClient
    HAS_GEMINI_WEB = True
except Exception as e:
    HAS_GEMINI_WEB = False
    print(f"[!] Chưa nạp được module GeminiWebClient: {e}")

# Trạng thái toàn cục
CONTROLLER_STATE = {
    "selected_transcript": None,
    "selected_conv_id": None,
    "selected_window_id": None,
    "selected_window_title": None,
    "watcher": None
}

ALLOWED_DISCORD_USER_IDS = set()

def get_allowed_discord_user_ids() -> set:
    """Đọc danh sách Discord User ID được phép điều khiển từ .env."""
    global ALLOWED_DISCORD_USER_IDS
    if ALLOWED_DISCORD_USER_IDS:
        return ALLOWED_DISCORD_USER_IDS

    env_path = BASE_DIR / ".env"
    raw_ids = os.getenv("DISCORD_ALLOWED_USER_IDS", "").strip()
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DISCORD_ALLOWED_USER_IDS="):
                    raw_ids = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    res = set()
    for item in raw_ids.replace(",", " ").split():
        if item.isdigit():
            res.add(item)
    ALLOWED_DISCORD_USER_IDS = res
    return res

# ==============================================================================
# 3. CÁC HÀM XỬ LÝ HỆ THỐNG MÁY TÍNH & THAO TÁC PHẦN CỨNG
# ==============================================================================

def query_gemini_web(prompt: str) -> str:
    """Gửi câu hỏi trực tiếp đến Google Gemini Web AI với Gemini 3.8 Flash / Argon High."""
    if not HAS_GEMINI_WEB:
        return "Chưa kết nối (Module Gemini Web chưa được cấu hình cookies hoặc thư viện)."
    try:
        client = GeminiWebClient(model="gemini-3.8-flash", thinking_level="high")
        res = asyncio.run(client.query(prompt))
        if not res or not res.strip():
            return "Chưa kết nối (Không nhận được phản hồi từ Gemini Web AI. Vui lòng kiểm tra cookies hoặc mạng internet)."
        return res
    except Exception as e:
        return f"Chưa kết nối (Lỗi kết nối Gemini Web AI: {e})"

def format_ai_embed(query: str, ans: str, author_name: str) -> discord.Embed:
    """Định dạng Embed phản hồi AI: Hiển thị cảnh báo màu đỏ nếu chưa kết nối, Embed chuẩn nếu thành công."""
    is_disconnected = "chưa kết nối" in ans.lower() or "không thể kết nối" in ans.lower() or ans.startswith("⚠️")
    if is_disconnected:
        embed = discord.Embed(
            title="⚠️ CHƯA KẾT NỐI — GEMINI WEB AI",
            description=(
                f"👤 **Yêu cầu:** *{query[:200]}*\n\n"
                f"🔴 **Trạng thái:** {ans}\n\n"
                f"💡 **Hướng dẫn khắc phục:**\n"
                f"1. Kiểm tra kết nối mạng Internet của máy tính.\n"
                f"2. Chạy file `CAP_NHAT_COOKIE_GEMINI_NGAY.bat` trên Desktop để cập nhật Cookie Google Gemini mới nhất.\n"
                f"3. Hoặc đảm bảo cổng Antigravity Tools Gateway (8045) đang hoạt động."
            ),
            color=0xED4245,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name} • Trạng thái: Chưa kết nối")
    else:
        embed = discord.Embed(
            title="✨ GOOGLE GEMINI 3.8 FLASH / ARGON (HIGH THINKING)",
            description=f"👤 **Yêu cầu:** *{query[:200]}*\n\n{ans[:3800]}",
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name} • Phản hồi từ Gemini Web AI (Mức tư duy: High)")
    return embed

def get_system_info() -> dict:
    """Lấy thông tin CPU, RAM, Disk C:, Uptime qua PowerShell."""
    ps_cmd = """
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    $cpuName = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)
    $totalRam = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
    $freeRam = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
    $usedRam = [math]::Round($totalRam - $freeRam, 2)
    $ramPercent = [math]::Round(($usedRam / $totalRam) * 100, 1)

    $drive = Get-PSDrive C -ErrorAction SilentlyContinue
    $freeDisk = if ($drive) { [math]::Round($drive.Free / 1GB, 2) } else { 0 }
    $totalDisk = if ($drive) { [math]::Round(($drive.Used + $drive.Free) / 1GB, 2) } else { 0 }

    $uptime = (Get-Date) - $os.LastBootUpTime
    $uptimeStr = "{0} ngày {1} giờ {2} phút" -f $uptime.Days, $uptime.Hours, $uptime.Minutes

    [PSCustomObject]@{
        CPU = "$cpu%"
        CPUName = "$cpuName"
        RAM = "$usedRam GB / $totalRam GB ($ramPercent%)"
        DiskC = "$freeDisk GB trống / $totalDisk GB"
        Uptime = $uptimeStr
        User = $env:USERNAME
        Computer = $env:COMPUTERNAME
    } | ConvertTo-Json -Compress
    """
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=8)
        return json.loads(res.stdout.strip())
    except Exception as e:
        return {"Error": str(e)}

def get_network_info() -> dict:
    """Kiểm tra mạng Internet, Ping Google, Cloudflare, IP LAN, Gateway."""
    ps_cmd = """
    $pingGoogle = Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet -ErrorAction SilentlyContinue
    $pingCloudflare = Test-Connection -ComputerName 1.1.1.1 -Count 1 -Quiet -ErrorAction SilentlyContinue
    $ipV4 = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*", "Wi-Fi*" -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch "^169\\." } | Select-Object -ExpandProperty IPAddress) -join ", "
    $gateway = (Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty NextHop) -join ", "
    $adapters = (Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Up" } | Select-Object -ExpandProperty Name) -join ", "

    [PSCustomObject]@{
        Internet = if ($pingGoogle -or $pingCloudflare) { "Hoạt động BÌNH THƯỜNG (Online) 🟢" } else { "BỊ CHẶN / MẤT MẠNG INTERNET 🔴" }
        PingGoogle = if ($pingGoogle) { "Thành công (8.8.8.8) ✅" } else { "Thất bại ❌" }
        PingCloudflare = if ($pingCloudflare) { "Thành công (1.1.1.1) ✅" } else { "Thất bại ❌" }
        LocalIP = if ($ipV4) { $ipV4 } else { "Không có IP" }
        Gateway = if ($gateway) { $gateway } else { "Không xác định" }
        Adapters = if ($adapters) { $adapters } else { "Không có kết nối" }
    } | ConvertTo-Json -Compress
    """
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=8)
        return json.loads(res.stdout.strip())
    except Exception as e:
        return {"Error": str(e)}

def get_battery_info() -> str:
    """Lấy trạng thái pin / nguồn điện."""
    ps_cmd = """
    $battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
    if ($battery) {
        $status = if ($battery.BatteryStatus -eq 2) { "Đang sạc ⚡" } else { "Đang dùng pin 🔋" }
        "$($battery.EstimatedChargeRemaining)% ($status)"
    } else {
        "PC để bàn (Nguồn điện trực tiếp 🔌)"
    }
    """
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=5)
        return res.stdout.strip() or "Không xác định"
    except Exception:
        return "PC để bàn (Nguồn trực tiếp)"

def capture_desktop_screenshot(output_path: Path) -> bool:
    """Chụp ảnh màn hình Desktop bằng .NET System.Windows.Forms."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ps_script = """
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $bitmap.Save($env:AGY_SCREENSHOT_PATH, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
    """
    try:
        env = os.environ.copy()
        env["AGY_SCREENSHOT_PATH"] = str(output_path)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            env=env,
            capture_output=True,
            timeout=15
        )
        return res.returncode == 0 and output_path.exists()
    except Exception as e:
        print(f"[!] Lỗi chụp màn hình: {e}")
        return False

def control_volume(action: str) -> str:
    """Điều chỉnh âm lượng loa: up, down, mute."""
    action = action.lower().strip()
    if action == "mute":
        ps_cmd = "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]173)"
        msg = "🔇 Đã bật/tắt chế độ Mute (Câm tiếng) trên loa máy tính!"
    elif action == "up":
        ps_cmd = "$w = New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object { $w.SendKeys([char]175); Start-Sleep -Milliseconds 50 }"
        msg = "🔊 Đã tăng âm lượng máy tính (+10%)!"
    elif action == "down":
        ps_cmd = "$w = New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object { $w.SendKeys([char]174); Start-Sleep -Milliseconds 50 }"
        msg = "🔉 Đã giảm âm lượng máy tính (-10%)!"
    else:
        return "⚠️ Lệnh không hợp lệ."
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=5)
        return msg
    except Exception as e:
        return f"⚠️ Lỗi: {e}"

def lock_screen() -> bool:
    """Khóa màn hình máy tính (Lock WorkStation)."""
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
        return True
    except Exception:
        return False

def sleep_pc() -> bool:
    """Đưa máy tính vào chế độ Sleep."""
    try:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], timeout=5)
        return True
    except Exception:
        return False

def get_gdrive_quota_info() -> str:
    """Kiểm tra dung lượng Google Drive 5TB."""
    if not GDRIVE_EXE.exists():
        return "⚠️ Không tìm thấy công cụ gdrive CLI trên máy tính."
    try:
        res = subprocess.run([str(GDRIVE_EXE), "readonly", "quota"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        out = res.stdout.strip() or res.stderr.strip()
        return f"```\n{out}\n```\n📌 **Tài khoản:** `vuongvanan1904@gmail.com` (Gói 5 TB)"
    except Exception as e:
        return f"⚠️ Lỗi kiểm tra Google Drive: {e}"

def inject_prompt_to_antigravity(prompt_text: str, create_new_chat: bool = False) -> bool:
    """Đưa cửa sổ Antigravity lên trên, dán prompt vào ô chat và nhấn Enter."""
    ps_script = """
    Add-Type -AssemblyName System.Windows.Forms
    $wshell = New-Object -ComObject wscript.shell
    $targetPid = $env:AGY_TARGET_PID
    $activated = $false

    if ($targetPid) {
        try {
            $activated = $wshell.AppActivate([int]$targetPid)
            Start-Sleep -Milliseconds 500
        } catch {}
    }

    if (-not $activated) {
        $procs = Get-Process | Where-Object { $_.MainWindowTitle -match "Antigravity|CAIDATHETTHONG" }
        if ($procs) {
            $wshell.AppActivate($procs[0].Id) | Out-Null
            Start-Sleep -Milliseconds 500
        }
    }

    if ($env:AGY_NEW_CHAT -eq "1") {
        [System.Windows.Forms.SendKeys]::SendWait("^l")
        Start-Sleep -Milliseconds 400
        [System.Windows.Forms.SendKeys]::SendWait("^+n")
        Start-Sleep -Milliseconds 600
    }

    if ($env:AGY_REMOTE_PROMPT) {
        Set-Clipboard -Value $env:AGY_REMOTE_PROMPT
        Start-Sleep -Milliseconds 300
        [System.Windows.Forms.SendKeys]::SendWait("^v")
        Start-Sleep -Milliseconds 400
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    }
    """
    try:
        env = os.environ.copy()
        env["AGY_REMOTE_PROMPT"] = prompt_text or ""
        env["AGY_NEW_CHAT"] = "1" if create_new_chat else "0"
        env["AGY_TARGET_PID"] = str(CONTROLLER_STATE.get("selected_window_id") or "")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            env=env,
            capture_output=True,
            timeout=15
        )
        return res.returncode == 0
    except Exception as e:
        print(f"[!] Lỗi gửi lệnh vào Antigravity: {e}")
        return False

def get_deep_agent_status(target_path: Path = None) -> dict:
    """Phân tích transcript.jsonl để xác định trạng thái làm việc của Antigravity Agent."""
    transcript = target_path or CONTROLLER_STATE.get("selected_transcript") or find_latest_transcript()
    conv_id = transcript.parent.parent.parent.name if (transcript and transcript.exists()) else "Chưa xác định"
    short_id = conv_id[:8] if len(conv_id) >= 8 else conv_id

    status_code = "IDLE"
    status_label = "🟢 ĐÃ HOÀN THÀNH (ĐANG CHỜ LỆNH)"
    last_action = "Sẵn sàng nhận câu hỏi & lệnh điều khiển mới qua Discord"
    last_user_goal = "Chưa có yêu cầu mới"
    last_answer = ""
    total_steps = 0
    elapsed_str = "Vừa xong"
    color = 0x57F287

    if transcript and transcript.exists():
        try:
            with open(transcript, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                total_steps = len(lines)

            parsed_tail = []
            for l in lines[-350:]:
                if l.strip():
                    try:
                        parsed_tail.append(json.loads(l.strip()))
                    except Exception:
                        pass

            for step in reversed(parsed_tail):
                stype = step.get("type")
                src = step.get("source")
                content = (step.get("content") or "").strip()
                if (stype == "USER_INPUT" or src == "USER_EXPLICIT") and content:
                    m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
                    if m:
                        last_user_goal = m.group(1).strip()
                    else:
                        last_user_goal = content.split("\n")[0][:150]
                    break

            for step in reversed(parsed_tail):
                stype = step.get("type")
                content = (step.get("content") or "").strip()
                if stype == "PLANNER_RESPONSE" and not step.get("tool_calls") and content:
                    last_answer = clean_agent_summary(content)
                    break

            if parsed_tail:
                last_step = parsed_tail[-1]
                stype = last_step.get("type")
                t_calls = last_step.get("tool_calls") or []
                created_at = last_step.get("created_at")
                if created_at:
                    try:
                        step_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        now_dt = datetime.now(timezone.utc)
                        diff_sec = max(0, int((now_dt - step_dt).total_seconds()))
                        if diff_sec < 60:
                            elapsed_str = f"{diff_sec} giây trước"
                        else:
                            elapsed_str = f"{diff_sec // 60} phút {diff_sec % 60} giây trước"
                    except Exception:
                        pass

                if t_calls:
                    first_tc = t_calls[0]
                    tool_name = first_tc.get("tool", "Công cụ")
                    args = first_tc.get("args") or {}
                    summary = args.get("toolSummary") or tool_name
                    status_code = "WORKING"
                    status_label = "⚡ ĐANG THỰC THI NHIỆM VỤ"
                    last_action = f"Đang chạy {tool_name}: {summary}"
                    color = 0x3498DB
                elif stype == "PLANNER_RESPONSE":
                    if last_step.get("thinking") and not last_step.get("content"):
                        status_code = "THINKING"
                        status_label = "💭 ĐANG SUY NGHĨ / LẬP KẾ HOẠCH"
                        last_action = "Agent đang suy luận chiến lược tiếp theo..."
                        color = 0x9B59B6
                    else:
                        status_code = "IDLE"
                        status_label = "🟢 ĐÃ HOÀN THÀNH BƯỚC / ĐANG CHỜ"
                        last_action = "Đã gửi câu trả lời, đang chờ phản hồi hoặc lệnh tiếp theo"
                        color = 0x57F287
        except Exception as e:
            last_action = f"Lỗi đọc transcript: {e}"

    return {
        "status_code": status_code,
        "status_label": status_label,
        "last_action": last_action,
        "last_user_goal": last_user_goal,
        "last_answer": last_answer,
        "total_steps": total_steps,
        "elapsed_str": elapsed_str,
        "short_id": short_id,
        "color": color
    }

# ==============================================================================
# 4. GIAO DIỆN TƯƠNG TÁC DISCORD (DISCORD.UI COMPONENTS CHO LỆNH !ASK)
# ==============================================================================

class AskModal(discord.ui.Modal, title="💬 Hỏi Đáp AI (3.8 Flash / Argon High)"):
    """Cửa sổ Modal Popup xuất hiện trên điện thoại để người dùng gõ nội dung."""
    prompt_input = discord.ui.TextInput(
        label="Nội dung câu hỏi hoặc công việc cần làm:",
        style=discord.TextStyle.paragraph,
        placeholder="Ví dụ: Giải bài tập Onluyen, kiểm tra code, mở trình duyệt, tóm tắt bài giảng...",
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        query = self.prompt_input.value.strip()
        author_name = interaction.user.display_name

        if HAS_GEMINI_WEB:
            ans = await asyncio.to_thread(query_gemini_web, query)
            embed = format_ai_embed(query, ans, author_name)
            await interaction.followup.send(embed=embed)
        else:
            await asyncio.to_thread(inject_prompt_to_antigravity, query)
            embed = discord.Embed(
                title="🤖 ĐÃ GỬI LỆNH TỚI ANTIGRAVITY AGENT TRÊN PC",
                description=f"👤 **Yêu cầu:** *{query}*\n\nAgent đang thực thi trên máy tính của bạn...",
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.followup.send(embed=embed)

async def handle_action(interaction: discord.Interaction, action: str):
    """Xử lý hành động từ ô lựa chọn (Dropdown) hoặc nút bấm (Button)."""
    author_id = str(interaction.user.id)
    author_name = interaction.user.display_name
    allowed_ids = get_allowed_discord_user_ids()
    if allowed_ids and author_id not in allowed_ids:
        await interaction.response.send_message(
            f"⛔ **CẢNH BÁO BẢO MẬT:** Người dùng `{author_name}` (`{author_id}`) không có quyền điều khiển máy tính này.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    if action == "action_screen":
        ok = await asyncio.to_thread(capture_desktop_screenshot, SCREENSHOT_TEMP)
        if ok and SCREENSHOT_TEMP.exists():
            embed = discord.Embed(
                title="📸 ẢNH CHỤP MÀN HÌNH DESKTOP HIỆN TẠI",
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Yêu cầu bởi {author_name} • Lúc {datetime.now().strftime('%H:%M:%S')}")
            file = discord.File(str(SCREENSHOT_TEMP), filename="screenshot.png")
            embed.set_image(url="attachment://screenshot.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send("⚠️ Không thể chụp ảnh màn hình hoặc màn hình đang bị khóa bảo vệ.")

    elif action == "action_pc":
        info = await asyncio.to_thread(get_system_info)
        if "Error" in info:
            await interaction.followup.send(f"⚠️ Lỗi lấy thông tin hệ thống: {info['Error']}")
            return
        embed = discord.Embed(
            title="💻 THÔNG SỐ & TRẠNG THÁI MÁY TÍNH HIỆN TẠI",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="⚙️ CPU Usage", value=f"`{info.get('CPU')}`\n*({info.get('CPUName', '')[:35]})*", inline=True)
        embed.add_field(name="🧠 Bộ nhớ RAM", value=f"`{info.get('RAM')}`", inline=True)
        embed.add_field(name="💾 Ổ đĩa C:", value=f"`{info.get('DiskC')}`", inline=True)
        embed.add_field(name="⏱️ Thời gian hoạt động", value=f"`{info.get('Uptime')}`", inline=True)
        embed.add_field(name="👤 Người dùng", value=f"`{info.get('User')}@{info.get('Computer')}`", inline=True)
        bat = await asyncio.to_thread(get_battery_info)
        embed.add_field(name="🔋 Nguồn / Pin", value=f"`{bat}`", inline=True)
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action == "action_net":
        net = await asyncio.to_thread(get_network_info)
        if "Error" in net:
            await interaction.followup.send(f"⚠️ Lỗi kiểm tra mạng: {net['Error']}")
            return
        embed = discord.Embed(
            title="🌐 KẾT QUẢ KIỂM TRA MẠNG & INTERNET MÁY TÍNH",
            color=0x57F287 if "BÌNH THƯỜNG" in net.get('Internet', '') else 0xED4245,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📡 Trạng thái Internet", value=f"**{net.get('Internet')}**", inline=False)
        embed.add_field(name="🔍 Ping Google DNS (8.8.8.8)", value=f"`{net.get('PingGoogle')}`", inline=True)
        embed.add_field(name="🔍 Ping Cloudflare (1.1.1.1)", value=f"`{net.get('PingCloudflare')}`", inline=True)
        embed.add_field(name="🏠 IP Mạng LAN", value=f"`{net.get('LocalIP')}`", inline=True)
        embed.add_field(name="🚪 Default Gateway (Router)", value=f"`{net.get('Gateway')}`", inline=True)
        embed.add_field(name="🔌 Card mạng hoạt động", value=f"`{net.get('Adapters')}`", inline=True)
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action == "action_status":
        st = await asyncio.to_thread(get_deep_agent_status)
        embed = discord.Embed(
            title="🤖 BÁO CÁO TIẾN ĐỘ ANTIGRAVITY AI AGENT",
            color=st["color"],
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📊 Trạng thái Agent", value=f"**{st['status_label']}**", inline=False)
        embed.add_field(name="🎯 Mục tiêu gần nhất", value=f"*{st['last_user_goal'][:250]}*", inline=False)
        embed.add_field(name="⚡ Hành động đang/vừa làm", value=f"`{st['last_action'][:250]}`", inline=False)
        embed.add_field(name="📈 Tổng số bước thực thi", value=f"`{st['total_steps']} bước`", inline=True)
        embed.add_field(name="⏱️ Hoạt động lần cuối", value=f"`{st['elapsed_str']}`", inline=True)
        embed.add_field(name="📁 Chat ID", value=f"`{st['short_id']}`", inline=True)
        if st.get("last_answer"):
            embed.add_field(name="💬 Phản hồi gần nhất của Agent", value=f"{st['last_answer'][:500]}", inline=False)
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action == "action_solve":
        def _run_solver():
            script_path = BASE_DIR / "auto_nightly_worker.py"
            pyw_exe = str(Path(sys.executable).parent / "pythonw.exe")
            if not os.path.exists(pyw_exe):
                pyw_exe = sys.executable
            subprocess.run([pyw_exe, str(script_path), "--once"])
        threading.Thread(target=_run_solver, daemon=True).start()

        embed = discord.Embed(
            title="📚 AUTOEDU ONLUYEN SOLVER",
            description=(
                "🚀 **ĐÃ KÍCH HOẠT TIẾN TRÌNH GIẢI BÀI TẬP TỰ ĐỘNG!**\n\n"
                "• **Mô hình AI:** Gemini 3.8 Flash siêu tốc (~2-3s/câu)\n"
                "• **Chế độ:** Quét Onluyen.vn, tự động giải bài và nộp bài\n"
                "• **Thông báo:** Ảnh kết quả và bảng điểm sẽ tự động gửi về Discord ngay khi nộp bài xong."
            ),
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action == "action_away":
        info = await asyncio.to_thread(get_system_info)
        net = await asyncio.to_thread(get_network_info)
        st = await asyncio.to_thread(get_deep_agent_status)
        ok_screen = await asyncio.to_thread(capture_desktop_screenshot, SCREENSHOT_TEMP)

        embed = discord.Embed(
            title="🏠 BÁO CÁO TOÀN DIỆN MÁY TÍNH KHI VẮNG NHÀ (AWAY MODE)",
            description=f"Xin chào **{author_name}**! Đây là trạng thái tổng quan máy tính của bạn lúc này:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="🤖 AI Agent", value=f"**{st['status_label']}**\n{st['last_action'][:150]}", inline=False)
        embed.add_field(name="💻 Thông số PC", value=f"CPU: `{info.get('CPU')}` | RAM: `{info.get('RAM')}`\nỔ C: `{info.get('DiskC')}` | Uptime: `{info.get('Uptime')}`", inline=False)
        embed.add_field(name="🌐 Mạng Internet", value=f"{net.get('Internet')}\nPing Google: `{net.get('PingGoogle')}` | IP: `{net.get('LocalIP')}`", inline=False)
        embed.set_footer(text=f"Cập nhật lúc {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")

        if ok_screen and SCREENSHOT_TEMP.exists():
            file = discord.File(str(SCREENSHOT_TEMP), filename="away_screen.png")
            embed.set_image(url="attachment://away_screen.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    elif action == "action_lock":
        await asyncio.to_thread(lock_screen)
        embed = discord.Embed(
            title="🔒 ĐÃ KHÓA MÀN HÌNH MÁY TÍNH",
            description="Màn hình Windows đã được khóa an toàn (Lock Workstation). Mọi tác vụ vẫn đang chạy bình thường phía sau.",
            color=0xED4245,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action == "action_sleep":
        embed = discord.Embed(
            title="💤 ĐANG ĐƯA MÁY TÍNH VÀO CHẾ ĐỘ SLEEP",
            description="Máy tính sẽ chuyển sang chế độ Sleep (Ngủ) để tiết kiệm điện sau 2 giây nữa.",
            color=0xFEE75C,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)
        await asyncio.sleep(2)
        await asyncio.to_thread(sleep_pc)

    elif action == "action_battery":
        bat = await asyncio.to_thread(get_battery_info)
        embed = discord.Embed(
            title="🔋 THÔNG TIN NGUỒN ĐIỆN & PIN",
            description=f"Trạng thái hiện tại: **`{bat}`**",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action in ("action_vol_up", "action_vol_down", "action_vol_mute"):
        act_map = {"action_vol_up": "up", "action_vol_down": "down", "action_vol_mute": "mute"}
        res = await asyncio.to_thread(control_volume, act_map[action])
        embed = discord.Embed(
            title="🔊 ĐIỀU CHỈNH ÂM LƯỢNG MÁY TÍNH",
            description=res,
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

    elif action == "action_gdrive":
        quota = await asyncio.to_thread(get_gdrive_quota_info)
        embed = discord.Embed(
            title="📁 DUNG LƯỢNG GOOGLE DRIVE (GÓI 5 TB)",
            description=quota,
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Yêu cầu bởi {author_name}")
        await interaction.followup.send(embed=embed)

class AskActionSelect(discord.ui.Select):
    """Dropdown Menu ô lựa chọn chức năng xổ xuống."""
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Chụp màn hình Desktop",
                value="action_screen",
                description="Chụp ảnh màn hình máy tính gửi về điện thoại ngay",
                emoji="📸"
            ),
            discord.SelectOption(
                label="Kiểm tra thông số PC",
                value="action_pc",
                description="Xem CPU, RAM, Ổ cứng C:, Uptime máy tính",
                emoji="💻"
            ),
            discord.SelectOption(
                label="Kiểm tra mạng Internet",
                value="action_net",
                description="Ping Google, Cloudflare, IP LAN, Gateway",
                emoji="🌐"
            ),
            discord.SelectOption(
                label="Tiến độ AI Antigravity",
                value="action_status",
                description="Xem Agent đang làm gì, bước nào, đã xong chưa",
                emoji="🤖"
            ),
            discord.SelectOption(
                label="Kích hoạt giải bài Onluyen",
                value="action_solve",
                description="Tự động quét và giải bài tập trên Onluyen.vn",
                emoji="📚"
            ),
            discord.SelectOption(
                label="Báo cáo vắng nhà (Away Mode)",
                value="action_away",
                description="Tổng hợp toàn diện PC + AI Agent + Ảnh màn hình",
                emoji="🏠"
            ),
            discord.SelectOption(
                label="Hộp thoại hỏi đáp AI / Giao việc",
                value="action_ask_modal",
                description="Mở ô nhập để gửi câu hỏi hoặc giao việc cho AI",
                emoji="💬"
            ),
            discord.SelectOption(
                label="Khóa màn hình máy tính",
                value="action_lock",
                description="Khóa Windows Lock Workstation an toàn",
                emoji="🔒"
            ),
            discord.SelectOption(
                label="Chế độ ngủ (Sleep PC)",
                value="action_sleep",
                description="Cho máy tính vào chế độ Ngủ (Sleep)",
                emoji="💤"
            ),
            discord.SelectOption(
                label="Kiểm tra Pin / Nguồn điện",
                value="action_battery",
                description="Xem trạng thái sạc và phần trăm pin",
                emoji="🔋"
            ),
            discord.SelectOption(
                label="Tăng âm lượng loa (+10%)",
                value="action_vol_up",
                description="Tăng âm lượng loa máy tính từ xa",
                emoji="🔊"
            ),
            discord.SelectOption(
                label="Giảm âm lượng loa (-10%)",
                value="action_vol_down",
                description="Giảm âm lượng loa máy tính từ xa",
                emoji="🔉"
            ),
            discord.SelectOption(
                label="Bật / Tắt tiếng loa (Mute)",
                value="action_vol_mute",
                description="Tắt hoặc bật lại âm thanh loa máy tính",
                emoji="🔇"
            ),
            discord.SelectOption(
                label="Dung lượng Google Drive 5TB",
                value="action_gdrive",
                description="Kiểm tra dung lượng bộ nhớ Google Drive",
                emoji="📁"
            ),
        ]
        super().__init__(
            placeholder="👇 Bấm vào đây để chọn chức năng điều khiển...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ask_select_menu",
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "action_ask_modal":
            await interaction.response.send_modal(AskModal())
        else:
            await handle_action(interaction, val)

class AskControlView(discord.ui.View):
    """Giao diện tương tác Trung tâm Điều khiển: Dropdown + 2 Hàng Nút bấm."""
    def __init__(self):
        super().__init__(timeout=None) # Persistent view hoạt động vĩnh viễn
        self.add_item(AskActionSelect())

    @discord.ui.button(label="Chụp màn hình", style=discord.ButtonStyle.primary, emoji="📸", custom_id="btn_screen", row=1)
    async def btn_screen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_screen")

    @discord.ui.button(label="Thông số PC", style=discord.ButtonStyle.secondary, emoji="💻", custom_id="btn_pc", row=1)
    async def btn_pc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_pc")

    @discord.ui.button(label="Kiểm tra mạng", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="btn_net", row=1)
    async def btn_net(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_net")

    @discord.ui.button(label="Tiến độ AI", style=discord.ButtonStyle.success, emoji="🤖", custom_id="btn_status", row=1)
    async def btn_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_status")

    @discord.ui.button(label="Giải bài tập", style=discord.ButtonStyle.success, emoji="📚", custom_id="btn_solve", row=2)
    async def btn_solve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_solve")

    @discord.ui.button(label="Báo cáo vắng nhà", style=discord.ButtonStyle.primary, emoji="🏠", custom_id="btn_away", row=2)
    async def btn_away(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_away")

    @discord.ui.button(label="Hỏi đáp AI", style=discord.ButtonStyle.secondary, emoji="💬", custom_id="btn_ask_modal", row=2)
    async def btn_ask_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AskModal())

    @discord.ui.button(label="Khóa máy", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="btn_lock", row=2)
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "action_lock")

def create_ask_control_embed() -> discord.Embed:
    """Tạo Embed thông tin cho Trung tâm Điều khiển !ask."""
    embed = discord.Embed(
        title="📱 TRUNG TÂM ĐIỀU KHIỂN TỪ XA — MOBILE CONTROL HUB",
        description=(
            "👋 **Xin chào!** Bạn có thể điều khiển máy tính ngay từ điện thoại mà **không cần phải gõ lệnh `!`**.\n\n"
            "👉 **Chỉ việc click trên điện thoại:**\n"
            "• **Cách 1:** Chọn chức năng trong **ô lựa chọn xổ xuống (Dropdown)** bên dưới.\n"
            "• **Cách 2:** Bấm nhanh các **nút bấm trực quan (Buttons)** bên dưới.\n"
            "• **Cách 3:** Bấm nút **💬 Hỏi đáp AI** để mở ô nhập câu hỏi gửi Gemini 3.8 Flash / Argon High."
        ),
        color=0x57F287,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(
        name="⚡ Thao tác nhanh (1-Click)",
        value="📸 Chụp màn hình | 💻 Thông số PC | 🌐 Mạng | 🤖 Tiến độ AI | 📚 Giải bài tập | 🏠 Vắng nhà | 💬 Hỏi AI | 🔒 Khóa máy",
        inline=False
    )
    embed.add_field(
        name="🧠 Trí tuệ nhân tạo (AI Engine)",
        value="• Mô hình: **Gemini 3.8 Flash / Gemini 4 Argon**\n• Mức tư duy (Thinking Level): **HIGH (Tối đa suy luận)**\n• Báo lỗi tự động: **Thông báo 'Chưa kết nối' khi mất mạng/hết cookie**",
        inline=False
    )
    embed.set_footer(text="Gõ !ask bất cứ lúc nào để gọi lại menu này • AutoEdu & PC Remote Controller")
    return embed

# ==============================================================================
# 5. DISCORD BOT CLIENT & SỰ KIỆN CHÍNH (GATEWAY WEBSOCKET)
# ==============================================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@tasks.loop(seconds=3.0)
async def antigravity_watcher_task():
    """Tác vụ ngầm kiểm tra cập nhật Antigravity theo thời gian thực."""
    watcher = CONTROLLER_STATE.get("watcher")
    if watcher:
        try:
            await asyncio.to_thread(watcher.check_updates)
        except Exception as e:
            pass

@bot.event
async def on_ready():
    # Khởi tạo chọn transcript mới nhất
    latest_transcript = find_latest_transcript()
    if latest_transcript:
        conv_id = latest_transcript.parent.parent.parent.name
        CONTROLLER_STATE["selected_transcript"] = latest_transcript
        CONTROLLER_STATE["selected_conv_id"] = conv_id
        CONTROLLER_STATE["watcher"] = AntigravityWatcher(latest_transcript, start_at_end=True)

    # Đăng ký persistent view để các nút bấm hoạt động mãi mãi
    bot.add_view(AskControlView())

    if not antigravity_watcher_task.is_running():
        antigravity_watcher_task.start()

    print("==================================================================")
    print(f"🟢 DISCORD REMOTE CONTROLLER ĐÃ HOẠT ĐỘNG: {bot.user} (ID: {bot.user.id})")
    print(f"📌 Mục chat Antigravity mặc định: {CONTROLLER_STATE.get('selected_conv_id') or 'Chưa tìm thấy'}")
    print(f"📌 Single-Instance Mutex: Hoạt động (Loại bỏ 100% lặp tin nhắn)")
    print("==================================================================")

@bot.event
async def on_message(message: discord.Message):
    # Bỏ qua tin nhắn từ Bot hoặc Webhook
    if message.author.bot or message.webhook_id:
        return

    author_id = str(message.author.id)
    author_name = message.author.display_name
    allowed_ids = get_allowed_discord_user_ids()
    if allowed_ids and author_id not in allowed_ids:
        print(f"[⚠️ BẢO MẬT] Bỏ qua tin nhắn từ User không thuộc whitelist: {author_name} (ID: {author_id})")
        return

    content = message.content.strip()
    if not content:
        return

    content_lower = content.lower()
    print(f"[📥 Lệnh từ Discord ({author_name})]: {content}")

    # ==================== 1. LỆNH DUY NHẤT !ASK (HOẶC /ASK, !MENU, !HELP, ASK) ====================
    if content_lower in ("!ask", "/ask", "!menu", "!hub", "ask", "!help", "/help", "!lenh"):
        embed = create_ask_control_embed()
        view = AskControlView()
        await message.channel.send(embed=embed, view=view)
        return

    # ==================== 2. LỆNH !ASK CÓ NỘI DUNG (!ASK <CÂU HỎI>) ====================
    if content_lower.startswith("!ask ") or content_lower.startswith("/ask "):
        prompt_text = content[5:].strip()
        if not prompt_text:
            embed = create_ask_control_embed()
            view = AskControlView()
            await message.channel.send(embed=embed, view=view)
            return

        async with message.channel.typing():
            if HAS_GEMINI_WEB:
                ans = await asyncio.to_thread(query_gemini_web, prompt_text)
                embed = format_ai_embed(prompt_text, ans, author_name)
                await message.channel.send(embed=embed)
            else:
                await asyncio.to_thread(inject_prompt_to_antigravity, prompt_text)
                embed = discord.Embed(
                    title="🤖 ĐÃ GỬI LỆNH TỚI ANTIGRAVITY AGENT TRÊN PC",
                    description=f"👤 **Yêu cầu:** *{prompt_text}*\n\nAgent đang thực thi trên máy tính...",
                    color=0x5865F2,
                    timestamp=datetime.now(timezone.utc)
                )
                await message.channel.send(embed=embed)
        return

    # ==================== 3. TƯƠNG THÍCH NGƯỢC CÁC LỆNH CŨ ====================
    # Chụp màn hình
    if content_lower in ("!screen", "/screen", "!sc", "/sc", "chụp màn hình", "chup man hinh"):
        async with message.channel.typing():
            ok = await asyncio.to_thread(capture_desktop_screenshot, SCREENSHOT_TEMP)
            if ok and SCREENSHOT_TEMP.exists():
                file = discord.File(str(SCREENSHOT_TEMP), filename="screenshot.png")
                embed = discord.Embed(title="📸 ẢNH CHỤP MÀN HÌNH DESKTOP HIỆN TẠI", color=0x5865F2, timestamp=datetime.now(timezone.utc))
                embed.set_image(url="attachment://screenshot.png")
                await message.channel.send(embed=embed, file=file)
            else:
                await message.channel.send("⚠️ Không thể chụp ảnh màn hình hoặc màn hình đang bị khóa.")
        return

    # Thông số PC
    if content_lower in ("!pc", "/pc", "!sys", "/sys", "!info", "/info", "máy tính sao rồi", "kiem tra pc"):
        async with message.channel.typing():
            info = await asyncio.to_thread(get_system_info)
            embed = discord.Embed(title="💻 THÔNG SỐ & TRẠNG THÁI MÁY TÍNH HIỆN TẠI", color=0x5865F2, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="⚙️ CPU Usage", value=f"`{info.get('CPU')}`", inline=True)
            embed.add_field(name="🧠 Bộ nhớ RAM", value=f"`{info.get('RAM')}`", inline=True)
            embed.add_field(name="💾 Ổ đĩa C:", value=f"`{info.get('DiskC')}`", inline=True)
            embed.add_field(name="⏱️ Thời gian hoạt động", value=f"`{info.get('Uptime')}`", inline=True)
            embed.add_field(name="👤 Người dùng", value=f"`{info.get('User')}@{info.get('Computer')}`", inline=True)
            bat = await asyncio.to_thread(get_battery_info)
            embed.add_field(name="🔋 Nguồn / Pin", value=f"`{bat}`", inline=True)
            await message.channel.send(embed=embed)
        return

    # Kiểm tra mạng
    if content_lower in ("!net", "/net", "!ping", "/ping", "!wifi", "/wifi", "!ethernet", "/ethernet", "mạng thế nào"):
        async with message.channel.typing():
            net = await asyncio.to_thread(get_network_info)
            embed = discord.Embed(title="🌐 KẾT QUẢ KIỂM TRA MẠNG & INTERNET", color=0x57F287 if "BÌNH THƯỜNG" in net.get('Internet', '') else 0xED4245, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="📡 Trạng thái Internet", value=f"**{net.get('Internet')}**", inline=False)
            embed.add_field(name="🔍 Ping Google", value=f"`{net.get('PingGoogle')}`", inline=True)
            embed.add_field(name="🔍 Ping Cloudflare", value=f"`{net.get('PingCloudflare')}`", inline=True)
            embed.add_field(name="🏠 IP LAN", value=f"`{net.get('LocalIP')}`", inline=True)
            await message.channel.send(embed=embed)
        return

    # Trạng thái AI
    if content_lower in ("!status", "/status", "!agent", "/agent", "!tiendo", "xong chưa", "agent đang làm gì"):
        async with message.channel.typing():
            st = await asyncio.to_thread(get_deep_agent_status)
            embed = discord.Embed(title="🤖 BÁO CÁO TIẾN ĐỘ ANTIGRAVITY AI AGENT", color=st["color"], timestamp=datetime.now(timezone.utc))
            embed.add_field(name="📊 Trạng thái Agent", value=f"**{st['status_label']}**", inline=False)
            embed.add_field(name="⚡ Hành động đang/vừa làm", value=f"`{st['last_action'][:250]}`", inline=False)
            embed.add_field(name="🎯 Mục tiêu gần nhất", value=f"*{st['last_user_goal'][:250]}*", inline=False)
            embed.add_field(name="📈 Tiến độ", value=f"`{st['total_steps']} bước` (lần cuối: `{st['elapsed_str']}`)", inline=True)
            if st.get("last_answer"):
                embed.add_field(name="💬 Phản hồi", value=f"{st['last_answer'][:500]}", inline=False)
            await message.channel.send(embed=embed)
        return

    # Báo cáo vắng nhà (Away mode)
    if content_lower in ("!away", "/away", "!check", "ở nhà thế nào", "tình hình ở nhà"):
        async with message.channel.typing():
            info = await asyncio.to_thread(get_system_info)
            net = await asyncio.to_thread(get_network_info)
            st = await asyncio.to_thread(get_deep_agent_status)
            ok_screen = await asyncio.to_thread(capture_desktop_screenshot, SCREENSHOT_TEMP)

            embed = discord.Embed(title="🏠 BÁO CÁO TOÀN DIỆN MÁY TÍNH KHI VẮNG NHÀ", color=0x5865F2, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="🤖 AI Agent", value=f"**{st['status_label']}**\n{st['last_action'][:150]}", inline=False)
            embed.add_field(name="💻 Thông số PC", value=f"CPU: `{info.get('CPU')}` | RAM: `{info.get('RAM')}` | C: `{info.get('DiskC')}`", inline=False)
            embed.add_field(name="🌐 Mạng Internet", value=f"{net.get('Internet')}\nPing: `{net.get('PingGoogle')}`", inline=False)

            if ok_screen and SCREENSHOT_TEMP.exists():
                file = discord.File(str(SCREENSHOT_TEMP), filename="away_screen.png")
                embed.set_image(url="attachment://away_screen.png")
                await message.channel.send(embed=embed, file=file)
            else:
                await message.channel.send(embed=embed)
        return

    # Giải bài tập Onluyen
    if content_lower in ("!solve", "/solve", "giải bài tập", "làm bài tập"):
        def _run_solver():
            script_path = BASE_DIR / "auto_nightly_worker.py"
            pyw_exe = str(Path(sys.executable).parent / "pythonw.exe")
            if not os.path.exists(pyw_exe):
                pyw_exe = sys.executable
            subprocess.run([pyw_exe, str(script_path), "--once"])
        threading.Thread(target=_run_solver, daemon=True).start()
        await message.channel.send("📚 **AutoEdu Onluyen Solver:** Đang quét và giải bài tập tự động bằng Gemini 3.8 Flash! Kết quả sẽ được nộp và gửi về Discord ngay.")
        return

    # Khóa màn hình
    if content_lower in ("!lock", "/lock", "khóa máy", "khoa man hinh"):
        await asyncio.to_thread(lock_screen)
        await message.channel.send("🔒 Đã khóa màn hình máy tính (Lock Workstation) thành công.")
        return

    # Chế độ ngủ
    if content_lower in ("!sleep", "/sleep", "ngủ đi"):
        await message.channel.send("💤 Máy tính sẽ vào chế độ Sleep sau 2 giây nữa...")
        await asyncio.sleep(2)
        await asyncio.to_thread(sleep_pc)
        return

    # Điều chỉnh âm lượng
    if content_lower.startswith("!vol "):
        action = content_lower.split(" ", 1)[1].strip()
        res = await asyncio.to_thread(control_volume, action)
        await message.channel.send(res)
        return

    # Google Drive Quota
    if content_lower in ("!gdrive", "/gdrive"):
        quota = await asyncio.to_thread(get_gdrive_quota_info)
        await message.channel.send(quota)
        return

    # Nhập câu hỏi Gemini trực tiếp
    if content_lower.startswith("!gemini ") or content_lower.startswith("!ai "):
        q = content.split(" ", 1)[1].strip()
        async with message.channel.typing():
            ans = await asyncio.to_thread(query_gemini_web, q)
            embed = format_ai_embed(q, ans, author_name)
            await message.channel.send(embed=embed)
        return

    # Nếu người dùng nhắn tin tự nhiên mà không có tiền tố !, trả lời qua Gemini Web AI hoặc gợi ý !ask
    if not content.startswith("!") and not content.startswith("/"):
        if HAS_GEMINI_WEB:
            async with message.channel.typing():
                ans = await asyncio.to_thread(query_gemini_web, content)
                embed = format_ai_embed(content, ans, author_name)
                embed.set_footer(text=f"💡 Gõ !ask để mở Menu điều khiển bằng 1-Click • Mức tư duy: High")
                await message.channel.send(embed=embed)
        else:
            embed = create_ask_control_embed()
            view = AskControlView()
            await message.channel.send(embed=embed, view=view)

# ==============================================================================
# 6. KHỞI ĐỘNG TIẾN TRÌNH BOT
# ==============================================================================

def main():
    # 1. Chiếm giữ Mutex độc quyền (ngăn chặn 100% việc lặp tin nhắn)
    if not acquire_single_instance_lock():
        print("[!] Thoát tiến trình vì đã có Bot đang chạy độc quyền.")
        return

    _, bot_token, _ = load_env_discord()
    if not bot_token:
        print("[!] Không tìm thấy DISCORD_BOT_TOKEN trong .env!")
        return

    print("🚀 Đang khởi động Discord Remote Controller Gateway...")
    try:
        bot.run(bot_token)
    except KeyboardInterrupt:
        print("\n[!] Dừng bởi người dùng.")
    except Exception as e:
        print(f"[!] Lỗi kết nối Discord: {e}")

if __name__ == "__main__":
    main()
