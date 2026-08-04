"""
يقارن تواريخ بدء المواسم بين مصدرها في ريبو الويب ونسختها في مُرسِل التذكيرات.

المشكلة التي يحلّها: `app/calendar/data.ts` هو مصدر الحقيقة للمواسم، لكن مُرسِل
التذكيرات بايثون ولا يقرأ TypeScript، فالتواريخ منسوخة يدوياً. النسخ اليدوي
ينحرف — وقد انحرف فعلاً في 8 مواسم من 12 لأن التواريخ اشتُقّت من أسماء العرض
(«11 نوفمبر») بدل حقل `start` (9 نوفمبر، وهو بداية النافذة لا يوم الذروة).

انحراف كهذا لا يُسقط شيئاً ولا يظهر في أي اختبار — الرسائل تُرسل ببساطة في
اليوم الخطأ. شغّل هذا بعد أي تعديل على مواسم التقويم.

    python check_season_dates.py
"""
from __future__ import annotations

import os
import re
import sys

WEB_DATA = os.path.expanduser(r"~/Desktop/dealpulseksa-web/app/calendar/data.ts")


def parse_web() -> dict[str, tuple[int, int]]:
    if not os.path.exists(WEB_DATA):
        sys.exit(f"❌ ملف المواسم غير موجود: {WEB_DATA}")
    src = open(WEB_DATA, encoding="utf-8").read()
    pattern = re.compile(
        r"id:\s*'([^']+)'.*?start:\s*\{\s*m:\s*(\d+),\s*d:\s*(\d+)\s*\}",
        re.S,
    )
    return {m[1]: (int(m[2]), int(m[3])) for m in pattern.finditer(src)}


def main() -> None:
    from api.workers.season_reminder_sender import SEASON_START as py

    web = parse_web()
    problems = 0

    for sid, wdate in sorted(web.items()):
        pdate = py.get(sid)
        if pdate is None:
            print(f"❌ ناقص في بايثون: {sid} → {wdate}")
            problems += 1
        elif pdate != wdate:
            print(f"❌ اختلاف: {sid} — الويب {wdate} · بايثون {pdate}")
            problems += 1

    for sid in sorted(set(py) - set(web)):
        print(f"⚠️  موجود في بايثون وغير موجود في الويب: {sid}")
        problems += 1

    if problems:
        sys.exit(f"\n{problems} مشكلة — حدّث SEASON_START في season_reminder_sender.py")
    print(f"✅ متطابق — {len(web)} موسماً في المصدرين")


if __name__ == "__main__":
    main()
