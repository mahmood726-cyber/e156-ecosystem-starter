# Source-linked trial evidence review (experimental pilot)

**Development aid only, not a scientifically validated error detector.**
This addition does not alter Synthesis v1.3's six-core/27-detailed checklist,
protected held-out cohorts, private correspondence, or existing manuscript intake.
It does not extract directly from PDFs, authenticate the meaning of source text,
or re-fit meta-analysis models. Only authorised material may be used.

## Reuse versus new work

* **Existing detector reused:** scripts/synthesis_v13_nma_preflight.py for
  caller-attested repeated trial/cohort effects and covariance handling.
* **Existing methodology reused:** docs/SYNTHESIS-METHODS.md on population,
  endpoint and estimand identity, refutation and explicit abstention.
* **New:** scripts/synthesis_source_trial_view.py verifies file SHA-256 digests
  and exact quoted substrings; evaluates selected integer-count or SD/SE-label
  differences only when the supplied source and published identities match;
  and renders two-column, standalone HTML. Optional PNG/JPEG page images can
  be embedded after their bytes and SHA-256 are verified.
* **Unimplemented:** automatic PDF retrieval/extraction, source-page locator
  authentication, semantically verified trial identities, model re-fitting,
  treatment ranking or conclusion-change assessment, email, or independent review.

A hash proves archived bytes. The printed locator and all clinical context fields
are **reviewer declarations**, not automatically authenticated semantic facts.

## Run offline

Python 3.10+, standard library only. Store permitted source archives and generated
HTML outside the public repository. Example command syntax:

~~~sh
python scripts/synthesis_source_trial_view.py \
  --packet /private/packet.json \
  --source-root /private/snapshots \
  --html-out /private/reviews/review.html

python -m unittest discover -s tests -p 'test_synthesis_source_trial_view.py'
~~~

Source paths inside the packet must be relative to the declared source root.
Absolute paths, traversal and symlinks leading outside the root are refused.
Text snapshots must be UTF-8 and at most 2 MB each. PNG/JPEG captures, when
provided, are limited to 5 MB. All displayed text is HTML-escaped.
The static output requires no browser network access or JS.

## JSON input contract — synthetic illustration, not a real medical case

Supply a JSON object containing a cases array. The sample below is a schema
illustration, **not directly executable**: replace the sample SHA-256 strings
with exact hashes of the corresponding source text files, which must contain
the quoted strings. All values and identifiers here are invented.

~~~json
{
  "cases": [{
    "case_id": "synthetic-001",
    "published": {
      "path": "paper.txt", "sha256": "REAL_SHA256_REQUIRED",
      "version": "paper-v1", "locator": "Table 2",
      "quote": "Synthetic manuscript reports 14 events"
    },
    "primary": {
      "path": "trial.txt", "sha256": "REAL_SHA256_REQUIRED",
      "version": "trial-v1", "locator": "Table 1",
      "quote": "Synthetic trial reports 12 events"
    },
    "contexts": {
      "published": {
        "trial_family_id": "synthetic-family",
        "cohort_id": "synthetic-cohort",
        "population": "invented adults",
        "intervention": "therapy A", "comparator": "placebo",
        "endpoint": "invented outcome", "time_window": "day 30",
        "analysis_set": "ITT", "effect_measure": "event count",
        "estimand": "crude count", "statistic_id": "treated events"
      },
      "primary": {
        "trial_family_id": "synthetic-family",
        "cohort_id": "synthetic-cohort",
        "population": "invented adults",
        "intervention": "therapy A", "comparator": "placebo",
        "endpoint": "invented outcome", "time_window": "day 30",
        "analysis_set": "ITT", "effect_measure": "event count",
        "estimand": "crude count", "statistic_id": "treated events"
      }
    },
    "comparison": {
      "kind": "integer_count", "published": 14, "primary": 12
    },
    "refutation": {
      "alternative": "Maybe different follow-up periods",
      "checked_against": "Methods and Table 1",
      "result": "NOT_SUPPORTED"
    }
  }]
}
~~~

The second supported comparison kind is variance_label, with published and
primary labels SD or SE. Neither kind reproduces a fitted statistical model.

To display a captured page alongside the quotation, add the optional
page_image object to either source snapshot, containing path and sha256 for an
authorised PNG or JPEG in the source root. Image presence is not proof of the
declared page locator. Do not claim OCR or automatic page extraction.

The optional top-level duplicate_effects array accepts structured rows already
used by the existing NMA preflight, including source version/locator and
same_cohort_source_verified attestations. Outputs remain separate.

## Conservative statuses

| Status | Meaning |
| --- | --- |
| REVIEW_CANDIDATE | Archived quotes verified, reviewer-declared contexts agree, difference exists and a specific alternative is recorded as source-refuted. This **is not a confirmed error**. |
| NO_SCOPED_DIFFERENCE | Selected values agree. No other statement about the paper follows. |
| NOT_COMPARABLE | One or more declared population/endpoint/time/estimator identities differ. |
| HOLD | Missing file, mismatched hash/quote, incomplete context, invalid input or alternative not refuted. |

No result authorises correspondence or allegations. Human source review,
statistical review and independent adjudication remain necessary. Keep private
manuscripts, protected extracts, identities and correspondence outside GitHub.

## Hardcode disclosure and validation

| Property | Static contract | Dynamically checked |
| --- | --- | --- |
| Required field names and decisions | Yes | No |
| Source byte hashes and exact substring occurrence | No | Yes, on supplied bytes |
| Optional page image type and digest | No | Yes, on supplied bytes |
| Declared population, trial ID or refutation truth | No | **No — human review** |
| Clinical impact, detection accuracy and actual model replay | No | **Not supported** |

The included synthetic tests cover matching and mismatching counts, SD/SE labels,
missing hashes, missing quotes, context mismatch, alternative-refutation gate,
path containment, HTML escaping and existing NMA duplicate-preflight integration.
Passing them cannot establish field sensitivity or accuracy.

Independent comparison should follow the existing
docs/SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md with unseen trial families, matched
inputs and review time, independent source adjudication and reports of precision,
false alerts, abstentions, review burden and conclusion impact.

Inspiration (concepts only; **no third-party code copied**): PaperTrace side-by-side
evidence, Scientific Claim Verification Engine provenance and abstention,
CSPaper second-pass checking, MetaCheck modularity, and SciCoQA paired benchmarking.
Review upstream licences before future code integration.
