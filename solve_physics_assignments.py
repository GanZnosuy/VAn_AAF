import asyncio
import os
import sys
import shutil
from pathlib import Path
from playwright.async_api import async_playwright
from autoedu.browser.context import launch_browser_context
from autoedu.solver.runner import solve_test_url
from autoedu.ai.gemini_web import GeminiWebClient

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

ARTIFACTS_DIR = Path(r"C:\Users\vuong\.gemini\antigravity\brain\5b530879-fc44-450d-a4c2-d13b720bc31c")

ASSIGNMENTS = [
    {
        "id": 1,
        "title": "Vật lí 12 - Nhiệt dung riêng (tổng hợp)",
        "url": "https://app.onluyen.vn/school/test/6ac4bb11b25a13ce9eb6678a",
        "screenshot": "result_nhiet_dung_rieng"
    },
    {
        "id": 2,
        "title": "Vật lí 12 - Nhiệt độ thang đo nhiệt độ nhiệt kế (tổng hợp)",
        "url": "https://app.onluyen.vn/school/test/6ac4ba90c27b45b4ffb8ee89",
        "screenshot": "result_thang_do_nhiet_do"
    }
]

def copy_to_artifacts(src_file: str):
    """Sao chép tệp kết quả vào thư mục artifacts để hiển thị trên UI."""
    try:
        if os.path.exists(src_file):
            dest = ARTIFACTS_DIR / os.path.basename(src_file)
            shutil.copy2(src_file, dest)
            print(f"[✓] Đã sao chép sang artifacts: {dest}")
    except Exception as e:
        print(f"[!] Không thể copy sang artifacts: {e}")

async def main():
    print("=" * 80)
    print("🚀 BẮT ĐẦU TỰ ĐỘNG GIẢI CÁC BÀI TẬP VẬT LÍ MỚI GIAO TRÊN ONLUYEN")
    print(f"📌 Tổng số bài tập cần hoàn thành: {len(ASSIGNMENTS)}")
    for a in ASSIGNMENTS:
        print(f"   [{a['id']}] {a['title']}")
        print(f"       URL: {a['url']}")
    print("=" * 80)

    ai = GeminiWebClient()
    results_summary = []

    async with async_playwright() as p:
        # Khởi chạy Chromium persistent context với cấu hình tối ưu
        context = await launch_browser_context(p, headless=False)
        page = context.pages[0] if context.pages else await context.new_page()

        # Tự động đồng ý các hộp thoại xác nhận (nếu có)
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))

        for item in ASSIGNMENTS:
            print("\n" + "#" * 75)
            print(f"🎯 TIẾN HÀNH GIẢI BÀI [{item['id']}/{len(ASSIGNMENTS)}]: {item['title']}")
            print("#" * 75)

            try:
                success = await solve_test_url(
                    page=page,
                    test_url=item["url"],
                    ai_client=ai,
                    screenshot_name=item["screenshot"]
                )

                screenshot_path = f"{item['screenshot']}.png"
                copy_to_artifacts(screenshot_path)

                results_summary.append({
                    "title": item["title"],
                    "url": item["url"],
                    "status": "Hoàn thành & Đã nộp bài" if success else "Thất bại",
                    "screenshot": screenshot_path
                })
            except Exception as e:
                print(f"[!] Lỗi trong quá trình giải bài {item['title']}: {e}")
                import traceback
                traceback.print_exc()
                results_summary.append({
                    "title": item["title"],
                    "url": item["url"],
                    "status": f"Lỗi: {e}",
                    "screenshot": None
                })

            await asyncio.sleep(3)

        # 3. Kiểm tra lại trang danh sách bài tập (Dashboard)
        print("\n" + "=" * 80)
        print("🔍 KIỂM TRA LẠI MỤC 'CẦN LÀM' TRÊN DASHBOARD BÀI TẬP...")
        print("=" * 80)
        try:
            await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="networkidle")
            await asyncio.sleep(3)

            # Đóng popup nếu xuất hiện
            for sel in [".close", "[aria-label='Close']", "button:has-text('Đóng')", ".modal button", "img[src*='close']"]:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass

            dashboard_img = "result_dashboard_physics_done.png"
            await page.screenshot(path=dashboard_img)
            copy_to_artifacts(dashboard_img)
            print(f"[✓] Đã chụp ảnh xác nhận trang danh sách bài tập: {dashboard_img}")

            # Đếm số bài còn lại trong mục Cần làm
            remaining_tasks = await page.evaluate("""() => {
                const results = [];
                const rows = document.querySelectorAll('.func-info, .task-item');
                rows.forEach((r, idx) => {
                    const parent = r.closest('.task-item, .item, tr, .row, .d-flex') || r.parentElement;
                    const text = parent ? parent.innerText.replace(/\\s+/g, ' ').trim() : r.innerText.replace(/\\s+/g, ' ').trim();
                    results.push(text);
                });
                return results;
            }""")

            print(f"📊 Số bài tập còn trong danh sách 'Cần làm': {len(remaining_tasks)}")
            for t in remaining_tasks:
                print(f"  • {t[:90]}")

        except Exception as e:
            print(f"[!] Lỗi khi kiểm tra dashboard: {e}")

        await asyncio.sleep(5)
        await context.close()

    print("\n" + "=" * 80)
    print("🎉 BÁO CÁO KẾT QUẢ TỔNG HỢP:")
    for r in results_summary:
        print(f" - {r['title']}: {r['status']} (Ảnh: {r['screenshot']})")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
