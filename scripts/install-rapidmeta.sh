#!/usr/bin/env bash
# install-rapidmeta.sh -- bash parallel of scripts/install-rapidmeta.ps1.
#
# Installs rapidmeta-kit -- the offline, STDLIB-ONLY meta-analysis dashboard
# generator. Its clone.py turns a small JSON config into a self-contained
# RapidMeta HTML dashboard with NO numpy/scipy and NO network. Clones the repo at
# a pinned commit into a target dir and exports RAPIDMETA_KIT_PATH.
#
# Low-token by construction: the whole config -> dashboard path is deterministic
# Python with no LLM in the loop. Nothing here needs an agent or a token budget.
#
# Usage:
#   ./scripts/install-rapidmeta.sh                  # clone to ~/code/rapidmeta-kit
#   ./scripts/install-rapidmeta.sh --target <dir>
#   ./scripts/install-rapidmeta.sh --skip-clone     # only set env + verify existing
#   ./scripts/install-rapidmeta.sh --import         # dot-source for tests

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

rapidmeta_repo_url() { echo "https://github.com/mahmood726-cyber/rapidmeta-kit.git"; }

# Pinned to the v1.1.0 release tag (includes the anti-fabrication fix). Reproducible
# clone -- same supply-chain approach as the Sentinel/Overmind installers. Override
# with RAPIDMETA_REF=main for latest.
RAPIDMETA_DEFAULT_REF="v1.1.0"
rapidmeta_default_ref() { echo "${RAPIDMETA_REF:-$RAPIDMETA_DEFAULT_REF}"; }

rapidmeta_default_target() { echo "${HOME}/code/rapidmeta-kit"; }

# A target is usable if it carries the stdlib dashboard generator.
test_rapidmeta_present() { [[ -n "$1" && -f "$1/clone.py" ]]; }

clone_or_update_rapidmeta() {
    local target="$1" ref="$2" url; url="$(rapidmeta_repo_url)"
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

persist_rapidmeta_path_env() {
    local target="$1"
    export RAPIDMETA_KIT_PATH="$target"
    local line="export RAPIDMETA_KIT_PATH=\"$target\""
    local rc
    for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -qF "RAPIDMETA_KIT_PATH=" "$rc" 2>/dev/null; then
            printf '\n# rapidmeta-kit (e156-ecosystem-starter)\n%s\n' "$line" >> "$rc"
            echo "  added RAPIDMETA_KIT_PATH to $rc"
        else
            echo "  RAPIDMETA_KIT_PATH already set in $rc (left as-is)"
        fi
    done
    if [[ ! -e "${HOME}/.bashrc" && ! -e "${HOME}/.zshrc" ]]; then
        printf '# rapidmeta-kit (e156-ecosystem-starter)\n%s\n' "$line" > "${HOME}/.bashrc"
        echo "  created ~/.bashrc with RAPIDMETA_KIT_PATH"
    fi
}

# Verify the stdlib-only generator is syntactically importable (no network/deps).
verify_rapidmeta() {
    local target="$1"
    [[ -n "$PYTHON" ]] || { echo "  (python not found; skipping check)"; return 0; }
    "$PYTHON" -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$target/clone.py"
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

# === Real flow =============================================================
log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$TARGET" ]] || TARGET="$(rapidmeta_default_target)"
REF="$(rapidmeta_default_ref)"

echo
echo "rapidmeta-kit installer (offline, stdlib-only meta-analysis dashboards)"
echo

if [[ "$SKIP_CLONE" -eq 1 ]]; then
    log_step "Skipping clone (--skip-clone); using existing checkout at $TARGET"
    test_rapidmeta_present "$TARGET" || {
        echo "ERROR: --skip-clone but no clone.py at $TARGET." >&2; exit 1; }
else
    log_step "Installing rapidmeta-kit into $TARGET (ref: ${REF:0:12})"
    mkdir -p "$(dirname "$TARGET")"
    clone_or_update_rapidmeta "$TARGET" "$REF"
    test_rapidmeta_present "$TARGET" || {
        echo "ERROR: clone completed but $TARGET/clone.py is missing." >&2; exit 1; }
    log_ok "checkout ready"
fi

log_step "Persisting RAPIDMETA_KIT_PATH"
persist_rapidmeta_path_env "$TARGET"

log_step "Verifying the stdlib generator parses"
if verify_rapidmeta "$TARGET" >/dev/null 2>&1; then
    log_ok "clone.py OK (stdlib-only, no deps to install)"
else
    echo "    WARNING: clone.py parse check did not pass (python missing?)." >&2
fi

echo
echo "====================================================="
echo "  rapidmeta-kit installed at $TARGET"
echo "  RAPIDMETA_KIT_PATH is set (reopen your shell to pick it up)."
echo
echo "  Token-free dashboard from the bundled example:"
echo "    cd \"$TARGET\" && bash run_example.sh        # or RUN_EXAMPLE.bat on Windows"
echo "  Or from your own config (config is positional):"
echo "    python \"$TARGET/clone.py\" my.json --out dashboard.html"
echo "====================================================="
