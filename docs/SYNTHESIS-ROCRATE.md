# Synthesis replay provenance export

## Implementation contract

This M3 increment exports an existing verified replay bundle as an attached
Process Run Crate. It reuses `synthesis_replay.py`, its ten-module code profile,
source/registry checks, strict inventory and external manifest trust anchor.
The exporter adds JSON-LD provenance and packages those exact inputs/results
with the implementing source and its licence. It does not introduce an extractor,
statistical estimator, signature system or scientific adjudicator.

Source inspection on 2026-11-11 found a version gap: the current
[Process Run Crate specification is 0.6](https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate/),
but the released `roc-validator==0.13.1` wheel's
`profiles/process-run-crate/profile.ttl` identifies **0.5**, inheriting **RO-Crate 1.1**.
This increment therefore targets [Process Run 0.5](https://www.researchobject.org/workflow-run-crate/profiles/0.5/process_run_crate/)
and [RO-Crate 1.1](https://www.researchobject.org/ro-crate/specification/1.1/).
It does not assert 0.6/1.3 conformance. The primary validator is
[CRS4's rocrate-validator](https://github.com/crs4/rocrate-validator), pinned with
its transitive dependencies in a separate optional lock.

The crate records a **new replay during export**, with observed UTC start/end
times and Python/OS version, rather than inventing the original run's date or
operator. A `CreateAction` connects the selected inputs/configuration, executing
software and reproduced result. A completed action means execution completed;
scientific validity remains `NOT_ESTABLISHED`. The original packet's reviewer
declarations, HOLD decisions, source licences and registry reference types survive
unchanged. No person/organization is invented for the recommended `agent` field.

The root has a mixed-rights statement. Each article retains its parsed licence;
software carries the repository MIT licence. Registry metadata retains its
service-terms notice. Input packets and prompts receive no newly asserted licence.
Publication of a private input bundle is a separate decision; this CLI only
creates local files.

The original replay subtree is copied byte-for-byte. Software copies use the
replay contract's LF-normalized bytes. All payload files have sizes and SHA-256
values in the JSON-LD. A separately retained metadata digest anchors the export.
The local verifier replays with trusted local code, compares the complete expected
graph and refuses unexpected files, changed code/data, links and malformed records.
It never imports software from a supplied crate. RO-Crate profile validation is
a separate check; its success alone cannot establish source truth or byte integrity.

Analytical payload bytes remain deterministic. Execution times and run IDs are
observations and intentionally differ across exports. No time, platform or
temporary path is injected into the existing analytical result.

## Acceptance and preflight

Work from the starter root. Existing smoke targets are the attributed StepWise
and STROKEWALK bundles and their recorded manifest digests. The baseline is
commit `7b42002dac039c759e12b0ee518f5aac2affca23`; neither bundle is modified.
Export and local verification use only the standard library. Upstream profile
validation runs in a separate environment, with inherited required checks enabled,
plus deliberately broken root/action controls. It may retrieve standard contexts;
offline replay/export itself makes no network calls.

Acceptance: both real development bundles export and still replay identically;
the upstream validator accepts the specified profile and rejects the negative
controls; the new integration tests, selected existing regression tests and
remote full suite pass. Bounded verification uses at most three repair loops per
failure. Current local Windows whole-suite restrictions remain in force.

| Item | Static or dynamic | Meaning |
|---|---|---|
| Target profile, graph mapping and limits | Authored static contract | Interoperability scope, not accuracy |
| Copied evidence, IDs, licences and results | Parsed and replayed existing bytes | Same archived development inputs |
| Run UUID, times and runtime version | Observed during export | New execution, not original study provenance |
| Software/dependency hashes | Computed from actual files/wheels | Exact implementation used |
| Upstream validation and adverse controls | Executed measurements | Specified profile/requirement coverage only |
| Scientific validity and human adjudication | Unestablished | Export cannot promote the evidence |

## Local use

From the repository root, export the existing attributed example to a new directory:

```console
python scripts/synthesis_rocrate.py export examples/synthesis-replay-strokewalk --expected-sha256 e0e02c64467a9a34ad41230eb64d4586c010f5531ed3091a01ffdd3cead31481 --output exported-crate
python scripts/synthesis_rocrate.py verify exported-crate --expected-sha256 <metadata-digest-returned-by-export>
```

Keep that metadata digest outside the crate in a trusted record. The local
receipt explicitly says profile validation was not run by the integrity check.
The crate contains `ro-crate-metadata.json`, `run.json`, the complete unchanged
`replay/` subtree and `software/` with the implementing modules and MIT licence.
The supplied software is available for inspection; verification imports the
trusted local implementation, never code from the crate. Old exports require
their recorded exporter and replay implementation.

For the optional independent implementation of profile checks, install the
separate lock in a virtual environment:

```console
python -m pip install --only-binary=:all: --require-hashes -r requirements-rocrate.lock
rocrate-validator validate exported-crate --no-auto-profile --profile-identifier process-run-crate-0.5 --requirement-severity required --enforce-availability
python scripts/check-synthesis-rocrate.py --output new-development-receipt.json
```

The last command measures both existing examples, checks expanded RDF file hashes,
and creates temporary copies with a missing execution instrument, root date or
payload file. It requires rejection of the intended defect. Dependency versions,
wheel lock hash, context hashes, executed checks and recommendation findings are
recorded separately from the original analytical payload. The two standard
contexts are pinned in `schemas/rocrate-contexts.json`; an unavailable or changed
context refuses the measurement. No check or inherited profile is disabled.

## Measured development result

The [integrated Windows measurement](../benchmarks/rocrate/development-integrated.json) on
2026-11-11 binds the actual checker/exporter bytes, dependency lock and contexts.
For each of the StepWise and STROKEWALK examples, the upstream validator executed
104 checks, including **47 required checks**, with **zero skipped checks** and
all required checks passing. Each example retained six recommendation findings;
recommended conformance did not pass. All three deliberate defects per example
(missing instrument, root date and payload file) were rejected by the intended
required checks. RDF expansion preserved all 18 StepWise and 19 STROKEWALK file
digests. Both analytical payload digests matched their existing replay receipts.

The [earlier measurement](../benchmarks/rocrate/development.json) remains
unchanged as a historical observation of the six-module profile. Integration
with main PR #92 added four imported modules and source-token context, and
keeps StepWise's overall decision on HOLD. The [replay migration](SYNTHESIS-REPLAY.md#development-evidence-and-attribution)
records the changed payload/manifest hashes and preserves the previous receipts.
Original source, registry, packet and prompt bytes are unchanged.

These are two development examples and synthetic adverse controls, not held-out
scientific evaluation. The receipt describes an observed export execution; its
new UUID, timestamps and metadata digest differ on subsequent runs. CI repeats
the measurement on Windows and Linux. The 45 local export integration cases
cover byte preservation, graph integrity and refusal behavior separately from
upstream profile validation.

## Recommendations and limits

Recommended conformance is reported separately from required checks. The
operator, author and publishing organization are not established by these
examples; their absence is reported rather than populated from the machine's
username. Relative software paths preserve portability and are permitted by the
profile, although the validator recommends absolute identifiers.

The pinned validator's recommended `Action actionStatus` shape compares string
literals, whereas this export retains a JSON-LD entity reference for
[Schema.org's ActionStatusType](https://schema.org/actionStatus). That finding
remains in the report; the external rule is unchanged. UTC timestamps use
millisecond precision, which its timestamp pattern accepts. Full recommended
conformance is not claimed. A required-profile result is still bounded by the
upstream implementation's coverage; negative controls do not prove completeness.

The base 1.1 context does not define `sha256`, so the export supplies an explicit
mapping to [Schema.org sha256](https://schema.org/sha256). The development runner
checks that RDF expansion retains every file digest. JSON key presence alone
would not establish semantic interoperability.

Hash and graph verification do not authenticate a local source, timestamp,
operator or host. The package includes source code, not a pinned interpreter
image. Concurrency with hostile filesystem writers and power-loss durability
are outside the contract. A partial export has no completion metadata and is
not accepted. Process Run 0.6/RO-Crate 1.3, signed trust roots, cross-report cohort
adjudication and held-out scientific evaluation remain subsequent work.
