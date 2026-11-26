# Real-publication numerical negative control: ordinary versus modified Hartung–Knapp

**Development comparator only, 20 November 2026.** This document records a
limited calculation from a published article's **reported study table**. It
is *not* an independent reconstruction from all original trials, an NMA audit,
a new finding about research integrity, or evidence of Synthesis accuracy.

## Source and exact scope

Wei Zhang and colleagues, *Primary intraocular lens implantation and secondary
glaucoma after congenital and infantile cataract surgery: a systematic review
of randomized and observational evidence*, Frontiers in Medicine (5 Nov 2026),
DOI 10.3389/fmed.2026.1985280.

Published article:
https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2026.1985280/full

Published Figure 2 (three randomized trial comparisons), printed event counts:

| Figure's study label | IOL glaucoma cases/children | Initial aphakia cases/children |
| --- | --- | --- |
| Li 2014 | 3/30 | 1/30 |
| Vasavada 2018 | 4/29 | 4/25 |
| Freedman 2021 | 12/57 | 13/57 |

Total 228 children across the three rows. The paper reports its **primary**
randomized pooled OR **1.01 (95% CI 0.31–3.24)** with Paule–Mandel
heterogeneity variance and ordinary Hartung–Knapp confidence intervals.
Separately, its modified HK sensitivity analysis reports **0.20–4.95** for
the same point estimate. The review explicitly distinguishes the modified
HK interval from the primary analysis.

**Source coverage update (20 November 2026):** Only part of the included-trial
evidence has been checked beyond the 2026 review's own Figure 2.

| Trial row | External source check | Status |
| --- | --- | --- |
| Li 2014, DOI 10.1111/aos.12465 | The accessible original Acta Ophthalmologica full text specifies 30 patients per arm and 3 glaucoma cases with IOL versus 1 with aphakia after one year. https://onlinelibrary.wiley.com/doi/10.1111/aos.12465 | **Source-text count match** for that scoped endpoint; this does not verify all trial methods and corrections |
| Vasavada 2018, DOI 10.1016/j.ajo.2018.06.005 | The 2022 Cochrane review DOI 10.1002/14651858.CD003171.pub3 reports 4/29 pseudophakic versus 4/25 aphakic eyes at five years, consistent with the 2026 article. https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD003171.pub3/pdf/full | **Secondary independent review match, original trial not checked**. PDF visual rendering returned a 403 and was not independently visually inspected |
| Freedman 2021, DOI 10.1001/jamaophthalmol.2020.5664 | The original publication belongs to JAMA Network, for which automated processing is excluded under the project's existing publisher restriction | **Original report not processed**; counts remain reproduced from the 2026 review table only |

This is **not** an independently source-verified three-trial extraction ledger:
endpoint definitions and differing follow-up periods (one, five and ten
years), first-eye versus eye-level counting, publication corrections, and
clinical comparability remain to be reviewed by a qualified researcher.
No author/editor contact is authorised by these calculations.

## Recalculation, conditional on exactly these printed counts

Per-study unadjusted log OR is
log[a (n0-c) / ((n1-a) c)], with variance
1/a + 1/(n1-a) + 1/c + 1/(n0-c).

On the three stated pairs, the independently calculated fixed-weight
heterogeneity statistic Q is approximately 1.07729, below df=2;
Paule–Mandel tau-squared therefore equals zero. The inverse-variance
pooled log OR is 0.00502175; the pooled OR is approximately **1.00503**.

The ordinary HK scale is Q/2 = approximately **0.53864**. With
Student-t critical value t_(.975,2) approximately 4.30265272974946, this yields
**OR 1.005 (95% CI 0.312–3.238)**, consistent with the primary paper's
reported 1.01 (0.31–3.24).

The **variance-floored** or modified HK uses max(1, Q/2) = 1, yielding
**OR 1.005 (95% CI 0.204–4.948)**, consistent with the paper's
separately described modified-HK sensitivity 0.20–4.95.

This is a methodological identity check with an expected *negative
control*: identical estimated OR, different CIs under two legitimate
confidence-interval constructions. It would be wrong to accuse the
primary paper of a discrepancy because a floored engine yields 0.20–4.95,
when the paper transparently reports both variants.

## Automated integration

The separate test `tests/test_synthesis_real_engine.py` checks the actual
trusted upstream `meta-starter-kit/metakit/engine.py` at commit
`4156930cf2d1404870766fb821b045b671a7eff6`,
by verified SHA-256 and pinned Git blob, against:

- the printed review-table numbers (not primary trial files);
- the independently calculated tau²=0, pooled OR and modified-HK
  confidence interval for this low-heterogeneity case;
- the corresponding unfloored HK reference calculation;
- exact published-decimal precision compatibility for the modified
  sensitivity result, and refusal to call that interval the paper's
  unfloored *primary* interval.

The GitHub Actions workflow runs the existing synthetic unit suite and
the **real external numerical-engine integration** separately. An additional real-engine end-to-end test uses explicitly **invented source files and an invented corrected event count** to confirm the original-before-corrected execution and the corrected-run refusal after an original CI mismatch. That simulated correction is not evidence about the 2026 ophthalmology paper. This does
not establish general engine correctness across many datasets, validate
the published trial set, or reproduce any corrected clinical analysis.

## Consequence for the Synthesis paired-replay gate

For a paper whose primary result uses **unmodified** HK, the
`META_STARTER_KIT_PM_HKSJ_FLOORED_LOG_OR` engine is not the primary
published model. Accordingly Synthesis now requires a specific source
quotation supporting the **variance-floor modification** before even
attempting the model comparison. The primary 0.31–3.24 interval must not
be represented as an error merely because the modified engine gives
0.20–4.95. Even when method matching succeeds, actual source-trial
identity and data extraction must still be independently checked.

## Static versus dynamic disclosure

| Item | Basis |
| --- | --- |
| Paper title, DOI, Figure 2 labels, printed counts and intervals | Public paper, manually selected |
| Engine source commit, blob identity and formula | Pinned code contract |
| Original-trial event/denominator validity | **Partially checked only** (Li original count matches; Vasavada Cochrane secondary source matches; Freedman original left unchecked) |
| Independent closed-form 3-trial calculation | Mathematical recalculation on reported study rows |
| Real external engine execution and comparison | Executed by the dedicated GitHub CI if its step completes successfully |
| Scientific error or clinical conclusion impact | **None established** |

This paper and its linked trial families are development material,
not eligible for an untouched Synthesis validation cohort.
