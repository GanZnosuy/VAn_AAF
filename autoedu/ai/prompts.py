import re
from typing import List, Dict

def is_english_text(text: str) -> bool:
    """Kiểm tra câu hỏi hoặc ngữ cảnh có thuộc môn Tiếng Anh hay không."""
    text_lower = text.lower()
    english_signals = [
        "mark the letter", "pronunciation", "underlined", "primary stress",
        "closest in meaning", "opposite in meaning", "best completes",
        "read the following passage", "according to the passage",
        "which of the following", "indicate the correct answer",
        "fill in the blank", "correct form of", "synonym", "antonym",
        "grammar", "vocabulary", "cloze test", "sentence", "questions 1",
        "questions 2", "questions 3", "choose the word"
    ]
    if any(sig in text_lower for sig in english_signals):
        return True

    # Kiểm tra tỉ lệ từ tiếng Anh phổ biến
    common_en_words = {
        "the", "is", "are", "in", "at", "on", "of", "and", "to", "a", "an",
        "that", "this", "which", "with", "for", "from", "by", "as", "he",
        "she", "it", "they", "we", "you", "not", "have", "has", "had"
    }
    words = set(re.findall(r"\b[a-z]{2,}\b", text_lower))
    overlap = len(words.intersection(common_en_words))
    vn_accents = re.findall(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", text_lower)

    if overlap >= 3 and len(vn_accents) < len(words) * 0.25:
        return True

    return False

def format_choice_prompt(question: str, options: List[str]) -> str:
    """
    Định dạng prompt cho câu hỏi trắc nghiệm A-D với Chain-of-Thought (suy luận từng bước).
    Tự động nhận diện: Tiếng Anh (IELTS/THPT Chuyên Anh) hoặc Toán/KHTN (THPT Quốc Gia).
    """
    clean_opts = []
    for idx, opt in enumerate(options):
        letter = chr(65 + idx)
        cleaned = re.sub(rf"^{letter}\s*[\.:\)]\s*", "", opt.strip())
        clean_opts.append(f"{letter}. {cleaned}")
        
    opts_str = "\n".join(clean_opts)

    if is_english_text(question + " " + opts_str):
        return (
            f"You are a Master English Teacher and High-Score IELTS/SAT/THPT National Exam Specialist.\n"
            f"Solve the following English question with absolute accuracy (aiming for 10/10):\n\n"
            f"QUESTION / READING PASSAGE:\n{question}\n\n"
            f"OPTIONS:\n{opts_str}\n\n"
            f"REASONING PROTOCOL (CHAIN OF THOUGHT):\n"
            f"1. Identify the linguistic skill: Phonetics (pronunciation/stress), Grammar/Tense, Vocabulary/Collocations/Idioms, Error Identification, or Reading Comprehension.\n"
            f"2. Explain concisely why the correct option is the best fit and eliminate distractors.\n"
            f"3. THE VERY LAST LINE must conclude with exactly:\n"
            f"ĐÁP ÁN: <A/B/C/D>"
        )

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
    m = re.search(r"(?:ĐÁP\s*ÁN|DAP\s*AN|CHỌN|KẾT\s*QUẢ|ANSWER|CHOICE)\s*[:=]?\s*[*_`\[(]*\s*([A-D])\b", response, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    
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
        f"Bạn là Giáo viên và Chuyên gia giải đề thi THPT Quốc Gia hàng đầu.\n"
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
        m = re.search(rf"(?:ý|mệnh\s*đề)?\s*{part}\s*[\)\.\:\-]\s*[*_`]*\s*(Đúng|Sai|True|False)", response, re.IGNORECASE)
        if not m:
            m = re.search(rf"\b{part}\b.*?[:=].*?(Đúng|Sai|True|False)", response, re.IGNORECASE)
        ans = m.group(1).capitalize() if m else "Đúng"
        if ans in ["True", "Đúng"]:
            answers[part] = "Đúng"
        else:
            answers[part] = "Sai"
    return answers

def format_short_answer_prompt(question: str) -> str:
    """
    Định dạng prompt cho câu hỏi trả lời ngắn / điền vào chỗ trống.
    Tự động nhận diện: Tiếng Anh (điền từ/cụm từ) hoặc Toán (điền số thập phân/nguyên).
    """
    if is_english_text(question):
        return (
            f"You are an Elite English Language Specialist.\n"
            f"Answer the following fill-in-the-blank / short answer question with absolute precision:\n\n"
            f"QUESTION / CONTEXT:\n{question}\n\n"
            f"RULES:\n"
            f"1. Determine the exact word or phrase that grammatically and contextually completes the sentence.\n"
            f"2. Do not include extraneous punctuation or words.\n"
            f"3. THE VERY LAST LINE must conclude with:\n"
            f"ĐÁP ÁN: <word/phrase>"
        )

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
    """Trích xuất kết quả từ phản hồi AI: hỗ trợ cả số (Toán) và từ vựng/chữ cái (Tiếng Anh)."""
    match = re.search(r"(?:ĐÁP\s*ÁN|DAP\s*AN|KẾT\s*QUẢ|KET\s*QUA|ANSWER|FINAL\s*ANSWER|GIÁ\s*TRỊ)\s*[:=]?\s*[*_`\[(]*\s*([^\n\r*`\])]+)", response, re.IGNORECASE)
    if match:
        val = match.group(1).strip()
        if re.match(r"^[-]?\d+[.,]\d+$", val):
            return val.replace(".", ",")
        return val

    nums = re.findall(r"[-]?\d+(?:[.,]\d+)?", response)
    if nums:
        raw = nums[-1].replace(".", ",")
        return raw.rstrip(",")

    return "0"
