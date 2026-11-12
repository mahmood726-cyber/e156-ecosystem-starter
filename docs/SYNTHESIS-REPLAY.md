# Synthesis source-bound replay

These M3 increments package the existing Synthesis v1.1 packet and run its
participant-count checks and optional study links against archived sources. They record exact inputs,
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
The current profile also fingerprints the intake-evidence, count-identity,
root-deduplication and case-state dependencies imported by the integrated preflight.
The replay interface does not accept intake `evidence_checks` or a private case
sidecar; those require a separately bounded replay contract.

Supported packets contain one primary PMC document, one corresponding source,
and 1–40 claims, each using `UNIQUE_ARMS` / `RESTRICTED` participant checks or
an exact registration passage with `registered_trial`. A registration claim
cannot also carry a participant check. Every claim locator must match its resolved quote. Additional arbitrary
numeric checks are refused because their numbers are not bound to source cells.
The existing correction-link checks are rerun; unresolved links or unreadable
sidecars prevent recording. External supplements are not automatically captured.

## Usage

The checked-in [OA development example](../examples/synthesis-replay-stepwise)
can be replayed without a network connection or third-party Python dependencies:

```console
python scripts/synthesis_replay.py verify examples/synthesis-replay-stepwise --expected-sha256 c7fb904293fcf13ec542553b9667bfec51ca7c713d1183b418ec93b6cbb177d3
```

Record your own supported packet and already licensed source snapshot:

```console
python scripts/synthesis_replay.py seal --packet packet.json --prompt prompt.md --xml article.xml --output new-bundle
python scripts/synthesis_replay.py verify new-bundle --expected-sha256 <digest-returned-by-seal>
```

Supply each explicit correction snapshot with `--linked-xml notice.xml`.
Supply each registry snapshot with `--registry-json registry.json` when the
packet declares `study_links`. The manifest is v2 when registry inputs are present;
participant-only bundles retain v1. Both formats use the current verifier profile.
The output directory must not exist; its parent must already exist. Exit 0 means
recorded/matched; refusal is exit 2 with JSON on stderr. All source processing is
offline. Bundle data cannot request network access, execute commands, or replace
the trusted local verifier implementation.

## Typed study links

Studies and reports are different entities: several reports may describe one
study, and a report may describe several studies. Cochrane recommends linking
reports using registration identifiers and other study characteristics. The
engineering inference here is to record a bibliographic edge and leave population
and outcome decisions explicit. See [Cochrane Handbook, chapter 5, section 5.2](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05).

The optional packet section has exactly this structure (angle-bracket values
are documentation slots, not a runnable research record):

```json
{"study_links":{"schema":"e156-study-links-v1","links":[{
  "nct_id":"<source-backed NCT identifier>",
  "registry_sha256":"<SHA-256 of archived API JSON>",
  "reference_type":"<RESULT or DERIVED, as recorded>",
  "registration":{"quote":"<exact registration passage>","locator":"<resolved source locator>"}
}]}}
```

