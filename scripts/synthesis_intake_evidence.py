"""Bounded source bindings for normal intake; never scientific adjudication."""
from __future__ import annotations

from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
import re

if __package__:
    from scripts.synthesis_participant_evidence import _count_ref, _reference_key, _label
    from scripts.synthesis_preflight_count_identity import compare_raw_counts, ESTIMATOR_FIELDS, OPTIONAL_METHOD_ABSENCE, RESULT_FIELDS, DENOMINATOR_UNITS, _missing_field
    from scripts.synthesis_preflight_root_dedup import group_preflight_roots
else:
    from synthesis_participant_evidence import _count_ref, _reference_key, _label
    from synthesis_preflight_count_identity import compare_raw_counts, ESTIMATOR_FIELDS, OPTIONAL_METHOD_ABSENCE, RESULT_FIELDS, DENOMINATOR_UNITS, _missing_field
    from synthesis_preflight_root_dedup import group_preflight_roots

MAX_EVIDENCE_CHECKS = 40
MAX_OCCURRENCES = 500
SCALAR_IDENTITY_FIELDS = tuple(k for k in RESULT_FIELDS if k != "count_basis") + ("comparison_id",)
NUMBER = re.compile(r"[+\-\u2212]?(?:(?:0|[1-9][0-9]{0,14}|[1-9][0-9]{0,2}(?:,[0-9]{3}){1,4})(?:\.[0-9]{1,12})?|\.[0-9]{1,12})(?:[eE][+\-]?[0-9]{1,3})?\Z")


def evidence_quotes(checks):
    """Collect only requested excerpts; bounded even for non-JSON callers."""
    quotes, visited = set(), 0
    def visit(value, depth=0):
        nonlocal visited
        visited += 1
        if depth > 12 or visited > 20000:
            raise ValueError("Evidence references exceed the traversal limit")
        if isinstance(value, dict):
            quote = value.get("quote")
            if isinstance(quote, str) and 1 <= len(quote) <= 500 and quote.strip():
                quotes.add(" ".join(quote.split()))
            for child in value.values(): visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value: visit(child, depth + 1)
    for _, check in checks: visit(check)
    return sorted(quotes)


def bind_quote(evidence, ref):
    if (not isinstance(ref, dict) or not {"quote"} <= set(ref) <= {"quote", "locator"}
            or not isinstance(ref["quote"], str) or not 1 <= len(ref["quote"]) <= 500 or not ref["quote"].strip()):
        raise ValueError("A source reference needs a quote and optional exact locator")
    quote = " ".join(ref["quote"].split())
    matches = evidence.get("quote_bindings", {}).get(quote, [])
    if "locator" in ref:
        if not isinstance(ref["locator"], str) or not 1 <= len(ref["locator"]) <= 200:
            raise ValueError("Invalid exact source locator")
        matches = [m for m in matches if m["locator"] == ref["locator"]]
    if len(matches) != 1 or matches[0].get("count_safe") is not True:
        raise ValueError("Source quote is missing, ambiguous, merged or uses unsupported markup")
    offset = matches[0].get("quote_offset")
    if type(offset) is not int or offset < 0:
        raise ValueError("Source quote lacks a verified text offset")
    return {"quote": quote, "locator": matches[0]["locator"], "quote_offset": offset,
            "quote_prefix": matches[0].get("quote_prefix", ""), "quote_suffix": matches[0].get("quote_suffix", "")}


