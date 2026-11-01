# Synthesis NMA outcome-by-outcome source-integrity protocol — v0.1 candidate

**Date:** 1 November 2026  
**Status:** DEVELOPMENT RULE CANDIDATE — **not incorporated into the authoritative Synthesis Evidence Integrity Operating Standard v1.2**  
**Intended owner:** Synthesis methodological steward with independent statistical/clinical review  
**Scope:** systematic reviews and network meta-analyses (NMAs) of trials, initially pharmacological heart-failure NMAs; portable to other disease areas.

## Why this candidate exists

The 1 November 2026 HF audit exposed a recurrent combination of problems: distinct reports of one trial presented as distinct randomized trials; event totals mistaken for participant totals; first and recurrent hospitalizations combined as binary events; one-year and entire-follow-up outcomes mixed; cardiac versus HF-specific hospitalizations conflated; safety populations and denominators mixed; effect-modifying trial selection/run-in and background therapy obscured by broad drug-class nodes; masking/comparator and numerical transcription errors persisting across review updates; and ranking claims exceeding the reported comparative intervals.

The methodology should catch these **without equating a suspicious table with a proven model error**, and without assuming that all trial results or NMAs are wrong. A correct source record can disagree with a crude diagnostic because the original outcome is time-to-event, stratified, adjusted, recurrent or differently censored. Every candidate error requires an explicit alternative explanation and a matched-estimator check.

This protocol **extends** the existing [Synthesis Preflight v1.1](SYNTHESIS-PREFLIGHT-v1.1.md) claim-ledger/abstention controls. It **does not replace** Synthesis v1.2, the open v1.3 candidate, Meta-Harness, protected E156 source records or any prospective frozen cohort.

## Mandatory unit and denominator

The atomic audit object is **(review DOI, reported outcome ID, target population/EF subgroup, contrast, follow-up window, estimand, analysis set, effect measure)**. Every claim/figure/table value is recorded, including values that pass checks, and every primary source may contribute multiple outcomes without becoming multiple independent trials.

For each outcome, retain the complete original claimed denominator: all included reports, parent RCTs, arms, available event definitions, missing/unavailable sources and exclusions. Never report an error rate or a number of independently checked outcomes using only detected anomalies as the denominator.

| Required field | Meaning / fail-closed test |
|---|---|
| `review_doi`, `review_version`, `reported_result_locator` | Exact current published edition; section, table, figure, supplement cell, date and any correction history. |
| `predecessor_review_doi`, `shared_registration_id`, `cross_review_cell_lineage` | Identify earlier versions of a review and repeated table entries (including anomalous Ns, endpoint codes and design labels). Mark `REUSED_REPORTING` separately from `MODEL_DATA_REUSED`, which requires proof from exact input rows. Do not imply that an explicitly updated review improperly used its earlier extraction. |
| `search_cutoff`, `source_publication_date`, `post_cutoff_capture_log` | Check the dated search/PRISMA trail whenever an included original results report postdates the claimed database publication cutoff. A documented manual capture or revision is a valid explanation; absence of a log requires clarification, not exclusion by assumption. |
| `outcome_id`, `outcome_definition`, `population_id`, `ef_rule` | Exact outcome, HF subtype, EF eligibility, symptomatic status and target PICO. |
| `parent_trial_id`, `report_doi`, `registry_id`, `subset_relation` | Registry-linked independent RCT, publication, subgroup/report inclusion and parent–child relationship; do not infer independence from author/year. |
| `arm_id`, `comparator_id`, `randomized_n`, `analysis_n`, `safety_n` | Exact arm, experimental/reference orientation and denominator type from the original source. |
| `endpoint_unit` | `PEOPLE_FIRST_EVENT`, `EVENTS_RECURRENT`, `RATE_PERSON_TIME`, `TIME_TO_FIRST`, `COMPOSITE_PEOPLE`, `CONTINUOUS`, `OTHER`, or `UNRESOLVED`. |
| `event_count`, `person_count`, `time_origin`, `followup`, `censoring` | Distinguish admissions from people; label first-year versus full follow-up and time at risk. |
| `outcome_available`, `source_outcome_code`, `outcome_edge_count` | Reconcile the paper's trial-level outcome availability table with every claimed outcome-specific graph, treatment estimate and figure; an absent code needs an explanation, not invented input. |
| `effect_measure`, `effect_of_interest`, `adjustment`, `model_signature` | HR/RR/OR/rate ratio/mean difference, ITT/assignment or adherence, stratification, repeated-event model, CI method. |
| `source_url`, `source_locator`, `source_version`, `retrieval_status`, `source_hash` | Original paper/registry/protocol/SAP and what exactly was accessed. Never invent inaccessible files. |
| `reported_estimate`, `reported_interval`, `authors_input`, `reproduced_estimate` | Keep reported, original-model-replayed, and independently repaired values separately; never substitute approximate crude ORs for author estimates. |
| `implied_se`, `information_bound`, `precision_explanation` | Compare displayed interval precision to the maximum information in the listed unique populations for an explicitly specified likelihood; check hidden independent data, hierarchical borrowing and shared controls before alleging an impossibility. |
| `rob2_domains`, `rob_nma_domains`, `transitivity_matrix`, `cinema_domains` | Outcome-specific judgments with exact justification and independent-review status. |
| `benign_explanation`, `refutation_result`, `severity`, `evidence_maturity`, `outreach_hold` | Strongest plausible non-error explanation, checked answer, materiality, provenance, and communication gate. |

