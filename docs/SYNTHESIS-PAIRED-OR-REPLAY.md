# Synthesis — published-first paired OR replay (experimental)

This is a supervised **development interface**, not an independently validated correction or evidence of accuracy on real papers. It supports only independent two-arm binary-outcome odds-ratio meta-analyses using the exact **Paule–Mandel random-effects model with floored Knapp–Hartung confidence interval**. It cannot substitute for a network meta-analysis, IPD model, REML, Mantel–Haenszel, fixed-effects model, different continuity correction, or adjusted effect.

## Workflow

1. Archive and hash the exact published methods and pooled-OR/CI passage. Record the printed point estimate, both 95% confidence limits, source version and exact quote offsets. A reviewer must source-attest the published estimator and the complete included-trial set.
2. Archive each original meta-analysis extraction row and its corresponding primary trial report. Bind all four original and proposed corrected arm counts to **distinct exact quoted-number occurrences**. Require a trial-family ID, matching analysis population/endpoint/time, supported T1–T3 primary source, independent non-overlapping trial attestations, and source-checked reasons for any changed values. Unidentified or duplicated families HOLD.
3. Reject missing, invalid, non-comparable and zero-cell inputs (continuity method not established). The preflight can return READY_FOR_PINNED_ENGINE without running a model. A fitted model is never claimed in this state.
4. Only when explicitly given a trusted local copy of the reviewed external meta-starter-kit engine plus its SHA-256, verify the file's SHA-256 and its **fixed Git blob SHA**. Execute original data **first** under that exact method. If the printed original OR **or either CI limit** cannot be reproduced at its printed precision, return PUBLISHED_REPLAY_MISMATCH and **do not execute** the corrected model.
5. Only after the original point and interval match may the same engine run corrected source-attested counts. Save both sets of pooled point estimates, confidence limits and heterogeneity, engine hash, relevant source digests and numeric point difference. The result is for expert review—not a declaration that the paper was incorrect or that clinical guidance should change.

All outcomes preserve **scientific_error_confirmed = false** and **conclusion_impact = NOT_ASSESSED**. Changed statistical significance or treatment superiority is not inferred.

Numeric bindings must cover complete unsigned tokens: signed values, exponent
fragments and neighbouring identifier characters are refused. The engine executes
the already hash-verified source buffer, rather than a cached Python bytecode file.
Every receipt retains `replay_stages` for the published and corrected fits. If a
fit fails, HOLD preserves any completed original result and engine hash; an
attempted fit is never reported as `NOT_RUN`.

## Existing implementation reused

The external numerical implementation is the user's public [meta-starter-kit engine at commit 464fd88e](https://github.com/mahmood726-cyber/meta-starter-kit/blob/464fd88eb50825985b46b60cda248516d4b495ab/metakit/engine.py), with canonical Git blob SHA-1:

9b25f4a98bb882c2d09c18288f93028de5bcf83b

This source actually calls the Paule–Mandel tau-squared routine and HKSJ-floor CI. Some upstream prose mentions REML; **the code is not an interchangeable REML implementation**. A future engine version must be separately re-reviewed and pinned. No third-party statistical engine code is copied into this repository.

The entrypoint is **scripts/synthesis_paired_model_replay.py** and it reuses the source-quote verifier and source-cell ledger helpers. It is offline, reads local inputs, makes no API calls and sends no correspondence. Loading an external Python source file is executing code; only supply a trusted checked-out file. Self-supplied SHA-256 alone does not establish that its code matches a reviewed source, so a separate fixed blob check is mandatory.

## How to invoke

Preflight (does not fit any model):

    python scripts/synthesis_paired_model_replay.py --packet /private/paired.json --source-root /private/captures --out /private/preflight.json

After independently obtaining the exact trusted upstream engine and its current file SHA-256, the optional real fit:

    python scripts/synthesis_paired_model_replay.py --packet /private/paired.json --source-root /private/captures --engine-file /trusted/meta-starter-kit/metakit/engine.py --engine-sha256 ACTUAL_FILE_SHA256 --out /private/replay.json

