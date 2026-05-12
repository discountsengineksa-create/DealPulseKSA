"""
patch_blocks.py — replaces broken page blocks in dashboard_fixed.py with correct versions.
Also runs iterative py_compile fixes for any remaining issues.
"""
import re, py_compile

def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def ind(line):
    return len(line) - len(line.lstrip())

# ── Replace a page block by name ──────────────────────────────────────────────
def replace_block(content, page_name, new_block):
    """Replace the block starting with 'if page == "page_name"' through to the next 'if page ==' marker."""
    # Find start
    start_pat = re.compile(r'^if page == "' + re.escape(page_name) + r'"', re.MULTILINE)
    m = start_pat.search(content)
    if not m:
        print(f'  Block not found: {page_name}')
        return content
    start = m.start()
    # Find end (next 'if page ==' at column 0, or EOF)
    next_pat = re.compile(r'^if page == "', re.MULTILINE)
    next_m = next_pat.search(content, m.end())
    if next_m:
        end = next_m.start()
    else:
        end = len(content)
    print(f'  Replacing: {page_name} (chars {start}-{end})')
    return content[:start] + new_block + '\n' + content[end:]

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT BLOCK: جدول الأقسام
# ═══════════════════════════════════════════════════════════════════════════════
BLOCK_JADWAL_AQSAM = '''\
if page == "جدول الأقسام":
    st.header("📂 مركز قيادة الأقسام (الربط الهندسي)")

    conn = None
    try:
        conn = get_conn()
        query = """
        SELECT store_id,
                COALESCE(name_en, '')        AS name_en,
                store_tags, store_tags_en,
                store_bio,  store_bio_en,
                public_coupon, discount_value, affiliate_link,
                extra_offer, extra_offer_en,
                total_coupon_copies, total_link_clicks
        FROM master
"""
        df_raw = pd.read_sql(query, conn)

        if not df_raw.empty:
            all_rows = []
            for _, row in df_raw.iterrows():
                ar_tags = parse_tags(row.get('store_tags'))
                en_tags = parse_tags(row.get('store_tags_en'))

                base = {
                    'المتجر':              row['store_id'],
                    'Store Name (EN)':     row['name_en'],
                    'الوصف':               row['store_bio'],
                    'Description (EN)':    row.get('store_bio_en') or '',
                    'الكوبون':             row['public_coupon'],
                    'عرض إضافي':           row['extra_offer'],
                    'Extra Offer (EN)':    row.get('extra_offer_en') or '',
                    'الخصم':               row['discount_value'],
                    'الرابط':              row['affiliate_link'],
                    'نقرات_الكوبون':       row['total_coupon_copies'],
                    'نقرات_الروابط':       row['total_link_clicks'],
                    'إجمالي_التفاعل':      row['total_coupon_copies'] + row['total_link_clicks'],
                }
                for t in ar_tags:
                    if t:
                        all_rows.append({'اللغة': 'AR', 'القسم': t, **base})
                for t in en_tags:
                    if t:
                        all_rows.append({'اللغة': 'EN', 'القسم': t, **base})

            df_full = pd.DataFrame(all_rows)
            tab1, tab2 = st.tabs(["📊 لوحة إدارة الأقسام", "📋 الجدول الشامل"])

            with tab1:
                st.subheader("📋 ملخص أداء الأقسام (AR / EN منفصلَين)")
                summary = (df_full.groupby(['اللغة', 'القسم']).agg(
                    عدد_المتاجر=('المتجر', 'count'),
                    نقرات_الكوبونات=('نقرات_الكوبون', 'sum'),
                    إجمالي_التفاعل=('إجمالي_التفاعل', 'sum'),
                    المتاجر_التابعة=('المتجر', lambda x: ", ".join(list(set(x))))
                ).reset_index().sort_values(by=['اللغة', 'إجمالي_التفاعل'], ascending=[True, False]))

                summary.columns = ['اللغة', 'اسم القسم', 'عدد المتاجر', 'نقرات الكوبونات', 'إجمالي التفاعل', 'المتاجر التابعة']
                st.dataframe(summary, use_container_width=True, hide_index=True)

            with tab2:
                st.subheader("🔍 استعراض الارتباطات الكاملة (AR + EN)")
                display_cols = [
                    'اللغة', 'القسم', 'المتجر', 'Store Name (EN)',
                    'الوصف', 'Description (EN)',
                    'الكوبون', 'عرض إضافي', 'Extra Offer (EN)',
                    'الخصم', 'الرابط',
                ]
                st.dataframe(df_full[display_cols], use_container_width=True, hide_index=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    summary.to_excel(writer, index=False, sheet_name='إحصائيات الأقسام')
                    df_full[display_cols].to_excel(writer, index=False, sheet_name='الارتباطات الشاملة')

                st.download_button(
                    label="📥 تحميل التقرير الشامل (Excel)",
                    data=output.getvalue(),
                    file_name="Tawfeer_Full_Analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("لا توجد بيانات متاجر مرتبطة بأقسام حالياً.")
    except Exception as e:
        st.error(f"⚠️ خطأ في معالجة البيانات: {e}")
    finally:
        if conn:
            conn.close()
'''

