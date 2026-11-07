# Synthesis — three worked public examples

[Six core checks](SYNTHESIS-HUMAN-CHECKLIST.md#start-with-six-core-checks) · [Participant worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md) · [Methods guide](SYNTHESIS-METHODS.md)

**Teaching examples checked 6 November 2026.** These are selected public-source walkthroughs, not an accuracy benchmark or new automated catches. All three source records declare [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The summaries below are paraphrases with added review steps and arithmetic. No private correspondence or protected evaluation labels are used. These papers and linked families are development examples and must not enter an untouched test split.

## 1. A documented correction in a restricted sensitivity analysis

**Source.** Ishikawa and colleagues' [published correction](https://doi.org/10.1007/s00737-026-01767-2), PMCID PMC13585883.1, links to original DOI [10.1007/s00737-026-01720-3](https://doi.org/10.1007/s00737-026-01720-3). Locate the previous and corrected versions of the Results paragraph describing the sixth sensitivity analysis, restricted to women with anxiety or sleep disorders.

| Worksheet entry | Verified from the notice |
|---|---|
| Outcome / counted unit | Miscarriage / matched controls as reported |
| Previous count | 76,242 controls |
| Replacement count | 7,624 controls |
| Cases in that comparison | 2,564 in both passages |
| Relationship | Published replacement for the same claim; participant-level matching was not reproduced |
| Working | 76,242 − 7,624 = 68,618 |

**Decision.** The notice establishes a historical correction. Record **VERSION_LIMITED / known published correction**, not a new current-paper error. The subtraction describes the printed change, not an independently verified cohort total. A restricted-count upper bound alone would miss the old count because it is below even the originally printed primary control total of 132,317. Do not assume that rematched controls form a literal subset.

**Revision sweep.** Check the corrected Results passage, abstract totals, Table 4 and related supplements. The notice also describes other numerical amendments, which require separate claim records. Do not mark uninspected files checked.

## 2. A count difference explained by the analysis population

**Source.** Coelho and colleagues' [PRAMEV trial](https://doi.org/10.1001/jamanetworkopen.2026.26884), PMCID PMC13463168.1. Compare the weight-change rows in Table 3 and its missing-data/analysis-population explanation, with the Statistical Analysis section.

| Worksheet entry | Verified from the article |
|---|---|
| Outcome / timepoint / arm | Weight change / week 20 / PRAMEV |
| ITT count and basis | 97, with missing outcomes handled by multiple imputation |
| Secondary per-protocol count | 59 completers |
| Working | 97 − 59 = 38; 59 <= 97 |
| Explanation | The analyses have different source-defined populations |

**Decision.** **Pass / NO_FLAG for the scoped count-bound check.** The different denominators are explained by ITT versus completer analysis. The difference of 38 is not an independently audited exclusion list. Do not compare the two effect estimates as if they used identical populations or infer that either entire analysis is verified. This is a secondary per-protocol analysis, distinct from the paper's missing-not-at-random sensitivity analyses.

**Software limit.** The counts sit inside compound effect-summary cells. The [quoted-token interface](SYNTHESIS-PREFLIGHT-PMC-COUNTS.md) can bind a reviewer-selected integer when its location and markup are unambiguous; unsupported or incomplete mappings still HOLD. Extracting these two numbers does not provide the exclusion ledger required for an automated accounting pass. This walkthrough remains a manual bound comparison, not a measured automated clearance.

## 3. A notice establishes a replacement but not independent reproduction

**Source.** Aqeel and colleagues' [exercise-timing review correction](https://doi.org/10.3390/nu12051263), PMCID PMC7281960.1, links to original DOI [10.3390/nu12010221](https://doi.org/10.3390/nu12010221). Locate the Abstract and Discussion correction paragraphs.

| Worksheet entry | Verified from the notice |
|---|---|
| Previous / revised participants | 352 / 332 |
| Previous / revised studies | 20 / 17 |
| Working | 352 − 332 = 20 participants; 20 − 17 = 3 studies |
| Additional evidence required | Original and revised study-level extraction, eligible unique participants and overlap accounting |

**Decision.** The published replacements are source-backed historical facts. **Insufficient evidence / HOLD for independently reproducing the participant total from this notice alone.** Subtracting two printed totals does not establish how excluded studies contributed or whether cohorts overlap. Do not divide the participant difference by the study difference to invent study-level counts. Reproduction requires the source-backed trial/cohort/arm ledger.

**Revision sweep.** Check the revised inclusion flow, study table, abstract, Results and Discussion once available. Keep the notice trace and the unperformed independent recount as separate outcomes.

## Re-run the displayed arithmetic

The following Python 3 snippet uses the source-derived printed values above. It performs only the displayed arithmetic, not study extraction, eligibility review or model reproduction.

```python
print("EX1 printed count change:", 76242 - 7624)
print("EX2 population difference:", 97 - 59)
print("EX2 restricted bound:", 59 <= 97)
print("EX3 printed participant change:", 352 - 332)
print("EX3 printed study change:", 20 - 17)
```

Actual output from Python 3 on 6 November 2026 follows.

```text
EX1 printed count change: 68618
EX2 population difference: 38
EX2 restricted bound: True
EX3 printed participant change: 20
EX3 printed study change: 3
```

## Source versions and scope

The public NLM XML snapshots below were retrieved and their identities, relevant passages, rights and arithmetic checked on 6 November 2026. SHA-256 binds the inspected bytes, not the scientific truth. XML body paragraph positions count descendant `p` elements in source order. In Table 3, row positions include header rows and cell positions are physical cells.

| Example | NLM versioned XML and inspected locator | SHA-256 |
|---|---|---|
| 1 | [PMC13585883.1](https://pmc-oa-opendata.s3.amazonaws.com/PMC13585883.1/PMC13585883.1.xml), body paragraphs 9 and 11 | `7ef7916992d2a251f956fe26854635d92135b6c241c2d243a845ea585786fedb` |
| 2 | [PMC13463168.1](https://pmc-oa-opendata.s3.amazonaws.com/PMC13463168.1/PMC13463168.1.xml), Table 3 rows 4 and 9, cell 2; body paragraphs 26 and 45 | `02c181d486876cc268eb161150cebb456ef1c58bdffc69586b93b50a9da2bb20` |
| 3 | [PMC7281960.1](https://pmc-oa-opendata.s3.amazonaws.com/PMC7281960.1/PMC7281960.1.xml), body paragraphs 2 and 15 | `98611a88336ff64a95c37c59342e57dd81be73e56649eb6654f43850b510627c` |

Only those public documents and scoped claims were checked for these walkthroughs. Underlying participant data, complete source-study recounts, supplements and statistical models were not independently reproduced. The worked outcomes are manual explanations, not measured performance of the revised prompt or optional software.
