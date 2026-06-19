"""Instagram Business — نشر صورة/كاروسيل/ستوري عبر Graph API.

Setup:
  1. Instagram Business account متّصل بـ Facebook Page (نفس Page المستخدمة لـ FB).
  2. صلاحيات الـ App: instagram_basic, instagram_content_publish, pages_show_list.
  3. env:
     IG_BUSINESS_ID=17841401234567890
     META_PAGE_ACCESS_TOKEN=<نفس التوكن الطويل المستخدم في Facebook>

ملاحظة: Instagram يتطلّب صورة (لا يقبل نص-فقط). image_url لازم يكون public HTTPS.

Flow (Single image):  create container → poll FINISHED → publish.
Flow (Carousel):      create child containers (per slide) → create parent
                      carousel container → poll FINISHED → publish.

كل خطوة container تحتاج polling لأن المعالجة async — لو نشرنا فوراً يطلع
«Media ID is not available».
"""
from __future__ import annotations

import os
import time

import requests

from api.social.base import BaseSocialPoster, PostResult

GRAPH = "https://graph.facebook.com/v21.0"

_POLL_INTERVAL_SEC = 2
_POLL_MAX_ATTEMPTS = 15  # 30 ثانية إجمالاً — كافية لصور صغيرة (carousel أبطأ قليلاً)
_POLL_MAX_ATTEMPTS_CAROUSEL = 25  # 50 ثانية — يحتاج معالجة كل child


