"""End-to-end offline capsule installer fail-closed canaries (synthetic fixtures).

Runs the shipped Bash installer, not a mocked verifier. These do not exercise the
pinned four-component ecosystem or independently validate scientific data.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-e156-capsules.sh"


def bash_executable():
    for candidate in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"):
        if candidate and "system32" not in candidate.lower() and Path(candidate).is_file():
            return candidate
    pytest.fail("Bash unavailable; installer canary must not silently skip")


def run_installer(tmp_path, chartkit, *, sample=True, without_python=False, stale_svg=False):
    target = tmp_path / "capsules"
    target.mkdir()
    (target / "chartkit.py").write_text(chartkit, encoding="utf-8")
    if stale_svg:
        (target / ".chartkit_check.svg").write_bytes(b"<svg/>")
    if sample:
        (target / "sample.capsule.json").write_text("{}", encoding="utf-8")
    home = tmp_path / "isolated-home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    if without_python:
        env["PATH"] = ""
    proc = subprocess.run(
        [bash_executable(), str(SCRIPT), "--target", str(target), "--skip-copy"],
        env=env, text=True, capture_output=True, timeout=30,
    )
    return proc, home


@pytest.mark.parametrize("program", [
    "raise SystemExit(9)\n",
    "pass\n",  # returns zero but produces no SVG
    "from pathlib import Path\nimport sys\nPath(sys.argv[-1]).write_bytes(b'')\n",
    "from pathlib import Path\nimport sys\nPath(sys.argv[-1]).write_bytes(b'NOT SVG')\n",
    "from pathlib import Path\nimport sys\nPath(sys.argv[1]).read_bytes()\nPath(sys.argv[-1]).write_text('<svg/>')\n",
])
def test_installer_refuses_failed_renderer_or_missing_sample(tmp_path, program):
    # The final program would normally work; omit its sample to test failure.
    sample = "read_bytes()" not in program
    result, home = run_installer(tmp_path, program, sample=sample)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "refus" in (result.stdout + result.stderr).lower()
    assert not (home / ".bashrc").exists(), "failed verification must not publish the target"


def test_installer_refuses_missing_python(tmp_path):
    result, home = run_installer(tmp_path, "pass\n", without_python=True)
    assert result.returncode != 0
    assert "Python is required" in result.stderr
    assert not (home / ".bashrc").exists()


def test_installer_refuses_stale_svg_without_clobbering_it(tmp_path):
    # Pre-existing, valid SVG bytes are not evidence this run rendered anything.
    # The actual chartkit process exits zero but writes no output at all.
    result, home = run_installer(tmp_path, "pass\n", stale_svg=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "refus" in (result.stdout + result.stderr).lower()
    assert not (home / ".bashrc").exists()
    target = tmp_path / "capsules"
    assert (target / ".chartkit_check.svg").read_bytes() == b"<svg/>"
    assert sorted(p.name for p in target.glob(".chartkit_check.*")) == [".chartkit_check.svg"]


def test_installer_accepts_fresh_svg_without_deleting_stale_user_file(tmp_path):
    program = (
        "from pathlib import Path\nimport sys\n"
        "Path(sys.argv[1]).read_bytes()\n"
        "Path(sys.argv[-1]).write_bytes(b'<svg/>')\n"
    )
    result, home = run_installer(tmp_path, program, stale_svg=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "chartkit OK" in result.stdout
    assert "E156_CAPSULES_PATH" in (home / ".bashrc").read_text(encoding="utf-8")
    target = tmp_path / "capsules"
    assert (target / ".chartkit_check.svg").read_bytes() == b"<svg/>"
    assert sorted(p.name for p in target.glob(".chartkit_check.*")) == [".chartkit_check.svg"]


def test_installer_accepts_real_svg_artifact(tmp_path):
    program = (
        "from pathlib import Path\nimport sys\n"
        "Path(sys.argv[1]).read_bytes()\n"
        "Path(sys.argv[-1]).write_bytes(b'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\"/>')\n"
    )
    result, home = run_installer(tmp_path, program)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "chartkit OK" in result.stdout
    assert "E156_CAPSULES_PATH" in (home / ".bashrc").read_text(encoding="utf-8")
