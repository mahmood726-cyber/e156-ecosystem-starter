#!/usr/bin/env bash
# install-sentinel.sh -- bash parallel of scripts/install-sentinel.ps1.
#
# Installs the Sentinel pre-push hook into a target repo. pip-installs the
# sentinel package from GitHub on first run if it's not already on PATH.
#
# Usage:
#   ./scripts/install-sentinel.sh --repo <path>
#   ./scripts/install-sentinel.sh --repo . --mode block
#   ./scripts/install-sentinel.sh --skip-pip-install
#   ./scripts/install-sentinel.sh --import

set -euo pipefail

REPO=""
MODE="warn"
SKIP_PIP=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)              REPO="$2"; shift 2 ;;
        --mode)              MODE="$2"; shift 2 ;;
        --skip-pip-install)  SKIP_PIP=1; shift ;;
        --import)            IMPORT=1; shift ;;
        -h|--help)           grep -E '^#' "$0" | head -20; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

test_sentinel_installed() {
    command -v sentinel >/dev/null 2>&1
}

# Resolve python3 / python (modern Linux defaults to python3 only)
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    PYTHON=""
fi

assert_real_python() {
    if [[ -z "$PYTHON" ]]; then
        echo "ERROR: neither 'python' nor 'python3' found on PATH." >&2
        echo "  Install: sudo apt install python3 python3-pip" >&2
        return 1
    fi
}

install_sentinel_package() {
    # BANDWIDTH TRIPWIRE (set 2026-04-21): measured Sentinel + Overmind fresh
    # install footprint = 4.5 MB. Below the threshold where a preflight UX
    # warning helps. IF a future dependency bump pushes Sentinel alone past
    # ~50 MB (numpy / scipy / torch additions), add an --estimate-mb preflight
    # here using `pip install --dry-run --report` first. See review-findings.md P0-2.
    local src="${1:-git+https://github.com/mahmood726-cyber/Sentinel.git}"
    assert_real_python || return 1
    "$PYTHON" -m pip install --quiet --disable-pip-version-check "$src" 2>&1 | sed 's/^/  /'
}

install_sentinel_hook_in_repo() {
    local repo_path="$1" hook_mode="$2"
    local abs
    abs="$(cd "$repo_path" 2>/dev/null && pwd)" || { echo "ERROR: not a dir: $repo_path" >&2; return 1; }
    [[ -d "$abs/.git" ]] || { echo "ERROR: not a git repo (no .git/): $abs" >&2; return 1; }
    sentinel install-hook --repo "$abs" --mode "$hook_mode" 2>&1 | sed 's/^/  /'
}

get_sentinel_bypass_log_path() {
    echo "${HOME}/.sentinel-logs/bypass.log"
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$REPO" ]] || { echo "ERROR: --repo is required. Example: $0 --repo ." >&2; exit 1; }

echo
echo "Sentinel pre-push hook installer"
echo

log_step "Checking for sentinel CLI"
if test_sentinel_installed; then
    log_ok "sentinel already installed"
else
    if [[ "$SKIP_PIP" -eq 1 ]]; then
        echo "ERROR: sentinel not on PATH and --skip-pip-install passed." >&2
        echo "  Install: pip install git+https://github.com/mahmood726-cyber/Sentinel.git" >&2
        exit 1
    fi
    log_step "Installing sentinel from GitHub (first-time setup)"
    install_sentinel_package
    test_sentinel_installed || {
        echo "ERROR: pip install completed but sentinel is still not on PATH." >&2
        echo "  Make sure ~/.local/bin (or your venv bin dir) is on PATH." >&2
        exit 1
    }
    log_ok "sentinel installed"
fi

log_step "Installing pre-push hook in $REPO (mode: $MODE)"
install_sentinel_hook_in_repo "$REPO" "$MODE"
log_ok "hook installed"

echo
echo "Bypass log: $(get_sentinel_bypass_log_path)"
echo "  Use only when a BLOCK is a false positive:"
echo "    SENTINEL_BYPASS=1 git push"
echo
echo "====================================================="
echo "  Sentinel hook installed. It fires on every git push."
echo "  List rules:   sentinel list-rules"
echo "  Uninstall:    sentinel uninstall-hook --repo $REPO"
echo "====================================================="
