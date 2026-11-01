# Synthesis NMA outcome-by-outcome source-integrity protocol — v0.1 candidate

**Date:** 1 November 2026  
**Status:** DEVELOPMENT RULE CANDIDATE — **not incorporated into the authoritative Synthesis Evidence Integrity Operating Standard v1.2**  
**Intended owner:** Synthesis methodological steward with independent statistical/clinical review  
**Scope:** systematic reviews and network meta-analyses (NMAs) of trials, initially pharmacological heart-failure NMAs; portable to other disease areas.

## Why this candidate exists

The 1 November 2026 HF audit exposed a recurrent combination of problems: distinct reports of one trial presented as distinct randomized trials; event totals mistaken for participant totals; first and recurrent hospitalizations combined as binary events; one-year and entire-follow-up outcomes mixed; cardiac versus HF-specific hospitalizations conflated; safety populations and denominators mixed; effect-modifying trial selection/run-in and background therapy obscured by broad drug-class nodes; masking/comparator and numerical transcription errors persisting across review updates; effect-measure estimates labelled against a wrong reference comparator; EF-defined networks silently containing broader EF cohorts; treatment *assigned* versus *actually received* dose after pharmacy/dispensing anomalies; and ranking claims exceeding the reported comparative intervals.

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
| `review_total_n`, `trial_table_total_n`, `baseline_table_total_n`, `sample_balance_by_trial` | Recompute headline sample size from every displayed trial and baseline arm; decompose cross-table differences by trial and reason (sex subgroup vs arm size; randomized, safety, efficacy, per-protocol) rather than presuming a single universal denominator. |
| `target_dose`, `actual_dose`, `dose_assignment_deviation`, `dose_exposure_n` | Dose planned under randomized assignment, actual titration/dispensing, protocol deviations, onset and number exposed; keep assignment and received-treatment estimands separate. |
| `endpoint_unit` | `PEOPLE_FIRST_EVENT`, `EVENTS_RECURRENT`, `RATE_PERSON_TIME`, `TIME_TO_FIRST`, `COMPOSITE_PEOPLE`, `CONTINUOUS`, `OTHER`, or `UNRESOLVED`. |
| `event_count`, `person_count`, `time_origin`, `followup`, `censoring` | Distinguish admissions from people; label first-year versus full follow-up and time at risk. |
| `outcome_available`, `source_outcome_code`, `outcome_edge_count` | Reconcile the paper's trial-level outcome availability table with every claimed outcome-specific graph, treatment estimate and figure; an absent code needs an explanation, not invented input. |
| `effect_measure`, `effect_of_interest`, `adjustment`, `model_signature` | HR/RR/OR/rate ratio/mean difference, ITT/assignment or adherence, stratification, repeated-event model, CI method. |
| `source_url`, `source_locator`, `source_version`, `retrieval_status`, `source_hash` | Original paper/registry/protocol/SAP and what exactly was accessed. Never invent inaccessible files. |
| `reported_estimate`, `reported_interval`, `authors_input`, `reproduced_estimate` | Keep reported, original-model-replayed, and independently repaired values separately; never substitute approximate crude ORs for author estimates. |
| `abstract_contrast`, `results_contrast`, `figure_contrast`, `effect_orientation` | Cross-check *exact same RR/HR/OR and CI* across abstract, figures, ranking tables and Results to detect switched placebo/active reference labels. A label error is a verified reporting issue but not necessarily a model error. |
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
10. Read the target phenotype definition *in the authors' own text*, then test whether each included whole-trial arm actually matches. For mismatches, enumerate the **known excluded-band participants** (e.g. original 41–49% EF strata within >40% cohorts) and request separate subgroup event counts, without treating the broader cohort as invalid if the authors' true prespecified PICO was HF with EF >40%. Also cross-check trial's original EF rule against the review's Table 1 eligibility and its internally reported mean EF.
11. Cross-validate the **comparison reference and direction** wherever a numerical estimate and CI are repeated in the abstract, Results, forest, league table and conclusions. Do not infer that a correct effect size has the claimed placebo comparator merely because its numerical value is plausible.
12. For dose-finding trials, compare each **target/randomized dose** with actual delivered dose and report any central dispensing or titration error. Reconcile randomized/FAS, treatment-exposed SAF and correctly dosed subsets, ascertain when vital status was measured, and keep deaths after stopping assigned treatment in the assignment estimand unless the original prespecified analysis genuinely differs.
13. Perform **cross-table sample-size mass balance**: independently sum the review abstract/headline total, study roster, baseline-arm Ns and each outcome's model-specific dataset, recording all differences by parent trial and analysis set. A baseline table's male count accidentally printed as its arm N is a real metadata error; a legitimate trial-analysis-subset N is not automatically one. Keep the claim `MODEL_N_WRONG` blocked until the model row is seen. When phenotype-specific subgroups of the same source appear in *separate, disjoint networks*, verify that their partition total equals the published study count without automatically labelling them repeated RCT information.

