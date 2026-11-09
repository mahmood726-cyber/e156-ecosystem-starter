# meta-harness: getting started

The **meta-harness** is Mahmood's reproducible meta-analysis pipeline. It searches, screens, extracts and pools
trial results for 32 reviews, and serves each review as a web page with every step on a tab:
protocol, search, screening, included studies, extraction (each number shown with the passage it came from),
risk of bias, analysis, results, comparison with a published meta-analysis, changes and signatures, and how to
reproduce it. Each review carries a certificate whose digests let anyone re-run it and get the same bytes.

It lives in its own repository. **This starter does not copy its code.** It points you at a published release,
and `scripts/install-meta-harness.{sh,ps1}` can fetch and verify that release for you.

## Download

| what | where |
|---|---|
| Release **v1.0.0** (`meta-harness-v1.0.0.zip` + `SHA256SUMS`; the repository at commit `cdd81860a29f`; **DOI pending, v1.0.1**) | https://github.com/mahmood726-cyber/meta-harness/releases/tag/v1.0.0 |
| Fetch and verify it from this starter | `bash scripts/install-meta-harness.sh` (Windows: `.\scripts\install-meta-harness.ps1`) |
| Repository (clone, full history) | https://github.com/mahmood726-cyber/meta-harness |

The installer first verifies that the downloaded **v1.0.0 `SHA256SUMS` itself** has the starter-reviewed SHA-256
`3bf1d1f9eaa6f423f3130ca5f6413b05dcf2994833a9fce038e1ee8e9ad00ddb` (90 bytes; source: public
release metadata). Only then does it fetch the 609,134,873-byte ZIP and check its SHA-256 against that manifest:
`694dc82f51fcde9040a8e1a5f0172978cb1a6f3eeade237fcd81df61185c2d0d`. This prevents a quiet
replacement of **both** assets at the release URL from passing with self-consistent checksums. It refuses
mismatches, unsafe archive paths, and non-empty destinations before publication. Remote refs other than v1.0.0
are **not admitted** until their manifest digest has been separately reviewed and pinned; `--ref` / `-Ref`
currently accepts such refs only with an explicitly local `file://` fixture base for isolated tests.

**This is a reviewed content pin, not signature verification.** The published v1.0.0 release does not provide a
separate signature asset, so neither provenance of the original ZIP nor scientific/clinical correctness is
independently authenticated by this installer's green result.

## Reproduce one review

There are two routes, and they need different commands: **a download has no git history.**

**From a git clone** (the full replay, including the git-recorded custody of each held document):

```
git clone https://github.com/mahmood726-cyber/meta-harness.git && cd meta-harness
git checkout v1.0.0
python -m pip install --require-hashes -r docs/offline/requirements.lock
python scripts/reproduce_review.py dpp4-mace-t2d
```

**From the release zip** (no git; networking is denied during the replay):

```
cd ~/code/meta-harness-v1.0.0
python -m pip install --require-hashes -r docs/offline/requirements.lock
python scripts/replay_offline.py dpp4-mace-t2d
```

`replay_offline.py` runs the same replay. Instead of asking git for each held document, it reads the document from
the unpacked files and checks its sha256 against the review's certificate. **`reproduce_review.py` does not work
from a zip**: it stops with "not a git repository". The offline contract is set out in `docs/offline/REPLAY.md` in
the harness (served at https://mahmood726-cyber.github.io/meta-harness/offline/REPLAY.md).

Both routes need CPython 3.13 and the hashed, pinned wheels in `requirements.lock`. Any review slug works in
place of `dpp4-mace-t2d`; the slugs are the folder names under `docs/reviews/`.

## Where things are

| | |
|---|---|
| Live reviews (32) | https://mahmood726-cyber.github.io/meta-harness/ |
| G1 scoreboard (trial-for-trial comparison with published meta-analyses) | https://mahmood726-cyber.github.io/meta-harness/g1/ |
| External audit pack (guide, per-review checklists) | https://mahmood726-cyber.github.io/meta-harness/audit/ |
| Offline replay kit | https://mahmood726-cyber.github.io/meta-harness/offline/REPLAY.md |

## Honest limits (read these before citing anything)

- **The external audit is in progress.** Reviews are being audited one by one; findings and fixes are published as
  they land. A review that has not been audited yet has not been checked by anyone outside the project.
- **G1: 13 of 22 active topics are MATCHED.** The other 10 of the 32 topics were abandoned by decision; they stay
  on the site and are never counted as matched. The scoreboard states the current count and every divergence.
- **Matched is not the same as validated.** G1 MATCHED means every eligible trial in a published meta-analysis was
  found and verified, and the result agrees. It is a comparison with one published review, not independent
  corroboration that either is right.
- **Replay proves the same inputs give the same outputs.** It does not prove the inputs are right, that the search
  found every eligible trial, or that a fresh search today would return the same records.
- **Risk-of-bias judgements are rule-based.** The recorded dual-model sign-off (decision D11) has not been applied
  yet, and each review page says so. Each page's Overview lists its own stated limitations.
- A release is pinned to one commit. The live site follows the repository's `main` branch and can move ahead of
  the latest release.
