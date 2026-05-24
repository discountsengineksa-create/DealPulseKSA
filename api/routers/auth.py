"""
نقاط نهاية المصادقة:
  POST /api/v1/auth/register          — إنشاء حساب جديد
  POST /api/v1/auth/login             — تسجيل دخول (جوال أو إيميل + كلمة سر)
  GET  /api/v1/auth/me                — بيانات المستخدم الحالي (يحتاج JWT)
  POST /api/v1/auth/forgot-password   — طلب كود استعادة (يُرسل للإيميل)
  POST /api/v1/auth/reset-password    — تأكيد الكود وتعيين كلمة سر جديدة
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from psycopg2.errors import UniqueViolation
from psycopg2.extras import RealDictCursor

from api.auth_utils import (
    create_jwt_token,
    decode_jwt_token,
    generate_reset_code,
    hash_password,
    hash_reset_code,
    send_reset_email,
    verify_password,
)
from api.db import get_db
from api.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from api.utils.rate_limit import (
    LIMIT_FORGOT_PASSWORD,
    LIMIT_LOGIN,
    LIMIT_REGISTER,
    LIMIT_RESET_PASSWORD,
    limiter,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Helpers ────────────────────────────────────────────────────────────────
def _row_to_user(row: dict) -> UserResponse:
    """يحوّل صف من DB إلى UserResponse (يستبعد password_hash)."""
    return UserResponse(
        id=row["id"],
        display_name=row.get("display_name") or "",
        phone_number=row["phone_number"],
        email=row.get("email") or "",
        city=row.get("city"),
        country=row.get("country"),
        lang=row.get("lang") or "ar",
        visited_clicks=row.get("visited_clicks") or 0,
        store_copy_count=row.get("store_copy_count") or 0,
        manual_favorites=list(row.get("manual_favorites") or []),
        created_at=row["created_at"].isoformat() if row.get("created_at") else None,
    )


def _find_user_by_username(conn, username: str) -> dict | None:
    """يبحث عن المستخدم بالجوال أو الإيميل."""
    username = username.strip()
    # نطبّع الجوال نفس الطريقة (لو دخل 05XX أو 5XX)
    phone = username
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if phone.startswith("0"):
        phone = "+966" + phone[1:]
    if phone.startswith("5") and len(phone) == 9:
        phone = "+966" + phone

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM web_users
            WHERE phone_number = %s OR email = %s OR phone_number = %s
            LIMIT 1
            """,
            (username, username.lower(), phone),
        )
        return cur.fetchone()


def _mask_email(email: str) -> str:
    """يخفي الإيميل: ahmed@gmail.com → a***d@gmail.com"""
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked = local[0] + "*"
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"


