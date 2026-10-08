# -*- coding: utf-8 -*-
"""
Telegram Bot Tuong Tac 2 Chieu:
- Ban thong bao tien do Antigravity
- Cho phep ban dung dien thoai nhan tin /status, /scan, /homework de kiem tra tu xa!
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from telegram_notifier import load_env_telegram, send_telegram_message, send_telegram_photo

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CONV_ID = "5b530879-fc44-450d-a4c2-d13b720bc31c"
TRANSCRIPT_PATH = os.path.expanduser(
    rf"~/.gemini/antigravity/brain/{CONV_ID}/.system_generated/logs/transcript.jsonl"
)
PROJECT_DIR = r"C:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"
LOG_FILE = os.path.join(PROJECT_DIR, "logs", "nightly_solver.log")

def get_antigravity_status_summary():
    """Lay trang thai tong quan de tra loi tin nhan Telegram."""
    status = "IDLE"
    last_action = "Chờ lệnh mới"
    total_steps = 0
    recent_tools = []
    
    if os.path.exists(TRANSCRIPT_PATH):
        try:
            with open(TRANSCRIPT_PATH, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                total_steps = len(lines)
                if lines:
                    last_obj = json.loads(lines[-1].strip())
                    if last_obj.get("type") == "PLANNER_RESPONSE":
                        tc = last_obj.get("tool_calls", [])
                        if tc:
                            status = "WORKING ⚡"
                            name = tc[0].get("name", "")
                            desc = tc[0].get("args", {}).get("toolSummary", name).strip('"')
                            last_action = f"{name}: {desc}"
                        else:
                            status = "IDLE 💤"
                            last_action = "Hoàn tất phản hồi"
                    elif last_obj.get("type") == "USER_INPUT":
                        status = "THINKING 💭"
                        last_action = "Đang xử lý yêu cầu..."

                for l in lines[-10:]:
                    try:
                        o = json.loads(l.strip())
                        for t in o.get("tool_calls", []):
                            n = t.get("name", "")
                            d = t.get("args", {}).get("toolSummary", n).strip('"')
                            recent_tools.append(f"• <code>{n}</code>: {d}")
                    except Exception:
                        pass
        except Exception as e:
            last_action = str(e)

    recent_str = "\n".join(recent_tools[-4:]) if recent_tools else "Chưa có hành động mới"
    now_str = datetime.now().strftime("%H:%M:%S %d/%m")

    msg = (
        f"🤖 <b>BÁO CÁO TIẾN ĐỘ ANTIGRAVITY</b> ({now_str})\n\n"
        f"📍 <b>Trạng thái:</b> {status}\n"
        f"🎯 <b>Đang làm:</b> {last_action}\n"
        f"🔢 <b>Tổng số bước:</b> {total_steps}\n\n"
        f"⚡ <b>Hành động gần nhất:</b>\n{recent_str}\n\n"
        f"<i>Gõ /homework để xem kết quả bài tập đêm!</i>"
    )
    return msg

def get_homework_summary():
    """Lay nhat ky lam bai tap dem tren Onluyen."""
    if not os.path.exists(LOG_FILE):
        return "📁 Chưa có file log bài tập đêm."
    
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        last_logs = "\n".join(lines[-6:]) if lines else "Chưa có log."
        return f"🌙 <b>NHẬT KÝ BÀI TẬP VỀ NHÀ GẦN NHẤT:</b>\n\n<pre>{last_logs}</pre>"
    except Exception as e:
        return f"Lỗi đọc log: {e}"

def poll_telegram_bot():
    """Vong lap lang nghe tin nhan tu dien thoai."""
    bot_token, authorized_chat_id = load_env_telegram()
    if not bot_token or not authorized_chat_id:
        print("[!] Vui lòng cấu hình TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID trong .env")
        return

    print("=" * 60)
    print("🤖 TELEGRAM BOT CONTROLLER ĐANG CHẠY...")
    print(f"👉 Hãy mở app Telegram trên điện thoại và gửi: /status hoặc /help")
    print("=" * 60)

    last_update_id = 0
    base_url = f"https://api.telegram.org/bot{bot_token}"

    while True:
        try:
            url = f"{base_url}/getUpdates?offset={last_update_id + 1}&timeout=30"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                for update in data.get("result", []):
                    last_update_id = update.get("update_id", last_update_id)
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip().lower()

                    # Chi tra loi dung chat_id cua chu nhan
                    if chat_id != str(authorized_chat_id):
                        continue

                    if text.startswith("/status") or text == "status":
                        reply = get_antigravity_status_summary()
                        send_telegram_message(reply)
                    elif text.startswith("/homework") or text == "homework" or text == "bai tap":
                        reply = get_homework_summary()
                        send_telegram_message(reply)
                    elif text.startswith("/help") or text == "help":
                        help_msg = (
                            "👋 <b>DANH SÁCH LỆNH ĐIỀU KHIỂN:</b>\n\n"
                            "/status - Xem tiến độ Antigravity đang làm gì\n"
                            "/homework - Xem kết quả làm bài tập Onluyen\n"
                            "/help - Xem danh sách lệnh trợ giúp"
                        )
                        send_telegram_message(help_msg)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    poll_telegram_bot()
