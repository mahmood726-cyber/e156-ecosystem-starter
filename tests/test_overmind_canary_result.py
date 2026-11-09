"""Offline negative tests for the Overmind verifier-health installer gate.

Synthetic CLI responses are test fixtures, not real TruthCert signatures,
Sentinel checks or independently executed ecosystem canaries.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "check-overmind-canary.py"
INSTALLER = ROOT / "scripts" / "install-overmind.sh"
GOOD = '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}'
FAILED = '{"passed":false,"verdict":"REJECT","alarm_written":"alarm.json"}'


@pytest.mark.parametrize(
    ("raw", "accepted"),
    [
        (GOOD, True),
        (FAILED, False),
        ('{"passed":true,"verdict":"REJECT","bundle_hash":"0123456789abcdef"}', False),
        ('{"passed":"true","verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}', False),
        ('{"passed":true,"verdict":"CERTIFIED"}', False),
        ('{"passed":true,"verdict":"CERTIFIED","bundle_hash":"not-sha"}', False),
        ('{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef","alarm_written":"present"}', False),
        ('{"passed":false,"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}', False),
        ('{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"} junk', False),
        ('[]', False),
        ('', False),
    ],
)
def test_strict_meta_verify_json_result(raw: str, accepted: bool) -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        input=raw,
        text=True,
        capture_output=True,
        check=False,
    )
    assert (result.returncode == 0) is accepted, result.stderr
    assert ("CERTIFIED local verifier-health fixture" in result.stdout) is accepted


@pytest.mark.parametrize(
    ("payload", "upstream_exit", "accepted"),
    [
        (GOOD, 0, True),
        (FAILED, 0, False),  # Overmind CLI can return 0 despite passed=false.
        (GOOD, 7, False),  # JSON success may not mask the CLI's nonzero exit.
        ('{"passed":"true","verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}', 0, False),
    ],
)
def test_actual_bash_installer_refuses_false_readiness(
    tmp_path: Path, payload: str, upstream_exit: int, accepted: bool
) -> None:
    """Run the actual Bash installer with an isolated fixture CLI, no pip/network."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake_cli = bindir / "overmind"
    fake_cli.write_text(
        '#!/bin/sh\n'
        '[ "$1" = "meta-verify" ] || exit 9\n'
        'printf "%s\\n" "$CANARY_FIXTURE_JSON"\n'
        'exit "$CANARY_FIXTURE_EXIT"\n',
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        PATH=str(bindir) + os.pathsep + env.get("PATH", ""),
        CANARY_FIXTURE_JSON=payload,
        CANARY_FIXTURE_EXIT=str(upstream_exit),
    )
    result = subprocess.run(
        ["bash", str(INSTALLER), "--skip-pip-install", "--hmac-key", "a" * 64],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert (result.returncode == 0) is accepted, (result.stdout, result.stderr)
    assert ("Overmind + TruthCert ready." in result.stdout) is accepted
    if not accepted:
        assert "REFUSED:" in result.stderr
