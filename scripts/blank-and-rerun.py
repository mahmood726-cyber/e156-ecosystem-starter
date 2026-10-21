#!/usr/bin/env python3
"""blank-and-rerun.py -- if you delete the function and the tests still pass, the
tests were not testing it. So "it matches R" was never shown.

WHAT IT IS. A one-command check for a claim like "our Python function matches
the R reference". It copies your project to a throwaway folder, replaces the body
of the named function with `raise NotImplementedError`, and runs your test
command there. Your own files are never touched.

    tests FAIL with the function blanked   -> the tests BITE: they depend on it
    tests still PASS with it blanked       -> the claim FAILS: whatever the tests
                                              check, it is not this function

WHY IT EXISTS. A test can pass for reasons unrelated to the code it names: it
compares a stored number to itself, it is skipped, it tests a cached file, or an
agent quietly made the expected value come from the function under test. A
passing suite plus "matches R" is then two true statements that prove nothing.
This is the bluntest form of mutation testing -- one mutant per function, the
whole body gone -- and it is enough to catch the commonest hollow test. Evidence
it is needed when agents write the tests:
  - SpecBench (arXiv:2605.21384): agents saturate the tests they can SEE while
    held-out tests fail; a visible pass is not evidence of correctness.
  - "When Can You Trust an Agent's Own Verifier?" (arXiv:2610.22779): with
    access to its verifier, an agent kept the claims that passed while held-out
    faithfulness fell -- and in-loop metrics did not show it.
  - Mutation-guided test generation at Meta (arXiv:2501.12862) uses surviving
    mutants as the signal that a test is too weak; this is the minimal version.
Approved by Mahmood on 2026-10-20 as P2.

USAGE
    python scripts/blank-and-rerun.py --file mypkg/pool.py --function dl_tau2 \
        --cmd "python -m pytest tests/test_pool.py -q"
    python scripts/blank-and-rerun.py --file mypkg/pool.py \
        --function dl_tau2 --function Pooler.fit --cmd "python -m pytest -q"
    python scripts/blank-and-rerun.py --selftest      # prove it fires, and does not

    --root     project folder to copy (default: current directory)
    --function repeatable; Class.method for methods
    --timeout  seconds per test run (default 900)
    --json     machine-readable output

VERDICTS -- the same three the rest of this kit uses.
    TESTS-BITE     0   every blanked function made the tests fail
    CLAIM-FAILS    1   at least one function was blanked and the tests still passed
    INCONCLUSIVE   2   could not tell: the tests fail even BEFORE blanking, the
                       function was not found, the copy did not compile, or a run
                       timed out. "Could not check" is never reported as a pass.

WHAT IT DOES NOT CHECK, named rather than implied.
  - TESTS-BITE means the tests NOTICE the function is gone. It does not mean the
    numbers are right. A test that only checks "returns a float" bites, and is
    still a weak test. Pair this with a known-answer test against R output.
  - Python only. For an R function, blank it by hand (`f <- function(...)
    stop("blanked")`) and re-run testthat; the logic is identical.
  - If your package is INSTALLED (pip install, or an editable install pointing at
    the original folder), the tests may import that copy, not the blanked one, and
    every function will "survive". That errs toward CLAIM-FAILS, never toward a
    false pass -- but if every function survives, check this first.
  - Use RELATIVE paths in --cmd. An absolute path points back at your real files.

Offline, standard library only, no API key, no model call. MIT-licensed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile

VERSION = "1.0.0"

TESTS_BITE, CLAIM_FAILS, INCONCLUSIVE = 0, 1, 2
VERDICT_CODE = dict([("TESTS-BITE", 0), ("CLAIM-FAILS", 1), ("INCONCLUSIVE", 2)])

STUB = 'raise NotImplementedError("blanked by blank-and-rerun")'

SKIP_DIRS = (".git", "__pycache__", "node_modules", ".venv", "venv", ".tox",
             ".mypy_cache", ".pytest_cache", ".nox")


def find_function(tree: ast.AST, dotted: str):
    """The FunctionDef for `name` or `Class.method`, or None."""
    nodes = tree.body
    parts = dotted.split(".")
    for i, part in enumerate(parts):
        found = None
        for n in nodes:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part:
                found = n  # the LAST definition wins, as at import time
        if found is None:
            return None
        if i < len(parts) - 1:
            if not isinstance(found, ast.ClassDef):
                return None
            nodes = found.body
        elif isinstance(found, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return found
    return None


def blank_function(src: str, dotted: str) -> str:
    """Return `src` with the body of `dotted` replaced by a single raise.

    Raises KeyError if the function is not there, SyntaxError if the source does
    not parse (before or after). The signature, decorators and everything else
    in the file are left exactly as they were.
    """
    tree = ast.parse(src)
    node = find_function(tree, dotted)
    if node is None:
        raise KeyError(dotted)
    lines = src.splitlines(True)
    first = node.body[0]
    start = min([first.lineno] + [d.lineno for d in getattr(first, "decorator_list", [])]) - 1
    end = node.end_lineno - 1
    if start + 1 == node.lineno:
        # one-liner `def f(x): return x` -- keep everything up to the body
        prefix = lines[start].encode("utf-8")[:first.col_offset].decode("utf-8")
    else:
        line = lines[start]
        prefix = line[: len(line) - len(line.lstrip())]
    newline = "\n" if lines[end].endswith("\n") or end + 1 < len(lines) else ""
    out = "".join(lines[:start]) + prefix + STUB + newline + "".join(lines[end + 1:])
    ast.parse(out)  # never hand back a file that does not compile
    return out


def _copy_project(root: str, dest: str) -> None:
    shutil.copytree(root, dest, ignore=shutil.ignore_patterns(*SKIP_DIRS), dirs_exist_ok=True)


def _run_tests(cmd: str, cwd: str, timeout: int):
    """(exit_code or None on timeout, last lines of output)."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, "timed out after %ds" % timeout
    tail = (r.stdout + r.stderr).strip().splitlines()[-5:]
    return r.returncode, " | ".join(tail)


