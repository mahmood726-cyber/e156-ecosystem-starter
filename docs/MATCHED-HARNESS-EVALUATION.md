# Matched harness evaluation: preparation and execution contract

**12 November 2026. Software preparation; independent scientific study NOT STARTED.**

This extends the [blinded validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md)
and [pilot runbook](SYNTHESIS-HARNESS-PILOT.md). No unseen corpus, custodian,
independent reviewers or paid-call budget has yet been supplied for this comparison.
The exposed StepWise/STROKEWALK examples and synthetic tests are development
material. They must not become the untouched scientific test sample. Preserve
the existing protected Simo cohort and labels.

## Reused implementation and bounded addition

Within e156-ecosystem-starter, `scripts/synthesis_blind_eval.py` already validates
family splits, source states, prediction freezes and independent reference
receipts; it scores wrong-root flags as both false alerts and missed errors.
The new `scripts/synthesis_matched_eval.py` reuses that evaluator unchanged.
SciCoQA's paired runners were inspected for failure retention and raw-output
binding; their SciCoQA-specific input schemas are not repurposed as generic
research tasks. The existing recovery benchmark remains an engineering test.

The addition checks a common protocol, verifies task-file bytes, validates the
complete claim-by-arm run ledger, exports masked review rows and reports paired
descriptive counts, time and separately recorded costs. It does not run a model,
install a runtime, enforce a spending cap, authenticate people, verify a licence,
or reproduce a scientific conclusion. No new runtime SDK dependency is needed.

## Prospective comparison

The custodian must approve and freeze the following before any test run:

1. **Atomic tasks and sampling.** An unseen OA source collection with authenticated
   versions, rights, DOI/family identifiers, source locations and supplements.
   Enumerate individual error-root targets, including unflagged claims. Freeze
   selection rule, seed, development/test families and any source-limited stops.
   All test claims must receive a reference label, including UNKNOWN. This narrow
   implementation does not support sampled-negative weighting.
2. **Arms.** Select an E156-integrated runtime and at least one advanced comparator.
   For example, a pinned LangGraph or Deep Agents configuration can run the same
   provider/model as the E156 arm. Freeze each source revision, system prompt,
   settings, model snapshot, decoding parameters, tool versions and permissions.
   Equal model/decoding and tool-access digests are required for `harness_only`.
   Comparisons using different models are `system` comparisons. The custodian
   must resolve what E156 adds to the chosen runtime: a verification component
   alone is not a general agent runtime.
3. **Shared limits.** Per atomic task: elapsed wall seconds, total model tokens,
   tool calls, API cost in USD and operator review seconds. Freeze total study
   spend externally as well. Common caps do not imply equal actual consumption.
   Adapters must enforce caps independently, including nested agents and retries;
   this evaluator only audits the recorded values afterward.
4. **Order and independence.** `prepare` emits a deterministic order using the
   frozen `order_seed`. Use fresh isolated sessions for each row and record actual
   order in the private ledger. This version permits one scheduled record per
   claim/arm. Internal provider retries are retained in its attempt count, usage,
   elapsed time and private trace; no selected best-of retries or repeated-run
   claims. Shared paper-level work must have a prespecified allocation rule to
   prevent counting its cost once for every claim.
5. **References and endpoints.** A separate custodian controls the reference
   material. Independent reviewers establish source truth without seeing arm
   identities; reconcile disagreements with a separate adjudicator. Freeze
   root-detection recall including abstentions, precision, false alerts,
   abstention/UNKNOWN fractions, runtime failures, operator time and costs.
   Family-cluster uncertainty and any superiority decision require a separately
   approved analysis plan; this tool supplies paired counts by family only.

## Files and schemas

Keep private material outside the repository. Canonical JSON hashes use
`synthesis_blind_eval.sha256_json`: sorted keys, compact separators, UTF-8 and no
NaN. File hashes use the exact bytes. All timestamps have an explicit timezone.

