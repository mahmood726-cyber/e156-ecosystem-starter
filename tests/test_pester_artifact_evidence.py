"""Fail-closed Windows Pester artifact contract at the real CI workflow head.

These are source-level mutation tests. Hosted Windows Pester execution and the
uploaded NUnit files are separate evidence; neither these fixtures nor a green
uploader certify the full Sentinel/Overmind/E156/Meta-Harness installation.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/test.yml"
ALLOWED_UPLOAD_ACTIONS = {
    "actions/upload-artifact@v4",  # existing CI; mutable until separately reviewed/pinned
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
}
OUTPUT = "pester-results-*.xml"


def require_pester_artifact_contract(source: str) -> None:
    match = re.search(
        r"(?ms)^  pester:\s*\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)",
        source,
    )
    if not match:
        raise ValueError("Pester job missing")
    job = match.group("job")

    # Per-suite NUnit results must be written using names covered by the
    # upload glob, rather than an old aggregate pester-results.xml path.
    if job.count("('pester-results-{0:D2}.xml' -f $i)") != 1:
        raise ValueError("Per-suite XML output naming absent or duplicated")
    # A wildcard upload only requires *one* matching file. Each required
    # Pester suite must prove it wrote a nonempty report before CI can pass.
    required_guards = (
        "$config.TestResult.OutputPath = $xmlPath",
        "if (-not (Test-Path -LiteralPath $xmlPath -PathType Leaf)) {",
        "if ((Get-Item -LiteralPath $xmlPath).Length -le 0) {",
    )
    for guard in required_guards:
        if job.count(guard) != 1:
            raise ValueError(f"Missing or duplicated per-suite XML guard: {guard}")

    steps = list(re.finditer(r"(?m)^      - uses:\s*([^\s#]+)\s*$", job))
    uploads = [step for step in steps if "upload-artifact" in step.group(1)]
    if len(uploads) != 1 or uploads[0].group(1) not in ALLOWED_UPLOAD_ACTIONS:
        raise ValueError("Exactly one approved Pester artifact uploader required")

    start = uploads[0].end()
    next_step = re.search(r"(?m)^      - ", job[start:])
    body = job[start : start + next_step.start()] if next_step else job[start:]
    expectations = (
        ("if", "always()", 8),
        ("name", "pester-results", 10),
        ("path", OUTPUT, 10),
        ("if-no-files-found", "error", 10),
    )
    for key, expected, spaces in expectations:
        found = re.findall(
            rf"(?m)^ {{{spaces}}}{re.escape(key)}:\s*([^\n#]+?)\s*$",
            body,
        )
        if [value.strip() for value in found] != [expected]:
            raise ValueError(f"Pester artifact step must set {key}: {expected}")


def test_real_ci_requires_per_suite_pester_evidence() -> None:
    require_pester_artifact_contract(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("original", "replacement"), [
    ("if-no-files-found: error", "if-no-files-found: warn"),
    ("if-no-files-found: error", "if-no-files-found: ignore"),
    ("if-no-files-found: error", ""),
    ("if: always()", "if: success()"),
    ("path: pester-results-*.xml", "path: pester-results-00.xml"),
    ("path: pester-results-*.xml", "path: unrelated.xml"),
    ("name: pester-results", "name: unrelated"),
    ("actions/upload-artifact@v4", "untrusted/upload-artifact@v4"),
    ("('pester-results-{0:D2}.xml' -f $i)", "'pester-results.xml'"),
])
def test_mutated_evidence_contract_refused(original: str, replacement: str) -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert original in source, "mutation must apply to current workflow"
    with pytest.raises(ValueError):
        require_pester_artifact_contract(source.replace(original, replacement, 1))


def test_duplicate_uploader_refused() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    marker = "      - uses: actions/upload-artifact@v4\n"
    assert source.count(marker) == 1
    with pytest.raises(ValueError):
        require_pester_artifact_contract(source.replace(marker, marker + marker, 1))


@pytest.mark.parametrize("guard", [
    "$config.TestResult.OutputPath = $xmlPath",
    "if (-not (Test-Path -LiteralPath $xmlPath -PathType Leaf)) {",
    "if ((Get-Item -LiteralPath $xmlPath).Length -le 0) {",
])
def test_missing_per_suite_xml_guard_refused(guard: str) -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert source.count(guard) == 1, "mutation must apply to current workflow"
    with pytest.raises(ValueError, match="per-suite XML guard"):
        require_pester_artifact_contract(source.replace(guard, "", 1))
