#!/usr/bin/env python3
"""recall.py — offline semantic-ish retrieval over a file-based memory store.

The memory store is a directory of Markdown files, each with YAML frontmatter
(`name`, `description`) plus a body, indexed by a flat `MEMORY.md`. That flat
index is loaded whole each session — fine at tens of memories, but it dilutes
and eventually won't fit as the store grows into the hundreds. This tool is the
mitigation: given a query, it ranks the memory files by relevance (Okapi BM25)
and returns the top-K, so retrieval can replace whole-index loading before the
index breaks.

Design constraints (match the ecosystem ethos):
  - Pure Python stdlib. No embeddings API, no network, no heavy deps. Runs
    offline and deterministically. BM25 is lexical, not neural — a big step up
    from dumping the flat index, and zero-infra. Swapping in sentence-transformer
    or Letta/Zep embeddings later is a drop-in upgrade to `_score_docs`.
  - The Markdown files remain the single source of truth. This builds no
    persistent index; it reads the dir each run (fast at this scale).

Usage:
  python recall.py "ed25519 signing provenance"            # top-K for a query
  python recall.py "overmind nightly" -k 3 --memory-dir D  # custom dir / K
  python recall.py "sentinel hook" --json                  # machine-readable
  python recall.py --health                                # index-size report
  python recall.py --health --json                         # machine-readable health
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from collections import Counter
from pathlib import Path


def _encode_project_dir(path: Path) -> str:
    """Encode a project cwd the way Claude Code names its projects/ subdir:
    EACH path separator and the drive colon becomes one '-'. Consecutive
    separators are NOT collapsed -- a Windows ``C:\\Users\\x`` cwd has both the
    colon and the backslash replaced, giving ``C--Users-x`` (two dashes)."""
    return re.sub(r"[:\\/]", "-", str(path))


ORIGIN_FILE = ".e156-project-origin.json"
ORIGIN_SCHEMA = "e156-memory-origin-v1"


def _project_identity(project: Path) -> str:
    resolved = project.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("project must be an existing directory")
    return hashlib.sha256(os.path.normcase(str(resolved)).encode("utf-8")).hexdigest()


def bind_memory_dir(memory_dir: Path, project: Path) -> dict:
    """Record operator-checked ownership, never inferred from a lossy name.

    This does not inspect historical ownership or make mixed content safe.
    Existing bindings are immutable through this command.
    """
    memory_dir = memory_dir.expanduser().resolve(strict=True)
    identity = _project_identity(project)
    _read_corpus(memory_dir)
    record = {"schema": ORIGIN_SCHEMA, "project_sha256": identity}
    with (memory_dir / ORIGIN_FILE).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _unique_origin(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate origin field")
        result[key] = value
    return result


def discover_memory_dir() -> Path | None:
    """Locate only this project's store, unless explicitly overridden.

    Claude Code stores per-project memory at
    ``~/.claude/projects/<encoded-cwd>/memory/``. We never hardcode a specific
    user's path (the dir name embeds the username, so a literal default leaks it
    and never resolves for anyone else). Resolution order:
      1. ``$CLAUDE_MEMORY_DIR`` if set (explicit override).
      2. a matching encoded directory with an operator-verified canonical
         project binding; the encoded name alone is ambiguous.
    Never borrow a sole or recently modified store from another project.
    Returns ``None`` without an exact match; use ``--memory-dir`` or the
    environment override for intentional cross-project recall.
    """
    env = os.environ.get("CLAUDE_MEMORY_DIR")
    if env:
        return Path(env).expanduser()
    projects = Path.home() / ".claude" / "projects"
    project = Path.cwd()
    encoded = _encode_project_dir(project)
    candidate = projects / encoded / "memory"
    try:
        # Refuse redirects and unverifiable/malformed origin records before
        # reading any memory contents. Explicit paths remain an operator choice.
        if not candidate.is_dir() or candidate.resolve(strict=True) != candidate:
            return None
        origin = candidate / ORIGIN_FILE
        if not origin.is_file() or origin.resolve(strict=True) != origin:
            return None
        record = json.loads(origin.read_text(encoding="utf-8"), object_pairs_hook=_unique_origin)
        expected = {"schema": ORIGIN_SCHEMA, "project_sha256": _project_identity(project)}
        return candidate if record == expected else None
    except (OSError, ValueError, RuntimeError):
        return None

# Recommend switching from flat-index loading to retrieval past this many
# memories — the point where the index stops being cheap to reason over whole.
INDEX_SOFT_LIMIT = 60

_STOP = frozenset(
    "a an the and or of to in for on with is are be by as at from this that it "
    "into via not no key set use used uses using than then so if when each per "
    "you your our my his her its their them they we i".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")

# BM25 hyperparameters (standard Okapi defaults).
_K1 = 1.5
_B = 0.75
# How many extra times a frontmatter `description` term is counted vs body —
# the description is the human-curated relevance hook, so weight it.
_DESC_WEIGHT = 3


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in _STOP]


class MemoryStoreError(ValueError):
    """The requested corpus cannot be read completely and safely."""


def _parse(path: Path, data: bytes | None = None) -> dict:
    """Parse one memory; its hash identifies bytes, not evidential validity."""
    if data is None:
        data = path.read_bytes()
    # Accept legacy UTF-8 BOMs but hash the actual bytes including the BOM.
    raw = data.decode("utf-8-sig").replace("\r\n", "\n")
    name, desc = path.stem, ""
    body = raw
    lines = raw.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            raise MemoryStoreError(f"unclosed frontmatter: {path.name}")
        body = "".join(lines[end + 1:])
        for line in lines[1:end]:
            m = re.match(r"\s*(name|description)\s*:\s*(.*)", line)
            if m:
                val = m.group(2).strip().strip('"').strip("'")
                if m.group(1) == "name":
                    name = val or name
                else:
                    desc = val
    # Description terms counted _DESC_WEIGHT times (boost the curated hook).
    tokens = _tokenize(body) + _tokenize(desc) * _DESC_WEIGHT
    return {"name": name, "description": desc, "path": path, "tokens": tokens,
            "sha256": hashlib.sha256(data).hexdigest(),
            "evidence_status": "unverified_memory"}


def _read_corpus(memory_dir: Path) -> tuple[list[dict], int]:
    """Read every flat Markdown entry or refuse; never return partial success.

    Resolve links before opening and require regular files inside the selected
    store. This is a local consistency check, not an adversarial filesystem
    sandbox or a transactional snapshot of concurrent writes.
    """
    try:
        root = memory_dir.expanduser().resolve(strict=True)
        if not stat.S_ISDIR(root.stat().st_mode):
            raise MemoryStoreError("memory store is not a directory")
        docs, index_lines = [], 0
        # glob may suppress scan errors on some Python versions. iterdir
        # exposes them so unreadable and empty stores stay distinct.
        for path in sorted(root.iterdir()):
            if path.suffix.lower() != ".md":
                continue
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise MemoryStoreError(f"memory entry resolves outside store: {path.name}")
            if not stat.S_ISREG(resolved.stat().st_mode):
                raise MemoryStoreError(f"memory entry is not a regular file: {path.name}")
            data = path.read_bytes()
            if path.name.lower() == "memory.md":
                index_lines += len(data.decode("utf-8-sig").splitlines())
            else:
                docs.append(_parse(path, data))
        return docs, index_lines
    except (OSError, UnicodeError, RuntimeError) as exc:
        raise MemoryStoreError(f"cannot read complete memory store ({type(exc).__name__})") from exc


def _load(memory_dir: Path) -> list[dict]:
    return _read_corpus(memory_dir)[0]


def _score_docs(query: str, docs: list[dict]) -> list[tuple[float, dict]]:
    """Okapi BM25. Returns (score, doc) sorted desc; score 0 for no overlap."""
    q_terms = sorted(set(_tokenize(query)))
    n = len(docs)
    if not q_terms or n == 0:
        return [(0.0, d) for d in docs]
    tfs = [Counter(d["tokens"]) for d in docs]
    lengths = [sum(tf.values()) for tf in tfs]
    avgdl = (sum(lengths) / n) or 1.0
    # df per query term
    df = {t: sum(1 for tf in tfs if t in tf) for t in q_terms}
    scored = []
    for d, tf, dl in zip(docs, tfs, lengths):
        s = 0.0
        for t in q_terms:
            f = tf.get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * (f * (_K1 + 1)) / (f + _K1 * (1 - _B + _B * dl / avgdl))
        scored.append((s, d))
    scored.sort(key=lambda x: (-x[0], str(x[1]["path"])))
    return scored


def recall(query: str, memory_dir: Path, k: int = 5) -> list[tuple[float, dict]]:
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    docs = _load(memory_dir)
    return [(s, d) for s, d in _score_docs(query, docs) if s > 0][:k]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline BM25 recall over file-based memory.")
    ap.add_argument("query", nargs="?", default="", help="search query")
    ap.add_argument("-k", type=int, default=5, help="max results (default 5)")
    ap.add_argument("--memory-dir", type=Path, default=None,
                    help="memory dir (default: exact current-project store only, "
                         "or set $CLAUDE_MEMORY_DIR)")
    ap.add_argument("--health", action="store_true", help="report index size and exit")
    ap.add_argument("--bind-project", type=Path,
                    help="bind an explicitly verified --memory-dir to its project; refuses replacement")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON (for agent/programmatic consumption)")
    args = ap.parse_args(argv)

    # Guard -k: a negative value would hit Python's `[:k]` slice and silently
    # DROP the last |k| results instead of erroring — a footgun for a caller who
    # fat-fingers the flag. Require a positive count.
    if args.k < 1:
        ap.error(f"-k must be >= 1 (got {args.k})")

    # Windows cp1252 stdout crashes/garbles on the em-dashes in descriptions
    # (lessons.md "Windows cp1252"). Force UTF-8 so output is faithful.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    def _emit_error(msg: str) -> int:
        # A programmatic consumer (--json) always gets JSON, even on failure,
        # so it never has to parse a stderr string. Humans get the message.
        if args.json:
            print(json.dumps({"error": msg}, ensure_ascii=False))
        else:
            print(f"[recall] {msg}", file=sys.stderr)
        return 2

    if args.bind_project is not None:
        if args.memory_dir is None or args.query.strip() or args.health:
            return _emit_error("--bind-project requires --memory-dir and no query/--health")
        try:
            record = bind_memory_dir(args.memory_dir, args.bind_project)
        except (OSError, ValueError, RuntimeError) as exc:
            return _emit_error(f"cannot bind project memory ({type(exc).__name__})")
        print(json.dumps({"status": "BOUND_BY_OPERATOR", **record}))
        return 0

    try:
        memory_dir = args.memory_dir or discover_memory_dir()
    except (OSError, RuntimeError) as exc:
        return _emit_error(f"cannot locate project memory ({type(exc).__name__})")
    if memory_dir is None:
        return _emit_error(
            "could not verify this project's Claude Code memory ownership. "
            "Pass --memory-dir <path> or set $CLAUDE_MEMORY_DIR after checking the store; "
            "use --memory-dir <path> --bind-project <project> to enable automatic discovery.")
    try:
        docs, idx_lines = _read_corpus(memory_dir)
    except MemoryStoreError as exc:
        return _emit_error(str(exc))
    if args.health:
        over_limit = len(docs) > INDEX_SOFT_LIMIT
        if args.json:
            print(json.dumps({
                "memory_dir": str(memory_dir),
                "memories": len(docs),
                "index_lines": idx_lines,
                "soft_limit": INDEX_SOFT_LIMIT,
                "over_soft_limit": over_limit,
            }, ensure_ascii=False))
            return 0
        print(f"memories: {len(docs)}  |  MEMORY.md lines: {idx_lines}")
        if over_limit:
            print(f"[recommend] {len(docs)} > {INDEX_SOFT_LIMIT}: prefer `recall.py <task>` "
                  f"over loading the whole flat index.")
        else:
            print(f"[ok] under the {INDEX_SOFT_LIMIT}-memory soft limit; flat index still cheap.")
        return 0

    if not args.query.strip():
        ap.error("a query is required unless --health is given")
    hits = [(s, d) for s, d in _score_docs(args.query, docs) if s > 0][:args.k]
    if args.json:
        print(json.dumps({
            "query": args.query,
            "memory_dir": str(memory_dir),
            "count": len(hits),
            "hits": [
                {
                    "score": round(score, 4),
                    "name": d["name"],
                    "description": d["description"],
                    "path": str(d["path"]),
                    "sha256": d["sha256"],
                    "evidence_status": d["evidence_status"],
                }
                for score, d in hits
            ],
        }, ensure_ascii=False))
        return 0
    if not hits:
        print("(no relevant memories)")
        return 0
    print("[context only] Unverified memory; recheck the source before using any claim.")
    for score, d in hits:
        print(f"{score:6.2f}  {d['name']}")
        if d["description"]:
            print(f"        {d['description']}")
        print(f"        {d['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
