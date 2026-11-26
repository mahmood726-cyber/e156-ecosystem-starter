"""Reproduce candidate SMD discrepancies; standard-library default, optional NumPy.

This is a mathematical research replay, not a validated meta-analysis package.
Simulation results are synthetic. Source author and human adjudication are open.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist

BASE = Path(__file__).resolve().parent


def finite(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def count(value: int, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def overlap_trace(n1: int, n2: int, shared: int) -> float:
    count(n1, "n1", 2)
    count(n2, "n2", 2)
    count(shared, "shared")
    if shared > min(n1, n2):
        raise ValueError("shared exceeds an outcome sample size")
    return shared - shared / n1 - shared / n2 + shared**2 / (n1 * n2)


def k_fixed(nt: tuple[int, int], nc: tuple[int, int], mt: int, mc: int) -> float:
    """Exact pooled-variance coefficient for fixed Normal observation sets."""
    qt = overlap_trace(nt[0], nt[1], mt)
    qc = overlap_trace(nc[0], nc[1], mc)
    return 2 * (qt + qc) / ((nt[0] + nc[0] - 2) * (nt[1] + nc[1] - 2))


def k_printed(nt: tuple[int, int], nc: tuple[int, int]) -> float:
    for n in nt + nc:
        count(n, "sample size", 2)
    return 2 * (nt[0] * nt[1] / (nt[0] + nt[1] - 1)
                + nc[0] * nc[1] / (nc[0] + nc[1] - 1) - 2) / (
                    (nt[0] + nc[0] - 2) * (nt[1] + nc[1] - 2))


def j_approx(df: int) -> float:
    count(df, "df", 2)
    return 1 - 3 / (4 * df - 1)


def j_exact(df: int) -> float:
    count(df, "df", 2)
    return math.exp(math.lgamma(df / 2) - .5 * math.log(df / 2)
                    - math.lgamma((df - 1) / 2))


def eq11(delta1: float, delta2: float, rho: float, nt: int, nc: int,
         squared: bool = False) -> float:
    count(nt, "nt", 2)
    count(nc, "nc", 2)
    delta1, delta2, rho = (finite(x, name) for x, name in
                           [(delta1, "delta1"), (delta2, "delta2"), (rho, "rho")])
    if abs(rho) > 1:
        raise ValueError("rho outside [-1,1]")
    return (1 / nt + 1 / nc) * rho + delta1 * delta2 * (
        rho**2 if squared else rho) / (2 * (nt + nc))


def limiting_size(delta: float, rho: float, alpha: float = .05) -> dict:
    """Equal-effects Wald-test limit for the inspected diagonal implementation."""
    delta, rho, alpha = finite(delta, "delta"), finite(rho, "rho"), finite(alpha, "alpha")
    if not -1 < rho < 1 or not 0 < alpha < 1:
        raise ValueError("require -1 < rho < 1 and 0 < alpha < 1")
    true_v = 4 * (1 - rho) + delta**2 * (1 - rho**2) / 2
    reported_v = 4 * (1 - rho) + delta**2 * (1 - rho**2) / 4
    z = NormalDist().inv_cdf(1 - alpha / 2)
    actual_alpha = math.erfc(z * math.sqrt(reported_v / true_v) / math.sqrt(2))
    return dict(delta=delta, rho=rho, nominal_alpha=alpha,
                true_n_variance=true_v, reported_n_variance=reported_v,
                variance_ratio=reported_v / true_v,
                limiting_rejection_rate=actual_alpha,
                limiting_interval_coverage=1 - actual_alpha)


def example_scale() -> dict:
    path = BASE / "data" / "Geeganage2010.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if len(rows) != 17:
        raise ValueError("Expected the pinned dataset's 17 supplied rows")
    checks = []
    for row in rows:
        for outcome in ("SBP", "DBP"):
            nt, nc, md, st, sc, stored = [finite(row[key + "_" + outcome], key) for key in
                                        ("nt", "nc", "MD", "sdt", "sdc", "SMD")]
            if nt <= 1 or nc <= 1 or st <= 0 or sc <= 0:
                raise ValueError("Invalid sample size or SD in reference data")
            pooled = math.sqrt(((nt - 1) * st**2 + (nc - 1) * sc**2) / (nt + nc - 2))
            stated = md / pooled
            fingerprint = md / math.hypot(st, sc)
            checks.append(dict(row=row["studyID"], outcome=outcome, stored=stored,
                               stated_raw_d=stated, fingerprint=fingerprint,
                               fingerprint_residual=stored - fingerprint))
    return dict(supplied_rows=len(rows), values=len(checks),
                maximum_fingerprint_residual=max(abs(x["fingerprint_residual"]) for x in checks),
                maximum_stated_definition_discrepancy=max(abs(x["stored"] - x["stated_raw_d"]) for x in checks),
                checks=checks)


def verify_integrity() -> int:
    manifest = json.loads((BASE / "SHA256SUMS.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        path = (BASE / name).resolve()
        if not path.is_relative_to(BASE) or not path.is_file():
            raise ValueError(f"Missing or unsafe manifest path: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"SHA-256 mismatch: {name}")
    return len(manifest)


def deterministic_results() -> dict:
    j = j_approx(18)
    return {
        "status": "COMPUTATIONALLY_REPRODUCED_CANDIDATES",
        "novelty": "NOT_ENOUGH_INFO", "author_adjudication": "NOT_ESTABLISHED",
        "eq11": {
            "printed": eq11(2, 2, .5, 50, 50),
            "printed_after_reversal": eq11(2, -2, -.5, 50, 50),
            "squared": eq11(2, 2, .5, 50, 50, True),
            "squared_after_reversal": eq11(2, -2, -.5, 50, 50, True)},
        "J_direction": {"raw_d": 1, "df": 18, "source_d_over_J": 1 / j,
                        "usual_J_times_d": j, "exact_J_times_d": j_exact(18)},
        "k12": {"printed_complete_n10": k_printed((10, 10), (10, 10)),
                "exact_complete_n10": k_fixed((10, 10), (10, 10), 10, 10),
                "exact_no_overlap_n10": k_fixed((10, 10), (10, 10), 0, 0)},
        "example_scale": example_scale(),
        "large_sample": [limiting_size(d, r) for d, r in [(0, .5), (1, .5), (2, .5), (1.5, .8)]]}


def simulate(n: int, delta: float, rho: float, reps: int, seed: int) -> dict:
    """Exact sufficient-statistic simulation; requires optional NumPy."""
    count(n, "n", 3)
    count(reps, "reps", 1000)
    count(seed, "seed")
    theory = limiting_size(delta, rho)
    import numpy as np

    rng = np.random.default_rng(seed)
    df = 2 * n - 2
    j = j_approx(df)
    root = math.sqrt(1 - rho**2)
    a = np.sqrt(rng.chisquare(df, size=reps))
    b, c = rng.normal(size=reps), rng.chisquare(df - 1, size=reps)
    v1, v2 = a * a / df, ((rho * a + root * b)**2 + (1 - rho**2) * c) / df
    z1 = rng.normal(size=reps)
    z2 = rho * z1 + root * rng.normal(size=reps)
    d1 = (delta + math.sqrt(2 / n) * z1) / np.sqrt(v1)
    d2 = (delta + math.sqrt(2 / n) * z2) / np.sqrt(v2)
    contrast = (d1 - d2) / j
    product_term = d1**2 + d2**2 - 2 * rho**2 * d1 * d2
    full_beta = j**2 * df / (df - 2) - 1
    source_beta = (n - 1) / (2 * n - 1) * full_beta
    s = 4 * (1 - rho) / n + source_beta * product_term
    k_changed = 4 * (1 - rho) / n + full_beta * product_term
    critical = NormalDist().inv_cdf(.975)
    p = float(np.mean(np.abs(contrast / np.sqrt(s)) > critical))
    p_changed = float(np.mean(np.abs((d1 - d2) * j / np.sqrt(k_changed)) > critical))
    return dict(n_each=n, delta=delta, rho=rho, repetitions=reps, seed=seed,
                source_rejection_rate=p, mcse=math.sqrt(p * (1 - p) / reps),
                J_and_k_diagnostic_rejection_rate=p_changed,
                empirical_n_variance=float(n * np.var(contrast, ddof=1)),
                mean_n_reported_variance=float(n * s.mean()), **{
                    k: v for k, v in theory.items() if k not in ("delta", "rho")})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "replay-output")
    parser.add_argument("--simulate", action="store_true", help="Replay the frozen additional grid with NumPy")
    args = parser.parse_args()
    integrity = verify_integrity()
    results = deterministic_results()
    if args.simulate:
        plan = json.loads((BASE / "simulation-plan.json").read_text(encoding="utf-8"))
        results["additional_grid"] = [simulate(**case) for case in plan["cases"]]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified_files": integrity, "example_values": results["example_scale"]["values"],
                      "limiting_size_delta2_rho05": results["large_sample"][2]["limiting_rejection_rate"],
                      "simulation_cases": len(results.get("additional_grid", [])),
                      "result": str(args.output / "results.json")}, indent=2))


if __name__ == "__main__":
    main()