| File | Required contents |
|---|---|
| `manifest.json` | Existing `synthesis-blind-manifest-v1`: frozen claim/family inventory and authentic source metadata. |
| `protocol.json` | `synthesis-matched-protocol-v1`; `purpose: prospective`; `comparison_kind: harness_only` or `system`; `manifest_sha256`; `frozen_at`; integer `order_seed`; `retry_policy: one_record_all_internal_attempts`; `analysis_plan_reference`; custodian, independent review and unseen corpus receipt references. |
| Protocol `arms` | Unique `arm_id`, `runtime`, exact `runtime_version`, `model_snapshot`, `config_sha256` (full prompt/runtime config), `model_config_sha256` (decoding settings), `tools_sha256` (versions, permissions and source-access contract). Preserve the hashed artifacts privately. |
| Protocol `tasks` | Exactly the manifest test claims: `claim_id`, relative `input_file`, `input_sha256`, `oa_rights_reference`, and `source_files` entries with relative `file` and `sha256`. Each task pack contains the same source bytes and user task for every arm. No answer fields. |
| Protocol `limits` | Exactly `wall_seconds`, `model_tokens`, `tool_calls`, `api_cost_usd`, `review_seconds`; finite nonnegative caps, integer tokens/tool calls. Zero is an explicit zero-resource cap. |
| `runs.json` | `synthesis-matched-runs-v1`; `protocol_sha256`; a common `frozen_at` after every result and before reference exposure; complete `records`. |
| Each run record | `arm_id`, `claim_id`, `arm_sha256` (canonical arm object), `input_sha256`, `status`, `started_at`, `ended_at`, observed `wall_seconds`, `internal_attempts`, `record_evidence_reference`, `record_evidence_sha256`, `prediction`, `usage`. |
| Run `prediction` | `disposition: FLAG`, `NO_FLAG` or `ABSTAIN`; measured `review_seconds`. FLAG requires `flag_root_id` and `evidence_locator`; ABSTAIN requires `stop_point`. |
| Run `usage` | Exactly `model_tokens`, `tool_calls`, `api_cost_usd`, `human_review_cost_usd`. Missing observations are JSON `null`, never invented zeros. Costs are charged USD observations supported by billing/usage evidence; estimates from price tables must not be passed as actual billed cost. |
| `masked.json` | Generated `synthesis-matched-masked-v1`: sample IDs, claim IDs, input hashes and whitelisted prediction fields. No arm, runtime, model, time or cost fields. |
| `adjudications.json` | `synthesis-matched-adjudications-v1`; `masked_packet_sha256`; exactly one adjudication per masked `sample_id`, with `truth: ERROR`, `NO_ERROR` or `UNKNOWN`, `independent_masked: true`, `adjudicated_at` and `evidence_reference`. Known-truth FLAG rows also require boolean `flag_root_match`. |

Prospective receipt fields are `custodian_receipt_reference`,
`independent_review_plan_reference` and `unseen_corpus_receipt_reference`.
Requiring these strings prevents accidental omission; it does not authenticate
approval. `purpose: synthetic_contract` exists only for artificial software
fixtures, not for reclassifying familiar research papers as unseen tests.

Every listed source file is byte-checked. A VERIFIED_ORIGINAL claim must have its
`original_sha256` in that checked inventory. This proves the declared source bytes
are present, not that a derived task pack faithfully quotes or includes them;
the custodian verifies that relationship and that every adapter receives the
inventory. Source-limited tasks can have an empty inventory with their declared
stop point. Path traversal, symbolic links and junctions are refused.

The private record evidence should retain raw output, parsing errors, all internal
attempts, provider request IDs, timestamps, token/call usage, billing reconciliation
and the operator time log. Its hash is a binding declaration in this version;
the evaluator does not open or authenticate that evidence. The custodian must
verify those files against their hashes and records. Never put API keys or secret
headers in a receipt or publish unredacted provider logs.

## Operating sequence

