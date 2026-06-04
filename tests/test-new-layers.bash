#!/usr/bin/env bash
# test-new-layers.bash -- exercises the helpers of the research-layer
# installers (rapidmeta / aact / aact-kit / pairwise70 / e156-capsules) via --import.
# Network-free and machine-independent (uses temp fixture dirs, not ~/code).
#
# Run: bash tests/test-new-layers.bash

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS="$ROOT/scripts"

PASS=0
FAIL=0
CURRENT=""
start() { CURRENT="$1"; }
ok()    { printf '  [+] %s\n' "$CURRENT"; PASS=$((PASS+1)); }
bad()   { printf '  [-] %s\n    FAIL: %s\n' "$CURRENT" "$1" >&2; FAIL=$((FAIL+1)); }
assert_eq() { [[ "$1" == "$2" ]] || { bad "expected '$2', got '$1'"; return 1; }; }
assert_true()  { [[ "$1" -eq 0 ]] || { bad "expected success, got exit $1"; return 1; }; }
assert_false() { [[ "$1" -ne 0 ]] || { bad "expected failure, got success"; return 1; }; }

# Pinned refs the installers must clone (bump here AND in the script together).
RAPIDMETA_SHA="5a74f31847c6dddba58bc5a9e057c5dcb67b0e3f"
AACT_SHA="f8cf87ab99e72e8c13b254534ab8cfd7960b9c3d"
AACT_KIT_SHA="35a0c42c5123997b828da2cd36c9994accaeefa9"
PAIRWISE70_SHA="fa0cba91ca9e24fee2f5cc96b3b167b1e6ccdb9e"

# --- rapidmeta -------------------------------------------------------------
( source "$SCRIPTS/install-rapidmeta.sh" --import
  set +e +o pipefail   # the sourced installer set -e; neutralize so a false present-check is a result, not an exit
  start "rapidmeta: repo url"; assert_eq "$(rapidmeta_repo_url)" "https://github.com/mahmood726-cyber/rapidmeta-kit.git" && ok
  start "rapidmeta: pinned ref"; assert_eq "$(rapidmeta_default_ref)" "$RAPIDMETA_SHA" && ok
  start "rapidmeta: default target under ~/code"; case "$(rapidmeta_default_target)" in */code/rapidmeta-kit) ok ;; *) bad "unexpected target $(rapidmeta_default_target)" ;; esac
  d="$(mktemp -d)"; : > "$d/clone.py"
  start "rapidmeta: present-check true when clone.py exists"; test_rapidmeta_present "$d"; assert_true $? && ok
  start "rapidmeta: present-check false on empty dir"; test_rapidmeta_present "$(mktemp -d)"; assert_false $? && ok
  rm -rf "$d"
  exit $FAIL ) ; R1=$?

# --- aact ------------------------------------------------------------------
( source "$SCRIPTS/install-aact.sh" --import
  set +e +o pipefail   # the sourced installer set -e; neutralize so a false present-check is a result, not an exit
  start "aact: repo url"; assert_eq "$(aact_repo_url)" "https://github.com/mahmood726-cyber/aact-cockpit.git" && ok
  start "aact: pinned ref"; assert_eq "$(aact_default_ref)" "$AACT_SHA" && ok
  d="$(mktemp -d)"; mkdir -p "$d/scripts"; : > "$d/scripts/make_capsule.py"
  start "aact: present-check finds scripts/make_capsule.py"; test_aact_present "$d"; assert_true $? && ok
  start "aact: present-check false when only root file"; e="$(mktemp -d)"; : > "$e/make_capsule.py"; test_aact_present "$e"; assert_false $? && ok
  rm -rf "$d" "$e"
  exit $FAIL ) ; R2=$?

# --- aact-kit (shared library; distinct from the aact-cockpit layer) -------
( source "$SCRIPTS/install-aact-kit.sh" --import
  set +e +o pipefail   # the sourced installer set -e; neutralize so a false present-check is a result, not an exit
  start "aact-kit: repo url"; assert_eq "$(aactkit_repo_url)" "https://github.com/mahmood726-cyber/aact-kit.git" && ok
  start "aact-kit: pinned ref"; assert_eq "$(aactkit_default_ref)" "$AACT_KIT_SHA" && ok
  start "aact-kit: default target under ~/code"; case "$(aactkit_default_target)" in */code/aact-kit) ok ;; *) bad "unexpected target $(aactkit_default_target)" ;; esac
  d="$(mktemp -d)"; mkdir -p "$d/src/aact_kit"; : > "$d/src/aact_kit/__init__.py"
  start "aact-kit: present-check finds src/aact_kit/__init__.py"; test_aactkit_present "$d"; assert_true $? && ok
  start "aact-kit: present-check false on empty dir"; test_aactkit_present "$(mktemp -d)"; assert_false $? && ok
  rm -rf "$d"
  exit $FAIL ) ; R5=$?

# --- pairwise70 ------------------------------------------------------------
( source "$SCRIPTS/install-pairwise70.sh" --import
  set +e +o pipefail   # the sourced installer set -e; neutralize so a false present-check is a result, not an exit
  start "pairwise70: repo url"; assert_eq "$(pairwise70_repo_url)" "https://github.com/mahmood726-cyber/pairwise70-workbench.git" && ok
  start "pairwise70: pinned ref"; assert_eq "$(pairwise70_default_ref)" "$PAIRWISE70_SHA" && ok
  d="$(mktemp -d)"; : > "$d/index.html"
  start "pairwise70: present-check true when index.html exists"; test_pairwise70_present "$d"; assert_true $? && ok
  rm -rf "$d"
  exit $FAIL ) ; R3=$?

# --- e156-capsules (bundled, no clone) -------------------------------------
( source "$SCRIPTS/install-e156-capsules.sh" --import
  set +e +o pipefail   # the sourced installer set -e; neutralize so a false present-check is a result, not an exit
  start "e156: bundled template dir exists in repo"; [[ -d "$(e156_template_dir)" ]] && ok || bad "missing $(e156_template_dir)"
  start "e156: template carries chartkit.py"; [[ -f "$(e156_template_dir)/chartkit.py" ]] && ok || bad "no chartkit.py"
  start "e156: template carries pre-baked sample"; [[ -f "$(e156_template_dir)/sample.capsule.md" && -f "$(e156_template_dir)/sample.forest.svg" ]] && ok || bad "missing pre-baked sample"
  d="$(mktemp -d)"; : > "$d/chartkit.py"
  start "e156: present-check true when chartkit.py exists"; test_e156_capsules_present "$d"; assert_true $? && ok
  rm -rf "$d"
  exit $FAIL ) ; R4=$?

echo
TOTAL_FAIL=$(( R1 + R2 + R3 + R4 + R5 ))
if [[ "$TOTAL_FAIL" -eq 0 ]]; then
    echo "test-new-layers: all checks passed"
    exit 0
else
    echo "test-new-layers: $TOTAL_FAIL subshell(s) reported failures" >&2
    exit 1
fi
