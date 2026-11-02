"""State 3: Brain-Hack Slide Drawer (420px right-docked, Feynman Gatekeeper, If-Then Trigger, Paraphrase Map)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.win32_stealth import set_window_stealth_and_clickthrough

logger = logging.getLogger(__name__)


class SlideDrawer(QWidget):
    """
    Animated right-docked drawer (420px x 100% height).
    Win32 click-through is DISABLED so students can interact and type.
    Includes:
      1. Session performance dashboard (score, time-sinks, guesses)
      2. Interactive Wrong Question navigation chips with browser click-to-scroll
      3. Feynman Gatekeeper Box: locks trap explanation until active recall note is typed
      4. 1-Line If-Then Trigger card in cyan
      5. Paraphrase Mapping comparison table
      6. Twin Challenge launcher button
    """

    question_selected = pyqtSignal(str)  # emits DOM selector or data-hud-qid
    launch_twin_challenge = pyqtSignal(dict)  # emits card data with twin question
    feynman_note_saved = pyqtSignal(int, str)  # card_id, note

    DRAWER_WIDTH = 420

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        db_manager: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.db_manager = db_manager

        self.is_open: bool = False
        self.wrong_questions: List[Dict[str, Any]] = []
        self.selected_index: int = 0
        self.active_card_data: Optional[Dict[str, Any]] = None

        self._init_window()
        self._init_ui()
        self._init_animation()
        self._apply_stealth()

    def _init_window(self) -> None:
        """Configures frameless right-docked drawer."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Initial hidden position off-screen to the right
        self.setGeometry(self.screen_w, 0, self.DRAWER_WIDTH, self.screen_h)

    def _init_ui(self) -> None:
        """Constructs modern cyber-dark drawer layout."""
        self.setStyleSheet(
            """
            QWidget {
                background-color: #0b1120;
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #0f172a;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38bdf8;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header Frame
        header = QFrame(self)
        header.setFixedHeight(64)
        header.setStyleSheet("background-color: #0f172a; border-bottom: 2px solid #1e293b;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("🧠 FEYNMAN GATEKEEPER")
        title_label.setStyleSheet("font-size: 14px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setStyleSheet(
            "QPushButton { background: #1e293b; color: #94a3b8; border-radius: 14px; font-weight: bold; border: none; } "
            "QPushButton:hover { background: #ef4444; color: white; }"
        )
        self.btn_close.clicked.connect(self.toggle)
        header_layout.addWidget(self.btn_close)

        root_layout.addWidget(header)

        # Scrollable Content Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(18, 16, 18, 20)
        self.content_layout.setSpacing(14)

        # 1. Top Metrics Summary
        self._build_metrics_panel()

        # 2. Wrong Question Chips
        self._build_question_chips_panel()

        # 3. 1-Line If-Then Trigger Banner
        self._build_if_then_banner()

        # 4. Feynman Gatekeeper Active Recall Box
        self._build_feynman_gatekeeper_box()

        # 5. Paraphrase Mapping Table
        self._build_paraphrase_table()

        # 6. Action Button: Twin Challenge
        self._build_action_buttons()

        scroll.setWidget(content_widget)
        root_layout.addWidget(scroll)

    def _build_metrics_panel(self) -> None:
        """Metric summary card."""
        panel = QFrame()
        panel.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 6px;")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)

        self.lbl_score = QLabel("🎯 Điểm: --%")
        self.lbl_score.setStyleSheet("font-weight: 700; color: #10b981; font-size: 12px;")
        layout.addWidget(self.lbl_score)

        self.lbl_timesink = QLabel("⏳ Sa lầy: 0")
        self.lbl_timesink.setStyleSheet("font-weight: 700; color: #ef4444; font-size: 12px;")
        layout.addWidget(self.lbl_timesink)

        self.lbl_guess = QLabel("⚡ Đoán nhanh: 0")
        self.lbl_guess.setStyleSheet("font-weight: 700; color: #f59e0b; font-size: 12px;")
        layout.addWidget(self.lbl_guess)

        self.content_layout.addWidget(panel)

    def _build_question_chips_panel(self) -> None:
        """Horizontal question chips for selecting wrong questions."""
        lbl = QLabel("📌 CÂU HỎI SAI CẦN PHÂN TÍCH:")
        lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;")
        self.content_layout.addWidget(lbl)

        self.chips_scroll = QScrollArea()
        self.chips_scroll.setFixedHeight(48)
        self.chips_scroll.setWidgetResizable(True)
        self.chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.chips_container = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)
        self.chips_scroll.setWidget(self.chips_container)

        self.content_layout.addWidget(self.chips_scroll)

    def _build_if_then_banner(self) -> None:
        """Cyan If-Then Trigger card."""
        self.if_then_card = QFrame()
        self.if_then_card.setStyleSheet(
            "background: rgba(56, 189, 248, 0.08); border-left: 4px solid #38bdf8; "
            "border-radius: 8px; padding: 10px; border-top: 1px solid rgba(56, 189, 248, 0.2); "
            "border-right: 1px solid rgba(56, 189, 248, 0.2); border-bottom: 1px solid rgba(56, 189, 248, 0.2);"
        )
        layout = QVBoxLayout(self.if_then_card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title = QLabel("⚡ 1-LINE IF-THEN MENTAL TRIGGER:")
        title.setStyleSheet("font-size: 10px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;")
        layout.addWidget(title)

        self.lbl_if_then = QLabel("Chọn một câu hỏi để hiển thị quy tắc phản xạ tư duy...")
        self.lbl_if_then.setWordWrap(True)
        self.lbl_if_then.setStyleSheet("font-size: 12px; font-weight: 600; color: #f0fdf4; line-height: 1.4;")
        layout.addWidget(self.lbl_if_then)

        self.content_layout.addWidget(self.if_then_card)

    def _build_feynman_gatekeeper_box(self) -> None:
        """Active recall requirement before unlocking trap analysis."""
        self.feynman_card = QFrame()
        self.feynman_card.setStyleSheet(
            "background: #0f172a; border: 1.5px solid #1e293b; border-radius: 10px; padding: 12px;"
        )
        layout = QVBoxLayout(self.feynman_card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        head_layout = QHBoxLayout()
        f_title = QLabel("🔒 FEYNMAN GATEKEEPER")
        f_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #f59e0b;")
        head_layout.addWidget(f_title)

        self.lbl_lock_status = QLabel("ĐANG KHOÁ LỜI GIẢI")
        self.lbl_lock_status.setStyleSheet("font-size: 10px; font-weight: 700; color: #ef4444;")
        head_layout.addWidget(self.lbl_lock_status)
        layout.addLayout(head_layout)

        f_prompt = QLabel("Tại sao lúc nãy bạn lại chọn đáp án sai này?")
        f_prompt.setStyleSheet("font-size: 12px; font-weight: 600; color: #cbd5e1;")
        layout.addWidget(f_prompt)

        self.txt_feynman_input = QPlainTextEdit()
        self.txt_feynman_input.setPlaceholderText("Gõ ngắn gọn 1 câu nguyên nhân chủ quan của bạn để mở khoá phân tích bẫy...")
        self.txt_feynman_input.setFixedHeight(56)
        self.txt_feynman_input.setStyleSheet(
            "background: #1e293b; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; "
            "padding: 6px; font-size: 12px;"
        )
        layout.addWidget(self.txt_feynman_input)

        self.btn_unlock_feynman = QPushButton("🔓 Mở Khoá & Lưu Ghi Chú Feynman")
        self.btn_unlock_feynman.setStyleSheet(
            "QPushButton { background: #0284c7; color: white; font-weight: bold; font-size: 11px; "
            "padding: 7px; border-radius: 6px; border: none; } "
            "QPushButton:hover { background: #0369a1; }"
        )
        self.btn_unlock_feynman.clicked.connect(self._handle_unlock_feynman)
        layout.addWidget(self.btn_unlock_feynman)

        # Trap Explanation (hidden/blurred until unlocked)
        self.lbl_trap_explanation = QLabel("")
        self.lbl_trap_explanation.setWordWrap(True)
        self.lbl_trap_explanation.setStyleSheet(
            "background: rgba(15, 23, 42, 0.85); color: #94a3b8; font-size: 12px; "
            "padding: 8px; border-radius: 6px; border: 1px dashed #334155; line-height: 1.4;"
        )
        self.lbl_trap_explanation.setVisible(False)
        layout.addWidget(self.lbl_trap_explanation)

        self.content_layout.addWidget(self.feynman_card)

    def _build_paraphrase_table(self) -> None:
        """Paraphrase mapping side-by-side comparison."""
        lbl = QLabel("🔄 BẢNG ĐỐI CHIẾU TỪ ĐỒNG NGHĨA (PARAPHRASE):")
        lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8;")
        self.content_layout.addWidget(lbl)

        self.table_paraphrase = QTableWidget(0, 2)
        self.table_paraphrase.setHorizontalHeaderLabels(["Cụm Từ Câu Hỏi", "Cụm Từ Đoạn Văn"])
        self.table_paraphrase.setFixedHeight(120)
        self.table_paraphrase.horizontalHeader().setStretchLastSection(True)
        self.table_paraphrase.verticalHeader().setVisible(False)
        self.table_paraphrase.setStyleSheet(
            "QTableWidget { background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; "
            "color: #f1f5f9; gridline-color: #1e293b; font-size: 11px; } "
            "QHeaderView::section { background: #1e293b; color: #38bdf8; font-weight: bold; padding: 4px; border: none; }"
        )
        self.content_layout.addWidget(self.table_paraphrase)

    def _build_action_buttons(self) -> None:
        """Twin challenge action button."""
        self.btn_twin_challenge = QPushButton("🚀 LÀM THỬ THÁCH CÂU HỎI SINH ĐÔI (TWIN QUIZ)")
        self.btn_twin_challenge.setFixedHeight(40)
        self.btn_twin_challenge.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #2563eb); "
            "color: white; font-weight: 800; font-size: 12px; border-radius: 8px; border: none; } "
            "QPushButton:hover { background: #0369a1; }"
        )
        self.btn_twin_challenge.clicked.connect(self._handle_launch_twin)
        self.content_layout.addWidget(self.btn_twin_challenge)

    def _init_animation(self) -> None:
        """Slide-in / slide-out smooth QPropertyAnimation."""
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(280)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _apply_stealth(self) -> None:
        """Click-through DISABLED so students can interact and type."""
        try:
            hwnd = int(self.winId())
            set_window_stealth_and_clickthrough(hwnd, click_through=False, hide_from_capture=True)
            logger.info("Drawer Win32 setup completed: click-through disabled, stealth active (HWND %s)", hwnd)
        except Exception as e:
            logger.warning("Could not set Win32 properties on Drawer: %s", e)

    # ==========================================
    # DRAWER TOGGLE & ANIMATION
    # ==========================================

    def toggle(self) -> None:
        """Smoothly opens or closes the drawer."""
        if self.is_open:
            self.close_drawer()
        else:
            self.open_drawer()

    def open_drawer(self) -> None:
        """Slides drawer in from right."""
        self.show()
        self.raise_()
        self._apply_stealth()

        start_rect = QRect(self.screen_w, 0, self.DRAWER_WIDTH, self.screen_h)
        end_rect = QRect(self.screen_w - self.DRAWER_WIDTH, 0, self.DRAWER_WIDTH, self.screen_h)

        self.anim.stop()
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.start()
        self.is_open = True

    def close_drawer(self) -> None:
        """Slides drawer out to right."""
        start_rect = self.geometry()
        end_rect = QRect(self.screen_w, 0, self.DRAWER_WIDTH, self.screen_h)

        self.anim.stop()
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.finished.connect(self._on_close_finished)
        self.anim.start()
        self.is_open = False

    def _on_close_finished(self) -> None:
        try:
            self.anim.finished.disconnect(self._on_close_finished)
        except Exception:
            pass
        self.hide()

    # ==========================================
    # DATA POPULATION
    # ==========================================

    def load_session_data(
        self,
        session_summary: Dict[str, Any],
        wrong_questions: List[Dict[str, Any]],
    ) -> None:
        """Fills drawer with session metrics and wrong questions."""
        self.wrong_questions = wrong_questions or []

        # Update summary metrics
        score = session_summary.get("estimated_score", 0.0)
        total = session_summary.get("total_questions", 0)
        wrong = session_summary.get("wrong_count", len(self.wrong_questions))
        correct = total - wrong if total >= wrong else 0
        timesink = session_summary.get("timesink_count", 0)
        guess = session_summary.get("guess_count", 0)

        self.lbl_score.setText(f"🎯 Điểm: {score}% ({correct}/{total})")
        self.lbl_timesink.setText(f"⏳ Sa lầy: {timesink}")
        self.lbl_guess.setText(f"⚡ Đoán nhanh: {guess}")

        # Clear and build chips
        for i in reversed(range(self.chips_layout.count())):
            w = self.chips_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        if not self.wrong_questions:
            no_wrong = QLabel("🎉 Tuyệt vời! Bạn không sai câu nào trong phiên thi này.")
            no_wrong.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
            self.chips_layout.addWidget(no_wrong)
            self._display_question_card(None)
            return

        for idx, q in enumerate(self.wrong_questions):
            q_num = q.get("question_number", idx + 1)
            chip = QPushButton(f"#{q_num}")
            chip.setCheckable(True)
            chip.setChecked(idx == 0)
            chip.setFixedHeight(32)
            chip.setStyleSheet(
                "QPushButton { background: #1e293b; color: #f8fafc; font-weight: 700; border-radius: 6px; "
                "padding: 0 10px; border: 1px solid #334155; } "
                "QPushButton:checked { background: #0284c7; border-color: #38bdf8; color: white; } "
                "QPushButton:hover:!checked { background: #334155; }"
            )
            # Capture index in closure
            chip.clicked.connect(lambda checked, i=idx: self.select_question_by_index(i))
            self.chips_layout.addWidget(chip)

        self.chips_layout.addStretch()
        self.select_question_by_index(0)

    def select_question_by_index(self, index: int) -> None:
        """Selects a question chip and displays its details."""
        if not self.wrong_questions or index >= len(self.wrong_questions):
            return

        self.selected_index = index

        # Update chip active state
        for i in range(self.chips_layout.count()):
            widget = self.chips_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                widget.setChecked(i == index)

        q_item = self.wrong_questions[index]
        self._display_question_card(q_item)

        # Emit signal to scroll browser window
        selector = q_item.get("dom_selector", f'[data-hud-qid="{q_item.get("question_number", 1)}"]')
        self.question_selected.emit(selector)

    def _display_question_card(self, q_item: Optional[Dict[str, Any]]) -> None:
        """Populates cards, triggers, and paraphrase table for selected question."""
        if not q_item:
            self.active_card_data = None
            self.lbl_if_then.setText("Không có dữ liệu câu hỏi sai.")
            self.lbl_trap_explanation.setText("")
            self.lbl_trap_explanation.setVisible(False)
            self.table_paraphrase.setRowCount(0)
            return

        self.active_card_data = q_item

        # 1. If-Then Trigger
        trigger = q_item.get("if_then_trigger", "Nếu gặp bẫy logic -> Hãy đối chiếu cấu trúc chủ-vị & Loại trừ phương án cực đoan.")
        self.lbl_if_then.setText(trigger)

        # 2. Feynman Gatekeeper check
        saved_note = q_item.get("feynman_user_note", "").strip()
        trap_explain = q_item.get("trap_explanation", "Bẫy từ vựng trùng lặp và suy diễn vượt quá nội dung bài đọc.")

        if saved_note:
            self.txt_feynman_input.setPlainText(saved_note)
            self.lbl_lock_status.setText("ĐÃ MỞ KHOÁ (ACTIVE RECALL ✓)")
            self.lbl_lock_status.setStyleSheet("font-size: 10px; font-weight: 700; color: #10b981;")
            self.lbl_trap_explanation.setText(f"💡 PHÂN TÍCH BẪY CHI TIẾT:\n{trap_explain}")
            self.lbl_trap_explanation.setVisible(True)
        else:
            self.txt_feynman_input.clear()
            self.lbl_lock_status.setText("ĐANG KHOÁ LỜI GIẢI")
            self.lbl_lock_status.setStyleSheet("font-size: 10px; font-weight: 700; color: #ef4444;")
            self.lbl_trap_explanation.setText("")
            self.lbl_trap_explanation.setVisible(False)

        # 3. Paraphrase Table
        mapping = q_item.get("paraphrase_mapping", [])
        self.table_paraphrase.setRowCount(0)
        for pair in mapping:
            r = self.table_paraphrase.rowCount()
            self.table_paraphrase.insertRow(r)
            q_ph = pair.get("question_phrase", "")
            p_ph = pair.get("passage_phrase", "")
            self.table_paraphrase.setItem(r, 0, QTableWidgetItem(q_ph))
            self.table_paraphrase.setItem(r, 1, QTableWidgetItem(p_ph))

    def _handle_unlock_feynman(self) -> None:
        """Unlocks trap explanation once student types active recall reflection."""
        note = self.txt_feynman_input.toPlainText().strip()
        if len(note) < 4:
            self.txt_feynman_input.setStyleSheet(
                "background: #1e293b; color: #f8fafc; border: 1.5px solid #ef4444; border-radius: 6px; padding: 6px;"
            )
            return

        self.txt_feynman_input.setStyleSheet(
            "background: #1e293b; color: #f8fafc; border: 1.5px solid #10b981; border-radius: 6px; padding: 6px;"
        )

        if self.active_card_data:
            card_id = self.active_card_data.get("card_id")
            if card_id and self.db_manager:
                self.db_manager.update_feynman_note(card_id, note)
                self.feynman_note_saved.emit(card_id, note)

            self.active_card_data["feynman_user_note"] = note
            trap_explain = self.active_card_data.get("trap_explanation", "Bẫy phân tán tư duy.")
            self.lbl_lock_status.setText("ĐÃ MỞ KHOÁ (ACTIVE RECALL ✓)")
            self.lbl_lock_status.setStyleSheet("font-size: 10px; font-weight: 700; color: #10b981;")
            self.lbl_trap_explanation.setText(f"💡 PHÂN TÍCH BẪY CHI TIẾT:\n{trap_explain}")
            self.lbl_trap_explanation.setVisible(True)

    def _handle_launch_twin(self) -> None:
        """Emits signal to open twin quiz modal."""
        if self.active_card_data:
            self.launch_twin_challenge.emit(self.active_card_data)