### Pass 2 — exact original-model reproduction

1. Obtain the author extraction matrix and runnable code/model specification, including all trial-arm events, covariance for multi-arm/overlapping subsets, zero-cell treatment, heterogeneity estimator, link and likelihood, priors if Bayesian, follow-up, confidence or credible intervals, ranking code and versioned statistical environment.
2. **First reproduce the printed NMA without repairing it.** Compare every reported effect, CI, treatment rank and network topology. Record any differences from rounding, package version or unidentified input.
3. If original code is unavailable, reconstruct a **labeled diagnostic** using published data and record all assumptions; do not call it a reproduction, conclude an exact hidden implementation, or present its changed CI as a formally corrected publication.
4. Before each comparison verify estimator identity: recurrent-event rate model versus people with an event, HR versus risk/odds ratio, adjusted versus crude, Cox/KM versus raw proportions, outcome time horizon, competing terminal events, and analysis population.
5. For single-edge drug nodes or suspect duplicate clusters, calculate a **conditional information-budget check**: derive the SE implied by the displayed interval and bound plausible binary contrast precision using unique source Ns/events, network geometry and allowed correlation. Record the assumptions and benign alternatives (additional unlisted RCT, adjusted survival likelihood, legitimate hierarchical shrinkage, class borrowing) before treating an overly narrow CI as a source/data problem. A contrast-only bound does **not** apply universally to complex joint NMA models.
6. For low-count or multi-arm dose-specific mortality/safety outcomes, compute and label an **unadjusted exact/binomial diagnostic** (including the denominator and endpoint as stated in the original safety table); compare the review's implied log-SE and observed result only **conditionally**. Correlated shared placebo arms, network path borrowing, model link and zero-cell corrections must be replayed before making any significance-change claim. A safety-table “AE with outcome death” must not be assumed identical to an ITT all-cause-mortality outcome without checking ascertainment and follow-up.

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
9. For an EF-heterogeneous network, run and clearly distinguish **authors' actual broad target**, the intended strict HFpEF/HFmrEF bands, and *when estimable* cohort-specific sensitivities; if phenotype-specific event data are unavailable, mark the strict comparison **NOT IDENTIFIED FROM PUBLIC DATA**, not an assumed corrected estimate. For randomized target-dose arms affected by dosing errors, record treatment-policy/assignment versus explanatory received-dose sensitivities, including any postrandomization selection bias in a correctly dosed-only comparison.

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
16. A review's abstract mislabels the reference treatment while its forest and internal model use the correct active comparator — **a reporting correction is indicated**, not an assertion that the effect was fitted against placebo.
17. A multi-arm dose-finding RCT has one rare-event safety contrast whose crude Fisher test is nonsignificant, yet a correctly specified joint NMA yields a narrower interval through legitimate information from other independently observed paths — **do not declare an error** from the two-arm P-value alone. Conversely, a randomized target-dose group contains individuals misdosed by the dispensing system: preserve the assignment/ITT deaths even if most occurred after medication cessation; do not silently shift them to per-protocol or erase them.
18. A review's baseline table sums to fewer than its cohort roster because one source displays an expressly defined per-protocol group while the model uses suitable randomized/safety denominators — report the difference and explanation, **not a proven model error**. Likewise, a correctly reported large trial is split into nonoverlapping EF bands for separate outcome networks; adding the bands for an overall descriptive N is **not** duplicate participant weighting within either fitted network.

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


