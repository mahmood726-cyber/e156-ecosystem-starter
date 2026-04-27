#!/usr/bin/env bash
# write-gemini-handoff.sh -- bash parallel of write-gemini-handoff.ps1.
#
# Called at the tail of install.sh to hand the rest of the bootstrap to an
# agent. Writes the handoff prompt to ~/Desktop/paste-into-gemini.txt (or
# $XDG_DESKTOP_DIR if set), copies to the clipboard if pbcopy/xclip/wl-copy
# is available, and prints a one-screen "next step" block.
#
# Failure non-fatal: any clipboard or desktop write that fails must NOT
# take down a successful install. Warn and continue.

set -u

starter_root="${E156_STARTER_ROOT:-}"
if [[ -z "$starter_root" ]]; then
    starter_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
prompt_file="$starter_root/scripts/gemini-handoff-prompt.md"
if [[ ! -f "$prompt_file" ]]; then
    echo "warning: handoff prompt not found at $prompt_file" >&2
    exit 0
fi

# Pick a sensible "Desktop" location; fall back to $HOME if Desktop missing.
desktop="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
[[ -d "$desktop" ]] || desktop="$HOME"
paste_file="$desktop/paste-into-gemini.txt"

if cp "$prompt_file" "$paste_file" 2>/dev/null; then
    wrote_file=1
else
    wrote_file=0
    echo "warning: could not write $paste_file" >&2
fi

# Try to copy to the system clipboard. Order matters: macOS > Wayland > X11.
wrote_clip=0
if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "$prompt_file" 2>/dev/null && wrote_clip=1
elif command -v wl-copy >/dev/null 2>&1; then
    wl-copy < "$prompt_file" 2>/dev/null && wrote_clip=1
elif command -v xclip >/dev/null 2>&1; then
    xclip -selection clipboard < "$prompt_file" 2>/dev/null && wrote_clip=1
elif command -v xsel >/dev/null 2>&1; then
    xsel --clipboard --input < "$prompt_file" 2>/dev/null && wrote_clip=1
fi

echo
echo "====================================================="
echo "  Almost done -- one paste left"
echo "====================================================="
echo
echo "The installer set up rules + memory + (optional) hooks."
echo "An AI agent finishes the rest: prereq diagnosis, smoke tests,"
echo "scaffolding your first paper. Hand off to it now:"
echo
echo "  1. In any folder, run one of:"
echo "       gemini"
echo "       claude"
echo "       codex"
echo "  2. Paste the handoff prompt:"
if [[ "$wrote_clip" == "1" ]]; then
    echo "       (already in your clipboard -- just paste)"
else
    echo "       (no clipboard tool found -- open the file below and copy)"
fi
if [[ "$wrote_file" == "1" ]]; then
    echo "       Backup copy: $paste_file"
fi
echo "  3. Hit Enter. The agent takes over from there."
echo
