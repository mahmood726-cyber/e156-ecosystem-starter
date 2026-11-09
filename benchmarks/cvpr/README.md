# CVPR worker 09 — synthetic arithmetic smoke benchmark

**Status: experimental engineering fixture only. Not a paper audit and not a real-world validation of Synthesis.**

This module implements a narrow deterministic baseline for four CVPR checklist
arithmetic checks (share percentage, macro mean, relative gain in the declared
metric direction, and absolute delta). It does **not** evaluate the other CVPR
rule families, independently establish scientific errors, access any article, or
exercise production acquisition/outgoing-message paths.

- Provenance: first-party **invented** examples created on 2026-11-06; no CVPR
  paper, author, correspondence, publisher text, code, or private benchmark input.
- Assignment: CVPR-W09- namespace, worker 9/9 only. The 24 case IDs, manual
  ground-truth rationales and disjoint DEV/TEST splits are frozen in
  [worker09_synthetic.json](worker09_synthetic.json) before the first baseline
  evaluation. Changes to held-out cases invalidate the original evaluation.
- Evaluator: [cvpr_synthetic_benchmark.py](../../scripts/cvpr_synthetic_benchmark.py).
  Invalid or non-synthetic inputs fail closed. Insufficient evidence and version
  mismatches abstain, rather than becoming errors.
- Run from repository root:
  python -m pytest tests/test_cvpr_synthetic_benchmark.py -q
  and python scripts/cvpr_synthetic_benchmark.py --split test.

**Frozen synthetic baseline:** in the 12 held-out examples, 5 deliberately
inconsistent cases were flagged, 5 consistent controls were cleared, and 2
unevaluable controls abstained. TP=5, FP=0, FN=0, TN=5, abstentions=2;
precision/recall/specificity on evaluable synthetic cases = 5/5 each.
These are purpose-built examples, not estimates for real CVPR manuscripts.
Even 5/5 successes give a wide 95% Wilson confidence interval (~0.57–1.00).

The user-required 20-paper deep-audit sample (Track A) is separate. This
synthetic benchmark does **not** allocate or audit any paper.
