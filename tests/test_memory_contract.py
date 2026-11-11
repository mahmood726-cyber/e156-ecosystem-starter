"""Development controls for the memory boundary; no research accuracy claims."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import recall


def write_memory(root, name="context.md", content=b"quasar telescope context\n"):
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_bytes(content)
    return path


@pytest.mark.parametrize("count", [1, 2])
def test_discovery_never_borrows_another_project(tmp_path, monkeypatch, count):
    for i in range(count):
        write_memory(tmp_path / ".claude" / "projects" / f"other-{i}" / "memory")
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path / "requested")
    assert recall.discover_memory_dir() is None


@pytest.mark.parametrize("bad", ["invalid_utf8", "directory", "broken_index"])
@pytest.mark.parametrize("health", [False, True])
def test_incomplete_store_refuses_without_partial_hits(tmp_path, capsys, bad, health):
    write_memory(tmp_path)
    if bad == "directory":
        (tmp_path / "broken.md").mkdir()
    else:
        write_memory(tmp_path, "MEMORY.md" if bad == "broken_index" else "broken.md", b"\xff")
    args = ["--health"] if health else ["quasar"]
    assert recall.main(args + ["--memory-dir", str(tmp_path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert "error" in payload
    assert "hits" not in payload


def test_directory_read_failure_is_not_empty_success(tmp_path, monkeypatch, capsys):
    def denied(self):
        raise PermissionError("denied")
    monkeypatch.setattr(Path, "iterdir", denied)
    assert recall.main(["quasar", "--memory-dir", str(tmp_path), "--json"]) == 2
    assert "error" in json.loads(capsys.readouterr().out)


def test_file_read_failure_refuses_whole_store(tmp_path, monkeypatch, capsys):
    write_memory(tmp_path)
    blocked = write_memory(tmp_path, "denied.md")
    original = Path.read_bytes
    def denied(path):
        if path == blocked:
            raise PermissionError("denied")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", denied)
    assert recall.main(["quasar", "--memory-dir", str(tmp_path), "--json"]) == 2
    assert "hits" not in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("name", ["escape.md", "MEMORY.md"])
def test_resolved_entry_outside_store_is_refused(tmp_path, monkeypatch, name):
    store = tmp_path / "store"
    entry = write_memory(store, name)
    outside = write_memory(tmp_path / "outside")
    original = Path.resolve
    def redirected(path, *args, **kwargs):
        return outside if path == entry else original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(ValueError, match="outside"):
        recall.recall("quasar", store)


@pytest.mark.parametrize("content", [b"quasar telescope\n", b"\xef\xbb\xbf---\r\nname: comet\r\ndescription: quasar\r\n---\r\nbody\r\n"])
def test_identity_and_trust_status_bind_exact_bytes(tmp_path, capsys, content):
    path = write_memory(tmp_path, content=content)
    assert recall.main(["quasar", "--memory-dir", str(tmp_path), "--json"]) == 0
    hit = json.loads(capsys.readouterr().out)["hits"][0]
    assert hit["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert hit["evidence_status"] == "unverified_memory"
    assert recall.recall("quasar", tmp_path)[0][1]["sha256"] == hit["sha256"]
    if content.startswith(b"\xef\xbb\xbf"):
        assert hit["name"] == "comet"


def test_cli_reads_each_entry_once(tmp_path, monkeypatch, capsys):
    path = write_memory(tmp_path)
    original = Path.read_bytes
    reads = []
    def counted(p):
        reads.append(p)
        return original(p)
    monkeypatch.setattr(Path, "read_bytes", counted)
    assert recall.main(["quasar", "--memory-dir", str(tmp_path), "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["hits"]) == 1
    assert reads.count(path) == 1


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_python_api_validates_result_limit(tmp_path, k):
    write_memory(tmp_path)
    with pytest.raises(ValueError):
        recall.recall("quasar", tmp_path, k)


def test_python_api_refuses_missing_store(tmp_path):
    with pytest.raises(ValueError):
        recall.recall("quasar", tmp_path / "missing")


def test_unclosed_frontmatter_refuses(tmp_path):
    write_memory(tmp_path, content=b"---\nname: quasar\nno closing delimiter")
    with pytest.raises(ValueError):
        recall.recall("quasar", tmp_path)


def test_empty_existing_store_and_legacy_markdown_are_valid(tmp_path):
    assert recall.recall("quasar", tmp_path) == []
    write_memory(tmp_path)
    assert recall.recall("quasar", tmp_path)[0][1]["name"] == "context"


def test_unrounded_scores_are_reproducible_across_hash_seeds(tmp_path):
    terms = " ".join(f"token{i}" for i in range(60))
    for i in range(12):
        write_memory(tmp_path, f"{i:02}.md", (terms[:40+i*17] * (i+1)).encode())
    code = (
        "import json,sys; from pathlib import Path; from scripts import recall; "
        "print(json.dumps([(s,d['name']) for s,d in recall.recall(sys.argv[2],Path(sys.argv[1]),20)]))"
    )
    outputs = []
    for seed in ("1", "7", "23"):
        result = subprocess.run([sys.executable, "-c", code, str(tmp_path), terms],
                                cwd=Path(__file__).resolve().parents[1],
                                env={**os.environ, "PYTHONHASHSEED": seed},
                                capture_output=True, text=True, timeout=20, check=True)
        outputs.append(result.stdout)
    assert len(set(outputs)) == 1


def test_equal_scores_have_explicit_path_tiebreak(tmp_path):
    write_memory(tmp_path, "b.md")
    write_memory(tmp_path, "a.md")
    docs = recall._load(tmp_path)
    assert [(s, d["path"]) for s, d in recall._score_docs("quasar", docs)] == [
        (s, d["path"]) for s, d in recall._score_docs("quasar", list(reversed(docs)))
    ]


def test_frozen_development_controls_pass():
    path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark-memory.py"
    spec = importlib.util.spec_from_file_location("memory_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.evaluate()
    assert report["all_passed"], report["results"]
    assert report["held_out"] is False
    assert report["scientific_accuracy_measured"] is False
