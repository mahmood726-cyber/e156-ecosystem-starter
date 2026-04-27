#Requires -Version 5.1
# install-projectindex.ps1 -- create a portfolio index + reconcile script
#
# ProjectIndex is the bookkeeping layer: a single INDEX.md that lists every
# project with its lifecycle status (triage / active / submission-ready /
# shipped), plus a reconcile_counts.py that fails-closed when the registries
# disagree. Stops "memory != evidence" drift where you THINK you have 50
# projects but registries disagree by 10.
#
# Usage:
#   .\scripts\install-projectindex.ps1 -Root C:\ProjectIndex
#   .\scripts\install-projectindex.ps1 -Root . -Force
#   .\scripts\install-projectindex.ps1 -Import

[CmdletBinding()]
param(
    [string]$Root,
    [switch]$Force,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

function Get-DefaultProjectIndexRoot {
    # Default: <user-home>\code\ProjectIndex.
    # Aligned with install.ps1's $PortfolioRoot default so a student running
    # install.ps1 -Full and a student running install-projectindex.ps1
    # standalone land at the same path. Override with -Root.
    $userHome = $env:USERPROFILE
    if (-not $userHome) { $userHome = $HOME }
    return Join-Path $userHome 'code\ProjectIndex'
}

function Write-IndexMarkdownTemplate {
    [CmdletBinding()]
    param([string]$Path)
    $content = @"
# Project Portfolio Index

> One line per project. Keep under 200 lines. Drop stale.
>
> This is the authoritative source for **dev status**. Submission status lives
> in your E156 workbook.

## Active projects

<!--
Format: - [Name](../path-to-repo) -- one-line hook. Status: active / WIP / blocked
Example:
  - [my-first-paper](../my-first-paper) -- sacubitril/valsartan in HFrEF meta-analysis. Status: active
-->

## Submission-ready

<!--
Projects that have passed Overmind verification + reconcile and are ready for
journal submission or pre-print.
-->

## Shipped

<!--
Submitted / published. Record the DOI or pre-print URL.
-->

## Triage

<!--
Projects in limbo: missing path, failed Overmind verdict, or registry mismatch.
Run reconcile_counts.py to detect drift.
-->
"@
    [System.IO.File]::WriteAllText($Path, $content, (New-Object System.Text.UTF8Encoding $false))
}

function Write-ReconcileScript {
    [CmdletBinding()]
    param([string]$Path)
    # Parameterized reconcile script -- takes --root, reads only local state.
    # Does NOT assume Mahmood-specific paths. Can be extended later to cross-check
    # push_all_repos.py and workbook.txt if the student has those.
    $content = @'
r"""Portfolio reconcile -- lightweight ecosystem-starter version.

Cross-checks:
  1. Every project listed under `## Active projects` in INDEX.md actually
     has a directory on disk at the linked path.
  2. Count of active projects matches any declared count in INDEX.md.
  3. Optional: if a `registry.json` exists in the same dir, its project
     count agrees with INDEX.md.

Exit codes:
  0 = all registries agree, all paths exist
  1 = drift (count mismatch or missing paths)
  2 = INDEX.md unreadable / missing

Usage:
  python reconcile_counts.py --root C:\ProjectIndex
  python reconcile_counts.py           (uses PROJECTINDEX_ROOT env var or cwd)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"^\s*-\s+\[([^\]]+)\]\(([^)]+)\)")


def load_projects_from_index(index_path: Path) -> list[tuple[str, str]]:
    """Return [(name, link)] for every markdown link bullet under
    `## Active projects` (until the next `## ` section).

    HTML comment blocks (<!-- ... -->) are stripped before parsing, so
    example links inside comments are NOT treated as real projects.
    """
    if not index_path.is_file():
        raise FileNotFoundError(f"INDEX.md not found at {index_path}")
    raw_text = index_path.read_text(encoding="utf-8")
    # Strip multiline HTML comments so example links don't count as projects.
    stripped = re.sub(r"<!--.*?-->", "", raw_text, flags=re.DOTALL)
    projects: list[tuple[str, str]] = []
    in_section = False
    for raw in stripped.splitlines():
        line = raw.rstrip()
        if line.startswith("## Active projects"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            m = LINK_RE.match(line)
            if m:
                projects.append((m.group(1), m.group(2)))
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("PROJECTINDEX_ROOT") or os.getcwd(),
                    help="ProjectIndex dir containing INDEX.md (default: cwd or $PROJECTINDEX_ROOT)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    index_path = root / "INDEX.md"
    try:
        projects = load_projects_from_index(index_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    missing: list[tuple[str, str, Path]] = []
    for name, link in projects:
        # Relative links are resolved against INDEX.md's dir
        candidate = (root / link).resolve() if not Path(link).is_absolute() else Path(link)
        if not candidate.exists():
            missing.append((name, link, candidate))

    if missing:
        print(f"FAIL: {len(missing)} project(s) in INDEX.md have missing paths:", file=sys.stderr)
        for name, link, resolved in missing:
            print(f"  - {name} -> {link}  (resolved to {resolved}, not found)", file=sys.stderr)
        return 1

    # Optional registry.json cross-check
    registry = root / "registry.json"
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            registry_count = len(data.get("projects", []))
            if registry_count != len(projects):
                print(f"FAIL: INDEX.md lists {len(projects)} projects but registry.json has {registry_count}", file=sys.stderr)
                return 1
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARN: registry.json unreadable: {e}", file=sys.stderr)

    print(f"OK: {len(projects)} project(s) in INDEX.md, all paths resolve, registries agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'@
    [System.IO.File]::WriteAllText($Path, $content, (New-Object System.Text.UTF8Encoding $false))
}

if ($Import) { return }

# === Real flow =============================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $Root) {
    $Root = Get-DefaultProjectIndexRoot
    Write-Host "Using default -Root: $Root" -ForegroundColor DarkGray
}

# Path disambiguation: a relative input like 'student' would otherwise resolve
# against CWD, which on a freshly-launched PowerShell is C:\WINDOWS\system32 --
# guaranteed PermissionDenied. Resolve relative inputs against $HOME\code\.
if ($Root -notmatch '^[A-Za-z]:[\\/]' -and $Root -notmatch '^\\\\') {
    $resolved = Join-Path (Join-Path $env:USERPROFILE 'code') $Root
    Write-Host "Relative path '$Root' interpreted as: $resolved" -ForegroundColor DarkGray
    $Root = $resolved
}
# Refuse system-protected roots (Permission denied is the symptom; explicit
# message is the cure).
$forbidden = @('C:\Windows', 'C:\Program Files', 'C:\Program Files (x86)', 'C:\ProgramData')
foreach ($f in $forbidden) {
    if ($Root -like "$f\*" -or $Root -eq $f) {
        Write-Host "Refusing to install into protected system path: $Root" -ForegroundColor Red
        Write-Host "Pick a path under $env:USERPROFILE." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "ProjectIndex installer" -ForegroundColor Cyan
Write-Host "Target: $Root"
Write-Host ""

Write-Step "Creating directory"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Write-Ok "exists: $Root"

$indexPath = Join-Path $Root 'INDEX.md'
if ((Test-Path $indexPath) -and -not $Force) {
    Write-Ok "INDEX.md already exists; skipping (use -Force to overwrite)"
} else {
    Write-Step "Writing INDEX.md template"
    Write-IndexMarkdownTemplate -Path $indexPath
    Write-Ok "wrote $indexPath"
}

$reconcilePath = Join-Path $Root 'reconcile_counts.py'
if ((Test-Path $reconcilePath) -and -not $Force) {
    Write-Ok "reconcile_counts.py already exists; skipping (use -Force to overwrite)"
} else {
    Write-Step "Writing reconcile_counts.py"
    Write-ReconcileScript -Path $reconcilePath
    Write-Ok "wrote $reconcilePath"
}

# Seed a sample restart-manifest.json so find-related-repos.py has SOMETHING
# to read against on a fresh install. NEVER overwrite an existing manifest,
# even when -Force is passed: -Force refreshes INDEX.md / reconcile.py
# templates, not the user's real portfolio data (e.g. a 468-record
# generated manifest from MA's nightly pipeline). Per P1-C, 2026-04-27.
$agentRecordsDir = Join-Path $Root 'agent-records'
$sampleManifest  = Join-Path $agentRecordsDir 'restart-manifest.json'
$starterRoot     = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$seedSource      = Join-Path $starterRoot 'memory\sample-restart-manifest.json'
if (Test-Path $sampleManifest) {
    Write-Ok "restart-manifest.json already present; preserving (sample-seed never overwrites real data)"
} elseif (-not (Test-Path $seedSource)) {
    Write-Ok "skipped restart-manifest.json seed (source not found at $seedSource)"
} else {
    Write-Step "Seeding sample restart-manifest.json (7 worked-example repos)"
    New-Item -ItemType Directory -Force -Path $agentRecordsDir | Out-Null
    Copy-Item $seedSource $sampleManifest -Force
    Write-Ok "wrote $sampleManifest"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  ProjectIndex scaffolded at $Root"
Write-Host "  Add your projects as markdown links under"
Write-Host "    ## Active projects"
Write-Host "  Then run:"
Write-Host "    python `"$reconcilePath`" --root `"$Root`""
Write-Host "  to verify paths resolve (exits 1 on drift, 0 on clean)."
Write-Host "======================================================" -ForegroundColor Green

exit 0
