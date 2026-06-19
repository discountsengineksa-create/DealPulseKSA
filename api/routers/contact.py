"""Contact-channel redirects — رابط قصير على دومين نبض الصفقات يحوّل لواتساب.

GET /r/whatsapp
  يستجيب بـ 307 Redirect إلى رابط WhatsApp Business Short Link.

الهدف: محاولة إخفاء وجهة الرابط من الـpreview على بعض الأنظمة.
ملاحظة صريحة: iOS Safari يتعامل مع *.wa.me كـUniversal Link لتطبيق واتساب،
ويعرض الـaction sheet مع الوجهة المُحلّلة بغض النظر عن مصدر النقرة. لذا
هذا التحويل قد لا يخفي الرقم على iOS — لكنه مفيد لـ:
  1. تركيز كل أزرار «تواصل» على endpoint واحد قابل للتغيير لاحقاً
  2. تسجيل النقرة في server-side analytics لو احتجنا
  3. تجربة سلوك iOS تجريبياً (يفشل = ما خسرنا، ينجح = ربح)
"""
from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import RedirectResponse


router = APIRouter(prefix="/r", tags=["redirect"])

# WhatsApp Business Short Link لـ«نبض الصفقات» — يقبل override من env.
WHATSAPP_LINK = os.getenv("WHATSAPP_LINK", "https://wa.me/message/7MKFJOMBC3LIC1")


@router.get("/whatsapp")
def redirect_whatsapp() -> RedirectResponse:
    # 307 يحفظ method الـHTTP (مهم لـPOST، آمن لـGET).
    # المتصفح يتبع الـredirect ويصل لـwa.me — iOS Universal Link قد يتفاعل هناك.
    return RedirectResponse(url=WHATSAPP_LINK, status_code=307)
