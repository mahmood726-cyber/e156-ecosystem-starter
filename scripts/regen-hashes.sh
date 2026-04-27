#!/usr/bin/env bash
# regen-hashes.sh -- recompute docs/HASH.txt and docs/HASH-linux.txt to
# match the SHA-256 of install/install.ps1 and install/install.sh.
#
# Run this whenever you edit either install script. CI also runs it in
# --check mode (verify-only, no write) and fails if the recorded hash
# does not match the actual install-script SHA -- catching the latent
# "stale HASH.txt breaks fresh installs" bug at PR time.
#
# Usage:
#   ./scripts/regen-hashes.sh              # write mode (default)
#   ./scripts/regen-hashes.sh --check      # verify-only; exit 1 on drift
#   ./scripts/regen-hashes.sh -h           # help

set -u

CHECK_ONLY=0
case "${1:-}" in
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    "") ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ps1="$repo_root/install/install.ps1"
sh="$repo_root/install/install.sh"
ps1_hash_file="$repo_root/docs/HASH.txt"
sh_hash_file="$repo_root/docs/HASH-linux.txt"

for f in "$ps1" "$sh"; do
    [[ -f "$f" ]] || { echo "ERROR: missing $f" >&2; exit 1; }
done

ps1_actual="$(sha256sum "$ps1" | awk '{print $1}')"
sh_actual="$(sha256sum "$sh"  | awk '{print $1}')"

# Read recorded hashes, stripping BOM (Get-FileHash via PowerShell sometimes
# writes a UTF-8 BOM) and any trailing whitespace.
strip_bom() { sed '1s/^\xef\xbb\xbf//'; }
ps1_recorded="$(strip_bom < "$ps1_hash_file" | tr -d '[:space:]')"
sh_recorded="$(strip_bom  < "$sh_hash_file"  | tr -d '[:space:]')"

drift=0
if [[ "$ps1_actual" != "$ps1_recorded" ]]; then
    drift=1
    printf 'DRIFT: install.ps1\n  expected: %s\n  recorded: %s\n' "$ps1_actual" "$ps1_recorded"
fi
if [[ "$sh_actual" != "$sh_recorded" ]]; then
    drift=1
    printf 'DRIFT: install.sh\n  expected: %s\n  recorded: %s\n' "$sh_actual" "$sh_recorded"
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
    if [[ "$drift" -eq 1 ]]; then
        echo
        echo "FAIL: HASH files out of sync with install scripts." >&2
        echo "Fix: bash scripts/regen-hashes.sh" >&2
        exit 1
    fi
    echo "OK: HASH files match install scripts."
    exit 0
fi

# Write mode
printf '%s' "$ps1_actual" > "$ps1_hash_file"
printf '%s' "$sh_actual"  > "$sh_hash_file"
if [[ "$drift" -eq 1 ]]; then
    echo "Updated docs/HASH.txt and docs/HASH-linux.txt."
else
    echo "Already in sync; no changes."
fi
