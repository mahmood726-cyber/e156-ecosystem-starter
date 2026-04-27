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
# even with FULL); show the student the truth, not a marketing claim. Plain-
# English purpose strings instead of engineer jargon — P1-U3 from review.
have() {
    # Args: cmd-name display-name purpose
    local cmd="$1" display="${2:-$1}" purpose="${3:-}"
    if command -v "$cmd" >/dev/null 2>&1; then
        printf "  [OK]   %-15s - %s\n" "$display" "$purpose"
    else
        printf "  [--]   %-15s - %s (not on PATH)\n" "$display" "$purpose"
    fi
}
file_present() {
    local path="$1" label="$2"
    if [[ -e "$path" ]]; then echo "  [OK]   $label"
    else echo "  [--]   $label (missing: $path)"
    fi
}

# Localise the banner header + section labels. P1-U4 from user-POV review.
# Keep it small: just the headers and the post-component CTA. Per-component
# purpose strings stay English for now (clarity > literal translation when
# the technical terms have no good vernacular equivalent).
locale="${E156_LANG:-${LANG:-en}}"
locale="$(printf '%s' "$locale" | cut -c1-2 | tr 'A-Z' 'a-z')"
case "$locale" in en|fr|pt|ar|ur) ;; *) locale=en ;; esac

case "$locale" in
    fr) BANNER_TITLE="E156 Ecosystem Starter -- prêt à utiliser"
        BANNER_INSTALLED="Ce qui vient d'être installé dans ce codespace :"
        BANNER_NEXT="UNE COMMANDE POUR DÉMARRER -- ceci lance votre agent IA avec le briefing :"
        BANNER_HOW="Tapez simplement :"
        BANNER_BROWSE="Pour lire le briefing avant : ~/.config/e156/handoff.md (visible dans l'explorateur de fichiers)" ;;
    pt) BANNER_TITLE="E156 Ecosystem Starter -- pronto para usar"
        BANNER_INSTALLED="O que acabou de ser instalado neste codespace:"
        BANNER_NEXT="UM COMANDO PARA INICIAR -- isto lança o seu agente de IA com o briefing:"
        BANNER_HOW="Basta escrever:"
        BANNER_BROWSE="Para ler o briefing antes: ~/.config/e156/handoff.md (visível no explorador de ficheiros)" ;;
    ar) BANNER_TITLE="E156 Ecosystem Starter -- جاهز للاستخدام"
        BANNER_INSTALLED="ما تم تثبيته للتو في هذا الـ codespace:"
        BANNER_NEXT="أمر واحد للبدء -- هذا يُشغِّل وكيل الذكاء الاصطناعي مع المُلخَّص:"
        BANNER_HOW="فقط اكتب:"
        BANNER_BROWSE="لقراءة المُلخَّص أولاً: ~/.config/e156/handoff.md (مرئي في مستكشف الملفات)" ;;
    ur) BANNER_TITLE="E156 Ecosystem Starter -- استعمال کے لیے تیار"
        BANNER_INSTALLED="ابھی اس codespace میں جو انسٹال ہوا ہے:"
        BANNER_NEXT="شروع کرنے کے لیے ایک کمانڈ -- یہ بریفنگ کے ساتھ آپ کا AI ایجنٹ چلاتی ہے:"
        BANNER_HOW="بس یہ ٹائپ کریں:"
        BANNER_BROWSE="بریفنگ پہلے پڑھنا چاہتے ہیں؟ دیکھیں ~/.config/e156/handoff.md (فائل ایکسپلورر میں نظر آتا ہے)" ;;
    *)  BANNER_TITLE="E156 Ecosystem Starter -- ready to use"
        BANNER_INSTALLED="What just got installed in this codespace:"
        BANNER_NEXT="ONE COMMAND TO START -- this runs your AI agent with the install briefing:"
        BANNER_HOW="Just type:"
        BANNER_BROWSE="Want to read the briefing first? See ~/.config/e156/handoff.md (visible in the file explorer)" ;;
esac

echo
echo "====================================================="
echo "  $BANNER_TITLE"
echo "====================================================="
echo
echo "$BANNER_INSTALLED"

# Plain-English labels: each line says what the component DOES, not just
# what it is. P1-U3 from user-POV review: a first-year medical student
# does not have a mental model for "HMAC key" or "pre-push hook".
file_present "$HOME/.claude/rules/rules.md"           "Rules pack          - your AI agent reads these to follow the E156 method"
file_present "$HOME/.claude/memory/MEMORY.md"         "Memory scaffold     - what your AI agent remembers between sessions"
file_present "$HOME/code/my-first-repo/.git/hooks/pre-push" "Sentinel guard      - checks code for 20 common mistakes before saving to GitHub"
file_present "$HOME/.config/e156/truthcert-hmac-key"  "TruthCert key       - signs your finished paper so it can't be tampered with"
file_present "$HOME/code/ProjectIndex/INDEX.md"       "ProjectIndex        - keeps a list of all your projects in one file"
have overmind "Overmind"     "checks tests + smoke + numerical baselines, gives a PASS/FAIL verdict"
have sentinel "Sentinel"     "command for running quality scans on demand"
have gemini   "Gemini CLI"   "free AI agent (sign in with Google) — your install partner"
have claude   "Claude Code"  "paid AI agent (needs API key) — alternative to Gemini"

echo
echo "$BANNER_NEXT"
echo
echo "      e156 start"
echo
echo "$BANNER_HOW  e156 start  (Gemini, free, Google sign-in)"
echo "                 e156 start --claude  (Claude Code, needs ANTHROPIC_API_KEY)"
echo
echo "$BANNER_BROWSE"
echo
echo "====================================================="
echo
