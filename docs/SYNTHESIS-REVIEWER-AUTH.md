# Reviewer-key authorization and persistent decisions

This increment connects the [decision-record adapter](SYNTHESIS-ADJUDICATION.md)
to explicitly authorized signing keys and a bounded SQLite workflow. A signature
authenticates a key's authorization of a frozen record under the supplied policy.
The policy's assignment of a key to a reviewer/person remains operator-attested.
Real-world human identity, independence and scientific correctness are not established.

`decision_ready` means every relation has a recorded definite agreement or
adjudication and every original ballot and adjudication has its required signature.
It does not mean ready for pooling, publication or release. All receipts retain
`HOLD`, `scientific_validity: NOT_ESTABLISHED` and `release_eligible: false`.

## Verified ingredients and reuse

The existing replay, decision-record, signing and persistent audit modules were
inspected before implementation. Both archived OA bundles and their original
identifiers/results remain unchanged. The new `synthesis_reviewer_auth.py` reuses
the existing signing adapter's strict base64, project trust policy, public-key
fingerprints, corrected Ed25519 point validation and explicit Overmind signer.
It re-executes `synthesis_adjudication.verify` rather than trusting a saved receipt.
`synthesis_decision_runner.py` reuses the audit module's bounded inventory,
SQLite connection, transaction/event writing and response helpers. Its protocol
and transition validation are distinct; existing audit states are not migrated.

