"""Fail-closed permission gate for automated article acquisition and processing.

The private manifest contains reviewer decisions, not legal conclusions inferred
from accessibility. This module never retrieves an article or permission page.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit
from uuid import uuid4

POLICY = Path(__file__).resolve().parents[1] / "policies" / "source-rights.json"
OPERATIONS = {"acquire", "process", "replay", "model_submit"}
HASH = re.compile(r"[0-9a-f]{64}")


class RightsError(ValueError):
    """No article IO or processing may proceed after this exception."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def doi_key(value):
    value = unquote(str(value or "")).strip().casefold()
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)


def jama_match(source):
    """Publication identity follows copies; hosting elsewhere grants no exemption."""
    if doi_key(source.get("doi")).startswith("10.1001/"):
        return True
    journal = " ".join(re.findall(r"[a-z0-9]+", str(source.get("journal", "")).casefold()))
    publisher = " ".join(re.findall(r"[a-z0-9]+", str(source.get("publisher", "")).casefold()))
    if (re.match(r"^jama(?:\s|$)", journal) or publisher == "american medical association"
            or journal in {"archives of internal medicine", "archives of general psychiatry",
                           "archives of neurology", "archives of surgery", "archives of dermatology",
                           "archives of ophthalmology", "archives of pediatrics adolescent medicine",
                           "archives of otolaryngology head neck surgery"}):
        return True
    origins = source.get("origin_urls", [])
    values = [source.get("resource", ""), *(origins if isinstance(origins, list) else [])]
    for value in values:
        value = str(value)
        for _ in range(3):
            value = unquote(value)
        for url in [value, *re.findall(r"(?=(https?://[^\s&\"<>]+))", value, re.I)]:
            try:
                host = (urlsplit(url).hostname or "").casefold().rstrip(".")
            except ValueError:
                continue
            if any(host == domain or host.endswith("." + domain)
                   for domain in ("jamanetwork.com", "jama.com", "ama-assn.org")):
                return True
            if "doi.org" == host and doi_key(url).startswith("10.1001/"):
                return True
    return False


def evidence_valid(evidence):
    return (isinstance(evidence, dict) and isinstance(evidence.get("ref"), str)
            and bool(evidence["ref"].strip()) and isinstance(evidence.get("sha256"), str)
            and HASH.fullmatch(evidence["sha256"]) is not None)


def instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed


def evaluate(source, operation, *, now=None, _depth=0):
    now = now or datetime.now(timezone.utc)
    result = {"status": "HOLD", "reason_code": "PERMISSION_UNVERIFIED", "operation": operation,
              "resource": source.get("resource"), "doi": source.get("doi"),
              "evidence": [], "hold_record": "SYN-SOURCE-HOLD-JAMA-20261104"}
    if jama_match(source):
        return dict(result, status="DENY", reason_code="JAMA_PROGRAMME_HOLD")
    if operation not in OPERATIONS:
        return dict(result, reason_code="UNSUPPORTED_OPERATION")
    lineage = source.get("lineage", [])
    if not isinstance(lineage, list) or len(lineage) > 128 or _depth > 8:
        return dict(result, reason_code="LINEAGE_UNVERIFIED")
    resource = str(source.get("resource", ""))
    derived = (source.get("content_kind") == "derived" or resource.startswith("sha256:")
               or urlsplit(resource).path.casefold().endswith((".json", ".jsonl")))
    if derived and not lineage:
        return dict(result, reason_code="LINEAGE_REQUIRED")
    lineage_decisions = []
    for member in lineage:
        if not isinstance(member, dict):
            return dict(result, reason_code="LINEAGE_UNVERIFIED")
        member_decision = evaluate(member, operation, now=now, _depth=_depth + 1)
        lineage_decisions.append(member_decision)
        if member_decision["status"] != "ALLOW":
            return dict(result, status=member_decision["status"],
                        reason_code=member_decision["reason_code"], lineage_decisions=lineage_decisions)
    if not (isinstance(source.get("resource"), str) and source["resource"].strip()
            and isinstance(source.get("origin_urls", []), list)
            and source.get("identity_verified") is True and evidence_valid(source.get("identity_evidence"))
            and re.fullmatch(r"10\.[0-9]{4,9}/\S+", doi_key(source.get("doi")))
            and all(isinstance(source.get(k), str) and source[k].strip() for k in ("journal", "publisher"))):
        return dict(result, reason_code="IDENTITY_UNVERIFIED")
    grant = source.get("permission")
    if not isinstance(grant, dict):
        return result
    evidence = grant.get("evidence")
    try:
        valid_dates = instant(grant.get("reviewed_at")) <= now < instant(grant.get("expires_at"))
    except (ValueError, TypeError, OverflowError):
        valid_dates = False
    if not (grant.get("basis") in {"licence", "explicit_permission", "reviewed_legal_basis"}
            and isinstance(grant.get("reviewed_by"), str) and grant["reviewed_by"].strip()
            and valid_dates and isinstance(grant.get("operations"), list) and operation in grant["operations"]
            and isinstance(evidence, list) and evidence and all(evidence_valid(e) for e in evidence)
            and grant.get("restrictions_checked") is True and grant.get("conditions_satisfied") is True):
        return result
    return dict(result, status="ALLOW", reason_code="VERIFIED_PERMISSION",
                evidence=evidence, identity_evidence=source["identity_evidence"],
                reviewed_by=grant["reviewed_by"], reviewed_at=grant["reviewed_at"],
                expires_at=grant["expires_at"], basis=grant["basis"],
                content_sha256=source.get("content_sha256"), lineage_decisions=lineage_decisions)


