# Research harness upgrade plan

Research and source inspection: 2026-11-11. Starting starter revision:
`677035bb3a4cabf7dc7480340be5323a72617e96`. This is a development plan, not
a release certification or a claim of superiority. See [benchmark.md](../benchmark.md)
for primary sources, comparison boundaries, and the evaluation protocol.

## Intended result

A researcher should be able to resume a review, find its current evidence,
replay its analysis, inspect unresolved disagreements, and understand exactly
which checks ran. The same evidence trail should connect memory, acquisition,
extraction, statistical code, a dashboard, Sentinel, and Overmind. The first
implementation milestone strengthens memory and makes its boundary executable.

This iteration edits the starter. Upstream packages remain separately owned
components; the audit does not silently replace their checkouts or change their
scientific methods. Deployment and lifecycle promotion require separate release
evidence. No manuscript or protected workbook section is part of this change.

## Verified ingredients and reuse

The current starter checkout was clean and its HEAD matched remote main when
inspection began. A second local starter checkout was older (`d2f13c9`); it was
not used for implementation. Local paths are retained only in ignored session
notes. Repository-relative paths below were inspected on disk.

| Component | Inspected implementation | Finding and intended reuse |
|---|---|---|
| Starter memory | `scripts/recall.py`, `scripts/test_recall.py`, `memory/templates/` | Reuse offline BM25. Automatic discovery falls back to an unrelated sole/newest store; unreadable files are silently dropped; query terms use unordered summation. Existing recall tests are outside default CI collection. |
| Sentinel | Installed checkout `4e923b0`, starter `scripts/install-sentinel.*` | Keep the pre-push gate. Starter's default commit is `5808f2bdc024506fa3d49a367c88b42b15fdf164`; installed and pinned versions are different evidence targets. Do not infer live rule counts from README badges. |
| Overmind | Installed checkout `a8131b0`, `overmind/memory/store.py`, `overmind/intelligence/gold_benchmark.py`, `overmind/verification/signers.py` | Reuse scoped store, numerical fixtures and signers. Starter's default is `d3d2de5f84d852f27d64d1686f1e105e190ac375`. Inspect each adapter's actual revision. Existing research-comparison weights and competitor scores are authored ratings, not comparative experiments. |
| RapidMeta | Checkout `368137d`, `clone.py`, `tests/`, starter `scripts/install-rapidmeta.sh` | Reuse dashboard generator and browser/R parity tests. Installer targets tag `v1.1.0`; Bash checkout errors are currently swallowed with `|| true`. File presence/AST parsing does not establish that the requested revision was installed. |
| Source acquisition | `scripts/synthesis_capture_evidence.py`, `scripts/synthesis_participant_evidence.py`, `scripts/synthesis_preflight.py` | Reuse OA capture, snapshot binding, locators and correction handling; do not create another extractor. Hash agreement does not adjudicate whether a claim follows from its source. |
| Extraction and analysis | RCT-extractor installers, AACT-kit installers, `templates/count-recovery/`, `scripts/meta-self-audit.py`, `scripts/trial-identity-screen.py` | Reuse existing source/identity/denominator safeguards. Keep shared controls, survival effects and multi-report trial families explicit. |
| Replay and publication | `docs/meta-harness.md`, capsule templates, Pairwise70 installers | Reuse optional meta-harness replay and capsule output. A generated page or successful unpack is not a scientifically verified review. |
| Evaluation | `scripts/verify-local.py`, full-system integration workflow, `docs/gate-gaps.json`, paired SciCoQA scoring, blinded Synthesis evaluation | Extend existing CI and measurement contracts. Preserve explicit unavailable/failed states and keep synthetic tests distinct from real-paper evaluation. |

Portfolio recon was also run with `find-related-repos.py` and the existing
manifest for `memory harness evidence`; it returned Evidence Board, Evidence
Half-Life, evidence-inference, evidence-tribunal and EvidenceBridgeFHIR. These
are keyword matches, not replacement infrastructure. Direct inspection of the
existing starter, Sentinel, Overmind and RapidMeta supplied the relevant reuse
evidence. This work extends an existing project and creates no new repository.

## Milestones and acceptance criteria

### M1 — trustworthy memory and a measured baseline (implemented locally)

1. Preserve BM25 and legacy Markdown memories; scope automatic discovery to the
   requested project. Cross-project access requires an explicit memory path.
2. Refuse unreadable/invalid stores and file links that escape the selected store.
   Never turn a partially read corpus into a successful empty result.
3. Make scoring deterministic across Python hash seeds. Attach a byte hash and
   an explicit unverified-memory label to returned context. A hash is identity,
   not truth or source freshness.
4. Exercise clean and adverse cases with a portable offline contract benchmark;
   emit case-level outcomes and implementation hashes. Preserve pre-change
   results. These are development controls, not held-out research accuracy.
5. Run the existing memory tests in ordinary `pytest tests/` CI. Maintain the
   gate-gap registry and document remaining failures separately.

