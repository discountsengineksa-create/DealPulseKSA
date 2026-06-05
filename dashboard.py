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


def _admin_post(path: str, params: dict | None = None, json_body: dict | None = None):
    """POST على /api/v1{path}. يرجّع (data, error)."""
    base, secret = _admin_api()
    if not secret:
        return None, "ADMIN_SHARED_SECRET غير مضبوط في بيئة الداشبورد"
    try:
        r = requests.post(f"{base}/api/v1{path}",
                          headers={"X-Admin-Secret": secret},
                          params=params or {}, json=json_body, timeout=90)
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

/* ── إخفاء أيقونة Material Icons داخل القائمة الجانبية ──
(تظهر كنص حرفي keyboard_arrow_down لأن قاعدة font-family: Cairo
التالية تطغى على خط Material Symbols Rounded) */
[data-testid="stSidebar"] span[data-testid="stIconMaterial"] {{
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
        return pg_pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=db_url)
    return pg_pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
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
# action_time يُكتب بـ NOW() على خادم Railway (UTC) → الرياض = UTC+3 (بدون توقيت صيفي).
RIYADH_TZ_OFFSET_HOURS = 3
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
"إدخال بيانات الماستر", "الاستعلام والتعديل", "جدول الكوبونات",
"📦 أرشيف المنتهية",
"جدول الأقسام", "البحث عن كود", "طلبات الأكواد", "بيانات المستخدمين",
"مستخدمو الموقع",
]
_ANALYSIS_PAGES = [
"🎬 تحليلات الستوري",
"تحليل المتاجر", "تحليل الأقسام",
"تحليل طلبات الأكواد", "تحليل المستخدمين", "تحليل الموقع",
"👥 الحضور الحي",
]
_OTHER_PAGES = [
"📣 بلاغات الأكواد",  # ← Migration 029: بلاغات لا يعمل + إدارة المتاجر المسحوبة
"📊 تقرير الشركاء",   # ← Demo Pack للشركات المتعاقدة (KPI نظيف + تصدير)
"مركز الإشعارات", "لوحة القيادة", "مركز الدعم",
"مختبر النمو", "رادار المنافسين", "استوديو المحتوى",
"ذكاء التنبؤ", "نظام الولاء", "التحكم الآلي", "التخصيص الفائق",
"رادار المناسبات", "مركز التوسع", "درع الحماية",
"مركز الصيانة", "مدير القناة", "المحفز الفوري",
"محرّك SEO", "📤 الصفحات المنشورة", "🎯 محرك الفرص", "الرصد الاجتماعي", "🎯 رادار الصفقات الفوري", "التدقيق والتجارب",
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

        # الصف 7: إشهار / إعلان مدفوع
        st.divider()
        is_promoted_input = st.checkbox(
            "📣 إشهار (إعلان مدفوع) — يظهر في قسم «المتاجر المختارة» أعلى الموقع",
            value=False,
            key="is_promoted_add",
            help="فعّل هذا الخيار للمتاجر التي دفعت مقابل الظهور في الواجهة الأمامية كإعلان مميّز."
        )

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
                        bool(is_promoted_input),
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
        df_views["action_time"] = (pd.to_datetime(df_views["action_time"])
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
        df_search["search_date"] = (pd.to_datetime(df_search["search_date"])
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
               "لوحة قرار: مين تركّز عليه · مين تطيّره · مين تعطيه ترند — كل المتاجر بالأرقام الفعلية")

    CHAN_MAP = {"bot": "📱 بوت", "web": "🌐 ويب",
                "telegram_miniapp": "🔹 بوت - ميني", "miniapp": "🔹 بوت - ميني"}
    SRC_FILTER = {"📱 بوت": ["bot"], "🌐 ويب": ["web"],
                  "🔹 بوت - ميني": ["telegram_miniapp", "miniapp"]}

    # ── شريط التحكم ──────────────────────────────────────────────────────────
    c_ref, c_src, c_hint = st.columns([1, 2.4, 2.6])
    with c_ref:
        if st.button("🔄 تحديث", width='stretch'):
            _sa_load_actions.clear(); _sa_load_master.clear(); _sa_load_searches.clear()
            st.rerun()
    with c_src:
        src_choice = st.radio("المصدر:", ["الكل", "📱 بوت", "🌐 ويب", "🔹 بوت - ميني"],
                              horizontal=True, key="sm_src")
    with c_hint:
        st.caption("أرقام فعلية من action_logs و direct_search · مخزّنة 3 دقائق.")

    try:
        df_logs = _sa_load_actions()
        df_master = _sa_load_master()
        df_search = _sa_load_searches()
    except Exception as e:
        st.error(f"⚠️ تعذّر تحميل البيانات: {e}")
        st.stop()

    if df_master.empty:
        st.info("📭 لا توجد متاجر في الماستر بعد.")
        st.stop()

    # ── استبعاد الكوبونات المنتهية (تاريخ الانتهاء فات) — مكانها «📦 أرشيف المنتهية» ──
    _today_d = pd.Timestamp.today().date()
    if "last_time" in df_master.columns:
        _lt = pd.to_datetime(df_master["last_time"], errors="coerce").dt.date
        df_master = df_master[_lt.isna() | (_lt >= _today_d)].copy()
    if df_master.empty:
        st.info("📭 لا توجد متاجر فعّالة (غير منتهية) حالياً. شوف صفحة «📦 أرشيف المنتهية».")
        st.stop()
    active_ids = set(df_master["store_id"])
    if not df_logs.empty:
        df_logs = df_logs[df_logs["store_id"].isin(active_ids)].copy()
    if not df_search.empty:
        df_search = df_search[df_search["store_id"].isin(active_ids)].copy()

    # ── توقيت الرياض + توحيد الحقول ──────────────────────────────────────────
    df_logs = df_logs.copy()
    if not df_logs.empty:
        df_logs["action_time"] = (pd.to_datetime(df_logs["action_time"])
                                  + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        df_logs["adate"] = df_logs["action_time"].dt.date
        df_logs["source"] = df_logs["source"].fillna("bot")
        # المدينة الحقيقية = من الـ IP (action_logs.city) لكل المصادر: البوت يلتقطها وقت
        # نقر الرابط عبر التحويل /go، والويب/الميني من الإثراء. bu_city افتراضية فلا نعتمدها.
        df_logs["city_c"] = (df_logs["geo_city"].fillna("").astype(str)
                             .str.strip().replace("", "غير معروف"))
        df_logs["src_ar"] = df_logs["source"].map(CHAN_MAP).fillna("🌐 ويب")

        def _clean(v):
            """يحوّل أي قيمة لـ str ويتجاهل NaN/None (تجنّب ظهور 'nan' حرفياً)."""
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        def _identity(r):
            src = r["source"]
            # ميني-ويب: مستخدم تيليجرام معروف — استخدم اسم التيليجرام أولاً
            # (نفس منطق البوت). LEFT JOIN bot_users يربط user_id → bu_username
            # تلقائياً في SQL، فالاسم متاح هنا حتى لمصدر telegram_miniapp.
            if src in ("telegram_miniapp", "miniapp"):
                u = _clean(r.get("bu_username"))
                if u:
                    return "@" + u.lstrip("@")
                uid = r.get("user_id")
                if pd.notna(uid):
                    return f"🔹 بوت - ميني {int(uid)}"
                h = _clean(r.get("ip_hex"))
                if h:
                    return f"🔹 بوت - ميني #{h[:6]}"
                return "🔹 بوت - ميني (غير مسجّل)"
            # ويب عادي: زائر مجهول → name/email/phone لو مسجّل، وإلا ip_hex
            if src == "web":
                for k in ("web_name", "web_email", "web_phone"):
                    v = _clean(r.get(k))
                    if v:
                        return v
                h = _clean(r.get("ip_hex"))
                if h:
                    return f"🌐 زائر ويب #{h[:6]}"
                return "🌐 زائر ويب (غير مسجّل)"
            # البوت (افتراضي): اسم تيليجرام → id → مجهول
            u = _clean(r.get("bu_username"))
            if u:
                return "@" + u.lstrip("@")
            uid = r.get("user_id")
            return f"تيليجرام {int(uid)}" if pd.notna(uid) else "مجهول"
        df_logs["identity"] = df_logs.apply(_identity, axis=1)
    else:
        for c in ["adate", "source", "city_c", "src_ar", "identity"]:
            df_logs[c] = pd.Series(dtype="object")

    if not df_search.empty:
        df_search = df_search.copy()
        df_search["search_date"] = (pd.to_datetime(df_search["search_date"])
                                    + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        df_search["adate"] = df_search["search_date"].dt.date

    # ── فلتر الفترة ──────────────────────────────────────────────────────────
    if not df_logs.empty:
        _min_d, _max_d = df_logs["adate"].min(), df_logs["adate"].max()
    elif not df_search.empty:
        _min_d, _max_d = df_search["adate"].min(), df_search["adate"].max()
    else:
        import datetime as _dt
        _min_d = _max_d = _dt.date.today()

    dcol1, dcol2 = st.columns([2, 3])
    with dcol1:
        _dr = st.date_input("📅 الفترة (من → إلى):", value=(_min_d, _max_d),
                            min_value=_min_d, max_value=_max_d, key="sm_dates")
    d_start, d_end = (_dr if isinstance(_dr, (list, tuple)) and len(_dr) == 2 else (_min_d, _max_d))
    if not df_logs.empty:
        df_logs = df_logs[(df_logs["adate"] >= d_start) & (df_logs["adate"] <= d_end)]
    if not df_search.empty:
        df_search = df_search[(df_search["adate"] >= d_start) & (df_search["adate"] <= d_end)]

    # ── نطاق المصدر (يحدّد أرقام اللوحة) ──────────────────────────────────────
    if src_choice in SRC_FILTER and not df_logs.empty:
        df_scope = df_logs[df_logs["source"].isin(SRC_FILTER[src_choice])]
    else:
        df_scope = df_logs

    def _search_scope(ds):
        if ds is None or ds.empty:
            return ds
        p = ds["platform"].astype(str).str.lower()
        is_mini = p.str.contains("mini")          # Miniapp / telegram_miniapp / TelegramMiniApp
        if src_choice == "📱 بوت":
            # البوت فقط — نستبعد الميني صراحةً حتى لو تسميته تحوي «telegram»
            return ds[(p.str.contains("telegram") | p.str.contains("bot")) & ~is_mini]
        if src_choice == "🌐 ويب":
            return ds[p.str.contains("web")]
        if src_choice == "🔹 بوت - ميني":
            return ds[is_mini]
        return ds
    df_search_scope = _search_scope(df_search)

    with dcol2:
        st.caption(f"📅 {d_start} ← {d_end} · المصدر: {src_choice} · "
                   f"أحداث: **{len(df_scope):,}**")

    # ── تجميع لكل متجر (قاعدة = كل متاجر الماستر، حتى الخاملة بصفر) ───────────
    def _store_agg(d, ds):
        piv = (d.groupby(["store_id", "action_type"]).size().unstack(fill_value=0)
               if not d.empty else pd.DataFrame())
        for c in ["click_link", "copy_coupon"]:
            if c not in piv.columns:
                piv[c] = 0
        piv = piv.rename(columns={"click_link": "نقرات", "copy_coupon": "نسخ"})
        piv = piv[["نقرات", "نسخ"]] if not piv.empty else pd.DataFrame(columns=["نقرات", "نسخ"])
        if ds is not None and not ds.empty:
            sps = ds[ds["store_id"].notna()].groupby("store_id").size().rename("بحث")
        else:
            sps = pd.Series(dtype="int64", name="بحث")
        return piv.join(sps, how="outer")

    ev = _store_agg(df_scope, df_search_scope)
    stores_all = df_master[["store_id", "is_trending", "logo_url"]].drop_duplicates("store_id").copy()
    agg = stores_all.merge(ev, left_on="store_id", right_index=True, how="left")
    for c in ["نقرات", "نسخ", "بحث"]:
        if c not in agg.columns:
            agg[c] = 0
        agg[c] = agg[c].fillna(0).astype(int)

    # ── أعداد المفضّلين لكل متجر (kind='store') — التفضيل كإشارة قرار مباشرة في
    #    لوحة القرار، تناظراً مع عمود «مفضّلون» في صفحة «تحليل الأقسام». ──
    try:
        _favs_all = _sa_load_favorites()
    except Exception:
        _favs_all = pd.DataFrame()
    if not _favs_all.empty and "kind" in _favs_all.columns:
        _favs_store = _favs_all[_favs_all["kind"] == "store"].copy()
        # احترام فلتر المصدر (platform) المختار أعلى الصفحة
        _PLAT_F = {"📱 بوت": ["bot"], "🌐 ويب": ["web"], "🔹 بوت - ميني": ["miniapp"]}
        if src_choice in _PLAT_F:
            _favs_store = _favs_store[_favs_store["platform"].isin(_PLAT_F[src_choice])]
        if not _favs_store.empty:
            _fav_cnt = _favs_store.groupby("store_id").size().rename("مفضّلون")
            agg = agg.merge(_fav_cnt, left_on="store_id", right_index=True, how="left")
    if "مفضّلون" not in agg.columns:
        agg["مفضّلون"] = 0
    agg["مفضّلون"] = agg["مفضّلون"].fillna(0).astype(int)

    # الإجمالي = أحداث التفاعل فقط (نقر/نسخ/بحث). التفضيل إشارة منفصلة لا تُجمع هنا.
    agg["الإجمالي"] = agg["نقرات"] + agg["نسخ"] + agg["بحث"]
    agg["is_trending"] = agg["is_trending"].fillna("عادي")
    agg["logo_url"] = agg["logo_url"].fillna("")
    agg["مُترند"] = agg["is_trending"].apply(lambda s: "🔥" if "ترند" in str(s) else "")

    # ── محرّك التوصية ────────────────────────────────────────────────────────
    n_stores = len(agg)
    q_hi = agg["نسخ"].quantile(0.75) if n_stores >= 4 else agg["نسخ"].max()
    q_lo = agg["نسخ"].quantile(0.25) if n_stores >= 4 else 0
    s_hi = agg["بحث"].quantile(0.75) if n_stores >= 4 else agg["بحث"].max()

    def _reco(r):
        trending = "ترند" in str(r["is_trending"])
        if r["الإجمالي"] == 0:
            return "💤 خامل — مرشّح للإيقاف"
        if r["نسخ"] >= q_hi and r["نسخ"] > 0 and not trending:
            return "🔥 رشّح للترند"
        if trending and r["نسخ"] <= q_lo:
            return "⬇️ اسحب الترند"
        if r["بحث"] >= s_hi and r["بحث"] > 0 and r["نسخ"] <= q_lo:
            return "⚠️ مطلوب وضعيف — راجع العرض"
        if r["نسخ"] <= q_lo and not trending:
            return "🪫 ضعيف — قلّل التركيز"
        return "✅ مستقر"
    agg["التوصية"] = agg.apply(_reco, axis=1)
    agg = agg.sort_values(["نسخ", "الإجمالي"], ascending=False).reset_index(drop=True)
    agg.insert(0, "#", range(1, len(agg) + 1))

    # ── 6 كروت: الأعلى/الأقل لكل مؤشر ────────────────────────────────────────
    def _hi(col):
        return agg.sort_values([col, "الإجمالي"], ascending=False).iloc[0]
    def _lo(col):
        return agg.sort_values([col, "الإجمالي"], ascending=True).iloc[0]
    hn, ln = _hi("نسخ"), _lo("نسخ")
    hs, ls = _hi("بحث"), _lo("بحث")
    hc, lc = _hi("نقرات"), _lo("نقرات")

    r1a, r1b, r1c = st.columns(3)
    with r1a: kpi_card("🏆", "الأعلى نسخاً (ركّز)", f"{hn['store_id']}", "emerald", note=f"{int(hn['نسخ'])} نسخة")
    with r1b: kpi_card("🔍", "الأعلى بحثاً", f"{hs['store_id']}", "info", note=f"{int(hs['بحث'])} بحث")
    with r1c: kpi_card("🖱️", "الأعلى نقراً", f"{hc['store_id']}", "warning", note=f"{int(hc['نقرات'])} نقرة")
    r2a, r2b, r2c = st.columns(3)
    with r2a: kpi_card("🗑️", "الأقل نسخاً (طيّره؟)", f"{ln['store_id']}", "danger", note=f"{int(ln['نسخ'])} نسخة")
    with r2b: kpi_card("📉", "الأقل بحثاً", f"{ls['store_id']}", "neutral", note=f"{int(ls['بحث'])} بحث")
    with r2c: kpi_card("🔻", "الأقل نقراً", f"{lc['store_id']}", "neutral", note=f"{int(lc['نقرات'])} نقرة")

    _SM_TABS = [
        "🏆 لوحة القرار (كل المتاجر)",
        "👤 مين نسخ من متجر",
        "📈 الرسوم والمعدلات",
        "❤️ المفضلة",
        "🔥 الترند",
    ]
    # radio بدل st.tabs: يثبّت التبويب المختار عبر إعادة التشغيل. st.tabs يرجع
    # للتبويب الأول مع أي rerun (تغيير الفلتر أو زر «تحديث») — هذا يبقيك مكانك.
    _sm_tab = st.radio("العرض:", _SM_TABS, horizontal=True,
                       key="sm_active_tab", label_visibility="collapsed")

    # ─────────────────────────── لوحة القرار ───────────────────────────
    if _sm_tab == _SM_TABS[0]:
        st.caption("كل متاجر الماستر تظهر (حتى الخاملة بصفر) · مرتّبة بالنسخ · «التوصية» قاعدة آلية. "
                   "اضغط رأس أي عمود للفرز.")
        q = st.text_input("🔎 ابحث عن متجر:", key="sm_board_q")
        board = agg.copy()
        if q:
            board = board[board["store_id"].str.contains(q, case=False, na=False)]
        view = pd.DataFrame({
            "#": board["#"].values,
            "الشعار": board["logo_url"].values,
            "المتجر": board["store_id"].values,
            "🔥": board["مُترند"].values,
            "نسخ": board["نسخ"].values,
            "نقرات": board["نقرات"].values,
            "بحث": board["بحث"].values,
            "❤️": board["مفضّلون"].values,
            "الإجمالي": board["الإجمالي"].values,
            "التوصية": board["التوصية"].values,
        })
        _maxtot = int(max(1, agg["الإجمالي"].max()))
        st.dataframe(
            view, hide_index=True, width='stretch',
            column_config={
                "الشعار": st.column_config.ImageColumn("🏪", width="small"),
                "❤️": st.column_config.NumberColumn("❤️ مفضّلون", help="عدد الأشخاص الذين أضافوا المتجر لمفضّلتهم"),
                "الإجمالي": st.column_config.ProgressColumn(
                    "الإجمالي", format="%d", min_value=0, max_value=_maxtot),
            },
        )
        st.download_button("📥 تحميل CSV", view.to_csv(index=False).encode("utf-8-sig"),
                           f"stores_decision_{d_start}_{d_end}.csv", "text/csv")

        # تفصيل لكل مصدر (يظهر في وضع «الكل») — نسخ/نقر لكل متجر × مصدر
        if src_choice == "الكل" and not df_logs.empty:
            with st.expander("📱🌐🔹 تفصيل النسخ والنقر لكل متجر حسب المصدر"):
                brk = (df_logs[df_logs["action_type"].isin(["copy_coupon", "click_link"])]
                       .assign(chan=lambda d: d["source"].map(CHAN_MAP).fillna("أخرى"),
                               نوع=lambda d: d["action_type"].map({"copy_coupon": "نسخ", "click_link": "نقر"}))
                       .groupby(["store_id", "chan", "نوع"]).size().reset_index(name="ع"))
                if brk.empty:
                    st.info("لا توجد نسخ/نقر ضمن الفترة.")
                else:
                    pb = brk.pivot_table(index="store_id", columns=["chan", "نوع"],
                                         values="ع", fill_value=0)
                    pb.columns = [f"{a} {b}" for a, b in pb.columns]
                    pb = pb.reset_index().rename(columns={"store_id": "المتجر"})
                    st.dataframe(pb, hide_index=True, width='stretch')
                    st.caption("النسخ والنقر مفصولة لكل مصدر (بوت/ويب/ميني-ويب). "
                               "تظهر أرقام الميني-ويب بعد نشره واستخدامه فعلياً.")

        st.divider()
        cc1, cc2 = st.columns(2)
        with cc1:
            promote = agg[agg["التوصية"].str.contains("رشّح للترند")]
            st.markdown("**🔥 رشّحهم للترند:**")
            st.write("، ".join(promote["store_id"].tolist()) or "—")
        with cc2:
            drop = agg[agg["التوصية"].str.contains("اسحب الترند|الإيقاف|قلّل")]
            st.markdown("**⬇️ راجعهم (اسحب ترند / أوقف / قلّل تركيز):**")
            st.write("، ".join(drop["store_id"].tolist()) or "—")

    # ─────────────────────────── مين نسخ ───────────────────────────
    elif _sm_tab == _SM_TABS[1]:
        st.caption("الافتراضي: كل المتاجر دفعة وحدة. اختر متجراً محدداً لو تبي تركّز عليه.")
        _ALL_STORES = "— الكل (جميع المتاجر) —"
        store_opts = [_ALL_STORES] + agg.sort_values("نسخ", ascending=False)["store_id"].tolist()
        sel = st.selectbox("المتجر:", store_opts, key="sm_who_store")

        if sel == _ALL_STORES:
            sdf = df_scope
        else:
            sdf = df_scope[df_scope["store_id"] == sel] if not df_scope.empty else df_scope
        scopy = sdf[sdf["action_type"] == "copy_coupon"] if not sdf.empty else sdf
        sclick = sdf[sdf["action_type"] == "click_link"] if not sdf.empty else sdf

        m1, m2, m3 = st.columns(3)
        with m1: kpi_card("🎟️", "إجمالي النسخ", f"{len(scopy):,}", "emerald")
        with m2: kpi_card("👤", "ناسخون مختلفون",
                          f"{scopy['identity'].nunique() if not scopy.empty else 0:,}", "info")
        if sel == _ALL_STORES:
            with m3: kpi_card("🏪", "متاجر منسوخ منها",
                              f"{scopy['store_id'].nunique() if not scopy.empty else 0:,}", "warning")
        else:
            with m3: kpi_card("🖱️", "النقرات", f"{len(sclick):,}", "warning")

        # ── المفضِّلون لهذا النطاق (kind='store') — يظهرون حتى لو لم ينسخوا ──
        def _cln(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        try:
            _fw = _sa_load_favorites()
        except Exception:
            _fw = pd.DataFrame()
        if not _fw.empty and "kind" in _fw.columns:
            _fw = _fw[_fw["kind"] == "store"].copy()
            # فلتر المصدر: «📱 بوت» يعرض مفضّلي البوت فقط، إلخ (الكل = الجميع)
            _PLAT_F = {"📱 بوت": ["bot"], "🌐 ويب": ["web"], "🔹 بوت - ميني": ["miniapp"]}
            if src_choice in _PLAT_F:
                _fw = _fw[_fw["platform"].isin(_PLAT_F[src_choice])]
            if sel != _ALL_STORES:
                _fw = _fw[_fw["store_id"] == sel]
        else:
            _fw = pd.DataFrame()

        _CHAN_FAV = {"bot": "📱 بوت", "web": "🌐 ويب",
                     "miniapp": "🔹 بوت - ميني", "telegram_miniapp": "🔹 بوت - ميني"}

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

        _fav_rows = []
        if not _fw.empty:
            for _, _fr in _fw.iterrows():
                _id = _fav_ident(_fr)
                if _id is None or pd.isna(_fr.get("store_id")):
                    continue
                _fav_rows.append({"identity": _id, "store_id": _fr["store_id"],
                                  "fav_src": _CHAN_FAV.get(_fr.get("platform"), _fr.get("platform"))})
        _fav_df = pd.DataFrame(_fav_rows)
        _fav_set = (set(zip(_fav_df["identity"], _fav_df["store_id"]))
                    if not _fav_df.empty else set())

        if scopy.empty and _fav_df.empty:
            st.info("لا توجد نسخات ولا مفضّلات ضمن الفترة/المصدر.")
        else:
            _group_keys = ["identity", "store_id"] if sel == _ALL_STORES else ["identity"]
            # عدّاد نسخ/نقر/بحث + كل أحداث التفاعل لكل (مستخدم[+متجر])
            events = (sdf[sdf["action_type"].isin(["copy_coupon", "click_link", "search"])]
                      if not sdf.empty else sdf)
            if not events.empty:
                counts = (events.groupby(_group_keys + ["action_type"])
                                .size().unstack(fill_value=0).reset_index())
            else:
                counts = pd.DataFrame(columns=list(_group_keys))
            for c in ("copy_coupon", "click_link", "search"):
                if c not in counts.columns:
                    counts[c] = 0
            # المصدر + أول/آخر تفاعل من **كل** أحداث الشخص على المتجر (نقر/بحث/نسخ)
            # — لا النسخ فقط — حتى لا يطلع «None»/«—» لمن نقر أو بحث بلا نسخ.
            if not events.empty:
                meta = (events.groupby(_group_keys).agg(
                            src=("src_ar", lambda s: "، ".join(sorted(set(s)))),
                            first=("action_time", "min"),
                            last=("action_time", "max"),
                        ).reset_index())
                who = counts.merge(meta, on=_group_keys, how="left")
            else:
                who = counts.copy()
                who["src"] = pd.NA
                who["first"] = pd.NaT
                who["last"] = pd.NaT

            # نُبقي: من نسخ (copy>0) أو من فضّل المتجر — نُقصي بقية الزوّار
            if not who.empty:
                def _keep(r):
                    _sid = r["store_id"] if sel == _ALL_STORES else sel
                    return (r["copy_coupon"] > 0) or ((r["identity"], _sid) in _fav_set)
                who = who[who.apply(_keep, axis=1)].copy()

            # أضف صفوف المفضِّلين الذين لا حدث (نسخ/نقر/بحث) لهم إطلاقاً (مفضّل فقط)
            if not _fav_df.empty:
                if sel == _ALL_STORES:
                    _present = (set(zip(who["identity"], who["store_id"]))
                                if not who.empty else set())
                    _mask = [((i, s) not in _present)
                             for i, s in zip(_fav_df["identity"], _fav_df["store_id"])]
                else:
                    _present = set(who["identity"]) if not who.empty else set()
                    _mask = [(i not in _present) for i in _fav_df["identity"]]
                _miss = _fav_df[_mask]
                if not _miss.empty:
                    _addcols = {
                        "identity": _miss["identity"].values,
                        "copy_coupon": 0, "click_link": 0, "search": 0,
                        "src": _miss["fav_src"].values,
                        "first": pd.NaT, "last": pd.NaT,
                    }
                    if sel == _ALL_STORES:
                        _addcols["store_id"] = _miss["store_id"].values
                    who = pd.concat([who, pd.DataFrame(_addcols)], ignore_index=True)

            # ── ملف تعريف الشخص: إيميل/جوال/تيليجرام/مدينة التسجيل لكل identity ──
            def _first_ne(series):
                if series is None:
                    return ""
                for v in series:
                    s = _cln(v)
                    if s:
                        return s
                return ""

            _profile = {}   # identity -> {email, phone, tg, city}
            if not df_logs.empty and "identity" in df_logs.columns:
                for _ident, _grp in df_logs.groupby("identity"):
                    _tg = _first_ne(_grp.get("web_tg")) or _first_ne(_grp.get("bu_username"))
                    _profile[_ident] = {
                        "email": _first_ne(_grp.get("web_email")),
                        "phone": _first_ne(_grp.get("web_phone")),
                        "tg":    _tg,
                        "city":  _first_ne(_grp.get("web_city")) or _first_ne(_grp.get("bu_city")),
                    }
            if not _fw.empty:
                for _, _fr in _fw.iterrows():
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

            # المدينة: من IP (نقر /go) إن توفّر، وإلا من مدينة التسجيل
            _geo = df_logs[df_logs["city_c"] != "غير معروف"]
            _cmap = ({} if _geo.empty else
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
                who["المدينة"] = who["identity"].map(_city_of)
                who["الإيميل"] = who["identity"].map(lambda i: _profile.get(i, {}).get("email") or "—")
                who["الجوال"] = who["identity"].map(lambda i: _profile.get(i, {}).get("phone") or "—")
                who["تيليجرام"] = who["identity"].map(_tg_of)
            else:
                for _c in ("المدينة", "الإيميل", "الجوال", "تيليجرام"):
                    who[_c] = pd.Series(dtype="object")

            def _who_fav(r):
                _sid = r["store_id"] if sel == _ALL_STORES else sel
                return f"❤️ {_sid}" if (r["identity"], _sid) in _fav_set else "—"
            who["❤️ المفضلة"] = (who.apply(_who_fav, axis=1)
                                 if not who.empty else pd.Series(dtype="object"))

            who = who.rename(columns={"identity": "المستخدم", "store_id": "المتجر",
                                      "copy_coupon": "نسخ", "click_link": "نقر",
                                      "search": "بحث",
                                      "src": "المصدر", "first": "أول تفاعل", "last": "آخر تفاعل"})
            who = who.sort_values("نسخ", ascending=False)
            who["أول تفاعل"] = pd.to_datetime(who["أول تفاعل"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            who["آخر تفاعل"] = pd.to_datetime(who["آخر تفاعل"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            who[["أول تفاعل", "آخر تفاعل"]] = who[["أول تفاعل", "آخر تفاعل"]].fillna("—")
            who["المصدر"] = who["المصدر"].fillna("—")
            _cols = (["المستخدم", "الإيميل", "الجوال", "تيليجرام", "المدينة",
                      "المتجر", "المصدر", "نسخ", "نقر", "بحث",
                      "❤️ المفضلة", "أول تفاعل", "آخر تفاعل"]
                     if sel == _ALL_STORES else
                     ["المستخدم", "الإيميل", "الجوال", "تيليجرام", "المدينة",
                      "المصدر", "نسخ", "نقر", "بحث",
                      "❤️ المفضلة", "أول تفاعل", "آخر تفاعل"])
            st.dataframe(who[_cols], hide_index=True, width='stretch')
            _fname = "all" if sel == _ALL_STORES else sel
            st.download_button("📥 تحميل القائمة (CSV)",
                               who.to_csv(index=False).encode("utf-8-sig"),
                               f"interactions_{_fname}_{d_start}_{d_end}.csv", "text/csv")
            st.caption("يشمل **من نسخ** و**من فضّل** المتجر · «المصدر» و«التفاعل» من كل أحداث الشخص "
                       "(نقر/بحث/نسخ). مفضّل بلا أي تفاعل آخر = «—» في التاريخ. «المدينة» من IP نقر /go.")

    # ─────────────────────────── الرسوم والمعدلات ───────────────────────────
    elif _sm_tab == _SM_TABS[2]:
        st.markdown("**🎟️ النسخ لكل متجر (أعلى 20)**")
        topn = agg[agg["نسخ"] > 0].sort_values("نسخ", ascending=False).head(20)
        if topn.empty:
            st.info("لا توجد نسخ ضمن الفلتر الحالي.")
        else:
            fig1 = px.bar(topn, x="نسخ", y="store_id", orientation="h",
                          color="نسخ", color_continuous_scale="Greens")
            fig1.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="عدد النسخ", yaxis_title="")
            st.plotly_chart(apply_brand_theme(fig1), width='stretch')

        st.markdown("**🔍 أعلى المتاجر بحثاً (أعلى 20)**")
        tops = agg[agg["بحث"] > 0].sort_values("بحث", ascending=False).head(20)
        if tops.empty:
            st.info("لا توجد عمليات بحث ضمن الفلتر الحالي.")
        else:
            fig_s = px.bar(tops, x="بحث", y="store_id", orientation="h",
                           color="بحث", color_continuous_scale="Blues")
            fig_s.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="عدد عمليات البحث", yaxis_title="")
            st.plotly_chart(apply_brand_theme(fig_s), width='stretch')

        st.markdown("**📱🌐🔹 النسخ والنقرات حسب المصدر**")
        if not df_scope.empty:
            bys = (df_scope[df_scope["action_type"].isin(["copy_coupon", "click_link"])]
                   .assign(نوع=lambda d: d["action_type"].map({"copy_coupon": "نسخ", "click_link": "نقرات"}))
                   .groupby(["src_ar", "نوع"]).size().reset_index(name="العدد"))
            if not bys.empty:
                fig2 = px.bar(bys, x="نوع", y="العدد", color="src_ar", barmode="group")
                fig2.update_layout(xaxis_title="", yaxis_title="العدد", legend_title_text="المصدر")
                st.plotly_chart(apply_brand_theme(fig2), width='stretch')
            else:
                st.info("لا توجد نسخ/نقر ضمن الفلتر.")
        else:
            st.info("لا توجد أحداث ضمن الفلتر.")

        st.divider()
        st.markdown("**📈 معدل النشاط عبر الزمن** — نسخ + نقرات + بحث")
        gcol1, gcol2 = st.columns([1.6, 3])
        with gcol1:
            gran = st.radio("الحبيبة:", ["دقيقة", "ساعة", "يوم"], index=2,
                            horizontal=True, key="sm_gran")
            store_pick = st.selectbox("المتجر (الكل = إجمالي):",
                                      ["— الكل —"] + agg["store_id"].tolist(), key="sm_ts_store")
        rule = {"دقيقة": "min", "ساعة": "h", "يوم": "D"}[gran]
        base = df_scope if store_pick == "— الكل —" else (
            df_scope[df_scope["store_id"] == store_pick] if not df_scope.empty else df_scope)
        if not base.empty:
            ev_src = (base[base["action_type"].isin(["copy_coupon", "click_link"])]
                      .assign(نوع=lambda d: d["action_type"].map({"copy_coupon": "نسخ", "click_link": "نقرات"})))
        else:
            ev_src = base
        if ev_src is None or ev_src.empty:
            ev_ts = pd.DataFrame(columns=["نوع", "action_time", "العدد"])
        else:
            ev_ts = (ev_src.set_index("action_time").groupby("نوع").resample(rule).size()
                     .reset_index(name="العدد"))
        if df_search_scope is not None and not df_search_scope.empty:
            sb = df_search_scope if store_pick == "— الكل —" else df_search_scope[df_search_scope["store_id"] == store_pick]
            if not sb.empty:
                sb_ts = sb.set_index("search_date").resample(rule).size().reset_index(name="العدد")
                sb_ts["نوع"] = "بحث"
                sb_ts = sb_ts.rename(columns={"search_date": "action_time"})
                ev_ts = pd.concat([ev_ts, sb_ts[["نوع", "action_time", "العدد"]]], ignore_index=True)
        if ev_ts.empty:
            st.info("لا توجد بيانات للرسم ضمن الفلتر.")
        else:
            figts = px.line(ev_ts, x="action_time", y="العدد", color="نوع", markers=(gran != "دقيقة"))
            figts.update_layout(xaxis_title=f"الزمن ({gran} · توقيت الرياض)",
                                yaxis_title="العدد", legend_title_text="")
            st.plotly_chart(apply_brand_theme(figts), width='stretch')
            st.caption("«دقيقة» لرصد دفعات النشاط اللحظية · «يوم» لرؤية الاتجاه العام.")

    # ─────────────────────────── ❤️ المفضلة ───────────────────────────
    elif _sm_tab == _SM_TABS[3]:
        st.caption("من جدول `user_favorites` الموحّد (بوت + ميني-ويب + ويب). كل شخص يُحتسب "
                   "مرة واحدة لكل متجر · أساس للتنبيهات المستقبلية (حقل last_notified_at جاهز).")
        try:
            df_fav = _sa_load_favorites()
        except Exception as e:
            st.error(f"⚠️ تعذّر تحميل المفضلة: {e}")
            df_fav = pd.DataFrame()

        # تحليل المتاجر يعرض مفضلة المتاجر فقط — نُقصي صفوف الأقسام
        # (موجودة في نفس الجدول بعد migration_028).
        if not df_fav.empty and "kind" in df_fav.columns:
            df_fav = df_fav[df_fav["kind"] == "store"].copy()

        # فلتر المصدر (platform) — يحترم نفس اختيار شريط التحكم أعلى الصفحة
        PLAT_FILTER = {"📱 بوت": ["bot"], "🌐 ويب": ["web"], "🔹 بوت - ميني": ["miniapp"]}
        if src_choice in PLAT_FILTER and not df_fav.empty:
            df_fav = df_fav[df_fav["platform"].isin(PLAT_FILTER[src_choice])].copy()

        if df_fav.empty:
            st.info("📭 لا توجد مفضلات بعد. بمجرد ما يبدأ المستخدمون بإضافة متاجرهم المفضلة ستظهر هنا.")
        else:
            _plat_ar = {"bot": "📱 بوت", "web": "🌐 ويب", "miniapp": "🔹 بوت - ميني"}

            # مفتاح هوية الشخص (ويب أو تيليجرام) لعدّ الأشخاص الفعليين
            def _person_key(r):
                if pd.notna(r.web_user_id):
                    return f"w{int(r.web_user_id)}"
                if pd.notna(r.telegram_id):
                    return f"t{int(r.telegram_id)}"
                return "?"

            total_fav    = len(df_fav)
            uniq_stores  = df_fav["store_id"].nunique()
            uniq_people  = df_fav.apply(_person_key, axis=1).nunique()
            k1, k2, k3 = st.columns(3)
            k1.metric("❤️ إجمالي الإضافات", f"{total_fav:,}")
            k2.metric("🏪 متاجر مفضّلة",     f"{uniq_stores:,}")
            k3.metric("👤 أشخاص فعّالون",    f"{uniq_people:,}")

            # ── لوحة أكثر المتاجر تفضيلاً ──
            st.markdown("**🏆 أكثر المتاجر تفضيلاً (عدد الأشخاص)**")
            board_f = (df_fav.groupby("store_id").size()
                       .reset_index(name="عدد الأشخاص")
                       .sort_values("عدد الأشخاص", ascending=False))
            board_f = board_f.merge(df_master[["store_id", "logo_url"]], on="store_id", how="left")
            view_f = pd.DataFrame({
                "الشعار": board_f["logo_url"].fillna("").values,
                "المتجر": board_f["store_id"].values,
                "عدد الأشخاص": board_f["عدد الأشخاص"].values,
            })
            _maxp = int(max(1, board_f["عدد الأشخاص"].max()))
            st.dataframe(
                view_f, hide_index=True, width='stretch',
                column_config={
                    "الشعار": st.column_config.ImageColumn("🏪", width="small"),
                    "عدد الأشخاص": st.column_config.ProgressColumn(
                        "عدد الأشخاص", format="%d", min_value=0, max_value=_maxp),
                },
            )
            st.download_button("📥 تحميل CSV", view_f.to_csv(index=False).encode("utf-8-sig"),
                               "favorites_leaderboard.csv", "text/csv", key="fav_csv")

            # ── التوزيع حسب المنصة ──
            if src_choice == "الكل":
                st.markdown("**📊 التوزيع حسب المنصة**")
                dist_f = (df_fav.assign(منصة=lambda d: d["platform"].map(_plat_ar).fillna(d["platform"]))
                          .groupby("منصة").size().reset_index(name="العدد"))
                fig_fp = px.pie(dist_f, names="منصة", values="العدد", hole=0.45)
                st.plotly_chart(apply_brand_theme(fig_fp), width='stretch')

            # ── من فضّل متجراً معيّناً؟ (الأساس لإرسال التنبيهات) ──
            st.divider()
            st.markdown("**🔍 مين فضّل متجراً معيّناً؟**")
            store_sel = st.selectbox("اختر متجراً:", board_f["store_id"].tolist(), key="fav_store_sel")
            sub_f = df_fav[df_fav["store_id"] == store_sel].copy()

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

            _ca = (pd.to_datetime(sub_f["created_at"], utc=True, errors="coerce")
                   + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
            out_f = pd.DataFrame({
                "الشخص": sub_f.apply(_fav_who, axis=1).values,
                "المدينة": sub_f.apply(_fav_city, axis=1).values,
                "المنصة": sub_f["platform"].map(_plat_ar).fillna(sub_f["platform"]).values,
                "تاريخ الإضافة": _ca.dt.strftime("%Y-%m-%d %H:%M").values,
            })
            st.dataframe(out_f, hide_index=True, width='stretch')
            st.caption(f"👥 {len(out_f)} شخص فضّلوا «{store_sel}» — هؤلاء جمهور التنبيه المستقبلي "
                       "عند نزول كوبون/خصم جديد لهذا المتجر.")

    # ════════════════════════════════════════════════════════════════════════
    # 🔥 الترند — نقاط موزونة + قاعدة Anti-Spam + تبويبات داخلية للمصدر
    #    اليومي = من 12 ليلاً → الآن (يبدأ من صفر كل ليلة)
    #    الأسبوعي = آخر 7 أيام rolling (يتحرّك ثانية بثانية)
    #    ⚠️ يتجاوز فلتر التاريخ في أعلى الصفحة — الترند له نوافذه الخاصة.
    # ════════════════════════════════════════════════════════════════════════
    elif _sm_tab == _SM_TABS[4]:
        # ── شريط الحداثة + إعادة التحميل اليدوي ─────────────────────
        _now_ts = pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS)
        c_info, c_btn = st.columns([4, 1])
        with c_info:
            st.caption(f"⏱️ آخر تحديث: **{_now_ts.strftime('%H:%M:%S')}** · "
                       f"الكاش يُجدَّد تلقائياً كل 60 ثانية · للتحديث الفوري اضغط زرّ التحديث.")
        with c_btn:
            if st.button("🔄 تحديث الآن", width='stretch', key="trend_refresh"):
                _sa_load_actions.clear()
                _sa_load_favorites.clear()
                _sa_load_master.clear()
                st.rerun()
        st.caption("نقاط موزونة: نقر=1 · بحث=2 · نسخ=3 · مفضلة=4 — مع قاعدة anti-spam "
                   "تمنع تضخيم الترند بالتكرار. الشرح الكامل أسفل الصفحة.")

        # ════════════════════════════════════════════════════════════════════
        # 🎛️ التحكم اليدوي بمراكز الترند (Admin Override / Pin)
        #   يثبّت متجراً معيناً في مركز محدد. الباقي يتزحّح طبيعياً.
        #   يُكتب في trend_overrides → الـ API يقرأه ويطبّقه قبل العرض للزوار.
        # ════════════════════════════════════════════════════════════════════
        with st.expander("🎛️ التحكم اليدوي بمراكز الترند (Admin Pin)", expanded=False):
            st.caption(
                "ثبّت متجراً في مركز محدد — الباقي يتزحّح تلقائياً. "
                "مثال: تثبيت متجر «نمشي 3» في المركز الثاني للأسبوعي يدفع المتجر "
                "اللي كان فيه إلى المركز الثالث، والثالث للرابع، وهكذا. "
                "**ملاحظة**: التغييرات تظهر للزوار على الموقع والميني-ويب خلال **دقيقة** (كاش API)."
            )

            # ── تحميل المتاجر المتوفرة + التجاوزات الحالية ─────────────
            try:
                _ov_conn = get_conn()
                _ov_conn.rollback()
                # نضمن وجود الجدول قبل القراءة (للأنظمة قبل migration 030).
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
                    _ov_conn,
                )
            except Exception as _e:
                st.error(f"⚠️ تعذّر قراءة التجاوزات: {_e}")
                _df_ov = pd.DataFrame(columns=["window", "rank", "store_id"])
            finally:
                try: _ov_conn.close()
                except Exception: pass

            _ov_daily = dict(zip(
                _df_ov[_df_ov["window"] == "daily"]["rank"].astype(int),
                _df_ov[_df_ov["window"] == "daily"]["store_id"],
            )) if not _df_ov.empty else {}
            _ov_weekly = dict(zip(
                _df_ov[_df_ov["window"] == "weekly"]["rank"].astype(int),
                _df_ov[_df_ov["window"] == "weekly"]["store_id"],
            )) if not _df_ov.empty else {}

            # ── قائمة المتاجر المتوفرة (نشطة + غير منتهية) ─────────────
            _store_options = sorted(df_master["store_id"].dropna().astype(str).unique().tolist())
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

            def _pinned_picker(window: str, rank: int, label: str, current: str | None):
                """selectbox واحد لمركز محدد. يُرجع store_id أو None لو تلقائي."""
                idx = (_option_list.index(current)
                       if current in _option_list else 0)
                pick = st.selectbox(label, _option_list, index=idx,
                                     key=f"pin_{window}_{rank}")
                return None if pick == _AUTO else pick

            # ── الترند اليومي (3 مراكز) ─────────────────────────────────
            st.markdown("##### 🌞 الترند اليومي (3 مراكز)")
            _daily_picks: dict[int, str | None] = {}
            for _rk, _lbl in _DAILY_TITLES.items():
                _daily_picks[_rk] = _pinned_picker(
                    "daily", _rk, _lbl, _ov_daily.get(_rk),
                )

            st.markdown("##### 📅 الترند الأسبوعي (7 مراكز)")
            _weekly_picks: dict[int, str | None] = {}
            _w_cols = st.columns(2)
            for _i, (_rk, _lbl) in enumerate(_WEEKLY_TITLES.items()):
                with _w_cols[_i % 2]:
                    _weekly_picks[_rk] = _pinned_picker(
                        "weekly", _rk, _lbl, _ov_weekly.get(_rk),
                    )

            # ── حفظ + تنبيه على التكرار داخل نفس النافذة ───────────────
            _b_save, _b_clear = st.columns([1, 1])
            with _b_save:
                _save_clicked = st.button("💾 حفظ التجاوزات", width='stretch',
                                            key="trend_pin_save", type="primary")
            with _b_clear:
                _clear_clicked = st.button("🧹 مسح كل التجاوزات", width='stretch',
                                            key="trend_pin_clear")

            if _save_clicked:
                # تحقق: نفس المتجر مو مكرّر في مركزين بنفس النافذة
                def _dup_in(picks: dict[int, str | None]) -> str | None:
                    seen = {}
                    for rk, sid in picks.items():
                        if sid and sid in seen:
                            return f"المتجر «{sid}» مكرّر في مركزين ({seen[sid]} و {rk})"
                        if sid:
                            seen[sid] = rk
                    return None

                err = _dup_in(_daily_picks) or _dup_in(_weekly_picks)
                if err:
                    st.error(f"⚠️ {err}. عدّل وأعد الحفظ.")
                else:
                    try:
                        _sv_conn = get_conn()
                        with _sv_conn.cursor() as _cur:
                            _cur.execute("DELETE FROM trend_overrides")
                            _rows = []
                            for rk, sid in _daily_picks.items():
                                if sid:
                                    _rows.append(("daily", rk, sid))
                            for rk, sid in _weekly_picks.items():
                                if sid:
                                    _rows.append(("weekly", rk, sid))
                            if _rows:
                                _cur.executemany(
                                    "INSERT INTO trend_overrides (window_kind, rank, store_id) "
                                    "VALUES (%s, %s, %s)",
                                    _rows,
                                )
                            _sv_conn.commit()
                        st.success(f"✅ تم حفظ {len(_rows)} تجاوز. ستظهر للزوار خلال دقيقة.")
                    except Exception as _e:
                        st.error(f"⚠️ فشل الحفظ: {_e}")
                    finally:
                        try: _sv_conn.close()
                        except Exception: pass
                    st.rerun()

            if _clear_clicked:
                try:
                    _cl_conn = get_conn()
                    with _cl_conn.cursor() as _cur:
                        _cur.execute("DELETE FROM trend_overrides")
                        _cl_conn.commit()
                    st.success("✅ تم مسح كل التجاوزات. الترند رجع للخوارزمية فقط.")
                except Exception as _e:
                    st.error(f"⚠️ فشل المسح: {_e}")
                finally:
                    try: _cl_conn.close()
                    except Exception: pass
                st.rerun()

            # ── جدول التجاوزات الحالية (سهل القراءة) ──────────────────
            if not _df_ov.empty:
                _show = _df_ov.copy()
                _show["window"] = _show["window"].map({"daily": "🌞 يومي",
                                                         "weekly": "📅 أسبوعي"})
                _show = _show.rename(columns={"window": "النافذة",
                                                "rank": "المركز",
                                                "store_id": "المتجر"})
                st.markdown("**📋 التجاوزات الحالية:**")
                st.dataframe(_show, hide_index=True, width='stretch')

        tr_tab_all, tr_tab_bot, tr_tab_web, tr_tab_mini = st.tabs([
            "📡 الكل", "📱 البوت", "🌐 الموقع", "🔹 الميني-ويب",
        ])

        _TREND_SRC_MAP = {
            "all": None,
            "bot": ["bot"],
            "web": ["web"],
            "mini": ["telegram_miniapp", "miniapp"],
        }
        _TREND_FAV_PLAT_MAP = {"all": None, "bot": ["bot"],
                                "web": ["web"], "mini": ["miniapp"]}

        _LOGO_MAP = df_master.set_index("store_id")["logo_url"].fillna("").to_dict()

        # توقيت الرياض كـ naive (للتطابق مع action_time المُزاح في الصفحة)
        _NOW_R = pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS)
        _TODAY_START = _NOW_R.normalize()
        _WEEK_START = _NOW_R - pd.Timedelta(days=7)

        # ── HTML card renderer ────────────────────────────────────────
        def _trend_card_html(title: str, row, big: bool = True) -> str:
            logo = (row.get("logo_url") or "").strip()
            store = row.get("store_id", "—")
            score = int(row.get("total_score", 0))
            cl = int(row.get("clicks_counted", 0))
            se = int(row.get("searches_counted", 0))
            co = int(row.get("copies_counted", 0))
            fv = int(row.get("favs_added", 0))
            uu = int(row.get("unique_users", 0))
            sz = 72 if big else 52
            fs_score = "30px" if big else "20px"
            fs_name = "17px" if big else "14px"
            min_h = "230px" if big else "190px"
            if logo:
                logo_html = (f'<img src="{logo}" style="width:{sz}px;height:{sz}px;'
                             f'object-fit:contain;border-radius:10px;background:{BRAND["surface"]};'
                             f'padding:4px;border:1px solid {BRAND["border"]};'
                             f'margin:6px auto;display:block">')
            else:
                logo_html = (f'<div style="width:{sz}px;height:{sz}px;border-radius:10px;'
                             f'background:{BRAND["bg_alt"]};margin:6px auto;display:flex;'
                             f'align-items:center;justify-content:center;font-size:24px;'
                             f'border:1px solid {BRAND["border"]}">🏪</div>')
            return f"""
<div style="border:1px solid {BRAND["border"]};border-radius:14px;padding:14px;
            text-align:center;background:{BRAND["surface"]};
            box-shadow:0 1px 3px rgba(0,0,0,0.05);min-height:{min_h}">
  <div style="font-size:13px;color:{BRAND["emerald_deep"]};font-weight:700;margin-bottom:2px">
    {title}
  </div>
  {logo_html}
  <div style="font-size:{fs_name};font-weight:700;color:{BRAND["text"]};margin:4px 0">
    {store}
  </div>
  <div style="font-size:{fs_score};color:{BRAND["emerald_deep"]};font-weight:800;line-height:1.1">
    {score}
  </div>
  <div style="font-size:10px;color:{BRAND["text_muted"]};margin-bottom:6px">نقطة</div>
  <div style="font-size:11px;color:{BRAND["text_soft"]};line-height:1.6">
    🔗 {cl} · 🔍 {se} · 📋 {co}<br>❤️ {fv} · 👤 {uu}
  </div>
</div>
"""

        def _empty_card_html(title: str) -> str:
            return f"""
<div style="border:1px dashed {BRAND["border"]};border-radius:14px;padding:20px;
            text-align:center;background:{BRAND["bg_alt"]};min-height:230px;
            display:flex;flex-direction:column;justify-content:center">
  <div style="font-size:13px;color:{BRAND["text_muted"]};font-weight:700;margin-bottom:8px">
    {title}
  </div>
  <div style="font-size:32px;opacity:0.4">—</div>
  <div style="font-size:11px;color:{BRAND["text_muted"]};margin-top:8px">
    لا توجد بيانات كافية
  </div>
</div>
"""

        def _render_detail_table(df_sec: pd.DataFrame, key_prefix: str, top_n: int) -> None:
            v = df_sec.head(top_n).copy()
            view = pd.DataFrame({
                "#": v["rank"].values,
                "الشعار": v["store_id"].map(_LOGO_MAP).fillna("").values,
                "المتجر": v["store_id"].values,
                "🔗 نقر": v["clicks_counted"].values,
                "🔍 بحث": v["searches_counted"].values,
                "📋 نسخ": v["copies_counted"].values,
                "❤️ مفضلة": v["favs_added"].values,
                "👤 أشخاص": v["unique_users"].values,
                "النقاط": v["total_score"].values,
            })
            max_score = int(max(1, view["النقاط"].max())) if len(view) else 1
            st.dataframe(
                view, hide_index=True, width='stretch',
                column_config={
                    "الشعار": st.column_config.ImageColumn("🏪", width="small"),
                    "النقاط": st.column_config.ProgressColumn(
                        "النقاط", format="%d", min_value=0, max_value=max_score),
                },
                key=f"{key_prefix}_table",
            )
            st.download_button(
                "📥 تحميل CSV",
                view.to_csv(index=False).encode("utf-8-sig"),
                f"trend_{key_prefix}.csv", "text/csv", key=f"{key_prefix}_csv",
            )

        # ── Drilldown: مين دفع متجراً معيّناً في الترند؟ ─────────────
        def _render_drilldown(d_full_marked: pd.DataFrame,
                              daily_df: pd.DataFrame, weekly_df: pd.DataFrame,
                              key_prefix: str) -> None:
            st.markdown("**🔍 مين دفع متجراً معيّناً في الترند؟**")
            stores_pool = []
            if not daily_df.empty: stores_pool.extend(daily_df["store_id"].tolist())
            if not weekly_df.empty: stores_pool.extend(weekly_df["store_id"].tolist())
            stores_pool = list(dict.fromkeys(stores_pool))  # uniq preserving order
            if not stores_pool:
                st.info("لا يوجد متجر في الترند حالياً.")
                return
            cdd1, cdd2 = st.columns([2, 3])
            with cdd1:
                store_sel = st.selectbox("اختر متجراً:", stores_pool,
                                          key=f"{key_prefix}_dd_store")
            with cdd2:
                scope = st.radio("النطاق:",
                                  ["📅 الأسبوعي (آخر 7 أيام)", "🌞 اليومي (منذ 12 ليلاً)"],
                                  horizontal=True, key=f"{key_prefix}_dd_scope")
            wstart = _WEEK_START if "أسبوعي" in scope else _TODAY_START

            d = d_full_marked[
                (d_full_marked["store_id"] == store_sel)
                & (d_full_marked["action_time"] >= wstart)
                & (d_full_marked["action_time"] <= _NOW_R)
                & (d_full_marked["counted"])
            ].copy()
            if d.empty:
                st.info("لا أحداث محسوبة (counted=True) لهذا المتجر في النطاق المحدد. "
                        "ربما كل أحداثه ضمن فترة التبريد 5 ساعات.")
                return

            CHAN_AR = {"bot": "📱 بوت", "web": "🌐 ويب",
                       "telegram_miniapp": "🔹 ميني-ويب", "miniapp": "🔹 ميني-ويب"}
            POINTS_MAP = {"click_link": 1, "search": 2, "copy_coupon": 3}

            def _ident(r):
                src = r["source"]
                if src in ("telegram_miniapp", "miniapp"):
                    u = (r.get("bu_username") or "")
                    if isinstance(u, str) and u.strip():
                        return "@" + u.strip().lstrip("@")
                    if pd.notna(r.get("user_id")):
                        return f"🔹 ميني #{int(r['user_id'])}"
                    return f"🔹 ميني #{(r.get('ip_hex') or '')[:6]}"
                if src == "web":
                    for k in ("web_name", "web_email"):
                        v = r.get(k)
                        if v is not None and not (isinstance(v, float) and pd.isna(v)):
                            s = str(v).strip()
                            if s: return s
                    return f"🌐 زائر #{(r.get('ip_hex') or '')[:6]}"
                u = (r.get("bu_username") or "")
                if isinstance(u, str) and u.strip():
                    return "@" + u.strip().lstrip("@")
                if pd.notna(r.get("user_id")):
                    return f"📱 بوت #{int(r['user_id'])}"
                return "📱 بوت (غير مسجّل)"

            d["الشخص"] = d.apply(_ident, axis=1)
            d["القناة"] = d["source"].map(CHAN_AR).fillna(d["source"])
            d["النقاط"] = d["action_type"].map(POINTS_MAP).fillna(0).astype(int)

            piv = d.pivot_table(index=["الشخص", "القناة"], columns="action_type",
                                 values="النقاط", aggfunc="count", fill_value=0)
            for c in ["click_link", "search", "copy_coupon"]:
                if c not in piv.columns: piv[c] = 0
            piv = piv.rename(columns={"click_link": "🔗 نقر",
                                      "search": "🔍 بحث",
                                      "copy_coupon": "📋 نسخ"})
            piv["النقاط"] = (piv["🔗 نقر"] * 1 + piv["🔍 بحث"] * 2 + piv["📋 نسخ"] * 3)
            piv = piv.reset_index().sort_values("النقاط", ascending=False).head(20)
            st.dataframe(piv, hide_index=True, width='stretch',
                          key=f"{key_prefix}_dd_table")
            st.caption(f"أعلى 20 شخصاً ساهموا في ترند «{store_sel}» (counted فقط). "
                        f"ملاحظة: المفضلة تُحسب من جدول `user_favorites` ولا تظهر هنا.")

        # ── Main per-source render ───────────────────────────────────
        def _render_trend_for_source(src_key: str) -> None:
            src_filter = _TREND_SRC_MAP[src_key]
            fav_filter = _TREND_FAV_PLAT_MAP[src_key]

            # Fresh load — يتجاوز فلتر التاريخ في أعلى الصفحة
            df_logs_full = _sa_load_actions()
            df_fav_full = _sa_load_favorites()

            if not df_logs_full.empty:
                df_logs_full = df_logs_full[df_logs_full["store_id"].isin(active_ids)].copy()
                df_logs_full["action_time"] = (pd.to_datetime(df_logs_full["action_time"])
                                                + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
                if src_filter:
                    df_logs_full = df_logs_full[df_logs_full["source"].isin(src_filter)]

            if not df_fav_full.empty:
                df_fav_full = df_fav_full.copy()
                df_fav_full["created_at"] = (
                    pd.to_datetime(df_fav_full["created_at"], utc=True)
                    .dt.tz_localize(None)
                    + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS)
                )
                if fav_filter:
                    df_fav_full = df_fav_full[df_fav_full["platform"].isin(fav_filter)]

            daily = _sa_compute_trend(df_logs_full, df_fav_full,
                                       _TODAY_START, _NOW_R, active_ids)
            weekly = _sa_compute_trend(df_logs_full, df_fav_full,
                                        _WEEK_START, _NOW_R, active_ids)
            for df_ in (daily, weekly):
                if not df_.empty:
                    df_["logo_url"] = df_["store_id"].map(_LOGO_MAP).fillna("")

            # ── 🌞 اليومي ──────────────────────────────────────────
            hours_in = max(1, int((_NOW_R - _TODAY_START).total_seconds() / 3600))
            st.markdown("### 🌞 الترند اليومي")
            st.caption(f"من 12:00 ص ← الآن · {hours_in} ساعة منقضية · "
                        f"إجمالي متاجر داخل الترند: **{len(daily)}**")

            DAILY_TITLES = ["🥇 الأعلى طلباً", "🥈 الأكثر شعبية", "🥉 الأوسع انتشاراً"]
            cols = st.columns(3)
            for i, (col, ttl) in enumerate(zip(cols, DAILY_TITLES)):
                with col:
                    if i < len(daily):
                        st.markdown(_trend_card_html(ttl, daily.iloc[i], big=True),
                                     unsafe_allow_html=True)
                    else:
                        st.markdown(_empty_card_html(ttl), unsafe_allow_html=True)

            if not daily.empty:
                with st.expander("📊 تفصيل النقاط اليومية (أعلى 15)", expanded=False):
                    _render_detail_table(daily, f"{src_key}_daily", top_n=15)

            st.divider()

            # ── 📅 الأسبوعي ─────────────────────────────────────────
            st.markdown("### 📅 الترند الأسبوعي")
            st.caption(f"آخر 7 أيام (rolling) · من {_WEEK_START.strftime('%Y-%m-%d %H:%M')} "
                        f"← الآن · إجمالي متاجر داخل الترند: **{len(weekly)}**")

            cols = st.columns(3)
            for i, (col, ttl) in enumerate(zip(cols, DAILY_TITLES)):
                with col:
                    if i < len(weekly):
                        st.markdown(_trend_card_html(ttl, weekly.iloc[i], big=True),
                                     unsafe_allow_html=True)
                    else:
                        st.markdown(_empty_card_html(ttl), unsafe_allow_html=True)

            if len(weekly) > 3 or True:  # نُظهر الصف دائماً حتى لو فاضي (تنسيق ثابت)
                st.markdown("**🏅 المراكز التالية:**")
                cols2 = st.columns(4)
                for i in range(4):
                    pos_idx = 3 + i
                    with cols2[i]:
                        ttl = f"المركز {pos_idx + 1}"
                        if pos_idx < len(weekly):
                            st.markdown(_trend_card_html(ttl, weekly.iloc[pos_idx], big=False),
                                         unsafe_allow_html=True)
                        else:
                            st.markdown(_empty_card_html(ttl), unsafe_allow_html=True)

            if not weekly.empty:
                with st.expander("📊 تفصيل النقاط الأسبوعية (أعلى 20)", expanded=False):
                    _render_detail_table(weekly, f"{src_key}_weekly", top_n=20)

            st.divider()

            # ── 🔍 Drilldown (يحتاج counted على كامل الـ logs) ────
            if df_logs_full is not None and not df_logs_full.empty:
                d_full = df_logs_full.copy()
                d_full = d_full[d_full["store_id"].notna()
                                & (d_full["store_id"].astype(str).str.strip() != "")]
                d_full["person_key"] = d_full.apply(
                    lambda r: _sa_person_key(r.get("source"), r.get("user_id"), r.get("ip_hex")),
                    axis=1,
                )
                d_full = _sa_apply_anti_spam(d_full, time_col="action_time")
                _render_drilldown(d_full, daily, weekly, src_key)
            else:
                st.info("لا توجد أحداث في هذا النطاق.")

            # ── ℹ️ شارح القاعدة ───────────────────────────────────
            with st.expander("ℹ️ كيف يُحسب الترند؟ (شرح القاعدة)", expanded=False):
                st.markdown("""
**نظام النقاط الموزون:**

| الفعل | النقاط لكل حدث |
|---|---|
| 🔗 نقر على رابط متجر | **1** |
| 🔍 بحث باسم المتجر | **2** |
| 📋 نسخ كوبون | **3** |
| ❤️ إضافة للمفضلة | **4** *(تنخصم تلقائياً لو أزال المستخدم المفضلة — لأن الصف يُحذف فعلياً من الجدول)* |

**قاعدة Anti-Spam (لكل نوع فعل × مستخدم × متجر بشكل مستقل):**

- ✅ **أول ساعة:** أول فعلَين تُحسب نقاطهما.
- ❌ **من ساعة 1 إلى ساعة 5:** أي فعل إضافي يُسجَّل في النظام بدون نقاط — يعني المستخدم يقدر ينسخ ويفتح وينقر زي ما يبي، بس ما يُضخّم الترند.
- 🔄 **بعد 5 ساعات** من بداية النافذة: نافذة جديدة تفتح بأول فعل قادم.

**النوافذ الزمنية:**

- 🌞 **اليومي:** من 12:00 ص (توقيت الرياض) إلى الآن. يبدأ من صفر كل ليلة.
- 📅 **الأسبوعي:** آخر 7 أيام (rolling) — يتحرك ثانية بثانية مع الوقت.

**ضمانات الفوترة:**

كل الأحداث الخام محفوظة في `action_logs` للأبد بختم زمني. لو طلبت شركة معلنة تقريراً «متى كان متجري في الترند هذا الشهر؟» نقدر نرجع لأي تاريخ ونعيد بناء الترند منه. **ما في تصفير أبداً** — الترند هو فقط *سؤال* نسأله للداتا الخام.
                """)

        with tr_tab_all:
            _render_trend_for_source("all")
        with tr_tab_bot:
            _render_trend_for_source("bot")
        with tr_tab_web:
            _render_trend_for_source("web")
        with tr_tab_mini:
            _render_trend_for_source("mini")


# ════════════════════════════════════════════════════════════════════════════
# 🎬 تحليلات الستوري (Migration 029) — صفحة مستقلة
#    مصدر البيانات: story_views + action_logs.story_view_id
#    تابز: الكل / 🌐 الموقع / 🔹 الميني-ويب
# ════════════════════════════════════════════════════════════════════════════
elif page == "🎬 تحليلات الستوري":
    st.header("🎬 تحليلات الستوري")
    st.caption("كل فتحة، مين فتح، كم مرّة، وعلى أيش دخل من داخل الستوري، ونسخ كود من الستوري أو لا — لاتخاذ قرار: هذا الستوري يستحق الدفع؟")

    sv_tab_all, sv_tab_web, sv_tab_mini = st.tabs(["📡 الكل", "🌐 الموقع", "🔹 الميني-ويب"])

    def _render_story_analytics(source_filter, key_prefix):
        """source_filter=None → كل المصادر، 'web' → الموقع فقط، 'telegram_miniapp' → الميني-ويب."""
        try:
            conn_st = get_conn()
            conn_st.rollback()
            src_where = ""
            params = []
            if source_filter:
                src_where = "WHERE source = %s"
                params = [source_filter]

            kpi = pd.read_sql(f"""
                SELECT
                  COUNT(*)                                          AS total_views,
                  COUNT(DISTINCT view_id)                           AS unique_opens,
                  COUNT(DISTINCT store_id)                          AS stores_seen,
                  COUNT(DISTINCT COALESCE(web_user_id::text,
                                          'tg:' || tg_user_id::text)) AS unique_viewers
                FROM story_views {src_where}
            """, conn_st, params=params)

            eng_filter = ""
            eng_params = []
            if source_filter:
                eng_filter = " AND al.source = %s "
                eng_params = [source_filter]
            eng = pd.read_sql(f"""
                SELECT
                  SUM(CASE WHEN al.action_type='copy_coupon' THEN 1 ELSE 0 END) AS copies,
                  SUM(CASE WHEN al.action_type='click_link'  THEN 1 ELSE 0 END) AS clicks
                FROM action_logs al
                WHERE al.story_view_id IS NOT NULL {eng_filter}
            """, conn_st, params=eng_params)

            total_views    = int(kpi["total_views"].iloc[0]    or 0)
            unique_viewers = int(kpi["unique_viewers"].iloc[0] or 0)
            stores_seen    = int(kpi["stores_seen"].iloc[0]    or 0)
            copies = int(eng["copies"].iloc[0] or 0)
            clicks = int(eng["clicks"].iloc[0] or 0)
            ctr = (clicks * 100.0 / total_views) if total_views else 0.0
            cvr = (copies * 100.0 / total_views) if total_views else 0.0

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: kpi_card("👀", "إجمالي الفتحات",  total_views,    "info")
            with c2: kpi_card("👥", "مشاهدون فريدون", unique_viewers, "emerald")
            with c3: kpi_card("🏬", "متاجر شُوهدت",    stores_seen,    "info")
            with c4: kpi_card("📋", f"نسخ ({cvr:.1f}%)", copies,       "warning")
            with c5: kpi_card("🚪", f"زيارات ({ctr:.1f}%)", clicks,    "emerald")

            st.markdown("---")

            # ─── جدول لكل متجر ─────────────────────────────────────────────
            st.subheader("📊 تفصيل لكل متجر")
            per_store_params = list(params) + list(eng_params)
            per_store = pd.read_sql(f"""
                WITH v AS (
                  SELECT store_id,
                         COUNT(*)                              AS views,
                         COUNT(DISTINCT COALESCE(web_user_id::text,
                                                 'tg:' || tg_user_id::text)) AS uniq_viewers
                  FROM story_views {src_where}
                  GROUP BY store_id
                ),
                e AS (
                  SELECT al.store_id,
                         SUM(CASE WHEN al.action_type='copy_coupon' THEN 1 ELSE 0 END) AS copies,
                         SUM(CASE WHEN al.action_type='click_link'  THEN 1 ELSE 0 END) AS clicks
                  FROM action_logs al
                  WHERE al.story_view_id IS NOT NULL {eng_filter}
                  GROUP BY al.store_id
                )
                SELECT v.store_id,
                       v.views,
                       v.uniq_viewers,
                       COALESCE(e.copies, 0) AS copies,
                       COALESCE(e.clicks, 0) AS clicks,
                       CASE WHEN v.views > 0
                            THEN ROUND((COALESCE(e.clicks,0)*100.0 / v.views)::numeric, 1)
                            ELSE 0 END AS ctr_pct,
                       CASE WHEN v.views > 0
                            THEN ROUND((COALESCE(e.copies,0)*100.0 / v.views)::numeric, 1)
                            ELSE 0 END AS cvr_pct
                FROM v LEFT JOIN e USING (store_id)
                ORDER BY v.views DESC
            """, conn_st, params=per_store_params)

            if per_store.empty:
                st.info("📭 لا توجد بيانات ستوري بعد لهذا المصدر.")
            else:
                per_store.rename(columns={
                    "store_id":     "المتجر",
                    "views":        "الفتحات",
                    "uniq_viewers": "مشاهدون فريدون",
                    "copies":       "نُسخ من الستوري",
                    "clicks":       "زيارات من الستوري",
                    "ctr_pct":      "% زيارة",
                    "cvr_pct":      "% نسخ",
                }, inplace=True)
                st.dataframe(per_store, use_container_width=True, hide_index=True)

            # ─── كل المشاهدين (بياناتهم كاملة) ─────────────────────────────
            st.markdown("---")
            st.subheader("👥 كل المشاهدين — بياناتهم الكاملة")
            st.caption("صف لكل شخص: مين هو، كم مرّة شاف، على أيش دخل، ونسخ كود من الستوري أو لا.")

            all_viewers = pd.read_sql(f"""
                WITH base AS (
                  SELECT sv.web_user_id,
                         sv.tg_user_id,
                         sv.source,
                         sv.store_id,
                         sv.view_id,
                         sv.viewed_at
                  FROM story_views sv
                  {src_where}
                ),
                agg AS (
                  SELECT web_user_id, tg_user_id,
                         MIN(source)                              AS source_any,
                         COUNT(*)                                 AS views,
                         COUNT(DISTINCT store_id)                 AS stores_count,
                         STRING_AGG(DISTINCT store_id, '، ' ORDER BY store_id) AS stores_list,
                         MIN(viewed_at)                           AS first_view,
                         MAX(viewed_at)                           AS last_view,
                         ARRAY_AGG(view_id)                       AS view_ids
                  FROM base
                  GROUP BY web_user_id, tg_user_id
                ),
                acts AS (
                  SELECT
                    a.web_user_id, a.tg_user_id,
                    SUM(CASE WHEN al.action_type='copy_coupon' THEN 1 ELSE 0 END) AS copies,
                    SUM(CASE WHEN al.action_type='click_link'  THEN 1 ELSE 0 END) AS clicks,
                    STRING_AGG(DISTINCT al.store_id, '، ' ORDER BY al.store_id)
                      FILTER (WHERE al.action_type='copy_coupon')                AS copied_stores,
                    STRING_AGG(DISTINCT al.store_id, '، ' ORDER BY al.store_id)
                      FILTER (WHERE al.action_type='click_link')                 AS visited_stores
                  FROM agg a
                  LEFT JOIN action_logs al
                    ON al.story_view_id = ANY(a.view_ids)
                   AND al.action_type IN ('copy_coupon','click_link')
                  GROUP BY a.web_user_id, a.tg_user_id
                )
                SELECT
                  agg.source_any                                                 AS source,
                  COALESCE(wu.display_name, bu.username, '—')                    AS الاسم,
                  COALESCE(wu.email, '—')                                        AS الإيميل,
                  COALESCE(wu.phone_number, '—')                                 AS الجوال,
                  COALESCE('@' || NULLIF(wu.telegram_username, ''),
                           '@' || NULLIF(bu.username, ''), '—')                  AS تيليجرام,
                  agg.views                                                      AS مرات_المشاهدة,
                  agg.stores_count                                               AS عدد_المتاجر,
                  agg.stores_list                                                AS متاجر_شاهدها,
                  COALESCE(acts.clicks, 0)                                       AS زيارات_من_الستوري,
                  COALESCE(acts.copies, 0)                                       AS نسخ_من_الستوري,
                  CASE WHEN COALESCE(acts.copies, 0) > 0 THEN '✅ نعم' ELSE '❌ لا' END
                                                                                 AS نسخ_كود_من_الستوري,
                  COALESCE(acts.visited_stores, '—')                             AS دخل_على,
                  COALESCE(acts.copied_stores,  '—')                             AS نسخ_من,
                  agg.first_view                                                 AS أول_مشاهدة,
                  agg.last_view                                                  AS آخر_مشاهدة
                FROM agg
                LEFT JOIN acts       USING (web_user_id, tg_user_id)
                LEFT JOIN web_users wu ON wu.id          = agg.web_user_id
                LEFT JOIN bot_users bu ON bu.telegram_id = agg.tg_user_id
                ORDER BY agg.views DESC, agg.last_view DESC
            """, conn_st, params=params)

            if all_viewers.empty:
                st.caption("لا مشاهدين بعد لهذا المصدر.")
            else:
                all_viewers["المصدر"] = all_viewers["source"].map(
                    {"web": "🌐 الموقع", "telegram_miniapp": "🔹 الميني ويب"}).fillna(all_viewers["source"])
                all_viewers["أول_مشاهدة"] = pd.to_datetime(all_viewers["أول_مشاهدة"], errors="coerce") \
                                                  .dt.strftime("%Y-%m-%d %H:%M")
                all_viewers["آخر_مشاهدة"] = pd.to_datetime(all_viewers["آخر_مشاهدة"], errors="coerce") \
                                                  .dt.strftime("%Y-%m-%d %H:%M")
                all_viewers.drop(columns=["source"], inplace=True)
                cols_order = ["المصدر", "الاسم", "الإيميل", "الجوال", "تيليجرام",
                              "مرات_المشاهدة", "عدد_المتاجر", "متاجر_شاهدها",
                              "زيارات_من_الستوري", "نسخ_من_الستوري", "نسخ_كود_من_الستوري",
                              "دخل_على", "نسخ_من", "أول_مشاهدة", "آخر_مشاهدة"]
                all_viewers = all_viewers[cols_order]
                st.dataframe(all_viewers, use_container_width=True, hide_index=True)
                st.caption(f"👥 {len(all_viewers)} شخص شاهدوا الستوري لهذا المصدر.")

            # ─── تفصيل المشاهدين لمتجر معيّن ──────────────────────────────
            st.markdown("---")
            st.subheader("🔍 مين شاهد ستوري متجر معيّن؟")
            stores_with_views = pd.read_sql(
                f"SELECT DISTINCT store_id FROM story_views {src_where} ORDER BY store_id",
                conn_st, params=params,
            )
            if stores_with_views.empty:
                st.caption("لا متاجر بعد.")
            else:
                pick_store = st.selectbox("اختر المتجر:", options=stores_with_views["store_id"].tolist(),
                                          key=f"sv_drill_{key_prefix}")
                viewer_filter_src = ""
                viewer_params = [pick_store]
                if source_filter:
                    viewer_filter_src = " AND sv.source = %s "
                    viewer_params.append(source_filter)

                viewers = pd.read_sql(f"""
                    SELECT
                      sv.source,
                      COALESCE(wu.display_name, bu.username, '—')            AS الاسم,
                      COALESCE(wu.email, '—')                                AS الإيميل,
                      COALESCE(wu.phone_number, '—')                         AS الجوال,
                      COALESCE('@' || NULLIF(wu.telegram_username, ''),
                               '@' || NULLIF(bu.username, ''), '—')          AS تيليجرام,
                      COUNT(*)                                               AS مرات_المشاهدة,
                      MIN(sv.viewed_at)                                      AS أول_مشاهدة,
                      MAX(sv.viewed_at)                                      AS آخر_مشاهدة,
                      (SELECT COUNT(*) FROM action_logs al
                         WHERE al.story_view_id IN (
                              SELECT view_id FROM story_views sv2
                               WHERE sv2.store_id = sv.store_id
                                 AND (sv2.web_user_id = sv.web_user_id OR sv2.tg_user_id = sv.tg_user_id)
                         ) AND al.action_type='copy_coupon')                 AS نُسخ,
                      (SELECT COUNT(*) FROM action_logs al
                         WHERE al.story_view_id IN (
                              SELECT view_id FROM story_views sv2
                               WHERE sv2.store_id = sv.store_id
                                 AND (sv2.web_user_id = sv.web_user_id OR sv2.tg_user_id = sv.tg_user_id)
                         ) AND al.action_type='click_link')                  AS زيارات
                    FROM story_views sv
                    LEFT JOIN web_users wu ON wu.id          = sv.web_user_id
                    LEFT JOIN bot_users bu ON bu.telegram_id = sv.tg_user_id
                    WHERE sv.store_id = %s {viewer_filter_src}
                    GROUP BY sv.source, sv.store_id, sv.web_user_id, sv.tg_user_id,
                             wu.display_name, wu.email, wu.phone_number, wu.telegram_username,
                             bu.username
                    ORDER BY مرات_المشاهدة DESC
                """, conn_st, params=viewer_params)

                if viewers.empty:
                    st.caption("لا مشاهدين بعد لهذا المتجر.")
                else:
                    viewers["المصدر"] = viewers["source"].map(
                        {"web": "🌐 الموقع", "telegram_miniapp": "🔹 الميني ويب"}).fillna(viewers["source"])
                    viewers["أول_مشاهدة"] = pd.to_datetime(viewers["أول_مشاهدة"], errors="coerce") \
                                                  .dt.strftime("%Y-%m-%d %H:%M")
                    viewers["آخر_مشاهدة"] = pd.to_datetime(viewers["آخر_مشاهدة"], errors="coerce") \
                                                  .dt.strftime("%Y-%m-%d %H:%M")
                    viewers.drop(columns=["source"], inplace=True)
                    st.dataframe(viewers, use_container_width=True, hide_index=True)
                    st.caption(f"👥 {len(viewers)} شخص شاهدوا ستوري «{pick_store}». «نُسخ» و«زيارات» مقترنة بفتحاتهم.")

        except Exception as e:
            st.error(f"⚠️ تعذّر تحميل تحليلات الستوري: {e}")
        finally:
            if 'conn_st' in locals():
                try: conn_st.close()
                except Exception: pass

    with sv_tab_all:
        _render_story_analytics(None, "all")
    with sv_tab_web:
        _render_story_analytics("web", "web")
    with sv_tab_mini:
        _render_story_analytics("telegram_miniapp", "mini")


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
            df_search['search_date'] = pd.to_datetime(df_search['search_date'], errors='coerce')

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
                        df_b['search_date'] = pd.to_datetime(df_b['search_date']).dt.strftime('%Y-%m-%d %H:%M')
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
                        df_w['search_date'] = pd.to_datetime(df_w['search_date']).dt.strftime('%Y-%m-%d %H:%M')
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
            req_df["تاريخ الطلب"] = pd.to_datetime(req_df["تاريخ الطلب"], errors='coerce')
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
                st.dataframe(susp, use_container_width=True, hide_index=True)

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
            disp["created_at"] = pd.to_datetime(disp["created_at"], errors="coerce") \
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
            st.dataframe(disp[shown_cols], use_container_width=True, hide_index=True)

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
                if st.button("💾 تحديث", key="rpt_upd_btn", use_container_width=True):
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

        df_req["requested_at"] = pd.to_datetime(df_req["requested_at"], errors="coerce")
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
                        users_df[_dc] = pd.to_datetime(users_df[_dc], errors='coerce').dt.strftime('%Y-%m-%d')

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
                    users_df[_dc] = pd.to_datetime(users_df[_dc], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')

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


# --- صفحة الحضور الحي: زوار البوت/الميني/الموقع · إجمالي + متواجدون الآن ---
elif page == "👥 الحضور الحي":
    page_title("👥", "الحضور الحي عبر القنوات",
               "إجمالي الزوار + المتواجدون الآن · البوت · الميني-ويب · الموقع")

    c1, c2, c3 = st.columns([1.6, 1.6, 3])
    with c1:
        window_min = st.selectbox("نافذة «متواجد الآن» (دقائق)",
                                  [5, 10, 15, 30, 60], index=0, key="presence_window",
                                  help="مستخدم متواجد = آخر تفاعل صريح خلال X دقيقة")
    with c2:
        auto = st.checkbox("🔁 تحديث تلقائي كل 10 ث", value=False, key="presence_auto")
    with c3:
        if st.button("🔄 تحديث الآن", key="presence_refresh"):
            st.rerun()

    _now_riyadh = (pd.Timestamp.utcnow() + pd.Timedelta(hours=3)).strftime("%H:%M:%S")
    st.caption(f"⏱️ آخر تحديث: **{_now_riyadh}** (الرياض) · "
               f"«متواجد» = آخر تفاعل صريح (رسالة/نقر/نسخ/بحث) ≤ {window_min} د. "
               f"لا يوجد heartbeat بعد، فالزائر الساكت لا يُعدّ متواجداً.")

    try:
        conn = get_conn()
        cur = conn.cursor()

        # ── البوت ───────────────────────────────────────────────────
        # عدد الناس = DISTINCT user_id من action_logs (أصدق من bot_users لو فُقدت صفوف)
        cur.execute("""SELECT COUNT(DISTINCT user_id) FROM action_logs
                       WHERE source='bot' AND user_id IS NOT NULL""")
        bot_people = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM action_logs WHERE source='bot'")
        bot_visits = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(DISTINCT user_id) FROM action_logs
                       WHERE source='bot' AND user_id IS NOT NULL
                         AND action_time >= NOW() - make_interval(mins => %s)""",
                    (window_min,))
        bot_live = cur.fetchone()[0]

        # ── الميني-ويب ──────────────────────────────────────────────
        cur.execute("""
            SELECT COUNT(DISTINCT COALESCE(user_id::text, encode(ip_hash,'hex')))
            FROM action_logs
            WHERE source IN ('telegram_miniapp','miniapp')
        """)
        mini_people = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM action_logs
                       WHERE source IN ('telegram_miniapp','miniapp')""")
        mini_visits = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(DISTINCT COALESCE(user_id::text, encode(ip_hash,'hex')))
            FROM action_logs
            WHERE source IN ('telegram_miniapp','miniapp')
              AND action_time >= NOW() - make_interval(mins => %s)
        """, (window_min,))
        mini_live = cur.fetchone()[0]

        # ── الموقع: ناس / زيارات / متواجدون / مجهولون (٤ كروت غير متداخلة) ──
        # عدد الناس الكلي = مسجَّلون + مجهولون مميَّزون (لا تداخل: المسجَّل له user_id، المجهول له ip_hash فقط)
        cur.execute("""
            SELECT
              (SELECT COUNT(DISTINCT user_id) FROM action_logs
                  WHERE source='web' AND user_id IS NOT NULL)
              +
              (SELECT COUNT(DISTINCT encode(ip_hash,'hex')) FROM action_logs
                  WHERE source='web' AND user_id IS NULL AND ip_hash IS NOT NULL)
        """)
        web_people = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM action_logs WHERE source='web'")
        web_visits = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(DISTINCT COALESCE(user_id::text, encode(ip_hash,'hex')))
            FROM action_logs
            WHERE source='web'
              AND action_time >= NOW() - make_interval(mins => %s)
        """, (window_min,))
        web_live = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(DISTINCT encode(ip_hash,'hex'))
            FROM action_logs
            WHERE source='web' AND user_id IS NULL AND ip_hash IS NOT NULL
        """)
        web_anon = cur.fetchone()[0]

        conn.close()

        st.divider()
        st.markdown("### 📱 البوت (تيليجرام)")
        b1, b2, b3 = st.columns(3)
        with b1:
            kpi_card("👥", "عدد الناس الكلي", f"{bot_people:,}", "info",
                     note="مستخدم مميَّز (محمد = ١ مهما كرّر)")
        with b2:
            kpi_card("📊", "إجمالي الزيارات", f"{bot_visits:,}", "neutral",
                     note="كل تفاعل = زيارة (محمد ٣ مرات = ٣)")
        with b3:
            kpi_card("🟢", f"المتواجد الفعلي (≤ {window_min} د)",
                     f"{bot_live:,}",
                     "emerald" if bot_live else "neutral")

        st.markdown("### 🔹 الميني-ويب (Telegram Mini App)")
        m1, m2, m3 = st.columns(3)
        with m1:
            kpi_card("👥", "عدد الناس الكلي", f"{mini_people:,}", "info")
        with m2:
            kpi_card("📊", "إجمالي الزيارات", f"{mini_visits:,}", "neutral")
        with m3:
            kpi_card("🟢", f"المتواجد الفعلي (≤ {window_min} د)",
                     f"{mini_live:,}",
                     "emerald" if mini_live else "neutral")
        if mini_visits <= 1:
            st.warning("⚠️ التتبّع فقير حالياً — لا يصل سوى نقر/نسخ. "
                       "تحتاج endpoint POST `/api/v1/track/visit` يضربه الـ frontend عند فتح الميني.")

        st.markdown("### 🌐 الموقع (dealpulseksa.com)")
        w1, w2, w3, w4 = st.columns(4)
        with w1:
            kpi_card("👥", "عدد الناس الكلي", f"{web_people:,}", "info",
                     note="مسجَّلون + مجهولون مميَّزون")
        with w2:
            kpi_card("📊", "إجمالي الزيارات", f"{web_visits:,}", "neutral",
                     note="كل تفاعل = زيارة")
        with w3:
            kpi_card("🟢", f"المتواجد الفعلي (≤ {window_min} د)",
                     f"{web_live:,}",
                     "emerald" if web_live else "neutral")
        with w4:
            kpi_card("👻", "منهم زائر مجهول",
                     f"{web_anon:,}", "warning",
                     note="فتح وتفاعل بدون تسجيل دخول")

        st.divider()
        st.markdown("#### ℹ️ القيود الحالية والخارطة")
        st.info(
            "- لا يوجد **heartbeat** من الـ frontend بعد، لذا الزائر الساكت غير المتفاعل لا يظهر «متواجد».\n"
            "- زوّار الموقع الذين يفتحون ولا ينقرون شيئاً = صفر سجل (لا page-view tracking).\n"
            "- الميني-ويب لا يسجّل فتح الواجهة — فقط النقر/النسخ يصل لـ `action_logs`.\n\n"
            "**المرحلة 2** — heartbeat كل 30 ثانية من الـ web/mini عبر `/track/heartbeat` + جدول `live_presence`.\n"
            "**المرحلة 3** — `visitor_id` UUID في localStorage لتمييز نفس الجهاز عبر تغيّر IP وربط المجهول بالمسجَّل بعد الدخول."
        )

        if auto:
            import time
            time.sleep(10)
            st.rerun()

    except Exception as e:
        st.error(f"⚠️ خطأ في تحميل بيانات الحضور: {e}")


# --- الصفحة الثانية عشرة: تحليل المستخدمين (Users Analytics) ---
elif page == "تحليل المستخدمين":
    page_title("📊", "مركز تحليل المستخدمين",
               "كل شي عن كل عميل — قاعدة + قرار + كتاب مفتوح لكل شخص + بناء شرائح")

    # ════════════════════════════════════════════════════════════════════
    # شريط التحكم العام
    # ════════════════════════════════════════════════════════════════════
    _ua_c1, _ua_c2, _ua_c3, _ua_c4 = st.columns([0.5, 1.2, 1.2, 3.1])
    with _ua_c1:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("🔄", help="مسح الكاش وإعادة التحميل", key="ua_refresh"):
            try: st.cache_data.clear()
            except Exception: pass
            st.rerun()
    # تقويم تواريخ من/إلى — بدل الـ slider
    _default_to   = date.today()
    _default_from = _default_to - timedelta(days=30)
    with _ua_c2:
        date_from = st.date_input("📅 من تاريخ:", value=_default_from,
                                  key="ua_date_from",
                                  max_value=_default_to)
    with _ua_c3:
        date_to = st.date_input("📅 إلى تاريخ:", value=_default_to,
                                key="ua_date_to",
                                min_value=date_from,
                                max_value=_default_to)
    with _ua_c4:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.caption("📡 فلتر المصدر داخل كل تبويب بالأسفل.")

    # عدد الأيام في النطاق (للاستعلامات اللي ما زالت تستخدم INTERVAL)
    N = max(1, (date_to - date_from).days + 1)
    # حدود زمنية صريحة للـ SQL (شامل)
    _t_from = pd.Timestamp(date_from).strftime("%Y-%m-%d 00:00:00")
    _t_to   = (pd.Timestamp(date_to) + pd.Timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    _SRC_SQL = {
        "🤖 البوت":       ("bot",),
        "🌐 الموقع":      ("web",),
        "🔹 الميني-ويب": ("telegram_miniapp", "miniapp"),
    }
    # كل تبويب يعيّن _src_tuple محلياً (None = الكل) — لا فلتر عام
    _src_tuple = None

    _SRC_LABEL = {
        "bot":              "🤖 البوت",
        "web":              "🌐 الموقع",
        "telegram_miniapp": "🔹 الميني-ويب",
        "miniapp":          "🔹 الميني-ويب",
    }

    # ترجمة شاملة لأنواع الحركات (action_logs.action_type) — تُستخدم في كل
    # الصفحة (الجداول، الـ pivot، آخر الحركات، السجل التفصيلي).
    _ACTION_AR = {
        "copy_coupon":              "🎟️ نسخ كوبون",
        "click_link":               "🖱️ نقر رابط",
        "search":                   "🔍 بحث",
        "view_tag":                 "🏷️ اختيار قسم",
        "view_story":               "🎬 مشاهدة ستوري",
        "start":                    "🚀 بدء جلسة",
        "end_session":              "⏹️ إنهاء جلسة",
        "back":                     "↩️ رجوع",
        "favorite_add":             "❤️ مفضّلة متجر +",
        "favorite_remove":          "🤍 مفضّلة متجر −",
        "category_favorite_add":    "🏷️❤️ مفضّلة قسم +",
        "category_favorite_remove": "🏷️🤍 مفضّلة قسم −",
        "idle_warn":                "⚠️ تحذير خمول",
        "idle_alert":               "🟠 تنبيه خمول",
        "idle_kick":                "🚪 طرد خمول",
        "lang_pick":                "🌐 اختيار لغة",
        "request_code":             "📩 طلب كود",
        "report_code":              "🚫 إبلاغ كود لا يعمل",
        "reaction_heart":           "تفاعل ❤️",
        "reaction_fire":            "تفاعل 🔥",
        "reaction_like":            "تفاعل 👍",
        "view_all":                 "📚 عرض كل المتاجر",
        "view_favorites":           "💛 عرض المفضلة",
        "view_trending":            "🔥 عرض الترند",
        "view_categories":          "📂 عرض الأقسام",
    }

    def _ua_src_clause(alias="al"):
        """يبني WHERE ... AND alias.source IN (...). يرجع (clause, params)."""
        if _src_tuple is None:
            return "", []
        ph = ",".join(["%s"] * len(_src_tuple))
        return f" AND {alias}.source IN ({ph}) ", list(_src_tuple)

    def _ua_time_clause(alias="al"):
        """نطاق زمني صريح (date_from ↔ date_to). يرجع (clause, params)."""
        return f" AND {alias}.action_time >= %s AND {alias}.action_time < %s ", [_t_from, _t_to]

    # توحيد أسماء المدن — العربي والإنجليزي يصبحان مدينة واحدة (canonical عربي).
    # يُستخدم في: الجغرافيا، تفصيل القنوات، الديموغرافيا، Audience Builder.
    def _norm_city_sql(col_expr: str) -> str:
        """يرجع SQL CASE WHEN يوحّد المدن السعودية بين العربي والإنجليزي."""
        return f"""
        CASE
          WHEN LOWER(TRIM({col_expr})) IN ('الرياض','riyadh','ar riyadh','ar-riyadh','al riyadh','riyad','riadh') THEN 'الرياض'
          WHEN LOWER(TRIM({col_expr})) IN ('جدة','جدة','جده','jeddah','jiddah','jedda','jiddah') THEN 'جدة'
          WHEN LOWER(TRIM({col_expr})) IN ('مكة','مكة المكرمة','makkah','mecca','makka','makkah al mukarramah') THEN 'مكة المكرمة'
          WHEN LOWER(TRIM({col_expr})) IN ('المدينة','المدينة المنورة','medina','madinah','al madinah','al-madinah') THEN 'المدينة المنورة'
          WHEN LOWER(TRIM({col_expr})) IN ('الدمام','dammam','ad dammam','ad-dammam','al dammam') THEN 'الدمام'
          WHEN LOWER(TRIM({col_expr})) IN ('الخبر','khobar','al khobar','al-khobar','khubar') THEN 'الخبر'
          WHEN LOWER(TRIM({col_expr})) IN ('الظهران','dhahran','al dhahran') THEN 'الظهران'
          WHEN LOWER(TRIM({col_expr})) IN ('ينبع','yanbu','yanbo','yenbo') THEN 'ينبع'
          WHEN LOWER(TRIM({col_expr})) IN ('تبوك','tabuk','tabouk') THEN 'تبوك'
          WHEN LOWER(TRIM({col_expr})) IN ('أبها','ابها','abha') THEN 'أبها'
          WHEN LOWER(TRIM({col_expr})) IN ('خميس مشيط','khamis mushait','khamis mushayt','khamis') THEN 'خميس مشيط'
          WHEN LOWER(TRIM({col_expr})) IN ('جازان','جيزان','jazan','jizan') THEN 'جازان'
          WHEN LOWER(TRIM({col_expr})) IN ('نجران','najran') THEN 'نجران'
          WHEN LOWER(TRIM({col_expr})) IN ('حائل','hail','ha''il','haaiel') THEN 'حائل'
          WHEN LOWER(TRIM({col_expr})) IN ('الباحة','al baha','al-baha','baha') THEN 'الباحة'
          WHEN LOWER(TRIM({col_expr})) IN ('بريدة','buraidah','buraydah','buraida') THEN 'بريدة'
          WHEN LOWER(TRIM({col_expr})) IN ('الطائف','taif','at taif','at-taif','al taif') THEN 'الطائف'
          WHEN LOWER(TRIM({col_expr})) IN ('عرعر','arar','ar ar') THEN 'عرعر'
          WHEN LOWER(TRIM({col_expr})) IN ('سكاكا','sakaka','sakakah') THEN 'سكاكا'
          WHEN LOWER(TRIM({col_expr})) IN ('القنفذة','qunfudah','al qunfudah','al-qunfudhah') THEN 'القنفذة'
          WHEN LOWER(TRIM({col_expr})) IN ('عنيزة','unaizah','unayzah') THEN 'عنيزة'
          WHEN LOWER(TRIM({col_expr})) IN ('الجبيل','jubail','al jubail','al-jubail') THEN 'الجبيل'
          WHEN LOWER(TRIM({col_expr})) IN ('رابغ','rabigh') THEN 'رابغ'
          WHEN LOWER(TRIM({col_expr})) IN ('القصيم','qassim','al qassim','al-qassim') THEN 'القصيم'
          WHEN LOWER(TRIM({col_expr})) IN ('','—',NULL) THEN NULL
          ELSE TRIM({col_expr})
        END
        """

    # Python-side normalizer لاستخدامات pandas (filter/group)
    _CITY_MAP_PY = {
        # English → Arabic canonical
        "riyadh":"الرياض","ar riyadh":"الرياض","ar-riyadh":"الرياض","al riyadh":"الرياض",
        "riyad":"الرياض","riadh":"الرياض",
        "jeddah":"جدة","jiddah":"جدة","jedda":"جدة","جده":"جدة",
        "makkah":"مكة المكرمة","mecca":"مكة المكرمة","الرياض":"الرياض","مكة":"مكة المكرمة",
        "medina":"المدينة المنورة","madinah":"المدينة المنورة","المدينة":"المدينة المنورة",
        "dammam":"الدمام","ad dammam":"الدمام",
        "khobar":"الخبر","al khobar":"الخبر",
        "dhahran":"الظهران",
        "yanbu":"ينبع","yanbo":"ينبع",
        "tabuk":"تبوك",
        "abha":"أبها","ابها":"أبها",
        "khamis mushait":"خميس مشيط","khamis":"خميس مشيط",
        "jazan":"جازان","jizan":"جازان","جيزان":"جازان",
        "najran":"نجران",
        "hail":"حائل",
        "al baha":"الباحة","baha":"الباحة",
        "buraidah":"بريدة","buraydah":"بريدة",
        "taif":"الطائف","at taif":"الطائف",
    }
    def _norm_city_py(v):
        if v is None: return None
        s = str(v).strip().lower()
        if s == "" or s == "—": return None
        return _CITY_MAP_PY.get(s, str(v).strip())

    try:
        conn = get_conn()
        try: conn.rollback()
        except Exception: pass

        # ════════════════════════════════════════════════════════════════
        # SECTION 0 (TOP) ─ 📖 الكتاب المفتوح — البحث الفردي العميق
        # ════════════════════════════════════════════════════════════════
        st.markdown("# 📋 سجل المستخدم — بحث عميق عن أي عميل")
        st.caption("ابحث بـ: إيميل · جوال · @تيليجرام · ID رقمي · جزء من الاسم — ستحصل على كل ما نملكه عن هذا الشخص.")

        q_raw = st.text_input(
            "🔎 ابحث عن شخص:",
            placeholder="example@mail.com  /  5XXXXXXXX  /  @username  /  123456789  /  محمد",
            key="ua_open_book_q",
        )

        if q_raw and q_raw.strip():
            try: conn.rollback()
            except Exception: pass

            q = q_raw.strip()
            q_lc = q.lstrip("@").lower()
            phone_norm = q.replace(" ", "").replace("-", "").replace("(","").replace(")","")
            if phone_norm.startswith("00"): phone_norm = "+" + phone_norm[2:]
            if phone_norm.startswith("0"):  phone_norm = "+966" + phone_norm[1:]
            if phone_norm.startswith("5") and len(phone_norm) == 9:
                phone_norm = "+966" + phone_norm

            web_user = None
            try:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM web_users
                         WHERE LOWER(COALESCE(email,'')) = %s
                            OR phone_number = %s
                            OR LOWER(COALESCE(telegram_username,'')) = %s
                            OR LOWER(COALESCE(display_name,'')) LIKE %s
                            OR (CASE WHEN %s ~ '^[0-9]+$' THEN id = %s::bigint ELSE FALSE END)
                         ORDER BY last_seen DESC NULLS LAST
                         LIMIT 1
                    """, (q_lc, phone_norm, q_lc, f"%{q_lc}%",
                          q, q if q.isdigit() else "0"))
                    web_user = cur.fetchone()
            except Exception as _e:
                conn.rollback()
                st.warning(f"تعذّر البحث في web_users: {_e}")

            bot_user = None
            try:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    keys = []
                    if web_user and web_user.get("telegram_username"):
                        keys.append(("username", web_user["telegram_username"].lower()))
                    if q.isdigit():
                        keys.append(("telegram_id", int(q)))
                    keys.append(("username", q_lc))
                    for col, val in keys:
                        if col == "telegram_id":
                            cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s LIMIT 1", (val,))
                        else:
                            cur.execute("SELECT * FROM bot_users WHERE LOWER(username) = %s LIMIT 1", (val,))
                        r = cur.fetchone()
                        if r:
                            bot_user = r
                            break
            except Exception as _e:
                conn.rollback()
                st.warning(f"تعذّر البحث في bot_users: {_e}")

            if not web_user and not bot_user:
                st.error("❌ لم يتم العثور على شخص مطابق. جرّب صيغة مختلفة.")
            else:
                wu_id = int(web_user["id"]) if web_user else None
                bu_tg = int(bot_user["telegram_id"]) if bot_user else None

                # ─── بطاقة الهوية ──────────────────────────────────────
                st.success(
                    f"✅ {'حساب ويب ✓' if web_user else '— لا ويب'} · "
                    f"{'حساب تيليجرام ✓' if bot_user else '— لا تيليجرام'}"
                )

                ic1, ic2 = st.columns([2,3])
                with ic1:
                    name = (web_user or {}).get("display_name") or \
                           (bot_user or {}).get("username") or "—"
                    st.markdown(f"### 👤 {name}")
                    badges = []
                    if web_user and web_user.get("email_verified_at"): badges.append("✉️ إيميل مؤكّد")
                    if web_user and web_user.get("consent_at"):        badges.append("✅ PDPL")
                    if bot_user: badges.append("📱 بوت")
                    st.caption(" · ".join(badges) if badges else "—")
                with ic2:
                    details = []
                    if web_user:
                        if web_user.get("email"):
                            details.append(f"📧 `{web_user['email']}`")
                        if web_user.get("phone_number"):
                            details.append(f"📞 `{web_user['phone_number']}`")
                    tg_un = (web_user or {}).get("telegram_username") or (bot_user or {}).get("username")
                    if tg_un:
                        details.append(f"💬 [@{tg_un}](https://t.me/{tg_un})")
                    if bu_tg: details.append(f"🆔 Telegram ID: `{bu_tg}`")
                    if wu_id: details.append(f"🆔 Web ID: `{wu_id}`")
                    st.markdown("  \n".join(details) if details else "—")

                # ─── الديموغرافيا ──────────────────────────────────────
                st.divider()
                gender_v  = (web_user or {}).get("gender")     or (bot_user or {}).get("gender")
                birth_v   = (web_user or {}).get("birth_date") or (bot_user or {}).get("birth_date")
                city_v    = (web_user or {}).get("city")       or (bot_user or {}).get("city")
                country_v = (web_user or {}).get("country")    or (bot_user or {}).get("country")
                lang_v    = (web_user or {}).get("lang")       or (bot_user or {}).get("lang")

                age_str = "—"; birth_str = "—"
                if birth_v:
                    try:
                        today = pd.Timestamp.today().date()
                        age_y = today.year - birth_v.year - ((today.month, today.day) < (birth_v.month, birth_v.day))
                        age_str = f"{age_y} سنة"
                        birth_str = birth_v.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                join_v = (web_user or {}).get("created_at") or (bot_user or {}).get("joined_at")
                last_v = (web_user or {}).get("last_seen")  or (bot_user or {}).get("last_seen")

                dc1, dc2, dc3, dc4, dc5, dc6 = st.columns(6)
                dc1.metric("👥 الجنس", "ذكر" if gender_v=="male" else "أنثى" if gender_v=="female" else "—")
                dc2.metric("🎂 العمر", age_str, delta=birth_str if birth_str!="—" else None)
                dc3.metric("📍 المدينة", city_v or "—")
                dc4.metric("🌐 اللغة", lang_v or "—")
                dc5.metric("📅 الانضمام", join_v.strftime("%Y-%m-%d") if join_v else "—")
                dc6.metric("⏰ آخر ظهور", last_v.strftime("%Y-%m-%d") if last_v else "—")

                # ─── شرط التصفية للأحداث (مع تمييز IDs لمنع التصادم) ──
                where_conds = []
                if web_user:
                    where_conds.append(f"(COALESCE(source,'') = 'web' AND user_id = {wu_id})")
                if bot_user:
                    where_conds.append(f"(COALESCE(source,'bot') IN ('bot','telegram_miniapp','miniapp') AND user_id = {bu_tg})")
                where_acts = " OR ".join(where_conds) if where_conds else "1=0"

                # ════════════════════════════════════════════════════
                # 🔬 الصف الخام من القاعدة — بدون JOIN ولا تحويل
                #   كل عمود من كل جدول بالقيمة الحقيقية كما هي في DB.
                # ════════════════════════════════════════════════════
                st.divider()
                st.markdown("### 🔬 الصف الخام من القاعدة — بدون أي تحويل")
                st.caption("ما تراه هنا هو القيمة الفعلية في PostgreSQL — لا COALESCE ولا normalize ولا fallback. الحقيقة العارية.")

                _raw_tabs = st.tabs([
                    "🌐 web_users (الخام)",
                    "🤖 bot_users (الخام)",
                    "📜 action_logs (آخر 200 حركة خام)",
                ])

                with _raw_tabs[0]:
                    if web_user and wu_id:
                        try: conn.rollback()
                        except Exception: pass
                        df_raw_web = pd.read_sql(
                            "SELECT * FROM web_users WHERE id = %s",
                            conn, params=(wu_id,))
                        if df_raw_web.empty:
                            st.warning("الصف غير موجود.")
                        else:
                            # نقلب لـ key/value لقراءة كل عمود بوضوح
                            raw_kv = df_raw_web.iloc[0].astype(str).reset_index()
                            raw_kv.columns = ["العمود", "القيمة الفعلية في DB"]
                            st.dataframe(raw_kv, use_container_width=True,
                                         hide_index=True, height=560)
                    else:
                        st.caption("لا حساب ويب لهذا المستخدم.")

                with _raw_tabs[1]:
                    if bot_user and bu_tg:
                        try: conn.rollback()
                        except Exception: pass
                        df_raw_bot = pd.read_sql(
                            "SELECT * FROM bot_users WHERE telegram_id = %s",
                            conn, params=(bu_tg,))
                        if df_raw_bot.empty:
                            st.warning("الصف غير موجود.")
                        else:
                            raw_kv = df_raw_bot.iloc[0].astype(str).reset_index()
                            raw_kv.columns = ["العمود", "القيمة الفعلية في DB"]
                            st.dataframe(raw_kv, use_container_width=True,
                                         hide_index=True, height=560)
                    else:
                        st.caption("لا حساب تيليجرام لهذا المستخدم.")

                with _raw_tabs[2]:
                    try: conn.rollback()
                    except Exception: pass
                    df_raw_acts = pd.read_sql(f"""
                        SELECT *
                          FROM action_logs
                         WHERE { where_acts }
                         ORDER BY action_time DESC
                         LIMIT 200
                    """, conn)
                    if df_raw_acts.empty:
                        st.caption("لا حركات.")
                    else:
                        # نحول الأعمدة بايتية إلى hex لتُعرض بدون مشاكل
                        for c in df_raw_acts.columns:
                            if df_raw_acts[c].dtype == object:
                                try:
                                    df_raw_acts[c] = df_raw_acts[c].apply(
                                        lambda v: v.hex() if isinstance(v, (bytes, bytearray, memoryview)) else v
                                    )
                                except Exception:
                                    pass
                        st.dataframe(df_raw_acts, use_container_width=True,
                                     hide_index=True, height=560)
                        st.caption(f"آخر {len(df_raw_acts)} حركة خام — كل الأعمدة.")
                        st.download_button(
                            "📥 CSV — السجل الخام",
                            df_raw_acts.astype(str).to_csv(index=False).encode("utf-8-sig"),
                            f"raw_actions_{name}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_raw_acts_{wu_id or bu_tg}",
                        )

                # ─── إحصائيات النشاط الكاملة ─────────────────────────
                st.divider()
                st.markdown("### 📊 سجل النشاط الكامل (كل الزمن، كل القنوات)")

                df_acts = pd.read_sql(f"""
                    SELECT COALESCE(source,'bot') AS source, action_type,
                           COUNT(*) AS cnt,
                           MIN(action_time) AS first_at,
                           MAX(action_time) AS last_at
                      FROM action_logs
                     WHERE {where_acts}
                     GROUP BY source, action_type
                """, conn)

                def _tot(at):
                    d = df_acts[df_acts["action_type"]==at]
                    return int(d["cnt"].sum()) if not d.empty else 0

                df_days = pd.read_sql(f"""
                    SELECT COUNT(DISTINCT DATE(action_time)) AS active_days
                      FROM action_logs WHERE {where_acts}
                """, conn)
                active_days = int(df_days["active_days"][0] or 0)

                # ستوري
                story_conds = []
                if web_user: story_conds.append(f"sv.web_user_id = {wu_id}")
                if bot_user: story_conds.append(f"sv.tg_user_id = {bu_tg}")
                where_story = " OR ".join(story_conds) if story_conds else "1=0"

                story_views_count = int(pd.read_sql(f"""
                    SELECT COUNT(*) AS c FROM story_views sv WHERE {where_story}
                """, conn)["c"][0] or 0)

                tc1, tc2, tc3, tc4, tc5, tc6 = st.columns(6)
                tc1.metric("🎟️ نسخ كوبونات", _tot("copy_coupon"))
                tc2.metric("🖱️ نقرات روابط", _tot("click_link"))
                tc3.metric("🔍 عمليات بحث", _tot("search"))
                tc4.metric("🚀 جلسات بدء", _tot("start"))
                tc5.metric("🎬 مشاهدات ستوري", story_views_count)
                tc6.metric("📅 أيام نشط", active_days)

                if not df_acts.empty:
                    pivot_src = (df_acts
                                 .pivot_table(index="source", columns="action_type",
                                              values="cnt", fill_value=0, aggfunc="sum"))
                    # نطبّق ترجمة _ACTION_AR + للأعمدة غير المعروفة نضع
                    # اسماً عربياً صالحاً مكوّناً من نسخة الكود نفسها لتفادي
                    # تكرار الأسماء (يحدث لو حركة جديدة لم تُترجم بعد).
                    def _ac_label(c: str) -> str:
                        return _ACTION_AR.get(c, c)
                    pivot_src.rename(columns={c: _ac_label(c) for c in pivot_src.columns}, inplace=True)
                    pivot_src.index = pivot_src.index.map(lambda s: _SRC_LABEL.get(s, s))
                    pivot_src.index.name = "المصدر"
                    pivot_src.columns.name = "نوع الحركة"
                    st.caption("تفصيل حسب القناة:")
                    st.dataframe(pivot_src.astype(int), use_container_width=True)

                # ─── المتاجر التي تفاعل معها ─────────────────────────
                st.divider()
                st.markdown("### 🏪 المتاجر التي تفاعل معها — وما الذي فعله بالضبط")
                df_stores = pd.read_sql(f"""
                    SELECT
                      COALESCE(a.store_id, '—') AS المتجر,
                      COUNT(*) FILTER (WHERE a.action_type='copy_coupon') AS نسخ,
                      COUNT(*) FILTER (WHERE a.action_type='click_link')  AS نقر,
                      COUNT(*) FILTER (WHERE a.action_type='search')      AS بحث,
                      TO_CHAR(MIN(a.action_time),'YYYY-MM-DD HH24:MI') AS أول_تفاعل,
                      TO_CHAR(MAX(a.action_time),'YYYY-MM-DD HH24:MI') AS آخر_تفاعل
                    FROM action_logs a
                    WHERE ({where_acts}) AND a.store_id IS NOT NULL
                    GROUP BY a.store_id
                    ORDER BY (COUNT(*) FILTER (WHERE a.action_type='copy_coupon')
                              + COUNT(*) FILTER (WHERE a.action_type='click_link')*0.5) DESC
                    LIMIT 100
                """, conn)
                if df_stores.empty:
                    st.info("لم يتفاعل مع أي متجر بعد.")
                else:
                    st.dataframe(df_stores, use_container_width=True, hide_index=True, height=300)
                    st.caption(f"إجمالي المتاجر التي تفاعل معها: **{len(df_stores)}**")

                # ─── الستوري ────────────────────────────────────────
                st.divider()
                st.markdown("### 🎬 القصص التي شاهدها — وأي منها تحوّلت لنسخ/زيارة")
                df_stories = pd.read_sql(f"""
                    SELECT
                      sv.store_id AS المتجر,
                      sv.source AS source,
                      COUNT(*) AS عدد_المشاهدات,
                      TO_CHAR(MIN(sv.viewed_at),'YYYY-MM-DD HH24:MI') AS أول_مشاهدة,
                      TO_CHAR(MAX(sv.viewed_at),'YYYY-MM-DD HH24:MI') AS آخر_مشاهدة,
                      (SELECT COUNT(*) FROM action_logs al2
                         WHERE al2.story_view_id IN (
                            SELECT view_id FROM story_views sv2
                             WHERE sv2.store_id=sv.store_id
                               AND ( (sv.web_user_id IS NOT NULL AND sv2.web_user_id=sv.web_user_id)
                                  OR (sv.tg_user_id IS NOT NULL AND sv2.tg_user_id=sv.tg_user_id))
                         )
                           AND al2.action_type='copy_coupon') AS نسخ_من_الستوري,
                      (SELECT COUNT(*) FROM action_logs al2
                         WHERE al2.story_view_id IN (
                            SELECT view_id FROM story_views sv2
                             WHERE sv2.store_id=sv.store_id
                               AND ( (sv.web_user_id IS NOT NULL AND sv2.web_user_id=sv.web_user_id)
                                  OR (sv.tg_user_id IS NOT NULL AND sv2.tg_user_id=sv.tg_user_id))
                         )
                           AND al2.action_type='click_link') AS زيارات_من_الستوري
                    FROM story_views sv
                    WHERE {where_story}
                    GROUP BY sv.store_id, sv.source, sv.web_user_id, sv.tg_user_id
                    ORDER BY عدد_المشاهدات DESC
                """, conn)
                if df_stories.empty:
                    st.info("لم يشاهد أي ستوري بعد.")
                else:
                    df_stories["المصدر"] = df_stories["source"].map(_SRC_LABEL).fillna(df_stories["source"])
                    df_stories.drop(columns=["source"], inplace=True)
                    cols_order = ["المصدر","المتجر","عدد_المشاهدات",
                                  "نسخ_من_الستوري","زيارات_من_الستوري",
                                  "أول_مشاهدة","آخر_مشاهدة"]
                    df_stories = df_stories[cols_order]
                    st.dataframe(df_stories, use_container_width=True, hide_index=True)

                # ─── المفضلة (متاجر + أقسام، منفصلة لكل حساب) ─────
                st.divider()
                st.markdown("### ❤️ المفضلة — متاجر + أقسام")
                st.caption("منفصلة لكل حساب (الموقع ≠ تيليجرام) — قاعدة التنبيه الشخصي.")
                _PLAT = {"bot":"📱 بوت","web":"🌐 ويب","miniapp":"🔹 ميني-ويب"}

                fav_all_stores, fav_all_cats = set(), set()

                def _show_favs(owner_col, owner_val, label):
                    favs = pd.read_sql(
                        f"""
                        SELECT kind, store_id, category_name, platform,
                               TO_CHAR(created_at,'YYYY-MM-DD HH24:MI') AS أُضيف
                          FROM user_favorites
                         WHERE {owner_col} = %s
                         ORDER BY created_at DESC
                        """, conn, params=(owner_val,))
                    st.markdown(f"**{label}** — {len(favs)} عنصر")
                    if favs.empty:
                        st.caption("لا مفضلة لهذا الحساب بعد.")
                        return
                    s_df = favs[favs["kind"]=="store"]
                    c_df = favs[favs["kind"]=="category"]
                    for sid in s_df["store_id"].dropna(): fav_all_stores.add(sid)
                    for cn  in c_df["category_name"].dropna(): fav_all_cats.add(cn)
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        st.markdown(f"🏪 متاجر: **{len(s_df)}**")
                        if not s_df.empty:
                            v = s_df[["store_id","platform","أُضيف"]].rename(
                                columns={"store_id":"المتجر","platform":"المنصة"})
                            v["المنصة"] = v["المنصة"].map(_PLAT).fillna(v["المنصة"])
                            st.dataframe(v, use_container_width=True, hide_index=True, height=220)
                    with fc2:
                        st.markdown(f"🏷️ أقسام: **{len(c_df)}**")
                        if not c_df.empty:
                            v = c_df[["category_name","platform","أُضيف"]].rename(
                                columns={"category_name":"القسم","platform":"المنصة"})
                            v["المنصة"] = v["المنصة"].map(_PLAT).fillna(v["المنصة"])
                            st.dataframe(v, use_container_width=True, hide_index=True, height=220)

                if web_user:
                    _show_favs("web_user_id", wu_id, "🌐 مفضلة الموقع")
                if bot_user:
                    _show_favs("telegram_id", bu_tg, "📱 مفضلة تيليجرام")

                # ─── ولاء المفضّلة: نسخ + بحث من المفضّلة ────────
                if fav_all_stores:
                    fav_stores_list = list(fav_all_stores)
                    cf = pd.read_sql(f"""
                        SELECT COUNT(*) AS c FROM action_logs
                         WHERE ({where_acts}) AND action_type='copy_coupon'
                           AND store_id = ANY(%s)
                    """, conn, params=(fav_stores_list,))
                    nfc = int(cf["c"][0] or 0)
                    sf = pd.read_sql(f"""
                        SELECT COUNT(*) AS c FROM action_logs
                         WHERE ({where_acts}) AND action_type='search'
                           AND store_id = ANY(%s)
                    """, conn, params=(fav_stores_list,))
                    nfs = int(sf["c"][0] or 0)

                    total_cp = _tot("copy_coupon")
                    loyalty = round(100*nfc/max(1,total_cp), 1) if total_cp else 0.0

                    st.markdown("#### 💎 ولاء المفضّلة")
                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric("🎟️ نسخ من متاجره المفضّلة", nfc)
                    lc2.metric("🔍 بحث عن متاجره المفضّلة", nfs)
                    lc3.metric("💎 نسبة الولاء", f"{loyalty}%",
                               delta="من إجمالي نسخه")

                # ─── طلبات الأكواد ────────────────────────────────
                st.divider()
                st.markdown("### 📩 طلبات الأكواد — وش طلب ومتى")
                req_parts = []
                req_params = []
                if web_user and web_user.get("email"):
                    req_parts.append("r.user_email = %s")
                    req_params.append(web_user["email"])
                if bot_user:
                    req_parts.append("r.user_id = %s")
                    req_params.append(bu_tg)
                if req_parts:
                    df_reqs = pd.read_sql(f"""
                        SELECT r.brand_name AS المتجر_المطلوب,
                               TO_CHAR(r.requested_at,'YYYY-MM-DD HH24:MI') AS التاريخ,
                               CASE WHEN r.master_id IS NULL THEN '⏳ معلّقة' ELSE '✅ وفّرناه' END AS الحالة
                          FROM unavailable_codes_requests r
                         WHERE { ' OR '.join(req_parts) }
                         ORDER BY r.requested_at DESC
                    """, conn, params=tuple(req_params))
                    if df_reqs.empty:
                        st.caption("لم يطلب أي كود بعد.")
                    else:
                        st.metric("📩 إجمالي الطلبات", len(df_reqs))
                        st.dataframe(df_reqs, use_container_width=True, hide_index=True)
                else:
                    st.caption("لا هوية معروفة لربط الطلبات.")

                # ─── خط الأيام النشطة + كل الحركات في النطاق ──────────────
                st.divider()
                st.markdown("### 📜 خط الأيام النشطة + كل حركات العميل في النطاق المحدّد")

                df_tl = pd.read_sql(f"""
                    SELECT DATE(action_time) AS d, COUNT(*) AS c
                      FROM action_logs WHERE {where_acts}
                     GROUP BY DATE(action_time)
                     ORDER BY d
                """, conn)
                if not df_tl.empty and len(df_tl) >= 2:
                    fig_tl = px.bar(df_tl, x="d", y="c",
                                    title="الأيام التي دخل فيها (تكرار الحركات لكل يوم)")
                    st.plotly_chart(apply_brand_theme(fig_tl), use_container_width=True)

                # كل حركات العميل في النطاق المحدّد (لا LIMIT — التاريخ هو الفلتر)
                df_recent = pd.read_sql(f"""
                    SELECT
                      TO_CHAR(a.action_time,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                      a.action_type AS الحركة,
                      COALESCE(a.source,'bot') AS source,
                      COALESCE(a.store_id,'—') AS المتجر,
                      COALESCE(a.city,'') AS المدينة,
                      COALESCE(a.details,'') AS التفاصيل
                    FROM action_logs a
                    WHERE ({where_acts})
                      AND a.action_time >= %s AND a.action_time < %s
                    ORDER BY a.action_time DESC
                """, conn, params=(_t_from, _t_to))
                if df_recent.empty:
                    st.info(f"📭 لا حركات لهذا العميل في النطاق {date_from} → {date_to}.")
                else:
                    df_recent["المصدر"] = df_recent["source"].map(_SRC_LABEL).fillna(df_recent["source"])
                    # ترجمة الحركة إلى العربي عبر القاموس الموحّد
                    df_recent["الحركة"] = df_recent["الحركة"].map(_ACTION_AR).fillna(df_recent["الحركة"])
                    df_recent = df_recent.drop(columns=["source"])
                    df_recent = df_recent[["الوقت","الحركة","المصدر","المتجر","المدينة","التفاصيل"]]
                    st.caption(
                        f"📊 إجمالي الحركات في النطاق: **{len(df_recent):,}** "
                        f"({date_from.strftime('%Y-%m-%d')} → {date_to.strftime('%Y-%m-%d')}) — "
                        "اضبط نطاق التاريخ من فوق الصفحة لتغيير الحدود."
                    )
                    st.dataframe(df_recent, use_container_width=True, hide_index=True, height=520)
                    # CSV مستقل لجميع الحركات
                    st.download_button(
                        "📥 CSV — كل حركات العميل في النطاق",
                        df_recent.to_csv(index=False).encode("utf-8-sig"),
                        f"actions_{name}_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_actions_full_{wu_id or bu_tg}",
                    )

                # ════════════════════════════════════════════════════════════
                # 📜 السجل التفصيلي الكامل — كل حدث في سطر بالتاريخ والوقت
                #   موحّد بين البوت + الموقع + الميني-ويب (ضم أوتوماتيكي).
                #   كل تابز = نوع حدث، مرتّب من الأحدث، قابل للتصدير CSV.
                # ════════════════════════════════════════════════════════════
                st.divider()
                st.markdown("### 📜 السجل التفصيلي — كل حدث في سطر")
                st.caption("كل فتحة ستوري، كل نسخة، كل نقرة، كل بحث، كل قسم، كل مفضّلة، كل جلسة — في سطر مستقل بتاريخ ووقت.")

                _ev_xlsx_sheets = {}  # نجمع كل الجداول لتصدير Excel موحّد لاحقاً

                ev_tabs = st.tabs([
                    "🎬 الستوري (كل فتحة)",
                    "🏬 المتاجر (كل تفاعل)",
                    "🏷️ الأقسام (كل تفاعل)",
                    "🔥 الترند (كل تفاعل)",
                    "❤️ المفضّلة (كل إضافة)",
                    "🔍 البحث (كل بحث)",
                    "🚀 الجلسات (كل دخول)",
                ])

                # ───── 🎬 الستوري: كل فتحة + هل نسخ/نقر من نفس الفتحة ─────
                with ev_tabs[0]:
                    df_sv = pd.read_sql(f"""
                        SELECT
                          TO_CHAR(sv.viewed_at, 'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                          sv.store_id AS المتجر,
                          sv.source AS source,
                          sv.view_id::text AS view_id,
                          (SELECT TO_CHAR(MIN(al.action_time),'YYYY-MM-DD HH24:MI:SS')
                             FROM action_logs al
                            WHERE al.story_view_id = sv.view_id
                              AND al.action_type='copy_coupon')        AS وقت_النسخ,
                          (SELECT TO_CHAR(MIN(al.action_time),'YYYY-MM-DD HH24:MI:SS')
                             FROM action_logs al
                            WHERE al.story_view_id = sv.view_id
                              AND al.action_type='click_link')         AS وقت_الزيارة
                        FROM story_views sv
                        WHERE {where_story}
                        ORDER BY sv.viewed_at DESC
                    """, conn)
                    if df_sv.empty:
                        st.info("لم يفتح أي ستوري بعد.")
                    else:
                        df_sv["المصدر"] = df_sv["source"].map(_SRC_LABEL).fillna(df_sv["source"])
                        df_sv["النسخ من الستوري"]    = df_sv["وقت_النسخ"].apply(lambda v: f"✅ {v}" if v else "—")
                        df_sv["الزيارة من الستوري"]  = df_sv["وقت_الزيارة"].apply(lambda v: f"✅ {v}" if v else "—")
                        df_sv_show = df_sv[["الوقت","المصدر","المتجر","النسخ من الستوري","الزيارة من الستوري"]]
                        st.dataframe(df_sv_show, use_container_width=True, hide_index=True, height=420)
                        st.caption(f"إجمالي الفتحات: **{len(df_sv)}** · فتحات أدّت لنسخ: "
                                   f"**{(df_sv['وقت_النسخ'].notna()).sum()}** · "
                                   f"فتحات أدّت لزيارة: **{(df_sv['وقت_الزيارة'].notna()).sum()}**")
                        st.download_button("📥 CSV — كل فتحات الستوري",
                                           df_sv_show.to_csv(index=False).encode("utf-8-sig"),
                                           f"profile_{name}_stories_{date.today()}.csv", "text/csv",
                                           key=f"ua_dl_ev_stories_{wu_id or bu_tg}")
                        _ev_xlsx_sheets["الستوري_كل_فتحة"] = df_sv_show

                # ───── 🏬 المتاجر: كل تفاعل (نسخ/نقر/بحث) بسطر مستقل ──────
                with ev_tabs[1]:
                    df_si = pd.read_sql(f"""
                        SELECT
                          TO_CHAR(a.action_time,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                          a.action_type AS action_type,
                          COALESCE(a.source,'bot') AS source,
                          a.store_id AS المتجر,
                          COALESCE(a.city,'') AS المدينة,
                          COALESCE(a.details,'') AS التفاصيل
                        FROM action_logs a
                        WHERE ({where_acts})
                          AND a.store_id IS NOT NULL AND a.store_id <> ''
                          AND a.action_type IN ('copy_coupon','click_link','search')
                        ORDER BY a.action_time DESC
                    """, conn)
                    if df_si.empty:
                        st.info("لا تفاعلات مع متاجر بعد.")
                    else:
                        df_si["الحركة"] = df_si["action_type"].map(_ACTION_AR).fillna(df_si["action_type"])
                        df_si["المصدر"] = df_si["source"].map(_SRC_LABEL).fillna(df_si["source"])
                        df_si_show = df_si[["الوقت","الحركة","المصدر","المتجر","المدينة","التفاصيل"]]
                        st.dataframe(df_si_show, use_container_width=True, hide_index=True, height=420)
                        nx = int((df_si["action_type"]=="copy_coupon").sum())
                        nc = int((df_si["action_type"]=="click_link").sum())
                        ns = int((df_si["action_type"]=="search").sum())
                        st.caption(f"إجمالي: **{len(df_si)}** سطر · نسخ: **{nx}** · نقر: **{nc}** · بحث: **{ns}**")
                        st.download_button("📥 CSV — كل تفاعلات المتاجر",
                                           df_si_show.to_csv(index=False).encode("utf-8-sig"),
                                           f"profile_{name}_stores_events_{date.today()}.csv", "text/csv",
                                           key=f"ua_dl_ev_stores_{wu_id or bu_tg}")
                        _ev_xlsx_sheets["المتاجر_كل_تفاعل"] = df_si_show

                # ───── 🏷️ الأقسام: كل view_tag بسطر ───────────────────────
                with ev_tabs[2]:
                    df_ct = pd.read_sql(f"""
                        SELECT
                          TO_CHAR(a.action_time,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                          COALESCE(a.source,'bot') AS source,
                          REPLACE(SPLIT_PART(COALESCE(a.details,''),';',1),'tag:','') AS القسم,
                          COALESCE(a.store_id,'—') AS من_صفحة_المتجر,
                          COALESCE(a.city,'') AS المدينة
                        FROM action_logs a
                        WHERE ({where_acts}) AND a.action_type = 'view_tag'
                        ORDER BY a.action_time DESC
                    """, conn)
                    if df_ct.empty:
                        st.info("لم يختر أي قسم بعد.")
                    else:
                        df_ct["المصدر"] = df_ct["source"].map(_SRC_LABEL).fillna(df_ct["source"])
                        df_ct_show = df_ct[["الوقت","المصدر","القسم","من_صفحة_المتجر","المدينة"]]
                        st.dataframe(df_ct_show, use_container_width=True, hide_index=True, height=400)
                        uniq_cats = df_ct["القسم"].nunique()
                        st.caption(f"إجمالي: **{len(df_ct)}** اختيار · أقسام فريدة: **{uniq_cats}**")
                        st.download_button("📥 CSV — كل اختيارات الأقسام",
                                           df_ct_show.to_csv(index=False).encode("utf-8-sig"),
                                           f"profile_{name}_categories_{date.today()}.csv", "text/csv",
                                           key=f"ua_dl_ev_cats_{wu_id or bu_tg}")
                        _ev_xlsx_sheets["الأقسام_كل_تفاعل"] = df_ct_show

                # ───── 🔥 الترند: تفاعلات على متاجر is_trending ───────────
                with ev_tabs[3]:
                    df_tr = pd.read_sql(f"""
                        SELECT
                          TO_CHAR(a.action_time,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                          a.action_type AS action_type,
                          COALESCE(a.source,'bot') AS source,
                          a.store_id AS المتجر,
                          COALESCE(a.city,'') AS المدينة
                        FROM action_logs a
                        JOIN master m ON m.store_id = a.store_id
                        WHERE ({where_acts})
                          AND a.store_id IS NOT NULL AND a.store_id <> ''
                          AND m.is_trending = 'ترند 🔥'
                          AND a.action_type IN ('copy_coupon','click_link','search','view_tag')
                        ORDER BY a.action_time DESC
                    """, conn)
                    if df_tr.empty:
                        st.info("لم يتفاعل مع أي متجر ترند بعد.")
                    else:
                        df_tr["الحركة"] = df_tr["action_type"].map(_ACTION_AR).fillna(df_tr["action_type"])
                        df_tr["المصدر"] = df_tr["source"].map(_SRC_LABEL).fillna(df_tr["source"])
                        df_tr_show = df_tr[["الوقت","الحركة","المصدر","المتجر","المدينة"]]
                        st.dataframe(df_tr_show, use_container_width=True, hide_index=True, height=400)
                        st.caption(f"إجمالي: **{len(df_tr)}** تفاعل مع متاجر ترند · "
                                   f"متاجر فريدة: **{df_tr['المتجر'].nunique()}**")
                        st.download_button("📥 CSV — تفاعلات الترند",
                                           df_tr_show.to_csv(index=False).encode("utf-8-sig"),
                                           f"profile_{name}_trend_{date.today()}.csv", "text/csv",
                                           key=f"ua_dl_ev_trend_{wu_id or bu_tg}")
                        _ev_xlsx_sheets["الترند_كل_تفاعل"] = df_tr_show

                # ───── ❤️ المفضّلة: كل إضافة بسطر ─────────────────────────
                with ev_tabs[4]:
                    fav_parts = []
                    fav_params = []
                    if web_user:
                        fav_parts.append("web_user_id = %s")
                        fav_params.append(wu_id)
                    if bot_user:
                        fav_parts.append("telegram_id = %s")
                        fav_params.append(bu_tg)
                    if fav_parts:
                        df_fv = pd.read_sql(f"""
                            SELECT
                              TO_CHAR(created_at,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                              kind                          AS النوع,
                              COALESCE(store_id, '—')       AS المتجر,
                              COALESCE(category_name, '—')  AS القسم,
                              platform                      AS source
                            FROM user_favorites
                            WHERE { ' OR '.join(fav_parts) }
                            ORDER BY created_at DESC
                        """, conn, params=tuple(fav_params))
                        if df_fv.empty:
                            st.info("لا مفضّلة بعد.")
                        else:
                            df_fv["النوع"] = df_fv["النوع"].map({"store":"🏪 متجر","category":"🏷️ قسم"}).fillna(df_fv["النوع"])
                            df_fv["المصدر"] = df_fv["source"].map(_SRC_LABEL).fillna(df_fv["source"])
                            df_fv_show = df_fv[["الوقت","النوع","المصدر","المتجر","القسم"]]
                            st.dataframe(df_fv_show, use_container_width=True, hide_index=True, height=400)
                            st.caption(f"إجمالي: **{len(df_fv)}** مفضّلة · "
                                       f"متاجر: **{int((df_fv['النوع'].str.contains('متجر')).sum())}** · "
                                       f"أقسام: **{int((df_fv['النوع'].str.contains('قسم')).sum())}**")
                            st.download_button("📥 CSV — كل المفضّلة",
                                               df_fv_show.to_csv(index=False).encode("utf-8-sig"),
                                               f"profile_{name}_favorites_{date.today()}.csv", "text/csv",
                                               key=f"ua_dl_ev_favs_{wu_id or bu_tg}")
                            _ev_xlsx_sheets["المفضّلة_كل_إضافة"] = df_fv_show
                    else:
                        st.caption("لا هوية للبحث في المفضّلة.")

                # ───── 🔍 البحث: كل بحث + الكلمة + هل وُجد ────────────────
                with ev_tabs[5]:
                    # المصادر: direct_search (للجميع) + action_logs.search (للنسخ المتزامن)
                    ds_parts = []
                    ds_params = []
                    if web_user:
                        ds_parts.append("(platform = 'Web' AND user_id = %s)")
                        ds_params.append(wu_id)
                        if web_user.get("email"):
                            ds_parts.append("(LOWER(user_email) = %s)")
                            ds_params.append(web_user["email"].lower())
                    if bot_user:
                        ds_parts.append("(platform IN ('Bot','Miniapp') AND user_id = %s)")
                        ds_params.append(bu_tg)
                    if ds_parts:
                        df_sr = pd.read_sql(f"""
                            SELECT
                              TO_CHAR(search_date,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                              platform AS source,
                              search_keyword AS الكلمة,
                              COALESCE(store_id, '—') AS وُجد_متجر,
                              CASE WHEN user_found THEN '✅' ELSE '❌' END AS نتيجة
                            FROM direct_search
                            WHERE { ' OR '.join(ds_parts) }
                            ORDER BY search_date DESC
                        """, conn, params=tuple(ds_params))
                        if df_sr.empty:
                            st.info("لم يبحث بعد.")
                        else:
                            df_sr["المصدر"] = df_sr["source"].map({
                                "Web":"🌐 الموقع","Bot":"🤖 البوت",
                                "Miniapp":"🔹 الميني-ويب","Dashboard":"⚙️ الداشبورد",
                            }).fillna(df_sr["source"])
                            df_sr_show = df_sr[["الوقت","المصدر","الكلمة","نتيجة","وُجد_متجر"]]
                            st.dataframe(df_sr_show, use_container_width=True, hide_index=True, height=400)
                            found_n   = int((df_sr["نتيجة"]=="✅").sum())
                            unfound_n = int((df_sr["نتيجة"]=="❌").sum())
                            st.caption(f"إجمالي: **{len(df_sr)}** بحث · ناجح: **{found_n}** · فاشل: **{unfound_n}**")
                            st.download_button("📥 CSV — كل عمليات البحث",
                                               df_sr_show.to_csv(index=False).encode("utf-8-sig"),
                                               f"profile_{name}_searches_{date.today()}.csv", "text/csv",
                                               key=f"ua_dl_ev_searches_{wu_id or bu_tg}")
                            _ev_xlsx_sheets["البحث_كل_بحث"] = df_sr_show
                    else:
                        st.caption("لا هوية للبحث.")

                # ───── 🚀 الجلسات: كل start بسطر ──────────────────────────
                with ev_tabs[6]:
                    df_se = pd.read_sql(f"""
                        SELECT
                          TO_CHAR(a.action_time,'YYYY-MM-DD HH24:MI:SS') AS الوقت,
                          COALESCE(a.source,'bot') AS source,
                          COALESCE(a.city,'') AS المدينة,
                          COALESCE(a.country_code,'') AS البلد,
                          COALESCE(a.details,'') AS التفاصيل
                        FROM action_logs a
                        WHERE ({where_acts}) AND a.action_type = 'start'
                        ORDER BY a.action_time DESC
                    """, conn)
                    if df_se.empty:
                        st.info("لا جلسات مسجّلة بعد.")
                    else:
                        df_se["المصدر"] = df_se["source"].map(_SRC_LABEL).fillna(df_se["source"])
                        df_se_show = df_se[["الوقت","المصدر","المدينة","البلد","التفاصيل"]]
                        st.dataframe(df_se_show, use_container_width=True, hide_index=True, height=400)
                        st.caption(f"إجمالي الجلسات: **{len(df_se)}**")
                        st.download_button("📥 CSV — كل الجلسات",
                                           df_se_show.to_csv(index=False).encode("utf-8-sig"),
                                           f"profile_{name}_sessions_{date.today()}.csv", "text/csv",
                                           key=f"ua_dl_ev_sessions_{wu_id or bu_tg}")
                        _ev_xlsx_sheets["الجلسات_كل_دخول"] = df_se_show

                # ─── تصدير الكتاب الكامل ──────────────────────────
                st.divider()
                out = BytesIO()
                with pd.ExcelWriter(out, engine="xlsxwriter") as w:
                    identity_rows = {
                        "الاسم": name,
                        "الإيميل": (web_user or {}).get("email") or "—",
                        "الجوال":  (web_user or {}).get("phone_number") or "—",
                        "تيليجرام": f"@{tg_un}" if tg_un else "—",
                        "Telegram_ID": bu_tg or "—",
                        "Web_ID": wu_id or "—",
                        "الجنس": "ذكر" if gender_v=="male" else ("أنثى" if gender_v=="female" else "—"),
                        "العمر": age_str,
                        "تاريخ_الميلاد": birth_str,
                        "المدينة": city_v or "—",
                        "البلد": country_v or "—",
                        "اللغة": lang_v or "—",
                        "تاريخ_الانضمام": join_v.strftime("%Y-%m-%d") if join_v else "—",
                        "آخر_ظهور": last_v.strftime("%Y-%m-%d") if last_v else "—",
                        "إجمالي_النسخ":   _tot("copy_coupon"),
                        "إجمالي_النقرات": _tot("click_link"),
                        "إجمالي_البحث":   _tot("search"),
                        "أيام_نشط":       active_days,
                        "مشاهدات_ستوري":  story_views_count,
                    }
                    pd.DataFrame([identity_rows]).T.to_excel(w, sheet_name="الهوية", header=["القيمة"])
                    if not df_stores.empty:  df_stores.to_excel(w, sheet_name="المتاجر", index=False)
                    if not df_stories.empty: df_stories.to_excel(w, sheet_name="الستوري", index=False)
                    if not df_recent.empty:  df_recent.to_excel(w, sheet_name="كل_الحركات", index=False)
                    # ── أوراق السجل التفصيلي (Migration 029 + V2) ──
                    for sheet_name, df_sheet in _ev_xlsx_sheets.items():
                        try:
                            # أسماء أوراق Excel محدودة 31 حرف
                            df_sheet.to_excel(w, sheet_name=sheet_name[:31], index=False)
                        except Exception:
                            pass
                st.download_button(
                    "📥 تصدير الكتاب الكامل لهذا الشخص (Excel)",
                    out.getvalue(),
                    f"profile_{name}_{date.today()}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="ua_dl_profile",
                )

        st.divider()

        st.divider()
        st.markdown("# 📊 تحليلات عامّة")
        st.caption("الأرقام الكبرى + العد الشامل + القوائم + التوقيت + الديموغرافيا + التحليل المتقدّم.")

        _main_tabs = st.tabs(["🎯 الأرقام الكبرى", "📊 العد الشامل", "📡 تفصيل القنوات", "🎯 قوائم القرار", "🕐 التوقيت", "👥 الديموغرافيا", "🎯 Audience Builder", "🎯 RFM", "🌀 Cohort", "📈 LTV", "🔻 Funnel", "🗺️ الجغرافيا", "🔔 Anomaly"])

        with _main_tabs[0]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_0",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 1 ─ KPIs الكبرى (موحّدة: ويب + بوت + ميني-ويب)
            # ════════════════════════════════════════════════════════════════
            st.markdown("### 🎯 الأرقام الكبرى")
            st.caption(
                f"عدد العملاء والنشاط في النطاق **{date_from.strftime('%Y-%m-%d')} → "
                f"{date_to.strftime('%Y-%m-%d')}** ({N} يوم) — قاعدة الحسابات لا تتأثر بفلتر المصدر."
            )

            kpis = pd.read_sql("""
                SELECT
                  (SELECT COUNT(*) FROM bot_users
                     WHERE deleted_at IS NULL)                                              AS bot_total,
                  (SELECT COUNT(*) FROM web_users)                                          AS web_total,
                  (SELECT COUNT(*) FROM bot_users
                     WHERE last_seen  >= %s AND last_seen  < %s
                       AND deleted_at IS NULL)                                              AS bot_active,
                  (SELECT COUNT(*) FROM web_users
                     WHERE last_seen  >= %s AND last_seen  < %s)                            AS web_active,
                  (SELECT COUNT(*) FROM bot_users
                     WHERE joined_at  >= %s AND joined_at  < %s
                       AND deleted_at IS NULL)                                              AS bot_new,
                  (SELECT COUNT(*) FROM web_users
                     WHERE created_at >= %s AND created_at < %s)                            AS web_new
            """, conn, params=(_t_from, _t_to, _t_from, _t_to, _t_from, _t_to, _t_from, _t_to))
            _r = kpis.iloc[0]
            bot_total  = int(_r["bot_total"]  or 0)
            web_total  = int(_r["web_total"]  or 0)
            bot_active = int(_r["bot_active"] or 0)
            web_active = int(_r["web_active"] or 0)
            bot_new    = int(_r["bot_new"]    or 0)
            web_new    = int(_r["web_new"]    or 0)

            grand_total  = bot_total + web_total
            grand_active = bot_active + web_active
            grand_new    = bot_new + web_new
            grand_idle   = grand_total - grand_active

            # نشاط مفلتر بالمصدر — نطاق زمني صريح
            _src_clause, _src_params = _ua_src_clause("al")
            _t_clause, _t_params = _ua_time_clause("al")
            act = pd.read_sql(f"""
                SELECT
                  COUNT(*) FILTER (WHERE action_type='copy_coupon') AS copies,
                  COUNT(*) FILTER (WHERE action_type='click_link')  AS clicks,
                  COUNT(*) FILTER (WHERE action_type='search')      AS searches,
                  COUNT(*) FILTER (WHERE action_type='start')       AS sessions,
                  COUNT(DISTINCT user_id) FILTER (WHERE action_type IN ('copy_coupon','click_link'))
                                                                    AS beneficiaries
                FROM action_logs al
                WHERE 1=1
                { _t_clause }
                { _src_clause }
            """, conn, params=tuple(_t_params + _src_params))
            copies        = int(act["copies"][0]        or 0)
            clicks        = int(act["clicks"][0]        or 0)
            searches      = int(act["searches"][0]      or 0)
            sessions      = int(act["sessions"][0]      or 0)
            beneficiaries = int(act["beneficiaries"][0] or 0)

            k1, k2, k3, k4 = st.columns(4)
            with k1: kpi_card("👥", "إجمالي العملاء", f"{grand_total:,}", "info",
                              note=f"🤖 بوت: {bot_total:,} · 🌐 موقع: {web_total:,}")
            with k2: kpi_card("🟢", "نشطون في النطاق", f"{grand_active:,}", "emerald",
                              note=f"🔴 خاملون: {grand_idle:,} · 🆕 جدد: {grand_new:,}")
            with k3: kpi_card("🎁", "المستفيدون فعلياً", f"{beneficiaries:,}", "warning",
                              note="نسخوا أو نقروا (يطبّق فلتر المصدر)")
            with k4: kpi_card("🎟️", "نسخ كوبونات", f"{copies:,}", "emerald",
                              note=f"🖱️ نقرات: {clicks:,} · 🔍 بحث: {searches:,} · 🚀 جلسات: {sessions:,}")

            st.info(
                "ℹ️ **فلتر المصدر** فوق التبويب: «الكل» يحسب كل القنوات معاً، أو "
                "اختر قناة محدّدة (بوت/موقع/ميني-ويب) لتفلتر **كل أرقام هذا التبويب**. "
                "كروت «إجمالي/نشط/خامل/جدد» لا تتأثر بالفلتر (مأخوذة من جداول الحسابات الكاملة)، "
                "أما «المستفيدون/نسخ/نقرات/بحث/جلسات» تتأثر."
            )

            # ════════════════════════════════════════════════════════════════
            # 🔍 تفصيل الكروت — مين هم بالاسم والإيميل والقناة والتواريخ
            # ════════════════════════════════════════════════════════════════
            st.markdown("#### 🔍 تفصيل الكروت — مين هم؟")
            st.caption("افتح أي قسم لرؤية الأسماء + الإيميل + الجوال + القناة + التواريخ + CSV.")

            # Source filter for miniapp: نحتاج subquery
            def _mini_users_subquery():
                return """telegram_id IN (
                    SELECT DISTINCT user_id FROM action_logs
                     WHERE source IN ('telegram_miniapp','miniapp') AND user_id IS NOT NULL
                )"""

            # ─── (١) إجمالي العملاء ─────────────────────────────────
            with st.expander(f"👥 إجمالي العملاء ({grand_total:,}) — مين هم بالقناة والتاريخ؟"):
                try: conn.rollback()
                except Exception: pass
                _q_bot = """
                    SELECT 'bot' AS source, telegram_id::text AS id,
                           username AS name, NULL::text AS email,
                           NULL::text AS phone, joined_at AS joined, last_seen
                      FROM bot_users WHERE deleted_at IS NULL
                """
                _q_web = """
                    SELECT 'web' AS source, id::text AS id,
                           display_name AS name, email AS email,
                           phone_number AS phone,
                           created_at AS joined, last_seen AS last_seen
                      FROM web_users
                """
                _q_mini = f"""
                    SELECT 'miniapp' AS source, telegram_id::text AS id,
                           username AS name, NULL::text AS email,
                           NULL::text AS phone, joined_at AS joined, last_seen
                      FROM bot_users
                     WHERE deleted_at IS NULL AND { _mini_users_subquery() }
                """
                if _src_tuple is None:
                    total_q = f"{_q_bot} UNION ALL {_q_web}"
                elif _src_tuple == ("bot",):
                    total_q = _q_bot
                elif _src_tuple == ("web",):
                    total_q = _q_web
                else:  # miniapp
                    total_q = _q_mini

                df_total = pd.read_sql(f"{total_q} ORDER BY joined DESC NULLS LAST", conn)
                if df_total.empty:
                    st.caption("لا عملاء في هذا الفلتر.")
                else:
                    df_total["المصدر"] = df_total["source"].map(_SRC_LABEL).fillna(df_total["source"])
                    df_total["تاريخ_الانضمام"] = pd.to_datetime(df_total["joined"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_total["آخر_ظهور"] = pd.to_datetime(df_total["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    show = df_total[["المصدر","id","name","email","phone","تاريخ_الانضمام","آخر_ظهور"]].rename(
                        columns={"id":"ID","name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=420)
                    st.caption(f"عرض {len(show):,} عميل — كله قابل للتنزيل.")
                    st.download_button(
                        "📥 CSV — إجمالي العملاء",
                        show.to_csv(index=False).encode("utf-8-sig"),
                        f"users_total_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_total_{_src_choice}",
                    )

            # ─── (٢) نشطون في النطاق ─────────────────────────────────
            with st.expander(f"🟢 نشطون في النطاق ({grand_active:,}) — مين تفاعل ومتى؟"):
                try: conn.rollback()
                except Exception: pass
                _q_bot_a = """
                    SELECT 'bot' AS source, telegram_id::text AS id, username AS name,
                           NULL::text AS email, NULL::text AS phone,
                           joined_at AS joined, last_seen
                      FROM bot_users
                     WHERE deleted_at IS NULL
                       AND last_seen >= %s AND last_seen < %s
                """
                _q_web_a = """
                    SELECT 'web' AS source, id::text AS id, display_name AS name,
                           email AS email, phone_number AS phone,
                           created_at AS joined, last_seen AS last_seen
                      FROM web_users
                     WHERE last_seen >= %s AND last_seen < %s
                """
                _q_mini_a = f"""
                    SELECT 'miniapp', telegram_id::text, username, NULL::text,
                           NULL::text, joined_at, last_seen
                      FROM bot_users
                     WHERE deleted_at IS NULL
                       AND last_seen >= %s AND last_seen < %s
                       AND { _mini_users_subquery() }
                """
                if _src_tuple is None:
                    q = f"{_q_bot_a} UNION ALL {_q_web_a}"
                    p = (_t_from, _t_to, _t_from, _t_to)
                elif _src_tuple == ("bot",):
                    q = _q_bot_a; p = (_t_from, _t_to)
                elif _src_tuple == ("web",):
                    q = _q_web_a; p = (_t_from, _t_to)
                else:
                    q = _q_mini_a; p = (_t_from, _t_to)

                df_act = pd.read_sql(f"{q} ORDER BY last_seen DESC NULLS LAST", conn, params=p)
                if df_act.empty:
                    st.caption("لا نشطين في النطاق المحدّد.")
                else:
                    df_act["المصدر"] = df_act["source"].map(_SRC_LABEL).fillna(df_act["source"])
                    df_act["تاريخ_الانضمام"] = pd.to_datetime(df_act["joined"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_act["آخر_ظهور"] = pd.to_datetime(df_act["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    show = df_act[["المصدر","id","name","email","phone","تاريخ_الانضمام","آخر_ظهور"]].rename(
                        columns={"id":"ID","name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=380)
                    st.download_button(
                        "📥 CSV — النشطين", show.to_csv(index=False).encode("utf-8-sig"),
                        f"users_active_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_active_{_src_choice}",
                    )

            # ─── (٣) خاملون ─────────────────────────────────────────
            with st.expander(f"🔴 خاملون ({grand_idle:,}) — آخر ظهور قبل النطاق"):
                try: conn.rollback()
                except Exception: pass
                _q_bot_i = """
                    SELECT 'bot' AS source, telegram_id::text AS id, username AS name,
                           NULL::text AS email, NULL::text AS phone,
                           joined_at AS joined, last_seen,
                           EXTRACT(EPOCH FROM (NOW() - last_seen))/86400.0 AS days_silent
                      FROM bot_users
                     WHERE deleted_at IS NULL
                       AND (last_seen IS NULL OR last_seen < %s)
                """
                _q_web_i = """
                    SELECT 'web' AS source, id::text AS id, display_name AS name,
                           email AS email, phone_number AS phone,
                           created_at AS joined, last_seen AS last_seen,
                           EXTRACT(EPOCH FROM (NOW() - last_seen))/86400.0 AS days_silent
                      FROM web_users
                     WHERE (last_seen IS NULL OR last_seen < %s)
                """
                _q_mini_i = f"""
                    SELECT 'miniapp', telegram_id::text, username, NULL::text,
                           NULL::text, joined_at, last_seen,
                           EXTRACT(EPOCH FROM (NOW() - last_seen))/86400.0
                      FROM bot_users
                     WHERE deleted_at IS NULL
                       AND (last_seen IS NULL OR last_seen < %s)
                       AND { _mini_users_subquery() }
                """
                if _src_tuple is None:
                    q = f"{_q_bot_i} UNION ALL {_q_web_i}"; p = (_t_from, _t_from)
                elif _src_tuple == ("bot",):
                    q = _q_bot_i; p = (_t_from,)
                elif _src_tuple == ("web",):
                    q = _q_web_i; p = (_t_from,)
                else:
                    q = _q_mini_i; p = (_t_from,)

                df_idle = pd.read_sql(f"{q} ORDER BY last_seen DESC NULLS LAST", conn, params=p)
                if df_idle.empty:
                    st.success("✨ لا خاملون — كل العملاء نشطون في النطاق.")
                else:
                    df_idle["المصدر"] = df_idle["source"].map(_SRC_LABEL).fillna(df_idle["source"])
                    df_idle["تاريخ_الانضمام"] = pd.to_datetime(df_idle["joined"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_idle["آخر_ظهور"] = pd.to_datetime(df_idle["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_idle["أيام_صمت"] = df_idle["days_silent"].fillna(9999).astype(float).round(0).astype(int)
                    show = df_idle[["المصدر","id","name","email","phone","تاريخ_الانضمام","آخر_ظهور","أيام_صمت"]].rename(
                        columns={"id":"ID","name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=380)
                    st.download_button(
                        "📥 CSV — الخاملون", show.to_csv(index=False).encode("utf-8-sig"),
                        f"users_idle_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_idle_{_src_choice}",
                    )

            # ─── (٤) جدد في النطاق ──────────────────────────────────
            with st.expander(f"🆕 جدد في النطاق ({grand_new:,}) — انضموا داخل التواريخ"):
                try: conn.rollback()
                except Exception: pass
                _q_bot_n = """
                    SELECT 'bot' AS source, telegram_id::text AS id, username AS name,
                           NULL::text AS email, NULL::text AS phone,
                           joined_at AS joined, last_seen
                      FROM bot_users
                     WHERE deleted_at IS NULL
                       AND joined_at >= %s AND joined_at < %s
                """
                _q_web_n = """
                    SELECT 'web' AS source, id::text AS id, display_name AS name,
                           email AS email, phone_number AS phone,
                           created_at AS joined, last_seen AS last_seen
                      FROM web_users
                     WHERE created_at >= %s AND created_at < %s
                """
                _q_mini_n = f"""
                    SELECT 'miniapp', telegram_id::text, username, NULL::text,
                           NULL::text, joined_at, last_seen
                      FROM bot_users
                     WHERE deleted_at IS NULL
                       AND joined_at >= %s AND joined_at < %s
                       AND { _mini_users_subquery() }
                """
                if _src_tuple is None:
                    q = f"{_q_bot_n} UNION ALL {_q_web_n}"; p = (_t_from, _t_to, _t_from, _t_to)
                elif _src_tuple == ("bot",):
                    q = _q_bot_n; p = (_t_from, _t_to)
                elif _src_tuple == ("web",):
                    q = _q_web_n; p = (_t_from, _t_to)
                else:
                    q = _q_mini_n; p = (_t_from, _t_to)

                df_new = pd.read_sql(f"{q} ORDER BY joined DESC", conn, params=p)
                if df_new.empty:
                    st.caption("لا عملاء جدد في النطاق.")
                else:
                    df_new["المصدر"] = df_new["source"].map(_SRC_LABEL).fillna(df_new["source"])
                    df_new["تاريخ_الانضمام"] = pd.to_datetime(df_new["joined"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_new["آخر_ظهور"] = pd.to_datetime(df_new["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    show = df_new[["المصدر","id","name","email","phone","تاريخ_الانضمام","آخر_ظهور"]].rename(
                        columns={"id":"ID","name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=380)
                    st.download_button(
                        "📥 CSV — جدد", show.to_csv(index=False).encode("utf-8-sig"),
                        f"users_new_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_new_{_src_choice}",
                    )

            # ─── (٥) المستفيدون فعلياً + ماذا فعلوا ─────────────────
            with st.expander(f"🎁 المستفيدون فعلياً ({beneficiaries:,}) — كيف صاروا مستفيدين؟"):
                try: conn.rollback()
                except Exception: pass
                _ben_src_clause, _ben_src_params = _ua_src_clause("al")
                df_ben = pd.read_sql(f"""
                    WITH agg AS (
                      SELECT
                        CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                        al.user_id,
                        COUNT(*) FILTER (WHERE al.action_type='copy_coupon')   AS copies,
                        COUNT(*) FILTER (WHERE al.action_type='click_link')    AS clicks,
                        COUNT(*) FILTER (WHERE al.action_type='search')        AS searches,
                        COUNT(DISTINCT al.store_id)
                          FILTER (WHERE al.action_type='copy_coupon')          AS uniq_stores,
                        MIN(al.action_time)                                    AS first_action,
                        MAX(al.action_time)                                    AS last_action
                      FROM action_logs al
                      WHERE al.action_time >= %s AND al.action_time < %s
                        AND al.user_id IS NOT NULL
                        AND al.action_type IN ('copy_coupon','click_link')
                        { _ben_src_clause }
                      GROUP BY src, al.user_id
                    )
                    SELECT a.src, a.user_id,
                           COALESCE(wu.display_name, bu.username, '—') AS name,
                           wu.email, wu.phone_number AS phone,
                           bu.username AS tg,
                           a.copies, a.clicks, a.searches, a.uniq_stores,
                           a.first_action, a.last_action
                      FROM agg a
                      LEFT JOIN web_users wu ON a.src='web' AND wu.id = a.user_id
                      LEFT JOIN bot_users bu ON a.src='bot' AND bu.telegram_id = a.user_id
                     ORDER BY a.copies DESC, a.clicks DESC
                """, conn, params=tuple([_t_from, _t_to] + _ben_src_params))
                if df_ben.empty:
                    st.caption("لا مستفيدين في هذا الفلتر/النطاق.")
                else:
                    df_ben["المصدر"]   = df_ben["src"].map({"web":"🌐 الموقع","bot":"🤖 البوت"}).fillna(df_ben["src"])
                    df_ben["تيليجرام"] = df_ben["tg"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    df_ben["أول_فعل"]  = pd.to_datetime(df_ben["first_action"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_ben["آخر_فعل"]  = pd.to_datetime(df_ben["last_action"],  errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    show = df_ben[["المصدر","name","email","phone","تيليجرام",
                                   "copies","clicks","searches","uniq_stores",
                                   "أول_فعل","آخر_فعل"]].rename(
                        columns={"name":"الاسم","email":"الإيميل","phone":"الجوال",
                                 "copies":"نسخ","clicks":"نقرات","searches":"بحث",
                                 "uniq_stores":"متاجر_فريدة"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=420)
                    st.caption(
                        f"📊 إجمالي المستفيدين: **{len(show):,}** — "
                        f"نسخوا {int(df_ben['copies'].sum()):,} كوبون · "
                        f"نقروا {int(df_ben['clicks'].sum()):,} رابط · "
                        f"بحثوا {int(df_ben['searches'].sum()):,} مرة."
                    )
                    st.download_button(
                        "📥 CSV — المستفيدون", show.to_csv(index=False).encode("utf-8-sig"),
                        f"users_beneficiaries_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_ben_{_src_choice}",
                    )

            st.divider()

        with _main_tabs[1]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_1",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 1.5 ─ العد الشامل: كل قناة + المربوطون
            # «المربوطون» = web_users.telegram_username يطابق bot_users.username
            # (العميل يدخل يوزر تيليجرام عند التسجيل بالموقع → نلتقطه أوتوماتيكياً)
            # ════════════════════════════════════════════════════════════════
            st.markdown("### 📊 العد الشامل — كم لكل قناة + المربوطون")
            st.caption(
                "«الموقع/البوت» من جداول الحسابات · «الميني-ويب» مستخدمون فريدون من action_logs · "
                "«المربوطون» = العميل ربط حسابه بإدخال يوزر تيليجرامه في الموقع (ضم أوتوماتيكي)."
            )

            try: conn.rollback()
            except Exception: pass

            # الميني-ويب: مستخدمون فريدون من action_logs
            mini_count = pd.read_sql("""
                SELECT COUNT(DISTINCT user_id)::int AS n
                FROM action_logs
                WHERE source IN ('telegram_miniapp', 'miniapp')
                  AND user_id IS NOT NULL
            """, conn)
            mini_total = int(mini_count["n"].iloc[0] or 0)

            # المربوطون: web_users.telegram_username يطابق bot_users.username
            linked = pd.read_sql("""
                SELECT COUNT(DISTINCT wu.id)::int AS n
                FROM web_users wu
                JOIN bot_users bu ON LOWER(bu.username) = LOWER(wu.telegram_username)
                WHERE wu.telegram_username IS NOT NULL
                  AND TRIM(wu.telegram_username) <> ''
                  AND bu.deleted_at IS NULL
            """, conn)
            linked_count = int(linked["n"].iloc[0] or 0)

            # ميني-ويب نشطون مربوطون أيضاً (subset)
            mini_linked = pd.read_sql("""
                SELECT COUNT(DISTINCT al.user_id)::int AS n
                FROM action_logs al
                JOIN bot_users bu ON bu.telegram_id = al.user_id
                JOIN web_users wu ON LOWER(wu.telegram_username) = LOWER(bu.username)
                WHERE al.source IN ('telegram_miniapp', 'miniapp')
                  AND wu.telegram_username IS NOT NULL
                  AND TRIM(wu.telegram_username) <> ''
            """, conn)
            mini_linked_count = int(mini_linked["n"].iloc[0] or 0)

            web_only_count = max(0, web_total - linked_count)
            bot_only_count = max(0, bot_total - linked_count)
            grand_unique   = web_only_count + bot_only_count + linked_count
            link_pct       = (linked_count * 100.0 / web_total) if web_total else 0.0

            g1, g2, g3, g4 = st.columns(4)
            with g1:
                kpi_card("🤖", "البوت — إجمالي", f"{bot_total:,}", "info",
                         note=f"بدون ربط: {bot_only_count:,}")
            with g2:
                kpi_card("🌐", "الموقع — إجمالي", f"{web_total:,}", "info",
                         note=f"بدون ربط: {web_only_count:,}")
            with g3:
                kpi_card("🔹", "الميني-ويب — مستخدمون فعليون", f"{mini_total:,}", "warning",
                         note=f"مربوطون: {mini_linked_count:,}")
            with g4:
                kpi_card("🔗", "مربوطون (ويب ↔ تيليجرام)", f"{linked_count:,}", "emerald",
                         note=f"{link_pct:.1f}% من الويب · ضم أوتوماتيكي")

            gT1, gT2 = st.columns([1, 2])
            with gT1:
                kpi_card("🧮", "الإجمالي الفريد (بعد الضم)", f"{grand_unique:,}", "danger",
                         note="ويب فقط + بوت فقط + المربوطون (مرة واحدة)")
            with gT2:
                pie_data = pd.DataFrame([
                    {"الفئة": "🌐 ويب فقط",        "العدد": web_only_count},
                    {"الفئة": "🤖 بوت فقط",        "العدد": bot_only_count},
                    {"الفئة": "🔗 ويب + تيليجرام", "العدد": linked_count},
                ])
                if int(pie_data["العدد"].sum()) > 0:
                    fig_seg = px.pie(pie_data, names="الفئة", values="العدد", hole=0.5,
                                     color_discrete_sequence=["#3B82F6","#F59E0B","#10B981"],
                                     title="تركيب القاعدة الفريدة")
                    st.plotly_chart(apply_brand_theme(fig_seg), use_container_width=True)

            # ─── drill-downs لكل كارت ─────────────────────────────────
            st.markdown("#### 🔍 تفصيل الكروت — مين هم؟")

            with st.expander(f"🤖 البوت ({bot_total:,}) — كل بوت يوزر بالاسم والتاريخ"):
                try: conn.rollback()
                except Exception: pass
                df_b = pd.read_sql("""
                    SELECT telegram_id::text AS ID, username AS الاسم,
                           city AS المدينة, lang AS اللغة,
                           joined_at AS تاريخ_الانضمام,
                           last_seen AS آخر_ظهور
                      FROM bot_users
                     WHERE deleted_at IS NULL
                     ORDER BY joined_at DESC NULLS LAST
                """, conn)
                if df_b.empty:
                    st.caption("لا بوت يوزرز.")
                else:
                    df_b["الاسم"] = df_b["الاسم"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    df_b["تاريخ_الانضمام"] = pd.to_datetime(df_b["تاريخ_الانضمام"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_b["آخر_ظهور"] = pd.to_datetime(df_b["آخر_ظهور"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_b = df_b.fillna("—")
                    st.dataframe(df_b, use_container_width=True, hide_index=True, height=380)
                    st.download_button("📥 CSV — بوت", df_b.to_csv(index=False).encode("utf-8-sig"),
                                       f"bot_users_{date.today()}.csv", "text/csv", key="ua_dl_bot_list")

            with st.expander(f"🌐 الموقع ({web_total:,}) — كل ويب يوزر بالاسم والتاريخ"):
                try: conn.rollback()
                except Exception: pass
                df_w = pd.read_sql("""
                    SELECT id::text AS ID, display_name AS الاسم, email AS الإيميل,
                           phone_number AS الجوال,
                           telegram_username AS تيليجرام,
                           city AS المدينة, lang AS اللغة,
                           created_at AS تاريخ_الانضمام,
                           last_seen AS آخر_ظهور
                      FROM web_users
                     ORDER BY created_at DESC NULLS LAST
                """, conn)
                if df_w.empty:
                    st.caption("لا ويب يوزرز.")
                else:
                    df_w["تيليجرام"] = df_w["تيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    df_w["تاريخ_الانضمام"] = pd.to_datetime(df_w["تاريخ_الانضمام"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_w["آخر_ظهور"] = pd.to_datetime(df_w["آخر_ظهور"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_w = df_w.fillna("—")
                    st.dataframe(df_w, use_container_width=True, hide_index=True, height=380)
                    st.download_button("📥 CSV — موقع", df_w.to_csv(index=False).encode("utf-8-sig"),
                                       f"web_users_{date.today()}.csv", "text/csv", key="ua_dl_web_list")

            with st.expander(f"🔹 الميني-ويب ({mini_total:,}) — مين فتح الميني فعلاً"):
                try: conn.rollback()
                except Exception: pass
                df_m = pd.read_sql("""
                    SELECT bu.telegram_id::text AS ID, bu.username AS الاسم,
                           bu.city AS المدينة, bu.lang AS اللغة,
                           bu.joined_at AS تاريخ_الانضمام,
                           bu.last_seen AS آخر_ظهور,
                           COUNT(al.id)::int AS عدد_حركات_الميني
                      FROM bot_users bu
                      JOIN action_logs al ON al.user_id = bu.telegram_id
                                         AND al.source IN ('telegram_miniapp','miniapp')
                     WHERE bu.deleted_at IS NULL
                     GROUP BY bu.telegram_id, bu.username, bu.city, bu.lang,
                              bu.joined_at, bu.last_seen
                     ORDER BY عدد_حركات_الميني DESC
                """, conn)
                if df_m.empty:
                    st.caption("لا أحد فتح الميني-ويب بعد.")
                else:
                    df_m["الاسم"] = df_m["الاسم"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    df_m["تاريخ_الانضمام"] = pd.to_datetime(df_m["تاريخ_الانضمام"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_m["آخر_ظهور"] = pd.to_datetime(df_m["آخر_ظهور"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_m = df_m.fillna("—")
                    st.dataframe(df_m, use_container_width=True, hide_index=True, height=380)
                    st.download_button("📥 CSV — ميني-ويب", df_m.to_csv(index=False).encode("utf-8-sig"),
                                       f"miniapp_users_{date.today()}.csv", "text/csv", key="ua_dl_mini_list")

            with st.expander(f"🔗 المربوطون ({linked_count:,}) — ويب وتيليجرام نفس الشخص"):
                try: conn.rollback()
                except Exception: pass
                df_l = pd.read_sql("""
                    SELECT wu.id::text AS Web_ID,
                           bu.telegram_id::text AS Telegram_ID,
                           wu.display_name AS الاسم_بالموقع,
                           bu.username AS التيليجرام,
                           wu.email AS الإيميل, wu.phone_number AS الجوال,
                           COALESCE(wu.city, bu.city) AS المدينة,
                           wu.created_at AS تسجيل_الموقع,
                           bu.joined_at AS انضمام_البوت,
                           GREATEST(
                               COALESCE(wu.last_seen, '1970-01-01'::timestamptz),
                               COALESCE(bu.last_seen, '1970-01-01'::timestamptz)
                           ) AS آخر_ظهور_موحّد
                      FROM web_users wu
                      JOIN bot_users bu ON LOWER(bu.username) = LOWER(wu.telegram_username)
                     WHERE wu.telegram_username IS NOT NULL
                       AND TRIM(wu.telegram_username) <> ''
                       AND bu.deleted_at IS NULL
                     ORDER BY آخر_ظهور_موحّد DESC NULLS LAST
                """, conn)
                if df_l.empty:
                    st.caption("لا مربوطين بعد. شجّع العملاء يضيفون يوزر تيليجرام في الموقع.")
                else:
                    df_l["التيليجرام"] = df_l["التيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    df_l["تسجيل_الموقع"] = pd.to_datetime(df_l["تسجيل_الموقع"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_l["انضمام_البوت"] = pd.to_datetime(df_l["انضمام_البوت"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_l["آخر_ظهور_موحّد"] = pd.to_datetime(df_l["آخر_ظهور_موحّد"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    df_l = df_l.fillna("—")
                    st.dataframe(df_l, use_container_width=True, hide_index=True, height=380)
                    st.download_button("📥 CSV — المربوطون", df_l.to_csv(index=False).encode("utf-8-sig"),
                                       f"linked_users_{date.today()}.csv", "text/csv", key="ua_dl_linked_list")

            st.divider()

        with _main_tabs[2]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_2",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 2 ─ تفصيل لكل قناة (مقارنة جنباً إلى جنب)
            # ════════════════════════════════════════════════════════════════
            st.markdown("### 📡 تفصيل لكل قناة")
            st.caption("«العملاء/نشط/جدد» من جداول الحسابات · «نسخ/نقرات/بحث/جلسات» من action_logs · «المدن» = أعلى ٣ مدن بالنشاط · «المفضلة» من user_favorites.")

            per_src_acts = pd.read_sql("""
                SELECT
                  COALESCE(source, 'bot') AS source,
                  COUNT(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) AS users_engaged,
                  COUNT(*) FILTER (WHERE action_type='copy_coupon') AS copies,
                  COUNT(*) FILTER (WHERE action_type='click_link')  AS clicks,
                  COUNT(*) FILTER (WHERE action_type='search')      AS searches,
                  COUNT(*) FILTER (WHERE action_type='start')       AS sessions,
                  COUNT(*)                                          AS total_actions
                FROM action_logs
                WHERE action_time >= %s AND action_time < %s
                GROUP BY source
            """, conn, params=(_t_from, _t_to))

            # المدن لكل قناة — أعلى 3 أسماء فعلية (لا عدد فقط)
            try: conn.rollback()
            except Exception: pass
            # المدينة fallback: لو action_logs.city فاضي (الميني-ويب غالباً)
            # نستخدم مدينة المستخدم من ملفه (bot_users/web_users).
            _city_chan = f"""COALESCE(
                NULLIF(TRIM(al.city),''),
                NULLIF(TRIM(bu.city),''),
                NULLIF(TRIM(wu.city),'')
            )"""
            cities_per_src = pd.read_sql(f"""
                WITH events AS (
                  SELECT
                    COALESCE(al.source,'bot') AS source,
                    { _norm_city_sql(_city_chan) } AS city
                  FROM action_logs al
                  LEFT JOIN bot_users bu
                         ON bu.telegram_id = al.user_id
                        AND COALESCE(al.source,'bot') IN ('bot','telegram_miniapp','miniapp')
                  LEFT JOIN web_users wu
                         ON wu.id = al.user_id
                        AND al.source = 'web'
                  WHERE al.action_time >= %s AND al.action_time < %s
                    AND al.user_id IS NOT NULL
                ),
                cnt AS (
                  SELECT source, city, COUNT(*)::int AS n
                  FROM events
                  WHERE city IS NOT NULL AND TRIM(city) <> ''
                  GROUP BY 1, 2
                ),
                ranked AS (
                  SELECT source, city, n,
                         ROW_NUMBER() OVER (PARTITION BY source ORDER BY n DESC) AS rk
                  FROM cnt
                )
                SELECT source, STRING_AGG(city || ' (' || n || ')', ' · ' ORDER BY n DESC) AS top_cities
                  FROM ranked
                 WHERE rk <= 3
                 GROUP BY source
            """, conn, params=(_t_from, _t_to))
            per_src_acts["lbl"] = per_src_acts["source"].map(_SRC_LABEL).fillna(per_src_acts["source"])
            per_src_view = (per_src_acts.groupby("lbl", as_index=False)
                            .agg(users_engaged=("users_engaged","sum"),
                                 copies=("copies","sum"), clicks=("clicks","sum"),
                                 searches=("searches","sum"), sessions=("sessions","sum"),
                                 total_actions=("total_actions","sum")))
            # المدن: ندمج top_cities لكل lbl
            cities_per_src["lbl"] = cities_per_src["source"].map(_SRC_LABEL).fillna(cities_per_src["source"])
            cities_view = (cities_per_src.groupby("lbl", as_index=False)
                              .agg(أعلى_المدن=("top_cities",
                                    lambda s: " · ".join(sorted(set(filter(None, s)))) or "—")))

            # المفضّلات لكل قناة (متاجر + أقسام) — من جدول user_favorites
            try: conn.rollback()
            except Exception: pass
            favs_by_src = pd.read_sql("""
                SELECT
                  platform,
                  kind,
                  COUNT(*)::int AS n
                FROM user_favorites
                WHERE platform IS NOT NULL
                GROUP BY platform, kind
            """, conn)
            _PLAT_TO_LBL = {
                "web":              "🌐 الموقع",
                "bot":              "🤖 البوت",
                "telegram_miniapp": "🔹 الميني-ويب",
                "miniapp":          "🔹 الميني-ويب",
            }
            favs_by_src["lbl"] = favs_by_src["platform"].map(_PLAT_TO_LBL).fillna(favs_by_src["platform"])
            fav_store_per_src = (favs_by_src[favs_by_src["kind"]=="store"]
                                 .groupby("lbl", as_index=False)["n"].sum()
                                 .rename(columns={"n":"مفضلة_متاجر"}))
            fav_cat_per_src   = (favs_by_src[favs_by_src["kind"]=="category"]
                                 .groupby("lbl", as_index=False)["n"].sum()
                                 .rename(columns={"n":"مفضلة_أقسام"}))

            # دمج مع أعداد القاعدة + المفضّلات + المدن
            base_rows = [
                {"lbl": "🤖 البوت",       "العملاء": bot_total, "نشط": bot_active, "جدد": bot_new},
                {"lbl": "🌐 الموقع",      "العملاء": web_total, "نشط": web_active, "جدد": web_new},
                {"lbl": "🔹 الميني-ويب",  "العملاء": 0,         "نشط": 0,          "جدد": 0},
            ]
            # ميني-ويب يشترك في bot_users؛ نعرضه 0 في «القاعدة» لكن النشاط مستقل من action_logs
            base_df = pd.DataFrame(base_rows)
            full_compare = (base_df.merge(per_src_view, on="lbl", how="left")
                                  .merge(cities_view, on="lbl", how="left")
                                  .merge(fav_store_per_src, on="lbl", how="left")
                                  .merge(fav_cat_per_src,   on="lbl", how="left")
                                  .fillna({"users_engaged":0,"copies":0,"clicks":0,"searches":0,
                                           "sessions":0,"total_actions":0,
                                           "أعلى_المدن":"—","مفضلة_متاجر":0,"مفضلة_أقسام":0}))
            full_compare = full_compare.rename(columns={
                "lbl":"المصدر", "users_engaged":"عملاء_متفاعلون",
                "copies":"نسخ", "clicks":"نقرات", "searches":"بحث",
                "sessions":"جلسات", "total_actions":"إجمالي_الحركات",
            })
            for c in ["العملاء","نشط","جدد","عملاء_متفاعلون","نسخ","نقرات","بحث","جلسات",
                      "إجمالي_الحركات","مفضلة_متاجر","مفضلة_أقسام"]:
                if c in full_compare.columns:
                    full_compare[c] = full_compare[c].astype(int)
            # ترتيب الأعمدة — المدن كنص ظاهر
            ordered = ["المصدر","العملاء","نشط","جدد","عملاء_متفاعلون",
                       "نسخ","نقرات","بحث","جلسات","إجمالي_الحركات",
                       "أعلى_المدن","مفضلة_متاجر","مفضلة_أقسام"]
            full_compare = full_compare[[c for c in ordered if c in full_compare.columns]]
            st.dataframe(full_compare, use_container_width=True, hide_index=True)

            # ─── drill-down: مين أحدث هذه الأرقام لكل قناة ───────────
            st.markdown("#### 🔍 مين أحدث هذه الأرقام؟ — التفصيل لكل قناة")

            def _channel_users_expander(label, sources_tuple, key_suffix):
                """Render expander with users who acted in this channel during the date range."""
                ph = ",".join(["%s"] * len(sources_tuple))
                with st.expander(f"{label} — كل المستخدم وتفاصيل تفاعله"):
                    try: conn.rollback()
                    except Exception: pass
                    df_ch = pd.read_sql(f"""
                        WITH agg AS (
                          SELECT
                            CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src_norm,
                            al.user_id,
                            COUNT(*) FILTER (WHERE al.action_type='copy_coupon')  AS نسخ,
                            COUNT(*) FILTER (WHERE al.action_type='click_link')   AS نقرات,
                            COUNT(*) FILTER (WHERE al.action_type='search')       AS بحث,
                            COUNT(*) FILTER (WHERE al.action_type='start')        AS جلسات,
                            COUNT(*) AS إجمالي_الحركات,
                            MIN(al.action_time) AS first_act,
                            MAX(al.action_time) AS last_act
                          FROM action_logs al
                          WHERE al.source IN ({ph})
                            AND al.action_time >= %s AND al.action_time < %s
                            AND al.user_id IS NOT NULL
                          GROUP BY src_norm, al.user_id
                        )
                        SELECT a.user_id,
                               COALESCE(wu.display_name, bu.username, '—') AS الاسم,
                               wu.email AS الإيميل, wu.phone_number AS الجوال,
                               bu.username AS التيليجرام,
                               COALESCE(wu.city, bu.city) AS المدينة,
                               a.نسخ, a.نقرات, a.بحث, a.جلسات, a.إجمالي_الحركات,
                               a.first_act, a.last_act
                          FROM agg a
                          LEFT JOIN web_users wu ON a.src_norm='web' AND wu.id = a.user_id
                          LEFT JOIN bot_users bu ON a.src_norm='bot' AND bu.telegram_id = a.user_id
                         ORDER BY a.إجمالي_الحركات DESC
                    """, conn, params=tuple(list(sources_tuple) + [_t_from, _t_to]))
                    if df_ch.empty:
                        st.caption(f"لا تفاعلات في {label} داخل النطاق.")
                    else:
                        df_ch["التيليجرام"] = df_ch["التيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                        df_ch["أول_فعل"] = pd.to_datetime(df_ch["first_act"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                        df_ch["آخر_فعل"] = pd.to_datetime(df_ch["last_act"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                        show = df_ch[["الاسم","الإيميل","الجوال","التيليجرام","المدينة",
                                      "نسخ","نقرات","بحث","جلسات","إجمالي_الحركات",
                                      "أول_فعل","آخر_فعل"]].fillna("—")
                        st.dataframe(show, use_container_width=True, hide_index=True, height=380)
                        st.caption(f"📊 {len(show):,} مستخدم تفاعل من {label}")
                        st.download_button(
                            f"📥 CSV — {label}",
                            show.to_csv(index=False).encode("utf-8-sig"),
                            f"channel_{key_suffix}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_ch_{key_suffix}",
                        )

            _channel_users_expander("🤖 البوت", ("bot",), "bot")
            _channel_users_expander("🌐 الموقع", ("web",), "web")
            _channel_users_expander("🔹 الميني-ويب", ("telegram_miniapp", "miniapp"), "mini")

            st.divider()

        with _main_tabs[3]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_3",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 3 ─ قوائم القرار (Churn / Welcome / VIP)
            # ════════════════════════════════════════════════════════════════
            st.markdown("### 🎯 قوائم القرار — جاهزة للتنفيذ")
            st.caption("3 شرائح حيّة: حدّد، صدّر CSV، أرسل broadcast.")

            try: conn.rollback()
            except Exception: pass

            churn = pd.read_sql("""
                SELECT 'bot' AS source, telegram_id AS user_id, username AS name,
                       NULL::text AS email, NULL::text AS phone, last_seen
                  FROM bot_users
                 WHERE last_seen BETWEEN NOW() - INTERVAL '30 days' AND NOW() - INTERVAL '7 days'
                   AND deleted_at IS NULL
                UNION ALL
                SELECT 'web', id, display_name, email, phone_number, last_seen
                  FROM web_users
                 WHERE last_seen BETWEEN NOW() - INTERVAL '30 days' AND NOW() - INTERVAL '7 days'
                ORDER BY last_seen DESC
            """, conn)

            welcome = pd.read_sql("""
                WITH nb AS (
                  SELECT 'bot' AS source, b.telegram_id AS user_id, b.username AS name,
                         NULL::text AS email, NULL::text AS phone, b.joined_at AS joined
                    FROM bot_users b
                   WHERE b.joined_at >= NOW() - INTERVAL '7 days'
                     AND b.deleted_at IS NULL
                     AND NOT EXISTS (
                        SELECT 1 FROM action_logs a
                         WHERE a.user_id = b.telegram_id
                           AND a.action_type IN ('copy_coupon','click_link','search')
                     )
                ),
                nw AS (
                  SELECT 'web', w.id, w.display_name, w.email, w.phone_number, w.created_at
                    FROM web_users w
                   WHERE w.created_at >= NOW() - INTERVAL '7 days'
                     AND NOT EXISTS (
                        SELECT 1 FROM action_logs a
                         WHERE a.user_id = w.id
                           AND a.action_type IN ('copy_coupon','click_link','search')
                     )
                )
                SELECT * FROM nb
                UNION ALL
                SELECT * FROM nw
                ORDER BY joined DESC
            """, conn)

            vip = pd.read_sql(f"""
                WITH rk AS (
                  SELECT a.user_id,
                         CASE WHEN a.source='web' THEN 'web' ELSE 'bot' END AS src_norm,
                         COUNT(*) FILTER (WHERE a.action_type='copy_coupon') AS copies
                    FROM action_logs a
                   WHERE a.action_time >= '{_t_from}' AND a.action_time < '{_t_to}'
                     AND a.user_id IS NOT NULL
                   GROUP BY a.user_id, src_norm
                  HAVING COUNT(*) FILTER (WHERE a.action_type='copy_coupon') > 0
                ),
                ranked AS (
                  SELECT *, NTILE(20) OVER (ORDER BY copies DESC) AS bucket FROM rk
                )
                SELECT r.user_id, r.src_norm AS source, r.copies,
                       COALESCE(wu.display_name, bu.username, '—') AS name,
                       wu.email, wu.phone_number AS phone
                  FROM ranked r
             LEFT JOIN web_users wu ON r.src_norm='web' AND wu.id = r.user_id
             LEFT JOIN bot_users bu ON r.src_norm='bot' AND bu.telegram_id = r.user_id
                 WHERE r.bucket = 1
                 ORDER BY r.copies DESC
                 LIMIT 100
            """, conn)

            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown(f"#### ⚠️ على وشك الفقد · **{len(churn)}**")
                st.caption("نشط قبل 7-30 يوم · صامت آخر 7 → broadcast إعادة تنشيط.")
                if churn.empty:
                    st.success("لا أحد على وشك الفقد 🎉")
                else:
                    cv = churn.copy()
                    cv["المصدر"] = cv["source"].map(_SRC_LABEL).fillna(cv["source"])
                    cv["آخر ظهور"] = pd.to_datetime(cv["last_seen"]).dt.strftime("%Y-%m-%d")
                    show = cv[["المصدر","name","email","phone","آخر ظهور"]].rename(
                        columns={"name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=240)
                    st.download_button("📥 CSV (Churn)",
                                       show.to_csv(index=False).encode("utf-8-sig"),
                                       f"churn_risk_{date.today()}.csv", "text/csv",
                                       key="ua_dl_churn")
            with a2:
                st.markdown(f"#### ✨ جدد بدون نشاط · **{len(welcome)}**")
                st.caption("سجّلوا آخر 7 أيام · صفر تفاعل → onboarding broadcast.")
                if welcome.empty:
                    st.success("كل الجدد بدأوا تفاعلهم 👏")
                else:
                    wv = welcome.copy()
                    wv["المصدر"] = wv["source"].map(_SRC_LABEL).fillna(wv["source"])
                    wv["انضم"] = pd.to_datetime(wv["joined"]).dt.strftime("%Y-%m-%d")
                    show = wv[["المصدر","name","email","phone","انضم"]].rename(
                        columns={"name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=240)
                    st.download_button("📥 CSV (Welcome)",
                                       show.to_csv(index=False).encode("utf-8-sig"),
                                       f"welcome_{date.today()}.csv", "text/csv",
                                       key="ua_dl_welcome")
            with a3:
                st.markdown(f"#### 🏆 VIPs (أعلى 5%) · **{len(vip)}**")
                st.caption(f"أكثر النسخات في النطاق {date_from.strftime('%Y-%m-%d')} → {date_to.strftime('%Y-%m-%d')} → عرض حصري.")
                if vip.empty:
                    st.info("لا أحد نسخ في هذا النطاق بعد.")
                else:
                    vv = vip.copy()
                    vv["المصدر"] = vv["source"].map(_SRC_LABEL).fillna(vv["source"])
                    show = vv[["المصدر","name","copies","email","phone"]].rename(
                        columns={"name":"الاسم","copies":"نسخ","email":"الإيميل","phone":"الجوال"}).fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=240)
                    st.download_button("📥 CSV (VIPs)",
                                       show.to_csv(index=False).encode("utf-8-sig"),
                                       f"vips_{date.today()}.csv", "text/csv",
                                       key="ua_dl_vip")

            st.divider()

        with _main_tabs[4]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_4",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 4 ─ Heatmap: متى الجمهور موجود؟ (24 ساعة × 7 أيام)
            # ════════════════════════════════════════════════════════════════
            st.markdown("### 🕐 متى يكون الجمهور موجوداً؟")
            st.caption(f"خط النشاط بالساعة (٠–٢٣) في النطاق المحدّد — الذروة = أفضل وقت للـ broadcast.")

            # نُعيد حساب فلتر المصدر/الزمن محلياً (التبويب له فلتر مستقل)
            _src_clause, _src_params = _ua_src_clause("al")
            _t_clause, _t_params = _ua_time_clause("al")

            try: conn.rollback()
            except Exception: pass

            df_hot = pd.read_sql(f"""
                SELECT
                  EXTRACT(DOW  FROM action_time)::int AS dow,
                  EXTRACT(HOUR FROM action_time)::int AS hour,
                  COUNT(*) AS cnt
                FROM action_logs al
                WHERE 1=1
                { _t_clause }
                { _src_clause }
                GROUP BY dow, hour
            """, conn, params=tuple(_t_params + _src_params))

            if df_hot.empty:
                st.info("📭 لا توجد بيانات نشاط في هذا النطاق.")
            else:
                dow_ar = {0:"الأحد",1:"الإثنين",2:"الثلاثاء",3:"الأربعاء",
                          4:"الخميس",5:"الجمعة",6:"السبت"}
                df_hot["اليوم"] = df_hot["dow"].map(dow_ar)

                # تابز: إجمالي اليوم · لكل يوم على حدة (خطوط واضحة بدل heatmap)
                tab_total, tab_perday = st.tabs(["📈 إجمالي النشاط بالساعة", "📅 لكل يوم على حدة"])

                with tab_total:
                    df_hour = (df_hot.groupby("hour", as_index=False)["cnt"].sum()
                                     .rename(columns={"hour":"الساعة","cnt":"النشاط"}))
                    # نملأ الـ 24 ساعة كلها لخط مستمر
                    all_hours = pd.DataFrame({"الساعة": list(range(24))})
                    df_hour = all_hours.merge(df_hour, on="الساعة", how="left").fillna(0)
                    df_hour["النشاط"] = df_hour["النشاط"].astype(int)
                    peak_h = int(df_hour.loc[df_hour["النشاط"].idxmax(), "الساعة"]) if df_hour["النشاط"].sum() > 0 else 0
                    fig_total = px.line(df_hour, x="الساعة", y="النشاط", markers=True,
                                        title=f"إجمالي النشاط بالساعة — الذروة: {peak_h:02d}:00")
                    fig_total.update_traces(line=dict(width=3, color="#10B981"),
                                            marker=dict(size=8, color="#10B981"))
                    fig_total.update_xaxes(dtick=1, tickformat="d")
                    st.plotly_chart(apply_brand_theme(fig_total), use_container_width=True)

                with tab_perday:
                    # خط لكل يوم — 7 خطوط ملوّنة
                    df_perday = (df_hot.groupby(["اليوم","hour"], as_index=False)["cnt"].sum()
                                       .rename(columns={"hour":"الساعة","cnt":"النشاط"}))
                    # نملأ كل (يوم, ساعة) — لو ما في بيانات نضع 0
                    all_combos = pd.MultiIndex.from_product(
                        [list(dow_ar.values()), list(range(24))],
                        names=["اليوم","الساعة"],
                    ).to_frame(index=False)
                    df_perday = all_combos.merge(df_perday, on=["اليوم","الساعة"], how="left").fillna(0)
                    df_perday["النشاط"] = df_perday["النشاط"].astype(int)
                    day_order = ["السبت","الأحد","الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة"]
                    fig_perday = px.line(df_perday, x="الساعة", y="النشاط", color="اليوم",
                                         markers=True, category_orders={"اليوم": day_order},
                                         title="النشاط بالساعة — منفصل لكل يوم")
                    fig_perday.update_xaxes(dtick=1, tickformat="d")
                    st.plotly_chart(apply_brand_theme(fig_perday), use_container_width=True)

                # ─── drill-down: مين النشط بالساعة المختارة ───────
                st.markdown("#### 🔍 مين النشط في ساعة محدّدة؟")
                st.caption(f"ساعة الذروة الافتراضية: **{peak_h:02d}:00**. اختر ساعة لرؤية الأشخاص.")
                pick_hour = st.slider("⏰ الساعة:", 0, 23, peak_h, key=f"ua_hour_pick_{_src_choice}")
                try: conn.rollback()
                except Exception: pass
                df_h_users = pd.read_sql(f"""
                    WITH at_hour AS (
                      SELECT DISTINCT
                        CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                        al.user_id,
                        COUNT(*) AS عدد_الحركات,
                        MAX(al.action_time) AS last_act
                      FROM action_logs al
                      WHERE al.action_time >= %s AND al.action_time < %s
                        AND EXTRACT(HOUR FROM al.action_time)::int = %s
                        AND al.user_id IS NOT NULL
                        { _src_clause }
                      GROUP BY src, al.user_id
                    )
                    SELECT a.src AS source,
                           COALESCE(wu.display_name, bu.username, '—') AS الاسم,
                           wu.email AS الإيميل, wu.phone_number AS الجوال,
                           bu.username AS التيليجرام,
                           a.عدد_الحركات, a.last_act
                      FROM at_hour a
                      LEFT JOIN web_users wu ON a.src='web' AND wu.id = a.user_id
                      LEFT JOIN bot_users bu ON a.src='bot' AND bu.telegram_id = a.user_id
                     ORDER BY a.عدد_الحركات DESC
                """, conn, params=tuple([_t_from, _t_to, int(pick_hour)] + _src_params))
                if df_h_users.empty:
                    st.caption(f"لا أحد نشط بالساعة {pick_hour:02d}:00 في النطاق.")
                else:
                    df_h_users["المصدر"] = df_h_users["source"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                    df_h_users["التيليجرام"] = df_h_users["التيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    df_h_users["آخر_فعل"] = pd.to_datetime(df_h_users["last_act"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                    show = df_h_users[["المصدر","الاسم","الإيميل","الجوال","التيليجرام",
                                       "عدد_الحركات","آخر_فعل"]].fillna("—")
                    st.dataframe(show, use_container_width=True, hide_index=True, height=320)
                    st.caption(f"📊 {len(show):,} شخص نشط بالساعة {pick_hour:02d}:00 — مرشّحون لـ broadcast بهذا الوقت.")
                    st.download_button(
                        f"📥 CSV — نشط بـ {pick_hour:02d}:00",
                        show.to_csv(index=False).encode("utf-8-sig"),
                        f"active_hour_{pick_hour}_{date.today()}.csv", "text/csv",
                        key=f"ua_dl_hour_{pick_hour}_{_src_choice}",
                    )

            st.divider()

        with _main_tabs[5]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_5",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 5 ─ ديموغرافيا موحّدة (web + bot)
            # ════════════════════════════════════════════════════════════════
            st.markdown("### 👥 الديموغرافيا الموحّدة")
            st.caption("الجنس + الفئة العمرية + المدينة من قاعدتي web_users و bot_users معاً.")

            try: conn.rollback()
            except Exception: pass

            # نتحقّق أولاً من توفّر الأعمدة (gender / birth_date) قبل أي استعلام —
            # ميجريشن 024/025 قد لا تكون مطبّقة على القاعدة، فنتعامل بأمان.
            cols_check = pd.read_sql("""
                SELECT
                  MAX(CASE WHEN table_name='web_users' AND column_name='gender'     THEN 1 ELSE 0 END) AS web_g,
                  MAX(CASE WHEN table_name='bot_users' AND column_name='gender'     THEN 1 ELSE 0 END) AS bot_g,
                  MAX(CASE WHEN table_name='web_users' AND column_name='birth_date' THEN 1 ELSE 0 END) AS web_b,
                  MAX(CASE WHEN table_name='bot_users' AND column_name='birth_date' THEN 1 ELSE 0 END) AS bot_b
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('web_users','bot_users')
            """, conn)
            _has_web_gender = bool(int(cols_check["web_g"].iloc[0] or 0))
            _has_bot_gender = bool(int(cols_check["bot_g"].iloc[0] or 0))
            _has_web_birth  = bool(int(cols_check["web_b"].iloc[0] or 0))
            _has_bot_birth  = bool(int(cols_check["bot_b"].iloc[0] or 0))
            _has_gender     = _has_web_gender or _has_bot_gender
            _has_birth      = _has_web_birth  or _has_bot_birth

            if not (_has_gender and _has_birth):
                st.warning(
                    "⚠️ بعض أعمدة الديموغرافيا (gender / birth_date) غير موجودة. "
                    "طبّق `migration_024_user_demographics.sql` + `migration_025_bot_users_demographics.sql` لرؤية كامل التحليلات."
                )

            d1, d2, d3 = st.columns(3)

            # ── الجنس ──
            with d1:
                if _has_gender:
                    try: conn.rollback()
                    except Exception: pass
                    try:
                        gender_parts = []
                        if _has_web_gender:
                            gender_parts.append(
                                "SELECT CASE gender WHEN 'male' THEN 'ذكر' WHEN 'female' THEN 'أنثى' END AS g, "
                                "COUNT(*) AS c FROM web_users WHERE gender IS NOT NULL GROUP BY gender"
                            )
                        if _has_bot_gender:
                            gender_parts.append(
                                "SELECT CASE gender WHEN 'male' THEN 'ذكر' WHEN 'female' THEN 'أنثى' END, "
                                "COUNT(*) FROM bot_users WHERE gender IS NOT NULL GROUP BY gender"
                            )
                        df_g = pd.read_sql(
                            f"SELECT g AS الجنس, SUM(c)::int AS العدد FROM ({ ' UNION ALL '.join(gender_parts) }) u "
                            "WHERE g IS NOT NULL GROUP BY g ORDER BY العدد DESC", conn)
                        if df_g.empty:
                            st.caption("لا توجد بيانات جنس بعد.")
                        else:
                            fig_g = px.pie(df_g, names="الجنس", values="العدد", hole=0.45, title="الجنس")
                            st.plotly_chart(apply_brand_theme(fig_g), use_container_width=True)
                    except Exception as ex:
                        try: conn.rollback()
                        except Exception: pass
                        st.caption(f"تعذّر تحميل الجنس: {str(ex)[:80]}")
                else:
                    st.caption("⚙️ عمود `gender` غير موجود.")

            # ── العمر ──
            with d2:
                if _has_birth:
                    try: conn.rollback()
                    except Exception: pass
                    try:
                        birth_parts = []
                        if _has_web_birth:
                            birth_parts.append("SELECT birth_date FROM web_users WHERE birth_date IS NOT NULL")
                        if _has_bot_birth:
                            birth_parts.append("SELECT birth_date FROM bot_users WHERE birth_date IS NOT NULL")
                        df_age = pd.read_sql(f"""
                            WITH u AS ({ ' UNION ALL '.join(birth_parts) })
                            SELECT الفئة, COUNT(*)::int AS العدد, MIN(yr)::int AS _o
                              FROM (
                                SELECT
                                  CASE
                                    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 18 THEN 'أقل من 18'
                                    WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 18 AND 24 THEN '18-24'
                                    WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 25 AND 34 THEN '25-34'
                                    WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 35 AND 44 THEN '35-44'
                                    WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 45 AND 54 THEN '45-54'
                                    ELSE '55+'
                                  END AS الفئة,
                                  EXTRACT(YEAR FROM AGE(birth_date)) AS yr
                                FROM u
                              ) x
                             GROUP BY الفئة ORDER BY _o
                        """, conn)
                        if df_age.empty:
                            st.caption("لا توجد بيانات أعمار بعد.")
                        else:
                            fig_a = px.bar(df_age, x="الفئة", y="العدد", text="العدد",
                                           title="الفئة العمرية")
                            st.plotly_chart(apply_brand_theme(fig_a), use_container_width=True)
                    except Exception as ex:
                        try: conn.rollback()
                        except Exception: pass
                        st.caption(f"تعذّر تحميل الأعمار: {str(ex)[:80]}")
                else:
                    st.caption("⚙️ عمود `birth_date` غير موجود.")

            # ── المدن (مستقلّة، لا تحتاج ميجريشن) ──
            with d3:
                try: conn.rollback()
                except Exception: pass
                try:
                    df_city = pd.read_sql("""
                        SELECT TRIM(city) AS المدينة, COUNT(*)::int AS العدد
                          FROM (
                            SELECT city FROM web_users WHERE city IS NOT NULL AND TRIM(city)<>''
                            UNION ALL
                            SELECT city FROM bot_users WHERE city IS NOT NULL AND TRIM(city)<>''
                          ) u
                         GROUP BY TRIM(city) ORDER BY العدد DESC LIMIT 10
                    """, conn)
                    if df_city.empty:
                        st.caption("لا توجد بيانات مدن بعد.")
                    else:
                        fig_c = px.bar(df_city, x="المدينة", y="العدد", text="العدد",
                                       title="أعلى 10 مدن")
                        st.plotly_chart(apply_brand_theme(fig_c), use_container_width=True)
                except Exception as ex:
                    try: conn.rollback()
                    except Exception: pass
                    st.caption(f"تعذّر تحميل المدن: {str(ex)[:80]}")

            # تقاطع الجنس × العمر — للشركاء (مشروط بوجود الأعمدة)
            if _has_gender and _has_birth:
                try: conn.rollback()
                except Exception: pass
                try:
                    cross_parts = []
                    if _has_web_gender and _has_web_birth:
                        cross_parts.append(
                            "SELECT gender, birth_date FROM web_users WHERE gender IS NOT NULL AND birth_date IS NOT NULL"
                        )
                    if _has_bot_gender and _has_bot_birth:
                        cross_parts.append(
                            "SELECT gender, birth_date FROM bot_users WHERE gender IS NOT NULL AND birth_date IS NOT NULL"
                        )
                    if cross_parts:
                        df_cross = pd.read_sql(f"""
                            WITH u AS ({ ' UNION ALL '.join(cross_parts) })
                            SELECT
                              CASE gender WHEN 'male' THEN 'ذكر' WHEN 'female' THEN 'أنثى' END AS "الجنس",
                              CASE
                                WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 18 THEN 'أقل من 18'
                                WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 18 AND 24 THEN '18-24'
                                WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 25 AND 34 THEN '25-34'
                                WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 35 AND 44 THEN '35-44'
                                WHEN EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN 45 AND 54 THEN '45-54'
                                ELSE '55+'
                              END AS "الفئة العمرية",
                              COUNT(*)::int AS "العدد"
                            FROM u
                            GROUP BY "الجنس", "الفئة العمرية"
                            ORDER BY "الجنس", "الفئة العمرية"
                        """, conn)
                        if not df_cross.empty:
                            st.markdown("#### 🎯 الشريحة (جنس × عمر) — قاعدة شراكات")
                            pivot_x = (df_cross.pivot(index="الفئة العمرية", columns="الجنس", values="العدد")
                                              .fillna(0).astype(int))
                            st.dataframe(pivot_x, use_container_width=True)
                except Exception:
                    try: conn.rollback()
                    except Exception: pass

            # ─── drill-downs: مين هم في كل شريحة ديموغرافية ─────────
            if _has_gender or _has_birth:
                st.markdown("#### 🔍 من هم في كل شريحة؟")
                st.caption("اختر شريحة لرؤية كل أعضائها بالاسم/الإيميل/القناة + CSV.")

                # نبني UNION واحد للجنسين معاً (مع NULL-safe للأعمدة المفقودة)
                sel_web_g = "gender" if _has_web_gender else "NULL::text"
                sel_web_b = "birth_date" if _has_web_birth else "NULL::date"
                sel_bot_g = "gender" if _has_bot_gender else "NULL::text"
                sel_bot_b = "birth_date" if _has_bot_birth else "NULL::date"
                try: conn.rollback()
                except Exception: pass
                # ملاحظة: Postgres يحوّل aliases غير المُقتبسة إلى lowercase.
                # نستخدم lowercase صريح لتجنّب مفاجآت في pandas.
                df_all = pd.read_sql(f"""
                    SELECT 'web' AS source, id::text AS id,
                           display_name AS name, email AS email,
                           phone_number AS phone,
                           telegram_username AS tg, city AS city,
                           {sel_web_g} AS gender, {sel_web_b} AS birth_date,
                           created_at AS joined, last_seen AS last_seen
                      FROM web_users
                    UNION ALL
                    SELECT 'bot', telegram_id::text, username, NULL::text, NULL::text,
                           username, city,
                           {sel_bot_g}, {sel_bot_b},
                           joined_at, last_seen
                      FROM bot_users
                     WHERE deleted_at IS NULL
                """, conn)

                df_all["age"] = pd.NA
                if "birth_date" in df_all.columns:
                    today = pd.Timestamp.today().normalize()
                    bd = pd.to_datetime(df_all["birth_date"], errors="coerce")
                    df_all["age"] = ((today - bd).dt.days // 365).astype("Int64")

                def _age_bucket(a):
                    if pd.isna(a): return "—"
                    a = int(a)
                    if a < 18: return "أقل من 18"
                    if a <= 24: return "18-24"
                    if a <= 34: return "25-34"
                    if a <= 44: return "35-44"
                    if a <= 54: return "45-54"
                    return "55+"
                df_all["age_bucket"] = df_all["age"].apply(_age_bucket)
                df_all["gender_ar"] = df_all["gender"].map({"male":"ذكر","female":"أنثى"}).fillna("—")
                df_all["المصدر"] = df_all["source"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                df_all["تيليجرام"] = df_all["tg"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")

                def _render_slice(label, df_slice, key):
                    """Render an expander with the slice's user list."""
                    with st.expander(f"{label} — {len(df_slice):,} مستخدم"):
                        if df_slice.empty:
                            st.caption("لا أحد في هذه الشريحة.")
                            return
                        show = df_slice[["المصدر","id","name","email","phone","تيليجرام",
                                         "city","gender_ar","age","age_bucket","joined","last_seen"]].copy()
                        show["joined"]    = pd.to_datetime(show["joined"],    errors="coerce").dt.strftime("%Y-%m-%d")
                        show["last_seen"] = pd.to_datetime(show["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d")
                        # age نوعه Int64 (nullable) — نحوّله لـ string لتعبئة "—" بدون TypeError
                        show["age"] = show["age"].astype("string")
                        show = show.rename(columns={
                            "id":"ID","name":"الاسم","email":"الإيميل","phone":"الجوال",
                            "city":"المدينة","gender_ar":"الجنس","age":"العمر",
                            "age_bucket":"الفئة_العمرية",
                            "joined":"الانضمام","last_seen":"آخر_ظهور",
                        })
                        # تعبئة آمنة لكل عمود حسب نوعه (نمنع TypeError على Int64)
                        for _col in show.columns:
                            show[_col] = show[_col].astype("string").fillna("—").replace("<NA>", "—")
                        st.dataframe(show, use_container_width=True, hide_index=True, height=320)
                        st.download_button(
                            f"📥 CSV — {label}",
                            show.to_csv(index=False).encode("utf-8-sig"),
                            f"slice_{key}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_demo_{key}",
                        )

                # تابز للأبعاد الثلاثة
                _dtab_g, _dtab_a, _dtab_c = st.tabs(["👥 حسب الجنس", "🎂 حسب الفئة العمرية", "📍 حسب المدينة"])

                with _dtab_g:
                    if _has_gender:
                        for g_label, g_key in [("👨 ذكور","ذكر"), ("👩 إناث","أنثى")]:
                            _render_slice(g_label, df_all[df_all["gender_ar"]==g_key], f"gender_{g_key}")
                    else:
                        st.caption("⚙️ عمود `gender` غير موجود.")

                with _dtab_a:
                    if _has_birth:
                        for b in ["أقل من 18","18-24","25-34","35-44","45-54","55+"]:
                            _render_slice(f"🎂 {b}", df_all[df_all["age_bucket"]==b], f"age_{b}")
                    else:
                        st.caption("⚙️ عمود `birth_date` غير موجود.")

                with _dtab_c:
                    # نختار أعلى 10 مدن لتجنّب فوضى الشاشة، ثم زر "كل المدن"
                    top_cities = (df_all[df_all["city"].notna() & (df_all["city"].astype(str).str.strip()!="")]
                                  ["city"].astype(str).str.strip().value_counts().head(10).index.tolist())
                    if not top_cities:
                        st.caption("لا بيانات مدن.")
                    else:
                        for c in top_cities:
                            _render_slice(f"📍 {c}",
                                          df_all[df_all["city"].astype(str).str.strip() == c],
                                          f"city_{c}")

            st.divider()

        with _main_tabs[6]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_6",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 7 ─ 🎯 Audience Builder — منشئ الشرائح
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 🎯 Audience Builder — منشئ الشرائح")
            st.caption("اختر معايير قابلة للجمع ← شاهد العدد ← صدّر CSV/Excel أو وجّه لمركز الإشعارات.")

            try: conn.rollback()
            except Exception: pass

            # نطاق التاريخ + الحالة (مستقلّ عن نطاق الصفحة العام)
            with st.expander("📅 نطاق التاريخ + الحالة", expanded=True):
                ab_d1, ab_d2, ab_d3 = st.columns(3)
                with ab_d1:
                    ab_date_from = st.date_input("📅 من تاريخ:", value=date.today() - timedelta(days=90),
                                                 max_value=date.today(), key="ab_date_from")
                with ab_d2:
                    ab_date_to = st.date_input("📅 إلى تاريخ:", value=date.today(),
                                               min_value=ab_date_from, max_value=date.today(),
                                               key="ab_date_to")
                with ab_d3:
                    ab_status = st.radio(
                        "📡 الحالة في النطاق:",
                        ["الكل", "🟢 نشط (تفاعل ولو مرة)", "🔴 خامل (لا تفاعل)"],
                        horizontal=False, key="ab_status",
                    )
                st.caption(
                    "ℹ️ النطاق هنا مستقل عن نطاق الصفحة الأعلى. "
                    "«نشط» = له حركة في action_logs خلال النطاق. «خامل» = موجود في الحسابات بدون أي حركة في النطاق."
                )

            # مرشّحات الديموغرافيا + المصدر
            with st.expander("🎯 الديموغرافيا + المصدر + المفضّلة", expanded=True):
                ab_c1, ab_c2, ab_c3 = st.columns(3)
                with ab_c1:
                    ab_gender = st.multiselect("👥 الجنس:", ["ذكر","أنثى"],
                                               key="ab_gender", placeholder="الكل")
                    ab_age_min = st.number_input("🎂 العمر من:", 0, 100, 0, key="ab_age_min")
                    ab_age_max = st.number_input("🎂 العمر إلى:", 0, 100, 100, key="ab_age_max")
                with ab_c2:
                    # المدن من قاعدة مُوحَّدة
                    cities_df = pd.read_sql(f"""
                        SELECT DISTINCT { _norm_city_sql('city') } AS city FROM (
                          SELECT city FROM web_users WHERE city IS NOT NULL AND TRIM(city)<>''
                          UNION
                          SELECT city FROM bot_users WHERE city IS NOT NULL AND TRIM(city)<>''
                        ) u
                        WHERE { _norm_city_sql('city') } IS NOT NULL
                        ORDER BY 1
                    """, conn)
                    ab_cities = st.multiselect("📍 المدن (موحَّدة عربي/إنجليزي):",
                                               cities_df["city"].dropna().tolist(),
                                               key="ab_cities", placeholder="الكل")
                    ab_source = st.multiselect("📡 المصدر:",
                                               ["🤖 البوت","🌐 الموقع","🔹 الميني-ويب"],
                                               key="ab_source", placeholder="الكل")
                with ab_c3:
                    # المفضّلة/الاهتمامات — من user_favorites (kind='category')
                    try: conn.rollback()
                    except Exception: pass
                    interests_df = pd.read_sql("""
                        SELECT DISTINCT TRIM(category_name) AS cat
                          FROM user_favorites
                         WHERE kind='category' AND category_name IS NOT NULL AND TRIM(category_name)<>''
                         ORDER BY 1
                    """, conn)
                    ab_interests = st.multiselect("❤️ مهتمّون بقسم/فضّلوه:",
                                                  interests_df["cat"].tolist(),
                                                  key="ab_interests", placeholder="الكل",
                                                  help="من user_favorites حيث kind='category'")
                    ab_min_copies = st.number_input("🎟️ نسخ ≥:", 0, 10000, 0, key="ab_min_copies")
                    ab_pdpl = st.checkbox("✅ موافقون على PDPL فقط (الموقع)", key="ab_pdpl")

            # بناء الـ UNION
            ab_clauses_web = ["1=1"]
            ab_clauses_bot = ["1=1"]
            ab_pw, ab_pb = [], []

            if "ذكر" in ab_gender and "أنثى" not in ab_gender:
                ab_clauses_web.append("gender='male'");   ab_clauses_bot.append("gender='male'")
            elif "أنثى" in ab_gender and "ذكر" not in ab_gender:
                ab_clauses_web.append("gender='female'"); ab_clauses_bot.append("gender='female'")

            if ab_age_min > 0 or ab_age_max < 100:
                age_w = f"birth_date IS NOT NULL AND EXTRACT(YEAR FROM AGE(birth_date)) BETWEEN {int(ab_age_min)} AND {int(ab_age_max)}"
                ab_clauses_web.append(age_w); ab_clauses_bot.append(age_w)

            if ab_cities:
                ph = ",".join(["%s"]*len(ab_cities))
                ab_clauses_web.append(f"{ _norm_city_sql('city') } IN ({ph})")
                ab_clauses_bot.append(f"{ _norm_city_sql('city') } IN ({ph})")
                ab_pw += ab_cities; ab_pb += ab_cities

            if ab_pdpl:
                ab_clauses_web.append("consent_at IS NOT NULL")

            include_web = (not ab_source) or "🌐 الموقع" in ab_source
            include_bot = (not ab_source) or "🤖 البوت" in ab_source or "🔹 الميني-ويب" in ab_source
            # لو فقط ميني-ويب مختار → نقتصر على bot_users اللي لهم نشاط ميني-ويب
            miniapp_only = ("🔹 الميني-ويب" in ab_source
                            and "🤖 البوت" not in ab_source
                            and "🌐 الموقع" not in ab_source)
            include_mini_filter = "🔹 الميني-ويب" in ab_source

            # حدود زمن للفلاتر الزمنية في Audience Builder
            ab_t_from = pd.Timestamp(ab_date_from).strftime("%Y-%m-%d 00:00:00")
            ab_t_to   = (pd.Timestamp(ab_date_to) + pd.Timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

            # نستخدم flags وجود الأعمدة (محسوبة في قسم الديموغرافيا) لبناء
            # SELECT ديناميكي يتجنّب الإشارة لأعمدة غير موجودة على القاعدة.
            _web_gender_sel = "gender"     if _has_web_gender else "NULL::text"
            _bot_gender_sel = "gender"     if _has_bot_gender else "NULL::text"
            _web_birth_sel  = "birth_date" if _has_web_birth  else "NULL::date"
            _bot_birth_sel  = "birth_date" if _has_bot_birth  else "NULL::date"

            # لو الفلتر يطلب جنس/عمر لكن العمود غير موجود → نتجنب الفشل
            # بإزالة شروط الفلتر تلك ونحذّر المستخدم.
            _filters_dropped = []
            ab_clauses_web_safe = [c for c in ab_clauses_web
                                   if not (c.startswith("gender=") and not _has_web_gender)
                                   and not (("birth_date" in c) and not _has_web_birth)]
            if len(ab_clauses_web_safe) != len(ab_clauses_web):
                _filters_dropped.append("بعض فلاتر الجنس/العمر على الموقع — العمود غير موجود")
            ab_clauses_bot_safe = [c for c in ab_clauses_bot
                                   if not (c.startswith("gender=") and not _has_bot_gender)
                                   and not (("birth_date" in c) and not _has_bot_birth)]
            if len(ab_clauses_bot_safe) != len(ab_clauses_bot):
                _filters_dropped.append("بعض فلاتر الجنس/العمر على البوت — العمود غير موجود")
            if _filters_dropped:
                for msg in _filters_dropped:
                    st.caption(f"⚠️ تجاهلنا {msg}.")

            parts, all_params = [], []
            if include_web:
                parts.append(f"""
                    SELECT 'web' AS source, id AS user_id, display_name AS name,
                           email, phone_number AS phone, telegram_username,
                           {_web_gender_sel} AS gender,
                           {_web_birth_sel}  AS birth_date,
                           city, last_seen, consent_at,
                           email_verified_at
                      FROM web_users
                     WHERE { ' AND '.join(ab_clauses_web_safe) }
                """)
                all_params += ab_pw
            if include_bot:
                parts.append(f"""
                    SELECT 'bot' AS source, telegram_id AS user_id, username AS name,
                           NULL::text AS email, NULL::text AS phone, username AS telegram_username,
                           {_bot_gender_sel} AS gender,
                           {_bot_birth_sel}  AS birth_date,
                           city, last_seen, NULL::timestamptz AS consent_at,
                           NULL::timestamptz AS email_verified_at
                      FROM bot_users
                     WHERE { ' AND '.join(ab_clauses_bot_safe) } AND deleted_at IS NULL
                """)
                all_params += ab_pb

            if not parts:
                st.warning("اختر مصدر واحد على الأقل.")
            else:
                ab_query = " UNION ALL ".join(parts) + " ORDER BY last_seen DESC NULLS LAST"
                audience = pd.read_sql(ab_query, conn,
                                       params=tuple(all_params) if all_params else None)

                # ─── فلتر «الحالة»: نشط/خامل في نطاق التاريخ ─────────────
                if not audience.empty and ab_status != "الكل":
                    try: conn.rollback()
                    except Exception: pass
                    activ = pd.read_sql("""
                        SELECT
                          CASE WHEN source='web' THEN 'web' ELSE 'bot' END AS src,
                          user_id,
                          COUNT(*) AS acts_in_range
                        FROM action_logs
                        WHERE user_id IS NOT NULL
                          AND action_time >= %s AND action_time < %s
                        GROUP BY src, user_id
                    """, conn, params=(ab_t_from, ab_t_to))
                    m = audience.merge(activ, left_on=["source","user_id"],
                                       right_on=["src","user_id"], how="left")
                    m["acts_in_range"] = m["acts_in_range"].fillna(0).astype(int)
                    if ab_status.startswith("🟢"):
                        audience = m[m["acts_in_range"] > 0].copy()
                    else:
                        audience = m[m["acts_in_range"] == 0].copy()

                # ─── فلتر الميني-ويب فقط ──────────────────────────────
                if not audience.empty and include_mini_filter:
                    try: conn.rollback()
                    except Exception: pass
                    mini = pd.read_sql("""
                        SELECT DISTINCT user_id
                          FROM action_logs
                         WHERE source IN ('telegram_miniapp','miniapp') AND user_id IS NOT NULL
                    """, conn)
                    mini_set = set(mini["user_id"].astype(int).tolist())
                    if miniapp_only:
                        audience = audience[
                            (audience["source"]=="bot") & (audience["user_id"].isin(mini_set))
                        ].copy()
                    # لو ميني-ويب مع باقي المصادر → لا نُسقط أحداً (شامل)

                # ─── فلتر الاهتمامات (مفضّلة قسم) ───────────────────────
                if not audience.empty and ab_interests:
                    try: conn.rollback()
                    except Exception: pass
                    ph = ",".join(["%s"] * len(ab_interests))
                    favs = pd.read_sql(f"""
                        SELECT DISTINCT
                          CASE WHEN platform='web' THEN 'web' ELSE 'bot' END AS src,
                          COALESCE(web_user_id, telegram_id) AS user_id
                        FROM user_favorites
                        WHERE kind='category'
                          AND TRIM(category_name) IN ({ph})
                    """, conn, params=tuple(ab_interests))
                    interest_keys = set(zip(favs["src"].astype(str), favs["user_id"].astype(int)))
                    audience["_key"] = list(zip(audience["source"].astype(str),
                                                audience["user_id"].astype(int)))
                    audience = audience[audience["_key"].isin(interest_keys)].drop(columns=["_key"]).copy()

                # ─── فلتر النسخ ─────────────────────────────────────────
                if ab_min_copies > 0 and not audience.empty:
                    copies_per = pd.read_sql("""
                        SELECT
                          CASE WHEN source='web' THEN 'web' ELSE 'bot' END AS src,
                          user_id,
                          COUNT(*) FILTER (WHERE action_type='copy_coupon') AS copies
                        FROM action_logs
                        WHERE user_id IS NOT NULL
                        GROUP BY src, user_id
                    """, conn)
                    m = audience.merge(copies_per, left_on=["source","user_id"],
                                       right_on=["src","user_id"], how="left")
                    m["copies"] = m["copies"].fillna(0).astype(int)
                    audience = m[m["copies"] >= ab_min_copies].copy()

                count = len(audience)
                cR1, cR2 = st.columns([1,3])
                with cR1:
                    kpi_card("👥", "العدد المطابق", f"{count:,}", "emerald")
                with cR2:
                    if count == 0:
                        st.warning("⚠️ لا أحد يطابق هذه المعايير. وسّع الفلاتر.")
                    else:
                        st.success(f"✅ **{count:,}** شخص جاهز للاستهداف.")

                if count > 0:
                    view = audience.copy()
                    view["المصدر"] = view["source"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                    view["الاسم"] = view["name"].where(view["name"].notna() & (view["name"]!=""), other=None)
                    view["الاسم"] = view["الاسم"].fillna(view["telegram_username"]).fillna("—")
                    view["الإيميل"]  = view["email"].fillna("—")
                    view["الجوال"]   = view["phone"].fillna("—")
                    view["تيليجرام"] = view["telegram_username"].apply(
                        lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    view["المدينة"]  = view["city"].fillna("—")
                    view["آخر_ظهور"] = pd.to_datetime(view["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d")

                    show_cols = ["المصدر","الاسم","الإيميل","الجوال","تيليجرام","المدينة","آخر_ظهور"]
                    if "copies" in view.columns:
                        view["نسخ"] = view["copies"]
                        show_cols.insert(2, "نسخ")

                    st.dataframe(view[show_cols].head(500), use_container_width=True,
                                 hide_index=True, height=380)
                    if count > 500:
                        st.caption(f"عرض أول 500 — التصدير يحتوي الـ {count:,} كلها.")

                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        st.download_button(
                            f"📥 CSV ({count:,})",
                            view[show_cols].to_csv(index=False).encode("utf-8-sig"),
                            f"audience_{date.today()}.csv", "text/csv",
                            key="ua_dl_aud_csv",
                        )
                    with ec2:
                        out_xl = BytesIO()
                        with pd.ExcelWriter(out_xl, engine="xlsxwriter") as w:
                            view[show_cols].to_excel(w, index=False, sheet_name="Audience")
                        st.download_button(
                            f"📥 Excel ({count:,})", out_xl.getvalue(),
                            f"audience_{date.today()}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="ua_dl_aud_xl",
                        )
                    with ec3:
                        if st.button("📨 أرسل لمركز الإشعارات", key="ua_send_aud_notify"):
                            st.session_state["broadcast_audience"] = {
                                "rows":   view[show_cols].to_dict(orient="records"),
                                "count":  count,
                                "source": "Audience Builder",
                                "ts":     date.today().isoformat(),
                            }
                            st.success(f"✅ تم تجهيز {count:,} شخص. افتح «مركز الإشعارات».")

            st.divider()

        with _main_tabs[7]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_7",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 8 ─ 🎯 RFM Matrix + Personas (شرائح ذكية)
            # R = Recency (أيام منذ آخر نشاط)
            # F = Frequency (عدد النسخات في النطاق)
            # M = Monetary proxy (عمق التفاعل: متاجر فريدة نسخ منها)
            # كل بُعد nytile(5) → 6 شخصيات سلوكية ثم Treemap + درل-داون
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 🎯 RFM + شخصيات سلوكية (Personas)")
            st.warning(
                "⚠️ **هذا القسم ذو معنى فقط مع N ≥ 100 مستخدم نسخوا.** "
                "الـ quintiles (1-5) تحتاج عيّنة كبيرة لتعطي شرائح معبّرة. "
                "مع عيّنة صغيرة قد يصير الشخص الوحيد «Champion» بناءً على رتبته في عيّنة من ٥ — وهذا ليس معبّراً. "
                "تستخدم هذا للاسترشاد فقط، ليس للقرارات التجارية."
            )
            st.caption(
                f"كل مستخدم نسخ ولو مرة في النطاق **{date_from.strftime('%Y-%m-%d')} → "
                f"{date_to.strftime('%Y-%m-%d')}** له ٣ نقاط (1-5): "
                "Recency / Frequency / Monetary-proxy. الشخصية مزيج النقاط الثلاث."
            )

            try: conn.rollback()
            except Exception: pass

            # نبني الجدول الموحّد (ويب + بوت) — كل مستخدم نسخ ≥ 1 خلال النطاق
            rfm_src_clause, rfm_src_params = _ua_src_clause("al")
            rfm_raw = pd.read_sql(f"""
                WITH agg AS (
                  SELECT
                    CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                    al.user_id,
                    MAX(al.action_time)                                      AS last_seen_act,
                    COUNT(*) FILTER (WHERE al.action_type='copy_coupon')     AS copies,
                    COUNT(*) FILTER (WHERE al.action_type='click_link')      AS clicks,
                    COUNT(DISTINCT al.store_id)
                      FILTER (WHERE al.action_type='copy_coupon')            AS uniq_stores
                  FROM action_logs al
                  WHERE al.action_time >= %s AND al.action_time < %s
                    AND al.user_id IS NOT NULL
                    { rfm_src_clause }
                  GROUP BY src, al.user_id
                  HAVING COUNT(*) FILTER (WHERE al.action_type='copy_coupon') > 0
                )
                SELECT a.src, a.user_id, a.last_seen_act, a.copies, a.clicks, a.uniq_stores,
                       EXTRACT(EPOCH FROM (NOW() - a.last_seen_act))/86400.0 AS days_since,
                       COALESCE(wu.display_name, bu.username, '—')            AS name,
                       wu.email, wu.phone_number AS phone, bu.username        AS tg_username,
                       COALESCE(wu.city, bu.city, '—')                        AS city
                  FROM agg a
                  LEFT JOIN web_users wu ON a.src='web' AND wu.id = a.user_id
                  LEFT JOIN bot_users bu ON a.src='bot' AND bu.telegram_id = a.user_id
            """, conn, params=tuple([_t_from, _t_to] + rfm_src_params))

            if rfm_raw.empty:
                st.info("📭 لا يوجد مستخدمون نسخوا في هذا النطاق بهذا الفلتر.")
            else:
                df_rfm = rfm_raw.copy()
                df_rfm["days_since"] = df_rfm["days_since"].astype(float).round(1)
                # NTILE 5 (1 = الأسوأ، 5 = الأفضل)
                df_rfm["R"] = pd.qcut(-df_rfm["days_since"], q=min(5, df_rfm["days_since"].nunique()),
                                      labels=False, duplicates="drop") + 1
                df_rfm["F"] = pd.qcut(df_rfm["copies"].rank(method="first"),
                                      q=min(5, df_rfm["copies"].nunique()),
                                      labels=False, duplicates="drop") + 1
                df_rfm["M"] = pd.qcut(df_rfm["uniq_stores"].rank(method="first"),
                                      q=min(5, df_rfm["uniq_stores"].nunique()),
                                      labels=False, duplicates="drop") + 1
                df_rfm[["R","F","M"]] = df_rfm[["R","F","M"]].fillna(1).astype(int)

                def _persona(r):
                    R, F, M = r["R"], r["F"], r["M"]
                    if R >= 4 and F >= 4 and M >= 4:   return "🏆 Champions — الأبطال"
                    if R >= 4 and F >= 3:              return "💎 Loyal — مخلصون"
                    if R >= 4 and F <= 2:              return "🆕 New / Promising — جدد واعدون"
                    if R <= 2 and F >= 4:              return "💔 Can't Lose — يجب الاحتفاظ بهم"
                    if R <= 2 and F >= 3:              return "⚠️ At Risk — على وشك الفقد"
                    if R == 3 and F >= 3:              return "👀 Need Attention — تحتاج متابعة"
                    if R <= 2 and F <= 2:              return "👻 Lost / Hibernating — نائمون"
                    return "🌱 Potential — محتملون"

                df_rfm["شخصية"] = df_rfm.apply(_persona, axis=1)

                # ─── Treemap ───
                pers_agg = (df_rfm.groupby("شخصية", as_index=False)
                                  .agg(عدد=("user_id","nunique"),
                                       نسخ_متوسط=("copies","mean"),
                                       recency_متوسط=("days_since","mean")))
                pers_agg["نسخ_متوسط"]      = pers_agg["نسخ_متوسط"].round(1)
                pers_agg["recency_متوسط"]   = pers_agg["recency_متوسط"].round(1)
                tot_p = int(pers_agg["عدد"].sum())
                pers_agg["نسبة%"]           = (pers_agg["عدد"]*100/tot_p).round(1)

                cR1, cR2 = st.columns([2,1])
                with cR1:
                    fig_tm = px.treemap(pers_agg, path=["شخصية"], values="عدد",
                                        color="نسخ_متوسط", color_continuous_scale="Greens",
                                        title=f"الشخصيات السلوكية ({tot_p:,} مستخدم نشط)")
                    st.plotly_chart(apply_brand_theme(fig_tm), use_container_width=True)
                with cR2:
                    st.markdown("#### 📊 ملخّص الشخصيات")
                    st.dataframe(pers_agg[["شخصية","عدد","نسبة%","نسخ_متوسط","recency_متوسط"]],
                                 use_container_width=True, hide_index=True, height=420)

                # ─── درل-داون: اختر شخصية + CSV + Action Center ───
                pick_persona = st.selectbox("🔍 اختر شخصية للدرل-داون:",
                                            sorted(df_rfm["شخصية"].unique()),
                                            key="ua_rfm_persona_pick")
                seg = df_rfm[df_rfm["شخصية"]==pick_persona].copy()
                seg["المصدر"]   = seg["src"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                seg["تيليجرام"] = seg["tg_username"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                seg["آخر_نشاط"] = pd.to_datetime(seg["last_seen_act"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                seg_show = seg[["المصدر","name","email","phone","تيليجرام","city",
                                "copies","clicks","uniq_stores","days_since","R","F","M","آخر_نشاط"]].rename(
                    columns={"name":"الاسم","email":"الإيميل","phone":"الجوال","city":"المدينة",
                             "copies":"نسخ","clicks":"نقرات","uniq_stores":"متاجر_فريدة",
                             "days_since":"أيام_منذ_آخر_نشاط"}).fillna("—")
                st.dataframe(seg_show.head(500), use_container_width=True,
                             hide_index=True, height=320)
                st.caption(f"عرض {min(len(seg_show), 500)} من **{len(seg_show)}** — التصدير كامل.")

                acR1, acR2 = st.columns(2)
                with acR1:
                    st.download_button(f"📥 CSV — {pick_persona}",
                                       seg_show.to_csv(index=False).encode("utf-8-sig"),
                                       f"persona_{date.today()}.csv", "text/csv",
                                       key="ua_dl_persona")
                with acR2:
                    if st.button(f"📨 أرسل {pick_persona} لمركز الإشعارات", key="ua_persona_notify"):
                        st.session_state["broadcast_audience"] = {
                            "rows":   seg_show.to_dict(orient="records"),
                            "count":  len(seg_show),
                            "source": f"Persona: {pick_persona}",
                            "ts":     date.today().isoformat(),
                        }
                        st.success(f"✅ تم تجهيز {len(seg_show):,} شخص.")

            st.divider()

        with _main_tabs[8]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_8",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 9 ─ 🌀 Cohort Retention — نمط البقاء
            # «من سجّل في شهر X، كم نسبتهم نشطون في الأشهر التالية؟»
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 🌀 Cohort Retention — منحنى البقاء")
            st.caption(
                "صفّ = شهر الانضمام · عمود = الشهر منذ الانضمام · القيمة = % مازالوا تفاعلوا فعلاً. "
                "**«تفاعل فعلي» = نسخ كوبون أو نقر رابط فقط** (لا يشمل بدء الجلسة `start` ولا view-only "
                "حتى لا تتضخّم الأرقام)."
            )

            try: conn.rollback()
            except Exception: pass

            df_coh = pd.read_sql("""
                WITH joined AS (
                  SELECT 'bot'::text AS src, telegram_id AS user_id,
                         DATE_TRUNC('month', joined_at)::date AS cohort
                    FROM bot_users
                   WHERE joined_at IS NOT NULL AND deleted_at IS NULL
                  UNION ALL
                  SELECT 'web', id, DATE_TRUNC('month', created_at)::date
                    FROM web_users WHERE created_at IS NOT NULL
                ),
                acts AS (
                  SELECT CASE WHEN source='web' THEN 'web' ELSE 'bot' END AS src,
                         user_id,
                         DATE_TRUNC('month', action_time)::date AS act_month
                    FROM action_logs
                   WHERE action_type IN ('copy_coupon','click_link')  -- تفاعل فعلي فقط (لا start ولا view)
                     AND user_id IS NOT NULL
                   GROUP BY 1,2,3
                )
                SELECT j.cohort,
                       (EXTRACT(YEAR FROM AGE(a.act_month, j.cohort))*12 +
                        EXTRACT(MONTH FROM AGE(a.act_month, j.cohort)))::int AS month_offset,
                       COUNT(DISTINCT j.user_id) AS active
                  FROM joined j
                  LEFT JOIN acts a ON a.src=j.src AND a.user_id=j.user_id AND a.act_month >= j.cohort
                 GROUP BY j.cohort, month_offset
                 ORDER BY j.cohort, month_offset
            """, conn)

            if df_coh.empty:
                st.info("📭 لا بيانات كافية لبناء الـ cohorts.")
            else:
                df_coh = df_coh.dropna(subset=["month_offset"])
                df_coh["month_offset"] = df_coh["month_offset"].astype(int)
                df_coh = df_coh[df_coh["month_offset"] >= 0]
                # حجم الـ cohort = offset=0
                sizes = (df_coh[df_coh["month_offset"]==0]
                         .set_index("cohort")["active"].to_dict())
                df_coh["cohort_size"] = df_coh["cohort"].map(sizes).fillna(0)
                df_coh["retention_pct"] = (df_coh["active"]*100.0 /
                                           df_coh["cohort_size"].replace(0, 1)).round(1)

                pivot_coh = df_coh.pivot(index="cohort", columns="month_offset",
                                         values="retention_pct").fillna(0)
                # نقصّ لآخر 12 cohort × 12 أشهر للوضوح
                pivot_coh = pivot_coh.tail(12).iloc[:, :12]
                pivot_coh.index = pd.to_datetime(pivot_coh.index).strftime("%Y-%m")

                fig_coh = px.imshow(pivot_coh, color_continuous_scale="Greens",
                                    aspect="auto", text_auto=".0f",
                                    labels=dict(x="الشهر منذ الانضمام", y="شهر الانضمام", color="بقاء %"),
                                    title="منحنى البقاء — كل صفّ cohort مستقل")
                st.plotly_chart(apply_brand_theme(fig_coh), use_container_width=True)

                # رؤى سريعة
                if not pivot_coh.empty and pivot_coh.shape[1] > 1:
                    avg_m1 = pivot_coh.iloc[:, 1].replace(0, pd.NA).dropna().mean()
                    avg_m3 = pivot_coh.iloc[:, 3].replace(0, pd.NA).dropna().mean() if pivot_coh.shape[1] > 3 else None
                    ic1, ic2 = st.columns(2)
                    with ic1: kpi_card("📅", "متوسط البقاء بعد شهر", f"{avg_m1:.1f}%" if pd.notna(avg_m1) else "—", "info")
                    if avg_m3 is not None and pd.notna(avg_m3):
                        with ic2: kpi_card("📅", "متوسط البقاء بعد 3 أشهر", f"{avg_m3:.1f}%", "warning")

                # ─── drill-down: مين انضمّ في cohort معيّن ─────────
                st.markdown("#### 🔍 مين انضمّ في شهر معيّن؟ + حالتهم الحالية")
                st.caption("اختر شهر cohort لرؤية كل من انضمّ فيه ومتى آخر ظهور — لتقييم البقاء الفعلي.")
                cohort_months = pivot_coh.index.tolist()
                if cohort_months:
                    pick_cohort = st.selectbox("📅 شهر الـ cohort:", cohort_months,
                                               index=len(cohort_months)-1,
                                               key="ua_cohort_pick")
                    try: conn.rollback()
                    except Exception: pass
                    df_coh_users = pd.read_sql("""
                        SELECT 'bot' AS source, telegram_id::text AS id, username AS name,
                               NULL::text AS email, NULL::text AS phone,
                               joined_at AS joined, last_seen
                          FROM bot_users
                         WHERE deleted_at IS NULL
                           AND TO_CHAR(joined_at, 'YYYY-MM') = %s
                        UNION ALL
                        SELECT 'web', id::text, display_name, email, phone_number,
                               created_at, last_seen
                          FROM web_users
                         WHERE TO_CHAR(created_at, 'YYYY-MM') = %s
                        ORDER BY last_seen DESC NULLS LAST
                    """, conn, params=(pick_cohort, pick_cohort))
                    if df_coh_users.empty:
                        st.caption("لا أحد انضمّ في هذا الشهر.")
                    else:
                        df_coh_users["المصدر"] = df_coh_users["source"].map(_SRC_LABEL).fillna(df_coh_users["source"])
                        df_coh_users["الانضمام"] = pd.to_datetime(df_coh_users["joined"], errors="coerce").dt.strftime("%Y-%m-%d")
                        df_coh_users["آخر_ظهور"] = pd.to_datetime(df_coh_users["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d")
                        # نحسب «نشط/خامل» بناءً على last_seen
                        df_coh_users["الحالة"] = df_coh_users["last_seen"].apply(
                            lambda v: "🟢 نشط (آخر 7 يوم)" if pd.notna(v) and (pd.Timestamp.now(tz="UTC") - pd.to_datetime(v, utc=True, errors="coerce")).days <= 7
                            else "🟡 ظهر مؤخراً (8-30)" if pd.notna(v) and (pd.Timestamp.now(tz="UTC") - pd.to_datetime(v, utc=True, errors="coerce")).days <= 30
                            else "🔴 خامل (>30)"
                        )
                        show = df_coh_users[["المصدر","id","name","email","phone",
                                             "الانضمام","آخر_ظهور","الحالة"]].rename(
                            columns={"id":"ID","name":"الاسم","email":"الإيميل","phone":"الجوال"}).fillna("—")
                        st.dataframe(show, use_container_width=True, hide_index=True, height=380)
                        # ملخّص حالة الـ cohort
                        active_n = int((df_coh_users["الحالة"]=="🟢 نشط (آخر 7 يوم)").sum())
                        idle_n   = int((df_coh_users["الحالة"]=="🔴 خامل (>30)").sum())
                        st.caption(
                            f"📊 cohort {pick_cohort}: **{len(show):,}** انضمّوا · "
                            f"🟢 {active_n} نشطون · 🔴 {idle_n} خاملون → "
                            f"بقاء فعلي: **{(active_n*100/max(1,len(show))):.1f}%**"
                        )
                        st.download_button(
                            f"📥 CSV — cohort {pick_cohort}",
                            show.to_csv(index=False).encode("utf-8-sig"),
                            f"cohort_{pick_cohort}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_cohort_{pick_cohort}",
                        )

            st.divider()

        with _main_tabs[9]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_9",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 10 ─ 📊 ترتيب التفاعل (سحب مباشر من action_logs)
            # كان اسمه «LTV» — أُلغي. لا توجد لدينا بيانات إيرادات أو عمولة فعلية
            # تسمح بحساب LTV حقيقي. نعرض فقط أرقام مسحوبة مباشرة.
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 📊 ترتيب العملاء بالتفاعل الفعلي — مسحوب من action_logs")
            st.error(
                "⚠️ **تنبيه صدق:** كان هنا «LTV Score» بصيغة مُخترعة. حذفناه. "
                "نعرض الآن فقط أرقاماً حقيقية مسحوبة من القاعدة: نسخ، نقرات، متاجر فريدة، "
                "وآخر نشاط. **هذي ليست قيمة نقدية ولا توقّع — مجرد ترتيب بالنشاط.** "
                "لا تنشرها على إنها LTV."
            )

            try: conn.rollback()
            except Exception: pass

            ltv_src_clause, ltv_src_params = _ua_src_clause("al")
            ltv_raw = pd.read_sql(f"""
                SELECT
                  CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                  al.user_id,
                  COUNT(*) FILTER (WHERE al.action_type='copy_coupon')                    AS copies,
                  COUNT(*) FILTER (WHERE al.action_type='click_link')                     AS clicks,
                  COUNT(DISTINCT al.store_id) FILTER (WHERE al.action_type='copy_coupon') AS uniq_stores,
                  EXTRACT(EPOCH FROM (NOW() - MAX(al.action_time)))/86400.0               AS days_since
                FROM action_logs al
                WHERE al.user_id IS NOT NULL
                  { ltv_src_clause }
                GROUP BY src, al.user_id
                HAVING COUNT(*) FILTER (WHERE al.action_type='copy_coupon') > 0
            """, conn, params=ltv_src_params if ltv_src_params else None)

            if ltv_raw.empty:
                st.info("📭 لا توجد بيانات نسخ.")
            else:
                df_ltv = ltv_raw.copy()
                df_ltv["days_since"] = df_ltv["days_since"].fillna(9999).astype(float).round(1)
                # ترتيب بسيط بعدد النسخ ثم النقرات — لا معادلة مخترعة
                df_ltv = df_ltv.sort_values(["copies","clicks","uniq_stores"],
                                            ascending=[False,False,False]).reset_index(drop=True)
                df_ltv["rank"] = df_ltv.index + 1

                l1, l2, l3 = st.columns(3)
                with l1: kpi_card("👥", "عملاء نسخوا على الأقل مرة", f"{len(df_ltv):,}", "info")
                with l2: kpi_card("🎟️", "إجمالي النسخ", f"{int(df_ltv['copies'].sum()):,}", "emerald")
                with l3: kpi_card("🖱️", "إجمالي النقرات", f"{int(df_ltv['clicks'].sum()):,}", "warning")

                # Top-100 + JOIN لمعرفة الهوية
                top_ids_web = df_ltv[df_ltv["src"]=="web"]["user_id"].head(100).tolist()
                top_ids_bot = df_ltv[df_ltv["src"]=="bot"]["user_id"].head(100).tolist()
                top_meta_parts = []
                if top_ids_web:
                    ph = ",".join(["%s"]*len(top_ids_web))
                    top_meta_parts.append((f"""
                        SELECT 'web' AS src, id AS user_id, display_name AS name, email,
                               phone_number AS phone, telegram_username AS tg,
                               { _norm_city_sql('city') } AS city
                        FROM web_users WHERE id IN ({ph})
                    """, top_ids_web))
                if top_ids_bot:
                    ph = ",".join(["%s"]*len(top_ids_bot))
                    top_meta_parts.append((f"""
                        SELECT 'bot' AS src, telegram_id AS user_id, username AS name, NULL AS email,
                               NULL AS phone, username AS tg,
                               { _norm_city_sql('city') } AS city
                        FROM bot_users WHERE telegram_id IN ({ph})
                    """, top_ids_bot))
                meta_dfs = []
                for q, p in top_meta_parts:
                    meta_dfs.append(pd.read_sql(q, conn, params=tuple(p)))
                top_meta = pd.concat(meta_dfs, ignore_index=True) if meta_dfs else pd.DataFrame()

                if not top_meta.empty:
                    top_view = df_ltv.head(100).merge(top_meta, on=["src","user_id"], how="left")
                    top_view["المصدر"]  = top_view["src"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                    top_view["تيليجرام"] = top_view["tg"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                    top_show = top_view[["rank","المصدر","name","email","phone","تيليجرام","city",
                                         "copies","clicks","uniq_stores","days_since"]].rename(
                        columns={"rank":"#","name":"الاسم","email":"الإيميل","phone":"الجوال","city":"المدينة",
                                 "copies":"نسخ","clicks":"نقرات","uniq_stores":"متاجر_فريدة",
                                 "days_since":"أيام_منذ_آخر_نشاط"}).fillna("—")
                    st.markdown("#### 🏅 Top 100 بالتفاعل الفعلي")
                    st.caption("مرتّبون بـ: نسخ ↓ ثم نقرات ↓ ثم متاجر فريدة ↓. **لا معادلة مشتقّة.** كل الأعمدة سحب مباشر من action_logs.")
                    st.dataframe(top_show, use_container_width=True, hide_index=True, height=380)
                    st.download_button("📥 CSV — Top 100",
                                       top_show.to_csv(index=False).encode("utf-8-sig"),
                                       f"top100_engagement_{date.today()}.csv", "text/csv",
                                       key="ua_dl_top100")

            st.divider()

        with _main_tabs[10]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_10",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 11 ─ 🔻 Funnel Conversion (search → view_tag → click → copy)
            # كم نسبة المسجّلين الذين بحثوا؟ شاهدوا قسم؟ نقروا؟ نسخوا؟
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 🔻 Funnel — أين يسقط الناس في الطريق؟")
            st.caption(
                f"📅 النطاق: **{date_from.strftime('%Y-%m-%d')} → "
                f"{date_to.strftime('%Y-%m-%d')}** · يطبّق فلتر المصدر."
            )
            with st.expander("ℹ️ شرح الـ Funnel — كيف يقرأ ولماذا الأرقام تنزل دائماً؟", expanded=False):
                st.markdown("""
**كل مرحلة subset من المرحلة السابقة** — يعني الشخص لا ينتقل للمرحلة التالية إلا إذا أتمّ السابقة. لذا الأرقام تنزل من الأعلى للأسفل دائماً.

| المرحلة | شرطها |
|---|---|
| 👥 **وصلوا** | عمل أي حركة في النطاق (دخل، بحث، نسخ، نقر، أي شي) |
| 🌐 **تصفّحوا** | وصلوا **+** بحثوا أو فتحوا قسماً أو عرضوا قائمة متاجر |
| 🖱️ **نقروا** | تصفّحوا **+** نقروا رابط متجر واحد على الأقل |
| 🎟️ **نسخوا (تحويل ناجح)** | نقروا **+** نسخوا كوبون واحد على الأقل |

**السقوط** بين مرحلتين = عدد من وصل للسابقة لكن لم يكمل للحالية. الأكبر = نقطة الانهيار التي تحتاج تحسين.

🔍 **مثال:** لو وصل ١٠٠، وتصفّح ٦٠، ونقر ٣٠، ونسخ ١٥ → معدّل التحويل النهائي ١٥٪، أكبر سقوط بين «وصلوا» و«تصفّحوا» (٤٠ سقطوا → ربما الواجهة الأولى مو جذابة).
                """)

            try: conn.rollback()
            except Exception: pass

            fun_clause, fun_params = _ua_src_clause("al")
            # مسار صارم: كل مرحلة subset من السابقة (BOOL_OR لكل شخص)
            df_fun = pd.read_sql(f"""
                WITH user_acts AS (
                  SELECT
                    CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                    al.user_id,
                    BOOL_OR(al.action_type IN ('search','view_tag','view_all',
                                               'view_trending','view_categories',
                                               'view_favorites'))            AS did_browse,
                    BOOL_OR(al.action_type='click_link')                      AS did_click,
                    BOOL_OR(al.action_type='copy_coupon')                     AS did_copy
                  FROM action_logs al
                  WHERE al.action_time >= %s AND al.action_time < %s
                    AND al.user_id IS NOT NULL
                    { fun_clause }
                  GROUP BY src, al.user_id
                )
                SELECT
                  COUNT(*)                                                              AS reached,
                  COUNT(*) FILTER (WHERE did_browse)                                    AS browsed,
                  COUNT(*) FILTER (WHERE did_browse AND did_click)                      AS clicked,
                  COUNT(*) FILTER (WHERE did_browse AND did_click AND did_copy)         AS copied
                FROM user_acts
            """, conn, params=tuple([_t_from, _t_to] + fun_params))

            r = df_fun.iloc[0]
            funnel_steps = [
                ("👥 وصلوا للمنصة",       int(r["reached"] or 0)),
                ("🌐 تصفّحوا (بحث/قسم/قائمة)", int(r["browsed"] or 0)),
                ("🖱️ نقروا متجراً",        int(r["clicked"] or 0)),
                ("🎟️ نسخوا كوبوناً ✓",     int(r["copied"]  or 0)),
            ]
            df_funnel = pd.DataFrame(funnel_steps, columns=["المرحلة","العدد"])
            # نسب التحويل
            df_funnel["% من السابق"] = [100.0] + [
                round(100.0*df_funnel["العدد"].iloc[i] /
                      max(1, df_funnel["العدد"].iloc[i-1]), 1)
                for i in range(1, len(df_funnel))
            ]
            df_funnel["% من القمة"] = [
                round(100.0*v / max(1, df_funnel["العدد"].iloc[0]), 1)
                for v in df_funnel["العدد"]
            ]

            fc1, fc2 = st.columns([2, 1])
            with fc1:
                fig_fun = go.Figure(go.Funnel(
                    y=df_funnel["المرحلة"],
                    x=df_funnel["العدد"],
                    textinfo="value+percent initial",
                    marker=dict(color=["#3B82F6","#06B6D4","#F59E0B","#10B981"]),
                ))
                fig_fun.update_layout(title="مسار التحويل")
                st.plotly_chart(apply_brand_theme(fig_fun), use_container_width=True)
            with fc2:
                st.markdown("#### 📊 نسب الانتقال")
                st.dataframe(df_funnel, use_container_width=True, hide_index=True)
                # كشف أكبر نقطة سقوط
                drop = []
                for i in range(1, len(df_funnel)):
                    prev = df_funnel["العدد"].iloc[i-1]
                    cur  = df_funnel["العدد"].iloc[i]
                    if prev > 0:
                        drop.append((df_funnel["المرحلة"].iloc[i-1], df_funnel["المرحلة"].iloc[i],
                                     prev - cur, round((prev-cur)*100/prev, 1)))
                if drop:
                    worst = max(drop, key=lambda x: x[2])
                    st.error(
                        f"🔴 أكبر سقوط:\n\n"
                        f"بين **{worst[0]}** و **{worst[1]}** سقط **{worst[2]:,}** شخص "
                        f"(**{worst[3]}%**)."
                    )

            # ─── drill-down: مين في كل مرحلة + مين سقط ──────────────
            st.markdown("#### 🔍 مين في كل مرحلة؟ + مين سقط بين كل مرحلتين؟")
            st.caption("اختر مرحلة لرؤية الأشخاص فيها، أو «سقط بين X و Y» لرؤية المتسرّبين.")

            # المسار المتدرّج (subset): نسخوا ⊆ نقروا ⊆ تصفّحوا ⊆ وصلوا
            step_keys = ["وصلوا", "تصفّحوا", "نقروا", "نسخوا"]
            step_filters = {
                "وصلوا":     "TRUE",                                          # كل من له حركة في النطاق
                "تصفّحوا":  "EXISTS (SELECT 1 FROM action_logs al2 WHERE al2.user_id = base.user_id "
                              "AND base.src = (CASE WHEN al2.source='web' THEN 'web' ELSE 'bot' END) "
                              "AND al2.action_type IN ('search','view_tag','view_all','view_trending','view_categories','view_favorites') "
                              "AND al2.action_time >= %s AND al2.action_time < %s)",
                "نقروا":    "EXISTS (SELECT 1 FROM action_logs al2 WHERE al2.user_id = base.user_id "
                              "AND base.src = (CASE WHEN al2.source='web' THEN 'web' ELSE 'bot' END) "
                              "AND al2.action_type='click_link' AND al2.action_time >= %s AND al2.action_time < %s)",
                "نسخوا":     "EXISTS (SELECT 1 FROM action_logs al2 WHERE al2.user_id = base.user_id "
                              "AND base.src = (CASE WHEN al2.source='web' THEN 'web' ELSE 'bot' END) "
                              "AND al2.action_type='copy_coupon' AND al2.action_time >= %s AND al2.action_time < %s)",
            }

            # تركيب الـ AND للمراحل المتدرّجة (كل مرحلة subset)
            step_cumulative = {
                "وصلوا":     "TRUE",
                "تصفّحوا":  step_filters["تصفّحوا"],
                "نقروا":    f"({step_filters['تصفّحوا']}) AND ({step_filters['نقروا']})",
                "نسخوا":     f"({step_filters['تصفّحوا']}) AND ({step_filters['نقروا']}) AND ({step_filters['نسخوا']})",
            }
            step_cum_params = {
                "وصلوا":     0,
                "تصفّحوا":  1,
                "نقروا":    2,
                "نسخوا":     3,
            }

            for i, step in enumerate(step_keys):
                step_label = ["👥 وصلوا للمنصة","🌐 تصفّحوا","🖱️ نقروا","🎟️ نسخوا (تحويل ناجح)"][i]
                with st.expander(f"{step_label} — مين هم؟"):
                    try: conn.rollback()
                    except Exception: pass
                    # نستخدم step_cumulative للحصول على strict subset
                    extra_clause = ""
                    extra_params = []
                    if step != "وصلوا":
                        extra_clause = "AND " + step_cumulative[step]
                        extra_params = [_t_from, _t_to] * step_cum_params[step]
                    df_step = pd.read_sql(f"""
                        WITH base AS (
                          SELECT DISTINCT
                            CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                            al.user_id
                          FROM action_logs al
                          WHERE al.action_time >= %s AND al.action_time < %s
                            AND al.user_id IS NOT NULL
                            { fun_clause }
                        )
                        SELECT base.src AS source, base.user_id,
                               COALESCE(wu.display_name, bu.username, '—') AS الاسم,
                               wu.email AS الإيميل, wu.phone_number AS الجوال,
                               bu.username AS التيليجرام
                          FROM base
                          LEFT JOIN web_users wu ON base.src='web' AND wu.id = base.user_id
                          LEFT JOIN bot_users bu ON base.src='bot' AND bu.telegram_id = base.user_id
                         WHERE TRUE { extra_clause }
                    """, conn, params=tuple([_t_from, _t_to] + fun_params + extra_params))
                    if df_step.empty:
                        st.caption("لا أحد في هذه المرحلة.")
                    else:
                        df_step["المصدر"] = df_step["source"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                        df_step["التيليجرام"] = df_step["التيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                        show = df_step[["المصدر","الاسم","الإيميل","الجوال","التيليجرام"]].fillna("—")
                        st.dataframe(show, use_container_width=True, hide_index=True, height=280)
                        st.caption(f"📊 {len(show):,} شخص في «{step}»")
                        st.download_button(
                            f"📥 CSV — {step}",
                            show.to_csv(index=False).encode("utf-8-sig"),
                            f"funnel_step_{step}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_fun_step_{i}",
                        )

            # السقوط بين كل مرحلتين (cumulative)
            st.markdown("##### 🔻 المتسرّبون بين كل مرحلتين")
            for i in range(1, len(step_keys)):
                prev_step = step_keys[i-1]
                cur_step  = step_keys[i]
                prev_label = ["👥 وصلوا","🌐 تصفّحوا","🖱️ نقروا"][i-1]
                cur_label  = ["🌐 تصفّحوا","🖱️ نقروا","🎟️ نسخوا"][i-1]
                with st.expander(f"🔻 سقطوا بين «{prev_label}» و «{cur_label}»"):
                    try: conn.rollback()
                    except Exception: pass
                    # وصلوا للسابق (cumulative) لكن لم يكملوا للحالي (الفلتر الجديد فقط)
                    prev_clause = step_cumulative[prev_step]
                    cur_clause  = step_filters[cur_step]   # الفلتر الإضافي فقط للحالي
                    prev_params = [_t_from, _t_to] * step_cum_params[prev_step]
                    cur_params  = [_t_from, _t_to]
                    df_dropoff = pd.read_sql(f"""
                        WITH base AS (
                          SELECT DISTINCT
                            CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                            al.user_id
                          FROM action_logs al
                          WHERE al.action_time >= %s AND al.action_time < %s
                            AND al.user_id IS NOT NULL
                            { fun_clause }
                        )
                        SELECT base.src AS source, base.user_id,
                               COALESCE(wu.display_name, bu.username, '—') AS الاسم,
                               wu.email AS الإيميل, wu.phone_number AS الجوال,
                               bu.username AS التيليجرام
                          FROM base
                          LEFT JOIN web_users wu ON base.src='web' AND wu.id = base.user_id
                          LEFT JOIN bot_users bu ON base.src='bot' AND bu.telegram_id = base.user_id
                         WHERE ({prev_clause})
                           AND NOT ({cur_clause})
                    """, conn, params=tuple(
                        [_t_from, _t_to] + fun_params + prev_params + cur_params
                    ))
                    if df_dropoff.empty:
                        st.success("✅ لا أحد سقط — كل من في المرحلة السابقة وصلوا للحالية.")
                    else:
                        df_dropoff["المصدر"] = df_dropoff["source"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                        df_dropoff["التيليجرام"] = df_dropoff["التيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                        show = df_dropoff[["المصدر","الاسم","الإيميل","الجوال","التيليجرام"]].fillna("—")
                        st.dataframe(show, use_container_width=True, hide_index=True, height=260)
                        st.warning(f"⚠️ **{len(show):,}** شخص وصلوا «{prev_step}» ولم يصلوا «{cur_step}» — broadcast استرجاع.")
                        st.download_button(
                            f"📥 CSV — متسرّبون {prev_step} → {cur_step}",
                            show.to_csv(index=False).encode("utf-8-sig"),
                            f"funnel_dropoff_{i}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_dropoff_{i}",
                        )

            st.divider()

        with _main_tabs[11]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_11",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 12 ─ 🗺️ خريطة جغرافية حية (السعودية + الباقي)
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 🗺️ التوزّع الجغرافي")
            st.caption(
                f"تجميع المستخدمين النشطين في النطاق **{date_from.strftime('%Y-%m-%d')} → "
                f"{date_to.strftime('%Y-%m-%d')}** حسب المدينة. مصدر المدينة: ip-enrichment + ملف المستخدم."
            )

            try: conn.rollback()
            except Exception: pass

            geo_clause, geo_params = _ua_src_clause("al")
            # المدينة: أولاً من action_logs (CF Worker IP enrichment).
            # لو NULL (الميني-ويب غالباً) نرجع لمدينة bot_users/web_users.
            # ثم نوحّد العربي/الإنجليزي بـ _norm_city_sql.
            _city_resolved = f"""COALESCE(
                NULLIF(TRIM(al.city), ''),
                NULLIF(TRIM(bu.city), ''),
                NULLIF(TRIM(wu.city), '')
            )"""
            df_geo = pd.read_sql(f"""
                SELECT
                  COALESCE({ _norm_city_sql(_city_resolved) }, 'غير معروف')        AS المدينة,
                  COUNT(DISTINCT al.user_id)                                       AS مستخدمون,
                  COUNT(*) FILTER (WHERE al.action_type='copy_coupon')             AS نسخ,
                  COUNT(*) FILTER (WHERE al.action_type='click_link')              AS نقرات
                FROM action_logs al
                LEFT JOIN bot_users bu
                       ON bu.telegram_id = al.user_id
                      AND COALESCE(al.source,'bot') IN ('bot','telegram_miniapp','miniapp')
                LEFT JOIN web_users wu
                       ON wu.id = al.user_id
                      AND al.source = 'web'
                WHERE al.action_time >= %s AND al.action_time < %s
                  AND al.user_id IS NOT NULL
                  { geo_clause }
                GROUP BY 1
                HAVING COUNT(DISTINCT al.user_id) >= 1
                ORDER BY مستخدمون DESC
                LIMIT 30
            """, conn, params=tuple([_t_from, _t_to] + geo_params))

            if df_geo.empty:
                st.info("📭 لا توجد بيانات جغرافية كافية بهذا الفلتر.")
            else:
                df_geo["نشاط_للمستخدم"] = (
                    (df_geo["نسخ"] + df_geo["نقرات"]*0.5) /
                    df_geo["مستخدمون"].replace(0, 1)
                ).round(2)

                g1, g2 = st.columns([2, 1])
                with g1:
                    fig_geo = px.bar(
                        df_geo.head(20), x="مستخدمون", y="المدينة", orientation="h",
                        color="نشاط_للمستخدم", color_continuous_scale="Greens",
                        text="مستخدمون",
                        title="أعلى 20 مدينة — حجم المستخدمين × كثافة التفاعل",
                    )
                    fig_geo.update_layout(yaxis=dict(autorange="reversed"))
                    st.plotly_chart(apply_brand_theme(fig_geo), use_container_width=True)
                with g2:
                    st.markdown(f"#### 📍 ملخّص")
                    kpi_card("🏙️", "مدن مغطّاة", f"{len(df_geo):,}", "info")
                    if len(df_geo) > 0:
                        top1 = df_geo.iloc[0]
                        kpi_card("🥇", "المدينة الأعلى", str(top1["المدينة"]), "emerald",
                                 note=f"{int(top1['مستخدمون']):,} مستخدم")
                    # نسبة الـ top3 من الإجمالي
                    if len(df_geo) >= 3:
                        top3_share = (df_geo.head(3)["مستخدمون"].sum() *100.0 /
                                      max(1, df_geo["مستخدمون"].sum()))
                        kpi_card("🎯", "حصة أعلى 3 مدن", f"{top3_share:.1f}%", "warning",
                                 note="من إجمالي النشطين")

                st.dataframe(df_geo, use_container_width=True, hide_index=True, height=280)
                st.download_button("📥 CSV — التوزّع الجغرافي",
                                   df_geo.to_csv(index=False).encode("utf-8-sig"),
                                   f"geo_{date.today()}.csv", "text/csv",
                                   key="ua_dl_geo")

                # ─── drill-down لكل مدينة ──────────────────────────
                st.markdown("#### 🔍 مين في كل مدينة؟")
                st.caption("اختر مدينة لرؤية كل العملاء فيها مع تفاصيل تفاعلهم.")
                city_pick = st.selectbox(
                    "📍 اختر مدينة:",
                    options=df_geo["المدينة"].tolist(),
                    key=f"ua_geo_city_{_src_choice}",
                )
                if city_pick:
                    try: conn.rollback()
                    except Exception: pass
                    _city_resolved2 = f"""COALESCE(
                        NULLIF(TRIM(al.city),''),
                        NULLIF(TRIM(bu.city),''),
                        NULLIF(TRIM(wu.city),'')
                    )"""
                    df_city = pd.read_sql(f"""
                        WITH agg AS (
                          SELECT
                            CASE WHEN al.source='web' THEN 'web' ELSE 'bot' END AS src,
                            al.user_id,
                            COUNT(*) FILTER (WHERE al.action_type='copy_coupon')  AS نسخ,
                            COUNT(*) FILTER (WHERE al.action_type='click_link')   AS نقرات,
                            MAX(al.action_time) AS last_act
                          FROM action_logs al
                          LEFT JOIN bot_users bu ON bu.telegram_id = al.user_id
                                                AND COALESCE(al.source,'bot') IN ('bot','telegram_miniapp','miniapp')
                          LEFT JOIN web_users wu ON wu.id = al.user_id AND al.source = 'web'
                          WHERE al.action_time >= %s AND al.action_time < %s
                            AND al.user_id IS NOT NULL
                            { geo_clause }
                            AND { _norm_city_sql(_city_resolved2) } = %s
                          GROUP BY src, al.user_id
                        )
                        SELECT a.src AS source,
                               COALESCE(wu.display_name, bu.username, '—') AS الاسم,
                               wu.email AS الإيميل, wu.phone_number AS الجوال,
                               bu.username AS التيليجرام,
                               a.نسخ, a.نقرات, a.last_act
                          FROM agg a
                          LEFT JOIN web_users wu ON a.src='web' AND wu.id = a.user_id
                          LEFT JOIN bot_users bu ON a.src='bot' AND bu.telegram_id = a.user_id
                         ORDER BY (a.نسخ + a.نقرات) DESC
                    """, conn, params=tuple([_t_from, _t_to] + geo_params + [city_pick]))
                    if df_city.empty:
                        st.caption("لا تفاعلات من هذه المدينة في النطاق.")
                    else:
                        df_city["المصدر"] = df_city["source"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                        df_city["التيليجرام"] = df_city["التيليجرام"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                        df_city["آخر_فعل"] = pd.to_datetime(df_city["last_act"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
                        show = df_city[["المصدر","الاسم","الإيميل","الجوال","التيليجرام",
                                        "نسخ","نقرات","آخر_فعل"]].fillna("—")
                        st.dataframe(show, use_container_width=True, hide_index=True, height=320)
                        st.caption(f"📊 {len(show):,} مستخدم في «{city_pick}»")
                        st.download_button(
                            f"📥 CSV — {city_pick}",
                            show.to_csv(index=False).encode("utf-8-sig"),
                            f"city_{city_pick}_{date.today()}.csv", "text/csv",
                            key=f"ua_dl_city_{city_pick}",
                        )

            st.divider()

        with _main_tabs[12]:
            _src_choice = st.radio(
                "📡 المصدر:",
                ["الكل", "🤖 البوت", "🌐 الموقع", "🔹 الميني-ويب"],
                horizontal=True, key=f"ua_src_tab_12",
            )
            _src_tuple = _SRC_SQL.get(_src_choice)
            # ════════════════════════════════════════════════════════════════
            # SECTION 13 ─ 🔔 Action Center + Anomalies (تنبيهات + Broadcast)
            # ════════════════════════════════════════════════════════════════
            st.markdown("## 🔔 مركز التنبيهات والإجراء الفوري")
            st.caption("شذوذات سلوكية + شرائح جاهزة للإرسال لمركز الإشعارات.")

            try: conn.rollback()
            except Exception: pass

            # 1) شذوذ: مستخدم كان نشطاً جداً ثم انخفض > 70%
            df_anom = pd.read_sql(f"""
                WITH base AS (
                  SELECT
                    CASE WHEN source='web' THEN 'web' ELSE 'bot' END AS src,
                    user_id,
                    COUNT(*) FILTER (WHERE action_time >= NOW() - INTERVAL '60 days'
                                     AND action_time < NOW() - INTERVAL '30 days'
                                     AND action_type IN ('copy_coupon','click_link')) AS prev_acts,
                    COUNT(*) FILTER (WHERE action_time >= NOW() - INTERVAL '30 days'
                                     AND action_type IN ('copy_coupon','click_link')) AS now_acts,
                    MAX(action_time) AS last_seen
                  FROM action_logs
                  WHERE user_id IS NOT NULL
                  GROUP BY src, user_id
                  HAVING COUNT(*) FILTER (WHERE action_time >= NOW() - INTERVAL '60 days'
                                          AND action_time < NOW() - INTERVAL '30 days'
                                          AND action_type IN ('copy_coupon','click_link')) >= 10
                     AND COUNT(*) FILTER (WHERE action_time >= NOW() - INTERVAL '30 days'
                                          AND action_type IN ('copy_coupon','click_link')) <
                         0.30 * COUNT(*) FILTER (WHERE action_time >= NOW() - INTERVAL '60 days'
                                                 AND action_time < NOW() - INTERVAL '30 days'
                                                 AND action_type IN ('copy_coupon','click_link'))
                )
                SELECT b.src, b.user_id, b.prev_acts, b.now_acts, b.last_seen,
                       ROUND(100.0*(b.prev_acts - b.now_acts)/NULLIF(b.prev_acts,0), 1) AS drop_pct,
                       COALESCE(wu.display_name, bu.username, '—') AS name,
                       wu.email, wu.phone_number AS phone, bu.username AS tg
                  FROM base b
                  LEFT JOIN web_users wu ON b.src='web' AND wu.id = b.user_id
                  LEFT JOIN bot_users bu ON b.src='bot' AND bu.telegram_id = b.user_id
                 ORDER BY b.prev_acts DESC
                 LIMIT 200
            """, conn)

            st.markdown("### ⚡ شذوذ: انخفاض حاد في النشاط")
            st.caption("كانوا نشطين (≥10 تفاعل) قبل 30-60 يوم، الآن نشاطهم تراجع > 70%. أرسل عرض إنقاذ.")
            if df_anom.empty:
                st.success("✅ لا توجد حالات شذوذ — استقرار جيد.")
            else:
                an_show = df_anom.copy()
                an_show["المصدر"]   = an_show["src"].map({"web":"🌐 الموقع","bot":"🤖 البوت"})
                an_show["تيليجرام"] = an_show["tg"].apply(lambda s: f"@{s}" if isinstance(s,str) and s else "—")
                an_show["آخر_نشاط"] = pd.to_datetime(an_show["last_seen"], errors="coerce").dt.strftime("%Y-%m-%d")
                an_show = an_show[["المصدر","name","email","phone","تيليجرام",
                                   "prev_acts","now_acts","drop_pct","آخر_نشاط"]].rename(
                    columns={"name":"الاسم","email":"الإيميل","phone":"الجوال",
                             "prev_acts":"نشاط_قبل","now_acts":"نشاط_الآن",
                             "drop_pct":"%_التراجع"}).fillna("—")
                st.dataframe(an_show, use_container_width=True, hide_index=True, height=320)
                ac1, ac2 = st.columns(2)
                with ac1:
                    st.download_button("📥 CSV — حالات الشذوذ",
                                       an_show.to_csv(index=False).encode("utf-8-sig"),
                                       f"anomaly_drop_{date.today()}.csv", "text/csv",
                                       key="ua_dl_anom")
                with ac2:
                    if st.button("📨 أرسل قائمة الشذوذ لمركز الإشعارات", key="ua_anom_notify"):
                        st.session_state["broadcast_audience"] = {
                            "rows":   an_show.to_dict(orient="records"),
                            "count":  len(an_show),
                            "source": "Anomaly: Activity Drop > 70%",
                            "ts":     date.today().isoformat(),
                        }
                        st.success(f"✅ تم تجهيز {len(an_show):,} للإرسال.")

            # 2) لوحة Audience مُحضّرة (إن وُجدت من أي قسم)
            if "broadcast_audience" in st.session_state:
                st.divider()
                st.markdown("### 📦 شريحة جاهزة للإرسال (Pending)")
                ba = st.session_state["broadcast_audience"]
                mb1, mb2, mb3 = st.columns([1,1,2])
                with mb1: kpi_card("👥", "العدد", f"{ba['count']:,}", "emerald")
                with mb2: kpi_card("🏷️", "المصدر", ba["source"], "info")
                with mb3:
                    st.caption(f"تم التجهيز: {ba['ts']}")
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("🗑️ مسح القائمة", key="ua_clear_aud"):
                            del st.session_state["broadcast_audience"]
                            st.rerun()
                    with cb2:
                        st.info("افتح صفحة «مركز الإشعارات» للإرسال.")


    except Exception as e:
        st.error(f"⚠️ خطأ في صفحة التحليلات: {e}")
        import traceback
        with st.expander("تفاصيل الخطأ (تقصّي)"):
            st.code(traceback.format_exc())
    finally:
        if 'conn' in locals():
            try: conn.close()
            except Exception: pass


# --- مركز الإشعارات (Telegram + Email Marketing) ---
elif page == "مركز الإشعارات":
    page_title("📢", "مركز البث والإشعارات الجماعية")

    # ── دالة إرسال البريد الإلكتروني ─────────────────────────────────────────
    def _send_campaign_email(to_email: str, subject: str, html_body: str) -> bool:
        """Resend API أولاً، ثم SMTP احتياطياً."""
        resend_key = os.getenv("RESEND_API_KEY")
        smtp_user  = os.getenv("SMTP_USER")
        smtp_pass  = (os.getenv("SMTP_PASS") or "").replace(" ", "")
        smtp_host  = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port  = int(os.getenv("SMTP_PORT", "587"))
        smtp_from  = os.getenv("SMTP_FROM", smtp_user or "onboarding@resend.dev")
        from_name  = os.getenv("SMTP_FROM_NAME", "نبض الصفقات")

        if resend_key:
            try:
                resp = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}",
                             "Content-Type": "application/json"},
                    json={"from": f"{from_name} <{smtp_from}>",
                          "to": [to_email], "subject": subject, "html": html_body},
                    timeout=15,
                )
                return resp.status_code in (200, 201, 202)
            except Exception:
                return False

        if smtp_user and smtp_pass:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = f"{from_name} <{smtp_from}>"
                msg["To"]      = to_email
                msg.attach(MIMEText(html_body, "html", "utf-8"))
                ipv4 = socket.gethostbyname(smtp_host)
                if smtp_port == 465:
                    with smtplib.SMTP_SSL(ipv4, smtp_port, timeout=20) as srv:
                        srv.login(smtp_user, smtp_pass)
                        srv.send_message(msg)
                else:
                    with smtplib.SMTP(ipv4, smtp_port, timeout=20) as srv:
                        srv.ehlo(); srv.starttls(); srv.ehlo()
                        srv.login(smtp_user, smtp_pass)
                        srv.send_message(msg)
                return True
            except Exception:
                return False
        return False

    # ── تبويبان رئيسيان ───────────────────────────────────────────────────────
    tab_tg, tab_email = st.tabs(["📱 إشعارات تليجرام", "✉️ حملات البريد الإلكتروني"])

    # ═══════════════════════════════════════════════════════════════════════════
    # تبويب 1 — إشعارات تليجرام
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_tg:
        st.info("نصيحة: الرسائل التي تحتوي على صور تحقق تفاعلاً أعلى بنسبة 40%.")
        try:
            conn = get_conn()
            users_df = pd.read_sql(
                "SELECT telegram_id, username, user_status, last_seen FROM bot_users", conn)
            total_users = len(users_df)
            now = pd.Timestamp.now()
            active_24h_df    = users_df[users_df['last_seen'] >= (now - pd.Timedelta(hours=24))]
            inactive_week_df = users_df[users_df['last_seen'] <  (now - pd.Timedelta(days=7))]
            active_normal_df = users_df[
                (users_df['last_seen'] < (now - pd.Timedelta(hours=24))) &
                (users_df['last_seen'] >= (now - pd.Timedelta(days=7)))]

            col_input, col_preview = st.columns([1.5, 1])
            with col_input:
                st.subheader("🖋️ تجهيز المحتوى")
                msg_text  = st.text_area("نص الرسالة:",
                    placeholder="مثال: أقوى عروض اليوم في متجر نون 🔥.. استخدم كود (B4) لخصم إضافي!",
                    height=150, key="tg_msg")
                msg_image = st.text_input("رابط صورة العرض (اختياري):",
                    placeholder="https://example.com/promo.jpg", key="tg_img")
                audience  = st.selectbox("الفئة المستهدفة:",
                    ["الكل","نشط (خلال 24 ساعة)","نشط (اعتيادي)","خامل (أكثر من أسبوع)"],
                    key="tg_aud")
                target_df = (users_df if audience == "الكل"
                             else active_24h_df if audience == "نشط (خلال 24 ساعة)"
                             else active_normal_df if audience == "نشط (اعتيادي)"
                             else inactive_week_df)
                st.divider()
                if st.button("🚀 إرسال الرسالة الآن", width='stretch', key="tg_send"):
                    if not msg_text:
                        st.error("يا برنس، ما يصير نرسل رسالة فاضية! اكتب شي.")
                    elif len(target_df) == 0:
                        st.warning(f"لا يوجد مستخدمين ضمن فئة ({audience}) حالياً.")
                    else:
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO broadcast_logs (message_text,image_url,target_audience,delivery_count) "
                            "VALUES (%s,%s,%s,%s)",
                            (msg_text, msg_image, audience, len(target_df)))
                        conn.commit()
                        st.success(f"✅ تمت جدولة إرسال {len(target_df)} رسالة لـ ({audience}) بنجاح!")
                        st.balloons()

            with col_preview:
                st.subheader("📱 معاينة في جوال العميل")
                with st.container(border=True):
                    if msg_image:
                        st.image(msg_image, width='stretch')
                    if msg_text:
                        st.markdown("**المصدر:** [Tawfeer Intelligence Engine]")
                        st.write(msg_text)
                        st.caption("🕒 يُرسل الآن...")
                    else:
                        st.caption("اكتب نص الرسالة لتظهر المعاينة هنا...")
                st.divider()
                st.markdown("### 📊 ملخص الجمهور")
                st.write(f"👥 **العدد الكلي للمشتركين:** `{total_users}`")
                with st.container(border=True):
                    st.write(f"🟢 نشط (24 ساعة): `{len(active_24h_df)}`")
                    st.write(f"🟡 نشط (اعتيادي): `{len(active_normal_df)}`")
                    st.write(f"🔴 خامل (+أسبوع):  `{len(inactive_week_df)}`")
                    st.divider()
                    st.metric("🎯 المستهدفين حالياً", len(target_df))

            st.divider()
            with st.expander("📜 سجل الرسائل المرسلة (آخر 10 حملات)"):
                history_df = pd.read_sql("""
                    SELECT sent_at as "تاريخ الإرسال", target_audience as "الفئة",
                           delivery_count as "العدد", message_text as "المحتوى"
                    FROM broadcast_logs ORDER BY sent_at DESC LIMIT 10
                """, conn)
                if not history_df.empty:
                    st.dataframe(history_df, width='stretch')
                else:
                    st.info("لا توجد حملات إرسال سابقة موثقة.")

        except Exception as e:
            st.error(f"حدث خطأ في إشعارات تليجرام: {e}")
        finally:
            if 'conn' in locals(): conn.close()

    # ═══════════════════════════════════════════════════════════════════════════
    # تبويب 2 — حملات البريد الإلكتروني
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_email:
        try:
            conn = get_conn()
            conn.autocommit = True

            # إحصاءات مستخدمي الموقع
            web_kpi = pd.read_sql("""
                SELECT
                    COUNT(*)                                                                           AS total,
                    COUNT(*) FILTER (WHERE last_seen >= NOW()-INTERVAL '1 day')                       AS active_24h,
                    COUNT(*) FILTER (WHERE last_seen <  NOW()-INTERVAL '1 day'
                                      AND  last_seen >= NOW()-INTERVAL '7 days')                      AS active_normal,
                    COUNT(*) FILTER (WHERE last_seen <  NOW()-INTERVAL '7 days' OR last_seen IS NULL) AS inactive,
                    COUNT(email) FILTER (WHERE email IS NOT NULL AND email <> '')                      AS with_email
                FROM web_users WHERE password_hash IS NOT NULL
            """, conn)
            kpi = web_kpi.iloc[0]

            col_build, col_prev = st.columns([3, 2])

            # ── عمود البناء ──────────────────────────────────────────────────
            with col_build:
                st.subheader("✉️ بناء الحملة البريدية")

                em_subject = st.text_input(
                    "📌 عنوان الإيميل (Subject):",
                    placeholder="مثال: عروض حصرية لك اليوم 🔥 — نبض الصفقات",
                    key="em_subject")
                em_banner = st.text_input(
                    "🖼️ رابط صورة البانر (اختياري):",
                    placeholder="https://...", key="em_banner")

                em_mode = st.radio(
                    "نوع المحتوى:", ["نص بسيط", "HTML متقدم"],
                    horizontal=True, key="em_mode")
                if em_mode == "نص بسيط":
                    em_body_raw = st.text_area(
                        "نص الإيميل:",
                        placeholder="اكتب محتوى الحملة هنا...\nيدعم الأسطر المتعددة.",
                        height=200, key="em_body_plain")
                    em_body_html = em_body_raw.replace("\n", "<br>") if em_body_raw else ""
                else:
                    em_body_html = st.text_area(
                        "كود HTML:",
                        placeholder="<h2>أهلاً بك!</h2>\n<p>اكتب HTML هنا...</p>",
                        height=200, key="em_body_html")

                em_audience = st.selectbox(
                    "👥 الجمهور المستهدف:",
                    ["الكل","نشط (خلال 24 ساعة)","نشط (اعتيادي)","خامل (أكثر من أسبوع)"],
                    key="em_audience")

                _aud_sql = {
                    "الكل":
                        "password_hash IS NOT NULL AND email IS NOT NULL AND email <> ''",
                    "نشط (خلال 24 ساعة)":
                        "password_hash IS NOT NULL AND email IS NOT NULL AND email <> '' "
                        "AND last_seen >= NOW()-INTERVAL '1 day'",
                    "نشط (اعتيادي)":
                        "password_hash IS NOT NULL AND email IS NOT NULL AND email <> '' "
                        "AND last_seen < NOW()-INTERVAL '1 day' "
                        "AND last_seen >= NOW()-INTERVAL '7 days'",
                    "خامل (أكثر من أسبوع)":
                        "password_hash IS NOT NULL AND email IS NOT NULL AND email <> '' "
                        "AND (last_seen < NOW()-INTERVAL '7 days' OR last_seen IS NULL)",
                }
                em_targets = pd.read_sql(
                    f"SELECT email, display_name FROM web_users WHERE {_aud_sql[em_audience]}",
                    conn)

                st.divider()
                mc1, mc2 = st.columns(2)
                with mc1: st.metric("📧 إيميلات في الجمهور", len(em_targets))
                with mc2: st.metric("👥 إجمالي مستخدمي الموقع", int(kpi['total']))
                st.divider()

                if st.button("🚀 إطلاق الحملة الآن",
                             width='stretch', key="em_send", type="primary"):
                    if not em_subject:
                        st.error("⚠️ أدخل عنوان الإيميل أولاً.")
                    elif not em_body_html:
                        st.error("⚠️ أدخل محتوى الإيميل.")
                    elif len(em_targets) == 0:
                        st.warning(f"لا يوجد مستخدمون بإيميل في فئة ({em_audience}).")
                    else:
                        # بناء قالب HTML الكامل
                        banner_tag = (
                            f'<img src="{em_banner}" style="width:100%;border-radius:8px;'
                            f'margin-bottom:24px;display:block;" />'
                            if em_banner else "")
                        full_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F5F5F0;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F5F0;padding:32px 16px;">
  <tr><td>
    <table width="600" cellpadding="0" cellspacing="0" align="center"
           style="background:#FFFFFF;border-radius:16px;overflow:hidden;
                  box-shadow:0 4px 24px rgba(0,0,0,0.07);max-width:100%;">
      <tr>
        <td style="background:linear-gradient(135deg,#10B981,#059669);
                   padding:28px 40px;text-align:center;">
          <h1 style="color:white;margin:0;font-size:22px;font-weight:700;">نبض الصفقات 🌐</h1>
          <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">dealpulseksa.com</p>
        </td>
      </tr>
      <tr>
        <td style="padding:32px 40px;font-size:15px;color:#1F2937;line-height:1.7;">
          {banner_tag}
          {em_body_html}
        </td>
      </tr>
      <tr>
        <td style="background:#F5F5F0;padding:20px 40px;text-align:center;
                   border-top:1px solid #E5E7EB;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">
            نبض الصفقات | Deal Pulse KSA<br>
            <a href="https://dealpulseksa.com"
               style="color:#10B981;text-decoration:none;">dealpulseksa.com</a>
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""

                        sent_ok = sent_fail = 0
                        total_t = len(em_targets)
                        prog = st.progress(0, text="جاري الإرسال...")

                        for _, row in em_targets.iterrows():
                            if _send_campaign_email(row['email'], em_subject, full_html):
                                sent_ok += 1
                            else:
                                sent_fail += 1
                            done = sent_ok + sent_fail
                            prog.progress(done / total_t,
                                          text=f"تم {done}/{total_t}...")

                        # تسجيل الحملة في email_logs
                        cur = conn.cursor()
                        conn.autocommit = False
                        cur.execute("""
                            INSERT INTO email_logs
                                (subject, body_html, banner_url, target_audience,
                                 delivery_count, sent_count, failed_count, status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (em_subject, full_html, em_banner, em_audience,
                              total_t, sent_ok, sent_fail,
                              'completed' if sent_fail == 0 else 'partial'))
                        conn.commit()
                        conn.autocommit = True

                        if sent_fail == 0:
                            st.success(f"✅ أُرسلت الحملة بنجاح لـ {sent_ok} مستخدم!")
                            st.balloons()
                        else:
                            st.warning(f"⚠️ انتهت الحملة — نجح {sent_ok} ، فشل {sent_fail}")

            # ── عمود المعاينة ─────────────────────────────────────────────────
            with col_prev:
                st.subheader("👁️ معاينة النشرة البريدية")

                _prev_banner = (
                    f'<img src="{em_banner}" style="width:100%;border-radius:6px;'
                    f'margin-bottom:14px;display:block;" />'
                    if em_banner else "")
                _prev_body   = em_body_html if em_body_html else (
                    '<p style="color:#9CA3AF;font-style:italic;">'
                    'اكتب محتوى الحملة لتظهر المعاينة...</p>')
                _prev_subj   = em_subject if em_subject else "عنوان الحملة"

                preview_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#ECEAE4;font-family:Arial,sans-serif;padding:12px;}}
.wrap{{background:#fff;border-radius:12px;overflow:hidden;
       box-shadow:0 2px 14px rgba(0,0,0,0.1);}}
.hdr{{background:linear-gradient(135deg,#10B981,#059669);
      padding:18px 24px;text-align:center;color:#fff;}}
.hdr h1{{font-size:16px;margin:0;}}
.hdr p{{font-size:11px;opacity:.85;margin:4px 0 0;}}
.subj{{background:#E8F5E9;padding:8px 20px;font-size:12px;
       color:#374151;border-bottom:1px solid #E5E7EB;}}
.body{{padding:20px 24px;font-size:13px;color:#1F2937;line-height:1.65;}}
.ftr{{background:#F5F5F0;padding:12px;text-align:center;
      font-size:11px;color:#9CA3AF;border-top:1px solid #E5E7EB;}}
.ftr a{{color:#10B981;text-decoration:none;}}
</style></head>
<body>
<div class="wrap">
  <div class="hdr"><h1>نبض الصفقات 🌐</h1><p>dealpulseksa.com</p></div>
  <div class="subj"><strong>📌 الموضوع:</strong> {_prev_subj}</div>
  <div class="body">{_prev_banner}{_prev_body}</div>
  <div class="ftr">نبض الصفقات |
    <a href="https://dealpulseksa.com">dealpulseksa.com</a>
  </div>
</div>
</body></html>"""
                components.html(preview_html, height=460, scrolling=True)

                st.divider()
                st.markdown("### 📊 إحصاءات جمهور الموقع")
                with st.container(border=True):
                    st.write(f"🟢 نشط اليوم:   `{int(kpi['active_24h'])}`")
                    st.write(f"🟡 نشط الأسبوع: `{int(kpi['active_normal'])}`")
                    st.write(f"🔴 خامل:         `{int(kpi['inactive'])}`")
                    st.write(f"📧 لديهم إيميل: `{int(kpi['with_email'])}`")

            # ── سجل الحملات البريدية ──────────────────────────────────────────
            st.divider()
            with st.expander("📜 سجل الحملات البريدية (آخر 10)"):
                try:
                    em_hist = pd.read_sql("""
                        SELECT sent_at         AS "تاريخ الإرسال",
                               subject         AS "الموضوع",
                               target_audience AS "الجمهور",
                               delivery_count  AS "المستهدفون",
                               sent_count      AS "نجح",
                               failed_count    AS "فشل",
                               status          AS "الحالة"
                        FROM email_logs ORDER BY sent_at DESC LIMIT 10
                    """, conn)
                    if not em_hist.empty:
                        st.dataframe(em_hist, width='stretch', hide_index=True)
                    else:
                        st.info("لا توجد حملات بريدية سابقة.")
                except Exception:
                    st.info("لا توجد حملات بريدية سابقة.")

        except Exception as e:
            st.error(f"حدث خطأ في حملات البريد الإلكتروني: {e}")
        finally:
            if 'conn' in locals(): conn.close()













# --- الصفحة السادسة عشرة: لوحة القيادة الإستراتيجية (Fixed Version) ---
elif page == "لوحة القيادة":
    page_title("🏢", "غرفة العمليات والإستراتيجية")

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("ROLLBACK")

        def get_stat(query):
            try:
                res = pd.read_sql(query, conn)
                return res.iloc[0,0] if not res.empty else 0
            except Exception:
                return 0

        m_count = get_stat("SELECT COUNT(*) FROM master")
        u_count = get_stat("SELECT COUNT(*) FROM bot_users")
        b_count = get_stat("SELECT COUNT(*) FROM broadcast_logs")
        idle_count = get_stat("""
            SELECT COUNT(*) FROM bot_users
            WHERE last_seen IS NULL OR last_seen < NOW() - INTERVAL '24 hours'
        """)
        beneficiaries = get_stat("""
            SELECT COUNT(DISTINCT user_id) FROM action_logs
            WHERE user_id IS NOT NULL
              AND action_type IN ('copy_coupon','click_link')
        """)

        st.markdown("### 📈 مؤشرات الأداء الحية")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📦 روابط الماستر", f"{m_count}")
        c2.metric("👥 المشتركين", f"{u_count}")
        c3.metric("📢 حملات مرسلة", f"{b_count}")
        c4.metric("💤 خاملون (>24س)", f"{idle_count}")
        c5.metric("🎁 المستفيدون", f"{beneficiaries}")

        st.divider()
        st.subheader("📜 سجل آخر الحركات")
        try:
            df_logs = pd.read_sql("""
                SELECT
                    TO_CHAR(a.action_time, 'YYYY-MM-DD HH24:MI:SS') AS "الوقت",
                    a.action_type AS "الحركة",
                    COALESCE(a.store_id, '—') AS "المتجر",
                    COALESCE(NULLIF(b.username, ''), '— مجهول —') AS "المستخدم",
                    COALESCE(a.details, '') AS "التفاصيل"
                FROM action_logs a
                LEFT JOIN bot_users b ON a.user_id = b.telegram_id
                ORDER BY a.action_time DESC LIMIT 20
            """, conn)
            if not df_logs.empty:
                st.dataframe(df_logs, width='stretch', hide_index=True, height=420)
            else:
                st.info("📭 لا توجد حركات مسجّلة بعد.")
        except Exception as e:
            st.warning(f"⚠️ تعذّر جلب سجل الحركات: {e}")

    except Exception as e:
        st.error(f"حدث خطأ فني: {e}")
    finally:
        if 'conn' in locals(): conn.close()


# --- الصفحة الثامنة عشرة: مركز الدعم الفني ---
elif page == "مركز الدعم":
    page_title("🎧", "مركز إدارة الدعم الفني")
    st.info("استقبل رسائل العملاء من البوت ورد عليهم مباشرة لتحسين تجربة المستخدم.")

    tab_inbox, tab_resolved = st.tabs(["📥 الرسائل الواردة", "✅ رسائل تم حلها"])

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        # التنظيف لضمان عدم وجود عمليات معلقة
        cur.execute("ROLLBACK")

        with tab_inbox:
            st.subheader("📬 طلبات المساعدة الجديدة")
            
            # جلب البيانات بأسماء أعمدة إنجليزية لتجنب أخطاء PostgreSQL
            query_open = "SELECT id, created_at, username, message FROM support_tickets WHERE status = 'open' ORDER BY created_at DESC"
            df_open = pd.read_sql(query_open, conn)
            
            if not df_open.empty:
                # تعريب الأعمدة هنا
                df_display = df_open.copy()
                df_display.columns = ['المعرف', 'التاريخ', 'المستخدم', 'الرسالة']
                st.dataframe(df_display.drop(columns=['المعرف']), width='stretch')
                
                st.divider()
                st.subheader("💬 الرد وإغلاق التذكرة")
                
                col_sel, col_btn = st.columns([2, 1])
                with col_sel:
                    # نستخدم قائمة المستخدمين من البيانات المجلوبة
                    ticket_to_solve = st.selectbox("اختر تذكرة للرد عليها:", df_open["username"], key="open_tickets")
                    reply_text = st.text_area(f"اكتب ردك لـ {ticket_to_solve}:", placeholder="أهلاً بك، تم تحديث الكود...")
                
                with col_btn:
                    st.write("##") # موازنة المسافة
                    if st.button("📧 إرسال الرد وإغلاق الطلب", width='stretch'):
                        if reply_text:
                            # تحديث حالة الرسالة في القاعدة
                            cur.execute("UPDATE support_tickets SET status = 'resolved' WHERE username = %s AND status = 'open'", (ticket_to_solve,))
                            conn.commit()
                            st.success(f"تم الرد على {ticket_to_solve} ونقل الرسالة للأرشيف.")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("يا برنس اكتب الرد أولاً!")
            else:
                st.success("🎉 مبروك! لا توجد طلبات مساعدة معلقة.")

        with tab_resolved:
            st.subheader("📚 أرشيف المساعدة")
            # جلب الرسائل المحلولة
            query_res = "SELECT created_at, username, message FROM support_tickets WHERE status = 'resolved' ORDER BY created_at DESC"
            df_resolved = pd.read_sql(query_res, conn)
            
            if not df_resolved.empty:
                df_resolved.columns = ['التاريخ', 'المستخدم', 'الرسالة']
                st.table(df_resolved)
            else:
                st.caption("الأرشيف فارغ حالياً.")

    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"خطأ في صفحة الدعم: {e}")
    finally:
        if conn:
            conn.close()





# --- الصفحة التاسعة عشرة: مختبر النمو والانتشار --- # البداية
elif page == "مختبر النمو":
    page_title("🚀", "مختبر النمو والانتشار (Growth Lab)")
    st.info("حلل الفجوات في سوق الكوبونات واكتشف الكلمات المفتاحية الأكثر ربحاً لتوسيع نشاطك.")

    conn = None
    try:
        conn = get_conn()
        # --- تعديل أمني: تنظيف أي عمليات معلقة قبل البدء ---
        conn.rollback() 
        # -----------------------------------------------
        
        col_seo, col_gap = st.columns([1, 1])

        with col_seo:
            st.subheader("🔍 الكلمات الأكثر بحثاً")
            # استعلام SQL سادة بدون أي تعريب داخل الاستعلام لتجنب Syntax Error
            query_seo = "SELECT search_query, search_count FROM search_analytics ORDER BY search_count DESC LIMIT 5"
            df_seo = pd.read_sql(query_seo, conn)
            
            if not df_seo.empty:
                # تعريب الأعمدة داخل الباندا (Pandas) فقط للعرض
                df_seo.columns = ['الكلمة', 'عدد البحث']
                st.dataframe(df_seo, width='stretch')
            else:
                st.write("لا توجد بيانات بحث كافية حالياً.")

        with col_gap:
            st.subheader("🕳️ تحليل الفجوات (Gap Analysis)")
            st.write("أقسام مطلوبة وغير متوفرة:")
            
            # مصفوفة الفجوات (يمكنك ربطها بجدول لاحقاً)
            gaps = ["قطع غيار سيارات", "اشتراكات رقمية", "مستلزمات حيوانات"]
            for gap in gaps:
                st.warning(f"⚠️ نقص: قسم **({gap})** مطلوب بشدة.")
            
            if st.button("➕ إرسال المقترحات للتنفيذ"):
                st.success("تم إرسال القائمة لـ فهد وعبدالله للبدء في توفير الكوبونات.")

        st.divider()
        
        # --- قسم الحملات الإعلانية ---
        st.subheader("🎯 مخطط الحملات الإعلانية")
        with st.expander("📝 صياغة إعلان تسويقي ذكي"):
            promo_type = st.radio("المنصة المستهدفة:", ["تيك توك", "تويتر (X)", "سناب شات"], horizontal=True)
            target_item = st.text_input("المنتج المراد الترويج له:", "بوت توفير")
            
            if st.button("🪄 توليد نص إعلاني"):
                if "تيك توك" in promo_type:
                    st.code(f"محتار بين الأسعار؟ 🧐 {target_item} صار أسهل مع بوت 'توفير'! يجيب لك الخصم من المصدر. الرابط في البايو! ✨", language="text")
                else:
                    st.code(f"وفر قروشك مع محرك التوفير الذكي 🚀 أقوى خصومات على {target_item} حصرية لمشتركينا. جربه الآن! 👇", language="text")

        # --- إحصائيات الزيارات الحقيقية ---
        st.divider()
        st.subheader("🔗 مصادر الزيارات (Traffic Sources)")
        # جلب البيانات بالإنجليزية
        try:
            query_traffic = "SELECT source_name, visit_count FROM traffic_sources"
            df_traffic = pd.read_sql(query_traffic, conn)
            
            if not df_traffic.empty:
                df_traffic.columns = ['المصدر', 'الزيارات']
                st.bar_chart(df_traffic.set_index("المصدر"))
            else:
                st.info("لا توجد بيانات لمصادر الزيارات حالياً.")
        except:
            st.warning("⚠️ جدول مصادر الزيارات غير متوفر حالياً في قاعدة البيانات.")
        
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"حدث خطأ في جلب بيانات النمو: {e}")
    finally:
        if conn: conn.close()
# --- نهاية الصفحة التاسعة عشرة --- # النهاية







# --- الصفحة العشرين: رادار المنافسين والذكاء التسويقي ---
elif page == "رادار المنافسين":
    st.header("📡 رادار المنافسين والذكاء التسويقي")
    st.info("مراقبة حية للمتاجر الكبرى واكتشاف العروض Flash Sales قبل الجميع.")

    conn = None
    try:
        conn = get_conn()
        
        col_spy, col_action = st.columns([1.2, 1])

        with col_spy:
            st.subheader("🕵️ وضع التجسس الذكي")
            stores_to_watch = ["Noon.com", "Amazon.sa", "Jarir.com", "Namshi.com"]
            selected_watch = st.multiselect("المواقع تحت المراقبة حالياً:", stores_to_watch, default=stores_to_watch)
            
            if st.button("🔍 فحص التغييرات الآن"):
                with st.spinner("جاري فحص أكواد المصدر للمنافسين..."):
                    # هنا مستقبلاً نربط سكريبت القشط (Scraping)
                    st.success("تم اكتشاف تغيير في سياسة الخصم في 'نون'!")
                    st.warning("⚠️ كود جديد ظهر في 'نمشي': [OFF50]")
            
            # جلب البيانات الحقيقية من الجدول
            query_watch = "SELECT store_name, last_code, status FROM competitor_watch"
            df_watch = pd.read_sql(query_watch, conn)
            
            if not df_watch.empty:
                # تعريب مسميات الأعمدة في العرض فقط
                df_watch.columns = ['المتجر', 'آخر كود مكتشف', 'الحالة']
                st.table(df_watch)

        with col_action:
            st.subheader("⚡ رد الفعل السريع")
            st.write("إجراءات مقترحة بناءً على حركة السوق:")
            
            with st.container(border=True):
                st.write("📌 **حدث الآن:** أمازون أطلقوا 'عروض الـ 24 ساعة'.")
                if st.button("📝 تجهيز رسالة برودكاست فورية"):
                    st.session_state.temp_msg = "🚨 عاجل: أمازون أطلقوا عروض قوية للـ 24 ساعة القادمة! شيكوا الروابط في البوت."
                    st.info("تم تجهيز النص، انتقل لصفحة 'مركز الإشعارات' للإرسال.")
            
            st.divider()
            st.write("📊 **قوة الخصم بالسوق:**")
            
            # رسم بياني من بيانات القاعدة
            query_chart = "SELECT store_name, discount_rate FROM competitor_watch"
            df_chart = pd.read_sql(query_chart, conn)
            if not df_chart.empty:
                df_chart.columns = ['المتجر', 'نسبة الخصم']
                st.line_chart(df_chart.set_index("المتجر"))

        # --- قسم اقتناص الفرص (Opportunity Sniping) ---
        st.divider()
        st.subheader("🎯 قناص الفرص (Opportunity Sniping)")
        st.write("الذكاء الاصطناعي يحلل أي المتاجر تعطي 'أفضل عمولة' (Affiliate) حالياً:")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        # ميتريك ثابتة حالياً أو تسحبها من جدول خارجي لاحقاً
        col_f1.metric("أعلى عمولة", "نمشي", "12%")
        col_f2.metric("أسرع انتشار", "نون", "8%")
        col_f3.metric("أقل منافسة", "صيدلية أومني", "جديد")

        st.caption("ملاحظة: البيانات يتم تحديثها بناءً على قراءة الـ Meta Data للمواقع المسجلة في الماستر.")

    except Exception as e:
        if conn: conn.rollback()
        st.error(f"خطأ في الرادار: {e}")
    finally:
        if conn: conn.close()












# ==============================================================================
# --- استوديو الإبداع والذكاء التسويقي (الربط مع الاهتمامات) ---
# ==============================================================================
elif page == "استوديو المحتوى":
    page_title("🎨", "استوديو الإبداع والذكاء التسويقي")
    
    conn = None
    top_interest = "عام" # افتراضي في حال عدم وجود بيانات
    
    try:
        conn = get_conn()
        conn.rollback() # حل حاسم لمشكلة "current transaction is aborted"
        
        # جلب أعلى اهتمام حالي لتوجيه التصميم
        df_int = pd.read_sql("SELECT interest_category FROM user_interests ORDER BY interest_score DESC LIMIT 1", conn)
        if not df_int.empty:
            top_interest = df_int.iloc[0]['interest_category']
            st.success(f"💡 **نصيحة الاستوديو:** الجمهور حالياً مهتم بـ **({top_interest})**. يفضل إنشاء محتوى لهذا القسم.")

    except Exception as e:
        st.caption("سيتم ربط التوصيات الذكية عند توفر بيانات في جدول الاهتمامات.")
    finally:
        if conn: conn.close()

    tab1, tab2, tab3 = st.tabs(["🖼️ مصمم البوستات", "✍️ كاتب الإعلانات (AI)", "🎬 مخرج الفيديو"])

    with tab1:
        st.subheader("🛠️ أدوات التصميم")
        col_edit, col_prev = st.columns([1, 1])
        
        with col_edit:
            prod_name = st.selectbox("المنتج المستهدف:", [f"عرض {top_interest}", "ايفون 15 Pro", "كوبون خصم"])
            coupon_code = st.text_input("كود الخصم الحصري:", "SAVE50")
            bg_color = st.color_picker("لون الخلفية:", BRAND["text"])
            text_color = st.color_picker("لون النص:", BRAND["emerald"])
            
        with col_prev:
            st.subheader("🖼️ المعاينة الحية")
            # منطق رسم البوستر (بناءً على صورتك الرائعة)
            st.markdown(f"""
                <div style="background-color:{bg_color}; padding:40px; border-radius:25px; text-align:center; border: 3px solid {text_color};">
                    <h5 style="color:white; opacity:0.6; letter-spacing:2px;">LIMITED TIME OFFER</h5>
                    <h1 style="color:{text_color}; font-size:45px;">{prod_name}</h1>
                    <p style="color:white; margin-top:20px;">استخدم الكود للحصول على الخصم</p>
                    <div style="background-color:{text_color}; color:{bg_color}; padding:15px; border-radius:10px; font-weight:bold; font-size:30px; display:inline-block; margin-top:10px;">
                        {coupon_code}
                    </div>
                    <p style="color:white; font-size:12px; margin-top:20px;">🚀 اطلبه الآن عبر محرك توفير</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("📥 تحميل كود التصميم"):
                st.info("سيتم تصدير التصميم بصيغة PNG في التحديث القادم.")

    with tab2:
        st.subheader("🤖 كاتب الإعلانات بالذكاء الاصطناعي")
        platform = st.selectbox("منصة النشر:", ["تيك توك", "سناب شات", "انستقرام"])
        if st.button("✨ توليد النص البيعي"):
            st.code(f"📢 الرابط بالبايو! {coupon_code} صار عليه عرض.. كود {top_interest} يا جماعة لا يفوتكم! 🔥")

    with tab3:
        # منطق مخرج الفيديو بناءً على 'Video Automation Logic'
        st.subheader("🎬 مخرج الفيديو والترند")
        st.info("هنا يتم تحويل بيانات الاهتمامات إلى سيناريوهات فيديو قصيرة.")
        if st.button("🎬 توليد سكربت النشر الفوري"):
            st.write(f"🎥 **السيناريو المقترح:** عرض سريع لمنتجات {top_interest} مع ظهور الكود {coupon_code} في المنتصف.")













# ==============================================================================
# --- الصفحة الثانية والعشرين: ذكاء التنبوء (النسخة المستقرة) ---
# ==============================================================================
elif page == "ذكاء التنبؤ":
    page_title("🧠", "محرك تحليل التنبؤ")
    st.info("الذكاء الاصطناعي يحلل اهتمامات العملاء لتوجيه الكوبونات المناسبة لكل فئة.")

    conn = None
    try:
        conn = get_conn()
        conn.rollback() 
        
        col_interests, col_trend = st.columns([1, 1.2])

        with col_interests:
            st.subheader("🎯 تحليل فئات الاهتمام")
            try:
                # الاستعلام من جدول الاهتمامات الجديد
                query = """
                    SELECT interest_category as "القسم", 
                           SUM(interest_score) as "قوة الطلب"
                    FROM user_interests 
                    GROUP BY interest_category 
                    ORDER BY "قوة الطلب" DESC LIMIT 5
                """
                df_int = pd.read_sql(query, conn)
                if not df_int.empty:
                    st.bar_chart(df_int.set_index('القسم'))
                    st.table(df_int)
                else:
                    st.info("بانتظار تفاعل المستخدمين مع الأقسام لتحديد الاهتمامات.")
            except:
                st.warning("⚠️ يرجى إنشاء جدول user_interests لبدء تحليل الاهتمامات.")

        with col_trend:
            st.subheader("🔮 التنبؤ بالقسم الأكثر طلباً غداً")
            # التحقق من وجود بيانات قبل محاولة عرضها
            if 'df_int' in locals() and not df_int.empty:
                top_cat = df_int.iloc[0]['القسم']
                st.success(f"🤖 **توصية ذكية:** القسم الأكثر نمواً هو **({top_cat})**. ننصح بتوفير كوبونات له.")
            else:
                st.info("📭 لا توجد بيانات اهتمامات كافية بعد. سيظهر التوقّع فور تفاعل المستخدمين مع الأقسام "
                        "(لا نعرض أي منحنى عشوائي/وهمي).")

    except Exception as e:
        st.error(f"خطأ في محرك التنبؤ: {e}")
    finally:
        if conn: conn.close()










# ==============================================================================
# --- الصفحة الثالثة والعشرين: نظام الولاء والمكافآت (إدارة الرتب والنقاط) ---
# ==============================================================================
elif page == "نظام الولاء":
    page_title("🎖️", "نظام الولاء والمكافآت (Tawfeer Loyalty)")
    
    conn = None
    try:
        conn = get_conn()
        conn.rollback() # لضمان عدم تعليق قاعدة البيانات

        # صف عرض إحصائيات عامة
        c1, c2, c3 = st.columns(3)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_loyalty")
        total_users = cur.fetchone()[0]
        c1.metric("إجمالي الأعضاء", total_users)
        
        cur.execute("SELECT SUM(points) FROM user_loyalty")
        total_points = cur.fetchone()[0] or 0
        c2.metric("إجمالي نقاط النظام", total_points)
        
        c3.metric("رتب النظام", "3 مستويات")

        # تقسيم الصفحة: لوحة الصدارة وإدارة المكافآت
        tab_leaderboard, tab_admin = st.tabs(["🏆 لوحة المتصدرين", "⚙️ إدارة مكافآت النظام"])

        with tab_leaderboard:
            st.subheader("📊 أبطال التوفير (Top 10)")
            # الاستعلام بناءً على أعمدة جدولك: user_id, username, points, rank
            query = """
                SELECT username as "المستخدم", 
                       points as "النقاط", 
                       rank as "الرتبة الحاليّة",
                       total_comparisons as "التفاعل"
                FROM user_loyalty 
                ORDER BY points DESC LIMIT 10
            """
            df_loyalty = pd.read_sql(query, conn)
            if not df_loyalty.empty:
                st.table(df_loyalty)
            else:
                st.info("لا يوجد أعضاء نشطين في النظام حالياً.")

        with tab_admin:
            st.subheader("🛠️ لوحة تحكم النقاط (إدارة النظام)")
            with st.form("award_points"):
                target_user = st.number_input("معرف المستخدم (User ID):", step=1)
                points_to_add = st.number_input("النقاط المراد منحها:", min_value=1, step=10)
                reason = st.selectbox("سبب المكافأة:", ["دعوة صديق", "تفاعل استثنائي", "تعويض", "هدية إطلاق"])
                
                if st.form_submit_button("✅ تنفيذ منح النقاط"):
                    cur.execute("""
                        UPDATE user_loyalty 
                        SET points = points + %s, 
                            rank = CASE 
                                WHEN points + %s > 2000 THEN '🥇 ذهبي'
                                WHEN points + %s > 500 THEN '🥈 فضي'
                                ELSE '🥉 برونزي'
                            END
                        WHERE user_id = %s
                    """, (points_to_add, points_to_add, points_to_add, target_user))
                    conn.commit()
                    st.success(f"تمت إضافة {points_to_add} نقطة للمستخدم بنجاح وتحديث رتبته!")

    except Exception as e:
        st.error(f"خطأ في قراءة بيانات الولاء: {e}")
    finally:
        if conn: conn.close()




# ==============================================================================
# --- الصفحة الرابعة والعشرين: مركز القيادة والتحكم الآلي (Autonomous Center) ---
# ==============================================================================
elif page == "التحكم الآلي":
    page_title("🤖", "مركز القيادة والتحكم الآلي")
    st.info("قم بضبط القواعد الذكية ليعمل البوت كـ 'روبوت' يتخذ القرارات بدلاً عنك.")

    conn = None
    try:
        conn = get_conn()
        conn.rollback()

        col_rules, col_monitor = st.columns([1.5, 1])

        with col_rules:
            st.subheader("⚙️ ضبط قواعد الروبوت")
            with st.container(border=True):
                rule_type = st.selectbox("اختر المهمة الآلية للروبوت:", [
                    "إرسال تنبيهات الاهتمامات (Trending)",
                    "إدارة العضويات والولاء تلقائياً",
                    "تصفية الكوبونات المنتهية",
                    "تغيير هوية البوت (رسائل الترحيب)"
                ])
                
                # إعدادات القاعدة المختارة
                if rule_type == "إرسال تنبيهات الاهتمامات (Trending)":
                    min_users = st.number_input("أرسل برودكاست إذا وصل عدد المهتمين بالقسم إلى:", value=50)
                    st.write(f"ℹ️ سيقوم الروبوت بمراقبة جدول الاهتمامات والإرسال فور الوصول لـ {min_users} مهتم.")
                
                elif rule_type == "تصفية الكوبونات المنتهية":
                    st.write("🧹 سيقوم الروبوت بفحص 'تاريخ الانتهاء' في جدول الماستر وحذف الأكواد القديمة كل 24 ساعة.")
                
                elif rule_type == "إدارة العضويات والولاء تلقائياً":
                    st.write("📈 سيقوم الروبوت بترقية المستخدمين للرتبة الفضية والذهبية تلقائياً بناءً على نقاطهم.")

                if st.button("🚀 تفعيل وحفظ القاعدة"):
                    # هنا يتم الحفظ في جدول auto_rules
                    st.success(f"تم تفعيل قاعدة ({rule_type}) بنجاح!")

        with col_monitor:
            st.subheader("🛰️ حالة الروبوت (Bot Health)")
            # حقيقي: آخر نشاط فعلي + أحداث آخر 24 ساعة من action_logs (لا أرقام عشوائية)
            try:
                _hb = pd.read_sql(
                    "SELECT MAX(action_time) AS last_seen, "
                    "COUNT(*) FILTER (WHERE action_time >= NOW() - INTERVAL '24 hours') AS last24 "
                    "FROM action_logs", conn)
                _ls = _hb.iloc[0]["last_seen"]
                _l24 = int(_hb.iloc[0]["last24"] or 0)
                if _ls is not None:
                    st.metric("آخر نشاط مُسجّل (UTC)", str(_ls)[:16])
                    st.metric("أحداث آخر 24 ساعة", f"{_l24:,}")
                    st.caption("✅ مصدر حقيقي: جدول action_logs مباشرة." if _l24 > 0
                               else "⚠️ لا نشاط في آخر 24 ساعة.")
                else:
                    st.info("📭 لا يوجد نشاط مُسجّل بعد في action_logs.")
            except Exception as _e:
                st.info(f"تعذّر قراءة حالة النشاط: {_e}")


    except Exception as e:
        st.error(f"❌ خطأ في محرك التحكم الآلي: {e}")
    finally:
        if conn: conn.close()

# ==============================================================================
# --- الصفحة الخامسة والعشرين: محرك التخصيص الفائق (The Sniper Master) ---
# ==============================================================================
elif page == "التخصيص الفائق":
    page_title("🎯", "محرك التخصيص الفائق")
    
    # تبويبات لفصل كودك الشغال عن الربط بقاعدة البيانات
    tab_personal, tab_database = st.tabs(["✨ هندسة العروض (كودك)", "📡 الربط مع الجداول (SQL)"])

    # --- الجزء الأول: كودك اللي اشتغل 100% ---
    with tab_personal:
        st.info("تحليل اهتمامات كل مستخدم لتقديم عروض مخصصة ترفع المبيعات.")
        col_analysis, col_segment = st.columns([1, 1])

        with col_analysis:
            st.subheader("🧐 تحليل اهتمامات الجماهير")
            interest_data = pd.DataFrame({
                "الفئة": ["إلكترونيات", "أزياء", "عناية وجمال", "مستلزمات منزل"],
                "عدد المهتمين": [450, 320, 280, 150],
                "تفاعل الفئة": ["🔥 مرتفع", "متوسط", "🔥 مرتفع", "هادئ"]
            })
            st.table(interest_data)

        with col_segment:
            st.subheader("🎨 إنشاء Segments مخصصة")
            with st.container(border=True):
                segment_name = st.text_input("اسم الشريحة الجديدة:", placeholder="مثال: عشاق القهوة")
                target_interest = st.multiselect("الكلمات المفتاحية المستهدفة:", ["نسبريسو", "مطحنة", "بن هرري", "ديلونجي"])
                if st.button("🏗️ تكوين الشريحة"):
                    st.success(f"تم حصر 85 مستخدم مهتم بـ {segment_name}.")

        st.divider()
        st.subheader("📊 دقة التخصيص (Accuracy Track)")
        accuracy_df = pd.DataFrame({
            "نوع الإرسال": ["إرسال عام (للجميع)", "إرسال مخصص (Segments)"],
            "نسبة فتح الرابط %": [12, 48]
        })
        st.bar_chart(accuracy_df.set_index("نوع الإرسال"))

    # --- الجزء الثاني: الربط مع جداول قاعدة البيانات (SQL) ---
    with tab_database:
        st.subheader("📡 البيانات الحقيقية من الجداول")
        conn = None
        try:
            conn = get_conn()
            if conn:
                conn.rollback() # لضمان تحديث البيانات اللحظي
                
                # جلب بيانات من جدول الاهتمامات
                query_radar = """
                    SELECT interest_category as "القسم", COUNT(user_id) as "العدد" 
                    FROM user_interests GROUP BY 1 ORDER BY 2 DESC
                """
                df_radar = pd.read_sql(query_radar, conn)
                
                if not df_radar.empty:
                    st.write("📈 **توزيع الاهتمامات الحقيقي:**")
                    st.bar_chart(df_radar.set_index("القسم"), color=BRAND["danger"])
                    
                    # عرض بروفايلات الـ VIP من جدولك
                    st.divider()
                    st.subheader("💎 أعلى 5 عملاء توفيراً (VIP)")
                    df_vip = pd.read_sql("SELECT user_id, loyalty_rank, total_savings FROM user_hyper_profiles ORDER BY total_savings DESC LIMIT 5", conn)
                    st.dataframe(df_vip, width='stretch', hide_index=True)
                else:
                    st.warning("⚠️ بانتظار تفاعل المستخدمين لتعبئة جداول SQL.")
        except Exception as e:
            st.error(f"❌ خطأ في الاتصال بالجداول: {e}")
        finally:
            if conn: conn.close()












# ==============================================================================
# --- الصفحة الثامنة والعشرين: رادار المناسبات والذكاء المتكامل ---
# ==============================================================================
elif page == "رادار المناسبات":
    page_title("📅", "رادار المناسبات والاستخبارات العاطفية")
    
    # التبويبات كملحقات ذكية داخل الرادار بناءً على جداولك
    tab_global, tab_spy, tab_marketing = st.tabs([
        "🗓️ المناسبات العامة",
        "🕵️ الملحق التجسسي",
        "💰 الملحق التسويقي"
    ])

    conn = get_conn()
    if conn:
        # لضمان عدم تعليق العمليات في حال وجود خطأ سابق
        conn.autocommit = True
        
        # --- 1. المناسبات العامة والترند (من جدول seasonal_events) ---
        with tab_global:
            st.subheader("🔥 رادار المواسم والترند")
            try:
                # تحويل event_date إلى DATE لضمان صحة الحسابات
                query_ev = "SELECT event_id, event_name, event_date::DATE, bot_status FROM seasonal_events ORDER BY event_date ASC"
                df_ev = pd.read_sql(query_ev, conn)
                
                if not df_ev.empty:
                    today = datetime.now().date()
                    df_ev['الأيام المتبقية'] = df_ev['event_date'].apply(lambda x: (x - today).days)
                    
                    # عرض المناسبات القادمة فقط
                    st.table(df_ev[df_ev['الأيام المتبقية'] >= 0][['event_name', 'event_date', 'الأيام المتبقية', 'bot_status']])
                else:
                    st.info("لا توجد مناسبات عامة مسجلة حالياً.")
            except Exception as e:
                st.error(f"خطأ في قراءة المناسبات العامة: {e}")

        # --- 2. الملحق التجسسي (من جداول bot_users و direct_search) ---
        with tab_spy:
            st.subheader("📡 تتبع النوايا الشرائية (Spy Mode)")
            try:
                # سحب بيانات التجسس المخزنة في JSONB
                query_spy = "SELECT username, spy_behavior, fav_store_inferred FROM bot_users WHERE spy_behavior IS NOT NULL"
                df_spy = pd.read_sql(query_spy, conn)
                
                if not df_spy.empty:
                    selected_user = st.selectbox("اختر مستهدف للرصد:", df_spy['username'])
                    user_data = df_spy[df_spy['username'] == selected_user].iloc[0]
                    
                    col1, col2 = st.columns(2)
                    col1.metric("المتجر المفضل المستنتج", user_data['fav_store_inferred'])
                    with col2:
                        st.write("سجل التحركات (JSONB):")
                        st.json(user_data['spy_behavior'])
                
                st.divider()
                st.write("🔍 آخر عمليات البحث المباشر (Direct Search):")
                df_search = pd.read_sql("SELECT search_keyword, search_date FROM direct_search ORDER BY search_date DESC LIMIT 5", conn)
                st.table(df_search)
            except Exception as e:
                st.error(f"خطأ في محرك التجسس: {e}")


                # --- 1. المناسبات العامة (إدارة كاملة: إضافة، حذف، تعديل) ---
        with tab_global:
            st.subheader("🔥 إدارة رادار المواسم")

            # --- أ. نموذج الإضافة أو التعديل ---
            # نستخدم expander عشان ما يزحم الصفحة
            with st.expander("➕ إضافة مناسبة جديدة أو تعديل"):
                with st.form("event_form"):
                    col1, col2 = st.columns(2)
                    e_id = col1.number_input("ID المناسبة (للتعديل فقط اترك 0 للجديد)", min_value=0, value=0)
                    e_name = col2.text_input("اسم المناسبة")
                    e_date = st.date_input("تاريخ المناسبة")
                    e_status = st.selectbox("حالة البوت", ["نشط", "مكتمل", "مؤرشف"])
                    e_sugg = st.text_area("اقتراح الذكاء الاصطناعي")
                    
                    submitted = st.form_submit_button("حفظ التغييرات")
                    
                    if submitted and e_name:
                        cur = conn.cursor()
                        if e_id == 0: # إضافة جديد
                            cur.execute("""
                                INSERT INTO seasonal_events (event_name, event_date, bot_status, ai_suggestion)
                                VALUES (%s, %s, %s, %s)
                            """, (e_name, e_date, e_status, e_sugg))
                            st.success(f"تمت إضافة {e_name}")
                        else: # تعديل موجود
                            cur.execute("""
                                UPDATE seasonal_events 
                                SET event_name=%s, event_date=%s, bot_status=%s, ai_suggestion=%s
                                WHERE event_id=%s
                            """, (e_name, e_date, e_status, e_sugg, e_id))
                            st.success(f"تم تحديث المناسبة رقم {e_id}")
                        st.rerun()

            # --- ب. عرض البيانات مع زر الحذف السريع ---
            df_ev = pd.read_sql("SELECT event_id, event_name, event_date::DATE, bot_status FROM seasonal_events ORDER BY event_date ASC", conn)
            
            if not df_ev.empty:
                # عرض الجدول بشكل احترافي
                st.dataframe(df_ev, width='stretch')
                
                st.divider()
                # قسم الحذف
                col_del, col_btn = st.columns([3, 1])
                target_del = col_del.selectbox("اختر مناسبة لحذفها نهائياً:", 
                                               options=df_ev['event_id'].tolist(),
                                               format_func=lambda x: df_ev[df_ev['event_id'] == x]['event_name'].values[0])
                
                if col_btn.button("🗑️ حذف الآن"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM seasonal_events WHERE event_id = %s", (target_del,))
                    st.warning(f"تم حذف المناسبة رقم {target_del}")
                    st.rerun()
            else:
                st.info("الرادار فارغ حالياً.")

        # --- 4. الملحق التسويقي (من جداول bot_users و marketing_segment) ---
        with tab_marketing:
            st.subheader("💰 محرك الاستهداف البيعي")
            try:
                query_mkt = "SELECT username, marketing_segment, loyalty_rank, visited_clicks FROM bot_users"
                df_mkt = pd.read_sql(query_mkt, conn)
                st.dataframe(df_mkt, width='stretch')
                st.info("💡 يتم تحديث الفئات التسويقية آلياً بناءً على عدد النقرات (visited_clicks).")
            except Exception as e:
                st.error(f"خطأ في المحرك التسويقي: {e}")

        conn.close()














            # ==============================================================================
# --- الصفحة السابعة والعشرين: مركز التوسع (إدارة حقيقية 100%) ---
# ==============================================================================
elif page == "مركز التوسع":
    page_title("🌍", "مركز إدارة التوسع والامتياز الحقيقي")
    
    tab_api, tab_franchise, tab_lab = st.tabs([
        "🔗 إدارة المتاجر والـ API", 
        "🤝 إدارة الوكلاء والامتياز", 
        "🛠️ مختبر التطوير والعمليات"
    ])

    conn = get_conn()
    if conn:
        # --- 1. تبويب إدارة المتاجر (إضافة، تعديل، حذف) ---
        with tab_api:
            st.subheader("📡 بوابات الربط النشطة")
            # جلب البيانات الحقيقية فقط
            df_api = pd.read_sql('SELECT partner_id, partner_name, api_endpoint, status FROM api_partners', conn)
            
            if not df_api.empty:
                for index, row in df_api.iterrows():
                    with st.expander(f"📦 متجر: {row['partner_name']} ({row['status']})"):
                        col1, col2 = st.columns([3, 1])
                        new_url = col1.text_input("تعديل الرابط:", row['api_endpoint'], key=f"url_{row['partner_id']}")
                        if col2.button("🗑️ حذف المتجر", key=f"del_{row['partner_id']}"):
                            cur = conn.cursor()
                            cur.execute("DELETE FROM api_partners WHERE partner_id = %s", (row['partner_id'],))
                            conn.commit()
                            st.rerun()
            else:
                st.info("لا يوجد متاجر مسجلة حالياً.")

            st.divider()
            with st.expander("➕ إضافة متجر جديد للقاعدة"):
                with st.form("new_store"):
                    name = st.text_input("اسم المتجر:")
                    url = st.text_input("رابط الـ API:")
                    key = st.text_input("API Key:", type="password")
                    if st.form_submit_button("💾 تسجيل المتجر حقيقياً"):
                        cur = conn.cursor()
                        cur.execute("INSERT INTO api_partners (partner_name, api_endpoint, api_key, status) VALUES (%s, %s, %s, 'نشط')", (name, url, key))
                        conn.commit()
                        st.rerun()

        # --- 2. تبويب إدارة الوكلاء (إدارة حقيقية) ---
        with tab_franchise:
            st.subheader("🤝 لوحة الوكلاء المعتمدين")
            df_agents = pd.read_sql('SELECT agent_id, agent_name, region, profit_share FROM franchise_agents', conn)
            
            if not df_agents.empty:
                st.dataframe(df_agents, width='stretch', hide_index=True)
                agent_to_del = st.selectbox("اختر وكيل لإلغاء تعاقده:", df_agents['agent_name'])
                if st.button("❌ حذف الوكيل المختارة"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM franchise_agents WHERE agent_name = %s", (agent_to_del,))
                    conn.commit()
                    st.rerun()
            else:
                st.warning("قاعدة البيانات لا تحتوي على وكلاء حالياً.")

            with st.expander("📝 إضافة وكيل جديد"):
                with st.form("new_agent"):
                    a_name = st.text_input("اسم الوكيل:")
                    a_region = st.selectbox("المنطقة:", ["الرياض", "جدة", "القصيم", "الشرقية", "دبي"])
                    a_share = st.number_input("نسبة الأرباح %:", min_value=0.0, max_value=100.0)
                    if st.form_submit_button("💾 تعميد الوكيل"):
                        cur = conn.cursor()
                        cur.execute("INSERT INTO franchise_agents (agent_name, region, profit_share) VALUES (%s, %s, %s)", (a_name, a_region, a_share))
                        conn.commit()
                        st.rerun()

        # --- 3. مختبر التطوير (عمليات حقيقية) ---
        with tab_lab:
            st.subheader("⚙️ مراقبة العمليات الحقيقية (Live)")
            # سحب إجمالي العمليات من جدول السجلات الفعلي
            try:
                total_ops = pd.read_sql("SELECT COUNT(*) FROM action_logs", conn).iloc[0,0]
                st.metric("إجمالي العمليات المنفذة فعلياً", f"{total_ops:,}")
            except:
                st.write("بانتظار تنفيذ أول عملية في النظام..")
            
            st.write("🧪 **تفعيل الميزات التقنية:**")
            st.toggle("البحث بالصور (Google Vision)", help="يرتبط بـ API قوقل الحقيقي")
            st.toggle("الرد الصوتي (ElevenLabs)", help="يرتبط بـ API الصوت الحقيقي")

        conn.close()











# ==============================================================================
# --- الصفحة الثامنة والعشرين: درع الحماية الهجومي (Cyber Shield V2.0) ---
# ==============================================================================
elif page == "درع الحماية":
    page_title("🛡️", "درع الحماية الهجومي (Cyber Shield)")
    
    # تبويبات للتحكم الكامل
    tab_radar, tab_blacklist, tab_settings, tab_emergency = st.tabs([
        "🚨 رادار التهديدات", 
        "🚫 القائمة السوداء", 
        "⚙️ بروتوكولات الأمان", 
        "💣 منطقة الطوارئ"
    ])

    conn = get_conn()
    if conn:
        # --- 1. رادار التهديدات (سحب حي من الجدول) ---
        with tab_radar:
            st.subheader("📡 رصد النشاط المشبوه (Live Feed)")
            # سحب آخر التهديدات المسجلة في الجدول
            query_threats = 'SELECT threat_type as "النوع", source_val as "المصدر", action_taken as "الإجراء", detection_time as "الوقت" FROM security_threats ORDER BY detection_time DESC'
            df_threats = pd.read_sql(query_threats, conn)
            
            if not df_threats.empty:
                st.warning(f"⚠️ تم رصد {len(df_threats)} تهديد محتمل")
                st.dataframe(df_threats, width='stretch')
            else:
                st.success("✅ الرادار نظيف، لا توجد تهديدات مسجلة.")

        # --- 2. القائمة السوداء (تحكم كامل بالحذف والإضافة) ---
        with tab_blacklist:
            col1, col2 = st.columns([1, 1.5])
            
            with col1:
                st.subheader("➕ إضافة حظر يدوي")
                with st.form("manual_block"):
                    target = st.text_input("IP / User ID / Username:")
                    reason = st.selectbox("سبب الحظر:", ["قشط بيانات", "سبام مكثف", "محاولة اختراق", "سلوك عدواني"])
                    if st.form_submit_button("🔨 تنفيذ الحظر"):
                        cur = conn.cursor()
                        cur.execute("INSERT INTO security_blacklist (target_value, reason) VALUES (%s, %s) ON CONFLICT DO NOTHING", (target, reason))
                        conn.commit()
                        st.success(f"تم نفي {target} للقائمة السوداء.")
                        st.rerun()

            with col2:
                st.subheader("🔓 إدارة المحظورين حالياً")
                df_black = pd.read_sql('SELECT target_value as "الهدف", reason as "السبب", block_date as "التاريخ" FROM security_blacklist', conn)
                if not df_black.empty:
                    st.table(df_black)
                    unban_target = st.selectbox("اختر لفك الحظر:", df_black['الهدف'])
                    if st.button("🔓 فك الحظر فوراً"):
                        cur = conn.cursor()
                        cur.execute("DELETE FROM security_blacklist WHERE target_value = %s", (unban_target,))
                        conn.commit()
                        st.rerun()
                else:
                    st.info("لا يوجد أي مستخدم محظور حالياً.")

        # --- 3. بروتوكولات الأمان (تعديل الإعدادات الحقيقية) ---
        with tab_settings:
            st.subheader("⚙️ تعديل قوانين النظام")
            # سحب القيمة الحالية من جدول الإعدادات
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM security_settings WHERE setting_key = 'max_requests_per_min'")
            current_max = cur.fetchone()[0]

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                new_max = st.number_input("أقصى عدد طلبات/دقيقة:", value=int(current_max))
                if st.button("💾 حفظ الإعدادات الجديدة"):
                    cur.execute("UPDATE security_settings SET setting_value = %s WHERE setting_key = 'max_requests_per_min'", (new_max,))
                    conn.commit()
                    st.toast("تم تحديث بروتوكول السرعة!")

            with col_s2:
                st.write("📊 **تحليل كفاءة الدرع:**")
                # إحصائية بسيطة لعدد الهجمات المصدودة
                total_threats = len(df_threats)
                st.metric("إجمالي التهديدات الموؤودة", total_threats, delta="نشط")

        # --- 4. منطقة الطوارئ (تدمير وتصفير) ---
        with tab_emergency:
            st.error("🚨 منطقة العمليات الحرجة - كن حذراً")
            col_e1, col_e2 = st.columns(2)
            
            if col_e1.button("🔥 تصفير سجل التهديدات بالكامل"):
                cur = conn.cursor()
                cur.execute("TRUNCATE TABLE security_threats")
                conn.commit()
                st.rerun()
                
            if col_e2.button("💣 طرد جميع الجلسات (Logout All)"):
                # منطق برمجي لتصفير التوكنات أو الجلسات
                st.warning("تم إرسال إشارة التدمير لجميع الجلسات النشطة.")

        conn.close()









        # ==============================================================================
# --- مركز الصيانة: التحكم الإستراتيجي الفعلي ---
# ==============================================================================
elif page == "مركز الصيانة":
    page_title("🛠️", "مركز العمليات والصيانة الحقيقي")

    conn = get_conn()
    if conn:
        conn.autocommit = True
        cur = conn.cursor()

        # --- 1. التحكم الديناميكي في واجهة البوت (أهم جزء) ---
        st.subheader("🎮 ريموت كنترول واجهة البوت")
        
        # سحب الأزرار الحقيقية من جدولك
        df_btns = pd.read_sql("SELECT * FROM bot_dynamic_buttons ORDER BY display_order", conn)
        
        col_list, col_add = st.columns([2, 1])
        
        with col_list:
            st.write("🔧 **إدارة الأزرار المفعلة حالياً:**")
            for _, row in df_btns.iterrows():
                c1, c2, c3 = st.columns([3, 2, 1])
                status_icon = "🟢" if row['is_active'] else "🔴"
                c1.write(f"**{row['button_text']}**")
                
                # زر تبديل الحالة الحقيقي (Update)
                if c2.button(f"تبديل {status_icon}", key=f"tgl_{row['button_id']}"):
                    cur.execute("UPDATE bot_dynamic_buttons SET is_active = NOT is_active WHERE button_id = %s", (row['button_id'],))
                    st.rerun()
                
                # زر الحذف الحقيقي (Delete)
                if c3.button("🗑️", key=f"del_{row['button_id']}"):
                    cur.execute("DELETE FROM bot_dynamic_buttons WHERE button_id = %s", (row['button_id'],))
                    st.rerun()
        
        with col_add:
            st.write("➕ **إضافة زر جديد (مثلاً: الويكند):**")
            with st.form("add_btn_form"):
                new_t = st.text_input("اسم الزر")
                new_c = st.text_input("Callback (الأمر)")
                if st.form_submit_button("إضافة للواجهة"):
                    cur.execute("INSERT INTO bot_dynamic_buttons (button_text, button_callback) VALUES (%s, %s)", (new_t, new_c))
                    st.rerun()

        st.divider()

        # --- 2. الرسائل الجماعية والتحديثات (Broadcast) ---
        st.subheader("📢 إرسال تحديث أو رسالة جماعية")
        with st.form("broadcast_center"):
            msg = st.text_area("نص الرسالة أو تفاصيل التحديث")
            target = st.selectbox("الفئة المستهدفة", ["الكل", "VIP", "المستخدمين الجدد"])
            if st.form_submit_button("بث الرسالة الآن"):
                # الربط بجدول broadcast_logs اللي في قاعدة بياناتك
                cur.execute("INSERT INTO broadcast_logs (message_text, target_audience, sent_at) VALUES (%s, %s, NOW())", (msg, target))
                st.success("تم إرسال الرسالة وتسجيل العملية في السجلات.")

        st.divider()

        # --- 3. مراقبة الصحة الحقيقية (بدون أرقام وهمية) ---
        st.subheader("📊 مؤشرات الأداء الفعلية")
        m1, m2, m3 = st.columns(3)

        # أ) حجم قاعدة البيانات الحقيقي
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size = cur.fetchone()[0]
        m1.metric("حجم البيانات", db_size)

        # ب) روابط الماستر المتعطلة حقيقياً
        cur.execute("SELECT COUNT(*) FROM master WHERE performance_status IN ('broken', '404')")
        broken_count = cur.fetchone()[0]
        m2.metric("روابط تحتاج صيانة", broken_count, delta=f"{broken_count} رابط", delta_color="inverse")

        # ج) عدد اليوزرز النشطين اليوم
        cur.execute("SELECT COUNT(*) FROM bot_users WHERE last_seen > NOW() - INTERVAL '24 hours'")
        active_today = cur.fetchone()[0]
        m3.metric("نشاط المستخدمين (24س)", active_today)

        st.divider()

        # --- 4. سجل أحداث النظام ---
        st.subheader("📜 سجل العمليات التقني")
        try:
            df_app_logs = pd.read_sql("""
                SELECT created_at AS "الوقت", log_type AS "النوع", action_details AS "التفاصيل"
                FROM app_monitor ORDER BY created_at DESC LIMIT 15
            """, conn)
            st.dataframe(df_app_logs, width='stretch', hide_index=True)
        except Exception:
            st.info("سيظهر سجل الأحداث هنا فور توليد النظام تسجيلات.")

        st.divider()

        # --- 5. النسخ الاحتياطي الشامل ---
        st.subheader("💾 النسخ الاحتياطي")
        st.info("تحميل نسخة كاملة من قاعدة البيانات بصيغة Excel (ورقة لكل جدول رئيسي).")
        if st.button("📥 توليد نسخة احتياطية الآن", width='stretch'):
            try:
                backup_buf = BytesIO()
                backup_tables = {
                    "master":          "SELECT * FROM master ORDER BY id",
                    "bot_users":       "SELECT telegram_id, username, joined_at, last_seen, loyalty_rank, marketing_segment, country, city, device_type, lang FROM bot_users ORDER BY joined_at",
                    "action_logs":     "SELECT * FROM action_logs ORDER BY action_time DESC LIMIT 5000",
                    "broadcast_logs":  "SELECT * FROM broadcast_logs ORDER BY sent_at DESC",
                    "direct_search":   "SELECT * FROM direct_search ORDER BY search_date DESC LIMIT 3000",
                    "categories_tags": "SELECT * FROM categories_tags ORDER BY id",
                    "users_master":    "SELECT * FROM users_master ORDER BY user_id",
                    "loyalty_history": "SELECT * FROM loyalty_history ORDER BY log_date DESC LIMIT 2000",
                }
                with pd.ExcelWriter(backup_buf, engine='xlsxwriter') as writer:
                    for sheet_name, sql in backup_tables.items():
                        try:
                            df_t = pd.read_sql(sql, conn)
                            df_t.to_excel(writer, index=False, sheet_name=sheet_name[:31])
                        except Exception:
                            pass
                backup_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    label="⬇️ تحميل النسخة الاحتياطية",
                    data=backup_buf.getvalue(),
                    file_name=f"DealPulse_Backup_{backup_ts}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                )
                st.success(f"✅ النسخة الاحتياطية جاهزة — {backup_ts}")
            except Exception as e:
                st.error(f"❌ فشل توليد النسخة: {e}")

        conn.close()



















# --- الصفحة الواحدة والثلاثين: محرك النشر المستقل لشبكة القنوات ---
elif page == "مدير القناة":
    page_title("📢", "محرك النشر المستقل لشبكة القنوات")
    
    conn = get_conn()
    if conn:
        conn.autocommit = True
        cur = conn.cursor()

        # 1. جلب القنوات الحقيقية من جدولك available_channels
        # هكذا لو أضفت قناة ثالثة في pgAdmin ستظهر هنا فوراً
        cur.execute("SELECT channel_name FROM available_channels WHERE is_active = TRUE")
        rows = cur.fetchall()
        channels_list = [row[0] for row in rows] if rows else ["القناة العامة 📢"]

        tab_entry, tab_queue = st.tabs(["📝 تعبئة روابط النشر", "⏳ قائمة الانتظار والجدولة"])

        # --- الجزء الأول: تعبئة الروابط وتوجيهها للقناة المناسبة ---
        with tab_entry:
            st.subheader("إضافة عروض جديدة للجدولة")
            with st.form("ads_form_v3", clear_on_submit=True):
                col_in1, col_in2 = st.columns(2)
                with col_in1:
                    ad_title = st.text_input("عنوان العرض:")
                    ad_link = st.text_input("رابط المنتج/الأفلييت:")
                    # القائمة المنسدلة تقرأ الآن من داتابيز
                    target_ch = st.selectbox("توجيه المنشور إلى:", channels_list)
                with col_in2:
                    ad_coupon = st.text_input("كود الخصم (إن وجد):")
                    ad_category = st.selectbox("تصنيف العرض:", ["أزياء", "إلكترونيات", "تجميل", "منزل"])
                
                ad_note = st.text_area("وصف حماسي للمنشور:", placeholder="يا بلاش! الخصم قوي...")
                
                if st.form_submit_button("➕ إضافة إلى قاعدة البيانات"):
                    if ad_title and ad_link:
                        # إدخال العرض مع تحديد القناة المستهدفة في الجدول
                        cur.execute("""
                            INSERT INTO channel_ads_queue (ad_title, ad_link, ad_category, ad_coupon, ad_note, target_channel, status)
                            VALUES (%s, %s, %s, %s, %s, %s, 'مجدول ⏳')
                        """, (ad_title, ad_link, ad_category, ad_coupon, ad_note, target_ch))
                        st.success(f"✅ تم الحفظ وتوجيه العرض إلى: {target_ch}")

        # --- الجزء الثاني: إدارة طابور النشر الذكي ---
        with tab_queue:
            st.subheader("🕒 جدولة أوقات النشر")
            
            # حل تقني جذري لمشكلة TypeError بجعل الوقت كائن مستقل تماماً
            # السطر 2493: اختيار وقت البدء (ساعة ودقيقة)
        start_time = st.time_input("حدد وقت بدء أول منشور اليوم:", value=datetime.time(21, 0))
        
        # السطر 2494: الفوارق مفتوحة من دقيقة إلى 24 ساعة (1440 دقيقة)
        interval = st.slider("الفارق الزمني (بالدقائق):", min_value=1, max_value=1440, value=30, step=1)
        
        # إضافة لمسة ذكاء: عرض الفارق بالساعات لو كان كبير
        if interval >= 60:
            st.caption(f"💡 الفارق الحالي: {interval // 60} ساعة و {interval % 60} دقيقة")

            st.divider()
            
            # عرض العروض المجدولة فعلياً من قاعدة البيانات
            st.subheader("📋 العروض المجدولة حالياً")
            query_view = "SELECT ad_id, ad_title as العرض, target_channel as القناة, status as الحالة FROM channel_ads_queue WHERE status = 'مجدول ⏳' ORDER BY ad_id ASC"
            df_q = pd.read_sql(query_view, conn)
            
            if not df_q.empty:
                st.dataframe(df_q[["العرض", "القناة", "الحالة"]], width='stretch')
                
                if st.button("🔥 تفعيل النشر لجميع القنوات"):
                    # توثيق التفعيل في سجلات النظام الحقيقية
                    cur.execute("INSERT INTO system_logs (event_name, event_status) VALUES ('محرك القنوات', 'تفعيل شبكة النشر')")
                    st.success(f"القبضة الحديدية تعمل! جاري معالجة {len(df_q)} منشور.")
            else:
                st.info("لا توجد عروض مجدولة في القاعدة حالياً.")

        conn.close()












# --- الصفحة الثانية والثلاثين: محرك التحفيز الفوري (الإصدار الاحترافي المفتوح) ---
elif page == "المحفز الفوري":
    page_title("⚡", "محرك التحفيز الفوري (Booster Engine)")
    
    conn = get_conn()
    if conn:
        conn.autocommit = True
        cur = conn.cursor()

        # تبويبات لتنظيم العمل بين الإدارة والتحقق والجداول
        tab_launch, tab_verify, tab_history = st.tabs(["🚀 إطلاق عرض فوري", "📸 تعميد الفواتير", "📋 سجل المحفزات"])

        # --- التبويب الأول: إطلاق العروض (مع الفوارق المفتوحة) ---
        with tab_launch:
            col1, col2 = st.columns([1, 1.2])
            with col1:
                st.subheader("🔥 إنشاء محفز جديد")
                with st.form("flash_offer_form", clear_on_submit=True):
                    o_title = st.text_input("اسم العرض (مثلاً: فزعة الرواتب):")
                    o_points = st.number_input("النقاط الهدية:", min_value=1, value=500)
                    o_coupon = st.text_input("الكود المطلوب استخدامه:", placeholder="AMAZON20")
                    
                    # هنا الفوارق المفتوحة من دقيقة ليوم كامل (1440 دقيقة)
                    o_duration = st.slider("مدة صلاحية المحفز (بالدقائق):", 1, 1440, 60)
                    
                    if st.form_submit_button("🚀 إرسال وبرمجة المحفز"):
                        # الحفظ في جدول flash_offers_queue
                        cur.execute("""
                            INSERT INTO flash_offers_queue (offer_title, reward_points, duration_minutes, target_coupon)
                            VALUES (%s, %s, %s, %s)
                        """, (o_title, o_points, o_duration, o_coupon))
                        st.success(f"تم إطلاق '{o_title}' بنجاح لمدة {o_duration} دقيقة!")

            with col2:
                st.subheader("🎯 معاينة العرض للجمهور")
                with st.container(border=True):
                    st.info(f"🎁 **المكافأة:** {o_points} نقطة ولاء")
                    st.error(f"⏰ ينتهي خلال: {o_duration} دقيقة")
                    st.write(f"🏷️ الكود: **{o_coupon if o_coupon else 'غير محدد'}**")
                    if st.button("📢 تنبيه المشتركين آلياً"):
                        st.toast("جاري إرسال التنبيه لكل المشتركين...")

        # --- التبويب الثاني: تعميد الفواتير (نظام التحقق) ---
        with tab_verify:
            st.subheader("📸 مركز التحقق من الفواتير المرفوعة")
            col_up, col_log = st.columns([1, 1])
            with col_up:
                # رفع الفاتورة
                u_handle = st.text_input("يوزر المستخدم (@):")
                uploaded_file = st.file_uploader("ارفع صورة الفاتورة للمراجعة:", type=['jpg', 'png'])
                if uploaded_file and u_handle:
                    if st.button("✅ تعميد النقاط يدوياً"):
                        # حفظ السجل في جدول invoice_verifications
                        cur.execute("""
                            INSERT INTO invoice_verifications (user_handle, status)
                            VALUES (%s, 'مقبول ✅')
                        """, (u_handle,))
                        st.success(f"تم إضافة {o_points} نقطة لـ {u_handle}")

        # --- التبويب الثالث: سجل المحفزات (الجداول الحقيقية) ---
        with tab_history:
            st.subheader("📊 أرشيف المحفزات المجدولة")
            # قراءة البيانات من الجدول اللي سويته في pgAdmin
            query = "SELECT offer_id as ID, offer_title as العنوان, reward_points as النقاط, duration_minutes as المدة FROM flash_offers_queue ORDER BY offer_id DESC"
            df_history = pd.read_sql(query, conn)
            if not df_history.empty:
                st.dataframe(df_history, width='stretch')
            else:
                st.info("لا يوجد سجلات حالياً. ابدأ بإضافة أول محفز!")

        conn.close()


# ─── تحليل الموقع (5 تبويبات) ────────────────────────────────────────────────
elif page == "تحليل الموقع":
    page_title("🌐", "مركز تحليل الموقع — dealpulseksa.com")
    st.caption("إحصائيات وتحليلات الزيارات والمستخدمين القادمين عبر الموقع.")
    st.divider()

    tab_overview, tab_users, tab_events, tab_search, tab_geo = st.tabs([
        "📊 نظرة عامة",
        "👥 نمو المستخدمين",
        "🎯 الأحداث",
        "🔍 البحث",
        "🗺️ الجغرافيا",
    ])

    def _web_conn():
        """اتصال جديد معطّل التعاملات — يُغلق يدوياً بعد الاستخدام."""
        c = get_conn()
        c.autocommit = True
        return c

    # ── تبويب 1: نظرة عامة ────────────────────────────────────────────
    with tab_overview:
        try:
            conn = _web_conn()
            st.subheader("📊 مؤشرات أداء الموقع")
            kpi_web = pd.read_sql("""
                SELECT
                    (SELECT COUNT(*) FROM web_users WHERE password_hash IS NOT NULL)                  AS total_reg_users,
                    (SELECT COUNT(*) FROM web_users WHERE created_at >= NOW() - INTERVAL '30 days')   AS new_30d,
                    (SELECT COUNT(*) FROM action_logs WHERE source = 'web')                           AS total_web_actions,
                    (SELECT COUNT(*) FROM action_logs WHERE source='web' AND action_type='copy_coupon') AS web_copies,
                    (SELECT COUNT(*) FROM action_logs WHERE source='web' AND action_type='click_link') AS web_clicks,
                    (SELECT COUNT(*) FROM direct_search WHERE platform = 'Web')                       AS web_searches
            """, conn)
            if not kpi_web.empty:
                r = kpi_web.iloc[0]
                c1, c2, c3 = st.columns(3)
                with c1: kpi_card("👥", "المستخدمون المسجّلون", f"{int(r['total_reg_users']):,}", accent="emerald")
                with c2: kpi_card("🆕", "جدد آخر 30 يوم",      f"{int(r['new_30d']):,}",          accent="info")
                with c3: kpi_card("⚡", "إجمالي أحداث الموقع",  f"{int(r['total_web_actions']):,}", accent="warning")
                c4, c5, c6 = st.columns(3)
                with c4: kpi_card("📋", "نسخ الكوبونات", f"{int(r['web_copies']):,}",  accent="purple")
                with c5: kpi_card("🔗", "نقرات الروابط", f"{int(r['web_clicks']):,}",  accent="red")
                with c6: kpi_card("🔍", "عمليات البحث",  f"{int(r['web_searches']):,}", accent="blue")
            st.write("### ⚖️ مقارنة الموقع والبوت")
            compare_df = pd.read_sql("""
                SELECT
                    COALESCE(source, 'unknown')                          AS "المصدر",
                    COUNT(*)                                             AS "الأحداث",
                    COUNT(DISTINCT store_id)                             AS "المتاجر المتفاعلة",
                    COUNT(*) FILTER (WHERE action_type = 'copy_coupon') AS "نسخ",
                    COUNT(*) FILTER (WHERE action_type = 'click_link')  AS "نقرات"
                FROM action_logs
                GROUP BY source ORDER BY COUNT(*) DESC
            """, conn)
            if not compare_df.empty:
                st.dataframe(compare_df, width='stretch', hide_index=True)
                fig_cmp = px.bar(compare_df, x="المصدر", y="الأحداث",
                                 title="توزيع الأحداث بحسب المصدر", color="المصدر",
                                 color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig_cmp, width='stretch')
        except Exception as e:
            st.error(f"⚠️ خطأ في نظرة عامة: {e}")
        finally:
            if 'conn' in locals(): conn.close()

    # ── تبويب 2: نمو المستخدمين ───────────────────────────────────────
    with tab_users:
        try:
            conn = _web_conn()
            st.subheader("👥 نمو المستخدمين المسجّلين")
            growth_df = pd.read_sql("""
                SELECT
                    DATE(created_at)                                AS "التاريخ",
                    COUNT(*)                                        AS "مسجّلون جدد",
                    SUM(COUNT(*)) OVER (ORDER BY DATE(created_at)) AS "الإجمالي التراكمي"
                FROM web_users
                WHERE password_hash IS NOT NULL
                GROUP BY DATE(created_at) ORDER BY 1
            """, conn)
            if not growth_df.empty:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.plotly_chart(px.bar(growth_df, x="التاريخ", y="مسجّلون جدد",
                                           title="التسجيلات اليومية",
                                           color_discrete_sequence=["#10B981"]),
                                    width='stretch')
                with col_g2:
                    st.plotly_chart(px.line(growth_df, x="التاريخ", y="الإجمالي التراكمي",
                                            title="النمو التراكمي",
                                            color_discrete_sequence=["#6366F1"]),
                                    width='stretch')
            else:
                st.info("لا يوجد مستخدمون مسجّلون بعد.")
            st.write("### 📊 تصنيف نشاط المستخدمين")
            activity_df = pd.read_sql("""
                SELECT
                    CASE
                        WHEN last_seen >= NOW() - INTERVAL '1 day'   THEN 'نشط اليوم'
                        WHEN last_seen >= NOW() - INTERVAL '7 days'  THEN 'نشط الأسبوع'
                        WHEN last_seen >= NOW() - INTERVAL '30 days' THEN 'نشط الشهر'
                        ELSE 'غير نشط'
                    END AS "الفئة",
                    COUNT(*) AS "العدد"
                FROM web_users WHERE password_hash IS NOT NULL GROUP BY 1
            """, conn)
            if not activity_df.empty:
                st.plotly_chart(px.pie(activity_df, names="الفئة", values="العدد",
                                       title="تصنيف نشاط المستخدمين",
                                       color_discrete_sequence=px.colors.qualitative.Pastel),
                                width='stretch')
        except Exception as e:
            st.error(f"⚠️ خطأ في نمو المستخدمين: {e}")
        finally:
            if 'conn' in locals(): conn.close()

    # ── تبويب 3: الأحداث ──────────────────────────────────────────────
    with tab_events:
        try:
            conn = _web_conn()
            st.subheader("🎯 تحليل أحداث الموقع")
            events_df = pd.read_sql("""
                SELECT action_type AS "نوع الحدث", COUNT(*) AS "العدد",
                       COUNT(DISTINCT store_id) AS "عدد المتاجر",
                       DATE(MIN(action_time)) AS "أول حدث", DATE(MAX(action_time)) AS "آخر حدث"
                FROM action_logs WHERE source = 'web'
                GROUP BY action_type ORDER BY COUNT(*) DESC
            """, conn)
            if not events_df.empty:
                st.plotly_chart(px.pie(events_df, names="نوع الحدث", values="العدد",
                                       title="توزيع أنواع الأحداث من الموقع",
                                       color_discrete_sequence=["#10B981","#6366F1","#F59E0B","#EF4444"]),
                                width='stretch')
                st.dataframe(events_df, width='stretch', hide_index=True)
            else:
                st.info("لا توجد أحداث من الموقع بعد.")
            st.write("### 🏆 أفضل المتاجر من الموقع")
            top_web = pd.read_sql("""
                SELECT store_id AS "المتجر", COUNT(*) AS "الأحداث",
                       COUNT(*) FILTER (WHERE action_type='copy_coupon') AS "نسخ",
                       COUNT(*) FILTER (WHERE action_type='click_link')  AS "نقرات"
                FROM action_logs WHERE source = 'web'
                GROUP BY store_id ORDER BY COUNT(*) DESC LIMIT 20
            """, conn)
            if not top_web.empty:
                st.plotly_chart(px.bar(top_web.head(10), x="المتجر", y="الأحداث",
                                       title="أكثر 10 متاجر تفاعلاً من الموقع",
                                       color_discrete_sequence=["#10B981"]),
                                width='stretch')
                st.dataframe(top_web, width='stretch', hide_index=True)
            st.write("### ⏰ الأحداث اليومية (آخر 30 يوم)")
            time_ev = pd.read_sql("""
                SELECT DATE(action_time) AS "التاريخ",
                       COUNT(*) FILTER (WHERE action_type='copy_coupon') AS "نسخ",
                       COUNT(*) FILTER (WHERE action_type='click_link')  AS "نقرات"
                FROM action_logs WHERE source = 'web'
                GROUP BY DATE(action_time) ORDER BY 1 DESC LIMIT 30
            """, conn)
            if not time_ev.empty:
                st.plotly_chart(px.line(time_ev, x="التاريخ", y=["نسخ","نقرات"],
                                        title="الأحداث اليومية — آخر 30 يوم",
                                        color_discrete_sequence=["#10B981","#6366F1"]),
                                width='stretch')
        except Exception as e:
            st.error(f"⚠️ خطأ في الأحداث: {e}")
        finally:
            if 'conn' in locals(): conn.close()

    # ── تبويب 4: البحث ────────────────────────────────────────────────
    with tab_search:
        try:
            conn = _web_conn()
            st.subheader("🔍 تحليل بحث الموقع")
            srch_kpi = pd.read_sql("""
                SELECT
                    COUNT(*)                                                                            AS "إجمالي البحث",
                    COUNT(*) FILTER (WHERE user_found = true)                                          AS "وجد نتائج",
                    COUNT(*) FILTER (WHERE user_found = false)                                         AS "لم يجد نتائج",
                    ROUND(COUNT(*) FILTER (WHERE user_found=true)::numeric/NULLIF(COUNT(*),0)*100, 1) AS "نسبة النجاح"
                FROM direct_search WHERE platform = 'Web'
            """, conn)
            if not srch_kpi.empty:
                r2 = srch_kpi.iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                with c1: kpi_card("🔍", "إجمالي البحث",  f"{int(r2['إجمالي البحث']):,}", accent="blue")
                with c2: kpi_card("✅", "وجد نتائج",     f"{int(r2['وجد نتائج']):,}",     accent="emerald")
                with c3: kpi_card("❌", "لم يجد نتائج",  f"{int(r2['لم يجد نتائج']):,}", accent="red")
                with c4: kpi_card("📈", "نسبة النجاح",   f"{r2['نسبة النجاح']}%",         accent="purple")
            st.write("### 🔤 الكلمات الأكثر بحثاً")
            top_kw = pd.read_sql("""
                SELECT search_keyword AS "الكلمة", COUNT(*) AS "عدد البحث",
                       ROUND(AVG(CASE WHEN user_found THEN 1.0 ELSE 0.0 END)*100,0) AS "نسبة الإيجاد %"
                FROM direct_search WHERE platform = 'Web'
                GROUP BY search_keyword ORDER BY COUNT(*) DESC LIMIT 25
            """, conn)
            if not top_kw.empty:
                st.plotly_chart(px.bar(top_kw.head(15), x="الكلمة", y="عدد البحث",
                                       title="أكثر 15 كلمة مطلوبة من الموقع",
                                       color="نسبة الإيجاد %", color_continuous_scale="RdYlGn"),
                                width='stretch')
                st.dataframe(top_kw, width='stretch', hide_index=True)
            st.write("### 🚨 فجوات المحتوى (بحث بلا نتائج)")
            gaps_df = pd.read_sql("""
                SELECT search_keyword AS "الكلمة", COUNT(*) AS "مرات البحث",
                       MAX(search_date) AS "آخر بحث"
                FROM direct_search WHERE platform='Web' AND user_found=false
                GROUP BY search_keyword ORDER BY COUNT(*) DESC LIMIT 20
            """, conn)
            if not gaps_df.empty:
                gaps_df["آخر بحث"] = pd.to_datetime(gaps_df["آخر بحث"], errors="coerce").dt.strftime("%Y-%m-%d")
                st.dataframe(gaps_df, width='stretch', hide_index=True)
            else:
                st.success("✅ لا توجد فجوات — كل البحث يجد نتائج!")
        except Exception as e:
            st.error(f"⚠️ خطأ في البحث: {e}")
        finally:
            if 'conn' in locals(): conn.close()

    # ── تبويب 5: الجغرافيا ────────────────────────────────────────────
    with tab_geo:
        try:
            conn = _web_conn()
            st.subheader("🗺️ التوزيع الجغرافي للمستخدمين")
            city_df = pd.read_sql("""
                SELECT COALESCE(city, 'غير محدد') AS "المدينة", COUNT(*) AS "العدد"
                FROM web_users WHERE password_hash IS NOT NULL
                GROUP BY city ORDER BY COUNT(*) DESC LIMIT 15
            """, conn)
            country_df = pd.read_sql("""
                SELECT COALESCE(country, 'غير محدد') AS "الدولة", COUNT(*) AS "العدد"
                FROM web_users WHERE password_hash IS NOT NULL
                GROUP BY country ORDER BY COUNT(*) DESC
            """, conn)
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if not city_df.empty:
                    st.plotly_chart(px.bar(city_df, x="المدينة", y="العدد",
                                           title="توزيع المستخدمين بالمدن",
                                           color_discrete_sequence=["#10B981"]),
                                    width='stretch')
                else:
                    st.info("لا توجد بيانات مدن بعد.")
            with col_c2:
                if not country_df.empty:
                    st.plotly_chart(px.pie(country_df, names="الدولة", values="العدد",
                                           title="توزيع الدول",
                                           color_discrete_sequence=px.colors.qualitative.Set2),
                                    width='stretch')
                else:
                    st.info("لا توجد بيانات دول بعد.")
            st.write("### 📱 أنواع الأجهزة")
            device_df = pd.read_sql("""
                SELECT COALESCE(device_type, 'غير محدد') AS "الجهاز", COUNT(*) AS "العدد"
                FROM web_users WHERE password_hash IS NOT NULL
                GROUP BY device_type ORDER BY COUNT(*) DESC
            """, conn)
            if not device_df.empty:
                st.plotly_chart(px.pie(device_df, names="الجهاز", values="العدد",
                                       title="توزيع أنواع الأجهزة",
                                       color_discrete_sequence=px.colors.qualitative.Pastel),
                                width='stretch')
        except Exception as e:
            st.error(f"⚠️ خطأ في الجغرافيا: {e}")
        finally:
            if 'conn' in locals(): conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# محرّك SEO — مراجعة ونشر صفحات الهبوط المولّدة تلقائياً (Week 5-6)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "محرّك SEO":
    st.header("🔍 محرّك صفحات SEO")
    st.caption("توليد ومراجعة وتعديل وحذف ونشر صفحات الـ landing من واجهة واحدة.")

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
                data, err = _admin_post("/admin/seo-run", params={"batch": int(batch_size)})
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
# 📤 الصفحات المنشورة — متابعة حالة صفحات SEO بعد النشر
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📤 الصفحات المنشورة":
    st.header("📤 الصفحات المنشورة")
    st.caption("متابعة صفحات SEO بعد النشر — رابط الصفحة الحيّة، حالة Google، فهرسة سريعة.")

    import os
    site_url = os.getenv("SITE_URL", "https://dealpulseksa.com").rstrip("/")

    top1, top2, top3 = st.columns([1, 1, 2])
    with top1:
        if st.button("🔄 تحديث", width='stretch'):
            st.rerun()
    with top2:
        lang_pub_filter = st.selectbox("اللغة", ["الكل", "عربي", "إنجليزي"], key="pub_lang")
    with top3:
        st.caption(f"الموقع: `{site_url}`")

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
# التدقيق والتجارب — Audit log + Quiet hours + A/B experiments (migration_016)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "التدقيق والتجارب":
    st.header("🛡️ التدقيق والتجارب")
    st.caption("سجل عمليات الأدمن (PDPL)، ساعات كتم التنبيهات، ونتائج تجارب A/B للردود.")

    tab_audit, tab_quiet, tab_exp = st.tabs(
        ["📜 سجل التدقيق", "🌙 ساعات الهدوء", "🧪 تجارب A/B"]
    )

    # ── سجل التدقيق ──
    with tab_audit:
        data, err = _admin_get("/admin/audit-log", params={"limit": 100})
        if err:
            st.error(err)
        elif not data or not data.get("entries"):
            st.info("لا توجد عمليات مُسجّلة بعد.")
        else:
            import pandas as _pd
            df = _pd.DataFrame(data["entries"])
            df = df.rename(columns={"at": "الوقت", "action": "العملية", "target": "الهدف",
                                    "actor": "المنفّذ", "status": "الحالة", "id": "#"})
            st.dataframe(df, width='stretch', hide_index=True)

    # ── ساعات الهدوء ──
    with tab_quiet:
        data, err = _admin_get("/admin/quiet-hours")
        if err:
            st.error(err)
        else:
            if data.get("email_muted_now"):
                st.warning(f"🔕 الإيميل مكتوم الآن (نافذة: {data.get('active_window') or '—'})")
            else:
                st.success("🔔 التنبيهات تُرسل الآن (لا نافذة كتم فعّالة).")
            for w in data.get("windows", []):
                with st.container(border=True):
                    cc1, cc2 = st.columns([4, 1])
                    with cc1:
                        chans = ", ".join(w.get("channels") or [])
                        st.markdown(f"**{w.get('label') or 'نافذة'}** — {w['start_hour']:02d}:00 ← {w['end_hour']:02d}:00 ({w.get('timezone')})")
                        st.caption(f"القنوات: {chans} · الحالة: {'مفعّلة ✅' if w.get('active') else 'متوقّفة'}")
                    with cc2:
                        lbl = "إيقاف" if w.get("active") else "تفعيل"
                        if st.button(lbl, key=f"qh_{w['id']}", width='stretch'):
                            _r, e2 = _admin_post(f"/admin/quiet-hours/{w['id']}/toggle")
                            if e2:
                                st.error(e2)
                            else:
                                st.rerun()

    # ── تجارب A/B ──
    with tab_exp:
        data, err = _admin_get("/admin/experiments")
        if err:
            st.error(err)
        elif not data or not data.get("results"):
            st.info("لا توجد بيانات تجارب بعد (تتراكم مع كل رد اجتماعي).")
        else:
            import pandas as _pd
            df = _pd.DataFrame(data["results"])
            df = df.rename(columns={"experiment": "التجربة", "surface": "السطح", "arm": "النسخة",
                                    "impressions": "ظهور", "clicks": "نقرات",
                                    "conversions": "تحويلات", "total_value": "القيمة"})
            st.dataframe(df, width='stretch', hide_index=True)
            st.caption("الظهور يُسجَّل عند توليد كل رد. النقرات/التحويلات تتفعّل مع ربط الإحالة لاحقاً.")


# ════════════════════════════════════════════════════════════════════════════
#  📊 تقرير الشركاء — Demo Pack للشركات المتعاقدة
#  لوحة KPI نظيفة قابلة للمشاركة + تصدير CSV/Excel + أرقام حقيقية فقط
# ════════════════════════════════════════════════════════════════════════════
elif page == "📊 تقرير الشركاء":
    page_title("📊", "تقرير أداء الشركاء",
               "بيانات حقيقية موثّقة من حركة المستخدمين الفعلية — للشركات المتعاقدة")

    # ── فلاتر زمنية ─────────────────────────────────────────────────────────
    f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
    with f_col1:
        period_label = st.selectbox(
            "📅 نافزة التقرير",
            ["آخر 7 أيام", "آخر 30 يوم", "آخر 90 يوم", "آخر سنة"],
            index=1,
            key="partner_period",
        )
    period_days = {"آخر 7 أيام": 7, "آخر 30 يوم": 30,
                    "آخر 90 يوم": 90, "آخر سنة": 365}[period_label]
    with f_col2:
        store_filter = st.text_input(
            "🏬 تصفية بمتجر (اختياري)",
            placeholder="مثل: نون، شي إن…",
            key="partner_store_filter",
        )
    with f_col3:
        st.caption(
            f"⏱️ يُحدَّث بشكل ديناميكي عند تغيير الفلاتر · "
            f"كل الأرقام من جدول action_logs الفعلي (لا توقّعات أو تقديرات)."
        )

    st.divider()

    # ── تحميل البيانات (يُخزَّن 3 دقائق لتقليل الضغط على DB) ──────────────
    @st.cache_data(ttl=180, show_spinner="جاري تحميل بيانات الشركاء…")
    def _partner_load(days: int, store_filter_text: str = "") -> dict:
        """يُحمّل كل المؤشرات اللازمة للتقرير في استعلام واحد لكل قسم."""
        out = {}
        c = get_conn()
        try:
            c.autocommit = True
            params = (days,)
            store_clause = ""
            if store_filter_text.strip():
                store_clause = " AND a.store_id ILIKE %s "
                params = (days, f"%{store_filter_text.strip()}%")

            # ─── 1. KPIs الإجمالية ─────────────────────────────────────────
            out["kpis"] = pd.read_sql(f"""
                SELECT
                    COUNT(*) AS total_events,
                    COUNT(DISTINCT a.user_id) FILTER (WHERE a.user_id IS NOT NULL) AS unique_users,
                    COUNT(*) FILTER (WHERE a.action_type='click_link')  AS total_clicks,
                    COUNT(*) FILTER (WHERE a.action_type='copy_coupon') AS total_copies,
                    COUNT(*) FILTER (WHERE a.action_type='search')      AS total_searches,
                    COUNT(DISTINCT a.store_id) FILTER (WHERE a.store_id IS NOT NULL) AS active_stores,
                    COUNT(*) FILTER (WHERE a.quality_score >= 50)       AS high_quality_events,
                    ROUND(AVG(a.quality_score)::numeric, 1)             AS avg_quality
                FROM action_logs a
                WHERE a.action_time >= NOW() - (%s || ' days')::interval
                {store_clause}
            """, c, params=params)

            # ─── 2. تطور الحركة يوميًا ─────────────────────────────────────
            out["daily"] = pd.read_sql(f"""
                SELECT
                    DATE(a.action_time AT TIME ZONE 'Asia/Riyadh') AS day,
                    COUNT(*) FILTER (WHERE a.action_type='click_link')  AS clicks,
                    COUNT(*) FILTER (WHERE a.action_type='copy_coupon') AS copies,
                    COUNT(*) FILTER (WHERE a.action_type='search')      AS searches
                FROM action_logs a
                WHERE a.action_time >= NOW() - (%s || ' days')::interval
                {store_clause}
                GROUP BY 1 ORDER BY 1
            """, c, params=params)

            # ─── 3. أعلى 20 متجر أداءً ─────────────────────────────────────
            top_params = params + (20,)
            out["top_stores"] = pd.read_sql(f"""
                SELECT
                    a.store_id,
                    COUNT(*) FILTER (WHERE a.action_type='click_link')  AS clicks,
                    COUNT(*) FILTER (WHERE a.action_type='copy_coupon') AS copies,
                    COUNT(DISTINCT a.user_id) FILTER (WHERE a.user_id IS NOT NULL) AS users,
                    ROUND(
                        100.0 * COUNT(*) FILTER (WHERE a.action_type='copy_coupon')::numeric
                        / NULLIF(COUNT(*) FILTER (WHERE a.action_type='click_link'), 0),
                        1
                    ) AS conversion_pct
                FROM action_logs a
                WHERE a.action_time >= NOW() - (%s || ' days')::interval
                  AND a.store_id IS NOT NULL
                {store_clause}
                GROUP BY a.store_id
                ORDER BY (
                    COUNT(*) FILTER (WHERE a.action_type='click_link') +
                    COUNT(*) FILTER (WHERE a.action_type='copy_coupon') * 2
                ) DESC
                LIMIT %s
            """, c, params=top_params)

            # ─── 4. توزيع جغرافي (مدن سعودية فقط) ──────────────────────────
            out["geo"] = pd.read_sql(f"""
                SELECT
                    COALESCE(NULLIF(a.city, ''), 'غير محدد') AS city,
                    COUNT(*) AS events,
                    COUNT(DISTINCT a.user_id) FILTER (WHERE a.user_id IS NOT NULL) AS users
                FROM action_logs a
                WHERE a.action_time >= NOW() - (%s || ' days')::interval
                  AND COALESCE(a.country_code, 'SA') = 'SA'
                {store_clause}
                GROUP BY 1
                ORDER BY events DESC
                LIMIT 15
            """, c, params=params)

            # ─── 5. توزيع الأجهزة ──────────────────────────────────────────
            out["devices"] = pd.read_sql(f"""
                SELECT
                    COALESCE(NULLIF(a.device_class, ''), 'unknown') AS device,
                    COUNT(*) AS events
                FROM action_logs a
                WHERE a.action_time >= NOW() - (%s || ' days')::interval
                {store_clause}
                GROUP BY 1
                ORDER BY events DESC
            """, c, params=params)

            # ─── 6. مصدر الحركة (بوت / موقع / mini-app) ────────────────────
            out["sources"] = pd.read_sql(f"""
                SELECT
                    COALESCE(a.source, 'unknown') AS source,
                    COUNT(*) AS events
                FROM action_logs a
                WHERE a.action_time >= NOW() - (%s || ' days')::interval
                {store_clause}
                GROUP BY 1
                ORDER BY events DESC
            """, c, params=params)

            # ─── 7. عدد المستخدمين الكلي والنشطين (للسياق) ────────────────
            out["users_summary"] = pd.read_sql("""
                SELECT
                    (SELECT COUNT(*) FROM bot_users)                                          AS bot_users_total,
                    (SELECT COUNT(*) FROM bot_users WHERE last_seen > NOW() - INTERVAL '7 days')  AS bot_users_7d,
                    (SELECT COUNT(*) FROM bot_users WHERE last_seen > NOW() - INTERVAL '30 days') AS bot_users_30d,
                    (SELECT COUNT(*) FROM web_users)                                          AS web_users_total,
                    (SELECT COUNT(*) FROM master WHERE COALESCE(public_coupon,'') <> '')      AS active_coupons,
                    (SELECT COUNT(*) FROM master WHERE is_trending='ترند 🔥')                  AS trending_stores
            """, c)
        finally:
            c.close()
        return out

    try:
        data = _partner_load(period_days, store_filter)
    except Exception as e:
        st.error(f"⚠️ تعذّر تحميل البيانات: {e}")
        st.stop()

    k = data["kpis"].iloc[0] if not data["kpis"].empty else None
    us = data["users_summary"].iloc[0] if not data["users_summary"].empty else None

    if k is None or int(k["total_events"]) == 0:
        st.warning(
            f"📭 لا توجد حركات مسجّلة خلال **{period_label}**"
            + (f" للمتجر «{store_filter}»" if store_filter else "")
            + ". جرّب نافذة زمنية أوسع، أو تأكّد أن البوت/الموقع يعمل."
        )
        st.stop()

    # ─── KPIs العليا ────────────────────────────────────────────────────────
    st.markdown("### 🎯 المؤشرات الرئيسية")
    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        kpi_card("👥", "مستخدمون فريدون",
                 f"{int(k['unique_users']):,}", "info",
                 note=f"إجمالي الأحداث: {int(k['total_events']):,}")
    with kc2:
        kpi_card("🔗", "نقرات الروابط",
                 f"{int(k['total_clicks']):,}", "emerald",
                 note="حركة من البوت + الموقع + الميني آب")
    with kc3:
        kpi_card("📋", "نسخ الأكواد",
                 f"{int(k['total_copies']):,}", "emerald",
                 note=f"معدل التحويل: {100*int(k['total_copies'])/max(1,int(k['total_clicks'])):.1f}%")
    with kc4:
        kpi_card("🏬", "متاجر فاعلة",
                 f"{int(k['active_stores']):,}", "warning",
                 note=f"جودة متوسطة: {k['avg_quality'] or 0}/100")

    if us is not None:
        st.caption(
            f"📌 السياق العام · "
            f"مستخدمو البوت: **{int(us['bot_users_total']):,}** · "
            f"نشطون آخر 7 أيام: **{int(us['bot_users_7d']):,}** · "
            f"مستخدمو الموقع: **{int(us['web_users_total']):,}** · "
            f"كوبونات فاعلة: **{int(us['active_coupons']):,}** · "
            f"متاجر ترند 🔥: **{int(us['trending_stores']):,}**"
        )

    st.divider()

    # ─── تطور الحركة يومياً ──────────────────────────────────────────────────
    if not data["daily"].empty:
        st.markdown("### 📈 تطور الحركة اليومية")
        df_d = data["daily"].copy()
        df_d["day"] = pd.to_datetime(df_d["day"])
        df_melt = df_d.melt(id_vars="day",
                            value_vars=["clicks", "copies", "searches"],
                            var_name="نوع الحدث", value_name="عدد")
        type_map = {"clicks": "🔗 نقرات", "copies": "📋 نسخ", "searches": "🔎 بحث"}
        df_melt["نوع الحدث"] = df_melt["نوع الحدث"].map(type_map)
        fig_d = px.area(df_melt, x="day", y="عدد", color="نوع الحدث",
                        title="حركة المستخدمين عبر الأيام", height=380)
        st.plotly_chart(apply_brand_theme(fig_d), width='stretch')

    # ─── أعلى المتاجر أداءً ─────────────────────────────────────────────────
    if not data["top_stores"].empty:
        st.markdown("### 🏆 أعلى 20 متجر أداءً")
        df_t = data["top_stores"].copy()
        df_t.columns = ["المتجر", "النقرات", "النسخ", "المستخدمون", "نسبة التحويل %"]
        st.dataframe(df_t, width='stretch', hide_index=True,
                     column_config={
                         "النقرات":        st.column_config.NumberColumn(format="%d"),
                         "النسخ":          st.column_config.NumberColumn(format="%d"),
                         "المستخدمون":     st.column_config.NumberColumn(format="%d"),
                         "نسبة التحويل %": st.column_config.NumberColumn(format="%.1f%%"),
                     })

    # ─── توزيع جغرافي + أجهزة + مصادر (3 أعمدة) ──────────────────────────
    col_geo, col_dev, col_src = st.columns(3)
    with col_geo:
        st.markdown("#### 📍 المدن")
        if not data["geo"].empty:
            df_g = data["geo"].copy()
            df_g.columns = ["المدينة", "أحداث", "مستخدمون"]
            st.dataframe(df_g, width='stretch', hide_index=True, height=320)
        else:
            st.info("لا توجد بيانات جغرافية بعد.")
    with col_dev:
        st.markdown("#### 📱 الأجهزة")
        if not data["devices"].empty:
            df_dv = data["devices"].copy()
            fig_dv = px.pie(df_dv, names="device", values="events",
                            title="", hole=0.4, height=260)
            st.plotly_chart(apply_brand_theme(fig_dv), width='stretch')
    with col_src:
        st.markdown("#### 🚪 المصدر")
        if not data["sources"].empty:
            df_s = data["sources"].copy()
            fig_s = px.pie(df_s, names="source", values="events",
                           title="", hole=0.4, height=260)
            st.plotly_chart(apply_brand_theme(fig_s), width='stretch')

    # ─── قمع التحويل ────────────────────────────────────────────────────────
    st.markdown("### 🎯 قمع التحويل (Funnel)")
    fn_searches = int(k["total_searches"] or 0)
    fn_clicks = int(k["total_clicks"] or 0)
    fn_copies = int(k["total_copies"] or 0)
    fn_df = pd.DataFrame({
        "المرحلة": ["🔎 بحث", "🔗 نقر رابط", "📋 نسخ كود"],
        "العدد":   [fn_searches, fn_clicks, fn_copies],
    })
    fig_fn = px.funnel(fn_df, x="العدد", y="المرحلة", height=300)
    st.plotly_chart(apply_brand_theme(fig_fn), width='stretch')

    # ─── تصدير ──────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📤 تصدير التقرير")
    exp_c1, exp_c2 = st.columns(2)
    with exp_c1:
        # CSV: أعلى المتاجر (مفيد للشركة المتعاقدة)
        if not data["top_stores"].empty:
            csv_bytes = data["top_stores"].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ تنزيل أعلى المتاجر (CSV)",
                data=csv_bytes,
                file_name=f"partner_top_stores_{period_days}d.csv",
                mime="text/csv",
                width='stretch',
            )
    with exp_c2:
        # CSV: التطور اليومي
        if not data["daily"].empty:
            csv_bytes = data["daily"].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ تنزيل التطور اليومي (CSV)",
                data=csv_bytes,
                file_name=f"partner_daily_{period_days}d.csv",
                mime="text/csv",
                width='stretch',
            )

    st.info(
        "💡 **ملاحظة للمشاركة:** كل الأرقام أعلاه مستخرجة من `action_logs` الحقيقي. "
        "نسبة التحويل تُحسب كـ (نسخ ÷ نقرات) — وهي مقياس صناعي معتمد. "
        "جودة الأحداث ≥50/100 تعني تم فلترة البوتات/Datacenters تلقائياً عبر Cloudflare + heuristics."
    )


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
    st.code(f"INTERNAL_API_URL = {_api_url}", language="text")
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
            if st.button("⚡ ولّد توجيهاً الآن", type="primary", use_container_width=True,
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

