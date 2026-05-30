import os
import sys
import threading
import time
from io import BytesIO

# على ويندوز بـ locale عربي (cp1256) تفشل طباعة الإيموجي وتُسقط البوت عند أول print.
# نفرض UTF-8 على stdout/stderr حتى يعمل التشغيل المحلي بأي طرفية.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import requests
import telebot
from telebot import types
import psycopg2
from psycopg2 import extras, pool as pg_pool
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# تحميل المتغيرات من ملف .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN/TELEGRAM_BOT_TOKEN غير موجود في متغيرات البيئة")

_DATABASE_URL = os.getenv("DATABASE_URL")
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# ── Unified API endpoint ─────────────────────────────────────────────────
# Source of Truth واحد: نفس الـ API الذي يخدم الموقع والـ Mini App.
# في الإنتاج، البوت يقرأ كوبوناته من PostgreSQL مباشرة (أسرع)، لكن البحث
# الذكي (trigram similarity) يمر عبر /coupons/search — لذا نضمن أن المسار
# الافتراضي يشير للإنتاج الموحَّد، وليس localhost.
# التطوير المحلي يضع API_BASE_URL=http://127.0.0.1:8000 في .env
_API_BASE = os.getenv("API_BASE_URL", "https://api.dealpulseksa.com").rstrip("/")

# دومين تحويل /go (يجب أن يكون خلف Cloudflare Worker لالتقاط الـ geo/IP).
# نفضّل WEBHOOK_BASE_URL (نفس host الذي يخدم /go والميني-ويب)، ثم API_BASE.
_GO_BASE = (os.getenv("GO_BASE_URL") or os.getenv("WEBHOOK_BASE_URL") or _API_BASE).rstrip("/")
if _GO_BASE and not _GO_BASE.startswith("http"):
    _GO_BASE = "https://" + _GO_BASE
_API_SEARCH_URL = _API_BASE + "/api/v1/coupons/search"

# إعدادات مراقب الخمول — مرحلتان (قابلة للتعديل من .env)
IDLE_WARN_MINUTES           = int(os.getenv("IDLE_WARN_MINUTES",  "5"))   # تذكير
IDLE_KICK_MINUTES           = int(os.getenv("IDLE_KICK_MINUTES",  "10"))  # إنهاء جلسة
IDLE_CHECK_INTERVAL_SECONDS = 30       # دورة الفحص كل 30 ثانية
IDLE_ALERT_WINDOW_HOURS     = 24       # لا ننبّه من اختفى أكثر من 24 ساعة

# تتبع المرحلتين في الذاكرة
_idle_warned = set()   # أُرسل لهم التذكير (5 دقائق)
_idle_kicked = set()   # أُنهيت جلستهم  (10 دقائق)
_idle_lock   = threading.Lock()

bot = telebot.TeleBot(TOKEN)


def _build_pool() -> pg_pool.ThreadedConnectionPool:
    if _DATABASE_URL:
        url = _DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return pg_pool.ThreadedConnectionPool(minconn=2, maxconn=8, dsn=url)
    return pg_pool.ThreadedConnectionPool(minconn=2, maxconn=8, **DB_CONFIG)

_db_pool: pg_pool.ThreadedConnectionPool | None = None
_db_pool_lock = threading.Lock()

# ─── Cache للأقسام (يتجدد كل 5 دقائق فقط بدل DB في كل ضغطة) ─────────────
_cats_cache: dict[str, tuple[float, list]] = {}   # lang → (timestamp, tags)
_CATS_TTL = 300                                    # 5 دقائق

def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _db_pool
    if _db_pool is None:
        with _db_pool_lock:
            if _db_pool is None:
                _db_pool = _build_pool()
    return _db_pool

def get_db_connection():
    """يُعيد connection من الـ pool — أسرع بكثير من فتح TCP جديد في كل مرة."""
    conn = _get_pool().getconn()
    conn.autocommit = False
    return conn

def release_conn(conn):
    """يُعيد الـ connection للـ pool بدل إغلاقه."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


# ============================================================
#  Schema setup — يُنفَّذ مرة عند بدء البوت
# ============================================================

def clean_legacy_columns():
    """حذف الأعمدة الثلاثة التي قرّر المستخدم إلغاءها نهائياً."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            ALTER TABLE bot_users
              DROP COLUMN IF EXISTS social_rank,
              DROP COLUMN IF EXISTS emotional_score,
              DROP COLUMN IF EXISTS birth_date
        """)
        conn.commit()
        release_conn(conn)
        print("✅ Schema cleanup: dropped social_rank, emotional_score, birth_date")
    except Exception as e:
        print(f"⚠️ clean_legacy_columns: {e}")


def ensure_tracking_tables():
    """جدول ربط رسائل الكوبونات بالـ store_id + عمود lang للـ i18n.
    أيضاً يُهيّئ seo_opportunity_keywords (محرك الفرص — Google Trends)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sent_coupon_messages (
                chat_id    BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                store_id   TEXT   NOT NULL,
                user_id    BIGINT,
                sent_at    TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (chat_id, message_id)
            )
        """)
        cur.execute("""
            ALTER TABLE bot_users
              ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'ar'
        """)
        cur.execute("""
            ALTER TABLE master
              ADD COLUMN IF NOT EXISTS name_en TEXT
        """)
        # migration_020 — محرك الفرص (Google Trends + keyword CRUD)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seo_opportunity_keywords (
                id                  BIGSERIAL PRIMARY KEY,
                keyword             TEXT NOT NULL UNIQUE,
                store_id            TEXT,
                notes               TEXT,
                active              BOOLEAN DEFAULT TRUE,
                trend_score         INTEGER DEFAULT 0,
                trend_avg           NUMERIC(6, 2) DEFAULT 0,
                rising_pct          NUMERIC(8, 2) DEFAULT 0,
                last_checked_at     TIMESTAMPTZ,
                last_error          TEXT,
                generated_page_id   BIGINT,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # migration_021 — أعمدة related queries + peak (idempotent عبر IF NOT EXISTS)
        cur.execute("""
            ALTER TABLE seo_opportunity_keywords
              ADD COLUMN IF NOT EXISTS trend_peak     INTEGER DEFAULT 0,
              ADD COLUMN IF NOT EXISTS related_top    JSONB   DEFAULT '[]'::jsonb,
              ADD COLUMN IF NOT EXISTS related_rising JSONB   DEFAULT '[]'::jsonb
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_seo_opp_active_score
                ON seo_opportunity_keywords (active, trend_score DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_seo_opp_store
                ON seo_opportunity_keywords (store_id)
                WHERE store_id IS NOT NULL
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_seo_opp_last_checked
                ON seo_opportunity_keywords (last_checked_at NULLS FIRST)
        """)
        conn.commit()
        release_conn(conn)
        print("✅ Tracking tables ready (sent_coupon_messages, lang, seo_opportunity_keywords)")
    except Exception as e:
        print(f"⚠️ ensure_tracking_tables: {e}")


# ============================================================
#  طبقة الـ Tracking (الإحياء الكامل لجداول التحليل)
# ============================================================


def register_or_update_user(message):
    """UPSERT في bot_users — تُستدعى في بداية كل handler.

    لا نضبط country/city تلقائياً من language_code — نتركهما NULL
    ليُكمَّلا عبر زر اللغة في onboarding (لتفادي بيانات تخمينية).
    device_type يُستنتج تخميناً من is_premium لأن Telegram لا يكشفه."""
    user = message.from_user

    with _idle_lock:
        _idle_warned.discard(user.id)
        _idle_kicked.discard(user.id)

    # Telegram لا يكشف نوع الجهاز — نسجّل 'Telegram' كقيمة محايدة صادقة
    inferred_device = 'Telegram'

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bot_users (telegram_id, username, joined_at, last_seen,
                                   device_type, user_status)
            VALUES (%s, %s, NOW(), NOW(), %s, 'Active')
            ON CONFLICT (telegram_id) DO UPDATE
                SET username    = EXCLUDED.username,
                    last_seen   = NOW(),
                    device_type = COALESCE(bot_users.device_type, EXCLUDED.device_type),
                    user_status = 'Active'
        """, (user.id, user.username or user.first_name or "Anonymous",
              inferred_device))
        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ فشل تسجيل المستخدم {user.id}: {e}")


def needs_onboarding(user_id):
    """هل يحتاج المستخدم لملء country/city/lang عبر زر اللغة؟"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT country, city,
                   EXISTS(SELECT 1 FROM action_logs WHERE user_id=%s AND action_type='lang_pick')
            FROM bot_users WHERE telegram_id = %s
        """, (user_id, user_id))
        row = cur.fetchone()
        release_conn(conn)
        if not row:
            return True
        country, city, has_picked_lang = row
        return not country or not city or not has_picked_lang
    except Exception as e:
        print(f"⚠️ needs_onboarding {user_id}: {e}")
        return False


