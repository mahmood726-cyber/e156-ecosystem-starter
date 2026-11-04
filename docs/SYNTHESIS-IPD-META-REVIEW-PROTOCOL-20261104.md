# Synthesis IPD meta-analysis review campaign — 10 workstreams

Date: 4 November 2026. **Status: research protocol; not a claim that reviews, discrepancies, clinical adjudications, or benchmarks have been completed.**

## Mission and migration gate

Run ten evidence-led, deduplicated reviews of **individual participant data (IPD) meta-analyses** in medicine, updating the Synthesis experimental audit workflow only when authentic source-backed cases reveal a generalizable problem. Historical correction-learning work is preserved independently on branch `synthesis/correction-learning-10k-20261103` and open draft PR #67, with the handoff checkpoint `docs/SYNTHESIS-CORRECTION-LEARNING-HANDOFF-TO-IPD-20261104.md`. That checkpoint explicitly reports the missing shard-09 evidence and cannot certify unsaved automation output. Do not merge, overwrite, delete, or relabel that evidence as IPD work.

## Always use the latest verified Synthesis main revision

At the **start of each invocation**, fetch repository `AGENTS.md`, current `main` commit SHA, `docs/SYNTHESIS-v1.3-CANDIDATE.md`, and relevant live implementation/docs. Use whatever Synthesis version is **actually latest on main**, recording SHA and document/version in each report; do not blindly pin to v1.3 or an old branch. As of this protocol's creation, the documented v1.3 is an **experimental, limited** integrity checker; `scripts/synthesis_v13_nma_preflight.py` flags narrow caller-attested NMA/IPD readiness/integrity conditions and **does not compute native IPD meta-analysis models or independently authenticate study results**. If code/doc versions differ, report and fail closed rather than guessing.

## Eligibility and sources

Include original, published medical IPD meta-analyses, including one-stage or two-stage randomized-treatment effect syntheses, IPD prognostic/diagnostic meta-analyses, and clearly identified hybrid IPD + aggregate-data meta-analyses (label hybrid explicitly). Find candidates in PubMed/MEDLINE, publisher full texts and supplements, trial registrations, protocols, registries, data repositories and source code. Prefer accessible published analysis outputs with registered methods and source-located estimands. Exclude ordinary aggregate-data meta-analyses merely mentioning IPD as a possibility. Record whether actual anonymized participant-level data/code are public, restricted, unavailable or unassessed; **do not infer IPD access simply from an article claiming IPD meta-analysis**.

Respect study rights, patient privacy, governance and licences: publish only non-sensitive article metadata, public source locators, permitted derived calculations and synthetic test fixtures. Never put raw participant rows, pseudonymized patient-level records, restricted documents, private emails, credentials, journal PDFs or full copyrighted articles in this public GitHub repository.

## Ten task lenses (same evidence gates; complementary methodological emphases)

| Task | Lens / primary question |
|---|---|
| 00 | IPD evidence discovery, article/registration/version provenance, source access and correction/retraction status |
| 01 | Eligible trial/cohort identity, overlap, participant flow, data availability, contributed-versus-eligible studies and denominators |
| 02 | Outcome and follow-up harmonisation, population definitions, endpoint measurement and source-to-analysis consistency |
| 03 | Within-trial treatment–covariate interactions, ecological bias, patient-level vs trial-level modifier interpretation |
| 04 | One-stage vs two-stage models, pooling weights, between-study heterogeneity, random effects and small-study uncertainty |
| 05 | Survival IPD analyses: Cox stratification/frailty, censoring, time origin, competing risks, proportional-hazards assumptions |
| 06 | Missing participant data, absent-study IPD, imputation, selection mechanisms and differential availability bias |
| 07 | Prognostic/diagnostic IPD models: calibration, discrimination, clustering, validation, thresholds and optimism |
| 08 | Reporting integrity: tables/figures/supplements/code, effect-direction/units/precision, protocol deviations, RoB and sensitivity |
| 09 | Independent replication readiness, benign controls, held-out evaluation, false-positive review burden, coordinated methodological improvement PRs |

