"""
Dual-Pane DOM Extractor & Context Segmentation Module.
Detects split-screen / sticky reading passages vs question containers,
preserves structural paragraph indexing ([Paragraph A], subheadings, footnotes),
and handles multi-passage tab & section traversal (e.g. IELTS Reading Passage 1, 2, 3).
"""

import asyncio
import re
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, ElementHandle


# Client-side JavaScript snippet to extract dual-pane structure,
# paragraph labels, subheadings, footnotes, and question items with high accuracy.
JS_DUAL_PANE_EXTRACTOR = """() => {
    // 1. Heuristic selectors for Reading Passage containers
    const PASSAGE_SELECTORS = [
        '#reading-passage', '.reading-passage', '.passage-content', '.reading-container',
        '[data-pane="passage"]', '.left-pane', '.left-col', '.col-left', '.passage-body',
        '.reading_text', '.reading-text', 'div[class*="passage"]', 'div[class*="reading-section"]',
        '#reading_passage', '.ielts-passage', '.test-reading', '.split-left',
        '#passage-container', '.passage-wrapper', '.text-content', 'article.passage'
    ];

    // 2. Heuristic selectors for Question containers
    const QUESTION_SELECTORS = [
        '#questions-container', '.questions-container', '.question-list', '.right-pane',
        '.right-col', '.col-right', '[data-pane="questions"]', '.reading-questions',
        '.test-questions', 'form.question-form', '.test-paper', 'div[class*="question-container"]',
        '#question-content', '.split-right', '#question-pane', '.question-wrapper'
    ];

    // Helper: Find element matching array of selectors
    function findFirst(selectors, root = document) {
        for (const s of selectors) {
            try {
                const el = root.querySelector(s);
                if (el && el.innerText && el.innerText.trim().length > 30) return el;
            } catch (e) {}
        }
        return null;
    }

    // Fallback: Detect split-screen by layout geometry (columns side by side)
    function detectSplitPanesByGeometry() {
        const candidates = Array.from(document.querySelectorAll('div, section, main, article'));
        let bestLeft = null;
        let bestRight = null;
        let maxArea = 0;

        for (const el of candidates) {
            const rect = el.getBoundingClientRect();
            // Check if visible and substantial in size
            if (rect.width > 280 && rect.height > 300) {
                const text = el.innerText ? el.innerText.trim() : '';
                if (text.length > 200) {
                    const centerX = rect.left + rect.width / 2;
                    const viewWidth = window.innerWidth;
                    if (centerX < viewWidth * 0.55 && (!bestLeft || rect.width * rect.height > bestLeft.area)) {
                        bestLeft = { el: el, area: rect.width * rect.height, rect: rect };
                    } else if (centerX >= viewWidth * 0.45 && (!bestRight || rect.width * rect.height > bestRight.area)) {
                        bestRight = { el: el, area: rect.width * rect.height, rect: rect };
                    }
                }
            }
        }
        return {
            left: bestLeft ? bestLeft.el : null,
            right: bestRight ? bestRight.el : null
        };
    }

    let passageEl = findFirst(PASSAGE_SELECTORS);
    let questionEl = findFirst(QUESTION_SELECTORS);

    if (!passageEl || !questionEl) {
        const geo = detectSplitPanesByGeometry();
        if (!passageEl && geo.left) passageEl = geo.left;
        if (!questionEl && geo.right) questionEl = geo.right;
    }

    // Default to document body if still not found
    if (!passageEl) passageEl = document.querySelector('article') || document.body;
    if (!questionEl) questionEl = document.body;

    // 3. Extract Passages with Paragraph Indexing
    function extractPassageData(container) {
        const titleEl = container.querySelector('h1, h2, h3, .passage-title, .title');
        const title = titleEl ? titleEl.innerText.trim() : 'Reading Passage';

        const subEl = container.querySelector('.passage-subtitle, .subtitle, h4');
        const subtitle = subEl ? subEl.innerText.trim() : '';

        // Extract footnotes/glossary if any
        const footnotes = [];
        const fnEls = container.querySelectorAll('.footnote, .glossary, .vocabulary, [class*="footnote"], [class*="glossary"]');
        fnEls.forEach(fn => {
            const txt = fn.innerText.trim();
            if (txt) footnotes.push(txt);
        });

        // Extract paragraphs with preservation of letters (A, B, C, D, ...)
        const paragraphs = {};
        const rawParagraphs = [];
        const pElements = container.querySelectorAll('p, div.paragraph, .passage-p, li.p-item');

        let currentLabel = 'Intro';
        let unnamedIdx = 1;

        if (pElements.length > 0) {
            pElements.forEach(p => {
                const text = p.innerText.replace(/\\s+/g, ' ').trim();
                if (!text || text.length < 15) return;
                // Exclude if it is footnote
                if (p.closest('.footnote, .glossary')) return;

                // Look for explicit paragraph markers:
                // e.g. "Paragraph A", "[A]", "A.", "A  ", or <b>A</b> at start
                let label = null;
                const strongFirst = p.querySelector('strong, b, span.label, span.paragraph-label');
                if (strongFirst) {
                    const st = strongFirst.innerText.trim();
                    if (/^[A-J]$/i.test(st) || /^(Paragraph\\s+[A-J])$/i.test(st)) {
                        label = st.toUpperCase().replace(/^PARAGRAPH\\s*/i, '');
                    }
                }

                if (!label) {
                    const match = text.match(/^(?:(?:\\[|\\()?\\s*Paragraph\\s+([A-J])(?:\\]|\\)|:)?|^([A-J])[\\.\\:\\s]{1,3})/i);
                    if (match) {
                        label = (match[1] || match[2]).toUpperCase();
                    }
                }

                if (label) {
                    currentLabel = label;
                    // Strip the leading label from paragraph text for clean NLP
                    const cleaned = text.replace(/^(?:(?:\\[|\\()?\\s*Paragraph\\s+[A-J](?:\\]|\\)|:)?|^[A-J][\\.\\:\\s]{1,3})/i, '').trim();
                    paragraphs[currentLabel] = (paragraphs[currentLabel] ? paragraphs[currentLabel] + ' ' : '') + cleaned;
                } else {
                    if (currentLabel === 'Intro' && Object.keys(paragraphs).length > 0) {
                        currentLabel = 'Para_' + unnamedIdx++;
                    }
                    paragraphs[currentLabel] = (paragraphs[currentLabel] ? paragraphs[currentLabel] + ' ' : '') + text;
                }
                rawParagraphs.push(text);
            });
        }

        // Fallback: If no <p> tags with labels were detected, split text by double newline
        if (Object.keys(paragraphs).length === 0) {
            const raw = container.innerText.split(/\\n\\s*\\n/);
            let idx = 0;
            raw.forEach(block => {
                const b = block.replace(/\\s+/g, ' ').trim();
                if (b.length > 30) {
                    const label = String.fromCharCode(65 + idx); // A, B, C...
                    paragraphs[label] = b;
                    rawParagraphs.push(b);
                    idx++;
                }
            });
        }

        return {
            title: title,
            subtitle: subtitle,
            paragraphs: paragraphs,
            footnotes: footnotes,
            full_text: container.innerText.replace(/\\s+/g, ' ').trim()
        };
    }

    // 4. Extract Questions and Group Clusters
    function extractQuestionClusters(container) {
        const items = [];
        // Candidate question wrappers
        const qEls = container.querySelectorAll(
            '.question, .question-item, .item-question, [data-question-id], .q-item, ' +
            'div[class*="question-item"], div[class*="reading-question"], tr.question-row, ' +
            '.exam-question, .group-question'
        );

        if (qEls.length > 0) {
            qEls.forEach((qEl, index) => {
                const text = qEl.innerText.replace(/\\s+/g, ' ').trim();
                if (!text || text.length < 5) return;

                // Detect question number
                let qNum = null;
                const numEl = qEl.querySelector('.q-number, .question-number, .num, b, strong');
                if (numEl) {
                    const nm = numEl.innerText.match(/\\b(\\d{1,3})\\b/);
                    if (nm) qNum = parseInt(nm[1], 10);
                }
                if (!qNum) {
                    const nm = text.match(/^(?:Question|C?u|Q)?\\s*(\\d{1,3})[\\.\\:\\s]/i);
                    if (nm) qNum = parseInt(nm[1], 10);
                }
                if (!qNum) qNum = index + 1;

                // Detect input types inside this question
                const radios = Array.from(qEl.querySelectorAll('input[type="radio"], [role="radio"]'));
                const checkboxes = Array.from(qEl.querySelectorAll('input[type="checkbox"], [role="checkbox"]'));
                const selects = Array.from(qEl.querySelectorAll('select, .custom-select, [role="combobox"]'));
                const textInputs = Array.from(qEl.querySelectorAll('input[type="text"], input:not([type]), textarea, .blank-input'));
                const dropzones = Array.from(qEl.querySelectorAll('.dropzone, [data-droppable], .ui-droppable'));

                // Extract options if multiple choice
                const optionEls = qEl.querySelectorAll('.option, .answer-option, label, [class*="choice"]');
                const options = [];
                optionEls.forEach(opt => {
                    const ot = opt.innerText.replace(/\\s+/g, ' ').trim();
                    if (ot && ot.length > 0 && !options.includes(ot)) options.push(ot);
                });

                items.push({
                    qNum: qNum,
                    text: text,
                    elementSelector: qEl.id ? '#' + qEl.id : null,
                    hasRadio: radios.length > 0,
                    radioCount: radios.length,
                    hasCheckbox: checkboxes.length > 0,
                    checkboxCount: checkboxes.length,
                    hasSelect: selects.length > 0,
                    selectCount: selects.length,
                    hasTextInput: textInputs.length > 0,
                    textInputCount: textInputs.length,
                    hasDropzone: dropzones.length > 0,
                    options: options
                });
            });
        }

        // Detect cluster headers/instructions (e.g. "Questions 1-5", "Choose the correct heading")
        const clusterHeaders = [];
        const headerEls = container.querySelectorAll('h3, h4, h5, .instruction, .group-title, .question-heading, strong, b');
        headerEls.forEach(h => {
            const ht = h.innerText.replace(/\\s+/g, ' ').trim();
            if (/Questions?\\s+\\d+\\s*(?:-|to)\\s*\\d+/i.test(ht) || /Do the following statements agree/i.test(ht) || /Choose the correct heading/i.test(ht) || /Complete the (?:summary|sentences|notes)/i.test(ht)) {
                clusterHeaders.push(ht);
            }
        });

        return {
            totalQuestions: items.length,
            questions: items,
            clusterHeaders: clusterHeaders
        };
    }

    // 5. Detect Passage Tabs (e.g. Passage 1, Passage 2, Passage 3)
    const tabs = [];
    const tabEls = document.querySelectorAll(
        '.passage-tabs button, .passage-tabs a, ul.nav-tabs li, [role="tab"], ' +
        '.section-tab, .part-item, .passage-nav button, .nav-item a'
    );
    tabEls.forEach((t, i) => {
        const text = t.innerText.replace(/\\s+/g, ' ').trim();
        if (text && (text.toLowerCase().includes('passage') || text.toLowerCase().includes('part') || text.toLowerCase().includes('section') || /^[123]$/.test(text))) {
            tabs.push({
                index: i,
                text: text,
                isActive: t.classList.contains('active') || t.getAttribute('aria-selected') === 'true'
            });
        }
    });

    return {
        hasSplitScreen: !!(passageEl && questionEl && passageEl !== questionEl),
        passage: extractPassageData(passageEl),
        questionsData: extractQuestionClusters(questionEl),
        tabs: tabs
    };
};
"""


