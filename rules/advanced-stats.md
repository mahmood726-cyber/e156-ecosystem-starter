# Advanced Statistics Rules (gotchas only)

> Formulas/theory: look up when needed. This file = mistake-prevention rules only.

## Pooling
- **DL bias**: Never use DL for k<10 - use REML or PM.
- **HKSJ floor**: If `Q < k-1`, HKSJ *narrows* CI below DL - set floor: `max(1, Q/(k-1))`.
- **HKSJ df**: Use `qt(alpha/2, k-1)` NOT `qnorm`. t-distribution matters when k<30.
- **OR->SMD constant**: `sqrt(3)/pi ~= 0.5513`, NOT `sqrt(3/pi)`.
- **Fisher z variance**: `1/(n-3)` exact - don't use n-2.
- **Log scale**: Always pool logRR/logOR/logHR, back-transform after. Natural scale + RE = Simpson's paradox.
- **Zero cells**: Add 0.5 ONLY if >=1 cell is zero. Unconditional correction biases OR->1.
- **PI df conflict**: Cochrane Handbook v6.5 (Nov 2024, §10.10.4.3) uses `t_{k-1}` × √(τ²+SE²); IntHout/Higgins/Tudur Smith 2016 derived `t_{k-2}`. Default to `t_{k-1}` for Cochrane / RevMan-2025 bit-reproducibility; document which convention if computing locally. Undefined for k<3 (k-1) or k<4 (k-2). Both conventions are defensible — never silently flip without recording in commit message.
- **Multiverse pooling**: Never IV-RE-pool many-analyst / multiverse results from one dataset — CIs collapse below truth (arXiv:2511.17064). Use weighted-likelihood (Wagenmakers 2025) or report as descriptive heterogeneity only. Direct hit on PI Atlas, repro-floor-atlas, and any Pairwise70-style multi-spec analysis.
- **Causal sign on RR/OR**: Pooled logOR/logRR is a causal contrast only under collapsibility; with non-trivial baseline-risk variation across studies (SD > 0.1), the pooled OR can flip sign vs. average causal effect (arXiv:2505.20168). Always pair logOR pooling with risk-difference sensitivity check when baseline-risk SD across studies > 0.1.
- **Observational IV trap**: For observational MAs, inverse-variance weights amplify SE-manipulation by primary-study modellers (Stanley 2025, Nat Comm s41467-025-63261-0). Use sample-size weighting (UWLS+3 or HS) as primary; report IV-RE only as sensitivity. Don't use FE/RE-IV as primary on observational data.

## Heterogeneity
- **I^2 != magnitude**: Measures proportion, not amount. Report tau^2 alongside.
- **I^2=0 != homogeneity**: Just means Q <= df. Low power with few studies.
- **I^2 CI**: Use Q-profile method (Viechtbauer 2007) for small k.

## Publication Bias
- **Egger's**: Use radial version. Low power for k<10. For binary outcomes: use Peters' test.
- **Trim-and-fill**: Sensitivity analysis only - never the primary result.
- **PET-PEESE**: PET first; if rejects null, switch to PEESE. Conditional procedure matters.
- **Copas**: Needs k>=15.
- **ROB-ME (Cochrane Ch.13, 2024+)**: Per-MA reporting-bias tool — funnel/Egger become inputs, not the verdict. Applies even at k=1 (where Egger/PET undefined). For Cochrane-aligned reviews, this is the formal small-study/missing-evidence assessment.
- **Outcome-switching base rate**: ~24% of pre-specified outcomes silently dropped in ITS (medRxiv 2025.11.06); 52% protocol-vs-paper discrepancy. Any review including ITS must compute protocol-vs-paper outcome-set diff; treat undisclosed drops as high-RoB contributing to publication bias.

