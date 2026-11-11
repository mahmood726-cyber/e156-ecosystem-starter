# Persistent Synthesis audit stage

This bounded M4 increment persists one existing source-replay audit. It does not
implement search, screening, extraction, human adjudication or publication.
The transition contract is `READY -> AUDITED -> COMPLETED`; dependency failures
make a run terminally `INVALIDATED`. Completion remains scientific `HOLD`.

## Verified ingredients and reuse

The existing starter `scripts/synthesis_replay.py` and its ten fingerprinted
dependencies provide the source, licence, identifier, code and payload checks.
The two archived OA development bundles remain unchanged. The recovery experiment
in [the November comparison](HARNESS-COMPARISON-2026-11.md) supplies the integration
failure cases. The private correspondence module `synthesis_case_state.py` has a
different contract and is not changed or imported as workflow storage.

Portfolio recon used `find-related-repos.py "review workflow persistence"` with
the local manifest generated 2026-06-04T18:49:27.390382+00:00. The top five README
and code hits were inspected: APSMethodologistReview, asreview_5star,
EESMethodologistReview, PEMMethodologistReview and UmbrellaReview. These were
token-only matches, not a reusable persistence implementation for this stage.
The manifest is historical discovery evidence, not evidence of current portfolio
status. Net-new code is the transactional state wrapper around the existing replay.

SQLite from the Python standard library is sufficient for this small local state
machine. LangGraph remains an experimental comparator; no new runtime package is
required. The design uses [SQLite rollback transactions](https://www.sqlite.org/atomiccommit.html),
`BEGIN IMMEDIATE`, `synchronous=FULL`, and
[Python's existing-database URI mode](https://docs.python.org/3.13/library/sqlite3.html#how-to-work-with-sqlite-uris).
It requires a local filesystem with working locks and flushes. It does not
establish network-filesystem or physical power-loss durability.

## Contract fixed before implementation

- `init` requires a new state file, an explicit protocol file and its independently
  retained SHA-256. The protocol declares one project, one supported stage and an
  externally reviewed replay-manifest digest. It contains no commands or paths.
- `advance` requires the same external protocol anchor and explicit input paths.
  It opens an existing database; missing or corrupt state is never recreated.
- The first advance replays the complete audit and stores `AUDITED`. The second
  replays again before atomically storing one deterministic completion receipt.
  Every subsequent advance replays again and returns that same receipt without
  adding another completion event.
- Changed protocol bytes, runner/replay source hashes, or evidence/results
  invalidate the run. Invalidated runs cannot resume, even if bytes are restored.
  A dependency change requires a new state file and independent review of the
  changed code/inputs. Update the protocol and its retained digest when the
  project, stage or manifest changes. A runner-only change binds a new code
  profile without forcing a different protocol digest; review is an operator
  responsibility, not authenticated by this tool.
- A caller supplying a different trust anchor is refused without modifying the
  existing run. A missing file, malformed state, wrong schema or invalid event
  history cannot emit a completion receipt. Infrastructure errors remain errors.
- SQLite serializes writers. A busy database refuses the operation without a
  stale success. An abruptly terminated writer must leave the previous committed
  event available to a new process. A termination after commit but before the
  response must not cause another completion event on retry.
- State and SQLite sidecars stay outside the bundle and separate from the
  protocol. Linked paths, unknown database tables/views/triggers, duplicate JSON
  fields, nonfinite values and oversized state are refused.
- State checksums detect accidental corruption; they are not authenticated history
  or reviewer identity. Every completion is derived again from the anchored inputs.
  The local filesystem and running interpreter must remain under operator control.
- This stage has no external actions. A stable receipt ID permits caller
  deduplication, but stdout delivery is not exactly-once delivery and does not
  authorize a downstream email, deployment, signature or publication.

## Acceptance checks

The [example protocol](../examples/synthesis-review-stepwise.json) binds the
existing StepWise development bundle. Its reviewed SHA-256 is
`3a6f7f31efcd41d10a027bd5e3d2f4d3e9d7a9c1f8296a54b2d4954a679e465b`.
Retain this value independently; hashing whatever file was supplied at resume
and accepting that new hash would defeat the trust boundary.

From the repository root, choose a new state filename outside the bundle:

```console
python scripts/synthesis_review_runner.py init --state review.sqlite --bundle examples/synthesis-replay-stepwise --protocol examples/synthesis-review-stepwise.json --expected-sha256 3a6f7f31efcd41d10a027bd5e3d2f4d3e9d7a9c1f8296a54b2d4954a679e465b
python scripts/synthesis_review_runner.py advance --state review.sqlite --bundle examples/synthesis-replay-stepwise --protocol examples/synthesis-review-stepwise.json --expected-sha256 3a6f7f31efcd41d10a027bd5e3d2f4d3e9d7a9c1f8296a54b2d4954a679e465b
python scripts/synthesis_review_runner.py advance --state review.sqlite --bundle examples/synthesis-replay-stepwise --protocol examples/synthesis-review-stepwise.json --expected-sha256 3a6f7f31efcd41d10a027bd5e3d2f4d3e9d7a9c1f8296a54b2d4954a679e465b
```

These operations produce READY, AUDITED and COMPLETED respectively. Repeating
the final command revalidates and returns the same completion and history head.
There is no cached-status command. Exit 0 means the declared stage completed,
exit 2 means refusal/invalidation, and exit 3 means a storage/infrastructure error.
Each response has `release_eligible: false`. Keep state databases private and
untracked; a database is mutable local state rather than a release artifact.

Do not delete or rename SQLite journal files after interruption. SQLite must
recover a hot rollback journal. An incomplete initialization or invalidated run
requires a new state filename after inspection; an existing history is never
overwritten. Protocols are limited to 8 KiB, the state and each sidecar to 1 MiB,
event bodies to 64 KiB, and histories to four events. There is no migration or
distributed-worker support. Code profiles bind local source files; they do not
pin the Python/SQLite binary or authenticate the operator. Before/after inventory
hashes detect changes during the audit; this is not an atomic snapshot against a
hostile concurrent filesystem writer.

Integration checks use the existing OA bundles in disposable directories. They
cover new-process advancement, changed sources/results/protocol/code, missing and
malformed state, concurrent writers, invalid history, abrupt termination before
commit, and termination after commit before response. Faults and refusals are
retained as such. This is engineering validation on development fixtures, not
held-out scientific accuracy or an improvement in clinical results.

## Static versus dynamic disclosure

| Material | Origin | Boundary |
|---|---|---|
| Stage names, limits, schema, transition rules | Authored static contract | No empirical research result |
| Protocol project label | Operator-supplied metadata | Not authenticated identity |
| Protocol and source anchors | Computed hashes of reviewed files | Trust comes from a separately retained digest |
| Audit payload and receipt | Actual existing replay execution | Scientific validity remains unestablished |
| SQLite history checksums | Computed local state | Corruption checks, not signed history |
| Recovery outcomes | Executed subprocess checks | No hardware power-loss claim |
