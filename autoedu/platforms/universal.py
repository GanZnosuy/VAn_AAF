import asyncio
import re
from typing import Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.ai.prompts import format_choice_prompt, parse_choice_answer, format_short_answer_prompt, parse_short_answer

class UniversalAdapter(BasePlatformAdapter):
    """
    Adapter Vạn Năng (Universal Web Exam Solver)
    Tự động phân tích cây DOM tổng quát để giải bài thi trên MỌI trang web giáo dục:
    (OLM.vn, VnEdu, Submoi, VietJack, Quizizz, Microsoft Forms, và các web trường học khác).
    """
    name = "Universal Web Solver"
    supported_domains = ["*"]

    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        print("=" * 65)
        print(f"🌐 [UNIVERSAL SOLVER] TỰ ĐỘNG PHÂN TÍCH VÀ GIẢI ĐỀ THI: {test_url}")
        print("=" * 65)

        await page.goto(test_url, wait_until="networkidle")
        await asyncio.sleep(2.5)

        # 1. Tìm các cụm câu hỏi tổng quát trong trang web
        # Thử tìm các fieldset, form, hoặc các container chứa câu hỏi
        question_blocks = await page.query_selector_all("fieldset, [class*='question'], [id*='question'], [class*='cau-hoi'], .item-cau-hoi")
        if not question_blocks:
            # Fallback: tìm các khối có chứa radio buttons
            question_blocks = await page.evaluate_handle("""() => {
                const radios = Array.from(document.querySelectorAll('input[type="radio"], [role="radio"]'));
                const parents = new Set();
                radios.forEach(r => {
                    const block = r.closest('form, fieldset, li, tr, .item, .card, div[class*="block"]') || r.parentElement.parentElement;
                    if (block) parents.add(block);
                });
                return Array.from(parents);
            }""")
            question_blocks = await question_blocks.get_properties()
            question_blocks = list(question_blocks.values())

        print(f"📊 [Universal] Nhận diện được {len(question_blocks)} khối câu hỏi trên trang.")

        if not question_blocks:
            print("[!] Không tìm thấy cấu trúc câu hỏi rõ ràng. Đang chuyển sang chế độ quét radio tổng...")
            # Quét tất cả radio group
            return await self._solve_flat_radios(page, ai, screenshot_name)

        for idx, block in enumerate(question_blocks):
            q_num = idx + 1
            try:
                block_el = block.as_element() if hasattr(block, "as_element") else block
                if not block_el:
                    continue

                q_text = await block_el.evaluate("el => el.innerText.replace(/\\s+/g, ' ').trim()")
                if len(q_text) < 5:
                    continue

                radios = await block_el.query_selector_all("input[type='radio'], [role='radio'], label")
                text_input = await block_el.query_selector("input[type='text'], textarea")

                print(f"\n--- [CÂU {q_num}]: {q_text[:75]}... ---")

                if radios and len(radios) >= 2:
                    opt_texts = []
                    for r in radios:
                        t = await r.evaluate("el => el.innerText.replace(/\\s+/g, ' ').trim()")
                        opt_texts.append(t if t else "Phương án")

                    prompt = format_choice_prompt(q_text, opt_texts[:4])
                    ai_resp = await ai.query(prompt)
                    chosen = parse_choice_answer(ai_resp)
                    print(f"   [AI] Chọn đáp án: {chosen}")

                    idx_map = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
                    if len(radios) > idx_map:
                        await radios[idx_map].click()
                elif text_input:
                    prompt = format_short_answer_prompt(q_text)
                    ai_resp = await ai.query(prompt)
                    val = parse_short_answer(ai_resp)
                    print(f"   [AI] Điền số: {val}")
                    await text_input.fill(val)

                await asyncio.sleep(0.4)
            except Exception as e:
                print(f"[!] Bỏ qua câu {q_num} do lỗi bóc tách: {e}")

        # 2. Tìm nút nộp bài thông minh trên mọi trang web
        print("\n🚀 [Universal] Tìm kiếm nút Nộp bài / Hoàn thành...")
        submit_selectors = [
            "button:has-text('Nộp bài')",
            "button:has-text('NỘP BÀI')",
            "button:has-text('Hoàn thành')",
            "button:has-text('Gửi')",
            "button:has-text('Submit')",
            "input[type='submit']",
            "a:has-text('Nộp bài')"
        ]
        for sel in submit_selectors:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                print(f"[✓] Đã click nút: {sel}")
                await asyncio.sleep(2)
                # Đóng confirm modal nếu có
                confirm = await page.query_selector(".modal button:has-text('Đồng ý'), .modal button:has-text('Xác nhận'), .modal button:has-text('Nộp bài')")
                if confirm:
                    await confirm.click()
                break

        await asyncio.sleep(3)
        if screenshot_name:
            await page.screenshot(path=f"{screenshot_name}.png")
            print(f"[✓] Đã lưu ảnh kết quả: {screenshot_name}.png")
        return True

    async def _solve_flat_radios(self, page: Page, ai: GeminiWebClient, screenshot_name: Optional[str]) -> bool:
        """Dự phòng: Xử lý dạng bài thi phân tán đơn giản."""
        radios = await page.query_selector_all("input[type='radio']")
        print(f"📊 Tìm thấy {len(radios)} nút radio rải rác.")
        if screenshot_name:
            await page.screenshot(path=f"{screenshot_name}.png")
        return len(radios) > 0
