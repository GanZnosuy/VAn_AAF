"""Application Bootstrap, Win32 Global Hotkey Listener, and 3-Thread Coordinator."""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QRect, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .core.ai_worker import AIWorker
from .core.browser_scraper import BrowserScraper
from .core.screen_watcher import SmartScreenWatcher
from .core.win32_stealth import set_window_stealth_and_clickthrough
from .database.db_manager import DatabaseManager
from .ui.central_dashboard import CentralDashboardWindow
from .ui.hud_pill import HudPill
from .ui.settings_dialog import SettingsDialog
from .ui.slide_drawer import SlideDrawer
from .ui.twin_quiz_modal import TwinQuizModal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
)
logger = logging.getLogger("tsa_ielts_hud")


# ==============================================================================
# 1. FLOATING TOAST NOTIFIER
# ==============================================================================
class ToastNotification(QWidget):
    """Temporary floating HUD toast displaying profile changes and hotkey events."""

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(380, 44)

        # Center top
        self.move((screen_w - 380) // 2, 58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.box = QFrame(self)
        self.box.setStyleSheet(
            "background: rgba(15, 23, 42, 0.95); border: 1.5px solid #38bdf8; "
            "border-radius: 22px; padding: 4px;"
        )
        b_layout = QHBoxLayout(self.box)
        b_layout.setContentsMargins(14, 0, 14, 0)

        self.lbl_text = QLabel("")
        self.lbl_text.setStyleSheet(
            "color: #f8fafc; font-size: 12px; font-weight: 700; font-family: 'Segoe UI', sans-serif;"
        )
        self.lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(self.lbl_text)

        layout.addWidget(self.box)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

        # Apply screen-capture stealth & click-through
        try:
            hwnd = int(self.winId())
            set_window_stealth_and_clickthrough(hwnd, click_through=True, hide_from_capture=True)
        except Exception:
            pass

    def show_message(self, message: str, duration_ms: int = 2200) -> None:
        """Displays toast message with auto-hide."""
        self.lbl_text.setText(message)
        self.show()
        self.raise_()
        self.timer.start(duration_ms)


# ==============================================================================
# 2. GLOBAL HOTKEY THREAD (WIN32 REGISTERHOTKEY)
# ==============================================================================
class Win32HotkeyThread(QThread):
    """
    Background Win32 message pump listening for global hotkeys:
      - Alt+M: Cycle Profiles
      - Alt+F: Flag Current Question
      - Alt+S: Trigger State 2 Auto-Sync (Scrape + AI)
      - Alt+Z: Toggle State 3 Brain-Hack Drawer
      - Alt+H: Toggle Stealth Visibility
    """

    hotkey_triggered = pyqtSignal(str)  # action name

    HOTKEY_ACTIONS = {
        101: "mode_switch",    # Alt+M
        102: "micro_flag",     # Alt+F
        103: "submit_scrape",  # Alt+S
        104: "toggle_drawer",  # Alt+Z
        105: "stealth_hide",   # Alt+H
        106: "reset_question", # Alt+R
        107: "next_question",  # Alt+Up
        108: "prev_question",  # Alt+Down
        109: "vision_analyze", # Alt+V
        110: "launch_chrome",  # Alt+C
        111: "read_question",  # Alt+Q
    }

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.running = True

    def run(self) -> None:
        if sys.platform != "win32":
            logger.warning("Global hotkeys via Win32 RegisterHotKey only supported on Windows.")
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Configure 64-bit safe argtypes and restype
        user32.PeekMessageW.argtypes = [
            ctypes.POINTER(ctypes.wintypes.MSG),
            ctypes.wintypes.HWND,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        user32.PeekMessageW.restype = ctypes.wintypes.BOOL

        user32.RegisterHotKey.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        user32.RegisterHotKey.restype = ctypes.wintypes.BOOL

        user32.UnregisterHotKey.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.c_int,
        ]
        user32.UnregisterHotKey.restype = ctypes.wintypes.BOOL

        kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD
        self.win32_thread_id = kernel32.GetCurrentThreadId()
        MOD_ALT = 0x0001
        MOD_NOREPEAT = 0x4000

        # Virtual Key Codes
        VK_M = 0x4D
        VK_F = 0x46
        VK_S = 0x53
        VK_Z = 0x5A
        VK_H = 0x48
        VK_R = 0x52
        VK_UP = 0x26
        VK_DOWN = 0x28
        VK_V = 0x56
        VK_C = 0x43
        VK_Q = 0x51

        bindings = [
            (101, VK_M),
            (102, VK_F),
            (103, VK_S),
            (104, VK_Z),
            (105, VK_H),
            (106, VK_R),
            (107, VK_UP),
            (108, VK_DOWN),
            (109, VK_V),
            (110, VK_C),
            (111, VK_Q),
        ]

        for hk_id, vk in bindings:
            res = user32.RegisterHotKey(None, hk_id, MOD_ALT | MOD_NOREPEAT, vk)
            if not res:
                # Retry without MOD_NOREPEAT for older Windows versions
                user32.RegisterHotKey(None, hk_id, MOD_ALT, vk)

        logger.info("Win32 global hotkeys successfully registered (Alt+M, Alt+F, Alt+S, Alt+Z, Alt+H, Alt+R, Alt+Up/Down, Alt+V, Alt+C).")

        try:
            # Win32 Message Loop
            msg = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            WM_HOTKEY = 0x0312
            PM_REMOVE = 0x0001

            while self.running:
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == 0x0012:  # WM_QUIT
                        break
                    if msg.message == WM_HOTKEY:
                        hk_id = msg.wParam
                        action = self.HOTKEY_ACTIONS.get(hk_id)
                        if action:
                            self.hotkey_triggered.emit(action)
                time.sleep(0.04)
        except Exception as e:
            logger.error("Exception in Win32HotkeyThread loop: %s", e)
        finally:
            # Cleanup registrations on exit
            for hk_id, _ in bindings:
                try:
                    user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass
            logger.info("Win32 global hotkeys unregistered cleanly.")

    def stop(self) -> None:
        self.running = False
        self.quit()
        self.wait(1000)


# ==============================================================================
# 3. SENSOR WORKER THREAD (0.5 FPS)
# ==============================================================================
class SensorWorkerThread(QThread):
    """
    Sensor thread sampling the screen at 0.5 FPS (2.0s interval).
    Emits telemetry updates, switch events, and pacing alerts.
    """

    telemetry_updated = pyqtSignal(dict)
    question_switched = pyqtSignal(dict)
    pacing_alert = pyqtSignal(str)

    def __init__(
        self,
        screen_watcher: SmartScreenWatcher,
        config: Dict[str, Any],
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.watcher = screen_watcher
        self.config = config
        self.running = True
        self.active_profile = config.get("active_profile", "YOUPASS_READING")
        self.pacing_config = config.get("passage_pacing_alerts", {})

        # Pacing alert tracking
        self.p1_alerted = False
        self.p2_alerted = False

    def set_profile(self, profile: str) -> None:
        self.active_profile = profile

    def run(self) -> None:
        logger.info("Sensor Worker Thread started (0.5 FPS sampling).")
        while self.running:
            start_t = time.time()
            try:
                frame_data = self.watcher.sample_frame(self.active_profile, delta_sec=2.0)
                frame_data["profile"] = self.active_profile

                # Check Passage Pacing Alerts (e.g. Passage 1 > 15m, Passage 2 cumulative > 35m)
                cum_min = frame_data["cumulative_sec"] / 60.0
                p1_max = float(self.pacing_config.get("passage_1_max_min", 15))
                p2_max = float(self.pacing_config.get("passage_2_cumulative_max_min", 35))

                pacing_msg = ""
                if cum_min > p2_max:
                    pacing_msg = f"Đã quá {int(p2_max)}m toàn bài!"
                    if not self.p2_alerted:
                        self.pacing_alert.emit(f"Cảnh báo tốc độ: Vượt quá {int(p2_max)} phút tích lũy!")
                        self.p2_alerted = True
                elif cum_min > p1_max:
                    pacing_msg = f"Passage 1 vượt {int(p1_max)}m!"
                    if not self.p1_alerted:
                        self.pacing_alert.emit(f"Cảnh báo tốc độ: Passage 1 đã vượt quá {int(p1_max)} phút!")
                        self.p1_alerted = True

                frame_data["pacing_warning"] = pacing_msg

                if frame_data.get("switched"):
                    self.question_switched.emit(frame_data)

                self.telemetry_updated.emit(frame_data)
            except Exception as e:
                logger.error("Exception in SensorWorker loop: %s", e)

            # Interruptible sleep maintaining 0.5 FPS (2000ms period)
            elapsed = time.time() - start_t
            sleep_sec = max(0.05, 2.0 - elapsed)
            steps = int(sleep_sec / 0.05)
            for _ in range(steps):
                if not self.running:
                    break
                time.sleep(0.05)

        logger.info("Sensor Worker Thread stopped.")

    def stop(self) -> None:
        self.running = False
        self.quit()
        self.wait(1000)


# ==============================================================================
# 3.5. AUTO-SUBMIT WATCHER THREAD (ZERO-CLICK EXAM COMPLETION DETECTOR)
# ==============================================================================
class AutoSubmitWatcherThread(QThread):
    """
    Background daemon monitoring browser tabs over CDP.
    Detects when student clicks 'Nộp bài' or reaches result page,
    and automatically emits exam_submitted_detected.
    """

    exam_submitted_detected = pyqtSignal(str, str)  # (profile_type, page_url)
    active_question_detected = pyqtSignal(int)      # live active question index in browser DOM

    def __init__(
        self,
        cdp_url: str = "http://localhost:9222",
        active_profile: str = "YOUPASS_READING",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.cdp_url = cdp_url
        self.active_profile = active_profile
        self.running = True
        self.last_synced_url: Optional[str] = None
        self.last_reported_q: Optional[int] = None

    def set_profile(self, profile: str) -> None:
        self.active_profile = profile

    def reset_synced_url(self) -> None:
        self.last_synced_url = None

    def run(self) -> None:
        logger.info("AutoSubmitWatcherThread started (polling CDP for exam submission).")
        scraper = BrowserScraper(cdp_url=self.cdp_url)

        while self.running:
            try:
                res = asyncio.run(scraper.check_is_exam_submitted())
                if res and res.get("submitted"):
                    current_url = res.get("url", "")
                    if current_url != self.last_synced_url:
                        self.last_synced_url = current_url
                        domain = res.get("domain", "")
                        prof = self.active_profile
                        if "hociz" in domain:
                            prof = "HOCIZ_TSA"
                        elif "study4" in domain:
                            prof = "STUDY4_READING"
                        elif "youpass" in domain:
                            prof = "YOUPASS_READING"
                        elif "tsa" in domain:
                            prof = "TSA_MODE"
                        logger.info("Exam submission detected on %s: %s", domain, current_url)
                        self.exam_submitted_detected.emit(prof, current_url)
                else:
                    # Live DOM sync for active question number (Hociz / Study4 / YouPass)
                    active_q = asyncio.run(scraper.get_current_active_question())
                    if active_q and active_q > 0 and active_q != self.last_reported_q:
                        self.last_reported_q = active_q
                        self.active_question_detected.emit(active_q)
            except Exception as e:
                logger.debug("AutoSubmitWatcher error: %s", e)
            finally:
                try:
                    asyncio.run(scraper.disconnect())
                except Exception:
                    pass

            # Sleep 2.0s with responsive check
            for _ in range(40):
                if not self.running:
                    break
                time.sleep(0.05)

        logger.info("AutoSubmitWatcherThread stopped.")

    def stop(self) -> None:
        self.running = False
        self.quit()
        self.wait(1000)


# ==============================================================================
# 4. ASYNC SYNC WORKER THREAD (SCRAPING & AI REFLEXION)
# ==============================================================================
class SyncWorkerThread(QThread):
    """
    Executes State 2 Auto-Sync:
      1. Connects to browser over CDP on port 9222.
      2. Scrapes post-exam wrong questions with Study4 / YouPass / TSA adapters.
      3. Ingests into DatabaseManager.
      4. Dispatches Gemini cognitive analysis & Reflexion loop for each wrong question.
      5. Emits sync_completed to open the Feynman Gatekeeper Drawer.
    """

    sync_progress = pyqtSignal(str)
    sync_completed = pyqtSignal(dict, list)  # summary, wrong_questions
    sync_failed = pyqtSignal(str)

    def __init__(
        self,
        session_id: int,
        profile_type: str,
        db_manager: DatabaseManager,
        cdp_url: str = "http://localhost:9222",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.session_id = session_id
        self.profile_type = profile_type
        self.db_manager = db_manager
        self.cdp_url = cdp_url
        self.scraper = BrowserScraper(cdp_url=self.cdp_url)
        self.ai_worker = AIWorker()

    def run(self) -> None:
        asyncio.run(self._execute_sync())

    async def _execute_sync(self) -> None:
        try:
            self.sync_progress.emit("Đang kết nối Chrome DevTools Protocol (CDP:9222)...")
            connected = await self.scraper.connect()

            scraped_items: List[Dict[str, Any]] = []
            if connected:
                self.sync_progress.emit(f"Đang trích xuất DOM câu hỏi sai cho {self.profile_type}...")
                scraped_items = await self.scraper.scrape_post_exam_results(self.profile_type)
            else:
                self.sync_progress.emit("Không tìm thấy Chrome CDP; kích hoạt bộ mô phỏng phân tích...")
                # Generate sample wrong questions for offline demonstration
                scraped_items = [
                    {
                        "question_number": 14,
                        "section_tag": self.profile_type,
                        "question_type": "Tư duy Logic & Đọc hiểu",
                        "question_text": "The author suggests that the introduction of automated machinery primarily influenced which social class?",
                        "user_answer": "B. Upper aristocracy (Do bị bẫy từ 'wealthy patrons')",
                        "official_answer": "C. Semi-skilled urban artisans",
                        "platform_explanation": "Đoạn 3 chỉ ra rằng thợ thủ công thành thị là nhóm chịu tác động trực tiếp và nặng nề nhất.",
                        "transcript_quote": "artisans in metropolitan hubs faced structural displacement...",
                        "dom_selector": '[data-hud-qid="14"]',
                        "dwell_time_sec": 135.0,
                        "is_timesink": 1,
                        "is_guessed": 0,
                        "is_correct": 0,
                    },
                    {
                        "question_number": 27,
                        "section_tag": self.profile_type,
                        "question_type": "Critical Thinking / TSA",
                        "question_text": "Which one of the following, if true, most seriously weakens the argument?",
                        "user_answer": "A. The overall sample size was marginally smaller than expected.",
                        "official_answer": "D. An external third variable accounted for both observed effects.",
                        "platform_explanation": "Bẫy ngụy biện nguyên nhân thứ ba (Confounding Variable).",
                        "transcript_quote": "A correlated with B, therefore A produced B.",
                        "dom_selector": '[data-hud-qid="27"]',
                        "dwell_time_sec": 10.0,
                        "is_timesink": 0,
                        "is_guessed": 1,
                        "is_correct": 0,
                    },
                ]

            self.sync_progress.emit("Đang lưu kết quả bài thi vào cơ sở dữ liệu SQLite...")
            log_ids = self.db_manager.save_scraped_results(self.session_id, scraped_items)
            for idx, q_data in enumerate(scraped_items):
                if idx < len(log_ids):
                    q_data["log_id"] = log_ids[idx]

            # Ingest Cognitive Analysis via Gemini AI Worker
            processed_cards = []
            for idx, q_data in enumerate(scraped_items):
                q_num = q_data.get("question_number", idx + 1)
                self.sync_progress.emit(f"AI Gemini đang phân tích câu #{q_num} và tạo Twin Quiz...")
                analysis = await self.ai_worker.analyze_wrong_question(
                    q_data=q_data,
                    profile_type=self.profile_type,
                    db_manager=self.db_manager,
                )

                # Check if Reflexion loop should trigger (if AI initial answer differed from official)
                if q_data.get("ai_initial_answer") and q_data.get("official_answer"):
                    await self.ai_worker.trigger_ai_self_correction(
                        q_data=q_data,
                        profile_type=self.profile_type,
                        db_manager=self.db_manager,
                    )

            # Retrieve complete session summary and enriched wrong questions
            summary = self.db_manager.get_session_summary(self.session_id)
            wrong_questions = self.db_manager.get_session_wrong_questions(self.session_id)

            self.sync_progress.emit("Hoàn tất đồng bộ! Đang mở Ngăn Kéo Feynman...")
            self.sync_completed.emit(summary, wrong_questions)

        except Exception as e:
            logger.error("Error during sync execution: %s", e)
            self.sync_failed.emit(str(e))
        finally:
            await self.scraper.disconnect()


# ==============================================================================
# 5. MASTER CONTROLLER & COORDINATOR
# ==============================================================================
class MasterCoordinator(QObject):
    """
    Central Coordinator managing:
      - HudPill, SlideDrawer, SettingsDialog, Toast
      - SensorWorkerThread & SyncWorkerThread
      - Win32 Hotkey listener
      - Database sessions and clean teardown
    """

    PROFILES = [
        "YOUPASS_READING",
        "STUDY4_READING",
        "TSA_MODE",
        "IELTS_LISTENING",
        "IELTS_WRITING",
    ]

    def __init__(self, app: QApplication, start_threads: bool = True):
        super().__init__()
        self.app = app

        # Load screen dimensions
        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        self.screen_w = geo.width()
        self.screen_h = geo.height()

        # Base directory resolution (handles both source code and PyInstaller frozen executable)
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
            bundle_dir = getattr(sys, "_MEIPASS", base_dir)
            self.config_path = os.path.join(base_dir, "config.json")
            if not os.path.isfile(self.config_path):
                bundled_cfg = os.path.join(bundle_dir, "tsa_ielts_hud", "config.json")
                if os.path.isfile(bundled_cfg):
                    self.config_path = bundled_cfg
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(base_dir, "config.json")

        self.config = self._load_config()

        # Database manager
        db_path = os.path.join(base_dir, "hud_cognitive.db")
        self.db_manager = DatabaseManager(db_path=db_path)

        # Initialize Active Session
        self.current_profile = self.config.get("active_profile", "YOUPASS_READING")
        self.session_id = self.db_manager.create_session(
            exam_profile=self.current_profile,
            exam_name=f"Cognitive Session ({self.current_profile})",
            platform_name="Stealth HUD Native",
        )
        logger.info("Initialized Exam Session #%s for %s", self.session_id, self.current_profile)

        # UI Components
        self.toast = ToastNotification(self.screen_w, self.screen_h)
        self.pill = HudPill(self.screen_w, self.screen_h)
        self.drawer = SlideDrawer(self.screen_w, self.screen_h, db_manager=self.db_manager)
        self.settings_dialog = SettingsDialog(config_path=self.config_path)
        self.dashboard = CentralDashboardWindow(
            self.screen_w, self.screen_h, config=self.config, db_manager=self.db_manager
        )

        # Screen Watcher Sensor (starts in paused standby so question remains 1)
        self.screen_watcher = SmartScreenWatcher(self.screen_w, self.screen_h, config=self.config)
        self.screen_watcher.is_paused = True

        # Worker Threads
        self.sensor_thread: Optional[SensorWorkerThread] = None
        self.sync_thread: Optional[SyncWorkerThread] = None
        self.hotkey_thread: Optional[Win32HotkeyThread] = None
        self.auto_submit_thread: Optional[AutoSubmitWatcherThread] = None

        # Visibility state
        self.stealth_visible: bool = True

        # System Tray Icon
        self.tray: Optional[QSystemTrayIcon] = None
        self._init_system_tray()

        self._connect_signals()
        if start_threads:
            self._start_threads()
            self.dashboard.show_dashboard()
        self.pill.show()

    def _load_config(self) -> Dict[str, Any]:
        """Loads configuration from JSON."""
        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Error reading config.json: %s", e)
        return {
            "active_profile": "YOUPASS_READING",
            "cdp_url": "http://localhost:9222",
            "sensor_fps": 0.5,
            "hamming_threshold": 4,
            "guess_threshold_sec": 12,
            "time_sink_thresholds": {
                "TSA_MODE": 120,
                "YOUPASS_READING": 90,
                "STUDY4_READING": 90,
                "IELTS_LISTENING": 60,
                "IELTS_WRITING": 300,
            },
            "passage_pacing_alerts": {
                "passage_1_max_min": 15,
                "passage_2_cumulative_max_min": 35,
            },
        }

    def _connect_signals(self) -> None:
        """Connects signals across threads and UI components."""
        # Drawer signals
        self.drawer.question_selected.connect(self._handle_drawer_scroll)
        self.drawer.launch_twin_challenge.connect(self._handle_launch_twin)

        # Settings dialog
        self.settings_dialog.config_saved.connect(self._handle_config_updated)

        # Central Dashboard signals
        self.dashboard.config_saved.connect(self._handle_config_updated)
        self.dashboard.start_exam_mode.connect(self._handle_start_exam_mode)
        self.dashboard.open_drawer_requested.connect(self.drawer.open_drawer)
        self.dashboard.open_twin_challenge_requested.connect(self._handle_launch_twin)
        self.dashboard.profile_changed.connect(self.set_active_profile)
        self.dashboard.request_vision_sync.connect(self.trigger_vision_sync)
        self.dashboard.request_read_question.connect(self.trigger_live_question_ocr)
        self.dashboard.request_reset_q1.connect(self.reset_exam_session)
        self.dashboard.request_launch_chrome.connect(self.launch_chrome_browser)

        # Pill profile click opens Dashboard
        self.pill.profile_clicked.connect(self.dashboard.show_dashboard)

    def _init_system_tray(self) -> None:
        """Initializes System Tray icon and quick-access context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = os.path.join(os.path.dirname(__file__), "assets", "hud_icon.ico")
        if not os.path.isfile(icon_path) and getattr(sys, "frozen", False):
            bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            icon_path = os.path.join(bundle_dir, "tsa_ielts_hud", "assets", "hud_icon.ico")
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()

        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip("TSA & IELTS Stealth Cognitive HUD")

        menu = QMenu()

        act_dash = QAction("🖥️ Bảng Điều Khiển Trung Tâm (Cài Đặt)", menu)
        act_dash.triggered.connect(self.dashboard.show_dashboard)
        menu.addAction(act_dash)

        menu.addSeparator()

        act_read = QAction("🔍 Đọc Đề Câu Này & Gợi Ý Chiến Thuật (Alt+Q)", menu)
        act_read.triggered.connect(self.trigger_live_question_ocr)
        menu.addAction(act_read)

        act_reset = QAction("🔄 Reset Về Câu #01 (00:00) (Alt+R)", menu)
        act_reset.triggered.connect(self.reset_exam_session)
        menu.addAction(act_reset)

        act_vision = QAction("📸 AI Vision Đọc Màn Hình (Zero CDP) (Alt+V)", menu)
        act_vision.triggered.connect(self.trigger_vision_sync)
        menu.addAction(act_vision)

        act_chrome = QAction("🌐 Mở Google Chrome CDP (Port 9222) (Alt+C)", menu)
        act_chrome.triggered.connect(self.launch_chrome_browser)
        menu.addAction(act_chrome)

        menu.addSeparator()

        act_drawer = QAction("📂 Mở Ngăn Kéo Ôn Tập (Alt+Z)", menu)
        act_drawer.triggered.connect(self.drawer.toggle)
        menu.addAction(act_drawer)

        act_profile = QAction("🔄 Đổi Chế Độ Thi (Alt+M)", menu)
        act_profile.triggered.connect(self.cycle_profile)
        menu.addAction(act_profile)

        act_sync = QAction("⚡ Đồng Bộ CDP & Phân Tích AI (Alt+S)", menu)
        act_sync.triggered.connect(self.trigger_auto_sync)
        menu.addAction(act_sync)

        act_stealth = QAction("👁️ Ẩn / Hiện HUD (Alt+H)", menu)
        act_stealth.triggered.connect(self.toggle_stealth_visibility)
        menu.addAction(act_stealth)

        menu.addSeparator()

        act_settings = QAction("⚙️ Cài Đặt / Ngưỡng Thời Gian...", menu)
        act_settings.triggered.connect(self.dashboard.show_dashboard)
        menu.addAction(act_settings)

        menu.addSeparator()

        act_quit = QAction("❌ Thoát Ứng Dụng", menu)
        act_quit.triggered.connect(self.app.quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Clicking on tray icon brings up the Central Dashboard!"""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.dashboard.show_dashboard()

    def _start_threads(self) -> None:
        """Starts Sensor thread and Win32 Global Hotkey listener."""
        # 1. Hotkey Thread
        self.hotkey_thread = Win32HotkeyThread()
        self.hotkey_thread.hotkey_triggered.connect(self.handle_hotkey_action)
        self.hotkey_thread.start()

        # 2. Sensor Thread
        self.sensor_thread = SensorWorkerThread(
            screen_watcher=self.screen_watcher,
            config=self.config,
        )
        self.sensor_thread.telemetry_updated.connect(self._on_sensor_telemetry)
        self.sensor_thread.question_switched.connect(self._on_question_switched)
        self.sensor_thread.pacing_alert.connect(lambda msg: self.toast.show_message(msg, 3500))
        self.sensor_thread.start()

        # 3. Auto-Submit Watcher Thread (Zero-Click Exam Completion Detector & DOM Question Sync)
        cdp_url = self.config.get("cdp_url", "http://localhost:9222")
        self.auto_submit_thread = AutoSubmitWatcherThread(
            cdp_url=cdp_url,
            active_profile=self.current_profile,
        )
        self.auto_submit_thread.exam_submitted_detected.connect(self._on_auto_exam_submitted)
        self.auto_submit_thread.active_question_detected.connect(self._on_active_question_detected)
        self.auto_submit_thread.start()

    # ==========================================
    # HOTKEY DISPATCHER
    # ==========================================

    @pyqtSlot(str)
    def handle_hotkey_action(self, action: str) -> None:
        """Processes global shortcuts dispatched from Win32 message pump."""
        logger.info("Hotkey triggered: %s", action)

        if action == "mode_switch":
            self.cycle_profile()
        elif action == "micro_flag":
            self.toggle_micro_flag()
        elif action == "submit_scrape":
            self.trigger_auto_sync()
        elif action == "toggle_drawer":
            self.drawer.toggle()
        elif action == "stealth_hide":
            self.toggle_stealth_visibility()
        elif action == "reset_question":
            self.reset_exam_session()
        elif action == "next_question":
            self.step_question(1)
        elif action == "prev_question":
            self.step_question(-1)
        elif action == "vision_analyze":
            self.trigger_vision_sync()
        elif action == "read_question":
            self.trigger_live_question_ocr()
        elif action == "launch_chrome":
            self.launch_chrome_browser()

    def reset_exam_session(self) -> None:
        """Alt+R / Button: Resets HUD to Question 1 and 00:00 dwell timer, unpauses sensor."""
        self.screen_watcher.reset_session()
        self.screen_watcher.is_paused = False
        limit = self.screen_watcher.time_sink_thresholds.get(self.current_profile, 90.0)
        self.pill.update_telemetry(
            profile=self.current_profile,
            question_number=1,
            dwell_sec=0.0,
            time_limit=limit,
            flag_count=0,
            pacing_warning="",
        )
        self.toast.show_message("🔄 Đã reset về CÂU #01 & tính giờ lại từ đầu (00:00)", 2500)
        logger.info("Exam session reset to Question 1.")

    def step_question(self, step: int) -> None:
        """Alt+Up / Alt+Down: Manually steps question index."""
        new_q = max(1, self.screen_watcher.current_q_index + step)
        self.screen_watcher.set_current_question(new_q)
        self.screen_watcher.is_paused = False
        limit = self.screen_watcher.time_sink_thresholds.get(self.current_profile, 90.0)
        self.pill.update_telemetry(
            profile=self.current_profile,
            question_number=new_q,
            dwell_sec=0.0,
            time_limit=limit,
            flag_count=len(self.screen_watcher.flagged_questions),
            pacing_warning="",
        )
        self.toast.show_message(f"📍 Chuyển sang CÂU #{new_q:02d}", 1500)
        logger.info("Question manually stepped to: %s", new_q)

    def launch_chrome_browser(self) -> None:
        """Alt+C / Button: Launches Google Chrome with CDP port 9222."""
        self.toast.show_message("🚀 Đang mở Google Chrome (CDP Port 9222) vào Hociz.vn...", 3000)
        ok = BrowserScraper.launch_chrome_with_cdp("https://hociz.vn")
        if ok:
            self.toast.show_message("🟢 Chrome CDP 9222 đã sẵn sàng! Mời bạn làm bài.", 3500)
        else:
            self.toast.show_message("⚠️ Không tìm thấy Google Chrome tại các thư mục chuẩn.", 3500)

    @pyqtSlot(int)
    def _on_active_question_detected(self, q_num: int) -> None:
        """Syncs question number when detected from browser DOM in real time."""
        if q_num != self.screen_watcher.current_q_index:
            logger.info("DOM active question detected: Q#%s", q_num)
            self.screen_watcher.set_current_question(q_num)
            limit = self.screen_watcher.time_sink_thresholds.get(self.current_profile, 90.0)
            self.pill.update_telemetry(
                profile=self.current_profile,
                question_number=q_num,
                dwell_sec=0.0,
                time_limit=limit,
                flag_count=len(self.screen_watcher.flagged_questions),
                pacing_warning="",
            )

    def cycle_profile(self) -> None:
        """Alt+M: Cycles next profile."""
        current_idx = self.PROFILES.index(self.current_profile) if self.current_profile in self.PROFILES else 0
        next_idx = (current_idx + 1) % len(self.PROFILES)
        self.current_profile = self.PROFILES[next_idx]

        if self.sensor_thread:
            self.sensor_thread.set_profile(self.current_profile)

        badge_text = HudPill.PROFILE_BADGES.get(self.current_profile, self.current_profile)
        self.toast.show_message(f"Chuyển chế độ: {badge_text}")
        logger.info("Switched profile to: %s", self.current_profile)

    def toggle_micro_flag(self) -> None:
        """Alt+F: Toggles flag on current question."""
        q_idx = self.screen_watcher.current_q_index
        flagged = self.screen_watcher.toggle_flag(q_idx)

        # Save to database
        self.db_manager.log_question_event(
            session_id=self.session_id,
            question_number=q_idx,
            dwell_time_sec=self.screen_watcher.current_dwell_sec,
            user_flagged=1 if flagged else 0,
        )

        status_text = f"Đã gắn cờ câu #{q_idx:02d} (⚑)" if flagged else f"Đã bỏ cờ câu #{q_idx:02d}"
        self.toast.show_message(status_text)

    def trigger_auto_sync(self) -> None:
        """Alt+S: Transitions to State 2 Auto-Sync (Scraping & AI)."""
        self.toast.show_message("⚡ Đang đồng bộ kết quả bài thi qua CDP & Phân tích AI...")

        if self.sync_thread and self.sync_thread.isRunning():
            logger.warning("Sync is already running; skipping duplicate trigger.")
            return

        cdp_url = self.config.get("cdp_url", "http://localhost:9222")
        self.sync_thread = SyncWorkerThread(
            session_id=self.session_id,
            profile_type=self.current_profile,
            db_manager=self.db_manager,
            cdp_url=cdp_url,
        )
        self.sync_thread.sync_progress.connect(lambda msg: self.toast.show_message(msg, 2000))
        self.sync_thread.sync_completed.connect(self._on_sync_completed)
        self.sync_thread.sync_failed.connect(lambda err: self.toast.show_message(f"Lỗi: {err}", 3500))
        self.sync_thread.start()

    def toggle_stealth_visibility(self) -> None:
        """Alt+H: Toggles visibility of all overlay windows."""
        self.stealth_visible = not self.stealth_visible
        self.pill.set_stealth_visible(self.stealth_visible)
        if not self.stealth_visible and self.drawer.is_open:
            self.drawer.close_drawer()
        self.toast.show_message(
            "Stealth HUD: ĐANG HIỂN THỊ" if self.stealth_visible else "Stealth HUD: ĐÃ ẨN HOÀN TOÀN"
        )

    # ==========================================
    # SENSOR & SYNC HANDLERS
    # ==========================================

    @pyqtSlot(dict)
    def _on_sensor_telemetry(self, data: Dict[str, Any]) -> None:
        """Updates Pill UI with telemetry data."""
        self.pill.update_telemetry(
            profile=data.get("profile", self.current_profile),
            question_number=data.get("question_index", 1),
            dwell_sec=data.get("dwell_sec", 0.0),
            time_limit=data.get("time_limit", 90.0),
            flag_count=len(self.screen_watcher.flagged_questions),
            pacing_warning=data.get("pacing_warning", ""),
        )

        # Log continuous question event in database
        q_idx = data.get("question_index", 1)
        self.db_manager.log_question_event(
            session_id=self.session_id,
            question_number=q_idx,
            dwell_time_sec=data.get("dwell_sec", 0.0),
            section_tag=self.current_profile,
            is_guessed=1 if data.get("is_guessed") else 0,
            is_timesink=1 if data.get("is_timesink") else 0,
        )

    @pyqtSlot(dict)
    def _on_question_switched(self, data: Dict[str, Any]) -> None:
        """Triggered when student navigates to another question."""
        q_idx = data.get("question_index", 1)
        if data.get("is_guessed"):
            self.toast.show_message(f"⚡ Phát hiện đoán nhanh câu #{q_idx - 1} (<12s)", 2000)

    @pyqtSlot(str, str)
    def _on_auto_exam_submitted(self, profile: str, url: str) -> None:
        """Fires automatically when the student finishes an exam and submits."""
        logger.info("Automatic exam submission detected for %s at %s", profile, url)
        self.toast.show_message("🎉 ĐÃ PHÁT HIỆN NỘP BÀI! Đang tự động phân tích & mở báo cáo rút kinh nghiệm...", 4000)
        self.set_active_profile(profile)
        self.trigger_auto_sync()

    @pyqtSlot(dict, list)
    def _on_sync_completed(self, summary: Dict[str, Any], wrong_questions: List[Dict[str, Any]]) -> None:
        """Handles completion of State 2 Auto-Sync: populates drawer and launches post-exam reflection dashboard!"""
        self.drawer.load_session_data(summary, wrong_questions)
        self.drawer.open_drawer()

        # Automatically pop up the Central Dashboard right in the middle of the screen!
        self.dashboard.load_post_exam_data(summary, wrong_questions)
        self.dashboard.show_dashboard()

    @pyqtSlot(str)
    def _handle_drawer_scroll(self, dom_selector: str) -> None:
        """Smooth scrolls browser when a question chip is clicked in drawer."""
        threading.Thread(
            target=self._run_async_scroll,
            args=(dom_selector,),
            daemon=True,
            name="ScrollWorkerThread",
        ).start()

    def _run_async_scroll(self, dom_selector: str) -> None:
        try:
            asyncio.run(self._async_scroll(dom_selector))
        except Exception as e:
            logger.debug("Failed to scroll browser to %s: %s", dom_selector, e)

    async def _async_scroll(self, dom_selector: str) -> None:
        scraper = BrowserScraper(cdp_url=self.config.get("cdp_url", "http://localhost:9222"))
        try:
            await scraper.scroll_to_question(dom_selector)
        finally:
            await scraper.disconnect()

    @pyqtSlot(dict)
    def _handle_launch_twin(self, card_data: Dict[str, Any]) -> None:
        """Opens Twin Question Countdown Modal."""
        modal = TwinQuizModal(card_data=card_data, db_manager=self.db_manager, parent=self.drawer)
        modal.quiz_completed.connect(self._on_twin_quiz_completed)
        modal.exec()

    def _on_twin_quiz_completed(self, card_id: int, passed: bool) -> None:
        """Live refresh of session wrong questions in slide drawer when twin quiz is completed."""
        try:
            summary = self.db_manager.get_session_summary(self.session_id)
            wrong_questions = self.db_manager.get_session_wrong_questions(self.session_id)
            self.drawer.load_session_data(summary, wrong_questions)
        except Exception as e:
            logger.debug("Failed refreshing drawer after quiz completion: %s", e)

    @pyqtSlot(dict)
    def _handle_config_updated(self, new_config: Dict[str, Any]) -> None:
        """Applies configuration updates."""
        self.config = new_config
        self.current_profile = new_config.get("active_profile", self.current_profile)
        if self.sensor_thread:
            self.sensor_thread.set_profile(self.current_profile)
        self.toast.show_message("Đã lưu cấu hình thành công!")

    @pyqtSlot()
    def _handle_start_exam_mode(self) -> None:
        """Activated when student starts exam mode from dashboard."""
        self.reset_exam_session()
        self.stealth_visible = True
        self.pill.set_stealth_visible(True)
        self.pill.show()
        self.toast.show_message("🚀 Đã bắt đầu bài thi! CÂU #01 đang tính giờ (⏱️ 00:00)", 3500)

    def trigger_vision_sync(self) -> None:
        """Alt+V: Zero-CDP Vision Screenshot & Direct AI Analysis."""
        self.toast.show_message("📸 Đang chụp màn hình & AI Gemini đọc kết quả bài thi trực tiếp (Zero CDP)...", 4000)

        class VisionWorkerThread(QThread):
            vision_done = pyqtSignal(dict)
            vision_failed = pyqtSignal(str)

            def __init__(self, ai_worker, profile, parent=None):
                super().__init__(parent)
                self.ai = ai_worker
                self.profile = profile

            def run(self):
                try:
                    res = asyncio.run(self.ai.analyze_screen_vision(profile_type=self.profile))
                    self.vision_done.emit(res)
                except Exception as e:
                    self.vision_failed.emit(str(e))

        self.vision_thread = VisionWorkerThread(AIWorker(), self.current_profile, self)
        self.vision_thread.vision_done.connect(self._on_vision_sync_completed)
        self.vision_thread.vision_failed.connect(lambda err: self.toast.show_message(f"Lỗi AI Vision: {err}", 3500))
        self.vision_thread.start()

    def _on_vision_sync_completed(self, data: Dict[str, Any]) -> None:
        wrong_questions = data.get("wrong_questions", [])
        if not wrong_questions:
            self.toast.show_message("⚠️ AI Vision không tìm thấy câu hỏi sai trên màn hình hiện tại.", 3500)
            return

        summary = {
            "total_questions": data.get("total_questions", len(wrong_questions)),
            "wrong_count": data.get("wrong_count", len(wrong_questions)),
            "estimated_score": data.get("estimated_score", 0.0),
            "timesink_count": sum(1 for q in wrong_questions if q.get("is_timesink")),
            "guess_count": sum(1 for q in wrong_questions if q.get("is_guessed")),
        }

        # Save to database
        self.db_manager.save_scraped_results(self.session_id, wrong_questions)

        self.toast.show_message(f"🎉 AI Vision trích xuất thành công {len(wrong_questions)} câu hỏi sai!", 3000)
        self.drawer.load_session_data(summary, wrong_questions)
        self.dashboard.load_post_exam_data(summary, wrong_questions)
        self.dashboard.show_dashboard()

    def trigger_live_question_ocr(self) -> None:
        """Alt+Q / Button: Captures current question card, runs local OCR + Gemini strategic hint."""
        self.toast.show_message("🔍 Đang đọc đề & phân tích chiến thuật câu hiện tại (Alt+Q)...", 3000)

        class LiveQuestionWorkerThread(QThread):
            question_done = pyqtSignal(dict)
            question_failed = pyqtSignal(str)

            def __init__(self, ai_worker, profile, parent=None):
                super().__init__(parent)
                self.ai = ai_worker
                self.profile = profile

            def run(self):
                try:
                    res = asyncio.run(self.ai.read_current_question_live(profile_type=self.profile))
                    self.question_done.emit(res)
                except Exception as e:
                    self.question_failed.emit(str(e))

        self.live_q_thread = LiveQuestionWorkerThread(AIWorker(), self.current_profile, self)
        self.live_q_thread.question_done.connect(self._on_live_question_completed)
        self.live_q_thread.question_failed.connect(lambda err: self.toast.show_message(f"Lỗi: {err}", 3500))
        self.live_q_thread.start()

    def _on_live_question_completed(self, data: Dict[str, Any]) -> None:
        if not data.get("success"):
            self.toast.show_message("⚠️ Không đọc được nội dung câu hỏi trên màn hình.", 3000)
            return

        q_num = data.get("question_number", self.screen_watcher.current_q_index)
        hint = data.get("cognitive_hint", "")
        trap = data.get("trap_alert", "")

        if q_num and q_num > 0 and q_num != self.screen_watcher.current_q_index:
            self.screen_watcher.set_current_question(q_num)

        limit = self.screen_watcher.time_sink_thresholds.get(self.current_profile, 90.0)
        self.pill.update_telemetry(
            profile=self.current_profile,
            question_number=q_num,
            dwell_sec=self.screen_watcher.current_dwell_sec,
            time_limit=limit,
            flag_count=len(self.screen_watcher.flagged_questions),
            pacing_warning="",
        )

        display_msg = f"💡 CÂU #{q_num:02d}: {hint}" if hint else f"💡 CÂU #{q_num:02d}: Đã nhận diện"
        if trap:
            display_msg += f" | ⚠️ Bẫy: {trap}"
        self.toast.show_message(display_msg, 6000)

    @pyqtSlot(str)
    def set_active_profile(self, profile: str) -> None:
        """Sets active profile directly from dashboard or menu."""
        self.current_profile = profile
        if self.sensor_thread:
            self.sensor_thread.set_profile(profile)
        badge_text = HudPill.PROFILE_BADGES.get(profile, profile)
        self.pill.lbl_profile.setText(badge_text)
        self.toast.show_message(f"Đã chọn chế độ: {badge_text}")

    def cleanup(self) -> None:
        """Ensures all threads, connections, and sessions are safely finalized."""
        logger.info("Executing clean shutdown of TSA & IELTS Stealth HUD...")

        if self.sensor_thread:
            self.sensor_thread.stop()
            self.sensor_thread = None

        if self.auto_submit_thread:
            self.auto_submit_thread.stop()
            self.auto_submit_thread = None

        if self.hotkey_thread:
            self.hotkey_thread.stop()
            self.hotkey_thread = None

        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.wait(2000)
            self.sync_thread = None

        self.screen_watcher.close()

        # Hide System Tray
        if hasattr(self, "tray") and self.tray:
            self.tray.hide()

        # Close HUD UI widgets safely
        try:
            self.dashboard.close()
            self.pill.close()
            self.drawer.close()
            self.toast.close()
            self.settings_dialog.close()
        except Exception:
            pass

        # Finalize exam session
        if self.session_id:
            try:
                self.db_manager.end_session(self.session_id)
                logger.info("Finalized Session #%s successfully.", self.session_id)
            except Exception as e:
                logger.error("Error finalizing session: %s", e)


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main() -> None:
    """Application entrypoint."""
    if sys.platform == "win32":
        try:
            myappid = "tsa.ielts.stealth.hud.app"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    # High DPI scaling support
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("TSA & IELTS Stealth Cognitive HUD")
    app.setQuitOnLastWindowClosed(False)

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "hud_icon.ico")
    if not os.path.isfile(icon_path) and getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        icon_path = os.path.join(bundle_dir, "tsa_ielts_hud", "assets", "hud_icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    coordinator = MasterCoordinator(app)
    app.aboutToQuit.connect(coordinator.cleanup)

    logger.info("TSA & IELTS Stealth Cognitive HUD is running. Press Alt+H to hide, Alt+Z to open drawer.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
