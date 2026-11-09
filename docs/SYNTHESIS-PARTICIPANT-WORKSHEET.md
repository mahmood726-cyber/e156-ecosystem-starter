# Synthesis — participant-count worksheet

[Six core checks](SYNTHESIS-HUMAN-CHECKLIST.md#start-with-six-core-checks) · [Worked examples](SYNTHESIS-WORKED-EXAMPLES.md) · [AI prompt](SYNTHESIS-COPY-PASTE-AI-PROMPT.md)

**Current experimental worksheet, 6 November 2026.** Complete one per count comparison using authorised sources. Blank cells mean unfinished work. Keep completed manuscript worksheets private. Use aggregate cohort labels, never patient identifiers.

## 1. Identify each count before doing arithmetic

Copy a row for every relevant count. Read prose, table headings, footnotes, figures and supplements. A number beside an effect estimate or inside a heading still needs a source locator.

| Field | Primary or parent analysis | Restricted or comparison analysis |
|---|---|---|
| Claim ID and exact count as printed | | |
| Paper/trial/cohort and arm | | |
| Document version, source URL/file and page/table/row/column | | |
| Counted unit (people, pregnancies, events, observations, person-time, weighted total) | | |
| Outcome and follow-up/timepoint | | |
| Analysis population (randomised, treated, ITT, per-protocol, respondents, eligible risk set) | | |
| Observed, imputed or weighted basis | | |
| Eligibility and restriction definition, with source | | |
| Missingness, exclusions and losses, with source | | |
| Verified count and extraction uncertainty | | |

Do not treat an outcome-specific denominator as the headline sample size. Do not equate events with people or weighted estimates with observed counts. A respondent-only proportion, survival estimate or imputed ITT result can legitimately differ from a crude complete-case fraction.

## 2. Establish the relationship

Select and justify one relationship with source evidence.

- **Strict subset** with unchanged counted unit and a verified common parent population.
- **Rematched sample** whose controls or other units may have changed.
- **Different risk set, outcome, timepoint or counting basis** requiring a different comparison.
- **Overlapping groups** that cannot simply be added.
- **Unknown**, requiring Insufficient evidence / HOLD.

The same analysis label does not establish comparability. For restricted sensitivity analyses, record the exact restriction and whether only removal occurred. Do not assume rematching preserves participant identities or a fixed control-to-case ratio.

## 3. Reconcile a verified strict subset

Use subtraction only when all exclusions are exhaustive, mutually exclusive and expressed on the same basis as the parent count. Otherwise record the missing mapping and hold the exact accounting.

| Source-backed quantity | Count | Exact source/version/locator |
|---|---|---|
| Parent population | | |
| Excluded category 1 | | |
| Excluded category 2 (copy more rows as needed) | | |
| Verified disjoint exclusion total | | |
| Expected restricted count = parent minus exclusions | | |
| Reported restricted count | | |
| Difference = reported minus expected | | |

Save the inputs, formula and actual working. Checking **restricted <= parent** is only a necessary bound for a strict subset. A smaller number can still be wrong. An unexplained excess is a review candidate, not evidence of which source value is incorrect. Verify both sides before proposing a replacement.

## 4. For reviews and shared controls

Use a separate row for each source-backed contribution. Keep study reports linked to their underlying trial/cohort family. Verify unique participants, outcome-specific contributions, disjoint arms and any repeated control identity before calculating a total.

| Trial/cohort family | Report/version | Arm | Outcome/timepoint | Count and basis | Overlap/shared-control evidence | Include once / exclude / unresolved |
|---|---|---|---|---|---|---|
| | | | | | | |

A matching trial name or count is insufficient proof that two contributions are identical. An unresolved overlap leaves the unique-participant total unverified. Person-time totals require their own accounting.

## 5. For a published correction

- Original article identifier/version and claim location
- Notice identifier/version and verified link to that article
- Previous count and its exact source location, including when reproduced in the notice
- Replacement count and its exact source location
- Counting basis or analysis changes mentioned by the notice
- Current article/supplement locations checked, plus any unavailable files
- What was independently recalculated and what remains notice-reported

Keep historical corrected errors separate from current unresolved concerns. A notice can establish a published replacement without independently proving the underlying participant tally or analysis. The optional [PMC count software](SYNTHESIS-PREFLIGHT-PMC-COUNTS.md) currently requires reviewer-selected plain integer cells for decisive comparisons. Prose, merged headers and compound cells can require manual review. This worksheet does not extend those extraction capabilities.

## 6. Close the scoped check

Record **Pass / Review needed / Insufficient evidence / N/A with reason**, the strongest benign explanation and source check, saved working, reviewer/date and any unresolved requirements. Separate presentation, numerical, analysis/code and citation issues. Record impact as demonstrated or undetermined.

A Pass covers this comparison only. Include the result in the claim ledger and the [revision sweep](SYNTHESIS-HUMAN-CHECKLIST.md#sweep-after-revisions-and-before-submission) when dependent results change. A worksheet does not authorise contact or certify a manuscript.