Missing essential source/estimand/parent-trial identifiers yields **HOLD**, never presumed duplicate, assumed model failure or invented data.

## Four-pass auditing protocol, executed for every outcome

### Pass 1 — source and trial-family reconstruction

1. Freeze the review and its supplements at the current publication version. Include appendices, correction notices, protocol/registration and dated changes.
2. Enumerate each explicitly claimed outcome; group by HF phenotype and estimand, **not** just by a single broad class outcome. Enumerate all conclusions and rankings that depend on those results.
3. Assign original study publications and subgroup analyses to a source-verified parent RCT (registry ID and arm relationship). Label `SAME_PEOPLE`, `SUBSET_OF_PARENT`, `NONOVERLAPPING_PARTITIONS`, `INDEPENDENT_TRIAL`, or `UNRESOLVED`.
4. Record **for each arm/outcome** whether a numerator means people, recurrent events, first events or person-time rate. Reject as a standard binomial person-count input any event total exceeding the relevant randomized/at-risk person count. Do not mistake valid recurrent events for fraud; they are valid when analysed appropriately.
5. Check placebo/active comparator, drug molecule and class-node coding, crossover, factorial/multi-arm shared controls, dose, background therapy and eligibility of every trial (symptomatic HF, EF cut, renal threshold, recent hospitalization, trial era).
6. Cross-check trial extraction tables against original primary reports and supplementary event tables; document both value and **endpoint identity**. A numerically equal count for cardiac admissions is not proof it is HF admissions.
7. Verify that each named treatment has an observed outcome-specific source edge wherever the review estimates that outcome; reconcile every trial's reported outcome-code availability with network diagrams and Results, retaining `UNRESOLVED` if source inputs are hidden.
8. For an updated NMA, compare the predecessor's published trial/outcome/denominator/design table **cell by cell** against the new version. Preserve unchanged normal entries and repeated anomalies, source the shared protocol/registration and correction history, and explicitly distinguish **transmission of reported text** from **use of erroneous numbers in the statistical model**. An impossible printed denominator is a reporting error but does not by itself establish a fitted-data error.
9. Crosswalk every EF-restricted network or subgroup label against original **subgroup-specific arm Ns** and results, distinguishing full trial EF >40% from an EF ≥50% analysis. Audit the original publication date of each included results report against the stated review search cutoff; log trial-results additions made at manuscript revision. Treat one-person randomized-versus-analysis N differences as unresolved until the analysis-set definition is found.

