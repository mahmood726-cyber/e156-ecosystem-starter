"""scripts/install-meta-harness.sh: fetch a meta-harness release, verify it against SHA256SUMS, then unpack.

Every test runs the REAL script end to end against a local release directory (META_HARNESS_BASE_URL=file://...),
so no network is needed. The refusals are the point: a fetch step that cannot refuse proves nothing.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-meta-harness.sh"
TAG = "v9.9.9-test"
ASSET = f"meta-harness-{TAG}.zip"


def _bash() -> str:
    # On Windows, prefer Git Bash over the WSL launcher in System32 (which cannot see these paths).
    for cand in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"):
        if cand and "system32" not in cand.lower() and Path(cand).exists():
            return cand
    pytest.fail("no usable bash found (Git Bash on Windows, bash on Linux)")


def _release(d: Path, members: dict[str, bytes], sums_line: str | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    z = d / ASSET
    with zipfile.ZipFile(z, "w") as f:
        for name, data in members.items():
            f.writestr(name, data)
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    (d / "SHA256SUMS").write_bytes(((sums_line if sums_line is not None else f"{digest}  {ASSET}") + "\n").encode())
    return d


GOOD = {f"meta-harness-{TAG}/scripts/replay_offline.py": b"print('replay')\n",
        f"meta-harness-{TAG}/README.md": b"# meta-harness\n"}


def _run(rel: Path, target: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, META_HARNESS_BASE_URL=rel.resolve().as_uri(), META_HARNESS_REF=TAG)
    return subprocess.run([_bash(), str(SCRIPT), "--target", str(target)], capture_output=True, text=True, env=env,
                          timeout=120)


def test_a_verified_release_is_unpacked_with_its_entry_point(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "sha256 OK" in p.stdout
    # a property of the result, not the exit code: the entry point exists with the released bytes
    assert (target / "scripts" / "replay_offline.py").read_bytes() == b"print('replay')\n"
    assert (target / "README.md").is_file()


def test_a_tampered_asset_is_refused_and_nothing_is_unpacked(tmp_path):
    rel = _release(tmp_path / "rel", GOOD, sums_line=f"{'0' * 64}  {ASSET}")
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0
    assert "sha256 mismatch" in p.stderr
    assert not target.exists()


def test_sha256sums_without_a_line_for_the_asset_is_refused(tmp_path):
    rel = _release(tmp_path / "rel", GOOD, sums_line=f"{'a' * 64}  some-other-file.zip")
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0 and "no line for" in p.stderr
    assert not target.exists()



@pytest.mark.parametrize("extra_entry", ["duplicate", "conflicting", "malformed"])
def test_ambiguous_sha256sums_refused_before_unpacked(tmp_path, extra_entry):
    """Matching a valid first line is insufficient if another asset line exists."""
    rel = _release(tmp_path / "rel", GOOD)
    sums = rel / "SHA256SUMS"
    valid_line = sums.read_text(encoding="utf-8").strip()
    bad_line = {
        "duplicate": valid_line,
        "conflicting": f"{'0' * 64}  *{ASSET}",
        "malformed": f"invalid-sha256  {ASSET}",
    }[extra_entry]
    sums.write_text(valid_line + "\n" + bad_line + "\n", encoding="utf-8")

    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0, p.stdout + p.stderr
    assert "duplicate or malformed entries" in p.stderr
    assert not target.exists(), "ambiguous checksum must not publish an installation"



def test_a_missing_asset_is_refused(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    (rel / ASSET).unlink()
    p = _run(rel, tmp_path / "out" / "mh")
    assert p.returncode != 0 and "could not download" in p.stderr


def test_a_non_empty_target_is_not_overwritten(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    target = tmp_path / "out" / "mh"
    target.mkdir(parents=True)
    (target / "mine.txt").write_text("keep", encoding="utf-8")
    p = _run(rel, target)
    assert p.returncode != 0 and "not empty" in (p.stdout + p.stderr)
    assert (target / "mine.txt").read_text(encoding="utf-8") == "keep"


def test_an_archive_with_an_escaping_path_is_refused(tmp_path):
    rel = _release(tmp_path / "rel", {**GOOD, "../escape.txt": b"x"})
    p = _run(rel, tmp_path / "out" / "mh")
    assert p.returncode != 0 and "unsafe path" in (p.stdout + p.stderr)
    assert not (tmp_path / "out" / "escape.txt").exists() and not (tmp_path / "escape.txt").exists()


def test_an_archive_without_the_entry_point_is_refused(tmp_path):
    rel = _release(tmp_path / "rel", {f"meta-harness-{TAG}/README.md": b"# not the harness\n"})
    p = _run(rel, tmp_path / "out" / "mh")
    assert p.returncode != 0 and "replay_offline.py is missing" in p.stderr
    assert not (tmp_path / "out" / "mh").exists(), "invalid archive must not leave a partial install"
    assert not list((tmp_path / "out").glob(".meta-harness-stage-*")), "staging directory leaked"



def test_default_pin_is_the_published_release_tag():
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'META_HARNESS_DEFAULT_REF="v1.0.0"' in src
    assert "$script:MetaHarnessDefaultRef = 'v1.0.0'" in (ROOT / "scripts" / "install-meta-harness.ps1").read_text(
        encoding="utf-8")


def test_missing_entrypoint_preserves_an_existing_empty_target(tmp_path):
    rel = _release(tmp_path / "rel", {f"meta-harness-{TAG}/README.md": b"# incomplete\\n"})
    target = tmp_path / "out" / "mh"
    target.mkdir(parents=True)
    p = _run(rel, target)
    assert p.returncode != 0 and "replay_offline.py is missing" in p.stderr
    assert target.is_dir() and not list(target.iterdir())
    assert not list(target.parent.glob(".meta-harness-stage-*"))


def test_windows_style_zip_path_is_rejected_on_all_platforms(tmp_path):
    rel = _release(tmp_path / "rel", {**GOOD, f"meta-harness-{TAG}\\\\scripts\\\\escape.py": b"x"})
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0 and "unsafe path" in (p.stdout + p.stderr)
    assert not target.exists()


def test_case_colliding_zip_members_are_rejected_before_extraction(tmp_path):
    rel = _release(tmp_path / "rel", {**GOOD,
                   f"meta-harness-{TAG}/scripts/Replay_Offline.py": b"print('different')\\n"})
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0 and "duplicate archive path" in (p.stdout + p.stderr)
    assert not target.exists()
