# Producing work at the same quality bar — student walkthrough

After running `install.ps1` / `install.sh`, your laptop has the same **enforcement
machinery** Mahmood uses: rules, governance, memory templates, Sentinel, Overmind,
ProjectIndex. This doc covers what to do **next** so you produce work at the same
quality bar he does — not just "with the same tools," but using the same
**method**.

You do not need to use everything below. Pick the parts that fit the work you're
doing. The whole point of shipping the rules is so your AI agent reads them and
nudges you toward the right pattern when it matters.

## TL;DR — 5 steps to your first paper

1. **Install the ecosystem** (this repo) — done if you're reading this.
2. **Scaffold a paper** with the `student` CLI from
   [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter):
   `pip install git+https://github.com/mahmood726-cyber/e156-student-starter.git@main`
   then `student new my-first-paper`.
3. **Use the brainstorm→spec-lock→plan-lock→TDD→audit method** (below).
4. **`git push`** — Sentinel runs as a pre-push hook and blocks the 20 most
   common defects before code leaves your laptop.
5. **`overmind run-once --repo <path>`** before declaring "done". A `PASS` /
   `CERTIFIED` verdict is your ship gate; `UNVERIFIED` and `FAIL` mean keep
   working.

## The method — brainstorm → spec-lock → plan-lock → TDD → audit

Validated 2026-04-15 after DossierGap Phase 1 shipped end-to-end with
ground-truth-matched extractions and an honest audit. This is the **default**
workflow for any new research-tool build.

### 1. Brainstorm before implementation

Use the `superpowers:brainstorming` skill (Claude Code) or equivalent. **Lock
decisions in writing** before you touch code: `docs/<criterion>.md` for every
methodological choice (inclusion rules, primary estimand, comparator, threshold).
The commit history then pre-registers your methodology — no post-hoc
criterion-shopping when the result disappoints.

> Why: too many AI-generated research tools produce inflated success claims on
> synthetic fixtures, then fall over on real data. Spec-locked decisions
> prevent the "I'll just relax that criterion" trap.

### 2. Writing plans with a Task 0 prereq gate

For any plan whose final task depends on an external integration (a database
file, a fitted model, an upstream API), add **Task 0** that preflights the
dependency and **fails closed** with a specific user-action list.

> Why: Evidence Forecast Phase-1 once planned 19 TDD tasks assuming
> `cardiosynth.engine.pool_for_pico` and `MetaAudit/outputs/pairs.csv` existed.
> Neither did. We discovered this at Task 17 — after 16 tasks of scaffolding
> that all had to become bootstrap. Lesson: prove the prereqs work before
> writing a single test.

### 3. TDD per task, commit per task

Each task lands a runnable state with its own commit. Keeps bisect-ability and
makes "moving from Task N to N+1" a self-triggering commit signal — if your
commit log skips ahead, your test coverage probably did too.

### 4. Fail-closed extractors

When you build a data extractor (PDF → struct, HTML → struct, anything with
regex):

- **Schema validators at construction time** (pydantic + model validators).
- **Sentinel-string contract tests:** the extractor must never emit
  `"unknown"`, `"n/a"`, empty string, `None` for required fields. If the input
  doesn't match, raise — don't silently mark the field as missing.
- **Silently-wrong-number guards.** A positive integer field can still be
  semantically wrong. Example: a regex `(\d+) subjects randomized` will match
  `Not Randomized 1,807` and emit 1807 — schema-valid, semantically the
  opposite of what you wanted. Always check the preceding ~30 chars for
  negation words (`not`, `non`, `never`).

### 5. Honest audit reports

After any integration run, write `outputs/extraction_audit.md` (or equivalent)
that enumerates failures with root causes. Don't report success metrics
without listing what didn't work and why. A 2-of-5 result with root-cause
analysis is **far** more publishable than a 20-of-20 claim that doesn't hold
up to scrutiny.

### 6. Cite ground truth explicitly

For every extracted numerical value, check against a published reference to N
decimal places. Match-to-published checks belong in the **audit doc** so a
reviewer can see them, not in code comments.

## Quality gates (these run automatically once installed)

### Pre-push: Sentinel

Every `git push` triggers the Sentinel scan. 20 rules covering:

