"""
محرّك بناء الشرائح (Audience Segment Engine).

يحوّل تعريف شريحة (JSON tree) إلى SQL آمن باستخدام psycopg2 params،
ويوفّر الاستعلامات: count / fetch / sample.

═══ الفلسفة ═══
- صفر f-string على قيم المستخدم → كل قيمة تمر عبر %s (params list).
- whitelist صارم لكل اسم عمود / اسم عملية / action_type / context.
- channel-aware: telegram يفلتر على bot_users، email على web_users.
- linked users: لو bot_user مربوط بحساب موقع، نشاطه الويبي يُحسب له تلقائياً
  في قواعد event/aggregate (نفس فلسفة صفحة تحليل المستخدمين).

═══ بنية الشريحة JSON ═══

{
  "version": 1,
  "logic": "or",                          # بين المجموعات (Facebook style)
  "groups": [
    {
      "logic": "and",                     # داخل المجموعة
      "rules": [
        # ───── Attribute ─────────────────────────────────────────────────
        {"type": "attribute", "field": "lang",
         "op": "=", "value": "ar"},

        # عُمر (مدى) — value=[min, max]
        {"type": "attribute", "field": "age",
         "op": "between", "value": [18, 34]},

        # مفضّل متجر محدد
        {"type": "attribute", "field": "favorite_store",
         "op": "=", "value": "noon"},

        # عدد مفضلاته ≥ 3
        {"type": "attribute", "field": "fav_count",
         "op": ">=", "value": 3},

        # عنده إيميل
        {"type": "attribute", "field": "has_email",
         "op": "=", "value": True},

        # ───── Event (حدث/لم يحدث) ──────────────────────────────────────
        # نسخ كوبون لمتجر "نون" آخر 30 يوم
        {"type": "event", "action": "copy_coupon",
         "entity_type": "store", "entity_value": "noon",
         "context": "any", "window": {"type": "last_days", "days": 30}},

        # شاف ترند يومي لأي متجر
        {"type": "event", "action": "view_store",
         "entity_type": "any", "context": "trend_daily",
         "window": {"type": "all"}},

        # بحث عن كلمة محددة
        {"type": "event", "action": "search_keyword",
         "entity_value": "ايفون",
         "window": {"type": "last_days", "days": 7}},

        # ───── Aggregate (عدّاد بعتبة) ──────────────────────────────────
        # نسخ متجر "نون" ≥ 3 آخر 30 يوم
        {"type": "aggregate", "action": "copy_coupon",
         "entity_type": "store", "entity_value": "noon",
         "context": "any",
         "op": ">=", "threshold_type": "absolute", "value": 3,
         "window": {"type": "last_days", "days": 30}},

        # أعلى 10% من المستخدمين نسخاً
        {"type": "aggregate", "action": "copy_coupon",
         "entity_type": "any", "context": "any",
         "threshold_type": "percentile_top", "value": 10,
         "window": {"type": "last_days", "days": 30}},

        # ───── Temporal (الزمن) ─────────────────────────────────────────
        # سجّل في آخر 7 أيام
        {"type": "temporal", "field": "joined_at",
         "op": ">=", "value_days": 7},

        # نشط في الأسبوع الماضي (آخر ظهور)
        {"type": "temporal", "field": "last_seen",
         "op": ">=", "value_days": 7}
      ]
    }
  ]
}

═══ negate ═══
أي قاعدة فيها "negate": true تُلفّ بـ NOT (...) — يدعم "ما فعل X".

═══ الاستخدام ═══
    from api.audience_engine import (
        count_audience, fetch_audience, sample_audience, build_sql
    )
    n = count_audience(conn, "telegram", rules)
    rows = fetch_audience(conn, "email", rules, limit=10_000)
    sample = sample_audience(conn, "telegram", rules, n=10)
"""
from __future__ import annotations

import json
from typing import Any, Iterable

# ════════════════════════════════════════════════════════════════════════════
# Whitelists — دفاع الأول ضد SQL injection: كل اسم عمود/عملية يجب أن يطابق هنا
# ════════════════════════════════════════════════════════════════════════════

_OPS_MAP = {
    "=":  "=",
    "==": "=",
    "!=": "<>",
    "<>": "<>",
    ">":  ">",
    ">=": ">=",
    "<":  "<",
    "<=": "<=",
}
_NUMERIC_OPS    = {"=", "!=", ">", ">=", "<", "<="}
_TEXT_OPS       = {"=", "!="}
_RANGE_OPS      = {"between"}
_IN_OPS         = {"in"}

_ACTION_TYPES = {
    "copy_coupon", "click_link", "search", "view_store", "view_tag",
}

# سياق الحدث: NULL = الكل، أو سياق محدد
_CONTEXT_CLAUSES = {
    "any":           None,
    "trend_daily":   "al.details = 'trend:daily'",
    "trend_weekly":  "al.details = 'trend:weekly'",
    "trend_any":     "al.details LIKE 'trend:%'",
    "story":         "al.story_view_id IS NOT NULL",
    "card":          "(al.details IS NULL OR (al.details NOT LIKE 'trend:%' AND al.story_view_id IS NULL))",
}

_ATTRIBUTE_FIELDS_DIRECT = {
    # field_name -> {channel: SQL expression}
    "lang": {
        "tg":  "bu.lang",
        "web": "wu.lang",
    },
    "country": {
        "tg":  "bu.country",
        "web": "cty.city",  # web_users ما عنده country مباشر — نقفل عليه عبر cty لاحقاً
    },
    "gender": {
        # الجنس على web_users فقط؛ في تيليجرام يُسحب من المربوط w3 إن وُجد
        "tg":  "w3.gender",
        "web": "wu.gender",
    },
    "city": {
        "tg":  "cty.city",
        "web": "cty.city",
    },
    "age": {
        # محسوبة من birth_date — على web_users (tg → w3 المربوط)
        "tg":  "EXTRACT(YEAR FROM AGE(w3.birth_date))::int",
        "web": "EXTRACT(YEAR FROM AGE(wu.birth_date))::int",
    },
}

