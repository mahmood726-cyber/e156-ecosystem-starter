#!/usr/bin/env python3
"""gate-can-fail.py -- a file named a GATE must be able to fail. The name is a promise.

WHAT IT IS. A static check over a tree of Python files. Any module whose filename
ends in `_gate.py` must contain a reachable non-zero exit -- `sys.exit(1)`,
`raise SystemExit(...)`, or a `main()` that can return non-zero. A module that
merely PRINTS its findings is a report, and a report is not a gate.

WHY IT EXISTS. On 2026-08-19 a sweep of one evidence-synthesis corpus found FOUR
files named `*_gate.py` with no reachable non-zero exit. They could only ever
pass. Wired into a pre-commit hook, all four would have reported green forever.

AND THE FOUR WERE NOT BROKEN -- THE NAME WAS. Reading them settled it: each
self-describes as advisory ("TRIAGE, NOT A VERDICT" / "a flag means READ THE
TRIAL"). They were correctly-built triage tools wearing the wrong name, and
wiring them to block would have contradicted their own stated contract. All four
were renamed to `*_triage.py`. The defect was the label, not the behaviour --
which is the difference between an error and a defensible different choice, and
this tool reports the label only.

    A GATE THAT CANNOT FAIL IS NOT A DEFECT WHILE NOTHING RUNS IT.
    IT IS A TRAP FOR WHOEVER WIRES IT IN NEXT, who will reasonably assume that a
    thing called a gate can block.

That is why this is a lint and not a one-off rename: renaming four files does
nothing to stop the fifth being written tomorrow.

WHAT IT DOES NOT CHECK, named rather than implied. Reachability is judged
SYNTACTICALLY -- the statement exists in the file. It does not prove that any
input can actually reach it. A gate containing `if False: sys.exit(1)` passes
this lint and cannot fail in practice. Proving a gate CAN fire on a real input is
a known-answer test: run it against a stored known-bad input and assert it
refuses. That is a different instrument, and this one does not substitute for it.
See docs/DETECTOR-VERIFICATION.md.

MEASURED. Run over the corpus that motivated it, after the four renames:
39 files named `*_gate.py` checked, 3 excluded by verb prefix, **0 that cannot
fail**. Before the renames it found 4. Both directions are exercised by
`--selftest`, which builds a known-bad and a known-good fixture for every rule
below and asserts the verdict on each.

USAGE
    python scripts/gate-can-fail.py                 # check the current directory
    python scripts/gate-can-fail.py path/to/repo    # check somewhere else
    python scripts/gate-can-fail.py --json          # machine-readable
    python scripts/gate-can-fail.py --selftest      # prove it fires, and does not

VERDICTS -- the same three the rest of this kit uses, and for the same reason.
    CLEAN            0   every file named a gate contains a failing exit
    DEFECTS-FOUND    1   at least one cannot fail
    INCONCLUSIVE     2   a file could not be parsed, so it was not checked

INCONCLUSIVE exits non-zero on purpose. "I could not check this" must never
collapse into "this is fine".

Offline, standard library only, no API key, no model call. MIT-licensed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

# A VERB PREFIX PUTS 'gate' IN THE OBJECT POSITION, NOT THE SUBJECT.
# `add_release_gate.py` and `fix_alignment_gate.py` are scripts that MODIFY a
# gate; `test_build_gate.py` is a TEST OF a gate. None of them claims to be one,
# so none owes a failing exit.
#
# This is exactly the move that turns a guard into a formality, so the exclusions
# are COUNTED AND NAMED on every run. If that list starts growing, it is being
# used as a hiding place -- and the fix then is to rename the file, not to extend
# this tuple.
ACTS_ON_A_GATE = ("test_", "add_", "extend_", "fix_", "make_", "regenerate_")

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache"}

CLEAN, DEFECTS_FOUND, INCONCLUSIVE = 0, 1, 2


def _returns_nonzero(tree: ast.AST, fname: str) -> bool:
    """Does the module-level function `fname` ever return a non-zero constant?

    THE IDIOM THAT DEFEATED THE FIRST VERSION OF THIS LINT. `sys.exit(main())` is
    the standard gate shape, so a non-constant argument was treated as "can
    fail" -- but all four files that motivated this lint end exactly that way,
    with a `main()` whose only return is 0. The first version WOULD HAVE MISSED
    THE FOUR FILES IT WAS WRITTEN FOR. It was caught by replaying it against
    those four real files rather than against an invented probe.

    Resolved conservatively: if the named function cannot be found, or returns
    something this cannot evaluate (a variable, a call), the answer is True --
    unproven is not the same as proven-safe, and a lint should not manufacture a
    failure it cannot demonstrate.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fname:
            saw_unknown = False
            for r in ast.walk(node):
                if isinstance(r, ast.Return) and r.value is not None:
                    if isinstance(r.value, ast.Constant) and isinstance(r.value.value, int):
                        if r.value.value != 0:
                            return True
                    else:
                        saw_unknown = True
            return saw_unknown
    return True  # function not found: do not claim it cannot fail


