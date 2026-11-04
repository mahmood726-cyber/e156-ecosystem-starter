# Participant counts from PMC tables

Use the normal Synthesis preflight with `document.pmcid`, a bare DOI in `document.identifier` and the exact edition in `document.version`. `--pmc-live` allows retrieval from PMC EFetch. `--pmc-xml PATH` replays a local JATS response without network access. The CLI saves validated XML bytes under `pmc-snapshots/<sha256>.xml` inside the receipt directory. Keep that directory with the receipt. Live receipts also record the final retrieval URL and UTC timestamp. A later response for the same PMCID version can have different bytes, so use the archived snapshot to reproduce a comparison.

Run capture once to locate tables and obtain the digest. Then add an optional `participant_count_check` object to the relevant entry in `claims` and replay the same XML. The object has these fields.

| Field | Meaning |
| --- | --- |
| `kind` | `RESTRICTED` for a strict subset or `UNIQUE_ARMS` for reported total versus distinct disjoint arms. |
| `snapshot_sha256` | The digest from `pmc_evidence.source.snapshot_sha256`. |
| `context_quote` | A verbatim excerpt of up to 500 characters from a source paragraph or table. The excerpt must resolve to one location. |
| `scope_verified` | The reviewer's attestation that the compared cells use the same participant denominator, outcome and timepoint. For a restriction, verify that the second analysis only removes participants or studies. For arms, verify complete coverage, disjoint populations and any shared-control identity. |
| `outcome`, `timepoint`, `basis` | Reviewer-supplied analysis labels retained in the receipt. |
| `primary`, `restricted` | Cell references for `RESTRICTED`. |
| `reported`, `arms` | The reported total cell and complete arm list for `UNIQUE_ARMS`. Each entry has `trial`, `cohort`, `arm` and a `count` cell reference. Mark every repeated occurrence of a verified shared control with `shared_control: true`. |

A cell reference has `table`, `row` and `cell` integer fields. The positions are one-based in JATS order. Count header rows, and use the physical cell position within its row even when earlier cells span columns. The selected cell must contain one plain integer and may use comma grouping. Merged cells, annotations, ranges, percentages and unsupported table markup require review. A table held for unsupported markup records the first offending element and its row and cell when applicable.

The receipt reports `REVIEW_CANDIDATE` for an inconsistency, `NO_FLAG` for a passed comparison, or `HOLD` for inadequate evidence. It records the source digest and the cells used in the calculation. The feature evaluates reviewer-selected cells and mappings. It does not choose the cells, establish the scientific meaning of a denominator, infer which count is wrong, or promote an allegation. A candidate or unresolved check holds a decisive disposition for that claim pending review.

## Corrections and supplements

Supply verified correction JATS with `--pmc-linked-xml PATH`, which can be repeated. The correction must carry a typed backlink to the article. `--pmc-live --pmc-follow-corrections` can also follow direct typed PMCID links using EFetch. Other links and missing or ambiguous records are listed for manual review. Archive older article XML separately from the current edition and the notice.

To associate a notice with a specific comparison, add `correction` to the count check with its `pmcid`, `snapshot_sha256`, `context_quote`, and reviewer attestation `same_claim_verified: true`. Add `replacement` with a cell reference when the notice gives the replacement in a table. A `SOURCE_BOUND` correction preserves the matching excerpt or cell. It leaves the original comparison and its review disposition intact.

Use `kind: "PUBLISHED_CORRECTION"` when the task is tracing a known correction without running a comparison. This mode uses the notice's context quote. Include `original` for a cell in the separately archived original article, or `correction.previous` when the notice itself reproduces the original cell. The receipt labels which source supplied the old count. Trace results should be scored separately from error detection.

Inline supplementary tables in the article body use the same snapshot and cell references. The receipt retains links and manual-review reasons for external attachments, whose edition and reuse rights require separate verification. [PMC archive versioning and access](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)