# ============================================================
#  i18n — قاموس النصوص + cache للغة المستخدم
# ============================================================

TEXTS = {
    # Onboarding
    'lang_picker_msg':   {'ar': '👋 أهلاً بك!\nاختر لغتك:',
                          'en': '👋 Welcome!\nChoose your language:'},
    'lang_ar_picked':    {'ar': '✅ تم اختيار اللغة العربية',
                          'en': '✅ تم اختيار اللغة العربية'},
    'lang_en_picked':    {'ar': '✅ English language selected',
                          'en': '✅ English language selected'},
    'welcome':           {'ar': 'مرحباً بك في نبض الصفقات يا أبو سعود 🛡️',
                          'en': 'Welcome to Deal Pulse 🛡️'},

    # Main menu buttons
    'menu_codes':        {'ar': '📜 أكوادنا',          'en': '📜 Our Codes'},
    'menu_categories':   {'ar': '📂 الأقسام',          'en': '📂 Categories'},
    'menu_search':       {'ar': '🔎 البحث عن كود',     'en': '🔎 Search Code'},
    'menu_request':      {'ar': '➕ طلب كود',          'en': '➕ Request Code'},
    'menu_end':          {'ar': '🛑 إنهاء',            'en': '🛑 End'},
    'start_btn':         {'ar': 'بدء الاستخدام 🚀',    'en': 'Start 🚀'},
    'back_btn':          {'ar': '🔙 عودة',             'en': '🔙 Back'},

    # Status / responses
    'no_codes':          {'ar': 'لا توجد أكواد حالياً في الداتابيز.',
                          'en': 'No codes available right now.'},
    'tech_error':        {'ar': '⚠️ حصل خلل تقني. حاول مرة ثانية بعد لحظات.',
                          'en': '⚠️ Technical issue. Please try again shortly.'},
    'pick_section':      {'ar': '📂 اختر القسم:',     'en': '📂 Choose a category:'},
    'no_sections':       {'ar': '❌ ما لقينا أقسام مسجّلة حالياً.',
                          'en': '❌ No categories registered yet.'},
    'sections_load_err': {'ar': '⚠️ تعذّر تحميل الأقسام. حاول لاحقاً.',
                          'en': '⚠️ Could not load categories. Try again later.'},
    'search_prompt':     {'ar': '🔎 أرسل اسم المتجر:', 'en': '🔎 Send the store name:'},
    'no_results':        {'ar': '❌ لم نجد نتائج.',     'en': '❌ No results found.'},
    'search_err':        {'ar': '⚠️ حصل خلل في البحث. حاول مرة ثانية.',
                          'en': '⚠️ Search error. Please try again.'},
    'session_ended':     {'ar': '🛑 تم إنهاء الجلسة. خذ قسطاً من الراحة يا أبو سعود!\n'
                                'اضغط الزر أسفل لما تجهز نبدأ من جديد 👇',
                          'en': '🛑 Session ended. Take a break!\n'
                                'Tap the button below when you are ready to continue 👇'},
    'request_prompt':    {'ar': '📝 اكتب اسم المتجر أو رابطه اللي تبي كوبونه، وحنا بنحاول نوفّره.',
                          'en': '📝 Type the store name or link you want a coupon for, and we will try to provide it.'},
    'request_empty':     {'ar': '⚠️ ما استلمت اسم المتجر. جرّب مرة ثانية.',
                          'en': '⚠️ No store name received. Please try again.'},
    'request_saved':     {'ar': '✅ تم تسجيل طلبك يا بطل، وبنحاول نوفر الكود في أسرع وقت!',
                          'en': '✅ Your request has been saved! We will try to provide the code soon.'},
    'request_err':       {'ar': '⚠️ تعذّر تسجيل الطلب الآن. حاول مرة ثانية.',
                          'en': '⚠️ Could not save the request now. Please try again.'},
    'back_msg':          {'ar': '🏠 رجعناك للقائمة الرئيسية.',
                          'en': '🏠 Back to the main menu.'},
    'tag_header':        {'ar': '📂 متاجر قسم: *{tag}*',
                          'en': '📂 Stores in category: *{tag}*'},
    'no_stores_in_tag':  {'ar': "❌ ما لقينا متاجر في قسم '{tag}' حالياً.",
                          'en': "❌ No stores in '{tag}' category yet."},
    'tag_load_err':      {'ar': '⚠️ تعذّر عرض المتاجر. حاول لاحقاً.',
                          'en': '⚠️ Could not load stores. Try later.'},
    'fallback':          {'ar': '🤔 ما فهمت طلبك. اختر من القائمة:',
                          'en': "🤔 I didn't get that. Pick from the menu:"},

    # Store card
    'btn_get_link':      {'ar': '🔗 احصل على الرابط',  'en': '🔗 Get the link'},
    'btn_copied_coupon': {'ar': '📋 نسخت الكوبون',     'en': '📋 Copied the coupon'},
    'card_store':        {'ar': '🏪 *متجر:*',          'en': '🏪 *Store:*'},
    'card_discount':     {'ar': '💰 *الخصم:*',         'en': '💰 *Discount:*'},
    'card_extra':        {'ar': '🎁 *عرض إضافي:*',    'en': '🎁 *Extra offer:*'},
    'card_react_hint':   {'ar': '_أعجبك العرض؟ تفاعل بـ ❤️ ليُضاف لمفضلتك_',
                          'en': '_Like this offer? React with ❤️ to add it to your favorites_'},

    # Callback responses
    'link_here':         {'ar': '✨ تفضل الرابط:',     'en': '✨ Here is the link:'},
    'open_store':        {'ar': '🌐 فتح متجر {sid}',   'en': '🌐 Open store {sid}'},
    'visit_logged':      {'ar': '✅ تم تسجيل زيارتك!', 'en': '✅ Visit logged!'},
    'link_unavailable':  {'ar': '⚠️ الرابط غير متوفر حالياً',
                          'en': '⚠️ Link not available right now'},
    'link_err':          {'ar': '⚠️ تعذر جلب الرابط', 'en': '⚠️ Could not fetch the link'},
    'coupon_here':       {'ar': '✅ تفضل الكوبون! انسخه من الرسالة.',
                          'en': '✅ Coupon ready! Copy it from the message.'},
    'coupon_unavailable':{'ar': '⚠️ الكوبون غير متوفر حالياً.',
                          'en': '⚠️ Coupon not available right now.'},
    'coupon_err':        {'ar': '⚠️ تعذر جلب الكوبون.',
                          'en': '⚠️ Could not fetch the coupon.'},
    'coupon_for':        {'ar': '🎫 *كوبون {sid}:*\n`{c}`\n\n_اضغط زر النسخ تحت ↓_',
                          'en': '🎫 *Coupon for {sid}:*\n`{c}`\n\n_Tap the copy button below ↓_'},

    # Reaction
    'fav_added':         {'ar': '❤️ تمت إضافة *{sid}* لمفضلتك',
                          'en': '❤️ Added *{sid}* to your favorites'},

    # Idle — مرحلة 1: تذكير
    'idle_warn':         {'ar': '⏰ غبت عنّا {m} دقائق...\n'
                                'هل ما زلت معنا؟ لو نعم اضغط أي زر 😊\n'
                                '_ستنتهي جلستك تلقائياً بعد {k} دقائق إضافية._',
                          'en': '⏰ You have been away for {m} minutes...\n'
                                'Still there? Tap any button 😊\n'
                                '_Session will end in {k} more minutes._'},
    # Idle — مرحلة 2: إنهاء جلسة تلقائي
    'idle_alert':        {'ar': '🛑 انتهت جلستك تلقائياً بسبب الخمول.\n'
                                'اضغط الزر لما تجهز نبدأ من جديد 👇',
                          'en': '🛑 Your session ended automatically due to inactivity.\n'
                                'Tap the button when you are ready 👇'},
}


_lang_cache: dict[int, tuple[str, float]] = {}   # user_id → (lang, timestamp)
_lang_cache_lock = threading.Lock()
_LANG_CACHE_TTL  = 300   # 5 دقائق — بعدها يُعاد جلب اللغة من DB


def get_lang(user_id):
    """يُرجع لغة المستخدم ('ar' أو 'en') مع cache يتجدد كل 5 دقائق."""
    if user_id is None:
        return 'ar'
    now = time.time()
    with _lang_cache_lock:
        entry = _lang_cache.get(user_id)
        if entry and now - entry[1] < _LANG_CACHE_TTL:
            return entry[0]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT lang FROM bot_users WHERE telegram_id = %s", (user_id,))
        row = cur.fetchone()
        release_conn(conn)
        lang = (row[0] if row and row[0] else 'ar')
    except Exception:
        lang = 'ar'
    with _lang_cache_lock:
        _lang_cache[user_id] = (lang, time.time())
    return lang


