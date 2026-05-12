#!/usr/bin/env bash
# e156-setup.sh -- one-command installer for the E156 ecosystem starter on Linux/macOS.
#
# The bash parallel of bootstrap/e156-setup.bat. Paste the one-liner on the
# landing page, or download and run. No admin / sudo required.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/mahmood726-cyber/e156-ecosystem-starter/main/bootstrap/e156-setup.sh | bash
#
# Or download and run with options:
#   ./e156-setup.sh --full        # chain Sentinel + Overmind + ProjectIndex
#   ./e156-setup.sh --ref v0.7.0  # pin to a release

set -euo pipefail

REF="${REF:-main}"
FULL_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ref)   REF="$2"; shift 2 ;;
        --full)  FULL_FLAG="--full"; shift ;;
        -h|--help) grep -E '^#' "$0" | head -15; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

say() { printf '\n==> %s\n' "$1"; }

say "E156 Ecosystem Starter -- one-command installer"
echo
echo "This will install:"
echo "  - AI agent rules (Claude Code / Gemini CLI / Codex)"
echo "  - Memory scaffold (cross-session learning)"
echo "  - Sentinel pre-push hook (optional, 28 quality rules)"
echo "  - Overmind + TruthCert (optional, verifier + signed bundles)"
echo "  - ProjectIndex portfolio tracker (optional)"
echo
echo "Takes about 2 minutes. No sudo needed."
echo
if [[ -t 0 ]]; then
    read -r -p "Press Enter to start, or Ctrl+C to cancel: " _
fi

# Prerequisites
say "[1/4] Checking prerequisites"
command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || {
    echo "  ERROR: Python is not installed or not on PATH." >&2
    echo "  Install Python 3.11+ first:"
    echo "    - Ubuntu/Debian:  sudo apt install python3 python3-pip"
    echo "    - Fedora/RHEL:    sudo dnf install python3 python3-pip"
    echo "    - macOS (brew):   brew install python"
    exit 1
}
command -v python >/dev/null 2>&1 || alias python=python3
echo "  OK - Python: $(python --version 2>&1 || python3 --version)"
command -v unzip >/dev/null 2>&1 || {
    echo "  ERROR: unzip is not installed." >&2
    echo "  Install: sudo apt install unzip  (or the equivalent for your distro)"
    exit 1
}

# Download
say "[2/4] Downloading ecosystem-starter ($REF)"
WORK="$(mktemp -d -t e156-setup.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
ZIP="$WORK/e156.zip"
URL="https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/heads/${REF}.zip"
if [[ "$REF" =~ ^v[0-9] ]]; then
    URL="https://github.com/mahmood726-cyber/e156-ecosystem-starter/archive/refs/tags/${REF}.zip"
fi
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$URL" -o "$ZIP"
elif command -v wget >/dev/null 2>&1; then
    wget -q "$URL" -O "$ZIP"
else
    echo "  ERROR: neither curl nor wget available; cannot download." >&2
    exit 1
fi
echo "  OK - downloaded to $ZIP"

# Extract
say "[3/4] Extracting"
unzip -q "$ZIP" -d "$WORK"
# The extracted folder is named e156-ecosystem-starter-<ref> (tag strips v)
SUFFIX="$REF"
[[ "$REF" =~ ^v(.+)$ ]] && SUFFIX="${BASH_REMATCH[1]}"
EXTRACT_ROOT="$WORK/e156-ecosystem-starter-$SUFFIX"
if [[ ! -f "$EXTRACT_ROOT/install/install.sh" ]]; then
    echo "  ERROR: extracted layout unexpected. Expected $EXTRACT_ROOT/install/install.sh" >&2
    exit 1
fi
chmod +x "$EXTRACT_ROOT/install/install.sh" "$EXTRACT_ROOT/scripts"/*.sh 2>/dev/null || true
echo "  OK - extracted to $EXTRACT_ROOT"

# Run
say "[4/4] Running installer"
echo
(cd "$EXTRACT_ROOT" && bash install/install.sh $FULL_FLAG)
RC=$?

echo
echo "====================================================="
if [[ "$RC" -eq 0 ]]; then
    echo "  INSTALL COMPLETE"
    echo "  Next steps:"
    echo "    1. Run 'claude' or 'gemini' in any project folder"
    echo "    2. Rules + memory from this install are loaded automatically"
    echo "    3. If you answered Yes to Sentinel, every git push is gated"
else
    echo "  INSTALL FAILED (exit code $RC)"
    echo "  Scroll up to see what went wrong."
fi
echo "====================================================="
exit $RC