# attributes صفات/أعلام (Bool)
_ATTRIBUTE_FIELDS_BOOL = {
    "is_linked": {
        "tg":  "(w3.id IS NOT NULL)",
        "web": "(wu.telegram_username IS NOT NULL AND wu.telegram_username <> '')",
    },
    "has_email": {
        "tg":  "(w3.email IS NOT NULL AND w3.email <> '')",
        "web": "(wu.email IS NOT NULL AND wu.email <> '')",
    },
    "has_phone": {
        "tg":  "(w3.phone_number IS NOT NULL AND w3.phone_number <> '')",
        "web": "(wu.phone_number IS NOT NULL AND wu.phone_number <> '')",
    },
    "has_birth_date": {
        "tg":  "(w3.birth_date IS NOT NULL)",
        "web": "(wu.birth_date IS NOT NULL)",
    },
    # ── الملف المكتمل ─────────────────────────────────────────────────────
    # مكتمل = يوزر تيليجرام (الربط أساسي) + إيميل + جوال + تاريخ ميلاد + جنس
    # ناقص = أي واحد من الخمسة فاضي
    "profile_complete": {
        "tg":  ("(bu.username IS NOT NULL AND bu.username <> '' "
                " AND w3.id IS NOT NULL "
                " AND w3.email IS NOT NULL AND w3.email <> '' "
                " AND w3.phone_number IS NOT NULL AND w3.phone_number <> '' "
                " AND w3.birth_date IS NOT NULL "
                " AND w3.gender IS NOT NULL AND w3.gender <> '')"),
        "web": ("(wu.telegram_username IS NOT NULL AND wu.telegram_username <> '' "
                " AND wu.email IS NOT NULL AND wu.email <> '' "
                " AND wu.phone_number IS NOT NULL AND wu.phone_number <> '' "
                " AND wu.birth_date IS NOT NULL "
                " AND wu.gender IS NOT NULL AND wu.gender <> '')"),
    },
}

# attribute fields special (تتحوّل لـ EXISTS أو subquery)
_ATTRIBUTE_SPECIAL = {
    "favorite_store", "favorite_category", "fav_count",
    "viewed_categories",
}

# Temporal fields
_TEMPORAL_FIELDS = {
    "joined_at": {
        "tg":  "bu.joined_at",
        "web": "wu.created_at",
    },
    "last_seen": {
        "tg":  "bu.last_seen",
        "web": "wu.last_seen",
    },
}

# نوع العتبة (aggregate)
_THRESHOLD_TYPES = {
    "absolute",         # value = رقم مطلق
    "percentile_top",   # value = أعلى N%
    "percentile_bot",   # value = أقل N%
    "top_n",            # value = أعلى N شخصاً
    "above_mean",       # value يُتجاهَل، نقارن بالمتوسط
    "below_mean",
}


# ════════════════════════════════════════════════════════════════════════════
# Channel Context — كل قناة لها مساراتها لربط الجداول
# ════════════════════════════════════════════════════════════════════════════

# عند بناء كلوزات event/aggregate لمستخدم تيليجرام مربوط، نحسب نشاطه
# في البوت/الميني-ويب + نشاطه على الموقع المربوط بـ w3.id (نفس فلسفة
# صفحة تحليل المستخدمين). للموقع غير المربوط: web فقط.

def _al_user_clause(channel: str) -> tuple[str, str]:
    """يرجّع (user_id_expr, source_clause) لـ action_logs حسب القناة.

    للقناة tg: يشمل نشاط الموقع للمربوطين عبر OR.
    """
    if channel == "tg":
        return (
            "al.user_id",
            "((al.user_id = bu.telegram_id AND al.source IN ('bot','telegram_miniapp')) "
            " OR (w3.id IS NOT NULL AND al.user_id = w3.id AND al.source = 'web'))"
        )
    return ("al.user_id", "(al.user_id = wu.id AND al.source = 'web')")


def _ds_user_clause(channel: str) -> str:
    """direct_search platform/user — كل قناة لها مسارها."""
    if channel == "tg":
        return ("((ds.user_id = bu.telegram_id AND ds.platform IN ('TelegramBot','Miniapp')) "
                " OR (w3.id IS NOT NULL AND ds.user_id = w3.id AND ds.platform = 'Web'))")
    return "(ds.user_id = wu.id AND ds.platform = 'Web')"


def _uf_user_clause(channel: str) -> str:
    """user_favorites lookup — مربوط = الاثنين، غير مربوط = الموقع فقط."""
    if channel == "tg":
        return ("(uf.telegram_id = bu.telegram_id "
                " OR (w3.id IS NOT NULL AND uf.web_user_id = w3.id))")
    return "(uf.web_user_id = wu.id)"


def _sv_user_clause(channel: str) -> str:
    """story_views user lookup."""
    if channel == "tg":
        return ("(sv.tg_user_id = bu.telegram_id "
                " OR (w3.id IS NOT NULL AND sv.web_user_id = w3.id))")
    return "(sv.web_user_id = wu.id)"


# ════════════════════════════════════════════════════════════════════════════
# Base Queries — هيكل SELECT الأساسي لكل قناة
# ════════════════════════════════════════════════════════════════════════════

