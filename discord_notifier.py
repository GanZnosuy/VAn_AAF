# -*- coding: utf-8 -*-
"""
Module gui thong bao tien do qua Discord (Webhook hoac Bot).
Su dung thu vien goc cua Python (khong can cai discord.py hay requests).
"""
import os
import sys
import json
import mimetypes
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def load_env_discord():
    """Doc DISCORD_WEBHOOK_URL hoac BOT_TOKEN tu file .env."""
    env_path = Path(__file__).resolve().parent / ".env"
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    channel_id = os.getenv("DISCORD_CHANNEL_ID", "").strip()

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "DISCORD_WEBHOOK_URL" and not webhook_url:
                        webhook_url = v
                    elif k == "DISCORD_BOT_TOKEN" and not bot_token:
                        bot_token = v
                    elif k == "DISCORD_CHANNEL_ID" and not channel_id:
                        channel_id = v

    return webhook_url, bot_token, channel_id

def send_discord_message(content: str = "", embeds: list = None) -> bool:
    """Gui tin nhan den Discord qua Webhook."""
    webhook_url, _, _ = load_env_discord()
    if not webhook_url:
        print("[!] Chua cau hinh DISCORD_WEBHOOK_URL trong .env")
        return False

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AntigravityDiscordNotifier/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[!] Loi gui tin nhan Discord: {e}")
        return False

def send_discord_photo(photo_path: str, title: str = "", description: str = "", color: int = 0x5865F2) -> bool:
    """Gui anh (screenshot bang diem Onluyen) kem Embed dep mat den Discord qua Webhook."""
    webhook_url, _, _ = load_env_discord()
    if not webhook_url:
        print("[!] Chua cau hinh DISCORD_WEBHOOK_URL trong .env")
        return False

    if not os.path.exists(photo_path):
        print(f"[!] Khong tim thay file anh: {photo_path}")
        return False

    filename = os.path.basename(photo_path)
    mime_type = mimetypes.guess_type(filename)[0] or "image/png"

    with open(photo_path, "rb") as f:
        file_bytes = f.read()

    boundary = "----WebKitFormBoundaryDiscordUpload7MA4"

    # Embed card kèm ảnh attachment
    embed_payload = {
        "title": title or "📸 Kết quả làm bài tập",
        "description": description or f"Ảnh chụp màn hình: `{filename}`",
        "color": color,
        "image": {"url": f"attachment://{filename}"},
        "footer": {"text": "Antigravity AI • AutoEdu Solver"},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    payload_json = {
        "embeds": [embed_payload]
    }

    body = bytearray()
    
    # 1. payload_json
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="payload_json"\r\n')
    body.extend(b'Content-Type: application/json\r\n\r\n')
    body.extend(json.dumps(payload_json).encode("utf-8"))
    body.extend(b"\r\n")

    # 2. File attachment
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(b"\r\n")

    # End
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    try:
        req = urllib.request.Request(
            webhook_url,
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
                "User-Agent": "AntigravityDiscordNotifier/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[!] Loi gui anh Discord: {e}")
        return False

def test_discord_connection() -> bool:
    """Gui tin nhan test kiem tra ket noi den Discord channel."""
    embed = [{
        "title": "🎉 KẾT NỐI DISCORD THÀNH CÔNG!",
        "description": "🤖 **Antigravity AI Agent & AutoEdu Solver**\nĐã liên kết thành công với kênh Discord này của bạn.\n\nTừ bây giờ, mọi thông báo tiến trình và bảng điểm bài tập đêm sẽ được gửi tự động về đây!",
        "color": 0x57F287, # Green
        "fields": [
            {"name": "⏰ Lịch quét bài đêm", "value": "22:00 hàng ngày", "inline": True},
            {"name": "📱 Thiết bị nhận tin", "value": "Discord App (Mobile / PC)", "inline": True}
        ],
        "footer": {"text": "Antigravity Assistant"},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }]
    return send_discord_message(content="🔔 **Thông báo kết nối:**", embeds=embed)

if __name__ == "__main__":
    webhook_url, bot_token, _ = load_env_discord()
    print("==================================================")
    print("🎮 KIỂM TRA CẤU HÌNH DISCORD NOTIFIER")
    print("==================================================")
    if webhook_url:
        masked = webhook_url[:35] + "..." + webhook_url[-10:]
        print(f"Webhook URL: {masked}")
        print("\nĐang gửi tin nhắn thử nghiệm tới Discord...")
        if test_discord_connection():
            print("[✓] Gửi thành công! Hãy kiểm tra Discord trên điện thoại của bạn.")
        else:
            print("[X] Gửi thất bại. Vui lòng kiểm tra lại URL Webhook.")
    else:
        print("[!] Chưa tìm thấy DISCORD_WEBHOOK_URL trong file .env")
        print("👉 Vui lòng thêm DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... vào .env")
