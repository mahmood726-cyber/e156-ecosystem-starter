# Recovering event counts from registries — the traps, and a harness that catches them

**What this is for.** You need per-arm 2×2 event counts (events and denominator, for
each arm) to pool a trial yourself rather than inheriting somebody else's pooled
number. This page is about where those counts come from when the paper is behind a
wall, and the specific ways that recovery goes wrong.

Everything here is enforced by a runnable script:

```bash
python templates/count-recovery/rapidmeta_count_harness.py --selftest
python templates/count-recovery/rapidmeta_count_harness.py --chain
python templates/count-recovery/rapidmeta_count_harness.py my_extraction.json --report r.md
```

Standard library only. No install, no network, no API key, no model call. Exit code 1
means at least one BLOCK, and a BLOCKed extraction does not go downstream.
`templates/count-recovery/example_extraction.json` is a complete worked input you can
run immediately; `example_report.md` is what it prints, if you would rather just read it.

---

## 1. The trap worth knowing even if you use none of this

**ClinicalTrials.gov requires an all-cause death count in the adverse-events module.**
For any trial with posted results it is there, it is an integer, and — this is what
makes it dangerous — **it is posted even when the trial's efficacy outcomes are
posted as percentages with no integer count anywhere.**

So when you are hunting counts and keep hitting percentage-only outcomes, the
adverse-events module looks like a universal key. It is not. It answers a different
question: the **safety population** over the **adverse-event collection window**, not
the efficacy analysis set over the efficacy follow-up.

How far apart they get, measured across six trials in one sweep:

| Trial | Adverse-events module | Efficacy endpoint | Divergence |
|---|---|---|---|
| SPRINT | 155 / 210 | 155 / 210 | identical |
| DECLARE-TIMI 58 | 529 / 570 | 529 / 570 | identical |
| PARAGON-HF | 347 / 357 | 342 / 349 | small |
| DAPA-HF | 286 / 333 | 276 / 329 | small |
| ODYSSEY OUTCOMES | 238 / 278 | 334 / 392 | **~100 events per arm** |
| EMPA-KIDNEY | 314 / 353 | 148 / 167 | **more than 2×** |

Two of six identical, two close, two badly wrong — and nothing on the page tells you
which case you are in. That is the whole problem: it is right often enough to feel
safe. `CHK013` in the harness blocks it unless you mark the cell `selected: false`
and label the population.

*Denominator: six trials, chosen because they were the ones being extracted, not
sampled. Treat the pattern as real and the proportions as nothing.*

## 2. The part that generalises beyond registries

The obvious defence is to check your recovered counts against the trial's published
effect estimate: if 2×2 reproduces the reported hazard ratio, the counts must be right.

**They must not.** For ODYSSEY OUTCOMES:

| Source | Counts | Implied risk ratio | Published HR |
|---|---|---|---|
| Adverse-events module | 238 / 278 | 0.856 | 0.85 |
| Efficacy endpoint | 334 / 392 | 0.852 | 0.85 |

Both reproduce the published estimate. They differ by roughly 100 events per arm. A
consistency check passes on either one.

This is not a quirk of that trial. A ratio is insensitive to anything that scales both
arms together, and the difference between a safety population and an efficacy
population very often does scale both arms together. So:

> **Agreement authenticates nothing. Only disagreement is informative.**

The harness encodes exactly that asymmetry: `CHK014` emits **WARN on disagreement** and
**INFO on agreement**, and never passes a cell on its own. A check that can only ever
say "fine" is not a check — the same reasoning that makes a quality gate with no
failure path worthless.

The general form, worth carrying into any extraction work: **before you rely on a
consistency check, ask what it would look like if the data were wrong.** If the answer
is "the same", it is decoration.

## 3. The other twelve checks

Each exists because the mistake was actually made, on real data, in this programme.

| Check | Prevents | Where it came from |
|---|---|---|
| `CHK001` count vs percentage | A count that contradicts the percentage printed beside it | 24/24 agreed in one round, which is what made those denominators trustworthy |
| `CHK002` denominator ≠ randomised | Recording only one of analysed/randomised | PARADIGM-HF analysed 4187/4212 but randomised 4209/4233 |
| `CHK003` duplicate outcome population | Silently picking between two arm-pairs for one outcome | PARADIGM-HF posts all-cause death twice — 711/835 (FAS) and 714/837 (randomised) |
| `CHK004` percentage-only registry | Multiplying a percentage by a denominator | PARACHUTE-HF: all four key outcomes percentage-only |
| `CHK005` single-source cell | "22 of 24 confirmed" hiding which 2 | PARALLEL-HF all-cause death exists only in the registry |
| `CHK006` read, not computed | Any non-read provenance; empty cells with no stated reason | — |
| `CHK007` composite ≠ sum of components | Building a first-event composite by addition | The sum overstated by 20–37% across three trials |
| `CHK008` events within denominator | events > analysed | Catches recurrent-event counts posing as 2×2 cells |
| `CHK009` blocked fetch ≠ absence | Logging a refused fetch as "no data" | See §5 |
| `CHK010` identifier provenance | An NCT number from memory | — |
| `CHK011` unverified tier flagged | Prior-meta extraction tables passing as primary | One had both a comparator and a follow-up wrong in the single row checked |
| `CHK012` arm pair complete | Half a 2×2 | — |