_BASE_TG = """
SELECT bu.telegram_id::text                                   AS user_id,
       bu.username                                            AS handle,
       COALESCE(w3.display_name, bu.name_en, bu.username)     AS name,
       w3.email                                               AS email,
       w3.phone_number                                        AS phone,
       bu.lang                                                AS lang,
       bu.last_seen                                           AS last_seen,
       cty.city                                               AS city,
       (w3.id IS NOT NULL)                                    AS is_linked
FROM bot_users bu
LEFT JOIN LATERAL (
    SELECT id, display_name, email, phone_number, gender, birth_date
    FROM web_users w
    WHERE w.telegram_username IS NOT NULL
      AND LOWER(w.telegram_username) = LOWER(bu.username)
    LIMIT 1
) w3 ON TRUE
LEFT JOIN LATERAL (
    SELECT city FROM action_logs al
    WHERE al.user_id = bu.telegram_id
      AND al.source IN ('bot','telegram_miniapp')
      AND al.city IS NOT NULL AND al.city <> ''
      AND al.is_proxy IS NOT TRUE AND al.is_datacenter IS NOT TRUE
    ORDER BY al.action_time DESC LIMIT 1
) cty ON TRUE
WHERE bu.deleted_at IS NULL
  AND bu.telegram_blocked_at IS NULL   -- يستبعد محظورين البوت تلقائياً
"""

_BASE_WEB_UNLINKED = """
SELECT wu.id::text                                            AS user_id,
       wu.telegram_username                                   AS handle,
       wu.display_name                                        AS name,
       wu.email                                               AS email,
       wu.phone_number                                        AS phone,
       wu.lang                                                AS lang,
       wu.last_seen                                           AS last_seen,
       cty.city                                               AS city,
       FALSE                                                  AS is_linked
FROM web_users wu
LEFT JOIN LATERAL (
    SELECT city FROM action_logs al
    WHERE al.user_id = wu.id AND al.source = 'web'
      AND al.city IS NOT NULL AND al.city <> ''
      AND al.is_proxy IS NOT TRUE AND al.is_datacenter IS NOT TRUE
    ORDER BY al.action_time DESC LIMIT 1
) cty ON TRUE
WHERE TRUE
  -- "غير مربوط" = إما بلا حساب تليجرام، أو مربوط بحساب محظور/محذوف
  -- (المحظورون يُعتبرون غير مربوطين هنا ليصلهم البريد بدل تليجرام المغلق)
  AND (wu.telegram_username IS NULL OR LOWER(wu.telegram_username) NOT IN (
       SELECT LOWER(username) FROM bot_users
       WHERE username IS NOT NULL AND deleted_at IS NULL
         AND telegram_blocked_at IS NULL))
"""

_BASE_WEB_ALL = """
SELECT wu.id::text                                            AS user_id,
       wu.telegram_username                                   AS handle,
       wu.display_name                                        AS name,
       wu.email                                               AS email,
       wu.phone_number                                        AS phone,
       wu.lang                                                AS lang,
       wu.last_seen                                           AS last_seen,
       cty.city                                               AS city,
       (wu.telegram_username IS NOT NULL AND wu.telegram_username <> '') AS is_linked
FROM web_users wu
LEFT JOIN LATERAL (
    SELECT city FROM action_logs al
    WHERE al.user_id = wu.id AND al.source = 'web'
      AND al.city IS NOT NULL AND al.city <> ''
      AND al.is_proxy IS NOT TRUE AND al.is_datacenter IS NOT TRUE
    ORDER BY al.action_time DESC LIMIT 1
) cty ON TRUE
WHERE TRUE
"""


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _resolve_op(op: str) -> str:
    """يحوّل عملية المستخدم لـSQL آمنة (من whitelist)."""
    if op not in _OPS_MAP:
        raise ValueError(f"عملية غير مدعومة: {op!r}")
    return _OPS_MAP[op]


def _window_clause(window: dict | None, time_col: str = "al.action_time") -> tuple[str, list]:
    """يبني clause لنافذة زمنية على عمود وقت محدد.

    window أنواع:
      - None / {"type":"all"} → بدون قيد
      - {"type":"last_days","days":N} → time_col >= NOW() - INTERVAL 'N days'
      - {"type":"between","from":"YYYY-MM-DD","to":"YYYY-MM-DD"} → بين تاريخين

    إضافات مشتركة (يمكن دمجها مع أي نوع أعلاه):
      - hour_from / hour_to (0..23) → فلتر ساعات اليوم بتوقيت الرياض
    """
    if not window:
        return "", []
    wtype = window.get("type", "all")
    clauses: list[str] = []
    params: list = []

    # الجزء الأول: نطاق التاريخ
    if wtype == "last_days":
        days = int(window.get("days", 30))
        if days < 0 or days > 3650:
            raise ValueError(f"days out of range: {days}")
        clauses.append(f"{time_col} >= NOW() - (%s || ' days')::INTERVAL")
        params.append(str(days))
    elif wtype == "between":
        clauses.append(f"{time_col} >= %s")
        clauses.append(f"{time_col} < %s")
        params.append(window.get("from"))
        params.append(window.get("to"))
    elif wtype != "all":
        raise ValueError(f"نوع نافذة غير مدعوم: {wtype!r}")

    # الجزء الثاني: نطاق الساعات (اختياري، يُضاف فوق أي نوع)
    h_from = window.get("hour_from")
    h_to   = window.get("hour_to")
    if h_from is not None and h_to is not None:
        try:
            hf = max(0, min(23, int(h_from)))
            ht = max(0, min(23, int(h_to)))
        except (ValueError, TypeError):
            hf = ht = None
        if hf is not None and ht is not None:
            hour_expr = (f"EXTRACT(HOUR FROM ({time_col}) "
                         f"AT TIME ZONE 'Asia/Riyadh')")
            if hf <= ht:
                clauses.append(f"{hour_expr} BETWEEN %s AND %s")
                params += [hf, ht]
            else:  # يلتف عبر منتصف الليل (مثلاً 22 → 06)
                clauses.append(f"({hour_expr} >= %s OR {hour_expr} <= %s)")
                params += [hf, ht]

    if not clauses:
        return "", []
    return " AND " + " AND ".join(clauses), params


# ════════════════════════════════════════════════════════════════════════════
# Rule Builders — كل دالة ترجع (sql_fragment, params)
# ════════════════════════════════════════════════════════════════════════════

