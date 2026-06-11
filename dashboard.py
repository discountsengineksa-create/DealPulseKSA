import os
import base64
import smtplib
import socket
import warnings as _warnings
# pandas يحذّر عند تمرير اتصال psycopg2 خام لـ read_sql (يقترح SQLAlchemy).
# الكود يعمل صحيحاً عبر الـ pool المخصّص (_PooledConn)؛ نكتم التحذير لتنظيف السجلّات.
_warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable.*",
)
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from psycopg2 import extras, pool as pg_pool
from contextlib import contextmanager
from io import BytesIO
from dotenv import load_dotenv
import numpy as np
import datetime
import json
import streamlit.components.v1 as components
try:
    from streamlit_option_menu import option_menu as _option_menu
    _OPTION_MENU_OK = True
except ImportError:
    _OPTION_MENU_OK = False

# ─── Cloudinary (اختياري: لرفع شعارات المتاجر تلقائياً) ──────────────────────
try:
    import cloudinary
    import cloudinary.uploader
    _CLOUDINARY_OK = bool(os.getenv("CLOUDINARY_CLOUD_NAME"))
    if _CLOUDINARY_OK:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        )
except ImportError:
    _CLOUDINARY_OK = False


def _upload_logo(file_bytes: bytes, store_slug: str) -> str | None:
    """رفع شعار المتجر إلى Cloudinary — يُعيد الـ secure_url أو None."""
    if not _CLOUDINARY_OK:
        return None
    try:
        # نخزّن نسخة أساسية عالية الدقة (تصغير فقط عند الحاجة، بدون تكبير ولا حشو)
        # عشان نشتقّ منها لاحقاً مقاس كل منصة عبر تحويلات رابط Cloudinary.
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=f"store_logos/{store_slug}",
            overwrite=True,
            transformation=[{"width": 1600, "height": 1600, "crop": "limit"}],
        )
        return result.get("secure_url")
    except Exception as e:
        st.warning(f"⚠️ فشل رفع الشعار إلى Cloudinary: {e}")
        return None


def _upload_story_media(file_bytes: bytes, store_slug: str) -> str | None:
    """رفع وسائط الستوري (فيديو أو صورة) إلى Cloudinary — يُعيد secure_url أو None.
    resource_type='auto' يجعل Cloudinary يكتشف نوع الملف (فيديو/صورة) تلقائياً."""
    if not _CLOUDINARY_OK:
        return None
    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=f"story_media/{store_slug}",
            overwrite=True,
            resource_type="auto",
        )
        return result.get("secure_url")
    except Exception as e:
        st.warning(f"⚠️ فشل رفع وسائط الستوري إلى Cloudinary: {e}")
        return None


def _is_video_url(url: str) -> bool:
    """يكتشف الفيديو من امتداد الرابط — نفس منطق الواجهة (الويب/الميني-ويب)."""
    u = (url or "").lower().split("?")[0]
    return u.endswith((".mp4", ".webm", ".mov", ".m4v"))


def _trigger_social_broadcast(master_id: int | None) -> None:
    """
    fire-and-forget: يبلّغ الـ FastAPI لينشر العرض على منصات السوشيال في الخلفية.
    لا يُعطّل الـ dashboard لو فشل — يكتفي بـ warning خفيف.
    """
    if not master_id:
        return
    secret = os.getenv("ADMIN_SHARED_SECRET")
    api_url = os.getenv(
    "INTERNAL_API_URL", 
    "https://api.dealpulseksa.com"
    ).rstrip("/")
    if not secret:
        st.warning(
            "⚠️ النشر التلقائي معطّل — أضف `ADMIN_SHARED_SECRET` على خدمة الداشبورد "
            "(بنفس قيمة الـ API) لتفعيل البث للسوشيال."
        )
        return
    try:
        resp = requests.post(
            f"{api_url}/api/v1/admin/broadcast/{master_id}",
            headers={"X-Admin-Secret": secret},
            timeout=4,
        )
    except Exception as e:
        st.warning(f"تم الحفظ، لكن فشلت جدولة النشر: {e}")
        return

    if resp.status_code < 300:
        st.toast("📢 جدولة نشر العرض على منصات السوشيال…")
    elif resp.status_code == 403:
        st.error(
            "❌ البث مرفوض (403): سرّ الإدمن غير متطابق بين الداشبورد والـ API. "
            "تأكّد إن `ADMIN_SHARED_SECRET` نفس القيمة على الخدمتين."
        )
    elif resp.status_code == 503:
        st.error(
            "❌ البث غير مفعّل (503): `ADMIN_SHARED_SECRET` غير مضبوط على خدمة الـ API."
        )
    else:
        st.warning(
            f"تم الحفظ، لكن جدولة النشر رجّعت HTTP {resp.status_code}: {resp.text[:200]}"
        )


# ─── جسر الـ Admin API (للوحات SEO + الرصد الاجتماعي) ──────────────────────────
def _admin_api():
    """يرجّع (base_url, secret) للـ admin API على الإنتاج."""
    secret = os.getenv("ADMIN_SHARED_SECRET")
    base = os.getenv(
    "INTERNAL_API_URL", 
    "https://api.dealpulseksa.com"
    ).rstrip("/")
    return base, secret


def _admin_get(path: str, params: dict | None = None):
    """GET على /api/v1{path}. يرجّع (data, error)."""
    base, secret = _admin_api()
    if not secret:
        return None, "ADMIN_SHARED_SECRET غير مضبوط في بيئة الداشبورد"
    try:
        r = requests.get(f"{base}/api/v1{path}",
                         headers={"X-Admin-Secret": secret},
                         params=params or {}, timeout=20)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)


def _admin_post(path: str, params: dict | None = None, json_body: dict | None = None,
                timeout: int = 90):
    """POST على /api/v1{path}. يرجّع (data, error). timeout أطول لعمليات LLM الثقيلة."""
    base, secret = _admin_api()
    if not secret:
        return None, "ADMIN_SHARED_SECRET غير مضبوط في بيئة الداشبورد"
    try:
        r = requests.post(f"{base}/api/v1{path}",
                          headers={"X-Admin-Secret": secret},
                          params=params or {}, json=json_body, timeout=timeout)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)


def _admin_put(path: str, json_body: dict | None = None):
    """PUT على /api/v1{path}. يرجّع (data, error)."""
    base, secret = _admin_api()
    if not secret:
        return None, "ADMIN_SHARED_SECRET غير مضبوط في بيئة الداشبورد"
    try:
        r = requests.put(f"{base}/api/v1{path}",
                         headers={"X-Admin-Secret": secret},
                         json=json_body or {}, timeout=30)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)


def _admin_delete(path: str):
    """DELETE على /api/v1{path}. يرجّع (data, error)."""
    base, secret = _admin_api()
    if not secret:
        return None, "ADMIN_SHARED_SECRET غير مضبوط في بيئة الداشبورد"
    try:
        r = requests.delete(f"{base}/api/v1{path}",
                            headers={"X-Admin-Secret": secret}, timeout=30)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)

# ─── لوحة ألوان "نبض الصفقات KSA" ──────────────────────────────────────────
BRAND_LIGHT = {
"bg":             "#FAFAF8",
"bg_alt":         "#F5F5F0",
"surface":        "#FFFFFF",
"surface_elev":   "#FDFDFB",
"glass":          "rgba(255,255,255,0.55)",
"glass_strong":   "rgba(255,255,255,0.70)",
"text":           "#1F2937",
"text_soft":      "#2D3142",
"text_muted":     "#6B7280",
"text_faint":     "#9CA3AF",
"emerald":        "#10B981",
"emerald_deep":   "#059669",
"emerald_dark":   "#047857",
"emerald_pastel": "#D1FAE5",
"emerald_mint":   "#A7F3D0",
"saudi_green":    "#006B3F",
"warning":        "#F59E0B",
"warning_soft":   "#FEF3C7",
"danger":         "#DC2626",
"danger_soft":    "#FEE2E2",
"info":           "#0EA5E9",
"info_soft":      "#E0F2FE",
"border":         "#E5E7EB",
"border_soft":    "#F0F0EA",
"grid":           "rgba(107,114,128,0.12)",
"blob_op":        "1.0",
}

# لوحة غامقة (وضع ليلي) — نفس المفاتيح بقيم داكنة مريحة للعين
BRAND_DARK = {
"bg":             "#0E1117",
"bg_alt":         "#161A23",
"surface":        "#1A1D24",
"surface_elev":   "#21252E",
"glass":          "rgba(30,34,43,0.55)",
"glass_strong":   "rgba(30,34,43,0.75)",
"text":           "#E6E8EB",
"text_soft":      "#CBD2D9",
"text_muted":     "#9AA4B2",
"text_faint":     "#6B7280",
"emerald":        "#10B981",
"emerald_deep":   "#34D399",
"emerald_dark":   "#6EE7B7",
"emerald_pastel": "#064E3B",
"emerald_mint":   "#065F46",
"saudi_green":    "#34D399",
"warning":        "#FBBF24",
"warning_soft":   "#3A2E12",
"danger":         "#F87171",
"danger_soft":    "#3A1A1A",
"info":           "#38BDF8",
"info_soft":      "#0C2A3A",
"border":         "#2A2F3A",
"border_soft":    "#21252E",
"grid":           "rgba(230,232,235,0.12)",
"blob_op":        "0.22",
}


load_dotenv()

# ─── تحميل الشعار ─────────────────────────────────────────────────────────────
_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
_logo_b64: str | None = None
if os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _f:_logo_b64 = base64.b64encode(_f.read()).decode()
_wm_url = f"data:image/jpeg;base64,{_logo_b64}" if _logo_b64 else ""

# إعداد الصفحة
st.set_page_config(
page_title="نبض الصفقات KSA | DEAL PULSE",
page_icon="🟢",
layout="wide",
initial_sidebar_state="expanded",
)

# اختيار المظهر: ليلي افتراضي. يُقرأ من مفتاح زر التبديل في الشريط الجانبي
# (يُعرض بعد الدخول)؛ session_state يحفظ الاختيار فيُطبَّق على كل الـ CSS أدناه.
_ui_dark = st.session_state.get("ui_theme_radio", "🌙 ليلي").startswith("🌙")
BRAND = BRAND_DARK if _ui_dark else BRAND_LIGHT

# ─── CSS حرج مبكّر: يمنع وميض التصميم الافتراضي (FOUC) قبل تحميل الستايل الكامل ─
# يثبّت اتجاه RTL، يضع الـ sidebar على اليمين، ويفرض خلفية الثيم الفاتحة فوراً
# حتى لا يومض المستخدم الثيم الداكن الافتراضي للمتصفح/Streamlit قبل أن يصل
# بلوك الستايل الكامل الذي يأتي بعد المصادقة.
_BRAND_BG_EARLY = BRAND["bg"]
_BRAND_BG_ALT_EARLY = BRAND["bg_alt"]
_BRAND_BORDER_EARLY = BRAND["border_soft"]
_BRAND_TEXT_EARLY = BRAND["text"]
st.markdown(f"""
<style>
html, body, [data-testid="stAppViewContainer"], .main, .main .block-container {{
    direction: rtl !important;
    text-align: right !important;
    background: {_BRAND_BG_EARLY} !important;
    color: {_BRAND_TEXT_EARLY} !important;
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif !important;
}}
.stApp {{ background: {_BRAND_BG_EARLY} !important; }}
[data-testid="stSidebar"] {{
    right: 0 !important;
    left: auto !important;
    background: linear-gradient(180deg, {_BRAND_BG_ALT_EARLY} 0%, {_BRAND_BG_EARLY} 60%, {_BRAND_BORDER_EARLY} 100%) !important;
}}
[data-testid="stSidebar"] * {{ color: {_BRAND_TEXT_EARLY} !important; text-align: right !important; }}
[data-testid="stSidebarCollapseButton"],
[data-testid="stDeployButton"],
[data-testid="stToolbar"],
header[data-testid="stHeader"] {{ display: none !important; }}
</style>
""", unsafe_allow_html=True)

# ─── بوابة تسجيل الدخول ────────────────────────────────────────────────────
# لا أي بيانات تظهر قبل المصادقة.
# مصدر بيانات الدخول:
#   • محليًا: .streamlit/secrets.toml (قسم [auth] بكلمة سر مُجزّأة bcrypt).
#   • على Railway (لا secrets.toml): من متغيّرات البيئة username/password.
# نُجزّئ كلمة سر البيئة مرّة واحدة في الجلسة، فيقبلها stauth مثل أي bcrypt hash.
try:
    _auth_cfg = st.secrets["auth"]
    _creds_raw = _auth_cfg["credentials"]
    _creds = _creds_raw.to_dict() if hasattr(_creds_raw, "to_dict") else dict(_creds_raw)
    _cookie_name = _auth_cfg["cookie_name"]
    _cookie_key  = _auth_cfg["cookie_key"]
    _cookie_days = int(_auth_cfg.get("cookie_expiry_days", 1))
except Exception:
    _u = os.getenv("DASHBOARD_USER") or os.getenv("username") or "admin"
    _p = os.getenv("DASHBOARD_PASSWORD") or os.getenv("password") or ""
    if not _p:
        st.error("⚠️ إعدادات الدخول ناقصة: أضف username و password في متغيّرات Railway.")
        st.stop()
    import hashlib as _hl
    if "_dp_pwhash" not in st.session_state:
        import bcrypt as _bc
        st.session_state["_dp_pwhash"] = _bc.hashpw(_p.encode(), _bc.gensalt()).decode()
    _cookie_name = os.getenv("DASHBOARD_COOKIE_NAME", "deal_pulse_admin")
    _cookie_key  = os.getenv("DASHBOARD_COOKIE_KEY") or _hl.sha256(_p.encode()).hexdigest()
    _cookie_days = int(os.getenv("DASHBOARD_COOKIE_DAYS", "1"))
    _creds = {"usernames": {_u: {"name": "Admin", "email": "admin@dealpulse.local",
                                 "password": st.session_state["_dp_pwhash"]}}}

_authenticator = stauth.Authenticate(
credentials=_creds,
cookie_name=_cookie_name,
cookie_key=_cookie_key,
cookie_expiry_days=_cookie_days,
)
_authenticator.login(location="main")

if st.session_state.get("authentication_status") is False:
    st.error("❌ اسم المستخدم أو كلمة السر غير صحيحة")
    st.stop()
if st.session_state.get("authentication_status") is None:
    st.info("🔒 الرجاء تسجيل الدخول للوصول إلى لوحة التحكم")
    st.stop()

# ─── ثيم "نبض الصفقات KSA" — Light Premium (مطابق للشعار) ────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');

/* ── RTL Global + Cairo Font ── */
html, body, [class*="css"] {{
direction: rtl !important;
text-align: right !important;
font-family: 'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif !important;
}}

/* ── Premium Light Background + Soft Pastel Blobs ── */
.stApp {{
background: {BRAND["bg"]} !important;
}}
.stApp::before {{
content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 800' preserveAspectRatio='xMidYMid slice'><circle cx='80' cy='90' r='280' fill='%23D1FAE5' opacity='0.55'/><circle cx='1120' cy='720' r='340' fill='%23A7F3D0' opacity='0.45'/><circle cx='1080' cy='120' r='90' fill='%23ECFDF5' opacity='0.6'/></svg>");
background-size: cover;
background-position: center;
opacity: {BRAND["blob_op"]};
}}
/* ── Watermark: الشعار كعلامة مائية في مركز الصفحة الرئيسية ── */
.stApp::after {{
content: ""; position: fixed;
top: 50%; left: 45%;                 /* التوسيط: 50% / 50% = منتصف الشاشة */
transform: translate(-50%, -50%);
width: 70vw; height: 70vw;           /* حجم العلامة (vw = نسبة من عرض الشاشة) */
pointer-events: none; z-index: 0;
background-image: url("{_wm_url}");
background-repeat: no-repeat;
background-size: contain;
background-position: center;
opacity: 0.05;                       /* الشفافية: 0 = مخفي تماماً، 1 = واضح كامل */
}}
.main .block-container {{
position: relative; z-index: auto !important;
direction: rtl !important;
padding-top: 1.5rem !important;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
background: linear-gradient(180deg, {BRAND["bg_alt"]} 0%, {BRAND["bg"]} 60%, {BRAND["border_soft"]} 100%) !important;
border-left: 1px solid {BRAND["border"]} !important;
box-shadow: 4px 0 18px rgba(31,41,55,0.06) !important;
width: 260px !important;
min-width: 260px !important;
}}
/* ── شعار رأس القائمة الجانبية ── */
[data-testid="stSidebar"] img {{
width: 90px !important;
max-width: 90px !important;
opacity: 0.88 !important;
display: block !important;
margin: 0 auto 6px auto !important;
border-radius: 8px !important;
filter: none !important;
box-shadow: 0 2px 10px rgba(16,185,129,0.18) !important;
}}
[data-testid="stSidebar"] > div:first-child {{
padding-top: 0px !important;
}}

/* ── إخفاء زر طي الـ Sidebar بالكامل ── */
[data-testid="stSidebarCollapseButton"] {{
display: none !important;
}}

/* ── إخفاء زر Deploy وشريط الهيدر العلوي ── */
[data-testid="stDeployButton"] {{ display: none !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}
header[data-testid="stHeader"] {{ display: none !important; }}

/* ── إخفاء أيقونة Material Icons في كل الواجهة ──
(تظهر كنص حرفي keyboard_arrow_down/keyboard_ar... لأن قاعدة
font-family: Cairo العالمية تطغى على خط Material Symbols Rounded.
المربع الأبيض يستخدم بدائل CSS (▼) من نفس Streamlit، فالإخفاء آمن.) */
[data-testid="stSidebar"] span[data-testid="stIconMaterial"],
span[data-testid="stIconMaterial"] {{
display: none !important;
}}

/* ── نصوص الـ Sidebar العامة ── */
[data-testid="stSidebar"] * {{
color: {BRAND["emerald_dark"]} !important;
text-align: right !important;
direction: rtl !important;
font-family: 'Cairo', sans-serif !important;
font-size: 14px !important;
}}

/* ── عناوين الـ Expander: النص العربي فقط ── */
[data-testid="stSidebar"] summary [data-testid="stMarkdownContainer"] p {{
font-size: 14px !important;
color: {BRAND["emerald_dark"]} !important;
font-family: 'Cairo', sans-serif !important;
font-weight: 700 !important;
margin: 0 !important;
}}
/* ── Radio labels: النقطة والنص في نفس السطر ── */
[data-testid="stSidebar"] .stRadio label {{
font-size: 14px !important;
padding: 7px 10px !important;
border-radius: 8px !important;
transition: background 0.2s ease !important;
color: {BRAND["emerald_dark"]} !important;
line-height: 1.45 !important;
display: flex !important;
align-items: center !important;
flex-direction: row-reverse !important;
gap: 8px !important;
margin: 1px 0 !important;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
background: rgba(16,185,129,0.10) !important;
color: {BRAND["emerald_dark"]} !important;
}}
/* ── فراغات بين عناصر القائمة ── */
[data-testid="stSidebar"] .stRadio > div {{
gap: 1px !important;
padding: 4px 2px !important;
}}
/* ── Expanders ── */
[data-testid="stSidebar"] [data-testid="stExpander"] {{
background: {BRAND["glass"]} !important;
border: 1px solid {BRAND["border"]} !important;
border-radius: 12px !important;
margin-bottom: 8px !important;
backdrop-filter: blur(12px) !important;
overflow: hidden !important;
}}
/* ── رأس الـ Expander ── */
[data-testid="stSidebar"] summary {{
color: {BRAND["emerald_deep"]} !important;
font-weight: 700 !important;
font-size: 14px !important;
font-family: 'Cairo', sans-serif !important;
padding: 9px 12px !important;
display: flex !important;
align-items: center !important;
justify-content: space-between !important;
}}
/* ── سهم الـ Expander ── */
[data-testid="stSidebar"] summary svg {{
display: block !important;
width: 16px !important;
height: 16px !important;
fill: {BRAND["emerald_deep"]} !important;
flex-shrink: 0 !important;
}}
/* منطقة المحتوى داخل الـ Expander */
[data-testid="stSidebar"] [data-testid="stExpander"] > div[data-testid="stExpanderDetails"] {{
padding: 4px 10px 10px !important;
}}

/* ── Headings ── */
h1, h2, h3 {{
text-align: right !important;
font-family: 'Cairo', sans-serif !important;
}}
h1 {{
color: {BRAND["text"]} !important;
border-bottom: 3px solid {BRAND["emerald"]};
padding-bottom: 10px;
font-weight: 900 !important;
letter-spacing: -0.5px;
}}
h2 {{
color: {BRAND["text"]} !important;
border-right: 4px solid {BRAND["emerald"]};
padding-right: 12px;
font-weight: 800 !important;
}}
h3 {{ color: {BRAND["emerald_dark"]} !important; font-weight: 700 !important; }}
h4 {{ color: {BRAND["text"]} !important; font-family: 'Cairo', sans-serif !important; }}
p, span, label, div {{
font-family: 'Cairo', sans-serif !important;
}}

/* ── Glassmorphism Metric Cards (Light) ── */
[data-testid="stMetric"] {{
background: {BRAND["glass_strong"]} !important;
backdrop-filter: blur(14px) !important;
-webkit-backdrop-filter: blur(14px) !important;
border-radius: 16px !important;
padding: 20px 16px !important;
border: 1px solid rgba(16,185,129,0.18) !important;
box-shadow: 0 4px 16px rgba(31,41,55,0.06) !important;
text-align: center !important;
transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}}
[data-testid="stMetric"]:hover {{
transform: translateY(-2px) !important;
box-shadow: 0 8px 24px rgba(16,185,129,0.18) !important;
}}
[data-testid="stMetric"] label {{
color: {BRAND["text_muted"]} !important;
font-size: 0.82rem !important;
font-family: 'Cairo', sans-serif !important;
font-weight: 600 !important;
}}
[data-testid="stMetric"] [data-testid="stMetricValue"] {{
color: {BRAND["emerald_deep"]} !important;
font-size: 1.95rem !important;
font-weight: 900 !important;
font-family: 'Cairo', sans-serif !important;
}}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {{
color: {BRAND["emerald"]} !important;
font-family: 'Cairo', sans-serif !important;
}}

/* ── Buttons ── */
.stButton > button {{
background: linear-gradient(135deg, {BRAND["emerald"]} 0%, {BRAND["emerald_deep"]} 100%) !important;
color: #ffffff !important;
font-weight: 700 !important;
border: none !important;
border-radius: 10px !important;
font-family: 'Cairo', sans-serif !important;
font-size: 0.95rem !important;
letter-spacing: 0.3px !important;
transition: transform 0.15s ease, box-shadow 0.15s ease !important;
box-shadow: 0 4px 12px rgba(16,185,129,0.22) !important;
}}
.stButton > button:hover {{
transform: translateY(-2px) !important;
box-shadow: 0 8px 20px rgba(16,185,129,0.35) !important;
background: linear-gradient(135deg, #34D399 0%, {BRAND["emerald"]} 100%) !important;
}}
.stButton > button:active {{ transform: translateY(0) !important; }}

/* ── Forms (Glass Effect) ── */
[data-testid="stForm"] {{
border: 1px solid {BRAND["border"]} !important;
border-radius: 16px !important;
padding: 20px !important;
background: {BRAND["glass"]} !important;
backdrop-filter: blur(8px) !important;
-webkit-backdrop-filter: blur(8px) !important;
box-shadow: 0 2px 12px rgba(31,41,55,0.04) !important;
}}
/* ── Glass Inputs ── */
input, textarea {{
background: {BRAND["glass"]} !important;
}}
/* ── Transparent block wrappers ── */
.main .block-container > div {{
background: transparent !important;
}}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {{
direction: rtl !important;
border-bottom: 1px solid {BRAND["border"]} !important;
gap: 4px !important;
}}
[data-testid="stTabs"] button[role="tab"] {{
color: {BRAND["text_muted"]} !important;
font-weight: 600 !important;
font-family: 'Cairo', sans-serif !important;
border-radius: 8px 8px 0 0 !important;
transition: color 0.2s !important;
}}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
color: {BRAND["emerald_deep"]} !important;
border-bottom: 3px solid {BRAND["emerald"]} !important;
background: {BRAND["surface"]} !important;
}}

/* ── Dataframes ── */
[data-testid="stDataFrame"] {{
direction: rtl !important;
border-radius: 12px !important;
overflow: hidden !important;
border: 1px solid {BRAND["border"]} !important;
box-shadow: 0 2px 12px rgba(31,41,55,0.04) !important;
}}

/* ── Expanders ── */
[data-testid="stExpander"] {{
border: 1px solid {BRAND["border"]} !important;
border-radius: 12px !important;
background: {BRAND["surface_elev"]} !important;
}}
[data-testid="stExpander"] summary {{
color: {BRAND["text"]} !important;
font-weight: 700 !important;
font-family: 'Cairo', sans-serif !important;
}}

/* ── Alerts ── */
[data-testid="stAlert"] {{
border-radius: 12px !important;
text-align: right !important;
direction: rtl !important;
font-family: 'Cairo', sans-serif !important;
}}

/* ── Divider ── */
hr {{ border-color: {BRAND["border"]} !important; }}

/* ── Inputs (Base) ── */
input, textarea, select {{
direction: rtl !important;
text-align: right !important;
font-family: 'Cairo', sans-serif !important;
background: {BRAND["surface"]} !important;
border: 1px solid {BRAND["border"]} !important;
color: {BRAND["text"]} !important;
}}

/* ── High-contrast widget overrides (يغلب على شفافية الـ form rule) ── */
.stTextInput input, .stTextArea textarea,
.stSelectbox > div > div, .stMultiSelect > div > div,
.stNumberInput input, .stDateInput input {{
background: {BRAND["surface"]} !important;
border: 1.5px solid {BRAND["border"]} !important;
color: {BRAND["text"]} !important;
font-weight: 500 !important;
}}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {{
color: {BRAND["text_muted"]} !important;
opacity: 1 !important;
}}
.stTextInput label, .stTextArea label,
.stSelectbox label, .stMultiSelect label,
.stNumberInput label, .stDateInput label, .stRadio label {{
color: {BRAND["text"]} !important;
font-weight: 600 !important;
opacity: 1 !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus,
.stNumberInput input:focus, .stDateInput input:focus {{
border-color: {BRAND["emerald"]} !important;
box-shadow: 0 0 0 3px rgba(16,185,129,0.15) !important;
outline: none !important;
}}

/* ── Plotly charts RTL ── */
.js-plotly-plot .plotly .gtitle {{ text-anchor: end !important; }}

/* ── Selectbox / Multiselect ── */
[data-testid="stMultiSelect"] span,
[data-testid="stSelectbox"] span {{
font-family: 'Cairo', sans-serif !important;
}}

/* ── Scrollbar Light Premium ── */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: {BRAND["border_soft"]}; }}
::-webkit-scrollbar-thumb {{
background: linear-gradient(180deg, {BRAND["emerald"]}, {BRAND["emerald_deep"]});
border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{ background: {BRAND["emerald_dark"]}; }}
</style>
""", unsafe_allow_html=True)

# ─── Connection Pool (مشترك بين كل جلسات Streamlit) ────────────────────────
@st.cache_resource
def _get_pool() -> pg_pool.ThreadedConnectionPool:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
    # Railway يُعطي postgres:// لكن psycopg2 يحتاج postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return pg_pool.ThreadedConnectionPool(
            minconn=1, maxconn=10, dsn=db_url,
            options="-c timezone=Asia/Riyadh",   # كل الأوقات تُعرض/تُحسب بتوقيت الرياض
        )
    return pg_pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    options="-c timezone=Asia/Riyadh",
)


class _PooledConn:
    """
    Proxy class for PostgreSQL connections.
    Instead of closing the connection, it returns it to the pool.
    """
    __slots__ = ("_pool", "_conn", "_closed")

    def __init__(self, pool, conn):
        object.__setattr__(self, "_pool",   pool)
        object.__setattr__(self, "_conn",   conn)
        object.__setattr__(self, "_closed", False)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name: str, value):
        if name in ("_pool", "_conn", "_closed"):
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_conn"), name, value)

    def close(self):
        if object.__getattribute__(self, "_closed"):
            return
        object.__setattr__(self, "_closed", True)
        pool = object.__getattribute__(self, "_pool")
        conn = object.__getattribute__(self, "_conn")
        try:
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)

    def __del__(self):
        """شبكة أمان: لو نُسي close() أو حصل exception، الاتصال يرجع للـ pool تلقائياً."""
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = object.__getattribute__(self, "_conn")
        if not object.__getattribute__(self, "_closed"):
            try:
                if exc_type is None:
                    conn.commit()
                else:
                    conn.rollback()
            except Exception:
                pass
        self.close()
        return False

def get_conn() -> _PooledConn:
    """
    دالة متوافقة مع الكود الحالي: تسحب اتصالاً من الـ Pool وتعيده عند close() .
    """
    p = _get_pool()
    return _PooledConn(p, p.getconn())


@contextmanager
def get_db():
    conn_proxy = get_conn()
    try:
        yield conn_proxy
        # إذا وصل التنفيذ هنا يعني لم يحدث خطأ في بلوك with
        conn_proxy._conn.commit() 
    except Exception as e:
        conn_proxy._conn.rollback()
        raise e
    finally:
        conn_proxy.close() # تعيده للمسبح (Pool)

def get_master_data():
    conn = None # تعريف أولي
    try:
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM master ORDER BY id ASC", conn)
        return df
    except Exception as e:
        st.error(f"خطأ: {e}")
        return pd.DataFrame()
    finally:
        if conn: # التأكد أن الاتصال تم بنجاح قبل محاولة إغلاقه
            conn.close()


@st.cache_data(ttl=300)
def _get_partner_logos() -> list[dict]:
    """شعارات المتاجر النشطة للشريط المتحرك وشبكة الأيقونات — مخزنة 5 دقائق."""
    try:
        conn = get_conn()
        rows = pd.read_sql(
            """
            SELECT store_id,
                   COALESCE(name_en, store_id) AS display_name,
                   logo_url
            FROM   master
            WHERE  logo_url IS NOT NULL AND logo_url != ''
            ORDER  BY priority_score DESC NULLS LAST
            LIMIT  50
            """,
            conn,
        ).to_dict("records")
        conn.close()
        return rows
    except Exception:
        return []


@st.cache_data(ttl=300)
def _get_all_tags() -> list[str]:
    """جميع الأقسام (tags) الفريدة من جدول master — مخزنة 5 دقائق."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT trim(t) AS tag
            FROM   master,
                   unnest(string_to_array(
                       trim(both '{}' from COALESCE(store_tags, '')), ','
                   )) AS t
            WHERE  trim(t) != ''
            ORDER  BY tag
            """,
            conn,
        )
        conn.close()
        return [r for r in df["tag"].tolist() if r]
    except Exception:
        return []


# خريطة الأيقونات للأقسام العربية الشائعة
_TAG_ICONS: dict[str, str] = {
    "أزياء": "👗", "ملابس": "👕", "موضة": "👠",
    "إلكترونيات": "📱", "تقنية": "💻", "جوالات": "📲",
    "توصيل": "🛵", "مطاعم": "🍽️", "طعام": "🍔",
    "تجميل": "💄", "عطور": "🌹", "عناية": "🧴",
    "رياضة": "⚽", "لياقة": "🏋️",
    "سفر": "✈️", "فنادق": "🏨",
    "عقارات": "🏠",
    "سوبرماركت": "🛒", "بقالة": "🧺",
    "أطفال": "🧸", "ألعاب": "🎮",
    "كتب": "📚", "تعليم": "🎓",
    "سيارات": "🚗",
    "صيدلية": "💊", "صحة": "🏥",
    "حيوانات": "🐾",
    "ديكور": "🛋️", "أثاث": "🪑",
    "خدمات": "🔧",
}


def _tag_icon(tag: str) -> str:
    for k, v in _TAG_ICONS.items():
        if k in tag:
            return v
    return "🏷️"


_API_SEARCH_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/v1/coupons/search"

def fetch_coupon_data(q: str, limit: int = 50) -> tuple[int, pd.DataFrame]:
    """
    Fetch search results from FastAPI and convert them to a DataFrame.
    
    Returns:
        (-1, empty) -> Server is closed / السيرفر مغلق
        (0, empty)  -> No results or HTTP error / لا نتائج أو خطأ
        (n, df)     -> n = total from API, df = rows / الصفوف
    """
    try:
        resp = requests.get(
            _API_SEARCH_URL,
            params={"q": q, "limit": limit},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        total = data.get("total", 0)
        results = data.get("results", [])
        df = pd.DataFrame(results) if results else pd.DataFrame()
        return total, df
    except requests.exceptions.ConnectionError:
        return -1, pd.DataFrame()
    except Exception:
        return 0, pd.DataFrame()


def parse_tags(raw):
    """تحويل عمود store_tags النصي ('{a,b,c}') إلى قائمة بايثون نظيفة."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    s = str(raw).strip().strip('{}').strip()
    if not s:
        return []
    return [t.strip() for t in s.split(',') if t.strip()]


# ─── Helpers موحَّدة لهوية "نبض الصفقات KSA" ────────────────────────────────
def apply_brand_theme(fig, *, transparent=True):
    """تطبيق هوية الشعار على رسوم Plotly: خلفية شفافة، خط Cairo، لوحة ألوان زمردية."""
    fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)" if transparent else BRAND["bg"],
    plot_bgcolor="rgba(0,0,0,0)" if transparent else BRAND["surface"],
    font=dict(family="Cairo, sans-serif", color=BRAND["text"], size=13),
    title=dict(
        text=(fig.layout.title.text or ""),   # يمنع ظهور "undefined" عند غياب العنوان
        font=dict(family="Cairo, sans-serif", color=BRAND["text"], size=18),
        x=0.98, xanchor="right",
    ),
    colorway=["#10B981", "#059669", "#6B7280", "#F59E0B",
                "#0EA5E9", "#A7F3D0", "#1F2937", "#DC2626"],
    legend=dict(font=dict(color=BRAND["text_muted"])),
    margin=dict(l=20, r=20, t=60, b=40),
    )
    fig.update_xaxes(gridcolor=BRAND["grid"], linecolor=BRAND["border"],
                    tickfont=dict(color=BRAND["text_muted"]))
    fig.update_yaxes(gridcolor=BRAND["grid"], linecolor=BRAND["border"],
                    tickfont=dict(color=BRAND["text_muted"]))
    return fig


def page_title(emoji, text, subtitle=None):
    sub = (
        f'<p style="text-align:center; font-size:1.05rem; '
        f'color:{BRAND["text_muted"]}; margin-top:-4px;">{subtitle}</p>'
    ) if subtitle else ""
    st.markdown(
        f'<h1 style="text-align:center; color:{BRAND["text"]}; '
        f'border-bottom:3px solid {BRAND["emerald"]}; padding-bottom:10px; '
        f'font-weight:900;">{emoji} {text}</h1>{sub}',
        unsafe_allow_html=True,
    )

def kpi_card(emoji, label, value, accent="emerald", note=None):
    palette = {
        "emerald": (BRAND["emerald_pastel"], BRAND["emerald"], BRAND["emerald_dark"]),
        "warning": (BRAND["warning_soft"],   BRAND["warning"], "#92400E"),
        "danger":  (BRAND["danger_soft"],    BRAND["danger"],  "#991B1B"),
        "info":    (BRAND["info_soft"],      BRAND["info"],    "#075985"),
        "neutral": ("#F9FAFB",               BRAND["text_muted"], "#374151"),
    }
    bg, bar, txt = palette.get(accent, palette["emerald"])
    note_html = (
        f'<p style="color:{BRAND["text_muted"]}; margin:0; font-size:0.85rem;">{note}</p>'
    ) if note else ""
    st.markdown(
        f'<div style="background:{bg}; padding:20px; border-radius:14px; '
        f'border-right:5px solid {bar}; text-align:center; '
        f'box-shadow:0 2px 10px rgba(31,41,55,0.05); border:1px solid {BRAND["border"]};">'
        f'<h4 style="color:{txt}; margin:0; font-weight:700;">{emoji} {label}</h4>'
        f'<p style="font-size:2.4em; font-weight:900; color:{BRAND["text"]}; '
        f'margin:10px 0;">{value}</p>{note_html}</div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════════════
#  Helpers خاصة بقسم «تحليل المتاجر» (Store Analytics BI Suite)
# ════════════════════════════════════════════════════════════════════════════
# الأعمدة الزمنية كلها timestamptz؛ باندا يقرأها كـ UTC. الرياض = UTC+3 (بدون توقيت صيفي).
RIYADH_TZ_OFFSET_HOURS = 3


def _ksa_dt(s):
    """سلسلة/عمود وقت من القاعدة → ‏Timestamp‏ naive بتوقيت الرياض (للعرض والمقارنة).
    يتعامل مع tz-aware (timestamptz) أو naive أو نص؛ errors='coerce' للقيم الفاسدة."""
    return (pd.to_datetime(s, utc=True, errors="coerce").dt.tz_localize(None)
            + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
_SA_ARABIC_DAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


@st.cache_data(ttl=60, show_spinner=False)
def _sa_load_actions() -> pd.DataFrame:
    """
    كل أحداث التفاعل + بيانات الجهاز/الموقع للمستخدم (LEFT JOIN على bot_users).
    مخزّنة 60 ثانية — توازن بين حداثة الترند وحماية الـ DB من الضغط.
    ⚠️ ملاحظة أداء: لو تجاوزت action_logs ~100 ألف صف، حوّل التجميع إلى SQL
    (FILTER / GROUP BY) بدل سحب الخام كاملاً إلى pandas.
    """
    conn = get_conn()
    try:
        conn.rollback()
        return pd.read_sql(
            """
            SELECT a.action_time, a.action_type, a.store_id, a.user_id,
                   COALESCE(a.source, 'bot')      AS source,
                   a.device_class,                              -- web: desktop/mobile/tablet/bot
                   a.is_datacenter, a.is_proxy, a.quality_score,
                   a.city          AS geo_city,                 -- web geo (من إثراء action_logs)
                   a.country_code,
                   encode(a.ip_hash, 'hex') AS ip_hex,          -- بصمة ثابتة لزائر الويب المجهول
                   bu.device_type, bu.city AS bu_city, bu.country, bu.lang,
                   bu.username     AS bu_username,              -- هوية تيليجرام
                   wu.display_name AS web_name,                 -- هوية الويب المسجّل
                   wu.email        AS web_email,
                   wu.phone_number AS web_phone,
                   wu.city         AS web_city,                 -- مدينة التسجيل (الويب)
                   wu.telegram_username AS web_tg               -- تيليجرام مربوط بحساب الويب
            FROM   action_logs a
            LEFT JOIN bot_users bu ON bu.telegram_id = a.user_id
            LEFT JOIN web_users wu ON wu.id = a.user_id AND a.source = 'web'
            WHERE  a.action_type IN ('click_link', 'copy_coupon', 'search')
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data(ttl=180, show_spinner=False)
def _sa_load_master() -> pd.DataFrame:
    """
    بيانات المتاجر للعرض. الاسم المعتمد عربي دائماً = store_id (نون، شاهد، …)
    وليس name_en الإنجليزي. DISTINCT ON يزيل تكرار نفس store_id (يفضّل صفاً بشعار).
    مخزّنة 3 دقائق.
    """
    conn = get_conn()
    try:
        conn.rollback()
        return pd.read_sql(
            """
            SELECT DISTINCT ON (store_id)
                   store_id,
                   store_id                       AS store_name,
                   COALESCE(logo_url, '')         AS logo_url,
                   COALESCE(is_trending, 'عادي')  AS is_trending,
                   COALESCE(priority_score, 'عادي') AS priority_score,
                   COALESCE(is_promoted, false)   AS is_promoted,
                   last_time
            FROM   master
            WHERE  store_id IS NOT NULL AND store_id <> ''
            ORDER  BY store_id,
                      (CASE WHEN logo_url IS NOT NULL AND logo_url <> '' THEN 0 ELSE 1 END)
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data(ttl=180, show_spinner=False)
def _sa_load_searches() -> pd.DataFrame:
    """
    عمليات البحث من جدول direct_search (تشمل الويب والتيليجرام والداشبورد).
    أبحاث الموقع تأتي بـ platform='Web'؛ أبحاث البوت بـ 'TelegramBot'.
    """
    conn = get_conn()
    try:
        conn.rollback()
        return pd.read_sql(
            """
            SELECT search_keyword, store_id, COALESCE(platform, '') AS platform,
                   user_found, search_date
            FROM   direct_search
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def _sa_load_favorites() -> pd.DataFrame:
    """
    مفضلة المستخدمين الموحّدة (user_favorites) + هوية المالك.
    كل صف = (شخص واحد × متجر واحد) — UNIQUE في الجدول يمنع التكرار، فعدّ
    الصفوف لكل متجر = عدد الأشخاص الذين فضّلوه. مخزّنة 60 ثانية للترند.
    """
    conn = get_conn()
    try:
        conn.rollback()
        return pd.read_sql(
            """
            SELECT uf.store_id,
                   -- migration_028: kind discriminator + category_name (NULL لو 'store')
                   COALESCE(uf.kind, 'store') AS kind,
                   uf.category_name,
                   uf.platform, uf.created_at,
                   uf.web_user_id, uf.telegram_id,
                   bu.username     AS bu_username,   -- هوية تيليجرام (بوت/ميني)
                   bu.city         AS bu_city,
                   wu.display_name AS web_name,       -- هوية ويب مسجّل
                   wu.email        AS web_email,
                   wu.phone_number AS web_phone,
                   wu.city         AS web_city,
                   wu.telegram_username AS web_tg
            FROM   user_favorites uf
            LEFT JOIN bot_users bu ON bu.telegram_id = uf.telegram_id
            LEFT JOIN web_users wu ON wu.id          = uf.web_user_id
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data(ttl=60, show_spinner=False)
def _sa_recent_raw(n: int = 20) -> pd.DataFrame:
    """آخر n عملية خام من action_logs (للتحقّق الشفّاف — بدون أي فلترة)."""
    conn = get_conn()
    try:
        conn.rollback()
        return pd.read_sql(
            """
            SELECT id, user_id, action_type, COALESCE(source, '') AS source,
                   store_id, action_time
            FROM   action_logs
            ORDER  BY action_time DESC
            LIMIT  %(n)s
            """,
            conn, params={"n": int(n)},
        )
    finally:
        conn.close()


@st.cache_data(ttl=300, show_spinner=False)
def _sa_web_users_count() -> int:
    """عدد مستخدمي الموقع المسجّلين (web_users). مخزّن 5 دقائق."""
    conn = get_conn()
    try:
        conn.rollback()
        return int(pd.read_sql("SELECT COUNT(*) AS n FROM web_users", conn).iloc[0]["n"])
    except Exception:
        return 0
    finally:
        conn.close()


def _sa_pct(part, whole) -> float:
    return (part / whole * 100.0) if whole else 0.0


def _sa_wow(curr, prev) -> float:
    """نمو أسبوعي %. يرجّع NaN لو الأسبوع السابق صفر (لا أساس للمقارنة = متجر جديد)."""
    if prev and prev > 0:
        return (curr - prev) / prev * 100.0
    return float("nan")


def _sa_growth_color(val):
    if pd.isna(val):
        return "color: #9CA3AF"
    if val > 0:
        return "color: #059669; font-weight: 700"
    if val < 0:
        return "color: #DC2626; font-weight: 700"
    return "color: #6B7280"


def _sa_fmt_growth(val) -> str:
    if pd.isna(val):
        return "🆕 جديد"
    if val > 0:
        return f"▲ {val:.0f}%"
    if val < 0:
        return f"▼ {abs(val):.0f}%"
    return "▬ 0%"


def _sa_hourly_fig(d: pd.DataFrame, title: str | None = None, include_search: bool = True):
    """
    رسم خطي بالساعة (0–23 بتوقيت الرياض) للمؤشرات: نقرات / نسخ (+ بحث اختيارياً).
    الويب لا يسجّل البحث في action_logs (يُسجَّل في direct_search)، فنخفي خط البحث
    عن رسوم الويب بـ include_search=False لتفادي خط صفر مُضلِّل.
    """
    cols_src = (["search", "click_link", "copy_coupon"] if include_search
                else ["click_link", "copy_coupon"])
    piv = (d.groupby(["hour", "action_type"]).size()
           .unstack(fill_value=0).reindex(range(24), fill_value=0))
    for c in cols_src:
        if c not in piv.columns:
            piv[c] = 0
    piv = piv.rename(columns={"search": "بحث", "click_link": "نقرات الروابط",
                              "copy_coupon": "نسخ الكوبونات"})
    _labels = ([("بحث"), "نقرات الروابط", "نسخ الكوبونات"] if include_search
               else ["نقرات الروابط", "نسخ الكوبونات"])
    piv = piv[_labels]
    piv.index.name = "الساعة"
    long = piv.reset_index().melt(id_vars="الساعة", var_name="النوع", value_name="العدد")
    long["الساعة"] = long["الساعة"].map(lambda h: f"{h:02d}:00")
    fig = px.line(long, x="الساعة", y="العدد", color="النوع", markers=True, title=title)
    fig.update_layout(xaxis_title="الساعة (توقيت الرياض)", yaxis_title="عدد الأحداث",
                      legend_title_text="النوع")
    return apply_brand_theme(fig)


def _sa_prevnow(prev, now) -> str:
    """صيغة عربية واضحة لمقارنة أسبوعية: القيمة الحالية ثم السابقة بين قوسين."""
    return f"{int(now)} (كان {int(prev)})"


def _sa_metric_hourly(d: pd.DataFrame, action_type: str, label: str):
    """رسم عمودي لمؤشر واحد (نقرات / نسخ / بحث) موزّعاً على 24 ساعة بتوقيت الرياض."""
    s = (d[d["action_type"] == action_type].groupby("hour").size()
         .reindex(range(24), fill_value=0))
    fig = px.bar(x=[f"{h:02d}:00" for h in range(24)], y=s.values,
                 title=f"{label} حسب الساعة (توقيت الرياض)")
    fig.update_layout(xaxis_title="الساعة", yaxis_title="العدد")
    return apply_brand_theme(fig)


def _sa_render_category(df_cat: pd.DataFrame, empty_msg: str) -> None:
    """
    يعرض تفاصيل فئة متاجر (صاعدة / هابطة / خاملة): جدول «سابق → حالي» لكل مؤشر
    + تفسير سطري لكل متجر يوضّح بالضبط ما الذي تغيّر.
    """
    if df_cat.empty:
        st.info(empty_msg)
        return
    table = pd.DataFrame({
        "المتجر": df_cat["store_name"].values,
        "نقرات الروابط": df_cat.apply(lambda r: _sa_prevnow(r["cl_prev"], r["cl_now"]), axis=1).values,
        "نسخ الكوبونات": df_cat.apply(lambda r: _sa_prevnow(r["co_prev"], r["co_now"]), axis=1).values,
        "عمليات البحث": df_cat.apply(lambda r: _sa_prevnow(r["se_prev"], r["se_now"]), axis=1).values,
        "الإجمالي": df_cat.apply(lambda r: _sa_prevnow(r["p7"], r["t7"]), axis=1).values,
        "التغير الأسبوعي": df_cat["wow"].apply(_sa_fmt_growth).values,
    })
    st.dataframe(table, hide_index=True, width='stretch')
    st.markdown("**🔎 تفسير سريع لكل متجر — وش بالضبط اللي تغيّر:**")
    for r in df_cat.itertuples():
        changed = []
        if r.cl_now != r.cl_prev: changed.append(f"النقرات ({int(r.cl_prev)}→{int(r.cl_now)})")
        if r.co_now != r.co_prev: changed.append(f"النسخ ({int(r.co_prev)}→{int(r.co_now)})")
        if r.se_now != r.se_prev: changed.append(f"البحث ({int(r.se_prev)}→{int(r.se_now)})")
        changed_txt = "، ".join(changed) if changed else "لا تغيّر يُذكر"
        if r.t7 == 0:
            st.markdown(f"- **{r.store_name}** — توقّف تماماً هذا الأسبوع (كان {int(r.p7)} حدثاً). "
                        f"المتأثر: {changed_txt}")
        elif pd.isna(r.wow):
            st.markdown(f"- **{r.store_name}** — نشاط جديد هذا الأسبوع ({int(r.t7)} حدثاً). "
                        f"التفاصيل: {changed_txt}")
        else:
            st.markdown(f"- **{r.store_name}** — الإجمالي من {int(r.p7)} إلى {int(r.t7)} "
                        f"({_sa_fmt_growth(r.wow)}). التفاصيل: {changed_txt}")


def _sa_groq_report(payload: dict) -> tuple[str | None, str | None]:
    """
    تقرير استشاري مؤتمت عبر Groq (Llama 3.3 70B) — استدعاء REST مباشر
    (OpenAI-compatible) باستخدام requests، فلا حاجة لمكتبة openai محلياً.
    يرجّع (نص_التقرير, رسالة_خطأ).
    """
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None, ("GROQ_API_KEY غير مضبوط في ملف .env المحلي. أضف السطر "
                      "`GROQ_API_KEY=...` (نفس مفتاح الإنتاج) ثم أعد التشغيل.")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    system = (
        "أنت مستشار ذكاء أعمال محترف لمنصة DealPulse KSA (نبض الصفقات) — منصة "
        "كوبونات خصم في السعودية. تحلّل بيانات أداء المتاجر وتُصدر تقريراً "
        "استشارياً عملياً بالعربية الفصحى المبسّطة.\n"
        "قواعد صارمة:\n"
        "1. كل توصية تذكر اسم متجر محدد من البيانات (ممنوع التوصيات العامة).\n"
        "2. ركّز على الإيرادات: تجديد الكوبونات، توسيع المتاجر الصاعدة، معالجة "
        "الهابطة/الخاملة، وضبط توقيت Broadcast الإشعارات حسب أوقات الذروة.\n"
        "3. اربط كل توصية برقم من البيانات (نمو %، نقرات، نسخ، ساعة الذروة).\n"
        "4. نبرة استشارية مهنية ومختصرة، دون إكثار من الإيموجي.\n"
        "أخرج التقرير بصيغة Markdown منظّم بهذه العناوين بالضبط:\n"
        "## 🔎 خلاصة تنفيذية\n## 🚀 فرص النمو\n## ⚠️ تنبيهات وخمول\n"
        "## 🎯 توصيات تشغيلية (مرتّبة بالأولوية)"
    )
    user = (
        "حلّل بيانات أداء المتاجر التالية وأصدر التقرير الاستشاري:\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```"
    )
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.4,
                "max_tokens": 1600,
            },
            timeout=60,
        )
        if resp.status_code >= 400:
            return None, f"Groq HTTP {resp.status_code}: {resp.text[:240]}"
        data = resp.json()
        return data["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


def _sa_build_excel(summary_df: pd.DataFrame, daily_df: "pd.DataFrame | None",
                    store_label: str, period_label: str) -> bytes:
    """تقرير Excel احترافي مُهيّأ للمعلنين (هوية نبض الصفقات + RTL)."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book
        title_fmt = wb.add_format({"bold": True, "font_size": 16, "font_color": "#047857"})
        sub_fmt = wb.add_format({"italic": True, "font_color": "#6B7280", "font_size": 10})
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#10B981", "font_color": "white",
                                 "border": 1, "align": "center", "valign": "vcenter"})

        summary_df.to_excel(writer, sheet_name="ملخص الأداء", startrow=4, index=False)
        ws = writer.sheets["ملخص الأداء"]
        ws.right_to_left()
        ws.write("A1", "تقرير أداء المتاجر — نبض الصفقات KSA", title_fmt)
        ws.write("A2", f"المتجر: {store_label}", sub_fmt)
        ws.write("A3", f"الفترة: {period_label}  |  تاريخ التوليد: {date.today():%Y-%m-%d}", sub_fmt)
        for c, col in enumerate(summary_df.columns):
            ws.write(4, c, col, hdr_fmt)
        ws.autofit()

        if daily_df is not None and not daily_df.empty:
            daily_df.to_excel(writer, sheet_name="التفصيل اليومي", startrow=1, index=False)
            ws2 = writer.sheets["التفصيل اليومي"]
            ws2.right_to_left()
            for c, col in enumerate(daily_df.columns):
                ws2.write(1, c, col, hdr_fmt)
            ws2.autofit()
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════════
#  🔥 محرّك «الترند» — نقاط موزونة + قاعدة Anti-Spam (2 لكل ساعة، تبريد 5 ساعات)
# ════════════════════════════════════════════════════════════════════════════
# نقاط: نقر=1، بحث=2، نسخ=3، مفضلة=4 (تختفي تلقائياً لو ألغى المستخدم المفضلة
# لأن الجدول hard-delete على الإزالة — لا حاجة لجدول إزالة منفصل).
_TREND_POINTS = {"click_link": 1, "search": 2, "copy_coupon": 3}
_TREND_FAV_POINTS = 4


def _sa_person_key(source: str, user_id, ip_hex) -> str:
    """
    هوية موحّدة للشخص لأغراض Anti-Spam — منفصلة لكل مصدر (web/miniapp/bot) حتى
    لا تنخلط فترات التبريد بين المنصات. النسخة المسجَّلة (user_id) تتفوّق دائماً
    على البصمة المجهولة (ip_hex). nan-safe.
    """
    src = (source or "bot").strip().lower()
    prefix = ("web" if src == "web"
              else "mini" if src in ("telegram_miniapp", "miniapp")
              else "bot")
    if user_id is not None and not (isinstance(user_id, float) and pd.isna(user_id)):
        try:
            return f"{prefix}:u{int(user_id)}"
        except Exception:
            return f"{prefix}:u{user_id}"
    if ip_hex and isinstance(ip_hex, str):
        return f"{prefix}:ip{ip_hex[:12]}"
    return f"{prefix}:anon"


def _sa_apply_anti_spam(df: pd.DataFrame, time_col: str = "action_time") -> pd.DataFrame:
    """
    يطبّق قاعدة anti-spam على كل (شخص × متجر × نوع الفعل) بشكل مستقل:
      * أول 2 فعل خلال أول ساعة من بداية النافذة → counted=True
      * من ساعة 1 إلى ساعة 5 → counted=False (لا تتحول لنقاط، رغم تنفيذها)
      * بعد 5 ساعات من بداية النافذة → نافذة جديدة تفتح بهذا الفعل
    يفترض وجود الأعمدة: person_key, store_id, action_type, time_col.
    يُرجع نسخة بعمود جديد 'counted' bool.
    """
    if df.empty:
        out = df.copy()
        out["counted"] = pd.Series([], dtype=bool)
        return out
    d = df.sort_values(["person_key", "store_id", "action_type", time_col]).reset_index(drop=True).copy()
    counted = [False] * len(d)
    last_key = (None, None, None)
    win_open: pd.Timestamp | None = None
    count_in_win = 0
    times = d[time_col].to_list()
    keys = list(zip(d["person_key"], d["store_id"], d["action_type"]))
    one_hour = pd.Timedelta(hours=1)
    five_hours = pd.Timedelta(hours=5)
    for i in range(len(d)):
        k = keys[i]
        t = times[i]
        if k != last_key:
            last_key = k
            win_open = t
            count_in_win = 1
            counted[i] = True
            continue
        delta = t - win_open
        if delta >= five_hours:
            win_open = t
            count_in_win = 1
            counted[i] = True
        elif delta < one_hour and count_in_win < 2:
            count_in_win += 1
            counted[i] = True
        else:
            counted[i] = False
    d["counted"] = counted
    return d


def _sa_compute_trend(df_logs: pd.DataFrame, df_fav: pd.DataFrame,
                       window_start: pd.Timestamp, window_end: pd.Timestamp,
                       active_ids: set) -> pd.DataFrame:
    """
    يحسب نقاط الترند لكل متجر داخل نافذة زمنية (يومي/أسبوعي).
    منطق صحيح: Anti-spam يُطبَّق على *كامل* تاريخ الأفعال (حتى لا تُعدّ نسخة فجر اليوم
    استمراراً لجلسة الأمس وتُمنع خطأً)، ثم نختار counted=True داخل النافذة فقط.
    يُرجع DataFrame مرتّباً بالنقاط تنازلياً مع تفصيل لكل مؤشّر.
    """
    # ── 1. الأفعال (نقر/بحث/نسخ) ───────────────────────────────────────────
    if df_logs is not None and not df_logs.empty:
        d = df_logs.copy()
        d = d[d["store_id"].notna() & (d["store_id"].astype(str).str.strip() != "")]
        d = d[d["store_id"].isin(active_ids)]
        d["person_key"] = d.apply(
            lambda r: _sa_person_key(r.get("source"), r.get("user_id"), r.get("ip_hex")),
            axis=1,
        )
        d = _sa_apply_anti_spam(d, time_col="action_time")
        win_mask = (d["action_time"] >= window_start) & (d["action_time"] <= window_end)
        d_win = d[win_mask & d["counted"]].copy()
        clicks = d_win[d_win["action_type"] == "click_link"].groupby("store_id").size()
        searches = d_win[d_win["action_type"] == "search"].groupby("store_id").size()
        copies = d_win[d_win["action_type"] == "copy_coupon"].groupby("store_id").size()
        users_uniq = d_win.groupby("store_id")["person_key"].nunique()
    else:
        clicks = searches = copies = users_uniq = pd.Series(dtype="int64")
        d_win = pd.DataFrame(columns=["store_id", "action_type", "person_key", "action_time", "counted"])

    # ── 2. المفضلة (تنخصم تلقائياً عند الإزالة — DELETE في الجدول) ─────────
    if df_fav is not None and not df_fav.empty:
        f = df_fav.copy()
        if "kind" in f.columns:
            f = f[f["kind"].fillna("store") == "store"]
        if not f.empty:
            f = f[f["store_id"].isin(active_ids)]
            f_win = f[(f["created_at"] >= window_start) & (f["created_at"] <= window_end)]
            favs = f_win.groupby("store_id").size()
        else:
            favs = pd.Series(dtype="int64")
    else:
        favs = pd.Series(dtype="int64")

    # ── 3. تجميع النتيجة ───────────────────────────────────────────────────
    all_ids = sorted(active_ids)
    out = pd.DataFrame({"store_id": all_ids})
    out["clicks_counted"] = out["store_id"].map(clicks).fillna(0).astype(int)
    out["searches_counted"] = out["store_id"].map(searches).fillna(0).astype(int)
    out["copies_counted"] = out["store_id"].map(copies).fillna(0).astype(int)
    out["favs_added"] = out["store_id"].map(favs).fillna(0).astype(int)
    out["unique_users"] = out["store_id"].map(users_uniq).fillna(0).astype(int)
    out["score_clicks"] = out["clicks_counted"] * _TREND_POINTS["click_link"]
    out["score_searches"] = out["searches_counted"] * _TREND_POINTS["search"]
    out["score_copies"] = out["copies_counted"] * _TREND_POINTS["copy_coupon"]
    out["score_favs"] = out["favs_added"] * _TREND_FAV_POINTS
    out["total_score"] = (out["score_clicks"] + out["score_searches"]
                          + out["score_copies"] + out["score_favs"])
    out = (out[out["total_score"] > 0]
           .sort_values(["total_score", "unique_users"], ascending=[False, False])
           .reset_index(drop=True))
    out.insert(0, "rank", out.index + 1)
    return out


# --- القائمة الجانبية ---
if _logo_b64:
    st.sidebar.markdown(f"""
<div style="text-align:center; padding:10px 8px 12px 8px; border-bottom:1px solid {BRAND["border"]}; margin-bottom:10px;">
<img src="data:image/jpeg;base64,{_logo_b64}"
        style="width:90px; border-radius:8px;" />
</div>
""", unsafe_allow_html=True)

# ── مبدّل المظهر: ليلي / نهاري (يحفظ الاختيار في الجلسة ويعيد بناء الثيم) ──
st.sidebar.radio(
    "🎨 المظهر",
    ["🌙 ليلي", "☀️ نهاري"],
    key="ui_theme_radio",
    horizontal=True,
)

_MAIN_PAGES = [
"إدخال بيانات الماستر", "الاستعلام والتعديل", "🎟️ أكواد إضافية", "جدول الكوبونات",
"📦 أرشيف المنتهية",
"جدول الأقسام", "البحث عن كود", "طلبات الأكواد", "بيانات المستخدمين",
"مستخدمو الموقع",
]
_ANALYSIS_PAGES = [
"🎬 إضافة استوري",
"🎬 تحليلات الستوري",
"تحليل المتاجر", "تحليل الأقسام",
"تحليل طلبات الأكواد", "تحليل المستخدمين",
]
_OTHER_PAGES = [
"📣 بلاغات الأكواد",  # ← Migration 029: بلاغات لا يعمل + إدارة المتاجر المسحوبة
"🎯 بناء الشرائح", "مركز الإشعارات", "لوحة القيادة", "مركز الدعم",
"استوديو المحتوى", "🎨 الثيمات",
"محرّك SEO", "📈 أداء SEO", "📤 الصفحات المنشورة", "🎯 محرك الفرص", "سجل التدقيق",
"🛰️ متابعة المنصة",
"🩺 تشخيص النشر",
]

# 1. تهيئة حالة الصفحة إذا لم تكن موجودة
if "page" not in st.session_state:
    st.session_state.page = _MAIN_PAGES[0]

_cur = st.session_state.page

# 2. دالة ذكية لإدارة التنقل تمنع التكرار اللانهائي (Infinite Loop)
def handle_nav(key):
    if st.session_state[key]:
        st.session_state.page = st.session_state[key]

# --- القائمة الرئيسية ---
with st.sidebar.expander("📋 القائمة الرئيسية", expanded=(_cur in _MAIN_PAGES)):
    # نستخدم 0 كافتراضي لكن الـ on_change هي المتحكم الفعلي
    _idx = _MAIN_PAGES.index(_cur) if _cur in _MAIN_PAGES else 0
    st.radio(
        "القائمة الرئيسية",
        _MAIN_PAGES,
        index=_idx, 
        key="r_main", 
        on_change=handle_nav, 
        args=("r_main",), 
        label_visibility="collapsed"
    )

# --- قائمة التحليل ---
with st.sidebar.expander("📊 التحليل", expanded=(_cur in _ANALYSIS_PAGES)):
    _idx2 = _ANALYSIS_PAGES.index(_cur) if _cur in _ANALYSIS_PAGES else 0
    st.radio(
        "التحليل",
        _ANALYSIS_PAGES,
        index=_idx2, 
        key="r_analysis", 
        on_change=handle_nav, 
        args=("r_analysis",), 
        label_visibility="collapsed"
    )

# --- أدوات متقدمة ---
with st.sidebar.expander("🔧 أدوات متقدمة", expanded=(_cur in _OTHER_PAGES)):
    _idx3 = _OTHER_PAGES.index(_cur) if _cur in _OTHER_PAGES else 0
    st.radio(
        "أدوات متقدمة",
        _OTHER_PAGES,
        index=_idx3, 
        key="r_other", 
        on_change=handle_nav, 
        args=("r_other",), 
        label_visibility="collapsed"
    )

# تحديث المتغير النهائي لعرض محتوى الصفحة الصحيحة
page = st.session_state.page

# --- الصفحة الأولى: إدخال بيانات الماستر (نسخة "بو سعود" المريحة) ---
# --- الصفحة الأولى: إدخال بيانات الماستر (نسخة بو سعود الاحترافية بالبحث الفوري) ---
if page == "إدخال بيانات الماستر":
    st.header("📝 إضافة متجر جديد للمحرك")
    if st.button("🔄 تحديث البيانات الآن"):
            st.rerun()

    # بعد حفظ ناجح فقط: نظّف حقول النموذج واعرض رسالة النجاح (يُنفَّذ في إعادة التشغيل بعد الحفظ).
    # عند فشل التحقق لا نمسح شيئاً — تبقى كل البيانات ليكمل المستخدم الحقل الناقص فقط.
    if st.session_state.pop("_master_clear_form", False):
        for _k in (
            "m_store_id", "m_name_en", "m_aff_link", "m_pub_coupon", "m_disc_val",
            "m_extra_offer", "m_extra_offer_en", "m_store_bio", "m_store_bio_en",
            "m_description", "m_my_coupon", "m_source_platform",
            "logo_url_add", "logo_upload_add", "is_promoted_add",
        ):
            st.session_state.pop(_k, None)
    _master_ok_msg = st.session_state.pop("_master_success_msg", None)
    if _master_ok_msg:
        st.success(_master_ok_msg)
        st.balloons()

    # 1. تهيئة قوائم التاقات (AR + EN) في Session State
    if 'custom_tags_list' not in st.session_state:
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT trim(t) AS tag
                FROM master,
                        unnest(string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',')) AS t
                WHERE trim(t) <> ''
            """)
            db_tags = [row[0] for row in cur.fetchall() if row[0]]
            conn.close()
            base = ["أزياء", "عطور", "إلكترونيات", "منزل", "أطفال", "تجميل", "سفر"]
            st.session_state.custom_tags_list = sorted(list(set(base + db_tags)))
        except:
            st.session_state.custom_tags_list = ["أزياء", "عطور", "إلكترونيات", "منزل", "أطفال", "تجميل", "سفر"]

    if 'custom_tags_list_en' not in st.session_state:
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT trim(t) AS tag
                FROM master,
                        unnest(string_to_array(trim(both '{}' from COALESCE(store_tags_en, '')), ',')) AS t
                WHERE trim(t) <> ''
            """)
            db_tags_en = [row[0] for row in cur.fetchall() if row[0]]
            conn.close()
            base_en = ["Fashion", "Perfumes", "Electronics", "Home", "Kids", "Beauty", "Travel"]
            st.session_state.custom_tags_list_en = sorted(list(set(base_en + db_tags_en)))
        except:
            st.session_state.custom_tags_list_en = ["Fashion", "Perfumes", "Electronics", "Home", "Kids", "Beauty", "Travel"]

    # 2. إدارة الأقسام بلغتين (AR + EN)
    st.subheader("🏷️ إدارة الأقسام (Tags)")

    # ─── الصف العربي ───
    st.markdown("**عربي:**")
    t1, t2, t3 = st.columns([2, 1, 0.5])
    with t1:
        selected_tags = st.multiselect(
            "🔍 ابحث عن القسم بالعربي:",
            options=st.session_state.custom_tags_list,
            placeholder="اكتب هنا للبحث (مثلاً: عطور)..."
        )
    with t2:
        new_tag_input = st.text_input("✨ تاق جديد (AR):", key="quick_tag_ar")
    with t3:
        st.write(" ")
        if st.button("➕ إضافة AR", key="add_tag_ar"):
            if new_tag_input and new_tag_input not in st.session_state.custom_tags_list:
                st.session_state.custom_tags_list.append(new_tag_input)
                st.toast(f"تمت إضافة '{new_tag_input}'")
                st.rerun()

    # ─── الصف الإنجليزي ───
    st.markdown("**English:**")
    e1, e2, e3 = st.columns([2, 1, 0.5])
    with e1:
        selected_tags_en = st.multiselect(
            "🔍 Search for English tag:",
            options=st.session_state.custom_tags_list_en,
            placeholder="Type to search (e.g. Perfumes)..."
        )
    with e2:
        new_tag_input_en = st.text_input("✨ New tag (EN):", key="quick_tag_en")
    with e3:
        st.write(" ")
        if st.button("➕ Add EN", key="add_tag_en"):
            if new_tag_input_en and new_tag_input_en not in st.session_state.custom_tags_list_en:
                st.session_state.custom_tags_list_en.append(new_tag_input_en)
                st.toast(f"Added '{new_tag_input_en}'")
                st.rerun()

    st.divider()

    # 3. نموذج الإدخال — صفوف AR/EN جنباً إلى جنب
    with st.form("master_final_form", clear_on_submit=False):
        # الصف 1: اسم المتجر AR + EN
        c_ar1, c_en1 = st.columns(2)
        store_id = c_ar1.text_input("🏪 اسم المتجر (عربي/ID)", key="m_store_id")
        name_en  = c_en1.text_input("🏪 Store Name (English)", key="m_name_en")

        # الصف 2: روابط/كوبون/خصم (لا يحتاج ترجمة)
        col_a, col_b, col_c = st.columns(3)
        aff_link   = col_a.text_input("🔗 رابط الأفلييت", key="m_aff_link")
        pub_coupon = col_b.text_input("🎟️ كوبون العملاء", key="m_pub_coupon")
        disc_val   = col_c.text_input("💰 نسبة الخصم", key="m_disc_val")

        # الصف 3: عرض إضافي AR + EN
        e_ar, e_en = st.columns(2)
        extra_offer    = e_ar.text_input("➕ عرض إضافي (عربي)", key="m_extra_offer")
        extra_offer_en = e_en.text_input("➕ Extra Offer (English)", key="m_extra_offer_en")

        # الصف 4: وصف المتجر AR + EN
        b_ar, b_en = st.columns(2)
        store_bio    = b_ar.text_area("📝 وصف المتجر (عربي)", key="m_store_bio")
        store_bio_en = b_en.text_area("📝 Store Description (English)", key="m_store_bio_en")

        # الصف 4.5: تفاصيل العرض — تُستخدم في منشورات السوشيال
        description = st.text_area(
            "📣 تفاصيل العرض (تُنشر على منصات السوشيال)",
            placeholder="مثال: خصم حصري على جميع منتجات القسم النسائي حتى نهاية الأسبوع. شامل التوصيل المجاني.",
            height=90,
            help="هذا النص يظهر في المنشورات التلقائية على X, Instagram, Facebook, Pinterest, Telegram, Discord, Threads, LinkedIn.",
            key="m_description",
        )

        st.divider()

        # الصف 5: الأهمية + التواريخ + عمولتي
        col7, col8, col9, col10 = st.columns(4)
        priority   = col7.selectbox("🚀 الأهمية", ["عادي", "مهم", "عاجل", "عاجل جداً"])
        date_start = col8.date_input("📅 تاريخ البداية", datetime.date.today())
        date_end   = col9.date_input("📅 تاريخ الانتهاء", datetime.date.today() + datetime.timedelta(days=30))
        my_coupon  = col10.text_input("💵 عمولتي (كود التتبع)", key="m_my_coupon")

        # الصف 5.5: مصدر الكود (من أي منصة تابعة)
        source_platform = st.text_input(
            "🛰️ من أين (المنصة التابعة لهذا الكود)",
            placeholder="مثال: ArabClicks, CJ Affiliate, تواصل مباشر...",
            help="اكتب اسم المنصة التي جاء منها هذا الكود — مفيد عند تجديد الكود لاحقاً.",
            key="m_source_platform",
        )

        # الصف 6: شعار المتجر
        st.divider()
        st.markdown("**🖼️ شعار المتجر (اختياري)**")
        logo_col1, logo_col2 = st.columns([1, 2])
        with logo_col1:
            logo_file = st.file_uploader(
                "رفع ملف الشعار",
                type=["png", "jpg", "jpeg", "webp"],
                key="logo_upload_add",
                help="سيُرفع تلقائياً إلى Cloudinary لو كانت الإعدادات موجودة"
            )
        with logo_col2:
            logo_url_input = st.text_input(
                "أو الصق رابط الشعار مباشرة",
                placeholder="https://example.com/logo.png",
                key="logo_url_add"
            )
            if logo_url_input:
                st.image(logo_url_input, width=80)

        # ملاحظة: الإشهار (is_promoted) ووسائط الستوري انتقلا لصفحة «🎬 إضافة استوري».
        # المتجر الجديد يُحفظ غير مُشهَر افتراضياً؛ تُفعّله وترفع له ستوري من هناك.
        st.divider()
        st.caption("📣 الإشهار ورفع ستوري (فيديو/صورة) صار من صفحة «🎬 إضافة استوري» بعد حفظ المتجر.")

        if st.form_submit_button("🚀 حفظ المتجر والبيانات"):
            # validation: كل الحقول AR + EN إجبارية
            required = {
                "اسم المتجر (AR)":  store_id,
                "Store Name (EN)": name_en,
                "عرض إضافي (AR)":  extra_offer,
                "Extra Offer (EN)": extra_offer_en,
                "وصف المتجر (AR)": store_bio,
                "Store Description (EN)": store_bio_en,
                "رابط الأفلييت":    aff_link,
                "كوبون العملاء":    pub_coupon,
                "نسبة الخصم":       disc_val,
            }
            missing = [k for k, v in required.items() if not (v or "").strip()]
            if not selected_tags:    missing.append("Tags (AR)")
            if not selected_tags_en: missing.append("Tags (EN)")
            if missing:
                st.warning(
                    "⚠️ ينقصك إكمال: " + " ، ".join(missing)
                    + "\n\n✅ بياناتك محفوظة كما هي — أكمل الناقص فقط واضغط حفظ مرة ثانية."
                )
            else:
                # ─── حل رابط الشعار ───────────────────────────────────────
                final_logo_url = (logo_url_input or "").strip()
                if logo_file and not final_logo_url:
                    uploaded = _upload_logo(logo_file.read(), store_id.strip())
                    if uploaded:
                        final_logo_url = uploaded
                    elif not _CLOUDINARY_OK:
                        st.error(
                            "❌ الشعار **ما انرفع** — Cloudinary غير مضبوط على هذه البيئة، "
                            "فالمتجر بينحفظ **بدون شعار**. أضف متغيّرات `CLOUDINARY_CLOUD_NAME` "
                            "و`CLOUDINARY_API_KEY` و`CLOUDINARY_API_SECRET` على خدمة الداشبورد، "
                            "ثم عدّل المتجر وأعد رفع الشعار. (أو الصق رابط شعار مباشر في الحقل المجاور)."
                        )
                    else:
                        st.error(
                            "❌ فشل رفع الشعار إلى Cloudinary — المتجر بينحفظ **بدون شعار**. "
                            "راجع رسالة الخطأ أعلاه، ثم عدّل المتجر وأعد الرفع."
                        )
                saved_ok = False
                try:
                    conn = get_conn()
                    cur = conn.cursor()
                    tags_ar_lit = "{" + ",".join(selected_tags) + "}"
                    tags_en_lit = "{" + ",".join(selected_tags_en) + "}"
                    _src_val = (source_platform or "").strip() or None
                    cur.execute("""
                        INSERT INTO master
                            (store_id, name_en, affiliate_link, public_coupon,
                                extra_offer, extra_offer_en, store_bio, store_bio_en,
                                description,
                                priority_score, discount_value, store_tags, store_tags_en,
                                my_coupon, first_time, last_time,
                                total_coupon_copies, total_link_clicks, is_trending,
                                logo_url, is_promoted, source_platform)
                        VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s, %s,%s,%s,%s, %s,%s,%s, 0,0,'عادي', %s, %s, %s)
                        RETURNING id
                    """, (
                        store_id, name_en, aff_link, pub_coupon,
                        extra_offer, extra_offer_en, store_bio, store_bio_en,
                        (description or None),
                        priority, disc_val, tags_ar_lit, tags_en_lit,
                        my_coupon, date_start, date_end,
                        final_logo_url or None,
                        False,  # is_promoted: يُفعَّل لاحقاً من صفحة «🎬 إضافة استوري»
                        _src_val,
                    ))
                    new_master_id = cur.fetchone()[0]
                    # Week 4 — توليد cloaked_slug للمتجر الجديد (نفس تعبير backfill في migration_012)
                    cur.execute(
                        """
                        UPDATE master
                        SET cloaked_slug = substr(
                                md5(random()::text || clock_timestamp()::text || id::text), 1, 10)
                        WHERE id = %s AND (cloaked_slug IS NULL OR cloaked_slug = '')
                        """,
                        (new_master_id,),
                    )
                    conn.commit()
                    _trigger_social_broadcast(new_master_id)
                    st.session_state["_master_success_msg"] = (
                        f"✅ تم الحفظ! التاقات: {len(selected_tags)} AR / {len(selected_tags_en)} EN — النموذج جاهز لمتجر جديد."
                    )
                    st.session_state["_master_clear_form"] = True
                    saved_ok = True
                except Exception as e:
                    st.error(f"⚠️ مشكلة في القاعدة: {e}")
                finally:
                    conn.close()
                if saved_ok:
                    st.rerun()


    # --- الصفحة الثانية: الاستعلام والتعديل (نسخة تعريب الجدول والبيانات الحقيقية) ---
if page == "الاستعلام والتعديل":
    st.header("🔍 مركز التحكم والتعديل الشامل")

    if st.button("🔄 تحديث", key="qe_refresh", help="إعادة تحميل البيانات"):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

    # 1. بلوك البحث والتعديل العلوي
    search_id = st.number_input("📌 أدخل رقم الـ ID للبحث والتعديل:", min_value=1, step=1)

    if search_id:
        try:
            conn = get_conn()
            cur = conn.cursor(cursor_factory=extras.DictCursor)
            cur.execute("SELECT * FROM master WHERE id = %s", (search_id,))
            res = cur.fetchone()
        
            if res:
                with st.form("edit_master_arabic_columns"):
                    st.info(f"📍 تعديل بيانات متجر: {res['store_id']} (ID: {search_id})")

                    # الصف 1: اسم المتجر AR + EN
                    r1_ar, r1_en = st.columns(2)
                    u_store   = r1_ar.text_input("🏪 اسم المتجر (عربي/ID)", res['store_id'])
                    u_name_en = r1_en.text_input("🏪 Store Name (English)", res.get('name_en') or '')

                    # الصف 2: روابط/كوبون/خصم
                    r2c1, r2c2, r2c3 = st.columns(3)
                    u_aff  = r2c1.text_input("🔗 رابط الأفلييت", res['affiliate_link'])
                    u_pub  = r2c2.text_input("🎟️ كوبون العملاء", res['public_coupon'])
                    u_disc = r2c3.text_input("💰 نسبة الخصم", res['discount_value'])

                    # الصف 3: عرض إضافي AR + EN
                    r3_ar, r3_en = st.columns(2)
                    u_extra    = r3_ar.text_input("➕ عرض إضافي (عربي)", res['extra_offer'])
                    u_extra_en = r3_en.text_input("➕ Extra Offer (English)", res.get('extra_offer_en') or '')

                    # الصف 4: وصف المتجر AR + EN
                    r4_ar, r4_en = st.columns(2)
                    u_bio    = r4_ar.text_area("📝 وصف المتجر (عربي)", res['store_bio'])
                    u_bio_en = r4_en.text_area("📝 Store Description (English)", res.get('store_bio_en') or '')

                    # الصف 4.5: تفاصيل العرض — تُستخدم في منشورات السوشيال
                    u_description = st.text_area(
                        "📣 تفاصيل العرض (تُنشر على منصات السوشيال)",
                        value=res.get('description') or '',
                        height=90,
                        help="يُنشر تلقائياً فقط عند تغيير «كوبون العملاء» — التعديلات الأخرى لا تُطلق نشراً.",
                    )

                    st.divider()

                    # الصف 5: الأهمية + التواريخ + عمولتي
                    r5c1, r5c2, r5c3, r5c4 = st.columns(4)
                    p_list = ["عادي", "مهم", "عاجل", "عاجل جداً"]
                    u_prio  = r5c1.selectbox("🚀 الأهمية", p_list, index=p_list.index(res['priority_score']) if res['priority_score'] in p_list else 0)
                    u_start = r5c2.date_input("📅 تاريخ البداية", res['first_time'])
                    u_end   = r5c3.date_input("📅 تاريخ الانتهاء", res['last_time'])
                    u_mine  = r5c4.text_input("💵 عمولتي الخاصة", res['my_coupon'])

                    # الصف 5.5: مصدر الكود
                    u_source = st.text_input(
                        "🛰️ من أين (المنصة التابعة لهذا الكود)",
                        value=(res.get('source_platform') or ''),
                        placeholder="مثال: ArabClicks, CJ Affiliate, تواصل مباشر...",
                        help="يساعدك تعرف من أي منصة تابعة جاء كود هذا المتجر — مفيد عند تجديد الكود.",
                    )

                    # الصف 6: شعار المتجر
                    st.divider()
                    logo_edit_c1, logo_edit_c2 = st.columns([1, 2])
                    with logo_edit_c1:
                        u_logo = st.text_input("🖼️ رابط شعار المتجر", res.get('logo_url') or '')
                    with logo_edit_c2:
                        if u_logo:
                            st.image(u_logo, width=80, caption="معاينة الشعار الحالي")
                        else:
                            st.caption("لا يوجد شعار — الصق رابط في الحقل المجاور")

                    # الصف 7: إشهار / إعلان مدفوع
                    st.divider()
                    current_promoted = bool(res.get('is_promoted') or False)
                    u_promoted = st.checkbox(
                        "📣 إشهار (إعلان مدفوع) — يظهر في قسم «المتاجر المختارة»",
                        value=current_promoted,
                        key=f"is_promoted_edit_{search_id}",
                        help="فعّل أو ألغِ الإشهار لهذا المتجر بدون الحاجة لإعادة إدخال البيانات."
                    )
                    if u_promoted != current_promoted:
                        st.caption(
                            "🟢 سيتم تفعيل الإشهار عند الحفظ"
                            if u_promoted else
                            "⚪ سيتم إلغاء الإشهار عند الحفظ"
                        )

                    if st.form_submit_button("💾 حفظ التعديلات النهائية"):
                        # validation: AR + EN كلاهما إجباري
                        required = {
                            "اسم المتجر (AR)":      u_store,
                            "Store Name (EN)":      u_name_en,
                            "عرض إضافي (AR)":      u_extra,
                            "Extra Offer (EN)":     u_extra_en,
                            "وصف المتجر (AR)":     u_bio,
                            "Store Description (EN)": u_bio_en,
                        }
                        missing = [k for k, v in required.items() if not (v or "").strip()]
                        if missing:
                            st.warning("⚠️ الحقول التالية إجبارية: " + " ، ".join(missing))
                        else:
                            # ملاحظة: التاقات (store_tags / store_tags_en) لا تُعدَّل من هنا
                            _u_src_val = (u_source or "").strip() or None
                            cur.execute("""
                                UPDATE master SET
                                    store_id=%s, name_en=%s,
                                    affiliate_link=%s, public_coupon=%s,
                                    extra_offer=%s, extra_offer_en=%s,
                                    store_bio=%s,   store_bio_en=%s,
                                    description=%s,
                                    priority_score=%s, discount_value=%s, my_coupon=%s,
                                    first_time=%s, last_time=%s,
                                    logo_url=%s,
                                    is_promoted=%s,
                                    source_platform=%s
                                WHERE id=%s
                            """, (
                                u_store, u_name_en,
                                u_aff, u_pub,
                                u_extra, u_extra_en,
                                u_bio, u_bio_en,
                                (u_description or None),
                                u_prio, u_disc, u_mine,
                                u_start, u_end,
                                u_logo.strip() or None,
                                bool(u_promoted),
                                _u_src_val,
                                search_id,
                            ))
                            conn.commit()
                            st.success("✅ تم تحديث البيانات بنجاح.")
                            # نشر تلقائي فقط لما الكوبون يتغير (تجديد كود)
                            if (u_pub or '').strip() != (res.get('public_coupon') or '').strip():
                                _trigger_social_broadcast(search_id)
                            st.rerun()
            
                if st.button("🗑️ حذف السجل"):
                    cur.execute("DELETE FROM master WHERE id = %s", (search_id,))
                    conn.commit()
                    st.warning("تم الحذف.")
                    st.rerun()
            conn.close()
        except Exception as e:
            st.error(f"خطأ: {e}")

    st.divider()

    # 2. الجزء السفلي: الجدول بأسماء أعمدة عربية/إنجليزية وتلوين التاريخ
    try:
        conn = get_conn()
        conn.rollback()  # تنظيف أي transaction سابقة معلّقة

        # نفحص أولاً هل عمود is_promoted موجود في قاعدة البيانات المتصلة الحالية
        # عشان الجدول يشتغل سواء طُبّق migration_008 أو لا
        with conn.cursor() as _check:
            _check.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name='master' AND column_name='is_promoted'
                LIMIT 1
            """)
            _has_promoted = _check.fetchone() is not None

        if _has_promoted:
            query = """
                SELECT id, store_id, name_en, affiliate_link, public_coupon, discount_value,
                        priority_score, first_time, last_time, my_coupon,
                        store_bio, store_bio_en, extra_offer, extra_offer_en,
                        store_tags, store_tags_en,
                        COALESCE(is_promoted, FALSE) AS is_promoted
                FROM master
                ORDER BY COALESCE(is_promoted, FALSE) DESC, id DESC
            """
        else:
            query = """
                SELECT id, store_id, name_en, affiliate_link, public_coupon, discount_value,
                        priority_score, first_time, last_time, my_coupon,
                        store_bio, store_bio_en, extra_offer, extra_offer_en,
                        store_tags, store_tags_en
                FROM master
                ORDER BY id DESC
            """
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            base_cols = [
                'ID', 'اسم المتجر', 'Store Name (EN)', 'رابط الأفلييت', 'كوبون العملاء', 'نسبة الخصم',
                'الأهمية', 'تاريخ البداية', 'تاريخ الانتهاء', 'عمولتي الخاصة',
                'وصف المتجر', 'Description (EN)', 'عرض إضافي', 'Extra Offer (EN)',
                'تاقات', 'Tags (EN)',
            ]
            if _has_promoted:
                df['is_promoted'] = df['is_promoted'].apply(
                    lambda v: '📣 مُشهَر' if bool(v) else '—'
                )
                df.columns = base_cols + ['الإشهار']
            else:
                df.columns = base_cols
                st.info(
                    "ℹ️ ميزة «الإشهار» غير مفعّلة على هذه القاعدة بعد. "
                    "شغّل `migration_008_is_promoted.sql` على Railway لتفعيلها."
                )

            # زر التحميل الماستر
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 تحميل الماستر (Excel)", output.getvalue(), f"Master_{date.today()}.xlsx")

            # منطق التلوين الزمني (أحمر للمنتهي، برتقالي لـ 3 أيام)
            def highlight_by_date(row):
                target_date = pd.to_datetime(row['تاريخ الانتهاء']).date()
                days_left = (target_date - date.today()).days
                color = ''
                if days_left <= 0: color = 'background-color: #ff4b4b; color: white'
                elif 0 < days_left <= 3: color = 'background-color: #ffa500; color: black'
                return [color] * len(row)

            st.subheader("📊 عرض سجل المتاجر (بيانات معربة)")
            st.dataframe(df.style.apply(highlight_by_date, axis=1), width='stretch', height=600)
        
    except Exception as e:
        st.error(f"خطأ في عرض الجدول: {e}")


# ══════════════════════════════════════════════════════════════════════
# 📦 أرشيف المنتهية — المتاجر اللي last_time < CURRENT_DATE
#    الموقع والبوت يخفونها تلقائياً (فلتر last_time >= CURRENT_DATE)،
#    وهنا نقدر نراجعها، نمدّد تاريخها، أو نحذفها نهائياً.
# ══════════════════════════════════════════════════════════════════════
if page == "📦 أرشيف المنتهية":
    st.header("📦 أرشيف الأكواد المنتهية")
    st.caption(
        "هذه المتاجر **مخفية تلقائياً** من الموقع والبوت لأن تاريخ انتهائها مرّ. "
        "تقدر تمدّد التاريخ لإعادة تفعيلها، أو تحذفها نهائياً."
    )

    try:
        conn = get_conn()
        conn.rollback()  # تنظيف أي transaction سابقة معلّقة

        archive_q = """
            SELECT id, store_id, name_en, last_time, store_tags,
                   public_coupon, discount_value, affiliate_link,
                   total_coupon_copies, total_link_clicks,
                   (CURRENT_DATE - last_time) AS days_expired
            FROM master
            WHERE last_time IS NOT NULL AND last_time < CURRENT_DATE
            ORDER BY last_time DESC, id DESC
        """
        df_arch = pd.read_sql(archive_q, conn)
        conn.close()

        if df_arch.empty:
            kc1, _kc2, _kc3 = st.columns(3)
            with kc1:
                kpi_card("📦", "إجمالي المتاجر المنتهية", 0, "emerald")
            st.success("✅ لا توجد متاجر منتهية حالياً — كل شي شغّال.")
        else:
            # كروت الإحصائيات
            recent_expired = int((df_arch['days_expired'] <= 7).sum())
            old_expired    = int((df_arch['days_expired'] >  30).sum())

            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                kpi_card("📦", "إجمالي المتاجر المنتهية", len(df_arch), "danger")
            with kc2:
                kpi_card("🆕", "انتهت مؤخراً (٧ أيام)", recent_expired, "warning")
            with kc3:
                kpi_card("🪦", "منتهية من زمان (+٣٠ يوم)", old_expired, "neutral")

            st.divider()

            # تصدير
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_arch.to_excel(writer, index=False)
            st.download_button(
                "📥 تصدير الأرشيف (Excel)",
                buf.getvalue(),
                f"Archive_{date.today()}.xlsx",
            )

            # عرض الجدول — مقسّم على tabs حسب الكروت
            display_df = df_arch.copy()
            display_df.columns = [
                'ID', 'اسم المتجر', 'Store Name (EN)', 'تاريخ الانتهاء', 'التاقات',
                'الكوبون', 'الخصم', 'الرابط',
                'مرات النسخ', 'مرات النقر',
                'منذ كم يوم',
            ]
            _mask_recent = (df_arch['days_expired'] <= 7).values
            _mask_old    = (df_arch['days_expired'] >  30).values

            tab_all_arc, tab_recent_arc, tab_old_arc = st.tabs([
                f"📦 الكل ({len(df_arch)})",
                f"🆕 انتهت مؤخراً ({recent_expired})",
                f"🪦 من زمان (+٣٠ يوم) ({old_expired})",
            ])
            with tab_all_arc:
                st.dataframe(display_df, width='stretch', height=420)
            with tab_recent_arc:
                if recent_expired == 0:
                    st.info("ما فيه متاجر انتهت خلال آخر 7 أيام.")
                else:
                    st.dataframe(display_df.loc[_mask_recent], width='stretch', height=420)
            with tab_old_arc:
                if old_expired == 0:
                    st.success("👌 ما فيه متاجر منتهية من أكثر من 30 يوم.")
                else:
                    st.dataframe(display_df.loc[_mask_old], width='stretch', height=420)

            # ─────────────── 📊 تحليل المتاجر المنتهية (تحليلها الخاص) ───────────────
            st.divider()
            st.subheader("📊 تحليل المنتهية")
            st.caption("أداء المتاجر المنتهية طوال فترة نشاطها — راجعه قبل التمديد أو الحذف.")
            an_rank, an_drill = st.tabs(["🏆 ترتيب المنتهية", "👤 مين تفاعل مع متجر"])

            with an_rank:
                rank = df_arch[["store_id", "total_coupon_copies",
                                "total_link_clicks", "days_expired"]].copy()
                rank = rank.rename(columns={"store_id": "المتجر",
                                            "total_coupon_copies": "نسخ",
                                            "total_link_clicks": "نقرات",
                                            "days_expired": "منذ كم يوم"})
                rank["نسخ"] = rank["نسخ"].fillna(0).astype(int)
                rank["نقرات"] = rank["نقرات"].fillna(0).astype(int)
                rank = rank.sort_values("نسخ", ascending=False)
                top_r = rank[rank["نسخ"] > 0].head(20)
                if top_r.empty:
                    st.info("لا توجد نسخ مسجّلة لأي متجر منتهٍ.")
                else:
                    fig_r = px.bar(top_r, x="نسخ", y="المتجر", orientation="h",
                                   color="نسخ", color_continuous_scale="Reds")
                    fig_r.update_layout(yaxis=dict(autorange="reversed"),
                                        xaxis_title="عدد النسخ", yaxis_title="")
                    st.plotly_chart(apply_brand_theme(fig_r), width='stretch')
                st.dataframe(rank, hide_index=True, width='stretch')

            with an_drill:
                _opts = df_arch.sort_values("total_coupon_copies",
                                            ascending=False)["store_id"].tolist()
                _sel = st.selectbox("اختر متجراً منتهياً:", _opts, key="arch_drill_store")
                who = pd.DataFrame()
                try:
                    _c = get_conn(); _c.rollback()
                    who = pd.read_sql("""
                        SELECT
                            CASE WHEN a.source IN ('web','telegram_miniapp','miniapp')
                                 THEN COALESCE(NULLIF(wu.display_name,''), NULLIF(wu.email,''),
                                              NULLIF(wu.phone_number,''), 'زائر ويب')
                                 ELSE COALESCE('@'||NULLIF(bu.username,''),
                                              'تيليجرام '||a.user_id::text, 'مجهول')
                            END AS identity,
                            COALESCE(a.source,'bot') AS src,
                            COALESCE(NULLIF(a.city,''),'غير معروف') AS city,
                            COUNT(*) FILTER (WHERE a.action_type='copy_coupon') AS copies,
                            COUNT(*) FILTER (WHERE a.action_type='click_link')  AS clicks,
                            TO_CHAR(MIN(a.action_time),'YYYY-MM-DD') AS first_seen,
                            TO_CHAR(MAX(a.action_time),'YYYY-MM-DD') AS last_seen
                        FROM action_logs a
                        LEFT JOIN bot_users bu ON bu.telegram_id = a.user_id
                        LEFT JOIN web_users wu ON wu.id = a.user_id AND a.source = 'web'
                        WHERE a.store_id = %s
                          AND a.action_type IN ('copy_coupon','click_link')
                        GROUP BY 1,2,3
                        ORDER BY copies DESC, clicks DESC
                    """, _c, params=(_sel,))
                    _c.close()
                except Exception as e:
                    st.error(f"تعذّر جلب التحليل: {e}")
                if who.empty:
                    st.info("لا يوجد تفاعل مسجّل لهذا المتجر.")
                else:
                    _smap = {"bot": "📱 بوت", "web": "🌐 ويب",
                             "telegram_miniapp": "🔹 بوت - ميني", "miniapp": "🔹 بوت - ميني"}
                    who["src"] = who["src"].map(_smap).fillna(who["src"])
                    ac1, ac2, ac3 = st.columns(3)
                    with ac1: kpi_card("🎟️", "إجمالي النسخ", int(who["copies"].sum()), "danger")
                    with ac2: kpi_card("🖱️", "إجمالي النقرات", int(who["clicks"].sum()), "warning")
                    with ac3: kpi_card("👤", "متفاعلون مختلفون", int(who["identity"].nunique()), "info")
                    who = who.rename(columns={"identity": "المستخدم", "src": "المصدر",
                                              "city": "المدينة", "copies": "نسخ", "clicks": "نقرات",
                                              "first_seen": "أول تفاعل", "last_seen": "آخر تفاعل"})
                    st.dataframe(who[["المستخدم", "المصدر", "نسخ", "نقرات", "المدينة",
                                      "أول تفاعل", "آخر تفاعل"]],
                                 hide_index=True, width='stretch')

            st.divider()
            st.subheader("⚙️ إجراءات على متجر")

            # اختيار متجر للإجراء
            options = [
                f"#{row['id']} — {row['store_id']} (انتهى منذ {int(row['days_expired'])} يوم)"
                for _, row in df_arch.iterrows()
            ]
            selected = st.selectbox("اختر متجراً:", options, key="archive_pick")
            target_id = int(selected.split("—")[0].replace("#", "").strip())

            act_col1, act_col2, act_col3 = st.columns(3)

            with act_col1:
                ext_days = st.number_input(
                    "♻️ تمديد لكم يوم؟",
                    min_value=1, max_value=365, value=30, step=1,
                    key="archive_extend_days",
                )
                if st.button("♻️ إعادة تفعيل (تمديد التاريخ)", key="archive_extend_btn"):
                    try:
                        c2 = get_conn()
                        cur2 = c2.cursor()
                        cur2.execute(
                            "UPDATE master SET last_time = CURRENT_DATE + %s WHERE id = %s",
                            (int(ext_days), target_id),
                        )
                        c2.commit()
                        c2.close()
                        st.success(f"✅ تم تمديد المتجر #{target_id} لـ {ext_days} يوم.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ فشل التمديد: {e}")

            with act_col2:
                if st.button("👁️ فتح في التعديل", key="archive_open_edit"):
                    st.info(
                        f"اذهب لصفحة **«الاستعلام والتعديل»** وأدخل الـ ID: **{target_id}**"
                    )

            with act_col3:
                confirm_del = st.checkbox(
                    "تأكيد الحذف النهائي",
                    key=f"archive_confirm_del_{target_id}",
                )
                if st.button("🗑️ حذف نهائي", key="archive_delete_btn", type="primary"):
                    if not confirm_del:
                        st.warning("⚠️ فعّل خانة التأكيد أولاً.")
                    else:
                        try:
                            c3 = get_conn()
                            cur3 = c3.cursor()
                            cur3.execute("DELETE FROM master WHERE id = %s", (target_id,))
                            c3.commit()
                            c3.close()
                            st.success(f"🗑️ تم حذف المتجر #{target_id} نهائياً.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ فشل الحذف: {e}")

    except Exception as e:
        st.error(f"خطأ في الأرشيف: {e}")


    # --- الصفحة الثالثة: جدول الكوبونات (واجهة العميل مع الترند من القاعدة) ---
if page == "جدول الكوبونات":
    st.header("🎟️ عرض الكوبونات المباشر (واجهة البوت)")
    st.info("المتاجر المحددة كـ 'ترند' في قاعدة البيانات ستظهر بعلامة 🔥 وتتصدر القائمة. "
            "الكوبونات المنتهية مخفية هنا تلقائياً ومكانها صفحة «📦 أرشيف المنتهية».")

    if st.button("🔄 تحديث", key="ct_refresh", help="إعادة تحميل البيانات"):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

    try:
        conn = get_conn()
        query = """
            SELECT
                is_trending,
                store_id,
                COALESCE(name_en, '')        AS name_en,
                affiliate_link,
                store_bio,
                COALESCE(store_bio_en, '')   AS store_bio_en,
                public_coupon,
                discount_value,
                extra_offer,
                COALESCE(extra_offer_en, '') AS extra_offer_en,
                last_time,
                COALESCE(source_platform, '—') AS source_platform,
                total_coupon_copies,
                total_link_clicks
            FROM master
            WHERE last_time IS NULL OR last_time >= CURRENT_DATE
            ORDER BY
                CASE WHEN is_trending = 'ترند 🔥' THEN 1 ELSE 2 END,
                priority_score DESC
        """
        df_client = pd.read_sql(query, conn)
        conn.close()

        if df_client.empty:
            st.warning("⚠️ لا توجد كوبونات متاحة.")
        else:
            # حساب الإحصائيات: إجمالي / فعّال / قربت تنتهي (خلال 7 أيام)
            today = pd.Timestamp.today().normalize()
            df_client['last_time'] = pd.to_datetime(df_client['last_time'], errors='coerce')
            active_mask = df_client['last_time'].notna() & (df_client['last_time'] >= today)
            near_expiry_mask = active_mask & (df_client['last_time'] <= today + pd.Timedelta(days=7))

            total_count = len(df_client)
            active_count = int(active_mask.sum())
            near_count = int(near_expiry_mask.sum())

            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                kpi_card("🏪", "إجمالي المتاجر", total_count, "info")
            with kc2:
                kpi_card("✅", "المتاجر الفعّالة", active_count, "emerald")
            with kc3:
                kpi_card("⏳", "قربت تنتهي (٧ أيام)", near_count, "warning")

            st.divider()

            df_client['اسم المتجر'] = df_client.apply(
                lambda r: f"🔥 {r['store_id']}" if r['is_trending'] == 'ترند 🔥' else r['store_id'],
                axis=1,
            )

            display_cols = {
                'اسم المتجر':       'اسم المتجر',
                'name_en':          'Store Name (EN)',
                'affiliate_link':   'الرابط',
                'store_bio':        'نبذه عن المتجر',
                'store_bio_en':     'Description (EN)',
                'public_coupon':    'كود الخصم',
                'discount_value':   'قيمة كود الخصم',
                'extra_offer':      'خصم إضافي',
                'extra_offer_en':   'Extra Offer (EN)',
                'last_time':        'تاريخ الانتهاء',
                'source_platform':  'من أين 🛰️',
            }
            df_display = df_client[list(display_cols.keys())].rename(columns=display_cols)

            tab_all, tab_active, tab_near = st.tabs([
                f"🏪 الكل ({total_count})",
                f"✅ الفعّالة ({active_count})",
                f"⏳ قربت تنتهي ({near_count})",
            ])

            with tab_all:
                st.dataframe(df_display, width='stretch', height=520, hide_index=True)

            with tab_active:
                if active_count == 0:
                    st.info("ما فيه متاجر فعّالة حالياً.")
                else:
                    st.dataframe(
                        df_display.loc[active_mask.values],
                        width='stretch', height=520, hide_index=True,
                    )

            with tab_near:
                if near_count == 0:
                    st.success("👌 ما فيه متاجر قربت تنتهي خلال 7 أيام.")
                else:
                    df_near = (
                        df_client[near_expiry_mask][[
                            'store_id', 'name_en', 'public_coupon',
                            'discount_value', 'source_platform', 'last_time',
                        ]].copy()
                    )
                    df_near['أيام متبقية'] = (df_near['last_time'] - today).dt.days
                    df_near['last_time'] = df_near['last_time'].dt.strftime('%Y-%m-%d')
                    df_near = df_near.rename(columns={
                        'store_id':        'اسم المتجر',
                        'name_en':         'Store Name (EN)',
                        'public_coupon':   'الكوبون',
                        'discount_value':  'الخصم',
                        'source_platform': 'من أين 🛰️',
                        'last_time':       'تاريخ الانتهاء',
                    })
                    df_near = df_near.sort_values('أيام متبقية')
                    st.dataframe(df_near, width='stretch', hide_index=True)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_display.to_excel(writer, index=False, sheet_name='Trending_View')
            st.download_button(
                label="📥 تحميل قائمة العملاء (Excel)",
                data=output.getvalue(),
                file_name="Tawfeer_Coupons.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    except Exception as e:
        st.error(f"❌ خطأ: {e}")



# ════════════════════════════════════════════════════════════════════════════
#  صفحة «تحليل الأقسام» — نسخة معمارية موازية لـ «تحليل المتاجر»
#  مصدر البيانات: نفس caches الـ _sa_*  (إعادة استخدام لا نسخ مكرّر).
#  تبويبات: الأداء العام · الفحص الفردي · الجغرافيا · ❤️ الأكثر تفضيلاً · الزمني · 🏅 الأولويات
# ════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def _ca_store_tags() -> pd.DataFrame:
    """خريطة store_id → list[tag] (موسّعة). مخزّنة 5 دقائق.
    نعتمد store_tags (العربية) لأنها المعتمدة في كل التحليلات."""
    conn = get_conn()
    try:
        conn.rollback()
        df = pd.read_sql(
            "SELECT store_id, COALESCE(store_tags, '') AS store_tags FROM master "
            "WHERE store_id IS NOT NULL AND store_id <> ''",
            conn,
        )
    finally:
        conn.close()
    if df.empty:
        return pd.DataFrame(columns=["store_id", "tag"])
    df["tags"] = df["store_tags"].apply(parse_tags)
    expanded = df.explode("tags").rename(columns={"tags": "tag"}).dropna(subset=["tag"])
    expanded["tag"] = expanded["tag"].astype(str).str.strip()
    expanded = expanded[expanded["tag"] != ""]
    return expanded[["store_id", "tag"]].reset_index(drop=True)


@st.cache_data(ttl=180, show_spinner=False)
def _ca_tag_views() -> pd.DataFrame:
    """أحداث الاهتمام الصريح بقسم (view_tag) عبر كل المنصات (بوت/ويب/ميني).
    details بصيغة 'tag:<اسم>' (و'user:..;tag:..' أحياناً) · لا store_id (حدث قسم).
    هذا مصدر «نقاط القسم» الحقيقي: نية صريحة بدل وراثة تفاعل المتاجر. مخزّن 3 دقائق."""
    conn = get_conn()
    try:
        conn.rollback()
        return pd.read_sql(
            """
            SELECT a.action_time, a.details, a.user_id,
                   COALESCE(a.source, 'bot')      AS source,
                   a.city          AS geo_city,
                   encode(a.ip_hash, 'hex') AS ip_hex,
                   bu.username     AS bu_username, bu.city AS bu_city,
                   wu.display_name AS web_name,  wu.email AS web_email,
                   wu.phone_number AS web_phone, wu.city  AS web_city,
                   wu.telegram_username AS web_tg
            FROM   action_logs a
            LEFT JOIN bot_users bu ON bu.telegram_id = a.user_id
            LEFT JOIN web_users wu ON wu.id = a.user_id AND a.source = 'web'
            WHERE  a.action_type = 'view_tag'
            """,
            conn,
        )
    finally:
        conn.close()


def _parse_view_tag(d):
    """يستخرج اسم القسم من details: 'tag:أزياء' أو 'user:123;tag:أزياء' → 'أزياء'."""
    if not d:
        return None
    s = str(d)
    i = s.find("tag:")
    if i < 0:
        return None
    return (s[i + 4:].split(";")[0].strip()) or None


if page == "تحليل الأقسام":
    page_title("📂", "تحليل الأقسام",
               "لوحة قرار بالنية الصريحة: نقطة القسم = اختياره (تايل/فلتر/تاق) + بحث باسمه + تفضيله — لا وراثة تفاعل متجر")

    CHAN_MAP = {"bot": "📱 بوت", "web": "🌐 ويب",
                "telegram_miniapp": "🔹 بوت - ميني", "miniapp": "🔹 بوت - ميني"}
    SRC_FILTER = {"📱 بوت": ["bot"], "🌐 ويب": ["web"],
                  "🔹 بوت - ميني": ["telegram_miniapp", "miniapp"]}

    # ── شريط التحكم ──────────────────────────────────────────────────────────
    c_ref, c_src, c_hint = st.columns([1, 2.4, 2.6])
    with c_ref:
        if st.button("🔄 تحديث", width='stretch', key="ca_refresh"):
            _sa_load_actions.clear(); _sa_load_master.clear()
            _sa_load_searches.clear(); _sa_load_favorites.clear()
            _ca_store_tags.clear()
            st.rerun()
    with c_src:
        src_choice = st.radio("المصدر:", ["الكل", "📱 بوت", "🌐 ويب", "🔹 بوت - ميني"],
                              horizontal=True, key="ca_src")
    with c_hint:
        st.caption("أرقام فعلية من action_logs + direct_search + user_favorites · مخزّنة 3 دقائق.")

    try:
        df_views  = _ca_tag_views()
        df_master = _sa_load_master()
        df_search = _sa_load_searches()
        df_favs   = _sa_load_favorites()
        df_tags   = _ca_store_tags()
    except Exception as e:
        st.error(f"⚠️ تعذّر تحميل البيانات: {e}")
        st.stop()

    if df_tags.empty:
        st.info("📭 لا توجد أقسام محدّدة في master.store_tags بعد.")
        st.stop()

    # ── استبعاد المتاجر منتهية الكوبون (لعدّ المتاجر تحت القسم — معلومة بنيوية) ─
    _today_d = pd.Timestamp.today().date()
    if "last_time" in df_master.columns:
        _lt = pd.to_datetime(df_master["last_time"], errors="coerce").dt.date
        df_master = df_master[_lt.isna() | (_lt >= _today_d)].copy()
    active_ids = set(df_master["store_id"])
    df_tags = df_tags[df_tags["store_id"].isin(active_ids)].copy()
    _valid_tags = set(df_tags["tag"].unique())

    # ── أحداث الاهتمام بالقسم (view_tag) — نية صريحة، لا وراثة تفاعل متجر ──────
    if not df_views.empty:
        df_views = df_views.copy()
        df_views["tag"] = df_views["details"].apply(_parse_view_tag)
        df_views = df_views.dropna(subset=["tag"])
        df_views["tag"] = df_views["tag"].astype(str).str.strip()
        df_views = df_views[df_views["tag"].isin(_valid_tags)].copy()
    if not df_views.empty:
        df_views["action_time"] = (pd.to_datetime(df_views["action_time"], utc=True).dt.tz_localize(None)
                                   + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        df_views["adate"]  = df_views["action_time"].dt.date
        df_views["hour"]   = df_views["action_time"].dt.hour
        df_views["source"] = df_views["source"].fillna("bot")
        df_views["city_c"] = (df_views["geo_city"].fillna("").astype(str)
                              .str.strip().replace("", "غير معروف"))
        df_views["src_ar"] = df_views["source"].map(CHAN_MAP).fillna("🌐 ويب")
        df_views["action_type"] = "view_tag"

        def _clean(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        def _identity(r):
            src = r["source"]
            if src in ("telegram_miniapp", "miniapp"):
                u = _clean(r.get("bu_username"))
                if u:
                    return "@" + u.lstrip("@")
                uid = r.get("user_id")
                if pd.notna(uid):
                    return f"🔹 بوت - ميني {int(uid)}"
                h = _clean(r.get("ip_hex"))
                return f"🔹 بوت - ميني #{h[:6]}" if h else "🔹 بوت - ميني (غير مسجّل)"
            if src == "web":
                for k in ("web_name", "web_email", "web_phone"):
                    v = _clean(r.get(k))
                    if v:
                        return v
                h = _clean(r.get("ip_hex"))
                return f"🌐 زائر ويب #{h[:6]}" if h else "🌐 زائر ويب (غير مسجّل)"
            u = _clean(r.get("bu_username"))
            if u:
                return "@" + u.lstrip("@")
            uid = r.get("user_id")
            return f"تيليجرام {int(uid)}" if pd.notna(uid) else "مجهول"
        df_views["identity"] = df_views.apply(_identity, axis=1)
    else:
        for _c in ["tag", "adate", "hour", "source", "city_c", "src_ar",
                   "action_type", "identity", "action_time", "user_id"]:
            if _c not in df_views.columns:
                df_views[_c] = pd.Series(dtype="object")

    # ── بحث باسم القسم (إشارة 1): كلمة البحث تطابق اسم قسم صراحةً ──────────────
    def _norm(s):
        return str(s).strip().lower()
    _tag_norm = {_norm(t): t for t in _valid_tags}
    if not df_search.empty:
        df_search = df_search.copy()
        df_search["search_date"] = (pd.to_datetime(df_search["search_date"], utc=True).dt.tz_localize(None)
                                    + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        df_search["adate"] = df_search["search_date"].dt.date
        df_search["cat_match"] = df_search["search_keyword"].apply(lambda k: _tag_norm.get(_norm(k)))
        search_cat = df_search.dropna(subset=["cat_match"]).copy()
    else:
        search_cat = pd.DataFrame(columns=["cat_match", "adate", "platform"])

    # ── فلتر الفترة ──────────────────────────────────────────────────────────
    if not df_views.empty:
        _min_d, _max_d = df_views["adate"].min(), df_views["adate"].max()
    elif not search_cat.empty:
        _min_d, _max_d = search_cat["adate"].min(), search_cat["adate"].max()
    else:
        import datetime as _dt
        _min_d = _max_d = _dt.date.today()

    dcol1, dcol2 = st.columns([2, 3])
    with dcol1:
        _dr = st.date_input("📅 الفترة (من → إلى):", value=(_min_d, _max_d),
                            min_value=_min_d, max_value=_max_d, key="ca_dates")
    d_start, d_end = (_dr if isinstance(_dr, (list, tuple)) and len(_dr) == 2 else (_min_d, _max_d))
    if not df_views.empty:
        df_views = df_views[(df_views["adate"] >= d_start) & (df_views["adate"] <= d_end)]
    if not search_cat.empty:
        search_cat = search_cat[(search_cat["adate"] >= d_start) & (search_cat["adate"] <= d_end)]

    # ── نطاق المصدر ──────────────────────────────────────────────────────────
    # scoped_with_tag = أحداث الاهتمام (view_tag) ضمن النطاق — قاعدة كل التبويبات.
    if src_choice in SRC_FILTER and not df_views.empty:
        scoped_with_tag = df_views[df_views["source"].isin(SRC_FILTER[src_choice])].copy()
    else:
        scoped_with_tag = df_views.copy() if not df_views.empty else df_views

    def _search_scope_ca(ds):
        if ds is None or ds.empty:
            return ds
        p = ds["platform"].astype(str).str.lower()
        is_mini = p.str.contains("mini")
        if src_choice == "📱 بوت":
            # البوت فقط — نستبعد الميني صراحةً (تحصين مطابق لصفحة تحليل المتاجر)
            return ds[(p.str.contains("telegram") | p.str.contains("bot")) & ~is_mini]
        if src_choice == "🌐 ويب":
            return ds[p.str.contains("web")]
        if src_choice == "🔹 بوت - ميني":
            return ds[is_mini]
        return ds
    search_cat_scope = _search_scope_ca(search_cat)

    with dcol2:
        st.caption(f"📅 {d_start} ← {d_end} · المصدر: {src_choice} · "
                   f"اختيارات قسم: **{len(scoped_with_tag):,}** · أقسام: **{len(_valid_tags)}** · "
                   "النقطة = نية صريحة (اختيار/بحث/تفضيل) — بلا تكرار عبر الأقسام.")

    # ─────────────────────────────────────────────────────────────────────────
    # تجميع كل قسم من النية الصريحة: اختيارات (view_tag) + بحث باسمه + مفضّلون.
    # كل حدث يخصّ قسماً واحداً → النقاط قابلة للجمع بلا تضخّم (عكس وراثة المتاجر).
    # ─────────────────────────────────────────────────────────────────────────
    def _cat_agg() -> pd.DataFrame:
        out = pd.DataFrame({"tag": sorted(_valid_tags)})
        if not scoped_with_tag.empty:
            v = scoped_with_tag.groupby("tag").size().rename("اختيارات")
            out = out.merge(v, on="tag", how="left")
        else:
            out["اختيارات"] = 0
        if search_cat_scope is not None and not search_cat_scope.empty:
            s = (search_cat_scope.groupby("cat_match").size().rename("بحث")
                 .reset_index().rename(columns={"cat_match": "tag"}))
            out = out.merge(s, on="tag", how="left")
        else:
            out["بحث"] = 0
        out[["اختيارات", "بحث"]] = out[["اختيارات", "بحث"]].fillna(0).astype(int)
        if not scoped_with_tag.empty:
            uq = scoped_with_tag.groupby("tag")["identity"].nunique().rename("مستخدمون فريدون")
            out = out.merge(uq, on="tag", how="left")
        else:
            out["مستخدمون فريدون"] = 0
        out["مستخدمون فريدون"] = out["مستخدمون فريدون"].fillna(0).astype(int)
        stores_per_tag = df_tags.groupby("tag")["store_id"].nunique().rename("متاجر")
        out = out.merge(stores_per_tag, on="tag", how="left")
        out["متاجر"] = out["متاجر"].fillna(0).astype(int)
        return out

    df_cat_agg = _cat_agg()

    # ── مفضّلون لكل قسم (kind='category' فقط) ────────────────────────────────
    if not df_favs.empty and "kind" in df_favs.columns:
        fav_cats_only = df_favs[df_favs["kind"] == "category"].copy()
    elif not df_favs.empty:
        fav_cats_only = df_favs.iloc[0:0].copy()
        fav_cats_only["category_name"] = pd.Series(dtype="object")
    else:
        fav_cats_only = pd.DataFrame(columns=["category_name", "platform",
                                              "web_user_id", "telegram_id"])

    if not fav_cats_only.empty:
        fav_per_cat = (fav_cats_only.groupby("category_name").size()
                       .rename("مفضّلون").reset_index()
                       .rename(columns={"category_name": "tag"}))
        df_cat_agg = df_cat_agg.merge(fav_per_cat, on="tag", how="left")
    else:
        df_cat_agg["مفضّلون"] = 0
    df_cat_agg["مفضّلون"] = df_cat_agg["مفضّلون"].fillna(0).astype(int)
    # النقاط = اختيارات + بحث + مفضّلون (نية صريحة، قابلة للجمع بلا تكرار)
    df_cat_agg["نقاط"] = df_cat_agg["اختيارات"] + df_cat_agg["بحث"] + df_cat_agg["مفضّلون"]
    df_cat_agg = df_cat_agg.sort_values(["نقاط", "اختيارات"], ascending=False).reset_index(drop=True)

    # ── محرّك التوصية لكل قسم + بطاقات الأعلى/الأقل (على النية الصريحة) ───────
    #   النقاط = اختيارات (view_tag) + بحث باسمه + مفضّلون · قابلة للجمع بلا تضخّم
    #   (كل حدث يخصّ قسماً واحداً). «اختيارات» = اختيار صريح للقسم (تايل/فلتر/تاق).
    agg = df_cat_agg.copy()
    _ncat = len(agg)
    q_hi = agg["اختيارات"].quantile(0.75) if _ncat >= 4 else agg["اختيارات"].max()
    q_lo = agg["اختيارات"].quantile(0.25) if _ncat >= 4 else 0
    s_hi = agg["بحث"].quantile(0.75) if _ncat >= 4 else agg["بحث"].max()

    def _reco_cat(r):
        if r["متاجر"] == 0:
            return "🚫 بلا متاجر — احذف الوسم"
        if r["نقاط"] == 0:
            return "💤 خامل — لا اهتمام صريح"
        # أثمن إشارة: يُبحث عنه باسمه لكن لا يُتصفّح = فجوة اكتشاف/عرض
        if r["بحث"] >= s_hi and r["بحث"] > 0 and r["اختيارات"] <= q_lo:
            return "⚠️ يُبحث ولا يُتصفّح — حسّن الظهور"
        if r["اختيارات"] >= q_hi and r["اختيارات"] > 0:
            return "🔥 قسم مطلوب — وسّع المخزون"
        if r["اختيارات"] <= q_lo:
            return "🪫 ضعيف — قلّل التركيز"
        return "✅ مستقر"
    agg["التوصية"] = agg.apply(_reco_cat, axis=1)
    agg = agg.sort_values(["نقاط", "اختيارات"], ascending=False).reset_index(drop=True)
    agg.insert(0, "#", range(1, len(agg) + 1))

    def _hi(col): return agg.sort_values([col, "نقاط"], ascending=False).iloc[0]
    def _lo(col): return agg.sort_values([col, "نقاط"], ascending=True).iloc[0]
    _hn, _ln = _hi("اختيارات"), _lo("اختيارات")
    _hs, _ls = _hi("بحث"), _lo("بحث")
    _hf, _lf = _hi("مفضّلون"), _lo("مفضّلون")
    r1a, r1b, r1c = st.columns(3)
    with r1a: kpi_card("🖱️", "الأعلى اختياراً (مطلوب)", f"{_hn['tag']}", "emerald", note=f"{int(_hn['اختيارات'])} اختيار")
    with r1b: kpi_card("🔍", "الأعلى بحثاً (طلب)", f"{_hs['tag']}", "info", note=f"{int(_hs['بحث'])} بحث")
    with r1c: kpi_card("❤️", "الأعلى تفضيلاً", f"{_hf['tag']}", "warning", note=f"{int(_hf['مفضّلون'])} مفضّل")
    r2a, r2b, r2c = st.columns(3)
    with r2a: kpi_card("🗑️", "الأقل اختياراً (راجع)", f"{_ln['tag']}", "danger", note=f"{int(_ln['اختيارات'])} اختيار")
    with r2b: kpi_card("📉", "الأقل بحثاً", f"{_ls['tag']}", "neutral", note=f"{int(_ls['بحث'])} بحث")
    with r2c: kpi_card("🔻", "الأقل تفضيلاً", f"{_lf['tag']}", "neutral", note=f"{int(_lf['مفضّلون'])} مفضّل")

    # ── التبويبات (موازية لصفحة «تحليل المتاجر») ────────────────────────────
    _CA_TABS = [
        "🏆 لوحة القرار (كل الأقسام)",
        "👤 مين تفاعل مع قسم",
        "📈 الرسوم والمعدلات",
        "❤️ المفضلة",
        "🏅 الأولويات",
    ]
    # radio محفوظ بدل st.tabs — يثبّت التبويب عبر إعادة التشغيل (تغيير الفلتر).
    _ca_tab = st.radio("العرض:", _CA_TABS, horizontal=True,
                       key="ca_active_tab", label_visibility="collapsed")

    # ── 1) لوحة القرار (كل الأقسام) ─────────────────────────────────────────
    if _ca_tab == _CA_TABS[0]:
        st.caption("كل الأقسام تظهر (حتى الخاملة بصفر) · مرتّبة بالنقاط · «التوصية» قاعدة آلية. "
                   "النقاط = اختيارات + بحث باسمه + مفضّلون (نية صريحة) — لا وراثة تفاعل متجر.")
        q = st.text_input("🔎 ابحث عن قسم:", key="ca_board_q")
        board = agg.copy()
        if q:
            board = board[board["tag"].str.contains(q, case=False, na=False)]
        view = pd.DataFrame({
            "#": board["#"].values,
            "القسم": board["tag"].values,
            "🖱️ اختيارات": board["اختيارات"].values,
            "🔍 بحث": board["بحث"].values,
            "❤️ مفضّلون": board["مفضّلون"].values,
            "🏪 متاجر": board["متاجر"].values,
            "👥 مستخدمون": board["مستخدمون فريدون"].values,
            "النقاط": board["نقاط"].values,
            "التوصية": board["التوصية"].values,
        })
        _maxtot = int(max(1, agg["نقاط"].max()))
        st.dataframe(
            view, hide_index=True, width='stretch',
            column_config={
                "🖱️ اختيارات": st.column_config.NumberColumn(
                    "🖱️ اختيارات", help="مرات اختيار القسم صراحةً (تايل/فلتر/تاق) — view_tag"),
                "النقاط": st.column_config.ProgressColumn(
                    "النقاط", format="%d", min_value=0, max_value=_maxtot),
            },
        )
        st.download_button("📥 تحميل CSV", view.to_csv(index=False).encode("utf-8-sig"),
                           f"categories_decision_{d_start}_{d_end}.csv", "text/csv", key="ca_board_csv")

        # تفصيل الاختيارات لكل قسم حسب المصدر (وضع «الكل»)
        if src_choice == "الكل" and not scoped_with_tag.empty:
            with st.expander("📱🌐🔹 تفصيل اختيارات الأقسام حسب المصدر"):
                brk = (scoped_with_tag.assign(chan=lambda d: d["source"].map(CHAN_MAP).fillna("أخرى"))
                       .groupby(["tag", "chan"]).size().reset_index(name="اختيارات"))
                if brk.empty:
                    st.info("لا اختيارات ضمن الفترة.")
                else:
                    pb = brk.pivot_table(index="tag", columns="chan",
                                         values="اختيارات", fill_value=0)
                    pb = pb.reset_index().rename(columns={"tag": "القسم"})
                    st.dataframe(pb, hide_index=True, width='stretch')

        st.divider()
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**🔥 وسّعهم (مطلوب / يُبحث عنه):**")
            grow = agg[agg["التوصية"].str.contains("مطلوب|يُبحث")]
            st.write("، ".join(grow["tag"].tolist()) or "—")
        with cc2:
            st.markdown("**⬇️ راجعهم (ضعيف / خامل / بلا متاجر):**")
            weak = agg[agg["التوصية"].str.contains("ضعيف|خامل|احذف")]
            st.write("، ".join(weak["tag"].tolist()) or "—")

    # ── 2) مين تفاعل مع قسم (اختار/فضّل القسم صراحةً — بهوية كاملة) ──────────
    elif _ca_tab == _CA_TABS[1]:
        st.caption("من **اختار** القسم صراحةً (تايل/فلتر/تاق) أو **فضّله** — بهوية كاملة "
                   "(إيميل/جوال/تيليجرام/مدينة). الافتراضي: كل الأقسام؛ اختر قسماً للتركيز.")
        _ALL_CATS = "— الكل (جميع الأقسام) —"
        cat_opts = [_ALL_CATS] + agg["tag"].tolist()
        selc = st.selectbox("القسم:", cat_opts, key="ca_who_cat")
        _is_all = (selc == _ALL_CATS)

        sdf = scoped_with_tag if _is_all else (
            scoped_with_tag[scoped_with_tag["tag"] == selc]
            if not scoped_with_tag.empty else scoped_with_tag)

        n_sel   = len(sdf) if (sdf is not None and not sdf.empty) else 0
        n_users = sdf["identity"].nunique() if (sdf is not None and not sdf.empty) else 0
        m1, m2, m3 = st.columns(3)
        with m1: kpi_card("🖱️", "إجمالي الاختيارات", f"{n_sel:,}", "emerald")
        with m2: kpi_card("👤", "مختارون مختلفون", f"{n_users:,}", "info")
        if _is_all:
            n_cats = sdf["tag"].nunique() if (sdf is not None and not sdf.empty) else 0
            with m3: kpi_card("🏷️", "أقسام مختارة", f"{n_cats:,}", "warning")
        else:
            n_fav = int(agg[agg["tag"] == selc]["مفضّلون"].iloc[0]) if (agg["tag"] == selc).any() else 0
            with m3: kpi_card("❤️", "مفضّلون", f"{n_fav:,}", "warning")

        # ── المفضِّلون لهذا النطاق (kind='category') — يظهرون حتى لو لم يختاروا ──
        def _cln(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        _fwc = fav_cats_only.copy() if not fav_cats_only.empty else pd.DataFrame()
        if not _fwc.empty and not _is_all:
            _fwc = _fwc[_fwc["category_name"] == selc]

        def _fav_ident(r):
            if pd.notna(r.get("telegram_id")):
                u = _cln(r.get("bu_username"))
                if u:
                    return "@" + u.lstrip("@")
                if r.get("platform") in ("miniapp", "telegram_miniapp"):
                    return f"🔹 بوت - ميني {int(r['telegram_id'])}"
                return f"تيليجرام {int(r['telegram_id'])}"
            for k in ("web_name", "web_email"):
                v = _cln(r.get(k))
                if v:
                    return v
            return None

        _CHAN_FAV = {"bot": "📱 بوت", "web": "🌐 ويب",
                     "miniapp": "🔹 بوت - ميني", "telegram_miniapp": "🔹 بوت - ميني"}
        _fav_rows = []
        if not _fwc.empty:
            for _, _fr in _fwc.iterrows():
                _id = _fav_ident(_fr)
                if _id is None or pd.isna(_fr.get("category_name")):
                    continue
                _fav_rows.append({"identity": _id, "tag": _fr["category_name"],
                                  "fav_src": _CHAN_FAV.get(_fr.get("platform"), _fr.get("platform"))})
        _fav_df = pd.DataFrame(_fav_rows)
        _fav_set = (set(zip(_fav_df["identity"], _fav_df["tag"]))
                    if not _fav_df.empty else set())

        if (sdf is None or sdf.empty) and _fav_df.empty:
            st.info("لا توجد اختيارات ولا مفضّلات ضمن الفترة/المصدر.")
        else:
            _gk = ["identity", "tag"] if _is_all else ["identity"]
            if sdf is not None and not sdf.empty:
                counts = sdf.groupby(_gk).size().rename("اختيارات").reset_index()
                meta = (sdf.groupby(_gk).agg(
                            src=("src_ar", lambda s: "، ".join(sorted(set(s)))),
                            first=("action_time", "min"),
                            last=("action_time", "max")).reset_index())
                who = counts.merge(meta, on=_gk, how="left")
            else:
                who = pd.DataFrame(columns=_gk + ["اختيارات", "src", "first", "last"])

            # أضف المفضِّلين الذين لم يختاروا القسم (مفضّل فقط)
            if not _fav_df.empty:
                if _is_all:
                    _present = (set(zip(who["identity"], who["tag"])) if not who.empty else set())
                    _mask = [((i, t) not in _present) for i, t in zip(_fav_df["identity"], _fav_df["tag"])]
                else:
                    _present = set(who["identity"]) if not who.empty else set()
                    _mask = [(i not in _present) for i in _fav_df["identity"]]
                _miss = _fav_df[_mask]
                if not _miss.empty:
                    _add = {"identity": _miss["identity"].values, "اختيارات": 0,
                            "src": _miss["fav_src"].values, "first": pd.NaT, "last": pd.NaT}
                    if _is_all:
                        _add["tag"] = _miss["tag"].values
                    who = pd.concat([who, pd.DataFrame(_add)], ignore_index=True)

            # ── ملف تعريف الشخص: إيميل/جوال/تيليجرام/مدينة (من أحداث الاختيار + المفضلة) ──
            def _first_ne(series):
                if series is None:
                    return ""
                for v in series:
                    s = _cln(v)
                    if s:
                        return s
                return ""
            _profile = {}
            if scoped_with_tag is not None and not scoped_with_tag.empty and "identity" in scoped_with_tag.columns:
                for _ident, _grp in scoped_with_tag.groupby("identity"):
                    _tg = _first_ne(_grp.get("web_tg")) or _first_ne(_grp.get("bu_username"))
                    _profile[_ident] = {
                        "email": _first_ne(_grp.get("web_email")),
                        "phone": _first_ne(_grp.get("web_phone")),
                        "tg":    _tg,
                        "city":  _first_ne(_grp.get("web_city")) or _first_ne(_grp.get("bu_city")),
                    }
            if not _fwc.empty:
                for _, _fr in _fwc.iterrows():
                    _ident = _fav_ident(_fr)
                    if _ident is None or _ident in _profile:
                        continue
                    _tg = _cln(_fr.get("web_tg")) or _cln(_fr.get("bu_username"))
                    _profile[_ident] = {
                        "email": _cln(_fr.get("web_email")),
                        "phone": _cln(_fr.get("web_phone")),
                        "tg":    _tg,
                        "city":  _cln(_fr.get("web_city")) or _cln(_fr.get("bu_city")),
                    }

            _geo = (scoped_with_tag[scoped_with_tag["city_c"] != "غير معروف"]
                    if (scoped_with_tag is not None and not scoped_with_tag.empty) else None)
            _cmap = ({} if (_geo is None or _geo.empty) else
                     _geo.groupby("identity")["city_c"].agg(
                         lambda s: s.mode().iat[0] if not s.mode().empty else "غير معروف").to_dict())

            def _city_of(ident):
                c = _cmap.get(ident)
                if c and c != "غير معروف":
                    return c
                return _profile.get(ident, {}).get("city") or "غير معروف"
            def _tg_of(ident):
                t = _profile.get(ident, {}).get("tg")
                return ("@" + t.lstrip("@")) if t else "—"

            if not who.empty:
                who["المدينة"]  = who["identity"].map(_city_of)
                who["الإيميل"]  = who["identity"].map(lambda i: _profile.get(i, {}).get("email") or "—")
                who["الجوال"]   = who["identity"].map(lambda i: _profile.get(i, {}).get("phone") or "—")
                who["تيليجرام"] = who["identity"].map(_tg_of)
            else:
                for _c in ("المدينة", "الإيميل", "الجوال", "تيليجرام"):
                    who[_c] = pd.Series(dtype="object")

            def _who_fav(r):
                _t = r["tag"] if _is_all else selc
                return f"❤️ {_t}" if (r["identity"], _t) in _fav_set else "—"
            who["❤️ المفضلة"] = (who.apply(_who_fav, axis=1)
                                 if not who.empty else pd.Series(dtype="object"))

            who = who.rename(columns={"identity": "المستخدم", "tag": "القسم",
                                      "src": "المصدر", "first": "أول اختيار", "last": "آخر اختيار"})
            who = who.sort_values("اختيارات", ascending=False)
            who["أول اختيار"] = pd.to_datetime(who["أول اختيار"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            who["آخر اختيار"] = pd.to_datetime(who["آخر اختيار"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            who[["أول اختيار", "آخر اختيار"]] = who[["أول اختيار", "آخر اختيار"]].fillna("—")
            who["المصدر"] = who["المصدر"].fillna("—")
            _cols = (["المستخدم", "الإيميل", "الجوال", "تيليجرام", "المدينة",
                      "القسم", "المصدر", "اختيارات", "❤️ المفضلة", "أول اختيار", "آخر اختيار"]
                     if _is_all else
                     ["المستخدم", "الإيميل", "الجوال", "تيليجرام", "المدينة",
                      "المصدر", "اختيارات", "❤️ المفضلة", "أول اختيار", "آخر اختيار"])
            st.dataframe(who[_cols], hide_index=True, width='stretch')
            _fname = "all" if _is_all else selc
            st.download_button("📥 تحميل القائمة (CSV)",
                               who.to_csv(index=False).encode("utf-8-sig"),
                               f"category_intent_{_fname}_{d_start}_{d_end}.csv", "text/csv",
                               key="ca_who_csv")
            st.caption("يشمل **من اختار** و**من فضّل** القسم · «الاختيار» = view_tag (تايل/فلتر/تاق). "
                       "«المدينة» من IP وقت الاختيار (متاحة جزئياً).")

            if not _is_all:
                st.divider()
                _sit = df_tags[df_tags["tag"] == selc]["store_id"].unique().tolist()
                st.markdown(f"**🏪 المتاجر في «{selc}» ({len(_sit)}):**")
                st.code(" · ".join(_sit) if _sit else "—", language=None)

    # ── 3) الرسوم والمعدلات ─────────────────────────────────────────────────
    elif _ca_tab == _CA_TABS[2]:
        st.markdown("**🖱️ أعلى الأقسام اختياراً (أعلى 20)**")
        topn = agg[agg["اختيارات"] > 0].sort_values("اختيارات", ascending=False).head(20)
        if topn.empty:
            st.info("لا توجد اختيارات أقسام ضمن الفلتر الحالي.")
        else:
            fig1 = px.bar(topn, x="اختيارات", y="tag", orientation="h",
                          color="اختيارات", color_continuous_scale="Greens")
            fig1.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="عدد الاختيارات", yaxis_title="")
            st.plotly_chart(apply_brand_theme(fig1), width='stretch')

        st.markdown("**🔍 أعلى الأقسام بحثاً (أعلى 20)**")
        tops = agg[agg["بحث"] > 0].sort_values("بحث", ascending=False).head(20)
        if tops.empty:
            st.info("لا توجد عمليات بحث ضمن الفلتر الحالي.")
        else:
            fig_s = px.bar(tops, x="بحث", y="tag", orientation="h",
                           color="بحث", color_continuous_scale="Blues")
            fig_s.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="عدد عمليات البحث", yaxis_title="")
            st.plotly_chart(apply_brand_theme(fig_s), width='stretch')

        # ── فجوة الطلب مقابل العرض: أقسام مطلوبة لكن متاجرها قليلة ──
        st.divider()
        st.markdown("**⚖️ الطلب مقابل العرض** — أقسام عليها طلب (اختيار+بحث) لكن متاجرها قليلة")
        gap = agg.copy()
        gap["طلب"] = gap["اختيارات"] + gap["بحث"]
        gap = gap[gap["طلب"] > 0].sort_values("طلب", ascending=False).head(15)
        if gap.empty:
            st.info("لا طلب صريح على أي قسم ضمن الفلتر بعد.")
        else:
            figg2 = px.scatter(gap, x="متاجر", y="طلب", text="tag", size="طلب",
                               color="مفضّلون", color_continuous_scale="Reds")
            figg2.update_traces(textposition="top center")
            figg2.update_layout(xaxis_title="عدد المتاجر (العرض)", yaxis_title="الطلب (اختيار+بحث)")
            st.plotly_chart(apply_brand_theme(figg2), width='stretch')
            st.caption("أعلى-يسار = طلب عالٍ وعرض قليل (فجوة) → أضف متاجر/كوبونات للقسم.")

        # ── الاختيارات حسب المصدر ──
        st.divider()
        st.markdown("**📱🌐🔹 اختيارات الأقسام حسب المصدر**")
        if scoped_with_tag is not None and not scoped_with_tag.empty:
            bys = (scoped_with_tag.groupby("src_ar").size().reset_index(name="العدد"))
            if not bys.empty:
                fig2 = px.bar(bys, x="src_ar", y="العدد", color="src_ar")
                fig2.update_layout(xaxis_title="", yaxis_title="عدد الاختيارات", showlegend=False)
                st.plotly_chart(apply_brand_theme(fig2), width='stretch')
            else:
                st.info("لا اختيارات ضمن الفلتر.")
        else:
            st.info("لا توجد اختيارات ضمن الفلتر.")

        # ── التوزيع الجغرافي (مع شريط تغطية صريح — لا نخفي ضعف البيانات) ──
        st.divider()
        st.markdown("**🏙️ التوزيع الجغرافي**")
        if scoped_with_tag.empty:
            st.info("لا أحداث ضمن النطاق.")
        else:
            known = scoped_with_tag[scoped_with_tag["city_c"] != "غير معروف"]
            _cov = (len(known) / len(scoped_with_tag) * 100) if len(scoped_with_tag) else 0
            st.caption(f"المدينة متاحة لـ **{_cov:.0f}%** من الأحداث فقط (تُلتقط وقت نقر /go). "
                       "«غير معروف» مستبعَد من الرسم لتفادي التضليل.")
            if known.empty:
                st.info("لا أحداث بمدينة معروفة ضمن النطاق.")
            else:
                geo = known.groupby(["tag", "city_c"]).size().reset_index(name="الأحداث")
                top_cities = (geo.groupby("city_c")["الأحداث"].sum()
                              .sort_values(ascending=False).head(10).index.tolist())
                geo = geo[geo["city_c"].isin(top_cities)]
                figg = px.bar(geo, x="الأحداث", y="city_c", color="tag",
                              orientation="h", title="أعلى 10 مدن × أقسام")
                figg.update_layout(yaxis=dict(autorange="reversed"),
                                   yaxis_title="المدينة", xaxis_title="عدد الأحداث")
                st.plotly_chart(apply_brand_theme(figg), width='stretch')

        # ── النشاط عبر الزمن (لكل قسم أو الكل) ──
        st.divider()
        st.markdown("**📈 النشاط عبر الزمن** — على مدار اليوم (توقيت الرياض)")
        if scoped_with_tag.empty:
            st.info("لا أحداث ضمن النطاق.")
        else:
            pick_t = st.selectbox("القسم (الكل = إجمالي):",
                                  ["— الكل —"] + agg["tag"].tolist(), key="ca_time_pick")
            d_one = (scoped_with_tag if pick_t == "— الكل —"
                     else scoped_with_tag[scoped_with_tag["tag"] == pick_t])
            if d_one.empty:
                st.info("لا أحداث لهذا القسم ضمن النطاق.")
            else:
                st.plotly_chart(
                    _sa_hourly_fig(d_one, title=f"نشاط «{pick_t}» على مدار اليوم",
                                   include_search=False),
                    width='stretch',
                )

    # ── 4) ❤️ المفضلة (نقل كامل من صفحة المتاجر — kind='category') ──────────
    elif _ca_tab == _CA_TABS[3]:
        st.caption("من جدول `user_favorites` (kind='category') عبر بوت + ميني-ويب + ويب · كل شخص "
                   "يُحتسب مرة لكل قسم · أساس تنبيه «نزل كوبون في قسمك المفضّل» (last_notified_at جاهز).")
        df_fav = fav_cats_only.copy() if not fav_cats_only.empty else pd.DataFrame()
        PLAT_FILTER = {"📱 بوت": ["bot"], "🌐 ويب": ["web"],
                       "🔹 بوت - ميني": ["miniapp", "telegram_miniapp"]}
        if src_choice in PLAT_FILTER and not df_fav.empty:
            df_fav = df_fav[df_fav["platform"].isin(PLAT_FILTER[src_choice])].copy()

        if df_fav.empty:
            st.info("📭 لا توجد تفضيلات أقسام بعد. زر ❤️ على أي قسم في البوت/الميني-ويب/الموقع يظهر هنا فوراً.")
        else:
            _plat_ar = {"bot": "📱 بوت", "web": "🌐 ويب",
                        "miniapp": "🔹 بوت - ميني", "telegram_miniapp": "🔹 بوت - ميني"}

            def _person_key(r):
                if pd.notna(r.web_user_id):
                    return f"w{int(r.web_user_id)}"
                if pd.notna(r.telegram_id):
                    return f"t{int(r.telegram_id)}"
                return "?"

            total_fav   = len(df_fav)
            uniq_cats   = df_fav["category_name"].nunique()
            uniq_people = df_fav.apply(_person_key, axis=1).nunique()
            k1, k2, k3 = st.columns(3)
            k1.metric("❤️ إجمالي الإضافات", f"{total_fav:,}")
            k2.metric("🏷️ أقسام مفضّلة",    f"{uniq_cats:,}")
            k3.metric("👤 أشخاص فعّالون",    f"{uniq_people:,}")

            st.markdown("**🏆 أكثر الأقسام تفضيلاً (عدد الأشخاص)**")
            board_f = (df_fav.groupby("category_name").size()
                       .reset_index(name="عدد الأشخاص")
                       .sort_values("عدد الأشخاص", ascending=False)
                       .rename(columns={"category_name": "القسم"}))
            _maxp = int(max(1, board_f["عدد الأشخاص"].max()))
            st.dataframe(
                board_f, hide_index=True, width='stretch',
                column_config={
                    "عدد الأشخاص": st.column_config.ProgressColumn(
                        "عدد الأشخاص", format="%d", min_value=0, max_value=_maxp),
                },
            )
            st.download_button("📥 تحميل CSV", board_f.to_csv(index=False).encode("utf-8-sig"),
                               "category_favorites_leaderboard.csv", "text/csv", key="ca_fav_csv")

            if src_choice == "الكل":
                st.markdown("**📊 التوزيع حسب المنصة**")
                dist_f = (df_fav.assign(منصة=lambda d: d["platform"].map(_plat_ar).fillna(d["platform"]))
                          .groupby("منصة").size().reset_index(name="العدد"))
                fig_fp = px.pie(dist_f, names="منصة", values="العدد", hole=0.45)
                st.plotly_chart(apply_brand_theme(fig_fp), width='stretch')

            st.divider()
            st.markdown("**🔍 مين فضّل قسماً معيّناً؟** (جمهور التنبيه)")
            cat_sel = st.selectbox("اختر قسماً:", board_f["القسم"].tolist(), key="ca_fav_cat_sel")
            sub_f = df_fav[df_fav["category_name"] == cat_sel].copy()

            def _fav_who(r):
                if pd.notna(r.web_name) and str(r.web_name).strip():
                    return str(r.web_name)
                if pd.notna(r.web_email) and str(r.web_email).strip():
                    return str(r.web_email)
                if pd.notna(r.bu_username) and str(r.bu_username).strip():
                    return "@" + str(r.bu_username).lstrip("@")
                if pd.notna(r.telegram_id):
                    return f"تيليجرام {int(r.telegram_id)}"
                if pd.notna(r.web_user_id):
                    return f"ويب #{int(r.web_user_id)}"
                return "غير معروف"

            def _fav_city(r):
                for v in (r.web_city, r.bu_city):
                    if pd.notna(v) and str(v).strip():
                        return str(v)
                return "—"

            _cadt = (pd.to_datetime(sub_f["created_at"], utc=True, errors="coerce")
                     + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
            out_f = pd.DataFrame({
                "الشخص": sub_f.apply(_fav_who, axis=1).values,
                "المدينة": sub_f.apply(_fav_city, axis=1).values,
                "المنصة": sub_f["platform"].map(_plat_ar).fillna(sub_f["platform"]).values,
                "تاريخ الإضافة": _cadt.dt.strftime("%Y-%m-%d %H:%M").values,
            })
            st.dataframe(out_f, hide_index=True, width='stretch')
            st.caption(f"👥 {len(out_f)} شخص فضّلوا «{cat_sel}» — جمهور التنبيه عند نزول كوبون/خصم جديد في هذا القسم.")

    # ── 5) الأولويات (إدارة يدوية لترتيب الأقسام) ───────────────────────────
    elif _ca_tab == _CA_TABS[4]:
        st.subheader("🏅 إدارة ترتيب الأقسام يدوياً")
        st.caption("الرقم 1 = يظهر أولاً في البوت والموقع · الرقم 5 = الافتراضي")
        try:
            conn_p = get_conn()
            conn_p.autocommit = True
            cur_p  = conn_p.cursor()
            cur_p.execute("""
                INSERT INTO categories_tags (tag_name, priority_rank)
                SELECT DISTINCT trim(tg), 5
                FROM master,
                     unnest(string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',')) AS tg
                WHERE trim(tg) <> ''
                ON CONFLICT (tag_name) DO NOTHING
            """)
            df_pr = pd.read_sql("""
                SELECT tag_name AS "القسم",
                       priority_rank AS "الأولوية (1-5)",
                       COALESCE("Tag_clicks", 0) AS "النقرات",
                       COALESCE(visit_count, 0)  AS "الزيارات"
                FROM categories_tags
                ORDER BY priority_rank ASC, "Tag_clicks" DESC
            """, conn_p)
            conn_p.close()
        except Exception as e:
            st.error(f"⚠️ خطأ في تحميل الأولويات: {e}")
            df_pr = pd.DataFrame()

        if not df_pr.empty:
            st.markdown("**عدّل عمود «الأولوية» ثم اضغط حفظ:**")
            edited_pr = st.data_editor(
                df_pr,
                column_config={
                    "القسم":          st.column_config.TextColumn(disabled=True),
                    "الأولوية (1-5)": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
                    "النقرات":        st.column_config.NumberColumn(disabled=True),
                    "الزيارات":       st.column_config.NumberColumn(disabled=True),
                },
                width='stretch',
                hide_index=True,
                key="priority_editor_1",
            )
            if st.button("💾 حفظ الأولويات", type="primary", key="save_priorities_1"):
                try:
                    conn_s = get_conn()
                    cur_s  = conn_s.cursor()
                    for _, row in edited_pr.iterrows():
                        cur_s.execute(
                            "UPDATE categories_tags SET priority_rank = %s WHERE tag_name = %s",
                            (int(row["الأولوية (1-5)"]), row["القسم"])
                        )
                    conn_s.commit()
                    conn_s.close()
                    st.success(f"✅ تم حفظ أولويات {len(edited_pr)} قسم!")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ فشل الحفظ: {e}")







# ════════════════════════════════════════════════════════════════════════════
#  صفحة «تحليل المتاجر» — جناح ذكاء الأعمال (Store Analytics BI Suite)
#  4 تبويبات: الأداء العام · سلوك المستخدمين والترند · ذكاء الأعمال (AI) · تقارير المعلنين
# ════════════════════════════════════════════════════════════════════════════
elif page == "تحليل المتاجر":
    page_title("📊", "تحليل المتاجر",
               "مستخدمون · مفضلة · حركات — تفضيلات الترند اليدوية في تبويب مستقل")

    # ── تبويبان رئيسيان فوق ────────────────────────────────────────
    sm_tab_main, sm_tab_pin = st.tabs(
        ["📊 تحليل المتاجر", "🎛️ تفضيلات الترند"])

    # ── خرائط الفلاتر ──────────────────────────────────────────────
    _SM_SRC_AR   = {"none": "لا شيء", "all": "الكل",
                     "bot": "📱 البوت", "miniapp": "🔹 الميني-ويب",
                     "web": "🌐 الموقع"}
    _SM_STAT_AR  = {"none": "لا شيء", "all": "الكل",
                     "active": "🟢 فعّال", "expiring": "⏳ قرب ينتهي",
                     "expired": "🗄️ منتهي"}
    _SM_TREND_AR = {"none": "لا شيء", "all": "الكل",
                     "daily": "🌞 يومي", "weekly": "📅 أسبوعي"}
    _SM_FAV_AR   = {"none": "لا شيء", "all": "الكل",
                     "yes": "❤️ مفضل", "no": "🤍 غير مفضل"}
    _SM_ACT_AR   = {"none": "لا شيء", "all": "الكل",
                     "click_link": "🖱️ نقر", "search": "🔍 بحث",
                     "copy_coupon": "🎟️ نسخ"}
    _SM_SRC_LOG  = {"bot": ["bot"],
                     "miniapp": ["telegram_miniapp", "miniapp"],
                     "web": ["web"]}
    _SM_FAV_PLAT = {"bot": ["bot"], "miniapp": ["miniapp"], "web": ["web"]}
    _SM_CHAN_AR  = {"bot": "📱 البوت", "web": "🌐 الموقع",
                     "telegram_miniapp": "🔹 الميني-ويب",
                     "miniapp": "🔹 الميني-ويب"}

    # ════════════════════════════════════════════════════════════════
    # TAB 1: تحليل المتاجر
    # ════════════════════════════════════════════════════════════════
    with sm_tab_main:
        # ─── شريط الفلاتر العلوي: المصدر + تحديث ─────────────────
        _c1, _c2 = st.columns([4, 1])
        with _c1:
            _src_lbl = st.segmented_control(
                "📡 المصدر", list(_SM_SRC_AR.values()),
                default="الكل", key="sm_src_pill")
        with _c2:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("🔄 تحديث", key="sm_refresh",
                         help="مسح الكاش وإعادة التحميل",
                         width='stretch'):
                _sa_load_actions.clear()
                _sa_load_master.clear()
                _sa_load_searches.clear()
                _sa_load_favorites.clear()
                st.rerun()
        _src_key = next((k for k, v in _SM_SRC_AR.items()
                          if v == _src_lbl), "all")

        st.divider()

        # ─── نطاق التاريخ ───────────────────────────────────────
        _d1, _d2 = st.columns(2)
        _today = date.today()
        with _d1:
            sm_date_from = st.date_input(
                "📅 من تاريخ",
                value=_today - timedelta(days=30),
                max_value=_today, key="sm_date_from")
        with _d2:
            sm_date_to = st.date_input(
                "📅 إلى تاريخ", value=_today,
                min_value=sm_date_from, max_value=_today,
                key="sm_date_to")

        st.divider()

        # ─── حالة المتجر ────────────────────────────────────────
        _stat_lbl = st.segmented_control(
            "🏪 حالة المتجر", list(_SM_STAT_AR.values()),
            default="الكل", key="sm_stat_pill")
        _stat_key = next((k for k, v in _SM_STAT_AR.items()
                           if v == _stat_lbl), "all")

        # ─── تحميل البيانات ─────────────────────────────────────
        try:
            df_logs_raw   = _sa_load_actions()
            df_master_raw = _sa_load_master()
            df_search_raw = _sa_load_searches()
            df_fav_raw    = _sa_load_favorites()
        except Exception as _e:
            st.error(f"⚠️ تعذّر تحميل البيانات: {_e}")
            st.stop()

        if df_master_raw.empty:
            st.info("📭 لا توجد متاجر في الماستر.")
            st.stop()

        # ─── فلتر حالة المتجر (last_time = تاريخ انتهاء الكوبون) ─
        # فعّال = NULL أو ≥ today+7 · قرب ينتهي = today ≤ < today+7 ·
        # منتهي = < today
        master = df_master_raw.copy()
        _soon = _today + timedelta(days=7)
        _lt = pd.to_datetime(master.get("last_time"), errors="coerce").dt.date
        if _stat_key == "active":
            master = master[_lt.isna() | (_lt >= _soon)]
        elif _stat_key == "expiring":
            master = master[(~_lt.isna()) & (_lt >= _today) & (_lt < _soon)]
        elif _stat_key == "expired":
            master = master[(~_lt.isna()) & (_lt < _today)]
        # "all" / "none" → لا تفلتر

        # ─── حساب ترند IDs (live algorithm، نوافذ ثابتة) ────────
        _now_r = (pd.Timestamp.utcnow().tz_localize(None)
                  + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        _today_start = _now_r.normalize()
        _week_start  = _now_r - pd.Timedelta(days=7)

        _df_l = df_logs_raw.copy()
        if not _df_l.empty:
            _df_l["action_time"] = (
                pd.to_datetime(_df_l["action_time"], utc=True).dt.tz_localize(None)
                + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        _df_f = df_fav_raw.copy()
        if not _df_f.empty:
            _df_f["created_at"] = (
                pd.to_datetime(_df_f["created_at"], utc=True)
                .dt.tz_localize(None)
                + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))

        _act_ids = set(master["store_id"])
        try:
            _daily_df  = _sa_compute_trend(_df_l, _df_f,
                                            _today_start, _now_r, _act_ids)
            _weekly_df = _sa_compute_trend(_df_l, _df_f,
                                            _week_start, _now_r, _act_ids)
        except Exception:
            _daily_df  = pd.DataFrame()
            _weekly_df = pd.DataFrame()
        daily_ids  = (set(_daily_df["store_id"].tolist()[:3])
                      if not _daily_df.empty else set())
        weekly_ids = (set(_weekly_df["store_id"].tolist()[:7])
                      if not _weekly_df.empty else set())

        # ─── فلتر الترند ────────────────────────────────────────
        _tr_lbl = st.segmented_control(
            "🔥 الترند", list(_SM_TREND_AR.values()),
            default="الكل", key="sm_trend_pill")
        _tr_key = next((k for k, v in _SM_TREND_AR.items()
                         if v == _tr_lbl), "all")
        if _tr_key == "daily":
            master = master[master["store_id"].isin(daily_ids)]
        elif _tr_key == "weekly":
            master = master[master["store_id"].isin(weekly_ids)]

        st.divider()

        # ─── فلتر المفضلة (يُطبَّق على صفوف الجدول لاحقاً) ────────
        _fav_lbl = st.segmented_control(
            "❤️ المفضلة", list(_SM_FAV_AR.values()),
            default="الكل", key="sm_fav_pill")
        _fav_key = next((k for k, v in _SM_FAV_AR.items()
                          if v == _fav_lbl), "all")

        st.divider()

        # ─── اختيار المتجر (يعتمد على الفلاتر السابقة) ──────────
        _store_pool = sorted(master["store_id"].dropna().unique().tolist())
        if not _store_pool:
            st.warning("📭 لا متاجر مطابقة للفلاتر المختارة.")
            st.stop()
        _store_pick = st.selectbox(
            "🏬 المتجر",
            ["لا شيء", "الكل"] + _store_pool,
            index=1, key="sm_store_pick")

        st.divider()

        # ─── فلتر الحركات (action_type) ──────────────────────────
        _act_lbl = st.segmented_control(
            "🎬 الحركات", list(_SM_ACT_AR.values()),
            default="الكل", key="sm_act_pill")
        _act_key = next((k for k, v in _SM_ACT_AR.items()
                          if v == _act_lbl), "all")

        st.divider()

        # ─── تطبيق الفلاتر على البيانات ──────────────────────────
        active_ids = set(master["store_id"])

        # logs (actions)
        df_logs = pd.DataFrame()
        if not df_logs_raw.empty:
            d = df_logs_raw.copy()
            d["action_time"] = (
                pd.to_datetime(d["action_time"], utc=True).dt.tz_localize(None)
                + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
            d["adate"] = d["action_time"].dt.date
            d = d[(d["adate"] >= sm_date_from)
                  & (d["adate"] <= sm_date_to)
                  & (d["store_id"].isin(active_ids))]
            if _src_key in _SM_SRC_LOG:
                d = d[d["source"].isin(_SM_SRC_LOG[_src_key])]
            if _store_pick == "لا شيء":
                d = d.iloc[0:0]
            elif _store_pick != "الكل":
                d = d[d["store_id"] == _store_pick]
            # فلتر نوع الحركة
            if _act_key in ("click_link", "search", "copy_coupon"):
                d = d[d["action_type"] == _act_key]
            df_logs = d

        # searches
        df_search = pd.DataFrame()
        if not df_search_raw.empty:
            s = df_search_raw.copy()
            s["search_date"] = (
                pd.to_datetime(s["search_date"], utc=True).dt.tz_localize(None)
                + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
            s["adate"] = s["search_date"].dt.date
            s = s[(s["adate"] >= sm_date_from)
                  & (s["adate"] <= sm_date_to)
                  & (s["store_id"].notna())
                  & (s["store_id"].isin(active_ids))]
            if _src_key in _SM_SRC_LOG:
                _p = s["platform"].astype(str).str.lower()
                if _src_key == "bot":
                    s = s[(_p.str.contains("bot") | _p.str.contains("telegram"))
                          & ~_p.str.contains("mini")]
                elif _src_key == "miniapp":
                    s = s[_p.str.contains("mini")]
                elif _src_key == "web":
                    s = s[_p.str.contains("web")]
            if _store_pick == "لا شيء":
                s = s.iloc[0:0]
            elif _store_pick != "الكل":
                s = s[s["store_id"] == _store_pick]
            # فلتر الحركات: البحث يطلع فقط لو الفلتر "بحث" أو "الكل" أو "لا شيء"
            if _act_key in ("click_link", "copy_coupon"):
                s = s.iloc[0:0]
            df_search = s

        # favorites
        df_fav = pd.DataFrame()
        if not df_fav_raw.empty:
            f = df_fav_raw.copy()
            if "kind" in f.columns:
                f = f[f["kind"] == "store"]
            f["created_at"] = (
                pd.to_datetime(f["created_at"], utc=True)
                .dt.tz_localize(None)
                + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
            f["adate"] = f["created_at"].dt.date
            f = f[(f["adate"] >= sm_date_from)
                  & (f["adate"] <= sm_date_to)
                  & (f["store_id"].isin(active_ids))]
            if _src_key in _SM_FAV_PLAT:
                f = f[f["platform"].isin(_SM_FAV_PLAT[_src_key])]
            if _store_pick == "لا شيء":
                f = f.iloc[0:0]
            elif _store_pick != "الكل":
                f = f[f["store_id"] == _store_pick]
            # فلتر الحركات: المفضلة تظهر فقط لو الفلتر "الكل" أو "لا شيء"
            if _act_key in ("click_link", "search", "copy_coupon"):
                f = f.iloc[0:0]
            df_fav = f

        # ─── ملخّص ──────────────────────────────────────────────
        st.caption(
            f"📅 {sm_date_from} ← {sm_date_to} · "
            f"المصدر: {_src_lbl} · حالة: {_stat_lbl} · "
            f"ترند: {_tr_lbl} · مفضلة: {_fav_lbl} · "
            f"حركات: {_act_lbl} · متجر: {_store_pick} · "
            f"السطور: حركات **{len(df_logs):,}** · "
            f"بحث **{len(df_search):,}** · "
            f"مفضلة **{len(df_fav):,}**")

        # ─── helpers للهوية والبيانات الشخصية ──────────────────
        def _clean(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        def _name(r):
            src = r.get("source", "")
            v = _clean(r.get("web_name"))
            if v: return v
            v = _clean(r.get("bu_username"))
            if v: return "@" + v.lstrip("@")
            if src in ("telegram_miniapp", "miniapp"):
                if pd.notna(r.get("user_id")):
                    return f"🔹 ميني #{int(r['user_id'])}"
            if src == "web":
                h = _clean(r.get("ip_hex"))
                if h: return f"🌐 زائر #{h[:6]}"
                return "🌐 زائر"
            if pd.notna(r.get("user_id")):
                return f"📱 #{int(r['user_id'])}"
            return "—"

        def _email(r): return _clean(r.get("web_email")) or "—"
        def _phone(r): return _clean(r.get("web_phone")) or "—"
        def _tg(r):
            v = _clean(r.get("web_tg")) or _clean(r.get("bu_username"))
            return ("@" + v.lstrip("@")) if v else "—"
        def _city(r):
            return (_clean(r.get("geo_city"))
                    or _clean(r.get("web_city"))
                    or _clean(r.get("bu_city")) or "—")

        # ════════════════════════════════════════════════════════
        # 📋 الجدول الموحّد — مستخدم × متجر مع كل البيانات
        # ════════════════════════════════════════════════════════
        st.markdown("### 📋 الجدول")
        st.caption(
            "صف لكل (مستخدم × متجر) — يدمج الحركات + المفضلة. فلتر «الحركات» "
            "أعلاه يحدد ما يُعرض (نقر/بحث/نسخ/الكل/لا شيء).")

        # aggregate من df_logs
        _grp_keys = (["user_id", "ip_hex", "store_id"]
                     if _store_pick == "الكل"
                     else ["user_id", "ip_hex"])

        if not df_logs.empty:
            ev = df_logs.copy()
            ev["copy"]   = (ev["action_type"] == "copy_coupon").astype(int)
            ev["click"]  = (ev["action_type"] == "click_link").astype(int)
            ev["srch"]   = (ev["action_type"] == "search").astype(int)
            agg = (ev.groupby(_grp_keys, dropna=False)
                     .agg(copy=("copy", "sum"),
                          click=("click", "sum"),
                          srch=("srch", "sum"),
                          first_action=("action_time", "min"),
                          last_action=("action_time", "max"),
                          src_any=("source", lambda s: "، ".join(sorted(set(
                              _SM_CHAN_AR.get(x, x) for x in s)))))
                     .reset_index())
            _pcols = [c for c in ["user_id", "ip_hex", "source", "web_name",
                                    "web_email", "web_phone", "web_tg",
                                    "web_city", "bu_username", "bu_city",
                                    "geo_city"] if c in ev.columns]
            prof = (ev[_pcols]
                    .drop_duplicates(subset=["user_id", "ip_hex"])
                    .reset_index(drop=True))
            agg = agg.merge(prof, on=["user_id", "ip_hex"], how="left")
        else:
            agg = pd.DataFrame()

        # إضافة rows من df_fav للمفضّلين بدون حركات (الفلتر يسمح)
        if not df_fav.empty:
            f = df_fav.copy()
            f["user_id"] = f["telegram_id"].fillna(f["web_user_id"])
            f["ip_hex"]  = None

            if _store_pick == "الكل":
                _exist = (set(zip(agg["user_id"], agg["store_id"]))
                          if not agg.empty else set())
                _missing = [
                    (uid, sid) not in _exist
                    for uid, sid in zip(f["user_id"], f["store_id"])
                ]
            else:
                _exist = (set(agg["user_id"]) if not agg.empty else set())
                _missing = [uid not in _exist for uid in f["user_id"]]
            miss = f[_missing]
            if not miss.empty:
                _plat_ar = {"bot": "📱 البوت", "web": "🌐 الموقع",
                             "miniapp": "🔹 الميني-ويب"}
                new_rows = {
                    "user_id":     miss["user_id"].values,
                    "ip_hex":      [None] * len(miss),
                    "copy":        [0] * len(miss),
                    "click":       [0] * len(miss),
                    "srch":        [0] * len(miss),
                    "first_action": miss["created_at"].values,
                    "last_action": miss["created_at"].values,
                    "src_any":     miss["platform"].map(_plat_ar)
                                       .fillna(miss["platform"]).values,
                    "source":      miss["platform"].values,
                    "web_name":    miss["web_name"].values,
                    "web_email":   miss["web_email"].values,
                    "web_phone":   miss["web_phone"].values,
                    "web_tg":      miss["web_tg"].values,
                    "web_city":    miss["web_city"].values,
                    "bu_username": miss["bu_username"].values,
                    "bu_city":     miss["bu_city"].values,
                    "geo_city":    [""] * len(miss),
                }
                if _store_pick == "الكل":
                    new_rows["store_id"] = miss["store_id"].values
                agg = pd.concat([agg, pd.DataFrame(new_rows)],
                                 ignore_index=True)

        if agg.empty:
            st.info("📭 لا بيانات للفلاتر المختارة.")
        else:
            # عمود "مفضل" — match (user, store) مع df_fav الكامل (مش المفلتر بالحركات)
            _fav_full = df_fav_raw.copy()
            if not _fav_full.empty:
                if "kind" in _fav_full.columns:
                    _fav_full = _fav_full[_fav_full["kind"] == "store"]
                _fav_full["uid"] = _fav_full["telegram_id"].fillna(
                    _fav_full["web_user_id"])
                _fav_set = set(zip(_fav_full["uid"], _fav_full["store_id"]))
            else:
                _fav_set = set()

            if _store_pick == "الكل":
                agg["مفضل"] = [
                    "✅ نعم" if (uid, sid) in _fav_set else "—"
                    for uid, sid in zip(agg["user_id"], agg["store_id"])
                ]
            else:
                _fixed_sid = (_store_pick if _store_pick not in
                              ("الكل", "لا شيء") else None)
                agg["مفضل"] = [
                    "✅ نعم" if (uid, _fixed_sid) in _fav_set else "—"
                    for uid in agg["user_id"]
                ]

            # تطبيق فلتر المفضلة pill
            if _fav_key == "yes":
                agg = agg[agg["مفضل"] == "✅ نعم"]
            elif _fav_key == "no":
                agg = agg[agg["مفضل"] != "✅ نعم"]

            agg["الاسم"]    = agg.apply(_name, axis=1)
            agg["الإيميل"]  = agg.apply(_email, axis=1)
            agg["الجوال"]   = agg.apply(_phone, axis=1)
            agg["تيليجرام"] = agg.apply(_tg, axis=1)
            agg["المدينة"]  = agg.apply(_city, axis=1)
            agg["تاريخ أول حركة"] = pd.to_datetime(
                agg["first_action"], errors="coerce").dt.strftime(
                    "%Y-%m-%d %H:%M")
            agg["تاريخ آخر حركة"] = pd.to_datetime(
                agg["last_action"], errors="coerce").dt.strftime(
                    "%Y-%m-%d %H:%M")
            agg = agg.rename(columns={"src_any": "المصدر",
                                       "store_id": "المتجر",
                                       "copy": "نسخ", "click": "نقر",
                                       "srch": "بحث"})
            agg["إجمالي الحركات"] = agg["نسخ"] + agg["نقر"] + agg["بحث"]

            _cols = ["الاسم", "الإيميل", "الجوال", "تيليجرام",
                      "المدينة", "المصدر"]
            if _store_pick == "الكل":
                _cols.append("المتجر")
            _cols += ["نسخ", "نقر", "بحث", "إجمالي الحركات",
                       "مفضل", "تاريخ أول حركة", "تاريخ آخر حركة"]
            agg = agg.sort_values("إجمالي الحركات", ascending=False)
            st.dataframe(agg[_cols], hide_index=True, width='stretch')
            st.caption(f"📋 {len(agg)} صف.")

            _ub = BytesIO()
            with pd.ExcelWriter(_ub, engine="xlsxwriter") as _w:
                agg[_cols].to_excel(_w, sheet_name="تحليل المتاجر",
                                      index=False)
            _ub.seek(0)
            st.download_button(
                "📥 تحميل Excel",
                data=_ub.getvalue(),
                file_name=(f"stores_analytics_"
                            f"{sm_date_from.strftime('%Y%m%d')}_"
                            f"{sm_date_to.strftime('%Y%m%d')}.xlsx"),
                mime=("application/vnd.openxmlformats-officedocument"
                       ".spreadsheetml.sheet"),
                key="sm_unified_xlsx")

    # ════════════════════════════════════════════════════════════════
    # TAB 2: 🎛️ تفضيلات الترند (admin pinning)
    # ════════════════════════════════════════════════════════════════
    with sm_tab_pin:
        st.markdown("### 🎛️ التحكم اليدوي بمراكز الترند")
        st.caption(
            "ثبّت متجراً في مركز محدد — الباقي يتزحّح تلقائياً. الخوارزمية "
            "تحسب النقاط (نقر=1، بحث=2، نسخ=3، مفضلة=4) مع anti-spam؛ "
            "التثبيت اليدوي يطغى عليها. التغيير يظهر للزوار خلال **دقيقة** "
            "(كاش API).")

        try:
            _ov_conn = get_conn()
            _ov_conn.rollback()
            with _ov_conn.cursor() as _cur:
                _cur.execute("""
                    CREATE TABLE IF NOT EXISTS trend_overrides (
                        id BIGSERIAL PRIMARY KEY,
                        window_kind TEXT NOT NULL CHECK (window_kind IN ('daily','weekly')),
                        rank INTEGER NOT NULL CHECK (rank >= 1 AND rank <= 10),
                        store_id TEXT NOT NULL,
                        set_at TIMESTAMPTZ DEFAULT NOW(),
                        set_by TEXT,
                        CONSTRAINT trend_overrides_uniq_rank UNIQUE (window_kind, rank),
                        CONSTRAINT trend_overrides_uniq_store UNIQUE (window_kind, store_id)
                    )
                """)
                _ov_conn.commit()
            _df_ov = pd.read_sql(
                "SELECT window_kind AS window, rank, store_id FROM trend_overrides",
                _ov_conn)
        except Exception as _e:
            st.error(f"⚠️ تعذّر قراءة التجاوزات: {_e}")
            _df_ov = pd.DataFrame(columns=["window", "rank", "store_id"])
        finally:
            try: _ov_conn.close()
            except Exception: pass

        _ov_daily = (dict(zip(
            _df_ov[_df_ov["window"] == "daily"]["rank"].astype(int),
            _df_ov[_df_ov["window"] == "daily"]["store_id"]))
            if not _df_ov.empty else {})
        _ov_weekly = (dict(zip(
            _df_ov[_df_ov["window"] == "weekly"]["rank"].astype(int),
            _df_ov[_df_ov["window"] == "weekly"]["store_id"]))
            if not _df_ov.empty else {})

        try:
            _master_for_pin = _sa_load_master()
        except Exception:
            _master_for_pin = pd.DataFrame(columns=["store_id"])
        _store_options = (sorted(_master_for_pin["store_id"]
                                   .dropna().astype(str).unique().tolist())
                          if not _master_for_pin.empty else [])
        _AUTO = "⚙️ تلقائي (بدون تثبيت)"
        _option_list = [_AUTO] + _store_options

        _DAILY_TITLES = {
            1: "🥇 المركز 1 — الأعلى طلباً",
            2: "🥈 المركز 2 — الأكثر شعبية",
            3: "🥉 المركز 3 — الأوسع انتشاراً",
        }
        _WEEKLY_TITLES = {
            1: "🥇 المركز 1 — الأعلى طلباً",
            2: "🥈 المركز 2 — الأكثر شعبية",
            3: "🥉 المركز 3 — الأوسع انتشاراً",
            4: "🏅 المركز 4 — الرابع",
            5: "🏅 المركز 5 — الخامس",
            6: "🏅 المركز 6 — السادس",
            7: "🏅 المركز 7 — السابع",
        }

        def _pin_picker(window: str, rank: int, label: str, current):
            idx = (_option_list.index(current)
                   if current in _option_list else 0)
            pick = st.selectbox(label, _option_list, index=idx,
                                 key=f"pin_tab_{window}_{rank}")
            return None if pick == _AUTO else pick

        st.markdown("##### 🌞 الترند اليومي (3 مراكز)")
        _daily_picks: dict[int, str | None] = {}
        for _rk, _lbl in _DAILY_TITLES.items():
            _daily_picks[_rk] = _pin_picker(
                "daily", _rk, _lbl, _ov_daily.get(_rk))

        st.markdown("##### 📅 الترند الأسبوعي (7 مراكز)")
        _weekly_picks: dict[int, str | None] = {}
        _w_cols = st.columns(2)
        for _i, (_rk, _lbl) in enumerate(_WEEKLY_TITLES.items()):
            with _w_cols[_i % 2]:
                _weekly_picks[_rk] = _pin_picker(
                    "weekly", _rk, _lbl, _ov_weekly.get(_rk))

        _b1, _b2 = st.columns(2)
        with _b1:
            _save = st.button("💾 حفظ التجاوزات", width='stretch',
                              key="pin_tab_save", type="primary")
        with _b2:
            _clear = st.button("🧹 مسح كل التجاوزات", width='stretch',
                                key="pin_tab_clear")

        if _save:
            def _dup_in(picks: dict) -> str | None:
                seen = {}
                for rk, sid in picks.items():
                    if sid and sid in seen:
                        return (f"المتجر «{sid}» مكرّر في مركزين "
                                f"({seen[sid]} و {rk})")
                    if sid:
                        seen[sid] = rk
                return None
            err = _dup_in(_daily_picks) or _dup_in(_weekly_picks)
            if err:
                st.error(f"⚠️ {err}")
            else:
                try:
                    _sv = get_conn()
                    with _sv.cursor() as _cur:
                        _cur.execute("DELETE FROM trend_overrides")
                        _rows = []
                        for rk, sid in _daily_picks.items():
                            if sid: _rows.append(("daily", rk, sid))
                        for rk, sid in _weekly_picks.items():
                            if sid: _rows.append(("weekly", rk, sid))
                        if _rows:
                            _cur.executemany(
                                "INSERT INTO trend_overrides "
                                "(window_kind, rank, store_id) "
                                "VALUES (%s, %s, %s)", _rows)
                        _sv.commit()
                    st.success(f"✅ تم حفظ {len(_rows)} تجاوز.")
                except Exception as _e:
                    st.error(f"⚠️ فشل الحفظ: {_e}")
                finally:
                    try: _sv.close()
                    except Exception: pass
                st.rerun()

        if _clear:
            try:
                _cl = get_conn()
                with _cl.cursor() as _cur:
                    _cur.execute("DELETE FROM trend_overrides")
                    _cl.commit()
                st.success("✅ تم مسح كل التجاوزات.")
            except Exception as _e:
                st.error(f"⚠️ فشل المسح: {_e}")
            finally:
                try: _cl.close()
                except Exception: pass
            st.rerun()

        if not _df_ov.empty:
            _show = _df_ov.copy()
            _show["window"] = _show["window"].map(
                {"daily": "🌞 يومي", "weekly": "📅 أسبوعي"})
            _show = _show.rename(columns={
                "window": "النافذة", "rank": "المركز", "store_id": "المتجر"})
            st.divider()
            st.markdown("**📋 التجاوزات الحالية:**")
            st.dataframe(_show, hide_index=True, width='stretch')


# ════════════════════════════════════════════════════════════════════════════
# 🎬 إضافة استوري — عدة شرائح (فيديو/صورة) لكل متجر + تفعيل الإشهار
#    الشرائح → جدول story_slides (متعدد/متجر) ، العضوية → is_promoted.
#    التحليلات (story_views) والترند بلا تغيير — مربوطة بالمتجر تلقائياً.
# ════════════════════════════════════════════════════════════════════════════
elif page == "🎬 إضافة استوري":
    st.header("🎬 إضافة استوري")
    st.caption(
        "لكل متجر عدة شرائح (فيديو/صورة) تُعرض كقصص متتابعة. فعّل الإشهار ليظهر المتجر "
        "في صف الستوري بالموقع والميني-ويب. المشاهدات والترند تُحسب باسم المتجر."
    )

    if st.button("🔄 تحديث", key="story_add_refresh", help="إعادة تحميل البيانات"):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

    _sc = get_conn(); _sc.rollback()
    try:
        _stores_df = pd.read_sql(
            "SELECT id, store_id, COALESCE(NULLIF(name_en,''), store_id) AS name_en, "
            "COALESCE(is_promoted, FALSE) AS is_promoted "
            "FROM master ORDER BY id DESC",
            _sc,
        )
    except Exception as _e:
        st.error(f"تعذّر جلب المتاجر: {_e}")
        _stores_df = pd.DataFrame()
    finally:
        _sc.close()

    if _stores_df.empty:
        st.info("لا توجد متاجر بعد. أضف متجراً أولاً من «إدخال بيانات الماستر».")
    else:
        _labels = {
            int(r["id"]): f'{r["store_id"]} · {r["name_en"]} (#{int(r["id"])})'
            for _, r in _stores_df.iterrows()
        }
        _sel_id = st.selectbox(
            "🏪 اختر المتجر",
            options=list(_labels.keys()),
            format_func=lambda i: _labels[i],
            key="story_store_select",
        )
        _srow = _stores_df[_stores_df["id"] == _sel_id].iloc[0]
        _cur_promoted = bool(_srow["is_promoted"])

        # ── حالة الإشهار (عضوية صف الستوري) ──
        pc1, pc2 = st.columns([3, 1])
        _promote = pc1.checkbox(
            "📣 فعّل الإشهار (يظهر المتجر في صف الستوري وقسم «المتاجر المختارة»)",
            value=_cur_promoted, key="story_promote_chk",
        )
        with pc2:
            st.write("")
            if st.button("💾 حفظ الإشهار", width="stretch", key="story_promote_save"):
                try:
                    _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                    _wcur.execute("UPDATE master SET is_promoted=%s WHERE id=%s",
                                  (bool(_promote), int(_sel_id)))
                    _wc.commit(); _wc.close()
                    st.success("✅ حُفظت حالة الإشهار."); st.rerun()
                except Exception as _e:
                    st.error(f"تعذّر الحفظ: {_e}")

        st.divider()
        st.subheader("🎬 شرائح هذا المتجر")

        _slc = get_conn(); _slc.rollback()
        try:
            _slides = pd.read_sql(
                "SELECT id, media_url, sort_order FROM story_slides "
                "WHERE master_id=%s ORDER BY sort_order, id",
                _slc, params=(int(_sel_id),),
            )
        except Exception as _e:
            st.error(f"تعذّر جلب الشرائح: {_e}")
            _slides = pd.DataFrame()
        finally:
            _slc.close()

        if _slides.empty:
            st.info("لا شرائح بعد لهذا المتجر — يعرض المتجر شعاره. أضف أول شريحة أدناه.")
        else:
            st.caption(f"{len(_slides)} شريحة — تُعرض بهذا الترتيب.")
            _n = len(_slides)
            for _i in range(_n):
                _sr = _slides.iloc[_i]
                _sid = int(_sr["id"]); _murl = _sr["media_url"]
                with st.container(border=True):
                    mc1, mc2 = st.columns([1, 2])
                    with mc1:
                        try:
                            if _is_video_url(_murl):
                                st.video(_murl)
                            else:
                                st.image(_murl, width=160)
                        except Exception:
                            pass
                    with mc2:
                        st.caption(
                            f"ترتيب {_i + 1} · "
                            f"{'🎬 فيديو' if _is_video_url(_murl) else '🖼️ صورة'} · #{_sid}")
                        st.code(_murl, language="text")
                        b1, b2, b3 = st.columns(3)
                        # ⬆️ رفع الترتيب (تبديل مع السابق)
                        if b1.button("⬆️", key=f"sl_up_{_sid}", width="stretch",
                                     disabled=(_i == 0), help="تقديم"):
                            _prev = _slides.iloc[_i - 1]
                            try:
                                _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                                _wcur.execute("UPDATE story_slides SET sort_order=%s WHERE id=%s",
                                              (int(_prev["sort_order"]), _sid))
                                _wcur.execute("UPDATE story_slides SET sort_order=%s WHERE id=%s",
                                              (int(_sr["sort_order"]), int(_prev["id"])))
                                _wc.commit(); _wc.close(); st.rerun()
                            except Exception as _e:
                                st.error(f"تعذّر: {_e}")
                        # ⬇️ خفض الترتيب (تبديل مع التالي)
                        if b2.button("⬇️", key=f"sl_dn_{_sid}", width="stretch",
                                     disabled=(_i == _n - 1), help="تأخير"):
                            _nxt = _slides.iloc[_i + 1]
                            try:
                                _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                                _wcur.execute("UPDATE story_slides SET sort_order=%s WHERE id=%s",
                                              (int(_nxt["sort_order"]), _sid))
                                _wcur.execute("UPDATE story_slides SET sort_order=%s WHERE id=%s",
                                              (int(_sr["sort_order"]), int(_nxt["id"])))
                                _wc.commit(); _wc.close(); st.rerun()
                            except Exception as _e:
                                st.error(f"تعذّر: {_e}")
                        if b3.button("🗑️ حذف", key=f"sl_del_{_sid}", width="stretch"):
                            try:
                                _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                                _wcur.execute("DELETE FROM story_slides WHERE id=%s", (_sid,))
                                _wc.commit(); _wc.close()
                                st.toast("🗑️ حُذفت الشريحة"); st.rerun()
                            except Exception as _e:
                                st.error(f"تعذّر الحذف: {_e}")

        st.divider()
        st.subheader("➕ أضف شريحة")
        with st.form("add_story_slide", clear_on_submit=True):
            af1, af2 = st.columns(2)
            _media_file = af1.file_uploader(
                "ارفع فيديو أو صورة",
                type=["mp4", "webm", "mov", "png", "jpg", "jpeg", "webp"],
                key="story_slide_file",
                help="فيديو (mp4/webm/mov) أو صورة (png/jpg/webp). يُرفع إلى Cloudinary.",
            )
            _media_url_input = af2.text_input(
                "أو الصق رابط مباشر", placeholder="https://...", key="story_slide_url")
            if st.form_submit_button("➕ أضف الشريحة", type="primary"):
                import time as _t
                _final = (_media_url_input or "").strip()
                if _media_file and not _final:
                    with st.spinner("جارٍ الرفع إلى Cloudinary..."):
                        _final = _upload_story_media(
                            _media_file.read(),
                            f"{_srow['store_id']}_{int(_t.time())}")
                if not _final:
                    st.error("ارفع ملفاً صالحاً أو الصق رابطاً مباشراً.")
                else:
                    try:
                        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                        _wcur.execute(
                            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM story_slides "
                            "WHERE master_id=%s", (int(_sel_id),))
                        _next_order = _wcur.fetchone()[0]
                        _wcur.execute(
                            "INSERT INTO story_slides (master_id, media_url, sort_order, is_active) "
                            "VALUES (%s, %s, %s, TRUE)",
                            (int(_sel_id), _final, int(_next_order)))
                        _wc.commit(); _wc.close()
                        st.success("✅ أُضيفت الشريحة."); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر الإضافة: {_e}")


# ════════════════════════════════════════════════════════════════════════════
# 🎬 تحليلات الستوري (Migration 029) — صفحة مستقلة
#    مصدر البيانات: story_views + action_logs.story_view_id
#    تابز: الكل / 🌐 الموقع / 🔹 الميني-ويب
# ════════════════════════════════════════════════════════════════════════════
elif page == "🎬 تحليلات الستوري":
    st.header("🎬 تحليلات الستوري")
    st.caption(
        "سجل مسار العميل من داخل الستوري فقط — لو خرج من الستوري وراح للمتجر بطريق ثاني، "
        "الحركات ما تتحسب هنا. تصنيف «ترند/عادي» = snapshot لحظة الفتح من خوارزمية "
        "‎/api/v1/trend (يومي ∪ أسبوعي) — مطابق للحلقة البرتقالية اللي شافها العميل. "
        "السجلات قبل migration 034 تظهر «— غير معروف» لأن البيانات التاريخية مفقودة "
        "(ما نخترع تصنيف)."
    )

    # ─── شريط الفلاتر: المصدر (segmented_control) + زر تحديث ─────────
    _sv_c1, _sv_c2 = st.columns([4, 1])
    with _sv_c1:
        # «الكل»            = صف لكل (عميل × متجر × قناة) — تفصيلي
        # «🏪 إجمالي المتجر» = صف لكل متجر — يجمع كل العملاء + كل القنوات
        # «👤 إجمالي العميل» = صف لكل (عميل × متجر) — يدمج القنوات (موقع+ميني)
        # «🔹 الميني/🌐 الموقع» = فلتر قناة فقط
        _SV_SRC_AR = {"all": "الكل",
                      "store_total":    "🏪 إجمالي المتجر",
                      "customer_total": "👤 إجمالي العميل",
                      "telegram_miniapp": "🔹 الميني-ويب",
                      "web": "🌐 الموقع"}
        _sv_src_label = st.segmented_control(
            "📡 المصدر", list(_SV_SRC_AR.values()),
            default="الكل", key="sv_src",
        )
        sv_source_filter = next((k for k, v in _SV_SRC_AR.items()
                                 if v == _sv_src_label), "all")
        sv_agg_mode = sv_source_filter if sv_source_filter in ("store_total", "customer_total") else None
        if sv_source_filter in ("all", "store_total", "customer_total"):
            sv_source_filter = None
    with _sv_c2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("🔄 تحديث", key="sv_refresh",
                     help="مسح الكاش وإعادة التحميل"):
            try: st.cache_data.clear()
            except Exception: pass
            st.rerun()

    st.divider()

    # ─── نطاق التاريخ ────────────────────────────────────────────────
    _sv_d1, _sv_d2 = st.columns(2)
    _sv_today = date.today()
    with _sv_d1:
        sv_date_from = st.date_input(
            "📅 من تاريخ", value=_sv_today - timedelta(days=30),
            max_value=_sv_today, key="sv_date_from",
        )
    with _sv_d2:
        sv_date_to = st.date_input(
            "📅 إلى تاريخ", value=_sv_today,
            min_value=sv_date_from, max_value=_sv_today, key="sv_date_to",
        )

    st.divider()

    # ─── فلتر المشاهدات: الكل / عادي / ترند (master.is_trending) ─────
    _SV_TREND_AR = {"all": "الكل", "normal": "🎬 عادي", "trend": "🔥 ترند"}
    _sv_trend_label = st.segmented_control(
        "🔥 المشاهدات", list(_SV_TREND_AR.values()),
        default="الكل", key="sv_trend",
    )
    sv_trend_filter = next((k for k, v in _SV_TREND_AR.items()
                            if v == _sv_trend_label), "all")

    st.divider()

    _sv_t_from = pd.Timestamp(sv_date_from).strftime("%Y-%m-%d 00:00:00")
    _sv_t_to   = (pd.Timestamp(sv_date_to) + pd.Timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    # ─── بنّاء WHERE لـ story_views ──────────────────────────────────
    # was_trending هو snapshot دقيق محفوظ لحظة الـ INSERT في track.py،
    # محسوب من compute_trending_store_ids (يطابق /api/v1/trend الحي).
    # ما نقدر نخترع تصنيف للسجلات القديمة (NULL)؛ فلتر «ترند» و «عادي»
    # يستثنيها، فلتر «الكل» يضمّها.
    def _sv_build_where(alias="sv"):
        parts  = [f"{alias}.viewed_at >= %s", f"{alias}.viewed_at < %s"]
        params = [_sv_t_from, _sv_t_to]
        if sv_source_filter:
            parts.append(f"{alias}.source = %s")
            params.append(sv_source_filter)
        if sv_trend_filter == "trend":
            parts.append(f"{alias}.was_trending IS TRUE")
        elif sv_trend_filter == "normal":
            parts.append(f"{alias}.was_trending IS FALSE")
        return "WHERE " + " AND ".join(parts), params

    try:
        conn_st = get_conn()
        conn_st.rollback()

        sv_where, sv_params = _sv_build_where("sv")

        # ─── سجل مسار العميل: صف لكل (عميل × متجر) ──────────────────────
        # العدّ يربط النسخ/النقرات بفتحات الستوري عبر action_logs.story_view_id
        # — أي حركة خارج الستوري (story_view_id IS NULL) لا تحسب هنا.
        journey = pd.read_sql(f"""
            WITH sv_f AS (
              SELECT sv.view_id, sv.store_id, sv.source,
                     sv.web_user_id, sv.tg_user_id, sv.viewed_at,
                     -- was_trending: TRUE/FALSE = snapshot موثوق وقت الفتح،
                     -- NULL = صف قبل migration 034 (لا تصنيف تاريخي).
                     sv.was_trending
              FROM story_views sv
              {sv_where}
            ),
            agg AS (
              SELECT
                web_user_id, tg_user_id, store_id,
                MIN(source)                              AS source,
                COUNT(*)                                 AS views,
                BOOL_OR(was_trending IS TRUE)            AS any_trending,
                BOOL_OR(was_trending IS NULL)            AS has_unknown,
                MIN(viewed_at)                           AS first_view,
                MAX(viewed_at)                           AS last_view,
                ARRAY_AGG(view_id)                       AS view_ids
              FROM sv_f
              GROUP BY web_user_id, tg_user_id, store_id
            ),
            acts AS (
              SELECT
                a.web_user_id, a.tg_user_id, a.store_id,
                SUM(CASE WHEN al.action_type='copy_coupon' THEN 1 ELSE 0 END) AS copies,
                SUM(CASE WHEN al.action_type='click_link'  THEN 1 ELSE 0 END) AS clicks
              FROM agg a
              LEFT JOIN action_logs al
                ON al.story_view_id = ANY(a.view_ids)
               AND al.store_id      = a.store_id
               AND al.action_type IN ('copy_coupon','click_link')
              GROUP BY a.web_user_id, a.tg_user_id, a.store_id
            )
            SELECT
              agg.source                                                  AS source,
              COALESCE(wu.display_name, bu.username, '—')                 AS العميل,
              COALESCE('@' || NULLIF(wu.telegram_username, ''),
                       '@' || NULLIF(bu.username, ''), '—')               AS تيليجرام,
              COALESCE(wu.email, '—')                                     AS الإيميل,
              COALESCE(wu.phone_number, '—')                              AS الجوال,
              agg.store_id                                                AS المتجر,
              CASE
                WHEN agg.any_trending             THEN '🔥 ترند'
                WHEN agg.has_unknown              THEN '— غير معروف'
                ELSE '🎬 عادي'
              END                                                         AS حالة_الستوري,
              agg.views                                                   AS مرات_المشاهدة,
              CASE WHEN COALESCE(acts.clicks, 0) > 0 THEN '✅ نعم' ELSE '❌ لا' END
                                                                          AS دخل_المتجر,
              COALESCE(acts.clicks, 0)                                    AS عدد_الزيارات,
              CASE WHEN COALESCE(acts.copies, 0) > 0 THEN '✅ نعم' ELSE '❌ لا' END
                                                                          AS نسخ_الكود,
              COALESCE(acts.copies, 0)                                    AS عدد_النسخ,
              agg.last_view                                               AS آخر_مشاهدة
            FROM agg
            -- IS NOT DISTINCT FROM: ربط آمن مع NULL — صفوف الموقع فيها tg_user_id=NULL
            -- وصفوف الميني فيها web_user_id=NULL؛ USING/= كانت تفشل (NULL=NULL ليس TRUE)
            -- فتظهر كل النسخ/النقرات أصفاراً. هذا الربط يطابق NULL مع NULL.
            LEFT JOIN acts
                   ON acts.web_user_id IS NOT DISTINCT FROM agg.web_user_id
                  AND acts.tg_user_id  IS NOT DISTINCT FROM agg.tg_user_id
                  AND acts.store_id     = agg.store_id
            LEFT JOIN web_users wu ON wu.id          = agg.web_user_id
            LEFT JOIN bot_users bu ON bu.telegram_id = agg.tg_user_id
            ORDER BY agg.last_view DESC, agg.views DESC
        """, conn_st, params=sv_params)

        if journey.empty:
            st.info("📭 لا توجد بيانات ستوري في النطاق/الفلتر المختار.")
        else:
            journey["المصدر"] = journey["source"].map(
                {"web": "🌐 الموقع", "telegram_miniapp": "🔹 الميني ويب"}).fillna(journey["source"])
            # باندا يقرأ timestamptz كـ UTC ويعرضه UTC؛ +3 لعرض توقيت الرياض (نفس
            # نمط RIYADH_TZ_OFFSET_HOURS في باقي الداشبورد). tz-aware + Timedelta سليم.
            journey["آخر_مشاهدة"] = (pd.to_datetime(journey["آخر_مشاهدة"], errors="coerce", utc=True)
                                     + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS)).dt.strftime("%Y-%m-%d %H:%M")
            journey.drop(columns=["source"], inplace=True)

            # ─── الدمج: «إجمالي المتجر» أو «إجمالي العميل» ───────────────
            # مفتاح الشخص الموحَّد عبر القنوات: tg username → email → اسم.
            # سلوك الجمع: الأعداد تُجمع، حالة الستوري bool_or، أعلام «نعم/لا»
            # تتحول لـ«نعم» لو في واحد قال نعم، التواريخ MAX.
            if sv_agg_mode in ("store_total", "customer_total"):
                def _pkey(r):
                    tg = str(r.get("تيليجرام") or "").strip()
                    if tg and tg not in ("—", "@"): return f"tg:{tg.lower()}"
                    em = str(r.get("الإيميل") or "").strip()
                    if em and em != "—": return f"em:{em.lower()}"
                    return f"nm:{str(r.get('العميل') or '').strip().lower()}"

                # المشتركة: تجميع الأعمدة بنفس النمط
                _yes = lambda s: "✅ نعم" if (s == "✅ نعم").any() else "❌ لا"
                _trend = lambda s: ("🔥 ترند" if (s == "🔥 ترند").any()
                                    else ("— غير معروف" if (s == "— غير معروف").any() else "🎬 عادي"))
                _src_join = lambda s: " + ".join(sorted(set(s.dropna())))
                _first_nonempty = lambda s: next((v for v in s if v and v != "—"), "—")

                if sv_agg_mode == "store_total":
                    # صف لكل متجر: لا يهمنا العميل ولا بياناته — نحذفها
                    # ونعرض فقط أرقام أداء المتجر (مشاهدات، زيارات، نسخ، الحالة).
                    _agg_spec = {
                        "المصدر":         _src_join,
                        "حالة_الستوري":   _trend,
                        "مرات_المشاهدة":  "sum",
                        "دخل_المتجر":     _yes,
                        "عدد_الزيارات":   "sum",
                        "نسخ_الكود":      _yes,
                        "عدد_النسخ":      "sum",
                        "آخر_مشاهدة":     "max",
                    }
                    journey = journey.groupby(["المتجر"], as_index=False).agg(_agg_spec)
                else:   # customer_total: web+miniapp لنفس الشخص في صف واحد
                    journey["_pk"] = journey.apply(_pkey, axis=1)
                    _agg_spec = {
                        "المصدر":         _src_join,
                        "العميل":         "first",
                        "تيليجرام":       _first_nonempty,
                        "الإيميل":        _first_nonempty,
                        "الجوال":         _first_nonempty,
                        "حالة_الستوري":   _trend,
                        "مرات_المشاهدة":  "sum",
                        "دخل_المتجر":     _yes,
                        "عدد_الزيارات":   "sum",
                        "نسخ_الكود":      _yes,
                        "عدد_النسخ":      "sum",
                        "آخر_مشاهدة":     "max",
                    }
                    journey = (journey.groupby(["_pk", "المتجر"], as_index=False)
                                       .agg(_agg_spec)
                                       .drop(columns=["_pk"]))

            # في وضع «إجمالي المتجر» تختفي أعمدة العميل (الاسم/تيليجرام/الإيميل/الجوال)
            # لأنه عرض للمتجر فقط، ولا معنى لمزج عملاء متعددين في صف واحد.
            if sv_agg_mode == "store_total":
                cols_order = ["المتجر", "المصدر", "حالة_الستوري", "مرات_المشاهدة",
                              "دخل_المتجر", "عدد_الزيارات",
                              "نسخ_الكود", "عدد_النسخ", "آخر_مشاهدة"]
            else:
                cols_order = ["المصدر", "العميل", "تيليجرام", "الإيميل", "الجوال",
                              "المتجر", "حالة_الستوري", "مرات_المشاهدة",
                              "دخل_المتجر", "عدد_الزيارات",
                              "نسخ_الكود", "عدد_النسخ",
                              "آخر_مشاهدة"]
            journey = journey[cols_order]

            # ─── بحث باسم المتجر ─────────────────────────────────────────
            _sv_q = st.text_input("🔎 بحث باسم المتجر", "", key="sv_store_search",
                                  placeholder="اكتب اسم المتجر لتصفية الصفوف…").strip()
            if _sv_q:
                journey = journey[journey["المتجر"].astype(str)
                                  .str.contains(_sv_q, case=False, na=False)]

            if journey.empty:
                st.info("📭 لا يوجد متجر مطابق للبحث.")
            else:
                st.dataframe(journey, width="stretch", hide_index=True)
            _sv_cap_mode = {
                "store_total":    "🏪 صف لكل متجر — يجمع كل العملاء + كل القنوات",
                "customer_total": "👤 صف لكل (عميل × متجر) — يدمج الموقع + الميني",
            }.get(sv_agg_mode, "صف لكل (عميل × متجر × قناة)")
            st.caption(f"📋 {len(journey)} صف — {_sv_cap_mode}. الحركات داخل الستوري فقط (story_view_id).")

            # ─── تحميل Excel ─────────────────────────────────────────────
            _sv_xlsx_buf = BytesIO()
            with pd.ExcelWriter(_sv_xlsx_buf, engine="xlsxwriter") as _sv_writer:
                journey.to_excel(_sv_writer, sheet_name="تحليلات الستوري",
                                 index=False)
            _sv_xlsx_buf.seek(0)
            _sv_fname = (f"story_analytics_"
                         f"{sv_date_from.strftime('%Y%m%d')}_"
                         f"{sv_date_to.strftime('%Y%m%d')}.xlsx")
            st.download_button(
                "📥 تحميل Excel",
                data=_sv_xlsx_buf.getvalue(),
                file_name=_sv_fname,
                mime=("application/vnd.openxmlformats-officedocument"
                      ".spreadsheetml.sheet"),
                key="sv_download_xlsx",
            )

    except Exception as e:
        st.error(f"⚠️ تعذّر تحميل تحليلات الستوري: {e}")
    finally:
        if 'conn_st' in locals():
            try: conn_st.close()
            except Exception: pass


# ---  الصفحة الخامسة : مركز قيادة الأقسام والتاقات (إدارة الـ 10 أعمدة) ---
# --- الصفحة الخامسة: مركز قيادة الأقسام والتاقات (نظام رصد نقرات الأقسام) ---
# --- الصفحة الخامسة المحدثة: عرض الأقسام من واقع الماستر ---
# --- الصفحة الخامسة: مركز قيادة الأقسام (الربط الهندسي والتحليل الفعلي) ---
elif page == "جدول الأقسام":
    st.header("📂 جدول الأقسام")
    st.caption("البيانات مسحوبة مباشرة من جدول master. التعديل والحذف هنا يطبّق على كل المتاجر التي تستخدم القسم.")

    conn = None
    try:
        conn = get_conn()
        df_raw = pd.read_sql(
            "SELECT store_id, COALESCE(name_en, '') AS name_en, store_tags, store_tags_en FROM master",
            conn,
        )

        if df_raw.empty:
            st.info("لا توجد متاجر في القاعدة حالياً.")
        else:
            # تفجير التاقات: صف لكل (قسم, متجر) — لغة AR ولغة EN منفصلتَين
            rows_ar, rows_en = [], []
            for _, row in df_raw.iterrows():
                for t in parse_tags(row.get('store_tags')):
                    if t and t.strip():
                        rows_ar.append({'القسم': t.strip(), 'المتجر': row['store_id']})
                for t in parse_tags(row.get('store_tags_en')):
                    if t and t.strip():
                        rows_en.append({'القسم': t.strip(), 'المتجر': row.get('name_en') or row['store_id']})

            def _summarize(rows):
                if not rows:
                    return pd.DataFrame(columns=['اسم القسم', 'عدد المتاجر', 'المتاجر'])
                df = pd.DataFrame(rows)
                grouped = (
                    df.groupby('القسم')['المتجر']
                      .agg(lambda s: ", ".join(sorted(set(s))))
                      .reset_index()
                      .rename(columns={'القسم': 'اسم القسم', 'المتجر': 'المتاجر'})
                )
                counts = df.groupby('القسم')['المتجر'].nunique().reset_index(name='عدد المتاجر')
                merged = grouped.merge(counts, left_on='اسم القسم', right_on='القسم').drop(columns=['القسم'])
                return merged[['اسم القسم', 'عدد المتاجر', 'المتاجر']].sort_values('عدد المتاجر', ascending=False)

            sum_ar = _summarize(rows_ar)
            sum_en = _summarize(rows_en)

            # كروت الإحصائيات
            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                kpi_card("📂", "إجمالي الأقسام (الكل)", len(sum_ar) + len(sum_en), "info")
            with kc2:
                kpi_card("🇸🇦", "أقسام عربية", len(sum_ar), "emerald")
            with kc3:
                kpi_card("🇬🇧", "أقسام إنجليزية", len(sum_en), "neutral")

            st.divider()

            tab_ar, tab_en, tab_manage = st.tabs([
                f"🇸🇦 عربي ({len(sum_ar)})",
                f"🇬🇧 English ({len(sum_en)})",
                "⚙️ إدارة الأقسام",
            ])
            with tab_ar:
                st.dataframe(sum_ar, width='stretch', hide_index=True)
            with tab_en:
                st.dataframe(sum_en, width='stretch', hide_index=True)

            with tab_manage:
                st.caption("⚠️ التعديل والحذف يطبّق على **كل المتاجر** التي تحتوي على القسم. لا يمكن التراجع.")

                # ═══════════════ Helpers ═══════════════
                # ⚠️ ALLOWLIST صارم: col_db يأتي من selectbox لكن نمنع أي
                # f-string interpolation بقيمة غير معتمدة (SQL injection guard).
                _ALLOWED_TAG_COLUMNS = {"store_tags", "store_tags_en"}

                def _do_rename(col_db, old_name, new_name):
                    if col_db not in _ALLOWED_TAG_COLUMNS:
                        st.error(f"عمود غير مسموح: {col_db}")
                        return 0
                    conn2 = get_conn()
                    cur2 = conn2.cursor()
                    cur2.execute(f"""
                        UPDATE master
                        SET {col_db} = '{{' || array_to_string(
                            array_replace(
                                string_to_array(trim(both '{{}}' from COALESCE({col_db}, '')), ','),
                                %s, %s
                            ),
                            ','
                        ) || '}}'
                        WHERE %s = ANY(string_to_array(trim(both '{{}}' from COALESCE({col_db}, '')), ','))
                    """, (old_name, new_name, old_name))
                    affected = cur2.rowcount
                    conn2.commit()
                    conn2.close()
                    return affected

                def _do_delete(col_db, name):
                    if col_db not in _ALLOWED_TAG_COLUMNS:
                        st.error(f"عمود غير مسموح: {col_db}")
                        return 0
                    conn2 = get_conn()
                    cur2 = conn2.cursor()
                    cur2.execute(f"""
                        UPDATE master
                        SET {col_db} = '{{' || array_to_string(
                            array_remove(
                                string_to_array(trim(both '{{}}' from COALESCE({col_db}, '')), ','),
                                %s
                            ),
                            ','
                        ) || '}}'
                        WHERE %s = ANY(string_to_array(trim(both '{{}}' from COALESCE({col_db}, '')), ','))
                    """, (name, name))
                    affected = cur2.rowcount
                    conn2.commit()
                    conn2.close()
                    return affected

                # ═══════════════ ➕ إضافة قسم ═══════════════
                st.markdown("### ➕ إضافة قسم جديد")
                st.caption("القسم الجديد يظهر بقائمة الاختيار في صفحة «إدخال بيانات الماستر» — يثبت في الجدول عند ربطه بأول متجر.")
                add_ar, add_en = st.tabs(["🇸🇦 عربي", "🇬🇧 English"])

                def _add_to_session(lang_key, label_lang, ui_key):
                    ac1, ac2 = st.columns([3, 1])
                    with ac1:
                        new_cat = st.text_input(
                            f"اسم القسم الجديد ({label_lang}):",
                            key=f"add_cat_{ui_key}",
                            placeholder="مثال: ساعات, نظارات, Watches...",
                        )
                    with ac2:
                        st.write(" ")
                        if st.button("➕ إضافة", key=f"add_btn_{ui_key}"):
                            _v = (new_cat or "").strip()
                            if not _v:
                                st.warning("⚠️ اكتب اسم القسم.")
                            else:
                                if lang_key not in st.session_state:
                                    st.session_state[lang_key] = []
                                if _v in st.session_state[lang_key]:
                                    st.info(f"«{_v}» موجود بالفعل في القائمة.")
                                else:
                                    st.session_state[lang_key] = sorted(set(st.session_state[lang_key] + [_v]))
                                    st.success(f"✅ «{_v}» أُضيف للقائمة — افتح «إدخال بيانات الماستر» واربطه بمتجر لحفظه دائماً.")

                with add_ar:
                    _add_to_session('custom_tags_list', 'عربي', 'ar')
                with add_en:
                    _add_to_session('custom_tags_list_en', 'English', 'en')

                st.markdown("---")

                # ═══════════════ ✏️ تعديل قسم ═══════════════
                st.markdown("### ✏️ تعديل اسم قسم")
                edit_ar, edit_en = st.tabs(["🇸🇦 عربي", "🇬🇧 English"])

                def _rename_ui(col_db, existing_list, ui_key):
                    rc1, rc2, rc3 = st.columns([2, 2, 1])
                    with rc1:
                        old_name = st.selectbox(
                            "القسم الحالي:",
                            options=["—"] + existing_list,
                            key=f"rename_old_{ui_key}",
                        )
                    with rc2:
                        new_name = st.text_input(
                            "الاسم الجديد:",
                            key=f"rename_new_{ui_key}",
                            placeholder="اكتب الاسم الجديد...",
                        )
                    with rc3:
                        st.write(" ")
                        if st.button("💾 تحديث", key=f"rename_btn_{ui_key}", type="primary"):
                            _new = (new_name or "").strip()
                            if old_name == "—" or not _new:
                                st.warning("⚠️ اختر القسم القديم واكتب الاسم الجديد.")
                            elif _new == old_name:
                                st.info("الاسم الجديد مطابق للقديم.")
                            else:
                                try:
                                    affected = _do_rename(col_db, old_name, _new)
                                    st.success(f"✅ تم تحديث {affected} متجر — «{old_name}» ← «{_new}»")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"⚠️ فشل التحديث: {e}")

                with edit_ar:
                    _rename_ui('store_tags', sum_ar['اسم القسم'].tolist(), 'ar')
                with edit_en:
                    _rename_ui('store_tags_en', sum_en['اسم القسم'].tolist(), 'en')

                st.markdown("---")

                # ═══════════════ 🗑️ حذف قسم ═══════════════
                st.markdown("### 🗑️ حذف قسم")
                del_ar, del_en = st.tabs(["🇸🇦 عربي", "🇬🇧 English"])

                def _delete_ui(col_db, existing_list, ui_key):
                    dc1, dc2, dc3 = st.columns([2, 2, 1])
                    with dc1:
                        del_name = st.selectbox(
                            "اختر القسم للحذف:",
                            options=["—"] + existing_list,
                            key=f"del_cat_{ui_key}",
                        )
                    with dc2:
                        confirm_del = st.checkbox(
                            "أؤكد الحذف من جميع المتاجر",
                            key=f"del_confirm_{ui_key}",
                        )
                    with dc3:
                        st.write(" ")
                        if st.button("🗑️ حذف", key=f"del_btn_{ui_key}"):
                            if del_name == "—":
                                st.warning("⚠️ اختر قسماً.")
                            elif not confirm_del:
                                st.warning("⚠️ فعّل خانة التأكيد أولاً.")
                            else:
                                try:
                                    affected = _do_delete(col_db, del_name)
                                    st.success(f"✅ تم حذف «{del_name}» من {affected} متجر.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"⚠️ فشل الحذف: {e}")

                with del_ar:
                    _delete_ui('store_tags', sum_ar['اسم القسم'].tolist(), 'ar')
                with del_en:
                    _delete_ui('store_tags_en', sum_en['اسم القسم'].tolist(), 'en')

            st.divider()
            _xl = BytesIO()
            with pd.ExcelWriter(_xl, engine='xlsxwriter') as _w:
                sum_ar.to_excel(_w, index=False, sheet_name='Categories_AR')
                sum_en.to_excel(_w, index=False, sheet_name='Categories_EN')
            st.download_button(
                "📥 تحميل الجدول (Excel)",
                _xl.getvalue(),
                "categories_table.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_categories_table_excel",
            )

    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة البيانات: {e}")
    finally:
        if conn:
            conn.close()

# --- الصفحة السابعة: البحث والتحليل الشامل ---
elif page == "البحث عن كود":
    st.header("🔍 البحث عن كود — تحليل الكلمات المُبحوثة")
    st.caption("الكلمة المبحوثة، عدد مرات البحث، ومن قام بالبحث (مع تفاصيله).")

    import re as _re
    def _detect_lang(text):
        if text and _re.search(r'[؀-ۿ]', str(text)):
            return 'ar'
        if text and _re.search(r'[a-zA-Z]', str(text)):
            return 'en'
        return 'other'

    try:
        conn = get_conn()
        df_search = pd.read_sql("""
            SELECT
                ds.id,
                COALESCE(NULLIF(TRIM(ds.store_id), ''), TRIM(ds.search_keyword)) AS store,
                ds.search_keyword,
                LOWER(COALESCE(NULLIF(TRIM(ds.platform), ''), 'unknown')) AS platform,
                ds.search_date,
                ds.user_id,
                ds.user_email,
                COALESCE(NULLIF('@' || b.username, '@'), NULL) AS bot_username
            FROM direct_search ds
            LEFT JOIN bot_users b ON ds.user_id = b.telegram_id
            WHERE COALESCE(ds.search_keyword, ds.store_id) IS NOT NULL
            ORDER BY ds.search_date DESC
        """, conn)
        conn.close()

        if df_search.empty:
            st.info("📭 لا توجد عمليات بحث مسجّلة بعد.")
        else:
            # تصنيف اللغة من الكلمة المبحوثة
            df_search['lang'] = df_search['search_keyword'].apply(_detect_lang)
            # تطبيع المنصة
            df_search['src'] = df_search['platform'].apply(
                lambda p: 'bot' if 'bot' in str(p).lower() or 'telegram' in str(p).lower()
                else ('web' if 'web' in str(p).lower() else 'other')
            )
            # timestamptz بعد migration_051 → نقرأ utc=True ثم نحوّل للرياض (نمط _ksa_dt)
            df_search['search_date'] = _ksa_dt(df_search['search_date'])

            # ─── فلتر تاريخ (من - إلى) ───────────────────────────────
            _min_d = df_search['search_date'].min().date() if df_search['search_date'].notna().any() else date.today()
            _max_d = df_search['search_date'].max().date() if df_search['search_date'].notna().any() else date.today()
            fdc1, fdc2 = st.columns(2)
            with fdc1:
                f_from = st.date_input("📅 من تاريخ:", value=_min_d, key="search_filter_from")
            with fdc2:
                f_to   = st.date_input("📅 إلى تاريخ:", value=_max_d, key="search_filter_to")

            mask = (
                df_search['search_date'].dt.date >= f_from
            ) & (
                df_search['search_date'].dt.date <= f_to
            )
            df_search = df_search[mask].copy()

            if df_search.empty:
                st.warning("⚠️ لا توجد بحثات ضمن الفترة المختارة. غيّر التواريخ.")
                st.stop()

            def _render_searches(df_subset, key_prefix):
                """يرسم الكروت + تابز البوت/الموقع + تفاصيل لقطعة من البيانات."""
                if df_subset.empty:
                    st.info("📭 لا توجد بحثات في هذا التصنيف.")
                    return

                total = len(df_subset)
                from_bot = int((df_subset['src'] == 'bot').sum())
                from_web = int((df_subset['src'] == 'web').sum())

                kc1, kc2, kc3 = st.columns(3)
                with kc1:
                    kpi_card("🔎", "إجمالي البحثات", total, "info")
                with kc2:
                    kpi_card("🤖", "من البوت", from_bot, "emerald")
                with kc3:
                    kpi_card("🌐", "من الموقع", from_web, "warning")

                st.divider()

                # جدول التجميع: متجر/كلمة | من البوت | من الموقع | الإجمالي
                pivot = (
                    df_subset.pivot_table(index='store', columns='src', aggfunc='size', fill_value=0)
                              .reset_index()
                )
                for s in ('bot', 'web'):
                    if s not in pivot.columns:
                        pivot[s] = 0
                pivot['الإجمالي'] = pivot[['bot', 'web']].sum(axis=1)
                pivot = pivot.rename(columns={
                    'store': 'اسم المتجر / الكلمة',
                    'bot':   'من البوت',
                    'web':   'من الموقع',
                })
                pivot = pivot[['اسم المتجر / الكلمة', 'من البوت', 'من الموقع', 'الإجمالي']]\
                    .sort_values('الإجمالي', ascending=False)

                t_all, t_bot, t_web = st.tabs([
                    f"📋 الإجمالي ({total})",
                    f"🤖 من البوت ({from_bot})",
                    f"🌐 من الموقع ({from_web})",
                ])

                with t_all:
                    st.dataframe(pivot, width='stretch', hide_index=True, height=380)

                with t_bot:
                    if from_bot == 0:
                        st.info("ما فيه بحثات من البوت في هذا التصنيف.")
                    else:
                        df_b = df_subset[df_subset['src'] == 'bot'].copy()
                        df_b['who'] = df_b['bot_username'].fillna(df_b['user_id'].astype(str)).replace('nan', '—')
                        df_b['search_date'] = _ksa_dt(df_b['search_date']).dt.strftime('%Y-%m-%d %H:%M')
                        df_b_view = df_b[['search_keyword', 'store', 'who', 'search_date']].rename(columns={
                            'search_keyword': 'كلمة البحث',
                            'store':          'تطابق مع',
                            'who':            'اسم المستخدم (Telegram)',
                            'search_date':    'وقت البحث',
                        })
                        st.dataframe(df_b_view, width='stretch', hide_index=True, height=380)

                with t_web:
                    if from_web == 0:
                        st.info("ما فيه بحثات من الموقع في هذا التصنيف.")
                    else:
                        df_w = df_subset[df_subset['src'] == 'web'].copy()
                        df_w['who'] = df_w['user_email'].fillna('—')
                        df_w['search_date'] = _ksa_dt(df_w['search_date']).dt.strftime('%Y-%m-%d %H:%M')
                        df_w_view = df_w[['search_keyword', 'store', 'who', 'search_date']].rename(columns={
                            'search_keyword': 'كلمة البحث',
                            'store':          'تطابق مع',
                            'who':            'إيميل الموقع',
                            'search_date':    'وقت البحث',
                        })
                        st.dataframe(df_w_view, width='stretch', hide_index=True, height=380)

                _xl = BytesIO()
                with pd.ExcelWriter(_xl, engine='xlsxwriter') as _w:
                    pivot.to_excel(_w, index=False, sheet_name='Summary')
                    df_subset.drop(columns=['lang']).to_excel(_w, index=False, sheet_name='All_Rows')
                st.download_button(
                    "📥 تحميل (Excel)",
                    _xl.getvalue(),
                    f"search_{key_prefix}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_search_{key_prefix}",
                )

            # تابز اللغة
            df_ar = df_search[df_search['lang'] == 'ar']
            df_en = df_search[df_search['lang'] == 'en']

            lang_ar, lang_en = st.tabs([
                f"🇸🇦 عربي ({len(df_ar)})",
                f"🇬🇧 English ({len(df_en)})",
            ])
            with lang_ar:
                _render_searches(df_ar, "ar")
            with lang_en:
                _render_searches(df_en, "en")

    except Exception as e:
        st.error(f"⚠️ خطأ في تحميل البيانات: {e}")


# --- الصفحة التاسعة: سجل طلبات الأكواد (unavailable_codes_requests) ---
elif page == "طلبات الأكواد":
    page_title("📩", "سجل طلبات الأكواد",
               "متابعة طلبات العملاء للمتاجر غير المتوفرة بالإيميل والـ ID.")
    st.divider()

    try:
        conn = get_conn()
        # طلب العميل نص حر (قد يكتبه بالعربي أو الإنجليزي)؛
        # لو رُبط بسجل master نُظهر اسمَيه AR + EN حتى يقدر الـ admin يتحقّق.
        query_requests = """
            SELECT
                r.id           as "ID",
                CASE
                    WHEN r.user_id IS NOT NULL AND r.user_id > 0 THEN '🤖 بوت'
                    WHEN r.user_email IS NOT NULL AND TRIM(r.user_email) <> '' THEN '🌐 موقع'
                    ELSE 'غير محدد'
                END as "المصدر",
                CASE
                    WHEN r.user_id IS NOT NULL AND r.user_id > 0
                    THEN COALESCE(
                        NULLIF('@' || b.username, '@'),
                        CAST(r.user_id AS TEXT)
                    )
                    ELSE '—'
                END as "اسم مستخدم البوت",
                CASE
                    WHEN r.user_email IS NOT NULL AND TRIM(r.user_email) <> ''
                    THEN r.user_email
                    ELSE '—'
                END as "إيميل الموقع",
                r.brand_name   as "طلب العميل (نص حر)",
                r.requested_at as "تاريخ الطلب",
                COALESCE(CAST(r.master_id AS TEXT), 'قيد الانتظار ⏳') as "رقم الماستر",
                COALESCE(m.store_id, '—')         as "اسم المتجر (AR)",
                COALESCE(NULLIF(m.name_en, ''), '—') as "Store Name (EN)"
            FROM unavailable_codes_requests r
            LEFT JOIN master m     ON r.master_id = m.id
            LEFT JOIN bot_users b  ON r.user_id   = b.telegram_id
            ORDER BY r.requested_at DESC
        """
        req_df = pd.read_sql(query_requests, conn)

        if not req_df.empty:
            req_df["تاريخ الطلب"] = _ksa_dt(req_df["تاريخ الطلب"])
            req_df['is_pending'] = (req_df["رقم الماستر"] == "قيد الانتظار ⏳")

            # --- كروت الإحصائيات (قبل الفلترة — الإجمالي الحقيقي) ---
            total_all = len(req_df)
            pending_all = int(req_df['is_pending'].sum())
            top_b_all = req_df["طلب العميل (نص حر)"].value_counts().idxmax() if total_all else "—"

            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("📦", "إجمالي الطلبات", total_all, "info")
            with c2:
                kpi_card("⏳", "لم توفر بعد", pending_all, "warning")
            with c3:
                kpi_card("🔥", "الأكثر طلباً", top_b_all, "emerald")

            st.divider()

            # ─── فلتر التاريخ (يطبق على كل التابز) ───────────────
            _min_d = req_df["تاريخ الطلب"].min().date() if req_df["تاريخ الطلب"].notna().any() else date.today()
            _max_d = req_df["تاريخ الطلب"].max().date() if req_df["تاريخ الطلب"].notna().any() else date.today()
            fc1, fc2 = st.columns(2)
            with fc1:
                rf_from = st.date_input("📅 من تاريخ:", value=_min_d, key="req_filter_from")
            with fc2:
                rf_to   = st.date_input("📅 إلى تاريخ:", value=_max_d, key="req_filter_to")

            mask_date = (
                req_df["تاريخ الطلب"].dt.date >= rf_from
            ) & (
                req_df["تاريخ الطلب"].dt.date <= rf_to
            )
            req_filtered = req_df[mask_date].copy()
            req_filtered["تاريخ الطلب"] = req_filtered["تاريخ الطلب"].dt.strftime('%Y-%m-%d %H:%M')

            if req_filtered.empty:
                st.warning("⚠️ لا توجد طلبات في الفترة المختارة.")
            else:
                # تقسيم الطلبات حسب الحالة
                df_pending = req_filtered[req_filtered['is_pending']].copy()
                df_fulfilled = req_filtered[~req_filtered['is_pending']].copy()
                cnt_total     = len(req_filtered)
                cnt_pending   = len(df_pending)
                cnt_fulfilled = len(df_fulfilled)

                cols_display = ["ID", "المصدر", "اسم مستخدم البوت", "إيميل الموقع",
                                "طلب العميل (نص حر)", "تاريخ الطلب",
                                "رقم الماستر", "اسم المتجر (AR)", "Store Name (EN)"]

                tab_all, tab_pending, tab_fulfilled, tab_top = st.tabs([
                    f"📋 الكل ({cnt_total})",
                    f"⏳ لم تتوفر ({cnt_pending})",
                    f"✅ توفّرت ({cnt_fulfilled})",
                    f"🔥 الأكثر طلباً",
                ])

                # ═══════ تاب 1: الكل ═══════
                with tab_all:
                    st.dataframe(req_filtered[cols_display], width='stretch', hide_index=True, height=420)
                    xl1 = BytesIO()
                    with pd.ExcelWriter(xl1, engine='xlsxwriter') as w:
                        req_filtered.drop(columns=['is_pending']).to_excel(w, index=False, sheet_name='All')
                    st.download_button(
                        "📥 تحميل الكل (Excel)",
                        xl1.getvalue(),
                        f"requests_all_{date.today()}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_req_all",
                    )

                # ═══════ تاب 2: لم تتوفر — مع زر "أوفرت الكود" ═══════
                with tab_pending:
                    if df_pending.empty:
                        st.success("👌 ما فيه طلبات معلّقة في الفترة المختارة.")
                    else:
                        st.dataframe(df_pending[cols_display], width='stretch', hide_index=True, height=380)

                        st.markdown("##### ✅ أوفرت الكود؟ احذف طلبات معينة")
                        pc1, pc2, pc3 = st.columns([3, 2, 1])
                        with pc1:
                            ids_to_close = st.multiselect(
                                "اختر ID الطلبات اللي وفّرت أكوادها:",
                                options=df_pending["ID"].astype(int).tolist(),
                                key="close_req_ids",
                                help="اختر طلب أو أكثر — يُحذفون دفعة واحدة.",
                            )
                        with pc2:
                            confirm_close = st.checkbox(
                                "✅ أؤكد التوفير والحذف",
                                key="confirm_close_req",
                            )
                        with pc3:
                            st.write(" ")
                            if st.button("🗑️ حذف الطلبات", key="btn_close_req", type="primary"):
                                if not ids_to_close:
                                    st.warning("⚠️ اختر طلب أو أكثر.")
                                elif not confirm_close:
                                    st.warning("⚠️ فعّل خانة التأكيد.")
                                else:
                                    try:
                                        c2 = get_conn()
                                        cur2 = c2.cursor()
                                        cur2.execute(
                                            "DELETE FROM unavailable_codes_requests WHERE id = ANY(%s)",
                                            (list(map(int, ids_to_close)),),
                                        )
                                        deleted = cur2.rowcount
                                        c2.commit()
                                        c2.close()
                                        st.success(f"✅ تم حذف {deleted} طلب — الكود وفّرته 🎉")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"⚠️ فشل الحذف: {e}")

                # ═══════ تاب 3: توفّرت ═══════
                with tab_fulfilled:
                    if df_fulfilled.empty:
                        st.info("📭 ما فيه طلبات متوفّرة بعد في هذه الفترة.")
                    else:
                        st.dataframe(df_fulfilled[cols_display], width='stretch', hide_index=True, height=420)

                # ═══════ تاب 4: الأكثر طلباً ═══════
                with tab_top:
                    st.caption("ترتيب المتاجر المطلوبة حسب عدد الطلبات. اضغط زر «🗑️ حذف كل طلبات هذا المتجر» لما توفّر الكود.")
                    # تجميع حسب اسم المتجر
                    grouped = (
                        req_filtered.groupby("طلب العميل (نص حر)")
                        .agg(
                            عدد_الطلبات=("ID", "count"),
                            معلّقة=('is_pending', 'sum'),
                            ids=("ID", lambda s: list(map(int, s))),
                        )
                        .reset_index()
                        .rename(columns={"طلب العميل (نص حر)": "اسم المتجر المطلوب"})
                        .sort_values('عدد_الطلبات', ascending=False)
                    )

                    # عرض كل صف مع زر حذف
                    for _, row in grouped.iterrows():
                        brand = row['اسم المتجر المطلوب']
                        cnt   = int(row['عدد_الطلبات'])
                        pend  = int(row['معلّقة'])
                        ids   = row['ids']

                        tc1, tc2, tc3, tc4 = st.columns([3, 1, 1, 2])
                        with tc1:
                            st.markdown(f"**🏪 {brand}**")
                        with tc2:
                            st.markdown(f"📥 **{cnt}** طلب")
                        with tc3:
                            badge = f"⏳ {pend} معلّقة" if pend else "✅ كلها مغلقة"
                            st.markdown(badge)
                        with tc4:
                            if st.button(f"🗑️ حذف الكل ({cnt})", key=f"del_brand_{brand}"):
                                try:
                                    c3 = get_conn()
                                    cur3 = c3.cursor()
                                    cur3.execute(
                                        "DELETE FROM unavailable_codes_requests WHERE id = ANY(%s)",
                                        (ids,),
                                    )
                                    deleted = cur3.rowcount
                                    c3.commit()
                                    c3.close()
                                    st.success(f"✅ تم حذف {deleted} طلب لـ «{brand}» — الكود وفّرته 🎉")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"⚠️ فشل الحذف: {e}")
                        st.divider()

            # --- إدارة متقدمة: ربط طلب بـ master + تصفير الكل ---
            with st.expander("⚙️ إدارة متقدمة"):
                ma1, ma2 = st.columns(2)
                with ma1:
                    st.markdown("**🔗 ربط طلب برقم الماستر**")
                    req_id = st.number_input("رقم طلب العميل (ID):", min_value=1, key="link_q9")
                    m_id   = st.number_input("رقم الكود في الماستر:", min_value=1, key="master_q9")
                    if st.button("تحديث وحفظ الربط", key="btn_link_master"):
                        try:
                            c4 = get_conn()
                            cur4 = c4.cursor()
                            cur4.execute(
                                "UPDATE unavailable_codes_requests SET master_id = %s WHERE id = %s",
                                (m_id, req_id),
                            )
                            c4.commit()
                            c4.close()
                            st.success(f"تم ربط الطلب {req_id} بالماستر {m_id}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ فشل الربط: {e}")

                with ma2:
                    st.markdown("**🚨 تصفير كل الجدول**")
                    st.caption("يحذف كل الطلبات نهائياً — لا يمكن التراجع.")
                    confirm_all = st.checkbox("أؤكد التصفير الكامل", key="confirm_truncate_all")
                    if st.button("🚨 تصفير الجدول نهائياً", key="btn_truncate_all"):
                        if not confirm_all:
                            st.warning("⚠️ فعّل خانة التأكيد أولاً.")
                        else:
                            try:
                                c5 = get_conn()
                                cur5 = c5.cursor()
                                cur5.execute("TRUNCATE TABLE unavailable_codes_requests RESTART IDENTITY;")
                                c5.commit()
                                c5.close()
                                st.success("تم تصفير الجدول.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ فشل التصفير: {e}")
        else:
            st.warning("الجدول فارغ حالياً.")

    except Exception as e:
        st.error(f"⚠️ خطأ: {e}")
    finally:
        if 'conn' in locals(): conn.close()


# ════════════════════════════════════════════════════════════════════════════
# 📣 بلاغات الأكواد (Migration 029)
#    - عرض كل البلاغات مع بيانات المُبلّغين
#    - إدارة حالة البلاغ: new → seen → fixed/rejected
#    - عرض المتاجر المسحوبة (auto/manual) + إزالة السحب
#    - سحب يدوي لمتجر معيّن
# ════════════════════════════════════════════════════════════════════════════
elif page == "📣 بلاغات الأكواد":
    page_title("📣", "بلاغات الأكواد",
               "بلاغات «الكود لا يعمل» من العملاء (الموقع/الميني-ويب/البوت)، وإدارة المتاجر المسحوبة.")

    SRC_AR = {"web": "🌐 الموقع", "telegram_miniapp": "🔹 الميني ويب", "bot": "📱 البوت"}
    STATUS_AR = {"new": "🆕 جديد", "seen": "👀 شُوهد", "fixed": "✅ أُصلح", "rejected": "🚫 مرفوض"}

    try:
        conn = get_conn()
        conn.rollback()  # نمط الـ dashboard — يحمي من حالة معاملة معطّلة سابقة

        # ── 1) KPIs ────────────────────────────────────────────────────────
        kpi_df = pd.read_sql("""
            SELECT
              COUNT(*)                                                          AS total,
              SUM(CASE WHEN status='new'  THEN 1 ELSE 0 END)                    AS new_cnt,
              SUM(CASE WHEN created_at >= NOW() - interval '1 hour' THEN 1 ELSE 0 END) AS last_hour,
              SUM(CASE WHEN triggered_auto_suspend THEN 1 ELSE 0 END)           AS triggered_susp
            FROM code_reports
        """, conn)
        susp_df = pd.read_sql(
            "SELECT COUNT(*) AS n FROM master WHERE is_suspended", conn)
        susp_cnt = int(susp_df["n"].iloc[0])

        k1, k2, k3, k4 = st.columns(4)
        with k1: kpi_card("📦", "إجمالي البلاغات",   int(kpi_df["total"].iloc[0] or 0),       "info")
        with k2: kpi_card("🆕", "جديدة",              int(kpi_df["new_cnt"].iloc[0] or 0),     "warning")
        with k3: kpi_card("⏱", "آخر ساعة",           int(kpi_df["last_hour"].iloc[0] or 0),   "danger")
        with k4: kpi_card("🚫", "متاجر مسحوبة الآن", susp_cnt,                                "danger" if susp_cnt else "info")

        st.divider()

        # ── 2) قائمة المتاجر المسحوبة (يدوي / تلقائي) ─────────────────────
        with st.expander(f"🚫 المتاجر المسحوبة حالياً ({susp_cnt})", expanded=susp_cnt > 0):
            if susp_cnt == 0:
                st.success("لا توجد متاجر مسحوبة. كل المتاجر تظهر للعملاء طبيعياً.")
            else:
                susp = pd.read_sql("""
                    SELECT store_id, public_coupon,
                           suspended_at, suspended_reason,
                           (SELECT COUNT(*) FROM code_reports cr
                              WHERE cr.store_id = m.store_id
                                AND cr.created_at >= NOW() - interval '24 hours') AS reports_24h
                    FROM master m
                    WHERE is_suspended
                    ORDER BY suspended_at DESC NULLS LAST
                """, conn)
                susp["suspended_at"] = pd.to_datetime(susp["suspended_at"], errors="coerce") \
                                            .dt.strftime('%Y-%m-%d %H:%M')
                susp.rename(columns={
                    "store_id":          "المتجر",
                    "public_coupon":     "الكود الحالي",
                    "suspended_at":      "تاريخ السحب",
                    "suspended_reason":  "سبب السحب",
                    "reports_24h":       "بلاغات آخر 24 سا",
                }, inplace=True)
                st.dataframe(susp, width="stretch", hide_index=True)

                # إزالة سحب بمتجر محدّد
                pick = st.selectbox("اختر متجراً لإزالة السحب:", options=susp["المتجر"].tolist(), key="unsusp_pick")
                if st.button("✅ إزالة السحب وإعادة العرض للعملاء", type="primary", key="unsusp_btn"):
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE master
                                SET is_suspended = FALSE,
                                    suspended_at = NULL,
                                    suspended_reason = NULL
                                WHERE store_id = %s
                            """, (pick,))
                            # علّم أي بلاغات «جديدة» على هذا المتجر كـ fixed
                            cur.execute("""
                                UPDATE code_reports
                                SET status = 'fixed', resolved_at = NOW(),
                                    resolved_note = 'إزالة السحب + اعتماد الكود الجديد'
                                WHERE store_id = %s AND status IN ('new','seen')
                            """, (pick,))
                        conn.commit()
                        st.success(f"تم إزالة السحب عن «{pick}» ✓")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"⚠️ فشل: {e}")

        st.divider()

        # ── 3) سحب يدوي لمتجر ───────────────────────────────────────────────
        with st.expander("🛠️ سحب يدوي لمتجر (بدون انتظار 10 بلاغات)", expanded=False):
            active = pd.read_sql("""
                SELECT store_id FROM master
                WHERE NOT COALESCE(is_suspended, FALSE)
                  AND (last_time IS NULL OR last_time >= CURRENT_DATE)
                ORDER BY store_id
            """, conn)
            if active.empty:
                st.info("لا توجد متاجر نشطة قابلة للسحب.")
            else:
                m_pick   = st.selectbox("اختر المتجر:", options=active["store_id"].tolist(), key="m_susp_pick")
                m_reason = st.text_input("سبب السحب (اختياري):", "مراجعة يدوية للكود",   key="m_susp_reason")
                if st.button("🚫 اسحب الآن", type="primary", key="m_susp_btn"):
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE master
                                SET is_suspended = TRUE,
                                    suspended_at = NOW(),
                                    suspended_reason = %s
                                WHERE store_id = %s
                            """, (f"manual: {m_reason}", m_pick))
                        conn.commit()
                        st.success(f"تم سحب «{m_pick}» ✓")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"⚠️ فشل: {e}")

        st.divider()

        # ── 4) جدول البلاغات الكامل + فلترة بحالة ─────────────────────────
        st.subheader("📋 سجلّ البلاغات")
        flt_col1, flt_col2 = st.columns([1, 2])
        with flt_col1:
            status_pick = st.selectbox(
                "الحالة:",
                ["كل الحالات", "🆕 جديد", "👀 شُوهد", "✅ أُصلح", "🚫 مرفوض"],
                key="rprt_status_filter",
            )

        status_filter_sql = ""
        if status_pick == "🆕 جديد":     status_filter_sql = "WHERE cr.status='new'"
        elif status_pick == "👀 شُوهد":  status_filter_sql = "WHERE cr.status='seen'"
        elif status_pick == "✅ أُصلح":  status_filter_sql = "WHERE cr.status='fixed'"
        elif status_pick == "🚫 مرفوض": status_filter_sql = "WHERE cr.status='rejected'"

        reports = pd.read_sql(f"""
            SELECT
              cr.id, cr.store_id, cr.source, cr.status,
              cr.reporter_name, cr.reporter_email, cr.reporter_phone,
              cr.reporter_telegram_username,
              cr.reported_code, cr.issue_note,
              cr.triggered_auto_suspend, cr.created_at,
              m.is_suspended AS store_suspended_now
            FROM code_reports cr
            LEFT JOIN master m ON m.store_id = cr.store_id
            {status_filter_sql}
            ORDER BY cr.created_at DESC
            LIMIT 500
        """, conn)

        if reports.empty:
            st.info("📭 لا بلاغات في هذا الفلتر.")
        else:
            disp = reports.copy()
            disp["source"]     = disp["source"].map(SRC_AR).fillna(disp["source"])
            disp["status"]     = disp["status"].map(STATUS_AR).fillna(disp["status"])
            disp["created_at"] = _ksa_dt(disp["created_at"]) \
                                       .dt.strftime('%Y-%m-%d %H:%M')
            disp["تيليجرام"] = disp["reporter_telegram_username"].apply(
                lambda v: f"@{v}" if v else "—")
            disp["الكود لحظة البلاغ"] = disp["reported_code"].fillna("—")
            disp["سحب تلقائي؟"]       = disp["triggered_auto_suspend"].map({True: "✅", False: ""})
            disp["متجر مسحوب الآن؟"] = disp["store_suspended_now"].map({True: "🚫", False: ""})
            disp.rename(columns={
                "id":              "ID",
                "store_id":        "المتجر",
                "source":          "المصدر",
                "status":          "الحالة",
                "reporter_name":   "اسم المُبلِّغ",
                "reporter_email":  "إيميل",
                "reporter_phone":  "جوال",
                "issue_note":      "ملاحظة العميل",
                "created_at":      "وقت البلاغ",
            }, inplace=True)
            shown_cols = ["ID","المتجر","المصدر","الحالة","سحب تلقائي؟","متجر مسحوب الآن؟",
                          "اسم المُبلِّغ","إيميل","جوال","تيليجرام",
                          "الكود لحظة البلاغ","ملاحظة العميل","وقت البلاغ"]
            st.dataframe(disp[shown_cols], width="stretch", hide_index=True)

            # تحديث حالة بلاغ
            st.markdown("##### ✏️ تغيير حالة بلاغ")
            uc1, uc2, uc3 = st.columns([1, 1.4, 1])
            with uc1:
                rpt_id = st.number_input("ID البلاغ:", min_value=1, step=1, key="rpt_upd_id")
            with uc2:
                new_status = st.selectbox(
                    "الحالة الجديدة:",
                    ["new", "seen", "fixed", "rejected"],
                    format_func=lambda x: STATUS_AR.get(x, x), key="rpt_upd_status",
                )
            with uc3:
                if st.button("💾 تحديث", key="rpt_upd_btn", width="stretch"):
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE code_reports
                                SET status = %s,
                                    resolved_at = CASE WHEN %s IN ('fixed','rejected')
                                                       THEN NOW() ELSE NULL END
                                WHERE id = %s
                            """, (new_status, new_status, int(rpt_id)))
                        conn.commit()
                        st.success("تم التحديث ✓")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"⚠️ {e}")

            # تصدير CSV
            st.download_button(
                "📥 تنزيل CSV",
                disp[shown_cols].to_csv(index=False).encode("utf-8-sig"),
                file_name="code_reports.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"⚠️ تعذّر تحميل البيانات: {e}")
    finally:
        if 'conn' in locals():
            try: conn.close()
            except Exception: pass


# --- الصفحة العاشرة: تحليل طلبات الأكواد ---
#   هدف الصفحة: مين طلب وش، كم مرة انطلب لكل متجر، ومعلومات تواصل كاملة
#   لإشعار الطالبين لما توفّر الكود.
elif page == "تحليل طلبات الأكواد":
    page_title("📊", "تحليل طلبات الأكواد",
               "كل من طلب كود — بياناته الكاملة ووقته. اعرف وش تنزل، وراسل الطالبين لما توفّره.")
    st.divider()

    if st.button("🔄 تحديث", key="cr_refresh", help="إعادة تحميل البيانات"):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

    try:
        conn = get_conn()
        conn.rollback()

        # ─── جلب الطلبات + ربط هوية الطالبين (web_users / bot_users) ─────────
        # brand_norm = TRIM(LOWER(brand_name)) لتجميع التهجئات المختلفة كأنها متجر واحد.
        df_req = pd.read_sql("""
            SELECT
              r.id,
              r.brand_name                                                  AS raw_brand,
              TRIM(LOWER(r.brand_name))                                     AS brand_norm,
              r.requested_at,
              r.master_id,
              CASE
                WHEN r.user_id IS NOT NULL AND r.user_id > 0          THEN 'bot'
                WHEN r.user_email IS NOT NULL AND TRIM(r.user_email)<>'' THEN 'web'
                ELSE 'unknown'
              END                                                           AS source,
              r.user_id                                                     AS tg_id,
              r.user_email                                                  AS web_email,
              COALESCE(wu.display_name, '')                                 AS web_name,
              COALESCE(wu.phone_number, '')                                 AS web_phone,
              COALESCE(bu.username, '')                                     AS tg_username,
              COALESCE(m.store_id, '')                                      AS matched_store_ar,
              COALESCE(NULLIF(m.name_en, ''), '')                           AS matched_store_en
            FROM unavailable_codes_requests r
            LEFT JOIN web_users  wu ON r.user_email = wu.email
            LEFT JOIN bot_users  bu ON r.user_id    = bu.telegram_id
            LEFT JOIN master     m  ON r.master_id  = m.id
            ORDER BY r.requested_at DESC
        """, conn)

        if df_req.empty:
            st.info("📭 ما فيه طلبات مسجّلة حتى الآن.")
            st.stop()

        df_req["requested_at"] = _ksa_dt(df_req["requested_at"])
        df_req["is_pending"]   = df_req["master_id"].isna()

        # ─── فلتر التاريخ + المصدر ──────────────────────────────────────────
        _min_d = df_req["requested_at"].min().date() if df_req["requested_at"].notna().any() else date.today()
        _max_d = df_req["requested_at"].max().date() if df_req["requested_at"].notna().any() else date.today()
        fc1, fc2, fc3 = st.columns([2, 2, 3])
        with fc1:
            d_from = st.date_input("📅 من تاريخ:", value=_min_d, key="req_an_from")
        with fc2:
            d_to   = st.date_input("📅 إلى تاريخ:", value=_max_d, key="req_an_to")
        with fc3:
            src_choice = st.radio("المصدر:", ["الكل", "🤖 البوت", "🌐 الموقع"],
                                  horizontal=True, key="req_an_src")

        m_date = (df_req["requested_at"].dt.date >= d_from) & (df_req["requested_at"].dt.date <= d_to)
        m_src  = (
            (df_req["source"] == "bot") if src_choice == "🤖 البوت"
            else (df_req["source"] == "web") if src_choice == "🌐 الموقع"
            else pd.Series(True, index=df_req.index)
        )
        df = df_req[m_date & m_src].copy()

        if df.empty:
            st.warning("⚠️ لا توجد طلبات في النطاق المختار.")
            st.stop()

        # ─── KPIs ───────────────────────────────────────────────────────────
        total_req       = len(df)
        unique_brands   = df["brand_norm"].nunique()
        pending_count   = int(df["is_pending"].sum())
        fulfilled_count = total_req - pending_count
        # طالبون فريدون = نشخّصهم بهوية: tg_id أو web_email
        df["person_key"] = df.apply(
            lambda r: f"tg:{int(r['tg_id'])}" if pd.notna(r["tg_id"]) and r["tg_id"] > 0
                      else (f"web:{r['web_email']}" if r["web_email"] else None),
            axis=1,
        )
        unique_people = df["person_key"].dropna().nunique()

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1: kpi_card("📥", "إجمالي الطلبات", total_req,       "info")
        with k2: kpi_card("🏪", "متاجر فريدة",    unique_brands,   "info")
        with k3: kpi_card("👥", "طالبون فريدون",  unique_people,   "emerald")
        with k4: kpi_card("⏳", "معلّقة",          pending_count,   "warning")
        with k5: kpi_card("✅", "موفّرة",          fulfilled_count, "emerald")

        st.divider()

        # ─── التبويبات ──────────────────────────────────────────────────────
        tab_store, tab_people, tab_drill = st.tabs([
            f"🏪 كل متجر وكم مرة انطلب ({unique_brands})",
            f"👥 كل الطالبين — بياناتهم الكاملة ({total_req})",
            "🔍 درل-داون متجر معيّن",
        ])

        # ═══════ 1. كل متجر وكم مرة انطلب ═══════
        with tab_store:
            st.caption("التجميع بعد تطبيع اسم المتجر (إزالة المسافات + الحروف الصغيرة) لجمع التهجئات المختلفة.")
            per_brand = (
                df.groupby("brand_norm")
                  .agg(
                      اسم_المتجر = ("raw_brand", lambda s: s.value_counts().idxmax()),
                      إجمالي_الطلبات = ("id", "count"),
                      طالبون_فريدون = ("person_key", lambda s: s.dropna().nunique()),
                      معلّقة = ("is_pending", "sum"),
                      موفّرة = ("is_pending", lambda s: (~s).sum()),
                      أول_طلب = ("requested_at", "min"),
                      آخر_طلب = ("requested_at", "max"),
                  )
                  .reset_index(drop=True)
                  .sort_values(["إجمالي_الطلبات", "طالبون_فريدون"], ascending=[False, False])
                  .reset_index(drop=True)
            )
            per_brand["معلّقة"] = per_brand["معلّقة"].astype(int)
            per_brand["موفّرة"] = per_brand["موفّرة"].astype(int)
            per_brand["أول_طلب"] = pd.to_datetime(per_brand["أول_طلب"]).dt.strftime("%Y-%m-%d %H:%M")
            per_brand["آخر_طلب"] = pd.to_datetime(per_brand["آخر_طلب"]).dt.strftime("%Y-%m-%d %H:%M")
            per_brand.insert(0, "#", per_brand.index + 1)

            st.dataframe(per_brand, width="stretch", hide_index=True, height=460)

            xl1 = BytesIO()
            with pd.ExcelWriter(xl1, engine="xlsxwriter") as w:
                per_brand.to_excel(w, index=False, sheet_name="Per_Brand")
            st.download_button(
                "📥 تحميل ملخص المتاجر (Excel)",
                xl1.getvalue(),
                f"requests_per_brand_{date.today()}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_req_per_brand",
            )

        # ═══════ 2. كل الطالبين — بياناتهم الكاملة ═══════
        with tab_people:
            st.caption("صف لكل طلب — مع بيانات تواصل كاملة لإشعار الطالب لما توفّر الكود.")
            view = df.copy()
            view["المصدر"] = view["source"].map(
                {"bot": "🤖 البوت", "web": "🌐 الموقع"}).fillna("غير محدد")
            view["الاسم"] = view.apply(
                lambda r: r["web_name"] if r["web_name"]
                          else (f"@{r['tg_username']}" if r["tg_username"] else "—"),
                axis=1,
            )
            view["الإيميل"]    = view["web_email"].fillna("").replace("", "—")
            view["الجوال"]     = view["web_phone"].fillna("").replace("", "—")
            view["تيليجرام"]   = view.apply(
                lambda r: f"@{r['tg_username']}" if r["tg_username"]
                          else (str(int(r["tg_id"])) if pd.notna(r["tg_id"]) and r["tg_id"] > 0 else "—"),
                axis=1,
            )
            view["تاريخ الطلب"] = view["requested_at"].dt.strftime("%Y-%m-%d %H:%M")
            view["الحالة"]      = view["is_pending"].map({True: "⏳ معلّقة", False: "✅ موفّرة"})
            view["المتجر المطلوب"] = view["raw_brand"]
            view["تطابق ماستر"] = view.apply(
                lambda r: r["matched_store_ar"] if r["matched_store_ar"] else "—",
                axis=1,
            )

            cols_people = ["id", "المصدر", "المتجر المطلوب", "الاسم",
                           "الإيميل", "الجوال", "تيليجرام",
                           "تاريخ الطلب", "الحالة", "تطابق ماستر"]
            people_view = view[cols_people].rename(columns={"id": "ID"})
            st.dataframe(people_view, width="stretch", hide_index=True, height=460)

            xl2 = BytesIO()
            with pd.ExcelWriter(xl2, engine="xlsxwriter") as w:
                people_view.to_excel(w, index=False, sheet_name="Requesters")
            st.download_button(
                "📥 تحميل قائمة الطالبين (Excel)",
                xl2.getvalue(),
                f"requesters_{date.today()}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_req_people",
            )

        # ═══════ 3. درل-داون متجر معيّن ═══════
        with tab_drill:
            st.caption("اختر متجر — يعرض لك كل من طلبه بمعلومات تواصل كاملة، جاهز للنسخ والمراسلة.")
            brand_opts = (df.groupby("brand_norm")["raw_brand"]
                            .agg(lambda s: s.value_counts().idxmax()).tolist())
            pick = st.selectbox("اختر المتجر المطلوب:", brand_opts, key="req_drill_pick")
            if pick:
                pick_norm = pick.strip().lower()
                d = df[df["brand_norm"] == pick_norm].copy()
                st.markdown(f"### 🏪 «{pick}» — {len(d)} طلب من {d['person_key'].dropna().nunique()} شخص فريد")

                drill = d.copy()
                drill["المصدر"] = drill["source"].map({"bot": "🤖 البوت", "web": "🌐 الموقع"}).fillna("—")
                drill["الاسم"] = drill.apply(
                    lambda r: r["web_name"] if r["web_name"]
                              else (f"@{r['tg_username']}" if r["tg_username"] else "—"),
                    axis=1,
                )
                drill["الإيميل"]   = drill["web_email"].fillna("").replace("", "—")
                drill["الجوال"]    = drill["web_phone"].fillna("").replace("", "—")
                drill["تيليجرام"]  = drill.apply(
                    lambda r: f"@{r['tg_username']}" if r["tg_username"]
                              else (str(int(r["tg_id"])) if pd.notna(r["tg_id"]) and r["tg_id"] > 0 else "—"),
                    axis=1,
                )
                drill["تاريخ الطلب"] = drill["requested_at"].dt.strftime("%Y-%m-%d %H:%M")
                drill["الحالة"]      = drill["is_pending"].map({True: "⏳ معلّقة", False: "✅ موفّرة"})
                cols_drill = ["id", "المصدر", "الاسم", "الإيميل", "الجوال",
                              "تيليجرام", "تاريخ الطلب", "الحالة"]
                drill_view = drill[cols_drill].rename(columns={"id": "ID"})
                st.dataframe(drill_view, width="stretch", hide_index=True, height=420)

                xl3 = BytesIO()
                with pd.ExcelWriter(xl3, engine="xlsxwriter") as w:
                    drill_view.to_excel(w, index=False, sheet_name="Requesters_of_Brand")
                st.download_button(
                    f"📥 تحميل طالبي «{pick}» (Excel)",
                    xl3.getvalue(),
                    f"requesters_of_{pick}_{date.today()}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_req_drill",
                )

    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة التحليلات: {e}")
    finally:
        if 'conn' in locals():
            try: conn.close()
            except Exception: pass




# --- الصفحة الحادية عشرة: بيانات المستخدمين ---
elif page == "بيانات المستخدمين":
    page_title("👥", "سجل بيانات المستخدمين")
    st.divider()

    if st.button("🔄 تحديث", key="bu_refresh", help="إعادة تحميل البيانات"):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

    # خريطة التعريب (ترتيب العرض)
    _COL_AR = {
        'telegram_id':            'المعرف (ID)',
        'username':               'الاسم',
        'lang':                   'اللغة',
        'joined_at':              'تاريخ الانضمام',
        'last_seen':              'آخر ظهور',
        'country':                'الدولة',
        'city':                   'المدينة',
        'device_type':            'نوع الجهاز',
        'user_status':            'الحالة',
        'loyalty_rank':           'رتبة الولاء',
        'marketing_segment':      'الشريحة التسويقية',
        'fav_store_inferred':     'المتجر المفضل (AR)',
        'fav_store_en':           'Favorite Store (EN)',
        'store_copy_count':       'عدد النسخ',
        'fav_tag_inferred':       'القسم المفضل',
        'tag_visit_count':        'زيارات الأقسام',
        'visited_clicks':         'النقرات',
        'interests':              'الاهتمامات',
        'search_date_timestamp':  'ساعة النشاط',
        'manual_favorites':       'المفضلة',
        'copied_coupons_history': 'سجل الكوبونات',
    }

    try:
        conn = get_conn()
        conn.rollback()
        table_exists = pd.read_sql(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bot_users');", conn
        ).iloc[0, 0]

        if table_exists:
            users_df = pd.read_sql("""
                SELECT
                    u.telegram_id, u.username, u.lang, u.joined_at, u.last_seen,
                    u.country, u.city, u.device_type,
                    u.user_status, u.loyalty_rank, u.marketing_segment,
                    u.fav_store_inferred,
                    COALESCE(NULLIF(m.name_en, ''), '') AS fav_store_en,
                    u.store_copy_count,
                    u.fav_tag_inferred, u.tag_visit_count, u.visited_clicks,
                    u.interests,
                    u.search_date_timestamp,
                    u.manual_favorites, u.copied_coupons_history
                FROM bot_users u
                LEFT JOIN master m ON u.fav_store_inferred = m.store_id
                ORDER BY u.last_seen DESC NULLS LAST
            """, conn)

            if not users_df.empty:
                # تنسيق التواريخ بشكل مقروء
                for _dc in ['joined_at', 'last_seen', 'search_date_timestamp']:
                    if _dc in users_df.columns:
                        users_df[_dc] = _ksa_dt(users_df[_dc]).dt.strftime('%Y-%m-%d')

                # ── KPIs ──
                st.write("### 🔑 ملخص القاعدة")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("إجمالي المشتركين", f"{len(users_df):,}")
                c2.metric("إجمالي النقرات", f"{int(users_df['visited_clicks'].sum()):,}")
                c3.metric("إجمالي عمليات النسخ", f"{int(users_df['store_copy_count'].sum()):,}")
                today_str = pd.Timestamp.now().strftime('%Y-%m-%d')
                c4.metric("نشطون اليوم", len(users_df[users_df['last_seen'] == today_str]))

                st.divider()

                # ── Deep Dive ──
                st.write("### 🎯 تحليل مستخدم محدد")
                user_list = [f"{row['username']} ({row['telegram_id']})" for _, row in users_df.iterrows()]
                selected_option = st.selectbox("اختر مستخدم:", ["-- اختر مستخدم --"] + user_list)

                if selected_option != "-- اختر مستخدم --":
                    selected_id = int(selected_option.split('(')[-1].replace(')', ''))
                    u = users_df[users_df['telegram_id'] == selected_id].iloc[0]

                    with st.container():
                        st.markdown(f"#### 👤 ملف المستخدم: {u['username']}")
                        i1, i2, i3, i4 = st.columns(4)
                        i1.info(f"📍 **الموقع:**\n{u.get('city') or '—'}, {u.get('country') or '—'}")
                        i2.info(f"📱 **الجهاز:**\n{u.get('device_type') or '—'}")
                        i3.info(f"📅 **آخر ظهور:**\n{u['last_seen'] or '—'}")
                        i4.info(f"🏆 **الحالة:**\n{u.get('user_status') or '—'}")

                        st.write("---")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write("**🧠 الميول الشرائية:**")
                            st.write(f"- القسم المفضل: `{u.get('fav_tag_inferred') or '—'}`")
                            _fav_ar = u.get('fav_store_inferred') or '—'
                            _fav_en = u.get('fav_store_en') or '—'
                            st.write(f"- المتجر المفضل (AR / EN): `{_fav_ar}` / `{_fav_en}`")
                            st.write(f"- رتبة الولاء: `{u.get('loyalty_rank') or '—'}`")
                            st.write(f"- الشريحة التسويقية: `{u.get('marketing_segment') or '—'}`")
                            st.write(f"- تاريخ الانضمام: `{u.get('joined_at') or '—'}`")
                        with col_b:
                            st.write("**📜 سجل الكوبونات المنسوخة:**")
                            hist = u.get('copied_coupons_history')
                            st.write(hist if hist else "لا يوجد تاريخ نسخ حتى الآن.")

                st.divider()

                # ── الجدول الكامل بأسماء عربية ──
                st.write("### 📋 السجل الكامل")
                display_df = users_df.rename(columns=_COL_AR)
                st.dataframe(display_df, width='stretch', hide_index=True, height=500)

                # ── تحميل Excel ──
                _xlu = BytesIO()
                with pd.ExcelWriter(_xlu, engine='xlsxwriter') as _wu:
                    display_df.to_excel(_wu, index=False, sheet_name='بيانات_المستخدمين')
                st.download_button(
                    "📥 تحميل بيانات المستخدمين (Excel)",
                    _xlu.getvalue(),
                    "users_data.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("الجدول موجود لكن لا توجد بيانات. (تأكد من ربط كود البوت بعملية الحفظ)")
        else:
            st.error("❌ خطأ: جدول 'bot_users' غير موجود.")

    except Exception as e:
        st.error(f"⚠️ خطأ تقني: {e}")
    finally:
        if 'conn' in locals(): conn.close()


# --- صفحة مستخدمي الموقع (web_users) ---
elif page == "مستخدمو الموقع":
    page_title("🌐", "مستخدمو موقع dealpulseksa.com")
    st.caption("جميع المستخدمين المسجّلين عبر الموقع (تسجيل اسم/جوال/إيميل/كلمة سر).")
    st.divider()

    if st.button("🔄 تحديث", key="wu_refresh", help="إعادة تحميل البيانات"):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

    try:
        conn = get_conn()
        conn.rollback()

        # KPIs
        kpi_df = pd.read_sql(
            """
            SELECT
                COUNT(*)                                              AS total_users,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')  AS new_7d,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS new_30d,
                COUNT(*) FILTER (WHERE last_seen >= NOW() - INTERVAL '7 days')   AS active_7d
            FROM web_users
            WHERE password_hash IS NOT NULL
            """,
            conn,
        )
        if not kpi_df.empty:
            r = kpi_df.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("👥", "إجمالي المسجّلين", f"{int(r['total_users']):,}", accent="emerald")
            with c2: kpi_card("🆕", "جدد آخر 7 أيام",   f"{int(r['new_7d']):,}",     accent="info")
            with c3: kpi_card("📅", "جدد آخر 30 يوم",   f"{int(r['new_30d']):,}",    accent="info")
            with c4: kpi_card("🔥", "نشطون آخر 7 أيام", f"{int(r['active_7d']):,}",  accent="warning")

        st.write("### 📋 جدول المستخدمين")

        # فلتر بحث
        search = st.text_input("🔎 بحث (اسم / جوال / إيميل / مدينة)", "")

        users_df = pd.read_sql(
            """
            SELECT
                id, display_name, phone_number, email, city, country, lang,
                visited_clicks, store_copy_count,
                created_at, last_seen, status,
                last_ip, device_type
            FROM web_users
            WHERE password_hash IS NOT NULL
            ORDER BY created_at DESC NULLS LAST
            """,
            conn,
        )

        if users_df.empty:
            st.info("ℹ️ لا يوجد مستخدمون مسجّلون عبر الموقع بعد.")
        else:
            # تطبيق الفلتر
            if search.strip():
                q = search.strip().lower()
                mask = (
                    users_df['display_name'].fillna('').str.lower().str.contains(q, na=False) |
                    users_df['phone_number'].fillna('').str.lower().str.contains(q, na=False) |
                    users_df['email'].fillna('').str.lower().str.contains(q, na=False) |
                    users_df['city'].fillna('').str.lower().str.contains(q, na=False)
                )
                users_df = users_df[mask]

            # تنسيق التواريخ
            for _dc in ['created_at', 'last_seen']:
                if _dc in users_df.columns:
                    users_df[_dc] = _ksa_dt(users_df[_dc]).dt.strftime('%Y-%m-%d %H:%M')

            # ترجمة الأعمدة
            users_df = users_df.rename(columns={
                'id':                'المعرف',
                'display_name':      'الاسم',
                'phone_number':      'الجوال',
                'email':             'الإيميل',
                'city':              'المدينة',
                'country':           'الدولة',
                'lang':              'اللغة',
                'visited_clicks':    'عدد النقرات',
                'store_copy_count':  'عدد النسخ',
                'created_at':        'تاريخ التسجيل',
                'last_seen':         'آخر دخول',
                'status':            'الحالة',
                'last_ip':           'آخر IP',
                'device_type':       'نوع الجهاز',
            })

            st.caption(f"عدد النتائج: {len(users_df):,}")
            st.dataframe(users_df, width='stretch', hide_index=True)

            # تصدير
            csv = users_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "⬇️ تصدير CSV",
                csv,
                file_name="web_users.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"⚠️ خطأ تقني: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# --- الصفحة الثانية عشرة: تحليل المستخدمين (Users Analytics) ---
elif page == "تحليل المستخدمين":
    # ════════════════════════════════════════════════════════════════════
    # إعادة البناء من الصفر — قائمتان رئيسيتان فقط:
    #   1) التحليل العام  — أرقام ومؤشرات على مستوى القاعدة كلها.
    #   2) التحليل الفردي — كل شي عن مستخدم واحد بعينه.
    # نبني محتوى كل قائمة خطوة خطوة.
    # ════════════════════════════════════════════════════════════════════
    page_title("📊", "تحليل المستخدمين")

    tab_general, tab_individual, tab_ai = st.tabs(
        ["🌍 التحليل العام", "👤 التحليل الفردي", "🤖 الذكاء الاصطناعي"]
    )

    # ── القائمة الأولى: التحليل العام ───────────────────────────────────
    with tab_general:
        # شريط التحكم العلوي: فلتر المصدر (pills) + زر تحديث
        _g_c1, _g_c2 = st.columns([4, 1])
        with _g_c1:
            gen_src_label = st.segmented_control(
                "📡 المصدر",
                ["الكل", "🤖 البوت", "🔹 الميني-ويب", "🌐 الموقع"],
                default="الكل",
                key="gen_src",
            )
        with _g_c2:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("🔄 تحديث", key="gen_refresh",
                         help="مسح الكاش وإعادة تحميل البيانات"):
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()

        # خريطة المصدر للاستعلامات (None = كل المصادر)
        _GEN_SRC_MAP = {
            "🤖 البوت":      ("bot",),
            "🌐 الموقع":     ("web",),
            "🔹 الميني-ويب": ("telegram_miniapp", "miniapp"),
        }
        gen_src = _GEN_SRC_MAP.get(gen_src_label)  # None عند "الكل"

        st.divider()

        # ── نطاق التاريخ (يحدّ كل الفلاتر تحت) ────────────────────────────
        _gd1, _gd2 = st.columns(2)
        _gen_today = date.today()
        with _gd1:
            gen_date_from = st.date_input(
                "📅 من تاريخ", value=_gen_today - timedelta(days=30),
                max_value=_gen_today, key="gen_date_from",
            )
        with _gd2:
            gen_date_to = st.date_input(
                "📅 إلى تاريخ", value=_gen_today,
                min_value=gen_date_from, max_value=_gen_today, key="gen_date_to",
            )

        st.divider()

        # ── المسميات ──────────────────────────────────────────────────────
        # المصدر/الحالة/الاكتمال إجبارية بـ«الكل». الباقي اختياري بـ«لا شيء»
        # (لا يجبرك على الاختيار؛ لا شيء = هذا الفلتر غير مطبَّق).
        _STATUS_AR    = {"all": "الكل", "active": "🟢 نشط", "idle": "😴 خامل"}
        _COMPLETE_AR  = {"all": "الكل", "complete": "✅ مكتمل", "partial": "⛔ ناقص"}
        _LANG_AR      = {"none": "لا شيء", "all": "الكل",
                         "ar": "🇸🇦 عربي", "en": "🇬🇧 إنجليزي"}
        _GENDER_AR    = {"none": "لا شيء", "all": "الكل",
                         "male": "♂️ ذكر", "female": "♀️ أنثى"}
        _AGE_AR       = {"none": "لا شيء", "all": "الكل", "u18": "أقل من 18",
                         "18-24": "18–24", "25-34": "25–34", "35-44": "35–44",
                         "45-54": "45–54", "55p": "55+"}
        _STORESTAT_AR = {"none": "لا شيء", "all": "الكل", "active": "🟢 فعّالة",
                         "expired": "🗄️ منتهية", "expiring": "⏳ قربت تنتهي"}
        _FAVSTORE_AR  = {"none": "لا شيء", "all": "الكل",
                         "has": "❤️ عنده", "not": "🤍 بلا"}
        _FAVCAT_AR    = {"none": "لا شيء", "all": "الكل",
                         "has": "🏷️ عنده", "not": "🤍 بلا"}
        _TREND_AR     = {"none": "لا شيء", "all": "الكل",
                         "daily": "🔥 يومي", "weekly": "🔥 أسبوعي"}
        _STORY_AR     = {"none": "لا شيء", "all": "الكل",
                         "normal": "🎬 عادي", "trend": "🔥 ترند"}
        _ACTION_AR    = {"none": "لا شيء", "all": "الكل",
                         "copy_coupon": "🎟️ نسخ كوبون",
                         "click_link": "🖱️ نقر رابط", "search": "🔍 بحث"}

        @st.cache_data(ttl=300)
        def _gen_distinct(sql):
            try:
                conn = get_conn()
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute(sql)
                rows = [r[0] for r in cur.fetchall()]
                conn.close()
                return rows
            except Exception:
                return []

        # ── المصدر (فوق) + الحالة → منهما تتحدّد قائمة المستخدمين ─────────
        gen_status_label = st.segmented_control(
            "⚡ الحالة", list(_STATUS_AR.values()), default="الكل",
            key="gen_status")
        gen_status = next((k for k, v in _STATUS_AR.items()
                           if v == gen_status_label), "all")

        # ── اكتمال الملف ──────────────────────────────────────────────────
        # مكتمل = مستخدم موقع له تسجيل + ربط تليجرام محقّق
        #         (web_users.telegram_username يطابق bot_users.username).
        gen_complete_label = st.segmented_control(
            "🧩 اكتمال الملف", list(_COMPLETE_AR.values()), default="الكل",
            key="gen_complete")
        gen_complete = next((k for k, v in _COMPLETE_AR.items()
                             if v == gen_complete_label), "all")

        # ── اللغة ─────────────────────────────────────────────────────────
        _lang_sel = st.segmented_control(
            "🌐 اللغة", list(_LANG_AR.values()), default="لا شيء", key="gen_lang")
        gen_lang = next((k for k, v in _LANG_AR.items() if v == _lang_sel), "none")

        # ── الجنس (الموقع فقط — web_users.gender) ─────────────────────────
        _gender_sel = st.segmented_control(
            "⚧ الجنس", list(_GENDER_AR.values()), default="لا شيء",
            key="gen_gender")
        gen_gender = next((k for k, v in _GENDER_AR.items()
                           if v == _gender_sel), "none")

        # ── العمر (الموقع فقط — web_users.birth_date) ─────────────────────
        _age_sel = st.segmented_control(
            "🎂 العمر", list(_AGE_AR.values()), default="لا شيء", key="gen_age")
        gen_age = next((k for k, v in _AGE_AR.items() if v == _age_sel), "none")

        # ── المدينة (من IP الحقيقي — action_logs.city) ────────────────────
        _city_opts = ["لا شيء", "الكل"] + _gen_distinct("""
            SELECT DISTINCT city FROM action_logs
            WHERE city IS NOT NULL AND city <> ''
              AND is_proxy IS NOT TRUE AND is_datacenter IS NOT TRUE
            ORDER BY city""") + ["غير معروف"]
        _city_sel = st.segmented_control(
            "📍 المدينة", _city_opts, default="لا شيء", key="gen_cities")
        gen_city = None if _city_sel in (None, "لا شيء", "الكل") else _city_sel

        # ── حالة المتجر (منها تظهر المتاجر المطلوبة لاحقاً) ───────────────
        _storestat_sel = st.segmented_control(
            "🏬 حالة المتاجر", list(_STORESTAT_AR.values()), default="لا شيء",
            key="gen_store_status")
        gen_store_status = next((k for k, v in _STORESTAT_AR.items()
                                 if v == _storestat_sel), "none")

        # ── متاجر مختارة (قائمتها تتفلتر حسب حالة المتاجر المختارة) ───────
        _store_cond = {
            "active":   "AND last_time > CURRENT_DATE + 3",
            "expired":  "AND last_time < CURRENT_DATE",
            "expiring": "AND last_time BETWEEN CURRENT_DATE AND CURRENT_DATE + 3",
        }.get(gen_store_status, "")
        _store_opts = ["لا شيء", "الكل"] + _gen_distinct(f"""
            SELECT DISTINCT store_id FROM master
            WHERE store_id IS NOT NULL AND store_id <> '' {_store_cond}
            ORDER BY store_id""")
        _store_sel = st.segmented_control(
            "🏪 متاجر متفاعل معها (نسخ/نقر/زيارة)", _store_opts, default="لا شيء", key="gen_stores")
        gen_store = None if _store_sel in (None, "لا شيء", "الكل") else _store_sel

        # ── الأقسام (من master.store_tags) ────────────────────────────────
        _cat_opts = ["لا شيء", "الكل"] + _gen_distinct("""
            SELECT DISTINCT TRIM(tag) AS tag
            FROM master,
                 unnest(string_to_array(
                     trim(both '{}' from COALESCE(store_tags, '')), ',')) AS tag
            WHERE TRIM(tag) <> ''
            ORDER BY tag""")
        _cat_sel = st.segmented_control(
            "🏷️ الأقسام", _cat_opts, default="لا شيء", key="gen_categories")
        gen_category = None if _cat_sel in (None, "لا شيء", "الكل") else _cat_sel

        # ── مفضلة المتاجر (user_favorites kind=store) ─────────────────────
        _favstore_sel = st.segmented_control(
            "🏪 مفضلة المتاجر", list(_FAVSTORE_AR.values()), default="لا شيء",
            key="gen_fav_store")
        gen_fav_store = next((k for k, v in _FAVSTORE_AR.items()
                              if v == _favstore_sel), "none")

        # ── مفضلة الأقسام (user_favorites kind=category) ──────────────────
        _favcat_sel = st.segmented_control(
            "🏷️ مفضلة الأقسام", list(_FAVCAT_AR.values()), default="لا شيء",
            key="gen_fav_cat")
        gen_fav_cat = next((k for k, v in _FAVCAT_AR.items()
                            if v == _favcat_sel), "none")

        # ── الترند ────────────────────────────────────────────────────────
        _trend_sel = st.segmented_control(
            "🔥 الترند", list(_TREND_AR.values()), default="لا شيء",
            key="gen_trend")
        gen_trend = next((k for k, v in _TREND_AR.items()
                          if v == _trend_sel), "none")

        # ── الستوري ───────────────────────────────────────────────────────
        _story_sel = st.segmented_control(
            "🎬 الستوري", list(_STORY_AR.values()), default="لا شيء",
            key="gen_story")
        gen_story = next((k for k, v in _STORY_AR.items()
                          if v == _story_sel), "none")

        # ── الحركات (آخر فلتر) ────────────────────────────────────────────
        _act_sel = st.segmented_control(
            "🎯 الحركات", list(_ACTION_AR.values()), default="لا شيء",
            key="gen_actions")
        gen_action = next((k for k, v in _ACTION_AR.items()
                           if v == _act_sel), "none")

        st.divider()

        # ════════════════════════════════════════════════════════════════
        # ناتج الشريحة: جدول الأشخاص المطابقين + أعمدتهم.
        # تُوصَّل المصادر وحدة وحدة في خطوات البناء القادمة.
        # المختار (بالترتيب): gen_src/gen_status/gen_complete/gen_lang/gen_gender/
        #   gen_age/gen_city/gen_store_status/gen_category/gen_fav_store/
        #   gen_fav_cat/gen_trend/gen_story/gen_store/gen_action
        # ════════════════════════════════════════════════════════════════
        st.caption(
            f"التاريخ: {gen_date_from} → {gen_date_to}  ·  "
            f"المصدر: {gen_src_label or 'الكل'}  ·  "
            f"الحالة: {gen_status_label or 'الكل'}  ·  "
            f"الاكتمال: {gen_complete_label or 'الكل'}  ·  "
            f"اللغة: {_lang_sel or 'لا شيء'}  ·  "
            f"الجنس: {_gender_sel or 'لا شيء'}  ·  "
            f"العمر: {_age_sel or 'لا شيء'}  ·  "
            f"المدينة: {_city_sel or 'لا شيء'}  ·  "
            f"حالة المتاجر: {_storestat_sel or 'لا شيء'}  ·  "
            f"القسم: {_cat_sel or 'لا شيء'}  ·  "
            f"مفضلة متاجر: {_favstore_sel or 'لا شيء'}  ·  "
            f"مفضلة أقسام: {_favcat_sel or 'لا شيء'}  ·  "
            f"الترند: {_trend_sel or 'لا شيء'}  ·  "
            f"الستوري: {_story_sel or 'لا شيء'}  ·  "
            f"متجر: {_store_sel or 'لا شيء'}  ·  "
            f"الحركة: {_act_sel or 'لا شيء'}"
        )

        # ── جلب المستخدمين الأساسيين حسب المصدر ───────────────────────────
        # tg  = bot_users (شخص تيليجرام له نشاط بوت/ميني ضمن المدى)
        # web = web_users
        # الكل = اتحاد منزوع الازدواج (الموقع المربوط بتيليجرام يُعدّ مرة)
        # الحالة: نشط = آخر ظهور < 20 يوم، خامل = ≥ 20 يوم (يتجدّد مع الدخول)
        # الاكتمال: مكتمل = مربوط بين الطرفين (web.telegram_username = bot.username)
        @st.cache_data(ttl=120)
        def _gen_fetch_users(src, status, complete, lang, gender, age, city,
                             store_status, store, action, fav_store, fav_cat,
                             category, story, trend, t_from, t_to):
            _BOT_HANDLES = ("SELECT LOWER(username) FROM bot_users "
                            "WHERE username IS NOT NULL")
            # tg مكتمل = مربوط بحساب موقع (نجلب بياناته عبر LEFT JOIN LATERAL أدناه)
            tg_complete  = "(w3.id IS NOT NULL)"
            web_complete = (f"(wu.telegram_username IS NOT NULL "
                            f"AND LOWER(wu.telegram_username) IN ({_BOT_HANDLES}))")

            def _stat(alias):
                if status == "active":
                    return f" AND {alias}.last_seen >  NOW() - INTERVAL '20 days' "
                if status == "idle":
                    return f" AND {alias}.last_seen <= NOW() - INTERVAL '20 days' "
                return ""

            def _compl(expr):
                if complete == "complete":
                    return f" AND {expr} "
                if complete == "partial":
                    return f" AND NOT {expr} "
                return ""

            def _lang(alias):
                if lang == "ar":
                    return f" AND {alias}.lang = 'ar' "
                if lang == "en":
                    return f" AND {alias}.lang = 'en' "
                return ""

            def _gender(realm):
                # الجنس من web_users فقط: tg مربوط → w3.gender، web → wu.gender
                if gender not in ("male", "female"):
                    return ""
                col = "w3.gender" if realm == "tg" else "wu.gender"
                return f" AND {col} = '{gender}' "

            def _age(realm):
                # العمر من web_users.birth_date (tg مربوط → w3، web → wu)
                col = "w3.birth_date" if realm == "tg" else "wu.birth_date"
                a = f"EXTRACT(YEAR FROM AGE({col}))::int"
                conds = {
                    "u18":   f"{a} < 18",
                    "18-24": f"{a} BETWEEN 18 AND 24",
                    "25-34": f"{a} BETWEEN 25 AND 34",
                    "35-44": f"{a} BETWEEN 35 AND 44",
                    "45-54": f"{a} BETWEEN 45 AND 54",
                    "55p":   f"{a} >= 55",
                }
                c = conds.get(age)
                return f" AND {col} IS NOT NULL AND {c} " if c else ""

            def _city_clause():
                # المدينة من آخر IP (alias cty أدناه). «غير معروف» = بلا مدينة.
                if not city:
                    return ""
                if city == "غير معروف":
                    return " AND cty.city IS NULL "
                safe = city.replace("'", "''")
                return f" AND cty.city = '{safe}' "

            def _storestat(realm):
                # الأشخاص اللي تعاملوا مع متجر بهذه الحالة (master.last_time)
                if store_status not in ("active", "expired", "expiring"):
                    return ""
                uid = "bu.telegram_id" if realm == "tg" else "wu.id"
                src = ("('bot','telegram_miniapp')" if realm == "tg"
                       else "('web')")
                cond = {
                    "active":   "m.last_time > CURRENT_DATE + 3",
                    "expiring": "m.last_time BETWEEN CURRENT_DATE AND CURRENT_DATE + 3",
                    "expired":  "m.last_time < CURRENT_DATE",
                }[store_status]
                return (" AND EXISTS (SELECT 1 FROM action_logs al2 "
                        "JOIN master m ON m.store_id = al2.store_id "
                        f"WHERE al2.user_id = {uid} AND al2.source IN {src} "
                        f"AND al2.store_id IS NOT NULL AND {cond}) ")

            def _store_clause(realm):
                # الأشخاص اللي تفاعلوا مع المتجر المختار بعينه
                if not store:
                    return ""
                uid = "bu.telegram_id" if realm == "tg" else "wu.id"
                src = ("('bot','telegram_miniapp')" if realm == "tg"
                       else "('web')")
                safe = store.replace("'", "''")
                return (" AND EXISTS (SELECT 1 FROM action_logs al3 "
                        f"WHERE al3.user_id = {uid} AND al3.source IN {src} "
                        f"AND al3.store_id = '{safe}') ")

            def _realm_src(realm):
                return ("bu.telegram_id", "('bot','telegram_miniapp')") if realm == "tg" \
                    else ("wu.id", "('web')")

            def _action_clause(realm):
                if action not in ("copy_coupon", "click_link", "search"):
                    return ""
                uid, src = _realm_src(realm)
                return (f" AND EXISTS (SELECT 1 FROM action_logs ala "
                        f"WHERE ala.user_id = {uid} AND ala.source IN {src} "
                        f"AND ala.action_type = '{action}') ")

            def _fav_clause(realm, kind, val):
                # val: has / not / (none|all = بلا فلتر)
                if val not in ("has", "not"):
                    return ""
                key = ("uf.telegram_id = bu.telegram_id" if realm == "tg"
                       else "uf.web_user_id = wu.id")
                ex = (f"EXISTS (SELECT 1 FROM user_favorites uf "
                      f"WHERE {key} AND uf.kind = '{kind}')")
                return f" AND {ex} " if val == "has" else f" AND NOT {ex} "

            def _category_clause(realm):
                if not category:
                    return ""
                # القسم = نقره (view_tag) أو بحثه باسمه (direct_search) — لا وراثة وسوم
                uid, src = _realm_src(realm)
                plat = "('TelegramBot','Miniapp')" if realm == "tg" else "('Web')"
                safe = category.replace("'", "''")
                return (f" AND (EXISTS (SELECT 1 FROM action_logs alc "
                        f"WHERE alc.user_id = {uid} AND alc.source IN {src} "
                        f"AND alc.action_type = 'view_tag' "
                        f"AND split_part(alc.details,'tag:',2) = '{safe}') "
                        f"OR EXISTS (SELECT 1 FROM direct_search dsc "
                        f"WHERE dsc.user_id = {uid} AND dsc.platform IN {plat} "
                        f"AND LOWER(TRIM(dsc.search_keyword)) = LOWER('{safe}'))) ")

            def _story_clause(realm):
                if story not in ("normal", "trend"):
                    return ""
                key = ("sv.tg_user_id = bu.telegram_id" if realm == "tg"
                       else "sv.web_user_id = wu.id")
                flag = ("sv.was_trending = TRUE" if story == "trend"
                        else "sv.was_trending IS NOT TRUE")
                return (f" AND EXISTS (SELECT 1 FROM story_views sv "
                        f"WHERE {key} AND {flag}) ")

            def _trend_clause(realm):
                # إسناد حقيقي: تفاعل (نقر/نسخ/زيارة بطاقة) من مسار الترند.
                # للمربوط (realm='tg' وله w3): نشاط الترند ممكن من البوت
                # (bu.telegram_id, source='bot|telegram_miniapp') أو من الموقع
                # (w3.id, source='web') — كلاهما لنفس الشخص. لو تجاهلنا web نُخفي
                # الجدول كاملاً لمستخدم مربوط نسخ من بطاقة ترند على الموقع.
                if trend not in ("daily", "weekly"):
                    return ""
                if realm == "tg":
                    return (f" AND (EXISTS (SELECT 1 FROM action_logs alt "
                            f"WHERE alt.user_id = bu.telegram_id AND alt.source IN ('bot','telegram_miniapp') "
                            f"AND alt.action_type IN ('click_link','copy_coupon','view_store') "
                            f"AND alt.details = 'trend:{trend}') "
                            f"OR EXISTS (SELECT 1 FROM action_logs altw "
                            f"WHERE w3.id IS NOT NULL AND altw.user_id = w3.id AND altw.source = 'web' "
                            f"AND altw.action_type IN ('click_link','copy_coupon','view_store') "
                            f"AND altw.details = 'trend:{trend}')) ")
                return (f" AND EXISTS (SELECT 1 FROM action_logs alt "
                        f"WHERE alt.user_id = wu.id AND alt.source = 'web' "
                        f"AND alt.action_type IN ('click_link','copy_coupon','view_store') "
                        f"AND alt.details = 'trend:{trend}') ")

            # المكتمل (المربوط) نملأ اسمه/إيميله/جواله من حساب الموقع المرتبط
            tg_sql = f"""
                SELECT 'tg' AS realm, bu.telegram_id::text AS person_id,
                       bu.username AS handle,
                       COALESCE(w3.display_name, bu.name_en) AS name,
                       w3.email AS email, w3.phone_number AS phone,
                       w3.gender AS gender, bu.lang AS lang,
                       EXTRACT(YEAR FROM AGE(w3.birth_date))::int AS age,
                       w3.birth_date AS birth_date, cty.city AS city,
                       bu.last_seen, {tg_complete} AS is_complete,
                       -- النشاط العام للمستخدم المربوط: نجمع عبر القنوات الثلاث
                       --   بوت + ميني-ويب: action_logs.user_id = bu.telegram_id AND source IN ('bot','telegram_miniapp')
                       --   موقع:          action_logs.user_id = w3.id          AND source = 'web' (لو الحساب مربوط)
                       -- نفس الفلسفة على direct_search مع platform ('TelegramBot','Miniapp') مقابل 'Web'.
                       (SELECT string_agg(DISTINCT s.store_id, ', ')
                        FROM action_logs s
                        WHERE s.store_id IS NOT NULL
                          AND ((s.user_id = bu.telegram_id AND s.source IN ('bot','telegram_miniapp'))
                               OR (w3.id IS NOT NULL AND s.user_id = w3.id AND s.source='web'))) AS stores,
                       (SELECT string_agg(DISTINCT cx.cat, ', ') FROM (
                          SELECT split_part(ad.details,'tag:',2) AS cat
                          FROM action_logs ad
                          WHERE ad.action_type='view_tag'
                            AND ((ad.user_id = bu.telegram_id AND ad.source IN ('bot','telegram_miniapp'))
                                 OR (w3.id IS NOT NULL AND ad.user_id = w3.id AND ad.source='web'))
                          UNION
                          SELECT TRIM(ds.search_keyword)
                          FROM direct_search ds
                          WHERE ((ds.user_id = bu.telegram_id AND ds.platform IN ('TelegramBot','Miniapp'))
                                 OR (w3.id IS NOT NULL AND ds.user_id = w3.id AND ds.platform='Web'))
                            AND LOWER(TRIM(ds.search_keyword)) IN (SELECT LOWER(TRIM(t)) FROM master,
                                unnest(string_to_array(trim(both '{{}}' from COALESCE(store_tags,'')), ',')) AS t WHERE TRIM(t)<>'')
                        ) cx WHERE cx.cat IS NOT NULL AND TRIM(cx.cat) <> '') AS categories,
                       (SELECT COUNT(*) FROM action_logs av
                          WHERE av.action_type='view_tag'
                            AND ((av.user_id = bu.telegram_id AND av.source IN ('bot','telegram_miniapp'))
                                 OR (w3.id IS NOT NULL AND av.user_id = w3.id AND av.source='web'))) AS n_cat_click,
                       (SELECT COUNT(*) FROM direct_search ds
                          WHERE LOWER(TRIM(ds.search_keyword)) IN (SELECT LOWER(TRIM(t)) FROM master,
                              unnest(string_to_array(trim(both '{{}}' from COALESCE(store_tags,'')), ',')) AS t WHERE TRIM(t)<>'')
                            AND ((ds.user_id = bu.telegram_id AND ds.platform IN ('TelegramBot','Miniapp'))
                                 OR (w3.id IS NOT NULL AND ds.user_id = w3.id AND ds.platform='Web'))) AS n_cat_search,
                       (SELECT COUNT(*) FROM action_logs ac
                          WHERE ac.action_type='copy_coupon'
                            AND ((ac.user_id = bu.telegram_id AND ac.source IN ('bot','telegram_miniapp'))
                                 OR (w3.id IS NOT NULL AND ac.user_id = w3.id AND ac.source='web'))) AS n_copy,
                       (SELECT COUNT(*) FROM action_logs ac
                          WHERE ac.action_type='click_link'
                            AND ((ac.user_id = bu.telegram_id AND ac.source IN ('bot','telegram_miniapp'))
                                 OR (w3.id IS NOT NULL AND ac.user_id = w3.id AND ac.source='web'))) AS n_click,
                       (SELECT COUNT(*) FROM action_logs ac
                          WHERE ac.action_type='search'
                            AND ((ac.user_id = bu.telegram_id AND ac.source IN ('bot','telegram_miniapp'))
                                 OR (w3.id IS NOT NULL AND ac.user_id = w3.id AND ac.source='web'))) AS n_search,
                       -- الستوري عبر القنوات: tg/ميني عبر sv.tg_user_id + موقع عبر sv.web_user_id (للمربوط).
                       -- الترند/العادي مبنيان على was_trending (snapshot من track.py الذي يطابق
                       -- /api/v1/trend الحي). NULL = سجل قبل migration 034 (لا تصنيف تاريخي) →
                       -- لا يدخل في "ترند" ولا "عادي" بل في "غير معروف" (يظهر في الإجمالي فقط).
                       (SELECT COUNT(*) FROM story_views sv WHERE (sv.tg_user_id = bu.telegram_id OR (w3.id IS NOT NULL AND sv.web_user_id = w3.id))) AS n_story,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.was_trending = TRUE  AND (sv.tg_user_id = bu.telegram_id OR (w3.id IS NOT NULL AND sv.web_user_id = w3.id))) AS n_story_trend,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.was_trending = FALSE AND (sv.tg_user_id = bu.telegram_id OR (w3.id IS NOT NULL AND sv.web_user_id = w3.id))) AS n_story_normal,
                       (SELECT string_agg(DISTINCT sv.store_id, ', ') FROM story_views sv WHERE sv.was_trending = TRUE  AND sv.store_id IS NOT NULL AND (sv.tg_user_id = bu.telegram_id OR (w3.id IS NOT NULL AND sv.web_user_id = w3.id))) AS story_trend_stores,
                       (SELECT string_agg(DISTINCT sv.store_id, ', ') FROM story_views sv WHERE sv.was_trending = FALSE AND sv.store_id IS NOT NULL AND (sv.tg_user_id = bu.telegram_id OR (w3.id IS NOT NULL AND sv.web_user_id = w3.id))) AS story_normal_stores,
                       -- زيارات/نسخ من داخل سياق الستوري: action_logs.story_view_id IS NOT NULL
                       -- (track.py يكتبه عند ما العميل نسخ/نقر من فيوور الستوري). نفس فلسفة
                       -- صفحة "🎬 تحليلات الستوري" — مطابق ١٠٠٪.
                       (SELECT COUNT(*) FROM action_logs al WHERE al.story_view_id IS NOT NULL AND al.action_type='click_link'  AND ((al.user_id = bu.telegram_id AND al.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND al.user_id = w3.id AND al.source='web'))) AS n_story_click,
                       (SELECT COUNT(*) FROM action_logs al WHERE al.story_view_id IS NOT NULL AND al.action_type='copy_coupon' AND ((al.user_id = bu.telegram_id AND al.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND al.user_id = w3.id AND al.source='web'))) AS n_story_copy,
                       -- المفضلة عبر القنوات: tg user يضيف من البوت/الميني عبر uf.telegram_id،
                       -- ومن الموقع عبر uf.web_user_id = w3.id (لو الحساب مربوط). نوسع للاثنين.
                       (SELECT COUNT(*) FROM user_favorites uf WHERE uf.kind='store' AND (uf.telegram_id = bu.telegram_id OR (w3.id IS NOT NULL AND uf.web_user_id = w3.id))) AS n_fav_store,
                       (SELECT COUNT(*) FROM user_favorites uf WHERE uf.kind='category' AND (uf.telegram_id = bu.telegram_id OR (w3.id IS NOT NULL AND uf.web_user_id = w3.id))) AS n_fav_cat,
                       (SELECT string_agg(DISTINCT uf.store_id, ', ') FROM user_favorites uf WHERE uf.kind='store' AND (uf.telegram_id = bu.telegram_id OR (w3.id IS NOT NULL AND uf.web_user_id = w3.id))) AS fav_stores,
                       (SELECT string_agg(DISTINCT uf.category_name, ', ') FROM user_favorites uf WHERE uf.kind='category' AND (uf.telegram_id = bu.telegram_id OR (w3.id IS NOT NULL AND uf.web_user_id = w3.id))) AS fav_cats,
                       -- أعمدة الترند للمستخدم المربوط: نشمل كل أحداثه عبر القنوات
                       -- (bot/miniapp بـ bu.telegram_id + web بـ w3.id لو الحساب موجود).
                       -- بدون هذا التوسع، نشاطه على الموقع يضيع من العدّ ويبدو الجدول
                       -- كأنه ٠ مع وجود سجلات حية في القاعدة.
                       (SELECT string_agg(DISTINCT at2.store_id, ', ') FROM action_logs at2 WHERE at2.action_type IN ('click_link','copy_coupon','view_store') AND at2.details='trend:daily' AND at2.store_id IS NOT NULL AND ((at2.user_id = bu.telegram_id AND at2.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND at2.user_id = w3.id AND at2.source='web'))) AS trend_d_stores,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.action_type='click_link' AND at2.details='trend:daily' AND ((at2.user_id = bu.telegram_id AND at2.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND at2.user_id = w3.id AND at2.source='web'))) AS n_td_click,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.action_type='copy_coupon' AND at2.details='trend:daily' AND ((at2.user_id = bu.telegram_id AND at2.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND at2.user_id = w3.id AND at2.source='web'))) AS n_td_copy,
                       (SELECT string_agg(DISTINCT at2.store_id, ', ') FROM action_logs at2 WHERE at2.action_type IN ('click_link','copy_coupon','view_store') AND at2.details='trend:weekly' AND at2.store_id IS NOT NULL AND ((at2.user_id = bu.telegram_id AND at2.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND at2.user_id = w3.id AND at2.source='web'))) AS trend_w_stores,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.action_type='click_link' AND at2.details='trend:weekly' AND ((at2.user_id = bu.telegram_id AND at2.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND at2.user_id = w3.id AND at2.source='web'))) AS n_tw_click,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.action_type='copy_coupon' AND at2.details='trend:weekly' AND ((at2.user_id = bu.telegram_id AND at2.source IN ('bot','telegram_miniapp')) OR (w3.id IS NOT NULL AND at2.user_id = w3.id AND at2.source='web'))) AS n_tw_copy
                FROM bot_users bu
                LEFT JOIN LATERAL (
                    SELECT id, display_name, email, phone_number, gender, birth_date
                    FROM web_users w3
                    WHERE w3.telegram_username IS NOT NULL
                      AND LOWER(w3.telegram_username) = LOWER(bu.username)
                    LIMIT 1
                ) w3 ON TRUE
                LEFT JOIN LATERAL (
                    SELECT city FROM action_logs al
                    WHERE al.user_id = bu.telegram_id
                      AND al.source IN ('bot','telegram_miniapp')
                      AND al.city IS NOT NULL AND al.city <> ''
                      AND al.is_proxy IS NOT TRUE AND al.is_datacenter IS NOT TRUE
                    ORDER BY al.action_time DESC LIMIT 1
                ) cty ON TRUE
                WHERE bu.deleted_at IS NULL
                  {_stat('bu')} {_compl(tg_complete)} {_lang('bu')} {_gender('tg')} {_age('tg')} {_city_clause()} {_storestat('tg')} {_store_clause('tg')} {_action_clause('tg')} {_fav_clause('tg','store',fav_store)} {_fav_clause('tg','category',fav_cat)} {_category_clause('tg')} {_story_clause('tg')} {_trend_clause('tg')}"""
            web_unlinked = f"""
                SELECT 'web' AS realm, wu.id::text AS person_id,
                       wu.telegram_username AS handle, wu.display_name AS name,
                       wu.email, wu.phone_number AS phone, wu.gender AS gender,
                       wu.lang AS lang,
                       EXTRACT(YEAR FROM AGE(wu.birth_date))::int AS age,
                       wu.birth_date AS birth_date, cty.city AS city,
                       wu.last_seen, {web_complete} AS is_complete,
                       (SELECT string_agg(DISTINCT s.store_id, ', ')
                        FROM action_logs s
                        WHERE s.user_id = wu.id AND s.source = 'web'
                          AND s.store_id IS NOT NULL) AS stores,
                       (SELECT string_agg(DISTINCT cx.cat, ', ') FROM (
                          SELECT split_part(ad.details,'tag:',2) AS cat
                          FROM action_logs ad WHERE ad.user_id = wu.id AND ad.source='web' AND ad.action_type='view_tag'
                          UNION
                          SELECT TRIM(ds.search_keyword)
                          FROM direct_search ds WHERE ds.user_id = wu.id AND ds.platform='Web'
                            AND LOWER(TRIM(ds.search_keyword)) IN (SELECT LOWER(TRIM(t)) FROM master,
                                unnest(string_to_array(trim(both '{{}}' from COALESCE(store_tags,'')), ',')) AS t WHERE TRIM(t)<>'')
                        ) cx WHERE cx.cat IS NOT NULL AND TRIM(cx.cat) <> '') AS categories,
                       (SELECT COUNT(*) FROM action_logs av WHERE av.user_id = wu.id
                          AND av.source='web' AND av.action_type='view_tag') AS n_cat_click,
                       (SELECT COUNT(*) FROM direct_search ds WHERE ds.user_id = wu.id
                          AND ds.platform = 'Web'
                          AND LOWER(TRIM(ds.search_keyword)) IN (SELECT LOWER(TRIM(t)) FROM master,
                              unnest(string_to_array(trim(both '{{}}' from COALESCE(store_tags,'')), ',')) AS t
                              WHERE TRIM(t)<>'')) AS n_cat_search,
                       (SELECT COUNT(*) FROM action_logs ac WHERE ac.user_id = wu.id
                          AND ac.source='web' AND ac.action_type='copy_coupon') AS n_copy,
                       (SELECT COUNT(*) FROM action_logs ac WHERE ac.user_id = wu.id
                          AND ac.source='web' AND ac.action_type='click_link') AS n_click,
                       (SELECT COUNT(*) FROM action_logs ac WHERE ac.user_id = wu.id
                          AND ac.source='web' AND ac.action_type='search') AS n_search,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.web_user_id = wu.id) AS n_story,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = TRUE)  AS n_story_trend,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = FALSE) AS n_story_normal,
                       (SELECT string_agg(DISTINCT sv.store_id, ', ') FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = TRUE  AND sv.store_id IS NOT NULL) AS story_trend_stores,
                       (SELECT string_agg(DISTINCT sv.store_id, ', ') FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = FALSE AND sv.store_id IS NOT NULL) AS story_normal_stores,
                       (SELECT COUNT(*) FROM action_logs al WHERE al.story_view_id IS NOT NULL AND al.action_type='click_link'  AND al.user_id = wu.id AND al.source='web') AS n_story_click,
                       (SELECT COUNT(*) FROM action_logs al WHERE al.story_view_id IS NOT NULL AND al.action_type='copy_coupon' AND al.user_id = wu.id AND al.source='web') AS n_story_copy,
                       (SELECT COUNT(*) FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='store') AS n_fav_store,
                       (SELECT COUNT(*) FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='category') AS n_fav_cat,
                       (SELECT string_agg(DISTINCT uf.store_id, ', ') FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='store') AS fav_stores,
                       (SELECT string_agg(DISTINCT uf.category_name, ', ') FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='category') AS fav_cats,
                       (SELECT string_agg(DISTINCT at2.store_id, ', ') FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type IN ('click_link','copy_coupon') AND at2.details='trend:daily' AND at2.store_id IS NOT NULL) AS trend_d_stores,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='click_link' AND at2.details='trend:daily') AS n_td_click,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='copy_coupon' AND at2.details='trend:daily') AS n_td_copy,
                       (SELECT string_agg(DISTINCT at2.store_id, ', ') FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type IN ('click_link','copy_coupon') AND at2.details='trend:weekly' AND at2.store_id IS NOT NULL) AS trend_w_stores,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='click_link' AND at2.details='trend:weekly') AS n_tw_click,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='copy_coupon' AND at2.details='trend:weekly') AS n_tw_copy
                FROM web_users wu
                LEFT JOIN LATERAL (
                    SELECT city FROM action_logs al
                    WHERE al.user_id = wu.id AND al.source = 'web'
                      AND al.city IS NOT NULL AND al.city <> ''
                      AND al.is_proxy IS NOT TRUE AND al.is_datacenter IS NOT TRUE
                    ORDER BY al.action_time DESC LIMIT 1
                ) cty ON TRUE
                WHERE (wu.telegram_username IS NULL
                       OR LOWER(wu.telegram_username) NOT IN ({_BOT_HANDLES}))
                  {_stat('wu')} {_compl(web_complete)} {_lang('wu')} {_gender('web')} {_age('web')} {_city_clause()} {_storestat('web')} {_store_clause('web')} {_action_clause('web')} {_fav_clause('web','store',fav_store)} {_fav_clause('web','category',fav_cat)} {_category_clause('web')} {_story_clause('web')} {_trend_clause('web')}"""
            web_all = f"""
                SELECT 'web' AS realm, wu.id::text AS person_id,
                       wu.telegram_username AS handle, wu.display_name AS name,
                       wu.email, wu.phone_number AS phone, wu.gender AS gender,
                       wu.lang AS lang,
                       EXTRACT(YEAR FROM AGE(wu.birth_date))::int AS age,
                       wu.birth_date AS birth_date, cty.city AS city,
                       wu.last_seen, {web_complete} AS is_complete,
                       (SELECT string_agg(DISTINCT s.store_id, ', ')
                        FROM action_logs s
                        WHERE s.user_id = wu.id AND s.source = 'web'
                          AND s.store_id IS NOT NULL) AS stores,
                       (SELECT string_agg(DISTINCT cx.cat, ', ') FROM (
                          SELECT split_part(ad.details,'tag:',2) AS cat
                          FROM action_logs ad WHERE ad.user_id = wu.id AND ad.source='web' AND ad.action_type='view_tag'
                          UNION
                          SELECT TRIM(ds.search_keyword)
                          FROM direct_search ds WHERE ds.user_id = wu.id AND ds.platform='Web'
                            AND LOWER(TRIM(ds.search_keyword)) IN (SELECT LOWER(TRIM(t)) FROM master,
                                unnest(string_to_array(trim(both '{{}}' from COALESCE(store_tags,'')), ',')) AS t WHERE TRIM(t)<>'')
                        ) cx WHERE cx.cat IS NOT NULL AND TRIM(cx.cat) <> '') AS categories,
                       (SELECT COUNT(*) FROM action_logs av WHERE av.user_id = wu.id
                          AND av.source='web' AND av.action_type='view_tag') AS n_cat_click,
                       (SELECT COUNT(*) FROM direct_search ds WHERE ds.user_id = wu.id
                          AND ds.platform = 'Web'
                          AND LOWER(TRIM(ds.search_keyword)) IN (SELECT LOWER(TRIM(t)) FROM master,
                              unnest(string_to_array(trim(both '{{}}' from COALESCE(store_tags,'')), ',')) AS t
                              WHERE TRIM(t)<>'')) AS n_cat_search,
                       (SELECT COUNT(*) FROM action_logs ac WHERE ac.user_id = wu.id
                          AND ac.source='web' AND ac.action_type='copy_coupon') AS n_copy,
                       (SELECT COUNT(*) FROM action_logs ac WHERE ac.user_id = wu.id
                          AND ac.source='web' AND ac.action_type='click_link') AS n_click,
                       (SELECT COUNT(*) FROM action_logs ac WHERE ac.user_id = wu.id
                          AND ac.source='web' AND ac.action_type='search') AS n_search,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.web_user_id = wu.id) AS n_story,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = TRUE)  AS n_story_trend,
                       (SELECT COUNT(*) FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = FALSE) AS n_story_normal,
                       (SELECT string_agg(DISTINCT sv.store_id, ', ') FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = TRUE  AND sv.store_id IS NOT NULL) AS story_trend_stores,
                       (SELECT string_agg(DISTINCT sv.store_id, ', ') FROM story_views sv WHERE sv.web_user_id = wu.id AND sv.was_trending = FALSE AND sv.store_id IS NOT NULL) AS story_normal_stores,
                       (SELECT COUNT(*) FROM action_logs al WHERE al.story_view_id IS NOT NULL AND al.action_type='click_link'  AND al.user_id = wu.id AND al.source='web') AS n_story_click,
                       (SELECT COUNT(*) FROM action_logs al WHERE al.story_view_id IS NOT NULL AND al.action_type='copy_coupon' AND al.user_id = wu.id AND al.source='web') AS n_story_copy,
                       (SELECT COUNT(*) FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='store') AS n_fav_store,
                       (SELECT COUNT(*) FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='category') AS n_fav_cat,
                       (SELECT string_agg(DISTINCT uf.store_id, ', ') FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='store') AS fav_stores,
                       (SELECT string_agg(DISTINCT uf.category_name, ', ') FROM user_favorites uf WHERE uf.web_user_id = wu.id AND uf.kind='category') AS fav_cats,
                       (SELECT string_agg(DISTINCT at2.store_id, ', ') FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type IN ('click_link','copy_coupon') AND at2.details='trend:daily' AND at2.store_id IS NOT NULL) AS trend_d_stores,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='click_link' AND at2.details='trend:daily') AS n_td_click,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='copy_coupon' AND at2.details='trend:daily') AS n_td_copy,
                       (SELECT string_agg(DISTINCT at2.store_id, ', ') FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type IN ('click_link','copy_coupon') AND at2.details='trend:weekly' AND at2.store_id IS NOT NULL) AS trend_w_stores,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='click_link' AND at2.details='trend:weekly') AS n_tw_click,
                       (SELECT COUNT(*) FROM action_logs at2 WHERE at2.user_id = wu.id AND at2.source='web' AND at2.action_type='copy_coupon' AND at2.details='trend:weekly') AS n_tw_copy
                FROM web_users wu
                LEFT JOIN LATERAL (
                    SELECT city FROM action_logs al
                    WHERE al.user_id = wu.id AND al.source = 'web'
                      AND al.city IS NOT NULL AND al.city <> ''
                      AND al.is_proxy IS NOT TRUE AND al.is_datacenter IS NOT TRUE
                    ORDER BY al.action_time DESC LIMIT 1
                ) cty ON TRUE
                WHERE TRUE {_stat('wu')} {_compl(web_complete)} {_lang('wu')} {_gender('web')} {_age('web')} {_city_clause()} {_storestat('web')} {_store_clause('web')} {_action_clause('web')} {_fav_clause('web','store',fav_store)} {_fav_clause('web','category',fav_cat)} {_category_clause('web')} {_story_clause('web')} {_trend_clause('web')}"""
            params = []
            if src is None:                       # الكل
                sql = tg_sql + " UNION ALL " + web_unlinked
            elif "web" in src:                    # الموقع
                sql = web_all
            else:                                 # بوت / ميني-ويب
                sql = tg_sql + """
                  AND EXISTS (SELECT 1 FROM action_logs al
                              WHERE al.user_id = bu.telegram_id
                                AND al.source = ANY(%s)
                                AND al.action_time >= %s
                                AND al.action_time <  %s)"""
                params = [list(src), t_from, t_to]
            try:
                conn = get_conn()
                conn.autocommit = True
                df = pd.read_sql(sql, conn, params=params or None)
                conn.close()
                return df
            except Exception as e:
                st.error(f"خطأ جلب المستخدمين: {e}")
                return pd.DataFrame()

        _t_from = pd.Timestamp(gen_date_from).strftime("%Y-%m-%d 00:00:00")
        _t_to   = (pd.Timestamp(gen_date_to) + pd.Timedelta(days=1)
                   ).strftime("%Y-%m-%d 00:00:00")
        df_users = _gen_fetch_users(gen_src, gen_status, gen_complete,
                                    gen_lang, gen_gender, gen_age, gen_city,
                                    gen_store_status, gen_store, gen_action,
                                    gen_fav_store, gen_fav_cat, gen_category,
                                    gen_story, gen_trend, _t_from, _t_to)

        st.markdown(f"### 👥 المستخدمون المطابقون: **{len(df_users)}**")
        if df_users.empty:
            st.info("لا مستخدمين مطابقين لهذه الفلاتر.")
        else:
            _disp = df_users.copy()
            _disp["النوع"]  = _disp["realm"].map(
                {"tg": "🤖 تيليجرام", "web": "🌐 موقع"}).fillna(_disp["realm"])
            _disp["الملف"]  = _disp["is_complete"].map(
                {True: "✅ مكتمل", False: "⛔ ناقص"})
            _disp["الجنس"]  = _disp["gender"].map(
                {"male": "♂️ ذكر", "female": "♀️ أنثى"}).fillna("—")
            _disp["اللغة"]  = _disp["lang"].map(
                {"ar": "🇸🇦 عربي", "en": "🇬🇧 إنجليزي"}).fillna("—")
            _disp["city"]   = _disp["city"].fillna("غير معروف")
            _disp = _disp.rename(columns={
                "person_id": "المعرّف", "handle": "اليوزر",
                "name": "الاسم", "email": "الإيميل",
                "phone": "الجوال", "age": "العمر",
                "birth_date": "تاريخ الميلاد", "city": "المدينة",
                "stores": "المتاجر", "categories": "الأقسام",
                "n_cat_click": "ضغطات القسم", "n_cat_search": "بحث القسم",
                "n_copy": "نسخ", "n_click": "نقرات",
                "n_search": "بحث",
                "n_story":             "ستوري (إجمالي)",
                "n_story_trend":       "ستوري ترند 🔥",
                "n_story_normal":      "ستوري عادي 🎬",
                "story_trend_stores":  "متاجر ستوري ترند 🔥",
                "story_normal_stores": "متاجر ستوري عادي 🎬",
                "n_story_click":       "🖱️ زيارات من ستوري",
                "n_story_copy":        "🎟️ نسخ من ستوري",
                "n_fav_store": "مفضلة متاجر", "n_fav_cat": "مفضلة أقسام",
                "fav_stores": "المتاجر المفضّلة", "fav_cats": "الأقسام المفضّلة",
                "trend_d_stores": "متاجر ترند يومي", "n_td_click": "نقر ترند يومي",
                "n_td_copy": "نسخ ترند يومي",
                "trend_w_stores": "متاجر ترند أسبوعي", "n_tw_click": "نقر ترند أسبوعي",
                "n_tw_copy": "نسخ ترند أسبوعي",
                "last_seen": "آخر ظهور",
            })[["النوع", "الملف", "المعرّف", "اليوزر", "الاسم", "الإيميل",
                "الجوال", "الجنس", "اللغة", "العمر", "تاريخ الميلاد", "المدينة",
                "المتاجر", "الأقسام", "ضغطات القسم", "بحث القسم",
                "نسخ", "نقرات", "بحث",
                "ستوري (إجمالي)",
                "ستوري ترند 🔥", "متاجر ستوري ترند 🔥",
                "ستوري عادي 🎬", "متاجر ستوري عادي 🎬",
                "🖱️ زيارات من ستوري", "🎟️ نسخ من ستوري",
                "متاجر ترند يومي", "نقر ترند يومي", "نسخ ترند يومي",
                "متاجر ترند أسبوعي", "نقر ترند أسبوعي", "نسخ ترند أسبوعي",
                "مفضلة متاجر", "المتاجر المفضّلة",
                "مفضلة أقسام", "الأقسام المفضّلة", "آخر ظهور"]]
            st.dataframe(_disp, width="stretch", hide_index=True)
            _bridge_c1, _bridge_c2 = st.columns(2)
            with _bridge_c1:
                st.download_button(
                    "⬇️ تحميل الجدول (Excel/CSV)",
                    _disp.to_csv(index=False).encode("utf-8-sig"),
                    file_name="users_analytics.csv",
                    mime="text/csv",
                    key="gen_dl",
                    width="stretch",
                )
            # ── الجسر إلى بنّاء الشرائح: تحويل الفلاتر الحالية → شريحة ──
            with _bridge_c2:
                if st.button("📢 احفظ هؤلاء كشريحة + افتح مركز الإشعارات",
                             key="gen_to_segment", width="stretch",
                             type="primary"):
                    try:
                        from api import audience_engine as _ae_bridge
                        _rules_from_filters = _ae_bridge.analytics_filters_to_rules(
                            lang=gen_lang if gen_lang != "none" else None,
                            gender=gen_gender if gen_gender != "none" else None,
                            age=gen_age if gen_age != "none" else None,
                            city=gen_city,
                            status=gen_status if gen_status != "all" else None,
                            complete=gen_complete if gen_complete != "all" else None,
                            fav_store=gen_fav_store if gen_fav_store != "none" else None,
                            fav_cat=gen_fav_cat if gen_fav_cat != "none" else None,
                            store=gen_store,
                            category=gen_category,
                            action=gen_action if gen_action != "none" else None,
                            trend=gen_trend if gen_trend != "none" else None,
                            story=gen_story if gen_story != "none" else None,
                        )
                        _auto_name = (
                            f"من التحليل · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                        _filter_desc = (
                            f"شريحة محوّلة من فلاتر تحليل المستخدمين "
                            f"({len(_rules_from_filters.get('groups',[{}])[0].get('rules',[]))} شرط)"
                        )
                        with get_conn() as _c_save:
                            _c_save.autocommit = True
                            _new_sid = _ae_bridge.save_segment(
                                _c_save, name=_auto_name,
                                description=_filter_desc,
                                rules_json=_rules_from_filters,
                                channel="both")
                        st.success(f"✅ حُفظت كشريحة #{_new_sid}: «{_auto_name}»")
                        st.session_state["nc_preset_segment_id"] = _new_sid
                        st.session_state["page"] = "مركز الإشعارات"
                        st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر الحفظ: {_e}")

        # ════════════════════════════════════════════════════════════════
        # سجل الترند الحي (مستقل) — كل تفاعل من سياق بطاقة ترند، حدث-بحدث.
        # يستخدم نفس فلاتر الجدول أعلاه (المصدر/التاريخ/الترند/الحركة/المدينة/
        # المتجر/اللغة/الجنس/العمر/حالة المستخدم/الاكتمال). يتجاوز bug تجميع
        # الأنشطة متعددة المصدر لمستخدم واحد مربوط، لأن كل صف = حدث منفصل.
        # ════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("### 🔥 سجل الترند الحي — حدث بحدث")
        st.caption(
            "كل تفاعل صار من سياق بطاقات الترند (نسخ كود · نقر رابط · "
            "زيارة بطاقة). يطبّق نفس الفلاتر أعلاه. مستقل عن الجدول الرئيسي."
        )

        # نوع الترند المختار: يحدد details المستهدف
        # NOTE: نستخدم %% في LIKE لتفادي تفسير psycopg2 لـ % كـ placeholder
        # (الـ params تحوي %s لـ action_time فقط).
        _trend_detail_map = {
            "daily":   "al.details = 'trend:daily'",
            "weekly":  "al.details = 'trend:weekly'",
        }
        _tl_trend_where = _trend_detail_map.get(
            gen_trend, "al.details LIKE 'trend:%%'")

        # المصدر event-level على al.source
        if gen_src is None:
            _tl_src_where = "TRUE"
        else:
            _src_list = ",".join(f"'{s}'" for s in gen_src)
            _tl_src_where = f"al.source IN ({_src_list})"

        # الحركة
        if gen_action in ("copy_coupon", "click_link", "search"):
            _tl_act_where = f"al.action_type = '{gen_action}'"
        else:
            # الترند فيه نسخ/نقر/زيارة فقط — البحث لا ينطبق
            _tl_act_where = "al.action_type IN ('click_link','copy_coupon','view_store')"

        # المتجر
        _tl_store_where = ("TRUE" if not gen_store
                           else f"al.store_id = '{gen_store.replace(chr(39), chr(39)*2)}'")

        # المدينة
        if not gen_city:
            _tl_city_where = "TRUE"
        elif gen_city == "غير معروف":
            _tl_city_where = "al.city IS NULL"
        else:
            _tl_city_where = f"al.city = '{gen_city.replace(chr(39), chr(39)*2)}'"

        # فلاتر شخصية: تطبق على web_users (wu) أو bot_users (bu) أو w3 (المربوط)
        _tl_lang_where = ""
        if gen_lang in ("ar", "en"):
            _tl_lang_where = (f" AND (wu.lang = '{gen_lang}' "
                              f"OR bu.lang = '{gen_lang}')")

        _tl_gender_where = ""
        if gen_gender in ("male", "female"):
            _tl_gender_where = (f" AND (wu.gender = '{gen_gender}' "
                                f"OR w3.gender = '{gen_gender}')")

        _age_expr = lambda col: f"EXTRACT(YEAR FROM AGE({col}))::int"
        _age_cond_for = {
            "u18":   lambda c: f"{_age_expr(c)} < 18",
            "18-24": lambda c: f"{_age_expr(c)} BETWEEN 18 AND 24",
            "25-34": lambda c: f"{_age_expr(c)} BETWEEN 25 AND 34",
            "35-44": lambda c: f"{_age_expr(c)} BETWEEN 35 AND 44",
            "45-54": lambda c: f"{_age_expr(c)} BETWEEN 45 AND 54",
            "55p":   lambda c: f"{_age_expr(c)} >= 55",
        }
        _tl_age_where = ""
        if gen_age in _age_cond_for:
            _fn = _age_cond_for[gen_age]
            _tl_age_where = (f" AND ((wu.birth_date IS NOT NULL AND {_fn('wu.birth_date')}) "
                             f"OR (w3.birth_date IS NOT NULL AND {_fn('w3.birth_date')}))")

        _tl_status_where = ""
        if gen_status == "active":
            _tl_status_where = (" AND (wu.last_seen > NOW() - INTERVAL '20 days' "
                                "OR bu.last_seen > NOW() - INTERVAL '20 days')")
        elif gen_status == "idle":
            _tl_status_where = (" AND (wu.last_seen <= NOW() - INTERVAL '20 days' "
                                "OR bu.last_seen <= NOW() - INTERVAL '20 days')")

        _tl_complete_where = ""
        if gen_complete == "complete":
            _tl_complete_where = " AND (w3.id IS NOT NULL OR wu.telegram_username IS NOT NULL)"
        elif gen_complete == "partial":
            _tl_complete_where = " AND (w3.id IS NULL AND (wu.telegram_username IS NULL OR wu.id IS NULL))"

        # حالة المتجر (last_time)
        _tl_storestat_where = ""
        if gen_store_status in ("active", "expired", "expiring"):
            _ms_cond = {
                "active":   "m.last_time > CURRENT_DATE + 3",
                "expired":  "m.last_time < CURRENT_DATE",
                "expiring": "m.last_time BETWEEN CURRENT_DATE AND CURRENT_DATE + 3",
            }[gen_store_status]
            _tl_storestat_where = (f" AND EXISTS (SELECT 1 FROM master m "
                                   f"WHERE m.store_id = al.store_id AND {_ms_cond})")

        _trend_sql = f"""
            SELECT
                al.action_time   AS action_time,
                al.action_type   AS action_type,
                al.details       AS details,
                al.store_id      AS store_id,
                al.user_id       AS user_id,
                COALESCE(wu.display_name, w3.display_name, bu.name_en) AS name,
                COALESCE(wu.telegram_username, bu.username)            AS handle,
                al.source        AS source,
                al.city          AS city,
                al.country_code  AS country_code
            FROM action_logs al
            LEFT JOIN web_users wu
                ON wu.id = al.user_id AND al.source = 'web'
            LEFT JOIN bot_users bu
                ON bu.telegram_id = al.user_id
                   AND al.source IN ('bot','telegram_miniapp')
            LEFT JOIN web_users w3
                ON LOWER(w3.telegram_username) = LOWER(bu.username)
            WHERE {_tl_trend_where}
              AND {_tl_src_where}
              AND {_tl_act_where}
              AND {_tl_store_where}
              AND {_tl_city_where}
              AND al.action_time >= %s
              AND al.action_time <  %s
              {_tl_lang_where}
              {_tl_gender_where}
              {_tl_age_where}
              {_tl_status_where}
              {_tl_complete_where}
              {_tl_storestat_where}
            ORDER BY al.action_time DESC
        """

        try:
            conn = get_conn()
            conn.autocommit = True
            df_trend_log = pd.read_sql(_trend_sql, conn,
                                       params=[_t_from, _t_to])
            conn.close()

            if df_trend_log.empty:
                st.info("لا تفاعلات مسجلة في سياق الترند ضمن الفلاتر الحالية. "
                        "(جرّب: نوع الترند = الكل، الحركات = الكل، المدى أوسع)")
            else:
                # خلاصة
                _by_act = df_trend_log["action_type"].value_counts().to_dict()
                _by_det = df_trend_log["details"].value_counts().to_dict()
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("إجمالي الأحداث", len(df_trend_log))
                mc2.metric("مستخدمون فريدون",
                           df_trend_log["user_id"].dropna().nunique())
                mc3.metric("متاجر مختلفة",
                           df_trend_log["store_id"].nunique())
                md1, md2, md3 = st.columns(3)
                md1.metric("👁️ زيارات", int(_by_act.get("view_store", 0)))
                md2.metric("🎟️ نسخ",   int(_by_act.get("copy_coupon", 0)))
                md3.metric("🖱️ نقرات", int(_by_act.get("click_link", 0)))

                # توزيع يومي/أسبوعي لو نوع الترند = الكل/لا شيء
                if gen_trend not in ("daily", "weekly"):
                    n_d = int(_by_det.get("trend:daily", 0))
                    n_w = int(_by_det.get("trend:weekly", 0))
                    st.caption(f"🔥 يومي: **{n_d}** حدث  ·  🔥 أسبوعي: **{n_w}** حدث")

                _disp_trend = df_trend_log.copy()
                _disp_trend["action_type"] = _disp_trend["action_type"].map({
                    "click_link":  "🖱️ نقر رابط",
                    "copy_coupon": "🎟️ نسخ كود",
                    "view_store":  "👁️ زيارة بطاقة",
                }).fillna(_disp_trend["action_type"])
                _disp_trend["details"] = _disp_trend["details"].map({
                    "trend:daily":  "🔥 يومي",
                    "trend:weekly": "🔥 أسبوعي",
                }).fillna(_disp_trend["details"])
                _disp_trend["source"] = _disp_trend["source"].map({
                    "web": "🌐 موقع",
                    "bot": "🤖 بوت",
                    "telegram_miniapp": "🔹 ميني-ويب",
                }).fillna(_disp_trend["source"])
                _disp_trend["name"]   = _disp_trend["name"].fillna("زائر غير مسجّل")
                _disp_trend["handle"] = _disp_trend["handle"].fillna("—")
                _disp_trend["city"]   = _disp_trend["city"].fillna("—")
                _disp_trend = _disp_trend.rename(columns={
                    "action_time":  "الوقت",
                    "action_type":  "الحدث",
                    "details":      "نوع الترند",
                    "store_id":     "المتجر",
                    "user_id":      "المعرّف",
                    "name":         "الاسم",
                    "handle":       "اليوزر",
                    "source":       "المصدر",
                    "city":         "المدينة",
                    "country_code": "الدولة",
                })[["الوقت", "نوع الترند", "الحدث", "المتجر", "المعرّف",
                    "الاسم", "اليوزر", "المصدر", "المدينة", "الدولة"]]

                st.dataframe(_disp_trend, width="stretch",
                             hide_index=True)
                st.download_button(
                    "⬇️ تحميل سجل الترند (Excel/CSV)",
                    _disp_trend.to_csv(index=False).encode("utf-8-sig"),
                    file_name="trend_log.csv",
                    mime="text/csv",
                    key="trend_log_dl",
                )
        except Exception as e:
            import traceback as _tb
            st.error(f"خطأ في سجل الترند: {type(e).__name__}: {e}")
            with st.expander("تفاصيل تقنية (للمطوّر)"):
                st.code(_tb.format_exc())
            if 'conn' in locals(): conn.close()

    # ── القائمة الثانية: التحليل الفردي ─────────────────────────────────
    with tab_individual:
        # ════════════════════════════════════════════════════════════════════
        # سيرة حياة المستخدم — كل تفاعل حصل، مرتباً بالوقت، عبر الموقع +
        # البوت + الميني-ويب، من أول دخول لآخر خروج. مصدر الحقيقة:
        #   • action_logs   : copy_coupon / click_link / search / view_tag / view_store
        #   • direct_search : بحث كلمات (يتقاطع مع action_logs.search لكنه يحفظ الكلمة)
        #   • story_views   : فتحات الستوري (مع was_trending snapshot)
        #   • user_favorites: إضافات مفضلة (متاجر/أقسام)
        # نوحّدها بـ UNION ALL ثم نرتّبها تنازلياً.
        # ════════════════════════════════════════════════════════════════════
        st.markdown("### 🔎 ابحث عن شخص")
        st.caption(
            "اكتب جزء من الاسم، يوزر تيليجرام، الإيميل، الجوال، أو معرّف موقع/تيليجرام. "
            "ثم اختر الشخص من النتائج لعرض سيرته الكاملة عبر القنوات الثلاث."
        )

        q = st.text_input(
            "🔎 الباحث",
            placeholder="مثال: salahasiri  ·  user@gmail.com  ·  0501234567  ·  650035493",
            key="ind_query",
        )

        if not q or len(q.strip()) < 2:
            st.info("اكتب حرفين على الأقل لبدء البحث.")
        else:
            qn = q.strip()
            qlike = f"%{qn}%"
            qdigits = "".join(ch for ch in qn if ch.isdigit())

            try:
                conn_i = get_conn()
                conn_i.autocommit = True
                # نبحث في web_users و bot_users ثم نوحّد النتائج. كل صف = شخص محتمل
                # مع person_key يميّز realm + person_id لاستعلام السيرة لاحقاً.
                matches_sql = """
                    SELECT 'web' AS realm,
                           wu.id::text AS person_id,
                           wu.display_name AS name,
                           wu.telegram_username AS handle,
                           wu.email, wu.phone_number AS phone,
                           wu.last_seen,
                           CASE
                             WHEN wu.telegram_username IS NOT NULL
                              AND LOWER(wu.telegram_username) IN
                                  (SELECT LOWER(username) FROM bot_users WHERE username IS NOT NULL)
                             THEN TRUE ELSE FALSE
                           END AS is_linked
                    FROM web_users wu
                    WHERE COALESCE(wu.display_name,'')      ILIKE %s
                       OR COALESCE(wu.telegram_username,'') ILIKE %s
                       OR COALESCE(wu.email,'')             ILIKE %s
                       OR COALESCE(wu.phone_number,'')      ILIKE %s
                       OR (LENGTH(%s) > 0 AND wu.id::text = %s)
                    UNION ALL
                    SELECT 'tg'  AS realm,
                           bu.telegram_id::text AS person_id,
                           bu.name_en AS name,
                           bu.username AS handle,
                           NULL AS email, NULL AS phone,
                           bu.last_seen,
                           CASE
                             WHEN bu.username IS NOT NULL
                              AND LOWER(bu.username) IN
                                  (SELECT LOWER(telegram_username) FROM web_users WHERE telegram_username IS NOT NULL)
                             THEN TRUE ELSE FALSE
                           END AS is_linked
                    FROM bot_users bu
                    WHERE bu.deleted_at IS NULL
                      AND (COALESCE(bu.name_en,'')   ILIKE %s
                       OR  COALESCE(bu.username,'')  ILIKE %s
                       OR  (LENGTH(%s) > 0 AND bu.telegram_id::text = %s))
                    ORDER BY last_seen DESC NULLS LAST
                    LIMIT 50
                """
                matches = pd.read_sql(
                    matches_sql, conn_i,
                    params=[qlike, qlike, qlike, qlike, qdigits, qdigits,
                            qlike, qlike, qdigits, qdigits],
                )

                if matches.empty:
                    st.warning("لا نتائج. جرّب جزء مختلف من الاسم/اليوزر/الإيميل/الجوال.")
                else:
                    # نطوي صفوف نفس الشخص (web+tg مربوطين) إلى صف واحد
                    # لأن البحث قد يصيب الاثنين بنفس الـ handle.
                    matches["label"] = matches.apply(
                        lambda r: (
                            f"{'🌐' if r['realm']=='web' else '🤖'} "
                            f"{r['name'] or '—'}  ·  "
                            f"@{r['handle']}" if r['handle'] else
                            (r['email'] or r['phone'] or r['person_id'])
                            + (f"  ·  {r['email'] or ''}" if r['email'] else "")
                            + ("  ·  🔗 مربوط" if r['is_linked'] else "")
                        ),
                        axis=1,
                    )
                    options = matches.apply(
                        lambda r: f"{r['realm']}|{r['person_id']}", axis=1
                    ).tolist()
                    labels  = matches["label"].tolist()
                    sel = st.selectbox(
                        f"اختر شخصاً ({len(matches)} نتيجة):",
                        options, format_func=lambda v: labels[options.index(v)],
                        key="ind_pick",
                    )
                    sel_realm, sel_pid = sel.split("|", 1)
                    sel_row = matches[(matches["realm"] == sel_realm)
                                      & (matches["person_id"] == sel_pid)].iloc[0]

                    # ── ملف مختصر ──────────────────────────────────────
                    st.markdown("---")
                    st.markdown(f"### 👤 ملف الشخص: **{sel_row['name'] or '—'}**")

                    # لو مربوط: نسحب الـ web_users.id (w3) و bot_users.telegram_id (bu)
                    # لربط كل الجداول لاحقاً. لو غير مربوط: واحد منهم فقط.
                    if sel_realm == "tg":
                        bu_tid = int(sel_pid)
                        link_row = pd.read_sql("""
                            SELECT w.id, w.display_name, w.email, w.phone_number,
                                   w.gender, w.birth_date, w.lang AS web_lang
                            FROM bot_users b
                            LEFT JOIN web_users w
                              ON w.telegram_username IS NOT NULL
                             AND LOWER(w.telegram_username) = LOWER(b.username)
                            WHERE b.telegram_id = %s LIMIT 1
                        """, conn_i, params=[bu_tid])
                        wu_id = (int(link_row.iloc[0]["id"])
                                 if not link_row.empty and pd.notna(link_row.iloc[0]["id"])
                                 else None)
                    else:
                        wu_id = int(sel_pid)
                        link_row = pd.read_sql("""
                            SELECT b.telegram_id, b.username, b.name_en, b.lang AS bot_lang
                            FROM web_users w
                            LEFT JOIN bot_users b
                              ON b.username IS NOT NULL
                             AND LOWER(b.username) = LOWER(w.telegram_username)
                             AND b.deleted_at IS NULL
                            WHERE w.id = %s LIMIT 1
                        """, conn_i, params=[wu_id])
                        bu_tid = (int(link_row.iloc[0]["telegram_id"])
                                  if not link_row.empty and pd.notna(link_row.iloc[0]["telegram_id"])
                                  else None)

                    # عرض الملف
                    pc1, pc2, pc3 = st.columns(3)
                    with pc1:
                        st.markdown(f"**🌐 يوزر تيليجرام:** {sel_row['handle'] or '—'}")
                        st.markdown(f"**📧 إيميل:** {sel_row['email'] or '—'}")
                        st.markdown(f"**📱 جوال:** {sel_row['phone'] or '—'}")
                    with pc2:
                        st.markdown(f"**🆔 web_users.id:** `{wu_id if wu_id else '—'}`")
                        st.markdown(f"**🆔 telegram_id:** `{bu_tid if bu_tid else '—'}`")
                        st.markdown(f"**🔗 الحالة:** "
                                    + ("✅ مربوط (موقع ↔ تيليجرام)"
                                       if wu_id and bu_tid else "⛔ قناة واحدة"))
                    with pc3:
                        # last_seen صار timestamptz → _ksa_dt يضمن العرض بتوقيت الرياض
                        st.markdown(f"**⏱️ آخر ظهور:** "
                                    f"{_ksa_dt(pd.Series([sel_row['last_seen']])).iloc[0].strftime('%Y-%m-%d %H:%M') if pd.notna(sel_row['last_seen']) else '—'}")

                    # ── سيرة الحياة (UNION ALL) ────────────────────────
                    # UID list: نوحد رصد الأحداث من كل القنوات. للمربوط: bu.telegram_id
                    # يلتقط البوت+الميني، wu.id يلتقط الموقع. لغير المربوط: واحد منهم.
                    st.markdown("---")
                    st.markdown("### 📜 سيرة الحياة — حدث بحدث")
                    st.caption(
                        "ترتيب تنازلي بالوقت. كل سطر = تفاعل حقيقي. القناة "
                        "تأتي من source/platform في القاعدة."
                    )

                    # ── نطاق التاريخ (يفلتر كل الأحداث في الـ UNION) ──
                    _ind_c1, _ind_c2 = st.columns(2)
                    _ind_today = date.today()
                    with _ind_c1:
                        ind_date_from = st.date_input(
                            "📅 من تاريخ",
                            value=_ind_today - timedelta(days=90),
                            max_value=_ind_today, key="ind_date_from",
                        )
                    with _ind_c2:
                        ind_date_to = st.date_input(
                            "📅 إلى تاريخ", value=_ind_today,
                            min_value=ind_date_from,
                            max_value=_ind_today, key="ind_date_to",
                        )
                    _ind_t_from = pd.Timestamp(ind_date_from).strftime("%Y-%m-%d 00:00:00")
                    _ind_t_to   = (pd.Timestamp(ind_date_to) + pd.Timedelta(days=1)
                                   ).strftime("%Y-%m-%d 00:00:00")

                    # نبني شرط user_id لكل جدول مع التعامل مع NULL لو واحد منهم مفقود.
                    bu_tid_sql = bu_tid if bu_tid is not None else -1
                    wu_id_sql  = wu_id  if wu_id  is not None else -1

                    # نلفّ الـ UNION ALL في outer SELECT ليطبّق فلتر التاريخ
                    # على كل الأحداث بصرف النظر عن مصدرها.
                    timeline_sql = """
                        SELECT * FROM (
                          -- action_logs: copy / click / search / view_tag / view_store
                          SELECT
                              al.action_time AS ts,
                              al.source      AS channel,
                              al.action_type AS event,
                              al.store_id    AS store_id,
                              COALESCE(al.details,'') AS details,
                              COALESCE(al.city,'')    AS city,
                              COALESCE(al.story_view_id::text,'') AS extra
                          FROM action_logs al
                          WHERE (al.user_id = %s AND al.source IN ('bot','telegram_miniapp'))
                             OR (al.user_id = %s AND al.source = 'web')

                          UNION ALL
                          -- direct_search: سجل الكلمات (العمود الصحيح في production = search_date)
                          SELECT
                              ds.search_date AS ts,
                              CASE ds.platform
                                WHEN 'TelegramBot' THEN 'bot'
                                WHEN 'Miniapp'     THEN 'telegram_miniapp'
                                WHEN 'Web'         THEN 'web'
                                ELSE COALESCE(ds.platform,'?')
                              END AS channel,
                              'direct_search' AS event,
                              COALESCE(ds.store_id,'') AS store_id,
                              COALESCE(ds.search_keyword,'') AS details,
                              '' AS city,
                              CASE WHEN ds.user_found THEN 'وجد' ELSE 'لم يجد' END AS extra
                          FROM direct_search ds
                          WHERE (ds.user_id = %s AND ds.platform IN ('TelegramBot','Miniapp'))
                             OR (ds.user_id = %s AND ds.platform = 'Web')

                          UNION ALL
                          -- story_views: فتحات الستوري
                          SELECT
                              sv.viewed_at  AS ts,
                              sv.source     AS channel,
                              'story_view'  AS event,
                              COALESCE(sv.store_id,'') AS store_id,
                              CASE WHEN sv.was_trending IS TRUE  THEN 'trend'
                                   WHEN sv.was_trending IS FALSE THEN 'normal'
                                   ELSE 'unknown' END AS details,
                              '' AS city,
                              COALESCE(sv.view_id::text,'') AS extra
                          FROM story_views sv
                          WHERE sv.tg_user_id = %s OR sv.web_user_id = %s

                          UNION ALL
                          -- user_favorites: إضافات المفضلة
                          SELECT
                              uf.created_at AS ts,
                              COALESCE(uf.platform,'?') AS channel,
                              'add_favorite' AS event,
                              COALESCE(uf.store_id,'')      AS store_id,
                              CASE uf.kind WHEN 'store' THEN 'store'
                                           WHEN 'category' THEN COALESCE(uf.category_name,'category')
                                           ELSE COALESCE(uf.kind,'?') END AS details,
                              '' AS city,
                              COALESCE(uf.kind,'') AS extra
                          FROM user_favorites uf
                          WHERE uf.telegram_id = %s OR uf.web_user_id = %s
                        ) tl
                        WHERE tl.ts >= %s AND tl.ts < %s
                        ORDER BY tl.ts DESC
                    """
                    timeline = pd.read_sql(
                        timeline_sql, conn_i,
                        params=[bu_tid_sql, wu_id_sql,    # action_logs
                                bu_tid_sql, wu_id_sql,    # direct_search
                                bu_tid_sql, wu_id_sql,    # story_views
                                bu_tid_sql, wu_id_sql,    # user_favorites
                                _ind_t_from, _ind_t_to],  # نطاق التاريخ
                    )

                    if timeline.empty:
                        st.info("لا يوجد سجل تفاعلات لهذا الشخص.")
                    else:
                        # تنسيق العرض
                        _ch_map = {
                            "web": "🌐 موقع",
                            "bot": "🤖 بوت",
                            "telegram_miniapp": "🔹 ميني-ويب",
                        }
                        _ev_map = {
                            # تفاعلات أساسية (action_logs)
                            "click_link":    "🖱️ نقر رابط",
                            "copy_coupon":   "🎟️ نسخ كود",
                            "search":        "🔎 بحث",
                            "view_tag":      "🏷️ تصفّح قسم",
                            "view_store":    "👁️ زيارة بطاقة متجر",
                            "view_trend":    "🔥 زيارة صفحة الترند",
                            # تنقل البوت
                            "start":              "🚀 بدء البوت",
                            "end_session":        "🏁 نهاية جلسة",
                            "view_all":           "📋 عرض كل المتاجر",
                            "view_sections":      "🗂️ عرض الأقسام",
                            "view_favorites":     "❤️ فتح المفضلة",
                            "back":               "↩️ رجوع",
                            "lang_pick":          "🌐 اختيار لغة",
                            "request_code":       "📝 طلب كود غير موجود",
                            "reaction_heart":     "💖 إعجاب",
                            "unknown_input":      "❓ نص غير معروف",
                            "favorite_add":       "❤️ إضافة مفضلة (بوت)",
                            "category_favorite_add": "❤️ إضافة قسم للمفضلة (بوت)",
                            # خمول
                            "idle_warn":   "💤 تنبيه خمول",
                            "idle_kick":   "⏰ طرد بسبب خمول",
                            "idle_alert":  "⚠️ تنبيه خمول",
                            # مصادر أخرى
                            "direct_search": "🔎 بحث كلمة",
                            "story_view":    "🎬 فتحة ستوري",
                            "add_favorite":  "❤️ إضافة مفضلة",
                        }
                        disp = timeline.copy()
                        disp["ts"]     = pd.to_datetime(disp["ts"], errors="coerce")
                        disp["channel"] = disp["channel"].map(_ch_map).fillna(disp["channel"])
                        disp["event"]   = disp["event"].map(_ev_map).fillna(disp["event"])
                        # توضيح details للستوري وللترند ولإضافة المفضلة
                        _det_map = {
                            "trend":          "🔥 ترند",
                            "normal":         "🎬 عادي",
                            "unknown":        "— غير معروف",
                            "trend:daily":    "🔥 ترند يومي",
                            "trend:weekly":   "🔥 ترند أسبوعي",
                            "store":          "🏪 متجر",
                            "category":       "🏷️ قسم",
                        }
                        # نحفظ القيم الخام قبل التحويل لاستخراج القسم/المتجر
                        _raw_event   = timeline["event"].astype(str)
                        _raw_details = timeline["details"].astype(str)
                        _raw_extra   = timeline["extra"].astype(str)
                        _raw_store   = timeline["store_id"].astype(str)

                        def _split_store(i):
                            ev = _raw_event.iat[i]
                            sid = _raw_store.iat[i]
                            ex = _raw_extra.iat[i]
                            # add_favorite بـ category لا يحمل store_id
                            if ev == "add_favorite" and ex == "category":
                                return ""
                            # category_favorite_add (بوت) كمان قسم
                            if ev == "category_favorite_add":
                                return ""
                            # view_tag تصفّح قسم (لا متجر)
                            if ev == "view_tag":
                                return ""
                            return sid

                        def _split_category(i):
                            ev = _raw_event.iat[i]
                            d  = _raw_details.iat[i]
                            ex = _raw_extra.iat[i]
                            # تصفّح قسم: details = 'tag:اسم'
                            if ev == "view_tag":
                                return d[4:] if d.startswith("tag:") else d
                            # category_favorite_add في البوت
                            if ev == "category_favorite_add":
                                return d[4:] if d.startswith("tag:") else d
                            # add_favorite من user_favorites: لو category، details يحمل اسم القسم
                            if ev == "add_favorite" and ex == "category":
                                return d
                            return ""

                        disp["المتجر"] = [
                            _split_store(i) for i in range(len(disp))
                        ]
                        disp["القسم"] = [
                            _split_category(i) for i in range(len(disp))
                        ]
                        disp["details"] = disp["details"].map(_det_map).fillna(disp["details"])
                        # ملاحظة: نحوّل extra (store/category) للعربي إذا كان نوع مفضلة
                        _extra_map = {"store": "🏪 متجر", "category": "🏷️ قسم"}
                        disp["extra"] = disp["extra"].map(_extra_map).fillna(disp["extra"])
                        disp = disp.rename(columns={
                            "ts": "الوقت", "channel": "القناة",
                            "event": "الحدث",
                            "details": "تفاصيل", "city": "المدينة",
                            "extra": "ملاحظة",
                        })

                        # خلاصة مختصرة
                        n_total = len(disp)
                        n_web   = (timeline["channel"] == "web").sum()
                        n_bot   = (timeline["channel"] == "bot").sum()
                        n_mini  = (timeline["channel"] == "telegram_miniapp").sum()
                        first_ts = disp["الوقت"].min()
                        last_ts  = disp["الوقت"].max()

                        mc1, mc2, mc3, mc4 = st.columns(4)
                        mc1.metric("إجمالي الأحداث", n_total)
                        mc2.metric("🌐 موقع", int(n_web))
                        mc3.metric("🤖 بوت", int(n_bot))
                        mc4.metric("🔹 ميني-ويب", int(n_mini))
                        st.caption(
                            f"📅 أول تفاعل: **{first_ts.strftime('%Y-%m-%d %H:%M') if pd.notna(first_ts) else '—'}**  ·  "
                            f"آخر تفاعل: **{last_ts.strftime('%Y-%m-%d %H:%M') if pd.notna(last_ts) else '—'}**"
                        )

                        _final_cols = ["الوقت", "القناة", "الحدث",
                                       "القسم", "المتجر",
                                       "تفاصيل", "المدينة", "ملاحظة"]
                        st.dataframe(
                            disp[_final_cols],
                            width="stretch", hide_index=True,
                        )
                        st.download_button(
                            "⬇️ تحميل السيرة (Excel/CSV)",
                            disp[_final_cols].to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"user_timeline_{sel_realm}_{sel_pid}.csv",
                            mime="text/csv",
                            key="ind_dl",
                        )
                conn_i.close()
            except Exception as e:
                import traceback as _tb
                st.error(f"خطأ في التحليل الفردي: {type(e).__name__}: {e}")
                with st.expander("تفاصيل تقنية"):
                    st.code(_tb.format_exc())
                if 'conn_i' in locals():
                    try: conn_i.close()
                    except Exception: pass

    # ── القائمة الثالثة: الذكاء الاصطناعي (Chat) ─────────────────────────
    with tab_ai:
        st.markdown("### 🤖 اسأل عن أي شيء في قاعدة البيانات")
        st.caption(
            "وصول كامل لكل الجداول والأعمدة الفعلية في القاعدة (يقرأها من "
            "information_schema لحظياً). اكتب سؤالك بالعربي — مثال: "
            "«أكثر 10 متاجر نسخاً هذا الأسبوع»، «كم بحث ما لقى نتيجة؟»، "
            "«مين أكثر 5 مستخدمين تفاعلاً مع متجر نون؟»"
        )

        if "ai_users_history" not in st.session_state:
            st.session_state["ai_users_history"] = []

        # ── جلب المخطط من القاعدة (مضغوط لتوفير التوكنز) ────────────────
        @st.cache_data(ttl=3600, show_spinner=False)
        def _ai_get_full_schema() -> str:
            """
            يقرأ جداول/أعمدة الـ public من information_schema.
            صيغة مضغوطة: اسم العمود فقط (بدون النوع/nullable) لتوفير ~50%
            من التوكنز. الـ AI يستنتج النوع من السياق أو الملاحظات.
            """
            try:
                _c = get_conn()
                _c.autocommit = True
                _cur = _c.cursor()
                _cur.execute("""
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                """)
                _rows = _cur.fetchall()
                _tables: dict[str, list[str]] = {}
                for tbl, col in _rows:
                    _tables.setdefault(tbl, []).append(col)
                _c.close()
                # سطر واحد لكل جدول: table_name: col1, col2, col3, ...
                _lines = [f"{tbl}: {', '.join(cols)}"
                          for tbl, cols in sorted(_tables.items())]
                return "\n".join(_lines)
            except Exception as e:
                return f"-- خطأ في جلب المخطط: {e}"

        # ملاحظات لا تظهر في information_schema (تحذيرات منطقية للـ AI)
        _AI_DB_HINTS = """
ملاحظات منطقية مهمة (لا تظهر في information_schema):
- master.store_id يحوي «اسم المتجر العربي» (مثل "نون", "شاهد")؛ لا يوجد عمود اسمه store_name.
- master.name_en الاسم بالإنجليزي (قد يكون فارغاً).
- master.store_tags و master.store_tags_en نوعهما TEXT (وليس مصفوفة) رغم أن البيانات بصيغة '{tag1,tag2}'.
  للبحث استخدم: store_tags ILIKE '%tag%'. ممنوع unnest(store_tags) أو ANY(store_tags).
  للتحويل لمصفوفة: string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',').
- master.is_trending قيمها نصية: 'عادي' أو 'ترند 🔥'.
- ربط جداول المستخدمين بـ action_logs حسب source:
    source IN ('bot','telegram_miniapp','miniapp') → user_id = bot_users.telegram_id
    source = 'web'                                  → user_id = web_users.id
- direct_search جدول البحث المستقل (يحوي search_keyword و search_date).
- action_logs.action_type ∈ ('search','click_link','copy_coupon','view_store','view_trend').
- لإجمالي المستخدمين عبر المنصة كاملة: اجمع bot_users + web_users بـ UNION.
- لربط action_logs بالمتجر: al.store_id = m.store_id (نص = نص).
- ⚠️ أرقام الجوال (web_users.phone) مخزّنة بصيغ مختلفة: '0534448900', '534448900',
  '+966534448900', '966534448900'، وقد تحوي مسافات/شرطات. للبحث المرن دائماً:
    WHERE REGEXP_REPLACE(COALESCE(phone,''), '\\D', '', 'g')
          LIKE '%' || REGEXP_REPLACE('<الرقم المُدخل>', '\\D', '', 'g') || '%'
  هذا يطابق بغضّ النظر عن الصيغة (يجرّد كل ما عدا الأرقام ثم يقارن).
- ⚠️ «مدينة المستخدم» الفعلية تأتي من IP في action_logs.city وليس من web_users.city.
  للجلب: آخر مدينة من action_logs مع استبعاد البروكسي/داتاسنتر:
    SELECT city FROM action_logs
    WHERE user_id = <id> AND city IS NOT NULL AND city <> ''
      AND is_proxy IS NOT TRUE AND is_datacenter IS NOT TRUE
    ORDER BY action_time DESC LIMIT 1
  مع مراعاة ربط user_id بالـ source كما في القاعدة أعلاه.
- لمعرفة مصدر المستخدم من رقم الجوال: ابحث في web_users (لأن bot_users لا يحوي phone)،
  ثم استخدم web_users.id لربط action_logs بـ source='web'.

- ⚠️⚠️ **التوقيت (مهم جداً)**: كل أعمدة الوقت في القاعدة (action_time, search_date,
  created_at, last_seen, ...) مخزّنة بـ **UTC**. المستخدمون في **السعودية (UTC+3)**.
  لذلك أي تحليل لساعة/يوم/شهر **يجب** أن يحوّل التوقيت أولاً:
    EXTRACT(HOUR FROM action_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh')
    DATE(action_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh')
  للمقارنة مع CURRENT_DATE بتوقيت السعودية:
    (action_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh')::date
       >= (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Riyadh')::date - INTERVAL '7 days'
  ممنوع استخدام EXTRACT(HOUR FROM action_time) مباشرة، يعطي ساعة UTC وهي غلط.

- ⚠️ **تحديد المستخدم بالاسم**: عند طلب «من بحث»، «من نسخ»، «اسم المستخدم»،
  لا تكتفي بإرجاع user_id رقمي — يجب الربط مع جداول المستخدمين عبر LEFT JOIN
  لإحضار اسم/يوزر/إيميل، مع التعامل مع source:
    LEFT JOIN bot_users bu ON bu.telegram_id = al.user_id
                          AND al.source IN ('bot','telegram_miniapp','miniapp')
    LEFT JOIN web_users wu ON wu.id = al.user_id AND al.source = 'web'
  ثم اعرض COALESCE معبّر، مثلاً:
    COALESCE(bu.username, wu.email, wu.phone,
             CASE WHEN bu.first_name IS NOT NULL
                  THEN bu.first_name || ' ' || COALESCE(bu.last_name,'')
                  ELSE NULL END,
             'مجهول') AS user_identifier

- ⚠️ **`direct_search.user_found` موجود وهو BOOLEAN**. للبحث عن الكلمات التي
  لم يجد لها المستخدم نتيجة، استخدم: `WHERE user_found = false`.
  لا تدّعِ أن العمود غير موجود — هو موجود ومُستخدم لتحليل الفجوات (gap analysis).

- ⚠️ **عندما يكون user_id في direct_search NULL** (بحث مجهول من زائر بدون حساب)،
  لا تحذف الصف بل اعرضه مع 'زائر مجهول' في عمود الاسم.
- ⚠️ البحث عن متجر/كوبون بالاسم: استخدم دائماً ILIKE مع % من الجانبين، لأن المستخدم
  قد يكتب جزء من الاسم فقط أو يخلط بين اسم المتجر ورقم/كود الكوبون.
  مثال: «كوبون نمشي5» يعني المتجر «نمشي» وكوبون احتواؤه «5»، فابحث:
    SELECT store_id, public_coupon, last_time, total_coupon_copies, total_link_clicks, is_trending
    FROM master
    WHERE (store_id ILIKE '%' || '<اسم>' || '%' OR name_en ILIKE '%' || '<اسم>' || '%'
           OR public_coupon ILIKE '%' || '<كل المدخل>' || '%')
    ORDER BY last_time DESC NULLS LAST
    LIMIT 20
  لو ما طلع نتائج بالأكواد، ابحث بالـ store_id فقط واعرض كل كوبونات المتجر.
- ⚠️ «متى ينتهي الكوبون» = master.last_time (تاريخ آخر صلاحية للكوبون الحالي).
- ⚠️ لتصنيف الكوبون (فعّال/منتهي/قريب الانتهاء):
    'فعّال'         إذا last_time > CURRENT_DATE + 3
    'قريب الانتهاء' إذا last_time BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
    'منتهي'         إذا last_time < CURRENT_DATE
"""

        # عرض سجل المحادثة
        for _idx, _msg in enumerate(st.session_state["ai_users_history"]):
            with st.chat_message(_msg["role"]):
                st.markdown(_msg["content"])
                if _msg.get("sql"):
                    with st.expander("🔍 الاستعلام المُستخدم"):
                        st.code(_msg["sql"], language="sql")
                _df_hist = _msg.get("df")
                if _df_hist is not None and not _df_hist.empty:
                    st.dataframe(_df_hist, width="stretch", hide_index=True)
                    _dl1, _dl2 = st.columns(2)
                    with _dl1:
                        st.download_button(
                            "⬇️ تحميل CSV",
                            data=_df_hist.to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"ai_query_{_idx}.csv",
                            mime="text/csv",
                            key=f"ai_dl_csv_h_{_idx}",
                            width="stretch",
                        )
                    with _dl2:
                        _xbuf = BytesIO()
                        with pd.ExcelWriter(_xbuf, engine="xlsxwriter") as _xw:
                            _df_hist.to_excel(_xw, sheet_name="result", index=False)
                        st.download_button(
                            "⬇️ تحميل Excel",
                            data=_xbuf.getvalue(),
                            file_name=f"ai_query_{_idx}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"ai_dl_xlsx_h_{_idx}",
                            width="stretch",
                        )

        if st.session_state["ai_users_history"]:
            if st.button("🗑️ مسح المحادثة", key="ai_users_clear"):
                st.session_state["ai_users_history"] = []
                st.rerun()

        # ── ذاكرة الجلسة: أمثلة ناجحة + سجل أخطاء (تعليم ذاتي) ──────────
        if "ai_success_examples" not in st.session_state:
            st.session_state["ai_success_examples"] = []  # [{q, sql}]
        if "ai_error_log" not in st.session_state:
            st.session_state["ai_error_log"] = []  # [{sql, error}]

        # ── دالة AI موحّدة: Groq أساسي + Gemini احتياطي (الاثنين مجاني) ──
        def _ai_chat(
            system: str,
            messages: list[dict],
            temperature: float = 0.1,
            max_tokens: int = 900,
        ) -> tuple[str | None, str | None]:
            """
            يستدعي Groq أولاً (سريع وحدّه اليومي 100K توكن — يكفي مع ضغط المخطط).
            احتياطياً Gemini عند فشل/تجاوز حد Groq.
            messages بصيغة OpenAI: [{role: 'user'|'assistant', content: str}, ...]
            يرجّع (content, error).
            """
            import time as _time
            groq_key = os.getenv("GROQ_API_KEY")
            gemini_key = os.getenv("GEMINI_API_KEY")

            def _call_groq() -> tuple[str | None, str | None]:
                model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
                _payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": system}] + messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                _last = None
                for attempt, delay in enumerate([0, 1, 2]):
                    if delay > 0:
                        _time.sleep(delay)
                    try:
                        r = requests.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {groq_key}",
                                     "Content-Type": "application/json"},
                            json=_payload, timeout=60,
                        )
                    except Exception as e:
                        _last = f"Groq شبكة: {e}"
                        continue
                    if r.status_code == 429:
                        return None, "GROQ_429"
                    if r.status_code >= 400:
                        return None, f"Groq HTTP {r.status_code}: {r.text[:200]}"
                    try:
                        return r.json()["choices"][0]["message"]["content"], None
                    except Exception as e:
                        return None, f"Groq parsing: {e}"
                return None, _last or "Groq فشل."

            def _call_gemini() -> tuple[str | None, str | None]:
                model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                contents = []
                for m in messages:
                    role = "user" if m["role"] == "user" else "model"
                    contents.append({"role": role,
                                     "parts": [{"text": m["content"]}]})
                _payload = {
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": contents,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max(max_tokens, 2048),
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                }
                _url = (f"https://generativelanguage.googleapis.com/v1beta/"
                        f"models/{model}:generateContent?key={gemini_key}")
                _last = None
                for attempt, delay in enumerate([0, 1, 2, 4]):
                    if delay > 0:
                        _time.sleep(delay)
                    try:
                        r = requests.post(
                            _url,
                            headers={"Content-Type": "application/json"},
                            json=_payload, timeout=60,
                        )
                    except Exception as e:
                        _last = f"Gemini شبكة: {e}"
                        continue
                    if r.status_code in (429, 503):
                        _last = ("🌐 سيرفرات Gemini مزدحمة. "
                                 if r.status_code == 503
                                 else "⏱️ Gemini Rate Limit. "
                                 ) + f"محاولة {attempt + 1}."
                        continue
                    if r.status_code >= 400:
                        return None, f"Gemini HTTP {r.status_code}: {r.text[:200]}"
                    try:
                        data = r.json()
                        cands = data.get("candidates") or []
                        if not cands:
                            return None, "Gemini رد فارغ."
                        parts = cands[0].get("content", {}).get("parts", []) or []
                        txt = "".join(p.get("text", "") for p in parts).strip()
                        if txt:
                            return txt, None
                        finish = cands[0].get("finishReason", "UNKNOWN")
                        return None, f"Gemini نص فارغ ({finish})."
                    except Exception as e:
                        return None, f"Gemini parsing: {e}"
                return None, _last or "Gemini فشل."

            # محاولة Groq أولاً (سريع)
            if groq_key:
                content, err = _call_groq()
                if content:
                    return content, None
                # عند تجاوز حد Groq اليومي → نتحوّل Gemini تلقائياً
                if err == "GROQ_429" and gemini_key:
                    return _call_gemini()
                # أخطاء أخرى من Groq وفي Gemini → جرّب
                if gemini_key:
                    content2, err2 = _call_gemini()
                    if content2:
                        return content2, None
                    return None, f"{err} | {err2}"
                if err == "GROQ_429":
                    return None, ("⏱️ تجاوزت حد Groq اليومي ولا يوجد GEMINI_API_KEY.\n"
                                  "• ينتظر إعادة تعيين تلقائية خلال 24 ساعة.\n"
                                  "• أو أضف GEMINI_API_KEY (مجاني) من https://aistudio.google.com/apikey")
                return None, err
            # ما عندنا Groq → Gemini فقط
            if gemini_key:
                return _call_gemini()
            return None, ("❌ لا يوجد مفتاح AI مجاني مضبوط.\n"
                          "أضف أحدهما (أو كليهما) في Railway → Variables:\n"
                          "• `GROQ_API_KEY` (سريع) — https://console.groq.com\n"
                          "• `GEMINI_API_KEY` (مرن) — https://aistudio.google.com/apikey")

        def _ai_build_few_shot() -> str:
            """يبني أمثلة few-shot من الاستعلامات الناجحة في الجلسة."""
            ex = st.session_state.get("ai_success_examples", [])
            if not ex:
                return ""
            out = ["===== أمثلة ناجحة سابقة في هذه الجلسة (اقتدِ بها) ====="]
            for i, e in enumerate(ex[-5:], 1):
                out.append(f"\nمثال {i}:\nالسؤال: {e['q']}\n"
                           f"```sql\n{e['sql']}\n```")
            return "\n".join(out) + "\n"

        def _ai_users_gen_sql(
            question: str,
            previous_attempts: list[dict] | None = None,
        ) -> tuple[str | None, str | None]:
            """
            يطلب من النموذج (Gemini → Groq) توليد SELECT آمن، ويرجّع (sql, error).
            previous_attempts: لو فيه محاولات فاشلة سابقة، يمررها للنموذج
            مع رسائل أخطاء PostgreSQL ليتعلم منها ويصحح.
            """
            _live_schema = _ai_get_full_schema()
            _few_shot = _ai_build_few_shot()
            system = (
                "أنت محرّر SQL لقاعدة PostgreSQL لمنصة DealPulse KSA. "
                "لديك صلاحية قراءة كاملة على كل جداول وأعمدة المخطط أدناه.\n"
                "قواعد صارمة (المخالفة = فشل):\n"
                "- SELECT فقط (ممنوع INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE).\n"
                "- استعلام واحد فقط بدون ; في المنتصف.\n"
                "- ممنوع اختراع جداول أو أعمدة. استخدم فقط ما هو موجود حرفياً في المخطط.\n"
                "- ممنوع إرجاع قيم نصية ثابتة كإجابة (مثل SELECT 'جيد'). "
                "يجب أن تأتي كل قيمة من الجداول.\n"
                "- إذا كان السؤال غامضاً (مثل «قيّم المشروع» أو «وش ينقصه») "
                "أو لا يمكن الإجابة عنه من المخطط، أرجع حرفياً السطر التالي بدون شيء آخر:\n"
                "  UNCLEAR: <سبب قصير بالعربي يوضّح اللازم من المستخدم>\n"
                "- إذا كان السؤال واضحاً، أرجع الاستعلام داخل ```sql … ``` فقط.\n"
                "- استخدم LIMIT 100 افتراضياً للنتائج الكبيرة.\n"
                "- أسماء الـ aliases بالإنجليزية فقط.\n"
                "- التواريخ بـ CURRENT_DATE / CURRENT_TIMESTAMP / INTERVAL.\n"
                "- لو قُدّمت لك محاولات سابقة فاشلة مع أخطاء PostgreSQL، "
                "حلّل الخطأ بدقة وصحّح الاستعلام (مثلاً: اسم عمود غير موجود → "
                "استبدله بالعمود الصحيح من المخطط؛ نوع لا يطابق → استخدم CAST؛ "
                "خطأ ربط → راجع شرط JOIN).\n\n"
                "===== المخطط الكامل (من information_schema) =====\n"
                f"{_live_schema}\n\n"
                f"===== ملاحظات منطقية =====\n{_AI_DB_HINTS}\n"
                f"{_few_shot}"
            )
            messages: list[dict] = []
            if previous_attempts:
                messages.append({"role": "user", "content": question})
                for att in previous_attempts:
                    messages.append({
                        "role": "assistant",
                        "content": f"```sql\n{att['sql']}\n```",
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            f"❌ فشل تنفيذ الاستعلام أعلاه. خطأ PostgreSQL:\n"
                            f"{att['error']}\n\n"
                            f"حلّل الخطأ بدقة وأعد كتابة الاستعلام بشكل صحيح. "
                            f"لا تكرر نفس الغلط. أرجع الاستعلام الجديد داخل "
                            f"```sql … ``` فقط."
                        ),
                    })
            else:
                messages.append({"role": "user", "content": question})

            content, err = _ai_chat(system, messages, temperature=0.1, max_tokens=900)
            if err or not content:
                return None, err or "النموذج رجّع رد فارغ."

            _stripped = content.strip()
            if _stripped.upper().startswith("UNCLEAR"):
                _reason = _stripped.split(":", 1)[1].strip() if ":" in _stripped else ""
                return None, ("🤔 السؤال غير واضح. "
                              + (_reason or "صياغ السؤال بشكل أوضح من فضلك.")
                              + "\n\nأمثلة على أسئلة واضحة:\n"
                              "• «كم مستخدم سجّل في آخر 7 أيام؟»\n"
                              "• «أكثر 10 متاجر تم نسخ كوبوناتها هذا الشهر»\n"
                              "• «كم بحث ما لقى نتيجة بالأسبوع الماضي؟»")
            import re as _re
            sql = None
            # 1) نحاول استخراج بلوك ```sql ... ``` أولاً
            m = _re.search(r"```sql\s*(.+?)\s*```", content,
                           _re.DOTALL | _re.IGNORECASE)
            if m:
                sql = m.group(1).strip()
            else:
                # 2) أو أي بلوك ``` ... ``` يحوي SELECT/WITH
                m2 = _re.search(r"```\s*((?:SELECT|WITH)\b.+?)```", content,
                                _re.DOTALL | _re.IGNORECASE)
                if m2:
                    sql = m2.group(1).strip()
                else:
                    # 3) آخر محاولة: نلتقط أول SELECT/WITH في النص حتى نهاية الكلام
                    m3 = _re.search(r"(?:^|\n)\s*((?:SELECT|WITH)\b[\s\S]+)",
                                    content, _re.IGNORECASE)
                    if m3:
                        sql = m3.group(1).strip()
                        # نقطع عند backticks أو خطوط شرح بعد الاستعلام
                        sql = _re.split(r"\n\s*(?:```|--\s*شرح|الشرح:|ملاحظة)",
                                        sql, maxsplit=1)[0].strip()
            if not sql:
                # ما قدرنا نلقى أي SQL — لا داعي للرفض إذا الرد نفسه نص عادي
                return None, ("النموذج ما رجّع استعلام SQL واضح. "
                              "صياغ السؤال بصورة أوضح من فضلك.\n\n"
                              f"رد النموذج: {content[:200]}")
            sql = sql.rstrip(";").strip()
            low = sql.lower().lstrip()
            if not (low.startswith("select") or low.startswith("with")):
                return None, ("النموذج رجّع استعلام غير SELECT — تم رفضه.\n"
                              f"بداية الاستعلام: {sql[:120]}")
            _forbidden = ("insert ", "update ", "delete ", "drop ", "alter ",
                          "truncate ", "grant ", "revoke ", "create ", ";")
            for f in _forbidden:
                if f in low:
                    return None, f"الاستعلام يحتوي على كلمة محظورة: {f.strip()!r}"
            return sql, None

        def _ai_users_summarize(question: str, sql: str, df: pd.DataFrame) -> str:
            """ملخص عربي بسيط للنتائج عبر النموذج الموحّد (Gemini → Groq)."""
            preview = df.head(30).to_dict(orient="records")
            system = (
                "أنت محلّل بيانات لمنصة DealPulse KSA. تلخّص نتائج SQL "
                "بإجابة عربية مختصرة ومباشرة (٢-٤ أسطر) مع ذكر الأرقام المهمة. "
                "لا تُكرّر الجدول، فقط الخلاصة والرؤية."
            )
            user_msg = (
                f"السؤال: {question}\n"
                f"الاستعلام:\n```sql\n{sql}\n```\n"
                f"النتائج ({len(df)} صف، عيّنة أول 30):\n```json\n"
                f"{json.dumps(preview, ensure_ascii=False, default=str)}\n```"
            )
            content, err = _ai_chat(
                system,
                [{"role": "user", "content": user_msg}],
                temperature=0.3, max_tokens=600,
            )
            if err or not content:
                return f"(تعذّر التلخيص — {err or 'رد فارغ'})"
            return content

        _MAX_AI_RETRIES = 2  # محاولات إضافية بعد المحاولة الأولى = إجمالي 3
        _ai_q = st.chat_input("اكتب سؤالك عن المستخدمين…")
        if _ai_q:
            st.session_state["ai_users_history"].append(
                {"role": "user", "content": _ai_q})
            with st.chat_message("user"):
                st.markdown(_ai_q)
            with st.chat_message("assistant"):
                _attempts: list[dict] = []   # [{sql, error}] لتعليم النموذج
                _ai_df = None
                _ai_sql = None
                _final_gen_err = None

                for _retry in range(_MAX_AI_RETRIES + 1):
                    _spinner_text = ("⌛ يكتب الاستعلام…" if _retry == 0
                                     else f"🔧 يتعلّم من الخطأ ويصحّح (محاولة {_retry + 1})…")
                    with st.spinner(_spinner_text):
                        _ai_sql, _gen_err = _ai_users_gen_sql(
                            _ai_q,
                            previous_attempts=_attempts if _attempts else None,
                        )
                    if _gen_err:
                        _final_gen_err = _gen_err
                        break
                    try:
                        _conn_ai = get_conn()
                        _conn_ai.autocommit = True
                        _ai_df = pd.read_sql(_ai_sql, _conn_ai)
                        _conn_ai.close()
                        break  # نجح
                    except Exception as e:
                        _err_str = str(e)
                        _attempts.append({"sql": _ai_sql, "error": _err_str})
                        st.session_state["ai_error_log"].append({
                            "q": _ai_q, "sql": _ai_sql, "error": _err_str,
                        })
                        _ai_df = None  # نواصل للمحاولة التالية

                if _final_gen_err:
                    st.error(_final_gen_err)
                    st.session_state["ai_users_history"].append(
                        {"role": "assistant", "content": f"❌ {_final_gen_err}"})
                elif _ai_df is None:
                    # كل المحاولات فشلت
                    _last = _attempts[-1] if _attempts else {"sql": "—", "error": "—"}
                    _msg_fail = (
                        f"❌ تعذّر تنفيذ الاستعلام بعد {len(_attempts)} محاولات. "
                        f"آخر خطأ:\n`{_last['error']}`"
                    )
                    st.error(_msg_fail)
                    with st.expander(f"🔍 المحاولات ({len(_attempts)})"):
                        for _i, _att in enumerate(_attempts, 1):
                            st.markdown(f"**المحاولة {_i}:**")
                            st.code(_att["sql"], language="sql")
                            st.caption(f"خطأ: {_att['error']}")
                    st.session_state["ai_users_history"].append({
                        "role": "assistant", "content": _msg_fail,
                        "sql": _last["sql"],
                    })
                else:
                    # نجاح → احفظ كمثال للجلسة، لخّص، اعرض
                    st.session_state["ai_success_examples"].append(
                        {"q": _ai_q, "sql": _ai_sql})
                    if len(_attempts) > 0:
                        st.success(f"✅ نجح بعد {len(_attempts) + 1} محاولات (تعلّم من الأخطاء).")
                    with st.spinner("📊 يحلّل النتائج…"):
                        _ai_summary = _ai_users_summarize(_ai_q, _ai_sql, _ai_df)
                    st.markdown(_ai_summary)
                    with st.expander("🔍 الاستعلام المُستخدم"):
                        st.code(_ai_sql, language="sql")
                        if _attempts:
                            st.caption(f"تم تصحيح {len(_attempts)} محاولة قبل النجاح.")
                    if not _ai_df.empty:
                        st.dataframe(_ai_df, width="stretch",
                                     hide_index=True)
                        _live_idx = len(st.session_state["ai_users_history"])
                        _ldl1, _ldl2 = st.columns(2)
                        with _ldl1:
                            st.download_button(
                                "⬇️ تحميل CSV",
                                data=_ai_df.to_csv(index=False).encode("utf-8-sig"),
                                file_name=f"ai_query_{_live_idx}.csv",
                                mime="text/csv",
                                key=f"ai_dl_csv_live_{_live_idx}",
                                width="stretch",
                            )
                        with _ldl2:
                            _lxbuf = BytesIO()
                            with pd.ExcelWriter(_lxbuf, engine="xlsxwriter") as _lxw:
                                _ai_df.to_excel(_lxw, sheet_name="result", index=False)
                            st.download_button(
                                "⬇️ تحميل Excel",
                                data=_lxbuf.getvalue(),
                                file_name=f"ai_query_{_live_idx}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"ai_dl_xlsx_live_{_live_idx}",
                                width="stretch",
                            )
                    st.session_state["ai_users_history"].append({
                        "role": "assistant", "content": _ai_summary,
                        "sql": _ai_sql, "df": _ai_df,
                    })

# ════════════════════════════════════════════════════════════════════════════
# صفحة 🎯 بناء الشرائح (Segment Builder)
# قواعد Attribute/Event/Aggregate/Temporal، تركيب AND/OR على مجموعات،
# عدّاد حي، معاينة، حفظ/تحميل شرائح. كامل عبر api.audience_engine.
# ════════════════════════════════════════════════════════════════════════════
elif page == "🎯 بناء الشرائح":
    page_title("🎯", "محرّر الشرائح المتقدّم")

    from api import audience_engine as _ae

    # ── حالة الجلسة ────────────────────────────────────────────────────────
    if "seg_rules" not in st.session_state:
        st.session_state.seg_rules = {
            "version": 1, "logic": "or",
            "groups": [{"logic": "and", "rules": []}],
        }
    if "seg_meta" not in st.session_state:
        st.session_state.seg_meta = {"id": None, "name": "", "description": "",
                                     "channel": "both"}

    @st.cache_data(ttl=300)
    def _ae_stores():
        with get_conn() as _c:
            _c.autocommit = True
            return _ae.list_stores(_c)

    @st.cache_data(ttl=300)
    def _ae_categories():
        with get_conn() as _c:
            _c.autocommit = True
            return _ae.list_categories(_c)

    @st.cache_data(ttl=300)
    def _ae_cities():
        with get_conn() as _c:
            _c.autocommit = True
            return _ae.list_cities(_c)

    _STORES     = _ae_stores()
    _CATEGORIES = _ae_categories()
    _CITIES     = _ae_cities()

    # ── شريط علوي: تحميل/جديد/حذف ─────────────────────────────────────────
    try:
        with get_conn() as _conn_top:
            _conn_top.autocommit = True
            _user_segs  = _ae.list_user_segments(_conn_top)
            _templates  = _ae.list_templates(_conn_top)
    except Exception as _e:
        _user_segs = []
        _templates = []
        st.warning(f"تعذّر تحميل الشرائح: {_e}")

    # ── القوالب الجاهزة ───────────────────────────────────────────────────
    with st.expander(f"📋 ابدأ من قالب ({len(_templates)} قالب جاهز)",
                     expanded=False):
        st.caption("اضغط «تطبيق» → القالب يصير شريحتك الحالية. عدّلها واحفظها باسم جديد.")
        for _tpl in _templates:
            _tc1, _tc2, _tc3 = st.columns([3, 4, 1])
            with _tc1:
                st.markdown(f"**{_tpl['name']}**")
            with _tc2:
                st.caption(_tpl.get("description") or "—")
            with _tc3:
                if st.button("⚡ تطبيق", key=f"tpl_apply_{_tpl['id']}",
                             width="stretch"):
                    st.session_state.seg_rules = _tpl["rules_json"]
                    st.session_state.seg_meta = {
                        "id": None,    # قالب → شريحة جديدة بعد التطبيق
                        "name": _tpl["name"].replace("[عدّل المتجر]","")
                                            .replace("[عدّل القسم]","").strip(),
                        "description": _tpl.get("description") or "",
                        "channel": _tpl.get("channel") or "both",
                    }
                    st.rerun()

    _col_load, _col_new, _col_del = st.columns([3, 1, 1])
    with _col_load:
        _opts = ["— شريحة جديدة —"] + [f"#{s['id']} · {s['name']}" for s in _user_segs]
        _sel = st.selectbox("📚 شرائحي المحفوظة:", _opts, key="seg_load_sel")
        if _sel != "— شريحة جديدة —" and st.button("📥 حمّل المختارة", key="seg_load_btn"):
            _sid = int(_sel.split("·")[0].strip().lstrip("#"))
            with get_conn() as _c:
                _c.autocommit = True
                _loaded = _ae.load_segment(_c, _sid)
            if _loaded:
                st.session_state.seg_rules = _loaded["rules_json"]
                st.session_state.seg_meta = {
                    "id": _loaded["id"], "name": _loaded["name"],
                    "description": _loaded.get("description") or "",
                    "channel": _loaded.get("channel") or "both",
                }
                st.rerun()
    with _col_new:
        if st.button("🆕 شريحة جديدة", key="seg_new_btn", width="stretch"):
            st.session_state.seg_rules = {
                "version": 1, "logic": "or",
                "groups": [{"logic": "and", "rules": []}],
            }
            st.session_state.seg_meta = {"id": None, "name": "",
                                         "description": "", "channel": "both"}
            st.rerun()
    with _col_del:
        if (st.session_state.seg_meta.get("id")
                and st.button("🗑️ احذف", key="seg_del_btn",
                              width="stretch", type="secondary")):
            with get_conn() as _c:
                _c.autocommit = True
                _ae.delete_segment(_c, st.session_state.seg_meta["id"])
            st.success("حُذفت الشريحة.")
            st.session_state.seg_rules = {"version": 1, "logic": "or",
                                          "groups": [{"logic": "and", "rules": []}]}
            st.session_state.seg_meta = {"id": None, "name": "",
                                         "description": "", "channel": "both"}
            st.rerun()

    # ── بيانات الشريحة (اسم، وصف، قناة) ────────────────────────────────────
    _meta_c1, _meta_c2, _meta_c3 = st.columns([2, 3, 1])
    with _meta_c1:
        st.session_state.seg_meta["name"] = st.text_input(
            "📝 اسم الشريحة:", st.session_state.seg_meta.get("name", ""),
            key="seg_name_in", placeholder="مثلاً: VIP نون")
    with _meta_c2:
        st.session_state.seg_meta["description"] = st.text_input(
            "ℹ️ وصف مختصر:", st.session_state.seg_meta.get("description", ""),
            key="seg_desc_in", placeholder="من نسخوا كوبون نون 3 مرات آخر شهر")
    with _meta_c3:
        _channels = ["both", "telegram", "email"]
        _ch_labels = {"both": "📡 الكل", "telegram": "📱 تليجرام", "email": "📧 إيميل"}
        _cur_ch = st.session_state.seg_meta.get("channel") or "both"
        st.session_state.seg_meta["channel"] = st.selectbox(
            "🎯 القناة:", _channels,
            index=_channels.index(_cur_ch) if _cur_ch in _channels else 0,
            format_func=lambda x: _ch_labels[x], key="seg_ch_in")

    st.divider()

    # ── ثوابت العرض ────────────────────────────────────────────────────────
    _ATTR_FIELDS = {
        "lang":              "🌐 اللغة",
        "gender":            "⚧ الجنس",
        "age":               "🎂 العمر",
        "city":              "📍 المدينة",
        "profile_complete":  "✅ اكتمال الملف (يوزر + إيميل + جوال + ميلاد + جنس)",
        "is_linked":         "🔗 ملف مربوط (موقع + تليجرام)",
        "has_email":         "📧 له إيميل",
        "has_phone":         "📱 له جوال",
        "has_birth_date":    "🎂 له تاريخ ميلاد",
        "favorite_store":    "❤️ مفضّل متجر محدد",
        "favorite_category": "🏷️ مفضّل قسم محدد",
        "fav_count":         "🔢 عدد مفضّلاته",
    }
    _ACTIONS_LABELS = {
        "copy_coupon":    "🎟️ نسخ كوبون",
        "click_link":     "🖱️ نقر رابط",
        "search":         "🔍 بحث",
        "view_store":     "👁️ زيارة بطاقة متجر",
        "view_tag":       "🏷️ زيارة قسم",
        "view_story":     "🎬 شاف ستوري (مستقل)",
        "search_keyword": "🔎 بحث عن كلمة محددة",
    }
    _CONTEXT_LABELS = {
        "any":          "أي سياق",
        "trend_daily":  "🔥 من ترند يومي",
        "trend_weekly": "🔥 من ترند أسبوعي",
        "trend_any":    "🔥 من أي ترند",
        "story":        "🎬 من سياق ستوري",
        "card":         "🃏 من بطاقة عادية",
    }
    _OPS_LABELS = {
        "=": "=", "!=": "≠", ">": ">", ">=": "≥", "<": "<", "<=": "≤",
        "between": "بين", "in": "ضمن قائمة",
    }
    _THRESHOLD_LABELS = {
        "absolute":         "مطلق (رقم)",
        "percentile_top":   "أعلى N%",
        "percentile_bot":   "أقل N%",
        "top_n":            "أعلى N شخصاً",
        "above_mean":       "أعلى من المتوسط",
        "below_mean":       "أقل من المتوسط",
    }

    def _render_attribute_rule(rule: dict, key: str):
        """يعرض ويحدّث قاعدة attribute في مكانها."""
        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            fld = st.selectbox("الحقل", list(_ATTR_FIELDS.keys()),
                index=list(_ATTR_FIELDS.keys()).index(rule.get("field","lang"))
                      if rule.get("field") in _ATTR_FIELDS else 0,
                format_func=lambda x: _ATTR_FIELDS[x], key=f"{key}_f")
            rule["field"] = fld

        with c2:
            if fld in ("is_linked","has_email","has_phone","has_birth_date","profile_complete"):
                rule["op"] = "="
                yn = st.selectbox("القيمة", ["نعم","لا"],
                    index=0 if rule.get("value", True) else 1, key=f"{key}_v")
                rule["value"] = (yn == "نعم")
            elif fld == "age":
                ops = ["=","!=","<",">","<=",">=","between"]
                rule["op"] = st.selectbox("العملية", ops,
                    index=ops.index(rule.get("op","between")) if rule.get("op") in ops else 6,
                    format_func=lambda x: _OPS_LABELS[x], key=f"{key}_op")
            elif fld == "fav_count":
                ops = ["=","!=","<",">","<=",">="]
                rule["op"] = st.selectbox("العملية", ops,
                    index=ops.index(rule.get("op",">=")) if rule.get("op") in ops else 5,
                    format_func=lambda x: _OPS_LABELS[x], key=f"{key}_op")
            else:
                ops = ["=","!="]
                rule["op"] = st.selectbox("العملية", ops,
                    index=ops.index(rule.get("op","=")) if rule.get("op") in ops else 0,
                    format_func=lambda x: _OPS_LABELS[x], key=f"{key}_op")

        with c3:
            if fld in ("is_linked","has_email","has_phone","has_birth_date","profile_complete"):
                st.caption("القيمة بوليانية أعلاه ☝️")
            elif fld == "lang":
                langs = ["ar","en"]
                rule["value"] = st.selectbox("اللغة", langs,
                    index=langs.index(rule.get("value","ar")) if rule.get("value") in langs else 0,
                    key=f"{key}_v")
            elif fld == "gender":
                gs = ["male","female"]
                rule["value"] = st.selectbox("الجنس", gs,
                    index=gs.index(rule.get("value","male")) if rule.get("value") in gs else 0,
                    format_func=lambda x: "♂️ ذكر" if x=="male" else "♀️ أنثى",
                    key=f"{key}_v")
            elif fld == "city":
                opts = _CITIES or ["—"]
                rule["value"] = st.selectbox("المدينة", opts,
                    index=opts.index(rule["value"]) if rule.get("value") in opts else 0,
                    key=f"{key}_v")
            elif fld == "favorite_store":
                opts = _STORES or ["—"]
                rule["value"] = st.selectbox("المتجر", opts,
                    index=opts.index(rule["value"]) if rule.get("value") in opts else 0,
                    key=f"{key}_v")
            elif fld == "favorite_category":
                opts = _CATEGORIES or ["—"]
                rule["value"] = st.selectbox("القسم", opts,
                    index=opts.index(rule["value"]) if rule.get("value") in opts else 0,
                    key=f"{key}_v")
            elif fld == "age":
                if rule.get("op") == "between":
                    _raw = rule.get("value") if isinstance(rule.get("value"),
                                                            (list,tuple)) else [18,34]
                    try: v1 = int(_raw[0])
                    except (ValueError, TypeError, IndexError): v1 = 18
                    try: v2 = int(_raw[1])
                    except (ValueError, TypeError, IndexError): v2 = 34
                    cc1, cc2 = st.columns(2)
                    v1 = cc1.number_input("من", min_value=0, max_value=120,
                                          value=v1, key=f"{key}_v1")
                    v2 = cc2.number_input("إلى", min_value=0, max_value=120,
                                          value=v2, key=f"{key}_v2")
                    rule["value"] = [int(v1), int(v2)]
                else:
                    try: _age = int(rule.get("value", 25) or 25)
                    except (ValueError, TypeError): _age = 25
                    rule["value"] = st.number_input("العمر", min_value=0,
                        max_value=120, value=_age, key=f"{key}_v")
            elif fld == "fav_count":
                try: _cnt = int(rule.get("value", 1) or 1)
                except (ValueError, TypeError): _cnt = 1
                rule["value"] = st.number_input("العدد", min_value=0,
                    value=_cnt, key=f"{key}_v")

    # ── أنماط الترند والستوري الجاهزة (مفاتيح ↔ (action, context, was_trending)) ─
    # عند اختيار نمط، نُملي الحقول المعنية تلقائياً، لكن باقي الحقول (النافذة،
    # المتجر، القسم، الساعة...) تبقى ظاهرة وقابلة للتعديل اليدوي. الـpreset
    # ما يُحفظ في الـDB — يُستنتج عند إعادة العرض من تركيبة action+context+was_trending.
    _EVENT_PRESETS = {
        "custom":              ("— مخصّص (يدوي) —",       None,             None,           None),
        "all":                 ("🌐 الكل (أي تفاعل · أي سياق)", "copy_coupon", "any",         None),
        "copy_trend_daily":    ("🎟️🔥 نسخ كوبون من ترند يومي",  "copy_coupon",  "trend_daily",  None),
        "copy_trend_weekly":   ("🎟️🔥 نسخ كوبون من ترند أسبوعي", "copy_coupon",  "trend_weekly", None),
        "copy_trend_any":      ("🎟️🔥 نسخ كوبون من أي ترند",    "copy_coupon",  "trend_any",    None),
        "click_trend_daily":   ("🖱️🔥 نقر رابط من ترند يومي",   "click_link",   "trend_daily",  None),
        "click_trend_weekly":  ("🖱️🔥 نقر رابط من ترند أسبوعي",  "click_link",   "trend_weekly", None),
        "click_trend_any":     ("🖱️🔥 نقر رابط من أي ترند",     "click_link",   "trend_any",    None),
        "story_trend":         ("🎬🔥 شاف ستوري لمتجر ترند",    "view_story",   None,           True),
        "story_normal":        ("🎬 شاف ستوري لمتجر عادي",     "view_story",   None,           False),
        "story_any":           ("🎬 شاف أي ستوري",            "view_story",   None,           None),
    }

    def _detect_event_preset(rule: dict) -> str:
        """يستنتج النمط من حالة الـrule الحالية لاختيار الـoption الصحيح في الـselectbox."""
        act = rule.get("action")
        ctx = rule.get("context")
        wt  = rule.get("was_trending")
        for key, (_, p_act, p_ctx, p_wt) in _EVENT_PRESETS.items():
            if key == "custom":
                continue
            if p_act == act and p_ctx == ctx and p_wt == wt:
                return key
        return "custom"

    def _render_event_rule(rule: dict, key: str):
        """يعرض ويحدّث قاعدة event."""
        # ── النمط الجاهز (اختياري) — يعبّي الحركة/السياق/نوع الستوري ────────
        preset_keys = list(_EVENT_PRESETS.keys())
        cur_preset = _detect_event_preset(rule)
        new_preset = st.selectbox(
            "🎯 نمط جاهز (اختياري — كل التفاصيل تبقى قابلة للتعديل تحت)",
            preset_keys,
            index=preset_keys.index(cur_preset),
            format_func=lambda x: _EVENT_PRESETS[x][0],
            key=f"{key}_preset",
        )
        if new_preset != cur_preset and new_preset != "custom":
            _, p_act, p_ctx, p_wt = _EVENT_PRESETS[new_preset]
            if p_act is not None: rule["action"] = p_act
            if p_ctx is not None: rule["context"] = p_ctx
            if p_wt is not None or new_preset.startswith("story_"):
                rule["was_trending"] = p_wt
            st.rerun()

        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            acts = list(_ACTIONS_LABELS.keys())
            rule["action"] = st.selectbox("الحركة", acts,
                index=acts.index(rule.get("action","copy_coupon")) if rule.get("action") in acts else 0,
                format_func=lambda x: _ACTIONS_LABELS[x], key=f"{key}_act")
        with c2:
            if rule["action"] == "search_keyword":
                rule["entity_type"] = "keyword"
                rule["entity_value"] = st.text_input("الكلمة",
                    value=rule.get("entity_value","") or "", key=f"{key}_kw")
            elif rule["action"] == "view_story":
                opts = ["الكل","ترند فقط","عادي فقط"]
                cur_wt = rule.get("was_trending")
                cur_idx = 0 if cur_wt is None else (1 if cur_wt else 2)
                sel = st.selectbox("نوع الستوري", opts,
                    index=cur_idx, key=f"{key}_wt")
                rule["was_trending"] = None if sel=="الكل" else (sel=="ترند فقط")
                rule["entity_type"] = "store"
                opts_s = ["— أي متجر —"] + (_STORES or [])
                cur_v = rule.get("entity_value") or "— أي متجر —"
                sel_s = st.selectbox("المتجر", opts_s,
                    index=opts_s.index(cur_v) if cur_v in opts_s else 0,
                    key=f"{key}_st")
                rule["entity_value"] = None if sel_s.startswith("— أي") else sel_s
            else:
                ent_opts = ["any","store","category"]
                rule["entity_type"] = st.selectbox("الهدف", ent_opts,
                    index=ent_opts.index(rule.get("entity_type","any"))
                        if rule.get("entity_type") in ent_opts else 0,
                    format_func=lambda x: {"any":"أي","store":"متجر محدد",
                                           "category":"قسم محدد"}[x],
                    key=f"{key}_ent")
                if rule["entity_type"] == "store":
                    opts = _STORES or ["—"]
                    rule["entity_value"] = st.selectbox("المتجر", opts,
                        index=opts.index(rule["entity_value"])
                            if rule.get("entity_value") in opts else 0,
                        key=f"{key}_ev")
                elif rule["entity_type"] == "category":
                    opts = _CATEGORIES or ["—"]
                    rule["entity_value"] = st.selectbox("القسم", opts,
                        index=opts.index(rule["entity_value"])
                            if rule.get("entity_value") in opts else 0,
                        key=f"{key}_ev")
                else:
                    rule["entity_value"] = None
        with c3:
            if rule["action"] != "view_story":
                ctxs = list(_CONTEXT_LABELS.keys())
                rule["context"] = st.selectbox("السياق", ctxs,
                    index=ctxs.index(rule.get("context","any")) if rule.get("context") in ctxs else 0,
                    format_func=lambda x: _CONTEXT_LABELS[x], key=f"{key}_ctx")
            # حالة المتاجر (اختياري)
            _ss_opts_ev = ["any", "active", "expiring", "expired"]
            _ss_labels_ev = {"any":"🌐 الكل", "active":"🟢 فعّالة",
                             "expiring":"⏳ قربت تنتهي (≤3 أيام)",
                             "expired":"⛔ منتهية"}
            _ev_ss = rule.get("store_status") or "any"
            _new_ev_ss = st.selectbox("🏪 حالة المتاجر",
                _ss_opts_ev,
                index=_ss_opts_ev.index(_ev_ss) if _ev_ss in _ss_opts_ev else 0,
                format_func=lambda x: _ss_labels_ev[x], key=f"{key}_ss")
            rule["store_status"] = None if _new_ev_ss == "any" else _new_ev_ss
            _render_window_picker(rule, f"{key}_w")

    # ── أنماط العداد الجاهزة: (label, action, context, threshold_type, op, value, days) ─
    # value=None → ما يُلمس (للأنماط اللي ما تحتاج رقم مثل above_mean)
    _AGG_PRESETS = {
        "custom":         ("— مخصّص (يدوي) —",                None,           None,    None,           None, None, None),
        "all":            ("🌐 الكل (أي حركة، بدون عتبة)",       "copy_coupon",  "any",   "absolute",     ">=", 1,    None),
        "vip_10_30d":     ("👑 VIP — نسخوا ≥ 10 آخر شهر",         "copy_coupon",  "any",   "absolute",     ">=", 10,   30),
        "active_5_30d":   ("🥇 جمهور نشط — نسخوا ≥ 5 آخر شهر",    "copy_coupon",  "any",   "absolute",     ">=", 5,    30),
        "top_10_pct":     ("💎 أعلى 10% نسخاً (نخبة)",            "copy_coupon",  "any",   "percentile_top",None, 10,  30),
        "top_50_users":   ("🎯 أعلى 50 شخصاً نسخاً",              "copy_coupon",  "any",   "top_n",        None, 50,   30),
        "above_mean":     ("📈 فوق المتوسط",                       "copy_coupon",  "any",   "above_mean",   None, None, 30),
        "below_mean":     ("📉 تحت المتوسط (مرشّحون لإعادة تنشيط)", "copy_coupon",  "any",   "below_mean",   None, None, 30),
        "click_5_30d":    ("🖱️ نقرات نشطة — ≥ 5 آخر شهر",          "click_link",   "any",   "absolute",     ">=", 5,    30),
        "trend_copy_3":   ("🔥 نسخوا ترند ≥ 3 آخر أسبوعين",        "copy_coupon",  "trend_any", "absolute", ">=", 3,    14),
    }

    def _detect_agg_preset(rule: dict) -> str:
        for k, (_, p_act, p_ctx, p_tt, p_op, p_v, p_d) in _AGG_PRESETS.items():
            if k == "custom":
                continue
            if (p_act == rule.get("action")
                and p_ctx == rule.get("context")
                and p_tt == rule.get("threshold_type")
                and (p_op is None or p_op == rule.get("op"))
                and (p_v is None or p_v == rule.get("value"))):
                w = rule.get("window") or {}
                if p_d is None or (w.get("type") == "last_days" and w.get("days") == p_d):
                    return k
        return "custom"

    def _render_aggregate_rule(rule: dict, key: str):
        """يعرض ويحدّث قاعدة aggregate."""
        # نمط جاهز
        preset_keys = list(_AGG_PRESETS.keys())
        cur_preset = _detect_agg_preset(rule)
        new_preset = st.selectbox(
            "🎯 نمط جاهز (اختياري — كل التفاصيل تبقى قابلة للتعديل تحت)",
            preset_keys,
            index=preset_keys.index(cur_preset),
            format_func=lambda x: _AGG_PRESETS[x][0],
            key=f"{key}_preset",
        )
        if new_preset != cur_preset and new_preset != "custom":
            _, p_act, p_ctx, p_tt, p_op, p_v, p_d = _AGG_PRESETS[new_preset]
            if p_act is not None: rule["action"] = p_act
            if p_ctx is not None: rule["context"] = p_ctx
            if p_tt  is not None: rule["threshold_type"] = p_tt
            if p_op  is not None: rule["op"] = p_op
            if p_v   is not None: rule["value"] = p_v
            if p_d   is not None: rule["window"] = {"type":"last_days","days":p_d}
            # entity_type يبقى "any" ما لم يحدّده المستخدم
            rule.setdefault("entity_type", "any")
            rule.setdefault("entity_value", None)
            st.rerun()

        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            acts = ["copy_coupon","click_link","search","view_store","view_tag"]
            rule["action"] = st.selectbox("الحركة", acts,
                index=acts.index(rule.get("action","copy_coupon")) if rule.get("action") in acts else 0,
                format_func=lambda x: _ACTIONS_LABELS[x], key=f"{key}_act")
            ent_opts = ["any","store","category"]
            rule["entity_type"] = st.selectbox("الهدف", ent_opts,
                index=ent_opts.index(rule.get("entity_type","any")) if rule.get("entity_type") in ent_opts else 0,
                format_func=lambda x: {"any":"أي","store":"متجر محدد",
                                       "category":"قسم محدد"}[x],
                key=f"{key}_ent")
            if rule["entity_type"] == "store":
                opts = _STORES or ["—"]
                rule["entity_value"] = st.selectbox("المتجر", opts,
                    index=opts.index(rule["entity_value"]) if rule.get("entity_value") in opts else 0,
                    key=f"{key}_ev")
            elif rule["entity_type"] == "category":
                opts = _CATEGORIES or ["—"]
                rule["entity_value"] = st.selectbox("القسم", opts,
                    index=opts.index(rule["entity_value"]) if rule.get("entity_value") in opts else 0,
                    key=f"{key}_ev")
            else:
                rule["entity_value"] = None
        with c2:
            ctxs = list(_CONTEXT_LABELS.keys())
            rule["context"] = st.selectbox("السياق", ctxs,
                index=ctxs.index(rule.get("context","any")) if rule.get("context") in ctxs else 0,
                format_func=lambda x: _CONTEXT_LABELS[x], key=f"{key}_ctx")
            ths = list(_THRESHOLD_LABELS.keys())
            rule["threshold_type"] = st.selectbox("نوع العتبة", ths,
                index=ths.index(rule.get("threshold_type","absolute")) if rule.get("threshold_type") in ths else 0,
                format_func=lambda x: _THRESHOLD_LABELS[x], key=f"{key}_tt")
            # حالة المتاجر (اختياري)
            _ss_opts_ag = ["any", "active", "expiring", "expired"]
            _ss_labels_ag = {"any":"🌐 الكل", "active":"🟢 فعّالة",
                             "expiring":"⏳ قربت تنتهي (≤3 أيام)",
                             "expired":"⛔ منتهية"}
            _ag_ss = rule.get("store_status") or "any"
            _new_ag_ss = st.selectbox("🏪 حالة المتاجر",
                _ss_opts_ag,
                index=_ss_opts_ag.index(_ag_ss) if _ag_ss in _ss_opts_ag else 0,
                format_func=lambda x: _ss_labels_ag[x], key=f"{key}_ss")
            rule["store_status"] = None if _new_ag_ss == "any" else _new_ag_ss
        with c3:
            def _safe_int(v, default):
                try: return int(v if v not in (None, "") else default)
                except (ValueError, TypeError): return default
            if rule["threshold_type"] == "absolute":
                ops = ["=","!=","<",">","<=",">="]
                rule["op"] = st.selectbox("العملية", ops,
                    index=ops.index(rule.get("op",">=")) if rule.get("op") in ops else 5,
                    format_func=lambda x: _OPS_LABELS[x], key=f"{key}_op")
                rule["value"] = st.number_input("العدد", min_value=0,
                    value=_safe_int(rule.get("value"), 3), key=f"{key}_v")
            elif rule["threshold_type"] in ("percentile_top","percentile_bot"):
                rule["value"] = st.number_input("النسبة %", min_value=1, max_value=100,
                    value=_safe_int(rule.get("value"), 10), key=f"{key}_v")
            elif rule["threshold_type"] == "top_n":
                rule["value"] = st.number_input("عدد الأشخاص N", min_value=1,
                    value=_safe_int(rule.get("value"), 100), key=f"{key}_v")
            else:
                st.caption("بدون قيمة (المقارنة بالمتوسط)")
            _render_window_picker(rule, f"{key}_w")

    # ── أنماط الزمن الجاهزة (مفتاح ↔ (label, field, op, value_days)) ────
    # يعبّي الحقول الثلاث تلقائياً ويظلّ المستخدم قادر على تعديل أي شيء بعدها.
    _TEMPORAL_PRESETS = {
        "custom":       ("— مخصّص (يدوي) —",                      None,        None,   None),
        "all":          ("🌐 الكل (بدون قيد زمني)",                "last_seen", ">=",   3650),
        "active":       ("🟢 نشط (شُوهد آخر 20 يوم)",              "last_seen", ">=",   20),
        "active_7":     ("🟢 نشط جداً (شُوهد آخر 7 أيام)",         "last_seen", ">=",   7),
        "idle":         ("😴 خامل (لم يُشاهد منذ 20+ يوم)",        "last_seen", "<=",   20),
        "idle_60":      ("😴 خامل بعيد (لم يُشاهد منذ 60+ يوم)",   "last_seen", "<=",   60),
        "new_7":        ("🆕 جديد (انضم آخر 7 أيام)",             "joined_at", ">=",   7),
        "new_30":       ("🆕 جديد (انضم آخر 30 يوم)",             "joined_at", ">=",   30),
        "veteran_90":   ("🌟 قديم (انضم قبل 90+ يوم)",            "joined_at", "<=",   90),
    }

    def _detect_temporal_preset(rule: dict) -> str:
        fld = rule.get("field")
        op  = rule.get("op")
        try: vd = int(rule.get("value_days") or 0)
        except (ValueError, TypeError): vd = 0
        for k, (_, p_f, p_o, p_v) in _TEMPORAL_PRESETS.items():
            if k == "custom":
                continue
            if p_f == fld and p_o == op and p_v == vd:
                return k
        return "custom"

    def _render_temporal_rule(rule: dict, key: str):
        """يعرض ويحدّث قاعدة temporal."""
        # نمط جاهز (اختياري) — يعبّي الحقول الثلاث ويبقى كل شيء قابل للتعديل
        preset_keys = list(_TEMPORAL_PRESETS.keys())
        cur_preset = _detect_temporal_preset(rule)
        new_preset = st.selectbox(
            "🎯 نمط جاهز (اختياري — كل الحقول تبقى قابلة للتعديل تحت)",
            preset_keys,
            index=preset_keys.index(cur_preset),
            format_func=lambda x: _TEMPORAL_PRESETS[x][0],
            key=f"{key}_preset",
        )
        if new_preset != cur_preset and new_preset != "custom":
            _, p_f, p_o, p_v = _TEMPORAL_PRESETS[new_preset]
            rule["field"]      = p_f
            rule["op"]         = p_o
            rule["value_days"] = p_v
            st.rerun()

        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            flds = ["joined_at","last_seen"]
            rule["field"] = st.selectbox("الحقل", flds,
                index=flds.index(rule.get("field","last_seen")) if rule.get("field") in flds else 1,
                format_func=lambda x: {"joined_at":"📅 تاريخ التسجيل",
                                       "last_seen":"👁️ آخر ظهور"}[x],
                key=f"{key}_f")
        with c2:
            ops = [">=","<="]
            rule["op"] = st.selectbox("العلاقة", ops,
                index=ops.index(rule.get("op",">=")) if rule.get("op") in ops else 0,
                format_func=lambda x: "خلال آخر" if x==">=" else "قبل أكثر من",
                key=f"{key}_op")
        with c3:
            try: _days = int(rule.get("value_days") or 7)
            except (ValueError, TypeError): _days = 7
            rule["value_days"] = st.number_input("عدد الأيام", min_value=0, max_value=3650,
                value=_days, key=f"{key}_d")

    def _render_window_picker(rule: dict, key: str):
        """مختار النافذة الزمنية المشترك بين event و aggregate.

        يدعم: كل التاريخ / آخر N يوم / بين تاريخين + فلتر ساعات اليوم اختياري.
        """
        import datetime as _dt
        win = rule.get("window") or {"type": "all"}
        wtypes = ["all", "last_days", "between"]
        _wlabels = {"all": "كل التاريخ", "last_days": "آخر N يوم",
                    "between": "📅 من تاريخ ↔ إلى تاريخ"}
        wt = st.selectbox("النافذة الزمنية", wtypes,
            index=wtypes.index(win.get("type","all")) if win.get("type") in wtypes else 0,
            format_func=lambda x: _wlabels.get(x, x),
            key=f"{key}_t")
        new_win: dict = {}
        if wt == "last_days":
            try: _days_def = int(win.get("days", 30) or 30)
            except (ValueError, TypeError): _days_def = 30
            d = st.number_input("عدد الأيام", min_value=1, max_value=3650,
                value=_days_def, key=f"{key}_d")
            new_win = {"type": "last_days", "days": int(d)}
        elif wt == "between":
            _today = _dt.date.today()
            def _parse_date(s, fallback):
                try: return _dt.date.fromisoformat(str(s)[:10])
                except (ValueError, TypeError): return fallback
            _from_def = _parse_date(win.get("from"), _today - _dt.timedelta(days=30))
            _to_def   = _parse_date(win.get("to"),   _today + _dt.timedelta(days=1))
            cc1, cc2 = st.columns(2)
            _f = cc1.date_input("من تاريخ", value=_from_def, key=f"{key}_from")
            _t = cc2.date_input("إلى تاريخ", value=_to_def, key=f"{key}_to")
            new_win = {"type": "between",
                       "from": _f.isoformat(),
                       "to": (_t + _dt.timedelta(days=1)).isoformat()}
        else:
            new_win = {"type": "all"}

        # ── فلتر ساعات اليوم (اختياري — يُدمج فوق أي نوع نافذة) ─────────────
        _h_on_default = bool(win.get("hour_from") is not None
                             and win.get("hour_to") is not None)
        _h_on = st.checkbox("🕐 قيّد بساعات معيّنة من اليوم (بتوقيت الرياض)",
                            value=_h_on_default, key=f"{key}_h_on")
        if _h_on:
            def _safe_h(v, default):
                try: return max(0, min(23, int(v)))
                except (ValueError, TypeError): return default
            hf_def = _safe_h(win.get("hour_from"), 8)
            ht_def = _safe_h(win.get("hour_to"), 22)
            hc1, hc2 = st.columns(2)
            hf = hc1.number_input("من ساعة", min_value=0, max_value=23,
                                  value=hf_def, key=f"{key}_hf",
                                  help="0-23 (مثلاً 18 = 6 مساءً)")
            ht = hc2.number_input("إلى ساعة", min_value=0, max_value=23,
                                  value=ht_def, key=f"{key}_ht",
                                  help="لو أصغر من «من» يلتف عبر منتصف الليل")
            new_win["hour_from"] = int(hf)
            new_win["hour_to"]   = int(ht)
        rule["window"] = new_win

    _RULE_TYPES = {
        "attribute": ("🏷️ صفة", _render_attribute_rule),
        "event":     ("⚡ حدث",  _render_event_rule),
        "aggregate": ("📊 عدّاد", _render_aggregate_rule),
        "temporal":  ("⏰ زمن", _render_temporal_rule),
    }

    # ════════════════════════════════════════════════════════════════════
    # ✨ الواجهة المسطّحة — Picker مباشر لـ 17 أصل
    # ════════════════════════════════════════════════════════════════════
    # بدل ما المستخدم يختار "نوع شرط" مجرّد ثم "حقل/حركة"، يختار الأصل
    # المطلوب مباشرة من قائمة واحدة (مثل فلاتر صفحة تحليل المستخدمين).
    # الـ backend يبقى كما هو — الـpicker يحوّل الاختيار إلى الـtype/field
    # المناسب خلف الكواليس، فالشرائح المحفوظة قديماً تشتغل بدون تغيير.
    # ── الأصول الـ13 — مطابقة 1:1 لفلاتر صفحة «تحليل المستخدمين» ──────
    # كل قيمة قابلة لاختيار "الكل" → الـbackend يستخدم op=is_any (يولّد TRUE).
    _PICKER_OPTIONS = [
        # الملف الشخصي
        ("lang",              "🌐 اللغة"),
        ("gender",            "⚧ الجنس"),
        ("age",               "🎂 العمر"),
        ("city",              "🏙 المدينة"),
        ("profile_complete",  "✅ اكتمال الملف"),
        ("status",            "⚡ الحالة (نشط/خامل)"),
        # المفضلات
        ("favorite_store",    "❤️ مفضّل متجر"),
        ("favorite_category", "🏷️ مفضّل قسم"),
        # السلوك (أحداث)
        ("evt_copy",          "🗒️ نسخ كوبون"),
        ("evt_click",         "🖱️ نقر رابط متجر"),
        ("evt_view",          "👁️ زيارة متجر / قسم"),
        ("evt_search",        "🔍 بحث"),
        ("evt_story",         "🎬 مشاهدة ستوري"),
        ("evt_trend",         "🔥 تفاعل مع ترند"),
    ]
    _PICKER_KEYS   = [k for k, _ in _PICKER_OPTIONS]
    _PICKER_LABELS = dict(_PICKER_OPTIONS)
    _ATTR_PICKERS  = {"lang","gender","age","city","profile_complete",
                      "favorite_store","favorite_category"}
    _EVT_PICKERS   = {"evt_copy","evt_click","evt_view","evt_search",
                      "evt_story","evt_trend"}

    # نطاقات العمر — نفس صفحة تحليل المستخدمين
    _AGE_RANGES = [
        ("u18",   "أقل من 18", [0, 17]),
        ("18-24", "18 – 24",   [18, 24]),
        ("25-34", "25 – 34",   [25, 34]),
        ("35-44", "35 – 44",   [35, 44]),
        ("45-54", "45 – 54",   [45, 54]),
        ("55+",   "+55",       [55, 200]),
    ]
    _AGE_RANGE_LABELS = {k: lbl for k, lbl, _ in _AGE_RANGES}
    _AGE_RANGE_BOUNDS = {k: bounds for k, _, bounds in _AGE_RANGES}

    def _detect_age_range(rule: dict) -> str:
        """يستنتج النطاق المختار من قيم between المخزّنة."""
        v = rule.get("value")
        if isinstance(v, (list, tuple)) and len(v) == 2:
            try:
                lo, hi = int(v[0]), int(v[1])
                for k, _, (b_lo, b_hi) in _AGE_RANGES:
                    if lo == b_lo and hi == b_hi:
                        return k
            except (ValueError, TypeError):
                pass
        return "18-24"

    def _detect_picker_key(rule: dict) -> str:
        """يستنتج خيار الـpicker من حالة الـrule المحفوظة (backward-compat)."""
        t = rule.get("type", "attribute")
        if t == "attribute":
            f = rule.get("field", "lang")
            return f if f in _ATTR_PICKERS else "lang"
        if t == "event":
            a = rule.get("action")
            # ترند مستقل: أي تفاعل (action=None) مع context=trend_*
            if (a is None
                and rule.get("context") in ("trend_daily","trend_weekly","trend_any")):
                return "evt_trend"
            if a == "copy_coupon":                 return "evt_copy"
            if a == "click_link":                  return "evt_click"
            if a in ("view_store", "view_tag"):    return "evt_view"
            if a in ("search", "search_keyword"):  return "evt_search"
            if a == "view_story":                  return "evt_story"
            return "evt_copy"
        if t == "temporal":  return "status"
        # aggregate/أصول قديمة محذوفة → fallback آمن
        return "lang"

    def _init_rule_for_picker(picker_key: str) -> dict:
        """قاعدة جديدة افتراضية «الكل» (is_any) لكل أصل — مطابقة لتحليل المستخدمين."""
        if picker_key in ("lang","gender","city","profile_complete",
                          "favorite_store","favorite_category"):
            return {"type":"attribute","field":picker_key,"op":"is_any","value":None}
        if picker_key == "age":
            # العمر يبدأ بـ"الكل" أيضاً
            return {"type":"attribute","field":"age","op":"is_any","value":None}
        if picker_key == "status":
            # ⚡ الحالة (نشط/خامل) = temporal مغلّف بـradio بسيط
            # افتراضياً "الكل" → نخزّن temporal مع op=is_any وlast_seen
            return {"type":"temporal","field":"last_seen","op":"is_any","value_days":20}
        if picker_key == "evt_copy":
            return {"type":"event","action":"copy_coupon","entity_type":"any",
                    "context":"any","window":{"type":"last_days","days":30}}
        if picker_key == "evt_click":
            return {"type":"event","action":"click_link","entity_type":"any",
                    "context":"any","window":{"type":"last_days","days":30}}
        if picker_key == "evt_view":
            return {"type":"event","action":"view_store","entity_type":"any",
                    "context":"any","window":{"type":"last_days","days":30}}
        if picker_key == "evt_search":
            return {"type":"event","action":"search_keyword","entity_type":"keyword",
                    "entity_value":"","context":"any",
                    "window":{"type":"last_days","days":30}}
        if picker_key == "evt_story":
            return {"type":"event","action":"view_story","entity_type":"any",
                    "entity_value":None,"was_trending":None,
                    "window":{"type":"last_days","days":30}}
        if picker_key == "evt_trend":
            # أي تفاعل (action=None) ضمن سياق ترند
            return {"type":"event","action":None,"entity_type":"any",
                    "context":"trend_any",
                    "window":{"type":"last_days","days":30}}
        return {"type":"attribute","field":"lang","op":"is_any","value":None}

    def _render_evt_target_context(rule: dict, key: str):
        """يعرض الهدف+السياق+حالة المتاجر لأحداث copy/click."""
        c1, c2 = st.columns(2)
        with c1:
            ent_opts = ["any","store","category"]
            rule["entity_type"] = st.selectbox(
                "🎯 الهدف", ent_opts,
                index=ent_opts.index(rule.get("entity_type","any"))
                      if rule.get("entity_type") in ent_opts else 0,
                format_func=lambda x: {"any":"أي شيء","store":"متجر محدد",
                                       "category":"قسم محدد"}[x],
                key=f"{key}_ent")
            if rule["entity_type"] == "store":
                opts = _STORES or ["—"]
                cur = rule.get("entity_value") or opts[0]
                rule["entity_value"] = st.selectbox("اسم المتجر", opts,
                    index=opts.index(cur) if cur in opts else 0, key=f"{key}_ev")
            elif rule["entity_type"] == "category":
                opts = _CATEGORIES or ["—"]
                cur = rule.get("entity_value") or opts[0]
                rule["entity_value"] = st.selectbox("اسم القسم", opts,
                    index=opts.index(cur) if cur in opts else 0, key=f"{key}_ev")
            else:
                rule["entity_value"] = None
        with c2:
            ctxs = list(_CONTEXT_LABELS.keys())
            rule["context"] = st.selectbox("🔥 السياق", ctxs,
                index=ctxs.index(rule.get("context","any"))
                      if rule.get("context") in ctxs else 0,
                format_func=lambda x: _CONTEXT_LABELS[x], key=f"{key}_ctx")
            _ss_opts = ["any","active","expiring","expired"]
            _ss_labels = {"any":"🌐 الكل","active":"🟢 فعّالة",
                         "expiring":"⏳ قربت تنتهي (≤3 أيام)",
                         "expired":"⛔ منتهية"}
            cur_ss = rule.get("store_status") or "any"
            new_ss = st.selectbox("🏪 حالة المتاجر", _ss_opts,
                index=_ss_opts.index(cur_ss) if cur_ss in _ss_opts else 0,
                format_func=lambda x: _ss_labels[x], key=f"{key}_ss")
            rule["store_status"] = None if new_ss == "any" else new_ss

    # ── Helper: زر/راديو "الكل" يُحوّل الـrule لقاعدة tautology ─────
    def _radio_with_any(label, options_dict, current_value, key,
                        any_choice="__any__", default_specific=None):
        """يعرض radio: «الكل» + قيم محددة. يرجّع (is_any, selected_value)."""
        keys_ordered = [any_choice] + list(options_dict.keys())
        labels = {any_choice: "🌐 الكل", **options_dict}
        idx = 0  # الافتراضي: الكل
        if current_value in options_dict:
            idx = keys_ordered.index(current_value)
        choice = st.radio(label, keys_ordered, index=idx, horizontal=True,
                          format_func=lambda x: labels[x], key=key)
        if choice == any_choice:
            return True, None
        return False, choice

    def _render_picker_rule(picker_key: str, rule: dict, key: str):
        """يرسم الواجهة المختصرة لكل أصل — مطابقة فلاتر تحليل المستخدمين."""

        # ── 🌐 اللغة ─────────────────────────────────────────────────
        if picker_key == "lang":
            rule["type"] = "attribute"; rule["field"] = "lang"
            cur = rule.get("value") if rule.get("op") != "is_any" else None
            is_any, val = _radio_with_any("القيمة",
                {"ar":"🇸🇦 عربي", "en":"🇬🇧 إنجليزي"},
                cur, key=f"{key}_v")
            rule["op"] = "is_any" if is_any else "="
            rule["value"] = val
            return

        # ── ⚧ الجنس ──────────────────────────────────────────────────
        if picker_key == "gender":
            rule["type"] = "attribute"; rule["field"] = "gender"
            cur = rule.get("value") if rule.get("op") != "is_any" else None
            is_any, val = _radio_with_any("القيمة",
                {"male":"♂️ ذكر", "female":"♀️ أنثى"},
                cur, key=f"{key}_v")
            rule["op"] = "is_any" if is_any else "="
            rule["value"] = val
            return

        # ── 🎂 العمر (نطاقات مطابقة لتحليل المستخدمين) ────────────────
        if picker_key == "age":
            rule["type"] = "attribute"; rule["field"] = "age"
            cur_op = rule.get("op", "is_any")
            cur_range = _detect_age_range(rule) if cur_op != "is_any" else None
            range_opts = {k: lbl for k, lbl, _ in _AGE_RANGES}
            is_any, sel = _radio_with_any("الفئة العمرية", range_opts,
                cur_range, key=f"{key}_v")
            if is_any:
                rule["op"] = "is_any"; rule["value"] = None
            else:
                rule["op"] = "between"
                rule["value"] = list(_AGE_RANGE_BOUNDS[sel])
            return

        # ── 🏙 المدينة ────────────────────────────────────────────────
        if picker_key == "city":
            rule["type"] = "attribute"; rule["field"] = "city"
            cur = rule.get("value") if rule.get("op") != "is_any" else None
            city_opts = {c: c for c in (_CITIES or [])}
            is_any, val = _radio_with_any("المدينة", city_opts,
                cur, key=f"{key}_v")
            rule["op"] = "is_any" if is_any else "="
            rule["value"] = val
            return

        # ── ✅ اكتمال الملف ──────────────────────────────────────────
        if picker_key == "profile_complete":
            rule["type"] = "attribute"; rule["field"] = "profile_complete"
            cur_op = rule.get("op", "is_any")
            cur_val = "yes" if (cur_op != "is_any" and rule.get("value")) \
                       else "no" if cur_op != "is_any" else None
            is_any, val = _radio_with_any("الحالة",
                {"yes":"✅ مكتمل", "no":"⚠️ ناقص"},
                cur_val, key=f"{key}_v")
            if is_any:
                rule["op"] = "is_any"; rule["value"] = None
            else:
                rule["op"] = "="; rule["value"] = (val == "yes")
            return

        # ── ⚡ الحالة (نشط/خامل = temporal مغلّف) ───────────────────
        if picker_key == "status":
            rule["type"] = "temporal"; rule["field"] = "last_seen"
            cur_op = rule.get("op", "is_any")
            cur_st = None
            if cur_op == ">=":   cur_st = "active"
            elif cur_op == "<=": cur_st = "idle"
            is_any, val = _radio_with_any("الحالة",
                {"active":"🟢 نشط (آخر 20 يوم)",
                 "idle":  "😴 خامل (لم يظهر منذ 20+ يوم)"},
                cur_st, key=f"{key}_v")
            if is_any:
                rule["op"] = "is_any"; rule["value_days"] = 20
            elif val == "active":
                rule["op"] = ">="; rule["value_days"] = 20
            else:
                rule["op"] = "<="; rule["value_days"] = 20
            return

        # ── ❤️ مفضّل متجر ───────────────────────────────────────────
        if picker_key == "favorite_store":
            rule["type"] = "attribute"; rule["field"] = "favorite_store"
            mode_opts = ["__any__", "has", "none", "specific"]
            mode_labels = {"__any__":"🌐 الكل", "has":"❤️ عنده مفضّل",
                          "none":"🤍 بلا مفضّل", "specific":"🎯 متجر محدد"}
            cur_op = rule.get("op", "is_any")
            cur_mode = ("__any__" if cur_op == "is_any"
                        else "has" if cur_op == "has_any"
                        else "none" if cur_op == "has_none"
                        else "specific")
            mode = st.radio("الوضع", mode_opts,
                index=mode_opts.index(cur_mode),
                horizontal=True,
                format_func=lambda x: mode_labels[x], key=f"{key}_m")
            if mode == "__any__":
                rule["op"] = "is_any"; rule["value"] = None
            elif mode == "has":
                rule["op"] = "has_any"; rule["value"] = None
            elif mode == "none":
                rule["op"] = "has_none"; rule["value"] = None
            else:
                opts = _STORES or ["—"]
                cur = rule.get("value") if rule.get("value") in opts else opts[0]
                rule["value"] = st.selectbox("اسم المتجر", opts,
                    index=opts.index(cur), key=f"{key}_s")
                rule["op"] = "="
            return

        # ── 🏷️ مفضّل قسم ────────────────────────────────────────────
        if picker_key == "favorite_category":
            rule["type"] = "attribute"; rule["field"] = "favorite_category"
            mode_opts = ["__any__", "has", "none", "specific"]
            mode_labels = {"__any__":"🌐 الكل", "has":"❤️ عنده مفضّل",
                          "none":"🤍 بلا مفضّل", "specific":"🎯 قسم محدد"}
            cur_op = rule.get("op", "is_any")
            cur_mode = ("__any__" if cur_op == "is_any"
                        else "has" if cur_op == "has_any"
                        else "none" if cur_op == "has_none"
                        else "specific")
            mode = st.radio("الوضع", mode_opts,
                index=mode_opts.index(cur_mode),
                horizontal=True,
                format_func=lambda x: mode_labels[x], key=f"{key}_m")
            if mode == "__any__":
                rule["op"] = "is_any"; rule["value"] = None
            elif mode == "has":
                rule["op"] = "has_any"; rule["value"] = None
            elif mode == "none":
                rule["op"] = "has_none"; rule["value"] = None
            else:
                opts = _CATEGORIES or ["—"]
                cur = rule.get("value") if rule.get("value") in opts else opts[0]
                rule["value"] = st.selectbox("اسم القسم", opts,
                    index=opts.index(cur), key=f"{key}_s")
                rule["op"] = "="
            return

        # ── 🗒️ نسخ كوبون / 🖱️ نقر رابط ─────────────────────────────
        if picker_key in ("evt_copy", "evt_click"):
            rule["type"] = "event"
            rule["action"] = "copy_coupon" if picker_key == "evt_copy" else "click_link"
            _render_evt_target_context(rule, key)
            _render_window_picker(rule, f"{key}_w")
            return

        # ── 👁️ زيارة متجر/قسم ──────────────────────────────────────
        if picker_key == "evt_view":
            rule["type"] = "event"
            c1, c2 = st.columns(2)
            with c1:
                view_opts = ["store", "category"]
                cur_act = rule.get("action", "view_store")
                cur_idx = 0 if cur_act != "view_tag" else 1
                sel = st.selectbox("🎯 نوع الزيارة", view_opts,
                    index=cur_idx,
                    format_func=lambda x: "👁️ متجر" if x == "store" else "🏷️ قسم",
                    key=f"{key}_vt")
                rule["action"] = "view_store" if sel == "store" else "view_tag"
            with c2:
                if rule["action"] == "view_store":
                    opts = ["— أي متجر —"] + (_STORES or [])
                    cur = rule.get("entity_value") or "— أي متجر —"
                    _sel = st.selectbox("اسم المتجر", opts,
                        index=opts.index(cur) if cur in opts else 0, key=f"{key}_ev")
                    if _sel.startswith("— أي"):
                        rule["entity_type"] = "any"; rule["entity_value"] = None
                    else:
                        rule["entity_type"] = "store"; rule["entity_value"] = _sel
                else:
                    opts = ["— أي قسم —"] + (_CATEGORIES or [])
                    cur = rule.get("entity_value") or "— أي قسم —"
                    _sel = st.selectbox("اسم القسم", opts,
                        index=opts.index(cur) if cur in opts else 0, key=f"{key}_ev")
                    if _sel.startswith("— أي"):
                        rule["entity_type"] = "any"; rule["entity_value"] = None
                    else:
                        rule["entity_type"] = "category"; rule["entity_value"] = _sel
            _render_window_picker(rule, f"{key}_w")
            return

        # ── 🔍 بحث ────────────────────────────────────────────────
        if picker_key == "evt_search":
            rule["type"] = "event"; rule["action"] = "search_keyword"
            rule["entity_type"] = "keyword"
            rule["entity_value"] = st.text_input(
                "🔎 الكلمة (اتركها فارغة لأي بحث)",
                value=rule.get("entity_value", "") or "",
                placeholder="مثلاً: نون، أزياء، عطور…",
                key=f"{key}_kw")
            _render_window_picker(rule, f"{key}_w")
            return

        # ── 🔥 تفاعل مع ترند (أي تفاعل ضمن سياق ترند) ───────────────
        if picker_key == "evt_trend":
            rule["type"] = "event"
            rule["action"] = None          # أي تفاعل
            rule["entity_type"] = "any"
            rule["entity_value"] = None
            opts = ["trend_any","trend_daily","trend_weekly"]
            cur_ctx = rule.get("context","trend_any")
            cur_idx = opts.index(cur_ctx) if cur_ctx in opts else 0
            sel = st.radio("🔥 نوع الترند", opts, index=cur_idx, horizontal=True,
                format_func=lambda x: {"trend_any":"🌐 الكل",
                                       "trend_daily":"🔥 يومي",
                                       "trend_weekly":"🔥 أسبوعي"}[x],
                key=f"{key}_tt")
            rule["context"] = sel
            _render_window_picker(rule, f"{key}_w")
            return

        # ── 🎬 مشاهدة ستوري ────────────────────────────────────────
        if picker_key == "evt_story":
            rule["type"] = "event"; rule["action"] = "view_story"
            opts = ["all","trend","normal"]
            cur_wt = rule.get("was_trending")
            cur_idx = 0 if cur_wt is None else (1 if cur_wt else 2)
            sel = st.radio("🎬 نوع الستوري", opts, index=cur_idx, horizontal=True,
                format_func=lambda x: {"all":"🌐 الكل","trend":"🔥 ترند فقط",
                                       "normal":"📌 عادي فقط"}[x],
                key=f"{key}_wt")
            rule["was_trending"] = None if sel == "all" else (sel == "trend")
            rule["entity_type"] = "any"; rule["entity_value"] = None
            _render_window_picker(rule, f"{key}_w")
            return

    # ── منطق التركيب بين المجموعات ────────────────────────────────────────
    _logic_opts = ["or", "and"]
    st.session_state.seg_rules["logic"] = st.radio(
        "🔗 الربط بين المجموعات:", _logic_opts,
        index=_logic_opts.index(st.session_state.seg_rules.get("logic","or")),
        horizontal=True,
        format_func=lambda x: "أو (أي مجموعة تكفي)" if x=="or" else "و (كل المجموعات معاً)",
        key="seg_top_logic")

    # ── العمودين: البناء + الإحصاء ─────────────────────────────────────────
    _build_col, _stat_col = st.columns([3, 2])

    with _build_col:
        # ── عرض المجموعات والقواعد ────────────────────────────────────────
        for g_idx, group in enumerate(st.session_state.seg_rules["groups"]):
            with st.container(border=True):
                _gh1, _gh2, _gh3 = st.columns([2, 2, 1])
                with _gh1:
                    st.markdown(f"#### 📦 المجموعة {g_idx+1}")
                with _gh2:
                    group["logic"] = st.selectbox(
                        "منطق داخلي", ["and","or"],
                        index=["and","or"].index(group.get("logic","and")),
                        format_func=lambda x: "🔗 كل الشروط" if x=="and" else "🔀 أي شرط",
                        key=f"g{g_idx}_logic", label_visibility="collapsed")
                with _gh3:
                    if (len(st.session_state.seg_rules["groups"]) > 1
                            and st.button("🗑️ احذف المجموعة",
                                          key=f"g{g_idx}_del",
                                          width="stretch")):
                        st.session_state.seg_rules["groups"].pop(g_idx)
                        st.rerun()

                # ── قواعد داخل المجموعة ──────────────────────────────────
                # نتتبّع الشروط "المؤكَّدة" بصرياً (مقفلة) بمفتاحٍ في session_state.
                _confirmed_set = st.session_state.setdefault("seg_confirmed", set())
                for r_idx, rule in enumerate(group["rules"]):
                    _cur_pk = _detect_picker_key(rule)
                    _pk_lbl = _PICKER_LABELS.get(_cur_pk, "شرط")
                    _rule_uid = f"g{g_idx}_r{r_idx}"
                    _is_confirmed = _rule_uid in _confirmed_set

                    # ملخّص قصير للقيمة الحالية (يظهر في العنوان عند القفل)
                    def _short_summary(rk, rl):
                        op = rl.get("op", "")
                        if op == "is_any":
                            return "الكل"
                        if rk == "evt_trend":
                            return {"trend_daily":"🔥 يومي",
                                    "trend_weekly":"🔥 أسبوعي",
                                    "trend_any":"🔥 أي ترند"
                                   }.get(rl.get("context","trend_any"), "ترند")
                        if rk in ("evt_copy","evt_click","evt_view",
                                  "evt_search","evt_story"):
                            ev = rl.get("entity_value")
                            return f"على «{ev}»" if ev else "أي هدف"
                        v = rl.get("value")
                        if isinstance(v, bool):
                            return "نعم" if v else "لا"
                        if isinstance(v, list):
                            return f"{v[0]}–{v[1]}"
                        if v is not None:
                            return str(v)
                        if op == "has_any":  return "عنده مفضّل"
                        if op == "has_none": return "بلا مفضّل"
                        return ""

                    _summary = _short_summary(_cur_pk, rule)
                    _title = (f"✅ {_pk_lbl}  —  {_summary}" if _is_confirmed
                              else f"{_pk_lbl}  —  شرط {r_idx+1}")
                    if rule.get('negate'): _title += "  🚫 (نفي)"

                    with st.expander(_title, expanded=not _is_confirmed):
                        # ── اختيار الأصل (قائمة مسطّحة من 13 خيار) ─────
                        new_pk = st.selectbox(
                            "✨ الأصل:",
                            _PICKER_KEYS,
                            index=_PICKER_KEYS.index(_cur_pk),
                            format_func=lambda x: _PICKER_LABELS[x],
                            key=f"{_rule_uid}_pk",
                            help="اختر ما تريد التصفية به مباشرة "
                                 "(اللغة، الجنس، نسخ كوبون، …).")
                        if new_pk != _cur_pk:
                            # إعادة تهيئة بقيم افتراضية «الكل» للأصل الجديد
                            group["rules"][r_idx] = _init_rule_for_picker(new_pk)
                            _confirmed_set.discard(_rule_uid)
                            st.rerun()

                        # ── الواجهة المختصرة لهذا الأصل ────────────────
                        _render_picker_rule(new_pk, rule, _rule_uid)

                        # خيارات: نفي
                        rule["negate"] = st.checkbox(
                            "🚫 نفي (ينطبق على من *لا* يحقق)",
                            value=bool(rule.get("negate")),
                            key=f"{_rule_uid}_neg")

                        # ── أزرار: ✅ تأكيد + 🗑️ حذف ─────────────────
                        btn_c1, btn_c2 = st.columns([3, 1])
                        with btn_c1:
                            if _is_confirmed:
                                if st.button("✏️ عدّل هذا الشرط",
                                             key=f"{_rule_uid}_edit",
                                             width="stretch"):
                                    _confirmed_set.discard(_rule_uid)
                                    st.rerun()
                            else:
                                if st.button("✅ تأكيد الشرط (اقفل المُحرِّر)",
                                             key=f"{_rule_uid}_ok",
                                             type="primary",
                                             width="stretch"):
                                    _confirmed_set.add(_rule_uid)
                                    st.rerun()
                        with btn_c2:
                            if st.button("🗑️ احذف",
                                         key=f"{_rule_uid}_del",
                                         width="stretch"):
                                group["rules"].pop(r_idx)
                                _confirmed_set.discard(_rule_uid)
                                st.rerun()

                # ── إضافة شرط جديد للمجموعة ───────────────────────────────
                _add_c1, _add_c2 = st.columns([3, 1])
                with _add_c1:
                    _new_pk_add = st.selectbox(
                        "أصل الشرط الجديد:",
                        _PICKER_KEYS,
                        format_func=lambda x: _PICKER_LABELS[x],
                        key=f"g{g_idx}_new_pk",
                        label_visibility="collapsed")
                with _add_c2:
                    if st.button("➕ أضف شرط", key=f"g{g_idx}_add_rule",
                                 width="stretch"):
                        group["rules"].append(_init_rule_for_picker(_new_pk_add))
                        st.rerun()

        # ── إضافة مجموعة جديدة ────────────────────────────────────────────
        st.write("")
        if st.button("➕ أضف مجموعة جديدة", key="seg_add_group", width="stretch"):
            st.session_state.seg_rules["groups"].append(
                {"logic": "and", "rules": []})
            st.rerun()

    # ── العمود الإحصائي + الحفظ + الانتقال للإرسال ─────────────────────────
    with _stat_col:
        st.markdown("### 📊 الإحصاء الحي")
        try:
            with get_conn() as _conn_s:
                _conn_s.autocommit = True
                _bd = _ae.count_audience_breakdown(
                    _conn_s, st.session_state.seg_rules)
            st.metric("👥 إجمالي فريد (الكل)", _bd["total_unique"])
            _m1, _m2 = st.columns(2)
            _m1.metric("📱 تليجرام", _bd["telegram"])
            _m2.metric("📧 إيميل",   _bd["email"])
        except Exception as _e:
            st.error(f"تعذّر العدّ: {_e}")

        st.divider()
        st.markdown("### 👁️ معاينة عيّنة")
        _prev_ch = st.session_state.seg_meta.get("channel") or "both"
        _prev_ch_for_sample = ("telegram" if _prev_ch == "telegram"
                               else "email" if _prev_ch == "email" else "both")
        try:
            with get_conn() as _conn_p:
                _conn_p.autocommit = True
                _sample = _ae.sample_audience(
                    _conn_p, _prev_ch_for_sample,
                    st.session_state.seg_rules, n=5)
            if _sample:
                _df_s = pd.DataFrame(_sample)
                # نختصر الأعمدة لعرض مناسب في عمود ضيق + تسميات عربية
                _rename = {"handle": "اليوزر", "name": "الاسم",
                           "email": "الإيميل", "lang": "اللغة",
                           "city": "المدينة"}
                _keep = [c for c in ["handle","name","email","lang","city"]
                         if c in _df_s.columns]
                _df_show = _df_s[_keep].rename(columns=_rename)
                # نُختصر النصوص الطويلة لتفادي القص في عمود ضيق
                for _c in _df_show.columns:
                    if _df_show[_c].dtype == object:
                        _df_show[_c] = _df_show[_c].astype(str).str.slice(0, 22)
                st.dataframe(_df_show, hide_index=True, width="stretch",
                             column_config={
                                 "اليوزر":   st.column_config.TextColumn(width="small"),
                                 "الاسم":    st.column_config.TextColumn(width="small"),
                                 "الإيميل":  st.column_config.TextColumn(width="medium"),
                                 "اللغة":    st.column_config.TextColumn(width="small"),
                                 "المدينة":  st.column_config.TextColumn(width="small"),
                             })
            else:
                st.info("لا مطابقين بعد. عدّل الشروط.")
        except Exception as _e:
            st.warning(f"تعذّرت المعاينة: {_e}")

        st.divider()
        st.markdown("### 💾 الحفظ")
        if st.button("💾 احفظ الشريحة", key="seg_save_btn",
                     width="stretch", type="primary"):
            _name = (st.session_state.seg_meta.get("name") or "").strip()
            if not _name:
                st.error("أدخل اسماً للشريحة.")
            else:
                try:
                    with get_conn() as _conn_save:
                        _conn_save.autocommit = True
                        _new_id = _ae.save_segment(
                            _conn_save,
                            name=_name,
                            description=st.session_state.seg_meta.get("description",""),
                            rules_json=st.session_state.seg_rules,
                            channel=st.session_state.seg_meta.get("channel"),
                            segment_id=st.session_state.seg_meta.get("id"))
                    st.session_state.seg_meta["id"] = _new_id
                    st.success(f"✅ حُفظت الشريحة #{_new_id}")
                    st.cache_data.clear()
                except Exception as _e:
                    st.error(f"فشل الحفظ: {_e}")

        if st.session_state.seg_meta.get("id"):
            if st.button("🚀 افتح في مركز الإشعارات",
                         key="seg_to_notif", width="stretch"):
                st.session_state["nc_preset_segment_id"] = st.session_state.seg_meta["id"]
                st.session_state["page"] = "مركز الإشعارات"
                st.rerun()

        # ── سجل التغييرات (rollback) ────────────────────────────────────
        if st.session_state.seg_meta.get("id"):
            with st.expander("📜 سجل التغييرات (آخر 10 نسخ)"):
                try:
                    with get_conn() as _conn_v:
                        _conn_v.autocommit = True
                        _versions = _ae.list_segment_versions(
                            _conn_v, st.session_state.seg_meta["id"], limit=10)
                    if not _versions:
                        st.caption("لا تعديلات سابقة بعد.")
                    else:
                        for _v in _versions:
                            _vc1, _vc2 = st.columns([4, 1])
                            with _vc1:
                                _ts = _v["saved_at"].strftime("%Y-%m-%d %H:%M")
                                st.caption(f"🕐 {_ts} · {_v.get('change_note') or '—'}")
                            with _vc2:
                                if st.button("⏪ ارجع",
                                             key=f"v_restore_{_v['id']}",
                                             width="stretch"):
                                    with get_conn() as _c2:
                                        _c2.autocommit = True
                                        _ae.restore_segment_version(
                                            _c2,
                                            st.session_state.seg_meta["id"],
                                            _v["id"])
                                        _refreshed = _ae.load_segment(
                                            _c2, st.session_state.seg_meta["id"])
                                    if _refreshed:
                                        st.session_state.seg_rules = _refreshed["rules_json"]
                                    st.success("استُرجعت النسخة.")
                                    st.rerun()
                except Exception as _e:
                    st.warning(f"تعذّر تحميل السجل: {_e}")

        # ── JSON للمطوّر (debug/تصدير) ─────────────────────────────────────
        with st.expander("🔧 JSON للشروط (متقدّم)"):
            _json_str = json.dumps(st.session_state.seg_rules,
                                   ensure_ascii=False, indent=2)
            # نُجبر LTR لعرض الـJSON بشكل قابل للقراءة (الـRTL يقلبه)
            st.markdown(
                f'<div dir="ltr" style="text-align:left;direction:ltr;">'
                f'<pre style="background:#0E1117;color:#E1E1E1;padding:12px;'
                f'border-radius:6px;overflow-x:auto;font-family:monospace;'
                f'font-size:12px;direction:ltr;text-align:left;white-space:pre;">'
                f'{_json_str}</pre></div>',
                unsafe_allow_html=True,
            )


elif page == "مركز الإشعارات":
    page_title("📢", "مركز البث والإشعارات الجماعية")

    from api import audience_engine as _ae_nc
    from api import audience_sender as _send_nc

    # ── زر تحديث الصفحة (مسح كاش + إعادة تحميل) ──────────────────────────
    _refresh_c1, _refresh_c2 = st.columns([5, 1])
    with _refresh_c2:
        if st.button("🔄 تحديث", key="nc_refresh", width="stretch",
                     help="مسح الكاش وإعادة تحميل الشرائح والحملات"):
            try:
                st.cache_data.clear()
            except Exception:
                pass
            st.rerun()

    # ── تحميل الشرائح المحفوظة ─────────────────────────────────────────────
    @st.cache_data(ttl=60)
    def _nc_load_segments():
        with get_conn() as _c:
            _c.autocommit = True
            usegs = _ae_nc.list_user_segments(_c)
            tmpls = _ae_nc.list_templates(_c)
        return usegs, tmpls

    _user_segs_nc, _templates_nc = _nc_load_segments()
    _all_segs_nc = _user_segs_nc + _templates_nc

    # شريحة معدّة سلفاً عبر زر «افتح في مركز الإشعارات» من بنّاء الشرائح
    _preset_sid = st.session_state.pop("nc_preset_segment_id", None)

    def _seg_picker(key_prefix: str, default_id: int | None = None,
                    channel_filter: str | None = None) -> int | None:
        """مختار شريحة موحّد للتبويبين.

        channel_filter: 'telegram' | 'email' | None
          - 'telegram' → يعرض شرائح channel='telegram' أو 'both' أو NULL
          - 'email'    → يعرض شرائح channel='email'    أو 'both' أو NULL
          - None       → كل الشرائح
        """
        if channel_filter in ("telegram", "email"):
            filtered = [s for s in _all_segs_nc
                        if (s.get("channel") in (channel_filter, "both")
                            or s.get("channel") is None)]
        else:
            filtered = _all_segs_nc
        _ch_badge = {"telegram":"📱", "email":"📧", "both":"📡"}
        opts = [(None, "— بدون شريحة (الكل) —")] + [
            (s["id"],
             f"{'📋' if s.get('is_template') else '💾'} "
             f"{_ch_badge.get(s.get('channel') or '', '⬜')} {s['name']}"
             + (f"  ({s['last_count']})" if s.get('last_count') is not None else ""))
            for s in filtered
        ]
        cur_idx = 0
        if default_id:
            for i, (sid, _) in enumerate(opts):
                if sid == default_id:
                    cur_idx = i
                    break
        sel = st.selectbox(
            "🎯 الشريحة المستهدفة:",
            opts, index=cur_idx,
            format_func=lambda x: x[1],
            key=f"{key_prefix}_seg",
        )
        return sel[0]

    def _live_count(channel: str, sid: int | None) -> int:
        try:
            with get_conn() as _c:
                _c.autocommit = True
                if sid:
                    seg = _ae_nc.load_segment(_c, sid)
                    return _ae_nc.count_audience(_c, channel,
                                                 seg["rules_json"] if seg else {})
                return _ae_nc.count_audience(_c, channel, {})
        except Exception:
            return 0

    tab_tg, tab_email, tab_sched, tab_reports, tab_excl = st.tabs(
        ["📱 إشعارات تليجرام", "✉️ حملات البريد الإلكتروني",
         "⏰ المجدولة", "📊 تقارير الحملات", "🚫 قائمة الاستثناء"])

    # ═══════════════════════════════════════════════════════════════════════
    # تبويب 1 — إشعارات تليجرام
    # ═══════════════════════════════════════════════════════════════════════
    with tab_tg:
        col_input, col_preview = st.columns([1.5, 1])

        with col_input:
            st.subheader("🖋️ تجهيز الرسالة")
            sid_tg = _seg_picker("nc_tg", default_id=_preset_sid,
                                 channel_filter="telegram")

            msg_text = st.text_area(
                "✍️ نص الرسالة:",
                placeholder="مثال: أقوى عروض اليوم في متجر نون 🔥",
                height=140, key="nc_tg_msg")
            msg_image = st.text_input(
                "🖼️ رابط صورة (اختياري):",
                placeholder="https://example.com/promo.jpg",
                key="nc_tg_img")

            with st.expander("⚙️ خيارات متقدّمة"):
                use_ab = st.checkbox("اختبار A/B (نصّان، 50/50)",
                                     key="nc_tg_ab")
                variant_b = None
                if use_ab:
                    variant_b = st.text_area(
                        "✍️ نص النسخة B:",
                        placeholder="نسخة بديلة لاختبار التفاعل",
                        height=120, key="nc_tg_msg_b")
                rate_tg = st.slider("⏱️ معدّل الإرسال (رسالة/ثانية)",
                                    1, 25, 20, key="nc_tg_rate",
                                    help="حد تليجرام 30/ثانية — يفضّل 20 للأمان")
                cap_tg = st.slider("🛡️ سقف الرسائل/يوم لكل مستخدم",
                                   0, 10, 3, key="nc_tg_cap",
                                   help="0 = بدون سقف")

            n_tg = _live_count("telegram", sid_tg)
            st.markdown(f"### 👥 سيستهدف: **{n_tg}** مستخدم تليجرام")

            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("🧪 محاكاة (بدون إرسال)",
                             key="nc_tg_dry", width="stretch"):
                    if not msg_text:
                        st.error("اكتب نص الرسالة أولاً.")
                    else:
                        with get_conn() as _c:
                            _c.autocommit = True
                            res = _send_nc.send_telegram_broadcast(
                                _c, segment_id=sid_tg,
                                message_text=msg_text, image_url=msg_image or None,
                                variant_b_text=variant_b,
                                rate_per_sec=rate_tg, freq_cap_per_day=cap_tg,
                                dry_run=True)
                        st.info(f"💡 ستُرسل لـ {res['would_send']} "
                                f"(تم استبعاد {res['skipped_freq_cap']} بسبب السقف)")

            with cc2:
                if st.button("🚀 إرسال فعلي", key="nc_tg_send",
                             width="stretch", type="primary"):
                    if not msg_text:
                        st.error("اكتب نص الرسالة أولاً.")
                    elif n_tg == 0:
                        st.warning("لا مستخدمين مطابقين للشريحة.")
                    else:
                        # مضاد التكرار
                        with get_conn() as _c_dup:
                            _c_dup.autocommit = True
                            _is_dup = _send_nc.check_recent_duplicate(
                                _c_dup, segment_id=sid_tg,
                                message_text=msg_text, channel="telegram",
                                within_hours=24)
                        if _is_dup:
                            st.error("🚫 نفس الرسالة أُرسلت لهذه الشريحة "
                                     "خلال آخر 24 ساعة. عدّل النص أو غيّر الشريحة.")
                            st.stop()
                        prog = st.progress(0.0, text="بدء الإرسال...")
                        def _cb(done, total):
                            try:
                                prog.progress(min(1.0, done/max(1,total)),
                                              text=f"تم {done}/{total}")
                            except Exception:
                                pass
                        try:
                            with get_conn() as _c:
                                _c.autocommit = True
                                res = _send_nc.send_telegram_broadcast(
                                    _c, segment_id=sid_tg,
                                    message_text=msg_text,
                                    image_url=msg_image or None,
                                    variant_b_text=variant_b,
                                    rate_per_sec=rate_tg,
                                    freq_cap_per_day=cap_tg,
                                    progress_cb=_cb)
                            if res["failed"] == 0:
                                st.success(f"✅ نجح إرسال {res['sent']} رسالة "
                                           f"(حملة #{res['broadcast_id']})")
                                st.balloons()
                            else:
                                st.warning(f"⚠️ نجح {res['sent']} ، فشل {res['failed']} "
                                           f"(حملة #{res['broadcast_id']})")
                            st.cache_data.clear()
                        except Exception as _e:
                            st.error(f"فشل الإرسال: {_e}")

        with col_preview:
            st.subheader("📱 معاينة")
            with st.container(border=True):
                if msg_image:
                    st.image(msg_image, width="stretch")
                if msg_text:
                    st.markdown("**نبض الصفقات**")
                    st.write(msg_text)
                else:
                    st.caption("اكتب نص الرسالة للمعاينة...")

        st.divider()
        with st.expander("📜 آخر 10 حملات تليجرام"):
            try:
                with get_conn() as _c:
                    _c.autocommit = True
                    hist = pd.read_sql("""
                        SELECT bl.id           AS "#",
                               (bl.sent_at AT TIME ZONE 'Asia/Riyadh')::text AS "وقت (KSA)",
                               s.name          AS "الشريحة",
                               bl.delivery_count AS "المستهدفون",
                               bl.sent_count   AS "نجح",
                               bl.failed_count AS "فشل",
                               bl.status       AS "الحالة",
                               LEFT(bl.message_text, 60) AS "مقتطف"
                        FROM broadcast_logs bl
                        LEFT JOIN audience_segments s ON s.id = bl.segment_id
                        ORDER BY bl.sent_at DESC LIMIT 10
                    """, _c)
                if hist.empty:
                    st.info("لا حملات سابقة.")
                else:
                    st.dataframe(hist, width="stretch", hide_index=True)
            except Exception as _e:
                st.error(f"تعذّر تحميل السجل: {_e}")

    # ═══════════════════════════════════════════════════════════════════════
    # تبويب 2 — حملات البريد الإلكتروني
    # ═══════════════════════════════════════════════════════════════════════
    with tab_email:
        col_build, col_prev = st.columns([3, 2])

        with col_build:
            st.subheader("✉️ بناء حملة بريدية")
            sid_em = _seg_picker("nc_em", default_id=_preset_sid,
                                 channel_filter="email")

            em_subject = st.text_input(
                "📌 عنوان الإيميل:",
                placeholder="مثال: عروض حصرية لك اليوم 🔥",
                key="nc_em_subj")
            em_banner = st.text_input(
                "🖼️ رابط البانر (اختياري):",
                placeholder="https://...", key="nc_em_banner")
            em_mode = st.radio("نوع المحتوى:",
                ["نص بسيط", "HTML متقدم"],
                horizontal=True, key="nc_em_mode")
            if em_mode == "نص بسيط":
                _raw = st.text_area("✍️ نص الإيميل:",
                    placeholder="اكتب محتوى الحملة...", height=200,
                    key="nc_em_body_plain")
                em_body_html = _raw.replace("\n","<br>") if _raw else ""
            else:
                em_body_html = st.text_area("كود HTML:",
                    placeholder="<h2>أهلاً!</h2>...", height=200,
                    key="nc_em_body_html")

            with st.expander("⚙️ خيارات متقدّمة"):
                use_ab_em = st.checkbox("اختبار A/B (موضوع+نص بديل)",
                                        key="nc_em_ab")
                vb_subj = vb_html = None
                if use_ab_em:
                    vb_subj = st.text_input("📌 عنوان النسخة B:",
                                            key="nc_em_subj_b")
                    vb_html = st.text_area("📝 محتوى النسخة B:",
                                           height=160, key="nc_em_body_b")
                    if vb_html:
                        vb_html = vb_html.replace("\n","<br>") if em_mode == "نص بسيط" else vb_html
                rate_em = st.slider("⏱️ معدّل الإرسال (إيميل/ثانية)",
                                    1, 20, 8, key="nc_em_rate")
                cap_em = st.slider("🛡️ سقف الإيميلات/يوم لكل مستخدم",
                                   0, 5, 3, key="nc_em_cap")

            n_em = _live_count("email", sid_em)
            st.markdown(f"### 📧 سيستهدف: **{n_em}** مشترك ببريد")

            ec1, ec2 = st.columns(2)
            with ec1:
                if st.button("🧪 محاكاة", key="nc_em_dry",
                             width="stretch"):
                    if not em_subject or not em_body_html:
                        st.error("عنوان ومحتوى الإيميل مطلوبان.")
                    else:
                        with get_conn() as _c:
                            _c.autocommit = True
                            res = _send_nc.send_email_broadcast(
                                _c, segment_id=sid_em,
                                subject=em_subject, body_html=em_body_html,
                                banner_url=em_banner or "",
                                variant_b_subject=vb_subj,
                                variant_b_html=vb_html,
                                rate_per_sec=rate_em,
                                freq_cap_per_day=cap_em,
                                dry_run=True)
                        st.info(f"💡 ستُرسل لـ {res['would_send']} إيميل "
                                f"(استبعد {res['skipped_freq_cap']} بسبب السقف)")
            with ec2:
                if st.button("🚀 إطلاق الحملة", key="nc_em_send",
                             width="stretch", type="primary"):
                    if not em_subject or not em_body_html:
                        st.error("عنوان ومحتوى الإيميل مطلوبان.")
                    elif n_em == 0:
                        st.warning("لا مشتركين بإيميل للشريحة.")
                    else:
                        with get_conn() as _c_dup:
                            _c_dup.autocommit = True
                            _is_dup_em = _send_nc.check_recent_duplicate(
                                _c_dup, segment_id=sid_em,
                                message_text=em_subject, channel="email",
                                within_hours=24)
                        if _is_dup_em:
                            st.error("🚫 إيميل بنفس العنوان أُرسل لهذه الشريحة "
                                     "خلال آخر 24 ساعة. غيّر العنوان أو الشريحة.")
                            st.stop()
                        prog = st.progress(0.0, text="بدء الإرسال...")
                        def _cbe(done, total):
                            try:
                                prog.progress(min(1.0, done/max(1,total)),
                                              text=f"تم {done}/{total}")
                            except Exception:
                                pass
                        try:
                            with get_conn() as _c:
                                _c.autocommit = True
                                res = _send_nc.send_email_broadcast(
                                    _c, segment_id=sid_em,
                                    subject=em_subject, body_html=em_body_html,
                                    banner_url=em_banner or "",
                                    variant_b_subject=vb_subj,
                                    variant_b_html=vb_html,
                                    rate_per_sec=rate_em,
                                    freq_cap_per_day=cap_em,
                                    progress_cb=_cbe)
                            if res["failed"] == 0:
                                st.success(f"✅ نجح {res['sent']} إيميل "
                                           f"(حملة #{res['broadcast_id']})")
                                st.balloons()
                            else:
                                st.warning(f"⚠️ نجح {res['sent']} ، فشل {res['failed']} "
                                           f"(حملة #{res['broadcast_id']})")
                            st.cache_data.clear()
                        except Exception as _e:
                            st.error(f"فشل الإرسال: {_e}")

        with col_prev:
            st.subheader("👁️ معاينة")
            _prev_banner = (
                f'<img src="{em_banner}" style="width:100%;border-radius:6px;'
                f'margin-bottom:14px;display:block;" />' if em_banner else "")
            _prev_body = em_body_html or (
                '<p style="color:#9CA3AF;font-style:italic;">'
                'اكتب المحتوى للمعاينة...</p>')
            _prev_subj = em_subject or "عنوان الحملة"
            preview_html = f"""<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8">
<style>*{{box-sizing:border-box;margin:0;padding:0;}}body{{background:#ECEAE4;font-family:Arial;padding:12px;}}
.wrap{{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 14px rgba(0,0,0,0.1);}}
.hdr{{background:linear-gradient(135deg,#10B981,#059669);padding:18px 24px;text-align:center;color:#fff;}}
.hdr h1{{font-size:16px;margin:0;}}.subj{{background:#E8F5E9;padding:8px 20px;font-size:12px;color:#374151;border-bottom:1px solid #E5E7EB;}}
.body{{padding:20px 24px;font-size:13px;color:#1F2937;line-height:1.65;}}
.ftr{{background:#F5F5F0;padding:12px;text-align:center;font-size:11px;color:#9CA3AF;border-top:1px solid #E5E7EB;}}
</style></head><body><div class="wrap"><div class="hdr"><h1>نبض الصفقات 🌐</h1></div>
<div class="subj"><strong>📌 الموضوع:</strong> {_prev_subj}</div>
<div class="body">{_prev_banner}{_prev_body}</div>
<div class="ftr">نبض الصفقات | dealpulseksa.com</div></div></body></html>"""
            components.html(preview_html, height=420, scrolling=True)

        st.divider()
        with st.expander("📜 آخر 10 حملات بريدية"):
            try:
                with get_conn() as _c:
                    _c.autocommit = True
                    em_hist = pd.read_sql("""
                        SELECT el.id           AS "#",
                               (el.sent_at AT TIME ZONE 'Asia/Riyadh')::text AS "وقت (KSA)",
                               s.name          AS "الشريحة",
                               el.subject      AS "العنوان",
                               el.delivery_count AS "المستهدفون",
                               el.sent_count   AS "نجح",
                               el.failed_count AS "فشل",
                               el.status       AS "الحالة"
                        FROM email_logs el
                        LEFT JOIN audience_segments s ON s.id = el.segment_id
                        ORDER BY el.sent_at DESC LIMIT 10
                    """, _c)
                if em_hist.empty:
                    st.info("لا حملات بريدية سابقة.")
                else:
                    st.dataframe(em_hist, width="stretch", hide_index=True)
            except Exception as _e:
                st.error(f"تعذّر تحميل السجل: {_e}")

    # ═══════════════════════════════════════════════════════════════════════
    # تبويب 3 — الحملات المجدولة
    # ═══════════════════════════════════════════════════════════════════════
    with tab_sched:
        st.subheader("⏰ الحملات المجدولة")
        st.caption("أنشئ حملة تنطلق تلقائياً في وقت محدد، أو متكرّرة يومياً/أسبوعياً.")

        with st.expander("➕ إنشاء جدولة جديدة", expanded=False):
            sc_name = st.text_input("📝 اسم الجدولة:",
                placeholder="مثلاً: تذكير صباحي يومي",
                key="nc_sc_name")
            sc_channel = st.radio("القناة", ["telegram","email"],
                format_func=lambda x: "📱 تليجرام" if x=="telegram" else "📧 إيميل",
                horizontal=True, key="nc_sc_ch")
            sc_seg = _seg_picker("nc_sc", channel_filter=sc_channel)
            if sc_channel == "telegram":
                sc_text = st.text_area("✍️ نص الرسالة:", height=120, key="nc_sc_text")
                sc_img  = st.text_input("🖼️ رابط صورة (اختياري):", key="nc_sc_img")
                sc_payload = {"text": sc_text, "image_url": sc_img or None}
            else:
                sc_subj = st.text_input("📌 العنوان:", key="nc_sc_subj")
                sc_html = st.text_area("📝 المحتوى (HTML/نص):", height=140, key="nc_sc_html")
                sc_bnr  = st.text_input("🖼️ بانر (اختياري):", key="nc_sc_bnr")
                sc_payload = {"subject": sc_subj,
                              "body_html": sc_html.replace("\n","<br>") if sc_html else "",
                              "banner_url": sc_bnr or ""}
            sc_type = st.selectbox("التكرار", ["once","daily","weekly"],
                format_func=lambda x: {"once":"مرة واحدة",
                                       "daily":"يومياً",
                                       "weekly":"أسبوعياً"}[x],
                key="nc_sc_type")
            sc_run_at = None
            if sc_type == "once":
                _d = st.date_input("📅 تاريخ الإطلاق (KSA)", key="nc_sc_date")
                _t = st.time_input("🕐 الساعة (KSA)", key="nc_sc_time", step=60)
                if _d and _t:
                    sc_run_at = f"{_d} {_t} Asia/Riyadh"
            if st.button("💾 جدول الحملة", key="nc_sc_create",
                         width="stretch", type="primary"):
                if not sc_name:
                    st.error("أدخل اسماً للجدولة.")
                elif not sc_seg:
                    st.error("اختر شريحة (إجبارية للجدولة).")
                else:
                    try:
                        with get_conn() as _c:
                            _c.autocommit = True
                            new_sid = _send_nc.schedule_broadcast(
                                _c, name=sc_name, segment_id=sc_seg,
                                channel=sc_channel,
                                message_payload=sc_payload,
                                schedule_type=sc_type,
                                run_at=sc_run_at)
                        st.success(f"✅ أُنشئت جدولة #{new_sid}")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"فشل: {_e}")

        st.divider()

        # قائمة الجداول
        try:
            with get_conn() as _c:
                _c.autocommit = True
                schedules = _send_nc.list_schedules(_c)
        except Exception as _e:
            schedules = []
            st.error(f"تعذّر التحميل: {_e}")

        if not schedules:
            st.info("لا حملات مجدولة.")
        else:
            for sch in schedules:
                with st.container(border=True):
                    sc1, sc2, sc3, sc4 = st.columns([3, 2, 1, 1])
                    with sc1:
                        _en_icon = "🟢" if sch["enabled"] else "⚪"
                        st.markdown(f"{_en_icon} **{sch['name'] or '—'}** "
                                    f"({sch['channel']})")
                        st.caption(f"شريحة: {sch.get('segment_name') or '—'} · "
                                   f"تكرار: {sch['schedule_type']} · "
                                   f"تالي: {sch.get('next_run_at') or '—'}")
                    with sc2:
                        st.caption(f"آخر تشغيل: {sch.get('last_run_at') or 'لم يُشغّل بعد'}")
                    with sc3:
                        _btn_lbl = "⏸️ أوقف" if sch["enabled"] else "▶️ شغّل"
                        if st.button(_btn_lbl, key=f"nc_sc_t_{sch['id']}",
                                     width="stretch"):
                            with get_conn() as _c:
                                _c.autocommit = True
                                _send_nc.toggle_schedule(_c, sch["id"],
                                                          not sch["enabled"])
                            st.rerun()
                    with sc4:
                        if st.button("🗑️", key=f"nc_sc_d_{sch['id']}",
                                     width="stretch"):
                            with get_conn() as _c:
                                _c.autocommit = True
                                _send_nc.delete_schedule(_c, sch["id"])
                            st.rerun()

        st.divider()
        if st.button("🔄 شغّل المستحقّة الآن (يدوياً)",
                     key="nc_sc_run_now", width="stretch"):
            try:
                with get_conn() as _c:
                    _c.autocommit = True
                    res = _send_nc.process_due_schedules(_c)
                if res:
                    st.success(f"✅ شُغّلت {len(res)} جدولة")
                    st.json(res)
                else:
                    st.info("لا جداول مستحقّة حالياً.")
            except Exception as _e:
                st.error(f"فشل: {_e}")

    # ═══════════════════════════════════════════════════════════════════════
    # تبويب 4 — تقارير الحملات المفصّلة
    # ═══════════════════════════════════════════════════════════════════════
    with tab_reports:
        st.subheader("📊 تقرير مفصّل لحملة")
        rp_ch = st.radio("القناة", ["telegram","email"],
            format_func=lambda x: "📱 تليجرام" if x=="telegram" else "📧 إيميل",
            horizontal=True, key="nc_rp_ch")
        try:
            with get_conn() as _c:
                _c.autocommit = True
                table = "broadcast_logs" if rp_ch == "telegram" else "email_logs"
                msg_col = "message_text" if rp_ch == "telegram" else "subject"
                rp_df = pd.read_sql(
                    f"SELECT id, "
                    f"  (sent_at AT TIME ZONE 'Asia/Riyadh')::text AS sent_at, "
                    f"  {msg_col} AS title, "
                    f"  delivery_count, sent_count, failed_count, status "
                    f"FROM {table} ORDER BY sent_at DESC LIMIT 50", _c)
        except Exception as _e:
            rp_df = pd.DataFrame()
            st.error(f"تعذّر التحميل: {_e}")

        if rp_df.empty:
            st.info("لا حملات مسجّلة.")
        else:
            rp_opts = [(int(r["id"]),
                        f"#{r['id']} · {str(r['sent_at'])[:16]} · "
                        f"{(r['title'] or '')[:40]} · "
                        f"{r['sent_count'] or 0}/{r['delivery_count'] or 0}")
                       for _, r in rp_df.iterrows()]
            rp_sel = st.selectbox("اختر حملة", rp_opts,
                format_func=lambda x: x[1], key="nc_rp_sel")
            if rp_sel and st.button("📊 اعرض التقرير", key="nc_rp_show",
                                     width="stretch"):
                with get_conn() as _c:
                    _c.autocommit = True
                    rep = _send_nc.broadcast_report(_c, rp_sel[0], rp_ch)
                if rep.get("error"):
                    st.error(rep["error"])
                else:
                    # ── سطر 1: إجماليات الإرسال ──
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("👥 المستهدفون", rep.get("delivery_count") or 0)
                    mc2.metric("✅ نجح", rep.get("sent_count") or 0)
                    mc3.metric("❌ فشل", rep.get("failed_count") or 0)
                    _total = (rep.get("sent_count") or 0) + (rep.get("failed_count") or 0)
                    _rate = (rep.get("sent_count") or 0) / _total * 100 if _total else 0
                    mc4.metric("📈 نسبة النجاح", f"{_rate:.1f}%")

                    # ── سطر 2: التفاعل (Open + Click) ──
                    eng = rep.get("engagement", {}) or {}
                    ec1, ec2, ec3, ec4 = st.columns(4)
                    if rp_ch == "email":
                        _orate = eng.get("open_rate")
                        ec1.metric("📬 فتح فريد", eng.get("unique_opens", 0))
                        ec2.metric("📊 Open Rate",
                                   f"{_orate:.1f}%" if _orate is not None else "—")
                    else:
                        ec1.metric("📬 فتح", "غير مدعوم",
                                   help="تليجرام API لا يكشف فتح الرسائل")
                        ec2.metric("📊 Open Rate", "—")
                    _crate = eng.get("click_rate")
                    ec3.metric("🖱️ نقرات فريدة", eng.get("unique_clicks", 0))
                    ec4.metric("📊 CTR",
                               f"{_crate:.1f}%" if _crate is not None else "—")

                    # تحذير لو tracking معطّل
                    if not eng.get("unique_clicks") and not eng.get("unique_opens"):
                        from api.utils.broadcast_tracker import is_tracking_enabled
                        if not is_tracking_enabled():
                            st.warning("⚠️ TRACKING_BASE_URL غير معرّف في البيئة — "
                                       "أرقام Open/Click لن تتجمّع. أضفه ثم أعد الإرسال.")

                    st.markdown("##### 📋 توزيع الحالة")
                    if rep.get("by_status"):
                        _bs = rep["by_status"]
                        _bs_labels = {
                            "queued":"⏳ في الطابور","sending":"📤 يُرسَل",
                            "sent":"✅ أُرسِل","failed":"❌ فشل",
                            "opened":"📬 فُتح","clicked":"🖱️ نُقر",
                            "skipped":"⏭️ مستبعد",
                        }
                        for _st_k, _st_v in _bs.items():
                            st.write(f"  - {_bs_labels.get(_st_k, _st_k)}: **{_st_v}**")

                    if rep.get("by_variant"):
                        st.markdown("##### 🅰️🅱️ مقارنة A/B")
                        _vars = rep["by_variant"]
                        if _vars:
                            _ab_df = pd.DataFrame.from_dict(_vars, orient="index")
                            _ab_df.index.name = "النسخة"
                            _ab_df = _ab_df.reset_index()
                            st.dataframe(_ab_df, hide_index=True, width="stretch")

                    if rep.get("top_links"):
                        st.markdown("##### 🔗 أعلى الروابط نقراً")
                        _tl_df = pd.DataFrame(rep["top_links"])
                        if not _tl_df.empty:
                            _tl_df = _tl_df.rename(columns={
                                "url":"الرابط","clicks":"إجمالي النقرات",
                                "unique_clickers":"ناقرون فريدون"})
                            st.dataframe(_tl_df, hide_index=True, width="stretch")
                        else:
                            st.caption("لا روابط مسجّلة في هذه الحملة.")

                    if rep.get("failure_samples"):
                        st.markdown("##### 🔍 عيّنة من حالات الفشل")
                        for _f in rep["failure_samples"]:
                            st.caption(f"  - `{_f['user']}` → {_f['error']}")

                    # ── الجدول المفصّل: كل مستلم على حدة ──
                    st.markdown("##### 👥 من شاف/نقر — تفاصيل كل مستلم")
                    st.caption("لمطابقة الأحداث مع المستخدمين الحقيقيين. "
                               "التوقيتات بتوقيت الرياض. النقرات الوهمية "
                               "(Telegram preview bot) مُستبعدة تلقائياً.")
                    try:
                        with get_conn() as _c_det:
                            _c_det.autocommit = True
                            details = _send_nc.broadcast_recipients_detail(
                                _c_det, rp_sel[0], rp_ch, limit=500)
                        if details:
                            _df = pd.DataFrame(details)
                            # تنسيق التوقيتات
                            for _tc in ("sent_at", "opened_at", "clicked_at"):
                                if _tc in _df.columns:
                                    _df[_tc] = pd.to_datetime(_df[_tc]).dt.strftime(
                                        "%Y-%m-%d %H:%M:%S")
                                    _df[_tc] = _df[_tc].replace("NaT", "—").fillna("—")
                            _stat_map = {"queued":"⏳","sending":"📤","sent":"✅",
                                         "failed":"❌","opened":"📬","clicked":"🖱️",
                                         "skipped":"⏭️"}
                            _df["status"] = _df["status"].map(_stat_map).fillna(
                                _df["status"])
                            _df = _df.rename(columns={
                                "user_id":"المعرّف", "name":"الاسم",
                                "handle":"اليوزر", "status":"الحالة",
                                "variant":"النسخة",
                                "sent_at":"وقت الإرسال (KSA)",
                                "opened_at":"وقت الفتح (KSA)",
                                "clicked_at":"وقت النقر (KSA)",
                                "open_count":"مرّات فتح", "click_count":"مرّات نقر",
                                "error_message":"خطأ",
                            })
                            # نخفي أعمدة فارغة (variant لو ما في A/B)
                            _drop = []
                            if "النسخة" in _df.columns and _df["النسخة"].isna().all():
                                _drop.append("النسخة")
                            if "خطأ" in _df.columns and _df["خطأ"].isna().all():
                                _drop.append("خطأ")
                            if _drop:
                                _df = _df.drop(columns=_drop)
                            st.dataframe(_df, hide_index=True, width="stretch")
                        else:
                            st.info("لا مستلمين بعد.")
                    except Exception as _e:
                        st.error(f"تعذّر تحميل التفاصيل: {_e}")

    # ═══════════════════════════════════════════════════════════════════════
    # تبويب 5 — قائمة الاستثناء (Don't-Send List)
    # ═══════════════════════════════════════════════════════════════════════
    with tab_excl:
        st.subheader("🚫 قائمة الاستثناء (لن يستلموا أي إشعار)")
        st.caption("مفيدة لـ: opt-out، شكاوى، اختبار، VIPs لا تزعجهم.")
        try:
            with get_conn() as _c:
                _c.autocommit = True
                excl_list = _send_nc.list_exclusions(_c)
        except Exception as _e:
            excl_list = []
            st.error(f"تعذّر تحميل القائمة: {_e}")

        with st.form("nc_excl_add", clear_on_submit=True):
            ec1, ec2, ec3, ec4 = st.columns([2, 3, 4, 1])
            with ec1:
                _excl_ch = st.selectbox("القناة", ["telegram","email","both"],
                    format_func=lambda x: {"telegram":"📱 تليجرام",
                                           "email":"📧 إيميل", "both":"📡 الكل"}[x],
                    key="nc_excl_ch")
            with ec2:
                _excl_id = st.text_input("المعرّف (telegram_id أو email):",
                                         key="nc_excl_id")
            with ec3:
                _excl_reason = st.text_input("السبب (اختياري)", key="nc_excl_reason")
            with ec4:
                st.markdown("&nbsp;")
                if st.form_submit_button("➕ أضف"):
                    if not _excl_id:
                        st.error("أدخل المعرّف.")
                    else:
                        with get_conn() as _c:
                            _c.autocommit = True
                            _send_nc.add_exclusion(_c, channel=_excl_ch,
                                user_identifier=_excl_id.strip(),
                                reason=_excl_reason or "")
                        st.success("أُضيف للاستثناء.")
                        st.rerun()

        if excl_list:
            df_excl = pd.DataFrame(excl_list)
            df_excl["channel"] = df_excl["channel"].map(
                {"telegram":"📱","email":"📧","both":"📡"}).fillna(df_excl["channel"])
            st.dataframe(df_excl[["id","channel","user_identifier","reason","added_at"]],
                         hide_index=True, width="stretch")
            _rem_id = st.number_input("معرّف صف للحذف (id من الجدول):",
                                      min_value=0, value=0, key="nc_excl_rem")
            if _rem_id and st.button("🗑️ احذف من قائمة الاستثناء"):
                with get_conn() as _c:
                    _c.autocommit = True
                    cur = _c.cursor()
                    cur.execute("DELETE FROM broadcast_exclusions WHERE id=%s",
                                (int(_rem_id),))
                st.success("حُذف.")
                st.rerun()
        else:
            st.info("لا استثناءات يدوية.")

        # ── المحظورون تلقائياً (وُسموا بعد فشل 403) ───────────────────────
        st.divider()
        st.subheader("🛑 المحظورون تلقائياً من البوت")
        st.caption("مستخدمو تليجرام رجع API لهم خطأ 403 → استُبعدوا تلقائياً "
                   "من كل حملة. يرجعون تلقائياً لو نجح إرسال لهم لاحقاً، "
                   "أو يدوياً بزر «أعد التفعيل».")
        try:
            with get_conn() as _c:
                _c.autocommit = True
                _blocked = _send_nc.list_blocked_telegram_users(_c, limit=200)
        except Exception as _e:
            _blocked = []
            st.error(f"تعذّر التحميل: {_e}")

        if not _blocked:
            st.info("لا محظورين حالياً 🎉")
        else:
            st.warning(f"⚠️ {len(_blocked)} مستخدم محظور — مستبعدون من كل الحملات")
            _df_blk = pd.DataFrame(_blocked)
            _df_blk["telegram_blocked_at"] = pd.to_datetime(
                _df_blk["telegram_blocked_at"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(
                _df_blk[["telegram_id","username","telegram_blocked_at","last_telegram_error"]],
                hide_index=True, width="stretch",
                column_config={
                    "telegram_id":         st.column_config.TextColumn("معرّف", width="small"),
                    "username":            st.column_config.TextColumn("اليوزر", width="small"),
                    "telegram_blocked_at": st.column_config.TextColumn("تاريخ الحظر", width="medium"),
                    "last_telegram_error": st.column_config.TextColumn("آخر خطأ"),
                })
            _unblk = st.text_input(
                "🔓 ألغِ الحظر يدوياً (أدخل telegram_id):",
                key="nc_unblk_id",
                help="مفيد لو تتوقّع أن المستخدم رجع للبوت بعد حذف.")
            if _unblk and st.button("✅ أعد تفعيله", key="nc_unblk_btn"):
                with get_conn() as _c:
                    _c.autocommit = True
                    if _send_nc.unblock_telegram_user(_c, _unblk.strip()):
                        st.success(f"أُعيد تفعيل {_unblk}")
                        st.rerun()
                    else:
                        st.error("لم يُعثر على المستخدم.")














# --- الصفحة السادسة عشرة: لوحة القيادة الإستراتيجية (Fixed Version) ---
elif page == "لوحة القيادة":
    page_title("🟢", "غرفة العمليات — متابعة لايف",
               "كل حركة في البوت والميني والموقع، لحظة بلحظة (توقيت السعودية)")

    # ── خرائط العرض ─────────────────────────────────────────────────────────
    _SRC_LBL = {"bot": "🤖 بوت", "telegram_miniapp": "📱 ميني", "web": "🌐 موقع"}
    _ACT_LBL = {
        "search": "🔍 بحث", "start": "▶️ بدأ المحادثة",
        "click_link": "🔗 فتح رابط المتجر", "copy_coupon": "📋 نسخ الكود",
        "view_store": "🏬 دخل متجر", "view_tag": "🏷️ تصفّح قسم",
        "view_sections": "📂 تصفّح الأقسام", "view_all": "📜 عرض الكل",
        "view_favorites": "⭐ عرض المفضلة", "favorite_add": "❤️ أضاف للمفضلة",
        "category_favorite_add": "❤️ أضاف قسماً للمفضلة",
        "request_code": "🙋 طلب كود", "reaction_heart": "💖 تفاعل",
        "lang_pick": "🌐 اختار اللغة", "code_report": "📣 أرسل بلاغ",
        "idle_warn": "⏰ تنبيه خمول", "idle_kick": "💤 إنهاء خمول",
        "idle_alert": "⏰ تنبيه", "end_session": "⏹️ نهاية جلسة",
        "unknown_input": "❓ إدخال غير مفهوم", "back": "↩️ رجوع",
    }
    # التصنيف — بمصطلحات المالك: نقر / بحث / نسخ / مفضلة / تصفّح
    _ACT_CAT = {
        "click_link": "🔗 نقر",
        "search": "🔍 بحث",
        "copy_coupon": "📋 نسخ",
        "request_code": "🙋 طلب",
        "favorite_add": "❤️ مفضلة", "category_favorite_add": "❤️ مفضلة",
        "view_favorites": "❤️ مفضلة", "reaction_heart": "❤️ مفضلة",
        "view_store": "👀 تصفّح", "view_tag": "👀 تصفّح",
        "view_sections": "👀 تصفّح", "view_all": "👀 تصفّح",
        "start": "👀 تصفّح", "lang_pick": "👀 تصفّح",
        "code_report": "📣 بلاغ",
    }
    _MEANINGFUL = ["search", "start", "click_link", "copy_coupon", "view_store",
                   "view_tag", "view_sections", "view_all", "view_favorites",
                   "favorite_add", "category_favorite_add", "request_code",
                   "reaction_heart", "lang_pick"]
    _SYS_ACTS = ["idle_warn", "idle_kick", "idle_alert", "end_session",
                 "unknown_input", "back"]

    # ── أدوات التحكم ────────────────────────────────────────────────────────
    _c1, _c2, _c3, _c4 = st.columns([1, 1, 1.3, 1.6])
    live = _c1.toggle("🔴 بث مباشر", value=True, key="cmd_live")
    interval = _c2.selectbox("التحديث", [5, 10, 30],
                             format_func=lambda x: f"كل {x} ثانية",
                             index=1, key="cmd_interval")
    limit = _c3.slider("عدد الأحداث (للعرض)", 50, 1000, 200, step=50, key="cmd_limit")
    show_sys = _c4.checkbox("إظهار أحداث النظام (خمول/جلسات)",
                            value=False, key="cmd_show_sys")

    # ── فلتر الفترة (للعرض وللتحميل) ────────────────────────────────────────
    _ksa_today = (datetime.datetime.utcnow() + timedelta(hours=3)).date()
    _dr = st.date_input(
        "📅 الفترة (من → إلى) — تُطبَّق على العرض وعلى تحميل الإكسل",
        value=(_ksa_today - timedelta(days=7), _ksa_today),
        max_value=_ksa_today, key="cmd_range", format="YYYY-MM-DD")
    if isinstance(_dr, (list, tuple)) and len(_dr) == 2:
        d_from, d_to = _dr
    else:
        _one = _dr[0] if isinstance(_dr, (list, tuple)) else _dr
        d_from = d_to = _one

    acts = _MEANINGFUL + (_SYS_ACTS if show_sys else [])
    _KSA = "AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh'"

    # الهدف الحقيقي للحركة: متجر (store_id) أو قسم (tag: داخل details) أو لا شيء
    def _target(store_id, details):
        if isinstance(store_id, str) and store_id.strip() and store_id != "—":
            return store_id
        d = details.strip() if isinstance(details, str) else ""
        if d.startswith("tag:"):
            return "🏷️ " + d[4:]
        return "—"

    # تنظيف التفاصيل من العلامات الداخلية وتعريب سياق الترند
    def _clean_detail(details):
        d = details.strip() if isinstance(details, str) else ""
        if d.startswith("tag:") or d.startswith("user:") or d.startswith("via_cloak"):
            return ""
        if d == "trend:daily":
            return "🔥 ترند يومي"
        if d == "trend:weekly":
            return "🔥 ترند أسبوعي"
        return d

    def _render_live():
        try:
            conn = get_conn()
            conn.rollback()

            def get_stat(q, p=None):
                try:
                    return int(pd.read_sql(q, conn, params=p).iloc[0, 0])
                except Exception:
                    return 0

            tab_bot, tab_web = st.tabs(["🤖 بوت + ميني ويب", "🌐 الموقع"])

            # ════════════════ تبويب البوت + الميني ════════════════
            with tab_bot:
                m_users = get_stat(
                    "SELECT COUNT(*) FROM bot_users WHERE deleted_at IS NULL")
                m_active = get_stat("""
                    SELECT COUNT(DISTINCT user_id) FROM action_logs
                    WHERE source IN ('bot','telegram_miniapp')
                      AND action_time > NOW() - INTERVAL '1 hour'""")
                m_today = get_stat(f"""
                    SELECT COUNT(*) FROM action_logs
                    WHERE source IN ('bot','telegram_miniapp')
                      AND action_type = ANY(%s)
                      AND (action_time {_KSA})::date
                          = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Riyadh')::date""",
                                   (_MEANINGFUL,))
                m_complete = get_stat("""
                    SELECT COUNT(*) FROM bot_users b
                    WHERE b.deleted_at IS NULL
                      AND b.username IS NOT NULL AND b.username <> ''
                      AND EXISTS (SELECT 1 FROM web_users w
                                  WHERE LOWER(w.telegram_username)=LOWER(b.username))""")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("👥 مستخدمو البوت", f"{m_users}")
                k2.metric("🟢 نشطون (آخر ساعة)", f"{m_active}")
                k3.metric("⚡ أحداث اليوم", f"{m_today}")
                k4.metric("✅ مكتملون (مربوطون بالموقع)", f"{m_complete}")
                st.divider()

                df = pd.read_sql(f"""
                    SELECT * FROM (
                        SELECT (a.action_time {_KSA}) AS ts,
                               a.source, a.action_type, a.user_id,
                               NULLIF(b.username,'') AS username, b.name_en,
                               a.store_id AS store_id,
                               COALESCE(a.details,'') AS details
                        FROM action_logs a
                        LEFT JOIN bot_users b ON a.user_id = b.telegram_id
                        WHERE a.source IN ('bot','telegram_miniapp')
                          AND a.action_type = ANY(%s)
                          AND (a.action_time {_KSA})::date BETWEEN %s AND %s
                        UNION ALL
                        SELECT (r.created_at {_KSA}) AS ts,
                               r.source, 'code_report' AS action_type, r.tg_user_id AS user_id,
                               r.reporter_telegram_username AS username, NULL::text AS name_en,
                               r.store_id AS store_id,
                               COALESCE(NULLIF(r.issue_note,''), r.reported_code, '') AS details
                        FROM code_reports r
                        WHERE r.source IN ('bot','telegram_miniapp')
                          AND (r.created_at {_KSA})::date BETWEEN %s AND %s
                    ) q
                    ORDER BY ts DESC LIMIT 50000
                """, conn, params=(acts, d_from, d_to, d_from, d_to))

                if df.empty:
                    st.info("📭 لا توجد حركات في هذه الفترة.")
                else:
                    def _who(r):
                        u = r["username"]
                        if isinstance(u, str) and u.strip():
                            return "@" + u
                        ne = r["name_en"]
                        if isinstance(ne, str) and ne.strip():
                            return ne
                        if pd.notna(r["user_id"]):
                            return f"زائر #{int(r['user_id'])}"
                        return "— مجهول —"
                    show = pd.DataFrame({
                        "الوقت": pd.to_datetime(df["ts"]).dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "المنصة": df["source"].map(_SRC_LBL).fillna(df["source"]),
                        "المستخدم": df.apply(_who, axis=1),
                        "الحركة": df["action_type"].map(_ACT_LBL).fillna(df["action_type"]),
                        "التصنيف": df["action_type"].map(_ACT_CAT).fillna("⚙️ نظام"),
                        "المتجر / القسم": df.apply(lambda r: _target(r["store_id"], r["details"]), axis=1),
                        "التفاصيل": df["details"].map(_clean_detail),
                    })
                    st.caption(f"📊 المعروض على الشاشة: {min(len(show), limit)} من {len(show)} "
                               f"حدث في الفترة · زر التحميل يشمل كامل الفترة")
                    st.dataframe(show.head(limit), width="stretch", hide_index=True, height=460)
                    _xl = BytesIO()
                    with pd.ExcelWriter(_xl, engine="xlsxwriter") as _w:
                        show.to_excel(_w, index=False, sheet_name="Bot_Live")
                    st.download_button(
                        f"📥 تحميل كامل الفترة ({len(show)} حدث) — Excel", _xl.getvalue(),
                        f"LiveFeed_Bot_{d_from}_to_{d_to}.xlsx", key="dl_bot_live")

            # ════════════════ تبويب الموقع ════════════════
            with tab_web:
                w_users = get_stat("SELECT COUNT(*) FROM web_users")
                w_active = get_stat("""
                    SELECT COUNT(DISTINCT user_id) FROM action_logs
                    WHERE source='web' AND action_time > NOW() - INTERVAL '1 hour'""")
                w_today = get_stat(f"""
                    SELECT COUNT(*) FROM action_logs
                    WHERE source='web' AND action_type = ANY(%s)
                      AND (action_time {_KSA})::date
                          = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Riyadh')::date""",
                                   (_MEANINGFUL,))
                w_complete = get_stat("""
                    SELECT COUNT(*) FROM web_users
                    WHERE display_name IS NOT NULL AND display_name <> ''
                      AND email IS NOT NULL AND email <> ''
                      AND phone_number IS NOT NULL AND phone_number <> ''
                      AND gender IS NOT NULL AND birth_date IS NOT NULL""")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("🌐 مستخدمو الموقع", f"{w_users}")
                k2.metric("🟢 نشطون (آخر ساعة)", f"{w_active}")
                k3.metric("⚡ أحداث اليوم", f"{w_today}")
                k4.metric("✅ مكتملون (ملف كامل)", f"{w_complete}")
                st.caption("المكتمل = اسم + إيميل + جوال + ميلاد + جنس")
                st.divider()

                dfw = pd.read_sql(f"""
                    SELECT * FROM (
                        SELECT (a.action_time {_KSA}) AS ts, a.action_type,
                               COALESCE(NULLIF(w.display_name,''),'—') AS name,
                               COALESCE(w.email,'—') AS email,
                               COALESCE(w.phone_number,'—') AS phone,
                               a.store_id AS store_id,
                               COALESCE(a.details,'') AS details
                        FROM action_logs a
                        LEFT JOIN web_users w ON a.user_id = w.id
                        WHERE a.source='web' AND a.action_type = ANY(%s)
                          AND (a.action_time {_KSA})::date BETWEEN %s AND %s
                        UNION ALL
                        SELECT (r.created_at {_KSA}) AS ts, 'code_report' AS action_type,
                               COALESCE(NULLIF(r.reporter_name,''),'—') AS name,
                               COALESCE(NULLIF(r.reporter_email,''),'—') AS email,
                               COALESCE(NULLIF(r.reporter_phone,''),'—') AS phone,
                               r.store_id AS store_id,
                               COALESCE(NULLIF(r.issue_note,''), r.reported_code, '') AS details
                        FROM code_reports r
                        WHERE r.source='web'
                          AND (r.created_at {_KSA})::date BETWEEN %s AND %s
                    ) q
                    ORDER BY ts DESC LIMIT 50000
                """, conn, params=(acts, d_from, d_to, d_from, d_to))

                if dfw.empty:
                    st.info("📭 لا توجد حركات في هذه الفترة.")
                else:
                    showw = pd.DataFrame({
                        "الوقت": pd.to_datetime(dfw["ts"]).dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "الاسم": dfw["name"],
                        "الإيميل": dfw["email"],
                        "الجوال": dfw["phone"],
                        "الحركة": dfw["action_type"].map(_ACT_LBL).fillna(dfw["action_type"]),
                        "التصنيف": dfw["action_type"].map(_ACT_CAT).fillna("⚙️ نظام"),
                        "المتجر / القسم": dfw.apply(lambda r: _target(r["store_id"], r["details"]), axis=1),
                        "التفاصيل": dfw["details"].map(_clean_detail),
                    })
                    st.caption(f"📊 المعروض على الشاشة: {min(len(showw), limit)} من {len(showw)} "
                               f"حدث في الفترة · زر التحميل يشمل كامل الفترة")
                    st.dataframe(showw.head(limit), width="stretch", hide_index=True, height=460)
                    _xlw = BytesIO()
                    with pd.ExcelWriter(_xlw, engine="xlsxwriter") as _w:
                        showw.to_excel(_w, index=False, sheet_name="Web_Live")
                    st.download_button(
                        f"📥 تحميل كامل الفترة ({len(showw)} حدث) — Excel", _xlw.getvalue(),
                        f"LiveFeed_Web_{d_from}_to_{d_to}.xlsx", key="dl_web_live")

            _stamp = (datetime.datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
            st.caption(f"⏱️ آخر تحديث: {_stamp} (توقيت السعودية)"
                       + ("  ·  🔴 بث مباشر" if live else "  ·  ⏸️ متوقف"))
        except Exception as e:
            st.error(f"حدث خطأ فني: {e}")
        finally:
            if "conn" in locals():
                conn.close()

    _runner = st.fragment(run_every=(interval if live else None))(_render_live)
    _runner()
    if not live and st.button("🔄 تحديث الآن", key="cmd_manual_refresh"):
        st.rerun()


# --- الصفحة الثامنة عشرة: مركز الدعم الفني ---
elif page == "مركز الدعم":
    page_title("🎧", "مركز إدارة الدعم الفني",
               "رسائل العملاء من البوت والميني والموقع — ردّك يُسلَّم لهم عبر تلجرام")

    _sc1, _sc2, _sc3 = st.columns([1, 1, 2])
    sup_live = _sc1.toggle("🔴 لايف", value=True, key="sup_live")
    sup_interval = _sc2.selectbox("التحديث", [5, 15, 30],
                                  format_func=lambda x: f"كل {x} ثانية",
                                  index=1, key="sup_interval")
    if _sc3.button("🔄 تحديث الآن", key="sup_refresh", width="stretch"):
        st.rerun()

    _SUP_SRC = {"bot": "📱 بوت", "telegram_miniapp": "🔹 ميني", "web": "🌐 موقع"}
    _BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

    def _tg_send(chat_id, text):
        """يسلّم رد الدعم للمستخدم عبر Telegram Bot API مباشرة."""
        if not _BOT_TOKEN:
            return False, "BOT_TOKEN غير مضبوط في بيئة الداشبورد"
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
                json={"chat_id": int(chat_id),
                      "text": f"🆘 *رد فريق الدعم:*\n\n{text}",
                      "parse_mode": "Markdown"},
                timeout=10)
            j = r.json()
            return (True, "تم") if j.get("ok") else (False, j.get("description", "فشل"))
        except Exception as ex:
            return False, str(ex)

    def _sup_ident(r):
        if isinstance(r["username"], str) and r["username"].strip():
            return "@" + r["username"]
        if isinstance(r["contact_name"], str) and r["contact_name"].strip():
            return r["contact_name"]
        if isinstance(r["contact_email"], str) and r["contact_email"].strip():
            return r["contact_email"]
        if pd.notna(r["telegram_id"]):
            return f"تيليجرام #{int(r['telegram_id'])}"
        return "— مجهول —"

    _OPEN_SQL = """
        SELECT id,
               (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh') AS ts,
               COALESCE(source,'bot') AS source, telegram_id, username,
               contact_name, contact_email, contact_phone, message, reply_text
        FROM support_tickets
        WHERE status = 'open'
        ORDER BY created_at DESC
    """

    tab_inbox, tab_resolved = st.tabs(["📥 الرسائل الواردة", "✅ رسائل تم حلها"])

    # ════════════ صندوق الوارد ════════════
    with tab_inbox:
        # ── جدول لايف (fragment) — يتحدّث تلقائياً، بلا قطع لخانة الكتابة ──
        def _live_inbox():
            c = get_conn(); c.rollback()
            try:
                d = pd.read_sql(_OPEN_SQL, c)
            finally:
                c.close()
            _stamp = (datetime.datetime.utcnow() + timedelta(hours=3)).strftime("%H:%M:%S")
            st.subheader(f"📬 طلبات مفتوحة ({len(d)})")
            if d.empty:
                st.success("🎉 لا توجد طلبات دعم معلقة.")
            else:
                _view = pd.DataFrame({
                    "#": d["id"],
                    "الوقت": pd.to_datetime(d["ts"]).dt.strftime("%Y-%m-%d %H:%M"),
                    "المصدر": d["source"].map(_SUP_SRC).fillna(d["source"]),
                    "المُرسِل": d.apply(_sup_ident, axis=1),
                    "الإيميل": d["contact_email"].fillna("—"),
                    "الجوال": d["contact_phone"].fillna("—"),
                    "الرسالة": d["message"],
                })
                st.dataframe(_view, width="stretch", hide_index=True, height=280)
            st.caption(f"⏱️ آخر تحديث: {_stamp}"
                       + ("  ·  🔴 لايف" if sup_live else "  ·  ⏸️ متوقف"))
        st.fragment(run_every=(sup_interval if sup_live else None))(_live_inbox)()

        st.divider()
        # ── نموذج الرد (ثابت — لا ينقطع أثناء التحديث التلقائي) ──
        _rconn = get_conn(); _rconn.rollback()
        try:
            df_open = pd.read_sql(_OPEN_SQL, _rconn)
            if df_open.empty:
                st.info("لا توجد تذاكر مفتوحة للرد عليها حالياً.")
            else:
                st.subheader("💬 الرد على تذكرة")
                sel_id = st.selectbox(
                    "اختر تذكرة (بالرقم):", df_open["id"].tolist(), key="sup_pick",
                    format_func=lambda i: f"#{i} · "
                        + _sup_ident(df_open[df_open['id'] == i].iloc[0]))
                row = df_open[df_open["id"] == sel_id].iloc[0]

                ic1, ic2, ic3 = st.columns(3)
                ic1.metric("المصدر", _SUP_SRC.get(row["source"], row["source"]))
                ic2.metric("اليوزر/الاسم", _sup_ident(row))
                _tgid = int(row["telegram_id"]) if pd.notna(row["telegram_id"]) else None
                ic3.metric("Telegram ID", str(_tgid) if _tgid else "—")
                _em = row["contact_email"] if isinstance(row["contact_email"], str) else None
                if _em:
                    st.caption(f"📧 {_em}" + (f"  ·  📱 {row['contact_phone']}"
                               if isinstance(row['contact_phone'], str) else ""))
                st.info(f"**رسالة العميل:**\n\n{row['message']}")
                if isinstance(row["reply_text"], str) and row["reply_text"].strip():
                    with st.expander("🧵 ردودك السابقة على هذه التذكرة", expanded=False):
                        st.text(row["reply_text"])

                _ver = st.session_state.get("sup_reply_ver", 0)
                reply_text = st.text_area("اكتب ردك:", key=f"sup_reply_{sel_id}_{_ver}",
                                          placeholder="أهلاً بك، بخصوص استفسارك...")
                can_tg = _tgid is not None
                if not can_tg:
                    st.warning("⚠️ تذكرة من الموقع بلا حساب تلجرام — الرد لن يُسلَّم "
                               "تلقائياً؛ تواصل عبر الإيميل أعلاه (يُحفظ ردك).")

                _b1, _b2 = st.columns(2)
                if _b1.button("📨 إرسال الرد (تبقى مفتوحة)", width="stretch", key="sup_send"):
                    _rt = (reply_text or "").strip()
                    if not _rt:
                        st.error("اكتب الرد أولاً.")
                    else:
                        delivered, dmsg = (False, "—")
                        if can_tg:
                            delivered, dmsg = _tg_send(_tgid, _rt)
                        _ts = (datetime.datetime.utcnow() + timedelta(hours=3)).strftime("%m-%d %H:%M")
                        _cur = _rconn.cursor()
                        _cur.execute("""
                            UPDATE support_tickets
                            SET reply_text = COALESCE(reply_text || chr(10), '') || %s,
                                replied_at = NOW(), delivered = %s
                            WHERE id = %s
                        """, (f"[{_ts}] {_rt}", delivered, int(sel_id)))
                        _rconn.commit()
                        st.session_state["sup_reply_ver"] = _ver + 1
                        if can_tg and delivered:
                            st.success("✅ أُرسل الرد عبر تلجرام — التذكرة تبقى مفتوحة للمتابعة.")
                        elif can_tg and not delivered:
                            st.error(f"⚠️ حُفظ الرد لكن تعذّر التسليم عبر تلجرام: {dmsg}")
                        else:
                            st.info("✅ حُفظ الرد (تواصل بالإيميل — لا تلجرام).")
                        st.rerun()

                if _b2.button("🔒 إغلاق التذكرة", width="stretch", key="sup_close"):
                    _cur = _rconn.cursor()
                    _cur.execute("UPDATE support_tickets SET status='resolved' WHERE id=%s",
                                 (int(sel_id),))
                    _rconn.commit()
                    st.success("🔒 أُغلقت التذكرة ونُقلت للأرشيف.")
                    st.balloons()
                    st.rerun()
        except Exception as e:
            st.error(f"خطأ في الرد: {e}")
        finally:
            _rconn.close()

    # ════════════ الأرشيف ════════════
    with tab_resolved:
        st.subheader("📚 أرشيف الدعم")
        _aconn = get_conn(); _aconn.rollback()
        try:
            df_res = pd.read_sql("""
                SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh') AS ts,
                       COALESCE(source,'bot') AS source, username, contact_email,
                       message, reply_text,
                       CASE WHEN delivered THEN '✅ سُلّم' ELSE '—' END AS deliv
                FROM support_tickets
                WHERE status = 'resolved'
                ORDER BY replied_at DESC NULLS LAST, created_at DESC
            """, _aconn)
            if df_res.empty:
                st.caption("الأرشيف فارغ حالياً.")
            else:
                _resv = pd.DataFrame({
                    "الوقت": pd.to_datetime(df_res["ts"]).dt.strftime("%Y-%m-%d %H:%M"),
                    "المصدر": df_res["source"].map(_SUP_SRC).fillna(df_res["source"]),
                    "المُرسِل": df_res["username"].fillna(df_res["contact_email"]).fillna("—"),
                    "الرسالة": df_res["message"],
                    "الرد": df_res["reply_text"].fillna("—"),
                    "التسليم": df_res["deliv"],
                })
                st.dataframe(_resv, width="stretch", hide_index=True, height=400)
        except Exception as e:
            st.error(f"خطأ في الأرشيف: {e}")
        finally:
            _aconn.close()






















# ==============================================================================
# --- استوديو المحتوى: محرك بوسترات نبض الصفقات (Brand-Locked Poster Engine) ---
# ==============================================================================
elif page == "استوديو المحتوى":
    page_title("🎨", "استوديو الإبداع — محرك البوسترات")
    st.caption("ارفع لوقو المتجر، اكتب الخصم والكود، واحصل على بوستر فاخر بهوية نبض الصفقات الموحّدة. مقاس ماستر 1080×1080.")

    import io
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import arabic_reshaper
    from bidi.algorithm import get_display

    # ─── ثوابت الهوية (مقفولة — لا يلمسها المستخدم) ─────────────────────────────
    _CANVAS = 1080
    _STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
    _FONT_AR = os.path.join(_STUDIO_DIR, "NotoSansArabic-Bold.ttf")
    _ARCHIVE_DIR = os.path.join(_STUDIO_DIR, "posters_archive")
    os.makedirs(_ARCHIVE_DIR, exist_ok=True)

    # لوحة الألوان: نسخة Apple/Keynote — كريمي فاخر + زمردي عميق
    _STUDIO_BG_TOP     = (250, 250, 248)   # cream
    _STUDIO_BG_BOTTOM  = (232, 240, 234)   # mint-cream
    _STUDIO_EMERALD    = (16, 185, 129)
    _STUDIO_EMERALD_DK = (5, 122, 85)
    _STUDIO_INK        = (31, 41, 55)
    _STUDIO_INK_SOFT   = (107, 114, 128)
    _STUDIO_PILL_BG    = (15, 23, 35)
    _STUDIO_PILL_FG    = (255, 255, 255)

    _AR_RESHAPER = arabic_reshaper.ArabicReshaper(configuration={
        'delete_harakat': False, 'support_ligatures': True,
    })

    def _ar(text: str) -> str:
        """يهيّئ النص العربي لـ Pillow (تشكيل + bidi)."""
        try:
            return get_display(_AR_RESHAPER.reshape(str(text)))
        except Exception:
            return str(text)

    def _font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
        """خط نوتو السعودي العربي — متغيّر الوزن. 700=Bold، 900=Black."""
        try:
            f = ImageFont.truetype(_FONT_AR, size)
            try:
                # axis order: [Weight, Width]
                f.set_variation_by_axes([weight, 100])
            except Exception:
                pass
            return f
        except Exception:
            return ImageFont.load_default()

    def _vgradient(w: int, h: int, top, bottom) -> Image.Image:
        base = Image.new("RGB", (w, h), top)
        draw = ImageDraw.Draw(base)
        for y in range(h):
            t = y / max(h - 1, 1)
            r = int(top[0] * (1 - t) + bottom[0] * t)
            g = int(top[1] * (1 - t) + bottom[1] * t)
            b = int(top[2] * (1 - t) + bottom[2] * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        return base

    def _soft_blob(img: Image.Image, cx: int, cy: int, radius: int, color, alpha: int):
        """يرسم blob أخضر زمردي مع blur ناعم — توهج فاخر."""
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*color, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(radius // 3))
        img.paste(layer, (0, 0), layer)

    def _drop_shadow(img: Image.Image, x: int, y: int, w: int, h: int, radius: int = 18, blur: int = 22, alpha: int = 55):
        """ظل ناعم تحت كارت زجاجي."""
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        d.rounded_rectangle([x, y + 8, x + w, y + h + 8], radius=radius, fill=(0, 0, 0, alpha))
        sh = sh.filter(ImageFilter.GaussianBlur(blur))
        img.paste(sh, (0, 0), sh)

    def _smart_crop_logo(img: Image.Image, white_threshold: int = 245) -> Image.Image:
        """يقص الـ whitespace/الشفافية حول اللوقو — يخلّيه يملأ الكارت."""
        img = img.convert("RGBA")
        # محاولة 1: bbox للـ alpha (PNG شفاف)
        alpha = img.split()[-1]
        bbox = alpha.getbbox()
        full = (
            bbox is not None
            and bbox[2] - bbox[0] >= img.width * 0.97
            and bbox[3] - bbox[1] >= img.height * 0.97
        )
        if bbox is not None and not full:
            return img.crop(bbox)
        # محاولة 2: خلفية بيضاء/فاتحة — نقص حسب البكسلات غير البيضاء
        try:
            gray = img.convert("RGB").convert("L")
            mask = gray.point(lambda p: 255 if p < white_threshold else 0)
            bbox2 = mask.getbbox()
            if bbox2 is not None:
                return img.crop(bbox2)
        except Exception:
            pass
        return img

    def _fit_logo(logo_bytes: bytes, box_w: int, box_h: int) -> Image.Image | None:
        """يفتح اللوقو، يقص حوافه الفارغة، ويصغّره ليملأ الصندوق."""
        try:
            lg = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            lg = _smart_crop_logo(lg)
            lg.thumbnail((box_w, box_h), Image.LANCZOS)
            return lg
        except Exception:
            return None

    def _cover_logo(logo_bytes: bytes, box_w: int, box_h: int) -> Image.Image | None:
        """يكبّر/يصغّر الصورة لتملأ الكارت بالكامل (cover) مع قص مركزي —
        أي صورة تملأ المقاس 540×400 بدون تشويه نسبتها."""
        try:
            lg = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            w, h = lg.size
            scale = max(box_w / w, box_h / h)
            nw, nh = max(int(w * scale + 0.5), box_w), max(int(h * scale + 0.5), box_h)
            lg = lg.resize((nw, nh), Image.LANCZOS)
            left, top = (nw - box_w) // 2, (nh - box_h) // 2
            return lg.crop((left, top, left + box_w, top + box_h))
        except Exception:
            return None

    def _remove_bg_api(image_bytes: bytes):
        """يشيل خلفية الصورة عبر remove.bg API → PNG شفاف.
        يرجع (bytes, None) عند النجاح أو (None, رسالة الخطأ)."""
        api_key = os.getenv("REMOVEBG_API_KEY")
        if not api_key:
            return None, "لم يُضبط REMOVEBG_API_KEY في بيئة الداشبورد"
        try:
            r = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                headers={"X-Api-Key": api_key},
                files={"image_file": ("logo.png", image_bytes)},
                data={"size": "auto"},
                timeout=30,
            )
            if r.status_code == 200:
                return r.content, None
            try:
                err = r.json().get("errors", [{}])[0].get("title", f"HTTP {r.status_code}")
            except Exception:
                err = f"HTTP {r.status_code}"
            return None, err
        except Exception as ex:
            return None, str(ex)

    def _center_text(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill, canvas_w: int = _CANVAS):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((canvas_w - tw) // 2 - bbox[0], y - bbox[1]), text, font=font, fill=fill)

    def _render_poster(
        store_name: str,
        store_logo_bytes: bytes | None,
        discount_label: str,
        discount_value: str,
        code: str,
        tagline: str,
        deal_pulse_logo_bytes: bytes | None,
        card_w: int = 540,
        card_h: int = 400,
        logo_scale: int = 100,
    ) -> bytes:
        """يبني البوستر الكامل ويرجعه PNG bytes. الكارت 540×400، وlogo_scale% يحدّد حجم اللوقو فيه."""
        W = H = _CANVAS
        # حماية: نمنع تجاوز الكنفس أو الطغيان على العناصر تحت الكارت
        card_w = max(100, min(int(card_w), W - 40))
        card_h = max(100, min(int(card_h), 600))
        img = _vgradient(W, H, _STUDIO_BG_TOP, _STUDIO_BG_BOTTOM).convert("RGBA")

        # توهج زمردي فاخر — زاويتان متقابلتان
        _soft_blob(img, int(W * 0.85), int(H * 0.18), 280, _STUDIO_EMERALD, 60)
        _soft_blob(img, int(W * 0.15), int(H * 0.88), 320, _STUDIO_EMERALD_DK, 45)

        draw = ImageDraw.Draw(img)

        # شريط علوي رفيع: "عرض حصري" بأسلوب Keynote
        small_label = _ar("عرض حصري")
        f_label = _font(28)
        _center_text(draw, small_label, 70, f_label, _STUDIO_INK_SOFT)

        # خط تحت العنوان الصغير
        line_w = 90
        draw.rounded_rectangle(
            [W // 2 - line_w // 2, 118, W // 2 + line_w // 2, 122],
            radius=2, fill=_STUDIO_EMERALD,
        )

        # كارت موحّد: مستطيل أبيض + إطار زمردي ثابت = نمط واحد لكل المتاجر
        # الأبعاد قابلة للتحكّم من الواجهة (الأصل 540×400)
        card_x = (W - card_w) // 2
        card_y = 150
        _drop_shadow(img, card_x, card_y, card_w, card_h, radius=36, blur=35, alpha=55)

        # خلفية الكارت الأبيض
        glass = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
        mask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w, card_h], radius=36, fill=255)
        img.paste(glass, (card_x, card_y), mask)

        # صورة/لوقو المتجر — دائماً contain: اللوقو كامل بلا أي قص.
        # النسبة logo_scale% تتحكّم بحجمه داخل الكارت فقط (100% = أكبر حجم بلا قص).
        if store_logo_bytes:
            _pct = max(20, min(int(logo_scale), 100)) / 100.0
            logo = _fit_logo(store_logo_bytes, int(card_w * _pct), int(card_h * _pct))
            if logo is not None:
                lx = card_x + (card_w - logo.width) // 2
                ly = card_y + (card_h - logo.height) // 2
                img.paste(logo, (lx, ly), logo)
        if not store_logo_bytes:
            f_store = _font(96, weight=800)
            _center_text(draw, _ar(store_name or "متجرك"), card_y + card_h // 2 - 50, f_store, _STUDIO_INK)

        # إطار موحّد ثابت — يطبع فوق كل شيء = نفس الـ frame لكل المتاجر بغض النظر عن اللوقو
        ImageDraw.Draw(img).rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + card_h],
            radius=36, outline=_STUDIO_EMERALD_DK, width=5,
        )

        # اسم المتجر تحت الكارت (لو فيه لوقو)
        if store_logo_bytes and store_name:
            f_store_sm = _font(32)
            _center_text(draw, _ar(store_name), card_y + card_h + 18, f_store_sm, _STUDIO_INK)
            block_y = card_y + card_h + 75
        else:
            block_y = card_y + card_h + 40

        # كتلة الخصم — البطل
        f_disc_lbl = _font(32, weight=600)
        _center_text(draw, _ar(discount_label or "خصم يصل إلى"), block_y, f_disc_lbl, _STUDIO_INK_SOFT)

        f_disc_num = _font(170, weight=900)
        _center_text(draw, str(discount_value or "70%"), block_y + 50, f_disc_num, _STUDIO_EMERALD_DK)

        # Pill الكود
        code_text = (code or "SAVE50").upper()
        f_code = _font(60, weight=800)
        cb = draw.textbbox((0, 0), code_text, font=f_code)
        cw = cb[2] - cb[0]
        pill_w = max(cw + 130, 360)
        pill_h = 100
        pill_x = (W - pill_w) // 2
        pill_y = block_y + 250
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=pill_h // 2, fill=_STUDIO_PILL_BG,
        )
        # نص الكود (لاتيني — لا حاجة لـ bidi)
        text_x = pill_x + (pill_w - cw) // 2 - cb[0]
        text_y = pill_y + (pill_h - (cb[3] - cb[1])) // 2 - cb[1]
        draw.text((text_x, text_y), code_text, font=f_code, fill=_STUDIO_PILL_FG)

        # نص فرعي تحت الـ pill
        f_tag = _font(28)
        _center_text(draw, _ar(tagline or "استخدم الكود عند الشراء"), pill_y + pill_h + 22, f_tag, _STUDIO_INK_SOFT)

        # ختم نبض الصفقات — زاوية يمين سفلى (صغير وأنيق)
        if deal_pulse_logo_bytes:
            wm = _fit_logo(deal_pulse_logo_bytes, 110, 110)
            if wm is not None:
                # شفافية 75%
                alpha = wm.split()[-1].point(lambda a: int(a * 0.75))
                wm.putalpha(alpha)
                img.paste(wm, (W - wm.width - 50, H - wm.height - 50), wm)

        # نص "نبض الصفقات" بجانب الختم
        f_wm = _font(22)
        wm_text = _ar("نبض الصفقات")
        wb = draw.textbbox((0, 0), wm_text, font=f_wm)
        tw = wb[2] - wb[0]
        draw.text((50, H - 50 - (wb[3] - wb[1])), wm_text, font=f_wm, fill=_STUDIO_INK_SOFT)

        out = io.BytesIO()
        img.convert("RGB").save(out, format="PNG", optimize=True)
        return out.getvalue()

    # ─── واجهة المستخدم ─────────────────────────────────────────────────────────
    tab_design, tab_archive = st.tabs(["🎨 مصمم البوستر", "🗂️ أرشيف التصاميم"])

    with tab_design:
        col_form, col_prev = st.columns([1, 1.1])

        with col_form:
            st.markdown("##### 🏷️ بيانات العرض")
            store_name_in = st.text_input("اسم المتجر / الشركة", value="", placeholder="مثال: نون، أمازون، نمشي…")
            store_logo_file = st.file_uploader(
                "لوقو المتجر (PNG شفاف أو JPG)",
                type=["png", "jpg", "jpeg", "webp"],
                help="نوصي بـ PNG شفاف لأفضل نتيجة. الصورة تملأ الكارت تلقائياً (cover).",
            )
            auto_rmbg = st.checkbox(
                "🪄 إزالة خلفية اللوقو تلقائياً (remove.bg)", value=False,
                key="studio_auto_rmbg",
                help="يحوّل اللوقو لخلفية شفافة قبل وضعه. يحتاج ضبط REMOVEBG_API_KEY.")
            logo_scale = st.number_input(
                "📐 حجم اللوقو داخل الكارت (%) — اكتب الرقم", min_value=20, max_value=100,
                value=100, step=1, key="studio_logo_scale",
                help="الكارت ثابت 540×400. 100% = اللوقو يملأ الكارت بالكامل · "
                     "أقل = اللوقو أصغر وبهوامش بيضاء حوله. اكتب أي رقم من 20 إلى 100.")
            c1, c2 = st.columns(2)
            with c1:
                discount_label_in = st.text_input("سطر فوق الرقم", value="خصم يصل إلى")
            with c2:
                discount_value_in = st.text_input("قيمة الخصم", value="70%", help="مثل: 70%، 50 ريال، 1+1")
            code_in = st.text_input("كود الخصم", value="SAVE50", max_chars=20)
            tagline_in = st.text_input("سطر تذييل اختياري", value="استخدم الكود عند الشراء")

            generate = st.button("✨ توليد البوستر", type="primary", width='stretch')

        with col_prev:
            st.markdown("##### 🖼️ المعاينة")
            if generate:
                store_logo_bytes = store_logo_file.read() if store_logo_file else None
                if auto_rmbg and store_logo_bytes:
                    with st.spinner("جاري إزالة الخلفية…"):
                        _clean, _rmbg_err = _remove_bg_api(store_logo_bytes)
                    if _clean:
                        store_logo_bytes = _clean
                        st.caption("🪄 تمت إزالة الخلفية بنجاح.")
                    else:
                        st.warning(f"تعذّر إزالة الخلفية: {_rmbg_err} — سنستخدم الصورة كما هي.")
                dp_logo_bytes = None
                if os.path.exists(_logo_path):
                    with open(_logo_path, "rb") as _f:
                        dp_logo_bytes = _f.read()
                with st.spinner("جاري الرسم…"):
                    png_bytes = _render_poster(
                        store_name=store_name_in,
                        store_logo_bytes=store_logo_bytes,
                        discount_label=discount_label_in,
                        discount_value=discount_value_in,
                        code=code_in,
                        tagline=tagline_in,
                        deal_pulse_logo_bytes=dp_logo_bytes,
                        logo_scale=logo_scale,
                    )
                # تخزين في الـ session ليبقى بعد إعادة التشغيل (rerun)
                safe_store = "".join(c for c in (store_name_in or "store") if c.isalnum() or c in ("_", "-"))[:40] or "store"
                safe_code = "".join(c for c in (code_in or "code") if c.isalnum())[:20] or "code"
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                st.session_state["studio_last_png"] = png_bytes
                st.session_state["studio_last_fname"] = f"{safe_store}_{safe_code}_{ts}.png"
                st.session_state["studio_last_saved"] = False

            last_png = st.session_state.get("studio_last_png")
            last_fname = st.session_state.get("studio_last_fname")

            if last_png:
                st.image(last_png, width='stretch')

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("💾 حفظ في الأرشيف", width='stretch', disabled=st.session_state.get("studio_last_saved", False)):
                        try:
                            with open(os.path.join(_ARCHIVE_DIR, last_fname), "wb") as _af:
                                _af.write(last_png)
                            st.session_state["studio_last_saved"] = True
                            st.success(f"تم الحفظ: {last_fname}")
                        except Exception as e:
                            st.error(f"فشل الحفظ: {e}")
                with bcol2:
                    st.download_button(
                        "📥 تحميل PNG",
                        data=last_png,
                        file_name=last_fname,
                        mime="image/png",
                        width='stretch',
                    )
                if st.session_state.get("studio_last_saved"):
                    st.caption(f"✓ محفوظ في الأرشيف باسم {last_fname}")
            else:
                st.info("اضغط «توليد البوستر» لرؤية المعاينة. الهوية مقفولة على ستايل نبض الصفقات — كل البوسترات تطلع بنفس الإحساس الفاخر.")

    with tab_archive:
        st.markdown("##### آخر التصاميم")
        try:
            files = sorted(
                [f for f in os.listdir(_ARCHIVE_DIR) if f.lower().endswith(".png")],
                key=lambda n: os.path.getmtime(os.path.join(_ARCHIVE_DIR, n)),
                reverse=True,
            )
        except Exception:
            files = []

        if not files:
            st.info("لا توجد تصاميم محفوظة بعد. ولّد بوسترك الأول من تبويب «مصمم البوستر».")
        else:
            cols = st.columns(3)
            for i, f in enumerate(files[:18]):
                fp = os.path.join(_ARCHIVE_DIR, f)
                with cols[i % 3]:
                    st.image(fp, width='stretch')
                    with open(fp, "rb") as rf:
                        st.download_button(
                            "تحميل",
                            data=rf.read(),
                            file_name=f,
                            mime="image/png",
                            key=f"dl_{f}",
                            width='stretch',
                        )













# ─────────────────────────────────────────────────────────────────────────────
# محرّك SEO — مراجعة ونشر صفحات الهبوط المولّدة تلقائياً (Week 5-6)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "محرّك SEO":
    st.header("🔍 محرّك صفحات SEO")
    st.caption("توليد ومراجعة وتعديل وحذف ونشر صفحات الـ landing من واجهة واحدة.")

    # ═══ مدير المناسبات — يغذّي النشر التلقائي 3 صباحاً (ربط خلال أسبوعين) ═══
    with st.expander("🗓️ مدير المناسبات (يستخدمها النشر التلقائي)", expanded=False):
        _oc = get_conn(); _oc.rollback()
        try:
            _ocur = _oc.cursor()
            with st.form("add_occasion", clear_on_submit=True):
                _oa, _ob, _oc3 = st.columns([2, 1, 1])
                _occ_name = _oa.text_input("اسم المناسبة", placeholder="مثلاً: الجمعة البيضاء")
                _occ_date = _ob.date_input("التاريخ", format="YYYY-MM-DD")
                _oc3.write(""); _oc3.write("")
                if _oc3.form_submit_button("➕ إضافة", width="stretch"):
                    if _occ_name.strip():
                        _ocur.execute(
                            "INSERT INTO seasonal_events (event_name, occasion_date, event_date, bot_status) "
                            "VALUES (%s, %s, %s, 'انتظار')",
                            (_occ_name.strip(), _occ_date, str(_occ_date)))
                        _oc.commit()
                        st.success(f"أُضيفت: {_occ_name}")
                        st.rerun()
                    else:
                        st.error("اكتب اسم المناسبة.")
            _df_occ = pd.read_sql(
                "SELECT event_id, event_name, occasion_date FROM seasonal_events "
                "WHERE occasion_date IS NOT NULL ORDER BY occasion_date ASC", _oc)
            if _df_occ.empty:
                st.info("لا مناسبات بتواريخ بعد — أضف من الأعلى.")
            else:
                st.caption(f"📅 {len(_df_occ)} مناسبة — المحرّك يربط القادمة خلال 14 يوماً.")
                for _, _r in _df_occ.iterrows():
                    _c1, _c2, _c3 = st.columns([3, 2, 1])
                    _c1.write(f"**{_r['event_name']}**")
                    _c2.write(str(_r['occasion_date']))
                    if _c3.button("🗑️", key=f"occ_del_{_r['event_id']}"):
                        _ocur.execute("DELETE FROM seasonal_events WHERE event_id=%s",
                                      (int(_r['event_id']),))
                        _oc.commit()
                        st.rerun()
        except Exception as _e:
            st.error(f"خطأ في مدير المناسبات: {_e}")
        finally:
            _oc.close()

    # ═══ تشغيل المحرّك الأوتوماتيكي يدوياً (نفس دورة 3 صباحاً — تجربة حقيقية) ═══
    st.subheader("🚀 تشغيل دورة المحرّك الآن")
    st.caption("نفس ما يحدث 3 صباحاً: أكثر المتاجر طلباً → ربط مناسبة → توليد → "
               "**نشر تلقائي حقيقي** للموقع. استخدمه لاختبار دورة كاملة بأمان.")
    if st.button("🚀 شغّل دورة SEO الآن", type="primary", key="seo_auto_run_btn"):
        with st.spinner("جارٍ تشغيل الدورة الكاملة عبر الـ LLM... (قد تأخذ دقيقة)"):
            _ar_data, _ar_err = _admin_post("/admin/seo-auto-run", timeout=280)
        if _ar_err:
            st.error(f"تعذّر التشغيل: {_ar_err}")
        elif _ar_data and not _ar_data.get("enabled", True):
            st.warning("المحرّك معطّل (SEO_AUTO_PUBLISH_ENABLED ليست true على خدمة الـ API).")
        else:
            d = _ar_data or {}
            st.success(
                f"✅ تمّت الدورة — متاجر: {d.get('top_stores', 0)} · "
                f"مناسبة: {d.get('occasion') or '—'} · وظائف: {d.get('enqueued', 0)} · "
                f"مُولَّد: {d.get('generated', 0)} · **منشور: {d.get('published', 0)}**"
            )
            st.balloons()

    # ═══ مسح كامل: كل صفحات SEO (مسودّات+منشورة+أرشيف) + الفهرسة + الوظائف ═══
    with st.expander("🧨 مسح كل صفحات SEO نهائياً (تصفير قبل الإطلاق)", expanded=False):
        st.warning("يحذف **كل** صفحات SEO (مسودّات + منشورة + مكررة) + سجل الفهرسة "
                   "+ وظائف التوليد. لا تراجع — لتصفير النظام بالكامل قبل الإطلاق الفعلي.")
        _purge_ok = st.checkbox("أؤكّد المسح الكامل لكل صفحات SEO", key="seo_purge_confirm")
        if st.button("🧨 امسح كل شي الآن", disabled=not _purge_ok, key="seo_purge_btn"):
            _pc = get_conn(); _pc.rollback()
            try:
                _pcur = _pc.cursor()
                _pcur.execute("DELETE FROM seo_index_submissions")
                _pcur.execute("DELETE FROM seo_landing_pages")
                _np = _pcur.rowcount
                _pcur.execute("DELETE FROM seo_generation_jobs")
                _nj = _pcur.rowcount
                # سجل التدقيق (PDPL): أخطر عملية في النظام — تُسجَّل ضمن نفس المعاملة
                import json as _json
                _pcur.execute(
                    "INSERT INTO pdpl_audit_log (actor, action, target, status, meta) "
                    "VALUES ('dashboard', 'seo_purge_all', 'all_seo_pages', 'ok', %s::jsonb)",
                    (_json.dumps({"pages_deleted": _np, "jobs_deleted": _nj}),),
                )
                _pc.commit()
                st.success(f"تم المسح الكامل: {_np} صفحة + {_nj} وظيفة. النظام صفر.")
                st.rerun()
            except Exception as _pe:
                st.error(f"تعذّر المسح: {_pe}")
            finally:
                _pc.close()

    # ═════════════════════════════════════════════════════════════════════════
    # القسم 1 — صندوق التوليد بموضوع مخصّص
    # ═════════════════════════════════════════════════════════════════════════
    st.subheader("✨ توليد صفحات حول موضوع")
    st.caption(
        "اكتب موضوعاً (مثال: «يوم التأسيس» / «رمضان 2026» / «اليوم الوطني») وسنُنشئ "
        "3 صفحات لكل من أهم المتاجر تربط الموضوع باسم المتجر."
    )

    with st.form("seo_custom_topic_form", clear_on_submit=False):
        col_topic, col_stores, col_btn = st.columns([3, 1, 1])
        with col_topic:
            topic_input = st.text_input(
                "الموضوع",
                placeholder="مثلاً: يوم التأسيس، رمضان 2026، عودة المدارس...",
                key="seo_topic_input",
            )
        with col_stores:
            max_stores_input = st.number_input(
                "عدد المتاجر",
                min_value=1, max_value=50, value=10, step=1,
                key="seo_max_stores",
            )
        with col_btn:
            st.write("")
            st.write("")
            submit_topic = st.form_submit_button("📥 جدولة الوظائف", width='stretch')

        if submit_topic:
            if not topic_input.strip():
                st.warning("اكتب موضوعاً أولاً.")
            else:
                with st.spinner("نُجدّول وظائف التوليد..."):
                    data, err = _admin_post(
                        "/admin/seo-seed-custom",
                        params={"topic": topic_input.strip(),
                                "max_stores": int(max_stores_input)},
                    )
                if err:
                    st.error(f"تعذّر: {err}")
                else:
                    st.success(
                        f"✅ تم جدولة **{data.get('jobs_enqueued', 0)}** وظيفة "
                        f"({data.get('jobs_skipped_duplicate', 0)} مُكرّر تم تخطيه). "
                        "اضغط «توليد المسودّات» أدناه لتشغيل الـ LLM."
                    )

    # ═════════════════════════════════════════════════════════════════════════
    # القسم 2 — أزرار تشغيل التوليد
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("⚙️ توليد المسودّات من قائمة الانتظار")

    cta1, cta2, cta3 = st.columns([1, 1, 2])
    with cta1:
        batch_size = st.number_input("حجم الدفعة", min_value=1, max_value=20,
                                      value=3, step=1, key="seo_batch_size",
                                      help="عدد المتاجر التي تُولَّد دفعة (كل متجر = صفحتان: عربي+إنجليزي)")
    with cta2:
        if st.button("⚙️ توليد الآن", width='stretch', type="primary"):
            with st.spinner(f"جارٍ توليد {batch_size} متجر عبر الـ LLM... (~{batch_size * 30} ثانية)"):
                data, err = _admin_post("/admin/seo-run", params={"batch": int(batch_size)}, timeout=280)
            if err:
                st.error(f"تعذّر التشغيل: {err}")
            else:
                g = data.get("generation", {}) if data else {}
                st.success(
                    f"✅ نتيجة الدفعة — مُعالَج: {g.get('processed', 0)} · "
                    f"مولّد: {g.get('generated', 0)} · فشل: {g.get('failed', 0)}"
                )
                st.rerun()
    with cta3:
        st.caption(
            "💡 لو ظهرت `failed` كثيرة، افتح تبويب «وظائف فاشلة» أدناه لتشخيص السبب. "
            "في الغالب: انتهاء حصة LLM اليومية (تتجدّد 03:00 صباحاً بتوقيت الرياض)."
        )

    # ═════════════════════════════════════════════════════════════════════════
    # القسم 3 — قائمة المسودّات (مع معاينة + تعديل + حذف + نشر)
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("📝 المسودّات بانتظار النشر")

    # شريط بحث/تصفية بسيط
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        search_filter = st.text_input(
            "🔎 بحث في العنوان/الكلمة المستهدفة",
            placeholder="مثلاً: نون، رمضان، شحن...",
            key="seo_search",
        ).strip().lower()
    with fc2:
        lang_filter = st.selectbox("اللغة", ["الكل", "عربي", "إنجليزي"], key="seo_lang_filter")
    with fc3:
        if st.button("🔄 تحديث القائمة", width='stretch'):
            st.rerun()

    drafts, err = _admin_get("/admin/seo-drafts", params={"limit": 200})
    if err:
        st.error(f"تعذّر جلب المسودّات: {err}")
    elif not drafts or not drafts.get("drafts"):
        st.info("لا توجد مسودّات حالياً. اكتب موضوعاً واضغط «جدولة الوظائف» ثم «توليد الآن».")
    else:
        all_drafts = drafts["drafts"]
        # تطبيق الفلاتر
        filtered = all_drafts
        if search_filter:
            filtered = [d for d in filtered
                        if search_filter in (d.get("title_meta") or "").lower()
                        or search_filter in (d.get("target_keyword") or "").lower()]
        lang_map = {"عربي": "ar", "إنجليزي": "en"}
        if lang_filter in lang_map:
            filtered = [d for d in filtered if d.get("lang") == lang_map[lang_filter]]

        st.caption(
            f"عرض **{len(filtered)}** من إجمالي **{drafts.get('total', 0)}** مسودّة"
            + (f" (مرشّحة)" if len(filtered) != len(all_drafts) else "")
        )

        for d in filtered:
            page_id = d["id"]
            lang_badge = "🇸🇦 عربي" if d.get("lang") == "ar" else "🇬🇧 EN"

            with st.container(border=True):
                # عنوان البطاقة
                head_l, head_r = st.columns([5, 1])
                with head_l:
                    st.markdown(
                        f"**{d.get('title_meta') or d.get('target_keyword')}** "
                        f"<span style='background:#10B981;color:white;padding:2px 8px;border-radius:4px;font-size:0.75em;'>{lang_badge}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"🔑 {d.get('target_keyword')} · 🏪 {d.get('store_name') or '—'} · "
                        f"🔗 `/c/{d.get('slug')}` · 📄 {d.get('body_len', 0)} حرف · `ID={page_id}`"
                    )
                    if d.get("description_meta"):
                        st.caption(f"📝 {d['description_meta']}")
                with head_r:
                    st.caption(f"#{page_id}")

                # أزرار العمل
                btn_preview, btn_edit, btn_publish, btn_delete = st.columns(4)
                with btn_preview:
                    show_preview = st.toggle(
                        "👁️ معاينة",
                        key=f"seo_prev_{page_id}",
                        help="عرض المحتوى الكامل قبل النشر",
                    )
                with btn_edit:
                    show_edit = st.toggle(
                        "✏️ تعديل",
                        key=f"seo_edit_{page_id}",
                        help="تعديل العنوان/الوصف/المحتوى",
                    )
                with btn_publish:
                    if st.button("🚀 نشر",
                                 key=f"seo_pub_{page_id}",
                                 width='stretch', type="primary"):
                        with st.spinner("نشر + IndexNow + Next.js revalidate..."):
                            res, perr = _admin_post(f"/admin/seo-publish/{page_id}")
                        if perr:
                            st.error(perr)
                        else:
                            st.success(f"✅ نُشر — /c/{res.get('slug')}")
                            st.rerun()
                with btn_delete:
                    if st.button("🗑️ حذف",
                                 key=f"seo_del_{page_id}",
                                 width='stretch'):
                        # نطلب تأكيداً عبر session_state
                        confirm_key = f"seo_del_confirm_{page_id}"
                        st.session_state[confirm_key] = True

                # تأكيد الحذف
                if st.session_state.get(f"seo_del_confirm_{page_id}"):
                    st.warning(f"⚠️ هل تريد حذف المسودّة #{page_id} نهائياً؟")
                    cf1, cf2, _ = st.columns([1, 1, 3])
                    with cf1:
                        if st.button("نعم احذف", key=f"seo_del_yes_{page_id}",
                                     width='stretch', type="primary"):
                            res, derr = _admin_delete(f"/admin/seo-draft/{page_id}")
                            if derr:
                                st.error(derr)
                            else:
                                st.toast(f"✅ حُذفت", icon="🗑️")
                                st.session_state.pop(f"seo_del_confirm_{page_id}", None)
                                st.rerun()
                    with cf2:
                        if st.button("إلغاء", key=f"seo_del_no_{page_id}",
                                     width='stretch'):
                            st.session_state.pop(f"seo_del_confirm_{page_id}", None)
                            st.rerun()

                # ─── المعاينة ──────────────────────────────────────────────
                if show_preview or show_edit:
                    full, ferr = _admin_get(f"/admin/seo-draft/{page_id}")
                    if ferr:
                        st.error(f"تعذّر جلب المحتوى: {ferr}")
                    elif full:
                        if show_preview and not show_edit:
                            with st.expander("📄 المحتوى الكامل", expanded=True):
                                st.markdown(f"**Title:** {full.get('title_meta', '')}")
                                st.markdown(f"**Description:** {full.get('description_meta', '')}")
                                st.markdown("---")
                                # نعرض markdown كما هو ليُرى بصورته النهائية
                                if full.get('lang') == 'en':
                                    st.markdown(f"<div dir='ltr' style='text-align:left'>{full.get('body_markdown', '')}</div>",
                                                unsafe_allow_html=True)
                                else:
                                    st.markdown(full.get('body_markdown', ''))

                        if show_edit:
                            with st.expander("✏️ نموذج التعديل", expanded=True):
                                with st.form(f"seo_edit_form_{page_id}"):
                                    new_title = st.text_input(
                                        "Title (≤180 حرف)",
                                        value=full.get('title_meta', ''),
                                        max_chars=180,
                                    )
                                    new_desc = st.text_area(
                                        "Description (≤280 حرف)",
                                        value=full.get('description_meta', ''),
                                        max_chars=280, height=80,
                                    )
                                    new_body = st.text_area(
                                        "Body Markdown",
                                        value=full.get('body_markdown', ''),
                                        height=400,
                                    )
                                    save_col, cancel_col, _ = st.columns([1, 1, 3])
                                    with save_col:
                                        if st.form_submit_button("💾 حفظ", type="primary",
                                                                  width='stretch'):
                                            update_body = {}
                                            if new_title != full.get('title_meta', ''):
                                                update_body["title_meta"] = new_title
                                            if new_desc != full.get('description_meta', ''):
                                                update_body["description_meta"] = new_desc
                                            if new_body != full.get('body_markdown', ''):
                                                update_body["body_markdown"] = new_body
                                            if not update_body:
                                                st.info("لا تغييرات للحفظ.")
                                            else:
                                                _r, uerr = _admin_put(
                                                    f"/admin/seo-draft/{page_id}",
                                                    json_body=update_body,
                                                )
                                                if uerr:
                                                    st.error(uerr)
                                                else:
                                                    st.toast("✅ حُفظت التعديلات", icon="💾")
                                                    st.rerun()
                                    with cancel_col:
                                        st.form_submit_button("إلغاء",
                                                               width='stretch')

    # ═════════════════════════════════════════════════════════════════════════
    # القسم 4 — تشخيص الفشل (مطوي)
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()
    with st.expander("🔧 تشخيص الوظائف الفاشلة (للمطوّر)", expanded=False):
        fail_data, fail_err = _admin_get("/admin/seo-failed-jobs", params={"limit": 20})
        if fail_err:
            st.error(fail_err)
        elif not fail_data or not fail_data.get("failed_jobs"):
            st.success("✅ لا توجد وظائف فاشلة.")
        else:
            st.caption(f"إجمالي الفاشلة: {fail_data.get('total', 0)} (آخر 20)")

            ret_col, _ = st.columns([1, 4])
            with ret_col:
                if st.button("🔁 إعادة جدولة الكل", width='stretch'):
                    _r, rerr = _admin_post("/admin/seo-retry-failed",
                                            params={"limit": 100})
                    if rerr:
                        st.error(rerr)
                    else:
                        st.success(f"✅ أُعيد جدولة {_r.get('requeued', 0)} وظيفة")
                        st.rerun()

            for j in fail_data["failed_jobs"]:
                with st.container(border=True):
                    st.markdown(f"**#{j['id']}** · 🔑 {j.get('target_keyword', '')}")
                    st.caption(f"📅 {j.get('completed_at', '—')}")
                    st.code((j.get("error_message") or "")[:500], language=None)

# ─────────────────────────────────────────────────────────────────────────────
# 📈 أداء SEO — PageSpeed (يشتغل الآن) + Search Console (يُربط قُبيل الإطلاق)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📈 أداء SEO":
    page_title("📈", "قياس وأداء SEO",
               "سرعة الموقع (PageSpeed) + نتائج البحث (Search Console)")
    _ps_tab, _gsc_tab, _trk_tab = st.tabs(
        ["⚡ سرعة الموقع (PageSpeed)", "🔍 Search Console", "📅 التتبّع اليومي"])

    with _ps_tab:
        st.caption("فحص الأداء/SEO/الإتاحة عبر Google PageSpeed — يكشف نقاط الضعف وفرص التحسين.")
        _pc1, _pc2 = st.columns([3, 1])
        _ps_url = _pc1.text_input("رابط الصفحة", value="https://www.dealpulseksa.com/", key="ps_url")
        _ps_strat = _pc2.selectbox(
            "الجهاز", ["mobile", "desktop"],
            format_func=lambda x: "📱 جوال" if x == "mobile" else "💻 سطح مكتب", key="ps_strat")
        if st.button("🔍 افحص الآن", type="primary", key="ps_run"):
            with st.spinner("جارٍ الفحص عبر Google (~20-30 ثانية)..."):
                try:
                    _pp = [("url", _ps_url), ("strategy", _ps_strat)]
                    for _cat in ("performance", "seo", "accessibility", "best-practices"):
                        _pp.append(("category", _cat))
                    _pk = os.getenv("PAGESPEED_API_KEY")
                    if _pk:
                        _pp.append(("key", _pk))
                    _pr = requests.get(
                        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                        params=_pp, timeout=70)
                    _pj = _pr.json()
                except Exception as _pe:
                    _pj = {"error": {"message": str(_pe)}}
            if "error" in _pj:
                st.error(f"تعذّر الفحص: {str(_pj['error'].get('message', ''))[:300]}")
            else:
                _lr = _pj.get("lighthouseResult", {})
                _cats = _lr.get("categories", {})
                _NAMES = [("performance", "⚡ الأداء"), ("seo", "🔍 SEO"),
                          ("accessibility", "♿ الإتاحة"), ("best-practices", "✅ الممارسات")]
                _cols = st.columns(4)
                for _col, (_k, _lbl) in zip(_cols, _NAMES):
                    _s = _cats.get(_k, {}).get("score")
                    _sc = int(_s * 100) if _s is not None else None
                    _ico = "🟢" if (_sc or 0) >= 90 else ("🟠" if (_sc or 0) >= 50 else "🔴")
                    _col.metric(_lbl, f"{_ico} {_sc}" if _sc is not None else "—")
                _audits = _lr.get("audits", {})
                _opps = [a for a in _audits.values()
                         if a.get("details", {}).get("type") == "opportunity"
                         and (a.get("score") if a.get("score") is not None else 1) < 0.9]
                _opps.sort(key=lambda a: a.get("score") if a.get("score") is not None else 1)
                st.divider()
                if _opps:
                    st.subheader("🛠️ أهم فرص التحسين")
                    for _a in _opps[:8]:
                        _dv = _a.get("displayValue", "")
                        st.markdown(f"- **{_a.get('title', '')}** {('— ' + _dv) if _dv else ''}")
                else:
                    st.success("✅ لا فرص تحسين كبيرة — الأداء جيد.")
        if not os.getenv("PAGESPEED_API_KEY"):
            st.caption("💡 يعمل الآن بلا مفتاح (محدود المعدّل). للاستخدام المكثّف أضف "
                       "`PAGESPEED_API_KEY` (مجاني من Google Cloud) على خدمة الداشبورد.")

    with _gsc_tab:
        _gsc_json = os.getenv("GSC_SA_JSON")
        _gsc_site = os.getenv("GSC_SITE", "https://www.dealpulseksa.com/")
        if not _gsc_json:
            st.info(
                "🔍 **GSC غير مربوط بعد.** أضف على خدمة الداشبورد:\n"
                "- `GSC_SA_JSON` = محتوى ملف service account (JSON كامل)\n"
                "- `GSC_SITE` = رابط الخاصية (مثل https://www.dealpulseksa.com/)\n\n"
                "وامنح الـ service account صلاحية في Search Console (المستخدمون والأذونات)."
            )
        else:
            st.caption(f"الخاصية: {_gsc_site}")
            _gd1, _gd2 = st.columns(2)
            _g_from = _gd1.date_input(
                "من", value=(datetime.datetime.utcnow() - timedelta(days=28)).date(),
                key="gsc_from", format="YYYY-MM-DD")
            _g_to = _gd2.date_input(
                "إلى", value=datetime.datetime.utcnow().date(), key="gsc_to", format="YYYY-MM-DD")
            if st.button("📊 اجلب بيانات Search Console", type="primary", key="gsc_run"):
                with st.spinner("جارٍ الجلب من Google Search Console..."):
                    _gerr = None
                    _tot = _byq = _byp = None
                    try:
                        from google.oauth2 import service_account
                        from googleapiclient.discovery import build
                        _creds = service_account.Credentials.from_service_account_info(
                            json.loads(_gsc_json),
                            scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
                        _svc = build("searchconsole", "v1", credentials=_creds,
                                     cache_discovery=False)

                        def _gq(dims):
                            return _svc.searchanalytics().query(
                                siteUrl=_gsc_site,
                                body={"startDate": str(_g_from), "endDate": str(_g_to),
                                      "dimensions": dims, "rowLimit": 25}).execute()
                        _tot = _gq([])
                        _byq = _gq(["query"])
                        _byp = _gq(["page"])
                    except Exception as _ge:
                        _gerr = str(_ge)
                if _gerr:
                    st.error(f"تعذّر الجلب: {_gerr[:400]}")
                else:
                    _agg = (_tot.get("rows") or [{}])[0]
                    _gk1, _gk2, _gk3, _gk4 = st.columns(4)
                    _gk1.metric("👆 نقرات", int(_agg.get("clicks", 0)))
                    _gk2.metric("👁️ ظهور", int(_agg.get("impressions", 0)))
                    _gk3.metric("📈 CTR", f"{_agg.get('ctr', 0) * 100:.1f}%")
                    _gk4.metric("📊 متوسط الترتيب", f"{_agg.get('position', 0):.1f}")
                    st.divider()

                    def _gtbl(resp, header):
                        _rs = resp.get("rows") or []
                        if not _rs:
                            st.caption("لا بيانات في هذه الفترة.")
                            return
                        st.dataframe(pd.DataFrame([{
                            header: r["keys"][0],
                            "نقرات": int(r.get("clicks", 0)),
                            "ظهور": int(r.get("impressions", 0)),
                            "CTR": f"{r.get('ctr', 0) * 100:.1f}%",
                            "ترتيب": f"{r.get('position', 0):.1f}",
                        } for r in _rs]), width="stretch", hide_index=True)
                    st.subheader("🔑 أهم كلمات البحث")
                    _gtbl(_byq, "الكلمة")
                    st.subheader("📄 أهم الصفحات")
                    _gtbl(_byp, "الصفحة")

    with _trk_tab:
        st.caption("تطوّر أدائك يوم بيوم — يُحدّث تلقائياً 4 صباحاً، أو اضغط لقطة فورية.")
        if st.button("📸 التقط لقطة الآن", type="primary", key="snap_now"):
            with st.spinner("جارٍ الالتقاط (PageSpeed + GSC)... ~دقيقة"):
                _sd, _serr = _admin_post("/admin/seo-snapshot", timeout=120)
            if _serr:
                st.error(f"تعذّر: {_serr}")
            else:
                _ge = (_sd or {}).get("gsc_error")
                _pe = (_sd or {}).get("ps_error")
                if _ge:
                    st.warning(f"⚠️ GSC لم تُجلب: {_ge[:400]}")
                if _pe:
                    st.warning(f"⚠️ PageSpeed لم تُجلب: {_pe[:400]}")
                if not _ge and not _pe:
                    st.success("✅ تم التقاط اللقطة كاملة (PageSpeed + GSC).")
                else:
                    st.info("اللقطة حُفظت جزئياً. حدّث الصفحة لرؤية السجل.")
        _tc = get_conn(); _tc.rollback()
        try:
            _snap = pd.read_sql("""
                SELECT snapshot_date AS "التاريخ", ps_performance AS "الأداء",
                       ps_seo AS "SEO", gsc_clicks AS "نقرات",
                       gsc_impressions AS "ظهور", gsc_position AS "الترتيب"
                FROM seo_perf_snapshots ORDER BY snapshot_date DESC LIMIT 90
            """, _tc)
        finally:
            _tc.close()
        if _snap.empty:
            st.info("لا لقطات بعد — اضغط «التقط لقطة الآن» أو انتظر دورة 4 صباحاً.")
        else:
            _chart = _snap.sort_values("التاريخ")
            st.markdown("##### ⚡ تطوّر الأداء (PageSpeed)")
            st.line_chart(_chart.set_index("التاريخ")[["الأداء", "SEO"]])
            st.markdown("##### 📊 تطوّر Search Console (إجمالي آخر 28 يوم لكل لقطة)")
            st.line_chart(_chart.set_index("التاريخ")[["نقرات", "ظهور"]])
            st.markdown("##### 📋 السجل")
            st.dataframe(_snap, width="stretch", hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 📤 الصفحات المنشورة — متابعة حالة صفحات SEO بعد النشر
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📤 الصفحات المنشورة":
    st.header("📤 الصفحات المنشورة")
    st.caption("متابعة صفحات SEO بعد النشر — رابط الصفحة الحيّة، حالة Google، فهرسة سريعة.")

    import os
    # القانوني = www (لمطابقة GSC + تجنّب التحويلات)
    site_url = os.getenv("SITE_URL", "https://www.dealpulseksa.com").rstrip("/")

    top1, top2, top3 = st.columns([1, 1, 2])
    with top1:
        if st.button("🔄 تحديث", width='stretch'):
            st.session_state.pop("pub_gsc_cache", None)
            st.rerun()
    with top2:
        lang_pub_filter = st.selectbox("اللغة", ["الكل", "عربي", "إنجليزي"], key="pub_lang")
    with top3:
        show_gsc_perf = st.checkbox("📊 أظهر أداء Google لكل صفحة (آخر 28 يوم)",
                                    value=False, key="pub_show_gsc")
        st.caption(f"الموقع: `{site_url}`")

    # تخصيب: أداء Google لكل صفحة (page dimension) — يُجلب مرة ويُخزَّن للجلسة
    def _fetch_gsc_page_metrics():
        raw = os.getenv("GSC_SA_JSON")
        gsite = os.getenv("GSC_SITE", "https://www.dealpulseksa.com/")
        if not raw:
            return {}
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            _creds = service_account.Credentials.from_service_account_info(
                json.loads(raw), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
            _svc = build("searchconsole", "v1", credentials=_creds, cache_discovery=False)
            _end = datetime.datetime.utcnow().date()
            _start = _end - timedelta(days=28)
            _resp = _svc.searchanalytics().query(
                siteUrl=gsite,
                body={"startDate": str(_start), "endDate": str(_end),
                      "dimensions": ["page"], "rowLimit": 1000}).execute()
            _out = {}
            for _r in _resp.get("rows", []):
                _u = _r["keys"][0].rstrip("/")
                _out[_u] = {"clicks": int(_r.get("clicks", 0)),
                            "impressions": int(_r.get("impressions", 0)),
                            "position": float(_r.get("position", 0))}
            return _out
        except Exception:
            return {}

    _gsc_pages = {}
    if show_gsc_perf:
        if "pub_gsc_cache" not in st.session_state:
            with st.spinner("جلب أداء Google لكل صفحة..."):
                st.session_state["pub_gsc_cache"] = _fetch_gsc_page_metrics()
        _gsc_pages = st.session_state["pub_gsc_cache"]
        if not _gsc_pages:
            st.caption("⚠️ تعذّر جلب بيانات GSC (تأكد GSC_SA_JSON على الداشبورد).")

    lang_param = {"عربي": "ar", "إنجليزي": "en"}.get(lang_pub_filter)
    params = {"limit": 200}
    if lang_param:
        params["lang"] = lang_param

    data, err = _admin_get("/seo/pages", params=params)
    if err:
        st.error(f"تعذّر جلب الصفحات: {err}")
    elif not data or not data.get("pages"):
        st.info("لا توجد صفحات منشورة بعد. اذهب إلى «محرّك SEO» وانشر مسودّة.")
    else:
        pages = data["pages"]
        st.success(f"📊 إجمالي المنشور: **{data.get('total', len(pages))}** صفحة")

        st.divider()
        for p in pages:
            slug = p.get("slug")
            lang_badge = "🇸🇦 عربي" if p.get("lang") == "ar" else "🇬🇧 EN"
            live_url = f"{site_url}/c/{slug}"

            with st.container(border=True):
                head_l, head_r = st.columns([5, 1])
                with head_l:
                    st.markdown(
                        f"**{p.get('title_meta') or p.get('target_keyword')}** "
                        f"<span style='background:#0EA5E9;color:white;padding:2px 8px;border-radius:4px;font-size:0.75em;'>{lang_badge}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"🔑 {p.get('target_keyword')} · 🔗 `/c/{slug}` · "
                        f"🗓️ {(p.get('published_at') or '—')[:10]}"
                    )
                    if p.get("description_meta"):
                        st.caption(f"📝 {p['description_meta']}")
                    if show_gsc_perf:
                        _m = _gsc_pages.get(live_url.rstrip("/"))
                        if _m:
                            st.caption(
                                f"📊 **Google:** 👆 {_m['clicks']} نقرة · "
                                f"👁️ {_m['impressions']} ظهور · 📈 ترتيب {_m['position']:.1f}")
                        else:
                            st.caption("📊 Google: لم تُفهرس بعد / لا بيانات (28 يوم)")
                with head_r:
                    st.caption(f"slug:")
                    st.code(slug, language=None)

                # شريط الإجراءات
                a1, a2 = st.columns(2)
                with a1:
                    st.link_button("🌐 افتح الصفحة", live_url, width='stretch')
                with a2:
                    import html as _html
                    url_attr = _html.escape(live_url, quote=True)
                    btn_html = (
                        '<button '
                        f'data-url="{url_attr}" '
                        "onclick=\"var u=this.dataset.url;"
                        "navigator.clipboard.writeText(u).then(function(){"
                        "this.innerHTML='&#10003; تم النسخ';"
                        "this.style.background='#10B981';"
                        "this.style.color='white';"
                        "this.style.borderColor='#10B981';"
                        "var b=this;"
                        "setTimeout(function(){"
                        "b.innerHTML='&#128203; نسخ الرابط';"
                        "b.style.background='rgb(240,242,246)';"
                        "b.style.color='';"
                        "b.style.borderColor='rgba(49,51,63,0.2)';"
                        "},1800);"
                        "}.bind(this)).catch(function(){"
                        "this.innerHTML='&#10007; فشل النسخ';"
                        "this.style.background='#EF4444';"
                        "this.style.color='white';"
                        "}.bind(this));\" "
                        "style=\"width:100%;padding:6px 12px;"
                        "background:rgb(240,242,246);"
                        "border:1px solid rgba(49,51,63,0.2);"
                        "border-radius:8px;cursor:pointer;"
                        "font-family:'Source Sans Pro',sans-serif;"
                        "font-size:14px;height:38px;transition:all 0.2s;\">"
                        "&#128203; نسخ الرابط"
                        "</button>"
                    )
                    components.html(btn_html, height=50)

# ═════════════════════════════════════════════════════════════════════════════
# 🎯 محرك الفرص — Google Trends + keyword CRUD + one-click page generation
#
# المستخدم يضيف keywords (مثلاً "كود خصم نون")، الـ scheduler يجلب درجة Google
# Trends لها كل ساعة في السعودية، الصفحة تعرضها مرتّبة، المستخدم يقرّر يولّد
# صفحة هبوط بضغطة واحدة. بديل Google Alerts الذي ثبت أنه غير منتج.
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🎯 محرك الفرص":
    page_title("🎯", "محرك الفرص",
               "Google Trends لكلماتك في السعودية — أضف، تابع، ولّد صفحة بضغطة")

    # شريط أعلى الصفحة: إضافة + sort + refresh-all
    top_l, top_m, top_r = st.columns([3, 1.4, 1.4])
    with top_l:
        with st.expander("➕ إضافة keyword جديد", expanded=False):
            with st.form("opp_add_form", clear_on_submit=True):
                fa1, fa2 = st.columns([3, 2])
                with fa1:
                    new_kw = st.text_input(
                        "الكلمة",
                        placeholder="مثلاً: كود خصم نون",
                        max_chars=200,
                    )
                with fa2:
                    new_store = st.text_input(
                        "store_id (اختياري)",
                        placeholder="مثلاً: noon",
                        help="لربط الكلمة بمتجر محدد في master. اتركه فارغاً للمطابقة التلقائية.",
                    )
                new_notes = st.text_input("ملاحظة (اختياري)", placeholder="مثلاً: ينافس عليه كود خصم")
                if st.form_submit_button("➕ أضف للمراقبة", type="primary"):
                    if not new_kw.strip():
                        st.error("الكلمة مطلوبة")
                    else:
                        body = {
                            "keyword": new_kw.strip(),
                            "store_id": (new_store or "").strip() or None,
                            "notes":    (new_notes or "").strip() or None,
                            "active":   True,
                        }
                        res, err = _admin_post("/admin/seo-opportunities", json_body=body)
                        if err:
                            st.error(f"فشل: {err}")
                        else:
                            st.success(f"تمت الإضافة ✅ (سيتم جلب درجة Trends خلال دقائق)")
                            st.rerun()

    with top_m:
        sort_opt = st.selectbox(
            "الترتيب",
            ["trend_score", "rising_pct", "created_at", "keyword"],
            format_func=lambda s: {
                "trend_score": "🔥 الأعلى شعبية",
                "rising_pct":  "↗️ الأسرع صعوداً",
                "created_at":  "🆕 الأحدث إضافة",
                "keyword":     "🔤 أبجدي",
            }[s],
            key="opp_sort",
        )
    with top_r:
        only_active = st.toggle("النشطة فقط", value=False, key="opp_active_only")
        if st.button("🔄 تحديث Trends لكل الكلمات", width='stretch',
                     key="opp_refresh_all",
                     help="يستغرق ~5 ثوانٍ × عدد الكلمات (لتفادي rate-limit)"):
            with st.spinner("جلب Google Trends لكل الكلمات النشطة..."):
                res, err = _admin_post("/admin/seo-opportunities/refresh-all")
            if err:
                st.error(err)
            else:
                stats = res.get("stats", {}) if res.get("ok") else {}
                st.success(
                    f"✅ تم — فُحص {stats.get('checked', 0)}، "
                    f"حُدّث {stats.get('updated', 0)}، فشل {stats.get('failed', 0)}"
                )
                st.rerun()

    # جلب القائمة
    data, err = _admin_get(
        "/admin/seo-opportunities",
        params={"sort": sort_opt, "only_active": str(only_active).lower(), "limit": 500},
    )
    if err:
        st.error(f"تعذّر الجلب: {err}")
    elif not data or not data.get("keywords"):
        st.info(
            "📭 لا توجد كلمات بعد. اضغط «➕ إضافة keyword» وابدأ بكلمات مثل:\n\n"
            "- كود خصم نون\n- كوبون نون 2026\n- كود خصم شي إن\n- كود خصم اكسايت"
        )
    else:
        kws = data["keywords"]
        # ─── KPIs مختصرة ───
        total       = len(kws)
        hot         = sum(1 for k in kws if (k.get("trend_score") or 0) >= 50)
        rising_fast = sum(1 for k in kws if (k.get("rising_pct") or 0) >= 30)
        with_page   = sum(1 for k in kws if k.get("generated_page_id"))
        k1, k2, k3, k4 = st.columns(4)
        with k1: kpi_card("📊", "إجمالي المُتابَع", f"{total}", "info")
        with k2: kpi_card("🔥", "شعبية ≥ 50", f"{hot}", "danger" if hot else "neutral")
        with k3: kpi_card("↗️", "صاعدة سريعاً", f"{rising_fast}", "emerald" if rising_fast else "neutral")
        with k4: kpi_card("✅", "مولَّدة صفحة", f"{with_page}/{total}", "info")

        st.divider()

        # ─── جدول الكلمات ───
        for kw in kws:
            score = int(kw.get("trend_score") or 0)
            rising = float(kw.get("rising_pct") or 0)
            inactive = not kw.get("active", True)
            has_page = bool(kw.get("generated_page_id"))

            # لون الإطار حسب الشعبية
            border_color = (
                "#9CA3AF" if inactive
                else "#DC2626" if score >= 70
                else "#F59E0B" if score >= 40
                else "#6B7280"
            )

            with st.container(border=True):
                # ── السطر العلوي: الكلمة + المتجر + الحالة ──
                h1, h2, h3, h4 = st.columns([3, 1.3, 1.3, 1.4])
                with h1:
                    badge_active = "🔇 موقوف" if inactive else ""
                    st.markdown(
                        f"### {kw['keyword']} {badge_active}",
                        help=kw.get("notes") or None,
                    )
                    if kw.get("notes"):
                        st.caption(f"📝 {kw['notes']}")
                with h2:
                    score_color = (
                        "#DC2626" if score >= 70
                        else "#F59E0B" if score >= 40
                        else "#6B7280"
                    )
                    st.markdown(
                        f"<div style='text-align:center;padding:6px;background:{score_color};"
                        f"color:white;border-radius:8px;'>"
                        f"<div style='font-size:11px;opacity:0.9;'>شعبية الآن</div>"
                        f"<div style='font-size:22px;font-weight:bold;'>{score}<span style='font-size:12px;'>/100</span></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with h3:
                    arrow = "↗️" if rising > 5 else "↘️" if rising < -5 else "→"
                    rcolor = (
                        "#16A34A" if rising > 5
                        else "#DC2626" if rising < -5
                        else "#6B7280"
                    )
                    st.markdown(
                        f"<div style='text-align:center;padding:6px;border:2px solid {rcolor};"
                        f"border-radius:8px;'>"
                        f"<div style='font-size:11px;color:#666;'>الاتجاه</div>"
                        f"<div style='font-size:18px;font-weight:bold;color:{rcolor};'>"
                        f"{arrow} {rising:+.0f}%</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with h4:
                    if kw.get("store_id"):
                        st.caption(f"🏪 `{kw['store_id']}`")
                    last_at = kw.get("last_checked_at") or "—"
                    st.caption(f"🕒 آخر فحص: {last_at}")
                    if kw.get("last_error"):
                        st.caption(f"⚠️ {kw['last_error'][:60]}")

                # ── سطر الإجراءات ──
                a1, a2, a3, a4, a5 = st.columns([2, 1.4, 1.4, 1.4, 1.4])
                with a1:
                    if has_page:
                        st.success(f"✅ مولَّدة صفحة #{kw['generated_page_id']}")
                    elif inactive:
                        st.caption("الكلمة موقوفة")
                    else:
                        if st.button("🚀 ولّد صفحة الآن", key=f"gen_{kw['id']}",
                                     type="primary", width='stretch'):
                            with st.spinner("جاري التوليد (قد يستغرق 30 ثانية للـ LLM)..."):
                                res, err = _admin_post(
                                    f"/admin/seo-opportunities/{kw['id']}/generate-page"
                                )
                            if err:
                                st.error(err)
                            elif res and res.get("ok"):
                                st.toast(f"✅ تم — slug: {res.get('slug', '?')}", icon="🚀")
                                st.rerun()
                            else:
                                st.error(res.get("error", "فشل غير معروف") if res else "فشل")

                with a2:
                    if st.button("🔄 جلب Trend", key=f"rf_{kw['id']}",
                                 width='stretch',
                                 help="جلب فوري لدرجة Google Trends لهذه الكلمة"):
                        with st.spinner("جلب من Google..."):
                            res, err = _admin_post(
                                f"/admin/seo-opportunities/{kw['id']}/refresh"
                            )
                        if err:
                            st.error(err)
                        else:
                            r = res.get("result", {})
                            if r.get("ok"):
                                st.toast(f"✅ Trend: {r.get('trend_score')}/100", icon="📊")
                            else:
                                st.toast(f"⚠️ {r.get('error', 'فشل')}", icon="⚠️")
                            st.rerun()

                with a3:
                    toggle_label = "▶️ تفعيل" if inactive else "⏸️ إيقاف"
                    if st.button(toggle_label, key=f"tg_{kw['id']}",
                                 width='stretch'):
                        res, err = _admin_put(
                            f"/admin/seo-opportunities/{kw['id']}",
                            json_body={"active": inactive},  # عكس الحالة الحالية
                        )
                        if err:
                            st.error(err)
                        else:
                            st.rerun()

                with a4:
                    with st.popover("✏️ تعديل", width='stretch'):
                        with st.form(f"edit_form_{kw['id']}"):
                            e_kw = st.text_input("الكلمة", value=kw["keyword"],
                                                  max_chars=200)
                            e_store = st.text_input("store_id",
                                                     value=kw.get("store_id") or "")
                            e_notes = st.text_area("ملاحظة",
                                                    value=kw.get("notes") or "",
                                                    max_chars=500)
                            if st.form_submit_button("💾 حفظ"):
                                body = {
                                    "keyword":  e_kw.strip(),
                                    "store_id": e_store.strip() or None,
                                    "notes":    e_notes.strip() or None,
                                }
                                res, err = _admin_put(
                                    f"/admin/seo-opportunities/{kw['id']}",
                                    json_body=body,
                                )
                                if err:
                                    st.error(err)
                                else:
                                    st.toast("✅ حُفظ", icon="✅")
                                    st.rerun()

                with a5:
                    confirm_key = f"del_confirm_{kw['id']}"
                    if st.session_state.get(confirm_key):
                        if st.button("⚠️ أكّد الحذف", key=f"del_yes_{kw['id']}",
                                     type="primary", width='stretch'):
                            res, err = _admin_delete(f"/admin/seo-opportunities/{kw['id']}")
                            if err:
                                st.error(err)
                            else:
                                st.session_state.pop(confirm_key, None)
                                st.toast("🗑️ تم الحذف", icon="🗑️")
                                st.rerun()
                    else:
                        if st.button("🗑️ حذف", key=f"del_{kw['id']}",
                                     width='stretch'):
                            st.session_state[confirm_key] = True
                            st.rerun()

                # ── related queries (الجدول الذي يعرضه Google Trends) ──
                related_top    = kw.get("related_top")    or []
                related_rising = kw.get("related_rising") or []
                if related_top or related_rising:
                    with st.expander(
                        f"🔍 اقتراحات Google ({len(related_top)} رائج + "
                        f"{len(related_rising)} صاعد) — اضغط [+ تتبّع] لإضافته للمراقبة",
                        expanded=False,
                    ):
                        rc1, rc2 = st.columns(2)
                        # ─ الأكثر رواجاً ─
                        with rc1:
                            st.markdown("**🔥 الأكثر رواجاً (Top)**")
                            if not related_top:
                                st.caption("—")
                            for i, q in enumerate(related_top[:10]):
                                q_text = str(q.get("query") or "").strip()
                                q_val = q.get("value") or 0
                                if not q_text:
                                    continue
                                rcol1, rcol2 = st.columns([3, 1])
                                with rcol1:
                                    st.markdown(
                                        f"<div style='padding:4px 8px;background:#F3F4F6;"
                                        f"border-radius:6px;margin-bottom:4px;'>"
                                        f"<span style='color:#1F2937;'>{q_text}</span> "
                                        f"<span style='color:#6B7280;font-size:12px;'> · "
                                        f"شعبية {q_val}</span></div>",
                                        unsafe_allow_html=True,
                                    )
                                with rcol2:
                                    btn_key = f"tt_{kw['id']}_t_{i}"
                                    if st.button("+ تتبّع", key=btn_key,
                                                 width='stretch'):
                                        body = {"keyword": q_text,
                                                "store_id": kw.get("store_id")}
                                        res, err = _admin_post(
                                            "/admin/seo-opportunities/track-related",
                                            json_body=body,
                                        )
                                        if err:
                                            st.error(err)
                                        else:
                                            already = res.get("already_tracked")
                                            msg = ("موجود مسبقاً" if already
                                                   else f"تمت الإضافة #{res.get('id')}")
                                            st.toast(f"✅ {msg}", icon="✅")
                                            st.rerun()

                        # ─ الأسرع صعوداً ─
                        with rc2:
                            st.markdown("**↗️ الأسرع صعوداً (Rising)**")
                            if not related_rising:
                                st.caption("—")
                            for i, q in enumerate(related_rising[:10]):
                                q_text = str(q.get("query") or "").strip()
                                q_val = q.get("value")
                                if not q_text:
                                    continue
                                # value هنا قد يكون "Breakout" أو رقم مثل 5000 = +5000%
                                if isinstance(q_val, (int, float)) and q_val:
                                    badge = f"+{int(q_val)}%"
                                    badge_color = "#DC2626" if q_val >= 100 else "#F59E0B"
                                elif str(q_val).lower() == "breakout":
                                    badge = "🚀 Breakout"
                                    badge_color = "#7C3AED"
                                else:
                                    badge = str(q_val or "—")
                                    badge_color = "#6B7280"
                                rcol1, rcol2 = st.columns([3, 1])
                                with rcol1:
                                    st.markdown(
                                        f"<div style='padding:4px 8px;background:#FEF3C7;"
                                        f"border-radius:6px;margin-bottom:4px;"
                                        f"border-right:3px solid {badge_color};'>"
                                        f"<span style='color:#1F2937;'>{q_text}</span> "
                                        f"<span style='color:{badge_color};font-weight:bold;"
                                        f"font-size:12px;'> · {badge}</span></div>",
                                        unsafe_allow_html=True,
                                    )
                                with rcol2:
                                    btn_key = f"tt_{kw['id']}_r_{i}"
                                    if st.button("+ تتبّع", key=btn_key,
                                                 width='stretch'):
                                        body = {"keyword": q_text,
                                                "store_id": kw.get("store_id")}
                                        res, err = _admin_post(
                                            "/admin/seo-opportunities/track-related",
                                            json_body=body,
                                        )
                                        if err:
                                            st.error(err)
                                        else:
                                            already = res.get("already_tracked")
                                            msg = ("موجود مسبقاً" if already
                                                   else f"تمت الإضافة #{res.get('id')}")
                                            st.toast(f"✅ {msg}", icon="✅")
                                            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# الرصد الاجتماعي — Social Listener + Auto-Responder (Week 7-8)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "الرصد الاجتماعي":
    st.header("📡 الرصد والتفاعل الاجتماعي")
    st.caption("النظام يرصد الإشارات (mentions) عن الكوبونات والخصومات، ويجهّز ردوداً ذكية تربط لصفحات الهبوط لزيادة الزوار.")

    top1, top2 = st.columns([1, 2])
    with top1:
        if st.button("🔄 معالجة الإشارات الآن", width='stretch', type="primary"):
            with st.spinner("scoring + matching + توليد الردود…"):
                data, err = _admin_post("/admin/social-run", params={"batch": 20})
            if err:
                st.error(err)
            else:
                st.success(
                    f"رُدّ على: {data.get('responded', 0)} · "
                    f"طوبِق: {data.get('scored', 0)} · تجاهل: {data.get('ignored', 0)}"
                )
    with top2:
        st.caption("المعالجة تلقائية كل 10 دقائق على السيرفر. الاستقبال الفوري عبر POST /api/v1/social/ingest للأتمتة الخارجية.")

    with st.expander("➕ إضافة إشارة يدوياً (للاختبار)"):
        with st.form("social_ingest_form", clear_on_submit=True):
            f_platform = st.selectbox("المنصة", ["x", "telegram", "instagram", "other"])
            f_content = st.text_area("نص الإشارة / المنشن", placeholder="مثال: أبي كوبون خصم نون")
            f_author = st.text_input("الحساب (اختياري)")
            if st.form_submit_button("📨 إرسال للرصد"):
                if not (f_content or "").strip():
                    st.warning("اكتب نص الإشارة أولاً.")
                else:
                    import time as _t
                    body = {
                        "platform": f_platform,
                        "external_id": f"manual-{int(_t.time())}",
                        "content": f_content.strip(),
                        "author_handle": (f_author or "").strip() or None,
                    }
                    res, err = _admin_post("/social/ingest", json_body=body)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"تم الاستقبال ✅ (إشارة #{res.get('signal_id', '—')})")
                        st.rerun()

    st.divider()
    st.subheader("✉️ ردود بانتظار المراجعة")
    pend, err = _admin_get("/admin/social-pending", params={"limit": 50})
    if err:
        st.error(f"تعذّر جلب الردود: {err}")
    elif not pend or not pend.get("responses"):
        st.info("لا توجد ردود معلّقة. شغّل المعالجة أو أضف إشارة للاختبار.")
    else:
        st.caption(f"إجمالي المعلّق: {pend.get('total', 0)}")
        for r in pend["responses"]:
            with st.container(border=True):
                st.markdown(f"**📨 منشن ({r.get('platform')}):** {(r.get('signal_content') or '')[:220]}")
                st.caption(
                    f"👤 {r.get('author_handle') or '—'} · 🎯 نية: {r.get('intent_score')} · "
                    f"الحالة: {r.get('review_status')}"
                )
                st.markdown("**↩️ الرد المقترح:**")
                st.code(r.get("rendered_text") or "", language=None)
                act1, act2, _sp = st.columns([1, 1, 3])
                with act1:
                    if st.button("✅ اعتماد ونشر", key=f"soc_appr_{r['id']}", width='stretch', type="primary"):
                        res, e2 = _admin_post(f"/admin/social-approve/{r['id']}")
                        if e2:
                            st.error(e2)
                        else:
                            st.success("تم الاعتماد ✅" + (" (نُشر)" if res and res.get("via") == "webhook" and res.get("ok") else ""))
                            st.rerun()
                with act2:
                    if st.button("🗑️ رفض", key=f"soc_rej_{r['id']}", width='stretch'):
                        res, e2 = _admin_post(f"/admin/social-reject/{r['id']}")
                        if e2:
                            st.error(e2)
                        else:
                            st.toast("رُفض")
                            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# 🎯 رادار الصفقات الفوري — Social Leads Radar
#
# يعرض كل العملاء المحتملين الذين كتبوا منشوراً يبحث عن كوبون متجر نُغطّيه.
# المصادر الحالية المفعّلة:
#   • Reddit (مجاني، يعمل تماماً)
#   • Google Alerts → RSS (مجاني — يلتقط تغريدات X العامة + مدونات + منتديات)
#
# لكل عميل: زر "↗ افتح المنشور" → يفتحه في تبويب جديد لترد عليه يدوياً
#            زر "✅ تم الرد"    → يخفيه من شاشة pending
#            زر "🗑️ تجاهل"     → يخفيه ولا يُحسب كردّ
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🎯 رادار الصفقات الفوري":
    page_title("🎯", "رادار الصفقات الفوري",
               "اصطد العملاء قبل المنافسين — منشورات Reddit التي تطلب أكواد خصم")

    # شريط تحكّم
    _r1, _r2, _r3 = st.columns([1.5, 1.5, 3])
    with _r1:
        status_filter = st.selectbox(
            "الحالة",
            ["pending", "replied", "dismissed", "all"],
            format_func=lambda s: {
                "pending":   "⏳ ينتظر ردّك",
                "replied":   "✅ ردّيت عليه",
                "dismissed": "🗑️ متجاهَل",
                "all":       "📋 الكل",
            }[s],
            key="leads_status",
        )
    with _r2:
        if st.button("🔄 تحديث الآن", width='stretch', key="leads_refresh"):
            st.rerun()
    with _r3:
        st.caption(
            "polling تلقائي كل 10 دقائق من Reddit. "
            "للبحث الاستباقي عن طلبات قوقل استخدم صفحة «🎯 محرك الفرص»."
        )

    # جلب البيانات
    leads_data, leads_err = _admin_get("/admin/social-leads",
                                        params={"status": status_filter, "limit": 200})
    if leads_err:
        st.error(f"تعذّر جلب الـ leads: {leads_err}")
    elif not leads_data or not leads_data.get("leads"):
        if status_filter == "pending":
            st.success(
                "✅ صفر leads معلّقة. الـ polling يعمل كل 10 دقائق على Reddit. "
                "هذه الصفحة لمنشورات اجتماعية تطلب أكواد خصم — أغلبها يأتي "
                "بشكل عشوائي وقد تمضي أيام بدون ظهور أي طلب. "
                "للبحث الاستباقي بكلمات تحددها أنت، استخدم صفحة «🎯 محرك الفرص»."
            )
        else:
            st.info("لا يوجد leads بهذه الحالة.")
    else:
        total = leads_data.get("total", 0)

        # KPIs مختصرة
        urgent = sum(1 for l in leads_data["leads"] if (l.get("age_seconds") or 0) < 3600)
        with_store = sum(1 for l in leads_data["leads"] if l.get("target_store_id"))

        k1, k2, k3 = st.columns(3)
        with k1: kpi_card("🎯", "عملاء بهذه الحالة", f"{total}", "warning" if status_filter == "pending" else "info")
        with k2: kpi_card("🔥", "خلال آخر ساعة", f"{urgent}", "danger" if urgent else "neutral")
        with k3: kpi_card("🏪", "مطابَق بمتجر", f"{with_store}/{total}", "emerald")

        st.divider()

        # جدول العملاء
        for lead in leads_data["leads"]:
            age_min = (lead.get("age_seconds") or 0) // 60
            age_str = (
                f"قبل {age_min} دقيقة" if age_min < 60
                else f"قبل {age_min // 60} ساعة" if age_min < 1440
                else f"قبل {age_min // 1440} يوم"
            )

            # تحديد عاجلية اللون
            border_color = (
                "#DC2626" if age_min < 30
                else "#F59E0B" if age_min < 180
                else "#9CA3AF"
            )

            with st.container(border=True):
                # رأس البطاقة
                head_c1, head_c2, head_c3 = st.columns([3, 1.5, 1.5])
                with head_c1:
                    platform_emoji = {
                        "reddit":      "🔴",
                        "rss":         "🌐",
                        "x":           "𝕏",
                        "twitter":     "𝕏",
                        "instagram":   "📷",
                        "facebook":    "📘",
                        "telegram":    "✈️",
                    }
                    plat_key = (lead.get("platform") or "").split(":")[0].lower()
                    emoji = platform_emoji.get(plat_key, "🌐")
                    st.markdown(
                        f"{emoji} **{lead.get('platform') or '?'}** · "
                        f"👤 `{lead.get('username') or '—'}`"
                    )
                with head_c2:
                    target = lead.get("target_store") or "—"
                    if lead.get("target_store_id"):
                        st.markdown(f"🏪 **{target}** ✓")
                    else:
                        st.caption(f"🏪 {target} (غير مطابق)")
                with head_c3:
                    color = "🔴" if age_min < 30 else "🟡" if age_min < 180 else "⚪"
                    intent = lead.get("intent_score")
                    intent_str = f" · نية: {float(intent):.2f}" if intent is not None else ""
                    st.markdown(f"{color} {age_str}{intent_str}")

                # نص المنشور
                post_text = (lead.get("post_text") or "").strip()
                if post_text:
                    preview = post_text[:400] + ("…" if len(post_text) > 400 else "")
                    st.markdown(f"> _{preview}_")

                # أزرار الإجراءات
                act_c1, act_c2, act_c3, _ = st.columns([2, 1.5, 1.5, 3])
                with act_c1:
                    post_url = lead.get("post_url")
                    if post_url:
                        st.link_button(
                            "↗ افتح المنشور للرد",
                            url=post_url,
                            width='stretch',
                            type="primary",
                        )
                    else:
                        st.button(
                            "🚫 لا يوجد رابط",
                            disabled=True,
                            width='stretch',
                            key=f"nourl_{lead['lead_id']}",
                        )
                with act_c2:
                    if lead.get("status") in ("matched", "responded", "lead_pending"):
                        if st.button("✅ تم الرد", key=f"replied_{lead['lead_id']}",
                                     width='stretch'):
                            _r, e2 = _admin_post(f"/admin/social-leads/{lead['lead_id']}/mark-replied")
                            if e2:
                                st.error(e2)
                            else:
                                st.toast("✅ تم تعليمه كـ مردود عليه", icon="✅")
                                st.rerun()
                with act_c3:
                    if lead.get("status") in ("matched", "responded", "lead_pending"):
                        if st.button("🗑️ تجاهل", key=f"dismiss_{lead['lead_id']}",
                                     width='stretch'):
                            _r, e2 = _admin_post(f"/admin/social-leads/{lead['lead_id']}/dismiss")
                            if e2:
                                st.error(e2)
                            else:
                                st.toast("تم التجاهل", icon="🗑️")
                                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# سجل التدقيق — Audit log (PDPL). يسجّل عمليات الأدمن الحسّاسة: نشر SEO، البث،
# تعديل/حذف المسودّات، المسح الكامل. (ساعات الهدوء + تجارب A/B أُخفيتا.)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "سجل التدقيق":
    st.header("📜 سجل التدقيق")
    st.caption("سجل عمليات الأدمن الحسّاسة (PDPL): نشر صفحات SEO، البث، تعديل/حذف المسودّات، المسح الكامل.")

    data, err = _admin_get("/admin/audit-log", params={"limit": 200})
    if err:
        st.error(err)
    elif not data or not data.get("entries"):
        st.info("لا توجد عمليات مُسجّلة بعد.")
    else:
        import pandas as _pd
        df = _pd.DataFrame(data["entries"])
        df = df.rename(columns={"at": "الوقت", "action": "العملية", "target": "الهدف",
                                "actor": "المنفّذ", "status": "الحالة", "id": "#"})
        st.caption(f"إجمالي المعروض: {len(df)} عملية")
        st.dataframe(df, width='stretch', hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# 🎟️ أكواد إضافية — عدّة أكواد لنفس المتجر (store_extra_coupons)
#    الثابت (الاسم/الرابط/الشعار/الوصف) من master؛ هنا فقط الأكواد الإضافية.
#    الحسابات (نسخ/نقر/بحث/مفضّلة) تتجمّع للمتجر تلقائياً (التتبّع بـ store_id).
# ════════════════════════════════════════════════════════════════════════════
if page == "🎟️ أكواد إضافية":
    st.header("🎟️ أكواد إضافية")
    st.caption(
        "أضف أكواداً إضافية لمتجر موجود — كل كود بعرضه الخاص (كوبون + خصم + عرض إضافي + تواريخ). "
        "الاسم والرابط والشعار ثابتة من المتجر. النسخ/النقر/البحث/المفضّلة تتجمّع للمتجر تلقائياً."
    )

    _xsc = get_conn(); _xsc.rollback()
    try:
        _xstores = pd.read_sql(
            "SELECT id, store_id, COALESCE(NULLIF(name_en,''), store_id) AS name_en, "
            "public_coupon, discount_value FROM master ORDER BY id DESC", _xsc)
    except Exception as _e:
        st.error(f"تعذّر جلب المتاجر: {_e}"); _xstores = pd.DataFrame()
    finally:
        _xsc.close()

    if _xstores.empty:
        st.info("لا توجد متاجر بعد. أضف متجراً أولاً من «إدخال بيانات الماستر».")
    else:
        _xlabels = {int(r["id"]): f'{r["store_id"]} · {r["name_en"]} (#{int(r["id"])})'
                    for _, r in _xstores.iterrows()}
        _xsel = st.selectbox("🏪 اختر المتجر", options=list(_xlabels.keys()),
                             format_func=lambda i: _xlabels[i], key="xc_store_select")
        _xrow = _xstores[_xstores["id"] == _xsel].iloc[0]
        st.caption(
            f"🎟️ الكود الرئيسي للمتجر: **{_xrow['public_coupon'] or '—'}** · "
            f"💰 {_xrow['discount_value'] or '—'}  (يُدار من «الاستعلام والتعديل»)")

        st.divider()
        st.subheader("🎟️ الأكواد الإضافية لهذا المتجر")

        _xc = get_conn(); _xc.rollback()
        try:
            _xcoupons = pd.read_sql(
                "SELECT id, public_coupon, discount_value, extra_offer, extra_offer_en, "
                "my_coupon, start_date, end_date, sort_order FROM store_extra_coupons "
                "WHERE master_id=%s ORDER BY sort_order, id", _xc, params=(int(_xsel),))
        except Exception as _e:
            st.error(f"تعذّر جلب الأكواد: {_e}"); _xcoupons = pd.DataFrame()
        finally:
            _xc.close()

        if _xcoupons.empty:
            st.info("لا أكواد إضافية بعد لهذا المتجر — أضف أول كود أدناه.")
        else:
            st.caption(f"{len(_xcoupons)} كود — تُعرض بهذا الترتيب تحت المتجر.")
            _xn = len(_xcoupons)
            for _xi in range(_xn):
                _xr = _xcoupons.iloc[_xi]; _xcid = int(_xr["id"])
                with st.container(border=True):
                    st.markdown(f"**🎟️ {_xr['public_coupon'] or '—'}**  ·  💰 {_xr['discount_value'] or '—'}")
                    _xparts = []
                    if _xr['extra_offer']:    _xparts.append(f"➕ {_xr['extra_offer']}")
                    if _xr['extra_offer_en']: _xparts.append(f"➕ EN: {_xr['extra_offer_en']}")
                    if pd.notna(_xr['start_date']): _xparts.append(f"📅 من {_xr['start_date']}")
                    if pd.notna(_xr['end_date']):   _xparts.append(f"إلى {_xr['end_date']}")
                    if _xr['my_coupon']:      _xparts.append(f"💵 تتبّع: {_xr['my_coupon']}")
                    if _xparts:
                        st.caption(" · ".join(_xparts))
                    xb1, xb2, xb3 = st.columns(3)
                    if xb1.button("⬆️", key=f"xc_up_{_xcid}", width="stretch",
                                  disabled=(_xi == 0), help="تقديم"):
                        _xprev = _xcoupons.iloc[_xi - 1]
                        try:
                            _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                            _wcur.execute("UPDATE store_extra_coupons SET sort_order=%s WHERE id=%s",
                                          (int(_xprev["sort_order"]), _xcid))
                            _wcur.execute("UPDATE store_extra_coupons SET sort_order=%s WHERE id=%s",
                                          (int(_xr["sort_order"]), int(_xprev["id"])))
                            _wc.commit(); _wc.close(); st.rerun()
                        except Exception as _e:
                            st.error(f"تعذّر: {_e}")
                    if xb2.button("⬇️", key=f"xc_dn_{_xcid}", width="stretch",
                                  disabled=(_xi == _xn - 1), help="تأخير"):
                        _xnext = _xcoupons.iloc[_xi + 1]
                        try:
                            _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                            _wcur.execute("UPDATE store_extra_coupons SET sort_order=%s WHERE id=%s",
                                          (int(_xnext["sort_order"]), _xcid))
                            _wcur.execute("UPDATE store_extra_coupons SET sort_order=%s WHERE id=%s",
                                          (int(_xr["sort_order"]), int(_xnext["id"])))
                            _wc.commit(); _wc.close(); st.rerun()
                        except Exception as _e:
                            st.error(f"تعذّر: {_e}")
                    if xb3.button("🗑️ حذف", key=f"xc_del_{_xcid}", width="stretch"):
                        try:
                            _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                            _wcur.execute("DELETE FROM store_extra_coupons WHERE id=%s", (_xcid,))
                            _wc.commit(); _wc.close()
                            st.toast("🗑️ حُذف الكود"); st.rerun()
                        except Exception as _e:
                            st.error(f"تعذّر الحذف: {_e}")

        st.divider()
        st.subheader("➕ أضف كوداً إضافياً")
        with st.form("add_extra_coupon", clear_on_submit=True):
            xf1, xf2 = st.columns(2)
            _x_coupon = xf1.text_input("🎟️ كوبون العملاء")
            _x_disc   = xf2.text_input("💰 نسبة الخصم", placeholder="مثلاً: 25%")
            xe1, xe2 = st.columns(2)
            _x_extra    = xe1.text_input("➕ عرض إضافي (عربي)", placeholder="مثلاً: خاص بالأزياء")
            _x_extra_en = xe2.text_input("➕ Extra Offer (English)")
            xd1, xd2, xd3 = st.columns(3)
            _x_my    = xd1.text_input("💵 عمولتي (كود التتبّع، اختياري)")
            _x_start = xd2.date_input("📅 تاريخ البداية", datetime.date.today(), format="YYYY-MM-DD")
            _x_end   = xd3.date_input("📅 تاريخ الانتهاء",
                                      datetime.date.today() + datetime.timedelta(days=30),
                                      format="YYYY-MM-DD")
            if st.form_submit_button("➕ أضف الكود", type="primary"):
                if not (_x_coupon or "").strip():
                    st.warning("اكتب كوبون العملاء على الأقل.")
                else:
                    try:
                        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                        _wcur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 "
                                      "FROM store_extra_coupons WHERE master_id=%s", (int(_xsel),))
                        _xno = _wcur.fetchone()[0]
                        _wcur.execute(
                            "INSERT INTO store_extra_coupons "
                            "(master_id, public_coupon, discount_value, extra_offer, extra_offer_en, "
                            " my_coupon, start_date, end_date, sort_order) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (int(_xsel), _x_coupon.strip(),
                             (_x_disc or "").strip() or None,
                             (_x_extra or "").strip() or None,
                             (_x_extra_en or "").strip() or None,
                             (_x_my or "").strip() or None,
                             _x_start, _x_end, int(_xno)))
                        _wc.commit(); _wc.close()
                        st.success("✅ أُضيف الكود الإضافي."); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر الإضافة: {_e}")


# ════════════════════════════════════════════════════════════════════════════
# 🎨 الثيمات — خلفيات المناسبات للموقع والميني-ويب (site_themes)
#    مكتبة ثيمات؛ تفعيل واحد يطبّقه على الزوار. لا ثيم مُفعَّل = الخلفية الأصلية.
#    كل ثيم: نهاري/ليلي × سطح-مكتب/جوال (الليلي اختياري → يرجع للنهاري).
# ════════════════════════════════════════════════════════════════════════════
if page == "🎨 الثيمات":
    st.header("🎨 الثيمات")
    st.caption(
        "غيّر خلفية الموقع والميني-ويب بضغطة. ارفع ثيم مناسبة (نهاري/ليلي · سطح-مكتب/جوال) "
        "وفعّله لكل الزوار. «الثيم الأساسي» يرجّع الخلفية الخضراء الأصلية (محفوظة دائماً)."
    )

    _tc = get_conn(); _tc.rollback()
    try:
        _themes = pd.read_sql(
            "SELECT id, name, desktop_url, mobile_url, desktop_dark_url, mobile_dark_url, "
            "is_active FROM site_themes ORDER BY created_at DESC", _tc)
    except Exception as _e:
        st.error(f"تعذّر جلب الثيمات: {_e}"); _themes = pd.DataFrame()
    finally:
        _tc.close()

    _has_active = (not _themes.empty) and bool(_themes["is_active"].any())

    # ── البحث عن ثيم اسمه «الاساسي» (بأي تشكيلة من الفتحات/المسافات) ──
    # لو موجود → هو الافتراضي. غير ذلك → الخلفية الخضراء الأصلية.
    def _norm(s: str) -> str:
        return "".join(ch for ch in str(s or "") if ch.isalpha()).strip()
    _user_default_row = None
    if not _themes.empty:
        for _i in range(len(_themes)):
            if _norm(_themes.iloc[_i]["name"]) in {"الاساسي", "الأساسي"}:
                _user_default_row = _themes.iloc[_i]; break

    def _theme_deactivate_all():
        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
        _wcur.execute("UPDATE site_themes SET is_active=FALSE WHERE is_active")
        _wc.commit(); _wc.close()

    def _theme_activate(_target_id: int):
        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
        _wcur.execute("UPDATE site_themes SET is_active=FALSE WHERE is_active")
        _wcur.execute("UPDATE site_themes SET is_active=TRUE WHERE id=%s", (_target_id,))
        _wc.commit(); _wc.close()

    # ── الافتراضي ──
    # إن وُجد ثيم اسمه «الاساسي» → هو الافتراضي (يُفعَّل بدل الخلفية الخضراء).
    # غير ذلك → الخلفية الخضراء الأصلية.
    with st.container(border=True):
        dc1, dc2 = st.columns([3, 1])
        if _user_default_row is not None:
            _udid = int(_user_default_row["id"])
            _is_default_active = bool(_user_default_row["is_active"])
            dc1.markdown(f"**🟢 الافتراضي — {_user_default_row['name']}**")
            dc1.caption("ثيمك الافتراضي. أي تفعيل آخر يُلغى بالضغط هنا.")
            with dc2:
                if _is_default_active:
                    st.success("✅ مُفعّل")
                elif st.button("🟢 فعّل الافتراضي", key="theme_user_default",
                               width="stretch", type="primary"):
                    try:
                        _theme_activate(_udid)
                        st.success("✅ رجعنا لثيمك الافتراضي."); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر: {_e}")
        else:
            dc1.markdown("**🟢 الثيم الأساسي** — الخلفية الخضراء الأصلية")
            dc1.caption("الافتراضي المحفوظ دائماً. لتغيير الافتراضي: أضِف ثيماً اسمه «الاساسي».")
            with dc2:
                if not _has_active:
                    st.success("✅ مُفعّل")
                elif st.button("🟢 فعّل الأساسي", key="theme_base",
                               width="stretch", type="primary"):
                    try:
                        _theme_deactivate_all()
                        st.success("رجعنا للثيم الأساسي."); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر: {_e}")

    st.divider()
    st.subheader("🖼️ ثيمات المناسبات")
    if _themes.empty:
        st.info("لا ثيمات بعد — أضف أول ثيم أدناه.")
    else:
        for _ti in range(len(_themes)):
            _tr = _themes.iloc[_ti]; _tid = int(_tr["id"])
            with st.container(border=True):
                st.markdown(f"**{_tr['name']}**  {'✅ مُفعّل الآن' if _tr['is_active'] else ''}")
                _pv = [("☀️ نهاري · سطح مكتب", _tr["desktop_url"]),
                       ("☀️ نهاري · جوال", _tr["mobile_url"]),
                       ("🌙 ليلي · سطح مكتب", _tr["desktop_dark_url"]),
                       ("🌙 ليلي · جوال", _tr["mobile_dark_url"])]
                _pcols = st.columns(4)
                for _pc, (_lbl, _u) in zip(_pcols, _pv):
                    _pc.caption(_lbl)
                    if _u:
                        try: _pc.image(_u, width=150)
                        except Exception: pass
                    else:
                        _pc.caption("—")
                ac1, ac2 = st.columns(2)
                if _tr["is_active"]:
                    ac1.success("✅ مُفعّل")
                elif ac1.button("🚀 فعّل هذا الثيم", key=f"theme_act_{_tid}",
                                width="stretch", type="primary"):
                    try:
                        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                        _wcur.execute("UPDATE site_themes SET is_active=FALSE WHERE is_active")
                        _wcur.execute("UPDATE site_themes SET is_active=TRUE WHERE id=%s", (_tid,))
                        _wc.commit(); _wc.close()
                        st.success("✅ فُعّل الثيم — سيظهر للزوار خلال دقيقة."); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر التفعيل: {_e}")
                if ac2.button("🗑️ حذف", key=f"theme_del_{_tid}", width="stretch"):
                    try:
                        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                        _wcur.execute("DELETE FROM site_themes WHERE id=%s", (_tid,))
                        _wc.commit(); _wc.close()
                        st.toast("🗑️ حُذف الثيم"); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر الحذف: {_e}")

    st.divider()
    st.subheader("🎚️ تحكم الشفافية")
    st.caption("تتحكم بكم تظهر خلفية الثيم خلف الكروت والأيقونات. التغيير يطبَّق على الموقع خلال دقيقة (Cloudflare cache + revalidate).")

    # تحميل الإعدادات الحالية (مع fallback لو الجدول غير موجود)
    _vs_defaults = {"overlay_opacity": 0.35, "card_opacity": 0.42,
                    "icon_opacity": 0.55, "blur_px": 28}
    _vs_current = dict(_vs_defaults)
    _vc = get_conn(); _vc.rollback()
    try:
        _vcur = _vc.cursor()
        _vcur.execute(
            "SELECT overlay_opacity, card_opacity, icon_opacity, blur_px "
            "FROM site_visual_settings WHERE id=1")
        _vrow = _vcur.fetchone()
        if _vrow:
            _vs_current = {"overlay_opacity": float(_vrow[0]),
                           "card_opacity":    float(_vrow[1]),
                           "icon_opacity":    float(_vrow[2]),
                           "blur_px":         int(_vrow[3])}
    except Exception as _ve:
        _vc.rollback()
        st.warning(f"⚠️ جدول الإعدادات غير موجود — شغّل migration_050. ({_ve})")
    finally:
        _vc.close()

    with st.form("visual_settings_form"):
        st.markdown("**كل قيمة من 0 إلى 1**:  0 = شفاف تماماً (الثيم يظهر كامل)  ·  1 = معتم (الثيم مخفي).")
        vc1, vc2 = st.columns(2)
        _vs_overlay = vc1.slider(
            "🌫️ الستارة فوق الثيم",
            min_value=0.00, max_value=1.00, step=0.05,
            value=_vs_current["overlay_opacity"],
            help="كم تخفي الستارة البيضاء/الداكنة صورة الثيم. أقل = الثيم أوضح.")
        _vs_card = vc2.slider(
            "🪟 خلفية الكروت",
            min_value=0.00, max_value=1.00, step=0.05,
            value=_vs_current["card_opacity"],
            help="شفافية كروت الترند والمتاجر. أقل = الثيم يطلّ تحتها.")
        vc3, vc4 = st.columns(2)
        _vs_icon = vc3.slider(
            "🟢 خلفية أيقونات المتاجر",
            min_value=0.00, max_value=1.00, step=0.05,
            value=_vs_current["icon_opacity"],
            help="شفافية المربع/الدائرة خلف لوقو المتجر.")
        _vs_blur = vc4.slider(
            "💧 شدّة الـ blur (px)",
            min_value=0, max_value=60, step=2,
            value=_vs_current["blur_px"],
            help="ضباب الزجاج خلف الكروت — يساعد على قراءة النصوص فوق أي خلفية.")

        sb1, sb2 = st.columns(2)
        if sb1.form_submit_button("💾 احفظ الإعدادات", type="primary", width="stretch"):
            try:
                _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                _wcur.execute(
                    "INSERT INTO site_visual_settings "
                    "(id, overlay_opacity, card_opacity, icon_opacity, blur_px, updated_at) "
                    "VALUES (1, %s, %s, %s, %s, NOW()) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "overlay_opacity=EXCLUDED.overlay_opacity, "
                    "card_opacity=EXCLUDED.card_opacity, "
                    "icon_opacity=EXCLUDED.icon_opacity, "
                    "blur_px=EXCLUDED.blur_px, "
                    "updated_at=NOW()",
                    (_vs_overlay, _vs_card, _vs_icon, _vs_blur))
                _wc.commit(); _wc.close()
                st.success("✅ حُفظت الإعدادات — ستظهر على الموقع خلال دقيقة."); st.rerun()
            except Exception as _e:
                st.error(f"تعذّر الحفظ: {_e}")
        if sb2.form_submit_button("🔄 ارجع للقيم الافتراضية", width="stretch"):
            try:
                _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                _wcur.execute(
                    "UPDATE site_visual_settings SET "
                    "overlay_opacity=0.35, card_opacity=0.42, icon_opacity=0.55, "
                    "blur_px=28, updated_at=NOW() WHERE id=1")
                _wc.commit(); _wc.close()
                st.success("✅ رجعنا للافتراضي."); st.rerun()
            except Exception as _e:
                st.error(f"تعذّر: {_e}")

    st.divider()
    st.subheader("➕ أضف ثيماً")
    st.caption("المقاس المثالي: سطح المكتب 1920×1080 (16:9 أفقي) · الجوال 1080×1920 (9:16 عمودي) — أي مقاس قريب يشتغل (تُعرض بـ cover).")
    with st.form("add_site_theme", clear_on_submit=True):
        _th_name = st.text_input("🏷️ اسم الثيم", placeholder="مثلاً: اليوم الوطني ١")
        st.markdown("**☀️ النهاري** (سطح المكتب إلزامي):")
        tn1, tn2 = st.columns(2)
        _th_dd = tn1.file_uploader("☀️ نهاري · سطح مكتب — 1920×1080 (16:9 أفقي)", type=["png", "jpg", "jpeg", "webp"], key="th_dd")
        _th_dm = tn2.file_uploader("☀️ نهاري · جوال — 1080×1920 (9:16 عمودي)", type=["png", "jpg", "jpeg", "webp"], key="th_dm")
        st.markdown("**🌙 الليلي** (اختياري — لو فاضي يُستخدم النهاري في الوضع الليلي):")
        tk1, tk2 = st.columns(2)
        _th_kd = tk1.file_uploader("🌙 ليلي · سطح مكتب — 1920×1080 (16:9 أفقي)", type=["png", "jpg", "jpeg", "webp"], key="th_kd")
        _th_km = tk2.file_uploader("🌙 ليلي · جوال — 1080×1920 (9:16 عمودي)", type=["png", "jpg", "jpeg", "webp"], key="th_km")
        if st.form_submit_button("➕ احفظ الثيم", type="primary"):
            if not (_th_name or "").strip():
                st.warning("اكتب اسم الثيم.")
            elif not _th_dd:
                st.warning("ارفع صورة «نهاري · سطح مكتب» على الأقل.")
            else:
                import time as _t
                _base = int(_t.time() * 1000)
                with st.spinner("جارٍ الرفع إلى Cloudinary..."):
                    _u_dd = _upload_story_media(_th_dd.read(), f"theme_{_base}_dd")
                    _u_dm = _upload_story_media(_th_dm.read(), f"theme_{_base}_dm") if _th_dm else None
                    _u_kd = _upload_story_media(_th_kd.read(), f"theme_{_base}_kd") if _th_kd else None
                    _u_km = _upload_story_media(_th_km.read(), f"theme_{_base}_km") if _th_km else None
                if not _u_dd:
                    st.error("❌ فشل رفع الصورة الأساسية — تأكّد أن Cloudinary مضبوط على الداشبورد.")
                else:
                    try:
                        _wc = get_conn(); _wc.rollback(); _wcur = _wc.cursor()
                        _wcur.execute(
                            "INSERT INTO site_themes (name, desktop_url, mobile_url, "
                            "desktop_dark_url, mobile_dark_url) VALUES (%s,%s,%s,%s,%s)",
                            (_th_name.strip(), _u_dd, _u_dm, _u_kd, _u_km))
                        _wc.commit(); _wc.close()
                        st.success("✅ أُضيف الثيم. اضغط «فعّل» لتطبيقه."); st.rerun()
                    except Exception as _e:
                        st.error(f"تعذّر الحفظ: {_e}")


# ─── صفحة: 🩺 تشخيص النشر ───────────────────────────────────────────────────
if page == "🩺 تشخيص النشر":
    st.header("🩺 تشخيص النشر والإعدادات")
    st.caption(
        "تكشف هذه الصفحة أسباب «الشعار ما وصل» و«ما اننشر شي للسوشيال» — "
        "حالة الإعدادات على هذه البيئة + نتيجة كل منصة لآخر بث."
    )

    # 1) كشف إعدادات بيئة الداشبورد (حالة فقط — بدون كشف القيم السرّية)
    st.subheader("⚙️ إعدادات بيئة الداشبورد")
    _secret_set = bool(os.getenv("ADMIN_SHARED_SECRET"))
    api_url = os.getenv("INTERNAL_API_URL", "https://api.dealpulseksa.com")
    d1, d2, d3 = st.columns(3)
    d1.metric("Cloudinary (رفع الشعار)", "✅ مضبوط" if _CLOUDINARY_OK else "❌ مفقود")
    d2.metric("ADMIN_SHARED_SECRET (البث)", "✅ مضبوط" if _secret_set else "❌ مفقود")
    d3.metric("وجهة الـ API", "✅" if os.getenv("INTERNAL_API_URL") else "⚠️ افتراضي")
    st.code(f"INTERNAL_API_URL = {api_url}", language="text")
    if not _CLOUDINARY_OK:
        st.error(
            "❌ Cloudinary غير مضبوط هنا → أي شعار يُرفع كملف بينحفظ فاضي (logo_url = NULL). "
            "أضف `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` "
            "على خدمة الداشبورد."
        )
    if not _secret_set:
        st.error(
            "❌ `ADMIN_SHARED_SECRET` غير مضبوط هنا → البث للسوشيال لن ينطلق إطلاقاً. "
            "أضفه بنفس قيمة خدمة الـ API."
        )

    st.divider()

    # 2) حالة آخر بث لمتجر معيّن (من social_posts_log في قاعدة الإنتاج)
    st.subheader("📡 حالة البث لكل منصة")
    _last_id = None
    try:
        _c = get_conn()
        _c.rollback()  # نظّف أي transaction معلّقة (نمط متكرر في الداشبورد)
        _last_id = pd.read_sql("SELECT MAX(id) AS m FROM master", _c)["m"].iloc[0]
    except Exception as e:
        st.warning(f"تعذّر جلب آخر متجر: {e}")
    finally:
        try:
            _c.close()
        except Exception:
            pass

    _default_id = int(_last_id) if _last_id else 0
    master_id_in = st.number_input(
        "🔢 رقم المتجر (master_id)",
        min_value=0,
        value=_default_id,
        step=1,
        help="افتراضياً آخر متجر مُضاف. غيّره لفحص متجر آخر.",
    )

    if st.button("🔍 افحص هذا المتجر", type="primary"):
        try:
            _c = get_conn()
            _c.rollback()
            _store_df = pd.read_sql(
                "SELECT id, store_id, logo_url FROM master WHERE id = %s",
                _c,
                params=(int(master_id_in),),
            )
            if _store_df.empty:
                st.error(f"ما فيه متجر بالرقم {int(master_id_in)}.")
            else:
                _row = _store_df.iloc[0]
                st.markdown(f"**المتجر:** {_row['store_id']}  ·  **ID:** {int(_row['id'])}")
                _logo = _row["logo_url"]
                if _logo:
                    lc1, lc2 = st.columns([3, 1])
                    lc1.success(f"✅ logo_url موجود")
                    lc1.code(_logo, language="text")
                    try:
                        lc2.image(_logo, width=90)
                    except Exception:
                        pass
                else:
                    st.error(
                        "❌ `logo_url` فاضي (NULL) — هذا سبب اختفاء الصورة في الموقع/الميني-ويب/البوت. "
                        "صحّح Cloudinary ثم عدّل المتجر وأعد رفع الشعار."
                    )

                _logs = pd.read_sql(
                    """
                    SELECT platform, status, error_message, attempted_at
                    FROM social_posts_log
                    WHERE master_id = %s
                    ORDER BY id DESC
                    """,
                    _c,
                    params=(int(master_id_in),),
                )
                if _logs.empty:
                    st.warning(
                        "⚠️ ما فيه أي صف في `social_posts_log` لهذا المتجر → البث **ما وصل الـ API** "
                        "أصلاً. غالباً `ADMIN_SHARED_SECRET` ناقص/غير متطابق، أو `INTERNAL_API_URL` خاطئ "
                        "على خدمة الداشبورد."
                    )
                else:
                    _logs = _logs.rename(columns={
                        "platform": "المنصة",
                        "status": "الحالة",
                        "error_message": "الخطأ",
                        "attempted_at": "وقت المحاولة",
                    })
                    st.dataframe(_logs, hide_index=True, width='stretch')
                    _counts = _logs["الحالة"].value_counts().to_dict()
                    st.caption(
                        "📊 " + " · ".join(f"{k}: {v}" for k, v in _counts.items())
                        + "  —  `sent`=نُشر، `skipped`=المنصة غير مضبوطة (توكنات ناقصة على الـ API)، "
                        "`failed`=حاول وفشل (راجع عمود الخطأ)."
                    )
        except Exception as e:
            st.error(f"خطأ في الاستعلام: {e}")
        finally:
            try:
                _c.close()
            except Exception:
                pass


# ─── صفحة: 🛰️ متابعة المنصة ────────────────────────────────────────────────
# مركز واحد لكل ما يخص نظام «توجيهات AI» التلقائي: التوجيهات المُنتَجة،
# استهلاك الذكاء الاصطناعي وتكلفته، التنبيهات والكاش، والضوابط (تشغيل/إيقاف،
# تقييد التكرار، بريد المستلِم). كل هذا كان مبعثراً في خدمة الـ API بلا واجهة.
if page == "🛰️ متابعة المنصة":
    st.header("🛰️ متابعة المنصة")
    st.caption(
        "مركز التحكم بنظام «توجيهات AI» التلقائي — المُولّد الذي يرسل لك إيميل "
        "كل بضع ساعات. من هنا تشوف ما يُنتجه، كم يكلّف، وتضبط متى وكيف يشتغل."
    )

    # ── ضوابط platform_settings عبر اتصال الداشبورد (نفس قاعدة الـ API) ──
    _PS_DDL = """
        CREATE TABLE IF NOT EXISTS platform_settings (
            key VARCHAR(60) PRIMARY KEY, value TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_by VARCHAR(80))
    """

    def _ps_get_all() -> dict:
        out = {}
        try:
            c = get_conn(); c.rollback()
            cur = c.cursor()
            cur.execute(_PS_DDL)
            cur.execute("SELECT key, value FROM platform_settings")
            out = {k: v for k, v in cur.fetchall()}
            c.commit(); c.close()
        except Exception as e:
            st.warning(f"تعذّر قراءة الإعدادات: {e}")
        return out

    def _ps_set_many(items: dict) -> bool:
        try:
            c = get_conn(); c.rollback()
            cur = c.cursor()
            cur.execute(_PS_DDL)
            for k, v in items.items():
                cur.execute(
                    """INSERT INTO platform_settings (key, value, updated_at, updated_by)
                       VALUES (%s, %s, NOW(), 'dashboard')
                       ON CONFLICT (key) DO UPDATE
                       SET value = EXCLUDED.value, updated_at = NOW(), updated_by = 'dashboard'""",
                    (k, v),
                )
            c.commit(); c.close()
            return True
        except Exception as e:
            st.error(f"تعذّر حفظ الإعدادات: {e}")
            return False

    def _safe_df(sql: str, params=None) -> pd.DataFrame:
        """read_sql مع تنظيف الـ transaction؛ يرجّع DataFrame فارغاً عند أي خطأ/جدول مفقود."""
        c = None
        try:
            c = get_conn(); c.rollback()
            return pd.read_sql(sql, c, params=params)
        except Exception:
            return pd.DataFrame()
        finally:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass

    _ps = _ps_get_all()
    _enabled = _ps.get("directive_enabled", "1") == "1"
    _min_hours = _ps.get("directive_min_hours", "0") or "0"
    _recipient = (_ps.get("directive_recipient", "") or "").strip()

    # ── شريط مؤشرات سريع ──
    _stat = _safe_df("""
        SELECT
            MAX(generated_at)                                              AS last_at,
            COUNT(*) FILTER (WHERE generated_at > NOW() - INTERVAL '24 hours') AS last_24h,
            COALESCE(SUM(cost_usd) FILTER (WHERE generated_at > NOW() - INTERVAL '7 days'), 0) AS cost_7d
        FROM ai_directives
    """)
    k1, k2, k3, k4 = st.columns(4)
    if not _stat.empty and pd.notna(_stat["last_at"].iloc[0]):
        _last = pd.to_datetime(_stat["last_at"].iloc[0])
        _ago = (pd.Timestamp.now(tz=_last.tz) - _last)
        _hrs = _ago.total_seconds() / 3600
        k1.metric("آخر توجيه", f"قبل {_hrs:.1f} ساعة" if _hrs < 48 else f"قبل {_hrs/24:.0f} يوم")
        k2.metric("توجيهات (24س)", int(_stat["last_24h"].iloc[0]))
        k3.metric("تكلفة AI (7 أيام)", f"${float(_stat['cost_7d'].iloc[0]):.4f}")
    else:
        k1.metric("آخر توجيه", "لا يوجد بعد")
        k2.metric("توجيهات (24س)", 0)
        k3.metric("تكلفة AI (7 أيام)", "$0.0000")
    k4.metric("حالة المولّد", "🟢 مفعّل" if _enabled else "🔴 موقوف")

    if not _enabled:
        st.warning("⏸️ المولّد **موقوف** حالياً — لن تصلك إيميلات توجيهات حتى تعيد تفعيله من تبويب «الضوابط».")

    tab_dir, tab_cost, tab_alerts, tab_ctrl = st.tabs(
        ["🧠 التوجيهات", "💸 استهلاك الذكاء", "📬 التنبيهات والكاش", "⚙️ الضوابط"]
    )

    # ════════════════ تبويب 1: التوجيهات ════════════════
    with tab_dir:
        c_a, c_b = st.columns([1, 3])
        with c_a:
            if st.button("⚡ ولّد توجيهاً الآن", type="primary", width="stretch",
                         help="يستدعي الـ API مباشرة لإنتاج توجيه فوري (بدون انتظار الجدولة)."):
                with st.spinner("جارٍ توليد التوجيه عبر الـ API... (~30 ثانية)"):
                    data, err = _admin_post("/admin/trigger-directive")
                if err:
                    st.error(f"فشل التوليد: {err}")
                elif data:
                    if data.get("refused_by_guardian"):
                        st.warning(f"الحارس المالي رفض الاستدعاء: {data.get('refused_reason')}")
                    else:
                        _src = "كاش" if data.get("cache_hit") else ("محاكاة" if data.get("is_mock") else data.get("provider"))
                        st.success(
                            f"✅ تم — {data.get('directives_count', 0)} توجيه · "
                            f"المصدر: {_src} · النموذج: {data.get('model')} · "
                            f"تكلفة: ${float(data.get('cost_usd') or 0):.5f}"
                        )
                        st.rerun()
        with c_b:
            st.caption(
                "التوجيهات تُنتَج تلقائياً عبر مجدول الـ API. الزر هنا للتوليد الفوري "
                "اليدوي (يحتاج `ADMIN_SHARED_SECRET` + `INTERNAL_API_URL` مضبوطين على الداشبورد)."
            )

        with st.expander("👁️ معاينة لقطة صحّة المنصة (نفس ما يُلحق بكل إيميل)"):
            st.caption("المستخدمون · أعلى المتاجر نسخاً/نقراً · أداء الموقع · الأمان · "
                       "القفزات الحقيقية · المتاجر البرتقالية · فجوات البحث.")
            if st.button("🔄 احسب اللقطة الآن"):
                try:
                    from api.utils.platform_health import build_health_report, render_health_html
                    _rep = build_health_report()
                    st.markdown(render_health_html(_rep), unsafe_allow_html=True)
                except Exception as _he:
                    st.error(f"تعذّرت المعاينة هنا: {_he}")

        st.divider()
        _df_dir = _safe_df("""
            SELECT id, generated_at, model, summary_ar, directive_ar,
                   confidence, cost_usd, cache_hit, token_input, token_output,
                   affected_master_ids, superseded_by
            FROM ai_directives
            ORDER BY generated_at DESC
            LIMIT 30
        """)
        if _df_dir.empty:
            st.info("ما فيه توجيهات بعد — اضغط «ولّد توجيهاً الآن» أو انتظر الجدولة التلقائية.")
        else:
            st.markdown(f"**آخر {len(_df_dir)} توجيه:**")
            for _, r in _df_dir.iterrows():
                _when = pd.to_datetime(r["generated_at"]).strftime("%Y-%m-%d %H:%M")
                _badge = "🟢 كاش" if r["cache_hit"] else "🔵 جديد"
                _sup = " · ⛔ مُستبدَل" if pd.notna(r["superseded_by"]) else ""
                _title = f"#{int(r['id'])} · {_when} · {r['model']} · {_badge}{_sup} — {r['summary_ar'] or '—'}"
                with st.expander(_title):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("التكلفة", f"${float(r['cost_usd'] or 0):.5f}")
                    m2.metric("التوكنز", f"{int(r['token_input'] or 0)}→{int(r['token_output'] or 0)}")
                    m3.metric("الثقة", f"{float(r['confidence']):.0%}" if pd.notna(r["confidence"]) else "—")
                    # تفكيك directive_ar (JSON) لعرض التوجيهات منظّمة
                    try:
                        _parsed = json.loads(r["directive_ar"])
                        _items = _parsed.get("directives", []) if isinstance(_parsed, dict) else []
                    except Exception:
                        _items = []
                    if _items:
                        _prio_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                        for i, d in enumerate(_items, 1):
                            _pe = _prio_emoji.get(d.get("priority", "medium"), "⚪")
                            st.markdown(f"**{_pe} {i}. {d.get('action', '')}**")
                            if d.get("rationale"):
                                st.caption(f"السبب: {d['rationale']}")
                            if d.get("affected_master_ids"):
                                st.caption(f"متاجر متأثرة: {d['affected_master_ids']}")
                    else:
                        st.code(r["directive_ar"], language="json")

    # ════════════════ تبويب 2: استهلاك الذكاء ════════════════
    with tab_cost:
        st.subheader("💸 استهلاك LLM وتكلفته")
        _df_log = _safe_df("""
            SELECT called_at, purpose, model, cache_hit, tokens_input,
                   tokens_output, cost_usd, latency_ms, success, error_message
            FROM llm_call_log
            WHERE called_at > NOW() - INTERVAL '7 days'
            ORDER BY called_at DESC
            LIMIT 500
        """)
        if _df_log.empty:
            st.info("ما فيه استدعاءات LLM مسجّلة في آخر 7 أيام.")
        else:
            _total = len(_df_log)
            _ok = int(_df_log["success"].sum())
            _cost = float(_df_log["cost_usd"].fillna(0).sum())
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("استدعاءات (7 أيام)", _total)
            cc2.metric("نسبة النجاح", f"{(_ok/_total*100):.0f}%")
            cc3.metric("التكلفة الكلية", f"${_cost:.5f}")
            cc4.metric("متوسط الزمن", f"{int(_df_log['latency_ms'].fillna(0).mean())} ms")

            st.markdown("**حسب النموذج:**")
            _by_model = (_df_log.groupby("model")
                         .agg(عدد=("model", "size"),
                              التكلفة=("cost_usd", lambda s: round(s.fillna(0).sum(), 5)),
                              نجاح=("success", "sum"))
                         .reset_index().rename(columns={"model": "النموذج"})
                         .sort_values("عدد", ascending=False))
            st.dataframe(_by_model, hide_index=True, width='stretch')

            _fails = _df_log[~_df_log["success"]]
            if not _fails.empty:
                st.markdown(f"**آخر الإخفاقات ({len(_fails)}):**")
                _fv = _fails[["called_at", "model", "error_message"]].head(15).rename(columns={
                    "called_at": "الوقت", "model": "النموذج", "error_message": "الخطأ"})
                st.dataframe(_fv, hide_index=True, width='stretch')

    # ════════════════ تبويب 3: التنبيهات والكاش ════════════════
    with tab_alerts:
        st.subheader("📬 طابور التنبيهات (ai_alerts)")
        _df_al = _safe_df("""
            SELECT dispatch_status, COUNT(*) AS n
            FROM ai_alerts GROUP BY dispatch_status
        """)
        if _df_al.empty:
            st.info("ما فيه تنبيهات مسجّلة.")
        else:
            _counts = {r["dispatch_status"]: int(r["n"]) for _, r in _df_al.iterrows()}
            a1, a2, a3 = st.columns(3)
            a1.metric("⏳ بالانتظار", _counts.get("pending", 0))
            a2.metric("✅ أُرسلت", _counts.get("sent", 0))
            a3.metric("❌ فشلت", _counts.get("failed", 0))
            _recent = _safe_df("""
                SELECT created_at, severity, title, dispatch_status, dispatch_error
                FROM ai_alerts ORDER BY created_at DESC LIMIT 20
            """)
            if not _recent.empty:
                _recent = _recent.rename(columns={
                    "created_at": "الوقت", "severity": "الخطورة", "title": "العنوان",
                    "dispatch_status": "الحالة", "dispatch_error": "الخطأ"})
                st.dataframe(_recent, hide_index=True, width='stretch')

        st.divider()
        st.subheader("🗃️ كاش الذكاء الاصطناعي (llm_semantic_cache)")
        _df_cache = _safe_df("""
            SELECT COUNT(*) AS rows,
                   COALESCE(SUM(hit_count), 0) AS hits,
                   COALESCE(SUM(tokens_saved), 0) AS saved,
                   COUNT(*) FILTER (WHERE expires_at > NOW()) AS live
            FROM llm_semantic_cache WHERE purpose = 'directive'
        """)
        if _df_cache.empty or int(_df_cache["rows"].iloc[0]) == 0:
            st.info("الكاش فارغ حالياً.")
        else:
            r = _df_cache.iloc[0]
            ch1, ch2, ch3 = st.columns(3)
            ch1.metric("صفوف الكاش", f"{int(r['rows'])} ({int(r['live'])} حيّة)")
            ch2.metric("مرات الاستفادة", int(r["hits"]))
            ch3.metric("توكنز موفّرة", f"{int(r['saved']):,}")
            st.caption("كل cache hit = استدعاء LLM مجاني بدل مدفوع. الكاش يعيش 6 ساعات لكل توجيه.")

    # ════════════════ تبويب 4: الضوابط ════════════════
    with tab_ctrl:
        st.subheader("⚙️ ضوابط المولّد")
        st.caption(
            "هذه الإعدادات تُحفظ في قاعدة البيانات ويقرأها عامل الـ API في كل دورة — "
            "تأخذ مفعولها خلال دقائق **بدون إعادة نشر**."
        )
        with st.form("directive_settings"):
            f_enabled = st.toggle(
                "تفعيل مولّد التوجيهات", value=_enabled,
                help="إيقافه يوقف الإيميلات التلقائية كلياً (المفتاح الرئيسي).")
            f_min = st.number_input(
                "أقل فاصل بين إيميلين (ساعات)", min_value=0.0, max_value=168.0,
                value=float(_min_hours), step=1.0,
                help="0 = بلا تقييد (يتبع جدولة الـ API كل 3 ساعات). مثال: 12 = إيميل كل 12 ساعة كحدّ أدنى.")
            f_to = st.text_input(
                "بريد المستلِم (اختياري)", value=_recipient,
                placeholder="اتركه فارغاً للبريد الافتراضي (OPS_ALERT_EMAIL)",
                help="يتجاوز وجهة الإيميل الافتراضية لهذا التقرير فقط.")
            if st.form_submit_button("💾 حفظ الضوابط", type="primary"):
                if _ps_set_many({
                    "directive_enabled": "1" if f_enabled else "0",
                    "directive_min_hours": str(f_min),
                    "directive_recipient": f_to.strip(),
                }):
                    st.success("✅ تم الحفظ — سيلتزم بها العامل في الدورة القادمة.")
                    st.rerun()

        st.divider()
        st.caption(
            "ℹ️ الجدولة الأساسية (كل كم ساعة يفحص العامل) تُضبط من متغيّر البيئة "
            "`WORKER_DIRECTIVE_HOURS` على خدمة الـ API. «أقل فاصل» هنا يقيّد الإرسال "
            "فوق الجدولة دون لمس البيئة."
        )

