#!/usr/bin/env bash
# Bash parallel of install/pester.tests.ps1. Exercises helpers dot-sourced
# from install.sh / scripts/*.sh via --import. Network-free.
#
# Run: bash tests/test-install-sh.bash

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
CURRENT=""

start() { CURRENT="$1"; }
ok()    { printf '  [+] %s\n' "$CURRENT"; PASS=$((PASS+1)); }
bad()   { printf '  [-] %s\n    FAIL: %s\n' "$CURRENT" "$1" >&2; FAIL=$((FAIL+1)); }

assert_eq() {
    local a="$1" b="$2"
    [[ "$a" == "$b" ]] || { bad "expected '$b', got '$a'"; return 1; }
}
assert_contains() {
    local hay="$1" needle="$2"
    [[ "$hay" == *"$needle"* ]] || { bad "expected substring '$needle' in output"; return 1; }
}
assert_not_contains() {
    local hay="$1" needle="$2"
    [[ "$hay" != *"$needle"* ]] || { bad "output unexpectedly contained '$needle'"; return 1; }
}
assert_file_exists() {
    [[ -f "$1" ]] || { bad "file does not exist: $1"; return 1; }
}
assert_file_missing() {
    [[ ! -f "$1" ]] || { bad "file unexpectedly exists: $1"; return 1; }
}

# Dot-source the install.sh helpers with --import (short-circuits the real flow)
# shellcheck source=/dev/null
source "$ROOT/install/install.sh" --import

# Describe: render_template
start "render_template substitutes {{NAME}} placeholders"
out="$(printf 'hello {{FOO}} world {{BAR}}' | \
    { tmp_in="$(mktemp)"; tmp_out="$(mktemp)"; \
      printf 'hello {{FOO}} world {{BAR}}' > "$tmp_in"; \
      render_template "$tmp_in" "$tmp_out" "FOO=alice" "BAR=42"; \
      cat "$tmp_out"; rm -f "$tmp_in" "$tmp_out"; })"
assert_eq "$out" "hello alice world 42" && ok

start "render_template leaves unmatched placeholders literal"
tmp_in="$(mktemp)"; tmp_out="$(mktemp)"
printf 'has {{FOO}} no {{BAR}}' > "$tmp_in"
render_template "$tmp_in" "$tmp_out" "FOO=X"
out="$(cat "$tmp_out")"
rm -f "$tmp_in" "$tmp_out"
assert_eq "$out" "has X no {{BAR}}" && ok

start "render_template handles value with forward slashes and backslashes"
tmp_in="$(mktemp)"; tmp_out="$(mktemp)"
printf 'path is {{P}}' > "$tmp_in"
render_template "$tmp_in" "$tmp_out" 'P=/home/alice/dir\sub'
out="$(cat "$tmp_out")"
rm -f "$tmp_in" "$tmp_out"
assert_contains "$out" "/home/alice/dir" && ok

# Describe: copy_rules_to_agent + rollback
SANDBOX="$(mktemp -d -t e156-test.XXXXXX)"
trap 'rm -rf "$SANDBOX"' EXIT

start "copy_rules_to_agent copies 4 rules files into an empty target"
target="$SANDBOX/agent1/rules"
: > "$MANIFEST_FILES"  # reset manifest
: > "$MANIFEST_DIRS"
: > "$MANIFEST_BACKUPS"
copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1
count="$(ls "$target"/*.md 2>/dev/null | wc -l)"
assert_eq "$count" "4" && ok

start "copy_rules_to_agent backs up existing user-edited file as .user"
target="$SANDBOX/agent2/rules"
mkdir -p "$target"
printf 'my-custom' > "$target/lessons.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1
assert_file_exists "$target/lessons.md.user" && \
    [[ "$(cat "$target/lessons.md.user")" == "my-custom" ]] && ok

