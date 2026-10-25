#!/usr/bin/env bash
# install-meta-harness.sh -- OPTIONAL: fetch a published meta-harness release and
# verify it against the release's SHA256SUMS before unpacking anything.
#
# The meta-harness is NOT vendored into this starter. This script downloads the
# release asset named by a tag from github.com/mahmood726-cyber/meta-harness,
# checks its sha256 against the SHA256SUMS published beside it, and only then
# unpacks it. Fail-closed: a missing asset, a missing SHA256SUMS line or a
# digest mismatch stops before anything is unpacked. See docs/meta-harness.md.
#
# Usage:
#   ./scripts/install-meta-harness.sh                    # fetch v1.0.0 into ~/code/meta-harness-v1.0.0
#   ./scripts/install-meta-harness.sh --target <dir>
#   ./scripts/install-meta-harness.sh --ref v1.0.0
#   ./scripts/install-meta-harness.sh --import           # source for tests
#
# Env overrides: META_HARNESS_REF (tag), META_HARNESS_BASE_URL (release download
# base; tests point it at a local directory).

set -euo pipefail

TARGET=""
REF_ARG=""
IMPORT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --ref)    REF_ARG="$2"; shift 2 ;;
        --import) IMPORT=1; shift ;;
        -h|--help) grep -E '^#' "$0" | head -18; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# A REAL python (skip the Windows Store alias stub), as in the other installers.
PYTHON=""
for _cand in python3 python; do
    if command -v "$_cand" >/dev/null 2>&1; then
        case "$(command -v "$_cand")" in *WindowsApps*) continue ;; esac
        if "$_cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PYTHON="$_cand"; break; fi
    fi
done

META_HARNESS_DEFAULT_REF="v1.0.0"
# Independent starter-side trust anchor for the public v1.0.0 SHA256SUMS asset.
# Release assets are mutable: checking a ZIP against the co-hosted sums alone
# would not detect replacement of both. Review any change to this digest.
META_HARNESS_V1_MANIFEST_SHA256="3bf1d1f9eaa6f423f3130ca5f6413b05dcf2994833a9fce038e1ee8e9ad00ddb"
meta_harness_default_ref() { echo "${META_HARNESS_REF:-$META_HARNESS_DEFAULT_REF}"; }
meta_harness_asset_name() { echo "meta-harness-$1.zip"; }
meta_harness_base_url() {
    echo "${META_HARNESS_BASE_URL:-https://github.com/mahmood726-cyber/meta-harness/releases/download/$1}"
}
meta_harness_default_target() { echo "${HOME}/code/meta-harness-$1"; }

# The unpacked release is usable if it carries the offline replay entry point.
test_meta_harness_present() { [[ -n "$1" && -f "$1/scripts/replay_offline.py" ]]; }

meta_harness_sha256() {
    local output digest
    if command -v sha256sum >/dev/null 2>&1; then
        # Hash stdin, not a filename: GNU sha256sum prefixes its digest with
        # a backslash when a Windows-native path contains backslashes. Splitting
        # its filename-bearing output previously produced a false mismatch on
        # Windows Git Bash despite identical bytes.
        output="$(sha256sum < "$1")" || return 1
        digest="${output%% *}"
    else
        [[ -n "$PYTHON" ]] || { echo "REFUSED: no SHA256 tool available" >&2; return 1; }
        # Stream the published ~609 MB archive instead of allocating its full
        # contents in memory on hosts without sha256sum (including some Windows
        # setups). A missing/failed Python digest still refuses installation.
        digest="$("$PYTHON" -c 'import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], "rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
print(h.hexdigest())' "$1")" || return 1
    fi
    if [[ ! "$digest" =~ ^[0-9a-f]{64}$ ]]; then
        echo "REFUSED: invalid SHA256 tool output" >&2
        return 1
    fi
    printf '%s\n' "$digest"
}

