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
Path(sys.argv[-1]).write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect/><line/></svg>')
'''
CHARTLESS_SVG = '''from pathlib import Path
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


@pytest.mark.parametrize("program", [EXIT_FAILURE, EXIT_ZERO_WITHOUT_SVG, NON_SVG, CHARTLESS_SVG],
                         ids=["nonzero-exit", "success-with-no-file", "success-with-non-svg", "chartless-svg"])
def test_invalid_render_never_claims_ready_or_persists_path(tmp_path: Path, program: str):
    proc, home, target = run_isolated(tmp_path, program)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "REFUSED: chart-kit render canary failed" in proc.stderr
    assert "chartkit OK" not in proc.stdout
    assert "e156-capsules installed at" not in proc.stdout
    assert not (home / ".bashrc").exists()
    assert not list(target.glob(".chartkit_check.*"))


def test_missing_python_is_refusal_not_silent_success(tmp_path: Path):
    proc, home, target = run_isolated(tmp_path, VALID_SVG, missing_python=True)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "Python is required" in proc.stderr
    assert "e156-capsules installed at" not in proc.stdout
    assert "chartkit OK" not in proc.stdout
    assert not (home / ".bashrc").exists()
    assert not list(target.glob(".chartkit_check.*"))


def test_valid_svg_render_succeeds_then_persists_path(tmp_path: Path):
    proc, home, target = run_isolated(tmp_path, VALID_SVG)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "chartkit OK" in proc.stdout
    assert f"e156-capsules installed at {target}" in proc.stdout
    assert str(target) in (home / ".bashrc").read_text(encoding="utf-8")
    assert not list(target.glob(".chartkit_check.*"))

def test_actual_bundled_chartkit_sample_renders_end_to_end(tmp_path: Path):
    """Execute the actual bundled installer and chartkit, not a fake renderer.

    The shipped example data are illustrative, NOT independently verified clinical effects.
    """
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "installed-capsules"
    proc = subprocess.run(
        ["/usr/bin/bash", str(SCRIPT), "--target", str(target)],
        env={**os.environ, "HOME": str(home)},
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "chartkit OK" in proc.stdout
    assert (target / "chartkit.py").read_bytes() == (
        ROOT / "templates" / "e156-capsule" / "chartkit.py"
    ).read_bytes()
    assert (target / "sample.capsule.json").is_file()
    assert str(target) in (home / ".bashrc").read_text(encoding="utf-8")
    assert not list(target.glob(".chartkit_check.*"))


def test_copy_refuses_nonempty_destination_and_preserves_user_file(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "capsules"
    target.mkdir()
    owned = target / "chartkit.py"
    owned.write_bytes(b"human-owned chartkit; never overwrite")
    proc = subprocess.run(
        ["/usr/bin/bash", str(SCRIPT), "--target", str(target)],
        env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "REFUSED: destination" in proc.stderr
    assert owned.read_bytes() == b"human-owned chartkit; never overwrite"
    assert [p.name for p in target.iterdir()] == ["chartkit.py"]
    assert not (home / ".bashrc").exists()


def test_copy_refuses_symlink_destination_without_touching_target(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    owned = outside / "chartkit.py"
    owned.write_bytes(b"another directory's private chartkit")
    destination = tmp_path / "capsules"
    destination.symlink_to(outside, target_is_directory=True)
    proc = subprocess.run(
        ["/usr/bin/bash", str(SCRIPT), "--target", str(destination)],
        env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "REFUSED: destination" in proc.stderr
    assert owned.read_bytes() == b"another directory's private chartkit"
    assert not (home / ".bashrc").exists()


def test_copy_accepts_existing_empty_directory_using_bundled_chartkit(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "empty-capsules"
    target.mkdir()
    proc = subprocess.run(
        ["/usr/bin/bash", str(SCRIPT), "--target", str(target)],
        env={**os.environ, "HOME": str(home)},
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "chartkit OK" in proc.stdout
    assert (target / "chartkit.py").is_file()
    assert str(target) in (home / ".bashrc").read_text(encoding="utf-8")
