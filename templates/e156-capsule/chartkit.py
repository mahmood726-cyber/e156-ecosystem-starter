#!/usr/bin/env python
"""chartkit.py -- offline, stdlib-only SVG primitive for an E156 capsule.

Renders the capsule's ONE named estimand as a single-row forest plot on a log
axis (ratio scale) or linear axis (difference scale), with the null line drawn.
No numpy / matplotlib / network: pure stdlib (json, math, argparse) so a student
on a metered connection or a token budget can produce a publication-shaped chart
for FREE -- no LLM, no pip install, no CDN.

Usage:
    python chartkit.py sample.capsule.json --out forest.svg
    python chartkit.py my.capsule.json --out my.svg --title "My estimate"

The output is a standalone .svg -- open it in any browser.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

_W, _H = 640, 160          # canvas
_PADL, _PADR = 280, 40     # left label gutter, right margin
_AXIS_Y = 110
_ROW_Y = 70


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _axis_bounds(point: float, lci, uci, null_value: float, log: bool):
    vals = [v for v in (point, lci, uci, null_value) if v is not None]
    lo, hi = min(vals), max(vals)
    # pad the range by 15% so markers aren't on the edge
    if log:
        lo, hi = math.log10(max(lo, 1e-9)), math.log10(max(hi, 1e-9))
    span = (hi - lo) or 1.0
    return lo - 0.15 * span, hi + 0.15 * span


def _project(value: float, lo: float, hi: float, log: bool) -> float:
    """Map a data value to an x pixel inside [_PADL, _W-_PADR]."""
    v = math.log10(max(value, 1e-9)) if log else value
    frac = (v - lo) / ((hi - lo) or 1.0)
    return _PADL + frac * (_W - _PADL - _PADR)


def render(capsule: dict, title: str | None = None) -> str:
    est = capsule.get("estimand") or {}
    point = float(est["point"])
    lci = est.get("lci")
    uci = est.get("uci")
    null_value = float(est.get("null_value", 1.0))
    log = (est.get("scale", "ratio") == "ratio")
    name = est.get("name", "effect")
    label = title or capsule.get("title", "estimand")

    lo, hi = _axis_bounds(point, lci, uci, null_value, log)
    x_pt = _project(point, lo, hi, log)
    x_null = _project(null_value, lo, hi, log)
    x_lo = _project(lci, lo, hi, log) if lci is not None else x_pt
    x_hi = _project(uci, lo, hi, log) if uci is not None else x_pt

    ci_txt = ""
    if lci is not None and uci is not None:
        ci_txt = f"  ({lci:g} to {uci:g})"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}" '
        f'viewBox="0 0 {_W} {_H}" font-family="system-ui,Segoe UI,Arial,sans-serif">',
        f'<rect width="{_W}" height="{_H}" fill="#ffffff"/>',
        f'<text x="16" y="28" font-size="15" font-weight="600" fill="#111">{_esc(label)}</text>',
        # null reference line
        f'<line x1="{x_null:.1f}" y1="40" x2="{x_null:.1f}" y2="{_AXIS_Y}" '
        f'stroke="#bbb" stroke-width="1" stroke-dasharray="4 3"/>',
        f'<text x="{x_null:.1f}" y="{_AXIS_Y + 18}" font-size="11" fill="#888" '
        f'text-anchor="middle">null {null_value:g}</text>',
        # axis line
        f'<line x1="{_PADL}" y1="{_AXIS_Y}" x2="{_W - _PADR}" y2="{_AXIS_Y}" stroke="#444" stroke-width="1"/>',
        # row label
        f'<text x="16" y="{_ROW_Y + 4}" font-size="13" fill="#222">{_esc(name)}: '
        f'<tspan font-weight="600">{point:g}</tspan>{_esc(ci_txt)}</text>',
        # CI whisker
        f'<line x1="{x_lo:.1f}" y1="{_ROW_Y}" x2="{x_hi:.1f}" y2="{_ROW_Y}" stroke="#1f6feb" stroke-width="2"/>',
        f'<line x1="{x_lo:.1f}" y1="{_ROW_Y - 5}" x2="{x_lo:.1f}" y2="{_ROW_Y + 5}" stroke="#1f6feb" stroke-width="2"/>',
        f'<line x1="{x_hi:.1f}" y1="{_ROW_Y - 5}" x2="{x_hi:.1f}" y2="{_ROW_Y + 5}" stroke="#1f6feb" stroke-width="2"/>',
        # point marker
        f'<rect x="{x_pt - 5:.1f}" y="{_ROW_Y - 5}" width="10" height="10" fill="#1f6feb"/>',
        f'<text x="{_W - _PADR}" y="{_AXIS_Y + 18}" font-size="11" fill="#888" '
        f'text-anchor="end">{"log scale" if log else "linear scale"}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Render an E156 capsule estimand as an offline SVG forest plot.")
    ap.add_argument("capsule", help="path to a capsule JSON (see capsule.schema.json)")
    ap.add_argument("--out", required=True, help="output .svg path")
    ap.add_argument("--title", default=None, help="override the chart title")
    args = ap.parse_args(argv)

    capsule = json.loads(Path(args.capsule).read_text(encoding="utf-8"))
    if "estimand" not in capsule or "point" not in (capsule.get("estimand") or {}):
        print("ERROR: capsule has no estimand.point to plot", file=sys.stderr)
        return 2
    svg = render(capsule, title=args.title)
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"wrote {args.out} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