### Pass 2 — exact original-model reproduction

1. Obtain the author extraction matrix and runnable code/model specification, including all trial-arm events, covariance for multi-arm/overlapping subsets, zero-cell treatment, heterogeneity estimator, link and likelihood, priors if Bayesian, follow-up, confidence or credible intervals, ranking code and versioned statistical environment.
2. **First reproduce the printed NMA without repairing it.** Compare every reported effect, CI, treatment rank and network topology. Record any differences from rounding, package version or unidentified input.
3. If original code is unavailable, reconstruct a **labeled diagnostic** using published data and record all assumptions; do not call it a reproduction, conclude an exact hidden implementation, or present its changed CI as a formally corrected publication.
4. Before each comparison verify estimator identity: recurrent-event rate model versus people with an event, HR versus risk/odds ratio, adjusted versus crude, Cox/KM versus raw proportions, outcome time horizon, competing terminal events, and analysis population.
5. For single-edge drug nodes or suspect duplicate clusters, calculate a **conditional information-budget check**: derive the SE implied by the displayed interval and bound plausible binary contrast precision using unique source Ns/events, network geometry and allowed correlation. Record the assumptions and benign alternatives (additional unlisted RCT, adjusted survival likelihood, legitimate hierarchical shrinkage, class borrowing) before treating an overly narrow CI as a source/data problem. A contrast-only bound does **not** apply universally to complex joint NMA models.

### Pass 3 — corrected and stress-tested outcome-specific network

Run and archive a delta for each correction **separately**, then jointly when defensible:

1. One independent parent trial contribution per estimand, or valid correlated/joint model of deliberately reused cohorts. Distinguish a true separate RCT with a similar title from multiple publications of the same RCT.
2. Compatible event units and measures: first event, recurrent HF admissions, CV-death/HF composites, serious versus all adverse events, cardiac versus HF hospitalisations, time-to-event and follow-up windows. Split incompatible networks or use a justified joint likelihood; never relabel recurrent admissions as people.
3. Correct source arm denominators: randomized/ITT, modified ITT, treatment-exposed safety and per-protocol as required for each outcome. Recheck deaths during run-in and ascertainment before/after randomization without allocating pre-randomization failures to later randomized arms.
4. Align eligibility and transitivity: EF bands, symptom status, background therapies, trial era, comparator type and run-in selection, geography, baseline renal risk, follow-up, dosing. Evaluate these as potential effect modifiers; **difference in design alone does not prove a biased effect**.
5. Test drug-class node sensitivity: molecule-specific ACEI/ARB/ARNI/RASi nodes; document network connectivity when nodes split. A disconnected contrast is **not identified**, not a zero effect. Explain class-effect assumptions when needed to keep a network connected.
6. Handle multi-arm correlations separately from repeated publications. Do not apply a standard multi-arm covariance formula to full parent/subgroup duplicate rows; use compatible dependence models or remove overlap.
7. Examine heterogeneity, fit, direct–indirect coherence **where identifiable** (do not demand node-splitting in a network with no loops), rank uncertainty, and small-study or missing-evidence concerns. Do not make superiority claims from SUCRA/P-scores without a supported pairwise contrast and interval.
8. For every reported outcome produce a `PUBLISHED -> EXACT_REPLAY -> ONE_FIX -> ALL_FIXES` evidence trail: effect/CI, direction, statistical significance if relevant, absolute effects where appropriate, network nodes/edges, contributors, influence and robust conclusions. Report when intervals widen and benefits persist, not just changes crossing 1.

### Pass 4 — domain-correct risk of bias and release gate

