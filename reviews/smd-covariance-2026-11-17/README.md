# Candidate discrepancies in standardized mean differences

Research note by Mahmood Ahmad, 17 November 2026. **Computational candidates; author adjudication, worldwide novelty and clinical consequences are not established.**

This audit finds three equation/implementation discrepancies and one example-input discrepancy in sources used for multivariate meta-analysis. Reproducible counterexamples support investigation. The familiar squared-correlation covariance term and the usual Hedges correction are established mathematics; this note does not claim to have invented them. The full private audit and correspondence are not included.

| ID | Source and location | Reproducible concern |
|---|---|---|
| F-SMD-COV-RHO2 | Becker & Zhang (2024), [DOI 10.1111/bmsp.12345](https://doi.org/10.1111/bmsp.12345), section 5.1.1, equation 11 | The printed linear correlation in the second term fails an outcome-sign reversal identity; a squared correlation satisfies it. |
| F-SMD-METAVCOV-J | Lu (2023), [DOI 10.3389/fpsyg.2023.1185012](https://doi.org/10.3389/fpsyg.2023.1185012), and pinned `metavcov::smd.vcov` source | Raw standardized mean differences are divided by a conventional correction factor below one, rather than multiplied. The same direction appears in Wei & Higgins (2013), section 3.4. These are one root. |
| F-SMD-K12-OVERLAP | Wei & Higgins (2013), [DOI 10.1002/sim.5679](https://doi.org/10.1002/sim.5679), equation 12 and Table I; retained `smd.vcov` | The printed cross-variance coefficient lacks patient-overlap counts and fails both the zero-overlap and identical-outcome checks. Its reuse on the software diagonal also has an asymptotic consequence. These are one root. |
| F-SMD-EXAMPLE-SCALE | Lu (2023) example; pinned `Geeganage2010` dataset | All 34 supplied SMD values follow `MD/sqrt(SD_T^2+SD_C^2)`, conflicting with the article's stated pooled-SD definition. This is one input/preprocessing root. |

## Replay

Python 3.11 or later runs the deterministic checks without third-party packages, from the repository root:

```sh
python reviews/smd-covariance-2026-11-17/audit.py
python -m pytest tests/test_smd_covariance_audit.py -q
```

For the additional synthetic grid, install the optional requirements and run:

```sh
python -m pip install -r reviews/smd-covariance-2026-11-17/requirements-simulation.txt
python reviews/smd-covariance-2026-11-17/audit.py --simulate
```

Base R replays the unmodified source functions, all seven example sensitivities, and the separate computational review's new cases:

```sh
Rscript reviews/smd-covariance-2026-11-17/verify_original.R
Rscript reviews/smd-covariance-2026-11-17/independent_checks.R
```

Outputs go to the ignored `replay-output/` directory. Committed outputs in [results/](results/) are reference executions, not patient observations. [provenance.json](provenance.json) records source pins and [SHA256SUMS.json](SHA256SUMS.json) fixes this bundle's bytes. The Python replay checks that manifest before calculating. It fails if an included file is missing or altered.

See [the execution record](VALIDATION.md): audit-specific checks passed, while the broader repository suite is not green on the current Windows host.

The retained R functions are executed directly; this does not test an installed package namespace, every package version, or every downstream application. They intentionally preserve the behavior under investigation. Diagnostic modifications in `verify_original.R` are confined to function copies.

## 1. A covariance must reverse sign with an outcome

The inspected equation 11 is

\[
F=(1/n_T+1/n_C)\rho+\delta_1\delta_2\rho/(2N),\qquad N=n_T+n_C.
\]

Reversing outcome 2 changes both \(\delta_2\) and \(\rho\) to their negatives. A covariance with outcome 2 must negate. The second printed term instead remains unchanged. With 50 participants per arm, effects 2 and 2, and correlation 0.5, the printed expression gives 0.030 before reversal and -0.010 afterwards. Replacing the second correlation by \(\rho^2\) gives 0.025 and -0.025.

This identity locates a problem with the printed expression without relying on a simulation. It does not establish whether the authors' analyses used the printed expression. The publisher HTML equation and publisher PDF text were checked in the underlying audit. An existing squared-correlation formulation is also available in the [metafor reconstruction of Gleser & Olkin (2009)](https://www.metafor-project.org/doku.php/analyses:gleser2009).

## 2. The direction of the Hedges correction

For \(\nu=n_T+n_C-2\), the conventional factor is

\[
J_\nu=\frac{\Gamma(\nu/2)}{\sqrt{\nu/2}\,\Gamma((\nu-1)/2)}
\approx1-\frac{3}{4\nu-1}.
\]

Under the usual independent Normal, common-variance model, \(E[d]=\delta/J_\nu\), so \(J_\nu d\) removes this bias. The retained source defines the approximation above but assigns `g[k,i] <- d[k,i]/jvi`. At 10 participants per arm and raw \(d=1\), it returns 1.0441176471, whereas multiplication gives 0.9577464789; the exact factor is 0.9576464270.

The interpretation of `d` matters: the paper defines the input as the mean difference divided by the pooled SD. This finding is conditional on that definition, not on an alternative already-corrected input. The original 1981 Hedges correction is not implicated.

## 3. Patient overlap and the cross-variance coefficient

The printed/source coefficient for outcomes 1 and 2 is

\[
k_{12}^{\rm printed}=\frac{2}{\nu_1\nu_2}
\left\{\frac{n_{1T}n_{2T}}{n_{1T}+n_{2T}-1}
+\frac{n_{1C}n_{2C}}{n_{1C}+n_{2C}-1}-2\right\}.
\]

It contains no actual overlap counts. With independent patients and disjoint observed samples, the two outcome estimators must be independent, even if the outcomes would be correlated within a patient. For `nt=nc=(12,17)`, `d=(0.8,-1.1)`, correlation -0.7 and zero off-diagonal overlaps, the unchanged R function returns covariance **-0.0042327234**, instead of zero.

There is also a complete-data identity check: if the two outcomes are identical, their covariance must equal their variance. For equal arm sizes \(n\), the printed \(k_{12}/k_i\) equals \((n-1)/(2n-1)\). At \(n=10\), equation 12 gives 0.0163849878 for the reciprocal-pooled-SD covariance, versus the exact variance 0.0345905298, a ratio of 9/19. The ratio tends to one half, not one.

An independent derivation for **fixed observation sets, independent Normal patients and a common within-arm outcome covariance** gives

\[
q_a=m_a-\frac{m_a}{n_{1a}}-\frac{m_a}{n_{2a}}+
\frac{m_a^2}{n_{1a}n_{2a}},\qquad
k_{12}^{\rm fixed}=\frac{2(q_T+q_C)}{\nu_1\nu_2}.
\]

Here \(m_a\) is the number of patients observed for both outcomes in arm \(a\). Writing sample-variance centering matrices as \(H_1,H_2\) and the shared-patient incidence matrix as \(C\), expansion gives \(q_a=\operatorname{tr}(H_1CH_2C')\). The Normal quadratic-form covariance identity then yields

\[
\operatorname{Cov}(V_1,V_2)=\rho^2\sigma_1^2\sigma_2^2 k_{12}^{\rm fixed},
\]

for the pooled variances \(V_j\). It gives zero at zero overlap, \(2/\nu\) at identical complete samples, and \(q_a=\min(n_{1a},n_{2a})-1\) for nested samples. **An exact pooled-variance coefficient does not make the full hybrid finite-sample SMD covariance formula exact.** Informative missingness or non-Normal outcomes require further analysis.

The 2013 Appendix A3 starts from common paired chi-square degrees of freedom and uses \(\operatorname{Corr}(s_1^2,s_2^2)=\rho^2\), which holds for complete paired Normal observations. It does not supply a general arbitrary-overlap justification. The inspected appendix uses an additional degrees-of-freedom symbol without an explicit definition in A3; this note makes no claim about the editorial origin of the discrepancy or an error in the cited bivariate chi-square theory.

### A large-sample consequence of this software's diagonal

Consider complete bivariate Normal observations, \(n\) per arm, unit marginal SDs, equal true effects \(\delta\), and correlation \(\rho\). Test the difference of the effects, whose true value is zero. In the retained implementation, let

\[
\nu=2n-2,\quad J=1-3/(4\nu-1),\quad
b=J^2\nu/(\nu-2)-1,\quad r=(n-1)/(2n-1).
\]

The returned effects are \(e_j=d_j/J\) and its covariance entries reduce to
\(S_{ij}=2\rho_{ij}/n+rb\rho_{ij}^2d_id_j\), including the diagonal \(\rho_{ii}=1\). Direct calls to the original function check this reduction. Since \(nb\to1/4\) and \(r\to1/2\),

\[
V_{\rm true}=\lim n\operatorname{Var}(e_1-e_2)
=4(1-\rho)+\tfrac12\delta^2(1-\rho^2),
\]
\[
V_{\rm reported}=\operatorname{plim} n(S_{11}+S_{22}-2S_{12})
=4(1-\rho)+\tfrac14\delta^2(1-\rho^2).
\]

The limiting two-sided nominal 5% Wald rejection rate is
\(2\Phi[-z_{.975}\sqrt{V_{\rm reported}/V_{\rm true}}]\).
For \(\delta=2,\rho=0.5\), the variances are 3.5 and 2.75, and this rate is **8.2330%**, corresponding to **91.7670%** interval coverage. At \(\delta=0\), the rate is 5%: an explicit negative control.

This concerns the inspected software's construction of both diagonal and off-diagonal entries. It is not a statement about every use of the 2013 paper, nor an estimate of a real clinical false-positive rate. Changing the J direction alone does not remove the limiting discrepancy. Changes to J and k are diagnostics, not a certified replacement method.

## 4. The supplied example uses a different scale

The pinned public dataset has **17 supplied rows/contrasts and 34 SMD values**. Four rows carry Barer 1988 labels; these are not established as 17 distinct independent trials. Every value matches

\[
d_{\rm stored}=\operatorname{MD}/\sqrt{s_T^2+s_C^2},
\]

whereas the article defines raw SMD using

\[
d_{\rm stated}=\operatorname{MD}/
\sqrt{\{(n_T-1)s_T^2+(n_C-1)s_C^2\}/(n_T+n_C-2)}.
\]

The Python fingerprint residual is below \(10^{-14}\), and the direct binary-data R check gives zero. The maximum discrepancy against the stated definition is 0.3095066775. Stored/stated ratios range from 0.6811989171 to 0.7369655895. In the equal-SD `Kaste 1994/120 mg` SBP row, stored=-0.0520535794 and stated=-0.0736148780, exactly the \(1/\sqrt2\) scale difference to numerical precision.

This is a numerical construction fingerprint. The upstream construction script was not located, so it does not identify an exact erroneous source-code line. The retained source and stored inputs reproduce the first six displayed effect/covariance rows in the 2023 article at printed precision.

The replay also computes seven controlled fixed-effect sensitivities using correlation 0.71 and the software's default overlap assumption. With original inputs/functions, the pooled SBP/DBP estimates are -0.05111962/-0.11068181 and Q=41.15898 (32 df, p=0.1287056). Reconstructing only the raw inputs gives -0.07180217/-0.15563949 and Q=81.37576 (p=0.0000035149). Across the seven sensitivities the SBP interval includes zero and the DBP interval excludes zero. These shifts concern this supplied example. **Shared controls and cross-contrast dependence have not been reconstructed; these are not validated corrected clinical meta-analyses.**

## Separate computational review and additional checks

A separate computational review rederived the overlap coefficient and selected new inputs. It was an additional AI computation, not independent human statistical adjudication. Exact scripts and reference output accompany this note.

| New setting | Measured result | Analytic comparison |
|---|---|---|
| Partial overlap: T=(7,12), C=(9,6), overlaps=(3,2), rho=-0.7; 300,000 raw-patient replicates | Pooled-variance covariance 0.01697237, MC SE 0.00025537 | Fixed-set derivation 0.01726852; printed-coefficient prediction 0.02854167; derivation is 1.16 MC SE from simulation. |
| Wald contrast: n=12,000 per arm, delta=1.5, rho=0.8; 300,000 replicates | Rejection 7.4243%, MC SE 0.0479 percentage points | Limit 7.3823%; empirical n-variance 1.205105 versus true limit 1.205; mean reported n-variance 1.002564 versus reported limit 1.0025. |
| Original R source versus reduced formula, 30 fresh input pairs | Effect error zero; maximum contrast-variance error below 2e-16 | Confirms which software calculation the asymptotic argument describes. |

A further six-scenario grid was fixed in [simulation-plan.json](simulation-plan.json) before execution, extending effects to 0.75/1.25 and correlations to -0.6/0.2/0.8 at n=50,000 per arm. These settings were chosen after the original rho=0.5 calculations; no coefficient was fitted or tuned. Results, Monte Carlo errors, and diagnostic J/k changes are in [results/python-reference.json](results/python-reference.json). This is additional checking of a derived identity, not a held-out clinical validation set.

| Ingredient | Fixed input or dynamic result? | Provenance / limit |
|---|---|---|
| Published formulas, DOIs, source version | Fixed source claims | Publisher links and exact CRAN Git commit in provenance.json; no PDFs redistributed. |
| `Geeganage2010` and its CSV export | Fixed public aggregate example data | Original binary and unmodified R source included with GPL notice. No individual patient data. |
| Equation counterexamples, fingerprints, variances, pooled sensitivities | Calculated | Recomputed by Python/base R; tests use independent identities and boundary cases. |
| Normal/Wishart observations | Generated synthetic data | Explicit sample sizes, effects, correlations, repetition counts and RNG seeds; not clinical evidence. |
| Reference outputs | Fixed record of actual executions | Replays write separate outputs and do not overwrite the references. |

## Licensing and limits

Own Python code and prose follow the repository's MIT licence. Original `metavcov` source/data and the R replay scripts are covered separately by GPL version 2 or later; see [third_party/metavcov/NOTICE.md](third_party/metavcov/NOTICE.md) and [COPYING](third_party/metavcov/COPYING). Source articles retain their own licences.

The four roots should be treated as candidates pending source-author response and qualified review. A bounded literature/erratum search did not establish whether these discrepancies were previously reported. The audit does not establish a new theorem, a globally first discovery, invalid clinical conclusions, or a validated replacement statistical package.
