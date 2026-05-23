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
import requests

# ─── إعدادات ────────────────────────────────────────────────────────────────
# JWT secret — لازم يكون قوي وثابت في الإنتاج
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # fail-fast: مع multi-worker / multi-replica، السرّ العشوائي لكل عملية
    # يُبطل الـ tokens بشكل عشوائي عند redeploy ويسمح بـ DoS صامت.
    raise RuntimeError(
        "JWT_SECRET غير معرّف. اضبطه كـ env var ثابت قبل التشغيل "
        "(`openssl rand -base64 64`)."
    )

JWT_ALGORITHM = "HS256"
# الجلسة 14 يوم — معيار B2C معقول. أقل من ذلك يُزعج المستخدم،
# أكثر يُعرّض الحساب لخطر طويل لو تسرّب التوكن.
JWT_EXPIRY_DAYS = int(os.getenv("JWT_EXPIRY_DAYS", "14"))


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
# الأولوية:
#   1. RESEND_API_KEY  → Resend HTTPS API (الأفضل — port 443، لا يُحجب)
#   2. SMTP_USER+PASS  → Gmail SMTP (احتياطي — Railway يحجب outbound SMTP عادةً)
#   3. لا شي         → Dev mode، يطبع الكود في الـ logs
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "onboarding@resend.dev")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "نبض الصفقات")


def _send_email(to: str, subject: str, html: str) -> bool:
    """
    الناقل العام للإيميلات — يُستخدم في كل أنواع الإيميل (استعادة كلمة سر،
    تنبيهات تشغيلية، توجيهات AI...).

    الترتيب: Resend HTTPS API ← SMTP ← Dev mode (طباعة في الـ logs)
    يرجع True لو نجح، False لو فشل.
    """
    if not RESEND_API_KEY and not (SMTP_USER and SMTP_PASS):
        print(f"[DEV MODE] Email to {to} | subject: {subject}")
        return True

    # ── المسار 1: Resend HTTPS API (port 443، لا يُحجب على المنصات السحابية) ──
    if RESEND_API_KEY:
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{SMTP_FROM_NAME} <{SMTP_FROM}>",
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                timeout=15,
            )
            if response.status_code in (200, 201, 202):
                print(f"✅ Resend: email sent to {to}")
                return True
            print(f"❌ Resend failed [{response.status_code}]: {response.text[:200]}")
            return False
        except Exception as e:
            print(f"❌ Resend exception: {e}")
            return False

    # ── المسار 2: SMTP (احتياطي — قد يفشل على Railway بسبب حجب outbound) ────
    smtp_pass_clean = (SMTP_PASS or "").replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        # نحلّ الـ host لـ IPv4 صراحةً (Railway قد يرجّح IPv6 بدون route)
        ipv4_host = socket.gethostbyname(SMTP_HOST)

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(ipv4_host, SMTP_PORT, timeout=20) as server:
                server.login(SMTP_USER, smtp_pass_clean)
                server.send_message(msg)
        else:
            with smtplib.SMTP(ipv4_host, SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, smtp_pass_clean)
                server.send_message(msg)
        print(f"✅ SMTP: email sent to {to}")
        return True
    except Exception as e:
        print(f"❌ فشل إرسال إيميل لـ {to}: {e}")
        return False


def send_reset_email(to_email: str, user_name: str, code: str) -> bool:
    """
    يرسل كود استعادة كلمة المرور للإيميل.

    الترتيب: Resend HTTPS API ← SMTP ← Dev mode (طباعة في الـ logs)
    يرجع True لو نجح، False لو فشل.
    """
    if not RESEND_API_KEY and not (SMTP_USER and SMTP_PASS):
        print(f"[DEV MODE] Reset code for {to_email}: {code}")
        return True

    subject = "🔐 استعادة كلمة المرور — نبض الصفقات"
    reset_url = f"https://dealpulseksa.com/forgot-password"
    html_body = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>استعادة كلمة المرور</title>
</head>
<body style="margin:0;padding:0;background:#F5F5F0;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#F5F5F0;padding:40px 16px;">
    <tr><td>
      <table width="520" cellpadding="0" cellspacing="0" align="center"
             style="background:#FFFFFF;border-radius:20px;overflow:hidden;
                    box-shadow:0 4px 32px rgba(0,0,0,0.08);max-width:100%;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#10B981,#059669);
                     padding:32px 40px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:22px;font-weight:800;
                       letter-spacing:-0.5px;">نبض الصفقات</h1>
            <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:13px;">
              dealpulseksa.com
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <div style="text-align:center;margin-bottom:28px;">
              <div style="display:inline-block;background:#ECFDF5;
                          border-radius:50%;width:64px;height:64px;
                          line-height:64px;font-size:28px;">🔐</div>
            </div>

            <h2 style="color:#1F2937;text-align:center;margin:0 0 12px;
                       font-size:20px;font-weight:700;">
              استعادة كلمة المرور
            </h2>

            <p style="color:#4B5563;font-size:15px;line-height:1.7;
                      text-align:center;margin:0 0 24px;">
              مرحباً <strong>{user_name}</strong>،<br>
              تلقّينا طلبك لاستعادة كلمة المرور.<br>
              استخدم الكود أدناه لإكمال العملية:
            </p>

            <!-- Code Box -->
            <div style="background:linear-gradient(135deg,#10B981,#059669);
                        border-radius:16px;padding:28px 20px;
                        text-align:center;margin:0 0 24px;">
              <p style="color:rgba(255,255,255,0.85);font-size:12px;
                        margin:0 0 10px;letter-spacing:2px;text-transform:uppercase;">
                كود التحقق
              </p>
              <div style="color:white;font-size:38px;font-weight:900;
                          letter-spacing:12px;font-family:monospace;">
                {code}
              </div>
            </div>

            <!-- CTA Button -->
            <div style="text-align:center;margin:0 0 28px;">
              <a href="{reset_url}"
                 style="display:inline-block;background:linear-gradient(135deg,#10B981,#059669);
                        color:white;text-decoration:none;font-size:15px;
                        font-weight:700;padding:16px 40px;border-radius:50px;
                        box-shadow:0 4px 14px rgba(16,185,129,0.4);">
                تعيين كلمة مرور جديدة
              </a>
            </div>

            <!-- Timer -->
            <div style="background:#FEF3C7;border-radius:12px;
                        padding:12px 20px;text-align:center;margin-bottom:24px;">
              <p style="color:#92400E;font-size:13px;margin:0;">
                ⏱️ الكود صالح لمدة <strong>15 دقيقة فقط</strong>
              </p>
            </div>

            <p style="color:#9CA3AF;font-size:12px;text-align:center;
                      line-height:1.6;margin:0;">
              إذا لم تطلب هذا الكود، تجاهل هذا الإيميل بأمان.<br>
              لا تشارك هذا الكود مع أي شخص.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F9FAFB;padding:20px 40px;text-align:center;
                     border-top:1px solid #E5E7EB;">
            <p style="color:#9CA3AF;font-size:12px;margin:0;">
              نبض الصفقات | Deal Pulse KSA<br>
              <a href="https://dealpulseksa.com"
                 style="color:#10B981;text-decoration:none;">
                dealpulseksa.com
              </a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    # ناقل الإيميل المشترك (Resend → SMTP → Dev mode)
    return _send_email(to=to_email, subject=subject, html=html_body)
