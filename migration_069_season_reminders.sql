-- ============================================================================
-- Migration 069 — تذكيرات المواسم (season_reminders)
-- ============================================================================
-- الغرض
--   صفحة /calendar تستقبل زيارات حقيقية ثم ترتدّ: الزائر يسأل «متى يبدأ الموسم؟»
--   فيأخذ التاريخ وتنتهي حاجته. المشكلة ليست ضعف الروابط بل أن نيّته **تخطيط**
--   لا شراء — الموسم بعد أسابيع، فلا شيء يفعله اليوم.
--
--   هذا الجدول يحوّل تلك الزيارة الميتة إلى أصل: نأخذ إيميلاً واحداً ونعيد
--   الاتصال به يوم يصير جاهزاً فعلاً. لا تسجيل ولا OTP — بوابة إضافية على زائر
--   بلا نيّة شراء تقتل حجم الالتقاط، وحجم الالتقاط هو الهدف كله هنا.
--
-- ملاحظات تصميم
--   • المواسم مصدرها `app/calendar/data.ts` في ريبو الويب (12 موسماً بمعرّفات
--     ثابتة) لا جدول `seasonal_events` — لذلك `season_id` نصّ حرّ لا مفتاح أجنبي.
--     نخزّن `season_name` معه حتى يبقى السجل مقروءاً لو تغيّر المعرّف لاحقاً.
--   • فريد على (email, season_id): إعادة الاشتراك في نفس الموسم تحديث لا تكرار.
--   • `unsubscribe_token` يولَّد هنا فلا يحتاج التطبيق منطق توليد، وكل رسالة
--     تحمل رابط إلغاء اشتراك — شرط أساسي لأي بريد جماعي.
--   • `sent_pre_at` / `sent_start_at` تمنع الإرسال المكرّر لو أعيد تشغيل الـcron،
--     ويُصفَّران سنوياً عبر `season_year` لأن التقويم متكرّر كل سنة.
-- ============================================================================

CREATE TABLE IF NOT EXISTS season_reminders (
    id                  BIGSERIAL PRIMARY KEY,

    email               TEXT        NOT NULL,
    season_id           TEXT        NOT NULL,
    season_name         TEXT,
    -- السنة الميلادية التي يعود فيها الموسم — تسمح بإعادة التذكير كل سنة
    season_year         INT         NOT NULL,

    -- من أين اشترك: 'calendar' (كرت الموسم) أو 'popup' أو أي سطح مستقبلي
    source              TEXT        NOT NULL DEFAULT 'calendar',
    visitor_id          TEXT,
    lang                TEXT        NOT NULL DEFAULT 'ar',

    -- 'active' | 'unsubscribed'
    status              TEXT        NOT NULL DEFAULT 'active',
    unsubscribe_token   UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- طوابع الإرسال (تمنع التكرار عند إعادة تشغيل الجدولة)
    sent_pre_at         TIMESTAMPTZ,   -- التنبيه المبكر (قبل الموسم بأيام)
    sent_start_at       TIMESTAMPTZ,   -- رسالة يوم البدء

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- منع التكرار: نفس الإيميل + نفس الموسم + نفس السنة = سجل واحد
CREATE UNIQUE INDEX IF NOT EXISTS ux_season_reminders_email_season_year
    ON season_reminders (lower(email), season_id, season_year);

-- الاستعلام الأهم في الجدولة: «أي المشتركين في موسم يبدأ خلال N يوماً؟»
CREATE INDEX IF NOT EXISTS ix_season_reminders_due
    ON season_reminders (season_id, season_year, status)
    WHERE status = 'active';

-- صفحة الداشبورد: التصنيف حسب الموسم + الأحدث أولاً
CREATE INDEX IF NOT EXISTS ix_season_reminders_created
    ON season_reminders (created_at DESC);

-- إلغاء الاشتراك عبر الرابط
CREATE INDEX IF NOT EXISTS ix_season_reminders_token
    ON season_reminders (unsubscribe_token);

COMMENT ON TABLE  season_reminders IS
    'اشتراكات تذكير مواسم التخفيضات من /calendar — إيميل فقط بلا تسجيل';
COMMENT ON COLUMN season_reminders.season_id IS
    'معرّف الموسم من app/calendar/data.ts في ريبو الويب (white-friday, ramadan, ...)';
COMMENT ON COLUMN season_reminders.season_year IS
    'السنة الميلادية التي يعود فيها الموسم — التقويم متكرّر فنُعيد التذكير سنوياً';
