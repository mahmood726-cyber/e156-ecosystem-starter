"""Run the real Bash Overmind installer against an isolated CLI failure fixture.

The mocked Overmind executable is a deliberate test double. These checks
verify installer refusal behavior only; they are NOT a real signed TruthCert
bundle canary or an end-to-end Sentinel/Overmind/E156 integration test.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import subprocess

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install-overmind.sh"
VALID_KEY = "a" * 64


def _invoke(tmp_path: Path, *args: str, existing: str | None = None):
    home = tmp_path / "home"
    home.mkdir()
    key_path = home / ".config" / "e156" / "truthcert-hmac-key"
    if existing is not None:
        key_path.parent.mkdir(parents=True)
        key_path.write_text(existing + "\n", encoding="ascii")
        key_path.chmod(0o600)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "overmind-invoked"
    fake_overmind = fake_bin / "overmind"
    fake_overmind.write_text(
        "#!/bin/sh\n"
        'printf "called\\n" >> "$OVERMIND_TEST_MARKER"\n'
        '[ "$1" = "meta-verify" ]\n',
        encoding="ascii",
    )
    fake_overmind.chmod(0o755)
    env = dict(
        os.environ,
        HOME=str(home),
        PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
        OVERMIND_TEST_MARKER=str(marker),
    )
    result = subprocess.run(
        ["bash", str(INSTALLER), "--skip-pip-install", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result, key_path, marker


@pytest.mark.parametrize("bad_key", [
    "", "short", "0" * 63, "0" * 65, "g" * 64, "a" * 32 + " " + "b" * 31,
    "0" * 32 + "\n" + "1" * 31,
])
def test_bad_explicit_key_refused_without_creating_secret_or_running_canary(tmp_path, bad_key):
    result, key_path, marker = _invoke(tmp_path, "--hmac-key", bad_key)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "REFUSED" in result.stderr
    assert not key_path.exists()
    assert not marker.exists()
    assert "ready" not in result.stdout


@pytest.mark.parametrize("bad_key", ["short", "g" * 64, "0" * 63])
def test_bad_existing_key_refused_without_implicit_rotation(tmp_path, bad_key):
    result, key_path, marker = _invoke(tmp_path, existing=bad_key)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "REFUSED" in result.stderr
    assert key_path.read_text(encoding="ascii") == bad_key + "\n"
    assert not marker.exists()


def test_invalid_explicit_rotation_preserves_previous_valid_key(tmp_path):
    result, key_path, marker = _invoke(tmp_path, "--hmac-key", "bad", existing=VALID_KEY)
    assert result.returncode != 0
    assert key_path.read_text(encoding="ascii").strip() == VALID_KEY
    assert not marker.exists()


def test_missing_key_option_argument_is_refused(tmp_path):
    result, key_path, marker = _invoke(tmp_path, "--hmac-key")
    assert result.returncode != 0
    assert "REFUSED" in result.stderr
    assert not key_path.exists()
    assert not marker.exists()


def test_valid_explicit_key_is_saved_privately_and_canary_runs(tmp_path):
    result, key_path, marker = _invoke(tmp_path, "--hmac-key", VALID_KEY)
    assert result.returncode == 0, result.stdout + result.stderr
    assert key_path.read_text(encoding="ascii").strip() == VALID_KEY
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    assert marker.read_text(encoding="ascii") == "called\n"


def test_valid_existing_key_is_reused_without_rotation(tmp_path):
    result, key_path, marker = _invoke(tmp_path, existing=VALID_KEY)
    assert result.returncode == 0, result.stdout + result.stderr
    assert key_path.read_text(encoding="ascii") == VALID_KEY + "\n"
    assert marker.exists()


def test_generated_default_key_has_32_byte_hex_shape(tmp_path):
    result, key_path, marker = _invoke(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.fullmatch(r"[0-9a-f]{64}", key_path.read_text(encoding="ascii").strip())
    assert marker.exists()