def check(root: str, rel_file: str, functions: list, cmd: str, timeout: int = 900) -> dict:
    """Run the baseline, then one fresh copy per blanked function."""
    root = os.path.abspath(root)
    result = dict(version=VERSION, root=root, file=rel_file, cmd=cmd,
                  baseline=None, functions=[], verdict="INCONCLUSIVE", reason="")
    target = os.path.join(root, rel_file)
    if not os.path.isfile(target):
        result["reason"] = "file not found: %s" % rel_file
        return result
    with open(target, encoding="utf-8") as fh:
        original = fh.read()

    with tempfile.TemporaryDirectory(prefix="blank-and-rerun-") as tmp:
        base_dir = os.path.join(tmp, "baseline")
        _copy_project(root, base_dir)
        code, tail = _run_tests(cmd, base_dir, timeout)
        result["baseline"] = dict(exit_code=code, tail=tail)
        if code != 0:
            result["reason"] = ("the tests do not pass BEFORE blanking (exit %s), so blanking "
                                "cannot show anything. Fix or explain the failing suite first." % code)
            return result

        for i, fn in enumerate(functions):
            row = dict(function=fn, exit_code=None, outcome="", tail="")
            try:
                blanked = blank_function(original, fn)
            except KeyError:
                row["outcome"] = "NOT-FOUND"
                result["functions"].append(row)
                continue
            except SyntaxError as exc:
                row["outcome"] = "DOES-NOT-COMPILE"
                row["tail"] = str(exc)[:200]
                result["functions"].append(row)
                continue
            run_dir = os.path.join(tmp, "blank-%d" % i)
            _copy_project(root, run_dir)
            with open(os.path.join(run_dir, rel_file), "w", encoding="utf-8") as fh:
                fh.write(blanked)
            code, tail = _run_tests(cmd, run_dir, timeout)
            row["exit_code"], row["tail"] = code, tail
            if code is None:
                row["outcome"] = "TIMEOUT"
            elif code == 0:
                row["outcome"] = "SURVIVED"
            else:
                row["outcome"] = "BITES"
            result["functions"].append(row)

    outcomes = [r["outcome"] for r in result["functions"]]
    if "SURVIVED" in outcomes:
        result["verdict"] = "CLAIM-FAILS"
        result["reason"] = "the tests still pass with %s blanked" % ", ".join(
            r["function"] for r in result["functions"] if r["outcome"] == "SURVIVED")
    elif outcomes and all(o == "BITES" for o in outcomes):
        result["verdict"] = "TESTS-BITE"
        result["reason"] = "every blanked function made the tests fail"
    else:
        result["reason"] = "not every function could be checked: %s" % ", ".join(
            "%s=%s" % (r["function"], r["outcome"]) for r in result["functions"])
    return result