class InstagramPoster(BaseSocialPoster):
    name = "instagram"

    def is_configured(self) -> bool:
        return bool(os.getenv("IG_BUSINESS_ID")) and bool(os.getenv("META_PAGE_ACCESS_TOKEN"))

    # ─────────────────────────────────────────────────────────────────
    # نقطة الدخول الموحّدة — تختار المسار بحسب نوع المُدخل
    # ─────────────────────────────────────────────────────────────────
    def post(self, text: str, image_url: str | None) -> PostResult:
        """نشر صورة واحدة. للحفاظ على التوافق مع dispatcher القديم."""
        return self._post_single(text, image_url)

    def post_carousel(self, text: str, image_urls: list[str]) -> PostResult:
        """نشر كاروسيل بعدة صور (2..10 صورة). يُسقط الـURLs الفاضية تلقائياً."""
        urls = [u for u in image_urls if u]
        if not urls:
            return PostResult(error="carousel needs at least 1 image_url")
        if len(urls) == 1:
            # كاروسيل بصورة واحدة = منشور عادي. نختصر للـsingle لتجنّب 400.
            return self._post_single(text, urls[0])
        if len(urls) > 10:
            urls = urls[:10]  # حدّ Instagram: 10 شرائح كحد أقصى

        ig_id, token, err = self._creds()
        if err:
            return PostResult(error=err)

        # Step 1: أنشئ child container لكل صورة (is_carousel_item=true)
        child_ids: list[str] = []
        for i, url in enumerate(urls):
            try:
                r = requests.post(
                    f"{GRAPH}/{ig_id}/media",
                    data={
                        "image_url": url,
                        "is_carousel_item": "true",
                        "access_token": token,
                    },
                    timeout=20,
                )
            except requests.RequestException as e:
                return PostResult(error=f"network (carousel child {i}): {e}")
            if r.status_code >= 400:
                return PostResult(
                    error=f"carousel child {i} HTTP {r.status_code}: {r.text[:200]}"
                )
            try:
                cid = r.json().get("id")
            except Exception:
                return PostResult(error=f"carousel child {i}: invalid response")
            if not cid:
                return PostResult(error=f"carousel child {i}: no id returned")
            child_ids.append(cid)

        # Step 2: poll كل child حتى FINISHED (children الفاضية تُسقط الـparent)
        for i, cid in enumerate(child_ids):
            status = self._poll_until_ready(cid, token, _POLL_MAX_ATTEMPTS)
            if status != "FINISHED":
                return PostResult(error=f"carousel child {i} not ready: {status}")

        # Step 3: أنشئ parent carousel container
        try:
            r = requests.post(
                f"{GRAPH}/{ig_id}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": ",".join(child_ids),
                    "caption": text,
                    "access_token": token,
                },
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network (carousel parent): {e}")
        if r.status_code >= 400:
            return PostResult(error=f"carousel parent HTTP {r.status_code}: {r.text[:300]}")

        try:
            parent_id = r.json().get("id")
        except Exception:
            return PostResult(error="carousel parent: invalid response")
        if not parent_id:
            return PostResult(error="carousel parent: no id returned")

        # Step 4: poll الـparent حتى FINISHED، ثم publish
        status = self._poll_until_ready(parent_id, token, _POLL_MAX_ATTEMPTS_CAROUSEL)
        if status != "FINISHED":
            return PostResult(error=f"carousel parent not ready: {status}")

        return self._publish(parent_id, token)

    def post_story(self, image_url: str) -> PostResult:
        """نشر صورة كـStory (تختفي بعد 24h). تُستخدم بعد منشور Feed لتعزيز الوصول."""
        if not image_url:
            return PostResult(error="story requires an image_url")

        ig_id, token, err = self._creds()
        if err:
            return PostResult(error=err)

        # Stories لا تقبل caption — النص يُتجاهل. media_type=STORIES.
        try:
            r = requests.post(
                f"{GRAPH}/{ig_id}/media",
                data={
                    "image_url": image_url,
                    "media_type": "STORIES",
                    "access_token": token,
                },
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network (story create): {e}")
        if r.status_code >= 400:
            return PostResult(error=f"story create HTTP {r.status_code}: {r.text[:300]}")

        try:
            cid = r.json().get("id")
        except Exception:
            return PostResult(error="story: invalid create response")
        if not cid:
            return PostResult(error="story: no creation_id")

        status = self._poll_until_ready(cid, token, _POLL_MAX_ATTEMPTS)
        if status != "FINISHED":
            return PostResult(error=f"story container not ready: {status}")

        return self._publish(cid, token)

    def post_reel(self, text: str, video_url: str, cover_url: str | None = None) -> PostResult:
        """نشر Reel فيديو. video_url لازم MP4 عام HTTPS، حد أقصى 100MB، 90 ثانية.
        cover_url اختياري — صورة الغلاف. لو ما توفّرت، Instagram يستخدم frame تلقائياً."""
        if not video_url:
            return PostResult(error="reel requires a video_url")

        ig_id, token, err = self._creds()
        if err:
            return PostResult(error=err)

        data = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": text,
            "share_to_feed": "true",  # يظهر في الـfeed العادي + قسم Reels
            "access_token": token,
        }
        if cover_url:
            data["cover_url"] = cover_url

        try:
            r = requests.post(f"{GRAPH}/{ig_id}/media", data=data, timeout=30)
        except requests.RequestException as e:
            return PostResult(error=f"network (reel create): {e}")
        if r.status_code >= 400:
            return PostResult(error=f"reel create HTTP {r.status_code}: {r.text[:300]}")

        try:
            cid = r.json().get("id")
        except Exception:
            return PostResult(error="reel: invalid create response")
        if not cid:
            return PostResult(error="reel: no creation_id")

        # Reels تحتاج معالجة فيديو أطول — حدّ أعلى للـpolling.
        status = self._poll_until_ready(cid, token, _POLL_MAX_ATTEMPTS_CAROUSEL)
        if status != "FINISHED":
            return PostResult(error=f"reel container not ready: {status}")

        return self._publish(cid, token)

    # ─────────────────────────────────────────────────────────────────
    # المسار القديم — single image (يحفظ التوافق مع dispatcher القديم)
    # ─────────────────────────────────────────────────────────────────
    def _post_single(self, text: str, image_url: str | None) -> PostResult:
        if not image_url:
            return PostResult(error="Instagram requires an image (logo_url empty)")

        ig_id, token, err = self._creds()
        if err:
            return PostResult(error=err)

        try:
            r = requests.post(
                f"{GRAPH}/{ig_id}/media",
                data={"image_url": image_url, "caption": text, "access_token": token},
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network (create): {e}")
        if r.status_code >= 400:
            return PostResult(error=f"create HTTP {r.status_code}: {r.text[:300]}")

        try:
            cid = r.json().get("id")
        except Exception:
            return PostResult(error="invalid create response")
        if not cid:
            return PostResult(error="no creation_id returned")

        status = self._poll_until_ready(cid, token, _POLL_MAX_ATTEMPTS)
        if status != "FINISHED":
            return PostResult(error=f"container not ready: {status}")

        return self._publish(cid, token)

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    def _creds(self) -> tuple[str | None, str | None, str | None]:
        """يقرأ (ig_id, token, error). error غير None لو شي مفقود."""
        ig_id = os.getenv("IG_BUSINESS_ID")
        token = os.getenv("META_PAGE_ACCESS_TOKEN")
        if not ig_id or not token:
            return None, None, "IG_BUSINESS_ID or META_PAGE_ACCESS_TOKEN missing"
        return ig_id, token, None

    def _poll_until_ready(self, container_id: str, token: str, max_attempts: int) -> str | None:
        """يستطلع status_code للـcontainer حتى FINISHED أو ERROR/EXPIRED أو نفاذ المحاولات.
        يُرجع آخر status معروف (FINISHED / ERROR / EXPIRED / None لو الـAPI فشل)."""
        last_status = None
        for _ in range(max_attempts):
            time.sleep(_POLL_INTERVAL_SEC)
            try:
                r = requests.get(
                    f"{GRAPH}/{container_id}",
                    params={"fields": "status_code,status", "access_token": token},
                    timeout=10,
                )
            except requests.RequestException:
                continue
            if r.status_code >= 400:
                continue
            try:
                last_status = r.json().get("status_code")
            except Exception:
                continue
            if last_status == "FINISHED":
                return "FINISHED"
            if last_status in ("ERROR", "EXPIRED"):
                return last_status
        return last_status

    def _publish(self, creation_id: str, token: str) -> PostResult:
        """ينشر الـcontainer النهائي. يُرجع platform_post_id أو error."""
        ig_id = os.getenv("IG_BUSINESS_ID")  # موجود لأن _creds() نجح
        try:
            r = requests.post(
                f"{GRAPH}/{ig_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network (publish): {e}")
        if r.status_code >= 400:
            return PostResult(error=f"publish HTTP {r.status_code}: {r.text[:300]}")
        try:
            pid = r.json().get("id", "")
            return PostResult(platform_post_id=str(pid))
        except Exception:
            return PostResult(platform_post_id="")
