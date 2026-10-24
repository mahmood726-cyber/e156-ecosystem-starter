"""Actual Bash E156 capsule installer canary refusals, offline and isolated.

These synthetic chartkit programs are deterministic failure-injection fixtures.
They do NOT constitute a signed Sentinel/Overmind/TruthCert/E156/Meta-Harness canary.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-e156-capsules.sh"

VALID_SVG = '''from pathlib import Path
import sys
Path(sys.argv[-1]).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
'''
NON_SVG = '''from pathlib import Path
import sys
Path(sys.argv[-1]).write_text("<html/>")
'''
EXIT_ZERO_WITHOUT_SVG = "import sys; sys.exit(0)\n"
EXIT_FAILURE = "import sys; sys.exit(17)\n"


def run_isolated(tmp_path: Path, chartkit: str, *, missing_python: bool = False):
    home = tmp_path / "home"
    target = tmp_path / "capsules"
    home.mkdir()
    target.mkdir()
    (target / "chartkit.py").write_text(chartkit, encoding="utf-8")
    (target / "sample.capsule.json").write_text("{}", encoding="utf-8")
    env = {**os.environ, "HOME": str(home)}
    if missing_python:
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()
        env["PATH"] = str(empty_path)
    proc = subprocess.run(
        ["/usr/bin/bash", str(SCRIPT), "--skip-copy", "--target", str(target)],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )
    return proc, home, target


@pytest.mark.parametrize("program", [EXIT_FAILURE, EXIT_ZERO_WITHOUT_SVG, NON_SVG],
                         ids=["nonzero-exit", "success-with-no-file", "success-with-non-svg"])
def test_invalid_render_never_claims_ready_or_persists_path(tmp_path: Path, program: str):
    proc, home, target = run_isolated(tmp_path, program)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "REFUSED: chart-kit render canary failed" in proc.stderr
    assert "chartkit OK" not in proc.stdout
    assert "e156-capsules installed at" not in proc.stdout
    assert not (home / ".bashrc").exists()
    assert not list(target.glob(".chartkit_check.*.svg"))


def test_missing_python_is_refusal_not_silent_success(tmp_path: Path):
    proc, home, target = run_isolated(tmp_path, VALID_SVG, missing_python=True)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "Python is required" in proc.stderr
    assert "e156-capsules installed at" not in proc.stdout
    assert "chartkit OK" not in proc.stdout
    assert not (home / ".bashrc").exists()
    assert not list(target.glob(".chartkit_check.*.svg"))


def test_valid_svg_render_succeeds_then_persists_path(tmp_path: Path):
    proc, home, target = run_isolated(tmp_path, VALID_SVG)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "chartkit OK" in proc.stdout
    assert f"e156-capsules installed at {target}" in proc.stdout
    assert str(target) in (home / ".bashrc").read_text(encoding="utf-8")
    assert not list(target.glob(".chartkit_check.*.svg"))