The new envelope follows [DSSE's typed pre-authentication encoding](https://github.com/dsse-lf/dsse/blob/master/protocol.md).
The payload type is `application/vnd.e156.reviewer-authorization.v1+json`, distinct
from replay signatures. Signature verification uses the
[cryptography Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
Runtime dependencies retain `scripts/requirements-signing.lock`; no new package or
cryptographic algorithm is introduced. Dedicated CI uses the existing locked
Overmind source commit. Local development used the installed signer, with the
locked source separately exercised in CI.

## Inputs and key assignments

All anchors are externally retained SHA-256 values of exact file bytes. The
caller supplies a project, dossier, existing signing trust policy, reviewer roster,
signature set and explicit report-alias paths. No source retrieval, production key
generation, discovery or enrollment occurs. Unknown/missing aliases, path overlap,
linked paths, malformed inputs and changed anchors refuse verification.

The trust file retains the [existing signing policy](SYNTHESIS-SIGNING.md):
`schema: e156-synthesis-trust-v1`, `project`, and public `keys`, including each
key's fingerprint and active/revoked status.

The roster has exactly:

| Field | Contract |
|---|---|
| `schema` | `e156-reviewer-roster-v1` |
| `project` | Same canonical project as dossier, caller and trust policy |
| `trust_sha256` | The externally reviewed trust-policy digest |
| `members` | 2–32 records with `reviewer`, `person_id`, `keyid`, `roles` |

Reviewer and person IDs are lowercase local tokens using the dossier's existing
identifier grammar. Each key must be present in the trust policy. Reviewer IDs,
person IDs and key fingerprints are unique across the roster. Roles are a sorted,
nonempty subset of `adjudicator` and `reviewer`. The role authorizes how a key may
be used; the dossier still enforces a separate adjudicator and retains both
original ballots. The roster may contain alternative reviewers not used in a
particular dossier. It cannot represent key rotation with duplicate assignments;
use a newly approved roster and trust-policy version.

Uniqueness prevents reusing a declared principal or key under two roster aliases.
It cannot detect one person controlling multiple keys and declaring different
person IDs. The tool reports `KEY_AUTHENTICATED_UNDER_POLICY` authorization,
`human_identity: NOT_ESTABLISHED` and `independence: NOT_ESTABLISHED`.

## What each signature authorizes

Each DSSE envelope contains one signature and the canonical JSON statement:
`schema: e156-reviewer-authorization-v1`, `project`, `dossier_sha256`,
`trust_sha256`, `roster_sha256`, `relation`, `role`, `reviewer`,
`context_sha256`, `record_sha256`, and `scientific_validity: NOT_ESTABLISHED`.
The verifier derives the complete expected statement again from current inputs.
It verifies exact canonical payload bytes, the role/key assignment, active key
status, and the Ed25519 signature. It does not accept a replay-signature envelope
as a reviewer authorization.

`record_sha256` binds the entire original review or adjudication object.
`context_sha256` is the decision adapter's binding of report anchors, endpoint
scopes, relation and project. The dossier digest binds every byte of the complete
frozen dossier, including the other ballots. Editing any dossier byte requires
all signers to authorize the new final version. Adding an adjudication also
requires fresh signatures from the original reviewers; the original review
objects remain present. This is final-document authorization, not blinded review
or an incremental ballot-collection service.

The signature-set JSON has exactly `schema: e156-reviewer-signatures-v1` and
`envelopes`. Every actual ballot and adjudication requires one signature, including
losing and UNCLEAR original ballots. Duplicates, missing or extra signatures,
wrong roles/projects/dossiers/policies and revoked keys refuse. An empty set
cannot pass. Signed disagreements may verify as authentic declarations, but
`decision_ready` remains false and the persistent completion stage refuses them.

Input and source inventories plus code fingerprints are checked before/after
verification. Receipts bind the existing decision receipt, signature-set and
policy hashes, implementing source profile and verified authorizations. Repeated
verification is deterministic under the same inputs/code. Old receipts are not
accepted as input. This is an offline policy model: the caller must select the
current approved anchors. The tool cannot detect that an operator supplied an old
valid policy, a newer unseen correction, a compromised key, or dishonest identity
assignments. Signatures do not establish freshness or semantic support.

## Commands

Use the existing isolated signing environment; protect private keys with OS access
controls. The signer takes only an explicit raw 32-byte key file, verifies the
returned signature independently, writes a new output exclusively, flushes it,
and refuses an existing output. Verification needs public inputs only.

```console
python scripts/synthesis_reviewer_auth.py sign --project review-id --dossier decisions.json --dossier-sha256 DOSSIER_DIGEST --trust trust.json --trust-sha256 TRUST_DIGEST --roster roster.json --roster-sha256 ROSTER_DIGEST --bundle report=review-bundle --relation relation-id --reviewer reviewer-id --role reviewer --private-key private-key --output reviewer-envelope.json
python scripts/synthesis_reviewer_auth.py verify --project review-id --dossier decisions.json --dossier-sha256 DOSSIER_DIGEST --trust trust.json --trust-sha256 TRUST_DIGEST --roster roster.json --roster-sha256 ROSTER_DIGEST --bundle report=review-bundle --signatures signatures.json --signatures-sha256 SIGNATURE_SET_DIGEST
```

Uppercase digest arguments denote required operator-retained values, not executable
examples or fabricated results. Assemble the reviewed envelopes into the bounded
signature-set format above. The tool does not gather signatures from other people
or send messages. Keep private reviewer material and keys out of public repos.

## Persistent authorization stage

The protocol is separate JSON with exactly `schema: e156-decision-protocol-v1`,
`stage: authenticated-decisions`, `project`, `dossier_sha256`, `trust_sha256`,
`roster_sha256`, and `signatures_sha256`. Retain its reviewed digest independently.
Initialization verifies complete signed decisions before creating a new state.
Each advance replays sources, verifies decisions/signatures/policies, and rechecks
the protocol and all implementing code. Transitions are:

`READY -> AUTHENTICATED -> COMPLETED`

```console
python scripts/synthesis_decision_runner.py init --state decision.sqlite --protocol decision-protocol.json --expected-sha256 PROTOCOL_DIGEST --dossier decisions.json --trust trust.json --roster roster.json --signatures signatures.json --bundle report=review-bundle
python scripts/synthesis_decision_runner.py advance --state decision.sqlite --protocol decision-protocol.json --expected-sha256 PROTOCOL_DIGEST --dossier decisions.json --trust trust.json --roster roster.json --signatures signatures.json --bundle report=review-bundle
```

Two advances after initialization store authentication and completion. Completed
retries revalidate and return the same receipt without another event. Changed or
missing anchored dependencies or code terminally invalidate an established run;
restoring bytes does not revive it. Changing/revoking keys requires a new approved
policy/roster, fresh signatures and a new protocol/state. Supplying the wrong
external protocol anchor refuses without altering the existing run.

Missing/corrupt state is never recreated. The existing `BEGIN IMMEDIATE`,
`synchronous=FULL`, rollback journal and strict history/schema checks are reused.
A busy writer or storage failure cannot emit cached completion. Infrastructure
errors roll back. Do not remove SQLite sidecars after interruption; let SQLite
recover them. State and sidecars must remain outside bundles and distinct from
every policy, dossier, protocol and signature input. Keep the database private
and untracked. State checksums detect corruption, not an authenticated audit log.

All COMPLETED receipts still carry HOLD. This is a frozen, already reviewed
dossier authorization stage, not a mutable reviewer queue or complete review
workflow. No search, screening, statistical synthesis or downstream actions are
added. New-process and worker-termination tests exercise process recovery, not
physical power loss, broken storage flushes, network filesystems or a hostile
concurrent writer changing and restoring dependencies between observations.

CLI responses use ASCII-escaped JSON for Windows console compatibility. Exit 0
means the requested record/stage operation ran; exit 2 is refusal/invalidation,
and exit 3 is a storage error. Refusals/errors expose no current receipt. Bounds
are 32 KiB trust/roster files, 512 KiB signature set, at most 192 envelopes,
the existing 256 KiB dossier limit, 8 KiB protocol, 1 MiB state/sidecar and four
events of at most 64 KiB. No distributed workers, migrations, policy discovery,
key expiry or transparency log are implemented.

## Static versus dynamic disclosure

| Material | Origin | Boundary |
|---|---|---|
| Schemas, role rules and limits | Authored static contract | Engineering choices |
| Reviewer/person assignments | Operator-attested policy | Human identity and independence not established |
| Test keys and ballots | Disposable synthetic controls | No real reviewer or production enrollment |
| Test quotations and source IDs | Existing archived OA bundles | Text identity, not semantic judgment |
| Signatures, hashes and source replay | Executed dynamic | Integrity and authorization under selected policy |
| Recovery results | Actual subprocess/SQLite controls | No physical power-loss guarantee |

Integration contracts precede implementation. Dedicated Windows/Linux CI requires
the locked signing dependencies and Overmind source, then runs signature, roster,
disagreement, invalidation, concurrent writer, forged history and interrupted-worker
controls. Engineering tests do not measure held-out research accuracy.
