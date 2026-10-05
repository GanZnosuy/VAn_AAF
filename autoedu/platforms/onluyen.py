from typing import Optional
from playwright.async_api import Page
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.ai.gemini_web import GeminiWebClient
from autoedu.solver.runner import solve_test_url

class OnluyenAdapter(BasePlatformAdapter):
    """Adapter chuyên biệt cho nền tảng Onluyen.vn (Angular SPA, MathML, 3 phần thi)."""
    name = "Onluyen.vn"
    supported_domains = ["onluyen.vn", "app.onluyen.vn"]

    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        return await solve_test_url(page, test_url, ai_client=ai, screenshot_name=screenshot_name)
