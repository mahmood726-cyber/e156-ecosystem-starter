#!/usr/bin/env python3
"""
count_recovery_harness.py — pre-condition checks for per-arm 2x2 event-count extraction.

Purpose
-------
Every check in this file exists because the mistake it catches was actually made,
in this programme, on real data. The harness turns those lessons into gates that
run before an extraction is allowed downstream, instead of paragraphs in a memo
that the next lane will not read.

Design rules
------------
1.  FAIL CLOSED. A cell that cannot be shown to be safe is BLOCK, not PASS.
    Missing information is never treated as reassurance.
2.  A BLOCKED FETCH IS NOT AN ABSENCE. Retrieval failure is recorded as
    obstacle=<reason> and raises; it never becomes events=None / "not reported".
3.  READ, NEVER COMPUTE. Any cell whose provenance is not "read" is blocked.
    The harness will not multiply a percentage by a denominator for you, and it
    blocks cells that admit to having done so.
4.  Stdlib only. No install step, so the next lane can actually run it.

Usage
-----
    python count_recovery_harness.py --selftest
    python count_recovery_harness.py extraction.json
    python count_recovery_harness.py extraction.json --report report.md --json result.json

Exit codes: 0 = no BLOCKs, 1 = one or more BLOCKs, 2 = usage/parse error.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Optional

__version__ = "1.0.0"

# --------------------------------------------------------------------------
# Source tiers
# --------------------------------------------------------------------------
# T1  trial's own primary publication (journal table / results text)
# T2  registry posted results module (ClinicalTrials.gov, EUCTR, jRCT ...)
# T3  regulatory review document (FDA statistical review, EMA EPAR)
# T4  prior meta-analysis extraction table  -- UNVERIFIED, must be flagged
TIERS = ("T1", "T2", "T3", "T4")
UNVERIFIED_TIERS = ("T4",)

SEVERITY_ORDER = {"PASS": 0, "INFO": 1, "WARN": 2, "BLOCK": 3}


class BlockedFetch(Exception):
    """Raised when retrieval fails.

    Deliberately an exception rather than a return value. If retrieval fails, the
    caller must handle it as an obstacle -- it must not silently flow onward as
    'no data available'. See CHK009.
    """

    def __init__(self, url: str, reason: str, tried: Iterable[str] = ()):
        self.url = url
        self.reason = reason
        self.tried = list(tried)
        super().__init__(f"blocked fetch: {url} :: {reason} :: tried={self.tried}")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class Cell:
    """One arm x one outcome x one trial."""

    trial: str
    nct: str
    arm: str
    outcome: str                      # canonical outcome concept key
    events: Optional[int] = None
    analysed: Optional[int] = None
    randomised: Optional[int] = None
    population_label: Optional[str] = None   # e.g. "FAS", "randomised", "ITT"
    selected: Optional[bool] = None   # when >1 population exists for one outcome, exactly one is True
    denominator_reason: Optional[str] = None  # why analysed != randomised
    printed_percent: Optional[float] = None   # percentage as printed beside the count
    provenance: str = "read"          # "read" | "derived" | "assumed"
    sources: list[dict] = field(default_factory=list)
    # each source: {"tier": "T1", "pointer": "...", "url": "...", "flagged_unverified": bool}
    not_recovered_reason: Optional[str] = None
    obstacle: Optional[str] = None    # set when retrieval was blocked
    identifier_provenance: Optional[str] = None  # "lookup" | "recall" | None
    registry_units: Optional[str] = None  # e.g. "participants", "percentage of participants"
    is_component_of: Optional[str] = None  # composite outcome key this feeds
    notes: str = ""

    def key(self) -> tuple:
        return (self.nct, self.arm, self.outcome)

    def tiers(self) -> list[str]:
        return [s.get("tier") for s in self.sources]


@dataclass
class Finding:
    check: str
    severity: str          # PASS | INFO | WARN | BLOCK
    subject: str
    message: str

    def line(self) -> str:
        return f"[{self.severity:5}] {self.check:34} {self.subject} :: {self.message}"


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
# Each check is a function (cells: list[Cell]) -> list[Finding].
# Registered in CHECKS at the bottom, in run order.


def CHK001_COUNT_PERCENT_AGREEMENT(cells: list[Cell]) -> list[Finding]:
    """Every count must agree with the percentage printed next to it.

    Origin: ARNI/HFrEF round. 24 of 24 cells agreed, which is what made the
    denominators trustworthy. That agreement was checked by hand; it is checked
    here so the first DISagreement announces itself instead of being absorbed.

    This is a verification of a read pair, not a derivation: we already have both
    numbers and are asking whether they are consistent. Tolerance allows for the
    trialists' rounding at the printed precision, plus a small slack.
    """
    out = []
    for c in cells:
        if c.printed_percent is None:
            out.append(Finding("CHK001_COUNT_PERCENT_AGREEMENT", "INFO", _sub(c),
                               "no printed percentage captured; agreement not testable"))
            continue
        if c.events is None or not c.analysed:
            continue
        implied = 100.0 * c.events / c.analysed
        # tolerance: half a unit at the printed precision, floored at 0.06pp
        decimals = _decimals(c.printed_percent)
        tol = max(0.5 * (10 ** -decimals) * 100 / 100, 0.06)
        tol = max(tol, 0.5 * (10 ** -decimals)) + 0.01
        delta = abs(implied - c.printed_percent)
        if delta <= tol:
            out.append(Finding("CHK001_COUNT_PERCENT_AGREEMENT", "PASS", _sub(c),
                               f"{c.events}/{c.analysed} = {implied:.2f}% vs printed {c.printed_percent}%"))
        else:
            out.append(Finding("CHK001_COUNT_PERCENT_AGREEMENT", "BLOCK", _sub(c),
                               f"DISAGREEMENT: {c.events}/{c.analysed} = {implied:.2f}% but source prints "
                               f"{c.printed_percent}% (delta {delta:.2f}pp, tol {tol:.2f}pp). "
                               "Either the count, the denominator, or the population label is wrong."))
    return out


def CHK002_DENOMINATOR_NOT_RANDOMISED(cells: list[Cell]) -> list[Finding]:
    """Require BOTH analysed and randomised, and a reason when they differ.

    Origin: PARADIGM-HF randomised 4209/4233 but analysed 4187/4212 (37 GCP-site
    exclusions + 6 mis-randomised). PARALLEL-HF randomised 112/113, analysed
    111/112. Two of three trials in that round. Recording only one number loses
    the distinction silently, so this fails closed when either is absent.
    """
    out = []
    for c in cells:
        if c.events is None:
            continue
        if c.analysed is None:
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "BLOCK", _sub(c),
                               "analysed denominator missing"))
            continue
        if c.randomised is None:
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "BLOCK", _sub(c),
                               "randomised total missing; cannot tell whether analysed == randomised. "
                               "Record both, even when they are equal."))
            continue
        if c.analysed == c.randomised:
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "PASS", _sub(c),
                               f"analysed == randomised == {c.analysed}"))
        elif c.analysed > c.randomised:
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "BLOCK", _sub(c),
                               f"analysed {c.analysed} > randomised {c.randomised}: impossible"))
        elif not c.denominator_reason:
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "BLOCK", _sub(c),
                               f"analysed {c.analysed} < randomised {c.randomised} with no "
                               "denominator_reason. State why participants were excluded."))
        elif c.denominator_reason.strip().upper().startswith("NOT STATED"):
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "WARN", _sub(c),
                               f"analysed {c.analysed} < randomised {c.randomised} "
                               f"({c.randomised - c.analysed} excluded) and the source does not say why: "
                               f"'{c.denominator_reason}'. Open item for primary verification — an "
                               "unexplained exclusion is not the same as an explained one."))
        else:
            out.append(Finding("CHK002_DENOMINATOR_NOT_RANDOMISED", "PASS", _sub(c),
                               f"analysed {c.analysed} of randomised {c.randomised} "
                               f"({c.randomised - c.analysed} excluded: {c.denominator_reason})"))
    return out


def CHK003_DUPLICATE_OUTCOME_POPULATION(cells: list[Cell]) -> list[Finding]:
    """Refuse to pick silently when one outcome concept has >1 arm-pair.

    Origin: PARADIGM-HF's registry posts all-cause death TWICE -- 711/835 on the
    Full Analysis Set and 714/837 on the randomised set (inside the adjudicated
    cause-of-death table). Both are 'all-cause death' for the same trial and arm.
    A silent pick mixes populations and would poison a small-study-effects test.

    Rule: duplicates are permitted, but every duplicate must carry a distinct
    population_label, and exactly one must set selected=True. An explicit boolean
    is used rather than sniffing free text -- an early version matched the
    substring 'SELECTED' and was fooled by the words 'not selected'.
    """
    out = []
    groups: dict[tuple, list[Cell]] = {}
    for c in cells:
        if c.events is None:
            continue
        groups.setdefault(c.key(), []).append(c)

    for key, grp in groups.items():
        if len(grp) == 1:
            continue
        nct, arm, outcome = key
        subject = f"{grp[0].trial}/{arm}/{outcome}"
        variants = [(g.population_label, g.events, g.analysed) for g in grp]
        labels = [g.population_label for g in grp]
        if any(l is None for l in labels):
            out.append(Finding("CHK003_DUPLICATE_OUTCOME_POPULATION", "BLOCK", subject,
                               f"{len(grp)} arm-pairs for one outcome concept, but at least one has no "
                               f"population_label. Variants: {variants}. Name the population for each."))
            continue
        if len(set(labels)) != len(labels):
            out.append(Finding("CHK003_DUPLICATE_OUTCOME_POPULATION", "BLOCK", subject,
                               f"{len(grp)} arm-pairs share a population_label: {labels}. "
                               "Two different numbers cannot describe the same population."))
            continue
        selected = [g for g in grp if g.selected is True]
        if len(selected) != 1:
            out.append(Finding("CHK003_DUPLICATE_OUTCOME_POPULATION", "BLOCK", subject,
                               f"registry/publication offers {len(grp)} arm-pairs for this outcome "
                               f"({variants}); exactly one must set selected=true with its population "
                               "named. Refusing to choose for you."))
        else:
            out.append(Finding("CHK003_DUPLICATE_OUTCOME_POPULATION", "PASS", subject,
                               f"{len(grp)} populations present, SELECTED = "
                               f"{selected[0].population_label} ({selected[0].events}/{selected[0].analysed})"))
    return out


def CHK004_PERCENTAGE_ONLY_REGISTRY(cells: list[Cell]) -> list[Finding]:
    """Flag registry postings that carry percentages but no counts, and hard-block derivation.

    Origin: PARACHUTE-HF. All four key outcomes are posted on ClinicalTrials.gov
    as 'percentage of participants' with no integer count anywhere in the results
    module. That is exactly the situation in which multiply-a-percentage creeps
    in. Counts for those cells must come from the publication.
    """
    out = []
    for c in cells:
        units = (c.registry_units or "").lower()
        pct_only = "percent" in units or "%" in units
        if not pct_only:
            continue
        if c.events is None:
            out.append(Finding("CHK004_PERCENTAGE_ONLY_REGISTRY", "INFO", _sub(c),
                               f"registry posts '{c.registry_units}' only and no count was recovered. "
                               "Publication retrieval required; derivation from the percentage is "
                               "prohibited."))
            continue
        registry_sources = [s for s in c.sources if s.get("tier") == "T2"]
        if c.provenance != "read":
            out.append(Finding("CHK004_PERCENTAGE_ONLY_REGISTRY", "BLOCK", _sub(c),
                               f"registry posts this outcome as '{c.registry_units}' (percentage-only) and "
                               f"provenance is '{c.provenance}'. A count derived from a percentage-only "
                               "posting is prohibited. Recover the integer from the publication."))
            continue
        if c.events is not None and registry_sources and len(c.sources) == len(registry_sources):
            out.append(Finding("CHK004_PERCENTAGE_ONLY_REGISTRY", "BLOCK", _sub(c),
                               f"registry posts '{c.registry_units}' only, yet an integer count is recorded "
                               "with the registry as its sole source. The registry cannot be the source of "
                               "a number it does not print."))
            continue
        out.append(Finding("CHK004_PERCENTAGE_ONLY_REGISTRY", "WARN", _sub(c),
                           f"registry posting is percentage-only ('{c.registry_units}'); count is sourced "
                           f"from {[s.get('tier') for s in c.sources if s.get('tier') != 'T2']}. "
                           "Derivation blocked, count accepted from publication."))
    return out


def CHK005_SINGLE_SOURCE_CELL(cells: list[Cell]) -> list[Finding]:
    """Mark cells confirmed by only one source, so 'N of M confirmed' means something.

    Origin: PARALLEL-HF all-cause death (19/16) exists only in the ClinicalTrials.gov
    results module -- the Circ J paper's Table 2 does not report it. Reporting
    '22 of 24 confirmed' is only honest if the other 2 are individually visible.
    """
    out = []
    for c in cells:
        if c.events is None:
            continue
        distinct = sorted({s.get("tier") for s in c.sources if s.get("tier")})
        n = len(c.sources)
        if n == 0:
            out.append(Finding("CHK005_SINGLE_SOURCE_CELL", "BLOCK", _sub(c),
                               "count recorded with no source at all"))
        elif n == 1:
            s = c.sources[0]
            out.append(Finding("CHK005_SINGLE_SOURCE_CELL", "WARN", _sub(c),
                               f"SINGLE-SOURCE cell ({distinct[0]}): {s.get('pointer')}. "
                               "Not independently confirmed; must be visibly distinguished in any "
                               "'n of m confirmed' statement."))
        else:
            out.append(Finding("CHK005_SINGLE_SOURCE_CELL", "PASS", _sub(c),
                               f"confirmed in {n} sources, tiers {distinct}"))
    return out


def CHK006_READ_NOT_COMPUTED(cells: list[Cell]) -> list[Finding]:
    """Provenance must be 'read'. Anything else is blocked."""
    out = []
    for c in cells:
        if c.events is None:
            if c.not_recovered_reason or c.obstacle:
                out.append(Finding("CHK006_READ_NOT_COMPUTED", "PASS", _sub(c),
                                   "no count recorded; reason stated"))
            else:
                out.append(Finding("CHK006_READ_NOT_COMPUTED", "BLOCK", _sub(c),
                                   "no count and no not_recovered_reason/obstacle. An empty cell must "
                                   "say why it is empty."))
            continue
        if c.provenance == "read":
            out.append(Finding("CHK006_READ_NOT_COMPUTED", "PASS", _sub(c), "read from source"))
        else:
            out.append(Finding("CHK006_READ_NOT_COMPUTED", "BLOCK", _sub(c),
                               f"provenance='{c.provenance}'. Only 'read' is admissible. Do not multiply a "
                               "percentage by a denominator and do not sum components into a composite."))
    return out


def CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS(cells: list[Cell]) -> list[Finding]:
    """A first-event composite must not equal the sum of its components.

    Origin: in all three ARNI trials the sum overstated the composite by 20-37%
    (PARADIGM-HF 558+537=1095 vs 914). If a recorded composite happens to equal
    the component sum exactly, it was almost certainly built by addition.
    """
    out = []
    by_arm: dict[tuple, dict[str, Cell]] = {}
    for c in cells:
        if c.events is None:
            continue
        by_arm.setdefault((c.nct, c.arm), {})[c.outcome] = c

    for (nct, arm), outcomes in by_arm.items():
        components = [c for c in outcomes.values() if c.is_component_of]
        if not components:
            continue
        targets: dict[str, list[Cell]] = {}
        for c in components:
            targets.setdefault(c.is_component_of, []).append(c)
        for comp_key, comps in targets.items():
            comp = outcomes.get(comp_key)
            if comp is None or len(comps) < 2:
                continue
            total = sum(c.events for c in comps)
            subject = f"{comp.trial}/{arm}/{comp_key}"
            if total == comp.events:
                out.append(Finding("CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS", "BLOCK", subject,
                                   f"composite {comp.events} equals the exact sum of its components "
                                   f"({' + '.join(str(c.events) for c in comps)} = {total}). A first-event "
                                   "composite counts each participant once; equality indicates it was "
                                   "constructed by addition."))
            elif total < comp.events:
                out.append(Finding("CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS", "BLOCK", subject,
                                   f"composite {comp.events} exceeds the component sum {total}: a first-event "
                                   "composite cannot exceed the total of its components."))
            else:
                over = 100.0 * (total - comp.events) / comp.events
                out.append(Finding("CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS", "PASS", subject,
                                   f"composite {comp.events} < component sum {total} (+{over:.0f}%), "
                                   "consistent with first-event counting"))
    return out


def CHK008_EVENTS_WITHIN_DENOMINATOR(cells: list[Cell]) -> list[Finding]:
    """Arithmetic sanity: 0 <= events <= analysed."""
    out = []
    for c in cells:
        if c.events is None or c.analysed is None:
            continue
        if c.events < 0:
            out.append(Finding("CHK008_EVENTS_WITHIN_DENOMINATOR", "BLOCK", _sub(c),
                               f"negative events {c.events}"))
        elif c.events > c.analysed:
            out.append(Finding("CHK008_EVENTS_WITHIN_DENOMINATOR", "BLOCK", _sub(c),
                               f"events {c.events} exceed analysed {c.analysed}. If this is a recurrent-event "
                               "count it is not a 2x2 cell -- see CHK012."))
        else:
            out.append(Finding("CHK008_EVENTS_WITHIN_DENOMINATOR", "PASS", _sub(c),
                               f"{c.events} <= {c.analysed}"))
    return out


def CHK009_BLOCKED_FETCH_NOT_ABSENCE(cells: list[Cell]) -> list[Finding]:
    """A retrieval failure must never be recorded as 'not reported'.

    Origin: the ClinicalTrials.gov API fetch was refused at the tool layer. The
    data existed and was reachable through the browser. Had that been logged as
    'not reported', four trials would have been silently written off.
    """
    out = []
    absence_words = ("not reported", "not available", "no data", "absent", "none found", "unavailable")
    for c in cells:
        if c.obstacle:
            if c.events is not None:
                out.append(Finding("CHK009_BLOCKED_FETCH_NOT_ABSENCE", "PASS", _sub(c),
                                   f"obstacle recorded and later overcome: {c.obstacle}"))
            else:
                out.append(Finding("CHK009_BLOCKED_FETCH_NOT_ABSENCE", "WARN", _sub(c),
                                   f"OBSTACLE, NOT ABSENCE: {c.obstacle}. This cell is unretrieved, not "
                                   "empty. Do not report it as 'no data'; escalate the fallback chain."))
            continue
        r = (c.not_recovered_reason or "").lower()
        if r and any(w in r for w in absence_words) and any(
                w in r for w in ("block", "denied", "403", "refus", "paywall", "timeout", "captcha")):
            out.append(Finding("CHK009_BLOCKED_FETCH_NOT_ABSENCE", "BLOCK", _sub(c),
                               f"not_recovered_reason conflates a retrieval failure with an absence: "
                               f"'{c.not_recovered_reason}'. Record it in `obstacle`, not as absence."))
    return out


def CHK010_IDENTIFIER_PROVENANCE(cells: list[Cell]) -> list[Finding]:
    """Registry identifiers must come from a lookup, never from recall."""
    out = []
    seen: dict[str, set] = {}
    for c in cells:
        seen.setdefault(c.nct, set()).add(c.identifier_provenance)
    for nct, provs in seen.items():
        provs = {p for p in provs if p}
        if not provs:
            out.append(Finding("CHK010_IDENTIFIER_PROVENANCE", "BLOCK", nct,
                               "no identifier_provenance recorded. State 'lookup' and how."))
        elif "recall" in provs:
            out.append(Finding("CHK010_IDENTIFIER_PROVENANCE", "BLOCK", nct,
                               "identifier sourced from recall. Resolve it by live lookup."))
        else:
            out.append(Finding("CHK010_IDENTIFIER_PROVENANCE", "PASS", nct,
                               f"identifier provenance: {sorted(provs)}"))
    return out


def CHK011_UNVERIFIED_TIER_FLAGGED(cells: list[Cell]) -> list[Finding]:
    """Prior-meta extraction tables are an unverified tier and must be flagged.

    Origin: Reyaz 2023 had both a comparator and a follow-up wrong in the single
    row that was checked.
    """
    out = []
    for c in cells:
        bad = [s for s in c.sources
               if s.get("tier") in UNVERIFIED_TIERS and not s.get("flagged_unverified")]
        if bad:
            out.append(Finding("CHK011_UNVERIFIED_TIER_FLAGGED", "BLOCK", _sub(c),
                               f"source(s) at unverified tier {[s.get('tier') for s in bad]} not marked "
                               "flagged_unverified=true. Prior meta-analysis extraction tables require "
                               "primary verification before use."))
        elif any(s.get("tier") in UNVERIFIED_TIERS for s in c.sources):
            only_t4 = all(s.get("tier") in UNVERIFIED_TIERS for s in c.sources)
            sev = "BLOCK" if only_t4 else "WARN"
            out.append(Finding("CHK011_UNVERIFIED_TIER_FLAGGED", sev, _sub(c),
                               "rests on a prior-meta extraction table"
                               + (" as its ONLY source" if only_t4 else "") +
                               "; queued for primary verification."))
    return out


def CHK012_ARM_PAIR_COMPLETE(cells: list[Cell]) -> list[Finding]:
    """Both arms of an outcome must be present, or neither is usable in a 2x2."""
    out = []
    groups: dict[tuple, list[Cell]] = {}
    for c in cells:
        groups.setdefault((c.nct, c.outcome, c.population_label), []).append(c)
    for (nct, outcome, pop), grp in groups.items():
        with_counts = [g for g in grp if g.events is not None]
        subject = f"{grp[0].trial}/{outcome}/{pop}"
        if len(with_counts) == 0:
            continue
        if len(with_counts) == 1:
            out.append(Finding("CHK012_ARM_PAIR_COMPLETE", "BLOCK", subject,
                               f"only one arm has a count ({with_counts[0].arm}). A 2x2 needs both arms "
                               "at the same population."))
        elif len(with_counts) > 2:
            out.append(Finding("CHK012_ARM_PAIR_COMPLETE", "WARN", subject,
                               f"{len(with_counts)} arms present; confirm which two form the comparison."))
        else:
            out.append(Finding("CHK012_ARM_PAIR_COMPLETE", "PASS", subject, "both arms present"))
    return out


def CHK013_AE_MODULE_DEATHS_NOT_EFFICACY(cells: list[Cell]) -> list[Finding]:
    """The registry adverse-events module's death count is not the efficacy endpoint.

    Origin: cardiology-atlas sweep, 2026-08-12. ClinicalTrials.gov requires an
    all-cause death count in the adverse-events module, which makes it a tempting
    universal source -- it is posted even when the efficacy outcomes are
    percentage-only. It answers a different question: safety population, and the
    adverse-event collection window rather than the efficacy follow-up.

    Measured divergence in this sweep:
        ODYSSEY OUTCOMES  AE 238/278   vs efficacy 334/392   (~100 events out)
        EMPA-KIDNEY       AE 314/353   vs efficacy 148/167   (>2x)
        DAPA-HF           AE 286/333   vs efficacy 276/329
        PARAGON-HF        AE 347/357   vs efficacy 342/349
        SPRINT            AE 155/210   vs efficacy 155/210   (identical)
        DECLARE-TIMI 58   AE 529/570   vs efficacy 529/570   (identical)

    Sometimes identical, sometimes double. Never safe to substitute silently.
    """
    out = []
    ae_markers = ("adverse event", "ae module", "adverseevents", "safety population",
                  "treatment-emergent", "deathsnumaffected")
    for c in cells:
        if c.events is None:
            continue
        pointers = " ".join(str(s.get("pointer", "")).lower() for s in c.sources)
        pop = (c.population_label or "").lower()
        looks_ae = any(k in pointers for k in ae_markers) or any(k in pop for k in ae_markers)
        if not looks_ae:
            continue
        if "death" not in c.outcome and "mortalit" not in c.outcome:
            continue
        if c.selected is False:
            out.append(Finding("CHK013_AE_MODULE_DEATHS_NOT_EFFICACY", "PASS", _sub(c),
                               "adverse-events-module death count recorded but not selected"))
        else:
            out.append(Finding("CHK013_AE_MODULE_DEATHS_NOT_EFFICACY", "BLOCK", _sub(c),
                               "this count comes from the registry adverse-events module (safety "
                               "population, AE collection window) and is being used as the efficacy "
                               "all-cause mortality endpoint. Observed divergence from the efficacy "
                               "outcome ranges from 0 to >2x. Recover the efficacy endpoint, or set "
                               "selected=false and label the population."))
    return out


def CHK014_EFFECT_ESTIMATE_CONSISTENCY(cells: list[Cell]) -> list[Finding]:
    """Recovered counts should reproduce the stored effect estimate -- necessary, not sufficient.

    Compares the crude risk ratio implied by the recovered 2x2 against a stored
    hazard ratio, when the caller supplies one in notes as 'stored_hr=<x>'.

    IMPORTANT LIMITATION, established empirically. For ODYSSEY OUTCOMES the
    adverse-events count (238/278, RR 0.856) and the efficacy count (334/392,
    RR 0.852) BOTH reproduce the stored HR of 0.85, yet differ by about 100
    events per arm. Agreement here therefore cannot be used to authenticate a
    count. Disagreement is informative; agreement is not. This check emits WARN
    on disagreement and INFO on agreement, and never PASSes a cell on its own.
    """
    out = []
    pairs: dict[tuple, list[Cell]] = {}
    for c in cells:
        if c.events is None or not c.analysed:
            continue
        pairs.setdefault((c.nct, c.outcome, c.population_label), []).append(c)
    for key, grp in pairs.items():
        if len(grp) != 2:
            continue
        stored = None
        for c in grp:
            for tok in (c.notes or "").split():
                if tok.startswith("stored_hr="):
                    try:
                        stored = float(tok.split("=", 1)[1])
                    except ValueError:
                        pass
        if stored is None:
            continue
        a, b = grp
        # orient: treatment arm is the one whose notes mark it, else first
        t = next((c for c in grp if "arm_role=treatment" in (c.notes or "")), a)
        ctl = b if t is a else a
        rr = (t.events / t.analysed) / (ctl.events / ctl.analysed) if ctl.events else None
        subject = f"{t.trial}/{t.outcome}/{t.population_label}"
        if rr is None:
            continue
        rel = abs(rr - stored) / stored
        if rel <= 0.08:
            out.append(Finding("CHK014_EFFECT_ESTIMATE_CONSISTENCY", "INFO", subject,
                               f"implied RR {rr:.3f} vs stored HR {stored:.3f} ({rel*100:.1f}% apart). "
                               "Consistent — but consistency does NOT authenticate the count "
                               "(see ODYSSEY OUTCOMES in the docstring)."))
        else:
            out.append(Finding("CHK014_EFFECT_ESTIMATE_CONSISTENCY", "WARN", subject,
                               f"implied RR {rr:.3f} vs stored HR {stored:.3f} ({rel*100:.1f}% apart). "
                               "Likely the wrong outcome, population, or follow-up window."))
    return out


CHECKS = [
    CHK001_COUNT_PERCENT_AGREEMENT,
    CHK002_DENOMINATOR_NOT_RANDOMISED,
    CHK003_DUPLICATE_OUTCOME_POPULATION,
    CHK004_PERCENTAGE_ONLY_REGISTRY,
    CHK005_SINGLE_SOURCE_CELL,
    CHK006_READ_NOT_COMPUTED,
    CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS,
    CHK008_EVENTS_WITHIN_DENOMINATOR,
    CHK009_BLOCKED_FETCH_NOT_ABSENCE,
    CHK010_IDENTIFIER_PROVENANCE,
    CHK011_UNVERIFIED_TIER_FLAGGED,
    CHK012_ARM_PAIR_COMPLETE,
    CHK013_AE_MODULE_DEATHS_NOT_EFFICACY,
    CHK014_EFFECT_ESTIMATE_CONSISTENCY,
]


# --------------------------------------------------------------------------
# Retrieval fallback chain (procedure encoded, not prose)
# --------------------------------------------------------------------------

REGISTRY_FALLBACK_CHAIN = [
    ("web_fetch_api",
     "mcp web_fetch of https://clinicaltrials.gov/api/v2/studies/<NCT>?fields=ResultsSection",
     "Fastest when permitted. KNOWN TO BE REFUSED AT THE TOOL LAYER in this environment "
     "(observed 2026-08-12). Refusal is an obstacle, not an absence -- fall through."),
    ("chrome_same_origin_fetch",
     "Chrome: navigate to https://clinicaltrials.gov/study/<NCT>?tab=results, then run "
     "fetch('/api/v2/studies/<NCT>?fields=ResultsSection') from the page context",
     "WORKS. Same-origin so no CORS; returns the full structured results module. "
     "This is the default path. Slice the JSON in-page; do not return the whole blob."),
    ("chrome_page_text",
     "Chrome: get_page_text on the ?tab=results page",
     "Fallback if the API shape changes. Registry results tables are JS-rendered, so a raw "
     "HTML fetch returns an empty shell -- the browser is required."),
    ("publication_pmc",
     "PubMed -> PMC full text -> read the outcomes table",
     "Required whenever the registry posts percentages only (see CHK004)."),
    ("publication_publisher",
     "Publisher site via Chrome (nejm.org, jstage, ahajournals ...)",
     "Abstract Results paragraphs frequently carry the per-arm counts even when the tables "
     "are paywalled."),
    ("regulatory",
     "FDA statistical review / EMA EPAR",
     "Use when trial predates registry results posting or the publication omits the outcome."),
]

CHROME_JS_TEMPLATE = r"""
// Run from a clinicaltrials.gov page (same-origin). Returns compact lines, not a JSON blob.
// Two output hygiene rules learned the hard way:
//   * strip URL-like tokens -- the tool layer rejects payloads containing query strings
//   * never return the whole results module; it exceeds the token cap
const NCT = '%%NCT%%';
const r = await fetch('/api/v2/studies/' + NCT + '?fields=ResultsSection').then(x => x.json());
const rs = r.resultsSection;
const clean = s => String(s).replace(/[^A-Za-z0-9 .,%()\/\n:;+\-\[\]]/g, ' ').replace(/\S*=\S*/g, ' ');
const L = [];
const pf = rs.participantFlowModule;
pf.groups.forEach(g => L.push('FLOWGRP ' + g.id + ' -> ' + g.title));
pf.periods.forEach(p => p.milestones.forEach(m =>
  L.push('MILESTONE ' + m.type + ' :: ' + m.achievements.map(a => a.groupId + ' -> ' + a.numSubjects).join(' | '))));