- **RoB 2:** a **trial-result-specific** assessment of randomization, deviations from assigned intervention, missing outcome data, outcome measurement and selective reporting. Record effect of assignment/adherence, source locators and independently adjudicated judgments. Pre-randomization active run-in is usually a **generalizability/indirectness** issue rather than automatically high risk for the randomized post-run-in effect; postrandomization attrition requires separate consideration.
- **ROBIS:** review-level methods for eligibility, study selection, data collection/appraisal and synthesis; not interchangeable with RoB 2 or RoB NMA.
- **RoB NMA (2025):** outcome-specific 17-item assessment across network geometry/interventions, effect modifiers and statistical synthesis. Do not mechanically fail a design merely because no direct–indirect test is possible in an acyclic network; retain appropriate `no information` entries.
- **ROB-MEN/ROB-ME:** missing-evidence/reporting-bias evaluation as applicable; absence of a significant funnel test is not proof of no reporting bias.
- **CINeMA:** outcome-specific comparison-level confidence (within-study bias, reporting bias, indirectness, imprecision, heterogeneity, incoherence); map exports to the actual outcome; do not count domain concerns as an automatic numerical score.

**External correspondence is HOLD unless all three are documented for that specific paper/outcome:**

1. Every disputed source count/endpoint/denominator independently verified from the actual original report, with a checked benign alternative and second qualified reviewer where appropriate.
2. Printed NMA exactly reproduced using original settings, then repaired using unique parent populations and compatible estimands, with appropriate outcome-specific RoB 2 and RoB NMA; if code/data are unavailable, clearly state that a full corrected result **cannot yet** be claimed and request the missing data through an approved route.
3. Changed versus unchanged conclusions documented with code, confidence intervals and sensitivity analyses; a separate source-backed, nonaccusatory author/journal request prepared and approved for **that paper only**, with contact de-duplication and user approval before sending.

Nonresponse is not evidence of intentional wrongdoing; corrections, editorial review and any ethics escalation must be proportional to independently verified reliability problems.

## Falsification / negative controls required in development

Include matched counterexamples so the protocol does not train a detector to always condemn a review:

1. Recurrent hospitalization counts correctly analysed in a negative-binomial/recurrent-event likelihood — **do not flag merely because count > people**.
2. First-year event numbers explicitly labelled and separately analysed as a prespecified one-year endpoint — **do not flag full-follow-up mismatch if no mixing**.
3. One trial with subgroup and whole-cohort reports listed in *bibliography* but only one contributes to fitted outcome — **descriptive overlap, not analytical double count**.
4. Distinct trials with similar names (e.g. prevention versus treatment) and separate randomized populations — **not duplicates**.
5. Valid multi-arm RCT with a shared control modelled with correlation — **not double-counting**.
6. Different safety/randomized/per-protocol populations correctly assigned to their intended endpoints — **not an error**.
7. Run-in exclusions followed by proper randomized ITT estimate and explicit population limitation — **no automatic RoB 2 failure**.
8. Active-comparator trial correctly connected through a prespecified, clinically justified class node, with transparent sensitivity — **possible assumption, not automatic error**.
9. Correct but different Cox HR versus crude 2×2 OR — **not comparable**.
10. NMA with no closed loops and no feasible coherence test — **do not claim missing test proves bias**.
11. A non-significant head-to-head estimate but numerically highest SUCRA — label rank uncertainty; do not allege computation error without source contradiction.
12. Current corrected journal version resolves an older table typo — flag as **resolved history**, not an ongoing defect.
13. A published treatment node with few direct events legitimately gains precision from **specified** hierarchical class borrowing or other independently observed constraints — test the full stated likelihood and structure before alleging impossible precision.
14. An updated review transparently reuses its predecessor's trial table, including a typographical denominator error, but its **separately verified fitted dataset uses valid Ns** — retain the reporting correction and do not assert a changed clinical effect or misconduct.
15. A trial report published after the initial database cutoff was appropriately added through a dated review update or peer-review revision — record the chronology and **do not** allege selection bias from the date difference alone.

These are **proposed fixture descriptions only**. No test code or independently sampled validation was executed by publishing this document.

## Outputs and integration contract

