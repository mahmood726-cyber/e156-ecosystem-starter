#!/usr/bin/env bash
# install-extractor.sh -- bash parallel of scripts/install-extractor.ps1.
#
# Installs the rct-extractor-v2 RCT data extractor (17 disease specialties: HIV,
# malaria, typhoid, schistosomiasis, sickle cell, cholera, maternal/neonatal, TB,
# hepatitis, meningitis, pneumonia, diarrhoeal, malnutrition, helminths,
# hypertension, cervical cancer, diabetes) that feeds the meta-starter-kit config
# the rest of the ecosystem consumes. Clones the repo at a pinned commit into a
# target dir and exports RCT_EXTRACTOR_PATH so the meta-system bridges
# (extractor_bridge/extract_meta.py) auto-find it. The clone also ships the
# `rct-extract` CLI and the `rct_extractor` Python package.
#
# The student's core path -- trial text in, meta-starter-kit config out -- is
# STDLIB-ONLY (no numpy / scipy / pdfplumber). Heavy PDF + scientific deps are
# OPT-IN via --with-pdf-deps, because most students paste abstract/results text
# rather than parse PDFs locally, and bandwidth is precious.
#
# Usage:
#   ./scripts/install-extractor.sh                  # clone to ~/code/rct-extractor-v2 (core only)
#   ./scripts/install-extractor.sh --target <dir>
#   ./scripts/install-extractor.sh --with-pdf-deps  # also pip-install the PDF/scientific stack
#   ./scripts/install-extractor.sh --skip-clone     # only set env + verify an existing clone
#   ./scripts/install-extractor.sh --import         # dot-source for tests

set -euo pipefail

TARGET=""
WITH_PDF_DEPS=0
SKIP_CLONE=0
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)         TARGET="$2"; shift 2 ;;
        --with-pdf-deps)  WITH_PDF_DEPS=1; shift ;;
        --skip-clone)     SKIP_CLONE=1; shift ;;
        --import)         IMPORT=1; shift ;;
        -h|--help)        grep -E '^#' "$0" | head -22; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# Resolve python3 / python (modern Linux defaults to python3 only).
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

# Default clone location: under the student's ~/code/ workspace, matching where
# install.sh lands Sentinel / ProjectIndex (NOT $HOME root).
extractor_default_target() {
    echo "${HOME}/code/rct-extractor-v2"
}

extractor_repo_url() {
    echo "https://github.com/mahmood726-cyber/rct-extractor-v2.git"
}

# Known-good extractor commit (all 17 disease specialties; packaged as the
# pip-installable `rct_extractor` lib + `rct-extract` CLI; 1343 tests green).
# Pinned to the v1.0.0 release tag (the reviewed/fixed build) so a fresh clone is
# reproducible -- same supply-chain approach as the Sentinel / Overmind
# installers. Override with RCT_EXTRACTOR_REF=main (or any branch/tag/SHA) for
# bleeding edge.
EXTRACTOR_DEFAULT_REF="v1.0.0"

extractor_default_ref() {
    echo "${RCT_EXTRACTOR_REF:-$EXTRACTOR_DEFAULT_REF}"
}

# A target is a usable extractor checkout if it carries the bridge entrypoint
# the meta-systems shell out to.
test_extractor_present() {
    [[ -n "$1" && -f "$1/scripts/build_metakit_config.py" ]]
}

clone_or_update_extractor() {
    local target="$1" ref="$2"
    local url; url="$(extractor_repo_url)"
    if [[ -d "$target/.git" ]]; then
        echo "  existing checkout: $target (fetch + checkout $ref)"
        git -C "$target" fetch --quiet origin "$ref" 2>/dev/null || git -C "$target" fetch --quiet origin
        git -C "$target" checkout --quiet "$ref" 2>&1 | sed 's/^/  /' || true
    else
        echo "  cloning $url"
        # Shallow-ish: full clone is needed to checkout an arbitrary SHA, so a
        # plain clone then checkout is the most portable across git versions.
        local attempt
        for attempt in 1 2 3; do
            if git clone --quiet "$url" "$target" 2>&1 | sed 's/^/  /'; then
                break
            fi
            if [[ "$attempt" -lt 3 ]]; then
                local wait=$(( 2 ** attempt ))
                echo "  clone attempt $attempt failed; retrying in ${wait}s..." >&2
                sleep "$wait"
            else
                echo "  clone failed after 3 attempts" >&2
                return 1
            fi
        done
        git -C "$target" checkout --quiet "$ref" 2>&1 | sed 's/^/  /' || true
    fi
}

