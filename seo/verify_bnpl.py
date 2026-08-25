"""
تحقّق حيّ من مزوّدي التقسيط (تابي/تمارا/مدفوع/ميس باي) لكل متجر في الكتالوج.

يقرأ `master` من قاعدة الإنتاج (قراءة فقط)، يزحف موقع كل متجر — الصفحة الرئيسية
وصفحتين داخليتين — ويبحث عن علامات المزوّدين في الـHTML، ثم يطبع خريطة جاهزة للصق
في `dealpulseksa-web/lib/payments.ts`.

    python seo/verify_bnpl.py            # طباعة الخريطة + ملخّص
    python seo/verify_bnpl.py --raw      # سطر لكل متجر بما فيه غير المؤكَّد

⚠️ حدّان يجب أن يبقيا مكتوبين في المخرَج نفسه:

1. **الصفحة الرئيسية إشارة ضعيفة.** المنيع يعرض `tabby` ٣٢ مرة على صفحة قسم
   و**صفراً** على صفحته الرئيسية — لذلك يزحف هذا السكربت صفحتين داخليتين، ومع ذلك
   يبقى الفحص جزئياً.
2. **الغياب ليس نفياً.** المواقع المُصيَّرة بجافاسكربت (نون، نمشي، علي اكسبرس،
   اتش اند ام، ماماز، إيرالو) لا يقرأها الزاحف فتخرج «غير مؤكَّدة». لا تكتب على
   الموقع أن متجراً «لا يوفّر التقسيط» اعتماداً على هذا المخرَج.

المطابقة على `madfu`/`mispay` **باللاتينية فقط** عمداً: كلمة «مدفوع» العربية تظهر في
نصوص عامة («المدفوع لاحقاً»، «غير مدفوع») فأنتجت إيجابيات كاذبة في أول تشغيل.
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import re
import sys
import urllib.parse as up

import psycopg2
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings()

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124 Safari/537.36'
    ),
    'Accept-Language': 'ar,en;q=0.8',
}

PATTERNS = {
    'tabby':  r'tabby|تابي',
    'tamara': r'tamara|تمارا',
    'madfu':  r'madfu',
    'mispay': r'mispay',
}

INNER_PAGE = re.compile(
    r'/(p|product|products|item|category|categories|c)/|c-\d+|/ar/|/collections?/',
    re.I,
)
ASSET = re.compile(r'\.(png|jpe?g|svg|css|js|webp|ico)$', re.I)

MAX_INNER_PAGES = 2
TIMEOUT = 25


def _hits(html: str) -> set[str]:
    return {name for name, pat in PATTERNS.items() if re.search(pat, html, re.I)}


def check_store(row: tuple[int, str, str]) -> tuple[int, str, int, set[str], str]:
    store_id, name, url = row
    found: set[str] = set()
    pages = 0
    err = ''
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url.strip(), timeout=TIMEOUT, allow_redirects=True, verify=False)
        pages += 1
        found |= _hits(resp.text)

        base = resp.url
        host = up.urlparse(base).netloc
        visited: set[str] = set()
        for href in re.findall(r'href="([^"#]+)"', resp.text):
            absolute = up.urljoin(base, href)
            if up.urlparse(absolute).netloc != host:
                continue
            if ASSET.search(absolute) or not INNER_PAGE.search(absolute):
                continue
            if absolute in visited or len(visited) >= MAX_INNER_PAGES:
                continue
            visited.add(absolute)
            try:
                inner = session.get(absolute, timeout=TIMEOUT, verify=False)
                pages += 1
                found |= _hits(inner.text)
            except requests.RequestException:
                pass
    except requests.RequestException as exc:
        err = type(exc).__name__
    return store_id, name, pages, found, err


def main() -> int:
    load_dotenv()
    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        print('DATABASE_URL غير موجود في .env', file=sys.stderr)
        return 1

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            'select id, store_id, affiliate_link from master '
            "where coalesce(affiliate_link, '') <> '' order by id"
        )
        rows = cur.fetchall()

    results = []
    with cf.ThreadPoolExecutor(8) as pool:
        results.extend(pool.map(check_store, rows))
    results.sort()

    order = ['tabby', 'tamara', 'madfu', 'mispay']
    supported = [r for r in results if r[3]]
    unverified = [r for r in results if not r[3] and not r[4]]
    failed = [r for r in results if r[4]]

    if '--raw' in sys.argv:
        for store_id, name, pages, found, err in results:
            state = '+'.join(sorted(found, key=order.index)) if found else (err or '-')
            print(f'{store_id:<4} {name:<28} pages={pages:<2} {state}')
        print()

    print('// مولَّد بـ seo/verify_bnpl.py — لا تحرّره يدوياً')
    print('export const STORE_BNPL: Record<string, BnplProvider[]> = {')
    for _, name, _, found, _ in supported:
        providers = ', '.join(f"'{p}'" for p in sorted(found, key=order.index))
        print(f"  '{name}': [{providers}],")
    print('};')
    print()
    print(
        f'// مؤكَّد: {len(supported)} · غير مؤكَّد (زُحف بلا علامة): {len(unverified)}'
        f' · تعذّر الزحف: {len(failed)} — الغياب ليس نفياً.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
