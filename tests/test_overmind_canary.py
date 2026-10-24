"""Network-free, executable installer canary regression tests.

These use a synthetic Overmind executable as an *injected failure fixture*,
not a full pinned Sentinel/Overmind/TruthCert/E156/Meta-Harness canary.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-overmind.sh"


def _run_installer(tmp_path: Path, *, exit_code: int, lines: int) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_overmind = fake_bin / "overmind"
    fake_overmind.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" != meta-verify ]; then exit 88; fi\n"
        "n=0\n"
        "while [ \"$n\" -lt \"$MOCK_LINES\" ]; do\n"
        "  n=$((n + 1))\n"
        "  printf 'fixture result %s\\n' \"$n\"\n"
        "done\n"
        "exit \"$MOCK_EXIT\"\n",
        encoding="utf-8",
    )
    fake_overmind.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({
        "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
        "HOME": str(home),
        "MOCK_EXIT": str(exit_code),
        "MOCK_LINES": str(lines),
    })
    return subprocess.run(
        ["bash", str(INSTALLER), "--skip-pip-install", "--hmac-key", "a" * 64],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


@pytest.mark.parametrize(("exit_code", "lines"), [(1, 0), (23, 8), (42, 2000)])
def test_failed_meta_verify_cannot_report_installer_ready(
    tmp_path: Path, exit_code: int, lines: int
) -> None:
    result = _run_installer(tmp_path, exit_code=exit_code, lines=lines)
    assert result.returncode == exit_code
    assert f"ERROR: overmind meta-verify failed (exit {exit_code})" in result.stderr
    assert "Overmind + TruthCert ready. Typical use:" not in result.stdout
    if lines:
        assert "fixture result 1" in result.stdout


def test_successful_verbose_canary_has_no_false_sigpipe_failure(tmp_path: Path) -> None:
    result = _run_installer(tmp_path, exit_code=0, lines=2000)
    assert result.returncode == 0, result.stderr
    assert "Overmind + TruthCert ready. Typical use:" in result.stdout
    assert "  fixture result 1\n" in result.stdout
    assert "  fixture result 5\n" in result.stdout
    assert "  fixture result 6\n" not in result.stdout
    assert "WARNING" not in result.stderr
    assert "ERROR: overmind meta-verify" not in result.stderr
