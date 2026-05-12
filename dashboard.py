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

# إعداد الصفحة
st.set_page_config(
page_title="نبض الصفقات KSA | DEAL PULSE",
page_icon="🟢",
layout="wide",
initial_sidebar_state="expanded",
)

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

_wm_url = f"data:image/jpeg;base64,{_logo_b64}" if _logo_b64 else ""



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

        st.divider()

        # الصف 5: الأهمية + التواريخ + عمولتي
        col7, col8, col9, col10 = st.columns(4)
        priority   = col7.selectbox("🚀 الأهمية", ["عادي", "مهم", "عاجل", "عاجل جداً"])
        date_start = col8.date_input("📅 تاريخ البداية", datetime.date.today())
        date_end   = col9.date_input("📅 تاريخ الانتهاء", datetime.date.today() + datetime.timedelta(days=30))
        my_coupon  = col10.text_input("💵 عمولتي (كود التتبع)")

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
                    cur.execute("""
                        INSERT INTO master
                            (store_id, name_en, affiliate_link, public_coupon,
                                extra_offer, extra_offer_en, store_bio, store_bio_en,
                                priority_score, discount_value, store_tags, store_tags_en,
                                my_coupon, first_time, last_time,
                                total_coupon_copies, total_link_clicks, is_trending,
                                logo_url)
                        VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, 0,0,'عادي', %s)
                    """, (
                        store_id, name_en, aff_link, pub_coupon,
                        extra_offer, extra_offer_en, store_bio, store_bio_en,
                        priority, disc_val, tags_ar_lit, tags_en_lit,
                        my_coupon, date_start, date_end,
                        final_logo_url or None,
                    ))
                    conn.commit()
                    st.success(f"✅ تم الحفظ! التاقات: {len(selected_tags)} AR / {len(selected_tags_en)} EN")
                    st.balloons()
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

                    st.divider()

                    # الصف 5: الأهمية + التواريخ + عمولتي
                    r5c1, r5c2, r5c3, r5c4 = st.columns(4)
                    p_list = ["عادي", "مهم", "عاجل", "عاجل جداً"]
                    u_prio  = r5c1.selectbox("🚀 الأهمية", p_list, index=p_list.index(res['priority_score']) if res['priority_score'] in p_list else 0)
                    u_start = r5c2.date_input("📅 تاريخ البداية", res['first_time'])
                    u_end   = r5c3.date_input("📅 تاريخ الانتهاء", res['last_time'])
                    u_mine  = r5c4.text_input("💵 عمولتي الخاصة", res['my_coupon'])

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
                            cur.execute("""
                                UPDATE master SET
                                    store_id=%s, name_en=%s,
                                    affiliate_link=%s, public_coupon=%s,
                                    extra_offer=%s, extra_offer_en=%s,
                                    store_bio=%s,   store_bio_en=%s,
                                    priority_score=%s, discount_value=%s, my_coupon=%s,
                                    first_time=%s, last_time=%s,
                                    logo_url=%s
                                WHERE id=%s
                            """, (
                                u_store, u_name_en,
                                u_aff, u_pub,
                                u_extra, u_extra_en,
                                u_bio, u_bio_en,
                                u_prio, u_disc, u_mine,
                                u_start, u_end,
                                u_logo.strip() or None,
                                search_id,
                            ))
                            conn.commit()
                            st.success("✅ تم تحديث البيانات بنجاح.")
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
        # سحب الأعمدة المطلوبة (AR + EN جنباً إلى جنب)
        query = """
            SELECT id, store_id, name_en, affiliate_link, public_coupon, discount_value,
                    priority_score, first_time, last_time, my_coupon,
                    store_bio, store_bio_en, extra_offer, extra_offer_en,
                    store_tags, store_tags_en
            FROM master ORDER BY id DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            # تعريب أسماء الأعمدة يدوياً (AR + EN)
            df.columns = [
                'ID', 'اسم المتجر', 'Store Name (EN)', 'رابط الأفلييت', 'كوبون العملاء', 'نسبة الخصم',
                'الأهمية', 'تاريخ البداية', 'تاريخ الانتهاء', 'عمولتي الخاصة',
                'وصف المتجر', 'Description (EN)', 'عرض إضافي', 'Extra Offer (EN)',
                'تاقات', 'Tags (EN)',
            ]

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


    # --- الصفحة الثالثة: جدول الكوبونات (واجهة العميل مع الترند من القاعدة) ---
    # --- الصفحة الثالثة: جدول الكوبونات (واجهة العميل مع الترند من القاعدة) ---
if page == "جدول الكوبونات":
    st.header("🎟️ عرض الكوبونات المباشر (واجهة البوت)")
    st.info("المتاجر المحددة كـ 'ترند' في قاعدة البيانات ستظهر بعلامة 🔥 وتتصدر القائمة.")
    try:
        conn = get_conn()
        # جلب البيانات (AR + EN) للعرض الثنائي
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
                total_coupon_copies,
                total_link_clicks
            FROM master
            ORDER BY
                CASE WHEN is_trending = 'ترند 🔥' THEN 1 ELSE 2 END,
                priority_score DESC
        """
        df_client = pd.read_sql(query, conn)
        conn.close()

        if not df_client.empty:
            # دمج علامة الترند مع الاسم برمجياً للعرض فقط
            def format_name(row):
                if row['is_trending'] == 'ترند 🔥':
                    return f"🔥 {row['store_id']}"
                return row['store_id']

            df_client['اسم المتجر'] = df_client.apply(format_name, axis=1)

            # اختيار الأعمدة: AR + EN جنباً إلى جنب
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
            }

            df_display = df_client[list(display_cols.keys())].rename(columns=display_cols)

            st.dataframe(df_display, use_container_width=True, height=600, hide_index=True)
        
        # زر تحميل الإكسل
    except Exception:
        pass
    try:
        # هنا الكود الذي قد يسبب خطأ (مثلاً جلب البيانات)
        if not df_display.empty:
            # زر تحميل الإكسل
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_display.to_excel(writer, index=False, sheet_name='Trending_View')
        
            # ملاحظة: يجب أن يكون الزر خارج الـ with ولكن داخل الـ if
            st.download_button(
                label="📥 تحميل قائمة العملاء (Excel)",
                data=output.getvalue(),
                file_name="Tawfeer_Coupons.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ لا توجد كوبونات متاحة.")

    except Exception as e:
        st.error(f"❌ خطأ: {e}")



    # --- صفحة تحليل المتاجر (الترند المزدوج والـ 3 خطوط بالساعة) ---
