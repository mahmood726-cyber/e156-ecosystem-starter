# LANE BRIEF — {LANE}

<!-- Replace every FILL marker below, then hand this file to scripts/delegate-lane.py --brief.
     delegate-lane.py REFUSES a brief that still contains a FILL marker, or whose
     anti-hard-coding + abort block below is not present word for word.
     {LANE}, {BASE} and {VENDOR} are substituted by delegate-lane.py. -->

You are a delegated lane working in your own isolated clone, detached at base `{BASE}`.
Vendor: {VENDOR}. Nobody is watching this terminal; stdin is closed.

## Goal
<FILL: one or two sentences: what must be true when you are done>

## Base
`{BASE}` — the clone is already checked out there. Do not fetch, rebase or switch branches.

## Scope (files you may touch)
<FILL: list the files or directories, one per line>

## Non-goals (do NOT do these)
<FILL: what is out of scope, e.g. "do not refactor X", "do not touch CI">

## Acceptance commands
Run these; paste each command and its exact pass/fail counts into the report.
<FILL: e.g. python -m pytest tests/ -q>

## Rules (verbatim — do not edit this block)
<!-- lane-rules:begin -->
- Never hard-code an expected value, a test answer, a fixture row or a special case for a named input to make a check pass. Fix the cause or report that you could not.
- Never delete, skip, xfail, weaken or re-scope an existing test, check, hook or tolerance.
- ABORT RULE: if the only way to make an acceptance command pass is to break a rule above, STOP. Write the report with status BLOCKED and say what you would have had to loosen and why.
- Do not commit, push or open a pull request. Leave every change uncommitted; the integrator lands it.
- A command's exit code is not evidence. Evidence is an artefact you can name: a test count, a file, a line of output.
<!-- lane-rules:end -->

## Report (your finish condition)
Write `LANE_REPORT.json` in the clone root. It must parse as JSON and have this shape:

```json
{"lane": "{LANE}", "status": "DONE|BLOCKED", "summary": "<2-3 sentences>",
 "files_changed": ["<path>"],
 "commands_run": [{"cmd": "<command>", "result": "<e.g. 41 passed, 0 failed>"}],
 "blocked_reason": "<empty when DONE; what you would have had to loosen when BLOCKED>"}
```

The lane is judged ENDED-REPORTED only when this file exists and parses with a
`status` of DONE or BLOCKED. A lane that exits without it is ENDED-NO-REPORT,
whatever its log says.
