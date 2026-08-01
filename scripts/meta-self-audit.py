#!/usr/bin/env python3
"""meta-self-audit.py -- point it at your own meta-analysis dashboard.

Offline. Standard library only. No API key, no model call, no network. It reads
one self-contained HTML file (the kind `rapidmeta-kit`'s `clone.py` or
`trialforge`'s `run.py` produce) and looks for the error classes catalogued in
`docs/META-ERROR-LIBRARY.md` -- every one of which was found in a real published
or generated meta-analysis, not invented for this script.

    python scripts/meta-self-audit.py MY_REVIEW.html
    python scripts/meta-self-audit.py MY_REVIEW.html --json
    python scripts/meta-self-audit.py MY_REVIEW.html --metamorphic probe.py

Verdicts (see `verdict()`):

    CLEAN          every applicable detector ran and found nothing
    DEFECTS-FOUND  at least one detector fired
    INCONCLUSIVE   a detector could not establish the facts it needs

There is deliberately no verdict called "PASSED". A detector that cannot see the
data it needs returns INCONCLUSIVE and the process exits non-zero, because the
failure this whole layer exists to prevent is a green badge over a number nobody
checked. INCONCLUSIVE is not a pass; neither is a SKIPped witness.

Exit codes: 0 CLEAN | 1 DEFECTS-FOUND | 2 INCONCLUSIVE | 3 usage / unreadable file.

What it cannot do is in `docs/META-ERROR-LIBRARY.md` under "Blind spots of these
detectors". Read that before you trust a CLEAN.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from itertools import combinations
from pathlib import Path

# --------------------------------------------------------------------------
# Severity ordering. Matches the grouping in docs/META-ERROR-LIBRARY.md so the
# doc and the code cannot drift into disagreeing about how bad something is.
# --------------------------------------------------------------------------
CRITICAL = "critical"   # the headline number is wrong or unsupported
HIGH = "high"           # a reported claim is not entitled to its confidence
MEDIUM = "medium"       # misleading framing; the number may survive

SEVERITY_ORDER = {CRITICAL: 0, HIGH: 1, MEDIUM: 2}

# Detector run states. `INCONCLUSIVE` exists so that "I could not check this"
# is never silently folded into "this is fine".
FIRED = "fired"
CLEAN_ = "clean"
NOT_APPLICABLE = "not-applicable"
INCONCLUSIVE_ = "inconclusive"

# Subset-sum search budget for MEL-03. Bounded on purpose: an unbounded search
# on a 90-trial table does not finish, and a detector that times out silently is
# worse than one that says so. Hitting the budget yields INCONCLUSIVE.
SUBSET_MAX_ROWS = 60
SUBSET_MAX_SIZE = 5
SUBSET_COMBO_BUDGET = 2_000_000


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------
@dataclass
class Finding:
    code: str
    severity: str
    title: str
    evidence: str
    fix: str


@dataclass
class DetectorReport:
    code: str
    name: str
    severity: str
    status: str
    detail: str = ""
    findings: list[Finding] = field(default_factory=list)


# --------------------------------------------------------------------------
# Document model
# --------------------------------------------------------------------------
class _Extractor(HTMLParser):
    """Pull visible text, script bodies, tables and badge-ish elements apart.

    We need all four views. Prose checks want text with tags gone; the
    prespecified-path and hardcoded-badge checks want the script source that the
    text view deliberately drops; the double-count check wants table structure.
    """

    _SKIP_TEXT_IN = {"script", "style"}
    # Elements that plausibly carry a status badge. Kept broad; the badge checks
    # filter on the text content, not on the tag.
    _BADGE_TAGS = {"span", "div", "p", "strong", "b", "td", "th", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.scripts: list[str] = []
        self.tables: list[list[list[str]]] = []
        # (tag, attrs-dict, inner-text) for anything that could be a badge
        self.elements: list[tuple[str, dict, str]] = []

        self._tag_stack: list[str] = []
        self._in_script = False
        self._table_stack: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._elem_stack: list[tuple[str, dict, list[str]]] = []

    # -- structure -------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self._tag_stack.append(tag)
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if tag == "script":
            self._in_script = True
            self._script_buf: list[str] = []
        elif tag == "table":
            self._table_stack.append([])
        elif tag == "tr" and self._table_stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

        if tag in self._BADGE_TAGS:
            self._elem_stack.append((tag, attr_map, []))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "script":
            self._in_script = False
            self.scripts.append("".join(getattr(self, "_script_buf", [])))
            self._script_buf = []
        elif tag == "table" and self._table_stack:
            self.tables.append(self._table_stack.pop())
        elif tag == "tr" and self._table_stack and self._row is not None:
            self._table_stack[-1].append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None

        if tag in self._BADGE_TAGS and self._elem_stack:
            # Unwind to the most recent matching open tag; malformed HTML in the
            # wild is common enough that a strict match would drop everything.
            for i in range(len(self._elem_stack) - 1, -1, -1):
                if self._elem_stack[i][0] == tag:
                    etag, eattrs, buf = self._elem_stack.pop(i)
                    self.elements.append((etag, eattrs, " ".join("".join(buf).split())))
                    break

        if self._tag_stack:
            for i in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[i] == tag:
                    del self._tag_stack[i:]
                    break

    def handle_data(self, data):
        if self._in_script:
            self._script_buf.append(data)
            return
        if any(t in self._SKIP_TEXT_IN for t in self._tag_stack):
            return
        self.text_parts.append(data)
        if self._cell is not None:
            self._cell.append(data)
        for _, _, buf in self._elem_stack:
            buf.append(data)


class Dashboard:
    """Four views of one self-contained HTML meta-analysis report."""

    def __init__(self, path: Path, raw: str) -> None:
        self.path = path
        self.raw = raw
        ex = _Extractor()
        try:
            ex.feed(raw)
            ex.close()
        except Exception:  # noqa: BLE001 - a malformed page must still be auditable
            pass
        self.text = " ".join(" ".join(ex.text_parts).split())
        self.lower = self.text.lower()
        self.scripts = ex.scripts
        self.script_src = "\n".join(ex.scripts)
        self.tables = ex.tables
        self.elements = ex.elements

    def has(self, *needles: str) -> bool:
        return any(n.lower() in self.lower for n in needles)

    def windows(self, needle: str, before: int = 160, after: int = 160) -> list[str]:
        """Text windows around each occurrence of `needle` (case-insensitive)."""
        out, start = [], 0
        low = self.lower
        n = needle.lower()
        while True:
            i = low.find(n, start)
            if i < 0:
                return out
            out.append(self.text[max(0, i - before): i + len(n) + after])
            start = i + len(n)


# --------------------------------------------------------------------------
# Shared parsing helpers
# --------------------------------------------------------------------------
NUM = r"-?\d+(?:\.\d+)?"

# point (lo to hi) / point [lo, hi] / point (95% CI lo-hi) / point (CrI lo;hi)
_EST_CI = re.compile(
    rf"(?P<point>{NUM})\s*"
    r"[\(\[]\s*"
    r"(?:95\s*%\s*)?(?:CI|CrI|C\.I\.|confidence interval|credible interval)?\s*[:=]?\s*"
    rf"(?P<lo>{NUM})\s*(?:to|;|,|–|—|\bto\b|-)\s*(?P<hi>{NUM})"
    r"\s*[\)\]]",
    re.IGNORECASE,
)

# Ratio-measure detection. Two patterns, deliberately.
#
# The spelled-out names are safe case-insensitively. The abbreviations are NOT:
# a naive `"irr" in text` matches "mirror" and "irregular", and a bare `\bOR\b`
# matches the English word "or". Both produced false positives on real corpus
# dashboards. So abbreviations must be UPPERCASE and adjacent to a number, an
# equals sign or an opening paren -- i.e. actually being used as a measure.
_RATIO_SPELLED = re.compile(
    r"\b(?:risk ratio|rate ratio|odds ratio|hazard ratio|incidence rate ratio|relative risk)\b",
    re.IGNORECASE,
)
_RATIO_ABBREV = re.compile(
    r"(?:\(\s*a?(?:RR|OR|HR|IRR)\b)|(?:\ba?(?:RR|OR|HR|IRR)\s*[=:]\s*-?\d)|(?:\ba?(?:RR|OR|HR|IRR)\s+-?\d)"
)


def ratio_measure_in(text: str) -> str | None:
    """The ratio measure named in `text`, or None. See the note above."""
    m = _RATIO_SPELLED.search(text)
    if m:
        return m.group(0)
    m = _RATIO_ABBREV.search(text)
    return m.group(0).strip("( ") if m else None

# Units that can only belong to a continuous outcome. A pooled RR/OR/HR carrying
# any of these in its own label is class MEL-01 -- the estimand and the measure
# disagree. `%` is deliberately absent: "% of patients" is a legitimate binary
# proportion, so it produces false positives.
CONTINUOUS_UNITS = (
    "mmhg", "mm hg", "kg/m2", "kg/m²", "ml/min", "mmol/l", "mg/dl", "g/dl",
    "µmol/l", "umol/l", "ng/ml", "pg/ml", "beats/min", "l/min",
    "pbac", "hba1c", "egfr slope", "ml/min/1.73",
    "points", "score", "-item scale", "vas", "sf-36", "eq-5d", "fev1", "6mwd",
    "six-minute walk", "change from baseline in",
)

RATIO_ONLY_MACHINERY = (
    ("number needed to treat", "NNT"),
    ("nnt", "NNT"),
    ("fragility index", "fragility index"),
    ("l'abb", "L'Abbe plot"),
    ("labbe", "L'Abbe plot"),
    ("trial sequential analysis", "TSA"),
)

HARM_TERMS = (
    "adverse event", "adverse events", "adverse reaction", "safety outcome",
    "serious adverse", "harms", "side effect", "toxicity", "mortality from treatment",
    "treatment-emergent", "teae", "sae",
)
EFFICACY_SIGNALS = ("primary outcome", "primary endpoint", "efficacy", "pooled estimate",
                    "forest plot", "pooled effect")

# Strings that only ever appear in a generated dashboard because a donor
# template leaked through. Sourced from the RapidMeta corpus fix log: every one
# of these was found in a shipped file describing the wrong drug or disease.
TEMPLATE_CONTAMINATION = (
    "non-steroidal mra", "across ckd trials", "finerenone", "colchicine",
    "app_slug", "{{", "}}", "replace_me", "__placeholder__", "lorem ipsum",
    "[object object]", "undefined participants", "none participants",
    "none trials", "nan trials", "n participants", "todo:",
)


def _iter_estimates(text: str):
    """Yield (point, lo, hi, matched-string) for every estimate-with-interval."""
    for m in _EST_CI.finditer(text):
        try:
            point = float(m.group("point"))
            lo = float(m.group("lo"))
            hi = float(m.group("hi"))
        except (TypeError, ValueError):
            continue
        # A bare-hyphen separator between a negative lo and hi is ambiguous
        # ("-0.5-0.2" could be one number). Drop those rather than guess.
        if "-" in m.group(0)[len(m.group("point")):] and lo < 0 and "to" not in m.group(0).lower():
            if not re.search(r"(?:to|;|,|–|—)", m.group(0)):
                continue
        yield point, lo, hi, " ".join(m.group(0).split())


def _ints_near(text: str, *labels: str, window: int = 90) -> list[int]:
    """Integers appearing within `window` chars of any of `labels`."""
    out = []
    low = text.lower()
    for label in labels:
        for m in re.finditer(re.escape(label.lower()), low):
            seg = text[m.start(): m.end() + window]
            for num in re.findall(r"\b(\d[\d,]{0,8})\b", seg):
                try:
                    out.append(int(num.replace(",", "")))
                except ValueError:
                    pass
    return out


def _first_int_near(text: str, *labels: str, window: int = 90) -> int | None:
    vals = _ints_near(text, *labels, window=window)
    return vals[0] if vals else None


def extract_k(doc: Dashboard) -> int | None:
    """Number of pooled studies. None when it cannot be established."""
    for pat in (
        r"\bk\s*=\s*(\d{1,3})\b",
        r"\b(\d{1,3})\s+(?:studies|trials|RCTs|randomi[sz]ed controlled trials)\s+(?:were\s+)?(?:included|pooled|contributed)",
        r"(?:included|pooled|analys\w+)\s+(\d{1,3})\s+(?:studies|trials|RCTs)\b",
        r"\b(\d{1,3})\s+(?:studies|trials)\s+in\s+the\s+(?:meta-analysis|pooled analysis|synthesis)",
    ):
        m = re.search(pat, doc.text, re.IGNORECASE)
        if m:
            try:
                k = int(m.group(1))
            except ValueError:
                continue
            if 1 <= k <= 500:
                return k
    return None


def _n_column(table: list[list[str]]) -> int | None:
    """Index of the participant-count column in a trials table, if identifiable."""
    if not table:
        return None
    header = [c.lower() for c in table[0]]
    for i, cell in enumerate(header):
        if re.fullmatch(r"\s*n\s*", cell) or any(
            key in cell for key in ("participants", "patients", "randomi", "sample size", "total n", "n analysed", "n analyzed")
        ):
            return i
    return None


# --------------------------------------------------------------------------
# Detectors
#
# Each takes a Dashboard and returns a DetectorReport. Contract:
#   - `NOT_APPLICABLE` when the construct genuinely is not in the document
#   - `INCONCLUSIVE` when the construct IS present but the facts cannot be read
#   - never `CLEAN` on the strength of "I did not look"
# --------------------------------------------------------------------------

# A window must look like it is describing an outcome before a unit token in it
# counts. Without this anchor, "points" and "score" match ordinary prose.
_OUTCOME_ANCHOR = re.compile(
    r"\b(?:outcome|endpoint|end-point|change (?:from baseline )?in|difference in|"
    r"reduction in|improvement in|mean|pooled|estimand)\b", re.IGNORECASE)


def d01_continuous_in_ratio_model(doc: Dashboard) -> DetectorReport:
    """MEL-01 -- a continuous outcome pooled as a ratio."""
    rep = DetectorReport("MEL-01", "continuous-outcome-in-a-ratio-model", CRITICAL, CLEAN_)
    hits = []
    for unit in CONTINUOUS_UNITS:
        for win in doc.windows(unit, 130, 130):
            if not _OUTCOME_ANCHOR.search(win):
                continue
            measure = ratio_measure_in(win)
            if measure:
                hits.append((unit, measure, " ".join(win.split())[:240]))
    if not hits:
        rep.status = NOT_APPLICABLE
        rep.detail = "no continuous-unit token found next to a ratio measure"
        return rep

    rep.status = FIRED
    for unit, measure, win in hits[:6]:
        machinery = [label for token, label in RATIO_ONLY_MACHINERY if token in doc.lower]
        rep.findings.append(Finding(
            "MEL-01", CRITICAL,
            f"Continuous outcome (unit '{unit}') reported with a ratio measure ('{measure.strip()}')",
            win,
            "Pool it as a mean difference or SMD. Then DELETE the machinery that is "
            "undefined for a continuous estimand"
            + (f" -- this page still shows: {', '.join(sorted(set(machinery)))}." if machinery else "."),
        ))
    return rep


def d02_measure_vs_data_type(doc: Dashboard) -> DetectorReport:
    """MEL-02 -- effect measure contradicts the data actually extracted."""
    rep = DetectorReport("MEL-02", "effect-measure-vs-data-type", CRITICAL, CLEAN_)
    has_counts = bool(re.search(r"\bevents?\s*/\s*(?:total|n)\b|\bn/N\b|\bevents\b.{0,40}\btotal\b", doc.text, re.I))
    has_means = bool(re.search(r"\bmean\s*\(?\s*(?:SD|s\.d\.|standard deviation)\)?|\bmean\s*±", doc.text, re.I))
    says_md = bool(re.search(r"\bmean difference\b|\bMD\b|\bSMD\b|\bstandardi[sz]ed mean difference\b", doc.text))
    says_ratio = ratio_measure_in(doc.text) is not None

    if not (has_counts or has_means):
        rep.status = NOT_APPLICABLE
        rep.detail = "no extractable 2x2 counts or mean(SD) columns found"
        return rep

    if has_means and not has_counts and says_ratio and not says_md:
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-02", CRITICAL,
            "Mean(SD) data pooled as a ratio measure",
            "page carries mean/SD columns but declares a risk/odds/hazard ratio and no mean difference",
            "Cochrane Handbook ch.6: continuous data take MD or SMD. Re-pool, or state the "
            "dichotomisation rule and show the counts it produced.",
        ))
    elif has_counts and not has_means and says_md and not says_ratio:
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-02", CRITICAL,
            "2x2 event counts pooled as a mean difference",
            "page carries events/total columns but declares a mean difference and no ratio measure",
            "Cochrane Handbook ch.6: dichotomous data take RR, OR or RD. Re-pool on the log scale "
            "and back-transform.",
        ))
    return rep


def d03_double_count_sum_of_subsets(doc: Dashboard) -> DetectorReport:
    """MEL-03 -- one trial entered twice, once pooled and once as its arms.

    The check that caught the U.S. Carvedilol Program double-count in three
    separate published reviews: test whether any row's n equals the sum of a
    subset of the other rows' n. Keyed on denominators, not on trial names,
    because the names are exactly what differ.
    """
    rep = DetectorReport("MEL-03", "double-counted-trial (sum-of-subsets on denominators)", CRITICAL, CLEAN_)
    candidates = []
    for table in doc.tables:
        col = _n_column(table)
        if col is None:
            continue
        rows = []
        for r in table[1:]:
            if col >= len(r):
                continue
            m = re.search(r"\b(\d[\d,]{0,7})\b", r[col])
            if not m:
                continue
            try:
                n = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if n > 0:
                label = (r[0] if r else "")[:60] or f"row{len(rows)}"
                rows.append((label, n))
        if len(rows) >= 3:
            candidates.append(rows)

    if not candidates:
        rep.status = NOT_APPLICABLE
        rep.detail = "no trials table with an identifiable participant-count column"
        return rep

    budget = SUBSET_COMBO_BUDGET
    for rows in candidates:
        if len(rows) > SUBSET_MAX_ROWS:
            rep.status = INCONCLUSIVE_
            rep.detail = (f"table has {len(rows)} rows, above the {SUBSET_MAX_ROWS}-row search bound; "
                          "subset-sum not run on it")
            return rep
        for i, (label, n) in enumerate(rows):
            others = [rows[j] for j in range(len(rows)) if j != i]
            for size in range(2, min(SUBSET_MAX_SIZE, len(others)) + 1):
                for combo in combinations(others, size):
                    budget -= 1
                    if budget <= 0:
                        rep.status = INCONCLUSIVE_
                        rep.detail = ("subset-sum search budget exhausted; this table is too large to "
                                      "clear -- check it by hand")
                        return rep
                    if sum(c[1] for c in combo) == n:
                        rep.status = FIRED
                        rep.findings.append(Finding(
                            "MEL-03", CRITICAL,
                            f"'{label}' (n={n}) equals the sum of {size} other rows",
                            " + ".join(f"{c[0]}({c[1]})" for c in combo) + f" = {n}",
                            "Almost always one trial entered twice: once pooled, once as its component "
                            "arms or sub-reports. Keep ONE row (the most complete report) and re-pool. "
                            "Check dose-ranging arms too -- a multi-arm trial is one cohort.",
                        ))
                        if len(rep.findings) >= 5:
                            return rep
                        break
    return rep


def d04_interval_containment(doc: Dashboard) -> DetectorReport:
    """MEL-04 -- a point estimate printed outside its own interval."""
    rep = DetectorReport("MEL-04", "point-estimate-outside-its-own-interval", CRITICAL, CLEAN_)
    seen = 0
    for point, lo, hi, s in _iter_estimates(doc.text):
        seen += 1
        if lo > hi:
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-04", CRITICAL, "Interval bounds are inverted", s,
                "Lower bound exceeds upper bound. Re-read the source; usually a transposition.",
            ))
        elif not (lo <= point <= hi):
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-04", CRITICAL, "Point estimate lies outside its own interval", s,
                "One of the three numbers is from a different analysis. Recompute all three "
                "from the same model and the same data.",
            ))
        if len(rep.findings) >= 8:
            break
    if seen == 0:
        rep.status = NOT_APPLICABLE
        rep.detail = "no 'estimate (low to high)' pattern found"
    return rep


def d05_arithmetic_impossibility(doc: Dashboard) -> DetectorReport:
    """MEL-05 -- a ratio that cannot exist on the ratio scale."""
    rep = DetectorReport("MEL-05", "impossible-value-on-the-ratio-scale", CRITICAL, CLEAN_)
    ratio_context = ratio_measure_in(doc.text) is not None
    if not ratio_context:
        rep.status = NOT_APPLICABLE
        rep.detail = "no ratio measure declared"
        return rep
    seen = 0
    for point, lo, hi, s in _iter_estimates(doc.text):
        # Only judge estimates that sit in a ratio-labelled window.
        idx = doc.text.find(s)
        win = doc.text[max(0, idx - 120): idx + len(s) + 60] if idx >= 0 else ""
        if ratio_measure_in(win) is None:
            continue
        seen += 1
        bad = [name for name, v in (("point", point), ("lower", lo), ("upper", hi)) if v <= 0]
        if bad:
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-05", CRITICAL,
                f"Ratio measure with a non-positive {'/'.join(bad)} bound", s,
                "A risk/odds/hazard ratio is strictly positive. Either the measure label is wrong "
                "(this looks like a difference) or a sign was lost in back-transformation.",
            ))
        if len(rep.findings) >= 6:
            break
    if seen == 0:
        rep.status = NOT_APPLICABLE
        rep.detail = "ratio measure declared but no interval found in a ratio-labelled context"
    return rep


_GREEN_LITERALS = ("#28a745", "#2ea44f", "#22c55e", "#4caf50", "#16a34a", "#0f9d58",
                   "green", "rgb(40,167,69)", "rgb(34,197,94)")
_PASS_BADGE_TEXT = ("internal checks passed", "checks passed", "all checks passed",
                    "verified", "validated", "integrity: pass", "status: pass",
                    "quality: pass", "no issues found", "100% integrity")
_FAIL_TOKENS = ("fail", "failed", "unverified", "reject", "blocked", "not verified",
                "could not be verified", "insufficient data", "no data available")


def d06_false_green_badge(doc: Dashboard) -> DetectorReport:
    """MEL-06 -- the badge is green because it was written green."""
    rep = DetectorReport("MEL-06", "false-green-badge (colour not derived from the verdict)", CRITICAL, CLEAN_)
    badges = [
        (tag, attrs, text) for tag, attrs, text in doc.elements
        if text and len(text) < 120 and any(p in text.lower() for p in _PASS_BADGE_TEXT)
    ]
    if not badges:
        rep.status = NOT_APPLICABLE
        rep.detail = "no pass/verified badge text found"
        return rep

    # (a) The strong check: badge asserts a pass while the page states a failure.
    contradicting = [t for t in _FAIL_TOKENS if re.search(rf"\b{re.escape(t)}\b", doc.lower)]
    if contradicting:
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-06", CRITICAL,
            "Page shows a pass badge while also stating a failing or unverified status",
            f"badge: {badges[0][2][:100]!r}; page also contains: {', '.join(sorted(set(contradicting))[:6])}",
            "Derive the badge from the verdict object. If any check is FAIL or UNVERIFIED the badge "
            "must not be green -- an UNVERIFIED is not a pass.",
        ))

    # (b) The structural check: literal colour on the badge, no verdict-driven assignment.
    literal_colour = []
    for tag, attrs, text in badges:
        blob = (attrs.get("style", "") + " " + attrs.get("class", "")).lower()
        if any(g in blob for g in _GREEN_LITERALS):
            literal_colour.append((text[:80], blob[:100]))
    derives_from_verdict = bool(re.search(
        r"(verdict|status|result|passed|ok)\s*[?=!<>]{1,3}[^;\n]{0,80}"
        r"(background|backgroundcolor|color|classname|class|style)",
        doc.script_src, re.IGNORECASE,
    )) or bool(re.search(
        r"(background|backgroundColor|color|className)\s*=\s*[^;\n]{0,60}"
        r"(verdict|status|result|passed|isOk|ok\b)",
        doc.script_src, re.IGNORECASE,
    ))
    if literal_colour and not derives_from_verdict:
        rep.status = FIRED
        text, blob = literal_colour[0]
        rep.findings.append(Finding(
            "MEL-06", CRITICAL,
            "Pass badge carries a hardcoded green with no verdict-derived colour assignment",
            f"badge {text!r} styled {blob!r}; no verdict->colour expression found in any <script>",
            "The badge colour must be computed from the verdict object, never written as a literal. "
            "A hardcoded green stays green after the check starts failing.",
        ))
    return rep


def d07_prespecified_vs_display_path(doc: Dashboard) -> DetectorReport:
    """MEL-07 -- headline reads a laxer path than the prespecified one."""
    rep = DetectorReport("MEL-07", "prespecified-estimate-vs-display-path", CRITICAL, CLEAN_)
    blob = doc.lower + " " + doc.script_src.lower()
    prespec = re.search(r"(hartung[- ]knapp|hksj|knapp[- ]hartung)", blob)
    if not prespec:
        rep.status = NOT_APPLICABLE
        rep.detail = "no Hartung-Knapp/HKSJ path declared as prespecified"
        return rep

    laxer = [name for name, pat in (
        ("DerSimonian-Laird", r"dersimonian|\bdl\b|\bd-l\b"),
        ("Wald/normal", r"\bwald\b|normal approximation|z-based"),
    ) if re.search(pat, blob)]
    if not laxer:
        rep.detail = "HKSJ declared and no competing DL/Wald interval found on the page"
        return rep

    # Both paths present. Can we tell which one the headline shows? If not, that
    # is exactly the state this detector must refuse to bless.
    #
    # "Headline" means the heading elements, not the first N characters of the
    # page: on a short report a char-slice swallows the sensitivity-analysis
    # prose and misreads a correctly-labelled page as a defect.
    headline = " ".join(
        text for tag, _attrs, text in doc.elements
        if tag in ("h1", "h2", "h3") and text
    ).lower()
    headline_labels = [n for n in ("hksj", "hartung", "dersimonian", "wald") if n in headline]
    if not headline_labels:
        rep.status = INCONCLUSIVE_
        rep.detail = (f"HKSJ is prespecified but a {'/'.join(laxer)} interval is also computed, and the "
                      "headline estimate is not labelled with the method that produced it")
        return rep
    if any(lbl in ("dersimonian", "wald") for lbl in headline_labels):
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-07", CRITICAL,
            "Headline shows a non-prespecified interval while HKSJ is the declared path",
            f"headline region labelled: {', '.join(headline_labels)}; prespecified: HKSJ",
            "Every display surface -- headline, plain-language text, NNT, significance colour, badge -- "
            "must read the prespecified estimate. Show the laxer path as a labelled sensitivity "
            "analysis, never as the headline.",
        ))
    return rep


# Cochrane Handbook 10.4.3.1 and 10.4.4.1: do not run these below k=10.
K_THRESHOLDS = (
    (r"egger", 10, "Egger's test"),
    (r"funnel plot", 10, "funnel plot"),
    (r"trim[- ]and[- ]fill|trim & fill|duval", 10, "trim-and-fill"),
    (r"meta[- ]regression|metareg", 10, "meta-regression"),
    (r"begg", 10, "Begg's test"),
    (r"peters' test|peters test", 10, "Peters' test"),
)


def d08_k_inappropriate_machinery(doc: Dashboard) -> DetectorReport:
    """MEL-08 -- small-study machinery run below the k it needs."""
    rep = DetectorReport("MEL-08", "k-inappropriate-machinery", HIGH, CLEAN_)
    present = [(label, thr) for pat, thr, label in K_THRESHOLDS if re.search(pat, doc.lower)]

    # The gate bug itself: an Egger call guarded at k>=3 instead of k>=10.
    for m in re.finditer(r"(?:k|nStudies|n_studies|numStudies|studies\.length)\s*(>=|>)\s*(\d{1,2})",
                         doc.script_src):
        thr = int(m.group(2)) + (1 if m.group(1) == ">" else 0)
        ctx = doc.script_src[max(0, m.start() - 200): m.end() + 200].lower()
        if thr < 10 and re.search(r"egger|funnel|trim|metareg|meta_reg|publication ?bias|pubbias", ctx):
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-08", HIGH,
                f"Small-study-effects gate set at k>={thr}",
                " ".join(m.group(0).split()) + "  (in a publication-bias code path)",
                "Cochrane Handbook 10.4.3.1: do not test for funnel-plot asymmetry below k=10. "
                "Raise the gate to k>=10 and suppress the test, the plot and the p-value below it.",
            ))

    # Machinery that a continuous estimand does not admit at all. Checked BEFORE
    # the small-study-effects early return, because a page can show an NNT on a
    # mean difference without running Egger at all.
    if re.search(r"\bmean difference\b|\bSMD\b", doc.text) and ratio_measure_in(doc.text) is None:
        for token, label in RATIO_ONLY_MACHINERY:
            if token in doc.lower:
                rep.status = FIRED
                rep.findings.append(Finding(
                    "MEL-08", HIGH,
                    f"{label} shown for a continuous (mean difference) estimand",
                    f"page declares a mean difference and also shows {label}",
                    f"{label} is undefined without a binary event. Delete it.",
                ))

    if not present:
        if rep.status == CLEAN_:
            rep.status = NOT_APPLICABLE
            rep.detail = "no small-study-effects machinery on the page"
        return rep

    k = extract_k(doc)
    if k is None:
        rep.status = INCONCLUSIVE_
        rep.detail = (f"page runs {', '.join(label for label, _ in present)} but the number of pooled "
                      "studies (k) could not be read, so the threshold cannot be checked")
        return rep

    for label, thr in present:
        if k < thr:
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-08", HIGH,
                f"{label} reported at k={k} (needs k>={thr})",
                f"k={k}; {label} present on the page",
                f"Below k={thr} this test has almost no power and its p-value is not interpretable. "
                "Remove it, or print it greyed out with the k and an explicit 'underpowered, not "
                "interpretable' label.",
            ))
    return rep


def d09_prisma_arithmetic(doc: Dashboard) -> DetectorReport:
    """MEL-09 -- a PRISMA flow whose own numbers do not reconcile."""
    rep = DetectorReport("MEL-09", "impossible-PRISMA-arithmetic", HIGH, CLEAN_)
    identified = _first_int_near(doc.text, "records identified", "studies identified", "citations identified")
    dupes = _first_int_near(doc.text, "duplicates removed", "duplicate records removed", "after duplicates removed")
    screened = _first_int_near(doc.text, "records screened", "titles and abstracts screened", "abstracts screened")
    excluded_screen = _first_int_near(doc.text, "records excluded", "excluded at screening")
    fulltext = _first_int_near(doc.text, "full-text articles assessed", "full text assessed",
                               "reports assessed for eligibility", "full-text assessed")
    excluded_ft = _first_int_near(doc.text, "full-text articles excluded", "reports excluded", "excluded at full text")
    included = _first_int_near(doc.text, "studies included", "included in the synthesis",
                               "included in quantitative synthesis", "studies included in review")

    known = {k: v for k, v in dict(identified=identified, screened=screened, fulltext=fulltext,
                                   included=included).items() if v is not None}
    if len(known) < 2:
        rep.status = NOT_APPLICABLE
        rep.detail = "no PRISMA flow counts found"
        return rep

    def bad(msg, ev, fix):
        rep.status = FIRED
        rep.findings.append(Finding("MEL-09", HIGH, msg, ev, fix))

    if identified is not None and dupes is not None and screened is not None:
        if identified - dupes != screened:
            bad("Screened count does not equal identified minus duplicates",
                f"identified {identified} - duplicates {dupes} = {identified - dupes}, but screened = {screened}",
                "Recount from the exported search results. A mismatch here usually means a second "
                "search was merged in without being added to 'identified'.")
    if screened is not None and excluded_screen is not None and fulltext is not None:
        if screened - excluded_screen != fulltext:
            bad("Full-text count does not equal screened minus excluded",
                f"screened {screened} - excluded {excluded_screen} = {screened - excluded_screen}, "
                f"but full-text assessed = {fulltext}",
                "Reconcile the screening log against the flow diagram.")
    if fulltext is not None and excluded_ft is not None and included is not None:
        if fulltext - excluded_ft != included:
            bad("Included count does not equal full-text assessed minus excluded",
                f"full-text {fulltext} - excluded {excluded_ft} = {fulltext - excluded_ft}, "
                f"but included = {included}",
                "Reconcile the exclusion table; every full-text exclusion needs a stated reason.")
    for name, val in known.items():
        if val == 0:
            bad(f"PRISMA '{name}' count is zero",
                f"{name} = 0 in a flow diagram that reports other non-zero stages",
                "A zero here means the flow was never populated. Fill it from the real search log "
                "or remove the diagram -- an empty PRISMA is worse than none.")
    if included is not None and identified is not None and included > identified:
        bad("More studies included than were ever identified",
            f"included {included} > identified {identified}",
            "Studies were added outside the search. Either widen the documented search so it "
            "retrieves them, or declare them as hand-searched additions in the flow.")

    k = extract_k(doc)
    if k is not None and included is not None and k != included:
        bad("PRISMA 'included' disagrees with the number of pooled studies",
            f"PRISMA included = {included}, but the analysis pools k = {k}",
            "State explicitly why they differ (e.g. studies included but not poolable), or fix "
            "whichever count is wrong.")
    return rep


def d10_fragility_misread(doc: Dashboard) -> DetectorReport:
    """MEL-10 -- 'fragility index = 0, therefore robust'."""
    rep = DetectorReport("MEL-10", "FI=0-read-as-robust", HIGH, CLEAN_)
    if "fragility" not in doc.lower:
        rep.status = NOT_APPLICABLE
        rep.detail = "no fragility index on the page"
        return rep
    for win in doc.windows("fragility", 200, 260):
        wl = win.lower()
        has_zero = re.search(r"fragility index[^.]{0,60}?\b(?:is\s+|=\s*|:\s*)0\b", wl) or \
                   re.search(r"\bfi\s*[:=]\s*0\b", wl)
        claims_robust = re.search(r"\brobust\b|\bstable\b|\bresilient\b|\bnot fragile\b", wl)
        if has_zero and claims_robust:
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-10", HIGH,
                "Fragility index of 0 described as robust",
                " ".join(win.split())[:260],
                "FI=0 is the WEAKEST possible result: the pooled effect is already non-significant, "
                "so no event needs to change to overturn it. Delete the robustness claim. FI is also "
                "undefined for a continuous outcome and for a pooled (rather than single-trial) estimate.",
            ))
            break
    return rep


def d11_missing_harms(doc: Dashboard) -> DetectorReport:
    """MEL-11 -- efficacy synthesised, harms not synthesised."""
    rep = DetectorReport("MEL-11", "missing-harms-synthesis", HIGH, CLEAN_)
    if not any(sig in doc.lower for sig in EFFICACY_SIGNALS):
        rep.status = NOT_APPLICABLE
        rep.detail = "no efficacy synthesis detected"
        return rep

    has_harms = any(t in doc.lower for t in HARM_TERMS)
    if not has_harms:
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-11", HIGH,
            "Efficacy is pooled; no adverse-event or safety outcome appears anywhere",
            "page contains a pooled efficacy estimate and none of: adverse event, serious adverse, "
            "harms, safety outcome, toxicity",
            "Pool at least one harm outcome, or state in the limitations that no harms were "
            "synthesised and that the benefit estimate therefore cannot support a practice claim.",
        ))
        return rep

    # The Tromp guard: discontinuation is a tolerability proxy, not an adverse event.
    if re.search(r"(discontinuation|withdrawal|drop-?out)[^.]{0,80}(adverse event|safety outcome)", doc.lower) or \
       re.search(r"(adverse event|safety outcome)[^.]{0,80}(discontinuation|withdrawal|drop-?out)", doc.lower):
        if not re.search(r"proxy|surrogate|not an adverse event|tolerability only", doc.lower):
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-11", HIGH,
                "All-cause discontinuation presented as an adverse-event outcome",
                "discontinuation/withdrawal appears in the same clause as an adverse-event outcome, "
                "with no proxy caveat",
                "Discontinuation is a tolerability proxy driven by efficacy as much as by harm. "
                "Label it as a proxy and do not let it stand in for a harms synthesis.",
            ))

    # Sign of NNH on a harm outcome.
    if "nnh" in doc.lower and re.search(r"nnh[^.]{0,40}\b-\d", doc.lower):
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-11", HIGH, "Negative number-needed-to-harm printed",
            "NNH appears with a negative value",
            "A negative NNH means the sign convention was inherited from the benefit outcome. "
            "Recompute NNH from the harm's own risk difference.",
        ))
    return rep


def d12_search_window(doc: Dashboard) -> DetectorReport:
    """MEL-12 -- included studies fall outside the stated search window."""
    rep = DetectorReport("MEL-12", "search-window-vs-included-studies", HIGH, CLEAN_)
    m = re.search(
        r"(?:search(?:ed)?|databases? searched)[^.]{0,120}?"
        r"(?:from\s+)?(?:\w+\s+)?(\d{4})\s*(?:to|through|until|-|–)\s*(?:\w+\s+)?(\d{4})",
        doc.text, re.IGNORECASE)
    if not m:
        rep.status = NOT_APPLICABLE
        rep.detail = "no explicit search window found"
        return rep
    lo_y, hi_y = int(m.group(1)), int(m.group(2))
    if lo_y > hi_y:
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-12", HIGH, "Search window runs backwards",
            " ".join(m.group(0).split()),
            "Correct the stated window.",
        ))
        return rep

    # Included-study years, taken from "Author 2021"-style citations.
    years = sorted({int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", doc.text)
                    if 1950 <= int(y) <= 2100})
    cited = [y for y in years if re.search(rf"[A-Z][a-z]+(?:\s+et\s+al\.?)?[,\s]+{y}\b", doc.text)]
    outside = [y for y in cited if y > hi_y]
    if outside:
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-12", HIGH,
            f"Included studies dated after the stated search end ({hi_y})",
            f"window {lo_y}-{hi_y}; cited study years beyond it: {', '.join(str(y) for y in sorted(set(outside))[:8])}",
            "Either the window is mis-stated or trials were added outside the search. Both are "
            "reportable: restate the real window, and declare any hand-added trial as such.",
        ))
    return rep


def d13_template_contamination(doc: Dashboard) -> DetectorReport:
    """MEL-13 -- donor-template text describing the wrong drug or disease."""
    rep = DetectorReport("MEL-13", "template-contamination", MEDIUM, CLEAN_)
    hits = []
    for token in TEMPLATE_CONTAMINATION:
        if token in doc.lower:
            idx = doc.lower.find(token)
            hits.append((token, " ".join(doc.text[max(0, idx - 90): idx + 120].split())))
    # Placeholder leaks. WHERE a token appears decides whether it is a bug:
    #   - `NaN` in <script> is ordinary JS; `NaN` in rendered text is a leak.
    #   - "None declared" under Conflicts of Interest is correct English;
    #     "None participants" is a Python None that reached the page.
    #   - `: None` inside a JS object literal is always a bug -- JS has no
    #     `None`, so the page dies with "ReferenceError: None is not defined".
    # Both false positives above were found by running this detector against
    # real dashboards; matching `\bNone\b` or raw-source `NaN` flagged them.
    _COUNT_NOUN = r"(?:participants|patients|trials|studies|events|records|arms|k)\b"
    for pat, where, label in (
        (r":\s*None\s*[,}\]]", "script", "Python None in a JS object literal (page will not render)"),
        (r"=\s*None\s*[;,)]", "script", "Python None assigned in JavaScript"),
        (rf"\b(?:None|NaN|undefined|null)\s+{_COUNT_NOUN}", "text", "placeholder where a count should be"),
        (rf"\b{_COUNT_NOUN}\s*[:=]\s*(?:None|NaN|undefined)\b", "text", "placeholder where a count should be"),
        (r"\bNaN\b", "text", "NaN shown in rendered output"),
    ):
        haystack = doc.script_src if where == "script" else doc.text
        m = re.search(pat, haystack)
        if m:
            hits.append((label, " ".join(haystack[max(0, m.start() - 80): m.end() + 80].split())))
    if not hits:
        rep.status = NOT_APPLICABLE
        rep.detail = "no known contamination or placeholder token found"
        return rep
    rep.status = FIRED
    for token, ctx in hits[:8]:
        rep.findings.append(Finding(
            "MEL-13", MEDIUM,
            f"Template or placeholder token in shipped output: {token!r}",
            ctx[:220],
            "Text from the donor template survived generation. Every sentence a reader sees must "
            "describe THIS review. Fix the generator (map None to 'null'/'not reported' at the "
            "boundary) and re-render, then keep this check in the build.",
        ))
    return rep


def d14_prospero_overclaim(doc: Dashboard) -> DetectorReport:
    """MEL-14 -- a git timestamp claimed as prospective registration."""
    rep = DetectorReport("MEL-14", "PROSPERO-equivalence-overclaim", MEDIUM, CLEAN_)
    if not re.search(r"prospero|prospectively registered|icmje|registration", doc.lower):
        rep.status = NOT_APPLICABLE
        rep.detail = "no registration claim on the page"
        return rep
    for win in doc.windows("timestamp", 240, 240) + doc.windows("commit", 200, 240):
        wl = win.lower()
        if re.search(r"prospero|icmje|prospectively registered|prospective registration", wl) and \
           re.search(r"equivalent|equival|serves as|functions as|same as|in lieu of|counts as|is our", wl):
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-14", MEDIUM,
                "A commit or GitHub timestamp is claimed as equivalent to prospective registration",
                " ".join(win.split())[:260],
                "Keep the timestamp -- it IS a legitimate tamper-evident record of when the protocol "
                "existed. Drop the equivalence claim. PROSPERO adds third-party custody and public "
                "discoverability, which a commit in your own repo does not.",
            ))
            break
    return rep


def d15_exclusion_mis_scoping(doc: Dashboard) -> DetectorReport:
    """MEL-15 -- an eligibility filter that silently narrows the question."""
    rep = DetectorReport("MEL-15", "date-or-comparator-exclusion-mis-scoping", MEDIUM, CLEAN_)
    blob = doc.text + "\n" + doc.script_src

    m = re.search(r"(?:exclud\w+|only|restricted to|published)[^.\n]{0,60}"
                  r"(?:before|after|since|from|prior to)\s+((?:19|20)\d{2})", blob, re.IGNORECASE)
    if m:
        yr = m.group(1)
        justified = re.search(rf"{yr}[^.]{{0,200}}(because|rationale|justif|guideline|approval|licens)",
                              blob, re.IGNORECASE)
        if not justified:
            rep.status = FIRED
            rep.findings.append(Finding(
                "MEL-15", MEDIUM,
                f"Hard publication-date cut-off at {yr} with no stated rationale",
                " ".join(m.group(0).split()),
                "A bare year cut-off drops eligible trials and biases toward recent, better-funded "
                "ones. Either state the methodological reason (a guideline change, a licensing date) "
                "or retire the filter and re-run the search.",
            ))

    m2 = re.search(r"comparator\s*(?:===?|==|:)\s*[\"']?(placebo|standard[ _-]?care|usual care)[\"']?",
                   blob, re.IGNORECASE)
    if m2:
        active = [n for n in ("warfarin", "aspirin", "dalteparin", "enoxaparin", "clopidogrel",
                              "metformin", "active comparator", "active control")
                  if n in doc.lower]
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-15", MEDIUM,
            "Eligibility filter admits only placebo/standard-care comparators",
            " ".join(m2.group(0).split())
            + (f"; page also mentions active comparators: {', '.join(active)}" if active else ""),
            "This silently converts 'is X effective?' into 'is X better than nothing?'. If active-"
            "comparator trials are genuinely out of scope, say so in the question. Otherwise widen "
            "the filter -- excluding them overstates the effect.",
        ))
    if rep.status == CLEAN_ and not m and not m2:
        rep.status = NOT_APPLICABLE
        rep.detail = "no date floor or comparator filter found"
    return rep


def d16_search_currency(doc: Dashboard) -> DetectorReport:
    """MEL-16 -- an old search presented as current (AMSTAR-2 item 4)."""
    rep = DetectorReport("MEL-16", "stale-search-presented-as-current", MEDIUM, CLEAN_)
    # Take the LATEST year inside each search clause, not the first one. A range
    # ("searched from 2010 to 2026") states the last-search date at its END --
    # reading the first year makes a current review look 16 years stale, which
    # is exactly what an earlier version of this detector did to the kit's own
    # clean example. Clause matching stops at a sentence boundary so a following
    # "Report generated: 2026" cannot be absorbed.
    search_years: list[int] = []
    for m in re.finditer(
        r"(?:last\s+search|search(?:ed|es)?(?:\s+(?:was|were))?"
        r"(?:\s+(?:run|conducted|performed|updated|date))?)\b([^.\n]{0,120})",
        doc.text, re.IGNORECASE,
    ):
        yrs = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", m.group(1))]
        if yrs:
            search_years.append(max(yrs))
    if not search_years:
        rep.status = NOT_APPLICABLE
        rep.detail = "no last-search date found"
        return rep
    search_year = max(search_years)
    gen = re.search(r"(?:generated|built|updated|published|report date)[^.\n]{0,40}?((?:19|20)\d{2})",
                    doc.text, re.IGNORECASE)
    if not gen:
        rep.status = INCONCLUSIVE_
        rep.detail = (f"last search dated {search_year} but the page states no generation/publication "
                      "date, so its currency cannot be assessed")
        return rep
    gap = int(gen.group(1)) - search_year
    if gap >= 2:
        claims_current = re.search(r"most up-to-date|up to date|current evidence|latest evidence|living",
                                   doc.lower)
        rep.status = FIRED
        rep.findings.append(Finding(
            "MEL-16", MEDIUM,
            f"Search is ~{gap} years older than the report",
            f"last search {search_year}; report dated {gen.group(1)}"
            + ("; page also claims to present the most up-to-date evidence" if claims_current else ""),
            "AMSTAR-2 item 4 expects a search within 24 months of publication. Re-run the search, or "
            "state the gap in the abstract and drop any 'most up-to-date evidence' claim.",
        ))
    return rep


DETECTORS = (
    d01_continuous_in_ratio_model,
    d02_measure_vs_data_type,
    d03_double_count_sum_of_subsets,
    d04_interval_containment,
    d05_arithmetic_impossibility,
    d06_false_green_badge,
    d07_prespecified_vs_display_path,
    d08_k_inappropriate_machinery,
    d09_prisma_arithmetic,
    d10_fragility_misread,
    d11_missing_harms,
    d12_search_window,
    d13_template_contamination,
    d14_prospero_overclaim,
    d15_exclusion_mis_scoping,
    d16_search_currency,
)


# --------------------------------------------------------------------------
# Optional witness: reuse Overmind's fail-closed metamorphic engine
# --------------------------------------------------------------------------
def metamorphic_witness(probe_path: str, project_path: str) -> dict:
    """Run Overmind's MetamorphicWitness against a pooling probe.

    Overmind already ships the fail-closed invariant engine for this -- scale
    invariance, zero-heterogeneity identity, sign reversal, tau2 non-negativity,
    I2 in range -- so we call it rather than reimplement it. It is optional
    because Overmind is a separate install.

    A SKIP is reported as SKIP. It is not a pass: Overmind's own history
    includes a bug where a skipped numerical witness was counted as one.
    """
    try:
        from overmind.verification.metamorphic import MetamorphicWitness
    except Exception as exc:  # noqa: BLE001
        return {"status": "SKIPPED", "reason": f"overmind not importable ({exc.__class__.__name__}); "
                                               "install it with scripts/install-overmind.ps1"}
    if not Path(probe_path).is_file():
        return {"status": "SKIPPED", "reason": f"probe not found: {probe_path}"}
    result = MetamorphicWitness().run(probe_path, project_path)
    out = {"status": result.verdict, "detail": result.stdout, "violations": result.stderr}

    # Named known-false-positive, measured against this kit's reference probe.
    # The witness's scale-invariance relation doubles the effects but leaves the
    # variances alone. That is not a change of units, and a correct random-
    # effects estimator is not invariant to it: tau^2 absorbs the extra spread
    # and the weights move (measured ratio 1.862, not 2.000). The relation is
    # valid for fixed-effect pooling only. Reported, not suppressed -- the
    # verdict is unchanged and the student is told what to do about it.
    viol = result.stderr or ""
    if result.verdict == "FAIL" and "scale_invariance" in viol and viol.count(":") <= 2 \
            and not any(r in viol for r in ("zero_het_identity", "sign_reversal", "tau2_nonneg", "i2_range")):
        out["note"] = (
            "the only violated relation is scale_invariance, which a correct RANDOM-EFFECTS "
            "estimator fails by construction (the relation rescales effects without rescaling "
            "variances). Re-run with POOLING_PROBE_MODE=fixed to exercise it meaningfully. "
            "Do not switch your probe to fixed-effect if your dashboard reports random-effects."
        )
    return out


# --------------------------------------------------------------------------
# Verdict + reporting
# --------------------------------------------------------------------------
def verdict(reports: list[DetectorReport]) -> str:
    if any(r.status == FIRED for r in reports):
        return "DEFECTS-FOUND"
    if any(r.status == INCONCLUSIVE_ for r in reports):
        return "INCONCLUSIVE"
    return "CLEAN"


EXIT = {"CLEAN": 0, "DEFECTS-FOUND": 1, "INCONCLUSIVE": 2}


def _dedupe(rep: DetectorReport, cap: int = 6) -> DetectorReport:
    """Collapse identical findings and cap the rest.

    A page that gates six different plots at k>=2 has one defect, not six. The
    count of suppressed duplicates is kept in the detail line so the cap is
    visible rather than silent.
    """
    seen, unique = set(), []
    for f in rep.findings:
        key = (f.title, f.evidence)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    if len(unique) > cap:
        rep.detail = (rep.detail + " " if rep.detail else "") + \
            f"[{len(unique) - cap} further finding(s) of the same class not shown]"
        unique = unique[:cap]
    rep.findings = unique
    return rep


def audit(doc: Dashboard) -> list[DetectorReport]:
    reports = []
    for fn in DETECTORS:
        try:
            reports.append(_dedupe(fn(doc)))
        except Exception as exc:  # noqa: BLE001
            # A crashed detector is inconclusive, never clean.
            code = fn.__name__.split("_")[0].upper().replace("d", "MEL-", 1)
            reports.append(DetectorReport(code, fn.__name__, HIGH, INCONCLUSIVE_,
                                          f"detector raised {exc.__class__.__name__}: {exc}"))
    return reports


def render_text(path: Path, reports: list[DetectorReport], witness: dict | None) -> str:
    v = verdict(reports)
    out = [f"meta-self-audit  {path.name}", "=" * 72]
    findings = [f for r in reports for f in r.findings]
    findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 9))

    if findings:
        out.append("")
        for f in findings:
            out.append(f"[{f.severity.upper():8}] {f.code}  {f.title}")
            out.append(f"           evidence: {f.evidence}")
            out.append(f"           fix:      {f.fix}")
            out.append("")

    truncated = [r for r in reports if r.status == FIRED and "further finding" in r.detail]
    for r in truncated:
        out.append(f"  ({r.code}: {r.detail.strip()})")
    if truncated:
        out.append("")

    inconclusive = [r for r in reports if r.status == INCONCLUSIVE_]
    if inconclusive:
        out.append("Could not be checked (this is why the verdict is not CLEAN):")
        for r in inconclusive:
            out.append(f"  - {r.code} {r.name}: {r.detail}")
        out.append("")

    na = [r for r in reports if r.status == NOT_APPLICABLE]
    clean = [r for r in reports if r.status == CLEAN_]
    out.append(f"Detectors: {len(reports)} run | {len([r for r in reports if r.status == FIRED])} fired "
               f"| {len(clean)} clean | {len(na)} not applicable | {len(inconclusive)} inconclusive")
    if na:
        out.append("  not applicable: " + ", ".join(r.code for r in na))

    if witness is not None:
        out.append(f"Pooling invariants (Overmind metamorphic witness): {witness.get('status')}"
                   + (f" -- {witness.get('reason') or witness.get('detail') or ''}"))
        if witness.get("violations"):
            out.append(f"  violations: {witness['violations']}")
        if witness.get("note"):
            out.append(f"  note: {witness['note']}")
    else:
        out.append("Pooling invariants: NOT RUN (no --metamorphic probe given). The arithmetic behind "
                   "the pooled estimate has not been independently recomputed.")

    out.append("")
    out.append(f"VERDICT: {v}")
    if v == "CLEAN":
        out.append("  No detector fired. That is not the same as correct -- read the "
                   "'Blind spots of these detectors' section of docs/META-ERROR-LIBRARY.md.")
    elif v == "INCONCLUSIVE":
        out.append("  At least one check could not establish the facts it needs. Fail-closed: "
                   "this is not a pass.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="meta-self-audit",
        description="Offline, deterministic self-audit for a single-file meta-analysis dashboard.",
    )
    p.add_argument("dashboard", help="path to the .html report to audit")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--metamorphic", metavar="PROBE.PY",
                   help="optional: also run Overmind's metamorphic pooling-invariant witness "
                        "against a probe reading {effects,variances} on stdin")
    p.add_argument("--project-path", default=".", help="cwd for the metamorphic probe (default: .)")
    args = p.parse_args(argv)

    # A Windows console defaults to cp1252 and raises UnicodeEncodeError the
    # moment a finding quotes a page containing >=, an en-dash or a Greek tau --
    # which real dashboards do constantly. Reconfigure rather than strip: the
    # student should see the evidence as it appears in their file.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    path = Path(args.dashboard)
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"meta-self-audit: cannot read {path}: {exc}", file=sys.stderr)
        return 3

    doc = Dashboard(path, raw)
    reports = audit(doc)
    witness = metamorphic_witness(args.metamorphic, args.project_path) if args.metamorphic else None

    if args.json:
        print(json.dumps({
            "file": str(path),
            "verdict": verdict(reports),
            "detectors": [asdict(r) for r in reports],
            "pooling_invariants": witness,
        }, indent=2))
    else:
        print(render_text(path, reports, witness))

    return EXIT[verdict(reports)]


if __name__ == "__main__":
    raise SystemExit(main())
