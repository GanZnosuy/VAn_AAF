from typing import List, Type
from autoedu.platforms.base import BasePlatformAdapter
from autoedu.platforms.onluyen import OnluyenAdapter
from autoedu.platforms.azota import AzotaAdapter
from autoedu.platforms.k12online import K12OnlineAdapter
from autoedu.platforms.google_forms import GoogleFormsAdapter
from autoedu.platforms.universal import UniversalAdapter

REGISTERED_PLATFORMS: List[Type[BasePlatformAdapter]] = [
    OnluyenAdapter,
    AzotaAdapter,
    K12OnlineAdapter,
    GoogleFormsAdapter,
]

def get_platform_adapter(url: str) -> BasePlatformAdapter:
    """
    Tự động phân tích URL bài thi và chọn Adapter chuyên biệt phù hợp:
    - Onluyen.vn (app.onluyen.vn, onluyen.vn)
    - Azota (azota.vn)
    - K12Online (k12online.vn)
    - Google Forms (docs.google.com/forms, forms.gle)
    - Universal Web Solver (Mọi trang web khảo thí, LMS khác)
    """
    for p_cls in REGISTERED_PLATFORMS:
        if p_cls.matches_url(url):
            return p_cls()
    # Mặc định sử dụng Universal Adapter nếu trang web lạ
    return UniversalAdapter()

__all__ = [
    "BasePlatformAdapter",
    "OnluyenAdapter",
    "AzotaAdapter",
    "K12OnlineAdapter",
    "GoogleFormsAdapter",
    "UniversalAdapter",
    "get_platform_adapter"
]
