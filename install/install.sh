#!/usr/bin/env bash
# install.sh -- e156-ecosystem-starter bootstrap (Linux / macOS)
#
# Bash parallel of install/install.ps1. Turns a Unix-like laptop into the
# same quality-dev environment: rules + memory + AGENTS.md across Claude
# Code / Gemini CLI / Codex config dirs.
#
# Usage:
#   ./install/install.sh                       # base + interactive chain prompts
#   ./install/install.sh --full                # everything non-interactively
#   ./install/install.sh --non-interactive     # base only, no prompts (CI-safe)
#   ./install/install.sh --dry-run             # SHA gate only
#   ./install/install.sh --force               # overwrite user-edited rules
#
# Per-layer:
#   --install-sentinel <repo-path>             # chain sentinel hook install
#   --install-overmind                          # chain overmind + TruthCert
#   --project-index-root <dir>                  # chain ProjectIndex seed
#   --e156-home <dir>       (default: $HOME/E156)
#   --portfolio-root <dir>  (default: $HOME/ProjectIndex)
#   --sentinel-root <dir>   (default: $HOME/Sentinel)
#   --overmind-root <dir>   (default: $HOME/overmind)
#   --github-user <name>    (default: prompts if not given)
#
# Non-negotiables (AGENTS.md):
#   - Fails closed on missing source files
#   - Never overwrites user-filled memory without --force
#   - Preserves user-edited rules files (backs up to *.user before overwrite)

set -euo pipefail

# Resolve which Python interpreter to call. On modern Linux (Ubuntu 22.04+,
# Fedora, Debian 12+, default WSL) only python3 is on PATH; bare 'python'
# was deliberately removed. Fall through python -> python3 -> fail.
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "ERROR: neither 'python' nor 'python3' found on PATH." >&2
    echo "  Install: sudo apt install python3 python3-pip   (Debian/Ubuntu/WSL)" >&2
    echo "           sudo dnf install python3 python3-pip   (Fedora/RHEL)" >&2
    echo "           brew install python                    (macOS)" >&2
    exit 1
fi

# --------------------------- arg parsing ----------------------------------

DRY_RUN=0
FORCE=0
FULL=0
NON_INTERACTIVE=0
IMPORT=0
INSTALL_SENTINEL=""
INSTALL_OVERMIND=0
PROJECT_INDEX_ROOT=""
# Default rule-template paths align with where the .sh installers ACTUALLY
# land things on a fresh student box (under $HOME/code/). The earlier
# $HOME/E156 / $HOME/ProjectIndex / $HOME/Sentinel / $HOME/overmind defaults
# matched MA's personal layout but caused agent rules to reference paths
# that the installer never created.
E156_HOME_VAR="${HOME}/code/E156"
PORTFOLIO_ROOT="${HOME}/code/ProjectIndex"
SENTINEL_ROOT="${HOME}/code/Sentinel"
OVERMIND_ROOT="${HOME}/code/overmind"
GITHUB_USER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)          DRY_RUN=1; shift ;;
        --force)            FORCE=1; shift ;;
        --full)             FULL=1; shift ;;
        --non-interactive)  NON_INTERACTIVE=1; shift ;;
        --import)           IMPORT=1; shift ;;
        --install-sentinel) INSTALL_SENTINEL="$2"; shift 2 ;;
        --install-overmind) INSTALL_OVERMIND=1; shift ;;
        --project-index-root) PROJECT_INDEX_ROOT="$2"; shift 2 ;;
        --e156-home)        E156_HOME_VAR="$2"; shift 2 ;;
        --portfolio-root)   PORTFOLIO_ROOT="$2"; shift 2 ;;
        --sentinel-root)    SENTINEL_ROOT="$2"; shift 2 ;;
        --overmind-root)    OVERMIND_ROOT="$2"; shift 2 ;;
        --github-user)      GITHUB_USER="$2"; shift 2 ;;
        -h|--help)
            grep -E '^#' "$0" | head -40
            exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# --------------------------- transcript log -------------------------------