def _build_attribute(rule: dict, channel: str) -> tuple[str, list]:
    field = rule.get("field")
    if not field:
        raise ValueError("attribute rule بحاجة field")
    op = rule.get("op", "=")
    value = rule.get("value")

    # ── Direct (column expression) ──────────────────────────────────────
    if field in _ATTRIBUTE_FIELDS_DIRECT:
        col_expr = _ATTRIBUTE_FIELDS_DIRECT[field][channel]
        # between مدى رقمي
        if op == "between":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError("between تحتاج value = [min, max]")
            return f"({col_expr} BETWEEN %s AND %s)", [value[0], value[1]]
        # in قائمة قيم
        if op == "in":
            if not isinstance(value, (list, tuple)) or not value:
                raise ValueError("in تحتاج value = [..]")
            placeholders = ", ".join(["%s"] * len(value))
            return f"({col_expr} IN ({placeholders}))", list(value)
        sql_op = _resolve_op(op)
        return f"({col_expr} {sql_op} %s)", [value]

    # ── Bool flags ──────────────────────────────────────────────────────
    if field in _ATTRIBUTE_FIELDS_BOOL:
        flag_expr = _ATTRIBUTE_FIELDS_BOOL[field][channel]
        # value=True → الشرط كما هو، False → النفي
        want_true = bool(value)
        return (f"({flag_expr})", []) if want_true else (f"(NOT {flag_expr})", [])

    # ── Specials (EXISTS / subqueries) ──────────────────────────────────
    if field == "favorite_store":
        uf_user = _uf_user_clause(channel)
        return (
            f"EXISTS (SELECT 1 FROM user_favorites uf "
            f"WHERE {uf_user} AND uf.kind = 'store' AND uf.store_id = %s)",
            [value],
        )

    if field == "favorite_category":
        uf_user = _uf_user_clause(channel)
        return (
            f"EXISTS (SELECT 1 FROM user_favorites uf "
            f"WHERE {uf_user} AND uf.kind = 'category' AND uf.category_name = %s)",
            [value],
        )

    if field == "fav_count":
        uf_user = _uf_user_clause(channel)
        if op == "between":
            return (
                f"((SELECT COUNT(*) FROM user_favorites uf WHERE {uf_user}) BETWEEN %s AND %s)",
                [value[0], value[1]],
            )
        sql_op = _resolve_op(op)
        return (
            f"((SELECT COUNT(*) FROM user_favorites uf WHERE {uf_user}) {sql_op} %s)",
            [int(value)],
        )

    raise ValueError(f"حقل attribute غير معروف: {field!r}")


def _action_filter_clauses(rule: dict, channel: str) -> tuple[list[str], list]:
    """يبني WHERE clauses مشتركة لـ event/aggregate (action_type + entity + context).

    يرجّع (clauses_list, params_list).
    """
    clauses: list[str] = []
    params: list = []

    action = rule.get("action")
    if action == "search_keyword":
        # هذا حالة خاصة على direct_search
        return ([], [])

    if action and action not in _ACTION_TYPES:
        raise ValueError(f"action غير مدعوم: {action!r}")
    if action:
        clauses.append("al.action_type = %s")
        params.append(action)

    entity_type = rule.get("entity_type", "any")
    entity_value = rule.get("entity_value")

    if entity_type == "store" and entity_value:
        clauses.append("al.store_id = %s")
        params.append(entity_value)
    elif entity_type == "category" and entity_value:
        # القسم: action_logs لا تخزّن tag بشكل مباشر إلا في view_tag (details='tag:X')
        # لو الفعل view_tag → فلتر على details. غير ذلك → عبر متاجر القسم.
        if action == "view_tag":
            clauses.append("split_part(al.details, 'tag:', 2) = %s")
            params.append(entity_value)
        else:
            clauses.append(
                "al.store_id IN (SELECT m.store_id FROM master m, "
                "unnest(string_to_array(trim(both '{}' from COALESCE(m.store_tags,'')), ',')) AS t "
                "WHERE TRIM(t) = %s)"
            )
            params.append(entity_value)

    context = rule.get("context", "any")
    if context not in _CONTEXT_CLAUSES:
        raise ValueError(f"context غير مدعوم: {context!r}")
    ctx_clause = _CONTEXT_CLAUSES[context]
    if ctx_clause:
        clauses.append(ctx_clause)

    return (clauses, params)


def _build_event(rule: dict, channel: str) -> tuple[str, list]:
    """قاعدة event: هل المستخدم فعل (أو لم يفعل) X خلال نافذة؟"""
    action = rule.get("action")
    user_id_expr, source_clause = _al_user_clause(channel)

    # ─ search_keyword: حالة خاصة على direct_search ─
    if action == "search_keyword":
        keyword = rule.get("entity_value", "")
        ds_user = _ds_user_clause(channel)
        win_sql, win_params = _window_clause(rule.get("window"), "ds.search_date")
        clause = (
            f"EXISTS (SELECT 1 FROM direct_search ds "
            f"WHERE {ds_user} "
            f"AND LOWER(TRIM(ds.search_keyword)) = LOWER(%s)"
            f"{win_sql})"
        )
        return clause, [keyword] + win_params

    # ─ view_story: على story_views (مستقل عن action_logs) ─
    if action == "view_story":
        sv_user = _sv_user_clause(channel)
        was_trending = rule.get("was_trending")  # True/False/None
        flag_clause = ""
        flag_params: list = []
        if was_trending is True:
            flag_clause = " AND sv.was_trending = TRUE"
        elif was_trending is False:
            flag_clause = " AND sv.was_trending = FALSE"
        entity_value = rule.get("entity_value")
        store_clause = ""
        if entity_value:
            store_clause = " AND sv.store_id = %s"
            flag_params.append(entity_value)
        win_sql, win_params = _window_clause(rule.get("window"), "sv.viewed_at")
        clause = (
            f"EXISTS (SELECT 1 FROM story_views sv "
            f"WHERE {sv_user}{flag_clause}{store_clause}{win_sql})"
        )
        return clause, flag_params + win_params

    # ─ default: action_logs ─
    sub_clauses, sub_params = _action_filter_clauses(rule, channel)
    win_sql, win_params = _window_clause(rule.get("window"), "al.action_time")
    where_parts = [source_clause] + sub_clauses
    where_sql = " AND ".join(where_parts)
    clause = (
        f"EXISTS (SELECT 1 FROM action_logs al "
        f"WHERE {where_sql}{win_sql})"
    )
    return clause, sub_params + win_params


