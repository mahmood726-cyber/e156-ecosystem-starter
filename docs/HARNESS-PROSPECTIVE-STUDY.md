# Prospective matched OA scientific evaluation: preparation decisions

**26 November 2026. Status: NOT_STARTED. Design proposal, not a preregistration,
approved protocol, executed study or scientific validation.**

The next evidence question is whether the candidate helps detect and substantiate
real scientific error roots under a matched resource budget, without increasing
false allegations or hiding failures behind abstention. The completed
[scripted execution comparison](HARNESS-EXECUTION-RESULTS-2026-11-26.md) answers a
different question. Its final cases are consumed; do not inspect them to select
new policies, reuse them as unseen tasks, or turn their repetitions into scientific
sample size.

This document adds decisions and preparation gates to the existing
[matched evaluation contract](MATCHED-HARNESS-EVALUATION.md),
[blinded validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md) and
[human pilot runbook](SYNTHESIS-HARNESS-PILOT.md). Those documents own the schemas,
CLI sequence, source rules and checklist workflow. No new corpus, human approval,
expert labels, paid-call budget or final sample size has been supplied here.

The [file-backed preflight](HARNESS-STUDY-PREFLIGHT.md) now verifies actual
configuration/reference files and task lineage before preparation. It reports
`EVIDENCE_BOUND_NOT_RUN`, leaves human and scientific requirements unverified,
and does not supply expert review. The [development runner](HARNESS-STUDY-RUNNER.md)
connects E156 and a constrained [native Pydantic Agent](HARNESS-NATIVE-PYDANTIC.md)
to read-only execution, recovery and measured ledger export. Its custom Responses
bridge has offline development controls; live provider validation remains pending.
The runner refuses prospective protocols and has not run this scientific study.

## Inputs that must exist before a prospective freeze

| Owner to appoint | Required decision or evidence | Current state |
|---|---|---|
| Study sponsor | Scientific task scope; primary comparison and endpoint; acceptable false-alert harm; total API, compute and human budget; authority to stop the study | Not supplied |
| Independent scientific custodian | Named responsibility, conflicts and access separation; source/rights verification; sampling frame; family definitions; exclusions and exposure register; private receipt custody | Not supplied |
| Two qualified source reviewers and a separate adjudicator | Domain/methods competence, conflicts/familiarity declarations, available time, masked allocation and dispute process | Not supplied; AI code reviewers cannot fill these roles |
| Analysis lead | Target population and estimand; family-level size/precision justification; missingness and UNKNOWN treatment; comparison multiplicity; decision margins and analysis code freeze | Not supplied |
| Execution lead | Verified live adapters; complete tool/model contracts; isolated sessions; cap enforcement; outcome parser; accounting bridge and failure policy | E156 and constrained native Pydantic development bridges implemented; live provider validation, Deep Agents adapter and scientific integration incomplete |
| Sponsor and execution lead | Exact model snapshot/access, decoding and routing policy; cap values; approved provider project and billing evidence; reviewer payment basis | Not supplied; do not substitute current prices or invented zero costs |

These are substantive inputs, not fields to fill with approval-like strings.
The evaluator checks receipt references but cannot authenticate the people or
their decisions. The earlier proposed feasibility size in the blinded plan is
not an approved sample size for this multi-arm study.

The custodian must draw a fresh OA frame with authenticated source versions and
typed publication/trial-family identifiers. Exclude exposed StepWise/STROKEWALK
families, known audit/correspondence cases, development probes and all families
used for tuning. Preserve the protected Simo cohort. Record ordinary papers as
unmodified, not presumed error-free. Deliberate error controls, if approved, are
a separate stratum and cannot establish population prevalence. A claim of
"unseen" covers documented project exposure; model pretraining exposure cannot
be certified from a local exclusion register.

Enumerate atomic claim/root targets before output exposure. Independently label
every test claim, including those never flagged; this evaluator has no
sampled-negative weighting. Decide whether NMA/IPD tasks are in scope only after
confirming source access and reviewers with the necessary methods expertise.

## Arms and fairness decisions

The proposed primary contrast is an E156 candidate against an explicit E156
baseline. Native framework arms answer whether that candidate is useful beside
existing options. Freeze all arms before final tasks are exposed:

| Proposed arm | Configuration to freeze | Interpretation |
|---|---|---|
| E156 baseline | Prior implementation/configuration; declare repetition guard and derivation-admission policy explicitly | The reference behavior, not an artificially broken baseline |
| E156 candidate | Reviewed implementation with the opt-in exact-result guard and execution-bound derivation enforcement | Combined change; cannot attribute an effect to either component separately |
| Native Deep Agents | Real `create_deep_agent`; version and dependency lock; documented middleware, context, tools and stop behavior | A named configuration of Deep Agents, not a claim about every native capability |
| Native Pydantic AI + Harness | Real `Agent`; versions/lock; explicit `DetectLoops`, usage limits, context and other capability settings | Enable relevant supported protections; do not carry forward the synthetic suite's disabled detectors without justification |

