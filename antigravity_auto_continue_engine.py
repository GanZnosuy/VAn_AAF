# -*- coding: utf-8 -*-
"""
antigravity_auto_continue_engine.py
================================================================================
ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE (v1.0 - Industrial Production Grade)
================================================================================
Autonomous, background multi-session watcher daemon for Google Antigravity.
Continuously monitors all active conversation threads, detects when any agent
stops prematurely (token exhaustion, stream truncation, server restart,
incomplete plan stall, or error abort), and autonomously injects the
/auto-continue protocol to keep all tasks executing non-stop until 100% complete.

Core Philosophy:
- UNBOUNDED TOKEN EXHAUSTION (NO TOKEN CONSERVATION): Commands agents to consume
  maximum tokens, strictly forbidding placeholders (# TODO, pass, mock snippets)
  or passive stalling. Grounded in disk truth.
- CONTINUOUS ZERO-TOUCH AUTONOMY: The user never has to manually type "tiếp tục"
  or "/auto-continue".
================================================================================
"""

import os
import sys
import time
import json
import re
import glob
import uuid
import ctypes
import asyncio
import logging
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from typing import Dict, List, Optional, Tuple, Set

# ------------------------------------------------------------------------------
# PATH CONSTANTS & SAFE STREAMS SETUP (FOR PYTHONW.EXE DAEMON)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "auto_continue_engine.log"
DEFAULT_BRAIN_DIR = Path(os.path.expanduser(r"~\.gemini\antigravity\brain"))
DEFAULT_AGENTAPI_BAT = Path(os.path.expanduser(r"~\.gemini\antigravity\bin\agentapi.bat"))
DEFAULT_LANG_SERVER = Path(os.path.expanduser(r"~\AppData\Local\Programs\antigravity\resources\bin\language_server.exe"))

# Ensure UTF-8 output and redirect None streams when running under pythonw.exe
if sys.platform == "win32":
    if sys.stdout is None:
        try:
            sys.stdout = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stdout = open(os.devnull, "w")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:
            pass

    if sys.stderr is None:
        try:
            sys.stderr = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stderr = open(os.devnull, "w")
    else:
        try:
            sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:
            pass

# Configure structured logging
logger = logging.getLogger("AutoContinueEngine")
logger.setLevel(logging.INFO)

# File handler with UTF-8
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler (if stdout exists and not redirected to log)
if sys.stdout and sys.stdout.name != str(LOG_FILE):
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

# ------------------------------------------------------------------------------
# SINGLE-INSTANCE WINDOWS KERNEL MUTEX SHIELD
# ------------------------------------------------------------------------------
_MUTEX_HANDLE = None
MUTEX_NAME = "Global\\Antigravity_Autonomous_Auto_Continue_Engine_Mutex"

def acquire_single_instance_mutex(mutex_name: str = MUTEX_NAME) -> bool:
    """Ensure only a single instance of the auto-continue daemon runs at any time."""
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return True

    ERROR_ALREADY_EXISTS = 183
    _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_err = ctypes.windll.kernel32.GetLastError()
    if last_err == ERROR_ALREADY_EXISTS:
        logger.warning(f"[!] Một phiên Auto-Continue Engine khác đang hoạt động độc quyền (Mutex: {mutex_name}).")
        return False

    pid_file = LOG_DIR / "auto_continue_engine.pid"
    try:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    logger.info(f"[🛡️] Windows Single-Instance Mutex đã được kích hoạt thành công (PID: {os.getpid()}).")
    return True