# Mirror everything the installer prints to a per-run log file so a student
# hitting a problem can attach it to an issue (or feed it to doctor-report).
# Logs land at ~/.local/share/e156/logs/install-<ts>.log on Linux, and at
# Library/Logs/e156/install-<ts>.log on macOS. Failure to start the log is
# non-fatal.
redact_secrets_in_log() {
    # Scrubs API keys, tokens, and high-entropy secrets from a transcript file
    # in-place. Runs at end-of-install so a student attaching the log to an
    # issue, or sharing it for help, doesn't leak credentials.
    #
    # Patterns covered (mirrors install.ps1 Invoke-LogRedaction):
    #   AIza... (Google), sk-/sk-ant- (OpenAI/Anthropic),
    #   ghp_/gho_/ghs_/ghu_ (GitHub), AKIA (AWS), 64-hex (HMAC/generic),
    #   eyJ... JWT, setx/export VAR_KEY/TOKEN/SECRET "x".
    local f="$1"
    [[ -f "$f" ]] || return 0
    # macOS sed lacks -i in-place; use a tmp file for portability.
    local tmp
    tmp="$(mktemp "${f}.redact.XXXXXX")" || return 0
    # Specific patterns first (preserve labels), then generic export-var
    # catch-all (skip lines that already got a labeled redaction so we don't
    # over-redact "[REDACTED-google-api-key]" -> "[REDACTED]").
    sed -E \
        -e 's/AIza[A-Za-z0-9_-]{35}/[REDACTED-google-api-key]/g' \
        -e 's/sk-ant-[A-Za-z0-9_-]{40,}/[REDACTED-anthropic-key]/g' \
        -e 's/sk-[A-Za-z0-9]{40,}/[REDACTED-openai-key]/g' \
        -e 's/gh[opsu]_[A-Za-z0-9]{36,}/[REDACTED-github-token]/g' \
        -e 's/AKIA[A-Z0-9]{16}/[REDACTED-aws-access-key]/g' \
        -e 's/eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/[REDACTED-jwt]/g' \
        -e 's/\b[0-9a-fA-F]{64}\b/[REDACTED-64hex]/g' \
        -e '/\[REDACTED/!s/(export[[:space:]]+[A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASS|HMAC)[A-Za-z0-9_]*=)["'"'"']?[^"'"'"' ]+/\1[REDACTED]/g' \
        "$f" > "$tmp" 2>/dev/null && mv "$tmp" "$f" || rm -f "$tmp"
}

if [[ "$IMPORT" -eq 0 ]]; then
    case "$(uname -s)" in
        Darwin) E156_LOG_DIR="${HOME}/Library/Logs/e156" ;;
        *)      E156_LOG_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/e156/logs" ;;
    esac
    if mkdir -p "$E156_LOG_DIR" 2>/dev/null; then
        E156_LOG_FILE="${E156_LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
        # Tee stdout+stderr through the log without breaking interactive
        # prompts: process substitution leaves the controlling tty in place.
        exec > >(tee -a "$E156_LOG_FILE") 2>&1
        echo "(transcript: $E156_LOG_FILE)"
        # Redact secrets from the transcript on exit (success or failure).
        # Close stdout/stderr first so the tee subshell flushes and exits;
        # then sed-substitute in place. Failure-safe: if redaction fails the
        # raw log is still on disk for the student to clean up manually.
        _e156_finalize_log() {
            [[ -n "${E156_LOG_FILE:-}" ]] || return 0
            exec >&- 2>&- 2>/dev/null || :
            sleep 0.2 2>/dev/null || :
            redact_secrets_in_log "$E156_LOG_FILE" 2>/dev/null || :
        }
        trap _e156_finalize_log EXIT
    fi
fi

# --------------------------- layout + self-SHA ----------------------------

SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || greadlink -f "$0" 2>/dev/null || echo "$0")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
STARTER_ROOT="$(dirname "$SCRIPT_DIR")"
HASH_FILE="${STARTER_ROOT}/docs/HASH-linux.txt"

verify_self_sha() {
    if [[ ! -f "$HASH_FILE" ]]; then
        echo "ERROR: ${HASH_FILE} not found. Re-download the release." >&2
        exit 1
    fi
    local expected actual
    expected="$(tr -d ' \n' < "$HASH_FILE")"
    if command -v sha256sum >/dev/null 2>&1; then
        actual="$(sha256sum "$SCRIPT_PATH" | awk '{print $1}')"
    else
        actual="$(shasum -a 256 "$SCRIPT_PATH" | awk '{print $1}')"
    fi
    if [[ "$expected" != "$actual" ]]; then
        echo "ERROR: install.sh hash mismatch. File may have been tampered with." >&2
        echo "  Expected: $expected" >&2
        echo "  Got:      $actual"   >&2
        exit 1
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "Dry run: self-SHA verified. Exiting before any install steps."
        exit 0
    fi
}

