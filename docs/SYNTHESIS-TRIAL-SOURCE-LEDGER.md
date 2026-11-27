# Source-to-cell trial extraction ledger (experimental)

**Development pilot, 20 November 2026.** This is a supervised *crosswalk* of values
printed in a meta-analysis to selected, archived primary-trial passages. It makes
each reviewer-entered extraction checkable by source location and records where
the evidence stops. It does not extract every study automatically, authenticate
a trial's clinical labels, fit a network model, or make a scientific-error allegation.

## What is new and what is reused

| Component | Role |
| --- | --- |
| \`scripts/synthesis_trial_source_ledger.py\` | **New** per-row crosswalk, exact quoted-token offsets, primary trial key/source tier, provenance receipt, aggregate HOLD accounting. |
| \`scripts/synthesis_source_trial_view.py\` | Reused for source SHA-256/quote checks, declared population and endpoint comparability, scoped count/percentage/SD-vs-SE checks, and private two-column HTML. |
| \`scripts/synthesis_v13_nma_preflight.py\` | Reused for **attested** repeated trial-family/cohort effects. It cannot independently establish duplicate patients. |
| \`scripts/synthesis_intake_evidence.py\` | Existing **stronger** PMC-bound COUNT_PERCENT and interval evidence checks; use as the primary evidence route when the source permits it. |
| \`templates/count-recovery/count_recovery_harness.py\` | Existing 14 preconditions for complete, recovered per-arm clinical event cells. Run separately on a fully sourced cell set; this pilot must **not** manufacture missing randomised/analysed denominators to satisfy it. |
| \`scripts/trial-identity-screen.py\` | Existing denominator-pattern screen for published included-studies tables. Signals need confirmation against trial identifiers. |

No third-party tool code is copied. This is an **interface and audit-record
improvement**, not an entirely new meta-analysis algorithm.

## Run on authorised local captures

Python 3.10+, standard library only. Keep sources and results in a private
working directory unless every excerpt is licensed for public redistribution.

Use distinct, new HTML and JSON output filenames; existing files and input/source
aliases are refused. See the shared [publication and retry requirements](SYNTHESIS-SOURCE-TRIAL-PILOT.md#run-offline).
Malformed source tiers or trial-key types retain a per-row HOLD so later rows are
still reported. Percentage bindings must match a complete numeric token at the
selected offset, even when the same percentage occurs elsewhere in a quotation.

~~~sh
python scripts/synthesis_trial_source_ledger.py \
  --packet /private/ledger.json \
  --source-root /private/captures \
  --html-out /private/review.html \
  --json-out /private/ledger-receipt.json

python -m unittest discover -s tests -p 'test_synthesis_source_trial_view.py' -v
~~~

The JSON receipt includes row IDs, statuses, reason, optional calculation,
declared trial key, source tier and each verified capture's **relative path,
SHA-256, source version and locator**, but no raw quotation or embedded image.
The HTML renders the reviewer-selected quotations and page images: **treat it
as private**. Neither output certifies a paper or an individual finding.

## Input contract

The packet contains \`ledger_version: "0.1"\`, a nonempty \`synthesis_id\`, and
\`rows\` containing 1–200 per-outcome extraction records.

Each row requires:

1. Unique \`row_id\`; \`trial_key\`, \`trial_key_type\` (REGISTRY, DOI or
   OTHER_SOURCE_ID), \`trial_key_source_checked: true\`, a
   \`trial_key_binding\` containing \`text\` and \`offset\` into the exact
   *primary* source quote; \`source_tier\` T1/T2/T3. T4 (another synthesis)
   cannot independently confirm original trial data. An NCT identifier is
   syntax-checked only: no registry lookup, registration verification or
   cohort identity authentication occurs.
2. A nested \`case\` in the existing viewer format containing \`published\` and
   \`primary\` archived UTF-8 snapshots (\`path\`, \`sha256\`, \`version\`,
   \`locator\`, \`quote\`), matching rich \`contexts\`, \`comparison\`,
   \`claim_version_status\` and \`refutation\`. An extracted count must remain
   tied to one study population, arm, endpoint and timepoint; shared labels
   alone do not establish these facts.
3. Explicit \`bindings\`: for integer counts/SD-vs-SE, \`published_value\`
   and \`primary_value\`; for a raw count/percentage check,
   \`published_count\`, \`published_denominator\`, \`published_percentage\`,
   \`primary_count\` and \`primary_denominator\`. Every binding has an exact
   \`text\` and **0-based Python character offset into its own quoted passage**.
   The token must exactly match its submitted value, avoiding substring matches
   within larger numbers. A verified byte hash does not by itself prove the
   selected table-cell interpretation.
4. An \`analysis\` object with \`report_id\`, \`contrast_id\`,
   \`included_as_independent_effect\` (boolean),
   \`same_cohort_source_verified\` (boolean), and \`dependence_handling\`
   (INDEPENDENT_UNCORRELATED, CORRELATION_ACCOUNTED_FOR or UNKNOWN).
   All these are reviewer's source-based **attestations**, not facts inferred
   by the tool. Unknown dependence leads to HOLD in overlap preflight.

For a machine-generable synthetic packet, see
\`TrialSourceLedgerTests._row\` in \`tests/test_synthesis_source_trial_view.py\`.
That fixture builds source files, hashes and offsets dynamically and is not
a real trial record.

## Scope and important abstentions

- **HOLD** if either source snapshot is inaccessible/changed, trial key not
  quoted at its selected location, value not bound at its exact quote offset,
  source tier is T4, analysis model/identity unknown, or the candidate is already
  a published correction without a verified *current* error.
- **NOT_COMPARABLE** for incompatible declared endpoints, time windows, cohorts
  or analysis definitions; do not subtract values across these estimands.
- **REVIEW_CANDIDATE** requires matching declared contexts, source-bound values,
  current uncorrected version and documented source-checked refutation; it is
  *never* a confirmed scientific error or publication validity assessment.
- **NO_SCOPED_DIFFERENCE** means the selected quoted values agree, not that
  the meta-analysis or source extraction is correct.
- Duplicate NMA preflight runs on eligible declared rows and retains a separate
  status; a single same-family label is not proof of duplicate patients, and
  covariance accounting can legitimately reuse a shared control.
- The original analysis model and the source-corrected model have **not** been
  fitted here. No effect-size, significance or treatment-ranking changes can
  be inferred merely from this ledger.

## Static-versus-runtime disclosure

| Question | Actual operation |
| --- | --- |
| Field names, supported comparisons, maximum rows | Static contracts |
| File hashes, quote existence, selected character offsets and arithmetic | Checked dynamically **on submitted captures** |
| Trial identifier existence, registry relation, comparator/endpoint assignment | Not verified; reviewer statements |
| Eligibility, source study overlap and covariance | Caller-attested, subject to existing conservative NMA preflight |
| Full study search coverage, missed papers, model reproduction | Not performed |
| Independent error recall, false-positive rate or conclusion impact | **Unknown** pending a separately controlled masked study |

## Optional model-replay bridge

The separately documented [published-first paired OR replay](SYNTHESIS-PAIRED-OR-REPLAY.md) can accept an independently source-bound two-arm count table and, **only with a trusted pinned external engine**, execute the publication-matched original method before a corrected-input run. It does not reanalyse NMA/IPD, infer clinical conclusion changes, or authenticate the scientific meaning of a quote. The ledger alone does not authorize model execution.

## Next scientific work

A source-validated extraction for all arms/outcomes of a defined small NMA,
followed by actual replay of the paper's **published model first** and a
compatible corrected-input model second, with saved scripts, versions, raw
outputs, effect estimates and independent statistical review. Reuse the
count-recovery harness for arm-level preconditions rather than treating
incomplete rows as zero events.

Development fixtures from previous Synthesis cases and published correction
notices are **excluded** from any untouched prospective evaluation cohort.
Always honour publisher access restrictions, correspondence holds and author
no-contact requests. The ledger does not send mail.
