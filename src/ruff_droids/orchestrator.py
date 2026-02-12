"""Orchestrator: run ruff, build work units, dispatch to Factory droids."""

import ast
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

MAX_RETRIES = 5
BACKOFF_BASE = 1.0  # seconds


def run_ruff(target_dir: str) -> list[dict]:
    """Run ruff --fix, then collect remaining violations as JSON."""
    # First pass: auto-fix what ruff can handle on its own
    subprocess.run(
        ["uvx", "ruff", "check", "--fix", target_dir],
        check=False,  # non-zero exit is expected when violations remain
    )

    # Second pass: report whatever is left
    res = subprocess.run(
        ["uvx", "ruff", "check", "--output-format", "json", target_dir],
        capture_output=True,
        text=True,
        check=False,
    )

    if not res.stdout.strip():
        return []
    return json.loads(res.stdout)


def _build_scope_map(filepath: str) -> list[tuple[range, str]]:
    """Parse a Python file's AST and return a list of (line_range, scope_name) tuples.

    Scopes are functions, methods, and classes. Nested scopes use dotted names
    (e.g. "MyClass.my_method"). The list is sorted innermost-first so that a
    violation on a line inside a method matches the method, not the enclosing class.
    """
    try:
        source = Path(filepath).read_text()
        tree = ast.parse(source, filename=filepath)
    except (OSError, SyntaxError):
        return []

    scopes: list[tuple[range, str]] = []

    def _walk(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}.{child.name}" if prefix else child.name
                end = child.end_lineno if child.end_lineno is not None else child.lineno
                scopes.append((range(child.lineno, end + 1), name))
                _walk(child, name)
            else:
                _walk(child, prefix)

    _walk(tree)

    # Sort by range size ascending so innermost scopes match first
    scopes.sort(key=lambda s: len(s[0]))
    return scopes


def _scope_for_line(scopes: list[tuple[range, str]], line: int) -> str:
    """Return the narrowest scope name containing `line`, or '<module>' for top-level."""
    for line_range, name in scopes:
        if line in line_range:
            return name
    return "<module>"


def build_work_units(violations: list[dict]) -> list[dict]:
    """Build per-violation work units, merging violations that share a scope to avoid conflicts.

    Two violations in the same file and same function/method/class are given to
    one droid.  Violations in different scopes (even in the same file) become
    separate work units so they can run in parallel without conflicts.
    """
    # Group violations by file first
    by_file: dict[str, list[dict]] = {}
    for v in violations:
        by_file.setdefault(v.get("filename", ""), []).append(v)

    work_units: list[dict] = []

    for filepath, file_violations in by_file.items():
        scope_map = _build_scope_map(filepath)

        # Sub-group by scope within the file
        by_scope: dict[str, list[dict]] = {}
        for v in file_violations:
            line = v.get("location", {}).get("row", 0)
            scope = _scope_for_line(scope_map, line)
            by_scope.setdefault(scope, []).append(v)

        for scope, scope_violations in by_scope.items():
            codes = ", ".join(sorted({v.get("code", "?") for v in scope_violations}))
            work_units.append({
                "file": filepath,
                "scope": scope,
                "violations": scope_violations,
                "description": f"Fix {len(scope_violations)} violation(s) [{codes}] in {filepath}:{scope}",
            })

    return work_units


def _exec_droid_unit(target_dir: str, unit: dict, unit_index: int) -> tuple[int, dict]:
    """Run a single droid exec for one work unit, with exponential backoff on failure."""
    unit_path = Path(target_dir) / f".factory_ruff_unit_{unit_index}.json"
    unit_path.write_text(json.dumps(unit))

    cmd = [
        "droid",
        "exec",
        "--auto",
        "medium",
        "--",
        "python",
        "-m",
        "ruff_droids.worker",
        str(unit_path),
    ]

    for attempt in range(MAX_RETRIES):
        result = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return 0, unit

        delay = BACKOFF_BASE * (2 ** attempt)
        time.sleep(delay)

    return 1, unit


def run_droid_exec(target_dir: str, work_units: list[dict], *, concurrency: int = 4) -> int:
    """Dispatch all work units to droids in parallel with exponential backoff."""
    failed: list[dict] = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_exec_droid_unit, target_dir, unit, i): unit
            for i, unit in enumerate(work_units)
        }
        for future in as_completed(futures):
            returncode, unit = future.result()
            if returncode == 0:
                pass
            else:
                failed.append(unit)

    if failed:
        for _u in failed:
            pass
        return 1
    return 0


def run_lint_fix(target_dir: str, *, concurrency: int = 4) -> int:
    """Top-level flow: ruff auto-fix -> collect remaining violations -> confirm -> droid exec."""
    violations = run_ruff(target_dir)

    if not violations:
        return 0

    work_units = build_work_units(violations)

    for _u in work_units:
        pass

    answer = input("\nWould you like to continue? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        return 1

    return run_droid_exec(target_dir, work_units, concurrency=concurrency)
