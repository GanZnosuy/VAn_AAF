import asyncio
import json
import os
import re
from typing import Any, Optional, TypeVar
from pydantic import BaseModel, ValidationError
from curl_cffi.requests import AsyncSession
from gemini_webapi.constants import Endpoint, Headers
from browser_use.llm.base import BaseChatModel, ChatInvokeCompletion
from langchain_core.messages import BaseMessage

T = TypeVar("T", bound=BaseModel)

GLOBAL_COOKIE_PATH = os.path.expanduser(r"~/.gemini/config/gemini_cookies.json")

def load_global_cookies() -> dict[str, str]:
    """Tự động nạp cookie từ biến môi trường hoặc file cấu hình toàn cục."""
    cookies = {}
    psid = os.getenv("GEMINI_SECURE_1PSID")
    psidts = os.getenv("GEMINI_SECURE_1PSIDTS")
    psidcc = os.getenv("GEMINI_SECURE_1PSIDCC")

    if psid and psidts:
        cookies["__Secure-1PSID"] = psid
        cookies["__Secure-1PSIDTS"] = psidts
        if psidcc:
            cookies["__Secure-1PSIDCC"] = psidcc
        return cookies

    if os.path.isfile(GLOBAL_COOKIE_PATH):
        try:
            with open(GLOBAL_COOKIE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("GEMINI_SECURE_1PSID") and data.get("GEMINI_SECURE_1PSIDTS"):
                    cookies["__Secure-1PSID"] = data["GEMINI_SECURE_1PSID"]
                    cookies["__Secure-1PSIDTS"] = data["GEMINI_SECURE_1PSIDTS"]
                    if data.get("GEMINI_SECURE_1PSIDCC"):
                        cookies["__Secure-1PSIDCC"] = data["GEMINI_SECURE_1PSIDCC"]
                    return cookies
        except Exception:
            pass

    return cookies

def get_browser_executable() -> str | None:
    """Tự động tìm đường dẫn Chrome/Chromium trên máy Windows."""
    # 1. Ưu tiên Playwright Chromium
    playwright_dir = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
    if os.path.isdir(playwright_dir):
        for root, dirs, files in os.walk(playwright_dir):
            if "chrome.exe" in files:
                return os.path.join(root, "chrome.exe")
    # 2. Chrome hệ thống
    for path in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]:
        if os.path.isfile(path):
            return path
    return None

