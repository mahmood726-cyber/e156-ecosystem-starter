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
E156_HOME_VAR="${HOME}/E156"
PORTFOLIO_ROOT="${HOME}/ProjectIndex"
SENTINEL_ROOT="${HOME}/Sentinel"
OVERMIND_ROOT="${HOME}/overmind"
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
        local name dest backup
        name="$(basename "$f")"
        dest="$target/$name"
        backup="${dest}.user"
        if [[ -f "$dest" && "$FORCE" -eq 0 && ! -f "$backup" ]]; then
            cp "$dest" "$backup"
            echo "$backup" >> "$MANIFEST_BACKUPS"
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
if [[ -n "$INSTALL_SENTINEL" ]]; then
    do_sentinel=1; sentinel_repo="$INSTALL_SENTINEL"
elif [[ "$FULL" -eq 1 ]]; then
    do_sentinel=1; sentinel_repo="$(pwd)"
    log_ok "(--full) Will install Sentinel hook in: $sentinel_repo"
elif can_prompt; then
    echo
    log_step "Sentinel pre-push hook (blocks 20 defect patterns before git push)"
    if prompt_yn "Install Sentinel in a repo now?" 1; then
        read -r -p "Target repo path (Enter for $(pwd)): " sentinel_repo
        sentinel_repo="${sentinel_repo:-$(pwd)}"
        do_sentinel=1
    fi
fi
if [[ "$do_sentinel" -eq 1 && -f "$SCRIPTS_DIR/install-sentinel.sh" ]]; then
    log_step "Chaining: install-sentinel.sh --repo $sentinel_repo"
    bash "$SCRIPTS_DIR/install-sentinel.sh" --repo "$sentinel_repo" || \
        log_warn "install-sentinel.sh exited $? (not fatal; continuing)"
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
if [[ "$do_overmind" -eq 1 && -f "$SCRIPTS_DIR/install-overmind.sh" ]]; then
    log_step "Chaining: install-overmind.sh"
    bash "$SCRIPTS_DIR/install-overmind.sh" || \
        log_warn "install-overmind.sh exited $? (not fatal; continuing)"
fi

# 5c: ProjectIndex
do_pi=0; pi_root=""
if [[ -n "$PROJECT_INDEX_ROOT" ]]; then
    do_pi=1; pi_root="$PROJECT_INDEX_ROOT"
elif [[ "$FULL" -eq 1 ]]; then
    do_pi=1; pi_root="$HOME/ProjectIndex"
    log_ok "(--full) Will seed ProjectIndex at: $pi_root"
elif can_prompt; then
    echo
    log_step "ProjectIndex seed (portfolio INDEX.md + reconcile_counts.py)"
    if prompt_yn "Seed ProjectIndex now?" 1; then
        read -r -p "Target dir (Enter for $HOME/ProjectIndex): " pi_root
        pi_root="${pi_root:-$HOME/ProjectIndex}"
        do_pi=1
    fi
fi
if [[ "$do_pi" -eq 1 && -f "$SCRIPTS_DIR/install-projectindex.sh" ]]; then
    log_step "Chaining: install-projectindex.sh --root $pi_root"
    bash "$SCRIPTS_DIR/install-projectindex.sh" --root "$pi_root" || \
        log_warn "install-projectindex.sh exited $? (not fatal; continuing)"
fi

# Step 6: banner
echo
echo "====================================================="
echo "  Ecosystem installed. You can now:"
echo "    1. Run 'claude' or 'gemini' in any repo"
echo "    2. Edit ~/.claude/memory/*.md as you learn preferences"
[[ "$do_sentinel" -eq 0 ]] && echo "    3. Install Sentinel later:  ./scripts/install-sentinel.sh --repo <dir>"
[[ "$do_overmind" -eq 0 ]] && echo "    4. Install Overmind later:   ./scripts/install-overmind.sh"
[[ "$do_pi" -eq 0 ]]       && echo "    5. Seed ProjectIndex later:  ./scripts/install-projectindex.sh --root <dir>"
echo "====================================================="
echo

trap - ERR
rm -rf "$MANIFEST_DIR"
exit 0
