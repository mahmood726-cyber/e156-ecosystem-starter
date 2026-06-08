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
  python recall.py --health                                # index-size report
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path


def _encode_project_dir(path: Path) -> str:
    """Encode a project cwd the way Claude Code names its projects/ subdir:
    EACH path separator and the drive colon becomes one '-'. Consecutive
    separators are NOT collapsed -- a Windows ``C:\\Users\\x`` cwd has both the
    colon and the backslash replaced, giving ``C--Users-x`` (two dashes)."""
    return re.sub(r"[:\\/]", "-", str(path))


def discover_memory_dir() -> Path | None:
    """Best-effort location of THIS machine's Claude Code memory dir.

    Claude Code stores per-project memory at
    ``~/.claude/projects/<encoded-cwd>/memory/``. We never hardcode a specific
    user's path (the dir name embeds the username, so a literal default leaks it
    and never resolves for anyone else). Resolution order:
      1. ``$CLAUDE_MEMORY_DIR`` if set (explicit override).
      2. the project whose encoded name matches the current working directory;
      3. the sole ``projects/*/memory`` dir if there is exactly one;
      4. otherwise the most-recently-modified ``projects/*/memory`` dir.
    Returns ``None`` if none exists (the caller then asks for ``--memory-dir``).
    """
    env = os.environ.get("CLAUDE_MEMORY_DIR")
    if env:
        return Path(env).expanduser()
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        return None
    candidates = [p for p in projects.glob("*/memory") if p.is_dir()]
    if not candidates:
        return None
    encoded = _encode_project_dir(Path.cwd())
    for c in candidates:
        if c.parent.name == encoded:
            return c
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda p: p.stat().st_mtime)

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


def _parse(path: Path) -> dict:
    """Return {name, description, tokens} for one memory file."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    name, desc = path.stem, ""
    body = raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            front, body = raw[3:end], raw[end + 4:]
            for line in front.splitlines():
                m = re.match(r"\s*(name|description)\s*:\s*(.*)", line)
                if m:
                    val = m.group(2).strip().strip('"').strip("'")
                    if m.group(1) == "name":
                        name = val or name
                    else:
                        desc = val
    # Description terms counted _DESC_WEIGHT times (boost the curated hook).
    tokens = _tokenize(body) + _tokenize(desc) * _DESC_WEIGHT
    return {"name": name, "description": desc, "path": path, "tokens": tokens}


def _load(memory_dir: Path) -> list[dict]:
    docs = []
    for p in sorted(memory_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        try:
            docs.append(_parse(p))
        except OSError:
            continue
    return docs


def _score_docs(query: str, docs: list[dict]) -> list[tuple[float, dict]]:
    """Okapi BM25. Returns (score, doc) sorted desc; score 0 for no overlap."""
    q_terms = set(_tokenize(query))
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
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def recall(query: str, memory_dir: Path, k: int = 5) -> list[tuple[float, dict]]:
    docs = _load(memory_dir)
    return [(s, d) for s, d in _score_docs(query, docs) if s > 0][:k]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline BM25 recall over file-based memory.")
    ap.add_argument("query", nargs="?", default="", help="search query")
    ap.add_argument("-k", type=int, default=5, help="max results (default 5)")
    ap.add_argument("--memory-dir", type=Path, default=None,
                    help="memory dir (default: auto-discover ~/.claude/projects/*/memory, "
                         "or set $CLAUDE_MEMORY_DIR)")
    ap.add_argument("--health", action="store_true", help="report index size and exit")
    args = ap.parse_args(argv)

    # Windows cp1252 stdout crashes/garbles on the em-dashes in descriptions
    # (lessons.md "Windows cp1252"). Force UTF-8 so output is faithful.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    memory_dir = args.memory_dir or discover_memory_dir()
    if memory_dir is None:
        print("[recall] could not locate a Claude Code memory dir under "
              "~/.claude/projects/*/memory.\n"
              "  Pass --memory-dir <path> or set $CLAUDE_MEMORY_DIR.", file=sys.stderr)
        return 2
    if not memory_dir.is_dir():
        print(f"[recall] memory dir not found: {memory_dir}", file=sys.stderr)
        return 2

    docs = _load(memory_dir)
    if args.health:
        idx = memory_dir / "MEMORY.md"
        idx_lines = len(idx.read_text(encoding="utf-8").splitlines()) if idx.exists() else 0
        print(f"memories: {len(docs)}  |  MEMORY.md lines: {idx_lines}")
        if len(docs) > INDEX_SOFT_LIMIT:
            print(f"[recommend] {len(docs)} > {INDEX_SOFT_LIMIT}: prefer `recall.py <task>` "
                  f"over loading the whole flat index.")
        else:
            print(f"[ok] under the {INDEX_SOFT_LIMIT}-memory soft limit; flat index still cheap.")
        return 0

    if not args.query.strip():
        ap.error("a query is required unless --health is given")
    hits = recall(args.query, memory_dir, args.k)
    if not hits:
        print("(no relevant memories)")
        return 0
    for score, d in hits:
        print(f"{score:6.2f}  {d['name']}")
        if d["description"]:
            print(f"        {d['description']}")
        print(f"        {d['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
