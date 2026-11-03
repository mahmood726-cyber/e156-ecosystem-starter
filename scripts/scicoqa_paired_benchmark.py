#!/usr/bin/env python3
"""Offline, source-blinded prompt-pair preparation and adjudication accounting.

Does not download articles, invoke an LLM, judge scientific truth, or email authors.
External model inference must consume the frozen prompts without truncation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from string import Template

ARMS = ("baseline", "synthesis")
SCHEMA = "synthesis-scicoqa-paired-v1"
CONTEXT_FIELDS = {"case_id", "split", "paper_version", "code_commit", "paper_text", "code_text"}
COMMIT = re.compile(r"[0-9a-fA-F]{40}")


class BenchmarkError(ValueError):
    """Preconditions for an interpretable paired comparison failed."""


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkError(f"{path}:{number} is not JSON") from exc
        if not isinstance(record, dict):
            raise BenchmarkError(f"{path}:{number} must be an object")
        rows.append(record)
    if not rows:
        raise BenchmarkError(f"{path} contains no records")
    return rows


def nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkError(f"{name} must be nonempty text")
    return value


def unique(rows: list[dict], field: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        key = nonempty(row.get(field), field)
        if key in result:
            raise BenchmarkError(f"duplicate {field}: {key}")
        result[key] = row
    return result


def upstream_plain_prompt(path: Path) -> str:
    """Read the verbatim YAML literal for SciCoQA discrepancy_generation, no YAML dependency."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    marker = "  discrepancy_generation: |"
    starts = [i for i, line in enumerate(lines) if line.rstrip() == marker]
    if len(starts) != 1:
        raise BenchmarkError("expected exactly one upstream discrepancy_generation: | block")
    block = []
    for line in lines[starts[0] + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        block.append(line[4:] if line.startswith("    ") else line)
    text = "".join(block).rstrip("\n") + "\n"
    if text.count("${paper}") != 1 or text.count("${code}") != 1:
        raise BenchmarkError("upstream prompt must contain one paper and one code placeholder")
    return text


def make_prompts(contexts: list[dict], base: str, candidate: str, model: str,
                 model_revision: str, decoding: dict, upstream_ref: str) -> tuple[dict, dict[str, list[dict]]]:
    nonempty(model, "model")
    nonempty(model_revision, "model_revision")
    if not COMMIT.fullmatch(upstream_ref):
        raise BenchmarkError("pin upstream_ref to a 40-character commit")
    for name, prompt in (("baseline", base), ("synthesis", candidate)):
        if prompt.count("${paper}") != 1 or prompt.count("${code}") != 1:
            raise BenchmarkError(f"{name} prompt needs exactly one paper and code placeholder")
    if not isinstance(decoding, dict) or not decoding:
        raise BenchmarkError("decoding_config must be a nonempty JSON object")
    rows = unique(contexts, "case_id")
    manifest = {"schema": SCHEMA, "source": "UKPLab/SciCoQA", "upstream_ref": upstream_ref,
                "model": model, "model_revision": model_revision, "decoding_config": decoding,
                "prompt_template_sha256": {"baseline": digest(base), "synthesis": digest(candidate)},
                "cases": []}
    outputs = {arm: [] for arm in ARMS}
    for case_id, row in sorted(rows.items()):
        if set(row) != CONTEXT_FIELDS:
            raise BenchmarkError(f"{case_id}: inputs must contain only {sorted(CONTEXT_FIELDS)}; no reference labels")
        if row["split"] not in ("real", "synthetic", "pooled", "clean_control"):
            raise BenchmarkError(f"{case_id}: unsupported split")
        paper = nonempty(row["paper_text"], "paper_text")
        code = nonempty(row["code_text"], "code_text")
        version = nonempty(row["paper_version"], "paper_version")
        commit = nonempty(row["code_commit"], "code_commit")
        if not COMMIT.fullmatch(commit):
            raise BenchmarkError(f"{case_id}: code_commit must be a 40-character SHA")
        case = {"case_id": case_id, "split": row["split"], "paper_version": version,
                "code_commit": commit.lower(), "paper_sha256": digest(paper),
                "code_sha256": digest(code), "rendered_prompt_sha256": {}}
        for arm, template in (("baseline", base), ("synthesis", candidate)):
            prompt = Template(template).substitute(paper=paper, code=code)
            sha = digest(prompt)
            case["rendered_prompt_sha256"][arm] = sha
            outputs[arm].append({"case_id": case_id, "arm": arm,
                                  "rendered_prompt_sha256": sha, "prompt": prompt})
        manifest["cases"].append(case)
    return manifest, outputs


def write_prepared(directory: Path, manifest: dict, prompts: dict[str, list[dict]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    filenames = [directory / "manifest.json"] + [directory / f"{a}-prompts.jsonl" for a in ARMS]
    if any(p.exists() for p in filenames):
        raise BenchmarkError("output files already exist; use a new directory to preserve the freeze")
    filenames[0].write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for arm in ARMS:
        (directory / f"{arm}-prompts.jsonl").write_text(
            "".join(canonical(row) + "\n" for row in prompts[arm]), encoding="utf-8")


def proportion(numerator: int, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": round(numerator / denominator, 6) if denominator else None}


def finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise BenchmarkError(f"{label} must be a finite nonnegative number")
    return float(value)


def score(manifest: dict, predictions: list[dict], adjudications: list[dict]) -> dict:
    """Account for *provided* independently reviewed labels, not scientific truth."""
    if manifest.get("schema") != SCHEMA or not manifest.get("cases"):
        raise BenchmarkError("unknown or empty frozen manifest")
    cases = unique(manifest["cases"], "case_id")
    expected = {(cid, arm) for cid in cases for arm in ARMS}
    pred_by_key = {}
    for row in predictions:
        key = (nonempty(row.get("case_id"), "prediction.case_id"), row.get("arm"))
        if key in pred_by_key or key not in expected:
            raise BenchmarkError(f"duplicate or unexpected prediction: {key}")
        if row.get("manifest_sha256") != digest(canonical(manifest)):
            raise BenchmarkError(f"prediction not bound to frozen manifest: {key}")
        if row.get("rendered_prompt_sha256") != cases[key[0]]["rendered_prompt_sha256"][key[1]]:
            raise BenchmarkError(f"wrong prompt hash: {key}")
        if row.get("model") != manifest["model"] or row.get("model_revision") != manifest["model_revision"]:
            raise BenchmarkError(f"model mismatch: {key}")
        if row.get("decoding_config") != manifest["decoding_config"]:
            raise BenchmarkError(f"decoding settings mismatch: {key}")
        if row.get("status") not in ("COMPLETE", "ABSTAIN", "FAILED"):
            raise BenchmarkError(f"invalid inference status: {key}")
        findings = row.get("findings")
        if not isinstance(findings, list):
            raise BenchmarkError(f"findings must be a list: {key}")
        ids = []
        for finding in findings:
            if not isinstance(finding, dict):
                raise BenchmarkError(f"finding must be an object: {key}")
            ids.append(nonempty(finding.get("finding_id"), "finding_id"))
            nonempty(finding.get("text"), "finding text")
        if len(ids) != len(set(ids)) or (row["status"] != "COMPLETE" and findings):
            raise BenchmarkError(f"duplicate findings or nonempty noncomplete output: {key}")
        if "latency_seconds" in row:
            finite_nonnegative(row["latency_seconds"], "latency_seconds")
        pred_by_key[key] = row
    if set(pred_by_key) != expected:
        raise BenchmarkError(f"predictions missing {len(expected - set(pred_by_key))} case-arm outputs; use FAILED/ABSTAIN explicitly")

    reviews = unique(adjudications, "case_id")
    if set(reviews) != set(cases):
        raise BenchmarkError("adjudication must enumerate every case, including unknown/unreviewed")
    stats = {a: {"detected": set(), "matched": 0, "false": 0, "unresolved": 0,
                 "abstain": 0, "failed": 0, "findings": 0, "review_minutes": 0.0,
                 "clean_cases_with_false_alert": 0, "clean_false_alerts": 0} for a in ARMS}
    references = set()
    clean_cases = 0
    unknown_cases = 0
    for cid in sorted(cases):
        item = reviews[cid]
        state = item.get("review_state")
        if state not in ("COMPLETE", "UNKNOWN"):
            raise BenchmarkError(f"{cid}: review_state must be COMPLETE or UNKNOWN")
        if state == "COMPLETE" and (item.get("independently_adjudicated") is not True or
                                     type(item.get("reviewer_count")) is not int or item["reviewer_count"] < 2):
            raise BenchmarkError(f"{cid}: independent two-reviewer attestation missing")
        refs = item.get("reference_ids")
        if not isinstance(refs, list) or any(not isinstance(r, str) or not r.strip() for r in refs):
            raise BenchmarkError(f"{cid}: reference_ids must be a list of nonempty strings")
        if len(set(refs)) != len(refs) or (state == "UNKNOWN" and refs):
            raise BenchmarkError(f"{cid}: invalid reference ID inventory")
        if state == "UNKNOWN":
            unknown_cases += 1
        else:
            references.update((cid, ref) for ref in refs)
            if not refs:
                clean_cases += 1
        reviews_for_arms = item.get("by_arm")
        if not isinstance(reviews_for_arms, dict) or set(reviews_for_arms) != set(ARMS):
            raise BenchmarkError(f"{cid}: require reviews for both arms")
        for arm in ARMS:
            prediction = pred_by_key[(cid, arm)]
            stat = stats[arm]
            stat["abstain"] += prediction["status"] == "ABSTAIN"
            stat["failed"] += prediction["status"] == "FAILED"
            findings = {f["finding_id"] for f in prediction["findings"]}
            stat["findings"] += len(findings)
            review = reviews_for_arms[arm]
            if not isinstance(review, dict):
                raise BenchmarkError(f"{cid}:{arm}: review must be object")
            stat["review_minutes"] += finite_nonnegative(review.get("review_minutes"), "review_minutes")
            matches = review.get("matches")
            false = review.get("false_positive_ids")
            unresolved = review.get("unresolved_ids")
            if not isinstance(matches, list) or not isinstance(false, list) or not isinstance(unresolved, list):
                raise BenchmarkError(f"{cid}:{arm}: adjudication lists required")
            match_ids, matched_refs = [], []
            for link in matches:
                if not isinstance(link, dict):
                    raise BenchmarkError(f"{cid}:{arm}: invalid match")
                match_ids.append(nonempty(link.get("finding_id"), "match.finding_id"))
                matched_refs.append(nonempty(link.get("reference_id"), "match.reference_id"))
            if any(not isinstance(f, str) for f in false + unresolved):
                raise BenchmarkError(f"{cid}:{arm}: bad finding ID")
            reviewed = match_ids + false + unresolved
            if (set(reviewed) != findings or len(reviewed) != len(set(reviewed)) or
                len(matched_refs) != len(set(matched_refs)) or not set(matched_refs).issubset(set(refs))):
                raise BenchmarkError(f"{cid}:{arm}: every finding needs one exclusive judgement, no duplicate reference")
            if state == "UNKNOWN" and (matches or false or set(unresolved) != findings):
                raise BenchmarkError(f"{cid}:{arm}: unknown references cannot produce verified matches/false alarms")
            if state == "COMPLETE":
                stat["detected"].update((cid, ref) for ref in matched_refs)
                stat["matched"] += len(matches)
                stat["false"] += len(false)
                stat["unresolved"] += len(unresolved)
                if not refs:
                    stat["clean_false_alerts"] += len(false)
                    stat["clean_cases_with_false_alert"] += bool(false)
            else:
                stat["unresolved"] += len(unresolved)

    outcome = {"schema": "synthesis-scicoqa-adjudicated-summary-v1",
               "interpretation": "conditional on caller-supplied independent adjudication; this script does not verify sources",
               "case_count": len(cases), "reference_error_count": len(references),
               "verified_clean_case_count": clean_cases, "unknown_reference_case_count": unknown_cases,
               "arms": {}}
    for arm in ARMS:
        s = stats[arm]
        outcome["arms"][arm] = {
            "full_reference_recall_including_abstentions_and_failures": proportion(len(s["detected"]), len(references)),
            "adjudicated_flag_precision_excluding_unresolved": proportion(s["matched"], s["matched"] + s["false"]),
            "false_alerts_per_100_verified_clean_cases": proportion(s["clean_false_alerts"] * 100, clean_cases),
            "clean_cases_with_any_false_alert_per_100": proportion(s["clean_cases_with_false_alert"] * 100, clean_cases),
            "total_findings": s["findings"], "unresolved_findings": s["unresolved"],
            "abstained_cases": s["abstain"], "failed_cases": s["failed"],
            "total_reviewer_minutes": round(s["review_minutes"], 2)}
    baseline, synthesis = stats["baseline"]["detected"], stats["synthesis"]["detected"]
    outcome["paired"] = {
        "baseline_only_reference_detections": len(baseline - synthesis),
        "synthesis_only_reference_detections": len(synthesis - baseline),
        "both_reference_detections": len(baseline & synthesis),
        "neither_reference_detections": len(references - (baseline | synthesis)),
        "recall_difference_synthesis_minus_baseline": (
            round((len(synthesis) - len(baseline)) / len(references), 6) if references else None),
        "confidence_interval": None,
        "note": "Descriptive paired counts only; cluster-aware uncertainty and external validation not supplied."}
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    make = sub.add_parser("prepare", help="freeze one set of paper/code contexts for two prompt arms")
    for opt in ("contexts", "upstream-prompts", "synthesis-prompt", "out-dir"):
        make.add_argument("--" + opt, required=True, type=Path)
    for opt in ("model", "model-revision", "decoding-config", "upstream-ref"):
        make.add_argument("--" + opt, required=True)
    evaluate = sub.add_parser("score", help="summarise externally produced, independently adjudicated runs")
    for opt in ("manifest", "predictions", "adjudications"):
        evaluate.add_argument("--" + opt, required=True, type=Path)
    evaluate.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.cmd == "prepare":
            decoding = json.loads(args.decoding_config)
            manifest, rendered = make_prompts(read_jsonl(args.contexts),
                                              upstream_plain_prompt(args.upstream_prompts),
                                              args.synthesis_prompt.read_text(encoding="utf-8"),
                                              args.model, args.model_revision, decoding, args.upstream_ref)
            write_prepared(args.out_dir, manifest, rendered)
            print(f"Prepared {len(manifest['cases'])} cases in {args.out_dir}; no model inference performed")
        else:
            result = score(json.loads(args.manifest.read_text(encoding="utf-8")),
                           read_jsonl(args.predictions), read_jsonl(args.adjudications))
            payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                if args.output.exists():
                    raise BenchmarkError("refusing to overwrite existing evaluation output")
                args.output.write_text(payload, encoding="utf-8")
            print(payload, end="")
    except (BenchmarkError, OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()