# ------------------------------------------------------------------------------
# NOTIFICATION INTEGRATION (DISCORD & TELEGRAM)
# ------------------------------------------------------------------------------
def send_telemetry_notification(
    conv_id: str,
    trigger_type: str,
    trigger_detail: str,
    iteration: int,
    total_steps: int,
    tokens_burned: int,
    files_touched: List[str],
    workspace_name: str,
    last_action: str
):
    """Dispatch real-time telemetry to Discord and Telegram with step/token burn stats."""
    now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    short_id = conv_id[:8] + "..." if len(conv_id) > 8 else conv_id

    # 1. Discord Embed Notification
    try:
        from discord_notifier import send_discord_message, get_iso_timestamp
        fields = [
            {"name": "🔥 Lần kích hoạt thứ", "value": f"**#{iteration}**", "inline": True},
            {"name": "🔢 Tổng số bước", "value": f"**{total_steps}** steps", "inline": True},
            {"name": "⚡ Token tiêu hao", "value": f"**{tokens_burned:,}** tokens", "inline": True},
            {"name": "📁 Workspace", "value": f"`{workspace_name}`", "inline": True},
            {"name": "🚨 Phân loại gián đoạn", "value": f"**{trigger_type}**", "inline": True},
            {"name": "🔍 Chi tiết nguyên nhân", "value": f"_{trigger_detail[:250]}_", "inline": False},
            {"name": "📍 Thao tác trước khi dừng", "value": f"`{last_action[:300] or 'N/A'}`", "inline": False},
        ]
        if files_touched:
            files_snippet = "\n".join([f"• `{f}`" for f in files_touched[:5]])
            if len(files_touched) > 5:
                files_snippet += f"\n*... và {len(files_touched) - 5} tệp khác*"
            fields.append({"name": "📦 Tệp tin đã thao tác gần nhất", "value": files_snippet, "inline": False})

        embed = [{
            "title": f"🔄 Tự động kích hoạt /auto-continue: [{short_id}]",
            "description": (
                f"Phát hiện phiên **Antigravity** (`{conv_id}`) bị dừng giữa chừng.\n"
                f"Đã tự động inject giao thức **/auto-continue** với chỉ thị **UNBOUNDED TOKEN EXHAUSTION** "
                f"để tiếp tục chạy non-stop đến khi hoàn thành 100%!"
            ),
            "color": 0x3498DB,  # Vibrant Blue
            "fields": fields,
            "footer": {"text": "Antigravity Autonomous Auto-Continue Engine • Zero-Touch Daemon"},
            "timestamp": get_iso_timestamp()
        }]
        send_discord_message(
            content=f"🔄 **TỰ ĐỘNG KÍCH HOẠT /auto-continue CHO PHIÊN [{short_id}]** (Phát hiện cạn token / ngắt kết nối)",
            embeds=embed
        )
    except Exception as e:
        logger.debug(f"Discord notification omitted or failed: {e}")

    # 2. Telegram Notification
    try:
        import html
        from telegram_notifier import send_telegram_message
        tg_text = (
            f"🔄 <b>TỰ ĐỘNG KÍCH HOẠT /auto-continue</b>\n\n"
            f"🆔 <b>Phiên:</b> <code>{html.escape(conv_id)}</code>\n"
            f"📂 <b>Workspace:</b> <code>{html.escape(workspace_name)}</code>\n"
            f"⚠️ <b>Nguyên nhân:</b> <b>{html.escape(trigger_type)}</b>\n"
            f"🔍 <i>{html.escape(trigger_detail[:200])}</i>\n\n"
            f"📊 <b>Burn Counter:</b> Lần #{iteration} | <b>Bước:</b> {total_steps} | <b>Token:</b> {tokens_burned:,}\n"
            f"📍 <b>Hành động:</b> <code>{html.escape(last_action[:150] or 'Chờ tác vụ')}</code>\n\n"
            f"🚀 <i>Đang tiếp tục thực thi không ngừng nghỉ cho đến khi hoàn thành 100%!</i>"
        )
        send_telegram_message(tg_text)
    except Exception as e:
        logger.debug(f"Telegram notification omitted or failed: {e}")

