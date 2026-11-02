"""
Resilient Multi-Type DOM Interaction Engine.
Handles universal element dispatch across modern web exam interfaces
(React, Vue, Angular, Svelte, Moodle, Canvas, STUDY4, YouPass).

Features:
- Radio & Checkbox: scrollIntoViewIfNeeded, label clicking, synthetic click dispatch.
- Dropdown Selects: Native <select> with change events + custom div/span dropdown popups.
- Text Inputs / Gap-Fills: React 16+ synthetic property descriptor setter, input/change/blur dispatch.
- Drag & Drop: Playwright drag_to with synthetic DataTransfer fallback.
- Session Progress Persistence: Auto-save & resume via session_progress.json.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from playwright.async_api import Page, ElementHandle, Locator


class SessionProgressManager:
    """
    Manages session progress state persistence and recovery across browser reloads or network drops.
    """
    def __init__(self, filepath: Optional[str] = None):
        self.filepath = Path(filepath or "session_progress.json")
        self.state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.filepath.exists() and self.filepath.stat().st_size > 0:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] [SessionManager] Could not read existing session: {e}")
        return {
            "exam_url": "",
            "passages_cached": [],
            "solved_questions": {},
            "total_solved": 0
        }

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] [SessionManager] Failed to save session progress: {e}")

    def is_solved(self, q_num: int) -> bool:
        q_str = str(q_num)
        return q_str in self.state.get("solved_questions", {}) and self.state["solved_questions"][q_str].get("injected", False)

    def record_answer(self, q_num: int, q_type: str, answer: Any, confidence: float = 0.95, injected: bool = True):
        if "solved_questions" not in self.state:
            self.state["solved_questions"] = {}
        self.state["solved_questions"][str(q_num)] = {
            "type": q_type,
            "answer": answer,
            "confidence": confidence,
            "injected": injected
        }
        self.state["total_solved"] = len(self.state["solved_questions"])
        self.save()


class ElementDispatcher:
    """
    Universal dispatcher for injecting answers into complex, dynamic DOM components.
    """
    def __init__(self, page: Page):
        self.page = page

    # =========================================================================
    # 1. RADIO BUTTONS & MULTIPLE CHOICE
    # =========================================================================
    async def inject_radio_choice(self, question_container: Union[ElementHandle, Locator, None], chosen_letter: str) -> bool:
        """
        Clicks the target radio or option label for a chosen letter (A, B, C, D, etc.).
        Handles hidden input radios, custom div options, and label elements.
        """
        chosen_letter = chosen_letter.strip().upper()
        letter_idx = ord(chosen_letter) - 65  # A=0, B=1, C=2, D=3

        root = question_container if question_container else self.page

        try:
            selectors = [
                f"input[type='radio'][value='{chosen_letter}']",
                f"input[type='radio'][value='{letter_idx}']",
                f".option:has-text('{chosen_letter}.')",
                f".option:has-text('{chosen_letter})')",
                f"label:has-text('{chosen_letter}.')",
                f"label:has-text('{chosen_letter})')",
                f"[data-option='{chosen_letter}']",
                f"[data-value='{chosen_letter}']",
                f".question-option:nth-of-type({letter_idx + 1})",
                f"label:nth-of-type({letter_idx + 1})"
            ]

            for s in selectors:
                target = await root.query_selector(s) if hasattr(root, "query_selector") else await self.page.query_selector(s)
                if target:
                    await target.scroll_into_view_if_needed()
                    await asyncio.sleep(0.15)
                    try:
                        await target.click(timeout=2000)
                        return True
                    except Exception:
                        await target.evaluate("el => el.click()")
                        return True

            all_options = await root.query_selector_all(".option, .question-option, .choice, label, input[type='radio']") if hasattr(root, "query_selector_all") else await self.page.query_selector_all(".option, .question-option, label")
            if all_options and 0 <= letter_idx < len(all_options):
                opt = all_options[letter_idx]
                await opt.scroll_into_view_if_needed()
                await opt.click(force=True)
                return True

        except Exception as e:
            print(f"[!] [Dispatcher] Radio injection error for {chosen_letter}: {e}")

        return False

    # =========================================================================
    # 2. CHECKBOXES & MULTI-SELECT
    # =========================================================================
    async def inject_checkbox_multi(self, question_container: Union[ElementHandle, Locator, None], chosen_letters: List[str]) -> bool:
        """
        Clicks multiple checkboxes for questions requiring multiple answers (e.g. Choose TWO letters).
        """
        root = question_container if question_container else self.page
        success_count = 0

        for letter in chosen_letters:
            letter = letter.strip().upper()
            letter_idx = ord(letter) - 65

            try:
                selectors = [
                    f"input[type='checkbox'][value='{letter}']",
                    f".option:has-text('{letter}.')",
                    f"label:has-text('{letter}.')",
                    f"label:has-text('{letter})')",
                    f"[data-option='{letter}']",
                    f"input[type='checkbox']:nth-of-type({letter_idx + 1})"
                ]
                clicked = False
                for s in selectors:
                    target = await root.query_selector(s) if hasattr(root, "query_selector") else await self.page.query_selector(s)
                    if target:
                        await target.scroll_into_view_if_needed()
                        await asyncio.sleep(0.1)
                        await target.click(force=True)
                        clicked = True
                        success_count += 1
                        break

                if not clicked:
                    cbs = await root.query_selector_all("input[type='checkbox'], .checkbox, label") if hasattr(root, "query_selector_all") else []
                    if 0 <= letter_idx < len(cbs):
                        await cbs[letter_idx].scroll_into_view_if_needed()
                        await cbs[letter_idx].click(force=True)
                        success_count += 1
            except Exception as e:
                print(f"[!] [Dispatcher] Checkbox click failed for {letter}: {e}")

        return success_count > 0

    # =========================================================================
    # 3. TEXT INPUTS & FILL-IN-THE-BLANKS (REACT/VUE PROTOTYPE OVERRIDES)
    # =========================================================================
    async def inject_text_input(
        self,
        question_container: Union[ElementHandle, Locator, None],
        answer_text: str,
        input_index: int = 0
    ) -> bool:
        """
        Fills input fields while properly firing synthetic events required by
        React 16+, Vue 3, and Angular change detection.
        """
        root = question_container if question_container else self.page
        answer_text = str(answer_text).strip()

        try:
            inputs = await root.query_selector_all("input[type='text'], input:not([type]), textarea, [contenteditable='true']") if hasattr(root, "query_selector_all") else await self.page.query_selector_all("input[type='text'], input:not([type]), textarea")
            if not inputs:
                inputs = await self.page.query_selector_all("input[type='text'], input:not([type]), textarea")

            if not inputs or input_index >= len(inputs):
                print(f"[!] [Dispatcher] No input element found at index {input_index}")
                return False

            target_input = inputs[input_index]
            await target_input.scroll_into_view_if_needed()
            await target_input.click()
            await asyncio.sleep(0.1)

            script = """(el, val) => {
                el.focus();
                const prototype = window.HTMLInputElement.prototype;
                const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
                if (descriptor && descriptor.set) {
                    descriptor.set.call(el, val);
                } else {
                    el.value = val;
                }
                el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true, cancelable: true }));
                return el.value === val;
            }"""

            success = await target_input.evaluate(script, answer_text)
            await asyncio.sleep(0.15)
            return bool(success)

        except Exception as e:
            print(f"[!] [Dispatcher] Failed to inject text '{answer_text}': {e}")
            return False

    # =========================================================================
    # 4. DROPDOWN SELECTS (NATIVE & CUSTOM DIV MENUS)
    # =========================================================================
    async def inject_dropdown_selection(
        self,
        question_container: Union[ElementHandle, Locator, None],
        value_or_text: str,
        dropdown_index: int = 0
    ) -> bool:
        """
        Handles both native <select> elements and modern custom div/span dropdowns
        (e.g., Ant Design, Vuetify, Bootstrap, custom IELTS selects).
        """
        root = question_container if question_container else self.page
        target_val = str(value_or_text).strip()

        try:
            selects = await root.query_selector_all("select") if hasattr(root, "query_selector_all") else []
            if selects and dropdown_index < len(selects):
                sel = selects[dropdown_index]
                await sel.scroll_into_view_if_needed()
                try:
                    await sel.select_option(label=target_val, timeout=2000)
                    return True
                except Exception:
                    try:
                        await sel.select_option(value=target_val, timeout=2000)
                        return True
                    except Exception:
                        await sel.evaluate("""(el, val) => {
                            for (let opt of el.options) {
                                if (opt.text.toLowerCase().includes(val.toLowerCase()) || opt.value.toLowerCase() === val.toLowerCase()) {
                                    el.value = opt.value;
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    return true;
                                }
                            }
                            return false;
                        }""", target_val)
                        return True

            custom_menus = await root.query_selector_all(".custom-select, [role='combobox'], .select-dropdown, .dropdown-toggle, .v-select, .ant-select") if hasattr(root, "query_selector_all") else []
            if custom_menus and dropdown_index < len(custom_menus):
                menu_btn = custom_menus[dropdown_index]
                await menu_btn.scroll_into_view_if_needed()
                await menu_btn.click()
                await asyncio.sleep(0.4)

                option_selectors = [
                    f"[role='option']:has-text('{target_val}')",
                    f".dropdown-item:has-text('{target_val}')",
                    f"li:has-text('{target_val}')",
                    f".select-option:has-text('{target_val}')"
                ]
                for os_sel in option_selectors:
                    opt = await self.page.query_selector(os_sel)
                    if opt:
                        await opt.click()
                        await asyncio.sleep(0.2)
                        return True

        except Exception as e:
            print(f"[!] [Dispatcher] Dropdown injection error for '{target_val}': {e}")

        return False

    # =========================================================================
    # 5. DRAG & DROP / REORDERING
    # =========================================================================
    async def inject_drag_and_drop(
        self,
        source_text_or_selector: str,
        target_zone_selector: str
    ) -> bool:
        """
        Performs HTML5 drag-and-drop or coordinate mouse drag between source and target elements.
        """
        try:
            source = await self.page.query_selector(source_text_or_selector)
            if not source:
                source = await self.page.query_selector(f":has-text('{source_text_or_selector}')")
            target = await self.page.query_selector(target_zone_selector)

            if source and target:
                await source.scroll_into_view_if_needed()
                await target.scroll_into_view_if_needed()

                try:
                    await source.drag_to(target, timeout=4000)
                    await asyncio.sleep(0.4)
                    return True
                except Exception:
                    await self.page.evaluate("""([src, dst]) => {
                        const dataTransfer = new DataTransfer();
                        src.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer }));
                        dst.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer }));
                        dst.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer }));
                        src.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true, dataTransfer }));
                    }""", [source, target])
                    await asyncio.sleep(0.4)
                    return True
        except Exception as e:
            print(f"[!] [Dispatcher] Drag and drop error: {e}")

        return False
