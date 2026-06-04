# E156 capsule + offline chart-kit (starter template)

A self-contained, **offline, stdlib-only** starting point for authoring an E156
micro-paper ("capsule") and rendering a chart for it without an internet
connection, a build step, or an LLM in the loop. Dropped into your workspace by
`scripts/install-e156-capsules.sh` (or `.ps1`).

This is the *authoring* template. The ecosystem-starter already ships ~40 worked
capsule examples under [`docs/capsules/`](../../docs/capsules/) — read those for
the finished look; use this template to write your own.

## What's here

| File | What it is |
|---|---|
| `capsule.template.md` | The E156 7-sentence contract (S1–S7) with per-sentence word budgets, ready to fill in. |
| `capsule.schema.json` | The minimal capsule object: the one named estimand + the seven sentences + metadata kept OUT of the body. |
| `sample.capsule.json` | A **pre-baked** filled example (a real-shaped capsule). Read it to see the result with **zero tokens** — no agent run needed. |
| `sample.capsule.md` | The same sample rendered as the 7-sentence paragraph. |
| `chartkit.py` | A ~120-line **stdlib-only** SVG primitive (no numpy/matplotlib): forest plot + sparkline. Deterministic, offline. |
| `sample.forest.svg` | Pre-baked output of `chartkit.py` on `sample.capsule.json` — open it in a browser to see the chart with zero tokens. |

## The E156 7-sentence contract

A capsule is **exactly 7 sentences, ≤156 words, one paragraph**, naming **one**
primary estimand, with **no citations/links/metadata in the body**:

| # | Role | ~words |
|---|---|---|
| S1 | Question | 22 |
| S2 | Dataset | 20 |
| S3 | Method | 20 |
| S4 | Result | 30 |
| S5 | Robustness | 22 |
| S6 | Interpretation | 22 |
| S7 | Boundary | 20 |

## Quick start (offline, no tokens)

```bash
# 1. See the finished example WITHOUT running anything that costs tokens:
cat sample.capsule.md
# 2. Render a chart from the sample, fully offline (stdlib only):
python chartkit.py sample.capsule.json --out my.forest.svg
# 3. Author your own: copy the template and fill S1–S7.
cp capsule.template.md my.capsule.md
```

## Low-token note

Authoring a capsule is the one step where an agent helps (drafting S1–S7). To keep
token use low: draft from the `sample.capsule.md` shape, validate sentence count /
word budget with the deterministic checker idea below (no LLM needed), and only ask
an agent to *tighten* a near-final draft rather than write from scratch. The chart
step (`chartkit.py`) is always token-free.
