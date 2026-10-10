import asyncio
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from telegram_notifier import send_telegram_message, send_telegram_photo
from discord_notifier import (
    send_discord_message,
    send_discord_photo,
    notify_task_completed,
    notify_interrupted_or_disconnected
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# Thư mục lưu trữ và cấu hình
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"
LOG_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "nightly_solver.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

USER_DATA_DIR = os.path.expanduser("~/.onluyen-browser-profile")

def send_windows_notification(title: str, message: str):
    """Gửi thông báo Windows Toast trực tiếp không cần thư viện ngoài."""
    try:
        import subprocess
        ps_cmd = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("AutoEdu Nightly Homework")
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        """
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=10)
    except Exception as e:
        logging.warning(f"Không thể gửi Windows Notification: {e}")

async def _execute_nightly_job(headless: bool = True):
    """Tiến trình kiểm tra và tự động giải bài tập đêm."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"==================================================")
    logging.info(f"🌙 BẮT ĐẦU PHIÊN QUÉT BÀI TẬP ĐÊM: {now_str}")
    logging.info(f"==================================================")

    from autoedu.browser.context import launch_browser_context
    from autoedu.browser.navigator import auto_login_if_needed
    from autoedu.solver.runner import solve_test_url
    from autoedu.ai.gemini_web import GeminiWebClient

    ai = GeminiWebClient()
    solved_count = 0
    failed_count = 0
    solved_titles = []

    async with async_playwright() as p:
        logging.info("Khởi động trình duyệt...")
        context = await launch_browser_context(p, headless=headless)
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Tự động đồng ý mọi dialog xác nhận nộp bài
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))

        # 1. Đi tới trang danh sách bài tập
        logging.info("Truy cập trang bài tập: https://app.onluyen.vn/school/student/assignment")
        await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="networkidle")
        await asyncio.sleep(3)
        await auto_login_if_needed(page)

        # Đóng popup nếu có
        for sel in [".close", "[aria-label='Close']", "button:has-text('Đóng')", ".modal button", "img[src*='close']"]:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

        # Cuộn trang nhẹ để kích hoạt danh sách
        for _ in range(4):
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(0.3)

        # 2. Quét danh sách bài tập cần làm
        pending_items = await page.evaluate("""() => {
            const results = [];
            const rows = document.querySelectorAll('.func-info');
            rows.forEach((r, idx) => {
                const parentRow = r.closest('.task-item, .item, tr, .row, .d-flex') || r.parentElement;
                const text = parentRow ? parentRow.innerText.replace(/\\s+/g, ' ').trim() : '';
                
                // Tìm link trực tiếp nếu có
                const link = parentRow ? parentRow.querySelector('a[href*=\"test\"], [routerlink*=\"test\"], a') : null;
                const href = link ? (link.getAttribute('href') || link.getAttribute('routerlink') || '') : '';
                
                // Tiêu đề
                const titleEl = parentRow ? (parentRow.querySelector('.name, .task-name, .title, b, strong') || parentRow) : r;
                const title = titleEl ? titleEl.innerText.replace(/\\s+/g, ' ').trim() : text;

                if (text.includes('Chưa làm') || text.includes('Đang làm')) {
                    results.push({
                        index: idx,
                        title: title.split('\\n')[0],
                        fullText: text,
                        href: href
                    });
                }
            });
            return results;
        }""")

        total_pending = len(pending_items)
        logging.info(f"🔍 Phát hiện tổng số bài tập chưa hoàn thành: {total_pending}")

        if total_pending == 0:
            logging.info("✨ Không có bài tập mới nào cần làm. Hệ thống sẽ nghỉ ngơi.")
            send_windows_notification(
                "AutoEdu - Kiểm tra bài tập",
                "Không có bài tập mới nào trên Onluyen. Chúc bạn ngủ ngon!"
            )
            send_telegram_message("🌙 <b>AutoEdu Nightly Homework</b>\n\n✨ Hôm nay không có bài tập mới nào trên Onluyen.vn.\nChúc bạn ngủ ngon! 💤")
            send_discord_message(embeds=[{
                "title": "🌙 AutoEdu Nightly Homework",
                "description": "✨ Hôm nay không có bài tập mới nào trên Onluyen.vn.\nChúc bạn ngủ ngon! 💤",
                "color": 0x5865F2,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }])
            await context.close()
            return

        # 3. Lần lượt giải từng bài
        for idx, item in enumerate(pending_items, 1):
            title = item.get("title", f"Bài tập {idx}")
            href = item.get("href", "")
            logging.info(f"--------------------------------------------------")
            logging.info(f"▶️ [{idx}/{total_pending}] Bắt đầu xử lý: {title}")
            
            # Xác định URL bài thi
            target_url = None
            if href and "test" in href:
                if href.startswith("http"):
                    target_url = href
                else:
                    target_url = f"https://app.onluyen.vn{href if href.startswith('/') else '/' + href}"
            
            if not target_url:
                # Nếu không có URL trực tiếp, click vào hàng tương ứng trên trang assignment
                logging.info(f"Click vào hàng bài tập số {item['index']} để vào phòng thi...")
                try:
                    row_elements = await page.query_selector_all(".func-info")
                    if item['index'] < len(row_elements):
                        target_row = row_elements[item['index']]
                        click_target = await target_row.query_selector("button, a, i, [role='button']") or target_row
                        await click_target.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await asyncio.sleep(3)
                        target_url = page.url
                except Exception as e:
                    logging.error(f"Lỗi khi click vào bài tập: {e}")

            if not target_url or "assignment" in target_url:
                logging.warning(f"Không thể mở URL bài thi cho: {title}")
                failed_count += 1
                continue

            logging.info(f"URL bài thi: {target_url}")
            
            # Tên file ảnh lưu kết quả
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
            screenshot_path = str(RESULTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_title}")

            try:
                success = await solve_test_url(
                    page=page,
                    test_url=target_url,
                    ai_client=ai,
                    screenshot_name=screenshot_path
                )
                if success:
                    logging.info(f"✅ Hoàn thành xuất sắc: {title}")
                    solved_count += 1
                    solved_titles.append(title)
                    img_candidate = f"{screenshot_path}.png"
                    details_list = [
                        f"Môn học / Tiêu đề: {title}",
                        f"Đường dẫn bài thi: {target_url}",
                        f"Trạng thái: Đã giải trọn vẹn 100% câu hỏi và nộp bài thành công"
                    ]
                    files_list = [img_candidate] if os.path.exists(img_candidate) else None

                    notify_task_completed(
                        task_title=f"Đã giải xong: {title}",
                        task_description="Hệ thống AutoEdu đã tự động giải bài và nộp thành công lên Onluyen.vn!",
                        details=details_list,
                        files_affected=files_list,
                        photo_path=img_candidate if os.path.exists(img_candidate) else None
                    )

                    if os.path.exists(img_candidate):
                        send_telegram_photo(img_candidate, caption=f"✅ <b>Đã giải xong:</b> {title}")
                    else:
                        send_telegram_message(f"✅ <b>Đã giải xong:</b> {title}")
                else:
                    logging.warning(f"⚠️ Chưa hoàn thành trọn vẹn: {title}")
                    failed_count += 1
                    notify_interrupted_or_disconnected(
                        task_name=f"Giải bài tập: {title}",
                        reason="Không thể hoàn tất toàn bộ câu hỏi hoặc nút Nộp bài không khả dụng",
                        last_action=f"Đang làm bài tại URL: {target_url}",
                        error_message="Quá trình nộp bài hoặc nhận diện câu hỏi bị dừng trước khi hoàn tất.",
                        recovery_hint="Kiểm tra lại bài tập trên Onluyen.vn xem bài có bị khóa hoặc hết hạn nộp hay không."
                    )
            except Exception as e:
                logging.error(f"❌ Lỗi ngoại lệ khi giải {title}: {e}")
                failed_count += 1
                err_str = str(e)
                is_disconnect = any(k in err_str.lower() for k in ["connection", "timeout", "network", "disconnected", "target closed", "net::err", "closed"])
                reason_str = "Mất kết nối Internet hoặc trình duyệt bị ngắt giữa chừng" if is_disconnect else "Lỗi ngoại lệ trong quá trình tự động làm bài"
                notify_interrupted_or_disconnected(
                    task_name=f"Giải bài tập: {title}",
                    reason=reason_str,
                    last_action=f"Đang tương tác với bài tập tại URL: {target_url}",
                    error_message=err_str,
                    recovery_hint="Kiểm tra đường truyền Internet của máy chủ/máy tính hoặc khởi động lại tiến trình."
                )

            # Quay lại trang danh sách bài tập nếu còn bài tiếp theo
            if idx < total_pending:
                logging.info("Quay lại trang danh sách bài tập để làm bài tiếp theo...")
                await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="networkidle")
                await asyncio.sleep(3)

        await context.close()

    # Tổng kết
    logging.info(f"==================================================")
    logging.info(f"🎉 TỔNG KẾT PHIÊN LÀM VIỆC: Hoàn thành {solved_count}/{total_pending} bài (Lỗi: {failed_count})")
    logging.info(f"==================================================")

    notif_msg = f"Đã tự động hoàn thành {solved_count}/{total_pending} bài tập!"
    if solved_titles:
        notif_msg += f" ({', '.join(solved_titles[:2])})"
    send_windows_notification("AutoEdu - Hoàn thành bài tập", notif_msg)
    send_telegram_message(f"🎉 <b>TỔNG KẾT BÀI TẬP ĐÊM:</b>\n\n{notif_msg}")

    summary_details = [
        f"Tổng số bài tập phát hiện: {total_pending} bài",
        f"Số bài giải thành công: {solved_count} bài",
        f"Số bài gặp sự cố hoặc chưa xong: {failed_count} bài"
    ]
    if solved_titles:
        summary_details.append(f"Danh sách bài đã giải: {', '.join(solved_titles)}")

    notify_task_completed(
        task_title="Tổng kết phiên giải bài tập đêm Onluyen.vn",
        task_description=notif_msg,
        details=summary_details,
        color=0xFEE75C if failed_count > 0 else 0x57F287
    )

