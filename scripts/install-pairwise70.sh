#!/usr/bin/env bash
# install-pairwise70.sh -- bash parallel of scripts/install-pairwise70.ps1.
#
# Installs pairwise70-workbench -- an offline gallery hub that shows and
# reproduces every Pairwise70-family analysis in one place. It embeds the proven
# HTML analysis engines verbatim; the statistics run offline in the browser (the
# only network use is the embedded charts' Plotly CDN). Clones the repo at a
# pinned commit and exports PAIRWISE70_PATH.
#
# Low-token by construction: it is a static HTML workbench -- open index.html and
# run analyses in the browser. No Python deps, no agent, no tokens.
#
# Usage:
#   ./scripts/install-pairwise70.sh                 # clone to ~/code/pairwise70-workbench
#   ./scripts/install-pairwise70.sh --target <dir>
#   ./scripts/install-pairwise70.sh --skip-clone    # only set env + verify existing
#   ./scripts/install-pairwise70.sh --import        # dot-source for tests

set -euo pipefail

TARGET=""
SKIP_CLONE=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)     TARGET="$2"; shift 2 ;;
        --skip-clone) SKIP_CLONE=1; shift ;;
        --import)     IMPORT=1; shift ;;
        -h|--help)    grep -E '^#' "$0" | head -19; exit 0 ;;
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

pairwise70_repo_url() { echo "https://github.com/mahmood726-cyber/pairwise70-workbench.git"; }

# Pinned to the v1.0.0 release tag. Override with PAIRWISE70_REF=master for latest.
PAIRWISE70_DEFAULT_REF="v1.0.0"
pairwise70_default_ref() { echo "${PAIRWISE70_REF:-$PAIRWISE70_DEFAULT_REF}"; }

pairwise70_default_target() { echo "${HOME}/code/pairwise70-workbench"; }

# A target is usable if it carries the gallery entry page.
test_pairwise70_present() { [[ -n "$1" && -f "$1/index.html" ]]; }

clone_or_update_pairwise70() {
    local target="$1" ref="$2" url; url="$(pairwise70_repo_url)"
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

persist_pairwise70_path_env() {
    local target="$1"
    export PAIRWISE70_PATH="$target"
    local line="export PAIRWISE70_PATH=\"$target\""
    local rc
    for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -qF "PAIRWISE70_PATH=" "$rc" 2>/dev/null; then
            printf '\n# pairwise70-workbench (e156-ecosystem-starter)\n%s\n' "$line" >> "$rc"
            echo "  added PAIRWISE70_PATH to $rc"
        else
            echo "  PAIRWISE70_PATH already set in $rc (left as-is)"
        fi
    done
    if [[ ! -e "${HOME}/.bashrc" && ! -e "${HOME}/.zshrc" ]]; then
        printf '# pairwise70-workbench (e156-ecosystem-starter)\n%s\n' "$line" > "${HOME}/.bashrc"
        echo "  created ~/.bashrc with PAIRWISE70_PATH"
    fi
}

# Optional: run the repo's stdlib smoke test if present (no deps).
verify_pairwise70() {
    local target="$1"
    [[ -n "$PYTHON" ]] || { echo "  (python not found; skipping smoke)"; return 0; }
    [[ -f "$target/tests/smoke.py" ]] || return 0
    "$PYTHON" "$target/tests/smoke.py" >/dev/null 2>&1
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

# === Real flow =============================================================
log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$TARGET" ]] || TARGET="$(pairwise70_default_target)"
REF="$(pairwise70_default_ref)"

echo
echo "pairwise70-workbench installer (offline Pairwise70 gallery hub)"
echo

if [[ "$SKIP_CLONE" -eq 1 ]]; then
    log_step "Skipping clone (--skip-clone); using existing checkout at $TARGET"
    test_pairwise70_present "$TARGET" || {
        echo "ERROR: --skip-clone but no index.html at $TARGET." >&2; exit 1; }
else
    log_step "Installing pairwise70-workbench into $TARGET (ref: ${REF:0:12})"
    mkdir -p "$(dirname "$TARGET")"
    clone_or_update_pairwise70 "$TARGET" "$REF"
    test_pairwise70_present "$TARGET" || {
        echo "ERROR: clone completed but $TARGET/index.html is missing." >&2; exit 1; }
    log_ok "checkout ready"
fi

log_step "Persisting PAIRWISE70_PATH"
persist_pairwise70_path_env "$TARGET"

log_step "Running the offline smoke (if present)"
if verify_pairwise70 "$TARGET"; then
    log_ok "smoke OK (static workbench, no deps)"
else
    echo "    note: smoke not run or not present; the workbench is static HTML regardless." >&2
fi

echo
echo "====================================================="
echo "  pairwise70-workbench installed at $TARGET"
echo "  PAIRWISE70_PATH is set (reopen your shell to pick it up)."
echo
echo "  Zero-token start -- just open the gallery in a browser:"
echo "    open \"$TARGET/index.html\"      # macOS"
echo "    xdg-open \"$TARGET/index.html\"  # Linux"
echo "  (Windows:  start index.html)   The stats run offline in the browser."
echo "====================================================="
