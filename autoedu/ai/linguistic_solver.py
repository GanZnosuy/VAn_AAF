"""
Specialized Linguistic Solver Modules for High-Stakes Language Exams
(IELTS, TOEFL, TOEIC, VSTEP, SAT Reading/Writing).

Features:
1. Strict 2-Step Evidence-Citation for True/False/Not Given and Yes/No/Not Given.
2. Global Elimination Matrix Algorithm for Matching Headings (ensuring 1-to-1 uniqueness).
3. Constraint-Enforced Gap-Fill / Summary Completion (word limits, verbatim passage match, grammar check).
4. Single vs Multi-Select Detection and parsing.
5. High-reliability regex parsing with fallback tolerance.
"""

import re
from typing import Dict, List, Optional, Any, Tuple


# ==============================================================================
# 1. QUESTION CLASSIFICATION ENGINE
# ==============================================================================

def classify_question_cluster(instruction: str, sample_text: str = "") -> str:
    """
    Classifies a question set into its linguistic typology based on prompt rubrics.
    Returns: 'tfng', 'yes_no_not_given', 'matching_headings', 'matching_features',
             'gap_fill', 'multiple_choice_multi', 'multiple_choice_single'
    """
    combined = (instruction + " " + sample_text).lower()

    if "true" in combined and "false" in combined and "not given" in combined:
        return "tfng"
    if "yes" in combined and "no" in combined and "not given" in combined:
        return "yes_no_not_given"
    if "heading" in combined or "list of headings" in combined:
        return "matching_headings"
    if "which paragraph contains" in combined or "match each statement" in combined or "look at the following" in combined:
        return "matching_features"
    if any(k in combined for k in ["no more than", "complete the summary", "complete the sentences", "fill in the blanks", "complete the notes", "complete the table"]):
        return "gap_fill"
    if re.search(r"choose\s+(?:two|three|four|\d+)\s+letters", combined) or "select all that apply" in combined:
        return "multiple_choice_multi"
    if "choose the correct letter" in combined or "a, b, c or d" in combined:
        return "multiple_choice_single"

    # Default fallback heuristics
    if "not given" in combined:
        return "tfng"
    if "complete" in combined or "summary" in combined:
        return "gap_fill"
    return "multiple_choice_single"


# ==============================================================================
# 2. PROMPT BUILDERS (CHAIN-OF-THOUGHT & CONTRACTS)
# ==============================================================================

def format_tfng_cluster_prompt(
    passage_text: str,
    questions: List[Dict[str, Any]],
    is_yes_no: bool = False
) -> str:
    """
    Builds a specialized prompt for True/False/Not Given or Yes/No/Not Given clusters.
    Enforces a strict 2-step evidence citation before verdict.
    """
    term_true = "YES" if is_yes_no else "TRUE"
    term_false = "NO" if is_yes_no else "FALSE"
    term_ng = "NOT GIVEN"

    q_lines = []
    for q in questions:
        q_num = q.get("qNum", "?")
        text = q.get("text", "")
        q_lines.append(f"Question {q_num}: {text}")

    questions_block = "\n".join(q_lines)

    return f"""You are a Cambridge-certified IELTS/TOEFL Senior Examiner and Master Linguistic Analyst.
Evaluate the following statements against the provided reading passage with absolute fidelity to the text.

### READING PASSAGE:
{passage_text}

### STATEMENTS TO EVALUATE:
{questions_block}

### STRICT CRITERIA:
- **{term_true}**: The statement strictly agrees with the information in the passage.
- **{term_false}**: The statement directly contradicts or is impossible according to the passage.
- **{term_ng}**: There is NO information on this claim, or it is impossible to know what the author thinks.
  *CRITICAL RULE FOR {term_ng}*: Never assume, speculate, or deduce facts that are not explicitly stated. If the passage does not confirm or negate the statement, it MUST be {term_ng}.

### REQUIRED OUTPUT FORMAT:
For EACH question, provide exactly:
1. EVIDENCE: The exact verbatim sentence from the passage that proves or contradicts the statement (or "NO MENTION IN TEXT").
2. REASONING: Concise 1-sentence breakdown of why it is {term_true}, {term_false}, or {term_ng}.
3. FINAL VERDICT: Exactly one of [{term_true}], [{term_false}], or [{term_ng}].

Example format:
Question 1:
EVIDENCE: "The tree species originally flourished throughout eastern Asia."
REASONING: The statement claims it was exclusive to Europe, which directly contradicts the text.
VERDICT: {term_false}
"""


