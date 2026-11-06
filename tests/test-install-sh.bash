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

# --dry-run promises a read-only self-SHA check. Even an empty transcript
# directory is an unintended write to the caller's home/state tree.
start "dry-run verifies SHA without creating a log or user state"
dryrun_home="$SANDBOX/dry-run home-Ü"
dryrun_state="$dryrun_home/state with spaces-Ü"
mkdir -p "$dryrun_home"
dryrun_status=0
dryrun_output="$(HOME="$dryrun_home" XDG_STATE_HOME="$dryrun_state" bash "$ROOT/install/install.sh" --dry-run 2>&1)" || dryrun_status=$?
if [[ "$dryrun_status" -eq 0 && "$dryrun_output" == *"Dry run: self-SHA verified."* &&
      ! -e "$dryrun_state" && ! -e "$dryrun_home/.local" ]]; then
    ok
else
    bad "dry-run wrote user state or did not verify the pinned installer SHA"
fi

start "dry-run rejects wrong SHA without creating user state"
dryrun_fixture="$SANDBOX/bad SHA fixture-Ü"
mkdir -p "$dryrun_fixture/install" "$dryrun_fixture/docs"
cp "$ROOT/install/install.sh" "$dryrun_fixture/install/install.sh"
printf '%064d\\n' 0 > "$dryrun_fixture/docs/HASH-linux.txt"
dryrun_bad_home="$SANDBOX/bad SHA home-Ü"
dryrun_bad_state="$dryrun_bad_home/state-Ü"
mkdir -p "$dryrun_bad_home"
dryrun_status=0
dryrun_output="$(HOME="$dryrun_bad_home" XDG_STATE_HOME="$dryrun_bad_state" bash "$dryrun_fixture/install/install.sh" --dry-run 2>&1)" || dryrun_status=$?
if [[ "$dryrun_status" -ne 0 && "$dryrun_output" == *"SHA does not match"* &&
      ! -e "$dryrun_bad_state" && ! -e "$dryrun_bad_home/.local" ]]; then
    ok
else
    bad "mismatched SHA dry-run wrote user state or did not fail closed"
fi


# A concurrent installer must not touch any of the same agent configuration.
# Use only synthetic HOME paths, never the actual user's configuration.
start "refuses a competing installation before changing agent files"
concurrent_home="$SANDBOX/concurrent install home-Ü"
concurrent_lock="$concurrent_home/.e156-ecosystem-starter-install.lock"
concurrent_tmp="$SANDBOX/concurrent temp-Ü"
mkdir -p "$concurrent_lock" "$concurrent_tmp"
printf 'untouched\n' > "$concurrent_lock/existing-marker"
concurrent_rc=0
concurrent_output="$(HOME="$concurrent_home" XDG_STATE_HOME="$SANDBOX/concurrent state" TMPDIR="$concurrent_tmp" bash "$ROOT/install/install.sh" --non-interactive 2>&1)" || concurrent_rc=$?
if [[ "$concurrent_rc" -ne 0 && "$concurrent_output" == *"another installation"* &&
      "$(cat "$concurrent_lock/existing-marker")" == "untouched" &&
      ! -e "$concurrent_home/.claude" && ! -e "$concurrent_home/.gemini" &&
      ! -e "$concurrent_home/.codex" ]] && ! compgen -G "$concurrent_tmp/e156-rollback.*" >/dev/null; then
    ok
else
    bad "concurrent install bypassed occupied lock, modified config, or altered existing lock"
fi

start "successful isolated install releases its lock"
single_home="$SANDBOX/single install home-Ü"
mkdir -p "$single_home"
single_rc=0
HOME="$single_home" XDG_STATE_HOME="$SANDBOX/single state" bash "$ROOT/install/install.sh" --non-interactive >/dev/null 2>&1 || single_rc=$?
if [[ "$single_rc" -eq 0 && ! -e "$single_home/.e156-ecosystem-starter-install.lock" &&
      -f "$single_home/.claude/rules/rules.md" ]]; then
    ok
else
    bad "isolated installation failed, retained lock, or omitted rules"
fi

start "failed isolated install releases its lock without following symlink"
failed_home="$SANDBOX/failed install home-Ü"
outside_dir="$SANDBOX/outside for failed install"
mkdir -p "$failed_home/.gemini" "$outside_dir"
ln -s "$outside_dir" "$failed_home/.gemini/rules"
failed_rc=0
HOME="$failed_home" XDG_STATE_HOME="$SANDBOX/failed state" bash "$ROOT/install/install.sh" --non-interactive >/dev/null 2>&1 || failed_rc=$?
if [[ "$failed_rc" -ne 0 && ! -e "$failed_home/.e156-ecosystem-starter-install.lock" &&
      -L "$failed_home/.gemini/rules" && ! -e "$outside_dir/rules.md" ]]; then
    ok
else
    bad "failing installer left a lock, followed a symlink, or did not reject destination"
fi


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