def _build_aggregate(rule: dict, channel: str) -> tuple[str, list]:
    """قاعدة aggregate: عدّ تفاعلات بعتبة (absolute / percentile / top_n / mean)."""
    threshold_type = rule.get("threshold_type", "absolute")
    if threshold_type not in _THRESHOLD_TYPES:
        raise ValueError(f"threshold_type غير مدعوم: {threshold_type!r}")

    user_id_expr, source_clause = _al_user_clause(channel)
    sub_clauses, sub_params = _action_filter_clauses(rule, channel)
    win_sql, win_params = _window_clause(rule.get("window"), "al.action_time")

    # عبارة العدّ لكل مستخدم
    where_parts = [source_clause] + sub_clauses
    where_sql = " AND ".join(where_parts)
    count_expr = (
        f"(SELECT COUNT(*) FROM action_logs al WHERE {where_sql}{win_sql})"
    )
    count_params = sub_params + win_params

    if threshold_type == "absolute":
        op = rule.get("op", ">=")
        sql_op = _resolve_op(op)
        value = int(rule.get("value", 0))
        return f"({count_expr} {sql_op} %s)", count_params + [value]

    if threshold_type == "above_mean":
        # المتوسط على كل المستخدمين اللي عندهم >= 1 من هذه الحركة
        mean_sub = (
            f"(SELECT AVG(c) FROM (SELECT COUNT(*) AS c FROM action_logs al2 "
            f"WHERE {where_sql.replace('al.', 'al2.')}"
            f"{win_sql.replace('al.', 'al2.')} "
            f"GROUP BY al2.user_id HAVING COUNT(*) >= 1) sub)"
        )
        # نضاعف params لأن المقارنة فيها نفس الشروط مرتين
        return f"({count_expr} > {mean_sub})", count_params + count_params

    if threshold_type == "below_mean":
        mean_sub = (
            f"(SELECT AVG(c) FROM (SELECT COUNT(*) AS c FROM action_logs al2 "
            f"WHERE {where_sql.replace('al.', 'al2.')}"
            f"{win_sql.replace('al.', 'al2.')} "
            f"GROUP BY al2.user_id HAVING COUNT(*) >= 1) sub)"
        )
        return f"({count_expr} < {mean_sub})", count_params + count_params

    if threshold_type in ("percentile_top", "percentile_bot", "top_n"):
        # نبني subquery يرجّع المستخدمين المؤهّلين، ونفلتر user_id IN منه
        pct_or_n = rule.get("value")
        # نشمل كل المستخدمين النشطين في هذه الحركة، نرتّبهم، ونقطع
        order_dir = "DESC" if threshold_type != "percentile_bot" else "ASC"
        ranked_sub = (
            f"SELECT al3.user_id FROM action_logs al3 WHERE "
            f"{where_sql.replace('al.', 'al3.')}"
            f"{win_sql.replace('al.', 'al3.')} "
            f"GROUP BY al3.user_id"
        )
        if threshold_type == "top_n":
            limit_clause = f"ORDER BY COUNT(*) {order_dir} LIMIT %s"
            extra_params = count_params + [int(pct_or_n)]
        else:
            # percentile: نأخذ النسبة من العدد الكلي
            ntile_value = max(1, min(100, int(pct_or_n)))
            ranked_sub = (
                f"SELECT user_id FROM (SELECT user_id, "
                f"NTILE(100) OVER (ORDER BY COUNT(*) {order_dir}) AS bucket "
                f"FROM action_logs al3 WHERE "
                f"{where_sql.replace('al.', 'al3.')}"
                f"{win_sql.replace('al.', 'al3.')} "
                f"GROUP BY user_id) sub WHERE bucket <= %s"
            )
            limit_clause = ""
            extra_params = count_params + [ntile_value]

        # ملاحظة: user_id في action_logs قد يكون tg_id (int) أو web_id (uuid).
        # نقارنه ضد الـ id الذي يعنينا في الـ outer query.
        if channel == "tg":
            target = "bu.telegram_id"
            # نُضمّن المربوط (نشاطه على الموقع كذلك يُحسب)
            return (
                f"({target} IN ({ranked_sub} {limit_clause}) "
                f"OR (w3.id IS NOT NULL AND w3.id IN ({ranked_sub} {limit_clause})))",
                extra_params + extra_params,  # subquery يتكرر
            )
        else:
            target = "wu.id"
            return (
                f"({target} IN ({ranked_sub} {limit_clause}))",
                extra_params,
            )

    raise ValueError(f"threshold_type unhandled: {threshold_type}")


def _build_temporal(rule: dict, channel: str) -> tuple[str, list]:
    """قاعدة temporal: مقارنة على عمود زمني (joined_at / last_seen)."""
    field = rule.get("field")
    if field not in _TEMPORAL_FIELDS:
        raise ValueError(f"حقل temporal غير معروف: {field!r}")
    col_expr = _TEMPORAL_FIELDS[field][channel]
    op = rule.get("op", ">=")

    value_days = rule.get("value_days")
    value_date = rule.get("value_date")

    if value_days is not None:
        days = int(value_days)
        if days < 0 or days > 3650:
            raise ValueError(f"value_days out of range: {days}")
        # value_days = الأيام الماضية. ">= N" أي «خلال آخر N يوم»
        if op in (">=", ">"):
            return f"({col_expr} >= NOW() - (%s || ' days')::INTERVAL)", [str(days)]
        if op in ("<=", "<"):
            return f"({col_expr} <= NOW() - (%s || ' days')::INTERVAL)", [str(days)]
        raise ValueError(f"عملية temporal غير مدعومة مع value_days: {op}")
    if value_date is not None:
        sql_op = _resolve_op(op)
        return f"({col_expr} {sql_op} %s)", [value_date]
    raise ValueError("temporal rule بحاجة value_days أو value_date")


