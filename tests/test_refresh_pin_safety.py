"""Offline negative tests: an installer pin cannot be inferred from incidental SHA text.

The legacy scripts/test_refresh_pins.py is outside the CI pytest tests/ tree.
These tests exercise the real updater module in the CI-discovered directory.
No network calls, installs, or user files are involved.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "refresh-ecosystem-pins.py"
spec = importlib.util.spec_from_file_location("refresh_ecosystem_pins", MODULE)
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

OLD = "a" * 40
NEW = "b" * 40


def test_actual_quoted_pin_is_read():
    assert rp.extract_pin(f'EXTRACTOR_DEFAULT_REF="{OLD}"\n') == OLD
    assert rp.extract_pin(f"EXTRACTOR_DEFAULT_REF='{OLD}'\n") == OLD


def test_actual_unquoted_pin_is_read():
    assert rp.extract_pin(f"EXTRACTOR_DEFAULT_REF={OLD}  # deliberate pin\n") == OLD


def test_tag_with_trailing_old_sha_comment_is_not_a_pin():
    src = f'SENTINEL_DEFAULT_REF="v1.0.0" # previously {OLD}\n'
    assert rp.extract_pin(src) is None


def test_comment_containing_default_ref_assignment_is_not_a_pin():
    src = f'# EXTRACTOR_DEFAULT_REF="{OLD}"\nEXTRACTOR_DEFAULT_REF="v1.0.0"\n'
    assert rp.extract_pin(src) is None


def test_first_incidental_sha_cannot_override_actual_pin():
    src = f'# migration note {OLD}\nOVERMIND_DEFAULT_REF="{NEW}"\n'
    assert rp.extract_pin(src) == NEW


def test_printed_example_assignment_does_not_become_a_pin():
    src = f'echo "SENTINEL_DEFAULT_REF={OLD}"\nSENTINEL_DEFAULT_REF="v1.0.0"\n'
    assert rp.extract_pin(src) is None


def test_tag_pinned_installer_skips_remote_updates_even_with_historical_sha(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    path = scripts / "install-sentinel.sh"
    src = f'SENTINEL_DEFAULT_REF="v1.0.0" # formerly {OLD}\n'
    path.write_text(src, encoding="utf-8")

    def forbidden_remote(*args, **kwargs):
        raise AssertionError("tag-pinned installer must not query or overwrite remote HEAD")

    monkeypatch.setattr(rp, "remote_head", forbidden_remote)
    result = rp.process_layer(
        {"name": "sentinel", "repo": "Sentinel", "files": ["scripts/install-sentinel.sh"]},
        apply=True,
        root=tmp_path,
    )
    assert result["status"] == "skip"
    assert path.read_text(encoding="utf-8") == src
