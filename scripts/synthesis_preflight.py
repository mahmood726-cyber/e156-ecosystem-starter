#!/usr/bin/env python3
"""Synthesis Preflight v1.1: local, no-network audit packet validator.

This checks the integrity of reported evidence and runs modest deterministic
consistency tests; it neither uses an LLM nor establishes scientific truth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SUPPORT = {"SUPPORTED", "CONTRADICTED", "OVERGENERALIZED", "UNSUPPORTED_CITATION",
           "SOURCE_UNAVAILABLE", "NOT_ENOUGH_INFO"}
MATURITY = {"SCREENED", "SOURCE_BACKED", "REPRODUCED", "INDEPENDENTLY_ADJUDICATED"}
DISPOSITIONS = {"FLAG", "RECONCILED", "DISCUSSION", "HOLD", "NO_FLAG"}
PRIORITIES = {"P1", "P2", "P3", "P4"}
CALC_KINDS = {"count_percent", "arm_total", "ci_bounds", "raw_rr", "infusion_rate"}
SOURCE_ACCESS = {"ACCESSIBLE", "UNAVAILABLE", "UNKNOWN"}


def digest_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_num(v: Any) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("nonnumeric or boolean input")
    try:
        n = float(v)
    except (ValueError, OverflowError):
        raise ValueError("numeric input cannot be represented finitely") from None
    if not math.isfinite(n):
        raise ValueError("nonfinite input")
    return n


def _check_one(check: dict) -> dict:
    """WARN means compare source/estimand; never auto-adjudicates a paper."""
    kind = check.get("kind")
    result = {"check_id": check.get("id"), "claim_id": check.get("claim_id"),
              "kind": kind, "status": "INVALID", "detail": ""}
    if not isinstance(kind, str) or kind not in CALC_KINDS:
        result["detail"] = "Unknown deterministic check"
        return result
    # Every check needs matching analysis populations/timepoint and compatible estimator.
    if check.get("same_population") is not True or check.get("same_time_window") is not True:
        result.update(status="NOT_COMPARABLE", detail="Population or time window differs/unknown")
        return result
    try:
        tolerance = _safe_num(check.get("tolerance", 0.1))
        if tolerance < 0:
            raise ValueError("negative tolerance")
        if kind == "count_percent":
            if check.get("measure") != "raw_percent":
                result.update(status="NOT_COMPARABLE", detail="Not a crude/raw proportion (may be KM/adjusted)")
                return result
            n, den, stated = (_safe_num(check[k]) for k in ("events", "denominator", "reported_percent"))
            if den <= 0 or n < 0 or n > den:
                raise ValueError("invalid participant counts")
            computed = 100*n/den
        elif kind == "arm_total":
            arms = check.get("arms")
            if not isinstance(arms, list) or not arms:
                raise ValueError("arms must be a nonempty list")
            values = [_safe_num(v) for v in arms]
            if any(v < 0 for v in values):
                raise ValueError("negative group count")
            computed, stated = sum(values), _safe_num(check["reported_total"])
        elif kind == "ci_bounds":
            low, point, high = (_safe_num(check[k]) for k in ("lower", "estimate", "upper"))
            if check.get("interval_type") not in ("conventional_two_sided", "reported_two_sided"):
                result.update(status="NOT_COMPARABLE", detail="Interval definition not known/compatible")
                return result
            result.update(status="CONSISTENT" if low <= point <= high else "REVIEW",
                          detail="Interval contains estimate" if low <= point <= high else "Interval bounds exclude estimate or are reversed",
                          computed={"lower":low,"estimate":point,"upper":high})
            return result
        elif kind == "raw_rr":
            if check.get("measure") != "crude_unadjusted_rr" or check.get("adjusted") is not False:
                result.update(status="NOT_COMPARABLE", detail="Adjusted/stratified/survival estimator cannot be checked as crude RR")
                return result
            a, n1, c, n0, stated = (_safe_num(check[k]) for k in
                                    ("intervention_events", "intervention_n", "control_events", "control_n", "reported_rr"))
            if min(n1,n0) <= 0 or min(a,c) < 0 or a > n1 or c > n0:
                raise ValueError("invalid RR event/denominator inputs")
            if c == 0:
                result.update(status="NOT_COMPARABLE", detail="Zero comparator event cell; method-specific correction needed")
                return result
            computed = (a/n1)/(c/n0)
        else:  # infusion_rate
            conc, vol, stated = (_safe_num(check[k]) for k in
                                  ("concentration_mg_per_ml", "volume_ml_per_min", "reported_mg_per_min"))
            if min(conc,vol) < 0:
                raise ValueError("negative concentration/flow")
            computed = conc*vol
        difference = abs(computed-stated)
        result.update(status="CONSISTENT" if difference <= tolerance else "REVIEW",
                      detail="Within declared tolerance" if difference <= tolerance else "Arithmetic discrepancy; check units/estimand/source before proposing error",
                      computed=computed, stated=stated, difference=difference, tolerance=tolerance)
    except (ValueError, KeyError, TypeError) as exc:
        result["detail"] = f"Invalid/missing inputs: {exc}"
    return result


def review_packet(packet: dict, prompt_sha256: str, input_sha256: str) -> dict:
    problems: list[dict] = []
    def warn(code: str, message: str, claim_id: str | None = None) -> None:
        problems.append({"code": code, "claim_id": claim_id, "detail": message})
    if not isinstance(packet, dict):
        return {"intake_valid": False, "problems": [{"code":"INVALID_PACKET","detail":"Root must be object"}]}
    if packet.get("schema_version") != "1.1":
        warn("UNSUPPORTED_PACKET_SCHEMA", "Packet schema_version must match validator v1.1")
    run = packet.get("run", {})
    if not isinstance(run, dict):
        run={}
    if run.get("prompt_sha256") != prompt_sha256:
        warn("PROMPT_SHA_MISMATCH", "Run must bind the SHA-256 of the supplied prompt bytes")
    if not run.get("run_id") or not isinstance(run.get("run_id"),str):
        warn("MISSING_RUN_ID", "A stable run ID is required")
    if not run.get("model_id") or not run.get("model_provider"):
        warn("MODEL_PROVENANCE_INCOMPLETE", "Record model/provider, or explicitly 'none' for manual checking")
    if not isinstance(run.get("tool_versions"),dict):
        warn("TOOL_PROVENANCE_INCOMPLETE", "Explicit tools and their versions are required, even if none")
    doc = packet.get("document",{})
    if not isinstance(doc, dict) or not doc.get("identifier") or not doc.get("version"):
        warn("DOCUMENT_VERSION_INCOMPLETE", "Document identifier and edition/version must be recorded")
    sources=packet.get("sources",[])
    if not isinstance(sources,list):
        warn("SOURCES_NOT_LIST", "Sources must be a list")
        sources=[]
    source_map={}
    for s in sources:
        if not isinstance(s,dict) or not isinstance(s.get("id"),str) or not s.get("id") or s["id"] in source_map:
            warn("BAD_SOURCE_ID", "Sources need unique nonempty IDs")
            continue
        source_map[s["id"]]=s
        if s.get("access") not in SOURCE_ACCESS:
            warn("BAD_SOURCE_ACCESS", "Access is ACCESSIBLE, UNAVAILABLE or UNKNOWN")
        if s.get("access")=="ACCESSIBLE" and not (s.get("version") and s.get("retrieval_path") and s.get("retrieved_at") and s.get("locator")):
            warn("SOURCE_PROVENANCE_INCOMPLETE", f"Accessible source {s['id']} lacks edition, retrieval, date or locator")
    claims=packet.get("claims",[])
    if not isinstance(claims,list) or not claims:
        warn("CLAIMS_MISSING", "All checkable claims, including unflagged, must be recorded")
        claims=[]
    claim_ids=set()
    views=[]
    for claim in claims:
        if not isinstance(claim,dict):
            warn("BAD_CLAIM", "Claim must be an object")
            continue
        cid=claim.get("id")
        if not isinstance(cid,str) or not cid or cid in claim_ids:
            warn("DUPLICATE_OR_MISSING_CLAIM_ID", "Claim IDs must be nonempty and unique",str(cid))
            continue
        claim_ids.add(cid)
        support=claim.get("source_support")
        maturity=claim.get("evidence_maturity")
        requested=claim.get("proposed_disposition")
        priority=claim.get("priority")
        effective=requested
        reasons=[]
        if not isinstance(support, str) or support not in SUPPORT:
            warn("INVALID_SUPPORT", "Must choose one source-support label",cid)
            reasons.append("invalid source-support label")
        if not isinstance(maturity, str) or maturity not in MATURITY:
            warn("INVALID_MATURITY", "Must choose an evidence maturity label",cid)
            reasons.append("invalid evidence maturity")
        if not isinstance(priority, str) or priority not in PRIORITIES:
            warn("INVALID_PRIORITY", "Use P1/P2/P3/P4",cid)
            reasons.append("invalid priority")
        if not isinstance(requested, str) or requested not in DISPOSITIONS:
            warn("INVALID_DISPOSITION", "Unknown proposed disposition",cid)
            effective="HOLD"
        if not claim.get("locator") or not claim.get("text"):
            warn("CLAIM_LOCATOR_MISSING", "Exact source claim quote and locator required",cid)
            reasons.append("claim or locator missing")
        ids=claim.get("source_ids", [])
        if not isinstance(ids,list):
            warn("BAD_SOURCE_IDS", "source_ids must be a list of source identifiers",cid)
            reasons.append("source_ids is not a list")
            ids=[]
        selected=[source_map[sid] for sid in ids if isinstance(sid,str) and sid in source_map]
        if len(selected)!=len(ids):
            warn("UNKNOWN_SOURCE_REFERENCE", "One or more cited source IDs unavailable",cid)
            reasons.append("unresolved source reference")
        if support == "SOURCE_UNAVAILABLE":
            if not selected or not any(s.get("access")=="UNAVAILABLE" and s.get("retrieval_path") and s.get("retrieval_failures") for s in selected):
                warn("UNAVAILABLE_WITHOUT_ACCESS_LOG", "Log exact source path and retrieval failure",cid)
                reasons.append("unavailable source has no failed access log")
        if support == "NOT_ENOUGH_INFO":
            steps=claim.get("checking_steps")
            if not (selected and any(s.get("access")=="ACCESSIBLE" and s.get("full_text_checked") is True and s.get("version") and s.get("retrieval_path") and s.get("retrieved_at") and s.get("locator") for s in selected)
                    and isinstance(steps,list) and len(steps)>0 and claim.get("stopped_at_step") and claim.get("stalled_reason")):
                warn("INSUFFICIENT_WITHOUT_FULLTEXT_LOG", "Requires actual full text, edition, retrieval, steps and exact stopping point",cid)
                reasons.append("not-enough-info prerequisites absent")
        if maturity == "INDEPENDENTLY_ADJUDICATED":
            rec=claim.get("human_receipt")
            if not isinstance(rec,dict) or rec.get("reviewer_kind")!="independent_human" or not rec.get("receipt_locator") or not rec.get("conflict_check"):
                warn("UNVERIFIED_INDEPENDENCE", "No independent human receipt and conflict check",cid)
                reasons.append("human reviewer independence not established")
        if maturity == "REPRODUCED":
            rec=claim.get("computation_receipt")
            if not isinstance(rec,dict) or not rec.get("exact_input_sha256") or not rec.get("tool_version") or not rec.get("output_locator"):
                warn("UNVERIFIED_REPRODUCTION", "Reproduced requires method, exact input hash, tool version, output locator",cid)
                reasons.append("reproduction receipt missing")
        ref=claim.get("refutation")
        if requested=="FLAG":
            if not isinstance(maturity,str) or maturity not in {"SOURCE_BACKED", "REPRODUCED", "INDEPENDENTLY_ADJUDICATED"}:
                reasons.append("flag has no source-backed maturity")
            if not isinstance(support,str) or support not in {"CONTRADICTED", "OVERGENERALIZED", "UNSUPPORTED_CITATION"}:
                reasons.append("source-support verdict does not justify error flag")
            if not any(s.get("access")=="ACCESSIBLE" and s.get("full_text_checked") is True and s.get("locator") and s.get("version") and s.get("retrieval_path") and s.get("retrieved_at") for s in selected):
                reasons.append("no complete accessible original full-text provenance")
            if not (isinstance(ref,dict) and ref.get("alternative") and ref.get("checked_against") and ref.get("result") == "NOT_SUPPORTED"):
                reasons.append("source-grounded refutation not completed")
        if isinstance(support,str) and support in {"SOURCE_UNAVAILABLE", "NOT_ENOUGH_INFO"} and isinstance(requested,str) and requested in {"NO_FLAG", "RECONCILED"}:
            reasons.append("unresolved or inaccessible evidence cannot establish a negative finding")
        if requested == "NO_FLAG" and isinstance(support,str) and support in {"CONTRADICTED", "OVERGENERALIZED", "UNSUPPORTED_CITATION"}:
            reasons.append("unsupported/contradicted source cannot be classified as verified no-flag")
        if requested == "RECONCILED" and not (isinstance(ref,dict) and ref.get("result") == "SUPPORTED"
                                                   and ref.get("alternative") and ref.get("checked_against")):
            reasons.append("reconciliation requires a specific, source-checked benign explanation")
        if reasons:
            effective="HOLD"
            warn("CLAIM_HELD", "; ".join(reasons),cid)
        views.append({"id":cid,"requested":requested,"effective":effective,"support":support,
                      "maturity":maturity,"priority":priority,"problem_type":claim.get("problem_type"),
                      "locator":claim.get("locator"),"text":claim.get("text"),"reasons":reasons,
                      "source_ids":ids})
    checks=packet.get("deterministic_checks",[])
    if not isinstance(checks,list):
        warn("CHECKS_NOT_LIST", "deterministic_checks must be a list")
        checks=[]
    seen_check_ids=set()
    check_results=[]
    for check in checks:
        if not isinstance(check,dict):
            warn("BAD_CHECK", "Deterministic check must be an object")
            continue
        if not isinstance(check.get("claim_id"),str) or check.get("claim_id") not in claim_ids:
            warn("ORPHAN_CHECK", "Deterministic check must reference a recorded claim",str(check.get("claim_id")))
        check_id=check.get("id")
        if not isinstance(check_id,str) or not check_id or check_id in seen_check_ids:
            warn("DUPLICATE_CHECK_ID", "Deterministic checks need unique string IDs",str(check.get("claim_id")))
        else:
            seen_check_ids.add(check_id)
        result=_check_one(check)
        if result["status"]=="INVALID":
            warn("INVALID_CHECK", result["detail"],str(check.get("claim_id")))
        check_results.append(result)
    rank={"P1":0,"P2":1,"P3":2,"P4":3}
    structural_faults = {
        "UNSUPPORTED_PACKET_SCHEMA", "PROMPT_SHA_MISMATCH", "MISSING_RUN_ID",
        "MODEL_PROVENANCE_INCOMPLETE", "TOOL_PROVENANCE_INCOMPLETE",
        "DOCUMENT_VERSION_INCOMPLETE", "CLAIMS_MISSING", "BAD_CLAIM",
        "DUPLICATE_OR_MISSING_CLAIM_ID", "INVALID_SUPPORT", "INVALID_MATURITY",
        "INVALID_PRIORITY", "INVALID_DISPOSITION", "CLAIM_LOCATOR_MISSING",
        "BAD_SOURCE_ID", "BAD_SOURCE_ACCESS", "SOURCE_PROVENANCE_INCOMPLETE",
        "UNKNOWN_SOURCE_REFERENCE", "UNAVAILABLE_WITHOUT_ACCESS_LOG",
        "INSUFFICIENT_WITHOUT_FULLTEXT_LOG", "UNVERIFIED_INDEPENDENCE",
        "UNVERIFIED_REPRODUCTION", "CHECKS_NOT_LIST", "BAD_CHECK",
        "ORPHAN_CHECK", "DUPLICATE_CHECK_ID", "INVALID_CHECK", "SOURCES_NOT_LIST", "BAD_SOURCE_IDS",
    }
    intake_valid = not any(p["code"] in structural_faults for p in problems)
    if not intake_valid:
        # Invalid input cannot emit an actionable positive OR definitive negative.
        # Keep original proposed dispositions and all evidence for repair/audit.
        for v in views:
            if v["effective"] in {"FLAG", "RECONCILED", "NO_FLAG"}:
                v["effective"] = "HOLD"
                v["reasons"].append("global intake invalid; all decisive outcomes are held")
                warn("GLOBAL_HOLD", "Intake validation failed; no decisive outcome may be promoted",v["id"])
    flag_summary = sorted([v for v in views if v["effective"]=="FLAG"],
                          key=lambda v:(rank.get(v["priority"],4),v["id"]))[:5]
    return {"schema_version":"1.1","intake_valid":intake_valid,
            "prompt_sha256":prompt_sha256,"input_sha256":input_sha256,
            "source_count":len(source_map),"claim_count":len(views),
            "flag_count":sum(v["effective"]=="FLAG" for v in views),
            "hold_count":sum(v["effective"]=="HOLD" for v in views),
            "reconciled_count":sum(v["effective"]=="RECONCILED" for v in views),
            "top_five":flag_summary,"ledger":views,"checks":check_results,"problems":problems,
            "disclaimer":"Structural verification only; no independent scientific accuracy measured. No external actions performed."}


def _markdown(result: dict) -> str:
    def esc(v: Any) -> str:
        return str(v if v is not None else "").replace("|","\\|").replace("\n"," ")
    out=["# Synthesis Preflight — verification receipt", "",result["disclaimer"],"",
         f"Prompt SHA256: `{result['prompt_sha256']}`",f"Input SHA256: `{result['input_sha256']}`", "",
         f"**All claims:** {result['claim_count']} | **Flag candidates permitted:** {result['flag_count']} | **Held:** {result['hold_count']} | **Reconciled:** {result['reconciled_count']}","",
         "## Priority summary (maximum five)","",
         "| Claim | Priority | Location | Source-support | Original proposed disposition |", "|---|---|---|---|---|"]
    for v in result["top_five"]:
        out.append("| "+" | ".join(esc(v.get(k)) for k in ("id","priority","locator","support","requested"))+" |")
    if not result["top_five"]:out.append("| — | — | — | — | No source-backed discrepancy established |")
    out.extend(["", "## Complete, unfiltered claim ledger", "", "| Claim | Priority | Requested | Effective | Support | Maturity |", "|---|---|---|---|---|---|"])
    for v in result["ledger"]:
        out.append("| "+" | ".join(esc(v.get(k)) for k in ("id","priority","requested","effective","support","maturity"))+" |")
    out.extend(["", "## Deterministic checking results (not error adjudications)","", "| Check | Claim | Status | Explanation |", "|---|---|---|---|"])
    for v in result["checks"]:
        out.append("| "+" | ".join(esc(v.get(k)) for k in ("kind","claim_id","status","detail"))+" |")
    out.extend(["", "## Structural issues and blocked promotions",""])
    for x in result["problems"]:
        out.append("- `"+esc(x["code"])+"`"+(" ["+esc(x.get("claim_id"))+"]" if x.get("claim_id") else "")+": "+esc(x["detail"]))
    if not result["problems"]:out.append("No structural refusals; this does not mean that the scientific claims are correct.")
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompt",type=Path,required=True,help="Exact dated prompt text; SHA verified")
    p.add_argument("--packet",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    raw=args.packet.read_bytes()
    packet=json.loads(raw.decode("utf-8"))
    result=review_packet(packet,digest_bytes(args.prompt.read_bytes()),digest_bytes(raw))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"receipt.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (args.output_dir/"report.md").write_text(_markdown(result),encoding="utf-8")
    print(f"Recorded {result['claim_count']} claims, {result['flag_count']} eligible flags, {result['hold_count']} held; receipt: {args.output_dir}/receipt.json")
    return 0 if result["intake_valid"] else 2

if __name__ == "__main__":
    raise SystemExit(main())