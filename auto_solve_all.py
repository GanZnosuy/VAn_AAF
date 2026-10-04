import asyncio
import os
import re
import sys
import json
from playwright.async_api import async_playwright
from gemini_web_adapter import get_browser_executable
from test_prompts import query_gemini

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

USER_DATA_DIR = os.path.expanduser(r"~/.onluyen-browser-profile")
USERNAME = os.getenv("ONLUYEN_USERNAME", "")
PASSWORD = os.getenv("ONLUYEN_PASSWORD", "")

JS_EXTRACTOR = """() => {
    function mmlToText(node) {
        if (!node) return '';
        if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim();
        const tag = node.tagName.toLowerCase();
        const children = Array.from(node.childNodes);
        if (tag === 'msup') return mmlToText(children[0]) + '^' + mmlToText(children[1]);
        if (tag === 'msub') return mmlToText(children[0]) + '_' + mmlToText(children[1]);
        if (tag === 'msubsup') return mmlToText(children[0]) + '_' + mmlToText(children[1]) + '^' + mmlToText(children[2]);
        if (tag === 'mfrac') return '(' + mmlToText(children[0]) + ')/(' + mmlToText(children[1]) + ')';
        if (tag === 'msqrt') return 'sqrt(' + children.map(mmlToText).join('') + ')';
        if (tag === 'mover') return 'vec(' + mmlToText(children[0]) + ')';
        return children.map(mmlToText).join('');
    }

    function getCleanText(el) {
        if (!el) return '';
        const clone = el.cloneNode(true);
        clone.querySelectorAll('mjx-container').forEach(c => {
            const mml = c.querySelector('math');
            if (mml) {
                c.replaceWith(document.createTextNode(' ' + mmlToText(mml) + ' '));
            } else {
                c.replaceWith(document.createTextNode(' ' + c.innerText.replace(/\\s+/g, '') + ' '));
            }
        });
        clone.querySelectorAll('img').forEach(img => {
            img.replaceWith(document.createTextNode(' [Hình: ' + (img.alt || img.src) + '] '));
        });
        return clone.innerText.replace(/\\s+/g, ' ').trim();
    }

    const qName = document.querySelector('.question-name') || document.querySelector('.question-title') || document.querySelector('.step-content');
    const questionText = getCleanText(qName);
    const opts = Array.from(document.querySelectorAll('.question-option')).map(o => getCleanText(o));
    
    // Tìm các câu khẳng định Đúng/Sai
    const statements = [];
    for (const el of document.querySelectorAll('p, div, li, tr')) {
        const t = getCleanText(el);
        if (/^[a-d]\\)/.test(t) && t.length < 350) {
            statements.push(t.replace(/ĐúngSai/g, '').trim());
        }
    }
    
    // Loại trừ trùng lặp cho mệnh đề
    const uniqueStmts = [];
    for (const s of statements) {
        if (!uniqueStmts.some(u => u.startsWith(s.substring(0, 5)))) {
            uniqueStmts.push(s);
        }
    }

    const hasInput = !!document.querySelector("input[id^='mathplay-answer'], .step-content input[type='text'], input.can-resize-second");
    const labels = Array.from(document.querySelectorAll('label')).filter(l => {
        const t = l.innerText ? l.innerText.trim() : '';
        return t === 'Đúng' || t === 'Sai';
    });
    const hasTrueFalse = labels.length >= 8;

    return {
        question: questionText,
        options: opts,
        statements: uniqueStmts,
        hasInput: hasInput,
        hasTrueFalse: hasTrueFalse,
        numOptions: opts.length
    };
}"""

