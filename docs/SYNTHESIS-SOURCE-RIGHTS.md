# Source rights for automated Synthesis work

Effective 5 November 2026. This is an operational control for the research
programme, not a determination of copyright law or a prohibition on ordinary
scholarly reading. Permission for source use and the separate question of ethics
committee review must not be conflated. No further email to JAMA is required to
implement this control.

## Current hold

`SYN-SOURCE-HOLD-JAMA-20261104` blocks automated acquisition, parsing, extraction,
text mining, replay and model submission of JAMA Network content under the
present restriction. It covers article text, figures/tables as content,
supplements, corrections, cached text/XML/PDF, existing extractions and copies on
PMC, repositories, author sites or mirrors. Changing host, supplying a licence
flag, or restarting a task does not remove the hold. Match the original DOI,
journal/publisher identity and originating URLs; the gate recognises DOI prefix
`10.1001/`, JAMA titles, former Archives titles and JAMA/AMA domains. Unknown or
conflicting identity is held rather than guessed. No article body is required
to make this decision.

The public policy records the programme decision and the operator's dated
instruction. Original correspondence, personal addresses, message identifiers
and permission files stay private. Release requires a reviewed code/policy
change supported by documented clarification or permission. This conservative
programme hold does not assert that every JAMA article has the same licence or
that every ordinary reading activity is prohibited.

Preserve past provenance, hashes, scientific classifications and correspondence.
Add a new rights status; do not rewrite historical source access as if it never
occurred, alter counts, delete evidence, or reopen held article text. Metadata
inventories and governance checks may continue. Hold status neither confirms nor
refutes any scientific finding.

## Permission gate

Before any article IO, independently inspect identity metadata and the
applicable licence, terms or specific permission for the planned route and use.
Do not obtain article text merely to discover whether it can be mined. Public
readability, subscription access, a PMC location, robots.txt, an OA flag, or a
model's assertion alone do not verify permission. When terms conflict or the
legal basis is uncertain, record HOLD and seek competent clarification through
the appropriate governance route; the code does not resolve that uncertainty.

Set `SYNTHESIS_RIGHTS_MANIFEST` to the private reviewed JSON manifest and
`SYNTHESIS_RIGHTS_LOG` to a private append-only JSONL decision log. The gate does
not automatically create permission grants. The manifest has a `sources` array
with exactly one entry matching each requested `resource`:

| Field | Required evidence |
|---|---|
| `resource` | Exact requested URL, `pmc:PMCID`, absolute file URI, or `sha256:` rendered-prompt digest. No wildcard grants. |
| `doi`, `journal`, `publisher` | Canonical original publication identity, verified from metadata. DOI-less publications are held in this implementation pending a separately reviewed identity extension. |
| `identity_verified`, `identity_evidence` | Explicit review and `{ref, sha256}` receipt for the metadata evidence. |
| `origin_urls` | Original publication and access routes when different from the requested host. |
| `permission.basis` | `licence`, `explicit_permission` or `reviewed_legal_basis`; the named reviewer must establish applicability and scope. |
| `permission.reviewed_by`, `reviewed_at`, `expires_at` | Accountable reviewer and current, timezone-aware validity interval. Expired/future reviews fail closed. |
| `permission.operations` | Separately cover `acquire`, `replay`, `process` (local extraction/analysis) and `model_submit` (external model command). |
| `permission.evidence` | Nonempty list of `{ref, sha256}` records pointing to retained, access-controlled supporting evidence. |
| `permission.restrictions_checked`, `conditions_satisfied` | Explicit confirmation after reviewing publisher restrictions, route restrictions, attribution, third-party material and other applicable conditions. |
| `content_sha256` | Mandatory for existing local files; exact bytes must match before processing. |
| `lineage` | Full source records for every publication represented by a batch, prompt or derived extraction. A container's permission never covers an unreviewed member. Any held member holds the batch. |

JSON/JSONL inputs, exact prompt digests and records declared
`content_kind: derived` require nonempty lineage in code. Reviewers must also
declare other derived formats as such; filename recognition does not establish
content identity.

