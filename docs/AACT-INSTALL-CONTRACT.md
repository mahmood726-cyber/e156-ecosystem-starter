# AACT-kit installation: M2 second increment

AACT-kit joins RapidMeta behind the shared source checkout boundary. Both Bash
and PowerShell verify before persisting a discovery path. The old installers
could ignore a checkout failure or downgrade a requested dependency failure to
a warning; the new path refuses those outcomes.

## Verified ingredients and scope

The existing installer selected GitHub tag `v1.0.0`. Its unsigned annotated tag
[`129842e50df032e0a5a5027b58c7674f1f32fc56`](https://api.github.com/repos/mahmood726-cyber/aact-kit/git/tags/129842e50df032e0a5a5027b58c7674f1f32fc56)
resolved on 2026-11-11 to
[`b1995128747848d1567386266eca95e9230e19b9`](https://github.com/mahmood726-cyber/aact-kit/commit/b1995128747848d1567386266eca95e9230e19b9).
That exact commit was fetched into a separate checkout. Its `pyproject.toml`
requires Python 3.10+ and pandas 2+; the starter adapter requires Python 3.11+.
The five package modules, schema validation API, backend dispatch and upstream
tests were inspected before writing the canary. Existing personal checkouts were
left untouched. No upstream analytical code or real trial records were changed.

Reused: RapidMeta's exact-commit/origin, clean-tree, runtime-floor and fresh-target
checks, extracted into `component_source.py`. New: the AACT source adapter,
backend canary, Windows/Linux CI and explicit source-only/runtime receipt states.
This does not extend the main `--full` installer chain yet.

## Installation contract

- Source-only mode requires an exact clean checkout, supported package metadata
  and parseable Python source. It reports `source_verified`, with
  `runtime_verified: false` and no runtime result. This mode does not import or
  install the package. Persisting `AACT_KIT_PATH` records a verified source path,
  not a claim that pandas or a local AACT snapshot is available.
- `--verify-runtime` / `-VerifyRuntime` executes the canary using the selected
  Python interpreter, without installing dependencies. The subprocess ignores
  ambient Python paths and checks that the imported package is the selected
  source. Missing dependencies, failed execution, malformed or incomplete reports
  and differing repeat results refuse the request.
- `--with-deps` / `-WithDeps` requires an active virtual environment before any
  checkout change. It performs the opt-in editable package installation and then
  requires runtime verification. Pip failure is fatal. Pip may have partially
  modified that explicitly selected environment before failing; this is not an
  atomic dependency transaction. Its resolver/build dependencies are not locked
  by this change.
- `--skip-clone` / `-SkipClone` still verifies source identity. A different HEAD
  requires a fresh target. Full lowercase commit overrides are allowed and marked
  as overrides in the receipt. Pin refresh leaves the lock unchanged.
- `--session-only` / `-SessionOnly` avoids persistent shell/registry writes.
  Conflicting existing settings refuse persistence. No reset, stash or clean is
  used to discard work.

## Runtime checks and their limits

The canary creates disposable CSV, pipe-delimited TSV, ZIP and SQLite versions of
two small tables. Each backend must load the same rows, project columns, filter
by synthetic drug name and lowercase intervention type before applying a row
limit, return an empty nonmatch, and refuse a required missing column. It runs
twice; receipts record matching payload hashes, tested checks, module hashes,
source/verifier identities and Python/pandas/NumPy versions.

These are synthetic engineering controls with explicit `fixture-*` identifiers.
They establish neither source-record correctness nor clinical/statistical
accuracy. PostgreSQL, schema variants beyond the fixture, invalid-date behavior,
large snapshots, all aggregation methods and macOS execution remain untested by
this adapter. Unknown or missing checks cannot be counted as passed.

The CI runtime dependencies are separately hash-pinned in
`requirements-aact-canary.lock`. Hashes were computed from downloaded PyPI wheels
for CPython 3.13 on x86_64 Windows and Linux. This lock covers the runtime canary,
not every supported upstream platform or the optional editable build process.

## Static versus dynamic disclosure

| Item | Kind | Meaning |
|---|---|---|
| Source SHA and package metadata contract | Static, source-inspected | Selects the implementation; not a source signature |
| Two tables, synthetic identifiers, expected checks | Static development fixtures | Engineering expectations, never research evidence |
| Wheel hashes | Measured from downloaded artifacts | Selected CI runtime distributions only |
| Backend rows and payload hashes | Dynamic execution | Tested data-path behavior, not all AACT schemas |
| Source-only/runtime state | Dynamic result | Explicitly separates source availability from executable validation |
| PostgreSQL/scientific validation | Not measured | Cannot support completeness or scientific-performance claims |

Execution evidence is saved in
[`benchmarks/components/aact-windows.json`](../benchmarks/components/aact-windows.json)
and current-head CI results on the draft pull request.

Local validation used a separate virtual environment and the inspected GitHub
commit. The actual opt-in editable installation succeeded, followed by two
matching runs across the four backends. RapidMeta was rerun after extracting the
shared source boundary; its generated output and asset hashes were unchanged.
The isolated component/pin suite passed 74 tests; research-layer Bash helpers
also passed. Governance checks and current-head remote CI are reported separately
on the pull request. Sentinel reported no blocking findings; warnings remain.
