#!/usr/bin/env bash
# Build the distributable zip:
#   dist/MaterialIconTheme-<version>.zip  (+ dist/SHA256SUMS)
#
# Layout inside the archive mirrors the repository:
#   FileIcons/MaterialIconTheme/…      <- copy to <OneCommander>/Resources/FileIcons/
#   FolderIcons/MaterialIconTheme/…    <- copy to <OneCommander>/Resources/FolderIcons/
#   MainFolderIcon/MaterialIconTheme.png
#                                      <- copy to <OneCommander>/Resources/MainFolderIcon/
#   mappings/  README.md  README.zh-CN.md  CHANGELOG.md  pack.json
#   LICENSE  ATTRIBUTION.md  LICENSES/material-icon-theme-MIT.txt
#
# The pack is a derivative work of MIT-licensed artwork, so the copyright line and the
# permission text have to accompany the copy a user downloads. The notices are therefore
# part of the archive, and scripts/check-notices.sh re-opens the finished zip and refuses it
# when anything is missing.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
VERSION="$(cat "$REPO/VERSION")"
OUT="$REPO/dist/MaterialIconTheme-$VERSION.zip"
PACK="$REPO/pack"

[ -d "$PACK/FileIcons" ] || { echo "run 'make build' first (pack/ is missing)" >&2; exit 1; }
[ -d "$PACK/MainFolderIcon" ] || { echo "run 'make build' first (pack/MainFolderIcon is missing)" >&2; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "zip is required" >&2; exit 1; }

"$HERE/check-notices.sh"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -a "$PACK/FileIcons" "$STAGE/FileIcons"
cp -a "$PACK/FolderIcons" "$STAGE/FolderIcons"
cp -a "$PACK/MainFolderIcon" "$STAGE/MainFolderIcon"
cp -a "$REPO/mappings" "$STAGE/mappings"
cp -a "$REPO/LICENSES" "$STAGE/LICENSES"
for f in README.md README.zh-CN.md CHANGELOG.md LICENSE ATTRIBUTION.md; do
  if [ -f "$REPO/$f" ]; then
    cp "$REPO/$f" "$STAGE/$f"
  fi
done
# provenance: the build manifest is optional here because package.sh also runs in CI
# without a full re-render
if [ -f "$REPO/dist/pack.json" ]; then
  cp "$REPO/dist/pack.json" "$STAGE/pack.json"
fi

mkdir -p "$REPO/dist"
rm -f "$OUT"
( cd "$STAGE" && zip -r -X -q "$OUT" . )

# re-open the archive: what matters is what the user downloads, not what we staged
"$HERE/check-notices.sh" --zip "$OUT"

( cd "$REPO/dist" && sha256sum "$(basename "$OUT")" > SHA256SUMS )

echo "wrote $OUT"
echo "wrote $REPO/dist/SHA256SUMS"
echo "contents:"
unzip -l "$OUT" | tail -n 3
