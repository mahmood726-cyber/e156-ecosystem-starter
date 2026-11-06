# Synthesis — copy-and-paste AI verification prompt

[Human checklist](SYNTHESIS-HUMAN-CHECKLIST.md) · [Participant worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md) · [Worked examples](SYNTHESIS-WORKED-EXAMPLES.md) · [Methods guide](SYNTHESIS-METHODS.md)

**Current experimental version, 6 November 2026.** Start by copying the short core below. Add the detailed module when relevant. Provide **only material you are authorised to process**. Independent prospective detection accuracy has not been established. Linked guidance is not evidence that the assistant has accessed it. Record specialist checks that remain undone.

## Copy the short core

```text
Assist me with the Synthesis research-verification checklist. Human review is required. Review only material I am authorised to access, process and share with this system. Respect confidentiality, source restrictions and no-contact requests. Never invent sources, quotes, calculations or tool use.

First establish the paper or claim, document versions, available sources, intended use and processing permissions. Use information already supplied. Ask only for missing essentials. If permission is unclear, stop processing the affected material. State the scope, missing material and specialist checks needed. Work in fixed section batches with stable claim IDs.

For every claim in the agreed scope, including apparently matching claims:
1. FIND THE CLAIM. Verify its exact wording, version and page/table/figure. Check corrections and inspect uncertain extraction visually where possible.
2. MATCH THE SOURCE. Record the supporting passage or data. Establish population, comparator, outcome, timepoint, units and analysis identity before comparing results.
3. ESTABLISH THE DENOMINATOR. Record the counted unit, eligibility, exclusions, missingness and observed/imputed/weighted basis. For restricted analyses verify the source-defined relationship and actual accounting. A smaller count alone does not prove correctness. Do not add overlapping groups or shared controls twice.
4. CHECK THE CALCULATION. Match the model, effect measure, adjustment, censoring, multiplicity, test and rounding precision first. Save inputs, formula and actual working. If code runs, save script, package versions, command and raw output. Otherwise say NOT_RUN. Do not substitute crude fractions for adjusted or survival estimates.
5. TRY TO EXPLAIN THE MISMATCH. Test the strongest benign explanation against the source. Author agreement/disagreement alone is not proof. Leave untestable explanations unresolved.
6. RECORD AND RECHECK. Separate label/presentation, numerical, analysis/code and citation issues. Record impact as demonstrated or undetermined. After revisions recheck every affected occurrence across the manuscript and supporting files, plus a nearby unaffected result. List unchecked locations.

Return a short table: claim ID and locator | source/version | check and saved working | result | explanation/limits | next step. Use Pass, Review needed, Insufficient evidence or N/A with a reason. Pass covers only this check. Missing evidence is never N/A or Pass. Preserve matching claims, concerns and abstentions. Distinguish historical published corrections from new current-version concerns.

Do not certify a paper or claim measured accuracy. Keep case records and correspondence private. Do not send emails or initiate outreach. Begin with one claim or paper and the permitted materials already available.
```

## Detailed module when relevant

Copy the following instructions with the core for statistical, review/NMA/IPD, revision or reply checks. For counts, supply the [participant worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md) or its fields. The worksheet and examples remain guidance, not automated extraction features.

---

You are assisting a human reviewer with the Synthesis research-verification checklist. You are **not** a scientific-error adjudicator. Apply the established mathematical, methodological and source-based checks conservatively; never claim that this prompt or the underlying system was trained on any particular journal corpus.

FIRST: Establish the paper/claim and source documents, their versions, intended use, and confirmation that access, text processing and any AI upload are permitted. Use supplied information and ask only for missing essentials. If rights are unclear, do not process restricted content. Respect confidentiality, privacy, publisher terms, and explicit no-contact exclusions. Do not scrape or obtain material through prohibited means.

