"""Replay the frozen OA claim checks against the two pinned Git snapshots."""
from collections import Counter
from pathlib import Path
import json
import subprocess
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "synthesis-v13-oa-benchmark.json"
IDENTITY_FIELDS = (
    "source_result_id", "data_version", "intervention", "comparator",
    "denominator_basis", "component",
)


def load_snapshot(revision, stem):
    path = f"scripts/{stem}.py"
    source = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
    module = ModuleType(stem)
    exec(compile(source, f"{revision}:{path}", "exec"), module.__dict__)
    return module


def signatures(module, case, paper, representation):
    # The source review establishes the identity of the specific displayed result.
    # Equal fields here stand for the same published analysis at the two locators.
    # Cross-context controls intentionally share this coarse signature except
    # where the fixture declares a documented estimator difference.
    target = f"{paper['article']} / {case['label']}"
    common = dict.fromkeys(module.ESTIMATOR_FIELDS, target)
    common.update(value_unit=representation, value_representation=representation,
                  value_identity_verified=True)
    left, right = common.copy(), common.copy()
    identity = dict.fromkeys(IDENTITY_FIELDS, target)
    left["result_identity"] = dict(identity, verified=True)
    right["result_identity"] = dict(identity, verified=True)
    for field, (a, b) in case.get("different", {}).items():
        if field in IDENTITY_FIELDS:
            left["result_identity"][field] = a
            right["result_identity"][field] = b
        elif field in module.ESTIMATOR_FIELDS:
            left[field] = a
            right[field] = b
        else:
            raise ValueError(f"Unknown identity field: {field}")
    return left, right


def evaluate(checks, nma, case, paper):
    left, right = case["left"], case["right"]
    notice, article = paper["notices"][0], paper["article"]
    if case["kind"] == "number":
        representation = case.get("representation", "count")
        left_sig, right_sig = signatures(checks, case, paper, representation)
        args = {}
        if isinstance(left, str) and isinstance(right, str):
            args.update(left_published_literal=left, right_published_literal=right,
                        published_precision_verified=True, display_rounding_rule="NEAREST_DECIMAL")
            left, right = float(left), float(right)
        return checks.cross_document(left, right, left_sig, right_sig, ["endpoint"], **args)
    if case["kind"] == "assignment":
        check = getattr(checks, "source_assignment", None)
        if check is None:
            return {"status": "UNAVAILABLE", "reason": "source assignment check absent"}
        left_loc, right_loc = case["locations"]
        return check(case["field"],
                     dict(value=left, locator=left_loc, version=article, verified=True),
                     dict(value=right, locator=right_loc, version=notice, verified=True),
                     same_assignment_verified=True)
    if case["kind"] == "closure":
        # Deliberately submit the same proposed closure even when the notice's
        # scope is wrong. Record separately whether there is an exact replacement.
        replacement = case["replacement"]
        return checks.gate({
            "severity": "S2",
            "version": "CORRECTED_LATEST",
            "source_access": "ACCESSIBLE",
            "source_locator": f"{article} / {left}",
            "current_correction_status": "RESOLVED_IN_PUBLISHED_VERSION",
            "correction_source_verified": True,
            "correction_locator": f"{notice} / {right}",
            "corrected_claim_verified": replacement is not None,
            "corrected_claim_locator": f"{notice} / {replacement}" if replacement else None,
        })
    if case["kind"] == "restriction":
        check = getattr(nma, "restricted_analysis_accounting", None)
        if check is None:
            return {"status": "UNAVAILABLE", "reason": "restricted-analysis check absent"}
        return check({
            "source_version": f"{article} with {notice}",
            "restriction_locator": right,
            "primary_locator": left,
            "restricted_locator": right,
            "same_source_version_verified": True,
            "relationship": "RESTRICTION",
            "same_participant_count_basis_verified": False,
        })
    raise ValueError(f"Unknown check kind: {case['kind']}")


def main():
    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))
    revisions = (benchmark["baseline"], benchmark["candidate_tree"])
    snapshots = [
        (load_snapshot(revision, "synthesis_v13_checks"),
         load_snapshot(revision, "synthesis_v13_nma_preflight"))
        for revision in revisions
    ]
    cases = benchmark["cases"]
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate case IDs")
    counts = Counter()
    print("ID   Expected           Before             After")
    for case in cases:
        paper = benchmark["papers"][case["paper"]]
        before, after = [evaluate(*snapshot, case, paper)["status"] for snapshot in snapshots]
        expected = case["expect"]
        counts[case["group"], "total"] += 1
        counts[case["group"], "before"] += before == expected
        counts[case["group"], "after"] += after == expected
        print(f"{case['id']:4} {expected:18} {before:18} {after}")
    print("\nGroup                Expected status reached (before, after, total)")
    for group in dict.fromkeys(case["group"] for case in cases):
        print(f"{group:20} {counts[group, 'before']:2}  {counts[group, 'after']:2}  {counts[group, 'total']:2}")


if __name__ == "__main__":
    main()
