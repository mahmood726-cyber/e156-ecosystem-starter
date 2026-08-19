#!/usr/bin/env python3
"""
pooled-point-achievable.py -- can the pooled point a paper serves be produced from the
trials it says it pooled?

Why this exists
---------------
A meta-analysis prints a headline number. You have its forest plot -- the per-trial
effects and their intervals -- and you want to know whether the headline follows from
them. The usual way to ask is to re-run the pooling: try fixed-effect, try
DerSimonian-Laird, try REML, try every subset, and see whether anything lands on the
served number.

That is what we did first, and it does not close the question. In one review 33
candidate pools were computed -- every subset of two, three and four of the page's
published hazard ratios under three estimators -- and none reproduced the headline.
Honest, and not a proof:

    AN ENUMERATION THAT FINDS NOTHING PROVES NOTHING ABOUT THE ESTIMATOR IT DID NOT TRY.

"None of the 33" leaves Mantel-Haenszel, Peto, Knapp-Hartung, a Bayesian posterior and
every fixed weighting a reviewer might have used. A reader cannot tell a number that was
never computed from one produced by an estimator nobody thought to run.

This script asks the question the other way round, so that it terminates. Instead of
searching estimators, it BOUNDS them.

The two bounds
--------------
LIMB 1 -- THE HULL. Every inverse-variance pool, every Mantel-Haenszel and Peto pool and
every fixed weighting whatsoever is a CONVEX COMBINATION of the per-trial log-effects.
A convex combination cannot leave the interval spanned by its inputs. So a claimed point
outside [min effect, max effect] cannot be produced by any estimator that has ever been
written or ever will be. No enumeration is involved and there is no estimator to try.

LIMB 2 -- THE TAU-PATH. Inside the hull, the inverse-variance random-effects FAMILY
bounds itself. Its weights are w_i = 1 / (v_i + tau-squared). As tau-squared runs from 0
to infinity the weights run from the fixed-effect weights to EQUAL weights, and nowhere
else. Scanning that one parameter gives the whole range of points the family can reach,
whatever estimator of tau-squared was used -- DL, REML, PM, Bayesian posterior mean, or a
value chosen by hand.

The worked case this was built on, and which runs in --selftest: a review served
`HR 0.75 (0.61-0.91)` over two trials, COLCOT `0.77 (0.61-0.96)` and LoDoCo2
`0.69 (0.57-0.83)`.

    HULL        0.6900 to 0.7700    0.75 is INSIDE it. Limb 1 does not convict.
    TAU-PATH    0.7215 to 0.7289    0.75 is outside by 0.0211. Limb 2 convicts.

The less precise trial's weight can never exceed one half -- 40.7% at tau-squared = 0,
rising to 50% -- and reaching 0.75 would require it to carry about seventy per cent.
The number was not this review's pool at all: it was an external published benchmark,
recorded in a file the page never consulted. See docs/META-ERROR-LIBRARY.md class C11.

What a CLEAN verdict here does and does not mean
-----------------------------------------------
ACHIEVABLE means the served point is reachable. It does NOT mean it is right, and it does
NOT mean it was computed from these trials. This bounds arithmetic, not provenance.

The two limbs are also not equally strong, and the output says which one it used:

    outside the HULL      no estimator can produce it. Nothing to appeal to.
    outside the TAU-PATH  no INVERSE-VARIANCE RANDOM-EFFECTS pool of these trials can
                          produce it at any tau-squared. Mantel-Haenszel, Peto and
                          bespoke fixed weightings live inside the hull and are NOT
                          excluded by this limb, so it is only binding if the paper
                          declares an inverse-variance method. Pass --method to say
                          what it declared; without one, limb 2 is reported and the
                          exit code is left to limb 1.

The tolerance is the served number's own precision
--------------------------------------------------
An early draft used a fixed point tolerance of 0.005 and the nearest candidate failed;
at a better-justified 0.0066 the same candidate passed. A gate whose answer moves when
you justify its threshold more carefully is measuring the threshold. So there is no
tunable tolerance here: the comparison is made at a half-unit in the LAST PRINTED PLACE
of the claim you pass. `--claim 0.75` is read to two decimals and compared at +/- 0.005;
`--claim 0.7500` is read to four and compared at +/- 0.00005.

Usage
-----
    python pooled-point-achievable.py trials.csv --claim 0.75
    python pooled-point-achievable.py trials.csv --claim 0.75 --method "DL random-effects"
    python pooled-point-achievable.py trials.csv --claim -0.31 --scale diff
    python pooled-point-achievable.py trials.csv --claim 0.75 --json
    python pooled-point-achievable.py --selftest

Input CSV needs a header. Recognised column names (case-insensitive):

    study | label | trial | author            -> row label (optional)
    effect | hr | or | rr | est | estimate    -> the trial's point estimate
    lcl | low | ci_low | lower                -> lower confidence limit
    ucl | high | ci_high | upper              -> upper confidence limit
    se | se_log                               -> standard error, INSTEAD of the limits

On --scale ratio (the default) effects and limits are log-transformed and any `se` is
read as already being on the log scale. On --scale diff they are used as given.

Verdicts, matching the house vocabulary: CLEAN (exit 0), DEFECTS-FOUND (exit 1),
INCONCLUSIVE (exit 2). There is deliberately no verdict called "passed" -- a check that
cannot establish what it needs exits non-zero rather than reading as an all-clear.

Offline, standard library only, no API key, no model call.
MIT-licensed, like the rest of the kit.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, asdict
from typing import Optional

CLEAN = "CLEAN"
DEFECTS_FOUND = "DEFECTS-FOUND"
INCONCLUSIVE = "INCONCLUSIVE"

EXIT = {CLEAN: 0, DEFECTS_FOUND: 1, INCONCLUSIVE: 2}

LABEL_KEYS = ("study", "label", "trial", "author", "name")
EFFECT_KEYS = ("effect", "hr", "or", "rr", "est", "estimate", "point")
LOW_KEYS = ("lcl", "low", "ci_low", "cilow", "lower", "l95", "ci_lower")
HIGH_KEYS = ("ucl", "high", "ci_high", "cihigh", "upper", "u95", "ci_upper")
SE_KEYS = ("se", "se_log", "selog", "stderr", "std_err")


# --------------------------------------------------------------------------- model


@dataclass
class Trial:
    label: str
    theta: float          # effect on the analysis scale (log, for ratios)
    var: float            # variance of theta
    reported: float       # the effect as the user typed it, for display


@dataclass
class Result:
    verdict: str
    claim: Optional[float]
    tolerance: Optional[float]
    k: int
    hull_low: Optional[float]
    hull_high: Optional[float]
    tau_path_low: Optional[float]
    tau_path_high: Optional[float]
    fixed_effect: Optional[float]
    equal_weight: Optional[float]
    weight_shares: Optional[list]
    limb1_fires: bool
    limb2_fires: bool
    limb2_binding: bool
    margin: Optional[float]
    method_declared: Optional[str]
    scale: str
    notes: list


# --------------------------------------------------------------------------- input


def _pick(row: dict, keys) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _num(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    cleaned = str(text).strip().replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def decimals_of(text: str) -> int:
    """How many decimal places the claim was PRINTED to. This sets the tolerance."""
    body = str(text).strip().lower()
    if "e" in body:            # scientific notation states no display precision
        return 6
    if "." not in body:
        return 0
    return len(body.split(".", 1)[1])


def read_trials(rows: list, scale: str) -> tuple:
    """Return (trials, notes). A row that cannot be read is a note, never a silent drop."""
    trials, notes = [], []
    for i, raw in enumerate(rows, start=1):
        row = {(k or "").strip().lower(): (v.strip() if isinstance(v, str) else v)
               for k, v in raw.items()}
        label = _pick(row, LABEL_KEYS) or f"row {i}"
        effect = _num(_pick(row, EFFECT_KEYS))
        if effect is None:
            notes.append(f"{label}: no readable effect estimate -- row not used")
            continue

        if scale == "ratio":
            if effect <= 0:
                notes.append(f"{label}: effect {effect} is not positive on a ratio scale -- row not used")
                continue
            theta = math.log(effect)
        else:
            theta = effect

        se = _num(_pick(row, SE_KEYS))
        if se is not None and se > 0:
            var = se * se
        else:
            low, high = _num(_pick(row, LOW_KEYS)), _num(_pick(row, HIGH_KEYS))
            if low is None or high is None:
                notes.append(f"{label}: needs both confidence limits, or an se -- row not used")
                continue
            if scale == "ratio":
                if low <= 0 or high <= 0:
                    notes.append(f"{label}: confidence limits must be positive on a ratio scale -- row not used")
                    continue
                low, high = math.log(low), math.log(high)
            if high <= low:
                notes.append(f"{label}: upper limit is not above the lower -- row not used")
                continue
            var = ((high - low) / (2 * 1.959963984540054)) ** 2

        if var <= 0:
            notes.append(f"{label}: variance is not positive -- row not used")
            continue
        trials.append(Trial(label=label, theta=theta, var=var, reported=effect))
    return trials, notes


# --------------------------------------------------------------------------- bounds


def pooled_at(trials: list, tau2: float) -> float:
    w = [1.0 / (t.var + tau2) for t in trials]
    return sum(wi * t.theta for wi, t in zip(w, trials)) / sum(w)


def tau_path_range(trials: list, grid: int = 4000) -> tuple:
    """
    The range of pooled points reachable by inverse-variance random effects.

    Scanned rather than solved: for k > 2 the path need not be monotone, so the
    honest description of what this returns is a dense numerical envelope of a
    continuous one-parameter curve, with BOTH exact endpoints included -- the
    fixed-effect pool at tau-squared = 0, and the equal-weight limit as it grows
    without bound. For k = 2 the curve is monotone and the endpoints ARE the range.
    """
    lo = hi = pooled_at(trials, 0.0)
    equal = sum(t.theta for t in trials) / len(trials)
    lo, hi = min(lo, equal), max(hi, equal)
    v_max = max(t.var for t in trials)
    for i in range(grid + 1):
        # log-spaced from far below the smallest variance to far above the largest
        tau2 = 10.0 ** (-10.0 + (math.log10(v_max) + 14.0) * i / grid)
        p = pooled_at(trials, tau2)
        lo, hi = min(lo, p), max(hi, p)
    return lo, hi


def weight_shares(trials: list) -> list:
    """
    Each trial's weight share at tau-squared = 0, and the equal-weight limit it moves to.

    This is the readable form of limb 2's argument, and it is per-trial on purpose. In
    the worked case the informative number is the LESS precise trial's ceiling: COLCOT
    carries 40.7% at tau-squared = 0 and can never exceed 50%, so a pool at 0.75 would
    need it to carry about seventy per cent. A single "largest share" figure answers a
    different question -- it reports the MORE precise trial, 59.3% here -- and that is
    the wrong end of the argument. Reported for every trial rather than collapsed.
    """
    w0 = [1.0 / t.var for t in trials]
    total = sum(w0)
    limit = 1.0 / len(trials)
    return [{"label": t.label, "share_at_tau2_zero": wi / total, "share_in_limit": limit}
            for t, wi in zip(trials, w0)]


# --------------------------------------------------------------------------- check


def check(trials: list, claim_text: Optional[str], scale: str,
          method: Optional[str], notes: list) -> Result:
    to_display = (lambda x: math.exp(x)) if scale == "ratio" else (lambda x: x)

    base = Result(
        verdict=INCONCLUSIVE, claim=None, tolerance=None, k=len(trials),
        hull_low=None, hull_high=None, tau_path_low=None, tau_path_high=None,
        fixed_effect=None, equal_weight=None, weight_shares=None,
        limb1_fires=False, limb2_fires=False, limb2_binding=False, margin=None,
        method_declared=method, scale=scale, notes=list(notes),
    )

    if len(trials) < 2:
        base.notes.append(
            f"k = {len(trials)} usable trials. A pool of fewer than two has nothing to bound; "
            "this is INCONCLUSIVE, which is not a pass."
        )
        return base

    claim = _num(claim_text)
    if claim is None:
        base.notes.append("no readable --claim, so there is nothing to test against the bounds")
        return base
    if scale == "ratio" and claim <= 0:
        base.notes.append(f"--claim {claim} is not positive on a ratio scale")
        return base

    dp = decimals_of(claim_text)
    tol = 0.5 * (10.0 ** -dp)

    hull_lo = to_display(min(t.theta for t in trials))
    hull_hi = to_display(max(t.theta for t in trials))
    tlo, thi = tau_path_range(trials)
    tau_lo, tau_hi = to_display(tlo), to_display(thi)
    if tau_lo > tau_hi:
        tau_lo, tau_hi = tau_hi, tau_lo

    base.claim, base.tolerance = claim, tol
    base.hull_low, base.hull_high = hull_lo, hull_hi
    base.tau_path_low, base.tau_path_high = tau_lo, tau_hi
    base.fixed_effect = to_display(pooled_at(trials, 0.0))
    base.equal_weight = to_display(sum(t.theta for t in trials) / len(trials))
    base.weight_shares = weight_shares(trials)

    base.limb1_fires = claim < hull_lo - tol or claim > hull_hi + tol
    base.limb2_fires = claim < tau_lo - tol or claim > tau_hi + tol

    # Limb 2 excludes only the inverse-variance random-effects family. It is binding
    # on the verdict when the paper declares such a method, and reported otherwise.
    declared = (method or "").lower()
    iv_words = ("inverse", "dersimonian", "dl", "reml", "random", "paule", "mandel",
                "hartung", "knapp", "sidik", "empirical bayes", "eb", "hksj", "ml")
    base.limb2_binding = any(w in declared.split() or w in declared for w in iv_words)

    if base.limb2_fires:
        base.margin = min(abs(claim - (tau_lo - tol)), abs(claim - (tau_hi + tol)))
    elif base.limb1_fires:
        base.margin = min(abs(claim - (hull_lo - tol)), abs(claim - (hull_hi + tol)))

    if base.limb1_fires:
        base.verdict = DEFECTS_FOUND
        base.notes.append(
            f"OUTSIDE THE HULL. The served point {claim} lies outside "
            f"[{hull_lo:.4f}, {hull_hi:.4f}], the interval spanned by these {len(trials)} "
            "trials. Every pooled estimate is a weighted average of its inputs, so no "
            "estimator of any kind can produce this from these trials."
        )
    elif base.limb2_fires and base.limb2_binding:
        base.verdict = DEFECTS_FOUND
        base.notes.append(
            f"OUTSIDE THE TAU-PATH. The served point {claim} lies outside "
            f"[{tau_lo:.4f}, {tau_hi:.4f}], the full range reachable by inverse-variance "
            f"random effects at any tau-squared, and the declared method ({method!r}) is in "
            "that family. It IS inside the hull, so a Mantel-Haenszel, Peto or bespoke "
            "fixed weighting could reach it -- but not the method this paper says it used."
        )
    elif base.limb2_fires:
        base.verdict = INCONCLUSIVE
        base.notes.append(
            f"Outside the tau-path [{tau_lo:.4f}, {tau_hi:.4f}] but inside the hull "
            f"[{hull_lo:.4f}, {hull_hi:.4f}]. No inverse-variance random-effects pool of "
            "these trials reaches it at any tau-squared. Mantel-Haenszel, Peto and fixed "
            "weightings are NOT excluded, so this is only a defect if the paper declares an "
            "inverse-variance method -- pass --method with what it declared to get a verdict."
        )
    else:
        base.verdict = CLEAN
        base.notes.append(
            f"ACHIEVABLE. {claim} is within [{tau_lo:.4f}, {tau_hi:.4f}] at the claim's own "
            f"printed precision (+/- {tol:g}). This bounds the ARITHMETIC and says nothing "
            "about whether the number was computed from these trials, or is correct."
        )
    return base


# --------------------------------------------------------------------------- report


def render(r: Result) -> str:
    out = []
    out.append(f"pooled-point-achievable  --  {r.verdict}")
    out.append("")
    if r.claim is not None:
        out.append(f"  claim served      {r.claim}  (compared at +/- {r.tolerance:g}, "
                   f"a half-unit in its own last printed place)")
    out.append(f"  trials usable     k = {r.k}")
    if r.hull_low is not None:
        out.append("")
        out.append(f"  LIMB 1  HULL      [{r.hull_low:.4f}, {r.hull_high:.4f}]"
                   f"   {'FIRES' if r.limb1_fires else 'does not fire'}")
        out.append("                    no estimator of any kind can leave this interval")
        out.append(f"  LIMB 2  TAU-PATH  [{r.tau_path_low:.4f}, {r.tau_path_high:.4f}]"
                   f"   {'FIRES' if r.limb2_fires else 'does not fire'}"
                   f"{'' if r.limb2_binding or not r.limb2_fires else '  (reported, not binding -- no inverse-variance method declared)'}")
        out.append(f"                    fixed-effect {r.fixed_effect:.4f}"
                   f"  ->  equal weights {r.equal_weight:.4f}")
        out.append("                    weight each trial can carry, tau-squared 0 -> limit:")
        for w in r.weight_shares:
            out.append(f"                      {w['label']:<24}"
                       f"{100 * w['share_at_tau2_zero']:5.1f}%  ->{100 * w['share_in_limit']:5.1f}%")
    if r.margin is not None:
        out.append("")
        out.append(f"  margin            {r.margin:.4f} beyond the tolerated edge")
    if r.notes:
        out.append("")
        for n in r.notes:
            out.append(f"  - {n}")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- selftest


def _rows(triples):
    return [{"study": s, "effect": str(e), "lcl": str(l), "ucl": str(u)}
            for s, e, l, u in triples]


COLCHICINE = [("COLCOT", 0.77, 0.61, 0.96), ("LoDoCo2", 0.69, 0.57, 0.83)]


def selftest() -> int:
    """
    Proofs in BOTH directions. A detector with only a positive test passes CI while
    matching everything; one with only a negative test has never been shown to work.
    Case 2 is the real corpus case that this script was written for, with the numbers
    read off the two published trials rather than invented for the test.
    """
    failures = []

    def expect(name, got, want):
        if got != want:
            failures.append(f"{name}: expected {want}, got {got}")
        print(f"  {'ok  ' if got == want else 'FAIL'}  {name}: {got}")

    print("pooled-point-achievable --selftest")
    print()

    # 1. KNOWN-BAD, limb 1. A claim below both trials cannot be a weighted average.
    t, n = read_trials(_rows(COLCHICINE), "ratio")
    r = check(t, "0.60", "ratio", "DL random-effects", n)
    expect("1 outside the hull fires limb 1", (r.verdict, r.limb1_fires), (DEFECTS_FOUND, True))

    # 2. KNOWN-BAD, limb 2 -- THE REAL CASE. Inside the hull, outside the tau-path.
    r = check(t, "0.75", "ratio", "DL random-effects pooling of 2 landmark RCTs", n)
    expect("2 the served 0.75 is inside the hull", r.limb1_fires, False)
    expect("2 and outside the tau-path", (r.verdict, r.limb2_fires), (DEFECTS_FOUND, True))
    expect("2 fixed-effect pool reproduces 0.7215", f"{r.fixed_effect:.4f}", "0.7215")
    expect("2 tau-path upper end is the equal-weight limit 0.7289",
           f"{r.tau_path_high:.4f}", "0.7289")
    shares = {w["label"]: w["share_at_tau2_zero"] for w in r.weight_shares}
    expect("2 the LESS precise trial COLCOT carries 40.7% at tau-squared 0",
           f"{100 * shares['COLCOT']:.1f}", "40.7")
    expect("2 and it can never exceed the 50% equal-weight limit",
           max(shares["COLCOT"], 0.5) <= 0.5, True)

    # 3. KNOWN-GOOD. The pool these two trials DO give must not fire.
    r = check(t, "0.72", "ratio", "DL random-effects", n)
    expect("3 the true pool 0.72 is clean", r.verdict, CLEAN)
    r = check(t, "0.7215", "ratio", "DL random-effects", n)
    expect("3 and so is it at four decimals", r.verdict, CLEAN)

    # 4. The tolerance is the claim's own precision, not a tunable constant.
    #    0.73 rounds to a band overlapping the tau-path; 0.7300 does not.
    r2, r4 = (check(t, "0.73", "ratio", "DL", n), check(t, "0.7300", "ratio", "DL", n))
    expect("4 0.73 at two decimals is tolerated", r2.verdict, CLEAN)
    expect("4 0.7300 at four decimals is not", r4.verdict, DEFECTS_FOUND)

    # 5. Limb 2 is NOT binding without a declared inverse-variance method.
    r = check(t, "0.75", "ratio", None, n)
    expect("5 no declared method leaves 0.75 inconclusive, not clean", r.verdict, INCONCLUSIVE)
    expect("5 and it is not silently passed", EXIT[r.verdict] != 0, True)

    # 6. A hull violation convicts even with no method declared -- it needs no family.
    r = check(t, "0.60", "ratio", None, n)
    expect("6 the hull convicts without a declared method", r.verdict, DEFECTS_FOUND)

    # 7. k < 2 is INCONCLUSIVE, never CLEAN.
    t1, n1 = read_trials(_rows([("only one", 0.77, 0.61, 0.96)]), "ratio")
    expect("7 k=1 is inconclusive", check(t1, "0.77", "ratio", "DL", n1).verdict, INCONCLUSIVE)

    # 8. An unreadable row is reported, never silently dropped into a smaller k.
    bad = _rows(COLCHICINE) + [{"study": "no interval", "effect": "0.8", "lcl": "", "ucl": ""}]
    t8, n8 = read_trials(bad, "ratio")
    expect("8 the unusable row is named in the notes", len(n8), 1)
    expect("8 and k counts only what was read", len(t8), 2)

    # 9. Difference scale works and is not log-transformed.
    td, nd = read_trials(_rows([("A", -0.40, -0.60, -0.20), ("B", -0.20, -0.40, 0.00)]), "diff")
    rd = check(td, "-0.05", "diff", "REML", nd)
    expect("9 a difference-scale claim outside the hull fires", rd.limb1_fires, True)
    rd = check(td, "-0.30", "diff", "REML", nd)
    expect("9 and the midpoint of two equally precise trials is clean", rd.verdict, CLEAN)

    # 10. Three trials: the equal-weight limit is included in the scanned range.
    t10, n10 = read_trials(_rows([("A", 0.50, 0.40, 0.62), ("B", 0.80, 0.70, 0.91),
                                  ("C", 0.95, 0.70, 1.29)]), "ratio")
    r10 = check(t10, "0.99", "ratio", "REML", n10)
    expect("10 k=3 scan brackets the equal-weight limit",
           r10.tau_path_low <= r10.equal_weight <= r10.tau_path_high, True)
    expect("10 and a claim above every trial still fires on the hull", r10.limb1_fires, True)

    print()
    if failures:
        print(f"SELFTEST FAILED -- {len(failures)} of the proofs above did not hold")
        for f in failures:
            print(f"  {f}")
        return 1
    print("SELFTEST PASSED -- the check fires on known-bad input and stays quiet on known-good")
    return 0


# --------------------------------------------------------------------------- cli


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Bound the pooled points a set of trials can produce, and test a served claim against them.",
        epilog="Verdicts: CLEAN (0), DEFECTS-FOUND (1), INCONCLUSIVE (2). There is no verdict called 'passed'.",
    )
    p.add_argument("csv", nargs="?", help="CSV of per-trial effects with confidence limits or standard errors")
    p.add_argument("--claim", help="the pooled point the paper serves, typed at the precision it prints")
    p.add_argument("--scale", choices=("ratio", "diff"), default="ratio",
                   help="ratio (default; log-transformed) or diff (used as given)")
    p.add_argument("--method", help="the pooling method the paper declares, e.g. 'DL random-effects'")
    p.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output")
    p.add_argument("--selftest", action="store_true", help="run the proofs and exit")
    a = p.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.csv:
        p.print_help()
        return 2

    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as exc:
        print(f"{INCONCLUSIVE}: cannot read {a.csv} -- {exc}", file=sys.stderr)
        return EXIT[INCONCLUSIVE]

    if not rows:
        print(f"{INCONCLUSIVE}: {a.csv} has a header and no rows", file=sys.stderr)
        return EXIT[INCONCLUSIVE]

    trials, notes = read_trials(rows, a.scale)
    result = check(trials, a.claim, a.scale, a.method, notes)

    if a.as_json:
        payload = asdict(result)
        payload["trials"] = [{"label": t.label, "effect": t.reported} for t in trials]
        print(json.dumps(payload, indent=2))
    else:
        print(render(result))
    return EXIT[result.verdict]


if __name__ == "__main__":
    sys.exit(main())
