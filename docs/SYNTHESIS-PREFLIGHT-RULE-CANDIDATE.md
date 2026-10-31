# RULE_CANDIDATE — first-pass source verification

**Date:** 31 October 2026
**Owner for acceptance:** existing Synthesis Ten-Journal Scientific Oversight rulebook steward, with Engineering Oversight for technical implementation
**Status:** PROPOSED, not incorporated into canonical rulebook v1.2
**Source:** Synthesis 46-case acknowledged-issue register; separate author-explanation controls; methods proposal v1.1 (31 October)

## Observed failure mode and desired change

Different workstreams perform broadly similar source and arithmetic checks with varying first-pass presentation. A copy-and-paste prompt alone cannot enforce source provenance, abstention, case denominators or independent review and may overinterpret model-based statistics. A recurring false-positive pattern is comparing *unmatched estimators* (Kaplan–Meier versus crude proportions; adjusted/stratified/permutation versus naive calculations) or overlooking a dated protocol amendment.

## Minimal amendment proposed to existing Rules 11–21, 34–40

> For new paper/AI/guideline audit candidates, provide the user-invoked Synthesis Preflight v1.1 prompt and structured evidence receipt as an optional common intake. Enumerate all claim units; retain every positive, negative and unavailable result. A separate source-grounded refutation is required before high-confidence material flags. Delegate applicable numerical checks to existing deterministic Synthesis/E156 tools. An inaccessible source is an abstention, not a contradiction. Exact prompt/model/tool versions and source accession records must be logged. This intake neither changes external contact thresholds nor serves as independent validation or a human sign-off.

### Negative-control counterexamples

- Prespecified modification of endpoint before unblinding: do not call post-hoc manipulation.
- Published Kaplan–Meier rate versus crude event proportion: non-comparable estimators.
- Modified ITT with SAP-specified complete-case handling: do not demand an invented imputation.
- Raw OR reconstructed from a sensitivity assumption versus primary permutation ITT: non-comparable.
- Corrected proof or already-corrected published article: do not count current published error.
- Paper-time exact code/config unavailable: record verification limitation, not confirmed coding bug.

## Promotion requirements

1. Append code-reviewed candidate to rulebook only after steward acceptance; preserve version history.
2. Exact-head full repository CI and relevant statistical/parity tests; independent human review where required. A passing local test is insufficient to merge.
3. Synthetic positive/negative regression fixtures, 46 known cases as selected-regression *coverage* only; do **not** report prospective sensitivity/specificity.
4. No modification to frozen prospective sampling, Simo 36/12 methods, HARNESS pilot, scheduled prompts, patient data, recipient contact or protected e156 records.
5. Publish a future separate evaluation protocol for **unseen** claims and independent masked adjudication of flags and nonflags before any performance claim.

**Steward disposition requested:** ACCEPTED / MERGED_INTO_EXISTING / DEFERRED / REJECTED, with short rationale, dated by steward. No duplicate numbered rules proposed.