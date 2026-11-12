# Explicit trust for Synthesis replay signatures

The optional `scripts/synthesis_signing.py` adapter signs an existing verified
replay and verifies it under a separately supplied public-key policy. It reuses
Overmind's `Ed25519Signer`, inspected at the existing locked commit
`d3d2de5f84d852f27d64d1686f1e105e190ac375`. Verification uses the cryptography
library directly and needs no private key or installed Overmind package.

## Contract and trust boundary

The detached envelope follows a bounded, single-signature
[DSSE v1 profile](https://github.com/dsse-lf/dsse/blob/master/protocol.md).
Its payload type is `application/vnd.e156.synthesis-replay-signature.v1+json`.
Pre-authentication encoding binds that type to the exact canonical payload.
The payload binds the project, manifest hash, analytical payload hash, schema
and `scientific_validity: NOT_ESTABLISHED`. Key IDs are SHA-256 fingerprints of
the raw 32-byte Ed25519 public key. Keys never come from the envelope.
Public points are checked with libsodium through PyNaCl 1.6.2 or newer. That
release includes the corrected subgroup validation described in the
[PyNaCl changelog](https://pynacl.readthedocs.io/en/latest/changelog/).
This rejects weak, noncanonical and invalid public points before signature use.

The verifier requires all of the following:

1. An independently retained SHA-256 digest of the trust-policy file.
2. A project identifier explicitly selected by the caller.
3. An active public key in that policy with the correct fingerprint.
4. A valid Ed25519 signature over the typed payload.
5. Successful execution of the existing replay verifier, including source,
   implementation, manifest, inventory and result checks.

`TRUSTED_SIGNATURE_REPLAY_MATCHED` means those requirements passed. It does not
establish the key holder's real-world identity, publisher authenticity,
independent human review, scientific accuracy, cohort/outcome equivalence or
release eligibility. Existing HOLD decisions remain unchanged. No timestamp,
freshness, key expiry, transparency log or automatic revocation lookup is claimed.
A previously valid signed bundle can be replayed. Use an independently approved
current policy and, where needed, separately pin the expected manifest in the
review's record. A compromised local interpreter or trust-anchor distribution
channel is outside this contract.

Revocation requires changing a key's status to `revoked` and distributing the
new policy digest through the trusted channel. Old policy digests still select
the old policy; this offline tool cannot determine which policy is latest.
Rotation can list multiple keys, but each envelope contains exactly one signature.
Duplicate keys, ambiguous JSON, noncanonical base64, unknown fields, missing
anchors, wrong projects and unsupported algorithms refuse.

## Policy and use

A policy has exactly `schema: e156-synthesis-trust-v1`, `project`, and `keys`.
Each key record has exactly `keyid`, `public_key` (base64 raw public bytes) and
`status` (`active` or `revoked`). The project is 1–128 lowercase ASCII characters
from letters, digits, period, underscore, slash and hyphen; it starts with a
letter or digit. Keys must be approved independently. The tool does not generate
or discover production keys, enroll signers, or trust environment-selected keys.

Install `scripts/requirements-signing.lock` inside an isolated Python 3.13
environment. Its downloaded wheel hashes cover Windows x64 and Linux x64.
Signing also requires the installed, trusted Overmind component. Supply an
explicit raw 32-byte Ed25519 private-key file protected by local access controls.
The [cryptography Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)
provides the underlying cryptographic operations. Private material is never
included in the envelope or returned receipt. This adapter does not audit OS ACLs.

```console
python scripts/synthesis_signing.py sign review-bundle --expected-sha256 MANIFEST_DIGEST --private-key private-key --policy approved-policy.json --trust-sha256 POLICY_DIGEST --project review-id --output signature.json
python scripts/synthesis_signing.py verify review-bundle --envelope signature.json --policy approved-policy.json --trust-sha256 POLICY_DIGEST --project review-id
```

The uppercase digest tokens above are command arguments to replace with actual
independently retained hashes. Policy, signature and private-key files must be
distinct and outside the bundle. The bundle's closed inventory is unchanged;
existing bundles and historical measurements need no resealing. Existing output
files are never overwritten. Exit 0 means verified; refusal exits 2. A filesystem
write failure can leave an incomplete signature file; it cannot verify.

## Evidence and limitations

| Item | Static or dynamic | Scope |
|---|---|---|
| DSSE/profile and policy fields | Authored static contract | One signature; no general threshold-policy or DSSE interoperability certification |
| Keys in tests | Dynamically generated disposable keys | Test principals only; no human identity or production enrollment |
| OA replay inputs | Existing attributed archived bytes | No new clinical findings or changed source identifiers |
| Signature/replay tests | Executed development controls | Engineering behavior, not held-out scientific accuracy |
| Dependency hashes | Computed from downloaded wheels | Reproducible dependency bytes on the declared platforms |

The dedicated CI job uses the actual locked Overmind source on Windows and Linux.
The ordinary lean test job may skip optional signing tests when cryptography or
Overmind is absent; the signing job explicitly requires both imports. Tests
include an independent construction of DSSE wire bytes, tampering, key/project
confusion, revoked keys and replay re-execution. No production signing keys are
used or committed.
