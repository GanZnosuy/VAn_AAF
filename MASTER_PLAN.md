# TÀI LIỆU ĐẶC TẢ KỸ THUẬT TOÀN DIỆN: ỨNG DỤNG HUD OVERLAY AI PHÂN TÍCH & TỰ HỌC TSA (100% LOCAL)

## MỤC LỤC
1. [Mục tiêu Cốt lõi & Triết lý Thiết kế](#1-mục-tiêu-cốt-lõi--triết-lý-thiết-kế)
2. [Tại sao dùng PyQt6 Native Overlay thay vì Overwolf SDK gốc?](#2-tại-sao-dùng-pyqt6-native-overlay-thay-vì-overwolf-sdk-gốc)
3. [Kiến trúc 4 Tầng & Cấu trúc Thư mục Local](#3-kiến-trúc-4-tầng--cấu-trúc-thư-mục-local)
4. [Cơ chế hoạt động của gemini-webapi: Tự lấy Cookie, Giữ phiên & Chống chặn](#4-cơ-chế-hoạt-động-của-gemini-webapi-tự-lấy-cookie-giữ-phiên--chống-chặn)
5. [Cơ chế Chụp màn hình ngầm (mss), Tàng hình HUD & Lọc Frame trùng](#5-cơ-chế-chụp-màn-hình-ngầm-mss-tàng-hình-hud--lọc-frame-trùng)
6. [Thuật toán Nhận diện Hành vi: Làm lâu, Khoanh bừa, Làm sai & Đánh giá Tiến bộ](#6-thuật-toán-nhận-diện-hành-vi-làm-lâu-khoanh-bừa-làm-sai--đánh-giá-tiến-bộ)
7. [Cơ chế Tự động Truy cập & Cào Đáp án sau khi Nộp bài (Playwright CDP)](#7-cơ-chế-tự-động-truy-cập--cào-đáp-án-sau-khi-nộp-bài-playwright-cdp)
8. [Vòng lặp Kép: AI Tự học khi Giải sai (Reflexion RAG) & Nhét kiến thức vào Não người](#8-vòng-lặp-kép-ai-tự-học-khi-giải-sai-reflexion-rag--nhét-kiến-thức-vào-não-người)
9. [Thiết kế Giao diện 3 Chế độ HUD Overlay & Bảng Cài đặt (Settings cho PC yếu)](#9-thiết-kế-giao-diện-3-chế-độ-hud-overlay--bảng-cài-đặt-settings-cho-pc-yếu)
10. [Thiết kế Cơ sở dữ liệu SQLite (tsa_local.db) — Đầy đủ 4 Bảng](#10-thiết-kế-cơ-sở-dữ-liệu-sqlite-tsa_localdb--đầy-đủ-4-bảng)
11. [Toàn bộ Code Mẫu Cốt lõi & Cấu trúc JSON Prompt](#11-toàn-bộ-code-mẫu-cốt-lõi--cấu-trúc-json-prompt)
12. [Lộ trình Xây dựng 4 Giai đoạn Thực chiến](#12-lộ-trình-xây-dựng-4-giai-đoạn-thực-chiến)

---

## 1. MỤC TIÊU CỐT LÕI & TRIẾT LÝ THIẾT KẾ

Một bài thi TSA (Đánh giá tư duy) tiêu chuẩn kéo dài 150 phút gồm 3 phần: **Tư duy Toán học (60 phút)**, **Tư duy Đọc hiểu (30 phút)** và **Tư duy Khoa học / Giải quyết vấn đề (60 phút)**.

* **Vấn đề nếu stream video thô**: Nếu quay video 60 FPS suốt 150 phút rồi gửi cho AI, dung lượng file sẽ cực lớn, tốn tài nguyên RAM/CPU của máy yếu và bị giới hạn upload của Web API.
* **Giải pháp cốt lõi (Smart Frame Sampling - Chụp và lọc khung hình theo sự kiện)**:
  * Máy Local tự đo đếm thời gian chính xác 100% bằng Python, lọc bỏ toàn bộ thời gian màn hình đứng yên (lúc đang đọc đề hoặc tính nháp trên giấy).
  * Chỉ chụp lại khung hình khi phát hiện chuyển câu hỏi hoặc thay đổi đáp án, đóng dấu thời gian trực tiếp lên ảnh, ghép 4 câu hỏi vào 1 ảnh lưới (Grid 2x2) và gửi ngầm (Micro-batching) qua `gemini-webapi` (`gemini-3.8-flash`).
  * Khi vừa bấm nộp bài, 90% dữ liệu trong lúc thi đã được xử lý xong. App lập tức điều khiển trình duyệt tự cào đáp án chuẩn, đối chiếu câu sai, ép AI tự rút kinh nghiệm nếu AI giải sai, đồng thời tạo công cụ "nhét kiến thức vào não" ngay trên màn hình Overlay.

---

## 2. TẠI SAO DÙNG PYQT6 NATIVE OVERLAY THAY VÌ OVERWOLF SDK GỐC?

Bạn muốn trải nghiệm giống Overwolf (nổi đè lên màn hình như MetaTFT/Porofessor, bấm chuột xuyên qua vùng trống, bật/tắt bằng phím nóng `Alt + Z` không cần `Alt + Tab`). Tuy nhiên, về mặt kỹ thuật, ta lấy trọn vẹn thiết kế UX/UI của Overwolf nhưng dựng bằng PyQt6 Native của Windows vì các lý do sau:

| Tiêu chí so sánh | Dùng Overwolf SDK Gốc | Tự làm Native Overlay bằng PyQt6 + QSS (Phương án chốt) |
| :--- | :--- | :--- |
| **Hoạt động trên Trình duyệt / PDF** | Bị hạn chế. Overwolf thiết kế để inject DLL vào DirectX/Vulkan của các tựa game nằm trong `GameList.xml`. Nó không tự hook vào `chrome.exe` hay `msedge.exe` khi làm đề web. | **Hoạt động mọi nơi.** Nổi đè lên bất kỳ cửa sổ nào (Chrome, Edge, PDF, phần mềm thi độc lập) nhờ cờ Always-on-top của hệ điều hành Windows. |
| **Thủ tục & Quyền hạn hệ thống** | Phải đăng ký Developer Whitelist với Overwolf để mở khóa gói `.opk`, bị nhốt trong Chromium Sandbox nên rất khó gọi trực tiếp Python `gemini-webapi` và Playwright. | **100% tự do trên máy bạn.** Chạy chung 1 tiến trình Python duy nhất với `gemini-webapi`, `mss`, `playwright` và `sqlite3` với độ trễ 0ms. |
| **Mức tiêu thụ RAM (PC yếu)** | Nặng (~350MB – 500MB RAM do phải chạy nền dịch vụ Overwolf). | **Siêu nhẹ (~30MB – 50MB RAM)**, không làm giật lag trình duyệt lúc đang thi. |
| **Click xuyên thấu (Click-Through)** | Có sẵn trong game. | Bật bằng 1 dòng lệnh Windows API / Qt (`Qt.WindowType.WindowTransparentForInput`). |
| **Tàng hình khi chụp màn hình** | Chỉ hỗ trợ trong tiến trình game. | Dùng hàm Windows API `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)`: mắt bạn vẫn nhìn thấy thanh HUD nổi trên đề thi, nhưng khi `mss` chụp màn hình gửi cho AI thì thanh HUD hoàn toàn vô hình, không bao giờ che mất chữ của đề bài! |

---

## 3. KIẾN TRÚC 4 TẦNG & CẤU TRÚC THƯ MỤC LOCAL

### 3.1. Sơ đồ Kiến trúc 4 Tầng (4-Layer Local Architecture)

```plaintext
+-------------------------------------------------------------------------+
|                        TẦNG 1: OVERLAY HUD LAYER                        |
| - PyQt6 + QSS Frameless Window (Always-on-top, Click-through)           |
| - WDA_EXCLUDEFROMCAPTURE (Tàng hình trước ống kính chụp màn hình MSS)   |
| - Stealth Mini-Pill (Đếm giây từng câu, cảnh báo Time-sink >120s/>90s)  |
| - Slide-out Drawer (Bảng thống kê, Sổ tay nhét não, Settings PC yếu)    |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                      TẦNG 2: SENSOR & SCRAPER LAYER                     |
| - MSS Screen Capture (Quét ngầm 0.5 FPS - 0.33 FPS ở tầng OS)           |
| - ImageHash / Diffing (Lọc frame đứng yên, cộng dồn duration từng câu)  |
| - Pillow Stamped Grid (Đóng dấu header thời gian & ghép 4 ảnh -> 2x2)   |
| - Playwright CDP (Nối cổng 9222 tự cào câu sai & chụp ảnh lời giải)     |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                     TẦNG 3: GEMINI FLASH AI WORKER                      |
| - gemini-webapi + browser-cookie3 (Tự lấy Cookie, auto_refresh=True)    |
| - Asyncio Rate-Limit Queue (Giãn cách 15-20s/batch, tự xóa chat rác)    |
| - Reflexion Loop (AI giải thử -> Đối chiếu -> Tự rút quy tắc nếu sai)   |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                       TẦNG 4: LOCAL SQLITE STORAGE                      |
| - tsa_local.db (4 bảng: sessions, question_logs, ai_rules, flashcards)  |
| - ./data/sessions/ (Lưu trữ ảnh .webp nén nhẹ 40-70KB/ảnh)              |
+-------------------------------------------------------------------------+
```

### 3.2. Cấu trúc Thư mục Lưu trữ trên Máy tính

```plaintext
tsa-ai-overlay/
├── .env                     # Lưu cấu hình dự phòng (GEMINI_MODEL="gemini-3.8-flash", PSID nếu cần)
├── requirements.txt         # PyQt6, mss, Pillow, imagehash, playwright, gemini-webapi[browser], keyboard
├── main.py                  # Điểm khởi chạy ứng dụng, khởi tạo luồng UI + Sensor + AI Queue
├── config.py                # Quản lý đọc/ghi file settings.json (ngưỡng giây, FPS, phím tắt, Low-End mode)
├── database.py              # Khởi tạo và truy vấn SQLite (tsa_local.db)
├── capture_sensor.py        # Module MSS chụp màn hình, ImageHash lọc trùng, Pillow đóng dấu & ghép Grid 2x2
├── playwright_scraper.py    # Module kết nối Chrome/Edge qua CDP (port 9222) cào đáp án & chụp lời giải
├── ai_worker.py             # Module gemini-webapi, tự lấy cookie, hàng đợi Queue, vòng lặp Reflexion tự học
├── ui_overlay.py            # Giao diện PyQt6 + QSS: Mini-Pill, Slide-out Drawer, Settings, Flashcard
└── data/
    ├── settings.json        # Lưu cấu hình người dùng tùy chỉnh trên UI
    ├── tsa_local.db         # File SQLite duy nhất chứa toàn bộ dữ liệu
    └── sessions/            # Thư mục lưu ảnh chụp màn hình theo từng đề
        └── 2026_10_26_de_01/
            ├── raw_frames/  # Ảnh từng câu đã nén .webp (40-70KB/ảnh)
            ├── grids/       # Ảnh ghép 2x2 đã đóng dấu thời gian để gửi AI
            └── solutions/   # Ảnh lời giải chuẩn do Playwright tự chụp sau khi nộp bài
```

---

## 4. CƠ CHẾ HOẠT ĐỘNG CỦA gemini-webapi: TỰ LẤY COOKIE, GIỮ PHIÊN & CHỐNG CHẶN

Thư viện `gemini-webapi` (repo `HanaokaYuzu/Gemini-API`) hoạt động bằng cách giả lập các request của trình duyệt web tới `gemini.google.com` thông qua 2 mã cookie xác thực là `__Secure-1PSID` và `__Secure-1PSIDTS`. Để hệ thống chạy hoàn toàn tự động suốt 150 phút làm bài mà không gặp lỗi, ứng dụng xử lý qua 4 cơ chế:

### 4.1. Cơ chế 1: Tự động lấy Cookie từ Trình duyệt (Zero Copy-Paste)
* Khi cài đặt gói `pip install "gemini-webapi[browser]"`, thư viện tích hợp sẵn `browser-cookie3`.
* Lúc khởi động app, nếu bạn không điền thủ công cookie vào file `.env`, `GeminiClient()` sẽ tự động tìm kiếm trong cơ sở dữ liệu Cookie của trình duyệt Chrome/Edge/Brave trên máy tính của bạn (nơi bạn đã đăng nhập sẵn tài khoản Google) để trích xuất `__Secure-1PSID` và `__Secure-1PSIDTS`.
* **Cơ chế dự phòng (Fallback):** Trong bảng Settings của App vẫn có 2 ô trống cho phép dán thủ công `__Secure-1PSID` và `__Secure-1PSIDTS` trong trường hợp Chrome khóa quyền đọc file cookie khi đang mở.

### 4.2. Cơ chế 2: Tự động xoay vòng Cookie ngầm (`auto_refresh=True`)
* Cookie `__Secure-1PSIDTS` của Google Web thường hết hạn sau mỗi 15–20 phút nếu không được làm mới. Trong khi đó, một đề TSA kéo dài tới 150 phút.
* Ngay khi mở app, hàm `await client.init(timeout=60, auto_close=False, auto_refresh=True)` được kích hoạt. Thư viện sẽ chạy một tác vụ ngầm (background task) định kỳ gửi tín hiệu làm mới phiên đăng nhập với máy chủ Google và tự cập nhật mã `__Secure-1PSIDTS` mới trong bộ nhớ RAM, đảm bảo không bao giờ bị văng phiên giữa giờ thi.

### 4.3. Cơ chế 3: Chống Rate-Limit & Captcha bằng kỹ thuật "Ghép Ảnh Đóng Dấu" (Stamped Grid 2x2)
* **Rủi ro:** Nếu bạn gửi lẻ tẻ 80–100 ảnh chụp màn hình lên `gemini-webapi`, Google Web sẽ lập tức chặn tính năng upload file hoặc bắt giải Captcha.
* **Giải pháp tại Local:**
  1. Mỗi khi bạn chuyển câu hỏi, Python chốt ảnh chụp câu vừa làm (trong đó có hình ảnh đáp án bạn vừa tô chọn) và biết chính xác bạn đã dừng ở câu đó bao nhiêu giây (ví dụ: 148 giây).
  2. Thư viện Pillow vẽ một dải băng màu đen ở mép trên cùng của bức ảnh và in chữ màu xanh sáng trực tiếp lên ảnh:  
     `Ô #1 | Lúc: Phút 34:10 | THỜI GIAN DỪNG: 148 GIÂY | Đổi đáp án: 2 lần`
  3. Khi gom đủ 4 câu hỏi, Pillow ghép 4 bức ảnh (mỗi ảnh 960x540) thành 1 bức ảnh lưới 2x2 duy nhất (1920x1080, định dạng `.webp`, dung lượng chỉ ~150KB).
  4. Đẩy ảnh Grid này vào hàng đợi `asyncio.Queue`. Worker của `gemini-webapi` sẽ lấy từng ảnh Grid ra gửi cách nhau 15–20 giây/lần. Nhờ vậy, cả bài thi 100 câu chỉ tốn khoảng 20–25 lần gửi ảnh, tuyệt đối an toàn trước bộ lọc chống spam của Google, đồng thời AI nhìn vào 1 ảnh là đọc được chính xác số giây của từng câu mà không bao giờ bị lệch thứ tự.

### 4.4. Cơ chế 4: Ép khuôn JSON & Tự động dọn rác Lịch sử Chat (`delete_chat`)
* **Ép khuôn JSON:** Vì `gemini-webapi` trả về văn bản Markdown tự do (`response.text`) chứ không có tham số `response_schema` cứng như API trả phí, hệ thống sử dụng Prompt ép AI chỉ trả về khối ` ```json ... ``` `, sau đó dùng biểu thức chính quy (Regex) bóc tách chuỗi JSON. Nếu `json.loads()` báo lỗi cú pháp, hệ thống tự động gửi 1 tin nhắn nhắc sửa lỗi ngay trong cùng `ChatSession` đó.
* **Dọn sạch lịch sử Web:** Mỗi lần phân tích 1 lô ảnh Grid, app tạo một phiên chat mới (`chat = client.start_chat(model="gemini-3.8-flash")`). Ngay sau khi bóc tách xong JSON và lưu vào SQLite, khối `finally:` sẽ gọi lệnh `await client.delete_chat(chat.cid)` để xóa ngay đoạn hội thoại đó, giữ cho trang chủ `gemini.google.com` của bạn hoàn toàn sạch sẽ, không bị ngập hàng chục cuộc trò chuyện rác.

---

## 5. CƠ CHẾ CHỤP MÀN HÌNH NGẦM (mss), TÀNG HÌNH HUD & LỌC FRAME TRÙNG

* **Chụp màn hình cấp độ Hệ điều hành (`mss`):**
  * Không dùng trình duyệt để quay màn hình (vì sẽ hiện thanh thông báo *"Bạn đang chia sẻ màn hình"* vướng mắt).
  * Dùng thư viện `mss` của Python đọc trực tiếp bộ nhớ đệm khung hình của hệ điều hành Windows trong 5ms, hoàn toàn vô hình.

* **Cơ chế Tàng hình HUD trước ống kính (`WDA_EXCLUDEFROMCAPTURE`):**
  * Cửa sổ Overlay PyQt6 khi khởi tạo sẽ lấy mã định danh cửa sổ (`hwnd = int(self.winId())`) và gọi hàm Windows:
    `ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)` (`WDA_EXCLUDEFROMCAPTURE`).
  * **Kết quả:** Mắt bạn nhìn màn hình vẫn thấy thanh HUD đếm giờ và bảng thống kê nổi đè lên đề thi, nhưng ảnh chụp ra bởi `mss` chỉ chứa 100% trang web đề thi sạch sẽ bên dưới, không hề dính giao diện của chính ứng dụng.

* **Thuật toán Lọc Frame trùng (`ImageHash` + Vùng ROI):**
  * Cứ mỗi 2 giây (0.5 FPS - có thể chỉnh trong Settings), Python chụp màn hình và tính mã băm hình ảnh (`dhash` hoặc `phash` qua thư viện `imagehash`).
  * **Trường hợp 1 (Khoảng cách Hamming `hash_diff <= 2`):** Màn hình không đổi (bạn đang suy nghĩ hoặc tính nháp trên giấy). Hệ thống không lưu ảnh mới, chỉ cộng thêm +2 giây vào biến `current_question_duration` và cập nhật bộ đếm lên thanh Mini-Pill HUD.
  * **Trường hợp 2 (Khoảng cách Hamming `hash_diff > 2` nhưng cấu trúc câu hỏi giữ nguyên, chỉ thay đổi vùng nút radio A/B/C/D):** Bạn vừa chọn hoặc đổi đáp án. Hệ thống ghi đè bức ảnh `latest_frame` của câu hiện tại (để luôn giữ bức ảnh có chứa đáp án cuối cùng bạn chọn) và tăng biến `answer_switch_count += 1`.
  * **Trường hợp 3 (Khoảng cách Hamming `hash_diff > 10`):** Bạn vừa chuyển sang câu hỏi mới hoặc cuộn sang bài đọc mới. Hệ thống lập tức chốt `latest_frame` cùng tổng thời gian `current_question_duration` của câu vừa rồi, đóng dấu thời gian và đẩy vào bộ đệm ghép Grid 2x2; đồng thời reset bộ đếm thời gian trên thanh Mini-Pill về 00:00 cho câu mới.

---

## 6. THUẬT TOÁN NHẬN DIỆN HÀNH VI: LÀM LÂU, KHOANH BỪA, LÀM SAI & ĐÁNH GIÁ TIẾN BỘ

Sự kết hợp giữa Số liệu thời gian đo tại Local và Khả năng đọc hiểu hình ảnh của Gemini 3.8 Flash sẽ phân loại từng câu hỏi theo bảng quy tắc sau:

| Tiêu chí | Dữ liệu đầu vào AI & Local trích xuất | Logic & Ngưỡng phân loại chi tiết (Heuristics) |
| :--- | :--- | :--- |
| **1. Câu làm lâu (Time-sink)** | • Số thứ tự câu hỏi (`question_number`)<br/>• Phần thi (Toán / Đọc hiểu / Khoa học)<br/>• Tổng thời gian dừng (`time_spent_seconds`) cộng dồn qua tất cả các lần ghé thăm (`visit_count`). | • Nếu bạn làm Câu 14 mất 70s, bỏ qua, cuối giờ quay lại làm thêm 65s $\rightarrow$ Hệ thống tự động cộng dồn theo `question_number`: `total_time = 135s`, `visit_count = 2`.<br/>• Gắn nhãn `time_sink` khi tổng thời gian vượt ngưỡng cài đặt trong Settings (Mặc định: **Toán $\ge$ 120 giây**, **Đọc hiểu / Khoa học $\ge$ 90 giây**). |
| **2. Khoanh bừa (Guessing)** | • Độ dài đề bài & độ phức tạp công thức Toán/Khoa học trên ảnh.<br/>• Tổng thời gian dừng (`time_spent_seconds`).<br/>• Số lần đổi đáp án (`answer_switch_count`).<br/>• Đồng hồ đếm ngược góc màn hình thi. | Xếp vào nhóm `guessed` (Khoanh bừa) khi rơi vào 1 trong 3 kịch bản:<br/>1. **Fast-click (Khoanh vội):** Đề bài có độ phức tạp trung bình/cao (nhiều chữ, bảng số liệu hoặc công thức) nhưng tổng thời gian nhìn đề **dưới 12 giây** đã chọn đáp án và chuyển câu.<br/>2. **Panic-click (Chạy loạn cuối giờ):** Chọn đáp án liên hoàn từ 3 câu trở lên khi đồng hồ đếm ngược còn **dưới 2 phút cuối giờ**.<br/>3. **Random-switch (Phân vân đánh lụi):** Đổi đáp án liên tục giữa các phương án (`switch_count >= 3`) trong vài giây ngắn ngủi rồi bỏ đi, hoặc người dùng chủ động bấm phím tắt `Alt + F` lúc đang làm. |
| **3. Câu làm sai (Error Analysis)** | • Đáp án bạn chọn ở frame cuối cùng (`user_answer`) đối chiếu với Đáp án chuẩn (`correct_answer`) do Playwright cào từ mục Đáp án sau khi nộp bài. | Phân tách rõ 2 loại câu sai nguy hiểm nhất:<br/>• **Sai + Time-sink:** Mất trên 2 phút tính toán nhưng vẫn ra đáp án bẫy (lỗ kép cả điểm lẫn thời gian).<br/>• **Đúng nhưng Khoanh bừa (Lucky Guess):** Dù web chấm Đúng nhưng `status_flag == 'guessed'` $\rightarrow$ Hệ thống vẫn liệt vào danh sách bắt buộc phải học lại, không cho phép ngộ nhận là đã biết làm. |
| **4. Đánh giá tiến bộ (Progress Tracking)** | • Nhãn chuyên đề chi tiết (`topic_tag`) của từng câu qua tất cả các đề lưu trong SQLite. | Tính toán và vẽ 4 chỉ số tiến bộ dài hạn:<br/>1. **Tốc độ xử lý trung bình (Pacing):** Số giây/câu của từng phần Toán, Đọc, Khoa qua từng đề.<br/>2. **Tỷ lệ Cắt lỗ & Chuyển hóa:** Sự sụt giảm số câu Khoanh bừa và số phút lãng phí vào các câu Làm lâu nhưng Sai.<br/>3. **Độ bền tâm lý (Stamina Index):** So sánh tỷ lệ làm đúng ở 30 phút đầu so với 30 phút cuối của ca thi 150 phút.<br/>4. **Bản đồ nhiệt Chuyên đề yếu (Topic Weakness Heatmap):** Top 5 chuyên đề có tỷ lệ (Sai + Làm lâu + Khoanh bừa) cao nhất để ưu tiên ôn tập. |

---

## 7. CƠ CHẾ TỰ ĐỘNG TRUY CẬP & CÀO ĐÁP ÁN SAU KHI NỘP BÀI (PLAYWRIGHT CDP)

Thay vì bắt bạn phải tự chấm tay hay mở trình duyệt ẩn danh mới (phải đăng nhập lại web luyện thi), ứng dụng kết nối trực tiếp vào trình duyệt bạn đang làm bài thông qua giao thức Chrome DevTools Protocol (CDP):

1. **Khởi tạo kết nối CDP không xâm lấn:**  
   Trên bảng điều khiển có nút *"Mở Trình Duyệt Thi (CDP Mode)"* (chạy lệnh mở Chrome/Edge của máy bạn với tham số `--remote-debugging-port=9222` giữ nguyên toàn bộ tài khoản đã đăng nhập).
2. **Tự động điều hướng mục Đáp án khi bấm `Alt + S`:**  
   * Ngay khi bạn nộp bài trên web và bấm `Alt + S`, module `playwright_scraper.py` kết nối vào `http://localhost:9222`.
   * Script tự động tìm nút *"Xem đáp án"* / *"Xem lời giải chi tiết"* trên trang web kết quả và click mở ra (nếu đang bị đóng).
3. **Thu thập Kép (DOM Parsing + Element Screenshot):**  
   * Quét danh sách câu hỏi trên trang kết quả để lấy: Câu số mấy, Đáp án bạn chọn, Đáp án đúng chuẩn của đề, và Trạng thái Đúng/Sai (dựa vào text hoặc class CSS `.wrong`, `.incorrect`, `.text-danger`, màu sắc ô câu hỏi).
   * Với tất cả những câu Làm sai, Khoanh bừa (kể cả ăn may đúng) hoặc Làm quá lâu (`time_sink`):
     * Playwright tự động cuộn (`locator.scroll_into_view_if_needed()`) đến đúng khung chứa câu hỏi và lời giải đó.
     * Chụp ảnh độ phân giải cao riêng khung lời giải chính thức (`locator.screenshot(path=...)`) — đảm bảo mọi công thức MathJax, hình vẽ hình học không gian hay đồ thị hàm số trong lời giải đều được bắt trọn vẹn 100%.

---

## 8. VÒNG LẶP KÉP: AI TỰ HỌC KHI GIẢI SAI (REFLEXION RAG) & NHÉT KIẾN THỨC VÀO NÃO NGƯỜI

Đây là trái tim thông minh nhất của hệ thống, giải quyết đồng thời 2 vấn đề: **Làm sao để AI không giải sai đề TSA?** và **Làm sao để người học không quên lỗi sai sau 3 ngày?**

```plaintext
[ KHI PHÁT HIỆN CÂU SAI / KHOANH BỪA ]
                     │
     ┌───────────────┴───────────────┐
     ▼                               ▼
[ LUỒNG 1: AI TỰ HỌC (REFLEXION RAG) ]   [ LUỒNG 2: NHÉT VÀO NÃO NGƯỜI ]
1. Lấy quy tắc cũ trong SQLite (`ai_rules`)   1. Tạo Móc Phản Xạ 1 dòng (If-Then Trigger)
2. AI tự giải độc lập đề bài trước             2. Chỉ rõ Bẫy Tư Duy & Mẹo bấm Casio 15s
3. So sánh đáp án AI với Đáp án chuẩn Web     3. Bắt người dùng gõ 1 dòng Feynman Note
4. Nếu AI giải SAI -> Đưa ảnh Lời giải chuẩn  4. Sinh "Câu hỏi Sinh Đôi" (Twin Question)
   ép AI tự tìm lỗi và đúc kết Quy tắc mới       cùng cấu trúc bẫy để làm lại trong 60s
5. Lưu Quy tắc mới vào SQLite để đề sau        5. Đưa vào lịch Spaced Repetition (SM-2):
   tự động chèn vào Prompt không tái phạm!        Nhắc làm lại sau 1 -> 3 -> 7 -> 14 ngày
```

### 8.1. Chi tiết Luồng 1: Cơ chế "AI Tự Học Khi Giải Sai" (Local Rulebook RAG)

Vì `gemini-webapi` tạo phiên chat mới mỗi lần gọi và ta không thể fine-tune trọng số trên server của Google, ta xây dựng **Bộ nhớ Quy tắc Nội bộ (`ai_learned_rules`)** trong SQLite:

* **Bước 1 (Truy xuất ký ức):** Trước khi giải một câu thuộc chuyên đề Tích phân hàm ẩn, Python truy vấn SQLite lấy ra các quy tắc mà AI từng rút kinh nghiệm ở chuyên đề này trong các đề trước và đính kèm vào Prompt.
* **Bước 2 (Thử lửa độc lập):** Cho Gemini 3.8 Flash nhìn ảnh câu hỏi (chưa cho xem lời giải của web) để tự giải và chốt đáp án `ai_answer`.
* **Bước 3 (Phản tư khi giải sai - Reflexion):** Nếu `ai_answer != correct_answer` (ví dụ đáp án chuẩn là C nhưng AI giải ra B), hệ thống lập tức gửi tiếp bức ảnh Lời giải chính thức của Web (do Playwright chụp ở Mục 7) kèm lệnh phạt:
  > *"Bạn vừa giải ra B là SAI. Đáp án chuẩn là C (xem ảnh lời giải đính kèm). Hãy chỉ rõ bước nào bạn đã hiểu nhầm điều kiện đề bài hoặc tính toán sai, và đúc kết thành 1 QUY TẮC CỐT LÕI (dưới 40 từ) để lần sau gặp dạng này không bao giờ lặp lại lỗi sai đó nữa."*
* **Bước 4 (Ghi nhớ vĩnh viễn):** Quy tắc mới được lưu thẳng vào bảng `ai_learned_rules`. Càng luyện nhiều đề cùng bạn, con AI trên máy bạn càng tinh thông đúng chuẩn cấu trúc đề TSA.

### 8.2. Chi tiết Luồng 2: Cơ chế "Nhét Kiến Thức Vào Não Người" (4 Công cụ Ghi nhớ Chủ động)

Để phá bỏ *"Ảo tưởng hiểu bài"* (Illusion of Competence) — đọc lời giải thấy hiểu nhưng vào phòng thi vẫn sai — mỗi câu sai được chuyển hóa thành 4 bước ép não hoạt động:

| Công cụ Ghi nhớ | Cách hiển thị & Tương tác trên App | Tác động lên Trí nhớ Não bộ |
| :--- | :--- | :--- |
| **1. Phản xạ Điều kiện (If-Then Trigger)** | Đóng khung nổi bật trên cùng: *"Hễ đề bài cho [Dấu hiệu X] $\rightarrow$ Lập tức dùng [Bước Y], tuyệt đối kiểm tra điều kiện [Z]"*. | Tạo "móc khóa phản xạ" ngắn gọn để não bật ra ngay trong 3 giây đầu tiên khi đọc đề trong phòng thi. |
| **2. Chẩn đoán Ngược Feynman (Active Diagnosis)** | Một ô nhập liệu nhỏ bắt buộc bạn tự gõ 1 câu ngắn gọn bằng lời của mình: *"Lúc nãy mình bị lừa ở chỗ nào?"* trước khi được đánh dấu "Đã hiểu". | Ép não chuyển từ đọc thụ động sang truy xuất chủ động, khắc sâu vị trí cái bẫy vào trí nhớ dài hạn. |
| **3. Câu hỏi Sinh đôi (Isomorphic Twin)** | Nút bấm *"Làm thử Câu Sinh Đôi (60s)"*: AI tự chế ra 1 câu hỏi mới tinh có cùng cấu trúc logic và cùng cái bẫy đó nhưng thay đổi số liệu/ngữ cảnh. | Kiểm tra tức thì xem bạn đã thực sự hiểu bản chất phương pháp hay chỉ vừa nhớ vẹt đáp án của câu cũ. |
| **4. Lặp lại Ngắt quãng (Spaced Repetition SM-2)** | Tự động lên lịch trong SQLite. Khi bạn mở app vào các ngày sau, thanh HUD sẽ báo: *"Hôm nay có 4 câu bẫy cũ đến hạn phục thù!"* theo chu kỳ **1 ngày $\rightarrow$ 3 ngày $\rightarrow$ 7 ngày $\rightarrow$ 14 ngày**. | Đánh gục "Đường cong quên lãng Ebbinghaus" — nhắc lại đúng thời điểm não bộ chuẩn bị xóa ký ức. |

---

## 9. THIẾT KẾ GIAO DIỆN 3 CHẾ ĐỘ HUD OVERLAY & BẢNG CÀI ĐẶT (SETTINGS CHO PC YẾU)

### 9.1. Ba Chế độ Biến hình của HUD Overlay (Điều khiển bằng Phím tắt Toàn cục)

#### Chế độ 1: In-Exam Stealth HUD (Lúc đang làm bài — 100% Xuyên chuột)
* **Hình dáng:** Một thanh Mini-Pill siêu gọn (240px x 36px), nằm sát mép trên cùng màn hình, hoàn toàn Click-through (bạn rê chuột hay click vào đó thì chuột vẫn bấm thẳng vào trang web thi bên dưới).
* **Hiển thị trực quan:**
```plaintext
╭───────────────────────────────────────────────────────────╮
│ 🟢 Câu hiện tại: 01:15 │ 📦 AI Queue: 3/4 │ [Alt+F: Cờ]   │
╰───────────────────────────────────────────────────────────╯
```
* **Đổi màu theo ngưỡng thời gian (nếu bật trong Settings):**
  * `0s – 60s`: Viền mảnh màu Xanh dương/Xanh lá dịu mắt.
  * `60s – Ngưỡng cảnh báo`: Chữ chuyển sang Vàng.
  * `Vượt ngưỡng` (VD: >120s cho Toán): Viền nhấp nháy Cam/Đỏ nhẹ nhàng kèm chữ *"⚠️ Quá giờ! Cắm cờ chuyển câu!"* (Không phát tiếng ồn nếu bạn tắt âm, không làm mất focus chuột).
* **Phím tắt trong lúc thi:**
  * `Alt + F` (Flag / Guess): Bấm nhanh khi bạn đang phân vân 50/50 hoặc đánh lụi câu đang nhìn $\rightarrow$ HUD nháy sáng báo đã ghi nhận để cuối giờ AI mổ xẻ kỹ câu này.
  * `Alt + H` (Hide): Ẩn/Hiện hoàn toàn thanh Mini-Pill nếu muốn màn hình trống 100%.

#### Chế độ 2: Post-Exam Auto-Scanner (Ngay khi bấm Nộp bài — `Alt + S`)
* Khi làm xong đề, bạn bấm `Alt + S`.
* Thanh HUD mở rộng nhẹ thông báo tiến trình tự động:
  * 🔍 *Đang kết nối trình duyệt cào đáp án chuẩn...*
  * 📸 *Đã chụp lời giải 8 câu sai & 5 câu làm quá giờ...*
  * 🧠 *Gemini 3.8 Flash đang đối chiếu & tạo thẻ Nhét Não...*

#### Chế độ 3: Slide-out Command Center Drawer (Ngăn kéo Học tập & Thống kê — `Alt + Z`)
* Bấm `Alt + Z`, một ngăn kéo hiện đại trượt từ mép phải màn hình ra (chiếm 38% màn hình bên phải, 62% màn hình bên trái vẫn là trang web đề thi để bạn đối chiếu trực tiếp).
* Lúc này chế độ Click-through tự động tắt trên vùng ngăn kéo để bạn click chuột tương tác với 4 Tab:
  * **Tab 1 — Bản đồ Trận đấu (Exam Breakdown):** Hiển thị tổng điểm, thời gian trung bình, và danh sách câu hỏi lọc theo bộ nút: `[Tất cả]`, `[🔴 Làm sai]`, `[🟣 Khoanh bừa]`, `[🟡 Làm lâu >2p]`. Đặc biệt: Click vào câu nào trên danh sách, Playwright tự động cuộn trình duyệt bên trái đến đúng câu đó!
  * **Tab 2 — Nhét vào não (Brain-Hack):** Hiển thị thẻ If-Then Trigger, giải thích bẫy, ô nhập Feynman Note, nút mở Câu hỏi sinh đôi 60s, và danh sách các thẻ đến hạn ôn tập Spaced Repetition hôm nay.
  * **Tab 3 — Tiến bộ & Não AI:** Biểu đồ xu hướng điểm số, biểu đồ độ bền tâm lý (Stamina 30p đầu vs 30p cuối), Heatmap chuyên đề yếu, và danh sách Quy tắc AI vừa tự học được (`ai_learned_rules`).
  * **Tab 4 — Cài đặt & Tối ưu hóa (Settings HUD):** Xem chi tiết mục 9.2 bên dưới.

### 9.2. Thiết kế Bảng Cài đặt (Settings HUD) & Tối ưu cho PC Yếu

```plaintext
┌──────────────────────────────────────────────────────────────────────┐
│  ⚙️ CÀI ĐẶT HỆ THỐNG & TỐI ƯU HÓA PC YẾU (TSA OVERLAY SETTINGS)       │
├──────────────────────────────────────────────────────────────────────┤
│ [ 1. CẢNH BÁO LÀM MỘT CÂU QUÁ LÂU (TIME-SINK ALERTS) ]               │
│  ☑ Bật thông báo khi làm 1 câu quá lâu trên thanh Mini-Pill          │
│  ├─ Ngưỡng cảnh báo phần Toán học:           [ 120 ] giây            │
│  └─ Ngưỡng cảnh báo Đọc hiểu / Khoa học:     [ 90  ] giây            │
│  ☑ Hiệu ứng nháy viền màu Cam/Đỏ khi vượt ngưỡng                     │
│  ☐ Phát âm thanh "Tít" nhẹ khi quá giờ                               │
│  ☑ Cảnh báo khi phát hiện Khoanh bừa liên tiếp cuối giờ              │
│                                                                      │
│ [ 2. HIỆU NĂNG & TÀI NGUYÊN CHO PC YẾU (LOW-END PC MODE) ]           │
│  ☑ Bật Chế độ Siêu Tiết Kiệm RAM (Flat UI - Tắt Blur/DropShadow)     │
│  ☑ Ẩn thanh HUD khỏi ảnh chụp màn hình (WDA_EXCLUDEFROMCAPTURE)      │
│  ├─ Chu kỳ quét màn hình (Capture FPS):   [ 2.0 giây/lần (0.5 FPS) ▼]│
│  └─ Chất lượng nén ảnh WebP Local:        [ 80% (Siêu nhẹ ~50KB)   ▼]│
│                                                                      │
│ [ 3. CẤU HÌNH AI (GEMINI 3.8 FLASH WEB API) & PLAYWRIGHT ]           │
│  ├─ Model sử dụng:                        [ gemini-3.8-flash       ] │
│  ├─ Nguồn Cookie:                         [ Tự động lấy từ Chrome  ▼]│
│  ├─ Thời gian nghỉ giữa 2 batch gửi AI:   [ 18 giây (Chống chặn)   ] │
│  ☑ Tự động xóa đoạn chat tạm trên Gemini Web sau khi lấy JSON         │
│  ☑ Bật chế độ AI Tự Học (Reflexion) khi AI giải lệch đáp án chuẩn    │
│  ☑ Tự động tạo "Câu hỏi sinh đôi" cho mọi câu làm sai / khoanh bừa   │
│                                                                      │
│ [ 4. PHÍM TẮT TOÀN CỤC (GLOBAL HOTKEYS) ]                            │
│  ├─ Bật/Tắt Ngăn kéo Thống kê & Học bài:  [ Alt + Z ]                │
│  ├─ Đánh dấu nhanh câu đang phân vân:     [ Alt + F ]                │
│  ├─ Chốt nộp bài & Tự động cào đáp án:    [ Alt + S ]                │
│  └─ Ẩn/Hiện hoàn toàn thanh Mini-Pill:    [ Alt + H ]                │
│                                                                      │
│                [ Lưu Cài Đặt ]      [ Khôi phục Mặc định ]           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 10. THIẾT KẾ CƠ SỞ DỮ LIỆU SQLITE (tsa_local.db) — ĐẦY ĐỦ 4 BẢNG

File `database.py` sẽ tự động khởi tạo 4 bảng SQLite sau ngay trong lần chạy đầu tiên:

```sql
-- BẢNG 1: Lưu thông tin mỗi ca làm đề (Exam Sessions)
CREATE TABLE IF NOT EXISTS exam_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_name TEXT NOT NULL,                   -- VD: "Đề thi thử TSA ĐHBK Lần 1"
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    total_time_seconds INTEGER DEFAULT 0,      -- Tổng thời gian làm bài thực tế
    score_math INTEGER DEFAULT 0,              -- Số câu đúng phần Toán (trên 40)
    score_reading INTEGER DEFAULT 0,           -- Số câu đúng Đọc hiểu (trên 20)
    score_science INTEGER DEFAULT 0,           -- Số câu đúng Khoa học (trên 40)
    time_sink_count INTEGER DEFAULT 0,         -- Tổng số câu làm quá giờ
    guessed_count INTEGER DEFAULT 0,           -- Tổng số câu khoanh bừa
    stamina_first_half_acc REAL,               -- Tỷ lệ đúng 30p đầu (%)
    stamina_last_half_acc REAL,                -- Tỷ lệ đúng 30p cuối (%)
    ai_overall_feedback TEXT                   -- Nhận xét chiến thuật tổng quan của Gemini
);

-- BẢNG 2: Lưu chi tiết từng câu hỏi trong đề (Question Logs)
CREATE TABLE IF NOT EXISTS question_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES exam_sessions(id) ON DELETE CASCADE,
    section TEXT,                              -- 'Toán học', 'Đọc hiểu', 'Khoa học'
    question_number INTEGER,                   -- Câu số mấy (1 -> 100)
    topic_tag TEXT,                            -- Chuyên đề (VD: "Tổ hợp - Xác suất", "Đọc hiểu công nghệ")
    question_complexity TEXT,                  -- 'low', 'medium', 'high'
    time_spent_seconds INTEGER DEFAULT 0,      -- Tổng số giây nhìn câu này (cộng dồn mọi lần quay lại)
    visit_count INTEGER DEFAULT 1,             -- Số lần quay lại câu này
    answer_switch_count INTEGER DEFAULT 0,     -- Số lần đổi đáp án A/B/C/D
    user_flagged BOOLEAN DEFAULT 0,            -- 1 nếu người dùng bấm Alt+F đánh dấu phân vân
    user_answer TEXT,                          -- Đáp án bạn chọn (A/B/C/D hoặc số điền)
    correct_answer TEXT,                       -- Đáp án chuẩn cào từ web
    is_correct BOOLEAN,                        -- 1: Đúng, 0: Sai
    status_flag TEXT,                          -- 'normal', 'time_sink', 'guessed'
    guessing_probability REAL DEFAULT 0.0,     -- Xác suất khoanh bừa (0.0 -> 1.0)
    behavior_note TEXT,                        -- Ghi chú hành vi (VD: "Chuyển câu sau 7s ở phút cuối")
    screenshot_path TEXT,                      -- Đường dẫn ảnh chụp câu hỏi (.webp)
    solution_screenshot_path TEXT,             -- Đường dẫn ảnh chụp lời giải chính thức (.webp)
    ai_explanation TEXT                        -- Lời giải & phân tích chi tiết của AI
);

-- BẢNG 3: Lưu "Kinh nghiệm xương máu" của AI sau những lần AI giải sai (Reflexion RAG)
CREATE TABLE IF NOT EXISTS ai_learned_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_tag TEXT NOT NULL,                   -- Chuyên đề (để truy xuất RAG khi gặp lại dạng này)
    mistake_pattern TEXT,                      -- Lý do trước đó AI bị mắc bẫy / giải sai
    learned_rule TEXT NOT NULL,                -- Quy tắc cốt lõi (<50 từ) rút ra từ đáp án chuẩn
    source_question_id INTEGER REFERENCES question_logs(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- BẢNG 4: Quản lý "Nhét vào não người" (Flashcard Phản xạ + Câu hỏi sinh đôi + Lịch SM-2)
CREATE TABLE IF NOT EXISTS human_memory_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER REFERENCES question_logs(id) ON DELETE CASCADE,
    topic_tag TEXT,
    if_then_trigger TEXT,                      -- Quy tắc phản xạ 1 dòng: "Hễ thấy X -> Làm Y"
    core_trap_note TEXT,                       -- Giải thích tại sao đáp án bạn chọn lại là bẫy
    mnemonic_tip TEXT,                         -- Mẹo nhớ nhanh / Cách thử máy tính Casio trong 15s
    twin_question_json TEXT,                   -- JSON chứa câu hỏi sinh đôi (đề, 4 đáp án, giải thích)
    user_feynman_note TEXT,                    -- Dòng tự thú lỗi sai do chính bạn gõ vào
    is_feynman_completed BOOLEAN DEFAULT 0,    -- Đã hoàn thành gõ giải thích ngược chưa
    repetition_stage INTEGER DEFAULT 0,        -- Mốc SM-2: 0 (Mới), 1 (+1d), 2 (+3d), 3 (+7d), 4 (+14d)
    next_review_date DATE                      -- Ngày thẻ này tự động nổi lên nhắc ôn tập
);
```

---

## 11. TOÀN BỘ CODE MẪU CỐT LÕI & CẤU TRÚC JSON PROMPT

Dưới đây là toàn bộ các đoạn code kỹ thuật quan trọng nhất đã được thiết kế cho hệ thống của bạn:

### 11.1. Code Quản lý Cài đặt (`config.py`) — Hỗ trợ bật/tắt cảnh báo & Low-End PC Mode

```python
import json
from pathlib import Path

DEFAULT_SETTINGS = {
    # Cảnh báo làm lâu (Time-sink)
    "enable_time_sink_alert": True,
    "math_threshold_sec": 120,
    "reading_science_threshold_sec": 90,
    "flash_border_on_alert": True,
    "beep_on_alert": False,
    "enable_panic_guess_alert": True,

    # Tối ưu PC yếu (Low-End PC Mode)
    "low_end_pc_mode": True,               # True = Dùng Flat QSS siêu nhẹ, tắt Blur/Shadow
    "exclude_hud_from_capture": True,      # Tàng hình HUD khi MSS chụp màn hình
    "capture_interval_sec": 2.0,           # 0.5 FPS - Cực nhẹ cho CPU
    "webp_quality": 80,

    # Cấu hình Gemini 3.8 Flash Web API & Playwright
    "gemini_model": "gemini-3.8-flash",
    "auto_browser_cookie": True,
    "manual_psid": "",
    "manual_psidts": "",
    "ai_queue_delay_sec": 18,              # Khoảng nghỉ an toàn giữa 2 lần gửi ảnh Grid
    "auto_delete_temp_chat": True,
    "enable_ai_self_learning": True,
    "cdp_port": 9222,

    # Phím tắt
    "hotkey_toggle_drawer": "alt+z",
    "hotkey_flag_question": "alt+f",
    "hotkey_submit_scan": "alt+s",
    "hotkey_hide_hud": "alt+h"
}

class ConfigManager:
    def __init__(self, path: str = "data/settings.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self.load()

    def load(self) -> dict:
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_SETTINGS, **data}
        return DEFAULT_SETTINGS.copy()

    def save(self, new_settings: dict):
        self.settings.update(new_settings)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)
```

### 11.2. Code Tàng hình Cửa sổ Overlay & Bấm xuyên chuột (`ui_overlay.py` trích đoạn cốt lõi)

```python
import ctypes
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Cờ Windows 10/11 giúp cửa sổ vô hình khi chụp màn hình

class StealthMiniPillHUD(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.current_seconds = 0
        self.init_ui()

    def init_ui(self):
        # 1. Cửa sổ không viền, luôn nổi trên cùng, công cụ không hiện dưới Taskbar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # Click xuyên thấu 100% xuống đề thi
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(820, 12, 320, 38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        
        self.status_label = QLabel("🟢 Câu hiện tại: 00:00 | Queue: 0")
        layout.addWidget(self.status_label)
        
        self.apply_style(alert_state="normal")
        
        # 2. Kích hoạt chế độ tàng hình trước ống kính chụp màn hình MSS
        if self.config.get("exclude_hud_from_capture", True):
            self.set_capture_stealth(True)

    def set_capture_stealth(self, enable: bool):
        hwnd = int(self.winId())
        affinity = WDA_EXCLUDEFROMCAPTURE if enable else WDA_NONE
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, affinity)

    def apply_style(self, alert_state: str = "normal"):
        # Giao diện Flat Dark Mode sắc nét, tốn dưới 5MB RAM đồ họa
        border_color = "#38bdf8"  # Xanh dương mặc định
        bg_color = "rgba(15, 23, 42, 215)"
        
        if alert_state == "warning":
            border_color = "#f59e0b"  # Vàng cam sắp lố giờ
        elif alert_state == "time_sink":
            border_color = "#ef4444"  # Đỏ cảnh báo sa lầy
            bg_color = "rgba(69, 10, 10, 230)"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 18px;
            }}
            QLabel {{
                color: #f8fafc;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 600;
                border: none;
                background: transparent;
            }}
        """)

    def update_timer_tick(self, seconds: int, queue_size: int, section: str = "math"):
        self.current_seconds = seconds
        mins, secs = divmod(seconds, 60)
        threshold = (
            self.config["math_threshold_sec"] 
            if section == "math" 
            else self.config["reading_science_threshold_sec"]
        )
        
        if self.config["enable_time_sink_alert"] and seconds >= threshold:
            self.apply_style("time_sink" if seconds % 2 == 0 else "warning")
            self.status_label.setText(f"⚠️ Quá giờ ({mins:02d}:{secs:02d})! Cắm cờ chuyển câu!")
        elif self.config["enable_time_sink_alert"] and seconds >= int(threshold * 0.75):
            self.apply_style("warning")
            self.status_label.setText(f"🟡 Câu hiện tại: {mins:02d}:{secs:02d} | Queue: {queue_size}")
        else:
            self.apply_style("normal")
            self.status_label.setText(f"🟢 Câu hiện tại: {mins:02d}:{secs:02d} | Queue: {queue_size}")
```

### 11.3. Code Kết nối `gemini-webapi` (Tự lấy Cookie + Đóng dấu Grid 2x2 + Vòng lặp Tự Học)

```python
import asyncio
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw
from gemini_webapi import GeminiClient

class TSAGeminiWebAnalyzer:
    def __init__(self, config: dict, db_conn):
        self.config = config
        self.db_conn = db_conn
        self.model_name = config.get("gemini_model", "gemini-3.8-flash")
        
        # Nếu auto_browser_cookie=True hoặc không nhập PSID thủ công,
        # GeminiClient() sẽ tự dùng browser-cookie3 đọc cookie từ Chrome/Edge trên máy
        psid = config.get("manual_psid") or None
        psidts = config.get("manual_psidts") or None
        self.client = GeminiClient(psid, psidts) if psid else GeminiClient()

    async def start(self):
        # Khởi tạo phiên và tự động làm mới __Secure-1PSIDTS suốt 150 phút làm bài
        await self.client.init(
            timeout=60, 
            auto_close=False, 
            auto_refresh=True
        )

    def create_stamped_grid(self, frames_data: list[dict], output_path: str) -> str:
        """
        frames_data = [
            { "image_path": "f1.webp", "duration": 145, "timestamp": "12:30", "switches": 2, "flagged": False },
            ... (tối đa 4 ảnh)
        ]
        Ghép 4 ảnh thành lưới 2x2 kèm thanh thông tin thời gian in trực tiếp lên mép ảnh.
        """
        imgs = []
        target_w, target_h = 960, 540
        
        for idx, item in enumerate(frames_data):
            img = Image.open(item["image_path"]).convert("RGB").resize((target_w, target_h))
            draw = ImageDraw.Draw(img)
            
            # Vẽ thanh header đen ở góc trên ảnh để AI đọc trực tiếp metadata
            draw.rectangle([(0, 0), (target_w, 36)], fill=(15, 23, 42))
            flag_str = " | [USER CẮM CỜ PHÂN VÂN]" if item.get("flagged") else ""
            banner_text = (
                f"Ô #{idx+1} | Lúc: {item['timestamp']} | "
                f"THỜI GIAN DỪNG: {item['duration']} GIÂY | "
                f"Đổi đáp án: {item.get('switches', 0)} lần{flag_str}"
            )
            draw.text((12, 8), banner_text, fill=(56, 189, 248))
            imgs.append(img)
            
        # Tạo khung lưới 2x2
        grid_img = Image.new("RGB", (target_w * 2, target_h * 2), color=(0, 0, 0))
        positions = [(0, 0), (target_w, 0), (0, target_h), (target_w, target_h)]
        for img, pos in zip(imgs, positions):
            grid_img.paste(img, pos)
            
        grid_img.save(output_path, "WEBP", quality=self.config.get("webp_quality", 80))
        return output_path

    async def analyze_batch(self, grid_image_path: str) -> list[dict]:
        math_lim = self.config.get("math_threshold_sec", 120)
        other_lim = self.config.get("reading_science_threshold_sec", 90)
        
        prompt = f"""
        Bạn là hệ thống phân tích hành vi làm bài thi TSA (Đánh giá tư duy).
        Hình ảnh đính kèm gồm tối đa 4 ô chụp màn hình làm bài. Ở mép trên mỗi ô đã ghi rõ:
        Ô số mấy, Thời điểm, THỜI GIAN DỪNG (giây), số lần đổi đáp án và cờ đánh dấu.

        Hãy đọc từng ô có chứa câu hỏi và trả về DUY NHẤT một khối JSON chuẩn theo cấu trúc:
        ```json
        [
          {{
            "cell_index": 1,
            "section": "Toán học | Đọc hiểu | Khoa học",
            "question_number": 14,
            "topic_tag": "Tên chuyên đề cụ thể (VD: Hình học không gian - Thể tích)",
            "question_complexity": "low | medium | high",
            "time_spent_seconds": 145,
            "selected_answer": "A/B/C/D hoặc nội dung điền, null nếu chưa chọn",
            "status_flag": "normal | time_sink | guessed",
            "guessing_probability": 0.15,
            "behavior_note": "Giải thích ngắn gọn tại sao phân loại như vậy"
          }}
        ]
        ```
        Quy tắc phân loại `status_flag`:
        - "time_sink" (Làm lâu): Toán > {math_lim}s, Đọc hiểu/Khoa học > {other_lim}s.
        - "guessed" (Khoanh bừa): Đề dài/có công thức nhưng THỜI GIAN DỪNG < 12s đã chọn đáp án, hoặc chọn liên tiếp ở những phút cuối giờ, hoặc đổi đáp án liên tục >= 3 lần, hoặc có nhãn [USER CẮM CỜ PHÂN VÂN].
        - "normal": Các trường hợp còn lại.
        """
        chat = self.client.start_chat(model=self.model_name)
        try:
            response = await chat.send_message(prompt, files=[Path(grid_image_path)])
            return self.extract_json(response.text)
        finally:
            if self.config.get("auto_delete_temp_chat", True) and getattr(chat, "cid", None):
                await self.client.delete_chat(chat.cid)

    async def process_wrong_question_and_learn(
        self,
        question_id: int,
        question_img_path: str,
        official_solution_img_path: str,
        topic_tag: str,
        user_answer: str,
        official_answer: str
    ) -> dict:
        cursor = self.db_conn.cursor()
        
        # 1. Lấy các quy tắc AI từng học được ở chuyên đề này trong quá khứ (Local RAG)
        cursor.execute(
            "SELECT learned_rule FROM ai_learned_rules WHERE topic_tag = ? ORDER BY id DESC LIMIT 5",
            (topic_tag,)
        )
        past_rules = [row[0] for row in cursor.fetchall()]
        rules_context = "\n".join(f"- {r}" for r in past_rules) if past_rules else "Chưa có."

        chat = self.client.start_chat(model=self.model_name)
        try:
            # 2. Bước 1: Yêu cầu AI tự giải câu hỏi độc lập (chưa cho xem đáp án chuẩn)
            solve_prompt = f"""
            Giải câu hỏi TSA trong ảnh (Chuyên đề: {topic_tag}).
            Các quy tắc kinh nghiệm từ lịch sử cần tuân thủ:
            {rules_context}
            Chỉ trả về JSON: {{"ai_answer": "A/B/C/D hoặc kết quả điền số", "short_solution": "Tóm tắt bước giải"}}
            """
            res1 = await chat.send_message(solve_prompt, files=[Path(question_img_path)])
            ai_attempt = self.extract_json(res1.text)
            ai_failed = (str(ai_attempt.get("ai_answer")).strip().upper() != official_answer.strip().upper())

            # 3. Bước 2: Đối chiếu với Đáp án chuẩn & Tạo gói học tập cho cả AI lẫn Người
            learn_prompt = f"""
            Đáp án chuẩn của đề là: {official_answer}.
            Người học đã chọn: {user_answer} (SAI).
            Lần giải thử vừa rồi của bạn ra: {ai_attempt.get("ai_answer")} ({'SAI' if ai_failed else 'ĐÚNG'}).
            Ảnh đính kèm là LỜI GIẢI CHÍNH THỨC từ hệ thống thi.

            Hãy đối chiếu lời giải chính thức và trả về DUY NHẤT 1 khối JSON theo cấu trúc:
            ```json
            {{
              "ai_self_reflection": {{
                "did_ai_fail": {str(ai_failed).lower()},
                "mistake_reason": "Nếu bạn giải sai, chỉ rõ bước nào bạn bị mắc bẫy (nếu đúng để null)",
                "new_learned_rule": "1 quy tắc cốt lõi dưới 40 từ rút ra từ lời giải chuẩn để lần sau AI không bao giờ giải sai dạng này nữa"
              }},
              "human_brain_hacks": {{
                "if_then_trigger": "Công thức phản xạ 1 dòng: Hễ thấy dấu hiệu [...] trong đề TSA -> Lập tức làm [...]",
                "core_trap": "Giải thích cực ngắn tại sao đáp án {user_answer} của người dùng lại là bẫy",
                "mnemonic_tip": "Mẹo nhớ nhanh / hình ảnh hóa / cách thử đáp án bằng máy tính cầm tay trong 15 giây",
                "twin_question": {{
                  "question_text": "Tự chế 1 câu hỏi tương tự (đổi số/ngữ cảnh) có cùng cái bẫy này",
                  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
                  "correct_option": "A/B/C/D",
                  "explanation": "Giải thích 1 dòng"
                }}
              }}
            }}
            ```
            """
            res2 = await chat.send_message(learn_prompt, files=[Path(official_solution_img_path)])
            learning_data = self.extract_json(res2.text)

            # 4. Nếu AI giải sai -> Lưu quy tắc mới vào "Não AI" (ai_learned_rules)
            refl = learning_data.get("ai_self_reflection", {})
            if self.config.get("enable_ai_self_learning", True) and refl.get("did_ai_fail") and refl.get("new_learned_rule"):
                cursor.execute(
                    """INSERT INTO ai_learned_rules (topic_tag, mistake_pattern, learned_rule, source_question_id)
                       VALUES (?, ?, ?, ?)""",
                    (topic_tag, refl.get("mistake_reason"), refl.get("new_learned_rule"), question_id)
                )

            # 5. Lưu bộ công cụ ghi nhớ vào "Não Người" (human_memory_cards), hẹn 1 ngày sau ôn lại
            hacks = learning_data.get("human_brain_hacks", {})
            cursor.execute(
                """INSERT INTO human_memory_cards (question_id, topic_tag, if_then_trigger, core_trap_note, mnemonic_tip, twin_question_json, next_review_date)
                   VALUES (?, ?, ?, ?, ?, ?, date('now', '+1 day'))""",
                (
                    question_id,
                    topic_tag,
                    hacks.get("if_then_trigger"),
                    hacks.get("core_trap"),
                    hacks.get("mnemonic_tip"),
                    json.dumps(hacks.get("twin_question"), ensure_ascii=False)
                )
            )
            self.db_conn.commit()
            return learning_data
        finally:
            if self.config.get("auto_delete_temp_chat", True) and getattr(chat, "cid", None):
                await self.client.delete_chat(chat.cid)

    @staticmethod
    def extract_json(raw_text: str):
        match = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", raw_text, re.DOTALL)
        json_str = match.group(1) if match else raw_text
        return json.loads(json_str)
```

---

## 12. LỘ TRÌNH XÂY DỰNG 4 GIAI ĐOẠN THỰC CHIẾN

* **Giai đoạn 1 — Khung Overlay Siêu Nhẹ & Bộ Cảm Biến Màn Hình (1–2 ngày):**
  * Dựng `config.py`, `database.py` và giao diện `ui_overlay.py` (Thanh Mini-Pill xuyên chuột, tàng hình `WDA_EXCLUDEFROMCAPTURE`, bảng Settings cho PC yếu).
  * Dựng `capture_sensor.py` dùng `mss` + `imagehash` đếm giây từng câu và ghép ảnh Grid 2x2 bằng Pillow.

* **Giai đoạn 2 — Tích hợp `gemini-webapi` & Hàng Đợi Ngầm (1–2 ngày):**
  * Kết nối tự động lấy Cookie trình duyệt, chạy `auto_refresh=True` và xử lý hàng đợi gửi ảnh Grid 2x2 trong lúc làm bài.

* **Giai đoạn 3 — Tự động Cào Đáp Án (Playwright CDP) & Vòng lặp Tự Học (2 ngày):**
  * Kết nối trình duyệt qua cổng 9222 khi bấm `Alt + S`, tự chụp lời giải chuẩn của các câu sai và chạy hàm `process_wrong_question_and_learn` (cập nhật cả bảng `ai_learned_rules` lẫn `human_memory_cards`).

* **Giai đoạn 4 — Hoàn thiện Ngăn kéo Học tập & Biểu đồ Tiến bộ (`Alt + Z`) (1–2 ngày):**
  * Hiển thị danh sách câu Sai/Khoanh bừa/Làm lâu (click để cuộn trình duyệt thật), làm thử Câu hỏi sinh đôi 60s, điền Feynman Note và nhắc lịch ôn tập Spaced Repetition SM-2.
