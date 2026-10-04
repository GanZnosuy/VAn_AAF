---
name: autoedu-solver
description: Autonomous exam and homework solver for online educational platforms (Onluyen.vn, etc.) using Playwright, MathML extraction, and Gemini Web AI without API keys.
---

# AutoEdu Exam & Homework Solver Skill

Kỹ năng tự động hóa đăng nhập, quét bài tập, giải bài toán/hóa học/vật lý đa dạng và nộp bài trên các nền tảng khảo thí trực tuyến (tiêu chuẩn Onluyen.vn).

## Khi nào kích hoạt Skill này?
- Người dùng yêu cầu hoàn thành bài tập, đề kiểm tra, hoặc đề thi thử trên Onluyen.vn.
- Cần tự động giải đề Toán, Hóa, Lý cấp THPT với công thức phức tạp (MathML, MathJax, vector, hàm số, tiệm cận, este, lipid).
- Cần giải bài với mô hình Gemini Web AI chất lượng cao mà không tốn chi phí token API.

## Kiến trúc thành phần

1. **AI Engine (`autoedu.ai.gemini_web`)**:
   - Sử dụng phiên cookie web của Google (`__Secure-1PSID`, `__Secure-1PSIDTS`, v.v.).
   - Tự động bóc tách token xsrf từ `window.WIZ_global_data` (`thykhd` / `SNlM0e` / `AFWL...`).
   - Phân tích đề bài tiếng Việt với tỷ lệ chính xác cao.

2. **DOM & MathML Parser (`autoedu.extractor.mathml_parser`)**:
   - Chuyển đổi thẻ MathML (`<msup>`, `<msub>`, `<msubsup>`, `<mfrac>`, `<sqrt>`, `<mover>`) thành biểu thức toán học tường minh (`vec(AB)`, `x^2`, `(a+b)/(c-d)`).
   - Làm sạch văn bản và phân loại tự động 3 dạng bài thi:
     - Phần I: Trắc nghiệm 4 lựa chọn (A, B, C, D)
     - Phần II: Trắc nghiệm Đúng / Sai (4 mệnh đề a, b, c, d)
     - Phần III: Trả lời ngắn / Điền số

3. **Trình điều khiển trình duyệt (`autoedu.browser`)**:
   - Duy trì phiên đăng nhập Chromium tại `~/.onluyen-browser-profile`.
   - Hỗ trợ xem trực tiếp trên màn hình (`headless=False`) hoặc chạy nền (`headless=True`).

4. **Lưu bài & Nộp bài (`autoedu.solver`)**:
   - **Bắt buộc**: Bấm nút `TRẢ LỜI` sau mỗi câu để máy chủ lưu đáp án và đổi trạng thái câu thành `done`.
   - Kiểm tra xác nhận trước khi chuyển câu.
   - Bấm `Nộp Bài` -> Xác nhận modal dialog -> Chụp ảnh báo cáo điểm số.

## Cách sử dụng

### 1. Kiểm tra kết nối AI
```bash
python cli.py test-ai
```

### 2. Quét danh sách bài tập cần làm
```bash
python cli.py scan
```

### 3. Giải tự động bài thi theo URL
```bash
python cli.py solve --url "https://app.onluyen.vn/school/test/<test_id>"
```
