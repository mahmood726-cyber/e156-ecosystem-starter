#!/usr/bin/env python3
"""render-gate-gaps.py -- every gate in this repo, what it STOPS, and what it would NOT stop.
Enumerated by a command, so a gate nobody wrote down is a refusal, not an omission.

WHAT IT IS. A registry, a renderer and a check.
    docs/gate-gaps.json   one entry per gate: id, kind, what it stops, what it would
                          NOT stop (a list of named gaps, never "etc."), and a SEAL --
                          the sha256 of the file(s) that implement the gate.
    docs/GATE_GAPS.md     generated from the JSON. Never hand-edit it.

WHY IT EXISTS. A green CI badge reads as "checked". It means "the checks that exist
passed", and nobody can say which checks exist, or what each one cannot see, without
reading every workflow and script. Two specific failures follow:
  - A NEW gate lands with no statement of its limits, and its green tick is read as
    covering more than it does.
  - A gate CHANGES -- a job is re-scoped, a regex narrowed -- and the old, wider
    description of what it stops is still being quoted. The seal is what catches
    this: the stated gaps were reviewed against specific bytes, and when those bytes
    move the review is void until someone looks again and re-seals.
Ported from the meta-harness gate-gap registry (registry/gate_gaps.json +
render_gate_gaps.py + gate_scorecard.py's refusal of an unaccounted gate).

WHAT --check REFUSES (exit 1)
  1. A gate found MECHANICALLY that has no entry. The enumeration is:
       - every job in .github/workflows/*.yml / *.yaml (parsed, not grepped for names);
       - every top-level scripts/*.py or scripts/*.sh that defines a `--check` or
         `--selftest` mode, that reads a Claude Code hook payload (`tool_input`), or
         that a CI job runs as `bash|python|./ scripts/<name>`.
  2. An entry whose gate no longer exists (an orphan describes nothing).
  3. A kind that contradicts the code: a job with `if: false` registered as anything
     but `declared-gap` (it runs nothing, so it stops nothing); a `declared-gap` job that
     has been re-enabled; a script that reads a Claude Code hook payload (`tool_input`)
     registered as anything but `hook`, or a plain script registered as `hook`.
  4. A seal that no longer matches -- the gate changed, so its stated gaps must be
     re-reviewed. A seal that omits the gate's own implementing artifact is refused too.
  5. docs/GATE_GAPS.md not byte-equal to what the JSON renders to.
  6. A malformed entry: unknown kind, duplicate id, empty `stops` or `would_not_stop`.
  If the workflows or the registry cannot be read or parsed, the verdict is
  INCONCLUSIVE (exit 2). "Could not enumerate" is never reported as current.

SEAL ARITHMETIC. A dependency is either a file path ("scripts/regen-hashes.sh") or a
CI job ("<workflow path>#jobs.<job id>"). A file is hashed with CRLF folded to LF, so a
Windows checkout (core.autocrlf=true) and the Linux CI runner agree on one seal. A job
is hashed as its own block of the workflow -- so editing one job re-opens that job's
review, not every job in the file. Leading/trailing blank and comment lines of a block
are not part of it.

WHAT IT DOES NOT CHECK, named rather than implied.
  - It does not check that the stated gaps are TRUE or COMPLETE. The seal proves that a
    human re-sealed after the last change; it cannot prove they re-read anything.
    `--reseal` is a claim of review, and it is visible in the diff.
  - The enumeration has a fixed scope: .github/workflows/ and top-level scripts/*.py,
    *.sh. A gate written in PowerShell, under install/ or bootstrap/, in a scripts/
    subfolder, or as a git hook installed by another tool (Sentinel's pre-push hook)
    is not enumerated, and so not refused when missing. Register those by hand.
  - A script counts as a gate only if it has a `--check`/`--selftest` mode, is a hook,
    or CI runs it directly. A checker with none of these is invisible to rule 1.
  - The workflow parser reads the block-style YAML GitHub documents. A workflow written
    in flow style (`jobs: {a: ...}`) has no parseable jobs and is INCONCLUSIVE, not
    silently empty.
  - It does not run any gate. Whether a gate CAN fail is scripts/gate-can-fail.py's
    question and a known-answer test's; this registry only says what each one covers.

OPT-IN. Nothing that already runs changes behaviour: no installer, hook or existing CI
step calls this. It is enforced only through tests/test_gate_gaps.py, which the existing
python-tests job collects. A lane opts in to keeping it current by running
`python scripts/render-gate-gaps.py --check` before opening a PR that adds or changes a
gate; see docs/GATE_GAPS.md for the add / re-seal workflow.

USAGE
    python scripts/render-gate-gaps.py --check            # verify; write nothing
    python scripts/render-gate-gaps.py                    # re-render docs/GATE_GAPS.md, then check
    python scripts/render-gate-gaps.py --reseal ID [ID]   # you RE-REVIEWED these gates' gaps:
                                                          # recompute their seals, re-render
    python scripts/render-gate-gaps.py --list             # print the mechanical enumeration
    --root DIR    operate on another checkout (tests use this)

EXIT CODES
    0  CURRENT       every enumerated gate is registered, sealed, and rendered
    1  REFUSED       at least one reason above
    2  INCONCLUSIVE  the registry or a workflow could not be read or parsed

Offline, standard library only, no API key, no model call. MIT-licensed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CURRENT, REFUSED, INCONCLUSIVE = 0, 1, 2

SCHEMA = "e156-gate-gaps-v1"
REGISTRY_PATH = "docs/gate-gaps.json"
DOC_PATH = "docs/GATE_GAPS.md"
WORKFLOW_DIR = ".github/workflows"
SCRIPTS_DIR = "scripts"

KINDS = ("ci-job", "hook", "script", "declared-gap")
KIND_TITLES = {
    "ci-job": "CI jobs (.github/workflows)",
    "hook": "Agent hooks (opt-in)",
    "script": "Check and guard scripts (scripts/)",
    "declared-gap": "Declared gaps -- present in the repo, but NOT a gate",
}

DEFAULT_ROOT = Path(__file__).resolve().parents[1]


class Inconclusive(Exception):
    """The enumeration or the registry could not be read; never a pass."""


# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _posix(path: str) -> str:
    return path.replace("\\", "/")


# --------------------------------------------------------------------------
# Mechanical enumeration -- CI jobs
# --------------------------------------------------------------------------

_JOB_HEADER = re.compile(r"^( +)([A-Za-z0-9_-]+):\s*(#.*)?$")
_IF_FALSE = re.compile(r"^\s+if:\s*(false|\$\{\{\s*false\s*\}\})\s*(#.*)?$")
_RUNS_SCRIPT = re.compile(r"(?:\b(?:bash|sh|python3?|pwsh)\s+|(?<![\w/])\./)scripts/([A-Za-z0-9_.-]+)")


def _is_filler(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def parse_workflow_jobs(text: str, rel: str) -> dict[str, dict]:
    """{job_id: {"block": str, "disabled": bool, "runs_scripts": set}} for one workflow.

    Raises Inconclusive when no `jobs:` mapping with block-style jobs is found.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if re.match(r"^jobs:\s*(#.*)?$", ln))
    except StopIteration:
        raise Inconclusive(f"{rel}: no block-style top-level `jobs:` key found")

    headers: list[tuple[int, str]] = []
    job_indent = None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if _is_filler(ln):
            continue
        if not ln.startswith(" "):  # next top-level key
            end = i
            break
        m = _JOB_HEADER.match(ln)
        if m and (job_indent is None or len(m.group(1)) == job_indent):
            if job_indent is None:
                job_indent = len(m.group(1))
            headers.append((i, m.group(2)))
    if not headers:
        raise Inconclusive(f"{rel}: `jobs:` has no block-style job entries")

    jobs: dict[str, dict] = {}
    for n, (i, job_id) in enumerate(headers):
        stop = headers[n + 1][0] if n + 1 < len(headers) else end
        block = lines[i:stop]
        while block and _is_filler(block[-1]):
            block.pop()
        body_indent = " " * (job_indent + 2)
        disabled = any(
            _IF_FALSE.match(ln) and ln.startswith(body_indent) and not ln.startswith(body_indent + " ")
            for ln in block
        )
        runs = set(_RUNS_SCRIPT.findall("\n".join(block)))
        jobs[job_id] = {"block": "\n".join(block) + "\n", "disabled": disabled, "runs_scripts": runs}
    return jobs


