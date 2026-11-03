# Synthesis v1.3 — publisher-correction-derived regression cases (experimental)

Date: 3 November 2026. **Development corpus only; not independently measured detector performance.** Publisher notices confirm that specified reporting elements were changed. They do not establish intent, causal mechanism, clinical impact, or prospective detection accuracy. Keep this corpus separate from frozen cohorts and from protected attestations.

## Verified public cases

| Case | Original article DOI | Correction DOI | Notice-established old → new | Target regression | Important benign/negative control |
|---|---|---|---|---|
| BROOKLYN obicetrapib RCT | 10.1038/s41591-025-04179-4 | 10.1038/s41591-026-04405-7 | Upper 95% CI limit `-2.0%` → `2.0%` at day 180; `-7.5%` → `7.5%` at day 365 | Signed CI endpoints, estimate containment with compatible scale, CI/null interpretation; exact paragraph | Negative changes and CIs spanning zero can be valid; do not flag simply because a bound is negative |
| Benralizumab HES phase III | 10.1038/s41591-026-04315-8 | 10.1038/s41591-026-04425-3 | Table 1 PROMIS Fatigue total median `51.1` → `55.1`; Supplementary Table 2 eosinophil group medians changed; `2 (1.5%)` → `2 (3.0%)` for n=67 | Verbatim extraction; table/supplement versioning; `100*2/67 = 2.9850746...%`, rounds to `3.0%` at 1 decimal | Do not compare median with mean; group-specific n must match the exact labelled subgroup |
| SYNCHRONIZE-MASLD survodutide phase III | 10.1038/s41591-026-04479-3 | 10.1038/s41591-026-04650-w | Treatment-discontinuation placebo denominator `72` → `70`; Extended Data Fig. 5 caption `week 48` → `week 52` | Denominator attached to analysis population; caption/axis/analysis-time identity; `100*28/70=40.0%` vs `100*28/72=38.888...%` | Alternate denominators may represent randomized vs treated vs observed populations; do not call wrong without verifying estimand |
| ACCESS aleniglipron phase IIb | 10.1038/s41591-026-04476-6 | 10.1038/s41591-026-04532-1 | Figure 3b 120-mg least-squares mean `-12.1` → `-12.7`; Figure 4 missing bottom-right panel data and vomiting-panel arrows restored | Figure-content completeness and source-matched numeric/caption labels; differentiate LS adjusted means from raw means | A raw mean need not equal LS mean; ambiguous graphical extraction must HOLD |

Primary notices:
- https://www.nature.com/articles/s41591-026-04405-7
- https://www.nature.com/articles/s41591-026-04425-3
- https://www.nature.com/articles/s41591-026-04650-w
- https://www.nature.com/articles/s41591-026-04532-1

## Mandatory implementation rules

1. **Separate notice identity from claim identity.** Case key = normalized original trial ID (when verified) + original DOI + exact claim locator + claim type. Notice DOI is a provenance link, not a new discovery.
2. **Store before and after values with verbatim strings and precise locators.** Record original DOI, correction DOI, first-online date, correction date, publisher source URI, version/hash or retrieval date, supplement/figure version, old/new claim span, numeric units, and source rights. A current corrected PDF is not historical evidence of the original value; use the publisher's explicit notice when historical PDF is unavailable.
3. **Match twelve-field estimator signatures before numeric comparisons:** population; endpoint; time_window; effect_measure; estimand; model; adjustment; multiplicity; missingness; censoring; variance_method; test_statistic_identity. Specialized checks may verify count/percent presentation with narrower explicitly documented prerequisites, but must not infer an estimand.
4. **Precision-aware checks:** use exact integers for counts; derive percent bounds from the displayed decimal precision. For rounding to one decimal, `2/67=2.985...%` is compatible with 3.0% and incompatible with 1.5% given the notice-attested numerator and denominator. Never treat percent differences arising from legitimate analysis populations as errors.
5. **Check CI sign and null threshold** only on the same effect scale and time point; validate printed source precision and report `NOT_COMPARABLE` if lower/upper labels, adjusted estimands, or scale are uncertain. An interval crossing zero is not intrinsically erroneous.
6. **Graph checks require content integrity:** values, panels, legends, arrows, captions, axes and time labels, preferably with vector/accessible data. Missing/inaccessible historical figure => HOLD rather than a fabricated image finding.
7. **Correction-state finite-state workflow:** `NOTICE_FOUND` → `CLAIM_LINKED` → `CURRENT_VOR_VERIFIED` → `RECONCILED` only with exact corrected claim locator; `UNVERIFIED` or `PARTIALLY_CORRECTED` remain HOLD. A notice can correct one claim while leaving a distinct claim unresolved.
8. **Refutation required:** verify the strongest legitimate alternative (population, estimation method, missingness, display precision, time point, figure rendition) and retain verified negative controls, false alerts and abstentions.
9. **Review metrics:** blind-check notice-derived original text with matched unchanged claims and legitimate alternative-estimator controls; distinguish retrospective *known-positive* recall from independent prospective sensitivity. Do not mix with frozen Simo cohort. Cluster by trial/publication; preserve all abstentions and reviewer effort.
10. **Contact governance:** published/resolved claim is closed for outreach, correspondence must remain private, and no public dataset includes replies or personal contact records. This corpus does not authorize contact or publication-integrity accusations.

## Suggested executable checks and acceptance criteria (not yet implemented)

- `count_percent(2,67,"1.5%",display_decimals=1)` → `REVIEW`; `count_percent(2,67,"3.0%",display_decimals=1)` → `CONSISTENT`.
- `count_percent(28,70,"40.0%",display_decimals=1)` → `CONSISTENT`; `count_percent(28,72,"40.0%",display_decimals=1)` → `REVIEW` **only if the denominator is attested to be 72 in the same labelled population**.
- `figure_completeness` should detect absent specified panel content and captions when both versions and reference annotations exist; absent image evidence → HOLD.
- `compare_adjusted_to_raw` must return NOT_COMPARABLE when adjusted LS mean and raw arithmetic mean are inappropriately mixed.
- `current_version_gate` must RECONCILE the *exact* corrected claim and must not close a separate unrelated claim from the same article.
- All four cases must include at least one plausible benign control; reproduce known corrections without falsely asserting proof of source extraction from unavailable historical articles.

## Delivery gate

This commit adds reference design/cases, **not a functional detector**. Before implementation promotion: parse both publisher notices and accessible original/current source spans, add isolated tests to the existing checker, run scoped and full CI, obtain independent code/methods review and run blinded real-world evaluation. Keep Synthesis v1.3 experimental and preserve v1.1/v1.2 and frozen evaluation cohorts.
