"""Endpoints لمستخدمي الموقع: إدارة المفضلة (يحتاج JWT) + بروفايل الميني-ويب."""
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.routers.auth import get_current_user
from api.schemas.users import (
    CategoryFavoriteRequest,
    CategoryFavoritesResponse,
    FavoriteRequest,
    FavoritesResponse,
    TelegramCategoryFavoriteRequest,
    TelegramFavoriteRequest,
    TelegramFavoritesListRequest,
    TelegramProfileSaveRequest,
    TelegramProfileStatusRequest,
    TelegramProfileStatusResponse,
)
from api.utils.rate_limit import (
    LIMIT_TG_FAVORITE,
    LIMIT_TG_PROFILE_READ,
    LIMIT_TG_PROFILE_SAVE,
    limiter,
)
from api.utils.telegram_init_data import TelegramAuthError, verify_init_data

router = APIRouter(prefix="/users", tags=["users"])


# ─── Helpers: كتابة الجدول الموحّد user_favorites (SSOT) ───────────────────
# يُستدعى بجانب تحديث manual_favorites (dual-write) ضمن نفس المعاملة، فلا
# يحتاج commit هنا — get_db يؤكّد المعاملة عند نجاح الطلب.
def _uf_upsert(cur, store_id, *, platform, web_user_id=None, telegram_id=None):
    """يضيف صفاً للمفضلة (idempotent). مالك واحد بالضبط: ويب أو تيليجرام."""
    if web_user_id is not None:
        cur.execute(
            """
            INSERT INTO user_favorites (platform, web_user_id, store_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (web_user_id, store_id) WHERE web_user_id IS NOT NULL
            DO NOTHING
            """,
            (platform, web_user_id, store_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO user_favorites (platform, telegram_id, store_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (telegram_id, store_id) WHERE telegram_id IS NOT NULL
            DO NOTHING
            """,
            (platform, telegram_id, store_id),
        )


def _uf_delete(cur, store_id, *, web_user_id=None, telegram_id=None):
    """يحذف صف المفضلة لمالكه."""
    if web_user_id is not None:
        cur.execute(
            "DELETE FROM user_favorites WHERE web_user_id = %s AND store_id = %s",
            (web_user_id, store_id),
        )
    else:
        cur.execute(
            "DELETE FROM user_favorites WHERE telegram_id = %s AND store_id = %s",
            (telegram_id, store_id),
        )


# ─── Category favorites helpers (kind='category') ─────────────────────────
def _uf_category_upsert(cur, category_name, *, platform,
                        web_user_id=None, telegram_id=None):
    """يضيف صف مفضلة قسم (idempotent). store_id NULL + kind='category'."""
    if web_user_id is not None:
        cur.execute(
            """
            INSERT INTO user_favorites (kind, platform, web_user_id, category_name)
            VALUES ('category', %s, %s, %s)
            ON CONFLICT (web_user_id, category_name)
            WHERE web_user_id IS NOT NULL AND kind = 'category'
            DO NOTHING
            """,
            (platform, web_user_id, category_name),
        )
    else:
        cur.execute(
            """
            INSERT INTO user_favorites (kind, platform, telegram_id, category_name)
            VALUES ('category', %s, %s, %s)
            ON CONFLICT (telegram_id, category_name)
            WHERE telegram_id IS NOT NULL AND kind = 'category'
            DO NOTHING
            """,
            (platform, telegram_id, category_name),
        )


def _uf_category_delete(cur, category_name, *, web_user_id=None, telegram_id=None):
    """يحذف صف مفضلة قسم لمالكه."""
    if web_user_id is not None:
        cur.execute(
            "DELETE FROM user_favorites WHERE kind = 'category' "
            "AND web_user_id = %s AND category_name = %s",
            (web_user_id, category_name),
        )
    else:
        cur.execute(
            "DELETE FROM user_favorites WHERE kind = 'category' "
            "AND telegram_id = %s AND category_name = %s",
            (telegram_id, category_name),
        )


def _category_exists(cur, category_name: str) -> bool:
    """يتحقق أن القسم موجود فعلاً في master.store_tags — يمنع abuse بقيم وهمية."""
    # store_tags نصّ بصيغة '{a,b,c}'. نستعمل ILIKE على النصّ المفصول
    # (انظر CLAUDE.md — العمود text وليس text[]).
    cur.execute(
        """
        SELECT 1 FROM master
        WHERE EXISTS (
            SELECT 1 FROM unnest(string_to_array(
                trim(both '{}' from COALESCE(store_tags, '')), ','
            )) AS t
            WHERE trim(t) = %s
        )
        LIMIT 1
        """,
        (category_name,),
    )
    return cur.fetchone() is not None


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

        # SSOT الموحّد للتحليل/التنبيهات (dual-write ضمن نفس المعاملة)
        _uf_upsert(cur, payload.store_id, platform="web", web_user_id=user["id"])

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

        # حذف من SSOT الموحّد (dual-write)
        _uf_delete(cur, store_id, web_user_id=user["id"])

    return FavoritesResponse(favorites=list(row["manual_favorites"] or []))


# ─── Web Category Favorites (JWT) ───────────────────────────────────────────
# مفضلة الأقسام لمستخدم الموقع المسجّل دخوله. لا dual-write — الأقسام تعيش في
# user_favorites فقط (لا توجد manual_categories على web_users).
@router.get("/me/favorite-categories", response_model=CategoryFavoritesResponse)
def get_favorite_categories(user=Depends(get_current_user), conn=Depends(get_db)):
    """قائمة أقسام مفضلة المستخدم الحالي (ترتيب تنازلي بتاريخ الإضافة)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT category_name FROM user_favorites "
            "WHERE kind = 'category' AND web_user_id = %s "
            "ORDER BY created_at DESC",
            (user["id"],),
        )
        cats = [r["category_name"] for r in cur.fetchall()]
    return CategoryFavoritesResponse(categories=cats)


@router.post("/me/favorite-categories",
             response_model=CategoryFavoritesResponse, status_code=201)
def add_favorite_category(
    payload: CategoryFavoriteRequest,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """إضافة قسم لمفضلة الويب (idempotent). يتحقق أن القسم موجود في master."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if not _category_exists(cur, payload.category_name):
            raise HTTPException(
                status_code=404,
                detail=f"category '{payload.category_name}' not found",
            )
        _uf_category_upsert(cur, payload.category_name,
                            platform="web", web_user_id=user["id"])
        cur.execute(
            "SELECT category_name FROM user_favorites "
            "WHERE kind = 'category' AND web_user_id = %s "
            "ORDER BY created_at DESC",
            (user["id"],),
        )
        cats = [r["category_name"] for r in cur.fetchall()]
    return CategoryFavoritesResponse(categories=cats)


@router.delete("/me/favorite-categories/{category_name}",
               response_model=CategoryFavoritesResponse)
def remove_favorite_category(
    category_name: str,
    user=Depends(get_current_user),
    conn=Depends(get_db),
):
    """حذف قسم من مفضلة الويب."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        _uf_category_delete(cur, category_name.strip(), web_user_id=user["id"])
        cur.execute(
            "SELECT category_name FROM user_favorites "
            "WHERE kind = 'category' AND web_user_id = %s "
            "ORDER BY created_at DESC",
            (user["id"],),
        )
        cats = [r["category_name"] for r in cur.fetchall()]
    return CategoryFavoritesResponse(categories=cats)


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


# ─── Telegram Mini-App Favorites (initData-authenticated) ──────────────────
# نفس نمط telegram-profile: التحقق بـ initData (لا JWT — مستخدم تيليجرام).
# يكتب في الجدول الموحّد user_favorites (platform='miniapp') + يُزامن
# bot_users.manual_favorites (dual-write) للتوافق مع استنتاج البوت والداشبورد.
@router.post("/telegram-favorites/list", response_model=FavoritesResponse)
@limiter.limit(LIMIT_TG_PROFILE_READ)
def telegram_favorites_list(
    payload: TelegramFavoritesListRequest,
    request: Request,
    conn=Depends(get_db),
):
    """قائمة مفضلة مستخدم الميني-ويب (من SSOT الموحّد)."""
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT store_id FROM user_favorites WHERE telegram_id = %s "
            "AND kind = 'store' ORDER BY created_at DESC",
            (telegram_id,),
        )
        favorites = [r["store_id"] for r in cur.fetchall()]

    return FavoritesResponse(favorites=favorites)


@router.post("/telegram-favorites", response_model=FavoritesResponse, status_code=201)
@limiter.limit(LIMIT_TG_FAVORITE)
def telegram_favorite_add(
    payload: TelegramFavoriteRequest,
    request: Request,
    conn=Depends(get_db),
):
    """إضافة متجر لمفضلة مستخدم الميني-ويب (idempotent)."""
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    username = tg_user.get("username") or tg_user.get("first_name") or "Anonymous"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

        # UPSERT bot_users + زامن manual_favorites (cache) — يضمن وجود السجل
        cur.execute(
            """
            INSERT INTO bot_users (telegram_id, username, joined_at, last_seen,
                                   user_status, manual_favorites)
            VALUES (%s, %s, NOW(), NOW(), 'Active', ARRAY[%s]::text[])
            ON CONFLICT (telegram_id) DO UPDATE
                SET manual_favorites = (
                        SELECT array_agg(DISTINCT x)
                        FROM unnest(array_append(
                            COALESCE(bot_users.manual_favorites, '{}'), EXCLUDED.manual_favorites[1]
                        )) AS x
                    ),
                    last_seen = NOW()
            """,
            (telegram_id, username, payload.store_id),
        )

        # SSOT الموحّد
        _uf_upsert(cur, payload.store_id, platform="miniapp", telegram_id=telegram_id)

        cur.execute(
            "SELECT store_id FROM user_favorites WHERE telegram_id = %s "
            "AND kind = 'store' ORDER BY created_at DESC",
            (telegram_id,),
        )
        favorites = [r["store_id"] for r in cur.fetchall()]

    return FavoritesResponse(favorites=favorites)


@router.delete("/telegram-favorites", response_model=FavoritesResponse)
@limiter.limit(LIMIT_TG_FAVORITE)
def telegram_favorite_remove(
    payload: TelegramFavoriteRequest,
    request: Request,
    conn=Depends(get_db),
):
    """حذف متجر من مفضلة مستخدم الميني-ويب."""
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE bot_users
            SET manual_favorites = array_remove(COALESCE(manual_favorites, '{}'), %s)
            WHERE telegram_id = %s
            """,
            (payload.store_id, telegram_id),
        )
        _uf_delete(cur, payload.store_id, telegram_id=telegram_id)

        cur.execute(
            "SELECT store_id FROM user_favorites WHERE telegram_id = %s "
            "AND kind = 'store' ORDER BY created_at DESC",
            (telegram_id,),
        )
        favorites = [r["store_id"] for r in cur.fetchall()]

    return FavoritesResponse(favorites=favorites)


# ─── Telegram Category Favorites (bot + miniapp) ───────────────────────────
# نفس نمط مفضلة المتاجر لكن للأقسام. لا dual-write — لا يوجد عمود manual
# للأقسام على bot_users، المصدر الوحيد هو user_favorites (kind='category').
@router.post("/telegram-favorite-categories/list",
             response_model=CategoryFavoritesResponse)
@limiter.limit(LIMIT_TG_PROFILE_READ)
def telegram_category_favorites_list(
    payload: TelegramFavoritesListRequest,
    request: Request,
    conn=Depends(get_db),
):
    """قائمة أقسام مفضلة مستخدم تيليجرام (بوت أو ميني-ويب)."""
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT category_name FROM user_favorites "
            "WHERE kind = 'category' AND telegram_id = %s "
            "ORDER BY created_at DESC",
            (telegram_id,),
        )
        cats = [r["category_name"] for r in cur.fetchall()]

    return CategoryFavoritesResponse(categories=cats)


@router.post("/telegram-favorite-categories",
             response_model=CategoryFavoritesResponse, status_code=201)
@limiter.limit(LIMIT_TG_FAVORITE)
def telegram_category_favorite_add(
    payload: TelegramCategoryFavoriteRequest,
    request: Request,
    conn=Depends(get_db),
):
    """إضافة قسم لمفضلة مستخدم تيليجرام (يتحقق من وجود القسم)."""
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    username = tg_user.get("username") or tg_user.get("first_name") or "Anonymous"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if not _category_exists(cur, payload.category_name):
            raise HTTPException(
                status_code=404,
                detail=f"category '{payload.category_name}' not found",
            )

        # نضمن وجود سجل bot_users (نفس النمط في telegram_favorite_add).
        cur.execute(
            """
            INSERT INTO bot_users (telegram_id, username, joined_at, last_seen, user_status)
            VALUES (%s, %s, NOW(), NOW(), 'Active')
            ON CONFLICT (telegram_id) DO UPDATE SET last_seen = NOW()
            """,
            (telegram_id, username),
        )

        _uf_category_upsert(cur, payload.category_name,
                            platform="miniapp", telegram_id=telegram_id)

        cur.execute(
            "SELECT category_name FROM user_favorites "
            "WHERE kind = 'category' AND telegram_id = %s "
            "ORDER BY created_at DESC",
            (telegram_id,),
        )
        cats = [r["category_name"] for r in cur.fetchall()]

    return CategoryFavoritesResponse(categories=cats)


@router.delete("/telegram-favorite-categories",
               response_model=CategoryFavoritesResponse)
@limiter.limit(LIMIT_TG_FAVORITE)
def telegram_category_favorite_remove(
    payload: TelegramCategoryFavoriteRequest,
    request: Request,
    conn=Depends(get_db),
):
    """حذف قسم من مفضلة مستخدم تيليجرام."""
    try:
        tg_user = verify_init_data(payload.init_data)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = int(tg_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        _uf_category_delete(cur, payload.category_name, telegram_id=telegram_id)
        cur.execute(
            "SELECT category_name FROM user_favorites "
            "WHERE kind = 'category' AND telegram_id = %s "
            "ORDER BY created_at DESC",
            (telegram_id,),
        )
        cats = [r["category_name"] for r in cur.fetchall()]

    return CategoryFavoritesResponse(categories=cats)