if page == "تحليل المتاجر":
    st.header("📊 تحليل المتاجر")

    tab_gen, tab_ind, tab_trend = st.tabs(["🌎 الأداء العام", "👤 تحليل متجر محدد", "🔥 إدارة الترند"])

    try:
        conn = get_conn()
        conn.rollback()

        # جلب action_logs كمصدر أساسي + master لحالة الترند
        df_logs = pd.read_sql("""
            SELECT action_time, action_type, user_id, store_id
            FROM action_logs
            WHERE action_type IN ('click_link', 'copy_coupon', 'search')
        """, conn)
        df_m = pd.read_sql(
            "SELECT store_id, COALESCE(name_en, '') AS name_en, total_coupon_copies, total_link_clicks, is_trending FROM master", conn
        )

        # معالجة مسبقة بـ Pandas لضمان السرعة
        if not df_logs.empty:
            df_logs['action_time'] = pd.to_datetime(df_logs['action_time'])
            df_logs['hour'] = df_logs['action_time'].dt.floor('h')

        with tab_gen:
            # 1. KPIs مأخوذة من action_logs مباشرة
            counts = df_logs['action_type'].value_counts() if not df_logs.empty else pd.Series(dtype=int)
            total_links  = int(counts.get('click_link',  0))
            total_copy   = int(counts.get('copy_coupon', 0))
            total_search = int(counts.get('search',      0))

            c1, c2, c3 = st.columns(3)
            c1.metric("🖱️ إجمالي نقرات الروابط",  f"{total_links:,}")
            c2.metric("✂️ إجمالي نسخ الكوبونات",   f"{total_copy:,}")
            c3.metric("🔍 إجمالي عمليات البحث",    f"{total_search:,}")

            st.divider()

            # 2. خط زمني بالساعة (Hourly) بـ 3 خطوط متزامنة
            st.subheader("📈 الأداء بالساعة — نقرات / نسخ / بحث")
            if not df_logs.empty:
                hourly = (df_logs.groupby(['hour', 'action_type'])
                                    .size()
                                    .reset_index(name='count'))
                hourly_pivot = (hourly.pivot(index='hour', columns='action_type', values='count')
                                        .fillna(0)
                                        .rename(columns={
                                            'click_link':  'نقرات الروابط',
                                            'copy_coupon': 'نسخ الكوبونات',
                                            'search':      'عمليات البحث'
                                        }))
                for col in ['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث']:
                    if col not in hourly_pivot.columns:
                        hourly_pivot[col] = 0
                # تعبئة الساعات الخالية بصفر لإظهار التعرج الحقيقي بدل الخط المستقيم
                full_range = pd.date_range(
                    start=hourly_pivot.index.min(),
                    end=hourly_pivot.index.max(),
                    freq='h'
                )
                hourly_pivot = hourly_pivot.reindex(full_range, fill_value=0)
                st.line_chart(hourly_pivot[['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث']])
            else:
                st.info("📭 لا توجد حركات مسجّلة بعد. الرسم سيظهر فور تفاعل المستخدمين مع البوت.")

                # سطر الإصلاح (أضفه عند سطر 1121 تقريباً)
                for col in ['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث']:
                    if col not in hourly_pivot.columns:
                        hourly_pivot[col] = 0

            # تأكد من تحويل البيانات لنص CSV بشكل سليم قبل التحميل
            csv_data = df_logs.to_csv(index=False).encode('utf-8-sig')
    
            st.download_button(
                label="📥 تحميل تقرير الأداء العام",
                data=csv_data,
                file_name=f"General_Report_{datetime.date.today()}.csv",
                mime="text/csv"
            )

        with tab_ind:
            st.subheader("🔍 البحث عن أداء متجر")
            store_options = [""] + sorted(df_m['store_id'].unique().tolist())
            search_input = st.selectbox("اختر المتجر للمعاينة:", store_options, key="search_ind")

            if search_input:
                target = df_m[df_m['store_id'] == search_input].iloc[0]
                store_logs = df_logs[df_logs['store_id'] == search_input] if not df_logs.empty else pd.DataFrame()
                sc = store_logs['action_type'].value_counts() if not store_logs.empty else pd.Series(dtype=int)
                s_clicks = int(sc.get('click_link',  0))
                s_copies = int(sc.get('copy_coupon', 0))
                s_search = int(sc.get('search',      0))

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("🖱️ نقرات الرابط",  f"{s_clicks:,}")
                k2.metric("✂️ مرات النسخ",     f"{s_copies:,}")
                k3.metric("🔍 البحث عنه",      f"{s_search:,}")
                k4.metric("الحالة",             target['is_trending'])

                df_ind_plot = pd.DataFrame({
                    'النوع':  ['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث'],
                    'العدد':  [s_clicks, s_copies, s_search]
                })
                _fig_ind_bar = px.bar(df_ind_plot, x='النوع', y='العدد', color='النوع')
                st.plotly_chart(apply_brand_theme(_fig_ind_bar), use_container_width=True)

        with tab_trend:
            st.subheader("🔥 نظام التحكم في الترند")
            col_a, col_b = st.columns(2)

            with col_a:
                st.write("🤖 **الترند الآلي — أعلى 5 سكور (نسخ×3 + نقر×2 + بحث×1)**")
                if not df_logs.empty:
                    score_raw = (df_logs.groupby(['store_id', 'action_type'])
                    .size().unstack(fill_value=0).reset_index())

                    # ركز هنا.. لازم نفس مستوى score_raw
                    for col in ['click_link', 'copy_coupon', 'search']:
                        if col not in score_raw.columns:
                            score_raw[col] = 0

                    # وهذا يرجع لمستوى الـ for
                    score_raw['السكور'] = (score_raw['copy_coupon'] * 3 +
                    score_raw['click_link']  * 2 +
                    score_raw['search']      * 1)
                    score_raw = score_raw.merge(df_m[['store_id', 'name_en']], on='store_id', how='left')
                    auto_top = (score_raw[['store_id', 'name_en', 'copy_coupon', 'click_link', 'search', 'السكور']]
                                .sort_values('السكور', ascending=False)
                                .head(5)
                                .rename(columns={
                                    'store_id':    'المتجر',
                                    'name_en':     'English Name',
                                    'copy_coupon': 'نسخ (×3)',
                                    'click_link':  'نقرات (×2)',
                                    'search':      'بحث (×1)'
                                })
                                .reset_index(drop=True))
                    st.table(auto_top)
                else:
                    st.info("لا توجد بيانات كافية لحساب الترند الآلي.")

            with col_b:
                st.write("🛠️ **الترند اليدوي (تثبيت)**")
                trending_set = set(df_m[df_m['is_trending'] == 'ترند 🔥']['store_id'])
                store_list = df_m['store_id'].unique().tolist()
                store_display = [f"🔥 {s}" if s in trending_set else s for s in store_list]
                store_map = dict(zip(store_display, store_list))

                selected_display = st.selectbox("اختر متجر لتغيير حالته:", store_display)
                target_store = store_map[selected_display]
                new_status = st.radio("الحالة المطلوبة:", ["عادي", "ترند 🔥"])

                if st.button("تحديث حالة الترند"):
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE master SET is_trending = %s WHERE store_id = %s",
                        (new_status, target_store)
                    )
                    conn.commit()
                    st.success(f"✅ تم تحويل {target_store} إلى {new_status}")
                    st.rerun()

    except Exception as e:
        st.error(f"⚠️ خطأ: {e}")
    finally:
        if 'conn' in locals(): conn.close()












        # ---  الصفحة الخامسة : مركز قيادة الأقسام والتاقات (إدارة الـ 10 أعمدة) ---
        # --- الصفحة الخامسة: مركز قيادة الأقسام والتاقات (نظام رصد نقرات الأقسام) ---
        # --- الصفحة الخامسة المحدثة: عرض الأقسام من واقع الماستر ---
        # --- الصفحة الخامسة: مركز قيادة الأقسام (الربط الهندسي والتحليل الفعلي) ---