def bind_scalar(evidence, ref):
    """Preserve signs/inequalities/precision without weakening count parsing."""
    if (not isinstance(ref, dict) or not {"quote", "number_text", "role", "unit", "scale"} <= set(ref)
            or not set(ref) <= {"quote", "number_text", "role", "unit", "scale", "locator", "inequality", "unit_context"}):
        raise ValueError("Scalar reference needs quote, number_text, role, unit and scale")
    role = ref["role"]
    if role not in {"estimate", "lower", "upper", "percentage", "value", "count"}:
        raise ValueError("Unknown scalar role")
    unit, scale = (_label(ref, k) for k in ("unit", "scale"))
    unit_context = bind_quote(evidence, ref.get("unit_context", {k: ref[k] for k in ("quote", "locator") if k in ref}))
    if unit == "percent":
        unit_present = re.search(r"%|\bpercent(?:age)?\b|\bper\s+cent\b", unit_context["quote"], re.I)
    else:
        unit_present = re.search(r"(?<!\w)" + re.escape(unit) + r"(?!\w)", unit_context["quote"], re.I)
    if not unit_present:
        raise ValueError("Declared unit is not present in the bound unit context")
    if role == "count":
        cell = _count_ref(evidence, {"quote": ref["quote"], "count_text": ref["number_text"],
                                  **({"locator": ref["locator"]} if "locator" in ref else {})})
        if ref.get("inequality") is not None:
            raise ValueError("Counts must be exact integers, without inequalities")
        return {**cell, "lexeme": ref["number_text"], "value": str(cell["participants"]),
                "role": role, "unit": unit, "unit_context": unit_context, "scale": scale, "inequality": None}
    binding = bind_quote(evidence, {k: ref[k] for k in ("quote", "locator") if k in ref})
    token = ref["number_text"]
    if not isinstance(token, str) or not NUMBER.fullmatch(token):
        raise ValueError("number_text must be a bounded exact numeric lexeme")
    quote = binding["quote"]
    matches = list(re.finditer(r"(?<![\w.,+\-\u2212\u2013\u2014\u00b1])" + re.escape(token)
                              + r"(?![\w+\-\u2212\u2013\u2014\u00b1]|[.,][0-9])", quote))
    if len(matches) != 1:
        raise ValueError("Numeric lexeme is absent, ambiguous or a partial signed/range token")
    match = matches[0]
    preceding = binding["quote_prefix"] + quote[:match.start()]
    following = quote[match.end():] + binding["quote_suffix"]
    if (re.search(r"[\w.,+\-\u2212\u2013\u2014\u00b1]$", preceding)
            or re.match(r"[\w+\-\u2212\u2013\u2014\u00b1]|[.,][0-9]", following)
            or re.search(r"[+\-\u2212\u00b1]\s+$", preceding)):
        raise ValueError("Numeric excerpt cuts a larger or signed source token")
    op = re.search(r"([<>]=?|[\u2264\u2265])\s*$", preceding)
    inequality = op.group(1) if op else None
    if ref.get("inequality") != inequality:
        raise ValueError("Printed inequality must be preserved explicitly")
    # The source suffix still governs units when the selected excerpt is clipped.
    follows_points = re.match(r"\s*(?:percent(?:age)?|per\s+cent)\s+points?\b", following, re.I)
    follows_percent = re.match(r"\s*(?:%|percent(?:age)?\b|per\s+cent\b)", following, re.I)
    if follows_points and unit.casefold() not in {"percentage point", "percentage points", "percent point", "percent points"}:
        raise ValueError("A percentage-point token requires the matching unit")
    if follows_percent and not follows_points and unit != "percent":
        raise ValueError("A percent token requires the percent unit")
    value = Decimal(token.replace(",", "").replace("\u2212", "-"))
    if not value.is_finite() or abs(value.adjusted()) > 100:
        raise ValueError("Numeric magnitude requires specialist review")
    return {**binding, "lexeme": token, "value": str(value), "role": role, "unit": unit, "unit_context": unit_context, "scale": scale,
            "inequality": inequality, "text": token,
            "source_token_start": binding["quote_offset"] + match.start(),
            "source_token_end": binding["quote_offset"] + match.end()}


