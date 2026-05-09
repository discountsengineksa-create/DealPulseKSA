from typing import Literal, Optional
from pydantic import BaseModel, Field


class TrackRequest(BaseModel):
    """طلب تسجيل حدث.

    user_id  : اختياري — مستخدم معروف (telegram_id للبوت / web_users.id للموقع / null للزوار).
    source   : 'bot' | 'web' | 'dashboard' — مصدر الحدث (لتقارير منفصلة).
    """
    user_id: Optional[int] = Field(None, ge=0, description="ID المستخدم (telegram_id أو web_users.id)")
    store_id: str = Field(..., min_length=1, max_length=200)
    action: Literal["click_link", "copy_coupon", "search"]
    details: Optional[str] = Field(None, max_length=500)
    source: Literal["bot", "web", "dashboard"] = "web"


class TrackResponse(BaseModel):
    ok: bool
    action: str
    store_id: str
    source: str


class SearchLogRequest(BaseModel):
    """تسجيل بحث في direct_search (للتحليلات وكشف فجوات المحتوى)."""
    keyword: str = Field(..., min_length=1, max_length=200)
    user_found: bool = False
    store_id: Optional[str] = None
    name_en: Optional[str] = None
    platform: Literal["Web", "Bot", "Dashboard"] = "Web"


class SearchLogResponse(BaseModel):
    ok: bool
    keyword: str
