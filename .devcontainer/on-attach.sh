#!/usr/bin/env bash
# on-attach.sh -- runs every time the user opens a new terminal in the
# Codespace. Greets them ONCE per container session, surfaces what is
# installed, and tells them the single next action: paste the handoff
# prompt into an agent.
#
# Per-session detection: we record PID 1's mtime in the marker file.
# PID 1 (the container init process) is created when the container
# starts and persists for the container's lifetime. When the container
# restarts (rebuild, stop+resume), PID 1's mtime changes. So:
#   - Same session as marker -> suppress banner, show one-line reminder.
#   - New session (PID 1 mtime changed) -> show full banner, update marker.
#   - No marker yet -> show full banner.
# This survives /tmp persistence and /tmp wiping equally well, because
# the freshness signal is the container's PID 1, not the marker's age.
# (Per second-pass review 2026-04-27, P1-A.)

set -u

marker="/tmp/e156-attach-shown"
container_init_mtime="$(stat -c %Y /proc/1 2>/dev/null || echo 0)"

if [[ -f "$marker" ]]; then
    recorded_mtime="$(cat "$marker" 2>/dev/null || echo 0)"
    if [[ "$recorded_mtime" == "$container_init_mtime" && "$container_init_mtime" != "0" ]]; then
        # Same container session -> quiet one-liner.
        echo "[E156] Ready. Handoff prompt: cat ~/.config/e156/handoff.md  (rm $marker for full banner)"
        exit 0
    fi
fi
# New session (or first ever): record current PID 1 mtime so subsequent
# terminal opens in this session take the quiet path.
printf '%s' "$container_init_mtime" > "$marker" 2>/dev/null || true

# Detect what actually landed (the build may have failed individual components
# even with FULL); show the student the truth, not a marketing claim.
have() { command -v "$1" >/dev/null 2>&1 && echo "  [OK]   $1" || echo "  [--]   $1 (not on PATH)"; }
file_present() {
    local path="$1" label="$2"
    if [[ -e "$path" ]]; then echo "  [OK]   $label"
    else echo "  [--]   $label (missing: $path)"
    fi
}

cat <<'BANNER'

=====================================================
  E156 Ecosystem Starter -- ready to use
=====================================================

What just got installed in this codespace:
BANNER

file_present "$HOME/.claude/rules/rules.md"      "rules pack          (~/.claude/rules/)"
file_present "$HOME/.claude/memory/MEMORY.md"    "memory scaffold     (~/.claude/memory/)"
file_present "$HOME/code/my-first-repo/.git/hooks/pre-push" "Sentinel hook       (~/code/my-first-repo/)"
file_present "$HOME/.config/e156/truthcert-hmac-key"  "TruthCert HMAC key  (~/.config/e156/)"
file_present "$HOME/code/ProjectIndex/INDEX.md"  "ProjectIndex seed   (~/code/ProjectIndex/)"
have overmind
have sentinel
have gemini
have claude

cat <<'BANNER'

ONE STEP LEFT -- run an agent and paste the handoff prompt:

  1. Pick an agent (gemini is free, browser-OAuth login):
       gemini       # free, sign in with Google
       claude       # paid, needs ANTHROPIC_API_KEY

  2. The agent will ask what to do. Paste the contents of:
       ~/.config/e156/handoff.md

     Quick way to copy it:
       cat ~/.config/e156/handoff.md

  3. Hit Enter. The agent diagnoses any missing prereqs, smoke-tests
     Sentinel + Overmind, and scaffolds your first E156 paper.

The handoff prompt is also visible in the file explorer on the left,
under .config/e156/handoff.md.

=====================================================

BANNER
