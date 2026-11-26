# Durable research harness

This optional runner adds budget reservations, recorded Responses calls, frozen
tool permissions, dependency checking and resumable operations to the Synthesis
workflow. Outputs remain **HOLD / unreviewed candidates**. It does not replace
the [Synthesis checklist](SYNTHESIS-v1.3-CANDIDATE.md), source replay or human review.
HTML is outside this change.

## Prepare a private run

Use Python 3.11 or newer from the repository root. The runner uses the standard
library. Keep run inputs, SQLite journals and full reports outside public Git:
reports contain source excerpts, prompts and raw model responses.

Copy the [context template](../examples/harness-runtime/context.template.json),
[configuration template](../examples/harness-runtime/config.template.json) and
[review instructions](../examples/harness-runtime/synthesis-review.txt) into a
private task directory. Templates deliberately contain nulls and zero spending
limits: they are incomplete configuration, not sample scientific results or
provider prices. Complete them before preparation:

1. Supply the actual OA source file and rights reference. Verify identifiers,
   dates and rights against the source. All node paths are relative to the task
   root. No symlinks, parent traversal or external file access is permitted.
2. Add the task's Synthesis checklist scope as a source artifact if it must be
   read by the model. Set the task text to name the relevant rows. Derived
   extraction, transform, analysis, claim and checklist artifacts must name their
   parent IDs. Memory is evidence to verify, never a trusted instruction.
3. Freeze the exact model snapshot, route and output-token limit. Obtain current
   input/output prices from the provider, enter integer micro-USD per million
   tokens, and record the price reference and expiry. One USD is 1,000,000
   micro-USD. The runner does not fetch prices or certify their accuracy.
4. Set an explicit per-run allowance for calls, total model tokens, tool calls,
   estimated cost and cumulative operation milliseconds. `request_ms` limits
   one operation; `context_chars` bounds initial evidence plus skill text.
   Catalog/tool/JSON overhead is covered by the subsequent token-count request.
5. Hash the frozen files and bind the context to the configuration. For example,
   after saving completed files as `private/context.json` and `private/config.json`:

```python
import hashlib, json
from pathlib import Path
from scripts import harness_context as h

root = Path('private')
graph = h.strict_json((root / 'context.json').read_bytes())
for node in graph['nodes']:
    node['sha256'] = hashlib.sha256(h.read_bytes(h.artifact(root, node['file']))).hexdigest()
config = h.strict_json((root / 'config.json').read_bytes())
config['context_sha256'] = h.digest(graph)
for name, value in [('context.json', graph), ('config.json', config)]:
    (root / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
```

Hashing establishes byte bindings, not scientific or licence verification. Keep
these configuration files outside the graph; do not select private reviewer
judgments, held-out labels or secrets as model evidence.

```text
python scripts/harness_context.py check --root private --manifest private/context.json
python scripts/harness_runtime.py prepare --root private --manifest private/context.json --config private/config.json --state private/run.sqlite --output private/prepared.json
```

`prepare` validates the source/config/code bindings and creates an empty journal
without an API key or network call. Output files must be new. Zero call limits
remain valid for preparation and prevent model execution.

## Execute and recover

Only after setting a budget, provide `OPENAI_API_KEY` through the process
environment and explicitly enable paid calls. Do not put the key in JSON, shell
arguments, source files or Git. A prepared journal starts with `resume`:

```text
python scripts/harness_runtime.py resume --allow-paid --root private --manifest private/context.json --config private/config.json --state private/run.sqlite --output private/result.json
```

`run` instead creates a new journal and refuses an existing state file. Resume
reuses completed operations and revalidates source, skills, configuration and
runtime code. A source/code/config change requires a new reviewed run. Failed
or interrupted API calls with unknown outcomes retain their full reservations;
the runner never retries or escalates across that ambiguity. Keep that journal
for reconciliation. Starting a separate run is not permission to ignore its
possible cost: allowances are per journal, not a shared account wallet.

The report includes all request/response attempts and the configured resource
accounting basis. `COMPLETED` means a structured candidate was produced, including
possible ABSTAIN. It never grants scientific Pass. A frozen fallback route is
used only after ABSTAIN or invalid structured output; it is not calibrated
confidence or a demonstrated quality improvement.

New execution and recovery require the returned model identity to match the
frozen snapshot. When `request_policy: {"service_tier": "default"}` is configured,
the returned tier must also match; an omitted tier policy does not impose one.
The supported response envelope contains assistant text messages, function calls
and reasoning items. Malformed or unsupported envelopes retain the complete
reservation and received response as unresolved evidence, before settlement.
Invalid final JSON inside an otherwise valid text message still follows the
ABSTAIN/output-validation policy. Offline accounting of historical artifacts
keeps its existing contract; it does not substitute for execution validation.

`inspect` writes a new report of an existing valid journal without paid calls.
The local hash chain detects inconsistent records under controlled storage;
it is not signed custody against someone able to replace the whole database.
Recovery tests exercise process termination, not physical power-loss durability
of every disk/controller. Make private backups and retain original evidence.

## Optional isolated calculation

