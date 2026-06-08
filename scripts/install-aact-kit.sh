#!/usr/bin/env bash
# install-aact-kit.sh -- bash parallel of scripts/install-aact-kit.ps1.
#
# Installs aact-kit -- the shared local-AACT (ClinicalTrials.gov) data-access
# LIBRARY: one API to resolve / load / validate / aggregate AACT across five
# local backends (Postgres, SQLite, ZIP, pipe-delimited TSV dir, CSV dir).
# Clones the repo at a pinned commit into a target dir and exports AACT_KIT_PATH.
#
# Footprint note: aact-kit is a small pip package whose only hard dependency is
# pandas (psycopg2 is optional, only for the Postgres backend). The clone is
# always free; installing the importable package is OPT-IN via --with-deps. The
# LOW-TOKEN / zero-setup path is to read src/aact_kit/ + README.md WITHOUT
# installing anything. (This is the LIBRARY that other CT.gov projects import;
# it is distinct from the aact-cockpit layer, which is a DuckDB analysis cockpit.)
#
# Usage:
#   ./scripts/install-aact-kit.sh                # clone to ~/code/aact-kit (no install)
#   ./scripts/install-aact-kit.sh --target <dir>
#   ./scripts/install-aact-kit.sh --with-deps    # also pip-install -e (import aact_kit)
#   ./scripts/install-aact-kit.sh --skip-clone   # only set env + verify existing
#   ./scripts/install-aact-kit.sh --import       # dot-source for tests

set -euo pipefail

TARGET=""
WITH_DEPS=0
SKIP_CLONE=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)     TARGET="$2"; shift 2 ;;
        --with-deps)  WITH_DEPS=1; shift ;;
        --skip-clone) SKIP_CLONE=1; shift ;;
        --import)     IMPORT=1; shift ;;
        -h|--help)    grep -E '^#' "$0" | head -24; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# Resolve a REAL python: skip the Windows Store alias stub (on PATH under git-bash
# but not an interpreter), and confirm the candidate actually executes.
PYTHON=""
for _cand in python3 python; do
    if command -v "$_cand" >/dev/null 2>&1; then
        case "$(command -v "$_cand")" in *WindowsApps*) continue ;; esac
        if "$_cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PYTHON="$_cand"; break; fi
    fi
done

aactkit_repo_url() { echo "https://github.com/mahmood726-cyber/aact-kit.git"; }

# Pinned to the v1.0.0 release tag. Override with AACT_KIT_REF=main for latest.
AACT_KIT_DEFAULT_REF="v1.0.0"
aactkit_default_ref() { echo "${AACT_KIT_REF:-$AACT_KIT_DEFAULT_REF}"; }

aactkit_default_target() { echo "${HOME}/code/aact-kit"; }

# A target is usable if it carries the importable package source.
test_aactkit_present() { [[ -n "$1" && -f "$1/src/aact_kit/__init__.py" ]]; }

clone_or_update_aactkit() {
    local target="$1" ref="$2" url; url="$(aactkit_repo_url)"
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

persist_aactkit_path_env() {
    local target="$1"
    export AACT_KIT_PATH="$target"
    local line="export AACT_KIT_PATH=\"$target\""
    local rc
    for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -qF "AACT_KIT_PATH=" "$rc" 2>/dev/null; then
            printf '\n# aact-kit (e156-ecosystem-starter)\n%s\n' "$line" >> "$rc"
            echo "  added AACT_KIT_PATH to $rc"
        else
            echo "  AACT_KIT_PATH already set in $rc (left as-is)"
        fi
    done
    if [[ ! -e "${HOME}/.bashrc" && ! -e "${HOME}/.zshrc" ]]; then
        printf '# aact-kit (e156-ecosystem-starter)\n%s\n' "$line" > "${HOME}/.bashrc"
        echo "  created ~/.bashrc with AACT_KIT_PATH"
    fi
}

install_aactkit_deps() {
    # Light: pandas (psycopg2 only for the optional Postgres backend). Opt-in.
    local target="$1"
    [[ -n "$PYTHON" ]] || { echo "  ERROR: python not found" >&2; return 1; }
    echo "  pip install -e \"$target\"  (pandas)"
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

[[ -n "$TARGET" ]] || TARGET="$(aactkit_default_target)"
REF="$(aactkit_default_ref)"

echo
echo "aact-kit installer (shared local-AACT data-access library)"
echo

if [[ "$SKIP_CLONE" -eq 1 ]]; then
    log_step "Skipping clone (--skip-clone); using existing checkout at $TARGET"
    test_aactkit_present "$TARGET" || {
        echo "ERROR: --skip-clone but no src/aact_kit/__init__.py at $TARGET." >&2; exit 1; }
else
    log_step "Installing aact-kit into $TARGET (ref: ${REF:0:12})"
    mkdir -p "$(dirname "$TARGET")"
    clone_or_update_aactkit "$TARGET" "$REF"
    test_aactkit_present "$TARGET" || {
        echo "ERROR: clone completed but $TARGET/src/aact_kit/__init__.py is missing." >&2; exit 1; }
    log_ok "checkout ready"
fi

log_step "Persisting AACT_KIT_PATH"
persist_aactkit_path_env "$TARGET"

if [[ "$WITH_DEPS" -eq 1 ]]; then
    log_step "Installing the package (--with-deps: pip install -e, pulls pandas)"
    install_aactkit_deps "$TARGET" && log_ok "aact-kit importable (import aact_kit)" || \
        echo "    WARNING: install failed; the read-only source path still works." >&2
fi

echo
echo "====================================================="
echo "  aact-kit installed at $TARGET"
echo "  AACT_KIT_PATH is set (reopen your shell to pick it up)."
echo
echo "  Zero-token / zero-setup path (no install needed):"
echo "    ls \"$TARGET/src/aact_kit\" ; less \"$TARGET/README.md\"   # read the API"
echo
echo "  Full path (after --with-deps):"
echo "    python -c \"from aact_kit import load_table, resolve_aact_location\""
echo "    # set AACT_TSV_DIR / AACT_CSV_DIR / AACT_DSN / AACT_SQLITE / AACT_ZIP to your snapshot"
[[ "$WITH_DEPS" -eq 1 ]] || \
echo "  To install the package later:  ./scripts/install-aact-kit.sh --with-deps"
echo "====================================================="
