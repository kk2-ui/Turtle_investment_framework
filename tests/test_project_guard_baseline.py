from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "project_guard.py"


def run_guard(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_current_head_inherits_consolidated_baseline() -> None:
    result = run_guard("baseline-check", "HEAD")
    assert result.returncode == 0, result.stderr
    assert "已继承统一基线 eadaae9dedbf" in result.stdout


def test_preconsolidation_branch_is_rejected() -> None:
    result = run_guard("baseline-check", "08c8620")
    assert result.returncode == 2
    assert "未继承要求的基线 eadaae9dedbf" in result.stderr


def test_integrated_ancestor_is_not_a_current_development_baseline() -> None:
    result = run_guard("baseline-check", "a115456")
    assert result.returncode == 2
    assert "未继承要求的基线 eadaae9dedbf" in result.stderr
