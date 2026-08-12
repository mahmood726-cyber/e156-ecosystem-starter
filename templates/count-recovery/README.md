# Count-recovery harness

Pre-condition checks for per-arm 2×2 event-count extraction — the numbers you need to
pool a trial yourself instead of inheriting somebody else's pooled estimate.

**Standard library only. Offline. No install, no API key, no model call.**

## Run it now

```bash
# 14 checks against 11 negative controls -- proves the checks can actually fail
python rapidmeta_count_harness.py --selftest

# the retrieval fallback chain, in order
python rapidmeta_count_harness.py --chain

# a complete worked extraction (24 rows, three real trials)
python rapidmeta_count_harness.py example_extraction.json

# your own
python rapidmeta_count_harness.py my_extraction.json --report r.md --json r.json
```

Exit code `1` means at least one **BLOCK**. A BLOCKed extraction does not go
downstream. `example_report.md` is the committed output of the example run, if you
would rather read the result than run it.

## What is in here

| File | What it is |
|---|---|
| `rapidmeta_count_harness.py` | The harness. 14 checks, each one traceable to a mistake actually made on real data. |
| `COUNT_RECOVERY_PROCEDURE.md` | The method the harness enforces — source tiers, retrieval order, cell schema, and the standing order for the next extraction round. |
| `example_extraction.json` | A runnable input: three trials, including the duplicate-population trap and a percentage-only registry posting. |
| `example_report.md` | What the example prints. |

## The four rules everything else serves

1. **Read the number, never compute it.** No multiplying a percentage by a
   denominator; no summing components into a composite. If it is not printed as an
   integer, it is not recovered.
2. **A blocked fetch is a blocked fetch, never an absence.**
3. **Identifiers by lookup, never recall.**
4. **Fail closed.** A cell that cannot be shown safe is BLOCK, not PASS.

## Start here if you read nothing else

[`docs/REGISTRY-EXTRACTION-TRAPS.md`](../../docs/REGISTRY-EXTRACTION-TRAPS.md) — the
registry adverse-events trap, and why a count that reproduces the published hazard
ratio still tells you nothing.

## Blind spots

The harness checks **structure and provenance, not truth**. It cannot tell you that a
correctly-formatted count was misread off the page, and it does not recompute your
pooled estimate. A `PASS_WITH_WARNINGS` means the traps it knows about were avoided,
not that the extraction is right.
