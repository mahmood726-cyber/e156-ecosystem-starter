"""Deterministic CVPR arithmetic-check smoke benchmark on INVENTED non-paper cases.

Not a CVPR paper audit, an independent scientific validation, or evidence of
real-world false-positive/recall rates. Source-rights gates are not bypassed:
this script rejects anything other than first-party synthetic fixtures.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import sqrt
from pathlib import Path
from typing import Any

RULES = frozenset({"share_percent", "macro_mean", "relative_gain_percent", "absolute_delta"})
PREDICTIONS = frozenset({"FLAG", "CLEAR", "ABSTAIN"})
LABELS = frozenset({"ERROR", "CLEAN", "NOT_ENOUGH_INFO"})


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("missing or nonnumeric operand")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid numeric operand") from exc
    if not number.is_finite():
        raise ValueError("nonfinite operand")
    return number


def assess(case: dict[str, Any]) -> dict[str, str | None]:
    """Calculate from synthetic operands; withhold when contract is ambiguous."""
    if case.get("fixture_type") != "invented_synthetic" or case.get("source_rights") != "first_party_synthetic":
        raise ValueError("Only invented, first-party synthetic fixtures are accepted")
    if not isinstance(case.get("case_id"), str) or not case["case_id"].startswith("CVPR-W09-"):
        raise ValueError("Case namespace is not reserved for worker 09")
    if case.get("rule") not in RULES:
        raise ValueError("Unknown rule")
    if case.get("source_version") != case.get("comparison_version"):
        return {"prediction": "ABSTAIN", "calculated": None, "reason": "source version mismatch"}
    decimals = case.get("decimals")
    if type(decimals) is not int or not 0 <= decimals <= 5:
        return {"prediction": "ABSTAIN", "calculated": None, "reason": "missing or unsupported precision"}
    x = case.get("operands", {})
    if not isinstance(x, dict):
        return {"prediction": "ABSTAIN", "calculated": None, "reason": "missing operands"}
    try:
        rule = case["rule"]
        if rule == "share_percent":
            num, denom = _number(x.get("numerator")), _number(x.get("denominator"))
            if denom <= 0 or num < 0 or num > denom:
                raise ValueError("unsupported share denominator or numerator")
            calculated = Decimal(100) * num / denom
        elif rule == "macro_mean":
            values = x.get("values")
            if not isinstance(values, list) or not values:
                raise ValueError("missing values")
            calculated = sum((_number(v) for v in values), Decimal(0)) / len(values)
        elif rule == "relative_gain_percent":
            baseline, result = _number(x.get("baseline")), _number(x.get("result"))
            if baseline == 0:
                raise ValueError("zero baseline")
            direction = x.get("metric_direction")
            if direction not in ("higher_better", "lower_better"):
                raise ValueError("unknown metric direction")
            delta = result - baseline if direction == "higher_better" else baseline - result
            calculated = Decimal(100) * delta / abs(baseline)
        else:
            calculated = _number(x.get("result")) - _number(x.get("baseline"))
        reported = _number(case.get("reported"))
        quantizer = Decimal(1).scaleb(-decimals)
        expected = calculated.quantize(quantizer, rounding=ROUND_HALF_UP)
        prediction = "CLEAR" if expected == reported else "FLAG"
        return {"prediction": prediction, "calculated": str(expected), "reason": None}
    except (InvalidOperation, ValueError, ArithmeticError):
        return {"prediction": "ABSTAIN", "calculated": None, "reason": "not enough comparable numeric evidence"}


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> list[float] | None:
    if not trials:
        return None
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    radius = z * sqrt((p * (1-p) + z*z/(4*trials)) / trials) / denom
    return [round(max(0, centre - radius), 4), round(min(1, centre + radius), 4)]


def evaluate(cases: list[dict[str, Any]], split: str = "test") -> dict[str, Any]:
    ids: set[str] = set()
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0,
              "abstained_adjudicated": 0, "abstained_ambiguous": 0,
              "flagged_ambiguous": 0, "cleared_ambiguous": 0}
    evaluations = []
    for case in cases:
        case_id = case.get("case_id")
        if case_id in ids:
            raise ValueError("Duplicate benchmark case ID")
        ids.add(case_id)
        if case.get("split") not in ("dev", "test"):
            raise ValueError("Invalid split")
        if case.get("label") not in LABELS or not case.get("adjudication"):
            raise ValueError("Every case needs an adjudicated label and independently written calculation rationale")
        if case["split"] != split:
            continue
        outcome = assess(case)
        pred, label = outcome["prediction"], case["label"]
        assert pred in PREDICTIONS
        if label == "ERROR":
            counts[{"FLAG": "tp", "CLEAR": "fn", "ABSTAIN": "abstained_adjudicated"}[pred]] += 1
        elif label == "CLEAN":
            counts[{"FLAG": "fp", "CLEAR": "tn", "ABSTAIN": "abstained_adjudicated"}[pred]] += 1
        else:
            counts[{"FLAG": "flagged_ambiguous", "CLEAR": "cleared_ambiguous", "ABSTAIN": "abstained_ambiguous"}[pred]] += 1
        evaluations.append({"case_id": case_id, "rule": case["rule"], "label": label, **outcome})
    tp, fp, fn, tn = (counts[k] for k in ("tp", "fp", "fn", "tn"))
    def ratio(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None
    return {"scope": "synthetic-engineering-only", "split": split, "n_cases": len(evaluations),
            "counts": counts, "precision": ratio(tp, tp + fp),
            "recall_over_evaluable": ratio(tp, tp + fn),
            "specificity_over_evaluable": ratio(tn, tn + fp),
            "recall_wilson_95pct": wilson_interval(tp, tp + fn),
            "specificity_wilson_95pct": wilson_interval(tn, tn + fp),
            "evaluations": evaluations}


def load_fixture(path: Path) -> list[dict[str, Any]]:
    def reject_nonfinite(s: str) -> None:
        raise ValueError(f"Nonfinite JSON number: {s}")
    obj = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_nonfinite)
    if obj.get("fixture_type") != "invented_synthetic" or obj.get("rights") != "first_party_synthetic":
        raise ValueError("Real-publication content is prohibited from this benchmark")
    if obj.get("schema_version") != 1 or not isinstance(obj.get("cases"), list):
        raise ValueError("Unexpected benchmark schema")
    if not all(c.get("fixture_type") == "invented_synthetic" and c.get("source_rights") == "first_party_synthetic" for c in obj["cases"]):
        raise ValueError("Non-synthetic case in benchmark")
    return obj["cases"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path(__file__).resolve().parent.parent / "benchmarks" / "cvpr" / "worker09_synthetic.json")
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    opts = parser.parse_args()
    print(json.dumps(evaluate(load_fixture(opts.fixture), opts.split), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