Only a pinned skill granting `python_worker` may request calculation. Configure
`worker` with exactly `image`, `memory_mb`, `cpus`, `pids`, `tmp_mb`, and
`output_bytes`. Image must be an already pulled, reviewed repository digest
(`repository@sha256:...`), not a tag. Bounds are respectively 64–4096 MiB,
1–8 CPUs, 8–256 processes, 4–256 MiB temporary storage and 1024–1048576 output
bytes. Missing Docker refuses; task code never falls back to the host.

The Linux container has no external network, a read-only root and selected
evidence snapshot, bounded resources and no host credentials. A separate trusted
supervisor owns status files; submitted Python runs as UID/GID 65534 without
capabilities. Docker uses an isolated client configuration and fixed local
endpoint. The calling process removes only its own container; supervisor expiry
also covers calling-process death while the daemon remains running. Docker
Desktop, kernel escapes and physical power failure are not established by the
Linux CI controls. Treat calculation output as untrusted evidence to reproduce.

## Quiet freshness checks

```text
python scripts/harness_context.py watch --root private --manifest private/context.json --state private/watch.json
python scripts/harness_context.py check --root private --manifest private/context.json
```

`watch` initializes quietly, then reports only changes since its previous local
snapshot. It sends no notifications. `check` exits 1 if any graph node is changed,
missing, expired or invalidated by an ancestor; malformed input exits 2. This
command can be added to a project's existing Overmind test commands. No scheduler
or portfolio registry was changed, and it does not poll remote publications.

Derived nodes require [execution-bound derivation receipts](HARNESS-DERIVATIONS.md).
Updating a source hash in a new manifest invalidates old descendant receipts,
including descendants whose immediate parent recomputes to identical bytes.
Legacy derived nodes without receipts are DERIVATION_UNVERIFIED and cannot be
read, packed or used by a worker. Source-only contexts remain compatible.
Recompute in dependency order and start a new source-bound journal when adopting
the new graph. CURRENT means byte/receipt consistency under a trusted local
producer; Human Pass and scientific review remain independent gates.

## Recovering an ambiguous model response

An interrupted call keeps its complete reservation until an operator supplies a
terminal response with valid usage. `reconcile` is offline and never retries a
provider call. Its receipt binds the current journal tip, original reservation,
exact request, configuration, context and recovered response. The count and
frozen model/price policy are rechecked; any recorded provider identifiers must
match. A reviewer, reason, evidence reference and explicit attestation are required.
This is an **operator attestation**, not provider authentication. A hash cannot
prove that a response is genuine. No unsupported "not sent" or zero-cost release
is available. Missing tool/count results remain unresolved.

```text
python scripts/harness_runtime.py reconcile --config private/runtime.json --manifest private/context.json --root private --state private/run.sqlite --receipt private/recovery.json --output private/recovered.json
```

The receipt uses schema `e156-harness-recovery-v1` with fields `operation_id`
(`model:N`), `journal_sha256`, `reservation_sha256`, `request_sha256`,
`config_sha256`, `context_sha256`, `response_sha256`, `response` (the complete
archived terminal object), `reviewer`, `reason`, `evidence_reference` and
`attestation` exactly `I verified this terminal response belongs to this exact request`.
Hashes use the existing canonical JSON `harness_context.digest` function; obtain
the reservation and current tip from a fresh private `inspect` report. Review the
external response evidence before signing that statement. A stale receipt is
refused. Keep the receipt and full reports private.

Recovery appends a `RECONCILED` event and retains the interrupted history. A late
executor is fenced from adding another terminal result or continuing with its
uncommitted response. Resume uses the recorded result; it may execute subsequent
calls only under the existing explicit paid-run controls. Stop the old worker
before recovery when possible. This prevents duplicate journal settlement, not
external exactly-once delivery or a second process already running elsewhere.
Configuration, source, skill and code drift still refuse recovery; there is no
automatic migration of journals created by older runtime code.

SQLite lock waits are bounded by the smaller of one second and the configured
request timeout. This allows a short concurrent reader to finish before a
reservation commit; prolonged contention refuses the operation. External calls
are never retried by this mechanism. Journal overhead is not included in the
operation-only wall accounting or claimed as whole-task elapsed time.

`usage` remains conservative budget accounting. `accounting.observed` separates
validated provider tokens/calls, measured operation time and price-policy cost
from `unresolved_reserved`. Recovered model elapsed time is unknown and retains
its full ceiling in `recovered_wall_reserved`. The three components sum to
`usage`; none is an invoice. Recovery does not invent observed elapsed time.

## Portable traces and offline regression replay

```text
python scripts/harness_trace.py export --input private/run.json --output trace.json
python scripts/harness_trace.py replay --input private/run.json --config private/runtime.json --manifest private/context.json --root private --state private/replay.sqlite --output private/regression.json
```

Export validates the complete event chain, bindings, transitions and redundant
accounting summaries. Its `e156-harness-trace-v1` output contains stable run and
attempt IDs, request/result hashes, attempt histories, status, timing and separate
observed/reserved resources. An allowlist excludes prompts, source text, model
responses, provider identifiers and reviewer names. **Hashes and timing remain
linkable**; review an export before publishing it. This is a local trace format,
not an Inspect log, a signed attestation or a scientific scoring ledger.

