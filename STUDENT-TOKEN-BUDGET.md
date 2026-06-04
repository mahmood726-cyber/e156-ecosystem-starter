# Student token budget — recreate the work without burning your limit

Agent CLIs (Claude / Gemini / Codex) are metered. If you're on a free or capped
plan, the trick is to **spend tokens only where an LLM actually helps**, and run
everything else with the deterministic, offline tools this starter installs.

**Rule of thumb: the math, the charts, and the dashboards cost ZERO tokens.**
They are plain Python / static HTML. You only need an agent to *write prose* (a
capsule draft, a README) or to *reason about a tricky bug* — and even then, ask it
to *edit* a near-final draft rather than generate from scratch.

## What costs tokens vs what is free

| Step | Tool | Token cost |
|---|---|---|
| Build a RapidMeta dashboard from a config | `rapidmeta-kit/clone.py` | **Free** (stdlib Python) |
| Render an E156 capsule chart (forest plot) | `e156-capsule/chartkit.py` | **Free** (stdlib SVG) |
| Run a Pairwise70 analysis | `pairwise70-workbench/index.html` | **Free** (browser, offline) |
| Build an AACT warehouse + capsule | `aact-cockpit/scripts/*.py` | **Free** to run (needs duckdb+numpy+data, no LLM) |
| Validate a capsule (7 sentences, ≤156 words) | a 5-line counter — no LLM | **Free** |
| Sentinel pre-push checks / Overmind verify | `sentinel`, `overmind` | **Free** (deterministic rules) |
| **Draft** the 7 capsule sentences | agent | **Costs tokens** — minimize (see below) |
| Reason about a non-obvious bug | agent | **Costs tokens** — use sparingly |

## The four research layers — the low-token path for each

- **RapidMeta** (`install-rapidmeta`): entirely token-free. `bash run_example.sh`
  builds a real dashboard from the bundled config. Write your own config by hand
  (copy a file in `configs/`) — no agent needed.
- **Pairwise70** (`install-pairwise70`): token-free. Open `index.html`, pick a
  tab, paste data, read the result. The statistics run in your browser.
- **E156 capsules** (`install-e156-capsules`): the chart is free
  (`python chartkit.py my.capsule.json --out my.svg`). Read the **pre-baked**
  `sample.capsule.md` and `sample.forest.svg` to see the finished shape **for
  zero tokens** before you write anything.
- **AACT** (`install-aact`): the analysis is free to run (no LLM) once you have
  `--with-data-deps` and a data snapshot. With **no setup at all**, read the
  committed `analyses/` and `templates/` examples — zero tokens, zero install.

## Cutting tokens when you DO need an agent

1. **Draft from the sample, not from blank.** Open `sample.capsule.md`, copy its
   shape, fill your numbers, and ask the agent only to *tighten* the result. A
   "tighten these 7 sentences to ≤156 words" turn is a fraction of "write a paper".
2. **Validate offline first.** Count sentences/words yourself (or with a 5-line
   script) before asking an agent — never spend a turn on something a `len()` check
   answers.
3. **Cap context.** Don't paste a whole repo. Paste the one file / one function.
   Grounding (and token cost) both degrade past ~10 sources in context.
4. **Pick the cheaper model for cheap work.** Use a smaller/faster model
   (e.g. Haiku-class) for mechanical edits, reformatting, and short drafts; reserve
   the largest model for genuinely hard reasoning.
5. **Let the deterministic gates catch mistakes.** Sentinel + Overmind find bugs,
   ungrounded claims, and bad paths for free — don't pay an agent to do a review a
   rule already does.
6. **Reuse, don't regenerate.** The starter ships ~40 worked capsule examples
   (`docs/capsules/`) and each tool ships its own example output. Read those
   instead of regenerating.

## One-line installs (all default to the low-token path)

```bash
# macOS / Linux
bash scripts/install-rapidmeta.sh          # offline, stdlib-only dashboards
bash scripts/install-pairwise70.sh         # offline browser gallery
bash scripts/install-e156-capsules.sh      # bundled capsule + chart-kit (no network)
bash scripts/install-aact.sh               # clone only; add --with-data-deps when ready
```

```powershell
# Windows PowerShell
.\scripts\install-rapidmeta.ps1
.\scripts\install-pairwise70.ps1
.\scripts\install-e156-capsules.ps1
.\scripts\install-aact.ps1                 # add -WithDataDeps when ready
```

Heavy dependencies are always opt-in (`--with-data-deps` / `-WithDataDeps`), so a
fresh install never downloads a scientific stack you didn't ask for.
