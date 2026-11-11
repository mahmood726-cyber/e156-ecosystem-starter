# Synthesis source-bound replay v1

This first M3 increment packages the existing Synthesis v1.1 packet and runs its
participant-count checks against archived PMC XML. It records exact inputs,
prompt/configuration, source identifiers and versions, licences, source locations,
verifier code and the resulting analytical payload. `REPLAY_MATCHED` means the
recorded payload was reconstructed. Scientific validity remains `NOT_ESTABLISHED`.

## Verified ingredients and scope

This extends existing starter code inspected on disk; it is not a new extractor
or statistical engine. `synthesis_capture_evidence.py` supplies OA rights checks,
typed PMCID/DOI/version matching, text/cell locators and typed correction links.
`synthesis_preflight.py` supplies the v1.1 packet and review ledger.
`synthesis_participant_evidence.py` and `synthesis_v13_nma_preflight.py` supply
source-bound distinct-arm and restricted-population accounting. The DOI normalizer
in `synthesis_five_journal_corrections.py` is included in the verifier fingerprint.
The new code supplies the bundle, strict inventory, external digest check and replay.

Supported packets contain one primary PMC document, one corresponding source,
and 1–40 claims, each using `UNIQUE_ARMS` or `RESTRICTED` participant checks.
Every claim locator must match its resolved context quote. Additional arbitrary
numeric checks are refused because their numbers are not bound to source cells.
The existing correction-link checks are rerun; unresolved links or unreadable
sidecars prevent recording. External supplements are not automatically captured.

## Usage

The checked-in [OA development example](../examples/synthesis-replay-stepwise)
can be replayed without a network connection or third-party Python dependencies:

```console
python scripts/synthesis_replay.py verify examples/synthesis-replay-stepwise --expected-sha256 8ef7bf6f59995d7198185b835b485d3f18eeca064abbf0252eae850b3cdf58b6
```

Record your own supported packet and already licensed source snapshot:

```console
python scripts/synthesis_replay.py seal --packet packet.json --prompt prompt.md --xml article.xml --output new-bundle
python scripts/synthesis_replay.py verify new-bundle --expected-sha256 <digest-returned-by-seal>
```

Supply each explicit correction snapshot with `--linked-xml notice.xml`.
The output directory must not exist; its parent must already exist. Exit 0 means
recorded/matched; refusal is exit 2 with JSON on stderr. All source processing is
offline. Bundle data cannot request network access, execute commands, or replace
the trusted local verifier implementation.

## Integrity and trust

`manifest.json` binds byte sizes and SHA-256 values for `packet.json`, `prompt.md`,
`result.json`, and every `sources/<sha256>.xml`. A completion manifest is written
last. An interrupted write can leave an incomplete directory for inspection; it
cannot verify. Existing bundles are never overwritten. Duplicate JSON keys,
nonfinite numbers, invalid paths, symlinks/junctions, extra/missing files and
oversized inputs are refused. Limits are 2 MiB for packet/prompt/manifest and
32 MiB per XML/result, with at most eight correction snapshots.

Keep the returned manifest digest in a separate trusted record or reviewed
version-control commit. A hash stored only beside the files it describes is not
a trust anchor. This contract has no signing key, independent timestamp or
authenticated source retrieval. The canonical PMC URL is derived from the parsed
identifier; local XML could have been fabricated. The recorded origin status
explicitly says `ARCHIVED_XML_NOT_NETWORK_AUTHENTICATED`.

Replay checks all input bytes before execution, rechecks source identity/licence
and locations, reruns the original preflight pipeline, and compares the complete
canonical JSON payload byte-for-byte. It also requires the six implementing
modules to match the recorded profile, before and after execution. Python source
fingerprints normalize CRLF to LF for normal Git checkout portability; evidence
bytes are never normalized. A test walks local imports to detect newly unbound
implementation dependencies. Use the recorded code revision for an old bundle;
a verifier upgrade needs a new bundle and reviewed digest.

