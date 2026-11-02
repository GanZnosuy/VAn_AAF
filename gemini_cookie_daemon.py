"""
GEMINI UNIVERSAL COOKIE ROTATION & SYNC DAEMON
================================================
Tự động làm mới Cookies Google Gemini Web API mỗi 1 giờ (3600 giây)
và đồng bộ tức thì đến TẤT CẢ các dự án & ứng dụng trên hệ thống:
1. Argon agennt (NEXUS Agent & MCP Server - 3 tài khoản luân phiên)
2. CAIDATHETTHONG (AutoEdu, Browser-Use Adapter, Discord Controller)
3. C:\\Users\\vuong\\.gemini\\config\\gemini_cookies.json (Global config)
4. germini (test_gemini.py)
"""

import os
import sys
import re
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from curl_cffi.requests import AsyncSession
from gemini_webapi.constants import Endpoint, Headers

# File Paths
CAIDA_DIR = Path(r"c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG")
CAIDA_ENV = CAIDA_DIR / ".env"
GLOBAL_COOKIE_JSON = Path(os.path.expanduser(r"~/.gemini/config/gemini_cookies.json"))
ARGON_DIR = Path(r"c:\Users\vuong\OneDrive\Desktop\Argon agennt")
ARGON_ENV = ARGON_DIR / ".env"
ARGON_COOKIES_TXT = ARGON_DIR / "cookies.txt"
GERMINI_TEST = Path(r"c:\Users\vuong\OneDrive\Desktop\germini\test_gemini.py")
LOG_FILE = CAIDA_DIR / "gemini_cookie_sync.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GeminiCookieDaemon")


async def rotate_cookies(psid: str, psidts: str) -> Optional[Dict[str, str]]:
    """Gửi yêu cầu xoay vòng token tới Google rotation endpoint."""
    if not psid:
        return None

    headers = Headers.ROTATE_COOKIES.value.copy()
    cookies = {"__Secure-1PSID": psid}
    if psidts:
        cookies["__Secure-1PSIDTS"] = psidts

    for attempt in range(3):
        try:
            async with AsyncSession(cookies=cookies, impersonate="chrome120") as s:
                res = await s.post(
                    Endpoint.ROTATE_COOKIES,
                    headers=headers,
                    data='[000,"-0000000000000000000"]',
                    timeout=20
                )
                if res.status_code == 200:
                    new_cookies = dict(s.cookies)
                    new_ts = new_cookies.get("__Secure-1PSIDTS", psidts)
                    new_cc = new_cookies.get("__Secure-1PSIDCC", "")
                    return {
                        "psid": psid,
                        "psidts": new_ts,
                        "psidcc": new_cc
                    }
                elif res.status_code == 401:
                    logger.warning(f"Lỗi 401: Cookie không còn hiệu lực hoặc đã bị thu hồi.")
                    return None
                else:
                    logger.warning(f"Thử {attempt+1}/3: Rotation endpoint trả về {res.status_code}")
        except Exception as e:
            logger.warning(f"Thử {attempt+1}/3 thất bại: {e}")
        await asyncio.sleep(2)
    return None


def read_argon_env_accounts() -> Dict[int, Dict[str, str]]:
    """Đọc thông tin 3 tài khoản từ Argon agennt/.env."""
    accounts = {}
    if not ARGON_ENV.exists():
        return accounts

    try:
        content = ARGON_ENV.read_text(encoding="utf-8", errors="replace")
        for idx in (1, 2, 3, 4, 5):
            psid_match = re.search(rf"^ACCOUNT{idx}_SECURE_1PSID\s*=\s*[\"']?(.*?)[\"']?\s*$", content, re.MULTILINE)
            psidts_match = re.search(rf"^ACCOUNT{idx}_SECURE_1PSIDTS\s*=\s*[\"']?(.*?)[\"']?\s*$", content, re.MULTILINE)
            if psid_match and psid_match.group(1).strip():
                accounts[idx] = {
                    "psid": psid_match.group(1).strip(),
                    "psidts": psidts_match.group(1).strip() if psidts_match else ""
                }
    except Exception as e:
        logger.error(f"Lỗi đọc {ARGON_ENV}: {e}")
    return accounts


