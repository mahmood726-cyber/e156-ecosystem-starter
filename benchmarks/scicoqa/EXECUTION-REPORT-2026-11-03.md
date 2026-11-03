# SciCoQA versus Synthesis: execution report

3 November 2026. Continued from merged PRs #73 and #74, base commit `845ebd52c26f75ffef5d7926c5dbe6cb28953be1`.

**The paired LLM experiment has not run.** Source retrieval and implementation verification were performed. This workspace has no configured model API key, inference endpoint, local model CLI, or installed local LLM runtime. No model identity, revision or inference settings have been invented. No independent human adjudication was performed. No comparative accuracy or superiority claim is supported.

## Observed source coverage

| Stratum | Reference discrepancy records | Paper source URLs | PDFs retrieved | Repository revisions | Full code archives | Source-only snapshots |
|---|---:|---:|---:|---:|---:|---:|
| real | 92 | 73 | 61 | 74 | 74 | 0 |
| synthetic | 543 | 204 | 204 | 204 | 203 | 1 |

Across strata there are 552 distinct source-URL assets, including 276 paper URLs and 276 repository revisions. These overlap across strata; they are not independent evaluation cases. Retrieved 264 PDFs and 275 full repository archives. Hashes, URLs, timestamps and explicit failures are in [the retrieval receipts](source-receipts-2026-11-03.jsonl).

The `armiro/COVID-CXNet` full archive exceeded the 256 MiB limit. Its separately retrieved source-only snapshot contains 22 selected source/text files, including notebooks, at commit `3ade488b3828705706fc5f58c0667421d8b04a01`. Every selected file matches the Git blob SHA from the complete pinned repository tree. Binary weights, images and other nonselected files are excluded; this is not a full repository archive. See [the file-level supplement](source-only-supplement-2026-11-03.json). Other unresolved source failures, if any, remain in the retrieval receipts and machine-readable summary.

