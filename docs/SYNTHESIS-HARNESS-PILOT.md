# Synthesis checklist in the research harness

The [Synthesis v1.3 checklist](SYNTHESIS-v1.3-CANDIDATE.md) is an executable
coverage record around existing source-replay tools. It preserves the six core
checks, all 27 detailed checks, and six revision-sweep steps from the
[human companion](SYNTHESIS-HUMAN-CHECKLIST.md). Wording is read from that document.

This is a supervised **development** workflow. Creating the tool does not complete
an independent human pilot or unseen-cohort scientific evaluation. External
prerequisites are an independent scientific custodian, two qualified reviewers,
a separate adjudicator for disagreements, and an approved fresh OA sampling frame.
AI code reviewers do not satisfy those prerequisites.

The [matched-harness evaluation contract](MATCHED-HARNESS-EVALUATION.md) adds
frozen comparator configurations, checked common inputs, complete run records,
masked review exports and paired descriptive scoring. Its independent scientific
study remains pending the prerequisites above.

## Integrated contract

`scripts/synthesis_checklist.py` initializes every claim in a supported source-replay
bundle with `core-1` through `core-6` and `detail-1` through `detail-27`, plus a
review-level sweep `revision-1` through `revision-6`. Missing, duplicated, changed
or extra rows/claims refuse verification.

Rows start with null judgments, displayed as `NOT_STARTED`. A reviewer records
**Pass**, **Review needed**, **Insufficient evidence**, or **N/A**, with a reason,
declared reviewer, date and actual check time. Pass and Review needed require a
saved evidence file, SHA-256 and locator. Inaccessible evidence means Insufficient
evidence; it is not inapplicable. Meaning and applicability remain human judgments.

| Checklist area | Existing software evidence | Judgment still required |
|---|---|---|
| Source/version/quoted counts | PMC replay, snapshot and locator checks | Currentness, completeness, quotation meaning |
| Denominators/populations/outcomes | Participant checks and scoped dossiers | Cohort attribution, exclusions, estimand/endpoint comparability |
| Calculations | Preflight and v1.3 supported arithmetic | Appropriate method, inputs, precision, coding, units, saved working |
| Trial families, shared controls, NMA/IPD | Identity/readiness controls where applicable | Overlap, transitivity, missingness, censoring, methodological adequacy |
| Benign explanations/replies | Evidence and response-review procedure | Point-by-point source recheck; issue class and demonstrated impact separately |
| Revisions | Record revisions and evidence hashes | Old/new versions, affected locations, recalculation, unaffected-control checks |

Automated replay stays **separate** from checklist judgments. Software never turns
a matched receipt into human Pass. Full coverage produces `ALL_CHECKS_RECORDED`;
scientific disposition stays `HOLD`, release eligibility false, and human identity/
independence `NOT_ESTABLISHED`.

## Development rehearsal

Create a private `review-work` directory under the repository root; Git ignores it.
The StepWise example is exposed development material. Replay checks its archived
source identity/licence. Retain this manifest anchor independently; do not recompute
a convenient anchor after changes.

```console
python scripts/synthesis_checklist.py init --bundle examples/synthesis-replay-stepwise --expected-sha256 d81086aaf3cee56b8936af0ef617085844718cdb1a200b88870fcfef7812b0d6 --project stepwise-operator-development --out review-work/review-001.json
python scripts/synthesis_checklist.py render --bundle examples/synthesis-replay-stepwise --record review-work/review-001.json
python scripts/synthesis_checklist.py verify --bundle examples/synthesis-replay-stepwise --record review-work/review-001.json
```

Initialization replays sources and leaves judgments unfilled. STROKEWALK is also
supported. Both examples, linked paper/trial families, and all development cases
are excluded from future untouched test cohorts. Protected labels are not needed.

After actually performing a check, save a new revision:

```text
python scripts/synthesis_checklist.py record --bundle <bundle> --record <previous.json> --out <next.json> --claim <claim-id> --item <core-N-or-detail-N> --status "<checklist result>" --reason "<source-based rationale>" --reviewer "<actual reviewer>" --seconds <actual check time> --evidence <saved-working-file> --locator "<exact location>"
```

For sweep rows use `--claim revision --item revision-N`. Omit evidence/locator only
for reasoned N/A or Insufficient evidence. Save structured working with source
versions, reviewed occurrences, inputs/formula/command/raw output, missing materials,
next action, and **separate issue-class and impact** assessments. A source or
calculation file may itself be the attachment. Locators are declared, not semantically
authenticated. Actual revisions need old/new hashes and the affected-occurrence log
specified by the human checklist. If no revision occurred, record N/A with a reason.

