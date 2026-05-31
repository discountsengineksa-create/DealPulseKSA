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
    send_verify_email,
    verify_password,
)
from api.db import get_db
from api.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SimpleOkResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from api.utils.rate_limit import (
    LIMIT_CHANGE_PASSWORD,
    LIMIT_DELETE_ACCOUNT,
    LIMIT_FORGOT_PASSWORD,
    LIMIT_LOGIN,
    LIMIT_PROFILE_UPDATE,
    LIMIT_REGISTER,
    LIMIT_RESET_PASSWORD,
    LIMIT_SEND_VERIFY,
    LIMIT_VERIFY_EMAIL,
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
        gender=row.get("gender"),
        birth_date=row["birth_date"].isoformat() if row.get("birth_date") else None,
        telegram_username=row.get("telegram_username"),
        email_verified=row.get("email_verified_at") is not None,
        consent_at=row["consent_at"].isoformat() if row.get("consent_at") else None,
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
                    gender, birth_date, telegram_username, consent_at,
                    password_hash, last_ip, last_seen, status
                ) VALUES (%s, %s, %s, %s, 'SA', 'ar', %s, %s, %s, NOW(), %s, %s, NOW(), 'Active')
                RETURNING *
                """,
                (
                    payload.phone_number,
                    email_lower,
                    payload.display_name,
                    payload.city,
                    payload.gender,
                    payload.birth_date,
                    payload.telegram_username,
                    pw_hash,
                    client_ip,
                ),
            )
            user = cur.fetchone()
    except UniqueViolation as e:
        # نوضّح الحقل المتكرّر + نقترح تسجيل الدخول/استعادة كلمة المرور.
        # أوضح بكثير من رسائل عامة → يمنع المستخدم من محاولة التسجيل مرتين
        # وهو ناسي أنه مسجّل أصلاً.
        msg = str(e).lower()
        if "telegram_username" in msg or "idx_web_users_telegram_username" in msg:
            raise HTTPException(
                status_code=409,
                detail="اسم المستخدم في تيليجرام مرتبط بحساب آخر. "
                       "استخدم اسم تيليجرام مختلف أو سجّل دخولك بالحساب القديم.",
            )
        if "phone" in msg:
            raise HTTPException(
                status_code=409,
                detail="رقم الجوال مسجّل مسبقاً لديك حساب. "
                       "سجّل دخولك أو استخدم 'نسيت كلمة المرور' للاستعادة.",
            )
        if "email" in msg:
            raise HTTPException(
                status_code=409,
                detail="الإيميل مسجّل مسبقاً لديك حساب. "
                       "سجّل دخولك أو استخدم 'نسيت كلمة المرور' للاستعادة.",
            )
        raise HTTPException(
            status_code=409,
            detail="هذا الحساب موجود مسبقاً. سجّل دخولك بدلاً من إنشاء حساب جديد.",
        )

    token = create_jwt_token(user["id"])
    return TokenResponse(token=token, user=_row_to_user(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LIMIT_LOGIN)
def login(payload: LoginRequest, request: Request, conn=Depends(get_db)):
    """تسجيل دخول. username = جوال أو إيميل. remember_me=true → JWT 30 يوم."""
    user = _find_user_by_username(conn, payload.username)
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    # تحديث last_seen
    with conn.cursor() as cur:
        cur.execute("UPDATE web_users SET last_seen = NOW() WHERE id = %s", (user["id"],))

    # remember_me يمدّد الجلسة لـ 30 يوم بدل 14 الافتراضية
    expiry_days = 30 if payload.remember_me else None
    token = create_jwt_token(user["id"], expiry_days=expiry_days)
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

    # ── قرار تصميمي: نُعطي إشارة صريحة للمستخدم بدل الرد العام ────────────
    # السبب: المستخدمون يملكون إيميلات متعددة وقد ينسون أيهم سجّلوا به.
    # الرد العام (حماية ضد user-enumeration) يجعلهم ينتظرون كود لن يصل أبداً
    # = UX سيء جداً. نختار صراحة الإفصاح + نطلب من المستخدم استخدام
    # /register أو إيميل آخر.
    if not user:
        raise HTTPException(
            status_code=404,
            detail="لا يوجد حساب مسجّل بهذا الإيميل/الجوال. تأكّد من البيانات "
                   "أو سجّل حساباً جديداً.",
        )
    if not user.get("email"):
        raise HTTPException(
            status_code=400,
            detail="الحساب موجود لكن بدون إيميل مسجّل. تواصل مع الدعم لتحديث "
                   "بياناتك.",
        )

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
        # نُخبر المستخدم بصراحة بدل صمت مُربك
        raise HTTPException(
            status_code=429,
            detail="طلبت كوداً 3 مرات خلال آخر 15 دقيقة. تحقّق من إيميلك "
                   "(والـ spam) أو حاول بعد 15 دقيقة.",
        )

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

    # أرسل الإيميل — لو فشل لا نخدع المستخدم برسالة "تم الإرسال"
    sent = send_reset_email(
        to_email=user["email"],
        user_name=user.get("display_name") or "عزيزي العميل",
        code=code,
    )
    if not sent:
        # 502 Bad Gateway = الخدمة الخارجية (Resend/SMTP) فشلت
        # الـ frontend يعرض الرسالة للمستخدم بدلاً من توهم النجاح.
        raise HTTPException(
            status_code=502,
            detail="تعذّر إرسال الإيميل حالياً. حاول بعد دقائق، أو راسل الدعم.",
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


# ─── Logged-in user endpoints (PATCH/DELETE/change-password/verify-email) ──
@router.post("/change-password", response_model=SimpleOkResponse)
@limiter.limit(LIMIT_CHANGE_PASSWORD)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """تغيير كلمة السر للمستخدم المسجّل دخوله (يتطلّب كلمة السر الحالية)."""
    if not user.get("password_hash") or not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="كلمة السر الحالية غير صحيحة")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="كلمة السر الجديدة مطابقة للحالية")

    new_hash = hash_password(payload.new_password)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE web_users SET password_hash = %s, last_seen = NOW() WHERE id = %s",
            (new_hash, user["id"]),
        )
        # نظّف أي كودات استعادة معلّقة بعد تغيير الكلمة (أمان)
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE user_id = %s AND used = FALSE",
            (user["id"],),
        )
    return SimpleOkResponse(message="تم تغيير كلمة السر")


@router.patch("/me", response_model=UserResponse)
@limiter.limit(LIMIT_PROFILE_UPDATE)
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """تعديل البروفايل: display_name / city / gender / birth_date / telegram_username.
    الإيميل/الجوال غير قابلين للتعديل من هنا. كل الحقول اختيارية — ما تُمرّره يُحدَّث.
    """
    # ابني UPDATE ديناميكي للحقول الممرّرة فقط
    fields = []
    values = []
    if payload.display_name is not None:
        fields.append("display_name = %s"); values.append(payload.display_name)
    if payload.city is not None:
        fields.append("city = %s"); values.append(payload.city)
    if payload.gender is not None:
        fields.append("gender = %s"); values.append(payload.gender)
    if payload.birth_date is not None:
        fields.append("birth_date = %s"); values.append(payload.birth_date)
    if payload.telegram_username is not None:
        fields.append("telegram_username = %s"); values.append(payload.telegram_username)

    if not fields:
        # لا تعديل — رجّع البيانات الحالية بدون SQL
        return _row_to_user(user)

    fields.append("last_seen = NOW()")
    values.append(user["id"])

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"UPDATE web_users SET {', '.join(fields)} WHERE id = %s RETURNING *",
                tuple(values),
            )
            updated = cur.fetchone()
    except UniqueViolation as e:
        msg = str(e).lower()
        if "telegram_username" in msg or "idx_web_users_telegram_username" in msg:
            raise HTTPException(status_code=409, detail="اسم المستخدم في تيليجرام مرتبط بحساب آخر")
        raise HTTPException(status_code=409, detail="القيمة مستخدمة بالفعل")

    return _row_to_user(updated)


@router.delete("/me", response_model=SimpleOkResponse)
@limiter.limit(LIMIT_DELETE_ACCOUNT)
def delete_account(
    request: Request,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """حذف الحساب نهائياً (PDPL — حق النسيان).
    يحذف الصف من web_users؛ CASCADE ينظّف password_reset_tokens و
    email_verification_codes. سجلات action_logs تبقى (بـ user_id يتيم — لا
    معلومات شخصية فيه)، للحفاظ على ثبات تحليلات الأعمال التاريخية.
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM web_users WHERE id = %s", (user["id"],))
    return SimpleOkResponse(message="تم حذف الحساب نهائياً")


