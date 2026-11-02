"""Playwright CDP (Port 9222) Zero-Intrusion Scraper: YouPass, STUDY4, and TSA DOM adapters."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BrowserScraper:
    """
    Zero-intrusion browser scraper interacting with Chrome / Edge via
    Chrome DevTools Protocol (CDP) on port 9222.
    """

    SUPPORTED_DOMAINS = [
        "hociz.vn",
        "hociz",
        "youpass.vn",
        "study4.com",
        "tuyensinh247.com",
        "tsa",
        "ielts",
        "localhost",
    ]

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser = None
        self._active_page = None
        self._lock = asyncio.Lock()

    @staticmethod
    def is_cdp_available(cdp_url: str) -> bool:
        """Fast non-blocking check if CDP port is listening before launching playwright."""
        try:
            import urllib.request
            norm_url = cdp_url.replace("localhost", "127.0.0.1")
            version_url = norm_url.rstrip("/") + "/json/version"
            with urllib.request.urlopen(version_url, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def launch_chrome_with_cdp(target_url: str = "https://hociz.vn") -> bool:
        """
        Launches Google Chrome with --remote-debugging-port=9222 and opens target_url.
        Uses standard installation paths and ensures CDP flags are applied cleanly.
        """
        import subprocess
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        chrome_exe = None
        for p in possible_paths:
            if os.path.isfile(p):
                chrome_exe = p
                break

        if not chrome_exe:
            logger.warning("Google Chrome executable not found in standard paths.")
            return False

        args = [
            chrome_exe,
            "--remote-debugging-port=9222",
            "--remote-allow-origins=*",
            target_url,
        ]
        try:
            subprocess.Popen(args, close_fds=True)
            logger.info("Launched Chrome with CDP port 9222 at %s", target_url)
            return True
        except Exception as e:
            logger.error("Failed launching Chrome with CDP: %s", e)
            return False

    async def connect(self) -> bool:
        """Connects over CDP to the running browser without restarting or disturbing tabs."""
        if not self.is_cdp_available(self.cdp_url):
            logger.info("CDP endpoint %s not listening (Chrome with --remote-debugging-port=9222 not running).", self.cdp_url)
            return False

        try:
            from playwright.async_api import async_playwright

            if self._browser is not None:
                return True

            self._playwright = await async_playwright().start()
            effective_url = self.cdp_url.replace("localhost", "127.0.0.1")
            self._browser = await self._playwright.chromium.connect_over_cdp(
                effective_url,
                timeout=10000,
            )
            logger.info("Connected to browser over CDP at %s", self.cdp_url)
            return True
        except Exception as e:
            logger.warning("CDP connection to %s failed: %s", self.cdp_url, e)
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnects cleanly from the CDP endpoint."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None
            self._active_page = None

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None

        # Give event loop a tick to flush pipe transports on Windows Proactor
        try:
            await asyncio.sleep(0.05)
        except Exception:
            pass

    async def find_exam_page(self, preferred_domain: Optional[str] = None):
        """
        Locates the active tab running an exam portal (youpass, study4, tuyensinh247, etc.).
        """
        if not await self.connect():
            return None

        try:
            contexts = self._browser.contexts
            for context in contexts:
                for page in context.pages:
                    url = page.url.lower()
                    if preferred_domain and preferred_domain.lower() in url:
                        self._active_page = page
                        return page
                    for domain in self.SUPPORTED_DOMAINS:
                        if domain in url:
                            self._active_page = page
                            return page

            # If no domain matched, fallback to first open tab
            if contexts and contexts[0].pages:
                self._active_page = contexts[0].pages[0]
                return self._active_page
        except Exception as e:
            logger.error("Error finding exam page: %s", e)

        return None

    async def check_is_exam_submitted(self) -> Optional[Dict[str, Any]]:
        """
        Fast non-intrusive probe checking if the user has completed and submitted the exam.
        Detects result page routes and result DOM elements across Hociz, Study4, YouPass, etc.
        """
        page = await self.find_exam_page()
        if not page:
            return None

        try:
            js_probe = """
            () => {
                const url = window.location.href;
                const isResultUrl = /lich-su-lam-bai|mark-point-exams|result|ket-qua|review/i.test(url);
                const hasResultDom = document.querySelector(
                    '.border-danger, .bg-danger, .test-result, .result-board, [class*="ExamResult"], [class*="result-summary"], .score-board'
                ) !== null;
                const hasSubmitBtn = Array.from(document.querySelectorAll('button, a')).some(
                    el => /^(Nộp bài|Hoàn thành bài thi|Submit)$/i.test(((el.innerText || el.textContent) || '').trim())
                );
                if (isResultUrl || (hasResultDom && !hasSubmitBtn)) {
                    return {
                        submitted: true,
                        url: url,
                        domain: window.location.hostname
                    };
                }
                return null;
            }
            """
            return await page.evaluate(js_probe)
        except Exception as e:
            logger.debug("Quiet exception probing exam submission: %s", e)
            return None

    async def get_current_active_question(self) -> Optional[int]:
        """
        Detects currently active question number in the browser DOM in real time.
        Checks active buttons in question palettes or question elements in viewport.
        """
        page = await self.find_exam_page()
        if not page:
            return None

        try:
            js_code = """
            () => {
                // 1. Look for active question palette button
                const activeBtn = document.querySelector(
                    '.question-nav button.active, .palette .btn-primary, [class*="active"][class*="question"], .btn-active-question, button[class*="active"], [aria-current="true"]'
                );
                if (activeBtn) {
                    const m = (activeBtn.innerText || activeBtn.textContent || '').match(/\\d+/);
                    if (m) return parseInt(m[0], 10);
                }
                // 2. Look for active question card near top of viewport
                const cards = document.querySelectorAll(
                    '[id^="question-"], [id^="question_"], .question-item, .test-question, [class*="question-card"], [class*="QuestionCard"]'
                );
                for (let card of cards) {
                    const rect = card.getBoundingClientRect();
                    if (rect.top >= -80 && rect.top <= 450) {
                        const m = (card.id || card.getAttribute('data-hud-qid') || card.innerText || '').match(/\\b(?:câu|q|question)?\\s*(\\d+)\\b/i);
                        if (m) return parseInt(m[1], 10);
                    }
                }
                return null;
            }
            """
            return await page.evaluate(js_code)
        except Exception as e:
            logger.debug("Quiet exception reading active question from DOM: %s", e)
            return None

    # ==========================================
    # DOM EXTRACTION ADAPTERS
    # ==========================================

    async def scrape_post_exam_results(
        self, profile_type: str = "YOUPASS_READING"
    ) -> List[Dict[str, Any]]:
        """
        Scrapes incorrect questions from the current result page using platform-specific adapters.
        """
        page = await self.find_exam_page()
        if not page:
            logger.warning("No active browser exam tab found over CDP.")
            return []

        async with self._lock:
            try:
                page_url = page.url.lower()
                if "hociz" in page_url or "HOCIZ" in profile_type.upper():
                    return await self._scrape_hociz(page)
                elif "STUDY4" in profile_type.upper():
                    return await self._scrape_study4(page)
                elif "YOUPASS" in profile_type.upper():
                    return await self._scrape_youpass(page, profile_type)
                elif "TSA" in profile_type.upper():
                    if "hociz" in page_url:
                        return await self._scrape_hociz(page)
                    return await self._scrape_tsa(page)
                else:
                    # General adapter fallback
                    return await self._scrape_general(page)
            except Exception as e:
                logger.error("Failed scraping post-exam results: %s", e)
                return []

    async def _scrape_study4(self, page) -> List[Dict[str, Any]]:
        """
        STUDY4 Adapter:
        1. Expands hidden explanation divs (.collapse:not(.show) -> .show).
        2. Detects wrong questions via .text-danger, .fa-times, .incorrect.
        3. Injects data-hud-qid for quick scroll targeting.
        """
        js_code = """
        () => {
            // 1. Expand all hidden explanation sections
            document.querySelectorAll('.collapse:not(.show)').forEach(el => el.classList.add('show'));

            const items = [];
            // Target candidate question containers
            const containers = document.querySelectorAll(
                '.result-question-item, .question-wrapper, .test-question, [class*="question-item"]'
            );

            containers.forEach((container, idx) => {
                const isWrong = container.querySelector('.text-danger, .fa-times, .incorrect, .badge-danger') !== null;
                const qNumEl = container.querySelector('.question-number, .q-num, b, strong');
                let qNum = idx + 1;
                if (qNumEl) {
                    const match = qNumEl.innerText.match(/\\d+/);
                    if (match) qNum = parseInt(match[0], 10);
                }

                // Inject HUD attribute for click-to-scroll
                container.setAttribute('data-hud-qid', qNum.toString());

                if (isWrong) {
                    const questionTextEl = container.querySelector('.question-text, .stem, .content');
                    const questionText = questionTextEl ? questionTextEl.innerText.trim() : container.innerText.slice(0, 300);

                    const userAnsEl = container.querySelector('.user-answer, .selected, .text-danger');
                    const officialAnsEl = container.querySelector('.correct-answer, .official-answer, .text-success');
                    const explanationEl = container.querySelector('.explanation, .explain, .solution-detail');
                    const quoteEl = container.querySelector('.transcript, .quote, .passage-highlight');

                    items.push({
                        question_number: qNum,
                        section_tag: "STUDY4_READING",
                        question_type: "Reading Comprehension",
                        question_text: questionText,
                        user_answer: userAnsEl ? userAnsEl.innerText.trim() : "Chưa xác định",
                        official_answer: officialAnsEl ? officialAnsEl.innerText.trim() : "Chưa xác định",
                        platform_explanation: explanationEl ? explanationEl.innerText.trim() : "",
                        transcript_quote: quoteEl ? quoteEl.innerText.trim() : "",
                        dom_selector: `[data-hud-qid="${qNum}"]`,
                        is_correct: 0
                    });
                }
            });

            return items;
        }
        """
        return await page.evaluate(js_code)

    async def _scrape_youpass(self, page, profile_type: str) -> List[Dict[str, Any]]:
        """
        YouPass Adapter:
        1. Scrapes incorrect question cards and Logical Framework explanations.
        2. Extracts target passage highlights.
        3. For YouPass Writing, extracts task prompt + user essay.
        """
        is_writing = "WRITING" in profile_type.upper()
        js_code = f"""
        () => {{
            const items = [];
            const isWriting = {str(is_writing).lower()};

            if (isWriting) {{
                const promptEl = document.querySelector('.writing-task-prompt, .topic-content, .prompt');
                const essayEl = document.querySelector('.user-essay, textarea, .writing-submission');
                items.push({{
                    question_number: 1,
                    section_tag: "YOUPASS_WRITING",
                    question_type: "Task Writing",
                    question_text: promptEl ? promptEl.innerText.trim() : "Đề bài IELTS Writing",
                    user_answer: essayEl ? (essayEl.value || essayEl.innerText).trim() : "",
                    official_answer: "Sample Band 8.0+",
                    platform_explanation: "Phân tích cấu trúc Task Response & Coherence",
                    dom_selector: ".user-essay, textarea",
                    is_correct: 0
                }});
                return items;
            }}

            const cards = document.querySelectorAll(
                '.question-card, .quiz-question, .result-item, .reading-question-card'
            );

            cards.forEach((card, idx) => {{
                const isWrong = card.querySelector('.incorrect, .text-danger, .badge-danger, .fa-times') !== null;
                const qNumEl = card.querySelector('.number, .q-idx, .badge');
                let qNum = idx + 1;
                if (qNumEl) {{
                    const match = qNumEl.innerText.match(/\\d+/);
                    if (match) qNum = parseInt(match[0], 10);
                }}

                card.setAttribute('data-hud-qid', qNum.toString());

                if (isWrong) {{
                    const stemEl = card.querySelector('.stem, .question-title, .title');
                    const userAnsEl = card.querySelector('.user-choice, .selected-incorrect, .text-danger');
                    const officialAnsEl = card.querySelector('.correct-choice, .text-success, .key');
                    const frameworkEl = card.querySelector('.logical-framework, .explanation-box, .explain');
                    const highlightEl = card.querySelector('.passage-highlight, .evidence, .reference-quote');

                    items.push({{
                        question_number: qNum,
                        section_tag: "YOUPASS_READING",
                        question_type: "Logical Reading",
                        question_text: stemEl ? stemEl.innerText.trim() : card.innerText.slice(0, 250),
                        user_answer: userAnsEl ? userAnsEl.innerText.trim() : "Lựa chọn của bạn",
                        official_answer: officialAnsEl ? officialAnsEl.innerText.trim() : "Đáp án đúng",
                        platform_explanation: frameworkEl ? frameworkEl.innerText.trim() : "",
                        transcript_quote: highlightEl ? highlightEl.innerText.trim() : "",
                        dom_selector: `[data-hud-qid="${{qNum}}"]`,
                        is_correct: 0
                    }});
                }}
            }});

            return items;
        }}
        """
        return await page.evaluate(js_code)

    async def _scrape_tsa(self, page) -> List[Dict[str, Any]]:
        """
        TSA Adapter:
        1. Locates incorrect questions.
        2. Captures element screenshot saved into captures/solutions/.
        3. Extracts stem, options, and solution text.
        """
        solutions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "captures",
            "solutions",
        )
        os.makedirs(solutions_dir, exist_ok=True)

        # First evaluate questions metadata
        js_code = """
        () => {
            const items = [];
            const cards = document.querySelectorAll(
                '.tsa-question, .exam-question, .question-card, [id^="question_"]'
            );

            cards.forEach((card, idx) => {
                const isWrong = card.querySelector('.wrong, .incorrect, .text-danger, .icon-cross') !== null;
                const qNum = idx + 1;
                card.setAttribute('data-hud-qid', qNum.toString());

                if (isWrong || cards.length <= 10) { // Keep wrong or all if compact
                    items.push({
                        question_number: qNum,
                        section_tag: "TSA_PROBLEM_SOLVING",
                        question_type: "TSA Critical Thinking",
                        question_text: card.innerText.slice(0, 300),
                        user_answer: "Lựa chọn sai",
                        official_answer: "Đáp án đúng",
                        platform_explanation: "Lời giải chi tiết câu hỏi TSA",
                        dom_selector: `[data-hud-qid="${qNum}"]`,
                        is_correct: 0
                    });
                }
            });
            return items;
        }
        """
        results = await page.evaluate(js_code)

        # Capture element screenshots for TSA questions
        for item in results:
            q_num = item["question_number"]
            selector = f'[data-hud-qid="{q_num}"]'
            img_path = os.path.join(solutions_dir, f"tsa_q_{q_num}.png")
            try:
                el = await page.query_selector(selector)
                if el:
                    await el.screenshot(path=img_path)
                    item["solution_img_path"] = img_path
            except Exception as e:
                logger.warning("Could not screenshot TSA element %s: %s", selector, e)

        return results

    async def _scrape_hociz(self, page) -> List[Dict[str, Any]]:
        """
        HOCIZ (hociz.vn) TSA Adapter:
        1. Checks if viewing result page (/lich-su-lam-bai/[id] or /mark-point-exams/[id]).
        2. If result view modal is closed, automatically clicks 'Xem đáp án' / 'Xem lời giải'.
        3. Identifies incorrect questions by examining options with .border-danger/.bg-danger
           or typing inputs with danger state, or question palette badges.
        4. Extracts question content, selected wrong answer, official correct answer, and explanation.
        5. Injects data-hud-qid attributes for click-to-scroll.
        6. Captures element screenshots for all wrong questions into captures/solutions/.
        """
        solutions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "captures",
            "solutions",
        )
        os.makedirs(solutions_dir, exist_ok=True)

        # 1. Ensure answers modal is opened if on summary board
        try:
            q_cards = await page.query_selector_all('[id^="question-"]')
            if not q_cards:
                buttons = await page.query_selector_all('button')
                for btn in buttons:
                    txt = (await btn.inner_text()).strip().lower()
                    if any(k in txt for k in ["xem đáp án", "xem lời giải", "xem chi tiết", "đáp án"]):
                        await btn.click()
                        await page.wait_for_timeout(1200)
                        break
        except Exception as e:
            logger.debug("Hociz auto-open modal check: %s", e)

        # 2. Extract DOM metadata
        js_code = """
        () => {
            const items = [];
            let questionEls = Array.from(document.querySelectorAll(
                '[id^="question-"], [id^="question_"], .question-item, .exam-question, .question-card, [class*="QuestionCard"], [class*="questionItem"], [class*="question-card"], [class*="test-question"], .ant-card'
            ));
            
            if (questionEls.length === 0) {
                const proseBlocks = Array.from(document.querySelectorAll('.prose, .ck-content'));
                if (proseBlocks.length > 0) {
                    questionEls = proseBlocks.map(p => p.closest('div') || p);
                }
            }

            // Detect wrong questions from palette if present
            const paletteWrongBtns = Array.from(document.querySelectorAll(
                '.question-nav button.text-danger, .palette button[class*="danger"], button[class*="wrong"], button[class*="incorrect"], [class*="bg-danger"]'
            ));
            const wrongQNumbers = new Set(paletteWrongBtns.map(b => {
                const m = (b.innerText || b.textContent || '').match(/\\d+/);
                return m ? parseInt(m[0], 10) : null;
            }).filter(Boolean));
            
            questionEls.forEach((card, idx) => {
                const qNumEl = card.querySelector('.question-number, .q-num, b, strong, [class*="number"]');
                let qNum = idx + 1;
                if (qNumEl) {
                    const match = (qNumEl.innerText || qNumEl.textContent || '').match(/\\d+/);
                    if (match) qNum = parseInt(match[0], 10);
                }
                card.setAttribute('data-hud-qid', qNum.toString());

                // Detect if question is wrong:
                // Option container has 'wrong' class / border-danger / bg-danger-50 / bg-danger
                const hasWrongOption = card.querySelector(
                    '.border-danger, .bg-danger, .bg-danger-50, [class*="bg-danger"], [class*="border-danger"], [class*="wrong"]'
                ) !== null;
                
                // Or typing input with danger color
                const hasDangerInput = card.querySelector('[data-color="danger"], .text-danger') !== null;
                
                const isWrong = hasWrongOption || hasDangerInput || wrongQNumbers.has(qNum);

                // Determine section tag based on question index (TSA: 40 Toán, 20 Đọc, 40 Khoa)
                let sectionTag = "TSA_MATH";
                if (qNum > 40 && qNum <= 60) {
                    sectionTag = "TSA_READING";
                } else if (qNum > 60) {
                    sectionTag = "TSA_SCIENCE";
                }

                // Extract User Answer (the wrong choice)
                let userAnswer = "Đã chọn phương án chưa chính xác";
                const wrongOptionEl = card.querySelector('.border-danger, .bg-danger, .bg-danger-50');
                if (wrongOptionEl) {
                    userAnswer = (wrongOptionEl.innerText || wrongOptionEl.textContent || "").trim().slice(0, 160);
                } else {
                    const typingInput = card.querySelector('input');
                    if (typingInput && typingInput.value) {
                        userAnswer = String(typingInput.value).slice(0, 160);
                    }
                }

                // Extract Official Correct Answer
                let officialAnswer = "Đáp án chuẩn";
                const correctOptionEl = card.querySelector('.border-success, .bg-success, .bg-success-50');
                if (correctOptionEl) {
                    officialAnswer = (correctOptionEl.innerText || correctOptionEl.textContent || "").trim().slice(0, 160);
                }

                // Extract Explanation / Giải thích
                let explanation = "";
                const explainHeaders = Array.from(card.querySelectorAll('div, span, p')).filter(
                    el => (el.innerText || el.textContent || "").toLowerCase().includes("giải thích")
                );
                if (explainHeaders.length > 0) {
                    const expContainer = explainHeaders[0].closest('div') || explainHeaders[0].parentElement;
                    if (expContainer) {
                        explanation = (expContainer.innerText || expContainer.textContent || "").trim().slice(0, 600);
                    }
                }

                // Extract Question Stem
                let stem = "";
                const proseEl = card.querySelector('.prose, .ck-content, [class*="prose"]');
                if (proseEl) {
                    stem = (proseEl.innerText || proseEl.textContent || "").trim().slice(0, 400);
                } else {
                    stem = (card.innerText || card.textContent || "").trim().slice(0, 300);
                }

                if (isWrong || questionEls.length <= 15) {
                    items.push({
                        question_number: qNum,
                        section_tag: sectionTag,
                        question_type: "TSA Đánh giá tư duy (hociz.vn)",
                        question_text: stem,
                        user_answer: userAnswer,
                        official_answer: officialAnswer,
                        platform_explanation: explanation || "Lời giải chi tiết câu hỏi TSA hociz.vn",
                        dom_selector: `[data-hud-qid="${qNum}"]`,
                        is_correct: isWrong ? 0 : 1
                    });
                }
            });

            return items;
        }
        """
        results = await page.evaluate(js_code)

        # 3. Capture element screenshots for each wrong question
        for item in results:
            q_num = item["question_number"]
            selector = f'[data-hud-qid="{q_num}"]'
            img_path = os.path.join(solutions_dir, f"hociz_q_{q_num}.png")
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.screenshot(path=img_path, timeout=3000)
                    item["solution_img_path"] = img_path
            except Exception as e:
                logger.warning("Could not screenshot Hociz element %s: %s", selector, e)

        return results

    async def _scrape_general(self, page) -> List[Dict[str, Any]]:
        """Fallback adapter for generic exam platforms."""
        js_code = """
        () => {
            const items = [];
            const wrongNodes = document.querySelectorAll('.incorrect, .wrong, .text-danger');
            wrongNodes.forEach((node, idx) => {
                const parent = node.closest('.card, .question, .row, div') || node;
                const qNum = idx + 1;
                parent.setAttribute('data-hud-qid', qNum.toString());
                items.push({
                    question_number: qNum,
                    section_tag: "GENERAL_EXAM",
                    question_type: "Multiple Choice",
                    question_text: parent.innerText.slice(0, 200),
                    user_answer: "Câu trả lời của bạn",
                    official_answer: "Đáp án chính xác",
                    platform_explanation: "",
                    dom_selector: `[data-hud-qid="${qNum}"]`,
                    is_correct: 0
                });
            });
            return items;
        }
        """
        return await page.evaluate(js_code)

    # ==========================================
    # INTERACTION & SCROLLING
    # ==========================================

    async def scroll_to_question(self, dom_selector: str) -> bool:
        """
        Smooth-scrolls target question to screen center and highlights it
        with a temporary glowing cyan border (3px solid #38bdf8).
        """
        page = await self.find_exam_page()
        if not page:
            logger.warning("No active browser page to scroll into.")
            return False

        try:
            js_code = """
            (selector) => {
                const target = document.querySelector(selector);
                if (!target) return false;

                // Smooth scroll to vertical center
                target.scrollIntoView({ behavior: 'smooth', block: 'center' });

                // Apply cyan glowing border
                const originalOutline = target.style.outline;
                const originalBoxShadow = target.style.boxShadow;

                target.style.outline = '3px solid #38bdf8';
                target.style.boxShadow = '0 0 16px rgba(56, 189, 248, 0.7)';
                target.style.transition = 'all 0.3s ease-in-out';

                // Automatically remove highlight after 4 seconds
                setTimeout(() => {
                    target.style.outline = originalOutline;
                    target.style.boxShadow = originalBoxShadow;
                }, 4000);

                return true;
            }
            """
            result = await page.evaluate(js_code, dom_selector)
            return bool(result)
        except Exception as e:
            logger.error("Error executing scroll_to_question(%s): %s", dom_selector, e)
            return False
