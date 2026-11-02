import asyncio
import os
import sys
import json
import logging
from datetime import datetime, timezone
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

def configure_background_window():
    """
    Dam bao cua so terminal luon hien thi duoi nen de khong anh huong thao tac:
    - Dat tieu de: 'AutoEdu Onluyen Solver [Chay duoi nen]'
    - Day cua so xuong day Z-order (HWND_BOTTOM) va khong cuop focus (SWP_NOACTIVATE)
    - Thu nho xuong Taskbar khong cuop focus (SW_SHOWMINNOACTIVE = 7)
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        kernel32.SetConsoleTitleW("AutoEdu Onluyen Solver [Chay duoi nen]")
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            # HWND_BOTTOM = 1, SWP_NOSIZE = 1, SWP_NOMOVE = 2, SWP_NOACTIVATE = 0x10
            user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            # SW_SHOWMINNOACTIVE = 7
            user32.ShowWindow(hwnd, 7)
    except Exception:
        pass

configure_background_window()


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

def check_internet_connection(timeout: float = 3.0) -> bool:
    """Kiểm tra máy tính có kết nối mạng Internet hay không."""
    import socket
    targets = [
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
        ("www.google.com", 80),
        ("app.onluyen.vn", 443)
    ]
    for host, port in targets:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except (socket.timeout, OSError):
            continue
    return False

def send_windows_notification(title: str, message: str):
    """Gửi thông báo Windows Toast trực tiếp không cần thư viện ngoài (An toàn chống Command Injection)."""
    try:
        import subprocess
        ps_cmd = """
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode($env:AGY_TOAST_TITLE)) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode($env:AGY_TOAST_MSG)) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("AutoEdu Nightly Homework")
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        """
        env = os.environ.copy()
        env["AGY_TOAST_TITLE"] = str(title)
        env["AGY_TOAST_MSG"] = str(message)
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], env=env, capture_output=True, timeout=10, creationflags=creationflags)
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
    logging.info(f"⚡ AI Engine: {ai.model} (Mức tư duy: {ai.thinking_level}) - Tối ưu tốc độ giải bài Onluyen")
    solved_count = 0
    failed_count = 0
    solved_titles = []
    total_pending = 0

    async with async_playwright() as p:
        logging.info("Khởi động trình duyệt...")
        context = await launch_browser_context(p, headless=headless)
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Tự động đồng ý mọi dialog xác nhận nộp bài
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))

        # 1. Đi tới trang danh sách bài tập
        logging.info("Truy cập trang bài tập: https://app.onluyen.vn/school/student/assignment")
        await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="domcontentloaded", timeout=45000)
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

        attempted_titles = set()
        loop_counter = 0
        max_attempts = 15

        while loop_counter < max_attempts:
            loop_counter += 1

            # Cuộn trang nhẹ để kích hoạt danh sách
            for _ in range(4):
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(0.3)

            # Quét danh sách bài tập cần làm
            pending_items = await page.evaluate("""() => {
                const results = [];
                const rows = document.querySelectorAll('.func-info');
                rows.forEach((r, idx) => {
                    const parentRow = r.closest('.task-item, .item, tr, .row, .d-flex') || r.parentElement;
                    const text = parentRow ? parentRow.innerText.replace(/\\s+/g, ' ').trim() : '';
                    
                    const link = parentRow ? parentRow.querySelector('a[href*="test"], [routerlink*="test"], a') : null;
                    const href = link ? (link.getAttribute('href') || link.getAttribute('routerlink') || '') : '';
                    
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

            # Lọc ra các bài chưa được thử trong phiên này
            remaining = [it for it in pending_items if it.get("title") not in attempted_titles]

            if not remaining:
                if loop_counter == 1:
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
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }])
                else:
                    logging.info("✨ Đã hoàn thành hoặc kiểm tra hết tất cả các bài tập chưa làm!")
                break

            total_pending = len(remaining)
            item = remaining[0]
            title = item.get("title", f"Bài tập {loop_counter}")
            href = item.get("href", "")
            attempted_titles.add(title)

            logging.info(f"--------------------------------------------------")
            logging.info(f"▶️ [Bài {solved_count + failed_count + 1} / Còn {total_pending} bài chưa làm] Bắt đầu xử lý: {title}")

            # Xác định URL bài thi
            target_url = None
            if href and "test" in href:
                if href.startswith("http"):
                    target_url = href
                else:
                    target_url = f"https://app.onluyen.vn{href if href.startswith('/') else '/' + href}"

            if not target_url:
                logging.info(f"Click vào nút Làm bài của hàng bài tập '{title}' (hàng số {item['index']})...")
                try:
                    row_elements = await page.query_selector_all(".func-info")
                    if item['index'] < len(row_elements):
                        target_row = row_elements[item['index']]
                        await target_row.scroll_into_view_if_needed()
                        await asyncio.sleep(1)
                        click_target = (
                            await target_row.query_selector(".btn-func[title*='Làm bài'], .btn-func, button, a, i, [role='button']")
                            or target_row
                        )
                        await click_target.click()
                        for _ in range(12):
                            await asyncio.sleep(1)
                            if "test" in page.url:
                                break
                        target_url = page.url
                except Exception as e:
                    logging.error(f"Lỗi khi click vào bài tập: {e}")

            if not target_url or "assignment" in target_url:
                logging.warning(f"Không thể mở URL bài thi cho: {title}")
                failed_count += 1
                await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(2)
                continue

            logging.info(f"URL bài thi: {target_url}")

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

            # Luôn quay lại trang danh sách bài tập sau mỗi bài
            logging.info("Quay lại trang danh sách bài tập để kiểm tra bài tiếp theo...")
            await page.goto("https://app.onluyen.vn/school/student/assignment", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)

        await context.close()

    if solved_count == 0 and failed_count == 0:
        return

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

