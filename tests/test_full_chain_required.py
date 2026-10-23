"""Network-free negative controls for requested Linux chain installers.

These tests run the *actual* install/install.sh against isolated synthetic
filesystem fixtures. A green fixture is not a real ecosystem canary.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_INSTALLER = ROOT / "install" / "install.sh"
CHAIN = (
    "install-sentinel.sh",
    "install-overmind.sh",
    "install-projectindex.sh",
    "install-extractor.sh",
)


@pytest.fixture
def starter(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "starter"
    home = tmp_path / "isolated-home"
    home.mkdir()
    for directory in ("install", "docs", "scripts", "rules", "memory/templates"):
        (root / directory).mkdir(parents=True)
    destination = root / "install/install.sh"
    shutil.copyfile(SOURCE_INSTALLER, destination)
    (root / "docs/HASH-linux.txt").write_text(
        hashlib.sha256(destination.read_bytes()).hexdigest(), encoding="ascii"
    )
    for name in ("rules.md", "e156.md", "advanced-stats.md", "lessons.md"):
        (root / "rules" / name).write_text(
            "project={{PROJECTINDEX_ROOT}}\n", encoding="utf-8"
        )
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "CODEX.md"):
        (root / name).write_text("synthetic fixture only\n", encoding="utf-8")
    (root / "memory/MEMORY.md").write_text("memory\n", encoding="utf-8")
    (root / "memory/templates/test.md").write_text("template\n", encoding="utf-8")
    for name in CHAIN:
        (root / "scripts" / name).write_text(
            "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
        )
    return root, home


def run_install(root: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(
        ["bash", str(root / "install/install.sh"), *args, "--github-user", "fixture-ci"],
        cwd=root, env=env, capture_output=True, text=True, timeout=30,
        check=False,
    )


@pytest.mark.parametrize("missing", CHAIN)
def test_full_refuses_missing_requested_script_before_modifying_home(starter, missing):
    root, home = starter
    (root / "scripts" / missing).unlink()
    result = run_install(root, home, "--full")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert f"requested chain installer is missing: {root / 'scripts' / missing}" in (result.stdout + result.stderr)
    assert "REFUSED: no user configuration has been changed." in (result.stdout + result.stderr)
    assert not (home / ".claude").exists()
    assert not (home / "code").exists()


@pytest.mark.parametrize(("missing", "requested_flags"), [
    ("install-sentinel.sh", ("--install-sentinel", "test-repo")),
    ("install-overmind.sh", ("--install-overmind",)),
    ("install-projectindex.sh", ("--project-index-root", "test-index")),
    ("install-extractor.sh", ("--install-extractor",)),
])
def test_individually_requested_missing_layer_refuses(starter, missing, requested_flags):
    root, home = starter
    (root / "scripts" / missing).unlink()
    result = run_install(root, home, "--non-interactive", *requested_flags)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert missing in (result.stdout + result.stderr)
    assert not (home / ".gemini").exists()


def test_complete_stubbed_chain_control_exits_success(starter):
    root, home = starter
    result = run_install(root, home, "--full")
    assert result.returncode == 0, (result.stdout, result.stderr)
    for name in ("sentinel", "overmind", "projectindex", "extractor"):
        assert f"{name:<14s} ok" in result.stdout


def test_non_requested_missing_scripts_may_be_skipped(starter):
    root, home = starter
    for name in CHAIN:
        (root / "scripts" / name).unlink()
    result = run_install(root, home, "--non-interactive")
    assert result.returncode == 0, (result.stdout, result.stderr)
    for name in ("sentinel", "overmind", "projectindex", "extractor"):
        assert f"{name:<14s} skipped" in result.stdout


def test_script_deleted_after_preflight_still_fails_chain(starter):
    root, home = starter
    (root / "scripts/install-sentinel.sh").write_text(
        '#!/usr/bin/env bash\nrm -f "$(dirname "$0")/install-overmind.sh"\n',
        encoding="utf-8",
    )
    result = run_install(root, home, "--full")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "install-overmind.sh exited" in (result.stdout + result.stderr)
    assert "overmind" in result.stdout and "failed" in result.stdout
