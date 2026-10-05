import asyncio
from typing import Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.ai.prompts import format_choice_prompt, parse_choice_answer, format_short_answer_prompt, parse_short_answer

class GoogleFormsAdapter(BasePlatformAdapter):
    """Adapter tự động giải đề thi trên Google Forms (docs.google.com/forms)."""
    name = "Google Forms"
    supported_domains = ["docs.google.com/forms", "forms.gle"]

    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        print("=" * 65)
        print(f"📖 [GOOGLE FORMS] BẮT ĐẦU GIẢI FORM BÀI THI: {test_url}")
        print("=" * 65)

        await page.goto(test_url, wait_until="networkidle")
        await asyncio.sleep(2)

        items = await page.query_selector_all("div[role='listitem']")
        print(f"📊 [Google Forms] Tìm thấy {len(items)} mục câu hỏi.")

        for idx, item in enumerate(items):
            q_num = idx + 1
            heading = await item.query_selector("div[role='heading']")
            if not heading:
                continue
            q_title = await heading.evaluate("el => el.innerText.replace(/\\s+/g, ' ').trim()")
            print(f"\n--- [CÂU {q_num}]: {q_title[:80]}... ---")

            radios = await item.query_selector_all("div[role='radio']")
            text_input = await item.query_selector("input[type='text'], textarea")

            if radios:
                # Trắc nghiệm radio
                opts = []
                for r in radios:
                    txt = await r.evaluate("el => el.innerText.replace(/\\s+/g, ' ').trim()")
                    opts.append(txt)

                prompt = format_choice_prompt(q_title, opts)
                ai_resp = await ai.query(prompt)
                chosen = parse_choice_answer(ai_resp)
                print(f"   [AI] Chọn đáp án: {chosen}")

                letter_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
                if len(radios) > letter_idx:
                    await radios[letter_idx].click()
            elif text_input:
                # Câu hỏi điền từ / số
                prompt = format_short_answer_prompt(q_title)
                ai_resp = await ai.query(prompt)
                ans = parse_short_answer(ai_resp)
                print(f"   [AI] Điền đáp án: {ans}")
                await text_input.fill(ans)

            await asyncio.sleep(0.4)

        # Nộp bài (Bấm nút Gửi / Submit)
        submit_btn = await page.query_selector("div[role='button']:has-text('Gửi'), div[role='button']:has-text('Submit')")
        if submit_btn:
            print("\n🚀 [Google Forms] Bấm nút Gửi bài...")
            await submit_btn.click()
            await asyncio.sleep(3)
            if screenshot_name:
                await page.screenshot(path=f"{screenshot_name}.png")
                print(f"[✓] Đã lưu ảnh kết quả: {screenshot_name}.png")
            return True
        return False
