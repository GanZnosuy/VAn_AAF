"""Central Control Dashboard Window for TSA & IELTS Cognitive Training HUD.
Provides a comprehensive fullscreen/centered control center for adjustments, live status, and spaced repetition.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QRect, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class CentralDashboardWindow(QMainWindow):
    """
    High-End Central Control Dashboard (1000px x 700px, centered on screen).
    Allows students to fine-tune dwell thresholds, inspect real-time sensor metrics,
    review Spaced Repetition flashcards, launch Chrome CDP, and trigger exam mode.
    """

    config_saved = pyqtSignal(dict)
    start_exam_mode = pyqtSignal()
    open_drawer_requested = pyqtSignal()
    open_twin_challenge_requested = pyqtSignal(dict)
    profile_changed = pyqtSignal(str)
    request_vision_sync = pyqtSignal()
    request_reset_q1 = pyqtSignal()
    request_launch_chrome = pyqtSignal()

    PROFILE_NAMES = {
        "YOUPASS_READING": "📖 YouPass Reading (IELTS)",
        "STUDY4_READING": "📘 Study4 Reading (IELTS)",
        "TSA_MODE": "⚡ TSA Đánh Giá Năng Lực (HUST/VNU)",
        "HOCIZ_TSA": "🎯 Hociz.vn - TSA Đánh Giá Tư Duy",
        "IELTS_LISTENING": "🎧 IELTS Listening",
        "IELTS_WRITING": "✍️ IELTS Writing",
    }

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        config: Optional[Dict[str, Any]] = None,
        db_manager: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.config = config or {}
        self.db_manager = db_manager

        # Base directories
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, "config.json")
        self.icon_path = os.path.join(base_dir, "assets", "hud_icon.ico")

        self._init_window()
        self._init_ui()

    def _init_window(self) -> None:
        """Window geometry, icon, and dark cyber styling."""
        self.setWindowTitle("TSA & IELTS STEALTH HUD - TRUNG TÂM ĐIỀU KHIỂN & CÀI ĐẶT")
        win_w, win_h = 1020, 720
        pos_x = max(0, (self.screen_w - win_w) // 2)
        pos_y = max(0, (self.screen_h - win_h) // 2)
        self.setGeometry(pos_x, pos_y, win_w, win_h)
        self.setMinimumSize(940, 640)

        if os.path.isfile(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0b1120;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background: #0f172a;
                border-radius: 10px;
                top: -1px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 22px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 700;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #0284c7;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
                color: #f8fafc;
            }
            QGroupBox {
                border: 1.5px solid #1e293b;
                border-radius: 10px;
                margin-top: 14px;
                font-weight: bold;
                font-size: 13px;
                color: #38bdf8;
                padding-top: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QLabel {
                color: #e2e8f0;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #1e293b;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #0284c7;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #38bdf8;
                width: 18px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 9px;
            }
            QComboBox, QLineEdit {
                background: #1e293b;
                color: #f8fafc;
                border: 1.5px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1.5px solid #38bdf8;
            }
            QTableWidget {
                background: #0f172a;
                color: #f8fafc;
                gridline-color: #1e293b;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                font-size: 12px;
                padding: 6px;
                border: 1px solid #0f172a;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 20px;
                border-radius: 5px;
            }
            """
        )

    def _init_ui(self) -> None:
        """Constructs layout, tabs, and action panels."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 18)
        main_layout.setSpacing(14)

        # 1. Header Banner
        main_layout.addLayout(self._build_header_banner())

        # 2. Main Tabs
        self.tabs = QTabWidget()
        self.post_exam_tab = self._build_post_exam_tab()
        self.tabs.addTab(self.post_exam_tab, "🎯 Báo Cáo & Rút Kinh Nghiệm Sau Thi")
        self.tabs.addTab(self._build_dashboard_tab(), "📊 Bảng Điều Khiển & Trạng Thái")
        self.tabs.addTab(self._build_thresholds_tab(), "⚙️ Cài Đặt Ngưỡng Thời Gian & Bẫy Logic")
        self.tabs.addTab(self._build_memory_cards_tab(), "🧠 Ngân Hàng Ký Ức (Spaced Repetition)")
        self.tabs.addTab(self._build_hotkeys_guide_tab(), "⌨️ Phím Tắt & Hướng Dẫn Phòng Thi")
        main_layout.addWidget(self.tabs)

        # 3. Footer Action Strip
        main_layout.addLayout(self._build_footer_strip())

    def _build_header_banner(self) -> QHBoxLayout:
        """Top banner with app branding and live status pills."""
        header = QHBoxLayout()

        # Logo and Title
        title_box = QVBoxLayout()
        title_label = QLabel("⚡ TSA & IELTS STEALTH COGNITIVE HUD")
        title_label.setStyleSheet("font-size: 18px; font-weight: 900; color: #38bdf8; letter-spacing: 0.5px;")
        sub_label = QLabel("Trung Tâm Điều Khiển Nhận Thức • Tàng Hình Tuyệt Đối • Tự Động Sửa Sai Reflexion AI")
        sub_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(title_label)
        title_box.addWidget(sub_label)
        header.addLayout(title_box)

        header.addStretch()

        # Live Badges
        b1 = QLabel("● WIN32 STEALTH")
        b1.setStyleSheet("background: rgba(16, 185, 129, 0.15); color: #10b981; font-weight: 800; font-size: 11px; padding: 6px 10px; border-radius: 6px; border: 1px solid #10b981;")
        b2 = QLabel("● SENSOR 0.5 FPS")
        b2.setStyleSheet("background: rgba(56, 189, 248, 0.15); color: #38bdf8; font-weight: 800; font-size: 11px; padding: 6px 10px; border-radius: 6px; border: 1px solid #38bdf8;")
        b3 = QLabel("● WAL DB READY")
        b3.setStyleSheet("background: rgba(245, 158, 11, 0.15); color: #f59e0b; font-weight: 800; font-size: 11px; padding: 6px 10px; border-radius: 6px; border: 1px solid #f59e0b;")

        header.addWidget(b1)
        header.addWidget(b2)
        header.addWidget(b3)

        return header

    # =========================================================================
    # TAB 0: POST-EXAM ANALYSIS & REFLECTION
    # =========================================================================
    def _build_post_exam_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        # Overview banner
        top_banner = QFrame()
        top_banner.setStyleSheet("background: #1e293b; border-radius: 10px; padding: 12px;")
        tb_layout = QHBoxLayout(top_banner)
        tb_layout.setContentsMargins(12, 6, 12, 6)

        title_vbox = QVBoxLayout()
        t_label = QLabel("🎯 BÁO CÁO PHÂN TÍCH QUÁ TRÌNH LÀM BÀI & RÚT KINH NGHIỆM AI")
        t_label.setStyleSheet("font-size: 15px; font-weight: 900; color: #38bdf8;")
        s_label = QLabel("Tự động kích hoạt khi bấm 'Nộp bài' trên web • Nhận diện sa lầy, đoán vội và đúc kết quy tắc If-Then")
        s_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_vbox.addWidget(t_label)
        title_vbox.addWidget(s_label)
        tb_layout.addLayout(title_vbox)
        tb_layout.addStretch()

        self.btn_load_demo = QPushButton("🧪 Xem Dữ Liệu Phân Tích Mẫu")
        self.btn_load_demo.setStyleSheet(
            "background: #0284c7; color: white; font-weight: bold; font-size: 12px; padding: 6px 14px; border-radius: 6px; border: none;"
        )
        self.btn_load_demo.clicked.connect(self._load_demo_post_exam_data)
        tb_layout.addWidget(self.btn_load_demo)
        layout.addWidget(top_banner)

        # 4 Post-Exam Metric Cards
        self.post_metrics_layout = QHBoxLayout()
        self.post_metrics_layout.setSpacing(12)

        self.card_post_score = self._create_metric_box("🎯 ĐIỂM SỐ & TỶ LỆ ĐÚNG", "Chưa làm bài", "Đang chờ nộp đề thi", "#10b981")
        self.card_post_time = self._create_metric_box("⏱️ THỜI GIAN LÀM BÀI", "-- phút", "Tốc độ trung bình / câu", "#38bdf8")
        self.card_post_timesink = self._create_metric_box("⚠️ CÂU SA LẦY (>120s)", "0 câu", "Mất quá nhiều thời gian", "#f43f5e")
        self.card_post_guess = self._create_metric_box("⚡ CÂU ĐOÁN VỘI (<12s)", "0 câu", "Khoanh bừa / đổi đáp án vội", "#a855f7")

        self.post_metrics_layout.addWidget(self.card_post_score)
        self.post_metrics_layout.addWidget(self.card_post_time)
        self.post_metrics_layout.addWidget(self.card_post_timesink)
        self.post_metrics_layout.addWidget(self.card_post_guess)
        layout.addLayout(self.post_metrics_layout)

        # Scroll Area for Detailed Wrong Questions & AI Reflection
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.post_exam_scroll_container = QWidget()
        self.post_exam_scroll_layout = QVBoxLayout(self.post_exam_scroll_container)
        self.post_exam_scroll_layout.setContentsMargins(4, 4, 4, 4)
        self.post_exam_scroll_layout.setSpacing(14)

        # Initial Empty State Widget
        self.empty_state_lbl = QLabel(
            "💡 CHƯA CÓ BÀI THI NÀO ĐƯỢC NỘP TRONG PHIÊN NÀY.\n\n"
            "👉 Bạn chỉ cần mở đề thi trên Chrome (Hociz.vn, Study4.com, YouPass.vn) và làm bài bình thường.\n"
            "🚀 Ngay khi bạn bấm 'Nộp bài', cửa sổ này sẽ TỰ ĐỘNG BẬT LÊN giữa màn hình và tổng hợp toàn bộ câu sai,\n"
            "chỉ rõ các bẫy tư duy mà bạn mắc phải, kèm các quy tắc If-Then để rút kinh nghiệm sâu sắc!"
        )
        self.empty_state_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 13px; line-height: 1.6; padding: 40px; background: #0f172a; "
            "border: 1.5px dashed #334155; border-radius: 12px;"
        )
        self.empty_state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.post_exam_scroll_layout.addWidget(self.empty_state_lbl)
        self.post_exam_scroll_layout.addStretch()

        scroll.setWidget(self.post_exam_scroll_container)
        layout.addWidget(scroll)

        return widget

    def _update_metric_box_val(self, frame: QFrame, val: str, sub: str) -> None:
        """Updates text values inside a metric box frame."""
        labels = frame.findChildren(QLabel)
        if len(labels) >= 3:
            labels[1].setText(val)
            labels[2].setText(sub)

    def load_post_exam_data(
        self, summary: Dict[str, Any], wrong_questions: List[Dict[str, Any]]
    ) -> None:
        """
        Populates aggregate metrics and detailed AI reflection cards after exam submission.
        """
        total = summary.get("total_questions", 0)
        wrong = summary.get("wrong_count", len(wrong_questions))
        timesink = summary.get("timesink_count", sum(1 for q in wrong_questions if q.get("is_timesink")))
        guess = summary.get("guess_count", sum(1 for q in wrong_questions if q.get("is_guessed")))
        correct = max(0, total - wrong) if total > 0 else 0
        pct = round((correct / total * 100.0) if total > 0 else 0.0, 1)

        self._update_metric_box_val(
            self.card_post_score,
            f"{pct}%" if total > 0 else f"{wrong} câu sai",
            f"{correct}/{total} Câu Đúng" if total > 0 else "Cần khắc phục",
        )
        self._update_metric_box_val(
            self.card_post_time,
            f"{total * 1.5:.0f} phút" if total > 0 else "--",
            "Tốc độ ~1.5 phút/câu",
        )
        self._update_metric_box_val(
            self.card_post_timesink,
            f"{timesink} câu",
            f"Chiếm ~{timesink * 2.5:.0f} phút lãng phí",
        )
        self._update_metric_box_val(
            self.card_post_guess,
            f"{guess} câu",
            "Đoán mò / đổi đáp án vội",
        )

        # Clear scroll area
        while self.post_exam_scroll_layout.count() > 0:
            item = self.post_exam_scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not wrong_questions:
            congrats = QLabel(
                "🎉 TUYỆT VỜI! BẠN ĐÃ LÀM ĐÚNG 100% HOẶC KHÔNG CÓ CÂU SAI NÀO!\n"
                "Tiếp tục duy trì phong độ cho các bài thi tiếp theo."
            )
            congrats.setStyleSheet(
                "color: #10b981; font-size: 15px; font-weight: bold; padding: 40px; background: #0f172a; "
                "border: 1.5px solid #10b981; border-radius: 12px;"
            )
            congrats.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.post_exam_scroll_layout.addWidget(congrats)
            self.post_exam_scroll_layout.addStretch()
            return

        for q in wrong_questions:
            q_card = self._create_wrong_question_card(q)
            self.post_exam_scroll_layout.addWidget(q_card)

        self.post_exam_scroll_layout.addStretch()

        # Switch to post exam tab
        self.tabs.setCurrentWidget(self.post_exam_tab)

    def _create_wrong_question_card(self, q: Dict[str, Any]) -> QFrame:
        """Builds a rich cognitive takeaway card for a single wrong question."""
        card = QFrame()
        card.setStyleSheet(
            "background: #131d31; border: 1.5px solid #334155; border-radius: 12px; padding: 14px;"
        )
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(10)

        # 1. Header with Badges
        h_layout = QHBoxLayout()
        q_num = q.get("question_number", 1)
        sec = q.get("section_tag", "TSA / IELTS")
        dwell = q.get("dwell_time_sec", 0.0)

        title_lbl = QLabel(f"CÂU #{q_num:02d} • {sec}")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 900; color: #38bdf8;")
        h_layout.addWidget(title_lbl)

        h_layout.addStretch()

        time_badge = QLabel(f"⏱️ {dwell:.0f}s")
        time_badge.setStyleSheet(
            "background: #1e293b; color: #cbd5e1; font-weight: bold; font-size: 11px; "
            "padding: 4px 8px; border-radius: 6px;"
        )
        h_layout.addWidget(time_badge)

        if q.get("is_timesink"):
            ts_badge = QLabel("⚠️ SA LẦY")
            ts_badge.setStyleSheet(
                "background: rgba(244, 63, 94, 0.2); color: #f43f5e; font-weight: 800; "
                "font-size: 11px; padding: 4px 8px; border-radius: 6px; border: 1px solid #f43f5e;"
            )
            h_layout.addWidget(ts_badge)

        if q.get("is_guessed"):
            g_badge = QLabel("⚡ ĐOÁN VỘI")
            g_badge.setStyleSheet(
                "background: rgba(168, 85, 247, 0.2); color: #a855f7; font-weight: 800; "
                "font-size: 11px; padding: 4px 8px; border-radius: 6px; border: 1px solid #a855f7;"
            )
            h_layout.addWidget(g_badge)

        c_layout.addLayout(h_layout)

        # 2. Question Text
        q_text = q.get("question_text", "Nội dung câu hỏi")
        q_lbl = QLabel(q_text)
        q_lbl.setWordWrap(True)
        q_lbl.setStyleSheet("font-size: 13px; color: #f1f5f9; line-height: 1.4;")
        c_layout.addWidget(q_lbl)

        # 3. Answer Comparison Box
        ans_box = QFrame()
        ans_box.setStyleSheet("background: #0f172a; border-radius: 8px; padding: 10px;")
        ans_layout = QVBoxLayout(ans_box)
        ans_layout.setSpacing(6)

        user_ans = q.get("user_answer", "Chưa rõ")
        off_ans = q.get("official_answer", "Chưa rõ")

        u_lbl = QLabel(f"❌ Bạn đã chọn: {user_ans}")
        u_lbl.setStyleSheet("color: #f87171; font-weight: bold; font-size: 12px;")
        o_lbl = QLabel(f"✅ Đáp án chuẩn: {off_ans}")
        o_lbl.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 12px;")
        ans_layout.addWidget(u_lbl)
        ans_layout.addWidget(o_lbl)

        exp = q.get("platform_explanation")
        if exp:
            exp_lbl = QLabel(f"📖 Giải thích đề bài: {exp}")
            exp_lbl.setWordWrap(True)
            exp_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 4px;")
            ans_layout.addWidget(exp_lbl)

        c_layout.addWidget(ans_box)

        # 4. Cognitive Reflection (Trap & If-Then Trigger)
        trap = q.get("trap_explanation") or q.get("trap_analysis")
        trigger = q.get("if_then_trigger")

        if trap or trigger:
            ref_box = QFrame()
            ref_box.setStyleSheet(
                "background: rgba(30, 41, 59, 0.7); border-left: 3px solid #38bdf8; "
                "border-radius: 6px; padding: 10px;"
            )
            ref_layout = QVBoxLayout(ref_box)
            ref_layout.setSpacing(6)

            if trap:
                t_lbl = QLabel(f"🚨 Bẫy tư duy bạn đã mắc: {trap}")
                t_lbl.setWordWrap(True)
                t_lbl.setStyleSheet("color: #fbbf24; font-size: 12px; font-weight: 600;")
                ref_layout.addWidget(t_lbl)

            if trigger:
                tr_lbl = QLabel(f"💡 Quy tắc rút kinh nghiệm (If-Then): {trigger}")
                tr_lbl.setWordWrap(True)
                tr_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 700;")
                ref_layout.addWidget(tr_lbl)

            c_layout.addWidget(ref_box)

        # 5. Action Buttons (Twin Challenge)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        twin_q = q.get("twin_question")
        if twin_q:
            btn_twin = QPushButton("🧪 Làm Thử Câu Hỏi Sinh Đôi (Twin Challenge - 60s)")
            btn_twin.setStyleSheet(
                "background: #0284c7; color: white; font-weight: bold; font-size: 12px; "
                "padding: 6px 14px; border-radius: 6px; border: none;"
            )
            btn_twin.clicked.connect(lambda _, card=q: self.open_twin_challenge_requested.emit(card))
            btn_layout.addWidget(btn_twin)

        c_layout.addLayout(btn_layout)
        return card

    def _load_demo_post_exam_data(self) -> None:
        """Loads sample TSA wrong question analysis for offline preview."""
        demo_summary = {
            "total_questions": 20,
            "wrong_count": 3,
            "timesink_count": 2,
            "guess_count": 1,
            "estimated_score": 85.0,
        }
        demo_wrong = [
            {
                "question_number": 7,
                "section_tag": "TSA Đánh Giá Năng Lực",
                "dwell_time_sec": 145.0,
                "is_timesink": 1,
                "is_guessed": 0,
                "question_text": "Một công ty công nghệ tuyên bố: 'Mọi nhân viên sử dụng AI đều tăng năng suất 30%. Do đó, AI là nguyên nhân duy nhất dẫn đến sự bứt phá của doanh nghiệp.' Phát biểu nào sau đây làm suy yếu lập luận trên nhất?",
                "user_answer": "B. Một số nhân viên không thích giao diện của công cụ AI mới.",
                "official_answer": "D. Trong cùng kỳ, công ty đã cắt giảm 50% các cuộc họp vô bổ và tái cấu trúc quy trình.",
                "platform_explanation": "Bẫy ngụy biện nguyên nhân thứ ba (Confounding Variable).",
                "trap_explanation": "Bạn đã chọn B vì có từ 'nhân viên' giống đề bài, nhưng B chỉ là cảm xúc cá nhân không tác động đến lập luận nhân quả.",
                "if_then_trigger": "Nếu gặp bài toán Làm suy yếu lập luận nhân quả (A sinh ra B) -> Lập tức tìm đáp án chỉ ra Nguyên nhân thứ ba (C) tạo ra kết quả B!",
                "twin_question": {
                    "time_limit_sec": 60,
                    "stem": "[CÂU HỎI SINH ĐÔI] Thành phố X lắp đặt thêm 100 camera giao thông và tỷ lệ tai nạn giảm 20%. Thị trưởng kết luận camera là lý do giảm tai nạn. Lựa chọn nào làm suy yếu kết luận này nhất?",
                    "options": {
                        "A": "Người dân phàn nàn camera chụp vi phạm quá khắt khe.",
                        "B": "Cùng lúc đó, mức phạt vi phạm nồng độ cồn tăng gấp 5 lần và cảnh sát tuần tra 24/7.",
                        "C": "Một số camera bị mờ sương vào ban đêm.",
                        "D": "Thành phố Y lân cận cũng có tỷ lệ tai nạn tương tự."
                    },
                    "correct_option": "B",
                    "short_explanation": "Yếu tố phạt nồng độ cồn và tuần tra 24/7 chính là nguyên nhân thứ ba (C) dẫn đến giảm tai nạn."
                }
            },
            {
                "question_number": 14,
                "section_tag": "Tư Duy Đọc Hiểu",
                "dwell_time_sec": 9.0,
                "is_timesink": 0,
                "is_guessed": 1,
                "question_text": "Theo đoạn văn số 3, tác động trực tiếp nhất của cuộc cách mạng bán dẫn vào giữa thế kỷ 20 là gì?",
                "user_answer": "A. Giảm giá thành toàn bộ các thiết bị gia dụng.",
                "official_answer": "C. Cho phép thu nhỏ mạch điện tử và ra đời máy tính cá nhân.",
                "platform_explanation": "Đoạn 3 khẳng định bán dẫn thay thế bóng chân không cồng kềnh, mở đường cho vi xử lý.",
                "trap_explanation": "Bạn chỉ dừng lại 9 giây và chọn vội A vì thấy quen tai mà không đối chiếu từ khóa then chốt trong đoạn 3.",
                "if_then_trigger": "Nếu còn dưới 15 giây mà câu hỏi hỏi 'Theo đoạn X' -> Tuyệt đối không chọn đáp án quen tai, định vị ngay danh từ riêng/mốc thời gian để quét nhanh!",
                "twin_question": {
                    "time_limit_sec": 45,
                    "stem": "[CÂU HỎI SINH ĐÔI] Tác động trực tiếp nhất của phát minh động cơ hơi nước trong thế kỷ 18 là gì?",
                    "options": {
                        "A": "Tất cả mọi người đều có xe ô tô riêng để đi lại.",
                        "B": "Giải phóng sức lao động khỏi các nguồn năng lượng tự nhiên như nước và gió.",
                        "C": "Làm tăng đột biến số lượng thợ thủ công may mặc gia đình.",
                        "D": "Xóa bỏ hoàn toàn việc sử dụng than đá."
                    },
                    "correct_option": "B",
                    "short_explanation": "Động cơ hơi nước cho phép đặt nhà máy ở bất kỳ đâu thay vì phụ thuộc dòng nước hoặc sức gió."
                }
            }
        ]
        self.load_post_exam_data(demo_summary, demo_wrong)

    # =========================================================================
    # TAB 1: DASHBOARD & QUICK LAUNCH
    # =========================================================================
    def _build_dashboard_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        # Profile Selector Banner
        prof_card = QFrame()
        prof_card.setStyleSheet("background: #1e293b; border-radius: 10px; padding: 12px;")
        prof_layout = QHBoxLayout(prof_card)

        prof_title = QLabel("🎯 Chế Độ Thi Đang Luyện Tập:")
        prof_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc;")
        prof_layout.addWidget(prof_title)

        self.combo_profile = QComboBox()
        for key, name in self.PROFILE_NAMES.items():
            self.combo_profile.addItem(name, key)

        cur_prof = self.config.get("active_profile", "YOUPASS_READING")
        idx = list(self.PROFILE_NAMES.keys()).index(cur_prof) if cur_prof in self.PROFILE_NAMES else 0
        self.combo_profile.setCurrentIndex(idx)
        self.combo_profile.currentIndexChanged.connect(self._on_profile_dropdown_changed)
        self.combo_profile.setFixedWidth(360)
        prof_layout.addWidget(self.combo_profile)

        prof_layout.addStretch()

        btn_launch_exam = QPushButton("🚀 Bắt Đầu Làm Bài Ngay (Alt+H)")
        btn_launch_exam.setFixedHeight(38)
        btn_launch_exam.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4); "
            "color: white; font-weight: bold; font-size: 13px; padding: 0 18px; border-radius: 8px; border: none; } "
            "QPushButton:hover { background: #0284c7; }"
        )
        btn_launch_exam.clicked.connect(self._trigger_start_exam)
        prof_layout.addWidget(btn_launch_exam)

        layout.addWidget(prof_card)

        # 3 Metrics Grid Cards
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(14)

        self.metric_cards = [
            self._create_metric_box("🟢 Trạng Thái Tàng Hình", "HOẠT ĐỘNG (100% Click-through)", "Vô hình trước OBS, Zoom, PrintScreen", "#10b981"),
            self._create_metric_box("👁️ Cảm Biến Thị Giác", "0.5 FPS (2.0s / lần quét)", "Dynamic ROI + 64-bit dHash Hamming", "#38bdf8"),
            self._create_metric_box("🌐 Trình Duyệt CDP", "Cổng 9222 (Playwright Ready)", "Tự động trích xuất kết quả sau nộp", "#f59e0b"),
        ]
        for mc in self.metric_cards:
            metrics_layout.addWidget(mc)
        layout.addLayout(metrics_layout)

        # Quick Actions Grid
        act_group = QGroupBox("⚡ BẢNG ĐIỀU KHIỂN TÁC VỤ NHANH")
        act_layout = QGridLayout(act_group)
        act_layout.setSpacing(12)

        btn_chrome_cdp = QPushButton("🌐 1-Click Khởi Động Google Chrome với Cổng CDP 9222")
        btn_chrome_cdp.setFixedHeight(46)
        btn_chrome_cdp.setStyleSheet(
            "QPushButton { background: #1e293b; color: #38bdf8; border: 1.5px solid #0284c7; "
            "border-radius: 8px; font-weight: bold; font-size: 13px; } "
            "QPushButton:hover { background: #0369a1; color: white; }"
        )
        btn_chrome_cdp.clicked.connect(self._launch_chrome_cdp)
        act_layout.addWidget(btn_chrome_cdp, 0, 0)

        btn_open_drawer = QPushButton("📂 Mở Ngăn Kéo Ôn Tập Feynman & Sửa Câu Sai (Alt+Z)")
        btn_open_drawer.setFixedHeight(46)
        btn_open_drawer.setStyleSheet(
            "QPushButton { background: #1e293b; color: #f59e0b; border: 1.5px solid #d97706; "
            "border-radius: 8px; font-weight: bold; font-size: 13px; } "
            "QPushButton:hover { background: #b45309; color: white; }"
        )
        btn_open_drawer.clicked.connect(self._trigger_open_drawer)
        act_layout.addWidget(btn_open_drawer, 0, 1)

        btn_sync_now = QPushButton("⚡ Kích Hoạt Đồng Bộ Cào Đề & Phân Tích Gemini AI (Alt+S)")
        btn_sync_now.setFixedHeight(46)
        btn_sync_now.setStyleSheet(
            "QPushButton { background: #1e293b; color: #a855f7; border: 1.5px solid #9333ea; "
            "border-radius: 8px; font-weight: bold; font-size: 13px; } "
            "QPushButton:hover { background: #7e22ce; color: white; }"
        )
        btn_sync_now.clicked.connect(self._trigger_open_drawer)
        act_layout.addWidget(btn_sync_now, 1, 0)

        btn_test_twin = QPushButton("🧪 Thử Thách Câu Hỏi Sinh Đôi (Twin Quiz Modal)")
        btn_test_twin.setFixedHeight(46)
        btn_test_twin.setStyleSheet(
            "QPushButton { background: #1e293b; color: #10b981; border: 1.5px solid #059669; "
            "border-radius: 8px; font-weight: bold; font-size: 13px; } "
            "QPushButton:hover { background: #047857; color: white; }"
        )
        btn_test_twin.clicked.connect(self._trigger_test_twin)
        act_layout.addWidget(btn_test_twin, 1, 1)

        layout.addWidget(act_group)
        layout.addStretch()
        return widget

    def _create_metric_box(self, title: str, val: str, sub: str, accent: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"background: #131d31; border: 1.5px solid {accent}; border-radius: 10px; padding: 12px;"
        )
        fl = QVBoxLayout(frame)
        fl.setSpacing(4)
        fl.setContentsMargins(8, 8, 8, 8)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {accent}; text-transform: uppercase;")
        fl.addWidget(t_lbl)

        v_lbl = QLabel(val)
        v_lbl.setStyleSheet("font-size: 14px; font-weight: 900; color: #ffffff;")
        fl.addWidget(v_lbl)

        s_lbl = QLabel(sub)
        s_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        fl.addWidget(s_lbl)

        return frame

    # =========================================================================
    # TAB 2: THRESHOLDS & SETTINGS
    # =========================================================================
    def _build_thresholds_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        # Group 1: Dwell Thresholds
        dwell_group = QGroupBox("⏱️ THỜI GIAN DỪNG TỐI ĐA TRƯỚC KHI BÁO ĐỘNG SA LẦY (TIME-SINK)")
        dwell_layout = QGridLayout(dwell_group)
        dwell_layout.setSpacing(12)

        thresholds = self.config.get("time_sink_thresholds", {})

        # TSA
        self.slider_tsa, self.lbl_tsa = self._create_slider_row(
            "⚡ TSA Đánh Giá Năng Lực (Tư duy phản biện):",
            thresholds.get("TSA_MODE", 120), 30, 240, 5, "giây"
        )
        dwell_layout.addWidget(self.lbl_tsa[0], 0, 0)
        dwell_layout.addWidget(self.slider_tsa, 0, 1)
        dwell_layout.addWidget(self.lbl_tsa[1], 0, 2)

        # YouPass / IELTS Reading
        self.slider_reading, self.lbl_reading = self._create_slider_row(
            "📖 YouPass & Study4 Reading (Đọc hiểu):",
            thresholds.get("YOUPASS_READING", 90), 30, 180, 5, "giây"
        )
        dwell_layout.addWidget(self.lbl_reading[0], 1, 0)
        dwell_layout.addWidget(self.slider_reading, 1, 1)
        dwell_layout.addWidget(self.lbl_reading[1], 1, 2)

        # IELTS Listening
        self.slider_listening, self.lbl_listening = self._create_slider_row(
            "🎧 IELTS Listening (Nghe):",
            thresholds.get("IELTS_LISTENING", 60), 20, 120, 5, "giây"
        )
        dwell_layout.addWidget(self.lbl_listening[0], 2, 0)
        dwell_layout.addWidget(self.slider_listening, 2, 1)
        dwell_layout.addWidget(self.lbl_listening[1], 2, 2)

        # IELTS Writing
        self.slider_writing, self.lbl_writing = self._create_slider_row(
            "✍️ IELTS Writing (Viết luận):",
            thresholds.get("IELTS_WRITING", 300), 60, 600, 10, "giây"
        )
        dwell_layout.addWidget(self.lbl_writing[0], 3, 0)
        dwell_layout.addWidget(self.slider_writing, 3, 1)
        dwell_layout.addWidget(self.lbl_writing[1], 3, 2)

        layout.addWidget(dwell_group)

        # Group 2: Pacing & Guessing Detection
        pace_group = QGroupBox("⚡ CẢNH BÁO TỐC ĐỘ TOÀN BÀI & NHẬN DIỆN ĐOÁN MÒ")
        pace_layout = QGridLayout(pace_group)
        pace_layout.setSpacing(12)

        self.slider_guess, self.lbl_guess = self._create_slider_row(
            "🎲 Ngưỡng nhận diện ĐOÁN MÒ (Chuyển câu khi dừng < X giây):",
            self.config.get("guess_threshold_sec", 12), 4, 30, 1, "giây"
        )
        pace_layout.addWidget(self.lbl_guess[0], 0, 0)
        pace_layout.addWidget(self.slider_guess, 0, 1)
        pace_layout.addWidget(self.lbl_guess[1], 0, 2)

        pacing_alerts = self.config.get("passage_pacing_alerts", {})
        self.slider_p1, self.lbl_p1 = self._create_slider_row(
            "⚠️ Báo động thời gian tối đa Passage 1 Reading:",
            int(pacing_alerts.get("passage_1_max_min", 15)), 5, 25, 1, "phút"
        )
        pace_layout.addWidget(self.lbl_p1[0], 1, 0)
        pace_layout.addWidget(self.slider_p1, 1, 1)
        pace_layout.addWidget(self.lbl_p1[1], 1, 2)

        self.slider_p2, self.lbl_p2 = self._create_slider_row(
            "⚠️ Báo động thời gian tích lũy Passage 2 Reading:",
            int(pacing_alerts.get("passage_2_cumulative_max_min", 35)), 15, 50, 1, "phút"
        )
        pace_layout.addWidget(self.lbl_p2[0], 2, 0)
        pace_layout.addWidget(self.slider_p2, 2, 1)
        pace_layout.addWidget(self.lbl_p2[1], 2, 2)

        layout.addWidget(pace_group)

        # Group 3: Chrome CDP & Low Spec
        net_group = QGroupBox("🌐 KẾT NỐI CDP TRÌNH DUYỆT & TỐI ƯU HÓA PHẦN CỨNG")
        net_layout = QGridLayout(net_group)
        net_layout.setSpacing(12)

        net_layout.addWidget(QLabel("Địa chỉ CDP Chrome / Edge:"), 0, 0)
        self.txt_cdp = QLineEdit(self.config.get("cdp_url", "http://localhost:9222"))
        net_layout.addWidget(self.txt_cdp, 0, 1)

        self.chk_low_ram = QCheckBox("Bật chế độ máy tính cấu hình yếu (Ép RAM dưới 35MB, hủy buffer ảnh ngay lập tức)")
        self.chk_low_ram.setChecked(self.config.get("low_end_pc_mode", True))
        self.chk_low_ram.setStyleSheet("font-size: 13px; font-weight: 600; color: #f8fafc;")
        net_layout.addWidget(self.chk_low_ram, 1, 0, 1, 2)

        layout.addWidget(net_group)
        layout.addStretch()

        scroll.setWidget(container)
        wrap_layout = QVBoxLayout(widget)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(scroll)
        return widget

    def _create_slider_row(
        self, label_text: str, default_val: int, min_val: int, max_val: int, step: int, unit: str
    ) -> tuple[QSlider, tuple[QLabel, QLabel]]:
        lbl_title = QLabel(label_text)
        lbl_title.setStyleSheet("font-size: 13px; color: #cbd5e1;")

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setSingleStep(step)
        slider.setValue(default_val)

        lbl_val = QLabel(f"{default_val} {unit}")
        lbl_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8; min-width: 65px;")

        slider.valueChanged.connect(lambda v: lbl_val.setText(f"{v} {unit}"))
        return slider, (lbl_title, lbl_val)

    # =========================================================================
    # TAB 3: MEMORY CARDS & AI RULES
    # =========================================================================
    def _build_memory_cards_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        desc = QLabel("🧠 BẢNG THEO DÕI SPATIAL REPETITION & GHI CHÚ FEYNMAN ĐÃ LƯU TRONG DATABASE")
        desc.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8;")
        top_row.addWidget(desc)
        top_row.addStretch()

        btn_refresh = QPushButton("🔄 Làm Mới Dữ Liệu")
        btn_refresh.setStyleSheet("background: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        btn_refresh.clicked.connect(self.reload_memory_cards)
        top_row.addWidget(btn_refresh)
        layout.addLayout(top_row)

        # Table
        self.table_cards = QTableWidget()
        self.table_cards.setColumnCount(6)
        self.table_cards.setHorizontalHeaderLabels([
            "Môn Thi", "Câu #", "Ghi Chú Feynman (Active Recall)", "Quy Tắc Phản Xạ 1 Dòng (If-Then)", "Bước Lặp", "Ngày Ôn Tập Tiếp Theo"
        ])
        header = self.table_cards.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cards.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_cards)

        self.reload_memory_cards()
        return widget

    def reload_memory_cards(self) -> None:
        """Loads memory cards from SQLite database."""
        if not self.db_manager:
            return

        due_cards = self.db_manager.get_due_cards(limit=50)
        self.table_cards.setRowCount(len(due_cards))

        for r, card in enumerate(due_cards):
            self.table_cards.setItem(r, 0, QTableWidgetItem(card.get("exam_profile", "")))
            self.table_cards.setItem(r, 1, QTableWidgetItem(str(card.get("question_number", ""))))
            self.table_cards.setItem(r, 2, QTableWidgetItem(card.get("feynman_user_note", "") or "(Chưa có note)"))
            self.table_cards.setItem(r, 3, QTableWidgetItem(card.get("if_then_trigger", "")))
            step_str = f"Bước {card.get('repetition_step', 1)}"
            self.table_cards.setItem(r, 4, QTableWidgetItem(step_str))
            self.table_cards.setItem(r, 5, QTableWidgetItem(str(card.get("next_review_date", ""))))

    # =========================================================================
    # TAB 4: HOTKEYS GUIDE
    # =========================================================================
    def _build_hotkeys_guide_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        title = QLabel("⌨️ BẢNG PHÍM TẮT TOÀN CẦU (HOẠT ĐỘNG NGAY CẢ KHI ĐANG MỞ TRÌNH DUYỆT)")
        title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38bdf8;")
        layout.addWidget(title)

        hotkey_cards = [
            ("Alt + R", "Reset Câu Hỏi Về #01 (00:00)", "Khởi động lại số câu về #01 và đặt lại đồng hồ bấm giờ về 00:00 cho bài thi mới"),
            ("Alt + Up", "Tới Câu Tiếp Theo (Q+1)", "Tăng nhanh số thứ tự câu hỏi khi đang làm bài hoặc lướt đề"),
            ("Alt + Down", "Lùi Câu Trước Đó (Q-1)", "Giảm nhanh số thứ tự câu hỏi khi quay lại rà soát"),
            ("Alt + V", "AI Vision Đọc Màn Hình (Zero CDP)", "Chụp màn hình bài thi và gửi trực tiếp cho Gemini Flash phân tích, không cần cổng CDP"),
            ("Alt + C", "Khởi Động Nhanh Chrome CDP", "Tự động mở Google Chrome với cổng gỡ lỗi 9222 sẵn sàng vào Hociz.vn"),
            ("Alt + M", "Đổi Chế Độ Thi (Cycle Profile)", "Xoay vòng qua Hociz TSA, YouPass Reading, Study4 Reading, TSA ĐGNL, Listening, Writing kèm thông báo Toast"),
            ("Alt + F", "Gắn Cờ Vi Mô (Micro-Flag)", "Đánh dấu ngay câu hỏi đang làm phân vân để ưu tiên tổng hợp sau khi thi (ghi nhận timestamp nếu ở Listening)"),
            ("Alt + S", "Đồng Bộ Tự Động (Auto-Sync CDP)", "Tự động kết nối Chrome CDP, mở rộng bài giải, cào câu sai, đẩy vào AI Gemini và mở ngăn kéo Feynman"),
            ("Alt + Z", "Đóng/Mở Ngăn Kéo (Toggle Drawer)", "Hiển thị ngăn trượt 420px bên phải để xem phân tích bẫy, mở khóa Feynman Box và làm Twin Challenge"),
            ("Alt + H", "Bật/Tắt Tàng Hình (Stealth Hide)", "Ẩn tức thời hoặc hiện lại toàn bộ giao diện overlay (Mini-Pill) chỉ trong 0.05 giây"),
        ]

        for hk, name, desc in hotkey_cards:
            row = QFrame()
            row.setStyleSheet("background: #1e293b; border-radius: 8px; padding: 10px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 6, 12, 6)

            badge = QLabel(hk)
            badge.setStyleSheet("background: #0284c7; color: white; font-weight: 900; font-size: 14px; padding: 4px 12px; border-radius: 6px; font-family: monospace;")
            badge.setFixedWidth(110)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(badge)

            detail_box = QVBoxLayout()
            d_name = QLabel(name)
            d_name.setStyleSheet("font-size: 13px; font-weight: bold; color: #f8fafc;")
            d_sub = QLabel(desc)
            d_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
            detail_box.addWidget(d_name)
            detail_box.addWidget(d_sub)
            rl.addLayout(detail_box)

            layout.addWidget(row)

        layout.addStretch()
        return widget

    # =========================================================================
    # FOOTER STRIP
    # =========================================================================
    def _build_footer_strip(self) -> QHBoxLayout:
        footer = QHBoxLayout()

        btn_hide = QPushButton("👁️ Thu Nhỏ Về Khay (Chạy Nền)")
        btn_hide.setFixedHeight(38)
        btn_hide.setStyleSheet(
            "QPushButton { background: #334155; color: #f8fafc; font-weight: bold; font-size: 12px; padding: 0 14px; border-radius: 6px; border: none; } "
            "QPushButton:hover { background: #475569; }"
        )
        btn_hide.clicked.connect(self.hide)
        footer.addWidget(btn_hide)

        btn_chrome = QPushButton("🌐 Mở Chrome CDP (Port 9222)")
        btn_chrome.setFixedHeight(38)
        btn_chrome.setStyleSheet(
            "QPushButton { background: #0f766e; color: #ccfbf1; font-weight: bold; font-size: 12px; padding: 0 14px; border-radius: 6px; border: 1px solid #14b8a6; } "
            "QPushButton:hover { background: #115e59; }"
        )
        btn_chrome.clicked.connect(self._launch_chrome_cdp)
        footer.addWidget(btn_chrome)

        btn_vision = QPushButton("📸 AI Vision Đọc Màn Hình (Zero-CDP)")
        btn_vision.setFixedHeight(38)
        btn_vision.setStyleSheet(
            "QPushButton { background: #6b21a8; color: #f3e8ff; font-weight: bold; font-size: 12px; padding: 0 14px; border-radius: 6px; border: 1px solid #a855f7; } "
            "QPushButton:hover { background: #581c87; }"
        )
        btn_vision.clicked.connect(self.request_vision_sync.emit)
        footer.addWidget(btn_vision)

        btn_reset = QPushButton("🔄 Reset Câu #01 (00:00)")
        btn_reset.setFixedHeight(38)
        btn_reset.setStyleSheet(
            "QPushButton { background: #b45309; color: #fef3c7; font-weight: bold; font-size: 12px; padding: 0 14px; border-radius: 6px; border: 1px solid #f59e0b; } "
            "QPushButton:hover { background: #92400e; }"
        )
        btn_reset.clicked.connect(self.request_reset_q1.emit)
        footer.addWidget(btn_reset)

        footer.addStretch()

        btn_save = QPushButton("💾 Lưu Cài Đặt")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet(
            "QPushButton { background: #0284c7; color: white; font-weight: bold; font-size: 13px; padding: 0 18px; border-radius: 6px; border: none; } "
            "QPushButton:hover { background: #0369a1; }"
        )
        btn_save.clicked.connect(self._save_settings)
        footer.addWidget(btn_save)

        btn_start = QPushButton("🚀 Bắt Đầu Thi (Mở Stealth HUD)")
        btn_start.setFixedHeight(38)
        btn_start.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669); "
            "color: white; font-weight: 900; font-size: 13px; padding: 0 20px; border-radius: 6px; border: none; } "
            "QPushButton:hover { background: #059669; }"
        )
        btn_start.clicked.connect(self._trigger_start_exam)
        footer.addWidget(btn_start)

        return footer

    # =========================================================================
    # ACTIONS & HANDLERS
    # =========================================================================
    def _save_settings(self) -> None:
        """Saves current controls back to config.json and emits config_saved signal."""
        selected_prof_idx = self.combo_profile.currentIndex()
        prof_keys = list(self.PROFILE_NAMES.keys())
        active_prof = prof_keys[selected_prof_idx] if selected_prof_idx < len(prof_keys) else "YOUPASS_READING"

        self.config["active_profile"] = active_prof
        self.config["cdp_url"] = self.txt_cdp.text().strip()
        self.config["guess_threshold_sec"] = self.slider_guess.value()
        self.config["low_end_pc_mode"] = self.chk_low_ram.isChecked()

        if "time_sink_thresholds" not in self.config:
            self.config["time_sink_thresholds"] = {}
        self.config["time_sink_thresholds"]["TSA_MODE"] = self.slider_tsa.value()
        self.config["time_sink_thresholds"]["YOUPASS_READING"] = self.slider_reading.value()
        self.config["time_sink_thresholds"]["STUDY4_READING"] = self.slider_reading.value()
        self.config["time_sink_thresholds"]["IELTS_LISTENING"] = self.slider_listening.value()
        self.config["time_sink_thresholds"]["IELTS_WRITING"] = self.slider_writing.value()

        if "passage_pacing_alerts" not in self.config:
            self.config["passage_pacing_alerts"] = {}
        self.config["passage_pacing_alerts"]["passage_1_max_min"] = self.slider_p1.value()
        self.config["passage_pacing_alerts"]["passage_2_cumulative_max_min"] = self.slider_p2.value()

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info("Saved configuration successfully from Central Dashboard.")
            self.config_saved.emit(self.config)
        except Exception as e:
            logger.error("Failed writing config.json: %s", e)

    def _trigger_start_exam(self) -> None:
        """Saves settings, hides Central Dashboard, and activates Stealth Mini-Pill."""
        self._save_settings()
        self.hide()
        self.start_exam_mode.emit()

    def _trigger_open_drawer(self) -> None:
        self.open_drawer_requested.emit()

    def _trigger_test_twin(self) -> None:
        dummy_card = {
            "card_id": 1,
            "exam_profile": "TSA_MODE",
            "twin_question": {
                "time_limit_sec": 60,
                "stem": "[THỬ THÁCH SINH ĐÔI] Một trường đại học phát hiện sinh viên dùng AI đạt điểm cao hơn 15%. Hiệu trưởng kết luận AI cải thiện tư duy độc lập. Điểm yếu logic lớn nhất là gì?",
                "options": {
                    "A": "Mẫu khảo sát có thể chỉ gồm các sinh viên xuất sắc sẵn.",
                    "B": "Đánh đồng tương quan điểm số với sự phát triển năng lực tư duy.",
                    "C": "Chưa đối chứng với nhóm không sử dụng thiết bị điện tử.",
                    "D": "Tỷ lệ 15% là quá nhỏ để có ý nghĩa thống kê thực tế.",
                    "correct_option": "B",
                    "short_explanation": "Bẫy ngụy biện False Cause (nhầm lẫn giữa kết quả điểm số với bản chất tư duy độc lập)."
                }
            }
        }
        self.open_twin_challenge_requested.emit(dummy_card)

    def _launch_chrome_cdp(self) -> None:
        """Emits signal to launch Google Chrome with --remote-debugging-port=9222."""
        self.request_launch_chrome.emit()

    def _on_profile_dropdown_changed(self, idx: int) -> None:
        prof_keys = list(self.PROFILE_NAMES.keys())
        if idx < len(prof_keys):
            prof = prof_keys[idx]
            self.profile_changed.emit(prof)

    def show_dashboard(self) -> None:
        """Brings the dashboard cleanly to the front."""
        self.show()
        self.raise_()
        self.activateWindow()
