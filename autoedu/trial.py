import os
import sys
import json
import uuid
import datetime
from pathlib import Path
from typing import Optional, Dict, Any

TRIAL_STORE_PATH = Path.home() / ".autoedu_trial.json"

class TrialManager:
    """
    Quản lý chế độ DÙNG THỬ 1 LẦN DUY NHẤT (1-Time Free Trial).
    Được thiết kế đặc biệt cho các AI Coding Agent miễn phí:
    - Cline / Roo Code (VS Code)
    - Google Antigravity / Gemini CLI
    - OpenCode
    - Cursor AI / Windsurf
    - Claude Code
    """
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or TRIAL_STORE_PATH

    def load_data(self) -> Dict[str, Any]:
        """Đọc dữ liệu dùng thử từ file lưu trữ cục bộ."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "device_id": str(uuid.uuid4())[:8],
            "trial_used": False,
            "trial_count": 0,
            "max_trials": 1,
            "first_used_at": None,
            "agent_name": None,
            "last_test_url": None
        }

    def save_data(self, data: Dict[str, Any]):
        """Lưu dữ liệu dùng thử ra file."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] Không thể ghi file trạng thái trial: {e}")

    def is_trial_available(self) -> bool:
        """Kiểm tra xem thiết bị còn lượt dùng thử miễn phí (tối đa 1 lần) hay không."""
        data = self.load_data()
        return data.get("trial_count", 0) < data.get("max_trials", 1)

    def record_trial(self, test_url: str, agent_name: Optional[str] = None):
        """Ghi nhận hoàn tất 1 lượt dùng thử."""
        data = self.load_data()
        data["trial_used"] = True
        data["trial_count"] = data.get("trial_count", 0) + 1
        data["first_used_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["agent_name"] = agent_name or self.detect_agent()
        data["last_test_url"] = test_url
        self.save_data(data)

    def detect_agent(self) -> str:
        """Tự động nhận diện Agent đang điều khiển môi trường."""
        env = os.environ
        if "CLINE_ACTIVE" in env or any("cline" in k.lower() for k in env):
            return "Cline (VS Code)"
        if "ANTIGRAVITY_APP_DIR" in env or "GEMINI_CLI" in env:
            return "Google Antigravity"
        if "OPENCODE" in env or "OPENCODE_CLIENT" in env:
            return "OpenCode"
        if "CURSOR_RUN" in env or "CURSOR_TRACE_ID" in env:
            return "Cursor AI"
        if "ROO_CODE" in env:
            return "Roo Code"
        if "WINDSURF_PID" in env:
            return "Windsurf Cascade"
        if "CLAUDE_CODE" in env:
            return "Claude Code"
        return "Free AI Agent"

    def print_trial_banner(self):
        """In thông tin chào mừng chế độ dùng thử."""
        agent = self.detect_agent()
        print("=" * 72)
        print("🎁 CHẾ ĐỘ DÙNG THỬ MIỄN PHÍ 1 LẦN DUY NHẤT (1-TIME FREE TRIAL 1/1)")
        print(f"🤖 Đang phát hiện môi trường: {agent}")
        print("⚡ Cho phép trải nghiệm trọn vẹn 1 bài thi mà không cần cấu hình .env trước.")
        print("=" * 72)

    def print_trial_exhausted(self):
        """In thông báo khi đã hết lượt dùng thử."""
        data = self.load_data()
        print("\n" + "=" * 72)
        print("⛔ THÔNG BÁO: BẠN ĐÃ SỬ DỤNG HẾT 1 LƯỢT DÙNG THỬ MIỄN PHÍ DUY NHẤT!")
        print(f"📅 Thời điểm đã dùng: {data.get('first_used_at', 'Trước đó')}")
        print(f"🔗 Bài thi đã trải nghiệm: {data.get('last_test_url', 'N/A')}")
        print("=" * 72)
        print("👉 Để tiếp tục sử dụng KHÔNG GIỚI HẠN VĨNH VIỄN:")
        print("   1. Đăng nhập Google Chrome vào https://gemini.google.com")
        print("   2. Lấy cookie __Secure-1PSID (xem chi tiết tại README.md)")
        print("   3. Điền vào file .env:")
        print("      GEMINI_SECURE_1PSID=...")
        print("      GEMINI_SECURE_1PSIDTS=...")
        print("   (Hoặc cấu hình GEMINI_API_KEY miễn phí từ Google AI Studio)")
        print("=" * 72 + "\n")

    def print_trial_success(self):
        """In thông báo khi hoàn thành bài thi dùng thử thành công."""
        print("\n" + "=" * 72)
        print("🎉 CHÚC MỪNG! BẠN ĐÃ HOÀN THÀNH 1 LẦN DÙNG THỬ MIỄN PHÍ XUẤT SẮC!")
        print("=" * 72)
        print("🌟 Hệ thống AutoEdu-Agent đã giải và nộp bài thành công trên Onluyen.vn.")
        print("📌 Để kích hoạt bản không giới hạn vĩnh viễn (Unlimited Runs):")
        print("   - Hãy cấu hình cookie Gemini Web trong file .env (hoàn toàn miễn phí)")
        print("   - Xem hướng dẫn chi tiết từng bước trong file README.md.")
        print("=" * 72 + "\n")
