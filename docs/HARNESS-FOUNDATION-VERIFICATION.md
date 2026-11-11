# Research harness foundation: local verification

Date: 2026-11-11. Branch: `research/harness-foundation-20261111`.
Remote main inspected at `677035bb3a4cabf7dc7480340be5323a72617e96`.
This is a development checkpoint, not SHIP or an Overmind release verdict.

## Changes and measurements

Memory discovery now requires an exact current-project match unless the caller
supplies an explicit store. Corpus reads refuse missing directories, unreadable
entries, invalid UTF-8, unclosed frontmatter and links outside the store. Legacy
Markdown and UTF-8 BOM input remain accepted. Health checks validate the index
and corpus. Query scoring uses sorted terms and a path tie-break; one CLI query
reads each entry once. Returned hashes describe the bytes read, and every hit is
marked `unverified_memory`. These checks do not authenticate sources, detect false
memories or make concurrent filesystem changes transactional.

The original recall test suite is collected through `tests/test_recall_legacy.py` while
retaining its canonical test identities in `scripts/test_recall.py`. The former
sole-candidate test now supplies an exact project match; separate negative tests
refuse one or several unrelated stores. This changes the unsafe contract rather
than deleting its test. New tests also check cross-process hash-seed determinism,
partial-read refusal, byte identity and index/link handling.

| Execution | Outcome | Boundary |
|---|---|---|
| Original `scripts/test_recall.py` | 17 passed | Existing tests accepted unrelated-store fallback |
| New memory controls before implementation | 24 failed, 1 passed | Adverse cases exercise the defects |
| `python -m pytest tests/test_memory_contract.py tests/test_recall_legacy.py -q` | 42 passed | Includes legacy suite and actual benchmark execution |
| `python scripts/benchmark-memory.py --output benchmarks/memory/after.json` | 11/11 controls satisfied; baseline 5/11 | Same evaluator hash, synthetic development cases, no held-out scientific accuracy |
| Installed Overmind `run_gold_benchmark()` | 43/43 stored fixtures passed, including 41 pooled fixtures | Installed `a8131b0`; not the starter-pinned revision; no independent clinical/source adjudication |
| `python -m pytest tests/test_bootstrap_effective_ref.py -q` with Git Bash available | 10 passed after isolation repair | Fake download stops execution; includes refusal when fake curl is absent |
| Targeted suite plus gate registry, ratchet, local verifier and protected-config tests | 186 passed | The seven-file command below; not the full suite |
| Installed Sentinel scan of branch changes vs baseline | Exit 0, zero BLOCK, 69 WARN at review | Installed `4e923b0`; some plugins inspect repository-wide documentation even in diff mode |

Expanded command (with Bash available on PATH):

```console
python -m pytest tests/test_memory_contract.py tests/test_recall_legacy.py tests/test_bootstrap_effective_ref.py tests/test_gate_gaps.py tests/test_honest_ratchet.py tests/test_verify_local.py tests/test_protect_test_config.py -q
python scripts/honest-ratchet.py --check
python scripts/render-gate-gaps.py --check
```

Both standalone governance checks passed. Sentinel initially blocked the new
collection adapter's duplicate basename and pre-existing machine-specific paths
in touched files. The adapter was renamed and the examples made portable; no
bypass was used. Warning counts are scan observations, not claims that every
warning has been resolved. The code/documentation change does not alter a browser
interface, numerical estimator or clinical dataset.

## Full-suite blocker and recovery

The initial Windows run stopped with 10 passing and 5 failing tests because Bash
was unavailable on PATH. Adding Git Bash and running `pytest tests/ -q --maxfail=8`
stopped at 10 passing and 8 failing bootstrap cases. Their Windows PATH injection
did not select fake curl; the actual downloader and installer ran against the
real user home. This was a test-safety failure, not a memory-code failure.

The installer had preserved first-run backups. Twenty-four affected rules/context
files were restored from those backups and byte-checked. Overwritten versions and
a restoration hash log were retained outside the repository. Generated installer
logs and the handoff-prompt file were retained; there was no pre-run snapshot of
the latter. No memory content was used as benchmark input or committed.

The bootstrap tests now establish PATH inside Bash, verify the selected curl is
the fixture before running the bootstrap, clear shell startup hooks, and use a
disposable home and working directory. Stub scripts use LF bytes. A missing stub
refuses before any bootstrap execution. Other installation tests also use
PATH-based stubs and need their own isolation review before a further whole-suite
Windows run. A full-suite PASS is not claimed. Linux CI and the other verify-local
limbs remain release requirements.

## Second-pass review and next gates

The memory benchmark evaluator and its original baseline are unchanged. Compare
case identities and evaluator hashes before comparing outcomes. Both reports
declare `held_out: false` and `scientific_accuracy_measured: false`. Scores are
BM25 relevance, and SHA-256 is byte identity; neither is an evidence confidence
measure. No trial identifier, study date, effect estimate or research dataset was
changed by this milestone.

Sentinel and Overmind installed revisions differ from the starter defaults; do
not reuse a pass across revisions. RapidMeta still swallows failed Bash checkout
and treats parse failure as a warning after persisting its path; repair these in
M2 before claiming reproducible installation. Overmind's stored-reference scorer
gates only declared tolerances; require a nonempty, validated metric contract in
the future integration rather than assuming every reported metric was checked.

## Static versus dynamic disclosure

| Item | Kind | Limit |
|---|---|---|
| Memory cases and expected behavior | Authored static development contracts | Not independent research labels |
| Runtime case results and byte hashes | Dynamic execution | Specific local implementation and environment |
| Component gaps | Source inspection | No full-chain installation or competitor execution |
| Proposed release gates | Authored plan | Outstanding until actually executed |
