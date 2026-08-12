# Per-arm event-count recovery — procedure

**Companion to** `rapidmeta_count_harness.py` (v1.0.0). Run the harness; do not re-derive its rules by hand.

```
python rapidmeta_count_harness.py --selftest        # 14 checks, 11 negative controls
python rapidmeta_count_harness.py --chain           # print the retrieval fallback chain
python rapidmeta_count_harness.py extraction.json --report r.md --json r.json
```

Exit code 1 means at least one BLOCK. A BLOCKed extraction does not go downstream.

---

## 1. The four rules that everything else serves

1. **Read the number, never compute it.** No multiplying a percentage by a denominator. No summing components into a composite. If it is not printed as an integer, it is not recovered. `CHK006`, `CHK004`, `CHK007`.
2. **A blocked fetch is a blocked fetch, never an absence.** Retrieval failure goes in `Cell.obstacle` and raises `BlockedFetch`. It never becomes "not reported". `CHK009`.
3. **Identifiers by lookup, never recall.** Every NCT resolved live. `CHK010`.
4. **Fail closed.** A cell that cannot be shown safe is BLOCK, not PASS. Missing information is never reassurance.

---

## 2. Retrieval fallback chain

Encoded in `REGISTRY_FALLBACK_CHAIN`; `--chain` prints it. Do not rediscover this.

| # | Strategy | Status |
|---|---|---|
| 1 | `web_fetch` of `clinicaltrials.gov/api/v2/studies/<NCT>?fields=ResultsSection` | **Refused at the tool layer** in this environment (observed 2026-08-12). An obstacle, not an absence — fall through. |
| 2 | **Chrome, same-origin fetch** — navigate to `clinicaltrials.gov/study/<NCT>?tab=results`, then `fetch('/api/v2/studies/<NCT>?...')` from the page context | **Works. This is the default path.** No CORS, full structured module. |
| 3 | Chrome `get_page_text` on the results tab | Fallback if the API shape changes. Registry results are JS-rendered, so a raw HTML fetch returns an empty shell — the browser is required. |
| 4 | PubMed → PMC full text → outcomes table | **Required whenever the registry is percentage-only.** |
| 5 | Publisher site via Chrome | Abstract/Results paragraphs often carry per-arm counts even when tables are paywalled. Confirmed working on nejm.org, jstage, pmc. |
| 6 | FDA statistical review / EMA EPAR | For trials predating results posting. |

Two output-hygiene rules learned the hard way when scripting step 2:

- **Strip URL-like tokens** from anything you return. The tool layer rejects payloads containing query strings (`[BLOCKED: Cookie/query string data]`). `String(s).replace(/\S*=\S*/g,' ')` fixes it.
- **Never return the whole results module.** It exceeds the token cap. Slice in-page to the outcomes you want. `CHROME_JS_TEMPLATE` in the harness is a working starting point.

---

## 3. Source tiers

| Tier | Meaning |
|---|---|
| **T1** | The trial's own primary publication — journal table or Results text |
| **T2** | Registry posted results module |
| **T3** | Regulatory review (FDA statistical review, EMA EPAR) |
| **T4** | **Prior meta-analysis extraction table — UNVERIFIED.** Must set `flagged_unverified: true`. A T4-only cell is BLOCKed. Reyaz 2023 had both a comparator and a follow-up wrong in the single row that was checked. |

---

## 4. The checks, and the mistake each one exists to prevent

| Check | Prevents | Real instance |
|---|---|---|
| `CHK001_COUNT_PERCENT_AGREEMENT` | A count that contradicts the percentage printed beside it | ARNI round: 24/24 agreed, which is what made the denominators trustworthy |
| `CHK002_DENOMINATOR_NOT_RANDOMISED` | Recording only one of analysed/randomised | PARADIGM-HF 4187/4212 analysed vs 4209/4233 randomised; PARALLEL-HF 111/112 vs 112/113 |
| `CHK003_DUPLICATE_OUTCOME_POPULATION` | Silently picking between two arm-pairs for one outcome | PARADIGM-HF posts all-cause death twice: 711/835 (FAS) and 714/837 (randomised) |
| `CHK004_PERCENTAGE_ONLY_REGISTRY` | Multiply-a-percentage creeping in | PARACHUTE-HF: all four key outcomes percentage-only. 16 of 25 cardio-atlas gaps are the same |
| `CHK005_SINGLE_SOURCE_CELL` | "22 of 24 confirmed" hiding which 2 | PARALLEL-HF all-cause death exists only in the registry |
| `CHK006_READ_NOT_COMPUTED` | Any non-read provenance; also empty cells with no stated reason | — |
| `CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS` | Building a first-event composite by addition | Sum overstates by 20–37% across the three ARNI trials |
| `CHK008_EVENTS_WITHIN_DENOMINATOR` | events > analysed | Catches recurrent-event counts masquerading as 2×2 cells |
| `CHK009_BLOCKED_FETCH_NOT_ABSENCE` | Logging a refused fetch as "no data" | The CT.gov API refusal above |
| `CHK010_IDENTIFIER_PROVENANCE` | NCT from memory | PARALLEL-HF = NCT02468232, resolved by lookup |
| `CHK011_UNVERIFIED_TIER_FLAGGED` | Prior-meta tables passing as primary | Reyaz 2023 |
| `CHK012_ARM_PAIR_COMPLETE` | Half a 2×2 | — |
| `CHK013_AE_MODULE_DEATHS_NOT_EFFICACY` | Using the registry's adverse-events death count as the efficacy endpoint | **New this round — see below** |
| `CHK014_EFFECT_ESTIMATE_CONSISTENCY` | Counts that cannot reproduce the stored effect estimate | Caught HEART-FID's 12-month count (RR 0.83 vs stored HR 0.95) |

