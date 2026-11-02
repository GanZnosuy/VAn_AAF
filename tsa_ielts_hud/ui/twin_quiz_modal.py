"""State 3 Modal: Intense Countdown Challenge (60s TSA / 45s IELTS) for AI-Generated Twin Questions."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.win32_stealth import set_window_stealth_and_clickthrough

logger = logging.getLogger(__name__)


class TwinQuizModal(QDialog):
    """
    Cognitive Countdown Challenge Modal.
    Tests active retention with an AI-generated twin question.
    Advances Spaced Repetition step if passed; resets step to 1 if failed/timed out.
    """

    quiz_completed = pyqtSignal(int, bool)  # card_id, passed

    def __init__(
        self,
        card_data: Dict[str, Any],
        db_manager: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.card_data = card_data
        self.db_manager = db_manager
        self.card_id = card_data.get("card_id", 0)

        twin = card_data.get("twin_question") or card_data.get("twin_question_json", {})
        if isinstance(twin, str):
            try:
                import json
                twin = json.loads(twin)
            except Exception:
                twin = {}

        self.twin_data = twin
        self.total_time_sec: int = int(twin.get("time_limit_sec", 45))
        self.remaining_sec: float = float(self.total_time_sec)
        self.correct_option: str = str(twin.get("correct_option", "A")).strip().upper()
        self.is_resolved: bool = False

        self._init_window()
        self._init_ui()
        self._init_timer()
        self._apply_stealth()

    def _init_window(self) -> None:
        """Configures modern frameless modal."""
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedSize(560, 480)

    def _init_ui(self) -> None:
        """Builds cyber dark challenge layout."""
        self.setStyleSheet(
            """
            QDialog {
                background-color: transparent;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # Container Frame
        self.container = QFrame(self)
        self.container.setStyleSheet(
            """
            QFrame {
                background-color: #0b1120;
                border: 2px solid #38bdf8;
                border-radius: 14px;
            }
            """
        )
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(20, 18, 20, 20)
        c_layout.setSpacing(12)

        # Header
        h_layout = QHBoxLayout()
        title = QLabel("⚡ THỬ THÁCH CÂU HỎI SINH ĐÔI (TWIN CHALLENGE)")
        title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8; border: none;")
        h_layout.addWidget(title)

        h_layout.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setStyleSheet(
            "QPushButton { background: #1e293b; color: #94a3b8; border-radius: 13px; font-weight: bold; border: none; } "
            "QPushButton:hover { background: #ef4444; color: white; }"
        )
        btn_close.clicked.connect(self._handle_close)
        h_layout.addWidget(btn_close)
        c_layout.addLayout(h_layout)

        # Countdown Header & Bar
        bar_header = QHBoxLayout()
        self.lbl_timer = QLabel(f"⏳ Thời gian còn lại: {int(self.remaining_sec)}s")
        self.lbl_timer.setStyleSheet("font-size: 12px; font-weight: 700; color: #38bdf8; border: none;")
        bar_header.addWidget(self.lbl_timer)
        bar_header.addStretch()
        c_layout.addLayout(bar_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, int(self.total_time_sec * 10))
        self.progress_bar.setValue(int(self.remaining_sec * 10))
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background: #1e293b;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #0284c7);
                border-radius: 4px;
            }
            """
        )
        c_layout.addWidget(self.progress_bar)

        # Question Stem
        stem_text = self.twin_data.get("stem", "Không tải được nội dung câu hỏi sinh đôi.")
        self.lbl_stem = QLabel(stem_text)
        self.lbl_stem.setWordWrap(True)
        self.lbl_stem.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #f8fafc; border: none; "
            "background: rgba(30, 41, 59, 0.5); padding: 10px; border-radius: 8px;"
        )
        c_layout.addWidget(self.lbl_stem)

        # Options Container
        options_dict = self.twin_data.get("options", {})
        self.option_buttons: Dict[str, QPushButton] = {}

        opts_layout = QVBoxLayout()
        opts_layout.setSpacing(8)

        for key in ["A", "B", "C", "D"]:
            opt_text = options_dict.get(key, f"Lựa chọn {key}")
            btn = QPushButton(f"{key}.  {opt_text}")
            btn.setCheckable(False)
            btn.setFixedHeight(36)
            btn.setStyleSheet(
                "QPushButton { background: #1e293b; color: #f1f5f9; text-align: left; padding-left: 14px; "
                "font-size: 12px; font-weight: 600; border-radius: 6px; border: 1px solid #334155; } "
                "QPushButton:hover { background: #334155; border-color: #38bdf8; }"
            )
            # Bind click
            btn.clicked.connect(lambda checked, k=key: self._handle_answer_selected(k))
            self.option_buttons[key] = btn
            opts_layout.addWidget(btn)

        c_layout.addLayout(opts_layout)

        # Result / Feedback Banner (initially hidden)
        self.feedback_banner = QLabel("")
        self.feedback_banner.setWordWrap(True)
        self.feedback_banner.setVisible(False)
        self.feedback_banner.setStyleSheet(
            "padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; border: none;"
        )
        c_layout.addWidget(self.feedback_banner)

        root.addWidget(self.container)

    def _init_timer(self) -> None:
        """Smooth 100ms interval timer for countdown."""
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start()

    def _apply_stealth(self) -> None:
        """Modal needs click interaction, but keep screen-capture stealth active."""
        try:
            hwnd = int(self.winId())
            set_window_stealth_and_clickthrough(hwnd, click_through=False, hide_from_capture=True)
        except Exception as e:
            logger.warning("Could not apply stealth to TwinQuizModal: %s", e)

    def _on_timer_tick(self) -> None:
        if self.is_resolved:
            return

        self.remaining_sec -= 0.1
        if self.remaining_sec <= 0:
            self.remaining_sec = 0
            self.timer.stop()
            self._handle_timeout()
            return

        self.progress_bar.setValue(int(self.remaining_sec * 10))
        self.lbl_timer.setText(f"⏳ Thời gian còn lại: {int(self.remaining_sec)}s")

        # Color shifts based on urgency
        ratio = self.remaining_sec / self.total_time_sec
        if ratio <= 0.25:
            self.lbl_timer.setStyleSheet("font-size: 12px; font-weight: 800; color: #ef4444; border: none;")
            self.progress_bar.setStyleSheet(
                """
                QProgressBar { background: #1e293b; border-radius: 4px; border: none; }
                QProgressBar::chunk { background: #ef4444; border-radius: 4px; }
                """
            )
        elif ratio <= 0.50:
            self.lbl_timer.setStyleSheet("font-size: 12px; font-weight: 700; color: #f59e0b; border: none;")
            self.progress_bar.setStyleSheet(
                """
                QProgressBar { background: #1e293b; border-radius: 4px; border: none; }
                QProgressBar::chunk { background: #f59e0b; border-radius: 4px; }
                """
            )

    def _handle_answer_selected(self, chosen_key: str) -> None:
        """Evaluates student's answer and updates Spaced Repetition status."""
        if self.is_resolved:
            return

        self.is_resolved = True
        self.timer.stop()

        is_correct = chosen_key.strip().upper() == self.correct_option

        # Disable all option buttons and highlight correct/incorrect
        for key, btn in self.option_buttons.items():
            btn.setEnabled(False)
            if key == self.correct_option:
                btn.setStyleSheet(
                    "background: #065f46; color: white; border: 2px solid #10b981; font-weight: bold; border-radius: 6px;"
                )
            elif key == chosen_key:
                btn.setStyleSheet(
                    "background: #7f1d1d; color: white; border: 2px solid #ef4444; font-weight: bold; border-radius: 6px;"
                )

        new_step = 1
        next_review = ""
        if self.db_manager and self.card_id:
            try:
                new_step, next_review = self.db_manager.update_twin_result(self.card_id, is_correct)
            except Exception as e:
                logger.error("Error updating twin result in DB: %s", e)

        short_explain = self.twin_data.get("short_explanation", "")

        if is_correct:
            self.feedback_banner.setStyleSheet(
                "background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1.5px solid #10b981; border-radius: 6px;"
            )
            self.feedback_banner.setText(
                f"🎉 CHÍNH XÁC! Bạn đã vượt qua bẫy tư duy!\n"
                f"📈 Spaced Repetition: Thăng hạng lên Bước {new_step} (Ôn lại: {next_review})\n"
                f"💡 {short_explain}"
            )
        else:
            self.feedback_banner.setStyleSheet(
                "background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1.5px solid #ef4444; border-radius: 6px;"
            )
            self.feedback_banner.setText(
                f"❌ CHƯA CHÍNH XÁC! Bạn vẫn mắc bẫy tương tự.\n"
                f"🔄 Spaced Repetition: Đặt lại về Bước 1 (Ôn lại vào ngày mai: {next_review})\n"
                f"💡 Lời giải: Đáp án đúng là {self.correct_option}. {short_explain}"
            )

        self.feedback_banner.setVisible(True)
        self.quiz_completed.emit(self.card_id, is_correct)

    def _handle_timeout(self) -> None:
        """Handles countdown expiration (counts as incorrect)."""
        if self.is_resolved:
            return

        self.is_resolved = True
        for key, btn in self.option_buttons.items():
            btn.setEnabled(False)
            if key == self.correct_option:
                btn.setStyleSheet(
                    "background: #065f46; color: white; border: 2px solid #10b981; font-weight: bold; border-radius: 6px;"
                )

        new_step = 1
        next_review = ""
        if self.db_manager and self.card_id:
            try:
                new_step, next_review = self.db_manager.update_twin_result(self.card_id, False)
            except Exception as e:
                logger.error("Error updating twin timeout in DB: %s", e)

        short_explain = self.twin_data.get("short_explanation", "")
        self.feedback_banner.setStyleSheet(
            "background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1.5px solid #ef4444; border-radius: 6px;"
        )
        self.feedback_banner.setText(
            f"⏰ HẾT GIỜ! Bạn chưa phản xạ kịp trước áp lực đồng hồ.\n"
            f"🔄 Spaced Repetition: Đặt lại về Bước 1 (Ôn lại ngày mai: {next_review})\n"
            f"💡 Đáp án đúng là {self.correct_option}. {short_explain}"
        )
        self.feedback_banner.setVisible(True)
        self.quiz_completed.emit(self.card_id, False)

    def _handle_close(self) -> None:
        """Stops timer and dismisses dialog."""
        self.timer.stop()
        self.reject()
