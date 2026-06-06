-- ════════════════════════════════════════════════════════════════════════════
-- Migration 036: زرع 7 قوالب جاهزة لـ Segment Builder
-- ════════════════════════════════════════════════════════════════════════════
-- قوالب نقطة بداية للمسوّق: انسخها، عدّل القيم، احفظها باسم جديد.
-- كل قالب is_template = TRUE → يظهر في تبويب «القوالب» منفصلاً عن
-- الشرائح المخصّصة، ولا يُحذف بالخطأ.
--
-- التطبيق: python api/run_migration.py migration_036_seed_segment_templates.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- نزرع فقط لو لا توجد قوالب أصلاً (idempotent)
INSERT INTO audience_segments (name, description, channel, is_template, rules_json)
SELECT * FROM (VALUES
    -- 1. الإيقاظ — خاملون لهم مفضّلات (نية شراء سابقة)
    ('🌅 الإيقاظ — خاملون لهم اهتمام',
     'مستخدمون لم يدخلوا أكثر من 30 يوم، ولديهم متاجر أو أقسام مفضّلة. حملة "وحشتنا" + كود مغري.',
     'both', TRUE,
     '{"version":1,"logic":"and","groups":[{"logic":"and","rules":[
        {"type":"temporal","field":"last_seen","op":"<=","value_days":30},
        {"type":"attribute","field":"fav_count","op":">=","value":1}
     ]}]}'::jsonb),

    -- 2. VIP عام — أكثر من 5 نسخات آخر 30 يوم
    ('💎 VIP — مكثّفو النسخ',
     'مستخدمون نسخوا 5 أكواد أو أكثر خلال 30 يوم. جمهور عالي التحويل، رسائل حصرية.',
     'both', TRUE,
     '{"version":1,"logic":"and","groups":[{"logic":"and","rules":[
        {"type":"aggregate","action":"copy_coupon","entity_type":"any","context":"any",
         "threshold_type":"absolute","op":">=","value":5,
         "window":{"type":"last_days","days":30}}
     ]}]}'::jsonb),

    -- 3. المهتمون بقسم محدد (يحتاج تعديل entity_value)
    ('🏷️ المهتمون بقسم [عدّل القسم]',
     'مفضّلون لقسم محدد، أو بحثوا عن منتجاته. عدّل entity_value لاسم القسم المطلوب.',
     'both', TRUE,
     '{"version":1,"logic":"or","groups":[
        {"logic":"and","rules":[{"type":"attribute","field":"favorite_category","op":"=","value":"مطاعم"}]},
        {"logic":"and","rules":[{"type":"event","action":"view_tag","entity_type":"category","entity_value":"مطاعم","context":"any","window":{"type":"last_days","days":60}}]}
     ]}'::jsonb),

    -- 4. مفضّلو متجر محدد (يحتاج تعديل)
    ('❤️ مفضّلو متجر [عدّل المتجر]',
     'مستخدمون أضافوا متجراً محدداً للمفضّلة. عدّل entity_value لاسم المتجر.',
     'both', TRUE,
     '{"version":1,"logic":"and","groups":[{"logic":"and","rules":[
        {"type":"attribute","field":"favorite_store","op":"=","value":"نون"}
     ]}]}'::jsonb),

    -- 5. معجبو الترند — تفاعلوا مع بطاقة ترند
    ('🔥 معجبو الترند',
     'نقروا أو نسخوا من بطاقات ترند (يومي أو أسبوعي) آخر 14 يوم. جمهور متابع للنار.',
     'both', TRUE,
     '{"version":1,"logic":"or","groups":[
        {"logic":"and","rules":[{"type":"event","action":"click_link","entity_type":"any","context":"trend_any","window":{"type":"last_days","days":14}}]},
        {"logic":"and","rules":[{"type":"event","action":"copy_coupon","entity_type":"any","context":"trend_any","window":{"type":"last_days","days":14}}]}
     ]}'::jsonb),

    -- 6. الجدد — انضمّوا آخر 7 أيام
    ('🆕 المنضمون حديثاً',
     'مستخدمون سجّلوا خلال آخر 7 أيام. رسالة ترحيب + جولة في أبرز المزايا.',
     'both', TRUE,
     '{"version":1,"logic":"and","groups":[{"logic":"and","rules":[
        {"type":"temporal","field":"joined_at","op":">=","value_days":7}
     ]}]}'::jsonb),

    -- 7. تردّدوا — نقروا بدون نسخ
    ('🤔 المتردّدون — اهتمام بلا تحويل',
     'نقروا روابط متاجر آخر 14 يوم، لكنهم لم ينسخوا أي كوبون. تذكير + كود إضافي يحسم القرار.',
     'both', TRUE,
     '{"version":1,"logic":"and","groups":[{"logic":"and","rules":[
        {"type":"event","action":"click_link","entity_type":"any","context":"any","window":{"type":"last_days","days":14}},
        {"type":"event","action":"copy_coupon","entity_type":"any","context":"any","window":{"type":"last_days","days":14},"negate":true}
     ]}]}'::jsonb)
) AS t(name, description, channel, is_template, rules_json)
WHERE NOT EXISTS (
    SELECT 1 FROM audience_segments WHERE is_template = TRUE AND name = t.name
);

COMMIT;

-- ─── ✅ تحقّق ──────────────────────────────────────────────────────────────
-- SELECT id, name, channel FROM audience_segments WHERE is_template = TRUE ORDER BY id;
