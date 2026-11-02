"""State 1: Floating top-right 520x38 Mini-Pill with Win32 click-through and 3-tier time-sink color pulse."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ..core.win32_stealth import set_window_stealth_and_clickthrough

logger = logging.getLogger(__name__)


class HudPill(QWidget):
    """
    Ultra-lightweight floating Mini-Pill overlay (520px x 38px).
    100% click-through (WS_EX_TRANSPARENT), invisible to screen capture (WDA_EXCLUDEFROMCAPTURE),
    displaying real-time telemetry: profile, question number, dwell timer with 3-tier color pulse,
    flag counter, and passage pacing warnings.
    """

    profile_clicked = pyqtSignal()
    pill_toggled = pyqtSignal(bool)

    PROFILE_BADGES = {
        "HOCIZ_TSA": "🎯 HOCIZ TSA",
        "YOUPASS_READING": "📖 YOUPASS",
        "STUDY4_READING": "📘 STUDY4",
        "TSA_MODE": "⚡ TSA ĐGNL",
        "IELTS_LISTENING": "🎧 LISTENING",
        "IELTS_WRITING": "✍️ WRITING",
    }

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Telemetry State
        self.current_profile: str = "YOUPASS_READING"
        self.question_number: int = 1
        self.dwell_sec: float = 0.0
        self.time_limit: float = 90.0
        self.flag_count: int = 0
        self.pacing_warning_text: str = ""

        # Visual blink state for time-sink alert
        self._is_blinking: bool = False
        self._blink_phase: bool = False

        self._init_window()
        self._init_ui()
        self._init_timers()
        self._apply_stealth()

    def _init_window(self) -> None:
        """Configures frameless, always-on-top, translucent window."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Fixed dimensions
        self.setFixedSize(520, 38)
        # Position at top-right
        x_pos = max(10, self.screen_w - 540)
        y_pos = 12
        self.move(x_pos, y_pos)

    def _init_ui(self) -> None:
        """Builds telemetry widgets inside the dark pill container."""
        # Main background container
        self.container = QFrame(self)
        self.container.setGeometry(0, 0, 520, 38)
        self.container.setObjectName("pillContainer")
        self._update_container_style("#334155")

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # 1. Profile Badge
        self.lbl_profile = QLabel(self.PROFILE_BADGES.get(self.current_profile, "📖 YOUPASS"))
        self.lbl_profile.setStyleSheet(
            "color: #38bdf8; font-weight: bold; font-size: 11px; background: rgba(56, 189, 248, 0.15); "
            "padding: 2px 7px; border-radius: 9px; border: 1px solid rgba(56, 189, 248, 0.3);"
        )
        layout.addWidget(self.lbl_profile)

        # 2. Question Indicator
        self.lbl_question = QLabel("Q: #01")
        self.lbl_question.setStyleSheet(
            "color: #f1f5f9; font-weight: bold; font-size: 12px; font-family: 'Consolas', monospace;"
        )
        layout.addWidget(self.lbl_question)

        # Separator dot
        sep1 = QLabel("•")
        sep1.setStyleSheet("color: #475569; font-size: 10px;")
        layout.addWidget(sep1)

        # 3. Live Dwell Timer
        self.lbl_dwell = QLabel("⏱️ 00:00")
        self.lbl_dwell.setStyleSheet(
            "color: #10b981; font-weight: 800; font-size: 12px; font-family: 'Consolas', monospace;"
        )
        layout.addWidget(self.lbl_dwell)

        # 4. Flag Counter
        self.lbl_flags = QLabel("⚑ 0")
        self.lbl_flags.setStyleSheet(
            "color: #94a3b8; font-size: 11px; font-weight: 600; padding: 2px 5px; "
            "background: rgba(148, 163, 184, 0.12); border-radius: 6px;"
        )
        layout.addWidget(self.lbl_flags)

        # 5. Passage Pacing Warning (hidden unless active)
        self.lbl_pacing = QLabel("")
        self.lbl_pacing.setStyleSheet(
            "color: #ef4444; font-weight: bold; font-size: 11px; "
            "background: rgba(239, 68, 68, 0.18); padding: 2px 6px; border-radius: 6px;"
        )
        self.lbl_pacing.setVisible(False)
        layout.addWidget(self.lbl_pacing)

        layout.addStretch()

        # Stealth status icon
        self.lbl_status = QLabel("HUD ⚡")
        self.lbl_status.setStyleSheet("color: #0ea5e9; font-size: 10px; font-weight: 700;")
        layout.addWidget(self.lbl_status)

    def _init_timers(self) -> None:
        """Initializes blink timer for time-sink visual cues."""
        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(450)
        self.blink_timer.timeout.connect(self._handle_blink_tick)

    def _apply_stealth(self) -> None:
        """Applies click-through and screen-capture stealth on Windows."""
        try:
            hwnd = int(self.winId())
            set_window_stealth_and_clickthrough(hwnd, click_through=True, hide_from_capture=True)
            logger.info("Win32 stealth & click-through enabled on HudPill (HWND %s)", hwnd)
        except Exception as e:
            logger.warning("Could not apply Win32 stealth to HudPill: %s", e)

    def _update_container_style(self, border_color: str, bg_alpha: float = 0.90) -> None:
        """Updates styling border and background dynamically."""
        self.container.setStyleSheet(
            f"""
            #pillContainer {{
                background-color: rgba(15, 23, 42, {bg_alpha});
                border: 1.6px solid {border_color};
                border-radius: 19px;
            }}
            """
        )

    # ==========================================
    # TELEMETRY UPDATE LOGIC
    # ==========================================

    def update_telemetry(
        self,
        profile: str,
        question_number: int,
        dwell_sec: float,
        time_limit: float = 90.0,
        flag_count: int = 0,
        pacing_warning: str = "",
    ) -> None:
        """
        Updates live telemetry and 3-tier dwell color pulse:
          - Green (#10b981): 0s to 75% limit
          - Amber (#f59e0b): 75% to 100% limit
          - Blinking Red (#ef4444): > limit (Time-Sink!)
        """
        self.current_profile = profile
        self.question_number = question_number
        self.dwell_sec = dwell_sec
        self.time_limit = max(time_limit, 10.0)
        self.flag_count = flag_count
        self.pacing_warning_text = pacing_warning

        # Update profile badge
        badge_text = self.PROFILE_BADGES.get(profile, f"⚡ {profile}")
        self.lbl_profile.setText(badge_text)

        # Update question number
        self.lbl_question.setText(f"Q: #{self.question_number:02d}")

        # Format dwell time
        m = int(self.dwell_sec // 60)
        s = int(self.dwell_sec % 60)
        dwell_str = f"⏱️ {m:02d}:{s:02d}"
        self.lbl_dwell.setText(dwell_str)

        # 3-Tier Color Grading
        ratio = self.dwell_sec / self.time_limit

        if ratio <= 0.75:
            # Green State
            self._stop_blinking()
            self.lbl_dwell.setStyleSheet(
                "color: #10b981; font-weight: 800; font-size: 12px; font-family: 'Consolas', monospace;"
            )
            self._update_container_style("#334155")
        elif ratio <= 1.0:
            # Amber State (approaching limit)
            self._stop_blinking()
            self.lbl_dwell.setStyleSheet(
                "color: #f59e0b; font-weight: 800; font-size: 12px; font-family: 'Consolas', monospace;"
            )
            self._update_container_style("#f59e0b")
        else:
            # Red Blinking State (Time-Sink exceeded!)
            self._start_blinking()

        # Update flags
        self.lbl_flags.setText(f"⚑ {self.flag_count}")
        if self.flag_count > 0:
            self.lbl_flags.setStyleSheet(
                "color: #38bdf8; font-size: 11px; font-weight: 700; padding: 2px 6px; "
                "background: rgba(56, 189, 248, 0.22); border-radius: 6px; border: 1px solid #38bdf8;"
            )
        else:
            self.lbl_flags.setStyleSheet(
                "color: #94a3b8; font-size: 11px; font-weight: 600; padding: 2px 5px; "
                "background: rgba(148, 163, 184, 0.12); border-radius: 6px;"
            )

        # Update pacing warning
        if self.pacing_warning_text:
            self.lbl_pacing.setText(f"⚠️ {self.pacing_warning_text}")
            self.lbl_pacing.setVisible(True)
        else:
            self.lbl_pacing.setVisible(False)

    def _start_blinking(self) -> None:
        if not self._is_blinking:
            self._is_blinking = True
            self.blink_timer.start()

    def _stop_blinking(self) -> None:
        if self._is_blinking:
            self._is_blinking = False
            self.blink_timer.stop()

    def _handle_blink_tick(self) -> None:
        """Toggles red alert flash."""
        self._blink_phase = not self._blink_phase
        if self._blink_phase:
            self.lbl_dwell.setStyleSheet(
                "color: #ffffff; background: #ef4444; border-radius: 4px; padding: 1px 4px; "
                "font-weight: 900; font-size: 12px; font-family: 'Consolas', monospace;"
            )
            self._update_container_style("#ef4444", bg_alpha=0.98)
        else:
            self.lbl_dwell.setStyleSheet(
                "color: #ef4444; font-weight: 900; font-size: 12px; font-family: 'Consolas', monospace;"
            )
            self._update_container_style("#7f1d1d", bg_alpha=0.90)

    def set_stealth_visible(self, visible: bool) -> None:
        """Toggles HUD pill visibility."""
        if visible:
            self.show()
            self._apply_stealth()
        else:
            self.hide()
        self.pill_toggled.emit(visible)
