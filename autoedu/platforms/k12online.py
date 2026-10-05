import asyncio
from typing import Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.ai.prompts import format_choice_prompt, parse_choice_answer

class K12OnlineAdapter(BasePlatformAdapter):
    """Adapter tự động giải và nộp bài trên hệ thống trường học K12Online (Viettel)."""
    name = "K12Online"
    supported_domains = ["k12online.vn"]

    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        print("=" * 65)
        print(f"📖 [K12ONLINE] BẮT ĐẦU GIẢI BÀI THI: {test_url}")
        print("=" * 65)

        await page.goto(test_url, wait_until="networkidle")
        await asyncio.sleep(2)

        start_btn = await page.query_selector("button:has-text('Vào thi'), button:has-text('Bắt đầu'), .btn:has-text('Làm bài')")
        if start_btn:
            await start_btn.click()
            await asyncio.sleep(2)

        # Quét các câu hỏi
        q_elements = await page.query_selector_all(".question-item, .box-question, .k12-question")
        print(f"📊 [K12Online] Số câu hỏi: {len(q_elements)}")

        for idx, q_el in enumerate(q_elements):
            q_num = idx + 1
            print(f"\n--- [K12ONLINE CÂU {q_num}/{len(q_elements)}] ---")
            q_text = await q_el.evaluate("el => el.innerText.replace(/\\s+/g, ' ').trim()")
            
            options = await q_el.evaluate("""el => {
                const items = Array.from(el.querySelectorAll('.item-answer, .answer-option, label'));
                return items.map(i => i.innerText.replace(/\\s+/g, ' ').trim());
            }""")
            if not options:
                options = ["A", "B", "C", "D"]

            prompt = format_choice_prompt(q_text, options)
            ans = await ai.query(prompt)
            chosen = parse_choice_answer(ans)
            print(f"   [AI] Chọn đáp án: {chosen}")

            letter_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
            clickable_opts = await q_el.query_selector_all(".item-answer, .answer-option, label, input[type='radio']")
            if len(clickable_opts) > letter_idx:
                await clickable_opts[letter_idx].click()
            await asyncio.sleep(0.5)

        # Nộp bài
        submit_btn = await page.query_selector("button:has-text('Nộp bài'), button:has-text('Hoàn thành')")
        if submit_btn:
            await submit_btn.click()
            await asyncio.sleep(1.5)
            confirm = await page.query_selector(".modal button:has-text('Xác nhận'), .modal button:has-text('Nộp bài')")
            if confirm:
                await confirm.click()
            await asyncio.sleep(3)
            if screenshot_name:
                await page.screenshot(path=f"{screenshot_name}.png")
            return True
        return False