if page == "جدول الأقسام":
    st.header("📂 مركز قيادة الأقسام (الربط الهندسي)")

    conn = None
    try:
        conn = get_conn()
        query = """
        SELECT store_id,
                COALESCE(name_en, '')        AS name_en,
                store_tags, store_tags_en,
                store_bio,  store_bio_en,
                public_coupon, discount_value, affiliate_link,
                extra_offer, extra_offer_en,
                total_coupon_copies, total_link_clicks
        FROM master
"""
        df_raw = pd.read_sql(query, conn)

        if not df_raw.empty:
            all_rows = []
            for _, row in df_raw.iterrows():
                ar_tags = parse_tags(row.get('store_tags'))
                en_tags = parse_tags(row.get('store_tags_en'))

                base = {
                    'المتجر':              row['store_id'],
                    'Store Name (EN)':     row['name_en'],
                    'الوصف':               row['store_bio'],
                    'Description (EN)':    row.get('store_bio_en') or '',
                    'الكوبون':             row['public_coupon'],
                    'عرض إضافي':           row['extra_offer'],
                    'Extra Offer (EN)':    row.get('extra_offer_en') or '',
                    'الخصم':               row['discount_value'],
                    'الرابط':              row['affiliate_link'],
                    'نقرات_الكوبون':       row['total_coupon_copies'],
                    'نقرات_الروابط':       row['total_link_clicks'],
                    'إجمالي_التفاعل':      row['total_coupon_copies'] + row['total_link_clicks'],
                }
                for t in ar_tags:
                    if t:
                        all_rows.append({'اللغة': 'AR', 'القسم': t, **base})
                for t in en_tags:
                    if t:
                        all_rows.append({'اللغة': 'EN', 'القسم': t, **base})

            df_full = pd.DataFrame(all_rows)
            tab1, tab2 = st.tabs(["📊 لوحة إدارة الأقسام", "📋 الجدول الشامل"])

            with tab1:
                st.subheader("📋 ملخص أداء الأقسام (AR / EN منفصلَين)")
                summary = (df_full.groupby(['اللغة', 'القسم']).agg(
                    عدد_المتاجر=('المتجر', 'count'),
                    نقرات_الكوبونات=('نقرات_الكوبون', 'sum'),
                    إجمالي_التفاعل=('إجمالي_التفاعل', 'sum'),
                    المتاجر_التابعة=('المتجر', lambda x: ", ".join(list(set(x))))
                ).reset_index().sort_values(by=['اللغة', 'إجمالي_التفاعل'], ascending=[True, False]))

                summary.columns = ['اللغة', 'اسم القسم', 'عدد المتاجر', 'نقرات الكوبونات', 'إجمالي التفاعل', 'المتاجر التابعة']
                st.dataframe(summary, use_container_width=True, hide_index=True)

            with tab2:
                st.subheader("🔍 استعراض الارتباطات الكاملة (AR + EN)")
                display_cols = [
                    'اللغة', 'القسم', 'المتجر', 'Store Name (EN)',
                    'الوصف', 'Description (EN)',
                    'الكوبون', 'عرض إضافي', 'Extra Offer (EN)',
                    'الخصم', 'الرابط',
                ]
                st.dataframe(df_full[display_cols], use_container_width=True, hide_index=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    summary.to_excel(writer, index=False, sheet_name='إحصائيات الأقسام')
                    df_full[display_cols].to_excel(writer, index=False, sheet_name='الارتباطات الشاملة')

                st.download_button(
                    label="📥 تحميل التقرير الشامل (Excel)",
                    data=output.getvalue(),
                    file_name="Tawfeer_Full_Analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cat_full_excel_1"
                )
        else:
            st.info("لا توجد بيانات متاجر مرتبطة بأقسام حالياً.")
    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة البيانات: {e}")
    finally:
        if conn:
            conn.close()
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







# --- صفحة تحليل المتاجر (الترند المزدوج والـ 3 خطوط بالساعة) ---
elif page == "تحليل المتاجر":
    st.header("📊 تحليل المتاجر")

    tab_gen, tab_ind, tab_trend = st.tabs(["🌎 الأداء العام", "👤 تحليل متجر محدد", "🔥 إدارة الترند"])

    try:
        conn = get_conn()
        conn.rollback()

        # جلب action_logs كمصدر أساسي + master لحالة الترند
        df_logs = pd.read_sql("""
            SELECT action_time, action_type, user_id, store_id
            FROM action_logs
            WHERE action_type IN ('click_link', 'copy_coupon', 'search')
        """, conn)
        df_m = pd.read_sql(
            "SELECT store_id, COALESCE(name_en, '') AS name_en, total_coupon_copies, total_link_clicks, is_trending FROM master", conn
        )

        # معالجة مسبقة بـ Pandas لضمان السرعة
        if not df_logs.empty:
            df_logs['action_time'] = pd.to_datetime(df_logs['action_time'])
            df_logs['hour'] = df_logs['action_time'].dt.floor('h')

        with tab_gen:
            # 1. KPIs مأخوذة من action_logs مباشرة
            counts = df_logs['action_type'].value_counts() if not df_logs.empty else pd.Series(dtype=int)
            total_links  = int(counts.get('click_link',  0))
            total_copy   = int(counts.get('copy_coupon', 0))
            total_search = int(counts.get('search',      0))

            c1, c2, c3 = st.columns(3)
            c1.metric("🖱️ إجمالي نقرات الروابط",  f"{total_links:,}")
            c2.metric("✂️ إجمالي نسخ الكوبونات",   f"{total_copy:,}")
            c3.metric("🔍 إجمالي عمليات البحث",    f"{total_search:,}")

            st.divider()

            # 2. خط زمني بالساعة (Hourly) بـ 3 خطوط متزامنة
            st.subheader("📈 الأداء بالساعة — نقرات / نسخ / بحث")
            if not df_logs.empty:
                hourly = (df_logs.groupby(['hour', 'action_type'])
                                 .size()
                                 .reset_index(name='count'))
                hourly_pivot = (hourly.pivot(index='hour', columns='action_type', values='count')
                                      .fillna(0)
                                      .rename(columns={
                                          'click_link':  'نقرات الروابط',
                                          'copy_coupon': 'نسخ الكوبونات',
                                          'search':      'عمليات البحث'
                                      }))
                for col in ['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث']:
                    if col not in hourly_pivot.columns:
                        hourly_pivot[col] = 0
                # تعبئة الساعات الخالية بصفر لإظهار التعرج الحقيقي بدل الخط المستقيم
                full_range = pd.date_range(
                    start=hourly_pivot.index.min(),
                    end=hourly_pivot.index.max(),
                    freq='h'
                )
                hourly_pivot = hourly_pivot.reindex(full_range, fill_value=0)
                st.line_chart(hourly_pivot[['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث']])
            else:
                st.info("📭 لا توجد حركات مسجّلة بعد. الرسم سيظهر فور تفاعل المستخدمين مع البوت.")

            st.download_button(
                "📥 تحميل تقرير الأداء العام",
                df_logs.drop(columns=['hour'], errors='ignore').to_csv(index=False).encode('utf-8-sig'),
                "General_Report.csv", "text/csv"
            )

        with tab_ind:
            st.subheader("🔍 البحث عن أداء متجر")
            store_options = [""] + sorted(df_m['store_id'].unique().tolist())
            search_input = st.selectbox("اختر المتجر للمعاينة:", store_options, key="search_ind")

            if search_input:
                target = df_m[df_m['store_id'] == search_input].iloc[0]
                store_logs = df_logs[df_logs['store_id'] == search_input] if not df_logs.empty else pd.DataFrame()
                sc = store_logs['action_type'].value_counts() if not store_logs.empty else pd.Series(dtype=int)
                s_clicks = int(sc.get('click_link',  0))
                s_copies = int(sc.get('copy_coupon', 0))
                s_search = int(sc.get('search',      0))

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("🖱️ نقرات الرابط",  f"{s_clicks:,}")
                k2.metric("✂️ مرات النسخ",     f"{s_copies:,}")
                k3.metric("🔍 البحث عنه",      f"{s_search:,}")
                k4.metric("الحالة",             target['is_trending'])

                df_ind_plot = pd.DataFrame({
                    'النوع':  ['نقرات الروابط', 'نسخ الكوبونات', 'عمليات البحث'],
                    'العدد':  [s_clicks, s_copies, s_search]
                })
                _fig_ind_bar = px.bar(df_ind_plot, x='النوع', y='العدد', color='النوع')
                st.plotly_chart(apply_brand_theme(_fig_ind_bar), use_container_width=True)

        with tab_trend:
            st.subheader("🔥 نظام التحكم في الترند")
            col_a, col_b = st.columns(2)

            with col_a:
                st.write("🤖 **الترند الآلي — أعلى 5 سكور (نسخ×3 + نقر×2 + بحث×1)**")
                if not df_logs.empty:
                    score_raw = (df_logs.groupby(['store_id', 'action_type'])
                                        .size()
                                        .unstack(fill_value=0)
                                        .reset_index())
                    for col in ['click_link', 'copy_coupon', 'search']:
                        if col not in score_raw.columns:
                            score_raw[col] = 0
                    score_raw['السكور'] = (score_raw['copy_coupon'] * 3 +
                                           score_raw['click_link']  * 2 +
                                           score_raw['search']      * 1)
                    score_raw = score_raw.merge(df_m[['store_id', 'name_en']], on='store_id', how='left')
                    auto_top = (score_raw[['store_id', 'name_en', 'copy_coupon', 'click_link', 'search', 'السكور']]
                                .sort_values('السكور', ascending=False)
                                .head(5)
                                .rename(columns={
                                    'store_id':    'المتجر',
                                    'name_en':     'English Name',
                                    'copy_coupon': 'نسخ (×3)',
                                    'click_link':  'نقرات (×2)',
                                    'search':      'بحث (×1)'
                                })
                                .reset_index(drop=True))
                    st.table(auto_top)
                else:
                    st.info("لا توجد بيانات كافية لحساب الترند الآلي.")

            with col_b:
                st.write("🛠️ **الترند اليدوي (تثبيت)**")
                trending_set = set(df_m[df_m['is_trending'] == 'ترند 🔥']['store_id'])
                store_list = df_m['store_id'].unique().tolist()
                store_display = [f"🔥 {s}" if s in trending_set else s for s in store_list]
                store_map = dict(zip(store_display, store_list))

                selected_display = st.selectbox("اختر متجر لتغيير حالته:", store_display)
                target_store = store_map[selected_display]
                new_status = st.radio("الحالة المطلوبة:", ["عادي", "ترند 🔥"])

                if st.button("تحديث حالة الترند"):
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE master SET is_trending = %s WHERE store_id = %s",
                        (new_status, target_store)
                    )
                    conn.commit()
                    st.success(f"✅ تم تحويل {target_store} إلى {new_status}")
                    st.rerun()

    except Exception as e:
        st.error(f"⚠️ خطأ: {e}")
    finally:
        if 'conn' in locals(): conn.close()












