# File-backed study preflight

`scripts/synthesis_study_preflight.py` checks the files behind a proposed matched
study. It complements the [matched evaluator](MATCHED-HARNESS-EVALUATION.md):
configuration hashes, reference declarations and source-to-task lineage must
resolve to actual, consistent files. Success is `EVIDENCE_BOUND_NOT_RUN`.
Scientific results stay null. No model, recipe, network request or study is run.

## Private operating layout

Use two disjoint directories: an input-artifact root and a private evidence root.
Neither may contain the other. Source/task files and any derivation recipes and
receipts resolve within the input-artifact root. Context manifests, arm
configurations and reference records resolve within the private root. Do not
publish either directory or expose either whole directory to a model: adapters
receive only the frozen public task/source allowlist. Derived receipts can contain
calculation output and stderr; filenames alone do not make their contents public.

All paths in the inventory are canonical relative paths. Linked paths, junctions,
traversal and hardlink aliases across the two roles are refused. Every file is
limited to 16 MiB, including during repeated reads; oversize sources need an
explicitly reviewed source-packaging contract, not a silently truncated read.
The existing matched evaluator's source reader uses this bound too.

```text
python scripts/synthesis_study_preflight.py --manifest private/manifest.json --protocol private/protocol.json --inventory private/evidence-inventory.json --inputs input-artifacts --evidence private --output private/preflight.json
```

The command creates a new output exclusively. It refuses malformed/changed
inputs and never overwrites a previous result. CLI errors contain a generic
failure classification, not private paths or JSON field names. Direct Python API
exceptions remain detailed local diagnostics and should not be published.

## Inventory contract

The inventory has exactly `schema: synthesis-study-evidence-inventory-v1`,
`manifest_sha256`, `protocol_sha256`, `references`, `arms` and `tasks`.
Manifest/protocol/inventory identities use the existing canonical JSON digest:
sorted keys, compact separators, UTF-8 and no nonfinite numbers. Duplicate JSON
keys are refused. References, context files and other file identities use exact
byte SHA-256 unless the table below says canonical JSON.

| Mapping | Required fields and checks |
|---|---|
| Each `references` entry | Exactly `role`, `reference`, `file`, `sha256`. There must be one each for `analysis_plan_reference`, `custodian_receipt_reference`, `independent_review_plan_reference`, `unseen_corpus_receipt_reference`; reference strings must match the protocol. Files live under the private root and must match their byte hashes. |
| Each reference file | Exactly `schema: synthesis-study-reference-v1`, `role`, `reference`, `manifest_sha256`, `protocol_sha256`, `statement`. Scope and role are checked inside the hashed file; statement is a nonempty declaration, not authenticated approval. |
| Each `arms` entry | Exactly `arm_id`, `config_file`, `model_config_file`, `tools_file`. One per protocol arm. Each file is a private JSON object whose canonical JSON hash matches the corresponding `config_sha256`, `model_config_sha256` or `tools_sha256`. The report retains its byte hash too. |
| Each `tasks` entry | Exactly `claim_id`, `context_file`, `context_sha256`, `node_id`. One per protocol task. Context manifest lives under the private root; its exact bytes must match the declared hash. Its artifacts resolve under the input-artifact root. |

All mapping sets must match exactly; unknown, duplicate or missing rows fail.
There are no supplied human approvals, scientific labels or model configurations.
Operators construct these files from genuine, privately retained evidence.

## Task lineage contract

The mapped node's file and output hash must match the task. Every graph artifact
is read with a size bound; every node must be CURRENT. The selected node's
reachable source files/hashes must exactly match the protocol source inventory.
Extra unrelated nodes do not satisfy this reachable-source check.

A raw task that is itself an inventoried source receives `RAW_SOURCE`.
A derived task receives `RECEIPT_BOUND` only when its complete declared ancestor
chain passes [derivation validation](HARNESS-DERIVATIONS.md). The preflight checks
retained execution receipts; it does not replay their recipes or independently
authenticate execution. Files are checked again before returning the report.

This strict increment cannot admit an empty source inventory for a source-limited
task. Keep that planned task and its abstention in the study denominator; resolve
its representation through a reviewed contract extension before freezing the
study. Do not delete difficult cases to obtain a successful preflight. Unbounded
or unsupported transformations and missing human derivations likewise remain
preparation blockers, not grounds to invent receipts.

## Meaning of a successful report

Success binds the supplied configuration objects, scoped declaration files and
task/source identities. The report exposes identities and statuses, not private
document text, filesystem paths or reviewer mappings. Hashes remain linkable
metadata. Recorded declarations can be false; a filesystem owner can replace
unsigned evidence and recompute its hashes. Recipes may calculate the wrong thing.

The report therefore retains `UNVERIFIED_EXTERNAL` for human identity, custody,
rights, unseen status, budget authorization, reviewer independence and semantic
fidelity. It grants no launch authorization, runtime enforcement, scientific
PASS or superiority claim. Actual run evidence, usage/invoices and adjudications
remain outside this preparation-only increment. The [prospective study plan](HARNESS-PROSPECTIVE-STUDY.md)
lists the remaining scientific and integration work.

| Item | Static implementation | Dynamic evidence |
|---|---|---|
| Schemas, path/size limits and scope checks | Enforced offline | Synthetic malformed/missing/changed/alias controls |
| Configuration, reference and task identities | No study values supplied | Computed from supplied actual files |
| Derivation lineage | Retained receipt consistency | Trusted producer execution; semantic review remains external |
| Custodian, expertise, rights, exposure, budget | Never inferred | Real independent verification required |
| Scientific performance and costs | No results | Fresh study and observed records required |

```text
python -m pytest tests/test_synthesis_study_preflight.py tests/test_synthesis_matched_eval.py -q
```