## HF NMA audit additions — 1 November 2026 continuation

The following checks were added after examining Tang et al. (2024), the JACC 2025 HFrEF regimen update, the original VICTOR trial results and the current netmeta P-score definition. These are method rules and audit targets, **not declarations that the corresponding NMA outputs have been independently reproduced**.

### Additional source-to-estimand checks

1. **Follow-up duration and estimand identity.** If a review pools crude risk ratios, record each trial's follow-up duration and time origin. A pooled risk at 2 months and one at 71.8 months are not automatically the same estimand. Verify whether the source is time-to-first-event, fixed-time cumulative risk, rate/person-time, or recurrent-event total. Prefer harmonized time horizons or compatible HR/rate-ratio models where data permit. Run duration-restricted or common-time-point sensitivities; never label a crude RR reconstruction as a reproduction of an adjusted Cox model.
2. **Endpoint numerator identity.** Record for every trial and outcome whether the numerator is number of people with a first event, people with any event, recurrent event count, rate/person-time, or time-to-first-event. Inspect the original report to establish whether HHF is number of people or number of admissions. If definitions differ, split the network or justify the common estimand.
3. **Background-regimen ecological classification.** Where a review labels a regimen from trial-level proportions (e.g. a component is considered present if at least 60% of participants used it), record the exact proportion, source, threshold and whether co-therapies were received by the **same individuals**. A trial-level label does not prove all drugs were jointly received by all randomized participants. Treat such an estimate as ecological/trial-level unless participant-level joint exposure or randomized factorial evidence supports a patient-level interpretation. Test continuous exposure proportions and alternate thresholds; threshold sensitivity does not substitute for patient-level overlap.
4. **Component-NMA assumptions.** Record the CNMA model matrix and component identifiability. Test additivity against prespecified component interactions where the network can identify them; report when interactions are not estimable. Narrower CIs after decomposing combinations are not independent new evidence: trace component contributions and shared trials. Compare standard NMA and CNMA, examine model fit and interaction sensitivity, and do not equate model-implied combinations with directly randomized regimens.
5. **P-score/SUCRA interpretation.** P-scores are frequentist certainty summaries based on relative estimates and standard errors, averaged over competing treatments; they are **not** probabilities that a treatment is the single best. SUCRA summarizes the cumulative ranking distribution, not proof of comparative superiority. Flag wording that calls a P-score/SUCRA a probability of being best. Require pairwise effects, intervals, clinical magnitude and evidence certainty alongside rankings.
6. **RoB-tool generation and target.** Record the exact RoB tool/version. Where an NMA used the older Cochrane RoB 1 tool, do not describe it as RoB 2. For a contemporary reappraisal, perform result-specific RoB 2 for each outcome/timepoint/estimand, retain the original judgements as historical, and record what changes. The presence of RoB 1 is an appraisal limitation requiring update, not automatic proof that all RCT estimates are biased.
7. **Multiplicity and secondary-endpoint hierarchy.** Record each parent RCT's primary endpoint, gatekeeping/multiplicity strategy, secondary endpoints, nominal versus multiplicity-controlled status, and whether a secondary mortality result was independently powered. When a new combination node is driven predominantly by one RCT's nominal secondary endpoint after a failed primary endpoint, flag the incremental component conclusion as exploratory and run leave-one-trial-out and node-removal sensitivities. Do not call a prespecified, independently powered secondary endpoint invalid; preserve its inferential status precisely.
8. **Life-years-gained extrapolation.** If an NMA transforms relative treatment effects into life-years gained using external cohorts, keep the network HR, baseline survival model, extrapolation horizon, proportional-hazards assumption, treatment-effect transportability, competing risks and cohort-specific baseline hazards as distinct layers. Report modelled absolute benefit as a projection, not observed randomized survival. Reproduce the base survival model before changing the NMA effect.
9. **Threshold sample-size exclusion.** If eligible RCTs below a minimum sample-size cut (e.g. N<100) are excluded, enumerate all excluded trials, outcomes and event counts. Test whether excluding smaller trials differentially removes older agents or early signals. A size cutoff may be justified, but its influence on the network and missing-evidence assessment must be visible.
10. **Network inconsistency is local.** When node-splitting finds inconsistency for particular comparisons, record exactly those edges and outcomes. Do not treat a global network as wholly invalid, but do not use a statement that results are generally consistent to erase failed comparisons. Run local influence and direct/indirect decomposition.
11. **Egger/funnel limits.** In complex multi-treatment networks, record which comparison-adjusted funnel plot and regression were used, the effective number and distribution of independent comparisons, and whether the test has adequate information. A nonsignificant Egger test is not evidence that publication bias is absent.