def record(decision, *, log_path=None):
    target = log_path or os.environ.get("SYNTHESIS_RIGHTS_LOG")
    if not target:
        raise RightsError("SOURCE_RIGHTS_HOLD: a private append-only decision log is required")
    decision = dict(decision, decision_id=str(uuid4()), decided_at=datetime.now(timezone.utc).isoformat())
    try:
        # One O_APPEND write; no truncation, replacement, or rewriting historical records.
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(target, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("audit log must be a regular file")
            encoded = (canonical(decision) + "\n").encode("utf-8")
            if os.write(fd, encoded) != len(encoded):
                raise OSError("incomplete audit write")
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise RightsError("SOURCE_RIGHTS_HOLD: decision log unavailable") from exc
    return decision


def authorize(resource, operation, *, doi=None, now=None):
    """Check a private grant and persist the decision BEFORE article IO."""
    requested = {"resource": resource, "doi": doi}
    decision = evaluate(requested, operation, now=now)
    decision["policy_sha256"] = None
    decision["manifest_sha256"] = None
    try:
        policy_bytes = POLICY.read_bytes()
        policy = json.loads(policy_bytes)
        decision["policy_sha256"] = sha256(policy_bytes).hexdigest()
        if policy.get("schema_version") != 1 or policy.get("jama_hold") != "active":
            raise RightsError("Invalid source-rights policy; reviewed code change required to release hold")
        # Known restrictions outrank missing grants and can be logged without opening a manifest.
        if decision["status"] != "DENY":
            location = os.environ.get("SYNTHESIS_RIGHTS_MANIFEST")
            if not location:
                raise RightsError("Private source-rights manifest required")
            raw = Path(location).read_bytes()
            manifest = json.loads(raw)
            decision["manifest_sha256"] = sha256(raw).hexdigest()
            sources = manifest.get("sources")
            if not isinstance(sources, list) or any(not isinstance(s, dict) for s in sources):
                raise RightsError("Invalid source-rights manifest")
            matches = [s for s in sources if s.get("resource") == resource]
            if len(matches) != 1:
                raise RightsError("Exactly one source grant must match the requested resource")
            source = matches[0]
            evaluated = evaluate(source, operation, now=now)
            decision.update(evaluated)
            if doi is not None and doi_key(source.get("doi")) != doi_key(doi):
                decision.update(status="HOLD", reason_code="IDENTITY_MISMATCH")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        decision.update(status="HOLD", reason_code="PERMISSION_UNVERIFIED", detail=str(exc))
    decision = record(decision)
    if decision["status"] != "ALLOW":
        raise RightsError("SOURCE_RIGHTS_HOLD: " + decision["reason_code"])
    return decision


def read_authorized(path, *, operation="replay", doi=None, now=None, max_bytes=64 * 1024 * 1024,
                    return_receipt=False):
    path = Path(path).resolve()
    receipt = authorize(path.as_uri(), operation, doi=doi, now=now)
    digest = receipt.get("content_sha256")
    if not isinstance(digest, str) or not HASH.fullmatch(digest):
        record(dict(receipt, status="HOLD", reason_code="CONTENT_DIGEST_REQUIRED"))
        raise RightsError("SOURCE_RIGHTS_HOLD: approved local content digest required")
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        record(dict(receipt, status="HOLD", reason_code="CONTENT_SIZE_LIMIT"))
        raise RightsError("SOURCE_RIGHTS_HOLD: content exceeds byte limit")
    if sha256(raw).hexdigest() != digest:
        record(dict(receipt, status="HOLD", reason_code="CONTENT_DIGEST_MISMATCH"))
        raise RightsError("SOURCE_RIGHTS_HOLD: local content differs from approved version")
    return (raw, receipt) if return_receipt else raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", help="Exact URL, pmc:PMCID or absolute file URI; metadata only")
    parser.add_argument("--operation", choices=sorted(OPERATIONS), required=True)
    parser.add_argument("--doi")
    args = parser.parse_args()
    try:
        print(json.dumps(authorize(args.resource, args.operation, doi=args.doi), indent=2))
        return 0
    except RightsError as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
