#!/usr/bin/env python3
"""Check null inclusion in source-transcribed intervals, without fitting a model."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    args = parser.parse_args()
    data = json.loads(args.inputs.read_text(encoding="utf-8"))
    results = defaultdict(lambda: {"checked": 0, "contains_zero": [], "excludes_zero": []})
    seen = set()
    for row in data["observations"]:
        key = (row["endpoint"], row["treatment"])
        if key in seen:
            raise ValueError(f"Duplicate endpoint/treatment: {key}")
        seen.add(key)
        lower, estimate, upper = (row[k] for k in ("lower", "estimate", "upper"))
        if not all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (lower, estimate, upper)):
            raise ValueError(f"Non-finite or nonnumeric interval: {key}")
        if not lower <= estimate <= upper:
            raise ValueError(f"Unordered interval: {key}")
        outcome = results[row["endpoint"]]
        outcome["checked"] += 1
        label = "contains_zero" if lower <= 0 <= upper else "excludes_zero"
        outcome[label].append(row["treatment"])
    print(json.dumps({"doi": data["doi"], "interval_checks": results,
                      "scope": "Arithmetic witness only; no p-value, model refit or error-count certification."},
                     indent=2))


if __name__ == "__main__":
    main()