### New negative controls

19. A review reports cumulative risks at different follow-up horizons but also has a correctly specified survival NMA on a common time-to-event estimand; do not flag solely because trial follow-up varies. Flag only if incompatible risk data were pooled as though they represented the same horizon.
20. A trial-level background therapy proportion is explicitly described as ecological and used only for study-level meta-regression; do not relabel it as an individual patient's combination effect.
21. A CNMA uses a prespecified interaction model or reports components as non-identifiable because of insufficient independent variation; do not assume additivity was forced.
22. P-scores are described as relative certainty summaries, with no claim that they are probabilities of being best; no interpretation flag.
23. A secondary endpoint is prespecified and adequately powered under its own alpha allocation despite a failed primary endpoint; do not automatically demote it to merely nominal.
24. A trial's older RoB 1 assessment is retained because it was completed before RoB 2 became available and the review is not being updated; label version and vintage, do not allege misconduct.

### Current audit examples to preserve as distinct statuses

- **Tang et al. 2024 (DOI 10.1186/s12872-024-04339-3):** source-verified methods disclosures show an LVEF eligibility threshold of ≤45%, a 60% trial-level background-treatment rule, aggregate rather than patient-level concomitant-treatment data, nonrandomized background therapies, additive CNMA assumption, outcome risk ratios and follow-up ranging from 2 to 71.8 months, an older six-domain Cochrane RoB assessment, and two local node-splitting failures (ACEI vs H-ISDN for all-cause mortality, p=0.02; BB vs placebo for HHF, p=0.01). The article also describes P-score as the likelihood of being ranked most effective, an incorrect interpretation. These are source-verified methodology/reporting limitations; exact model input and outcome-specific impact remain to be established from the supplement and analysis code.
- **JACC 2025 updated HFrEF regimen NMA (DOI 10.1016/j.jacc.2025.08.054):** the incremental quintuple-versus-quadruple result is explicitly described by the authors as exploratory because it is derived from a secondary endpoint of one trial. VICTOR's primary composite (CV death or HF hospitalisation) was neutral (HR 0.93, 95% CI 0.83–1.04); the secondary CV death endpoint was favourable (HR 0.83, 0.71–0.97), and the secondary all-cause mortality result was HR 0.84 (0.74–0.97). The prespecified protocol states secondary/exploratory endpoints are nominal after failure of the primary endpoint. The audit must retain this hierarchy and not treat the NMA's quintuple rank as confirmatory evidence of an incremental vericiguat survival benefit. This is a strength-of-evidence limitation, not proof that the underlying VICTOR HR is wrong.


## JACC 2025 HFrEF NMA — external registry and reference-trial audit additions (1 November 2026)

These additions follow a deeper source check of van Essen et al. (JACC 2025; DOI 10.1016/j.jacc.2025.08.054). They record **issues to resolve**, not proven errors in the unseen fitted input matrix.