Four rules sit under all of them:

1. **Read the number, never compute it.** No multiplying a percentage by a
   denominator, no summing components into a composite. If it is not printed as an
   integer, it is not recovered.
2. **A blocked fetch is a blocked fetch, never an absence.**
3. **Identifiers by lookup, never recall.**
4. **Fail closed.** A cell that cannot be shown safe is BLOCK, not PASS. Missing
   information is never reassurance.

Rule 3 deserves a note for anyone working with an AI assistant: a language model will
produce a plausible, well-formatted, wrong NCT number without hesitation, because a
registry identifier is exactly the kind of string that is easy to generate and hard to
recognise as false. Resolve every one by live lookup and record how.

## 4. Where to look, in order

Printed by `--chain`, so it does not have to be rediscovered:

1. **Registry API** — fast when permitted. In some tool environments the fetch is
   refused outright. That is an obstacle, not an absence; fall through.
2. **Browser, same-origin fetch** on the registry's own results page. Usually the
   working default: no cross-origin problem, full structured results module.
3. **Browser, page text** on the results tab. Registry results are rendered by
   JavaScript, so a raw HTML fetch returns an empty shell — a browser is required.
4. **PubMed → PMC full text → outcomes table.** Required whenever the registry is
   percentage-only.
5. **Publisher site.** Abstract and Results paragraphs often carry per-arm counts even
   when the tables are paywalled.
6. **Regulatory review** (FDA statistical review, EMA assessment report) for trials
   predating results posting.

Two output-hygiene notes learned while scripting step 2, which will otherwise cost you
an afternoon: strip URL-like tokens from anything you return, and never return the
whole results module — slice it in the page first.

## 5. A failed fetch is never a data absence

When retrieval fails, record **what stopped you**, not "not reported". They are
different facts with different remedies, and collapsing them destroys the second one.

`CHK009` blocks any `not_recovered_reason` that conflates the two — a string like
"not reported (403)" is refused, because a 403 is a statement about your access, not
about the trial.

This matters more than it sounds. In one sweep, a registry API refusal at the tool
layer would have written off four trials as having no data. The data was there, and a
browser reached it on the next step of the chain. **An obstacle you have named is a
task; an absence you have recorded is a conclusion.** Do not convert the first into
the second by accident.

## 6. "Not found" often means "not named"

A search returns nothing. The natural reading is that the thing does not exist. The
more common reading is that you searched an index that does not contain it.

The worked case: a Chinese-language trial was invisible to a PubMed search because its
journal is not indexed in MEDLINE. It was **free to read the whole time**. It was not
paywalled, not hidden, not missing — just not indexed where the search was pointed.
It took seven routes to reach, and the one that worked was rendering the record in a
browser.

So a PubMed-only search measures **indexing**, not existence. If your synthesis says
"no trials were found", the honest form is "no trials were found *in the databases
searched*", and the useful next question is which databases would have contained one.
For non-English literature that means the national indexes; for trials run outside the
United States it means the registries other than ClinicalTrials.gov.

This is the same failure the toolkit already warns about for registry audits — a
CT.gov-only denominator over-reports hiddenness, and over-reports it worst for exactly
the regions this toolkit is built for.

---

## Blind spots

- The harness checks **structure and provenance**, not truth. It cannot tell you that
  a correctly-formatted count was misread off the page.
- `CHK001` only works if you captured the printed percentage. Most of its value comes
  from having bothered to record both numbers.
- The divergence table in §1 is six trials, chosen by what was being extracted.
- Nothing here recovers a number that was never published. See
  [ACCESS-LEDGER.md](ACCESS-LEDGER.md) for why that layer, not the paywalled one, is
  the genuinely irrecoverable one.

## Related

- [`ACCESS-LEDGER.md`](ACCESS-LEDGER.md) — what actually blocks access, measured
- [`META-ERROR-LIBRARY.md`](META-ERROR-LIBRARY.md) — defect classes in finished syntheses
- [`SOURCING-METHOD.md`](SOURCING-METHOD.md) — where to source a replacement number
- `scripts/trial-identity-screen.py` — screen a table for one trial entered twice