# ════════════════════════════════════════════════════════════════════════════
# Composer: شجرة القواعد → WHERE clause
# ════════════════════════════════════════════════════════════════════════════

_BUILDERS = {
    "attribute": _build_attribute,
    "event":     _build_event,
    "aggregate": _build_aggregate,
    "temporal":  _build_temporal,
}


def _build_rules_clause(rules_json: dict, channel: str) -> tuple[str, list]:
    """يبني clause = WHERE شامل من شجرة القواعد. يرجّع (sql, params)."""
    if not rules_json or not isinstance(rules_json, dict):
        return ("TRUE", [])
    groups = rules_json.get("groups") or []
    if not groups:
        return ("TRUE", [])

    top_logic = (rules_json.get("logic") or "or").lower()
    if top_logic not in ("and", "or"):
        raise ValueError(f"logic غير مدعوم: {top_logic!r}")
    top_sep = f" {top_logic.upper()} "

    all_params: list = []
    group_sqls: list[str] = []

    for g_idx, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        rules = group.get("rules") or []
        if not rules:
            continue
        within_logic = (group.get("logic") or "and").lower()
        if within_logic not in ("and", "or"):
            raise ValueError(f"group logic غير مدعوم: {within_logic!r}")
        within_sep = f" {within_logic.upper()} "

        rule_sqls: list[str] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rtype = rule.get("type")
            if rtype not in _BUILDERS:
                raise ValueError(f"نوع قاعدة غير معروف: {rtype!r}")
            sql, params = _BUILDERS[rtype](rule, channel)
            if rule.get("negate"):
                sql = f"NOT ({sql})"
            rule_sqls.append(sql)
            all_params.extend(params)
        if rule_sqls:
            group_sqls.append(f"({within_sep.join(rule_sqls)})")

    if not group_sqls:
        return ("TRUE", [])
    return (f"({top_sep.join(group_sqls)})", all_params)


# ════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════

def build_sql(
    channel: str,
    rules_json: dict | None,
    *,
    select_mode: str = "rows",       # "rows" | "count" | "ids_only"
    limit: int | None = None,
    apply_exclusions: bool = True,
) -> tuple[str, list]:
    """
    يبني استعلام SQL كامل + params للقناة المطلوبة.

    channel: 'telegram' | 'email' | 'both'
    select_mode: 'rows' = كل الأعمدة، 'count' = COUNT(*) فقط، 'ids_only' = user_id فقط
    limit: حد أقصى للنتائج (None = الكل)
    apply_exclusions: استبعاد المستخدمين في broadcast_exclusions
    """
    if channel not in ("telegram", "email", "both"):
        raise ValueError(f"channel غير مدعوم: {channel!r}")

    rules_clause_tg,  params_tg  = _build_rules_clause(rules_json or {}, "tg")
    rules_clause_web, params_web = _build_rules_clause(rules_json or {}, "web")

    # استثناءات يدوية
    excl_tg = (" AND NOT EXISTS (SELECT 1 FROM broadcast_exclusions be "
               "WHERE be.user_identifier = bu.telegram_id::text "
               "AND be.channel IN ('telegram','both'))") if apply_exclusions else ""
    excl_web = (" AND NOT EXISTS (SELECT 1 FROM broadcast_exclusions be "
                "WHERE be.user_identifier = wu.email "
                "AND be.channel IN ('email','both'))") if apply_exclusions else ""

    if channel == "telegram":
        body = (
            _BASE_TG
            + f" AND {rules_clause_tg}"
            + excl_tg
        )
        params = list(params_tg)
    elif channel == "email":
        # الإيميل: لازم يكون عنده إيميل صالح
        body = (
            _BASE_WEB_ALL
            + " AND wu.email IS NOT NULL AND wu.email <> ''"
            + " AND wu.password_hash IS NOT NULL"
            + f" AND {rules_clause_web}"
            + excl_web
        )
        params = list(params_web)
    else:  # both: تيليجرام + الموقع غير المربوط (للحماية من التكرار)
        body = (
            _BASE_TG
            + f" AND {rules_clause_tg}"
            + excl_tg
            + " UNION ALL "
            + _BASE_WEB_UNLINKED
            + f" AND {rules_clause_web}"
            + excl_web
        )
        params = list(params_tg) + list(params_web)

    # تطبيق select_mode
    if select_mode == "count":
        sql = f"SELECT COUNT(*) FROM ({body}) sub"
    elif select_mode == "ids_only":
        sql = f"SELECT user_id, handle, email, lang FROM ({body}) sub"
    else:
        sql = body

    if limit is not None and select_mode != "count":
        sql = f"{sql} LIMIT %s"
        params = params + [int(limit)]

    return (sql, params)


def count_audience(conn, channel: str, rules_json: dict | None,
                   *, apply_exclusions: bool = True) -> int:
    """عدّ المستخدمين المطابقين للشريحة."""
    sql, params = build_sql(channel, rules_json,
                            select_mode="count",
                            apply_exclusions=apply_exclusions)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return int(row[0]) if row else 0


def count_audience_breakdown(conn, rules_json: dict | None) -> dict:
    """عدّ مفصّل: كم في تليجرام، كم في إيميل، كم في الإجمالي."""
    n_tg = count_audience(conn, "telegram", rules_json)
    n_em = count_audience(conn, "email", rules_json)
    n_both = count_audience(conn, "both", rules_json)
    return {"telegram": n_tg, "email": n_em, "total_unique": n_both}