def invalidate_lang_cache(user_id):
    with _lang_cache_lock:
        _lang_cache.pop(user_id, None)


def t(user_id, key, **kwargs):
    """ترجمة مفتاح حسب لغة المستخدم. يقبل {placeholders} عبر kwargs."""
    entry = TEXTS.get(key, {})
    lang = get_lang(user_id) if user_id else 'ar'
    s = entry.get(lang) or entry.get('ar') or key
    return s.format(**kwargs) if kwargs else s


def matches_label(text, key):
    """هل النص يطابق زر مُعرَّف بأي من اللغتين؟"""
    if not text:
        return False
    entry = TEXTS.get(key, {})
    return text in (entry.get('ar'), entry.get('en'))


def log_action(store_id, action_type, user_id=None, details=None):
    """إدراج صف في action_logs — مع user_id منفصل (بعد ميجريشن 001)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO action_logs (store_id, action_type, user_id, details, action_time)
            VALUES (%s, %s, %s, %s, NOW())
        """, (store_id, action_type, user_id, details))
        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ فشل تسجيل action_log [{action_type}]: {e}")


def increment_link_clicks(store_id):
    """زيادة total_link_clicks في master."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE master
            SET total_link_clicks = COALESCE(total_link_clicks, 0) + 1
            WHERE store_id = %s
        """, (store_id,))
        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ فشل تحديث نقرات الرابط لـ {store_id}: {e}")


def increment_coupon_copies(store_id):
    """زيادة total_coupon_copies في master."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE master
            SET total_coupon_copies = COALESCE(total_coupon_copies, 0) + 1
            WHERE store_id = %s
        """, (store_id,))
        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ فشل تحديث نسخ الكوبون لـ {store_id}: {e}")


def log_search(keyword, found, user_id=None):
    """تسجيل عملية بحث في direct_search لتغذية صفحة 'تحليل بحث الأكواد'."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO direct_search (search_keyword, user_found, search_date, platform, user_id)
            VALUES (%s, %s, NOW(), 'TelegramBot', %s)
        """, (keyword, found, user_id))
        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ فشل تسجيل البحث '{keyword}': {e}")


def _loyalty_rank(total_actions):
    if total_actions >= 50:
        return 'VIP 👑'
    if total_actions >= 20:
        return 'مميز ⭐'
    if total_actions >= 5:
        return 'نشط 🟢'
    return 'مبتدئ'