async def solve_part_1(page, q_num: int, data: dict):
    """Xử lý trắc nghiệm chọn 1 đáp án (A, B, C, D)"""
    print(f"📝 [Câu {q_num}] Trắc nghiệm A-D: {data['question'][:120]}...")
    opts = data['options']
    for idx, o in enumerate(opts):
        print(f"   {chr(65+idx)}. {o[:80]}")

    formatted_opts = "\n".join([f"{chr(65+idx)}. {o}" for idx, o in enumerate(opts)])
    prompt = (
        f"{data['question']}\n\n"
        f"Các lựa chọn:\n{formatted_opts}\n\n"
        f"Hãy giải bài tập và cho biết đáp án nào là đúng nhất.\n"
        f"Kết luận cuối cùng bằng đúng định dạng:\n"
        f"ĐÁP ÁN: <A/B/C/D>"
    )
    
    res = await query_gemini(prompt)
    match = re.search(r"ĐÁP ÁN:.*?([A-D])\b", res, re.IGNORECASE)
    if not match:
        letters = re.findall(r"\b([A-D])\b", res)
        chosen = letters[-1] if letters else "A"
    else:
        chosen = match.group(1).upper()
        
    print(f"💡 AI chọn: {chosen}")
    letter_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
    
    opt_elements = await page.query_selector_all(".question-option")
    if len(opt_elements) > letter_idx:
        await opt_elements[letter_idx].click()
        print(f"👉 Đã click chọn: {chosen}")
    await asyncio.sleep(0.8)
    
    # Bấm TRẢ LỜI
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        print("🔘 Đã nhấn nút 'TRẢ LỜI'")
        await asyncio.sleep(1.5)

async def solve_part_2(page, q_num: int, data: dict):
    """Xử lý Đúng / Sai 4 ý a, b, c, d"""
    print(f"📝 [Câu {q_num}] Đúng/Sai 4 ý: {data['question'][:120]}...")
    stmts = data['statements']
    for s in stmts:
        print(f"   • {s[:80]}")

    stmts_text = "\n".join(stmts) if stmts else "Xem trong đề bài."
    prompt = (
        f"{data['question']}\n\n"
        f"Các khẳng định cần xét tính đúng/sai:\n{stmts_text}\n\n"
        f"Hãy xét từng khẳng định a, b, c, d là Đúng hay Sai.\n"
        f"Kết luận cuối cùng theo đúng định dạng sau:\n"
        f"a) <Đúng/Sai>\n"
        f"b) <Đúng/Sai>\n"
        f"c) <Đúng/Sai>\n"
        f"d) <Đúng/Sai>"
    )
    
    res = await query_gemini(prompt)
    print(f"💡 AI phân tích Đúng/Sai:")
    
    answers = {}
    for part in ["a", "b", "c", "d"]:
        m = re.search(rf"{part}\)\s*[*_]*\s*(Đúng|Sai)", res, re.IGNORECASE)
        answers[part] = m.group(1).capitalize() if m else "Đúng"
        print(f"   {part}) -> {answers[part]}")
        
    mapping = {
        "a": 0 if answers["a"] == "Đúng" else 1,
        "b": 2 if answers["b"] == "Đúng" else 3,
        "c": 4 if answers["c"] == "Đúng" else 5,
        "d": 6 if answers["d"] == "Đúng" else 7,
    }
    for part, idx in mapping.items():
        await page.evaluate(f"""idx => {{
            const ls = Array.from(document.querySelectorAll('label')).filter(l => {{
                const t = l.innerText ? l.innerText.trim() : '';
                return t === 'Đúng' || t === 'Sai';
            }});
            if (ls[idx]) ls[idx].click();
        }}""", idx)
        await asyncio.sleep(0.3)
    print("👉 Đã chọn toàn bộ 4 ý Đúng/Sai.")
        
    await asyncio.sleep(0.8)
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        print("🔘 Đã nhấn nút 'TRẢ LỜI'")
        await asyncio.sleep(1.5)

