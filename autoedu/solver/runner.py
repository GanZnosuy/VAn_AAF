import asyncio
from typing import Optional
from playwright.async_api import Page
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.extractor.mathml_parser import JS_EXTRACTOR_SCRIPT
from autoedu.browser.navigator import auto_login_if_needed
from autoedu.solver.handlers import handle_choice, handle_true_false, handle_short_answer, click_tra_loi_btn

async def solve_test_url(
    page: Page,
    test_url: str,
    ai_client: Optional[GeminiWebClient] = None,
    screenshot_name: Optional[str] = None
) -> bool:
    """
    Quy trình giải tự động 1 bài kiểm tra từ URL.
    Bao gồm vào phòng thi, giải từng câu, lưu đáp án, nộp bài và chụp ảnh kết quả.
    """
    ai = ai_client or GeminiWebClient()
    print("=" * 65)
    print(f"📖 BẮT ĐẦU GIẢI: {test_url}")
    print("=" * 65)

    await page.goto(test_url, wait_until="networkidle")
    await asyncio.sleep(2)
    await auto_login_if_needed(page)

    # 1. Nhấn nút Bắt đầu nếu đang ở trang giới thiệu và chưa có lưới câu hỏi
    has_grid = await page.query_selector(".grid .option")
    if not has_grid:
        start_btn = await page.query_selector(".btn-test.green, button:has-text('Bắt đầu'), button:has-text('Làm bài'), button:has-text('Tiếp tục'), .btn:has-text('Tiếp tục')")
        if start_btn:
            print("▶️ Bấm nút Bắt đầu/Tiếp tục làm bài...")
            await start_btn.click()

    # 2. Đợi danh sách câu hỏi xuất hiện
    try:
        await page.wait_for_selector(".grid .option", timeout=25000)
    except Exception:
        print("[!] Không tìm thấy danh sách câu hỏi (.grid .option).")
        return False

    await asyncio.sleep(1.5)

    # 3. Lấy tổng số câu hỏi
    total_q = await page.evaluate("() => document.querySelectorAll('.grid .option').length")
    print(f"📊 Tổng số câu hỏi: {total_q}")

    for q_num in range(1, total_q + 1):
        # Click vào câu hỏi q_num trong phiếu trả lời
        info = await page.evaluate(f"""num => {{
            const items = document.querySelectorAll('.grid .option');
            for (const item of items) {{
                if (item.innerText.trim() === String(num)) {{
                    item.click();
                    return {{ found: true, isDone: item.classList.contains('done') }};
                }}
            }}
            return {{ found: false, isDone: false }};
        }}""", q_num)

        if not info.get("found"):
            continue

        if info.get("isDone"):
            print(f"⏩ [Câu {q_num}/{total_q}] Đã hoàn thành trước đó -> Bỏ qua.")
            continue

        print(f"\n--- [CÂU {q_num}/{total_q}] ---")
        await asyncio.sleep(1.2)

        data = await page.evaluate(JS_EXTRACTOR_SCRIPT)

        # Định tuyến theo loại câu hỏi
        if data.get("hasInput"):
            await handle_short_answer(page, q_num, data, ai)
        elif data.get("hasTrueFalse"):
            await handle_true_false(page, q_num, data, ai)
        else:
            await handle_choice(page, q_num, data, ai)

        await asyncio.sleep(0.8)

        # Kiểm tra xác nhận lưu đáp án (thử tối đa 2 lần)
        for retry in range(2):
            is_done = await page.evaluate(f"""num => {{
                const items = document.querySelectorAll('.grid .option');
                for (const item of items) {{
                    if (item.innerText.trim() === String(num)) return item.classList.contains('done');
                }}
                return false;
            }}""", q_num)
            if is_done:
                break
            print(f"[!] Câu {q_num} chưa có nhãn 'done', bấm lại TRẢ LỜI (lần {retry+1})...")
            await click_tra_loi_btn(page)
            await asyncio.sleep(1.2)

    print("\n" + "=" * 65)
    print("🎉 HOÀN THÀNH TOÀN BỘ CÂU HỎI! TIẾN HÀNH NỘP BÀI...")
    print("=" * 65)

    # 4. Nộp bài
    submit_btn = await page.query_selector("button:has-text('Nộp Bài'), button:has-text('Nộp bài')")
    if submit_btn:
        await submit_btn.click()
        await asyncio.sleep(2)

        confirm_btn = await page.query_selector(".modal button:has-text('Nộp bài'), [role='dialog'] button:has-text('Nộp bài'), .modal button:has-text('Nộp Bài')")
        if confirm_btn:
            await confirm_btn.click()
            print("[✓] Đã bấm xác nhận Nộp bài.")
        else:
            all_submits = await page.query_selector_all("button:has-text('Nộp bài')")
            if all_submits:
                await all_submits[-1].click()
                print("[✓] Đã bấm nút nộp bài!")

        await asyncio.sleep(5)
        close_dialog = await page.query_selector(".modal button:has-text('Xác nhận'), button:has-text('Đóng'), button:has-text('Xem kết quả')")
        if close_dialog:
            try:
                await close_dialog.click()
                await asyncio.sleep(2)
            except Exception:
                pass

        if screenshot_name:
            await page.screenshot(path=f"{screenshot_name}.png")
            print(f"[✓] Đã lưu ảnh kết quả: {screenshot_name}.png")

        return True

    return False