def format_matching_headings_prompt(
    passage_paragraphs: Dict[str, str],
    headings_bank: List[str]
) -> str:
    """
    Builds a prompt to rank candidate headings for each paragraph to feed into
    the Elimination Matrix.
    """
    paras_block = []
    for label, text in passage_paragraphs.items():
        paras_block.append(f"--- [Paragraph {label}] ---\n{text}\n")
    paras_str = "\n".join(paras_block)

    headings_str = "\n".join([f"{idx+1}. {h}" for idx, h in enumerate(headings_bank)])

    return f"""You are an Expert Reading Analyst specialized in IELTS/TOEFL Matching Headings tasks.
Match each paragraph to its most accurate global heading from the provided List of Headings.

### LIST OF HEADINGS:
{headings_str}

### PARAGRAPHS:
{paras_str}

### INSTRUCTIONS:
- A heading must capture the MAIN IDEA of the entire paragraph, not just a supporting detail or single sentence.
- For EACH paragraph, rank the top 3 best matching headings along with a confidence percentage (0-100%).
- Provide a brief justification linking the paragraph's topic sentence/concluding synthesis to the heading.

OUTPUT FORMAT FOR EACH PARAGRAPH:
Paragraph <LABEL>:
- Best: <Heading Number or Roman Numeral> (Confidence: <XX>%) - Reason: <brief>
- Runner-up: <Heading Number> (Confidence: <XX>%)
- 3rd: <Heading Number> (Confidence: <XX>%)
"""


def format_gap_fill_prompt(
    passage_text: str,
    questions: List[Dict[str, Any]],
    word_limit_instruction: str = "NO MORE THAN TWO WORDS"
) -> str:
    """
    Builds a prompt for summary completion and gap fill tasks.
    Enforces word-count limits and verbatim extraction.
    """
    q_lines = []
    for q in questions:
        q_num = q.get("qNum", "?")
        text = q.get("text", "")
        q_lines.append(f"Gap {q_num}: {text}")
    questions_block = "\n".join(q_lines)

    return f"""You are a Premier Linguistic Exam Specialist.
Fill in the blanks using EXACT words taken directly from the reading passage.

### READING PASSAGE:
{passage_text}

### QUESTIONS / SUMMARY WITH GAPS:
{questions_block}

### STRICT CONSTRAINTS:
1. WORD LIMIT: {word_limit_instruction.upper()} from the passage for each answer. Answers exceeding this limit are strictly penalized with 0 marks.
2. VERBATIM REQUIREMENT: The answer MUST be an exact quote from the passage. Do NOT change word forms, tense, or spelling.
3. GRAMMATICAL ACCURACY: The filled word MUST grammatically complete the sentence (correct part of speech, singular/plural agreement).

OUTPUT FORMAT:
For EACH gap, output:
Gap <NUM>:
EXACT_WORD: <verbatim word(s) from passage>
CONTEXT_QUOTE: <sentence from passage where word appears>
"""


def format_multiple_choice_prompt(
    passage_text: str,
    questions: List[Dict[str, Any]],
    is_multi_select: bool = False,
    num_to_choose: int = 1
) -> str:
    """
    Builds a prompt for Single or Multi-Select Multiple Choice questions.
    """
    q_blocks = []
    for q in questions:
        q_num = q.get("qNum", "?")
        text = q.get("text", "")
        opts = q.get("options", [])
        opts_formatted = "\n".join([f"  - {opt}" for opt in opts])
        q_blocks.append(f"Question {q_num}: {text}\nOptions:\n{opts_formatted}\n")

    questions_block = "\n".join(q_blocks)
    choice_rule = f"Choose EXACTLY {num_to_choose} letters (e.g. ['A', 'C'])" if is_multi_select else "Choose EXACTLY 1 letter (A, B, C, or D)"

    return f"""You are a High-Score IELTS/TOEFL/SAT Reading Architect.
Solve the following multiple-choice questions based strictly on the passage.

### READING PASSAGE:
{passage_text}

### QUESTIONS:
{questions_block}

### CONSTRAINT:
{choice_rule}

OUTPUT FORMAT:
For EACH question:
Question <NUM>:
EVIDENCE: <quote from passage>
VERDICT: <Chosen Letter(s) e.g. A or A, C>
"""


