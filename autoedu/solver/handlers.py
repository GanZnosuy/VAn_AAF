import asyncio
from playwright.async_api import Page
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.ai.prompts import (
    format_choice_prompt, parse_choice_answer,
    format_true_false_prompt, parse_true_false_answer,
    format_short_answer_prompt, parse_short_answer
)

async def click_tra_loi_btn(page: Page) -> bool:
    """Bấm nút TRẢ LỜI để lưu kết quả vào Onluyen."""
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        await asyncio.sleep(1.2)
        return True
    return False

async def handle_choice(page: Page, q_num: int, data: dict, ai: GeminiWebClient):
    """Xử lý câu trắc nghiệm 4 lựa chọn (A, B, C, D)."""
    prompt = format_choice_prompt(data["question"], data["options"])
    res = await ai.query(prompt)
    chosen = parse_choice_answer(res)
    print(f"   [AI] Chọn đáp án: {chosen}")

    letter_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
    opt_elements = await page.query_selector_all(".question-option")
    if len(opt_elements) > letter_idx:
        await opt_elements[letter_idx].click()
    await asyncio.sleep(0.6)
    await click_tra_loi_btn(page)

async def handle_true_false(page: Page, q_num: int, data: dict, ai: GeminiWebClient):
    """Xử lý câu Đúng / Sai 4 ý a, b, c, d."""
    prompt = format_true_false_prompt(data["question"], data["statements"])
    res = await ai.query(prompt)
    answers = parse_true_false_answer(res)
    print(f"   [AI] Đúng/Sai: a={answers.get('a')}, b={answers.get('b')}, c={answers.get('c')}, d={answers.get('d')}")

    mapping = {
        "a": 0 if answers.get("a") == "Đúng" else 1,
        "b": 2 if answers.get("b") == "Đúng" else 3,
        "c": 4 if answers.get("c") == "Đúng" else 5,
        "d": 6 if answers.get("d") == "Đúng" else 7,
    }
    for part, idx in mapping.items():
        await page.evaluate(f"""idx => {{
            const ls = Array.from(document.querySelectorAll('label')).filter(l => {{
                const t = l.innerText ? l.innerText.trim() : '';
                return t === 'Đúng' || t === 'Sai';
            }});
            if (ls[idx]) ls[idx].click();
        }}""", idx)
        await asyncio.sleep(0.2)

    await asyncio.sleep(0.6)
    await click_tra_loi_btn(page)

async def handle_short_answer(page: Page, q_num: int, data: dict, ai: GeminiWebClient):
    """Xử lý câu trả lời ngắn / điền số."""
    prompt = format_short_answer_prompt(data["question"])
    res = await ai.query(prompt)
    raw_val = parse_short_answer(res)
    print(f"   [AI] Điền số: {raw_val}")

    ans_input = await page.query_selector("input[id^='mathplay-answer'], .step-content input[type='text'], input.can-resize-second")
    if ans_input:
        await ans_input.fill(raw_val)
    await asyncio.sleep(0.6)
    await click_tra_loi_btn(page)
