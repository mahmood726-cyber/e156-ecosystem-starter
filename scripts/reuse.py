#!/usr/bin/env python3
r"""reuse.py -- offline "copy it, don't regenerate it" index for the shared kits.

The single biggest token cost for a student on a capped plan is asking an agent
to *regenerate* code that already exists in one of the offline kits. A forest
plot, a funnel plot, an AACT loader -- these are already written, tested, and
free to run. Regenerating one costs thousands of tokens; copying it costs zero.

This tool builds (offline, no LLM) a searchable index of every reusable symbol
(function / class / method) in the kits the starter installs, and lets you query
it by keyword to get the EXACT thing to copy -- its signature, one-line doc, and
source location -- so you never pay an agent to re-derive it.

    reuse.py build                      # (re)build reuse-index.json from kit roots
    reuse.py find "forest plot"         # what already exists for this?
    reuse.py find "aact loader" --plain # human-friendly terminal output
    reuse.py find "funnel" --json       # machine-readable

Two subcommands:

  build   Walk the configured kit roots, extract public symbols (Python via the
          stdlib `ast` module -- parsed, never executed; JavaScript via bounded
          regex), and write `reuse-index.json`. Paths in the index are stored
          RELATIVE to each kit root (plus the kit name), never absolute, so the
          committed index is portable across machines.

  find    Search the committed index offline and print ranked matches. No
          network, no LLM, no kit checkout required -- the index ships pre-baked.

Kit roots are resolved (first source that yields any existing dir wins):
  1. --roots "name=path,name=path"            (explicit override)
  2. $REUSE_ROOTS  (same "name=path" CSV, or os.pathsep-separated bare paths)
  3. scripts/reuse-roots.txt   (one "name=path" per line; '#' comments ok)
  4. built-in defaults for the known kits (skipped silently if absent)

A missing root is skipped, not fatal -- you can build an index from whatever
kits are present on this machine.

Exit codes:
  0  success (build wrote an index / find printed matches)
  1  find: no matches above threshold
  2  no index to search (run `reuse.py build`) / build: no roots found
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX = SCRIPT_DIR / "reuse-index.json"
ROOTS_FILE = SCRIPT_DIR / "reuse-roots.txt"

SCHEMA_VERSION = 1

# Directories never worth indexing. `vendor` holds bundled third-party libraries
# (plotly, etc.) -- those are not OUR reusable code, and indexing their minified
# bundles produces thousands of garbage symbols.
SKIP_DIRS = frozenset((
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    "site-packages", ".pytest_cache", ".tox", ".mypy_cache", "tests", "test",
    "vendor",
))

# A minified/generated bundle (e.g. *.min.js) is third-party noise, not authored
# kit code. Two cheap tells: the conventional `.min.` infix, or any single line
# longer than this (hand-written source virtually never has 1000-char lines).
_MINIFIED_MAX_LINE = 1000

# Built-in default kit roots. Each is tried at a few conventional locations; the
# first that exists is used, and any that resolve to nothing are silently skipped
# (a student may have installed only some layers). NO single drive is hardcoded
# as the sole candidate -- home-relative and both common Windows drives are tried.
_HOME = Path.home()
DEFAULT_KIT_CANDIDATES: dict[str, tuple[Path, ...]] = {
    "e156-chart-kit": (
        _HOME / "code" / "e156" / "flagship" / "kit",
        Path("C:/Projects/e156/flagship/kit"),
        SCRIPT_DIR.parent / "templates" / "e156-capsule",
    ),
    "e156-capsule": (
        SCRIPT_DIR.parent / "templates" / "e156-capsule",
    ),
    "aact-kit": (
        _HOME / "code" / "aact-kit" / "src",
        Path("C:/Projects/aact-kit/src"),
    ),
    "rapidmeta-kit": (
        _HOME / "code" / "rapidmeta-kit",
        Path("C:/Projects/rapidmeta-kit"),
    ),
}


# --- Symbol model -----------------------------------------------------------


@dataclass
class Symbol:
    kit: str
    name: str
    kind: str          # "function" | "class" | "method"
    lang: str          # "py" | "js"
    relpath: str       # path RELATIVE to the kit root (portable)
    line: int
    signature: str
    doc: str           # first line of docstring / nearby comment
    public: bool


# --- Root resolution --------------------------------------------------------


def _parse_roots_spec(spec: str) -> list[tuple[str, Path]]:
    """Parse a 'name=path,name=path' CSV (or os.pathsep bare paths) into pairs.

    Bare paths (no '=') are named by their final path component.
    """
    out: list[tuple[str, Path]] = []
    # Allow either commas or the platform path separator between entries.
    raw_parts: list[str] = []
    for chunk in spec.split(os.pathsep):
        raw_parts.extend(chunk.split(","))
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, _, path_str = part.partition("=")
            name, path_str = name.strip(), path_str.strip()
        else:
            path_str = part
            name = Path(path_str).name
        out.append((name, Path(path_str).expanduser()))
    return out


def _load_roots_file(path: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.extend(_parse_roots_spec(line))
    return out


def resolve_roots(explicit: str | None) -> list[tuple[str, Path]]:
    """Return [(kit_name, existing_dir)] from the first source that yields dirs.

    An EXPLICIT `--roots` override is authoritative: it never falls through to
    the defaults (a student who names a root and mistypes it should get a clear
    "no roots found", not a silent scan of unrelated kits). The env / roots-file
    / built-in-defaults chain uses first-source-that-yields-an-existing-dir.
    """
    def _existing_dedup(pairs: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
        seen: set[str] = set()
        out: list[tuple[str, Path]] = []
        for name, p in pairs:
            if not p.is_dir():
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((name, p))
        return out

    if explicit:
        return _existing_dedup(_parse_roots_spec(explicit))

    sources: list[list[tuple[str, Path]]] = []
    env = os.environ.get("REUSE_ROOTS")
    if env:
        sources.append(_parse_roots_spec(env))
    if ROOTS_FILE.exists():
        sources.append(_load_roots_file(ROOTS_FILE))
    # Built-in defaults: pick the first existing candidate per kit.
    defaults: list[tuple[str, Path]] = []
    for name, candidates in DEFAULT_KIT_CANDIDATES.items():
        for cand in candidates:
            if cand.is_dir():
                defaults.append((name, cand))
                break
    sources.append(defaults)

    for source in sources:
        existing = _existing_dedup(source)
        if existing:
            return existing
    return []


# --- Extraction: Python (AST, never executed) -------------------------------


def _py_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    # ast.unparse (3.9+) reproduces the full arg spec including defaults and
    # annotations -- the API surface a student needs to call the symbol.
    try:
        return f"{node.name}({ast.unparse(node.args)})"
    except Exception:
        return f"{node.name}(...)"


def _first_doc_line(doc: str | None) -> str:
    if not doc:
        return ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def extract_python(kit: str, root: Path, path: Path) -> list[Symbol]:
    """Parse one .py file and return its public top-level symbols + methods."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError):
        return []
    rel = path.relative_to(root).as_posix()
    out: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Symbol(
                kit=kit, name=node.name, kind="function", lang="py", relpath=rel,
                line=node.lineno, signature=_py_signature(node),
                doc=_first_doc_line(ast.get_docstring(node)),
                public=not node.name.startswith("_"),
            ))
        elif isinstance(node, ast.ClassDef):
            out.append(Symbol(
                kit=kit, name=node.name, kind="class", lang="py", relpath=rel,
                line=node.lineno, signature=f"class {node.name}",
                doc=_first_doc_line(ast.get_docstring(node)),
                public=not node.name.startswith("_"),
            ))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if sub.name.startswith("_") and sub.name != "__init__":
                        continue
                    out.append(Symbol(
                        kit=kit, name=f"{node.name}.{sub.name}", kind="method",
                        lang="py", relpath=rel, line=sub.lineno,
                        signature=_py_signature(sub),
                        doc=_first_doc_line(ast.get_docstring(sub)),
                        public=not sub.name.startswith("_") or sub.name == "__init__",
                    ))
    return out


