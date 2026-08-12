# Count-extraction harness report (v1.0.0)

**Verdict: PASS_WITH_WARNINGS** — 0 BLOCK, 10 WARN across 14 checks on 22 cells.

- cells with counts: **22** / 22
- independently confirmed (>=2 sources): **20**
- single-source: **2**
- unretrieved due to an obstacle (NOT absence): **0**

## WARN (10)

- `CHK004_PERCENTAGE_ONLY_REGISTRY` — **PARACHUTE-HF/sacubitril/valsartan/composite_cvdeath_or_first_hfhosp** — registry posting is percentage-only ('percentage of participants'); count is sourced from ['T1']. Derivation blocked, count accepted from publication.
- `CHK004_PERCENTAGE_ONLY_REGISTRY` — **PARACHUTE-HF/sacubitril/valsartan/cv_death** — registry posting is percentage-only ('percentage of participants'); count is sourced from ['T1']. Derivation blocked, count accepted from publication.
- `CHK004_PERCENTAGE_ONLY_REGISTRY` — **PARACHUTE-HF/sacubitril/valsartan/first_hf_hosp** — registry posting is percentage-only ('percentage of participants'); count is sourced from ['T1']. Derivation blocked, count accepted from publication.
- `CHK004_PERCENTAGE_ONLY_REGISTRY` — **PARACHUTE-HF/enalapril/composite_cvdeath_or_first_hfhosp** — registry posting is percentage-only ('percentage of participants'); count is sourced from ['T1']. Derivation blocked, count accepted from publication.
- `CHK004_PERCENTAGE_ONLY_REGISTRY` — **PARACHUTE-HF/enalapril/cv_death** — registry posting is percentage-only ('percentage of participants'); count is sourced from ['T1']. Derivation blocked, count accepted from publication.
- `CHK004_PERCENTAGE_ONLY_REGISTRY` — **PARACHUTE-HF/enalapril/first_hf_hosp** — registry posting is percentage-only ('percentage of participants'); count is sourced from ['T1']. Derivation blocked, count accepted from publication.
- `CHK005_SINGLE_SOURCE_CELL` — **PARADIGM-HF/sacubitril/valsartan/all_cause_death** — SINGLE-SOURCE cell (T2): CT.gov NCT01035255 results, Outcome 3 (adjudicated causes of death). Not independently confirmed; must be visibly distinguished in any 'n of m confirmed' statement.
- `CHK005_SINGLE_SOURCE_CELL` — **PARADIGM-HF/enalapril/all_cause_death** — SINGLE-SOURCE cell (T2): CT.gov NCT01035255 results, Outcome 3 (adjudicated causes of death). Not independently confirmed; must be visibly distinguished in any 'n of m confirmed' statement.
- `CHK005_SINGLE_SOURCE_CELL` — **PARALLEL-HF/sacubitril/valsartan/all_cause_death** — SINGLE-SOURCE cell (T2): CT.gov NCT02468232 results, Outcome 10. Not independently confirmed; must be visibly distinguished in any 'n of m confirmed' statement.
- `CHK005_SINGLE_SOURCE_CELL` — **PARALLEL-HF/enalapril/all_cause_death** — SINGLE-SOURCE cell (T2): CT.gov NCT02468232 results, Outcome 10. Not independently confirmed; must be visibly distinguished in any 'n of m confirmed' statement.

## INFO (4)

- `CHK001_COUNT_PERCENT_AGREEMENT` — **PARADIGM-HF/sacubitril/valsartan/all_cause_death** — no printed percentage captured; agreement not testable
- `CHK001_COUNT_PERCENT_AGREEMENT` — **PARADIGM-HF/enalapril/all_cause_death** — no printed percentage captured; agreement not testable
- `CHK001_COUNT_PERCENT_AGREEMENT` — **PARALLEL-HF/sacubitril/valsartan/all_cause_death** — no printed percentage captured; agreement not testable
- `CHK001_COUNT_PERCENT_AGREEMENT` — **PARALLEL-HF/enalapril/all_cause_death** — no printed percentage captured; agreement not testable

## PASS counts by check

- `CHK001_COUNT_PERCENT_AGREEMENT`: 20
- `CHK002_DENOMINATOR_NOT_RANDOMISED`: 24
- `CHK003_DUPLICATE_OUTCOME_POPULATION`: 2
- `CHK005_SINGLE_SOURCE_CELL`: 20
- `CHK006_READ_NOT_COMPUTED`: 24
- `CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS`: 6
- `CHK008_EVENTS_WITHIN_DENOMINATOR`: 24
- `CHK010_IDENTIFIER_PROVENANCE`: 3
- `CHK012_ARM_PAIR_COMPLETE`: 12
