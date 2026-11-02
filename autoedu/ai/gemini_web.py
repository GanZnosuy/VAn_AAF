import asyncio
import json
import re
import sys
import os
from typing import Optional
from curl_cffi.requests import AsyncSession
from autoedu.config import (
    ACTIVE_GEMINI_COOKIES,
    GEMINI_API_KEY,
    DEFAULT_MODEL,
    DEFAULT_THINKING_LEVEL,
    ANTIGRAVITY_GATEWAY_URL
)

INIT_ENDPOINT = "https://gemini.google.com/app"
GENERATE_ENDPOINT = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
DISCONNECTED_MESSAGE = "Chưa kết nối (Không thể kết nối đến Gemini Web AI. Vui lòng kiểm tra cookies hoặc kết nối mạng)."

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
    - Chế độ 1 (Khuyên dùng): Antigravity Tools Gateway (http://127.0.0.1:8045) với cụm 5 tài khoản PRO tự động đảo acc khi hết quota
    - Chế độ 2: Gemini Web Cookie (miễn phí 100%, không cần API key)
    - Chế độ 3: Gemini API Key từ Google AI Studio (fallback)
    """
    def __init__(
        self,
        cookies: Optional[dict] = None,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        thinking_level: str = DEFAULT_THINKING_LEVEL,
        proxy_url: str = ANTIGRAVITY_GATEWAY_URL
    ):
        self.cookies = cookies or ACTIVE_GEMINI_COOKIES
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model
        # Luôn đảm bảo gemini-3.8-flash và argon ở mức tư duy "high" theo yêu cầu người dùng
        if "3.8" in self.model or "argon" in self.model:
            self.thinking_level = "high"
        else:
            self.thinking_level = thinking_level
        self.proxy_url = proxy_url
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

    async def _query_antigravity_tools(self, prompt: str) -> str:
        """Truy vấn thông qua Antigravity Tools Gateway (cụm 5 tài khoản PRO tự động đảo acc)."""
        chat_url = f"{self.proxy_url.rstrip('/')}/chat/completions"
        if "argon" in self.model:
            models_to_try = ["gemini-4-argon", "gemini-4-argon-high", "gemini-3.8-flash", "gemini-3.8-flash-high"]
        elif "3.8" in self.model:
            models_to_try = ["gemini-3.8-flash", "gemini-3.8-flash-high", "gemini-3.8-flash-low", "gemini-4-argon"]
        elif "high" not in self.model:
            models_to_try = [self.model, f"{self.model}-high", "gemini-3.8-flash", "gemini-4-argon"]
        else:
            models_to_try = [self.model, "gemini-3.8-flash", "gemini-4-argon"]

        thinking_lvl = "high" if ("3.8" in self.model or "argon" in self.model or self.thinking_level == "high") else self.thinking_level

        for m in models_to_try:
            payload = {
                "model": m,
                "messages": [{"role": "user", "content": prompt}],
                "thinking": {"level": thinking_lvl}
            }
            try:
                async with AsyncSession() as s:
                    res = await s.post(chat_url, json=payload, timeout=40)
                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices and "message" in choices[0]:
                            text = choices[0]["message"].get("content", "").strip()
                            if text:
                                return text
            except Exception:
                continue
        return ""

    async def _query_api_key(self, prompt: str) -> str:
        """Fallback qua Google AI Studio API Key với mô hình Argon / 3.8 mức tư duy cao (High)."""
        if "argon" in self.model:
            models = ["gemini-2.5-pro", "gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        else:
            models = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

        thinking_lvl = "high" if ("3.8" in self.model or "argon" in self.model or self.thinking_level == "high") else self.thinking_level

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "thinking_config": {
                        "thinking_level": thinking_lvl
                    }
                }
            }
            try:
                async with AsyncSession() as s:
                    res = await s.post(url, json=payload, timeout=35)
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
        """Gửi prompt tới Gemini và nhận phản hồi văn bản với mức tư duy cao (high)."""
        # 1. Ưu tiên: Antigravity Tools Gateway cục bộ (tự động đảo tài khoản giữa 5 tài khoản PRO khi hết quota)
        try:
            res_proxy = await self._query_antigravity_tools(prompt)
            if res_proxy:
                return res_proxy
        except Exception:
            pass

        # 2. Chế độ Gemini Web Cookie (nếu có cookie cấu hình)
        if self.cookies:
            for attempt in range(max_retries):
                try:
                    async with AsyncSession(headers=HEADERS, cookies=self.cookies, impersonate="chrome120") as s:
                        token = await self.get_token(s)
                        if not token:
                            self.cached_token = None
                            await asyncio.sleep(1.5)
                            continue

                        # Payload với cờ extended thinking (mức cao = 2)
                        inner_req = [None] * 81
                        inner_req[0] = [[[prompt, 0, None, None, None, None, 0]]]
                        inner_req[1] = ["vi"]
                        inner_req[6] = [1]
                        inner_req[10] = 1
                        inner_req[79] = 1
                        # Luôn để thinking level high (2) cho 3.8 flash và argon
                        inner_req[80] = 2 if (self.thinking_level == "high" or "3.8" in self.model or "argon" in self.model) else 1

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

        # 3. Fallback qua Google AI Studio API Key
        if self.api_key:
            res = await self._query_api_key(prompt)
            if res:
                return res

        # 4. Nếu không kết nối được qua bất kỳ kênh nào, thông báo chưa kết nối rõ ràng
        return DISCONNECTED_MESSAGE