def _count_record(evidence, record):
    if not isinstance(record, dict) or record.get("scope_verified") is not True:
        raise ValueError("Each count requires verified scope and a source-bound definition")
    cell = _count_ref(evidence, record.get("count"))
    definition = bind_quote(evidence, record.get("definition"))
    identity = record.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("Each count requires its own result identity")
    source = evidence["source"]
    for key, value in (("publication_id", source["doi"]), ("source_version", source["version"]),
                       ("source_sha256", source["snapshot_sha256"]), ("locator", cell["locator"]),
                       ("value", cell["participants"])):
        if key in identity and identity[key] != value:
            raise ValueError("Declared count identity contradicts captured source: " + key)
    return {**identity, "publication_id": source["doi"], "source_version": source["version"],
            "source_sha256": source["snapshot_sha256"], "locator": cell["locator"],
            "value": cell["participants"], "binding": cell, "definition": definition}


def _counts(evidence, spec):
    left, right = (_count_record(evidence, spec.get(k)) for k in ("left", "right"))
    if _reference_key(left["binding"]) == _reference_key(right["binding"]):
        raise ValueError("Two count occurrences must use distinct physical tokens")
    check = compare_raw_counts(left, right)
    status = {"CONSISTENT": "NO_FLAG", "REVIEW": "REVIEW_CANDIDATE"}.get(check["status"], "HOLD")
    return {"status": status, "reason": check["reason"], "identity": check, "left": left, "right": right}


def _subset(evidence, spec):
    if spec.get("relationship") != "STRICT_SUBSET":
        raise ValueError("Rematched, different-risk-set and unknown populations cannot use strict subtraction")
    primary, restricted = (_count_record(evidence, spec.get(k)) for k in ("primary", "restricted"))
    same_fields = ("data_version", "count_basis", "analysis_cell_id") + tuple(k for k in ESTIMATOR_FIELDS if k != "population")
    for record in (primary, restricted):
        if compare_raw_counts(record, record)["status"] != "CONSISTENT":
            raise ValueError("Restricted-count identity is incomplete or invalid")
    if any(primary[k] != restricted[k] for k in same_fields):
        raise ValueError("Restriction changes the outcome, arm, timepoint or counting basis")
    if _reference_key(primary["binding"]) == _reference_key(restricted["binding"]):
        raise ValueError("Parent and restricted counts require distinct tokens")
    result = {"primary": primary, "restricted": restricted, "identity_status": "MATCHED_RESTRICTION",
              "bound_status": "REVIEW_CANDIDATE" if restricted["value"] > primary["value"] else "NO_FLAG"}
    exclusions = spec.get("exclusions")
    if exclusions is None:
        return {**result, "status": result["bound_status"] if result["bound_status"] == "REVIEW_CANDIDATE" else "HOLD",
                "reason": "Restricted bound only; exact exclusion accounting is unverified"}
    if (not isinstance(exclusions, list) or len(exclusions) > MAX_OCCURRENCES
            or spec.get("exclusions_disjoint_verified") is not True or spec.get("exclusions_exhaustive_verified") is not True):
        raise ValueError("Strict subtraction requires explicitly disjoint, exhaustive exclusions")
    records = [_count_record(evidence, record) for record in exclusions]
    used = {_reference_key(v["binding"]) for v in (primary, restricted)}
    for record in records:
        if (compare_raw_counts(record, record)["status"] != "CONSISTENT"
                or any(record[k] != primary[k] for k in same_fields)):
            raise ValueError("Exclusion identity is incomplete or uses a different counting basis")
        key = _reference_key(record["binding"])
        if key in used: raise ValueError("Reused exclusion/parent/restricted physical token")
        used.add(key)
    expected = primary["value"] - sum(r["value"] for r in records)
    if expected < 0: raise ValueError("Exclusions exceed the parent count")
    difference = restricted["value"] - expected
    return {**result, "status": "REVIEW_CANDIDATE" if difference else "NO_FLAG", "exclusions": records,
            "expected_restricted": expected, "difference": difference,
            "formula": "parent - sum(disjoint exhaustive exclusions); reported - expected",
            "reason": "Source-bound restriction accounting checked; source tally remains unverified"}


