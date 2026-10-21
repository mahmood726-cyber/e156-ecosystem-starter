# verify-local: run what CI runs, before you push (opt-in, v1.0.0, 2026-10-21)

**Who this is for.** Anyone changing this starter who wants to know, before
pushing, whether CI will go red.

**The problem in one sentence.** If the checks you run locally are not the
checks CI runs, a green local run means nothing, and the two drift apart
quietly.

**What it does.** `scripts/verify-local.py` runs every check in
`.github/workflows/test.yml` that can run on your machine, one named *limb* per
CI step, and prints one verdict per limb:

| Limb | Mirrors CI step |
|---|---|
| `pytest` | python-tests / Run pytest |
| `bash-install-sh` | bash-tests / Run bash test suite |
| `bash-handoff-locale` | bash-tests / Run handoff-locale bash tests |
| `hash-check` | hash-check / Verify docs/HASH.txt + docs/HASH-linux.txt |
| `i18n-parity` | i18n-parity / Verify `<details>` count parity |
| `pester` | pester / Run Pester suites (needs Pester 5+) |
| `shellcheck` | lint / ShellCheck |
| `psscriptanalyzer` | lint / PSScriptAnalyzer |
| `link-check` | link-check / Lychee link checker (needs network) |

```bash
python scripts/verify-local.py           # run all limbs
python scripts/verify-local.py --list    # show limbs and the CI steps they mirror
```

**Verdicts and exit codes.**

- `PASS`: the limb ran and passed. Exit 0 only when every limb passed, apart
  from any you excused by name (below).
- `REFUSED`: the limb ran and failed. Exit 1.
- `COULD-NOT-EXECUTE`: the limb could not run, for example `shellcheck` is not
  installed. Exit 2. **A missing tool is never a silent skip.**
- `NOT RUN`: the tool is missing and you said you accept that:
  `--allow-missing shellcheck`. The ledger still prints it, so the gap stays
  visible, and CI still runs it. The excuse only covers a *missing* tool: if the
  tool is present the limb runs, and a failure is `REFUSED` whatever you pass.

verify-local never installs anything. CI installs ShellCheck and
PSScriptAnalyzer itself; locally, install them or excuse them.

## Opt in to the pre-commit hook

Nothing runs verify-local for you. To run it before every commit in your clone:

```bash
git config core.hooksPath .githooks
```

`.githooks/pre-commit` calls `scripts/verify-local.py` and nothing else. To
excuse tools you do not have on this machine (named, per limb):

```bash
git config e156.verifyAllowMissing "shellcheck link-check"
```

Opt out with `git config --unset core.hooksPath`.

**Your existing hooks keep working.** Setting `core.hooksPath` makes git stop
reading `.git/hooks/`. So `.githooks/pre-commit` first runs any existing
`.git/hooks/pre-commit`, and `.githooks/pre-push` runs any existing
`.git/hooks/pre-push` (where the Sentinel pre-push hook lives), unchanged.

On Linux/macOS, make the hooks executable once if your checkout did not:
`chmod +x .githooks/pre-commit .githooks/pre-push`.

## Local and CI cannot drift silently

`tests/test_verify_local.py` (part of the CI pytest job) reads
`.github/workflows/test.yml` and fails if:

- a CI job or step has no limb, and is not listed in `CI_ONLY_STEPS` /
  `CI_ONLY_JOBS` in `scripts/verify-local.py` with a reason (checkout,
  set-up-python and version prints are listed there; the
  `sentinel-rule-list-drift` job is listed only while CI has it at `if: false`);
- a limb points at a CI step that no longer exists;
- the Pester file list, ShellCheck files and flags, PSScriptAnalyzer folders and
  excluded rules, or lychee arguments differ from CI's.

So adding a step to CI without adding a limb turns CI red.

## What it does not check

- It checks your **working tree**, as CI checks the pushed tree. With partly
  staged changes the two can differ; CI is the authority.
- Same tool, different machine: CI runs Pester on Windows (pwsh) and the bash
  suites on Ubuntu. A local pass on another OS is strong evidence, not proof.
- It never runs `sentinel-rule-list-drift` (disabled in CI). Run
  `bash scripts/regen-sentinel-rule-list.sh --check` yourself with
  `SENTINEL_REPO` set.
- The hook is a convenience, not enforcement: a fresh clone has no hook, and
  `core.hooksPath` is local config. CI is the gate.

Ported from the meta-harness `scripts/verify_all.py` ("one standard", hook and
CI run the same script).
