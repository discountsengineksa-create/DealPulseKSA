import py_compile, re, shutil, os

def check(path):
    try:
        py_compile.compile(path, doraise=True)
        return None, ''
    except py_compile.PyCompileError as e:
        msg = str(e)
        m = re.search(r'line (\d+)', msg)
        return int(m.group(1)) if m else 0, msg

shutil.copy('dashboard_fixed.py', 'dashboard_scan.py')

with open('dashboard_scan.py', encoding='utf-8') as f:
    lines = f.readlines()

errors = []
for _ in range(150):
    with open('dashboard_scan.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    lineno, msg = check('dashboard_scan.py')
    if not lineno:
        break
    kind = 'IndentationError' if 'IndentationError' in msg else 'SyntaxError'
    sub = 'unexpected_indent' if 'unexpected indent' in msg else \
          'empty_block' if 'expected an indented block' in msg else \
          'unindent' if 'unindent does not match' in msg else \
          'expected_except' if 'expected' in msg and 'except' in msg else 'other'
    errors.append((lineno, kind, sub))
    lines[lineno-1] = '    pass  # REMOVED\n'

os.remove('dashboard_scan.py')

with open('scan_results.txt', 'w', encoding='utf-8') as f:
    for lineno, kind, sub in errors:
        f.write(f'L{lineno} {kind}:{sub}\n')
    f.write(f'\nTotal: {len(errors)} errors\n')

print(f'Total errors found: {len(errors)}')
print('Written to scan_results.txt')
