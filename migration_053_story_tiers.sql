-- migration_053: نظام طبقات الستوري
--  1) master.story_ring_color: لون حلقة الستوري العادي (يدوي). NULL = تلقائي/عادي.
--     القيم: gold/silver/bronze/red/green/purple/pink (البرتقالي/الأزرق محجوزان للترند).
--  2) أعداد الترند القابلة للتحكّم في platform_settings (يومي=3، أسبوعي=7 افتراضياً).
ALTER TABLE master ADD COLUMN IF NOT EXISTS story_ring_color text;

INSERT INTO platform_settings (key, value, updated_at)
SELECT k, v, now()
FROM (VALUES ('trend_daily_count', '3'), ('trend_weekly_count', '7')) AS t(k, v)
WHERE NOT EXISTS (SELECT 1 FROM platform_settings ps WHERE ps.key = t.k);
