"""
محرّك «الترند» — نسخة Python نقية (بدون pandas) للاستهلاك من FastAPI.

نفس قواعد النقاط و Anti-Spam المُطبَّقة في dashboard.py:
    - نقر = 1، بحث = 2، نسخ = 3، مفضلة = 4
    - لكل (شخص × متجر × نوع فعل): أول 2 خلال ساعة تُحسب، ثم تبريد إلى أن
      تمرّ 5 ساعات من بداية النافذة → نافذة جديدة.

يُكرَّر المنطق هنا (بدلاً من استيراد dashboard.py) لأن dashboard.py يشغّل
Streamlit عند الاستيراد، وكذلك pandas ثقيلة في مسار API ساخن.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


POINTS: dict[str, int] = {"click_link": 1, "search": 2, "copy_coupon": 3}
FAV_POINTS: int = 4

ONE_HOUR = timedelta(hours=1)
FIVE_HOURS = timedelta(hours=5)

# ألقاب المراكز — مطابقة لِما في الداشبورد
RANK_TITLES_TOP3: list[str] = [
    "الأعلى طلباً",
    "الأكثر شعبية",
    "الأوسع انتشاراً",
]
RANK_TITLES_POSITIONAL: dict[int, str] = {
    4: "المركز الرابع",
    5: "المركز الخامس",
    6: "المركز السادس",
    7: "المركز السابع",
}


def person_key(source: str | None, user_id: Any, ip_hex: str | None) -> str:
    """
    هوية موحّدة للشخص — منفصلة لكل مصدر (web/mini/bot) حتى لا تختلط
    فترات التبريد بين المنصات. nan-safe.
    """
    src = (source or "bot").strip().lower()
    prefix = ("web" if src == "web"
              else "mini" if src in ("telegram_miniapp", "miniapp")
              else "bot")
    if user_id is not None:
        try:
            return f"{prefix}:u{int(user_id)}"
        except (TypeError, ValueError):
            pass
    if ip_hex and isinstance(ip_hex, str):
        return f"{prefix}:ip{ip_hex[:12]}"
    return f"{prefix}:anon"


def apply_anti_spam(events: list[dict]) -> None:
    """
    يضيف مفتاح 'counted' (bool) داخل كل dict من القائمة.
    يُعدّل القائمة في مكانها (in-place sort + mutation).

    شروط: كل عنصر يحتوي على المفاتيح: time, person_key, store_id, action_type.
    """
    if not events:
        return
    events.sort(key=lambda e: (e["person_key"], e["store_id"],
                                e["action_type"], e["time"]))
    last_key: tuple = (None, None, None)
    win_open: datetime | None = None
    count_in_win = 0
    for e in events:
        k = (e["person_key"], e["store_id"], e["action_type"])
        t = e["time"]
        if k != last_key:
            last_key = k
            win_open = t
            count_in_win = 1
            e["counted"] = True
            continue
        delta = t - win_open
        if delta >= FIVE_HOURS:
            win_open = t
            count_in_win = 1
            e["counted"] = True
        elif delta < ONE_HOUR and count_in_win < 2:
            count_in_win += 1
            e["counted"] = True
        else:
            e["counted"] = False


def compute_trend(events: list[dict], favorites: list[dict],
                  window_start: datetime, window_end: datetime,
                  top_n: int) -> list[dict]:
    """
    يطبّق Anti-Spam على كامل تاريخ الأفعال، يجمع داخل النافذة فقط،
    يجمع المفضلة، يرتّب تنازلياً بالنقاط، ويُرجع أعلى top_n.

    events: dicts فيها time, person_key, store_id, action_type
    favorites: dicts فيها created_at, store_id
    """
    apply_anti_spam(events)

    scores: dict[str, dict[str, Any]] = {}

    def _bucket(sid: str) -> dict[str, Any]:
        b = scores.get(sid)
        if b is None:
            b = {"clicks": 0, "searches": 0, "copies": 0, "favs": 0,
                  "users": set()}
            scores[sid] = b
        return b

    for e in events:
        if not e.get("counted"):
            continue
        t = e["time"]
        if not (window_start <= t <= window_end):
            continue
        sid = e["store_id"]
        if not sid:
            continue
        b = _bucket(sid)
        b["users"].add(e["person_key"])
        at = e["action_type"]
        if at == "click_link":
            b["clicks"] += 1
        elif at == "search":
            b["searches"] += 1
        elif at == "copy_coupon":
            b["copies"] += 1

    for f in favorites:
        ca = f["created_at"]
        if not (window_start <= ca <= window_end):
            continue
        sid = f["store_id"]
        if not sid:
            continue
        _bucket(sid)["favs"] += 1

    results: list[dict] = []
    for sid, b in scores.items():
        total = (b["clicks"] * POINTS["click_link"]
                 + b["searches"] * POINTS["search"]
                 + b["copies"] * POINTS["copy_coupon"]
                 + b["favs"] * FAV_POINTS)
        if total <= 0:
            continue
        results.append({
            "store_id": sid,
            "score": total,
            "clicks": b["clicks"],
            "searches": b["searches"],
            "copies": b["copies"],
            "favs": b["favs"],
            "unique_users": len(b["users"]),
        })
    # ترتيب ثابت: نقاط ↓ ثم أشخاص فريدين ↓ ثم اسم المتجر ↑ (لاستقرار النتيجة)
    results.sort(key=lambda r: (-r["score"], -r["unique_users"], r["store_id"]))
    return results[:top_n]


def assign_rank_titles(items: list[dict]) -> list[dict]:
    """يضيف rank + rank_title لكل عنصر. الأول-الثالث ألقاب موصوفة، 4-7 «المركز X»."""
    for i, it in enumerate(items):
        rk = i + 1
        it["rank"] = rk
        if rk <= 3:
            it["rank_title"] = RANK_TITLES_TOP3[i]
        else:
            it["rank_title"] = RANK_TITLES_POSITIONAL.get(rk, f"المركز {rk}")
    return items


NONE_SENTINEL = "__NONE__"   # «بدون» — يُخفي مركزاً معيّناً عمداً من قائمة الترند.


def apply_overrides(items: list[dict], overrides: dict[int, str],
                    top_n: int) -> list[dict]:
    """
    يدمج نتائج الخوارزمية مع التجاوزات اليدوية (admin pins).

    منطق الإزاحة (نفس ما طلبه المالك):
      - لكل rank من 1 إلى top_n: لو فيه override → نضع المتجر المُثبَّت هناك.
      - لو الـoverride هو NONE_SENTINEL «بدون» → نتخطّى هذا المركز كلياً
        (لا يظهر شيء)، والمراكز اللاحقة لا تتزحّح لملئه.
      - لو ما فيه override → نأخذ التالي من نتائج الخوارزمية، **متخطّين**
        المتاجر المُجاوزة (لتجنّب التكرار).

    إذا المتجر المُجاوَز موجود أصلاً في نتائج الخوارزمية، نحافظ على نقاطه
    (breakdown). إذا غير موجود (مثلاً متجر بلا نشاط هذه النافذة)، نُنشئ
    placeholder بأصفار — الـ caller يُثري التفاصيل (logo/name_en) من master.

    overrides: dict {rank: store_id | NONE_SENTINEL}.
    """
    items_by_id = {it["store_id"]: it for it in items}
    # NONE_SENTINEL لا يُحجز متجراً حقيقياً، فلا يُستبعد من algo_pool.
    overridden_ids = {v for v in overrides.values() if v != NONE_SENTINEL}
    # algo pool — ترتيب الخوارزمية مع استبعاد المتاجر المُجاوزة (لمنع التكرار).
    algo_pool = [it for it in items if it["store_id"] not in overridden_ids]

    result: list[dict] = []
    for rank in range(1, top_n + 1):
        if rank in overrides:
            sid = overrides[rank]
            if sid == NONE_SENTINEL:
                # «بدون» صريحة لهذا المركز — لا نُضيف شيئاً، نتخطّى.
                continue
            if sid in items_by_id:
                # المتجر له نقاط من الخوارزمية — نستخدمها (مع تجاهل ترتيبه الأصلي).
                result.append(dict(items_by_id[sid]))
            else:
                # غير نشط هذه النافذة — placeholder بأصفار.
                result.append({
                    "store_id": sid, "score": 0,
                    "clicks": 0, "searches": 0, "copies": 0, "favs": 0,
                    "unique_users": 0,
                })
        elif algo_pool:
            result.append(algo_pool.pop(0))
        # else: لا overrides ولا algo → نتوقف عند هذا المركز

    return result
