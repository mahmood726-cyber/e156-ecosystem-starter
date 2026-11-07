# Count provenance, restricted analyses and correction propagation

**Development review, 7 November 2026.** This change responds to the completed full-paper prompt comparison. Those papers are now development material. The changes below have software regression checks and public-source replay diagnostics; improved detection accuracy has not been measured on a new untouched sample.

## What changes

- The short core distinguishes arithmetic agreement, source-tally verification and correction propagation. Internally consistent categories can still contain wrong source counts. Reviewers should request the authorised aggregate extraction or eligibility ledger when that evidence is needed.
- Normal PMC intake can bind reviewer-selected integer tokens in abstract/body text and supported compound cells, retaining exact snapshot, quote, locator and text offsets. Repeated excerpts require an exact indexed locator. Ambiguous, unsupported or missing evidence holds.
- A restricted count below its parent stays HOLD without a source-bound exclusion ledger, attested disjoint and exhaustive. A ledger mismatch can flag a wrong restricted count even when it is below its parent. Rematching and different risk sets must not be treated as strict subsets.
- A correction trace and its revision sweep have separate outcomes. A selected corrected table can match while mapped prose still differs. The sweep retains unchecked dependencies; matching mapped occurrences does not certify complete propagation.
- Every count finding records `count_validity: NOT_INDEPENDENTLY_VERIFIED`. The feature checks mapped printed evidence, not participant records, scientific meaning or author truthfulness.

See the [packet contract](SYNTHESIS-PREFLIGHT-PMC-COUNTS.md), [core prompt](SYNTHESIS-COPY-PASTE-AI-PROMPT.md) and [participant worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md).

## Public evidence behind the change

**Internally coherent wrong inputs.** The [G-KNIGHT article](https://doi.org/10.1007/s10120-025-01641-7), PMC12378153.1, reports stable disease 82 and progressive disease 21 among 299 response-evaluable patients. Its [published correction](https://doi.org/10.1007/s10120-026-01772-5), PMC13524959.1, replaces these with 78 and 25, leaving the denominator unchanged. The original categories and reported disease-control rate are internally consistent; arithmetic alone cannot identify the correct classification. A notice can establish published replacements without reproducing the source response ledger.

**Incomplete propagation.** In [the pulmonary WHO-group article](https://doi.org/10.3389/fmed.2025.1561387), PMC12010923.1, the severe group contains 54 people. The [correction notice](https://doi.org/10.3389/fmed.2026.1793266), PMC13014252.1, replaces the table's male and female counts of 26 with 27 each. The retrieved table incorporates those replacements, but Results 3.1 still prints 26 men alongside 50.0%. A table-only MATCH cannot clear that prose conflict. This refers to the inspected snapshot, not an assertion about the latest publisher rendering.

**Restricted-category ambiguity.** G-KNIGHT Figure 3g describes 28 exclusions for unknown ascites severity, while Table 1 has 24 unclear-severity patients among all patients with known ascites. A broader definition involving unknown ascites presence could explain the difference. The cross-tabulation is missing, so the concern remains unresolved; it is not a confirmed inflated count. The feature does not convert the caption's word number into an automatically verified integer.

## Normal-intake replay diagnostics

The same archived public JATS, document identities and reviewer-selected comparisons were replayed through the normal preflight CLI at baseline `5413440da99271ccdbe4b17c107e43f961614334` and this implementation. These are opened development cases, not a new accuracy evaluation. No public paper was altered or given an injected error.

| Public-source mapping | Baseline | Updated evidence capture |
|---|---|---|
| Nurse-study eligibility: 1,321 baseline respondents minus 118 excluded equals 1,203 eligible/randomised | HOLD: quoted count references unsupported | NO_FLAG for mapped printed accounting; expected count 1,203; source records remain unverified |
| G-KNIGHT stable-disease count: original compound cell 82 versus notice replacement 78 | HOLD: decisive pair unsupported | PUBLISHED_CORRECTION; sweep flags superseded table and prose values; figure pixels and response ledger remain unchecked |
| G-KNIGHT 527 effectiveness patients versus 299 response-evaluable patients, without an exclusion ledger | HOLD | HOLD; the bound passes, but actual membership accounting is unresolved |

The [nurse-study article](https://doi.org/10.1093/joccuh/uiaf061), PMC12638291.1, states the eligibility flow in one paragraph. The initial excerpt for 1,203 matched both abstract and body and correctly held. A reviewer selected the exact body locator without changing the source counts; the diagnostic replay then checked the ledger. This mapping refinement is not a frozen-test success.

Article-level CC BY 4.0, typed identities, version and raw snapshot SHA-256 were verified by capture for these replayed sources. The inspected source digests are:

| Source | Raw XML SHA-256 |
|---|---|
| [PMC12638291.1](https://pmc-oa-opendata.s3.amazonaws.com/PMC12638291.1/PMC12638291.1.xml) | `7751bfe0636800db944bfd1e139a4560bca820baf0aa2da85875422a5c7f3546` |
| [PMC12378153.1](https://pmc-oa-opendata.s3.amazonaws.com/PMC12378153.1/PMC12378153.1.xml) | `1c20770a6e05a421ceca35252f0ef11da5df48ed7eb4b2e156c463f6a5f717ea` |
| [PMC13524959.1](https://pmc-oa-opendata.s3.amazonaws.com/PMC13524959.1/PMC13524959.1.xml) | `99906391049e17e19aef5b25ed08f91e413de8e69efd18f0a974bfe55478a900` |

The pulmonary article and notice remain on HOLD under the existing dated-licence policy in automated intake. Their manually inspected public passages motivate the synthetic stale-prose regression; no licence declaration was removed to obtain an automated result. Figure images, attachments, registries, model code and participant records were not audited. Correction comparison is not independent discovery of an error.

## Regression and evaluation boundaries

The synthetic normal-intake tests exercise a wrong smaller restricted count, matching accounting, missing/overlapping exclusions, aliased tokens, two counts in one paragraph, repeated compound cells, partial numeric matches, percentages, unsupported styling, ambiguous excerpts and a corrected table with stale prose. Synthetic counts are software fixtures, not research findings. The [tests](../tests/test_synthesis_capture_evidence.py) and [implementation](../scripts/synthesis_participant_evidence.py) contain the reproducible contracts.

The prior full-paper comparison used these public article identities: PMC11154119, PMC13472939, PMC13730552, PMC13730512, PMC12378153, PMC12638291, PMC13737348, PMC13729332, PMC12010923, PMC13356027, PMC13731994 and PMC13727397. Exclude those papers, their correction notices and linked trial/cohort families from a future untouched accuracy test. Freeze fresh families, model/tools, source versions and equal budgets before testing; retain misses, abstentions and retrieval failures. Do not infer precision or sensitivity from these replay diagnostics.

| Fixed design or source-transcribed annotation | Dynamically read or executed evidence |
|---|---|
| Reference schema, quote limits, ledger attestations and mapped sweep scope | Source identities, rights, exact bytes/digests, quotes and indexed offsets |
| Selected public development comparisons and synthetic fixture definitions | Actual CLI findings, expected-count arithmetic, holds and regression outcomes |
| Prompt guidance | No newly measured prospective accuracy or independent participant-data reproduction |

Only public source material and synthetic fixtures support this PR. Private correspondence, completed private ledgers, detector transcripts and sealed answer keys are excluded. No outreach or manuscript certification is performed.
