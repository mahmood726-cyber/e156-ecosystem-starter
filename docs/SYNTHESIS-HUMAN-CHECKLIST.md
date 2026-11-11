# Synthesis — human review checklist (v1.3 companion)

**Start here if you are an author, reviewer or editor.** Use this current experimental checklist with a manuscript and its source documents. No code or AI is required. **Updated 10 November 2026.** A completed checklist does not certify a paper or establish detection accuracy. The [start page](SYNTHESIS-START.md) explains the manual, optional AI and local capture routes.

**Before starting:** Confirm that you are permitted to access and process each source. Respect publisher terms, requests not to contact authors and any research-ethics requirements. Do not upload restricted manuscripts or personal data into external AI systems without permission.

## Start with six core checks

For each claim record **Pass / Review needed / Insufficient evidence / N/A** and a source locator. **Pass** applies only to the stated check and material reviewed. **Review needed** is not confirmation of an error. Give a reason for **N/A**. Missing or inaccessible evidence is **Insufficient evidence**, never N/A or Pass.

| Core | What to do | Result and evidence |
|---|---|---|
| 1. Find the claim | Check its exact wording and location in the correct version, including corrections. Inspect uncertain extracted symbols and table alignment. | |
| 2. Match the source | Find the supporting passage or data. Match the population, comparison, outcome, timepoint and units. | |
| 3. Establish the denominator | Identify who or what was counted, exclusions, missingness and analysis population. Use the [participant worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md) for count comparisons. | |
| 4. Check the calculation | Establish the model, effect measure and precision first. Save inputs, formula and actual working. If code runs, save its versions, command and raw output. | |
| 5. Try to explain the mismatch | Test rounding, different populations, methods, coding, versions and footnotes against the source. Leave an untestable explanation unresolved. | |
| 6. Record and recheck | Keep matching claims and abstentions as well as concerns. Separate labels, numbers, analyses and impact. After a revision, complete the sweep below. | |

Record the sections and claims reviewed, missing materials and remaining checks. For long papers use fixed section batches and stable claim IDs. Do not describe a partial review as complete.

**Next:** Use the relevant detailed checks below, the [worked public examples](SYNTHESIS-WORKED-EXAMPLES.md), or the [optional AI prompt](SYNTHESIS-COPY-PASTE-AI-PROMPT.md). The [methods guide](SYNTHESIS-METHODS.md) explains the evidence labels and software limits.

## Sweep after revisions and before submission

Repeat after changes to data, populations, models, units, labels, tables, numbering or wording, including editorial and proof changes.

1. Log what changed and why, with the previous and revised document/file versions.
2. Locate every affected occurrence in the abstract, text, tables, figures, legends, supplements, source-data sheets and code. Record inaccessible and unchecked locations.
3. Recheck the meaning as well as the number. Look for copied adjacent columns, reversed groups, stale SD/SE headings, units, reference numbers and table/figure links. One heading may not describe every data block.
4. Recalculate affected results from the authorised source. Distinguish a presentation edit from a change to inputs, analysis or interpretation. Do not infer unchanged conclusions without checking the affected claims.
5. Check a nearby unaffected result to detect unintended changes. Review the rendered final files where available.
6. Record each location as checked, intentionally different with a reason, or unresolved. A blocked location keeps that part of the sweep incomplete.

Copy one row per affected occurrence. Keep this log private when it concerns a manuscript.

| Change ID / claim ID | Old and new file/version | Location | Required update or reason for difference | Recheck and saved working | Checked / unresolved | Reviewer/date |
|---|---|---|---|---|---|---|
| | | | | | | |

## Detailed checks when relevant

Use the same four results as the core. Apply the relevant study-type checks even when simple arithmetic agrees.