def fetch_audience(conn, channel: str, rules_json: dict | None,
                   *, limit: int | None = None,
                   apply_exclusions: bool = True) -> list[dict]:
    """جلب قائمة المستلمين كاملة (للإرسال أو التحميل)."""
    sql, params = build_sql(channel, rules_json,
                            select_mode="ids_only",
                            limit=limit,
                            apply_exclusions=apply_exclusions)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def sample_audience(conn, channel: str, rules_json: dict | None,
                    n: int = 10) -> list[dict]:
    """جلب عيّنة صغيرة (للمعاينة في الـUI قبل الإرسال)."""
    sql, params = build_sql(channel, rules_json,
                            select_mode="rows",
                            limit=n,
                            apply_exclusions=True)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ════════════════════════════════════════════════════════════════════════════
# Segment storage helpers
# ════════════════════════════════════════════════════════════════════════════

def save_segment(conn, *, name: str, rules_json: dict,
                 description: str = "", channel: str | None = None,
                 created_by: str = "", is_template: bool = False,
                 segment_id: int | None = None) -> int:
    """يحفظ شريحة جديدة أو يحدّث موجودة. يرجّع الـid."""
    rules_str = json.dumps(rules_json, ensure_ascii=False)
    with conn.cursor() as cur:
        if segment_id:
            # حفظ نسخة قبل التعديل (audit)
            cur.execute(
                "INSERT INTO audience_segment_versions (segment_id, rules_json, saved_by) "
                "SELECT id, rules_json, %s FROM audience_segments WHERE id = %s",
                (created_by, segment_id),
            )
            cur.execute(
                "UPDATE audience_segments SET name=%s, description=%s, rules_json=%s, "
                "channel=%s, updated_at=NOW() WHERE id=%s",
                (name, description, rules_str, channel, segment_id),
            )
            conn.commit()
            return segment_id
        cur.execute(
            "INSERT INTO audience_segments "
            "(name, description, rules_json, channel, created_by, is_template) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (name, description, rules_str, channel, created_by, is_template),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


def load_segment(conn, segment_id: int) -> dict | None:
    """يجلب تعريف شريحة كاملاً."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, description, rules_json, channel, "
            "created_at, updated_at, last_used_at, use_count, "
            "last_count, last_count_at, is_template "
            "FROM audience_segments WHERE id = %s",
            (segment_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [c.name for c in cur.description]
        d = dict(zip(cols, row))
        # rules_json قد يكون dict مسبقاً (JSONB) أو str
        if isinstance(d["rules_json"], str):
            d["rules_json"] = json.loads(d["rules_json"])
        return d


def list_segments(conn, *, include_templates: bool = True) -> list[dict]:
    """قائمة الشرائح المحفوظة (أحدث استخداماً أولاً)."""
    with conn.cursor() as cur:
        where = "" if include_templates else " WHERE is_template = FALSE"
        cur.execute(
            f"SELECT id, name, description, channel, is_template, "
            f"created_at, last_used_at, use_count, last_count, last_count_at "
            f"FROM audience_segments{where} "
            f"ORDER BY COALESCE(last_used_at, created_at) DESC"
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def delete_segment(conn, segment_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM audience_segments WHERE id = %s", (segment_id,))
        conn.commit()


def cache_segment_count(conn, segment_id: int, count: int) -> None:
    """يحفظ آخر عدّ في الجدول (للعرض السريع لاحقاً)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE audience_segments SET last_count=%s, last_count_at=NOW() "
            "WHERE id=%s",
            (count, segment_id),
        )
        conn.commit()


def mark_segment_used(conn, segment_id: int) -> None:
    """يحدّث last_used_at و use_count عند الإرسال الفعلي."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE audience_segments "
            "SET last_used_at = NOW(), use_count = COALESCE(use_count,0) + 1 "
            "WHERE id = %s",
            (segment_id,),
        )
        conn.commit()


def list_templates(conn) -> list[dict]:
    """قائمة القوالب الجاهزة (is_template = TRUE)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, description, channel, rules_json "
            "FROM audience_segments WHERE is_template = TRUE "
            "ORDER BY name"
        )
        cols = [c.name for c in cur.description]
        out = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            if isinstance(d["rules_json"], str):
                d["rules_json"] = json.loads(d["rules_json"])
            out.append(d)
        return out


def list_user_segments(conn) -> list[dict]:
    """شرائح مخصّصة من المستخدم فقط (بدون القوالب)."""
    return [s for s in list_segments(conn) if not s.get("is_template")]


