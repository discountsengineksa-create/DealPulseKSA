"""
fix_dashboard.py v2 — إصلاح شامل لأخطاء التنسيق في dashboard.py
"""
import re

with open('dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# ─────────────────────────────────────────────────────────────────────────────
# الثوابت: النصوص الصحيحة للـ class والدوال
# ─────────────────────────────────────────────────────────────────────────────

CORRECT_POOLEDCONN = '''\
class _PooledConn:
    __slots__ = ("_pool", "_conn")

    def __init__(self, pool: pg_pool.ThreadedConnectionPool, conn):
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_conn", conn)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name: str, value):
        if name in ("_pool", "_conn"):
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_conn"), name, value)

    def close(self):
        pool = object.__getattribute__(self, "_pool")
        conn = object.__getattribute__(self, "_conn")
        try:
            conn.autocommit = False
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)

'''

CORRECT_PAGE_TITLE = '''\
def page_title(emoji, text, subtitle=None):
    sub = (
        f\'<p style="text-align:center; font-size:1.05rem; \'
        f\'color:{BRAND["text_muted"]}; margin-top:-4px;">{subtitle}</p>\'
    ) if subtitle else ""
    st.markdown(
        f\'<h1 style="text-align:center; color:{BRAND["text"]}; \'
        f\'border-bottom:3px solid {BRAND["emerald"]}; padding-bottom:10px; \'
        f\'font-weight:900;">{emoji} {text}</h1>{sub}\',
        unsafe_allow_html=True,
    )

'''

CORRECT_KPI_CARD = '''\
def kpi_card(emoji, label, value, accent="emerald", note=None):
    palette = {
        "emerald": (BRAND["emerald_pastel"], BRAND["emerald"], BRAND["emerald_dark"]),
        "warning": (BRAND["warning_soft"],   BRAND["warning"], "#92400E"),
        "danger":  (BRAND["danger_soft"],    BRAND["danger"],  "#991B1B"),
        "info":    (BRAND["info_soft"],      BRAND["info"],    "#075985"),
        "neutral": ("#F9FAFB",               BRAND["text_muted"], "#374151"),
    }
    bg, bar, txt = palette.get(accent, palette["emerald"])
    note_html = (
        f\'<p style="color:{BRAND["text_muted"]}; margin:0; font-size:0.85rem;">{note}</p>\'
    ) if note else ""
    st.markdown(
        f\'<div style="background:{bg}; padding:20px; border-radius:14px; \'
        f\'border-right:5px solid {bar}; text-align:center; \'
        f\'box-shadow:0 2px 10px rgba(31,41,55,0.05); border:1px solid {BRAND["border"]};">\'
        f\'<h4 style="color:{txt}; margin:0; font-weight:700;">{emoji} {label}</h4>\'
        f\'<p style="font-size:2.4em; font-weight:900; color:{BRAND["text"]}; \'
        f\'margin:10px 0;">{value}</p>{note_html}</div>\',
        unsafe_allow_html=True,
    )

'''

# ─────────────────────────────────────────────────────────────────────────────
# أدوات مساعدة
# ─────────────────────────────────────────────────────────────────────────────

PAGE_MARKER_RE = re.compile(r'^(\s*)(if|elif)\s+page\s*==\s*"')

def indent_of(line):
    return len(line) - len(line.lstrip())

# ─────────────────────────────────────────────────────────────────────────────
# اكتشاف حدود الصفحات مع حفظ marker_indent
# ─────────────────────────────────────────────────────────────────────────────

page_boundaries = []   # list of (line_index, marker_indent)
for i, line in enumerate(lines):
    m = PAGE_MARKER_RE.match(line)
    if m:
        page_boundaries.append((i, len(m.group(1))))

page_boundaries.append((len(lines), 0))   # sentinel

# ─────────────────────────────────────────────────────────────────────────────
# المرحلة الأولى: ما قبل توجيه الصفحات (سطور 1 → first_page-1)
# ─────────────────────────────────────────────────────────────────────────────

first_page = page_boundaries[0][0]
result = []
i = 0

while i < first_page:
    line = lines[i]

    # إصلاح st.stop() على مستوى المودول
    if line.strip() == 'st.stop()' and indent_of(line) == 0:
        result.append('    st.stop()\n')
        i += 1
        continue

    # إصلاح _PooledConn class
    if line.strip().startswith('class _PooledConn:'):
        result.append(CORRECT_POOLEDCONN)
        i += 1
        while i < first_page and not lines[i].strip().startswith('def get_conn()'):
            i += 1
        continue

    # إصلاح page_title
    if line.strip().startswith('def page_title('):
        result.append(CORRECT_PAGE_TITLE)
        i += 1
        while i < first_page and not (lines[i].strip().startswith('def ') or
                                       lines[i].strip().startswith('# ---') or
                                       lines[i].strip().startswith('if _logo')):
            i += 1
        continue

    # إصلاح kpi_card
    if line.strip().startswith('def kpi_card('):
        result.append(CORRECT_KPI_CARD)
        i += 1
        while i < first_page and not (lines[i].strip().startswith('# ---') or
                                       lines[i].strip().startswith('if _logo')):
            i += 1
        continue

    result.append(line)
    i += 1

# إصلاح Sidebar expanders (radio خارج with)
result_str = ''.join(result)

result_str = result_str.replace(
    'with st.sidebar.expander("📋 القائمة الرئيسية", expanded=(_cur in _MAIN_PAGES)):\n'
    '    _idx = _MAIN_PAGES.index(_cur) if _cur in _MAIN_PAGES else None\n'
    '_sel = st.radio("", _MAIN_PAGES, index=_idx, key="r_main", label_visibility="collapsed")\n'
    'if _sel and _sel != _cur:\n'
    '    st.session_state.page = _sel\n'
    '    st.rerun()\n',
    'with st.sidebar.expander("📋 القائمة الرئيسية", expanded=(_cur in _MAIN_PAGES)):\n'
    '    _idx = _MAIN_PAGES.index(_cur) if _cur in _MAIN_PAGES else None\n'
    '    _sel = st.radio("", _MAIN_PAGES, index=_idx, key="r_main", label_visibility="collapsed")\n'
    '    if _sel and _sel != _cur:\n'
    '        st.session_state.page = _sel\n'
    '        st.rerun()\n'
)
result_str = result_str.replace(
    'with st.sidebar.expander("📊 التحليل", expanded=(_cur in _ANALYSIS_PAGES)):\n'
    '    _idx2 = _ANALYSIS_PAGES.index(_cur) if _cur in _ANALYSIS_PAGES else None\n'
    '_sel2 = st.radio("", _ANALYSIS_PAGES, index=_idx2, key="r_analysis", label_visibility="collapsed")\n'
    'if _sel2 and _sel2 != _cur:\n'
    '    st.session_state.page = _sel2\n'
    '    st.rerun()\n',
    'with st.sidebar.expander("📊 التحليل", expanded=(_cur in _ANALYSIS_PAGES)):\n'
    '    _idx2 = _ANALYSIS_PAGES.index(_cur) if _cur in _ANALYSIS_PAGES else None\n'
    '    _sel2 = st.radio("", _ANALYSIS_PAGES, index=_idx2, key="r_analysis", label_visibility="collapsed")\n'
    '    if _sel2 and _sel2 != _cur:\n'
    '        st.session_state.page = _sel2\n'
    '        st.rerun()\n'
)
result_str = result_str.replace(
    'with st.sidebar.expander("🔧 أدوات متقدمة", expanded=(_cur in _OTHER_PAGES)):\n'
    '    _idx3 = _OTHER_PAGES.index(_cur) if _cur in _OTHER_PAGES else None\n'
    '_sel3 = st.radio("", _OTHER_PAGES, index=_idx3, key="r_other", label_visibility="collapsed")\n'
    'if _sel3 and _sel3 != _cur:\n'
    '    st.session_state.page = _sel3\n'
    '    st.rerun()\n',
    'with st.sidebar.expander("🔧 أدوات متقدمة", expanded=(_cur in _OTHER_PAGES)):\n'
    '    _idx3 = _OTHER_PAGES.index(_cur) if _cur in _OTHER_PAGES else None\n'
    '    _sel3 = st.radio("", _OTHER_PAGES, index=_idx3, key="r_other", label_visibility="collapsed")\n'
    '    if _sel3 and _sel3 != _cur:\n'
    '        st.session_state.page = _sel3\n'
    '        st.rerun()\n'
)

# إعادة بناء النتيجة كـ list
result_lines_part1 = result_str.split('\n')
result = [l + '\n' for l in result_lines_part1]
if result and result[-1] == '\n':
    result.pop()

# ─────────────────────────────────────────────────────────────────────────────
# المرحلة الثانية: توجيه الصفحات
# ─────────────────────────────────────────────────────────────────────────────

def fix_page_block(block_lines, marker_indent=0):
    """
    يُصحح مسافات كتلة صفحة واحدة.
    marker_indent: مسافات سطر if/elif page == الأصلي (0 أو 4).
    """
    fixed = []
    n = len(block_lines)
    def next_nonblank_indent(j):
        for k in range(j + 1, min(j + 8, n)):
            if block_lines[k].strip():
                return indent_of(block_lines[k])
        return 99

    # is_broken يُحسب بعد تحديد module_base في المرحلة 2
    def is_broken(j, mb):
        """هل جسم try/except/finally المجاور مكسور (≤ module_base)؟"""
        return next_nonblank_indent(j) <= mb

    # ── المرحلة 1: أسطر body الأصلية (indent > marker_indent) ─────────────
    j = 0
    while j < n:
        line = block_lines[j]
        if not line.strip():
            fixed.append(line)
            j += 1
            continue
        ci = indent_of(line)
        if ci <= marker_indent:
            break                          # خروج إلى مرحلة module
        new_ind = ci - marker_indent       # تطبيع: marker → 0، body → 4
        fixed.append(' ' * new_ind + line.lstrip())
        j += 1

    # ── المرحلة 2: أسطر module-level ──────────────────────────────────────
    # تحديد module_base ديناميكياً: أدنى مسافة في أول سطر غير فارغ
    module_base = 0
    for k in range(j, n):
        if block_lines[k].strip():
            module_base = min(marker_indent, indent_of(block_lines[k]))
            break

    STATE_PAGE = 'page'
    STATE_TRY  = 'try'
    STATE_EXC  = 'exc'
    STATE_FIN  = 'fin'
    state  = STATE_PAGE
    broken = False

    while j < n:
        line = block_lines[j]

        if not line.strip():
            fixed.append(line)
            j += 1
            continue

        ci      = indent_of(line)
        stripped = line.strip()
        at_mod  = (ci <= module_base)

        is_try_kw = (stripped == 'try:')               and at_mod
        is_exc_kw = stripped.startswith('except')      and at_mod
        is_fin_kw = (stripped == 'finally:')           and at_mod

        # Extended detection: outer except/finally may sit at module_base+4
        # (mismatched indentation in original) — only when we're in a broken try
        # and the clause body is broken (≤ the clause's own indent level).
        if not is_exc_kw and broken and state == STATE_TRY:
            if stripped.startswith('except') and ci == module_base + 4:
                if next_nonblank_indent(j) <= ci:  # body at same/lower level = broken
                    is_exc_kw = True
        if not is_fin_kw and state in (STATE_TRY, STATE_EXC):
            if stripped == 'finally:' and ci == module_base + 4:
                is_fin_kw = True

        # الأولوية القصوى: جسم مكسور على مستوى module
        # (حتى لو الكلمة هي try:، إذا broken → معاملتها ككود عادي داخل الجسم المكسور)
        if broken and at_mod and not (is_exc_kw or is_fin_kw):
            fixed.append('        ' + stripped + '\n')

        # ── try ───────────────────────────────────────────────────────────
        elif is_try_kw:
            # try سابق مفتوح بدون except → أضف except وهمي
            if state == STATE_TRY:
                fixed.append('    except Exception:\n')
                fixed.append('        pass\n')
            broken = is_broken(j, module_base)
            state  = STATE_TRY
            fixed.append('    try:\n')

        # ── except ────────────────────────────────────────────────────────
        elif is_exc_kw:
            if state == STATE_PAGE:
                fixed.append('    try:\n')
                fixed.append('        pass\n')
            broken = is_broken(j, module_base)
            state  = STATE_EXC
            fixed.append('    ' + stripped + '\n')

        # ── finally ───────────────────────────────────────────────────────
        elif is_fin_kw:
            if state == STATE_PAGE:
                fixed.append('    try:\n')
                fixed.append('        pass\n')
            broken = is_broken(j, module_base)
            state  = STATE_FIN
            fixed.append('    finally:\n')

        # ── سطر متداخل داخل جسم مكسور (فوق مستوى module) ─────────────────
        elif broken and not at_mod:
            # In except/finally body, lines at module_base+4 are broken body → strip them
            if module_base == 0 and state in (STATE_EXC, STATE_FIN) and ci == module_base + 4:
                fixed.append('        ' + stripped + '\n')
            elif module_base == 0:
                fixed.append('        ' + line)
            else:
                fixed.append('    ' + line)

        # ── كود عادي على مستوى الصفحة ─────────────────────────────────────
        elif at_mod:
            fixed.append('    ' + stripped + '\n')

        # ── كود متداخل داخل كود مستوى الصفحة ────────────────────────────
        else:
            if module_base == 0:
                fixed.append('    ' + line)
            else:
                fixed.append(line)

        j += 1

    return fixed


# معالجة كتل الصفحات
for blk_idx in range(len(page_boundaries) - 1):
    start, marker_indent = page_boundaries[blk_idx]
    end                  = page_boundaries[blk_idx + 1][0]

    # سطر الماركر: تطبيع (إزالة مسافات + elif → if)
    page_line = lines[start]
    marker_stripped = page_line.strip()
    if marker_stripped.startswith('elif '):
        marker_stripped = 'if ' + marker_stripped[5:]
    result.append(marker_stripped if marker_stripped.endswith('\n') else marker_stripped + '\n')

    # معالجة محتوى الكتلة
    block      = lines[start + 1:end]
    fixed_block = fix_page_block(block, marker_indent)
    result.extend(fixed_block)

# ─────────────────────────────────────────────────────────────────────────────
# كتابة الملف الناتج
# ─────────────────────────────────────────────────────────────────────────────
with open('dashboard_fixed.py', 'w', encoding='utf-8') as f:
    f.writelines(result)

print('Done! Check dashboard_fixed.py')