Both complete v1.1 benchmark JSONL files were retrieved from [UKPLab/SciCoQA at commit 463162906459be508ed4a2294fcaede9fa072036](https://github.com/UKPLab/scicoqa/tree/463162906459be508ed4a2294fcaede9fa072036). Their SHA-256 values are:

| File | SHA-256 |
|---|---|
| Real v1.1 | `78e1138f0b034ae8b52d5a60806c763f9ad2b1e1cdee55546d6db0721f195dc7` |
| Synthetic v1.1 | `7fccd1267c09ea8dc944cee996341e57931dcddcf086c600c1f8bc8c0f94fbdb` |

The full pinned SciCoQA source archive was retrieved (SHA-256 `2550cfa21bc4414a9e551a2fe35bd83f9015d0b356b62b0c85fb32648c63cb0b`). The [SciCoQA paper](https://aclanthology.org/2026.acl-long.1795/) PDF was retrieved (SHA-256 `d67fcfaf9247fe931a113658c93a8d223aeadc8f3486a3859a9e24c89e01d00e`). The source archive includes historical upstream inference outputs; these have not been used as results of this experiment. Corpus PDFs, repository bytes, benchmark answers and historical outputs are not committed to this public repository.

## Scientific results: explicitly unmeasured

| Scoring basis | Stratum | Prompt | Recall | Precision | False positives | Abstentions | Reviewer minutes |
|---|---|---|---|---|---|---|---|
| Automated judge (not run) | real | Original SciCoQA | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Automated judge (not run) | real | Synthesis | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Automated judge (not run) | synthetic | Original SciCoQA | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Automated judge (not run) | synthetic | Synthesis | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Independent humans (not performed) | real | Original SciCoQA | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Independent humans (not performed) | real | Synthesis | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Independent humans (not performed) | synthetic | Original SciCoQA | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |
| Independent humans (not performed) | synthetic | Synthesis | Unmeasured | Unmeasured | Unmeasured | Unmeasured | Unmeasured |

Actual paired model calls: **0**. Actual automated judge calls: **0**. Actual independent human reviews: **0**. This does not mean zero false positives or zero abstentions: none of those outcomes has been observed. Unit-test mock subprocess responses are implementation fixtures, never benchmark runs. No precision or false-alert estimate can be inferred from an error-enriched reference inventory alone.

## Implementation repaired and verified

- Human-adjudicated summaries now report real, synthetic and other strata separately in `by_split`; the legacy pooled aggregate is secondary. Every prepared case requires a frozen paper-family identifier.
- Prose before or after a YAML result is rejected as a format abstention, rather than accepted as a completed zero-finding response. Conservative unsupported YAML is also an explicit format abstention. No semantic refusal detector is claimed.
- Timeouts retain partial stdout and stderr, raw-response hashes and latency. Every completed call is checkpointed immediately; execution metadata states that provider settings remain caller-declared.
- Retrieval checks exact dataset bytes, versioned arXiv PDF editions, payload type, repository archive root, byte limits and a hard external-process timeout. Empty receipt files can be resumed. Cached-file integrity failures remain failures.
- Targeted tests reproduce the above failures using artificial fixtures. The full Python suite passed **1,003 tests and 66 subtests**; the two Bash suites passed **34 and 18 tests**. GitHub checks must pass on the final PR head before merge. These checks establish software behavior, not scientific detection performance.

## Required continuation

1. Configure one callable LLM and freeze its actual model revision and all supported inference settings for both arms. The current CLI adapter passes identical frozen prompts to a user-specified command but cannot authenticate the deployed model or settings. Do not silently substitute a different model.
2. Extract and quality-check label-free paper/code contexts. Preserve exact versions, paper families and the synthetic changes from the benchmark; synthetic changes have been downloaded but have not been applied to frozen inference contexts. Resolve any conflicting mutations explicitly. One real paper has two code snapshots: retain both rather than silently selecting the first.
3. Freeze a common source budget that fits both rendered prompts. Use the original upstream `discrepancy_generation` literal and the existing task-adapted Synthesis prompt unchanged. Preserve full source hashes and the same source bytes in both arms; do not clip code separately by prompt length.
4. Run both arms and retain no-findings, abstentions, failures, response bytes, timing and provider receipts. Randomize or counterbalance arm order in the configured execution plan; the current simple CLI uses baseline then Synthesis and should not be presented as randomized.
5. Run the pre-specified identical automated judge as a secondary analysis. Independently recruit two masked scientific reviewers, resolving disagreements with a third. Review all actionable flags and the reference inventory; retain unknowns and measure actual review time. An automated judge is not human adjudication. The existing `score` command accepts caller-supplied human attestations and does not authenticate people.
6. Report per-stratum recall, precision, false positives, abstentions and burden with their denominators. Independently verified clean controls are still required for clean-case false-alert rates. No family-cluster confidence interval or new prospective held-out validation is supplied here. Do not promote the prompt on this potentially contaminated public benchmark.

## Reproduction and evidence boundary

Retrieve the source tree at the pinned commit, then run from this repository root (Python 3.11+ and `curl` required):

```bash
python scripts/scicoqa_retrieve_sources.py \
  --dataset-dir /path/to/pinned-scicoqa/data \
  --output /path/to/new-source-cache \
  --workers 10 --timeout 60 --max-bytes 268435456
python -m pytest tests/ -q
```

Do not run two collectors concurrently against one output directory. The initial collection used a 64 MiB cap and was interrupted; final receipts use the bounded 256 MiB collection and preserve validated earlier successes. An oversized repository was recovered separately through the complete pinned Git tree and exact-blob text downloads. The general collector does not automate that source-only fallback.

| Static implementation/design | Dynamically observed evidence |
|---|---|
| Two existing prompt templates, schemas, source allowlists, size limits, parser policy, per-stratum accounting | Dataset bytes, source download successes/failures and hashes, Git blob validation, actual test output |
| Proposed LLM/automated-judge/human-review workflow | No new paired model generations, automated judgments, human judgments or scientific accuracy estimates |

The machine-readable [execution summary](execution-summary-2026-11-03.json) uses JSON null for unmeasured scientific outcomes. Repository CI and review are software checks, not independent source adjudication. No authors or journals were contacted.
