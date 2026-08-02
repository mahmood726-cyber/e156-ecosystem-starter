# Review summary — meta-error library + self-audit layer

Branch: `feat/meta-error-library-and-self-audit`
Repo: `C:\Projects\e156-ecosystem-starter` (the clone that is level with `origin/main`)
Status: **staged locally, not pushed.**

**Two rounds.** Round 1 (2026-08-01) built the layer against a 97-app ledger.
Round 2 (2026-08-02) added the two detectors round 1 catalogued but did not
automate, refreshed every corpus figure against the now-626-app ledger, and
added the open-data sourcing method. Round-2 changes are marked **[R2]** below.

Delete this file before merging, or keep it as a PR description — it is a
handoff note, not part of the kit.

---

## What this adds

A new **optional layer**, in the same shape as Sentinel and Overmind: a teaching
document plus the machinery that enforces it.

| File | What it is |
|---|---|
| `docs/META-ERROR-LIBRARY.md` | The teaching artifact. **[R2]** 18 automated error classes grouped by severity (critical / high / medium), each with a plain-language description, a real worked example with real numbers, why it fools a reader, and how to detect + correct it. Plus a "What is not automated" table of 9 classes that resist automation, a blind-spots section, and a standards mapping. |
| `scripts/meta-self-audit.py` | **[R2]** 18 deterministic detectors over a single-file dashboard. Stdlib-only, offline, no API key, no model call. ~0.4 s on a 913 KB real dashboard. |
| `docs/SOURCING-METHOD.md` | **[R2] New.** The open-data sourcing method: the yield-ordered hierarchy (prior-meta supplements -> PMC/Europe PMC -> FDA/EMA -> ClinicalTrials.gov), the provenance-line format, add-beside-never-overwrite, fail-closed rules, the Tier A/Tier B missing-trial rule, and the case for retiring date-based exclusions. |
| `tests/test_meta_self_audit.py` | **[R2]** 23 further tests for MEL-17/18 (repo total **136**, all passing). Every detector has **both** a known-bad that must fire and a known-good that must not. |
| `templates/meta-self-audit/pooling_probe.py` | Reference pooling probe for the optional Overmind metamorphic witness. |
| `templates/meta-self-audit/example_clean_review.html` | A deliberately correct review, kept as a fixture so the suite is provably able to return `CLEAN`. |
| `docs/index.html` | New "What's new" entry + 5 new bullets in "What this toolkit cannot do" + a row in the installs table. |
| `README.md`, `STUDENT-WORKFLOW.md`, `docs/RAISE-alignment.md` | Layer row, usage section, third-gate placement, and 2 new RAISE rows. |

---

## Where the content came from

| Source | Used for |
|---|---|
| `F:\E156\_burn\fixed_ledger.tsv` (**[R2]** 626 dashboards) | Class frequencies. All quoted numbers are recomputed from the file, not remembered. |
| `F:\E156\_burn\fix_recipe.md` (19 classes) | The defect taxonomy the detectors implement. |
| `F:\E156\error-reversal-registry.jsonl` (19 Class-A records) | Published-literature worked examples and the "What is not automated" table. |
| `F:\E156\_burn\trials_to_review.tsv` | The flag-don't-add rule, documented as a rule. |

**[R2] Frequencies quoted in the docs**, recomputed from a snapshot of the
ledger taken 2026-08-02T08:56Z (626 distinct apps, deduplicated on the app
column — the raw file had 628 rows because 2 apps appear twice):

- class 5 incompatible pooling not fail-closed — **610/626 (97.4%)**
- class 16 timestamp-as-registration — **540/626 (86.3%)**
- class 7 false-green badge — **532/626 (85.0%)**
- class 9 template contamination — 63/626 (10.1%)
- classes 1, 2, 3, 4, 11, 12, 13, 18, 19 — 1–3 each

The ledger was **still being written to** while I read it (it grew 616 → 628
rows during the session), so every figure is labelled a point-in-time snapshot
in the docs. The snapshot I computed from is kept at
`scratchpad/ledger_snapshot.tsv` if you want to reproduce the numbers.

---

## Three things that need your judgement

