"""Endpoints لمستخدمي الموقع: إدارة المفضلة (يحتاج JWT)."""
from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.routers.auth import get_current_user
from api.schemas.users import FavoriteRequest, FavoritesResponse

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
        # تحقق من وجود المتجر
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

        # نُضيف للمصفوفة مع منع التكرار
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
