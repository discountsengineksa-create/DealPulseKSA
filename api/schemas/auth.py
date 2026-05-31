"""Pydantic schemas للمصادقة."""
import re
from datetime import date, timedelta
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Helpers ───────────────────────────────────────────────────────────────
_TG_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{4,31}$")


def _normalize_telegram_username(v: Optional[str]) -> Optional[str]:
    """يطبّع اسم تيليجرام: يزيل @ ويحوّل lowercase ويتحقق من الشكل.
    NULL/فارغ → None. شكل غير صحيح → ValueError."""
    if v is None:
        return None
    v = str(v).strip().lstrip("@").lower()
    if not v:
        return None
    if not _TG_USERNAME_RE.match(v):
        raise ValueError(
            "اسم مستخدم تيليجرام غير صحيح. الشكل: يبدأ بحرف، 5-32 حرفاً، "
            "أحرف/أرقام/_ فقط (بدون @)."
        )
    return v


def _validate_age_range(v: date) -> date:
    """العمر 10-100 سنة (يطابق CHECK في DB)."""
    today = date.today()
    min_date = today - timedelta(days=100 * 365)
    max_date = today - timedelta(days=10 * 365)
    if v > max_date:
        raise ValueError("العمر يجب أن يكون 10 سنوات على الأقل")
    if v < min_date:
        raise ValueError("تاريخ الميلاد غير منطقي")
    return v


def _normalize_phone(v: str) -> str:
    """يحوّل الجوال للصيغة الموحّدة: +9665XXXXXXXX"""
    v = v.strip().replace(" ", "").replace("-", "")
    if v.startswith("00"):
        v = "+" + v[2:]
    if v.startswith("0"):
        v = "+966" + v[1:]
    if v.startswith("5") and len(v) == 9:
        v = "+966" + v
    if not v.startswith("+"):
        v = "+" + v
    if not (v.startswith("+966") and len(v) == 13 and v[1:].isdigit()):
        raise ValueError("رقم جوال سعودي غير صحيح. يجب أن يكون +9665XXXXXXXX")
    return v


# ─── Register ──────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    """طلب إنشاء حساب جديد."""
    display_name: str = Field(..., min_length=2, max_length=100, description="الاسم الكامل")
    phone_number: str = Field(..., description="رقم الجوال (يقبل 5XXXXXXXX أو +9665XXXXXXXX)")
    email: EmailStr = Field(..., description="الإيميل")
    password: str = Field(..., min_length=6, max_length=128, description="كلمة المرور (6 أحرف على الأقل)")
    city: str = Field(..., min_length=2, max_length=50, description="المدينة")
    gender: Literal["male", "female"] = Field(..., description="الجنس: male أو female")
    birth_date: date = Field(..., description="تاريخ الميلاد (YYYY-MM-DD)")
    consent: bool = Field(..., description="موافقة PDPL على سياسة الخصوصية (إلزامي)")
    telegram_username: Optional[str] = Field(
        None,
        max_length=33,
        description="اختياري: اسم مستخدم تيليجرام (لربط الحساب مع نشاطك في البوت)",
    )

    @field_validator("phone_number")
    @classmethod
    def _phone(cls, v: str) -> str:
        return _normalize_phone(v)

    @field_validator("display_name", "city")
    @classmethod
    def _trim(cls, v: str) -> str:
        return v.strip()

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, v: date) -> date:
        return _validate_age_range(v)

    @field_validator("consent")
    @classmethod
    def _consent_must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("يجب الموافقة على سياسة الخصوصية قبل إنشاء الحساب")
        return v

    @field_validator("telegram_username")
    @classmethod
    def _tg(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_telegram_username(v)


class TokenResponse(BaseModel):
    """رد ناجح من register/login يحتوي على الـ JWT."""
    token: str
    user: "UserResponse"


# ─── Login ─────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    """طلب تسجيل دخول. remember_me=True يمدّد الجلسة لـ 30 يوم بدل 14 الافتراضية."""
    username: str = Field(..., min_length=3, max_length=200, description="جوال أو إيميل")
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = Field(False, description="تذكّرني — جلسة 30 يوم بدل 14")


# ─── User ──────────────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    """بيانات المستخدم (بدون كلمة السر)."""
    id: int
    display_name: str
    phone_number: str
    email: str
    city: Optional[str] = None
    country: Optional[str] = "SA"
    lang: str = "ar"
    gender: Optional[Literal["male", "female"]] = None
    birth_date: Optional[str] = None  # ISO YYYY-MM-DD
    telegram_username: Optional[str] = None
    email_verified: bool = False
    consent_at: Optional[str] = None  # ISO datetime
    visited_clicks: int = 0
    store_copy_count: int = 0
    manual_favorites: list[str] = []
    created_at: Optional[str] = None


# ─── Forgot Password ───────────────────────────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    """طلب استعادة كلمة المرور."""
    username: str = Field(..., min_length=3, max_length=200, description="جوال أو إيميل المستخدم")


class ForgotPasswordResponse(BaseModel):
    """رد عام (لا نكشف هل المستخدم موجود فعلاً لأمان أكبر)."""
    message: str
    email_hint: Optional[str] = None  # مثلاً: 'a***@gmail.com' (للتأكد فقط)


# ─── Reset Password ────────────────────────────────────────────────────────
class ResetPasswordRequest(BaseModel):
    """تغيير كلمة المرور بالكود."""
    username: str = Field(..., min_length=3, max_length=200)
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(..., min_length=6, max_length=128)


# ─── Change Password (logged-in user) ──────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    """تغيير كلمة السر للمستخدم المسجّل دخوله."""
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


# ─── Profile Update ────────────────────────────────────────────────────────
class ProfileUpdateRequest(BaseModel):
    """تعديل بيانات الحساب — كل الحقول اختيارية، عدّل ما تبيه فقط.
    الإيميل/الجوال غير قابلين للتعديل من هنا (يحتاجان flow إعادة تحقق منفصل)."""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    city: Optional[str] = Field(None, min_length=2, max_length=50)
    gender: Optional[Literal["male", "female"]] = None
    birth_date: Optional[date] = None
    telegram_username: Optional[str] = Field(None, max_length=33)

    @field_validator("display_name", "city")
    @classmethod
    def _trim(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, v: Optional[date]) -> Optional[date]:
        return _validate_age_range(v) if v is not None else None

    @field_validator("telegram_username")
    @classmethod
    def _tg(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_telegram_username(v)


# ─── Email Verification ────────────────────────────────────────────────────
class VerifyEmailRequest(BaseModel):
    """تأكيد الإيميل بالكود (6 أرقام)."""
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class SimpleOkResponse(BaseModel):
    ok: bool = True
    message: Optional[str] = None


# Forward ref resolution
TokenResponse.model_rebuild()
