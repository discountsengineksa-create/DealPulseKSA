"""Endpoints لمستخدمي الموقع: تزامن Firebase + المفضلة."""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.schemas.users import (
    UserSyncRequest, UserResponse,
    FavoriteRequest, FavoritesResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


def _get_user_by_firebase_uid(conn, firebase_uid: str) -> dict | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM web_users WHERE firebase_uid = %s", (firebase_uid,))
        return cur.fetchone()


@router.post("/sync", response_model=UserResponse, status_code=200)
def sync_user(
    payload: UserSyncRequest,
    request: Request,
    conn=Depends(get_db),
):
    """
    يُستدعى من الموقع بعد نجاح Firebase OTP.
    UPSERT: يُنشئ السجل لأول مرة، أو يُحدّث last_seen + display_name.
    """
    client_ip = request.client.host if request.client else None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO web_users (
                firebase_uid, phone_number, display_name, email,
                user_agent, device_type, last_ip, last_seen
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (firebase_uid) DO UPDATE SET
                phone_number = EXCLUDED.phone_number,
                display_name = COALESCE(EXCLUDED.display_name, web_users.display_name),
                email        = COALESCE(EXCLUDED.email, web_users.email),
                user_agent   = COALESCE(EXCLUDED.user_agent, web_users.user_agent),
                device_type  = COALESCE(EXCLUDED.device_type, web_users.device_type),
                last_ip      = COALESCE(EXCLUDED.last_ip, web_users.last_ip),
                last_seen    = NOW(),
                status       = 'Active'
            RETURNING id, phone_number, display_name, email, country, city, lang,
                      visited_clicks, store_copy_count, manual_favorites
            """,
            (
                payload.firebase_uid, payload.phone_number, payload.display_name,
                payload.email, payload.user_agent, payload.device_type, client_ip,
            ),
        )
        row = cur.fetchone()

    return UserResponse(**row, manual_favorites=row.get("manual_favorites") or [])


@router.get("/me", response_model=UserResponse)
def get_me(
    x_firebase_uid: str = Header(..., alias="X-Firebase-UID"),
    conn=Depends(get_db),
):
    """يجلب بيانات المستخدم الحالي عبر Firebase UID المُرسل في الـ header."""
    user = _get_user_by_firebase_uid(conn, x_firebase_uid)
    if not user:
        raise HTTPException(status_code=404, detail="user not found — call /sync first")
    return UserResponse(**user, manual_favorites=user.get("manual_favorites") or [])


@router.get("/me/favorites", response_model=FavoritesResponse)
def get_favorites(
    x_firebase_uid: str = Header(..., alias="X-Firebase-UID"),
    conn=Depends(get_db),
):
    user = _get_user_by_firebase_uid(conn, x_firebase_uid)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return FavoritesResponse(favorites=user.get("manual_favorites") or [])


@router.post("/me/favorites", response_model=FavoritesResponse, status_code=201)
def add_favorite(
    payload: FavoriteRequest,
    x_firebase_uid: str = Header(..., alias="X-Firebase-UID"),
    conn=Depends(get_db),
):
    """إضافة متجر للمفضلة (idempotent — لا يُضاف مرتين)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # تحقق من وجود المتجر
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

        # array_append مع تجنّب التكرار عبر array(SELECT DISTINCT)
        cur.execute(
            """
            UPDATE web_users SET
                manual_favorites = (
                    SELECT array_agg(DISTINCT x)
                    FROM unnest(array_append(COALESCE(manual_favorites, '{}'), %s)) AS x
                )
            WHERE firebase_uid = %s
            RETURNING manual_favorites
            """,
            (payload.store_id, x_firebase_uid),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")

    return FavoritesResponse(favorites=row["manual_favorites"] or [])


@router.delete("/me/favorites/{store_id}", response_model=FavoritesResponse)
def remove_favorite(
    store_id: str,
    x_firebase_uid: str = Header(..., alias="X-Firebase-UID"),
    conn=Depends(get_db),
):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE web_users SET
                manual_favorites = array_remove(COALESCE(manual_favorites, '{}'), %s)
            WHERE firebase_uid = %s
            RETURNING manual_favorites
            """,
            (store_id, x_firebase_uid),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")

    return FavoritesResponse(favorites=row["manual_favorites"] or [])
