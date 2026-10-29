# How One Commander picks an icon

One Commander does not use a manifest. It scans the pack directory and derives the
association **from the file name**:

```
Resources/FileIcons/MaterialIconTheme/
├── py,pyw.png            → files ending in .py or .pyw
├── ts,tsx.png            → .ts, .tsx
├── gitignore.png         → the dot-file .gitignore
└── Thumbnail.png         → pack preview shown in Settings → Theme

Resources/FolderIcons/MaterialIconTheme/
├── src.png               → any folder named "src"
├── reducers.png          → folders named "reducers"
└── Thumbnail.png
```

## Consequences for the generator

| Constraint | Where it is handled |
| --- | --- |
| File name length ≤ 100 | `--max-name-len`, tokens are chunked into several identical PNGs |
| File name must be valid on NTFS | ASCII only, no `\ / : * ? " < > \|` |
| Windows device names are illegal | `con`, `prn`, `aux`, `nul`, `com1…9`, `lpt1…9` dropped |
| Matching is case-insensitive | folder names are lower-cased before mapping |
| Missing icons fall back to the built-in set | every Material icon that has no usable token is skipped and reported |

## Size and previews

- Icons are rendered at **512×512**. One Commander rescales on the fly and caches the results
  in numeric subdirectories (`16/`, `20/`, `24/` …) next to the pack — those are ignored by
  git and by `make clean`.
- `Thumbnail.png` must be **420×280**; it is what the Settings dialog shows for the pack.
  `scripts/build.py` builds it with ImageMagick from six representative icons
  (`--thumbnail-icons`).

## Installing by hand

```
<OneCommander>/
└── Resources/
    ├── FileIcons/
    │   └── MaterialIconTheme/
    └── FolderIcons/
        └── MaterialIconTheme/
```

Restart One Commander (or reopen Settings) and the pack appears in **Settings → Theme**.

`scripts/install.ps1` automates the copy, keeps the previous pack as
`MaterialIconTheme.bak`, and supports `-DryRun`. `scripts/uninstall.ps1` reverses it.

## Troubleshooting

- **Pack does not appear in the dropdown** — the folder must be
  `Resources\FileIcons\MaterialIconTheme` (the pack name is the directory name); reopen the
  Settings dialog.
- **Icons look stale after a rebuild** — delete the numeric cache directories inside the
  two pack folders, or run `make clean` before copying.
- **A file type uses the wrong icon** — check the row in `mappings/file-icons.tsv`; the
  first claim wins, so a more specific icon may need to be moved earlier in the definitions.
