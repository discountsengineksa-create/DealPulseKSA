-- ============================================================================
-- Seed: seo_keyword_blocklist
-- ============================================================================
-- يُحقن قائمة افتراضية محظورة من إنتاج صفحات SEO حولها.
-- يحمي المنصة من:
--   1. توليد محتوى لكلمات بحث ممنوعة في السعودية (PDPL + هيئة الاتصالات)
--   2. منافسة العلامات التجارية بكلماتها (legal risk)
--   3. كلمات بحث بمعدّل تحويل صفري (يتلف الـ LLM cost على لا شي)
--
-- التشغيل:
--   psql $DATABASE_URL -f seed_seo_blocklist.sql
--
-- آمن للتشغيل عدة مرات (ON CONFLICT DO NOTHING).
-- ============================================================================

BEGIN;

INSERT INTO seo_keyword_blocklist (pattern, pattern_type, reason) VALUES
  -- ─── محتوى ممنوع في السعودية ───────────────────────────────────────────
  ('قمار',                'substring', 'gambling — illegal in KSA'),
  ('كازينو',              'substring', 'gambling — illegal in KSA'),
  ('casino',              'substring', 'gambling — illegal in KSA'),
  ('gambling',            'substring', 'gambling — illegal in KSA'),
  ('betting',             'substring', 'gambling — illegal in KSA'),
  ('lottery',             'substring', 'gambling — illegal in KSA'),
  ('يانصيب',              'substring', 'gambling — illegal in KSA'),

  ('خمر',                 'substring', 'alcohol — illegal in KSA'),
  ('نبيذ',                'substring', 'alcohol — illegal in KSA'),
  ('alcohol',             'substring', 'alcohol — illegal in KSA'),
  ('wine',                'exact',     'alcohol — illegal in KSA'),
  ('beer',                'exact',     'alcohol — illegal in KSA'),
  ('vodka',               'substring', 'alcohol — illegal in KSA'),

  ('سيجار',               'substring', 'tobacco/vape — regulated'),
  ('شيشة',                'substring', 'tobacco/vape — regulated'),
  ('vape',                'substring', 'tobacco/vape — regulated'),
  ('cigarette',           'substring', 'tobacco/vape — regulated'),
  ('e-?cig',              'regex',     'tobacco/vape — regulated'),

  -- ─── أدوية تتطلب وصفة ───────────────────────────────────────────────────
  ('فياجرا',              'substring', 'prescription medication'),
  ('viagra',              'substring', 'prescription medication'),
  ('cialis',              'substring', 'prescription medication'),
  ('xanax',               'substring', 'prescription medication'),
  ('tramadol',            'substring', 'controlled substance'),
  ('ترامادول',            'substring', 'controlled substance'),

  -- ─── محتوى للبالغين ─────────────────────────────────────────────────────
  ('porn',                'substring', 'adult content'),
  ('adult',               'exact',     'adult content'),
  ('sex',                 'exact',     'adult content'),
  ('xxx',                 'substring', 'adult content'),
  ('escort',              'substring', 'adult content'),

  -- ─── احتيال وروابط مشبوهة ──────────────────────────────────────────────
  ('ربح سريع',            'substring', 'scam-prone keyword'),
  ('get rich quick',      'substring', 'scam-prone keyword'),
  ('forex bot',           'substring', 'financial scam-prone'),
  ('crypto pump',         'substring', 'financial scam-prone'),
  ('mlm',                 'exact',     'multi-level marketing scam-prone'),
  ('hyip',                'substring', 'high-yield investment scam'),

  -- ─── علامات تجارية محظور التنافس عليها مباشرة ──────────────────────────
  -- (إن أضفنا اسم Amazon أو Noon هنا، نمنع توليد صفحة تنافسهم بكلمتهم
  --  لكن ما زلنا قادرين على إنشاء صفحة "كوبون أمازون" لو هو متجر مسجّل لدينا
  --  لأن المُطابق يربط الكلمة بـ master.store_id قبل المرور بالـ blocklist)
  -- اتركها فارغة الآن — قابلة للإضافة لاحقاً عند طلب قانوني.

  -- ─── كلمات بحث منخفضة الجودة (تستنزف LLM) ─────────────────────────────
  ('test',                'exact',     'low-quality test query'),
  ('asdf',                'substring', 'noise / keyboard mashing'),
  ('قاسم',                'exact',     'noise — common Arabic name'),
  ('a',                   'exact',     'too short'),
  ('the',                 'exact',     'too short'),

  -- ─── محتوى ديني/سياسي حسّاس ─────────────────────────────────────────────
  -- (نتجنّب توليد محتوى تجاري على كلمات حسّاسة)
  ('shia',                'substring', 'sensitive religious'),
  ('sunni',               'substring', 'sensitive religious'),
  ('palestine',           'substring', 'sensitive political'),
  ('فلسطين',              'substring', 'sensitive political'),
  ('isreal',              'substring', 'sensitive political'),
  ('israel',              'substring', 'sensitive political')

ON CONFLICT (pattern) DO NOTHING;

-- إحصاء سريع للتأكيد
SELECT pattern_type, COUNT(*) AS total
FROM seo_keyword_blocklist
GROUP BY pattern_type
ORDER BY total DESC;

COMMIT;