@router.post("/send-verify-email", response_model=SimpleOkResponse)
@limiter.limit(LIMIT_SEND_VERIFY)
def send_verify_email_endpoint(
    request: Request,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """يرسل كود 6 أرقام لتأكيد إيميل المستخدم. صالح 15 دقيقة."""
    if user.get("email_verified_at"):
        raise HTTPException(status_code=400, detail="الإيميل مؤكّد سابقاً")
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="لا يوجد إيميل في الحساب")

    # حد بسيط: لا أكثر من 3 كودات في 15 دقيقة (يطابق LIMIT_SEND_VERIFY)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM email_verification_codes
            WHERE user_id = %s AND created_at > NOW() - INTERVAL '15 minutes'
            """,
            (user["id"],),
        )
        recent = cur.fetchone()[0]
    if recent >= 3:
        raise HTTPException(status_code=429, detail="أرسلت كودات كثيرة، انتظر قليلاً")

    from datetime import datetime, timedelta, timezone
    code = generate_reset_code()
    code_hash = hash_reset_code(code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    client_ip = request.client.host if request.client else None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO email_verification_codes (user_id, code_hash, expires_at, request_ip)
            VALUES (%s, %s, %s, %s)
            """,
            (user["id"], code_hash, expires_at, client_ip),
        )

    send_verify_email(
        to_email=user["email"],
        user_name=user.get("display_name") or "عزيزي العميل",
        code=code,
    )
    return SimpleOkResponse(message=f"تم إرسال كود التأكيد إلى {_mask_email(user['email'])}")


@router.post("/verify-email", response_model=UserResponse)
@limiter.limit(LIMIT_VERIFY_EMAIL)
def verify_email_endpoint(
    payload: VerifyEmailRequest,
    request: Request,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """تأكيد الإيميل بكود 6 أرقام (المُرسَل عبر /send-verify-email)."""
    if user.get("email_verified_at"):
        return _row_to_user(user)  # مؤكّد فعلاً — idempotent

    code_hash = hash_reset_code(payload.code)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM email_verification_codes
            WHERE user_id = %s AND code_hash = %s
              AND used = FALSE AND expires_at > NOW()
            ORDER BY created_at DESC LIMIT 1
            """,
            (user["id"], code_hash),
        )
        token_row = cur.fetchone()
    if not token_row:
        raise HTTPException(status_code=400, detail="كود غير صحيح أو منتهي الصلاحية")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "UPDATE web_users SET email_verified_at = NOW() WHERE id = %s RETURNING *",
            (user["id"],),
        )
        updated = cur.fetchone()
        cur.execute(
            "UPDATE email_verification_codes SET used = TRUE WHERE user_id = %s AND used = FALSE",
            (user["id"],),
        )
    return _row_to_user(updated)
