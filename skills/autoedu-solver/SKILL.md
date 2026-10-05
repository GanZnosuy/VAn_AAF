---
name: autoedu-solver
description: Autonomous exam and homework solver for online educational platforms (Onluyen.vn, Azota, K12Online, Google Forms, etc.) using Playwright, MathML extraction, and Gemini AI.
---

# AutoEdu Universal Exam & Homework Solver Skill

Kỹ năng tự động hóa đăng nhập, quét bài tập, giải bài thi và nộp bài trên TẤT CẢ các nền tảng giáo dục trực tuyến phổ biến:
- **Onluyen.vn**
- **Azota.vn**
- **K12Online (Viettel)**
- **Google Forms (Docs Forms)**
- **Universal Web Solver (OLM.vn, VnEdu, Submoi, VietJack, Quizizz, Microsoft Forms...)**

## Khi nào kích hoạt Skill này?
- Người dùng yêu cầu hoàn thành bài tập, đề kiểm tra, hoặc đề thi thử trên bất kỳ trang web/app giáo dục nào.
- Cần tự động giải đề Toán, Hóa, Lý cấp THPT với công thức phức tạp (MathML, MathJax, vector, hàm số, tiệm cận, bảng biến thiên, tích phân, este, lipid).
- Cần giải bài với mô hình Gemini AI chất lượng cao mà không tốn chi phí token API.
- Hỗ trợ chạy Dùng Thử 1 Lần Duy Nhất (`1-Time Free Trial`) cho các AI Coding Agent (Cline, Antigravity, OpenCode, Cursor, Windsurf).

## Kiến trúc thành phần

1. **Bộ điều phối Đa nền tảng (`autoedu.platforms`)**:
   - `OnluyenAdapter`: Tối ưu hóa sâu cho Onluyen.vn (Angular SPA, phiếu trả lời, 3 phần thi).
   - `AzotaAdapter`: Giải đề kiểm tra trắc nghiệm trên Azota.vn.
   - `K12OnlineAdapter`: Hệ thống trường học trực tuyến K12Online.
   - `GoogleFormsAdapter`: Giải các biểu mẫu đề thi Google Forms.
   - `UniversalAdapter`: Tự động phân tích cây DOM tổng quát trên mọi trang web giáo dục khác.

2. **AI Engine (`autoedu.ai.gemini_web` & `autoedu.trial`)**:
   - Chế độ chính: Sử dụng phiên cookie web của Google (`__Secure-1PSID`, `__Secure-1PSIDTS`).
   - Chế độ Free API: Hỗ trợ Google AI Studio key miễn phí.
   - Chế độ Free Trial (1/1): Cho phép chạy thử nghiệm 1 bài thi ngay lập tức mà chưa cần cấu hình `.env`.
   - Phân tích đề bài tiếng Việt với quy trình suy luận từng bước (Chain-of-Thought) nâng cao độ chính xác.

3. **DOM & MathML Parser (`autoedu.extractor.mathml_parser`)**:
   - Chuyển đổi toàn diện thẻ MathML (`<msup>`, `<msub>`, `<msubsup>`, `<mfrac>`, `<sqrt>`, `<mroot>`, `<mover>`, `<munder>`, `<munderover>`, `<mtable>`) thành biểu thức toán học tường minh (`vec(AB)`, `x^2`, `lim_(x->+inf)`, `(a+b)/(c-d)`).
   - Tự động chuẩn hóa bảng biến thiên, hệ phương trình, ma trận và các ký hiệu toán học đặc biệt.

4. **Trình điều khiển trình duyệt (`autoedu.browser`)**:
   - Duy trì phiên đăng nhập Chromium tại `~/.onluyen-browser-profile`.
   - Hỗ trợ xem trực tiếp trên màn hình (`headless=False`) hoặc chạy nền (`headless=True`).

## Cách sử dụng

### 1. Kiểm tra trạng thái hệ thống & lượt dùng thử
```bash
python cli.py status
```

### 2. Kiểm tra kết nối AI
```bash
python cli.py test-ai
```

### 3. Dùng thử 1 lần duy nhất (Dành cho AI Agent & Người dùng mới)
```bash
python cli.py trial --url "<LINK_BAI_THI_BAT_KY>"
```

### 4. Giải tự động và nộp bài kiểm tra trên mọi nền tảng
```bash
python cli.py solve --url "https://app.onluyen.vn/school/test/<test_id>"
python cli.py solve --url "https://azota.vn/vi/test/<test_id>"
python cli.py solve --url "https://k12online.vn/bai-thi/<test_id>"
python cli.py solve --url "https://docs.google.com/forms/d/e/<form_id>/viewform"
```
*(Thêm cờ `--headless` nếu muốn chạy ẩn)*
