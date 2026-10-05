# 🎓 AutoEdu-Agent: Hệ Thống Tự Động Giải Bài Tập & Thi Trực Tuyến

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Playwright-Chromium-green?logo=playwright" alt="Playwright" />
  <img src="https://img.shields.io/badge/AI%20Engine-Gemini%20Web%20(Free)-orange?logo=google-gemini" alt="Gemini Web" />
  <img src="https://img.shields.io/badge/Free%20Trial-1--Time%20Trial%20Ready-success" alt="Free Trial" />
  <img src="https://img.shields.io/badge/License-MIT-purple" alt="License" />
</p>

**AutoEdu-Agent** là hệ thống tự động hóa giải bài tập và bài thi trực tuyến (tiêu chuẩn Onluyen.vn) kết hợp giữa **Trình duyệt tự động (Playwright / Browser-Use)** và **Trí tuệ nhân tạo (Gemini AI)** mà không phụ thuộc vào API Key trả phí.

Dự án được tối ưu hóa đặc biệt cho các **AI Coding Agent miễn phí** như **Cline**, **Google Antigravity**, **OpenCode**, **Cursor**, **Windsurf**, **Roo Code** và **Claude Code**.

---

## 🎁 Chế Độ Dùng Thử 1 Lần Duy Nhất (1-Time Free Trial)

Nhằm giúp các nhà phát triển và người dùng trải nghiệm ngay mà không phải mất thời gian cấu hình cookies:
- **Tự động kích hoạt lượt dùng thử miễn phí (1/1)** cho lần chạy đầu tiên trên mỗi thiết bị.
- Hỗ trợ chạy trực tiếp thông qua các AI Agent miễn phí:
  ```bash
  # Xem trạng thái cấu hình và hạn mức trial
  python cli.py status

  # Chạy bài thi dùng thử 1 lần duy nhất (không cần file .env)
  python cli.py trial --url "https://app.onluyen.vn/school/test/<ID_BÀI_THI>"
  ```
- Sau khi trải nghiệm xong 1 lượt dùng thử, người dùng chỉ cần thêm cookies Gemini Web vào `.env` để mở khóa **không giới hạn vĩnh viễn**.

---

## 🎯 Đột Phá Nâng Cao Độ Chính Xác (High Accuracy Engine)

1. **Quy trình Suy luận Từng bước (Chain-of-Thought)**:
   - Mô hình AI được định hướng suy luận từng bước (viết rõ công thức, tập xác định, tính toán chi tiết và loại trừ phương án sai) trước khi kết luận đáp án.
   - Giúp nâng cao tỷ lệ giải đúng các bài toán phức tạp (Hình học Oxyz, khảo sát hàm số, tiệm cận, bảng biến thiên, hóa hữu cơ).

2. **Bộ bóc tách MathML v2 & Chuẩn hóa Ký hiệu Toán học**:
   - Chuyển đổi toàn diện các cấu trúc toán học từ MathJax:
     - Vectơ: `<mover>` -> `vec(AB)`
     - Giới hạn: `<munder>` -> `lim_(x->+inf)`
     - Căn thức: `<mroot>`, `<msqrt>` -> `root(3, x)`, `sqrt(x)`
     - Bảng biến thiên, ma trận, hệ phương trình: `<mtable>`, `<mtr>`, `<mtd>` -> `[Hàng: x | y' | y]`
     - Chuẩn hóa ký hiệu: vô cực ($\infty$), tập hợp ($\in, \cup, \cap$), dấu trừ âm ($-$).

3. **Cơ chế Lưu bài & Đồng bộ Angular Chắc Chắn**:
   - Bắt buộc click nút **`TRẢ LỜI`** sau mỗi câu và tự động retry kiểm tra nhãn `done` trên phiếu trước khi qua câu mới.
   - Đảm bảo 100% dữ liệu được lưu lên máy chủ máy chấm thi.

---

## 🏗 Kiến Trúc Hệ Thống

```mermaid
flowchart TD
    subgraph Browser ["1. Browser Automation Layer"]
        B1["Playwright Chromium Persistent Profile"] --> B2["Trang bài thi (Angular SPA)"]
        B2 --> B3["Phiếu trả lời & Trắc nghiệm"]
    end

    subgraph Parser ["2. MathML & DOM Extractor v2"]
        B3 --> P1["Bóc tách MathJax / MathML"]
        P1 --> P2["Chuyển đổi: vec, lim, root, mtable, mfrac"]
        P2 --> P3["Phân loại: Trắc nghiệm / Đúng Sai / Điền số"]
    end

    subgraph AI ["3. Gemini AI Engine (CoT Reasoning)"]
        P3 --> A1["Chế độ: Cookie Web / Free API / Trial Bridge"]
        A1 --> A2["Giải mã WIZ_global_data Token (thykhd/SNlM0e)"]
        A2 --> A3["Prompt Chain-of-Thought Toán 12 THPT"]
        A3 --> A4["Suy luận & Trích xuất đáp án chuẩn xác"]
    end

    subgraph Solver ["4. Action & Persistence"]
        A4 --> S1["Click chọn phương án / Điền ô đáp án"]
        S1 --> S2["Click 'TRẢ LỜI' (Lưu dữ liệu máy chủ)"]
        S2 --> S3["Kiểm tra nhãn 'done' (Retry 2 lần nếu cần)"]
        S3 --> S4["Bấm 'Nộp Bài' & Chụp ảnh kết quả"]
    end
```

---

## 📁 Cấu Trúc Thư Mục

