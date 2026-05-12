"""
post_fix.py — targeted iterative syntax-error fixer for dashboard_fixed.py.
Reads dashboard_fixed.py, finds syntax/indent errors via py_compile,
applies heuristic patches, repeats until clean.
"""
import py_compile, re, sys

MAX_ITER = 60

def compile_check(path):
    try:
        py_compile.compile(path, doraise=True)
        return None, None
    except py_compile.PyCompileError as exc:
        msg = str(exc)
        m = re.search(r'line (\d+)', msg)
        lineno = int(m.group(1)) if m else None
        kind = 'IndentationError' if 'IndentationError' in msg else 'SyntaxError'
        return lineno, kind

def read_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()

def write_lines(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def ind(line):
    return len(line) - len(line.lstrip())

def find_page_block_start(lines, lineno):
    """Find the start of the if page == block that contains lineno."""
    for i in range(lineno - 2, -1, -1):
        if re.match(r'^if page == ', lines[i]):
            return i
    return 0

def find_matching_try(lines, exc_lineno):
    """
    Find the try: that matches the except/finally at exc_lineno (0-based).
    Returns (try_lineno, try_indent) or (None, None).
    """
    exc_ind = ind(lines[exc_lineno])
    # Walk backwards from exc_lineno to find a try: at <= exc_ind
    # that has no matching except between it and our line
    for i in range(exc_lineno - 1, -1, -1):
        l = lines[i]
        if not l.strip():
            continue
        ci = ind(l)
        stripped = l.strip()
        if stripped == 'try:' and ci <= exc_ind:
            return i, ci
        # Stop at page boundary
        if re.match(r'^if page == ', l):
            break
    return None, None

def fix_try_mismatch(lines, err_lineno):
    """
    Fix try/except/finally indentation mismatch.
    err_lineno is 1-based.
    """
    idx = err_lineno - 1  # 0-based

    stripped = lines[idx].strip()
    is_except = stripped.startswith('except')
    is_finally = stripped == 'finally:'
    is_try = stripped == 'try:'

    if is_except or is_finally:
        # Find the matching try
        try_idx, try_ci = find_matching_try(lines, idx)
        if try_idx is None:
            # No matching try found — look for a try in the same page block
            # and align with it
            block_start = find_page_block_start(lines, idx)
            # Scan forward from block_start for a try at 4sp
            for k in range(block_start, idx):
                if lines[k].strip() == 'try:' and ind(lines[k]) == 4:
                    try_ci = 4
                    try_idx = k
                    break
            if try_idx is None:
                # Insert a dummy try above this except
                lines.insert(idx, '    try:\n')
                lines.insert(idx + 1, '        pass\n')
                return lines

        # Set except/finally to same indent as try
        lines[idx] = ' ' * try_ci + stripped + '\n'

        # Also fix the body of the except/finally (lines after it until next
        # clause or block end, that are at wrong indent)
        target_body_ci = try_ci + 4
        j = idx + 1
        while j < len(lines):
            l = lines[j]
            if not l.strip():
                j += 1; continue
            ci = ind(l)
            s = l.strip()
            # Stop at next except/finally/try at same or lower level
            if (s.startswith('except') or s == 'finally:' or s == 'try:') and ci <= try_ci + 4:
                break
            # Stop at new page block or end
            if re.match(r'^if page == ', l):
                break
            if ci != target_body_ci and ci < target_body_ci:
                lines[j] = ' ' * target_body_ci + s + '\n'
            j += 1

        return lines

    if is_try:
        # try: at unexpected indent — find surrounding context
        ci = ind(lines[idx])
        # Look at the next non-blank line
        j = idx + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines):
            next_ci = ind(lines[j])
            if next_ci <= ci:
                # Try body not indented — this is a broken try
                # Indent the body lines until except/finally/end
                target = ci + 4
                k = j
                while k < len(lines):
                    l = lines[k]
                    if not l.strip():
                        k += 1; continue
                    kci = ind(l)
                    ks = l.strip()
                    if ks.startswith('except') or ks == 'finally:' or re.match(r'^if page == ', l):
                        break
                    if kci <= ci:
                        lines[k] = ' ' * target + ks + '\n'
                    k += 1
        return lines

    return lines


