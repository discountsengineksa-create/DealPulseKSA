"""
سكربت تشخيصي محلي — يكشف سبب HTTP 500 على /openapi.json في الإنتاج.

طريقة التشغيل (PowerShell على Windows):
    # تأكد أن .env معبأ، ثم:
    python diagnose_openapi.py

ما يفعله:
  1. يحمّل .env تلقائياً (لا تحتاج set env vars يدوياً)
  2. يحقن defaults لـ WEBHOOK_BASE_URL/WEBHOOK_SECRET إن نقصت (للتشخيص فقط)
  3. يستورد bot_app.py محلياً ويستدعي app.openapi() مباشرةً
  4. لو فشل، يعزل الـ route المُسبّب ويطبع المسار + الخطأ

ملاحظة Windows: يستخدم ASCII بدلاً من رموز Unicode حتى لا يفشل عند
توجيه الإخراج لملف عبر PowerShell (cp1252).
"""
from __future__ import annotations

import os
import sys
import traceback

from dotenv import load_dotenv
import os
load_dotenv() # هذا السطر سيجبر السكربت على قراءة ملف .env

# ─── تحميل .env تلقائياً + حقن defaults للتشخيص فقط ─────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# قيم placeholders آمنة فقط لاجتياز فحوصات الإقلاع — لا تُستخدم فعلياً.
os.environ.setdefault("WEBHOOK_BASE_URL", "https://localhost.diagnostic")
os.environ.setdefault("WEBHOOK_SECRET", "diagnostic_secret_at_least_32_chars_long_xx")
os.environ.setdefault("BOT_TOKEN", "diagnostic:placeholder")
os.environ.setdefault("DATABASE_URL", "postgresql://localhost/diagnostic")
os.environ.setdefault("JWT_SECRET", "diagnostic_jwt_secret_at_least_32_chars_long_xxx")

# تعطيل إقلاع الـ workers أثناء التشخيص (لا نحتاج Redis/DB حقيقي)
os.environ.setdefault("DISABLE_WORKERS", "1")

# Windows: حاول فرض UTF-8 على stdout/stderr لتفادي UnicodeEncodeError عند الـ redirect.
# errors="replace" يحوّل أي حرف غير قابل للترميز إلى '?' بدل crash.
for _stream_name in ("stdout", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> int:
    print("-" * 60)
    print("🔬 تشخيص /openapi.json — Deal Pulse KSA")
    print("-" * 60)

    # --- 1. استيراد التطبيق -----------------------------------------------
    try:
        print("\n[1/3] استيراد bot_app …")
        from bot_app import app
        print("    ✅ نجح الاستيراد")
    except Exception as exc:
        print(f"    ❌ فشل الاستيراد: {type(exc).__name__}: {exc}")
        print("\nStack trace:")
        traceback.print_exc()
        print(
            "\n💡 لو الخطأ بسبب env vars ناقصة، تأكّد من تعريف الـ متغيرات"
            " المطلوبة في .env قبل التشغيل."
        )
        return 1

    # --- 2. توليد الـ openapi schema --------------------------------------
    try:
        print("\n[2/3] توليد OpenAPI schema …")
        schema = app.openapi()
        print(f"    ✅ نجح — {len(schema.get('paths', {}))} مسار, "
              f"{len(schema.get('components', {}).get('schemas', {}))} schema")
    except Exception as exc:
        print(f"    ❌ فشل التوليد: {type(exc).__name__}: {exc}")
        print("\nStack trace:")
        traceback.print_exc()

        # محاولة تحديد الـ route المُسبّب
        print("\n[تشخيص] محاولة عزل المسار المُسبّب …")
        for route in app.routes:
            try:
                from fastapi.openapi.utils import get_openapi
                get_openapi(
                    title="test",
                    version="1.0",
                    routes=[route],
                )
            except Exception as inner:
                path = getattr(route, "path", "?")
                name = getattr(route, "name", "?")
                print(f"    ⚠️  مشكلة في: {path} ({name})")
                print(f"        الخطأ: {type(inner).__name__}: {str(inner)[:200]}")

        return 2

    # --- 3. مقارنة سريعة مع الإنتاج ----------------------------------------
    print("\n[3/3] مقارنة سريعة مع Railway production …")
    try:
        import urllib.request
        with urllib.request.urlopen(
            "https://dealpulseksa-production.up.railway.app/openapi.json",
            timeout=10,
        ) as resp:
            print(f"    الإنتاج: HTTP {resp.status}")
            if resp.status == 200:
                print("    ✅ الإنتاج يعمل الآن — لا حاجة للإصلاح")
    except urllib.error.HTTPError as e:
        print(f"    ❌ الإنتاج: HTTP {e.code} — {e.reason}")
        print(
            "\n💡 المحلي يعمل لكن الإنتاج يفشل = اختلاف بيئة (fastapi/pydantic)."
            "\n   راجع version على Railway: pip show fastapi pydantic starlette"
        )
    except Exception as exc:
        print(f"    تعذّر الاتصال بالإنتاج: {exc}")

    print("\n" + "-" * 60)
    print("✅ التشخيص اكتمل")
    return 0


if __name__ == "__main__":
    sys.exit(main())
