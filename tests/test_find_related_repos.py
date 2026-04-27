"""Tests for scripts/find-related-repos.py.

The tool is what an agent runs at the start of a new project to surface
prior work in the user's portfolio. Failure modes worth covering:
  - missing index file (must fail-closed with a clear message, not crash)
  - manifest with no records (graceful empty result, not zero-division)
  - case-insensitive matching
  - phrase scoring outranks token-only scoring
  - README excerpt + code grep work when the path exists
  - handles INDEX.md fallback when no manifest is present
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "find-related-repos.py"


@pytest.fixture(scope="module")
def find_related():
    spec = importlib.util.spec_from_file_location("find_related_repos", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["find_related_repos"] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "restart-manifest.json"
    p.write_text(json.dumps({"records": records}), encoding="utf-8")
    return p


def test_load_index_raises_on_missing(find_related, tmp_path):
    nonexistent = tmp_path / "no-such.json"
    with pytest.raises(FileNotFoundError):
        find_related.load_index(str(nonexistent))


def test_load_index_handles_empty_records(find_related, tmp_path):
    p = _write_manifest(tmp_path, [])
    projects, source = find_related.load_index(str(p))
    assert projects == []
    assert source == p


def test_score_phrase_outranks_tokens(find_related, tmp_path):
    p = _write_manifest(tmp_path, [
        {"name": "Forest Plot Tool", "workbook": {"title": "Pure forest plot library"}},
        {"name": "Plot Helpers", "workbook": {"title": "Random scatter plot widgets"}},
    ])
    projects, _ = find_related.load_index(str(p))
    phrase = "forest plot"
    tokens = find_related.tokenize(phrase)
    scored = [find_related.score_project(proj, phrase, tokens) for proj in projects]
    by_name = {p.name: p for p in scored}
    # "Forest Plot Tool" gets +10 (phrase in name) +5 (phrase in title)
    # "Plot Helpers" gets +2 (token in name) +1 (token in title); phrase NOT
    # present in either field
    assert by_name["Forest Plot Tool"].score > by_name["Plot Helpers"].score
    assert by_name["Forest Plot Tool"].score >= 10
    assert "name(phrase)" in by_name["Forest Plot Tool"].matched_fields


def test_case_insensitive_matching(find_related, tmp_path):
    p = _write_manifest(tmp_path, [
        {"name": "SGLT2-HFpEF Demo", "workbook": {"title": "PARAGON-HF replication"}},
    ])
    projects, _ = find_related.load_index(str(p))
    scored = find_related.score_project(projects[0], "sglt2 hfpef", find_related.tokenize("sglt2 hfpef"))
    assert scored.score > 0


def test_no_matches_returns_empty(find_related, tmp_path):
    p = _write_manifest(tmp_path, [
        {"name": "Cardiology Tool", "workbook": {"title": "Heart-failure pooler"}},
    ])
    projects, _ = find_related.load_index(str(p))
    scored = [find_related.score_project(proj, "quantum", ["quantum"]) for proj in projects]
    assert all(p.score == 0 for p in scored)


def test_index_md_fallback(find_related, tmp_path):
    md = tmp_path / "INDEX.md"
    md.write_text(
        "# My Index\n\n"
        "### Project Alpha\n"
        "> path: `C:\\Projects\\alpha`\n"
        "> Does cool things\n\n"
        "### Project Beta\n"
        "> Does other things\n",
        encoding="utf-8",
    )
    projects, source = find_related.load_index(str(md))
    assert source == md
    assert {p.name for p in projects} == {"Project Alpha", "Project Beta"}
    alpha = next(p for p in projects if p.name == "Project Alpha")
    # Path extraction from blockquoted backticks
    assert alpha.path == Path("C:\\Projects\\alpha")


def test_readme_excerpt_returns_none_when_path_missing(find_related, tmp_path):
    nonexistent = tmp_path / "ghost-repo"
    assert find_related.readme_excerpt(nonexistent, ["topic"]) is None


def test_readme_excerpt_returns_blockquoted_lines(find_related, tmp_path):
    repo = tmp_path / "real-repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Title\n\nLine 2\nLine 3\n",
        encoding="utf-8",
    )
    out = find_related.readme_excerpt(repo, ["title"])
    assert out is not None
    assert out.startswith("  > # Title")
    assert "  > Line 2" in out
    assert "  > Line 3" in out


def test_code_grep_finds_token_in_python_file(find_related, tmp_path):
    repo = tmp_path / "code-repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "tool.py").write_text(
        "def transportability_score(x):\n    return x * 2\n",
        encoding="utf-8",
    )
    hits = find_related.code_grep(repo, ["transportability"], max_hits=3)
    assert len(hits) == 1
    assert "src/tool.py:1" in hits[0]
    assert "transportability_score" in hits[0]


def test_code_grep_skips_node_modules_and_dotted_dirs(find_related, tmp_path):
    repo = tmp_path / "noisy-repo"
    (repo / "src").mkdir(parents=True)
    (repo / "node_modules" / "junk").mkdir(parents=True)
    (repo / ".cache").mkdir()
    (repo / "src" / "real.py").write_text("topic_x = 1\n", encoding="utf-8")
    (repo / "node_modules" / "junk" / "bad.py").write_text("topic_x = 2\n", encoding="utf-8")
    (repo / ".cache" / "bad.py").write_text("topic_x = 3\n", encoding="utf-8")
    hits = find_related.code_grep(repo, ["topic_x"], max_hits=10)
    # Only the src/real.py hit -- the others are skipped.
    assert len(hits) == 1
    assert "src/real.py" in hits[0]