class ChatGeminiWeb(BaseChatModel):
    """
    Adapter trực tiếp kết nối Gemini Web thông qua Cookie và curl_cffi
    (vượt qua hàng rào TLS Fingerprint của Google, không cần API Key).
    """

    def __init__(
        self,
        secure_1psid: str | None = None,
        secure_1psidts: str | None = None,
        secure_1psidcc: str | None = None,
        model: str = "gemini-web"
    ):
        self.model = model
        
        # Nếu không truyền vào thì nạp tự động từ cấu hình toàn cục
        loaded = load_global_cookies()
        self.secure_1psid = secure_1psid or loaded.get("__Secure-1PSID", "")
        self.secure_1psidts = secure_1psidts or loaded.get("__Secure-1PSIDTS", "")
        self.secure_1psidcc = secure_1psidcc or loaded.get("__Secure-1PSIDCC")
        
        if not self.secure_1psid or not self.secure_1psidts:
            raise ValueError(
                "Chưa cấu hình Cookie Gemini Web! Vui lòng lưu vào ~/.gemini/config/gemini_cookies.json hoặc biến môi trường."
            )

        self.access_token: str | None = None
        self._session: Optional[AsyncSession] = None
        self._verified_api_keys: bool = True

    @property
    def provider(self) -> str:
        return "gemini_webapi"

    @property
    def name(self) -> str:
        return f"gemini-web/{self.model}"

    async def get_session(self) -> AsyncSession:
        if self._session is None:
            cookies = {
                "__Secure-1PSID": self.secure_1psid,
                "__Secure-1PSIDTS": self.secure_1psidts,
            }
            if self.secure_1psidcc:
                cookies["__Secure-1PSIDCC"] = self.secure_1psidcc

            self._session = AsyncSession(
                headers=Headers.GEMINI.value,
                cookies=cookies,
                impersonate="chrome120",
                timeout=60
            )
            # Khởi tạo và trích xuất access token (SNlM0e)
            r = await self._session.get(Endpoint.INIT.value, allow_redirects=True)
            m = re.search(r'"SNlM0e":"(.*?)"', r.text)
            if not m:
                raise RuntimeError("Không thể tìm thấy mã token SNlM0e từ Gemini Web. Cookie có thể đã hết hạn.")
            self.access_token = m.group(1)
        return self._session

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        output_format: type[T] | None = None,
        **kwargs: Any
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        session = await self.get_session()

        # Tạo prompt tổng hợp - lọc bỏ các dữ liệu ảnh base64 khổng lồ để tránh lỗi HTTP 400
        prompt_parts = []
        for msg in messages:
            role = getattr(msg, "type", "user")
            if isinstance(msg.content, list):
                text_pieces = []
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_pieces.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_pieces.append(item)
                content = "\n".join(text_pieces)
            else:
                content = str(msg.content)

            # Cắt ngắn nếu nội dung văn bản quá dài vượt giới hạn web request
            if len(content) > 15000:
                content = content[:15000] + "\n...[truncated for length]..."

            prompt_parts.append(f"[{role.upper()}]:\n{content}")

        if output_format is not None:
            schema = json.dumps(output_format.model_json_schema(), ensure_ascii=False)
            prompt_parts.append(
                f"\n[SYSTEM INSTRUCTION]:\n"
                f"You MUST format your entire response as a single, valid, parseable JSON object matching this schema:\n{schema}\n"
                f"CRITICAL: Output raw JSON only. Do NOT include markdown code fences (```json or ```). "
                f"Do not include any conversational filler."
            )

        full_prompt = "\n\n".join(prompt_parts)

        # Gửi request đến StreamGenerate
        post_data = {
            "at": self.access_token,
            "f.req": json.dumps([
                None,
                json.dumps([[full_prompt], None, None])
            ])
        }

        res = await session.post(Endpoint.GENERATE.value, data=post_data, timeout=60)
        if res.status_code != 200:
            raise RuntimeError(f"Yêu cầu đến Gemini Web thất bại với mã HTTP {res.status_code}")

        # Trích xuất văn bản trả lời đầy đủ (tránh lấy chunk streaming đầu tiên)
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

        if not raw_text:
            raise RuntimeError("Không tìm thấy nội dung phản hồi trong gói tin trả về từ Gemini Web.")

        raw_text = raw_text.strip()

        if output_format is None:
            return ChatInvokeCompletion(completion=raw_text, usage=None)

        # Làm sạch và phân tích cú pháp JSON
        clean_text = raw_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        # 1. Thử validate trực tiếp
        try:
            parsed = output_format.model_validate_json(clean_text)
            return ChatInvokeCompletion(completion=parsed, usage=None)
        except Exception:
            pass

        # 2. Sử dụng json-repair để tự động sửa các lỗi dấu ngoặc/nháy kép/ký tự điều khiển
        try:
            from json_repair import repair_json
            repaired_json = repair_json(clean_text, return_objects=False)
            parsed = output_format.model_validate_json(repaired_json)
            return ChatInvokeCompletion(completion=parsed, usage=None)
        except Exception:
            pass

        # 3. Cố gắng trích xuất khối { ... }
        match = re.search(r"\{.*\}", clean_text, re.DOTALL)
        if match:
            from json_repair import repair_json
            repaired = repair_json(match.group(0), return_objects=False)
            parsed = output_format.model_validate_json(repaired)
            return ChatInvokeCompletion(completion=parsed, usage=None)

        raise ValidationError.from_exception_data(
            title="AgentOutput",
            line_errors=[]
        )

def create_gemini_browser_agent(task: str, headless: bool = False):
    """
    Hàm tiện ích toàn cục: Tạo ngay một Agent Browser-Use dùng Gemini Web làm bộ não.
    Tự động nạp cookie và tự động tìm đường dẫn trình duyệt.
    """
    from browser_use import Agent, Browser

    browser_exe = get_browser_executable()
    browser = Browser(executable_path=browser_exe, headless=headless)
    llm = ChatGeminiWeb()

    return Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision=False,
        max_clickable_elements_length=15000,
    )
