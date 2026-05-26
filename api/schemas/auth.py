"""Pydantic schemas للمصادقة."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Register ──────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    """طلب إنشاء حساب جديد."""
    display_name: str = Field(..., min_length=2, max_length=100, description="الاسم الكامل")
    phone_number: str = Field(..., description="رقم الجوال (يقبل 5XXXXXXXX أو +9665XXXXXXXX)")
    email: EmailStr = Field(..., description="الإيميل")
    password: str = Field(..., min_length=8, max_length=128, description="كلمة المرور (8 أحرف على الأقل)")
    city: str = Field(..., min_length=2, max_length=50, description="المدينة")

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
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
        # تحقق نهائي: +966 ثم 9 أرقام
        if not (v.startswith("+966") and len(v) == 13 and v[1:].isdigit()):
            raise ValueError("رقم جوال سعودي غير صحيح. يجب أن يكون +9665XXXXXXXX")
        return v

    @field_validator("display_name", "city")
    @classmethod
    def trim_strings(cls, v: str) -> str:
        return v.strip()


class TokenResponse(BaseModel):
    """رد ناجح من register/login يحتوي على الـ JWT."""
    token: str
    user: "UserResponse"


# ─── Login ─────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    """طلب تسجيل دخول."""
    username: str = Field(..., min_length=3, max_length=200, description="جوال أو إيميل")
    password: str = Field(..., min_length=1, max_length=128)


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
    new_password: str = Field(..., min_length=8, max_length=128)


# Forward ref resolution
TokenResponse.model_rebuild()
