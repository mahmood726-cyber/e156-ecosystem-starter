"""Native Windows canary transport controls, without installation or key access.

Payloads are explicitly synthetic health results. Tests import only the helper,
execute disposable fixture commands and use the unchanged production validator.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install-overmind.ps1"
CHECKER = ROOT / "scripts/check-overmind-canary.py"
POWERSHELL = shutil.which("powershell.exe") if os.name == "nt" else None
GOOD = b'{"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}'
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell 5.1 transport")


def fixture_paths(tmp_path: Path, payload: bytes, exit_code: int, stderr: bytes):
    (tmp_path / "payload.bin").write_bytes(payload)
    (tmp_path / "stderr.bin").write_bytes(stderr)
    emitter = tmp_path / "fixture.py"
    emitter.write_text(
        "from pathlib import Path\nimport sys\n"
        "root = Path(__file__).parent\n"
        "assert sys.argv[1:] == ['meta-verify']\n"
        "sys.stdout.buffer.write((root/'payload.bin').read_bytes())\n"
        "sys.stderr.buffer.write((root/'stderr.bin').read_bytes())\n"
        f"raise SystemExit({exit_code})\n", encoding="utf-8",
    )
    launcher = tmp_path / "overmind fixture.cmd"
    launcher.write_text(f'@"{sys.executable}" "{emitter}" %*\r\n', encoding="utf-8")
    return launcher


def run_powershell(driver: Path, *args):
    # Only OS launch prerequisites; no inherited signing keys or agent settings.
    environment = {name: os.environ[name] for name in
                   ("PATH", "SystemRoot", "WINDIR", "ComSpec", "PATHEXT", "TEMP", "TMP")
                   if name in os.environ}
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(driver), *map(str, args)],
        env=environment, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize(("payload", "exit_code", "stderr", "accepted"), [
    (GOOD, 0, b"", True),
    (GOOD, 0, b"synthetic diagnostic on stderr\n", True),
    (GOOD, 7, b"", False),
    (b'{"passed":false,"verdict":"REJECT","bundle_hash":"0123456789abcdef"}', 0, b"", False),
    (b'{"passed":false,"passed":true,"verdict":"CERTIFIED","bundle_hash":"0123456789abcdef"}', 0, b"", False),
    (b"\xef\xbb\xbf" + GOOD, 0, b"", False),
    (GOOD + b"\n" + GOOD, 0, b"", False),
    (b"diagnostic on stdout\n" + GOOD, 0, b"", False),
    (b"", 0, b"", False),
])
def test_canary_byte_transport_preserves_strict_result_contract(
    tmp_path, payload, exit_code, stderr, accepted,
):
    launcher = fixture_paths(tmp_path, payload, exit_code, stderr)
    driver = tmp_path / "probe.ps1"
    driver.write_text(
        "param($Installer, $Python, $Overmind, $Checker)\n"
        "$ErrorActionPreference = 'Stop'\n"
        ". $Installer -Import\n"
        "$OutputEncoding = [Text.Encoding]::UTF8\n"
        "Invoke-OvermindHealthCanary -PythonPath $Python -OvermindPath $Overmind -CheckerPath $Checker\n",
        encoding="utf-8",
    )
    result = run_powershell(driver, INSTALLER, sys.executable, launcher, CHECKER)
    assert (result.returncode == 0) is accepted, (result.stdout, result.stderr)
    assert ("CERTIFIED local verifier-health fixture" in result.stdout) is accepted
    if stderr:
        assert "synthetic diagnostic on stderr" in result.stderr
    if not accepted:
        assert "REFUSED" in result.stderr


def test_legacy_text_pipe_adds_bom_to_valid_json(tmp_path):
    launcher = fixture_paths(tmp_path, GOOD, 0, b"")
    driver = tmp_path / "legacy.ps1"
    driver.write_text(
        "param($Python, $Overmind, $Checker)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$OutputEncoding = [Text.Encoding]::UTF8\n"
        "$canary = & $Overmind meta-verify 2>&1\n"
        "$canaryJson = $canary -join \"`n\"\n"
        "$canaryJson | & $Python $Checker\n"
        "exit $LASTEXITCODE\n", encoding="utf-8",
    )
    result = run_powershell(driver, sys.executable, launcher, CHECKER)
    assert result.returncode != 0
    assert "not unambiguous JSON" in result.stderr


@pytest.mark.parametrize("stage", ["canary", "checker"])
def test_actual_health_adapter_bounds_orphaned_pipe_descendant(tmp_path, stage):
    """Both native invocations must use containment, not subprocess.run timeout alone."""
    launcher = fixture_paths(tmp_path, GOOD, 0, b"")
    marker = tmp_path / "late-write"
    started = tmp_path / "child-started"
    leaf = (
        "import pathlib,sys,time; pathlib.Path(sys.argv[2]).touch(); "
        "time.sleep(2.5); pathlib.Path(sys.argv[1]).touch()"
    )
    orphan_source = (
        "import os,subprocess,sys\n"
        f"subprocess.Popen([sys.executable, '-c', {leaf!r}, {str(marker)!r}, {str(started)!r}])\n"
        f"sys.stdout.buffer.write({GOOD!r}); sys.stdout.buffer.flush()\n"
        "os._exit(0)\n"
    )
    checker = CHECKER
    if stage == "canary":
        (tmp_path / "fixture.py").write_text(orphan_source, encoding="utf-8")
    else:
        checker = tmp_path / "orphan-checker.py"
        checker.write_text(orphan_source, encoding="utf-8")
    driver = tmp_path / "timeout-probe.ps1"
    driver.write_text(
        "param($Installer, $Python, $Overmind, $Checker)\n"
        "$ErrorActionPreference = 'Stop'\n"
        ". $Installer -Import\n"
        "Invoke-OvermindHealthCanary -PythonPath $Python -OvermindPath $Overmind "
        "-CheckerPath $Checker -TimeoutSeconds 0.8 -CheckerTimeoutSeconds 0.8\n",
        encoding="utf-8",
    )
    began = time.monotonic()
    result = run_powershell(driver, INSTALLER, sys.executable, launcher, checker)
    assert time.monotonic() - began < 4
    assert result.returncode != 0
    assert "timed out" in result.stderr
    assert started.is_file(), "descendant must start before timeout is tested"
    assert "CERTIFIED local verifier-health fixture" not in result.stdout
    time.sleep(2.6)
    assert not marker.exists()
