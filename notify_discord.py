# -*- coding: utf-8 -*-
"""
Script CLI tien ich de ban gui bat ky thong bao nao den Discord.
Vi du: uv run python notify_discord.py -m "Antigravity da xong viec!"
"""
import sys
import argparse
from discord_notifier import send_discord_message, send_discord_photo

def main():
    parser = argparse.ArgumentParser(description="Gui thong bao nhanh toi Discord")
    parser.add_argument("-m", "--message", type=str, help="Noi dung tin nhan")
    parser.add_argument("-t", "--title", type=str, default="🔔 Thông báo từ Antigravity", help="Tieu de embed")
    parser.add_argument("-p", "--photo", type=str, default=None, help="Duong dan anh gui kem")
    args = parser.parse_args()

    if not args.message and not args.photo:
        print("Vui long nhap it nhat mot noi dung (-m) hoac anh (-p)")
        sys.exit(1)

    if args.photo:
        ok = send_discord_photo(args.photo, title=args.title, description=args.message or "")
    else:
        embed = [{
            "title": args.title,
            "description": args.message,
            "color": 0x5865F2,
            "footer": {"text": "Antigravity Assistant"}
        }]
        ok = send_discord_message(embeds=embed)

    if ok:
        print("[✓] Da gui thong bao toi Discord thanh cong!")
    else:
        print("[X] Gui thong bao that bai.")

if __name__ == "__main__":
    main()