rs.outcomeMeasuresModule.outcomeMeasures.forEach((o, i) =>
  L.push('OUTCOME ' + i + ' | ' + o.type + ' | ' + o.unitOfMeasure + ' | ' + o.title));
clean(L.join('\n'));
"""


def fetch_registry_results(nct: str, transport=None) -> dict:
    """Walk the fallback chain. Never returns None on failure -- raises BlockedFetch.

    `transport` is a callable (strategy_name, nct) -> dict | None, supplied by the
    caller (an agent driving Chrome, a cached fixture, a test double). The harness
    owns the ORDER and the failure semantics; the caller owns the mechanism.
    """
    tried = []
    if transport is None:
        raise BlockedFetch(nct, "no transport supplied", tried)
    last = None
    for name, how, _why in REGISTRY_FALLBACK_CHAIN:
        tried.append(name)
        try:
            got = transport(name, nct)
        except Exception as exc:  # transport-level failure -> try next strategy
            last = f"{name}: {exc}"
            continue
        if got:
            return got
        last = f"{name}: returned empty"
    raise BlockedFetch(nct, f"all strategies exhausted (last: {last})", tried)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def _sub(c: Cell) -> str:
    return f"{c.trial}/{c.arm}/{c.outcome}"


def _decimals(x: float) -> int:
    s = repr(float(x))
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def run_checks(cells: list[Cell]) -> list[Finding]:
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check(cells))
    return findings


def summarise(cells: list[Cell], findings: list[Finding]) -> dict:
    blocks = [f for f in findings if f.severity == "BLOCK"]
    warns = [f for f in findings if f.severity == "WARN"]
    # Deliverable cells exclude alternate populations that were explicitly not
    # selected -- they are recorded so the duplicate is visible (CHK003), but they
    # are not part of the extraction and must not dilute the confirmation rate.
    deliverable = [c for c in cells if c.selected is not False]
    alternates = [c for c in cells if c.selected is False]
    filled = [c for c in deliverable if c.events is not None]
    single = [c for c in filled if len(c.sources) == 1]
    multi = [c for c in filled if len(c.sources) > 1]
    obstacles = [c for c in deliverable if c.obstacle and c.events is None]
    return {
        "harness_version": __version__,
        "cells_total": len(deliverable),
        "alternate_population_rows": len(alternates),
        "cells_with_counts": len(filled),
        "cells_empty": len(deliverable) - len(filled),
        "cells_multi_source": len(multi),
        "cells_single_source": len(single),
        "cells_unretrieved_obstacle": len(obstacles),
        "checks_run": len(CHECKS),
        "findings_total": len(findings),
        "blocks": len(blocks),
        "warns": len(warns),
        "verdict": "BLOCKED" if blocks else ("PASS_WITH_WARNINGS" if warns else "CLEAN"),
    }


def render_report(cells: list[Cell], findings: list[Finding], summary: dict) -> str:
    lines = [f"# Count-extraction harness report (v{__version__})", ""]
    lines.append(f"**Verdict: {summary['verdict']}** — "
                 f"{summary['blocks']} BLOCK, {summary['warns']} WARN "
                 f"across {summary['checks_run']} checks on {summary['cells_total']} cells.")
    lines.append("")
    lines.append(f"- cells with counts: **{summary['cells_with_counts']}** / {summary['cells_total']}")
    lines.append(f"- independently confirmed (>=2 sources): **{summary['cells_multi_source']}**")
    lines.append(f"- single-source: **{summary['cells_single_source']}**")
    lines.append(f"- unretrieved due to an obstacle (NOT absence): **{summary['cells_unretrieved_obstacle']}**")
    lines.append("")
    for sev in ("BLOCK", "WARN", "INFO"):
        sel = [f for f in findings if f.severity == sev]
        if not sel:
            continue
        lines.append(f"## {sev} ({len(sel)})")
        lines.append("")
        for f in sel:
            lines.append(f"- `{f.check}` — **{f.subject}** — {f.message}")
        lines.append("")
    passes: dict[str, int] = {}
    for f in findings:
        if f.severity == "PASS":
            passes[f.check] = passes.get(f.check, 0) + 1
    if passes:
        lines.append("## PASS counts by check")
        lines.append("")
        for k in sorted(passes):
            lines.append(f"- `{k}`: {passes[k]}")
        lines.append("")
    return "\n".join(lines)


def load_cells(path: str) -> list[Cell]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    rows = raw["cells"] if isinstance(raw, dict) and "cells" in raw else raw
    valid = {f for f in Cell.__dataclass_fields__}
    out = []
    for r in rows:
        unknown = set(r) - valid
        if unknown:
            raise ValueError(f"unknown field(s) {sorted(unknown)} in row {r.get('trial')}/{r.get('outcome')}")
        out.append(Cell(**r))
    return out


# --------------------------------------------------------------------------
# Self-test: the ARNI/HFrEF round, including the traps it actually contained
# --------------------------------------------------------------------------

def _selftest_cells() -> list[Cell]:
    NEJM = {"tier": "T1", "pointer": "NEJM 2014;371:993-1004 Results text",
            "url": "https://doi.org/10.1056/NEJMoa1409077"}
    CTG1 = {"tier": "T2", "pointer": "CT.gov NCT01035255 results, Outcome 1",
            "url": "https://clinicaltrials.gov/study/NCT01035255"}
    CTG1b = {"tier": "T2", "pointer": "CT.gov NCT01035255 results, Outcome 2 (all-cause mortality)",
             "url": "https://clinicaltrials.gov/study/NCT01035255"}
    CTG1c = {"tier": "T2", "pointer": "CT.gov NCT01035255 results, Outcome 3 (adjudicated causes of death)",
             "url": "https://clinicaltrials.gov/study/NCT01035255"}
    base = dict(trial="PARADIGM-HF", nct="NCT01035255", identifier_provenance="lookup",
                registry_units="participants")
    cells = [
        Cell(**base, arm="sacubitril/valsartan", outcome="composite_cvdeath_or_first_hfhosp",
             events=914, analysed=4187, randomised=4209, population_label="FAS",
             denominator_reason="37 at GCP-closed sites + 6 mis-randomised (trial-wide)",
             printed_percent=21.8, sources=[NEJM, CTG1]),
        Cell(**base, arm="enalapril", outcome="composite_cvdeath_or_first_hfhosp",
             events=1117, analysed=4212, randomised=4233, population_label="FAS",
             denominator_reason="37 at GCP-closed sites + 6 mis-randomised (trial-wide)",
             printed_percent=26.5, sources=[NEJM, CTG1]),
        Cell(**base, arm="sacubitril/valsartan", outcome="cv_death", events=558, analysed=4187,
             randomised=4209, population_label="FAS", denominator_reason="as above",
             printed_percent=13.3, sources=[NEJM, CTG1],
             is_component_of="composite_cvdeath_or_first_hfhosp"),
        Cell(**base, arm="enalapril", outcome="cv_death", events=693, analysed=4212,
             randomised=4233, population_label="FAS", denominator_reason="as above",
             printed_percent=16.5, sources=[NEJM, CTG1],
             is_component_of="composite_cvdeath_or_first_hfhosp"),
        Cell(**base, arm="sacubitril/valsartan", outcome="first_hf_hosp", events=537, analysed=4187,
             randomised=4209, population_label="FAS", denominator_reason="as above",
             printed_percent=12.8, sources=[NEJM, CTG1],
             is_component_of="composite_cvdeath_or_first_hfhosp"),
        Cell(**base, arm="enalapril", outcome="first_hf_hosp", events=658, analysed=4212,
             randomised=4233, population_label="FAS", denominator_reason="as above",
             printed_percent=15.6, sources=[NEJM, CTG1],
             is_component_of="composite_cvdeath_or_first_hfhosp"),
        # the duplicate-population trap, both variants present and one SELECTED
        Cell(**base, arm="sacubitril/valsartan", outcome="all_cause_death", events=711, analysed=4187,
             randomised=4209, population_label="FAS", denominator_reason="as above",
             printed_percent=17.0, sources=[NEJM, CTG1b], selected=True,
             notes="FAS population; matches NEJM Results text"),
        Cell(**base, arm="enalapril", outcome="all_cause_death", events=835, analysed=4212,
             randomised=4233, population_label="FAS", denominator_reason="as above",
             printed_percent=19.8, sources=[NEJM, CTG1b], selected=True,
             notes="FAS population; matches NEJM Results text"),
        Cell(**base, arm="sacubitril/valsartan", outcome="all_cause_death", events=714, analysed=4209,
             randomised=4209, population_label="randomised",
             sources=[CTG1c], selected=False,
             notes="alternate population, recorded so the duplicate is visible"),
        Cell(**base, arm="enalapril", outcome="all_cause_death", events=837, analysed=4233,
             randomised=4233, population_label="randomised",
             sources=[CTG1c], selected=False,
             notes="alternate population, recorded so the duplicate is visible"),
    ]
    # PARACHUTE-HF: percentage-only registry, counts from JAMA
    JAMA = {"tier": "T1", "pointer": "JAMA 2026;335(1):49-59 Table 2",
            "url": "https://doi.org/10.1001/jama.2025.19808"}
    CTG2 = {"tier": "T2", "pointer": "CT.gov NCT04023227 results (percentage-only)",
            "url": "https://clinicaltrials.gov/study/NCT04023227"}
    pbase = dict(trial="PARACHUTE-HF", nct="NCT04023227", identifier_provenance="lookup",
                 registry_units="percentage of participants", population_label="FAS",
                 randomised=None)
    for arm, comp, cvd, hosp, pcts in (
            ("sacubitril/valsartan", 155, 110, 102, (33.5, 23.8, 22.1)),
            ("enalapril", 169, 117, 111, (36.7, 25.4, 24.1))):
        n = 462 if arm.startswith("sacu") else 460
        d = dict(pbase); d["randomised"] = n
        cells += [
            Cell(**d, arm=arm, outcome="composite_cvdeath_or_first_hfhosp", events=comp,
                 analysed=n, printed_percent=pcts[0], sources=[JAMA, CTG2]),
            Cell(**d, arm=arm, outcome="cv_death", events=cvd, analysed=n,
                 printed_percent=pcts[1], sources=[JAMA, CTG2],
                 is_component_of="composite_cvdeath_or_first_hfhosp"),
            Cell(**d, arm=arm, outcome="first_hf_hosp", events=hosp, analysed=n,
                 printed_percent=pcts[2], sources=[JAMA, CTG2],
                 is_component_of="composite_cvdeath_or_first_hfhosp"),
        ]
    # PARALLEL-HF: the single-source all-cause-death cells
    CIRCJ = {"tier": "T1", "pointer": "Circ J 2021;85(5):584-594 Table 2",
             "url": "https://doi.org/10.1253/circj.CJ-20-0854"}
    CTG3 = {"tier": "T2", "pointer": "CT.gov NCT02468232 results, Outcome 10",
            "url": "https://clinicaltrials.gov/study/NCT02468232"}
    for arm, n, rnd, comp, cvd, hosp, acm, pcts in (
            ("sacubitril/valsartan", 111, 112, 30, 13, 25, 19, (27.0, 11.7, 22.5)),
            ("enalapril", 112, 113, 28, 11, 20, 16, (25.0, 9.8, 17.9))):
        lb = dict(trial="PARALLEL-HF", nct="NCT02468232", identifier_provenance="lookup",
                  registry_units="participants", population_label="FAS", arm=arm,
                  analysed=n, randomised=rnd, denominator_reason="1 mis-randomised per arm")
        cells += [
            Cell(**lb, outcome="composite_cvdeath_or_first_hfhosp", events=comp,
                 printed_percent=pcts[0], sources=[CIRCJ, CTG3]),
            Cell(**lb, outcome="cv_death", events=cvd, printed_percent=pcts[1],
                 sources=[CIRCJ, CTG3], is_component_of="composite_cvdeath_or_first_hfhosp"),
            Cell(**lb, outcome="first_hf_hosp", events=hosp, printed_percent=pcts[2],
                 sources=[CIRCJ, CTG3], is_component_of="composite_cvdeath_or_first_hfhosp"),
            Cell(**lb, outcome="all_cause_death", events=acm, sources=[CTG3],
                 notes="registry-only; Circ J Table 2 does not report all-cause mortality"),
        ]
    return cells


def _selftest() -> int:
    print(f"count_recovery_harness v{__version__} — self-test on the ARNI/HFrEF round\n")
    cells = _selftest_cells()
    findings = run_checks(cells)
    summary = summarise(cells, findings)
    for f in findings:
        if f.severity in ("BLOCK", "WARN"):
            print(f.line())
    print()
    print(json.dumps(summary, indent=2))

    ok = True
    if summary["blocks"]:
        print("\nFAIL: clean input produced BLOCKs")
        ok = False

    # negative controls: each trap must actually be caught
    print("\n--- negative controls ---")

    def expect(name, mutate, check_name):
        muts = _selftest_cells()
        mutate(muts)
        fs = [f for f in run_checks(muts) if f.severity == "BLOCK" and f.check == check_name]
        status = "caught" if fs else "MISSED"
        print(f"  {status:7} {name} -> {check_name}")
        return bool(fs)

    ok &= expect("count contradicts printed percentage",
                 lambda cs: setattr(cs[0], "events", 814),
                 "CHK001_COUNT_PERCENT_AGREEMENT")
    ok &= expect("randomised total omitted",
                 lambda cs: setattr(cs[0], "randomised", None),
                 "CHK002_DENOMINATOR_NOT_RANDOMISED")
    ok &= expect("duplicate population, none selected",
                 lambda cs: setattr(cs[6], "selected", None),
                 "CHK003_DUPLICATE_OUTCOME_POPULATION")
    ok &= expect("duplicate population, both selected",
                 lambda cs: setattr(cs[8], "selected", True),
                 "CHK003_DUPLICATE_OUTCOME_POPULATION")
    ok &= expect("count derived from a percentage-only registry posting",
                 lambda cs: [setattr(c, "provenance", "derived")
                             for c in cs if c.trial == "PARACHUTE-HF" and c.outcome == "cv_death"],
                 "CHK004_PERCENTAGE_ONLY_REGISTRY")
    ok &= expect("composite equals sum of components",
                 lambda cs: setattr(cs[0], "events", 558 + 537),
                 "CHK007_COMPOSITE_NOT_SUM_OF_COMPONENTS")
    ok &= expect("blocked fetch logged as absence",
                 lambda cs: (setattr(cs[0], "events", None),
                             setattr(cs[0], "not_recovered_reason",
                                     "not reported - fetch was blocked with 403")),
                 "CHK009_BLOCKED_FETCH_NOT_ABSENCE")
    ok &= expect("identifier from recall",
                 lambda cs: setattr(cs[0], "identifier_provenance", "recall"),
                 "CHK010_IDENTIFIER_PROVENANCE")
    ok &= expect("unflagged prior-meta source",
                 lambda cs: cs[0].sources.append({"tier": "T4", "pointer": "Reyaz 2023 Table 1"}),
                 "CHK011_UNVERIFIED_TIER_FLAGGED")
    def _add_ae_cell(cs, selected):
        for arm, ev, n in (("sacubitril/valsartan", 347, 2419), ("enalapril", 357, 2402)):
            cs.append(Cell(trial="PARAGON-HF", nct="NCT01920711", arm=arm,
                           outcome="all_cause_death", events=ev, analysed=n, randomised=n,
                           population_label="safety population (adverse events module)",
                           identifier_provenance="lookup", selected=selected,
                           sources=[{"tier": "T2",
                                     "pointer": "CT.gov adverseEventsModule deathsNumAffected"}]))

    ok &= expect("adverse-events death count used as the efficacy endpoint",
                 lambda cs: _add_ae_cell(cs, True),
                 "CHK013_AE_MODULE_DEATHS_NOT_EFFICACY")
    ok &= expect("one arm missing",
                 lambda cs: setattr(cs[1], "events", None) or setattr(
                     cs[1], "not_recovered_reason", "left blank on purpose"),
                 "CHK012_ARM_PAIR_COMPLETE")

    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("extraction", nargs="?", help="JSON file with a list of cells")
    p.add_argument("--report", help="write a markdown report here")
    p.add_argument("--json", dest="json_out", help="write machine-readable findings here")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--chain", action="store_true", help="print the registry fetch fallback chain")
    a = p.parse_args(argv)

    if a.chain:
        print("Registry retrieval fallback chain (in order):\n")
        for i, (name, how, why) in enumerate(REGISTRY_FALLBACK_CHAIN, 1):
            print(f"{i}. {name}\n   how: {how}\n   why: {why}\n")
        print("A failure at any step is an OBSTACLE, recorded in Cell.obstacle, and is never")
        print("recorded as an absence of data. Exhausting the chain raises BlockedFetch.")
        return 0
    if a.selftest:
        return _selftest()
    if not a.extraction:
        p.print_help()
        return 2

    try:
        cells = load_cells(a.extraction)
    except Exception as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return 2

    findings = run_checks(cells)
    summary = summarise(cells, findings)
    report = render_report(cells, findings, summary)

    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(report)
    else:
        print(report)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump({"summary": summary, "findings": [asdict(f) for f in findings]}, fh, indent=2)

    print(f"\n{summary['verdict']}: {summary['blocks']} BLOCK / {summary['warns']} WARN "
          f"on {summary['cells_total']} cells", file=sys.stderr)
    return 1 if summary["blocks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
