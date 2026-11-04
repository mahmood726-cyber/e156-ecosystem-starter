"""Replay the OA assisted source review through Synthesis and its receipt CLI."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

from synthesis_v13_oa_benchmark import ROOT, load_snapshot


FIXTURE = ROOT / "docs" / "synthesis-v13-oa-workflow.json"
PROMPT = ROOT / "docs" / "SYNTHESIS-PREFLIGHT-v1.1.md"
PREFLIGHT = ROOT / "scripts" / "synthesis_preflight.py"
NUMBER_WORDS = dict(zip("zero one two three four five six seven eight nine".split(), range(10)))
NUMBER_WORDS["twice"] = 2


def integer(literal):
    if literal is None:
        return None
    if literal in NUMBER_WORDS:
        return NUMBER_WORDS[literal]
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", literal):
        raise ValueError(f"Unrecognized source count: {literal}")
    return int(literal.replace(",", ""))


def subset(nma, case, paper):
    primary, sensitivity = map(integer, case["reported"])
    primary_loc, sensitivity_loc = case["locators"]
    check = getattr(nma, "restricted_analysis_accounting", None)
    if check is None:
        result = {"status": "UNAVAILABLE", "reason": "subset-count rule absent at this revision"}
    else:
        result = check({
            "source_version": paper["doi"],
            "restriction_locator": sensitivity_loc,
            "primary_locator": primary_loc,
            "restricted_locator": sensitivity_loc,
            "same_source_version_verified": True,
            "relationship": case["relationship"],
            "same_participant_count_basis_verified": case["basis_verified"],
            "primary_participants": primary,
            "restricted_participants": sensitivity,
        })
    result.update(primary=primary, sensitivity=sensitivity)
    return result


def shared_control(nma, checks, case, paper, notice):
    original_loc, notice_loc = case["locators"]
    common = dict(case["control"],
                  source_locator=f"{paper['doi']} / {original_loc}; {notice['doi']} / {notice_loc}")
    result = nma.shared_control_dependence([
        dict(common, comparison_id=contrast) for contrast in ("arm A versus control", "arm B versus control")
    ])
    unique = sum(map(integer, case["split_literals"]))
    original = integer(case["original_reuse_literal"]) * unique
    replacement = f"{notice['doi']} / {notice_loc}"
    closure = checks.gate({
        "severity": "S2",
        "version": "CORRECTED_LATEST",
        "source_access": "ACCESSIBLE",
        "source_locator": f"{paper['doi']} / {original_loc}",
        "current_correction_status": "RESOLVED_IN_PUBLISHED_VERSION",
        "correction_source_verified": True,
        "correction_locator": replacement,
        "corrected_claim_verified": True,
        "corrected_claim_locator": replacement,
    })
    result.update(unique_controls=unique, original_control_entries=original,
                  excess_entries=original - unique, current_correction=closure["status"])
    return result


def receipt_packet(case, paper, notice, result, retrieved_on, revision):
    primary_loc, secondary_loc = case["locators"]
    provenance = [(paper, primary_loc if notice else " / ".join(case["locators"]))]
    if notice:
        provenance.append((notice, secondary_loc))
    sources = [
        {"id": source["doi"], "access": "ACCESSIBLE", "version": source["edition"],
         "retrieval_path": source["url"], "retrieved_at": retrieved_on, "locator": locator,
         "full_text_checked": True}
        for source, locator in provenance
    ]
    status = result["status"]
    text = case["claim"]
    if notice:
        text += (f". The historical fit used {result['original_control_entries']} control entries "
                 f"for {result['unique_controls']} distinct controls.")
    elif result["primary"] is not None and result["sensitivity"] is not None:
        text += f". Reported participant counts were {result['primary']} and {result['sensitivity']}."
    claim = {
        "id": case["id"], "locator": primary_loc, "text": text,
        "source_ids": [source["id"] for source in sources],
        "problem_type": case["check"], "priority": "P2",
        "source_support": "NOT_ENOUGH_INFO", "evidence_maturity": "SCREENED",
        "proposed_disposition": "HOLD",
        "checking_steps": [primary_loc, secondary_loc],
        "stopped_at_step": "Check availability and applicability",
        "stalled_reason": result.get("reason") or result.get("warning") or status,
    }
    if result.get("current_correction") == "RECONCILED":
        claim.update(source_support="SUPPORTED", evidence_maturity="SOURCE_BACKED",
                     proposed_disposition="RECONCILED", refutation={
                         "alternative": "The original overcount has a published exact replacement",
                         "checked_against": f"{notice['doi']} / {secondary_loc}", "result": "SUPPORTED",
                     })
    elif status == "REVIEW_CANDIDATE":
        claim.update(source_support="CONTRADICTED", evidence_maturity="SOURCE_BACKED",
                     proposed_disposition="DISCUSSION")
    elif status in {"NO_FLAG", "NOT_COMPARABLE"}:
        claim.update(source_support="SUPPORTED", evidence_maturity="SOURCE_BACKED",
                     proposed_disposition="NO_FLAG")
    return {
        "schema_version": "1.1",
        "run": {
            "run_id": f"oa-workflow-{revision[:12]}-{case['id']}",
            "model_id": "Codex assisted source review; exact snapshot unavailable",
            "model_provider": "OpenAI",
            "prompt_sha256": sha256(PROMPT.read_bytes()).hexdigest(),
            "tool_versions": {"preflight": "v1.1", "checks_git_revision": revision},
        },
        "document": {"identifier": paper["doi"], "version": paper["edition"]},
        "sources": sources,
        "claims": [claim],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raw = FIXTURE.read_bytes()
    data = json.loads(raw)
    results = []
    for arm in ("baseline", "candidate"):
        revision = data[arm]
        snapshot = data["candidate_tree"] if arm == "candidate" else revision
        nma = load_snapshot(snapshot, "synthesis_v13_nma_preflight")
        checks = load_snapshot(snapshot, "synthesis_v13_checks")
        for case in data["cases"]:
            paper = data["sources"][case["paper"]]
            notice = data["sources"][case["notice"]] if "notice" in case else None
            if case["check"] == "subset_count":
                rule = subset(nma, case, paper)
            elif case["check"] == "shared_control":
                rule = shared_control(nma, checks, case, paper, notice)
            else:
                raise ValueError(f"Unknown check: {case['check']}")
            packet = receipt_packet(case, paper, notice, rule, data["retrieved_on"], revision)
            run_dir = args.output_dir / arm / case["id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            path = run_dir / "packet.json"
            path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            subprocess.run([
                sys.executable, "-B", str(PREFLIGHT), "--prompt", str(PROMPT),
                "--packet", str(path), "--output-dir", str(run_dir),
            ], check=True, stdout=subprocess.DEVNULL)
            receipt = json.loads((run_dir / "receipt.json").read_bytes())
            if (not receipt["intake_valid"] or receipt["input_sha256"] != sha256(path.read_bytes()).hexdigest()
                    or [entry["id"] for entry in receipt["ledger"]] != [case["id"]]):
                raise ValueError(f"Receipt failed verification for {arm} {case['id']}")
            results.append({
                "arm": arm, "id": case["id"], "cohort": case["cohort"], "rule": rule,
                "receipt_disposition": receipt["ledger"][0]["effective"],
                "packet_sha256": receipt["input_sha256"],
            })
            print(arm, case["id"], rule["status"], receipt["ledger"][0]["effective"])
    summary = {"fixture_sha256": sha256(raw).hexdigest(), "results": results}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