1. **Registry-to-paper endpoint reconciliation is mandatory.** For every contribution to an outcome network, retain the ClinicalTrials.gov/WHO ICTRP record version, original registered primary/secondary outcome, actual registry result posting, protocol/SAP amendment chronology, paper endpoint, and outcome event unit. Distinguish primary composite, separately registered secondary composite, standalone event/time-to-event endpoint, and post hoc endpoint. A trial whose primary CV-death/HF event includes urgent outpatient visits must not be silently represented as CV-death/HF-hospitalisation; if an exact secondary CV-death/HF-hospitalisation outcome exists, verify it was the one used. Example control: DAPA-HF registered both a broad primary (CV death/HF hospitalization/urgent HF visit) and a distinct secondary composite without urgent visits; GALACTIC-HF's primary includes urgent visits/ED or admission, with separately registered CV death and first HF hospitalisation. Neither is categorically ineligible; the exact extracted endpoint must be identified.
2. **Reference-trial bridge audit.** If authors say an older RCT served as a “reference” to analyse a composite that was not reported in other early trials, identify its exact role: network anchor, imputation, conversion, calibration or actual outcome observation. The reference endpoint must match the target event definition, population, analysis set, follow-up window and treatment estimand. Do not infer a CV-death/HF-hospitalisation result from all-cause death/any-cause hospitalisation. If the reference trial reports only a sequential strategy (e.g. initial 6-month monotherapy followed by combination), it cannot automatically stand for a fixed chronic regimen. A separately reported CV-death/cardiovascular-hospitalisation result may help but must be shown to match exactly.
3. **CIBIS III control case.** The JACC 2025 paper says CIBIS III served as a reference for composite CV death/HF hospitalisation analyses. CIBIS III's main randomized strategy was bisoprolol-first versus enalapril-first for 6 months, then combination for 6–24 months; its primary endpoint was all-cause death or any-cause hospitalisation. Secondary/post-hoc endpoints include CV death and cardiovascular hospitalisation, but these are not automatically identical to CV death or HF hospitalisation. Require the exact CIBIS III supplement row, endpoint label, time period and source event definition before determining whether it creates an endpoint or treatment-strategy mismatch.
4. **HFrEF phenotype labelling.** If the review uses LVEF ≤50% for an analysis labelled HFrEF, document that its target includes 41–49% HFmrEF under the 2021 ESC and Universal Definition classifications (HFrEF ≤40%; HFmrEF 41–49%). This may be a deliberate broader inclusion and is not automatically invalid. Require EF≤40 versus 41–49 separate sensitivity analyses or explicit justification; mean LVEF similarity across trials does not replace individual-level subgroup estimates.
5. **Registry searching and missing evidence.** Search strategy audit must explicitly record whether ClinicalTrials.gov, WHO ICTRP, EU CTIS/older EU Clinical Trials Register, sponsor trial registers, conference abstracts and reference lists were searched. If the paper reports only MEDLINE, Embase and CENTRAL, label `REGISTRY_SEARCH_NOT_REPORTED` rather than assume no registry search was performed. Crosswalk completed/terminated/suspended trials with unpublished results, and assess whether an intervention/outcome is selectively absent. Never infer missing evidence from no registry mention alone.
6. **Trial-level multiplicity attached to NMA evidence.** For each effect used in an NMA, flag whether the underlying RCT endpoint was its primary endpoint or a nominal secondary/exploratory endpoint after a failed primary endpoint. This does not prohibit using a secondary endpoint in a meta-analysis, but the inference status and certainty must be retained in CINeMA and the clinical interpretation. Example: VICTOR's primary CV death/HF hospitalisation composite was neutral (HR 0.93, 95% CI 0.83–1.04); its protocol describes secondary/exploratory endpoints as nominal. The separate mortality publication's 2026 erratum corrected risk tables/cumulative counts for sudden/HF-related death and anaemia rows, but did **not** change overall CV-death and all-cause mortality HRs; the corrected paper must be used for time-to-event and relevant safety extraction.
7. **Outcome rows must not be interchanged.** For VICTORIA, distinguish total CV deaths (414/441) and total all-cause deaths (512/534) from deaths counted as the first component event in a composite (e.g. CV deaths 206/225). For GALACTIC-HF, distinguish total CV deaths (808/798) from CV deaths as first primary composite event (346/371); its primary event count includes urgent HF events. If a supplement labels first-event counts as total mortality, flag a verified reporting-table issue, but block `MODEL_INPUT_WRONG` until executed model rows establish what was fitted.

### JACC 2025 audit status (classification, not verdict)

