# Synthesis v1.3 — independent blinded scientific-validation plan

**3 November 2026 · protocol proposal only · NOT STARTED**

This is a prospective evaluation design, **not** a frozen or executed study. It cannot itself establish real-paper accuracy. An independent scientific custodian must review and approve the selection rule, source rights, benchmark claims, reviewer assignments and analysis plan before a fresh test manifest is frozen.

## Non-negotiable separation

- Preserve the existing frozen Simo v0.10 36-claim/12-trial-family cohort, all signed e156 evidence, previously reviewed controls and correspondence unchanged. Never use held-out labels to tune v1.3.
- Do not treat earlier correspondence, correction notices, selected known-error cases, synthetic tests or emailed queries as unbiased validation.
- A newly proposed feasibility design is **24 paper/trial families with at least 12 NMA/IPD families**; this number is not a completed sample, approval or prospective freeze. Stratification, sample size and test fractions remain subject to independent protocol review.
- A separate reviewer must not adjudicate their own paper, any conflicted work, or a development example they already know. Record familiarity before allocation. Mask output source (manual/v1.2/v1.3) where feasible.

## Before exposing detector outputs

1. Independent custodian defines a DOI/arXiv-family sampling frame, accessibility and licence rules, random seed and selection probabilities. Include ordinary unmodified papers and some pre-specified error controls; **unmodified does not mean error-free**.
2. Independently retrieve and authenticate exact current Version of Record (or versioned preprint), supplements, protocol/SAP/registry, analysis code and correction notices. Preserve hashes, exact locations and full-text retrieval paths; when blocked, record the stop point and abstain.
3. Enumerate the target claims before testing, including unflagged/negative claims and multiple errors within a document; separate trial-family roots from affected outputs. Lock the manifest and exclude familiar examples from the untouched test split.
4. Freeze v1.2 and v1.3 commits, prompts/configuration, model/tool versions and a matched time/retrieval budget. Run structured manual checking, baseline v1.2 and candidate v1.3 on identical claims and access rights.
5. Freeze time-stamped, hash-bound predictions before revealing references. Keep flags, no-flags, and NOT_ENOUGH_INFO/ABSTAIN with source stop points.

## Independent source adjudication

Two appropriately skilled, masked reviewers examine every flagged claim and a prespecified probability sample of unflagged claims. Disagreements go to a separate adjudicator. Preserve reasons, version and source locators, the published estimator and missingness/multiplicity/censoring method. A flag on the wrong root is not a true positive for a labelled error. Unknown source truth is not a negative control.

For NMA/IPD families, independently verify unique trial populations and multiple reports, every extracted trial-outcome value, shared controls, network transitivity/consistency, and outcome-specific RoB 2/RoB NMA assessments. Reproduce the **published** model first. Only then rerun a source-corrected model using compatible endpoints and treatment definitions. Record which conclusions, not merely which estimates, change.

## Prespecified results and uncertainty

Report per version and manual comparator:

- Substantive error-root recall including missed and abstained known errors; conditional sensitivity separately, never as overall recall.
- Precision of actionable flags, false alerts per 100 adjudicated negative claims, unchanged clean-control papers with at least one false flag per 100 eligible papers, and all source-limited/unknown denominators.
- Evidence-location correctness, retrieval coverage, unresolved questions, severity, distinct paper/trial-family roots and affected outputs.
- Reviewer minutes, total review cost, false allegations prevented, repeat-run agreement and coverage/abstention trade-offs.
- Paired comparisons on identical paper-family clusters, 95% uncertainty intervals with family-level clustering, and a sensitivity analysis for unadjudicated claims. Do not extrapolate from an error-enriched sample to prevalence in all publications.

No numerical performance threshold is declared achieved here. The independent custodian should preregister acceptable false-alert harm, minimum evidence coverage and a stopping/escalation rule before seeing results. If prospective control performance is poor, retire the detector candidate or repair it using development data, then freeze a *fresh* unexposed cohort for final assessment.

## Existing tooling

Follow [SYNTHESIS-REPORTING-v0.1.md](SYNTHESIS-REPORTING-v0.1.md) and the offline synthesis_blind_eval.py manifest/prediction/adjudication SHA-256 contracts. Those checks establish file consistency, **not** source truth, blinding, reviewer independence or a cryptographically signed attestation.

Development scripts synthesis_v13_checks.py, synthesis_v13_evidence.py and synthesis_v13_nma_preflight.py create only synthetic/administrative outputs. Do not commit private author correspondence, raw protected ledgers or unlicensed manuscripts. Do not send new author/journal allegations based on candidate benchmark flags.

**Current scientific validation result: UNKNOWN.** This document does not execute masked review, confer a publication-performance claim or authorize automatic Synthesis outreach.
