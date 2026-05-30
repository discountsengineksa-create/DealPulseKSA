"""Endpoints لمستخدمي الموقع: إدارة المفضلة (يحتاج JWT) + بروفايل الميني-ويب."""
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.routers.auth import get_current_user
from api.schemas.users import (
    FavoriteRequest,
    FavoritesResponse,
    TelegramProfileSaveRequest,
    TelegramProfileStatusRequest,
    TelegramProfileStatusResponse,
)
from api.utils.rate_limit import LIMIT_TG_PROFILE_READ, LIMIT_TG_PROFILE_SAVE, limiter
from api.utils.telegram_init_data import TelegramAuthError, verify_init_data

router = APIRouter(prefix="/users", tags=["users"])


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
    """إضافة متجر للمفضلة (idempotent — لا يُضاف مرتين)."""
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


# ─── Telegram Mini-App Profile ─────────────────────────────────────────────
# جمع gender + birth_date من مستخدمي الميني-ويب (bot_users).
# المصادقة: initData موقّع من تيليجرام (HMAC-SHA256 بالـ bot_token).
@router.post("/telegram-profile/status", response_model=TelegramProfileStatusResponse)
@limiter.limit(LIMIT_TG_PROFILE_READ)
def telegram_profile_status(
    payload: TelegramProfileStatusRequest,
    request: Request,
    conn=Depends(get_db),
):
    """يرجّع إن كان المستخدم عبّأ gender + birth_date أو لا.

    الميني-ويب يستدعي هذا عند الإقلاع — لو `has_demographics=false`
    يعرض الموديال الإلزامي.
    """
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT gender, birth_date FROM bot_users WHERE telegram_id = %s",
            (telegram_id,),
        )
        row = cur.fetchone()

    if not row:
        # المستخدم ما تفاعل مع البوت بعد (نادر — الميني-ويب يُفتح من البوت أصلاً)
        return TelegramProfileStatusResponse(
            telegram_id=telegram_id,
            has_demographics=False,
        )

    gender = row.get("gender")
    birth_date = row.get("birth_date")
    return TelegramProfileStatusResponse(
        telegram_id=telegram_id,
        has_demographics=bool(gender and birth_date),
        gender=gender,
        birth_date=birth_date.isoformat() if birth_date else None,
    )


@router.post("/telegram-profile", status_code=200)
@limiter.limit(LIMIT_TG_PROFILE_SAVE)
def telegram_profile_save(
    payload: TelegramProfileSaveRequest,
    request: Request,
    conn=Depends(get_db),
):
    """يحفظ gender + birth_date لمستخدم الميني-ويب.

    يتحقق من initData أولاً، ثم UPSERT في bot_users (INSERT إن جديد،
    UPDATE إن موجود — لتفادي race لو ضغط قبل ما /start يُنشئ السجل).
    """
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    username = tg_user.get("username") or tg_user.get("first_name") or "Anonymous"

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bot_users (telegram_id, username, joined_at, last_seen,
                                   user_status, gender, birth_date)
            VALUES (%s, %s, NOW(), NOW(), 'Active', %s, %s)
            ON CONFLICT (telegram_id) DO UPDATE
                SET gender     = EXCLUDED.gender,
                    birth_date = EXCLUDED.birth_date,
                    last_seen  = NOW()
            """,
            (telegram_id, username, payload.gender, payload.birth_date),
        )

    return {"ok": True, "telegram_id": telegram_id}
