"""Refuse mutable GitHub Actions checkout references in the real CI workflow.

Installer SHA checks and Sentinel pinning are insufficient if an attacker can
change the checkout action fetched by GitHub Actions. This is an isolated
CI-integrity contract, not a five-component live ecosystem canary.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "test.yml"
# Official actions/checkout refs/tags/v4 resolved to this full commit on
# 26 October 2026. Review updates against the upstream commit before changing.
REVIEWED_CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
CHECKOUT = "actions/checkout@" + REVIEWED_CHECKOUT_SHA

_JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
_USES = re.compile(r"^\s*- uses:\s*(\S+)\s*(?:#.*)?$")


def checkout_pin_problems(workflow: str) -> list[str]:
    """Check each declared CI job has exactly one SHA-pinned checkout step."""
    jobs: dict[str, list[str]] = {}
    in_jobs = False
    active: str | None = None
    for raw in workflow.splitlines():
        if raw.strip() == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if raw and not raw.startswith((" ", "#")):
            break
        match = _JOB.fullmatch(raw)
        if match:
            active = match.group(1)
            jobs[active] = []
            continue
        step = _USES.fullmatch(raw)
        if step and active is not None:
            jobs[active].append(step.group(1))
    problems = []
    if not jobs:
        return ["workflow has no CI jobs (cannot prove checkout pinning)"]
    for name, actions in jobs.items():
        checkouts = [action for action in actions if action.startswith("actions/checkout@")]
        if len(checkouts) != 1:
            problems.append(f"{name}: expected exactly one checkout step, found {len(checkouts)}")
        elif checkouts[0] != CHECKOUT:
            problems.append(f"{name}: checkout does not match reviewed full SHA")
    return problems


def test_live_workflow_has_exact_checkout_sha_in_every_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert checkout_pin_problems(text) == []
    assert len(re.findall(r"(?m)^  [A-Za-z0-9_-]+:\s*$", text.split("jobs:", 1)[1])) == 9


@pytest.mark.parametrize("bad", [
    "actions/checkout@v4",            # mutable major-version tag
    "actions/checkout@v4.2.2",        # mutable release tag
    "actions/checkout@" + "0" * 40, # wrong exact commit
    "attacker/checkout@" + REVIEWED_CHECKOUT_SHA,  # replacement action
    "actions/cache@" + REVIEWED_CHECKOUT_SHA,      # missing checkout entirely
])
def test_planted_checkout_reference_changes_are_refused(bad):
    original = WORKFLOW.read_text(encoding="utf-8")
    altered = original.replace(CHECKOUT, bad, 1)
    assert altered != original
    assert checkout_pin_problems(altered), f"unchecked altered action: {bad}"


def test_planted_duplicate_checkout_is_refused():
    original = WORKFLOW.read_text(encoding="utf-8")
    altered = original.replace("- uses: " + CHECKOUT, "- uses: " + CHECKOUT + "\n      - uses: " + CHECKOUT, 1)
    assert altered != original
    assert checkout_pin_problems(altered)


def test_planted_no_jobs_is_refused():
    assert checkout_pin_problems("name: workflow without jobs\n") != []
