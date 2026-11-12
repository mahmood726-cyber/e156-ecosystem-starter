"""Safety controls for the disposable Windows integration entrypoint.

These tests never run an installer or download a component. The real chain is
reserved for the separately gated GitHub-hosted Windows workflow.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows_install_smoke.ps1"
POWERSHELL = shutil.which("powershell.exe") if os.name == "nt" else None
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell safety controls")


def run_script(script, *args, env=None):
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(script), *map(str, args)],
        env=env, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("metadata", [
    {"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows"},
    {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "Windows"},
    {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux"},
])
def test_non_disposable_context_refuses_before_writing(tmp_path, metadata):
    environment = {**os.environ, **metadata, "RUNNER_TEMP": str(tmp_path)}
    result = run_script(SCRIPT, env=environment)
    assert result.returncode != 0
    assert "disposable GitHub-hosted Windows runner" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_import_has_no_install_side_effects(tmp_path):
    result = run_script(SCRIPT, "-Import", env={**os.environ, "RUNNER_TEMP": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("case", ["existing", "outside", "parent"])
def test_existing_or_unconfined_target_is_refused(tmp_path, case):
    runner_temp = tmp_path / "runner temp"
    runner_temp.mkdir()
    candidate = {
        "existing": runner_temp / "existing",
        "outside": tmp_path / "sibling",
        "parent": runner_temp,
    }[case]
    if case == "existing":
        candidate.mkdir()
        (candidate / "keep.txt").write_text("preserve me", encoding="utf-8")
    driver = tmp_path / "safety.ps1"
    driver.write_text(
        "param($Source, $ParentDir, $Candidate)\n"
        "$ErrorActionPreference = 'Stop'\n"
        ". $Source -Import\n"
        "Assert-NewSmokeRoot -ParentPath $ParentDir -CandidatePath $Candidate\n",
        encoding="utf-8",
    )
    result = run_script(driver, SCRIPT, runner_temp, candidate)
    assert result.returncode != 0
    assert "REFUSED" in result.stderr
    if case == "existing":
        assert (candidate / "keep.txt").read_text(encoding="utf-8") == "preserve me"
    if case == "outside":
        assert not candidate.exists()


def test_child_command_failure_cannot_be_reported_as_success(tmp_path):
    driver = tmp_path / "exit-check.ps1"
    driver.write_text(
        "param($Source, $Shell)\n"
        "$ErrorActionPreference = 'Stop'\n"
        ". $Source -Import\n"
        "Invoke-CheckedNative $Shell @('-NoProfile', '-Command', 'exit 7')\n",
        encoding="utf-8",
    )
    result = run_script(driver, SCRIPT, POWERSHELL)
    assert result.returncode != 0
    assert "exit 7" in result.stderr


def test_linked_runner_temp_is_refused(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    junction = tmp_path / "linked runner temp"
    driver = tmp_path / "junction-check.ps1"
    driver.write_text(
        "param($Source, $Target, $Link)\n"
        "$ErrorActionPreference = 'Stop'\n"
        ". $Source -Import\n"
        "$null = New-Item -ItemType Junction -Path $Link -Target $Target\n"
        "Assert-NewSmokeRoot -ParentPath $Link -CandidatePath (Join-Path $Link 'new-run')\n",
        encoding="utf-8",
    )
    result = run_script(driver, SCRIPT, target, junction)
    assert result.returncode != 0
    assert "linked paths" in result.stderr
    assert list(target.iterdir()) == []


def test_multiple_executable_matches_choose_first_path(tmp_path):
    driver = tmp_path / "application-resolution.ps1"
    driver.write_text(
        "param($Source)\n"
        "$ErrorActionPreference = 'Stop'\n"
        ". $Source -Import\n"
        "function Get-Command { param($Name, $CommandType, $ErrorAction)\n"
        "  [pscustomobject]@{Source = 'first-python.exe'}\n"
        "  [pscustomobject]@{Source = 'second-python.exe'}\n"
        "}\n"
        "$selected = Resolve-SmokeApplication -Name 'python'\n"
        "if ($selected -cne 'first-python.exe') { throw 'Multiple applications combined' }\n"
        "Write-Output $selected\n", encoding="utf-8")
    result = run_script(driver, SCRIPT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "first-python.exe"