Every task may review cross-lens issues in the IPD paper it owns. Lenses are not proof of correctness or automatic error classifiers.

## Routing, deduplication and progress

Ten **hourly** workstreams, six-minute offset in Europe/London: shard 00 at :00, 01 :06, 02 :12, 03 :18, 04 :24, 05 :30, 06 :36, 07 :42, 08 :48, 09 :54. The offsets do **not guarantee** runs cannot overlap when a run exceeds six minutes.

Canonical article identity is normalized original IPD synthesis DOI (or PMID, then stable primary-publisher URL if DOI missing); SHA-256(canonical key), unsigned big-endian integer mod 10, determines the owning worker. Article aliases, multiple reports, IPD trial families and multi-outcome papers require explicit separate keys; hand non-owned articles to the owner without counting them. A study can contain multiple independently evaluated claims, but do not count the same paper or claim multiple times across runs.

Track separately discovered, eligibility-confirmed, metadata-only, partial-text, source-reviewed full texts, code/data available, attempted reproductions, reproducible issues, refuted cases, HOLDs, and independently adjudicated findings. No fabricated target, no counting candidates as confirmed errors, and no inferred GitHub persistence.

## Per-paper evidence minimum

- Original meta-analysis title, DOI/PMID, publication and version/update dates, corresponding protocols/registration, review type and included trial-family list.
- Precise article/supplement/table/figure locators, original claim and exact source numbers at stated precision; data/code availability and licence/consent status.
- Explicit population, outcome, time window, effect measure, estimand, model and one-/two-stage method; covariate, cluster, missingness, censoring and variance handling.
- Verify which participants were eligible, obtained, excluded and analysed, including missing/failed-to-share trials and aggregate-only data.
- For subgroup or treatment-modifier claims, distinguish within-trial interactions from between-trial/ecometric comparisons; do not confuse participant-level with trial-level associations.
- Cross-check reported outputs and, **only when accessible and permitted**, execute the exact published method before sensitivity/correction runs. Record code/library versions and actual machine-run logs; if no replay, say so.
- Seek strongest benign alternative (different estimands, clustering, adjusted model, imputation, time origin, transformations, rounding, source/version changes). When uncertainty remains, classify `NOT_COMPARABLE` or `HOLD`, not an error.
- Source-supported severity, claim status, materiality, correction status, and independent human adjudication (or explicitly **none**). Separate source-authenticated calculations from heuristic flags and developer synthetic tests.

## Storage, QA and publication gates

Work only on an IPD-specific review branch; proposed initial branch is `research/synthesis-ipd-meta-audit-20261104`. Save unique per-run public evidence files in `research/ipd_meta_audit/20261104/shard-XX/` with next cursor, owner DOI key, access date, Synthesis main SHA, and explicit review depth. Avoid conflicting writes; fetch branch head and use new immutable filenames. If writing fails, report findings as **unsaved**; never silently claim persistent progress.

Keep any checker changes narrow, covered by source-derived paired failing/pass and benign/abstention controls. New methods code must run reproducible tests and documented CI on an exact commit. Shared code and aggregate manifests are coordinated by shard 09 through a distinct reviewed PR. Never assume a synthetic green suite is real-world clinical validity, never edit frozen test cohorts to achieve a score, and **do not merge** without required status checks, independent scientific/privacy review and GitHub-confirmed authorisation.

**No automatic author/journal/sponsor emails in this IPD campaign.** Existing unrelated Nature, Lancet, NEJM or personal automations are outside this ten-task replacement and must not be modified without another instruction.

## Per-run response

Report new candidate papers searched/triaged, unique in-scope additions, full/partial/HOLD counts, specific sources and locators, issues refuted/candidate/independently verified separately, true executed tests vs proposed tests, new file and commit/PR URLs or explicit saving blockers, current Synthesis SHA, and next review queue. If source access or tool approvals block work, perform a smaller useful accessible batch instead of fabricating a result.
