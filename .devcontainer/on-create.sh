#!/usr/bin/env bash
# on-create.sh -- runs once when the Codespace is built.
#
# Strategy: just the base install (rules + memory + AGENTS.md across .claude
# / .gemini / .codex). No Sentinel hook, no Overmind pip-install, no
# ProjectIndex seed. Those are opt-in via the agent handoff prompt because:
#   - Codespaces are ephemeral; an installed sentinel hook on /workspaces is
#     gone the next session
#   - Pip-installing 5+ MB of dependencies on every container build is waste
#   - A non-coder student's first session should be "rules ready, agent ready,
#     start writing", not "wait 90 seconds for pip"
#
# Failure non-fatal: the rules + memory copy is what matters. If something
# downstream fails the container still boots.

set -u
cd "$(dirname "$0")/.."   # repo root

echo
echo "==> E156 Ecosystem Starter -- Codespaces bootstrap"
echo

# Make sure install.sh is executable (the repo may have been cloned by the
# Codespaces clone step rather than by us, which doesn't preserve +x).
chmod +x install/install.sh scripts/*.sh 2>/dev/null || true

# Run the base install non-interactively. --non-interactive skips the
# Sentinel/Overmind/ProjectIndex chain prompts; we do not want an unattended
# 'pip install' on a fresh Codespace.
bash install/install.sh --non-interactive --github-user "${GITHUB_USER:-{{GITHUB_USER}}}" || {
    echo "==> WARNING: base install reported non-zero exit; rules+memory may be partial." >&2
}

# Stage the agent handoff prompt so it appears every time the student
# attaches a terminal (see on-attach.sh).
mkdir -p ~/.config/e156
cp scripts/gemini-handoff-prompt.md ~/.config/e156/handoff.md

echo
echo "==> Base install complete. The integrated terminal will show your"
echo "    next steps when you open it."
echo
