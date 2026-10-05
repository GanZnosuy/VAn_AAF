import argparse
import asyncio
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.browser.context import launch_browser_context
from autoedu.browser.navigator import scan_assignments
from autoedu.solver.runner import solve_test_url
from autoedu.trial import TrialManager
from autoedu.config import ACTIVE_GEMINI_COOKIES, GEMINI_API_KEY

trial_manager = TrialManager()

async def cmd_test_ai(args):
    """Kiểm tra kết nối và trích xuất token Gemini AI."""
    print("🤖 Đang kiểm tra kết nối tới Gemini AI Engine...")
    client = GeminiWebClient()
    test_prompt = "Chào bạn! Hãy giải phép tính: 2 + 3 bằng mấy? Kết luận ngắn gọn: ĐÁP ÁN: 5"
    resp = await client.query(test_prompt)
    if resp:
        print(f"[✓] Kết nối thành công!")
        print(f"    Phản hồi từ AI: {resp}")
    else:
        print("[!] Không có cookies hoặc cookies đã hết hạn.")
        if trial_manager.is_trial_available():
            print("🎁 Bạn vẫn có thể dùng thử 1 lần duy nhất bằng lệnh: python cli.py trial --url <URL>")
        else:
            print("👉 Vui lòng cập nhật lại cookie trong file .env để tiếp tục.")

async def cmd_status(args):
    """Hiển thị trạng thái cấu hình và hạn mức Dùng Thử (Free Trial)."""
    data = trial_manager.load_data()
    agent = trial_manager.detect_agent()
    print("=" * 65)
    print("📊 TRẠNG THÁI HỆ THỐNG AUTOEDU-AGENT")
    print("=" * 65)
    print(f"🤖 AI Coding Agent phát hiện: {agent}")
    print(f"🍪 Cookie Gemini Web:        {'Đã cấu hình' if ACTIVE_GEMINI_COOKIES else 'Chưa cấu hình (.env rỗng)'}")
    print(f"🔑 Gemini API Key:           {'Đã cấu hình' if GEMINI_API_KEY else 'Không có'}")
    print("-" * 65)
    print(f"🎁 Lượt dùng thử (Trial):    {'CÒN 1 LƯỢT (Miễn phí)' if trial_manager.is_trial_available() else 'ĐÃ SỬ DỤNG'}")
    if data.get("trial_used"):
        print(f"   - Thời điểm dùng:        {data.get('first_used_at')}")
        print(f"   - Bài thi đã giải:       {data.get('last_test_url')}")
    print("=" * 65)

async def cmd_scan(args):
    """Quét các bài tập cần làm trên Onluyen."""
    print("🔍 Đang quét danh sách bài tập...")
    async with async_playwright() as p:
        context = await launch_browser_context(p, headless=args.headless)
        page = context.pages[0] if context.pages else await context.new_page()
        items = await scan_assignments(page)
        print(f"\n📋 Tìm thấy {len(items)} bài tập cần làm:")
        for idx, it in enumerate(items):
            print(f"  [{idx+1}] Môn: {it.get('subject', 'Chung')} | {it.get('text', '')}")
        await context.close()

async def cmd_trial(args):
    """Chạy chế độ DÙNG THỬ MIỄN PHÍ 1 LẦN DUY NHẤT dành cho AI Agent & người dùng mới."""
    if not trial_manager.is_trial_available():
        trial_manager.print_trial_exhausted()
        return

    trial_manager.print_trial_banner()
    print(f"\n▶️ Bắt đầu bài thi dùng thử: {args.url}")

    async with async_playwright() as p:
        context = await launch_browser_context(p, headless=args.headless)
        page = context.pages[0] if context.pages else await context.new_page()
        success = await solve_test_url(page, args.url, screenshot_name=args.output)
        await asyncio.sleep(2)
        await context.close()

    if success:
        trial_manager.record_trial(args.url)
        trial_manager.print_trial_success()
    else:
        print("\n[!] Bài thi chưa hoàn thành trọn vẹn. Lượt dùng thử vẫn được bảo lưu.")

async def cmd_solve(args):
    """Tự động giải một bài kiểm tra theo URL."""
    # Kiểm tra nếu chưa cấu hình cookies và chưa có API key
    if not ACTIVE_GEMINI_COOKIES and not GEMINI_API_KEY:
        if args.trial or trial_manager.is_trial_available():
            print("[*] Phát hiện chưa cấu hình .env -> Tự động chuyển sang Chế độ Dùng Thử 1 Lần...")
            await cmd_trial(args)
            return
        else:
            trial_manager.print_trial_exhausted()
            return

    async with async_playwright() as p:
        context = await launch_browser_context(p, headless=args.headless)
        page = context.pages[0] if context.pages else await context.new_page()
        success = await solve_test_url(page, args.url, screenshot_name=args.output)
        if success:
            print("\n🏆 Hoàn thành bài thi và nộp bài thành công!")
        else:
            print("\n[!] Không thể hoàn tất bài thi.")
        await asyncio.sleep(3)
        await context.close()

def main():
    parser = argparse.ArgumentParser(description="AutoEdu - Hệ thống tự động giải bài tập và bài thi trực tuyến")
    subparsers = parser.add_subparsers(dest="command", help="Lệnh thực hiện")

    # test-ai
    subparsers.add_parser("test-ai", help="Kiểm tra kết nối Gemini AI")

    # status
    subparsers.add_parser("status", help="Xem trạng thái cấu hình và lượt dùng thử (Free Trial)")

    # scan
    p_scan = subparsers.add_parser("scan", help="Quét bài tập trên Onluyen")
    p_scan.add_argument("--headless", action="store_true", help="Chạy ở chế độ ẩn danh")

    # trial (Lệnh dùng thử 1 lần duy nhất)
    p_trial = subparsers.add_parser("trial", help="Chế độ DÙNG THỬ 1 LẦN DUY NHẤT dành cho Cline, Antigravity, OpenCode")
    p_trial.add_argument("--url", required=True, help="URL bài thi Onluyen")
    p_trial.add_argument("--headless", action="store_true", help="Chạy ẩn danh")
    p_trial.add_argument("--output", default="ket_qua_dung_thu", help="Tên file ảnh kết quả")

    # solve
    p_solve = subparsers.add_parser("solve", help="Giải bài kiểm tra theo URL")
    p_solve.add_argument("--url", required=True, help="URL bài thi (ví dụ: https://app.onluyen.vn/school/test/...)")
    p_solve.add_argument("--headless", action="store_true", help="Chạy ẩn danh")
    p_solve.add_argument("--trial", action="store_true", help="Kích hoạt dưới chế độ dùng thử")
    p_solve.add_argument("--output", default="ket_qua_bai_thi", help="Tên file ảnh chụp kết quả")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "test-ai":
        asyncio.run(cmd_test_ai(args))
    elif args.command == "status":
        asyncio.run(cmd_status(args))
    elif args.command == "scan":
        asyncio.run(cmd_scan(args))
    elif args.command == "trial":
        asyncio.run(cmd_trial(args))
    elif args.command == "solve":
        asyncio.run(cmd_solve(args))

if __name__ == "__main__":
    main()
