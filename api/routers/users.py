"""Endpoints لمستخدمي الموقع: إدارة المفضلة + حقوق PDPL (حذف/تصدير البيانات)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from api.auth_utils import decode_jwt_token, verify_password
from api.db import get_db
from api.routers.auth import get_current_user
from api.schemas.users import FavoriteRequest, FavoritesResponse
from api.utils.ops import audit_log

router = APIRouter(prefix="/users", tags=["users"])


# ─────────────────────────────────────────────────────────────────────────────
# Favorites
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/me/favorites", response_model=FavoritesResponse)
def get_favorites(user=Depends(get_current_user)):
    """قائمة المفضلة للمستخدم الحالي."""
    return FavoritesResponse(favorites=list(user.get("manual_favorites") or []))


@router.post("/me/favorites", response_model=FavoritesResponse, status_code=201)
def add_favorite(
    payload: FavoriteRequest,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """إضافة متجر للمفضلة (idempotent)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

        cur.execute(
            """
            UPDATE web_users SET
                manual_favorites = (
                    SELECT array_agg(DISTINCT x)
                    FROM unnest(array_append(COALESCE(manual_favorites, '{}'), %s)) AS x
                )
            WHERE id = %s
            RETURNING manual_favorites
            """,
            (payload.store_id, user["id"]),
        )
        row = cur.fetchone()

    return FavoritesResponse(favorites=list(row["manual_favorites"] or []))


@router.delete("/me/favorites/{store_id}", response_model=FavoritesResponse)
def remove_favorite(
    store_id: str,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """حذف متجر من المفضلة."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE web_users SET
                manual_favorites = array_remove(COALESCE(manual_favorites, '{}'), %s)
            WHERE id = %s
            RETURNING manual_favorites
            """,
            (store_id, user["id"]),
        )
        row = cur.fetchone()

    return FavoritesResponse(favorites=list(row["manual_favorites"] or []))


# ═════════════════════════════════════════════════════════════════════════════
#  PDPL (Saudi Personal Data Protection Law) — § 8 Data Subject Rights
# ═════════════════════════════════════════════════════════════════════════════
GRACE_PERIOD_DAYS = 30


class DeleteAccountRequest(BaseModel):
    """تأكيد حذف الحساب بكلمة السر + كلمة 'DELETE' (مزدوجة الحماية)."""
    password: str = Field(..., min_length=1, description="كلمة سرّك الحالية للتأكيد")
    confirm: str = Field(..., description="اكتب كلمة 'DELETE' حرفياً")


def _get_user_allow_deleted(
    authorization: str = Header(..., alias="Authorization"),
    conn=Depends(get_db),
) -> dict:
    """
    نسخة من get_current_user تسمح بالحسابات المحذوفة ناعماً.
    تُستخدم فقط في endpoint استرجاع الحذف (cancel-deletion).
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header malformed")
    payload = decode_jwt_token(authorization[7:].strip())
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        uid = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM web_users WHERE id = %s", (uid,))
        user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/me/export", tags=["pdpl"])
def export_my_data(user=Depends(get_current_user), conn=Depends(get_db)):
    """
    PDPL § 8 — حق الوصول (data portability).

    يُرجع نسخة كاملة بصيغة JSON تحتوي:
      • بيانات الحساب
      • المفضلة
      • تاريخ نسخ الأكواد
      • سجل النشاط (آخر 200 حدث)
    """
    uid = user["id"]
    out: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "pdpl_notice": (
            "هذه نسخة كاملة من بياناتك المخزّنة لدينا وفق نظام حماية البيانات السعودي § 8."
        ),
        "account": {
            "id":               user["id"],
            "display_name":     user.get("display_name"),
            "email":            user.get("email"),
            "phone_number":     user.get("phone_number"),
            "city":             user.get("city"),
            "country":          user.get("country"),
            "lang":             user.get("lang"),
            "created_at":       user["created_at"].isoformat() if user.get("created_at") else None,
            "last_seen":        user["last_seen"].isoformat() if user.get("last_seen") else None,
            "visited_clicks":   user.get("visited_clicks") or 0,
            "store_copy_count": user.get("store_copy_count") or 0,
        },
        "favorites": list(user.get("manual_favorites") or []),
        "copied_coupons_history": list(user.get("copied_coupons_history") or []),
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT to_char(action_time, 'YYYY-MM-DD"T"HH24:MI:SSOF') AS action_time,
                   action_type, store_id, source, country_code, city, device_class
            FROM action_logs
            WHERE user_id = %s AND source = 'web'
            ORDER BY action_time DESC
            LIMIT 200
            """,
            (uid,),
        )
        out["recent_activity"] = [dict(r) for r in cur.fetchall()]

    audit_log(
        action="user_data_export",
        actor=f"user:{uid}",
        target=user.get("email") or str(uid),
        meta={"records_exported": len(out["recent_activity"])},
    )
    return out


