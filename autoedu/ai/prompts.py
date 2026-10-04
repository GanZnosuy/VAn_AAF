import re
from typing import List, Dict

def format_choice_prompt(question: str, options: List[str]) -> str:
    """Định dạng prompt cho câu hỏi trắc nghiệm A-D."""
    # Làm sạch tiền tố trùng lặp nếu có (A., B., ...)
    clean_opts = []
    for idx, opt in enumerate(options):
        letter = chr(65 + idx)
        cleaned = re.sub(rf"^{letter}\s*", "", opt.strip())
        clean_opts.append(f"{letter}. {cleaned}")
        
    opts_str = "\n".join(clean_opts)
    return (
        f"{question}\n\n"
        f"Các lựa chọn:\n{opts_str}\n\n"
        f"Hãy giải bài tập chi tiết và kết luận phương án đúng nhất.\n"
        f"Kết luận cuối cùng bằng định dạng chính xác:\n"
        f"ĐÁP ÁN: <A/B/C/D>"
    )

def parse_choice_answer(response: str) -> str:
    """Trích xuất ký tự đáp án A, B, C hoặc D từ phản hồi AI."""
    m = re.search(r"ĐÁP ÁN:.*?([A-D])\b", response, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    letters = re.findall(r"\b([A-D])\b", response)
    return letters[-1].upper() if letters else "A"

def format_true_false_prompt(question: str, statements: List[str]) -> str:
    """Định dạng prompt cho câu hỏi Đúng/Sai 4 mệnh đề."""
    stmts_text = "\n".join(statements) if statements else "Xem trong đề bài."
    return (
        f"{question}\n\n"
        f"Các khẳng định cần xét tính đúng/sai:\n{stmts_text}\n\n"
        f"Hãy xét từng khẳng định a, b, c, d là Đúng hay Sai.\n"
        f"Kết luận cuối cùng theo đúng định dạng sau:\n"
        f"a) <Đúng/Sai>\n"
        f"b) <Đúng/Sai>\n"
        f"c) <Đúng/Sai>\n"
        f"d) <Đúng/Sai>"
    )

def parse_true_false_answer(response: str) -> Dict[str, str]:
    """Trích xuất kết quả Đúng/Sai cho 4 mệnh đề a, b, c, d."""
    answers = {}
    for part in ["a", "b", "c", "d"]:
        m = re.search(rf"{part}\)\s*[*_]*\s*(Đúng|Sai)", response, re.IGNORECASE)
        answers[part] = m.group(1).capitalize() if m else "Đúng"
    return answers

def format_short_answer_prompt(question: str) -> str:
    """Định dạng prompt cho câu hỏi điền số/ngắn."""
    return (
        f"{question}\n\n"
        f"Yêu cầu: Giải chi tiết bài tập và đưa ra kết quả cuối cùng.\n"
        f"Quy tắc ghi đáp án: Chỉ sử dụng chữ số, dấu phẩy ',' (nếu là số thập phân) và dấu '-' (nếu là số âm). Không viết thêm chữ hay đơn vị đo.\n"
        f"Kết luận cuối cùng bằng định dạng chính xác:\n"
        f"ĐÁP ÁN: <số>"
    )

def parse_short_answer(response: str) -> str:
    """Trích xuất giá trị số từ phản hồi AI."""
    match = re.search(r"ĐÁP ÁN:\s*[*_]*\s*([-\d,.]+)", response)
    if match:
        return match.group(1).replace(".", ",")
    nums = re.findall(r"[-]?\d+(?:[.,]\d+)?", response)
    return nums[-1].replace(".", ",") if nums else "0"
