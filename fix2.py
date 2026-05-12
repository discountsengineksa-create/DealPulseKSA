"""
fix2.py — rewrites dashboard.py with correct indentation.
Strategy per page-block:
  1. Split into pre-try lines and the main try/except/finally wrapper.
  2. Normalize: shift everything so the outermost content sits at 4sp.
  3. Fix any "broken try" where try body leaked to same indent as try keyword.
"""
import re, textwrap

with open('dashboard.py', 'r', encoding='utf-8') as f:
    src = f.read()

lines = src.splitlines(keepends=True)
n = len(lines)

PAGE_RE  = re.compile(r'^(\s*)(if|elif)\s+page\s*==\s*"')

def ind(line):
    return len(line) - len(line.lstrip())

def is_blank(line):
    return not line.strip() or line.strip().startswith('#') and False  # comments are not blank

# ── Locate page-block boundaries ─────────────────────────────────────────────
bounds = []   # (line_idx, marker_indent)
for i, l in enumerate(lines):
    m = PAGE_RE.match(l)
    if m:
        bounds.append((i, len(m.group(1))))
bounds.append((n, 0))  # sentinel

# ── Pre-page preamble: keep as-is ────────────────────────────────────────────
result = list(lines[:bounds[0][0]])

# ── Fix sidebar radio indent bugs (known patterns) ───────────────────────────
preamble = ''.join(result)
for key, label in [
    ('📋 القائمة الرئيسية', 'r_main'),
    ('📊 التحليل', 'r_analysis'),
    ('🔧 أدوات متقدمة', 'r_other'),
]:
    sfx = '_main' if 'القائمة' in key else ('_analysis' if 'التحليل' in key else '_other')
    var = f'_sel{sfx}'.replace('_main', '').replace('_sel_analysis', '_sel2').replace('_sel_other', '_sel3')
    # generic: just ensure radio/if are inside the with
    bad1 = f'with st.sidebar.expander("{key}"'
    if bad1 in preamble:
        # regex-replace: any 'radio' line starting at col 0 after the with
        preamble = re.sub(
            r'(with st\.sidebar\.expander\("' + re.escape(key) + r'"[^\n]*\n'
            r'(\s+[^\n]+\n)*?)'
            r'^(_sel\w* = st\.radio\([^\n]+\n'
            r'if _sel\w* and[^\n]+\n'
            r'    st\.session_state[^\n]+\n'
            r'    st\.rerun\(\)\n)',
            lambda m: m.group(1) + textwrap.indent(m.group(3), '    '),
            preamble, flags=re.MULTILINE
        )
result = [l + ('\n' if not l.endswith('\n') else '') for l in preamble.splitlines()]

# ── Process each page block ───────────────────────────────────────────────────

