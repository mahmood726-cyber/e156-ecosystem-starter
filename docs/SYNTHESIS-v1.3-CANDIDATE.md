# Synthesis v1.3 — evidence-integrity development candidate

**Updated 3 November 2026 · Status: experimental implementation integrated into main; not scientifically validated**

This document describes a candidate extension to Synthesis v1.2 and the existing v1.1 preflight validator. It does **not** supersede the canonical internal standard, alter prospective protocols, adjudicate any paper, authorize author contact, or certify a published scientific error. The implementation accompanying it is deliberately small, offline and fail-closed.

## Current integration and limitations (3 November 2026)

- [PR #64](https://github.com/mahmood726-cyber/e156-ecosystem-starter/pull/64) merged the development candidate on 2 November at commit `ee66c160`; **210/210 synthetic v1.3 checks passed** and full repository checks passed on that merge SHA. This is software integration, not source authentication or clinical detection validation.
- The canonical v1.2 methodology and all separately frozen cohorts remain unchanged. Private correspondence, raw case ledgers and signed/protected historical records stay outside this public repository.
- The receipt/accounting module (`scripts/synthesis_v13_evidence.py`) validates caller-supplied evidence packet fields and sent-ID deduplication; it cannot authenticate their truth or email delivery. The NMA/IPD preflight (`scripts/synthesis_v13_nma_preflight.py`) detects narrowly identified potential trial overlaps, shared-control covariance problems and replay-readiness gaps; it neither fits NMA models nor independently reproduces results.
- Unequal floating cross-document values now require attested exact unrounded inputs **or** source-verbatim decimal precision and a declared rounding rule. Unverified precision abstains. Equivalent overlapping printed rounding intervals do not generate a discrepancy candidate.
- Read the [blinded validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md) and [audit packet/accounting contract](SYNTHESIS-v1.3-AUDIT-PACKET.md). The independent validation study has **not** been performed. Real-paper sensitivity, precision, false-alert rates, abstention harm and reviewer time remain UNKNOWN.
- The original 31 October change notes below are historical development records; their head SHAs, PR statuses and smaller test counts are not the current integration status.

## Objective

Increase true detection of substantive scientific inconsistencies **without** an unacceptable increase in false alerts, wasted reviewer time or incorrect author allegations. All test cases in this public repository are synthetic; development-case correspondence remains private. A correct arithmetic calculation does not prove that the source endpoint, analysis population or statistical model is correct.

## Modules and interfaces

1. **Numerical** — counts, denominators, CI ordering, raw OR/RR, P values and units, each with declared estimator constraints.
2. **Identity** — trial family, intervention, comparator, endpoint, population, follow-up and version matching.
3. **Statistical implementation** — coding conversion, model/variance choice, multiplicity, missing-data methods, survival, censoring and test-statistic identity.
4. **Cross-document** — abstract, paper, tables, figures, supplement, protocol/SAP, registry and related publications.
5. **Meta-analysis integrity** — study overlap, shared controls, harmonised endpoints, transformation, uncertainty methods, multi-arm accounting and source-true extraction.
6. **Figures, references and code** — visual labels, axis orientation, corrected citations and meaningful paper–code semantic discrepancies at an identifiable historical revision.
7. **Mandatory refutation** — seek the strongest plausible benign explanation and record where it was tested; abstain when evidence is insufficient.
8. **Root-cause learning** — group errors by mechanism while retaining every affected output and every unflagged/abstained claim.

The initial `scripts/synthesis_v13_checks.py` implements conservative, bounded primitives: explicit estimator signatures; CI order; unadjusted 2×2 odds ratios; a narrowly identified normal z-test; source-statistic identity; observed 0/1→1/2 factor conversion; cross-document matching; document-version states; source/refutation gates; root-cause grouping; and transparent claim-denominator summaries. It **does not yet** implement comprehensive literature retrieval, trial-family reconstruction, native meta-analysis, model replay, code audit, or an AI detector. None of the functions automatically declare a publication wrong.

## Required estimator signature

`population`, `endpoint`, `time_window`, `effect_measure`, `estimand`, `model`, `adjustment`, `multiplicity`, `missingness`, `censoring`, `variance_method`, `test_statistic_identity`.

Material unknowns or differences produce `NOT_COMPARABLE` unless the particular checking function explicitly limits the necessary signature. Crude event ratios must not be substituted for Kaplan–Meier/Cox estimates, adjusted models, ITT permutations or time-varying analyses.

**Normal-z false-alert control (31 October 2026 candidate delta).** A reported P value must not be recomputed as if the null were zero, the test two-sided, or the estimate and SE on the same scale by default. The `p_from_normal_z` primitive now requires separately verified normal-z test identity, explicit null, one-/two-sided direction, and identical declared effect and SE scales (linear or log-ratio); incomplete inputs return `NOT_COMPARABLE`. Paired synthetic regressions cover a deliberately wrong P versus valid nonzero-null, one-sided and log-ratio controls. The previous 35 synthetic tests are not evidence of prospective accuracy; newly added tests are mechanism checks only. Rounding-precision-aware P tolerances, historical-source replay, external review and independent held-out assessment remain outstanding. A heterogeneity Q-test P value does not verify a meta-analysis pooled effect P value. Correction notices and version provenance must be checked before treating a discrepancy as current.

## Independent evidence fields

Separate these dimensions; do not collapse them into a confidence score:

- Source-support: `SUPPORTED`, `CONTRADICTED`, `OVERGENERALIZED`, `UNSUPPORTED_CITATION`, `SOURCE_UNAVAILABLE`, `NOT_ENOUGH_INFO`.
- Maturity: `SCREENED`, `SOURCE_BACKED`, `REPRODUCED`, `INDEPENDENTLY_ADJUDICATED`.
- Disposition: `FLAG`, `RECONCILED`, `DISCUSSION`, `HOLD`, `NO_FLAG`.
- Correspondence: `NOT_SENT`, `SENT`, `ACKNOWLEDGED`, `AUTHOR_CONFIRMED`, `AUTHOR_DISAGREED`, `CORRECTION_REQUESTED`, `CORRECTION_PUBLISHED`, `RESOLVED_NO_ERROR`, `UNRESOLVED`.
- Severity: `S1` cosmetic; `S2` local typo; `S3` material numeric/reporting defect with apparently unchanged interpretation; `S4` plausible interpretation impact; `S5` potentially conclusion/recommendation/safety-changing. Severity is not confidence.

Keep exact source access paths, source-version/hash, claim locator, refutation evidence, model/tool version, root cause and all denominator-eligible nonflags and abstentions. An acknowledgement of an email is not scientific confirmation. An author requesting an erratum is not a published erratum. An independently verified analytical disagreement may warrant discussion but no allegation.

## Testing method

**Retrospective development:** Historical correspondence and known correction notices are useful as regression and failure-analysis examples only. They were selected because an issue was noticed; they cannot yield an unbiased sensitivity/specificity estimate.

**External engineered challenges:** On unseen papers and properly licensed, unexposed datasets, compare structured manual checking, existing Synthesis v1.2 and candidate v1.3. Include independently labelled errors and unmodified control documents; test several errors per document, long-context evidence spans, paper–code mismatches and OCR/notation false positives. Do not tune on held-out data.

**Real prospective evaluation:** Preserve the separately frozen Simo v0.10 36-claim/12-trial-family cohort unchanged. A future expanded study requires preregistered sampling of papers/trial families, enumeration of flagged **and unflagged** claims, masked independent expert review with conflict exclusions and adjudication of disagreements. Unknown/unavailable cases must remain in the denominator record.

**Outcomes:** Sensitivity for adjudicated substantive errors, precision of actionable flags, false alerts per 100 independently assessed claims, abstention, retrieval coverage, evidence-span correctness, missed errors, severity, root cause versus affected outputs, reviewer time/cost, and repeated-run agreement. Report confidence intervals with clustering by paper/trial family; never extrapolate from 35 synthetic tests or 36 frozen claims to real-world accuracy. Assess model score calibration; a model's own confidence never waives verification.

## External scientific methods informing the design

- [Bianchi et al., AI Paper Correctness Checker](https://arxiv.org/abs/2512.05925): independent flag precision and controlled inserted-error recall require different denominators; OCR and unfamiliar notation can induce false positives.
- [Nuijten et al., statcheck](https://github.com/MicheleNuijten/statcheck): deterministic, auditable statistical extraction is useful within explicitly supported reporting formats.
- [SciCoQA](https://ukplab.github.io/scicoqa/): distinguish genuine semantic paper–code mismatches from code-only bugs; stratify real and synthetic cases.
- [PaperAudit-Bench](https://aclanthology.org/2026.emnlp-main.474/): stress-test sparse document errors under held-out controlled interventions.
- [FIND](https://aclanthology.org/2026.findings-acl.1675/): demand accurate evidence spans in long technical documents.
- [Project APE, Verifying the Verifiers](https://ape.socialcatalystlab.org/verify): separate recall on planted changes from expert-reviewed precision on unmodified papers; test repeatability, error interference and poor confidence calibration.
- [La et al., Eye 2026](https://www.nature.com/articles/s41433-026-04965-5): paired planted-error and untouched-control clinical manuscript evaluation.
- [Penelope.ai](https://www.penelope.ai/), [SciTrue](https://www.scitrue.ai/how-it-works), [Code Ocean](https://docs.codeocean.com/osl-guide/publishing-on-code-ocean/the-verification-process/code-oceans-verification-process-for-computational-reproducibility-and-quality), [STM Integrity Hub](https://stm-assoc.org/what-we-do/strategic-areas/research-integrity/integrity-hub/stm-integrity-hub-pilot-program/): useful but distinct manuscript checks, source-grounding, computational replay and publisher distribution models. None is equivalent to source-to-claim scientific adjudication.

## Local development verification

```bash
python3 -B -m unittest discover -s tests -p 'test_synthesis_v13_checks.py' -v
```

At local creation, **35/35 synthetic tests passed**. Hosted CI and protected-branch tests must be rechecked on the exact eventual PR head. These tests check code behaviour on constructed examples, *not* accuracy on published papers. Current estimator signatures are conservative and may abstain even when a more specialized comparison could be justified; this is an intentional development limitation.

## Change-control constraints

**Historical 31 October rule:** the candidate was initially kept separate from Preflight v1.1 PR #60 and v1.2. PR #60 subsequently merged and the v1.3 implementation entered main through PR #64 on 2 November. Preserve frozen protocols, e156 protected attestations, exact-head full CI, provenance and independent scientific validation. Do not alter historical certificates, infer an error, authorize external contact or publish private correspondence from this code. The repository owner has elected not to require new GitHub branch-protection settings; required CI and evidence-truth constraints still apply. Any publication-performance claim requires separate independent prospective evaluation.

## Printed-P precision safeguard (31 October 2026 candidate delta)

A fixed absolute 0.01 P tolerance could incorrectly call a result consistent across a 0.05 decision boundary: a two-sided normal-z value of 1.89 implies P≈0.05876, while a supplied published P=.049 was previously accepted. The candidate now requires verbatim published P notation and source-verified input precision. Exact test inputs or independently derived P bounds covering *all plausible rounding of printed source statistics* are mandatory; otherwise the checker returns `NOT_COMPARABLE`. It distinguishes `P=.05` (nearest-two-decimal display), `P<.001`, `P<=.001` and `P>.05`. Unsupported OCR glyphs, ambiguous precision and numerical/text mismatch fail closed. It tests notation compatibility rather than asserting that the reported P is the erroneous component. `P=.000` is treated as a possible *rounded* display, not proof of an exactly zero P; journal presentation guidance is a separate matter.

Ten new synthetic regression methods include a decision-boundary injection, matched benign rounding and inequality controls, verified input-range tolerance, absent input-range abstention, OCR corruption, and a source-text/numeric inconsistency. Historical or selected papers cannot establish new held-out accuracy. The source-derived P-bound calculation, full repository CI, independent adversarial code review and clinically relevant source-matched blinded evaluation remain required. The previous 0.01 numeric tolerance is no longer a source-fidelity substitute.

## Abstention and denominator accounting safeguard (31 October 2026 candidate delta)

The earlier `outcome_counts` reported `sensitivity = TP/(TP+FN)` after excluding every `HOLD`, including source-labelled errors. In a synthetic paired example with one flagged known error and one held known error, it returned 100% conditional sensitivity despite automatic detection of only 1 of 2 labelled errors. That conditional figure is not the programme's full-cohort error recall. The candidate retains the original fields for compatibility but adds `flag_recall_including_abstentions = TP/(TP+FN+HOLD_ERROR)` and discloses `HOLD_ERROR`, `HOLD_NO_ERROR`, `HOLD_UNDETERMINED`, total unknown references, claim-level labelled coverage and nonabstention coverage. A deliberately clean held claim remains in the denominator and is not called an error.

The older `false_alerts_per_100_adjudicated` is *conditional on a labelled, nonabstained subset*. A separate `false_alerts_per_100_reference_known` includes labelled held claims in the denominator, while leaving truly unknown-reference claims out of any judged rate. These are different estimands; neither is an unchanged-*paper* false-alert rate. That latter metric still needs paper IDs, complete untouched controls and independent adjudication. No function authenticates the caller's reference labels, and missing labels do not become true negatives. Confidence intervals, reviewer costs and selection-adjusted estimates remain outside this primitive.

Four additional injected/benign synthetic regression methods check held true errors, held clean controls, false-alert denominator divergence and all-undetermined labels. All comparisons are *development accounting*, not independent paper-level or clinical performance evidence. Selective classification literature highlights the need to report risk alongside coverage ([Jones et al., 2020](https://arxiv.org/abs/2010.14134)); no benchmark software, private correspondence, or benchmark labels are imported.


## Complete clean-paper false-alert denominator (31 October 2026 candidate delta)

A previous claim-only summary could not report *papers with at least one false alert per 100 unchanged control papers*. It risked mistaking one flagged paper for multiple alerted papers and silently losing partially inventoried or unadjudicated negative controls. The experimental \`unchanged_control_false_alerts(papers, claims)\` bookkeeping primitive therefore keeps **three different estimands** separate: papers with >=1 false alert per 100 eligible clean papers; false-alert *flags* per 100 eligible clean papers; and false-alert flags per 100 eligible clean-paper claims. These must never be interchanged.

A paper labelled \`CLEAN_UNCHANGED\` is eligible only if its declared claim inventory is complete, its claim IDs exactly match its recorded predictions, and *every* claim carries the \`NO_ERROR\` reference label. Incomplete inventories, unknown labels or detected actual errors hold the paper out of the clean-negative denominator, with explicit hold counts. An unchanged article may itself contain errors, so an untouched paper is **not automatically** a verified clean control. The labels and inventory assertions remain caller-supplied and unauthenticated; human verification of the current Version of Record, complete claim enumeration and independent masked adjudication is needed before reporting real-world accuracy.

Seven synthetic tests include a positive planted-error paper alongside an unchanged benign control; two false alerts in a single clean paper (one alerted paper, two flags); incomplete inventories; unresolved or contradictory references; unknown paper status; duplicate claims; and undefined rates when no eligible controls exist. Passing these tests **does not imply** zero real false alerts, actual sensitivity, prospective clean-paper performance or best-in-field parity. Reviewer minutes, cost and clustered confidence limits remain unmeasured. The existing frozen prospective cohorts and versioned source rights are unchanged.


## Current-Version Claim Gate (31 October 2026; experimental)

**Failure mechanism:** Previous gate() accepted FINAL_CURRENT or CORRECTED_LATEST plus a source-backed contradiction without requiring proof that the exact disputed claim persists in the current Version of Record or relevant correction notices were checked. An old PDF discrepancy could create a stale candidate.

**Current claim and correction evidence.** A candidate requires `current_claim_verified=True` and either `NO_RELEVANT_CORRECTION` or `CORRECTION_REVIEWED_CLAIM_PERSISTS`. For `RESOLVED_IN_PUBLISHED_VERSION`, provide `correction_source_verified=True` and an exact `correction_locator`. Also set `corrected_claim_verified=True` only after checking that the authoritative replacement resolves this particular claim, and provide its `corrected_claim_locator`. An explicit replacement in a publisher notice can supply the latter locator. A notice about another claim, a planned amendment, or an unexplained conflict across displayed versions requires `HOLD`. The gate validates caller declarations and has no authority to certify an error or authorize outreach.

**Paired synthetic witnesses:** A current, method-matched injected contradiction remains FLAG_CANDIDATE; a previously reported contradiction resolved in a verified published correction becomes RECONCILED. Unknown correction history, missing current-claim verification, and unsupported or unlocated correction claims abstain. Six new synthetic tests are development checks, never held-out sensitivity or precision.

**Scientific provenance:** Crossref documents publisher-supplied status via [Crossmark](https://www.crossref.org/crossmark/) and [registering updates](https://www.crossref.org/documentation/register-maintain-records/maintaining-your-metadata/registering-updates/). Separate notice DOIs and in-place changes exist; a missing Crossmark entry does NOT prove absence of a correction. Audit exact current publisher text, supplements, notices and claim spans directly. Preserve current/old version identifiers and exact source/notice locators privately.

**Required next gates:** exact-head scoped CI; separate adversarial review; non-leaking real-paper blinded evaluation of flagged and sampled unflagged claims, including appropriately corrected and unchanged controls. No change to v1.2 Standard, PR #60, frozen samples or contacts.


## 31 October 2026 — full-analysis-identity gate for cross-document numerical comparisons

**Root-cause development ID:** `SYN-METHODS-20261031-CROSS-DOC-ANALYSIS-IDENTITY-010`.
Previously `cross_document()` protected five core target-question fields (population, endpoint,
time window, effect measure and estimand), while model, covariate adjustment, multiplicity,
missingness, censoring, variance method and test-statistic identity were only mandatory
when explicitly requested by the caller. A caller specifying just `("endpoint",)` could
therefore produce a `REVIEW` alert for different but legitimate adjusted and crude outputs.

**Falsifiable change:** require the complete existing 12-field `ESTIMATOR_FIELDS`
signature in every `cross_document()` comparison, in addition to the already required
source-attested numeric unit and representation. Missing or mismatched fields return
`NOT_COMPARABLE`. The supplied source attestations are not independently authenticated.

**Paired synthetic regression controls:** ten new tests cover a deliberately different
same-analysis value (retains `REVIEW`), unchanged matched value (retains `CONSISTENT`),
and benign/uncertain differences in adjusted vs crude, model, multiplicity, missingness,
censoring, variance method, statistic identity and unknown adjustment (all abstain).
Thus 97 -> 107 synthetic methods if the entire scoped test suite passes. These are
constructed cases, not adjudicated claims or fresh held-out accuracy evidence.

**Scientific rationale:** ICH E9(R1), FDA final guidance (May 2021),
https://www.fda.gov/regulatory-information/search-fda-guidance-documents/e9r1-statistical-principles-clinical-trials-addendum-estimands-and-sensitivity-analysis-clinical
and Cochrane Handbook Chapter 24,
https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-24
support distinguishing target estimands, analysis estimators and adjusted from unadjusted
effects. A mismatch in analysis method is not by itself a published error.

**Adversarial limitation:** this may over-abstain when two estimators yield the same
legitimately comparable point estimand; flag recall and coverage could fall. Require
independent source extraction, exact-head full-repo CI, adversarial review and prespecified
blinded real-paper measurement before promotion, parity claims or merge.


## 31 October 2026 — large exact-integer cross-document precision gate

**Root-cause development ID:** `SYN-METHODS-20261031-LOSSY-COUNT-011`. Previously,
`cross_document()` converted all numbers to binary floats through `finite()`. In
Python, `float(2**53 + 1) == float(2**53)`, so two distinct source-attested integer
counts could silently become `CONSISTENT`. This is a deterministic software
failure, not a claim of an actual scientific-paper error.

**Reversible change:** when both numbers and the tolerance are native integers,
compare with arbitrary-precision integer arithmetic. When a large integer is mixed
with a float, or large floating values may already be rounded, return
`NOT_COMPARABLE` rather than asserting consistency or disagreement. Preserve the
prior small-float path and its explicit estimator/unit/representation gates.
Callers must still verify original source values and source precision.

**Synthetic paired witnesses:** the injected `2**53+1` vs `2**53` exact-count
discrepancy now produces `REVIEW`, while an unchanged `2**53+1` pair remains
`CONSISTENT`. Nine new tests cover exact tolerances, mixed/large-float abstention,
ordinary float continuity, booleans and invalid negative tolerance. If passing,
the scoped suite grows from 107 to 116 synthetic tests; this is NOT a measured
improvement in clinical recall or precision.

**Source/rationale:** Python numeric documentation, https://docs.python.org/3/library/stdtypes.html
(ints have arbitrary precision, floats generally binary64). No public dataset or
third-party code was imported. **Potential disadvantage:** extra abstentions on
large float values may hide true discrepancies. External, independent source-level
review and held-out matched-budget testing are required before promotion. Keep the
v1.2 Standard, frozen cohorts, correspondence and protected branch policies intact.

## 3 November 2026 — fail-closed source precision, NMA preflight and audit packet

**Cross-document precision contract.** `cross_document()` retains exact integer arithmetic. For unequal floating-point comparisons, the caller must either attest exact unrounded source inputs (`source_values_exact=True`) or provide both source-verbatim printed literals, `published_precision_verified=True`, and `display_rounding_rule="NEAREST_DECIMAL"`. In the latter path the checker conservatively includes halfway ties and checks interval overlap, returning `NOT_COMPARABLE` for incomplete/ambiguous/OCR-unverified precision. Passing source attestations remain unauthenticated; even `REVIEW` is a candidate for human inspection, not an error verdict.

**Independent evidence receipt.** `evidence_packet()` requires a current claim, correction check, matched analysis, exact locators and SHA-256 source identifiers, original report, reconstruction and benign-alternative refutation. It outputs only `READY_FOR_INDEPENDENT_REVIEW`, never an error certification. `reconciliation_summary()` separately counts administratively eligible distinct substantive root records and distinct actual-message identifiers, with independently adjudicated caller attestations and documented Synthesis discovery. Consolidated emails may cover multiple independent roots. Neither function checks private Gmail, verifies publication contents, nor proves correspondence was sent.

**NMA/IPD integrity preflight.** `duplicate_trial_population()` and `shared_control_dependence()` flag only explicitly source-attested duplicated independent effects or unaccounted shared controls; different cohorts/endpoints or verified covariance handling are negative controls. `replay_readiness()` requires original published-model replay before corrected-analysis replay; outcome-level source extraction, unique populations, RoB 2/RoB NMA, transitivity/consistency and conclusion sensitivity are mandatory evidence references. These are administrative/source-identity gates. Comprehensive source retrieval, native network estimation and independent source-level verification remain open development work.

**Restriction accounting.** When a sensitivity analysis explicitly restricts the primary analysis, pass `restricted_analysis_accounting()` the exact participant counts, their source locations, the location of the restriction, and verified same-version and same-count-basis attestations. A higher restricted count opens a review candidate. Check which data and trial families entered each analysis before attributing the discrepancy. Analyses that add or substitute studies are non-comparable, and unclear scope or count definitions require a hold. Equal or lower counts pass this check without proving actual cohort membership. The [published ACS network and sensitivity results](https://www.frontiersin.org/journals/cardiovascular-medicine/articles/10.3389/fcvm.2026.1717817/full) illustrate why this check is useful. The [PLOS ONE diet-review correction](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0200284) supplies a contrasting example in which the restricted count decreases after a duplicate trial report is removed.

## Source result identity

For new source-backed numerical comparisons, supply `result_identity` on both estimator signatures passed to `cross_document()`. Each mapping requires `verified=True` and canonical text for `source_result_id`, `data_version`, ordered `intervention` and `comparator`, `denominator_basis` and `component`. Use a stable result key grounded in the source row, including when that row is repeated in a different artefact. Use explicit source-verified text such as `no comparator` for a single-group result. Any missing or differing identity returns `NOT_COMPARABLE` before arithmetic. Existing callers that omit both identity mappings retain the estimator-only comparison.

Use `source_assignment(field, reported, source, same_assignment_verified=True)` when the assignment itself is in dispute, such as which cohort a source row describes. Each mapping contains the canonical `value`, exact `version`, `locator` and `verified=True`. Set the same-assignment attestation only after establishing that the report refers to that specific source field. Resolve aliases first. A mismatch returns `REVIEW` with both locators and versions, even when the accompanying arithmetic agrees. A comparison between legitimately different analyses stays `NOT_COMPARABLE`.

| Public development example | Check and control |
|---|---|
| A [Scientific Reports correction](https://www.nature.com/articles/s41598-026-50693-x) reassigns samples that the [archived original, Methods Table 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC10070245/) puts in another cohort. | Verify the cohort label against the same dataset record. Hold an apparent mismatch if the dataset or result ID differs. |
| A [BMC Medicine correction](https://link.springer.com/article/10.1186/s12916-025-04033-x) aligns the study-design description with the comparison-group definition in the [archived original, Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11613771/). | Verify the ordered treatment and comparator independently of the effect values. |
| A [BMC Public Health notice](https://link.springer.com/article/10.1186/s12889-026-29536-x) gives replacement wording for the main association and retains the separate moderation finding. The [article display](https://link.springer.com/article/10.1186/s12889-025-23265-3) still showed the previous wording on 4 November 2026. | Record the authoritative replacement and its exact target. Keep main association and moderation separate, and record any display discrepancy independently. |

| Fixed design | Source-derived evidence |
|---|---|
| Required identities, evidence fields and synthetic control scenarios | Exact source result, ordered groups, component, denominator, data version and locators for each real comparison |
| Rule that an identified notice alone cannot reconcile a claim | Publisher notice, version and replacement span checked against the disputed claim |

The open-access development screen covered 1,000 unique notice bodies. Keyword matches informed triage and can overlap. The three paired examples above were checked at the affected passage. Synthetic tests exercise the software decisions. Independent blinded evaluation is required to measure detection performance on unseen papers.

All added regressions are synthetic; do not use them to estimate real-paper performance. Preserve the Simo v0.10 frozen 36-claim/12-family cohort, the separately proposed 24-family benchmark and any other held-out manifests without modification or label leakage.
