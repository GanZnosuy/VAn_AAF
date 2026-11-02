"""Dual AI Engine & Reflexion Loop using gemini-webapi and Spaced Repetition Integration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

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
    and cleans up session chats to keep Google accounts tidy.
    """

    def __init__(self, cookies: Optional[Dict[str, str]] = None):
        self.cookies = cookies or load_global_cookies()
        self.client = None
        self._is_initialized = False

    @staticmethod
    async def harvest_live_cookies() -> Dict[str, str]:
        """
        Silently extracts live Google/Gemini authentication cookies from Chrome CDP on port 9222
        and automatically propagates them to ~/.gemini/config/gemini_cookies.json and local .env.
        Zero user friction.
        """
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                if not browser.contexts:
                    return {}
                context = browser.contexts[0]
                cookies = await context.cookies([
                    "https://gemini.google.com",
                    "https://google.com",
                    "https://accounts.google.com"
                ])
                cdict = {c["name"]: c["value"] for c in cookies}
                psid = cdict.get("__Secure-1PSID")
                psidts = cdict.get("__Secure-1PSIDTS")
                psidcc = cdict.get("__Secure-1PSIDCC")

                if psid and psidts:
                    res = {
                        "__Secure-1PSID": psid,
                        "__Secure-1PSIDTS": psidts,
                    }
                    if psidcc:
                        res["__Secure-1PSIDCC"] = psidcc

                    # Persist to global config
                    global_path = os.path.expanduser(r"~/.gemini/config/gemini_cookies.json")
                    os.makedirs(os.path.dirname(global_path), exist_ok=True)
                    with open(global_path, "w", encoding="utf-8") as f:
                        json.dump({
                            "GEMINI_SECURE_1PSID": psid,
                            "GEMINI_SECURE_1PSIDTS": psidts,
                            "GEMINI_SECURE_1PSIDCC": psidcc or ""
                        }, f, indent=2, ensure_ascii=False)
                    logger.info("Harvested and persisted live cookies from Chrome CDP.")
                    return res
        except Exception as e:
            logger.debug("Live CDP cookie harvest attempt skipped or failed: %s", e)
        return {}

    async def init_client(self, auto_harvest: bool = True) -> bool:
        """Initializes GeminiClient with cookie session, auto-refresh, and CDP fallback."""
        if self._is_initialized and self.client is not None:
            return True

        psid = self.cookies.get("__Secure-1PSID")
        psidts = self.cookies.get("__Secure-1PSIDTS")
        psidcc = self.cookies.get("__Secure-1PSIDCC")

        if (not psid or not psidts) and auto_harvest:
            logger.info("Cookies missing, attempting live harvest from Chrome CDP...")
            fresh = await self.harvest_live_cookies()
            if fresh:
                self.cookies = fresh
                psid = self.cookies.get("__Secure-1PSID")
                psidts = self.cookies.get("__Secure-1PSIDTS")
                psidcc = self.cookies.get("__Secure-1PSIDCC")

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

    async def delete_chat(self, cid: Optional[str]) -> bool:
        """
        Deletes the conversation thread from Google account history
        to maintain a spotless workspace.
        """
        if not cid or not self.client:
            return False

        try:
            # BatchExecute RPC 't2b5Sc' deletes conversations in Gemini Web UI
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
                # Try cleaning trailing commas or escaped characters
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
        chat_cid = None
        extracted_data: Optional[Dict[str, Any]] = None

        if await self.init_client() and self.client:
            try:
                chat = self.client.start_chat()
                chat_cid = getattr(chat, "cid", None)
                response = await chat.send_message(prompt)
                resp_text = response.text if hasattr(response, "text") else str(response)
                extracted_data = self.extract_json_from_text(resp_text)
            except Exception as e:
                logger.error("Error generating wrong question analysis with Gemini: %s", e)
            finally:
                if chat_cid:
                    await self.delete_chat(chat_cid)

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
            "if_then_trigger": f"Nếu gặp từ chỉ tần suất tuyệt đối (all/never/only) -> Thì đối chiếu trực tiếp vị ngữ của bài đọc & Tránh bẫy khái quát hoá quá mức.",
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
                    "A": f"Hệ quả diễn ra khi các điều kiện biên được thỏa mãn chặt chẽ.",
                    "B": f"Hiện tượng này luôn luôn xảy ra trong mọi trường hợp (Bẫy).",
                    "C": f"Không có mối tương quan nào giữa nguyên nhân và kết quả.",
                    "D": f"Mọi cá thể đều phản ứng giống hệt nhau.",
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
        chat_cid = None
        result: Optional[Dict[str, Any]] = None

        if await self.init_client() and self.client:
            try:
                chat = self.client.start_chat()
                chat_cid = getattr(chat, "cid", None)
                resp = await chat.send_message(prompt)
                resp_text = resp.text if hasattr(resp, "text") else str(resp)
                result = self.extract_json_from_text(resp_text)
            except Exception as e:
                logger.error("Reflexion loop generation error: %s", e)
            finally:
                if chat_cid:
                    await self.delete_chat(chat_cid)

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

    async def analyze_screen_vision(
        self,
        img_path: Optional[str] = None,
        profile_type: str = "TSA_MODE"
    ) -> Dict[str, Any]:
        """
        Zero-CDP Vision Analysis:
        Captures the exam screen and asks Gemini Flash to directly extract wrong questions,
        stems, user answers, official answers, and explanations directly from the pixels.
        """
        import mss
        from PIL import Image

        if not img_path:
            captures_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "captures",
                "solutions",
            )
            os.makedirs(captures_dir, exist_ok=True)
            img_path = os.path.join(captures_dir, "screen_vision_exam.png")
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    if img.width > 1920:
                        ratio = 1920 / img.width
                        img = img.resize((1920, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    img.save(img_path, "PNG", optimize=True)
            except Exception as e:
                logger.error("Failed capturing screen for Vision analysis: %s", e)
                return {"success": False, "error": str(e), "wrong_questions": []}

        prompt = f"""Bạn là Giám Khảo & Huấn Luyện Viên AI chuyên sâu cho kỳ thi {profile_type} (TSA Đánh giá tư duy / IELTS).
Dưới đây là ảnh chụp màn hình hiển thị kết quả làm bài thi của học viên (từ trang web Hociz, Study4, YouPass, hoặc đề thi).
Nhiệm vụ của bạn là:
1. Đọc lướt toàn bộ ảnh để nhận diện các câu hỏi học viên LÀM SAI (thường có màu đỏ, đánh dấu X, hoặc hiển thị 'đáp án của bạn' khác 'đáp án đúng').
2. Trích xuất chính xác từng câu hỏi sai đó.
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
        if await self.init_client() and self.client:
            try:
                response = await self.client.generate_content(prompt, images=[img_path])
                resp_text = response.text if hasattr(response, "text") else str(response)
                extracted = self.extract_json_from_text(resp_text)
                if extracted and isinstance(extracted, dict):
                    extracted["success"] = True
                    return extracted
            except Exception as e:
                logger.error("Gemini Vision OCR extraction failed: %s", e)

        return {"success": False, "error": "AI Vision không thể kết nối hoặc không phân tích được ảnh", "wrong_questions": []}
