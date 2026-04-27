#!/usr/bin/env bash
# on-attach.sh -- runs every time the user opens a new terminal in the
# Codespace. Greets them and surfaces the agent handoff prompt path.
#
# Idempotent and cheap: just a few echos. No filesystem writes.

set -u

cat <<'BANNER'

=====================================================
  E156 Ecosystem Starter -- ready
=====================================================

Rules + memory are installed in ~/.claude, ~/.gemini, ~/.codex.

NEXT STEP -- finish the install with an AI agent:

  1. Run an agent in this terminal (Claude Code is pre-installed):
       claude

  2. When it prompts you, paste the contents of:
       ~/.config/e156/handoff.md

  3. Hit Enter. The agent diagnoses prereqs, smoke-tests Sentinel/Overmind
     if you want them, and scaffolds your first E156 paper.

Tip: open the file with `cat ~/.config/e156/handoff.md` and copy the text,
or click it in the file explorer on the left.

If anything fails: open an issue with what you tried. The repo is at
github.com/mahmood726-cyber/e156-ecosystem-starter

=====================================================

BANNER
