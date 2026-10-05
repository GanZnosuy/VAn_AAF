---
name: autoedu-solver
description: Autonomous exam and homework solver for online educational platforms (Onluyen.vn, etc.) using Playwright, MathML extraction, and Gemini Web AI without API keys.
---

# AutoEdu Exam & Homework Solver Skill

Kỹ năng tự động hóa đăng nhập, quét bài tập, giải bài toán/hóa học/vật lý đa dạng và nộp bài trên các nền tảng khảo thí trực tuyến (tiêu chuẩn Onluyen.vn).

## Khi nào kích hoạt Skill này?
- Người dùng yêu cầu hoàn thành bài tập, đề kiểm tra, hoặc đề thi thử trên Onluyen.vn.
- Cần tự động giải đề Toán, Hóa, Lý cấp THPT với công thức phức tạp (MathML, MathJax, vector, hàm số, tiệm cận, bảng biến thiên, tích phân, este, lipid).
- Cần giải bài với mô hình Gemini AI chất lượng cao mà không tốn chi phí token API.
- Hỗ trợ chạy Dùng Thử 1 Lần Duy Nhất (`1-Time Free Trial`) cho các AI Coding Agent (Cline, Antigravity, OpenCode, Cursor, Windsurf).

## Kiến trúc thành phần

1. **AI Engine (`autoedu.ai.gemini_web` & `autoedu.trial`)**:
   - Chế độ chính: Sử dụng phiên cookie web của Google (`__Secure-1PSID`, `__Secure-1PSIDTS`).
   - Chế độ Free API: Hỗ trợ Google AI Studio key miễn phí.
   - Chế độ Free Trial (1/1): Cho phép chạy thử nghiệm 1 bài thi ngay lập tức mà chưa cần cấu hình `.env`.
   - Phân tích đề bài tiếng Việt với quy trình suy luận từng bước (Chain-of-Thought) nâng cao độ chính xác.

2. **DOM & MathML Parser (`autoedu.extractor.mathml_parser`)**:
   - Chuyển đổi toàn diện thẻ MathML (`<msup>`, `<msub>`, `<msubsup>`, `<mfrac>`, `<sqrt>`, `<mroot>`, `<mover>`, `<munder>`, `<munderover>`, `<mtable>`) thành biểu thức toán học tường minh (`vec(AB)`, `x^2`, `lim_(x->+inf)`, `(a+b)/(c-d)`).
   - Tự động chuẩn hóa bảng biến thiên, hệ phương trình, ma trận và các ký hiệu toán học đặc biệt.
   - Phân loại tự động 3 dạng bài thi:
     - Phần I: Trắc nghiệm 4 lựa chọn (A, B, C, D)
     - Phần II: Trắc nghiệm Đúng / Sai (4 mệnh đề a, b, c, d)
     - Phần III: Trả lời ngắn / Điền số (tự động chuẩn hóa dấu phẩy thập phân `,`)

3. **Trình điều khiển trình duyệt (`autoedu.browser`)**:
   - Duy trì phiên đăng nhập Chromium tại `~/.onluyen-browser-profile`.
   - Hỗ trợ xem trực tiếp trên màn hình (`headless=False`) hoặc chạy nền (`headless=True`).

4. **Lưu bài & Nộp bài (`autoedu.solver`)**:
   - **Bắt buộc**: Bấm nút `TRẢ LỜI` sau mỗi câu để máy chủ lưu đáp án và kiểm tra nhãn `done` trên phiếu trước khi chuyển sang câu tiếp theo.
   - Bấm `Nộp Bài` -> Xác nhận modal dialog -> Chụp ảnh báo cáo điểm số.

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
python cli.py trial --url "https://app.onluyen.vn/school/test/<test_id>"
```

### 4. Quét danh sách bài tập cần làm
```bash
python cli.py scan
```

### 5. Giải tự động và nộp bài kiểm tra
```bash
python cli.py solve --url "https://app.onluyen.vn/school/test/<test_id>"
```
*(Thêm cờ `--headless` nếu muốn chạy ẩn)*
