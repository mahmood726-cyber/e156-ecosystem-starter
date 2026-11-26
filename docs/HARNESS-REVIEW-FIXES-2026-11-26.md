# Harness benchmark and recovery repairs - 26 November 2026

The follow-up review identified three reproducible defects. This maintenance
change fixes them in the starter kit without changing scientific release status.

1. **Unexpected exceptions could earn a refusal score.** The benchmark now
   records witnessed refusal causes bound to the actual source/tool request.
   Unexpected callback failures remain apparatus `ERROR` in the denominator;
   contradictory success predictions and missing causes fail grading. Production
   journals still retain unknown outcomes as `UNRESOLVED`.
2. **An initialization crash could leave an unusable journal.** SQLite now
   commits and validates `READY` in a short private sibling file, closes it, then
   publishes exclusively using a hard link. Real subprocess exits before READY,
   before/after commit and before/after publication verify study abort and frozen
   export retain every planned slot. Existing corrupt journals and interrupted
   staging remain preserved. This does not provide automatic adoption, retries
   of unknown effects, or power-loss guarantees.
3. **Recovery comparison anchors lagged the OA fixtures.** The benchmark now
   uses the explicit anchors already reviewed in the source-replay workflow at
   commit `ded4e352e22f87c1e5c7b7d45fd93f0c1e05fa75`, after full source-backed
   replay verification. They are not recomputed from arbitrary current files.
   The CI job exercises every scenario and requires exact resume outcomes and
   verifier-call counts. Completed attempts are flushed and fsynced separately
   so interruption of a later case cannot erase earlier observations.

Independent AI review caught and corrected an additional Windows path-length
regression in the first staging implementation. The final staging basename has
the same length as `run.sqlite`; a Windows regression exercises a 250-character
journal path and its 258-character rollback sidecar. This does not extend the
study runner's general Windows path limits or replace human scientific review.

## Recovery evidence

| Run / strategy | Integrity contracts satisfied | Attempted resumes |
|---|---:|---:|
| Before repair, all strategies | 0/18 | 0/18 |
| After repair, direct replay | 6/6 | 6/6 |
| After repair, deliberately cached LangGraph | 2/6 | 6/6 |
| After repair, revalidated LangGraph | 6/6 | 6/6 |

The four cached-strategy failures are the expected negative controls: that
integration intentionally omits revalidation after source/result mutation.
They are not a LangGraph vulnerability. Both OA bundles are known development
fixtures and every strategy uses the same E156 source checker. No scientific
accuracy, live-model quality, cost, speed, or worldwide ranking is established.

Preserved reports and their exact SHA-256 identities:

- [Failed run](../benchmarks/recovery/development-stale-anchors-2026-11-26.json):
  `90ecdb9c9463e94090efa4a8c9ce5bb8ef29a5d327047d51a97a1a9164aafc7a`.
- [Repaired run](../benchmarks/recovery/development-repaired-2026-11-26.json):
  `ef31794183f376b5fb5cd79fd8b68d7227b0f4607846a0c5fb5511789a720edb`.
- [Per-case attempt log](../benchmarks/recovery/development-repaired-2026-11-26.json.attempts.jsonl):
  `bff7b6d482b7be8c67bd417847b26c4b2f61870a8d4760c43bb1c54cd9190848`.

The original November 11 measurement and consumed final execution campaign are
unchanged. Post-repair execution checks use the known development cases;
fault-injection tests exercise the newly discovered scoring failure.

## Fixed inputs and measured behavior

| Component | Static / configured | Dynamically checked |
|---|---|---|
| Replay comparison | Explicit reviewed anchors, two known fixtures, three strategies and scenarios | Full source-backed recomputation and fresh-process resume; changed bytes refuse |
| Execution comparison | Scripted synthetic responses and fixed mechanism contracts | Actual E156, Deep Agents and Pydantic execution; trace-bound refusal evidence and injected unexpected faults |
| Journal initialization | Exclusive publication and no unknown-effect retry | Actual process exits, target races, sidecar refusal, retained study denominators and Windows path budget |
| Interpretation | Development engineering evaluation only | No live model calls, independent scientific adjudication or held-out scientific result |