start "rollback deletes net-new files and restores backups"
target="$SANDBOX/agent3/rules"
mkdir -p "$target"
printf 'pre-existing' > "$target/lessons.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1
# Now manually invoke rollback with the manifest state
rollback "test-triggered rollback" 2>/dev/null || true
# rollback re-creates MANIFEST_DIR because it removes it at the end; reset for safety
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES" ; : > "$MANIFEST_DIRS" ; : > "$MANIFEST_BACKUPS"
assert_file_missing "$target/rules.md" && \
    assert_file_missing "$target/advanced-stats.md" && \
    assert_file_missing "$target/e156.md" && \
    [[ -f "$target/lessons.md" && "$(cat "$target/lessons.md")" == "pre-existing" ]] && \
    [[ ! -f "$target/lessons.md.user" ]] && ok

# Describe: render_template rules in practice
start "templated rules have no residual Mahmood paths"
target="$SANDBOX/rendered/rules"
copy_rules_to_agent "$ROOT/rules" "$target" \
    "E156_HOME=/mine/e156" "PROJECTINDEX_ROOT=/mine/idx" \
    "SENTINEL_ROOT=/mine/sentinel" "OVERMIND_ROOT=/mine/overmind" \
    "GITHUB_USER=alice42" >/dev/null 2>&1
assert_not_contains "$(cat "$target/e156.md")" "C:\\E156" && \
    assert_not_contains "$(cat "$target/e156.md")" "mahmood726-cyber" && \
    assert_contains "$(cat "$target/e156.md")" "/mine/e156" && \
    assert_contains "$(cat "$target/e156.md")" "alice42" && ok

# Describe: sub-installer scripts parse under --import
start "install-sentinel.sh dot-sources cleanly"
bash -c "source '$ROOT/scripts/install-sentinel.sh' --import && declare -F test_sentinel_installed get_sentinel_bypass_log_path > /dev/null" && ok

start "install-overmind.sh dot-sources cleanly"
bash -c "source '$ROOT/scripts/install-overmind.sh' --import && declare -F new_truthcert_hmac_key > /dev/null" && ok

start "new_truthcert_hmac_key produces a 64-hex-char string"
hex="$(bash -c "source '$ROOT/scripts/install-overmind.sh' --import && new_truthcert_hmac_key")"
[[ ${#hex} -eq 64 && "$hex" =~ ^[0-9a-f]{64}$ ]] && ok

# Describe: supply-chain pinning (P0 — fresh installs must be reproducible)
start "sentinel_default_source pins to a tagged release by default"
default_src="$(bash -c "source '$ROOT/scripts/install-sentinel.sh' --import && sentinel_default_source")"
[[ "$default_src" == git+https://github.com/mahmood726-cyber/Sentinel.git@v* ]] && ok

start "sentinel_default_source honours SENTINEL_REF override"
override_src="$(bash -c "export SENTINEL_REF=main; source '$ROOT/scripts/install-sentinel.sh' --import; sentinel_default_source")"
assert_eq "$override_src" "git+https://github.com/mahmood726-cyber/Sentinel.git@main" && ok

start "overmind_default_source pins to a SHA-or-tag by default"
default_src="$(bash -c "source '$ROOT/scripts/install-overmind.sh' --import && overmind_default_source")"
[[ "$default_src" =~ ^git\+https://github\.com/mahmood726-cyber/overmind\.git@[a-zA-Z0-9._-]+$ ]] && ok

start "overmind_default_source honours OVERMIND_REF override"
override_src="$(bash -c "export OVERMIND_REF=main; source '$ROOT/scripts/install-overmind.sh' --import; overmind_default_source")"
assert_eq "$override_src" "git+https://github.com/mahmood726-cyber/overmind.git@main" && ok

start "install-projectindex.sh dot-sources cleanly"
bash -c "source '$ROOT/scripts/install-projectindex.sh' --import && declare -F write_index_markdown_template write_reconcile_script > /dev/null" && ok

# Summary
echo
echo "Tests completed: $((PASS+FAIL))"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
exit 0
