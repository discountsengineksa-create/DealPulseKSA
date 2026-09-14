# -*- coding: utf-8 -*-
import re

blog_path = r'C:\Users\PC\Desktop\dealpulseksa-web\lib\blog.ts'
with open(blog_path, encoding='utf-8') as f:
    lines = f.readlines()

slug_re = re.compile(r"^\s*slug:\s*'([^']+)'")
bullet_re = re.compile(r'^\s*-\s*\*\*⚠️')

cur_slug = None
counts = {}
slug_at_line = {}
for i, line in enumerate(lines):
    m = slug_re.match(line)
    if m:
        cur_slug = m.group(1)
        slug_at_line[cur_slug] = i + 1
    if bullet_re.match(line) and cur_slug:
        counts[cur_slug] = counts.get(cur_slug, 0) + 1

affected = [(s, c) for s, c in counts.items() if c >= 3]
affected.sort(key=lambda x: -x[1])

out = open('scratch_thin_todo.txt', 'w', encoding='utf-8')
out.write(f'remaining slugs with >=3 decorative-warning bullets: {len(affected)}\n')
for s, c in affected:
    out.write(f'{s}\n')
out.close()
print(len(affected))
