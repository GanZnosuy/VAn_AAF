# -*- coding: utf-8 -*-
"""
Script CLI tien ich de ban gui bat ky thong bao nao den Discord.
Ho tro:
1. Thong bao nhanh:
   python notify_discord.py -m "Tin nhan nhanh"
2. Thong bao hoan thanh cong viec:
   python notify_discord.py --status completed -t "Giai de Toan" -m "Da giai xong 10 cau" -d "Cau 1-5 dung" "Cau 6-10 dung"
3. Thong bao ngat ket noi / gian doan:
   python notify_discord.py --status interrupted -t "Quet bai dem" -r "Mat ket noi mang" -e "Timeout 30s"
"""
import sys
import argparse
from discord_notifier import (
    send_discord_message,
    send_discord_photo,
    notify_task_completed,
    notify_interrupted_or_disconnected
)

def main():
    parser = argparse.ArgumentParser(description="Gui thong bao tien do & canh bao toi Discord")
    parser.add_argument("-t", "--title", type=str, default="Thông báo từ Antigravity", help="Tieu de thong bao")
    parser.add_argument("-m", "--message", type=str, default="", help="Noi dung tin nhan mo ta")
    parser.add_argument("-s", "--status", choices=["info", "completed", "interrupted"], default="info", help="Trang thai: info | completed | interrupted")
    parser.add_argument("-r", "--reason", type=str, default="Mất kết nối hoặc tiến trình bị gián đoạn", help="Ly do gián đoạn (neu status=interrupted)")
    parser.add_argument("-e", "--error", type=str, default="", help="Chi tiet loi ky thuat (neu status=interrupted)")
    parser.add_argument("-d", "--details", nargs="*", default=None, help="Danh sach cong viec chi tiet (neu status=completed)")
    parser.add_argument("-f", "--files", nargs="*", default=None, help="Danh sach file da xu ly")
    parser.add_argument("-p", "--photo", type=str, default=None, help="Duong dan anh gui kem")
    args = parser.parse_args()

    if args.status == "completed":
        ok = notify_task_completed(
            task_title=args.title,
            task_description=args.message,
            details=args.details,
            files_affected=args.files,
            photo_path=args.photo
        )
    elif args.status == "interrupted":
        ok = notify_interrupted_or_disconnected(
            task_name=args.title,
            reason=args.reason,
            last_action=args.message or "Đang chạy tiến trình",
            error_message=args.error,
            photo_path=args.photo
        )
    else:
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