# Reinstallation must restore the *latest* user edit when a subsequent
# install fails. A pre-existing first-install .user backup stays intact.
# This also exercises quoting for spaces and non-ASCII paths.
start "rollback restores timestamped user backup after reinstall"
target="$SANDBOX/reinstall path-Ü/rules"
mkdir -p "$target"
printf 'first user edit' > "$target/lessons.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1
printf 'second user edit' > "$target/lessons.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1
timestamp_backup="$(grep -F "$target/lessons.md.user-" "$MANIFEST_BACKUPS" | head -1)"
if [[ -n "$timestamp_backup" && -f "$timestamp_backup" ]]; then
    rollback "test-triggered timestamped rollback" 2>/dev/null || true
    if [[ "$(cat "$target/lessons.md")" == "second user edit" &&
          "$(cat "$target/lessons.md.user")" == "first user edit" &&
          ! -f "$timestamp_backup" ]]; then
        ok
    else
        bad "the latest edit was not restored, or the first .user backup changed"
    fi
else
    bad "timestamped reinstall backup was not recorded"
fi
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"

# A fixed timestamp makes a same-second collision deterministic. In the
# old installer, cp silently overwrote the pre-existing timestamped backup.
# Run in temporary paths only; do not touch real agent configuration.
start "same-second reinstall preserves previous timestamp backup and rolls back"
target="$SANDBOX/same-second path-Ü/rules"
mkdir -p "$target"
printf 'most recent user edit' > "$target/lessons.md"
printf 'first preserved edit' > "$target/lessons.md.user"
collision_stamp="20261105-081719"
printf 'earlier timestamp edit' > "$target/lessons.md.user-$collision_stamp"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
date() {
    if [[ "$#" -eq 1 && "$1" == "+%Y%m%d-%H%M%S" ]]; then
        printf '%s\n' "$collision_stamp"
    else
        command date "$@"
    fi
}
copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1
unset -f date
collision_backup="$target/lessons.md.user-$collision_stamp-1"
if [[ -f "$collision_backup" &&
      "$(cat "$collision_backup")" == "most recent user edit" &&
      "$(cat "$target/lessons.md.user-$collision_stamp")" == "earlier timestamp edit" &&
      "$(cat "$target/lessons.md.user")" == "first preserved edit" ]] &&
   grep -Fxq "$collision_backup" "$MANIFEST_BACKUPS"; then
    rollback "test-triggered collision rollback" 2>/dev/null || true
    if [[ "$(cat "$target/lessons.md")" == "most recent user edit" &&
          "$(cat "$target/lessons.md.user-$collision_stamp")" == "earlier timestamp edit" &&
          "$(cat "$target/lessons.md.user")" == "first preserved edit" &&
          ! -e "$collision_backup" ]]; then
        ok
    else
        bad "rollback did not restore latest edit or it altered an older backup"
    fi
else
    bad "same-second backup collision clobbered existing backup or was not tracked"
fi
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"

# Context files must preserve successive user edits, just like rules. The
# old helper skipped backups whenever AGENTS.md.user already existed.
start "context reinstall backs up the latest edit even with a .user snapshot"
context_target="$SANDBOX/context path-Ü"
mkdir -p "$context_target"
printf 'earliest context edit' > "$context_target/AGENTS.md.user"
printf 'latest context edit' > "$context_target/AGENTS.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
copy_context_files "$ROOT" "$context_target" >/dev/null 2>&1
context_backup="$(grep -F "$context_target/AGENTS.md.user-" "$MANIFEST_BACKUPS" | head -1)"
if [[ -n "$context_backup" && -f "$context_backup" &&
      "$(cat "$context_backup")" == "latest context edit" &&
      "$(cat "$context_target/AGENTS.md.user")" == "earliest context edit" ]]; then
    rollback "test-triggered context rollback" 2>/dev/null || true
    if [[ "$(cat "$context_target/AGENTS.md")" == "latest context edit" &&
          "$(cat "$context_target/AGENTS.md.user")" == "earliest context edit" &&
          ! -e "$context_backup" ]]; then
        ok
    else
        bad "context rollback did not restore latest edit or preserve first backup"
    fi
else
    bad "context reinstall did not back up the latest edit"
fi
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"

# Force a collision deterministically without touching the real clock.
# Both older backups must survive, and rollback must restore the newest edit.
start "same-second context reinstall preserves prior timestamp backup"
context_target="$SANDBOX/context collision path-Ü"
mkdir -p "$context_target"
printf 'first context snapshot' > "$context_target/AGENTS.md.user"
printf 'older timestamp snapshot' > "$context_target/AGENTS.md.user-20261105-092000"
printf 'latest context edit' > "$context_target/AGENTS.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
date() {
    if [[ "$#" -eq 1 && "$1" == "+%Y%m%d-%H%M%S" ]]; then
        printf '%s\n' "20261105-092000"
    else
        command date "$@"
    fi
}
copy_context_files "$ROOT" "$context_target" >/dev/null 2>&1
unset -f date
context_collision="$context_target/AGENTS.md.user-20261105-092000-1"
if [[ -f "$context_collision" &&
      "$(cat "$context_collision")" == "latest context edit" &&
      "$(cat "$context_target/AGENTS.md.user")" == "first context snapshot" &&
      "$(cat "$context_target/AGENTS.md.user-20261105-092000")" == "older timestamp snapshot" ]] &&
   grep -Fxq "$context_collision" "$MANIFEST_BACKUPS"; then
    rollback "test-triggered context collision rollback" 2>/dev/null || true
    if [[ "$(cat "$context_target/AGENTS.md")" == "latest context edit" &&
          "$(cat "$context_target/AGENTS.md.user")" == "first context snapshot" &&
          "$(cat "$context_target/AGENTS.md.user-20261105-092000")" == "older timestamp snapshot" &&
          ! -e "$context_collision" ]]; then
        ok
    else
        bad "context collision rollback altered an earlier backup or failed to restore"
    fi