def _rounding_result(value, reported, quantum, policy):
    """A tie with an unspecified convention cannot establish a discrepancy."""
    if policy not in {"UNSPECIFIED", "HALF_UP", "HALF_EVEN"}:
        raise ValueError("Unknown rounding policy")
    modes = {"HALF_UP": ROUND_HALF_UP, "HALF_EVEN": ROUND_HALF_EVEN}
    chosen = modes if policy == "UNSPECIFIED" else {policy: modes[policy]}
    with localcontext(Context(prec=64)):
        options = {name: str(value.quantize(quantum, rounding=mode)) for name, mode in chosen.items()}
    values = {Decimal(v) for v in options.values()}
    status = "NO_FLAG" if values == {reported} else "HOLD" if reported in values else "REVIEW_CANDIDATE"
    return {"status": status, "rounding": policy, "rounding_options": options,
            "rounded_value": next(iter(options.values())) if len(values) == 1 else None}


def _scalar_record(evidence, record):
    if not isinstance(record, dict) or record.get("scope_verified") is not True:
        raise ValueError("Each scalar requires verified scope and a source-bound definition")
    binding = bind_scalar(evidence, record.get("value"))
    if binding["role"] == "count" or binding["inequality"] is not None:
        raise ValueError("Repeated scalars must be exact, uncensored non-count tokens")
    definition = bind_quote(evidence, record.get("definition"))
    identity = record.get("identity")
    optional = {"source_sha256", "locator", "analysis_denominator_n", "analysis_denominator_unit"}
    if not isinstance(identity, dict) or not set(identity) <= set(SCALAR_IDENTITY_FIELDS) | optional:
        raise ValueError("Unsupported scalar identity fields")
    identity = dict(identity)
    source = evidence["source"]
    for key, value in (("publication_id", source["doi"]), ("source_version", source["version"]),
                       ("source_sha256", source["snapshot_sha256"]), ("locator", binding["locator"])):
        if key in identity and identity[key] != value:
            raise ValueError("Declared scalar identity contradicts captured source: " + key)
        identity[key] = value
    for key in SCALAR_IDENTITY_FIELDS:
        # comparison_id is a core contrast/reference/coding identity, never N/A.
        if _missing_field(identity.get(key), "source_result_id" if key == "comparison_id" else key):
            raise ValueError("Missing or unverified scalar identity: " + key)
    return {"binding": binding, "definition": definition, "identity": identity}


def _scalars(evidence, spec):
    left, right = (_scalar_record(evidence, spec.get(key)) for key in ("left", "right"))
    a, b = left["binding"], right["binding"]
    if _reference_key(a) == _reference_key(b):
        raise ValueError("Repeated values require distinct physical tokens")
    if any(a[key] != b[key] for key in ("role", "unit", "scale")):
        raise ValueError("Scalar roles, units and scales must match; no conversion is inferred")
    fields = list(SCALAR_IDENTITY_FIELDS)
    for r in (left, right):
        ident = r["identity"]
        if ("analysis_denominator_n" in ident) != ("analysis_denominator_unit" in ident):
            raise ValueError("Scalar denominator size and unit must be supplied together")
    for field in ("analysis_denominator_n", "analysis_denominator_unit"):
        if field in left["identity"] or field in right["identity"]:
            if not all(field in r["identity"] for r in (left, right)):
                raise ValueError("A supplied scalar denominator must be defined on both sides")
            fields.append(field)
    for r in (left, right):
        ident = r["identity"]
        if "analysis_denominator_n" in ident and (type(ident["analysis_denominator_n"]) is not int or ident["analysis_denominator_n"] <= 0):
            raise ValueError("Scalar denominator size must be a positive exact integer")
        if "analysis_denominator_unit" in ident and ("analysis_denominator_n" not in ident or ident["analysis_denominator_unit"] not in DENOMINATOR_UNITS):
            raise ValueError("Scalar denominator unit needs its size and a known unit")
    mismatches = [key for key in fields if left["identity"][key] != right["identity"][key]]
    comparability = {"status": "NOT_COMPARABLE" if mismatches else "MATCHED", "mismatched_fields": mismatches,
                     "scope_authenticated": False}
    result = {"left": left, "right": right, "comparability": comparability,
              "reason": "Repeated printed scalars at compatible precision; scientific identity is reviewer supplied"}
    if mismatches:
        return {**result, "status": "HOLD"}
    values = [Decimal(v["value"]) for v in (a, b)]
    fine, coarse = sorted(values, key=lambda v: v.as_tuple().exponent)
    quantum = Decimal(1).scaleb(coarse.as_tuple().exponent)
    return {**result, **_rounding_result(fine, coarse, quantum, spec.get("rounding", "UNSPECIFIED"))}


