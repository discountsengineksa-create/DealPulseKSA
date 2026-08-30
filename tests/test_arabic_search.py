"""
اختبارات طبقة البحث الذكي — تطبيع عربي + سلامة بذرة قاموس المفاهيم.
لا تحتاج قاعدة بيانات (منطق نقيّ).
"""
from __future__ import annotations

from api.utils.arabic_search import CONCEPT_SEED, build_seed_rows, normalize_ar, strip_ws


def test_normalize_unifies_letter_forms():
    assert normalize_ar("أحذية") == "احذيه"          # الوسم في الكتالوج «أحذيه»
    assert normalize_ar("نمشى") == normalize_ar("نمشي")
    assert normalize_ar("ازياء") == normalize_ar("أزياء")
    assert normalize_ar("  عَسَل  ") == "عسل"          # تشكيل + فراغات
    assert normalize_ar(None) == ""


def test_strip_ws_collapses_spaces():
    assert strip_ws(normalize_ar("ترند يول")) == "ترنديول"


def test_seed_rows_are_normalized_and_unique():
    rows = build_seed_rows()
    assert len(rows) > 250
    seen = set()
    for term, tag, weight in rows:
        assert term == normalize_ar(term), f"صفّ غير مطبّع: {term!r}"
        assert len(term) >= 2
        assert 0 < weight <= 1.0
        assert (term, tag) not in seen, f"تكرار: {(term, tag)}"
        seen.add((term, tag))


def test_every_concept_target_has_identity_row():
    """كل وسم canonical في القاموس يجب أن يطابق نفسه (حتى يجد الباحثُ القسمَ
    بلا مرادف صريح: «ازياء» → «أزياء»)."""
    rows = build_seed_rows()
    by_term = {(t, tag) for t, tag, _ in rows}
    targets = {tag for targets in CONCEPT_SEED.values() for tag, _ in targets}
    for tag in targets:
        assert (normalize_ar(tag), tag) in by_term, f"لا صفّ هويّة لـ {tag!r}"


def test_known_saudi_product_words_route_to_a_category():
    """كلمات المنتج التي فشلت في direct_search حيّاً يجب أن تُحلّ لقسم."""
    rows = build_seed_rows()
    idx: dict[str, set[str]] = {}
    for term, tag, _ in rows:
        idx.setdefault(term, set()).add(tag)
    for word, expected in [
        ("فحمات", "قطع غيار سيارات"),
        ("خواتم", "مجوهرات"),
        ("الخزف", "المنزل"),
        ("جزم", "أحذيه"),
    ]:
        assert expected in idx.get(normalize_ar(word), set()), word