def _compute_segment(cur, user_id):
    """شريحة تسويقية محسوبة من تفاعل المستخدم الفعلي:
       - مخلص 💎: تفاعل في 4 أيام مختلفة على الأقل خلال آخر 7 أيام.
       - صياد عروض 🎯: نسخ كوبونات ≥ 3، والنسخ ≥ النقرات.
       - متصفح 👀: الباقي."""
    cur.execute("""
        SELECT COUNT(DISTINCT DATE(action_time))::int FROM action_logs
        WHERE user_id = %s AND action_time >= NOW() - INTERVAL '7 days'
    """, (user_id,))
    active_days = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT
          COALESCE(SUM((action_type='copy_coupon')::int), 0)::int AS copies,
          COALESCE(SUM((action_type='click_link')::int), 0)::int  AS clicks
        FROM action_logs WHERE user_id = %s
    """, (user_id,))
    copies, clicks = cur.fetchone()

    if active_days >= 4:
        return 'مخلص 💎'
    if copies >= 3 and copies >= clicks:
        return 'صياد عروض 🎯'
    return 'متصفح 👀'


def update_user_behavior(user_id, action_type, store_id=None, tag=None):
    """تحديث إحصائيات السلوك في bot_users فوراً بعد كل تفاعل حقيقي."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if action_type == 'copy_coupon' and store_id:
            cur.execute("""
                SELECT store_id FROM action_logs
                WHERE user_id = %s AND action_type = 'copy_coupon' AND store_id IS NOT NULL
                GROUP BY store_id ORDER BY COUNT(*) DESC LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            fav = row[0] if row else store_id
            cur.execute("""
                UPDATE bot_users
                SET store_copy_count       = COALESCE(store_copy_count, 0) + 1,
                    fav_store_inferred     = %s,
                    copied_coupons_history = CASE
                        WHEN copied_coupons_history IS NULL        THEN ARRAY[%s]::text[]
                        WHEN NOT (%s = ANY(copied_coupons_history)) THEN copied_coupons_history || ARRAY[%s]::text[]
                        ELSE copied_coupons_history
                    END
                WHERE telegram_id = %s
            """, (fav, store_id, store_id, store_id, user_id))

        elif action_type == 'click_link':
            cur.execute("""
                UPDATE bot_users SET visited_clicks = COALESCE(visited_clicks, 0) + 1
                WHERE telegram_id = %s
            """, (user_id,))

        elif action_type == 'view_tag' and tag:
            cur.execute("""
                SELECT details FROM action_logs
                WHERE user_id = %s AND action_type = 'view_tag' AND details IS NOT NULL
                GROUP BY details ORDER BY COUNT(*) DESC LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            fav_tag = row[0].split('tag:')[-1] if row else tag
            cur.execute("""
                UPDATE bot_users
                SET tag_visit_count  = COALESCE(tag_visit_count, 0) + 1,
                    fav_tag_inferred = %s
                WHERE telegram_id = %s
            """, (fav_tag, user_id))

        # تحديث رتبة الولاء + الشريحة التسويقية بعد كل تفاعل
        cur.execute("""
            SELECT COUNT(*) FROM action_logs
            WHERE user_id = %s
              AND action_type IN ('click_link','copy_coupon','search','view_tag')
        """, (user_id,))
        rank = _loyalty_rank(cur.fetchone()[0])
        segment = _compute_segment(cur, user_id)
        cur.execute("""
            UPDATE bot_users
            SET loyalty_rank      = %s,
                marketing_segment = %s
            WHERE telegram_id = %s
        """, (rank, segment, user_id))

        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ update_user_behavior [{action_type}] user={user_id}: {e}")


def backfill_user_behavior():
    """تعبئة إحصائيات bot_users من action_logs الموجودة — تُشغَّل مرة عند البدء."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT user_id FROM action_logs WHERE user_id IS NOT NULL")
        user_ids = [r[0] for r in cur.fetchall()]
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ backfill query error: {e}")
        return

    for uid in user_ids:
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT COUNT(*) FROM action_logs WHERE user_id=%s AND action_type='copy_coupon'
            """, (uid,))
            copy_count = cur.fetchone()[0]

            cur.execute("""
                SELECT store_id FROM action_logs
                WHERE user_id=%s AND store_id IS NOT NULL
                  AND action_type IN ('copy_coupon','click_link')
                GROUP BY store_id ORDER BY COUNT(*) DESC LIMIT 1
            """, (uid,))
            row = cur.fetchone()
            fav_store = row[0] if row else None

            cur.execute("""
                SELECT DISTINCT store_id FROM action_logs
                WHERE user_id=%s AND action_type='copy_coupon' AND store_id IS NOT NULL
            """, (uid,))
            copied_stores = [r[0] for r in cur.fetchall()] or None

            cur.execute("""
                SELECT COUNT(*) FROM action_logs WHERE user_id=%s AND action_type='click_link'
            """, (uid,))
            link_clicks = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM action_logs WHERE user_id=%s AND action_type='view_tag'
            """, (uid,))
            tag_visits = cur.fetchone()[0]

            cur.execute("""
                SELECT details FROM action_logs
                WHERE user_id=%s AND action_type='view_tag' AND details IS NOT NULL
                GROUP BY details ORDER BY COUNT(*) DESC LIMIT 1
            """, (uid,))
            row = cur.fetchone()
            fav_tag = row[0].split('tag:')[-1] if row else None

            cur.execute("""
                SELECT COUNT(*) FROM action_logs
                WHERE user_id=%s AND action_type IN ('click_link','copy_coupon','search','view_tag')
            """, (uid,))
            rank = _loyalty_rank(cur.fetchone()[0])
            segment = _compute_segment(cur, uid)

            cur.execute("""
                UPDATE bot_users
                SET store_copy_count       = %s,
                    fav_store_inferred     = COALESCE(fav_store_inferred, %s),
                    visited_clicks         = %s,
                    tag_visit_count        = %s,
                    fav_tag_inferred       = COALESCE(fav_tag_inferred, %s),
                    loyalty_rank           = %s,
                    marketing_segment      = %s,
                    copied_coupons_history = COALESCE(copied_coupons_history, %s),
                    device_type            = COALESCE(device_type, 'غير محدد'),
                    user_status            = COALESCE(user_status, 'Active')
                WHERE telegram_id = %s
            """, (copy_count, fav_store, link_clicks, tag_visits,
                  fav_tag, rank, segment, copied_stores, uid))
            conn.commit()
            release_conn(conn)
        except Exception as e:
            print(f"⚠️ backfill user {uid}: {e}")

    print(f"✅ Backfill اكتمل: {len(user_ids)} مستخدم")


# ============================================================
#  Navigation State — رسالة واحدة لكل مستخدم (in-memory)
# ============================================================

_user_nav      = {}
_user_nav_lock = threading.Lock()


def _get_nav(user_id):
    with _user_nav_lock:
        return dict(_user_nav.get(user_id, {}))


def _set_nav(user_id, data):
    with _user_nav_lock:
        _user_nav[user_id] = data


def _update_nav(user_id, **kwargs):
    with _user_nav_lock:
        _user_nav.setdefault(user_id, {}).update(kwargs)


# ============================================================
#  Keyboard Builders (Inline فقط — لا ReplyKeyboard)
# ============================================================

def _kb_main(lang):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(TEXTS['menu_codes'][lang],      callback_data='nav:codes'),
        types.InlineKeyboardButton(TEXTS['menu_categories'][lang], callback_data='nav:cats'),
    )
    kb.add(
        types.InlineKeyboardButton(TEXTS['menu_search'][lang],  callback_data='nav:search'),
        types.InlineKeyboardButton(TEXTS['menu_request'][lang], callback_data='nav:request'),
    )
    kb.add(types.InlineKeyboardButton(TEXTS['menu_end'][lang], callback_data='nav:end'))
    return kb


def _kb_cats(lang, tags):
    kb = types.InlineKeyboardMarkup(row_width=2)
    for tag in tags:
        kb.add(types.InlineKeyboardButton(f"🏷️ {tag}", callback_data=f"ntag:{tag[:50]}"))
    kb.add(types.InlineKeyboardButton(TEXTS['back_btn'][lang], callback_data='nav:menu'))
    return kb


def _kb_card(lang, store, page, total, source):
    kb  = types.InlineKeyboardMarkup(row_width=2)
    sid = store['store_id']
    kb.add(
        types.InlineKeyboardButton(TEXTS['btn_get_link'][lang],      callback_data=f"link:{sid}"),
        types.InlineKeyboardButton(TEXTS['btn_copied_coupon'][lang], callback_data=f"copy:{sid}"),
    )
    dot       = " "
    prev_btn  = (types.InlineKeyboardButton("◀", callback_data='nav:prev')
                 if page > 0 else types.InlineKeyboardButton(dot, callback_data='nav:noop'))
    count_btn =  types.InlineKeyboardButton(f"{page + 1}/{total}", callback_data='nav:noop')
    next_btn  = (types.InlineKeyboardButton("▶", callback_data='nav:next')
                 if page < total - 1 else types.InlineKeyboardButton(dot, callback_data='nav:noop'))
    kb.row(prev_btn, count_btn, next_btn)
    back_cb = 'nav:cats' if source == 'tag' else 'nav:menu'
    kb.add(types.InlineKeyboardButton(TEXTS['back_btn'][lang], callback_data=back_cb))
    return kb


def _kb_start(lang):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(TEXTS['start_btn'][lang], callback_data='nav:menu'))
    return kb


def _kb_cancel(lang):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(TEXTS['back_btn'][lang], callback_data='nav:menu'))
    return kb


def _kb_coupon_back(lang):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(TEXTS['back_btn'][lang], callback_data='nav:card'))
    return kb


# ============================================================
#  Nav Message Helpers
# ============================================================

def _edit_nav(user_id, text, markup):
    """تعديل رسالة التنقل المحفوظة. يُرجع True عند النجاح."""
    nav = _get_nav(user_id)
    if not nav.get('msg_id'):
        return False

    # لو الرسالة الحالية صورة، نحذفها ونُرسل نص جديد
    if nav.get('msg_type') == 'photo':
        try:
            bot.delete_message(nav['chat_id'], nav['msg_id'])
        except Exception:
            pass
        _update_nav(user_id, msg_id=None, msg_type='text')
        try:
            sent = bot.send_message(nav['chat_id'], text, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            sent = bot.send_message(nav['chat_id'], text, reply_markup=markup)
        _update_nav(user_id, msg_id=sent.message_id, msg_type='text')
        return True

    try:
        bot.edit_message_text(
            text, nav['chat_id'], nav['msg_id'],
            reply_markup=markup, parse_mode="Markdown"
        )
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" not in err:
            print(f"⚠️ _edit_nav user={user_id}: {e}")
        return "message is not modified" in err


def _ensure_nav(chat_id, user_id, text, markup):
    """يعدّل رسالة التنقل إن وُجدت، وإلا يُرسل واحدة جديدة.

    يحتوي على fallback: لو فشل Markdown parsing (بسبب emoji أو أحرف خاصة)،
    نُعيد المحاولة بدون parse_mode حتى لا تختفي رسالة الأزرار.
    """
    nav = _get_nav(user_id)
    if nav.get('msg_id') and nav.get('chat_id') == chat_id:
        try:
            bot.edit_message_text(
                text, chat_id, nav['msg_id'],
                reply_markup=markup, parse_mode="Markdown"
            )
            return nav['msg_id']
        except Exception as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return nav['msg_id']
            if "can't parse" in err or "parse_mode" in err:
                # Markdown فشل → نُحاول بدونه
                try:
                    bot.edit_message_text(
                        text, chat_id, nav['msg_id'], reply_markup=markup
                    )
                    return nav['msg_id']
                except Exception:
                    pass
            # أي خطأ آخر → نسقط للإرسال الجديد بالأسفل

    try:
        sent = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"⚠️ _ensure_nav send_message Markdown failed: {e}")
        # fallback بدون parse_mode — الأزرار أهم من التنسيق
        sent = bot.send_message(chat_id, text, reply_markup=markup)
    _update_nav(user_id, chat_id=chat_id, msg_id=sent.message_id, msg_type='text')
    return sent.message_id


def _edit_nav_photo(user_id, photo_url, caption, markup):
    """يعرض أو يحدّث كارت المتجر كرسالة صورة (send_photo / edit_message_media)."""
    nav     = _get_nav(user_id)
    chat_id = nav.get('chat_id')
    msg_id  = nav.get('msg_id')

    # لو الرسالة الحالية صورة → عدّل فقط (أسرع وأنظف)
    if msg_id and nav.get('msg_type') == 'photo':
        try:
            bot.edit_message_media(
                types.InputMediaPhoto(photo_url, caption=caption, parse_mode="Markdown"),
                chat_id, msg_id, reply_markup=markup
            )
            return
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return
            # أي خطأ آخر → نسقط لإرسال جديد

    # احذف الرسالة القديمة (نص أو صورة فاشلة) قبل الإرسال الجديد
    if msg_id and chat_id:
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

    try:
        sent = bot.send_photo(
            chat_id, photo_url,
            caption=caption, reply_markup=markup, parse_mode="Markdown"
        )
        _update_nav(user_id, chat_id=chat_id, msg_id=sent.message_id, msg_type='photo')
    except Exception as e:
        print(f"⚠️ _edit_nav_photo send_photo failed: {e} — falling back to text")
        try:
            sent = bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            sent = bot.send_message(chat_id, caption, reply_markup=markup)
        _update_nav(user_id, chat_id=chat_id, msg_id=sent.message_id, msg_type='text')


# ============================================================
#  Card Text + عرض المتاجر المرقّم
# ============================================================

def _card_text(s, lang):
    """
    يبني نص الكارت حسب اللغة.
    لكل حقل: لو EN معبّأ نُظهره، وإلا نرجع للعربي (Fallback).
    يعمل سواء `s` جاي من DB (يحوي *_en raw) أو من API (مُستبدل).
    """
    trend_emoji = " 🔥" if s.get('is_trending') == 'ترند 🔥' else ""

    if lang == "en":
        store_name  = (s.get('name_en') or '').strip() or s.get('store_id', '')
        bio         = (s.get('store_bio_en') or '').strip() or (s.get('store_bio') or '')
        offer_value = (s.get('extra_offer_en') or '').strip() or (s.get('extra_offer') or '')
    else:
        store_name  = s.get('store_id', '')
        bio         = s.get('store_bio') or ''
        offer_value = s.get('extra_offer') or ''

    extra_line = f"\n{TEXTS['card_extra'][lang]} {offer_value}" if offer_value else ""
    return (
        f"{TEXTS['card_store'][lang]} {store_name}{trend_emoji}\n"
        f"{TEXTS['card_discount'][lang]} {s.get('discount_value', '')}"
        f"{extra_line}\n"
        f"📝 {bio}\n\n"
        f"{TEXTS['card_react_hint'][lang]}"
    )


def _show_card(user_id, page):
    """يعدّل رسالة التنقل لتعرض كرت المتجر في الصفحة المطلوبة."""
    nav    = _get_nav(user_id)
    stores = nav.get('stores', [])
    if not stores:
        return
    page = max(0, min(page, len(stores) - 1))
    _update_nav(user_id, page=page, state='codes')

    s      = stores[page]
    lang   = get_lang(user_id)
    source = nav.get('source', 'codes')
    text   = _card_text(s, lang)
    markup = _kb_card(lang, s, page, len(stores), source)

    nav2 = _get_nav(user_id)
    if nav2.get('msg_id'):
        try:
            conn = get_db_connection()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO sent_coupon_messages (chat_id, message_id, store_id, user_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id, message_id) DO UPDATE SET store_id = EXCLUDED.store_id
            """, (nav2['chat_id'], nav2['msg_id'], s['store_id'], user_id))
            conn.commit()
            release_conn(conn)
        except Exception as e:
            print(f"⚠️ sent_coupon_messages upsert: {e}")

    logo_url = (s.get('logo_url') or '').strip()
    if logo_url:
        _edit_nav_photo(user_id, logo_url, text, markup)
    else:
        _edit_nav(user_id, text, markup)