def _bounded(evidence, spec):
    if spec.get("scope_verified") is not True:
        raise ValueError("Scale applicability must be reviewed against its source")
    scope = bind_quote(evidence, spec.get("scope_context"))
    refs = {key: bind_scalar(evidence, spec.get(key)) for key in ("value", "minimum", "maximum")}
    if any(v["role"] != "value" or v["inequality"] is not None for v in refs.values()):
        raise ValueError("Scale limits and value require exact uncensored value tokens")
    if len({(v["unit"], v["scale"]) for v in refs.values()}) != 1:
        raise ValueError("Scale limits and value must use the same unit and scale")
    if len({_reference_key(v) for v in refs.values()}) != 3:
        raise ValueError("Scale checking requires three distinct source tokens")
    value, minimum, maximum = (Decimal(refs[key]["value"]) for key in ("value", "minimum", "maximum"))
    if minimum >= maximum:
        raise ValueError("Scale minimum must be strictly less than maximum")
    return {"status": "NO_FLAG" if minimum <= value <= maximum else "REVIEW_CANDIDATE",
            "reason": "Inclusive source-defined scale limits only; applicability remains reviewer attested",
            "values": refs, "scope_context": scope, "scope_authenticated": False}


def _percent(evidence, spec):
    numerator, denominator = (_count_record(evidence, spec.get(k)) for k in ("numerator", "denominator"))
    identity = compare_raw_counts(numerator, denominator)
    if identity["status"] not in {"CONSISTENT", "REVIEW"}:
        return {"status": "HOLD", "reason": identity["reason"], "identity": identity}
    for record in (numerator, denominator):
        normalized = lambda key: re.sub(r"[\s_-]+", "_", record[key].casefold())
        if (normalized("effect_measure") != "raw_count" or normalized("estimand") != "observed_count"
                or any(normalized(key) not in OPTIONAL_METHOD_ABSENCE for key in ("model", "adjustment", "censoring"))
                or normalized("missingness") not in OPTIONAL_METHOD_ABSENCE | {"observed", "complete_case", "available_case", "no_imputation"}
                or record.get("analysis_denominator_unit", record["count_basis"]) != record["count_basis"]):
            raise ValueError("COUNT_PERCENT requires raw observed counts, absent model/adjustment/censoring and an observed same-unit denominator")
    if _reference_key(numerator["binding"]) == _reference_key(denominator["binding"]):
        raise ValueError("Numerator and denominator need distinct source tokens")
    percent = bind_scalar(evidence, spec.get("percentage"))
    if (percent["role"] != "percentage" or percent["unit"] != "percent" or percent["scale"] != "raw"
            or percent["inequality"] is not None):
        raise ValueError("Percentage checking requires an exact raw percentage")
    n, den = numerator["value"], denominator["value"]
    if denominator["count_basis"] != numerator["count_basis"] or not 0 <= n <= den or den == 0:
        raise ValueError("Invalid same-unit numerator/denominator accounting")
    reported = Decimal(percent["value"])
    quantum = Decimal(1).scaleb(reported.as_tuple().exponent)
    with localcontext(Context(prec=64, rounding=ROUND_HALF_UP)):
        computed = Decimal(100) * n / den
    rounding = _rounding_result(computed, reported, quantum, spec.get("rounding", "UNSPECIFIED"))
    return {**rounding,
            "reason": "Raw percentage checked at the captured printed precision",
            "numerator": numerator, "denominator": denominator, "percentage": percent,
            "computed_percent": str(computed), "rounded_percent": rounding["rounded_value"],
            "formula": "100 * source numerator / source denominator",
            "identity": {"status": "MATCHED", "scope_authenticated": False}}


