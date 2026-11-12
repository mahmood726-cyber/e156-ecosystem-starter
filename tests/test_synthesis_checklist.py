"""Engineering controls, not human judgments or scientific validation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import shutil

import pytest

from scripts import synthesis_checklist as checklist

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "examples" / "synthesis-replay-stepwise"
ANCHOR = "fc7e071298fc1fed636ed16dda1252358c026552d0d8209896607d72d23013f9"


@pytest.fixture
def record():
    return checklist.initialize(BUNDLE, ANCHOR, "operator-development")


def test_catalog_preserves_every_published_check():
    catalog = checklist.catalog()
    assert [r["id"] for r in catalog["core"]] == [f"core-{i}" for i in range(1, 7)]
    assert [r["id"] for r in catalog["detailed"]] == [f"detail-{i}" for i in range(1, 28)]
    assert [r["id"] for r in catalog["revision"]] == [f"revision-{i}" for i in range(1, 7)]
    assert "denominator" in catalog["core"][2]["text"].lower()


def test_init_replays_real_source_and_never_assigns_human_pass(record):
    report = checklist.verify(record, BUNDLE)
    assert len(record["claims"]) == 1
    assert record["claims"][0]["id"] == "baseline-exclusion-accounting"
    assert len(record["claims"][0]["checks"]) == 33
    assert all(row["status"] is None for row in record["claims"][0]["checks"])
    assert report["checks_recorded"] == 0
    assert report["checks_total"] == 39
    assert report["scientific_disposition"] == "HOLD"
    assert report["scientific_accuracy_measured"] is False
    assert report["operator_seconds"] is None
    assert record["evaluation_split"] == "development"


@pytest.mark.parametrize("mutation", [
    lambda r: r["claims"].clear(),
    lambda r: r["claims"][0]["checks"].pop(),
    lambda r: r["revision_sweep"].pop(),
    lambda r: r["claims"].append(copy.deepcopy(r["claims"][0])),
    lambda r: r["claims"][0].update(text="different claim"),
    lambda r: r.update(evaluation_split="test"),
    lambda r: r.update(manifest_sha256="0" * 64),
    lambda r: r["checklist_sha256"].update({"SYNTHESIS-HUMAN-CHECKLIST.md": "0" * 64}),
])
def test_missing_changed_or_relabelled_records_refuse(record, mutation):
    mutation(record)
    with pytest.raises(ValueError):
        checklist.verify(record, BUNDLE)


def entered(record, tmp_path, status="Pass"):
    evidence = tmp_path / "working.txt"
    evidence.write_text("Synthetic saved working, no scientific judgment.", encoding="utf-8")
    return checklist.record_check(record, BUNDLE, claim="baseline-exclusion-accounting",
        item="core-4", status=status, reason="Synthetic contract control only",
        reviewer="synthetic-reviewer", seconds=5, evidence=evidence, locator="line 1")


def test_recording_requires_evidence_and_keeps_automation_separate(record, tmp_path):
    updated = entered(record, tmp_path)
    report = checklist.verify(updated, BUNDLE)
    assert report["checks_recorded"] == 1
    assert report["status_counts"]["Pass"] == 1
    assert report["operator_seconds"] == 5
    assert report["workflow_status"] == "INCOMPLETE"
    assert report["scientific_disposition"] == "HOLD"
    assert record["claims"][0]["checks"][3]["status"] is None


@pytest.mark.parametrize("status", ["Pass", "Review needed"])
def test_positive_or_concern_record_needs_saved_evidence(record, status):
    with pytest.raises(ValueError, match="evidence"):
        checklist.record_check(record, BUNDLE, claim="baseline-exclusion-accounting",
            item="core-2", status=status, reason="Synthetic control", reviewer="test",
            seconds=2, evidence=None, locator=None)


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "5", 10**400])
def test_invalid_time_refuses(record, tmp_path, value):
    updated = entered(record, tmp_path)
    updated["claims"][0]["checks"][3]["seconds"] = value
    with pytest.raises(ValueError):
        checklist.verify(updated, BUNDLE)


def test_changed_evidence_refuses(record, tmp_path):
    updated = entered(record, tmp_path)
    (tmp_path / "working.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence"):
        checklist.verify(updated, BUNDLE)


@pytest.mark.parametrize("field,value", [("status", "PASS"), ("reason", ""),
    ("reviewer", ""), ("recorded_at", "yesterday"), ("recorded_at", "2026-11-12T10:00:00")])
def test_invalid_human_record_refuses(record, tmp_path, field, value):
    updated = entered(record, tmp_path)
    updated["claims"][0]["checks"][3][field] = value
    with pytest.raises(ValueError):
        checklist.verify(updated, BUNDLE)


def test_insufficient_evidence_and_na_remain_distinct(record):
    updated = checklist.record_check(record, BUNDLE, claim="baseline-exclusion-accounting",
        item="detail-17", status="N/A", reason="Synthetic non-NMA control",
        reviewer="test", seconds=1, evidence=None, locator=None)
    updated = checklist.record_check(updated, BUNDLE, claim="baseline-exclusion-accounting",
        item="detail-10", status="Insufficient evidence", reason="Protocol unavailable in this control",
        reviewer="test", seconds=2, evidence=None, locator=None)
    report = checklist.verify(updated, BUNDLE)
    assert report["status_counts"]["N/A"] == 1
    assert report["status_counts"]["Insufficient evidence"] == 1
    assert report["scientific_disposition"] == "HOLD"


def test_cli_init_verify_render_and_no_overwrite(tmp_path):
    output = tmp_path / "review.json"
    base = [sys.executable, str(ROOT / "scripts" / "synthesis_checklist.py")]
    init = subprocess.run(base + ["init", "--bundle", str(BUNDLE), "--expected-sha256", ANCHOR,
        "--project", "cli-development", "--out", str(output)], capture_output=True, text=True,
        encoding="utf-8", timeout=30)
    assert init.returncode == 0, init.stderr
    assert json.loads(init.stdout)["scientific_disposition"] == "HOLD"
    before = output.read_bytes()
    again = subprocess.run(base + ["init", "--bundle", str(BUNDLE), "--expected-sha256", ANCHOR,
        "--project", "cli-development", "--out", str(output)], capture_output=True, timeout=30)
    assert again.returncode == 2
    assert output.read_bytes() == before
    rendered = subprocess.run(base + ["render", "--bundle", str(BUNDLE), "--record", str(output)],
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert rendered.returncode == 0, rendered.stderr
    assert "NOT_STARTED" in rendered.stdout
    assert "detail-27" in rendered.stdout
    assert "revision-6" in rendered.stdout
    assert output.read_bytes() == before


def test_complete_record_is_not_scientific_approval(record, tmp_path):
    updated = entered(record, tmp_path)
    point = {key: updated["claims"][0]["checks"][3][key] for key in checklist.POINT_FIELDS}
    for row in updated["claims"][0]["checks"] + updated["revision_sweep"]:
        row.update(copy.deepcopy(point))
    result = checklist.verify(updated, BUNDLE)
    assert result["workflow_status"] == "ALL_CHECKS_RECORDED"
    assert result["scientific_disposition"] == "HOLD"
    assert result["release_eligible"] is False
    assert result["human_identity_and_independence"] == "NOT_ESTABLISHED"


def test_correction_preserves_original_judgment_and_time(record, tmp_path):
    updated = entered(record, tmp_path)
    corrected = checklist.record_check(updated, BUNDLE, claim="baseline-exclusion-accounting",
        item="core-4", status="Insufficient evidence", reason="Synthetic reconsideration",
        reviewer="synthetic-reviewer", seconds=3, evidence=None, locator=None)
    report = checklist.verify(corrected, BUNDLE)
    row = corrected["claims"][0]["checks"][3]
    assert row["history"][0]["status"] == "Pass"
    assert report["operator_seconds"] == 8
    assert report["recorded_corrections"] == 1
    assert report["checks_recorded"] == 1


def test_source_mutation_refuses(record, tmp_path):
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    source = next((bundle / "sources").glob("*.xml"))
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        checklist.verify(record, bundle)


def test_cli_cannot_write_inside_source_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    output = bundle / "review.json"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "synthesis_checklist.py"),
        "init", "--bundle", str(bundle), "--expected-sha256", ANCHOR,
        "--project", "synthetic-control", "--out", str(output)], capture_output=True, timeout=30)
    assert result.returncode == 2
    assert not output.exists()


def test_second_development_bundle_is_covered():
    bundle = ROOT / "examples" / "synthesis-replay-strokewalk"
    # Independent local source fixture; digest from its committed manifest bytes.
    from hashlib import sha256
    record = checklist.initialize(bundle, sha256((bundle / "manifest.json").read_bytes()).hexdigest(), "second-demo")
    report = checklist.verify(record, bundle)
    assert report["checks_total"] == 33 * len(record["claims"]) + 6
    assert report["checks_recorded"] == 0


def test_time_aggregate_overflow_refuses(record, tmp_path):
    updated = entered(record, tmp_path)
    point = {key: updated["claims"][0]["checks"][3][key] for key in checklist.POINT_FIELDS}
    point["seconds"] = 1e308
    for row in updated["claims"][0]["checks"][:2]:
        row.update(copy.deepcopy(point))
    with pytest.raises(ValueError, match="finite"):
        checklist.verify(updated, BUNDLE)


@pytest.mark.parametrize("alias", ["output", "bundle"])
@pytest.mark.parametrize("operation", ["init", "record"])
def test_parent_path_alias_cannot_write_into_bundle(tmp_path, alias, operation):
    bundle = tmp_path / "bundle"
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    shutil.copytree(BUNDLE, bundle)
    supplied_bundle = sibling / ".." / "bundle" if alias == "bundle" else bundle
    output = sibling / ".." / "bundle" / "review.json" if alias == "output" else bundle / "review.json"
    args = [operation, "--bundle", str(supplied_bundle), "--out", str(output)]
    if operation == "init":
        args += ["--expected-sha256", ANCHOR, "--project", "alias-control"]
    else:
        prior = tmp_path / "prior.json"
        prior.write_text(json.dumps(checklist.initialize(bundle, ANCHOR, "alias-control")), encoding="utf-8")
        args += ["--record", str(prior), "--claim", "revision", "--item", "revision-1",
                 "--status", "N/A", "--reason", "synthetic control", "--reviewer", "test", "--seconds", "1"]
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "synthesis_checklist.py"), *args],
                            capture_output=True, timeout=30)
    assert result.returncode == 2
    assert not (bundle / "review.json").exists()
