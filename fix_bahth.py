"""
fix_bahth.py — fixes the البحث عن كود block in dashboard_fixed.py by:
1. Shifting all body lines by -4sp
2. Restoring the missing 'with tab_analytics:' line
Then runs iterative fixes for remaining errors.
"""
import re, py_compile

def check(lines):
    code = ''.join(lines)
    try:
        compile(code, 'dashboard_fixed.py', 'exec')
        return None, ''
    except SyntaxError as e:
        return e.lineno or 0, type(e).__name__ + ':' + str(e)

def ind(line):
    return len(line) - len(line.lstrip())

with open('dashboard_fixed.py', encoding='utf-8') as f:
    lines = f.readlines()

# Find the block
start = None
end = None
for i, l in enumerate(lines):
    if re.match(r'^if page == "البحث عن كود"', l):
        start = i
    elif start is not None and re.match(r'^if page == "', l):
        end = i
        break
if end is None:
    end = len(lines)

print(f'Found block: L{start+1} to L{end}')

# Shift body lines by -4sp
new_lines = list(lines)
for i in range(start+1, end):
    l = new_lines[i]
    if not l.strip():
        continue
    ci = ind(l)
    if ci >= 4:
        new_lines[i] = ' '*(ci-4) + l.lstrip()
    # Lines at < 4sp (0sp comments) stay as-is

# Fix: replace '    pass\n' before '        st.subheader(' with '    with tab_analytics:\n'
# (after the shift, 8sp pass becomes 4sp pass, 8sp st.subheader becomes 4sp)
# Actually after -4sp shift: pass at 8sp→4sp, st.subheader at 8sp→4sp
# We need to find the 'pass' that should be 'with tab_analytics:'
# Look in the block for the pattern: blank/pass before 'st.subheader("📊 تحليلات الأداء'
for i in range(start+1, end-1):
    l = new_lines[i]
    l_next = new_lines[i+1] if i+1 < len(new_lines) else ''
    if (l.strip() == 'pass' or l.strip() == 'pass  # AUTO-REMOVED') and 'تحليلات الأداء' in l_next:
        print(f'  Replacing pass at L{i+1} with with tab_analytics:')
        new_lines[i] = '    with tab_analytics:\n'
        break

# Also check for 'with tab_analytics:' being missing — look for st.subheader("📊 تحليلات الأداء"
for i in range(start+1, end):
    if 'تحليلات الأداء' in new_lines[i] and ind(new_lines[i]) == 4:
        # Check if previous non-blank line is 'with tab_analytics:'
        for k in range(i-1, max(0,i-5), -1):
            if new_lines[k].strip():
                if 'with tab_analytics:' not in new_lines[k]:
                    print(f'  Inserting with tab_analytics: before L{i+1}')
                    new_lines.insert(i, '    with tab_analytics:\n')
                    end += 1  # adjust end
                break
        break

# Write back
with open('dashboard_fixed.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Block fixed. Running iterative error fixer...')

# Iterative fixer
with open('dashboard_fixed.py', encoding='utf-8') as f:
    lines = f.readlines()

MAX = 200
prev = None
stuck = 0

for it in range(1, MAX+1):
    lineno, kind = check(lines)
    if lineno is None:
        with open('dashboard_fixed.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f'SUCCESS after {it-1} fixes!')
        break

    if lineno == prev:
        stuck += 1
    else:
        stuck = 0
    prev = lineno
    idx = lineno - 1

    if stuck >= 8:
        lines[idx] = '    pass\n'
        stuck = 0
        continue

    stripped = lines[idx].strip()
    ci = ind(lines[idx])

    if 'IndentationError' in kind:
        if 'unexpected indent' in kind:
            for k in range(idx-1, max(0,idx-30), -1):
                p = lines[k]
                if not p.strip(): continue
                pci = ind(p)
                ps = p.strip()
                if ps.endswith(':'):
                    lines[idx] = ' '*(pci+4) + stripped + '\n'; break
                if pci < ci:
                    lines[idx] = ' '*pci + stripped + '\n'; break
            else:
                lines[idx] = '    ' + stripped + '\n'
        elif 'expected an indented block' in kind:
            for k in range(idx-1, max(0,idx-5), -1):
                l = lines[k]
                if l.strip() and l.strip().endswith(':'):
                    lines.insert(k+1, ' '*(ind(l)+4)+'pass\n'); break
        elif 'unindent' in kind:
            seen = sorted(set(ind(lines[k]) for k in range(max(0,idx-100),idx) if lines[k].strip()))
            valid = [x for x in seen if x < ci]
            lines[idx] = ' '*(valid[-1] if valid else 4) + stripped + '\n'
        else:
            lines[idx] = '    ' + stripped + '\n'
    else:
        if stripped.startswith('except') or stripped == 'finally:':
            for k in range(idx-1, max(0,idx-300), -1):
                lk = lines[k]
                if not lk.strip(): continue
                if lk.strip() == 'try:':
                    lines[idx] = ' '*ind(lk) + stripped + '\n'; break
                if re.match(r'^if page == ', lk): break
            else:
                lines.insert(idx, ' '*ci+'try:\n')
                lines.insert(idx+1, ' '*(ci+4)+'pass\n')
        elif stripped == 'try:':
            j = idx+1
            while j < len(lines) and not lines[j].strip(): j+=1
            if j < len(lines) and ind(lines[j]) <= ci:
                k = j
                while k < len(lines):
                    lk = lines[k]
                    if not lk.strip(): k+=1; continue
                    ck = ind(lk)
                    sk = lk.strip()
                    if sk.startswith('except') or sk=='finally:': break
                    if re.match(r'^if page == ', lk): break
                    if ck <= ci:
                        lines[k] = ' '*(ci+4) + sk + '\n'
                    k += 1
        else:
            for k in range(idx-1, max(0,idx-5), -1):
                l = lines[k]
                if l.strip() and l.strip().endswith(':'):
                    if ind(lines[idx]) <= ind(l):
                        lines.insert(k+1, ' '*(ind(l)+4)+'pass\n')
                    break
            else:
                lines[idx] = '    ' + stripped + '\n'
else:
    with open('dashboard_fixed.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Still errors after {MAX} iterations. Last error at L{prev}')