- Hardcoded local paths in shipped code (`C:\Users\...`, `/home/...`)
- Placeholder HMAC keys (`SIG_RSA_SHA256_...`)
- Silent-failure sentinels (`return "unknown"` on schema mismatch)
- XSS sinks (`innerHTML = userInput` without escape)
- localStorage key collisions across HTML variants
- Empty-DataFrame access (`.iloc[0]` without an upstream length guard)
- Committed `.claude/` / `.gemini/` configs
- And more.

**A BLOCK is a real defect.** When one fires, fix the underlying issue —
don't bypass. Each rule encodes a past-incident lesson; bypassing means
re-living it. If you're certain it's a false positive: `SENTINEL_BYPASS=1
git push` (logged to `~/.sentinel-logs/bypass.log`).

### Pre-ship: Overmind

Before declaring a project "done" (Submission-ready / Shipped):

```powershell
overmind run-once --repo C:\Projects\my-paper
```

Emits one of: `PASS`, `CERTIFIED`, `FAIL`, `UNVERIFIED`, `REJECT`.

- **PASS / CERTIFIED:** ship gate cleared.
- **UNVERIFIED:** test suite + smoke passed but a numerical witness was
  skipped (usually a missing baseline). **Not** a release pass — fix the
  baseline before promoting status.
- **FAIL / REJECT:** keep working.

A passing Overmind verdict is the only authoritative ship signal. Don't
promote project status from "memory" or stale prose.

## Worked examples — clone these and reproduce

These are live in Mahmood's portfolio. Read the README, run the test suite,
read the body, then adapt the structure to your question.

| Repo | What it shows | Method |
|---|---|---|
| [ma-workbench](https://github.com/mahmood726-cyber/ma-workbench) — `sglt2i-hfpef-demo` | Full E156 demo: data → analysis → 156-word body → reproducibility audit | The HR-0.81 vs Vaduganathan-0.80 honest-FAIL ship is the worked example of step 5+6 of the method (`|Δ|=0.007 > 0.005`, shipped anyway with full transparency). |
| [repro-floor-atlas](https://github.com/mahmood726-cyber/repro-floor-atlas) | Pairwise70-scale (7,545 MAs) reproduction floor study | E156 method applied at portfolio scale; Sentinel + Overmind verdicts in CI. |
| [responder-floor-atlas](https://github.com/mahmood726-cyber/responder-floor-atlas) | Empirical-MID-vs-canonical study with bootstrap CIs | Demonstrates the spec-lock cycle: feasibility tag → amendment tag → results tag. |
| [impossible-ma](https://github.com/mahmood726-cyber/impossible-ma) | "Possibility Envelope" primitive (k=1, missing SE, adversarial) | Shows fail-closed extractor design + 88-test coverage on a single primitive. |

## Adapting the rules to your setup

The shipped rules reference Mahmood-specific paths (`C:\E156\`, `C:\ProjectIndex\`,
`C:\Sentinel\`, `C:\overmind\`, GitHub user `mahmood726-cyber`). The installer
templates these to **your** values when you run it. After install, your version
of `~/.claude/rules/*.md` will reference your paths and your GitHub handle.

Re-running `install.ps1` / `install.sh` preserves files you've edited (backed up
as `*.user`). Use `-Force` if you want to overwrite with the upstream version.

## When you hit something the rules don't cover

Add a **new lesson** to your `~/.claude/rules/lessons.md` after fixing. Format:

```markdown
- **Short rule** (learned YYYY-MM-DD): The pattern to avoid + the fix. **Why:**
  what incident this prevents. **How to apply:** when this rule kicks in.
```

That's how `lessons.md` grew to its current size — every entry is a real
incident that wasted real time. Yours will too.

## Companion repos

- [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter) — narrow submission-pipeline CLI: `student new`, `student validate`, `student publish`.
- [`e156-binary-mirror`](https://github.com/mahmood726-cyber/e156-binary-mirror) — content-stable mirror of large pinned binaries.
- [Sentinel](https://github.com/mahmood726-cyber/Sentinel) — pre-push rule engine (this starter pins to `v0.1.0` by default; override with `SENTINEL_REF=<ref>`).
- [overmind](https://github.com/mahmood726-cyber/overmind) — nightly portfolio verifier (this starter pins to a known-good SHA by default; override with `OVERMIND_REF=<ref>`).

## License

This walkthrough and the rules pack are MIT-licensed. Use, adapt, fork freely.
