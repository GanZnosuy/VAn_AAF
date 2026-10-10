# -*- coding: utf-8 -*-
"""
Module gui thong bao tien do va canh bao qua Discord (Webhook hoac Bot).
Ho tro:
1. Thong bao hoan thanh cong viec (kem noi dung chi tiet, tep tin, hinh anh).
2. Canh bao ngat ket noi giua chung, loi mang, crash hoac gian doan tien trinh.
3. Gui tin nhan embed va anh chup man hinh ket qua.
Khong can cai bat ky thu vien ngoai nao (Pure Python standard library).
"""
import os
import sys
import json
import mimetypes
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def get_iso_timestamp() -> str:
    """Tra ve chuoi thoi gian ISO 8601 chuan UTC cho Discord embed."""
    try:
        return datetime.now(timezone.utc).isoformat()
    except Exception:
        return datetime.utcnow().isoformat() + "Z"

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
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AntigravityDiscordNotifier/2.0"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[!] Loi gui tin nhan Discord: {e}")
        return False

def send_discord_photo(photo_path: str, title: str = "", description: str = "", color: int = 0x5865F2, fields: list = None) -> bool:
    """Gui anh (screenshot) kem Embed day du thong tin den Discord qua Webhook."""
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

    embed_payload = {
        "title": title or "📸 Kết quả thực hiện",
        "description": description or f"Ảnh đính kèm: `{filename}`",
        "color": color,
        "image": {"url": f"attachment://{filename}"},
        "footer": {"text": "Antigravity Assistant • AutoEdu"},
        "timestamp": get_iso_timestamp()
    }
    if fields:
        embed_payload["fields"] = fields

    payload_json = {
        "embeds": [embed_payload]
    }

    body = bytearray()
    # 1. payload_json
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="payload_json"\r\n')
    body.extend(b'Content-Type: application/json; charset=utf-8\r\n\r\n')
    body.extend(json.dumps(payload_json, ensure_ascii=False).encode("utf-8"))
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
                "User-Agent": "AntigravityDiscordNotifier/2.0"
            }
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[!] Loi gui anh Discord: {e}")
        return False

def notify_task_completed(
    task_title: str,
    task_description: str = "",
    details: list = None,
    files_affected: list = None,
    photo_path: str = None,
    color: int = 0x57F287  # Discord Green
) -> bool:
    """
    Thong bao khi mot cong viec hoan thanh thanh cong.
    Hien thi ro: Noi dung cong viec da xong, danh sach viec chi tiet, thoi gian, tep tin.
    """
    now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    embed_fields = [
        {"name": "⏰ Thời gian hoàn tất", "value": f"`{now_str}`", "inline": True},
        {"name": "📊 Trạng thái", "value": "✅ **Thành công (Completed)**", "inline": True}
    ]

    if details:
        # Gioi han moi item de tranh tran Discord limit
        detail_text = "\n".join([f"• {str(d)[:150]}" for d in details[:10]])
        if len(details) > 10:
            detail_text += f"\n*... và {len(details) - 10} nội dung khác*"
        embed_fields.append({
            "name": "📝 Nội dung các công việc đã thực hiện:",
            "value": detail_text[:1024],
            "inline": False
        })

    if files_affected:
        files_text = "\n".join([f"📁 `{f}`" for f in files_affected[:8]])
        embed_fields.append({
            "name": "📦 Tệp tin liên quan / Đã xử lý:",
            "value": files_text[:1024],
            "inline": False
        })

    full_title = f"🎉 HOÀN THÀNH: {task_title}"
    desc = task_description or "Công việc đã được xử lý trọn vẹn và hoàn tất thành công."

    if photo_path and os.path.exists(photo_path):
        return send_discord_photo(
            photo_path=photo_path,
            title=full_title,
            description=desc,
            color=color,
            fields=embed_fields
        )

    embed = [{
        "title": full_title,
        "description": desc,
        "color": color,
        "fields": embed_fields,
        "footer": {"text": "Antigravity Assistant • Task Manager"},
        "timestamp": get_iso_timestamp()
    }]
    return send_discord_message(content="🔔 **Thông báo hoàn thành công việc:**", embeds=embed)

