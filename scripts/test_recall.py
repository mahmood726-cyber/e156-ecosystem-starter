"""Tests for recall.py — offline BM25 memory retrieval."""
from __future__ import annotations

from pathlib import Path

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