# ---  الصفحة الخامسة : مركز قيادة الأقسام والتاقات (إدارة الـ 10 أعمدة) ---
# --- الصفحة الخامسة: مركز قيادة الأقسام والتاقات (نظام رصد نقرات الأقسام) ---
# --- الصفحة الخامسة المحدثة: عرض الأقسام من واقع الماستر ---
# --- الصفحة الخامسة: مركز قيادة الأقسام (الربط الهندسي والتحليل الفعلي) ---
elif page == "جدول الأقسام":
    st.header("📂 مركز قيادة الأقسام (الربط الهندسي)")

    conn = None
    try:
        conn = get_conn()
        # 1. سحب البيانات (AR + EN معاً)
        query = """
            SELECT store_id,
                   COALESCE(name_en, '')        AS name_en,
                   store_tags, store_tags_en,
                   store_bio,  store_bio_en,
                   public_coupon, discount_value, affiliate_link,
                   extra_offer, extra_offer_en,
                   total_coupon_copies, total_link_clicks
            FROM master
        """
        df_raw = pd.read_sql(query, conn)

        if not df_raw.empty:
            # 2. تفجير التاقات لكلا اللغتين — كل سطر يحوي عمود "اللغة" لتمييز AR/EN
            all_rows = []
            for _, row in df_raw.iterrows():
                ar_tags = parse_tags(row.get('store_tags'))
                en_tags = parse_tags(row.get('store_tags_en'))

                base = {
                    'المتجر':              row['store_id'],
                    'Store Name (EN)':     row['name_en'],
                    'الوصف':               row['store_bio'],
                    'Description (EN)':    row.get('store_bio_en') or '',
                    'الكوبون':             row['public_coupon'],
                    'عرض إضافي':           row['extra_offer'],
                    'Extra Offer (EN)':    row.get('extra_offer_en') or '',
                    'الخصم':               row['discount_value'],
                    'الرابط':              row['affiliate_link'],
                    'نقرات_الكوبون':       row['total_coupon_copies'],
                    'نقرات_الروابط':       row['total_link_clicks'],
                    'إجمالي_التفاعل':      row['total_coupon_copies'] + row['total_link_clicks'],
                }
                for t in ar_tags:
                    if t:
                        all_rows.append({'اللغة': 'AR', 'القسم': t, **base})
                for t in en_tags:
                    if t:
                        all_rows.append({'اللغة': 'EN', 'القسم': t, **base})

            df_full = pd.DataFrame(all_rows)

            # 3. التبويبات
            tab1, tab2 = st.tabs(["📊 لوحة إدارة الأقسام", "📋 الجدول الشامل"])

            with tab1:
                st.subheader("📋 ملخص أداء الأقسام (AR / EN منفصلَين)")
                summary = (df_full.groupby(['اللغة', 'القسم']).agg(
                    عدد_المتاجر=('المتجر', 'count'),
                    نقرات_الكوبونات=('نقرات_الكوبون', 'sum'),
                    إجمالي_التفاعل=('إجمالي_التفاعل', 'sum'),
                    المتاجر_التابعة=('المتجر', lambda x: ", ".join(list(set(x))))
                ).reset_index().sort_values(by=['اللغة', 'إجمالي_التفاعل'], ascending=[True, False]))

                summary.columns = ['اللغة', 'اسم القسم', 'عدد المتاجر', 'نقرات الكوبونات', 'إجمالي التفاعل', 'المتاجر التابعة']
                st.dataframe(summary, use_container_width=True, hide_index=True)

            with tab2:
                st.subheader("🔍 استعراض الارتباطات الكاملة (AR + EN)")
                display_cols = [
                    'اللغة', 'القسم', 'المتجر', 'Store Name (EN)',
                    'الوصف', 'Description (EN)',
                    'الكوبون', 'عرض إضافي', 'Extra Offer (EN)',
                    'الخصم', 'الرابط',
                ]
                st.dataframe(df_full[display_cols], use_container_width=True, hide_index=True)

                # زر التحميل
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    summary.to_excel(writer, index=False, sheet_name='إحصائيات الأقسام')
                    df_full[display_cols].to_excel(writer, index=False, sheet_name='الارتباطات الشاملة')

                st.download_button(
                    label="📥 تحميل التقرير الشامل (Excel)",
                    data=output.getvalue(),
                    file_name="Tawfeer_Full_Analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cat_full_excel_2"
                )
        else:
            st.info("لا توجد بيانات متاجر مرتبطة بأقسام حالياً.")

    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة البيانات: {e}")
    finally:
        if conn:
            conn.close()

