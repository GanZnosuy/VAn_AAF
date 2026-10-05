import asyncio
import json
import re
import sys
import os
from typing import Optional
from curl_cffi.requests import AsyncSession
from autoedu.config import ACTIVE_GEMINI_COOKIES, GEMINI_API_KEY

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
    Client giao tiếp trực tiếp với Gemini AI:
    - Chế độ 1 (Khuyên dùng): Gemini Web Cookie (miễn phí 100%, không cần API key)
    - Chế độ 2: Gemini API Key miễn phí (Google AI Studio)
    - Chế độ 3: Chế độ Dùng Thử 1 lần (Free Trial Bridge) cho AI Coding Agents (Cline, Antigravity, OpenCode)
    """
    def __init__(self, cookies: Optional[dict] = None, api_key: Optional[str] = None):
        self.cookies = cookies or ACTIVE_GEMINI_COOKIES
        self.api_key = api_key or GEMINI_API_KEY
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

    async def _query_api_key(self, prompt: str) -> str:
        """Fallback qua Google AI Studio API Key nếu được cấu hình."""
        models = ["gemini-2.0-flash", "gemini-1.5-flash"]
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2}
            }
            try:
                async with AsyncSession() as s:
                    res = await s.post(url, json=payload, timeout=30)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
            except Exception:
                continue
        return ""

    async def query(self, prompt: str, max_retries: int = 3, timeout: int = 35) -> str:
        """Gửi prompt tới Gemini và nhận phản hồi văn bản."""
        # 1. Nếu có Cookies, ưu tiên sử dụng Gemini Web
        if self.cookies:
            for attempt in range(max_retries):
                try:
                    async with AsyncSession(headers=HEADERS, cookies=self.cookies, impersonate="chrome120") as s:
                        token = await self.get_token(s)
                        if not token:
                            self.cached_token = None
                            await asyncio.sleep(1.5)
                            continue

                        post_data = {
                            "at": token,
                            "f.req": json.dumps([None, json.dumps([[prompt], None, None])])
                        }

                        res = await s.post(GENERATE_ENDPOINT, data=post_data, timeout=timeout)
                        if res.status_code != 200:
                            self.cached_token = None
                            await asyncio.sleep(1.5)
                            continue

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
                except Exception:
                    self.cached_token = None
                    await asyncio.sleep(1.5)

        # 2. Fallback nếu có API Key
        if self.api_key:
            res = await self._query_api_key(prompt)
            if res:
                return res

        return ""
