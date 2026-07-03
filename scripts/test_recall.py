"""Tests for recall.py — offline BM25 memory retrieval."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import recall


def _write(d: Path, name: str, description: str, body: str) -> None:
    (d / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def _corpus(tmp_path: Path) -> Path:
    _write(tmp_path, "ed25519-signing",
           "Ed25519 keyless signing and public-key verification of bundles",
           "Asymmetric signatures, public key committed, offline verify, sigstore Rekor.")
    _write(tmp_path, "aact-queries",
           "Querying the AACT ClinicalTrials.gov snapshot for trial metadata",
           "Lowercase intervention types, verify columns exist, drug names not classes.")
    _write(tmp_path, "pooling-gotchas",
           "Meta-analysis pooling gotchas: HKSJ floor, DL bias, log scale",
           "Never use DL for small k; pool on log scale; back-transform after.")
    (tmp_path / "MEMORY.md").write_text("# index\n", encoding="utf-8")
    return tmp_path


def test_ranks_relevant_memory_first(tmp_path):
    _corpus(tmp_path)
    hits = recall.recall("how do I verify an ed25519 signed bundle", tmp_path, k=5)
    assert hits, "expected at least one hit"
    assert hits[0][1]["name"] == "ed25519-signing"


def test_topic_separation(tmp_path):
    _corpus(tmp_path)
    hits = recall.recall("clinicaltrials AACT snapshot columns", tmp_path, k=5)
    assert hits[0][1]["name"] == "aact-queries"


def test_memory_md_excluded_from_corpus(tmp_path):
    _corpus(tmp_path)
    docs = recall._load(tmp_path)
    assert "MEMORY" not in {d["name"] for d in docs}
    assert len(docs) == 3


def test_no_overlap_returns_empty(tmp_path):
    _corpus(tmp_path)
    assert recall.recall("zzz quantum bryophyte xylophone", tmp_path, k=5) == []


def test_description_weight_boosts_match(tmp_path):
    # Term only in description should still rank that doc top.
    _write(tmp_path, "doc-a", "fragility index robustness", "unrelated body text here.")
    _write(tmp_path, "doc-b", "completely different topic", "fragility appears once in body.")
    (tmp_path / "MEMORY.md").write_text("# index\n", encoding="utf-8")
    hits = recall.recall("fragility", tmp_path, k=5)
    assert hits[0][1]["name"] == "doc-a"


# --- default memory-dir discovery (no hardcoded per-user path) --------------


def test_encode_project_dir_does_not_collapse_separators():
    # Claude Code names the projects/ subdir by replacing EACH separator with a
    # dash; "C:\\Users\\x" -> "C--Users-x" (colon AND backslash both -> dash).
    # A regex that collapsed consecutive separators would yield "C-Users-x" and
    # silently fail to match the real store. Guard against that regression.
    assert recall._encode_project_dir(Path(r"C:\Users\x")) == "C--Users-x"
    assert recall._encode_project_dir(Path("/home/x/proj")) == "-home-x-proj"


def test_discover_respects_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_MEMORY_DIR", str(tmp_path / "custom"))
    assert recall.discover_memory_dir() == (tmp_path / "custom")


def test_discover_returns_none_when_no_projects(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    monkeypatch.setattr(recall.Path, "home", classmethod(lambda cls: tmp_path))
    assert recall.discover_memory_dir() is None


def test_discover_picks_sole_candidate(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    mem = tmp_path / ".claude" / "projects" / "some-proj" / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setattr(recall.Path, "home", classmethod(lambda cls: tmp_path))
    assert recall.discover_memory_dir() == mem


def test_discover_prefers_cwd_match(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    projects = tmp_path / ".claude" / "projects"
    other = projects / "other-proj" / "memory"
    other.mkdir(parents=True)
    fake_cwd = tmp_path / "work" / "repo"
    fake_cwd.mkdir(parents=True)
    encoded = recall._encode_project_dir(fake_cwd)
    mine = projects / encoded / "memory"
    mine.mkdir(parents=True)
    monkeypatch.setattr(recall.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(recall.Path, "cwd", classmethod(lambda cls: fake_cwd))
    assert recall.discover_memory_dir() == mine


def test_no_hardcoded_username_in_source():
    # The whole point of the discovery refactor: the file must not ship a
    # specific user's home/project path. (Guards against regressing to the old
    # Path.home()/".claude"/"projects"/"C--Users-mahmo" default.)
    src = (Path(recall.__file__)).read_text(encoding="utf-8")
    assert "mahmo" not in src
    assert "C--Users-mahmo" not in src


# --- --json machine-readable output (agent/programmatic consumption) --------


def test_json_query_emits_valid_ranked_json(tmp_path, capsys):
    _corpus(tmp_path)
    rc = recall.main(["how do I verify an ed25519 signed bundle",
                      "--memory-dir", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] >= 1
    assert payload["hits"][0]["name"] == "ed25519-signing"
    top = payload["hits"][0]
    # Contract: every hit carries these keys for a programmatic consumer.
    assert set(top) == {"score", "name", "description", "path"}
    assert isinstance(top["score"], float)


def test_json_no_match_emits_empty_hits(tmp_path, capsys):
    _corpus(tmp_path)
    rc = recall.main(["zzz quantum bryophyte xylophone",
                      "--memory-dir", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 0
    assert payload["hits"] == []


def test_json_health_reports_index_stats(tmp_path, capsys):
    _corpus(tmp_path)
    rc = recall.main(["--memory-dir", str(tmp_path), "--health", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["memories"] == 3
    assert payload["over_soft_limit"] is False
    assert payload["soft_limit"] == recall.INDEX_SOFT_LIMIT


def test_json_error_is_json_not_stderr_string(tmp_path, capsys):
    # A --json consumer must ALWAYS get JSON, even on the missing-dir failure
    # path — never a bare stderr string it can't parse.
    rc = recall.main(["x", "--memory-dir", str(tmp_path / "nope"), "--json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert "error" in payload


# --- input validation on the -k flag ----------------------------------------


@pytest.mark.parametrize("bad_k", ["-3", "0"])
def test_negative_or_zero_k_is_rejected(tmp_path, bad_k):
    # A negative -k would hit Python's `[:k]` slice and silently drop the last
    # |k| hits rather than erroring. argparse .error() exits 2 via SystemExit.
    with pytest.raises(SystemExit) as exc:
        recall.main(["query", "--memory-dir", str(tmp_path), "-k", bad_k])
    assert exc.value.code == 2
