# Attribution

## Upstream project

The artwork in `pack/` and `vendor/material-icon-theme/icons/` is derived from the
**Material Icon Theme** for Visual Studio Code:

- Project: <https://github.com/material-extensions/vscode-material-icon-theme>
- Pinned version: **v5.39.0** (see `upstream.lock.json`)
- Copyright: Material Extensions
- License: MIT

`vendor/material-icon-theme/` contains an unmodified subset of that project: `icons/*.svg`,
`src/core/icons/fileIcons.ts`, `src/core/icons/folderIcons.ts` and `package.json`. It exists
so this repository can be built offline.

## This project

- The generator (`scripts/build.py`), validation, packaging and documentation: MIT, see
  `LICENSE`.
- The rendered packs under `pack/` are derivative works of the upstream artwork and are
  distributed under the same MIT terms.

## Trademarks

One Commander is a product of its respective owner. Material Design is a design language by
Google. This project is not affiliated with, endorsed by, or sponsored by either of them.
