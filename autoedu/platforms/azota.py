import asyncio
import re
from typing import Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.ai.prompts import format_choice_prompt, parse_choice_answer

class AzotaAdapter(BasePlatformAdapter):
    """Adapter tự động giải và nộp bài trên hệ thống thi trực tuyến Azota.vn."""
    name = "Azota.vn"
    supported_domains = ["azota.vn"]

    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        print("=" * 65)
        print(f"📖 [AZOTA] BẮT ĐẦU GIẢI ĐỀ THI: {test_url}")
        print("=" * 65)

        await page.goto(test_url, wait_until="networkidle")
        await asyncio.sleep(2)

        # 1. Bấm nút bắt đầu làm bài nếu có
        start_btn = await page.query_selector("button:has-text('Bắt đầu làm bài'), button:has-text('Làm bài')")
        if start_btn:
            print("▶️ [Azota] Bấm nút bắt đầu làm bài...")
            await start_btn.click()
            await asyncio.sleep(2)

        # 2. Quét danh sách các câu hỏi trên đề thi Azota
        questions = await page.query_selector_all(".question-item, .item-question, [id^='question-']")
        if not questions:
            # Thử tìm các khối câu hỏi qua tiêu đề câu
            questions = await page.query_selector_all("div:has(p:has-text('Câu'))")

        print(f"📊 [Azota] Tìm thấy {len(questions)} câu hỏi.")

        for idx, q_el in enumerate(questions):
            q_num = idx + 1
            print(f"\n--- [AZOTA CÂU {q_num}/{len(questions)}] ---")

            # Lấy nội dung đề bài
            q_text = await q_el.evaluate("el => el.innerText.replace(/\\s+/g, ' ').trim()")
            
            # Lấy các lựa chọn đáp án A, B, C, D
            options = await q_el.evaluate("""el => {
                const opts = Array.from(el.querySelectorAll('.answer-item, .option-item, .azota-option, label, [role=\"radio\"]'));
                return opts.map(o => o.innerText.replace(/\\s+/g, ' ').trim());
            }""")

            if not options:
                options = ["A", "B", "C", "D"]

            prompt = format_choice_prompt(q_text, options)
            ai_ans = await ai.query(prompt)
            chosen = parse_choice_answer(ai_ans)
            print(f"   [AI] Chọn đáp án: {chosen}")

            letter_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
            
            # Click vào phương án đã chọn
            opt_elements = await q_el.query_selector_all(".answer-item, .option-item, .azota-option, label, [role='radio'], input[type='radio']")
            if len(opt_elements) > letter_idx:
                await opt_elements[letter_idx].click()
            else:
                # Fallback click nút A B C D trên thanh phiếu đáp án
                await page.evaluate(f"""({{q, chosen}}) => {{
                    const btns = Array.from(document.querySelectorAll('button, div, span'));
                    const target = btns.find(b => b.innerText.trim() === chosen);
                    if (target) target.click();
                }}""", {"q": q_num, "chosen": chosen})

            await asyncio.sleep(0.5)

        # 3. Nộp bài
        print("\n🚀 [Azota] Tiến hành nộp bài...")
        submit_btn = await page.query_selector("button:has-text('Nộp bài'), button:has-text('NỘP BÀI')")
        if submit_btn:
            await submit_btn.click()
            await asyncio.sleep(1.5)
            # Xác nhận hộp thoại
            confirm = await page.query_selector(".modal button:has-text('Nộp bài'), .modal button:has-text('Xác nhận'), .modal button:has-text('Đồng ý')")
            if confirm:
                await confirm.click()

            await asyncio.sleep(3)
            if screenshot_name:
                await page.screenshot(path=f"{screenshot_name}.png")
                print(f"[✓] Đã chụp ảnh kết quả: {screenshot_name}.png")
            return True

        return False