The contract excludes execution timestamps, durations and temporary paths from
the analytical payload. Runtime version/OS are visible in CI execution logs; the
bundle does not pin an interpreter image. Agreement across environments is
established by rerunning and comparing the payload. This is not a sandbox against
a hostile local filesystem, running interpreter or concurrent external writer,
and does not promise power-loss durability.

## Development evidence and attribution

The real example archives **Hargreaves EA, Mutrie N, Fleming JD**, “A Web-Based
Intervention to Encourage Walking (StepWise): Pilot Randomized Controlled Trial,”
*JMIR Research Protocols* (2016), [DOI 10.2196/resprot.4288](https://doi.org/10.2196/resprot.4288),
[PMC4746436](https://pmc.ncbi.nlm.nih.gov/articles/PMC4746436/), under
[CC BY 2.0](https://creativecommons.org/licenses/by/2.0/). The original EFetch XML
bytes are unchanged. The packet, prompt and derived JSON are new; they select one
baseline exclusion-accounting example, not the paper's intervention outcomes.

The captured record is version `PMC4746436.1`, PMID `26810251`, snapshot SHA-256
`082fdfae1bf21fd176ef2224959b05516305271bdf636388725febf670481ffb`.
The source's body paragraph 32 reports 103 attendees, six baseline exclusions and
97 eligible participants. Replay extracts the selected tokens and recomputes
`103 - 6 = 97`; the derived difference is zero. The actual source identifiers,
licence and source positions were read from that snapshot. Selection and the
disjoint/exhaustive interpretation are agent declarations, not independently
adjudicated facts. The packet labels the selection as agent-made and leaves
`full_text_checked` false: the selected passages were checked, without an
exhaustive full-paper audit. The article's later analysis population is a different quantity.
The [measured receipt](../benchmarks/replay/stepwise.json) binds the source,
manifest and resulting payload. This is a development example, not a held-out
benchmark or a scientific accuracy estimate.

Local validation: **47 synthetic replay controls** passed; the broader targeted
preflight/capture/NMA-contract run passed **140 tests and 82 subtests**; including
gate, ratchet and CI-lock controls, **240 tests and 82 subtests** passed. The real
example was sealed and successfully replayed locally. CI separately replays its
fixed digest on Windows and Linux. The control suite covers changed source/config/
output, malformed records, forged internal hashes, broken locations, licence
refusal, correction resolution, changed code, relocation and partial writes.

| Item | Static or dynamic | What it establishes |
|---|---|---|
| Bundle schema, supported check kinds and resource limits | Authored static contract | Intended engineering scope |
| Synthetic XML, invented test identifiers and defect mutations | Explicit static development fixtures | Adverse controls; no real trial findings |
| OA source XML, identity, licence and byte digest | Retrieved/parsed source record | Identity of the archived bytes; not proof they are the latest version |
| Selected count passages and analysis relationship flags | Agent-authored choices for this example | A declared extraction; no independent adjudication |
| Counts, arithmetic, locators, payload hashes and test results | Dynamic execution | Observed reconstruction under the recorded verifier |
| Comparative accuracy, sensitivity and superiority | Unmeasured | No present scientific performance claim |

## Remaining M3 work

This bundle does not establish trial-family identity, verify every manuscript
claim, fit a meta-analysis, or make a review release-ready. A reproducible
`REVIEW_CANDIDATE` stays a review candidate; `HOLD` in the review ledger is not
promoted by replay. Existing private evidence/correspondence packets stay private.

The [Process Run Crate 0.6 specification](https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate/)
links executions to software, inputs/configuration and outputs. That provides the
mapping target for a later RO-Crate export. This increment does not emit JSON-LD
or claim RO-Crate conformance. Typed trial-family relations, signed trust roots,
general analysis replay, independently validated profile export and held-out
scientific evaluation remain separate work.
