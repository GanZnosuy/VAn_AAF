import os
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext
from autoedu.config import USER_DATA_DIR, CHROME_PATH

def get_browser_executable() -> Optional[str]:
    """Tìm đường dẫn tệp thực thi Google Chrome trên hệ thống."""
    candidates = [
        CHROME_PATH,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

async def launch_browser_context(playwright_instance, headless: bool = False) -> BrowserContext:
    """Khởi tạo Chromium persistent context để duy trì phiên đăng nhập."""
    browser_exe = get_browser_executable()
    launch_kwargs = {
        "user_data_dir": USER_DATA_DIR,
        "headless": headless,
        "viewport": {"width": 1366, "height": 850},
        "args": ["--start-maximized", "--disable-blink-features=AutomationControlled"]
    }
    if browser_exe:
        launch_kwargs["executable_path"] = browser_exe

    return await playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
