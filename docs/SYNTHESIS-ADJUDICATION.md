# Source-bound cohort and outcome decision records

This bounded M3/M4 increment records declared reviewer judgments alongside
revalidated evidence. It supports cohort-overlap and outcome-equivalence pairs.
It does not decide whether a judgment follows from its passages, establish
reviewer identity or independence, or authorize pooling. Every receipt retains
`HOLD`, `scientific_validity: NOT_ESTABLISHED`, and `release_eligible: false`.

## Ingredients and reuse

The existing starter replay validates OA rights, primary article identity,
corrections, optional registry references, source bytes and the analytical
payload. Its archived StepWise and STROKEWALK bundles were verified on disk before
implementation and remain unchanged. The capture module supplies exact normalized
quote locations, offsets, context and markup restrictions. The persistent audit
runner supplies bounded inventory snapshots. No new extractor or scientific
estimator is introduced. Net-new code is `scripts/synthesis_adjudication.py`, a
read-only adapter for separately anchored decision records. It does not change
the existing SQLite stage or promote its completed HOLD receipt.

## Fixed record contract

A dossier is UTF-8 JSON with exactly `schema`, `project`, `reports`, `entities`
and `relations`. Its schema is `e156-adjudication-v1`. The caller supplies the
expected project and a separately retained SHA-256 of the reviewed dossier.
Paths are supplied explicitly as `--bundle ALIAS=PATH`; they are not executed or
discovered from dossier content. Each alias must be declared and used.

- A report has a local `id` and an independently reviewed `manifest_sha256`.
  Replaying its bundle rechecks article identifiers and licences from archived
  sources. Primary PMCID, DOI and available PMID cannot be duplicated under
  another alias, including another version of the same article. Different papers
  from one trial are allowed and remain different reports; aliases are not trial
  identities. Registry links retain the existing replay's limited meaning.
- An entity has `id`, `kind`, `report`, and `scope`. Cohort scope contains
  `definition`, `population`, and `timepoint`; outcome scope also has `measure`.
  Each field is a `{quote, locator}` binding or explicit `null`. Definition must
  be bound. Quotes use the capture module's normalized whitespace and are limited
  to 500 characters. The selected locator must have one safe matching binding.
  Receipts retain offsets, context, snapshot hashes and the actual source
  metadata. Finding a quote establishes text identity; its semantic role remains unassessed.
- A relation has `id`, `kind`, `left`, `right`, `reviews`, and `adjudication`.
  `cohort_overlap` permits `SAME`, `PARTIAL`, `DISJOINT`, or `UNCLEAR`;
  `outcome_equivalence` permits `EQUIVALENT`, `DIFFERENT`, or `UNCLEAR`.
  Endpoint kinds must match. Self-pairs, reversed duplicates, duplicate IDs,
  unused entities and unknown fields are refused. No transitive graph facts or
  independent study weights are inferred.
- Each original review has `reviewer`, `decision`, `rationale`,
  `context_sha256`, and `evidence`. Evidence references `{entity, field}` must
  cite each available scope binding of both endpoints exactly once. Rationale
  is nonempty, at most 2,000 characters, and remains a reviewer declaration.
  Zero, one or two original reviews are supported; their declared reviewer IDs
  must differ. IDs are lowercase ASCII local tokens, not authenticated people.
- A third declared reviewer may adjudicate disagreement or an `UNCLEAR` pair.
  The adjudication has the same fields plus sorted `review_sha256`, containing
  hashes of both complete original review objects. It cannot replace the
  original ballots, use either original reviewer ID, or override an agreed
  definite decision. `context_sha256` binds the project, relation ID/type and
  endpoints, complete endpoint scopes, and relevant report anchors. Editing
  these inputs invalidates existing review bindings; editing a ballot invalidates
  the adjudication. These hashes are not signatures or an authenticated history.

Every verification reads the dossier anew and executes every unchanged source
replay. It checks complete bundle inventories, dossier bytes and implementing
code hashes before and after verification. Missing, altered, malformed or
unexpected inputs refuse a current receipt. Storage errors are reported separately.
The receipt has a deterministic ID derived from its complete contents. A changed
adapter or replay implementation changes that identity. The replay's own version
binding continues to refuse changed replay code.