# ------------------------------------------------------------------------------
# CONVERSATION STATE TRACKER
# ------------------------------------------------------------------------------
class ConversationState:
    """Tracks running state, metrics, and progress for a single conversation thread."""
    def __init__(self, conv_id: str, brain_dir: Path):
        self.conv_id: str = conv_id
        self.brain_path: Path = brain_dir / conv_id
        self.logs_dir: Path = self.brain_path / ".system_generated" / "logs"
        self.transcript_path: Path = self.logs_dir / "transcript.jsonl"
        self.transcript_full_path: Path = self.logs_dir / "transcript_full.jsonl"
        self.tasks_dir: Path = self.brain_path / ".system_generated" / "tasks"
        self.messages_dir: Path = self.brain_path / ".system_generated" / "messages"

        # Byte offsets for efficient tailing
        self.last_pos_compact: int = 0
        self.last_pos_full: int = 0

        # Timing and activity
        self.last_activity_time: float = time.time()
        self.last_injection_time: float = 0.0
        self.consecutive_injections: int = 0
        self.total_injections: int = 0

        # Steps and metrics
        self.total_steps: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cache_read_tokens: int = 0
        self.files_touched: Set[str] = set()
        self.recent_steps: List[dict] = []
        self.last_step_data: Optional[dict] = None
        self.last_action_desc: str = "Chưa có thao tác"

        # Ground-truth workspace binding
        self.workspace_dir: Optional[Path] = None
        self.workspace_name: str = "Unknown Workspace"

        # Lifecycle status
        self.status: str = "INITIALIZING"
        self.stall_reason: str = ""

    def update_metrics_from_step(self, step: dict):
        """Update token counts, step counts, and touched files from a transcript step."""
        self.last_step_data = step
        self.total_steps += 1
        self.recent_steps.append(step)
        if len(self.recent_steps) > 20:
            self.recent_steps.pop(0)

        # Token metrics
        self.total_input_tokens += step.get("input_tokens", 0)
        self.total_output_tokens += step.get("output_tokens", 0)
        self.total_cache_read_tokens += step.get("cache_read_tokens", 0)

        # Action descriptions & touched files
        tool_calls = step.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                summary = (args.get("toolSummary") or args.get("toolAction") or "").strip().strip('"')
                desc = f"`{name}`"
                if summary:
                    desc += f": {summary}"
                self.last_action_desc = desc

                # Collect files
                for key in ("Path", "TargetFile", "AbsolutePath", "path"):
                    val = args.get(key)
                    if val and isinstance(val, str):
                        self.files_touched.add(os.path.basename(val.strip('"')))

    def has_active_background_tasks(self, recency_seconds: float = 60.0) -> bool:
        """Check if any background task in .system_generated/tasks is actively writing logs."""
        if not self.tasks_dir.exists():
            return False
        now = time.time()
        try:
            for task_log in self.tasks_dir.glob("task-*.log"):
                if (now - task_log.stat().st_mtime) < recency_seconds:
                    return True
        except Exception:
            pass
        return False

