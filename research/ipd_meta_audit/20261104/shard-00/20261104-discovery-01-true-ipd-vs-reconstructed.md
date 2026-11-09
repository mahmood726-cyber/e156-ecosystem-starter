# Shard 00: IPD provenance discovery — true trial IPD, methodological demonstration, reconstructed KM pseudo-IPD

**Review date:** 2026-11-04 (UK/GMT). **Scope:** bounded source-first discovery/provenance screen of three distinct scholarly article families, not a comprehensive clinical audit, model replication, or scientific-error adjudication. **Immutable record 01.** No papers are declared erroneous.

## Code and governance snapshot

- Repository: https://github.com/mahmood726-cyber/e156-ecosystem-starter
- Current integrated **main** HEAD resolved at start: `5f74f21dbc6e170c04d61eb60382877c5cef8e0c` (2026-11-04 16:40:05Z).
- Read from main: `AGENTS.md` (Git blob `1135b82681e9b061438bfd034955a08d7fe1876d`); `docs/SYNTHESIS-v1.3-CANDIDATE.md` (blob `2ca1b6ed2b1985b344dd812454d8bf8a4f502c87`); `scripts/synthesis_v13_nma_preflight.py` (blob `c9d011694b40afa81065d0e7a0e9b9b33bdd5004`); `rules/rules.md` (blob `4f2cf053e8dcc6b410feff0f7620ddc80882a905`). Latest integrated documented candidate = **Synthesis v1.3 experimental**, NOT clinically validated. Four functions check source-attested duplicate populations, shared controls, restriction counts, and replay readiness. The script does not fit an IPD meta-analysis or independently authenticate any source. No Synthesis code was run.
- Research protocol: `docs/SYNTHESIS-IPD-META-AUDIT-20261104.md` on research branch, blob `b1da19b4b96cce13f70874da24d5232473fd0bc0` (read in full). Research branch HEAD before this file write: `3382e0326d94d3d1e0864f02c69bbb1bbcf8b9c9`; destination path verified absent.
- Previous correction campaign is preserved as unmerged *draft* PR #67, observed head `a80d471783682207928a348907d1faecee68bc2f`. No files in that PR or other automations were altered.
- Record labels are **source access** FULL/PARTIAL/METADATA; **disposition** NO_FLAG/REVIEW_CANDIDATE/REFUTED/HOLD; **adjudication** separately tracked. The FULL category requires all relevant original sources, supplemental methods, correction status and identity checked; reading an article HTML alone is not FULL.

## Ownership, stable discovery identity and dedup

Normalize DOI by lowercasing the bare DOI, then assign `int(SHA256(UTF-8 normalized DOI),16) % 10`; compute independently, never determine by first hex character. All three below route to **shard 00**. One article family per DOI; constituent trials must be linked to their original trial family before adding a second result; multiple manifestations of the same article and cross-lens referrals earn no extra discovery credit.

| Family / article type | Canonical DOI | SHA-256 hex | Owner |
|---|---|---|---|
| TOPCHILD clinical genuine two-stage trial IPD | `10.1016/s0140-6736(25)01144-4` | `89d4e497ec9a746e6a55f7fdc2fdeb23516b42635a1618d67280cad8efcdec3c` | 00 |
| Siegel et al. methodological paper with real TICO/ACTIV-3 IPD application PLUS separate simulated examples | `10.1017/rsm.2025.10043` | `ea83368bc3b705d9a0cbf16125af25aa60ca7941ac2864eb14e1575c4f5ef84c` | 00 |
| Campbell et al. survival NMA based on reconstructed KM pseudo-IPD, NOT source-original participant records | `10.1017/rsm.2025.21` | `dd99c2a1a1cdca38eb6a7f37d0bf6e6f6b98b0fbad3961034310f1db53e97304` | 00 |

## S00-01 — genuine trial IPD: TOPCHILD (PARTIAL)

**Identity:** Hunter KE et al. “Parent-focused behavioural interventions for the prevention of early childhood obesity (TOPCHILD): a systematic review and individual participant data meta-analysis.” *Lancet* 2025;406:1235–1254, published online 10 September 2025. DOI `10.1016/S0140-6736(25)01144-4`. **Version state:** the accessible [PMC article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12884657/) explicitly identifies itself as an **author manuscript** (PMC available 10 February 2026), NOT the publisher final VoR. [Publisher VoR link](https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(25)01144-4/fulltext) returned HTTP 403 in this run; publisher page and definitive current corrections not independently inspected. PMCID `PMC12884657`; PMID `40945528`.

