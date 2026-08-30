---
name: search_intelligence_layer
description: بحث الموقع صار ٤ طبقات (تطبيع عربي + search_concepts + blog_bridge) — /coupons/search أعيد كتابته، migration_070، وسكربتان يولّدان الجدولين
metadata: 
  node_type: memory
  type: project
  originSessionId: af5f88b2-ef39-4521-add3-b8b3d0c591c9
  modified: 2026-08-30T15:39:10.506Z
---

**السياق:** `direct_search` أثبت حيّاً (٢٠٢٦-٠٨-٣٠) أن البحث كان يطابق هويّة المتجر
فقط: «أحذية» → `user_found=FALSE` بينما الوسم `أحذيه`؛ «خواتم/الخزف/وجبات» صفر نتائج.
طلب المالك: بحث ذكي — اسم متجر (+ الأقرب عند الخطأ)، قسم (+ إملاء `أزياء/ازياء`)،
وكلمة نادرة في مقال → متاجر ذلك المقال.

**ما نُفِّذ (كود مدفوع، الجداول تنتظر تشغيل المالك للميقريشن):**

| | الملف | الدور |
|---|---|---|
| تطبيع | `api/utils/arabic_search.py::normalize_ar` | أإآٱ→ا، ى→ي، ة→ه، تطويل/تشكيل. **نفس قواعد** `api/seo/matcher._normalize_ar` و web `lib/seo/category-content.normalizeTag` — الثلاثة يجب أن تتطابق. `_norm_sql()` في `coupons.py` يكرّرها SQL بلا دالة DB (توافق نشر قبل الميقريشن) |
| ط٢ مفاهيم | جدول `search_concepts(term,canonical_tag,weight,source)` | مرادف/إملاء/كلمة-منتج مطبّعة → وسم في `master.store_tags`. **مصدر الحقيقة بعد البذر** (يُحرَّر من اللوحة). البذرة `arabic_search.CONCEPT_SEED` (~327 صفّ، ٤٢ وسماً، فيها صفّ هويّة لكل وسم). `weight` 1.0 مرادف قسم / 0.6 كلمة منتج |
| ط٣ مدوّنة | جدول `blog_bridge(slug PK,title,category,store_ids,body_norm)` | **صفّ/مقال** (لا صفّ/كلمة — تلك أنتجت ٩٤ألف صفّ ضجيج). FTS `to_tsvector('simple',body_norm) @@ plainto_tsquery`. احتياط أخير: يُرجع متاجر أعلى ٣ مقالات + `via_article` |

**`/coupons/search` أعيد كتابته** (`api/routers/coupons.py`): تدرّج
name_hit(1) → name_score≥.4(2) → concept≥1(3) → concept>0(4) → blog(5) → bio(6) →
fuzzy>.25(7)، وداخل كل تدرّج `popularity_score DESC`. كل صفّ يحمل `match_type` +
`via_article` (أُضيفا لـ`StoreResult` و web `Store`). كلا اللوكاب محروسان بـ
`to_regclass` — يُتخطّيان بأمان قبل الميقريشن.

**الويب:** `app/stores/page.tsx` عند `?q=` يستدعي `searchStores` (الـAPI) بدل الفلترة
client-side على قائمة خام؛ `StoresListing` بـprop `preRanked` (لا يُعيد فلترة/فرز،
يُخفي شريط الفرز). `SearchBar` كان يستدعي الـAPI أصلاً فورث التحسين.

**التوليد (بعد أي تغيير):**
- `python -m scripts.gen_migration_070` → يعيد كتابة `migration_070_search_intelligence.sql` من البذرة (idempotent، `ON CONFLICT DO NOTHING`).
- `python -m scripts.build_blog_bridge` → dry-run + `data/blog_bridge_preview.json` (١٤٠٧ مقال، ٥٩ متجراً). `--write` = `TRUNCATE`+ملء (كتابة DB، إذن المالك). يقرأ `lib/blog.ts` نصّاً (regex، لا import — يُفجّر tsc).

**تشغيل المالك المطلوب:** (١) `psql "$DATABASE_URL" -f migration_070_search_intelligence.sql`
(٢) `python -m scripts.build_blog_bridge --write`. بدونهما البحث يعمل بالتطبيع فقط
(«أحذية» يجد ٦ عبر النبذة بدل ٠، لكن لا توسيع أقسام).

يكمّل [[seo_category_query_alignment]] (وزن مفردات الطلب) و [[occasion_page_relevance_filter]]
(`store_tags` تصنيف كتالوج) و [[reconcile_web_repo_separately]].