The decision file is persistent input, not a journal: there is no historical
append-only guarantee, permanent invalidation flag, conflict-merging service or
atomic editing command. Keep reviewed versions and their anchors separately.
Restoring original bytes permits verification again. For journaled audit progress,
use the separate [persistent runner](SYNTHESIS-REVIEW-RUNNER.md). The new record
adapter never emits its SQLite completion receipt or sends external actions.

| Relation state | Meaning |
|---|---|
| `INCOMPLETE_SCOPE` | At least one endpoint scope field is null; no resolved decision is emitted |
| `AWAITING_REVIEWS` | Scope is populated but fewer than two original ballots exist |
| `DISAGREEMENT` | Two ballots differ and no adjudication is recorded |
| `UNRESOLVED` | Agreement or adjudication says UNCLEAR |
| `AGREEMENT_RECORDED` | Two declared reviewers recorded the same definite answer |
| `ADJUDICATION_RECORDED` | A third declared ID recorded a definite decision bound to both ballots |

None of these states establishes clinical correctness. Two IDs may belong to
one person; two copied ballots may agree; a quoted passage may be irrelevant.
The adapter reports `DECLARED_NOT_AUTHENTICATED` reviewer identity and
`NOT_ASSESSED` semantic support even in agreement/adjudication states. Authenticated
independent review, semantic adjudication, reviewer blinding and broader synthesis
eligibility remain separate work.

## Reproducible unreviewed example

[The StepWise example](../examples/synthesis-adjudication-stepwise.json) binds the
existing archived baseline/eligibility passages. Population and timepoint scopes
remain null; no reviewer, outcome decision or clinical finding is invented.
Its reviewed dossier SHA-256 is
`184552927c4defaa8741a5c792ffa508522b05d63c3987eea66abde64811e114`.

```console
python scripts/synthesis_adjudication.py --dossier examples/synthesis-adjudication-stepwise.json --project stepwise-development --expected-sha256 184552927c4defaa8741a5c792ffa508522b05d63c3987eea66abde64811e114 --bundle stepwise=examples/synthesis-replay-stepwise
```

The result is `RECORDS_REVALIDATED` with `INCOMPLETE_SCOPE` and HOLD. Exit 0 means
record verification ran, not review completion or release approval. Exit 2 means
refusal and exit 3 means a storage error; both have a null receipt. The command
writes only stdout. Keep private reviewer records and identifying information out
of public repositories. Do not use shell output redirection to overwrite a dossier.

To prepare ballots, review and populate each endpoint's source-bound scope,
retain the revised dossier, and inspect its verified relation `context_sha256`.
Each reviewer records that context, their judgment, rationale and all available
scope references. Preserve the original objects when recording an adjudication.
Retain the newly reviewed complete dossier hash externally before accepting it.
Computing and accepting the current hash automatically at resume defeats that
boundary. The tool does not authenticate this review or anchor distribution.

Bounds: 256 KiB dossier, 1–8 reports, 2–32 entities, 1–64 relations, two original
reviews and one optional adjudication per relation. The process assumes a trusted
local interpreter/filesystem; before/after checks are not an atomic snapshot
against an adversary who changes and restores files during execution. Source
licensing and origin caveats remain those of the original replay. General PDFs,
unarchived web sources, registry outcome extraction and cross-file supplements
are not newly supported.

## Static versus dynamic disclosure

| Material | Origin | Boundary |
|---|---|---|
| Schema, limits, scope fields and state rules | Authored static contract | Engineering choices, not clinical findings |
| Example definitions | Existing archived OA source passages | Exact text bindings, no completed reviewer judgment |
| Example missing scopes and empty reviews | Explicit unreviewed state | No filler reviews or invented equivalence |
| Test ballots and deliberately reused scope quotations | Synthetic development controls | Structural behavior only; never real reviewer decisions |
| Source identifiers, byte hashes, replay results, receipt IDs | Actual parsing and execution | Identity/integrity, not semantic truth |
| Reviewer IDs and rationale | Operator declarations | Unauthenticated, independence unestablished |

Integration tests were written before the adapter. They exercise typed decisions,
missing scope, disagreement, stale context/ballots, duplicate sources, malformed
types, quote/locator failures, source/code mutation and repeat CLI execution.
These are development contracts, not held-out scientific accuracy measurements.