# ============================================================
#  Navigation Logic Helpers
# ============================================================

def _load_and_show_codes(user_id, lang):
    log_action(None, 'view_all', user_id=user_id)
    try:
        conn = get_db_connection()
        cur  = conn.cursor(cursor_factory=extras.DictCursor)
        cur.execute("""
            SELECT * FROM master
            WHERE last_time IS NULL OR last_time >= CURRENT_DATE
            ORDER BY
                CASE WHEN is_trending = 'ترند 🔥' THEN 1 ELSE 2 END,
                priority_score DESC
            LIMIT 20
        """)
        rows = [dict(r) for r in cur.fetchall()]
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ _load_and_show_codes: {e}")
        _edit_nav(user_id, t(user_id, 'tech_error'), _kb_cancel(lang))
        return
    if not rows:
        _edit_nav(user_id, t(user_id, 'no_codes'), _kb_cancel(lang))
        return
    _update_nav(user_id, stores=rows, page=0, source='codes', state='codes')
    _show_card(user_id, 0)


def _fetch_cats_from_db(lang: str) -> list:
    tags_expr = "COALESCE(NULLIF(store_tags_en, ''), store_tags)" if lang == "en" else "store_tags"
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            WITH tags_raw AS (
                SELECT DISTINCT trim(tg) AS tag
                FROM master,
                     unnest(string_to_array(
                         trim(both '{{}}' from COALESCE({tags_expr}, '')), ','
                     )) AS tg
                WHERE trim(tg) <> ''
                  AND (last_time IS NULL OR last_time >= CURRENT_DATE)
            )
            SELECT t.tag
            FROM tags_raw t
            LEFT JOIN categories_tags ct ON ct.tag_name = t.tag
            ORDER BY COALESCE(ct.priority_rank, 5) ASC,
                     COALESCE(ct."Tag_clicks",   0) DESC,
                     t.tag                          ASC
        """)
        return [r[0] for r in cur.fetchall()]
    finally:
        release_conn(conn)


def _get_cats(lang: str) -> list:
    """يُعيد الأقسام من الـ cache — يستعلم DB مرة كل 5 دقائق فقط."""
    now = time.time()
    entry = _cats_cache.get(lang)
    if entry and now - entry[0] < _CATS_TTL:
        return entry[1]
    tags = _fetch_cats_from_db(lang)
    _cats_cache[lang] = (now, tags)
    return tags


def _show_cats(user_id, lang):
    log_action(None, 'view_sections', user_id=user_id)
    try:
        tags = _get_cats(lang)
    except Exception as e:
        print(f"⚠️ _show_cats: {e}")
        _edit_nav(user_id, t(user_id, 'sections_load_err'), _kb_cancel(lang))
        return
    if not tags:
        _edit_nav(user_id, t(user_id, 'no_sections'), _kb_cancel(lang))
        return
    _update_nav(user_id, state='cats')
    _edit_nav(user_id, t(user_id, 'pick_section'), _kb_cats(lang, tags))


def _load_tag_stores(user_id, lang, tag):
    # نُطابق الـ tag بنفس العمود اللي عرضناه للمستخدم في _show_cats
    tags_expr = "COALESCE(NULLIF(store_tags_en, ''), store_tags)" if lang == "en" else "store_tags"
    try:
        conn = get_db_connection()
        cur  = conn.cursor(cursor_factory=extras.DictCursor)
        cur.execute(f"""
            SELECT * FROM master
            WHERE %s = ANY(
                SELECT lower(trim(tg))
                FROM unnest(string_to_array(trim(both '{{}}' from COALESCE({tags_expr}, '')), ',')) AS tg
            )
            AND (last_time IS NULL OR last_time >= CURRENT_DATE)
            ORDER BY
                CASE WHEN is_trending = 'ترند 🔥' THEN 1 ELSE 2 END,
                priority_score DESC
        """, (tag.lower(),))
        rows = [dict(r) for r in cur.fetchall()]
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ _load_tag_stores: {e}")
        _edit_nav(user_id, t(user_id, 'tag_load_err'), _kb_cancel(lang))
        return
    if not rows:
        _edit_nav(user_id, t(user_id, 'no_stores_in_tag', tag=tag), _kb_cancel(lang))
        return
    _update_nav(user_id, stores=rows, page=0, source='tag', tag=tag, state='codes')
    _show_card(user_id, 0)


def fetch_api_results(query: str, limit: int = 30, lang: str = "ar") -> list | None:
    """
    يستعلم من FastAPI ويُعيد قائمة dicts.
    - يمرّر ?lang= للسيرفر فيُستبدل القيم تلقائياً (Fallback عربي).
    - None  → السيرفر مغلق (ConnectionError) — يُفعِّل الـ fallback على DB
    - []    → السيرفر شغال لكن لا نتائج
    - [...]  → نتائج جاهزة للعرض
    """
    print(f"🔍 [API] قاعد أبحث في الـ API عن: '{query}' (lang={lang})")
    try:
        resp = requests.get(
            _API_SEARCH_URL,
            params={"q": query, "limit": limit, "lang": lang},
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        normalized = []
        for r in results:
            normalized.append({
                "store_id":      r.get("store_id", ""),
                "name_en":       r.get("name_en") or "",
                "affiliate_link":r.get("affiliate_link") or "",
                "public_coupon": r.get("public_coupon") or "",
                "discount_value":r.get("discount_value") or "—",
                "extra_offer":   r.get("extra_offer") or "",
                "store_bio":     r.get("store_bio") or "",
                "is_trending":   r.get("is_trending") or "عادي",
                "priority_score":r.get("priority_score") or "عادي",
                "logo_url":      r.get("logo_url") or "",
            })
        return normalized
    except requests.exceptions.ConnectionError:
        print(f"⚠️ [API] السيرفر مغلق — تشغيل: uvicorn api.main:app --reload --port 8000")
        return None
    except Exception as e:
        print(f"⚠️ [API] خطأ غير متوقع: {e}")
        return None


def _db_search(search_term: str) -> list:
    """
    بحث احتياطي مباشر في قاعدة البيانات (fallback عند إغلاق الـ API).
    يبحث في الأعمدة العربية والإنجليزية معاً (المستخدم قد يكتب بأي لغة).
    يرجع الصف الخام (يحوي AR و EN) و _card_text يختار حسب لغة المستخدم.
    """
    try:
        conn = get_db_connection()
        cur  = conn.cursor(cursor_factory=extras.DictCursor)
        like = f"%{search_term}%"
        cur.execute("""
            SELECT * FROM master
            WHERE (last_time IS NULL OR last_time >= CURRENT_DATE)
              AND (   store_id                              ILIKE %s
                   OR COALESCE(name_en,        '')          ILIKE %s
                   OR COALESCE(store_tags,     '')          ILIKE %s
                   OR COALESCE(store_tags_en,  '')          ILIKE %s
                   OR COALESCE(store_bio_en,   '')          ILIKE %s)
        """, (like, like, like, like, like))
        rows = [dict(r) for r in cur.fetchall()]
        release_conn(conn)
        return rows
    except Exception as e:
        print(f"⚠️ _db_search: {e}")
        return []


def _process_search(message):
    user_id     = message.from_user.id
    lang        = get_lang(user_id)
    search_term = (message.text or "").strip()
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    # إظهار حالة "جاري البحث" فوراً قبل أي استعلام
    _edit_nav(user_id, "🔍 جاري البحث في نبض الصفقات...", None)

    # ── المرحلة 1: API أولاً (مع تمرير لغة المستخدم) ──────────
    api_rows    = fetch_api_results(search_term, lang=lang)
    api_offline = api_rows is None

    if api_offline:
        # السيرفر مغلق → Fallback للـ DB
        rows = _db_search(search_term.lower())
    elif api_rows:
        rows = api_rows
    else:
        # API شغال لكن لا نتائج → جرب DB كـ fallback إضافي
        rows = _db_search(search_term.lower())

    log_search(search_term, found=bool(rows), user_id=user_id)
    log_action(None, 'search', user_id=user_id,
               details=f"keyword:{search_term};found:{bool(rows)}")

    if rows:
        _update_nav(user_id, stores=rows, page=0, source='search', state='codes')
        _show_card(user_id, 0)
    elif api_offline:
        # API مغلق + DB لا يعرف المتجر → رسالة خطأ واضحة
        if lang == 'ar':
            err_msg = (
                "⚠️ *خلل تقني مؤقت*\n\n"
                "محرك البحث غير متاح حالياً.\n"
                "جرّب بعد لحظات، أو تصفّح الأقسام من القائمة."
            )
        else:
            err_msg = (
                "⚠️ *Temporary technical issue*\n\n"
                "The search engine is currently unavailable.\n"
                "Try again in a moment or browse categories."
            )
        _edit_nav(user_id, err_msg, _kb_cancel(lang))
    else:
        if lang == 'ar':
            no_results_msg = (
                f"❌ ما وجدنا نتائج لـ *{search_term}*\n\n"
                f"💡 *جرّب:*\n"
                f"• اسم المتجر بالإنجليزي\n"
                f"• كلمة من اسم القسم (مثل: أزياء، إلكترونيات)\n"
                f"• أو تصفّح الأقسام من القائمة الرئيسية"
            )
        else:
            no_results_msg = (
                f"❌ No results for *{search_term}*\n\n"
                f"💡 *Try:*\n"
                f"• English store name\n"
                f"• Category keyword (fashion, electronics)\n"
                f"• Browse categories from the main menu"
            )
        _edit_nav(user_id, no_results_msg, _kb_cancel(lang))


def _process_request(message):
    user_id = message.from_user.id
    lang    = get_lang(user_id)
    brand   = (message.text or "").strip()
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    if not brand:
        _edit_nav(user_id, t(user_id, 'request_empty'), _kb_cancel(lang))
        return
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO unavailable_codes_requests (user_id, brand_name, requested_at)
            VALUES (%s, %s, NOW())
        """, (user_id, brand))
        conn.commit()
        release_conn(conn)
        log_action(None, 'request_code', user_id=user_id, details=f"brand:{brand}")
        _update_nav(user_id, state='menu')
        _edit_nav(user_id, t(user_id, 'request_saved'), _kb_main(lang))
    except Exception as e:
        print(f"⚠️ _process_request: {e}")
        _edit_nav(user_id, t(user_id, 'request_err'), _kb_cancel(lang))


