import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Tải cấu hình từ .env trong thư mục CAIDATHETTHONG
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Trình duyệt
USER_DATA_DIR = os.getenv("BROWSER_USER_DATA_DIR", str(Path.home() / ".onluyen-browser-profile"))
CHROME_PATH = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# Tài khoản Onluyen (Đọc từ biến môi trường)
ONLUYEN_USERNAME = os.getenv("ONLUYEN_USERNAME", "")
ONLUYEN_PASSWORD = os.getenv("ONLUYEN_PASSWORD", "")

# Cấu hình AI Model & Gateway
DEFAULT_MODEL = os.getenv("AUTOEDU_MODEL", "gemini-3.8-flash")
DEFAULT_THINKING_LEVEL = os.getenv("AUTOEDU_THINKING_LEVEL", "high")
ANTIGRAVITY_GATEWAY_URL = os.getenv("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:8045/v1")

# Cookies Gemini Web (Đọc từ .env, fallback sang gemini_cookies.json và Argon agennt/.env)
def load_all_gemini_cookies():
    cookies = {
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
    
    # Fallback 1: C:\Users\vuong\.gemini\config\gemini_cookies.json
    global_cfg = Path.home() / ".gemini" / "config" / "gemini_cookies.json"
    if (not cookies.get("__Secure-1PSID") or not cookies.get("__Secure-1PSIDTS")) and global_cfg.exists():
        try:
            with open(global_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not cookies.get("__Secure-1PSID"):
                    cookies["__Secure-1PSID"] = data.get("__Secure-1PSID", "")
                if not cookies.get("__Secure-1PSIDTS"):
                    cookies["__Secure-1PSIDTS"] = data.get("__Secure-1PSIDTS", "")
                if not cookies.get("__Secure-1PSIDCC"):
                    cookies["__Secure-1PSIDCC"] = data.get("__Secure-1PSIDCC", "")
        except Exception:
            pass

    # Fallback 2: Argon agennt/.env
    argon_env = Path.home() / "OneDrive" / "Desktop" / "Argon agennt" / ".env"
    if (not cookies.get("__Secure-1PSID") or not cookies.get("__Secure-1PSIDTS")) and argon_env.exists():
        try:
            from dotenv import dotenv_values
            av = dotenv_values(argon_env)
            # Thử từ account active hoặc account 5, 1, 2, 3
            for i in [5, 1, 2, 3, 4]:
                p = av.get(f"ACCOUNT{i}_SECURE_1PSID", "")
                ts = av.get(f"ACCOUNT{i}_SECURE_1PSIDTS", "")
                if p and ts:
                    if not cookies.get("__Secure-1PSID"):
                        cookies["__Secure-1PSID"] = p
                    if not cookies.get("__Secure-1PSIDTS"):
                        cookies["__Secure-1PSIDTS"] = ts
                    break
        except Exception:
            pass

    return {k: v for k, v in cookies.items() if v}

GEMINI_COOKIES = load_all_gemini_cookies()
ACTIVE_GEMINI_COOKIES = GEMINI_COOKIES

# (Tùy chọn) API Key miễn phí từ Google AI Studio (fallback nếu không dùng cookie)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

