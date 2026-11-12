#!/usr/bin/env python3
"""Offline matched-run validation and masked export; never runs models or proves truth.

All judgments, identity, timestamps, usage and rights remain external evidence.
Budget checks audit recorded consumption; this tool does not enforce runtime caps.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath

if __package__:
    from scripts import synthesis_blind_eval as blind
    from scripts.component_source import linked
else:
    import synthesis_blind_eval as blind
    from component_source import linked

Refused = blind.EvaluationError
digest = blind.sha256_json
STATUSES = {"COMPLETE", "FAILED", "TIMEOUT", "NOT_ATTEMPTED"}
LIMITS = {"wall_seconds", "model_tokens", "tool_calls", "api_cost_usd", "review_seconds"}
USAGE = {"model_tokens", "tool_calls", "api_cost_usd", "human_review_cost_usd"}


def _need(condition, message):
    if not condition:
        raise Refused(message)


def _text(value, field):
    return blind._text(value, field)


def _hash(value, field):
    _need(bool(blind.HEX64.fullmatch(_text(value, field))), f"invalid {field}")


def _number(value, field, *, integer=False):
    _need(not isinstance(value, bool) and isinstance(value, int if integer else (int, float)),
          f"{field} must be numeric")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _need(finite and value >= 0, f"invalid {field}")
    return value


def _sum(values):
    try:
        total = math.fsum(values)
    except OverflowError as exc:
        raise Refused("measurement total overflow") from exc
    return _number(total, "measurement total")


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_constant(value):
    raise Refused(f"nonfinite JSON constant: {value}")


def _labels(value):
    if isinstance(value, dict):
        _need(not (blind.FORBIDDEN_LABEL_KEYS | {"flag_root_match"}).intersection(value),
              "answer fields in public protocol, manifest or run records")
        for item in value.values():
            _labels(item)
    elif isinstance(value, list):
        for item in value:
            _labels(item)


def _index(rows, field):
    _need(isinstance(rows, list) and rows, f"nonempty {field} list required")
    result = {}
    for row in rows:
        _need(isinstance(row, dict), f"{field} entry must be object")
        key = _text(row.get(field), field)
        _need(key == row[field] and key not in result, f"duplicate/noncanonical {field}")
        result[key] = row
    return result


def _file(root, name, expected):
    """Check a relative regular file without following links/junctions."""
    raw = _text(name, "input_file")
    relative = PurePosixPath(raw)
    _need(not relative.is_absolute() and ".." not in relative.parts
          and "\\" not in raw and ":" not in raw and relative.parts,
          "input_file must remain within inputs root")
    _hash(expected, "input_sha256")
    root = Path(root).absolute()
    _need(root.is_dir(), "inputs root missing")
    for parent in (root, *root.parents):
        _need(not linked(parent), "linked inputs root refused")
    target = root
    for part in relative.parts:
        target = target / part
        _need(target.exists(), f"input file missing: {raw}")
        _need(not linked(target), "linked input refused")
    _need(target.is_file(), f"input file missing: {raw}")
    _need(hashlib.sha256(target.read_bytes()).hexdigest() == expected, f"input bytes changed: {raw}")


def prepare(manifest, protocol, inputs):
    """Validate a supplied protocol; do not manufacture a cohort or approval."""
    _need(isinstance(protocol, dict) and protocol.get("schema") == "synthesis-matched-protocol-v1",
          "protocol schema mismatch")
    _need(isinstance(manifest, dict), "manifest must be object")
    _labels(protocol)
    _labels(manifest)
    _need(protocol.get("manifest_sha256") == digest(manifest), "manifest binding mismatch")
    _need(protocol.get("purpose") in {"synthetic_contract", "prospective"}, "explicit purpose required")
    _need(protocol.get("comparison_kind") in {"harness_only", "system"}, "comparison_kind required")
    _need(protocol.get("retry_policy") == "one_record_all_internal_attempts", "unsupported retry policy")
    _number(protocol.get("order_seed"), "order_seed", integer=True)
    _text(protocol.get("analysis_plan_reference"), "analysis_plan_reference")
    frozen = blind._timestamp(protocol.get("frozen_at"), "protocol.frozen_at")
    _need(frozen >= blind._timestamp(manifest.get("frozen_at"), "manifest.frozen_at"),
          "protocol predates manifest")
    if protocol["purpose"] == "prospective":
        for field in ("custodian_receipt_reference", "independent_review_plan_reference",
                      "unseen_corpus_receipt_reference"):
            _text(protocol.get(field), field)
        # These are required references, never authenticated human approval.
    arms = _index(protocol.get("arms"), "arm_id")
    _need(len(arms) >= 2, "at least two arms required")
    for arm in arms.values():
        for field in ("runtime", "runtime_version", "model_snapshot"):
            _text(arm.get(field), field)
        for field in ("config_sha256", "model_config_sha256", "tools_sha256"):
            _hash(arm.get(field), field)
    _need(len({x["tools_sha256"] for x in arms.values()}) == 1, "unequal tool/access contracts")
    if protocol["comparison_kind"] == "harness_only":
        _need(len({x["model_snapshot"] for x in arms.values()}) == 1, "harness-only requires identical model")
        _need(len({x["model_config_sha256"] for x in arms.values()}) == 1,
              "harness-only requires identical model decoding settings")
    limits = protocol.get("limits")
    _need(isinstance(limits, dict) and set(limits) == LIMITS, "common explicit limits required")
    for field, value in limits.items():
        _number(value, field, integer=field in {"model_tokens", "tool_calls"})
    tasks = _index(protocol.get("tasks"), "claim_id")
    claims = _index(manifest.get("claims"), "claim_id")
    _need(set(tasks) == {cid for cid, c in claims.items() if c.get("split") == "test"},
          "task inventory must equal frozen test claim inventory")
    for task in tasks.values():
        _text(task.get("oa_rights_reference"), "oa_rights_reference")
        _file(inputs, task.get("input_file"), task.get("input_sha256"))
        sources = task.get("source_files")
        _need(isinstance(sources, list), "explicit source_files inventory required")
        indexed = _index(sources, "file") if sources else {}
        for source in indexed.values():
            _file(inputs, source["file"], source.get("sha256"))
        claim = claims[task["claim_id"]]
        if claim.get("original_state") == "VERIFIED_ORIGINAL":
            _need(claim.get("original_sha256") in {s["sha256"] for s in indexed.values()},
                  "verified original not bound to checked source files")
    # Exercise the existing family/source/manifest validator without pretending
    # preparation produced real predictions. This temporary document is not exported.
    check = {"schema": "synthesis-predictions-v1", "manifest_sha256": digest(manifest),
             "frozen_at": protocol["frozen_at"], "predictions": [
                 {"claim_id": cid, "disposition": "ABSTAIN", "stop_point": "schema validation only",
                  "predicted_at": protocol["frozen_at"], "review_seconds": 0} for cid in tasks]}
    blind.evaluate(manifest, check)
    schedule = [{"claim_id": cid, "arm_id": aid} for cid in tasks for aid in arms]
    schedule.sort(key=lambda row: digest({"seed": protocol["order_seed"], **row}))
    return {"schema": "synthesis-matched-preparation-v1", "status": "PREPARED_NOT_RUN",
            "purpose": protocol["purpose"], "protocol_sha256": digest(protocol),
            "schedule": schedule, "scientific_results": None,
            "warning": "File consistency only; source rights, custody and independence need external verification."}


def _validated(manifest, protocol, runs, inputs):
    prepare(manifest, protocol, inputs)
    _need(isinstance(runs, dict) and runs.get("schema") == "synthesis-matched-runs-v1", "run schema mismatch")
    _labels(runs)
    _need(runs.get("protocol_sha256") == digest(protocol), "run protocol binding mismatch")
    start = blind._timestamp(protocol["frozen_at"], "protocol.frozen_at")
    end = blind._timestamp(runs.get("frozen_at"), "runs.frozen_at")
    _need(end >= start, "run freeze predates protocol")
    arms = _index(protocol["arms"], "arm_id")
    tasks = _index(protocol["tasks"], "claim_id")
    records, predictions, issues = {}, {}, []
    _need(isinstance(runs.get("records"), list), "records must be list")
    for row in runs["records"]:
        _need(isinstance(row, dict), "run record must be object")
        aid, cid = _text(row.get("arm_id"), "arm_id"), _text(row.get("claim_id"), "claim_id")
        _need(aid in arms and cid in tasks and (aid, cid) not in records, "unknown/duplicate case-arm")
        _need(row.get("arm_sha256") == digest(arms[aid]), "run arm/config binding mismatch")
        _need(row.get("input_sha256") == tasks[cid]["input_sha256"], "run input binding mismatch")
        _need(row.get("status") in STATUSES, "unknown run status")
        began = blind._timestamp(row.get("started_at"), "started_at")
        ended = blind._timestamp(row.get("ended_at"), "ended_at")
        _need(start <= began <= ended <= end, "run outside frozen pre-reveal window")
        _number(row.get("wall_seconds"), "wall_seconds")
        _number(row.get("internal_attempts"), "internal_attempts", integer=True)
        _need((row["internal_attempts"] == 0) == (row["status"] == "NOT_ATTEMPTED"),
              "attempt count contradicts run status")
        _text(row.get("record_evidence_reference"), "record_evidence_reference")
        _hash(row.get("record_evidence_sha256"), "record_evidence_sha256")
        prediction = row.get("prediction")
        _need(isinstance(prediction, dict), "prediction must be object")
        allowed = {"disposition", "review_seconds", "flag_root_id", "evidence_locator", "stop_point"}
        _need(set(prediction) <= allowed, "unexpected prediction field")
        _number(prediction.get("review_seconds"), "review_seconds")
        if row["status"] != "COMPLETE":
            _need(prediction.get("disposition") == "ABSTAIN", "failed/unattempted run must abstain")
        usage = row.get("usage")
        _need(isinstance(usage, dict) and set(usage) == USAGE, "explicit usage fields required (null if unavailable)")
        for field, value in usage.items():
            if value is not None:
                _number(value, field, integer=field in {"model_tokens", "tool_calls"})
        consumption = {**usage, "wall_seconds": row["wall_seconds"], "review_seconds": prediction["review_seconds"]}
        for field, limit in protocol["limits"].items():
            value = consumption[field]
            if value is None or value > limit:
                issues.append({"arm_id": aid, "claim_id": cid, "resource": field,
                               "status": "UNVERIFIED" if value is None else "VIOLATION"})
        records[aid, cid] = row
    _need(set(records) == set(itertools.product(arms, tasks)), "missing prespecified case-arm records")
    for aid in sorted(arms):
        predictions[aid] = {"schema": "synthesis-predictions-v1", "manifest_sha256": digest(manifest),
                            "frozen_at": runs["frozen_at"], "predictions": [
                                {"claim_id": cid, "predicted_at": records[aid, cid]["ended_at"],
                                 **records[aid, cid]["prediction"]} for cid in sorted(tasks)]}
        blind.evaluate(manifest, predictions[aid])
    return records, predictions, issues


def _sample(runs, aid, cid):
    return digest({"runs_sha256": digest(runs), "arm_id": aid, "claim_id": cid})


def _masked(protocol, runs, records):
    samples = []
    for (aid, cid), row in records.items():
        sample = {"sample_id": _sample(runs, aid, cid), "claim_id": cid,
                  "input_sha256": row["input_sha256"]}
        for field in ("disposition", "flag_root_id", "evidence_locator", "stop_point"):
            if field in row["prediction"]:
                sample[field] = row["prediction"][field]
        samples.append(sample)
    return {"schema": "synthesis-matched-masked-v1", "purpose": protocol["purpose"],
            "samples": sorted(samples, key=lambda row: row["sample_id"])}


def mask(manifest, protocol, runs, inputs):
    records, _, _ = _validated(manifest, protocol, runs, inputs)
    return _masked(protocol, runs, records)


def _total(rows, field):
    values = [row["usage"][field] for row in rows]
    missing = sum(value is None for value in values)
    observed = _sum(value for value in values if value is not None)
    return {"total": None if missing else observed, "observed_subtotal": observed, "missing_records": missing}


def _paired(cases, left, right, truths):
    result = {}
    for endpoint, truth in (("error_root_detection", "ERROR"), ("negative_claim_false_alert", "NO_ERROR"), ("abstention", None)):
        counts = dict.fromkeys(("both", "left_only", "right_only", "neither"), 0)
        for cid in cases:
            if truth is not None and truths[cid] != truth:
                continue
            def outcome(row):
                if endpoint == "abstention":
                    return row["disposition"] == "ABSTAIN"
                return row["disposition"] == "FLAG" and (endpoint == "negative_claim_false_alert" or row["flag_root_match"])
            a, b = outcome(left[cid]), outcome(right[cid])
            counts["both" if a and b else "left_only" if a else "right_only" if b else "neither"] += 1
        n = sum(counts.values())
        result[endpoint] = {**counts, "denominator": n,
                            "rate_difference_left_minus_right": (counts["left_only"] - counts["right_only"]) / n if n else None}
    return result


def compare(manifest, protocol, runs, inputs, adjudications=None):
    records, predictions, issues = _validated(manifest, protocol, runs, inputs)
    judgments, scored_rows, truths = {}, {}, {}
    if adjudications is not None:
        _need(isinstance(adjudications, dict) and adjudications.get("schema") == "synthesis-matched-adjudications-v1",
              "adjudication schema mismatch")
        _need(adjudications.get("masked_packet_sha256") == digest(_masked(protocol, runs, records)), "masked packet binding mismatch")
        indexed = _index(adjudications.get("adjudications"), "sample_id")
        _need(set(indexed) == {_sample(runs, aid, cid) for aid, cid in records}, "incomplete masked adjudications")
        for aid in predictions:
            rows, scored_rows[aid] = [], {}
            for cid in sorted(k[1] for k in records if k[0] == aid):
                row = {k: v for k, v in indexed[_sample(runs, aid, cid)].items() if k != "sample_id"}
                row["claim_id"] = cid
                if cid in truths:
                    _need(truths[cid] == row.get("truth"), "reference truth differs across arms")
                truths[cid] = row.get("truth")
                rows.append(row)
                scored_rows[aid][cid] = {**records[aid, cid]["prediction"], "flag_root_match": row.get("flag_root_match")}
            judgments[aid] = {"schema": "synthesis-adjudications-v1", "prediction_sha256": digest(predictions[aid]),
                              "adjudications": rows}
    arms = {}
    for aid, prediction in predictions.items():
        rows = [row for (arm, _), row in records.items() if arm == aid]
        arms[aid] = {"evaluation": blind.evaluate(manifest, prediction, judgments.get(aid)),
                     "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
                     "wall_seconds": _sum(row["wall_seconds"] for row in rows),
                     "review_seconds": _sum(row["prediction"]["review_seconds"] for row in rows),
                     "internal_attempts": sum(row["internal_attempts"] for row in rows),
                     "costs": {f: _total(rows, f) for f in ("api_cost_usd", "human_review_cost_usd")}}
    paired = None
    if adjudications is not None:
        families = {}
        for case in manifest["claims"]:
            if case["split"] == "test":
                families.setdefault(case["family_id"], []).append(case["claim_id"])
        paired = []
        for left, right in itertools.combinations(sorted(arms), 2):
            paired.append({"left": left, "right": right,
                           **_paired(truths, scored_rows[left], scored_rows[right], truths),
                           "families": {family: _paired(cids, scored_rows[left], scored_rows[right], truths)
                                        for family, cids in sorted(families.items())}})
    return {"schema": "synthesis-matched-result-v1", "purpose": protocol["purpose"],
            "comparison_kind": protocol["comparison_kind"], "protocol_sha256": digest(protocol),
            "runs_sha256": digest(runs), "adjudications_sha256": digest(adjudications) if adjudications is not None else None,
            "scientific_validation": "NOT_ESTABLISHED_BY_THIS_SOFTWARE",
            "matched_budget_status": "VIOLATION" if any(i["status"] == "VIOLATION" for i in issues) else "UNVERIFIED" if issues else "WITHIN_RECORDED_CAPS",
            "budget_issues": issues, "arms": arms, "paired": paired,
            "limitations": ["Receipts are declared evidence, not authenticated billing, identity or independence.",
                            "Caps are audited after execution, not enforced by this evaluator.",
                            "Costs exclude infrastructure and reference adjudication; missing values are not zero.",
                            "Per-arm Wilson intervals are claim-level; paired counts are descriptive with no family-cluster interval.",
                            "No automatic ranking or superiority conclusion."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "mask", "compare"))
    for name in ("manifest", "protocol", "inputs", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    try:
        def read(path):
            return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_pairs,
                              parse_constant=_json_constant)
        manifest, protocol = read(args.manifest), read(args.protocol)
        if args.action == "prepare":
            _need(args.runs is None and args.adjudications is None, "prepare does not consume results or labels")
            result = prepare(manifest, protocol, args.inputs)
        else:
            _need(args.runs is not None, "--runs required")
            runs = read(args.runs)
            if args.action == "mask":
                _need(args.adjudications is None, "mask must not consume labels")
                result = mask(manifest, protocol, runs, args.inputs)
            else:
                result = compare(manifest, protocol, runs, args.inputs,
                                 read(args.adjudications) if args.adjudications else None)
        encoded = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    except (Refused, OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
