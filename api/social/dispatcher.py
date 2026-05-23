"""
Dispatcher: يجلب المتجر من DB، يبني نص المنشور، ويوزّعه على كل poster مُسجَّل.
يُنفَّذ كـ FastAPI BackgroundTask — خارج سياق request — لذا يفتح اتصال مستقلاً.
"""
from __future__ import annotations

import traceback

from psycopg2.extras import RealDictCursor

from api.db import get_pool
from api.social.base import BaseSocialPoster, NotConfiguredError, PostResult
from api.social.platforms import REGISTERED_POSTERS
from api.social.template import build_post_text


def _fetch_store(conn, master_id: int) -> dict | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, store_id, public_coupon, last_time, description,
                   affiliate_link, logo_url
            FROM master
            WHERE id = %s
            """,
            (master_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _insert_log(
    conn,
    master_id: int,
    store_id: str,
    platform: str,
    post_text: str,
    image_url: str | None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO social_posts_log
                (master_id, store_id, platform, post_text, image_url, status)
            VALUES (%s, %s, %s, %s, %s, 'queued')
            RETURNING id
            """,
            (master_id, store_id, platform, post_text, image_url),
        )
        return cur.fetchone()[0]


def _update_log(
    conn,
    log_id: int,
    status: str,
    platform_post_id: str | None = None,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE social_posts_log
            SET status = %s,
                platform_post_id = %s,
                error_message = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, platform_post_id, error_message, log_id),
        )


def _run_one_poster(
    conn,
    master_id: int,
    store: dict,
    post_text: str,
    image_url: str | None,
    poster: BaseSocialPoster,
) -> None:
    """ينفّذ poster واحد، يسجّل النتيجة، يلتقط الاستثناءات بأمان."""
    log_id = _insert_log(
        conn,
        master_id=master_id,
        store_id=store["store_id"],
        platform=poster.name,
        post_text=post_text,
        image_url=image_url,
    )
    conn.commit()

    if not poster.is_configured():
        _update_log(conn, log_id, status="skipped", error_message="not configured")
        conn.commit()
        return

    try:
        result: PostResult = poster.post(post_text, image_url)
        if result.error:
            _update_log(conn, log_id, status="failed", error_message=result.error)
        else:
            _update_log(
                conn,
                log_id,
                status="sent",
                platform_post_id=result.platform_post_id,
            )
    except NotConfiguredError as e:
        _update_log(conn, log_id, status="skipped", error_message=str(e))
    except Exception as e:
        _update_log(
            conn,
            log_id,
            status="failed",
            error_message=f"{type(e).__name__}: {e}",
        )
        print(f"[social] {poster.name} crashed: {traceback.format_exc()}")
    finally:
        conn.commit()


def broadcast_to_all_platforms(master_id: int) -> None:
    """
    نقطة دخول الـ BackgroundTask.
    تجلب المتجر، تبني النص، توزّع على كل المنصات، تسجّل النتائج.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        store = _fetch_store(conn, master_id)
        if not store:
            print(f"[social] master_id={master_id} not found — skip broadcast.")
            return

        post_text = build_post_text(store)
        image_url = store.get("logo_url")

        for poster_cls in REGISTERED_POSTERS:
            try:
                poster = poster_cls()
            except Exception as e:
                print(f"[social] failed to instantiate {poster_cls.__name__}: {e}")
                continue
            _run_one_poster(conn, master_id, store, post_text, image_url, poster)
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)
