# Source-linked trial evidence review (experimental pilot)

**Development aid only, not a scientifically validated error detector.**
This addition does not alter Synthesis v1.3's six-core/27-detailed checklist,
protected held-out cohorts, private correspondence, or existing manuscript intake.
It does not extract directly from PDFs, authenticate the meaning of source text,
or re-fit meta-analysis models. Only authorised material may be used.

## Relationship to the existing, stronger count/percent gate

Synthesis **already implemented** a source-bound `COUNT_PERCENT` check in
`scripts/synthesis_intake_evidence.py`, used by the PMC intake workflow.
That existing module binds selected numerator, denominator, and printed
percentage tokens in a versioned source snapshot, checks a much richer
methodological identity, and records the declared rounding convention.
The present `count_percentage` viewer extension is **not a newly invented
scientific detector** and must not replace that source-bound workflow.

The viewer adds a lightweight display-level *prescreen* for reviewer-supplied
archived text/PDF-derived quotations where the full PMC token-binding contract
has not been completed. It requires source bytes/quote matching and declared
context but cannot authenticate which cell represents an outcome or a risk set.
If the exact paper is available through the established PMC intake, prefer
`COUNT_PERCENT` as the primary numerical evidence record and use the viewer
only to communicate what the reviewer actually inspected.

A `REVIEW_CANDIDATE` from the viewer is never a validated `COUNT_PERCENT`
finding, an independent adjudication, or permission for outreach. Converting
between the two schemas without replaying the corresponding source evidence
would be misleading. The viewer treats exact halfway rounding ties
conservatively, whereas the canonical gate records an explicit `HALF_UP`
or `HALF_EVEN` convention.

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
    "claim_version_status": "CURRENT_UNCORRECTED",
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

The second comparison kind is `variance_label`, with published and primary
labels SD or SE. A third comparison kind, `count_percentage`, checks a
**simple unweighted person count divided by the same population denominator**,
provided exact source-located counts and the printed percentage are present in
the respective archived quotations. None of these checks reproduces a fitted
statistical model.

For `count_percentage`, provide this `comparison` object (synthetic values):

~~~json
{
  "kind": "count_percentage",
  "published_count": 2,
  "published_denominator": 67,
  "published_percentage": "1.5%",
  "primary_count": 2,
  "primary_denominator": 67,
  "percentage_method": "RAW_UNWEIGHTED_PERSON_FRACTION",
  "raw_fraction_source_verified": true,
  "denominator_basis_source_verified": true
}
~~~

Both context records must additionally have **the same meaningful
`denominator_basis`** (for example, a clearly identified treated population),
with matching trial, cohort, endpoint, analysis population and time-window
identities. The published source quotation must contain the exact numerator,
denominator and printed percentage, and the primary source quotation must
contain the numerator and denominator. These literals appearing somewhere
in a quotation **do not authenticate their assignment to a particular cell
or subgroup**; that remains a human responsibility.

The checker uses integer arithmetic to calculate compatibility with the
percentage's printed decimal precision. It tolerates exact half-step rounding
ties rather than accusing a paper because its rounding convention differs.
For 2/67, 3.0% is compatible while 1.5% is not. However, a review candidate
still requires the required source attestations, a documented refutation of
alternative explanations and a genuinely **current, uncorrected** claim.
Historical corrections are held and are not treated as new discoveries.
Missing source denominators, different count populations, Kaplan-Meier
percentages, weighted event rates, person-time incidences, and incomplete
analysis definitions produce HOLD or NOT_COMPARABLE rather than a flag.

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
| REVIEW_CANDIDATE | Archived quotes verified, each compared literal appears in its respective archived quotation, reviewer-declared contexts agree, version is attested CURRENT_UNCORRECTED, difference exists and a specific alternative is recorded as source-refuted. This **is not a confirmed error**. |
| NO_SCOPED_DIFFERENCE | Selected values agree. No other statement about the paper follows. |
| NOT_COMPARABLE | One or more declared population/endpoint/time/estimator identities differ. |
| HOLD | Missing file, mismatched hash/quote, numeric value not present as a complete literal in its quote, unknown/already-corrected version, incomplete context, invalid input or alternative not refuted. |

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
source-anchored raw count/percent arithmetic and rounding boundaries,
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

## Retrospective lessons from previous cases (2026-11-19)

These are **historical regression illustrations transcribed from public publisher notices**, not runs over the original dated manuscript PDFs, study-level data, current Version of Record or blinded papers. Each transcribed fixture is explicitly labelled synthetic in tests/test_synthesis_source_trial_view.py. Do **not** count statuses as retrospective detection performance.

| Published case | Notice-established change | Expected scoped behaviour with transcribed fixtures | Important limit |
| --- | --- | --- | --- |
| Ishikawa, DOI 10.1007/s00737-026-01767-2 | Matched controls 76,242 → 7,624 | HOLD because HISTORICAL_CORRECTED | The printed subtraction does not independently recount matched participants |
| Aqeel, DOI 10.3390/nu12051263 | Participants 352 → 332 and studies 20 → 17 | HOLD because HISTORICAL_CORRECTED | No study-by-study inclusion or statistical reanalysis |
| Benralizumab HES, DOI 10.1038/s41591-026-04425-3 | 2 (1.5%) → 2 (3.0%), denominator 67 | Count-only mode says NO_SCOPED_DIFFERENCE; new raw-percent mode finds the arithmetic mismatch in synthetic **current-claim** scenarios but yields HOLD for the historical corrected notice | No detection claim from transcribed data; original source and current-Version-of-Record meaning not independently authenticated |
| BROOKLYN obicetrapib, DOI 10.1038/s41591-026-04405-7 | Upper CI limit -2.0% → +2.0% | HOLD; signed-CI comparison is unsupported | CI method, scale, confidence bounds and version need separate verification |
| Previously investigated duplicate-trial and SD-versus-SE examples | Trial family overlap or data extraction labels | Synthetic overlap/label gates exist; **real original-source replay NOT RUN** | Qualified trial-identity and method adjudication required |
| Silverii network meta-analysis correction | Corrected pooled effect estimates | NOT TESTABLE with this module | Requires source-based trial extraction and actual estimator replay |

**Failure-mode checks added:** arbitrary mismatched count values not appearing in their quotations must HOLD, including partial-digit matches (e.g. printed 142 is not evidence for a reported 14). The value tie is syntactic only and does not authenticate table-cell assignment, population or timing. Historical corrected claims must HOLD rather than generate new flags. A matched numerator must not be misrepresented as validation of its percentage or denominator.

Related correction notices:
- https://doi.org/10.1007/s00737-026-01767-2
- https://doi.org/10.3390/nu12051263
- https://doi.org/10.1038/s41591-026-04425-3
- https://doi.org/10.1038/s41591-026-04405-7

**Implemented next:** Bounded count/percentage precision checks on human-attested matched denominators, plus negative controls for missing counts, alternative populations, weighted/KM methods and historical corrections. This is arithmetic checking, **not** independent verification of endpoint/denominator identity.
**Next work:** Improve source-to-cell assignment with a reviewable per-trial extraction ledger and independent model replay; never infer an analysis change from a notice alone.