# ==============================================================================
# 3. RESPONSE PARSERS & ELIMINATION MATRIX ALGORITHMS
# ==============================================================================

def parse_tfng_cluster_response(response: str, expected_qnums: List[int], is_yes_no: bool = False) -> Dict[int, Dict[str, Any]]:
    """
    Parses LLM response for TFNG questions into structured answers with evidence and confidence.
    """
    results = {}
    term_true = "YES" if is_yes_no else "TRUE"
    term_false = "NO" if is_yes_no else "FALSE"
    term_ng = "NOT GIVEN"

    for qnum in expected_qnums:
        # Search for block around Question {qnum}
        pattern = rf"(?:Question|C?u|Q)?\s*{qnum}\s*[:\.\-]([\s\S]*?)(?=(?:Question|C?u|Q)?\s*\d+\s*[:\.\-]|$)"
        m = re.search(pattern, response, re.IGNORECASE)
        block = m.group(1) if m else response

        # Extract verdict
        verdict = None
        v_match = re.search(rf"\bVERDICT\b\s*[:=]?\s*[*_`\[(]*\s*({term_true}|{term_false}|{term_ng})\b", block, re.IGNORECASE)
        if v_match:
            verdict = v_match.group(1).upper()
        else:
            # Fallback scan inside the block
            if re.search(rf"\b{term_ng}\b", block, re.IGNORECASE):
                verdict = term_ng
            elif re.search(rf"\b{term_false}\b", block, re.IGNORECASE):
                verdict = term_false
            elif re.search(rf"\b{term_true}\b", block, re.IGNORECASE):
                verdict = term_true
            else:
                verdict = term_true  # Default fallback

        # Extract evidence
        ev_match = re.search(r"EVIDENCE\s*[:=]?\s*[\"']?(.*?)[\"']?(?:\n|$|REASONING)", block, re.IGNORECASE)
        evidence = ev_match.group(1).strip() if ev_match else ""

        results[qnum] = {
            "verdict": verdict,
            "evidence": evidence,
            "confidence": 0.95 if verdict else 0.70
        }

    return results


def solve_matching_headings_elimination_matrix(
    llm_response: str,
    paragraph_labels: List[str],
    headings_bank: List[str]
) -> Dict[str, str]:
    """
    Elimination Matrix Algorithm:
    Builds a bipartite preference matrix between paragraphs and headings,
    then executes a greedy Hungarian-style assignment with uniqueness constraint
    to ensure NO heading is duplicated.
    """
    # Parse candidate scores for each paragraph
    # para_candidates[para_label] = [(heading_idx, score)]
    para_candidates: Dict[str, List[Tuple[int, float]]] = {}

    for label in paragraph_labels:
        para_candidates[label] = []
        pattern = rf"Paragraph\s+{label}\s*[:\.\-]([\s\S]*?)(?=Paragraph\s+[A-Z]|$)"
        m = re.search(pattern, llm_response, re.IGNORECASE)
        block = m.group(1) if m else ""

        # Extract ranked headings
        # e.g., Best: 3 (Confidence: 90%), Runner-up: 5
        matches = re.findall(r"(?:Best|Runner-up|3rd|Heading)?\s*[:\.\-]?\s*([ivxIVX\d]+)\s*(?:\(Confidence:\s*(\d+)%\))?", block)
        if matches:
            base_score = 1.0
            for raw_h, conf_str in matches:
                # Convert roman or int to integer 1-indexed
                h_idx = _parse_heading_index(raw_h)
                if h_idx is not None and 1 <= h_idx <= len(headings_bank):
                    conf = float(conf_str) / 100.0 if conf_str else base_score
                    para_candidates[label].append((h_idx, conf))
                    base_score -= 0.2
        
        # Fallback if parsing failed: assign sequential candidates
        if not para_candidates[label]:
            for i in range(1, len(headings_bank) + 1):
                para_candidates[label].append((i, 0.5))

    # Elimination Matrix Solver: Greedy Best-First with Uniqueness
    assigned_headings = set()
    final_assignments: Dict[str, str] = {}

    # Flatten all candidate pairs (score, para, heading)
    all_pairs = []
    for label, cands in para_candidates.items():
        for h_idx, score in cands:
            all_pairs.append((score, label, h_idx))

    # Sort descending by confidence score
    all_pairs.sort(key=lambda x: x[0], reverse=True)

    for score, label, h_idx in all_pairs:
        if label not in final_assignments and h_idx not in assigned_headings:
            final_assignments[label] = _index_to_roman(h_idx)
            assigned_headings.add(h_idx)

    # Fill any remaining unassigned paragraphs with leftover headings
    remaining_paras = [p for p in paragraph_labels if p not in final_assignments]
    available_headings = [i for i in range(1, len(headings_bank) + 1) if i not in assigned_headings]

    for p in remaining_paras:
        if available_headings:
            h_idx = available_headings.pop(0)
            final_assignments[p] = _index_to_roman(h_idx)
            assigned_headings.add(h_idx)
        else:
            final_assignments[p] = "i"

    return final_assignments