def fix_empty_block(lines, err_lineno):
    """
    Fix 'expected an indented block after X' by inserting pass.
    """
    idx = err_lineno - 1  # error is AT this line, the empty block is one line before
    # The block opener should be at err_lineno - 1 (1-based) = idx - 1 (0-based)
    opener_idx = idx - 1
    while opener_idx >= 0 and not lines[opener_idx].strip():
        opener_idx -= 1
    if opener_idx >= 0:
        opener = lines[opener_idx]
        opener_stripped = opener.strip()
        if opener_stripped.endswith(':'):
            opener_ci = ind(opener)
            pass_line = ' ' * (opener_ci + 4) + 'pass\n'
            lines.insert(opener_idx + 1, pass_line)
    return lines


def fix_unindent_mismatch(lines, err_lineno):
    """
    Fix 'unindent does not match any outer indentation level'.
    """
    idx = err_lineno - 1
    l = lines[idx]
    if not l.strip():
        return lines
    ci = ind(l)
    stripped = l.strip()

    # Find nearest ancestor indent level that this could belong to
    # Walk back to find an enclosing block that ends at ci-4 or ci-8
    for offset in [4, 8, 12]:
        target = ci - offset
        if target < 0:
            continue
        # Check if there's a line at target ci before this
        for k in range(idx - 1, max(0, idx - 50), -1):
            prev = lines[k]
            if not prev.strip():
                continue
            pci = ind(prev)
            if pci == target:
                # Re-indent this line to match
                lines[idx] = ' ' * target + stripped + '\n'
                return lines
            if pci < target:
                break

    # Just normalize to 4sp if we can't figure it out
    if not re.match(r'^if page == ', l):
        lines[idx] = '    ' + stripped + '\n'
    return lines


path = 'dashboard_fixed.py'
lines = read_lines(path)

for iteration in range(1, MAX_ITER + 1):
    write_lines(path, lines)
    err_lineno, kind = compile_check(path)

    if err_lineno is None:
        print(f'✅ Clean after {iteration-1} fixes!')
        break

    print(f'[{iteration}] {kind} at line {err_lineno}: {lines[err_lineno-1].rstrip()!r}')

    if kind == 'SyntaxError':
        lines = fix_try_mismatch(lines, err_lineno)
    elif kind == 'IndentationError':
        err_msg = ''
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            err_msg = str(e)

        if 'expected an indented block' in err_msg:
            lines = fix_empty_block(lines, err_lineno)
        elif 'unindent does not match' in err_msg:
            lines = fix_unindent_mismatch(lines, err_lineno)
        elif 'unexpected indent' in err_msg:
            # The line is over-indented — de-dent it
            idx = err_lineno - 1
            stripped = lines[idx].strip()
            ci = ind(lines[idx])
            # Find what indentation the previous block opener expects
            for k in range(idx - 1, max(0, idx - 20), -1):
                prev = lines[k]
                if not prev.strip():
                    continue
                pci = ind(prev)
                ps = prev.strip()
                if ps.endswith(':'):
                    # This line should be pci + 4
                    lines[idx] = ' ' * (pci + 4) + stripped + '\n'
                    break
                elif pci < ci:
                    # Match the previous line's indent
                    lines[idx] = ' ' * pci + stripped + '\n'
                    break
            else:
                lines[idx] = '    ' + stripped + '\n'
        else:
            # Generic: try the try-mismatch fixer
            lines = fix_try_mismatch(lines, err_lineno)

    write_lines(path, lines)

else:
    print(f'❌ Still has errors after {MAX_ITER} iterations. Last error at line {err_lineno}.')

write_lines(path, lines)