def _interval(evidence, spec):
    if spec.get("scope_verified") is not True or spec.get("method") not in {"reported_two_sided", "conventional_two_sided"}:
        raise ValueError("Two-sided interval scope/method must be established")
    method = bind_quote(evidence, spec.get("method_context"))
    effect = _label(spec, "effect_measure")
    values = {k: bind_scalar(evidence, spec.get(k)) for k in ("estimate", "lower", "upper")}
    if any(v["role"] != k or v["inequality"] is not None for k, v in values.items()):
        raise ValueError("Interval roles must match exact, uncensored numeric tokens")
    if len({(v["unit"], v["scale"]) for v in values.values()}) != 1:
        raise ValueError("Interval units or scales differ; no conversion is inferred")
    if len({_reference_key(v) for v in values.values()}) != 3:
        raise ValueError("Interval roles require three distinct source tokens")
    point, lower, upper = (Decimal(values[k]["value"]) for k in ("estimate", "lower", "upper"))
    return {"status": "NO_FLAG" if lower <= point <= upper else "REVIEW_CANDIDATE",
            "reason": "Printed interval ordering and containment only; no CI/P-value equivalence inferred",
            "values": values, "method_context": method, "effect_measure": effect,
            "method": spec["method"], "interval_method_validated": False}


def _sweep(evidence, spec, claim_id):
    expected = bind_scalar(evidence, spec.get("expected"))
    refs, deps = spec.get("occurrences"), spec.get("dependencies")
    if (not isinstance(refs, list) or not 1 <= len(refs) <= MAX_OCCURRENCES
            or not isinstance(deps, list) or len(deps) > MAX_OCCURRENCES):
        raise ValueError("Map occurrences and explicitly list dependencies, even when empty")
    occurrences, keys, ids, roots = [], set(), set(), []
    for item in refs:
        if not isinstance(item, dict): raise ValueError("Malformed revision occurrence")
        output_id, root = (_label(item, k) for k in ("id", "root_id"))
        if output_id in ids: raise ValueError("Repeated revision output ID")
        ids.add(output_id)
        value = bind_scalar(evidence, item.get("ref"))
        key = _reference_key(value)
        if key in keys: raise ValueError("Revision occurrences reuse the same physical token")
        keys.add(key)
        if any(value[k] != expected[k] for k in ("unit", "scale", "role", "inequality")):
            raise ValueError("Revision values use different roles, units, scales or inequalities")
        same = Decimal(value["value"]) == Decimal(expected["value"])
        occurrences.append({"id": output_id, "root_id": root, "binding": value, "status": "MATCH" if same else "STALE"})
        roots.append({"publication_id": evidence["source"]["doi"], "source_version": evidence["source"]["version"],
                      "root_scope_id": claim_id, "root_cause_id": root, "affected_output_id": output_id,
                      "source_support": "NOT_ENOUGH_INFO", "maturity": "SCREENED", "disposition": "HOLD",
                      "human_adjudicated": False, "author_confirmed": False})
    edges, dependencies = {}, []
    for dep in deps:
        if not isinstance(dep, dict): raise ValueError("Malformed revision dependency")
        dep_id, locator = (_label(dep, k) for k in ("id", "locator"))
        if dep_id in ids or dep_id in edges: raise ValueError("Repeated revision dependency/output ID")
        parents = dep.get("depends_on", [])
        if not isinstance(parents, list) or len(parents) > MAX_OCCURRENCES or any(not isinstance(p, str) for p in parents):
            raise ValueError("Invalid dependency edges")
        edges[dep_id] = set(parents)
        state = dep.get("status")
        if state not in {"MAPPED", "JUSTIFIED_DIFFERENCE", "UNINSPECTED"}:
            raise ValueError("Unknown dependency state")
        entry = {"id": dep_id, "locator": locator, "status": state, "depends_on": sorted(set(parents))}
        if state == "MAPPED":
            if dep.get("occurrence_id") not in ids: raise ValueError("Mapped dependency lacks an occurrence")
            occurrence = next(o for o in occurrences if o["id"] == dep["occurrence_id"])
            if locator != occurrence["binding"]["locator"]:
                raise ValueError("Mapped dependency locator does not match its captured occurrence")
            entry["occurrence_id"] = dep["occurrence_id"]
        if state == "JUSTIFIED_DIFFERENCE":
            if dep.get("reviewed") is not True: raise ValueError("A justified difference requires source review")
            entry.update(reason=_label(dep, "reason"), evidence=bind_quote(evidence, dep.get("evidence")))
        dependencies.append(entry)
    if any(p not in ids and p not in edges for parents in edges.values() for p in parents):
        raise ValueError("Unresolved revision dependency edge")
    pending = {k: v - ids for k, v in edges.items()}
    while pending:
        ready = {k for k, v in pending.items() if not v}
        if not ready: raise ValueError("Revision dependency cycle")
        pending = {k: v - ready for k, v in pending.items() if k not in ready}
    stale = any(o["status"] == "STALE" for o in occurrences)
    unchecked = any(d["status"] == "UNINSPECTED" for d in dependencies)
    grouping = group_preflight_roots(roots)
    if grouping["status"] != "GROUPED": raise ValueError("Revision root identities are invalid")
    return {"status": "REVIEW_CANDIDATE" if stale else "HOLD" if unchecked else "NO_FLAG",
            "reason": "Mapped revision comparisons; dependencies outside the map are not certified",
            "coverage": "REVIEWER_SELECTED_ONLY", "expected": expected, "occurrences": occurrences,
            "dependencies": dependencies, "root_groups": grouping}


