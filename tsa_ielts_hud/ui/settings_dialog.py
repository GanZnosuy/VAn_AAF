"""Settings & Profile Configuration Dialog for TSA & IELTS Cognitive Training HUD."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Dialog for configuring active profile, dwell thresholds,
    sensor sampling rate, CDP URL, and low-spec RAM mode.
    """

    config_saved = pyqtSignal(dict)

    def __init__(
        self,
        config_path: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
        self.config_path = config_path
        self.config_data = self._load_config()

        self._init_window()
        self._init_ui()

    def _load_config(self) -> Dict[str, Any]:
        """Loads configuration from JSON file or returns defaults."""
        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not read config.json: %s", e)

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
            "hotkeys": {
                "mode_switch": "Alt+M",
                "micro_flag": "Alt+F",
                "submit_scrape": "Alt+S",
                "toggle_drawer": "Alt+Z",
                "stealth_hide": "Alt+H",
            },
            "low_end_pc_mode": True,
        }

    def _init_window(self) -> None:
        """Window configuration."""
        self.setWindowTitle("Cấu Hình Hệ Thống HUD - TSA & IELTS")
        self.setFixedSize(520, 560)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0b1120;
                color: #f1f5f9;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 12px;
            }
            QGroupBox {
                border: 1.5px solid #1e293b;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #38bdf8;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QComboBox, QLineEdit {
                background: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0284c7;
                border: 1px solid #38bdf8;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QCheckBox {
                color: #f1f5f9;
                font-size: 12px;
            }
            """
        )

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Title
        title = QLabel("⚙️ CẤU HÌNH THÔNG SỐ HUẤN LUYỆN COGNITIVE HUD")
        title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8;")
        layout.addWidget(title)

        # 1. Profile Selection
        group_profile = QGroupBox("Chế Độ Thi Đấu / Nền Tảng Đích")
        gp_layout = QGridLayout(group_profile)
        gp_layout.addWidget(QLabel("Profile Đang Kích Hoạt:"), 0, 0)

        self.combo_profile = QComboBox()
        self.combo_profile.addItems([
            "HOCIZ_TSA",
            "YOUPASS_READING",
            "STUDY4_READING",
            "TSA_MODE",
            "IELTS_LISTENING",
            "IELTS_WRITING",
        ])
        current_prof = self.config_data.get("active_profile", "YOUPASS_READING")
        idx = self.combo_profile.findText(current_prof)
        if idx >= 0:
            self.combo_profile.setCurrentIndex(idx)
        gp_layout.addWidget(self.combo_profile, 0, 1)

        gp_layout.addWidget(QLabel("CDP Browser Endpoint:"), 1, 0)
        self.txt_cdp = QLineEdit(self.config_data.get("cdp_url", "http://localhost:9222"))
        gp_layout.addWidget(self.txt_cdp, 1, 1)
        layout.addWidget(group_profile)

        # 2. Time Thresholds
        group_thresholds = QGroupBox("Ngưỡng Báo Động Sa Lầy (Time-Sink Alert)")
        gt_layout = QGridLayout(group_thresholds)

        # TSA limit
        tsa_val = int(self.config_data.get("time_sink_thresholds", {}).get("TSA_MODE", 120))
        gt_layout.addWidget(QLabel("Giới hạn TSA (giây):"), 0, 0)
        self.lbl_tsa_val = QLabel(f"{tsa_val}s")
        self.slider_tsa = QSlider(Qt.Orientation.Horizontal)
        self.slider_tsa.setRange(45, 240)
        self.slider_tsa.setValue(tsa_val)
        self.slider_tsa.valueChanged.connect(lambda v: self.lbl_tsa_val.setText(f"{v}s"))
        gt_layout.addWidget(self.slider_tsa, 0, 1)
        gt_layout.addWidget(self.lbl_tsa_val, 0, 2)

        # IELTS limit
        ielts_val = int(self.config_data.get("time_sink_thresholds", {}).get("YOUPASS_READING", 90))
        gt_layout.addWidget(QLabel("Giới hạn IELTS Reading (giây):"), 1, 0)
        self.lbl_ielts_val = QLabel(f"{ielts_val}s")
        self.slider_ielts = QSlider(Qt.Orientation.Horizontal)
        self.slider_ielts.setRange(30, 180)
        self.slider_ielts.setValue(ielts_val)
        self.slider_ielts.valueChanged.connect(lambda v: self.lbl_ielts_val.setText(f"{v}s"))
        gt_layout.addWidget(self.slider_ielts, 1, 1)
        gt_layout.addWidget(self.lbl_ielts_val, 1, 2)

        # Guess limit
        guess_val = int(self.config_data.get("guess_threshold_sec", 12))
        gt_layout.addWidget(QLabel("Ngưỡng Đoán Nhanh (giây):"), 2, 0)
        self.lbl_guess_val = QLabel(f"{guess_val}s")
        self.slider_guess = QSlider(Qt.Orientation.Horizontal)
        self.slider_guess.setRange(3, 30)
        self.slider_guess.setValue(guess_val)
        self.slider_guess.valueChanged.connect(lambda v: self.lbl_guess_val.setText(f"{v}s"))
        gt_layout.addWidget(self.slider_guess, 2, 1)
        gt_layout.addWidget(self.lbl_guess_val, 2, 2)
        layout.addWidget(group_thresholds)

        # 3. Hardware & RAM Toggles
        group_hw = QGroupBox("Tối Ưu Hoá Tài Nguyên Phần Cứng")
        gh_layout = QVBoxLayout(group_hw)

        self.chk_low_ram = QCheckBox("Chế độ Máy Cấu Hình Thấp (RAM < 45MB, hủy bộ đệm ảnh tức thì)")
        self.chk_low_ram.setChecked(bool(self.config_data.get("low_end_pc_mode", True)))
        gh_layout.addWidget(self.chk_low_ram)

        hotkey_info = QLabel("⌨️ Phím Tắt: Alt+M (Đổi Profile) | Alt+F (Gắn Cờ) | Alt+S (Đồng Bộ) | Alt+Z (Mở Ngăn Kéo) | Alt+H (Ẩn)")
        hotkey_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        gh_layout.addWidget(hotkey_info)
        layout.addWidget(group_hw)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Huỷ Bỏ")
        btn_cancel.setFixedSize(100, 34)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #1e293b; color: #94a3b8; border-radius: 6px; font-weight: bold; border: 1px solid #334155; } "
            "QPushButton:hover { background: #334155; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Lưu Cấu Hình")
        btn_save.setFixedSize(130, 34)
        btn_save.setStyleSheet(
            "QPushButton { background: #0284c7; color: white; border-radius: 6px; font-weight: bold; border: none; } "
            "QPushButton:hover { background: #0369a1; }"
        )
        btn_save.clicked.connect(self._save_and_close)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _save_and_close(self) -> None:
        """Saves values to config.json and closes."""
        self.config_data["active_profile"] = self.combo_profile.currentText()
        self.config_data["cdp_url"] = self.txt_cdp.text().strip()
        self.config_data["guess_threshold_sec"] = self.slider_guess.value()
        self.config_data["low_end_pc_mode"] = self.chk_low_ram.isChecked()

        if "time_sink_thresholds" not in self.config_data:
            self.config_data["time_sink_thresholds"] = {}
        self.config_data["time_sink_thresholds"]["TSA_MODE"] = self.slider_tsa.value()
        self.config_data["time_sink_thresholds"]["YOUPASS_READING"] = self.slider_ielts.value()
        self.config_data["time_sink_thresholds"]["STUDY4_READING"] = self.slider_ielts.value()

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.info("Saved configuration to %s", self.config_path)
            self.config_saved.emit(self.config_data)
        except Exception as e:
            logger.error("Failed writing config.json: %s", e)

        self.accept()
