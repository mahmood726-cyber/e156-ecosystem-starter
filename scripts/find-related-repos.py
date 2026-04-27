#!/usr/bin/env python3
r"""find-related-repos.py -- "before any new project" portfolio recon.

Given a topic / keyword, scan the user's portfolio index for prior work
and surface the top N matches with README excerpts and code hits, so an
agent (or you) can decide what to reuse vs build from scratch.

Index source priority (first one that exists wins):
  1. --manifest <path>                          (explicit override)
  2. $PROJECTINDEX_MANIFEST                     (env override)
  3. ~/code/ProjectIndex/agent-records/restart-manifest.json   (student layout)
  4. C:/ProjectIndex/agent-records/restart-manifest.json       (Mahmood layout)
  5. ~/code/ProjectIndex/INDEX.md               (fallback: parse H3 headings)
  6. C:/ProjectIndex/INDEX.md                   (fallback)

If none exists, exits 2 with a clear message about how to create one
(install-projectindex.sh seeds INDEX.md; restart-manifest.json comes from
the agent-records pipeline).

Scoring (per project):
  +10  exact phrase in name (case-insensitive)
  +5   exact phrase in workbook.title or INDEX H3 heading
  +3   exact phrase in restart.resumeSummary (manifest only)
  +2   per query token found in name
  +1   per query token found in workbook.title / heading
  +1   per query token found in resumeSummary
Hits with score 0 are dropped.

For each top-N hit (default N=5):
  - Read README.md (first 30 lines, query-line-highlighted)
  - Grep for query terms in *.py / *.md / *.html (first 3 file:line hits)

Usage:
    find-related-repos.py "sglt2 hfpef"
    find-related-repos.py "fragility index meta-analysis" --top 8
    find-related-repos.py "transportability" --no-code      # readme only
    find-related-repos.py "atlas" --names-only              # bare list

Exit codes:
  0  matches found and printed
  1  no matches above score threshold
  2  no index source available

Written for use by an agent: output is human + agent friendly markdown.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# --- Index loading ----------------------------------------------------------


@dataclass
class Project:
    """A normalized record from any of the supported index formats."""
    name: str
    path: Path | None = None
    title: str = ""           # workbook title or INDEX heading
    summary: str = ""         # restart.resumeSummary (manifest only)
    status: str = ""
    tier: str = ""
    remote: str = ""
    score: int = 0
    matched_fields: list[str] = field(default_factory=list)


def candidate_manifest_paths(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser()]
    paths: list[Path] = []
    env = os.environ.get("PROJECTINDEX_MANIFEST")
    if env:
        paths.append(Path(env).expanduser())
    home = Path.home()
    paths += [
        home / "code" / "ProjectIndex" / "agent-records" / "restart-manifest.json",
        Path("C:/ProjectIndex/agent-records/restart-manifest.json"),
        home / "code" / "ProjectIndex" / "INDEX.md",
        Path("C:/ProjectIndex/INDEX.md"),
    ]
    return paths


def load_from_manifest(path: Path) -> list[Project]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    out: list[Project] = []
    for r in data.get("records", []):
        p_str = r.get("resolvedPath") or r.get("path") or ""
        out.append(Project(
            name=r.get("name", ""),
            path=Path(p_str) if p_str else None,
            title=(r.get("workbook") or {}).get("title", ""),
            summary=(r.get("restart") or {}).get("resumeSummary", ""),
            status=r.get("status", ""),
            tier=r.get("tier", ""),
            remote=(r.get("git") or {}).get("remote", ""),
        ))
    return out


def load_from_index_md(path: Path) -> list[Project]:
    """Fallback: parse H3 headings from a free-form INDEX.md.

    Format assumption (matches Mahmood's INDEX.md): each project starts
    with `### Name`, followed by `> ` blockquote lines until the next
    H3 or H2. Path is extracted from the first `C:\\...` or `~/...`
    looking string in the body.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[Project] = []
    h3_re = re.compile(r"^### (.+)$", re.MULTILINE)
    headings = list(h3_re.finditer(text))
    for i, m in enumerate(headings):
        name = m.group(1).strip()
        body_start = m.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[body_start:body_end]
        path_match = re.search(r"`?([A-Z]:\\[^`\s]+|~/[^`\s]+|/[A-Za-z][^`\s]+)", body)
        proj_path = Path(path_match.group(1)) if path_match else None
        out.append(Project(
            name=name,
            path=proj_path,
            title=name,             # heading IS the title in this format
            summary=body[:300].strip(),
        ))
    return out


def load_index(explicit: str | None) -> tuple[list[Project], Path]:
    for candidate in candidate_manifest_paths(explicit):
        if not candidate.exists():
            continue
        if candidate.suffix == ".json":
            return load_from_manifest(candidate), candidate
        if candidate.suffix == ".md":
            return load_from_index_md(candidate), candidate
    raise FileNotFoundError(
        "No portfolio index found. Set $PROJECTINDEX_MANIFEST, pass --manifest, "
        "or run scripts/install-projectindex.sh to seed one."
    )


# --- Scoring ----------------------------------------------------------------


def tokenize(query: str) -> list[str]:
    """Split a query into lowercased word tokens, dropping empties."""
    return [t for t in re.split(r"\W+", query.lower()) if t]


def score_project(p: Project, phrase: str, tokens: list[str]) -> Project:
    fields_searched = {
        "name": (p.name or "").lower(),
        "title": (p.title or "").lower(),
        "summary": (p.summary or "").lower(),
    }
    score = 0
    matched: list[str] = []

    if phrase and phrase in fields_searched["name"]:
        score += 10
        matched.append("name(phrase)")
    if phrase and phrase in fields_searched["title"]:
        score += 5
        matched.append("title(phrase)")
    if phrase and phrase in fields_searched["summary"]:
        score += 3
        matched.append("summary(phrase)")

    if tokens:
        for tok in tokens:
            if tok in fields_searched["name"]:
                score += 2
            if tok in fields_searched["title"]:
                score += 1
            if tok in fields_searched["summary"]:
                score += 1

    p.score = score
    p.matched_fields = matched
    return p


# --- Drill-down: README excerpt + code grep --------------------------------


def readme_excerpt(repo: Path, tokens: list[str], max_lines: int = 30) -> str | None:
    """Return up to max_lines of the project's README, prefixed with `> `."""
    if not repo or not repo.exists():
        return None
    candidates = ["README.md", "Readme.md", "readme.md", "README.MD"]
    for cand in candidates:
        f = repo / cand
        if f.exists():
            break
    else:
        return None
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines]
    except OSError:
        return None
    if not lines:
        return None
    return "\n".join(f"  > {line}" for line in lines)


