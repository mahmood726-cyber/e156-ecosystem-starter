#!/usr/bin/env python3
"""pass-to-pass.py -- every test that passed BEFORE the agent's change must still
pass AFTER it. "The new test passes" is not enough.

WHAT IT IS. Two commands around any change an AI agent makes:

    snapshot   run your pytest suite now, record which tests pass
    compare    run it again after the change, list every test that USED to pass
               and now fails, errors, is skipped, or has disappeared

A test going from pass to anything else is a REGRESSION, whatever the reason.
New tests and tests that start passing are reported but never count against you.

WHY IT EXISTS. Coding agents fix the issue in front of them and quietly break
something next to it; a skip or a deleted test then hides it. Evidence:
  - TDAD (arXiv:2603.17973): on SWE-bench Verified, showing the agent WHICH
    existing tests its change touches cut regressions by 70% (6.08% -> 1.82%).
    Telling it to "do TDD" in prose, without that test list, made it WORSE
    (9.94%). A concrete before/after test list beats an instruction.
  - hacktrace (arXiv:2610.03055): deleting the test that exposes a bug is one of
    the shortcuts a coding agent takes to get a passing grade.
  - SWE-ABS (arXiv:2603.00520) and Wang et al. (arXiv:2503.15223): a large share
    of "solved" benchmark patches pass the target test and are still wrong.
The kit's honest-ratchet already refuses a test that is deleted or marked skip
in the SOURCE. This catches what it cannot: a test that still exists but now
fails, errors, or calls pytest.skip() at run time.

USAGE
    python scripts/pass-to-pass.py snapshot --cmd "python -m pytest -q" --out before.json
    ... let the agent make its change ...
    python scripts/pass-to-pass.py compare --before before.json --cmd "python -m pytest -q"
    python scripts/pass-to-pass.py compare --before before.json --after after.json
    python scripts/pass-to-pass.py --selftest       # prove it fires, and does not

    --cmd must be a pytest command: the script adds --junitxml=<temp file> to it
          and reads that file. Use the SAME command both times; a narrower
          command makes tests "disappear", which is reported (the safe direction).
    --timeout  seconds per run (default 1800)
    --json     machine-readable output

VERDICTS -- the same three the rest of this kit uses.
    KEPT           0   every test that passed before still passes
    REGRESSED      1   at least one test went from pass to fail / error / skip / missing
    INCONCLUSIVE   2   could not tell: no result file was written, no test ran, a
                       run timed out, the snapshot is unreadable, or nothing passed
                       before. "Could not check" is never reported as a pass.

WHAT IT DOES NOT CHECK, named rather than implied.
  - It compares test OUTCOMES, not test CONTENTS. A test edited to assert less
    still "passes". Read test diffs; pair with blank-and-rerun.py.
  - pytest only (anything that writes JUnit XML through --junitxml).
  - A flaky test will show up as a regression. That is deliberate: re-run, and if
    it is flaky, say so in the PR. Never hide it by dropping the test.

Offline, standard library only, no API key, no model call. MIT-licensed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

VERSION = "1.0.0"

VERDICT_CODE = dict([("KEPT", 0), ("REGRESSED", 1), ("INCONCLUSIVE", 2)])


def parse_junit(path: str) -> dict:
    """{test id: 'passed' | 'failed' | 'error' | 'skipped'} from a JUnit XML file."""
    tests = {}
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        cls, name = case.get("classname", ""), case.get("name", "")
        tid = "%s::%s" % (cls, name) if cls else name
        tags = {child.tag for child in case}
        if "error" in tags:
            outcome = "error"
        elif "failure" in tags:
            outcome = "failed"
        elif "skipped" in tags:
            outcome = "skipped"
        else:
            outcome = "passed"
        # a test that errors in teardown appears twice: the worse outcome wins
        if tests.get(tid) not in (None, "passed"):
            continue
        tests[tid] = outcome
    return tests


def run_suite(cmd: str, cwd: str = ".", timeout: int = 1800) -> dict:
    """Run `cmd --junitxml=<tmp>` and return a snapshot dict (tests may be empty)."""
    snap = dict(version=VERSION, cmd=cmd, exit_code=None, tests={}, problem="")
    fd, xml_path = tempfile.mkstemp(prefix="pass-to-pass-", suffix=".xml")
    os.close(fd)
    os.remove(xml_path)  # so "no file" means pytest never wrote one
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    full = "%s --junitxml=%s" % (cmd, chr(34) + xml_path + chr(34))
    try:
        r = subprocess.run(full, shell=True, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        snap["exit_code"] = r.returncode
        if not os.path.isfile(xml_path):
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            snap["problem"] = "no JUnit result was written (is --cmd a pytest command?): %s" % " | ".join(tail)
        else:
            snap["tests"] = parse_junit(xml_path)
    except subprocess.TimeoutExpired:
        snap["problem"] = "timed out after %ds" % timeout
    except ET.ParseError as exc:
        snap["problem"] = "the JUnit result could not be read: %s" % exc
    finally:
        if os.path.isfile(xml_path):
            os.remove(xml_path)
    return snap


def compare(before: dict, after: dict) -> dict:
    """The verdict for a before/after pair of snapshots."""
    result = dict(version=VERSION, verdict="INCONCLUSIVE", reason="", regressions=[],
                  now_passing=[], new_tests=[], cmd_changed=before.get("cmd") != after.get("cmd"))
    for label, snap in (("before", before), ("after", after)):
        if snap.get("problem"):
            result["reason"] = "%s run: %s" % (label, snap["problem"])
            return result
    b, a = before.get("tests", {}), after.get("tests", {})
    passed_before = sorted(t for t, o in b.items() if o == "passed")
    if not passed_before:
        result["reason"] = "no test passed in the BEFORE snapshot, so there is nothing to keep"
        return result
    if not a:
        result["reason"] = "no test ran in the AFTER run"
        return result
    for t in passed_before:
        now = a.get(t, "missing")
        if now != "passed":
            result["regressions"].append(dict(test=t, now=now))
    result["now_passing"] = sorted(t for t, o in a.items() if o == "passed" and t in b and b[t] != "passed")
    result["new_tests"] = sorted(t for t in a if t not in b)
    if result["regressions"]:
        result["verdict"] = "REGRESSED"
        result["reason"] = "%d of %d previously passing tests no longer pass" % (
            len(result["regressions"]), len(passed_before))
    else:
        result["verdict"] = "KEPT"
        result["reason"] = "all %d previously passing tests still pass" % len(passed_before)
    return result


def report(result: dict) -> int:
    print("pass-to-pass v%s" % result["version"])
    if result["cmd_changed"]:
        print("NOTE: the test command differs between the two runs; tests the second")
        print("      command did not run are reported as missing.")
    for row in result["regressions"]:
        print("  %-8s %s" % (row["now"].upper(), row["test"]))
    if result["now_passing"]:
        print("  now passing (was not before): %d" % len(result["now_passing"]))
    if result["new_tests"]:
        print("  new tests: %d" % len(result["new_tests"]))
    print()
    print("%s: %s" % (result["verdict"], result["reason"]))
    if result["verdict"] == "REGRESSED":
        print("The change broke, skipped or removed tests that used to pass. Fix the code,")
        print("or explain in the PR why the old test was wrong. Never delete, skip or loosen")
        print("the test to make this check pass.")
    return VERDICT_CODE[result["verdict"]]


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            snap = json.load(fh)
        if not isinstance(snap.get("tests"), dict):
            raise ValueError("no 'tests' table")
        return snap
    except (OSError, ValueError) as exc:
        return dict(cmd=None, tests={}, problem="snapshot %s unreadable: %s" % (path, exc))


# --------------------------------------------------------------------------
# Selftest -- BOTH DIRECTIONS, plus the inconclusive ones.
# --------------------------------------------------------------------------

SELF_TESTS = (
    "def test_mean():\n"
    "    assert sum([1, 2, 3]) / 3 == 2\n"
    "\n"
    "def test_size():\n"
    "    assert len([1, 2]) == 2\n"
)


def selftest() -> int:
    failures = []
    pytest_cmd = chr(34) + sys.executable + chr(34) + " -m pytest -q -p no:cacheprovider"

    def scenario(new_src):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_self.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(SELF_TESTS)
            before = run_suite(pytest_cmd, tmp, 300)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_src)
            return compare(before, run_suite(pytest_cmd, tmp, 300))

    cases = [
        ("unchanged suite", SELF_TESTS, "KEPT"),
        ("a new passing test", SELF_TESTS + "\ndef test_new():\n    assert True\n", "KEPT"),
        ("a test now failing", SELF_TESTS.replace("== 2\n", "== 3\n", 1), "REGRESSED"),
        ("a test now skipped at run time",
         SELF_TESTS.replace("def test_size():\n", "def test_size():\n    import pytest; pytest.skip('x')\n"),
         "REGRESSED"),
        ("a test deleted", SELF_TESTS.split("\ndef test_size")[0] + "\n", "REGRESSED"),
        ("every test deleted", "", "INCONCLUSIVE"),
    ]
    for label, src, want in cases:
        got = scenario(src)["verdict"]
        if got != want:
            failures.append("%s gave %s, not %s" % (label, got, want))
    with tempfile.TemporaryDirectory() as tmp:
        snap = run_suite(chr(34) + sys.executable + chr(34) + " -c pass", tmp, 60)
        if compare(snap, snap)["verdict"] != "INCONCLUSIVE":
            failures.append("a non-pytest command was not INCONCLUSIVE")
    if failures:
        for f in failures:
            print("SELFTEST FAIL: %s" % f)
        return VERDICT_CODE["REGRESSED"]
    print("selftest OK -- unchanged and added tests are KEPT; a test that now fails, is")
    print("skipped at run time, or was deleted is REGRESSED; no tests or no result file")
    print("is INCONCLUSIVE.")
    return VERDICT_CODE["KEPT"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Every test that passed before a change must still pass after it.",
        epilog="Verdicts: KEPT=0, REGRESSED=1, INCONCLUSIVE=2.",
    )
    ap.add_argument("--selftest", action="store_true", help="prove it fires, and that it does not")
    sub = ap.add_subparsers(dest="action")
    s = sub.add_parser("snapshot", help="record which tests pass now")
    s.add_argument("--cmd", required=True, help="pytest command, run from --root")
    s.add_argument("--out", required=True, help="where to write the snapshot JSON")
    s.add_argument("--root", default=".")
    s.add_argument("--timeout", type=int, default=1800)
    c = sub.add_parser("compare", help="compare against a snapshot")
    c.add_argument("--before", required=True, help="snapshot JSON from before the change")
    c.add_argument("--after", help="a second snapshot JSON (instead of --cmd)")
    c.add_argument("--cmd", help="pytest command to run now (instead of --after)")
    c.add_argument("--root", default=".")
    c.add_argument("--timeout", type=int, default=1800)
    c.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.action == "snapshot":
        snap = run_suite(args.cmd, args.root, args.timeout)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2, sort_keys=True)
        n = sum(1 for o in snap["tests"].values() if o == "passed")
        if snap["problem"]:
            print("INCONCLUSIVE: %s" % snap["problem"])
            return VERDICT_CODE["INCONCLUSIVE"]
        print("snapshot written to %s: %d tests, %d passing" % (args.out, len(snap["tests"]), n))
        return VERDICT_CODE["KEPT"]
    if args.action == "compare":
        if bool(args.after) == bool(args.cmd):
            ap.error("compare needs exactly one of --after or --cmd")
        before = _load(args.before)
        after = _load(args.after) if args.after else run_suite(args.cmd, args.root, args.timeout)
        result = compare(before, after)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return VERDICT_CODE[result["verdict"]]
        return report(result)
    ap.error("choose snapshot or compare (or --selftest)")
    return VERDICT_CODE["INCONCLUSIVE"]


if __name__ == "__main__":
    sys.exit(main())
