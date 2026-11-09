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
- [Public implementation tree](https://github.com/Google-Health/consumer-health-research/tree/3e9d1e4877a54cf81ce8ef34085006952dd19601/personal_health_agent), checked 9 November. This tree contains the agent implementation, demonstration notebooks and tests. No clearly named historical HC3 statistical-fitting script was identified by this tree inspection; this is not proof that no such script exists elsewhere.

Fresh source hashes match the prior review's supplement and data ZIP. The current article was downloaded and its Methods reviewed. No correction resolving this specific statistic was established in this review; a comprehensive correction-history search was not completed.

## Findings and controls

| Check | Executed result | Synthesis disposition |
|---|---|---|
| HC3 published row | beta 1.052; Z 257.65; P <0.001 | Source value confirmed; statistical correctness unresolved |
| HC3 released preference data | 67 agent wins and 26 base wins; 93 ratings, 31 scripts, 3 raters | Counts reproduced; 72.043% agrees with displayed 72.0% |
| Rating structure | Every script has 3 ratings; every rater has 31; no duplicate rater/script pairs | Dependence must be retained in model reconstruction |
| HC3 implied SE if conventional Wald Z | 1.052 / 257.65 = 0.00408306 | Arithmetic reproduced; conditional on statistic definition |
| MCQ overall paired comparison, Table S12 | McNemar chi-square 9.50625 from discordant counts 100 and 60 | Matching control, NO_FLAG |
| Diagnostic ranking, Table S13 | Paired Wilcoxon W 126589.5 | Matching control, NO_FLAG |

The supplement identifies a binomial mixed model for S31. The main Methods explain a log link and system/rater/script roles for comparisons involving at least three systems; that paragraph cannot automatically be treated as the exact specification for this two-system HC3 preference analysis. The HC3 row still needs a precise mapping to outcome coding, link, fixed/random design, observation encoding, weights and the actual fitted contrast.

For scale only, an independent Bernoulli intercept-only logit calculation on the 67/93 preferences gives log-odds 0.946596, SE 0.231056 and Wald Z 4.096824. **This is not the published GLMM.** It ignores dependence and supplies no replacement P value, corrected table entry or multiplicity-adjusted conclusion. Its exact binomial P value is included only as a labelled diagnostic in the output. A crude-versus-adjusted mismatch does not establish an error.

## Alternative explanations and missing evidence

A transcription problem, numerical fitting/Hessian problem, different outcome encoding, weighting, link or contrast remain possibilities, not findings. The table's bootstrap percentage uncertainty is distinct from the model coefficient SE and must not be substituted for it. The rounded coefficient/statistic cannot identify the original fit.

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