- `source_registry`: exact source IDs, versions, retrieval path, locators, hashes and access failures.
- `trial_family_map`: independent parent RCT and publications/subgroups; overlap/missing status, source-backed.
- `cross_review_lineage`: predecessor DOI and registration, exact reused table cells and status, corrected edition, and a separate proof field for **whether the model actually imported a disputed value**.
- `outcome_ledger`: every reported network/outcome/contrast; no missing unflagged outcomes; source and analysis statuses.
- `replay_manifest`: author original code/options/input, actual run command, environment and differences; `UNAVAILABLE` if not obtained.
- `corrected_manifest`: one-at-a-time and joint sensitivity, network topology, estimates and appropriate intervals.
- `bias_ledger`: RoB 2 per trial/outcome and RoB NMA per review network/outcome, ROBIS/CINeMA as suitable, with independent-review signature/status.
- `editorial_packet`: only independently verified case-specific concerns, no mass allegations or private correspondence in public git.

**Status vocabulary:** retain Synthesis Preflight v1.1 `SUPPORTED`, `CONTRADICTED`, `OVERGENERALIZED`, `UNSUPPORTED_CITATION`, `SOURCE_UNAVAILABLE`, `NOT_ENOUGH_INFO` and evidence maturity. Add an orthogonal `model_impact_status` with `NOT_TESTED`, `DIAGNOSTIC_ONLY`, `AUTHOR_REPLAYED`, `REPAIRED_SENSITIVITY`, `INDEPENDENTLY_ADJUDICATED`; do not imply scientific validation from passing schema tests.

## Provenance, reuse and hardcode disclosure

| Ingredient | Current status | Reuse or new |
|---|---|---|
| Synthesis Evidence Integrity v1.2, Preflight v1.1 and open v1.3 | Existing standards and candidate work; no changes made here | **Reuse** claim enumeration, provenance, abstention and source/estimator gates. |
| Meta-Harness / E156 provenance and exact-head CI | Existing verification machinery; not invoked or reconfigured by this document | **Reuse** numerical replay, source receipt and protected independent-review controls. |
| Outcome-specific parent-trial / estimand / bias matrix | Proposed reporting method | **New** explicit ledger and source-to-model-to-conclusion lineage. |
| Numeric HF examples | No live numeric data or hardcoded clinical result in this public method; all actual findings stay in restricted case dossier | **Neither** fixture nor benchmark. |
| Frozen Simo/independent cohorts | Unchanged and **not** used to develop/validate this proposal | **Protected**, excluded from changes. |

### Validation and promotion

1. Methodological steward and an independent clinical statistician review proposal; resolve inconsistencies with the canonical v1.2 and the open v1.3 branch before accepting numbered rules.
2. Implement and test at least the twelve positive/negative fixtures with source-attested metadata, then verify exact-head CI and cross-platform/parity gates; maintain zero private cases in public tests.
3. Compare prospective sensitivity, precision, false alerts, serious misses, abstentions, sources retrieved and reviewer time on a separate **precommitted unseen sample** with masked independent human adjudication. Do not re-use or modify frozen validation cohorts.
4. Report adverse results and unchanged conclusions. A proposed protocol, past retrospective case matches or synthetic tests alone do not establish detector performance.
5. No merge to canonical method, protected record change, schedule change, email, editorial contact or ethics referral is authorized by opening a draft PR.

## Authoritative methods references

- Cochrane Handbook Chapter 11 (NMA transitivity, geometry, estimands): https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-11
- Cochrane RoB 2: https://www.cochrane.org/learn/courses-and-resources/cochrane-methodology/risk-bias/about-risk-bias-2-rob-2
- RoB NMA development, *BMJ* 2025: https://doi.org/10.1136/bmj-2024-079839
- ROB-MEN missing evidence: https://pubmed.ncbi.nlm.nih.gov/34809639/
- ICMJE on correction and major reanalysis: https://www.icmje.org/recommendations/browse/publishing-and-editorial-issues/corrections-and-version-control.html