The candidate derivation work is implemented in `scripts/harness_derivation.py`
and the context validator; see the [receipt contract](HARNESS-DERIVATIONS.md).
Freeze its tested revision before selecting an arm. The receipt binds parent lineage,
recipe, execution policy and exact worker output. A locally generated unsigned
receipt establishes consistency under a trusted producer; it does not
authenticate external custody or establish the scientific calculation's validity.

If component attribution is important, add a prespecified guard-only ablation or
factorial design with adequate resources. Do not add arms after looking at final
results. If only two arms are affordable, prioritize the candidate/baseline
contrast and record that no native scientific comparison was conducted.

For a `harness_only` comparison, freeze the same model snapshot, decoding/reasoning
settings, routing/fallback policy, task instructions, source bytes and external
scientific capabilities. Harness-specific scaffolding may differ but must be
archived. Freeze tool names/schemas, implementations, access permissions, source
visibility, calculation environment and output limits. The common cap provides
equal opportunity, not a requirement to consume equal resources. Choose caps
from separate development/feasibility workloads, then lock them before the
test set is opened; state what workload fits and what legitimate work may be
truncated. Include nested models, retries, compaction and delegated work.

There are two unresolved contract boundaries that block an honest freeze:

- `synthesis_matched_eval.prepare` requires identical `tools_sha256` in **both**
  `harness_only` and `system` comparisons. Equal strings do not establish equal
  semantics. Native planning/filesystem/subagent tools must either be matched
  honestly in the capability manifest or explicitly disabled for a constrained
  comparison. Keep native context and guard features where compatible. If exact
  alignment is impossible, revise and test the comparison contract before the
  study; changing the label to `system` alone does not fix this restriction.
- Decide whether derivation validation is a shared evidence boundary or the
  candidate's policy under test. Sharing it means native arms inherit the same
  source check, so its benefit cannot be attributed uniquely to E156. Different
  evidence-tool permissions/semantics cannot be concealed under one tool hash.
  Resolve the policy-versus-tool boundary in an explicit arm contract; otherwise
  evaluate derivation integrity separately from the matched scientific contrast.

