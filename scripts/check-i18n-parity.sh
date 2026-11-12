#!/usr/bin/env bash
# check-i18n-parity.sh -- structural parity check between English landing
# page and the i18n variants (fr, pt, ar, ur).
#
# Why this exists: the 2026-04-27 user-POV fix bundle shipped four new
# <details> blocks on the English page and forgot to add them to the
# four i18n pages. Non-English students got a strict regression. This
# check makes that class of failure a CI-blocking error instead of
# something that escapes to production.
#
# What it checks: the count of <details> blocks in each i18n page must
# equal the count in the English page. (We don't validate translation
# quality — that's a human review concern. We only validate structural
# parity: if EN has N expandable sections, the others must too.)
#
# Usage:
#   ./scripts/check-i18n-parity.sh        # run check, exit 1 on drift
#   ./scripts/check-i18n-parity.sh --report   # just print the count table
#
# Exit codes:
#   0 - parity holds
#   1 - one or more i18n pages out of parity with English
#   2 - input pages missing

set -u

REPORT_ONLY=0
case "${1:-}" in
    --report) REPORT_ONLY=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
en="$repo_root/docs/index.html"
declare -a langs=(fr pt ar ur sw)

[[ -f "$en" ]] || { echo "ERROR: English page missing at $en" >&2; exit 2; }

# Count <details> openings (not closings, in case they ever go on the same line).
count_details() {
    grep -c '<details' "$1" 2>/dev/null || echo 0
}

en_count="$(count_details "$en")"

printf '%-10s %s\n' "lang" "<details> count"
printf '%-10s %s\n' "----" "----"
printf '%-10s %d  (reference)\n' "en" "$en_count"

drift=0
for lang in "${langs[@]}"; do
    page="$repo_root/docs/$lang/index.html"
    if [[ ! -f "$page" ]]; then
        printf '%-10s MISSING (%s)\n' "$lang" "$page"
        drift=1
        continue
    fi
    n="$(count_details "$page")"
    if [[ "$n" -ne "$en_count" ]]; then
        printf '%-10s %d  *** drift (en has %d) ***\n' "$lang" "$n" "$en_count"
        drift=1
    else
        printf '%-10s %d\n' "$lang" "$n"
    fi
done

if [[ "$REPORT_ONLY" -eq 1 ]]; then
    exit 0
fi

if [[ "$drift" -eq 1 ]]; then
    echo
    echo "FAIL: i18n pages out of parity with English." >&2
    echo "Either port the missing <details> sections to the i18n pages, or" >&2
    echo "update this check if a structural divergence is intentional." >&2
    exit 1
fi
echo
echo "OK: all i18n pages match English structure."
