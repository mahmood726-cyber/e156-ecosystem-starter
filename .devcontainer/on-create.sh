#!/usr/bin/env bash
# on-create.sh -- runs once when the Codespace is built.
#
# Goal: when the student opens the codespace, ALL of Mahmood's quality-dev
# stack is already installed and ready. Not just rules + memory -- also
# Sentinel pre-push hook, Overmind verifier (with TruthCert HMAC key
# generated and persisted), ProjectIndex seed, and at least one agent CLI
# on PATH so the handoff prompt works the moment they hit Enter.
#
# Failure non-fatal where reasonable: a sub-installer that fails should NOT
# take down the container build. Print a warning, continue. The end-of-build
# banner (printed by install.sh itself) reports per-component status.

set -u
cd "$(dirname "$0")/.."   # repo root

echo
echo "==> E156 Ecosystem Starter -- Codespaces full bootstrap"
echo "    Stack: rules + memory + Sentinel + Overmind + ProjectIndex + agent CLIs"
echo "    This takes ~2-3 minutes. Progress markers below."
echo

# Phase counter for at-a-glance progress; expand if/when phases change.
PHASES_TOTAL=5
phase() { echo; echo "==> [${1}/${PHASES_TOTAL}] ${2}"; }

# Make every shipped script executable. The repo may have been cloned by the
# Codespaces clone step, which doesn't always preserve +x.
chmod +x install/install.sh scripts/*.sh .devcontainer/*.sh 2>/dev/null || true

phase 1 "Detecting GitHub user"
# install.sh --full needs --github-user passed non-interactively (otherwise
# it prompts and hangs the codespace build). Try several Codespaces-provided
# env vars; final fall-through is the gh CLI which is pre-authed via
# $GITHUB_TOKEN. If all of those fail, leave the {{GITHUB_USER}} placeholder
# in the rules and the student edits it later.
gh_user=""
for candidate in "${GITHUB_USER:-}" "${GITHUB_REPOSITORY_OWNER:-}" ; do
    if [[ -n "$candidate" ]]; then gh_user="$candidate"; break; fi
done
if [[ -z "$gh_user" ]] && command -v gh >/dev/null 2>&1; then
    gh_user="$(gh api user --jq .login 2>/dev/null || true)"
fi
gh_user="${gh_user:-{{GITHUB_USER}}}"
echo "    GitHub user resolved as: $gh_user"

# --- Pre-install at least one free agent CLI --------------------------------
# Gemini CLI is the right default for student users -- generous free tier,
# Google account login, no API key to pay for. Claude Code is also installed
# for users with an Anthropic API key. Both are best-effort: a failed npm
# install must NOT block the rest of the bootstrap.
phase 2 "Installing agent CLIs — gemini + claude (slowest step, ~30-60s)"
echo
# Pin to known-good versions so a registry breaking-change tomorrow doesn't
# silently break the next codespace build. Bump these deliberately.
# Verified against npm registry on 2026-04-27:
#   @google/gemini-cli         0.39.x  (latest 0.39.1)
#   @anthropic-ai/claude-code  2.1.x   (latest 2.1.119)
#
# Pin semantics:
#   ^0.39.0 on 0.x is restrictive per npm semver: equivalent to ~0.39.0,
#   accepts patch updates only. Correct for gemini-cli.
#   ~2.1.0  on 2.x is restrictive: accepts patch updates only. We use
#   tilde explicitly here because ^2.1.0 would accept minor bumps
#   (2.2.x), and Claude Code is moving fast enough that a 2.2.0 next
#   week could change CLI flags the handoff prompt depends on.
GEMINI_CLI_VERSION="${GEMINI_CLI_VERSION:-^0.39.0}"
CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION:-~2.1.0}"
if command -v npm >/dev/null 2>&1; then
    npm install -g \
        "@google/gemini-cli@${GEMINI_CLI_VERSION}" \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" 2>&1 \
        | sed 's/^/    /' \
        || echo "    WARNING: npm install of agent CLIs failed; continue without."
else
    echo "    WARNING: npm not on PATH; skipping agent-CLI install."
fi

# --- Run the full install chain ---------------------------------------------
# --full chains Sentinel (into ~/code/my-first-repo, with git init), Overmind
# (pip-install + TRUTHCERT_HMAC_KEY generation), and ProjectIndex (seed at
# ~/code/ProjectIndex). It exits 0 if everything succeeded or 2 if any chain
# failed; either way we want to keep going so the student gets at least a
# partial environment.
phase 3 "Running install.sh --full (rules + memory + Sentinel + Overmind + ProjectIndex)"
echo
bash install/install.sh --full --github-user "$gh_user" || \
    echo "==> install.sh --full reported partial failure; see banner above for which components are ok."

phase 4 "Wiring TruthCert key + e156 wrapper + handoff prompt"

# --- TruthCert HMAC key: file-only, no global export ------------------------
# install-overmind.sh writes the key to ~/.config/e156/truthcert-hmac-key
# (mode 600). overmind reads that file at invocation time. We deliberately do
# NOT export TRUTHCERT_HMAC_KEY into the global shell environment via .bashrc
# -- doing so leaks the key to every child process (post-install npm scripts,
# notebook kernels reading os.environ, transitive subshells) for no benefit.
# (Per security review 2026-04-27, P1-3.)
key_file="${HOME}/.config/e156/truthcert-hmac-key"
if [[ -f "$key_file" ]]; then
    echo "==> TruthCert key at $key_file (mode 600). overmind will read it on demand."
fi

# --- Stage the handoff prompt (locale-aware) for the on-attach banner -------
mkdir -p "${HOME}/.config/e156"
locale="${E156_LANG:-${LANG:-en}}"
locale="$(printf '%s' "$locale" | cut -c1-2 | tr 'A-Z' 'a-z')"
case "$locale" in en|fr|pt|ar|ur) ;; *) locale=en ;; esac
prompt_src="scripts/gemini-handoff-prompt.${locale}.md"
[[ -f "$prompt_src" ]] || prompt_src="scripts/gemini-handoff-prompt.en.md"
cp "$prompt_src" "${HOME}/.config/e156/handoff.md"

# --- Install the `e156` wrapper command on PATH -----------------------------
# Single-command UX: `e156 start` launches Gemini with the handoff briefing
# already loaded. Removes the prior cliff where students had to remember
# `cat ~/.config/e156/handoff.md | gemini`. P0-U1 from user-POV review.
mkdir -p "${HOME}/.local/bin"
cp scripts/e156 "${HOME}/.local/bin/e156"
chmod +x "${HOME}/.local/bin/e156"
# Ensure ~/.local/bin is on PATH for new shells. Idempotent.
if ! grep -q '\.local/bin' "${HOME}/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME}/.bashrc"
fi
# Also export for the current build shell so on-attach can find it.
export PATH="$HOME/.local/bin:$PATH"

# --- Record installed version for `e156 version` ----------------------------
# P0-U3 + P1-V3: a shallow Codespace clone breaks `git describe --tags`
# (no tag is reachable without history). Fall back through tag -> SHA ->
# unknown so the file is always non-empty for `e156 version` to read.
if command -v git >/dev/null 2>&1 && [[ -d ".git" ]]; then
    {
        git describe --tags --always 2>/dev/null \
            || git rev-parse --short HEAD 2>/dev/null \
            || echo "unknown"
    } > "${HOME}/.config/e156/installed-ref"
else
    echo "unknown" > "${HOME}/.config/e156/installed-ref"
fi

phase 5 "Done — codespace ready"
echo
echo "==> When you open a terminal it will tell you what to do next."
echo "    TL;DR: type 'e156 start' and press Enter."
echo