def update_argon_env(account_idx: int, psid: str, psidts: str):
    """Cập nhật cookie tài khoản vào Argon agennt/.env."""
    if not ARGON_ENV.exists():
        return

    try:
        content = ARGON_ENV.read_text(encoding="utf-8", errors="replace")
        psid_key = f"ACCOUNT{account_idx}_SECURE_1PSID"
        psidts_key = f"ACCOUNT{account_idx}_SECURE_1PSIDTS"

        if re.search(rf"^{psid_key}\s*=", content, flags=re.MULTILINE):
            content = re.sub(rf"^{psid_key}\s*=.*$", f'{psid_key}="{psid}"', content, flags=re.MULTILINE)
        else:
            content += f'\n{psid_key}="{psid}"'

        if re.search(rf"^{psidts_key}\s*=", content, flags=re.MULTILINE):
            content = re.sub(rf"^{psidts_key}\s*=.*$", f'{psidts_key}="{psidts}"', content, flags=re.MULTILINE)
        else:
            content += f'\n{psidts_key}="{psidts}"'

        ARGON_ENV.write_text(content, encoding="utf-8")
        logger.info(f"✓ Đã cập nhật Argon agennt/.env (ACCOUNT{account_idx})")
    except Exception as e:
        logger.error(f"Lỗi ghi {ARGON_ENV}: {e}")


def update_argon_cookies_txt(psid: str, psidts: str, psidcc: str = ""):
    """Cập nhật bản ghi cookie vào Argon agennt/cookies.txt."""
    if not ARGON_COOKIES_TXT.exists():
        return

    try:
        lines = ARGON_COOKIES_TXT.read_text(encoding="utf-8", errors="replace").splitlines(True)
        new_lines = []
        skip_names = {"__Secure-1PSID", "__Secure-1PSIDTS", "__Secure-1PSIDCC"}

        for line in lines:
            if line.startswith("#") or not line.strip():
                new_lines.append(line)
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 7 and parts[5] in skip_names:
                continue
            new_lines.append(line)

        expiry = str(int(time.time()) + 31536000)
        new_lines.append(f".google.com\tTRUE\t/\tTRUE\t{expiry}\t__Secure-1PSID\t{psid}\n")
        new_lines.append(f".google.com\tTRUE\t/\tTRUE\t{expiry}\t__Secure-1PSIDTS\t{psidts}\n")
        if psidcc:
            new_lines.append(f".google.com\tTRUE\t/\tTRUE\t{expiry}\t__Secure-1PSIDCC\t{psidcc}\n")

        ARGON_COOKIES_TXT.write_text("".join(new_lines), encoding="utf-8")
        logger.info(f"✓ Đã cập nhật Argon agennt/cookies.txt")
    except Exception as e:
        logger.error(f"Lỗi ghi {ARGON_COOKIES_TXT}: {e}")


def update_caida_env(psid: str, psidts: str, psidcc: str = ""):
    """Đồng bộ cookie vào CAIDATHETTHONG/.env."""
    if not CAIDA_ENV.exists():
        return

    try:
        content = CAIDA_ENV.read_text(encoding="utf-8", errors="replace")

        def set_key(key: str, val: str):
            nonlocal content
            if re.search(rf"^{key}\s*=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{key}\s*=.*$", f'{key}={val}', content, flags=re.MULTILINE)
            else:
                content += f"\n{key}={val}"

        set_key("GEMINI_SECURE_1PSID", psid)
        set_key("GEMINI_SECURE_1PSIDTS", psidts)
        if psidcc:
            set_key("GEMINI_SECURE_1PSIDCC", psidcc)

        CAIDA_ENV.write_text(content, encoding="utf-8")
        logger.info(f"✓ Đã cập nhật CAIDATHETTHONG/.env")
    except Exception as e:
        logger.error(f"Lỗi ghi {CAIDA_ENV}: {e}")


def update_global_json(psid: str, psidts: str, psidcc: str = ""):
    """Đồng bộ cookie vào ~/.gemini/config/gemini_cookies.json."""
    try:
        GLOBAL_COOKIE_JSON.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "GEMINI_SECURE_1PSID": psid,
            "GEMINI_SECURE_1PSIDTS": psidts,
            "GEMINI_SECURE_1PSIDCC": psidcc
        }
        GLOBAL_COOKIE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"✓ Đã cập nhật global config: {GLOBAL_COOKIE_JSON}")
    except Exception as e:
        logger.error(f"Lỗi ghi {GLOBAL_COOKIE_JSON}: {e}")


def update_germini_test(psid: str, psidts: str):
    """Đồng bộ cookie vào Desktop/germini/test_gemini.py."""
    if not GERMINI_TEST.exists():
        return

    try:
        content = GERMINI_TEST.read_text(encoding="utf-8", errors="replace")
        content = re.sub(r'^SECURE_1PSID\s*=.*$', f'SECURE_1PSID = "{psid}"', content, flags=re.MULTILINE)
        content = re.sub(r'^SECURE_1PSIDTS\s*=.*$', f'SECURE_1PSIDTS = "{psidts}"', content, flags=re.MULTILINE)
        GERMINI_TEST.write_text(content, encoding="utf-8")
        logger.info(f"✓ Đã cập nhật Desktop/germini/test_gemini.py")
    except Exception as e:
        logger.error(f"Lỗi ghi {GERMINI_TEST}: {e}")


