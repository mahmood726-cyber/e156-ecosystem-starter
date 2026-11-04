# Synthesis IPD meta-analysis surveillance — ten-workstream programme

Initiated 2026-11-04. **Experimental, review-first protocol.** This replaces the ten correction-learning automations in their respective time slots, without merging or deleting the prior campaign's work. The correction-learning evidence remains in draft PR #67 with a dedicated handoff manifest at `docs/SYNTHESIS-CORRECTION-LEARNING-HANDOFF-TO-IPD-20261104.md` on its preservation branch.

## Objective

Systematically review **published individual participant data (IPD) meta-analyses** across medicine, find source-reproducible analytical or reporting questions, prioritize material issues, and improve Synthesis via source-backed regression tests and independent validation. Do not invent errors to satisfy a quota. Distinguish true participant-level one-stage/two-stage IPD, pooled trial-level aggregate meta-analysis, pseudo-IPD from reconstructed Kaplan–Meier curves, patient-level registry pooled analyses and IPD network meta-analysis.

## Source and code identity

Each worker reads fresh default-branch `AGENTS.md`, `docs/SYNTHESIS-v1.3-CANDIDATE.md` and `scripts/synthesis_v13_nma_preflight.py`, then records the **actual main head SHA** and any active version/tag before every review. Treat Synthesis v1.3 as experimental and do not claim it implements an end-to-end native IPD meta-analysis engine: its NMA/IPD code consists of conservative, source-attested preflight/readiness checks. Prefer published full reports and supplements, protocol and SAP, trial registries, dataset/code repositories and later corrections; confirm Version of Record and exact claim. Do not assert analysis reproduction without running original data and code.

## Ten disjoint audit lenses (all medical specialties)

| Shard | IPD audit lens |
| --- | --- |
| 00 | Discovery, study design and IPD provenance; distinguishing genuine/shared IPD, reconstructed and aggregate data |
| 01 | Participant/trial identity, exclusions, recruitment and repeated reporting |
| 02 | One-stage vs two-stage models, weighting, random effects and clustering |
| 03 | Survival IPD: censoring, left truncation, time origin, competing risks, proportional hazards |
| 04 | Treatment-effect modifiers: within-trial interaction, ecological bias, nonlinear covariates |
| 05 | Missing data, imputation, attrition, availability bias and selective IPD sharing |
| 06 | Binary and continuous outcomes: denominators, scales, transformations and uncertainty |
| 07 | IPD network meta-analysis: multi-arm correlations, transitivity, inconsistency and overlap |
| 08 | Reporting, cross-document results, tables, figures, safety and auditability |
| 09 | Independent replication, negative controls, case deduplication, reviewer burden and regression-test integration |

Distinct focus is a division of responsibility, **not** permission to claim that each review has different participants or cohorts. For duplicate articles and shared IPD databases, maintain the same family identifier and assign lead review by SHA-256(normalized DOI or canonical source URL) mod 10; cross-lens comments are secondary, never independent discovery credit. For a source without verified identity or overlapping units, HOLD.

## Review record

For each paper log DOI/title/journal/date, article/version and accessed source URL, IPD type, registration, trial/participant denominators, study inclusion list and overlap, consent/licence/access restrictions, claimed outcome/estimand, methodology and exact claim locator, published estimates and precision, source evidence and locator, independent computation (if performed), strongest benign explanations, S1–S5 materiality, status (FULL/PARTIAL/METADATA/HOLD/NO_FLAG/REVIEW_CANDIDATE/REFUTED/INDEPENDENTLY_ADJUDICATED), reviewer time, and stable family/claim key. One document read is not an independent adjudication, and inaccessible IPD prohibits claims of numerical reproducibility.

Investigate clinically relevant high-impact papers, but never imply an issue from a methodological preference alone; distinguish legitimate analytic alternatives, prespecification, unavailable historical protocol and benign rounding. For IPD access limitations, source-observable reporting checks can proceed but analysis replay must stay HOLD.

## Privacy, rights and safety

Never place actual participant-level records, reidentifiable values, restricted/licensed files, embargoes, private emails, usernames/tokens, clinical records or unpublished private correspondence in public GitHub. Public-only references, source-located summaries and synthetic/non-identifying fixtures are permissible. Respect source licences and data use agreements. No contact with authors, journals or sponsors by these IPD tasks without a new, case-specific authorisation. Never claim a prior correction is a new Synthesis-discovered error.

## Code and publication gates

Record each checked case as an immutable per-shard evidence file under `research/ipd_meta_audit/20261104/shard-XX/` on `research/synthesis-ipd-audit-20261104` or a separate short-lived branch; fetch current branch head before writing and do not overwrite another worker. Preserve negative controls, abstentions and near-miss cases. Require paired synthetic tests and held-out, trial-family-separated independent adjudication before claiming detector performance. Any engine change goes through a focused PR with exact-head CI, full-repository checks and independent review; do not merge if protections or approvals are missing. Keep main and all frozen canonical datasets unchanged until appropriate review.

## Scheduling and per-run report

Ten task slots, exact hourly, staggered six minutes in Europe/London at :00/:06/:12/:18/:24/:30/:36/:42/:48/:54. A six-minute offset does **not** ensure nonoverlapping runtime. Each run does a bounded review and reports real source URLs and locators, full/partial/held counts, source verification, reproducibility status, suspected and refuted issues distinctly, code/PR status and next cursor. If blocked by an app permission or missing data, record an explicit HOLD; do not fabricate completion or run results.

## Previous research preservation status

The correction branch was inspected and found to contain 21 evidence/test files in shards 00–08 and no shard-09 file. A committed handoff manifest on the preservation branch records those file counts. **Not all historical run output could be verified as committed;** this limitation is preserved rather than silently declared resolved. Both PR #66 and PR #67 stay open draft pending independent verification.
