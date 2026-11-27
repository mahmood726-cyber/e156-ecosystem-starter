# Harness output and benchmark validation repairs - 27 November 2026

The fresh development review reproduced the previous benchmark behavior and
identified two additional validation defects. Both fixes preserve the frozen
protocols, package locks and consumed final campaign.

## Malformed prediction types

A valid provider envelope could contain a prediction with `disposition: []`.
The core runner then raised `TypeError` while testing enum membership, leaving
the study in `EXECUTION_UNKNOWN`. The response and usage were settled, and an
explicit abort retained all planned slots, but ordinary output validation was
bypassed.

The core runner now requires an object prediction and a string disposition
before interpreting its value. Invalid types become the existing
`ABSTAIN` / `OUTPUT_VALIDATION` result, with the configured fallback route
unchanged. Regressions exercise valid predictions, invalid types, actual study
settlement, cached replay without provider calls, retained usage and frozen
export. The array/object study cases are required CI process controls.

## Benchmark trace consistency

The prior grader could accept a successful observation whose execution trace
was empty or whose counters and trace hash were inconsistent. Two controlled
apparatus-corruption probes demonstrated this. Independent reconciliation found
no such discrepancy in the 96 observations measured before the repair.

The comparator now checks trace completeness and consistency before awarding
credit. Model requests, tool attempts/results and failure evidence must agree
with the row and the scripted case; invalid apparatus evidence remains a failed
attempt. This checks the observed record on a trusted host. It does not
authenticate an adversary who replaces the entire trace and its hash together.

## Verification scope

| Component | Fixed/configured | Dynamically exercised |
|---|---|---|
| Output policy | Existing disposition vocabulary and fallback policy | Valid controls, malformed types, settled journals and actual study children |
| Trace oracle | Event, count, request/result and hash contracts | Deliberately missing/corrupted telemetry and native known-development cases |
| Comparison | Same eight known cases, scripted responses and locked versions | Actual E156, Deep Agents and Pydantic execution and independent reconciliation |
| Scientific interpretation | Development engineering checks only | No paid model calls, new held-out result or scientific accuracy measurement |

Run the focused contracts from the repository root:

```text
python -m pytest tests/test_harness_runtime.py tests/test_harness_study_runner.py tests/test_harness_execution_benchmark.py -q
```

Native comparison and study checks use the separate locked environment described
in [the native adapter guide](HARNESS-NATIVE-PYDANTIC.md). Historical results
remain in [the original campaign report](HARNESS-EXECUTION-RESULTS-2026-11-26.md);
they have not been rescored or presented as a fresh held-out evaluation.
