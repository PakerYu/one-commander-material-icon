#!/usr/bin/env bash
# Verify the legal notices that have to travel with this pack.
#
#   ./scripts/check-notices.sh
#   ./scripts/check-notices.sh --zip dist/MaterialIconTheme-<version>.zip
#
# Checks
# ------
# 1. LICENSE is MIT and carries both the upstream and the project copyright line.
# 2. LICENSES/material-icon-theme-MIT.txt is byte-identical to the vendored upstream
#    LICENSE, so the text that ships can never drift from the text we inherited.
# 3. ATTRIBUTION.md still explains scope, licenses and trademarks.
# 4. dist/pack.json (when present) declares the same license.
# 5. --zip: the archive itself contains the notices and at least one icon, i.e. the copy a
#    user downloads is self-describing (MIT: the notice must accompany every copy).
#
# Exit code 0 means the notices are publishable.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

ZIP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --zip) ZIP="${2:?--zip needs a path}"; shift 2 ;;
    -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

LICENSE="$REPO/LICENSE"
ATTRIBUTION="$REPO/ATTRIBUTION.md"
NOTICE="$REPO/LICENSES/material-icon-theme-MIT.txt"
VENDOR_LICENSE="$REPO/vendor/material-icon-theme/LICENSE"
MANIFEST="$REPO/dist/pack.json"

fails=0
pass() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; fails=$((fails + 1)); }

has() { grep -qF -- "$2" "$1"; }

echo "notices:"

# -- 1. LICENSE ------------------------------------------------------------ #
if [ ! -f "$LICENSE" ]; then
  fail "LICENSE is missing"
else
  has "$LICENSE" "The MIT License (MIT)" && pass "LICENSE is MIT" || fail "LICENSE has no MIT title"
  if has "$LICENSE" "Permission is hereby granted, free of charge"; then
    pass "LICENSE carries the permission text"
  else
    fail "LICENSE is missing the MIT permission text"
  fi
  if has "$LICENSE" "WITHOUT WARRANTY OF ANY KIND"; then
    pass "LICENSE carries the warranty disclaimer"
  else
    fail "LICENSE is missing the warranty disclaimer"
  fi
  has "$LICENSE" "Copyright (c) 2025 Material Extensions" \
    && pass "LICENSE keeps the upstream copyright line" \
    || fail "LICENSE lost the upstream copyright line (Material Extensions)"
  lines=$(grep -cE '^Copyright \(c\) [0-9]{4} ' "$LICENSE" || true)
  if [ "${lines:-0}" -ge 2 ]; then
    pass "LICENSE lists this project's copyright too"
  else
    fail "LICENSE has no copyright line of its own (expected 2, found ${lines:-0})"
  fi
fi

# -- 2. upstream notice ---------------------------------------------------- #
if [ ! -f "$NOTICE" ]; then
  fail "LICENSES/material-icon-theme-MIT.txt is missing"
elif [ ! -f "$VENDOR_LICENSE" ]; then
  fail "vendor/material-icon-theme/LICENSE is missing (run 'make vendor')"
elif cmp -s "$NOTICE" "$VENDOR_LICENSE"; then
  pass "LICENSES/material-icon-theme-MIT.txt matches the vendored license"
else
  fail "LICENSES/material-icon-theme-MIT.txt drifted from vendor/material-icon-theme/LICENSE"
fi

# -- 3. attribution -------------------------------------------------------- #
if [ ! -f "$ATTRIBUTION" ]; then
  fail "ATTRIBUTION.md is missing"
else
  has "$ATTRIBUTION" "Material Extensions" && pass "ATTRIBUTION names the upstream copyright holder" \
    || fail "ATTRIBUTION does not name the upstream copyright holder"
  has "$ATTRIBUTION" "LICENSES/material-icon-theme-MIT.txt" \
    && pass "ATTRIBUTION points at the upstream license text" \
    || fail "ATTRIBUTION does not point at LICENSES/material-icon-theme-MIT.txt"
  if grep -qFi "trademark" "$ATTRIBUTION"; then
    pass "ATTRIBUTION covers third-party trademarks"
  else
    fail "ATTRIBUTION has no trademark section"
  fi
  has "$ATTRIBUTION" "not affiliated" && pass "ATTRIBUTION carries the non-affiliation statement" \
    || fail "ATTRIBUTION is missing the non-affiliation statement"
fi

# -- 4. build manifest ----------------------------------------------------- #
if [ -f "$MANIFEST" ]; then
  if python3 - "$MANIFEST" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
license_info = manifest.get("license") or {}
raise SystemExit(0 if license_info.get("spdx") == "MIT" else 1)
PY
  then
    pass "dist/pack.json declares MIT"
  else
    fail "dist/pack.json does not declare license.spdx = MIT (re-run 'make build')"
  fi
fi

# -- 5. release archive ---------------------------------------------------- #
if [ -n "$ZIP" ]; then
  if [ ! -f "$ZIP" ]; then
    fail "archive $ZIP does not exist"
  else
    if ! command -v zipinfo >/dev/null 2>&1 && ! command -v unzip >/dev/null 2>&1; then
      fail "neither zipinfo nor unzip is available to inspect $ZIP"
    else
      entries=$( (command -v zipinfo >/dev/null 2>&1 && zipinfo -1 "$ZIP") || unzip -Z1 "$ZIP")
      for required in LICENSE ATTRIBUTION.md LICENSES/material-icon-theme-MIT.txt; do
        if grep -qxF "$required" <<<"$entries"; then
          pass "archive ships $required"
        else
          fail "archive is missing $required"
        fi
      done
      if grep -qE '^(FileIcons|FolderIcons)/MaterialIconTheme/.+\.png$' <<<"$entries"; then
        pass "archive carries the icon pack"
      else
        fail "archive carries no PNG icons"
      fi
    fi
  fi
fi

echo
if [ "$fails" -gt 0 ]; then
  echo "$fails notice check(s) failed" >&2
  exit 1
fi
echo "all notice checks passed"
