# Attribution

The artwork in this repository is not original to this project. This file records where it
comes from and which terms apply; the full legal texts live in [`LICENSES/`](LICENSES/).

## Summary

| Part | Origin | License |
| --- | --- | --- |
| `vendor/material-icon-theme/` — SVGs, the two TypeScript definition files, `package.json` | Material Icon Theme **v5.39.0** | MIT, © Material Extensions |
| `pack/**` — 403 file-icon PNGs + 925 folder-icon PNGs (512×512) + 1 default folder icon (64×64) | rendered from the SVGs above | MIT, © Material Extensions — derivative work, see below |
| `scripts/`, `mappings/`, `docs/`, `.github/`, this file | this project | MIT, © PakerYu (`LICENSE`) |

## Upstream project

- Project: <https://github.com/material-extensions/vscode-material-icon-theme>
- Pinned version: **v5.39.0** (see `upstream.lock.json`)
- Copyright: Material Extensions
- License: MIT — full text in [`LICENSES/material-icon-theme-MIT.txt`](LICENSES/material-icon-theme-MIT.txt)

`vendor/material-icon-theme/` contains an unmodified subset of that project so this
repository can be built offline. It keeps its own `LICENSE` file; `LICENSES/` holds the copy
that travels with releases, and `make notices` fails if the two ever diverge.

## The rendered pack is a derivative work

Every PNG under `pack/` is a raster of an upstream SVG — same geometry, same colours, only
the resolution and the file name change. That makes the pack a derivative work of the
upstream artwork, so it is distributed under the upstream MIT terms as well: the copyright
line and the permission text must accompany every copy. That is why `LICENSE`,
`ATTRIBUTION.md` and `LICENSES/material-icon-theme-MIT.txt` sit in the repository root, in
every release archive, and are checked by `make notices` before a zip is accepted.

## This project's own work

The generator (`scripts/build.py`), validation, packaging, CI and documentation are original
work of this project and are MIT licensed through the second copyright line in `LICENSE`.

## Third-party names and logos

A number of icons identify third-party products and carry their logos (Visual Studio Code,
React, Docker, Adobe, JetBrains, …). Those names and logos are trademarks of their respective
owners and are used here only to identify file types and folders — the MIT license covers the
artwork as distributed, it does not grant any trademark rights.

One Commander is a product of its respective owner. Material Design is a design language by
Google. This project is not affiliated with, endorsed by, or sponsored by any of them; the
name is used descriptively to say which file manager the pack is formatted for.

## Keeping this file accurate

`make notices` re-checks everything above. When you bump the pinned upstream, run
`make licenses` to refresh `LICENSES/` from `vendor/` and review the diff.
