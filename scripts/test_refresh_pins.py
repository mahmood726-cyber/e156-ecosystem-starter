"""Offline tests for refresh-ecosystem-pins.py (no network)."""
import importlib.util
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parent / "refresh-ecosystem-pins.py"
spec = importlib.util.spec_from_file_location("refresh_ecosystem_pins", _MOD_PATH)
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

OLD = "dd299165a6cc1e637fe5a261e9a2f5f64ae90ff3"
NEW = "1981da94935da371ae2b6d5aeb84cae2b4c3ef8d"


def test_extract_pin_from_sh():
    text = 'EXTRACTOR_DEFAULT_REF="%s"\n' % OLD
    assert rp.extract_pin(text) == OLD


def test_extract_pin_none_for_tag():
    assert rp.extract_pin('DEFAULT_REF="v0.7.0"\n') is None


def test_apply_bump_full_and_short():
    text = f'REF="{OLD}"  # pinned `{OLD[:7]}`'
    out = rp.apply_bump(text, OLD, NEW)
    assert OLD not in out
    assert NEW in out
    assert f"`{NEW[:7]}`" in out
    assert OLD[:7] not in out


def test_apply_bump_idempotent_when_same():
    text = f'REF="{NEW}"'
    assert rp.apply_bump(text, NEW, NEW) == text


def test_layers_cover_seven_pinned_systems():
    names = {l["name"] for l in rp.LAYERS}
    assert names == {"extractor", "sentinel", "overmind", "rapidmeta",
                     "pairwise70", "aact", "aact-kit"}
    for l in rp.LAYERS:
        assert l["files"][0].endswith(".sh")
        assert any(f.endswith(".ps1") for f in l["files"])


def test_process_layer_detects_drift(tmp_path, monkeypatch):
    sh = tmp_path / "scripts" / "install-x.sh"
    ps1 = tmp_path / "scripts" / "install-x.ps1"
    sh.parent.mkdir(parents=True)
    sh.write_text(f'X_DEFAULT_REF="{OLD}"\n', encoding="utf-8")
    ps1.write_text(f"$ref = '{OLD}'\n", encoding="utf-8")
    monkeypatch.setattr(rp, "remote_head", lambda repo: NEW)
    layer = {"name": "x", "repo": "X", "files": ["scripts/install-x.sh", "scripts/install-x.ps1"]}

    # dry-run: detects drift, does not write
    r = rp.process_layer(layer, apply=False, root=tmp_path)
    assert r["status"] == "drift" and r["old"] == OLD and r["new"] == NEW
    assert OLD in sh.read_text(encoding="utf-8")

    # apply: rewrites both files
    r = rp.process_layer(layer, apply=True, root=tmp_path)
    assert r["status"] == "drift"
    assert set(r["changed"]) == {"scripts/install-x.sh", "scripts/install-x.ps1"}
    assert NEW in sh.read_text(encoding="utf-8") and OLD not in sh.read_text(encoding="utf-8")
    assert NEW in ps1.read_text(encoding="utf-8")


def test_process_layer_current_is_noop(tmp_path, monkeypatch):
    sh = tmp_path / "scripts" / "install-y.sh"
    sh.parent.mkdir(parents=True)
    sh.write_text(f'Y_DEFAULT_REF="{NEW}"\n', encoding="utf-8")
    monkeypatch.setattr(rp, "remote_head", lambda repo: NEW)
    layer = {"name": "y", "repo": "Y", "files": ["scripts/install-y.sh"]}
    r = rp.process_layer(layer, apply=True, root=tmp_path)
    assert r["status"] == "current"


def test_preserves_crlf_line_endings(tmp_path, monkeypatch):
    ps1 = tmp_path / "scripts" / "install-z.ps1"
    sh = tmp_path / "scripts" / "install-z.sh"
    sh.parent.mkdir(parents=True)
    sh.write_text(f'Z_DEFAULT_REF="{OLD}"\n', encoding="utf-8")
    ps1.write_bytes(f"$ref = '{OLD}'\r\nWrite-Host ok\r\n".encode("utf-8"))
    monkeypatch.setattr(rp, "remote_head", lambda repo: NEW)
    layer = {"name": "z", "repo": "Z", "files": ["scripts/install-z.sh", "scripts/install-z.ps1"]}
    rp.process_layer(layer, apply=True, root=tmp_path)
    assert b"\r\n" in ps1.read_bytes()  # CRLF preserved
