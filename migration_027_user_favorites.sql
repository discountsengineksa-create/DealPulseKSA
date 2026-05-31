-- ════════════════════════════════════════════════════════════════════════════
-- Migration 027: user_favorites — جدول مفضلة موحّد عبر المنصات (SSOT)
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف جدولاً مُطبّعاً واحداً يربط الشخص بمتاجره المفضّلة عبر البوت + الميني ويب
-- + الموقع، ويصبح مصدر الحقيقة الوحيد للتحليل التجميعي وللتنبيهات المستقبلية.
--
-- لماذا (وليس الاكتفاء بـ manual_favorites TEXT[]):
--   - manual_favorites مصفوفة نصية لا تحمل وقت التفضيل ولا متى آخر تنبيه.
--   - الهدف «نرسل للشخص لما ينزل كوبون جديد/خصم أفضل لمتجره المفضل» يتطلّب:
--       * created_at        : متى فضّله (للترتيب + رسائل «أضفته قبل ٣ أيام»).
--       * last_notified_at  : منع تكرار التنبيه عن نفس المتجر (أساس فقط الآن).
--   - leaderboard «أكثر المتاجر تفضيلاً + كم شخص» = GROUP BY سهل على جدول واحد
--     بدل unnest لمصفوفتين على جدولين منفصلين.
--
-- التوافق العكسي (dual-write):
--   نُبقي عمودي manual_favorites على web_users و bot_users كما هي — الكود
--   التطبيقي يكتب في الاثنين (الجدول الجديد = SSOT للتحليل، والعمود = cache
--   للواجهات الحالية: getFavorites بالموقع + بطاقة المستخدم بالداشبورد + استنتاج
--   البوت). لا حذف للأعمدة في هذه الـ migration.
--
-- التطبيق:
--   python api/run_migration.py migration_027_user_favorites.sql
--   (أو) psql "$DATABASE_URL" -f migration_027_user_favorites.sql
-- ════════════════════════════════════════════════════════════════════════════

-- ─── 1. الجدول ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_favorites (
    id               BIGSERIAL   PRIMARY KEY,
    platform         TEXT        NOT NULL CHECK (platform IN ('bot', 'web', 'miniapp')),
    web_user_id      BIGINT      REFERENCES web_users(id) ON DELETE CASCADE,  -- مالك ويب
    telegram_id      BIGINT,                                                   -- مالك بوت/ميني
    store_id         TEXT        NOT NULL,   -- بدون FK لـ master (store_id غير فريد هناك)
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    last_notified_at TIMESTAMPTZ,            -- أساس التنبيهات: NULL = لم يُنبَّه بعد
    -- مالك واحد بالضبط لكل صف (إمّا ويب وإمّا تيليجرام، لا الاثنان ولا لا شيء)
    CONSTRAINT uf_owner_exactly_one CHECK (
        (web_user_id IS NOT NULL)::int + (telegram_id IS NOT NULL)::int = 1
    )
);

COMMENT ON TABLE  user_favorites                  IS 'مفضلة المستخدمين الموحّدة عبر البوت/الميني/الويب — SSOT للتحليل والتنبيهات.';
COMMENT ON COLUMN user_favorites.platform         IS 'منصة آخر إضافة: bot | web | miniapp.';
COMMENT ON COLUMN user_favorites.web_user_id      IS 'مالك ويب (web_users.id). NULL لو المالك تيليجرام.';
COMMENT ON COLUMN user_favorites.telegram_id      IS 'مالك تيليجرام (bot_users.telegram_id) — مشترك بين البوت والميني ويب. NULL لو المالك ويب.';
COMMENT ON COLUMN user_favorites.store_id         IS 'معرّف المتجر (master.store_id) — بدون FK لأن store_id غير فريد في master.';
COMMENT ON COLUMN user_favorites.last_notified_at IS 'آخر مرة نُبّه فيها المالك عن جديد هذا المتجر. NULL = لم يُنبَّه. (الإرسال الفعلي مرحلة لاحقة.)';

-- ─── 2. منع التكرار لكل مالك (partial unique على كل مسار هوية) ─────────────
-- شخص واحد = صف واحد لكل متجر. الميني والبوت يشتركان في telegram_id فلا يتكرر
-- المتجر بينهما (السلوك المطلوب: مفضلة موحّدة للشخص الواحد).
CREATE UNIQUE INDEX IF NOT EXISTS uf_web_unique
    ON user_favorites (web_user_id, store_id) WHERE web_user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uf_tg_unique
    ON user_favorites (telegram_id, store_id) WHERE telegram_id IS NOT NULL;

-- ─── 3. index للوحة الأكثر تفضيلاً (GROUP BY store_id) ────────────────────
CREATE INDEX IF NOT EXISTS uf_store_idx ON user_favorites (store_id);

-- ─── 4. Backfill من manual_favorites الموجودة ─────────────────────────────
-- (أ) مفضلة الويب → platform='web'
INSERT INTO user_favorites (platform, web_user_id, store_id, created_at)
SELECT 'web', wu.id, TRIM(f), NOW()
FROM web_users wu
CROSS JOIN LATERAL unnest(COALESCE(wu.manual_favorites, '{}')) AS f
WHERE TRIM(f) <> ''
ON CONFLICT DO NOTHING;

-- (ب) مفضلة البوت/الميني → platform='bot' (التفاعل ❤️ يأتي من البوت)
INSERT INTO user_favorites (platform, telegram_id, store_id, created_at)
SELECT 'bot', bu.telegram_id, TRIM(f), NOW()
FROM bot_users bu
CROSS JOIN LATERAL unnest(COALESCE(bu.manual_favorites, '{}')) AS f
WHERE bu.telegram_id IS NOT NULL AND TRIM(f) <> ''
ON CONFLICT DO NOTHING;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق سريع بعد التطبيق:
--   SELECT platform, COUNT(*) FROM user_favorites GROUP BY platform;
--   SELECT store_id, COUNT(*) people FROM user_favorites
--     GROUP BY store_id ORDER BY people DESC LIMIT 10;