def evidence_finding(claim_id, spec, evidence):
    result = {"claim_id": claim_id, "status": "HOLD", "source_authenticated": False,
              "count_validity": "NOT_INDEPENDENTLY_VERIFIED"}
    try:
        if not isinstance(spec, dict): raise ValueError("Evidence check must be an object")
        result.update(check_id=_label(spec, "id"), kind=spec.get("kind"))
        if not evidence or evidence.get("status") != "CAPTURED":
            raise ValueError("A captured OA PMC snapshot is required")
        if spec.get("snapshot_sha256") != evidence["source"]["snapshot_sha256"]:
            raise ValueError("Evidence check must bind the exact captured snapshot")
        result["source"] = evidence["source"]
        kind = spec.get("kind")
        if kind == "MATCHED_COUNTS": result.update(_counts(evidence, spec))
        elif kind == "STRICT_SUBSET": result.update(_subset(evidence, spec))
        elif kind == "COUNT_PERCENT": result.update(_percent(evidence, spec))
        elif kind == "MATCHED_SCALARS": result.update(_scalars(evidence, spec))
        elif kind == "BOUNDED_VALUE": result.update(_bounded(evidence, spec))
        elif kind == "INTERVAL": result.update(_interval(evidence, spec))
        elif kind == "REVISION_SWEEP": result.update(_sweep(evidence, spec, claim_id))
        else: raise ValueError("Unknown source evidence kind")
    except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError) as exc:
        result.update(status="HOLD", reason=str(exc))
    return result
