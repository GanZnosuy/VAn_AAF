-- TSA & IELTS Stealth HUD SQLite Schema
-- High-Performance Cognitive Training & Reflexion Database

PRAGMA foreign_keys = ON;

-- 1. Session Tracker
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

-- 2. Question Log Records
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

-- 3. Human Memory Cards (Spaced Repetition & Feynman Gatekeeper)
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

-- 4. AI Learned Rules (Self-Correction & Reflexion Loop)
CREATE TABLE IF NOT EXISTS ai_learned_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_profile TEXT NOT NULL,
    ai_mistake_summary TEXT,
    correction_rule TEXT,
    source_log_id INTEGER,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(source_log_id) REFERENCES question_logs(log_id) ON DELETE SET NULL
);

-- Indices for rapid querying
CREATE INDEX IF NOT EXISTS idx_question_logs_session ON question_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_cards_review ON human_memory_cards(next_review_date, repetition_step);
CREATE INDEX IF NOT EXISTS idx_ai_rules_profile ON ai_learned_rules(exam_profile);
