#!/usr/bin/env bash
# Refresh vendor/material-icon-theme from the tag pinned in upstream.lock.json.
#
#   ./scripts/fetch-upstream.sh [--ref TAG] [--force]
#
# Only the parts the build needs are kept: icons/*.svg, src/core/icons/*.ts and
# package.json.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
DEST="$REPO/vendor/material-icon-theme"
LOCK="$REPO/upstream.lock.json"
REF=""
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="${2:?--ref needs a tag}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$REF" ]; then
  REF="$(python3 -c "import json;print(json.load(open('$LOCK'))['tag'])")"
fi

if [ -d "$DEST" ] && [ "$FORCE" = 0 ]; then
  echo "$DEST already exists (use --force to refetch)"
  exit 0
fi

echo "fetching $REF"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://codeload.github.com/material-extensions/vscode-material-icon-theme/tar.gz/refs/tags/$REF" \
  -o "$TMP/upstream.tar.gz"
tar -xzf "$TMP/upstream.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'vscode-material-icon-theme-*' | head -1)"
[ -n "$SRC" ] || { echo "unexpected archive layout" >&2; exit 1; }

rm -rf "$DEST"
mkdir -p "$DEST/src/core/icons" "$DEST/icons"
cp "$SRC"/icons/*.svg "$DEST/icons/"
cp "$SRC"/src/core/icons/fileIcons.ts "$SRC"/src/core/icons/folderIcons.ts "$DEST/src/core/icons/"
cp "$SRC"/package.json "$SRC"/LICENSE "$DEST/" 2>/dev/null || cp "$SRC"/package.json "$DEST/"
echo "vendored $REF -> $DEST ($(find "$DEST" -type f | wc -l) files)"
echo "next: make check && make build"
