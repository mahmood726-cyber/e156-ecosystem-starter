#!/usr/bin/env bash
# install-long-term-plan.sh -- bash parallel of install-long-term-plan.ps1.
#
# Clones mahmood726-cyber/long-term-plan to a local dir and installs the only
# runtime dep (pyyaml). See the .ps1 file header for the design rationale.
#
# Usage:
#   ./scripts/install-long-term-plan.sh
#   ./scripts/install-long-term-plan.sh --root ~/code/long-term-plan
#   ./scripts/install-long-term-plan.sh --ref v0.7.0 --force
#   ./scripts/install-long-term-plan.sh --import     # dot-source for tests

set -euo pipefail

ROOT=""
REF=""
FORCE=0
IMPORT=0

LONG_TERM_PLAN_DEFAULT_REF='v0.7.0'
LONG_TERM_PLAN_REPO_URL='https://github.com/mahmood726-cyber/long-term-plan.git'

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)    ROOT="$2"; shift 2 ;;
        --ref)     REF="$2"; shift 2 ;;
        --force)   FORCE=1; shift ;;
        --import)  IMPORT=1; shift ;;
        -h|--help) grep -E '^#' "$0" | head -15; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

get_default_long_term_plan_root() {
    printf '%s' "${HOME}/code/long-term-plan"
}

get_default_long_term_plan_ref() {
    # Pinned to a tagged release; override with LONG_TERM_PLAN_REF env var.
    if [[ -n "${LONG_TERM_PLAN_REF:-}" ]]; then
        printf '%s' "$LONG_TERM_PLAN_REF"
    else
        printf '%s' "$LONG_TERM_PLAN_DEFAULT_REF"
    fi
}

assert_python() {
    if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
        cat >&2 <<EOF
ERROR: python is not on PATH.

Install Python 3.11+ from https://www.python.org/downloads/ (or your distro's
package manager), then re-run this script.
EOF
        return 1
    fi
}

assert_git() {
    if ! command -v git >/dev/null 2>&1; then
        cat >&2 <<EOF
ERROR: git is not on PATH.

Install git from https://git-scm.com/downloads (or your distro's package
manager), then re-run this script.
EOF
        return 1
    fi
}

pick_python() {
    if command -v python >/dev/null 2>&1; then printf 'python';
    else printf 'python3'; fi
}

install_pyyaml_if_missing() {
    local py
    py="$(pick_python)"
    "$py" -m pip install --quiet --disable-pip-version-check pyyaml \
        2>&1 | sed 's/^/  /'
    # shellcheck disable=SC2181
    if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
        echo "ERROR: pip install pyyaml failed." >&2
        return 1
    fi
}

is_long_term_plan_repo() {
    # Mirrors Test-IsLongTermPlanRepo in the .ps1.
    local path="$1"
    [[ -f "$path/scripts/weekly_plan_update.py" ]] || return 1
    [[ -f "$path/ideas.yaml" ]] || return 1
    [[ -d "$path/.git" ]] || return 1
    return 0
}

install_long_term_plan_clone() {
    local path="$1"
    local ref="$2"
    if is_long_term_plan_repo "$path"; then
        printf '  long-term-plan clone already present at %s; updating\n' "$path"
        (
            cd "$path"
            git fetch --tags --depth 1 origin "$ref" 2>&1 | sed 's/^/  /'
            # shellcheck disable=SC2181
            [[ ${PIPESTATUS[0]} -eq 0 ]] || { echo "ERROR: git fetch failed" >&2; exit 1; }
            git checkout --quiet "$ref" 2>&1 | sed 's/^/  /'
            # shellcheck disable=SC2181
            [[ ${PIPESTATUS[0]} -eq 0 ]] || { echo "ERROR: git checkout $ref failed" >&2; exit 1; }
        )
    else
        if [[ -d "$path" ]]; then
            local children
            children="$(ls -A "$path" 2>/dev/null | head -1)"
            if [[ -n "$children" ]]; then
                cat >&2 <<EOF
ERROR: target directory $path already exists and is non-empty but is not a
long-term-plan clone. Refusing to clone over it.

Pick a different --root, or empty / remove $path first.
EOF
                return 1
            fi
        fi
        git clone --quiet --branch "$ref" --depth 1 \
            "$LONG_TERM_PLAN_REPO_URL" "$path" 2>&1 | sed 's/^/  /'
        # shellcheck disable=SC2181
        if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
            echo "ERROR: git clone failed. Check network + ref name." >&2
            return 1
        fi
    fi
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$ROOT" ]] || ROOT="$(get_default_long_term_plan_root)"
[[ -n "$REF" ]]  || REF="$(get_default_long_term_plan_ref)"

echo
echo "long-term-plan installer"
echo "Target: $ROOT"
echo "Ref:    $REF"
echo

log_step "Checking prerequisites (python + git)"
assert_python || exit 1
assert_git || exit 1
log_ok "python + git on PATH"

log_step "Installing pyyaml (long-term-plan's only runtime dep)"
install_pyyaml_if_missing || exit 1
log_ok "pyyaml ready"

log_step "Cloning / updating long-term-plan at $ROOT"
parent="$(dirname "$ROOT")"
[[ -d "$parent" ]] || mkdir -p "$parent"
install_long_term_plan_clone "$ROOT" "$REF" || exit 1
log_ok "cloned at ref $REF"

echo
echo "====================================================="
echo "  long-term-plan installed at $ROOT"
echo
echo "  The published clone ships Mahmood's real backlog as a"
echo "  REFERENCE. Build your own:"
echo "    1. Edit $ROOT/ideas.yaml -- delete the seeded ideas,"
echo "       add your own."
echo "    2. Edit $ROOT/objectives.yaml -- replace the Q3-2026"
echo "       milestones with yours."
echo "    3. Edit $ROOT/north_star_tags.yaml -- replace with your"
echo "       own north stars."
echo
echo "  Then weekly:"
echo "    cd $ROOT"
echo "    python scripts/weekly_plan_update.py"
echo
echo "  Flip an idea to in-progress:"
echo "    python scripts/weekly_plan_update.py --pick <idea-id>"
echo
echo "  Add an idea inline:"
echo "    python scripts/weekly_plan_update.py --add \"my new idea\""
echo "====================================================="
