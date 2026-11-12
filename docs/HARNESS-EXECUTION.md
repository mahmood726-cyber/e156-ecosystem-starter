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

Invalidation operates against the frozen graph. Updating a source hash in a new
manifest can make unchanged derived files appear CURRENT: that means byte
consistency, not that their work was repeated. Recompute/review dependent
extractions, analyses, claims and checklist judgments before adopting that graph.
Human Pass remains an independent gate.

## Matched evaluation boundary

The [matched evaluator](MATCHED-HARNESS-EVALUATION.md) accepts independently
assembled run ledgers. This runner's report is supporting evidence, **not a
ready-to-score ledger**. There is deliberately no conversion that invents human
review time, whole-task duration or billed cost.

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
