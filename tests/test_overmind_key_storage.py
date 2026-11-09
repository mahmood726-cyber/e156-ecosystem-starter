"""Offline tests of the actual TruthCert key-storage path in the Bash installer.

These use isolated HOME directories and, for the import/read case, a synthetic
CLI stub. They do NOT prove signed-bundle verification or a full ecosystem
canary; they do exercise the shipped secret-store and refusal entrypoints.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install-overmind.sh"
KEY = "a" * 64
REPLACEMENT = "b" * 64


def _store(home: Path, key: str = KEY) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, HOME=str(home), TEST_KEY=key, INSTALLER=str(INSTALLER))
    return subprocess.run(
        ["bash", "-c", 'umask 022; source "$INSTALLER" --import; store_truthcert_hmac_key "$TEST_KEY"'],
        env=env, capture_output=True, text=True, timeout=15, check=False,
    )


def _key_path(home: Path) -> Path:
    return home / ".config" / "e156" / "truthcert-hmac-key"


def test_new_hmac_key_is_private_despite_permissive_parent_umask(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = _store(home)
    key = _key_path(home)
    assert result.returncode == 0, result.stderr
    assert result.stdout == str(key)
    assert key.read_text(encoding="ascii") == KEY + "\n"
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert stat.S_IMODE(key.parent.stat().st_mode) == 0o700
    assert list(key.parent.glob(".truthcert-hmac-key.*")) == []


def test_key_rotation_is_atomic_and_recovers_private_permissions(tmp_path: Path) -> None:
    home = tmp_path / "home"
    key = _key_path(home)
    key.parent.mkdir(parents=True)
    key.write_text(KEY + "\n", encoding="ascii")
    key.chmod(0o644)
    result = _store(home, REPLACEMENT)
    assert result.returncode == 0, result.stderr
    assert key.read_text(encoding="ascii") == REPLACEMENT + "\n"
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert not list(key.parent.glob(".truthcert-hmac-key.*"))


def test_key_file_symlink_is_refused_without_overwriting_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    key = _key_path(home)
    key.parent.mkdir(parents=True)
    external = tmp_path / "outside.txt"
    external.write_text("untouched\n", encoding="ascii")
    key.symlink_to(external)
    result = _store(home)
    assert result.returncode != 0
    assert "REFUSED" in result.stderr
    assert key.is_symlink()
    assert external.read_text(encoding="ascii") == "untouched\n"
    assert not list(key.parent.glob(".truthcert-hmac-key.*"))


@pytest.mark.parametrize("link_component", [".config", "e156"])
def test_config_directory_symlink_is_refused(tmp_path: Path, link_component: str) -> None:
    home = tmp_path / "home"
    home.mkdir()
    external = tmp_path / "outside"
    external.mkdir()
    if link_component == ".config":
        (home / ".config").symlink_to(external, target_is_directory=True)
    else:
        (home / ".config").mkdir()
        (home / ".config" / "e156").symlink_to(external, target_is_directory=True)
    result = _store(home)
    assert result.returncode != 0
    assert "REFUSED" in result.stderr
    assert list(external.iterdir()) == []


def test_existing_symlink_refused_before_installer_canary_or_success(tmp_path: Path) -> None:
    home = tmp_path / "home"
    key = _key_path(home)
    key.parent.mkdir(parents=True)
    external = tmp_path / "external-valid-key.txt"
    external.write_text(KEY + "\n", encoding="ascii")
    key.symlink_to(external)
    binary = tmp_path / "bin"
    binary.mkdir()
    marker = tmp_path / "canary-called"
    fake_cli = binary / "overmind"
    fake_cli.write_text(
        '#!/bin/sh\nprintf "%s\\n" called >> "$CANARY_MARKER"\nexit 0\n',
        encoding="ascii",
    )
    fake_cli.chmod(0o755)
    env = dict(
        os.environ,
        HOME=str(home),
        PATH=str(binary) + os.pathsep + os.environ["PATH"],
        CANARY_MARKER=str(marker),
    )
    result = subprocess.run(
        ["bash", str(INSTALLER), "--skip-pip-install"],
        env=env, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode != 0
    assert "REFUSED" in result.stderr
    assert not marker.exists()
    assert "Overmind + TruthCert ready" not in result.stdout
    assert external.read_text(encoding="ascii") == KEY + "\n"
