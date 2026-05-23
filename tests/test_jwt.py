"""
3 اختبارات JWT — create, decode, expired.
لا تحتاج DB.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone


def test_jwt_create_and_decode():
    """token صحيح يفك بنفس البيانات."""
    from api.auth_utils import create_jwt_token, decode_jwt_token
    token = create_jwt_token(user_id=42, extra={"role": "user"})
    payload = decode_jwt_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
    assert "exp" in payload and "iat" in payload


def test_jwt_expired_returns_none():
    """token منتهي يرجع None بدل ما يرفع exception."""
    import jwt
    from api.auth_utils import JWT_ALGORITHM, JWT_SECRET, decode_jwt_token
    expired_payload = {
        "sub": "1",
        "iat": datetime.now(timezone.utc) - timedelta(days=60),
        "exp": datetime.now(timezone.utc) - timedelta(days=30),
    }
    token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    assert decode_jwt_token(token) is None


def test_jwt_invalid_signature_returns_none():
    """token موقّع بسرّ آخر يُرفض بصمت."""
    import jwt
    from api.auth_utils import JWT_ALGORITHM, decode_jwt_token
    fake_payload = {
        "sub": "999",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=1),
    }
    bad_token = jwt.encode(fake_payload, "wrong-secret-xxx", algorithm=JWT_ALGORITHM)
    assert decode_jwt_token(bad_token) is None
