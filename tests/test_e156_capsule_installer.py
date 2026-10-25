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


def run_installer(tmp_path, chartkit, *, sample=True, without_python=False, stale_svg=False,
                  target_name="capsules", preexisting_rc=False):
    target = tmp_path / target_name
    target.mkdir()
    (target / "chartkit.py").write_text(chartkit, encoding="utf-8")
    if stale_svg:
        (target / ".chartkit_check.svg").write_bytes(b"<svg/>")
    if sample:
        (target / "sample.capsule.json").write_text("{}", encoding="utf-8")
    home = tmp_path / "isolated-home"
    home.mkdir()
    if preexisting_rc:
        for rc in (".bashrc", ".zshrc"):
            (home / rc).write_text("# existing user settings\n", encoding="utf-8")
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

@pytest.mark.parametrize("target_name", [
    "capsules$(touch injected_substitution)",
    "capsules`touch injected_backtick`",
    "capsules with spaces '$HOME' and a dollar $USER",
])
def test_persisted_path_is_literal_and_cannot_execute_rc_commands(tmp_path, target_name):
    # A legitimate local folder name must never become shell code in .bashrc
    # or .zshrc. Exercise the shipped installer, then reload both files in Bash.
    # This is a structural shell-quoting test, not a full-system canary.
    program = (
        "from pathlib import Path\\nimport sys\\n"
        "Path(sys.argv[1]).read_bytes()\\n"
        "Path(sys.argv[-1]).write_bytes(b'<svg/>')\\n"
    )
    result, home = run_installer(
        tmp_path, program, target_name=target_name, preexisting_rc=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "chartkit OK" in result.stdout
    target = str(tmp_path / target_name)
    for rc in (".bashrc", ".zshrc"):
        contents = (home / rc).read_text(encoding="utf-8")
        assert "# existing user settings" in contents
        assert "export E156_CAPSULES_PATH=" in contents
        reload = subprocess.run(
            [bash_executable(), "-c",
             f'source "$HOME/{rc}"; printf "%s" "$E156_CAPSULES_PATH"'],
            cwd=tmp_path, env=dict(os.environ, HOME=str(home)),
            text=True, capture_output=True, timeout=15,
        )
        assert reload.returncode == 0, reload.stderr
        assert reload.stdout == target
    assert not (tmp_path / "injected_substitution").exists()
    assert not (tmp_path / "injected_backtick").exists()