| Item | Human-readable question | Result | Evidence or notes |
|---|---|---|---|
| 1 | Is this the correct current version of the paper, including corrections? | | |
| 2 | Are the abstract's numbers and conclusions consistent with the full text? | | |
| 3 | Do tables, figures, text and supplementary files agree on results and recommendations, including eligibility, age boundaries and logical qualifiers such as “not”, “and” and “or”? | | |
| 4 | Do reported counts and percentages agree with the stated denominators? | | |
| 5 | Are confidence intervals ordered correctly and reported on the intended scale? | | |
| 6 | Are units, labels, figure axes and treatment directions consistent? | | |
| 7 | Do references actually support the specific claims attributed to them? | | |
| 8 | Do the population, intervention, comparator and endpoint, including its primary or secondary status, match the cited source? | | |
| 9 | Are follow-up windows, analysis populations and endpoint definitions consistent across documents? | | |
| 10 | Does the reported analysis match the protocol, registration and statistical analysis plan, or are changes explained? | | |
| 11 | Are effect measure, estimand, adjustment and model identified before comparing estimates? | | |
| 12 | Are missing data, censoring, multiplicity and variance methods explained and appropriate to the claim? | | |
| 13 | If checking a P value, have the test identity, null, sidedness, scale and input precision been established? | | |
| 14 | Have rounding and legitimate statistical-method differences been checked against the source? | | |
| 15 | For a review/meta-analysis, are included studies, outcomes and extracted values traceable to their sources? | | |
| 16 | Have duplicate trial families, overlapping participants and shared controls been identified and handled? | | |
| 17 | For network meta-analysis, are treatment nodes, transitivity and consistency assumptions examined? | | |
| 18 | For IPD or reconstructed survival analyses, are data provenance, censoring and reconstruction limitations documented? | | |
| 19 | If code/data are available, do their definitions and outputs correspond to the reported analysis? | | |
| 20 | Have I actively sought the strongest benign explanation and recorded what would refute my concern? | | |
| 21 | Is the evidence sufficient for this specific assessment? Record Insufficient evidence when it is not. | | |
| 22 | Have I recorded both flagged and unflagged items, rather than reporting only apparent problems? | | |
| 23 | Have I verified that each quoted phrase actually occurs in this exact paper and section, including the rendered table or figure where extraction is uncertain? | | |
| 24 | Before linking a coefficient to an HR/OR, have I checked predictor coding, reference category, contrast size and units? | | |
| 25 | Have I distinguished observed counts, respondent-specific denominators, exposure-adjusted rates, weighted estimates and marginal standardisation? | | |
| 26 | For a numerical claim, are the inputs, formula and actual working saved; if code was run, are its script, versions and raw output saved? | | |
| 27 | If there is a reply, have I compared it with the original question and rechecked its explanation and counterevidence for each separate point? | | |

## Review record (copy once for each possible discrepancy)

- **Paper and version / DOI:**
- **Source permission and access route:**
- **Exact claim location and wording:**
- **Original enquiry:** clarification request / error allegation (record each point separately)
- **Comparison source, version and location:**
- **What seems inconsistent (without assuming an error):**
- **Issue class, separately for each point:** label/presentation / numerical value / analysis or code / citation / methodological discussion
- **Impact:** display only / numerical result / interpretation or conclusion / undetermined (record supporting evidence, not an assumption)
- **Recalculation or methodological check, with assumptions:**
- **Saved inputs and working / script and raw output (if executed):**
- **Are the estimates genuinely comparable?** Yes / No / Unclear
- **Strongest benign explanation and how checked:**
- **Reply, source recheck and counterevidence (if any):**
- **Point outcome:** concern persists / resolved enquiry / false-positive allegation / version-limited / methodological discussion / unresolved
- **Source-support:** SUPPORTED / CONTRADICTED / OVERGENERALIZED / UNSUPPORTED_CITATION / SOURCE_UNAVAILABLE / NOT_ENOUGH_INFO
- **Evidence maturity:** SCREENED / SOURCE_BACKED / REPRODUCED / INDEPENDENTLY_ADJUDICATED
- **Disposition:** FLAG / RECONCILED / DISCUSSION / HOLD / NO_FLAG
- **Severity (if justified):** S1 / S2 / S3 / S4 / S5 (not a confidence score)
- **Reviewer and date:**
- **Correspondence stage, if relevant:** not sent / acknowledged / author-confirmed point / disputed / correction requested / verified published correction / resolved enquiry / unresolved
- **Follow-up:** None / independent review / seek clarification subject to contact permissions

**Decision rule:** A mismatch is not automatically an error. If sources, versions, endpoint identity, estimator or precision are insufficient, record **HOLD / NOT_ENOUGH_INFO** or **NOT_COMPARABLE** rather than alleging a mistake. An email acknowledgement is not author confirmation; author confirmation is not a published correction. Preserve a record of negative and abstained checks. Do not contact authors automatically.

**Handling a reply:** Disagreement alone does not prove the enquiry wrong, and acknowledgement of one typo does not validate all its other points. A resolved clarification question is not automatically a false-positive error allegation. See the [response-review procedure](SYNTHESIS-RESPONSE-REVIEW.md) for the evidence needed to close, retain or withdraw a concern.

**Technical detail and limits:** [Methods guide](SYNTHESIS-METHODS.md) · [Synthesis overview](SYNTHESIS-v1.3-CANDIDATE.md) · [Blinded validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md) · [Audit packet](SYNTHESIS-v1.3-AUDIT-PACKET.md). The v1.3 candidate remains experimental and has not undergone independent prospective real-paper accuracy validation.
