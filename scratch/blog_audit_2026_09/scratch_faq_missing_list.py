# -*- coding: utf-8 -*-
import re

blog_path = r'C:\Users\PC\Desktop\dealpulseksa-web\lib\blog.ts'
with open(blog_path, encoding='utf-8') as f:
    text = f.read()

parts = re.split(r"(?=^\s*slug:\s*')", text, flags=re.MULTILINE)
missing = []
total = 0
for p in parts:
    m = re.match(r"\s*slug:\s*'([^']+)'", p)
    if not m:
        continue
    total += 1
    slug = m.group(1)
    if 'أسئلة شائعة' not in p and 'الأسئلة الشائعة' not in p:
        missing.append(slug)

out = open('scratch_faq_missing.txt', 'w', encoding='utf-8')
out.write(f'total articles: {total}\n')
out.write(f'missing FAQ section: {len(missing)}\n')
for s in missing:
    out.write(f'{s}\n')
out.close()
print(f'total={total} missing={len(missing)}')
