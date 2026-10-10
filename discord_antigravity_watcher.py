# -*- coding: utf-8 -*-
"""
discord_antigravity_watcher.py
Watcher giam sat tien trinh Antigravity va tac vu he thong theo thoi gian thuc.
Tu dong doc transcript.jsonl de:
1. Gui thong bao Discord khi Agent hoan thanh cong viec (kem noi dung chi tiet, danh sach file da sua/tao).
2. Phat hien va gui canh bao khan cap khi Agent bi gian doan, mat ket noi, hoac gap loi nghiem trong.
"""

import os
import sys
import time
import json
import re
import argparse
from datetime import datetime
from pathlib import Path

from discord_notifier import (
    notify_task_completed,
    notify_interrupted_or_disconnected,
    send_discord_message
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

DEFAULT_BRAIN_DIR = Path(os.path.expanduser(r"~\.gemini\antigravity\brain"))

def find_latest_transcript(brain_dir: Path = DEFAULT_BRAIN_DIR) -> Path:
    """Tim file transcript.jsonl gan nhat trong thu muc brain."""
    if not brain_dir.exists():
        return None

    candidates = list(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
    if not candidates:
        return None

    # Sap xep theo thoi gian sua doi moi nhat
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]

def extract_user_goal(content: str) -> str:
    """Trich xuat muc tieu cua user tu the <USER_REQUEST>."""
    if not content:
        return "Yêu cầu từ người dùng"
    m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    else:
        raw = content.strip()
    
    # Lay toi da 3 dong dau hoac 200 ky tu
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    summary = " ".join(lines[:2])
    if len(summary) > 200:
        summary = summary[:197] + "..."
    return summary or "Yêu cầu từ người dùng"

def clean_agent_summary(content: str) -> str:
    """Lam sach noi dung phan hoi cua agent de hien thi ngan gon tren Discord."""
    if not content:
        return "Công việc đã được hoàn thành thành công."
    
    # Bo bot cac tag hoac block dai
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("```")]
    text_snippet = "\n".join(lines[:5])
    if len(text_snippet) > 400:
        text_snippet = text_snippet[:397] + "..."
    return text_snippet

