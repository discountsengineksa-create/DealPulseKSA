"""Schemas للـ /users endpoints (المفضلة + بروفايل تيليجرام)."""
from datetime import date, timedelta
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class FavoriteRequest(BaseModel):
    store_id: str = Field(..., min_length=1, max_length=200)


class FavoritesResponse(BaseModel):
    favorites: List[str]


# ─── Category Favorites (web + telegram) ───────────────────────────────────
# الأقسام نصوص حرة من master.store_tags. نحدّ الطول لتفادي abuse.
class CategoryFavoriteRequest(BaseModel):
    """إضافة/حذف قسم من مفضلة مستخدم ويب (JWT)."""
    category_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("category_name")
    @classmethod
    def trim_category(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("category_name cannot be empty")
        return s


class CategoryFavoritesResponse(BaseModel):
    categories: List[str]


# ─── Telegram Mini-App Favorites (initData-authenticated) ──────────────────
class TelegramFavoriteRequest(BaseModel):
    """إضافة/حذف متجر من مفضلة مستخدم الميني-ويب — يتحقق من initData."""
    init_data: str = Field(..., min_length=10, description="Telegram WebApp initData الخام")
    store_id: str = Field(..., min_length=1, max_length=200)


class TelegramFavoritesListRequest(BaseModel):
    """جلب قائمة مفضلة مستخدم الميني-ويب — يحتاج initData فقط."""
    init_data: str = Field(..., min_length=10)


class TelegramCategoryFavoriteRequest(BaseModel):
    """إضافة/حذف قسم من مفضلة مستخدم الميني-ويب أو البوت."""
    init_data: str = Field(..., min_length=10)
    category_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("category_name")
    @classmethod
    def trim_category(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("category_name cannot be empty")
        return s


# ─── Telegram Mini-App Profile (gender + birth_date) ───────────────────────
class TelegramProfileStatusRequest(BaseModel):
    """يطلب حالة بروفايل المستخدم — يحتاج initData فقط."""
    init_data: str = Field(..., min_length=10, description="Telegram WebApp initData الخام")


class TelegramProfileStatusResponse(BaseModel):
    """يرجّع إن كان البروفايل مكتمل أو يحتاج تعبئة."""
    telegram_id: int
    has_demographics: bool
    gender: Optional[Literal["male", "female"]] = None
    birth_date: Optional[str] = None  # ISO YYYY-MM-DD


class TelegramProfileSaveRequest(BaseModel):
    """حفظ gender + birth_date للمستخدم (يتحقق من initData قبل الحفظ)."""
    init_data: str = Field(..., min_length=10)
    gender: Literal["male", "female"] = Field(...)
    birth_date: date = Field(...)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v: date) -> date:
        """العمر 10–100 سنة (يطابق CHECK في DB)."""
        today = date.today()
        min_date = today - timedelta(days=100 * 365)
        max_date = today - timedelta(days=10 * 365)
        if v > max_date:
            raise ValueError("العمر يجب أن يكون 10 سنوات على الأقل")
        if v < min_date:
            raise ValueError("تاريخ الميلاد غير منطقي")
        return v