async def solve_part_3(page, q_num: int, data: dict):
    """Xử lý trả lời ngắn / điền số"""
    print(f"📝 [Câu {q_num}] Điền từ/Số: {data['question'][:150]}...")
    prompt = (
        f"{data['question']}\n\n"
        f"Yêu cầu: Giải chi tiết bài tập và đưa ra kết quả cuối cùng.\n"
        f"Quy tắc ghi đáp án: Chỉ sử dụng chữ số, dấu phẩy ',' (nếu là số thập phân) và dấu '-' (nếu là số âm). Không viết thêm bất kỳ chữ nào khác.\n"
        f"Kết luận cuối cùng bằng định dạng chính xác:\n"
        f"ĐÁP ÁN: <số>"
    )
    
    res = await query_gemini(prompt)
    match = re.search(r"ĐÁP ÁN:\s*[*_]*\s*([-\d,.]+)", res)
    if match:
        raw_val = match.group(1).replace(".", ",")
    else:
        nums = re.findall(r"[-]?\d+(?:[.,]\d+)?", res)
        raw_val = nums[-1].replace(".", ",") if nums else "0"
        
    print(f"💡 AI tính ra: {raw_val}")
    ans_input = await page.query_selector("input[id^='mathplay-answer'], .step-content input[type='text'], input.can-resize-second")
    if ans_input:
        await ans_input.fill(raw_val)
        print(f"👉 Đã điền vào ô đáp án: {raw_val}")
        
    await asyncio.sleep(0.8)
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        print("🔘 Đã nhấn nút 'TRẢ LỜI'")
        await asyncio.sleep(1.5)

async def run_single_assignment(page, test_url: str, output_name: str):
    print("\n" + "=" * 70)
    print(f"📖 BẮT ĐẦU GIẢI BÀI TẬP: {test_url}")
    print("=" * 70)

    await page.goto(test_url, wait_until="networkidle")
    await asyncio.sleep(3)

    # Đăng nhập nếu bị yêu cầu
    if "login" in page.url.lower():
        print("[!] Phát hiện trang đăng nhập...")
        user_input = await page.wait_for_selector('input[placeholder*="Tên đăng nhập"], input[type="text"]', timeout=5000)
        await user_input.fill(USERNAME)
        pass_input = await page.wait_for_selector('input[type="password"]', timeout=5000)
        await pass_input.fill(PASSWORD)
        login_btn = await page.wait_for_selector('button:has-text("Đăng nhập")', timeout=5000)
        await login_btn.click()
        await asyncio.sleep(5)
        if "/test/" not in page.url:
            await page.goto(test_url, wait_until="networkidle")

    # Kiểm tra nút Bắt đầu (DIV .btn-test.green)
    start_btn = await page.query_selector(".btn-test.green")
    if start_btn:
        print("▶️ Nhấn nút Bắt đầu làm bài...")
        await start_btn.click()
        print("Đang tải dữ liệu bài thi...")

    # Đợi danh sách câu hỏi xuất hiện
    await page.wait_for_selector(".grid .option", timeout=25000)
    await asyncio.sleep(2)

    # Đếm số lượng câu hỏi trong phiếu trả lời
    total_q = await page.evaluate("""() => {
        const items = document.querySelectorAll('.grid .option');
        return items.length;
    }""")
    print(f"📊 Tổng số câu hỏi: {total_q}")

    for q_num in range(1, total_q + 1):
        # Click vào câu hỏi q_num
        click_info = await page.evaluate(f"""num => {{
            const items = document.querySelectorAll('.grid .option');
            for (const item of items) {{
                if (item.innerText.trim() === String(num)) {{
                    item.click();
                    return {{
                        found: true,
                        isDone: item.classList.contains('done')
                    }};
                }}
            }}
            return {{ found: false, isDone: false }};
        }}""", q_num)

        if not click_info.get("found"):
            print(f"[!] Không tìm thấy ô câu {q_num}")
            continue

        if click_info.get("isDone"):
            print(f"⏩ [Câu {q_num}/{total_q}] Đã hoàn thành trước đó -> Bỏ qua.")
            continue

        print(f"\n--- [CÂU {q_num} / {total_q}] ---")
        await asyncio.sleep(1.5)

        data = await page.evaluate(JS_EXTRACTOR)

        # Nhận diện dạng bài
        if data["hasInput"]:
            await solve_part_3(page, q_num, data)
        elif data["hasTrueFalse"]:
            await solve_part_2(page, q_num, data)
        else:
            await solve_part_1(page, q_num, data)

        await asyncio.sleep(1)

        # Kiểm tra xem câu hỏi đã đổi thành done chưa, nếu chưa bấm lại TRẢ LỜI
        is_done = await page.evaluate(f"""num => {{
            const items = document.querySelectorAll('.grid .option');
            for (const item of items) {{
                if (item.innerText.trim() === String(num)) {{
                    return item.classList.contains('done');
                }}
            }}
            return false;
        }}""", q_num)
        
        if not is_done:
            print(f"[!] Câu {q_num} chưa có nhãn 'done', thử bấm lại TRẢ LỜI...")
            tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
            if tra_loi and await tra_loi.is_visible():
                await tra_loi.click()
                await asyncio.sleep(1.5)

    print("\n" + "=" * 60)
    print(f"🎉 ĐÃ HOÀN THÀNH TẤT CẢ {total_q} CÂU HỎI!")
    print("🚀 TIẾN HÀNH NỘP BÀI...")
    print("=" * 60)

    # Nộp bài
    submit_btn = await page.query_selector("button:has-text('Nộp Bài'), button:has-text('Nộp bài')")
    if submit_btn:
        await submit_btn.click()
        await asyncio.sleep(2)

        confirm_btn = await page.query_selector(".modal button:has-text('Nộp bài'), [role='dialog'] button:has-text('Nộp bài'), .modal button:has-text('Nộp Bài')")
        if confirm_btn:
            await confirm_btn.click()
            print("[✓] Đã bấm xác nhận Nộp bài trong dialog!")
        else:
            all_submits = await page.query_selector_all("button:has-text('Nộp bài')")
            if all_submits:
                await all_submits[-1].click()
                print("[✓] Đã bấm nút nộp bài!")

        await asyncio.sleep(5)
        # Bấm đóng / xác nhận nếu có modal "Nộp bài thành công"
        close_dialog = await page.query_selector(".modal button:has-text('Xác nhận'), button:has-text('Đóng'), button:has-text('Xem kết quả')")
        if close_dialog:
            try:
                await close_dialog.click()
                await asyncio.sleep(2)
            except Exception:
                pass

        screenshot_path = f"result_{output_name}.png"
        await page.screenshot(path=screenshot_path)
        print(f"[✓] Đã chụp ảnh kết quả: {screenshot_path}")
    else:
        print("[!] Không tìm thấy nút Nộp Bài.")

