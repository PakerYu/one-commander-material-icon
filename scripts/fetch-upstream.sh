#!/usr/bin/env bash
# Refresh vendor/material-icon-theme from the tag pinned in upstream.lock.json.
#
#   ./scripts/fetch-upstream.sh [--ref TAG] [--force]
#
# Only the parts the build needs are kept: icons/*.svg, src/core/icons/*.ts and
# package.json. The generated default icons (folder.svg, folder-root.svg) are not
# in the git tag; if already present in vendor/ they are preserved across refreshes.
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

# folder.svg / folder-root.svg are upstream's default folder icons. They are generated
# during the npm build and are not committed to the git tag, so the tarball above does not
# contain them. Keep the copies already in vendor/ (or the MainFolderIcon build breaks);
# this script never downloads them itself.
mkdir -p "$TMP/keep"
for icon in folder folder-root; do
  if [ -f "$DEST/icons/$icon.svg" ]; then
    cp "$DEST/icons/$icon.svg" "$TMP/keep/$icon.svg"
  fi
done

rm -rf "$DEST"
mkdir -p "$DEST/src/core/icons" "$DEST/icons"
cp "$SRC"/icons/*.svg "$DEST/icons/"
cp "$SRC"/src/core/icons/fileIcons.ts "$SRC"/src/core/icons/folderIcons.ts "$DEST/src/core/icons/"
cp "$SRC"/package.json "$SRC"/LICENSE "$DEST/" 2>/dev/null || cp "$SRC"/package.json "$DEST/"
for icon in folder folder-root; do
  if [ -f "$TMP/keep/$icon.svg" ] && [ ! -f "$DEST/icons/$icon.svg" ]; then
    cp "$TMP/keep/$icon.svg" "$DEST/icons/$icon.svg"
    echo "kept generated default icon: icons/$icon.svg"
  fi
done
echo "vendored $REF -> $DEST ($(find "$DEST" -type f | wc -l) files)"
echo "next: make check && make build"
