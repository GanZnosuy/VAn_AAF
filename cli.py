import argparse
import asyncio
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.browser.context import launch_browser_context
from autoedu.browser.navigator import scan_assignments
from autoedu.solver.runner import solve_test_url

async def cmd_test_ai(args):
    """Kiểm tra kết nối và trích xuất token Gemini Web AI."""
    print("🤖 Đang kiểm tra kết nối tới Gemini Web...")
    client = GeminiWebClient()
    test_prompt = "Chào bạn! Hãy trả lời ngắn gọn: 1 + 1 bằng mấy?"
    resp = await client.query(test_prompt)
    if resp:
        print(f"[✓] Kết nối thành công!")
        print(f"    Phản hồi từ AI: {resp}")
    else:
        print("[!] Không thể kết nối hoặc cookies đã hết hạn. Hãy cập nhật lại .env.")

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

async def cmd_solve(args):
    """Tự động giải một bài kiểm tra theo URL."""
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
    subparsers.add_parser("test-ai", help="Kiểm tra kết nối Gemini Web AI")

    # scan
    p_scan = subparsers.add_parser("scan", help="Quét bài tập trên Onluyen")
    p_scan.add_argument("--headless", action="store_true", help="Chạy ở chế độ ẩn danh (không hiện cửa sổ Chrome)")

    # solve
    p_solve = subparsers.add_parser("solve", help="Giải bài kiểm tra theo URL")
    p_solve.add_argument("--url", required=True, help="URL bài thi (ví dụ: https://app.onluyen.vn/school/test/...)")
    p_solve.add_argument("--headless", action="store_true", help="Chạy ẩn danh")
    p_solve.add_argument("--output", default="ket_qua_bai_thi", help="Tên file ảnh chụp kết quả")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "test-ai":
        asyncio.run(cmd_test_ai(args))
    elif args.command == "scan":
        asyncio.run(cmd_scan(args))
    elif args.command == "solve":
        asyncio.run(cmd_solve(args))

if __name__ == "__main__":
    main()