```
AutoEdu-Agent/
├── autoedu/                        # Gói thư viện cốt lõi
│   ├── ai/
│   │   ├── gemini_web.py           # Client kết nối Gemini (Web Cookies / Free API)
│   │   └── prompts.py              # Template prompt Chain-of-Thought độ chính xác cao
│   ├── browser/
│   │   ├── context.py              # Quản lý Chromium & profile lưu phiên
│   │   └── navigator.py            # Quét danh sách bài tập cần làm
│   ├── extractor/
│   │   └── mathml_parser.py        # Bộ chuyển đổi MathML v2 sang văn bản toán
│   ├── solver/
│   │   ├── handlers.py             # Xử lý từng dạng câu hỏi (I, II, III)
│   │   └── runner.py               # Vòng lặp giải đề & nộp bài tự động
│   ├── trial.py                    # Quản lý chế độ Dùng Thử 1 Lần Duy Nhất
│   └── config.py                   # Quản lý biến môi trường
├── skills/
│   └── autoedu-solver/
│       └── SKILL.md                # Skill chuẩn cho Antigravity / Claude Code
├── .clinerules                     # Cấu hình tối ưu cho Cline / Roo Code (VS Code)
├── opencode.json                   # Cấu hình lệnh cho OpenCode CLI
├── .cursorrules                    # Cấu hình cho Cursor AI & Windsurf
├── CLAUDE.md                       # Hướng dẫn cho Claude Code
├── cli.py                          # Giao diện dòng lệnh CLI (solve, trial, status, scan)
├── .env.example                    # File mẫu cấu hình cookies & tài khoản
├── .gitignore                      # Bảo vệ thông tin bí mật và file rác
├── requirements.txt                # Danh sách thư viện Python
├── pyproject.toml                  # Cấu hình cài đặt gói
├── LICENSE                         # Giấy phép MIT
└── README.md                       # Tài liệu hướng dẫn
```

---

## 🚀 Cài Đặt & Sử Dụng

### 1. Cài đặt môi trường
Yêu cầu Python >= 3.11:

```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt

# Cài đặt browser binary Playwright
playwright install chromium
```

### 2. Dùng thử ngay (Không cần cấu hình)
```bash
python cli.py trial --url "https://app.onluyen.vn/school/test/<ID_BÀI_THI>"
```

### 3. Mở khóa vĩnh viễn (Cấu hình Cookie Gemini Web Miễn Phí)
1. Mở Chrome truy cập [gemini.google.com](https://gemini.google.com).
2. Nhấn `F12` -> Chọn tab **Application** (Ứng dụng) -> **Cookies** -> `https://gemini.google.com`.
3. Tìm và sao chép 3 cookie:
   - `__Secure-1PSID`
   - `__Secure-1PSIDTS`
   - `__Secure-1PSIDCC`
4. Tạo file `.env` từ `.env.example` và dán vào:

```env
GEMINI_SECURE_1PSID=g.a000...
GEMINI_SECURE_1PSIDTS=sidts-...
GEMINI_SECURE_1PSIDCC=AKEy...

# (Tùy chọn) Hoặc dùng Free API Key từ Google AI Studio:
# GEMINI_API_KEY=AIzaSy...

# (Tùy chọn) Tài khoản Onluyen để tự động đăng nhập nếu hết phiên:
ONLUYEN_USERNAME=your_username
ONLUYEN_PASSWORD=your_password
```

---

## 🖥 Hướng Dẫn Sử Dụng CLI

### Xem trạng thái hệ thống & lượt dùng thử
```bash
python cli.py status
```

### Kiểm tra kết nối AI
```bash
python cli.py test-ai
```

### Quét danh sách bài tập đang giao trên Onluyen
```bash
python cli.py scan
```

### Tự động giải và nộp bài kiểm tra
```bash
# Mở cửa sổ trình duyệt trực tiếp để quan sát:
python cli.py solve --url "https://app.onluyen.vn/school/test/<ID_BÀI_THI>"

# Hoặc chạy ngầm (Headless):
python cli.py solve --url "https://app.onluyen.vn/school/test/<ID_BÀI_THI>" --headless
```

---

## 🤖 Tích Hợp Vào Các AI Coding Agent

Dự án cung cấp sẵn cấu hình cho mọi nền tảng Agent phổ biến:
- **Cline & Roo Code**: Đã có sẵn [`.clinerules`](.clinerules). Bạn chỉ cần mở VS Code và ra lệnh cho Cline: `"Hãy quét bài tập trên Onluyen và làm giúp tôi"`.
- **OpenCode**: Đã có sẵn [`opencode.json`](opencode.json). Hỗ trợ trực tiếp các lệnh `status`, `scan`, `trial`, `solve`.
- **Google Antigravity / Claude Code**: Đã có sẵn [`skills/autoedu-solver/SKILL.md`](skills/autoedu-solver/SKILL.md) và [`CLAUDE.md`](CLAUDE.md).
- **Cursor & Windsurf**: Đã có sẵn [`.cursorrules`](.cursorrules).

---

## 📜 Giấy Phép & Tuyên Bố Miễn Trừ Trách Nhiệm

- Dự án phát hành theo giấy phép [MIT License](LICENSE).
- Công cụ được phát triển phục vụ mục đích nghiên cứu công nghệ tự động hóa kiểm thử web (E2E Web Automation) và ứng dụng LLM trong hỗ trợ học tập. Người dùng tự chịu trách nhiệm khi sử dụng công cụ trên các nền tảng thực tế.
