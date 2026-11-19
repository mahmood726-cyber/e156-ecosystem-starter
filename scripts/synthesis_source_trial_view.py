"""Synthesis source-to-trial evidence viewer (experimental, offline, stdlib only).

Reviewer-supplied identity fields remain *attestations*: file hashes and quoted
text are checked mechanically; semantic correctness and scientific findings are
NOT authenticated. This module does not extract from PDFs, fit models, or email.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
from pathlib import Path

IDENTITY = (
    "trial_family_id", "cohort_id", "population", "intervention", "comparator",
    "endpoint", "time_window", "analysis_set", "effect_measure", "estimand",
    "statistic_id",
)
UNKNOWN = {"", "unknown", "n/a", "not reported", "not enough info", "unavailable"}
MAX_TEXT_BYTES = 2_000_000
MAX_IMAGE_BYTES = 5_000_000


def _meaningful(value):
    return isinstance(value, str) and value.strip().casefold() not in UNKNOWN


def _safe_file(root: Path, rel: str, maximum: int) -> bytes:
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("source path missing")
    requested = Path(rel)
    if requested.is_absolute():
        raise ValueError("absolute source paths are not allowed")
    root = root.resolve()
    path = (root / requested).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("source must be an existing file inside source root")
    if path.stat().st_size > maximum:
        raise ValueError("source exceeds declared byte limit")
    return path.read_bytes()


def _capture(snapshot: dict, root: Path) -> dict:
    """Verify exact bytes and substring, not locator accuracy or clinical meaning."""
    if not isinstance(snapshot, dict):
        raise ValueError("source snapshot missing")
    for field in ("path", "sha256", "version", "locator", "quote"):
        if not _meaningful(snapshot.get(field)):
            raise ValueError("source snapshot lacks " + field)
    data = _safe_file(root, snapshot["path"], MAX_TEXT_BYTES)
    digest = hashlib.sha256(data).hexdigest()
    if digest != snapshot["sha256"]:
        raise ValueError("source snapshot SHA-256 mismatch")
    try:
        decoded = data.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("source is not UTF-8 text; supply an authorised text capture") from exc
    if snapshot["quote"] not in decoded:
        raise ValueError("verbatim quote not found in archived source bytes")
    result = {k: snapshot[k] for k in ("path", "sha256", "version", "locator", "quote")}
    result["image_data"] = None
    if snapshot.get("page_image") is not None:
        image = snapshot["page_image"]
        if not isinstance(image, dict) or not _meaningful(image.get("path")) or not _meaningful(image.get("sha256")):
            raise ValueError("page image needs a path and SHA-256")
        filename = image["path"]
        raw = _safe_file(root, filename, MAX_IMAGE_BYTES)
        if hashlib.sha256(raw).hexdigest() != image["sha256"]:
            raise ValueError("page image SHA-256 mismatch")
        suffix = Path(filename).suffix.lower()
        if suffix == ".png" and raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif suffix in (".jpg", ".jpeg") and raw.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        else:
            raise ValueError("page image format unsupported")
        result["image_data"] = "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")
    return result


def evaluate_case(case: dict, root: Path) -> dict:
    """Candidate statuses are NEVER verified errors or a paper-level pass."""
    case_id = case.get("case_id") if isinstance(case, dict) else None
    result = {"case_id": case_id or "UNIDENTIFIED", "status": "HOLD", "reason": "",
              "evidence": {}, "calculation": "NOT_RUN"}
    try:
        if not isinstance(case, dict) or not _meaningful(case_id):
            raise ValueError("case_id missing")
        for side in ("published", "primary"):
            result["evidence"][side] = _capture(case.get(side), root)
        contexts = case.get("contexts")
        if not isinstance(contexts, dict):
            raise ValueError("comparison contexts missing")
        left, right = contexts.get("published"), contexts.get("primary")
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ValueError("both source contexts required")
        missing = [f for f in IDENTITY if not (_meaningful(left.get(f)) and _meaningful(right.get(f)))]
        if missing:
            result.update(status="HOLD", reason="missing context identity: " + ", ".join(missing))
            return result
        mismatched = [f for f in IDENTITY if left[f] != right[f]]
        if mismatched:
            result.update(status="NOT_COMPARABLE",
                          reason="source and published contexts differ: " + ", ".join(mismatched))
            return result
        check = case.get("comparison")
        if not isinstance(check, dict):
            raise ValueError("comparison missing")
        kind = check.get("kind")
        if kind == "integer_count":
            lhs, rhs = check.get("published"), check.get("primary")
            if type(lhs) is not int or type(rhs) is not int or min(lhs, rhs) < 0:
                raise ValueError("count comparison requires exact nonnegative integers")
            result["calculation"] = f"reported {lhs} - source {rhs} = {lhs - rhs} (count difference)"
            equal = lhs == rhs
        elif kind == "variance_label":
            lhs, rhs = check.get("published"), check.get("primary")
            if lhs not in ("SD", "SE") or rhs not in ("SD", "SE"):
                raise ValueError("variance labels must be SD or SE")
            result["calculation"] = f"source label {rhs}; reported label {lhs}; no numeric model replay"
            equal = lhs == rhs
        else:
            raise ValueError("only integer_count or variance_label supported")
        if equal:
            result.update(status="NO_SCOPED_DIFFERENCE",
                          reason="supplied values agree; no other claims assessed")
            return result
        refutation = case.get("refutation")
        if (not isinstance(refutation, dict) or
            not _meaningful(refutation.get("alternative")) or
            not _meaningful(refutation.get("checked_against")) or
            refutation.get("result") != "NOT_SUPPORTED"):
            result.update(status="HOLD",
                          reason="mismatch observed but specific alternative has not been source-refuted")
            return result
        result.update(status="REVIEW_CANDIDATE",
                      reason="source-quoted mismatch, contexts attested comparable; human adjudication required")
    except (ValueError, OSError) as exc:
        result.update(status="HOLD", reason=str(exc))
    return result


def duplicate_preflight(rows):
    """Reuse the existing overlap gate; declarations are not independently verified."""
    if rows is None:
        return None
    spec = importlib.util.spec_from_file_location(
        "synthesis_v13_nma_preflight",
        Path(__file__).with_name("synthesis_v13_nma_preflight.py"),
    )
    if spec is None or spec.loader is None:
        return {"status": "HOLD", "reason": "existing NMA preflight unavailable"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.duplicate_trial_population(rows)


def evaluate_packet(packet: dict, root: Path) -> dict:
    if not isinstance(packet, dict) or not isinstance(packet.get("cases"), list):
        raise ValueError("packet must contain a cases array")
    cases = [evaluate_case(case, root) for case in packet["cases"]]
    return {
        "scope": "supervised development; no independent scientific validation",
        "cases": cases,
        "duplicate_preflight": duplicate_preflight(packet.get("duplicate_effects")),
    }


def _section(title: str, evidence: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    if not evidence:
        return "<section><h3>" + esc(title) + "</h3><p>Source inaccessible or unverified.</p></section>"
    photo = ("<img alt='Reviewer-supplied verified page capture' src='" +
             esc(evidence["image_data"]) + "'>" if evidence.get("image_data") else
             "<p class='muted'>No page image supplied. Locator is reviewer-declared, not authenticated.</p>")
    return (
        "<section><h3>" + esc(title) + "</h3><p><b>Version:</b> " + esc(evidence["version"]) +
        " · <b>Locator:</b> " + esc(evidence["locator"]) + "</p><p><b>Archive:</b> " +
        esc(evidence["path"]) + "</p><p class='muted'>SHA-256: " + esc(evidence["sha256"]) +
        "</p><blockquote><mark>" + esc(evidence["quote"]) + "</mark></blockquote>" + photo + "</section>"
    )


def render_html(report: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for case in report["cases"]:
        evidence = case["evidence"]
        cards.append(
            "<article><h2>" + esc(case["case_id"]) + "</h2>" +
            "<p><strong>Status: " + esc(case["status"]) + "</strong> — " +
            esc(case["reason"]) + "</p><div class='cols'>" +
            _section("Published claim", evidence.get("published", {})) +
            _section("Original source", evidence.get("primary", {})) +
            "</div><p><b>Scoped comparison:</b> " + esc(case["calculation"]) + "</p></article>"
        )
    overlap = report.get("duplicate_preflight")
    if overlap is not None:
        cards.append("<article><h2>Duplicate trial identity preflight</h2><p>" +
                     esc(overlap.get("status")) + ": " + esc(overlap.get("reason")) +
                     "</p><p>Only checks caller-attested trial identities, not raw source meaning.</p></article>")
    css = (
        "body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:auto;padding:24px;"
        "background:#fafafa;color:#18212d}article,section{border:1px solid #cbd5e1;"
        "background:white;border-radius:10px;padding:16px;margin:12px 0;min-width:0}"
        ".cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}"
        "blockquote{margin:12px 0;padding:12px;border-left:4px solid #64748b;white-space:pre-wrap}"
        "mark{background:#fff1b3}img{max-width:100%;height:auto;border:1px solid #ddd}"
        ".muted{color:#475569;overflow-wrap:anywhere}p{overflow-wrap:anywhere}"
    )
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Synthesis source evidence review</title><style>" + css +
            "</style><main><h1>Synthesis: source evidence review</h1>"
            "<p>Experimental reviewer aid. Hashes prove captured bytes, not clinical accuracy. "
            "Source locators, context matching and refutations require qualified review. "
            "Keep output private when excerpts are not licensed for release.</p>" +
            "".join(cards) + "</main></html>")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True, help="private JSON case packet")
    parser.add_argument("--source-root", type=Path, required=True, help="root of allowed archived text/page files")
    parser.add_argument("--html-out", type=Path, required=True, help="private standalone HTML reviewer view")
    args = parser.parse_args(argv)
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        report = evaluate_packet(packet, args.source_root)
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(render_html(report), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, "Input/output failure: " + str(exc) + "\n")
    # Do not print quotes, local paths or manuscript text to stdout.
    print(json.dumps({"cases": [{"case_id": c["case_id"], "status": c["status"]}
                                for c in report["cases"]],
                      "duplicate_preflight": report["duplicate_preflight"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