else
    bad "same-second context backup was overwritten or not recorded"
fi
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"

# A renderer may fail after creating a partial destination. The ERROR trap
# must remove net-new files even when rendering did not return successfully.
# Use a fresh Bash process so errexit/ERR behave as in a real install, not
# like a function invoked inside a test's conditional expression.
partial_render_driver="$SANDBOX/partial-render-driver.bash"
cat > "$partial_render_driver" <<'BASH_PARTIAL_DRIVER'
set -eEuo pipefail
source "$ROOT/install/install.sh" --import
trap 'rollback "synthetic interrupted render" >/dev/null 2>&1' ERR
render_template() {
    printf 'synthetic partial write' > "$2"
    return 71
}
case "$KIND" in
    rules) copy_rules_to_agent "$ROOT/rules" "$TARGET" ;;
    context) copy_context_files "$ROOT" "$TARGET" ;;
    *) exit 90 ;;
esac
BASH_PARTIAL_DRIVER

start "rules rollback cleans incomplete new file after renderer error"
target="$SANDBOX/partial render rules-Ü/rules"
if ROOT="$ROOT" KIND=rules TARGET="$target" bash "$partial_render_driver" >/dev/null 2>&1; then
    bad "synthetic rules renderer failure was swallowed"
elif [[ ! -e "$target" ]]; then
    ok
else
    bad "rules renderer failure left a partial user configuration file"
fi

start "context rollback cleans incomplete new file after renderer error"
context_target="$SANDBOX/partial render context-Ü"
if ROOT="$ROOT" KIND=context TARGET="$context_target" bash "$partial_render_driver" >/dev/null 2>&1; then
    bad "synthetic context renderer failure was swallowed"
elif [[ ! -e "$context_target" ]]; then
    ok
else
    bad "context renderer failure left a partial user configuration file"
fi

# Creating nested install roots with mkdir -p previously recorded only the
# leaf directory. Rollback then left intermediate empty directories behind.
# All tests use temporary Unicode/space-containing directories.
start "rules interrupted render rolls back newly created ancestor directories"
parent="$SANDBOX/rules parent sentinel-Ü"
mkdir -p "$parent"
printf 'keep parent' > "$parent/existing.txt"
target="$parent/deep one-Ü/deep two/rules"
if ROOT="$ROOT" KIND=rules TARGET="$target" bash "$partial_render_driver" >/dev/null 2>&1; then
    bad "synthetic rules renderer error was swallowed"
elif [[ ! -e "$parent/deep one-Ü" && -f "$parent/existing.txt" &&
        "$(cat "$parent/existing.txt")" == "keep parent" ]]; then
    ok
else
    bad "rules rollback left newly created ancestor directories or changed existing parent"
fi

start "context interrupted render rolls back newly created ancestor directories"
parent="$SANDBOX/context parent sentinel-Ü"
mkdir -p "$parent"
printf 'keep context parent' > "$parent/existing.txt"
context_target="$parent/deep one-Ü/deep two/context"
if ROOT="$ROOT" KIND=context TARGET="$context_target" bash "$partial_render_driver" >/dev/null 2>&1; then
    bad "synthetic context renderer error was swallowed"
elif [[ ! -e "$parent/deep one-Ü" && -f "$parent/existing.txt" &&
        "$(cat "$parent/existing.txt")" == "keep context parent" ]]; then
    ok
else
    bad "context rollback left newly created ancestor directories or changed existing parent"
fi

# Simulate an unrelated subsequent failure after memory scaffolding succeeds.
# The ERR trap must remove all new ancestors but retain a pre-existing parent.
memory_ancestor_driver="$SANDBOX/memory-ancestor-driver.bash"
cat > "$memory_ancestor_driver" <<'BASH_MEMORY_ANCESTOR_DRIVER'
set -eEuo pipefail
source "$ROOT/install/install.sh" --import
trap 'rollback "synthetic later failure" >/dev/null 2>&1' ERR
copy_memory_scaffold "$ROOT/memory" "$TARGET"
false
BASH_MEMORY_ANCESTOR_DRIVER
start "memory late failure rolls back newly created ancestors and preserves parent"
parent="$SANDBOX/memory parent sentinel-Ü"
mkdir -p "$parent"
printf 'keep memory parent' > "$parent/existing.txt"
memory_target="$parent/deep one-Ü/deep two/memory"
if ROOT="$ROOT" TARGET="$memory_target" bash "$memory_ancestor_driver" >/dev/null 2>&1; then
    bad "synthetic memory later failure was swallowed"
