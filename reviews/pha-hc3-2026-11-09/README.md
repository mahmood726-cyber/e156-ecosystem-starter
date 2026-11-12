# PHA HC3 statistical enquiry: reproducible review notes

**Review date: 9 November 2026. Status: unresolved (`NOT_ENOUGH_INFO`, `HOLD`).**

This narrow Synthesis review concerns Supplementary Table S31 of *The anatomy of a personal health agent*, DOI [10.1038/s41586-026-11161-8](https://www.nature.com/articles/s41586-026-11161-8). It establishes neither a confirmed error nor a corrected mixed-model estimate. No conclusion reversal has been demonstrated.

## Scope and method

Reuses the [Synthesis methods guide](../../docs/SYNTHESIS-METHODS.md): establish source identity, inspect the displayed table, check data structure, reproduce matching controls, test alternative explanations, and abstain when the estimator cannot be matched. This adds a paper-specific calculation script and its executed output to the existing `e156-ecosystem-starter` repository. It is a review attachment, not a new software product or validated release. No portfolio index was available in this environment; no portfolio counts or lifecycle promotion are asserted.

The publicly linked general checklist is not this paper-specific analysis. This folder supplies the missing working. No private correspondence or author screenshot is included.

## Sources inspected

- [Final article and Methods](https://www.nature.com/articles/s41586-026-11161-8).
- [Published supplementary information](https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-026-11161-8/MediaObjects/41586_2026_11161_MOESM1_ESM.pdf): Table S31, printed page 76, PDF page 77. The table was visually inspected, not only text-extracted. SHA-256: `295ee91635feb8478ea5f6117ca2f7525b5870e5683cd374531b3989750e4f35`.
- [Released evaluation data ZIP](https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-026-11161-8/MediaObjects/41586_2026_11161_MOESM4_ESM.zip): SHA-256 `2945e086af56c6922ed68bc1cafecd017efd777c93b2b970b081c06cf9a9fce8`.
- [Published peer review and author responses](https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-026-11161-8/MediaObjects/41586_2026_11161_MOESM3_ESM.pdf): the statistical review discusses rater/script random effects and the authors distinguish two-system within-rubric tests from multi-system contrasts. SHA-256: `60ca70b5a7df6a56a2bc2004daa4713a0716ff21951a48b5283933a5086e80ba`.
- [August 2025 arXiv version 1](https://arxiv.org/abs/2508.20148v1) and [September 2025 version 2](https://arxiv.org/abs/2508.20148v2): both have the same HC3 coefficient and Z in Supplementary Table S27. Downloaded PDF SHA-256 values: v1 `ef928beadc0551e8e158e218d027ab54f542777f46f93ac569a2fc69ea4693ee`; v2 `66579f9e89e5688c29d513be2f411d825cd92df5a5186a6fbfd4f9d40ce74918`. The final publication renumbered this as S31. This shows that the printed statistic was present in the initial preprint and persisted through publication; it does not identify the original cause.
- [Public implementation tree](https://github.com/Google-Health/consumer-health-research/tree/3e9d1e4877a54cf81ce8ef34085006952dd19601/personal_health_agent), checked 9 November. This tree contains the agent implementation, demonstration notebooks and tests. No clearly named historical HC3 statistical-fitting script was identified by this tree inspection; this is not proof that no such script exists elsewhere.

Fresh source hashes match the prior review's supplement and data ZIP. The current article was downloaded and its Methods reviewed. No correction resolving this specific statistic was established in this review; a comprehensive correction-history search was not completed.

## Findings and controls

| Check | Executed result | Synthesis disposition |
|---|---|---|
| HC3 published row | beta 1.052; Z 257.65; P <0.001 | Source value confirmed; statistical correctness unresolved |
| HC3 released preference data | 67 agent wins and 26 base wins; 93 ratings, 31 scripts, 3 raters | Counts reproduced; 72.043% agrees with displayed 72.0% |
| Rating structure | Every script has 3 ratings; every rater has 31; no duplicate rater/script pairs | Dependence must be retained in model reconstruction |
| HC3 implied SE if conventional Wald Z | 1.052 / 257.65 = 0.00408306 | Arithmetic reproduced; conditional on statistic definition |
| Other eight rows in S31 | Implied SEs range 0.2576 to 0.5484; median 0.3128 | HC3 implied SE is at least 63 times smaller; within-table comparison conditional on Wald Z |
| Script-block label-swap sensitivity | Two-sided exact P = 0.000438649 under a sharp within-script exchangeability null | Supports a preference difference under that null; cannot authenticate the printed Z |
| MCQ overall paired comparison, Table S12 | McNemar chi-square 9.50625 from discordant counts 100 and 60 | Matching control, NO_FLAG |
| Diagnostic ranking, Table S13 | Paired Wilcoxon W 126589.5 | Matching control, NO_FLAG |

The supplement identifies a binomial mixed model for S31. The main Methods explain a log link and system/rater/script roles for comparisons involving at least three systems; that paragraph cannot automatically be treated as the exact specification for this two-system HC3 preference analysis. The HC3 row still needs a precise mapping to outcome coding, link, fixed/random design, observation encoding, weights and the actual fitted contrast.

For scale only, an independent Bernoulli intercept-only logit calculation on the 67/93 preferences gives log-odds 0.946596, SE 0.231056 and Wald Z 4.096824. **This is not the published GLMM.** It ignores dependence and supplies no replacement P value, corrected table entry or multiplicity-adjusted conclusion. Its exact binomial P value is included only as a labelled diagnostic in the output. A crude-versus-adjusted mismatch does not establish an error.

The script-block check enumerates all 2^31 possible label swaps, keeping each script's three ratings together. It assumes scripts are independent and agent/base labels exchangeable under the sharp null. This provides an independent sensitivity check that avoids treating 93 ratings as 93 independent scripts. A conservative nine-test Bonferroni adjustment gives P = 0.003948 under that same null; the preference difference would survive this adjustment. It does not reproduce a crossed rater/script GLMM, and the repeated use of the same three raters needs separate consideration in any model reconstruction. The empirical standard error of the 31 script-level win fractions is about 5.15 percentage points; the table's 4.8-point error bar is described as a bootstrap result, so these should not be equated.

For an *unweighted unit-coded Bernoulli logit Wald coefficient*, each independent observation contributes no more than 1/4 Fisher information before nuisance parameters; 93 observations would imply SE at least 2/sqrt(93) = 0.2074. Achieving SE 0.004083 at this maximum information would require about 240,000 independent unit-coded observations. This is a conditional information check, **not a universal impossibility proof for the authors' unspecified fit**. We cannot apply it to an unknown weighted analysis, different parameter coding, link, or test definition. The original coefficient and model summary remain necessary.

## Alternative explanations and missing evidence

A transcription problem, numerical fitting/Hessian problem, different outcome encoding, weighting, link or contrast remain possibilities, not findings. The table's bootstrap percentage uncertainty is distinct from the model coefficient SE and must not be substituted for it. The rounded coefficient/statistic cannot identify the original fit. The peer review endorses a general repeated-rating model strategy, but does not provide the HC3 coefficient/SE output or explain the displayed Z.

The next useful evidence is the exact HC3 model call and data preparation, coefficient/contrast summary with SE, package versions, optimizer, convergence warnings, Hessian checks and random-effect variance estimates. Confirm whether preference observations were represented once or as paired/stacked system rows. Re-run that specification before deciding whether the displayed Z is reproducible. If an explanation resolves the mismatch, retain it as a resolved enquiry; if a defect is demonstrated, assess the affected claims and multiplicity analysis separately.

## Reproduce these checks

Download the two publisher files above to your own machine. Source files retain their own terms; they are not redistributed here. Install Python, pandas, scipy and Poppler (`pdftotext`). From this folder:

```bash
python -m pip install pandas==2.2.3 scipy==1.17.0
pdftotext -layout supplement.pdf supplement.txt
python verify.py --data-zip data.zip --supplement-text supplement.txt --output results.json
```

`results.json` records the actual run and package versions. The script reads the reported HC3 values from the supplied supplement text, calculates results from released CSVs and checks key data integrity conditions. It does not recreate LLM outputs, adjudicate clinical content, or reproduce the historical GLMM. The supplement text hash can differ across Poppler versions; original PDF and ZIP hashes above identify the sources.

## AI and review disclosure

AI assistance was used to inspect documents, draft code and interpret the scoped checks; the numerical checks were executed deterministically in Python. This is not independent human adjudication. No swarm was used in this review. Nothing here establishes which tools or number of agents were used in every earlier session.

| Fixed instructions or choices | Source-derived or executed evidence |
|---|---|
| Selected HC3 rubric and matching controls; diagnostic formula and abstention rules | Downloaded source hashes, extracted table values, observed counts, executed statistics and package versions |
| Proposed evidence request and alternative explanations | No original GLMM replay performed; no confirmed error, author confirmation or correction inferred |
