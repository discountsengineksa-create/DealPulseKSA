"""
أدوات المصادقة: تشفير كلمات السر، JWT tokens، إرسال إيميل.
"""
import hashlib
import os
import secrets
import smtplib
import socket
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import bcrypt
import jwt

# ─── إعدادات ────────────────────────────────────────────────────────────────
# JWT secret — لازم يكون قوي وثابت في الإنتاج
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # في التطوير فقط: نولّد واحد عشوائي. في الإنتاج لازم env var ثابت.
    JWT_SECRET = secrets.token_urlsafe(64)
    print("⚠️  JWT_SECRET غير معرّف — تم توليد مؤقت. اضبطه كـ env var في الإنتاج!")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30  # الجلسة 30 يوم


# ─── Password Hashing (bcrypt مباشر، بدون passlib) ─────────────────────────
def _truncate_password(password: str) -> bytes:
    """bcrypt يدعم 72 byte فقط — نقطع الزائد بصمت."""
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    """تشفير كلمة السر بـ bcrypt (one-way)."""
    pw_bytes = _truncate_password(password)
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """التحقق من كلمة السر."""
    try:
        pw_bytes = _truncate_password(plain)
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ─── JWT Tokens ─────────────────────────────────────────────────────────────
def create_jwt_token(user_id: int, extra: Optional[dict] = None) -> str:
    """يولّد JWT token صالح JWT_EXPIRY_DAYS يوم."""
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[dict]:
    """يفك JWT ويرجع الـ payload، أو None لو invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ─── Reset Code ─────────────────────────────────────────────────────────────
def generate_reset_code() -> str:
    """يولّد كود 6 أرقام لاستعادة كلمة السر."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_code(code: str) -> str:
    """نُخزّن الكود مشفّر في DB (مش plain) لأمان أكبر."""
    return hashlib.sha256(code.encode()).hexdigest()


# ─── Email Sending ──────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@dealpulseksa.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "نبض الصفقات")


def send_reset_email(to_email: str, user_name: str, code: str) -> bool:
    """
    يرسل كود استعادة كلمة المرور للإيميل.
    لو SMTP غير معدّ، يطبع الكود في الـ logs (للتطوير).
    يرجع True لو نجح، False لو فشل.
    """
    if not (SMTP_USER and SMTP_PASS):
        # Dev mode — اطبع الكود
        print(f"📧 [DEV MODE] Reset code for {to_email}: {code}")
        return True

    subject = "كود استعادة كلمة المرور - نبض الصفقات"
    html_body = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 40px 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,0.06);">
            <h1 style="color: #10B981; text-align: center; margin: 0 0 16px;">🔐 استعادة كلمة المرور</h1>
            <p style="color: #334155; font-size: 16px; line-height: 1.6;">
                مرحباً {user_name}،<br><br>
                طلبت استعادة كلمة مرور حسابك في <strong>نبض الصفقات</strong>.
                استخدم الكود التالي لإكمال العملية:
            </p>
            <div style="background: linear-gradient(135deg, #10B981, #059669); color: white; font-size: 32px; font-weight: bold; text-align: center; padding: 24px; border-radius: 12px; letter-spacing: 8px; margin: 24px 0;">
                {code}
            </div>
            <p style="color: #64748B; font-size: 14px; text-align: center; margin: 24px 0 8px;">
                ⏱️ صالح لمدة 15 دقيقة فقط
            </p>
            <p style="color: #94A3B8; font-size: 13px; text-align: center; line-height: 1.5;">
                إذا لم تطلب هذا الكود، تجاهل هذا الإيميل.<br>
                لا تشارك هذا الكود مع أي شخص.
            </p>
            <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 32px 0 16px;">
            <p style="color: #94A3B8; font-size: 12px; text-align: center; margin: 0;">
                نبض الصفقات | Deal Pulse KSA<br>
                <a href="https://dealpulseksa.com" style="color: #10B981; text-decoration: none;">dealpulseksa.com</a>
            </p>
        </div>
    </body>
    </html>
    """

    # نُجبر IPv4 — حاويات Railway/Docker قد ترجع IPv6 من DNS بدون route صالح،
        # فيفشل الاتصال بـ "Network is unreachable" قبل ما يجرّب IPv4.
    # SMTP_PASS قد يأتي بمسافات (Gmail يعرضه كـ "abcd efgh ijkl mnop")
    smtp_pass_clean = (SMTP_PASS or "").replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        # نحلّ الـ host لـ IPv4 صراحةً (gethostbyname دائماً IPv4)
        ipv4_host = socket.gethostbyname(SMTP_HOST)

        if SMTP_PORT == 465:
            # SMTPS — SSL من البداية (يعمل عادة على المنصات اللي تحجب 587)
            with smtplib.SMTP_SSL(ipv4_host, SMTP_PORT, timeout=20) as server:
                server.login(SMTP_USER, smtp_pass_clean)
                server.send_message(msg)
        else:
            # STARTTLS — افتراضي port 587
            with smtplib.SMTP(ipv4_host, SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, smtp_pass_clean)
                server.send_message(msg)
        print(f"✅ Reset email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ فشل إرسال إيميل لـ {to_email}: {e}")
        return False
