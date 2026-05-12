"""
post_fix2.py — targeted fix for dashboard_fixed.py.

Main patterns to fix:
1. try at 8sp with no except at 8sp (except is at 4sp) →
   move try to 4sp, shift body -4sp
2. except/finally at wrong level vs their try →
   fix their level to match try
3. Repeat until py_compile passes.
"""
import py_compile, re, sys

def ind(line):
    return len(line) - len(line.lstrip())

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()

def write(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def check(path):
    try:
        py_compile.compile(path, doraise=True)
        return None, ''
    except py_compile.PyCompileError as e:
        msg = str(e)
        m = re.search(r'line (\d+)', msg)
        lineno = int(m.group(1)) if m else 0
        kind = ('IndentationError' if 'IndentationError' in msg
                else 'SyntaxError')
        detail = ('unexpected_indent' if 'unexpected indent' in msg
                  else 'empty_block' if 'expected an indented block' in msg
                  else 'unindent' if 'unindent does not match' in msg
                  else 'expected_except' if 'expected' in msg and 'except' in msg
                  else 'syntax')
        return lineno, f'{kind}:{detail}'

# ── Fix pattern 1: try@8sp with except/finally at 4sp ────────────────────────
def fix_try8_exc4(lines):
    """
    Find all try: at exactly 8sp that have no matching except/finally at 8sp.
    Shift them (and their body) down by 4sp.
    Returns (new_lines, changed:bool).
    """
    new = list(lines)
    i = 0
    changed = False
    while i < len(new):
        l = new[i]
        if l.rstrip() == '        try:':   # exactly 8sp
            # Look ahead for the except/finally
            # Find next except/finally/try at 8sp or lower
            j = i + 1
            found_at = None
            while j < len(new):
                lj = new[j]
                if not lj.strip():
                    j += 1; continue
                ci = ind(lj)
                sj = lj.strip()
                if (sj.startswith('except') or sj == 'finally:') and ci == 8:
                    found_at = 8   # already at 8sp, fine
                    break
                if (sj.startswith('except') or sj == 'finally:') and ci < 8:
                    found_at = ci
                    break
                if (sj.startswith('except') or sj == 'finally:') and ci > 8:
                    j += 1; continue
                if ci <= 8 and sj not in ('', ):
                    # Reached something at 8sp or lower that's NOT except/finally
                    # The try has no except → needs to be fixed
                    found_at = None
                    break
                j += 1

            if found_at is None or found_at < 8:
                # This try@8sp has no except at 8sp → shift it to 4sp
                # Move try line from 8sp to 4sp
                new[i] = '    try:\n'
                # Find the extent of the try body (lines at > 8sp, until exc/fin/page)
                k = i + 1
                while k < len(new):
                    lk = new[k]
                    if not lk.strip():
                        k += 1; continue
                    ck = ind(lk)
                    sk = lk.strip()
                    if ck <= 8:
                        break
                    # Shift: 12sp → 8sp, 16sp → 12sp, etc. (subtract 4sp)
                    new[k] = ' ' * (ck - 4) + sk + '\n'
                    k += 1
                changed = True
                i = k  # skip ahead
                continue
        i += 1
    return new, changed

# ── Fix pattern 2: except/finally at wrong level ─────────────────────────────
def fix_except_level(lines, err_lineno):
    """
    At err_lineno (1-based), except/finally is at wrong indent.
    Find nearest try: and realign.
    """
    idx = err_lineno - 1
    l = lines[idx]
    stripped = l.strip()
    if not (stripped.startswith('except') or stripped == 'finally:'):
        return lines, False

    ci = ind(l)

    # Walk backward to find matching try
    depth = 0
    for k in range(idx - 1, max(0, idx - 200), -1):
        lk = lines[k]
        if not lk.strip():
            continue
        ck = ind(lk)
        sk = lk.strip()
        if (sk.startswith('except') or sk == 'finally:') and ck == ci:
            depth += 1
        if sk == 'try:':
            if depth == 0:
                # Found the matching try
                lines[idx] = ' ' * ck + stripped + '\n'
                # Also fix the body of this clause (next lines until next clause at ck)
                target_body = ck + 4
                j = idx + 1
                while j < len(lines):
                    lj = lines[j]
                    if not lj.strip():
                        j += 1; continue
                    cj = ind(lj)
                    sj = lj.strip()
                    if (sj.startswith('except') or sj == 'finally:' or sj == 'try:') and cj <= ck + 4:
                        break
                    if re.match(r'^if page == ', lj):
                        break
                    if cj < target_body:
                        lines[j] = ' ' * target_body + sj + '\n'
                    j += 1
                return lines, True
            else:
                depth -= 1
        if re.match(r'^if page == ', lk):
            break

    return lines, False

# ── Fix unexpected indent ─────────────────────────────────────────────────────
def fix_unexpected_indent(lines, err_lineno):
    idx = err_lineno - 1
    l = lines[idx]
    stripped = l.strip()
    ci = ind(l)

    # Find the expected indent level from context
    for k in range(idx - 1, max(0, idx - 30), -1):
        prev = lines[k]
        if not prev.strip():
            continue
        pci = ind(prev)
        ps = prev.strip()
        if ps.endswith(':'):
            expected = pci + 4
            if ci != expected:
                lines[idx] = ' ' * expected + stripped + '\n'
            return lines, True
        elif pci < ci:
            lines[idx] = ' ' * pci + stripped + '\n'
            return lines, True

    return lines, False

# ── Fix empty block (expected indented block) ─────────────────────────────────
def fix_empty_block(lines, err_lineno):
    idx = err_lineno - 1
    # Find the block opener (line before err_lineno that ends with :)
    for k in range(idx - 1, max(0, idx - 5), -1):
        l = lines[k]
        if l.strip() and l.strip().endswith(':'):
            ck = ind(l)
            lines.insert(k + 1, ' ' * (ck + 4) + 'pass\n')
            return lines, True
    return lines, False

# ── Fix unindent mismatch ─────────────────────────────────────────────────────
def fix_unindent(lines, err_lineno):
    idx = err_lineno - 1
    l = lines[idx]
    stripped = l.strip()
    ci = ind(l)

    # Find nearest legal indent level
    seen_indents = set()
    for k in range(idx - 1, max(0, idx - 100), -1):
        lk = lines[k]
        if lk.strip():
            seen_indents.add(ind(lk))

    # Find the closest indent level that's <= ci
    valid = sorted([x for x in seen_indents if x < ci], reverse=True)
    if valid:
        lines[idx] = ' ' * valid[0] + stripped + '\n'
        return lines, True

    return lines, False

# ── Main loop ─────────────────────────────────────────────────────────────────
path = 'dashboard_fixed.py'

# First pass: fix all try@8sp globally
lines = read(path)
for _ in range(10):
    lines, changed = fix_try8_exc4(lines)
    if not changed:
        break
write(path, lines)
print('try@8sp pass done.')

# Check for remaining try@4sp with body not at 8sp (body at same level)
lines = read(path)
i = 0
changed_body = False
while i < len(lines):
    l = lines[i]
    if l.rstrip() == '    try:':   # exactly 4sp
        # Check body
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines):
            body_ci = ind(lines[j])
            if body_ci == 4:  # broken try: body at same level as try
                # Shift body to 8sp until except/finally/lower indent
                k = j
                while k < len(lines):
                    lk = lines[k]
                    if not lk.strip():
                        k += 1; continue
                    ck = ind(lk)
                    sk = lk.strip()
                    if sk.startswith('except') or sk == 'finally:' or ck < 4:
                        break
                    if ck == 4:
                        lines[k] = '        ' + sk + '\n'
                        changed_body = True
                    elif ck > 4:
                        lines[k] = ' ' * (ck + 4) + sk + '\n'
                        changed_body = True
                    k += 1
                i = k
                continue
    i += 1

if changed_body:
    write(path, lines)
    print('broken-try-body pass done.')

# Iterative error fixing
lines = read(path)
MAX_ITER = 80
for iteration in range(1, MAX_ITER + 1):
    write(path, lines)
    lineno, kind = check(path)
    if lineno is None:
        print(f'SUCCESS after {iteration-1} fixes!')
        break

    print(f'[{iteration}] {kind} @ L{lineno}: {lines[lineno-1].rstrip()[:60]!r}')

    if 'SyntaxError' in kind:
        lines, ok = fix_except_level(lines, lineno)
        if not ok:
            # Try fixing as unexpected indent
            lines, ok = fix_unexpected_indent(lines, lineno)
    elif 'empty_block' in kind:
        lines, ok = fix_empty_block(lines, lineno)
    elif 'unexpected_indent' in kind:
        lines, ok = fix_unexpected_indent(lines, lineno)
    elif 'unindent' in kind:
        lines, ok = fix_unindent(lines, lineno)
    else:
        lines, ok = fix_except_level(lines, lineno)
        if not ok:
            lines, ok = fix_unexpected_indent(lines, lineno)

write(path, lines)
