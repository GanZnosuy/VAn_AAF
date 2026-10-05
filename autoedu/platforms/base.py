from abc import ABC, abstractmethod
from typing import List, Optional
from playwright.async_api import Page
from autoedu.ai.gemini_web import GeminiWebClient

class BasePlatformAdapter(ABC):
    """
    Lớp cơ sở trừu tượng cho tất cả các nền tảng thi & bài tập trực tuyến.
    Mọi nền tảng (Onluyen, Azota, K12Online, Olm, Google Forms...) kế thừa từ lớp này.
    """
    name: str = "Base Platform"
    supported_domains: List[str] = []

    @classmethod
    def matches_url(cls, url: str) -> bool:
        """Kiểm tra xem URL bài thi có thuộc nền tảng này hay không."""
        return any(domain.lower() in url.lower() for domain in cls.supported_domains)

    @abstractmethod
    async def solve_test(
        self,
        page: Page,
        test_url: str,
        ai: GeminiWebClient,
        screenshot_name: Optional[str] = None
    ) -> bool:
        """
        Thực hiện toàn bộ quy trình:
        1. Mở trang bài thi và đăng nhập nếu cần
        2. Nhận diện cấu trúc đề bài & bóc tách câu hỏi
        3. Dùng AI suy luận đáp án chính xác
        4. Tương tác điền đáp án
        5. Nộp bài và lưu ảnh chụp kết quả
        """
        pass
