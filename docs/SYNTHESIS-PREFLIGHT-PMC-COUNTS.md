# Source-bound participant counts from PMC

For new comparisons, use the [normal-intake evidence checks](SYNTHESIS-INTAKE-EVIDENCE.md) to bind each count's population/denominator definition and full analysis identity. Legacy `participant_count_check` results below retain their arithmetic/trace status but now have `decision_status: HOLD`; attested labels alone cannot clear a claim. The [start page](SYNTHESIS-START.md) includes a runnable synthetic example.

Use the normal Synthesis preflight with `document.pmcid`, a bare DOI in `document.identifier` and the exact edition in `document.version`. `--pmc-live` allows retrieval from PMC EFetch. `--pmc-xml PATH` replays a local JATS response without network access. The CLI saves validated XML bytes under `pmc-snapshots/<sha256>.xml` inside the receipt directory. Keep that directory with the receipt. Live receipts also record the final retrieval URL and UTC timestamp. A later response for the same PMCID version can have different bytes, so use the archived snapshot to reproduce a comparison.

The archive requires a single article. Responses containing nested articles, separately restricted material or contradictory rights declarations are held before any XML is saved.

Run capture once to locate tables and obtain the digest. Then add an optional `participant_count_check` object to the relevant entry in `claims` and replay the same XML. Counts can bind an integer cell or a reviewer-selected, uniquely located integer token in supported text. Matching printed arithmetic does not establish that the source counts are correct. Every count finding records `count_validity: NOT_INDEPENDENTLY_VERIFIED`.

| Field | Meaning |
| --- | --- |
| `kind` | `RESTRICTED` for a strict subset or `UNIQUE_ARMS` for reported total versus distinct disjoint arms. |
| `snapshot_sha256` | The digest from `pmc_evidence.source.snapshot_sha256`. |
| `context_quote` | A verbatim excerpt of up to 500 characters from a source paragraph or table. The excerpt must resolve to one location. |
| `scope_verified` | The reviewer's attestation that the compared counts use the same counting basis, outcome and timepoint. For a restriction, verify the strict-subset relationship. For arms, verify complete coverage, disjoint populations and any shared-control identity. |
| `outcome`, `timepoint`, `basis` | Reviewer-supplied analysis labels retained in the receipt. |
| `primary`, `restricted` | Count references for `RESTRICTED`. An upper bound alone cannot clear a restricted tally. |
| `exclusion_counts` | One to 500 source-bound exclusion count references for exact restricted accounting. |
| `exclusions_disjoint_verified`, `exclusions_exhaustive_verified` | Both must be `true` before calculating parent minus exclusions. These are reviewer attestations, not automatically authenticated facts. |
| `reported`, `arms` | The reported total count reference and complete arm list for `UNIQUE_ARMS`. Each entry has `trial`, `cohort`, `arm` and a `count` reference. Mark every repeated occurrence of a verified shared control with `shared_control: true`. |

A cell reference has `table`, `row` and `cell` integer fields. The positions are one-based in JATS order. Count header rows, and use the physical cell position within its row even when earlier cells span columns. The selected cell must contain one plain integer and may use comma grouping. Merged cells, annotations, ranges, percentages and unsupported table markup require review. A table held for unsupported markup records the first offending element and its row and cell when applicable.

Alternatively use `{"quote": "Final analysis included 19 participants.", "count_text": "19"}`. This is an illustrative synthetic reference, not a real-paper finding. The normal intake automatically requests quotes from count references, exclusion entries, arms, correction pairs and correction-sweep occurrences. Quotes are limited to 500 characters each and 1,000 per captured document. Supported locations include abstract paragraphs, body paragraphs (including caption paragraphs), section titles, table captions/footnotes and structured unmerged cells. Each quote must occur once at one indexed location, and the selected nonnegative integer must be a complete token occurring once inside it. When the same excerpt occurs in several cells, supply the optional exact `locator` from `quote_bindings`, for example `body table-wrap 1 row 2 cell 2`. Missing or incorrect disambiguation holds. The receipt preserves the quote, locator and offsets in the indexed text. It does not select counts or infer their scientific roles.

This permits a reviewer to bind the integer in a compound count/percentage cell while rejecting the percentage itself. Word numbers, decimal counts, ranges, merged cells, ambiguous excerpts, unsupported semantic styling and uninspected external graphics remain HOLD. Different excerpts of the same physical token cannot be reused as independent contributions; distinct count tokens in one paragraph can be mapped separately. Offsets refer to the captured text representation, not PDF coordinates.

For `RESTRICTED`, the necessary upper-bound comparison is retained as `comparison_status`. A count below its parent remains `HOLD` with `accounting_status: HOLD` until the source-bound, disjoint and exhaustive exclusion ledger is supplied. With that ledger, the receipt saves expected restricted count, difference, formula and exclusion bindings. A wrong count can yield `REVIEW_CANDIDATE` even while below its parent. An excess above a verified parent already violates a strict-subset bound and can yield a candidate without an exclusion ledger. Rematched, differently defined or unknown populations must not be attested as strict subsets. Neither outcome authenticates participant records.