**Exact main-text locators (PMC HTML, not verified publisher pagination):**
- **Methods > Search and selection, lines 461–462**: databases/registries searched and trial representatives invited to supply individual-level data.
- **Methods > Data collection, lines 463–482 (especially 469–471, 475–477)**: de-identified trial participant datasets received, independently checked and harmonized, merged and processed; prespecified BMI Z endpoint age 24mo ±6mo; two-stage randomized-trial IPD methods and one-stage sensitivity described; *aggregate data when unavailable were separately sourced*, not disguised as participant records.
- **Results > Study profile, lines 486–489**: 47 completed eligible trials; 18 measured primary endpoint (9,383 eligible); 17 shared true IPD (9,128 participants); the 18th trial's aggregate report was NOT included for primary endpoint per authors' documented decision rules. Trial list includes more reports and secondary outcome contributors (31); the count bases are distinct.
- **Results, line 606, and Table 2 lines 611–619**: primary BMI Z analysis 6,505 with observed endpoint, missing 2,623; mean difference −0.01 (95% CI −0.08 to 0.05). This is a *source-quoted estimate only*, not independently reproduced or certified.
- **Table 2 footnote lines 642–650 and Figure 2 caption lines 658–663**: two multi-arm trials (Wen 2022, Taylor 2017) and paper states approximate adjustment for shared controls to avoid unit-of-analysis errors. This is a **NO_FLAG** disclosure control; *the adequacy of the published covariance handling is not independently replayed*.
- **Data sharing, lines 810–813**: TOPCHILD obtained limited permission but does not own all original trial IPD; data dictionary / IPD released only under moderated approval and cross-institution agreement. SAP located by article to **appendix pp 8–119**, example code pp 234–236; those appendix pages were **NOT accessed/read** in this run. Reported registered TOPCHILD study protocol [Hunter et al., BMJ Open 2022, DOI 10.1136/bmjopen-2020-048166](https://doi.org/10.1136/bmjopen-2020-048166), and PROSPERO `CRD42020177408` require original source-version checks. BMJ publisher fetch returned 403 in this run.

**Source-attested design decision:** **TRUE TRIAL IPD, TWO-STAGE primary analysis**. Not pseudo-IPD; not merely aggregate; not pooled observational registry. Published primary difference is necessarily smaller than total eligible randomized count due to endpoint and IPD availability.

**NO_FLAG controls (2 source-level claims):** (1) Reported endpoint observed 6,505 + missing 2,623 = 9,128 with supplied IPD (local Python integer arithmetic PASS); not a discrepancy between 9,128 and 6,505. (2) Reported eligible participants 9,383 − 9,128 = 255 not available as IPD from the one missing trial, and authors did not substitute aggregate effects into the primary analysis; not an unexplained 'missing trial' or duplicate. A third benign control: Table 2 explicitly describes a multi-arm adjustment; no source attests ignored shared-control covariance. These are bounded negative checks, **not proof of flawless data or correct analysis**.

**Best benign explanations:** trial inclusion counts refer to different eligibility/endpoint/availability populations; aggregate report of the unshared trial intentionally excluded from primary estimate; some participants lack outcome but were in shared trial IPD. Model differences and multi-arm adjustments require exact trial-specific data before determining whether they were appropriate.

**Replay / protocol / corrections:** **HOLD**: restricted participant data and historic executable analysis inputs unavailable; appendix SAP and original corrections/VoR not fully examined. No trial-level original IPD, covariance matrix, analysis code execution, true clinical effect confirmation, model comparison or independent adjudication claimed. Stable claim root `doi:10.1016/s0140-6736(25)01144-4|2025-09-10-lancet-VoR-unverified|ipd-provenance-17of18`.

## S00-02 — true IPD *methodology demonstration* with simulations: Siegel et al. (PARTIAL)

**Identity:** Siegel LK et al. “Examining covariate-specific treatment effects in individual participant data meta-analysis: Framing aggregation bias in terms of trial-level confounding and funnel plots.” *Research Synthesis Methods* 2026;17(1):194–209, first online 23 October 2025. DOI `10.1017/rsm.2025.10043`; PMCID `PMC12823212`; PMID `41626891`. Accessible [PMC full-text publisher article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12823212/) says CC BY 4.0, but related supplements, whole code history, and data licenses were not inspected.

**Exact locators:**
- **Section 2 'Motivating example', PMC lines 163–167**: TICO/ACTIV-3 master protocol investigates five passive-antibody therapies; cites prior Knowlton IPD synthesis with a sixth ITAC trial, **but present application is five TICO/ACTIV-3 trials**; shared placebo patients *can be shared across eligible trials*. A participant counted within a particular trial is assigned that agent or its matched placebo. Distinct article family versus patient family is essential: the five apparent trials do NOT establish five disjoint participant sets.
- **Section 4.2 'Data-generating mechanism', lines 178–181**: synthetic illustration generates **100,000 fabricated participants per trial for each hypothetical scenario**; must NEVER be interpreted as real RCT enrollment or discovered participant totals.
- **Section 9 'Application to ACTIV-3/TICO', lines 291–304**: empirical application fits Fine–Gray competing risk regressions separately by trial and one-stage pooled model, Figure 5. Stratified treatment–serostatus interaction rRRR 1.19 (95% CI 1.01–1.39) and unstratified 1.18 (95% CI 1.01–1.39), source-reported not reproduced.
- **Data availability lines 325–327**: original authors state data at https://public-data.ccbr.umn.edu/ and public R code https://github.com/liannesiegel/TrialLevelConfounding. These locations are bibliographically verified from text **only**. Actual data contents, trial-level study IDs, full executable code/versions, access terms and reuse permissions NOT independently retrieved.

**Source-attested decision:** *Original individual-level trial-data illustration* plus *clearly separate simulations*. Not an exclusively simulated or aggregate-only article; it is primarily an **IPD methodology paper, not a novel six-trial clinical-effect meta-analysis**. **NO_FLAG** that generated synthetic simulations are separate from real data. **HOLD**, not REVIEW_CANDIDATE, for the real paper's shared-placebo dependence: reuse of participant placebo data is disclosed, but the published exact covariance/dependence handling, true participant identities, results of an executed replay, and whether any error occurs were not established. Do **not** infer overlapping trial controls were used as independent effects just from mentioning shared placebos.

**Replay / correction:** **HOLD** pending public license/version and permissible data/code verification; no attempt to pull raw participant records or execute analysis. Family key `doi:10.1017/rsm.2025.10043|2025-10-23-cambridge-published|provenance-empirical-vs-simulation`. Related previous Knowlton IPD meta-analysis is **another paper/family**, not a second credit in this record.

## S00-03 — *reconstructed KM pseudo-IPD*, not original trial IPD: Campbell et al. (PARTIAL)

**Identity:** Campbell H et al. “One-step parametric network meta-analysis models using the exact likelihood that allow for time-varying treatment effects.” *Research Synthesis Methods* 2025;16(4):650–671. Publisher [Version of Record full HTML](https://doi.org/10.1017/rsm.2025.21), Cambridge online 15 May 2025; DOI `10.1017/rsm.2025.21`; publisher page says CC BY 4.0.

**Exact publisher locators:** article **Section 4 'Illustrative examples with existing empirical data', paragraphs 1–3 (Cambridge HTML lines 685–690)**: connected network of ten advanced-melanoma RCTs, published 1991–2004, with KM curves digitized using DigitizeIt; **event and censoring times reconstructed using Guyot et al algorithm**. **Figure 4 caption** specifically labels *reconstructed* times. Article highlights in publisher HTML lines 550–554 likewise explicitly describe reconstruction. Publisher **Data availability / Supplementary material** near lines 783–793 offers example data and Stan/R code in supplementary materials; those materials **not inspected or executed** in this run.

**Design verdict:** RECONSTRUCTED KAPLAN–MEIER PSEUDO-IPD in an IPD-level NMA computation. It legitimately permits fitting individual-time likelihood models on approximations but is **not confirmed original trial participant data**; therefore exclude this article from the genuine shared-IPD clinical-synthesis denominator. **NO_FLAG**, because reconstruction and its limits are transparently disclosed; describing a “one-step” model is not proof of original source IPD. Strong benign explanation for a naive 'mislabelled IPD' allegation: methods use reconstructed individual records and explicitly explain how derived. **HOLD** for empirical model replay: underlying extracted KM, event-time reconstruction calibration, package versions, permissions and original source RCT identity not independently verified. Family key `doi:10.1017/rsm.2025.21|2025-05-15-cambridge-VoR|km-reconstruction`.

## Source manifest / access inventory

| ID | Source | Source access during this run | Exact useful locator |
|---|---|---|---|
| S00-01a | TOPCHILD [PMC author manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC12884657/) | PARTIAL, HTML main body read; not VoR | Methods/Data collection; Results; Table 2; Figure 2 caption; Data sharing |
| S00-01b | TOPCHILD [Lancet publisher VoR](https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(25)01144-4/fulltext) | HOLD, 403 | DOI/Version of Record link only; NO text comparison |
| S00-01c | TOPCHILD appendix/SAP linked from PMC manuscript | HOLD, supplement content not accessed | Article-reported appendix pp 8–119 SAP, pp 234–236 example code; pointers only |
| S00-01d | [TOPCHILD protocol DOI 10.1136/bmjopen-2020-048166](https://doi.org/10.1136/bmjopen-2020-048166) | METADATA pointer / BMJ publisher 403 | Article References no.30; actual protocol/version audit HOLD |
| S00-02a | [Siegel full article, PMC12823212](https://pmc.ncbi.nlm.nih.gov/articles/PMC12823212/) | PARTIAL; main HTML and key sections | §2, §4.2, §9, Data availability |
| S00-02b | [Siegel public code repo](https://github.com/liannesiegel/TrialLevelConfounding) and [data location](https://public-data.ccbr.umn.edu/) | METADATA pointer (stated in article), not inspected or reproduced | Data availability |
| S00-03a | [Campbell Cambridge publisher VoR](https://doi.org/10.1017/rsm.2025.21) | PARTIAL; full HTML available, selected sections read | §4, Figure 4 caption, Highlights; supplement not accessed |
| S00-03b | Campbell supplementary R/Stan example data/source | HOLD, publisher-linked supplementary content not read | Data availability / Supplementary material |

Correction-notice search: no correction affecting a specific reviewed claim was source-verified in this bounded pass. **This does NOT prove no correction exists.** Full original trial registry/SAP identity, licencing, public-code replay, and corrected article version follow-up remain mandatory before escalating any candidate.

## Explicit accounting and epistemic limits

- **Article-family screen / discoveries:** 3 unique DOI families **owned by shard 00**; 1 genuine clinical **two-stage** trial IPD meta-analysis, 1 **real-IPD application in a methods paper** (plus separate simulation), 1 **reconstructed KM pseudo-IPD methodology** (not counted as true-IPD discovery). No pooled-registry or solely aggregate-only paper happened to be reviewed in this bounded sample; no claims about prevalence of other designs.
- **Article access:** **FULL 0 / PARTIAL 3 / METADATA-only 0**; many linked *source documents* remain metadata/HOLD. A full HTML body was located for two, but FULL evidence-stack audit was not achieved.
- **Disposition at distinct source-observable checks:** **REVIEW_CANDIDATE 0; REFUTED 0; INDEPENDENTLY_ADJUDICATED 0; NO_FLAG 5**: TOPCHILD outcome-missingness arithmetic; TOPCHILD missing source-IPD trial; TOPCHILD disclosed multi-arm handling; Siegel synthetic-vs-empirical separation; Campbell reconstructed data correctly labelled. These are checked **negative controls**, not five verified correct papers.
- **Replay:** **3 article-level HOLDs**, one each; no IPD analysis replay, no original fitted model, no meta-analysis result reproduced. Additional subclaim HOLD: TOPCHILD published VoR/SAP/PROSPERO and correction history; Siegel shared-placebo dependence/model identity and code/permission; Campbell KM reconstruction calibration and executable code.
- **Source-check arithmetic:** local Python `assert 6505+2623==9128`, `assert 4549+4415+164==9128`, `assert 9128+255==9383`; all **PASS**. DOI SHA-256 modulo-10 routing computed with Python (full hashes above). **No other numeric analysis run.**
- **Reviewer burden:** actual human reviewer minutes / independent masked assessments **NOT_MEASURED**. Three article main-text sources, multiple repository docs, and cited source pointers were inspected; cannot estimate prospective reviewer cost from this run.
- **Code/PR/CI status:** immutable evidence-only file, no changes to software/tests/automations or prior draft PR #67; **full current-head CI NOT RUN / NOT VERIFIED**, independently approved medical adjudication **none**, no email sent. Do not claim a successful GH check from creation of this file.
- **Static/dynamic hardcode disclosure:** fixed classifications and status definitions are audit rules, not measured sensitivity; DOI/title/counts/locators dynamically extracted from cited public articles and independently checked in limited arithmetic; no synthetic vectors masquerade as actual participant records, no raw data or private correspondence included.

## Next cursor / handoff

`shard00:after-discovery-01|TOPCHILD:publisher-final-VoR+appendix-SAP-pp8-119+correction-scan+register-CRD42020177408|TICO:public-code-licence+shared-placebo-covariance|Campbell:KM-provenance+supplement-code|next-owned-DOI`.

Follow-up: verify complete TOPCHILD supplement/VoR/protocol/SAP and correction history against the exact claims; for TICO verify code and permitted public source material without publishing raw participants, and test whether reused placebo observations are modeled appropriately before any possible REVIEW_CANDIDATE; for Campbell evaluate reconstruction reproducibility with permitted non-identifying/synthetic fixtures. Then continue a fresh **shard-00**-owned DOI not already credited elsewhere. Forward methodological cross-lens questions to owners without counting new distinct case IDs. No outbound contact or merge without new case-specific authorization and exact-head independently verified CI/approvals.