# ============================================================
#  Lang Picker + Welcome Image
# ============================================================

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_arabic_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        # خط Cairo المرفق في المستودع — الأولوية
        os.path.join(_BASE_DIR, "Cairo-Bold.ttf"),
        os.path.join(_BASE_DIR, "Cairo-Bold.ttf.ttf"),  # توافق مع الاسم القديم لو لم يُعَد التسمية
        os.path.join(_BASE_DIR, "Cairo-Regular.ttf"),
        # احتياطي على Railway / Linux (Nixpacks يثبّت dejavu افتراضياً)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        # احتياطي على Windows (التطوير المحلي فقط)
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate_welcome_image(user_name: str) -> BytesIO:
    img_path = os.path.join(_BASE_DIR, "logo4.jpeg")
    img  = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = _load_arabic_font(85)

    reshaped     = arabic_reshaper.reshape(user_name)
    display_name = get_display(reshaped)

    img_w  = img.width
    bbox   = draw.textbbox((0, 0), display_name, font=font)
    text_w = bbox[2] - bbox[0]
    x, y   = (img_w - text_w) // 2, 270
    draw.text((x, y), display_name, font=font,
              fill="#1B5E3B", stroke_width=2, stroke_fill="#1B5E3B")

    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf


def show_lang_picker(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇸🇦 العربية",  callback_data="lang:ar_sa"),
        types.InlineKeyboardButton("🇺🇸 English", callback_data="lang:en_us"),
    )
    bot.send_message(
        chat_id,
        f"{TEXTS['lang_picker_msg']['ar']}\n\n{TEXTS['lang_picker_msg']['en']}",
        reply_markup=markup
    )


# ============================================================
#  Session Start
# ============================================================

