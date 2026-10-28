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
    # A synthetic BLOCK-mode installed hook fixture; NOT a real Sentinel hook.
    hook.write_text(
        "#!/bin/sh\n"
        "# === SENTINEL PRE-PUSH HOOK (do not edit above this line) ===\n"
        'MODE="${SENTINEL_MODE:-block}"\n'
        "python -m sentinel scan --repo .\n",
        encoding="utf-8",
    )
    hook.chmod(0o700)
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


def test_warn_mode_sentinel_hook_refuses_static_full_canary(tmp_path):
    _fake_installed_tree(tmp_path)
    hook = tmp_path / "code" / "my-first-repo" / ".git" / "hooks" / "pre-push"
    # Pinned Sentinel source specifies that warn mode allows BLOCK pushes.
    hook.write_text(
        hook.read_text(encoding="utf-8").replace(":-block}", ":-warn}"),
        encoding="utf-8",
    )
    assert "Sentinel hook installed" in _failures(tmp_path)


def test_sentinel_keyword_without_authentic_hook_marker_refuses(tmp_path):
    _fake_installed_tree(tmp_path)
    hook = tmp_path / "code" / "my-first-repo" / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho sentinel\nexit 0\n", encoding="utf-8")
    assert "Sentinel hook installed" in _failures(tmp_path)


def test_non_executable_sentinel_hook_refuses_on_posix(tmp_path):
    _fake_installed_tree(tmp_path)
    hook = tmp_path / "code" / "my-first-repo" / ".git" / "hooks" / "pre-push"
    hook.chmod(0o600)
    if os.name == "posix":
        assert "Sentinel hook installed" in _failures(tmp_path)


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


# These are explicitly synthetic failure-injection fixtures, not signed bundles
# or evidence that a real published four-component ecosystem is certified.
import subprocess

import pytest


CERTIFIED_FIXTURE = (
    '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}'
)


@pytest.mark.parametrize(
    "payload",
    [
        '{"passed":false,"verdict":"REJECT","bundle_hash":"0123456789abcdef"}',
        '{"passed":1,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}',
        '{"passed":true,"verdict":"CERTIFIED"}',
        '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"INVALID"}',
        '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef","alarm_written":false}',
        '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef","passed":false}',
        '{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef","noise":NaN}',
        'not JSON',
        CERTIFIED_FIXTURE + '\nwarning: unexpected extra text',
    ],
)
def test_overmind_meta_verify_rejects_ambiguous_or_failed_json(payload):
    assert MODULE._overmind_certified_result(payload) is False


def test_overmind_meta_verify_accepts_unambiguous_fixture_json():
    assert MODULE._overmind_certified_result(CERTIFIED_FIXTURE) is True


@pytest.mark.parametrize(
    ("stdout", "exit_code", "expected"),
    [
        ('{"passed":false,"verdict":"REJECT","bundle_hash":"0123456789abcdef"}', 0, "FAIL"),
        (CERTIFIED_FIXTURE, 1, "FAIL"),
        (CERTIFIED_FIXTURE, 0, "PASS"),
    ],
)
def test_full_canary_requires_overmind_json_verdict_and_process_success(
    tmp_path, monkeypatch, stdout, exit_code, expected
):
    _fake_installed_tree(tmp_path)
    monkeypatch.setattr(MODULE.shutil, "which", lambda _exe: "/isolated-test-bin")
    calls = []

    def simulated_runner(argv, **_kwargs):
        calls.append(tuple(argv))
        if argv[:2] == ["overmind", "meta-verify"]:
            return subprocess.CompletedProcess(argv, exit_code, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", simulated_runner)
    outcomes = MODULE.verify(tmp_path, run_canaries=True)
    results = {name: verdict for name, verdict, _ in outcomes}
    assert ("overmind", "meta-verify") in calls
    assert results["Overmind numerical canary"] == expected
    assert results["Sentinel CLI scan"] == "PASS"
    details = {name: diagnostic for name, _, diagnostic in outcomes}
    assert f"overmind_fixture_verdict_certified={stdout == CERTIFIED_FIXTURE}" in details["Overmind numerical canary"]
    assert "overmind_fixture_verdict_certified" not in details["Sentinel CLI scan"]
