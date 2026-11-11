#!/usr/bin/env bash
# Verify locked AACT-kit source before persistence; runtime verification is opt-in.
# Usage: install-aact-kit.sh [--target DIR] [--skip-clone] [--session-only]
# --verify-runtime checks existing dependencies; --with-deps installs in an active venv first.
# --skip-clone still verifies exact identity, cleanliness and package source.
# --session-only avoids writes to shell startup files. --import loads helpers.
set -euo pipefail

TARGET=""
SKIP_CLONE=0
SESSION_ONLY=0
WITH_DEPS=0
VERIFY_RUNTIME=0
IMPORT=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) [[ $# -ge 2 ]] || { echo "--target needs a path" >&2; exit 2; }; TARGET="$2"; shift 2 ;;
        --skip-clone) SKIP_CLONE=1; shift ;;
        --with-deps) WITH_DEPS=1; shift ;;
        --verify-runtime) VERIFY_RUNTIME=1; shift ;;
        --session-only) SESSION_ONLY=1; shift ;;
        --import) IMPORT=1; shift ;;
        -h|--help) head -5 "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done
AACT_KIT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=""
for candidate in python python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        case "$(command -v "$candidate")" in *WindowsApps*) continue ;; esac
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
            PYTHON="$candidate"; break
        fi
    fi
done
aactkit_require_python() {
    [[ -n "$PYTHON" ]] || { echo "REFUSED: Python 3.11+ is required" >&2; return 2; }
}
aactkit_repo_url() {
    aactkit_require_python || return
    "$PYTHON" "$AACT_KIT_SCRIPT_DIR/component_lock.py" --component aact-kit --field repository
}
aactkit_default_ref() {
    aactkit_require_python || return
    local ref
    if [[ "${AACT_KIT_REF+x}" == x ]]; then
        ref="$AACT_KIT_REF"
    else
        ref="$("$PYTHON" "$AACT_KIT_SCRIPT_DIR/component_lock.py" --component aact-kit --field commit)" || return
    fi
    [[ "$ref" =~ ^[0-9a-f]{40}$ ]] || { echo "REFUSED: AACT-kit requires a full lowercase commit SHA" >&2; return 2; }
    printf '%s\n' "$ref"
}
aactkit_default_target() { printf '%s/code/aact-kit\n' "$HOME"; }
test_aactkit_present() { [[ -n "$1" && -f "$1/src/aact_kit/__init__.py" ]]; }

persist_aactkit_path_env() {
    local target="$1" line rc binding
    printf -v line 'export AACT_KIT_PATH=%q' "$target"
    # Preflight both files before writing either. Preserve conflicting settings.
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [[ -e "$rc" ]]; then
            [[ -f "$rc" ]] || { echo "REFUSED: startup path is not a file" >&2; return 2; }
            while IFS= read -r binding || [[ -n "$binding" ]]; do
                if [[ "$binding" == *AACT_KIT_PATH=* && "$binding" != "$line" ]]; then
                    echo "REFUSED: conflicting AACT_KIT_PATH in $rc; update it explicitly or use --session-only" >&2
                    return 2
                fi
            done < "$rc"
        fi
    done
    if [[ ! -e "$HOME/.bashrc" && ! -e "$HOME/.zshrc" ]]; then
        printf '# AACT-kit verified source\n%s\n' "$line" > "$HOME/.bashrc"
    else
        for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
            [[ -e "$rc" ]] || continue
            if ! grep -qxF "$line" "$rc"; then
                printf '\n# AACT-kit verified source\n%s\n' "$line" >> "$rc"
            fi
        done
    fi
    export AACT_KIT_PATH="$target"
}

if [[ "$IMPORT" -eq 1 ]]; then return 0 2>/dev/null || exit 0; fi
aactkit_require_python
[[ -n "$TARGET" ]] || TARGET="$(aactkit_default_target)"
REF="$(aactkit_default_ref)"
args=(--target "$TARGET" --ref "$REF")
[[ "$SKIP_CLONE" -eq 0 ]] || args+=(--skip-clone)
[[ "$WITH_DEPS" -eq 0 ]] || args+=(--with-deps)
[[ "$VERIFY_RUNTIME" -eq 0 ]] || args+=(--verify-runtime)
receipt="$("$PYTHON" "$AACT_KIT_SCRIPT_DIR/aact_install.py" "${args[@]}")" || exit 2
# Persist the absolute spelling so a later shell cannot resolve a relative path elsewhere.
TARGET="$(cd "$TARGET" && pwd -P)"
if [[ "$SESSION_ONLY" -eq 0 ]]; then
    persist_aactkit_path_env "$TARGET"
else
    export AACT_KIT_PATH="$TARGET"
fi
printf '%s\n' "$receipt"
if [[ "$WITH_DEPS" -eq 1 || "$VERIFY_RUNTIME" -eq 1 ]]; then
    printf 'AACT-kit source and four local backends verified on synthetic fixtures.\n'
else
    printf 'AACT-kit source verified only; runtime has not been checked.\n'
fi
