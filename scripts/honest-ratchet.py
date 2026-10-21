#!/usr/bin/env python3
"""honest-ratchet.py -- the kit's protective state may only get quieter with a
named, dated, reasoned acknowledgement.

WHAT IT IS. A ratchet over what protects this repository. It MEASURES:
  - tests per suite: pytest test functions (tests/test_*.py, scripts/test_*.py),
    Pester `It` blocks (every *.tests.ps1), and bash test cases (tests/*.bash);
    both the COUNT per suite and the NAME of every test;
  - the rules files shipped in rules/;
  - the protected-config patterns in scripts/protect-test-config.py;
  - the guard/check scripts present in scripts/;
  - the CI job names in .github/workflows/test.yml, and which of them are enabled;
and compares that with a committed baseline, docs/ratchet-baseline.json.

    --check    exit 1 on ANY decrease or removal that
               docs/ratchet-acknowledgements.json does not name exactly.
               Increases and additions pass.
    --update   rewrite the baseline -- ONLY when --check would pass (or when no
               baseline exists yet). It cannot be used to bless a silent loss.

WHY IT EXISTS. Every gate in this kit is a file. Deleting a test, dropping a
rules file, removing a pattern from the test-config hook, or switching a CI job
to `if: false` turns red into green without fixing anything, and the diff is a
quiet one: nothing fails, something just stops being checked. Ported from the
meta-harness honest-state ratchet (harness/honest_ratchet.py), whose rule is
"a page may add warnings, but once a warning has been served it must not
silently go quieter". Here the "warnings" are the checks themselves.

AN ACKNOWLEDGEMENT. A loss is accepted only under an entry that names it exactly:

    {"item": "pytest:tests/test_reuse.py", "base": 12, "new": 11,
     "reason": "merged two duplicate cases into one parametrized test",
     "date": "2026-10-21"}
    {"item": "rules::rules/advanced-stats.md",
     "reason": "folded into rules/rules.md", "date": "2026-10-21"}

A count item needs BOTH counts exactly (as in the source: a fix that lands the
count anywhere else is a different change and is not covered). A member item is
`<set>::<member>`. reason and an ISO date (YYYY-MM-DD) are required; an entry
missing either is ignored, not half-honoured.

WHAT IT DOES NOT CHECK, named rather than implied.
  - It counts tests; it does not judge them. A test whose body is emptied keeps
    its name and its count. Pair with scripts/blank-and-rerun.py.
  - A pytest function is dropped from the name set when decorated with
    pytest.mark.skip / pytest.mark.xfail / unittest.skip (so newly skipping a
    test IS a removal). skipif is conditional and is still counted; a
    `pytest.skip()` call inside a body is not seen.
  - A Pester `It ... -Skip` (or -Skip:$true) is dropped likewise;
    `-Skip:(<condition>)` is conditional and still counted; a skipped
    Describe/Context is not seen.
  - Bash cases are `start "<name>"` calls, or -- in a file with no start()
    helper -- labelled `assert_eq "<name>"` / `ok "<name>"` calls.
  - It does not read what CI does inside a job, only that the job exists and is
    not `if: false`.

OPT-IN. Nothing in the installer runs this. The starter enforces it on itself
through tests/test_honest_ratchet.py (so the existing python-tests CI job runs
it). To use it on your own repo: `python scripts/honest-ratchet.py --root . --update`
once, commit docs/ratchet-baseline.json, then run `--check` in CI or a hook.
See docs/HONEST-RATCHET.md.

EXIT CODES
    0   pass (or baseline written)
    1   REFUSED -- an unacknowledged decrease or removal
    2   could not execute (missing/malformed baseline or acknowledgements);
        fail-closed: an unreadable baseline is not a pass.

    python scripts/honest-ratchet.py --selftest   # prove it refuses, and passes

Offline, standard library only. MIT-licensed.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

VERSION = "1.0.0"

PASS, REFUSED, NOEXEC = 0, 1, 2

BASELINE_PATH = Path("docs") / "ratchet-baseline.json"
ACK_PATH = Path("docs") / "ratchet-acknowledgements.json"

PYTEST_GLOBS = ("tests/test_*.py", "scripts/test_*.py")
PESTER_GLOBS = ("**/*.tests.ps1",)
BASH_GLOBS = ("tests/*.bash",)
WORKFLOW = Path(".github") / "workflows" / "test.yml"
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
PROTECT_SCRIPT =Path("scripts") / "protect-test-config.py"
PROTECT_TUPLES = ("PROTECTED_NAMES", "PROTECTED_R_TESTTHAT", "OPTIONAL_NAMES")

# A guard/check script: its name says so, or it offers --check / --selftest.
GUARD_NAME = re.compile(r"(protect|guard|gate|check|audit|screen|reconcile|rerun|ratchet|achievable)", re.I)
GUARD_FLAG = re.compile(r"--(check|selftest)\b")

SKIP_DECORATORS = re.compile(r"(^|\.)(mark\.skip|mark\.xfail|skip)$")
PESTER_IT = re.compile(r"""^\s*It\s+(['"])(.*?)\1(.*)$""")
BASH_START = re.compile(r"""^\s*start\s+(['"])(.*?)\1""")
BASH_LABELLED = re.compile(r"""^\s*(?:assert_eq|ok)\s+(['"])(.*?)\1""")
BASH_HAS_START = re.compile(r"^\s*start\(\)\s*\{", re.M)
JOB_LINE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
JOB_DISABLED = re.compile(r"^    if:\s*(false|\$\{\{\s*false\s*\}\})\s*$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------

def _files(root: Path, globs) -> list:
    out = set()
    for g in globs:
        for p in root.glob(g):
            if p.is_file() and not IGNORED_DIRS.intersection(p.relative_to(root).parts):
                out.add(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def _decorator_name(node) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def pytest_tests(text: str) -> list:
    """Active test function names (`Class::test_x` for methods); skip/xfail dropped."""
    tree = ast.parse(text)
    names = []

    def visit(body, prefix):
        for node in body:
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                if not any(SKIP_DECORATORS.search(_decorator_name(d)) for d in node.decorator_list):
                    visit(node.body, prefix + node.name + "::")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                if not any(SKIP_DECORATORS.search(_decorator_name(d)) for d in node.decorator_list):
                    names.append(prefix + node.name)

    visit(tree.body, "")
    return names


def pester_tests(text: str) -> list:
    names = []
    for line in text.splitlines():
        m = PESTER_IT.match(line)
        # Unconditional -Skip / -Skip:$true drops the test; -Skip:(<condition>) is Pester's skipif.
        if m and not re.search(r"(^|\s)-Skip(?::\$true)?(?=\s|\{|$)", m.group(3), re.I):
            names.append(m.group(2))
    return names


def bash_tests(text: str) -> list:
    pat = BASH_START if BASH_HAS_START.search(text) else BASH_LABELLED
    names = []
    for line in text.splitlines():
        m = pat.match(line)
        # `ok "$label"` inside a helper is plumbing, not a case.
        if m and not m.group(2).startswith("$"):
            names.append(m.group(2))
    return names


def protected_patterns(text: str) -> list:
    out = []
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in PROTECT_TUPLES:
                    for v in ast.literal_eval(node.value):
                        out.append("%s:%s" % (t.id, v))
    return out


def ci_jobs(text: str) -> tuple:
    jobs, enabled, in_jobs, current = [], [], False, None
    for line in text.splitlines():
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if in_jobs and re.match(r"^\S", line):
            in_jobs = False
        if not in_jobs:
            continue
        m = JOB_LINE.match(line)
        if m:
            current = m.group(1)
            jobs.append(current)
            enabled.append(current)
        elif current and JOB_DISABLED.match(line) and current in enabled:
            enabled.remove(current)
    return jobs, enabled


def measure(root) -> dict:
    """The protective state of `root`: {"counts": {key: int}, "sets": {key: [members]}}."""
    root = Path(root)
    counts, sets = {}, {}
    for kind, globs, fn in (("pytest", PYTEST_GLOBS, pytest_tests),
                            ("pester", PESTER_GLOBS, pester_tests),
                            ("bash", BASH_GLOBS, bash_tests)):
        for p in _files(root, globs):
            names = fn(_read(p))
            counts["%s:%s" % (kind, _rel(root, p))] = len(names)
            sets["%s-names:%s" % (kind, _rel(root, p))] = sorted(set(names))
    sets["rules"] = [_rel(root, p) for p in _files(root, ("rules/*",))]
    protect = root / PROTECT_SCRIPT
    sets["protected-config"] = sorted(protected_patterns(_read(protect))) if protect.is_file() else []
    guards = []
    for p in _files(root, ("scripts/*.py", "scripts/*.sh", "scripts/*.ps1")):
        if p.name.startswith(("test_", "pester.")):
            continue
        if GUARD_NAME.search(p.name) or GUARD_FLAG.search(_read(p)):
            guards.append(_rel(root, p))
    sets["guard-scripts"] = guards
    wf = root / WORKFLOW
    jobs, enabled = ci_jobs(_read(wf)) if wf.is_file() else ([], [])
    sets["ci-jobs"] = sorted(jobs)
    sets["ci-jobs-enabled"] = sorted(enabled)
    return {"counts": dict(sorted(counts.items())), "sets": dict(sorted(sets.items()))}


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

def _valid_entry(e) -> bool:
    return (isinstance(e, dict) and isinstance(e.get("item"), str) and e["item"]
            and isinstance(e.get("reason"), str) and e["reason"].strip()
            and isinstance(e.get("date"), str) and bool(ISO_DATE.match(e["date"])))


def load_acknowledgements(root) -> tuple:
    """(entries, errors). A missing file is no acknowledgements; a malformed one is an error."""
    path = Path(root) / ACK_PATH
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return [], ["COULD-NOT-EXECUTE: cannot read %s: %s" % (ACK_PATH.as_posix(), exc)]
    if not isinstance(data, dict) or not isinstance(data.get("acknowledgements"), list):
        return [], ["COULD-NOT-EXECUTE: %s must be an object with an \"acknowledgements\" list"
                    % ACK_PATH.as_posix()]
    return [e for e in data["acknowledgements"] if _valid_entry(e)], []


def _acked_count(acks, item, base, new) -> bool:
    return any(e["item"] == item and e.get("base") == base and e.get("new") == new for e in acks)


def _acked_member(acks, item) -> bool:
    return any(e["item"] == item for e in acks)


def compare(base: dict, new: dict, acks) -> list:
    """Unacknowledged decreases/removals between two measurements. Increases are silent."""
    out = []
    for key, b in sorted(base.get("counts", {}).items()):
        n = new.get("counts", {}).get(key, 0)
        if n < b and not _acked_count(acks, key, b, n):
            what = "suite removed" if key not in new.get("counts", {}) else "count decreased"
            out.append('%s: %s %d -> %d  (ack: {"item": "%s", "base": %d, "new": %d, "reason": ..., "date": ...})'
                       % (key, what, b, n, key, b, n))
    for key, members in sorted(base.get("sets", {}).items()):
        have = set(new.get("sets", {}).get(key, []))
        for m in members:
            item = "%s::%s" % (key, m)
            if m not in have and not _acked_member(acks, item):
                out.append('%s: removed  (ack: {"item": "%s", "reason": ..., "date": ...})' % (item, item))
    return out


def load_baseline(root) -> tuple:
    path = Path(root) / BASELINE_PATH
    if not path.exists():
        return None, "COULD-NOT-EXECUTE: no baseline at %s (create one with --update)" % BASELINE_PATH.as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, "COULD-NOT-EXECUTE: cannot read %s: %s" % (BASELINE_PATH.as_posix(), exc)
    if not isinstance(data, dict) or not isinstance(data.get("counts"), dict) or not isinstance(data.get("sets"), dict):
        return None, "COULD-NOT-EXECUTE: %s must hold \"counts\" and \"sets\" objects" % BASELINE_PATH.as_posix()
    return data, None


def check(root) -> tuple:
    """(exit_code, lines)."""
    base, err = load_baseline(root)
    if err:
        return NOEXEC, [err]
    acks, errors = load_acknowledgements(root)
    if errors:
        return NOEXEC, errors
    violations = compare(base, measure(root), acks)
    return (REFUSED, violations) if violations else (PASS, [])


def write_baseline(root) -> Path:
    path = Path(root) / BASELINE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"_doc": "Protective-state baseline for scripts/honest-ratchet.py. Do not hand-edit: "
                    "run `python scripts/honest-ratchet.py --update`, which refuses while any "
                    "decrease is unacknowledged. Losses are acknowledged in "
                    "docs/ratchet-acknowledgements.json.",
            "version": VERSION}
    data.update(measure(root))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return path


def update(root) -> tuple:
    base, err = load_baseline(root)
    if base is not None or "no baseline" not in (err or ""):
        code, lines = check(root)
        if code != PASS:
            return code, ["--update refused: --check does not pass."] + lines
    return PASS, ["baseline written: %s" % write_baseline(root)]


# --------------------------------------------------------------------------
# Selftest -- BOTH DIRECTIONS, as everywhere in this kit.
# --------------------------------------------------------------------------

_FIXTURE = {
    "tests/test_a.py": "def test_one():\n    pass\n\ndef test_two():\n    pass\n",
    "rules/rules.md": "# rules\n",
    ".github/workflows/test.yml": "jobs:\n  python-tests:\n    runs-on: x\n",
}


def selftest() -> int:
    failures = []
    tmp = Path(tempfile.mkdtemp(prefix="honest-ratchet-"))
    try:
        for rel, text in _FIXTURE.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(text, encoding="utf-8")
        if check(tmp)[0] != NOEXEC:
            failures.append("a missing baseline did not fail closed")
        update(tmp)
        if check(tmp)[0] != PASS:
            failures.append("an unchanged tree did not pass")
        (tmp / "tests/test_a.py").write_text(_FIXTURE["tests/test_a.py"] + "\ndef test_three():\n    pass\n",
                                             encoding="utf-8")
        if check(tmp)[0] != PASS:
            failures.append("an ADDED test was refused")
        (tmp / "tests/test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
        if check(tmp)[0] != REFUSED:
            failures.append("a DELETED test was not refused")
        if update(tmp)[0] != REFUSED:
            failures.append("--update blessed an unacknowledged loss")
        ack = {"acknowledgements": [
            {"item": "pytest:tests/test_a.py", "base": 2, "new": 1, "reason": "selftest", "date": "2026-10-21"},
            {"item": "pytest-names:tests/test_a.py::test_two", "reason": "selftest", "date": "2026-10-21"}]}
        (tmp / ACK_PATH).write_text(json.dumps(ack), encoding="utf-8")
        if check(tmp)[0] != PASS:
            failures.append("an ACKNOWLEDGED deletion was refused")
        ack["acknowledgements"][0]["new"] = 0
        (tmp / ACK_PATH).write_text(json.dumps(ack), encoding="utf-8")
        if check(tmp)[0] != REFUSED:
            failures.append("an acknowledgement with the wrong count was honoured")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        for f in failures:
            print("SELFTEST FAIL: %s" % f)
        return REFUSED
    print("selftest OK -- missing baseline fails closed, added test passes, deleted test refused,")
    print("--update refuses to bless it, exact acknowledgement passes, wrong-count acknowledgement refused.")
    return PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Protective-state ratchet (v%s)." % VERSION)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="refuse any unacknowledged decrease or removal")
    mode.add_argument("--update", action="store_true", help="rewrite the baseline (only if --check passes)")
    mode.add_argument("--show", action="store_true", help="print the current measurement")
    mode.add_argument("--selftest", action="store_true", help="prove it refuses and passes")
    mode.add_argument("--version", action="store_true")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]),
                        help="repository root (default: this script's repo)")
    args = parser.parse_args(argv)
    if args.version:
        print(VERSION)
        return PASS
    if args.selftest:
        return selftest()
    root = Path(args.root)
    if args.show:
        print(json.dumps(measure(root), indent=1, ensure_ascii=False))
        return PASS
    code, lines = (check if args.check else update)(root)
    label = {PASS: "PASS", REFUSED: "REFUSED", NOEXEC: "COULD-NOT-EXECUTE"}[code]
    print("honest-ratchet v%s: %s" % (VERSION, label))
    for line in lines:
        print("  " + line)
    return code


if __name__ == "__main__":
    sys.exit(main())
