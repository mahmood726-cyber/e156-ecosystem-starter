# Synthesis — methods and evidence guide

**Current experimental guide, 6 November 2026.** [Start with six checks](SYNTHESIS-HUMAN-CHECKLIST.md#start-with-six-core-checks), use the [AI prompt](SYNTHESIS-COPY-PASTE-AI-PROMPT.md) if permitted, and retain a private claim ledger. The checklist is a review procedure. It does not establish real-world detection accuracy.

## Scope and source record

Agree which documents, sections and claims will be reviewed. Preserve exact article, supplement, protocol/SAP, registry, code and correction versions where available. Record identifiers from the source, access route, permission, file hash when possible, locator and retrieval failures. An inaccessible source remains visible in the ledger. For long papers use fixed batches and stable claim IDs, including matching, flagged and unresolved claims.

A result needs an exact source passage or data location. Inspect the rendered source where extraction could change signs, symbols, table alignment or group assignment. A citation that does not support a statement is not proof that the statement is false. Historical corrected claims are distinct from current-version concerns.

## Comparability before calculation

The optional [normal-intake evidence contract](SYNTHESIS-INTAKE-EVIDENCE.md) binds count definitions, signed values and units to captured sources; it also retains mapped revision dependencies and redacted private-case states. The [author start page](SYNTHESIS-START.md) explains where the manual, prompt and Python routes run. These checks do not establish scientific accuracy.

Establish the relevant population, intervention, comparator, endpoint, time window, effect measure, estimand, model, adjustment, multiplicity, missingness, censoring, variance method and test identity. These correspond to the implementation's `ESTIMATOR_FIELDS` in [synthesis_v13_checks.py](../scripts/synthesis_v13_checks.py). Missing material fields or different estimators can require `NOT_COMPARABLE`.

For participant accounting use the [worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md). Separate people, events, observations and person-time. Verify the relationship between populations before subtraction or addition. For regressions establish coding, reference category, units and contrast before exponentiating a coefficient. For P values establish null, sidedness, scale, test and source precision. Preserve the published estimator when attempting reproduction.

Save actual inputs, formula, assumptions and working. Code-assisted calculations need the runnable script, package versions, command and raw output. A proposed script is `NOT_RUN` until executed. Arithmetic agreement does not establish that a value belongs to the intended cohort or analysis. Distinguish reproducing a printed difference from reproducing the underlying study.

## Short checklist results and detailed records

The four short results are reporting aids, not new software-schema values. There is no automatic conversion into an approved finding.

| Short result | Interpretation and possible detailed record |
|---|---|
| Pass | This scoped check has supporting evidence. A matching comparison may be `NO_FLAG`; a source-resolved mismatch may be `RECONCILED`. Neither clears the paper. |
| Review needed | A discrepancy requires investigation. `FLAG` needs the existing source, version, comparability and refutation gates. A preference or interpretation can be `DISCUSSION`. |
| Insufficient evidence | Preserve `HOLD`, the missing evidence and the stalled step. Distinguish `SOURCE_UNAVAILABLE`, `NOT_ENOUGH_INFO` and `NOT_COMPARABLE` as applicable. |
| N/A with reason | This check does not apply. Retain the claim and reason. Do not invent a software disposition or remove an inaccessible claim from the denominator. |

Keep these independent dimensions in the detailed record.

| Dimension | Values or required explanation |
|---|---|
| Source support | `SUPPORTED`, `CONTRADICTED`, `OVERGENERALIZED`, `UNSUPPORTED_CITATION`, `SOURCE_UNAVAILABLE`, `NOT_ENOUGH_INFO` |
| Evidence maturity | `SCREENED`, `SOURCE_BACKED`, `REPRODUCED`, `INDEPENDENTLY_ADJUDICATED`, with evidence of work actually completed |
| Disposition | `FLAG`, `RECONCILED`, `DISCUSSION`, `HOLD`, `NO_FLAG` |
| Issue class | Label/presentation, numerical value, analysis/code, citation, methodological discussion; split mixed points |
| Impact | Display only, numerical result, interpretation/conclusion, or undetermined; provide the basis |
| Severity | S1 cosmetic, S2 local typo, S3 material reporting/numeric issue with apparently unchanged interpretation, S4 plausible interpretation impact, S5 potentially conclusion/recommendation/safety-changing; severity is not confidence |
| Correspondence | Keep not sent, acknowledgement, author confirmation, disagreement, correction requested, verified published correction, resolved enquiry and unresolved stages distinct |

An author-reported impact assessment remains attributed until independently verified. A wrong label can coexist with correct calculations. A code defect in an unused model does not demonstrate an error in the published fitted result. Record which version and analysis generated that result.

## Refutation, revisions and replies

For every candidate mismatch test the strongest benign explanation against the source. If it cannot be tested, keep it unresolved. An acknowledgement validates neither a whole enquiry nor a performance claim. Read the original question and reply together and apply the [point-by-point response review](SYNTHESIS-RESPONSE-REVIEW.md).

Use the [revision sweep](SYNTHESIS-HUMAN-CHECKLIST.md#sweep-after-revisions-and-before-submission) after substantive edits and at submission/proof stages. Track every dependent location, saved recalculation, nearby unaffected check, reviewer/date and unresolved file. Check the semantics of each data block, including SD/SE labels, copied columns and units.

If human-authorised correspondence is needed, consolidate related points for the same paper into one prioritised record. Keep the message brief and put reproducible detail in an attachment. This guide does not initiate contact or override permissions or no-contact requests.

## Implementation boundaries

- [Preflight v1.1](SYNTHESIS-PREFLIGHT-v1.1.md) and [its packet contract](../scripts/synthesis_preflight.py) validate supplied records and evidence gates. A completed manual worksheet does not authenticate those records.
- [PMC capture and participant counts](SYNTHESIS-PREFLIGHT-PMC-COUNTS.md) archive source XML and evaluate reviewer-selected integer cells or uniquely quoted integer tokens in supported prose/compound cells. This is bounded mapping, not automatic semantic extraction. Restricted counts within a parent bound stay HOLD without a source-bound, reviewer-attested disjoint and exhaustive exclusion ledger. Correction sweeps compare mapped occurrences and preserve unchecked locations. Matching arithmetic does not independently verify the source tally.
- [v1.3 checks](../scripts/synthesis_v13_checks.py) implement bounded numerical, identity, source and feedback gates. [NMA preflight](../scripts/synthesis_v13_nma_preflight.py) checks declared overlap/dependence, restricted-count bounds and replay readiness. It does not fit the model or verify all underlying participants.
- The [audit packet](SYNTHESIS-v1.3-AUDIT-PACKET.md) and [reporting contract](SYNTHESIS-REPORTING-v0.1.md) describe evidence accounting. File/schema consistency is not scientific authentication or independent adjudication.

## Evaluation and public descriptions

Independent prospective accuracy remains unestablished. Follow the [blinded validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md), which is a proposal, not an executed study. Freeze paper/trial families, source versions, baseline and revised prompts, model/tools, permissions and equal review budgets before testing. Keep examples used to design this revision, including the worked examples and their linked families, outside the untouched test split.

Measure missed errors, actionable-flag precision, false alerts, abstentions, retrieval/evidence-location coverage, completion and reviewer time. Retain unflagged claims and source-limited cases. Independent assessment must be real, not inferred from a second AI answer. Report uncertainty and family clustering. Do not infer prevalence or performance from selected correction notices or positive correspondence.

Describe this as the **current experimental public version**. Any historical publication count needs a dated, deduplicated register that distinguishes unique papers, individual issues, author-confirmed points and verified published corrections. This guide asserts no such count. The repository's MIT licence applies to its software and documentation; linked third-party sources retain their own licences.

## Static-versus-dynamic disclosure

| Fixed guidance | Source-derived or actually performed work |
|---|---|
| Six core checks, worksheet fields, example selection and decision vocabulary | Exact document identities, source versions, count passages and extracted values |
| Formula definitions and proposed evaluation design | Executed arithmetic with saved inputs/output; no underlying model replay implied |
| Review templates and optional prompt instructions | Completed reviews, detections, accuracy and impact require separately documented evidence |

The worked examples are public teaching material. Real correspondence, completed private ledgers, protected research files and sealed evaluation keys must stay out of public artifacts.
