"""Fail-closed regression for Bash Sentinel pre-push installation.

Exercises the committed Bash installer and disposable real Git repositories.
The fake Sentinel CLI models installer outputs; this is NOT a genuine pinned
Sentinel installation, signed release, or end-to-end ecosystem canary.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install-sentinel.sh"
FAKE_CLI = """#!/usr/bin/env python3
import os
import sys
from pathlib import Path

if len(sys.argv) < 2 or sys.argv[1] != "install-hook":
    sys.exit(21)
target = Path(sys.argv[sys.argv.index("--repo") + 1])
requested = sys.argv[sys.argv.index("--mode") + 1]
fixture = os.environ["SENTINEL_POSTINSTALL_FIXTURE"]
if fixture == "exit-failure":
    sys.exit(42)
if fixture == "no-hook":
    sys.exit(0)

marker = "# === SENTINEL PRE-PUSH HOOK (do not edit above this line) ==="
if fixture == "wrong-marker":
    marker = "# unrelated pre-push hook"
installed_mode = ("warn" if requested == "block" else "block") if fixture == "wrong-mode" else requested
lines = [
    "#!/bin/sh",
    marker,
    'MODE="${SENTINEL_MODE:-' + installed_mode + '}"',
]
if fixture != "no-scanner":
    lines.append('output="$(python -m sentinel scan --repo "$REPO_TOPLEVEL" $SCAN_ARGS 2>&1)"')
lines.append("exit 0")
hook = target / ".git" / "hooks" / "pre-push"
hook.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
hook.chmod(0o644 if fixture == "nonexecutable" else 0o755)
"""


@pytest.mark.parametrize(
    ("fixture", "mode", "should_pass"),
    [
        ("no-hook", "block", False),
        ("wrong-marker", "block", False),
        ("no-scanner", "block", False),
        ("wrong-mode", "block", False),
        ("nonexecutable", "block", False),
        ("exit-failure", "block", False),
        ("valid", "invalid-mode", False),
        ("valid", "block", True),
        ("valid", "warn", True),
    ],
)
def test_sentinel_hook_postinstall_fail_closed(tmp_path: Path, fixture: str, mode: str, should_pass: bool):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_sentinel = bin_dir / "sentinel"
    fake_sentinel.write_text(FAKE_CLI, encoding="utf-8")
    fake_sentinel.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["SENTINEL_POSTINSTALL_FIXTURE"] = fixture
    result = subprocess.run(
        ["bash", str(INSTALLER), "--repo", str(repo), "--mode", mode, "--skip-pip-install"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    output = result.stdout + result.stderr
    if should_pass:
        assert result.returncode == 0, output
        assert "hook installed" in result.stdout
    else:
        assert result.returncode != 0, output
        assert "Sentinel hook installed. It fires on every git push." not in result.stdout


@pytest.mark.parametrize(
    ("extra_args", "expected_mode"),
    [
        ([], "block"),                       # no --mode must BLOCK
        (["--mode", "block"], "block"),
        (["--mode", "warn"], "warn"),         # explicit nonblocking opt-in
        (["--mode", "off"], None),            # unsupported bypass must refuse
    ],
)
def test_wrapper_cli_default_block_and_warn_opt_in(tmp_path: Path, extra_args, expected_mode):
    """Run the real Bash wrapper with a disposable Git repo and synthetic CLI.

    This verifies requested mode and refusal, not real installed Sentinel runtime.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "sentinel"
    executable.write_text(FAKE_CLI, encoding="utf-8")
    executable.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["SENTINEL_POSTINSTALL_FIXTURE"] = "valid"
    result = subprocess.run(
        ["bash", str(INSTALLER), "--repo", str(repo), "--skip-pip-install", *extra_args],
        env=env, capture_output=True, text=True, timeout=20, check=False,
    )
    hook = repo / ".git" / "hooks" / "pre-push"
    if expected_mode is None:
        assert result.returncode != 0, result.stdout + result.stderr
        assert "unsupported Sentinel hook mode" in result.stderr
        assert not hook.exists(), "invalid mode must be rejected before hook writes"
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert hook.is_file() and os.access(hook, os.X_OK)
        assert ("SENTINEL_MODE:-" + expected_mode) in hook.read_text(encoding="utf-8")
