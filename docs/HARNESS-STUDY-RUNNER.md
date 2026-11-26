# E156 development study runner

The [runner](../scripts/harness_study_runner.py) connects the
[file-backed preflight](HARNESS-STUDY-PREFLIGHT.md),
[durable runtime](HARNESS-EXECUTION.md), and
[matched evaluator](MATCHED-HARNESS-EVALUATION.md). It stages concrete cases,
executes a serial frozen schedule, retains failures, and binds records to private
evidence before masking. The [record adapter](../scripts/harness_study_records.py)
derives predictions and usage from retained operations; an editable summary is
not accepted as the prediction's authority.

**Scope: E156-only development. Scientific study status: NOT_STARTED.**
Protocol purposes are `development` and `synthetic_contract`; this runner does
not admit a prospective scientific protocol. Live native-comparator adapters,
an unseen OA corpus, authenticated human custody and independent scientific
adjudication are not supplied here. Software contracts, preflight receipts and
completed development records establish no scientific superiority. The
[prospective plan](HARNESS-PROSPECTIVE-STUDY.md) owns those remaining decisions.
Previously consumed benchmark final cases must not be reused as unseen material.

## Frozen inputs and operating scope

Use separate operator-owned input, private evidence, work and result directories.
Keep these private artifacts outside the repository. The work directory must not
already exist at preparation and must be disjoint from the input and evidence
roots. The input/evidence separation and bounded, link-refusing reads follow the
preflight contract. Commands below run from the repository root; directory and
file names are operator-supplied arguments, not bundled study material. Create
the private result directory before requesting CLI output there.

Use a filesystem supporting exclusive hard-link publication and same-directory
atomic rename, such as local NTFS or an appropriate local POSIX filesystem.
Unsupported publication fails closed. The recovery contract covers process
interruption; it does not promise durability through power loss or arbitrary
network-filesystem behavior.

In addition to the preflight's manifest, protocol and evidence inventory:

- Every arm has `runtime: e156` and `runtime_version` equal to the canonical JSON
  digest of `harness_runtime.profile()` for the executing code.
- Its config artifact has exactly `schema: e156-study-arm-configs-v1`,
  `runtime_profile` and `configurations`. The latter maps every claim ID to its
  complete concrete runtime configuration. There is no implicit template
  expansion at execution time.
- Each concrete config has one frozen model and one selected route, the arm's
  exact model snapshot, explicit price policy, `request_policy:
  {"service_tier":"default"}`, task selection, skills and limits. Optional
  `progress_policy` must also be frozen. Model and tool artifacts must match the
  actual `model_contract` and `tools_contract` computed by the runner, including
  prompt identities, tool schemas, permissions and caps.
- `worker` must be `null`; authorized tools are limited to `read_evidence`.
  No `python_worker` execution is admitted inside this runner. Derived task
  inputs remain usable after receipt-bound preflight validation. Their existing
  recipes are not executed by preparation or this read-only tool path.
- The protocol supplies common per-task limits. A separate budget JSON object
  supplies exactly `model_calls`, `model_tokens`, `tool_calls`, `cost_microusd`
  and `wall_ms`, each a nonnegative integer, as aggregate study ceilings.

This implementation admits at most 1,000 scheduled case-arm slots. Each case has
a positive wall limit no greater than 300,000 milliseconds, also bounded by the
common protocol cap. These are implementation limits, not study-size or
scientific adequacy recommendations.

Each case receives a separate staged input directory, configuration, context and
journal. The context is limited to the task's ancestry and authorized skills.
Derivation recipes/receipts may be staged for validation; their presence does not
make them available through the model's node allowlist. Source bytes are checked
again before use. This is a trusted local runner with constrained tool access,
not a general operating-system sandbox against malicious host code.