async def main():
    assignments = [
        {
            "name": "hoa_hoc_ester_lipid",
            "title": "12A1 - HÓA HỌC: Ester - Lipid (Tổng hợp)",
            "url": "https://app.onluyen.vn/school/test/6abf9b1361250459d0af450b"
        },
        {
            "name": "toan_duong_tiem_can",
            "title": "12A1 - TOÁN: Bài 3. Đường tiệm cận của đồ thị hàm số (Cơ bản)",
            "url": "https://app.onluyen.vn/school/test/6abbc1ed180b539b37d25be3"
        }
    ]

    print("=" * 70)
    print("🤖 CHƯƠNG TRÌNH TỰ ĐỘNG GIẢI TOÀN BỘ BÀI TẬP CÒN LẠI TRÊN ONLUYEN")
    print(f"Tổng số bài tập cần làm: {len(assignments)}")
    print("=" * 70)

    browser_exe = get_browser_executable()
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=browser_exe,
            headless=False,
            viewport={"width": 1366, "height": 850},
            args=["--start-maximized"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        for idx, item in enumerate(assignments):
            print(f"\n▶️ [{idx+1}/{len(assignments)}] BẮT ĐẦU: {item['title']}")
            try:
                await run_single_assignment(page, item["url"], item["name"])
            except Exception as e:
                print(f"[!] Lỗi khi làm bài {item['title']}: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 70)
        print("🏆 TẤT CẢ CÁC BÀI TẬP ĐÃ ĐƯỢC HOÀN THÀNH VÀ NỘP BÀI THÀNH CÔNG!")
        print("=" * 70)
        await asyncio.sleep(5)
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