Never use invented sample data as clinical evidence. The schema is illustrated by the **PairedModelReplayTests** test class in tests/test_synthesis_source_trial_view.py. It generates source files, hashes and exact offsets dynamically.

### Input contract overview

Top-level fields: schema_version 0.1, claim_version_status CURRENT_UNCORRECTED, analysis and publication mappings, and trials (2–40 rows).

The analysis mapping must provide named population, endpoint, time_window, analysis_set, intervention, comparator, effect_measure OR, and estimand UNADJUSTED_TWO_ARM_LOG_OR.

The publication record must provide a hash-checked text snapshot, source-checked matching method, a verbatim methods excerpt, **published_variance_floor_source_verified: true** and a **variance_floor_quote** present in that original published passage, and three source-bound decimal literals with 1–6 digits of decimal precision: pooled_or_text, ci_low_text and ci_high_text, each with a corresponding *_binding offset and text. It also requires trial_set_complete_source_checked true.

Each trial record requires unique trial_key and trial_family_id, primary source tier T1/T2/T3, attested distinct participant population, matching analysis map, two hash-checked captured source records (published_extraction and primary_trial), trial-key binding in the primary quote, original and corrected four-cell tables (tE, tN, cE, cN), and exact, non-aliased original_bindings and corrected_bindings. Changed cells require correction_source_checked true and a specific correction_rationale.

These are **reviewer-supplied assertions**. Source hashing and exact token matching cannot prove the value is from the right clinical arm, trial, outcome or risk set.

## Results and limits

| Status | Meaning |
| --- | --- |
| HOLD | Evidence, comparability, source version or model trust insufficient. |
| READY_FOR_PINNED_ENGINE | Packet preflight completed; no statistical engine run. |
| PUBLISHED_REPLAY_MISMATCH | Original OR or CI cannot be reproduced. Corrected replay blocked. |
| ORIGINAL_REPLAY_MATCHED_NO_INPUT_CHANGE | Original model point and CI match but no input differences were submitted. |
| PAIRED_MODEL_REPLAYED_FOR_REVIEW | Original point and interval reproduced under the chosen pinned method, then corrected counts run under the identical model. Further independent statistical and source review required. |

**Static-versus-dynamic disclosure:** required fields and gating rules are fixed; source/engine bytes and token offsets are verified at runtime; numerical estimates are produced only with an explicitly supplied pinned engine; independent trial identity, clinical/estimand comparability, corrected-source truth and conclusions are *not* authenticated.

## Validation status

The synthetic unit tests use a **toy/mock pooling interface** to validate execution order, early refusal, bookkeeping and SHA/source gates. Separately, the real-engine integration test executes the entire source-bound original-before-corrected branch on **invented archived quotations and a deliberately invented correction**. It also demonstrates that changing the printed original CI blocks the corrected fit. This is real computation on synthetic data, not verification of a historical scientific error. The separate `test_synthesis_real_engine.py` integration suite requires an **actual checked-out, pinned upstream engine**. It tests real engine output against an independent low-heterogeneity closed-form calculation and a **published paper-table negative control** from [Zhang et al., Frontiers in Medicine, 2026](SYNTHESIS-HK-PAPER-NEGATIVE-CONTROL.md): ordinary and variance-floored Knapp–Hartung correctly produce different confidence limits from identical trial rows. The published table is not independent primary-trial source verification, and no corrected original clinical study result has been demonstrated. Broader validation against R `metafor` on independently checked primary-trial data remains necessary.

Keep the pull request in draft pending methods review and proper validation. No source-confirmed findings may be emailed based on this module alone.

### Unmet numerical precision gate (26 November 2026)

An independent closed-form check of the existing three-row negative control
found that the pinned engine uses `4.30265` for the two-degree-of-freedom
Student t critical value, versus `4.302652729749463`. The resulting upper-limit
absolute difference is approximately `5.00347e-6`. The current integration
test's `2e-5` tolerance is a bounded development diagnostic; it does **not**
satisfy this repository's deterministic `1e-6` requirement. This release gate
remains unmet pending an independently reviewed upstream precision fix and a
new source pin. No tolerance relaxation or clinical implication is claimed.
