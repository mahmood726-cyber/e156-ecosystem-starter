"""Fail-closed inventory for the SHA-pinned Python setup action in CI.

This is supply-chain *revision* pinning, not independent attestation of a
release, runner image, Python interpreter or transitive dependency. The tests
inspect production workflow declarations and refuse deliberately planted
unsafe/missing/extra steps. No external fixtures or clinical data are used.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/test.yml"
SETUP_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
SETUP_USE = f"actions/setup-python@{SETUP_SHA}"
REQUIRED = frozenset({"python-tests", "meta-harness-unpack-windows"})

JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", re.M)
ACTION_USE = re.compile(r"^\s+-\s+uses:\s*['\"]?([^\s'\"#]+)", re.M)


def setup_python_problems(workflow: str) -> list[str]:
    """Report missing, substituted, duplicate, unreviewed or unexpected actions."""
    matches = list(JOB_HEADER.finditer(workflow))
    if not matches:
        return ["no CI job inventory"]
    jobs = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(workflow)
        jobs[match.group(1)] = workflow[match.start():end]

    problems = []
    for required in sorted(REQUIRED - jobs.keys()):
        problems.append(f"missing required job: {required}")

    for name, block in jobs.items():
        uses = ACTION_USE.findall(block)
        setup_actions = [
            action for action in uses
            if action.split("@", 1)[0].endswith("/setup-python")
        ]
        if name in REQUIRED:
            if len(setup_actions) != 1:
                problems.append(f"{name}: expected exactly one setup-python step, got {len(setup_actions)}")
        elif setup_actions:
            problems.append(f"{name}: unreviewed setup-python step")
        for action in setup_actions:
            if action != SETUP_USE:
                problems.append(f"{name}: unpinned, substituted or unreviewed setup-python action: {action}")
    return problems


def test_current_workflow_uses_exact_reviewed_setup_python_revision():
    assert setup_python_problems(WORKFLOW.read_text(encoding="utf-8")) == []


def test_clean_copy_is_accepted():
    clean = WORKFLOW.read_text(encoding="utf-8")
    assert setup_python_problems(clean) == []


@pytest.mark.parametrize("replacement", [
    "actions/setup-python@v5",
    "actions/setup-python@v5.6.0",
    "actions/setup-python@main",
    "actions/setup-python@" + "0" * 40,
    "untrusted/setup-python@" + SETUP_SHA,
])
def test_refuses_mutable_or_substituted_action(replacement):
    real = WORKFLOW.read_text(encoding="utf-8")
    assert SETUP_USE in real
    assert setup_python_problems(real.replace(SETUP_USE, replacement, 1))


def test_refuses_missing_action():
    real = WORKFLOW.read_text(encoding="utf-8")
    assert setup_python_problems(real.replace("      - uses: " + SETUP_USE + "\n", "", 1))


def test_refuses_commented_out_action():
    real = WORKFLOW.read_text(encoding="utf-8")
    assert setup_python_problems(real.replace("      - uses: " + SETUP_USE,
                                               "      # - uses: " + SETUP_USE, 1))


def test_refuses_duplicate_action():
    real = WORKFLOW.read_text(encoding="utf-8")
    line = "      - uses: " + SETUP_USE
    assert setup_python_problems(real.replace(line, line + "\n" + line, 1))


def test_refuses_extra_unreviewed_setup_job():
    real = WORKFLOW.read_text(encoding="utf-8")
    planted = real + "\n  new-setup-job:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: " + SETUP_USE + "\n"
    assert setup_python_problems(planted)


def test_refuses_no_or_removed_job_inventory():
    assert setup_python_problems("name: tests\non: push\n") != []
    real = WORKFLOW.read_text(encoding="utf-8")
    assert setup_python_problems(real.replace("  python-tests:", "  renamed-python-tests:", 1))
