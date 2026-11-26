#!/usr/bin/env bash
# Bash tests for the locale picker in scripts/write-gemini-handoff.sh.
# P1-D from the 2026-04-27 second-pass review.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="$REPO_ROOT/scripts/write-gemini-handoff.sh"
PASS=0
FAIL=0

# Source the helpers using the --import hook (no side effects).
# shellcheck source=/dev/null
. "$SCRIPT_PATH" --import

ok() { printf '  [+] %s\n' "$1"; PASS=$((PASS+1)); }
ko() { printf '  [X] %s\n    expected: %s\n    actual:   %s\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); }

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        ok "$label"
    else
        ko "$label" "$expected" "$actual"
    fi
}

# Each test clears the locale env vars first, then sets only what it cares about.
clear_locale() { unset E156_LANG LC_ALL LANG 2>/dev/null || true; }

echo "Locale resolver precedence:"

clear_locale
assert_eq "default to en when nothing set" "en" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=fr_FR.UTF-8
assert_eq "LANG=fr_FR.UTF-8 -> fr" "fr" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=pt_BR.UTF-8
assert_eq "LANG=pt_BR.UTF-8 -> pt" "pt" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=ar_EG.UTF-8
assert_eq "LANG=ar_EG.UTF-8 -> ar" "ar" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=ur_PK.UTF-8
assert_eq "LANG=ur_PK.UTF-8 -> ur" "ur" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=fr_FR.UTF-8 LC_ALL=pt_BR.UTF-8
assert_eq "LC_ALL beats LANG (POSIX canonical precedence)" "pt" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=fr_FR.UTF-8 LC_ALL=pt_BR.UTF-8 E156_LANG=ar
assert_eq "E156_LANG beats LC_ALL and LANG" "ar" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=de_DE.UTF-8
assert_eq "unsupported locale (de) -> en" "en" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=sw_KE.UTF-8
assert_eq "LANG=sw_KE.UTF-8 -> sw" "sw" "$(e156_resolve_handoff_locale)"

clear_locale; export LANG=FR_FR.UTF-8
assert_eq "case-insensitive (FR_FR.UTF-8 -> fr)" "fr" "$(e156_resolve_handoff_locale)"

echo
echo "Path resolver:"

clear_locale; export LANG=fr_FR.UTF-8
expected_fr="$REPO_ROOT/scripts/gemini-handoff-prompt.fr.md"
actual_fr="$(e156_resolve_handoff_prompt_path "$REPO_ROOT")"
assert_eq "fr -> .fr.md path" "$expected_fr" "$actual_fr"
[[ -f "$actual_fr" ]] && ok "  resolved file exists" || ko "  resolved file exists" "file" "missing"

clear_locale; export LANG=pt_BR.UTF-8
expected_pt="$REPO_ROOT/scripts/gemini-handoff-prompt.pt.md"
assert_eq "pt -> .pt.md path" "$expected_pt" "$(e156_resolve_handoff_prompt_path "$REPO_ROOT")"

clear_locale; export LANG=ar_EG.UTF-8
expected_ar="$REPO_ROOT/scripts/gemini-handoff-prompt.ar.md"
assert_eq "ar -> .ar.md path" "$expected_ar" "$(e156_resolve_handoff_prompt_path "$REPO_ROOT")"

clear_locale; export LANG=ur_PK.UTF-8
expected_ur="$REPO_ROOT/scripts/gemini-handoff-prompt.ur.md"
actual_ur="$(e156_resolve_handoff_prompt_path "$REPO_ROOT")"
assert_eq "ur -> .ur.md path" "$expected_ur" "$actual_ur"
[[ -f "$actual_ur" ]] && ok "  resolved Urdu file exists" || ko "  resolved Urdu file exists" "file" "missing"

clear_locale; export LANG=sw_KE.UTF-8
expected_sw="$REPO_ROOT/scripts/gemini-handoff-prompt.sw.md"
actual_sw="$(e156_resolve_handoff_prompt_path "$REPO_ROOT")"
assert_eq "sw -> .sw.md path" "$expected_sw" "$actual_sw"
[[ -f "$actual_sw" ]] && ok "  resolved Swahili file exists" || ko "  resolved Swahili file exists" "file" "missing"

# Force a locale whose file doesn't exist; expect English fallback.
clear_locale
expected_en="$REPO_ROOT/scripts/gemini-handoff-prompt.en.md"
actual_de="$(e156_resolve_handoff_prompt_path "$REPO_ROOT" "de")"
assert_eq "missing locale (de) falls back to .en.md" "$expected_en" "$actual_de"

echo
echo "End-to-end --resolve-only entry point:"
clear_locale; export LANG=fr_FR.UTF-8
e2e_actual="$(bash "$SCRIPT_PATH" --resolve-only)"
assert_eq "--resolve-only matches helper output" "$expected_fr" "$e2e_actual"

clear_locale
echo
echo "Tests completed: $((PASS+FAIL))"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
[[ "$FAIL" -eq 0 ]]
