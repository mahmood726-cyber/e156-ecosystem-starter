"""Run the Windows updater with a local ZIP and real installer copy helpers.

All destinations are temporary. No network, agent configuration, or optional
package installation is touched; the child records the actual forwarded flags.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe") if os.name == "nt" else None
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="actual Windows updater process")


@pytest.mark.parametrize("full", [False, True], ids=["base", "full"])
def test_updater_preserves_each_local_edit_and_memory_across_updates(tmp_path, full):
    source = tmp_path / "starter source"
    target = tmp_path / "user files"
    entries = ("rules/rules.md", "rules/_index.yaml", "AGENTS.md")
    for name in entries:
        incoming, existing = source / name, target / name
        incoming.parent.mkdir(parents=True, exist_ok=True)
        existing.parent.mkdir(parents=True, exist_ok=True)
        incoming.write_text("CURRENT STARTER " + name, encoding="utf-8")
        existing.write_text("FIRST USER EDIT " + name, encoding="utf-8")
    memory = target / "memory" / "MEMORY.md"
    memory.parent.mkdir()
    memory.write_text("PRIVATE EXISTING MEMORY", encoding="utf-8")
    installer = r"""param([switch]$Force, [switch]$NonInteractive, [switch]$Full)
$ErrorActionPreference = 'Stop'
$forwarded = @{Force = [bool]$Force; NonInteractive = [bool]$NonInteractive; Full = [bool]$Full}
. $env:UPDATE_TEST_INSTALL_SOURCE -Import
$null = Copy-RulesToAgent -SourceRulesDir (Join-Path $env:UPDATE_TEST_SOURCE 'rules') -TargetRulesDir (Join-Path $env:UPDATE_TEST_TARGET 'rules') -Force:$forwarded.Force
$null = Copy-ContextFiles -SourceRoot $env:UPDATE_TEST_SOURCE -TargetDir $env:UPDATE_TEST_TARGET -Force:$forwarded.Force
$null = Copy-MemoryScaffold -SourceMemoryDir (Join-Path $env:UPDATE_TEST_SOURCE 'memory') -TargetMemoryDir (Join-Path $env:UPDATE_TEST_TARGET 'memory')
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $env:UPDATE_TEST_TARGET 'invocation.json'), ($forwarded | ConvertTo-Json), $utf8)
exit 0
"""
    archive = tmp_path / "local-update.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("e156-ecosystem-starter-main/install/install.ps1", installer)
    driver = tmp_path / "run-update.ps1"
    driver.write_text(r"""param([string]$Updater, [switch]$Full)
$ErrorActionPreference = 'Stop'
function Invoke-WebRequest {
    param($Uri, $OutFile, [switch]$UseBasicParsing, $ErrorAction)
    if ($Uri -cne 'https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/main.zip') { throw 'Unexpected update URL' }
    Copy-Item -LiteralPath $env:UPDATE_TEST_ARCHIVE -Destination $OutFile -ErrorAction Stop
}
& $Updater -Full:$Full
""", encoding="utf-8")
    environment = {
        **os.environ,
        "TEMP": str(tmp_path), "TMP": str(tmp_path),
        "UPDATE_TEST_ARCHIVE": str(archive),
        "UPDATE_TEST_SOURCE": str(source),
        "UPDATE_TEST_TARGET": str(target),
        "UPDATE_TEST_INSTALL_SOURCE": str(ROOT / "install" / "install.ps1"),
    }
    command = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(driver), "-Updater", str(ROOT / "scripts" / "update-ecosystem.ps1")]
    if full:
        command.append("-Full")
    for revision in ("FIRST", "SECOND"):
        if revision == "SECOND":
            for name in entries:
                (target / name).write_text("SECOND USER EDIT " + name, encoding="utf-8")
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        forwarded = json.loads((target / "invocation.json").read_text(encoding="utf-8"))
        assert forwarded == {"Force": False, "NonInteractive": True, "Full": full}
        for name in entries:
            destination = target / name
            assert destination.read_text(encoding="utf-8") == "CURRENT STARTER " + name
            backups = [p.read_text(encoding="utf-8") for p in destination.parent.glob(destination.name + ".user*")]
            assert "FIRST USER EDIT " + name in backups
            if revision == "SECOND":
                assert "SECOND USER EDIT " + name in backups
                assert len(backups) == 2
        assert memory.read_text(encoding="utf-8") == "PRIVATE EXISTING MEMORY"
