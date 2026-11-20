"""Opt-in paired *pairwise* OR replay, using an explicitly pinned external engine.

This validates reviewer-supplied source-cell bindings, attempts to reproduce the
published point estimate FIRST, and only then reruns changed input counts under
the identical engine. No NMA/IPD/adjusted-effect fitting, independent clinical
adjudication, or conclusion-change inference is performed. No network or email.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

MAX_TRIALS = 40
METHOD = "META_STARTER_KIT_PM_HKSJ_FLOORED_LOG_OR"
CELL_FIELDS = ("tE", "tN", "cE", "cN")
ANALYSIS_FIELDS = ("population", "endpoint", "time_window", "analysis_set",
                   "intervention", "comparator", "effect_measure", "estimand")


def _load_companion(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    if spec is None or spec.loader is None:
        raise RuntimeError("required source gate unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _not_known(value):
    return (not isinstance(value, str) or
            value.strip().casefold() in {"", "unknown", "n/a", "unavailable", "not reported"})


def _status(status, reason, **extra):
    return {"status": status, "reason": reason, "scientific_error_confirmed": False,
            "conclusion_impact": "NOT_ASSESSED", **extra}


def _number_bind(snapshot, binding, value, ledger):
    return ledger._exact_binding(snapshot["quote"], binding, value)


def _verified_snapshot(snapshot, root, viewer):
    return viewer._capture(snapshot, root)


def _check_original_report(packet, root, viewer, ledger):
    report = packet.get("publication")
    if not isinstance(report, dict):
        raise ValueError("publication source and published method required")
    snapshot = _verified_snapshot(report.get("snapshot"), root, viewer)
    if report.get("model") != METHOD or report.get("published_method_source_checked") is not True:
        raise ValueError("published model must be source-attested as the exact supported PM/HKSJ log-OR model")
    if not isinstance(report.get("method_quote"), str) or not report["method_quote"].strip() or \
            report["method_quote"] not in snapshot["quote"]:
        raise ValueError("published method quote not bound to archived report")
    text = report.get("pooled_or_text")
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})", text):
        raise ValueError("published OR must be a positive decimal literal with 1-6 places")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("published OR invalid") from exc
    if value <= 0 or value > Decimal("1000000"):
        raise ValueError("reported OR outside supported comparison range")
    if not _number_bind(snapshot, report.get("pooled_or_binding"), text, ledger):
        raise ValueError("printed published OR not bound to the selected manuscript quote")
    if report.get("trial_set_complete_source_checked") is not True:
        raise ValueError("published model trial-set completeness not source-attested")
    return snapshot, text


def _bind_rows(packet, root, viewer, ledger):
    rows = packet.get("trials")
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_TRIALS:
        raise ValueError("2-40 two-arm trials required")
    analysis = packet.get("analysis")
    if not isinstance(analysis, dict) or any(_not_known(analysis.get(k)) for k in ANALYSIS_FIELDS):
        raise ValueError("complete target analysis identity required")
    if analysis["effect_measure"] != "OR" or analysis["estimand"] != "UNADJUSTED_TWO_ARM_LOG_OR":
        raise ValueError("only unadjusted two-arm OR is supported")
    if packet.get("claim_version_status") != "CURRENT_UNCORRECTED":
        raise ValueError("historical-corrected or current-unverified claims cannot be new error flags")
    trial_keys, family_keys, originals, corrections, refs = set(), set(), [], [], []
    changes = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"trial {index + 1}: row must be an object")
        key, family = row.get("trial_key"), row.get("trial_family_id")
        if _not_known(key) or _not_known(family):
            raise ValueError(f"trial {index + 1}: typed trial/family source identity missing")
        if key in trial_keys or family in family_keys:
            raise ValueError("duplicate trial identity/family: external model assumes independent trials")
        trial_keys.add(key)
        family_keys.add(family)
        if row.get("trial_identity_source_checked") is not True:
            raise ValueError(f"trial {key}: trial/family identity not source-reviewed")
        if row.get("source_tier") not in {"T1", "T2", "T3"}:
            raise ValueError(f"trial {key}: T4/unavailable source not primary verification")
        if row.get("independent_trial_source_verified") is not True:
            raise ValueError(f"trial {key}: independent participant population unverified")
        identity = row.get("analysis")
        if not isinstance(identity, dict) or any(identity.get(k) != analysis[k] for k in ANALYSIS_FIELDS):
            raise ValueError(f"trial {key}: source analysis population, estimand or contrast differs")
        original_source = _verified_snapshot(row.get("published_extraction"), root, viewer)
        primary_source = _verified_snapshot(row.get("primary_trial"), root, viewer)
        if not _number_bind(primary_source, row.get("trial_key_binding"), key, ledger):
            raise ValueError(f"trial {key}: primary trial identifier not bound to exact quote")
        original, corrected = row.get("original"), row.get("corrected")
        binding_a, binding_b = row.get("original_bindings"), row.get("corrected_bindings")
        if not all(isinstance(v, dict) for v in (original, corrected, binding_a, binding_b)):
            raise ValueError(f"trial {key}: both source-bound arm tables required")
        for phase, vals, binds, source in (("original", original, binding_a, original_source),
                                          ("corrected", corrected, binding_b, primary_source)):
            if set(vals) != set(CELL_FIELDS) or set(binds) != set(CELL_FIELDS):
                raise ValueError(f"trial {key}: all four event and denominator fields required in {phase}")
            if any(type(vals[f]) is not int or vals[f] < 0 for f in CELL_FIELDS):
                raise ValueError(f"trial {key}: exact nonnegative integer arm inputs required")
            if vals["tN"] <= 0 or vals["cN"] <= 0 or vals["tE"] > vals["tN"] or vals["cE"] > vals["cN"]:
                raise ValueError(f"trial {key}: impossible arm/event counts in {phase}")
            if len({(binds[f].get("offset"), binds[f].get("text"))
                    for f in CELL_FIELDS if isinstance(binds[f], dict)}) != len(CELL_FIELDS):
                raise ValueError(f"trial {key}: {phase} values must bind distinct physical tokens")
            if any(not _number_bind(source, binds[f], vals[f], ledger) for f in CELL_FIELDS):
                raise ValueError(f"trial {key}: {phase} counts not bound to exact source tokens")
            if min(vals["tE"], vals["tN"] - vals["tE"],
                   vals["cE"], vals["cN"] - vals["cE"]) == 0:
                raise ValueError(f"trial {key}: zero cell requires published-method-specific continuity handling; not supported")
        if original != corrected:
            changes += 1
            if row.get("correction_source_checked") is not True or _not_known(row.get("correction_rationale")):
                raise ValueError(f"trial {key}: corrected values lack source-reviewed rationale")
        originals.append({"name": key, "nct": key if re.fullmatch(r"NCT[0-9]{8}", key) else None, **original})
        corrections.append({"name": key, "nct": key if re.fullmatch(r"NCT[0-9]{8}", key) else None, **corrected})
        refs.append({"trial_key": key, "trial_family_id": family,
                     "original_sha256": original_source["sha256"],
                     "primary_sha256": primary_source["sha256"],
                     "original_locator": original_source["locator"],
                     "primary_locator": primary_source["locator"]})
    return originals, corrections, refs, changes


def _precision_overlap(printed: str, value: float):
    stated = Decimal(printed)
    places = len(printed.split(".")[1])
    halfstep = Decimal(5).scaleb(-places - 1)
    observed = Decimal(str(value))
    return stated - halfstep <= observed <= stated + halfstep


def _engine_at(path: Path, digest: str):
    if not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest):
        raise ValueError("exact external engine SHA-256 is required")
    if not path.is_file() or path.name != "engine.py":
        raise ValueError("explicit trusted meta-starter-kit/metakit/engine.py required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("external engine bytes differ from expected SHA-256")
    spec = importlib.util.spec_from_file_location("_synthesis_pinned_metakit_engine", path)
    if spec is None or spec.loader is None:
        raise ValueError("unable to load pinned engine")
    # Explicit code execution: only use a trusted, already installed checkout.
    engine = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = engine
    spec.loader.exec_module(engine)
    if not callable(getattr(engine, "binary_effect", None)) or not callable(getattr(engine, "pool_effects", None)):
        raise ValueError("pinned engine does not export required methods")
    return engine


def _run_engine(engine, trials):
    effects = []
    for trial in trials:
        e = engine.binary_effect(trial["name"], trial["tE"], trial["tN"],
                                 trial["cE"], trial["cN"], nct=trial["nct"])
        if e is None:
            raise ValueError("engine rejected a complete two-arm study; no silent dropping")
        effects.append(e)
    pool = engine.pool_effects(effects, "OR")
    if pool is None or pool.k != len(trials):
        raise ValueError("engine pooled a different study set")
    values = {k: getattr(pool, k) for k in ("pooled", "ci_low", "ci_high", "tau2", "i2")}
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in values.values()):
        raise ValueError("engine returned nonfinite pooled outputs")
    if not (values["ci_low"] <= values["pooled"] <= values["ci_high"] and
            values["ci_low"] > 0 and values["tau2"] >= 0):
        raise ValueError("engine output violates supported interval/variance bounds")
    return {"k": pool.k, **values}


def check_replay(packet: dict, source_root: Path, *, engine_path=None, engine_sha256=None):
    """No run or correction output before all preflight and engine identity gates."""
    if not isinstance(packet, dict) or packet.get("schema_version") != "0.1":
        return _status("HOLD", "unsupported paired-replay schema")
    try:
        viewer = _load_companion("synthesis_source_trial_view.py", "_paired_viewer")
        ledger = _load_companion("synthesis_trial_source_ledger.py", "_paired_ledger")
        _, printed = _check_original_report(packet, source_root, viewer, ledger)
        original, corrected, refs, changed = _bind_rows(packet, source_root, viewer, ledger)
        safe = {"method": METHOD, "scale": "OR", "source_refs": refs,
                "changed_trials": changed, "k": len(original),
                "model_fit": "NOT_RUN", "published_replay": "NOT_RUN",
                "corrected_replay": "NOT_RUN"}
        if engine_path is None or engine_sha256 is None:
            return _status("READY_FOR_PINNED_ENGINE", "source-cell receipts prepared; no model fitted", **safe)
        engine = _engine_at(Path(engine_path), engine_sha256)
        before = _run_engine(engine, original)
        safe["model_fit"] = "ACTUALLY_EXECUTED"
        safe["published_replay"] = before
        safe["external_engine_sha256"] = engine_sha256
        if not _precision_overlap(printed, before["pooled"]):
            return _status("PUBLISHED_REPLAY_MISMATCH",
                           "original inputs and specified engine do not reproduce printed pooled OR; no corrected model run",
                           **safe)
        if changed == 0:
            return _status("ORIGINAL_REPLAY_MATCHED_NO_INPUT_CHANGE",
                           "printed OR reproduced under declared method but no corrected inputs differ",
                           **safe)
        after = _run_engine(engine, corrected)
        safe["corrected_replay"] = after
        safe["delta_pooled_or"] = after["pooled"] - before["pooled"]
        return _status("PAIRED_MODEL_REPLAYED_FOR_REVIEW",
                       "original printed OR reproduced; corrected source-declared inputs run under identical method; independent scientific adjudication needed",
                       **safe)
    except (ValueError, TypeError, KeyError, OSError, OverflowError, AttributeError, RuntimeError) as exc:
        return _status("HOLD", str(exc))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--engine-file", type=Path, help="trusted local meta-starter-kit/metakit/engine.py")
    ap.add_argument("--engine-sha256", help="expected SHA-256 of the exact engine.py")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        result = check_replay(packet, args.source_root,
                              engine_path=args.engine_file, engine_sha256=args.engine_sha256)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        ap.exit(2, "paired replay failed to load or write: " + str(exc) + "\n")
    print(json.dumps({"status": result["status"],
                      "model_fit": result.get("model_fit", "NOT_RUN"),
                      "scientific_error_confirmed": False}, sort_keys=True))
    return 0 if result["status"] in {"READY_FOR_PINNED_ENGINE", "PAIRED_MODEL_REPLAYED_FOR_REVIEW",
                                     "ORIGINAL_REPLAY_MATCHED_NO_INPUT_CHANGE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
