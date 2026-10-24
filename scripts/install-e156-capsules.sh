#!/usr/bin/env bash
# install-e156-capsules.sh -- bash parallel of scripts/install-e156-capsules.ps1.
#
# Installs the BUNDLED E156 capsule + offline chart-kit authoring template
# (templates/e156-capsule/) into a target dir and exports E156_CAPSULES_PATH.
#
# This layer is unique: it makes NO network call and clones NOTHING. The template
# (capsule contract + stdlib-only SVG chart-kit + a pre-baked sample) is shipped
# inside the starter, so it works fully offline with zero tokens -- the lowest-
# footprint layer in the ecosystem, by design.
#
# Usage:
#   ./scripts/install-e156-capsules.sh                 # copy to ~/code/e156-capsules
#   ./scripts/install-e156-capsules.sh --target <dir>
#   ./scripts/install-e156-capsules.sh --skip-copy     # only set env + verify existing
#   ./scripts/install-e156-capsules.sh --import        # dot-source for tests

set -euo pipefail

TARGET=""
SKIP_COPY=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)    TARGET="$2"; shift 2 ;;
        --skip-copy) SKIP_COPY=1; shift ;;
        --import)    IMPORT=1; shift ;;
        -h|--help)   grep -E '^#' "$0" | head -20; exit 0 ;;
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

# Source template dir: templates/e156-capsule/ relative to this script's repo root.
e156_template_dir() {
    local script_dir; script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "$(cd "$script_dir/.." && pwd)/templates/e156-capsule"
}

e156_default_target() {
    echo "${HOME}/code/e156-capsules"
}

# A target is usable if it carries the offline chart-kit primitive.
test_e156_capsules_present() {
    [[ -n "$1" && -f "$1/chartkit.py" ]]
}

copy_e156_template() {
    local src="$1" dst="$2"
    [[ -d "$src" ]] || { echo "  bundled template not found at $src" >&2; return 1; }
    mkdir -p "$dst"
    # cp -R contents (portable; no rsync dependency)
    cp -R "$src/." "$dst/"
}

persist_e156_path_env() {
    local target="$1"
    export E156_CAPSULES_PATH="$target"
    local line="export E156_CAPSULES_PATH=\"$target\""
    local rc
    for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -qF "E156_CAPSULES_PATH=" "$rc" 2>/dev/null; then
            printf '\n# e156-capsules (e156-ecosystem-starter)\n%s\n' "$line" >> "$rc"
            echo "  added E156_CAPSULES_PATH to $rc"
        else
            echo "  E156_CAPSULES_PATH already set in $rc (left as-is)"
        fi
    done
    if [[ ! -e "${HOME}/.bashrc" && ! -e "${HOME}/.zshrc" ]]; then
        printf '# e156-capsules (e156-ecosystem-starter)\n%s\n' "$line" > "${HOME}/.bashrc"
        echo "  created ~/.bashrc with E156_CAPSULES_PATH"
    fi
}

# Verify the offline chart-kit actually renders the bundled sample (token-free).
verify_chartkit() {
    local target="$1" out
    [[ -n "$PYTHON" ]] || { echo "REFUSED: Python is required to verify the E156 chart-kit." >&2; return 1; }
    # Keep verification inside the target for native Windows Python under Git Bash.
    # A unique path avoids deleting/accepting a stale user's .chartkit_check.svg.
    out="$target/.chartkit_check.$.$RANDOM.svg"
    if "$PYTHON" "$target/chartkit.py" "$target/sample.capsule.json" --out "$out" >/dev/null 2>&1 &&
       [[ -s "$out" ]] &&
       "$PYTHON" -c 'import sys, xml.etree.ElementTree as ET; root=ET.parse(sys.argv[1]).getroot(); sys.exit(0 if root.tag in ("svg", "{http://www.w3.org/2000/svg}svg") else 1)' "$out" >/dev/null 2>&1; then
        rm -f -- "$out"
        return 0
    fi
    rm -f -- "$out"
    return 1
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

# === Real flow =============================================================
log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$TARGET" ]] || TARGET="$(e156_default_target)"

echo
echo "e156-capsules installer (offline capsule + chart-kit template; zero network)"
echo

if [[ "$SKIP_COPY" -eq 1 ]]; then
    log_step "Skipping copy (--skip-copy); using existing template at $TARGET"
    test_e156_capsules_present "$TARGET" || {
        echo "ERROR: --skip-copy but no chartkit.py at $TARGET." >&2; exit 1; }
else
    SRC="$(e156_template_dir)"
    log_step "Copying bundled template -> $TARGET"
    copy_e156_template "$SRC" "$TARGET"
    test_e156_capsules_present "$TARGET" || {
        echo "ERROR: copy completed but $TARGET/chartkit.py is missing." >&2; exit 1; }
    log_ok "template copied"
fi

# Refuse BEFORE persisting a path that would advertise an unusable installation.
log_step "Verifying the offline chart-kit renders the sample"
if ! verify_chartkit "$TARGET"; then
    echo "REFUSED: chart-kit render canary failed; E156_CAPSULES_PATH was not persisted." >&2
    exit 1
fi
log_ok "chartkit OK (stdlib-only SVG render verified, no network)"

log_step "Persisting E156_CAPSULES_PATH"
persist_e156_path_env "$TARGET"

echo
echo "====================================================="
echo "  e156-capsules installed at $TARGET"
echo "  E156_CAPSULES_PATH is set (reopen your shell to pick it up)."
echo
echo "  Zero-token starts:"
echo "    cat \"$TARGET/sample.capsule.md\"                 # see a finished capsule"
echo "    \"\$BROWSER\" \"$TARGET/sample.forest.svg\"          # see the chart"
echo "  Author your own (chart step is always token-free):"
echo "    cp \"$TARGET/capsule.template.md\" my.capsule.md"
echo "    python \"$TARGET/chartkit.py\" my.capsule.json --out my.svg"
echo "====================================================="
