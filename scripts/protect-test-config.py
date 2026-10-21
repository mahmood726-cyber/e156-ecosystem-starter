#!/usr/bin/env python3
"""protect-test-config.py -- an OPT-IN Claude Code hook: the agent may not edit the
files that decide what "the tests passed" means.

WHAT IT IS. A PreToolUse hook. Before the agent runs Edit / Write / MultiEdit /
NotebookEdit -- or a Bash command that writes to a file -- it checks the target
against a short list of TEST SETUP AND CONFIG files: conftest.py, pytest.ini,
tox.ini, noxfile.py, .coveragerc, jest/vitest/karma/mocha config, phpunit.xml,
and the testthat setup/helper files in R. A match is BLOCKED (exit 2), and the
agent is told why and what to do instead.

WHY IT EXISTS. Changing the test harness is the cheapest way for an agent to turn
red into green without fixing anything: skip a marker in conftest.py, add
`--deselect` to pytest.ini, lower a coverage threshold. Published measurements:
  - SpecBench (arXiv:2605.21384): every frontier agent saturated the VISIBLE test
    suite while held-out tests still failed; the gap grew ~28 points per tenfold
    increase in code size.
  - Gomez (arXiv:2608.29460): across 8 frontier models, 23.6% of runs reward-
    hacked (editing test files or test data counted as hacking) before any
    intervention.
  - CATCH (arXiv:2609.39533): test-file modification is one of the loophole
    classes built into its coding-RL testbed.
The house rule "never loosen a test" was text. This makes its commonest form a
refusal the agent cannot argue with.

WHAT THE AGENT IS TOLD INSTEAD. Stop, and say which test configuration you
believe is wrong and why. A human then edits it, or sets the override below for
one session. Disclosure beats a quiet edit: in the same Gomez paper an explicit
"report the broken test" route plus a policy cut hacking from 23.6% to 5.3%.

THE OVERRIDE IS FOR HUMANS. Set E156_ALLOW_TEST_CONFIG_EDIT=1 in the shell that
LAUNCHES Claude Code (not inside the session). The hook reads its own process
environment, which a command typed by the agent does not change.

OPTIONAL WIDER SCOPE. pyproject.toml and setup.cfg often hold [tool.pytest] or
[coverage] settings, but they hold everything else too, so they are NOT blocked by
default. Set E156_PROTECT_PYPROJECT=1 to block them as well.

WHAT IT DOES NOT CHECK, named rather than implied.
  - Bash detection is a heuristic: a protected file name plus a write-shaped
    operator (>, >>, sed -i, tee, rm, mv, cp, truncate, git checkout/restore).
    A command that builds the file name at runtime (python -c "open(...)") is
    not caught.
  - It does not stop edits to the TEST FILES themselves (test_*.py). That is a
    bigger, noisier rule: agents legitimately add tests. Review test diffs.
  - It does not check what a human commits. Pair it with code review.

INSTALL (opt-in -- nothing in the starter turns this on for you): see
docs/AGENT-TEST-INTEGRITY.md for the settings.json snippet and a plain-language
walkthrough.

EXIT CODES (Claude Code's PreToolUse contract)
    0   allowed
    2   BLOCKED -- the reason on stderr is shown to the agent
    1   the hook could not read its input; Claude Code shows the error to the
        human and does not block. Fail-open here is deliberate and named: a hook
        that blocked every tool call on malformed input would be switched off,
        and a switched-off guard protects nothing.

    python scripts/protect-test-config.py --selftest   # prove it fires, and does not

Offline, standard library only, no API key, no model call. MIT-licensed.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

VERSION = "1.0.0"

ALLOWED, ERROR, BLOCKED = 0, 1, 2

# Matched against the file's BASENAME, case-insensitively.
PROTECTED_NAMES = (
    "conftest.py",
    "pytest.ini",
    "tox.ini",
    "noxfile.py",
    ".coveragerc",
    "jest.config.*",
    "vitest.config.*",
    "karma.conf.*",
    ".mocharc*",
    "phpunit.xml*",
    "testthat.r",
)

# Matched against the path's last two components ("testthat/setup-db.R").
PROTECTED_R_TESTTHAT = ("testthat/setup*.r", "testthat/helper*.r")

OPTIONAL_NAMES = ("pyproject.toml", "setup.cfg")

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
PATH_KEYS = ("file_path", "notebook_path", "path")

# A write-shaped Bash command. Deliberately narrow: READING conftest.py (cat,
# grep, pytest itself) must stay allowed.
WRITE_SHAPED = re.compile(
    r"(>>?|\bsed\s+(-[a-zA-Z]*i|--in-place)|\btee\b|\brm\b|\bmv\b|\bcp\b|\btruncate\b"
    r"|\bgit\s+(checkout|restore)\b|\bperl\s+-[a-zA-Z]*i|Set-Content|Out-File|Remove-Item)"
)


def _names() -> tuple:
    if os.environ.get("E156_PROTECT_PYPROJECT") == "1":
        return PROTECTED_NAMES + OPTIONAL_NAMES
    return PROTECTED_NAMES


def protected_reason(path: str):
    """The pattern that makes `path` protected, or None."""
    norm = path.replace("\\", "/").rstrip("/").lower()
    base = norm.rsplit("/", 1)[-1]
    for pat in _names():
        if fnmatch.fnmatch(base, pat):
            return pat
    tail = "/".join(norm.split("/")[-2:])
    for pat in PROTECTED_R_TESTTHAT:
        if fnmatch.fnmatch(tail, pat):
            return pat
    return None


def bash_targets(command: str) -> list:
    """Protected file names that a write-shaped Bash command mentions."""
    if not WRITE_SHAPED.search(command):
        return []
    hits = []
    for token in re.split(r"[\s'\"`;|&()<>=]+", command):
        if token and protected_reason(token):
            hits.append(token)
    return hits


def decide(payload: dict) -> tuple:
    """(exit_code, message) for one PreToolUse payload."""
    if os.environ.get("E156_ALLOW_TEST_CONFIG_EDIT") == "1":
        return ALLOWED, ""
    tool = payload.get("tool_name", "")
    args = payload.get("tool_input") or {}
    targets = []
    if tool == "Bash":
        targets = bash_targets(str(args.get("command", "")))
    elif tool in EDIT_TOOLS:
        for key in PATH_KEYS:
            p = args.get(key)
            if isinstance(p, str) and protected_reason(p):
                targets.append(p)
    if not targets:
        return ALLOWED, ""
    return BLOCKED, (
        "BLOCKED by protect-test-config (opt-in hook, v%s): %s is test setup/config.\n"
        "Changing it changes what 'the tests pass' means, so an agent may not edit it.\n"
        "Do NOT work around this. Instead: stop and tell the human which test config\n"
        "you believe is wrong, why, and the exact change you propose. A human makes it,\n"
        "or relaunches with E156_ALLOW_TEST_CONFIG_EDIT=1 for that one session."
        % (VERSION, ", ".join(sorted(set(targets))))
    )


# --------------------------------------------------------------------------
# Selftest -- BOTH DIRECTIONS, as everywhere in this kit.
# --------------------------------------------------------------------------

def _call(tool: str, key: str, value: str) -> dict:
    return dict(tool_name=tool, tool_input=dict([(key, value)]))


WINDOWS_PATH = "proj/sub/pytest.ini".replace("/", chr(92))  # proj<backslash>sub<backslash>pytest.ini

MUST_BLOCK = [
    _call("Edit", "file_path", "/repo/tests/conftest.py"),
    _call("Write", "file_path", WINDOWS_PATH),
    _call("MultiEdit", "file_path", "web/jest.config.ts"),
    _call("Edit", "file_path", "pkg/tests/testthat/setup-data.R"),
    _call("Edit", "file_path", "TOX.INI"),
    _call("NotebookEdit", "notebook_path", "nb/conftest.py"),
    _call("Bash", "command", "sed -i s/fail_under=90/fail_under=50/ .coveragerc"),
    _call("Bash", "command", "echo addopts=--deselect=tests/x.py >> pytest.ini"),
    _call("Bash", "command", "git checkout HEAD~3 -- tests/conftest.py"),
]

MUST_ALLOW = [
    _call("Edit", "file_path", "/repo/src/stats.py"),
    _call("Write", "file_path", "/repo/tests/test_stats.py"),
    _call("Edit", "file_path", "/repo/pyproject.toml"),
    _call("Edit", "file_path", "/repo/docs/conftest-notes.md"),
    _call("Bash", "command", "cat tests/conftest.py"),
    _call("Bash", "command", "python -m pytest -c pytest.ini -q"),
    _call("Read", "file_path", "/repo/tests/conftest.py"),
]

ENV_KEYS = ("E156_ALLOW_TEST_CONFIG_EDIT", "E156_PROTECT_PYPROJECT")


def selftest() -> int:
    failures = []
    saved = dict((k, os.environ.pop(k, None)) for k in ENV_KEYS)
    try:
        for p in MUST_BLOCK:
            if decide(p)[0] != BLOCKED:
                failures.append("MISSED: %r" % (p,))
        for p in MUST_ALLOW:
            if decide(p)[0] != ALLOWED:
                failures.append("FALSE BLOCK: %r" % (p,))
        os.environ["E156_PROTECT_PYPROJECT"] = "1"
        if decide(_call("Edit", "file_path", "pyproject.toml"))[0] != BLOCKED:
            failures.append("E156_PROTECT_PYPROJECT=1 did not protect pyproject.toml")
        del os.environ["E156_PROTECT_PYPROJECT"]
        os.environ["E156_ALLOW_TEST_CONFIG_EDIT"] = "1"
        if decide(MUST_BLOCK[0])[0] != ALLOWED:
            failures.append("the human override did not allow the edit")
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    if failures:
        for f in failures:
            print("SELFTEST FAIL: %s" % f)
        return ERROR
    print("selftest OK -- %d must-block blocked, %d must-allow allowed, the pyproject"
          % (len(MUST_BLOCK), len(MUST_ALLOW)))
    print("opt-in and the human override both behave.")
    return ALLOWED


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    if "--version" in argv:
        print(VERSION)
        return ALLOWED
    try:
        payload = json.loads(sys.stdin.read() or "null")
        if not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
    except ValueError as exc:
        print("protect-test-config: could not read hook input (%s); NOT checked." % exc, file=sys.stderr)
        return ERROR
    code, msg = decide(payload)
    if msg:
        print(msg, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
