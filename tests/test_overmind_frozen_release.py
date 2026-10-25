"""Frozen Overmind v1.0.0 commit identity: real installer + negative controls.

Fixture mutation tests verify the updater refuses tag drift, not that a live
Overmind/TruthCert install or signature verification was performed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIN = "d3d2de5f84d852f27d64d1686f1e105e190ac375"
URL = "git+https://github.com/mahmood726-cyber/overmind.git@"


def load_updater():
    spec = importlib.util.spec_from_file_location(
        "refresh_ecosystem_pins", ROOT / "scripts" / "refresh-ecosystem-pins.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def source_pin(path: Path, pattern: str) -> str:
    matches = re.findall(pattern, path.read_text(encoding="utf-8"))
    assert len(matches) == 1, f"missing/ambiguous frozen release declaration in {path.name}"
    return matches[0]


def test_both_real_installer_defaults_are_the_reviewed_commit():
    assert source_pin(
        ROOT / "scripts" / "install-overmind.sh",
        r'''(?m)^OVERMIND_DEFAULT_REF=["']([^"']+)["']\s*$''',
    ) == PIN
    assert source_pin(
        ROOT / "scripts" / "install-overmind.ps1",
        r'''(?m)^\$script:OvermindDefaultRef\s*=\s*["']([^"']+)["']\s*$''',
    ) == PIN


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash unavailable; Windows Pester checks PowerShell")
def test_bash_runtime_defaults_to_the_exact_commit():
    proc = subprocess.run(
        ["bash", "-c", "unset OVERMIND_REF; source scripts/install-overmind.sh --import; overmind_default_source"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == URL + PIN


def test_refresh_checker_keeps_frozen_release_even_if_head_moves(monkeypatch):
    updater = load_updater()
    def cannot_fetch(_):
        raise AssertionError("a frozen release must not query or track HEAD")
    monkeypatch.setattr(updater, "remote_head", cannot_fetch)
    layer = next(x for x in updater.LAYERS if x["name"] == "overmind")
    result = updater.process_layer(layer, apply=True, root=ROOT)
    assert result["status"] == "skip", result
    assert PIN[:12] in result["detail"]


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        ("scripts/install-overmind.sh", "v1.0.0"),
        ("scripts/install-overmind.ps1", "main"),
        ("scripts/install-overmind.sh", "0" * 40),
        ("scripts/install-overmind.ps1", "f" * 40),
    ],
)
def test_mutated_default_is_refused_not_auto_updated(tmp_path, path, replacement, monkeypatch):
    updater = load_updater()
    layer = next(x for x in updater.LAYERS if x["name"] == "overmind")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for rel in layer["files"]:
        orig = ROOT / rel
        copy = tmp_path / rel
        copy.write_text(orig.read_text(encoding="utf-8"), encoding="utf-8")
    victim = tmp_path / path
    before = victim.read_text(encoding="utf-8")
    assert PIN in before
    victim.write_text(before.replace(PIN, replacement, 1), encoding="utf-8")

    def cannot_fetch(_):
        raise AssertionError("invalid frozen release must not trigger network resolution")
    monkeypatch.setattr(updater, "remote_head", cannot_fetch)
    result = updater.process_layer(layer, apply=True, root=tmp_path)
    assert result["status"] == "error", result
    assert path in result["detail"]
    assert replacement in victim.read_text(encoding="utf-8")