async def run_hourly_loop(interval_seconds: int = 3600, headless: bool = True):
    """
    Vòng lặp tự động kiểm tra bài tập mỗi 1 tiếng khi có mạng.
    - Kiểm tra kết nối Internet trước khi quét.
    - Nếu mất mạng: Chờ mạng, thăm dò mỗi 30s.
    - Ngay khi có mạng trở lại: Lập tức quét và giải bài tập Onluyen ngay để không bỏ sót!
    - Khi hoàn tất: Nghỉ 1 tiếng (3600s) cho chu kỳ tiếp theo.
    """
    logging.info("=" * 60)
    logging.info(f"🔄 KHỞI ĐỘNG CHẾ ĐỘ GIÁM SÁT BÀI TẬP (MỖI {interval_seconds // 60} PHÚT / TỰ ĐỘNG KHI CÓ MẠNG)")
    logging.info("=" * 60)
    
    was_offline = False
    
    while True:
        # 1. Kiểm tra mạng
        online = check_internet_connection()
        if not online:
            if not was_offline:
                logging.warning("⚠️ [OFFLINE] Hiện không có kết nối Internet. Tạm dừng và chờ kết nối mạng...")
                was_offline = True
            await asyncio.sleep(30)
            continue
        
        if was_offline:
            logging.info("🌐 [ONLINE] Đã phát hiện mạng Internet trở lại! Lập tức quét bài tập để không bỏ sót...")
            was_offline = False
        else:
            logging.info("🌐 [ONLINE] Kết nối Internet ổn định. Bắt đầu phiên quét bài tập Onluyen.vn...")
            
        # 2. Chạy phiên giải bài tập
        try:
            await run_nightly_job(headless=headless)
        except Exception as e:
            logging.error(f"Lỗi trong phiên làm việc: {e}")
            
        # 3. Chờ chu kỳ tiếp theo (chia nhỏ 15s để phản ứng nhanh nếu mạng bị ngắt)
        logging.info(f"😴 Phiên quét hoàn tất. Hệ thống sẽ nghỉ ngơi {interval_seconds // 60} phút trước phiên tiếp theo...")
        elapsed = 0
        while elapsed < interval_seconds:
            await asyncio.sleep(min(15, interval_seconds - elapsed))
            elapsed += 15
            # Nếu trong lúc ngủ bị ngắt mạng, ghi nhận để khi có mạng lại quét ngay
            if not check_internet_connection():
                logging.warning("⚠️ Mất mạng trong thời gian chờ. Chuyển sang chế độ theo dõi mạng...")
                was_offline = True
                break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoEdu Hourly Homework Solver")
    parser.add_argument("--headed", action="store_true", help="Hiện cửa sổ trình duyệt (mặc định ẩn)")
    parser.add_argument("--once", action="store_true", help="Chỉ chạy quét 1 lần duy nhất rồi thoát")
    parser.add_argument("--interval", type=int, default=3600, help="Thời gian giãn cách giữa các lần quét (mặc định 3600 giây = 1 tiếng)")
    parser.add_argument("--schedule", type=str, default=None, help="Chạy dạng hẹn giờ lặp lại hàng ngày (ví dụ: 22:00)")
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
    elif args.once:
        # Chạy ngay lập tức 1 lần
        if not check_internet_connection():
            logging.error("❌ Không có kết nối mạng Internet. Không thể chạy phiên giải bài.")
            sys.exit(1)
        asyncio.run(run_nightly_job(headless=not args.headed))
    else:
        # Mặc định: Chế độ giám sát định kỳ mỗi 1 tiếng khi có mạng
        asyncio.run(run_hourly_loop(interval_seconds=args.interval, headless=not args.headed))
