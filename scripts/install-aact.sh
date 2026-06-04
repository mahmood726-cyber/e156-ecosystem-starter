#!/usr/bin/env bash
# install-aact.sh -- bash parallel of scripts/install-aact.ps1.
#
# Installs aact-cockpit -- a local DuckDB-backed cockpit for large-scale
# ClinicalTrials.gov / AACT analysis that emits self-auditing e156 capsules.
# Clones the repo at a pinned commit into a target dir and exports
# AACT_COCKPIT_PATH.
#
# Footprint note (read this): unlike rapidmeta-kit, RUNNING aact-cockpit needs
# duckdb + numpy AND a local AACT/CT.gov data snapshot. So the deps are OPT-IN
# via --with-data-deps, and the LOW-TOKEN / zero-setup path is to read the
# repo's committed example analyses + capsules (analyses/, templates/) WITHOUT
# building a warehouse at all. Clone is always free; data + deps are opt-in.
#
# Usage:
#   ./scripts/install-aact.sh                   # clone to ~/code/aact-cockpit (no deps)
#   ./scripts/install-aact.sh --target <dir>
#   ./scripts/install-aact.sh --with-data-deps  # also pip-install duckdb + numpy (+the pkg)
#   ./scripts/install-aact.sh --skip-clone      # only set env + verify existing
#   ./scripts/install-aact.sh --import          # dot-source for tests

set -euo pipefail

TARGET=""
WITH_DATA_DEPS=0
SKIP_CLONE=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)         TARGET="$2"; shift 2 ;;
        --with-data-deps) WITH_DATA_DEPS=1; shift ;;
        --skip-clone)     SKIP_CLONE=1; shift ;;
        --import)         IMPORT=1; shift ;;
        -h|--help)        grep -E '^#' "$0" | head -23; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# Resolve a REAL python: skip the Windows Store alias stub (on PATH under git-bash
# but not an interpreter — same trap as install-*.ps1 Assert-RealPython), and
# confirm the candidate actually executes.
PYTHON=""
for _cand in python3 python; do
    if command -v "$_cand" >/dev/null 2>&1; then
        case "$(command -v "$_cand")" in *WindowsApps*) continue ;; esac
        if "$_cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PYTHON="$_cand"; break; fi
    fi
done

aact_repo_url() { echo "https://github.com/mahmood726-cyber/aact-cockpit.git"; }

# Pinned commit (2026-06-04). Override with AACT_REF=master for latest.
AACT_DEFAULT_REF="f8cf87ab99e72e8c13b254534ab8cfd7960b9c3d"
aact_default_ref() { echo "${AACT_REF:-$AACT_DEFAULT_REF}"; }

aact_default_target() { echo "${HOME}/code/aact-cockpit"; }

# A target is usable if it carries a capsule maker entrypoint.
test_aact_present() { [[ -n "$1" && -f "$1/scripts/make_capsule.py" ]]; }

clone_or_update_aact() {
    local target="$1" ref="$2" url; url="$(aact_repo_url)"
    if [[ -d "$target/.git" ]]; then
        echo "  existing checkout: $target (fetch + checkout ${ref:0:12})"
        git -C "$target" fetch --quiet origin "$ref" 2>/dev/null || git -C "$target" fetch --quiet origin
        git -C "$target" checkout --quiet "$ref" 2>&1 | sed 's/^/  /' || true
    else
        echo "  cloning $url"
        local attempt
        for attempt in 1 2 3; do
            if git clone --quiet "$url" "$target" 2>&1 | sed 's/^/  /'; then break; fi
            if [[ "$attempt" -lt 3 ]]; then
                local wait=$(( 2 ** attempt ))
                echo "  clone attempt $attempt failed; retrying in ${wait}s..." >&2
                sleep "$wait"
            else
                echo "  clone failed after 3 attempts" >&2; return 1
            fi
        done
        git -C "$target" checkout --quiet "$ref" 2>&1 | sed 's/^/  /' || true
    fi
}

