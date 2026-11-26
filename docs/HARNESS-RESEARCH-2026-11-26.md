# Harness research and comparison plan — 26 November 2026

This review extends E156's existing runtime and recovery benchmark. It is a
selected primary-source survey, not an exhaustive literature review or a claim
that external published scores have been reproduced. New preprints are proposals
and author-reported experiments. Sources were checked on 26 November 2026.

## Source review and decisions

| Primary source | Date/version checked | Useful idea and decision |
|---|---|---|
| [TransHarness](https://arxiv.org/abs/2611.33757v1) | 25 Nov 2026 | Learn interventions from contrasting trajectories and test transfer outside the tuning distribution. Adopt a frozen independent final split; do not import the authors' performance claims. |
| [AHE-Beta](https://arxiv.org/html/2611.24924v1) / [code](https://github.com/Curry09/AHE-Beta) | 18 Nov; repository `43b165fff7b01e01f4fe4697b7597ccd61700727` | Select small changes against verified user requirements and expose actual progress. Use explicit stop evidence and a reviewer-controlled final check. Defer autonomous self-editing and simulated-user scoring. |
| [Harnesses That Improve Themselves](https://arxiv.org/abs/2611.22299v1) | 17 Nov | Modular changes, regression gates and protection of the evaluator. Keep the benchmark outside the execution harness's editable state. |
| [Agency: system optimizations](https://arxiv.org/abs/2611.12122v1) | 9 Nov | Separate harness overhead from model quality and measure actual calls. Record measured operations and time; scripted token counts are not real token efficiency. |
| [Contexture](https://arxiv.org/abs/2611.26980v1) | 20 Nov | Preserve full history separately from model context. E156 already retains its journal. Defer KV-cache-aware eviction: this runner lacks the serving-layer state required to reproduce it. |
| [CTXAgent](https://arxiv.org/abs/2610.34425v1) | 25 Oct | Model-controlled compaction needs retention tests and model-specific evidence. Defer enabling compaction until long-session fact/constraint retention can be tested with actual models. |
| [Trial by Trace](https://arxiv.org/html/2610.32285v1) | 23 Oct | Separate task outcomes, harness contracts and apparatus failures. Adopt case-level outcome/limit/trace records; do not turn an adapter error into a competitor defect. |
| [Doc2Harness](https://arxiv.org/html/2610.20344v1) / [repository](https://github.com/tatra-labs/doc2harness) | 14 Oct; repository `507f3ca3007c7d4bfa48775d011a82a466e8b655` | Scripted model responses can test real harness execution deterministically. Use positive controls and observable calls, tool results, files and terminal outcomes. This new suite is not the official Doc2Harness benchmark. |
| [Harness-Bench](https://arxiv.org/abs/2605.27922v2) | revised 15 Oct | Compare complete configurations under common environments and budgets. Publish adapter choices and exact package versions. |
| [Deep Agents evaluation practice](https://www.langchain.com/blog/how-we-benchmark-deep-agents) | 23 Jul | Test end-to-end artifacts and repeat cases rather than judging final prose alone. Retain every scheduled attempt. |
| [Deep Agents harness engineering](https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering) | 17 Feb | Repeated-work detection and trace diagnosis are useful bounded interventions. Do not adopt coding-specific file-edit heuristics as research correctness checks. |
| [Pydantic DetectLoops](https://pydantic.dev/docs/ai/harness/detect-loops/) | current documentation | Compare canonical calls and their results; repeated calls with changing results can be useful progress. Adopt opt-in exact-result loop stopping and include Pydantic's native detector as a comparator. |
| [Managed Agents architecture](https://www.anthropic.com/research/managed-agents) | 8 Apr | Keep persistent session history, agent loop and sandbox as separate responsibilities. Preserve existing E156 boundaries; no hosted-service replacement is needed. |

A search mirror associated the self-improving-harness title with `2611.22991`.
The [canonical record](https://arxiv.org/abs/2611.22991) is instead
*RagHarnessDebugger*. The verified self-improving-harness identifier is
`2611.22299`; the mirror's title/identifier pairing was rejected.

## Current repositories and executable comparators

GitHub metadata was checked directly, including public MIT licences. Repository
heads are discovery provenance, not claims that the installed release wheel is
identical to the current development branch.

| Repository | Observed head | Executable release selected |
|---|---|---|
| [Deep Agents](https://github.com/langchain-ai/deepagents) | `87f6080d9f3375e0b41aa07a71ce0a8f1027dd9a` | `deepagents==0.7.42`, including resolved LangGraph |
| [Pydantic AI](https://github.com/pydantic/pydantic-ai) | `9ce8f5d35ec9be69d7cbd58a8bff36dd146a1123` | `pydantic-ai-slim==2.75.0`, `pydantic-ai-harness==0.75.0` |

Use native `create_deep_agent`, model-call-limit middleware, and Pydantic `Agent`,
`FunctionModel`, `UsageLimits` and `DetectLoops`. Do not emulate another framework
with an E156 function and label it a competitor. Record the complete installed
wheel lock and adapter source hashes. The older LangGraph recovery ablation
remains a separate result; it is not silently replaced by this experiment.

## Bounded implementation and measurement

1. Add an opt-in exact-result progress guard to the existing runtime. Canonical
   tool name/arguments/result determine repetition; new provider call IDs do not
   hide it. Changing arguments or results remains progress. Stop before another
   model request once the frozen threshold is reached. Preserve reservations,
   evidence and deterministic resumption.
2. Allow settled non-success traces to seed offline regressions. Unresolved or
   missing responses still cannot become a fabricated successful replay.
3. Compare the unchanged policy, guarded E156, Deep Agents and Pydantic with its
   native guard. Use the same synthetic task facts, scripted response sequences,
   evidence tool and six-call ceiling. Compare configurations, not vendor quality.
4. Freeze development/final identities before tuning. An independent reviewer
   chooses final synthetic cases, withholds their contents from the implementer,
   and runs the frozen implementation once for the final result. Repetitions
   quantify execution variability, not independent scientific observations.
5. Publish per-case records, protocol/code/dependency hashes, honest failures and
   exact scope; run independent review, repository gates and hosted CI before merge.

This task reuses `scripts/harness_runtime.py`, `scripts/harness_trace.py`,
`scripts/harness_context.py`, the current execution tests, and the existing
benchmark directory. It creates no new project or scientific analysis pipeline.
Owning runtime and measurement files were verified in this existing repository.

No paid-model budget has been supplied for this extension. The initial executable
comparison uses controlled synthetic responses, not live LLM judgments. It cannot
measure scientific accuracy, model reasoning, real billed cost or leaderboard
superiority. The separate matched scientific study and its source/reviewer gates
remain unchanged.

| Item | Static/configured | Dynamically measured |
|---|---|---|
| Synthetic source facts, response scripts, limits, repetition threshold | Explicit test inputs and policies | Never presented as research findings |
| Package/code/protocol identity | Frozen before final run | Hashes and installed versions checked |
| Model and tool calls, terminal status, source/result hashes, elapsed time | Not authored scores | Recorded from actual framework execution |
| Token counts supplied by scripted models | Synthetic accounting fixtures | Not real token efficiency or invoices |
| Scientific quality, live-model gains and global ranking | Unmeasured | Require separate matched live evaluation |

## Adapter and reproduction details

The common suite gives each runtime the same synthetic source facts, scripted
responses, read-only excerpt implementation and six-call ceilings. Native prompt
formatting, validation, execution and persistence remain different. E156 also
counts input tokens and persists every operation; these count requests are
retained in its trace but are not model generation calls. Deep Agents retains its
default planning/filesystem/subagent middleware and virtual backend; the common
cases do not exercise those extra capabilities. Its native model/tool limit
middleware is active. Pydantic uses `FunctionModel`, native `UsageLimits`, and
`DetectLoops(window=3, repeated_result_threshold=3, action="error")`, with the
other detectors disabled. Neither comparator is replaced by a handwritten loop.

Tool attempts count actual calls into the shared evidence function. Native
validation refusals can happen before that function, and are retained separately
in structured native messages. Repeated identical read-only call IDs may be
cached by E156 and re-executed by another framework; both are permitted, with
actual counts reported. The grader checks the original typed request, expected
excerpt bytes and source hash; an invented successful result cannot pass.

Each observation runs in a fresh subprocess and directory. Environment variables
are allowlisted to remove provider credentials and tracing, and socket
connections are denied in Python. Windows asyncio's local wake-up socket pair is
created before that denial. This is a testing guard, not OS containment. Native
imports and source fixture creation precede the measured interval; agent setup,
execution, persistence and revalidation are included. Timing is descriptive only.

On Windows x64 with CPython 3.13, create a fresh environment and run:

```powershell
python -m venv .venv-benchmark
.venv-benchmark/Scripts/python -m pip install --only-binary=:all: --require-hashes -r benchmarks/requirements-execution-windows.lock
.venv-benchmark/Scripts/python -m scripts.harness_execution_benchmark --cases benchmarks/harness-execution-development.json --split development --output development-local.json
```

Use new output names: the runner refuses to overwrite results and flushes an
`.attempts.jsonl` record after every observation. Dependency wheels are specific
to this Python/platform combination. Code/protocol/case byte hashes are checked
before and after a suite; line-ending changes can change those hashes. CI reruns
only development cases. Once published, final cases are ordinary regression
inputs for future work and cannot be claimed as unseen again.

Before and after execution, the runner verifies every locked distribution version
and every installed file covered by its wheel RECORD hash. It records the full
inventory and RECORD digests, including explicitly identified environment
bootstrap tools. Unlocked runtime distributions, altered covered files or
mid-run identity changes refuse the aggregate; partial attempts remain retained.
Tool successes are tied to the specific triggering model call, so native argument
coercion cannot borrow a later valid request. Provider-failure cases require that
no model execution occurs after the first scripted timeout. These are the common
suite's strict contracts, not claims that all frameworks promise identical typing
or retry defaults.
