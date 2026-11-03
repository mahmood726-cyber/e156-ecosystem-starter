# SciCoQA × Synthesis: paper–code discrepancy comparison

**3 November 2026 · Design + offline preparation/scoring code only · NO head-to-head inference or scientific adjudication performed**

This experimental comparison is a *public external benchmark study*, not a claim that Synthesis is better than SciCoQA or the baseline LLM. It does not replace Synthesis v1.2, the candidate [v1.3 method](SYNTHESIS-v1.3-CANDIDATE.md), or the separate [blinded prospective validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md). The existing protected/frozen Simo v0.10 cohort and historical correspondence must remain unchanged. No automatic author or journal contact is permitted.

## Primary sources and versions

- Baumgärtner T, Gurevych I. *SciCoQA: Quality Assurance for Scientific Paper–Code Alignment*. ACL 2026, pp. 38740–38770, DOI [10.18653/v1/2026.acl-long.1795](https://aclanthology.org/2026.acl-long.1795/).
- [Upstream SciCoQA code](https://github.com/UKPLab/scicoqa) at inspected `main` commit **`463162906459be508ed4a2294fcaede9fa072036`** (3 Nov 2026); use the exact [`config/prompts.yaml`](https://github.com/UKPLab/scicoqa/blob/463162906459be508ed4a2294fcaede9fa072036/config/prompts.yaml) `discrepancy_generation` literal as the plain-prompt comparator. The baseline must **not** be paraphrased or replaced with a newly invented "plain prompt."
- [SciCoQA dataset v1.1](https://huggingface.co/datasets/UKPLab/scicoqa): **92 real and 543 synthetic reference discrepancies** (635 in total); the separate **pooled** slice combines 103 annotated model predictions and 26 real discrepancies on 20 papers. These are not 635 independently sampled *error-free and error-containing papers*. Pin the dataset revision/content hashes at study registration; reference IDs often share a paper.
- [Project page and reported evaluation](https://ukplab.github.io/scicoqa/). SciCoQA evaluates **22 models**; its reported best **real discrepancy recall is 46.7%**, for Gemini 3.1 Pro and GPT-5 Mini under the paper's conditions. That is not Synthesis recall. The reported precision on the selected pooled subset (e.g. 88.0% GPT-5, 94.6% Gemini 2.5 Pro) is not a field-wide false-alarm rate.
- This repository's method was inspected on `main` at **`c53d381b959e881506861636a94915a220534dde`**. The Synthesis v1.3 implementation has synthetic software regression checks; no SciCoQA model comparison or independent clinical-source detection evaluation was observed.

## What the systems actually cover

| Axis | SciCoQA | Synthesis v1.2 / v1.3 development candidate | Comparable here? |
|---|---|---|---|
| Target | Meaningful semantic conflict between scientific paper and code | Numerical, source, protocol, figure, evidence, and paper–code integrity | **Yes, restricted to paper–code** |
| Error types | Difference; Paper Omission; Code Omission | Code/figure/data analysis discrepancies among wider issue classes | Map to upstream three classes |
| Categories | Algorithm, Model, Loss, Evaluation, Data, Training | Identity, statistical implementation, NMA, cross-document, source-reproducibility | Map without claiming equivalent scope |
| Unit of analysis | Reference discrepancy, often several per paper | Complete claim/source ledger, issue root, paper/trial-family | Primary: source-reference discrepancy; supplementary: paper and claim |
| Published performance | 22 LLM models; best 46.7% real reference recall | None that is scientifically comparable | **No Synthesis result yet** |
| Safeguards | Historical code commit and versioned paper; ground-truth descriptions; LLM judge; pooled manual sample | Source versions, evidence maturity, benign explanation, abstention and independent adjudication | Test as additional quality endpoints |

SciCoQA explicitly **excludes** unrelated code-only bugs, routine hyperparameters and incidental missing implementation. This must remain true in the comparison; counting all Synthesis methodological observations as SciCoQA true positives would inflate performance. Conversely, a potential clinical source-to-claim error may be important in Synthesis but outside SciCoQA's labels. Paper Omission (an important implemented scientific detail missing from the paper) must not be conflated with merely unspecified routine settings.

## Proposed pre-specified design (not yet run)

1. **Freeze the external benchmark and avoid leakage.** Preserve the v1.1 real and synthetic strata separately; record paper-family IDs, exact paper edition/PDF hash, repository commit, synthetic code changes applied, and case-to-reference mapping. Do not add the ground-truth discrepancy descriptions, GitHub issue text or answer labels to model input. Public SciCoQA items may have been seen in model training or prompt-development; treat this as an **external, potentially contaminated benchmark**, not a novel prospective blind test. Exclude any examples previously used to tune this prompt from a final independent cohort.
2. **Two prompt arms, one model.** Arm A: upstream verbatim `discrepancy_generation`; arm B: `benchmarks/scicoqa/synthesis_paper_code_prompt.txt`. The second is an **explicitly disclosed task-adapted Synthesis prompt**, not a verbatim full reproduction of the author-facing Synthesis v1.2 text. Both output upstream-compatible YAML `discrepancies` and receive the **same pre-frozen** paper markdown and code text. Match model ID/revision, temperature, seed where supported, reasoning effort, maximum output tokens, tool/retrieval access and independent repeats. Freeze actual rendered prompt hashes.
3. **Prevent the prompt-length context confound.** The unmodified SciCoQA inference iterator computes the code allowance as `0.9 × model_max_tokens − tokens(intermediate_prompt)` after adding the paper and prompt. A longer Synthesis prompt can silently *reduce available code*, so naively running the upstream CLI twice is **not** a strict prompt-only comparison. Capture paper/code once and run both prepared prompts **without additional arm-specific clipping**. If either rendered prompt exceeds the model's genuine limit, predeclare a common truncation rule for the source input, regenerate both, and record excluded code tokens. Compare evidence coverage and total token/cost differences separately; long prompts need not improve detection.
4. **Inference first; adjudication later.** Store every case × arm output, including zero detections, refusals, failures and abstentions. Predictions must be frozen before exposing reference descriptions. Use an identical upstream GPT-OSS 20B judge for a **secondary baseline-comparable recall** analysis; separately use two masked independent reviewers to label all predicted findings against source code and references, with disagreements resolved by a third reviewer. An LLM judge is **not** independent adjudication. Verify whether one predicted finding maps to one true root; an unverified flag is not a confirmed error.
5. **Controls and denominators.** Public real/synthetic SciCoQA entries are error-enriched; absence of a ground-truth mismatch is **not** proof that a paper is clean. Create separate, independently verified unchanged clean controls (within permitted sources), enumerate all claims, and review nonflags or a probability sample with known sampling weights. Stratify by real/synthetic, discrepancy type/category, long-context exposure and chronology. Do not mix multiple discrepancies per paper into independent-paper confidence intervals.
6. **Report outcomes transparently.** Primary: paired per-reference recall on the independently adjudicated reference set, counting abstentions/failures as misses; precision of actionable predicted flags, false alerts per 100 independently verified clean *cases*, reviewer minutes and model cost. Report all unresolved/unadjudicated cases and denominators. Secondary: upstream-judge recall, false alerts per 100 negative **claims**, clean **papers** with >=1 false alert, paper-family-cluster bootstrap 95% confidence intervals, prompt-length/token differences, repeated-run agreement and calibration where appropriate. Pre-register minimum acceptable reviewer burden/false-alert risk before evaluating results.

## Runnable offline preparation and scoring

The standard-library utility [`scripts/scicoqa_paired_benchmark.py`](../scripts/scicoqa_paired_benchmark.py) has **no model, network, PDF-download, GitHub-write or email side effects**. It does **not** collect the SciCoQA contexts automatically. In an authorised local scratch checkout of SciCoQA at the exact pinned commit, obtain paper markdown and version-correct code with the upstream loader/approved extraction method; supply the same fully rendered text for both arms. Do not commit restricted PDFs, raw source text, benchmark answers or third-party model outputs to this public repo.

A local `contexts.jsonl` record must have **exactly** these keys, with unique `case_id` per paper–code snapshot (not per known error):

```json
{"case_id":"LOCAL-SNAPSHOT-ID","split":"real","paper_version":"https://example.org/versioned-paper-v1","code_commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","paper_text":"[full permitted paper markdown]","code_text":"[full exact-commit code prompt]"}
```

The above record is a **schema illustration**, not a real SciCoQA item, downloaded paper or valid experimental sample. For synthetic cases, `code_text` must already include the *specified injected* change; record the exact changed-code snapshot and group related cases by underlying paper. Never put labels in contexts. Use the actual source code commit rather than the illustrative `aaaaaaaa...`.

```bash
# In a scratch checkout of UKPLab/scicoqa pinned at the upstream commit:
python3 scripts/scicoqa_paired_benchmark.py prepare \
  --contexts /private/path/contexts.jsonl \
  --upstream-prompts /scratch/scicoqa/config/prompts.yaml \
  --synthesis-prompt benchmarks/scicoqa/synthesis_paper_code_prompt.txt \
  --upstream-ref 463162906459be508ed4a2294fcaede9fa072036 \
  --model "EXACT_DEPLOYED_MODEL" --model-revision "EXACT_REVISION" \
  --decoding-config '{"temperature":0,"seed":1}' \
  --out-dir /private/path/scicoqa-pair-001
```

This writes `manifest.json`, `baseline-prompts.jsonl` and `synthesis-prompts.jsonl`. Run each prompt with the same model and settings **externally**; preserve the full raw YAML outputs and their hashes, then produce `predictions.jsonl` and blinded `adjudications.jsonl`. Record immutable raw outputs and judged evidence in a restricted provenance store. Each prediction must declare `case_id`, `arm`, `manifest_sha256` (SHA-256 of canonical compact sorted-key JSON for the manifest), `rendered_prompt_sha256`, `model`, `model_revision`, `decoding_config`, `status` (`COMPLETE`, `ABSTAIN`, `FAILED`), `findings` (`[{"finding_id":"F1","text":"verbatim model finding"}]`), and optionally `latency_seconds`. Missing case × arm rows are an error; use explicit `FAILED`/`ABSTAIN` records rather than discarding them.

For each case the blinded review file must include `case_id`, `review_state` (`COMPLETE` or `UNKNOWN`), `reference_ids` (one per independently resolved discrepancy root; empty only for an assessed clean item), and `by_arm` holding **both** `baseline` and `synthesis`. Each arm has `matches` (`[{"finding_id":"F1","reference_id":"R1"}]`), `false_positive_ids`, `unresolved_ids`, and `review_minutes`. For `COMPLETE`, attest `independently_adjudicated: true` and `reviewer_count: 2` or more. Those assertions are **caller-supplied**: the script cannot authenticate people or judgment. For `UNKNOWN`, all findings must remain `unresolved_ids`, no reference matches or false positives can be claimed, and unknown cases are excluded from adjudicated-rate denominators while remaining visible in case counts. Each predicted finding is judged once; each reference root can match no more than one finding per arm.

```bash
python3 scripts/scicoqa_paired_benchmark.py score \
  --manifest /private/path/scicoqa-pair-001/manifest.json \
  --predictions /private/path/predictions.jsonl \
  --adjudications /private/path/adjudications.jsonl \
  --output /private/path/scicoqa-pair-summary.json
python3 -B -m unittest discover -s tests -p 'test_scicoqa_paired_benchmark.py' -v
```

`score` computes paired reference detection, full-denominator recall, conditional judged precision, known-clean case false alerts, abstention/failure counts and reviewer minutes, and displays an explicit `null` confidence interval. It deliberately **does not** claim source truth, verify model calls, audit licences, prove the reviewers were independent, compute a cluster-aware interval, or perform the upstream LLM judge evaluation. Unresolved findings are excluded from **conditional** precision, but their number is always reported; this metric cannot be quoted as overall paper/claim precision. The generated example identifiers are for tests/schema only, not published research evidence.

## Risks, falsifiers and next decisions

- **Likely benefit to evaluate:** Synthesis's explicit model/estimand alignment, version provenance, negative controls and adversarial benign explanations may cut misleading paper–code flags.
- **Likely trade-off:** longer instructions can increase token costs, abstention, missed paper omissions and false-negative rates; the Synthesis template may be less adapted to ML architectures than the specialized SciCoQA prompt.
- **Critical falsifier:** if blinded, paired recall does not improve or additional true detections are outweighed by false alerts/reviewer time, **do not promote** the prompt. Refine on development-only data and freeze a fresh evaluation set.
- **Release status:** protocol/design ready for independent review; **model inference not run, adjudications not done, sensitivity/precision delta UNKNOWN**. The 7 synthetic CLI/unit checks protect code behavior only, not detection accuracy.

### Static versus externally derived evidence

| Repository contents | Must come from externally executed and audited study |
|---|---|
| Version links, source definitions, prompt text, JSONL schema, fail-closed preparation/accounting and synthetic unit tests | Actual paper/code input snapshots, model API calls, complete generations, blind source adjudication, recall/precision/CI, time and costs |

**Responsible communication:** Do not use a detected SciCoQA benchmark mismatch alone to email authors or assert scientific misconduct. Independent evidence verification, source permissions and manual editorial judgment remain essential.