persist_aact_path_env() {
    local target="$1"
    export AACT_COCKPIT_PATH="$target"
    local line="export AACT_COCKPIT_PATH=\"$target\""
    local rc
    for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -qF "AACT_COCKPIT_PATH=" "$rc" 2>/dev/null; then
            printf '\n# aact-cockpit (e156-ecosystem-starter)\n%s\n' "$line" >> "$rc"
            echo "  added AACT_COCKPIT_PATH to $rc"
        else
            echo "  AACT_COCKPIT_PATH already set in $rc (left as-is)"
        fi
    done
    if [[ ! -e "${HOME}/.bashrc" && ! -e "${HOME}/.zshrc" ]]; then
        printf '# aact-cockpit (e156-ecosystem-starter)\n%s\n' "$line" > "${HOME}/.bashrc"
        echo "  created ~/.bashrc with AACT_COCKPIT_PATH"
    fi
}

install_aact_data_deps() {
    # Heavy: duckdb + numpy (the cockpit's required runtime). Opt-in only.
    local target="$1"
    [[ -n "$PYTHON" ]] || { echo "  ERROR: python not found" >&2; return 1; }
    echo "  pip install -e \"$target\"  (duckdb + numpy)"
    local attempt
    for attempt in 1 2 3; do
        if "$PYTHON" -m pip install --quiet --disable-pip-version-check -e "$target" 2>&1 | sed 's/^/  /'; then
            return 0
        fi
        if [[ "$attempt" -lt 3 ]]; then
            local wait=$(( 2 ** attempt ))
            echo "  pip install attempt $attempt failed; retrying in ${wait}s..." >&2
            sleep "$wait"
        fi
    done
    echo "  pip install failed after 3 attempts" >&2; return 1
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

# === Real flow =============================================================
log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$TARGET" ]] || TARGET="$(aact_default_target)"
REF="$(aact_default_ref)"

echo
echo "aact-cockpit installer (ClinicalTrials.gov/AACT -> e156 capsules)"
echo

if [[ "$SKIP_CLONE" -eq 1 ]]; then
    log_step "Skipping clone (--skip-clone); using existing checkout at $TARGET"
    test_aact_present "$TARGET" || {
        echo "ERROR: --skip-clone but no scripts/make_capsule.py at $TARGET." >&2; exit 1; }
else
    log_step "Installing aact-cockpit into $TARGET (ref: ${REF:0:12})"
    mkdir -p "$(dirname "$TARGET")"
    clone_or_update_aact "$TARGET" "$REF"
    test_aact_present "$TARGET" || {
        echo "ERROR: clone completed but $TARGET/scripts/make_capsule.py is missing." >&2; exit 1; }
    log_ok "checkout ready"
fi

log_step "Persisting AACT_COCKPIT_PATH"
persist_aact_path_env "$TARGET"

if [[ "$WITH_DATA_DEPS" -eq 1 ]]; then
    log_step "Installing data deps (--with-data-deps: duckdb + numpy)"
    install_aact_data_deps "$TARGET" && log_ok "data deps installed" || \
        echo "    WARNING: data deps failed; the read-only example path still works." >&2
fi

echo
echo "====================================================="
echo "  aact-cockpit installed at $TARGET"
echo "  AACT_COCKPIT_PATH is set (reopen your shell to pick it up)."
echo
echo "  Zero-token / zero-setup path (no deps, no data snapshot needed):"
echo "    ls \"$TARGET/analyses\"   \"$TARGET/templates\"     # read committed example capsules"
echo
echo "  Full path (after --with-data-deps AND a local AACT/CT.gov snapshot):"
echo "    python \"$TARGET/scripts/build_warehouse.py\" --help    # build the DuckDB warehouse"
echo "    python \"$TARGET/scripts/make_capsule.py\" --help       # emit an e156 capsule"
[[ "$WITH_DATA_DEPS" -eq 1 ]] || \
echo "  To install the runtime later:  ./scripts/install-aact.sh --with-data-deps"
echo "====================================================="