# --- Extraction: JavaScript (bounded regex, no parser in stdlib) ------------

# `function name(args)` and `const name = (args) =>` and `name: function(args)`.
# Bounded character classes only (no nested quantifiers) -> ReDoS-safe.
_JS_FUNC_RE = re.compile(
    r"\bfunction\s+([A-Za-z_$][\w$]{0,80})\s*\(([^)]{0,400})\)"
)
_JS_ARROW_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]{0,80})\s*=\s*\(([^)]{0,400})\)\s*=>"
)
_JS_METHOD_RE = re.compile(
    r"\b([A-Za-z_$][\w$]{0,80})\s*:\s*function\s*\(([^)]{0,400})\)"
)


def _js_doc_above(lines: list[str], def_index: int) -> str:
    """Nearest meaningful comment line in the up-to-8 lines above a def."""
    for i in range(def_index - 1, max(-1, def_index - 9), -1):
        raw = lines[i].strip()
        if not raw:
            continue
        stripped = raw.lstrip("/*").rstrip("*/").strip()
        if raw.startswith(("/*", "*", "//")) and stripped:
            return stripped[:200]
        # A non-comment, non-blank line ends the comment block scan.
        if not raw.startswith(("/*", "*", "//")):
            break
    return ""


def extract_js(kit: str, root: Path, path: Path) -> list[Symbol]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rel = path.relative_to(root).as_posix()
    lines = source.splitlines()
    out: list[Symbol] = []
    seen: set[tuple[str, int]] = set()
    for lineno, line in enumerate(lines, 1):
        for regex, kind in ((_JS_FUNC_RE, "function"),
                            (_JS_ARROW_RE, "function"),
                            (_JS_METHOD_RE, "method")):
            for m in regex.finditer(line):
                name, raw_args = m.group(1), m.group(2)
                if (name, lineno) in seen:
                    continue
                seen.add((name, lineno))
                args = ", ".join(a.strip() for a in raw_args.split(",") if a.strip())
                out.append(Symbol(
                    kit=kit, name=name, kind=kind, lang="js", relpath=rel,
                    line=lineno, signature=f"{name}({args})",
                    doc=_js_doc_above(lines, lineno - 1),
                    public=not name.startswith("_"),
                ))
    return out