Run from the repository root using relative paths to an operator-owned study
directory. The names below are arguments, not supplied study files.

```text
python scripts/synthesis_matched_eval.py prepare --manifest study/manifest.json --protocol study/protocol.json --inputs study/inputs --output study/prepared.json
python scripts/synthesis_matched_eval.py mask --manifest study/manifest.json --protocol study/protocol.json --inputs study/inputs --runs study/runs.json --output study/masked.json
python scripts/synthesis_matched_eval.py compare --manifest study/manifest.json --protocol study/protocol.json --inputs study/inputs --runs study/runs.json --output study/pre-adjudication.json
python scripts/synthesis_matched_eval.py compare --manifest study/manifest.json --protocol study/protocol.json --inputs study/inputs --runs study/runs.json --adjudications study/adjudications.json --output study/comparison.json
```

`prepare` returns `PREPARED_NOT_RUN` with no scientific results. Between preparation
and masking, the operator must run approved adapters, capture real results and
freeze the complete ledger. Give each runtime only the public task pack and its
configuration. Do not give it the private protocol mapping, receipt store, answer
key, other arm's output or unrestricted access to the custodian's filesystem.
All outputs are created exclusively; an existing output is never overwritten.

FAILED, TIMEOUT and NOT_ATTEMPTED are explicit runtime statuses and require an
ABSTAIN prediction. They remain in the denominator. Zero internal attempts is
reserved for NOT_ATTEMPTED; actual attempts require a positive count. Unparsable
results must abstain with the parsing stop point. Do not fabricate NO_FLAG for
an error, missing source or interrupted run. Source-limited originals also abstain.

Give reviewers only the masked packet and appropriate source material. Masking
removes structured identity fields, but cannot remove identifying prose from an
evidence locator or stop reason, authenticate human independence, or stop a holder
of the private ledger from reconstructing the mapping. Custodian review and secure
allocation remain necessary. Reconcile one common source truth for each claim
across all arms; root matching can differ by arm.

The evaluator refuses incomplete or changed records. Resource overruns are reported
as `VIOLATION`, unavailable cap measurements as `UNVERIFIED`; they do not erase
predictions. `WITHIN_RECORDED_CAPS` describes the supplied records, not enforcement.
Without adjudications there are no accuracy results. Missing costs produce a null
total plus an observed subtotal and missing-record count. API and operator costs
remain separate; infrastructure and independent reference adjudication are not
included. Do not call either subtotal the total study cost.

## Interpretation and verification

Per-arm metrics retain the existing evaluator's claim-level Wilson intervals.
Those are not family-cluster uncertainty intervals. Paired tables show both,
left-only, right-only and neither for error-root detection, false alerts on
adjudicated negative claims (`negative_claim_false_alert`) and abstentions, with
family-level counts. Wrong-root flags on error claims remain FP and FN in the
per-arm scorer; they are outside the negative-claim false-alert denominator.
The paired tables provide no significance test, composite
score, automatic winner or superiority statement. All reports retain
`scientific_validation: NOT_ESTABLISHED_BY_THIS_SOFTWARE`.

```text
python -m pytest tests/test_synthesis_matched_eval.py tests/test_synthesis_reporting.py -q
```

Tests use deliberately synthetic DOI-like strings and bytes, not publication
identifiers, real model outputs or independently adjudicated research findings.

| Item | Static implementation / protocol | Dynamic evidence required |
|---|---|---|
| Schemas, hashing, masked field allowlist, failure rules, paired count formulas | Yes | Tested with synthetic contracts only |
| Comparator choice, budgets, selection and analysis plan | Proposed structure only | Independent prospective freeze |
| Corpus, OA rights, IDs, exact source versions, lack of prior exposure | No research sample supplied | Custodian-authenticated records |
| Model performance, usage, billed cost, human time and scientific labels | No measurements supplied | Real run receipts and independent adjudication |
| Overall superiority or production readiness | No | Not conferred by this tool |
