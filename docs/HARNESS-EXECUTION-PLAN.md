# Harness execution upgrade

Status: implementation and independent review completed, 12 November 2026;
final remote verification tracked in draft PR 96. See the [usage guide](HARNESS-EXECUTION.md).
HTML was already checked; this work changes the research harness, not the UI.

## Ingredients verified and reuse

The starter already contains `synthesis_matched_eval.py`, source replay and
checklist validators, SQLite review/decision runners, `component_source.linked`,
`bounded_native.run`, BM25 `recall.py`, and shared CI. Reuse these contracts.
The earlier portfolio recon in RESEARCH-HARNESS-ROADMAP.md identified Evidence
Board, Evidence Half-Life, evidence-inference, evidence-tribunal and
EvidenceBridgeFHIR; this implementation extends the starter, not those projects.
No new portfolio repository, HTML change or lifecycle promotion is needed.

## Bounded components

1. Execution: a real OpenAI Responses adapter with exact input-token preflight,
   bounded function-tool loop, frozen model/routing/price policies, automatic
   usage and trace records, and budget reservation before calls. Default no paid
   calls. Price-policy estimates remain distinct from actual billed cost.
2. Reliability: durable SQLite operation journal, conservative in-flight recovery,
   dependency revalidation, and isolated optional Docker workers. An ambiguous
   interrupted request never repeats automatically. No local shell fallback.
3. Context and improvement: typed artifact dependency graph, pinned skills and
   their tool permissions, bounded excerpts, expiration/change invalidation,
   deterministic task routing, and a quiet local change-monitoring command.
   Model/skill policy changes require a new frozen run and development evaluation.

Tests are written before implementation. Independent reviewer reruns and remote
CI follow each integrated milestone. Existing protected tests are unchanged.
Real model quality, billing and independent research adjudication remain external
prerequisites; software fixtures never count as scientific study results.

## Acceptance checks

- Every generation request has a committed reservation; validated responses and
  ambiguous outcomes are recorded. Exhausted budgets prevent a call. Interrupted
  calls retain their reservation; a response lost in transport cannot be recovered.
- Restart reuses committed outputs and revalidates source/config/code bytes.
- Unknown outcomes, malformed usage, changed context and unauthorized tools stop
  the run, preserving evidence and costs already incurred.
- Workers cannot write source mounts or use the host network/credentials. A real
  Linux Docker CI test exercises containment; missing Docker refuses execution.
- Changes against a frozen source graph invalidate descendants; unaffected branches stay current;
  repeated monitoring emits no duplicate alert for unchanged evidence state.
- The worker receives only the selected public evidence snapshot. Operators must
  exclude held-out labels and private judgments from that selection. The provider
  adapter alone reads its API key; no automatic file classification is claimed.

## Static versus dynamic disclosure

| Item | Static / configured | Dynamic evidence |
|---|---|---|
| Schemas, routes, tool policies, budgets, price ceilings | Operator-frozen inputs | Not performance measurements |
| Synthetic responses, prices, sources and labels in tests | Explicit fixtures | Never real research/billing |
| Source and code hashes, operation status, elapsed time, API token usage | Derived at runtime | Recorded observations |
| Actual billed USD, independent judgments, scientific benefit | Not inferred from tokens/tests | Requires provider/human evidence |

Provider implementation follows official [token counting](https://developers.openai.com/api/docs/guides/token-counting)
and [function calling](https://developers.openai.com/api/docs/guides/function-calling)
contracts fetched on 12 November 2026. No API key provisioning tool is available;
the adapter reads its key from the process environment only when explicitly run.