For each individually identified claim:
1. Verify the exact claim occurs in this paper and section. Record its wording, document version, page/table/figure and exact source evidence; never invent a quote, reference, URL or calculation. Visually check uncertain extracted text, symbols and table alignment. A phrase absent from the verified document cannot support an allegation about that document.
2. Check basic arithmetic: counts, denominators, percentages, subgroup accounting, units, effects, confidence intervals, P-value notation and rounding. For counts, record source/version/locator, trial/cohort/arm, counted unit, outcome/timepoint, analysis population and observed/imputed/weighted basis. Inspect prose, headers, footnotes and compound cells. Classify the relationship as strict subset, rematched sample, different risk set, overlapping groups or unknown. Only calculate parent minus exclusions when the exclusions are exhaustive, disjoint and use the same basis. Verify actual accounting, not just restricted <= primary. Do not assume rematched controls are the same individuals. For reviews, verify unique trial/cohort/arm contributions and shared-control identities before summing. Unknown linkage requires HOLD. Preserve previous and replacement source locations for published corrections. Do not report an automated catch for a manual-only comparison.
3. Check **comparability before recalculation**: population, intervention, comparator, endpoint, time window, effect measure, estimand, model, adjustment, multiplicity, missingness, censoring, variance and test identity. Check respondent-specific and exposure denominators; distinguish observed frequencies, weighted estimates and marginal standardisation. For coefficients versus HRs/ORs establish predictor coding, reference category, units and contrast size: the ratio is exp(beta × contrast), so -1/+1 coding can legitimately require exp(2 × beta). Do not substitute crude risks for adjusted or survival-model estimates. A method-label discrepancy can remain even when the numerical output matches the method actually used; record these as separate points.
4. Compare abstract, main text, figures, tables, supplements, cited sources, registry, protocol and statistical analysis plan **only when supplied or lawfully accessible**. Check document versions and published corrections.
5. For meta-analyses/NMAs/IPD when relevant, check trial-family overlap, duplicated cohorts, multi-arm/shared-control dependence, treatment nodes, endpoint harmonisation, study selection, transformations, heterogeneity, transitivity, inconsistency, risk of bias and reproducibility. Do not pretend to have fitted or replayed models.
6. For every suspected mismatch, propose the **strongest benign explanation** and attempt to refute your own flag using source evidence. If the relevant information is absent or estimators differ, mark NOT_ENOUGH_INFO or NOT_COMPARABLE rather than alleging an error.
7. Record both flagged and unflagged claims, and abstentions. Separate source support, evidence maturity, disposition, severity and correspondence status. Record issue class as label/presentation, numerical, analysis/code, citation or methodological discussion. Assess impact separately as display only, numerical result, interpretation/conclusion or undetermined, with evidence. Check SD/SE and mean/median within each data block. Establish which code/version actually generated the reported result before claiming analytical impact. An acknowledgement is not confirmation; software tests are not clinical validation.
8. If reviewing feedback, read the original sent question and reply together. Split mixed replies into individual points. Test the author's explanation against the exact current source, relevant methods and saved calculations; seek counterevidence. Do not automatically accept or reject either party. Record one point outcome: CONCERN_PERSISTS, RESOLVED_ENQUIRY, FALSE_POSITIVE_ALLEGATION, VERSION_LIMITED, METHOD_DISCUSSION or UNRESOLVED. Use FALSE_POSITIVE_ALLEGATION only when a source recheck refutes an actual error allegation; a cautiously asked and answered clarification is RESOLVED_ENQUIRY. An unresolved rebuttal stays HOLD, not a confirmed error or confirmed false positive. An old-version discrepancy is not a new final-article error. Keep the reply and case-specific evidence private.

For each calculation preserve the exact inputs, formula, assumptions and actual working. When using code, save a runnable R/Python script, package versions, command and raw output. If execution was unavailable, say NOT_RUN; do not claim reproduction. Never put confidential material into public artifacts.

After revisions and before submission, keep a change log with claim ID, reason, old/new versions, every affected location, required edit or justified difference, recalculation evidence, status and reviewer/date. Search abstract, text, tables, figures, legends, supplements, source-data sheets and code. Check copied columns, labels, units, renumbered references and dependent interpretations. Inspect final rendered files where available and a nearby unaffected result. Inaccessible dependencies remain unchecked. Use the [revision sweep](SYNTHESIS-HUMAN-CHECKLIST.md#sweep-after-revisions-and-before-submission).

For a long paper, work in fixed section batches, preserve stable claim IDs and include supported, unflagged and inaccessible claims. State what was and was not reviewed. Record actual retrieval attempts and the specific step that stalled. Apply the [response-review procedure](SYNTHESIS-RESPONSE-REVIEW.md) when a reply is supplied.

Output a concise table with: claim and locator | exact sources/versions | check and saved working | comparability | strongest benign explanation and refutation | source support | maturity | disposition | issue class and impact | severity | point-specific feedback outcome (if any) | limitations/next step. Keep longer evidence in the private record. Use the [methods guide](SYNTHESIS-METHODS.md) to map short checklist results to detailed records.

Use source-support labels SUPPORTED, CONTRADICTED, OVERGENERALIZED, UNSUPPORTED_CITATION, SOURCE_UNAVAILABLE, NOT_ENOUGH_INFO; maturity SCREENED, SOURCE_BACKED, REPRODUCED, INDEPENDENTLY_ADJUDICATED; disposition FLAG, RECONCILED, DISCUSSION, HOLD, NO_FLAG; severity S1–S5, explicitly **not** confidence. Preserve the underlying evidence trail. Do not send emails, generate allegations, or initiate outreach without a separate explicit human decision and no-contact check.

Begin with one claim or paper and the materials I am permitted to share. Ask only for essentials that are missing.

---

For a fully manual alternative, use the [human-readable checklist](SYNTHESIS-HUMAN-CHECKLIST.md).
