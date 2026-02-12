"""Tests that run ruff-droids against test_repo and verify violations are fixed."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TEST_REPO = Path(__file__).resolve().parent.parent / "test_repo"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Copy test_repo into a temp directory so originals stay dirty."""
    dest = tmp_path / "test_repo"
    shutil.copytree(TEST_REPO, dest)
    return dest


def _ruff_violations(target: Path) -> list[dict]:
    """Return current ruff violations as parsed JSON."""
    res = subprocess.run(
        ["uvx", "ruff", "check", "--output-format", "json", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if not res.stdout.strip():
        return []
    return json.loads(res.stdout)


def _violation_codes(violations: list[dict]) -> set[str]:
    return {v["code"] for v in violations}


def _run_ruff_fix(workspace: Path) -> None:
    subprocess.run(
        ["uvx", "ruff", "check", "--fix", str(workspace)],
        capture_output=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# Pre-condition: violations exist before any fix
# ---------------------------------------------------------------------------


def test_precondition_violations_exist(workspace: Path) -> None:
    """Sanity check: the test repo actually has violations before we do anything."""
    violations = _ruff_violations(workspace)
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# did_fix_F401: unused imports removed (safe fix)
# ---------------------------------------------------------------------------


def test_did_fix_F401_unused_imports(workspace: Path) -> None:
    """After ruff --fix, unused imports (F401) should be gone."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "F401" not in codes


# ---------------------------------------------------------------------------
# did_fix_I001: import sorting (safe fix)
# ---------------------------------------------------------------------------


def test_did_fix_I001_import_sorting(workspace: Path) -> None:
    """After ruff --fix, import blocks (I001) should be sorted."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "I001" not in codes


# ---------------------------------------------------------------------------
# did_fix_RET505: unnecessary elif after return (safe fix)
# ---------------------------------------------------------------------------


def test_did_fix_RET505_elif_after_return(workspace: Path) -> None:
    """After ruff --fix, unnecessary elif after return (RET505) should be gone."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "RET505" not in codes


# ---------------------------------------------------------------------------
# Unsafe fixes: these remain after --fix and need droids
# ---------------------------------------------------------------------------


def test_needs_droid_E712_bool_comparison(workspace: Path) -> None:
    """E712 (== True/False) is an unsafe fix — needs a droid."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "E712" in codes


def test_needs_droid_F841_unused_variable(workspace: Path) -> None:
    """F841 (unused variable) is an unsafe fix — needs a droid."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "F841" in codes


def test_needs_droid_T201_print(workspace: Path) -> None:
    """T201 (print found) is an unsafe fix — needs a droid."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "T201" in codes


def test_needs_droid_SIM103_simplify_return(workspace: Path) -> None:
    """SIM103 (return condition directly) is an unsafe fix — needs a droid."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))
    assert "SIM103" in codes


# ---------------------------------------------------------------------------
# Unfixable violations remain (droids needed)
# ---------------------------------------------------------------------------


def test_unfixable_violations_remain(workspace: Path) -> None:
    """After ruff --fix, violations that need droids should still be present."""
    _run_ruff_fix(workspace)
    codes = _violation_codes(_ruff_violations(workspace))

    expected_remaining = {"D100", "D101", "D102", "D103", "ANN001", "E501", "E721"}
    for code in expected_remaining:
        assert code in codes, f"Expected {code} to still be present after auto-fix"


# ---------------------------------------------------------------------------
# Scope grouping: violations in the same method become one work unit
# ---------------------------------------------------------------------------


def test_scope_grouping_merges_same_method(workspace: Path) -> None:
    """Violations in the same scope should be merged into a single work unit."""
    from ruff_droids.orchestrator import build_work_units

    _run_ruff_fix(workspace)
    violations = _ruff_violations(workspace)
    work_units = build_work_units(violations)

    # mixed_issues.py:DataProcessor.validate has multiple violations (E721, D102, etc.)
    # They should all land in one work unit, not separate ones
    validate_units = [u for u in work_units if u["scope"] == "DataProcessor.validate"]
    assert len(validate_units) == 1, f"Expected 1 work unit for validate, got {len(validate_units)}"
    assert len(validate_units[0]["violations"]) > 1, "Expected multiple violations merged into one unit"