The request contract fixes `parallel_tool_calls: false`, `store: false`, and
`include: ["reasoning.encrypted_content"]`. Omitted provider defaults are recorded
as omissions, not invented settings. Changing source, configuration, fixtures or
producer code after preparation causes a binding refusal. The plan also binds
the Python implementation, version, cache tag and platform; recovery must use
the matching environment.

Use a current, source-backed price upper bound covering applicable tier and
cache-write/input charges; record its reference and expiry. Provider prices and
caching policies may change. A configured monetary ceiling cannot establish
actual charges. See the provider's [prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching).

## Prepare and dispatch

Preparation is offline. It validates and stages evidence without launching a
model, and returns `PREPARED_NOT_RUN` with `scientific_results: null`.

```text
python -m scripts.harness_study_runner prepare --manifest private/manifest.json --protocol private/protocol.json --inventory private/evidence-inventory.json --inputs input-artifacts --evidence private --budget private/budget.json --mode LIVE --work study-work --output private-results/prepared.json
```

For an explicitly synthetic rehearsal, use a distinct new work directory and
`--mode SYNTHETIC_CONTRACT --fixtures private/fixtures.json`. Fixtures map every
computed case ID to exactly `input_tokens` and a nonempty `responses` list. They
are scripted test responses, not live predictions or observed scientific data.
Synthetic mode does not invoke the paid provider. Live mode refuses a fixture
file; execution mode is retained in the evidence.

Live dispatch requires the prepared explicit configuration and aggregate cap,
the `--allow-paid` flag, and `OPENAI_API_KEY` supplied through the environment.
These technical gates do not authenticate budget authorization or source rights.
Do not put credentials in JSON, command arguments, receipts or published logs.
This transport currently uses the configured OpenAI Responses path; it has no
automatic provider fallback or retry after an ambiguous outcome.

```text
python -m scripts.harness_study_runner run --work study-work --allow-paid --output private-results/dispatch-01.json
```

One `run` invocation selects at most one new scheduled case. Invoke it again with
a new output filename only after inspecting the prior status. Omit
`--allow-paid` for synthetic mode. `CASE_RECORDED` means evidence was retained;
inspect its runtime status before interpreting the outcome. `EXECUTION_COMPLETE`
means no new scheduled slots remain, not that every prediction succeeded.

Before dispatch, the supervisor durably reserves the entire case ceiling against
the aggregate budget. It never refunds unused case allowance. `STUDY_BUDGET_STOP`
starts no additional case; retain all remaining slots through `abort` instead of
removing them. An `EXECUTION_UNKNOWN` result blocks ordinary continuation and
requires explicit settlement, reconciliation/resumption or abort.

## Interrupted execution and recovery

The supervisor and child use operating-system file locks. A live child holds its
case lock for its lifetime; a lock is not reclaimed merely because a PID or
timestamp looks stale. Preserve the work directory when investigating a refusal.
Do not delete a journal or edit state to force a new attempt.

A child-owned watchdog keeps the original deadline active after parent loss.
Provider operations are also bounded by the remaining original deadline, and
each provider subprocess owns a total-deadline watchdog. Snapshot checks are
inside the case watchdog too. Remote accepted requests may outlive local cleanup.

Use the exact `case_id` reported by the runner or retained in `plan.json`:

```text
python -m scripts.harness_study_runner settle --work study-work --case-id CASE_ID --output private-results/settlement.json
python -m scripts.harness_study_runner reconcile --work study-work --case-id CASE_ID --receipt private/recovery.json --output private-results/reconciliation.json
python -m scripts.harness_study_runner resume --work study-work --case-id CASE_ID --allow-paid --output private-results/resumption.json
python -m scripts.harness_study_runner abort --work study-work --output private-results/abort.json
```

`CASE_ID` in these command templates must be replaced with that recorded value.
The commands serve different recovery states:

