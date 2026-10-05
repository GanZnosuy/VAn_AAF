import re
from typing import List, Dict

def format_choice_prompt(question: str, options: List[str]) -> str:
    """
    Định dạng prompt cho câu hỏi trắc nghiệm A-D với Chain-of-Thought (suy luận từng bước).
    Tối ưu hóa đặc biệt cho chương trình THPT Quốc Gia (Toán, Lý, Hóa, Sinh).
    """
    clean_opts = []
    for idx, opt in enumerate(options):
        letter = chr(65 + idx)
        cleaned = re.sub(rf"^{letter}\s*[\.:\)]\s*", "", opt.strip())
        clean_opts.append(f"{letter}. {cleaned}")
        
    opts_str = "\n".join(clean_opts)
    return (
        f"Bạn là Giáo viên và Chuyên gia giải đề thi môn Toán và Khoa học tự nhiên THPT Quốc Gia hàng đầu.\n"
        f"Hãy giải bài tập sau với độ chính xác cao nhất (mục tiêu 10/10 điểm):\n\n"
        f"ĐỀ BÀI:\n{question}\n\n"
        f"CÁC LỰA CHỌN:\n{opts_str}\n\n"
        f"QUY TRÌNH SUY LUẬN BẮT BUỘC (CHAIN OF THOUGHT):\n"
        f"1. Xác định giả thiết, công thức áp dụng (chú ý dấu âm/dương, điều kiện xác định, tọa độ, vectơ).\n"
        f"2. Trình bày chi tiết các bước tính toán và kiểm tra lại kết quả tính.\n"
        f"3. So sánh kỹ với từng phương án A, B, C, D để loại trừ phương án nhiễu.\n"
        f"4. DÒNG CUỐI CÙNG kết luận chính xác theo định dạng:\n"
        f"ĐÁP ÁN: <A/B/C/D>"
    )

def parse_choice_answer(response: str) -> str:
    """Trích xuất ký tự đáp án A, B, C hoặc D từ phản hồi AI với khả năng chịu lỗi cao."""
    # Tìm theo format chuẩn: ĐÁP ÁN: A hoặc **ĐÁP ÁN:** [A]
    m = re.search(r"(?:ĐÁP\s*ÁN|CHỌN|KẾT\s*QUẢ)\s*[:=]?\s*[*_`\[(]*\s*([A-D])\b", response, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    
    # Tìm chữ cái A-D đứng độc lập ở các dòng cuối
    lines = [ln.strip() for ln in response.strip().split("\n") if ln.strip()]
    for ln in reversed(lines[-5:]):
        sub_m = re.search(r"\b([A-D])\b", ln)
        if sub_m:
            return sub_m.group(1).upper()

    letters = re.findall(r"\b([A-D])\b", response)
    return letters[-1].upper() if letters else "A"

def format_true_false_prompt(question: str, statements: List[str]) -> str:
    """
    Định dạng prompt cho câu hỏi Đúng/Sai 4 mệnh đề a, b, c, d.
    Yêu cầu phân tích độc lập từng mệnh đề trước khi kết luận.
    """
    stmts_text = "\n".join(statements) if statements else "Xem các mệnh đề trong đề bài."
    return (
        f"Bạn là Giáo viên và Chuyên gia giải đề thi môn Toán và Khoa học tự nhiên THPT Quốc Gia hàng đầu.\n"
        f"Hãy xét tính Đúng / Sai của từng mệnh đề dưới đây với độ chính xác tuyệt đối:\n\n"
        f"ĐỀ BÀI:\n{question}\n\n"
        f"CÁC MỆNH ĐỀ CẦN XÉT TÍNH ĐÚNG / SAI:\n{stmts_text}\n\n"
        f"QUY TRÌNH SUY LUẬN:\n"
        f"- Xét độc lập từng mệnh đề a, b, c, d.\n"
        f"- Nêu rõ chứng minh/tính toán ngắn gọn vì sao Đúng hoặc Sai.\n"
        f"- KẾT LUẬN CUỐI CÙNG bắt buộc đầy đủ 4 dòng theo đúng định dạng sau:\n"
        f"a) <Đúng/Sai>\n"
        f"b) <Đúng/Sai>\n"
        f"c) <Đúng/Sai>\n"
        f"d) <Đúng/Sai>"
    )

def parse_true_false_answer(response: str) -> Dict[str, str]:
    """Trích xuất kết quả Đúng/Sai cho 4 mệnh đề a, b, c, d từ phản hồi AI."""
    answers = {}
    for part in ["a", "b", "c", "d"]:
        # Khớp định dạng: a) Đúng, a. Đúng, Ý a: Đúng, Mệnh đề a là Đúng, v.v.
        m = re.search(rf"(?:ý|mệnh\s*đề)?\s*{part}\s*[\)\.\:\-]\s*[*_`]*\s*(Đúng|Sai)", response, re.IGNORECASE)
        if not m:
            m = re.search(rf"\b{part}\b.*?[:=].*?(Đúng|Sai)", response, re.IGNORECASE)
        answers[part] = m.group(1).capitalize() if m else "Đúng"
    return answers

def format_short_answer_prompt(question: str) -> str:
    """
    Định dạng prompt cho câu hỏi điền số / trả lời ngắn (Phần III).
    Chuẩn hóa kết quả theo quy chuẩn thi THPT: số nguyên hoặc số thập phân dùng dấu phẩy ','.
    """
    return (
        f"Bạn là Giáo viên và Chuyên gia giải đề thi môn Toán và Khoa học tự nhiên THPT Quốc Gia hàng đầu.\n"
        f"Hãy giải chi tiết bài toán trả lời ngắn dưới đây và tìm ra kết quả số chính xác:\n\n"
        f"ĐỀ BÀI:\n{question}\n\n"
        f"QUY TRÌNH SUY LUẬN:\n"
        f"1. Xác định điều kiện, bản chất toán học và thực hiện phép tính cẩn thận.\n"
        f"2. Nếu kết quả là phân số, hãy chuyển thành số thập phân (hoặc xem đề có yêu cầu làm tròn không).\n"
        f"3. Quy tắc ghi đáp án: Chỉ sử dụng chữ số, dấu phẩy ',' (nếu là số thập phân) và dấu '-' (nếu là số âm). Tuyệt đối không ghi thêm chữ hay đơn vị đo.\n"
        f"4. DÒNG CUỐI CÙNG kết luận đúng định dạng:\n"
        f"ĐÁP ÁN: <số>"
    )

def parse_short_answer(response: str) -> str:
    """Trích xuất giá trị số từ phản hồi AI, chuẩn hóa dấu phẩy thập phân theo tiêu chuẩn Onluyen."""
    match = re.search(r"(?:ĐÁP\s*ÁN|KẾT\s*QUẢ|GIÁ\s*TRỊ)\s*[:=]?\s*[*_`]*\s*([-\d,.]+)", response, re.IGNORECASE)
    if match:
        raw = match.group(1).replace(".", ",")
        return raw.rstrip(",")
    
    # Tìm số cuối cùng xuất hiện trong văn bản
    nums = re.findall(r"[-]?\d+(?:[.,]\d+)?", response)
    if nums:
        raw = nums[-1].replace(".", ",")
        return raw.rstrip(",")
    return "0"