def _parse_heading_index(val: str) -> Optional[int]:
    """Converts Roman numeral or string digit to 1-based integer."""
    val = val.strip().lower()
    roman_map = {
        "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
        "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
        "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15
    }
    if val in roman_map:
        return roman_map[val]
    if val.isdigit():
        return int(val)
    return None


def _index_to_roman(num: int) -> str:
    """Converts integer index (1..15) to lower-case Roman numeral."""
    val_map = [
        (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')
    ]
    roman = ""
    for n, r in val_map:
        while num >= n:
            roman += r
            num -= n
    return roman if roman else "i"


def parse_gap_fill_response(
    response: str,
    expected_qnums: List[int],
    passage_text: str,
    max_words: int = 2
) -> Dict[int, Dict[str, Any]]:
    """
    Parses and strictly verifies gap fill answers:
    - Enforces max word limit.
    - Verifies verbatim presence in passage text.
    """
    results = {}
    passage_lower = passage_text.lower()

    for qnum in expected_qnums:
        pattern = rf"(?:Gap|Question|C?u)?\s*{qnum}\s*[:\.\-]([\s\S]*?)(?=(?:Gap|Question|C?u)?\s*\d+\s*[:\.\-]|$)"
        m = re.search(pattern, response, re.IGNORECASE)
        block = m.group(1) if m else response

        # Extract EXACT_WORD
        w_match = re.search(r"EXACT_WORD\s*[:=]?\s*[\"']?([^\n\r\"']+)[\"']?", block, re.IGNORECASE)
        raw_word = w_match.group(1).strip() if w_match else ""

        if not raw_word:
            # Fallback: find word in quotes or after colon
            fb = re.search(r"[:=]\s*[\"']?([A-Za-z0-9\s\-]+)[\"']?", block)
            if fb:
                raw_word = fb.group(1).strip()

        # Word limit enforcement
        words = raw_word.split()
        if len(words) > max_words:
            # Trim to max_words
            raw_word = " ".join(words[:max_words])

        # Verbatim check against passage
        is_verbatim = raw_word.lower() in passage_lower if raw_word else False

        results[qnum] = {
            "answer": raw_word,
            "is_verbatim": is_verbatim,
            "word_count": len(raw_word.split()),
            "confidence": 0.98 if is_verbatim else 0.75
        }

    return results


def parse_multiple_choice_response(
    response: str,
    expected_qnums: List[int],
    is_multi_select: bool = False,
    expected_count: int = 1
) -> Dict[int, List[str]]:
    """
    Parses single or multi-select letters (e.g. ['A'], ['B', 'D']).
    """
    results = {}
    for qnum in expected_qnums:
        pattern = rf"(?:Question|C?u|Q)?\s*{qnum}\s*[:\.\-]([\s\S]*?)(?=(?:Question|C?u|Q)?\s*\d+\s*[:\.\-]|$)"
        m = re.search(pattern, response, re.IGNORECASE)
        block = m.group(1) if m else response

        v_match = re.search(r"VERDICT\s*[:=]?\s*([A-Za-z\s,]+)", block, re.IGNORECASE)
        letters_text = v_match.group(1) if v_match else block

        found_letters = re.findall(r"\b([A-G])\b", letters_text.upper())
        if is_multi_select:
            selected = list(dict.fromkeys(found_letters))[:expected_count]
            if not selected:
                selected = ["A", "B"][:expected_count]
            results[qnum] = selected
        else:
            chosen = found_letters[0] if found_letters else "A"
            results[qnum] = [chosen]

    return results