def _start_session(message):
    """
    إقلاع جلسة المستخدم. مُحصّن بـ multi-layer fallbacks بحيث الـ user
    يحصل على رد دائماً حتى لو فشلت صورة الترحيب أو DB call أو i18n.

    سلسلة الـ fallback:
      1. الـ flow الكامل (image + main menu)
      2. لو فشلت image → main menu نصي فقط
      3. لو فشل DB/i18n → رسالة طوارئ ثابتة + لوحة افتراضية
    """
    chat_id = message.chat.id
    user_id = message.from_user.id

    # محاولة 1: register + onboarding check + log — كلها optional
    try:
        register_or_update_user(message)
        log_action(None, 'start', user_id=user_id)
        if needs_onboarding(user_id):
            try:
                show_lang_picker(chat_id)
                return
            except Exception as e:
                print(f"⚠️ show_lang_picker failed: {e}")
                # نُكمل للـ welcome العادي حتى لو فشل onboarding
    except Exception as e:
        print(f"⚠️ start preflight (register/onboarding) failed: {e}")

    # محاولة 2: استخراج اللغة بأمان
    try:
        lang = get_lang(user_id)
    except Exception:
        lang = 'ar'

    # محاولة 3: صورة الترحيب — اختيارية تماماً، نتخطّاها بصمت لو فشلت
    user_name = message.from_user.first_name or message.from_user.username or "زائر"
    try:
        img_buf = generate_welcome_image(user_name)
        bot.send_photo(chat_id, img_buf, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        print(f"⚠️ welcome image failed (skipping): {e}")
        # ReplyKeyboardRemove مهم لمسح أي لوحة قديمة
        try:
            bot.send_message(chat_id, "🟢", reply_markup=types.ReplyKeyboardRemove())
        except Exception:
            pass

    # محاولة 4: القائمة الرئيسية — الأهم. لو فشلت، نُرسل رسالة طوارئ.
    try:
        welcome_text = t(user_id, 'welcome')
    except Exception:
        welcome_text = "👋 أهلاً بك في نبض الصفقات!" if lang == 'ar' else "👋 Welcome to Deal Pulse!"

    try:
        kb = _kb_main(lang)
        msg_id = _ensure_nav(chat_id, user_id, welcome_text, kb)
        _set_nav(user_id, {
            'chat_id': chat_id, 'msg_id': msg_id,
            'state': 'menu', 'stores': [], 'page': 0, 'source': 'codes',
        })
    except Exception as e:
        print(f"❌ critical: main menu failed: {e}")
        # رسالة طوارئ — لا تعتمد على أي helper. الـ user يجب أن يرى شيئاً.
        fallback_text = (
            "⚠️ حصل خطأ مؤقت في تحضير القائمة. جرّب /start مرة أخرى بعد لحظات.\n"
            "للبحث المباشر، اكتب اسم المتجر."
            if lang == 'ar' else
            "⚠️ Temporary error preparing the menu. Try /start again in a moment.\n"
            "For direct search, type a store name."
        )
        try:
            bot.send_message(chat_id, fallback_text)
        except Exception as e2:
            print(f"❌❌ even fallback failed: {e2}")


# ============================================================
#  Message Handlers
# ============================================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    _start_session(message)


@bot.message_handler(commands=['help'])
def send_help(message):
    register_or_update_user(message)
    user_id = message.from_user.id
    lang    = get_lang(user_id)
    if lang == 'en':
        text = (
            "🤖 *Deal Pulse — Help*\n\n"
            "📜 *Our Codes* — browse all available coupons\n"
            "📂 *Categories* — filter stores by category\n"
            "🔎 *Search* — type any store name to find its coupon\n"
            "➕ *Request Code* — ask us to add a store you need\n"
            "🛑 *End* — close the current session\n\n"
            "💡 You can also just type a store name directly — "
            "the bot will search automatically."
        )
    else:
        text = (
            "🤖 *نبض الصفقات — المساعدة*\n\n"
            "📜 *أكوادنا* — تصفّح جميع الكوبونات المتاحة\n"
            "📂 *الأقسام* — فلتر المتاجر حسب القسم\n"
            "🔎 *البحث* — اكتب اسم أي متجر للعثور على كوبونه\n"
            "➕ *طلب كود* — اطلب إضافة متجر لا تجد كوبونه\n"
            "🛑 *إنهاء* — أغلق الجلسة الحالية\n\n"
            "💡 يمكنك كتابة اسم المتجر مباشرة — البوت سيبحث تلقائياً."
        )
    bot.reply_to(message, text, parse_mode="Markdown")



@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def handle_text(message):
    register_or_update_user(message)
    user_id = message.from_user.id
    nav     = _get_nav(user_id)
    state   = nav.get('state', '')

    if state == 'search':
        _process_search(message)
    elif state == 'request':
        _process_request(message)
    elif message.text.strip():
        # نص عادي بدون حالة بحث → بحث مباشر تلقائي
        if not nav.get('msg_id'):
            # لا توجد جلسة نشطة → ابدأ جلسة أولاً
            _start_session(message)
            return
        _update_nav(user_id, state='search')
        _process_search(message)
    else:
        log_action(None, 'unknown_input', user_id=user_id,
                   details=f"text:{(message.text or '')[:80]}")
        if not nav.get('msg_id'):
            _start_session(message)


# ============================================================
#  Callback Handlers
# ============================================================

_LANG_DEFAULTS = {
    'ar_sa': {'lang': 'ar', 'country': 'المملكة العربية السعودية', 'city': 'الرياض',
              'ack_key': 'lang_ar_picked'},
    'en_us': {'lang': 'en', 'country': 'المملكة العربية السعودية', 'city': 'الرياض',
              'ack_key': 'lang_en_picked'},
}


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang:"))
def handle_lang_pick(call):
    code    = call.data.split(":", 1)[1]
    user_id = call.from_user.id
    cfg     = _LANG_DEFAULTS.get(code)
    if not cfg:
        bot.answer_callback_query(call.id, "⚠️ خيار غير معروف")
        return

    is_premium  = getattr(call.from_user, 'is_premium', False)
    device_type = 'iPhone' if is_premium else 'Android'

    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE bot_users
            SET lang = %s, country = %s, city = %s, device_type = %s, user_status = 'Active'
            WHERE telegram_id = %s
        """, (cfg['lang'], cfg['country'], cfg['city'], device_type, user_id))
        segment = _compute_segment(cur, user_id)
        cur.execute("""
            SELECT COUNT(*) FROM action_logs
            WHERE user_id = %s AND action_type IN ('click_link','copy_coupon','search','view_tag')
        """, (user_id,))
        rank = _loyalty_rank(cur.fetchone()[0])
        cur.execute("""
            UPDATE bot_users SET marketing_segment = %s, loyalty_rank = %s WHERE telegram_id = %s
        """, (segment, rank, user_id))
        conn.commit()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ lang pick {code} for {user_id}: {e}")
        bot.answer_callback_query(call.id, "⚠️")
        return

    invalidate_lang_cache(user_id)
    log_action(None, 'lang_pick', user_id=user_id,
               details=f"code:{code};device:{device_type}")
    bot.answer_callback_query(call.id)

    lang = cfg['lang']
    try:
        bot.edit_message_text(
            TEXTS[cfg['ack_key']][lang],
            call.message.chat.id, call.message.message_id
        )
    except Exception:
        pass

    sent = bot.send_message(
        call.message.chat.id,
        t(user_id, 'welcome'),
        reply_markup=_kb_main(lang),
        parse_mode="Markdown"
    )
    _set_nav(user_id, {
        'chat_id': call.message.chat.id, 'msg_id': sent.message_id,
        'state': 'menu', 'stores': [], 'page': 0, 'source': 'codes',
    })


@bot.callback_query_handler(func=lambda call: call.data.startswith('nav:'))
def handle_nav(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    lang    = get_lang(user_id)
    action  = call.data[4:]

    bot.answer_callback_query(call.id)

    nav = _get_nav(user_id)
    if not nav.get('msg_id') or nav.get('msg_id') != call.message.message_id:
        _update_nav(user_id, chat_id=chat_id, msg_id=call.message.message_id)

    if action == 'menu':
        _update_nav(user_id, state='menu')
        _edit_nav(user_id, t(user_id, 'welcome'), _kb_main(lang))

    elif action == 'codes':
        _load_and_show_codes(user_id, lang)

    elif action == 'cats':
        _show_cats(user_id, lang)

    elif action == 'search':
        _update_nav(user_id, state='search')
        _edit_nav(user_id, t(user_id, 'search_prompt'), _kb_cancel(lang))

    elif action == 'request':
        _update_nav(user_id, state='request')
        _edit_nav(user_id, t(user_id, 'request_prompt'), _kb_cancel(lang))

    elif action == 'end':
        log_action(None, 'end_session', user_id=user_id)
        _update_nav(user_id, state='ended')
        _edit_nav(user_id, t(user_id, 'session_ended'), _kb_start(lang))

    elif action == 'prev':
        _show_card(user_id, _get_nav(user_id).get('page', 0) - 1)

    elif action == 'next':
        _show_card(user_id, _get_nav(user_id).get('page', 0) + 1)

    elif action == 'card':
        _show_card(user_id, _get_nav(user_id).get('page', 0))

    elif action == 'noop':
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('ntag:'))
def handle_tag_nav(call):
    user_id = call.from_user.id
    lang    = get_lang(user_id)
    tag     = call.data[5:]

    bot.answer_callback_query(call.id)
    _update_nav(user_id, chat_id=call.message.chat.id, msg_id=call.message.message_id)

    log_action(None, 'view_tag', user_id=user_id, details=f"tag:{tag}")
    update_user_behavior(user_id, 'view_tag', tag=tag)
    _load_tag_stores(user_id, lang, tag)


@bot.callback_query_handler(func=lambda call: call.data.startswith("link:"))
def handle_link_click(call):
    store_id = call.data.split(":", 1)[1]
    user_id  = call.from_user.id
    lang     = get_lang(user_id)

    _update_nav(user_id, chat_id=call.message.chat.id, msg_id=call.message.message_id)
    update_user_behavior(user_id, 'click_link')
    bot.answer_callback_query(call.id, t(user_id, 'visit_logged'))

    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT affiliate_link, cloaked_slug FROM master
            WHERE store_id = %s
              AND (last_time IS NULL OR last_time >= CURRENT_DATE)
            LIMIT 1
        """, (store_id,))
        row  = cur.fetchone()
        release_conn(conn)
    except Exception as e:
        print(f"⚠️ link callback: {e}")
        return

    affiliate_link = row[0] if row else None
    cloaked_slug   = row[1] if row else None

    if cloaked_slug:
        # عبر /go → السيرفر يلتقط الـ IP (Worker) فيُعرف المدينة، ويسجّل النقرة + يرفع
        # العدّاد. s=bot لفصل المصدر، u=معرّف المستخدم لربط النقرة/المدينة بالشخص.
        # فلا نسجّل النقرة هنا تفادياً للتكرار.
        open_url = f"{_GO_BASE}/go/{cloaked_slug}?s=bot&u={user_id}"
    elif affiliate_link:
        # متجر بلا cloaked_slug → رابط خام لا يمرّ على /go → نسجّل النقرة هنا (بلا مدينة)
        open_url = affiliate_link
        increment_link_clicks(store_id)
        log_action(store_id, 'click_link', user_id=user_id)
    else:
        bot.answer_callback_query(call.id, t(user_id, 'link_unavailable'))
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t(user_id, 'open_store', sid=store_id), url=open_url))
    kb.add(types.InlineKeyboardButton(TEXTS['back_btn'][lang], callback_data='nav:card'))
    _edit_nav(user_id, t(user_id, 'link_here'), kb)