## NMA
- **Always test consistency** (design-by-treatment + node-splitting) before interpreting.
- **SUCRA != effect size**: Never rank by SUCRA alone - show CrI of relative effects.
- **Disconnected networks**: Cannot do NMA. Check connectivity first.
- **Multi-arm trials**: Off-diagonal covariance = `tau^2/2` (shared control).
- **POTH for SUCRA hierarchy**: Always report POTH (Wigle 2025, arXiv:2501.11596) alongside SUCRA — summarises rank-uncertainty into [0,1]. If POTH < 0.5, hierarchy is non-informative — do not write "X ranked best" in conclusions.
- **NMA multiplicative fallback**: If Egger/funnel suggests publication bias OR the network has ≥1 small-study outlier, fit multiplicative-heterogeneity NMA alongside additive RE (arXiv:2601.11735). Switch to ME if AIC favours by ≥2.

## DTA
- **Bivariate convergence**: Common failure with k<5. Constrain rho to [-0.95, 0.95] or fix rho=0.
- **Threshold effect**: Spearman corr(logit(Se), logit(1-Sp)) > 0.6 -> report SROC curve, not pooled Se/Sp.

## Bayesian
- **Rhat > 1.01**: Do NOT interpret. Increase iterations or reparameterize.
- **ESS < 400**: Unreliable CrI. Need >=400 per parameter.
- **Divergent transitions**: Increase adapt_delta to 0.95-0.99 or use non-centered parameterization.
- **Grid approximation**: 200x200 OK for unimodal. Fails beyond 2-3 params - use MCMC.

## Survival
- **RMST**: Always state tau*. Pool differences, not ratios.
- **Guyot IPD**: Never claim IPD-level accuracy. Verify events/median/p-value match published.
- **Non-PH**: If Schoenfeld rejects PH, single HR is misleading. Use interval HRs or RMST.

## Numerical
- **NPD matrix**: Fix with nearPD() (Higham), NOT eigenvalue clamping.
- **Log-likelihood**: Always compute on log scale. `exp(a)+exp(b)` -> `exp(a)*(1+exp(b-a))`.
- **Fisher z at r=+/-1**: Clamp to [-0.9999, 0.9999].
- **logit(0)/logit(1)**: Clamp to [1e-10, 1-1e-10].
- **Clopper-Pearson**: `qbeta(alpha/2, x, n-x+1)` - the alpha/2 IS correct. Agents false-flag this.
- **RevMan-2025 reproducibility checklist**: For bit-reproducibility against a Cochrane review, all four must match — τ²=REML (default), PI df=k-1, HKSJ-floor=`max(1, Q/(k-1))`, τ² CI by Q-profile. A failing bit-mismatch → check these four first before suspecting your engine.
- **INSPECT-SR ≠ RoB**: For MAs with k≤5, run INSPECT-SR trustworthiness checks (medRxiv 2025.09.03). Across 95 RCTs / 50 Cochrane reviews, **32% raised authenticity concerns** and **22% of MAs would have zero RCTs left** after exclusion — RoB-2 + GRADE missed all of it. Orthogonal check, not a substitute.
- **Conformal PI for federated MA (HOLD — future consideration, 2026-04-26)**: arXiv:2604.23847 ("Privacy-preserving Meta-analysis through Low-Rank Basis Hunting") constructs prediction intervals via **conformal prediction** with asymptotically valid marginal coverage in the privacy-preserving / federated setting. Single paper, very fresh (Apr 2026). Not actionable for current portfolio (no privacy-preserving MA in scope). Promote to a real rule only if a federated-MA project enters the workbook OR if a follow-up paper validates the coverage claim on real data.

## TSA
- **O'Brien-Fleming**: `z_k = z_alpha / sqrt(t_k)`.
- **Design effect for heterogeneity**: `D = 1 + tau^2 * (sum(1/v_i^2)/(sum(1/v_i))^2 * k - 1)`. NOT cluster-design effect.
- **Binding vs non-binding futility**: If tool allows ignoring futility, must be non-binding.
