"""Synthetic project-identity controls; never read the user's memory."""
import json
import os
from pathlib import Path

import pytest

from scripts import recall


def layout(tmp_path, monkeypatch):
    first = tmp_path / "work" / "trial-a"
    second = tmp_path / "work" / "trial" / "a"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    store = tmp_path / ".claude" / "projects" / recall._encode_project_dir(first) / "memory"
    store.mkdir(parents=True)
    (store / "context.md").write_text("quasar context", encoding="utf-8")
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: first)
    return first, second, store


def test_ambiguous_unbound_store_is_not_discovered(tmp_path, monkeypatch):
    first, second, store = layout(tmp_path, monkeypatch)
    assert recall._encode_project_dir(first) == recall._encode_project_dir(second)
    assert recall.discover_memory_dir() is None
    monkeypatch.setattr(Path, "cwd", lambda: second)
    assert recall.discover_memory_dir() is None


def test_bound_store_is_discovered_only_for_its_canonical_owner(tmp_path, monkeypatch):
    first, second, store = layout(tmp_path, monkeypatch)
    recall.bind_memory_dir(store, first)
    assert recall.discover_memory_dir() == store
    monkeypatch.setattr(Path, "cwd", lambda: second)
    assert recall.discover_memory_dir() is None


def test_binding_never_overwrites_an_existing_claim(tmp_path, monkeypatch):
    first, second, store = layout(tmp_path, monkeypatch)
    recall.bind_memory_dir(store, first)
    before = (store / recall.ORIGIN_FILE).read_bytes()
    with pytest.raises((ValueError, FileExistsError)):
        recall.bind_memory_dir(store, second)
    assert (store / recall.ORIGIN_FILE).read_bytes() == before


@pytest.mark.parametrize("content", [b"{}", b"[]", b"null", b"\xff", b"{} trailing",
    b'{"schema":"e156-memory-origin-v1","project_sha256":"a","project_sha256":"b"}'])
def test_invalid_origin_refuses_discovery(tmp_path, monkeypatch, content):
    _, _, store = layout(tmp_path, monkeypatch)
    (store / recall.ORIGIN_FILE).write_bytes(content)
    assert recall.discover_memory_dir() is None


def test_non_directory_project_cannot_bind(tmp_path, monkeypatch):
    _, _, store = layout(tmp_path, monkeypatch)
    with pytest.raises((ValueError, OSError)):
        recall.bind_memory_dir(store, tmp_path / "missing")
    assert not (store / recall.ORIGIN_FILE).exists()


def test_binding_checks_store_before_writing(tmp_path, monkeypatch):
    first, _, store = layout(tmp_path, monkeypatch)
    (store / "broken.md").write_bytes(b"\xff")
    with pytest.raises(ValueError):
        recall.bind_memory_dir(store, first)
    assert not (store / recall.ORIGIN_FILE).exists()


def test_redirected_automatic_store_is_not_selected(tmp_path, monkeypatch):
    first, _, store = layout(tmp_path, monkeypatch)
    recall.bind_memory_dir(store, first)
    original = Path.resolve
    def redirected(path, *args, **kwargs):
        return tmp_path / "elsewhere" if path == store else original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", redirected)
    assert recall.discover_memory_dir() is None


def test_binding_cli_and_default_query(tmp_path, monkeypatch, capsys):
    first, second, store = layout(tmp_path, monkeypatch)
    assert recall.main(["--memory-dir", str(store), "--bind-project", str(first), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "BOUND_BY_OPERATOR"
    assert recall.main(["quasar", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1
    monkeypatch.setattr(Path, "cwd", lambda: second)
    assert recall.main(["quasar", "--json"]) == 2
    assert "hits" not in json.loads(capsys.readouterr().out)
    assert recall.main(["quasar", "--memory-dir", str(store), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1


def test_unbound_store_remains_available_by_explicit_override(tmp_path, monkeypatch):
    _, _, store = layout(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_MEMORY_DIR", str(store))
    assert recall.discover_memory_dir() == store


def test_tilde_binding_validates_and_writes_the_same_store(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    store = home / "memory"
    store.mkdir()
    shadow = tmp_path / "~" / "memory"
    shadow.mkdir(parents=True)
    (shadow / "invalid.md").write_bytes(b"\xff")
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    recall.bind_memory_dir(Path("~") / "memory", home)
    assert (store / recall.ORIGIN_FILE).is_file()
    assert not (shadow / recall.ORIGIN_FILE).exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows short-path aliases")
def test_windows_short_path_alias_keeps_verified_owner(tmp_path, monkeypatch):
    import ctypes
    long_home = tmp_path / "long home directory for memory"
    long_home.mkdir()
    buffer = ctypes.create_unicode_buffer(32768)
    size = ctypes.windll.kernel32.GetShortPathNameW(str(long_home), buffer, len(buffer))
    assert size > 0
    short_home = Path(buffer.value)
    # A volume may disable 8.3 aliases; retain the identity check either way.
    assert short_home.samefile(long_home)
    project = short_home / "working-project"
    project.mkdir()
    store = short_home / ".claude/projects" / recall._encode_project_dir(project) / "memory"
    store.mkdir(parents=True)
    recall.bind_memory_dir(store, project)
    monkeypatch.delenv("CLAUDE_MEMORY_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: short_home)
    monkeypatch.setattr(Path, "cwd", lambda: project)
    assert recall.discover_memory_dir() == store