The verifier requires the article's unambiguous PMID, an exact source-bound
registration passage with one selected NCT, and a registry record whose primary
`protocolSection.identificationModule.nctId` agrees. The registry must contain
exactly one reference with that PMID and the declared `RESULT` or `DERIVED` type;
`BACKGROUND`, missing, conflicting and duplicate matches refuse. The API v2
JSON structure was checked against the actual official response; see the
[NLM API announcement](https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html)
and [official API documentation](https://clinicaltrials.gov/data-api/api).

There are at most eight distinct NCT links per report and eight registry snapshots.
The parser accepts canonical `NCT` plus eight ASCII digits, or one space between
`NCT` and those digits in normalized source text; it retains the printed literal.
It does not guess digit corrections, resolve aliases, or merge registrations.
Other registry schemes are unsupported. Unused snapshots and unknown link fields
refuse. Each output edge retains the source quote/location, registry content hash
and JSON pointer to the matching reference. Partial or invalid protocol
update-posted dates refuse instead of acquiring invented days.

`REPORT_AND_REGISTRY_LINKED` establishes agreement of those selected archived
fields. It does not establish independent trial participants, primary publication
status, registration timing, outcome equivalence or source authenticity. A matching
`DERIVED` reference stays `DERIVED`. `cohort_overlap` and `outcome_equivalence`
remain `UNASSESSED`; `pooling_readiness` remains `HOLD`. This strict reciprocal
requirement can refuse a genuine relationship when the registry omits the paper:
refusal means the supported contract could not establish it, not that the paper
is unrelated or fraudulent. Cross-report cohort reconciliation remains future work.

## Integrity and trust

`manifest.json` binds byte sizes and SHA-256 values for `packet.json`, `prompt.md`,
`result.json`, every `sources/<sha256>.xml`, and (v2) every
`registries/<sha256>.json`. A completion manifest is written
last. An interrupted write can leave an incomplete directory for inspection; it
cannot verify. Existing bundles are never overwritten. Duplicate JSON keys,
nonfinite numbers, invalid paths, symlinks/junctions, extra/missing files and
oversized inputs are refused. Limits are 2 MiB for packet/prompt/manifest and
32 MiB per XML/result, with at most eight correction snapshots. Each registry
snapshot is limited to 2 MiB and is parsed with the same strict JSON rules.

Keep the returned manifest digest in a separate trusted record or reviewed
version-control commit. A hash stored only beside the files it describes is not
a trust anchor. This contract has no signing key, independent timestamp or
authenticated source retrieval. The canonical PMC URL is derived from the parsed
identifier; local XML could have been fabricated. The recorded origin status
explicitly says `ARCHIVED_XML_NOT_NETWORK_AUTHENTICATED`.
Registry records likewise say `ARCHIVED_JSON_NOT_NETWORK_AUTHENTICATED`.

Replay checks all input bytes before execution, rechecks source identity/licence
and locations, reruns the original preflight pipeline, and compares the complete
canonical JSON payload byte-for-byte. It also requires the ten implementing
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

The initial study-link verifier upgrade preserved the analytical payload. The
subsequent integration of main PR #92 expanded the fingerprint from six to ten
modules and added bounded source-token context. StepWise still reconstructs the
same arithmetic, but its overall ledger decision is now `HOLD`, with
`scope_status: REVIEWER_ATTESTATION_ONLY`; matching arithmetic is insufficient
to clear an agent-declared population mapping. Its payload and manifest digests
therefore changed. Source, packet and prompt bytes remain identical.
The [previous receipt](../benchmarks/replay/history/stepwise-9875059.json) is
preserved, and the current receipt records the predecessor digests. Old bundles
require their recorded verifier; old hashes are not relabelled as current passes.

The second example archives **Vahlberg B, Lundström E, Eriksson S, Holmbäck U,
Cederholm T**, “Effects on walking performance and lower body strength by short
message service guided training after stroke or transient ischemic attack (The
STROKEWALK Study): a randomized controlled trial,”
[DOI 10.1177/0269215520954346](https://doi.org/10.1177/0269215520954346),
[PMC7874373](https://pmc.ncbi.nlm.nih.gov/articles/PMC7874373/), under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The original XML bytes
are unchanged. The selected registration sentence at `abstract 1 p 9` names
`NCT02902367`; the archived registry lists the article's PMID `32942914` as
`DERIVED` at `/protocolSection/referencesModule/references/2`.

Only public factual identifier/date/reference metadata from the
[official API projection](https://clinicaltrials.gov/api/v2/studies/NCT02902367?fields=NCTId,LastUpdatePostDate,ReferencePMID,ReferenceType)
is archived, without narrative descriptions or contact information. See
[ClinicalTrials.gov terms](https://clinicaltrials.gov/about-site/terms-conditions);
the article's CC BY licence is not asserted for registry content. The registry's
protocol update-posted date, `2017-09-19`, is a source field, not the retrieval
date or a version date for later derived references. Retrieval times, hashes and
the observed graph are in the [STROKEWALK receipt](../benchmarks/replay/strokewalk.json).
The selection is agent-made, `full_text_checked` remains false, and no treatment
effect or independent adjudication is asserted.

After the same main integration, STROKEWALK's result adds the two empty
source-context boundary strings around its complete registration sentence.
The study link, identifiers, reference type and source/registry/input bytes are
unchanged. Its manifest and payload have new digests; the
[previous receipt](../benchmarks/replay/history/strokewalk-9875059.json) remains
available. Neither migration changes the selection or claims scientific accuracy.

```console
python scripts/synthesis_replay.py verify examples/synthesis-replay-strokewalk --expected-sha256 8ebe174bf7613830c5c919b989d8967c3f56d3ea5b742dd4a8b561293faf4533
```

On 12 November 2026, the scalar, source-bound scale, rounding and reply-inventory
upgrade changed two fingerprinted modules. Both bundles were sealed afresh and
verified with the new code. Every archived input and the complete analytical
result bytes remain unchanged. Only the manifests' verifier fingerprints and
their trusted digest references changed. The preceding
[StepWise receipt](../benchmarks/replay/history/stepwise-fb511d8.json) and
[STROKEWALK receipt](../benchmarks/replay/history/strokewalk-fb511d8.json) remain
available; their original bundles are retained at Git revision `fb511d8`.
Historical profile-validation measurements remain historical. The new bundles
require a fresh export/profile check, rather than relabelling earlier validation.

The concurrent trusted-review/checklist integration at public revision `34359562`
also consumes these bundles. Its current example protocol and unreviewed dossier,
CLI commands and test trust-anchor data were rebound to the regenerated manifests.
The source excerpts, report/entity selections and empty reviewer-ballot lists
remain unchanged. The original configurations remain at that public revision;
the rebuilt checklist and dossier still retain scientific `HOLD`.

At the preceding revision, local validation reported **88 synthetic replay controls** passed. Both real examples
were sealed and successfully replayed locally. CI separately replays both fixed
digests on Windows and Linux. The control suite covers changed source/config/
output, malformed records, forged internal hashes, broken locations, licence
refusal, correction resolution, changed code, relocation, partial writes, registry
identity/reference disagreement, registration-only claims and one report linked
to multiple trials. These are development cases, not held-out scientific accuracy.

| Item | Static or dynamic | What it establishes |
|---|---|---|
| Bundle schema, supported check kinds and resource limits | Authored static contract | Intended engineering scope |
| Synthetic XML, invented test identifiers and defect mutations | Explicit static development fixtures | Adverse controls; no real trial findings |
| OA source XML, identity, licence and byte digest | Retrieved/parsed source record | Identity of the archived bytes; not proof they are the latest version |
| Registry primary ID, protocol date, PMID and reference type | Retrieved/parsed public factual metadata | Reciprocal field agreement; no proof of cohort or outcome equivalence |
| Selected count passages and analysis relationship flags | Agent-authored choices for this example | A declared extraction; no independent adjudication |
| Counts, arithmetic, locators, payload hashes and test results | Dynamic execution | Observed reconstruction under the recorded verifier |
| Comparative accuracy, sensitivity and superiority | Unmeasured | No present scientific performance claim |

## Remaining M3 work

These bundles do not establish trial-family or cohort identity, verify every manuscript
claim, fit a meta-analysis, or make a review release-ready. A reproducible
`REVIEW_CANDIDATE` stays a review candidate; `HOLD` in the review ledger is not
promoted by replay. Existing private evidence/correspondence packets stay private.

The optional [RO-Crate exporter](SYNTHESIS-ROCRATE.md) packages this unchanged
bundle with JSON-LD execution provenance. It targets Process Run Crate 0.5 and
RO-Crate 1.1, the versions covered by the pinned validator. The replay command
itself does not issue a profile-conformance verdict. Adjudicated trial-family/
cohort relations, signed trust roots, general analysis replay, migration to the
newer profile versions and held-out scientific evaluation remain separate work.
