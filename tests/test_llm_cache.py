"""
3 اختبارات LLM cache — exact-hash matching, miss path, expiry.

نستخدم البنية الفعلية للجدول:
    - prompt_hash BYTEA (SHA-256)
    - purpose = 'directive' (ثابت)
    - expires_at يتحكم بالـ TTL (6 ساعات افتراضياً)
"""
from __future__ import annotations

import hashlib

import pytest


@pytest.fixture
def clean_llm_cache(db_conn):
    """ينظّف صفوف الاختبار من llm_semantic_cache قبل وبعد."""
    # نستخدم prompt_text كعلامة (يبدأ بـ 'pytest_')
    sql = "DELETE FROM llm_semantic_cache WHERE prompt_text LIKE 'pytest_%'"
    with db_conn.cursor() as cur:
        cur.execute(sql)
    db_conn.commit()
    yield
    with db_conn.cursor() as cur:
        cur.execute(sql)
    db_conn.commit()


def _hash_text(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _insert_cache(db_conn, prompt_text: str, response: dict,
                  ttl_hours_from_now: int = 6):
    """يحقن صفاً مع expires_at قابل للتحكم (موجب = ساري، سالب = منتهي)."""
    import json
    from api.utils.llm_service import PURPOSE, psycopg2_bytea
    h = _hash_text(prompt_text)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO llm_semantic_cache
                (purpose, prompt_text, prompt_hash, response_text, response_json,
                 model, tokens_input, tokens_output, expires_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, 'pytest-model', 100, 50,
                    NOW() + (%s || ' hours')::interval)
            ON CONFLICT (prompt_hash) DO UPDATE SET
                expires_at = EXCLUDED.expires_at,
                response_text = EXCLUDED.response_text,
                response_json = EXCLUDED.response_json
            """,
            (PURPOSE, prompt_text, psycopg2_bytea(h),
             json.dumps(response, ensure_ascii=False),
             json.dumps(response, ensure_ascii=False),
             str(ttl_hours_from_now)),
        )
    db_conn.commit()
    return h


def test_llm_cache_hit_returns_stored(db_conn, clean_llm_cache):
    """عند وجود صف ساري، _try_cache يرجع البيانات ويرفع hit_count."""
    from api.utils.llm_service import _try_cache
    prompt = "pytest_cache_hit_prompt"
    h = _insert_cache(db_conn, prompt, {"summary": "محفوظ"}, ttl_hours_from_now=5)

    result = _try_cache(h)
    assert result is not None
    assert result["response_json"]["summary"] == "محفوظ"

    # نتحقق أن hit_count ارتفع
    with db_conn.cursor() as cur:
        cur.execute("SELECT hit_count FROM llm_semantic_cache WHERE prompt_hash = %s",
                    (h,))
        hits = cur.fetchone()[0]
    assert hits >= 1


def test_llm_cache_miss_returns_none(db_conn, clean_llm_cache):
    """مفتاح غير موجود → None."""
    from api.utils.llm_service import _try_cache
    missing = _hash_text("pytest_definitely_not_cached_xxx")
    assert _try_cache(missing) is None


def test_llm_cache_expired_returns_none(db_conn, clean_llm_cache):
    """صف expires_at < NOW() لا يُعتبر hit."""
    from api.utils.llm_service import _try_cache
    prompt = "pytest_expired_prompt"
    # عمر سالب = expires_at في الماضي
    h = _insert_cache(db_conn, prompt, {"summary": "قديم"}, ttl_hours_from_now=-1)

    assert _try_cache(h) is None, "صف منتهي ما يجب أن يُرجَع"