Replay requires the private complete report, matching configuration and current
source manifest, plus a new journal path. It returns recorded provider responses
only for the exact ordered request hashes, recomputes tools through the existing
bounded tool path, and compares all operation results, non-wall reservations and
usage, aggregate non-wall accounting and the final prediction.
Unrecorded requests and incomplete transcripts are refused; there is no network
fallback or provider credential requirement. A changed output produces `FAIL`
and CLI exit 1. Both original and replay code profiles are recorded so a code
upgrade can be tested deliberately. Wall timing and wall-time reservation sizes
can differ between replays; other resource accounting must match. Replay output is private and contains a full
run report. Synthetic transcripts test execution behavior, not scientific
accuracy, model quality or comparative performance.

## Optional repeated-result stopping

Set `"progress_policy": {"repeated_result_limit": 3}` in the frozen runtime
configuration to stop after three consecutive identical tool names, arguments
and results. The policy is absent by default. Thresholds must be integers from
2 through 100. Changing a provider call ID does not count as progress; changing
arguments or results does. A route escalation resets the counter so the next
model can review the evidence afresh.

The terminal status is `STALLED`, with no prediction and a hash-bound stop
summary. Resume reconstructs the counter from recorded responses and cached
tool results, without another provider call. Canonical JSON serialization of
tool results keeps subsequent request identities stable after journal reload.
Existing journals remain bound to their original code profile; there is no
automatic migration across this serialization change.

Settled `STALLED`, `BUDGET_STOP`, `REFUSED` and `CANCELLED` runs can also seed
offline regressions. Every recorded operation must be settled; an unresolved
provider or tool outcome is still refused. Empty zero-model-call budget stops
replay without inventing a provider transcript. A wall-time-exhausted budget
stop before the model-call ceiling is refused as incomparable: replay timing
can change even when the code does not. Replay compares the stop summary as
well as status, prediction, tool results and resource accounting. Export validates
stall evidence and exposes only the allowlisted stop reason. This exact-result
heuristic can stop legitimate repeated reads and cannot recognize every kind of
nonprogress; it is an operator-selected policy, not an accuracy guarantee.

See the [source survey and comparison protocol](HARNESS-RESEARCH-2026-11-26.md)
for the native framework comparison and its limited synthetic scope.

## Matched evaluation boundary

The [matched evaluator](MATCHED-HARNESS-EVALUATION.md) accepts independently
assembled run ledgers. This runner's report is supporting evidence, **not a
ready-to-score ledger**. There is deliberately no conversion that invents human
review time, whole-task duration or billed cost.

The separate [E156 development study runner](HARNESS-STUDY-RUNNER.md) now
supplies observed lifecycle boundaries, trace-derived record conversion and
explicit measurement receipts. It preserves unknown human time and billing;
this runtime report alone is still insufficient. That path supports read-only
development execution, not the prospective scientific study.

| Evaluation field | Required evidence |
|---|---|
| Arm and input bindings | Frozen protocol, full model/route policy and verified common task inventory |
| Whole-task wall time | Separate observed start/end measurement, including prespecified restart/overhead treatment |
| Human review seconds/cost | Measured operator record; zero requires evidence that none occurred |
| API cost | Actual billing evidence; otherwise null |
| Tokens and tool calls | Reconciled observed usage; unknown when unresolved reservations remain |
| Attempts/status/prediction | Complete trace including failures, abstentions and earlier route attempts |

`usage.cost_microusd` is conservative price-policy accounting, not billed USD.
`usage.wall_ms` sums operation timing or unresolved reservation ceilings, not
end-to-end duration. Unknown outcomes must not become zero cost, actual token
consumption or omitted failures. Different model/routing policies make a system
comparison; a harness-only comparison requires the same full model policy.

## Verification and disclosure

New tests exercise synthetic tool loops, crash recovery, competing reservations,
budget stops, source/skill/code changes, price/usage validation and tool refusal.
Dedicated Windows/Linux CI runs the execution contracts; Linux Docker CI also
requires the actual containment tests without skips. Existing matched/scoring
and repository gates remain separate requirements. No paid API call, untouched
scientific cohort or superiority result was produced by this implementation.

| Item | Static/configured | Dynamic evidence |
|---|---|---|
| Routes, prices, limits, tool permissions, image digest | Operator policies | Not observed quality or billing |
| Test papers/responses/prices | Explicit synthetic fixtures | Never research results |
| Source/code hashes, trace, provider usage, operation time | Computed during execution | Reservations distinguished from observations |
| Scientific validity, actual invoices, independent judgments | Not inferred | Requires source/provider/human evidence |

Provider contracts: [token counting](https://developers.openai.com/api/docs/guides/token-counting)
and [function calling](https://developers.openai.com/api/docs/guides/function-calling).
Container configuration: [Docker run](https://docs.docker.com/reference/cli/docker/container/run/)
and [Docker proxy injection](https://docs.docker.com/engine/cli/proxy/).