# --- Build ------------------------------------------------------------------


def _is_minified(path: Path) -> bool:
    """True for *.min.js or any file with an implausibly long line (a bundle)."""
    if ".min." in path.name.lower():
        return True
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if len(line) > _MINIFIED_MAX_LINE:
                    return True
    except OSError:
        return True
    return False


def _iter_source_files(root: Path) -> Iterable[Path]:
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if Path(fname).suffix.lower() not in (".py", ".js"):
                continue
            path = Path(cur) / fname
            if path.suffix.lower() == ".js" and _is_minified(path):
                continue
            yield path


def build_index(roots: list[tuple[str, Path]]) -> dict:
    symbols: list[Symbol] = []
    for kit, root in roots:
        for path in _iter_source_files(root):
            if path.suffix.lower() == ".py":
                symbols.extend(extract_python(kit, root, path))
            else:
                symbols.extend(extract_js(kit, root, path))
    # Deterministic ordering: kit, relpath, line.
    symbols.sort(key=lambda s: (s.kit, s.relpath, s.line, s.name))
    return {
        "schema": SCHEMA_VERSION,
        # kit NAMES only -- never persist absolute build-machine paths.
        "kits": sorted({kit for kit, _ in roots}),
        "symbol_count": len(symbols),
        "symbols": [asdict(s) for s in symbols],
    }


# --- Find -------------------------------------------------------------------


def tokenize(query: str) -> list[str]:
    return [t for t in re.split(r"\W+", query.lower()) if t]


@dataclass
class Hit:
    symbol: dict
    score: int = 0
    matched: list[str] = field(default_factory=list)


def score_symbol(sym: dict, phrase: str, tokens: list[str]) -> Hit:
    name = (sym.get("name") or "").lower()
    doc = (sym.get("doc") or "").lower()
    kit = (sym.get("kit") or "").lower()
    sig = (sym.get("signature") or "").lower()
    score = 0
    matched: list[str] = []
    if phrase and phrase in name:
        score += 6
        matched.append("name(phrase)")
    for tok in tokens:
        if tok in name:
            score += 3
            matched.append(f"name:{tok}")
        if tok in doc:
            score += 1
        if tok in sig:
            score += 1
        if tok in kit:
            score += 1
    if score and sym.get("public"):
        score += 1
    return Hit(symbol=sym, score=score, matched=matched)


def find(index: dict, query: str, top: int, min_score: int) -> list[Hit]:
    phrase = query.lower().strip()
    tokens = tokenize(query)
    hits = [score_symbol(s, phrase, tokens) for s in index.get("symbols", [])]
    ranked = sorted(
        [h for h in hits if h.score >= min_score],
        key=lambda h: (-h.score, not h.symbol.get("public"),
                       h.symbol.get("kit", ""), h.symbol.get("name", "")),
    )
    return ranked[:top]


# --- Rendering --------------------------------------------------------------

_INSTALL_HINT = {
    "e156-chart-kit": "install-e156-capsules",
    "e156-capsule": "install-e156-capsules",
    "aact-kit": "install-aact-kit",
    "rapidmeta-kit": "install-rapidmeta",
}


def _reuse_line(sym: dict) -> str:
    kit = sym.get("kit", "")
    hint = _INSTALL_HINT.get(kit)
    where = f"{kit}/{sym.get('relpath','')}:{sym.get('line','')}"
    if hint:
        return f"copy from {where}  (get it: {hint}) -- don't regenerate"
    return f"copy from {where} -- don't regenerate"


