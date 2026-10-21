# Honest ratchet: the kit's checks may only get quieter on the record (v1.0.0, 2026-10-21)

**The problem in one sentence.** The quietest way to turn red into green is to
stop checking: delete a test, drop a rules file, remove a pattern from the
test-config hook, or set a CI job to `if: false`. Nothing fails; something just
stops being checked.

**What `scripts/honest-ratchet.py` does.** It measures what protects this repo
and compares it with a committed baseline, `docs/ratchet-baseline.json`:

| Measured | Where |
|---|---|
| tests per suite, and every test's name | pytest functions in `tests/test_*.py` and `scripts/test_*.py`; Pester `It` blocks in every `*.tests.ps1`; bash `start "..."` cases in `tests/*.bash` |
| rules files | `rules/*` |
| protected-config patterns | the tuples in `scripts/protect-test-config.py` |
| guard/check scripts | `scripts/*` whose name says protect/guard/gate/check/audit/screen/reconcile/rerun/ratchet, or that offer `--check`/`--selftest` |
| CI jobs, and which are enabled | `.github/workflows/test.yml` |

```
python scripts/honest-ratchet.py --check     # exit 1 on any unacknowledged decrease or removal
python scripts/honest-ratchet.py --update    # rewrite the baseline; refuses unless --check passes
python scripts/honest-ratchet.py --show      # print today's measurement
python scripts/honest-ratchet.py --selftest  # prove it refuses a loss and passes an addition
```

Adding tests, rules, patterns, scripts or jobs always passes. Run `--update`
afterwards to raise the floor, and commit the new baseline.

**When a loss is right** (two duplicate tests merged, a rules file folded into
another), a human reviewer adds an entry to `docs/ratchet-acknowledgements.json`
naming it exactly, with a reason and a date:

```json
{"item": "pytest:tests/test_reuse.py", "base": 18, "new": 17,
 "reason": "two duplicate cases folded into one parametrized test", "date": "2026-10-21"}
{"item": "pytest-names:tests/test_reuse.py::test_old_name",
 "reason": "same as above", "date": "2026-10-21"}
```

`--check` prints the exact acknowledgement each loss needs. A count entry must
give both counts exactly; an entry without a reason or an ISO date is ignored.

**Newly skipping a test counts as removing it.** A pytest function decorated
`@pytest.mark.skip` / `xfail` or a Pester `It ... -Skip` leaves the name set.
Conditional skips (`skipif`, `-Skip:(<condition>)`) still count.

## Opt-in

- **This repo:** enforced by `tests/test_honest_ratchet.py`, which the existing
  `python-tests` CI job already runs. Nothing in `install.ps1` / `install.sh`
  runs it, so installing the starter changes nothing on your machine.
- **Your own project:** copy the script, run
  `python honest-ratchet.py --root . --update` once, commit
  `docs/ratchet-baseline.json`, then run `--check` from CI or a pre-push hook.

## Limits, named

- It counts tests; it does not judge them. A test whose body was emptied keeps
  its name. Pair with `scripts/blank-and-rerun.py`.
- `pytest.skip()` inside a test body, and skipped Pester `Describe`/`Context`
  blocks, are not seen.
- It reads CI job names and `if: false`, not what each job runs.

Ported from the meta-harness honest-state ratchet (`harness/honest_ratchet.py`),
which applies the same rule to warnings on rendered pages.