async def run_nightly_job(headless: bool = True):
    """Bọc tiến trình giải bài đêm với cơ chế phát hiện ngắt kết nối / crash đột ngột."""
    try:
        await _execute_nightly_job(headless=headless)
    except Exception as e:
        err_str = str(e)
        logging.error(f"🚨 TIẾN TRÌNH QUÉT BÀI BỊ GIÁN ĐOẠN ĐỘT NGỘT: {err_str}")
        is_net = any(k in err_str.lower() for k in ["connection", "timeout", "network", "disconnected", "target closed", "net::err", "refused", "offline", "dns"])
        notify_interrupted_or_disconnected(
            task_name="Tiến trình AutoEdu Nightly Solver",
            reason="Mất kết nối Internet hoặc trình duyệt bị ngắt giữa chừng" if is_net else "Sự cố crash tiến trình ngoài dự kiến",
            last_action="Đang thực hiện phiên quét bài tập đêm",
            error_message=err_str,
            recovery_hint="Kiểm tra lại kết nối mạng của máy chủ/máy tính hoặc khởi động lại tiến trình."
        )
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoEdu Nightly Homework Solver")
    parser.add_argument("--headed", action="store_true", help="Hiện cửa sổ trình duyệt (mặc định ẩn)")
    parser.add_argument("--schedule", type=str, default=None, help="Chạy dạng hẹn giờ lặp lại (ví dụ: 22:00)")
    args = parser.parse_args()

    if args.schedule:
        import time
        target_time = args.schedule
        print(f"⏰ Chế độ hẹn giờ: Đang chờ tới {target_time} hàng ngày...")
        while True:
            current_time = datetime.now().strftime("%H:%M")
            if current_time == target_time:
                print(f"\n🚀 Đã đến giờ ({target_time})! Kích hoạt tiến trình giải bài...")
                asyncio.run(run_nightly_job(headless=not args.headed))
                print(f"😴 Chờ qua phút hiện tại...")
                time.sleep(65)
            time.sleep(20)
    else:
        # Chạy ngay lập tức 1 lần
        asyncio.run(run_nightly_job(headless=not args.headed))