if [[ "$IMPORT" -eq 0 ]]; then
    verify_self_sha
fi

# --------------------------- helpers --------------------------------------

log_step() { printf '==> %s\n' "$1"; }
log_ok()   { printf '    %s\n' "$1"; }
log_warn() { printf '    WARNING: %s\n' "$1" >&2; }

# Rollback manifest: flat files that list net-new files + net-new dirs +
# backups. Keeping them as files (not arrays) lets the EXIT trap access them
# even if the error happens inside a subshell.
MANIFEST_DIR="$(mktemp -d -t e156-rollback.XXXXXX)"
MANIFEST_FILES="${MANIFEST_DIR}/files"
MANIFEST_DIRS="${MANIFEST_DIR}/dirs"
MANIFEST_BACKUPS="${MANIFEST_DIR}/backups"
: > "$MANIFEST_FILES"
: > "$MANIFEST_DIRS"
: > "$MANIFEST_BACKUPS"

rollback() {
    local reason="$1"
    echo
    echo "Rollback triggered: $reason" >&2

    # Delete net-new files (reverse order so nested paths go first)
    if [[ -s "$MANIFEST_FILES" ]]; then
        tac "$MANIFEST_FILES" | while IFS= read -r f; do
            [[ -n "$f" && -f "$f" ]] && rm -f "$f"
        done
    fi
    # Restore backups (.user -> original)
    if [[ -s "$MANIFEST_BACKUPS" ]]; then
        while IFS= read -r b; do
            if [[ -n "$b" && -f "$b" ]]; then
                local orig="${b%.user}"
                mv -f "$b" "$orig"
            fi
        done < "$MANIFEST_BACKUPS"
    fi
    # Remove empty net-new dirs (reverse order)
    if [[ -s "$MANIFEST_DIRS" ]]; then
        tac "$MANIFEST_DIRS" | while IFS= read -r d; do
            [[ -n "$d" && -d "$d" ]] && rmdir "$d" 2>/dev/null || true
        done
    fi
    echo "Rollback complete. Pre-existing user files restored."
    rm -rf "$MANIFEST_DIR"
}
trap 'rollback "unexpected error (line $LINENO)"; exit 1' ERR

# --------------------------- template render -----------------------------

# Render {{NAME}} placeholders in a file using KEY=VALUE pairs. Uses python
# (a prereq) for literal string replacement -- avoids sed's ambiguous
# handling of {{ / }} in ERE and eliminates escaping concerns in the value.
render_template() {
    local infile="$1" outfile="$2"; shift 2
    "$PYTHON" - "$infile" "$outfile" "$@" <<'PY_EOF'
import sys
in_path, out_path = sys.argv[1], sys.argv[2]
pairs = [a.split("=", 1) for a in sys.argv[3:] if "=" in a]
with open(in_path, "r", encoding="utf-8") as f:
    text = f.read()
for key, val in pairs:
    text = text.replace("{{" + key + "}}", val)
with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
PY_EOF
}

