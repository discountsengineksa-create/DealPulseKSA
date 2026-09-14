# -*- coding: utf-8 -*-
import re

blog_path = r'C:\Users\PC\Desktop\dealpulseksa-web\lib\blog.ts'
with open(blog_path, encoding='utf-8') as f:
    text = f.read()

todo = open('scratch_thin_todo.txt', encoding='utf-8').read().splitlines()[1:]
todo = [s.strip() for s in todo if s.strip()]

parts = re.split(r"(?=^\s*slug:\s*')", text, flags=re.MULTILINE)
slug_to_body = {}
for p in parts:
    m = re.match(r"\s*slug:\s*'([^']+)'", p)
    if not m:
        continue
    slug_to_body[m.group(1)] = p

out = open('scratch_recheck_report.txt', 'w', encoding='utf-8')
genuinely_thin = []
already_fine = []
for slug in todo:
    body = slug_to_body.get(slug, '')
    # measure average length of bullet lines (a proxy for fragment-style vs real prose)
    bullets = re.findall(r'^\s*-\s*\*\*.*$', body, re.MULTILINE)
    if not bullets:
        continue
    avg_len = sum(len(b) for b in bullets) / len(bullets)
    total_chars = len(body)
    if avg_len < 45 and total_chars < 4500:
        genuinely_thin.append((slug, round(avg_len,1), total_chars))
    else:
        already_fine.append((slug, round(avg_len,1), total_chars))

out.write(f'genuinely thin (fragment-style, needs rewrite): {len(genuinely_thin)}\n')
for s,a,t in genuinely_thin:
    out.write(f'{s}\tavg_bullet_len={a}\ttotal_chars={t}\n')

out.write(f'\nalready reasonably substantive (skip/light-touch): {len(already_fine)}\n')
for s,a,t in already_fine:
    out.write(f'{s}\tavg_bullet_len={a}\ttotal_chars={t}\n')
out.close()
print(len(genuinely_thin), len(already_fine))
