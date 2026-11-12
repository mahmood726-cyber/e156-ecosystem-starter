"""Real local-Git installer controls; synthetic files, no research findings."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bounded_native", ROOT / "scripts/bounded_native.py")
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
POWERSHELL = shutil.which("powershell.exe") if os.name == "nt" else None


def test_large_stderr_is_drained_without_leaking_it():
    result = transport.run([sys.executable, "-c",
                            "import sys; sys.stderr.write('private diagnostic'*100000); print('ok')"], 10)
    assert result == b"ok\r\n" if os.name == "nt" else result == b"ok\n"


def test_native_failure_is_refused_without_disclosing_stderr():
    with pytest.raises(transport.Refused, match="exit 7") as error:
        transport.run([sys.executable, "-c", "import sys; sys.stderr.write('private'); sys.exit(7)"], 10)
    assert "private" not in str(error.value)


def test_timeout_terminates_child_tree(tmp_path):
    marker = tmp_path / "late-write"
    code = "import time,pathlib; time.sleep(2); pathlib.Path(__import__('sys').argv[1]).touch()"
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); time.sleep(10)"
    started = time.monotonic()
    with pytest.raises(transport.Refused, match="timed out"):
        transport.run([sys.executable, "-c", parent, code, str(marker)], 0.3)
    assert time.monotonic() - started < 5
    time.sleep(2.1)
    assert not marker.exists()


@pytest.mark.parametrize("nested", [False, True])
def test_timeout_terminates_descendants_after_native_parent_exits(tmp_path, nested):
    marker = tmp_path / "late-write"
    started = tmp_path / "child-started"
    leaf = (
        "import pathlib,sys,time; pathlib.Path(sys.argv[2]).touch(); "
        "time.sleep(2.5); pathlib.Path(sys.argv[1]).touch()"
    )
    parent = (
        "import subprocess,sys,os; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],*sys.argv[2:]]); os._exit(0)"
    )
    arguments = [sys.executable, "-c", parent, leaf, str(marker), str(started)]
    if nested:
        arguments = [sys.executable, "-c", parent, parent, leaf, str(marker), str(started)]
    began = time.monotonic()
    with pytest.raises(transport.Refused, match="timed out"):
        transport.run(arguments, 0.8)
    assert time.monotonic() - began < 3
    assert started.is_file(), "descendant must run before the timeout control is meaningful"
    time.sleep(2.6)
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows pre-spawn containment gate")
def test_job_assignment_failure_never_releases_native_command(tmp_path, monkeypatch):
    marker = tmp_path / "must-not-run"

    def refuse_assignment(self, pid):
        time.sleep(0.3)
        assert not marker.exists()
        raise transport.Refused("synthetic containment assignment failure")

    monkeypatch.setattr(transport._WindowsJob, "assign", refuse_assignment)
    with pytest.raises(transport.Refused, match="containment assignment failure"):
        transport.run([sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
                       str(marker)], 2)
    assert not marker.exists()


def test_binary_stdin_and_opt_in_stderr_are_not_text_transcoded():
    diagnostics = []
    result = transport.run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stderr.buffer.write(b'warning')"],
        10, input=b"\xef\xbb\xbf{\"test\":true}\x00", stderr_sink=diagnostics.append,
    )
    assert result == b"\xef\xbb\xbf{\"test\":true}\x00"
    assert diagnostics == [b"warning"]


def test_git_child_has_no_interactive_prompt():
    code = "import os,sys; assert sys.stdin.read()==''; print(os.environ['GIT_TERMINAL_PROMPT'],os.environ['GCM_INTERACTIVE'])"
    assert transport.run([sys.executable, "-c", code], 10).strip() == b"0 Never"


def git(*args):
    return subprocess.run(["git", *map(str, args)], capture_output=True, text=True,
                          check=True, timeout=15).stdout.strip()


def native_path(path):
    # Exercise Git's long-path support even when the host Win32 opt-in is off.
    return Path("\\\\?\\" + str(path)) if os.name == "nt" else path


@pytest.fixture
def origin(tmp_path):
    path = tmp_path / "source"
    git("init", "--quiet", path)
    nested = path / ("a" * 90) / ("b" * 90)
    native_path(nested).mkdir(parents=True)
    native_path(nested / "long.txt").write_text("synthetic fixture", encoding="utf-8")
    git("-C", path, "config", "core.longpaths", "true")
    git("-C", path, "add", ".")
    git("-C", path, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "synthetic path fixture")
    git("-C", path, "tag", "v1.0.0")
    return path, git("-C", path, "rev-parse", "HEAD")


def install(tmp_path, origin, target, ref):
    driver = tmp_path / "invoke.ps1"
    driver.write_text("param($Source,$FixtureOrigin,$FixtureTarget,$FixtureRef)\n"
                      "$ErrorActionPreference='Stop'\n. $Source -Import\n"
                      "function Get-ExtractorRepoUrl { return $FixtureOrigin }\n"
                      "Install-ExtractorClone -TargetDir $FixtureTarget -Ref $FixtureRef\n", encoding="utf-8")
    return subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(driver),
                           str(ROOT / "scripts/install-extractor.ps1"), str(origin), str(target), ref],
                          capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell installer")
def test_long_paths_exact_ref_and_missing_ref_cleanup(tmp_path, origin):
    source, sha = origin
    target = tmp_path / "installed path with spaces"
    result = install(tmp_path, source, target, "v1.0.0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git("-C", target, "rev-parse", "HEAD") == sha
    assert git("-C", target, "rev-parse", "--is-shallow-repository") == "true"
    assert native_path(target / ("a" * 90) / ("b" * 90) / "long.txt").read_text() == "synthetic fixture"
    result = install(tmp_path, source, target, "absent-ref")
    assert result.returncode != 0
    assert "requested extractor Git ref unavailable" in result.stderr
    assert git("-C", target, "rev-parse", "HEAD") == sha
    absent = tmp_path / "new install"
    result = install(tmp_path, source, absent, "absent-ref")
    assert result.returncode != 0
    assert not absent.exists()
    assert list(tmp_path.glob(".extractor-stage-*")) == []


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell installer")
@pytest.mark.parametrize("ref", ["--upload-pack=evil", "refs/../main", "refs//main", "v1.0.0/"])
def test_unsafe_ref_refused_before_mutation(tmp_path, ref):
    target = tmp_path / "installed"
    result = install(tmp_path, tmp_path / "absent", target, ref)
    assert result.returncode != 0
    assert "invalid extractor Git ref" in result.stderr
    assert not target.exists()