# Persist RCT_EXTRACTOR_PATH so the meta-system bridges find the extractor in
# future shells. Append to ~/.bashrc (idempotent) and export for the current
# process. macOS default zsh users also get ~/.zshrc.
persist_extractor_path_env() {
    local target="$1"
    export RCT_EXTRACTOR_PATH="$target"
    local line="export RCT_EXTRACTOR_PATH=\"$target\""
    local rc
    for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -qF "RCT_EXTRACTOR_PATH=" "$rc" 2>/dev/null; then
            printf '\n# rct-extractor-v2 (e156-ecosystem-starter)\n%s\n' "$line" >> "$rc"
            echo "  added RCT_EXTRACTOR_PATH to $rc"
        else
            echo "  RCT_EXTRACTOR_PATH already set in $rc (left as-is)"
        fi
    done
    # If neither rc existed, create ~/.bashrc so the var survives.
    if [[ ! -e "${HOME}/.bashrc" && ! -e "${HOME}/.zshrc" ]]; then
        printf '# rct-extractor-v2 (e156-ecosystem-starter)\n%s\n' "$line" > "${HOME}/.bashrc"
        echo "  created ~/.bashrc with RCT_EXTRACTOR_PATH"
    fi
}

# Verify the stdlib-only student path actually imports (text -> config).
verify_core_import() {
    local target="$1"
    assert_real_python || return 1
    "$PYTHON" - "$target" <<'PY_EOF'
import sys
sys.path.insert(0, sys.argv[1])
import scripts.build_metakit_config  # noqa: F401  (the bridge entrypoint)
from src.specialties.registry import detect_specialty
assert detect_specialty("viral suppression with dolutegravir")[0] == "hiv"
# prove this is the 17-specialty build, not the old cardio+malaria+HIV one
assert detect_specialty("empagliflozin in type 2 diabetes lowered HbA1c")[0] == "diabetes"
print("ok")
PY_EOF
}

install_pdf_deps() {
    # Heavy: numpy / scipy / pdfplumber / pymupdf for real-PDF parsing and the
    # scipy-verified validation scripts. ~150 MB. Opt-in only.
    local target="$1"
    assert_real_python || return 1
    local req="$target/requirements.txt"
    [[ -f "$req" ]] || { echo "  no requirements.txt at $req" >&2; return 1; }
    echo "  pip install -r $req  (PDF + scientific stack, ~150 MB)"
    local attempt
    for attempt in 1 2 3; do
        if "$PYTHON" -m pip install --quiet --disable-pip-version-check -r "$req" 2>&1 | sed 's/^/  /'; then
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

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

# === Real flow =============================================================

log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }

[[ -n "$TARGET" ]] || TARGET="$(extractor_default_target)"
REF="$(extractor_default_ref)"

echo
echo "rct-extractor-v2 installer (17 disease specialties)"
echo

if [[ "$SKIP_CLONE" -eq 1 ]]; then
    log_step "Skipping clone (--skip-clone); using existing checkout at $TARGET"
    test_extractor_present "$TARGET" || {
        echo "ERROR: --skip-clone but no extractor at $TARGET (missing scripts/build_metakit_config.py)." >&2
        exit 1
    }
else
    log_step "Installing extractor into $TARGET (ref: ${REF:0:12})"
    mkdir -p "$(dirname "$TARGET")"
    clone_or_update_extractor "$TARGET" "$REF"
    test_extractor_present "$TARGET" || {
        echo "ERROR: clone completed but $TARGET/scripts/build_metakit_config.py is missing." >&2
        exit 1
    }
    log_ok "checkout ready"
fi

log_step "Persisting RCT_EXTRACTOR_PATH"
persist_extractor_path_env "$TARGET"

log_step "Verifying the core (text -> config) path imports"
if verify_core_import "$TARGET" >/dev/null 2>&1; then
    log_ok "core import OK (stdlib-only path verified)"
else
    echo "    WARNING: core import check did not return ok (Python missing? see above)." >&2
fi

if [[ "$WITH_PDF_DEPS" -eq 1 ]]; then
    log_step "Installing PDF + scientific deps (--with-pdf-deps)"
    install_pdf_deps "$TARGET" && log_ok "PDF deps installed" || \
        echo "    WARNING: PDF deps failed; the core text->config path still works." >&2
fi

echo
echo "====================================================="
echo "  rct-extractor-v2 installed at $TARGET"
echo "  RCT_EXTRACTOR_PATH is set (reopen your shell to pick it up)."
echo
echo "  Use it from a meta-system repo (bridge auto-finds it):"
echo "    python extractor_bridge/extract_meta.py records.json --out config.json"
echo "  Or directly:"
echo "    python \"$TARGET/scripts/build_metakit_config.py\" records.json --out config.json"
echo
echo "  Or the new unified CLI (after  pip install \"$TARGET\"):"
echo "    rct-extract --list-specialties"
echo "    rct-extract --specialty diabetes --input abstract.txt"
echo "    rct-extract --auto --input ./corpus --json -o results.jsonl"
echo
echo "  17 specialties auto-detected: hiv, malaria, typhoid, schistosomiasis,"
echo "    sickle_cell, cholera, maternal_neonatal, tuberculosis, hepatitis,"
echo "    meningitis, pneumonia, diarrhoeal, malnutrition, helminths,"
echo "    hypertension, cervical_cancer, diabetes."
[[ "$WITH_PDF_DEPS" -eq 1 ]] || \
echo "  For local PDF parsing later:  ./scripts/install-extractor.sh --with-pdf-deps"
echo "====================================================="