| Action | Meaning |
|---|---|
| `settle` | Retain an already completed child output after parent loss. It checks the output against the current journal and does not launch a provider request. |
| `reconcile` | Bind a genuinely recovered terminal model response to the exact unresolved operation. It does not fetch or invent the response and does not resume execution. |
| `resume` | Continue the named pending case through its journal; completed operations are replayed locally. It may make a new call if the original remaining workflow requires one, so live mode still needs paid authorization. |
| `abort` | Record all unfinished and never-dispatched slots without starting calls. Completed child evidence is settled when available; unknown outcomes and reservations remain retained. |

The recovery receipt is `e156-harness-recovery-v1`. It binds configuration,
context, current journal tip, operation, reservation, request and exact recovered
response; it also requires the reviewer, reason, evidence reference and explicit
attestation defined by [runtime recovery](HARNESS-EXECUTION.md). The recovered
model and service tier must match the frozen configuration. It is an operator
attestation, not provider authentication or independent scientific review. Only
model-response recovery is supported; a missing count/tool result is not
silently reconstructed.

Resumption preserves the first start, original deadline and full case reservation.
It does not create a fresh time or spending allowance. An unknown dispatch
without a journal cannot be retried automatically. If the original deadline has
expired, retain evidence and abort instead of extending it. Whole-task elapsed
time includes recovery gaps; it is not the sum of operation durations. Terminating
a local process does not prove that an already accepted remote request incurred
no charge. The read-only tool restriction avoids introducing an unbounded worker
process into this initial deadline contract.

## Draft records and explicit measurements

Once every scheduled slot has execution or abort evidence, export drafts:

```text
python -m scripts.harness_study_runner records --work study-work --output private-results/drafts.json
```

The output maps case IDs to `e156-study-record-draft-v1` objects. A completed
runtime result becomes a `COMPLETE` record only after its prediction is derived
from the last settled model response and checked against the trace summary.
Invalid structured output retains the runtime's `ABSTAIN` parsing stop.
Noncompleted results are `FAILED`, or `TIMEOUT` when the lifecycle records deadline expiry, with `ABSTAIN`.
`NOT_ATTEMPTED` has zero dispatches and known zero model/tool usage; it remains in
the planned denominator.

`internal_attempts` counts runner dispatches including resumes, not provider
requests. Separate `operation_counts` distinguish count/model/tool allocations,
finished operations, reconciliations and unresolved operations. Reported model
tokens and tool calls come from settled usage; an unresolved operation makes the
relevant usage category null. The `accounting` object separately retains observed
usage, `unresolved_reserved` and `recovered_wall_reserved`. An absent report after
an interruption leaves resource observations unknown rather than zero.

Draft `prediction.review_seconds`, `usage.api_cost_usd` and
`usage.human_review_cost_usd` are null. Record human work with an actual timing log
and a prespecified allocation basis, including interventions as applicable.
Neither model execution time nor an agent's guess supplies human review time.

Supply `measurements.json` as an object mapping **every case ID**, including
failed/unattempted cases, to an object with exactly these fields:

| Field | Required value |
|---|---|
| `schema` | `e156-study-measurement-v1` |
| `case_sha256` | Exact value from that case's draft |
| `report_sha256` | Exact value from that draft, including null when no report exists |
| `review_seconds` | Measured finite nonnegative number; null and booleans are refused |
| `api_cost_usd` | Attributable observed charge, or null if unavailable |
| `human_review_cost_usd` | Observed allocated human cost, or null if unavailable |
| `evidence_reference` | Nonempty reference to the retained timing/billing evidence |
| `observed_at` | Timezone-bearing timestamp at or after the case's end and no later than the retained freeze timestamp |

An explicitly measured zero is permitted; absence of a measurement is not zero.
All required cases need a numeric review-time measurement before this v1 ledger
can freeze. Hashes bind the supplied declaration; they do not authenticate the
person, stopwatch or invoice. Charges may stay null. Estimated price-policy
costs and reserved ceilings are never substituted for actual billed USD. API and
human costs remain separate, and an observed subtotal is not total study cost.