def notify_interrupted_or_disconnected(
    task_name: str,
    reason: str,
    last_action: str = "",
    error_message: str = "",
    recovery_hint: str = "",
    photo_path: str = None,
    color: int = 0xED4245  # Discord Red
) -> bool:
    """
    Canh bao khan cap khi tien trinh bi ngat ket noi giua chung, mat mang, hoac loi dot ngot.
    """
    now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    embed_fields = [
        {"name": "⏰ Thời điểm phát hiện", "value": f"`{now_str}`", "inline": True},
        {"name": "⚠️ Phân loại", "value": "🚨 **Ngắt kết nối / Gián đoạn**", "inline": True},
        {"name": "🛑 Nguyên nhân gián đoạn:", "value": f"**{reason}**", "inline": False}
    ]

    if last_action:
        embed_fields.append({
            "name": "📍 Vị trí / Bước đang làm dở:",
            "value": f"`{last_action[:500]}`",
            "inline": False
        })

    if error_message:
        # Cat gon loi de tranh vuot qua 1024 ky tu
        err_clean = str(error_message).strip()
        if len(err_clean) > 500:
            err_clean = err_clean[:500] + "... [Cắt gọn]"
        embed_fields.append({
            "name": "🔍 Chi tiết lỗi / Trích xuất lỗi mạng:",
            "value": f"```\n{err_clean}\n```",
            "inline": False
        })

    hint = recovery_hint or "Kiểm tra lại kết nối mạng Internet của máy chủ hoặc chạy lại lệnh từ điện thoại/máy tính."
    embed_fields.append({
        "name": "💡 Hướng xử lý đề xuất:",
        "value": f"_{hint}_",
        "inline": False
    })

    full_title = f"⚠️ CẢNH BÁO GIÁN ĐOẠN: {task_name}"
    desc = f"Tiến trình **{task_name}** vừa bị dừng đột ngột hoặc mất kết nối giữa chừng!\nVui lòng kiểm tra lại trạng thái."

    if photo_path and os.path.exists(photo_path):
        return send_discord_photo(
            photo_path=photo_path,
            title=full_title,
            description=desc,
            color=color,
            fields=embed_fields
        )

    embed = [{
        "title": full_title,
        "description": desc,
        "color": color,
        "fields": embed_fields,
        "footer": {"text": "Antigravity Assistant • Alert Monitor"},
        "timestamp": get_iso_timestamp()
    }]
    return send_discord_message(content="🚨 **CẢNH BÁO: PHÁT HIỆN SỰ CỐ GIÁN ĐOẠN TIẾN TRÌNH!**", embeds=embed)

def test_discord_connection() -> bool:
    """Gui tin nhan test kiem tra ket noi den Discord channel."""
    embed = [{
        "title": "🎉 KẾT NỐI DISCORD THÀNH CÔNG!",
        "description": "🤖 **Antigravity AI Agent & AutoEdu Solver**\nĐã liên kết thành công với kênh Discord này của bạn.\n\nTừ bây giờ, bot sẽ tự động thông báo:\n• ✅ **Chi tiết nội dung công việc vừa hoàn tất**\n• 🚨 **Cảnh báo mất kết nối / gián đoạn giữa chừng ngay tức thì!**",
        "color": 0x57F287,
        "fields": [
            {"name": "⏰ Lịch quét bài đêm", "value": "22:00 hàng ngày", "inline": True},
            {"name": "📱 Thiết bị nhận tin", "value": "Discord App (Mobile / PC)", "inline": True}
        ],
        "footer": {"text": "Antigravity Assistant"},
        "timestamp": get_iso_timestamp()
    }]
    return send_discord_message(content="🔔 **Thông báo kết nối Discord Notifier v2.0:**", embeds=embed)

if __name__ == "__main__":
    webhook_url, bot_token, _ = load_env_discord()
    print("==================================================")
    print("🎮 KIỂM TRA CẤU HÌNH DISCORD NOTIFIER V2.0")
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
