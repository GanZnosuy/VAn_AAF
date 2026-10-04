import asyncio
import json
import re
import sys
from typing import Optional
from curl_cffi.requests import AsyncSession
from autoedu.config import ACTIVE_GEMINI_COOKIES

INIT_ENDPOINT = "https://gemini.google.com/app"
GENERATE_ENDPOINT = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"

HEADERS = {
    "host": "gemini.google.com",
    "x-same-domain": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    "origin": "https://gemini.google.com",
    "referer": "https://gemini.google.com/",
}

class GeminiWebClient:
    """
    Client giao tiếp trực tiếp với Gemini Web API (miễn phí, không tốn token API).
    Tự động xử lý đăng nhập qua Cookie và giải mã token động từ WIZ_global_data.
    """
    def __init__(self, cookies: Optional[dict] = None):
        self.cookies = cookies or ACTIVE_GEMINI_COOKIES
        self.cached_token: Optional[str] = None

    async def get_token(self, session: AsyncSession) -> str:
        """Trích xuất token CSRF/xsrf (SNlM0e / thykhd / AFWL...) từ HTML của Gemini Web."""
        if self.cached_token:
            return self.cached_token

        r = await session.get(INIT_ENDPOINT)
        # 1. Tìm trong window.WIZ_global_data
        wiz_match = re.findall(r"window\.WIZ_global_data\s*=\s*(\{.*?\});", r.text)
        if wiz_match:
            try:
                wiz = json.loads(wiz_match[0])
                # Cập nhật theo kiến trúc mới của Google (thykhd hoặc SNlM0e hoặc token bắt đầu bằng AFWL)
                token = wiz.get("SNlM0e") or wiz.get("thykhd")
                if not token:
                    for v in wiz.values():
                        if isinstance(v, str) and v.startswith("AFWL"):
                            token = v
                            break
                if token:
                    self.cached_token = token
                    return token
            except Exception:
                pass

        # 2. Regex fallback trực tiếp
        m = re.search(r'"SNlM0e":"(.*?)"', r.text)
        if m:
            self.cached_token = m.group(1)
            return self.cached_token

        return ""

    async def query(self, prompt: str, max_retries: int = 3, timeout: int = 35) -> str:
        """Gửi prompt tới Gemini Web và nhận phản hồi văn bản."""
        for attempt in range(max_retries):
            try:
                async with AsyncSession(headers=HEADERS, cookies=self.cookies, impersonate="chrome120") as s:
                    token = await self.get_token(s)
                    if not token:
                        self.cached_token = None
                        await asyncio.sleep(2)
                        continue

                    post_data = {
                        "at": token,
                        "f.req": json.dumps([None, json.dumps([[prompt], None, None])])
                    }

                    res = await s.post(GENERATE_ENDPOINT, data=post_data, timeout=timeout)
                    if res.status_code != 200:
                        self.cached_token = None
                        await asyncio.sleep(2)
                        continue

                    # Bóc tách câu trả lời từ luồng dữ liệu trả về của Google
                    raw_text = ""
                    for line in res.text.split("\n"):
                        if line.startswith("[["):
                            try:
                                data = json.loads(line)
                                for item in data:
                                    if isinstance(item, list) and len(item) > 2 and isinstance(item[2], str):
                                        inner_body = json.loads(item[2])
                                        if isinstance(inner_body, list) and len(inner_body) > 4 and inner_body[4]:
                                            candidate_text = inner_body[4][0][1][0]
                                            if len(candidate_text) > len(raw_text):
                                                raw_text = candidate_text
                            except Exception:
                                pass

                    if raw_text:
                        return raw_text.strip()
                    else:
                        self.cached_token = None
            except Exception as e:
                self.cached_token = None
                await asyncio.sleep(2)

        return ""
