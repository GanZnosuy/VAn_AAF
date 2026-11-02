"""
Specialized Platform Adapter for Long-Form Foreign Language Exams
(IELTS, TOEFL, TOEIC, VSTEP, SAT Reading/Writing) on split-screen web platforms
(STUDY4, YouPass, IELTS Online Tests, Mini-IELTS, Canvas, Moodle, Exam Portals).
"""

import asyncio
from typing import List, Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.solver.linguistic_runner import LinguisticExamRunner


class LanguageExamAdapter(BasePlatformAdapter):
    """
    Platform Adapter for Foreign Language Exams.
    Features:
    - Dual-pane DOM extraction (Reading passage left, Questions right).
    - Structural paragraph indexing ([Paragraph A], [Paragraph B]).
    - Clustered batch inference (4-7 questions per cluster, zero context truncation).
    - Specialized solvers (TFNG evidence citation, Matching Headings elimination matrix, Gap-fill word limits).
    - Multi-type resilient element injection and session progress persistence.
    """
    name = "Linguistic Exam Solver (IELTS/TOEFL/TOEIC/VSTEP/SAT)"
    supported_domains: List[str] = [
        "study4.com",
        "youpass.vn",
        "ieltsonlinetests.com",
        "mini-ielts.com",
        "testglider.com",
        "englishteststore.net",
        "canvas",
        "moodle",
        "ielts",
        "toefl",
        "toeic",
        "vstep",
        "sat"
    ]

    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        runner = LinguisticExamRunner(
            page=page,
            ai_client=ai,
            rate_limit_delay=2.5,
            session_file="session_progress.json"
        )

        success = await runner.run(test_url)

        if screenshot_name:
            try:
                await page.screenshot(path=screenshot_name, full_page=True)
                print(f"? [LanguageExamAdapter] Saved result screenshot to: {screenshot_name}")
            except Exception as e:
                print(f"?? [LanguageExamAdapter] Screenshot failed: {e}")

        return success
