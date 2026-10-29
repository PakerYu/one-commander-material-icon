#!/usr/bin/env bash
# Build the distributable zip:
#   dist/MaterialIconTheme-<version>.zip
#
# Layout inside the archive mirrors the repository:
#   FileIcons/MaterialIconTheme/…      <- copy to <OneCommander>/Resources/FileIcons/
#   FolderIcons/MaterialIconTheme/…    <- copy to <OneCommander>/Resources/FolderIcons/
#   mappings/  README.md  README.zh-CN.md  LICENSE  ATTRIBUTION.md
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
VERSION="$(cat "$REPO/VERSION")"
OUT="$REPO/dist/MaterialIconTheme-$VERSION.zip"
PACK="$REPO/pack"

[ -d "$PACK/FileIcons" ] || { echo "run 'make build' first (pack/ is missing)" >&2; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "zip is required" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -a "$PACK/FileIcons" "$STAGE/FileIcons"
cp -a "$PACK/FolderIcons" "$STAGE/FolderIcons"
cp -a "$REPO/mappings" "$STAGE/mappings"
for f in README.md README.zh-CN.md LICENSE ATTRIBUTION.md; do
  [ -f "$REPO/$f" ] && cp "$REPO/$f" "$STAGE/$f"
done

mkdir -p "$REPO/dist"
rm -f "$OUT"
( cd "$STAGE" && zip -r -X -q "$OUT" . )
echo "wrote $OUT"
echo "contents:"
unzip -l "$OUT" | tail -n 3
