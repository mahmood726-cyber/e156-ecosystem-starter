"""Fail-closed Windows Pester artifact-evidence gate.

These tests inspect the actual GitHub Actions workflow and plant CI-declaration
failures in memory. They do not claim to execute a live five-component canary.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/test.yml"


def require_pester_result_artifact(source: str) -> None:
    """Refuse a Pester job that can finish without producing uploadable XML."""
    match = re.search(
        r"(?ms)^  pester:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)",
        source,
    )
    if match is None:
        raise ValueError("Pester job is missing")
    job = match.group("body")
    upload_steps = re.findall(
        r"(?m)^      - uses:\s*([^\s#]+)\s*$", job
    )
    upload_steps = [step for step in upload_steps if "upload-artifact" in step]
    if upload_steps != ["actions/upload-artifact@v4"]:
        raise ValueError("Pester must have exactly one official artifact upload step")

    marker = "      - uses: actions/upload-artifact@v4\n"
    if job.count(marker) != 1:
        raise ValueError("Pester artifact upload step is duplicated or missing")
    step = job.split(marker, 1)[1].split("\n      - ", 1)[0]
    required = {
        "if": "always()",
        "name": "pester-results",
        "path": "pester-results.xml",
        "if-no-files-found": "error",
    }
    for key, expected in required.items():
        values = re.findall(r"(?m)^\s+(" + re.escape(key) + r"):\s*([^\n#]+?)\s*$", step)
        if [v.strip() for _, v in values] != [expected]:
            raise ValueError(f"Pester artifact upload requires {key}: {expected}")


def test_real_workflow_requires_pester_evidence_xml() -> None:
    require_pester_result_artifact(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("if-no-files-found: error", "if-no-files-found: warn"),
        ("if-no-files-found: error", "if-no-files-found: ignore"),
        ("if-no-files-found: error", ""),
        ("if: always()", "if: success()"),
        ("path: pester-results.xml", "path: missing.xml"),
        ("name: pester-results", "name: something-else"),
        ("actions/upload-artifact@v4", "other/upload-artifact@v4"),
    ],
)
def test_planted_evidence_gaps_are_refused(before: str, after: str) -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert before in source, "the planted failure must actually modify this workflow"
    with pytest.raises(ValueError):
        require_pester_result_artifact(source.replace(before, after, 1))


def test_duplicate_artifact_upload_step_is_refused() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    marker = "      - uses: actions/upload-artifact@v4\n"
    assert source.count(marker) == 1
    with pytest.raises(ValueError):
        require_pester_result_artifact(source.replace(marker, marker + marker))
