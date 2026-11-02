import asyncio
import re
from typing import Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.ai.prompts import format_choice_prompt, parse_choice_answer, format_short_answer_prompt, parse_short_answer
from autoedu.extractor.dual_pane_extractor import DualPaneExtractor

class UniversalAdapter(BasePlatformAdapter):
    """
    Adapter Vạn Năng (Universal Web Exam Solver)
    Tự động phân tích cây DOM tổng quát để giải bài thi trên MỌI trang web giáo dục:
    (OLM.vn, VnEdu, Submoi, VietJack, Quizizz, Microsoft Forms, Canvas, Moodle và các web trường học khác).
    Tự động kích hoạt Dual-Pane Linguistic Runner nếu phát hiện layout đề thi ngoại ngữ / bài đọc.
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

        await page.goto(test_url, wait_until="domcontentloaded")
        await asyncio.sleep(2.5)

        # 0. Kiểm tra thông minh: nếu phát hiện split-screen reading passage -> Ủy quyền sang LanguageExamAdapter
        try:
            extractor = DualPaneExtractor(page)
            view = await extractor.extract_current_view()
            if view.get("hasSplitScreen") or (view.get("passage", {}).get("paragraphs") and len(view.get("passage", {}).get("paragraphs")) >= 2):
                print("⚡ [Universal] Phát hiện cấu trúc Dual-Pane / Reading Passage đa đoạn! Tự động kích hoạt Linguistic Exam Solver...")
                from autoedu.platforms.language_exam import LanguageExamAdapter
                lang_adapter = LanguageExamAdapter()
                return await lang_adapter.solve_test(page, test_url, ai, screenshot_name)
        except Exception as e:
            print(f"ℹ️ [Universal] Dual-pane check note: {e}")

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
            "button:has-text('Nộp bài')", "button:has-text('Nộp Bài')",
            "button:has-text('Submit')", "button:has-text('Hoàn thành')",
            "input[type='submit']", ".btn-submit"
        ]
        for sel in submit_selectors:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                print(f"   [✓] Đã bấm nút nộp bài: {sel}")
                await asyncio.sleep(2)
                break

        if screenshot_name:
            await page.screenshot(path=screenshot_name, full_page=True)
            print(f"📸 Đã lưu ảnh minh chứng tại: {screenshot_name}")

        return True

    async def _solve_flat_radios(self, page: Page, ai: GeminiWebClient, screenshot_name: Optional[str]) -> bool:
        """Phương án dự phòng: gom nhóm các thẻ radio theo thuộc tính 'name'."""
        radio_groups = await page.evaluate("""() => {
            const groups = {};
            document.querySelectorAll('input[type="radio"]').forEach(r => {
                const name = r.name || 'unnamed';
                if (!groups[name]) groups[name] = [];
                groups[name].push(r.value || r.id || 'opt');
            });
            return groups;
        }""")
        print(f"🎯 [Universal] Tìm thấy {len(radio_groups)} nhóm radio.")
        for name, opts in radio_groups.items():
            try:
                radios = await page.query_selector_all(f"input[type='radio'][name='{name}']")
                if radios:
                    await radios[0].click()
            except Exception:
                pass
        return True