def _workflow_files(root: Path) -> list[Path]:
    d = root / WORKFLOW_DIR
    if not d.is_dir():
        raise Inconclusive(f"{WORKFLOW_DIR}/ not found under {root}")
    files = sorted(p for p in d.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml"))
    if not files:
        raise Inconclusive(f"{WORKFLOW_DIR}/ has no *.yml / *.yaml files")
    return files


def _all_jobs(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for wf in _workflow_files(root):
        rel = _posix(str(wf.relative_to(root)))
        try:
            text = wf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise Inconclusive(f"{rel}: unreadable ({exc})")
        for job_id, job in parse_workflow_jobs(text, rel).items():
            out[f"{rel}#jobs.{job_id}"] = job
    return out


# --------------------------------------------------------------------------
# Mechanical enumeration -- scripts
# --------------------------------------------------------------------------

_PY_MODE = re.compile(r"""["']--(?:check|selftest)["']""")
_SH_MODE = re.compile(r"^\s*--(?:check|selftest)\)", re.MULTILINE)
# A Claude Code hook reads `tool_input` from the JSON payload on stdin.
_HOOK = re.compile(r"""(?:\.get\(|\[)\s*["']tool_input["']""")


def _script_gates(root: Path, ci_run: set[str]) -> dict[str, dict]:
    d = root / SCRIPTS_DIR
    out: dict[str, dict] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        if not p.is_file() or p.suffix not in (".py", ".sh"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise Inconclusive(f"{SCRIPTS_DIR}/{p.name}: unreadable ({exc})")
        has_mode = bool((_PY_MODE if p.suffix == ".py" else _SH_MODE).search(text))
        is_hook = p.suffix == ".py" and bool(_HOOK.search(text))
        if has_mode or is_hook or p.name in ci_run:
            out[f"{SCRIPTS_DIR}/{p.name}"] = {"hook": is_hook}
    return out


def enumerate_gates(root: Path) -> dict[str, dict]:
    """{gate_id: {"source": "ci"|"script", "allowed_kinds": tuple, ...}} -- the mechanical census."""
    jobs = _all_jobs(root)
    ci_run: set[str] = set()
    for job in jobs.values():
        ci_run |= job["runs_scripts"]
    gates: dict[str, dict] = {}
    for gid, job in jobs.items():
        gates[gid] = {"source": "ci", "allowed_kinds": ("declared-gap",) if job["disabled"] else ("ci-job",),
                      "disabled": job["disabled"]}
    for gid, info in _script_gates(root, ci_run).items():
        gates[gid] = {"source": "script", "allowed_kinds": ("hook",) if info["hook"] else ("script",)}
    return gates


# --------------------------------------------------------------------------
# Seals
# --------------------------------------------------------------------------

def dependency_digest(root: Path, dep: str, jobs: dict[str, dict] | None = None) -> str | None:
    """sha256 of one seal dependency, or None if it no longer exists."""
    dep = _posix(dep)
    if "#jobs." in dep:
        if jobs is None:
            jobs = _all_jobs(root)
        job = jobs.get(dep)
        return None if job is None else _sha256(job["block"].encode("utf-8"))
    p = root / dep
    if not p.is_file():
        return None
    return _sha256(p.read_bytes())


def seal_digest(seal: dict[str, str]) -> str:
    """One short digest of a whole seal, shown in the rendered table."""
    blob = "\n".join(f"{k}={seal[k]}" for k in sorted(seal))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

def load_registry(root: Path) -> dict:
    p = root / REGISTRY_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Inconclusive(f"{REGISTRY_PATH} not found")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Inconclusive(f"{REGISTRY_PATH}: unreadable ({exc})")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("gates"), list):
        raise Inconclusive(f"{REGISTRY_PATH}: expected {{\"schema\": \"{SCHEMA}\", \"gates\": [...]}}")
    return data


def write_registry(root: Path, data: dict) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (root / REGISTRY_PATH).write_text(text, encoding="utf-8", newline="\n")


def _schema_reasons(data: dict) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for idx, e in enumerate(data["gates"]):
        if not isinstance(e, dict):
            reasons.append(f"gates[{idx}]: not an object")
            continue
        gid = e.get("id")
        label = gid if isinstance(gid, str) and gid else f"gates[{idx}]"
        if not isinstance(gid, str) or not gid:
            reasons.append(f"{label}: missing id")
        elif gid in seen:
            reasons.append(f"{label}: duplicate id")
        else:
            seen.add(gid)
        if e.get("kind") not in KINDS:
            reasons.append(f"{label}: kind must be one of {', '.join(KINDS)} (got {e.get('kind')!r})")
        for key in ("name", "stops", "source"):
            if not isinstance(e.get(key), str) or not e[key].strip():
                reasons.append(f"{label}: `{key}` must be a non-empty string")
        gaps = e.get("would_not_stop")
        if not isinstance(gaps, list) or not gaps or not all(isinstance(g, str) and g.strip() for g in gaps):
            reasons.append(f"{label}: `would_not_stop` must be a non-empty list of named gaps")
        seal = e.get("seal")
        if not isinstance(seal, dict) or not seal or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in seal.items()):
            reasons.append(f"{label}: `seal` must be a non-empty {{dependency: sha256}} map")
    return reasons


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _cell(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render(data: dict) -> str:
    out = [
        "<!-- GENERATED by scripts/render-gate-gaps.py from docs/gate-gaps.json. Do not hand-edit:",
        "     edit the JSON, then run `python scripts/render-gate-gaps.py`. -->",
        "",
        "# Gate gaps: every gate in this repo, and what it would NOT stop",
        "",
        f"Registry schema `{SCHEMA}`, renderer v{__version__}. "
        f"{len(data['gates'])} entries.",
        "",
        "A green check means *the checks that exist passed*. This page says which checks exist "
        "and, for each, what it cannot see -- named, not implied. `scripts/render-gate-gaps.py "
        "--check` (run by `tests/test_gate_gaps.py` in CI) refuses when a workflow job or a "
        "check script exists with no row here, when a row's seal no longer matches the gate's "
        "files, or when this page is stale.",
        "",
        "**Adding a gate.** Add an entry to `docs/gate-gaps.json` with `\"seal\": {}` (list any "
        "extra implementing files as keys), then run `python scripts/render-gate-gaps.py "
        "--reseal <id>`. `--check` refuses an empty seal, so the entry cannot land unsealed.",
        "",
        "**Changing a gate.** `--check` will refuse its seal. Re-read the row's *would NOT stop* "
        "list against the new code, fix the text, then `--reseal <id>`. Re-sealing is a claim "
        "that you did that review, and it is visible in the diff.",
        "",
    ]
    by_kind: dict[str, list[dict]] = {k: [] for k in KINDS}
    for e in data["gates"]:
        by_kind.setdefault(e["kind"], []).append(e)
    for kind in KINDS:
        rows = sorted(by_kind.get(kind, []), key=lambda e: e["id"])
        if not rows:
            continue
        out += [f"## {KIND_TITLES[kind]}", "",
                "| gate | what it stops | what it would NOT stop | seal | source of the gap list |",
                "|---|---|---|---|---|"]
        for e in rows:
            gaps = "<br>".join(f"- {_cell(g)}" for g in e["would_not_stop"])
            out.append("| " + " | ".join([
                f"**{_cell(e['name'])}**<br>`{_cell(e['id'])}`",
                _cell(e["stops"]),
                gaps,
                f"`{seal_digest(e['seal'])}`",
                _cell(e["source"]),
            ]) + " |")
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# The check
# --------------------------------------------------------------------------

def check(root: Path) -> tuple[int, list[str]]:
    """(verdict code, reasons). Never raises for a bad repo: Inconclusive becomes exit 2."""
    try:
        data = load_registry(root)
        census = enumerate_gates(root)
        jobs = _all_jobs(root)
    except Inconclusive as exc:
        return INCONCLUSIVE, [str(exc)]

    reasons = _schema_reasons(data)
    if reasons:
        return REFUSED, reasons

    entries = {e["id"]: e for e in data["gates"]}
    for gid, g in census.items():
        if gid not in entries:
            reasons.append(f"{gid}: UNREGISTERED gate -- add an entry naming what it stops and "
                           f"what it would NOT stop (kind {g['allowed_kinds'][0]})")
            continue
        kind = entries[gid]["kind"]
        if kind not in g["allowed_kinds"]:
            if g["source"] == "ci" and g.get("disabled"):
                why = "the job is `if: false`, so it runs nothing and stops nothing"
            elif g["source"] == "ci":
                why = "the job is enabled, so it is a gate again; re-review and reclassify it"
            elif "hook" in g["allowed_kinds"]:
                why = "the script reads a Claude Code hook payload"
            else:
                why = "the script does not read a Claude Code hook payload"
            reasons.append(f"{gid}: kind {kind!r} contradicts the code -- must be "
                           f"{g['allowed_kinds'][0]!r} ({why})")
    for gid, e in entries.items():
        if gid not in census and e["kind"] != "declared-gap":
            reasons.append(f"{gid}: ORPHAN entry -- no such gate is enumerated any more")
        elif gid not in census:
            reasons.append(f"{gid}: ORPHAN declared gap -- the job it declares no longer exists")
        seal = {_posix(k): v for k, v in e["seal"].items()}
        if gid not in seal:
            reasons.append(f"{gid}: seal does not cover the gate's own implementation `{gid}`")
        for dep, recorded in sorted(seal.items()):
            actual = dependency_digest(root, dep, jobs)
            if actual is None:
                reasons.append(f"{gid}: seal dependency `{dep}` no longer exists")
            elif actual != recorded:
                reasons.append(f"{gid}: STALE SEAL on `{dep}` -- the gate changed; re-review its "
                               f"would-NOT-stop list, then --reseal {gid}")

    doc = root / DOC_PATH
    expected = render(data)
    try:
        current = doc.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = None
    if current is None:
        reasons.append(f"{DOC_PATH}: missing -- run `python scripts/render-gate-gaps.py`")
    elif current.replace("\r\n", "\n") != expected:
        reasons.append(f"{DOC_PATH}: STALE -- not what {REGISTRY_PATH} renders to; "
                       f"run `python scripts/render-gate-gaps.py` (never hand-edit it)")
    return (REFUSED if reasons else CURRENT), reasons


def reseal(root: Path, ids: list[str]) -> list[str]:
    """Recompute the seals of the named entries. Returns problems (empty on success)."""
    data = load_registry(root)
    jobs = _all_jobs(root)
    entries = {e.get("id"): e for e in data["gates"] if isinstance(e, dict)}
    problems: list[str] = []
    for gid in ids:
        e = entries.get(gid)
        if e is None:
            problems.append(f"{gid}: no such entry in {REGISTRY_PATH}")
            continue
        deps = [_posix(k) for k in (e.get("seal") or {})]
        if gid not in deps:
            deps.insert(0, gid)
        new = {}
        for dep in deps:
            digest = dependency_digest(root, dep, jobs)
            if digest is None:
                problems.append(f"{gid}: seal dependency `{dep}` does not exist; remove it from the entry")
                break
            new[dep] = digest
        else:
            e["seal"] = new
    if not problems:
        write_registry(root, data)
    return problems


def write_doc(root: Path) -> None:
    (root / DOC_PATH).write_text(render(load_registry(root)), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate-gap registry: render docs/GATE_GAPS.md and check it.")
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    ap.add_argument("--reseal", nargs="+", metavar="ID", help="recompute these entries' seals (after re-review)")
    ap.add_argument("--list", action="store_true", help="print the mechanical gate enumeration")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="repo root (default: this checkout)")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.list:
            for gid, g in sorted(enumerate_gates(root).items()):
                print(f"{g['allowed_kinds'][0]:13s} {gid}")
            return CURRENT
        if args.reseal:
            problems = reseal(root, args.reseal)
            if problems:
                print("RESEAL REFUSED:")
                for p in problems:
                    print(f"  - {p}")
                return REFUSED
            print(f"resealed: {', '.join(args.reseal)}")
        if not args.check:
            write_doc(root)
            print(f"rendered {DOC_PATH}")
    except Inconclusive as exc:
        print(f"INCONCLUSIVE: {exc}")
        return INCONCLUSIVE

    code, reasons = check(root)
    if code == CURRENT:
        print(f"CURRENT: every enumerated gate is registered, sealed, and rendered ({DOC_PATH}).")
    elif code == INCONCLUSIVE:
        print("INCONCLUSIVE: the gate census could not be taken, so nothing was checked.")
        for r in reasons:
            print(f"  - {r}")
    else:
        print(f"REFUSED: {len(reasons)} reason(s).")
        for r in reasons:
            print(f"  - {r}")
    return code


if __name__ == "__main__":
    sys.exit(main())