Done means the targeted tests and contract benchmark pass, original behavior
still retrieves relevant explicit-store memories, and the full-suite result is
reported without concealing pre-existing environment failures. No retrieval
quality or state-of-the-art claim follows from M1.

Implementation and verification are recorded in
[HARNESS-FOUNDATION-VERIFICATION.md](HARNESS-FOUNDATION-VERIFICATION.md).
The same evaluator now satisfies 11/11 development controls, against 5/11 in
the preserved baseline. Cross-platform release validation remains outstanding.

### M2 — a reproducible component installation and verification boundary

Use one machine-readable component lock with full commits/archive digests,
runtime requirements, supported platforms, and component-specific smoke tests.
Both installer languages consume or validate it. Existing-checkout updates
must reject dirty/conflicting state and failed checkout before persisting paths.
First repair test isolation: the Windows/Git Bash baseline exposed fake-command
resolution failure that allowed a bootstrap test to reach the real installer.
The bootstrap fixture now checks fake curl resolution and uses a disposable home;
audit equivalent PATH-based stubs before running other installation tests locally.
Add disposable Windows and Linux full-chain tests including RapidMeta and
AACT-kit; record expected and observed commits. Keep Sentinel and Overmind
results bound to the tested tree and never count a missing witness as PASS.

Acceptance: each deliberately wrong ref, unavailable tool, corrupt archive,
dirty checkout and malformed report refuses; a clean real installation runs
the declared adapters. No installer runs against the researcher's home as a test.

### M3 — a shared source-to-claim record and replay bundle

Extend the existing Synthesis packet rather than introduce competing schemas.
Represent source URL, permitted OA use, retrieved snapshot hash, typed identifier,
version/correction relation, exact locator, extraction decision, analysis input,
method/config hash and generated artifact. Model paper, trial and outcome as
different entities. A source change invalidates dependent verification. Memory
may point to this record but cannot promote it to evidence by repetition.
Export a minimal Workflow Run RO-Crate profile and validate conformance before
advertising compatibility. Reuse Overmind signatures with an explicit trust root;
signature validity alone never establishes scientific correctness.

Acceptance: replay rebuilds the same analytical payload from OA fixtures;
changed source/config, broken locator, unknown licence and unresolved trial
identity fail with a specific reason. Separate deterministic payload hashes from
timestamps, durations and other run metadata.

### M4 — a complete review with accountable decisions

Add resumable protocol/search/screen/extract/appraise/synthesise/report stages
over that shared record. Reuse CoLRev/ASReview through optional adapters where
they fit. Preserve search queries, deduplication decisions, excluded-study
reasons, independent reviewer decisions and adjudication. Freeze estimands and
analysis choices before outcome evaluation; changed protocols create versions.
RapidMeta becomes a view of the verified analytical artifact. Show unresolved
items and AI/model involvement alongside the human decision record.

Acceptance: an interrupted OA review resumes without repeating completed work;
unresolved disagreements and changed sources cannot produce a release-ready
state. Browser E2E and numerical parity checks inspect the resulting dashboard.

### M5 — independent, held-out scientific evaluation

Freeze review/trial-family splits, OA licences, corpus hashes and reference
adjudication before tuning. Use ASReview/SYNERGY for screening where licensed
inputs permit it, independent extraction references, metafor/R baselines for
fixed declared estimators, and masked real-paper audits for claim validation.
Existing SciCoQA/Synthesis paired and blinded scorers should be reused.

Report recall and workload together, field-level extraction errors, effect and
interval deviations, false alerts, abstentions, source/version errors, human
corrections, elapsed time and actual token/cost logs. Report all attempted cases,
including errors, and uncertainty by review rather than treating correlated
claims as independent. Compare like-for-like tasks with identical inputs and
budgets. A failed or null comparison is a result to preserve. No real held-out
split is created or consumed in M1; the final test is reserved for M5.

## Static versus dynamic disclosure

| Item | Kind | What it establishes |
|---|---|---|
| Milestones, severity priorities, comparator selection | Authored static plan | Engineering judgement, not measured performance |
| Inspected commits, files, installer refs | Observed source state | Exact inspected implementation; not all installations |
| Memory benchmark fixtures | Explicit synthetic development controls | Boundary and error-handling behavior only |
| BM25 constants | Existing static algorithm defaults | No parameter tuning or performance optimisation in M1 |
| Command results and per-case outcomes | Dynamic local execution | Behavior under the recorded code/environment |
| Overmind stored numerical references | Existing cited fixtures | Reproduction of stored references; not newly adjudicated clinical evidence |
| External comparator features | Primary documentation, checked 2026-11-11 | Documented capability; competitors were not run locally |
| Future scientific rankings | Not measured | Cannot support any present superiority claim |

## Release boundary

Keep changes on a dedicated branch. A local checkpoint is not SHIP. Full
cross-platform CI, a fresh project-specific Overmind verdict, and any required
TruthCert/registry reconciliation precede promotion. Update the portfolio index
and workbook only when lifecycle/submission state actually changes.