# Verify the independently reviewed release manifest BEFORE downloading the ~609 MB ZIP.
# A custom local file:// release is permitted solely for isolated fixture tests;
# an unreviewed remote release must not be silently treated as authenticated.
verify_meta_harness_release_manifest() {
    local sums="$1" ref="$2" base="$3" actual
    if [[ "$ref" == "$META_HARNESS_DEFAULT_REF" ]]; then
        actual="$(meta_harness_sha256 "$sums")" || return 1
        if [[ "$actual" != "$META_HARNESS_V1_MANIFEST_SHA256" ]]; then
            echo "REFUSED: meta-harness v1.0.0 SHA256SUMS differs from reviewed pinned digest (actual: ${actual:-empty})" >&2
            return 1
        fi
        echo "  pinned meta-harness v1.0.0 SHA256SUMS OK"
    elif [[ "$base" == file://* ]]; then
        echo "  LOCAL TEST FIXTURE: unpinned release $ref (not an authenticated distribution)" >&2
    else
        echo "REFUSED: unreviewed meta-harness release ref '$ref'; no pinned SHA256SUMS trust anchor" >&2
        return 1
    fi
}

# Accept exactly one well-formed checksum record naming this asset.
# GNU binary-mode checksum lines (*filename) are supported. Fail closed when a
# matching record is malformed or repeated; never select the first of several.
meta_harness_expected_sha() {
    local sums="$1" name="$2" hash="" entry="" extra="" digest="" matches=0
    while read -r hash entry extra || [[ -n "${hash}${entry}${extra}" ]]; do
        [[ "$entry" == "$name" || "$entry" == "*$name" ]] || continue
        matches=$((matches + 1))
        if [[ "$matches" -gt 1 ]]; then
            echo "REFUSED: SHA256SUMS has multiple entries for $name" >&2; return 1
        fi
        if [[ ! "$hash" =~ ^[0-9a-f]{64}$ || -n "$extra" ]]; then
            echo "REFUSED: SHA256SUMS has malformed entry for $name" >&2; return 1
        fi
        digest="$hash"
    done < <(tr -d '\r' < "$sums")
    [[ "$matches" -eq 1 ]] || {
        echo "REFUSED: SHA256SUMS has no line for $name" >&2; return 1; }
    printf '%s\n' "$digest"
}

# Verify <zip> against <sums>. Prints the reason and returns 1 on any failure.
verify_meta_harness_asset() {
    local zip="$1" sums="$2" name expected actual
    name="$(basename "$zip")"
    expected="$(meta_harness_expected_sha "$sums" "$name")" || return 1
    actual="$(meta_harness_sha256 "$zip")"
    [[ "$actual" == "$expected" ]] || {
        echo "REFUSED: sha256 mismatch for $name (expected $expected, got $actual)" >&2; return 1; }
    echo "  sha256 OK: $actual  $name"
}

fetch_url() {
    local url="$1" out="$2" attempt
    for attempt in 1 2 3; do
        if curl -fsSL --retry 2 -o "$out" "$url"; then return 0; fi
        [[ "$attempt" -lt 3 ]] && sleep $(( 2 ** attempt ))
    done
    echo "REFUSED: could not download $url" >&2; return 1
}

# Unpack with stdlib zipfile (no unzip dependency); the archive's single top-level
# folder becomes <target>.
unpack_meta_harness() {
    local zip="$1" target="$2"
    "$PYTHON" - "$zip" "$target" <<'PY'
import pathlib, re, shutil, stat, sys, tempfile, zipfile

zp, target = sys.argv[1], pathlib.Path(sys.argv[2])
if target.exists():
    if not target.is_dir() or any(target.iterdir()):
        sys.exit(f"REFUSED: {target} exists and is not empty")

# Validate the entire manifest before writing any extraction bytes. ZipFile's
# built-in path sanitisation is platform-dependent and can hide collisions.
with zipfile.ZipFile(zp) as z:
    infos = z.infolist()
    if not infos:
        sys.exit("REFUSED: empty meta-harness archive")
    seen = set()
    for info in infos:
        name = info.filename
        parts = name.rstrip("/").split("/")
        unsafe = (
            not name or name.startswith("/") or "\\" in name
            or any(not part or part in (".", "..") or ":" in part
                   or part.endswith((" ", ".")) for part in parts)
        )
        if unsafe:
            sys.exit(f"REFUSED: unsafe path in archive: {name}")
        folded = name.rstrip("/").casefold()
        if folded in seen:
            sys.exit(f"REFUSED: duplicate archive path (case-insensitive): {name}")
        seen.add(folded)
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            sys.exit(f"REFUSED: unsupported archive entry type: {name}")

    tops = {info.filename.split("/", 1)[0] for info in infos}
    root = next(iter(tops)) + "/" if len(tops) == 1 else ""
    entry = root + "scripts/replay_offline.py"
    if not any(i.filename == entry and not i.is_dir() for i in infos):
        sys.exit("REFUSED: scripts/replay_offline.py is missing from archive")

    # Extraction and entrypoint inspection take place in a private staging
    # directory on the same filesystem. Never publish a partial installation.
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=".meta-harness-stage-", dir=target.parent))
    try:
        z.extractall(tmp)
        src = tmp / root if root else tmp
        if not (src / "scripts" / "replay_offline.py").is_file():
            sys.exit("REFUSED: extracted scripts/replay_offline.py is missing")
        if target.exists():
            target.rmdir()  # empty target only; refuse concurrent modifications
        src.rename(target)  # atomic publication when on the same filesystem
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
PY
}

if [[ "$IMPORT" -eq 1 ]]; then
    return 0 2>/dev/null || exit 0
fi

# === Real flow =============================================================
[[ -n "$PYTHON" ]] || { echo "ERROR: python not found (needed to unpack and to run the harness)." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "ERROR: curl not found." >&2; exit 1; }

REF="${REF_ARG:-$(meta_harness_default_ref)}"
ASSET="$(meta_harness_asset_name "$REF")"
BASE="$(meta_harness_base_url "$REF")"
[[ -n "$TARGET" ]] || TARGET="$(meta_harness_default_target "$REF")"

echo
echo "meta-harness release fetch (optional layer; nothing is vendored into the starter)"
echo "==> release $REF: $BASE/$ASSET"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
fetch_url "$BASE/SHA256SUMS" "$work/SHA256SUMS"
verify_meta_harness_release_manifest "$work/SHA256SUMS" "$REF" "$BASE"
fetch_url "$BASE/$ASSET" "$work/$ASSET"

echo "==> verifying against the release's SHA256SUMS"
verify_meta_harness_asset "$work/$ASSET" "$work/SHA256SUMS"

echo "==> unpacking into $TARGET"
mkdir -p "$(dirname "$TARGET")"
unpack_meta_harness "$work/$ASSET" "$TARGET"
test_meta_harness_present "$TARGET" || {
    echo "REFUSED: unpacked, but $TARGET/scripts/replay_offline.py is missing." >&2; exit 1; }

echo
echo "====================================================="
echo "  meta-harness $REF unpacked at $TARGET (sha256 verified)"
echo "  This is a download without git history: replay a review OFFLINE with"
echo "    cd \"$TARGET\""
echo "    python -m pip install --require-hashes -r docs/offline/requirements.lock"
echo "    python scripts/replay_offline.py dpp4-mace-t2d"
echo "  (scripts/reproduce_review.py needs a git clone -- see docs/meta-harness.md.)"
echo "====================================================="
