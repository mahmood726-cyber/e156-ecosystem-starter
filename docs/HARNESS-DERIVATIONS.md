# Execution-bound derivation receipts

Every derived context node now needs a receipt produced by an explicit checked
calculation. Updating a source hash cannot by itself make old downstream work
CURRENT. This closes the byte-only freshness gap; it does not establish the
scientific correctness of a calculation.

## Admission and migration

Source and skill roots retain the v1 context format. Derived nodes without a
receipt are `DERIVATION_UNVERIFIED`; changed, missing or inconsistent receipts
are `DERIVATION_INVALID`. An invalid ancestor makes descendants
`DEPENDENCY_INVALID`. `check`, context packing, evidence reads and calculation
workers refuse these nodes. Receipt enforcement is mandatory, including for
legacy derived nodes. There is no switch that labels legacy bytes CURRENT.

Recompute in dependency order with new revision paths. A calculation can replace
the same node ID in a newly written manifest, but cannot overwrite an existing
artifact, receipt or manifest. Existing journals remain bound to their original
code/configuration/context; start a new journal after migration. Human-produced
extractions and judgments have no attestation-import shortcut in this increment.
They remain unverified until supported provenance is supplied through an explicit
execution or a separately designed, reviewed human-workflow contract.

## Produce a derivation

Run from the repository root. Keep operator study material outside the repository.
`--root` contains the evidence, recipe and output revision paths. The manifest and
request below are operator-supplied files, not supplied scientific evidence.

```text
python scripts/harness_derivation.py run --root study --manifest study/context.json --spec study/request.json --output-manifest study/context-v2.json
python scripts/harness_context.py check --root study --manifest study/context-v2.json
```

The request has exactly these fields:

| Field | Contract |
|---|---|
| `schema` | `e156-derivation-request-v1` |
| `node` | Exactly `id`, `kind`, `file`, `parents`, `expires_at`; a non-root kind, explicit parent IDs and a new relative output path. Output SHA-256 is calculated by the producer. |
| `recipe_file` | Relative UTF-8 Python file, at most 65,536 bytes. The explicit run action executes this recipe inside the checked worker. |
| `receipt_file` | New relative receipt path, distinct from all artifacts and control inputs. |
| `worker` | Existing complete Docker worker policy: reviewed image digest, memory, CPU, process, temporary-storage and output limits. |
| `timeout_seconds` | Numeric deadline from 1 through 300 seconds. |

Each direct parent is exposed as `/inputs/<parent-id>.data` in the read-only
worker snapshot. The artifact is the UTF-8 encoding of the returned `stdout`
text; the worker already decodes raw stdout with replacement for invalid UTF-8.
This is not a byte-exact archive of arbitrary binary stdout. Use explicit text
serialization, such as deterministic JSON, for numeric results.

The producer reads the recipe and recursive input identities before execution,
executes the existing isolated Linux Docker worker, verifies successful cleanup
and its returned input/code bindings, and checks inputs, recipe and producer code
again afterward. Missing Docker refuses execution; there is no host fallback.
It creates artifact and receipt exclusively, validates the new node, then writes
the new manifest last. Interrupted publication may leave orphan revision files;
inspect them and choose new paths for an intentional retry. It never automatically
reruns an uncertain calculation or imports a JSON document claiming to be a
worker result.

## Receipt contents and validation

The node's `derivation` reference contains exactly `recipe_file`,
`recipe_sha256`, `receipt_file` and `receipt_sha256`. File hashes cover exact
bytes. The receipt contains the output node without its own derivation reference,
the exact parent set with output and recursive-lineage hashes, recipe hash,
execution start/end, complete worker policy/deadline, producer code hashes and
the full worker result, including stdout/stderr and cleanup confirmation.

Recursive lineage hashes include node metadata, its receipt reference and all
ancestor identities. Recomputing an intermediate node to identical output bytes
therefore does not preserve the validity of an old descendant receipt. Changed
parent sets, source rights metadata, recipes and node descriptions also invalidate
affected receipts. Recipe and receipt files receive the same control-path
protection as other evidence, including SQLite sidecars and existing hardlink
aliases.

Inspection validates retained evidence without executing any recipe or network
request. Historical producer hashes are checked for completeness and retained;
they are not required to equal today's producer code. This supports examining
old artifacts after software changes, not automatic upgrading of their execution
journals. Code versions and scientific acceptability still need review.

## Trust and evidence boundary

These unsigned receipts establish consistency under a trusted local producer.
An owner able to rewrite all artifacts, receipts and manifests can forge a
consistent history. There is no independent execution attestation, authentication
or signed custody claim. The checks do not prevent a user from relabeling a
derived artifact as a root source or concealing an undeclared dependency.

A recipe can ignore its inputs or implement the wrong analysis. A receipt proves
neither semantic fidelity to a paper nor valid statistical reasoning. Scientific
review remains independent. Reproducibility also depends on the recipe avoiding
nondeterministic operations; output equality is checked, not guaranteed for every
permitted Python program. Concurrent hostile filesystem modification is outside
the trusted local-writer boundary.

| Item | Static implementation/configuration | Dynamic evidence |
|---|---|---|
| Schemas, required receipts and transitive invalidation | Implemented admission policy | Synthetic regression controls and actual Docker integration test |
| Inputs, output, recipe and receipt hashes | No research values embedded | Computed from files and returned execution output |
| Worker policy and deadline | Explicit operator choices | Checked worker execution and cleanup result |
| Scientific conclusions, rights and human review | Not inferred | Independent source and methods review required |
| Comparative benefit | Not measured by this change | Fresh prospective study required; previous benchmark remains historical |

```text
python -m pytest tests/test_harness_context.py tests/test_harness_derivation.py tests/test_harness_runtime.py tests/test_harness_worker.py -q
```

The actual-container test is mandatory in the dedicated Linux Docker CI job.
Local environments without the reviewed image skip that test explicitly.