copy_rules_to_agent() {
    local src="$1" target="$2"; shift 2
    [[ -d "$src" ]] || { echo "ERROR: source rules dir missing: $src" >&2; return 1; }
    if [[ ! -d "$target" ]]; then
        mkdir -p "$target"
        echo "$target" >> "$MANIFEST_DIRS"
    fi
    local copied=0 backed=0
    for f in "$src"/*.md; do
        local name dest backup actual_backup
        name="$(basename "$f")"
        dest="$target/$name"
        backup="${dest}.user"
        if [[ -f "$dest" && "$FORCE" -eq 0 ]]; then
            # First re-install: back up to <name>.md.user
            # Subsequent re-installs: back up to <name>.md.user-<timestamp> so
            # we never silently overwrite a re-edited file (the original .user
            # backup is preserved as the "first-known-edit" copy).
            if [[ -f "$backup" ]]; then
                actual_backup="${dest}.user-$(date +%Y%m%d-%H%M%S)"
            else
                actual_backup="$backup"
            fi
            cp "$dest" "$actual_backup"
            echo "$actual_backup" >> "$MANIFEST_BACKUPS"
            backed=$((backed+1))
        fi
        local pre_existed=0
        [[ -f "$dest" ]] && pre_existed=1
        render_template "$f" "$dest" "$@"
        [[ "$pre_existed" -eq 0 ]] && echo "$dest" >> "$MANIFEST_FILES"
        copied=$((copied+1))
    done
    log_ok "${target}  (${copied} copied, ${backed} backed up as .user)"
}

copy_context_files() {
    local src_root="$1" target="$2"; shift 2
    if [[ ! -d "$target" ]]; then
        mkdir -p "$target"
        echo "$target" >> "$MANIFEST_DIRS"
    fi
    local count=0
    for name in AGENTS.md CLAUDE.md GEMINI.md CODEX.md; do
        local src="$src_root/$name"
        [[ -f "$src" ]] || continue
        local dest="$target/$name"
        local backup="${dest}.user"
        if [[ -f "$dest" && "$FORCE" -eq 0 && ! -f "$backup" ]]; then
            cp "$dest" "$backup"
            echo "$backup" >> "$MANIFEST_BACKUPS"
        fi
        local pre_existed=0
        [[ -f "$dest" ]] && pre_existed=1
        render_template "$src" "$dest" "$@"
        [[ "$pre_existed" -eq 0 ]] && echo "$dest" >> "$MANIFEST_FILES"
        count=$((count+1))
    done
    log_ok "${target}  (${count} context files)"
}

copy_memory_scaffold() {
    local src="$1" target="$2"
    mkdir -p "$target"
    if compgen -G "$target/*.md" > /dev/null; then
        log_ok "${target}  (already has memory -- preserved, templates not overwritten)"
        return
    fi
    cp "$src/MEMORY.md" "$target/MEMORY.md"
    echo "$target/MEMORY.md" >> "$MANIFEST_FILES"
    mkdir -p "$target/templates"
    for f in "$src/templates"/*.md; do
        cp "$f" "$target/templates/"
        echo "$target/templates/$(basename "$f")" >> "$MANIFEST_FILES"
    done
    log_ok "${target}  (bootstrapped -- starter MEMORY.md + type templates)"
}

test_tool_installed() {
    command -v "$1" >/dev/null 2>&1
}

prompt_yn() {
    local question="$1" default_yes="${2:-1}"
    local hint; if [[ "$default_yes" -eq 1 ]]; then hint="[Y/n]"; else hint="[y/N]"; fi
    local ans
    read -r -p "$question $hint " ans
    ans="${ans,,}"  # lowercase (bash 4+)
    if [[ -z "$ans" ]]; then [[ "$default_yes" -eq 1 ]] && return 0 || return 1; fi
    case "$ans" in y|yes) return 0 ;; *) return 1 ;; esac
}

can_prompt() {
    [[ "$NON_INTERACTIVE" -eq 0 && -t 0 ]]
}

if [[ "$IMPORT" -eq 1 ]]; then
    # Dot-sourced; leave helpers defined, skip the flow
    trap - ERR
    return 0 2>/dev/null || exit 0
fi

# --------------------------- real install flow ---------------------------

echo
echo "e156-ecosystem-starter bootstrap"
echo "Installing quality-dev environment to ${HOME}"
echo

# Step 1: agent CLI detection
log_step "Detecting agent CLIs"
test_tool_installed claude && log_ok "claude: found" || \
    printf '    claude: not on PATH (https://docs.anthropic.com/en/docs/claude-code)\n'
test_tool_installed gemini && log_ok "gemini: found" || \
    printf '    gemini: not on PATH (https://github.com/google-gemini/gemini-cli)\n'
test_tool_installed codex  && log_ok "codex: found"  || \
    printf '    codex: not on PATH (https://github.com/openai/codex)\n'

# Step 1.5: resolve rules-template vars (prompt only for GitHub user)
if [[ -z "$GITHUB_USER" ]] && can_prompt; then
    read -r -p "Your GitHub username (or Enter to leave placeholder): " GITHUB_USER
    GITHUB_USER="${GITHUB_USER// /}"
fi
RULES_VARS=(
    "E156_HOME=$E156_HOME_VAR"
    "PROJECTINDEX_ROOT=$PORTFOLIO_ROOT"
    "SENTINEL_ROOT=$SENTINEL_ROOT"
    "OVERMIND_ROOT=$OVERMIND_ROOT"
    "ECOSYSTEM_STARTER_ROOT=$STARTER_ROOT"
    "GITHUB_USER=${GITHUB_USER:-{{GITHUB_USER}}}"
)

# Step 2: rules
log_step "Copying rules/*.md (with your paths substituted in)"
SOURCE_RULES="$STARTER_ROOT/rules"
for agent_dir in ".claude/rules" ".gemini/rules" ".codex/rules"; do
    copy_rules_to_agent "$SOURCE_RULES" "$HOME/$agent_dir" "${RULES_VARS[@]}"
done

# Step 3: context files
log_step "Writing context files to ~/.claude, ~/.gemini, ~/.codex"
for base in ".claude" ".gemini" ".codex"; do
    copy_context_files "$STARTER_ROOT" "$HOME/$base" "${RULES_VARS[@]}"
done

# Step 4: memory scaffold
log_step "Setting up memory scaffolding"
for base in ".claude" ".gemini"; do
    copy_memory_scaffold "$STARTER_ROOT/memory" "$HOME/$base/memory"
done

# Step 5: chain sub-installers
SCRIPTS_DIR="$STARTER_ROOT/scripts"

# 5a: Sentinel
do_sentinel=0; sentinel_repo=""
# Default Sentinel target. Earlier this was $(pwd), but in the bootstrap-
# extracted flow that's a temp dir under /tmp/e156-ecosystem-starter-main/
# which gets rm -rf'd at the end -- so the hook installed cleanly and was
# then deleted with the temp tree. Now it lands in the student's persistent
# workspace. (Reported in code review.)
sentinel_default_repo="$HOME/code/my-first-repo"
if [[ -n "$INSTALL_SENTINEL" ]]; then
    do_sentinel=1; sentinel_repo="$INSTALL_SENTINEL"
elif [[ "$FULL" -eq 1 ]]; then
    do_sentinel=1; sentinel_repo="$sentinel_default_repo"
    log_ok "(--full) Will install Sentinel hook in: $sentinel_repo"
elif can_prompt; then
    echo
    log_step "Sentinel pre-push hook (blocks 20 defect patterns before git push)"
    if prompt_yn "Install Sentinel in a repo now?" 1; then
        read -r -p "Target repo path (Enter for $sentinel_default_repo): " sentinel_repo
        sentinel_repo="${sentinel_repo:-$sentinel_default_repo}"
        do_sentinel=1
    fi
fi
chain_sentinel="skipped"; chain_sentinel_detail=""
if [[ "$do_sentinel" -eq 1 && -f "$SCRIPTS_DIR/install-sentinel.sh" ]]; then
    # Make sure the target dir exists and is a git repo (Sentinel hook needs .git/).
    if [[ ! -d "$sentinel_repo" ]]; then
        mkdir -p "$sentinel_repo" 2>/dev/null \
            && log_ok "Created $sentinel_repo" \
            || log_warn "Could not create $sentinel_repo"
    fi
    if [[ -d "$sentinel_repo" && ! -d "$sentinel_repo/.git" ]]; then
        ( cd "$sentinel_repo" && git init --quiet ) 2>/dev/null \
            && log_ok "git init at $sentinel_repo"
    fi
    log_step "Chaining: install-sentinel.sh --repo $sentinel_repo"
    if bash "$SCRIPTS_DIR/install-sentinel.sh" --repo "$sentinel_repo"; then
        chain_sentinel="ok"
        chain_sentinel_detail="installed in $sentinel_repo"
    else
        rc=$?
        chain_sentinel="failed"
        chain_sentinel_detail="exited $rc"
        log_warn "install-sentinel.sh exited $rc (continuing; reported in summary)"
    fi
fi

# 5b: Overmind
do_overmind=0
if [[ "$INSTALL_OVERMIND" -eq 1 ]]; then
    do_overmind=1
elif [[ "$FULL" -eq 1 ]]; then
    do_overmind=1
    log_ok "(--full) Will install Overmind + TruthCert"
elif can_prompt; then
    echo
    log_step "Overmind verifier + TruthCert HMAC signing (~200 MB pip deps)"
    prompt_yn "Install Overmind + TruthCert now?" 1 && do_overmind=1 || true
fi
chain_overmind="skipped"; chain_overmind_detail=""
if [[ "$do_overmind" -eq 1 && -f "$SCRIPTS_DIR/install-overmind.sh" ]]; then
    log_step "Chaining: install-overmind.sh"
    if bash "$SCRIPTS_DIR/install-overmind.sh"; then
        chain_overmind="ok"
        chain_overmind_detail="installed"
    else
        rc=$?
        chain_overmind="failed"
        chain_overmind_detail="exited $rc"
        log_warn "install-overmind.sh exited $rc (continuing; reported in summary)"
    fi
fi

# 5c: ProjectIndex
do_pi=0; pi_root=""
pi_default="$HOME/code/ProjectIndex"
if [[ -n "$PROJECT_INDEX_ROOT" ]]; then
    do_pi=1; pi_root="$PROJECT_INDEX_ROOT"
elif [[ "$FULL" -eq 1 ]]; then
    do_pi=1; pi_root="$pi_default"
    log_ok "(--full) Will seed ProjectIndex at: $pi_root"
elif can_prompt; then
    echo
    log_step "ProjectIndex seed (portfolio INDEX.md + reconcile_counts.py)"
    if prompt_yn "Seed ProjectIndex now?" 1; then
        read -r -p "Target dir (Enter for $pi_default): " pi_root
        pi_root="${pi_root:-$pi_default}"
        do_pi=1
    fi
fi
chain_pi="skipped"; chain_pi_detail=""
if [[ "$do_pi" -eq 1 && -f "$SCRIPTS_DIR/install-projectindex.sh" ]]; then
    log_step "Chaining: install-projectindex.sh --root $pi_root"
    if bash "$SCRIPTS_DIR/install-projectindex.sh" --root "$pi_root"; then
        chain_pi="ok"
        chain_pi_detail="seeded at $pi_root"
    else
        rc=$?
        chain_pi="failed"
        chain_pi_detail="exited $rc"
        log_warn "install-projectindex.sh exited $rc (continuing; reported in summary)"
    fi
fi

# Step 6: honest summary (counts failed chains, exits non-zero if any failed).
n_failed=0
for st in "$chain_sentinel" "$chain_overmind" "$chain_pi"; do
    [[ "$st" == "failed" ]] && n_failed=$((n_failed + 1))
done

echo
if [[ "$n_failed" -eq 0 ]]; then
    echo "====================================================="
    echo "  Ecosystem installed cleanly"
    echo "====================================================="
else
    echo "====================================================="
    echo "  Install completed with $n_failed component(s) failing -- see below"
    echo "====================================================="
fi

print_chain() {
    local name="$1" status="$2" detail="$3"
    case "$status" in
        ok)      sym="[OK]";  ;;
        failed)  sym="[X]";   ;;
        *)       sym="[-]";   ;;
    esac
    if [[ -n "$detail" ]]; then
        printf "  %-5s %-14s %-8s -- %s\n" "$sym" "$name" "$status" "$detail"
    else
        printf "  %-5s %-14s %-8s\n" "$sym" "$name" "$status"
    fi
}
print_chain "rules+memory" "ok" ""
print_chain "sentinel"     "$chain_sentinel"     "$chain_sentinel_detail"
print_chain "overmind"     "$chain_overmind"     "$chain_overmind_detail"
print_chain "projectindex" "$chain_pi"           "$chain_pi_detail"

echo
echo "Next steps:"
echo "    1. Read STUDENT-WORKFLOW.md  (brainstorm -> spec-lock -> plan-lock -> TDD -> audit method,"
echo "       worked-example repos, quality gates):"
echo "         https://github.com/mahmood726-cyber/e156-ecosystem-starter/blob/main/STUDENT-WORKFLOW.md"
echo "    2. Run 'claude' or 'gemini' in any repo"
echo "    3. Edit ~/.claude/memory/*.md as you learn preferences"
[[ "$chain_sentinel" != "ok" ]] && echo "    4. Re-try Sentinel later:  ./scripts/install-sentinel.sh --repo $sentinel_default_repo"
[[ "$chain_overmind" != "ok" ]] && echo "    5. Re-try Overmind later:  ./scripts/install-overmind.sh"
[[ "$chain_pi"       != "ok" ]] && echo "    6. Re-try ProjectIndex later:  ./scripts/install-projectindex.sh --root $pi_default"
if [[ "$n_failed" -gt 0 ]]; then
    echo
    echo "If a sub-installer reported a Python error: install python3 and pip"
    echo "(sudo apt install python3 python3-pip on Debian/Ubuntu/WSL), reopen"
    echo "your shell, then re-run the failed sub-installer."
fi
echo

# --- Gemini-CLI handoff (one-paste install completion) ---------------------
# Hand the rest off to an agent. Non-fatal if it fails.
handoff_script="$STARTER_ROOT/scripts/write-gemini-handoff.sh"
if [[ -f "$handoff_script" ]]; then
    bash "$handoff_script" || true
fi

trap - ERR
rm -rf "$MANIFEST_DIR"
# Exit non-zero if any chain failed so callers (bootstrap, CI) can detect.
[[ "$n_failed" -gt 0 ]] && exit 2 || exit 0
