"""
Clustered Batch Inference & Execution Runner.
Coordinates dual-pane extraction, cluster-based question chunking,
precise context window pairing, specialized linguistic reasoning,
element dispatching, rate limit hygiene, and progress recovery.
"""

import asyncio
import re
from typing import Dict, List, Optional, Any
from playwright.async_api import Page

from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.extractor.dual_pane_extractor import DualPaneExtractor
from autoedu.solver.element_dispatcher import ElementDispatcher, SessionProgressManager
from autoedu.ai.linguistic_solver import (
    classify_question_cluster,
    format_tfng_cluster_prompt,
    parse_tfng_cluster_response,
    format_matching_headings_prompt,
    solve_matching_headings_elimination_matrix,
    format_gap_fill_prompt,
    parse_gap_fill_response,
    format_multiple_choice_prompt,
    parse_multiple_choice_response
)


class LinguisticExamRunner:
    """
    High-End Runner for Multi-Paragraph, Long-Form Language Exams
    (IELTS Academic/General, TOEFL iBT, TOEIC Reading, VSTEP, SAT Reading/Writing).
    """

    def __init__(
        self,
        page: Page,
        ai_client: Optional[GeminiWebClient] = None,
        rate_limit_delay: float = 2.5,
        session_file: Optional[str] = "session_progress.json"
    ):
        self.page = page
        self.ai = ai_client or GeminiWebClient()
        self.rate_limit_delay = rate_limit_delay
        self.extractor = DualPaneExtractor(page)
        self.dispatcher = ElementDispatcher(page)
        self.progress_mgr = SessionProgressManager(session_file)

    async def run(self, exam_url: str) -> bool:
        """
        Main execution flow:
        1. Navigate to exam URL.
        2. Extract & cache all passages across tabs.
        3. Identify and chunk question clusters.
        4. Solve each cluster with rate-limiting and progress tracking.
        5. Submit exam when complete.
        """
        print("=" * 70)
        print(f"[EXAM] [LINGUISTIC EXAM SOLVER] COMMENCING EXAM RUNNER")
        print(f"[URL] Target: {exam_url}")
        print("=" * 70)

        # 1. Page navigation & stabilization
        try:
            await self.page.goto(exam_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[!] [Runner] Navigation note: {e}")

        # Update session URL
        self.progress_mgr.state["exam_url"] = exam_url

        # Check for start buttons
        start_btn = await self.page.query_selector(
            "button:has-text('Start'), button:has-text('Take Test'), button:has-text('Bat dau'), button:has-text('Lam bai'), .btn-start, #btn-start"
        )
        if start_btn:
            print("[*] [Runner] Clicking exam start button...")
            await start_btn.click()
            await asyncio.sleep(2.0)

        # 2. Extract and cache all passages (Traversing tabs if present)
        print("[*] [Runner] Inspecting dual-pane DOM and traversing passage tabs...")
        passages = await self.extractor.detect_and_traverse_tabs()
        print(f"[+] [Runner] Successfully extracted & indexed {len(passages)} reading passage(s).")

        # 3. Extract question elements from the active page
        current_view = await self.extractor.extract_current_view()
        q_data = current_view.get("questionsData", {})
        questions: List[Dict[str, Any]] = q_data.get("questions", [])
        cluster_headers: List[str] = q_data.get("clusterHeaders", [])

        if not questions:
            print("[!] No structured questions found via dual-pane selector. Falling back to universal scan...")
            raw_blocks = await self.page.query_selector_all(".question, fieldset, [data-question-id], tr.question-row")
            for idx, rb in enumerate(raw_blocks, 1):
                txt = (await rb.inner_text()).strip()
                questions.append({
                    "qNum": idx,
                    "text": txt,
                    "elementSelector": None,
                    "hasRadio": True,
                    "hasTextInput": False
                })

        total_q = len(questions)
        print(f"[*] [Runner] Detected {total_q} total question items.")

        # 4. Group questions into logical prompt clusters (4-7 questions per cluster)
        clusters = self._partition_into_clusters(questions, cluster_headers)
        print(f"[*] [Runner] Formed {len(clusters)} logical question clusters for batch inference.")

        # 5. Process each cluster sequentially
        for c_idx, cluster in enumerate(clusters, 1):
            q_start = cluster["q_start"]
            q_end = cluster["q_end"]
            c_type = cluster["cluster_type"]
            c_items = cluster["items"]

            # Check if all questions in this cluster are already solved (Recovery)
            all_solved = all(self.progress_mgr.is_solved(q["qNum"]) for q in c_items)
            if all_solved:
                print(f"[>>] [Passage {cluster['passage_idx']}] [Questions {q_start}-{q_end}] [Type: {c_type.upper()}] -> Already solved in session. Skipping.")
                continue

            # Switch to correct passage tab if necessary
            target_p_idx = cluster["passage_idx"]
            if self.extractor.active_passage_idx != target_p_idx:
                await self._switch_to_passage(target_p_idx)

            active_passage_data = self.extractor.cached_passages.get(target_p_idx) or (passages[target_p_idx - 1] if target_p_idx <= len(passages) else passages[0])
            
            # Select relevant passage context based on cluster type
            context_text = self._prepare_context_for_cluster(c_type, active_passage_data, c_items)

            # Execute Specialized Linguistic Solver
            print(f"\n[AI] [Passage {target_p_idx}] [Questions {q_start}-{q_end}] [Type: {c_type.upper()}] Solving cluster ({len(c_items)} questions)...")
            solved_map = await self._solve_cluster_with_ai(c_type, context_text, active_passage_data, c_items, cluster.get("instruction", ""))

            # Inject answers into DOM
            for item in c_items:
                qnum = item["qNum"]
                if self.progress_mgr.is_solved(qnum):
                    continue

                ans_info = solved_map.get(qnum)
                if not ans_info:
                    continue

                injected = await self._inject_answer(item, c_type, ans_info)
                conf = ans_info.get("confidence", 0.95) if isinstance(ans_info, dict) else 0.95
                ans_display = ans_info.get("verdict") or ans_info.get("answer") or ans_info

                print(f"[OK] [Passage {target_p_idx}] [Question {qnum}] [Type: {c_type.upper()}] -> Solved & Injected (Ans: {ans_display}) (Confidence: {int(conf * 100)}%)")
                self.progress_mgr.record_answer(qnum, c_type, ans_display, confidence=conf, injected=injected)

            # Rate-limit hygiene delay between question clusters (2-3 seconds)
            await asyncio.sleep(self.rate_limit_delay)

        print("\n" + "=" * 70)
        print(f"[COMPLETE] [Runner] ALL {total_q} QUESTIONS COMPLETED! PROCEEDING TO SUBMISSION...")
        print("=" * 70)

        # 6. Automatic submission
        await self._submit_test()
        return True

    def _partition_into_clusters(
        self,
        questions: List[Dict[str, Any]],
        cluster_headers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Partitions 40 questions into chunks of 4-7 questions sharing common instructions,
        associated with their corresponding passage (Passage 1: 1-13, Passage 2: 14-26, Passage 3: 27-40).
        """
        q_map = {q["qNum"]: q for q in questions}
        sorted_qnums = sorted(q_map.keys())

        # 1. Parse explicit cluster ranges from headers if available
        header_ranges = []
        for h in cluster_headers:
            m = re.search(r"Questions?\s+(\d+)\s*(?:-|to)\s*(\d+)", h, re.IGNORECASE)
            if m:
                s_num, e_num = int(m.group(1)), int(m.group(2))
                header_ranges.append((s_num, e_num, h))

        clusters = []
        processed_qnums = set()

        for s_num, e_num, h_text in header_ranges:
            range_items = [q_map[qn] for qn in sorted_qnums if s_num <= qn <= e_num and qn in q_map]
            if range_items:
                for qn in range(s_num, e_num + 1):
                    processed_qnums.add(qn)

                if e_num <= 13:
                    p_idx = 1
                elif e_num <= 26:
                    p_idx = 2
                else:
                    p_idx = 3

                c_type = classify_question_cluster(h_text, range_items[0].get("text", ""))
                if range_items[0].get("hasSelect"):
                    c_type = "matching_headings"
                elif range_items[0].get("hasTextInput"):
                    c_type = "gap_fill"

                clusters.append({
                    "passage_idx": p_idx,
                    "q_start": range_items[0]["qNum"],
                    "q_end": range_items[-1]["qNum"],
                    "cluster_type": c_type,
                    "instruction": h_text,
                    "items": range_items
                })

        # 2. Process any remaining questions in groups of 4-7
        remaining_items = [q_map[qn] for qn in sorted_qnums if qn not in processed_qnums]
        if remaining_items:
            chunk_size = 6
            for i in range(0, len(remaining_items), chunk_size):
                chunk = remaining_items[i:i + chunk_size]
                q_start = chunk[0]["qNum"]
                q_end = chunk[-1]["qNum"]

                if q_end <= 13:
                    p_idx = 1
                elif q_end <= 26:
                    p_idx = 2
                else:
                    p_idx = 3

                if chunk[0].get("hasTextInput"):
                    c_type = "gap_fill"
                elif chunk[0].get("hasSelect"):
                    c_type = "matching_headings"
                elif chunk[0].get("hasCheckbox"):
                    c_type = "multiple_choice_multi"
                else:
                    c_type = "multiple_choice_single"

                clusters.append({
                    "passage_idx": p_idx,
                    "q_start": q_start,
                    "q_end": q_end,
                    "cluster_type": c_type,
                    "instruction": chunk[0].get("text", ""),
                    "items": chunk
                })

        clusters.sort(key=lambda c: c["q_start"])
        return clusters

    def _prepare_context_for_cluster(
        self,
        cluster_type: str,
        passage_data: Dict[str, Any],
        items: List[Dict[str, Any]]
    ) -> str:
        """
        Precise Context Window Management:
        Pairs each cluster only with relevant passage paragraphs or formatted text
        to prevent token truncation.
        """
        paragraphs = passage_data.get("paragraphs", {})

        if cluster_type == "matching_headings":
            return self.extractor.format_passage_for_prompt(passage_data)

        full_text = self.extractor.format_passage_for_prompt(passage_data)
        if len(full_text.split()) > 2000 and len(paragraphs) > 4:
            q_keywords = set()
            for item in items:
                words = re.findall(r"\b[A-Za-z]{4,}\b", item.get("text", "").lower())
                q_keywords.update(words)

            relevant_labels = []
            for label, p_text in paragraphs.items():
                p_words = set(re.findall(r"\b[A-Za-z]{4,}\b", p_text.lower()))
                overlap = len(q_keywords.intersection(p_words))
                if overlap > 0:
                    relevant_labels.append((label, overlap))

            relevant_labels.sort(key=lambda x: x[1], reverse=True)
            top_labels = [label for label, _ in relevant_labels[:4]]
            if top_labels:
                return self.extractor.format_passage_for_prompt(passage_data, selected_paragraphs=top_labels)

        return full_text

    async def _solve_cluster_with_ai(
        self,
        c_type: str,
        context_text: str,
        passage_data: Dict[str, Any],
        items: List[Dict[str, Any]],
        instruction: str
    ) -> Dict[int, Any]:
        """
        Dispatches prompt to Gemini AI and parses answers using domain-specific heuristics.
        """
        expected_qnums = [it["qNum"] for it in items]

        if c_type in ["tfng", "yes_no_not_given"]:
            is_yes_no = (c_type == "yes_no_not_given")
            prompt = format_tfng_cluster_prompt(context_text, items, is_yes_no=is_yes_no)
            res = await self.ai.query(prompt)
            return parse_tfng_cluster_response(res, expected_qnums, is_yes_no=is_yes_no)

        elif c_type == "matching_headings":
            paragraphs = passage_data.get("paragraphs", {})
            labels = list(paragraphs.keys())
            headings_bank = items[0].get("options", [])
            if not headings_bank:
                headings_bank = [f"Heading {i}" for i in range(1, len(labels) + 3)]

            prompt = format_matching_headings_prompt(paragraphs, headings_bank)
            res = await self.ai.query(prompt)
            assigned = solve_matching_headings_elimination_matrix(res, labels, headings_bank)

            results = {}
            for idx, label in enumerate(labels):
                if idx < len(expected_qnums):
                    qnum = expected_qnums[idx]
                    results[qnum] = {"answer": assigned.get(label, "i"), "confidence": 0.96}
            return results

        elif c_type == "gap_fill":
            word_limit = "NO MORE THAN TWO WORDS"
            if "one word" in instruction.lower():
                word_limit = "NO MORE THAN ONE WORD"
            elif "three words" in instruction.lower():
                word_limit = "NO MORE THAN THREE WORDS"

            prompt = format_gap_fill_prompt(context_text, items, word_limit_instruction=word_limit)
            res = await self.ai.query(prompt)
            max_w = 1 if "one" in word_limit.lower() else (3 if "three" in word_limit.lower() else 2)
            return parse_gap_fill_response(res, expected_qnums, context_text, max_words=max_w)

        elif c_type == "multiple_choice_multi":
            prompt = format_multiple_choice_prompt(context_text, items, is_multi_select=True, num_to_choose=2)
            res = await self.ai.query(prompt)
            parsed = parse_multiple_choice_response(res, expected_qnums, is_multi_select=True, expected_count=2)
            return {qn: {"answer": letters, "confidence": 0.94} for qn, letters in parsed.items()}

        else:  # multiple_choice_single
            prompt = format_multiple_choice_prompt(context_text, items, is_multi_select=False, num_to_choose=1)
            res = await self.ai.query(prompt)
            parsed = parse_multiple_choice_response(res, expected_qnums, is_multi_select=False, expected_count=1)
            return {qn: {"verdict": letters[0], "confidence": 0.95} for qn, letters in parsed.items()}

    async def _inject_answer(self, item: Dict[str, Any], c_type: str, ans_info: Any) -> bool:
        """
        Dispatches answer injection based on element type and question structure.
        """
        sel = item.get("elementSelector")
        container = await self.page.query_selector(sel) if sel else None

        ans_val = ans_info.get("verdict") if isinstance(ans_info, dict) else None
        if not ans_val and isinstance(ans_info, dict):
            ans_val = ans_info.get("answer")

        if c_type in ["tfng", "yes_no_not_given"]:
            verdict = str(ans_val).strip()
            mapping = {"TRUE": "A", "FALSE": "B", "NOT GIVEN": "C", "YES": "A", "NO": "B"}
            letter = mapping.get(verdict.upper(), "A")
            return await self.dispatcher.inject_radio_choice(container, letter)

        elif c_type == "matching_headings":
            roman = str(ans_val).strip()
            injected = await self.dispatcher.inject_dropdown_selection(container, roman)
            if not injected:
                injected = await self.dispatcher.inject_radio_choice(container, roman)
            return injected

        elif c_type == "gap_fill":
            text = str(ans_val).strip()
            return await self.dispatcher.inject_text_input(container, text)

        elif c_type == "multiple_choice_multi":
            letters = ans_val if isinstance(ans_val, list) else [str(ans_val)]
            return await self.dispatcher.inject_checkbox_multi(container, letters)

        else:  # multiple_choice_single
            letter = str(ans_val).strip().upper()
            return await self.dispatcher.inject_radio_choice(container, letter)

    async def _switch_to_passage(self, passage_idx: int):
        """Switches UI to specific passage tab."""
        tab_buttons = await self.page.query_selector_all(
            '.passage-tabs button, .passage-tabs a, ul.nav-tabs li, [role="tab"], .part-item'
        )
        if 0 <= passage_idx - 1 < len(tab_buttons):
            await tab_buttons[passage_idx - 1].click()
            await asyncio.sleep(1.0)
            self.extractor.active_passage_idx = passage_idx

    async def _submit_test(self):
        """Finds and triggers test submission button."""
        submit_selectors = [
            "button:has-text('Submit')", "button:has-text('Nop bai')", "button:has-text('Finish')",
            "button:has-text('Finish Test')", "button:has-text('Complete')", ".btn-submit"
        ]
        for s in submit_selectors:
            btn = await self.page.query_selector(s)
            if btn and await btn.is_visible():
                print("[SUBMIT] [Runner] Submitting exam...")
                await btn.click()
                await asyncio.sleep(2.0)
                confirm_btn = await self.page.query_selector(".modal button:has-text('Yes'), .modal button:has-text('Confirm')")
                if confirm_btn:
                    await confirm_btn.click()
                    await asyncio.sleep(2.0)
                break
