# Wightman frailty IPD-NMA: held intervals and a reconciled count

Wightman et al., DOI [10.1371/journal.pmed.1004553](https://doi.org/10.1371/journal.pmed.1004553). Current [publisher article](https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004553), [S2 code](https://doi.org/10.1371/journal.pmed.1004553.s002), [S1 data](https://doi.org/10.1371/journal.pmed.1004553.s011) and actual Figure 5 inspected 3 November 2026.

**Status:** the displayed interval differences below are source-verified; same-analysis identity, intended correction and substantive impact remain unresolved. They are held outside the substantive-error target. The 12-versus-11 study-count lead is **reconciled and is not an error**.

## Held uncertainty reporting

| Display location | Outcome | Estimate (95% CI) |
|---|---|---|
| Abstract | Baseline frailty/MACE | HR 3.01 (2.48–3.67) |
| Results, association with adverse events | Baseline frailty/MACE | HR 3.01 (2.68–3.37) |
| Figure 5, actual image | Baseline frailty/MACE | HR 3.01 (2.69–3.37) |
| Abstract and Results | Treatment-related adverse events | IRR 1.36 (1.23–1.49) |
| Figure 5, actual image | Treatment-related adverse events | IRR 1.36 (1.32–1.49) |

These are displayed differences, not established errors in the fitted estimates. Different adjustments, variance estimators or pooling could explain the MACE intervals. Original baseline-MACE pooling outputs are needed to decide. The exported f2/f3 models contain treatment interactions; their baseline coefficients must not be substituted for the marginal frailty association. No p-value was reverse-engineered and no restricted IPD were accessed.

## Native materials resolve the study count

The exported MACE coefficients contain 12 first-stage studies per model. The published R code explicitly excludes `H9X-MC-GBDE` because its arms belong to the same drug class. The reference-arm file identifies dulaglutide and liraglutide, both mapped to GLP1 by the code. Twelve first-stage studies and eleven class-network studies are therefore compatible. The previously held count discrepancy is closed, with zero error credit.

The [input JSON](WIGHTMAN-1004553-inputs.json) records exact source locators, observations and SHA-256 hashes. With the original downloaded source files, run:

```bash
python scripts/inspect_wightman_1004553_sources.py docs/audits/WIGHTMAN-1004553-inputs.json /path/to/S1_Data.zip /path/to/S2_Appendix.docx
```

This verifies the downloaded hashes, counts the exported study IDs, checks the documented exclusion statement and reports 12 before/11 after exclusion. It inspects public aggregate files and code text without executing the authors' analysis. It does not validate a native R fit, posterior draws or the intended confidence intervals.

| Component | Static or computed | Evidence/limit |
|---|---|---|
| Displayed intervals and source locators | Static source transcription | Current HTML and actual Figure 5 |
| Source hashes and exported study counts | Computed from downloaded files | Public ZIP/DOCX; no restricted IPD |
| Same-class exclusion | Source code and reference-arm verification | Static inspection; no native NMA refit |
| Model identity and intended intervals | Unknown | Held for clarification; no target credit |

The current article has an IPD network-analysis component; the questioned baseline-risk association is distinct from its treatment-effect network. A bounded current correction search retrieved no relevant notice; absence is not established. Private correspondence is excluded.
