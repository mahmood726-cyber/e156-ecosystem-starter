#!/usr/bin/env python3
"""Fail-closed bookkeeping for a pre-frozen, claim-level Synthesis blind evaluation.

Prediction and answer-key files are separate. This program checks declared
provenance and temporal ordering, not the truth of human or source attestations.
It never selects/replaces cases, retrieves papers, or computes scientific truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path


HEX64 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
SPLITS = {"development", "test"}
PREDICTIONS = {"FLAG", "NO_FLAG", "ABSTAIN"}
TRUTH = {"ERROR", "NO_ERROR", "UNKNOWN"}
FORBIDDEN_LABEL_KEYS = {"truth", "answer", "gold_label", "correction_answer",
                        "published_correction", "adjudication", "root_match"}


class EvaluationError(ValueError):
    """A proposed accuracy estimate would lack required protocol evidence."""


def sha256_json(document: dict) -> str:
    data = json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{field} must be a nonempty string")
    return value.strip()


def _timestamp(value: object, field: str) -> datetime:
    raw = _text(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationError(f"{field} must be ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvaluationError(f"{field} requires an explicit timezone")
    return parsed


def _no_labels(row: dict, field: str) -> None:
    hidden = FORBIDDEN_LABEL_KEYS.intersection(row)
    if hidden:
        raise EvaluationError(f"{field} exposes answer fields: {sorted(hidden)}")


def _wilson(successes: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def _proportion(num: int, den: int) -> dict:
    return {"numerator": num, "denominator": den,
            "estimate": round(num / den, 4) if den else None,
            "wilson_95ci": _wilson(num, den)}


def evaluate(manifest: dict, predictions: dict, adjudications: dict | None = None) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != "synthesis-blind-manifest-v1":
        raise EvaluationError("manifest schema mismatch")
    _no_labels(manifest, "manifest")
    _text(manifest.get("cohort_id"), "cohort_id")
    _text(manifest.get("selection_rule"), "selection_rule")
    if isinstance(manifest.get("seed"), bool) or not isinstance(manifest.get("seed"), int):
        raise EvaluationError("manifest must freeze an integer selection seed")
    manifest_time = _timestamp(manifest.get("frozen_at"), "manifest.frozen_at")
    cases = manifest.get("claims")
    if not isinstance(cases, list) or not cases:
        raise EvaluationError("manifest needs prespecified claims")
    by_id: dict[str, dict] = {}
    families: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationError("manifest claim must be an object")
        _no_labels(case, "manifest.claim")
        cid = _text(case.get("claim_id"), "claim_id")
        family = _text(case.get("family_id"), "family_id")
        doi = _text(case.get("doi"), "doi")
        if not DOI.fullmatch(doi):
            raise EvaluationError(f"invalid DOI for {cid}")
        if cid in by_id:
            raise EvaluationError(f"duplicate claim_id {cid}")
        split = case.get("split")
        if split not in SPLITS:
            raise EvaluationError(f"invalid split for {cid}")
        if family in families and families[family] != split:
            raise EvaluationError(f"family {family} leaked across development/test")
        families[family] = split
        if case.get("original_state") == "VERIFIED_ORIGINAL":
            _text(case.get("original_version"), "original_version")
            _text(case.get("retrieval_path"), "retrieval_path")
            _text(case.get("source_locator"), "source_locator")
            if not HEX64.fullmatch(_text(case.get("original_sha256"), "original_sha256")):
                raise EvaluationError(f"invalid original hash for {cid}")
        elif case.get("original_state") == "SOURCE_LIMITED":
            _text(case.get("retrieval_path"), "retrieval_path")
            _text(case.get("stop_point"), "stop_point")
        else:
            raise EvaluationError(f"unknown original source state for {cid}")
        by_id[cid] = case
    test_ids = {cid for cid, case in by_id.items() if case["split"] == "test"}
    if not test_ids:
        raise EvaluationError("no held-out test claims")

    if not isinstance(predictions, dict) or predictions.get("schema") != "synthesis-predictions-v1":
        raise EvaluationError("prediction schema mismatch")
    _no_labels(predictions, "predictions")
    if predictions.get("manifest_sha256") != sha256_json(manifest):
        raise EvaluationError("predictions not bound to exact frozen manifest")
    freeze_time = _timestamp(predictions.get("frozen_at"), "predictions.frozen_at")
    if freeze_time < manifest_time:
        raise EvaluationError("predictions frozen before cohort manifest")
    items = predictions.get("predictions")
    if not isinstance(items, list):
        raise EvaluationError("predictions must be a list")
    by_prediction: dict[str, dict] = {}
    for prediction in items:
        if not isinstance(prediction, dict):
            raise EvaluationError("prediction must be an object")
        _no_labels(prediction, "prediction")
        cid = _text(prediction.get("claim_id"), "prediction.claim_id")
        if cid not in by_id or cid in by_prediction:
            raise EvaluationError(f"unknown/duplicate prediction {cid}")
        status = prediction.get("disposition")
        if status not in PREDICTIONS:
            raise EvaluationError(f"invalid prediction status for {cid}")
        if by_id[cid]["original_state"] == "SOURCE_LIMITED" and status != "ABSTAIN":
            raise EvaluationError(f"source-limited original requires abstention for {cid}")
        t = _timestamp(prediction.get("predicted_at"), "predicted_at")
        if not (manifest_time <= t <= freeze_time):
            raise EvaluationError(f"prediction timestamp outside pre-reveal window for {cid}")
        if status == "FLAG":
            _text(prediction.get("flag_root_id"), "flag_root_id")
            _text(prediction.get("evidence_locator"), "evidence_locator")
        elif status == "ABSTAIN":
            _text(prediction.get("stop_point"), "stop_point")
        seconds = prediction.get("review_seconds")
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds) or seconds < 0):
            raise EvaluationError(f"invalid review_seconds for {cid}")
        by_prediction[cid] = prediction
    missing = sorted(test_ids - by_prediction.keys())
    if missing:
        raise EvaluationError(f"missing prespecified test predictions ({len(missing)}); no silent exclusions")

    result = {
        "schema": "synthesis-blind-eval-result-v1",
        "cohort_id": manifest["cohort_id"],
        "manifest_sha256": sha256_json(manifest),
        "prediction_sha256": sha256_json(predictions),
        "test_claims": len(test_ids),
        "development_claims": len(by_id) - len(test_ids),
        "test_abstentions": sum(by_prediction[cid]["disposition"] == "ABSTAIN" for cid in test_ids),
        "test_source_limited": sum(by_id[cid]["original_state"] == "SOURCE_LIMITED" for cid in test_ids),
        "test_review_hours": round(sum(by_prediction[cid]["review_seconds"] for cid in test_ids) / 3600, 3),
        "status": "PREDICTIONS_FROZEN_AWAITING_BLIND_ADJUDICATION",
        "metrics": None,
        "warning": "Structural checks only; signed files, independent review and real source fidelity are not authenticated by this software.",
    }
    if adjudications is None:
        return result
    if not isinstance(adjudications, dict) or adjudications.get("schema") != "synthesis-adjudications-v1":
        raise EvaluationError("adjudication schema mismatch")
    if adjudications.get("prediction_sha256") != sha256_json(predictions):
        raise EvaluationError("adjudications not bound to exact frozen predictions")
    judgments = adjudications.get("adjudications")
    if not isinstance(judgments, list):
        raise EvaluationError("adjudications must be a list")
    by_judgment: dict[str, dict] = {}
    for judgment in judgments:
        if not isinstance(judgment, dict):
            raise EvaluationError("adjudication must be an object")
        cid = _text(judgment.get("claim_id"), "adjudication.claim_id")
        if cid not in test_ids or cid in by_judgment:
            raise EvaluationError(f"unknown/duplicate test adjudication {cid}")
        if _timestamp(judgment.get("adjudicated_at"), "adjudicated_at") <= freeze_time:
            raise EvaluationError(f"adjudication predates prediction freeze for {cid}")
        if judgment.get("independent_masked") is not True:
            raise EvaluationError(f"independent masked adjudication receipt required for {cid}")
        if judgment.get("truth") not in TRUTH:
            raise EvaluationError(f"unknown truth status for {cid}")
        _text(judgment.get("evidence_reference"), "evidence_reference")
        if by_prediction[cid]["disposition"] == "FLAG" and judgment["truth"] != "UNKNOWN":
            if not isinstance(judgment.get("flag_root_match"), bool):
                raise EvaluationError(f"flag_root_match must be adjudicated for {cid}")
        by_judgment[cid] = judgment
    if set(by_judgment) != test_ids:
        raise EvaluationError("all frozen test claims require an adjudication, including UNKNOWN")
    counts = {"TP": 0, "FP": 0, "FP_NEGATIVE": 0, "FP_WRONG_ROOT": 0,
              "FN": 0, "TN": 0, "ABSTAIN_NEGATIVE": 0,
              "UNKNOWN_TRUTH": 0, "ABSTAIN_ERROR": 0}
    for cid in test_ids:
        truth = by_judgment[cid]["truth"]
        prediction = by_prediction[cid]["disposition"]
        if truth == "UNKNOWN":
            counts["UNKNOWN_TRUTH"] += 1
            continue
        if prediction == "FLAG":
            if truth == "ERROR" and by_judgment[cid]["flag_root_match"]:
                counts["TP"] += 1
            else:
                counts["FP"] += 1
                if truth == "ERROR":
                    counts["FP_WRONG_ROOT"] += 1
                    counts["FN"] += 1  # incorrect root: false alarm AND missed error
                else:
                    counts["FP_NEGATIVE"] += 1
        elif truth == "ERROR":
            counts["FN"] += 1
            if prediction == "ABSTAIN":
                counts["ABSTAIN_ERROR"] += 1
        elif prediction == "NO_FLAG":
            counts["TN"] += 1
        else:
            counts["ABSTAIN_NEGATIVE"] += 1
    tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
    result["status"] = "ADJUDICATED_WITH_UNKNOWN_TRUTH" if counts["UNKNOWN_TRUTH"] else "ADJUDICATED"
    result["metrics"] = {
        **counts,
        "precision_on_adjudicated_flags": _proportion(tp, tp + fp),
        "automatic_error_recall_including_abstentions": _proportion(tp, tp + fn),
        "false_alerts_per_adjudicated_negative_claim": _proportion(
            counts["FP_NEGATIVE"],
            counts["TN"] + counts["ABSTAIN_NEGATIVE"] + counts["FP_NEGATIVE"]),
        "abstention_rate_all_test_claims": _proportion(result["test_abstentions"], len(test_ids)),
        "unknown_truth_fraction": _proportion(counts["UNKNOWN_TRUTH"], len(test_ids)),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
        adjudications = (json.loads(args.adjudications.read_text(encoding="utf-8"))
                         if args.adjudications else None)
        result = evaluate(manifest, predictions, adjudications)
    except (EvaluationError, OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
