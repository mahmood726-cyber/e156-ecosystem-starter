# Research harness comparison and next upgrades

Checked 2026-11-11. The strongest next step is to connect the ecosystem's evidence
checks to durable review orchestration and independent human adjudication. The
local experiment supports that engineering direction. It does not establish
superior research accuracy over competing systems.

The reference set covers agent runtimes, evaluation infrastructure and systematic
review workflows. It is not an ordered list of the world's best products. Public
documentation establishes features; only the local experiment below establishes
measured behavior. Commercial and hosted services were not executed or purchased.

## Reference systems and observed gaps

| Reference | Documented capability | Implication for this ecosystem | Evidence type |
|---|---|---|---|
| [OpenAI Agents API / Agents SDK](https://developers.openai.com/api/docs/guides/agents) | Managed Codex execution and saved sessions; application-controlled tools, handoffs and state in the SDK | Keep domain evidence checks independent of model/runtime; add explicit session/artifact adapters | Current official docs; no hosted run |
| [Claude Agent SDK harness practice](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) | Incremental tasks, durable progress artifacts and feature checks across context windows | Existing PROGRESS/Git checkpoints help; add machine-readable stage state and recovery checks | Engineering account, 2025-11-26; not a new 2026 release |
| [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) / [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Planning, filesystem context, subagents, memory; thread checkpoints and cross-thread stores | Prototype optional orchestration around Synthesis checks; revalidate evidence at resume | Docs plus local LangGraph strategy experiment; Deep Agents model loop not run |
| [Microsoft Copilot harness](https://blogs.microsoft.com/blog/2026/10/28/introducing-the-microsoft-copilot-harness-unlocking-the-potential-of-truly-multi-model-agentic-work/) | Multi-model managed execution through Foundry, with MCP, skills and plugins | Keep research records portable; measure task-specific routing before adopting it | Vendor announcement, 2026-10-28; performance claims not reproduced |
| [Inspect](https://inspect.aisi.org.uk/eval-logs.html) | Sample/error logs, retries using stable IDs, score history and provenance | Retain every attempted case, failure, retry, token record and human correction in exportable traces | Primary docs; not executed in this continuation |
| [ASReview](https://asreview.readthedocs.io/en/stable/lab/simulation_overview.html) / SYNERGY | Screening simulations against labelled reviews and workload metrics | Reuse review-level evaluation when screening is integrated; replay tests cannot measure inclusion recall | Primary docs; no screening experiment performed |
| [CoLRev](https://colrev-environment.github.io/colrev/) | Review stages, data/process standards, Git collaboration, validate and undo | Adopt an interoperable review record and optional adapters | Primary docs; no local CoLRev run |
| [Elicit systematic reviews](https://support.elicit.com/en/articles/14759154-systematic-reviews-in-elicit) | Guided search, abstract/full-text screening, extraction and reporting around the review question | Connect existing components into a coherent reviewer-facing workflow | Vendor help docs; time-saving/accuracy claims not adopted |
| [Laser AI and Nested Knowledge in Cochrane's platform study](https://www.cochrane.org/about-us/news/cochrane-announces-selected-ai-tools-innovative-platform-study) | Selected platforms evaluated within reviews under RAISE-aligned selection | Use review-specific validation and recorded oversight; selection is explicitly not endorsement | Cochrane announcement, 2026-03-17; outcomes not inferred |
| [EviStreams](https://arxiv.org/abs/2609.27418) | Typed extraction fields, supporting passages, reviewer-blinded dual review and adjudication | Prioritize field specification and recorded disagreement resolution | Authors' September 2026 system paper; results not reproduced |

Local strengths are evidence-byte binding, explicit refusal, bounded source-linked
replay, component activation checks and public-key trust separated from scientific
validity. Evidence is linked from [benchmark.md](../benchmark.md) and
[the roadmap](RESEARCH-HARNESS-ROADMAP.md). Outstanding gaps are full review
orchestration, adjudicated trial/cohort/outcome relations, generic statistical
replay, model cost traces and held-out research performance. These are local
implementation/evidence gaps, not measured scores against complete competitors.

## Recent developments affecting the design

- **Managed execution is expanding.** OpenAI's
  [2026-10-30 changelog](https://developers.openai.com/api/docs/changelog) documents
  session-tool updates, background compaction and optional automatic review.
  Background compaction may increase token usage. Its
  [review guide](https://developers.openai.com/api/docs/guides/agents-api/sessions/approvals)
  retains network restrictions and bills review separately. Keep research policy
  and usage records explicit; runtime permission review is not scientific review.
- **Multi-model orchestration is becoming a managed product surface.** Microsoft's
  October announcement above motivates portable adapters, but supplies no
  research-specific accuracy measurement for E156. Compare routing on frozen
  tasks with identical budgets and graders before selecting it.
- **Evaluator design needs calibration and restraint.** Anthropic's
  [2026-03-24 harness study](https://www.anthropic.com/research/harness-design-long-running-apps)
  separates planning, generation and evaluation, while describing reduced
  orchestration overhead as models improve. Its
  [evaluation guidance](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
  separates tasks, trials, graders and actual outcomes. Keep independent review
  where it catches failures; agent count is not a progress metric.
- **Typed fields and reviewer control matter for research.** EviStreams' September
  paper is a recent concrete example. That workflow is directly relevant to the
  next research milestone. Its reported comparative findings do not transfer to
  this repository without independent evaluation.

This is a selected primary-source update, not an exhaustive survey of every AI
announcement. No model was replaced, no paid request was made, and no vendor
benchmark became our own result.

## Measured recovery experiment

The [protocol](../benchmarks/harness-recovery-protocol.json) was written before
execution and is hash-bound in the [measurement](../benchmarks/recovery/development-windows.json).
The [runner](../benchmarks/harness_recovery.py) uses the SAME existing E156 replay
verifier in three strategies. LangGraph 1.2.20 and SQLite checkpointer 3.1.3 run in
a separate environment. Exact Windows wheels are recorded in the
[dependency lock](../benchmarks/requirements-recovery-windows.lock).

Each strategy audits each of two existing OA development bundles, exits its first
Python process, then resumes in a new process. Between processes, the runner
leaves files unchanged or changes source/result bytes in disposable copies.
There are no model calls. Workers install application guards for socket
connect/create_connection and source retrieval; this is not OS network isolation.
The final step emits a local receipt, without publishing externally or clearing HOLD.

| Strategy | Unchanged completion | Changed bytes refused | Verifier calls before + after restart, unchanged case |
|---|---:|---:|---:|
| Direct E156 replay, re-executed | 2/2 | 4/4 | 1 + 1 |
| LangGraph checkpoint, cached receipt only | 2/2 | 0/4 | 1 + 0 |
| LangGraph checkpoint, E156 revalidation at resume | 2/2 | 4/4 | 1 + 1 |

All 18 cases are retained, including four stale receipt emissions. The cached
variant deliberately omits application revalidation. **This is not a LangGraph
vulnerability or a scientific product ranking.** It is an integration ablation
using the same checker. Checkpoints preserve workflow state but cannot replace
the evidence check where a current receipt is emitted. Revalidated resumption
preserves unchanged analytical payloads and refuses changed bytes.

The cached variant saves a verifier call by omitting a necessary check; no safe
speedup is claimed. Timings include interpreter startup and are diagnostic only.
Two development examples on one Windows environment cannot establish general
performance. This is controlled pause/restart, not an abrupt kill, corrupted-disk
or physical power-loss experiment. Scientific accuracy remains unmeasured.

An independent reviewer reproduced all 18 outcomes and checked distinct worker
processes, persisted SQLite state, call counts and infrastructure-error accounting.
That review also identified the original network-isolation wording as too broad;
the final runner/record now describe the narrower application guards explicitly.

Reproduce in a disposable Windows Python 3.13 environment from the repository root:

```console
python -m pip install --only-binary=:all: --require-hashes -r benchmarks/requirements-recovery-windows.lock
python benchmarks/harness_recovery.py --output recovery-new.json
```

The output must be new. Integrity failures remain in the report; exit 2 means
execution was incomplete, not an acceptable refusal. This lock covers Windows
x64; Linux benchmark reproduction is not asserted from it.

## Prioritized next milestones

| Priority | Concrete work | Acceptance evidence |
|---|---|---|
| 1 | Persistent review runner around existing checks with protocol/source/code digests | New-process recovery; no duplicate external actions; changed dependencies invalidate descendants; missing/corrupt state refuses; separate abrupt-interruption tests |
| 2 | Typed cohort/outcome decisions and independent adjudication | Source locations and reviewer decisions for every accepted relation; disagreements stay HOLD; source changes reopen decisions; no identity inference from matching counts |
| 3 | Shared evaluation trace and stable case IDs, compatible with Inspect-style records | Every attempt/error/retry, model/tool version, usage record and human correction accounted for; no fabricated costs |
| 4 | Independently adjudicated OA scientific benchmark | Freeze review/trial-family splits and corpus hashes before tuning; matched inputs/budgets; report screening recall, extraction errors, effect/interval deviations, abstentions and review-level uncertainty; retain nulls |
| 5 | Windows installation isolation and CoLRev/ASReview interoperability | Disposable Windows full-installer contract; round-trip records/labels without losing provenance; no unsafe legacy tests against the personal home |

Implement milestone 1 on a narrow review stage, then adjudication and scientific
evaluation. A new vector database or larger agent topology is not justified by
this experiment. This priority order is engineering judgment grounded in the
observations, not proof that alternative designs cannot work.

## Static versus dynamic disclosure

| Material | Origin | Scope |
|---|---|---|
| Reference selection/priorities | Authored judgment | Plan, not external ranking |
| Capabilities/dates | Primary documentation checked 2026-11-11 | Documented features; hosted performance unmeasured |
| Cases/mutations | Authored development protocol | Fixed challenge; no held-out split |
| Outcomes/calls/hashes/versions | Actual subprocess execution | Declared local strategies |
| OA bundles | Existing attributed bytes | Bounded replay, not a completed review |
| Worldwide superiority/clinical accuracy/production durability | Not measured | No such claim supported |