The receipt reports `REVIEW_CANDIDATE` for an inconsistency, `NO_FLAG` for a passed comparison, or `HOLD` for inadequate evidence. It records the source digest and the cells used in the calculation. The feature evaluates reviewer-selected cells and mappings. It does not choose the cells, establish the scientific meaning of a denominator, infer which count is wrong, or promote an allegation. A candidate or unresolved check holds a decisive disposition for that claim pending review.

## Corrections and supplements

Supply verified correction JATS with `--pmc-linked-xml PATH`, which can be repeated. The correction must carry a typed backlink to the article. If the notice declares an article type, it must be `correction`. When the article gives typed forward links, the notice must match one. Versioned links take precedence for their target PMCID. `--pmc-live --pmc-follow-corrections` can also follow direct typed PMCID links using EFetch. Other links and missing or ambiguous records are listed for manual review. Archive older article XML separately from the current edition and the notice. [JATS article types](https://jats.nlm.nih.gov/archiving/tag-library/1.3/attribute/article-type.html)

To associate a notice with a specific comparison, add `correction` to the count check with its `pmcid`, `snapshot_sha256`, `context_quote`, and reviewer attestation `same_claim_verified: true`. Add `replacement` with a supported cell or quoted-token reference. A `SOURCE_BOUND` correction preserves the matching excerpt or cell. A requested correction holds a comparison that would otherwise yield `NO_FLAG` on the original counts alone. The receipt retains the arithmetic separately for review.

Use `kind: "PUBLISHED_CORRECTION"` when the task is tracing a known count replacement. This mode requires the notice's context quote, its `correction.replacement` count reference, and one previous count reference. Set `original` for a count in the separately archived article snapshot, or `correction.previous` when the notice itself reproduces the original. Integer-cell and quoted-token references are supported on both sides, including distinct old/new tokens in one notice paragraph. The receipt reports `MATCH` when the selected numbers agree, `PUBLISHED_CORRECTION` when they differ, and `HOLD` when the exact pair cannot be verified. Trace results should be scored separately from error detection.

The historical trace is separate from `revision_sweep`. Supply `current_occurrences` with one to 500 current-article count references and `unchecked_locations` with an explicit list of uninspected dependencies (empty only when none remain in the agreed scope). Each mapped occurrence is compared with the published replacement. A stale abstract, prose or table token produces sweep `REVIEW_CANDIDATE` even when the initially selected table matches. Missing, ambiguous or unchecked locations hold the sweep when no definite difference is found. `MATCH` covers only the mapped occurrences: coverage is always `REVIEWER_SELECTED_ONLY`, never an automatically complete revision audit. External figure pixels and source records are not inspected by this feature. Source tally, arithmetic and correction propagation remain separate outcomes in JSON and the normal intake report.

The [development review](SYNTHESIS-COUNT-EVIDENCE-REVIEW.md) explains the public-source failures motivating these changes. Its cases are now development material; no new detection-accuracy gain has been measured.

Inline supplementary tables in the article body use the same snapshot and cell references. Supplements with unresolved tables or external attachments remain in manual review. The receipt distinguishes captured from unresolved tables. [PMC archive versioning and access](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)

## Public-source evaluation summary

An independent AI evaluator froze 12 PMC cases before examining preflight results. The purposive challenge included repeated articles and notices. It excluded identifiers present in the 1,000-notice development register and four earlier public manifests. The evaluator supplied the target cells and adjudicated scope. Preflight computed the findings and cell bindings from the archived XML.

| Case group | Baseline | Frozen candidate | Same-case diagnostic after the trace-status fix |
| --- | --- | --- | --- |
| Two valid analytical controls | No count finding | Both held for review | Same |
| Four analytical abstention controls | No count finding | All four held | Same |
| Two documented historical count changes | No trace finding | One exact trace and one hold | Same |
| Two agreeing count pairs | No trace finding | Both pairs extracted correctly, with the correction label | Both reported as `MATCH` |
| Two incomplete replacement pairs | No trace finding | One hold and one notice-only result labeled as a correction | Both held |

The baseline was `396c7ab0279b3d0af806c6f60c4452f8fe72ed0c`. The frozen implementation used tree `355f0d2ba46398c58eb92302adf0312beda16a6a`. The initial run was blinded. The later diagnostic rerun reused the opened cases to verify the fix. Source markup sent both valid analytical comparisons to review. The analytical suite had zero verified positive errors, so detection sensitivity and false-positive rates remain unmeasured. The correction tests measured traceability with supplied notices. Live PMC intake separately retrieved and archived a fresh article and followed its direct typed correction link.