def report(result: dict) -> int:
    print("blank-and-rerun v%s   file %s   cmd: %s" % (result["version"], result["file"], result["cmd"]))
    if result["baseline"] is not None:
        print("baseline (nothing blanked): exit %s" % result["baseline"]["exit_code"])
    for row in result["functions"]:
        print("  %-12s %s" % (row["outcome"], row["function"]))
        if row["outcome"] == "SURVIVED":
            print("               the tests passed WITHOUT this function: they do not test it.")
    print()
    print("%s: %s" % (result["verdict"], result["reason"]))
    if result["verdict"] == "CLAIM-FAILS":
        print("A matches-R (or any correctness) claim resting on these tests is NOT shown.")
        print("FIX: add a known-answer test that calls the function and compares to the R")
        print("     value. Do not weaken or delete anything to make this check pass.")
    if result["verdict"] == "TESTS-BITE":
        print("The tests depend on these functions. That is necessary, not sufficient:")
        print("it does not show the numbers are right. Keep the known-answer test against R.")
    return VERDICT_CODE[result["verdict"]]


# --------------------------------------------------------------------------
# Selftest -- BOTH DIRECTIONS, plus the inconclusive ones.
# --------------------------------------------------------------------------

SELF_MOD = (
    "def mean(xs):\n"
    "    return sum(xs) / len(xs)\n"
    "\n"
    "def unused():\n"
    "    return 42\n"
    "\n"
    "class Pool:\n"
    "    def size(self, xs): return len(xs)\n"
)
SELF_CHECK = (
    "import mod\n"
    "assert mod.mean([1, 2, 3]) == 2\n"
    "assert mod.Pool().size([1, 2]) == 2\n"
)
NESTED = (
    "def outer():\n"
    "    @staticmethod\n"
    "    def inner():\n"
    "        return 1\n"
    "    return inner\n"
)


def selftest() -> int:
    failures = []
    if "@staticmethod" in blank_function(NESTED, "outer"):
        failures.append("a decorated nested def was not blanked cleanly")
    if "return len" in blank_function(SELF_MOD, "Pool.size"):
        failures.append("a one-line method was not blanked")
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "mod.py"), "w", encoding="utf-8") as fh:
            fh.write(SELF_MOD)
        with open(os.path.join(tmp, "check.py"), "w", encoding="utf-8") as fh:
            fh.write(SELF_CHECK)
        cmd = chr(34) + sys.executable + chr(34) + " check.py"
        r = check(tmp, "mod.py", ["mean", "Pool.size"], cmd, timeout=120)
        if r["verdict"] != "TESTS-BITE":
            failures.append("tested functions gave %s, not TESTS-BITE" % r["verdict"])
        r = check(tmp, "mod.py", ["mean", "unused"], cmd, timeout=120)
        if r["verdict"] != "CLAIM-FAILS":
            failures.append("an untested function gave %s, not CLAIM-FAILS" % r["verdict"])
        r = check(tmp, "mod.py", ["no_such_function"], cmd, timeout=120)
        if r["verdict"] != "INCONCLUSIVE":
            failures.append("a missing function gave %s, not INCONCLUSIVE" % r["verdict"])
        with open(os.path.join(tmp, "mod.py"), encoding="utf-8") as fh:
            if fh.read() != SELF_MOD:
                failures.append("the ORIGINAL file was modified")
        with open(os.path.join(tmp, "check.py"), "a", encoding="utf-8") as fh:
            fh.write("assert False\n")
        r = check(tmp, "mod.py", ["mean"], cmd, timeout=120)
        if r["verdict"] != "INCONCLUSIVE":
            failures.append("a suite that fails before blanking gave %s" % r["verdict"])
    if failures:
        for f in failures:
            print("SELFTEST FAIL: %s" % f)
        return CLAIM_FAILS
    print("selftest OK -- tested functions BITE, an untested one makes the claim FAIL,")
    print("a missing function and an already-red suite are INCONCLUSIVE, and the")
    print("original file was not touched.")
    return TESTS_BITE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Blank a function and re-run the tests: if they still pass, they do not test it.",
        epilog="Verdicts: TESTS-BITE=0, CLAIM-FAILS=1, INCONCLUSIVE=2.",
    )
    ap.add_argument("--root", default=".", help="project folder to copy (default: .)")
    ap.add_argument("--file", help="Python file holding the function, relative to --root")
    ap.add_argument("--function", action="append", default=[], help="name or Class.method; repeatable")
    ap.add_argument("--cmd", help="test command, run from the copied project root")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per test run")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--selftest", action="store_true", help="prove it fires, and that it does not")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not (args.file and args.function and args.cmd):
        ap.error("--file, --function and --cmd are required (or use --selftest)")
    result = check(args.root, args.file, args.function, args.cmd, args.timeout)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return VERDICT_CODE[result["verdict"]]
    return report(result)


if __name__ == "__main__":
    sys.exit(main())
