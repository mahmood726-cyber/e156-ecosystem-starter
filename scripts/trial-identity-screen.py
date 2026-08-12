#!/usr/bin/env python3
"""
trial-identity-screen.py -- screen an included-studies table for one trial entered more than once.

Why this exists
---------------
Across six published syntheses adjudicated in this programme, three were erroneous,
and all three failed the same way: a trial was counted as several, or characterised
as something it is not. Not one failed by missing a trial. The underlying defect is
matching on the CITATION STRING instead of on TRIAL IDENTITY -- so "Bakris 2020" and
"Gerasimos 2021" read as two studies when they are one trial, and a pooled analysis
of two trials reads as a third trial alongside its own components.

This screen ignores names and looks at denominators, which is where the duplication
is visible. It is deliberately cheap: standard library only, offline, no model call,
runs on a table you can type out in a minute.

Relationship to `scripts/meta-self-audit.py`
--------------------------------------------
`meta-self-audit.py`'s MEL-03 detector runs the same subset-sum idea over a rendered
single-file HTML dashboard. This script takes a CSV instead, so you can screen a
synthesis you did NOT write -- a published paper's Table 1, typed out -- and it adds
three things MEL-03 does not do: arm-level reconciliation, near-duplicate matching
under a transcription tolerance, and the I-squared co-signature. Use MEL-03 on your
own dashboard; use this on somebody else's table.

Usage
-----
    python trial-identity-screen.py studies.csv
    python trial-identity-screen.py studies.csv --universe 22000 --i2 0
    python trial-identity-screen.py studies.csv --json
    python trial-identity-screen.py --selftest

Input CSV needs a header with, at minimum, a study-label column and either
`n` or both `n_treat` and `n_ctrl`. Recognised names (case-insensitive):

    study | label | trial | author        -> the row label
    n_treat | treat | intervention | t    -> intervention arm size
    n_ctrl | ctrl | control | comparator | c -> control arm size
    n | total | participants              -> total (derived from arms if absent)

Verdicts, matching the house vocabulary: CLEAN (exit 0), DEFECTS-FOUND (exit 1),
INCONCLUSIVE (exit 2). There is deliberately no verdict called "passed" -- a screen
that cannot establish what it needs exits non-zero rather than reading as an all-clear.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

__version__ = "1.0.0"

CLEAN = "CLEAN"
DEFECTS = "DEFECTS-FOUND"
INCONCLUSIVE = "INCONCLUSIVE"

# Bounded on purpose. An unbounded subset-sum over a large table is both slow and
# increasingly prone to coincidental hits: with enough rows, some subset sums to
# almost anything. Beyond these bounds the screen reports INCONCLUSIVE rather than
# a false all-clear -- the same fail-closed choice MEL-03 makes.
MAX_ROWS_FOR_SUBSET_SUM = 40
MAX_SUBSET_SIZE = 4

# Default tolerance for near-duplicate arm matching. Zero would be the strict
# choice, but it misses the real cases: one published table rendered the same
# trial's arms as 2833/2841, 2840/2833 and 2830/2839 in three different rows.
# Those are transcription noise around one trial, not three trials.
DEFAULT_ARM_TOLERANCE = 12

# I-squared at or below this, combined with a duplication hit, is the co-signature.
# Pooling data against itself drives between-study heterogeneity toward zero because
# the "studies" are not independent.
I2_FLOOR = 5.0

LABEL_KEYS = ("study", "label", "trial", "author", "name")
TREAT_KEYS = ("n_treat", "ntreat", "treat", "intervention", "t", "n_t", "experimental")
CTRL_KEYS = ("n_ctrl", "nctrl", "ctrl", "control", "comparator", "c", "n_c", "placebo")
TOTAL_KEYS = ("n", "total", "participants", "n_total", "sample")


@dataclass
class Row:
    label: str
    n_treat: Optional[int] = None
    n_ctrl: Optional[int] = None
    n_total: Optional[int] = None
    index: int = 0

    def arms(self) -> Optional[tuple[int, int]]:
        if self.n_treat is None or self.n_ctrl is None:
            return None
        return (self.n_treat, self.n_ctrl)

    def total(self) -> Optional[int]:
        if self.n_total is not None:
            return self.n_total
        a = self.arms()
        return sum(a) if a else None


@dataclass
class Finding:
    check: str
    severity: str          # BLOCK | WARN | INFO | PASS
    subject: str
    message: str

    def line(self) -> str:
        return f"[{self.severity:5}] {self.check:28} {self.subject} :: {self.message}"


@dataclass
class Report:
    verdict: str = CLEAN
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------


def S1_arm_level_subset_sum(rows: list[Row], _cfg) -> list[Finding]:
    """A row whose BOTH arms equal the summed arms of other rows is a pooled analysis
    sitting alongside its own components.

    This is the strongest signal in the screen, and the reason it is strongest is that
    it has to hold twice independently. In the confirmed finerenone case the pooled
    row's arms were 6519/6507, and its two component trials were 2833/2841 and
    3686/3666: 2833+3686 = 6519 exactly, and 2841+3666 = 6507 exactly. Two exact
    coincidences on the same subset is not a coincidence.
    """
    out = []
    usable = [r for r in rows if r.arms()]
    if len(usable) < 3:
        return out
    if len(usable) > MAX_ROWS_FOR_SUBSET_SUM:
        out.append(Finding("S1_ARM_SUBSET_SUM", "INFO", f"{len(usable)} rows",
                           f"table exceeds the bounded search ({MAX_ROWS_FOR_SUBSET_SUM} rows); "
                           "arm-level subset-sum not run. This is not an all-clear."))
        return out
    for target in usable:
        others = [r for r in usable if r is not target]
        tt, tc = target.arms()
        for size in range(2, min(MAX_SUBSET_SIZE, len(others)) + 1):
            hit = None
            for combo in itertools.combinations(others, size):
                if sum(r.n_treat for r in combo) == tt and sum(r.n_ctrl for r in combo) == tc:
                    hit = combo
                    break
            if hit:
                names = " + ".join(r.label for r in hit)
                out.append(Finding(
                    "S1_ARM_SUBSET_SUM", "BLOCK", target.label,
                    f"both arms reconcile exactly against other rows: "
                    f"{'+'.join(str(r.n_treat) for r in hit)} = {tt} and "
                    f"{'+'.join(str(r.n_ctrl) for r in hit)} = {tc} ({names}). "
                    f"'{target.label}' is almost certainly a pooled analysis of rows it is "
                    "pooled ALONGSIDE. Those participants are counted twice."))
                break
    return out


def S2_total_subset_sum(rows: list[Row], _cfg) -> list[Finding]:
    """Same idea on totals only, for tables that do not print arm splits.

    Weaker than S1: one coincidence instead of two. Reported as WARN, and it is
    suppressed when S1 already flagged the same row so the reader is not told the
    same thing twice.
    """
    out = []
    usable = [r for r in rows if r.total() is not None]
    if len(usable) < 3:
        return out
    if len(usable) > MAX_ROWS_FOR_SUBSET_SUM:
        out.append(Finding("S2_TOTAL_SUBSET_SUM", "INFO", f"{len(usable)} rows",
                           f"table exceeds the bounded search ({MAX_ROWS_FOR_SUBSET_SUM} rows); "
                           "total-level subset-sum not run. This is not an all-clear."))
        return out
    for target in usable:
        others = [r for r in usable if r is not target]
        tn = target.total()
        for size in range(2, min(MAX_SUBSET_SIZE, len(others)) + 1):
            hit = None
            for combo in itertools.combinations(others, size):
                if sum(r.total() for r in combo) == tn:
                    hit = combo
                    break
            if hit:
                names = " + ".join(r.label for r in hit)
                out.append(Finding(
                    "S2_TOTAL_SUBSET_SUM", "WARN", target.label,
                    f"total {tn} equals the sum of {names} "
                    f"({'+'.join(str(r.total()) for r in hit)}). Check whether this row is a "
                    "pooled report of those rows. Totals alone are weaker evidence than arms; "
                    "print the arm splits and re-run."))
                break
    return out


def S3_near_duplicate_arms(rows: list[Row], cfg) -> list[Finding]:
    """Two rows with near-identical arm splits under different names.

    Origin: one synthesis entered the same trial as "Barkris" (a misspelling of
    Bakris) and again as "Ruilope", a co-author of the same trial. The names look
    unrelated; the arm splits do not. The tolerance exists because published
    characteristics tables disagree with themselves on the same trial's arm sizes by
    a handful of patients -- the rows there read 2840/2833 and 2830/2839 for a trial
    whose registered split is 2833/2841.

    A tolerance buys sensitivity at the cost of precision. Two genuinely distinct
    trials of similar size will collide. This is a screen, not a verdict: every hit
    needs the registry identifier checked before you act on it.
    """
    out = []
    tol = cfg.tol
    usable = [r for r in rows if r.arms()]
    for a, b in itertools.combinations(usable, 2):
        at, ac = a.arms()
        bt, bc = b.arms()
        dt, dc = abs(at - bt), abs(ac - bc)
        # also test the transposed pairing -- a table that swaps the arm columns on
        # one row of a duplicated trial is exactly how this hides
        st, sc = abs(at - bc), abs(ac - bt)
        if dt <= tol and dc <= tol:
            how = f"arms match within {tol} ({at}/{ac} vs {bt}/{bc})"
        elif st <= tol and sc <= tol:
            how = f"arms match within {tol} WHEN TRANSPOSED ({at}/{ac} vs {bt}/{bc})"
        else:
            continue
        sev = "BLOCK" if (dt == 0 and dc == 0) or (st == 0 and sc == 0) else "WARN"
        exact = " exactly" if sev == "BLOCK" else ""
        out.append(Finding(
            "S3_NEAR_DUPLICATE_ARMS", sev, f"{a.label} / {b.label}",
            f"two rows{exact} share an arm split: {how}. Different citation strings can name "
            "one trial -- a surname, a co-author, a forename mistaken for a surname, or a "
            "misspelling. Resolve both rows to a registry identifier before pooling."))
    return out


def S4_universe_inflation(rows: list[Row], cfg) -> list[Finding]:
    """Total participants against the known randomised universe for the question.

    You have to supply the universe (--universe); the screen cannot know it. That is
    the honest design: the number comes from your own count of the registered trials
    that exist, and stating it is the point of the exercise.
    """
    out = []
    totals = [r.total() for r in rows if r.total() is not None]
    if not totals:
        return out
    claimed = sum(totals)
    out.append(Finding("S4_UNIVERSE_INFLATION", "INFO", "table total",
                       f"rows sum to {claimed:,} participants across {len(totals)} rows"))
    if cfg.universe is None:
        out.append(Finding("S4_UNIVERSE_INFLATION", "INFO", "universe",
                           "no --universe supplied, so inflation was not tested. Supply the "
                           "randomised universe for this question to enable it."))
        return out
    if cfg.universe <= 0:
        return out
    infl = 100.0 * (claimed - cfg.universe) / cfg.universe
    if infl >= 25.0:
        out.append(Finding(
            "S4_UNIVERSE_INFLATION", "BLOCK", "table total",
            f"{claimed:,} claimed against a universe of {cfg.universe:,} = +{infl:.0f}%. "
            "A synthesis cannot randomise more participants than were ever randomised. "
            "The two confirmed duplicate-counting syntheses in this programme sat at "
            "+52% and +82%."))
    elif infl > 0:
        out.append(Finding("S4_UNIVERSE_INFLATION", "WARN", "table total",
                           f"{claimed:,} vs universe {cfg.universe:,} = +{infl:.0f}%. "
                           "Modest, but any excess over the universe needs an explanation."))
    else:
        out.append(Finding("S4_UNIVERSE_INFLATION", "PASS", "table total",
                           f"{claimed:,} within the stated universe of {cfg.universe:,}"))
    return out


def S5_i2_cosignature(rows: list[Row], cfg, prior: list[Finding] | None = None) -> list[Finding]:
    """Near-zero heterogeneity ALONGSIDE a duplication hit.

    On its own, a low I-squared is not a defect -- consistent trials produce it
    legitimately, and this screen must not teach anyone that low heterogeneity is
    suspicious. It is the CONJUNCTION that is diagnostic: pooling a trial against
    itself forces the between-study variance down, because the duplicated rows agree
    with themselves perfectly. Both confirmed cases reported I-squared near 0 across
    most outcomes while inflating N by half again or more.
    """
    out = []
    if cfg.i2 is None:
        return out
    dup_hits = [f for f in (prior or [])
                if f.severity == "BLOCK" and f.check in ("S1_ARM_SUBSET_SUM",
                                                         "S3_NEAR_DUPLICATE_ARMS",
                                                         "S4_UNIVERSE_INFLATION")]
    if cfg.i2 > I2_FLOOR:
        out.append(Finding("S5_I2_COSIGNATURE", "INFO", f"I2={cfg.i2:g}%",
                           "above the co-signature floor; no conjunction to report"))
        return out
    if not dup_hits:
        out.append(Finding(
            "S5_I2_COSIGNATURE", "INFO", f"I2={cfg.i2:g}%",
            "low heterogeneity with no duplication hit. This is NOT a defect on its own "
            "-- consistent trials legitimately produce it."))
        return out
    out.append(Finding(
        "S5_I2_COSIGNATURE", "BLOCK", f"I2={cfg.i2:g}%",
        f"near-zero heterogeneity CO-OCCURRING with {len(dup_hits)} duplication finding(s). "
        "This is the screenable signature: duplicated rows agree with themselves perfectly, "
        "which drives between-study variance toward zero and makes every pooled interval "
        "falsely narrow. Re-pool after de-duplicating by registry identifier."))
    return out


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def screen(rows: list[Row], cfg) -> Report:
    findings: list[Finding] = []
    findings += S1_arm_level_subset_sum(rows, cfg)
    s1_subjects = {f.subject for f in findings if f.check == "S1_ARM_SUBSET_SUM"}
    findings += [f for f in S2_total_subset_sum(rows, cfg) if f.subject not in s1_subjects]
    findings += S3_near_duplicate_arms(rows, cfg)
    findings += S4_universe_inflation(rows, cfg)
    findings += S5_i2_cosignature(rows, cfg, prior=findings)

    blocks = [f for f in findings if f.severity == "BLOCK"]
    warns = [f for f in findings if f.severity == "WARN"]
    infos = [f for f in findings if f.severity == "INFO"]
    bounded_out = [f for f in infos if "exceeds the bounded search" in f.message]

    if blocks:
        verdict = DEFECTS
    elif bounded_out:
        verdict = INCONCLUSIVE
    elif warns:
        verdict = DEFECTS
    else:
        verdict = CLEAN

    return Report(verdict=verdict, findings=findings, summary={
        "screen_version": __version__,
        "rows": len(rows),
        "rows_with_arms": len([r for r in rows if r.arms()]),
        "blocks": len(blocks),
        "warns": len(warns),
        "verdict": verdict,
    })


def render(rep: Report) -> str:
    lines = [f"trial-identity-screen v{__version__}", ""]
    lines.append(f"VERDICT: {rep.verdict}  "
                 f"({rep.summary['blocks']} BLOCK, {rep.summary['warns']} WARN "
                 f"over {rep.summary['rows']} rows)")
    lines.append("")
    for sev in ("BLOCK", "WARN", "INFO", "PASS"):
        sel = [f for f in rep.findings if f.severity == sev]
        for f in sel:
            lines.append(f.line())
    if rep.verdict == CLEAN:
        lines += ["", "No duplication signature found. Read the blind spots before trusting this:",
                  "  * a trial can be duplicated without its denominators reconciling, if the",
                  "    two reports analyse different subsets of one cohort",
                  "  * the screen never checks comparator, population or outcome definition --",
                  "    the OTHER way a synthesis mis-characterises a trial it did find",
                  "  * without --universe and --i2, two of the five screens did not run"]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------


def _pick(header: list[str], keys: tuple) -> Optional[str]:
    norm = {h.strip().lower().replace(" ", "_").replace("-", "_"): h for h in header}
    for k in keys:
        if k in norm:
            return norm[k]
    return None


def _int(v) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def load_csv(path: str) -> list[Row]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rdr = csv.DictReader(fh)
        if not rdr.fieldnames:
            raise ValueError("CSV has no header row")
        header = list(rdr.fieldnames)
        lab = _pick(header, LABEL_KEYS)
        t = _pick(header, TREAT_KEYS)
        c = _pick(header, CTRL_KEYS)
        n = _pick(header, TOTAL_KEYS)
        if lab is None:
            raise ValueError(f"no study-label column found; looked for {LABEL_KEYS} in {header}")
        if t is None and c is None and n is None:
            raise ValueError(
                f"no size column found; need `n`, or `n_treat` + `n_ctrl`. Header was {header}")
        rows = []
        for i, r in enumerate(rdr):
            label = (r.get(lab) or "").strip() or f"row{i + 1}"
            rows.append(Row(label=label, index=i,
                            n_treat=_int(r.get(t)) if t else None,
                            n_ctrl=_int(r.get(c)) if c else None,
                            n_total=_int(r.get(n)) if n else None))
    if not rows:
        raise ValueError("CSV has a header but no data rows")
    return rows


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------


class _Cfg:
    def __init__(self, universe=None, i2=None, tol=DEFAULT_ARM_TOLERANCE):
        self.universe = universe
        self.i2 = i2
        self.tol = tol


def _selftest() -> int:
    """Positive case + negative controls.

    The positive case is a published synthesis's own characteristics table, read
    verbatim in this programme's audit. Names as printed; the misspelling is theirs.
    """
    print(f"trial-identity-screen v{__version__} -- self-test\n")
    ok = True

    # --- positive: the confirmed triple-count, arm splits as printed -------------
    dup = [
        Row("Bakris (2020)", 2833, 2841),      # FIDELIO-DKD
        Row("Bertram (2021)", 3686, 3666),     # FIGARO-DKD
        Row("Gerasimos (2021)", 2833, 2841),   # FIDELIO-DKD again
        Row("Agarwal (2022)", 6519, 6507),     # FIDELITY = FIDELIO + FIGARO pooled
        Row("Gerasimos (2022)", 3686, 3666),   # FIGARO-DKD again
    ]
    rep = screen(dup, _Cfg(universe=22000, i2=0))
    print(render(rep))
    print()

    def want(name, cond):
        nonlocal ok
        print(f"  {'ok     ' if cond else 'MISSED '} {name}")
        ok &= bool(cond)

    checks = {f.check for f in rep.findings if f.severity == "BLOCK"}
    want("pooled-alongside-components caught (S1)", "S1_ARM_SUBSET_SUM" in checks)
    want("repeated trial caught (S3)", "S3_NEAR_DUPLICATE_ARMS" in checks)
    want("universe inflation caught (S4)", "S4_UNIVERSE_INFLATION" in checks)
    want("I2 co-signature caught (S5)", "S5_I2_COSIGNATURE" in checks)
    want("verdict is DEFECTS-FOUND", rep.verdict == DEFECTS)

    print("\n  --- negative controls (must NOT fire) ---")

    # a genuinely clean table: five distinct trials, no subset relation, sizes far apart
    clean = [
        Row("Trial A", 120, 118),
        Row("Trial B", 340, 337),
        Row("Trial C", 811, 795),
        Row("Trial D", 1502, 1488),
        Row("Trial E", 2610, 2590),
    ]
    rc = screen(clean, _Cfg(universe=11000, i2=41))
    want("clean table returns CLEAN", rc.verdict == CLEAN)
    want("clean table raises no BLOCK", not [f for f in rc.findings if f.severity == "BLOCK"])

    # low I2 with NO duplication must not be called a defect -- the co-signature is
    # a conjunction, and a screen that flagged low heterogeneity alone would teach
    # exactly the wrong lesson
    rlow = screen(clean, _Cfg(universe=11000, i2=0))
    want("low I2 alone is not a defect",
         not [f for f in rlow.findings
              if f.check == "S5_I2_COSIGNATURE" and f.severity == "BLOCK"])
    want("low I2 alone still CLEAN", rlow.verdict == CLEAN)

    # a table under the universe must not be flagged as inflated
    want("no inflation flag when within universe",
         not [f for f in rc.findings
              if f.check == "S4_UNIVERSE_INFLATION" and f.severity in ("BLOCK", "WARN")])

    # oversized table must go INCONCLUSIVE, never CLEAN
    big = [Row(f"T{i}", 100 + i * 7, 100 + i * 5) for i in range(MAX_ROWS_FOR_SUBSET_SUM + 5)]
    rb = screen(big, _Cfg())
    want("oversized table is INCONCLUSIVE, not CLEAN", rb.verdict == INCONCLUSIVE)

    # transposed-arm duplicate must still be caught
    trans = [Row("X (2020)", 500, 480), Row("Y (2021)", 480, 500), Row("Z (2019)", 90, 88)]
    rt = screen(trans, _Cfg())
    want("transposed-arm duplicate caught",
         any(f.check == "S3_NEAR_DUPLICATE_ARMS" and f.severity == "BLOCK" for f in rt.findings))

    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", nargs="?", help="included-studies table")
    p.add_argument("--universe", type=int, default=None,
                   help="total participants ever randomised across the trials that exist "
                        "for this question; enables the inflation screen")
    p.add_argument("--i2", type=float, default=None,
                   help="the synthesis's reported I-squared (percent); enables the co-signature")
    p.add_argument("--tol", type=int, default=DEFAULT_ARM_TOLERANCE,
                   help=f"arm-size tolerance for near-duplicate matching "
                        f"(default {DEFAULT_ARM_TOLERANCE}; 0 = exact only)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args(argv)

    if a.selftest:
        return _selftest()
    if not a.csv:
        p.print_help()
        return 2

    try:
        rows = load_csv(a.csv)
    except Exception as exc:  # noqa: BLE001
        print(f"INCONCLUSIVE: could not read {a.csv}: {exc}", file=sys.stderr)
        return 2

    rep = screen(rows, a)
    if a.json:
        print(json.dumps({"summary": rep.summary,
                          "findings": [asdict(f) for f in rep.findings]}, indent=2))
    else:
        print(render(rep))

    return {CLEAN: 0, DEFECTS: 1, INCONCLUSIVE: 2}[rep.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
