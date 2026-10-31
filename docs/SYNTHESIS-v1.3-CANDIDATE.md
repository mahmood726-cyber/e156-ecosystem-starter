# Synthesis v1.3 — evidence-integrity development candidate

**31 October 2026 · Status: experimental, not scientifically validated**

This document describes a candidate extension to Synthesis v1.2 and the existing v1.1 preflight validator. It does **not** supersede the canonical internal standard, alter prospective protocols, adjudicate any paper, authorize author contact, or certify a published scientific error. The implementation accompanying it is deliberately small, offline and fail-closed.

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

Material unknowns or differences produce `NOT_COMPARABLE` unless the particular checking function explicitly limits the necessary signature. Crude event ratios must not be substituted for Kaplan–Meier/Cox estimates, adjusted models, ITT permutations or time-varying analyses. A heterogeneity Q-test P value does not verify a meta-analysis pooled effect P value. Correction notices and version provenance must be checked before treating a discrepancy as current.

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

Build this v1.3 candidate **separately** from unmerged Preflight v1.1 PR #60 and from the v1.2 public-site proposal. Keep frozen protocols, e156 protected attestations, all full CI gates and required independent human review. No bypasses, no merge without exact-head CI and provenance, no alteration to historical certificates, no external contact and no private correspondence in this repository. Any future publication-performance claim requires a separate independent, prospective evaluation.
