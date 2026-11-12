#!/usr/bin/env python3
"""Source-replayed Synthesis checklist records for a supervised development pilot.

Preserves every published check; software never assigns a human Pass. No model,
outreach, scientific certification, or held-out cohort creation is performed.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import re
import sqlite3
import sys

if __package__:
    from scripts import synthesis_replay as replay
else:
    import synthesis_replay as replay

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "e156-synthesis-checklist-v1"
DOCS = ("SYNTHESIS-v1.3-CANDIDATE.md", "SYNTHESIS-HUMAN-CHECKLIST.md",
        "SYNTHESIS-RESPONSE-REVIEW.md", "SYNTHESIS-PARTICIPANT-WORKSHEET.md")
STATUSES = ("Pass", "Review needed", "Insufficient evidence", "N/A")
POINT_FIELDS = {"status", "reason", "reviewer", "recorded_at", "seconds", "evidence"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), f"invalid {label} fields")


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 20000,
            f"{label} needs nonempty text")
    value.encode("utf-8")
    return value


def catalog():
    """Extract the current authoritative wording instead of duplicating it."""
    document = (ROOT / "docs" / "SYNTHESIS-HUMAN-CHECKLIST.md").read_text(encoding="utf-8")
    sections = {"core": [], "detailed": [], "revision": []}
    section = None
    for line in document.splitlines():
        if line.startswith("## "):
            section = {"## Start with six core checks": "core",
                       "## Detailed checks when relevant": "detailed",
                       "## Sweep after revisions and before submission": "revision"}.get(line)
        if section in ("core", "detailed") and re.match(r"\| \d+[. |]", line):
            cells = [part.strip() for part in line.strip("|").split("|")]
            number = re.match(r"\d+", cells[0]).group()
            wording = " ".join(cells[:2]) if section == "core" else cells[1]
            prefix = "core" if section == "core" else "detail"
            sections[section].append({"id": f"{prefix}-{number}", "text": wording})
        if section == "revision" and re.match(r"\d+\. ", line):
            number, wording = line.split(". ", 1)
            sections[section].append({"id": f"revision-{number}", "text": wording})
    for section, prefix, count in (("core", "core", 6), ("detailed", "detail", 27),
                                   ("revision", "revision", 6)):
        require([item["id"] for item in sections[section]] ==
                [f"{prefix}-{i}" for i in range(1, count + 1)],
                "published checklist inventory changed; review integration before use")
    return sections


def document_profile():
    return {name: replay.digest(replay.read(ROOT / "docs" / name, replay.JSON_LIMIT).replace(b"\r\n", b"\n"))
            for name in DOCS}


def software_profile():
    return {**replay.code_profile(), Path(__file__).name:
            replay.digest(replay.read(Path(__file__), replay.JSON_LIMIT).replace(b"\r\n", b"\n"))}


def environment():
    packages = {}
    for name in ("cryptography", "PyNaCl"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "os": platform.system(), "os_release": platform.release(),
            "sqlite": sqlite3.sqlite_version, "optional_packages": packages}


def blank(item):
    return {"id": item["id"], **{key: None for key in POINT_FIELDS}, "history": []}


def claim_inventory(bundle):
    packet = replay.strict_json(replay.read(bundle / "packet.json", replay.JSON_LIMIT))
    return [{"id": claim["id"], "text": claim["text"], "locator": claim["locator"]}
            for claim in packet["claims"]]


def initialize(bundle, expected_sha256, project):
    bundle = Path(bundle)
    text(project, "project")
    replay.verify(bundle, expected_sha256)
    checks = catalog()
    return {"schema": SCHEMA, "project": project, "evaluation_split": "development",
            "manifest_sha256": expected_sha256, "checklist_sha256": document_profile(),
            "software_sha256": software_profile(), "initial_environment": environment(),
            "previous_record_sha256": None,
            "claims": [{**claim, "checks": [blank(item) for item in checks["core"] + checks["detailed"]]}
                       for claim in claim_inventory(bundle)],
            "revision_sweep": [blank(item) for item in checks["revision"]]}


def validate_point(point, *, allow_blank=True):
    fields(point, POINT_FIELDS, "check decision")
    if point["status"] is None:
        require(allow_blank and all(value is None for value in point.values()), "partial unstarted check")
        return
    require(point["status"] in STATUSES, "unknown checklist status")
    for key in ("reason", "reviewer", "recorded_at"):
        text(point[key], key)
    timestamp = datetime.fromisoformat(point["recorded_at"].replace("Z", "+00:00"))
    require(timestamp.tzinfo is not None and timestamp.utcoffset() is not None, "review time requires timezone")
    seconds = point["seconds"]
    try:
        valid_seconds = type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0
    except OverflowError:
        valid_seconds = False
    require(valid_seconds, "seconds must be finite and nonnegative")
    evidence = point["evidence"]
    require(isinstance(evidence, list), "evidence must be a list")
    if point["status"] in ("Pass", "Review needed"):
        require(bool(evidence), "Pass/Review needed requires saved evidence and a locator")
    for attachment in evidence:
        fields(attachment, {"path", "sha256", "locator"}, "evidence")
        text(attachment["path"], "evidence path")
        text(attachment["locator"], "evidence locator")
        require(Path(attachment["path"]).is_absolute(), "evidence path must be absolute in private record")
        raw = replay.read(Path(attachment["path"]), replay.capture.MAX_BYTES)
        require(replay.digest(raw) == attachment["sha256"], "saved evidence changed")


def validate_rows(rows, expected):
    require(isinstance(rows, list) and [r.get("id") for r in rows if isinstance(r, dict)] ==
            [r["id"] for r in expected] and len(rows) == len(expected), "missing/duplicate/unknown checklist rows")
    for row in rows:
        fields(row, POINT_FIELDS | {"id", "history"}, "check row")
        validate_point({key: row[key] for key in POINT_FIELDS})
        require(isinstance(row["history"], list), "invalid correction history")
        require(not row["history"] or row["status"] is not None, "cannot erase a recorded check")
        for previous in row["history"]:
            validate_point(previous, allow_blank=False)


def verify(record, bundle):
    fields(record, {"schema", "project", "evaluation_split", "manifest_sha256", "checklist_sha256",
                   "software_sha256", "initial_environment", "previous_record_sha256", "claims",
                   "revision_sweep"}, "review record")
    require(record["schema"] == SCHEMA and record["evaluation_split"] == "development",
            "checklist adapter is a development record, not an unseen-cohort freeze")
    text(record["project"], "project")
    require(record["checklist_sha256"] == document_profile(), "checklist guidance changed")
    require(record["software_sha256"] == software_profile(), "implementing software changed")
    require(record["previous_record_sha256"] is None or
            isinstance(record["previous_record_sha256"], str) and
            replay.SHA.fullmatch(record["previous_record_sha256"]), "invalid previous-record digest")
    fields(record["initial_environment"], environment(), "environment observation")
    for key in ("python", "implementation", "os", "os_release", "sqlite"):
        text(record["initial_environment"][key], key)
    fields(record["initial_environment"]["optional_packages"], {"cryptography", "PyNaCl"}, "packages")
    require(all(v is None or isinstance(v, str) and v.strip()
                for v in record["initial_environment"]["optional_packages"].values()), "invalid package version")
    automated = replay.verify(Path(bundle), record["manifest_sha256"])
    expected = claim_inventory(Path(bundle))
    claims = record["claims"]
    require(isinstance(claims, list) and len(claims) == len(expected), "missing/extra source claims")
    checks = catalog()
    all_rows = []
    for claim, original in zip(claims, expected):
        fields(claim, {"id", "text", "locator", "checks"}, "claim")
        require({key: claim[key] for key in original} == original, "source claim changed")
        validate_rows(claim["checks"], checks["core"] + checks["detailed"])
        all_rows.extend(claim["checks"])
    validate_rows(record["revision_sweep"], checks["revision"])
    all_rows.extend(record["revision_sweep"])
    completed = [row for row in all_rows if row["status"] is not None]
    attempts = [point for row in all_rows for point in row["history"]] + completed
    total_seconds = sum(point["seconds"] for point in attempts) if attempts else None
    try:
        require(total_seconds is None or math.isfinite(total_seconds), "total check time must be finite")
    except OverflowError as exc:
        raise ValueError("total check time must be finite") from exc
    return {"schema": SCHEMA + "-report", "record_sha256": replay.digest(replay.canonical(record)),
            "workflow_status": "ALL_CHECKS_RECORDED" if len(completed) == len(all_rows) else "INCOMPLETE",
            "checks_total": len(all_rows), "checks_recorded": len(completed),
            "status_counts": {status: sum(row["status"] == status for row in completed) for status in STATUSES},
            "operator_seconds": total_seconds,
            "time_basis": "operator_declared_check_time_including_preserved_corrections",
            "recorded_corrections": sum(len(row["history"]) for row in all_rows),
            "automated_source_replay": automated,
            "scientific_disposition": "HOLD", "release_eligible": False,
            "scientific_accuracy_measured": False, "human_identity_and_independence": "NOT_ESTABLISHED",
            "current_environment": environment()}


def record_check(record, bundle, *, claim, item, status, reason, reviewer, seconds, evidence, locator):
    verify(record, bundle)
    result = copy.deepcopy(record)
    result["previous_record_sha256"] = replay.digest(replay.canonical(record))
    if claim == "revision":
        rows = result["revision_sweep"]
    else:
        found = [row for row in result["claims"] if row["id"] == claim]
        require(len(found) == 1, "unknown claim")
        rows = found[0]["checks"]
    found = [row for row in rows if row["id"] == item]
    require(len(found) == 1, "unknown check")
    row = found[0]
    if row["status"] is not None:
        row["history"].append({key: copy.deepcopy(row[key]) for key in POINT_FIELDS})
    attachments = []
    if evidence is not None:
        evidence = replay.guarded(Path(evidence).expanduser()).resolve()
        attachments.append({"path": str(evidence), "locator": locator,
                            "sha256": replay.digest(replay.read(evidence, replay.capture.MAX_BYTES))})
    else:
        require(locator is None, "locator supplied without evidence")
    row.update(status=status, reason=reason, reviewer=reviewer, seconds=seconds,
               recorded_at=datetime.now(timezone.utc).isoformat(), evidence=attachments)
    verify(result, bundle)
    return result


def render(record, report):
    checks = catalog()
    wording = {item["id"]: item["text"] for group in checks.values() for item in group}
    lines = ["# Synthesis checklist review", "", "Scientific disposition: HOLD. Human judgments are operator declarations.",
             "", f"Recorded checks: {report['checks_recorded']}/{report['checks_total']}", "",
             "Automated source replay is separate from checklist judgments.", ""]
    groups = [(c["id"], c["checks"]) for c in record["claims"]] + [("Revision sweep", record["revision_sweep"])]
    for name, rows in groups:
        lines += [f"## {name}", ""]
        for row in rows:
            lines += [f"- **{row['id']} — {row['status'] or 'NOT_STARTED'}:** {wording[row['id']]}"]
            if row["status"] is not None:
                lines += [f"  Reason: {row['reason']}; reviewer: {row['reviewer']}; time: {row['recorded_at']}."]
                for evidence in row["evidence"]:
                    lines += [f"  Evidence: {evidence['path']} ({evidence['locator']}); SHA-256 {evidence['sha256']}."]
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "record", "verify", "render"):
        command = sub.add_parser(name)
        command.add_argument("--bundle", type=Path, required=True)
        if name == "init":
            command.add_argument("--expected-sha256", required=True)
            command.add_argument("--project", required=True)
        else:
            command.add_argument("--record", type=Path, required=True)
        if name in ("init", "record"):
            command.add_argument("--out", type=Path, required=True, help="new private record; never overwritten")
        if name == "record":
            for flag in ("claim", "item", "reason", "reviewer"):
                command.add_argument("--" + flag, required=True)
            command.add_argument("--status", choices=STATUSES, required=True)
            command.add_argument("--seconds", type=float, required=True)
            command.add_argument("--evidence", type=Path)
            command.add_argument("--locator")
    args = parser.parse_args(argv)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if args.command == "init":
            record = initialize(args.bundle, args.expected_sha256, args.project)
        else:
            record = replay.strict_json(replay.read(args.record, replay.JSON_LIMIT))
        if args.command == "record":
            record = record_check(record, args.bundle, **{key: getattr(args, key) for key in
                ("claim", "item", "status", "reason", "reviewer", "seconds", "evidence", "locator")})
        report = verify(record, args.bundle)
        if args.command in ("init", "record"):
            output = replay.guarded(args.out).resolve()
            require(not output.is_relative_to(replay.guarded(args.bundle).resolve()), "record must remain outside sealed bundle")
            raw = replay.canonical(record)
            require(len(raw) <= replay.JSON_LIMIT, "review record exceeds size limit")
            with output.open("xb") as stream:
                stream.write(raw)
        print(render(record, report) if args.command == "render" else json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        print(json.dumps({"error": str(exc), "scientific_disposition": "HOLD", "release_eligible": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
