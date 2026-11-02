"""0.5 FPS Screen Watcher: Dynamic ROI Cropping, dHash Hamming Comparison, Local OCR Confirmation, and 2x2 Grid Builder."""

from __future__ import annotations

import io
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import imagehash
import mss
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class SmartScreenWatcher:
    """
    Ultra-low latency screen sensor thread (0.5 FPS / 2s intervals).
    Monitors dynamic regions of interest (ROI) per exam platform,
    computes 64-bit dHash Hamming distance + local OCR header parsing to detect question switches,
    tracks dwell time, and flags rapid guesses or time-sinks.
    """

    DEFAULT_ROI_RATIOS = {
        # HOCIZ TSA: Central question card on hociz.vn
        "HOCIZ_TSA": (0.16, 0.10, 0.68, 0.82),
        # TSA: Center questions area
        "TSA_MODE": (0.15, 0.12, 0.70, 0.75),
        # YouPass Reading: Right-hand question pane (ignores left-side passage scrolling)
        "YOUPASS_READING": (0.52, 0.12, 0.44, 0.76),
        # STUDY4: Main left/center question card, avoids right question-index grid
        "STUDY4_READING": (0.05, 0.15, 0.67, 0.73),
        # IELTS Listening & Writing defaults
        "IELTS_LISTENING": (0.18, 0.15, 0.64, 0.72),
        "IELTS_WRITING": (0.10, 0.12, 0.80, 0.76),
    }

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.screen_w = max(screen_w, 800)
        self.screen_h = max(screen_h, 600)
        self.config = config or {}

        self.hamming_threshold: int = int(self.config.get("hamming_threshold", 8))
        self.guess_threshold_sec: float = float(self.config.get("guess_threshold_sec", 12))
        self.time_sink_thresholds: Dict[str, float] = self.config.get(
            "time_sink_thresholds",
            {
                "HOCIZ_TSA": 120,
                "TSA_MODE": 120,
                "YOUPASS_READING": 90,
                "STUDY4_READING": 90,
                "IELTS_LISTENING": 60,
                "IELTS_WRITING": 300,
            },
        )

        # Session tracking state
        self.current_q_index: int = 1
        self.current_q_hash: Optional[imagehash.ImageHash] = None
        self.current_dwell_sec: float = 0.0

        # Anti-flapping / debounce filter state
        self.candidate_switch_count: int = 0
        self.candidate_switch_hash: Optional[imagehash.ImageHash] = None
        self.is_paused: bool = False

        # Memory of seen questions in current session: list of (index, hash, accumulated_dwell)
        self.question_history: List[Dict[str, Any]] = []

        # Total cumulative exam timer (seconds)
        self.session_elapsed_sec: float = 0.0

        # Flagged questions set
        self.flagged_questions: set[int] = set()

        # Cache mss instance per thread or create on demand
        self._sct: Any = None
        self._ocr = None

    def _get_ocr(self):
        """Lazy-loads RapidOCR for header confirmation."""
        if self._ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr = RapidOCR()
            except Exception as e:
                logger.debug("RapidOCR not loaded in watcher: %s", e)
        return self._ocr

    def _get_sct(self) -> Any:
        if self._sct is None:
            factory = getattr(mss, "MSS", getattr(mss, "mss", None))
            self._sct = factory()
        return self._sct

    def close(self) -> None:
        """Closes MSS capture context safely."""
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None

    def reset_session(self) -> None:
        """Resets watcher state for a fresh exam session (locks to Question 1)."""
        self.current_q_index = 1
        self.current_q_hash = None
        self.current_dwell_sec = 0.0
        self.question_history.clear()
        self.session_elapsed_sec = 0.0
        self.flagged_questions.clear()
        self.candidate_switch_count = 0
        self.candidate_switch_hash = None
        self.is_paused = False

    def set_current_question(self, q_num: int) -> None:
        """Explicitly sets active question index (from hotkey, UI, or CDP DOM sync)."""
        if q_num < 1:
            q_num = 1
        self.current_q_index = q_num
        self.current_dwell_sec = 0.0
        self.candidate_switch_count = 0
        self.candidate_switch_hash = None

        # Check if already in history
        found = False
        for entry in self.question_history:
            if entry.get("index") == q_num:
                found = True
                break
        if not found and self.current_q_hash is not None:
            self.question_history.append(
                {
                    "index": q_num,
                    "hash": self.current_q_hash,
                    "dwell": 0.0,
                    "is_guessed": False,
                }
            )

    def get_roi_box(self, profile_id: str) -> Tuple[int, int, int, int]:
        """
        Calculates screen pixel coordinate bounding box:
        (left, top, width, height) based on platform profile.
        """
        ratios = self.DEFAULT_ROI_RATIOS.get(
            profile_id, self.DEFAULT_ROI_RATIOS["YOUPASS_READING"]
        )
        rx, ry, rw, rh = ratios
        left = int(rx * self.screen_w)
        top = int(ry * self.screen_h)
        width = int(rw * self.screen_w)
        height = int(rh * self.screen_h)
        return left, top, width, height

    def capture_roi(self, profile_id: str) -> Optional[Image.Image]:
        """Captures only the target ROI and returns an in-memory PIL Image."""
        try:
            sct = self._get_sct()
            left, top, width, height = self.get_roi_box(profile_id)
            monitor = {"left": left, "top": top, "width": width, "height": height}
            sct_img = sct.grab(monitor)
            # Convert MSS BGRA to PIL RGB Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
        except Exception as e:
            logger.debug("Quiet exception capturing screen ROI (desktop may be locked or virtualized): %s", e)
            return None

    def detect_question_number_from_image(self, img: Image.Image) -> Optional[int]:
        """
        Performs fast OCR on the top header strip of the question image
        to detect the exact question number ('Câu 5', 'Question 12', '#05').
        """
        ocr = self._get_ocr()
        if ocr is None or img is None:
            return None

        try:
            # Crop header strip (top 15% or up to 100px)
            header_h = min(100, max(40, int(img.height * 0.18)))
            header_crop = img.crop((0, 0, img.width, header_h))

            # Convert to bytes for RapidOCR
            buf = io.BytesIO()
            header_crop.save(buf, format="PNG")
            ocr_res, _ = ocr(buf.getvalue())
            if not ocr_res:
                return None

            text = " ".join([item[1] for item in ocr_res])
            patterns = [
                r"(?:c[aâu]u|cbu|cuhi|cuhiso|question|q)\s*(?:h[oỏi]i)?\s*(?:s[oố]o)?\s*[:#\s]*(\d+)",
                r"(?:câu|question|cbu|q|#)\s*[:#\s]*(\d+)",
                r"(?:c[a-z]*\s*(?:h[a-z]*)?\s*(?:s[a-z]*)?|q[a-z]*)\s*[:#\s]*(\d+)",
            ]
            for pat in patterns:
                m = re.search(pat, text, re.I)
                if m:
                    num = int(m.group(1))
                    if 1 <= num <= 200:
                        return num
        except Exception as e:
            logger.debug("Quiet exception in detect_question_number_from_image: %s", e)

        return None

    def sample_frame(
        self, profile_id: str, delta_sec: float = 2.0
    ) -> Dict[str, Any]:
        """
        0.5 FPS sensor evaluation:
        1. Grabs ROI.
        2. Computes 64-bit dHash.
        3. Runs anti-flapping filter + OCR confirmation.
        4. Detects switch, guess, timesink, or revisitation of previous question.
        """
        self.session_elapsed_sec += delta_sec
        img = self.capture_roi(profile_id)

        if img is None:
            self.current_dwell_sec += delta_sec
            return {
                "question_index": self.current_q_index,
                "dwell_sec": self.current_dwell_sec,
                "switched": False,
                "is_guessed": False,
                "is_timesink": False,
                "cumulative_sec": self.session_elapsed_sec,
                "captured_img": None,
            }

        try:
            gray = img.convert("L")
            new_hash = imagehash.dhash(gray, hash_size=8)
        except Exception as e:
            logger.warning("Failed computing dHash: %s", e)
            new_hash = self.current_q_hash

        switched = False
        is_guessed = False
        is_timesink = False
        prev_q_index: Optional[int] = None
        prev_dwell: float = 0.0

        limit = self.time_sink_thresholds.get(
            profile_id, self.time_sink_thresholds.get("YOUPASS_READING", 90.0)
        )

        if self.is_paused:
            return {
                "question_index": self.current_q_index,
                "prev_question_index": None,
                "prev_dwell_sec": 0.0,
                "dwell_sec": self.current_dwell_sec,
                "switched": False,
                "is_guessed": False,
                "is_timesink": False,
                "cumulative_sec": self.session_elapsed_sec,
                "time_limit": limit,
                "flagged": self.current_q_index in self.flagged_questions,
                "captured_img": img,
            }

        if self.current_q_hash is None:
            # First question initialized
            self.current_q_hash = new_hash
            self.current_dwell_sec = delta_sec

            # Check if OCR can identify initial question number
            detected_num = self.detect_question_number_from_image(img)
            if detected_num and detected_num > 0:
                self.current_q_index = detected_num

            self.question_history.append(
                {
                    "index": self.current_q_index,
                    "hash": new_hash,
                    "dwell": self.current_dwell_sec,
                    "is_guessed": False,
                }
            )
        else:
            diff = self.current_q_hash - new_hash  # Hamming distance

            # Optional OCR check for direct question detection
            ocr_detected_q = self.detect_question_number_from_image(img)

            if diff <= self.hamming_threshold and (not ocr_detected_q or ocr_detected_q == self.current_q_index):
                # Same question: accumulate dwell
                self.candidate_switch_count = 0
                self.candidate_switch_hash = None
                self.current_dwell_sec += delta_sec
                for q in reversed(self.question_history):
                    if q["index"] == self.current_q_index:
                        q["dwell"] = self.current_dwell_sec
                        break
            else:
                # Question switch confirmed!
                self.candidate_switch_count = 0
                self.candidate_switch_hash = None
                switched = True
                prev_q_index = self.current_q_index
                prev_dwell = self.current_dwell_sec
                ocr_differs = (ocr_detected_q is not None and ocr_detected_q != self.current_q_index)

                # Record whether previous question was guessed (< 12s)
                if prev_dwell < self.guess_threshold_sec:
                    is_guessed = True

                # Update history entry for previous question
                for q in reversed(self.question_history):
                    if q["index"] == prev_q_index:
                        q["dwell"] = prev_dwell
                        if is_guessed:
                            q["is_guessed"] = True
                        break

                # Determine next question number:
                if ocr_differs and ocr_detected_q:
                    next_q_num = ocr_detected_q
                else:
                    # Check if hash matches an earlier question in the session (user navigating back)
                    matched_entry = None
                    for past_q in reversed(self.question_history):
                        if past_q["index"] != prev_q_index and past_q["hash"] - new_hash <= self.hamming_threshold:
                            matched_entry = past_q
                            break

                    if matched_entry is not None:
                        next_q_num = matched_entry["index"]
                    else:
                        max_idx = max((q["index"] for q in self.question_history), default=0)
                        next_q_num = max_idx + 1

                # Check if next_q_num already exists in history
                existing_entry = None
                for entry in self.question_history:
                    if entry["index"] == next_q_num:
                        existing_entry = entry
                        break

                self.current_q_index = next_q_num
                self.current_q_hash = new_hash

                if existing_entry is not None:
                    self.current_dwell_sec = existing_entry["dwell"] + delta_sec
                    existing_entry["dwell"] = self.current_dwell_sec
                else:
                    self.current_dwell_sec = delta_sec
                    self.question_history.append(
                        {
                            "index": self.current_q_index,
                            "hash": new_hash,
                            "dwell": self.current_dwell_sec,
                            "is_guessed": False,
                        }
                    )

        # Check for time-sink condition
        if self.current_dwell_sec > limit:
            is_timesink = True

        result = {
            "question_index": self.current_q_index,
            "prev_question_index": prev_q_index if switched else None,
            "prev_dwell_sec": prev_dwell if switched else 0.0,
            "dwell_sec": self.current_dwell_sec,
            "switched": switched,
            "is_guessed": is_guessed,
            "is_timesink": is_timesink,
            "cumulative_sec": self.session_elapsed_sec,
            "time_limit": limit,
            "flagged": self.current_q_index in self.flagged_questions,
            "captured_img": img,
        }
        return result

    def toggle_flag(self, question_number: Optional[int] = None) -> bool:
        """Toggles the flag state of the current or specified question."""
        target = question_number if question_number is not None else self.current_q_index
        if target in self.flagged_questions:
            self.flagged_questions.remove(target)
            return False
        else:
            self.flagged_questions.add(target)
            return True

    def build_2x2_grid(
        self,
        items: List[Dict[str, Any]],
        out_path: str,
    ) -> str:
        """
        Stitches up to 4 question crops into a 1600x1200 JPEG.
        Each cell has a 36px solid black header strip with cyan (#38bdf8) text:
        [Q_NUM: XX] | [DWELL: Ys (TAG)] | [FLAGGED: True/False]
        Ensures low RAM by releasing buffers immediately.
        """
        canvas_w = 1600
        canvas_h = 1200
        cell_w = 800
        cell_h = 600
        header_h = 36

        # Create master black canvas
        grid_image = Image.new("RGB", (canvas_w, canvas_h), color=(15, 23, 42))
        draw = ImageDraw.Draw(grid_image)

        # Positions for 2x2 grid: (col, row)
        grid_coords = [
            (0, 0),
            (cell_w, 0),
            (0, cell_h),
            (cell_w, cell_h),
        ]

        # Font fallback
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            font = ImageFont.load_default()

        cyan_color = (56, 189, 248)  # #38bdf8
        black_color = (0, 0, 0)
        border_color = (30, 41, 59)

        for idx, item in enumerate(items[:4]):
            gx, gy = grid_coords[idx]

            # 1. Header Strip
            draw.rectangle(
                [gx, gy, gx + cell_w, gy + header_h],
                fill=black_color,
                outline=border_color,
            )

            # Metadata text
            q_num = item.get("question_number", item.get("q_num", idx + 1))
            dwell = round(float(item.get("dwell_time_sec", item.get("dwell", 0.0))), 1)
            tag = item.get("section_tag", item.get("tag", "GENERAL"))
            flagged = bool(item.get("user_flagged", item.get("flagged", False)))
            header_text = (
                f"[Q_NUM: {q_num:02d}] | [DWELL: {dwell}s ({tag})] | [FLAGGED: {flagged}]"
            )

            draw.text((gx + 12, gy + 8), header_text, fill=cyan_color, font=font)

            # 2. Crop Image Placement
            img_obj = item.get("image")
            img_path = item.get("image_path")

            crop: Optional[Image.Image] = None
            if img_obj is not None and isinstance(img_obj, Image.Image):
                crop = img_obj.copy()
            elif img_path and os.path.isfile(img_path):
                try:
                    with Image.open(img_path) as opened:
                        crop = opened.convert("RGB")
                except Exception as e:
                    logger.warning("Could not open image %s: %s", img_path, e)

            available_h = cell_h - header_h
            if crop is not None:
                crop.thumbnail((cell_w, available_h), Image.Resampling.LANCZOS)
                px = gx + (cell_w - crop.width) // 2
                py = gy + header_h + (available_h - crop.height) // 2
                grid_image.paste(crop, (px, py))
                crop.close()
            else:
                draw.text(
                    (gx + cell_w // 4, gy + header_h + available_h // 2),
                    "[Không có ảnh xem trước câu hỏi]",
                    fill=(148, 163, 184),
                    font=font,
                )

            # Outer cell border
            draw.rectangle(
                [gx, gy, gx + cell_w, gy + cell_h],
                outline=border_color,
                width=2,
            )

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        grid_image.save(out_path, format="JPEG", quality=88, optimize=True)
        grid_image.close()

        return out_path
