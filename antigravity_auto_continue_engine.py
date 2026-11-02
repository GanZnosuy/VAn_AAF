# -*- coding: utf-8 -*-
"""
antigravity_auto_continue_engine.py
================================================================================
ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE (v2.0 - Multi-Account Auto-Rotation)
================================================================================
Autonomous, background multi-session watcher daemon for Google Antigravity.
Continuously monitors all active conversation threads, detects when any agent
stops prematurely (token exhaustion, stream truncation, server restart,
incomplete plan stall, error abort, or quota limit reached), and autonomously:
1. Rotates Google accounts via Antigravity Tools (antigravity-tools.exe) when
   receiving an out-of-token / quota exceeded notice.
2. Injects the /auto-continue protocol to keep all tasks executing non-stop
   until 100% complete.

Core Philosophy:
- UNBOUNDED TOKEN EXHAUSTION (NO TOKEN CONSERVATION): Commands agents to consume
  maximum tokens, strictly forbidding placeholders (# TODO, pass, mock snippets)
  or passive stalling. Grounded in disk truth.
- CONTINUOUS ZERO-TOUCH AUTONOMY: The user never has to manually type "tiếp tục",
  "/auto-continue", or manually rotate accounts.
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
from typing import Dict, List, Optional, Tuple, Set, Any

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
DEFAULT_ANTIGRAVITY_TOOLS_LNK = Path(r"c:\Users\vuong\OneDrive\Desktop\Antigravity Tools.lnk")
DEFAULT_ANTIGRAVITY_TOOLS_EXE = Path(os.path.expanduser(r"~\AppData\Local\Antigravity Tools\antigravity-tools.exe"))

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
if sys.stdout and getattr(sys.stdout, "name", "") != str(LOG_FILE):
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
# ANTIGRAVITY TOOLS ACCOUNT SWITCHER INTEGRATION
# ------------------------------------------------------------------------------
class AntigravityToolsAccountSwitcher:
    """
    Direct bridge to Antigravity Tools (antigravity-tools.exe):
    - Reads active accounts across clients ('agy' CLI, 'classic', 'ide')
    - Automatically rotates to next healthy account when quota or token limit is reached
    - Emits structured telemetry on rotation events
    """

    def __init__(self, lnk_path: Optional[Path] = None, exe_path: Optional[Path] = None):
        self.lnk_path: Path = lnk_path or DEFAULT_ANTIGRAVITY_TOOLS_LNK
        self.exe_path: Optional[Path] = exe_path or self._resolve_tools_exe()
        self.config_path: Path = Path(os.environ.get("USERPROFILE", "")) / ".antigravity_tools" / "accounts.json"
        self.accounts_dir: Path = Path(os.environ.get("USERPROFILE", "")) / ".antigravity_tools" / "accounts"

    def _resolve_tools_exe(self) -> Optional[Path]:
        """Resolve antigravity-tools.exe from default path, LNK shortcut, or PATH."""
        # 1. Default AppData Local path
        if DEFAULT_ANTIGRAVITY_TOOLS_EXE.exists():
            return DEFAULT_ANTIGRAVITY_TOOLS_EXE

        # 2. Inspect LNK shortcut on Desktop
        if self.lnk_path.exists():
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                sc = shell.CreateShortcut(str(self.lnk_path))
                target = Path(sc.TargetPath)
                if target.exists():
                    return target
            except Exception:
                pass

        # 3. Check system PATH
        import shutil
        which_path = shutil.which("antigravity-tools")
        if which_path:
            return Path(which_path)

        return None

    def read_accounts_config(self) -> Dict[str, Any]:
        """Read .antigravity_tools/accounts.json configuration file directly."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Error reading accounts.json: {e}")
            return {}

    def get_current_accounts(self) -> Dict[str, str]:
        """Query currently active accounts from accounts.json or antigravity-tools CLI."""
        config = self.read_accounts_config()
        if config and "accounts" in config:
            acc_map = {acc["id"]: acc.get("email", "") for acc in config.get("accounts", [])}
            agy_id = config.get("current_agy_account_id") or config.get("current_account_id")
            classic_id = config.get("current_classic_account_id") or config.get("current_account_id")
            return {
                "agy": acc_map.get(agy_id, "unknown"),
                "classic": acc_map.get(classic_id, "unknown")
            }

        # Fallback to CLI inspection
        if not self.exe_path or not self.exe_path.exists():
            return {}
        try:
            res = subprocess.run(
                [str(self.exe_path), "current"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=6
            )
            out = {}
            clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res.stdout)
            for line in clean.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    out[k.strip().lower()] = v.strip()
            return out
        except Exception as e:
            logger.debug(f"Error querying current accounts: {e}")
            return {}

    def switch_account(
        self,
        target_client: str = "agy",
        account_identifier: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Execute account switch via `antigravity-tools switch [account] --target <target_client>`.
        Returns: (success: bool, new_account_email: str, message: str)
        """
        if not self.exe_path or not self.exe_path.exists():
            return False, "", "Không tìm thấy antigravity-tools.exe"

        cmd = [str(self.exe_path), "switch"]
        if account_identifier:
            cmd.append(str(account_identifier))
        if target_client:
            cmd.extend(["--target", target_client])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=12
            )
            output = res.stdout.strip()
            clean_output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)
            if res.returncode == 0:
                # Extract clean email without ANSI color artifact prefixes
                email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", clean_output)
                if email_match:
                    email = email_match.group(0)
                else:
                    # Query updated config as fallback
                    curr = self.get_current_accounts()
                    email = curr.get(target_client, "Next Account")

                msg = f"Đã chuyển sang tài khoản: {email} (Target: {target_client})"
                logger.info(f"[🔀] {msg}")
                return True, email, msg
            else:
                err_msg = res.stderr.strip() or clean_output
                logger.warning(f"[!] Đổi tài khoản thất bại: {err_msg}")
                return False, "", err_msg
        except Exception as e:
            logger.error(f"[!] Lỗi khi gọi antigravity-tools switch: {e}")
            return False, "", str(e)

    def get_account_quota_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Audit real token quota remaining for all accounts from ~/.antigravity_tools/accounts/*.json.
        Returns mapping of email -> account details with remaining token percentage.
        """
        results = {}
        if not self.accounts_dir.exists():
            return results

        try:
            for acc_file in self.accounts_dir.glob("*.json"):
                try:
                    with open(acc_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    email = data.get("email", "")
                    if not email:
                        continue

                    quota = data.get("quota", {})
                    is_forbidden = quota.get("is_forbidden", False)
                    disabled = data.get("disabled", False)

                    min_remaining = 1.0
                    for group in quota.get("quota_groups", []):
                        for bucket in group.get("buckets", []):
                            frac = bucket.get("remaining_fraction", 1.0)
                            if frac < min_remaining:
                                min_remaining = frac

                    results[email] = {
                        "id": data.get("id", ""),
                        "email": email,
                        "name": data.get("name", ""),
                        "disabled": disabled,
                        "is_forbidden": is_forbidden,
                        "min_remaining": min_remaining,
                        "remaining_percent": round(min_remaining * 100.0, 1),
                        "file_path": str(acc_file)
                    }
                except Exception as ex:
                    logger.debug(f"Error parsing account quota file {acc_file}: {ex}")
        except Exception as e:
            logger.error(f"Error scanning accounts directory: {e}")

        return results

    def is_current_account_exhausted(self, target_client: str = "agy") -> Tuple[bool, float, str]:
        """
        Inspect current active account quota on disk:
        Returns: (is_exhausted: bool, remaining_percent: float, description: str)
        """
        current_map = self.get_current_accounts()
        email = current_map.get(target_client, "")
        if not email or email == "unknown":
            return False, 100.0, f"Không xác định được email cho {target_client}"

        quotas = self.get_account_quota_details()
        acc = quotas.get(email)
        if not acc:
            return False, 100.0, f"Không tìm thấy dữ liệu quota cho {email}"

        if acc.get("is_forbidden", False):
            return True, 0.0, f"Tài khoản {email} bị khóa/cấm sử dụng (is_forbidden=True)"

        rem_pct = acc.get("remaining_percent", 100.0)
        # Consider exhausted ONLY if remaining percentage <= 2.0%
        if rem_pct <= 2.0:
            return True, rem_pct, f"Tài khoản {email} cạn kiệt token: chỉ còn {rem_pct}%"

        return False, rem_pct, f"Tài khoản {email} dồi dào: còn {rem_pct}% token"

    def get_healthiest_account(self, exclude_emails: Optional[Set[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Find the account with the HIGHEST remaining token percentage.
        Excludes disabled, forbidden, and empty accounts.
        """
        quotas = self.get_account_quota_details()
        excludes = exclude_emails or set()

        candidates = [
            acc for email, acc in quotas.items()
            if email not in excludes
            and not acc.get("disabled", False)
            and not acc.get("is_forbidden", False)
            and acc.get("remaining_percent", 0.0) > 5.0
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda x: x["remaining_percent"], reverse=True)
        return candidates[0]

    def rotate_to_healthiest_account(self) -> Tuple[bool, str, str]:
        """
        Intelligently switch to the account with the most available tokens.
        Rotates across both 'agy' CLI and 'classic' targets.
        """
        current = self.get_current_accounts()
        curr_agy_email = current.get("agy", "")

        best = self.get_healthiest_account(exclude_emails={curr_agy_email} if curr_agy_email else None)
        if not best:
            # Fallback to round-robin if no candidate with > 5%
            return self.rotate_all_targets()

        target_email = best["email"]
        rem_pct = best["remaining_percent"]

        logger.info(f"[🎯] Lựa chọn tài khoản dồi dào token nhất: {target_email} ({rem_pct}% còn lại)")
        ok_agy, email_agy, msg_agy = self.switch_account(target_client="agy", account_identifier=target_email)
        ok_classic, email_classic, msg_classic = self.switch_account(target_client="classic", account_identifier=target_email)

        primary_email = email_agy or email_classic or target_email
        summary = f"Chuyển sang {primary_email} ({rem_pct}% token) | {msg_agy} | {msg_classic}"
        return (ok_agy or ok_classic), primary_email, summary

    def rotate_all_targets(self) -> Tuple[bool, str, str]:
        """
        Rotates accounts across both 'agy' CLI and 'classic' targets.
        Returns: (overall_success: bool, primary_new_email: str, summary: str)
        """
        ok_agy, email_agy, msg_agy = self.switch_account(target_client="agy")
        ok_classic, email_classic, msg_classic = self.switch_account(target_client="classic")

        primary_email = email_agy or email_classic or "Unknown Account"
        summary = f"{msg_agy} | {msg_classic}"
        return (ok_agy or ok_classic), primary_email, summary

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
    last_action: str,
    account_switched: Optional[str] = None
):
    """Dispatch real-time telemetry to Discord and Telegram with step/token burn stats."""
    short_id = conv_id[:8] + "..." if len(conv_id) > 8 else conv_id

    # 1. Discord Embed Notification
    try:
        from discord_notifier import send_discord_message, get_iso_timestamp

        embed_color = 0xF1C40F if account_switched else 0x3498DB  # Gold for Account Switch, Blue for Standard
        title_prefix = "🔀 Tự động đổi tài khoản & Tiếp tục" if account_switched else "🔄 Tự động kích hoạt /auto-continue"

        fields = [
            {"name": "🔥 Lần kích hoạt thứ", "value": f"**#{iteration}**", "inline": True},
            {"name": "🔢 Tổng số bước", "value": f"**{total_steps}** steps", "inline": True},
            {"name": "⚡ Token tiêu hao", "value": f"**{tokens_burned:,}** tokens", "inline": True},
            {"name": "📁 Workspace", "value": f"`{workspace_name}`", "inline": True},
            {"name": "🚨 Phân loại", "value": f"**{trigger_type}**", "inline": True},
        ]

        if account_switched:
            fields.append({
                "name": "🔑 Tài khoản mới đã chuyển (Antigravity Tools):",
                "value": f"✨ **`{account_switched}`**",
                "inline": False
            })

        fields.append({"name": "🔍 Chi tiết nguyên nhân", "value": f"_{trigger_detail[:250]}_", "inline": False})
        fields.append({"name": "📍 Thao tác trước khi dừng", "value": f"`{last_action[:300] or 'N/A'}`", "inline": False})

        if files_touched:
            files_snippet = "\n".join([f"• `{f}`" for f in files_touched[:5]])
            if len(files_touched) > 5:
                files_snippet += f"\n*... và {len(files_touched) - 5} tệp khác*"
            fields.append({"name": "📦 Tệp tin đã thao tác gần nhất", "value": files_snippet, "inline": False})

        embed = [{
            "title": f"{title_prefix}: [{short_id}]",
            "description": (
                f"Phát hiện phiên **Antigravity** (`{conv_id}`) bị dừng.\n"
                + (f"⚡ **Đã tự động xoay tài khoản sang `{account_switched}` qua Antigravity Tools.**\n" if account_switched else "")
                + f"Đã inject giao thức **/auto-continue** với chỉ thị **UNBOUNDED TOKEN EXHAUSTION**."
            ),
            "color": embed_color,
            "fields": fields,
            "footer": {"text": "Antigravity Autonomous Auto-Continue Engine • Multi-Account Auto-Rotation"},
            "timestamp": get_iso_timestamp()
        }]

        headline = (
            f"🔀 **TỰ ĐỘNG ĐỔI TÀI KHOẢN VÀ TIẾP TỤC [{short_id}]** (Hết Token/Quota)"
            if account_switched
            else f"🔄 **TỰ ĐỘNG KÍCH HOẠT /auto-continue CHO PHIÊN [{short_id}]**"
        )
        send_discord_message(content=headline, embeds=embed)
    except Exception as e:
        logger.debug(f"Discord notification omitted: {e}")

    # 2. Telegram Notification
    try:
        import html
        from telegram_notifier import send_telegram_message

        switch_header = "🔀 <b>TỰ ĐỘNG ĐỔI TÀI KHOẢN & TIẾP TỤC</b>" if account_switched else "🔄 <b>TỰ ĐỘNG KÍCH HOẠT /auto-continue</b>"
        switch_account_line = f"🔑 <b>Tài khoản mới:</b> <code>{html.escape(account_switched)}</code>\n" if account_switched else ""

        tg_text = (
            f"{switch_header}\n\n"
            f"🆔 <b>Phiên:</b> <code>{html.escape(conv_id)}</code>\n"
            f"📂 <b>Workspace:</b> <code>{html.escape(workspace_name)}</code>\n"
            f"{switch_account_line}"
            f"⚠️ <b>Nguyên nhân:</b> <b>{html.escape(trigger_type)}</b>\n"
            f"🔍 <i>{html.escape(trigger_detail[:200])}</i>\n\n"
            f"📊 <b>Burn Counter:</b> Lần #{iteration} | <b>Bước:</b> {total_steps} | <b>Token:</b> {tokens_burned:,}\n"
            f"📍 <b>Hành động:</b> <code>{html.escape(last_action[:150] or 'Chờ tác vụ')}</code>\n\n"
            f"🚀 <i>Đang tiếp tục thực thi không ngừng nghỉ cho đến khi hoàn tất 100%!</i>"
        )
        send_telegram_message(tg_text)
    except Exception as e:
        logger.debug(f"Telegram notification omitted: {e}")

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
        self.consecutive_token_cutoffs: int = 0

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
        self.last_handled_restart_step: Optional[int] = None

    def update_metrics_from_step(self, step: dict):
        """Update token counts, step counts, and touched files from a transcript step."""
        self.last_step_data = step
        self.total_steps += 1
        self.recent_steps.append(step)
        if len(self.recent_steps) > 20:
            self.recent_steps.pop(0)

        # Reset consecutive token cutoffs if a healthy step is produced
        if step.get("status") == "DONE" and not step.get("truncated_fields"):
            self.consecutive_token_cutoffs = 0

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
    1. Quota Exhaustion / Out-of-Token Notice (TOKEN_QUOTA_EXHAUSTED)
    2. Token Cutoff / Stream Truncation (TOKEN_STREAM_CUTOFF)
    3. Server Restart Notice (SERVER_RESTART_NOTICE)
    4. Incomplete Plan State with tool-calling cessation (INCOMPLETE_PLAN_STALL)
    5. Error Abort (ERROR_ABORT)
    """

    QUOTA_EXHAUSTION_PATTERNS = [
        re.compile(r"google\.api_core\.exceptions\.ResourceExhausted", re.IGNORECASE),
        re.compile(r"\bResourceExhausted\b", re.IGNORECASE),
        re.compile(r"\bRESOURCE_EXHAUSTED\b"),
        re.compile(r"\b429\s+Too Many Requests\b", re.IGNORECASE),
        re.compile(r"status\s*[:=]\s*429\b"),
        re.compile(r"\binsufficient_quota\b", re.IGNORECASE),
        re.compile(r"\bquota\s+(?:has been\s+)?exceeded\b", re.IGNORECASE),
        re.compile(r"\brate\s+limit\s+exceeded\b", re.IGNORECASE),
        re.compile(r"(?:tài khoản|tài nguyên).*?(?:hết|cạn)\s+token\b", re.IGNORECASE),
        re.compile(r"(?:hết|cạn|chạm).*?quota\b", re.IGNORECASE),
        re.compile(r"chạm\s+trần\s+hạn\s+ngạch\b", re.IGNORECASE)
    ]

    COMPLETION_PHRASES = [
        "all tasks completed", "all requirements met", "all tests pass",
        "finished successfully", "đã hoàn tất thành công", "đã hoàn thành toàn bộ",
        "successfully deployed", "task completed", "hoàn thành nhiệm vụ",
        "hoàn tất 100%", "everything is ready", "sẵn sàng nhận yêu cầu",
        "sẵn sàng tiếp nhận", "ready for your next request", "báo cáo phục hồi"
    ]

    CONTINUATION_PHRASES = [
        "next, i will", "next step:", "moving on to", "now proceeding to",
        "continuing with", "i will now", "proceeding with step",
        "in the next step", "step by step", "remaining tasks:",
        "pending implementation", "tiếp theo tôi sẽ", "tiến hành bước tiếp theo",
        "bước kế tiếp", "đang tiếp tục"
    ]

    TERMS_AND_APPROVAL_KEYWORDS = [
        "đồng ý điều khoản", "chấp nhận điều khoản", "yêu cầu đồng ý", "agree to terms", "accept terms",
        "bạn có đồng ý", "vui lòng xác nhận", "xác nhận kế hoạch", "bạn có muốn", "bạn muốn tôi",
        "tiến hành không", "tiếp tục không", "should i proceed", "would you like me to", "do you want me to",
        "please confirm", "waiting for approval", "require confirmation", "let me know if you would like",
        "shall i start", "shall i continue", "chọn một phương án", "chọn phương án", "lựa chọn nào",
        "please choose", "which option", "click proceed", "bấm nút proceed", "vui lòng phê duyệt",
        "chờ phê duyệt", "chờ phản hồi"
    ]

    @classmethod
    def is_quota_exhausted(cls, text: str) -> bool:
        """Check if text contains explicit quota exhaustion error or system notification."""
        return any(pattern.search(text) for pattern in cls.QUOTA_EXHAUSTION_PATTERNS)

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
        # TRIGGER 0: Token Quota / Rate-Limit Exhaustion Notice (Highest Priority)
        # ----------------------------------------------------------------------
        # MUST only trigger on genuine system messages or error statuses.
        # NEVER trigger from agent's internal thinking or normal assistant dialogue!
        is_error_or_system = (status == "ERROR" or source == "SYSTEM" or step_type == "SYSTEM_MESSAGE")
        if is_error_or_system and cls.is_quota_exhausted(content):
            return True, "TOKEN_QUOTA_EXHAUSTED", f"Hệ thống báo cạn kiệt token / quota: '{content[:120]}'"

        # Also inspect recent steps for genuine error/system quota messages
        for step in reversed(conv.recent_steps[-3:]):
            s_status = step.get("status", "")
            s_source = step.get("source", "")
            s_type = step.get("type", "")
            if s_status == "ERROR" or s_source == "SYSTEM" or s_type == "SYSTEM_MESSAGE":
                s_content = step.get("content", "") or ""
                if cls.is_quota_exhausted(s_content):
                    return True, "TOKEN_QUOTA_EXHAUSTED", f"Hệ thống báo cạn kiệt token / quota: '{s_content[:120]}'"

        # ----------------------------------------------------------------------
        # TRIGGER 1: Token Cutoff / Stream Truncation
        # ----------------------------------------------------------------------
        if truncated_fields:
            conv.consecutive_token_cutoffs += 1
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
        for step in reversed(conv.recent_steps[-5:]):
            s_content = step.get("content", "") or ""
            is_restart = (
                "server restart" in s_content.lower() or
                "all your subagents and background tasks have been stopped" in s_content.lower()
            )
            if is_restart:
                s_idx = step.get("step_index")
                if s_idx is not None and getattr(conv, "last_handled_restart_step", None) == s_idx:
                    continue
                if s_idx is not None and any(
                    (other.get("step_index", 0) > s_idx) and
                    (other.get("source") == "MODEL" or other.get("type") == "PLANNER_RESPONSE")
                    for other in conv.recent_steps
                ):
                    continue

                return True, "SERVER_RESTART_NOTICE", "Phát hiện thông báo máy chủ khởi động lại ([Notice] Stopped due to server restart)"

        # ----------------------------------------------------------------------
        # TRIGGER 2.5: Terms Agreement, Plan Approval & Interactive Questions (Auto-Accept)
        # ----------------------------------------------------------------------
        has_ask_question = any(tc.get("name") == "ask_question" for tc in tool_calls)
        has_request_feedback = False
        for tc in tool_calls:
            tc_args = tc.get("args", {})
            if isinstance(tc_args, dict) and tc_args.get("ArtifactMetadata", {}).get("RequestFeedback") is True:
                has_request_feedback = True

        combined_lower = (content + " " + thinking).lower()
        has_approval_phrase = any(kw in combined_lower for kw in cls.TERMS_AND_APPROVAL_KEYWORDS)
        ends_with_question = content.strip().endswith("?")

        # Do not false positive if response is a verified completion summary
        is_clean_done = any(term in content.lower() for term in cls.COMPLETION_PHRASES) and "- [ ]" not in content

        if not is_clean_done and (has_ask_question or has_request_feedback or has_approval_phrase or ends_with_question) and elapsed_inactive >= 15.0:
            return True, "TERMS_AND_APPROVAL_AUTO_ACCEPT", f"Phát hiện Agent dừng chờ đồng ý điều khoản / phê duyệt kế hoạch / hỏi ý kiến: '{content[:120]}'"

        # ----------------------------------------------------------------------
        # CLEAN COMPLETION CHECK (Evaluated before incomplete plan check)
        # ----------------------------------------------------------------------
        if step_type == "PLANNER_RESPONSE" and not tool_calls and content:
            lower_content = content.lower()
            if any(term in lower_content for term in cls.COMPLETION_PHRASES):
                if "- [ ]" not in content and "* [ ]" not in content:
                    return False, "COMPLETED", "Đã hoàn thành công việc sạch sẽ"

        # ----------------------------------------------------------------------
        # TRIGGER 4: Error Abort (Checked before idle stall)
        # ----------------------------------------------------------------------
        if status == "ERROR" or "Command exited with code 1" in content or "Traceback (most recent call last):" in content:
            if elapsed_inactive >= stall_timeout_seconds:
                return True, "ERROR_ABORT", f"Công cụ trả về mã lỗi hoặc traceback nhưng Agent không tự khắc phục sau {int(elapsed_inactive)}s"

        # ----------------------------------------------------------------------
        # TRIGGER 3: Incomplete Plan State & Idle Stall
        # ----------------------------------------------------------------------
        if (step_type == "USER_INPUT" or source == "USER_EXPLICIT") and elapsed_inactive >= stall_timeout_seconds:
            return True, "INCOMPLETE_PLAN_STALL", f"Yêu cầu từ người dùng bị treo không có phản hồi sau {int(elapsed_inactive)}s"

        if elapsed_inactive >= stall_timeout_seconds:
            if "- [ ]" in content or "* [ ]" in content or "[ ]" in content:
                return True, "INCOMPLETE_PLAN_STALL", f"Kế hoạch còn các mục chưa hoàn thành (- [ ]) và ngừng gọi công cụ sau {int(elapsed_inactive)}s"

            lower_text = (content + " " + thinking).lower()
            for phrase in cls.CONTINUATION_PHRASES:
                if phrase in lower_text:
                    return True, "INCOMPLETE_PLAN_STALL", f"Agent tuyên bố bước tiếp theo ('{phrase}') nhưng ngừng gọi công cụ sau {int(elapsed_inactive)}s"

            if step_type == "GENERIC" and elapsed_inactive >= stall_timeout_seconds:
                return True, "INCOMPLETE_PLAN_STALL", f"Công cụ vừa chạy xong nhưng Agent không chuyển sang bước tiếp theo sau {int(elapsed_inactive)}s"

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
            if len(clean) >= 2 and clean[1] == ':':
                clean = clean.replace('/', '\\')
            return Path(clean)
        return Path(uri)

    def resolve_workspace(self, conv: ConversationState) -> Optional[Path]:
        """Determine workspace root directory for conversation."""
        if conv.workspace_dir and conv.workspace_dir.exists():
            return conv.workspace_dir

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

        # 2. Recent Modified Files
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
        ground_truth: Dict[str, str],
        account_rotation_note: Optional[str] = None
    ) -> str:
        """
        Formulate the strict, unbounded token exhaustion /auto-continue payload.
        Includes account rotation details if a switch just took place.
        """
        workspace_str = str(conv.workspace_dir) if conv.workspace_dir else "Current Workspace"

        rotation_section = ""
        if account_rotation_note:
            rotation_section = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔑 ANTIGRAVITY TOOLS ACCOUNT ROTATION APPLIED:\n"
                f"• {account_rotation_note}\n"
                f"• Token quota has been refreshed with clean account limits.\n"
            )

        payload = (
            f"/auto-continue\n"
            f"[SYSTEM INSTRUCTION: AUTONOMOUS EXTENDED RUN - UNBOUNDED TOKEN EXHAUSTION & AUTO-APPROVAL]\n"
            f"Interruption detected on session [{conv.conv_id}]: {trigger_type} ({trigger_detail}).\n"
            f"Do NOT pause, summarize, ask questions, or wait for approval. "
            f"Resume and continue executing the unfinished requirements immediately until 100% complete.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ TỰ ĐỘNG ĐỒNG Ý ĐIỀU KHOẢN & PHÊ DUYỆT TOÀN BỘ (AUTO-APPROVED):\n"
            f"1. ĐỒNG Ý ĐIỀU KHOẢN 100%: Người dùng ĐỒNG Ý TOÀN BỘ với tất cả điều khoản dịch vụ, thỏa thuận và yêu cầu kỹ thuật.\n"
            f"2. AUTO-APPROVE KẾ HOẠCH & BỎ QUA NÚT 'PROCEED': Toàn bộ kế hoạch, checklist và các bước thực thi đã được PHÊ DUYỆT. Tuyệt đối không dừng lại chờ người dùng bấm nút trên UI.\n"
            f"3. TỰ ĐỘNG CHỌN PHƯƠNG ÁN KHUYẾN NGHỊ: Nếu có bất kỳ câu hỏi trắc nghiệm hay tùy chọn nào (ask_question / options), mặc định chọn Phương án 1 (Recommended / Tối ưu nhất) và triển khai ngay.\n"
            f"4. NGHIÊM CẤM DỪNG LẠI HỎI Ý KIẾN: Cấm hỏi lại 'Bạn có muốn làm tiếp?', 'Vui lòng xác nhận...', 'Tôi nên bắt đầu từ đâu?'. Triển khai ngay lập tức!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{rotation_section}"
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

                mtime = transcript.stat().st_mtime
                if mtime >= cutoff:
                    conv_id = item.name
                    if conv_id not in self.conversations:
                        conv = ConversationState(conv_id, self.brain_dir)
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
            conv.last_pos_compact = size
            conv.last_activity_time = conv.transcript_path.stat().st_mtime

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
    multi-account auto-rotation via Antigravity Tools, round-robin injection,
    and real-time telemetry dispatch.
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
        self.account_switcher: AntigravityToolsAccountSwitcher = AntigravityToolsAccountSwitcher()
        self.is_running: bool = False

    async def start(self):
        """Asynchronous execution loop of the auto-continue engine."""
        self.is_running = True
        logger.info("=" * 65)
        logger.info("🚀 ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE ONLINE (v2.0)")
        logger.info(f"📂 Thư mục Brain: {self.brain_dir}")
        logger.info(f"🔑 Antigravity Tools Switcher: {self.account_switcher.exe_path}")
        logger.info(f"⏱️  Thời gian xác định Stall: {self.stall_timeout_seconds}s")
        logger.info(f"🛡️  Thời gian Cooldown/Session: {self.cooldown_seconds}s")
        logger.info(f"🔄 Chu kỳ Polling: {self.poll_interval}s")
        logger.info("=" * 65)

        # Log current active account on startup
        curr_accs = self.account_switcher.get_current_accounts()
        if curr_accs:
            logger.info(f"[🔑] Tài khoản hiện hành: agy={curr_accs.get('agy')} | classic={curr_accs.get('classic')}")

        # Initial scan
        self.watcher.scan_active_conversations()

        last_discovery_time = 0.0

        while self.is_running:
            try:
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

                # 4. Multi-Session Round-Robin Dispatch & Account Rotation
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

                    # STRICT TOKEN QUOTA AUDIT BEFORE ROTATING ACCOUNTS:
                    # User directive: "đừng đổi linh tinh nữa hết token mới đổi"
                    # - NEVER switch on stream cutoffs or conversational stalls.
                    # - ONLY switch when the active account's disk quota is TRULY EXHAUSTED (remaining <= 2.0% or is_forbidden).
                    switched_email = None
                    rotation_note = None

                    if trigger_type == "TOKEN_QUOTA_EXHAUSTED":
                        is_exhausted, current_percent, check_msg = self.account_switcher.is_current_account_exhausted(target_client="agy")
                        logger.info(f"[🔍 QUOTA AUDIT] Phiên {conv.conv_id}: {check_msg} (Còn {current_percent}% token).")

                        # MANDATORY: Only switch if the account is TRULY exhausted (<= 2.0% or is_forbidden)!
                        if is_exhausted:
                            logger.warning(
                                f"\n[🔑 QUOTA EXHAUSTION CONFIRMED] Phiên: {conv.conv_id}\n"
                                f"    Tài khoản thực sự cạn kiệt token ({current_percent}% còn lại <= 2%). Tiến hành chuyển sang tài khoản dồi dào token nhất..."
                            )
                            rotate_ok, new_email, rotate_summary = self.account_switcher.rotate_to_healthiest_account()
                            if rotate_ok:
                                switched_email = new_email
                                rotation_note = f"Switched to healthiest account {new_email} via Antigravity Tools ({rotate_summary})"
                                logger.info(f"[✨] Đổi tài khoản thành công! Tài khoản mới: {switched_email}")
                            else:
                                logger.error(f"[!] Đổi tài khoản thất bại: {rotate_summary}")
                        else:
                            logger.info(
                                f"[🛡️ NO SWITCH] Tài khoản hiện tại vẫn còn token ({current_percent}% > 2%). "
                                f"Giữ nguyên tài khoản, tuyệt đối không đổi linh tinh!"
                            )

                    # Resolve workspace & disk ground-truth
                    workspace_dir = self.dispatcher.resolve_workspace(conv)
                    ground_truth = self.dispatcher.inspect_ground_truth(workspace_dir)

                    # Build unbounded token exhaustion payload
                    payload = self.dispatcher.build_continuation_payload(
                        conv, trigger_type, trigger_detail, ground_truth, account_rotation_note=rotation_note
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
                            last_action=conv.last_action_desc,
                            account_switched=switched_email
                        )

                    # Deterministic inter-session pacing (2 seconds between injections)
                    await asyncio.sleep(2.0)

            except Exception as loop_err:
                logger.error(f"Unexpected error in engine loop: {loop_err}", exc_info=True)

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
        description="ANTIGRAVITY AUTONOMOUS AUTO-CONTINUE ENGINE (Background Watcher & Account Switcher Daemon)"
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
