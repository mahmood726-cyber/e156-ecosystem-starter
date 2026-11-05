"""Fail-closed Synthesis source-rights and outgoing-contact preflight.

This is a *software policy gate*, not a statement of copyright law or proof
that a reviewer actually checked permissions. All fixtures are synthetic.
Call at every source ingress and every outgoing-transport boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import getaddresses
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

SOURCE_POLICY = "SYN-SOURCE-HOLD-JAMA-20261104|reviewed-operation-specific-permissions-v1"
OUTGOING_POLICY = "SYN-OUTGOING-PAUSE-20261105|SYN-NOCONTACT-ZUIN-20261105"
OUTGOING_PAUSED = True  # Explicit user instruction; no environment override.
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _day(value):
    if not isinstance(value, str):
        raise ValueError("date not supplied")
    return date.fromisoformat(value)


def _doi(value):
    """Canonicalize a DOI literal or trusted resolver URL for identity checks.

    Host comparison uses parsed hostname (not string prefix) so an impostor
    host cannot impersonate doi.org. Query/fragment belong to the resolver
    request, not the DOI identity. Non-resolver URLs fail closed.
    """
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if value.casefold().startswith("doi:"):
        value = value[4:].strip()
    elif "://" in value:
        try:
            parsed = urlsplit(value)
            if (parsed.scheme.casefold() not in {"https", "http"}
                    or (parsed.hostname or "").casefold() not in
                    {"doi.org", "dx.doi.org"}
                    or parsed.username is not None or parsed.password is not None):
                return ""
        except ValueError:
            return ""
        value = parsed.path.lstrip("/")
    value = value.casefold()
    return value if re.fullmatch(r"10\.\d{4,9}/[^\s?#]+", value) else ""


def _host(value):
    if not isinstance(value, str):
        return ""
    try:
        return (urlsplit(value).hostname or "").casefold()
    except ValueError:
        return ""


def is_jama_source(source):
    """Match original publication identity, never just its current mirror host."""
    if not isinstance(source, dict):
        return False
    doi = _doi(source.get("doi"))
    if doi.startswith("10.1001/"):
        return True
    host_names = (_host(source.get(k)) for k in ("source_url", "original_url"))
    if any(h == "jamanetwork.com" or h.endswith(".jamanetwork.com") or
           h == "ama-assn.org" or h.endswith(".ama-assn.org")
           for h in host_names):
        return True
    journal = str(source.get("original_journal") or "").casefold()
    publisher = str(source.get("original_publisher") or "").casefold()
    return (bool(re.search(r"\bjama\b|\barchives of\b|\bjournal of the american medical association\b", journal)) or
            "american medical association" in publisher or
            publisher in {"ama", "ama publishing", "jama network"})


def assess_source(manifest, source, operation, *, on_date=None):
    """Pure, deterministic policy decision; caller must append a receipt first."""
    if not isinstance(source, dict) or not isinstance(operation, str):
        return "SOURCE_RIGHTS_HOLD", "invalid source or operation"
    if is_jama_source(source):
        return "SOURCE_RIGHTS_HOLD", "programme-wide JAMA identity hold"
    doi = _doi(source.get("doi"))
    version = source.get("version")
    resource = source.get("resource_ref")
    route = source.get("access_route")
    if not doi or not all(isinstance(x, str) and x.strip() for x in (version, resource, route)):
        return "SOURCE_RIGHTS_HOLD", "unverified source identity/version/access route"
    if operation not in {"NETWORK_FETCH", "CACHE_READ", "EXTRACT", "REPLAY", "MODEL_SUBMISSION"}:
        return "SOURCE_RIGHTS_HOLD", "unrecognized operation"
    if not isinstance(manifest, dict) or manifest.get("schema") != "source-permissions-v1" or not isinstance(manifest.get("permissions"), list):
        return "SOURCE_RIGHTS_HOLD", "missing or invalid reviewed permission manifest"
    matches = [p for p in manifest["permissions"] if isinstance(p, dict) and
               _doi(p.get("doi")) == doi and p.get("version") == version and
               p.get("resource_ref") == resource and p.get("access_route") == route]
    if len(matches) != 1:
        return "SOURCE_RIGHTS_HOLD", "no unique reviewed permission for exact source version and route"
    p = matches[0]
    # The reviewer-supplied original publication identity is mandatory even
    # when the requested bytes are hosted by a mirror or a local cache.
    if not all(isinstance(p.get(k), str) and p[k].strip() for k in
               ("original_journal", "original_publisher", "original_url")):
        return "SOURCE_RIGHTS_HOLD", "original publisher/journal identity not reviewed"
    if is_jama_source(p):
        return "SOURCE_RIGHTS_HOLD", "programme-wide JAMA original-publication hold"
    # Bind the caller's original-publication identity to the reviewed grant.
    # The same DOI/version/cache route must not authorize changed source identity.
    original_fields = ("original_journal", "original_publisher", "original_url")
    if any(not isinstance(source.get(k), str) or not source[k].strip() or
           source[k].strip() != p[k].strip() for k in original_fields):
        return "SOURCE_RIGHTS_HOLD", "original publication identity differs from reviewed permission"
    # A grant for the original publication cannot be reused on a different
    # retrieval URL. Both source and reviewed record must agree on the exact
    # route URL when either declares it; aliases need separate review.
    requested_url, reviewed_url = source.get("source_url"), p.get("source_url")
    if requested_url is not None or reviewed_url is not None:
        if (not isinstance(requested_url, str) or not requested_url.strip()
                or not isinstance(reviewed_url, str) or not reviewed_url.strip()
                or requested_url.strip() != reviewed_url.strip()):
            return "SOURCE_RIGHTS_HOLD", "source URL differs from exact reviewed access route"
    # This helper's v1 manifest has no way to authenticate each linked source
    # in a derived item. Hold declared ancestry rather than silently granting
    # linked-source operations via the top-level DOI. The separately reviewed
    # source-rights caller must cover each ancestor before integration.
    for entry in (source, p):
        kind = entry.get("content_kind")
        if isinstance(kind, str) and kind.strip().casefold() == "derived":
            return "SOURCE_RIGHTS_HOLD", "derived provenance requires separate reviewed permissions"
        if any(key in entry and
               (not isinstance(entry[key], list) or bool(entry[key]))
               for key in ("lineage", "origin_urls")):
            return "SOURCE_RIGHTS_HOLD", "linked source provenance has not been reviewed"
    if p.get("status") != "REVIEWED_ALLOW" or p.get("conditions_satisfied") is not True:
        return "SOURCE_RIGHTS_HOLD", "unreviewed/denied permission or unmet conditions"
    if not all(isinstance(p.get(k), str) and p[k].strip() for k in ("reviewer", "evidence_reference")):
        return "SOURCE_RIGHTS_HOLD", "missing reviewer or evidence reference"
    if not isinstance(p.get("evidence_sha256"), str) or not HEX64.fullmatch(p["evidence_sha256"]):
        return "SOURCE_RIGHTS_HOLD", "missing permission evidence digest"
    if not isinstance(p.get("operations"), list) or operation not in p["operations"]:
        return "SOURCE_RIGHTS_HOLD", "operation not explicitly permitted"
    try:
        reviewed, expires = _day(p.get("reviewed_on")), _day(p.get("expires_on"))
        today = on_date or date.today()
        if type(today) is not date or reviewed > today or expires < today or expires < reviewed:
            raise ValueError("expired or future permission review")
    except ValueError:
        return "SOURCE_RIGHTS_HOLD", "missing, invalid, expired or future permission dates"
    return "ALLOW", "reviewed permission matches exact identity, version, route and operation"


def source_preflight(source, operation, *, manifest_path=None, decision_log=None, on_date=None):
    """Return ALLOW only after an append-only decision receipt is durably written.

    The private log must already exist: unavailable or unwritable log is HOLD.
    No source bytes, cache metadata or network are accessed by this function.
    """
    manifest_path = manifest_path or os.getenv("SYNTHESIS_SOURCE_RIGHTS_MANIFEST")
    decision_log = decision_log or os.getenv("SYNTHESIS_SOURCE_ACCESS_LOG")
    manifest, manifest_digest = None, None
    try:
        raw = Path(manifest_path).read_bytes() if manifest_path else None
        if raw:
            manifest_digest = sha256(raw).hexdigest()
            manifest = json.loads(raw)
    except (OSError, ValueError, TypeError):
        pass
    outcome, reason = assess_source(manifest, source, operation, on_date=on_date)
    matched_permission = None
    if outcome == "ALLOW":
        # Bind the successful decision to the precise reviewed permission
        # evidence; do not expose these private details in public CI logs.
        matches = [p for p in manifest["permissions"]
                   if isinstance(p, dict) and _doi(p.get("doi")) == _doi(source["doi"])
                   and p.get("version") == source["version"]
                   and p.get("resource_ref") == source["resource_ref"]
                   and p.get("access_route") == source["access_route"]]
        if len(matches) == 1:
            matched_permission = matches[0]
    receipt = {"when_utc": datetime.now(timezone.utc).isoformat(),
               "policy": SOURCE_POLICY, "policy_sha256": sha256(SOURCE_POLICY.encode()).hexdigest(),
               "manifest_sha256": manifest_digest, "doi": _doi(source.get("doi")) if isinstance(source, dict) else "",
               "version": source.get("version") if isinstance(source, dict) else None,
               "resource_ref": source.get("resource_ref") if isinstance(source, dict) else None,
               "access_route": source.get("access_route") if isinstance(source, dict) else None,
               "operation": operation, "decision": outcome, "reason": reason,
               **({key: matched_permission.get(key) for key in
                   ("evidence_reference", "evidence_sha256", "reviewer", "reviewed_on", "expires_on")}
                  if matched_permission else {})}
    if not decision_log:
        return {**receipt, "decision": "SOURCE_RIGHTS_HOLD", "reason": "private decision log unavailable"}
    try:
        path = Path(decision_log)
        if not path.is_file():
            raise OSError("decision log must pre-exist")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        return {**receipt, "decision": "SOURCE_RIGHTS_HOLD", "reason": "private decision log missing/unwritable"}
    return receipt


def require_source_allowed(source, operation, *, manifest_path=None, decision_log=None, on_date=None):
    """Use directly before the source I/O operation; never on a warm cache hit only."""
    decision = source_preflight(source, operation, manifest_path=manifest_path,
                                decision_log=decision_log, on_date=on_date)
    if decision["decision"] != "ALLOW":
        raise PermissionError("SOURCE_RIGHTS_HOLD: " + decision["reason"])
    return decision


def execute_source_action(source, operation, action, *, manifest_path=None, decision_log=None, on_date=None):
    """Guard a supplied read/replay/network callback; never invoke it on HOLD."""
    require_source_allowed(source, operation, manifest_path=manifest_path,
                           decision_log=decision_log, on_date=on_date)
    return action()


def _norm(value):
    return " ".join(value.casefold().strip().split()) if isinstance(value, str) else ""


def _title_key(value):
    return " ".join(re.findall(r"[a-z0-9]+", _norm(value)))


def _recipient_keys(value):
    """Match normalized recipient names, display-name aliases, and mailboxes.

    A withheld correspondent may appear under a previously unseen mailbox.
    Checking only the complete formatted recipient or mailbox can miss an
    excluded name, including when the recipient is routed indirectly.
    """
    if not isinstance(value, str):
        return set()
    # A single transport field may contain several comma-separated
    # mailboxes. parseaddr only sees one (or rejects the whole header), so a
    # protected second recipient could otherwise be missed. Parse every
    # address, preserving quoted commas inside display names.
    keys = {_norm(value)}
    for display, mailbox in getaddresses([value]):
        if "@" in mailbox:
            keys.add(_norm(mailbox))
            if display:
                keys.add(_norm(display))
    return {key for key in keys if key}


def outgoing_blockers(message, exclusions=None):
    """Inspect all recipients/aliases and publication/thread IDs, without a send."""
    reasons = ["PROGRAMME_OUTGOING_QUERY_PAUSE"] if OUTGOING_PAUSED else []
    if not isinstance(message, dict) or not isinstance(exclusions, list):
        return reasons + ["CONTACT_BLOCKED_NO_CONTACT: exclusions unavailable"]
    identities = set()
    for k in ("to", "cc", "bcc", "indirect_recipients"):
        val = message.get(k, [])
        if not isinstance(val, list) or any(not isinstance(x, str) for x in val):
            return reasons + ["CONTACT_BLOCKED_NO_CONTACT: invalid recipient list"]
        for recipient in val:
            identities.update(_recipient_keys(recipient))
    names = message.get("recipient_names", [])
    if not isinstance(names, list) or any(not isinstance(x, str) for x in names):
        return reasons + ["CONTACT_BLOCKED_NO_CONTACT: invalid names"]
    identities.update(_norm(x) for x in names)
    collections = ("related_dois", "related_titles", "related_trial_families")
    if any(not isinstance(message.get(k, []), list) or
           any(not isinstance(x, str) for x in message.get(k, [])) for k in collections):
        return reasons + ["CONTACT_BLOCKED_NO_CONTACT: malformed publication identifiers"]
    dois = {_doi(v) for v in (message.get("doi"), *message.get("related_dois", []))} - {""}
    titles = {_title_key(v) for v in (message.get("title"), *message.get("related_titles", []))} - {""}
    families = {_title_key(v) for v in (message.get("trial_family"), *message.get("related_trial_families", []))} - {""}
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            reasons.append("CONTACT_BLOCKED_NO_CONTACT: invalid exclusion")
            continue
        fields = ("names", "aliases", "emails", "coauthors", "dois", "threads", "titles", "trial_families")
        if any(not isinstance(exclusion.get(k, []), list) or
               any(not isinstance(x, str) for x in exclusion.get(k, [])) for k in fields):
            reasons.append("CONTACT_BLOCKED_NO_CONTACT: malformed exclusion")
            continue
        blocked_identities = set()
        for k in ("names", "aliases", "emails", "coauthors"):
            for x in exclusion.get(k, []):
                blocked_identities.update(_recipient_keys(x))
        blocked_dois = {_doi(x) for x in exclusion.get("dois", [])} - {""}
        blocked_titles = {_title_key(x) for x in exclusion.get("titles", [])} - {""}
        blocked_families = {_title_key(x) for x in exclusion.get("trial_families", [])} - {""}
        thread = _norm(message.get("thread_id"))
        if ((identities & blocked_identities) or (dois & blocked_dois) or
                (titles & blocked_titles) or (families & blocked_families) or
                (thread and thread in {_norm(x) for x in exclusion.get("threads", [])})):
            reasons.append("CONTACT_BLOCKED_NO_CONTACT: recipient/publication/thread exclusion")
    return reasons


def require_outgoing_allowed(message, exclusions=None):
    reasons = outgoing_blockers(message, exclusions)
    if reasons:
        raise PermissionError("; ".join(reasons))
    return True