# --- الصفحة السادسة: تحليل الأقسام ---
elif page == "تحليل الأقسام":
    st.header("📂 مركز تحليل أداء الأقسام الذكي")
    tab_gen_cat, tab_ind_cat, tab_time_analyser, tab_priority = st.tabs([
        "🌎 الأداء العام", "🏷️ تحليل فردي", "⏰ التحليل الزمني", "🏅 الأولويات"
    ])

    try:
        conn = get_conn()
        # نجلب user_id الجديد + action_time + الربط مع master للحصول على store_tags
        cat_query = """
            SELECT m.store_tags, a.action_time, a.action_type, a.user_id
            FROM action_logs a
            JOIN master m ON a.store_id = m.store_id
            WHERE a.store_id IS NOT NULL
        """
        df_raw = pd.read_sql(cat_query, conn)
        conn.close()

        if not df_raw.empty:
            # store_tags نص بصيغة '{a,b,c}' — نحوّله لقائمة قبل التفجير
            df_raw['store_tags'] = df_raw['store_tags'].apply(parse_tags)
            df_exploded = df_raw.explode('store_tags').dropna(subset=['store_tags'])
            df_exploded['store_tags'] = df_exploded['store_tags'].astype(str).str.strip()

            # --- تبويب الأداء العام ---
            with tab_gen_cat:
                st.subheader("📊 مقارنة نشاط الأقسام")
                fig = px.sunburst(df_exploded, path=['store_tags', 'action_type'],
                                  title="توزيع الأقسام ونوع الحركة داخلها")
                st.plotly_chart(apply_brand_theme(fig), use_container_width=True)

            # --- تبويب التحليل الفردي ---
            with tab_ind_cat:
                search_tag = st.selectbox("اختر القسم للمراقبة:", sorted(df_exploded['store_tags'].unique()))
                tag_data = df_exploded[df_exploded['store_tags'] == search_tag]

                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي الحركات", len(tag_data))
                unique_users = tag_data['user_id'].dropna().nunique()
                c2.metric("👥 مستخدمون فريدون", int(unique_users))
                top_action = tag_data['action_type'].mode()[0] if not tag_data.empty else "N/A"
                c3.metric("السلوك الغالب", top_action)

            # --- تبويب التحليل الزمني ---
            with tab_time_analyser:
                st.subheader("📅 متى ينشط هذا القسم؟")
                df_exploded['hour'] = pd.to_datetime(df_exploded['action_time']).dt.hour
                time_stats = (df_exploded[df_exploded['store_tags'] == search_tag]
                              .groupby('hour').size().reset_index(name='الزيارات'))
                fig_time = px.line(time_stats, x='hour', y='الزيارات',
                                   title=f"نشاط قسم {search_tag} خلال ساعات اليوم", markers=True)
                st.plotly_chart(apply_brand_theme(fig_time), use_container_width=True)

        else:
            st.info("📭 لا توجد حركات على متاجر مسجّلة بعد. ستظهر فور ضغط روابط أو نسخ كوبونات في البوت.")
    except Exception as e:
        st.error(f"حدث خطأ فني: {e}")

    # ─── تبويب الأولويات (مستقل — يعمل حتى لو لا توجد action_logs) ───────────
    with tab_priority:
        st.subheader("🏅 إدارة ترتيب الأقسام يدوياً")
        st.caption("الرقم 1 = يظهر أولاً في البوت والموقع · الرقم 5 = الترتيب الافتراضي")

        try:
            conn_p = get_conn()
            conn_p.autocommit = True
            cur_p  = conn_p.cursor()

            # مزامنة أي تاقات جديدة من master لم تُضَف بعد
            cur_p.execute("""
                INSERT INTO categories_tags (tag_name, priority_rank)
                SELECT DISTINCT trim(tg), 5
                FROM master,
                     unnest(string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',')) AS tg
                WHERE trim(tg) <> ''
                ON CONFLICT (tag_name) DO NOTHING
            """)

            df_pr = pd.read_sql("""
                SELECT
                    tag_name                          AS "القسم",
                    priority_rank                     AS "الأولوية (1-5)",
                    COALESCE("Tag_clicks", 0)         AS "النقرات",
                    COALESCE(visit_count,  0)         AS "الزيارات"
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
                key="priority_editor",
            )

            if st.button("💾 حفظ الأولويات", type="primary", key="save_priorities"):
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
                    st.success(f"✅ تم حفظ أولويات {len(edited_pr)} قسم بنجاح!")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ فشل الحفظ: {e}")










# --- الصفحة السابعة: البحث والتحليل الشامل ---
elif page == "البحث عن كود":
    st.header("🔍 محرك البحث الذكي والتحليلات")
    
    # تبويبات الصفحة
    tab_search, tab_analytics = st.tabs(["🔎 البحث الفوري", "📊 مركز التحليل (عام/فردي)"])

    with tab_search:
        api_q = st.text_input(
            "🔎 ابحث باسم المتجر أو القسم:",
            placeholder="نمشي، إلكترونيات، عطور…",
            key="api_search_input",
        )

        if api_q:
            _q = api_q.strip()
            if len(_q) < 2:
                st.info("اكتب حرفين على الأقل للبحث.")
            else:
                _total, df_api = fetch_coupon_data(_q)

                # ── معالجة حالة السيرفر المغلق ──────────────────────────
                if _total == -1:
                    st.error(
                        "⚠️ **السيرفر غير متاح** — شغّل الـ API من Terminal:\n\n"
                        "```\nuvicorn api.main:app --reload --port 8000\n```"
                    )
                elif df_api.empty:
                    st.warning("⚠️ لا توجد نتائج — جرّب اسم المتجر بالإنجليزي أو كلمة مختلفة.")
                else:
                    # ── Metric Cards ─────────────────────────────────────
                    _best   = int(df_api['score_pct'].max())
                    _avg    = float(df_api['score_pct'].mean())
                    _shown  = len(df_api)
                    _capped = (_shown == 50)

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        kpi_card("🎟️", "إجمالي الكوبونات", _total, "emerald")
                    with mc2:
                        kpi_card("📊", "نتائج البحث", _shown, "info")
                    with mc3:
                        kpi_card("🏆", "أعلى تطابق", f"{_best}%", "warning")
                    with mc4:
                        kpi_card("📈", "متوسط التطابق", f"{_avg:.0f}%", "neutral")

                    if _capped:
                        st.caption("⚡ وصلت للحد الأقصى (50) — جرّب كلمة أدق.")

                    st.divider()

                    # ── الرسوم البيانية ───────────────────────────────────
                    ch1, ch2 = st.columns(2)

                    with ch1:
                        st.subheader("📊 توزيع النتائج حسب المتجر")
                        df_c1 = (df_api[['store_id', 'score_pct']]
                                 .sort_values('score_pct', ascending=True)
                                 .tail(15))
                        fig1 = px.bar(
                            df_c1, x='score_pct', y='store_id',
                            orientation='h',
                            color='score_pct',
                            color_continuous_scale=[
                                [0, BRAND["emerald_pastel"]],
                                [1, BRAND["emerald_dark"]],
                            ],
                            labels={'score_pct': 'نسبة التطابق %', 'store_id': 'المتجر'},
                            title=f'أفضل {len(df_c1)} متجراً لـ "{_q}"',
                        )
                        fig1.update_layout(coloraxis_showscale=False)
                        st.plotly_chart(apply_brand_theme(fig1), use_container_width=True)

                    with ch2:
                        st.subheader("💪 متوسط قوة الخصم بالقسم")
                        # store_tags قادمة من الـ API كـ list — نفجّرها مباشرةً
                        _has_tags = (
                            'store_tags' in df_api.columns
                            and df_api['store_tags'].apply(
                                lambda x: len(x) if isinstance(x, list) else 0
                            ).sum() > 0
                        )
                        if _has_tags:
                            df_te = df_api.explode('store_tags')
                            df_te = df_te[df_te['store_tags'].notna() & (df_te['store_tags'] != '')]
                            avg_tag = (df_te.groupby('store_tags')['score_pct']
                                           .mean()
                                           .reset_index()
                                           .rename(columns={'store_tags': 'القسم',
                                                            'score_pct': 'متوسط التطابق %'})
                                           .sort_values('متوسط التطابق %', ascending=False)
                                           .head(10))
                            fig2 = px.bar(
                                avg_tag, x='القسم', y='متوسط التطابق %',
                                color='متوسط التطابق %',
                                color_continuous_scale=[
                                    [0, BRAND["info_soft"]],
                                    [1, BRAND["emerald"]],
                                ],
                                title="متوسط نسبة التطابق لكل قسم",
                            )
                            fig2.update_layout(coloraxis_showscale=False)
                        else:
                            fig2 = px.histogram(
                                df_api, x='score_pct', nbins=10,
                                title="توزيع درجات التطابق",
                                labels={'score_pct': 'التطابق %', 'count': 'العدد'},
                                color_discrete_sequence=[BRAND["emerald"]],
                            )
                        st.plotly_chart(apply_brand_theme(fig2), use_container_width=True)

                    st.divider()

                    # ── بطاقات النتائج (AR + EN عرض ثنائي للـ admin) ────────
                    st.success(f"✅ {_shown} نتيجة — مرتبة بالأدق أولاً")
                    for _, row in df_api.iterrows():
                        _name_en = (row.get('name_en') or '').strip()
                        _score   = int(row.get('score_pct', 0))
                        _header  = f"{row['store_id']} | {_name_en}" if _name_en else row['store_id']
                        _badge   = f"  ({_score}% تطابق)" if _score else ""
                        _tags_ar = row.get('store_tags') or []
                        _tags_en = row.get('store_tags_en') or []

                        with st.expander(
                            f"🏬 {_header}{_badge} — كود: {row.get('public_coupon', '—')}",
                            expanded=False,
                        ):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"🔗 **الرابط:** [اضغط هنا]({row.get('affiliate_link', '#')})")
                                st.write(f"🎟️ **كود العميل:** `{row.get('public_coupon') or '—'}`")
                                st.write(f"➕ **العرض الإضافي (AR):** `{row.get('extra_offer') or '—'}`")
                                st.write(f"➕ **Extra Offer (EN):** `{row.get('extra_offer_en') or '—'}`")
                            with col2:
                                st.write(f"💰 **الخصم:** {row.get('discount_value') or '—'}")
                                st.write(f"🏷️ **الأقسام (AR):** {', '.join(_tags_ar) if _tags_ar else '—'}")
                                st.write(f"🏷️ **Tags (EN):** {', '.join(_tags_en) if _tags_en else '—'}")
                                st.write(f"📊 **نسبة التطابق:** {_score}%")
                            st.info(f"📝 **نبذة (AR):** {row.get('store_bio') or '—'}")
                            st.info(f"📝 **Description (EN):** {row.get('store_bio_en') or '—'}")

    with tab_analytics:
        st.subheader("📊 تحليلات الأداء")
        sub_tab1, sub_tab2 = st.tabs(["📈 الأداء العام", "👤 الأداء الفردي"])

        # جلب البيانات
        conn = get_conn()
        conn.rollback()
        df_all = pd.read_sql("SELECT * FROM master", conn)
        df_actions = pd.read_sql("""
            SELECT
                a.action_time,
                a.action_type,
                a.store_id,
                COALESCE(m.name_en, '') AS name_en,
                m.public_coupon,
                m.discount_value,
                COALESCE(NULLIF(b.username, ''), CAST(a.user_id AS TEXT), '—') AS username,
                a.user_id,
                COALESCE(a.details, '') AS details
            FROM action_logs a
            LEFT JOIN master m ON a.store_id = m.store_id
            LEFT JOIN bot_users b ON a.user_id = b.telegram_id
            WHERE a.action_type IN ('click_link', 'copy_coupon', 'search')
            ORDER BY a.action_time DESC
        """, conn)
        conn.close()

        if not df_actions.empty:
            df_actions['action_time'] = pd.to_datetime(df_actions['action_time'])

        with sub_tab1:
            st.markdown("### ملخص أداء المنصة كاملة")
            m1, m2, m3 = st.columns(3)
            m1.metric("إجمالي المتاجر", len(df_all))
            m2.metric("إجمالي نقرات الروابط", df_all['total_link_clicks'].sum())
            m3.metric("إجمالي عمليات النسخ", df_all['total_coupon_copies'].sum())

            if not df_all.empty:
                df_tags = df_all.copy()
                df_tags['store_tags'] = df_tags['store_tags'].apply(parse_tags)
                df_tags = df_tags.explode('store_tags').dropna(subset=['store_tags'])
                tag_counts = df_tags.groupby('store_tags')['total_coupon_copies'].sum().reset_index()
                fig = px.bar(tag_counts, x='store_tags', y='total_coupon_copies',
                             title="تفاعل العملاء حسب القسم")
                st.plotly_chart(apply_brand_theme(fig), use_container_width=True)

            # ── الجدول التفاعلي لسجل الحركات ──
            st.divider()
            st.subheader("📋 سجل حركات الكوبونات التفصيلي")

            if not df_actions.empty:
                _action_map = {
                    'click_link':  'نقر رابط',
                    'copy_coupon': 'نسخ كوبون',
                    'search':      'بحث'
                }

                # فلاتر
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    stores_list = ["الكل"] + sorted(df_actions['store_id'].dropna().unique().tolist())
                    f_store = st.selectbox("🏪 المتجر:", stores_list, key="f_store_gen")
                with fc2:
                    f_action = st.multiselect(
                        "⚡ نوع الحركة:",
                        options=list(_action_map.keys()),
                        default=list(_action_map.keys()),
                        format_func=lambda x: _action_map[x],
                        key="f_action_gen"
                    )
                with fc3:
                    _min_d = df_actions['action_time'].min().date()
                    _max_d = df_actions['action_time'].max().date()
                    f_dates = st.date_input("📅 نطاق التاريخ:", value=(_min_d, _max_d), key="f_dates_gen")

                # تطبيق الفلاتر
                df_filt = df_actions.copy()
                if f_store != "الكل":
                    df_filt = df_filt[df_filt['store_id'] == f_store]
                if f_action:
                    df_filt = df_filt[df_filt['action_type'].isin(f_action)]
                if isinstance(f_dates, (list, tuple)) and len(f_dates) == 2:
                    df_filt = df_filt[
                        (df_filt['action_time'].dt.date >= f_dates[0]) &
                        (df_filt['action_time'].dt.date <= f_dates[1])
                    ]

                # تعريب وعرض
                df_disp = df_filt.rename(columns={
                    'action_time':   'الوقت',
                    'action_type':   'نوع الحركة',
                    'store_id':      'المتجر',
                    'name_en':       'English Name',
                    'public_coupon': 'الكوبون',
                    'discount_value':'الخصم',
                    'username':      'المستخدم',
                    'user_id':       'Telegram ID',
                    'details':       'التفاصيل'
                })
                df_disp['نوع الحركة'] = df_disp['نوع الحركة'].map(_action_map).fillna(df_disp['نوع الحركة'])

                st.caption(f"🔢 عدد السجلات: **{len(df_disp):,}**")
                st.dataframe(df_disp, use_container_width=True, height=420, hide_index=True)

                _xl = BytesIO()
                with pd.ExcelWriter(_xl, engine='xlsxwriter') as _w:
                    df_disp.to_excel(_w, index=False, sheet_name='سجل_الحركات')
                st.download_button(
                    "📥 تحميل الجدول كـ Excel",
                    _xl.getvalue(),
                    "coupon_actions_report.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("📭 لا توجد حركات مسجّلة بعد.")

        with sub_tab2:
            st.markdown("### تحليل متجر محدد")
            selected_store = st.selectbox("اختر المتجر للمعاينة الفردية:", df_all['store_id'].unique())
            store_data = df_all[df_all['store_id'] == selected_store].iloc[0]

            c1, c2 = st.columns(2)
            with c1:
                fig_ind = px.pie(
                    values=[store_data['total_link_clicks'], store_data['total_coupon_copies']],
                    names=['نقرات الرابط', 'عمليات النسخ'],
                    hole=0.4, title=f"تفاعل {selected_store}"
                )
                st.plotly_chart(apply_brand_theme(fig_ind))
            with c2:
                st.write("#### تفاصيل التحويل")
                conversion = (store_data['total_coupon_copies'] / store_data['total_link_clicks'] * 100) if store_data['total_link_clicks'] > 0 else 0
                st.metric("نسبة التحويل (نسخ/نقر)", f"{conversion:.2f}%")

        st.divider()
        csv = df_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 تحميل تقرير الأداء الشامل (CSV)", csv, "performance_report.csv", "text/csv")





# --- الصفحة الثامنة: تحليل بحث الأكواد (الشاملة - النسخة الملكية النهائية) ---
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
                r.id          as "ID",
                r.user_id     as "Telegram ID",
                r.brand_name  as "طلب العميل (نص حر)",
                r.requested_at as "تاريخ الطلب",
                r.user_email  as "الإيميل",
                COALESCE(CAST(r.master_id AS TEXT), 'قيد الانتظار ⏳') as "رقم الماستر",
                COALESCE(m.store_id, '—')         as "اسم المتجر (AR)",
                COALESCE(NULLIF(m.name_en, ''), '—') as "Store Name (EN)"
            FROM unavailable_codes_requests r
            LEFT JOIN master m ON r.master_id = m.id
            ORDER BY r.requested_at DESC
        """
        req_df = pd.read_sql(query_requests, conn)

        if not req_df.empty:
            # --- كروت الإحصائيات الموحَّدة بهوية الشعار ---
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("📦", "إجمالي الطلبات", len(req_df), "info")
            with c2:
                pending = len(req_df[req_df["رقم الماستر"] == "قيد الانتظار ⏳"])
                kpi_card("⏳", "لم توفر بعد", pending, "warning")
            with c3:
                top_b = req_df["طلب العميل (نص حر)"].value_counts().idxmax()
                kpi_card("🔥", "الأكثر طلباً", top_b, "emerald")

            st.divider()

            # --- عرض الجدول الأساسي (يحتوي على الإيميل) ---
            st.write("### 📋 قائمة الطلبات الواردة (بالتفصيل)")
            st.dataframe(req_df, use_container_width=True, height=450)

            # --- أزرار التحميل (Excel) ---
            r_output = BytesIO()
            with pd.ExcelWriter(r_output, engine='xlsxwriter') as writer:
                req_df.to_excel(writer, index=False, sheet_name='Requests')
            
            st.download_button(
                label="📥 تحميل قائمة الطلبات كاملة (Excel)",
                data=r_output.getvalue(),
                file_name=f"Code_Requests_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # --- منطقة الإدارة (الربط والحذف) ---
            st.divider()
            col_manage1, col_manage2 = st.columns(2)
            
            with col_manage1:
                with st.expander("🔗 ربط طلب برقم الماستر"):
                    req_id = st.number_input("رقم طلب العميل (ID):", min_value=1, key="link_q9")
                    m_id = st.number_input("رقم الكود في الماستر:", min_value=1, key="master_q9")
                    if st.button("تحديث وحفظ الربط"):
                        cur = conn.cursor()
                        cur.execute("UPDATE unavailable_codes_requests SET master_id = %s WHERE id = %s", (m_id, req_id))
                        conn.commit()
                        st.success(f"تم ربط الطلب {req_id} بالماستر {m_id}")
                        st.rerun()

            with col_manage2:
                with st.expander("🗑️ حذف وتصفير"):
                    del_id = st.number_input("حذف ID معين:", min_value=1, key="del_q9")
                    if st.button("تأكيد الحذف"):
                        cur = conn.cursor()
                        cur.execute("DELETE FROM unavailable_codes_requests WHERE id = %s", (del_id,))
                        cur.execute("SELECT public.reset_ids('unavailable_codes_requests');")
                        conn.commit()
                        st.success("تم الحذف.")
                        st.rerun()
                    
                    if st.button("🚨 تصفير الجدول نهائياً"):
                        cur = conn.cursor()
                        cur.execute("TRUNCATE TABLE unavailable_codes_requests RESTART IDENTITY;")
                        conn.commit()
                        st.rerun()
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
        # السر هنا: تنظيف أي خطأ سابق في الجلسة الحالية
        cur = conn.cursor()
        cur.execute("ROLLBACK") 
        
        # دالة جلب الأعداد بمرونة عالية
        def get_stat(query):
            try:
                res = pd.read_sql(query, conn)
                return res.iloc[0,0] if not res.empty else 0
            except:
                return 0

        # جلب البيانات الحقيقية
        m_count = get_stat("SELECT COUNT(*) FROM master ")
        u_count = get_stat("SELECT COUNT(*) FROM bot_users")
        b_count = get_stat("SELECT COUNT(*) FROM broadcast_logs")

        # KPI: المستخدمون الخاملون (لم يدخلوا خلال 24 ساعة أو لا يوجد last_seen)
        idle_count = get_stat("""
            SELECT COUNT(*) FROM bot_users
            WHERE last_seen IS NULL OR last_seen < NOW() - INTERVAL '24 hours'
        """)

        # KPI: العملاء المستفيدون (نسخوا كوبون أو ضغطوا رابط — يعتمد على ميجريشن 001)
        beneficiaries = get_stat("""
            SELECT COUNT(DISTINCT user_id) FROM action_logs
            WHERE user_id IS NOT NULL
              AND action_type IN ('copy_coupon','click_link')
        """)

        # --- عرض العدادات ---
        st.markdown("### 📈 مؤشرات الأداء الحية")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📦 روابط الماستر", f"{m_count}")
        c2.metric("👥 المشتركين", f"{u_count}")
        c3.metric("📢 حملات مرسلة", f"{b_count}")
        c4.metric("💤 خاملون (>24س)", f"{idle_count}")
        c5.metric("🎁 المستفيدون", f"{beneficiaries}")

        st.divider()

        # --- تحليل الاهتمامات (مع معالجة احتمال عدم وجود الجدول) ---
        col_left, col_right = st.columns([1.5, 1])
        with col_left:
            st.subheader("🔥 اهتمامات الجمهور")
            try:
                df_int = pd.read_sql("SELECT interest_name as 'الهدف', COUNT(*) as 'الطلب' FROM user_interests GROUP BY interest_name ORDER BY 'الطلب' DESC LIMIT 5", conn)
                if not df_int.empty:
                    st.bar_chart(df_int.set_index('الهدف'))
                else:
                    st.info("💡 سيظهر تحليل الاهتمامات هنا فور تفاعل المستخدمين.")
            except:
                st.caption("جاري تهيئة جداول التحليل...")

        with col_right:
            st.subheader("⚙️ حالة النظام")
            with st.container(border=True):
                st.write(f"🌐 **القاعدة:** `متصلة بنجاح ✅` ")
                st.write(f"📊 **إجمالي السجلات:** `{m_count + u_count}`")
                st.success("النظام يعمل بكفاءة عالية")

        st.divider()

        # --- سجل آخر الحركات (يستخدم user_id الجديد + JOIN مع bot_users لإظهار اسم المستخدم) ---
        st.subheader("📜 سجل آخر الحركات")
        try:
            recent_logs_query = """
                SELECT
                    TO_CHAR(a.action_time, 'YYYY-MM-DD HH24:MI:SS') AS "الوقت",
                    a.action_type AS "الحركة",
                    COALESCE(a.store_id, '—') AS "المتجر",
                    COALESCE(m.name_en, '') AS "English Name",
                    COALESCE(NULLIF(b.username, ''), '— مجهول —') AS "المستخدم",
                    a.user_id AS "Telegram ID",
                    COALESCE(a.details, '') AS "التفاصيل"
                FROM action_logs a
                LEFT JOIN bot_users b ON a.user_id = b.telegram_id
                LEFT JOIN master m ON a.store_id = m.store_id
                ORDER BY a.action_time DESC
                LIMIT 20
            """
            df_logs = pd.read_sql(recent_logs_query, conn)
            if not df_logs.empty:
                st.dataframe(df_logs, use_container_width=True, hide_index=True, height=420)
                st.caption(f"🕒 يعرض آخر {len(df_logs)} حركة. كل صف مرتبط باسم المستخدم تلقائياً.")
            else:
                st.info("📭 لا توجد حركات مسجّلة بعد. ستظهر فور تفاعل المستخدمين مع البوت.")
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
                st.write("📊 منحنى النشاط المتوقع لليوم القادم:")
                # استخدام np.random بعد استيراد المكتبة
                st.line_chart(np.random.randn(24, 1)) 

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
            status_data = pd.DataFrame(np.random.randint(95, 100, size=(10, 1)), columns=['استقرار النظام'])
            st.line_chart(status_data)
            st.write("✅ **حالة الذكاء:** مستقر")


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