# ─── JWT Dependency ─────────────────────────────────────────────────────────
def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    conn=Depends(get_db),
) -> dict:
    """
    Dependency يستخرج المستخدم الحالي من Authorization header.
    استخدامه في endpoints محمية: user = Depends(get_current_user)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header malformed")

    token = authorization[7:].strip()
    payload = decode_jwt_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM web_users WHERE id = %s", (user_id,))
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ─── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit(LIMIT_REGISTER)
def register(payload: RegisterRequest, request: Request, conn=Depends(get_db)):
    """إنشاء حساب جديد. يرجع JWT token مباشرة (دخول تلقائي)."""
    pw_hash = hash_password(payload.password)
    client_ip = request.client.host if request.client else None
    email_lower = payload.email.lower()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO web_users (
                    phone_number, email, display_name, city, country, lang,
                    password_hash, last_ip, last_seen, status
                ) VALUES (%s, %s, %s, %s, 'SA', 'ar', %s, %s, NOW(), 'Active')
                RETURNING *
                """,
                (
                    payload.phone_number,
                    email_lower,
                    payload.display_name,
                    payload.city,
                    pw_hash,
                    client_ip,
                ),
            )
            user = cur.fetchone()
    except UniqueViolation as e:
        # PostgreSQL يرجع 'phone_number' أو 'email' في رسالة الخطأ
        msg = str(e).lower()
        if "phone" in msg:
            raise HTTPException(status_code=409, detail="رقم الجوال مسجّل مسبقاً")
        if "email" in msg:
            raise HTTPException(status_code=409, detail="الإيميل مسجّل مسبقاً")
        raise HTTPException(status_code=409, detail="مستخدم موجود مسبقاً")

    token = create_jwt_token(user["id"])
    return TokenResponse(token=token, user=_row_to_user(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LIMIT_LOGIN)
def login(payload: LoginRequest, request: Request, conn=Depends(get_db)):
    """تسجيل دخول. username = جوال أو إيميل."""
    user = _find_user_by_username(conn, payload.username)
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    # تحديث last_seen
    with conn.cursor() as cur:
        cur.execute("UPDATE web_users SET last_seen = NOW() WHERE id = %s", (user["id"],))

    token = create_jwt_token(user["id"])
    return TokenResponse(token=token, user=_row_to_user(user))


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    """بيانات المستخدم الحالي (يحتاج Authorization: Bearer <token>)."""
    return _row_to_user(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit(LIMIT_FORGOT_PASSWORD)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, conn=Depends(get_db)
):
    """
    يرسل كود 6 أرقام للإيميل المسجّل.
    لأمان أكبر: نرجع نفس الرد دائماً (سواء وُجد المستخدم أو لا).
    """
    user = _find_user_by_username(conn, payload.username)
    generic_response = ForgotPasswordResponse(
        message="إذا كان الحساب موجوداً، تم إرسال كود لإيميلك المسجّل."
    )

    if not user or not user.get("email"):
        return generic_response

    # rate-limit بسيط: لا أكثر من 3 طلبات في 15 دقيقة لنفس المستخدم
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM password_reset_tokens
            WHERE user_id = %s AND created_at > NOW() - INTERVAL '15 minutes'
            """,
            (user["id"],),
        )
        recent_count = cur.fetchone()[0]

    if recent_count >= 3:
        # ما نقول للمستخدم بصراحة، بس ما نرسل كود إضافي
        return generic_response

    # ولّد كود + خزّنه
    code = generate_reset_code()
    code_hash = hash_reset_code(code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    client_ip = request.client.host if request.client else None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO password_reset_tokens (user_id, code_hash, expires_at, request_ip)
            VALUES (%s, %s, %s, %s)
            """,
            (user["id"], code_hash, expires_at, client_ip),
        )

    # أرسل الإيميل
    send_reset_email(
        to_email=user["email"],
        user_name=user.get("display_name") or "عزيزي العميل",
        code=code,
    )

    return ForgotPasswordResponse(
        message="تم إرسال كود الاستعادة لإيميلك.",
        email_hint=_mask_email(user["email"]),
    )


@router.post("/reset-password", response_model=TokenResponse)
@limiter.limit(LIMIT_RESET_PASSWORD)
def reset_password(payload: ResetPasswordRequest, request: Request, conn=Depends(get_db)):
    """
    يتحقق من الكود ويعيّن كلمة سر جديدة.
    عند النجاح: يحذف الكود + يرجع JWT جديد (دخول تلقائي).
    """
    user = _find_user_by_username(conn, payload.username)
    if not user:
        raise HTTPException(status_code=400, detail="بيانات غير صحيحة")

    code_hash = hash_reset_code(payload.code)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM password_reset_tokens
            WHERE user_id = %s
              AND code_hash = %s
              AND used = FALSE
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user["id"], code_hash),
        )
        token_row = cur.fetchone()

    if not token_row:
        raise HTTPException(status_code=400, detail="كود غير صحيح أو منتهي الصلاحية")

    # حدّث كلمة السر + علّم الكود مستخدم
    new_hash = hash_password(payload.new_password)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "UPDATE web_users SET password_hash = %s, last_seen = NOW() WHERE id = %s RETURNING *",
            (new_hash, user["id"]),
        )
        updated_user = cur.fetchone()
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE id = %s",
            (token_row["id"],),
        )
        # نظّف بقية الأكواد القديمة لنفس المستخدم
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE user_id = %s AND used = FALSE",
            (user["id"],),
        )

    jwt_token = create_jwt_token(updated_user["id"])
    return TokenResponse(token=jwt_token, user=_row_to_user(updated_user))
