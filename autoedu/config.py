import os
from pathlib import Path
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Trình duyệt
USER_DATA_DIR = os.getenv("BROWSER_USER_DATA_DIR", str(Path.home() / ".onluyen-browser-profile"))
CHROME_PATH = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# Tài khoản Onluyen (Đọc từ biến môi trường, không để lộ thông tin nhạy cảm)
ONLUYEN_USERNAME = os.getenv("ONLUYEN_USERNAME", "")
ONLUYEN_PASSWORD = os.getenv("ONLUYEN_PASSWORD", "")

# Cookies Gemini Web (Đọc 100% từ biến môi trường .env)
GEMINI_COOKIES = {
    "HSID": os.getenv("GEMINI_HSID", ""),
    "SSID": os.getenv("GEMINI_SSID", ""),
    "APISID": os.getenv("GEMINI_APISID", ""),
    "SAPISID": os.getenv("GEMINI_SAPISID", ""),
    "__Secure-1PAPISID": os.getenv("GEMINI_SECURE_1PAPISID", ""),
    "__Secure-3PAPISID": os.getenv("GEMINI_SECURE_3PAPISID", ""),
    "SID": os.getenv("GEMINI_SID", ""),
    "__Secure-1PSID": os.getenv("GEMINI_SECURE_1PSID", ""),
    "__Secure-3PSID": os.getenv("GEMINI_SECURE_3PSID", ""),
    "__Secure-1PSIDTS": os.getenv("GEMINI_SECURE_1PSIDTS", ""),
    "__Secure-3PSIDTS": os.getenv("GEMINI_SECURE_3PSIDTS", ""),
    "__Secure-1PSIDCC": os.getenv("GEMINI_SECURE_1PSIDCC", ""),
    "__Secure-3PSIDCC": os.getenv("GEMINI_SECURE_3PSIDCC", ""),
    "SIDCC": os.getenv("GEMINI_SIDCC", ""),
}

# Lọc bỏ các cookie rỗng
ACTIVE_GEMINI_COOKIES = {k: v for k, v in GEMINI_COOKIES.items() if v}
