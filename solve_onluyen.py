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
        return clone.innerText.replace(/\\s+/g, ' ').trim();
    }

    const qName = document.querySelector('.question-name');
    const questionText = getCleanText(qName);
    const opts = Array.from(document.querySelectorAll('.question-option')).map(o => getCleanText(o));
    
    // Tìm các câu khẳng định Đúng/Sai
    const statements = [];
    for (const el of document.querySelectorAll('p, div, li, tr')) {
        const t = getCleanText(el);
        if (/^[a-d]\\)/.test(t) && t.length < 300) {
            statements.push(t.replace(/ĐúngSai/g, '').trim());
        }
    }
    
    // Loại trừ trùng lặp
    const uniqueStmts = [];
    for (const s of statements) {
        if (!uniqueStmts.some(u => u.startsWith(s.substring(0, 5)))) {
            uniqueStmts.push(s);
        }
    }

    return {
        question: questionText,
        options: opts,
        statements: uniqueStmts
    };
}"""

async def solve_part_1(page, q_num: int, data: dict):
    """Xử lý phần I: Trắc nghiệm 4 lựa chọn (A, B, C, D)"""
    print(f"📝 Đề bài: {data['question'][:120]}...")
    opts = data['options']
    for idx, o in enumerate(opts):
        print(f"   {chr(65+idx)}. {o[:80]}")

    formatted_opts = "\n".join([f"{chr(65+idx)}. {o}" for idx, o in enumerate(opts)])
    prompt = (
        f"{data['question']}\n\n"
        f"Các lựa chọn:\n{formatted_opts}\n\n"
        f"Hãy giải bài toán và cho biết đáp án nào là đúng nhất.\n"
        f"Kết luận cuối cùng bằng định dạng chính xác:\n"
        f"ĐÁP ÁN: <A/B/C/D>"
    )
    
    res = await query_gemini(prompt)
    match = re.search(r"ĐÁP ÁN:\s*([A-D])", res, re.IGNORECASE)
    if not match:
        # Tìm chữ cái A, B, C, D xuất hiện cuối cùng
        letters = re.findall(r"\b([A-D])\b", res)
        chosen = letters[-1] if letters else "A"
    else:
        chosen = match.group(1).upper()
        
    print(f"💡 AI chọn đáp án: {chosen}")
    letter_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(chosen, 0)
    
    opt_elements = await page.query_selector_all(".question-option")
    if len(opt_elements) > letter_idx:
        await opt_elements[letter_idx].click()
        print(f"👉 Đã chọn phương án: {chosen}")
    await asyncio.sleep(1)
    
    # Bấm TRẢ LỜI
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        print("🔘 Đã nhấn nút 'TRẢ LỜI'")
        await asyncio.sleep(2)

async def solve_part_2(page, q_num: int, data: dict):
    """Xử lý phần II: Đúng / Sai cho 4 mệnh đề a, b, c, d"""
    print(f"📝 Đề bài: {data['question'][:120]}...")
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
    print(f"💡 AI phản hồi phân tích Đúng/Sai:")
    
    answers = {}
    for part in ["a", "b", "c", "d"]:
        m = re.search(rf"{part}\)\s*(Đúng|Sai)", res, re.IGNORECASE)
        answers[part] = m.group(1).capitalize() if m else "Đúng"
        print(f"   {part}) -> {answers[part]}")
        
    # Click các label Đúng / Sai tương ứng
    labels = await page.query_selector_all(".step-content label")
    if len(labels) >= 8:
        mapping = {
            "a": 0 if answers["a"] == "Đúng" else 1,
            "b": 2 if answers["b"] == "Đúng" else 3,
            "c": 4 if answers["c"] == "Đúng" else 5,
            "d": 6 if answers["d"] == "Đúng" else 7,
        }
        for part, idx in mapping.items():
            await labels[idx].click()
            await asyncio.sleep(0.3)
        print("👉 Đã chọn toàn bộ 4 ý Đúng/Sai thành công.")
    else:
        print(f"[!] Cảnh báo: Tìm thấy {len(labels)} thẻ label, không đủ 8 thẻ.")
        
    await asyncio.sleep(1)
    # Bấm TRẢ LỜI
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        print("🔘 Đã nhấn nút 'TRẢ LỜI'")
        await asyncio.sleep(2)

async def solve_part_3(page, q_num: int, data: dict):
    """Xử lý phần III: Trả lời ngắn (điền số)"""
    print(f"📝 Đề bài: {data['question'][:150]}...")
    prompt = (
        f"{data['question']}\n\n"
        f"Yêu cầu: Giải chi tiết bài toán và đưa ra kết quả cuối cùng.\n"
        f"Quy tắc ghi đáp án: Chỉ sử dụng chữ số, dấu phẩy ',' (nếu là số thập phân) và dấu '-' (nếu là số âm).\n"
        f"Kết luận cuối cùng bằng định dạng chính xác:\n"
        f"ĐÁP ÁN: <số>"
    )
    
    res = await query_gemini(prompt)
    match = re.search(r"ĐÁP ÁN:\s*([-\d,.]+)", res)
    if match:
        raw_val = match.group(1).replace(".", ",")
    else:
        nums = re.findall(r"[-]?\d+(?:[.,]\d+)?", res)
        raw_val = nums[-1].replace(".", ",") if nums else "0"
        
    print(f"💡 AI tính ra kết quả: {raw_val}")
    ans_input = await page.query_selector("input[id^='mathplay-answer'], .step-content input[type='text']")
    if ans_input:
        await ans_input.fill(raw_val)
        print(f"👉 Đã điền vào ô đáp án: {raw_val}")
    else:
        print("[!] Không tìm thấy ô nhập đáp án.")
        
    await asyncio.sleep(1)
    # Bấm TRẢ LỜI
    tra_loi = await page.query_selector("button:has-text('TRẢ LỜI'), button:has-text('Trả lời'), .btn:has-text('TRẢ LỜI')")
    if tra_loi and await tra_loi.is_visible():
        await tra_loi.click()
        print("🔘 Đã nhấn nút 'TRẢ LỜI'")
        await asyncio.sleep(2)
    await asyncio.sleep(1)

async def main():
    print("=" * 70)
    print("🚀 HỆ THỐNG TỰ ĐỘNG GIẢI TOÁN ONLUYEN.VN BẰNG GEMINI WEB AI")
    print("=" * 70)

    browser_exe = get_browser_executable()
    print(f"[✓] Sử dụng trình duyệt: {browser_exe}")
    print(f"[✓] Profile lưu trữ: {USER_DATA_DIR}")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=browser_exe,
            headless=False,
            viewport={"width": 1366, "height": 850},
            args=["--start-maximized"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"\n[1] Mở trang bài kiểm tra: {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle")
        await asyncio.sleep(3)

        # Xử lý tự động đăng nhập nếu bị redirect
        if "login" in page.url.lower():
            print("\n[!] Phát hiện trang đăng nhập. Đang tự động điền tài khoản...")
            try:
                user_input = await page.wait_for_selector('input[placeholder*="Tên đăng nhập"], input[type="text"]', timeout=5000)
                await user_input.fill(USERNAME)
                pass_input = await page.wait_for_selector('input[type="password"]', timeout=5000)
                await pass_input.fill(PASSWORD)
                login_btn = await page.wait_for_selector('button:has-text("Đăng nhập")', timeout=5000)
                await login_btn.click()
                print("[✓] Đã gửi thông tin đăng nhập! Đang chờ vào bài...")
                await asyncio.sleep(5)
                if "/test/step/" not in page.url:
                    await page.goto(TARGET_URL, wait_until="networkidle")
            except Exception as e:
                print(f"[!] Lỗi khi tự động đăng nhập: {e}")

        print("\n[2] Đã vào phòng thi thành công! Bắt đầu quét danh sách câu hỏi...")
        await asyncio.sleep(2)

        # Quét các câu hỏi từ 1 đến 22 trong Phiếu trả lời
        # Kiểm tra xem câu nào chưa làm (chưa có class 'done')
        for q_num in range(1, 23):
            # Click vào câu hỏi
            clicked = await page.evaluate(f"""num => {{
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

            if not clicked.get("found"):
                print(f"[!] Không tìm thấy câu {q_num} trên phiếu trả lời.")
                continue

            # Nếu câu đã hoàn thành từ trước, có thể bỏ qua để tiết kiệm thời gian
            if clicked.get("isDone"):
                print(f"⏩ Câu {q_num}: Đã có đáp án từ trước -> Bỏ qua.")
                continue

            print(f"\n{'='*25} CÂU {q_num} {'='*25}")
            await asyncio.sleep(2)

            data = await page.evaluate(JS_EXTRACTOR)

            if q_num <= 12:
                # Phần I: Trắc nghiệm 4 lựa chọn
                await solve_part_1(page, q_num, data)
            elif q_num <= 16:
                # Phần II: Đúng / Sai
                await solve_part_2(page, q_num, data)
            else:
                # Phần III: Trả lời ngắn
                await solve_part_3(page, q_num, data)

            # Click nhẹ vào câu tiếp theo hoặc câu hiện tại để Onluyen lưu đáp án
            await asyncio.sleep(1.5)

        print("\n" + "=" * 70)
        print("🎉🎉🎉 ĐÃ HOÀN THÀNH TẤT CẢ 22 CÂU HỎI TRONG BÀI THI!")
        print("🚀 TIẾN HÀNH TỰ ĐỘNG BẤM NỘP BÀI TRÊN TRÌNH DUYỆT...")
        print("=" * 70)

        # Bấm nút Nộp bài trên thanh tiêu đề
        submit_btn = await page.query_selector("button:has-text('Nộp Bài'), button:has-text('Nộp bài')")
        if submit_btn:
            await submit_btn.click()
            await asyncio.sleep(2)
            
            # Bấm nút xác nhận Nộp bài trong dialog
            confirm_btn = await page.query_selector(".modal button:has-text('Nộp bài'), [role='dialog'] button:has-text('Nộp bài'), .modal button:has-text('Nộp Bài')")
            if confirm_btn:
                await confirm_btn.click()
                print("[✓] ĐÃ BẤM XÁC NHẬN NỘP BÀI THÀNH CÔNG!")
            else:
                # Tìm bất kỳ nút nộp bài nào xuất hiện
                all_submits = await page.query_selector_all("button:has-text('Nộp bài')")
                if all_submits:
                    await all_submits[-1].click()
                    print("[✓] Đã bấm xác nhận nộp bài!")
                    
            print("Đang đợi trang kết quả...")
            await asyncio.sleep(5)
            await page.screenshot(path="final_result.png")
            print("[✓] Đã chụp ảnh kết quả điểm thi vào final_result.png")
        else:
            print("[!] Không tìm thấy nút Nộp Bài.")

        # Giữ trình duyệt mở
        try:
            while True:
                await asyncio.sleep(5)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