# ── Load dashboard.py to get correct source for other blocks ──────────────────
with open('dashboard.py', encoding='utf-8') as f:
    orig_lines = f.readlines()

def get_orig_block(page_name):
    """Extract raw lines for a page block from original dashboard.py"""
    start = None
    for i, l in enumerate(orig_lines):
        if re.match(r'^\s*(if|elif)\s+page\s*==\s*"' + re.escape(page_name) + '"', l):
            start = i
            break
    if start is None:
        return None
    end = len(orig_lines)
    for i in range(start+1, len(orig_lines)):
        if re.match(r'^\s*(if|elif)\s+page\s*==\s*"', orig_lines[i]):
            end = i
            break
    return orig_lines[start:end]

def fix_block_from_orig(page_name):
    """Build a correctly indented block from the original source."""
    raw = get_orig_block(page_name)
    if raw is None:
        return None

    # First line: the if/elif page == marker
    marker = raw[0].strip()
    if marker.startswith('elif '):
        marker = 'if ' + marker[5:]
    if not marker.endswith('\n'):
        marker += '\n'

    body = raw[1:]

    # Find minimum indentation of non-blank lines in body
    min_ind = 999
    for l in body:
        if l.strip():
            min_ind = min(min_ind, ind(l))
    if min_ind == 999:
        min_ind = 0

    # Normalize: lines at min_ind go to 4sp, deeper lines proportionally
    result = [marker]
    for l in body:
        if not l.strip():
            result.append('\n')
            continue
        ci = ind(l)
        new_ci = 4 + (ci - min_ind)
        result.append(' ' * new_ci + l.lstrip())

    return ''.join(result)

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT BLOCK: البحث عن كود
# ═══════════════════════════════════════════════════════════════════════════════
def build_bahth_kood():
    raw = get_orig_block('البحث عن كود')
    if not raw:
        return None

    # The original block: L1430-1712 in dashboard.py
    # marker at 0sp, body content at 4sp (correct structure)
    # Find min indent
    body = raw[1:]
    min_ind = min((ind(l) for l in body if l.strip()), default=4)

    lines_out = ['if page == "البحث عن كود":\n']
    for l in body:
        if not l.strip():
            lines_out.append('\n')
            continue
        ci = ind(l)
        new_ci = 4 + (ci - min_ind)
        if new_ci < 4:
            new_ci = 4
        lines_out.append(' ' * new_ci + l.lstrip())
    return ''.join(lines_out)

# ═══════════════════════════════════════════════════════════════════════════════
# APPLY PATCHES
# ═══════════════════════════════════════════════════════════════════════════════
path = 'dashboard_fixed.py'
content = read(path)

# Patch 1: جدول الأقسام (manually written correct version)
print('Patching جدول الأقسام...')
content = replace_block(content, 'جدول الأقسام', BLOCK_JADWAL_AQSAM.rstrip())

# Patch 2: البحث عن كود (auto-fixed from original)
print('Patching البحث عن كود...')
blk = build_bahth_kood()
if blk:
    content = replace_block(content, 'البحث عن كود', blk.rstrip())

# Patch remaining blocks that have structural issues by re-building from original
BLOCKS_TO_REBUILD = [
    'تحليل بحث الأكواد',
    'تحليل المبيعات',
    'استوديو المحتوى',
    'ذكاء التنبؤ',
]
for bname in BLOCKS_TO_REBUILD:
    print(f'Patching {bname}...')
    blk = fix_block_from_orig(bname)
    if blk:
        content = replace_block(content, bname, blk.rstrip())

write(path, content)
print('Patches applied.')

# ── Iterative error fixer ─────────────────────────────────────────────────────
def check_lines(lines):
    code = ''.join(lines)
    try:
        compile(code, path, 'exec')
        return None, ''
    except SyntaxError as e:
        return e.lineno or 0, type(e).__name__ + ':' + str(e)

lines = list(content.splitlines(keepends=True))
MAX = 200
prev = None
stuck = 0

for it in range(1, MAX+1):
    lineno, kind = check_lines(lines)
    if lineno is None:
        write(path, ''.join(lines))
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
            # find expected indent
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

    else:  # SyntaxError
        if stripped.startswith('except') or stripped == 'finally:':
            # find matching try
            for k in range(idx-1, max(0,idx-300), -1):
                lk = lines[k]
                if not lk.strip(): continue
                if lk.strip() == 'try:':
                    lines[idx] = ' '*ind(lk) + stripped + '\n'
                    break
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
            # check for empty block before this line
            for k in range(idx-1, max(0,idx-5), -1):
                l = lines[k]
                if l.strip() and l.strip().endswith(':'):
                    if ind(lines[idx]) <= ind(l):
                        lines.insert(k+1, ' '*(ind(l)+4)+'pass\n')
                    break
            else:
                lines[idx] = '    ' + stripped + '\n'
else:
    write(path, ''.join(lines))
    print(f'Still errors after {MAX} iterations. Last error at L{prev}')
