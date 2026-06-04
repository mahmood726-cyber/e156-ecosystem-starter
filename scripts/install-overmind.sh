#!/usr/bin/env bash
# install-overmind.sh -- bash parallel of scripts/install-overmind.ps1.
#
# pip-installs mahmood726-cyber/overmind (which bundles TruthCert engine)
# and generates a 64-hex-char TRUTHCERT_HMAC_KEY written to a gitignored
# file at ~/.config/e156/truthcert-hmac-key. Shell-rc hint emitted so the
# student can source it per session.
#
# Usage:
#   ./scripts/install-overmind.sh
#   ./scripts/install-overmind.sh --skip-pip-install
#   ./scripts/install-overmind.sh --hmac-key <pre-generated>
#   ./scripts/install-overmind.sh --import

set -euo pipefail

SKIP_PIP=0
HMAC_KEY=""
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-pip-install) SKIP_PIP=1; shift ;;
        --hmac-key)         HMAC_KEY="$2"; shift 2 ;;
        --import)           IMPORT=1; shift ;;
        -h|--help)          grep -E '^#' "$0" | head -20; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

test_overmind_installed() {
    command -v overmind >/dev/null 2>&1
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

OVERMIND_DEFAULT_REF="f383dddc0f030cdf54b22882017318bf892aa477"   # 2026-06-04: evidence subsystem + pooling engine + gold-benchmark (measured output-correctness) + hybrid retrieval + reporting-bias. Override with OVERMIND_REF=master.

overmind_default_source() {
    # Pinned to a known-good commit so fresh installs are reproducible. Override
    # with OVERMIND_REF=main (or any branch/tag/SHA) for bleeding edge or
    # rollback if a release breaks something.
    local ref="${OVERMIND_REF:-$OVERMIND_DEFAULT_REF}"
    printf 'git+https://github.com/mahmood726-cyber/overmind.git@%s' "$ref"
}

install_overmind_package() {
    # BANDWIDTH TRIPWIRE (set 2026-04-21): Overmind + Sentinel fresh-install
    # measured at 4.5 MB total. If a future Overmind release adds heavy deps
    # (numpy / scipy / torch / pandas) and the footprint passes ~50 MB, add a
    # --estimate-mb preflight via `pip install --dry-run --report`. See
    # review-findings.md P0-2.
    #
    # RETRY (added 2026-04-27, P1-1): 3 attempts with 2/4/8s backoff for
    # transient git+https failures under student-class burst load.
    local src="${1:-$(overmind_default_source)}"
    assert_real_python || return 1
    echo "  source: $src"
    local attempt
    for attempt in 1 2 3; do
        if "$PYTHON" -m pip install --quiet --disable-pip-version-check "$src" 2>&1 | sed 's/^/  /'; then
            return 0
        fi
        if [[ "$attempt" -lt 3 ]]; then
            local wait=$(( 2 ** attempt ))
            echo "  pip install attempt $attempt failed; retrying in ${wait}s..." >&2
            sleep "$wait"
        fi
    done
    echo "  pip install failed after 3 attempts" >&2
    return 1
}

new_truthcert_hmac_key() {
    # 32 bytes of /dev/urandom hex-encoded -> 64 chars
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    else
        head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
    fi
}

store_truthcert_hmac_key() {
    local key="$1"
    [[ -n "$key" ]] || { echo "ERROR: empty key" >&2; return 1; }
    local cfg_dir="${HOME}/.config/e156"
    mkdir -p "$cfg_dir"
    local key_file="$cfg_dir/truthcert-hmac-key"
    printf '%s\n' "$key" > "$key_file"
    chmod 600 "$key_file"
    printf '%s' "$key_file"
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }
log_warn() { printf '    WARNING: %s\n' "$1" >&2; }

echo
echo "Overmind + TruthCert installer"
echo

log_step "Checking for overmind CLI"
if test_overmind_installed; then
    log_ok "overmind already installed"
else
    if [[ "$SKIP_PIP" -eq 1 ]]; then
        echo "ERROR: overmind not on PATH and --skip-pip-install passed." >&2
        echo "  Install: pip install $(overmind_default_source)" >&2
        exit 1
    fi
    log_step "Installing overmind (first-time setup)"
    install_overmind_package
    test_overmind_installed || {
        echo "ERROR: pip install completed but overmind is still not on PATH." >&2
        exit 1
    }
    log_ok "overmind installed"
fi

log_step "Setting TRUTHCERT_HMAC_KEY"
key_file="${HOME}/.config/e156/truthcert-hmac-key"
if [[ -f "$key_file" && -z "$HMAC_KEY" ]]; then
    existing="$(cat "$key_file")"
    log_ok "existing key at $key_file (length: ${#existing})"
    echo "    Use --hmac-key <new> to rotate."
    export TRUTHCERT_HMAC_KEY="$existing"
else
    if [[ -n "$HMAC_KEY" ]]; then
        key="$HMAC_KEY"
        stored_at="$(store_truthcert_hmac_key "$key")"
        log_ok "user-provided key saved to $stored_at"
    else
        key="$(new_truthcert_hmac_key)"
        stored_at="$(store_truthcert_hmac_key "$key")"
        log_ok "generated new 64-hex-char key, saved to $stored_at"
    fi
    export TRUTHCERT_HMAC_KEY="$key"
    echo "    Back it up somewhere safe -- losing it invalidates all prior signed bundles."
    echo
    echo "    Add this to your shell rc so future sessions see the key:"
    echo "      export TRUTHCERT_HMAC_KEY=\"\$(cat $key_file)\""
fi

log_step "overmind meta-verify (canary)"
overmind meta-verify 2>&1 | head -5 | sed 's/^/  /' || \
    log_warn "overmind meta-verify returned non-zero (review above)"

echo
echo "====================================================="
echo "  Overmind + TruthCert ready. Typical use:"
echo "    overmind scan --repo ~/Projects/my-paper"
echo "    overmind run-once --repo ~/Projects/my-paper"
echo "====================================================="
