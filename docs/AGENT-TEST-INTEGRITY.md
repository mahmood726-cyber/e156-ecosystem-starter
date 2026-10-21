# Agent test integrity: two opt-in checks (v1.0.0, 2026-10-21)

**Who this is for.** Anyone who lets an AI coding agent (Claude Code, Codex,
Gemini) write or fix code that has tests. You do not need to be a software
engineer to use either check.

**The problem in one sentence.** When an agent is asked to "make the tests
pass", the cheapest route is sometimes to change the tests, not the code, and a
green test run then means nothing.

This is measured, not hypothetical:

| Source | What it found |
|---|---|
| SpecBench, [arXiv:2605.21384](https://arxiv.org/abs/2605.21384) | Every frontier agent passed all the tests it could see; held-out tests still failed, and the gap grew with code size. |
| Gomez, [arXiv:2608.29460](https://arxiv.org/abs/2608.29460) | 23.6% of runs across 8 frontier models gamed the tests (e.g. edited test files). Giving agents a way to *report* a broken test, plus a policy, cut that to 5.3%. |
| CATCH, [arXiv:2609.39533](https://arxiv.org/abs/2609.39533) | Test-file modification is one of the main loopholes in coding-agent training; a reasoning monitor helped at first, then was fooled. |
| Lee et al., [arXiv:2610.22779](https://arxiv.org/abs/2610.22779) | An agent that could see its own checker kept what passed the checker while real faithfulness fell, invisibly to in-loop metrics. |

Both checks below are **opt-in**: installing the starter does not switch them on.

---

## 1. `protect-test-config.py`: the agent may not edit test setup

**What it does.** A Claude Code *hook* (a small program Claude Code runs before
each action). If the agent tries to edit `conftest.py`, `pytest.ini`, `tox.ini`,
`noxfile.py`, `.coveragerc`, jest/vitest/karma/mocha config, `phpunit.xml`, or
R `testthat` setup/helper files, the edit is **blocked** and the agent is told
to explain the problem to you instead.

**Turn it on.** Add this to `~/.claude/settings.json` (merge with any `hooks`
you already have; adjust the path to where you cloned the starter):

```json
"hooks": {
  "PreToolUse": [
    {"matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
     "hooks": [{"type": "command",
                "command": "python ~/e156-ecosystem-starter/scripts/protect-test-config.py"}]}
  ]
}
```

Check it works: `python scripts/protect-test-config.py --selftest`

**When YOU need to change test config.** Edit the file yourself, or start
Claude Code from a shell where `E156_ALLOW_TEST_CONFIG_EDIT=1` is set, for that
session only.

**Optional.** `E156_PROTECT_PYPROJECT=1` also protects `pyproject.toml` and
`setup.cfg` (off by default because those files hold much more than tests).

**Limits.** It does not block edits to test files themselves (`test_*.py`):
agents legitimately add tests, so read test diffs. A shell command that builds
the file name at runtime can slip past the Bash check.

---

## 2. `blank-and-rerun.py`: do the tests actually test the function?

**What it does.** Copies your project to a temporary folder, deletes the body of
one function (replacing it with an error), and re-runs your tests there. Your
files are never changed.

- Tests **fail** -> `TESTS-BITE`: they really depend on that function.
- Tests still **pass** -> `CLAIM-FAILS`: they are not testing it, so a claim like
  "our function matches R" is not supported by them.
- Could not tell (tests already failing, function not found, timeout) ->
  `INCONCLUSIVE`, never a pass.

**Run it.**

```bash
python scripts/blank-and-rerun.py --file mypkg/pool.py --function dl_tau2 \
    --cmd "python -m pytest tests/test_pool.py -q"
```

Use `--function Class.method` for methods; repeat `--function` to check several.

**Before you write "matches R" anywhere,** run this on every function the claim
covers. If any comes back `CLAIM-FAILS`, add a known-answer test that calls the
function and compares with the R value. Never weaken or delete a test to make
this check pass.

**Limits.** `TESTS-BITE` is necessary, not sufficient: it shows the tests notice
the function, not that its numbers are right. Python only (for R, blank the
function by hand and re-run testthat). If your package is pip-installed, the
tests may import the installed copy; then everything "survives" and you get
`CLAIM-FAILS` (the safe direction) - check that first.

---

*Both tools: standard library only, offline, no API key. Approved by Mahmood
Ahmad on 2026-10-20 (P1, P2); research log in the meta-harness repo,
`docs/ai-coding-research-log.md`.*