Deep Agents documents context management, memory and delegation; Pydantic
documents a broad set of capabilities and native loop detection. Disabling these
for matching narrows the claim to the tested configuration. A full-capability
product comparison would be a separate design, with disclosed differences and
appropriate contract support. See the primary [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview),
[Pydantic Harness documentation](https://pydantic.dev/docs/ai/harness/) and
[DetectLoops contract](https://pydantic.dev/docs/ai/harness/detect-loops/).

## Family-level planning and endpoints

The independent sampling unit is a paper/trial family defined by the custodian;
several claims, multiple reports and repeated executions within a family do not
create new independent families. Prespecify the primary estimand: for example,
the paired difference in correct error-root detection among adjudicated ERROR
claims, including misses and abstentions. Choose claim-weighted or family-weighted
aggregation explicitly; they answer different questions. Protect against a
nominal gain caused by false allegations with a prespecified false-alert margin
and report wrong-root flags as both false alerts and missed roots.

The analysis lead's size-planning artifact must record:

1. The meaningful effect or desired interval width, false-alert constraint,
   confidence level, power if a hypothesis test is planned, and multiplicity
   handling for the selected arm contrasts.
2. Assumptions about error prevalence, claims per family and unequal family
   sizes, within-family dependence, paired arm discordance, UNKNOWN/source-limited
   fractions and expected attrition. Obtain assumptions from independent
   development/feasibility data or label sensitivity ranges as assumptions.
3. Simulations of the actual paired family structure and proposed analysis,
   including low-prevalence and high-dependence scenarios; freeze code, seed,
   target independent family count and feasibility conclusion. Simulations here
   are design calculations, never scientific performance results.
4. A prespecified treatment of insufficient eligible families or too few known
   ERROR/NO_ERROR outcomes. Report an inconclusive/feasibility study when needed;
   do not keep sampling until a favorable contrast appears.

Plan paired uncertainty at the family level, retaining every arm and claim from
a resampled family together if a cluster bootstrap is selected. Check its coverage
in the planning simulations; do not presume a small number of families makes
asymptotic methods reliable. Ordinary independent-claim calculations are not
sufficient for clustered matched observations; see the primary methodological
study [Non-inferiority tests for clustered matched pair data](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717020/).
That paper supports accounting for the dependence, not a chosen sample size or
a ready-made superiority analysis for this project.

The existing evaluator supplies paired family counts and claim-level Wilson
intervals only. Family uncertainty, evidence-location correctness, paper-level
false-allegation risk, and any inference or integration decision require a frozen,
reviewed analysis addition or independently checked external analysis. Report
recall, precision, false alerts, abstention/UNKNOWN, runtime failures, source
coverage, operator time and costs separately. Do not rank a composite score whose
weights were chosen after observing results. UNKNOWN is not NO_ERROR; describe
its reasons and prespecified sensitivity analyses.

## Masked reference review and execution isolation

The custodian assigns source families to two qualified reviewers after recording
conflicts and familiarity. They establish claim truth from source material
independently of arm outputs, reconcile reasons, and use a separate adjudicator
for disagreements. Freeze this reference work privately; final predictions must
be frozen before the execution team can see it. Build one common truth per claim,
then judge each masked output's evidence and root match against that reference.

Use the evaluator's masked sample IDs for output review. Keep the arm mapping,
raw traces, timing and billing in custodian-controlled storage. Randomize and
record review allocation/order with a separate frozen seed. Where reviewer
capacity permits, avoid giving the same reviewer competing outputs for the same
claim; otherwise prespecify separated review sessions and record the residual
recognition risk. Review identifying prose, locator strings and stop reasons
before release to reviewers without altering their substantive content. Preserve
the original packet, any redaction mapping and checksums. Masking alone is not
proof of independence or successful blinding. Retain both initial judgments,
disagreements, adjudicator reasons, conflicts, and measured review time; the
current final adjudication schema does not allocate reviewers or store this whole
workflow.

Run each scheduled claim/arm in a fresh isolated process and workspace with a
read-only copy of the approved input inventory, separate journal/checkpointer,
memory and output directory. Do not expose answer files, review receipts, the
private protocol mapping, another arm's outputs, home directories or credentials
unneeded by the run. Restrict retrieval to the frozen source inventory for the
primary contrast; an open-web retrieval task needs a separate prespecified source
capture/access policy. Prevent application memory or retrieval caches from
carrying results between runs; record provider caching policy and actual charges.

Execute the deterministic schedule emitted by `prepare`, recording actual order
and deviations. The current contract permits one record per claim/arm, retaining
all internal attempts. It does not support extra stochastic replicates by adding
duplicate records; that requires a reviewed schema/analysis extension. Allocate
shared paper-level preparation costs once under a frozen rule. Isolate restarts
without duplicating completed side effects. Keep FAILED, TIMEOUT and
NOT_ATTEMPTED as ABSTAIN records in the planned denominator; retain all evidence
and do not select a successful retry as if earlier attempts never occurred.

## Concrete adapter and accounting work before execution

The existing execution guide's [matched evaluation boundary](HARNESS-EXECUTION.md#matched-evaluation-boundary)
is binding. `scripts/harness_execution_benchmark.py` uses scripted model fixtures;
it is not the live scientific runner. The E156 development runner and record
adapter now supply the bounded first path below. Remaining cross-framework and
scientific work must be completed before prospective execution:

| Existing ingredient | Work still required | Development acceptance evidence |
|---|---|---|
| Matched/blind evaluators and `harness_study_runner.py` | E156 read-only development schedule, case isolation and immutable ledger are implemented; extend to reviewed native live arms and scientific protocol | Synthetic prepare, execution, recovery, mask and compare; real process locks/watchdog; missing/changed records fail closed |
| E156 runtime/provider/context/trace and `harness_study_records.py` | Trace-derived predictions/accounting and explicit measured-review receipts are implemented; real development provider rehearsal and broader tool integration remain pending | Parse/refusal/timeout/unknown-outcome cases retained; current source/receipt bindings required; missing measurements remain unknown |
| Native Deep Agents and Pydantic integrations in the execution benchmark | Live provider adapters, matched tools and permissions, native configuration freeze and output normalization | Same bytes and capabilities verified; native features/settings disclosed; no fabricated model output |
| E156 development aggregate supervisor and native limits | Full case ceilings are reserved without refund for serial E156 read-only cases; extend and verify equivalent controls for native tools, retries and child agents | Development probes retain allocations through unknown launches, recovery and deadlines; ceilings are not invoices |
| Trace-derived evidence packages and measurement receipts | Implemented byte-bound ledger bridge and whole-case clock; supply real operator time logs, actual invoice reconciliation and independent custody | Evidence packages checked; unknown measurements stay null; no substitution of reservations for observations |
| Masked exporter and scorer | Reviewer allocation/receipt store; family-level analysis; prespecified decision report | Full masked handoff rehearsed on development data; root matching and analysis verified independently |

Extend the bridge's measurement dictionary explicitly for native arms: count
successful, failed and refused tool attempts separately; declare which count
populates the cap field; distinguish model-loop turns from transport retries;
include billed ancillary requests and nested usage. Reconcile provider usage
with local events and unresolved reservations. Native counters may differ:
Pydantic documents successful-tool counting, loop-turn request counting and
post-response token/cost checks. Its spend limits can overshoot and some costs
depend on pricing coverage. Thus a native limit alone is not proof of a hard
shared study cap. [Pydantic production limits](https://pydantic.dev/docs/ai/production/)

Enforce a conservative reservation/deadline policy before dispatch, with a frozen
allowance for bounded in-flight work; test it on each adapter. Record overruns as
violations. If the provider cannot guarantee an exact charge ceiling, state the
enforceable bound and reserve rather than promising an impossible exact dollar
cap. Stop new dispatches when unresolved usage threatens the budget.

Populate `api_cost_usd` only from attributable actual charges supported by provider
records; leave it null while reconciliation is pending or attribution is unknown.
Retain price-policy estimates separately. Measure end-to-end wall time separately
from operation timing. Measure human work, including interventions, with a frozen
payment/allocation basis; unpaid work still consumes time. Record infrastructure,
reference adjudication and setup separately because the evaluator excludes them.
Report observed subtotals, missing counts and the separately reconciled study
total; never call a partial subtotal total cost.

Freeze the complete run ledger before masking. Masked sample IDs depend on its
full digest, including costs; editing later billing fields changes the IDs and
invalidates the adjudication binding. Either reconcile charges before this
freeze, or retain null costs in the immutable ledger and publish a separately
bound reconciliation supplement. A later software extension for amended costs
needs its own reviewed contract; do not rewrite the scored ledger in place.

## Preparation milestones and integration decisions

| Milestone | Exit evidence | Status |
|---|---|---|
| A. Scientific ownership and design | Named custodian/reviewers, scope, exposure register, feasible sampling frame, budget and analysis decisions | NOT_STARTED |
| B. Development integration | Completed adapters/accounting and isolated rehearsal; actual failure log and comparator fairness review | NOT_COMPLETE |
| C. Prospective freeze | Reviewed size justification; authenticated private source/task inventory; source/reference separation; full versions/configs/limits; genuine receipts; `PREPARED_NOT_RUN` | NOT_STARTED |
| D. Execute, adjudicate and analyze | Complete frozen ledger, independent masked review, billing/time reconciliation and family-aware analysis | NOT_STARTED |

Drive integration work from observed development failures, not a checklist of
fashionable features. For each issue preserve the trace, frequency, consequence,
owner, repair and regression evidence. Examples to investigate only when observed
include repeated-result loops, stale derived evidence, context-loss errors,
incorrect root matching, source-access failures, cap/accounting gaps and excessive
human rescue. Add compaction, delegation or new policies only when the failure
evidence and a development test justify them. Freeze again after changes; never
repair against the final labels and call the same cohort untouched.

An integrity breach (label leakage, changed frozen bytes, lost attempts, unbound
outputs or unverifiable accounting) pauses execution under the predeclared stop
policy. Preserve affected records and report the deviation; do not silently
replace unfavorable tasks. Scientific go/no-go requires the prespecified benefit,
false-alert, coverage, cost and human-time criteria with appropriate uncertainty.
No numeric threshold is supplied here because the scientific owner has not
chosen one. A null result or insufficient evidence means no superiority claim;
candidate software tests and local consistency receipts cannot change that result.

## Static-versus-dynamic disclosure

| Item | Static/configured in this preparation | Dynamic evidence still required |
|---|---|---|
| Proposed arms, stages, schemas and failure rules | Design/software structure only | Reviewed final configurations and integration receipts |
| Sample size, effect/precision targets, margins, cap values and reviewer allocation | Not assigned; no fabricated defaults | Independent planning assumptions, approved decisions and freeze |
| Source identifiers, OA rights, family inventory and exposure exclusions | No fresh scientific corpus supplied | Authenticated source records and custodian register |
| Derivation receipts and source hashes | Consistency mechanism under declared trust assumptions | Actual checked execution, exact bytes and independent scientific verification |
| Outputs, flags, labels, usage, charged cost and reviewer time | No prospective measurements supplied | Complete live traces, human source adjudication and reconciled records |
| Native framework features | Primary-source documented capabilities | Verified behavior of each frozen adapter/configuration |
| Scientific accuracy, comparative benefit, production readiness | Not established | Prospective results and the separately applicable release gates |

Preparation can proceed without exposing final cases. Scientific execution waits
for the listed real inputs and completed integration, not for another general
expression of approval.
