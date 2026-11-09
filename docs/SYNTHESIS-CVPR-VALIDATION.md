# Synthesis CVPR verification and validation module — experimental

**Status:** Protocol, not a validated error detector. Applies only to lawfully accessible CVPR material with permitted processing rights. Do not infer error rates from a selected sample.

## Two parallel tracks

### Track A — 20-paper deep audit
Select 20 distinct IEEE/CVF CVPR papers with a reproducible selection record (year, proceedings URL, DOI or paper ID, selection rule, access/rights status). Record each as an assignment before auditing; prevent overlapping workers. Do not replace inaccessible papers silently: log exclusion and replacement reason.

For each paper, record:
- exact paper version, access permission, URL and date; supplementary files, code commit and dataset/model availability;
- claims and verbatim locations (abstract, text, table, figure, supplement);
- checks attempted, passed, failed and untestable; why a check was untestable;
- source values, formula, units, rounding tolerance, executable calculation and independently checked result;
- benchmark identity, split, metric direction, preprocessing, test-time augmentation, training data, compute and baseline comparability;
- seeds, variability and significance support; ablations and parameter/compute fairness;
- code/configuration/evaluation implementation versus manuscript; leakage and contamination only when demonstrable from authorised evidence;
- alternative explanations and author response, if any;
- status: NO_ISSUE_OBSERVED, HYPOTHESIS, REPRODUCIBLE_DISCREPANCY, INDEPENDENTLY_VERIFIED_ERROR, or NOT_ENOUGH_INFO.

Never call a mismatch an error before ruling out rounding, versions, metric definitions, different evaluation settings or transcription mistakes. A paper with no detected issue is not certified correct.

### Track B — detection benchmark
Create a rights-cleared, provenance-linked benchmark of documented CV/ML corrections, reproducibility failures or independently demonstrable reporting errors, plus clean or deliberately ambiguous negative controls. Do not treat a public allegation as ground truth. Record source and adjudication for every label. Keep calibration examples separate from held-out examples; avoid memorised examples and leakage between splits.

For each checklist rule measure true positives, false positives, false negatives, true negatives, abstentions, precision, recall, specificity and adjudication agreement. Report denominators and uncertainty intervals; stratify by error type and availability of source code/data. An unverified flag is not a true positive. Count untestable/abstained separately, not as correct predictions.

## CVPR rule families
1. Arithmetic and consistency of tables, averages, relative/absolute improvements, rankings and abstract/conclusion claims.
2. Metric definitions, evaluation splits, benchmark versions and baseline protocol comparability.
3. Multiple seeds, variance, uncertainty and unsupported significance claims.
4. Ablation logic, parameter budgets, pretraining data, inference-time settings and compute fairness.
5. Dataset overlap, duplicate images, leakage and contamination, with direct evidence.
6. Reproducibility of released code, configuration, weights and evaluation scripts, when access and resources permit.
7. Cross-version consistency across main paper, supplement, repository and corrections.

## Contact and safety gates
Respect source rights, no-contact and opt-out lists, and existing JAMA Network exclusion. Check prior correspondence and deduplicate. Do not send speculative or batch emails. Author outreach requires a substantive independently verified issue, precise reproducible evidence and a courteous source-based message; log sent status rather than assuming delivery.

## Reporting
Controller publishes per-run counts: assigned / attempted / completed papers; checks performed; hypotheses; reproducible discrepancies; verified errors; NOT_ENOUGH_INFO; benchmark TP/FP/FN/TN/abstentions; and sent emails. Distinguish completed work from scheduled or requested work. Keep manuscript-specific correspondence and sensitive development records private; this public document contains only the protocol.
