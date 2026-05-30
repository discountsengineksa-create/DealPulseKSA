"""
التحقق من Telegram WebApp initData وفق المواصفة الرسمية:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

السبب الأمني:
    أي عميل يقدر يرسل POST لأي endpoint مع telegram_id مزيف. الميني-ويب
    يحصل initData موقّع من تيليجرام عبر `window.Telegram.WebApp.initData`،
    وهذه الدالة تتحقق أن التوقيع صحيح (HMAC-SHA256 بالـ bot_token) قبل
    قبول أي بيانات.

الاستخدام:
    from api.utils.telegram_init_data import verify_init_data, TelegramAuthError

    try:
        user = verify_init_data(init_data_raw, max_age_seconds=3600)
        # user = {"id": 123456789, "first_name": "...", ...}
    except TelegramAuthError as e:
        raise HTTPException(401, str(e))
"""
import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(Exception):
    """خطأ تحقق initData (توقيع غير صالح، منتهي الصلاحية، إلخ)."""


def _bot_token() -> str:
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramAuthError("BOT_TOKEN غير مضبوط في الـ environment")
    return token


def verify_init_data(init_data_raw: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """
    يتحقق من initData ويرجّع dict للمستخدم (id, first_name, ...).

    Args:
        init_data_raw: السلسلة الخام من `window.Telegram.WebApp.initData`
                       (URL-encoded query string).
        max_age_seconds: عمر أقصى لـ auth_date — افتراضي 24 ساعة.

    Raises:
        TelegramAuthError: لو initData فاضي، توقيع غلط، أو منتهي الصلاحية.

    Returns:
        dict للمستخدم: {"id": int, "first_name": str, "username": str?, ...}
    """
    if not init_data_raw or not isinstance(init_data_raw, str):
        raise TelegramAuthError("initData فارغ")

    # parse_qsl يفك URL-encoding تلقائياً
    pairs = parse_qsl(init_data_raw, keep_blank_values=True)
    data = dict(pairs)

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("hash مفقود في initData")

    # ─── 1. بناء data-check-string (مرتّب أبجدياً) ───────────────────────
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # ─── 2. اشتقاق المفتاح السرّي ────────────────────────────────────────
    # secret_key = HMAC_SHA256(key="WebAppData", message=bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=_bot_token().encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # ─── 3. حساب الـ hash المتوقّع ───────────────────────────────────────
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # ─── 4. مقارنة آمنة من timing-attacks ────────────────────────────────
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("توقيع initData غير صالح")

    # ─── 5. تحقق من العمر (auth_date) ────────────────────────────────────
    auth_date_str = data.get("auth_date")
    if not auth_date_str:
        raise TelegramAuthError("auth_date مفقود")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise TelegramAuthError("auth_date غير صالح")

    age = int(time.time()) - auth_date
    if age > max_age_seconds:
        raise TelegramAuthError(f"initData منتهي ({age}s > {max_age_seconds}s)")
    if age < -300:  # ساعة سماح للساعات غير المتزامنة
        raise TelegramAuthError("auth_date في المستقبل (الساعة غير متزامنة؟)")

    # ─── 6. استخراج بيانات المستخدم ──────────────────────────────────────
    user_json = data.get("user")
    if not user_json:
        raise TelegramAuthError("user مفقود في initData")
    try:
        user = json.loads(user_json)
    except json.JSONDecodeError:
        raise TelegramAuthError("user JSON غير صالح")

    if "id" not in user or not isinstance(user["id"], int):
        raise TelegramAuthError("user.id مفقود أو غير صالح")

    return user