def has_failing_exit(tree: ast.AST) -> bool:
    """True if the module contains a non-zero exit / SystemExit / `return 1`."""
    for node in ast.walk(tree):
        # sys.exit(1) / exit(2) / sys.exit(main())
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name in ("exit", "_exit"):
                if not node.args:
                    continue  # exit() with no code == exit(0)
                a = node.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, int):
                    if a.value != 0:
                        return True
                elif isinstance(a, ast.Call) and getattr(a.func, "id", None):
                    # sys.exit(main()) -- resolve main() rather than assume it can fail
                    if _returns_nonzero(tree, a.func.id):
                        return True
                else:
                    return True  # sys.exit(<expr>) we cannot resolve
        if isinstance(node, ast.Raise):
            exc = node.exc
            nm = getattr(getattr(exc, "func", None), "id", None) or getattr(exc, "id", None)
            if nm == "SystemExit":
                return True
        # `return 1` (or any non-zero int) from a function
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, int) and node.value.value != 0:
                return True
    return False


def scan(root: str, suffix: str = "_gate.py") -> dict:
    """Walk `root` and classify every file whose name ends in `suffix`.

    Returns a dict carrying the DENOMINATOR as well as the findings. A count of
    hits with no count of what was looked at is not refutable.
    """
    cannot_fail, checked, unparsable, excluded = [], [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(filenames):
            if not fn.endswith(suffix):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if fn.startswith(ACTS_ON_A_GATE):
                excluded.append(rel)
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    tree = ast.parse(fh.read())
            except (SyntaxError, OSError) as exc:  # reported, never silently skipped
                unparsable.append({"file": rel, "error": str(exc)[:120]})
                continue
            checked.append(rel)
            if not has_failing_exit(tree):
                cannot_fail.append(rel)

    if cannot_fail:
        verdict = "DEFECTS-FOUND"
    elif unparsable:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "CLEAN"

    return {
        "verdict": verdict,
        "root": os.path.abspath(root),
        "suffix": suffix,
        "files_checked": len(checked),
        "cannot_ever_fail": cannot_fail,
        "unparsable": unparsable,
        "excluded_by_verb_prefix": excluded,
        "not_checked": (
            "Reachability is judged syntactically. `if False: sys.exit(1)` passes "
            "this lint. Proving a gate can fire on a real input is a known-answer "
            "test, a different instrument."
        ),
    }


def report(result: dict) -> int:
    for rel in result["cannot_ever_fail"]:
        print(rel)
        print("      named a GATE but contains no reachable non-zero exit: it can only pass.")
    for row in result["unparsable"]:
        print("%s  UNPARSABLE (%s) -- reported, not skipped" % (row["file"], row["error"]))

    excluded = result["excluded_by_verb_prefix"]
    if excluded:
        print()
        print("excluded -- a VERB prefix puts 'gate' in the object position, so the file")
        print("acts ON a gate rather than being one. Counted and named every run:")
        for rel in excluded:
            print("   %s" % rel)

    print()
    print("files named *%s   %d checked, %d unparsable, %d excluded by verb prefix"
          % (result["suffix"], result["files_checked"], len(result["unparsable"]), len(excluded)))
    print("cannot ever fail        %d" % len(result["cannot_ever_fail"]))
    print()
    print("NOT CHECKED: %s" % result["not_checked"])
    print()

    if result["verdict"] == "DEFECTS-FOUND":
        print("DEFECTS-FOUND: %d file(s) named a gate cannot fail." % len(result["cannot_ever_fail"]))
        print("FIX: give it a reachable non-zero exit, or RENAME it -- a report is")
        print("     *_triage.py, *_check.py, *_census.py. Renaming is the right fix when")
        print("     the file is advisory by design; do not wire an advisory tool to block.")
        return DEFECTS_FOUND
    if result["verdict"] == "INCONCLUSIVE":
        print("INCONCLUSIVE: a file named a gate could not be parsed, so it was not checked.")
        print("A check that could not run is not a check that passed.")
        return INCONCLUSIVE
    if result["files_checked"] == 0:
        print("CLEAN over an EMPTY SET -- nothing here is named `*%s`, so nothing was"
              % result["suffix"])
        print("checked. This is not evidence about your gates. If you expected files, check")
        print("the path and the --suffix; if your project spells them differently, pass it.")
        return CLEAN
    print("CLEAN: every file named a gate can fail (%d of %d)."
          % (result["files_checked"], result["files_checked"]))
    return CLEAN


# --------------------------------------------------------------------------
# Selftest -- BOTH DIRECTIONS. A detector with only a positive test passes CI
# while matching everything; a detector with only a negative test passes CI
# while matching nothing.
# --------------------------------------------------------------------------

KNOWN_BAD = {
    # The idiom that defeated the first version: a real gate shape whose main()
    # can only return 0.
    "silent_main_gate.py": (
        "import sys\n"
        "def main():\n"
        "    print('all good')\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n"
    ),
    # A report wearing a gate's name.
    "prints_only_gate.py": (
        "def main():\n"
        "    print('2 problems found')\n"
        "main()\n"
    ),
    # exit() with no argument is exit(0).
    "bare_exit_gate.py": (
        "import sys\n"
        "print('done')\n"
        "sys.exit()\n"
    ),
}

KNOWN_GOOD = {
    "explicit_gate.py": "import sys\nif True:\n    sys.exit(1)\n",
    "return_one_gate.py": (
        "import sys\n"
        "def main():\n"
        "    if 1:\n"
        "        return 1\n"
        "    return 0\n"
        "sys.exit(main())\n"
    ),
    "systemexit_gate.py": "raise SystemExit('refused')\n",
    # Not a gate by name: must not be checked at all, however it exits.
    "quiet_report.py": "print('nothing to see')\n",
}

EXCLUDED_FIXTURE = {"test_build_gate.py": "def test_x():\n    assert True\n"}
UNPARSABLE_FIXTURE = {"broken_gate.py": "def main(:\n"}


def selftest() -> int:
    import tempfile

    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, src in list(KNOWN_BAD.items()) + list(KNOWN_GOOD.items()) + list(EXCLUDED_FIXTURE.items()):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(src)
        res = scan(tmp)

        fired = set(res["cannot_ever_fail"])
        for name in KNOWN_BAD:
            if name not in fired:
                failures.append("MISSED a known-bad: %s was not flagged" % name)
        for name in KNOWN_GOOD:
            if name in fired:
                failures.append("FALSE POSITIVE: %s was flagged" % name)
        if "quiet_report.py" in res["cannot_ever_fail"] + res["excluded_by_verb_prefix"]:
            failures.append("scanned a file that is not named a gate: quiet_report.py")
        if res["excluded_by_verb_prefix"] != ["test_build_gate.py"]:
            failures.append("verb-prefix exclusion wrong: %r" % (res["excluded_by_verb_prefix"],))
        if res["files_checked"] != len(KNOWN_BAD) + len(KNOWN_GOOD) - 1:  # quiet_report is not a gate
            failures.append("denominator wrong: files_checked=%d" % res["files_checked"])
        if res["verdict"] != "DEFECTS-FOUND":
            failures.append("verdict on the known-bad set was %s" % res["verdict"])

        # And the clean direction: remove the known-bad files, expect CLEAN.
        for name in KNOWN_BAD:
            os.remove(os.path.join(tmp, name))
        clean = scan(tmp)
        if clean["verdict"] != "CLEAN":
            failures.append("verdict on the known-good set was %s" % clean["verdict"])

        # And the inconclusive direction: an unparsable gate must not read clean.
        for name, src in UNPARSABLE_FIXTURE.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(src)
        inc = scan(tmp)
        if inc["verdict"] != "INCONCLUSIVE":
            failures.append("an unparsable gate produced %s, not INCONCLUSIVE" % inc["verdict"])

    if failures:
        for f in failures:
            print("SELFTEST FAIL: %s" % f)
        return DEFECTS_FOUND
    print("selftest OK -- %d known-bad fired, %d known-good did not, an unparsable file"
          % (len(KNOWN_BAD), len(KNOWN_GOOD)))
    print("returned INCONCLUSIVE rather than CLEAN, and a file not named a gate was")
    print("not scanned at all.")
    return CLEAN


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="A file named a gate must be able to fail.",
        epilog="Verdicts: CLEAN=0, DEFECTS-FOUND=1, INCONCLUSIVE=2.",
    )
    ap.add_argument("path", nargs="?", default=".", help="directory to scan (default: .)")
    ap.add_argument("--suffix", default="_gate.py", help="filename suffix that promises a gate")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--selftest", action="store_true", help="prove it fires, and that it does not")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if not os.path.isdir(args.path):
        print("INCONCLUSIVE: not a directory: %s" % args.path)
        return INCONCLUSIVE

    result = scan(args.path, args.suffix)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return {"CLEAN": CLEAN, "DEFECTS-FOUND": DEFECTS_FOUND, "INCONCLUSIVE": INCONCLUSIVE}[result["verdict"]]
    return report(result)


if __name__ == "__main__":
    sys.exit(main())
