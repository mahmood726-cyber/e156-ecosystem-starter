# Validation record

Executed 17 November 2026 against upstream tree `806f8bb7329d33d1667f505274bc11a6a1863734` (main commit `bfa686359d9ec47520089d4864a90f20f0d0d7f5`) plus this candidate bundle.

| Check | Actual result |
|---|---|
| New Python regression tests | **20 passed**, 0 failed, 0 skipped (0.29 s). |
| Python deterministic replay and additional fixed simulation grid | Passed; 34 example values checked and 6 x 200,000 synthetic replicates. All six rejection rates are within three Monte Carlo standard errors of their derived limits. |
| Base-R original-source/example replay | Passed; first six published effect/covariance rows agree at printed precision; all seven sensitivity fits agree with an independent GLS calculation. |
| Separate computational review's R replay | Passed; 300,000 partial-overlap and 300,000 complete-data Wald replicates; centering-matrix identity, 30 source-reduction pairs, disjoint-patient counterexample, binary-data fingerprint and GLS checks. |
| Source bytes | All four original files match their pinned Git blob hashes. |
| Separate review | Additional AI computational review of the mathematics, README, Python and tests approved with limits. It is not human review, author agreement or clinical validation. The author of this bundle subsequently executed the portable R wrappers and assembled/checked the manifest and outputs. |
| Privacy pass | No private correspondence, recipient addresses, message IDs, personal filesystem paths or private audit identifiers in the curated public files. |
| Sentinel changed-file scan | Exit 0; no BLOCK findings. It also reported 77 repository warnings outside the new note/test paths. No bypass used. |
| Full repository pytest execution | **Failed:** 1,407 passed, 307 failed, 165 errors, 8 skipped; 999 subtests passed; 331.69 s. This is not an all-green repository result. |

The Windows host's globally auto-loaded `zarr` pytest plugin first failed before collection because Application Control blocked `numcodecs.zstd`. The new-test and full-suite runs above used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` to exclude unrelated host plugins; no repository tests or test configuration were changed. The full run still encountered sandbox temporary-file/copy restrictions and unavailable external tools. This execution does not isolate every failure's cause or establish that every failure predates this change.

The wider repository's Bash, Pester, lint, drift and link gates are not represented as passing by this record. Available host tools and their actual verifier results are recorded in the pull request. This bundle is published as a candidate on a review branch. Passing the narrow audit checks does not certify the repository, the method, or a corrected clinical analysis.

Reference computation versions: Python 3.13.13, NumPy 2.4.6 and base R 4.6.0. R emitted host locale startup warnings; all explicit numerical assertions completed successfully. Run the commands in the note to reproduce numerical outputs; fixed reference outputs are separate from newly generated files.