def render(hits: list[Hit], query: str, plain: bool) -> str:
    if not hits:
        return ""
    header_note = ("These already exist in the offline kits -- copy/import them "
                   "instead of asking an agent to regenerate (that costs tokens).")
    if plain:
        bold = "\033[1m"; dim = "\033[2m"; rst = "\033[0m"
        out = [f"{bold}Reusable matches for \"{query}\"{rst}", f"{dim}{header_note}{rst}", ""]
        for i, h in enumerate(hits, 1):
            s = h.symbol
            tags = " | ".join(filter(None, [s.get("kit"), s.get("lang"),
                                            "public" if s.get("public") else "internal"]))
            out.append(f"{bold}{i}. {s.get('name')}{rst}  [{tags}]")
            out.append(f"   signature: {s.get('signature')}")
            if s.get("doc"):
                out.append(f"   doc:       {s.get('doc')}")
            out.append(f"   source:    {s.get('kit')}/{s.get('relpath')}:{s.get('line')}")
            out.append(f"   reuse:     {_reuse_line(s)}")
            out.append("")
        return "\n".join(out)
    out = [f"## Reusable matches for \"{query}\"", f"_{header_note}_", ""]
    for i, h in enumerate(hits, 1):
        s = h.symbol
        tags = " | ".join(filter(None, [s.get("kit"), s.get("lang"),
                                        "public" if s.get("public") else "internal"]))
        bits = [f"### {i}. `{s.get('name')}`  _[{tags}]_",
                f"  signature: `{s.get('signature')}`"]
        if s.get("doc"):
            bits.append(f"  doc: {s.get('doc')}")
        bits.append(f"  source: `{s.get('kit')}/{s.get('relpath')}:{s.get('line')}`")
        bits.append(f"  reuse: {_reuse_line(s)}")
        out.append("\n".join(bits))
        out.append("")
    return "\n".join(out)


# --- CLI --------------------------------------------------------------------


def _cmd_build(args: argparse.Namespace) -> int:
    roots = resolve_roots(args.roots)
    if not roots:
        print("ERROR: no kit roots found. Set $REUSE_ROOTS, pass --roots "
              "\"name=path\", create scripts/reuse-roots.txt, or install a kit "
              "layer (e.g. install-e156-capsules).", file=sys.stderr)
        return 2
    index = build_index(roots)
    out_path = Path(args.out).expanduser() if args.out else DEFAULT_INDEX
    out_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    kits = ", ".join(index["kits"])
    print(f"wrote {index['symbol_count']} symbols from {len(roots)} kit root(s) "
          f"[{kits}] -> {out_path}")
    return 0


def _cmd_find(args: argparse.Namespace) -> int:
    index_path = Path(args.index).expanduser() if args.index else DEFAULT_INDEX
    if not index_path.exists():
        print(f"ERROR: no index at {index_path}. Run `reuse.py build` first.",
              file=sys.stderr)
        return 2
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read index {index_path}: {e}", file=sys.stderr)
        return 2
    query = " ".join(args.query)
    hits = find(index, query, top=args.top, min_score=args.min_score)
    if args.json:
        print(json.dumps([{"score": h.score, **h.symbol} for h in hits], indent=2,
                         ensure_ascii=False))
        return 0 if hits else 1
    if not hits:
        print(f"No reusable symbol matches \"{query}\" in {index_path} "
              f"({index.get('symbol_count', 0)} indexed, threshold={args.min_score}).",
              file=sys.stderr)
        return 1
    print(render(hits, query, plain=args.plain))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="reuse.py", description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="(re)build the reuse index from kit roots")
    b.add_argument("--roots", help='"name=path,name=path" override of kit roots')
    b.add_argument("--out", help=f"index output path (default: {DEFAULT_INDEX.name})")
    b.set_defaults(func=_cmd_build)

    f = sub.add_parser("find", help="search the index for something to reuse")
    f.add_argument("query", nargs="+", help="keyword(s), e.g. \"forest plot\"")
    f.add_argument("--top", type=int, default=8, help="max matches (default 8)")
    f.add_argument("--min-score", type=int, default=1, help="drop hits below this")
    f.add_argument("--index", help="index path (default: reuse-index.json)")
    f.add_argument("--plain", action="store_true",
                   help="terminal-friendly output (default: markdown for agents)")
    f.add_argument("--json", action="store_true", help="machine-readable JSON")
    f.set_defaults(func=_cmd_find)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
