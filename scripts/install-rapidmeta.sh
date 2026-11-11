#!/usr/bin/env bash
# Install the locked RapidMeta source and verify the generator before persistence.
# Usage: install-rapidmeta.sh [--target DIR] [--skip-clone] [--session-only]
# --skip-clone still verifies exact identity, cleanliness and generator output.
# --session-only avoids writes to shell startup files. --import loads helpers.
set -euo pipefail

TARGET=""
SKIP_CLONE=0
SESSION_ONLY=0
IMPORT=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) [[ $# -ge 2 ]] || { echo "--target needs a path" >&2; exit 2; }; TARGET="$2"; shift 2 ;;
        --skip-clone) SKIP_CLONE=1; shift ;;
        --session-only) SESSION_ONLY=1; shift ;;
        --import) IMPORT=1; shift ;;
        -h|--help) head -5 "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done
RAPIDMETA_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        case "$(command -v "$candidate")" in *WindowsApps*) continue ;; esac
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
            PYTHON="$candidate"; break
        fi
    fi
done
rapidmeta_require_python() {
    [[ -n "$PYTHON" ]] || { echo "REFUSED: Python 3.11+ is required" >&2; return 2; }
}
rapidmeta_repo_url() {
    rapidmeta_require_python || return
    "$PYTHON" "$RAPIDMETA_SCRIPT_DIR/component_lock.py" --component rapidmeta --field repository
}
rapidmeta_default_ref() {
    rapidmeta_require_python || return
    local ref
    if [[ "${RAPIDMETA_REF+x}" == x ]]; then
        ref="$RAPIDMETA_REF"
    else
        ref="$("$PYTHON" "$RAPIDMETA_SCRIPT_DIR/component_lock.py" --component rapidmeta --field commit)" || return
    fi
    [[ "$ref" =~ ^[0-9a-f]{40}$ ]] || { echo "REFUSED: RapidMeta requires a full lowercase commit SHA" >&2; return 2; }
    printf '%s\n' "$ref"
}
rapidmeta_default_target() { printf '%s/code/rapidmeta-kit\n' "$HOME"; }
test_rapidmeta_present() { [[ -n "$1" && -f "$1/clone.py" ]]; }

persist_rapidmeta_path_env() {
    local target="$1" line rc binding
    printf -v line 'export RAPIDMETA_KIT_PATH=%q' "$target"
    # Preflight both files before writing either. Preserve conflicting settings.
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [[ -e "$rc" ]]; then
            [[ -f "$rc" ]] || { echo "REFUSED: startup path is not a file" >&2; return 2; }
            while IFS= read -r binding || [[ -n "$binding" ]]; do
                if [[ "$binding" == *RAPIDMETA_KIT_PATH=* && "$binding" != "$line" ]]; then
                    echo "REFUSED: conflicting RAPIDMETA_KIT_PATH in $rc; update it explicitly or use --session-only" >&2
                    return 2
                fi
            done < "$rc"
        fi
    done
    if [[ ! -e "$HOME/.bashrc" && ! -e "$HOME/.zshrc" ]]; then
        printf '# RapidMeta verified source\n%s\n' "$line" > "$HOME/.bashrc"
    else
        for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
            [[ -e "$rc" ]] || continue
            if ! grep -qxF "$line" "$rc"; then
                printf '\n# RapidMeta verified source\n%s\n' "$line" >> "$rc"
            fi
        done
    fi
    export RAPIDMETA_KIT_PATH="$target"
}

if [[ "$IMPORT" -eq 1 ]]; then return 0 2>/dev/null || exit 0; fi
rapidmeta_require_python
[[ -n "$TARGET" ]] || TARGET="$(rapidmeta_default_target)"
REF="$(rapidmeta_default_ref)"
args=(--target "$TARGET" --ref "$REF")
[[ "$SKIP_CLONE" -eq 0 ]] || args+=(--skip-clone)
receipt="$("$PYTHON" "$RAPIDMETA_SCRIPT_DIR/rapidmeta_install.py" "${args[@]}")" || exit 2
# Persist the absolute spelling so a later shell cannot resolve a relative path elsewhere.
TARGET="$(cd "$TARGET" && pwd -P)"
if [[ "$SESSION_ONLY" -eq 0 ]]; then
    persist_rapidmeta_path_env "$TARGET"
else
    export RAPIDMETA_KIT_PATH="$TARGET"
fi
printf '%s\n' "$receipt"
printf 'RapidMeta source and generator verified. Browser and scientific validation are separate.\n'