# ------------------------------------------------------------------------------
# STOP-SIGNAL & INTERRUPTION CLASSIFIER
# ------------------------------------------------------------------------------
class InterruptionClassifier:
    """
    Heuristic engine detecting stop-signals, premature terminations, and stalls:
    1. Token Cutoff / Stream Truncation
    2. Server Restart Notice
    3. Incomplete Plan State (with tool-calling cessation > timeout)
    4. Error Abort
    """

    COMPLETION_PHRASES = [
        "all tasks completed", "all requirements met", "all tests pass",
        "finished successfully", "đã hoàn tất thành công", "đã hoàn thành toàn bộ",
        "successfully deployed", "task completed", "hoàn thành nhiệm vụ",
        "hoàn tất 100%", "everything is ready"
    ]

    CONTINUATION_PHRASES = [
        "next, i will", "next step:", "moving on to", "now proceeding to",
        "continuing with", "i will now", "proceeding with step",
        "in the next step", "step by step", "remaining tasks:",
        "pending implementation", "tiếp theo tôi sẽ", "tiến hành bước tiếp theo",
        "bước kế tiếp", "đang tiếp tục"
    ]

    @classmethod
    def classify(
        cls,
        conv: ConversationState,
        stall_timeout_seconds: float = 45.0
    ) -> Tuple[bool, str, str]:
        """
        Evaluate conversation state. Returns:
        (is_stalled: bool, trigger_type: str, trigger_detail: str)
        """
        now = time.time()
        elapsed_inactive = now - conv.last_activity_time

        # If very recent activity (< 5 seconds), let it run
        if elapsed_inactive < 5.0:
            return False, "ACTIVE", "Đang xử lý tích cực"

        # Check if background tasks are actively executing/logging
        if conv.has_active_background_tasks(recency_seconds=60.0):
            return False, "WAITING_BG_TASK", "Đang chờ tác vụ nền (background task) hoàn thành"

        last_step = conv.last_step_data
        if not last_step:
            return False, "EMPTY", "Chưa có bước thực thi"

        step_type = last_step.get("type", "")
        source = last_step.get("source", "")
        status = last_step.get("status", "")
        content = last_step.get("content", "") or ""
        thinking = last_step.get("thinking", "") or ""
        tool_calls = last_step.get("tool_calls", [])
        truncated_fields = last_step.get("truncated_fields", [])

        # ----------------------------------------------------------------------
        # TRIGGER 1: Token Cutoff / Stream Truncation
        # ----------------------------------------------------------------------
        if truncated_fields:
            fields_str = ", ".join(truncated_fields)
            return True, "TOKEN_STREAM_CUTOFF", f"Trường dữ liệu bị cắt cụt do chạm giới hạn token: [{fields_str}]"

        # Check for unclosed markdown code blocks in content or thinking
        combined_text = content + "\n" + thinking
        if combined_text.count("```") % 2 == 1:
            return True, "TOKEN_STREAM_CUTOFF", "Nội dung phản hồi bị ngắt cụt giữa chừng (khối mã ``` chưa đóng)"

        # Check for trailing ellipses or abrupt endings in PLANNER_RESPONSE
        if step_type == "PLANNER_RESPONSE" and not tool_calls and content:
            stripped = content.rstrip()
            if stripped.endswith(("...", "…", "--", "-->", "\\")):
                return True, "TOKEN_STREAM_CUTOFF", f"Nội dung phản hồi kết thúc lửng lơ: '{stripped[-15:]}'"

        # ----------------------------------------------------------------------
        # TRIGGER 2: Server Restart Notice
        # ----------------------------------------------------------------------
        # Inspect recent steps for system restart alerts
        for step in reversed(conv.recent_steps[-5:]):
            s_type = step.get("type", "")
            s_content = step.get("content", "") or ""
            if "server restart" in s_content.lower():
                return True, "SERVER_RESTART_NOTICE", "Phát hiện thông báo máy chủ khởi động lại ([Notice] Stopped due to server restart)"
            if "all your subagents and background tasks have been stopped" in s_content.lower():
                return True, "SERVER_RESTART_NOTICE", "Toàn bộ subagent & background task bị dừng do máy chủ khởi động lại"

        # ----------------------------------------------------------------------
        # TRIGGER 4: Error Abort (Checked before idle stall)
        # ----------------------------------------------------------------------
        if status == "ERROR" or "Command exited with code 1" in content or "Traceback (most recent call last):" in content:
            if elapsed_inactive >= stall_timeout_seconds:
                # Agent stopped without self-healing
                return True, "ERROR_ABORT", f"Công cụ trả về mã lỗi hoặc traceback nhưng Agent không tự khắc phục sau {int(elapsed_inactive)}s"

        # ----------------------------------------------------------------------
        # TRIGGER 3: Incomplete Plan State & Idle Stall
        # ----------------------------------------------------------------------
        # Check if user input arrived but agent never started processing
        if (step_type == "USER_INPUT" or source == "USER_EXPLICIT") and elapsed_inactive >= stall_timeout_seconds:
            return True, "INCOMPLETE_PLAN_STALL", f"Yêu cầu từ người dùng bị treo không có phản hồi sau {int(elapsed_inactive)}s"

        # Check if agent stopped mid-plan with pending checklist items or continuation phrases
        if elapsed_inactive >= stall_timeout_seconds:
            # Check for uncompleted checkboxes
            if "- [ ]" in content or "* [ ]" in content or "[ ]" in content:
                return True, "INCOMPLETE_PLAN_STALL", f"Kế hoạch còn các mục chưa hoàn thành (- [ ]) và ngừng gọi công cụ sau {int(elapsed_inactive)}s"

            # Check for continuative forward-looking language
            lower_text = (content + " " + thinking).lower()
            for phrase in cls.CONTINUATION_PHRASES:
                if phrase in lower_text:
                    return True, "INCOMPLETE_PLAN_STALL", f"Agent tuyên bố bước tiếp theo ('{phrase}') nhưng ngừng gọi công cụ sau {int(elapsed_inactive)}s"

            # If last step was a tool call that completed, but agent never produced the next turn
            if step_type == "GENERIC" and elapsed_inactive >= stall_timeout_seconds:
                return True, "INCOMPLETE_PLAN_STALL", f"Công cụ vừa chạy xong nhưng Agent không chuyển sang bước tiếp theo sau {int(elapsed_inactive)}s"

        # ----------------------------------------------------------------------
        # CLEAN COMPLETION CHECK
        # ----------------------------------------------------------------------
        if step_type == "PLANNER_RESPONSE" and not tool_calls and content:
            lower_content = content.lower()
            if any(term in lower_content for term in cls.COMPLETION_PHRASES):
                if "- [ ]" not in content:
                    return False, "COMPLETED", "Đã hoàn thành công việc sạch sẽ"

        return False, "IDLE", "Đang chờ lệnh mới hoặc hoàn tất hợp lệ"