@bot.callback_query_handler(func=lambda call: call.data.startswith("copy:"))
def handle_coupon_copy(call):
    store_id = call.data.split(":", 1)[1]
    user_id  = call.from_user.id
    lang     = get_lang(user_id)

    _update_nav(user_id, chat_id=call.message.chat.id, msg_id=call.message.message_id)
    increment_coupon_copies(store_id)
    log_action(store_id, 'copy_coupon', user_id=user_id)
    update_user_behavior(user_id, 'copy_coupon', store_id=store_id)

    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT public_coupon FROM master
            WHERE store_id = %s
              AND (last_time IS NULL OR last_time >= CURRENT_DATE)
            LIMIT 1
        """, (store_id,))
        row    = cur.fetchone()
        release_conn(conn)
        coupon = row[0] if row and row[0] else None
    except Exception as e:
        bot.answer_callback_query(call.id, t(user_id, 'coupon_err'))
        print(f"⚠️ copy callback: {e}")
        return

    if coupon:
        bot.answer_callback_query(call.id, t(user_id, 'coupon_here'))
        _update_nav(user_id, state='coupon')
        # Bot API 7.7 / telebot 4.21+: زر copy_text ينسخ النص للحافظة بضغطة وحدة فعلاً
        # (لا حاجة للمستخدم يضغط على الكود نفسه).
        kb_copy = types.InlineKeyboardMarkup()
        kb_copy.add(types.InlineKeyboardButton(
            f"📋 انسخ الكود: {coupon}",
            copy_text=types.CopyTextButton(text=coupon)))
        kb_copy.add(types.InlineKeyboardButton(TEXTS['back_btn'][lang], callback_data='nav:card'))
        _edit_nav(user_id, t(user_id, 'coupon_for', sid=store_id, c=coupon), kb_copy)
    else:
        bot.answer_callback_query(call.id, t(user_id, 'coupon_unavailable'))


# ============================================================
#  Reaction Handler — ❤️ يضيف للمفضلة بصمت (لا رسالة جديدة)
# ============================================================

_HEART_EMOJIS = {'❤️', '❤', '🩷', '💖', '💗', '💘', '💝', '😍', '🥰'}


def _process_heart_reaction(chat_id, message_id, user_id):
    # نلتقط الاتصال في finally لمنع تسرّبه إلى الـ pool في حالة الاستثناء
    conn = None
    store_id = None
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT store_id FROM sent_coupon_messages
            WHERE chat_id = %s AND message_id = %s
        """, (chat_id, message_id))
        row = cur.fetchone()
        if not row:
            return
        store_id = row[0]

        cur.execute("""
            UPDATE bot_users
            SET manual_favorites = CASE
                WHEN manual_favorites IS NULL             THEN ARRAY[%s]::text[]
                WHEN NOT (%s = ANY(manual_favorites))     THEN manual_favorites || ARRAY[%s]::text[]
                ELSE manual_favorites
                END,
                fav_store_inferred = %s
            WHERE telegram_id = %s
        """, (store_id, store_id, store_id, store_id, user_id))
        conn.commit()
    except Exception as e:
        print(f"⚠️ _process_heart_reaction: {e}")
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if conn is not None:
            release_conn(conn)

    # الاستدعاءات التابعة تستخدم اتصالاً جديداً — نتركها خارج try/except
    # حتى لا تُحجب أخطاؤها بسبب أخطاء قسم DB أعلاه.
    if store_id is not None:
        try:
            log_action(store_id, 'reaction_heart', user_id=user_id)
            update_user_behavior(user_id, 'reaction_heart', store_id=store_id)
        except Exception as e:
            print(f"⚠️ _process_heart_reaction post-actions: {e}")


if hasattr(bot, 'message_reaction_handler'):
    @bot.message_reaction_handler()
    def handle_reaction(reaction):
        try:
            new_emojis = {
                getattr(r, 'emoji', None)
                for r in (reaction.new_reaction or [])
                if getattr(r, 'type', None) == 'emoji'
            }
            if not (new_emojis & _HEART_EMOJIS):
                return
            user_id = reaction.user.id if reaction.user else None
            if not user_id:
                return
            _process_heart_reaction(reaction.chat.id, reaction.message_id, user_id)
        except Exception as e:
            print(f"⚠️ reaction handler: {e}")
    print("✅ Reactions enabled (message_reaction_handler registered)")
else:
    print("⚠️ Reactions غير مدعومة — حدّث: pip install --upgrade pyTelegramBotAPI")


# ============================================================
#  Idle Watcher — يعدّل رسالة التنقل بدل إرسال رسالة جديدة
# ============================================================

def check_idle_users():
    global _idle_warned, _idle_kicked
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        # المرحلة 1: خامل >= WARN دقيقة
        cur.execute("""
            SELECT telegram_id FROM bot_users
            WHERE last_seen IS NOT NULL
              AND last_seen < NOW() - make_interval(mins => %s)
              AND last_seen > NOW() - make_interval(hours => %s)
        """, (IDLE_WARN_MINUTES, IDLE_ALERT_WINDOW_HOURS))
        warn_ids = [row[0] for row in cur.fetchall()]

        # المرحلة 2: خامل >= KICK دقيقة
        cur.execute("""
            SELECT telegram_id FROM bot_users
            WHERE last_seen IS NOT NULL
              AND last_seen < NOW() - make_interval(mins => %s)
              AND last_seen > NOW() - make_interval(hours => %s)
        """, (IDLE_KICK_MINUTES, IDLE_ALERT_WINDOW_HOURS))
        kick_ids = [row[0] for row in cur.fetchall()]
        release_conn(conn)
    except Exception as e:
        print(f"idle query error: {e}")
        return

    active_window = set(warn_ids) | set(kick_ids)
    with _idle_lock:
        # حذف من الـ sets من خرج عن نافذة الـ 24 ساعة (غاب وانتهت فترة المراقبة)
        _idle_warned &= active_window
        _idle_kicked &= active_window
        to_warn = [uid for uid in warn_ids if uid not in _idle_warned and uid not in _idle_kicked]
        to_kick = [uid for uid in kick_ids if uid not in _idle_kicked]

    # ── المرحلة 1: إرسال تذكير ────────────────────────────────────────────
    for uid in to_warn:
        try:
            lang = get_lang(uid)
            nav  = _get_nav(uid)
            text = t(uid, 'idle_warn',
                     m=IDLE_WARN_MINUTES,
                     k=IDLE_KICK_MINUTES - IDLE_WARN_MINUTES)
            if nav.get('msg_id') and nav.get('chat_id'):
                try:
                    bot.edit_message_text(
                        text, nav['chat_id'], nav['msg_id'],
                        reply_markup=_kb_start(lang), parse_mode="Markdown"
                    )
                except Exception:
                    bot.send_message(uid, text,
                                     reply_markup=_kb_start(lang),
                                     parse_mode="Markdown")
            else:
                bot.send_message(uid, text,
                                 reply_markup=_kb_start(lang),
                                 parse_mode="Markdown")
            log_action(None, 'idle_warn', user_id=uid)
            with _idle_lock:
                _idle_warned.add(uid)
            time.sleep(0.05)
        except Exception as e:
            print(f"idle warn failed for {uid}: {e}")

    # ── المرحلة 2: إنهاء الجلسة تلقائياً ────────────────────────────────
    for uid in to_kick:
        try:
            lang = get_lang(uid)
            nav  = _get_nav(uid)
            text = t(uid, 'idle_alert')
            if nav.get('msg_id') and nav.get('chat_id'):
                try:
                    bot.edit_message_text(
                        text, nav['chat_id'], nav['msg_id'],
                        reply_markup=_kb_start(lang), parse_mode="Markdown"
                    )
                except Exception:
                    bot.send_message(uid, text, reply_markup=_kb_start(lang))
            else:
                bot.send_message(uid, text, reply_markup=_kb_start(lang))
            _update_nav(uid, state='ended')
            log_action(None, 'idle_kick', user_id=uid)
            with _idle_lock:
                _idle_kicked.add(uid)
            time.sleep(0.05)
        except Exception as e:
            print(f"idle kick failed for {uid}: {e}")


def idle_watcher():
    while True:
        try:
            check_idle_users()
        except Exception as e:
            print(f"idle watcher loop: {e}")
        time.sleep(IDLE_CHECK_INTERVAL_SECONDS)


# ============================================================
#  تشغيل البوت
# ============================================================

if __name__ == "__main__":
    # ⚠️ الإنتاج يعمل عبر bot_app.py (webhook). تشغيل هذا الملف محلياً ينفّذ
    # remove_webhook() ويحذف webhook الإنتاج → البوت الحيّ يسكت ويختفي كل شي.
    # لذلك نمنع التشغيل العرضي ونطلب علماً صريحاً (ALLOW_LOCAL_POLLING=1)
    # للتطوير فقط وعندما يكون الإنتاج موقوفاً.
    if os.getenv("ALLOW_LOCAL_POLLING") != "1":
        print("\n⛔ ممنوع تشغيل البوت محلياً (polling): يحذف webhook الإنتاج فيوقف البوت الحيّ.")
        print("   البوت يعمل على خدمة DealPulseKSA (webhook). لا تشغّله محلياً.")
        print("   للتطوير فقط (والإنتاج موقوف):")
        print("     PowerShell: $env:ALLOW_LOCAL_POLLING='1'; .\\venv\\Scripts\\python.exe deal_pulse_bot.py\n")
        raise SystemExit(1)
    try:
        bot.remove_webhook()
        clean_legacy_columns()
        ensure_tracking_tables()
        # backfill في background — البوت يبدأ فوراً دون انتظار
        threading.Thread(target=backfill_user_behavior, daemon=True).start()
        threading.Thread(target=idle_watcher, daemon=True).start()
        print(f"✅ البوت شغال + مراقبة الخمول مفعّلة (تذكير={IDLE_WARN_MINUTES}m | إنهاء={IDLE_KICK_MINUTES}m)")
        bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'])
    except Exception as e:
        print(f"❌ حدث خطأ: {e}")
