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


def _run(rel: Path, target: Path, ref: str = TAG) -> subprocess.CompletedProcess:
    env = dict(os.environ, META_HARNESS_BASE_URL=rel.resolve().as_uri(), META_HARNESS_REF=ref)
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


@pytest.mark.parametrize("second_digest", ["same", "conflicting"])
def test_duplicate_sha256sums_asset_entries_are_refused(tmp_path, second_digest):
    rel = _release(tmp_path / "rel", GOOD)
    sums = rel / "SHA256SUMS"
    first_line = sums.read_text(encoding="ascii").strip()
    other_line = first_line if second_digest == "same" else f"{'0' * 64}  {ASSET}"
    sums.write_text(first_line + "\n" + other_line + "\n", encoding="ascii")
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0 and "multiple entries" in (p.stdout + p.stderr)
    assert not target.exists()


def test_sha256sums_unrelated_entry_is_not_mistaken_for_duplicate(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    sums = rel / "SHA256SUMS"
    sums.write_text(sums.read_text(encoding="ascii") + f"{'0' * 64}  different.zip\n", encoding="ascii")
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (target / "scripts" / "replay_offline.py").is_file()


@pytest.mark.parametrize("position", ["only", "after_valid"])
def test_malformed_matching_sha256sums_record_is_refused(tmp_path, position):
    rel = _release(tmp_path / "rel", GOOD)
    sums = rel / "SHA256SUMS"
    malformed = f"invalid-sha256  {ASSET}\n"
    first_line = sums.read_text(encoding="ascii")
    sums.write_text((first_line if position == "after_valid" else "") + malformed, encoding="ascii")
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    # A second matching line is also an ambiguity, even if it is malformed.
    expected_reason = "malformed entry" if position == "only" else "multiple entries"
    assert p.returncode != 0 and expected_reason in (p.stdout + p.stderr)
    assert not target.exists()


def test_single_gnu_binary_marker_checksum_is_accepted(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    sums = rel / "SHA256SUMS"
    digest = hashlib.sha256((rel / ASSET).read_bytes()).hexdigest()
    sums.write_text(f"{digest} *{ASSET}\n", encoding="ascii")
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (target / "scripts" / "replay_offline.py").is_file()


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


@pytest.mark.parametrize(
    "unsafe_component",
    [
        "CON",
        "con.txt",
        "PRN",
        "AUX.md",
        "NUL",
        "CONIN$",
        "conout$.log",
        "COM1.py",
        "lpt9.log",
        "COM¹",
        "COM².log",
        "COM³.txt",
        "LPT¹",
        "lpt².dat",
        "LPT³",
        "line" + chr(10) + "break",
        "tab" + chr(9) + "name",
        "carriage" + chr(13) + "return",
    ],
)
def test_windows_reserved_or_control_character_zip_paths_refuse_on_all_platforms(
    tmp_path, unsafe_component
):
    # Fully checksummed fixture: path validation, not SHA mismatch, must refuse.
    rel = _release(tmp_path / "rel", {
        **GOOD,
        f"meta-harness-{TAG}/docs/{unsafe_component}": b"cannot install portably\\n",
    })
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0, p.stdout + p.stderr
    assert "unsafe path in archive" in p.stderr
    assert not target.exists(), "refusal must not publish an archive"
    assert not list(target.parent.glob(".meta-harness-stage-*")), "staging directory leaked"


@pytest.mark.parametrize("safe_component", ["COM10.txt", "LPT10.log", "README¹.md", "CONINPUT.txt", "CONOUTSIDE.txt"])
def test_nonreserved_windows_lookalike_names_are_allowed(tmp_path, safe_component):
    # Full checksummed local fixture: don't over-block ordinary filenames.
    rel = _release(tmp_path / "rel", {
        **GOOD,
        f"meta-harness-{TAG}/docs/{safe_component}": b"benign fixture\\n",
    })
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (target / "docs" / safe_component).is_file()


def test_case_colliding_zip_members_are_rejected_before_extraction(tmp_path):
    rel = _release(tmp_path / "rel", {**GOOD,
                   f"meta-harness-{TAG}/scripts/Replay_Offline.py": b"print('different')\\n"})
    target = tmp_path / "out" / "mh"
    p = _run(rel, target)
    assert p.returncode != 0 and "duplicate archive path" in (p.stdout + p.stderr)
    assert not target.exists()

# These checks exercise the actual Bash manifest-pin helper in both Ubuntu and
# Windows Git Bash. Release manifests here are *integrity fixtures*, not research
# data or proof of any signed scientific certification.
PUBLISHED_V1_MANIFEST = (
    "694dc82f51fcde9040a8e1a5f0172978cb1a6f3eeade237fcd81df61185c2d0d"
    "  meta-harness-v1.0.0.zip\n"
)
PUBLISHED_V1_MANIFEST_SHA = "3bf1d1f9eaa6f423f3130ca5f6413b05dcf2994833a9fce038e1ee8e9ad00ddb"


def _check_pinned_manifest(path: Path, ref: str, base: str) -> subprocess.CompletedProcess:
    command = 'source "$1" --import; verify_meta_harness_release_manifest "$2" "$3" "$4"'
    return subprocess.run(
        [_bash(), "-c", command, "bash", str(SCRIPT), str(path), ref, base],
        capture_output=True, text=True, timeout=30,
    )


def test_independently_pinned_v1_manifest_is_accepted(tmp_path):
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_bytes(PUBLISHED_V1_MANIFEST.encode("ascii"))
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == PUBLISHED_V1_MANIFEST_SHA
    p = _check_pinned_manifest(manifest, "v1.0.0",
                               "https://github.com/mahmood726-cyber/meta-harness/releases/download/v1.0.0")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "pinned meta-harness v1.0.0 SHA256SUMS OK" in p.stdout


def test_manifest_pin_refuses_coordinated_zip_and_sums_replacement(tmp_path):
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_text("0" * 64 + "  meta-harness-v1.0.0.zip\n", encoding="ascii")
    # Its ZIP could match this altered checksum, but starter's independent pin cannot.
    p = _check_pinned_manifest(manifest, "v1.0.0", tmp_path.as_uri())
    assert p.returncode != 0
    assert "differs from reviewed pinned digest" in p.stderr


def test_unreviewed_remote_release_ref_is_refused_even_with_well_formed_sums(tmp_path):
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_bytes(PUBLISHED_V1_MANIFEST.encode("ascii"))
    p = _check_pinned_manifest(manifest, "v1.0.1",
                               "https://github.com/mahmood726-cyber/meta-harness/releases/download/v1.0.1")
    assert p.returncode != 0
    assert "unreviewed meta-harness release" in p.stderr


def test_only_explicitly_local_fixture_ref_is_unpinned(tmp_path):
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_text("0" * 64 + f"  {ASSET}\n", encoding="ascii")
    local = _check_pinned_manifest(manifest, TAG, tmp_path.as_uri())
    assert local.returncode == 0, local.stdout + local.stderr
    assert "LOCAL TEST FIXTURE" in local.stderr
    remote = _check_pinned_manifest(manifest, TAG, "https://example.org/releases")
    assert remote.returncode != 0


def test_actual_installer_refuses_changed_v1_manifest_before_zip_fetch(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    target = tmp_path / "out" / "mh"
    p = _run(rel, target, ref="v1.0.0")
    assert p.returncode != 0
    assert "differs from reviewed pinned digest" in p.stderr
    assert "could not download" not in p.stderr, "manifest must gate before ZIP download"
    assert not target.exists()

def test_crlf_release_manifest_is_refused_as_changed_bytes(tmp_path):
    manifest = tmp_path / "SHA256SUMS"
    # On Windows, Path.write_text() silently writes CRLF; release checksums
    # must cover the actual LF-terminated 90-byte publication, not text equality.
    manifest.write_bytes(PUBLISHED_V1_MANIFEST.replace("\n", "\r\n").encode("ascii"))
    p = _check_pinned_manifest(manifest, "v1.0.0", tmp_path.as_uri())
    assert p.returncode != 0
    assert "differs from reviewed pinned digest" in p.stderr



def test_python_fallback_hashes_in_chunks_when_sha256sum_is_missing(tmp_path):
    """Exercise the real installer helper with sha256sum intentionally unavailable.

    The payload is a binary integrity fixture, not research data. A regression
    to open(...).read() would reintroduce a ~609 MB memory allocation on the
    published release download, even if small digest fixtures still matched.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'for chunk in iter(lambda: stream.read(1024 * 1024), b""):' in source
    payload = tmp_path / "hash-fixture.bin"
    payload.write_bytes(b"integrity-fallback-fixture" * 131073)
    shell = r'''source "$1" --import
command() {
    if [[ "${1:-}" == "-v" && "${2:-}" == "sha256sum" ]]; then return 1; fi
    builtin command "$@"
}
meta_harness_sha256 "$2"'''
    result = subprocess.run(
        [_bash(), "-c", shell, "bash", str(SCRIPT), str(payload)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == hashlib.sha256(payload.read_bytes()).hexdigest()


def test_no_hash_tool_or_python_must_fail_closed(tmp_path):
    payload = tmp_path / "hash-fixture.bin"
    payload.write_bytes(b"binary integrity fixture")
    shell = r'''source "$1" --import
command() {
    if [[ "${1:-}" == "-v" && "${2:-}" == "sha256sum" ]]; then return 1; fi
    builtin command "$@"
}
PYTHON=""
meta_harness_sha256 "$2"'''
    result = subprocess.run(
        [_bash(), "-c", shell, "bash", str(SCRIPT), str(payload)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "REFUSED: no SHA256 tool available" in result.stderr


@pytest.mark.parametrize("first,second", [
    ("caf\u00e9.txt", "cafe\u0301.txt"),       # NFC versus NFD
    ("FO\u00d6.txt", "foO\u0308.txt"),          # case plus canonical equivalence
])
def test_unicode_equivalent_zip_names_refuse_before_extraction(tmp_path, first, second):
    # A matching SHA256SUMS alone cannot make colliding filenames portable.
    # The real installer must preflight *all* names, without publishing either.
    rel = _release(tmp_path / "rel", {
        **GOOD,
        f"meta-harness-{TAG}/notes/{first}": b"one",
        f"meta-harness-{TAG}/notes/{second}": b"two",
    })
    target = tmp_path / "out" / "mh"
    target.mkdir(parents=True)
    result = _run(rel, target)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "duplicate archive path" in (result.stdout + result.stderr)
    assert target.is_dir() and not list(target.iterdir()), "empty pre-existing target changed"
    assert not list(target.parent.glob(".meta-harness-stage-*")), "temporary extraction leaked"


def test_single_unicode_named_member_is_still_installable(tmp_path):
    rel = _release(tmp_path / "rel", {
        **GOOD, f"meta-harness-{TAG}/notes/cafe\u0301.txt": b"note"
    })
    target = tmp_path / "out" / "mh"
    result = _run(rel, target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "scripts" / "replay_offline.py").is_file()


def test_e156_capsule_profile_path_is_literal_on_windows_git_bash_and_ubuntu(tmp_path):
    """Cross-platform installer integrity: do not execute a path on shell startup.

    This tests the real shipped Bash helper with synthetic shell metacharacters;
    it is not a live signed five-component ecosystem installation.
    """
    installer = tmp_path / "installer.sh"
    installer.write_bytes((ROOT / "scripts" / "install-e156-capsules.sh").read_bytes())
    for name in (".bashrc", ".zshrc"):
        (tmp_path / name).write_text("", encoding="utf-8")
    # The old double-quoted export executed $(touch ...) while sourcing the profile.
    requested = "dir with spaces ' \" $HOME $(touch path-executed)"
    command = (
        'source "./installer.sh" --import; '
        'persist_e156_path_env "$1" >/dev/null; '
        'source "./.bashrc"; [[ "$E156_CAPSULES_PATH" == "$1" ]] || exit 10; '
        'source "./.zshrc"; [[ "$E156_CAPSULES_PATH" == "$1" ]] || exit 11'
    )
    result = subprocess.run(
        [_bash(), "-c", command, "_", requested],
        cwd=tmp_path,
        env={**os.environ, "HOME": "."},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "path-executed").exists()


@pytest.mark.parametrize("bad_ref", [
    "../escape", "tag/../../escape", r"..\..\escape",
    "v1.0.0?raw=1", "v1.0.0#fragment", "v1.0.0%2Fescape",
    "v1.0.0 latest", "v1.0.0\nextra", "-unexpected-option",
])
@pytest.mark.parametrize("via_cli", [False, True])
def test_unsafe_release_ref_is_refused_before_download_or_publication(tmp_path, bad_ref, via_cli):
    """Run the actual Bash installer; test input is synthetic, not a signed release."""
    target = tmp_path / "published"
    env = dict(os.environ, META_HARNESS_BASE_URL=(tmp_path / "no-release").resolve().as_uri(),
               META_HARNESS_REF=(TAG if via_cli else bad_ref))
    cmd = [_bash(), str(SCRIPT), "--target", str(target)]
    if via_cli:
        cmd.extend(["--ref", bad_ref])
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    assert p.returncode == 2, p.stdout + p.stderr
    # Git for Windows may re-tokenise a newline embedded in an argv value.
    # Both the ref validator and unknown-argument parser must refuse before
    # any fetch/publication; this exception is ONLY for that Windows case.
    if via_cli and chr(10) in bad_ref and os.name == "nt":
        assert ("invalid Meta-Harness release ref" in p.stderr
                or "unknown arg: extra" in p.stderr), p.stderr
    else:
        assert "invalid Meta-Harness release ref" in p.stderr
    assert "could not download" not in p.stderr
    assert "release fetch" not in p.stdout
    assert not target.exists()


def test_safe_explicit_ref_still_fetches_verified_local_fixture(tmp_path):
    rel = _release(tmp_path / "rel", GOOD)
    target = tmp_path / "published"
    env = dict(os.environ, META_HARNESS_BASE_URL=rel.resolve().as_uri(),
               META_HARNESS_REF="v0-incorrect")
    p = subprocess.run([_bash(), str(SCRIPT), "--ref", TAG, "--target", str(target)],
                       capture_output=True, text=True, env=env, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (target / "scripts" / "replay_offline.py").is_file()