### CHK013 in detail — the trap that nearly cost the whole sweep

ClinicalTrials.gov requires an all-cause death count in the **adverse-events module** (`eventGroups[].deathsNumAffected`). It is an integer, it is posted even when the efficacy outcomes are percentage-only, and it is therefore extremely tempting as a universal source. It answers a different question: **safety population, adverse-event collection window**, not the efficacy analysis set over the efficacy follow-up.

Measured divergence in this sweep:

| Trial | AE module | Efficacy endpoint | Divergence |
|---|---|---|---|
| SPRINT | 155 / 210 | 155 / 210 | identical |
| DECLARE-TIMI 58 | 529 / 570 | 529 / 570 | identical |
| PARAGON-HF | 347 / 357 | 342 / 349 | small |
| DAPA-HF | 286 / 333 | 276 / 329 | small |
| ODYSSEY OUTCOMES | 238 / 278 | 334 / 392 | **~100 events per arm** |
| EMPA-KIDNEY | 314 / 353 | 148 / 167 | **>2×** |

Sometimes identical, sometimes double. Never safe to substitute silently.

### CHK014's limitation — stated because it matters

Agreement with a stored effect estimate is **necessary but not sufficient**. For ODYSSEY OUTCOMES the AE-module pair (238/278, RR 0.856) and the efficacy pair (334/392, RR 0.852) **both** reproduce the stored HR of 0.85, while differing by about 100 events per arm. Disagreement is informative; agreement authenticates nothing. CHK014 therefore emits WARN on disagreement and INFO on agreement, and never PASSes a cell on its own.

---

## 5. Cell schema

```jsonc
{
  "trial": "PARADIGM-HF", "nct": "NCT01035255", "arm": "sacubitril/valsartan",
  "outcome": "all_cause_death",
  "events": 711, "analysed": 4187, "randomised": 4209,
  "population_label": "FAS",
  "denominator_reason": "37 at GCP-closed sites + 6 mis-randomised",
  "printed_percent": 17.0,
  "provenance": "read",                       // only "read" is admissible
  "selected": true,                            // exactly one true per duplicated outcome
  "identifier_provenance": "lookup",
  "registry_units": "participants",
  "is_component_of": null,
  "sources": [ { "tier": "T1", "pointer": "NEJM 2014 Results text", "url": "..." } ],
  "not_recovered_reason": null,
  "obstacle": null,
  "notes": "stored_hr=0.84 arm_role=treatment"
}
```

Conventions: `denominator_reason` beginning `NOT STATED` downgrades CHK002 to WARN and marks an open item — an unexplained exclusion is not the same as an explained one. `notes` may carry `stored_hr=<x>` and `arm_role=treatment|control` to activate CHK014.

---

## 6. Standing order for the next lane

1. Resolve every identifier by lookup. Record how.
2. Registry first via **Chrome same-origin fetch** (chain step 2). Scan outcome titles for the outcome concept; check `unitOfMeasure`.
3. If `unitOfMeasure` contains "percent" → mark `registry_units` accordingly and go to the publication. Do not derive.
4. Read participant flow for **both** randomised and analysed, plus the exclusion reason. If the source does not give a reason, write `NOT STATED …` rather than inventing one.
5. Never take the count from the adverse-events module for an efficacy endpoint. If you record it at all, set `selected: false` and label the population.
6. Where one outcome has two populations, record both, set `selected` on exactly one, and say why.
7. Run the harness. Fix BLOCKs. Do not hand on a BLOCKed extraction.
8. Report the rate with its denominator, and make single-source cells individually visible.