- **Source verified:** JACC's public methods identify MEDLINE, Embase and CENTRAL through April 2025; the public search description retrieved so far does not disclose ClinicalTrials.gov/ICTRP. The paper describes component NMA as additive and background-therapy components as trial-arm-level classifications; its threshold sensitivity (50%, 70%, 90%) changes the top regimen. It explicitly calls the incremental quintuple benefit exploratory and derived from a single trial's secondary endpoint.
- **Source verified:** conventional ESC/Universal Definition categories identify HFrEF as LVEF ≤40% and HFmrEF as 41–49%; a JACC network described as HFrEF needs an explicit interpretation if its eligibility threshold extends to ≤50%.
- **High-priority unresolved:** exact CIBIS III endpoint/estimand used for the composite network; exact VICTORIA and GALACTIC-HF mortality outcome rows used in the fitted network; precise registry-to-NMA outcome mapping for each of the 21 composite trials.
- **Not demonstrated:** that any of these discrepancies changed the JACC NMA coefficients or that all regimen estimates are wrong. Author extraction workbook, supplement model inputs and reproducible code are still required for exact replay.


## JACC 2025 HFrEF NMA — deeper source reconciliation (1 November 2026, continuation 2)

### 1. CIBIS III is not an endpoint-equivalent reference without a documented transformation

The JACC article states that CIBIS III served as a reference for analysing the CV-death/HF-hospitalisation composite in earlier trials. Primary-source reconciliation shows:

- CIBIS III's randomized strategy was bisoprolol-first versus enalapril-first: 6 months of open-label monotherapy, then both agents in combination for 6–24 months. It enrolled 1,010 stable patients, mean LVEF about 28.8%, aged ≥65 years, previously not receiving ACEI, BB or ARB.
- Its primary outcome was **all-cause death or hospitalisation from any cause**, not CV death or HF hospitalisation (main RCT HR 0.94, 95% CI 0.77–1.16).
- A post-hoc analysis examined mortality or cardiovascular hospitalisation; this is still not equivalent to CV death or HF hospitalisation. It reported that 60% of endpoints occurred during the monotherapy phase, and treatment initiated during that phase was not a predictor of the assessed outcomes.
- Separate reporting gives 63 vs 51 patients hospitalised for worsening HF (HR 1.25, 95% CI 0.87–1.81) and overall deaths 65 vs 73 (HR 0.88, 95% CI 0.63–1.22), but the whole trial remains a sequential treatment-strategy RCT rather than a fixed chronic regimen comparison.

Sources: PMID 16143696 (main randomized CIBIS III); PMID 21551161 (post-hoc strategy/outcome analysis); PMID 20528880 (mode-of-death analysis). The JACC authors' phrase “served as a reference” does not identify whether CIBIS III was a data source, calibration, proxy, or bridge. Therefore classify this as `ENDPOINT_AND_ESTIMAND_BRIDGE_UNRESOLVED`, not a confirmed model-input error. Require the exact CIBIS III row, source report, outcome definition, follow-up and transformation. Do not accept all-cause mortality/any-cause or CV hospitalization as interchangeable with CV death/HF hospitalization.

### 2. GALACTIC-HF has separate broad and narrow outcomes; exact NMA row is decisive

ClinicalTrials.gov NCT02929329 and FDA source documents define the primary event as CV death or first HF event. HF event includes urgent clinic visit, emergency-department visit, or hospital admission with worsening HF requiring treatment intensification. The registry separately reports **time to first HF hospitalization** and **time to CV death**. It is not automatically invalid for the JACC composite network: the audit must identify whether the NMA used the broader primary event, the separately reported narrow hospitalization endpoint, or a documented harmonized source. A narrow composite of CV death OR HF hospitalization is not identical to the broader primary composite. Because first HF hospitalization and CV death may occur in the same participant, analysts must not simply add marginal counts or HRs to create a composite without joint-time-to-event data.

Sources: ClinicalTrials.gov NCT02929329; FDA GALACTIC-HF clinical trial overview; NEJM GALACTIC-HF primary publication. Required status: `OUTCOME_ROW_NOT_YET_RECONCILED` pending the exact JACC supplement input.

### 3. VICTOR trial-level multiplicity must remain visible in NMA certainty

