# -*- coding: utf-8 -*-
"""
Module gui thong bao tien do qua Telegram Bot.
Su dung thu vien goc cua Python (khong can pip install).
"""
import os
import sys
import json
import mimetypes
import urllib.request
import urllib.parse
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def load_env_telegram():
    """Doc BOT_TOKEN va CHAT_ID tu file .env hoac bien moi truong."""
    env_path = Path(__file__).resolve().parent / ".env"
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if (not bot_token or not chat_id) and env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "TELEGRAM_BOT_TOKEN" and not bot_token:
                        bot_token = v
                    elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                        chat_id = v

    return bot_token, chat_id

def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Gui tin nhan van ban den Telegram."""
    bot_token, chat_id = load_env_telegram()
    if not bot_token or not chat_id:
        print("[!] Chua cau hinh TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID trong .env")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data.get("ok", False)
    except Exception as e:
        print(f"[!] Loi gui tin nhan Telegram: {e}")
        return False

def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """Gui anh (screenshot bang diem, ket qua) den Telegram bang multipart/form-data."""
    bot_token, chat_id = load_env_telegram()
    if not bot_token or not chat_id:
        print("[!] Chua cau hinh TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID trong .env")
        return False

    if not os.path.exists(photo_path):
        print(f"[!] Khong tim thay file anh: {photo_path}")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    with open(photo_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(photo_path)
    mime_type = mimetypes.guess_type(filename)[0] or "image/png"

    # Xay dung multipart body
    body = bytearray()
    
    # Field chat_id
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))

    # Field caption
    if caption:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n')

    # Field photo
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(b"\r\n")

    # End boundary
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    try:
        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body))
            }
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data.get("ok", False)
    except Exception as e:
        print(f"[!] Loi gui anh Telegram: {e}")
        return False

def test_telegram_connection() -> bool:
    """Gui tin nhan kiem tra ket noi den dien thoai."""
    msg = (
        "<b>🎉 KẾT NỐI THÀNH CÔNG!</b>\n\n"
        "🤖 <i>Antigravity AI Agent & AutoEdu Homework Solver</i>\n"
        "Đã kết nối thành công với tài khoản Telegram của bạn.\n"
        "Từ bây giờ, mọi tiến trình và kết quả làm bài tập đêm sẽ được gửi trực tiếp về đây!"
    )
    return send_telegram_message(msg)

if __name__ == "__main__":
    bot_token, chat_id = load_env_telegram()
    print("==================================================")
    print("📱 KIỂM TRA CẤU HÌNH TELEGRAM BOT")
    print("==================================================")
    print(f"Token:   {bot_token[:10]}...{bot_token[-4:] if bot_token else 'CHƯA CÓ'}")
    print(f"Chat ID: {chat_id if chat_id else 'CHƯA CÓ'}")
    
    if not bot_token or not chat_id:
        print("\n👉 Bạn cần điền TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID vào file .env")
    else:
        print("\nĐang gửi tin nhắn thử nghiệm...")
        ok = test_telegram_connection()
        if ok:
            print("[✓] Tin nhắn đã được gửi tới điện thoại của bạn!")
        else:
            print("[X] Gửi tin nhắn thất bại. Vui lòng kiểm tra lại Token hoặc Chat ID.")