# ------------------------------------------------------------------------------
# GROUND-TRUTH WORKSPACE INSPECTOR & CONTINUATION DISPATCHER
# ------------------------------------------------------------------------------
class ContinuationDispatcher:
    """Inspects workspace ground truth and injects the /auto-continue payload."""

    def __init__(self, agentapi_cmd: Optional[List[str]] = None):
        self.agentapi_cmd: Optional[List[str]] = agentapi_cmd or self._detect_agentapi()

    @staticmethod
    def _detect_agentapi() -> Optional[List[str]]:
        """Find agentapi CLI executable."""
        if DEFAULT_AGENTAPI_BAT.exists():
            return [str(DEFAULT_AGENTAPI_BAT)]
        if DEFAULT_LANG_SERVER.exists():
            return [str(DEFAULT_LANG_SERVER), "agentapi"]
        return None

    @staticmethod
    def uri_to_path(uri: str) -> Optional[Path]:
        """Convert a file:/// URI to a valid local Windows Path."""
        if not uri:
            return None
        if uri.startswith("file:///"):
            clean = unquote(uri[8:])
            # Handle Windows drive letters like c:/...
            if len(clean) >= 2 and clean[1] == ':':
                clean = clean.replace('/', '\\')
            return Path(clean)
        return Path(uri)

    def resolve_workspace(self, conv: ConversationState) -> Optional[Path]:
        """Determine workspace root directory for conversation."""
        if conv.workspace_dir and conv.workspace_dir.exists():
            return conv.workspace_dir

        # Method 1: Query agentapi get-conversation-metadata
        if self.agentapi_cmd:
            try:
                cmd = self.agentapi_cmd + ["get-conversation-metadata", conv.conv_id]
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=10)
                if res.returncode == 0 and res.stdout:
                    data = json.loads(res.stdout)
                    workspaces = data.get("response", {}).get("conversationMetadata", {}).get("metadata", {}).get("workspaces", [])
                    if workspaces:
                        uri = workspaces[0].get("workspaceFolderAbsoluteUri", "")
                        resolved = self.uri_to_path(uri)
                        if resolved and resolved.exists():
                            conv.workspace_dir = resolved
                            conv.workspace_name = resolved.name
                            return resolved
            except Exception as e:
                logger.debug(f"agentapi metadata query failed for {conv.conv_id}: {e}")

        # Method 2: Fallback to current working directory if match
        cwd = Path.cwd()
        if (conv.brain_path / "scratch").exists():
            conv.workspace_dir = cwd
            conv.workspace_name = cwd.name
            return cwd

        return None

    def inspect_ground_truth(self, workspace_dir: Optional[Path]) -> Dict[str, str]:
        """Audit git status, modified files, and error logs directly from disk."""
        ground_truth = {
            "git_status": "Không có Git repository",
            "recent_modified": "Không phát hiện tệp mới sửa",
            "error_logs": "Không phát hiện file lỗi"
        }

        if not workspace_dir or not workspace_dir.exists():
            return ground_truth

        # 1. Git Status Audit
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(workspace_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                ground_truth["git_status"] = "\n".join(lines[:8])
                if len(lines) > 8:
                    ground_truth["git_status"] += f"\n... và {len(lines) - 8} thay đổi khác"
            elif res.returncode == 0:
                ground_truth["git_status"] = "Git working tree clean (đã commit hoặc không có diff chưa lưu)"
        except Exception:
            pass

        # 2. Recent Modified Files (last 1 hour, ignoring hidden/venv)
        try:
            now = time.time()
            modified = []
            for item in workspace_dir.glob("*"):
                if item.name.startswith((".", "node_modules", "venv", "__pycache__")):
                    continue
                if item.is_file() and (now - item.stat().st_mtime) < 3600:
                    modified.append(item.name)
            if modified:
                ground_truth["recent_modified"] = ", ".join(modified[:8])
        except Exception:
            pass

        return ground_truth

    def build_continuation_payload(
        self,
        conv: ConversationState,
        trigger_type: str,
        trigger_detail: str,
        ground_truth: Dict[str, str]
    ) -> str:
        """
        Formulate the strict, unbounded token exhaustion /auto-continue payload.
        Explicitly commands agent to consume maximum tokens without abbreviation.
        """
        workspace_str = str(conv.workspace_dir) if conv.workspace_dir else "Current Workspace"

        payload = (
            f"/auto-continue\n"
            f"[SYSTEM INSTRUCTION: AUTONOMOUS EXTENDED RUN - UNBOUNDED TOKEN EXHAUSTION]\n"
            f"Interruption detected on session [{conv.conv_id}]: {trigger_type} ({trigger_detail}).\n"
            f"Do NOT pause, summarize, ask questions, or wait for approval. "
            f"Resume and continue executing the unfinished requirements immediately until 100% complete.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 WORKSPACE GROUND-TRUTH (ON DISK):\n"
            f"• Workspace Directory: {workspace_str}\n"
            f"• Interrupted At Step: #{conv.total_steps}\n"
            f"• Last Action Before Stall: {conv.last_action_desc}\n"
            f"• Git Status Diffs:\n{ground_truth.get('git_status', 'N/A')}\n"
            f"• Recent Modified Files: {ground_truth.get('recent_modified', 'N/A')}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ UNBOUNDED TOKEN EXHAUSTION DIRECTIVE (MANDATORY):\n"
            f"1. MAXIMUM DEPTH: Consume all available context and token capacity. Provide complete, "
            f"exhaustive implementations. Never abbreviate or truncate.\n"
            f"2. ZERO PLACEHOLDERS: Strictly forbidden to output '# TODO', '// TODO', 'pass', or mock snippets.\n"
            f"3. CONTINUOUS AUTONOMY: Fix broken/partial code, implement the next production requirement, "
            f"run verification tests, and proceed relentlessly to the next step.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Bắt đầu thực thi ngay lập tức dựa trên sự thật ổ đĩa (Disk Truth)."
        )
        return payload

    def inject(self, conv: ConversationState, payload: str, trigger_type: str) -> bool:
        """
        Inject continuation payload via agentapi CLI, falling back to direct message drop.
        """
        title = f"/auto-continue [AUTONOMOUS EXTENDED RUN: {trigger_type}]"

        # Method 1: Primary agentapi send-message
        if self.agentapi_cmd:
            try:
                cmd = self.agentapi_cmd + [
                    "send-message",
                    f"--title={title}",
                    conv.conv_id,
                    payload
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=15
                )
                if res.returncode == 0 and "sendMessage" in res.stdout:
                    logger.info(f"[🚀] Inject thành công qua agentapi CLI cho phiên {conv.conv_id}")
                    return True
                else:
                    logger.warning(f"[!] agentapi send-message trả về: {res.stdout.strip()} (code: {res.returncode})")
            except Exception as e:
                logger.error(f"[!] Lỗi khi gọi agentapi send-message: {e}")

        # Method 2: Direct message JSON drop fallback
        try:
            if conv.messages_dir.exists():
                msg_id = str(uuid.uuid4())
                msg_data = {
                    "id": msg_id,
                    "recipient": conv.conv_id,
                    "sender": "antigravity_auto_continue_engine",
                    "priority": "MESSAGE_PRIORITY_HIGH",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "renderDetails": {
                        "messageTitle": title
                    },
                    "content": payload
                }
                msg_file = conv.messages_dir / f"{msg_id}.json"
                msg_file.write_text(json.dumps(msg_data, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info(f"[📁] Inject thành công qua Direct Message Drop: {msg_file.name}")
                return True
        except Exception as e:
            logger.error(f"[!] Lỗi khi ghi Direct Message Drop: {e}")

        return False

# ------------------------------------------------------------------------------
# MULTI-CONVERSATION DIRECTORY MONITOR (BRAIN WATCHER)
# ------------------------------------------------------------------------------
class BrainWatcher:
    """Monitors ~/.gemini/antigravity/brain/*/ asynchronously for multi-session tracking."""

    def __init__(
        self,
        brain_dir: Path = DEFAULT_BRAIN_DIR,
        scan_window_hours: float = 24.0
    ):
        self.brain_dir: Path = brain_dir
        self.scan_window_hours: float = scan_window_hours
        self.conversations: Dict[str, ConversationState] = {}

    def scan_active_conversations(self) -> List[str]:
        """Discover active or recently modified conversation folders in brain directory."""
        if not self.brain_dir.exists():
            return []

        now = time.time()
        cutoff = now - (self.scan_window_hours * 3600.0)
        discovered = []

        try:
            for item in self.brain_dir.iterdir():
                if not item.is_dir() or item.name.startswith(".") or item.name == "tempmediaStorage":
                    continue

                transcript = item / ".system_generated" / "logs" / "transcript.jsonl"
                if not transcript.exists():
                    continue

                # Check modification time of transcript or folder
                mtime = transcript.stat().st_mtime
                if mtime >= cutoff:
                    conv_id = item.name
                    if conv_id not in self.conversations:
                        conv = ConversationState(conv_id, self.brain_dir)
                        # Initialize position from end to tail new changes, or read initial state
                        self._initialize_conversation_state(conv)
                        self.conversations[conv_id] = conv
                        logger.info(f"[+] Đăng ký theo dõi phiên mới: {conv_id} (mtime: {datetime.fromtimestamp(mtime).strftime('%H:%M:%S')})")
                    discovered.append(conv_id)
        except Exception as e:
            logger.error(f"Error scanning brain directory: {e}")

        return discovered

    def _initialize_conversation_state(self, conv: ConversationState):
        """Read initial transcript lines to populate baseline step metrics."""
        if not conv.transcript_path.exists():
            return
        try:
            size = conv.transcript_path.stat().st_size
            conv.last_pos_compact = size  # Point to end for real-time delta tracking
            conv.last_activity_time = conv.transcript_path.stat().st_mtime

            # Read the last 15 lines to initialize recent steps & tokens
            with open(conv.transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                conv.total_steps = len(lines)
                for line in lines[-15:]:
                    line = line.strip()
                    if line:
                        try:
                            step = json.loads(line)
                            conv.update_metrics_from_step(step)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Error initializing state for {conv.conv_id}: {e}")

    def poll_updates(self, conv_id: str) -> bool:
        """Poll and process newly appended lines for a specific conversation."""
        conv = self.conversations.get(conv_id)
        if not conv or not conv.transcript_path.exists():
            return False

        try:
            current_size = conv.transcript_path.stat().st_size
            if current_size < conv.last_pos_compact:
                logger.info(f"[i] File transcript bị reset cho phiên {conv_id}, đọc lại từ đầu.")
                conv.last_pos_compact = 0

            if current_size == conv.last_pos_compact:
                return False

            with open(conv.transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(conv.last_pos_compact)
                new_lines = f.readlines()
                conv.last_pos_compact = f.tell()

            if new_lines:
                conv.last_activity_time = time.time()
                for line in new_lines:
                    line = line.strip()
                    if line:
                        try:
                            step = json.loads(line)
                            conv.update_metrics_from_step(step)
                        except Exception:
                            pass
                return True
        except Exception as e:
            logger.debug(f"Error polling updates for {conv_id}: {e}")

        return False

# ------------------------------------------------------------------------------
# AUTONOMOUS AUTO-CONTINUE ENGINE (MAIN DAEMON)
# ------------------------------------------------------------------------------
class AntigravityAutoContinueEngine:
    """
    Main autonomous engine coordinating directory watching, state classification,
    round-robin continuation injection, and real-time telemetry dispatch.
    """

    def __init__(
        self,
        brain_dir: Path = DEFAULT_BRAIN_DIR,
        scan_window_hours: float = 24.0,
        stall_timeout_seconds: float = 45.0,
        cooldown_seconds: float = 45.0,
        poll_interval: float = 2.0,
        max_consecutive_injections: int = 10
    ):
        self.brain_dir: Path = brain_dir
        self.stall_timeout_seconds: float = stall_timeout_seconds
        self.cooldown_seconds: float = cooldown_seconds
        self.poll_interval: float = poll_interval
        self.max_consecutive_injections: int = max_consecutive_injections

        self.watcher: BrainWatcher = BrainWatcher(brain_dir, scan_window_hours)
        self.dispatcher: ContinuationDispatcher = ContinuationDispatcher()
        self.is_running: bool = False

    async def start(self):
        """Asynchronous execution loop of the auto-continue engine."""
        self.is_running = True
        logger.info("=" * 60)
        logger.info("🚀 ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE ONLINE")
        logger.info(f"📂 Thư mục Brain: {self.brain_dir}")
        logger.info(f"⏱️  Thời gian xác định Stall: {self.stall_timeout_seconds}s")
        logger.info(f"🛡️  Thời gian Cooldown/Session: {self.cooldown_seconds}s")
        logger.info(f"🔄 Chu kỳ Polling: {self.poll_interval}s")
        logger.info("=" * 60)

        # Initial scan
        self.watcher.scan_active_conversations()

        last_discovery_time = 0.0

        while self.is_running:
            now = time.time()

            # 1. Periodic scan for new conversation directories (every 15s)
            if (now - last_discovery_time) > 15.0:
                self.watcher.scan_active_conversations()
                last_discovery_time = now

            # 2. Poll transcript updates across all tracked conversations
            for conv_id in list(self.watcher.conversations.keys()):
                self.watcher.poll_updates(conv_id)

            # 3. Classify conversations and identify stalled candidates
            stalled_candidates = []
            for conv_id, conv in self.watcher.conversations.items():
                is_stalled, trigger_type, trigger_detail = InterruptionClassifier.classify(
                    conv, stall_timeout_seconds=self.stall_timeout_seconds
                )
                if is_stalled:
                    conv.status = "STALLED_INCOMPLETE"
                    conv.stall_reason = f"{trigger_type}: {trigger_detail}"
                    stalled_candidates.append((conv, trigger_type, trigger_detail))

            # 4. Multi-Session Round-Robin Dispatch
            for conv, trigger_type, trigger_detail in stalled_candidates:
                # Check cooldown to prevent injection flood
                time_since_last_injection = now - conv.last_injection_time
                if time_since_last_injection < self.cooldown_seconds:
                    continue

                # Check max consecutive injection ceiling
                if conv.consecutive_injections >= self.max_consecutive_injections:
                    logger.warning(
                        f"[⚠️] Phiên {conv.conv_id} đã được inject {conv.consecutive_injections} lần "
                        f"liên tiếp mà không có phản hồi mới. Tạm ngưng để tránh spam."
                    )
                    continue

                # Resolve workspace & disk ground-truth
                workspace_dir = self.dispatcher.resolve_workspace(conv)
                ground_truth = self.dispatcher.inspect_ground_truth(workspace_dir)

                # Build unbounded token exhaustion payload
                payload = self.dispatcher.build_continuation_payload(
                    conv, trigger_type, trigger_detail, ground_truth
                )

                logger.warning(
                    f"\n[⚡ STALL PHÁT HIỆN] Phiên: {conv.conv_id} ({conv.workspace_name})\n"
                    f"    Nguyên nhân: {trigger_type} - {trigger_detail}\n"
                    f"    Thực hiện Inject /auto-continue lần #{conv.total_injections + 1}..."
                )

                # Inject continuation
                success = self.dispatcher.inject(conv, payload, trigger_type)
                if success:
                    conv.last_injection_time = time.time()
                    conv.consecutive_injections += 1
                    conv.total_injections += 1
                    conv.status = "REVIVED_EXECUTING"

                    # Dispatch real-time telemetry alert
                    send_telemetry_notification(
                        conv_id=conv.conv_id,
                        trigger_type=trigger_type,
                        trigger_detail=trigger_detail,
                        iteration=conv.total_injections,
                        total_steps=conv.total_steps,
                        tokens_burned=(conv.total_input_tokens + conv.total_output_tokens),
                        files_touched=list(conv.files_touched),
                        workspace_name=conv.workspace_name,
                        last_action=conv.last_action_desc
                    )

                # Deterministic inter-session pacing (2 seconds between injections)
                await asyncio.sleep(2.0)

            # Sleep for polling interval
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Signal engine to cease running gracefully."""
        self.is_running = False
        logger.info("[🛑] Nhận tín hiệu dừng Auto-Continue Engine.")

# ------------------------------------------------------------------------------
# CLI ENTRY POINT
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE (Background Watcher Daemon)"
    )
    parser.add_argument("--daemon", action="store_true", help="Chạy ở chế độ nền (daemon mode)")
    parser.add_argument("--scan-window", type=float, default=24.0, help="Số giờ quét lại các phiên gần nhất (mặc định: 24h)")
    parser.add_argument("--timeout", type=float, default=45.0, help="Số giây im lặng trước khi coi là Stall (mặc định: 45s)")
    parser.add_argument("--cooldown", type=float, default=45.0, help="Số giây chờ tối thiểu giữa các lần inject (mặc định: 45s)")
    parser.add_argument("--interval", type=float, default=2.0, help="Chu kỳ polling file transcript (mặc định: 2.0s)")
    parser.add_argument("--max-retry", type=int, default=10, help="Số lần inject tối đa cho một trạng thái stall (mặc định: 10)")

    args = parser.parse_args()

    # Enforce Windows single-instance mutex
    if not acquire_single_instance_mutex():
        sys.exit(0)

    engine = AntigravityAutoContinueEngine(
        brain_dir=DEFAULT_BRAIN_DIR,
        scan_window_hours=args.scan_window,
        stall_timeout_seconds=args.timeout,
        cooldown_seconds=args.cooldown,
        poll_interval=args.interval,
        max_consecutive_injections=args.max_retry
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(engine.start())
    except (KeyboardInterrupt, SystemExit):
        engine.stop()
    finally:
        loop.close()
        logger.info("[✓] Daemon đã dừng an toàn.")

if __name__ == "__main__":
    main()
