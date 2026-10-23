"""Negative controls for the full-install verifier (no external downloads)."""
from __future__ import annotations

import importlib.util
import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "full_install_verifier", ROOT / "scripts" / "verify-full-install.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _fake_installed_tree(home: Path) -> None:
    for agent in (".claude", ".gemini", ".codex"):
        base = home / agent
        (base / "rules").mkdir(parents=True)
        for name in MODULE.RULE_FILES:
            (base / "rules" / name).write_text(
                f"PROJECTINDEX_ROOT: {home / 'code' / 'ProjectIndex'}\n",
                encoding="utf-8",
            )
        for name in MODULE.CONTEXT_FILES:
            (base / name).write_text("pointer\n", encoding="utf-8")
    for agent in (".claude", ".gemini"):
        p = home / agent / "memory" / "MEMORY.md"
        p.parent.mkdir(parents=True)
        p.write_text("memory\n", encoding="utf-8")
    hook = home / "code" / "my-first-repo" / ".git" / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\nsentinel scan --repo .\n", encoding="utf-8")
    key = home / ".config" / "e156" / "truthcert-hmac-key"
    key.parent.mkdir(parents=True)
    key.write_text("a" * 64 + "\n", encoding="utf-8")
    key.chmod(0o600)
    pi = home / "code" / "ProjectIndex"
    for rel in ("INDEX.md", "reconcile_counts.py",
                "agent-records/restart-manifest.json"):
        target = pi / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("sample\n", encoding="utf-8")
    bridge = home / "code" / "rct-extractor-v2" / "scripts" / "build_metakit_config.py"
    bridge.parent.mkdir(parents=True)
    bridge.write_text("sample\n", encoding="utf-8")


def _failures(home: Path) -> set[str]:
    return {name for name, verdict, _ in MODULE.verify(home, run_canaries=False)
            if verdict == "FAIL"}


def test_fresh_empty_home_is_refused(tmp_path):
    failures = _failures(tmp_path)
    assert "Sentinel hook installed" in failures
    assert "TruthCert key format" in failures
    assert "RCT extractor bridge installed" in failures


def test_complete_synthetic_artifacts_pass_static_contract(tmp_path):
    _fake_installed_tree(tmp_path)
    assert _failures(tmp_path) == set()


def test_missing_extractor_refuses_even_with_other_layers(tmp_path):
    _fake_installed_tree(tmp_path)
    bridge = tmp_path / "code" / "rct-extractor-v2" / "scripts" / "build_metakit_config.py"
    bridge.unlink()
    assert "RCT extractor bridge installed" in _failures(tmp_path)


def test_placeholder_truthcert_key_refuses(tmp_path):
    _fake_installed_tree(tmp_path)
    key = tmp_path / ".config" / "e156" / "truthcert-hmac-key"
    key.write_text("please-set-real-key\n", encoding="utf-8")
    assert "TruthCert key format" in _failures(tmp_path)


def test_unrendered_projectindex_binding_refuses(tmp_path):
    _fake_installed_tree(tmp_path)
    rules = tmp_path / ".claude" / "rules" / "rules.md"
    rules.write_text("{{PROJECTINDEX_ROOT}}\n", encoding="utf-8")
    assert ".claude ProjectIndex binding" in _failures(tmp_path)


def test_non_sentinel_pre_push_hook_refuses(tmp_path):
    _fake_installed_tree(tmp_path)
    hook = tmp_path / "code" / "my-first-repo" / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    assert "Sentinel hook installed" in _failures(tmp_path)


def test_insecure_key_permissions_refuse_on_posix(tmp_path):
    _fake_installed_tree(tmp_path)
    key = tmp_path / ".config" / "e156" / "truthcert-hmac-key"
    key.chmod(0o644)
    if os.name == "posix":
        assert "TruthCert key permissions" in _failures(tmp_path)