class AntigravityWatcher:
    def __init__(self, transcript_path: Path, start_at_end: bool = True):
        self.transcript_path = transcript_path
        self.last_pos = 0
        self.current_user_prompt = ""
        self.turn_actions = []
        self.files_touched = set()
        self.in_turn = False
        self.last_activity_time = time.time()
        self.warned_stall = False

        if start_at_end and self.transcript_path.exists():
            self.last_pos = self.transcript_path.stat().st_size
            print(f"[i] Bat dau theo doi tu cuoi file (byte {self.last_pos})")
        else:
            self.last_pos = 0

    def check_updates(self):
        """Doc cac dong moi tu file transcript.jsonl."""
        if not self.transcript_path.exists():
            return

        current_size = self.transcript_path.stat().st_size
        if current_size < self.last_pos:
            # File bi reset hoac ghi de
            print("[i] File transcript bi reset, doc lai tu dau.")
            self.last_pos = 0

        if current_size == self.last_pos:
            # Kiem tra neu dang trong turn ma bi dung qua lau (> 5 phut)
            if self.in_turn and not self.warned_stall:
                elapsed = time.time() - self.last_activity_time
                if elapsed > 300: # 5 phut khong co phan hoi
                    notify_interrupted_or_disconnected(
                        task_name=f"Antigravity Turn: {self.current_user_prompt[:50]}",
                        reason="Tiến trình Agent bị dừng quá 5 phút mà không có phản hồi mới (Stall / Network Freeze)",
                        last_action=self.turn_actions[-1] if self.turn_actions else "Đang thực hiện công việc",
                        recovery_hint="Kiểm tra lại cửa sổ Antigravity hoặc kết nối Internet máy tính."
                    )
                    self.warned_stall = True
            return

        with open(self.transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(self.last_pos)
            lines = f.readlines()
            self.last_pos = f.tell()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                self.process_step(data)
            except Exception as e:
                # Co the la dong JSON chua ghi xong
                continue

    def process_step(self, step: dict):
        step_type = step.get("type")
        source = step.get("source")
        status = step.get("status")
        tool_calls = step.get("tool_calls", [])
        content = step.get("content", "")

        self.last_activity_time = time.time()
        self.warned_stall = False

        # 1. User Input moi -> Khoi dau turn moi
        if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
            self.current_user_prompt = extract_user_goal(content)
            self.turn_actions = []
            self.files_touched = set()
            self.in_turn = True
            print(f"\n[+] User Request: {self.current_user_prompt}")
            return

        # 2. Tool calls (cac hanh dong agent thuc hien)
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}

                tool_summary = (args.get("toolSummary") or args.get("toolAction") or "").strip().strip('"')
                action_desc = f"Gọi công cụ: `{name}`"
                if name in ("replace_file_content", "write_to_file", "view_file"):
                    target = args.get("TargetFile") or args.get("AbsolutePath") or ""
                    if target:
                        filename = os.path.basename(target)
                        self.files_touched.add(filename)
                        action_desc = f"Tệp `{filename}`: {tool_summary}" if tool_summary else f"Chỉnh sửa tệp: `{filename}`"
                elif name == "run_command":
                    cmd = args.get("CommandLine", "").strip('"')
                    if len(cmd) > 60:
                        cmd = cmd[:57] + "..."
                    action_desc = f"Lệnh `{cmd}`: {tool_summary}" if tool_summary else f"Chạy lệnh: `{cmd}`"
                elif name == "invoke_subagent":
                    subs = args.get("Subagents", [])
                    action_desc = f"Gọi {len(subs)} subagent ({tool_summary})" if tool_summary else f"Gọi {len(subs)} subagent phụ trợ"
                elif tool_summary:
                    action_desc = f"`{name}`: {tool_summary}"

                self.turn_actions.append(action_desc)
                print(f"    -> {action_desc}")

        # 3. Kiem tra loi gián đoạn hoac loi nghiem trong tu tool
        if status == "ERROR":
            err_msg = content or "Công cụ trả về mã lỗi."
            # Kiem tra neu loi mat mang hoac connection
            if any(k in str(err_msg).lower() for k in ["disconnect", "timeout", "network", "connecterror", "connection refused"]):
                notify_interrupted_or_disconnected(
                    task_name=f"Antigravity: {self.current_user_prompt[:50]}",
                    reason="Mất kết nối hoặc gián đoạn dịch vụ mạng trong quá trình chạy lệnh",
                    last_action=self.turn_actions[-1] if self.turn_actions else "Đang thực thi công cụ",
                    error_message=str(err_msg),
                    recovery_hint="Kiểm tra lại kết nối mạng Internet hoặc API quota."
                )

        # 4. Turn hoan thanh: PLANNER_RESPONSE cuoi cung (khong co tool_calls, co content tra loi)
        if step_type == "PLANNER_RESPONSE" and not tool_calls and content:
            if self.in_turn:
                print(f"[✓] Hoan thanh turn: {self.current_user_prompt}")
                task_title = f"Antigravity: {self.current_user_prompt}"
                task_desc = clean_agent_summary(content)
                
                details_list = []
                if self.turn_actions:
                    # Lay toi da 6 hanh dong dai dien
                    sample_actions = self.turn_actions[:6]
                    details_list = [f"• {a}" for a in sample_actions]
                    if len(self.turn_actions) > 6:
                        details_list.append(f"• ... và {len(self.turn_actions) - 6} thao tác khác")
                else:
                    details_list = ["• Đã xử lý và trả lời câu hỏi trực tiếp"]

                files_list = list(self.files_touched)[:6] if self.files_touched else None

                notify_task_completed(
                    task_title=task_title,
                    task_description=task_desc,
                    details=details_list,
                    files_affected=files_list
                )

                self.in_turn = False
                self.turn_actions = []
                self.files_touched = set()

def main():
    parser = argparse.ArgumentParser(description="Giam sat Antigravity va gui thong bao tien do ve Discord")
    parser.add_argument("--path", type=str, default=None, help="Duong dan truc tiep toi file transcript.jsonl")
    parser.add_argument("--interval", type=float, default=2.0, help="Chu ky quet file (giay)")
    parser.add_argument("--from-start", action="store_true", help="Doc tu dau file thay vi tu cuoi")
    args = parser.parse_args()

    if args.path:
        transcript_file = Path(args.path)
    else:
        transcript_file = find_latest_transcript()

    if not transcript_file or not transcript_file.exists():
        print("[!] Khong tim thay file transcript.jsonl nao cua Antigravity.")
        print(f"    Kiem tra tai: {DEFAULT_BRAIN_DIR}")
        sys.exit(1)

    print("==================================================")
    print("🚀 ANTIGRAVITY DISCORD REAL-TIME WATCHER")
    print(f"📂 Dang giam sat: {transcript_file}")
    print(f"⏱️  Chu ky quet: {args.interval}s")
    print("==================================================")
    print("Nhan Ctrl+C de dung giam sat.")

    watcher = AntigravityWatcher(transcript_file, start_at_end=not args.from_start)

    try:
        while True:
            watcher.check_updates()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[!] Da dung giam sat.")

if __name__ == "__main__":
    main()
