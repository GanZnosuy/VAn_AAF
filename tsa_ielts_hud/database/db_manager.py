"""Thread-safe SQLite Database Manager for TSA & IELTS Cognitive Training HUD."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class DatabaseManager:
    """
    Thread-safe SQLite Database Manager implementing CRUD operations,
    session tracking, and cognitive spaced repetition scheduling.
    """

    SPACED_REPETITION_INTERVALS = {
        1: 1,   # 1 day
        2: 3,   # 3 days
        3: 7,   # 7 days
        4: 14,  # 14 days
    }

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "hud_cognitive.db")
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection configured with row factory and pragmas."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables and schema indices."""
        schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
        with self._lock:
            conn = self._get_connection()
            try:
                if os.path.isfile(schema_file):
                    with open(schema_file, "r", encoding="utf-8") as f:
                        schema_sql = f.read()
                else:
                    schema_sql = """
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE IF NOT EXISTS exam_sessions (
                        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        exam_profile TEXT NOT NULL,
                        exam_name TEXT,
                        platform_name TEXT,
                        started_at TEXT DEFAULT (datetime('now', 'localtime')),
                        ended_at TEXT,
                        total_questions INTEGER DEFAULT 0,
                        wrong_count INTEGER DEFAULT 0,
                        timesink_count INTEGER DEFAULT 0,
                        guess_count INTEGER DEFAULT 0,
                        estimated_score REAL DEFAULT 0.0
                    );
                    CREATE TABLE IF NOT EXISTS question_logs (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        question_number INTEGER,
                        section_tag TEXT,
                        question_type TEXT,
                        dwell_time_sec REAL DEFAULT 0.0,
                        user_flagged INTEGER DEFAULT 0,
                        is_guessed INTEGER DEFAULT 0,
                        is_timesink INTEGER DEFAULT 0,
                        user_answer TEXT,
                        official_answer TEXT,
                        ai_initial_answer TEXT,
                        is_correct INTEGER DEFAULT 0,
                        question_img_path TEXT,
                        solution_img_path TEXT,
                        platform_explanation TEXT,
                        dom_selector TEXT,
                        FOREIGN KEY(session_id) REFERENCES exam_sessions(session_id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS human_memory_cards (
                        card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        log_id INTEGER NOT NULL,
                        exam_profile TEXT NOT NULL,
                        if_then_trigger TEXT,
                        trap_explanation TEXT,
                        paraphrase_mapping_json TEXT,
                        feynman_user_note TEXT,
                        twin_question_json TEXT,
                        twin_passed INTEGER DEFAULT 0,
                        repetition_step INTEGER DEFAULT 1,
                        next_review_date TEXT,
                        FOREIGN KEY(log_id) REFERENCES question_logs(log_id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS ai_learned_rules (
                        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        exam_profile TEXT NOT NULL,
                        ai_mistake_summary TEXT,
                        correction_rule TEXT,
                        source_log_id INTEGER,
                        created_at TEXT DEFAULT (datetime('now', 'localtime')),
                        FOREIGN KEY(source_log_id) REFERENCES question_logs(log_id) ON DELETE SET NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_question_logs_session ON question_logs(session_id);
                    CREATE INDEX IF NOT EXISTS idx_memory_cards_review ON human_memory_cards(next_review_date, repetition_step);
                    CREATE INDEX IF NOT EXISTS idx_ai_rules_profile ON ai_learned_rules(exam_profile);
                    """
                conn.executescript(schema_sql)
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def calculate_next_review(current_step: int, passed: bool) -> tuple[int, str]:
        """
        Calculates the new repetition step and next review timestamp.
        Formula:
          - Step 1 = 1 day
          - Step 2 = 3 days
          - Step 3 = 7 days
          - Step >= 4 = 14 days
          - If failed, step resets immediately to 1 (+1 day).
        """
        now = datetime.now()
        if passed:
            new_step = min(current_step + 1, 4)
            interval_days = DatabaseManager.SPACED_REPETITION_INTERVALS.get(new_step, 14)
        else:
            new_step = 1
            interval_days = DatabaseManager.SPACED_REPETITION_INTERVALS[1]

        next_date = (now + timedelta(days=interval_days)).strftime("%Y-%m-%d %H:%M:%S")
        return new_step, next_date

    # ==========================================
    # SESSION OPERATIONS
    # ==========================================

    def create_session(
        self,
        exam_profile: str,
        exam_name: Optional[str] = None,
        platform_name: Optional[str] = None,
    ) -> int:
        """Creates a new exam session record and returns its session_id."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO exam_sessions (exam_profile, exam_name, platform_name, started_at)
                    VALUES (?, ?, ?, datetime('now', 'localtime'))
                    """,
                    (exam_profile, exam_name or exam_profile, platform_name or "General"),
                )
                conn.commit()
                return int(cursor.lastrowid)
            finally:
                conn.close()

    def update_session(self, session_id: int, **kwargs: Any) -> bool:
        """Updates fields of an exam session (e.g. ended_at, wrong_count, estimated_score)."""
        if not kwargs:
            return False

        fields = []
        values = []
        for key, val in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(val)
        values.append(session_id)

        sql = f"UPDATE exam_sessions SET {', '.join(fields)} WHERE session_id = ?"

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def end_session(self, session_id: int) -> Dict[str, Any]:
        """Finalizes session, calculates aggregate metrics, and returns summary."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                # Aggregate metrics from question_logs
                cursor.execute(
                    """
                    SELECT 
                        COUNT(*) as total_questions,
                        SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as wrong_count,
                        SUM(CASE WHEN is_timesink = 1 THEN 1 ELSE 0 END) as timesink_count,
                        SUM(CASE WHEN is_guessed = 1 THEN 1 ELSE 0 END) as guess_count
                    FROM question_logs
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
                total = row["total_questions"] or 0
                wrong = row["wrong_count"] or 0
                timesink = row["timesink_count"] or 0
                guess = row["guess_count"] or 0
                correct = total - wrong
                score = round((correct / total * 100.0) if total > 0 else 0.0, 1)

                cursor.execute(
                    """
                    UPDATE exam_sessions
                    SET ended_at = datetime('now', 'localtime'),
                        total_questions = ?,
                        wrong_count = ?,
                        timesink_count = ?,
                        guess_count = ?,
                        estimated_score = ?
                    WHERE session_id = ?
                    """,
                    (total, wrong, timesink, guess, score, session_id),
                )
                conn.commit()
                return {
                    "session_id": session_id,
                    "total_questions": total,
                    "wrong_count": wrong,
                    "timesink_count": timesink,
                    "guess_count": guess,
                    "estimated_score": score,
                }
            finally:
                conn.close()

    def get_session_summary(self, session_id: int) -> Dict[str, Any]:
        """Fetches session metadata and aggregates."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM exam_sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return {}
                return dict(row)
            finally:
                conn.close()

    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent exam session."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM exam_sessions ORDER BY session_id DESC LIMIT 1")
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    # ==========================================
    # QUESTION LOG OPERATIONS
    # ==========================================

    def log_question_event(
        self,
        session_id: int,
        question_number: int,
        dwell_time_sec: float = 0.0,
        section_tag: Optional[str] = None,
        question_type: Optional[str] = None,
        user_flagged: int = 0,
        is_guessed: int = 0,
        is_timesink: int = 0,
        user_answer: Optional[str] = None,
        official_answer: Optional[str] = None,
        ai_initial_answer: Optional[str] = None,
        is_correct: int = 0,
        question_img_path: Optional[str] = None,
        solution_img_path: Optional[str] = None,
        platform_explanation: Optional[str] = None,
        dom_selector: Optional[str] = None,
    ) -> int:
        """Inserts or updates a question log entry."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT log_id FROM question_logs 
                    WHERE session_id = ? AND question_number = ?
                    """,
                    (session_id, question_number),
                )
                existing = cursor.fetchone()
                if existing:
                    log_id = existing["log_id"]
                    cursor.execute(
                        """
                        UPDATE question_logs
                        SET dwell_time_sec = ?, section_tag = COALESCE(?, section_tag),
                            question_type = COALESCE(?, question_type), user_flagged = ?,
                            is_guessed = ?, is_timesink = ?, user_answer = COALESCE(?, user_answer),
                            official_answer = COALESCE(?, official_answer),
                            ai_initial_answer = COALESCE(?, ai_initial_answer),
                            is_correct = ?, question_img_path = COALESCE(?, question_img_path),
                            solution_img_path = COALESCE(?, solution_img_path),
                            platform_explanation = COALESCE(?, platform_explanation),
                            dom_selector = COALESCE(?, dom_selector)
                        WHERE log_id = ?
                        """,
                        (
                            dwell_time_sec,
                            section_tag,
                            question_type,
                            user_flagged,
                            is_guessed,
                            is_timesink,
                            user_answer,
                            official_answer,
                            ai_initial_answer,
                            is_correct,
                            question_img_path,
                            solution_img_path,
                            platform_explanation,
                            dom_selector,
                            log_id,
                        ),
                    )
                    conn.commit()
                    return log_id
                else:
                    cursor.execute(
                        """
                        INSERT INTO question_logs (
                            session_id, question_number, section_tag, question_type,
                            dwell_time_sec, user_flagged, is_guessed, is_timesink,
                            user_answer, official_answer, ai_initial_answer, is_correct,
                            question_img_path, solution_img_path, platform_explanation, dom_selector
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            question_number,
                            section_tag,
                            question_type,
                            dwell_time_sec,
                            user_flagged,
                            is_guessed,
                            is_timesink,
                            user_answer,
                            official_answer,
                            ai_initial_answer,
                            is_correct,
                            question_img_path,
                            solution_img_path,
                            platform_explanation,
                            dom_selector,
                        ),
                    )
                    conn.commit()
                    return int(cursor.lastrowid)
            finally:
                conn.close()

    def save_scraped_results(
        self,
        session_id: int,
        questions_data: List[Dict[str, Any]],
    ) -> List[int]:
        """Saves a batch of post-exam scraped questions and updates session aggregates."""
        log_ids = []
        with self._lock:
            conn = self._get_connection()
            try:
                for q in questions_data:
                    q_num = q.get("question_number", 0)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT log_id, dwell_time_sec, user_flagged FROM question_logs
                        WHERE session_id = ? AND question_number = ?
                        """,
                        (session_id, q_num),
                    )
                    existing = cursor.fetchone()

                    dwell = q.get("dwell_time_sec", existing["dwell_time_sec"] if existing else 0.0)
                    flagged = q.get("user_flagged", existing["user_flagged"] if existing else 0)
                    is_correct = int(bool(q.get("is_correct", False)))
                    is_timesink = int(bool(q.get("is_timesink", False)))
                    is_guessed = int(bool(q.get("is_guessed", False)))

                    if existing:
                        log_id = existing["log_id"]
                        cursor.execute(
                            """
                            UPDATE question_logs
                            SET section_tag = COALESCE(?, section_tag),
                                question_type = COALESCE(?, question_type),
                                dwell_time_sec = ?,
                                user_flagged = ?,
                                is_guessed = ?,
                                is_timesink = ?,
                                user_answer = ?,
                                official_answer = ?,
                                ai_initial_answer = COALESCE(?, ai_initial_answer),
                                is_correct = ?,
                                question_img_path = COALESCE(?, question_img_path),
                                solution_img_path = COALESCE(?, solution_img_path),
                                platform_explanation = ?,
                                dom_selector = ?
                            WHERE log_id = ?
                            """,
                            (
                                q.get("section_tag"),
                                q.get("question_type"),
                                dwell,
                                flagged,
                                is_guessed,
                                is_timesink,
                                q.get("user_answer"),
                                q.get("official_answer"),
                                q.get("ai_initial_answer"),
                                is_correct,
                                q.get("question_img_path"),
                                q.get("solution_img_path"),
                                q.get("platform_explanation"),
                                q.get("dom_selector"),
                                log_id,
                            ),
                        )
                        log_ids.append(log_id)
                        q["log_id"] = log_id
                    else:
                        cursor.execute(
                            """
                            INSERT INTO question_logs (
                                session_id, question_number, section_tag, question_type,
                                dwell_time_sec, user_flagged, is_guessed, is_timesink,
                                user_answer, official_answer, ai_initial_answer, is_correct,
                                question_img_path, solution_img_path, platform_explanation, dom_selector
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                session_id,
                                q_num,
                                q.get("section_tag"),
                                q.get("question_type"),
                                dwell,
                                flagged,
                                is_guessed,
                                is_timesink,
                                q.get("user_answer"),
                                q.get("official_answer"),
                                q.get("ai_initial_answer"),
                                is_correct,
                                q.get("question_img_path"),
                                q.get("solution_img_path"),
                                q.get("platform_explanation"),
                                q.get("dom_selector"),
                            ),
                        )
                        new_log_id = int(cursor.lastrowid)
                        log_ids.append(new_log_id)
                        q["log_id"] = new_log_id

                conn.commit()
            finally:
                conn.close()

        # Update session totals
        self.end_session(session_id)
        return log_ids

    def get_session_wrong_questions(self, session_id: int) -> List[Dict[str, Any]]:
        """Returns all incorrect questions for a session with optional linked memory card."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT q.*, c.card_id, c.if_then_trigger, c.trap_explanation,
                           c.paraphrase_mapping_json, c.feynman_user_note,
                           c.twin_question_json, c.twin_passed, c.repetition_step, c.next_review_date
                    FROM question_logs q
                    LEFT JOIN human_memory_cards c ON q.log_id = c.log_id
                    WHERE q.session_id = ? AND q.is_correct = 0
                    ORDER BY q.question_number ASC
                    """,
                    (session_id,),
                )
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    item = dict(row)
                    if item.get("paraphrase_mapping_json"):
                        try:
                            item["paraphrase_mapping"] = json.loads(item["paraphrase_mapping_json"])
                        except Exception:
                            item["paraphrase_mapping"] = []
                    else:
                        item["paraphrase_mapping"] = []

                    if item.get("twin_question_json"):
                        try:
                            item["twin_question"] = json.loads(item["twin_question_json"])
                        except Exception:
                            item["twin_question"] = {}
                    else:
                        item["twin_question"] = {}

                    results.append(item)
                return results
            finally:
                conn.close()

    # ==========================================
    # HUMAN MEMORY CARD OPERATIONS (SPACED REPETITION)
    # ==========================================

    def save_memory_card(
        self,
        log_id: int,
        exam_profile: str,
        if_then_trigger: str,
        trap_explanation: str,
        paraphrase_mapping: Any,
        feynman_user_note: Optional[str] = None,
        twin_question: Optional[Any] = None,
        repetition_step: int = 1,
    ) -> int:
        """Creates or updates a Feynman memory card for a wrong question."""
        para_json = json.dumps(paraphrase_mapping, ensure_ascii=False) if not isinstance(paraphrase_mapping, str) else paraphrase_mapping
        twin_json = json.dumps(twin_question, ensure_ascii=False) if (twin_question and not isinstance(twin_question, str)) else (twin_question or "")

        now = datetime.now()
        interval = self.SPACED_REPETITION_INTERVALS.get(repetition_step, 1)
        next_date = (now + timedelta(days=interval)).strftime("%Y-%m-%d %H:%M:%S")

        feynman_note_val = feynman_user_note.strip() if (feynman_user_note and str(feynman_user_note).strip()) else None

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT card_id FROM human_memory_cards WHERE log_id = ?",
                    (log_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    card_id = existing["card_id"]
                    cursor.execute(
                        """
                        UPDATE human_memory_cards
                        SET exam_profile = ?, if_then_trigger = ?, trap_explanation = ?,
                            paraphrase_mapping_json = ?, feynman_user_note = COALESCE(?, feynman_user_note),
                            twin_question_json = ?, repetition_step = ?, next_review_date = ?
                        WHERE card_id = ?
                        """,
                        (
                            exam_profile,
                            if_then_trigger,
                            trap_explanation,
                            para_json,
                            feynman_note_val,
                            twin_json,
                            repetition_step,
                            next_date,
                            card_id,
                        ),
                    )
                    conn.commit()
                    return card_id
                else:
                    cursor.execute(
                        """
                        INSERT INTO human_memory_cards (
                            log_id, exam_profile, if_then_trigger, trap_explanation,
                            paraphrase_mapping_json, feynman_user_note, twin_question_json,
                            twin_passed, repetition_step, next_review_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            log_id,
                            exam_profile,
                            if_then_trigger,
                            trap_explanation,
                            para_json,
                            feynman_user_note or "",
                            twin_json,
                            repetition_step,
                            next_date,
                        ),
                    )
                    conn.commit()
                    return int(cursor.lastrowid)
            finally:
                conn.close()

    def update_feynman_note(self, card_id: int, note: str) -> bool:
        """Saves the user's active recall Feynman explanation note."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE human_memory_cards SET feynman_user_note = ? WHERE card_id = ?",
                    (note, card_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def update_twin_result(self, card_id: int, passed: bool) -> tuple[int, str]:
        """
        Updates the result of a twin challenge.
        Advances repetition step if passed; resets step to 1 if failed.
        Returns (new_step, next_review_date).
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT repetition_step FROM human_memory_cards WHERE card_id = ?",
                    (card_id,),
                )
                row = cursor.fetchone()
                current_step = row["repetition_step"] if row else 1

                new_step, next_date = self.calculate_next_review(current_step, passed)

                cursor.execute(
                    """
                    UPDATE human_memory_cards
                    SET twin_passed = ?, repetition_step = ?, next_review_date = ?
                    WHERE card_id = ?
                    """,
                    (1 if passed else 0, new_step, next_date, card_id),
                )
                conn.commit()
                return new_step, next_date
            finally:
                conn.close()

    def get_due_cards(
        self, profile: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Returns all memory cards scheduled for review on or before now."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = """
                    SELECT c.*, q.question_number, q.section_tag, q.user_answer, q.official_answer
                    FROM human_memory_cards c
                    JOIN question_logs q ON c.log_id = q.log_id
                    WHERE datetime(c.next_review_date) <= datetime('now', 'localtime')
                """
                params: list[Any] = []
                if profile:
                    query += " AND c.exam_profile = ?"
                    params.append(profile)

                query += " ORDER BY c.next_review_date ASC"
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                items = []
                for row in rows:
                    d = dict(row)
                    if d.get("twin_question_json"):
                        try:
                            d["twin_question"] = json.loads(d["twin_question_json"])
                        except Exception:
                            d["twin_question"] = {}
                    items.append(d)
                return items
            finally:
                conn.close()

    def get_card_by_id(self, card_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves card details by card_id with parsed JSON fields."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM human_memory_cards WHERE card_id = ?", (card_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                data = dict(row)
                if data.get("paraphrase_mapping_json"):
                    try:
                        data["paraphrase_mapping"] = json.loads(data["paraphrase_mapping_json"])
                    except Exception:
                        data["paraphrase_mapping"] = []
                else:
                    data["paraphrase_mapping"] = []

                if data.get("twin_question_json"):
                    try:
                        data["twin_question"] = json.loads(data["twin_question_json"])
                    except Exception:
                        data["twin_question"] = {}
                else:
                    data["twin_question"] = {}

                return data
            finally:
                conn.close()

    # ==========================================
    # AI LEARNED RULES (REFLEXION LOOP)
    # ==========================================

    def save_ai_learned_rule(
        self,
        exam_profile: str,
        ai_mistake_summary: str,
        correction_rule: str,
        source_log_id: Optional[int] = None,
    ) -> int:
        """Stores an AI-synthesized rule learned from an incorrect deduction."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ai_learned_rules (
                        exam_profile, ai_mistake_summary, correction_rule, source_log_id, created_at
                    ) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
                    """,
                    (exam_profile, ai_mistake_summary, correction_rule, source_log_id),
                )
                conn.commit()
                return int(cursor.lastrowid)
            finally:
                conn.close()

    def get_ai_rules(self, profile: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns the most recent AI-learned reflection rules for a profile."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT rule_id, exam_profile, ai_mistake_summary, correction_rule, source_log_id, created_at
                    FROM ai_learned_rules
                    WHERE exam_profile = ?
                    ORDER BY rule_id DESC
                    LIMIT ?
                    """,
                    (profile, limit),
                )
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
