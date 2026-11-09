"""Sentinel v1.0.0 exact source-ref integrity and negative failure injection.

Offline fixture and source-helper checks; not a full installation, signature
verification, real Git pre-push test or full five-component ecosystem canary.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIN = "5808f2bdc024506fa3d49a367c88b42b15fdf164"


def updater():
    spec = importlib.util.spec_from_file_location(
        "refresh_pins_test", ROOT / "scripts" / "refresh-ecosystem-pins.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_bash_and_windows_installer_defaults_are_exact_commit():
    source_bash = (ROOT / "scripts" / "install-sentinel.sh").read_text(encoding="utf-8")
    source_ps = (ROOT / "scripts" / "install-sentinel.ps1").read_text(encoding="utf-8")
    assert re.findall(r'^SENTINEL_DEFAULT_REF="([^"]+)"$', source_bash, re.M) == [PIN]
    assert re.findall(r"""(?m)^\$script:SentinelDefaultRef = '([^']+)'$""", source_ps) == [PIN]


def test_real_bash_runtime_uses_commit_not_movable_tag():
    proc = subprocess.run(
        ["bash", "-c",
         "unset SENTINEL_REF; source scripts/install-sentinel.sh --import; sentinel_default_source"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == "git+https://github.com/mahmood726-cyber/Sentinel.git@" + PIN


@pytest.mark.parametrize("unsafe_ref", [
    "main", "master", "HEAD", "latest", "v1.0.0", "f" * 39,
    "f" * 41, "F" * 40, "deadbeef", "refs/heads/main",
])
def test_bash_rejects_mutable_or_noncanonical_override(unsafe_ref):
    proc = subprocess.run(
        ["bash", "-c", "source scripts/install-sentinel.sh --import; sentinel_default_source"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, "SENTINEL_REF": unsafe_ref},
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "40-character commit SHA" in proc.stderr
    assert "git+https" not in proc.stdout


def test_bash_accepts_explicit_exact_sha_override():
    requested = "f" * 40
    proc = subprocess.run(
        ["bash", "-c", "source scripts/install-sentinel.sh --import; sentinel_default_source"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, "SENTINEL_REF": requested},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == "git+https://github.com/mahmood726-cyber/Sentinel.git@" + requested


def test_mutable_override_preflight_runs_before_existing_cli_check():
    bash_source = (ROOT / "scripts/install-sentinel.sh").read_text(encoding="utf-8")
    ps_source = (ROOT / "scripts/install-sentinel.ps1").read_text(encoding="utf-8")
    assert bash_source.index("sentinel_default_source >/dev/null || exit 1") < bash_source.index("if test_sentinel_installed; then")
    assert ps_source.index("try { $null = Get-SentinelDefaultSource }") < ps_source.index("if (Test-SentinelInstalled) {")


def test_frozen_release_never_queries_mutable_remote_head(monkeypatch):
    module = updater()
    monkeypatch.setattr(module, "remote_head",
                        lambda repo: pytest.fail("frozen pin may not query HEAD"))
    layer = next(x for x in module.LAYERS if x["name"] == "sentinel")
    result = module.process_layer(layer, apply=True, root=ROOT)
    assert result["status"] == "skip", result
    assert PIN[:12] in result["detail"]


@pytest.mark.parametrize("rel,changed_ref", [
    ("scripts/install-sentinel.sh", "v1.0.0"),
    ("scripts/install-sentinel.ps1", "main"),
    ("scripts/install-sentinel.sh", "0" * 40),
    ("scripts/install-sentinel.ps1", "f" * 40),
])
def test_unsafe_or_divergent_pin_refuses_apply_without_network(
    tmp_path, monkeypatch, rel, changed_ref,
):
    module = updater()
    layer = next(x for x in module.LAYERS if x["name"] == "sentinel")
    for path in layer["files"]:
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / path).read_bytes())
    candidate = tmp_path / rel
    content = candidate.read_text(encoding="utf-8")
    old = (f'SENTINEL_DEFAULT_REF="{PIN}"' if rel.endswith(".sh")
           else f"$script:SentinelDefaultRef = '{PIN}'")
    new = (f'SENTINEL_DEFAULT_REF="{changed_ref}"' if rel.endswith(".sh")
           else f"$script:SentinelDefaultRef = '{changed_ref}'")
    assert old in content
    candidate.write_text(content.replace(old, new, 1), encoding="utf-8")
    monkeypatch.setattr(module, "remote_head",
                        lambda repo: pytest.fail("unsafe pin may not query HEAD"))
    result = module.process_layer(layer, apply=True, root=tmp_path)
    assert result["status"] == "error", result
    assert rel in result["detail"]
    assert new in candidate.read_text(encoding="utf-8")


def test_missing_windows_mirror_refuses_apply_without_network(tmp_path, monkeypatch):
    module = updater()
    layer = next(x for x in module.LAYERS if x["name"] == "sentinel")
    shell = tmp_path / layer["files"][0]
    shell.parent.mkdir(parents=True)
    shell.write_bytes((ROOT / layer["files"][0]).read_bytes())
    monkeypatch.setattr(module, "remote_head",
                        lambda repo: pytest.fail("missing pin may not query HEAD"))
    result = module.process_layer(layer, apply=True, root=tmp_path)
    assert result["status"] == "error", result
    assert "mirror missing" in result["detail"]