def code_grep(repo: Path, tokens: list[str], max_hits: int = 3) -> list[str]:
    """Return up to max_hits 'relpath:lineno  excerpt' strings."""
    if not repo or not repo.exists() or not tokens:
        return []
    pattern = re.compile("|".join(re.escape(t) for t in tokens), re.IGNORECASE)
    hits: list[str] = []
    skip_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__",
                 "dist", "build", "site-packages", ".pytest_cache"}
    extensions = {".py", ".md", ".html", ".js", ".ts", ".sh", ".ps1"}
    try:
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for fname in files:
                if Path(fname).suffix.lower() not in extensions:
                    continue
                fpath = Path(root) / fname
                # Skip the README we already excerpted
                if fname.lower() == "readme.md":
                    continue
                try:
                    with fpath.open(encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                rel = fpath.relative_to(repo).as_posix()
                                excerpt = line.strip()[:120]
                                hits.append(f"  - {rel}:{lineno}  {excerpt}")
                                if len(hits) >= max_hits:
                                    return hits
                                break  # one hit per file
                except OSError:
                    continue
    except OSError:
        pass
    return hits


# --- CLI --------------------------------------------------------------------


def render(matches: list[Project], query: str, source: Path,
           include_readme: bool, include_code: bool, names_only: bool,
           plain: bool = False) -> str:
    if names_only:
        return "\n".join(f"{p.name}\t{p.path or ''}" for p in matches)
    if plain:
        # Terminal-friendly output: no markdown decoration, ANSI for emphasis.
        bold = "\033[1m"; dim = "\033[2m"; rst = "\033[0m"
        out = [f"{bold}Top {len(matches)} portfolio matches for \"{query}\"{rst}",
               f"{dim}index source: {source}{rst}", ""]
        tokens = tokenize(query)
        for i, p in enumerate(matches, 1):
            head = f"{bold}{i}. {p.name}{rst}"
            meta = " / ".join([s for s in [p.tier, p.status] if s])
            if meta: head += f"  [{meta}]"
            out.append(head)
            if p.path:    out.append(f"   path:    {p.path}")
            if p.remote:  out.append(f"   remote:  {p.remote}")
            if p.title and p.title != p.name:
                out.append(f"   title:   {p.title}")
            if p.summary: out.append(f"   summary: {p.summary[:280]}")
            out.append(f"   score:   {p.score} ({', '.join(p.matched_fields) or 'token-only'})")
            if include_readme:
                ex = readme_excerpt(p.path, tokens) if p.path else None
                if ex:
                    out.append("   README (first 30 lines):")
                    # Reuse the "  > line" prefix from readme_excerpt, indent further
                    out.append("\n".join("  " + ln for ln in ex.splitlines()))
                elif p.path:
                    out.append("   README: not present")
            if include_code:
                hits = code_grep(p.path, tokens) if p.path else []
                if hits:
                    out.append("   code hits:")
                    out.extend("  " + h for h in hits)
            out.append("")
        return "\n".join(out)
    # Default: markdown for agents
    out = [f"## Top {len(matches)} portfolio matches for \"{query}\"",
           f"_index source: {source}_", ""]
    tokens = tokenize(query)
    for i, p in enumerate(matches, 1):
        bits = [f"### {i}. {p.name}"]
        meta = " / ".join([s for s in [p.tier, p.status] if s])
        if meta:
            bits[0] += f"  _[{meta}]_"
        if p.path:
            bits.append(f"  path: `{p.path}`")
        if p.remote:
            bits.append(f"  remote: {p.remote}")
        if p.title and p.title != p.name:
            bits.append(f"  title: {p.title}")
        if p.summary:
            bits.append(f"  summary: {p.summary[:280]}")
        bits.append(f"  score: {p.score}  ({', '.join(p.matched_fields) or 'token-only'})")
        if include_readme:
            ex = readme_excerpt(p.path, tokens) if p.path else None
            if ex:
                bits.append("\n  README (first 30 lines):")
                bits.append(ex)
            elif p.path:
                bits.append("  README: not present")
        if include_code:
            hits = code_grep(p.path, tokens) if p.path else []
            if hits:
                bits.append("\n  code hits:")
                bits.extend(hits)
        out.append("\n".join(bits))
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("query", nargs="+", help="Topic / keyword(s) to search for")
    ap.add_argument("--top", type=int, default=5, help="Max number of matches")
    ap.add_argument("--manifest", help="Explicit path to restart-manifest.json or INDEX.md")
    ap.add_argument("--no-readme", action="store_true", help="Skip README excerpt drill-down")
    ap.add_argument("--no-code", action="store_true", help="Skip code grep drill-down")
    ap.add_argument("--names-only", action="store_true", help="Bare name+path list (no formatting)")
    ap.add_argument("--plain", action="store_true",
                    help="Terminal-friendly output (ANSI), no markdown decoration. "
                         "Default output is markdown (good for agents, ugly for humans).")
    ap.add_argument("--min-score", type=int, default=1, help="Drop hits below this score")
    args = ap.parse_args()

    query = " ".join(args.query)
    phrase = query.lower().strip()
    tokens = tokenize(query)

    try:
        projects, source = load_index(args.manifest)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    scored = [score_project(p, phrase, tokens) for p in projects]
    matches = sorted(
        [p for p in scored if p.score >= args.min_score],
        key=lambda p: (-p.score, p.name.lower()),
    )[: args.top]

    if not matches:
        print(f"No matches for \"{query}\" in {source} (scored {len(scored)} projects, "
              f"threshold={args.min_score}).", file=sys.stderr)
        return 1

    print(render(
        matches, query, source,
        include_readme=not args.no_readme,
        include_code=not args.no_code,
        names_only=args.names_only,
        plain=args.plain,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
