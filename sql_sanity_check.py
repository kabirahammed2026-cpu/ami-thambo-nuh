"""Static SQL sanity checks for common placeholder/count errors.

Checks:
1) For SQL literals used in cursor.execute(..., (<literal tuple/list>)), the number of '?'
   placeholders must match the tuple/list length.
2) For SQL literals containing `INSERT INTO ... (cols) VALUES (vals)` with only '?' vals,
   the number of columns must match placeholders.

This script intentionally only validates static/literal patterns and avoids dynamic SQL.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PY_FILES = sorted(Path('.').glob('*.py'))


def _const_str(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _const_str(node.left)
        right = _const_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _seq_len(node: ast.AST):
    if isinstance(node, (ast.Tuple, ast.List)):
        if any(isinstance(elt, ast.Starred) for elt in node.elts):
            return None
        return len(node.elts)
    return None


def check_execute_placeholder_counts(path: Path, source: str):
    tree = ast.parse(source)
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != 'execute':
            continue
        if len(node.args) < 2:
            continue
        sql = _const_str(node.args[0])
        if sql is None:
            continue
        params_len = _seq_len(node.args[1])
        if params_len is None:
            continue
        q_count = sql.count('?')
        if q_count != params_len:
            issues.append(
                f"{path}:{node.lineno} execute placeholder mismatch: {q_count} '?' vs {params_len} params"
            )
    return issues


def check_insert_column_placeholder_counts(path: Path, source: str):
    tree = ast.parse(source)
    issues = []
    pattern = re.compile(
        r"INSERT\s+INTO\s+([a-zA-Z_][\w]*)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)",
        re.IGNORECASE | re.DOTALL,
    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr not in {'execute', 'executescript'}:
            continue
        if not node.args:
            continue
        sql = _const_str(node.args[0])
        if sql is None:
            continue

        for statement in sql.split(';'):
            stmt = statement.strip()
            if not stmt:
                continue
            match = pattern.search(stmt)
            if not match:
                continue
            columns = [c.strip() for c in match.group(2).split(',') if c.strip()]
            values = [v.strip() for v in match.group(3).split(',') if v.strip()]
            if values and all(v == '?' for v in values):
                if len(columns) != len(values):
                    issues.append(
                        f"{path}:{node.lineno} INSERT {match.group(1)} mismatch: {len(columns)} columns vs {len(values)} placeholders"
                    )
    return issues


def main() -> int:
    issues = []
    for py_file in PY_FILES:
        source = py_file.read_text(encoding='utf-8')
        issues.extend(check_execute_placeholder_counts(py_file, source))
        issues.extend(check_insert_column_placeholder_counts(py_file, source))

    if issues:
        print('SQL sanity check failed:')
        for issue in issues:
            print(f' - {issue}')
        return 1

    print('SQL sanity check passed: no static placeholder/count mismatches found.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
