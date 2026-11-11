# Research harness benchmark and comparison

Checked 2026-11-11. This replaces the April capability scorecard: its weighted
rankings and niche-superiority claims were not head-to-head measurements.
Historical text remains in Git history. There is currently no evidence here
that the ecosystem is the best research harness worldwide.

The upgrade plan is [RESEARCH-HARNESS-ROADMAP.md](docs/RESEARCH-HARNESS-ROADMAP.md).
The useful target is a reproducible, source-grounded review with accountable
human decisions and measurable failures, at a documented cost.

## External comparison: documented capabilities, not measured rankings

All sources below are primary project documentation or originating organisations,
consulted on the date above. Their tools were not run in this session. A feature
listed here is not a claim of superior accuracy, and an omitted feature is not
proof of absence.

| Reference | Documented practice to learn from | Implication for this ecosystem |
|---|---|---|
| [ASReview simulation](https://asreview.readthedocs.io/en/stable/lab/simulation_overview.html) and [SYNERGY](https://github.com/asreview/synergy-dataset) | Replay screening against labelled review datasets; compare workload and screening behavior | Evaluate screening on independent review-level splits, report missed inclusions, and use appropriate OA/licensed inputs |
| [CoLRev](https://colrev-environment.github.io/colrev/) | Shared review data/process standards, Git collaboration, validate/undo operations | Interoperate with an established review state model; preserve decisions and reversibility |
| [LangGraph memory](https://docs.langchain.com/oss/python/concepts/memory) | Thread-scoped checkpoints and separately namespaced long-term memory | Explicit project boundaries and resumable state must precede richer retrieval |
| [Inspect evaluation logs](https://inspect.aisi.org.uk/eval-logs.html) | Task/sample logs, failures, model usage and retry records | Keep every attempted case, preserve failure denominators, bind outcomes to the exact configuration |
| [Anthropic agent evaluations](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) | Distinguishes tasks, trials, graders, transcripts and actual outcomes | Check generated artifacts and state, rather than accepting the agent's completion claim |
| [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) and [Process Run Crate](https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate/) | Records execution provenance linking software, actions, inputs and outputs | Export a validated interoperable research bundle; cryptographic identity alone is insufficient |
| [Cochrane/Campbell/JBI/CEE AI position](https://doi.org/10.1002/14651858.ED000178) and [Cochrane platform study](https://www.cochrane.org/about-us/news/cochrane-announces-selected-ai-tools-innovative-platform-study) | Human responsibility, transparent disclosure and contextual evaluation of AI tools | Require recorded oversight/adjudication and domain-specific validation; do not claim blanket RAISE conformance |

The inference from this comparison is an engineering priority: strengthen the
connections between existing components before adding another model or database.
It is not an experimental finding about which platform performs best.

## Measured local baseline

Starter source: `677035bb3a4cabf7dc7480340be5323a72617e96`. Run results must be
read with their scope; they cannot be combined into a single quality percentage.

| Probe | Observed result | Exact interpretation |
|---|---|---|
| Memory contract controls | [baseline.json](benchmarks/memory/baseline.json): 5/11 satisfied | Synthetic development controls of scoping, corpus readability and context identity; deliberately includes contracts introduced by this upgrade |
| Installed Overmind gold fixtures (`a8131b0`) | 43/43 stored fixtures passed; 41 pooled fixtures; maximum reported log-estimate deviation 0.00003234215813041619 | Actual `run_gold_benchmark()` execution against its committed references. Not a new independent source audit, not the starter-pinned Overmind revision, and not clinical accuracy |
| Starter Python tests on Windows | Initial capped run: 10 passed, 5 failed; Bash was absent from PATH | Environment failure before implementation. A Git Bash retry is recorded in the verification notes; unavailable prerequisites are not counted as passes |
| RapidMeta install provenance | Source inspection: default `v1.1.0`, checkout failure swallowed in Bash | Confirmed code path requiring M2 repair; no claim that a real install was validated |

The first three rows are local observations; the fourth is a source review.
No private memory was read for the benchmark, and no paid AI calls were made.
The Overmind probe called its numerical function directly to avoid starting a
portfolio scan or changing the user's existing benchmark artifact.

## Reproduce the memory controls

```console
python scripts/benchmark-memory.py
python -m pytest tests/test_memory_contract.py tests/test_recall.py -q
```

The evaluator creates isolated temporary Markdown stores. It runs the real
memory module and emits per-case outcomes, SHA-256 of the evaluated module,
SHA-256 of the evaluator, and explicit `held_out: false` and
`scientific_accuracy_measured: false` labels. Exit 0 requires every case to pass;
exit 1 means a behavioral failure; exit 2 means the evaluator could not run.
An implementation crash fails a case; it does not count as a successful refusal.

`--implementation` accepts a trusted local copy of `recall.py`, allowing replay
of the original committed version without resetting the checkout. `--output`
writes the report. Preserve the baseline rather than overwriting it. Source
hashes refer to actual local bytes, including newline encoding.

## Scientific benchmark protocol for later milestones

Freeze the task definition, reference adjudication, split rule, corpus hashes,
method configuration and budgets before optimisation. Split by review and
trial family to avoid related-paper leakage. Keep development controls separate
from the final held-out set; there is no held-out scientific evaluation in M1.

| Task | Baseline and measurements | Refusal or limitation to expose |
|---|---|---|
| Memory/recovery | Explicit project namespace, relevant-context recall, stale-source rate, restart replay | Cross-project leakage, unresolved source, incomplete read; BM25 score is not truth |
| Search/screening | ASReview/SYNERGY where OA-compatible; recall and work saved at fixed recall | Coverage is limited by available corpora and OA policy; errors and abstentions remain in denominators |
| Extraction/identity | Independently checked source fields and trial families; field accuracy, exact locator, correction sensitivity | Missing identifiers, shared controls, publication/trial confusion, survival/count substitution |
| Statistical synthesis | Fixed estimand and estimator against independent R/metafor output; estimates, SEs, intervals, heterogeneity | No best-of-many configuration search masquerading as fixed-pipeline reproduction |
| Integrity review | Existing paired SciCoQA and blinded Synthesis scorers; false alerts, missed errors, abstention | Development error examples do not estimate real-world sensitivity |
| End-to-end review | Replayable OA case with human adjudication; completion, unresolved decisions, human correction time, real token/cost logs | An attractive dashboard, checksum or passing unit tests cannot certify a review |

Estimate uncertainty using the review as the clustering unit. Report separate
dimensions and paired differences on identical tasks; do not fabricate a global
leaderboard by scoring competitors on features they were not intended to offer.

## Static versus dynamic disclosure

| Item | Type | Evidence boundary |
|---|---|---|
| Comparator selection and proposed acceptance criteria | Static author judgement | Priorities, not empirical superiority |
| External feature descriptions | Primary documentation | Not local competitor measurements |
| Synthetic memory controls and expected results | Static development fixtures | Engineering regression coverage only |
| Memory case outcomes and hashes | Dynamically executed | Exact implementation and evaluator bytes |
| Overmind gold result | Dynamically executed stored-reference comparison | No new clinical/source adjudication |
| Future held-out accuracy and relative cost | Unmeasured | No headline claim is permitted yet |