**1. Published-literature examples are described but not attributed.** The
Class-A registry findings name real reviews and real authors. I wrote the worked
examples structurally — real numbers, real mechanism, no names ("a 2024 network
meta-analysis of HFrEF pharmacotherapy"). Publishing an audit finding against a
named researcher on a public student site is your call, not mine. If you want
attribution, the registry IDs behind each example are EA-001/002/003 (C3),
EA-015 (C4), EA-011 (H4), EA-012 (H5), EA-006 (M4), and EA-004/005/009/013/
014/016/017/018/019 (the not-automated table).

**2. The `link-check` CI job will fail on the PR, then pass after merge.**
`docs/index.html` links to
`github.com/.../blob/main/docs/META-ERROR-LIBRARY.md`, which 404s until the file
is on `main`. Lychee runs with `fail: true`. Either merge and let CI go green on
`main`, or switch those two links to relative `./META-ERROR-LIBRARY.md` first.
I kept absolute blob URLs to match the existing site convention (every other
`.md` link on the page is one) and because they render properly for readers.

**3. `i18n-parity` CI is already failing on `main` — not from this branch.**
`ar` and `ur` have 3 `<details>` sections against English's 5. I verified the
counts are byte-identical between this branch and `main` and added no
`<details>`. Out of scope here; flagging so it isn't mistaken for a regression.

**[R2] 4. The ledger's `flagged` column does not mean what it looks like — I
published nothing from it.** 619 of 626 rows carry `11` in column 5
(`flagged`). That reads as "a Tier-B eligibility concern was flagged on 619
apps", and round 1's docs said as much ("flagged on 95 of 97"). It is not
supportable, for two independent reasons:

- `drain_loop.ps1:197` — the only writer of that file — hardcodes that column to
  `-`. The value `11` cannot come from the documented path.
- `trials_to_review.tsv` holds **2** rows, both for the same PAH review. The
  recipe requires a flag to append a row there, so 619 flags and 2 review rows
  cannot both be true.

The public docs now teach the flag-don't-add rule from the **two real
escalations** — documented, checkable, and a better example anyway — and quote
no frequency for class 11. Worth chasing on the burn side separately: something
is writing that column and it is not the driver.

**[R2] 5. Two corpus apps have mojibake in trial names.**
`CANAKINUMAB_SJIA_AUTO_FULL_REVIEW.html` and
`CONCIZUMAB_HEMA_AUTO_FULL_REVIEW.html` carry a trial name both as a `\uXXXX`
escape and as an undecodable `<?>` byte (`explorer<?>4`). MEL-18 surfaced it
while I was chasing a false positive. I did not touch those files — separate
workstream — but it is a real encoding defect in the corpus.

---

## A real finding about Overmind, made while building this

Overmind's `MetamorphicWitness.run()` **reports a false FAIL against any correct
random-effects estimator.** Its scale-invariance relation multiplies every
effect by 2 and leaves the variances alone. That is not a change of units — if
you rescale an outcome, its standard errors rescale with it — so τ² correctly
absorbs the inflated spread and the weights move. Measured on the witness's own
inputs with the reference probe:

| Transform | Pooled ratio | τ² |
|---|---|---|
| effects ×2, variances unchanged (what the witness does) | 1.862 | 0.021 → 0.150 |
| effects ×2, variances ×4 (a real unit change) | **2.000** | 0.021 → 0.085 |
| fixed-effect, effects ×2 | **2.000** | — |

The relation is valid for fixed-effect pooling only. I did **not** make the
probe return a fixed-effect number to turn the gate green — that is exactly the
"point the check at code the dashboard doesn't run" failure this layer exists to
catch. Instead: the probe stays correct, `POOLING_PROBE_MODE=fixed` exercises
all five relations meaningfully, and the audit *names* the false FAIL in its own
output when scale-invariance is the sole violation. Worth fixing upstream in
`overmind/verification/metamorphic.py` — the relation should scale variances by
k² alongside effects.

---

## What I verified, and how

- **113 tests pass** (`python -m pytest tests/ -q`), 44 of them new.
- **Both directions per detector.** Every one has a known-bad that fires and a
  known-good that doesn't. Plus an end-to-end test that the shipped clean
  example returns `CLEAN` and exit 0 — a suite that can only fire is not a check.
- **Run against real corpus dashboards** (read-only; no RapidMeta app was
  touched). On `COPD_TRIPLE_REVIEW.html` it independently found the finerenone
  template bleed-through in a COPD review, Egger at k=3, gate bugs at `k>=2`/
  `k>=3`, the PROSPERO equivalence claim, and the false-green badge. On
  `HFREF_NMA_FULL_REVIEW.html`, the badge and a `k>=5` gate.
- **Four false positives found by running it on real files, and fixed at the
  source** — not by loosening a test:
  1. `"irr" in text` matched "m**irr**or"; abbreviations now require uppercase
     plus adjacency to a number or paren.
  2. `NaN` inside `<script>` is ordinary JS; only a *rendered* `NaN` is a leak.
  3. "Conflicts of interest: None declared" is correct English; `None` now only
     counts next to a count noun.
  4. "searched from 2010 to 2026" read the window *start* as the last-search
     date and called a current review 16 years stale; it now takes the latest
     year in the search clause.
  Each has a regression test named after the false positive.
- **Two genuine detector bugs found by the tests before shipping:** MEL-07 used
  a character-slice as "the headline" (now heading elements); MEL-08 returned
  early before the continuous-estimand check could run.
- **Windows console crash fixed.** cp1252 raised `UnicodeEncodeError` on the
  first finding quoting a `≥`. stdout/stderr now reconfigure to UTF-8.
- **Performance:** 0.4 s on 913 KB. The subset-sum search is explicitly bounded
  (sizes 2–5, ≤60 rows, 2M-combination budget) and returns `INCONCLUSIVE`
  rather than a false all-clear when it hits the bound.

### [R2] Round 2 verification

- **136 tests pass**, 23 of them new (MEL-17 ×7, MEL-18 ×16). Both directions
  for each, plus a regression test named after every false positive below.
- **Scanned 431 real corpus dashboards** with the two new detectors, read-only.
  Final state: **0 fired**, 426 of 431 engaging MEL-18's structural checks. Note
  what that does and does not show — it is a *specificity* result on
  already-repaired files. Sensitivity rests on the known-bad fixtures. Both
  documents say so rather than implying the scan proves the detectors work.
- **Three false positives found on real files and fixed at the source**, none of
  which the unit tests caught:
  1. **MEL-18 bound each ID to the nearest capitalised token** and so fired on
     **38 of 40** dashboards — one NCT legitimately appears a dozen times per
     page and picked up `AUTO`, `TRIALS`, `AACT`, `RANDOMIZED` as trial names.
     Fixed by binding only from structure (a table column whose header says what
     it holds, or a trial record in the page's own script state), not proximity.
     A longer exclusion list would only have moved the noise.
  2. **A sample size of 1,912 was read as a publication year**, making an
     ordinary NCT look impossible. The year now comes from a column whose header
     says `year`.
  3. **One trial name split across two encodings** (`explorer™4` vs its
     decoded form) read as two different trials. Escapes are decoded before
     comparison, and an undecodable name is skipped rather than treated as a
     conflict.
- **One check deliberately removed after the evidence went against it.** "One
  trial name against several registry IDs" looks sound and is not: one
  publication routinely reports two registered trials — in this corpus "Siegal
  2015" covers ANNEXA-A and ANNEXA-R. It has a test asserting it stays quiet.
- **Three bugs in my own new code, caught by the tests before any scan:** a
  `favours` capture whose character class included a space, so both ends of the
  axis collapsed into one match; ID binding that took the first name in a
  symmetric window rather than the nearest; and an NCT block index read from one
  digit when an 8-digit NCT always begins with `0`, which silently put every
  trial in block 0.
- **Checked for stale claims repo-wide**, not just in the files I edited:
  `README.md`, `STUDENT-WORKFLOW.md`, `docs/RAISE-alignment.md` and
  `docs/index.html` all still said 16 detectors / 97 dashboards / 97-97.

## What I did not do

- Did not push, and did not touch `F:\rapidmeta-finerenone` app files.
- Did not ship the cross-family adversarial gating. It needs paid multi-vendor
  API access, so it cannot run offline; it is documented in `STUDENT-WORKFLOW.md`
  as optional guidance with its real limit restated (≈two effective independent
  votes, not one per model), not presented as something the free tier gets.
- Did not automate the 9 classes in the "What is not automated" table. Several
  are automatable with more work (included-trials vs reference-list is a set
  difference); one — a stratification printed as a randomisation split — cannot
  be, because the table is internally consistent.
- Did not add a pre-push hook. The README shows the one-liner if you want the
  audit enforced alongside Sentinel.

---

## To push

```powershell
cd C:\Projects\e156-ecosystem-starter
git log --stat -1                     # review what's in the commit
git push -u origin feat/meta-error-library-and-self-audit
```

Then open a PR against `main`:

```powershell
gh pr create --base main --head feat/meta-error-library-and-self-audit `
  --title "Meta-analysis error library + offline self-audit layer" `
  --body-file SUMMARY-META-ERROR-LAYER.md
```

Try it before you merge:

```powershell
python scripts\meta-self-audit.py templates\meta-self-audit\example_clean_review.html   # CLEAN, exit 0
python scripts\meta-self-audit.py <any real dashboard>                                  # the interesting one
```
