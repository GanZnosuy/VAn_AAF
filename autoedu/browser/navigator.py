import asyncio
import re
from typing import List, Dict
from playwright.async_api import Page
from autoedu.config import ONLUYEN_USERNAME, ONLUYEN_PASSWORD

async def auto_login_if_needed(page: Page) -> bool:
    """Tự động điền tài khoản nếu phát hiện trang đăng nhập."""
    if "login" in page.url.lower():
        if not (ONLUYEN_USERNAME and ONLUYEN_PASSWORD):
            return False
        try:
            user_input = await page.wait_for_selector('input[placeholder*="Tên đăng nhập"], input[type="text"]', timeout=4000)
            if user_input:
                await user_input.fill(ONLUYEN_USERNAME)
                pass_input = await page.wait_for_selector('input[type="password"]', timeout=4000)
                await pass_input.fill(ONLUYEN_PASSWORD)
                login_btn = await page.wait_for_selector('button:has-text("Đăng nhập")', timeout=4000)
                await login_btn.click()
                await asyncio.sleep(4)
                return True
        except Exception:
            pass
    return False

async def scan_assignments(page: Page) -> List[Dict[str, str]]:
    """Quét toàn bộ bài tập cần làm trong mục Bài tập."""
    await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="networkidle")
    await asyncio.sleep(2)
    await auto_login_if_needed(page)

    # Cuộn trang để tải dữ liệu
    for _ in range(4):
        await page.mouse.wheel(0, 800)
        await asyncio.sleep(0.4)

    raw_items = await page.evaluate("""() => {
        const results = [];
        const rows = document.querySelectorAll('.func-info');
        rows.forEach(r => {
            const parentRow = r.closest('.task-item, .item, tr, .row, .d-flex') || r.parentElement;
            
            // Tìm tên môn học (12A1 - ...)
            let subject = '';
            let curr = parentRow;
            while (curr && curr !== document.body) {
                const header = curr.querySelector('.header, .title, .subject-name, h4, h5, h6, .badge');
                if (header && header.innerText.includes('12A1')) {
                    subject = header.innerText.trim();
                    break;
                }
                curr = curr.parentElement;
            }

            const text = parentRow.innerText ? parentRow.innerText.replace(/\\s+/g, ' ').trim() : '';
            const link = parentRow.querySelector('a, [routerlink]');
            const href = link ? (link.getAttribute('href') || '') : '';

            if (text.includes('Chưa làm') || text.includes('Đang làm')) {
                results.push({
                    subject: subject,
                    text: text,
                    href: href
                });
            }
        });
        return results;
    }""")

    return raw_items
