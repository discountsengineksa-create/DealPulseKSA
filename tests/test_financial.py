"""
3 اختبارات Financial Guardian — budget enforcement.

ملاحظة مهمة: precharge() يحوّل USD إلى int(round(usd * 100)) cents.
Python يستخدم banker's rounding، لذا 0.001 USD = 0 cents (يُهمَل).
نستخدم مبالغ كبيرة بما يكفي (≥ $0.10) لتجنّب هذه الفخّ.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_guardian_state():
    """ينظّف عداد الصرف اليومي بين كل اختبار."""
    from api.utils.financial_guardian import _alert_key, _spend_key
    from api.utils.redis_client import get_redis
    r = get_redis()
    try:
        r.set(_spend_key(), "0")
        r.set(_alert_key(), "")
    except Exception:
        pass
    yield
    try:
        r.set(_spend_key(), "0")
        r.set(_alert_key(), "")
    except Exception:
        pass


def test_guardian_precharge_under_cap_succeeds():
    """طلب ضمن السقف يُقبَل ويُسجَّل."""
    from api.utils.financial_guardian import current_spend_usd, precharge
    before = current_spend_usd()
    # $0.10 = 10 cents (تجاوز banker's rounding)
    ok = precharge(estimated_cost_usd=0.10, purpose="pytest-small")
    assert ok is True
    after = current_spend_usd()
    assert after >= before + 0.09, f"الصرف لم يرتفع: {before} → {after}"


def test_guardian_precharge_over_cap_refuses_and_refunds():
    """طلب يكسر السقف يُرفَض ويُسترَدّ الـ precharge."""
    from api.utils.financial_guardian import (
        cap_usd, current_spend_usd, precharge,
    )
    cap = cap_usd()
    spend_before = current_spend_usd()
    # نحاول precharge أكبر من السقف
    ok = precharge(estimated_cost_usd=cap + 100.0, purpose="pytest-huge")
    assert ok is False, "الـ precharge المتجاوز يجب أن يُرفض"
    # المهم: الـ refund أعاد العداد لمكانه
    spend_after = current_spend_usd()
    assert abs(spend_after - spend_before) < 0.01, \
        f"العداد لم يُسترَدّ: {spend_before} → {spend_after}"


def test_guardian_settle_adjusts_for_actual_cost():
    """settle() يُضيف/يُنقص الفرق بين تقدير والقيمة الفعلية."""
    from api.utils.financial_guardian import (
        current_spend_usd, precharge, settle,
    )
    spend_start = current_spend_usd()
    # نحجز $0.50 ونصرف فعلياً $0.20 (وفّرنا $0.30)
    assert precharge(estimated_cost_usd=0.50, purpose="pytest-settle") is True
    after_precharge = current_spend_usd()
    settle(actual_cost_usd=0.20, estimated_cost_usd=0.50)
    after_settle = current_spend_usd()

    # ارتفع 0.50 ثم نزل 0.30 = صافي +0.20
    assert after_precharge > after_settle, "settle لم يُخفّض الصرف"
    assert abs((after_settle - spend_start) - 0.20) < 0.02, \
        f"الصافي خاطئ: بدأ {spend_start}، انتهى {after_settle}"
