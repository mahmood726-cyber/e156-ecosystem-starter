# Synthesis reporting: blinded evaluation and journal-yield accounting (v0.1)

**1 November 2026 — development tooling only; no clinical/scientific accuracy claim.**

These two offline, standard-library tools implement the six-week 5/5 pilot's
*measurement contracts*. They do not search for papers, send messages, alter the
frozen 36-claim Simo cohort, the separate 100-slot November study, the proposed
300-review benchmark or the 48-paper candidate sample. They do not create a
prospectively frozen cohort by themselves. The files in `tests/test_synthesis_reporting.py`
are deliberately synthetic and are not real-paper benchmark results.

## Separation of responsibilities

| Existing work reused | Net-new, intentionally limited addition |
|---|---|
| Synthesis v1.1 preflight's source/version and claim-receipt distinctions (PR #60) | A report-time manifest/prediction/adjudication contract for prospective, masked evaluation |
| v1.3's proposed root-cause and abstention bookkeeping (draft PR #61) | Explicit claim-level TP/FP/FN/TN and undecidable denominators; no scoring without frozen predictions |
| Existing journal-case and private correspondence ledgers | A private-ledger-to-public-aggregate yield calculator, with unique DOI and trial-family/root reconciliation |

### 1. Journal yield

Use `scripts/synthesis_journal_yield.py` on a **private** JSON list containing
one reconciled row per DOI. The tool prints aggregate JSON only; do not commit
raw ledgers, source documents, sender identities, SENT IDs or replies.

```bash
python scripts/synthesis_journal_yield.py PRIVATE_RECONCILED_LEDGER.json
```

Required row fields:

| Field | Contract |
|---|---|
| `doi`, `journal`, `family_id` | Distinct DOI; explicit report-family grouping, so repeated causes do not inflate the portfolio total |
| `access` | `ACCESSIBLE_VOR`, `SOURCE_LIMITED` or `BLOCKED` |
| `source_version`, `retrieval_path`, `source_locator` | Required when VOR is accessible; exact edition, retrieval method and claim location |
| `stop_point` | Required when source-limited or blocked; no imputation of unseen supplements |
| `deep_audit`, `audit_outcome` | Explicit boolean and one of `NOT_AUDITED`, `NEGATIVE`, `CANDIDATE`, `VERIFIED`, `INCONCLUSIVE` |
| `review_seconds` | Finite, nonnegative effort for this record |
| `root_causes` | List of distinct `{root_id, status}` with provenance for verified statuses |
| `sent_ids`, `reply_ids`, `correction_ids` | Optional lists of distinct local message/notice identifiers; never exported by the calculator |

Verified root statuses are `SOURCE_VERIFIED`, `AUTHOR_CONFIRMED` and
`PUBLISHED_CORRECTION`. Each requires `evidence_locator`, `source_reference`,
and an explicit `synthesis_discovery` Boolean. If `synthesis_discovery` is true,
include `detection_record` showing Synthesis discovered the claim; a correction
mined after publication has **false**, and never becomes a new Synthesis detection.
Author confirmations also need `confirmation_reference`; published corrections
need `correction_reference`. `PROVISIONAL`, `UNRESOLVED`, and `REFUTED` are not
counted as verified roots. A `NEGATIVE` audit may contain only refuted roots.

The output separately reports screened DOIs, accessible VOR, source-limited,
blocked, deep audits, explicit negatives, verified roots, verified *Synthesis*
discoveries, acknowledgements, published corrections, sent IDs, replies, hours,
per-100-accessible rates and discoveries per reviewer-hour. A null rate means
the denominator is zero; it does **not** mean the observed rate was zero.
The overall distinct trial-family/root count avoids treating several affected
papers as independent discoveries. Journal subtotals sharing a trial family
are **not additive**.

Do not call publisher acknowledgements, email delivery, author replies, or
downstream changed P-values independent scientific validation. Report roots,
not every altered table cell as a separate scientific error. Keep selection
methods and inaccessible-source denominators alongside any comparisons.

### 2. Blinded, claim-level real-paper evaluation

