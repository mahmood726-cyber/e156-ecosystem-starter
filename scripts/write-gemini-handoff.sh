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

# Pure locale resolver -- testable, no side effects.
# Precedence: explicit E156_LANG > LC_ALL (POSIX-canonical) > LANG > en.
# Returns one of: en, fr, pt, ar.
e156_resolve_handoff_locale() {
    local raw
    if [[ -n "${E156_LANG:-}" ]]; then raw="$E156_LANG"
    elif [[ -n "${LC_ALL:-}" ]]; then raw="$LC_ALL"
    elif [[ -n "${LANG:-}"   ]]; then raw="$LANG"
    else raw="en"
    fi
    local code
    code="$(printf '%s' "$raw" | cut -c1-2 | tr 'A-Z' 'a-z')"
    case "$code" in en|fr|pt|ar|ur|sw) printf '%s' "$code" ;; *) printf 'en' ;; esac
}

# Resolves the on-disk path, falling back to English if the localised file
# is missing (partial release / file corruption).
e156_resolve_handoff_prompt_path() {
    local starter="$1" locale="${2:-$(e156_resolve_handoff_locale)}"
    local localised="$starter/scripts/gemini-handoff-prompt.${locale}.md"
    if [[ -f "$localised" ]]; then
        printf '%s' "$localised"
    else
        printf '%s' "$starter/scripts/gemini-handoff-prompt.en.md"
    fi
}

# Test hook: --import dot-sources helpers only; --resolve-only prints the
# resolved path and exits so bash tests can assert on it without firing
# the clipboard side effect.
case "${1:-}" in
    --import)       return 0 2>/dev/null || exit 0 ;;
    --resolve-only) e156_resolve_handoff_prompt_path "$starter_root"; exit 0 ;;
esac

prompt_file="$(e156_resolve_handoff_prompt_path "$starter_root")"
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