@router.delete("/me", status_code=200, tags=["pdpl"])
def delete_my_account(
    payload: DeleteAccountRequest,
    request: Request,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """
    PDPL § 8 — حق الحذف (right to erasure).

    سياسة الحذف المتدرّج:
      1. soft delete فوري: deleted_at = NOW()
      2. الحساب يختفي من جميع الواجهات (login/me يفشلان فوراً)
      3. خلال 30 يوماً يمكن الاسترجاع عبر /users/me/cancel-deletion
      4. بعد 30 يوماً worker يومي يحذف نهائياً (cascade على favorites + tokens)

    الحماية المزدوجة (anti-takeover):
      • password صحيحة + confirm == "DELETE"
    """
    if payload.confirm != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="يجب كتابة كلمة 'DELETE' حرفياً في حقل confirm.",
        )
    if not verify_password(payload.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="كلمة السر غير صحيحة.")

    uid = user["id"]
    purge_at = datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE web_users
            SET deleted_at = NOW(), last_seen = NOW()
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id, email
            """,
            (uid,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=410, detail="الحساب محذوف مسبقاً.")

    audit_log(
        action="user_self_delete",
        actor=f"user:{uid}",
        target=row["email"] or str(uid),
        meta={
            "grace_period_days": GRACE_PERIOD_DAYS,
            "scheduled_purge_at": purge_at.isoformat(),
            "ip": request.client.host if request.client else None,
        },
    )
    return {
        "ok": True,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "purge_scheduled_at": purge_at.isoformat(),
        "grace_period_days": GRACE_PERIOD_DAYS,
        "message": (
            f"تم حذف حسابك. لديك {GRACE_PERIOD_DAYS} يوماً لاسترجاعه عبر تسجيل الدخول "
            "ثم POST /api/v1/users/me/cancel-deletion. بعدها يُمسح نهائياً."
        ),
    }


@router.post("/me/cancel-deletion", tags=["pdpl"])
def cancel_my_deletion(
    user=Depends(_get_user_allow_deleted),
    conn=Depends(get_db),
):
    """استرجاع حساب محذوف ناعماً (داخل الـ grace period فقط)."""
    if user.get("deleted_at") is None:
        raise HTTPException(status_code=400, detail="الحساب نشط، لا يحتاج استرجاعاً.")

    deleted_at = user["deleted_at"]
    # نضمن tz-aware للمقارنة
    if deleted_at.tzinfo is None:
        deleted_at = deleted_at.replace(tzinfo=timezone.utc)
    days_passed = (datetime.now(timezone.utc) - deleted_at).days

    if days_passed >= GRACE_PERIOD_DAYS:
        raise HTTPException(
            status_code=410,
            detail=f"انقضت فترة الاسترجاع ({GRACE_PERIOD_DAYS} يوماً). الحساب في طور الحذف النهائي.",
        )

    with conn.cursor() as cur:
        cur.execute("UPDATE web_users SET deleted_at = NULL WHERE id = %s", (user["id"],))

    audit_log(
        action="user_cancel_deletion",
        actor=f"user:{user['id']}",
        target=user.get("email") or str(user["id"]),
        meta={"days_after_delete": days_passed},
    )
    return {"ok": True, "message": "تم استرجاع حسابك بنجاح. سُجِّل دخولك من جديد لتجديد الجلسة."}