The three source files must be kept separately, with access controls supplied
by the study owner. Their SHA-256 bindings are reproducible *integrity checks*,
not an authenticated signature, source attestation or proof that blindness
actually occurred.

1. **Manifest** (`synthesis-blind-manifest-v1`): `cohort_id`, explicit
   `selection_rule`, integer `seed`, timezone-bearing `frozen_at`, and a
   prespecified `claims` list. Each claim needs `claim_id`, `family_id`, DOI,
   `split` (`development` or `test`) and source status. A verified original
   requires `original_version`, `retrieval_path`, `source_locator`, and
   `original_sha256`. An inaccessible original remains `SOURCE_LIMITED` with
   `retrieval_path` and exact `stop_point`. No known-correction answers or
   other outcome labels may appear in this file. All reports in a trial family
   belong to the same split.
2. **Frozen predictions** (`synthesis-predictions-v1`): exact
   `manifest_sha256`, timezone-bearing `frozen_at`, and one prediction for
   every test claim: `claim_id`, `predicted_at`, `review_seconds`, and
   `disposition` (`FLAG`, `NO_FLAG`, `ABSTAIN`). A flag needs `flag_root_id`
   and `evidence_locator`; an abstention needs `stop_point`. No silent
   replacements or missing test outputs are permitted. A claim with a
   source-limited original must abstain. This file cannot
   contain correction answers.
3. **Masked adjudications** (`synthesis-adjudications-v1`): exact
   `prediction_sha256` and one judgment for **every** test claim, after the
   prediction freeze. Each needs `truth` (`ERROR`, `NO_ERROR`, `UNKNOWN`),
   `adjudicated_at`, a real `evidence_reference`, and
   `independent_masked=true`. For a flag with known truth, an adjudicator
   additionally determines `flag_root_match`: merely flagging *some*
   issue in an erroneous paper is not necessarily detection of the target
   root cause. The code verifies that fields are present, but cannot verify
   adjudicator independence or the evidence itself.

```bash
python scripts/synthesis_blind_eval.py \
  --manifest PRIVATE_FROZEN_MANIFEST.json \
  --predictions PRIVATE_PREDICTIONS.json

python scripts/synthesis_blind_eval.py \
  --manifest PRIVATE_FROZEN_MANIFEST.json \
  --predictions PRIVATE_PREDICTIONS.json \
  --adjudications PRIVATE_MASKED_ADJUDICATIONS.json
```

**Before adjudication**, output is deliberately `PREDICTIONS_FROZEN_AWAITING_BLIND_ADJUDICATION`
with `metrics: null`. **After adjudication**, TP requires a validated match to
the prespecified claim/root. A flagged wrong root on an actually erroneous
claim counts both as a false alert and an undetected root. Known-error
abstentions count against automatic recall, while unknown truth is never a
true negative. Report conditional precision, automatic recall including
abstention misses, false-alerts per adjudicated negative claim, unknown-truth
fraction, and Wilson 95% intervals where denominators exist. These are
claim-level descriptive estimates on the selected population, not
population-prevalence estimates. Known-error-enriched selection cannot
estimate error prevalence in all journals.

**Release criterion for an accuracy claim:** independently verify the complete
prespecified sampling and source trail, stable pre-reveal prediction record,
masked reviewer assignments, reason-level labels, outcomes on unflagged
claims, and leakage controls. Compare v1.2 and v1.3 on identical untouched
test claims with effort/time and abstention accounting. If the test set has
been used for detector tuning, retire it from final evaluation and freeze a
fresh one before claiming improvement.

### Static-versus-dynamic disclosure

| Component | Static | Derived from actual input |
|---|---|---|
| Accepted statuses, JSON schema, Wilson formula | Yes, fixed code | No |
| Test seed and example DOI strings in synthetic unit tests | Yes; marked synthetic | No empirical paper data |
| Journal denominators, verified-root counts, response rates, reviewer hours | No | Yes, from reconciled private records |
| Blind test sample, prediction labels, independent adjudication and accuracy | No | Yes, only after authentic files and external verification |

This development PR provides the tools and synthetic tests only. It must not
be presented as completed blinded evaluation, independent validation, or a
shipping-certified v1.3 detector.