def fix_block(blk_lines, marker_indent):
    """
    Normalize a page-block's content lines.
    Returns list of fixed lines (already including the correct indentation).
    """
    # ── Phase A: body lines (indent > marker_indent) ── keep, re-base to marker→0
    out = []
    j = 0
    nblk = len(blk_lines)

    while j < nblk:
        l = blk_lines[j]
        if not l.strip():
            out.append(l); j += 1; continue
        ci = ind(l)
        if ci <= marker_indent:
            break
        new_ci = ci - marker_indent   # e.g. 8sp-4sp=4sp
        out.append(' ' * new_ci + l.lstrip())
        j += 1

    # ── Phase B: module-level content ── the messy part
    # Collect remaining lines
    rest = blk_lines[j:]

    # Find the minimum indent of non-blank lines in rest
    min_ci = min((ind(l) for l in rest if l.strip()), default=0)

    # Detect outer try/except/finally structure at min_ci level
    # We'll scan rest to find:
    #   outer_try_idx, outer_exc_idx, outer_fin_idx  (indices in rest[])
    outer_try = outer_exc = outer_fin = -1
    state = 'scan'   # 'scan', 'in_try', 'in_exc', 'in_fin'

    # First: find the LOWEST-indent try (= outer try at min_ci or min_ci+4)
    for k, l in enumerate(rest):
        if not l.strip():
            continue
        ci = ind(l)
        stripped = l.strip()
        # Try keyword: accept at min_ci or min_ci+4 (misaligned)
        if stripped == 'try:' and ci <= min_ci + 4 and outer_try == -1:
            outer_try = k
            state = 'in_try'
            continue
        # Except keyword: accept at min_ci to min_ci+8 (misaligned in either dir)
        if stripped.startswith('except') and ci <= min_ci + 8 and state in ('in_try', 'in_exc') and outer_exc == -1:
            outer_exc = k
            state = 'in_exc'
            continue
        # Finally keyword: same tolerance
        if stripped == 'finally:' and ci <= min_ci + 8 and state in ('in_try', 'in_exc', 'in_fin') and outer_fin == -1:
            outer_fin = k
            state = 'in_fin'
            continue

    # ── Build sections from rest ──────────────────────────────────────────────

    def normalize_section(sec_lines, base_ci, target_ci):
        """
        Shift sec_lines so that lines at base_ci map to target_ci.
        Lines with indent < base_ci also map to target_ci (they were at module level).
        """
        fixed = []
        for l in sec_lines:
            if not l.strip():
                fixed.append(l); continue
            ci = ind(l)
            if ci <= base_ci:
                fixed.append(' ' * target_ci + l.lstrip())
            else:
                extra = ci - base_ci
                fixed.append(' ' * (target_ci + extra) + l.lstrip())
        return fixed

    if outer_try == -1:
        # No try structure — just normalize everything to 4sp
        out.extend(normalize_section(rest, min_ci, 4))
        return out

    # ── Pre-try lines (before outer_try) ──────────────────────────────────────
    pre_try = rest[:outer_try]
    out.extend(normalize_section(pre_try, min_ci, 4))

    # ── try: line ────────────────────────────────────────────────────────────
    out.append('    try:\n')

    # ── try body ─────────────────────────────────────────────────────────────
    exc_start = outer_exc if outer_exc != -1 else (outer_fin if outer_fin != -1 else len(rest))
    try_body = rest[outer_try + 1 : exc_start]

    # Detect if try body is broken (min indent of body <= try indent)
    try_min = min((ind(l) for l in try_body if l.strip()), default=8)
    body_base = min(try_min, ind(rest[outer_try]))  # base = min(body, try keyword)
    out.extend(normalize_section(try_body, body_base, 8))

    # ── except / finally ─────────────────────────────────────────────────────
    if outer_exc != -1:
        exc_line = rest[outer_exc].strip()
        out.append('    ' + exc_line + '\n')

        fin_start = outer_fin if outer_fin != -1 else len(rest)
        exc_body = rest[outer_exc + 1 : fin_start]
        exc_min = min((ind(l) for l in exc_body if l.strip()), default=8)
        exc_base = min(exc_min, ind(rest[outer_exc]))
        out.extend(normalize_section(exc_body, exc_base, 8))

    if outer_fin != -1:
        out.append('    finally:\n')
        fin_body = rest[outer_fin + 1:]
        fin_min = min((ind(l) for l in fin_body if l.strip()), default=8)
        fin_base = min(fin_min, ind(rest[outer_fin]))
        out.extend(normalize_section(fin_body, fin_base, 8))
    elif outer_exc == -1:
        # No except — add dummy
        out.append('    except Exception:\n')
        out.append('        pass\n')

    return out


for blk_idx in range(len(bounds) - 1):
    start, marker_indent = bounds[blk_idx]
    end = bounds[blk_idx + 1][0]

    # Emit page marker (normalized to 0sp, elif→if)
    marker = lines[start].strip()
    if marker.startswith('elif '):
        marker = 'if ' + marker[5:]
    result.append(marker if marker.endswith('\n') else marker + '\n')

    block = lines[start + 1 : end]
    fixed = fix_block(block, marker_indent)
    result.extend(fixed)


# ── Merge consecutive blank lines → max 2 ────────────────────────────────────
out_lines = []
blank_count = 0
for l in result:
    if not l.strip():
        blank_count += 1
        if blank_count <= 2:
            out_lines.append(l)
    else:
        blank_count = 0
        out_lines.append(l)

with open('dashboard_fixed.py', 'w', encoding='utf-8') as f:
    f.writelines(out_lines)

print('Done. dashboard_fixed.py written.')