class DualPaneExtractor:
    """
    Python interface to extract and manage dual-pane exam data.
    Provides structural passage parsing, paragraph caching, and multi-passage tab switching.
    """

    def __init__(self, page: Page):
        self.page = page
        self.cached_passages: Dict[int, Dict[str, Any]] = {}
        self.active_passage_idx: int = 1

    async def extract_current_view(self) -> Dict[str, Any]:
        """Runs client-side script and returns structured dual-pane data."""
        data = await self.page.evaluate(JS_DUAL_PANE_EXTRACTOR)
        return data

    async def get_active_passage(self) -> Dict[str, Any]:
        """Extracts and caches current passage details."""
        data = await self.extract_current_view()
        passage_info = data.get("passage", {})
        self.cached_passages[self.active_passage_idx] = passage_info
        return passage_info

    async def detect_and_traverse_tabs(self) -> List[Dict[str, Any]]:
        """
        Discovers all passage tabs (Passage 1, 2, 3), switches to each sequentially,
        and caches the complete structural paragraph content for every passage.
        """
        initial_data = await self.extract_current_view()
        tabs = initial_data.get("tabs", [])
        if not tabs:
            # Single passage exam
            passage = await self.get_active_passage()
            return [passage]

        passages_list = []
        tab_buttons = await self.page.query_selector_all(
            '.passage-tabs button, .passage-tabs a, ul.nav-tabs li, [role="tab"], '
            '.section-tab, .part-item, .passage-nav button, .nav-item a'
        )

        # Filter tab elements that match passage texts
        valid_tabs: List[ElementHandle] = []
        for btn in tab_buttons:
            txt = (await btn.inner_text()).strip()
            if any(k in txt.lower() for k in ["passage", "part", "section", "b?i ??c"]):
                valid_tabs.append(btn)

        if not valid_tabs:
            passage = await self.get_active_passage()
            return [passage]

        for idx, tab_btn in enumerate(valid_tabs, start=1):
            try:
                txt = (await tab_btn.inner_text()).strip()
                print(f"[Passage] [Passage Navigator] Switching to {txt} (Tab #{idx})...")
                await tab_btn.scroll_into_view_if_needed()
                await tab_btn.click()
                await asyncio.sleep(1.2)  # Wait for DOM/AJAX update

                view_data = await self.extract_current_view()
                passage_info = view_data.get("passage", {})
                self.cached_passages[idx] = passage_info
                passages_list.append(passage_info)
            except Exception as e:
                print(f"[!] [Passage Navigator] Warning switching tab {idx}: {e}")

        # Switch back to Tab 1 to start solving
        if valid_tabs:
            try:
                await valid_tabs[0].click()
                await asyncio.sleep(0.8)
                self.active_passage_idx = 1
            except Exception:
                pass

        return passages_list

    def format_passage_for_prompt(self, passage_data: Dict[str, Any], selected_paragraphs: Optional[List[str]] = None) -> str:
        """
        Formats passage into clean structural text with [Paragraph X] markers
        ready for LLM ingestion without extraneous noise.
        """
        title = passage_data.get("title", "Reading Passage")
        subtitle = passage_data.get("subtitle", "")
        paragraphs = passage_data.get("paragraphs", {})
        footnotes = passage_data.get("footnotes", [])

        lines = [f"# {title}"]
        if subtitle:
            lines.append(f"*{subtitle}*\n")
        else:
            lines.append("")

        for label, text in paragraphs.items():
            if selected_paragraphs and label not in selected_paragraphs:
                continue
            lines.append(f"[{label.upper()}]: {text}\n")

        if footnotes:
            lines.append("### Footnotes & Glossary:")
            for fn in footnotes:
                lines.append(f"- {fn}")

        return "\n".join(lines)
