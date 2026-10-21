"""Tests for scripts/protect-test-config.py (opt-in hook, P1 of 2026-10-20).

House rule: BOTH directions. A guard that blocks everything also "passes" a
must-block test, and a guard that blocks nothing passes a must-allow test; only
the pair says anything.

The case this suite exists for: an agent that cannot make a test pass appends
`--deselect` to pytest.ini, or skips a marker in conftest.py, and reports green.
`test_the_agent_cannot_loosen_pytest_ini_through_bash` is the regression test for
that move made through the shell instead of the Edit tool.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "protect-test-config.py"


@pytest.fixture(scope="module")
def ptc():
    spec = importlib.util.spec_from_file_location("protect_test_config", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("E156_ALLOW_TEST_CONFIG_EDIT", raising=False)
    monkeypatch.delenv("E156_PROTECT_PYPROJECT", raising=False)


def call(tool, key, value):
    return dict(tool_name=tool, tool_input=dict([(key, value)]))


@pytest.mark.parametrize("path", [
    "tests/conftest.py", "pytest.ini", "tox.ini", "noxfile.py", ".coveragerc",
    "jest.config.js", "vitest.config.ts", "karma.conf.js", ".mocharc.yml",
    "phpunit.xml.dist", "tests/testthat.R", "tests/testthat/setup-fixtures.R",
    "tests/testthat/helper-data.R", "SUB/CONFTEST.PY",
])
def test_protected_files_are_blocked(ptc, path):
    assert ptc.decide(call("Edit", "file_path", path))[0] == ptc.BLOCKED


@pytest.mark.parametrize("path", [
    "src/model.py", "tests/test_model.py", "pyproject.toml", "setup.cfg",
    "docs/conftest-explained.md", "tests/testthat/test-pool.R", "R/pool.R",
])
def test_ordinary_files_are_allowed(ptc, path):
    assert ptc.decide(call("Edit", "file_path", path))[0] == ptc.ALLOWED


def test_the_agent_cannot_loosen_pytest_ini_through_bash(ptc):
    cmd = "echo addopts=--deselect=tests/test_pool.py >> pytest.ini"
    assert ptc.decide(call("Bash", "command", cmd))[0] == ptc.BLOCKED


@pytest.mark.parametrize("cmd", [
    "sed -i s/0.05/0.5/ tests/conftest.py",
    "rm tests/conftest.py",
    "git restore --source=HEAD~2 pytest.ini",
])
def test_write_shaped_bash_is_blocked(ptc, cmd):
    assert ptc.decide(call("Bash", "command", cmd))[0] == ptc.BLOCKED


@pytest.mark.parametrize("cmd", [
    "cat tests/conftest.py", "python -m pytest -c pytest.ini -q", "grep fixture tests/conftest.py",
    "echo hello > notes.txt",
])
def test_reading_or_unrelated_bash_is_allowed(ptc, cmd):
    assert ptc.decide(call("Bash", "command", cmd))[0] == ptc.ALLOWED


def test_read_tool_is_never_blocked(ptc):
    assert ptc.decide(call("Read", "file_path", "tests/conftest.py"))[0] == ptc.ALLOWED


def test_pyproject_is_protected_only_when_opted_in(ptc, monkeypatch):
    assert ptc.decide(call("Edit", "file_path", "pyproject.toml"))[0] == ptc.ALLOWED
    monkeypatch.setenv("E156_PROTECT_PYPROJECT", "1")
    assert ptc.decide(call("Edit", "file_path", "pyproject.toml"))[0] == ptc.BLOCKED


def test_human_override_allows(ptc, monkeypatch):
    monkeypatch.setenv("E156_ALLOW_TEST_CONFIG_EDIT", "1")
    assert ptc.decide(call("Edit", "file_path", "tests/conftest.py"))[0] == ptc.ALLOWED


def test_block_message_tells_the_agent_to_disclose(ptc):
    code, msg = ptc.decide(call("Edit", "file_path", "pytest.ini"))
    assert code == ptc.BLOCKED
    assert "tell the human" in msg and "Do NOT work around" in msg


def _run(stdin_text, env_extra=None):
    import os
    env = dict(os.environ)
    env.pop("E156_ALLOW_TEST_CONFIG_EDIT", None)
    env.pop("E156_PROTECT_PYPROJECT", None)
    env.update(env_extra or dict())
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], input=stdin_text,
                          capture_output=True, text=True, env=env)


def test_end_to_end_exit_codes_follow_the_hook_contract():
    blocked = _run(json.dumps(call("Write", "file_path", "tests/conftest.py")))
    assert blocked.returncode == 2 and "BLOCKED" in blocked.stderr
    allowed = _run(json.dumps(call("Write", "file_path", "src/x.py")))
    assert allowed.returncode == 0 and allowed.stderr == ""


def test_unreadable_input_is_reported_not_silently_passed():
    bad = _run("this is not json")
    assert bad.returncode == 1 and "NOT checked" in bad.stderr


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
