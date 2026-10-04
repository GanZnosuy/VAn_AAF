import asyncio
import json
import os
import re
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from dotenv import load_dotenv
from curl_cffi.requests import AsyncSession
from gemini_webapi.constants import Endpoint, Headers

load_dotenv()

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
cookies = {k: v for k, v in cookies.items() if v}

cached_token = None

async def get_gemini_token(session: AsyncSession) -> str:
    global cached_token
    if cached_token:
        return cached_token
    r = await session.get(Endpoint.INIT.value)
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
                cached_token = token
                return token
        except Exception:
            pass
    m = re.search(r'"SNlM0e":"(.*?)"', r.text)
    if m:
        cached_token = m.group(1)
        return cached_token
    return ""

async def query_gemini(prompt: str) -> str:
    global cached_token
    for attempt in range(3):
        try:
            async with AsyncSession(headers=Headers.GEMINI.value, cookies=cookies, impersonate="chrome120") as s:
                token = await get_gemini_token(s)
                if not token:
                    cached_token = None
                    await asyncio.sleep(2)
                    continue

                post_data = {
                    "at": token,
                    "f.req": json.dumps([None, json.dumps([[prompt], None, None])])
                }
                res = await s.post(Endpoint.GENERATE.value, data=post_data, timeout=35)
                if res.status_code != 200:
                    cached_token = None
                    await asyncio.sleep(2)
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
                        except:
                            pass
                if raw_text:
                    return raw_text
                else:
                    cached_token = None
        except Exception as e:
            cached_token = None
            await asyncio.sleep(2)
    return ""

async def main():
    test_prompts = [
        "Tính 1 + 1 bằng mấy? Trả lời dạng: ĐÁP ÁN: 2",
        "Chất nào sau đây là este? A. CH3COOH B. HCOOCH3 C. C2H5OH D. HCHO. ĐÁP ÁN: <A/B/C/D>",
        "Cho hàm số y = (2x + 1)/(x - 1). Tìm tiệm cận đứng và tiệm cận ngang. ĐÁP ÁN: <tóm tắt>"
    ]
    for p in test_prompts:
        print(">>> Prompt:", p)
        ans = await query_gemini(p)
        print("<<< Answer:", repr(ans[:120]))
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
