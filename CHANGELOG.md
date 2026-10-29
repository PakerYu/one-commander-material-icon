# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The upstream icon set is tracked separately: the version in parentheses is the pinned
`vscode-material-icon-theme` release from `upstream.lock.json`.

## [Unreleased]

## [1.0.0] - 2025-10-29 (upstream 5.39.0)

### Added

- One Commander icon pack `MaterialIconTheme` generated from Material Icon Theme 5.39.0:
  403 file icons covering 1308 extension/file tokens and 925 folder icons, all at 512×512,
  plus two 420×280 `Thumbnail.png` previews.
- Deterministic mapping tables committed under `mappings/` (`file-icons.tsv`,
  `folder-icons.tsv`) with drift detection (`make check`).
- `scripts/build.py` with renderer auto-detection (inkscape / rsvg-convert / cairosvg /
  imagemagick / copy), Inkscape `--shell` batching, serial retries, `--limit` smoke mode and
  a `dist/pack.json` build manifest.
- `scripts/verify.py`: PNG dimensions, filename length, Windows reserved names, thumbnail
  size, mapping ↔ file consistency, manifest counts.
- Offline build via the vendored upstream subset in `vendor/material-icon-theme/`.
- PowerShell `install.ps1` / `uninstall.ps1` with `-DryRun` and `.bak` rollback.
- GitHub Actions CI (mapping drift + pack validation) and a tag-driven release that
  attaches `MaterialIconTheme-<version>.zip`.

### Notes

- Icons that only exist as generated clones upstream (`nest-*`, `angular-*`, `advpl-*`, …)
  are skipped and listed in the build manifest.
- File names are capped at 100 characters; longer extension lists are split into several
  identical PNGs, matching One Commander's own limit.
