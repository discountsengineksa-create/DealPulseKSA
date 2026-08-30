"""
يولّد migration_070_search_intelligence.sql من api/utils/arabic_search.CONCEPT_SEED.

السبب لتوليده لا كتابته يدوياً: البذرة ~300 صفّ، وأي تعديل على القاموس في
arabic_search.py يجب أن ينعكس بأمر واحد لا بنسخ يدوي. المايقريشن الناتج
idempotent (ON CONFLICT DO NOTHING) فإعادة تشغيله بعد توسيع البذرة تُضيف
الجديد فقط دون لمس ما حرّره المالك من اللوحة.

الاستخدام:
    python -m scripts.gen_migration_070      # يكتب/يحدّث ملف المايقريشن
"""
from __future__ import annotations

import pathlib

from api.utils.arabic_search import build_seed_rows

OUT = pathlib.Path(__file__).resolve().parent.parent / "migration_070_search_intelligence.sql"

HEADER = """\
-- migration_070_search_intelligence.sql
-- بحث الموقع الذكي: مرادف/إملاء/كلمة-منتج → قسم، وجسر المدوّنة.
--
-- Why (مثبّت حيّاً في direct_search، 2026-08-30):
--   البحث كان يطابق هويّة المتجر فقط (store_id/name_en/نصّ store_tags الخام/
--   store_bio_en). أول صفّ في direct_search: «أحذية» → user_found = FALSE
--   بينما الوسم في الكتالوج «أحذيه». وكذلك «خواتم»، «الخزف»، «وجبات» — نيّة
--   قسم واضحة، صفر نتائج. السبب: لا طبقة مفاهيم بين ما يكتبه الباحث وبين الوسم.
--
--   جدولان:
--   1) search_concepts — مرادف مطبّع (normalize_ar) → وسم canonical في
--      master.store_tags. البحث يوسّع الاستعلام: يجد الوسم ثم يرجّع **كل**
--      متاجره مرتّبةً بالشعبية. مصدر الحقيقة بعد البذر: هذا الجدول (يُحرَّر
--      من لوحة الأدمِن)، والبذرة في arabic_search.CONCEPT_SEED مرجع توليد فقط.
--   2) blog_bridge — صفّ لكل مقال ضيّق الموضوع: نصّه المطبّع + متاجره. البحث
--      يستعمله **احتياطاً أخيراً** (لا اسم ولا مفهوم): FTS بترتيب ts_rank،
--      فيُرجع متاجر أعلى مقال/مقالات مع عنوانه في via_article. يملؤه
--      scripts/build_blog_bridge.py. يبدأ فارغاً — البحث يتخطّاه بأمان حتى يُملأ.
--
-- الشكل: canonical_tag / store_ids يطابقان اصطلاح master (نصّ، لا مصفوفة).
-- الدلالة: **إضافة فقط.** فارغ = سلوك البحث الحالي بلا تغيير. آمنة رجعياً.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ═══════════════════════════════════════════════════════════════════════════
-- 0) normalize_ar()  —  نفس قواعد api/utils/arabic_search.normalize_ar
--    أإآٱ→ا ، ى→ي ، ة→ه ، حذف التطويل/التشكيل ، ضغط الفراغات.
--    IMMUTABLE ليصلح داخل الفهارس والاستعلامات المتكرّرة.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION normalize_ar(t text) RETURNS text AS $$
  SELECT trim(regexp_replace(
    translate(
      regexp_replace(lower(coalesce(t, '')), '[ـً-ْ]', '', 'g'),
      'أإآٱىة', 'اااايه'
    ),
    '\\s+', ' ', 'g'
  ))
$$ LANGUAGE sql IMMUTABLE;

-- ═══════════════════════════════════════════════════════════════════════════
-- 1) search_concepts
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS search_concepts (
    id             SERIAL PRIMARY KEY,
    term           TEXT NOT NULL,                    -- مطبّع بـ normalize_ar
    canonical_tag  TEXT NOT NULL,                    -- قيمة فعلية في master.store_tags
    weight         REAL NOT NULL DEFAULT 1.0,        -- 1.0 مرادف قسم ، 0.6 كلمة منتج
    source         TEXT NOT NULL DEFAULT 'curated',  -- curated | blog | manual
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (term, canonical_tag)
);

COMMENT ON TABLE search_concepts IS
  'طبقة المفاهيم للبحث: مرادف/إملاء/كلمة-منتج مطبّعة → وسم قسم. يوسّع البحث ليرجّع كل متاجر القسم.';

CREATE INDEX IF NOT EXISTS idx_search_concepts_term       ON search_concepts (term);
CREATE INDEX IF NOT EXISTS idx_search_concepts_term_trgm  ON search_concepts USING gin (term gin_trgm_ops);

-- ═══════════════════════════════════════════════════════════════════════════
-- 2) blog_bridge  —  صفّ واحد لكل مقال ضيّق الموضوع (يبدأ فارغاً)
--    الاحتياط الأخير في البحث: لا اسم متجر ولا مفهوم → FTS على نصوص المقالات،
--    نُرجع متاجر أعلى ١–٣ مقالات مع via_article. يملؤه scripts/build_blog_bridge.py.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS blog_bridge (
    slug        TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '',
    store_ids   TEXT NOT NULL DEFAULT '',            -- '{id,id}' — متاجر يذكرها المقال
    body_norm   TEXT NOT NULL DEFAULT '',            -- عنوان+مقتطف+متن، مطبّع (normalize_ar)
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE blog_bridge IS
  'جسر المدوّنة (صفّ/مقال): FTS على body_norm → متاجر المقال. يملؤه scripts/build_blog_bridge.py من ريبو الويب.';

-- فهرس FTS على النصّ المطبّع مسبقاً (config=simple: لا تحليل صرفي عربي مدمج،
-- والتطبيع يعوّض توحيد صور الحرف). الاستعلام:
--   to_tsvector('simple', body_norm) @@ plainto_tsquery('simple', normalize_ar(:q))
CREATE INDEX IF NOT EXISTS idx_blog_bridge_fts
    ON blog_bridge USING gin (to_tsvector('simple', body_norm));

-- ═══════════════════════════════════════════════════════════════════════════
-- 3) بذرة search_concepts  (مولّدة من arabic_search.CONCEPT_SEED)
-- ═══════════════════════════════════════════════════════════════════════════
"""


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main() -> None:
    rows = build_seed_rows()
    rows.sort(key=lambda r: (r[1], -r[2], r[0]))

    lines = [HEADER]
    lines.append("INSERT INTO search_concepts (term, canonical_tag, weight, source) VALUES")
    values = [
        f"  ({_sql_str(term)}, {_sql_str(tag)}, {weight:.1f}, 'curated')"
        for term, tag, weight in rows
    ]
    lines.append(",\n".join(values))
    lines.append("ON CONFLICT (term, canonical_tag) DO NOTHING;")
    lines.append("")
    lines.append(f"-- {len(rows)} صفّ بذرة، تغطّي "
                 f"{len({r[1] for r in rows})} وسماً canonical.")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}  ({len(rows)} seed rows, "
          f"{len({r[1] for r in rows})} canonical tags)")


if __name__ == "__main__":
    main()
