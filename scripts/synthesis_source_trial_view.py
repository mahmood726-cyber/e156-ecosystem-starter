"""Synthesis source-to-trial evidence viewer (experimental, offline, stdlib only).

Reviewer-supplied identity fields remain *attestations*: file hashes and quoted
text are checked mechanically; semantic correctness and scientific findings are
NOT authenticated. This module does not extract from PDFs, fit models, or email.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import html
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

IDENTITY = (
    "trial_family_id", "cohort_id", "population", "intervention", "comparator",
    "endpoint", "time_window", "analysis_set", "effect_measure", "estimand",
    "statistic_id",
)
UNKNOWN = {"", "unknown", "n/a", "not reported", "not enough info", "unavailable"}
MAX_TEXT_BYTES = 2_000_000
MAX_IMAGE_BYTES = 5_000_000


def _source_paths(packet, root: Path):
    """Collect declared text/image paths, including missing captures, for output isolation."""
    pending = [packet]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and "sha256" in value:
                yield root / value["path"]
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)


def _prepare_outputs(outputs, *, protected=()):
    """Require distinct, new destinations without writing or creating directories."""
    try:
        forbidden = {os.path.normcase(str(Path(path).resolve())) for path in protected}
        prepared, identities = [], set()
        for value in outputs:
            path = Path(value)
            # lexists also refuses dangling links, which exists() would miss.
            if os.path.lexists(path):
                raise ValueError("Output already exists; choose a new output filename")
            path = path.resolve()
            identity = os.path.normcase(str(path))
            if identity in forbidden or identity in identities:
                raise ValueError("Output destinations must be distinct from inputs and each other")
            if os.path.lexists(path):
                raise ValueError("Output already exists; choose a new output filename")
            parent = path.parent
            while not parent.exists():
                if parent.parent == parent:
                    raise ValueError("Output filesystem root is unavailable")
                parent = parent.parent
            if not parent.is_dir():
                raise ValueError("Output parent must be a directory")
            identities.add(identity)
            prepared.append(path)
        return prepared
    except (OSError, RuntimeError) as exc:
        raise ValueError("Unable to validate output destinations") from exc


def _publish_outputs(outputs, *, protected=()):
    """Stage complete UTF-8 files, then atomically publish without replacing any file.

    Hard-link creation is the no-clobber publication primitive on Windows and POSIX.
    A filesystem that cannot provide it refuses rather than falling back to an
    overwriting rename. Multi-output failures roll back this attempt's own links.
    """
    outputs = list(outputs)
    paths = _prepare_outputs([path for path, _ in outputs], protected=protected)
    staged, published = [], []
    failure = None
    try:
        for path, (_, content) in zip(paths, outputs):
            data = content.encode("utf-8")
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".synthesis-output-", suffix=".tmp", dir=path.parent)
            temporary = Path(name)
            staged.append((temporary, path))
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        for temporary, path in staged:
            os.link(temporary, path)
            published.append((temporary, path))
    except BaseException as exc:
        failure = exc
    cleanup_failed = False
    if failure is not None:
        for temporary, path in reversed(published):
            try:
                # Do not remove a competing file or symlink that replaced our link.
                if os.path.samestat(temporary.stat(), path.stat(follow_symlinks=False)):
                    path.unlink()
            except FileNotFoundError:
                continue
            except OSError:
                cleanup_failed = True
    for temporary, _ in staged:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            cleanup_failed = True
    if isinstance(failure, (KeyboardInterrupt, SystemExit)):
        raise failure
    if failure is not None or cleanup_failed:
        raise ValueError("Output publication failed; existing files were not overwritten. "
                         "Inspect new destinations before retrying") from None


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
    if not re.fullmatch(r"[a-f0-9]{64}", snapshot["sha256"]) or not hmac.compare_digest(digest, snapshot["sha256"]):
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
        if not re.fullmatch(r"[a-f0-9]{64}", image["sha256"]) or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), image["sha256"]):
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


def _complete_number_at(quote: str, offset: int, text: str) -> bool:
    """Refuse fragments of signed, decimal, exponent or identifier tokens."""
    if quote[offset:offset + len(text)] != text:
        return False
    before = quote[offset - 1] if offset else ""
    after = quote[offset + len(text):offset + len(text) + 1]
    return not any(char and (char.isalnum() or char in ".,_+-−±﹣－⁺⁻")
                   for char in (before, after))


def _verbatim_value_in_quote(quote: str, value) -> bool:
    """Minimal literal tie to source bytes; still not semantic cell authentication."""
    if type(value) is int:
        literals = (str(value), format(value, ","))
        return any(_complete_number_at(quote, match.start(), literal)
                   for literal in literals for match in re.finditer(re.escape(literal), quote))
    if value in ("SD", "SE"):
        # A trailing full stop in "SD." is punctuation, not a numeric decimal.
        return bool(re.search(r"(?<![A-Za-z])" + value + r"(?![A-Za-z])", quote))
    return False



def _count_percentage(check: dict, evidence: dict, contexts: dict) -> dict:
    """Screen a source-anchored unweighted people/people percentage.

    Exact-integer cross multiplication implements conservative nearest-decimal
    compatibility, including either halfway tie. Inputs and raw-fraction method
    remain human attestations; this cannot authenticate clinical denominators.
    """
    if (check.get("percentage_method") != "RAW_UNWEIGHTED_PERSON_FRACTION"
            or check.get("raw_fraction_source_verified") is not True
            or check.get("denominator_basis_source_verified") is not True):
        return {"status": "HOLD", "reason": "raw participant-fraction method and denominator basis unverified"}
    published_context, primary_context = contexts["published"], contexts["primary"]
    basis_a = published_context.get("denominator_basis")
    basis_b = primary_context.get("denominator_basis")
    if not _meaningful(basis_a) or not _meaningful(basis_b):
        return {"status": "HOLD", "reason": "denominator basis missing from source contexts"}
    if basis_a != basis_b:
        return {"status": "NOT_COMPARABLE", "reason": "published and primary denominator bases differ"}
    keys = ("published_count", "published_denominator", "primary_count", "primary_denominator")
    values = [check.get(k) for k in keys]
    if any(type(value) is not int or value < 0 for value in values):
        return {"status": "HOLD", "reason": "numerators and denominators must be exact nonnegative integers"}
    count, denominator, source_count, source_denominator = values
    if not denominator or not source_denominator or count > denominator or source_count > source_denominator:
        return {"status": "HOLD", "reason": "participant counts exceed or lack their denominators"}
    printed = check.get("published_percentage")
    if not isinstance(printed, str):
        return {"status": "HOLD", "reason": "verbatim printed percent absent"}
    m = re.fullmatch(r"(0|[1-9][0-9]*)(?:\.([0-9]{1,8}))?%", printed)
    if not m:
        return {"status": "HOLD", "reason": "unsupported percentage literal or display precision"}
    digits = m.group(2) or ""
    scale = 10 ** len(digits)
    reported_scaled = int(m.group(1)) * scale + int(digits or "0")
    if reported_scaled > 100 * scale:
        return {"status": "HOLD", "reason": "reported participant percentage outside 0 to 100"}
    pub_quote = evidence["published"]["quote"]
    src_quote = evidence["primary"]["quote"]
    expected_literals = (
        ("published count", pub_quote, count),
        ("published denominator", pub_quote, denominator),
        ("primary count", src_quote, source_count),
        ("primary denominator", src_quote, source_denominator),
    )
    for name, quote, value in expected_literals:
        if not _verbatim_value_in_quote(quote, value):
            return {"status": "HOLD", "reason": name + " not anchored in its verbatim source quote"}
    if not any(_complete_number_at(pub_quote, match.start(), printed)
               and pub_quote[match.end():match.end() + 1] != "%"
               for match in re.finditer(re.escape(printed), pub_quote)):
        return {"status": "HOLD", "reason": "published percentage not anchored in verbatim published quote"}
    if count != source_count or denominator != source_denominator:
        return {"status": "HOLD", "reason": "source count or denominator differs; resolve extraction before percentage check"}
    # exact fraction: percentage = (100 * count) / denominator;
    # printed interval ± 0.5 / scale percent, including ties conservatively.
    delta = abs(100 * count * scale - reported_scaled * denominator)
    compatible = 2 * delta <= denominator
    calculation = (f"100 * {count} / {denominator} percent versus published {printed}; "
                   f"nearest {len(digits)} decimal(s), halfway ties treated as compatible")
    return {"status": "CONSISTENT" if compatible else "REVIEW",
            "reason": "source-anchored raw fraction compatible with printed rounding"
                      if compatible else "raw fraction outside printed rounding interval; human review required",
            "calculation": calculation}


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
        elif kind == "count_percentage":
            percentage = _count_percentage(check, result["evidence"], contexts)
            result["calculation"] = percentage.get("calculation", "NOT_RUN")
            if percentage["status"] in ("HOLD", "NOT_COMPARABLE"):
                result.update(status=percentage["status"], reason=percentage["reason"])
                return result
            equal = percentage["status"] == "CONSISTENT"
        else:
            raise ValueError("only integer_count, variance_label or count_percentage supported")
        if kind != "count_percentage":
            for side, value in (("published", lhs), ("primary", rhs)):
                if not _verbatim_value_in_quote(result["evidence"][side]["quote"], value):
                    result.update(status="HOLD",
                                  reason="comparison value not anchored in verbatim " + side + " quote")
                    return result
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
        if case.get("claim_version_status") != "CURRENT_UNCORRECTED":
            result.update(status="HOLD",
                          reason="current uncorrected published claim not established; "
                                 "historical correction or unknown version cannot be a new flag")
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
        "background:#fafafa;color:#18212d;overflow-wrap:anywhere}article,section{border:1px solid #cbd5e1;"
        "background:white;border-radius:10px;padding:16px;margin:12px 0;min-width:0}"
        ".cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:16px}"
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
        _prepare_outputs([args.html_out], protected=[args.packet])
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        protected = [args.packet, *_source_paths(packet, args.source_root)]
        output, = _prepare_outputs([args.html_out], protected=protected)
        report = evaluate_packet(packet, args.source_root)
        _publish_outputs([(output, render_html(report))], protected=protected)
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
