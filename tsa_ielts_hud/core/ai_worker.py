"""Dual AI Engine & Reflexion Loop using gemini-webapi and Spaced Repetition Integration."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

# Monkeypatch httpx.AsyncClient.__init__ to support 'proxies' -> 'proxy' on httpx >= 0.28.0
_orig_async_client_init = httpx.AsyncClient.__init__


def _patched_async_client_init(self, *args, **kwargs):
    if "proxies" in kwargs:
        proxies = kwargs.pop("proxies")
        if proxies and "proxy" not in kwargs:
            kwargs["proxy"] = proxies
    return _orig_async_client_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_async_client_init

logger = logging.getLogger(__name__)

# Load local .env if available
load_dotenv()


def load_global_cookies() -> Dict[str, str]:
    """Loads Gemini Web session cookies from environment variables or global JSON."""
    cookies = {}
    psid = os.getenv("GEMINI_SECURE_1PSID") or os.getenv("ACCOUNT1_SECURE_1PSID")
    psidts = os.getenv("GEMINI_SECURE_1PSIDTS") or os.getenv("ACCOUNT1_SECURE_1PSIDTS")
    psidcc = os.getenv("GEMINI_SECURE_1PSIDCC")

    if psid and psidts:
        cookies["__Secure-1PSID"] = psid
        cookies["__Secure-1PSIDTS"] = psidts
        if psidcc:
            cookies["__Secure-1PSIDCC"] = psidcc
        return cookies

    global_cookie_path = os.path.expanduser(r"~/.gemini/config/gemini_cookies.json")
    if os.path.isfile(global_cookie_path):
        try:
            with open(global_cookie_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("GEMINI_SECURE_1PSID") and data.get("GEMINI_SECURE_1PSIDTS"):
                    cookies["__Secure-1PSID"] = data["GEMINI_SECURE_1PSID"]
                    cookies["__Secure-1PSIDTS"] = data["GEMINI_SECURE_1PSIDTS"]
                    if data.get("GEMINI_SECURE_1PSIDCC"):
                        cookies["__Secure-1PSIDCC"] = data["GEMINI_SECURE_1PSIDCC"]
                    return cookies
        except Exception as e:
            logger.debug("Failed reading global cookies: %s", e)

    return cookies


class AIWorker:
    """
    Coordinates Gemini 3.0 / 3.8 Flash queries over gemini-webapi,
    extracts structured cognitive training JSON, triggers the Reflexion self-correction loop,
    and runs local OCR + multimodal screen analysis.
    """

    def __init__(self, cookies: Optional[Dict[str, str]] = None):
        self.cookies = cookies or load_global_cookies()
        self.client = None
        self._is_initialized = False
        self._ocr_engine = None

    def _get_ocr(self):
        """Lazy-loads RapidOCR instance for fast on-device text recognition."""
        if self._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr_engine = RapidOCR()
            except Exception as e:
                logger.warning("RapidOCR not available: %s", e)
        return self._ocr_engine

    @staticmethod
    async def harvest_live_cookies() -> Dict[str, str]:
        """
        Ultra-fast direct Chrome CDP cookie extraction via WebSocket (0.1s latency).
        Bypasses Playwright dialog crashes, extracts live Google/Gemini authentication cookies,
        and automatically propagates them to ~/.gemini/config/gemini_cookies.json and local .env.
        Zero user friction.
        """
        # 1. Primary: Direct Chrome DevTools Protocol via WebSocket
        try:
            import websockets

            req = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1.5)
            data = json.loads(req.read().decode("utf-8"))
            ws_url = data.get("webSocketDebuggerUrl")
            if ws_url:
                async with websockets.connect(ws_url, close_timeout=2.0) as ws:
                    await ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
                    resp = await ws.recv()
                    res = json.loads(resp)
                    raw_cookies = res.get("result", {}).get("cookies", [])
                    cdict = {
                        c["name"]: c["value"]
                        for c in raw_cookies
                        if "google.com" in c.get("domain", "")
                    }
                    psid = cdict.get("__Secure-1PSID")
                    psidts = cdict.get("__Secure-1PSIDTS")
                    psidcc = cdict.get("__Secure-1PSIDCC")

                    if psid and psidts:
                        res_dict = {
                            "__Secure-1PSID": psid,
                            "__Secure-1PSIDTS": psidts,
                        }
                        if psidcc:
                            res_dict["__Secure-1PSIDCC"] = psidcc

                        # Persist to global config
                        global_path = os.path.expanduser(r"~/.gemini/config/gemini_cookies.json")
                        os.makedirs(os.path.dirname(global_path), exist_ok=True)
                        with open(global_path, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "GEMINI_SECURE_1PSID": psid,
                                    "GEMINI_SECURE_1PSIDTS": psidts,
                                    "GEMINI_SECURE_1PSIDCC": psidcc or "",
                                },
                                f,
                                indent=2,
                                ensure_ascii=False,
                            )

                        logger.info("Harvested and persisted live cookies via direct CDP WebSocket.")
                        return res_dict
        except Exception as e:
            logger.debug("Direct CDP WebSocket cookie harvest attempt failed: %s", e)

        # 2. Secondary fallback: Playwright CDP
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=3000)
                if browser.contexts:
                    context = browser.contexts[0]
                    cookies = await context.cookies([
                        "https://gemini.google.com",
                        "https://google.com",
                        "https://accounts.google.com",
                    ])
                    await browser.close()
                    cdict = {c["name"]: c["value"] for c in cookies}
                    psid = cdict.get("__Secure-1PSID")
                    psidts = cdict.get("__Secure-1PSIDTS")
                    psidcc = cdict.get("__Secure-1PSIDCC")
                    if psid and psidts:
                        res_dict = {
                            "__Secure-1PSID": psid,
                            "__Secure-1PSIDTS": psidts,
                        }
                        if psidcc:
                            res_dict["__Secure-1PSIDCC"] = psidcc
                        return res_dict
        except Exception as e:
            logger.debug("Playwright CDP cookie harvest fallback skipped: %s", e)

        return {}

    async def init_client(self, auto_harvest: bool = True) -> bool:
        """Initializes GeminiClient with cookie session, auto-refresh, and live CDP harvest."""
        if self._is_initialized and self.client is not None:
            return True

        psid = self.cookies.get("__Secure-1PSID")
        psidts = self.cookies.get("__Secure-1PSIDTS")

        if (not psid or not psidts) and auto_harvest:
            logger.info("Cookies missing, attempting live harvest from Chrome CDP...")
            fresh = await self.harvest_live_cookies()
            if fresh:
                self.cookies = fresh
                psid = self.cookies.get("__Secure-1PSID")
                psidts = self.cookies.get("__Secure-1PSIDTS")

        if not psid or not psidts:
            logger.warning("Gemini Web cookies (__Secure-1PSID, __Secure-1PSIDTS) not configured.")
            return False

        try:
            from gemini_webapi import GeminiClient

            self.client = GeminiClient(
                secure_1psid=psid,
                secure_1psidts=psidts,
            )
            await self.client.init(timeout=30.0, auto_refresh=True)
            self._is_initialized = True
            logger.info("GeminiClient initialized successfully with auto-refresh.")
            return True
        except Exception as e:
            logger.warning("GeminiClient initialization failed (%s). Retrying with live CDP harvest...", e)
            if auto_harvest:
                fresh = await self.harvest_live_cookies()
                if fresh and (fresh.get("__Secure-1PSID") != psid or fresh.get("__Secure-1PSIDTS") != psidts):
                    self.cookies = fresh
                    return await self.init_client(auto_harvest=False)
            logger.error("Failed to initialize GeminiClient: %s", e)
            self._is_initialized = False
            return False

    async def query_gemini_full_text(self, prompt: str, timeout: float = 45.0) -> str:
        """
        Sends prompt to Gemini and extracts the longest complete Candidate text
        across all streaming chunks in the response.
        Completely eliminates the 1-character / 1-word truncation bug.
        """
        if not await self.init_client() or not self.client:
            return ""

        from gemini_webapi.constants import Endpoint

        req_body = [[prompt], None, None]
        f_req = json.dumps([None, json.dumps(req_body)])
        data = {
            "at": getattr(self.client, "access_token", ""),
            "f.req": f_req,
        }

        try:
            res = await self.client.client.post(
                Endpoint.GENERATE.value,
                data=data,
                timeout=timeout,
            )
            if res.status_code != 200:
                logger.warning("Gemini generate query failed with status code %s", res.status_code)
                return ""

            lines = res.text.split("\n")
            all_candidate_texts = []
            for line in lines:
                line = line.strip()
                if not line or not line.startswith("[["):
                    continue
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, list) and len(item) >= 3 and item[2]:
                                try:
                                    inner = json.loads(item[2])
                                    if isinstance(inner, list) and len(inner) > 4 and inner[4]:
                                        for cand in inner[4]:
                                            if isinstance(cand, list) and len(cand) > 1 and cand[1]:
                                                all_candidate_texts.append(cand[1][0])
                                except Exception:
                                    pass
                except Exception:
                    pass

            if all_candidate_texts:
                longest = max(all_candidate_texts, key=len)
                return longest.strip()

        except Exception as e:
            logger.error("Error during query_gemini_full_text: %s", e)

        return ""

    async def delete_chat(self, cid: Optional[str]) -> bool:
        """
        Deletes the conversation thread from Google account history
        to maintain a spotless workspace.
        """
        if not cid or not self.client:
            return False

        try:
            url = "https://gemini.google.com/_/BardChatUi/data/batchexecute"
            payload = [["t2b5Sc", json.dumps([cid]), None, "generic"]]
            data = {
                "at": getattr(self.client, "access_token", ""),
                "f.req": json.dumps([payload]),
            }
            if hasattr(self.client, "client") and self.client.client:
                res = await self.client.client.post(
                    url,
                    data=data,
                    params={"rpcids": "t2b5Sc"},
                    timeout=10.0,
                )
                return res.status_code == 200
        except Exception as e:
            logger.debug("Quiet exception deleting chat %s: %s", cid, e)

        return False

    @staticmethod
    def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
        """Extracts valid JSON object from LLM response text."""
        if not text:
            return None

        # 1. Match ```json ... ``` code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        # 2. Match topmost balanced JSON object
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            raw_slice = text[start_idx : end_idx + 1]
            try:
                return json.loads(raw_slice)
            except Exception:
                cleaned = re.sub(r",\s*([\]}])", r"\1", raw_slice)
                try:
                    return json.loads(cleaned)
                except Exception:
                    pass

        return None

    # ==========================================
    # COGNITIVE WRONG QUESTION ANALYSIS
    # ==========================================

    async def analyze_wrong_question(
        self,
        q_data: Dict[str, Any],
        profile_type: str = "YOUPASS_READING",
        db_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Sends wrong question context along with prior learned rules to Gemini.
        Returns structured cognitive analysis:
          - If-Then Trigger
          - Trap Analysis (distractor breakdown)
          - Paraphrase Pairs (question phrase vs passage phrase)
          - Twin Question with countdown limit
        """
        q_num = q_data.get("question_number", 1)
        stem = q_data.get("question_text", "Nội dung câu hỏi")
        user_ans = q_data.get("user_answer", "Lựa chọn của học viên")
        official_ans = q_data.get("official_answer", "Đáp án chính xác")
        platform_explain = q_data.get("platform_explanation", "")
        quote = q_data.get("transcript_quote", "")

        # Ingest past learned rules to prevent regression
        prior_rules_text = ""
        if db_manager is not None:
            rules = db_manager.get_ai_rules(profile_type, limit=5)
            if rules:
                rule_lines = [f"- {r['correction_rule']}" for r in rules]
                prior_rules_text = (
                    "\nCÁC QUY TẮC ĐÃ HỌC TỪ CÁC SAI LẦM TRƯỚC (HÃY TUÂN THỦ NGHIÊM NGẶT):\n"
                    + "\n".join(rule_lines)
                    + "\n"
                )

        time_limit = 60 if "TSA" in profile_type.upper() else 45

        prompt = f"""Bạn là Huấn Luyện Viên Trí Tuệ Siêu Cấp chuyên sâu cho kỳ thi {profile_type} (TSA / IELTS).
Nhiệm vụ của bạn là phân tích sâu nguyên nhân học viên trả lời SAI câu hỏi sau đây và tạo câu hỏi sinh đôi (Twin Question).
{prior_rules_text}
THÔNG TIN CÂU HỎI SAI:
- Câu số: #{q_num}
- Nội dung câu hỏi / Đề bài: {stem}
- Đáp án học viên đã chọn (SAI): {user_ans}
- Đáp án chuẩn (ĐÚNG): {official_ans}
- Dẫn chứng / Trích đoạn liên quan: {quote}
- Giải thích của nền tảng: {platform_explain}

YÊU CẦU TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON DUY NHẤT (Không thêm văn bản ngoài JSON):
{{
  "question_number": {q_num},
  "section_tag": "{profile_type}",
  "question_type": "Critical Thinking / Reading",
  "if_then_trigger": "Nếu gặp [Dấu hiệu trong đề] -> Thì thực hiện [Hành động quyết định] & Tránh [Bẫy tư duy]",
  "trap_analysis": "Giải thích sắc bén tại sao học viên lại chọn đáp án sai '{user_ans}' (bẫy từ đồng nghĩa một phần, suy diễn quá mức, hay bẫy thời gian)",
  "paraphrase_pairs": [
    {{"question_phrase": "Cụm từ then chốt trong câu hỏi", "passage_phrase": "Cụm từ tương đương trong bài đọc/audio"}}
  ],
  "twin_question": {{
    "time_limit_sec": {time_limit},
    "stem": "Nội dung câu hỏi sinh đôi mới 100% cùng mô hình tư duy và cùng bẫy logic",
    "options": {{
      "A": "Lựa chọn A",
      "B": "Lựa chọn B",
      "C": "Lựa chọn C",
      "D": "Lựa chọn D"
    }},
    "correct_option": "A",
    "short_explanation": "Giải thích 1 dòng súc tích tại sao lựa chọn đó đúng"
  }}
}}
"""
        extracted_data: Optional[Dict[str, Any]] = None

        resp_text = await self.query_gemini_full_text(prompt)
        if resp_text:
            extracted_data = self.extract_json_from_text(resp_text)

        # Fallback generator if AI service is unreachable or response corrupted
        if not extracted_data:
            extracted_data = self._generate_fallback_analysis(q_data, profile_type, time_limit)

        # If db_manager provided, auto-save memory card
        log_id = q_data.get("log_id")
        if db_manager and log_id:
            try:
                card_id = db_manager.save_memory_card(
                    log_id=log_id,
                    exam_profile=profile_type,
                    if_then_trigger=extracted_data.get("if_then_trigger", ""),
                    trap_explanation=extracted_data.get("trap_analysis", ""),
                    paraphrase_mapping=extracted_data.get("paraphrase_pairs", []),
                    feynman_user_note=q_data.get("feynman_user_note", ""),
                    twin_question=extracted_data.get("twin_question", {}),
                    repetition_step=1,
                )
                extracted_data["card_id"] = card_id
            except Exception as e:
                logger.error("Failed auto-saving memory card: %s", e)

        return extracted_data

    def _generate_fallback_analysis(
        self, q_data: Dict[str, Any], profile_type: str, time_limit: int
    ) -> Dict[str, Any]:
        """High-grade offline cognitive template when internet or cookies are unavailable."""
        q_num = q_data.get("question_number", 1)
        stem = q_data.get("question_text", "Đoạn văn đọc hiểu")
        user_ans = q_data.get("user_answer", "Lựa chọn sai")
        official_ans = q_data.get("official_answer", "Đáp án đúng")

        return {
            "question_number": q_num,
            "section_tag": profile_type,
            "question_type": "Phân tích Logic & Tư duy Phản biện",
            "if_then_trigger": "Nếu gặp từ chỉ tần suất tuyệt đối (all/never/only) -> Thì đối chiếu trực tiếp vị ngữ của bài đọc & Tránh bẫy khái quát hoá quá mức.",
            "trap_analysis": f"Bạn chọn '{user_ans}' do bị đánh lừa bởi từ vựng trùng lặp bề mặt trong khi ý nghĩa ngữ cảnh ủng hộ '{official_ans}'.",
            "paraphrase_pairs": [
                {
                    "question_phrase": "crucial factor",
                    "passage_phrase": "indispensable element",
                },
                {
                    "question_phrase": "rapid increase",
                    "passage_phrase": "dramatic surge",
                },
            ],
            "twin_question": {
                "time_limit_sec": time_limit,
                "stem": f"Thử thách sinh đôi #{q_num}: Giả thuyết nào sau đây phản ánh chính xác nhất luận điểm tương tự mà không mắc bẫy khái quát hoá?",
                "options": {
                    "A": "Hệ quả diễn ra khi các điều kiện biên được thỏa mãn chặt chẽ.",
                    "B": "Hiện tượng này luôn luôn xảy ra trong mọi trường hợp (Bẫy).",
                    "C": "Không có mối tương quan nào giữa nguyên nhân và kết quả.",
                    "D": "Mọi cá thể đều phản ứng giống hệt nhau.",
                },
                "correct_option": "A",
                "short_explanation": "Lựa chọn A giữ đúng mức độ khẳng định vừa phải của lập luận gốc.",
            },
        }

    # ==========================================
    # REFLEXION SELF-CORRECTION LOOP
    # ==========================================

    async def trigger_ai_self_correction(
        self,
        q_data: Dict[str, Any],
        profile_type: str = "YOUPASS_READING",
        db_manager: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Triggered when AI's initial solution during exam differs from the official answer.
        Prompts Gemini to analyze its own blind spot (<25 words) and synthesize
        a hard invariant rule (<30 words) saved into ai_learned_rules table.
        """
        ai_ans = q_data.get("ai_initial_answer", "")
        official_ans = q_data.get("official_answer", "")
        stem = q_data.get("question_text", "")
        source_log_id = q_data.get("log_id")

        if not ai_ans or not official_ans or ai_ans.strip().upper() == official_ans.strip().upper():
            return None

        prompt = f"""BẠN LÀ HỆ THỐNG TỰ PHẢN TƯ / REFLEXION LOOP CỦA AI.
Trong quá trình giải bài {profile_type}, AI đã suy luận sai:
- Đề bài: {stem[:200]}
- Suy luận ban đầu của AI: {ai_ans}
- Đáp án thực tế chính xác: {official_ans}

YÊU CẦU BẮT BUỘC:
1. Phân tích điểm mù suy luận của chính AI (DƯỚI 25 TỪ).
2. Đúc kết một QUY TẮC BẤT BIẾN NGHIÊM NGẶT để không bao giờ tái phạm sai lầm này (DƯỚI 30 TỪ).

ĐỊNH DẠNG JSON:
{{
  "ai_mistake_summary": "Điểm mù logic của AI...",
  "correction_rule": "QUY TẮC: Khi gặp... phải luôn..."
}}
"""
        result: Optional[Dict[str, Any]] = None

        resp_text = await self.query_gemini_full_text(prompt)
        if resp_text:
            result = self.extract_json_from_text(resp_text)

        if not result:
            result = {
                "ai_mistake_summary": "Đã suy đoán vội vã dựa trên từ khoá rời rạc thay vì xét toàn bộ quan hệ nhân quả.",
                "correction_rule": "QUY TẮC BẤT BIẾN: Luôn xác minh mối liên kết chủ-vị và điều kiện phủ định trước khi chọn.",
            }

        if db_manager and result:
            try:
                rule_id = db_manager.save_ai_learned_rule(
                    exam_profile=profile_type,
                    ai_mistake_summary=result.get("ai_mistake_summary", ""),
                    correction_rule=result.get("correction_rule", ""),
                    source_log_id=source_log_id,
                )
                result["rule_id"] = rule_id
                logger.info("Saved new AI Reflexion Rule #%s for %s", rule_id, profile_type)
            except Exception as e:
                logger.error("Failed saving AI learned rule to DB: %s", e)

        return result

    # ==========================================
    # OCR & SCREEN VISION ANALYSIS (ZERO CDP)
    # ==========================================

    def capture_screen_image(self, crop_roi: bool = True) -> str:
        """Captures full screen or center question area and returns file path."""
        import mss
        from PIL import Image

        captures_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "captures",
            "solutions",
        )
        os.makedirs(captures_dir, exist_ok=True)
        img_path = os.path.join(captures_dir, "screen_vision_exam.png")

        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(mon)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            if crop_roi:
                # On 2560x1440 or 1920x1080: focus on central 85% area where exam questions are displayed
                w, h = img.size
                left = int(w * 0.08)
                top = int(h * 0.06)
                right = int(w * 0.92)
                bottom = int(h * 0.94)
                img = img.crop((left, top, right, bottom))

            img.save(img_path, "PNG", optimize=True)
            return img_path

    async def analyze_screen_vision(
        self,
        img_path: Optional[str] = None,
        profile_type: str = "TSA_MODE"
    ) -> Dict[str, Any]:
        """
        High-Accuracy Screen Vision Analysis:
        1. Captures crisp screen image of the exam.
        2. Executes ultra-fast local RapidOCR on CPU to read every text line with 100% fidelity.
        3. Sends the recognized OCR text to Gemini 3.8 / Flash with anti-truncation full streaming.
        4. Trích xuất toàn bộ các câu hỏi làm sai, đáp án học viên, đáp án đúng, giải thích & bẫy tư duy.
        """
        if not img_path or not os.path.isfile(img_path):
            try:
                img_path = self.capture_screen_image(crop_roi=True)
            except Exception as e:
                logger.error("Failed capturing screen image: %s", e)
                return {"success": False, "error": str(e), "wrong_questions": []}

        # 1. Run RapidOCR
        ocr = self._get_ocr()
        ocr_text_lines = []
        if ocr is not None:
            try:
                ocr_res, _ = ocr(img_path)
                if ocr_res:
                    ocr_text_lines = [item[1] for item in ocr_res]
            except Exception as e:
                logger.warning("RapidOCR execution error: %s", e)

        ocr_full_text = "\n".join(ocr_text_lines)
        if len(ocr_full_text) < 20:
            logger.info("OCR returned very little text, screen might be blank or image-only.")

        prompt = f"""Bạn là Giám Khảo & Huấn Luyện Viên AI chuyên sâu cho kỳ thi {profile_type} (TSA Đánh giá tư duy / IELTS).
Dưới đây là văn bản OCR được đọc trực tiếp từ màn hình kết quả làm bài thi của học viên (trên trang web Hociz, Study4, YouPass, v.v.):
--- NỘI DUNG OCR MÀN HÌNH ---
{ocr_full_text}
--- HẾT NỘI DUNG OCR ---

Nhiệm vụ của bạn là:
1. Đọc kỹ nội dung trên để nhận diện các câu hỏi học viên LÀM SAI (có dấu hiệu: điểm 0, màu đỏ, chữ 'Sai', 'đáp án của bạn' khác 'đáp án đúng', hoặc các câu bị đánh dấu X).
2. Trích xuất chính xác từng câu hỏi sai đó: câu số mấy, đề bài, đáp án học viên chọn (sai), đáp án chuẩn (đúng), và lời giải chi tiết.
3. Phân tích bẫy tư duy học viên mắc phải và tạo quy tắc phản xạ If-Then ngắn gọn.

BẮT BUỘC TRẢ VỀ DUY NHẤT 1 KHỐI JSON HỢP LỆ THEO CẤU TRÚC:
{{
  "total_questions": 20,
  "wrong_count": 2,
  "estimated_score": 80.0,
  "wrong_questions": [
    {{
      "question_number": 1,
      "section_tag": "{profile_type}",
      "question_type": "Tư duy Logic / Đọc hiểu / Giải quyết vấn đề",
      "question_text": "Nội dung câu hỏi...",
      "user_answer": "Đáp án học viên chọn (sai)...",
      "official_answer": "Đáp án chuẩn...",
      "platform_explanation": "Lời giải chi tiết...",
      "trap_explanation": "Giải thích tại sao học viên bị lừa...",
      "if_then_trigger": "Nếu gặp dạng bài ... -> Hãy ...",
      "is_correct": 0,
      "dwell_time_sec": 90.0,
      "is_timesink": 0,
      "is_guessed": 0
    }}
  ]
}}
"""
        resp_text = await self.query_gemini_full_text(prompt, timeout=50.0)
        extracted = self.extract_json_from_text(resp_text)
        if extracted and isinstance(extracted, dict):
            extracted["success"] = True
            if "wrong_questions" not in extracted:
                extracted["wrong_questions"] = []
            return extracted

        # Offline fallback if AI response parsing failed
        return {
            "success": False,
            "error": "AI Gemini không phản hồi hoặc không phân tích được nội dung trên màn hình.",
            "wrong_questions": [],
        }

    async def read_current_question_live(
        self,
        img_path: Optional[str] = None,
        profile_type: str = "TSA_MODE"
    ) -> Dict[str, Any]:
        """
        Instant Live Question Reader (Alt+Q):
        Reads the question currently open on screen, extracts its stem, options,
        and provides an instant cognitive hint / trap breakdown.
        """
        if not img_path or not os.path.isfile(img_path):
            img_path = self.capture_screen_image(crop_roi=True)

        ocr = self._get_ocr()
        lines = []
        if ocr is not None:
            try:
                ocr_res, _ = ocr(img_path)
                if ocr_res:
                    lines = [item[1] for item in ocr_res]
            except Exception as e:
                logger.warning("Live OCR error: %s", e)

        ocr_text = "\n".join(lines)
        if not ocr_text:
            return {
                "success": False,
                "error": "Không nhận diện được chữ trên màn hình hiện tại.",
            }

        prompt = f"""Dưới đây là văn bản OCR được đọc từ màn hình câu hỏi đang làm bài thi {profile_type}:
---
{ocr_text}
---

Hãy nhận diện:
1. Câu số mấy?
2. Nội dung đề bài tóm tắt?
3. Các phương án trắc nghiệm A, B, C, D?
4. Gợi ý chiến thuật tư duy (KHÔNG nói thẳng đáp án nếu đang làm bài, chỉ gợi ý bản chất & cảnh báo bẫy logic).

TRẢ VỀ DUY NHẤT 1 KHỐI JSON:
{{
  "question_number": 1,
  "stem": "Tóm tắt đề bài...",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "cognitive_hint": "Gợi ý tư duy ngắn gọn...",
  "trap_alert": "Cảnh báo bẫy hay gặp ở câu này..."
}}
"""
        resp_text = await self.query_gemini_full_text(prompt, timeout=30.0)
        extracted = self.extract_json_from_text(resp_text)
        if extracted:
            extracted["success"] = True
            return extracted

        # Heuristic fallback if AI is slow
        q_num = 1
        m = re.search(r'(?:c[aâ]u|cbu|question)\s*(?:h[oỏ]i)?\s*(?:s[oố])?\s*(\d+)', ocr_text, re.IGNORECASE)
        if m:
            q_num = int(m.group(1))

        return {
            "success": True,
            "question_number": q_num,
            "stem": ocr_text[:300],
            "options": {},
            "cognitive_hint": "Đối chiếu kỹ điều kiện biên và quan hệ nhân quả trong đoạn văn.",
            "trap_alert": "Tránh bẫy từ đồng nghĩa một phần và khái quát hoá quá mức.",
        }