async def sync_all_accounts():
    """Làm mới toàn bộ cookies cho 3 tài khoản và đồng bộ đến tất cả các file cấu hình."""
    logger.info("==================================================")
    logger.info("Bắt đầu chu trình làm mới cookies Google Gemini Web...")
    accounts = read_argon_env_accounts()
    if not accounts:
        logger.error("Không tìm thấy tài khoản nào trong Argon agennt/.env!")
        return False

    refreshed_accounts = {}

    for idx, acc in accounts.items():
        psid = acc["psid"]
        psidts = acc["psidts"]
        logger.info(f"Đang làm mới token cho Tài khoản {idx}...")
        res = await rotate_cookies(psid, psidts)
        if res:
            logger.info(f"✓ Làm mới token Tài khoản {idx} THÀNH CÔNG!")
            update_argon_env(idx, res["psid"], res["psidts"])
            refreshed_accounts[idx] = res
            if idx == 1:
                refreshed_primary = res
                update_argon_cookies_txt(res["psid"], res["psidts"], res["psidcc"])
        else:
            logger.warning(f"⚠️ Làm mới token Tài khoản {idx} không thành công.")

    # Lưu pool toàn bộ các tài khoản sống ra gemini_cookies_pool.json
    pool_file = Path(os.path.expanduser(r"~/.gemini/config/gemini_cookies_pool.json"))
    try:
        pool_file.parent.mkdir(parents=True, exist_ok=True)
        pool_data = {
            "updated_at": int(time.time()),
            "accounts": [
                {"account_index": k, **v} for k, v in refreshed_accounts.items()
            ]
        }
        pool_file.write_text(json.dumps(pool_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"✓ Đã cập nhật pool đa tài khoản: {pool_file} ({len(refreshed_accounts)} tài khoản sống)")
    except Exception as e:
        logger.error(f"Lỗi lưu {pool_file}: {e}")

    # Ưu tiên tài khoản chính, nếu tài khoản chính lỗi thì lấy tài khoản sống đầu tiên
    target = refreshed_primary
    if not target and refreshed_accounts:
        first_live_idx = sorted(refreshed_accounts.keys())[0]
        target = refreshed_accounts[first_live_idx]
        logger.info(f"Tài khoản 1 không khả dụng, tự động chuyển tài khoản mặc định sang Tài khoản {first_live_idx}")
    elif not target:
        for idx in sorted(accounts.keys()):
            target = accounts[idx]
            break

    if target:
        psid = target.get("psid", "")
        psidts = target.get("psidts", "")
        psidcc = target.get("psidcc", "")
        logger.info(f"Đang đồng bộ cookies tài khoản hoạt động sang CAIDATHETTHONG & Global...")
        update_caida_env(psid, psidts, psidcc)
        update_global_json(psid, psidts, psidcc)
        update_germini_test(psid, psidts)
        logger.info("✓ Hoàn tất đồng bộ toàn diện trên mọi ứng dụng!")
        return True
    return False


async def run_daemon(interval_seconds: int = 3600):
    """Chạy vòng lặp định kỳ mỗi 1 giờ (3600 giây)."""
    logger.info(f"🚀 Gemini Cookie Daemon đã khởi động (chu kỳ: {interval_seconds}s / 1 giờ).")
    while True:
        try:
            await sync_all_accounts()
        except Exception as e:
            logger.error(f"Lỗi trong chu trình sync: {e}")
        logger.info(f"Đang chờ {interval_seconds}s trước lần cập nhật tiếp theo...")
        await asyncio.sleep(interval_seconds)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gemini Cookie Sync Daemon")
    parser.add_argument("--once", action="store_true", help="Chạy 1 lần rồi thoát (dành cho Task Scheduler)")
    parser.add_argument("--daemon", action="store_true", help="Chạy nền liên tục mỗi 1 giờ")
    parser.add_argument("--interval", type=int, default=3600, help="Khoảng thời gian lặp (giây), mặc định 3600s = 1h")
    args = parser.parse_args()

    if args.once:
        success = asyncio.run(sync_all_accounts())
        sys.exit(0 if success else 1)
    else:
        asyncio.run(run_daemon(interval_seconds=args.interval))


if __name__ == "__main__":
    main()
