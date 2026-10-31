"""Installer pin-integrity regressions using a LOCAL disposable Git remote.

These are negative/positive control fixtures for git ref handling only.
They do NOT download a real RCT Extractor release or validate extraction.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-extractor.sh"


def _git(*args: str) -> str:
    result = subprocess.run(["git", *map(str, args)], check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def _make_local_origin(tmp_path: Path) -> tuple[Path, str]:
    origin = tmp_path / "origin.git"
    source = tmp_path / "upstream-source"
    _git("init", "--bare", "--initial-branch=main", str(origin))
    _git("init", "--initial-branch=main", str(source))
    _git("-C", str(source), "config", "user.name", "CI fixture")
    _git("-C", str(source), "config", "user.email", "fixture@example.invalid")
    (source / "scripts").mkdir()
    (source / "scripts" / "build_metakit_config.py").write_text(
        "# TEST FIXTURE, not real extractor data\n", encoding="utf-8"
    )
    _git("-C", str(source), "add", "scripts/build_metakit_config.py")
    _git("-C", str(source), "-c", "commit.gpgsign=false",
         "commit", "-m", "local installer pin test fixture")
    sha = _git("-C", str(source), "rev-parse", "HEAD")
    _git("-C", str(source), "remote", "add", "origin", str(origin))
    _git("-C", str(source), "push", "origin", "main")
    _git("-C", str(source), "tag", "v1.0.0")
    _git("-C", str(source), "push", "origin", "v1.0.0")
    return origin, sha


def _invoke(origin: Path, target: Path, ref: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ,
               TEST_ORIGIN=str(origin), TEST_TARGET=str(target),
               TEST_REF=ref, EXTRACTOR_SCRIPT=str(SCRIPT))
    return subprocess.run(
        ["bash", "-c", """
set -euo pipefail
source "$EXTRACTOR_SCRIPT" --import
extractor_repo_url() { printf '%s\\n' "$TEST_ORIGIN"; }
clone_or_update_extractor "$TEST_TARGET" "$TEST_REF"
"""],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )


def test_unsafe_ref_tokens_refused_before_clone(tmp_path: Path) -> None:
    """Option-shaped, traversal and shell-fragment refs must never reach git."""
    for index, ref in enumerate((
        "--upload-pack=sh",
        "refs/heads/../main",
        "refs//heads/main",
        "v1.0.0/",
        "$(touch unexpected)",
        "",
    )):
        target = tmp_path / f"invalid-{index}"
        run = _invoke(tmp_path / "not-a-remote", target, ref)
        assert run.returncode != 0, (ref, run.stdout, run.stderr)
        assert "REFUSED: unsafe extractor Git ref" in run.stderr
        assert not target.exists(), ref


def test_valid_tag_fetch_is_checked_out_at_resolved_commit(tmp_path: Path) -> None:
    origin, sha = _make_local_origin(tmp_path)
    target = tmp_path / "installed"
    run = _invoke(origin, target, "v1.0.0")
    assert run.returncode == 0, run.stdout + run.stderr
    assert _git("-C", str(target), "rev-parse", "HEAD") == sha
    assert f"verified extractor HEAD: {sha}" in run.stdout


def test_exact_commit_sha_fetch_is_checked_out(tmp_path: Path) -> None:
    origin, sha = _make_local_origin(tmp_path)
    target = tmp_path / "installed"
    run = _invoke(origin, target, sha)
    assert run.returncode == 0, run.stdout + run.stderr
    assert _git("-C", str(target), "rev-parse", "HEAD") == sha


def test_missing_ref_fails_even_if_fresh_clone_contains_expected_file(tmp_path: Path) -> None:
    origin, _ = _make_local_origin(tmp_path)
    target = tmp_path / "installed"
    run = _invoke(origin, target, "absent-release-tag")
    assert run.returncode != 0
    assert "REFUSED: could not fetch requested extractor ref" in run.stderr
    assert "verified extractor HEAD" not in run.stdout
    # The default clone's valid-looking entrypoint must not be used as proof
    # that the requested ref was successfully installed.
    assert (target / "scripts" / "build_metakit_config.py").is_file()


def test_missing_ref_preserves_existing_checkout_head(tmp_path: Path) -> None:
    origin, sha = _make_local_origin(tmp_path)
    target = tmp_path / "installed"
    first = _invoke(origin, target, "v1.0.0")
    assert first.returncode == 0, first.stdout + first.stderr
    bad = _invoke(origin, target, "release-never-published")
    assert bad.returncode != 0
    assert "REFUSED: could not fetch requested extractor ref" in bad.stderr
    assert _git("-C", str(target), "rev-parse", "HEAD") == sha


def test_valid_ref_can_recover_after_previous_refusal(tmp_path: Path) -> None:
    origin, sha = _make_local_origin(tmp_path)
    target = tmp_path / "installed"
    assert _invoke(origin, target, "missing-ref").returncode != 0
    good = _invoke(origin, target, "v1.0.0")
    assert good.returncode == 0, good.stdout + good.stderr
    assert _git("-C", str(target), "rev-parse", "HEAD") == sha
