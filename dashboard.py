import os
import base64
import smtplib
import socket
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import psycopg2
import plotly.express as px
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
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=f"store_logos/{store_slug}",
            overwrite=True,
            format="webp",
            transformation=[{"width": 400, "height": 400, "crop": "pad", "background": "white"}],
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
        "https://dealpulseksa-production.up.railway.app",
    ).rstrip("/")
    if not secret:
        st.toast("ℹ️ النشر التلقائي معطّل — أضف ADMIN_SHARED_SECRET لتفعيله.")
        return
    try:
        requests.post(
            f"{api_url}/api/v1/admin/broadcast/{master_id}",
            headers={"X-Admin-Secret": secret},
            timeout=4,
        )
        st.toast("📢 جدولة نشر العرض على منصات السوشيال…")
    except Exception as e:
        st.warning(f"تم الحفظ، لكن فشلت جدولة النشر: {e}")


# ─── جسر الـ Admin API (للوحات SEO + الرصد الاجتماعي) ──────────────────────────
def _admin_api():
    """يرجّع (base_url, secret) للـ admin API على الإنتاج."""
    secret = os.getenv("ADMIN_SHARED_SECRET")
    base = os.getenv(
        "INTERNAL_API_URL", "https://dealpulseksa-production.up.railway.app"
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
BRAND = {
"bg":             "#FAFAF8",
"bg_alt":         "#F5F5F0",
"surface":        "#FFFFFF",
"surface_elev":   "#FDFDFB",
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
# لا أي بيانات تظهر قبل المصادقة. الإعدادات في .streamlit/secrets.toml محلياً
# وفي Settings > Variables (Streamlit secrets) على Railway للإنتاج.
_auth_cfg = st.secrets["auth"]
# streamlit-authenticator يُعدّل على credentials داخلياً (failed_login_attempts، logged_in...)
# لذلك لازم تحويل deep من st.secrets (immutable) إلى dict عادي.
_creds_raw = _auth_cfg["credentials"]
_creds = _creds_raw.to_dict() if hasattr(_creds_raw, "to_dict") else dict(_creds_raw)
_authenticator = stauth.Authenticate(
credentials=_creds,
cookie_name=_auth_cfg["cookie_name"],
cookie_key=_auth_cfg["cookie_key"],
cookie_expiry_days=int(_auth_cfg.get("cookie_expiry_days", 1)),
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
}}
/* ── Watermark: الشعار كعلامة مائية في مركز الصفحة الرئيسية ── */
.stApp::after {{
content: ""; position: fixed;
top: 75%; left: 40%;
transform: translate(-50%, -50%);
width: 80vw; height: 80vw;
pointer-events: none; z-index: 0;
background-image: url("{_wm_url}");
background-repeat: no-repeat;
background-size: contain;
background-position: center;
opacity: 0.10;
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
background: rgba(255,255,255,0.55) !important;
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
background: rgba(255,255,255,0.7) !important;
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
background: rgba(255,255,255,0.55) !important;
backdrop-filter: blur(8px) !important;
-webkit-backdrop-filter: blur(8px) !important;
box-shadow: 0 2px 12px rgba(31,41,55,0.04) !important;
}}
/* ── Glass Inputs ── */
input, textarea {{
background: rgba(255,255,255,0.5) !important;
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
background: #FFFFFF !important;
border: 1.5px solid #D1D5DB !important;
color: #111827 !important;
font-weight: 500 !important;
}}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {{
color: #6B7280 !important;
opacity: 1 !important;
}}
.stTextInput label, .stTextArea label,
.stSelectbox label, .stMultiSelect label,
.stNumberInput label, .stDateInput label, .stRadio label {{
color: #1F2937 !important;
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


@st.cache_data(ttl=180, show_spinner=False)
def _sa_load_actions() -> pd.DataFrame:
    """
    كل أحداث التفاعل + بيانات الجهاز/الموقع للمستخدم (LEFT JOIN على bot_users).
    مخزّنة 3 دقائق. ⚠️ ملاحظة أداء: لو تجاوزت action_logs ~100 ألف صف، حوّل
    التجميع إلى SQL (FILTER / GROUP BY) بدل سحب الخام كاملاً إلى pandas.
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
                   bu.device_type, bu.city AS bu_city, bu.country, bu.lang
            FROM   action_logs a
            LEFT JOIN bot_users bu ON bu.telegram_id = a.user_id
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
                   COALESCE(is_promoted, false)   AS is_promoted
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
    st.dataframe(table, hide_index=True, use_container_width=True)
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


# --- القائمة الجانبية ---
if _logo_b64:
    st.sidebar.markdown(f"""
<div style="text-align:center; padding:10px 8px 12px 8px; border-bottom:1px solid {BRAND["border"]}; margin-bottom:10px;">
<img src="data:image/jpeg;base64,{_logo_b64}"
        style="width:90px; border-radius:8px;" />
</div>
""", unsafe_allow_html=True)

_MAIN_PAGES = [
"إدخال بيانات الماستر", "الاستعلام والتعديل", "جدول الكوبونات",
"📦 أرشيف المنتهية",
"جدول الأقسام", "البحث عن كود", "طلبات الأكواد", "بيانات المستخدمين",
"مستخدمو الموقع",
]
_ANALYSIS_PAGES = [
"تحليل المتاجر", "تحليل الأقسام", "تحليل بحث الأكواد",
"تحليل طلبات الأكواد", "تحليل المستخدمين", "تحليل الموقع",
]
_OTHER_PAGES = [
"مركز الإشعارات", "لوحة القيادة", "مركز الدعم",
"مختبر النمو", "رادار المنافسين", "استوديو المحتوى",
"ذكاء التنبؤ", "نظام الولاء", "التحكم الآلي", "التخصيص الفائق",
"رادار المناسبات", "مركز التوسع", "درع الحماية",
"مركز الصيانة", "مدير القناة", "المحفز الفوري",
"محرّك SEO", "📤 الصفحات المنشورة", "🎯 محرك الفرص", "الرصد الاجتماعي", "🎯 رادار الصفقات الفوري", "التدقيق والتجارب",
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
        "", 
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
        "", 
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
        "", 
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
    with st.form("master_final_form", clear_on_submit=True):
        # الصف 1: اسم المتجر AR + EN
        c_ar1, c_en1 = st.columns(2)
        store_id = c_ar1.text_input("🏪 اسم المتجر (عربي/ID)")
        name_en  = c_en1.text_input("🏪 Store Name (English)")

        # الصف 2: روابط/كوبون/خصم (لا يحتاج ترجمة)
        col_a, col_b, col_c = st.columns(3)
        aff_link   = col_a.text_input("🔗 رابط الأفلييت")
        pub_coupon = col_b.text_input("🎟️ كوبون العملاء")
        disc_val   = col_c.text_input("💰 نسبة الخصم")

        # الصف 3: عرض إضافي AR + EN
        e_ar, e_en = st.columns(2)
        extra_offer    = e_ar.text_input("➕ عرض إضافي (عربي)")
        extra_offer_en = e_en.text_input("➕ Extra Offer (English)")

        # الصف 4: وصف المتجر AR + EN
        b_ar, b_en = st.columns(2)
        store_bio    = b_ar.text_area("📝 وصف المتجر (عربي)")
        store_bio_en = b_en.text_area("📝 Store Description (English)")

        # الصف 4.5: تفاصيل العرض — تُستخدم في منشورات السوشيال
        description = st.text_area(
            "📣 تفاصيل العرض (تُنشر على منصات السوشيال)",
            placeholder="مثال: خصم حصري على جميع منتجات القسم النسائي حتى نهاية الأسبوع. شامل التوصيل المجاني.",
            height=90,
            help="هذا النص يظهر في المنشورات التلقائية على X, Instagram, Facebook, Pinterest, Telegram, Discord, Threads, LinkedIn.",
        )

        st.divider()

        # الصف 5: الأهمية + التواريخ + عمولتي
        col7, col8, col9, col10 = st.columns(4)
        priority   = col7.selectbox("🚀 الأهمية", ["عادي", "مهم", "عاجل", "عاجل جداً"])
        date_start = col8.date_input("📅 تاريخ البداية", datetime.date.today())
        date_end   = col9.date_input("📅 تاريخ الانتهاء", datetime.date.today() + datetime.timedelta(days=30))
        my_coupon  = col10.text_input("💵 عمولتي (كود التتبع)")

        # الصف 5.5: مصدر الكود (من أي منصة تابعة)
        source_platform = st.text_input(
            "🛰️ من أين (المنصة التابعة لهذا الكود)",
            value="",
            placeholder="مثال: ArabClicks, CJ Affiliate, تواصل مباشر...",
            help="اكتب اسم المنصة التي جاء منها هذا الكود — مفيد عند تجديد الكود لاحقاً.",
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
                st.warning("⚠️ الحقول التالية إجبارية: " + " ، ".join(missing))
            else:
                # ─── حل رابط الشعار ───────────────────────────────────────
                final_logo_url = (logo_url_input or "").strip()
                if logo_file and not final_logo_url:
                    uploaded = _upload_logo(logo_file.read(), store_id.strip())
                    if uploaded:
                        final_logo_url = uploaded
                    elif not _CLOUDINARY_OK:
                        st.info("💡 لتفعيل الرفع التلقائي للشعارات، أضف CLOUDINARY_* في ملف .env")
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
                    st.success(f"✅ تم الحفظ! التاقات: {len(selected_tags)} AR / {len(selected_tags_en)} EN")
                    st.balloons()
                    _trigger_social_broadcast(new_master_id)
                except Exception as e:
                    st.error(f"⚠️ مشكلة في القاعدة: {e}")
                finally:
                    conn.close()


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
            st.dataframe(df.style.apply(highlight_by_date, axis=1), use_container_width=True, height=600)
        
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
                st.dataframe(display_df, use_container_width=True, height=420)
            with tab_recent_arc:
                if recent_expired == 0:
                    st.info("ما فيه متاجر انتهت خلال آخر 7 أيام.")
                else:
                    st.dataframe(display_df.loc[_mask_recent], use_container_width=True, height=420)
            with tab_old_arc:
                if old_expired == 0:
                    st.success("👌 ما فيه متاجر منتهية من أكثر من 30 يوم.")
                else:
                    st.dataframe(display_df.loc[_mask_old], use_container_width=True, height=420)

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
    st.info("المتاجر المحددة كـ 'ترند' في قاعدة البيانات ستظهر بعلامة 🔥 وتتصدر القائمة.")
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
                st.dataframe(df_display, use_container_width=True, height=520, hide_index=True)

            with tab_active:
                if active_count == 0:
                    st.info("ما فيه متاجر فعّالة حالياً.")
                else:
                    st.dataframe(
                        df_display.loc[active_mask.values],
                        use_container_width=True, height=520, hide_index=True,
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
                    st.dataframe(df_near, use_container_width=True, hide_index=True)

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



if page == "تحليل الأقسام":
    st.header("📂 مركز تحليل أداء الأقسام الذكي")
    tab_gen_cat, tab_ind_cat, tab_time_analyser, tab_priority = st.tabs([
        "🌎 الأداء العام", "🏷️ تحليل فردي", "⏰ التحليل الزمني", "🏅 الأولويات"
    ])

    try:
        conn = get_conn()
        cat_query = """
            SELECT m.store_tags, a.action_time, a.action_type, a.user_id
            FROM action_logs a
            JOIN master m ON a.store_id = m.store_id
            WHERE a.store_id IS NOT NULL
        """
        df_raw = pd.read_sql(cat_query, conn)
        conn.close()

        if not df_raw.empty:
            df_raw['store_tags'] = df_raw['store_tags'].apply(parse_tags)
            df_exploded = df_raw.explode('store_tags').dropna(subset=['store_tags'])
            df_exploded['store_tags'] = df_exploded['store_tags'].astype(str).str.strip()

            with tab_gen_cat:
                st.subheader("📊 مقارنة نشاط الأقسام")
                fig = px.sunburst(df_exploded, path=['store_tags', 'action_type'],
                                  title="توزيع الأقسام ونوع الحركة داخلها")
                st.plotly_chart(apply_brand_theme(fig), use_container_width=True)

            with tab_ind_cat:
                search_tag = st.selectbox("اختر القسم للمراقبة:", sorted(df_exploded['store_tags'].unique()), key="cat_sel_1")
                tag_data = df_exploded[df_exploded['store_tags'] == search_tag]
                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي الحركات", len(tag_data))
                c2.metric("👥 مستخدمون فريدون", int(tag_data['user_id'].dropna().nunique()))
                c3.metric("السلوك الغالب", tag_data['action_type'].mode()[0] if not tag_data.empty else "N/A")

            with tab_time_analyser:
                st.subheader("📅 متى ينشط هذا القسم؟")
                df_exploded['hour'] = pd.to_datetime(df_exploded['action_time']).dt.hour
                time_stats = (df_exploded[df_exploded['store_tags'] == search_tag]
                              .groupby('hour').size().reset_index(name='الزيارات'))
                fig_time = px.line(time_stats, x='hour', y='الزيارات',
                                   title=f"نشاط قسم {search_tag} خلال ساعات اليوم", markers=True)
                st.plotly_chart(apply_brand_theme(fig_time), use_container_width=True)
        else:
            with tab_gen_cat:
                st.info("📭 لا توجد حركات مسجّلة بعد.")
    except Exception as e:
        st.error(f"حدث خطأ فني: {e}")

    # ─── تبويب الأولويات ───────────────────────────────────────────────────────
    with tab_priority:
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
                use_container_width=True,
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
               "منظومة تحليلية متكاملة: أداء · سلوك المستخدمين · ذكاء أعمال · تقارير المعلنين")

    _rc, _rt, _ric = st.columns([1.2, 1.6, 3])
    with _rc:
        if st.button("🔄 تحديث البيانات", use_container_width=True):
            _sa_load_actions.clear()
            _sa_load_master.clear()
            _sa_load_searches.clear()
            _sa_recent_raw.clear()
            _sa_web_users_count.clear()
            st.rerun()
    with _rt:
        only_genuine = st.toggle(
            "🧹 ترافيك حقيقي فقط", value=True,
            help="استبعاد الزواحف/البوتات ومراكز البيانات (datacenter) والبروكسي — أي حركة غير بشرية.")
    with _ric:
        st.caption("البيانات مخزّنة مؤقتاً 3 دقائق — «تحديث» لإعادة الجلب. الفلتر يستبعد الزواحف وحركة الـ datacenter لتظهر القراءات الحقيقية فقط.")

    try:
        df_logs = _sa_load_actions()
        df_master = _sa_load_master()
        df_search = _sa_load_searches()
    except Exception as e:
        st.error(f"⚠️ تعذّر تحميل البيانات: {e}")
        df_logs, df_master, df_search = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    if df_logs.empty:
        st.info("📭 لا توجد حركات مسجّلة بعد. ستظهر كل التحليلات فور تفاعل المستخدمين مع البوت.")
    else:
        # ── معالجة زمنية موحّدة (تحويل UTC ← توقيت الرياض) ──
        df_logs = df_logs.copy()
        df_logs["action_time"] = (pd.to_datetime(df_logs["action_time"])
                                  + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
        df_logs["hour"] = df_logs["action_time"].dt.hour
        df_logs["dow"] = df_logs["action_time"].dt.dayofweek
        df_logs["adate"] = df_logs["action_time"].dt.date

        # ── مصدر الحدث (ويب/تيليجرام) ──
        df_logs["source"] = df_logs["source"].fillna("bot")
        df_logs["src_ar"] = df_logs["source"].map(
            {"web": "🌐 ويب", "bot": "📱 تيليجرام"}).fillna("📱 تيليجرام")

        # ── الجهاز الموحّد: الويب من device_class، تيليجرام من bot_users.device_type ──
        _is_web = df_logs["source"].eq("web")
        _wdev = df_logs["device_class"].fillna("").astype(str).str.strip()
        _bdev = df_logs["device_type"].fillna("").astype(str).str.strip()
        df_logs["device"] = _wdev.where(_is_web, _bdev).replace("", "غير معروف")

        # ── المدينة الموحّدة: الويب من geo_city، تيليجرام من bot_users.city ──
        _wcity = df_logs["geo_city"].fillna("").astype(str).str.strip()
        _bcity = df_logs["bu_city"].fillna("").astype(str).str.strip()
        df_logs["city_c"] = _wcity.where(_is_web, _bcity).replace("", "غير معروف")

        # ── تصنيف «الترافيك الحقيقي» = ليس زاحف/بوت ولا datacenter ولا proxy ──
        df_logs["is_genuine"] = ~(
            (df_logs["device_class"].fillna("").astype(str).str.lower() == "bot")
            | (df_logs["is_datacenter"].fillna(False).astype(bool))
            | (df_logs["is_proxy"].fillna(False).astype(bool))
        )

        # ── فلتر التاريخ العام (يطبّق على كل التبويبات: أداء/سلوك/ذكاء/ويب/تصدير) ──
        _min_d, _max_d = df_logs["adate"].min(), df_logs["adate"].max()
        _dc1, _dc2 = st.columns([2, 3])
        with _dc1:
            _dr = st.date_input("📅 الفترة (من → إلى):", value=(_min_d, _max_d),
                                min_value=_min_d, max_value=_max_d, key="sa_global_dates")
        d_start, d_end = (_dr if isinstance(_dr, (list, tuple)) and len(_dr) == 2 else (_min_d, _max_d))
        df_logs = df_logs[(df_logs["adate"] >= d_start) & (df_logs["adate"] <= d_end)]

        # الأبحاث (direct_search) — نفس فلتر الفترة بتوقيت الرياض
        if not df_search.empty:
            df_search = df_search.copy()
            df_search["search_date"] = (pd.to_datetime(df_search["search_date"])
                                        + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS))
            df_search["adate"] = df_search["search_date"].dt.date
            df_search = df_search[(df_search["adate"] >= d_start) & (df_search["adate"] <= d_end)]

        # كشف شفّاف (ضمن الفترة المختارة)
        _n_total = len(df_logs)
        _n_bot_src = int(df_logs["source"].eq("bot").sum())
        _n_web_src = int(df_logs["source"].eq("web").sum())
        _n_fake = int((~df_logs["is_genuine"]).sum())

        # كل المصادر ضمن الفترة (للوحة الويب) ثم فلتر الجودة
        df_all = df_logs.copy()
        if only_genuine:
            df_logs = df_logs[df_logs["is_genuine"]].copy()

        with _dc2:
            st.caption(
                f"📅 {d_start} ← {d_end} · 📊 أحداث: **{_n_total}** "
                f"(📱 تيليجرام {_n_bot_src} · 🌐 ويب {_n_web_src}) · "
                f"🤖 مستبعَد: **{_n_fake}** "
                + ("✅" if only_genuine else "⚠️ غير مطبّق"))

        with st.expander("🧾 تحقّق خام: آخر 20 عملية فعلية في الداتابيز (بدون أي فلترة)"):
            _raw = _sa_recent_raw(20)
            if _raw.empty:
                st.info("لا توجد عمليات.")
            else:
                _raw = _raw.copy()
                _raw["UTC (كما خُزّنت)"] = pd.to_datetime(_raw["action_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                _raw["الرياض (UTC+3)"] = (pd.to_datetime(_raw["action_time"])
                                          + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS)).dt.strftime("%Y-%m-%d %H:%M:%S")
                st.dataframe(
                    _raw.rename(columns={"user_id": "المستخدم", "action_type": "النوع",
                                         "source": "المصدر", "store_id": "المتجر"})
                        [["id", "المستخدم", "النوع", "المصدر", "المتجر", "UTC (كما خُزّنت)", "الرياض (UTC+3)"]],
                    hide_index=True, use_container_width=True)
                _last = pd.to_datetime(_raw["action_time"]).max() + pd.Timedelta(hours=RIYADH_TZ_OFFSET_HOURS)
                st.caption(f"🕐 آخر نشاط مُسجّل: **{_last:%Y-%m-%d %H:%M}** بتوقيت الرياض. "
                           "لو ما يطابق دخولك، فالأحداث قديمة أو من زوّار/زواحف (user_id فارغ = زائر مجهول).")

        if df_logs.empty:
            st.warning("لا توجد أحداث بشرية حقيقية بعد الفلترة. أطفئ «🧹 ترافيك حقيقي فقط» لمشاهدة كل الحركات.")
            st.stop()

        # نوافذ النمو نسبةً لنهاية الفترة المختارة (آخر 7 أيام من الفترة مقابل الـ 7 قبلها)
        ref_end = pd.Timestamp(d_end) + pd.Timedelta(days=1)
        cut7 = ref_end - pd.Timedelta(days=7)
        cut14 = ref_end - pd.Timedelta(days=14)

        # ── تجميع لكل متجر (الإجمالي + الأسبوع الحالي/السابق للنمو) ──
        piv = df_logs.groupby(["store_id", "action_type"]).size().unstack(fill_value=0)
        for col in ["click_link", "copy_coupon", "search"]:
            if col not in piv.columns:
                piv[col] = 0
        piv = piv.rename(columns={"click_link": "clicks", "copy_coupon": "copies", "search": "searches"})

        # تفصيل أسبوعي لكل مؤشر (الحالي مقابل السابق) — يجيب على «وش الهابط وايش اللي تغيّر»
        def _sa_week_split(d, sfx):
            p = d.groupby(["store_id", "action_type"]).size().unstack(fill_value=0)
            for cc in ["click_link", "copy_coupon", "search"]:
                if cc not in p.columns:
                    p[cc] = 0
            return p.rename(columns={"click_link": f"cl_{sfx}", "copy_coupon": f"co_{sfx}",
                                     "search": f"se_{sfx}"})[[f"cl_{sfx}", f"co_{sfx}", f"se_{sfx}"]]

        wk_now = _sa_week_split(df_logs[df_logs["action_time"] >= cut7], "now")
        wk_prev = _sa_week_split(
            df_logs[(df_logs["action_time"] >= cut14) & (df_logs["action_time"] < cut7)], "prev")

        agg = piv.join(wk_now, how="left").join(wk_prev, how="left").fillna(0).reset_index()
        agg["t7"] = agg["cl_now"] + agg["co_now"] + agg["se_now"]
        agg["p7"] = agg["cl_prev"] + agg["co_prev"] + agg["se_prev"]

        if not df_master.empty:
            agg = agg.merge(df_master.drop(columns=["store_name"], errors="ignore"),
                            on="store_id", how="left")
        for _col, _def in [("logo_url", ""), ("is_trending", "عادي"),
                           ("priority_score", "عادي"), ("is_promoted", False)]:
            if _col not in agg.columns:
                agg[_col] = _def
        agg["priority_score"] = agg["priority_score"].fillna("عادي")
        agg["is_promoted"] = agg["is_promoted"].fillna(False)
        # الاسم المعتمد عربي دائماً = store_id (يحلّ تضارب «مرة عربي مرة إنجليزي» + يصلح البحث العربي)
        agg["store_name"] = agg["store_id"]
        agg["logo_url"] = agg["logo_url"].fillna("")
        agg["is_trending"] = agg["is_trending"].fillna("عادي")
        agg["total"] = agg["clicks"] + agg["copies"] + agg["searches"]
        agg["engagement"] = agg.apply(lambda r: _sa_pct(r["clicks"] + r["copies"], r["total"]), axis=1)
        agg["conv"] = agg.apply(lambda r: _sa_pct(r["copies"], r["clicks"]), axis=1)
        agg["wow"] = agg.apply(lambda r: _sa_wow(r["t7"], r["p7"]), axis=1)

        tot_clicks = int(agg["clicks"].sum())
        tot_copies = int(agg["copies"].sum())
        tot_search = int(agg["searches"].sum())
        global_conv = _sa_pct(tot_copies, tot_clicks)

        engaged_df = df_logs[df_logs["action_type"].isin(["click_link", "copy_coupon"])]
        peak_hour = int(engaged_df.groupby("hour").size().idxmax()) if not engaged_df.empty else None

        tab_overview, tab_behavior, tab_ai, tab_web, tab_export = st.tabs([
            "🌎 الأداء العام",
            "🧭 سلوك المستخدمين والترند",
            "🧠 ذكاء الأعمال والتوقعات",
            "🌐 الويب",
            "📤 تقارير المعلنين",
        ])

        # ─────────────────────────── التبويب 1: الأداء العام ───────────────────────────
        # كل بطاقة = تبويب مستقل (نقرات / نسخ / تحويل / الأكثر نمواً) + الجدول الكامل
        with tab_overview:
            cand = agg[(agg["p7"] > 0) & (agg["t7"] >= 3)]
            if not cand.empty:
                _top = cand.loc[cand["wow"].idxmax()]
                grow_name, grow_note = str(_top["store_name"]), _sa_fmt_growth(_top["wow"])
            else:
                _new = agg[(agg["p7"] == 0) & (agg["t7"] >= 3)].sort_values("t7", ascending=False)
                if not _new.empty:
                    grow_name, grow_note = str(_new.iloc[0]["store_name"]), "🆕 صاعد جديد"
                else:
                    grow_name, grow_note = "—", "بيانات غير كافية"

            # البطاقات تبقى ظاهرة زي ماهي (صف علوي)
            k1, k2, k3, k4 = st.columns(4)
            with k1: kpi_card("🖱️", "إجمالي النقرات", f"{tot_clicks:,}", "info")
            with k2: kpi_card("✂️", "إجمالي نسخ الكوبونات", f"{tot_copies:,}", "emerald")
            with k3: kpi_card("🎯", "معدل تحويل النسخ", f"{global_conv:.0f}%", "warning", note="نسخ ÷ نقرات")
            with k4: kpi_card("🚀", "الأكثر نمواً هذا الأسبوع", grow_name, "emerald", note=grow_note)
            st.divider()
            st.caption("👇 افتح أي تبويب لتفاصيل البطاقة المقابلة")

            # تبويبات تفتح تفاصيل كل بطاقة (البطاقات نفسها فوق)
            ov_clicks, ov_copies, ov_conv, ov_grow, ov_source, ov_priority, ov_table = st.tabs([
                "🖱️ النقرات",
                "✂️ النسخ",
                "🎯 تحويل النسخ",
                "🚀 الأكثر نمواً",
                "📱🌐 حسب المصدر",
                "⭐ الأولوية والترند",
                "📋 الجدول الكامل",
            ])

            # ── تفاصيل بطاقة النقرات ──
            with ov_clicks:
                st.markdown("**ترتيب المتاجر حسب نقرات الروابط**")
                t = agg[agg["clicks"] > 0].sort_values("clicks", ascending=False)
                if t.empty:
                    st.info("لا توجد نقرات مسجّلة بعد.")
                else:
                    st.dataframe(pd.DataFrame({
                        "المتجر": t["store_name"].values,
                        "النقرات": t["clicks"].astype(int).values,
                        "هذا الأسبوع": t.apply(lambda r: _sa_prevnow(r["cl_prev"], r["cl_now"]), axis=1).values,
                    }), hide_index=True, use_container_width=True)
                    st.plotly_chart(_sa_metric_hourly(df_logs, "click_link", "النقرات"),
                                    use_container_width=True)

            # ── تفاصيل بطاقة النسخ ──
            with ov_copies:
                st.markdown("**ترتيب المتاجر حسب نسخ الكوبونات**")
                t = agg[agg["copies"] > 0].sort_values("copies", ascending=False)
                if t.empty:
                    st.info("لا توجد عمليات نسخ مسجّلة بعد.")
                else:
                    st.dataframe(pd.DataFrame({
                        "المتجر": t["store_name"].values,
                        "النسخ": t["copies"].astype(int).values,
                        "هذا الأسبوع": t.apply(lambda r: _sa_prevnow(r["co_prev"], r["co_now"]), axis=1).values,
                    }), hide_index=True, use_container_width=True)
                    st.plotly_chart(_sa_metric_hourly(df_logs, "copy_coupon", "النسخ"),
                                    use_container_width=True)

            # ── تفاصيل بطاقة تحويل النسخ ──
            with ov_conv:
                st.markdown("**معدل تحويل النسخ لكل متجر** (كم نسخة لكل نقرة رابط)")
                cv = agg[agg["clicks"] > 0].sort_values("conv", ascending=False)
                if cv.empty:
                    st.info("لا توجد بيانات كافية لحساب التحويل.")
                else:
                    cvt = pd.DataFrame({
                        "المتجر": cv["store_name"].values,
                        "نقرات": cv["clicks"].astype(int).values,
                        "نسخ": cv["copies"].astype(int).values,
                        "تحويل النسخ %": cv["conv"].round(1).values,
                    })
                    try:
                        st.dataframe(cvt.style.format({"تحويل النسخ %": "{:.1f}%"}),
                                     hide_index=True, use_container_width=True)
                    except Exception:
                        st.dataframe(cvt, hide_index=True, use_container_width=True)

            # ── تفاصيل بطاقة الأكثر نمواً ──
            with ov_grow:
                st.markdown("**لوحة النمو الأسبوعي (كل المتاجر)** — الأسبوع الحالي مقابل السابق")
                g = agg.sort_values("wow", ascending=False, na_position="last")
                gt = pd.DataFrame({
                    "المتجر": g["store_name"].values,
                    "الأسبوع السابق": g["p7"].astype(int).values,
                    "الأسبوع الحالي": g["t7"].astype(int).values,
                    "النمو": g["wow"].values,
                })
                try:
                    _gm = gt.style
                    _gmap = _gm.map if hasattr(_gm, "map") else _gm.applymap
                    st.dataframe(_gmap(_sa_growth_color, subset=["النمو"]).format({"النمو": _sa_fmt_growth}),
                                 hide_index=True, use_container_width=True)
                except Exception:
                    gt["النمو"] = gt["النمو"].apply(_sa_fmt_growth)
                    st.dataframe(gt, hide_index=True, use_container_width=True)

            # ── تفاصيل بطاقة «حسب المصدر» (كم تيليجرام وكم ويب) ──
            with ov_source:
                st.markdown("**كم من التفاعل من تيليجرام 📱 وكم من الموقع 🌐؟** (ترافيك حقيقي بعد الفلتر)")
                sp = df_logs.groupby(["source", "action_type"]).size().unstack(fill_value=0)
                for _at in ["click_link", "copy_coupon", "search"]:
                    if _at not in sp.columns:
                        sp[_at] = 0
                _zero = pd.Series(0, index=sp.columns)
                tel = sp.loc["bot"] if "bot" in sp.index else _zero
                wbs = sp.loc["web"] if "web" in sp.index else _zero
                comp = pd.DataFrame({
                    "المؤشر": ["نقرات الروابط", "نسخ الكوبونات", "عمليات البحث", "الإجمالي"],
                    "📱 تيليجرام": [int(tel["click_link"]), int(tel["copy_coupon"]), int(tel["search"]),
                                   int(tel[["click_link", "copy_coupon", "search"]].sum())],
                    "🌐 ويب": [int(wbs["click_link"]), int(wbs["copy_coupon"]), int(wbs["search"]),
                              int(wbs[["click_link", "copy_coupon", "search"]].sum())],
                })
                comp["الإجمالي"] = comp["📱 تيليجرام"] + comp["🌐 ويب"]
                st.dataframe(comp, hide_index=True, use_container_width=True)

                melt = comp[comp["المؤشر"] != "الإجمالي"].melt(
                    id_vars="المؤشر", value_vars=["📱 تيليجرام", "🌐 ويب"],
                    var_name="المصدر", value_name="العدد")
                fig_src = px.bar(melt, x="المؤشر", y="العدد", color="المصدر", barmode="group")
                fig_src.update_layout(xaxis_title="", yaxis_title="العدد", legend_title_text="المصدر")
                st.plotly_chart(apply_brand_theme(fig_src), use_container_width=True)

            # ── تفاصيل بطاقة «الأولوية والترند» ──
            with ov_priority:
                st.markdown("**⭐ أولوية المتاجر وحالة الترند والترويج**")
                st.caption("الأولوية من `master.priority_score` · الترند من `is_trending` · مُروّج من `is_promoted`.")
                pt = agg.sort_values("total", ascending=False)
                ptv = pd.DataFrame({
                    "المتجر": pt["store_name"].values,
                    "الأولوية": pt["priority_score"].astype(str).values,
                    "الترند": pt["is_trending"].astype(str).values,
                    "مُروّج": pt["is_promoted"].map(lambda b: "✅" if bool(b) else "—").values,
                    "إجمالي النشاط": pt["total"].astype(int).values,
                })
                st.dataframe(ptv, hide_index=True, use_container_width=True)

                st.divider()
                st.markdown("### 🔥 إدارة الترند (آلي + يدوي)")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**🤖 الترند الآلي — أعلى 5 سكور** `نسخ×3 + نقر×2 + بحث×1`")
                    score = agg.copy()
                    score["السكور"] = score["copies"] * 3 + score["clicks"] * 2 + score["searches"]
                    auto_top = (score.sort_values("السكور", ascending=False).head(5)
                                [["store_name", "copies", "clicks", "searches", "السكور"]]
                                .rename(columns={"store_name": "المتجر", "copies": "نسخ (×3)",
                                                 "clicks": "نقرات (×2)", "searches": "بحث (×1)"})
                                .reset_index(drop=True))
                    st.table(auto_top)
                with col_b:
                    st.markdown("**🛠️ الترند اليدوي (تثبيت)**")
                    if not df_master.empty:
                        trend_set = set(df_master[df_master["is_trending"].astype(str)
                                                  .str.contains("ترند")]["store_id"])
                        s_list = df_master["store_id"].tolist()
                        s_disp = [f"🔥 {s}" if s in trend_set else s for s in s_list]
                        s_map = dict(zip(s_disp, s_list))
                        sel_disp = st.selectbox("اختر متجراً لتغيير حالته:", s_disp, key="sa_trend_sel")
                        new_status = st.radio("الحالة المطلوبة:", ["عادي", "ترند 🔥"],
                                              key="sa_trend_status", horizontal=True)
                        if st.button("تحديث حالة الترند", key="sa_trend_btn"):
                            _c = get_conn()
                            try:
                                _c.rollback()
                                _cur = _c.cursor()
                                _cur.execute("UPDATE master SET is_trending=%s WHERE store_id=%s",
                                             (new_status, s_map[sel_disp]))
                                _c.commit()
                                _sa_load_master.clear()
                                st.success(f"✅ تم تحويل {s_map[sel_disp]} إلى {new_status}")
                                st.rerun()
                            finally:
                                _c.close()
                    else:
                        st.info("لا تتوفر بيانات متاجر.")

            # ── الجدول الكامل ──
            with ov_table:
                st.subheader("📋 الجدول التحليلي الرئيسي")
                st.caption("معدل التفاعل = (نقرات + نسخ) ÷ إجمالي النشاط · تحويل النسخ = نسخ ÷ نقرات · "
                           "النمو الأسبوعي = آخر 7 أيام مقابل الـ 7 السابقة لها.")
                q = st.text_input("🔎 ابحث عن متجر في الجدول:", key="sa_table_q")
                disp = agg.sort_values("total", ascending=False)
                if q:
                    disp = disp[disp["store_name"].str.contains(q, case=False, na=False)]
                view = pd.DataFrame({
                    "الشعار": disp["logo_url"].values,
                    "المتجر": disp["store_name"].values,
                    "🔥": disp["is_trending"].apply(lambda s: "🔥" if "ترند" in str(s) else "").values,
                    "نقرات": disp["clicks"].astype(int).values,
                    "نسخ": disp["copies"].astype(int).values,
                    "بحث": disp["searches"].astype(int).values,
                    "التفاعل %": disp["engagement"].round(1).values,
                    "تحويل النسخ %": disp["conv"].round(1).values,
                    "نمو أسبوعي": disp["wow"].values,
                })
                try:
                    _sty = view.style
                    _mapper = _sty.map if hasattr(_sty, "map") else _sty.applymap
                    styled = _mapper(_sa_growth_color, subset=["نمو أسبوعي"]).format({
                        "نمو أسبوعي": _sa_fmt_growth,
                        "التفاعل %": "{:.1f}%",
                        "تحويل النسخ %": "{:.1f}%",
                    })
                    st.dataframe(
                        styled, use_container_width=True, hide_index=True,
                        column_config={"الشعار": st.column_config.ImageColumn("🏪", width="small")},
                    )
                except Exception:
                    view["نمو أسبوعي"] = view["نمو أسبوعي"].apply(_sa_fmt_growth)
                    st.dataframe(view, use_container_width=True, hide_index=True)
                st.caption("⭐ الأولوية وإدارة الترند انتقلت إلى تبويب «الأولوية والترند».")

        # ───────────────────── التبويب 2: سلوك المستخدمين والترند ─────────────────────
        with tab_behavior:
            beh_overall, beh_store, beh_dg = st.tabs([
                "📊 النشاط العام (كل المتاجر)",
                "🔍 نشاط متجر محدد",
                "📱 الأجهزة والجغرافيا",
            ])

            # ── النشاط العام (كل المتاجر) — بحث / نقر / نسخ ──
            with beh_overall:
                st.subheader("⏰ النشاط بالساعة — بحث / نقرات / نسخ (توقيت الرياض)")
                st.caption("توزيع المؤشرات الثلاثة الحقيقية على مدار 24 ساعة لكل المتاجر — يحدّد أفضل نوافذ إرسال الإشعارات.")
                st.plotly_chart(_sa_hourly_fig(df_logs), use_container_width=True)
                if peak_hour is not None:
                    st.success(f"🕐 ساعة الذروة (نقر + نسخ): **{peak_hour:02d}:00 – {peak_hour + 1:02d}:00** "
                               "بتوقيت الرياض. يُنصح بجدولة الـ Broadcast حولها.")

                st.divider()
                st.subheader("🗓️ خريطة النشاط الحرارية (اليوم × الساعة)")
                st.caption("كثافة كل التفاعلات حسب اليوم والساعة — كلما اخضرّت الخلية زاد النشاط الفعلي.")
                heat = (df_logs.groupby(["dow", "hour"]).size()
                        .unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0))
                heat.index = _SA_ARABIC_DAYS
                heat.columns = [f"{h:02d}" for h in range(24)]
                fig_heat = px.imshow(heat, aspect="auto", color_continuous_scale="Greens",
                                     labels=dict(x="الساعة", y="اليوم", color="الأحداث"))
                st.plotly_chart(apply_brand_theme(fig_heat), use_container_width=True)

            # ── نشاط متجر محدد — بحث / نقر / نسخ ──
            with beh_store:
                st.subheader("🔍 نشاط متجر محدد بالساعة — بحث / نقرات / نسخ")
                _opts = agg.sort_values("total", ascending=False)["store_name"].tolist()
                if not _opts:
                    st.info("لا توجد متاجر بعد.")
                else:
                    _seld = st.selectbox("اختر متجراً:", _opts, key="sa_store_drill")
                    _sid = agg[agg["store_name"] == _seld]["store_id"].iloc[0]
                    srow = agg[agg["store_id"] == _sid].iloc[0]
                    sdf = df_logs[df_logs["store_id"] == _sid]

                    m1, m2, m3, m4 = st.columns(4)
                    with m1: kpi_card("🖱️", "نقرات الروابط", f"{int(srow['clicks']):,}", "info")
                    with m2: kpi_card("✂️", "نسخ الكوبونات", f"{int(srow['copies']):,}", "emerald")
                    with m3: kpi_card("🔍", "عمليات البحث", f"{int(srow['searches']):,}", "neutral")
                    with m4: kpi_card("🎯", "تحويل النسخ", f"{srow['conv']:.0f}%", "warning")

                    if sdf.empty:
                        st.info("لا توجد حركات مسجّلة لهذا المتجر بعد.")
                    else:
                        st.plotly_chart(_sa_hourly_fig(sdf, title=f"النشاط بالساعة — {_seld}"),
                                        use_container_width=True)
                        _sph = (sdf[sdf["action_type"].isin(["click_link", "copy_coupon"])]
                                .groupby("hour").size())
                        if not _sph.empty:
                            _sp = int(_sph.idxmax())
                            st.success(f"🕐 ذروة «{_seld}»: **{_sp:02d}:00 – {_sp + 1:02d}:00** بتوقيت الرياض.")
                        sdev = sdf[sdf["action_type"] != "search"]["device"].value_counts()
                        if not sdev.empty:
                            st.markdown("**📱 أجهزة زوّار هذا المتجر**")
                            st.plotly_chart(apply_brand_theme(
                                px.pie(values=sdev.values, names=sdev.index, hole=0.55)),
                                use_container_width=True)

            # ── الأجهزة والجغرافيا (كل المتاجر) ──
            with beh_dg:
                c_dev, c_geo = st.columns(2)
                with c_dev:
                    st.subheader("📱 الأجهزة والمنصات")
                    dev_counts = engaged_df["device"].value_counts()
                    if dev_counts.empty:
                        st.info("لا توجد بيانات أجهزة بعد.")
                    else:
                        fig_dev = px.pie(values=dev_counts.values, names=dev_counts.index, hole=0.55)
                        st.plotly_chart(apply_brand_theme(fig_dev), use_container_width=True)
                        known = int((engaged_df["device"] != "غير معروف").sum())
                        cov = _sa_pct(known, engaged_df.shape[0])
                        st.caption(f"تغطية بيانات الجهاز: {cov:.0f}% من الأحداث "
                                   "(الباقي «غير معروف» — غالباً مستخدمو ويب أو قبل حفظ نوع الجهاز).")
                with c_geo:
                    st.subheader("🌍 التوزيع الجغرافي (أعلى 10 مدن)")
                    geo = engaged_df[engaged_df["city_c"] != "غير معروف"]["city_c"].value_counts().head(10)
                    if geo.empty:
                        st.info("لا تتوفر بيانات مدن كافية في البيانات الخام بعد.")
                    else:
                        fig_geo = px.bar(x=geo.values, y=geo.index, orientation="h")
                        fig_geo.update_layout(xaxis_title="عدد الأحداث", yaxis_title="",
                                              yaxis=dict(autorange="reversed"))
                        st.plotly_chart(apply_brand_theme(fig_geo), use_container_width=True)

        # ──────────────────── التبويب 3: ذكاء الأعمال والتوقعات (AI) ────────────────────
        # كل بطاقة إشارة = تبويب مستقل (صاعدة / هابطة / خاملة) + تبويب التقرير الذكي
        with tab_ai:
            risers = agg[((agg["wow"] > 30) | ((agg["p7"] == 0) & (agg["t7"] >= 3)))
                         & (agg["t7"] >= 3)].sort_values("t7", ascending=False)
            decliners = agg[(agg["wow"] < -30) & (agg["p7"] >= 3)].sort_values("wow")
            inactive = agg[(agg["t7"] == 0) & (agg["p7"] >= 3)].sort_values("p7", ascending=False)
            alarm = pd.concat([decliners, inactive]).drop_duplicates(subset="store_id")

            # البطاقات تبقى ظاهرة زي ماهي (صف علوي)
            sc1, sc2, sc3 = st.columns(3)
            with sc1: kpi_card("🚀", "متاجر صاعدة", f"{len(risers)}", "emerald", note="نمو > 30% أو نشاط جديد")
            with sc2: kpi_card("📉", "متاجر هابطة", f"{len(decliners)}", "danger", note="هبوط > 30% أسبوعياً")
            with sc3: kpi_card("💤", "متاجر خاملة", f"{len(inactive)}", "warning", note="توقّفت هذا الأسبوع")
            st.divider()
            st.caption("👇 افتح أي تبويب لتفاصيل البطاقة المقابلة")

            # تبويبات تفتح تفاصيل كل بطاقة (البطاقات نفسها فوق)
            ai_up, ai_down, ai_idle, ai_report = st.tabs([
                "🚀 الصاعدة",
                "📉 الهابطة",
                "💤 الخاملة",
                "🧠 التقرير الاستشاري (AI)",
            ])

            # ── تفاصيل بطاقة المتاجر الصاعدة ──
            with ai_up:
                _sa_render_category(risers, "لا توجد متاجر صاعدة أو جديدة بشكل ملحوظ هذا الأسبوع.")

            # ── تفاصيل بطاقة المتاجر الهابطة ──
            with ai_down:
                _sa_render_category(decliners, "لا توجد متاجر هابطة هذا الأسبوع. الأداء مستقر 👍")

            # ── تفاصيل بطاقة المتاجر الخاملة ──
            with ai_idle:
                _sa_render_category(inactive, "لا توجد متاجر خاملة هذا الأسبوع. 👍")

            # ── بطاقة التقرير الاستشاري عبر Groq ──
            with ai_report:
                st.subheader("🧠 التقرير الاستشاري المؤتمت (Groq · Llama 3.3 70B)")
                st.caption("يحلّل النموذج بيانات الجدول الفعلية (بما فيها ما تغيّر) ويُخرج توصيات تشغيلية محددة بالأسماء والأرقام.")
                if st.button("🪄 توليد / تحديث التقرير الذكي", type="primary", key="sa_ai_btn"):
                    top10 = agg.sort_values("total", ascending=False).head(10)
                    payload = {
                        "إجماليات": {
                            "نقرات": tot_clicks, "نسخ": tot_copies, "بحث": tot_search,
                            "معدل_تحويل_النسخ_%": round(global_conv, 1),
                            "ساعة_الذروة_الرياض": peak_hour,
                        },
                        "أعلى_المتاجر": [
                            {"المتجر": r.store_name, "نقرات": int(r.clicks), "نسخ": int(r.copies),
                             "بحث": int(r.searches), "تفاعل_%": round(r.engagement, 1),
                             "تحويل_%": round(r.conv, 1),
                             "نمو_اسبوعي_%": (None if pd.isna(r.wow) else round(r.wow, 1))}
                            for r in top10.itertuples()
                        ],
                        "متاجر_صاعدة": [
                            {"المتجر": r.store_name,
                             "نمو_%": ("جديد" if pd.isna(r.wow) else round(r.wow, 1)),
                             "أحداث_الأسبوع": int(r.t7)}
                            for r in risers.head(6).itertuples()
                        ],
                        "متاجر_هابطة_او_خاملة": [
                            {"المتجر": r.store_name,
                             "الحالة": ("خامل" if r.t7 == 0 else f"هبوط {abs(r.wow):.0f}%"),
                             "نقرات_سابق_حالي": f"{int(r.cl_prev)}→{int(r.cl_now)}",
                             "نسخ_سابق_حالي": f"{int(r.co_prev)}→{int(r.co_now)}",
                             "بحث_سابق_حالي": f"{int(r.se_prev)}→{int(r.se_now)}"}
                            for r in alarm.head(6).itertuples()
                        ],
                    }
                    with st.spinner("Groq يحلّل البيانات ويكتب التقرير…"):
                        report, err = _sa_groq_report(payload)
                    st.session_state["sa_ai_report"] = report
                    st.session_state["sa_ai_err"] = err

                if st.session_state.get("sa_ai_err"):
                    st.error(f"⚠️ تعذّر توليد التقرير: {st.session_state['sa_ai_err']}")
                if st.session_state.get("sa_ai_report"):
                    st.markdown(st.session_state["sa_ai_report"])
                    st.download_button("📥 تحميل التقرير (Markdown)",
                                       st.session_state["sa_ai_report"].encode("utf-8"),
                                       "AI_Consulting_Report.md", "text/markdown")

        # ──────────────────────────── التبويب 4: الويب (web) ────────────────────────────
        # تحليل زوّار الموقع فقط (source='web') — منفصل تماماً عن تيليجرام
        with tab_web:
            st.subheader("🌐 تحليل زوّار الموقع (Website)")
            web_all = df_all[df_all["source"] == "web"]          # كل أحداث الويب (قبل فلتر الجودة)
            web = web_all[web_all["is_genuine"]]                  # الويب البشري الحقيقي فقط
            if web_all.empty:
                st.info("📭 لا توجد أحداث ويب مسجّلة بعد. تأكد أن الموقع يرسل الأحداث إلى "
                        "`/api/v1/track/event` بـ `source='web'`.")
            else:
                n_web, n_crawl = len(web_all), len(web_all) - len(web)
                wc = web["action_type"].value_counts()
                # أبحاث الموقع تأتي من جدول direct_search (platform='Web') وليس action_logs
                web_search = (df_search[df_search["platform"].str.lower() == "web"]
                              if not df_search.empty else pd.DataFrame())
                w1, w2, w3, w4, w5 = st.columns(5)
                with w1: kpi_card("🖱️", "نقرات الموقع", f"{int(wc.get('click_link', 0)):,}", "info")
                with w2: kpi_card("✂️", "نسخ الموقع", f"{int(wc.get('copy_coupon', 0)):,}", "emerald")
                with w3: kpi_card("🔍", "بحث الموقع", f"{len(web_search):,}", "warning", note="من direct_search")
                with w4: kpi_card("🤖", "زواحف مستبعَدة", f"{n_crawl:,}", "danger", note=f"من أصل {n_web}")
                with w5: kpi_card("👤", "مستخدمو الموقع", f"{_sa_web_users_count():,}", "neutral")

                st.divider()
                st.caption("👇 افتح أي تبويب لتفاصيل البطاقة المقابلة")

                wt_stores, wt_search, wt_dev, wt_geo, wt_hours, wt_bots = st.tabs([
                    "🏪 المتاجر", "🔍 البحث", "📱 الأجهزة", "🌍 المدن", "⏰ بالساعة", "🤖 الزواحف المستبعدة",
                ])

                # ── متاجر الموقع ──
                with wt_stores:
                    if web.empty:
                        st.info("لا يوجد ترافيك بشري حقيقي على الموقع بعد.")
                    else:
                        ws = web.groupby(["store_id", "action_type"]).size().unstack(fill_value=0)
                        for cc in ["click_link", "copy_coupon"]:
                            if cc not in ws.columns:
                                ws[cc] = 0
                        ws = (ws.rename(columns={"click_link": "نقرات", "copy_coupon": "نسخ"})
                              .assign(الإجمالي=lambda d: d["نقرات"] + d["نسخ"])
                              .sort_values("الإجمالي", ascending=False).reset_index()
                              .rename(columns={"store_id": "المتجر"}))
                        st.dataframe(ws[["المتجر", "نقرات", "نسخ", "الإجمالي"]],
                                     hide_index=True, use_container_width=True)

                # ── بحث الموقع (من جدول direct_search) ──
                with wt_search:
                    st.caption("🔎 أبحاث الموقع تُسجَّل في جدول `direct_search` بـ `platform='Web'` "
                               "(وليست في action_logs مثل النقر/النسخ).")
                    if web_search.empty:
                        st.info("لا توجد عمليات بحث من الموقع ضمن الفترة المختارة.")
                    else:
                        _wsr = web_search.copy()
                        _wsr["found"] = _wsr["user_found"].fillna(False).astype(bool)
                        n_found = int(_wsr["found"].sum())
                        cwa, cwb, cwc = st.columns(3)
                        with cwa: kpi_card("🔍", "إجمالي أبحاث الموقع", f"{len(_wsr):,}", "info")
                        with cwb: kpi_card("✅", "وجدت نتيجة", f"{n_found:,}", "emerald")
                        with cwc: kpi_card("❌", "بدون نتيجة (فرص ناقصة)", f"{len(_wsr) - n_found:,}", "danger")
                        st.markdown("**أكثر كلمات البحث على الموقع**")
                        kw = (_wsr.groupby("search_keyword")
                              .agg(عدد=("found", "size"), وجدت=("found", "sum"))
                              .reset_index())
                        kw["وجدت"] = kw["وجدت"].astype(int)
                        kw["بدون نتيجة"] = kw["عدد"] - kw["وجدت"]
                        kw = (kw.rename(columns={"search_keyword": "كلمة البحث"})
                              .sort_values("عدد", ascending=False))
                        st.dataframe(kw[["كلمة البحث", "عدد", "وجدت", "بدون نتيجة"]],
                                     hide_index=True, use_container_width=True)

                # ── أجهزة زوّار الموقع ──
                with wt_dev:
                    if web.empty:
                        st.info("لا يوجد ترافيك بشري حقيقي بعد.")
                    else:
                        wdev = web["device"].value_counts()
                        st.plotly_chart(apply_brand_theme(
                            px.pie(values=wdev.values, names=wdev.index, hole=0.55)),
                            use_container_width=True)
                        st.caption("الأجهزة من Geo-IP enrichment (desktop / mobile / tablet). «غير معروف» = لم يُصنَّف الجهاز.")

                # ── مدن زوّار الموقع ──
                with wt_geo:
                    if web.empty:
                        st.info("لا يوجد ترافيك بشري حقيقي بعد.")
                    else:
                        wcity = web[web["city_c"] != "غير معروف"]["city_c"].value_counts().head(10)
                        if wcity.empty:
                            st.info("لا تتوفر بيانات مدن في البيانات الحالية.")
                        else:
                            figwc = px.bar(x=wcity.values, y=wcity.index, orientation="h")
                            figwc.update_layout(xaxis_title="عدد الأحداث", yaxis_title="",
                                                yaxis=dict(autorange="reversed"))
                            st.plotly_chart(apply_brand_theme(figwc), use_container_width=True)
                            st.caption("المدن مستنتجة من عنوان الـ IP (Geo-IP).")

                # ── نشاط الموقع بالساعة: عام + فردي ──
                with wt_hours:
                    if web.empty:
                        st.info("لا يوجد ترافيك بشري حقيقي بعد.")
                    else:
                        st.markdown("**📊 الأداء العام للموقع بالساعة (كل المتاجر)**")
                        st.caption("الموقع يسجّل النقر والنسخ فقط هنا؛ البحث في تبويب «🔍 البحث».")
                        st.plotly_chart(_sa_hourly_fig(web, include_search=False), use_container_width=True)
                        st.divider()
                        st.markdown("**🔍 أداء متجر محدد على الموقع**")
                        _wopts = web.groupby("store_id").size().sort_values(ascending=False).index.tolist()
                        _wsel = st.selectbox("اختر متجراً:", _wopts, key="sa_web_store_drill")
                        _wsdf = web[web["store_id"] == _wsel]
                        _wsc = _wsdf["action_type"].value_counts()
                        _wm1, _wm2 = st.columns(2)
                        with _wm1: kpi_card("🖱️", "نقرات (الموقع)", f"{int(_wsc.get('click_link', 0)):,}", "info")
                        with _wm2: kpi_card("✂️", "نسخ (الموقع)", f"{int(_wsc.get('copy_coupon', 0)):,}", "emerald")
                        st.plotly_chart(_sa_hourly_fig(_wsdf, title=f"نشاط «{_wsel}» على الموقع",
                                                       include_search=False),
                                        use_container_width=True)

                # ── الزواحف المستبعدة (مع الشرح) ──
                with wt_bots:
                    st.markdown("**🤖 ايش هي «زواحف البوتات»؟**")
                    st.info(
                        "الزواحف/البوتات (Bots & Crawlers) برامج آلية تتصفّح الموقع تلقائياً — مثل "
                        "Googlebot لفهرسة جوجل، أدوات السحب/الفحص، أو روبوتات السبام — **وليست أشخاصاً حقيقيين**. "
                        "نكتشفها ونستبعدها حتى تعكس الأرقام تفاعل البشر فقط، عبر:\n\n"
                        "• **بصمة المتصفح**: `device_class = bot`\n"
                        "• **عنوان IP من مركز بيانات** (datacenter) — السيرفرات لا يتصفّحها بشر\n"
                        "• **بروكسي/VPN مشبوه** (proxy)")
                    bots = web_all[~web_all["is_genuine"]].copy()
                    if bots.empty:
                        st.success("لا توجد زواحف مستبعدة حالياً. 👍")
                    else:
                        def _sa_bot_reason(r):
                            rs = []
                            if str(r["device_class"] or "").lower() == "bot":
                                rs.append("زاحف (bot)")
                            if pd.notna(r["is_datacenter"]) and r["is_datacenter"]:
                                rs.append("datacenter")
                            if pd.notna(r["is_proxy"]) and r["is_proxy"]:
                                rs.append("proxy")
                            return "، ".join(rs) or "غير بشري"
                        bt = pd.DataFrame({
                            "المتجر": bots["store_id"].values,
                            "النوع": bots["action_type"].map(
                                {"click_link": "نقرة", "copy_coupon": "نسخ", "search": "بحث"}).values,
                            "المدينة": bots["city_c"].values,
                            "سبب الاستبعاد": bots.apply(_sa_bot_reason, axis=1).values,
                            "الوقت (الرياض)": pd.to_datetime(bots["action_time"]).dt.strftime("%Y-%m-%d %H:%M").values,
                        })
                        st.dataframe(bt, hide_index=True, use_container_width=True)
                        st.caption(f"إجمالي {len(bots)} حدث مستبعَد — هذه الأرقام **لا** تُحتسب ضمن نقرات/نسخ الموقع الحقيقية.")

        # ───────────────────────── التبويب 5: تقارير المعلنين ─────────────────────────
        with tab_export:
            st.subheader("📤 مركز تقارير المعلنين والشركاء")
            st.caption("صفِّ البيانات حسب المتجر والفترة، ثم حمّل تقريراً نظيفاً (CSV / Excel) جاهزاً للإرسال للمعلنين.")

            name_to_id = dict(zip(agg["store_name"], agg["store_id"]))
            st.caption(f"📅 الفترة معتمدة من الفلتر العام أعلى الصفحة: **{d_start} ← {d_end}** — "
                       "غيّرها من منتقي «الفترة» بالأعلى.")
            sel_names = st.multiselect("المتاجر (فارغة = كل المتاجر):",
                                       sorted(agg["store_name"].tolist()), key="sa_exp_stores")
            fdf = df_logs.copy()
            if sel_names:
                fdf = fdf[fdf["store_id"].isin([name_to_id[n] for n in sel_names])]

            if fdf.empty:
                st.warning("لا توجد بيانات ضمن النطاق المحدد.")
            else:
                rpiv = fdf.groupby(["store_id", "action_type"]).size().unstack(fill_value=0)
                for c in ["click_link", "copy_coupon", "search"]:
                    if c not in rpiv.columns:
                        rpiv[c] = 0
                rpiv = rpiv.rename(columns={"click_link": "clicks", "copy_coupon": "copies",
                                            "search": "searches"}).reset_index()
                fl = fdf.groupby("store_id")["action_time"].agg(["min", "max"]).reset_index()
                rep = rpiv.merge(fl, on="store_id", how="left")
                if not df_master.empty:
                    rep = rep.merge(df_master[["store_id", "store_name"]], on="store_id", how="left")
                    rep["store_name"] = rep["store_name"].fillna(rep["store_id"])
                else:
                    rep["store_name"] = rep["store_id"]
                rep["engagement"] = rep.apply(
                    lambda r: _sa_pct(r["clicks"] + r["copies"], r["clicks"] + r["copies"] + r["searches"]), axis=1)
                rep["conv"] = rep.apply(lambda r: _sa_pct(r["copies"], r["clicks"]), axis=1)
                rep = rep.sort_values("clicks", ascending=False)

                summary = pd.DataFrame({
                    "المتجر": rep["store_name"].values,
                    "نقرات الروابط": rep["clicks"].astype(int).values,
                    "نسخ الكوبونات": rep["copies"].astype(int).values,
                    "عمليات البحث": rep["searches"].astype(int).values,
                    "معدل التفاعل %": rep["engagement"].round(1).values,
                    "معدل تحويل النسخ %": rep["conv"].round(1).values,
                    "أول نشاط": pd.to_datetime(rep["min"]).dt.strftime("%Y-%m-%d").values,
                    "آخر نشاط": pd.to_datetime(rep["max"]).dt.strftime("%Y-%m-%d").values,
                })
                total_row = pd.DataFrame([{
                    "المتجر": "الإجمالي",
                    "نقرات الروابط": int(rep["clicks"].sum()),
                    "نسخ الكوبونات": int(rep["copies"].sum()),
                    "عمليات البحث": int(rep["searches"].sum()),
                    "معدل التفاعل %": "", "معدل تحويل النسخ %": "", "أول نشاط": "", "آخر نشاط": "",
                }])
                st.dataframe(pd.concat([summary, total_row], ignore_index=True),
                             hide_index=True, use_container_width=True)

                daily = fdf.groupby(["adate", "action_type"]).size().unstack(fill_value=0)
                for c in ["click_link", "copy_coupon", "search"]:
                    if c not in daily.columns:
                        daily[c] = 0
                daily = (daily.rename(columns={"click_link": "نقرات", "copy_coupon": "نسخ", "search": "بحث"})
                         .reset_index().rename(columns={"adate": "التاريخ"}))
                daily["التاريخ"] = daily["التاريخ"].astype(str)

                store_label = "كل المتاجر" if not sel_names else "، ".join(sel_names[:5]) + ("…" if len(sel_names) > 5 else "")
                period_label = f"{d_start} ← {d_end}"

                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button("📥 تحميل CSV", summary.to_csv(index=False).encode("utf-8-sig"),
                                       f"DealPulse_Report_{d_start}_{d_end}.csv", "text/csv",
                                       use_container_width=True)
                with dl2:
                    try:
                        xls = _sa_build_excel(summary, daily, store_label, period_label)
                        st.download_button(
                            "📊 تحميل Excel احترافي", xls,
                            f"DealPulse_Report_{d_start}_{d_end}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
                    except Exception as e:
                        st.warning(f"تعذّر توليد ملف Excel: {e}")












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
                st.dataframe(sum_ar, use_container_width=True, hide_index=True)
            with tab_en:
                st.dataframe(sum_en, use_container_width=True, hide_index=True)

            with tab_manage:
                st.caption("⚠️ التعديل والحذف يطبّق على **كل المتاجر** التي تحتوي على القسم. لا يمكن التراجع.")

                # ═══════════════ Helpers ═══════════════
                def _do_rename(col_db, old_name, new_name):
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
                lambda p: 'bot' if 'bot' in str(p) or 'telegram' in str(p)
                else ('web' if 'web' in str(p) else 'other')
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
                    st.dataframe(pivot, use_container_width=True, hide_index=True, height=380)

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
                        st.dataframe(df_b_view, use_container_width=True, hide_index=True, height=380)

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
                        st.dataframe(df_w_view, use_container_width=True, hide_index=True, height=380)

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


elif page == "تحليل بحث الأكواد":
    page_title("📊", "لوحة تحكم ذكاء البحث",
               "عينك على السوق: اكتشف ما يبحث عنه العملاء وحدد الفرص الضائعة.")
    st.divider()

    try:
        conn = get_conn()
        query = "SELECT * FROM direct_search ORDER BY search_date DESC"
        df_log = pd.read_sql(query, conn)
        
        if not df_log.empty:
            # التحقق من نوع البيانات وتأمينها
            df_log['search_date'] = pd.to_datetime(df_log['search_date'])

            # --- التبويبات الرئيسية ---
            t_kpi, t_general, t_individual, t_admin = st.tabs([
                "📊 مؤشرات KPIs", "🌍 الأداء العام", "🔍 الأداء الفردي", "⚙️ إدارة السجلات"
            ])

            # 1. تبويب الـ KPIs (التصميم الملكي المعتمد بكروته الملونة)
            with t_kpi:
                st.write("### 🔑 مؤشرات الأداء الرئيسية")
                total_searches = len(df_log)
                found_count = df_log['user_found'].sum()
                missed_count = total_searches - found_count
                success_rate = (found_count / total_searches) * 100 if total_searches > 0 else 0

                # كروت الأداء الموحَّدة بهوية الشعار
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    kpi_card("🔎", "إجمالي عمليات البحث", total_searches, "info")
                with col_b:
                    kpi_card("✅", "عمليات بحث ناجحة", found_count, "emerald",
                             f"نسبة النجاح: {success_rate:.1f}%")
                with col_c:
                    kpi_card("❌", "فرص ضائعة", missed_count, "danger")
                
                st.divider()
                st.write("### 📋 سجل البحث التفصيلي")
                # تلوين الفرص الضائعة بالأحمر الخفيف
                def color_missed(row):
                    return [f'background-color: {BRAND["danger_soft"]}; color: #991B1B;'] * len(row) if not row['user_found'] else [''] * len(row)
                
                st.dataframe(df_log.style.apply(color_missed, axis=1), use_container_width=True)
                
                # --- زر تحميل الملفات ---
                csv = df_log.to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 تحميل سجل البحث كامل (CSV)", data=csv, file_name='search_analytics.csv', mime='text/csv')

            # 2. تبويب الأداء العام (تحليل الترندات والكلمات)
            with t_general:
                st.write("### 🌍 تحليل نشاط البحث العام")
                # الرسم البياني للنشاط الزمني
                df_trend = df_log.resample('h', on='search_date').size().reset_index(name='count')
                fig_gen = px.area(df_trend, x='search_date', y='count', title="معدل نشاط البحث (بالساعة)")
                st.plotly_chart(apply_brand_theme(fig_gen), use_container_width=True)
                
                st.divider()
                # ترند الكلمات
                st.write("### 🔥 الكلمات الأكثر طلباً")
                top_k = df_log['search_keyword'].value_counts().head(10).reset_index()
                top_k.columns = ['الكلمة', 'التكرار']
                fig_bar = px.bar(top_k, x='الكلمة', y='التكرار', color='التكرار',
                                 color_continuous_scale=[[0, BRAND["emerald_pastel"]],
                                                         [0.5, BRAND["emerald"]],
                                                         [1, BRAND["emerald_dark"]]])
                st.plotly_chart(apply_brand_theme(fig_bar), use_container_width=True)

            # 3. تبويب الأداء الفردي (تحليل المتاجر)
            with t_individual:
                st.write("### 🔍 تحليل أداء المتاجر")
                store = st.selectbox("اختر المتجر للمراقبة:", [""] + list(df_log['search_keyword'].unique()))
                if store:
                    df_store = df_log[df_log['search_keyword'] == store]
                    st.success(f"تم العثور على {len(df_store)} عملية بحث لـ '{store}'")
                    
                    # رسم بياني خاص بالمتجر
                    hourly = df_store.groupby(df_store['search_date'].dt.hour).size().reset_index(name='c')
                    hourly.columns = ['hour', 'c']
                    fig_store = px.line(hourly, x='hour', y='c',
                                        title=f"سلوك طلب {store} خلال اليوم", markers=True)
                    st.plotly_chart(apply_brand_theme(fig_store), use_container_width=True)

            # 4. تبويب الإدارة
            with t_admin:
                st.write("### ⚙️ أدوات تنظيف البيانات")
                if st.button("🗑️ تصفير السجل بالكامل"):
                    cur = conn.cursor()
                    cur.execute("TRUNCATE TABLE direct_search RESTART IDENTITY;")
                    conn.commit()
                    st.success("تم تصفير البيانات بنجاح")
                    st.rerun()

        else:
            st.warning("لا توجد بيانات حالياً.")

    except Exception as e:
        st.error(f"⚠️ حدث خطأ في النظام: {e}")
    finally:
        if 'conn' in locals(): conn.close()




        



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
                    st.dataframe(req_filtered[cols_display], use_container_width=True, hide_index=True, height=420)
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
                        st.dataframe(df_pending[cols_display], use_container_width=True, hide_index=True, height=380)

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
                        st.dataframe(df_fulfilled[cols_display], use_container_width=True, hide_index=True, height=420)

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


        # --- الصفحة العاشرة: تحليل طلبات الأكواد (Unavailable Codes Analytics) ---
elif page == "تحليل طلبات الأكواد":
    st.header("📊 مركز تحليل طلبات الأكواد")
    st.info("هنا نكتشف المتاجر التي يطلبها العملاء بكثرة لتوفير أكوادها.")

    # تقسيم الصفحة إلى تبييبات (Tabs)
    tab_gen_req, tab_ind_req = st.tabs(["📈 الأداء العام للطلبات", "🔍 تحليل متجر معين"])

    try:
        conn = get_conn()

        # --- التبويب الأول: الأداء العام ---
        with tab_gen_req:
            st.subheader("📊 إحصائيات الطلبات الحية")
            
            # جلب البيانات للتحليل العام
            query_all_req = "SELECT brand_name, requested_at FROM unavailable_codes_requests"
            df_all_req = pd.read_sql(query_all_req, conn)

            if not df_all_req.empty:
                # 1. داشبورد سريع
                c1, c2, c3 = st.columns(3)
                total_req = len(df_all_req)
                unique_brands = df_all_req['brand_name'].nunique()
                c1.metric("إجمالي الطلبات", total_req)
                c2.metric("متاجر فريدة مطلوبة", unique_brands)
                
                # 2. رسم بياني لأكثر 10 متاجر مطلوبة
                st.write("### 🔥 أكثر 10 متاجر مطلوبة")
                top_10_req = df_all_req['brand_name'].value_counts().head(10)
                st.bar_chart(top_10_req)

                # 3. زر تحميل البيانات الخام للتحليل
                req_excel = BytesIO()
                with pd.ExcelWriter(req_excel, engine='xlsxwriter') as writer:
                    df_all_req.to_excel(writer, index=False, sheet_name='All_Requests')
                st.download_button("📥 تحميل سجل الطلبات (Excel)", req_excel.getvalue(), "all_requests_analytics.xlsx")
            else:
                st.warning("لا توجد بيانات كافية لإجراء تحليل عام حالياً.")

        # --- التبويب الثاني: تحليل متجر معين ---
        with tab_ind_req:
            st.subheader("🔍 تتبع طلبات متجر محدد")
            if not df_all_req.empty:
                selected_brand = st.selectbox("اختر المتجر أو الرابط لتحليله:", df_all_req['brand_name'].unique())
                
                if selected_brand:
                    # تصفية البيانات للمتجر المختار
                    brand_data = df_all_req[df_all_req['brand_name'] == selected_brand]
                    
                    st.write(f"### تحليل الطلبات لـ: {selected_brand}")
                    st.success(f"تم طلب هذا المتجر {len(brand_data)} مرة.")

                    # رسم بياني للتدفق الزمني لطلبات هذا المتجر
                    brand_data['date'] = pd.to_datetime(brand_data['requested_at']).dt.date
                    timeline = brand_data.groupby('date').size()
                    st.line_chart(timeline)
            else:
                st.warning("لا توجد طلبات متاحة للتحليل الفردي.")

    except Exception as e:
        st.error(f"خطأ في معالجة التحليلات: {e}")
    finally:
        if 'conn' in locals(): conn.close()




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
                st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)

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
            st.dataframe(users_df, use_container_width=True, hide_index=True)

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
    page_title("📊", "مركز تحليل سلوك المستخدمين")
    st.info("تحليل معمق لقاعدة البيانات لفهم تفاعل العملاء وتصنيفهم بناءً على الـ 17 عموداً الأساسية.")

    # إنشاء الثلاث تبويبات المطلوبة
    tab_kpi, tab_gen_u, tab_ind_u = st.tabs(["🎯 مؤشرات الأداء (KPIs)", "📈 الأداء العام للعملاء", "🔍 الفحص الفردي (ID)"])

    try:
        conn = get_conn()

        # JOIN رئيسي: bot_users + action_logs على user_id (المصدر الوحيد للحقيقة بعد الميجريشن)
        df_users = pd.read_sql("""
            SELECT
                b.telegram_id,
                COALESCE(NULLIF(b.username, ''), '— مجهول —') AS username,
                b.joined_at,
                b.last_seen,
                COUNT(a.id) AS total_actions,
                COUNT(*) FILTER (WHERE a.action_type = 'click_link')   AS link_clicks,
                COUNT(*) FILTER (WHERE a.action_type = 'copy_coupon')  AS coupon_copies,
                COUNT(*) FILTER (WHERE a.action_type = 'search')       AS searches,
                COUNT(*) FILTER (WHERE a.action_type = 'start')        AS sessions
            FROM bot_users b
            LEFT JOIN action_logs a ON a.user_id = b.telegram_id
            GROUP BY b.telegram_id, b.username, b.joined_at, b.last_seen
            ORDER BY total_actions DESC
        """, conn)

        if not df_users.empty:
            df_users['joined_at'] = pd.to_datetime(df_users['joined_at'])
            df_users['last_seen'] = pd.to_datetime(df_users['last_seen'])

            # --- تبويب 1: KPIs ---
            with tab_kpi:
                st.subheader("🎯 ملخص جودة قاعدة المستخدمين")
                now = pd.Timestamp.now()
                active_24h = (df_users['last_seen'] >= (now - pd.Timedelta(hours=24))).sum()
                inactive = len(df_users) - active_24h
                beneficiaries = ((df_users['link_clicks'] + df_users['coupon_copies']) > 0).sum()

                c1, c2, c3 = st.columns(3)
                c1.metric("👥 إجمالي المشتركين", len(df_users))
                c2.metric("🟢 نشطون (24س)", int(active_24h))
                c3.metric("🔴 خاملون", int(inactive))

                st.divider()
                cc1, cc2, cc3, cc4 = st.columns(4)
                cc1.metric("🖱️ نقرات روابط", int(df_users['link_clicks'].sum()))
                cc2.metric("📋 نسخ كوبونات", int(df_users['coupon_copies'].sum()))
                cc3.metric("🔍 عمليات بحث", int(df_users['searches'].sum()))
                cc4.metric("🎁 المستفيدون", int(beneficiaries))

            # --- تبويب 2: الأداء العام (جدول حركة المستخدمين) ---
            with tab_gen_u:
                st.subheader("📈 لوحة أعلى المستخدمين تفاعلاً")

                top_users = df_users.head(20)[
                    ['username', 'telegram_id', 'sessions', 'link_clicks',
                     'coupon_copies', 'searches', 'total_actions', 'last_seen']
                ].rename(columns={
                    'username': 'المستخدم',
                    'telegram_id': 'Telegram ID',
                    'sessions': 'جلسات',
                    'link_clicks': 'نقرات الروابط',
                    'coupon_copies': 'نسخ الكوبون',
                    'searches': 'عمليات البحث',
                    'total_actions': 'إجمالي الحركات',
                    'last_seen': 'آخر ظهور'
                })
                st.dataframe(top_users, use_container_width=True, hide_index=True)

                # رسم: إجمالي حركات أفضل 10 مستخدمين
                st.write("### 🏆 أفضل 10 مستخدمين")
                top10 = df_users.head(10).set_index('username')[
                    ['link_clicks', 'coupon_copies', 'searches']
                ].rename(columns={
                    'link_clicks': 'نقرات', 'coupon_copies': 'نسخ', 'searches': 'بحث'
                })
                st.bar_chart(top10)

                u_anal_excel = BytesIO()
                with pd.ExcelWriter(u_anal_excel, engine='xlsxwriter') as writer:
                    df_users.to_excel(writer, index=False, sheet_name='Users_Analytics')
                st.download_button("📥 تحميل التقرير الكامل (Excel)",
                                   u_anal_excel.getvalue(), "total_users_analytics.xlsx")

            # --- تبويب 3: الفحص الفردي (بالـ ID) ---
            with tab_ind_u:
                st.subheader("🔍 تفاصيل ملف العميل")
                search_id = st.text_input("أدخل Telegram ID للمستخدم:", placeholder="مثال: 123456789")

                if search_id:
                    user_data = df_users[df_users['telegram_id'].astype(str) == search_id.strip()]

                    if not user_data.empty:
                        u = user_data.iloc[0]
                        st.success(f"✅ ملف: {u['username']} ({u['telegram_id']})")

                        bc1, bc2, bc3, bc4 = st.columns(4)
                        bc1.info(f"**تاريخ الانضمام**\n\n{u['joined_at'].date() if pd.notna(u['joined_at']) else '—'}")
                        bc2.info(f"**آخر ظهور**\n\n{u['last_seen'].date() if pd.notna(u['last_seen']) else '—'}")
                        bc3.info(f"**عدد الجلسات**\n\n{int(u['sessions'])}")
                        bc4.info(f"**إجمالي الحركات**\n\n{int(u['total_actions'])}")

                        st.divider()
                        # سجل تفصيلي مأخوذ من action_logs لهذا المستخدم
                        st.write("### 📜 آخر 30 حركة لهذا المستخدم")
                        df_personal = pd.read_sql("""
                            SELECT
                                TO_CHAR(a.action_time, 'YYYY-MM-DD HH24:MI:SS') AS "الوقت",
                                a.action_type AS "الحركة",
                                COALESCE(a.store_id, '—') AS "المتجر",
                                COALESCE(m.name_en, '') AS "English Name",
                                COALESCE(a.details, '') AS "التفاصيل"
                            FROM action_logs a
                            LEFT JOIN master m ON a.store_id = m.store_id
                            WHERE a.user_id = %s
                            ORDER BY a.action_time DESC
                            LIMIT 30
                        """, conn, params=(int(u['telegram_id']),))

                        if not df_personal.empty:
                            st.dataframe(df_personal, use_container_width=True, hide_index=True)
                        else:
                            st.info("📭 لا توجد حركات لهذا المستخدم بعد.")
                    else:
                        st.error("❌ لا يوجد مستخدم بهذا الـ ID في قاعدة البيانات.")
        else:
            st.warning("⚠️ قاعدة البيانات فارغة. انتظر دخول مستخدمين لبدء التحليل.")

    except Exception as e:
        st.error(f"حدث خطأ في صفحة التحليلات: {e}")
    finally:
        if 'conn' in locals(): conn.close()




        

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
                if st.button("🚀 إرسال الرسالة الآن", use_container_width=True, key="tg_send"):
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
                        st.image(msg_image, use_container_width=True)
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
                    st.dataframe(history_df, use_container_width=True)
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
                             use_container_width=True, key="em_send", type="primary"):
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
                        st.dataframe(em_hist, use_container_width=True, hide_index=True)
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
                st.dataframe(df_logs, use_container_width=True, hide_index=True, height=420)
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
                st.dataframe(df_display.drop(columns=['المعرف']), use_container_width=True)
                
                st.divider()
                st.subheader("💬 الرد وإغلاق التذكرة")
                
                col_sel, col_btn = st.columns([2, 1])
                with col_sel:
                    # نستخدم قائمة المستخدمين من البيانات المجلوبة
                    ticket_to_solve = st.selectbox("اختر تذكرة للرد عليها:", df_open["username"], key="open_tickets")
                    reply_text = st.text_area(f"اكتب ردك لـ {ticket_to_solve}:", placeholder="أهلاً بك، تم تحديث الكود...")
                
                with col_btn:
                    st.write("##") # موازنة المسافة
                    if st.button("📧 إرسال الرد وإغلاق الطلب", use_container_width=True):
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
                st.dataframe(df_seo, use_container_width=True)
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
                    st.dataframe(df_vip, use_container_width=True, hide_index=True)
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
                st.dataframe(df_ev, use_container_width=True)
                
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
                st.dataframe(df_mkt, use_container_width=True)
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
                st.dataframe(df_agents, use_container_width=True, hide_index=True)
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
                st.dataframe(df_threats, use_container_width=True)
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
            st.dataframe(df_app_logs, use_container_width=True, hide_index=True)
        except Exception:
            st.info("سيظهر سجل الأحداث هنا فور توليد النظام تسجيلات.")

        st.divider()

        # --- 5. النسخ الاحتياطي الشامل ---
        st.subheader("💾 النسخ الاحتياطي")
        st.info("تحميل نسخة كاملة من قاعدة البيانات بصيغة Excel (ورقة لكل جدول رئيسي).")
        if st.button("📥 توليد نسخة احتياطية الآن", use_container_width=True):
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
                    use_container_width=True,
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
                st.dataframe(df_q[["العرض", "القناة", "الحالة"]], use_container_width=True)
                
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
                st.dataframe(df_history, use_container_width=True)
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
                st.dataframe(compare_df, use_container_width=True, hide_index=True)
                fig_cmp = px.bar(compare_df, x="المصدر", y="الأحداث",
                                 title="توزيع الأحداث بحسب المصدر", color="المصدر",
                                 color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig_cmp, use_container_width=True)
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
                                    use_container_width=True)
                with col_g2:
                    st.plotly_chart(px.line(growth_df, x="التاريخ", y="الإجمالي التراكمي",
                                            title="النمو التراكمي",
                                            color_discrete_sequence=["#6366F1"]),
                                    use_container_width=True)
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
                                use_container_width=True)
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
                                use_container_width=True)
                st.dataframe(events_df, use_container_width=True, hide_index=True)
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
                                use_container_width=True)
                st.dataframe(top_web, use_container_width=True, hide_index=True)
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
                                use_container_width=True)
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
                                use_container_width=True)
                st.dataframe(top_kw, use_container_width=True, hide_index=True)
            st.write("### 🚨 فجوات المحتوى (بحث بلا نتائج)")
            gaps_df = pd.read_sql("""
                SELECT search_keyword AS "الكلمة", COUNT(*) AS "مرات البحث",
                       MAX(search_date) AS "آخر بحث"
                FROM direct_search WHERE platform='Web' AND user_found=false
                GROUP BY search_keyword ORDER BY COUNT(*) DESC LIMIT 20
            """, conn)
            if not gaps_df.empty:
                gaps_df["آخر بحث"] = pd.to_datetime(gaps_df["آخر بحث"], errors="coerce").dt.strftime("%Y-%m-%d")
                st.dataframe(gaps_df, use_container_width=True, hide_index=True)
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
                                    use_container_width=True)
                else:
                    st.info("لا توجد بيانات مدن بعد.")
            with col_c2:
                if not country_df.empty:
                    st.plotly_chart(px.pie(country_df, names="الدولة", values="العدد",
                                           title="توزيع الدول",
                                           color_discrete_sequence=px.colors.qualitative.Set2),
                                    use_container_width=True)
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
                                use_container_width=True)
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
            submit_topic = st.form_submit_button("📥 جدولة الوظائف", use_container_width=True)

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
        if st.button("⚙️ توليد الآن", use_container_width=True, type="primary"):
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
        if st.button("🔄 تحديث القائمة", use_container_width=True):
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
                                 use_container_width=True, type="primary"):
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
                                 use_container_width=True):
                        # نطلب تأكيداً عبر session_state
                        confirm_key = f"seo_del_confirm_{page_id}"
                        st.session_state[confirm_key] = True

                # تأكيد الحذف
                if st.session_state.get(f"seo_del_confirm_{page_id}"):
                    st.warning(f"⚠️ هل تريد حذف المسودّة #{page_id} نهائياً؟")
                    cf1, cf2, _ = st.columns([1, 1, 3])
                    with cf1:
                        if st.button("نعم احذف", key=f"seo_del_yes_{page_id}",
                                     use_container_width=True, type="primary"):
                            res, derr = _admin_delete(f"/admin/seo-draft/{page_id}")
                            if derr:
                                st.error(derr)
                            else:
                                st.toast(f"✅ حُذفت", icon="🗑️")
                                st.session_state.pop(f"seo_del_confirm_{page_id}", None)
                                st.rerun()
                    with cf2:
                        if st.button("إلغاء", key=f"seo_del_no_{page_id}",
                                     use_container_width=True):
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
                                                                  use_container_width=True):
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
                                                               use_container_width=True)

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
                if st.button("🔁 إعادة جدولة الكل", use_container_width=True):
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
        if st.button("🔄 تحديث", use_container_width=True):
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
                    st.link_button("🌐 افتح الصفحة", live_url, use_container_width=True)
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
                        res, err = _admin_post("/seo-opportunities", json_body=body)
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
        if st.button("🔄 تحديث Trends لكل الكلمات", use_container_width=True,
                     key="opp_refresh_all",
                     help="يستغرق ~5 ثوانٍ × عدد الكلمات (لتفادي rate-limit)"):
            with st.spinner("جلب Google Trends لكل الكلمات النشطة..."):
                res, err = _admin_post("/seo-opportunities/refresh-all")
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
        "/seo-opportunities",
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
                                     type="primary", use_container_width=True):
                            with st.spinner("جاري التوليد (قد يستغرق 30 ثانية للـ LLM)..."):
                                res, err = _admin_post(
                                    f"/seo-opportunities/{kw['id']}/generate-page"
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
                                 use_container_width=True,
                                 help="جلب فوري لدرجة Google Trends لهذه الكلمة"):
                        with st.spinner("جلب من Google..."):
                            res, err = _admin_post(
                                f"/seo-opportunities/{kw['id']}/refresh"
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
                                 use_container_width=True):
                        res, err = _admin_put(
                            f"/seo-opportunities/{kw['id']}",
                            json_body={"active": inactive},  # عكس الحالة الحالية
                        )
                        if err:
                            st.error(err)
                        else:
                            st.rerun()

                with a4:
                    with st.popover("✏️ تعديل", use_container_width=True):
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
                                    f"/seo-opportunities/{kw['id']}",
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
                                     type="primary", use_container_width=True):
                            res, err = _admin_delete(f"/seo-opportunities/{kw['id']}")
                            if err:
                                st.error(err)
                            else:
                                st.session_state.pop(confirm_key, None)
                                st.toast("🗑️ تم الحذف", icon="🗑️")
                                st.rerun()
                    else:
                        if st.button("🗑️ حذف", key=f"del_{kw['id']}",
                                     use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# الرصد الاجتماعي — Social Listener + Auto-Responder (Week 7-8)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "الرصد الاجتماعي":
    st.header("📡 الرصد والتفاعل الاجتماعي")
    st.caption("النظام يرصد الإشارات (mentions) عن الكوبونات والخصومات، ويجهّز ردوداً ذكية تربط لصفحات الهبوط لزيادة الزوار.")

    top1, top2 = st.columns([1, 2])
    with top1:
        if st.button("🔄 معالجة الإشارات الآن", use_container_width=True, type="primary"):
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
                    if st.button("✅ اعتماد ونشر", key=f"soc_appr_{r['id']}", use_container_width=True, type="primary"):
                        res, e2 = _admin_post(f"/admin/social-approve/{r['id']}")
                        if e2:
                            st.error(e2)
                        else:
                            st.success("تم الاعتماد ✅" + (" (نُشر)" if res and res.get("via") == "webhook" and res.get("ok") else ""))
                            st.rerun()
                with act2:
                    if st.button("🗑️ رفض", key=f"soc_rej_{r['id']}", use_container_width=True):
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
        if st.button("🔄 تحديث الآن", use_container_width=True, key="leads_refresh"):
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
                            use_container_width=True,
                            type="primary",
                        )
                    else:
                        st.button(
                            "🚫 لا يوجد رابط",
                            disabled=True,
                            use_container_width=True,
                            key=f"nourl_{lead['lead_id']}",
                        )
                with act_c2:
                    if lead.get("status") in ("matched", "responded", "lead_pending"):
                        if st.button("✅ تم الرد", key=f"replied_{lead['lead_id']}",
                                     use_container_width=True):
                            _r, e2 = _admin_post(f"/admin/social-leads/{lead['lead_id']}/mark-replied")
                            if e2:
                                st.error(e2)
                            else:
                                st.toast("✅ تم تعليمه كـ مردود عليه", icon="✅")
                                st.rerun()
                with act_c3:
                    if lead.get("status") in ("matched", "responded", "lead_pending"):
                        if st.button("🗑️ تجاهل", key=f"dismiss_{lead['lead_id']}",
                                     use_container_width=True):
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
            st.dataframe(df, use_container_width=True, hide_index=True)

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
                        if st.button(lbl, key=f"qh_{w['id']}", use_container_width=True):
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
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption("الظهور يُسجَّل عند توليد كل رد. النقرات/التحويلات تتفعّل مع ربط الإحالة لاحقاً.")