def list_segment_versions(conn, segment_id: int, limit: int = 20) -> list[dict]:
    """تاريخ تعديلات شريحة (للـrollback)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, segment_id, rules_json, saved_at, saved_by, change_note "
            "FROM audience_segment_versions WHERE segment_id = %s "
            "ORDER BY saved_at DESC LIMIT %s",
            (segment_id, limit),
        )
        cols = [c.name for c in cur.description]
        out = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            if isinstance(d["rules_json"], str):
                d["rules_json"] = json.loads(d["rules_json"])
            out.append(d)
        return out


def restore_segment_version(conn, segment_id: int, version_id: int,
                            restored_by: str = "") -> bool:
    """يُرجع شريحة إلى نسخة سابقة (يحفظ الحالة الحالية كنسخة قبل الاسترجاع)."""
    with conn.cursor() as cur:
        # تحقّق أن النسخة تخص الشريحة
        cur.execute(
            "SELECT rules_json FROM audience_segment_versions "
            "WHERE id = %s AND segment_id = %s",
            (version_id, segment_id),
        )
        row = cur.fetchone()
        if not row:
            return False
        old_rules = row[0]
        if isinstance(old_rules, dict):
            old_rules_str = json.dumps(old_rules, ensure_ascii=False)
        else:
            old_rules_str = old_rules
        # احفظ الحالة الحالية كنسخة قبل الاسترجاع
        cur.execute(
            "INSERT INTO audience_segment_versions "
            "(segment_id, rules_json, saved_by, change_note) "
            "SELECT id, rules_json, %s, %s FROM audience_segments WHERE id = %s",
            (restored_by, f"snapshot قبل استرجاع نسخة #{version_id}", segment_id),
        )
        cur.execute(
            "UPDATE audience_segments SET rules_json = %s, updated_at = NOW() "
            "WHERE id = %s",
            (old_rules_str, segment_id),
        )
        conn.commit()
        return True


def clone_template(conn, template_id: int, new_name: str,
                   created_by: str = "") -> int | None:
    """ينسخ قالباً كشريحة مستخدم قابلة للتعديل (is_template = FALSE)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name, description, rules_json, channel "
            "FROM audience_segments WHERE id = %s AND is_template = TRUE",
            (template_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        _, desc, rules, channel = row
        if isinstance(rules, dict):
            rules_str = json.dumps(rules, ensure_ascii=False)
        else:
            rules_str = rules
        cur.execute(
            "INSERT INTO audience_segments "
            "(name, description, rules_json, channel, created_by, is_template) "
            "VALUES (%s, %s, %s, %s, %s, FALSE) RETURNING id",
            (new_name, desc, rules_str, channel, created_by),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


# ════════════════════════════════════════════════════════════════════════════
# Reference data (لقوائم الـ UI)
# ════════════════════════════════════════════════════════════════════════════

def analytics_filters_to_rules(*, lang=None, gender=None, age=None, city=None,
                                status=None, complete=None, fav_store=None,
                                fav_cat=None, store=None, category=None,
                                action=None, trend=None, story=None) -> dict:
    """يحوّل فلاتر صفحة «تحليل المستخدمين» إلى rules_json متوافق مع المحرّك.

    كل القيم اختيارية. ما يُمرّر = ما يُضاف كقاعدة. ينتج مجموعة AND واحدة.
    """
    rules: list[dict] = []

    if lang in ("ar", "en"):
        rules.append({"type":"attribute","field":"lang","op":"=","value":lang})

    if gender in ("male", "female"):
        rules.append({"type":"attribute","field":"gender","op":"=","value":gender})

    if age and age != "none":
        ranges = {"u18":[0,17],"18-24":[18,24],"25-34":[25,34],
                  "35-44":[35,44],"45-54":[45,54],"55p":[55,120]}
        if age in ranges:
            rules.append({"type":"attribute","field":"age","op":"between",
                          "value":ranges[age]})

    if city and city not in (None, "none", "all", "الكل", "لا شيء"):
        rules.append({"type":"attribute","field":"city","op":"=","value":city})

    if status == "active":
        rules.append({"type":"temporal","field":"last_seen","op":">=","value_days":20})
    elif status == "idle":
        rules.append({"type":"temporal","field":"last_seen","op":"<=","value_days":20})

    if complete == "complete":
        rules.append({"type":"attribute","field":"is_linked","op":"=","value":True})
    elif complete == "partial":
        rules.append({"type":"attribute","field":"is_linked","op":"=","value":False})

    if fav_store == "has":
        rules.append({"type":"attribute","field":"fav_count","op":">=","value":1})

    if store:
        rules.append({"type":"event","action":"view_store","entity_type":"store",
                      "entity_value":store,"context":"any",
                      "window":{"type":"all"}})

    if category:
        rules.append({"type":"event","action":"view_tag","entity_type":"category",
                      "entity_value":category,"context":"any",
                      "window":{"type":"all"}})

    if action in ("copy_coupon", "click_link", "search"):
        rules.append({"type":"event","action":action,"entity_type":"any",
                      "context":"any","window":{"type":"all"}})

    if trend in ("daily", "weekly"):
        ctx = "trend_daily" if trend == "daily" else "trend_weekly"
        rules.append({"type":"event","action":"click_link","entity_type":"any",
                      "context":ctx,"window":{"type":"all"}})

    if story in ("normal", "trend"):
        rules.append({"type":"event","action":"view_story",
                      "was_trending":(story == "trend"),
                      "window":{"type":"all"}})

    if not rules:
        return {"version":1, "logic":"or", "groups":[]}
    return {"version":1, "logic":"or",
            "groups":[{"logic":"and", "rules":rules}]}


def list_stores(conn) -> list[str]:
    """قائمة store_id من master للـ dropdown."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT store_id FROM master "
            "WHERE store_id IS NOT NULL AND store_id <> '' "
            "ORDER BY store_id"
        )
        return [r[0] for r in cur.fetchall()]


def list_categories(conn) -> list[str]:
    """قائمة كل التاجز/الأقسام من master.store_tags."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT TRIM(tag) FROM master, "
            "unnest(string_to_array(trim(both '{}' from COALESCE(store_tags,'')), ',')) AS tag "
            "WHERE TRIM(tag) <> '' ORDER BY 1"
        )
        return [r[0] for r in cur.fetchall()]


def list_cities(conn) -> list[str]:
    """قائمة المدن المكتشفة من IP في action_logs."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT city FROM action_logs "
            "WHERE city IS NOT NULL AND city <> '' "
            "AND is_proxy IS NOT TRUE AND is_datacenter IS NOT TRUE "
            "ORDER BY city"
        )
        return [r[0] for r in cur.fetchall()]


__all__ = [
    "build_sql",
    "count_audience",
    "count_audience_breakdown",
    "fetch_audience",
    "sample_audience",
    "save_segment",
    "load_segment",
    "list_segments",
    "list_user_segments",
    "list_templates",
    "list_segment_versions",
    "restore_segment_version",
    "clone_template",
    "delete_segment",
    "cache_segment_count",
    "mark_segment_used",
    "list_stores",
    "list_categories",
    "list_cities",
    "analytics_filters_to_rules",
]