elif [[ ! -e "$parent/deep one-Ü" && -f "$parent/existing.txt" &&
        "$(cat "$parent/existing.txt")" == "keep memory parent" ]]; then
    ok
else
    bad "memory rollback left newly created ancestors or changed existing parent"
fi

# Symlinked user destinations must be refused before any other config files
# are installed. The external fixture is never a real agent configuration.
start "rules install refuses symlink leaf without partial writes"
target="$SANDBOX/symlink rules-Ü/rules"
mkdir -p "$target"
external="$SANDBOX/outside-rule-content"
printf 'external sentinel' > "$external"
ln -s "$external" "$target/lessons.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1; then
    bad "rules installer followed an existing leaf symlink"
elif [[ -L "$target/lessons.md" &&
        "$(cat "$external")" == "external sentinel" &&
        ! -e "$target/rules.md" && ! -e "$target/advanced-stats.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "rules symlink refusal caused changes or partial installation"
fi

start "context install refuses dangling leaf symlink even with force"
context_target="$SANDBOX/dangling context-Ü"
mkdir -p "$context_target"
external="$SANDBOX/never-created-outside"
ln -s "$external" "$context_target/AGENTS.md"
saved_force="$FORCE"; FORCE=1
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_context_files "$ROOT" "$context_target" >/dev/null 2>&1; then
    bad "context installer accepted a dangling link with force"
elif [[ -L "$context_target/AGENTS.md" &&
        ! -e "$external" && ! -e "$context_target/CLAUDE.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "context symlink refusal modified an external path"
fi
FORCE="$saved_force"

start "rules install refuses symlinked agent parent directory"
agent_parent="$SANDBOX/agent parent-Ü"
external_dir="$SANDBOX/outside-agent-directory"
mkdir -p "$agent_parent" "$external_dir"
ln -s "$external_dir" "$agent_parent/.claude"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_rules_to_agent "$ROOT/rules" "$agent_parent/.claude/rules" >/dev/null 2>&1; then
    bad "rules installer accepted symlinked agent config parent"
elif [[ ! -e "$external_dir/rules" && ! -s "$MANIFEST_DIRS" ]]; then
    ok
else
    bad "rules install traversed the symlinked agent parent"
fi

start "memory scaffold refuses symlinked templates directory"
memory_target="$SANDBOX/memory path-Ü"
outside_templates="$SANDBOX/elsewhere-templates"
mkdir -p "$memory_target" "$outside_templates"
ln -s "$outside_templates" "$memory_target/templates"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
    bad "memory scaffold followed symlinked templates directory"
elif [[ -L "$memory_target/templates" && ! -e "$memory_target/MEMORY.md" &&
        ! -e "$outside_templates/MEMORY.md" && ! -s "$MANIFEST_FILES" ]]; then
    ok
else
    bad "memory symlink refusal modified existing files"
fi

# A memory root with no top-level Markdown may contain user-edited nested
# templates. An installer must not clobber them when bootstrapping MEMORY.md.
start "memory scaffold preserves existing nested templates and adds missing files"
memory_target="$SANDBOX/memory nested edit-Ü"
mkdir -p "$memory_target/templates"
fixture_template=""
for fixture in "$ROOT"/memory/templates/*.md; do
    fixture_template="$fixture"
    break
done
if [[ -f "$fixture_template" ]]; then
    fixture_name="$(basename "$fixture_template")"
    printf 'user-edited nested memory' > "$memory_target/templates/$fixture_name"
    : > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
    if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1 &&
       [[ "$(cat "$memory_target/templates/$fixture_name")" == "user-edited nested memory" &&
          -f "$memory_target/MEMORY.md" &&
          "$(find "$memory_target/templates" -maxdepth 1 -type f -name '*.md' | wc -l)" -eq "$(find "$ROOT/memory/templates" -maxdepth 1 -type f -name '*.md' | wc -l)" ]]; then
        ok
    else
        bad "memory scaffold lost a user-edited nested template or missed new templates"
    fi
else
    bad "memory source template fixture missing"
fi

# A later install failure must undo only files/directories created by the
# current memory bootstrap. Newly created empty directories must not linger.
start "memory rollback removes newly scaffolded directory tree"
memory_target="$SANDBOX/memory new rollback-Ü"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
    rollback "synthetic later-step failure" >/dev/null 2>&1 || true
    if [[ ! -e "$memory_target" ]]; then
        ok
    else
        bad "rollback left net-new memory directories behind"
    fi
else
    bad "clean memory bootstrap failed"
fi
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"

start "memory rollback keeps pre-existing nested user templates"
memory_target="$SANDBOX/memory existing rollback-Ü"
mkdir -p "$memory_target/templates"
printf 'keep user edit' > "$memory_target/templates/$fixture_name"
if [[ -f "$fixture_template" ]]; then
    : > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
    if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
        rollback "synthetic later-step failure" >/dev/null 2>&1 || true
        if [[ "$(cat "$memory_target/templates/$fixture_name")" == "keep user edit" &&
              ! -e "$memory_target/MEMORY.md" &&
              "$(find "$memory_target/templates" -maxdepth 1 -type f -name '*.md' | wc -l)" -eq 1 ]]; then
            ok
        else
            bad "rollback removed existing template or left new memory files"
        fi
    else
        bad "memory bootstrap failed with user nested template"
    fi
else
    bad "memory source template fixture missing"
fi
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="$MANIFEST_DIR/files"
MANIFEST_DIRS="$MANIFEST_DIR/dirs"
MANIFEST_BACKUPS="$MANIFEST_DIR/backups"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"

# A symlinked grandparent redirects writes even when the target and its
# immediate parent are real directories. All paths remain in this test sandbox.
start "rules install refuses an ancestor symlink, without external writes"
ancestor_via="$SANDBOX/ancestor via-Ü"
ancestor_outside="$SANDBOX/ancestor outside-Ü"
mkdir -p "$ancestor_via" "$ancestor_outside/deep/.claude" "$ancestor_outside/deep/.gemini"
ln -s "$ancestor_outside" "$ancestor_via/redirect"
target="$ancestor_via/redirect/deep/.claude/rules"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1; then
    bad "rules install followed an ancestor symlink"
elif [[ -L "$ancestor_via/redirect" &&
        ! -e "$ancestor_outside/deep/.claude/rules" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_DIRS" &&
        ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "rules ancestor refusal modified redirected files or manifest"
fi

start "context install refuses an ancestor symlink, without external writes"
context_target="$ancestor_via/redirect/deep/.gemini"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_context_files "$ROOT" "$context_target" >/dev/null 2>&1; then
    bad "context install followed an ancestor symlink"
elif [[ ! -e "$ancestor_outside/deep/.gemini/AGENTS.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_DIRS" &&
        ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "context ancestor refusal modified redirected files or manifest"
fi

start "memory scaffold refuses an ancestor symlink, without external writes"
memory_target="$ancestor_via/redirect/deep/.claude/memory"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
    bad "memory scaffold followed an ancestor symlink"
elif [[ ! -e "$ancestor_outside/deep/.claude/memory/MEMORY.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_DIRS" &&
        ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "memory ancestor refusal modified redirected files or manifest"
fi

# A non-symlinked templates directory can itself contain a symlinked file.
# Reject it BEFORE writing MEMORY.md, including when other templates are safe.
start "memory scaffold refuses an existing symlinked template leaf"
memory_target="$SANDBOX/memory nested-Ü"
outside_template="$SANDBOX/outside nested template"
mkdir -p "$memory_target/templates"
printf 'preserve this outside file' > "$outside_template"
template_fixture=""
for src_template in "$ROOT"/memory/templates/*.md; do
    template_fixture="$src_template"
    break
done
if [[ -f "$template_fixture" ]]; then
    ln -s "$outside_template" "$memory_target/templates/$(basename "$template_fixture")"
    : > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
    if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
        bad "memory scaffold followed a nested template leaf symlink"
    elif [[ "$(cat "$outside_template")" == "preserve this outside file" &&
            ! -e "$memory_target/MEMORY.md" &&
            ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
        ok
    else
        bad "memory nested-template refusal modified files or manifest"
    fi
else
    bad "memory template fixture missing"
fi

# Non-regular nodes are unsafe config destinations: a FIFO write could
# block indefinitely. All fixtures are isolated; reject before any writes.
start "rules install refuses FIFO leaf with no partial writes"
target="$SANDBOX/fifo rules-Ü/rules"
mkdir -p "$target"
mkfifo "$target/lessons.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1; then
    bad "rules installer accepted FIFO destination"
elif [[ -p "$target/lessons.md" && ! -e "$target/rules.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "rules FIFO refusal changed filesystem or manifest"
fi

start "context install rejects a directory at context-file leaf"
context_target="$SANDBOX/directory context-Ü"
mkdir -p "$context_target/AGENTS.md"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_context_files "$ROOT" "$context_target" >/dev/null 2>&1; then
    bad "context installer accepted directory as a document"
elif [[ -d "$context_target/AGENTS.md" &&
        ! -e "$context_target/CLAUDE.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "context directory refusal left partial copies"
fi

start "memory scaffold refuses a file in place of templates directory"
memory_target="$SANDBOX/file templates-Ü"
mkdir -p "$memory_target"
printf 'preserve original templates sentinel' > "$memory_target/templates"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
    bad "memory scaffold accepted file as templates directory"
elif [[ "$(cat "$memory_target/templates")" == "preserve original templates sentinel" &&
        ! -e "$memory_target/MEMORY.md" &&
        ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
    ok
else
    bad "memory templates refusal changed user files or manifest"
fi

start "memory scaffold refuses FIFO inside normal templates directory"
memory_target="$SANDBOX/fifo template-Ü"
mkdir -p "$memory_target/templates"
template_fixture=""
for src_template in "$ROOT"/memory/templates/*.md; do
    template_fixture="$src_template"
    break
done
if [[ -f "$template_fixture" ]]; then
    mkfifo "$memory_target/templates/$(basename "$template_fixture")"
    : > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
    if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
        bad "memory scaffold accepted a template FIFO"
    elif [[ -p "$memory_target/templates/$(basename "$template_fixture")" &&
            ! -e "$memory_target/MEMORY.md" &&
            ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
        ok
    else
        bad "memory FIFO refusal left partial installation"
    fi
else
    bad "memory template source missing"
fi

# Hardlinks are regular files, so symlink/nonregular checks alone miss
# external data reachable through a second inode name. A template renderer
# opening that path for writing would clobber the other hardlink's content.
# Use only temporary, synthetic files; skip if host filesystem cannot hardlink.
start "rules installer refuses hardlinked rule destination before copying"
target="$SANDBOX/hardlink rules-Ü/rules"
mkdir -p "$target"
outside_hardlink="$SANDBOX/external rule hardlink-Ü"
printf 'outside rule must survive' > "$outside_hardlink"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if ln "$outside_hardlink" "$target/lessons.md" 2>/dev/null; then
    if copy_rules_to_agent "$ROOT/rules" "$target" >/dev/null 2>&1; then
        bad "rules accepted a hardlinked destination"
    elif [[ "$(cat "$outside_hardlink")" == "outside rule must survive" &&
            ! -e "$target/rules.md" && ! -e "$target/e156.md" &&
            ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
        ok
    else
        bad "rules hardlink refusal changed other files or manifest"
    fi
else
    printf '  [~] hardlinks unavailable for rules fixture\n'
fi

start "context installer refuses hardlinked AGENTS.md before copying"
context_target="$SANDBOX/hardlink context-Ü"
mkdir -p "$context_target"
outside_hardlink="$SANDBOX/external context hardlink-Ü"
printf 'outside context must survive' > "$outside_hardlink"
: > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
if ln "$outside_hardlink" "$context_target/AGENTS.md" 2>/dev/null; then
    if copy_context_files "$ROOT" "$context_target" >/dev/null 2>&1; then
        bad "context accepted hardlinked AGENTS.md"
    elif [[ "$(cat "$outside_hardlink")" == "outside context must survive" &&
            ! -e "$context_target/CLAUDE.md" &&
            ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
        ok
    else
        bad "context hardlink refusal changed other files or manifest"
    fi
else
    printf '  [~] hardlinks unavailable for context fixture\n'
fi

start "memory installer refuses hardlinked nested template before writing MEMORY.md"
memory_target="$SANDBOX/hardlink memory-Ü"
mkdir -p "$memory_target/templates"
outside_hardlink="$SANDBOX/external template hardlink-Ü"
printf 'outside template must survive' > "$outside_hardlink"
template_fixture=""
for src_template in "$ROOT"/memory/templates/*.md; do
    template_fixture="$src_template"
    break
done
if [[ -f "$template_fixture" ]] &&
   ln "$outside_hardlink" "$memory_target/templates/$(basename "$template_fixture")" 2>/dev/null; then
    : > "$MANIFEST_FILES"; : > "$MANIFEST_DIRS"; : > "$MANIFEST_BACKUPS"
    if copy_memory_scaffold "$ROOT/memory" "$memory_target" >/dev/null 2>&1; then
        bad "memory installer accepted a hardlinked nested template"
    elif [[ "$(cat "$outside_hardlink")" == "outside template must survive" &&
            ! -e "$memory_target/MEMORY.md" &&
            ! -s "$MANIFEST_FILES" && ! -s "$MANIFEST_BACKUPS" ]]; then
        ok
    else
        bad "memory hardlink refusal left partial install or clobbered external file"
    fi
else
    printf '  [~] hardlink/template fixture unavailable on this host\n'
fi

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

# CLI discovery regression: negative controls use only isolated shell fixtures.
# They cannot certify a pinned Overmind/TruthCert installation.
start "overmind CLI discovery refuses an exported shell function"
cli_empty="$SANDBOX/overmind-empty-PATH"
mkdir -p "$cli_empty"
overmind() { return 0; }
export -f overmind
if ( PATH="$cli_empty"; source "$ROOT/scripts/install-overmind.sh" --import; ! test_overmind_installed ); then
    ok
else
    bad "a shell function without an executable was accepted as Overmind"
fi
unset -f overmind

start "overmind CLI discovery accepts an executable PATH fixture"
cli_bin="$SANDBOX/overmind-cli-PATH"
mkdir -p "$cli_bin"
printf '#!/bin/sh\nexit 0\n' > "$cli_bin/overmind"
chmod 700 "$cli_bin/overmind"
if ( PATH="$cli_bin"; source "$ROOT/scripts/install-overmind.sh" --import; test_overmind_installed ); then
    ok
else
    bad "the executable fixture was not discovered"
fi

start "overmind CLI discovery refuses a non-executable PATH entry"
chmod 600 "$cli_bin/overmind"
if ( PATH="$cli_bin"; source "$ROOT/scripts/install-overmind.sh" --import; ! test_overmind_installed ); then
    ok
else
    bad "a non-executable file was accepted as Overmind"
fi

start "new_truthcert_hmac_key produces a 64-hex-char string"
hex="$(bash -c "source '$ROOT/scripts/install-overmind.sh' --import && new_truthcert_hmac_key")"
[[ ${#hex} -eq 64 && "$hex" =~ ^[0-9a-f]{64}$ ]] && ok

# Describe: supply-chain pinning (P0 — fresh installs must be reproducible)
# Retain these test identities for the honest-ratchet, but require the
# exact release-target commit. A mutable tag alone is not an immutable pin.
start "sentinel_default_source pins to a tagged release by default"
default_src="$(bash -c "source '$ROOT/scripts/install-sentinel.sh' --import && sentinel_default_source")"
assert_eq "$default_src" "git+https://github.com/mahmood726-cyber/Sentinel.git@5808f2bdc024506fa3d49a367c88b42b15fdf164" && ok

start "sentinel_default_source honours SENTINEL_REF override"
override_sha="ffffffffffffffffffffffffffffffffffffffff"
override_src="$(bash -c "export SENTINEL_REF='$override_sha'; source '$ROOT/scripts/install-sentinel.sh' --import; sentinel_default_source")"
assert_eq "$override_src" "git+https://github.com/mahmood726-cyber/Sentinel.git@$override_sha" && ok

start "sentinel_default_source refuses mutable or malformed overrides"
for unsafe in main master HEAD v1.0.0 deadbeef FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF; do
    if bash -c "export SENTINEL_REF='$unsafe'; source '$ROOT/scripts/install-sentinel.sh' --import; sentinel_default_source" >/dev/null 2>&1; then
        bad "unsafe SENTINEL_REF was accepted: $unsafe"
    fi
done
[[ "$FAIL" -eq 0 ]] && ok

start "overmind_default_source pins to a SHA-or-tag by default"
default_src="$(bash -c "unset OVERMIND_REF; source '$ROOT/scripts/install-overmind.sh' --import && overmind_default_source")"
assert_eq "$default_src" "git+https://github.com/mahmood726-cyber/overmind.git@d3d2de5f84d852f27d64d1686f1e105e190ac375" && ok

start "overmind_default_source honours OVERMIND_REF override"
override_src="$(bash -c "export OVERMIND_REF=main; source '$ROOT/scripts/install-overmind.sh' --import; overmind_default_source")"
assert_eq "$override_src" "git+https://github.com/mahmood726-cyber/overmind.git@main" && ok

start "install-projectindex.sh dot-sources cleanly"
bash -c "source '$ROOT/scripts/install-projectindex.sh' --import && declare -F write_index_markdown_template write_reconcile_script > /dev/null" && ok

start "install-extractor.sh dot-sources cleanly"
bash -c "source '$ROOT/scripts/install-extractor.sh' --import && declare -F test_extractor_present extractor_default_ref extractor_repo_url > /dev/null" && ok

start "extractor_default_ref pins to a SHA-or-tag by default"
default_ref="$(bash -c "source '$ROOT/scripts/install-extractor.sh' --import && extractor_default_ref")"
[[ "$default_ref" =~ ^(v[0-9]|[0-9a-f]{7,40})$ ]] && ok

start "extractor_default_ref honours RCT_EXTRACTOR_REF override"
override_ref="$(bash -c "export RCT_EXTRACTOR_REF=main; source '$ROOT/scripts/install-extractor.sh' --import; extractor_default_ref")"
assert_eq "$override_ref" "main" && ok

start "extractor_repo_url points at rct-extractor-v2"
repo_url="$(bash -c "source '$ROOT/scripts/install-extractor.sh' --import && extractor_repo_url")"
assert_eq "$repo_url" "https://github.com/mahmood726-cyber/rct-extractor-v2.git" && ok

# Describe: log redaction (P1 — secrets must not survive in transcripts)
redact_test() {
    local input="$1" expected="$2" label="$3"
    local tmpf
    tmpf="$(mktemp)"
    printf '%s' "$input" > "$tmpf"
    bash -c "source '$ROOT/install/install.sh' --import; redact_secrets_in_log '$tmpf'"
    local actual
    actual="$(cat "$tmpf")"
    rm -f "$tmpf"
    if [[ "$actual" == *"$expected"* && "$actual" != *"$input"* ]]; then
        return 0
    else
        bad "[$label] expected to find '$expected' and not find original; got: '$actual'"
        return 1
    fi
}

start "redact_secrets_in_log scrubs Google API keys (AIza...)"
redact_test 'export GEMINI_API_KEY=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R' '[REDACTED-google-api-key]' 'google' && ok

start "redact_secrets_in_log scrubs OpenAI keys (sk-...)"
redact_test 'OPENAI_API_KEY=sk-1234567890abcdefABCDEFghijklmnopqrstuvwxyz0' '[REDACTED-openai-key]' 'openai' && ok

start "redact_secrets_in_log scrubs Anthropic keys (sk-ant-...)"
redact_test 'ANTHROPIC_API_KEY=sk-ant-api03-abcdef1234567890ABCDEFghijklmnopqrstuvwxyz' '[REDACTED-anthropic-key]' 'anthropic' && ok

start "redact_secrets_in_log scrubs GitHub tokens (ghp_/gho_...)"
redact_test 'GH_TOKEN=ghp_1234567890abcdef1234567890abcdef1234' '[REDACTED-github-token]' 'github' && ok

start "redact_secrets_in_log scrubs AWS access keys (AKIA...)"
redact_test 'AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE' '[REDACTED-aws-access-key]' 'aws' && ok

start "redact_secrets_in_log scrubs 64-hex HMAC keys"
redact_test 'TRUTHCERT_HMAC_KEY=68c4bf3aecd57c8815e1a8fb74f74eb38c471155a0abf25a9b95e0f7429f97fc' '[REDACTED-64hex]' 'hmac' && ok

start "redact_secrets_in_log scrubs JWTs"
redact_test 'Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c' '[REDACTED-jwt]' 'jwt' && ok

# Describe: backup_existing_pre_push_hook (P0 — researcher's existing hook)
mk_repo() {
    local d
    d="$(mktemp -d)"
    mkdir -p "$d/.git/hooks"
    printf '%s' "$d"
}

start "backup_existing_pre_push_hook returns nothing when no hook exists"
repo="$(mk_repo)"
result="$(bash -c "source '$ROOT/scripts/install-sentinel.sh' --import; backup_existing_pre_push_hook '$repo'")"
[[ -z "$result" ]] && ok
rm -rf "$repo"

start "backup_existing_pre_push_hook backs up user-authored hook"
repo="$(mk_repo)"
printf '#!/bin/sh\nmy custom lint\n' > "$repo/.git/hooks/pre-push"
result="$(bash -c "source '$ROOT/scripts/install-sentinel.sh' --import; backup_existing_pre_push_hook '$repo'")"
if [[ "$result" =~ pre-push\.user-[0-9]{8}-[0-9]{6}$ ]] && [[ -f "$result" ]] && grep -q 'my custom lint' "$result"; then
    ok
else
    bad "expected timestamped backup with original content, got: $result"
fi
rm -rf "$repo"

start "copy_rules_to_agent timestamp-suffixes second-rerun backups (P2)"
target="$(mktemp -d)"
src="$ROOT/rules"
# First re-install: lessons.md.user gets created
echo "edit-1" > "$target/lessons.md"
copy_rules_to_agent "$src" "$target" >/dev/null
# Now lessons.md.user contains "edit-1"
# Re-edit lessons.md and re-install
echo "edit-2" > "$target/lessons.md"
copy_rules_to_agent "$src" "$target" >/dev/null
# Original .user must still hold "edit-1"; the .user-<ts> must hold "edit-2"
ts_backup_count="$(ls "$target"/lessons.md.user-* 2>/dev/null | wc -l)"
[[ "$(cat "$target/lessons.md.user")" == "edit-1" ]] && \
    [[ "$ts_backup_count" -eq 1 ]] && \
    [[ "$(cat "$target"/lessons.md.user-*)" == "edit-2" ]] && ok
rm -rf "$target"

start "backup_existing_pre_push_hook skips Sentinel-installed hooks"
repo="$(mk_repo)"
printf '#!/bin/sh\nsentinel run-pre-push --repo .\n' > "$repo/.git/hooks/pre-push"
result="$(bash -c "source '$ROOT/scripts/install-sentinel.sh' --import; backup_existing_pre_push_hook '$repo'")"
if [[ -z "$result" ]] && ! ls "$repo"/.git/hooks/pre-push.user-* >/dev/null 2>&1; then
    ok
else
    bad "expected no backup for Sentinel-installed hook"
fi
rm -rf "$repo"

# E156 offline capsule profile persistence must treat a target path as data.
# The isolated path is synthetic; this is installer-integrity failure injection,
# not a live five-component canary or evidence-synthesis dataset.
start "E156 capsule shell profiles preserve literal paths without executing them"
rc_home="$SANDBOX/e156-profile-home"
mkdir -p "$rc_home"
: > "$rc_home/.bashrc"
: > "$rc_home/.zshrc"
injected_file="$rc_home/path-executed"
dangerous_path="$SANDBOX/space ' quote \"double\" \$(touch $injected_file) \$HOME"
if (
    export HOME="$rc_home"
    source "$ROOT/scripts/install-e156-capsules.sh" --import
    persist_e156_path_env "$dangerous_path" >/dev/null
    bash -c 'source "$1"; [[ "$E156_CAPSULES_PATH" == "$2" ]]' _ "$HOME/.bashrc" "$dangerous_path" &&
    bash -c 'source "$1"; [[ "$E156_CAPSULES_PATH" == "$2" ]]' _ "$HOME/.zshrc" "$dangerous_path"
) && [[ ! -e "$injected_file" ]]; then
    ok
else
    bad "profile source executed part of the requested path or changed its value"
fi

# Summary
echo
echo "Tests completed: $((PASS+FAIL))"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
exit 0
