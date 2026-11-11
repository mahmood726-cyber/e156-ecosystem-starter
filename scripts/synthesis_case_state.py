"""Local append-only case metadata with redacted intake summaries; no email API."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "synthesis-case-state/1"
MAX_BYTES = 1024 * 1024
MAX_EVENTS = 2000
OUTCOMES = {"ACKNOWLEDGED", "EXPLANATION_UNVERIFIED", "UNRESOLVED", "SOURCE_RECHECKED",
            "RESOLVED_ENQUIRY", "METHOD_DISCUSSION", "CONCERN_PERSISTS"}
PENDING = {"ACKNOWLEDGED", "EXPLANATION_UNVERIFIED", "UNRESOLVED", "CONCERN_PERSISTS"}
CORRECTIONS = {"NOT_REQUESTED", "REQUESTED", "AUTHOR_REPORTED_PUBLISHED", "PUBLIC_NOTICE_RECORDED"}


def _text(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 500
            or value != value.strip() or any(ord(c) < 32 for c in value)):
        raise ValueError("Invalid private metadata text")
    return value


def _time(value):
    _text(value)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("Private events require explicit UTC timestamps")
    return result


def read_state(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError("Duplicate field in private metadata")
            result[key] = value
        return result
    with path.open("rb") as stream: raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES: raise ValueError("Private case file exceeds the size limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)


def project_state(state, document, claim_ids):
    """Validate references without exposing or fetching private evidence."""
    held = {"status": "HOLD", "reason": "Private case metadata is invalid or mismatched",
            "email_eligible": False, "contact_paused": True, "claims": []}
    try:
        if (not isinstance(state, dict) or state.get("schema_version") != SCHEMA
                or not isinstance(state.get("document"), dict) or not isinstance(document, dict)):
            return held
        for field in ("identifier", "version"):
            if _text(state["document"].get(field)) != document.get(field): return held
        events = state.get("events")
        if not isinstance(events, list) or len(events) > MAX_EVENTS: return held
        claim_ids = set(claim_ids)
        replies, corrections, pauses, seen = {}, {}, {}, set()
        last_time = datetime.min.replace(tzinfo=timezone.utc)
        for event in events:
            if not isinstance(event, dict): return held
            event_id, when = _text(event.get("event_id")), _time(event.get("recorded_at"))
            if event_id in seen or when < last_time: return held
            seen.add(event_id); last_time = when
            kind = event.get("type")
            if kind in ("REPLY_POINT", "CORRECTION_STATUS"):
                cid, point = _text(event.get("claim_id")), _text(event.get("point_id"))
                if cid not in claim_ids: return held
                key = cid, point
                if kind == "REPLY_POINT":
                    original = _text(event.get("original_question_reference"))
                    _text(event.get("reply_reference"))
                    outcome = event.get("outcome")
                    if not isinstance(outcome, str) or outcome not in OUTCOMES: return held
                    if key in replies and replies[key][1] != original: return held
                    if outcome not in {"ACKNOWLEDGED", "EXPLANATION_UNVERIFIED", "UNRESOLVED"}:
                        _text(event.get("source_recheck_reference")); _text(event.get("reviewer_reference"))
                    replies[key] = outcome, original
                else:
                    status = event.get("status")
                    if not isinstance(status, str) or status not in CORRECTIONS: return held
                    _text(event.get("evidence_reference"))
                    corrections[key] = status
            elif kind == "CONTACT_PAUSE":
                pause_id = _text(event.get("pause_id"))
                if pause_id in pauses: return held
                _text(event.get("source_reference")); _text(event.get("reason")); _text(event.get("release_condition"))
                scope = event.get("scope")
                if scope == "DOCUMENT": affected = claim_ids
                elif isinstance(scope, list) and scope and all(isinstance(c, str) and c in claim_ids for c in scope):
                    affected = set(scope)
                else: return held
                pauses[pause_id] = {"active": True, "claims": affected}
            elif kind == "CONTACT_RELEASE":
                pause_id = _text(event.get("pause_id"))
                _text(event.get("source_reference"))
                if event.get("release_authorised") is not True or pause_id not in pauses or not pauses[pause_id]["active"]:
                    return held
                pauses[pause_id]["active"] = False
            else: return held
        summaries = []
        for cid in sorted(claim_ids):
            outcomes = [v[0] for k, v in sorted(replies.items()) if k[0] == cid]
            pending = sum(o in PENDING for o in outcomes)
            summaries.append({"claim_id": cid, "point_count": len(outcomes), "point_outcomes": outcomes,
                              "pending_point_count": pending, "reply_pending": bool(pending),
                              "correction_statuses": [v for k, v in sorted(corrections.items()) if k[0] == cid],
                              "publication_independently_verified": False,
                              "contact_paused": any(p["active"] and cid in p["claims"] for p in pauses.values())})
        return {"status": "VALIDATED", "reason": "Private metadata checked; sources and attestations are not authenticated",
                "event_count": len(events), "claims": summaries,
                "contact_paused": any(p["active"] for p in pauses.values()), "email_eligible": False,
                "evidence_basis": "REVIEWER_ATTESTATION_ONLY"}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return held


def _claim_ids(state):
    ids = set()
    for event in state.get("events", []):
        if not isinstance(event, dict): continue
        if isinstance(event.get("claim_id"), str): ids.add(event["claim_id"])
        if isinstance(event.get("scope"), list): ids.update(c for c in event["scope"] if isinstance(c, str))
    return ids


def append_event(state, event):
    if not isinstance(state, dict) or not isinstance(state.get("events"), list):
        raise ValueError("Invalid existing private state")
    candidate = deepcopy(state)
    candidate["events"].append(deepcopy(event))
    if project_state(candidate, candidate.get("document"), _claim_ids(candidate))["status"] != "VALIDATED":
        raise ValueError("Private event rejected; existing history preserved")
    return candidate


def _write(path, state):
    raw = (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(raw) > MAX_BYTES: raise ValueError("Private case file exceeds the size limit")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name); stream.write(raw)
        temporary.replace(path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--event", type=Path)
    parser.add_argument("--identifier")
    parser.add_argument("--version")
    args = parser.parse_args(argv)
    lock = args.state.with_name(args.state.name + ".lock")
    descriptor = None
    try:
        fresh_directory = not args.state.parent.exists()
        args.state.parent.mkdir(parents=True, exist_ok=True)
        if fresh_directory:
            (args.state.parent / ".gitignore").write_text("*\n", encoding="utf-8")
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        if args.init:
            if args.state.exists(): raise ValueError("Existing history cannot be reinitialised")
            state = {"schema_version": SCHEMA, "document": {"identifier": _text(args.identifier),
                     "version": _text(args.version)}, "events": []}
            _write(args.state, state)
        else:
            state = read_state(args.state)
            if args.event is not None:
                state = append_event(state, read_state(args.event))
                _write(args.state, state)
        summary = project_state(state, state.get("document"), _claim_ids(state))
        if summary["status"] != "VALIDATED": raise ValueError("Invalid private state")
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print(json.dumps({"status": "HOLD", "reason": "Private case operation refused; history was not replaced",
                          "email_eligible": False}))
        return 2
    finally:
        if descriptor is not None:
            os.close(descriptor); lock.unlink(missing_ok=True)


if __name__ == "__main__": raise SystemExit(main())
