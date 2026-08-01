#!/usr/bin/env python3
"""Example pooling probe for `meta-self-audit.py --metamorphic`.

Overmind's `MetamorphicWitness` does not check your pooled number against a
"right answer" -- there isn't one to check against. It checks that your pooling
code obeys relations any correct implementation must obey:

    scale invariance     multiply every effect by 2 -> pooled doubles
    zero-heterogeneity   all effects identical -> pooled equals that value
    sign reversal        negate every effect -> pooled negates
    tau2 >= 0
    I2 in [0, 100]

That is the oracle problem solved sideways, and it catches a whole family of
weighting and back-transformation bugs that eyeballing a forest plot does not.

Contract: read `{"effects": [...], "variances": [...]}` on stdin, write
`{"pooled": float, "tau2": float, "I2": float}` on stdout. Nothing else on
stdout -- the witness parses it as JSON.

Copy this next to your own analysis and replace the body of `pool()` with a call
into YOUR pooling code. The point is to test the code your dashboard actually
runs, not this reference implementation.

    python scripts/meta-self-audit.py MY_REVIEW.html \
        --metamorphic templates/meta-self-audit/pooling_probe.py

Standard library only. DerSimonian-Laird is used here because it is the shortest
correct thing to write; note that `rules/advanced-stats.md` tells you not to use
DL for k<10 in real work -- prefer REML or Paule-Mandel there.

KNOWN LIMITATION OF RELATION 1 (measured, not assumed)
------------------------------------------------------
Overmind's scale-invariance relation multiplies every effect by 2 and leaves the
variances alone. That is not a change of units -- if you rescale an outcome, the
standard errors rescale with it. Under the witness's transform a *correct*
random-effects estimator is NOT scale-invariant, because tau^2 absorbs the
inflated spread and the weights move. Measured on the witness's own inputs:

    effects x2, variances unchanged -> pooled ratio 1.862  (tau^2 0.0213 -> 0.1497)
    effects x2, variances x4        -> pooled ratio 2.000  (a real unit change)
    fixed-effect, effects x2        -> pooled ratio 2.000

So a random-effects probe fails relation 1 by construction. The other four
relations are valid for it. Run the probe in `fixed` mode to get a meaningful
signal from all five:

    POOLING_PROBE_MODE=fixed python scripts/meta-self-audit.py MY.html \
        --metamorphic templates/meta-self-audit/pooling_probe.py

Do not "fix" this by making your probe return a fixed-effect number while your
dashboard reports a random-effects one. That makes the gate green by pointing it
at code the dashboard does not run -- which is the failure mode this whole layer
exists to catch.
"""
from __future__ import annotations

import json
import os
import sys


def pool(effects: list[float], variances: list[float], mode: str = "random") -> dict:
    """Pool. `mode='random'` (default) is DerSimonian-Laird; `'fixed'` is inverse-variance.

    See the module docstring for why `mode` exists: relation 1 of Overmind's
    metamorphic witness is only valid for fixed-effect pooling.
    """
    k = len(effects)
    if k == 0 or k != len(variances) or any(v <= 0 for v in variances):
        raise ValueError("need matching effects/variances with all variances > 0")

    # Fixed-effect stage
    w = [1.0 / v for v in variances]
    sw = sum(w)
    fe = sum(wi * yi for wi, yi in zip(w, effects)) / sw

    # Q, and DL tau^2
    q = sum(wi * (yi - fe) ** 2 for wi, yi in zip(w, effects))
    df = k - 1
    c = sw - sum(wi * wi for wi in w) / sw
    tau2 = max(0.0, (q - df) / c) if df > 0 and c > 0 else 0.0

    # Random-effects stage
    wr = [1.0 / (v + tau2) for v in variances]
    swr = sum(wr)
    pooled = sum(wi * yi for wi, yi in zip(wr, effects)) / swr

    i2 = max(0.0, (q - df) / q * 100.0) if q > 0 and df > 0 else 0.0
    if mode == "fixed":
        return {"pooled": fe, "tau2": tau2, "I2": i2, "k": k, "Q": q, "model": "fixed"}
    return {"pooled": pooled, "tau2": tau2, "I2": i2, "k": k, "Q": q, "model": "random"}


def main() -> int:
    payload = json.load(sys.stdin)
    mode = os.environ.get("POOLING_PROBE_MODE", "random").strip().lower()
    if mode not in ("random", "fixed"):
        print(f"POOLING_PROBE_MODE must be 'random' or 'fixed', got {mode!r}", file=sys.stderr)
        return 2
    json.dump(pool(payload["effects"], payload["variances"], mode), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