Every command replays the source, checks the entire inventory and verifies evidence
bytes. Normalized-LF guidance and implementing-source hashes are bound. Changed
source/guidance/code requires a new reviewed record; never copy old Pass statuses
automatically. Preserve changed evidence in a new file and retain the original.
Corrections retain original decisions and their check time. New record files are
created exclusively; previous records and sealed bundles are not overwritten.
Exit 2 means refusal.

Records contain private local paths and identities. Parent digests/history aid
inspection; they are not authenticated append-only custody. Independently retain
record digests at handoff. Runtime observations include Python/SQLite/OS and
available signing-package versions; they do not attest the interpreter or pin all
dependencies. Controlled local files are assumed; hostile concurrent writers are
outside this boundary. Historical evidence must retain its original bytes too.

## Supervised operator pilot

1. Appoint custodian/reviewers. Record conflicts, familiarity, roles, current policy
   anchor and checked key enrollment. Use a narrow cohort/outcome/denominator
   question with authorised OA sources.
2. On exposed examples, observe initialization, evidence entry, correction, resume
   and changed-input refusal. Preserve actual failures, confusing steps and any
   assistance given; avoid coaching where feasible.
3. Measure task start/end and interruptions separately from per-check time. Capture
   manual corrections and actual costs/usage. Missing measurements are null, not
   zero. CLI time is declared check time, not observed total operator task time.
4. Two humans collect initial judgments independently before seeing each other or
   predictions. A third adjudicates disagreements. Retain every attempted case/
   field, including unsupported, inaccessible, unresolved and abstained cases.
5. Fix observed friction using development material. Challenge valid quotations
   assigned to wrong populations, endpoints, analysis sets or follow-up windows.
   Label intentional changes synthetic controls, not real-paper errors. Expert
   references must be prepared independently.

Reviewer-key authorization covers only supported **final cohort/outcome relation
dossiers**, not arbitrary checklist rows or initial blinding. Collect reviews
first; finalize/sign supported dossiers later, retaining all original ballots.
Changed dossiers require fresh signatures under the current approved policy.

## Freeze and evaluate an unseen cohort

Reuse the [independent blinded plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md) and
`scripts/synthesis_blind_eval.py`. This adapter does not relabel development records.

- The custodian approves the OA sampling frame, rights/currentness checks, family
  grouping, selection rule/seed, inclusion/stopping rules, target claims,
  sample-size rationale, metrics and analysis before selection.
- Split by paper/trial family; exclude all development, feedback and tuning
  families. Preserve protected earlier cohorts.
- Freeze commits, checklist/prompt/config bytes, model/tool versions, access,
  retrieval/time budgets and baseline. Use matched structured manual checking
  without checklist assistance, or another independently approved comparator.
- Keep all attempts and every claim-arm prediction. Missing source requires
  ABSTAIN with its stop point. Do not derive FLAG/NO_FLAG from checklist counts.
- Freeze predictions before reference disclosure; independently retain canonical
  manifest/prediction digests and custody timestamps. Scripts check declared
  ordering, not truthful clocks, identities or blinding.

```console
python scripts/synthesis_blind_eval.py --manifest private-manifest.json --predictions private-baseline-predictions.json
python scripts/synthesis_blind_eval.py --manifest private-manifest.json --predictions private-checklist-predictions.json
```

These checks require every test prediction and produce no accuracy result. After
real independent adjudication, add the matching `--adjudications` file per arm.
Every test claim needs a row, including UNKNOWN. Unreviewed negatives cannot become
NO_ERROR. Wrong-root flags, missed errors, abstentions and unknown truth remain.

Report descriptive feasibility and paired counts first. Existing Wilson intervals
are **claim-level**, not family-cluster uncertainty. Inferential comparison needs
an independently approved family-level paired analysis; do not substitute those
intervals. Accept an honest null. Later tuning needs fresh unseen families. Generic
OA pilots are not SciCoQA, whose tool requires its actual paper/code inputs.

## Static versus dynamic disclosure

| Item | Static or dynamic | Meaning |
|---|---|---|
| Inventory, statuses, mapping | Static contract; wording from pinned docs | Requirements, not completed review |
| Synthetic decisions/times/mutations | Static test inputs | Engineering controls, not human findings |
| Replay, hashes, runtime observations | Dynamic execution | Supplied-input consistency and observed environment |
| Human judgments, task observations, costs | Pending actual pilot | Not supplied by implementation |
| Unseen families, references, accuracy | Pending independent custody/execution | No prospective accuracy claim |
