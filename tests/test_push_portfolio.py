"""Regression tests for push-portfolio.py find_git_repos.

The hidden-config-repo skip rule was added 2026-04-27 after a code-review
finding: a student running `push-portfolio.py --report` on a broad root
(e.g. $HOME) could pick up `.claude/`, `.codex/`, `.gemini/`, `.config/...`
git repos and surface them in the portfolio listing. Those config dirs
are private by convention and the agent-config sentinel rule already
blocks them from being committed into student work — so they have no
business showing up in a "your portfolio" scan either.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "push-portfolio.py"


@pytest.fixture(scope="module")
def push_portfolio():
    """Import scripts/push-portfolio.py despite the hyphen in the filename."""
    spec = importlib.util.spec_from_file_location("push_portfolio", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["push_portfolio"] = module
    spec.loader.exec_module(module)
    return module


def _make_repo(parent: Path, name: str) -> Path:
    """Create a fake bare-bones git repo (just the .git/ marker)."""
    repo = parent / name
    (repo / ".git").mkdir(parents=True)
    return repo


def test_finds_normal_repos(push_portfolio, tmp_path):
    a = _make_repo(tmp_path, "project-a")
    b = _make_repo(tmp_path, "project-b")
    found = push_portfolio.find_git_repos([tmp_path])
    assert set(found) == {a, b}


def test_skips_dotted_top_level_repos(push_portfolio, tmp_path):
    """A scan of $HOME-like roots must skip ~/.claude/, ~/.codex/, etc."""
    real = _make_repo(tmp_path, "real-paper")
    _make_repo(tmp_path, ".claude")
    _make_repo(tmp_path, ".codex")
    _make_repo(tmp_path, ".gemini")
    _make_repo(tmp_path, ".config")
    found = push_portfolio.find_git_repos([tmp_path])
    assert found == [real]


def test_skips_repos_under_dotted_ancestor(push_portfolio, tmp_path):
    """A repo nested inside a dotted dir (e.g. .hidden/repo) must be skipped."""
    real = _make_repo(tmp_path, "visible")
    hidden_parent = tmp_path / ".hidden"
    hidden_parent.mkdir()
    _make_repo(hidden_parent, "buried-repo")
    found = push_portfolio.find_git_repos([tmp_path])
    assert found == [real]


def test_still_skips_build_and_node_modules(push_portfolio, tmp_path):
    real = _make_repo(tmp_path, "app")
    nm_parent = tmp_path / "node_modules"
    nm_parent.mkdir()
    _make_repo(nm_parent, "some-pkg")
    build_parent = tmp_path / "build"
    build_parent.mkdir()
    _make_repo(build_parent, "artifact")
    found = push_portfolio.find_git_repos([tmp_path])
    assert found == [real]