The caller/reviewer must enumerate complete lineage and verify its truth; the
software cannot infer missing publications from a PDF without first processing
it. This version requires a DOI and deliberately holds unsupported identities.
For sources without permission, retain only a metadata-only HOLD record.

The command below evaluates only supplied metadata/grants and writes the access
decision; it does not download the article:

```bash
python scripts/synthesis_source_rights.py pmc:PMC123 --operation acquire --doi 10.1234/synthetic
```

The example identifier is synthetic, not a real permission record. There is no
production bypass or `--force` flag. Unit tests mock IO gates only in legacy
parser tests; boundary/integration tests exercise the real gate with exact
generated synthetic grants. Never use test grants for real sources.

Each decision records a unique ID, timestamp, resource, operation, canonical
identity, ALLOW/DENY/HOLD, reason, policy and manifest SHA-256, reviewer/validity,
and evidence references/digests. File hash/size failures append a subsequent
HOLD. Failure to append and sync a regular decision-log file stops the operation.
The log is append-only at the application boundary, not tamper-proof storage;
retain it under private access controls and normal backup/version management.

## Enforcement coverage and migration

Inspection base: `5f74f21dbc6e170c04d61eb60382877c5cef8e0c` on 5 November 2026.
The prior methodology recorded access paths and rights; PMC checked a CC BY/CC0
declaration after downloading. Neither supplied a JAMA exclusion or a common
pre-access operation-permission gate. The examined scheduled task prompts had
no such gate. The default branch was unprotected at inspection; CODEOWNERS
requires maintainer review by repository policy, not an enforced server rule.

| Path | Control added |
|---|---|
| `synthesis_capture_evidence.py` | Check before live request/cache read; process permission before parsing; bind captured DOI to the grant; block JAMA identity before body extraction; refuse redirects; retain the existing JATS licence/identity/version checks. |
| Linked PMC corrections and XML sidecars | Each target needs its own grant and local digest. Following a link is not authorization. External supplements remain manual review. |
| `synthesis_preflight.py` CLI | Approve exact packet bytes before loading; check document/source identity and cited accessible source grants before scientific checks; PMC capture also passes its own gate. |
| `scicoqa_retrieve_sources.py` | Gate dataset bytes before inventory; check acquisition/processing or replay before cache use/download, check explicit arXiv PDF target separately, and disable automatic redirect following. |
| SciCoQA context preparation/scoring/inference CLIs | Approve source-derived context/prompt/result file bytes before use; `execute()` separately checks permission for every exact rendered prompt immediately before external model submission. |
| OA benchmark/workflow and correction-register CLIs | Gate source-derived input files before replay; generated downstream packets also need reviewed grants. A multi-stage run may stop for that review. |
| Real-source correction corpus smoke tests | Hold/skip when verified permissions are unavailable; retain synthetic boundary tests. No corpus is reacquired to make CI green. |
| Scheduled Synthesis work | Explicit JAMA hold and mandatory permission/log check; unavailable or unreviewed gate means metadata/synthetic work only. Preserve schedule, paused state and no-contact rules. |

This is an IO boundary in the listed commands, not a network sandbox for every
program on the computer. Existing pure arithmetic/structural helper functions
remain callable; callers importing those helpers must gate real source input
before use. Permission attestations are not signatures or authentication of
their evidence. A misidentified or falsely approved source can still be fetched;
the PMC DOI check detects mismatches before extracting/archiving evidence.
Unrecognised mirrors require verified lineage; URL matching alone is insufficient.
The task instructions are behavioural controls, not machine-level egress rules,
and updates do not prove that already-running jobs have adopted new prompts.

Run only synthetic permission/capture/preflight/model-runner tests for this
change. Full repository CI must be checked at the exact PR head; unapproved
historical corpora stay held. Maintainer review is required before deployment;
do not equate an open PR, synthetic pass or policy document with a deployed
restriction across external tools and agents.

| Fixed policy/test constants | Per-source runtime inputs |
|---|---|
| JAMA hold identifiers/selectors, supported operations, schema, fail-closed rules and synthetic test scenarios | Original identity, access route/version, actual permission terms and evidence, reviewer/validity, full lineage, local content digest, decision timestamps |
