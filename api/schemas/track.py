from typing import Literal, Optional
from pydantic import BaseModel, Field


class TrackRequest(BaseModel):
    """طلب تسجيل حدث.

    user_id       : اختياري — مستخدم معروف (telegram_id للبوت / web_users.id للموقع / null للزوار).
    source        : 'bot' | 'web' | 'dashboard' — مصدر الحدث (لتقارير منفصلة).
    event_id      : اختياري — يُسمح للعميل بتمرير UUID للحماية من تكرار الحدث
                    عند إعادة المحاولة. لو لم يُمرَّر، الـ Cloudflare Worker
                    (أو السيرفر) يولّد واحد.
    story_view_id : اختياري — UUID من story_views.view_id لو الحدث نشأ من
                    داخل ستوري (نسخ/زيارة من فيوور الستوري).
    """
    user_id: Optional[int] = Field(None, ge=0, description="ID المستخدم (telegram_id أو web_users.id)")
    store_id: str = Field(..., min_length=1, max_length=200)
    action: Literal["click_link", "copy_coupon", "search"]
    details: Optional[str] = Field(None, max_length=500)
    source: Literal["bot", "web", "dashboard", "telegram_miniapp"] = "web"
    event_id: Optional[str] = Field(None, max_length=64, description="UUID اختياري لحماية الـ idempotency")
    story_view_id: Optional[str] = Field(None, max_length=64, description="UUID story_views.view_id لو الحدث من داخل ستوري")


class TrackResponse(BaseModel):
    ok: bool
    action: str
    store_id: str
    source: str


class SetLangRequest(BaseModel):
    """تحديث لغة المستخدم المفضّلة (آخر اختيار) — مصدر الحقيقة لإرسال
    المنشورات/الإيميلات بلغته. لا فحص دوري؛ نعتمد آخر قيمة دائماً.

    web                 → user_id (web_users.id) → web_users.lang
    telegram_miniapp/bot → tg_user_id (telegram_id) → bot_users.lang
    """
    lang:       Literal["ar", "en"]
    source:     Literal["web", "telegram_miniapp", "bot"] = "web"
    user_id:    Optional[int] = Field(None, ge=0, description="web_users.id (للموقع)")
    tg_user_id: Optional[int] = Field(None, ge=0, description="telegram_id (للبوت/الميني)")


class SetLangResponse(BaseModel):
    ok: bool
    lang: str
    source: str


class CategoryViewRequest(BaseModel):
    """تسجيل اهتمام صريح بقسم (view_tag) — بلا متجر.

    يُطلَق عند: نقر تايل القسم في صفحة الأقسام · اختيار قسم في فلتر المتاجر ·
    نقر تاق قسم داخل صفحة متجر. يوحّد عُرف البوت (action_type='view_tag',
    details='tag:<اسم>', store_id=NULL) عبر كل المنصات.
    """
    tag:     str = Field(..., min_length=1, max_length=120, description="اسم القسم")
    source:  Literal["web", "telegram_miniapp", "bot", "dashboard"] = "web"
    user_id: Optional[int] = Field(None, ge=0, description="telegram_id أو web_users.id لو معروف")


class CategoryViewResponse(BaseModel):
    ok: bool
    tag: str


class SearchLogRequest(BaseModel):
    """تسجيل بحث في direct_search (للتحليلات وكشف فجوات المحتوى)."""
    keyword: str = Field(..., min_length=1, max_length=200)
    user_found: bool = False
    store_id: Optional[str] = None
    name_en: Optional[str] = None
    platform: Literal["Web", "Bot", "Dashboard", "Miniapp"] = "Web"
    user_email: Optional[str] = None
    user_id: Optional[int] = None


class SearchLogResponse(BaseModel):
    ok: bool
    keyword: str


class CodeRequestRequest(BaseModel):
    """طلب من العميل لتوفير كود متجر غير موجود حالياً."""
    brand_name: str = Field(..., min_length=1, max_length=200, description="اسم المتجر/البراند المطلوب")
    user_email: Optional[str] = Field(None, max_length=200, description="إيميل العميل للموقع")
    user_id: Optional[int] = Field(None, ge=0, description="telegram_id لو الطلب من البوت")


class CodeRequestResponse(BaseModel):
    ok: bool
    request_id: int
    brand_name: str


# ─── بلاغات «الكود لا يعمل» (Migration 029) ────────────────────────────────
class ReportCodeRequest(BaseModel):
    """بلاغ من عميل مسجّل بأن كود متجر معيّن لا يعمل.

    شروط:
      - web              : web_user_id ملزم.
      - telegram_miniapp : tg_user_id ملزم (telegram_id).
      - bot              : tg_user_id ملزم.
    لا بلاغات مجهولة. التحقّق يتم في الـ endpoint.
    """
    store_id:     str  = Field(..., min_length=1, max_length=200)
    source:       Literal["web", "telegram_miniapp", "bot"]
    web_user_id:  Optional[int] = Field(None, ge=1, description="web_users.id للموقع")
    tg_user_id:   Optional[int] = Field(None, ge=1, description="telegram_id للبوت/الميني-ويب")
    issue_note:   Optional[str] = Field(None, max_length=500, description="ملاحظة اختيارية من العميل")


class ReportCodeResponse(BaseModel):
    ok: bool
    report_id: int
    auto_suspended: bool = Field(
        ..., description="هل سحب هذا البلاغ المتجرَ تلقائياً (10/60min)"
    )


# ─── فتح ستوري (Migration 029) ─────────────────────────────────────────────
class StoryViewRequest(BaseModel):
    """تسجيل فتحة ستوري لمسجّل فقط.

    العميل يولّد view_id (UUID v4) ويُمرّره مع كل نسخ/زيارة لاحقاً في نفس
    الفتحة عبر /track.story_view_id حتى نربط الـ engagement بالستوري.
    """
    view_id:     str  = Field(..., min_length=36, max_length=36, description="UUID v4 يولّده العميل")
    store_id:    str  = Field(..., min_length=1, max_length=200)
    source:      Literal["web", "telegram_miniapp"]
    web_user_id: Optional[int] = Field(None, ge=1)
    tg_user_id:  Optional[int] = Field(None, ge=1)


class StoryViewResponse(BaseModel):
    ok: bool
    view_id: str