## Freeze before masking

```text
python -m scripts.harness_study_runner freeze --work study-work --measurements private/measurements.json --output private-results/freeze-summary.json
```

Freeze requires all planned slots and measurements, with no unresolved case left
open. Abort can close a failed slot while retaining unresolved resource evidence;
it cannot manufacture a successful outcome or known usage. Finalization
recomputes each draft from original inputs, then creates an immutable evidence
package containing case, report, configuration, context, arm, task, draft and
measurement. Each record points to `evidence/<sha256>.json` inside the frozen
bundle. Its SHA-256 covers exact compact, sorted UTF-8 JSON bytes followed by one
LF. This differs from the canonical JSON digest without that trailing LF used
for case/report identities.

Publication first creates `exports/<generation-sha>/intent.json` with a fixed
freeze timestamp, then stages its bundle. The generation binds the plan,
measurements and retained case-record identities. Retrying the same freeze after
interruption verifies existing bytes and resumes that generation. Different
measurements can create a different generation only before publication.

A complete bundle is renamed atomically to `frozen/` within the work directory.
It includes `runs.json`, `masked.json`, `comparison.json`, `manifest.json`,
`protocol.json`, bound evidence packages, checked input files, and `receipt.json`
with content hashes. State then records the receipt and ledger identities. If a
process dies after publication but before the state update, repeat the same
freeze command: the runner verifies and re-adopts the matching bundle. It refuses
a different generation or changed/missing published bytes. A fully committed
freeze closes the study to further execution and export; do not delete artifacts
to force a replacement. CLI `--output` files are exclusive, so use a fresh result
filename if an earlier summary already exists.

Masking is computed from the complete frozen ledger. Do not reveal reference
labels before the freeze or amend the ledger afterward: changes to costs also
change masked sample IDs. Later billing reconciliation belongs in a separately
bound supplement, not a rewrite of scored records.

Keep the full bundle private: traces and evidence packages contain prompts,
source text, raw responses and human records. Only the appropriate masked packet
and sources belong in a reviewer handoff. Masking removes structured arm fields;
free text may still identify an arm, and software cannot establish reviewer
independence. A pre-adjudication comparison can report accounting and descriptive
records; null costs leave applicable budget checks `UNVERIFIED`. It supplies no
accuracy results or superiority decision. `scientific_results` remains null.

## Static-versus-dynamic disclosure

| Item | Static or frozen contract | Dynamic evidence and limitation |
|---|---|---|
| Schedule, schemas, tools, source scope, route and caps | Checked before dispatch; E156 development only | Supplied actual configurations and file identities; no invented corpus or approved budget |
| Synthetic mode | Explicit scripted responses and counts | Software rehearsal only; never live scientific observations |
| Live predictions and usage | Frozen provider request contract and trace parser | Actual retained responses; unknown outcomes remain unknown; local consistency is not provider authentication |
| Budget | Full case ceilings reserved before dispatch and never refunded | Configured price policy, not an invoice or a guarantee of remote billing |
| Attempts and time | Runner dispatches; original case start/deadline | Whole lifecycle includes recovery gaps; operation clocks and recovery ceilings stay separate |
| Human time and charges | Exact measurement schema; no zero imputation | Supplied timing/billing evidence; human authenticity and allocation remain external |
| Freeze and masking | Complete ledger and byte-bound evidence packages | Integrity under a trusted local producer, not tamper-proof external custody |
| Scientific validity or comparative leadership | No automatic approval or winner | Fresh independent corpus, reference review, live comparator evidence and prespecified analysis still required |

Development verification uses synthetic contracts and process/recovery probes:

```text
python -m pytest -q tests/test_harness_study_runner.py tests/test_harness_study_records.py tests/test_harness_provider.py tests/test_synthesis_study_preflight.py tests/test_synthesis_matched_eval.py
```

Passing these checks does not execute or validate the proposed scientific study.