ClinicalTrials.gov NCT05093933 specifies the primary outcome as time to first CV death or HF hospitalization. The trial report gives 549/3,053 versus 584/3,052 events, HR 0.93 (95% CI 0.83–1.04; p=0.22). The authors state that, per protocol, after failure of the primary endpoint, all secondary/exploratory endpoint analyses are nominal. The mortality analysis reports CV death HR 0.83 (0.71–0.97) and all-cause mortality HR 0.84 (0.74–0.97); it describes CV death as a prespecified secondary endpoint and independently powered, but the protocol's multiplicity/hierarchical statement still governs confirmatory interpretation. This is not grounds to exclude the result from a secondary synthesis, but it must inform outcome-specific selective-reporting/certainty appraisal and clinical language.

JACC outcome pattern: the estimated quintuple-versus-quadruple contrast is significant for all-cause death (HR 0.88, 95% CI 0.79–0.98) and standalone CV death (HR 0.87, 95% CI 0.77–0.98), but **not** for the CV-death/HF-hospitalisation composite (HR 0.93, 95% CI 0.85–1.02). The latter is the closest of the three to VICTOR's neutral primary endpoint. This discordance is not proof of error, but it makes the incremental mortality-only ranking more dependent on a single secondary mortality signal. Required sensitivities: remove VICTOR; report no estimable quintuple node if disconnected; preserve nominal endpoint status; compare fixed vs random effects and outcome definitions.

Sources: ClinicalTrials.gov NCT05093933; PMID 40897189 (VICTOR primary trial); PMID 40884032 (VICTOR mortality analysis); JACC DOI 10.1016/j.jacc.2025.08.054.

### 4. Quintuple regimen estimate is model-implied, not an observed randomized five-drug arm

JACC reports HR 0.35 (0.27–0.45) for quintuple therapy and 0.39 (0.32–0.49) for quadruple therapy vs placebo. The authors' own text and correspondence clarify that component background exposure was coded at trial-arm level (e.g. whether ≥50% of each arm used each individual component), not by observed joint exposure in the same individual participants. VICTOR is the sole trial supporting the quintuple node. Thus HR 0.35 is a CNMA extrapolation from trial-level marginal component classification plus additivity—not the observed HR from a trial randomizing patients to ARNI+BB+MRA+SGLT2i+vericiguat as a complete combination. The estimated incremental benefit is exploratory and must be described accordingly. The 50%, 70%, and 90% coding sensitivity changes the leading regimen; this is evidence of model-specification sensitivity. It is not an error by itself.

### 5. Counterfactual life-years and NNT require a model audit separate from the NMA

The 2025 paper projects 5.3 life-years for quadruple therapy and 6.0 for quintuple therapy at age 70 vs “no treatment”; the underlying BIOSTAT-CHF/ASIAN-HF survival sample includes 7,376 patients, 77% on ACEI/ARB, 82% on beta-blockers and 55% on MRA at baseline. The earlier 2021 NMA from the same programme explicitly distinguished gains vs actual care and gains vs hypothetical placebo/no treatment, adjusting each patient's baseline regimen. The 2025 update must be checked for the same explicit counterfactual construction. Verify how observed treated survival was converted to untreated baseline, whether the NMA HR is applied conditionally on the individual's existing background treatment, and whether no-treatment absolute risks avoid double-counting existing therapy. Treat this as `COUNTERFACTUAL_MODEL_REPRODUCTION_REQUIRED`, not as a proven double-counting error.

The reported two-year NNTs (6.3 [6.2–6.4] for quadruple; 5.8 [5.8–5.9] for quintuple) require independent reproduction from patient-level baseline hazards and joint bootstrap draws. Do not derive an incremental NNT by subtracting marginal NNTs. Obtain the paired difference distribution, its CI, and bootstrap design/covariance. Authors have stated that bootstrapping addressed uncertainty; exact executable implementation and paired estimand remain to be checked.

### Status update

New source-verified facts: CIBIS III endpoint/strategy definitions; GALACTIC-HF's separate broad primary and narrower registered hospitalisation outcomes; VICTOR's neutral primary, protocol-defined nominal secondary analyses; JACC's differing incremental results across all-cause mortality, CV mortality and the composite. Unresolved: exact CIBIS and GALACTIC rows fitted by JACC; whether VICTORIA/GALACTIC mislabelled counts entered models; whether the no-treatment baseline reconstruction and paired NNT uncertainty are correctly implemented. No claim of a complete NMA reproduction or proven change in JACC model coefficients is permitted until the exact supplement inputs and code are obtained.
