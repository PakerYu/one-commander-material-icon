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

Resources/MainFolderIcon/
└── MaterialIconTheme.png → the default folder icon (Settings → Theme)
```

`MainFolderIcon` is a separate, shared directory: One Commander lists every PNG directly
inside it in the **Default folder icon** dropdown. The file name is the label, and unlike the
folder pack there is no per-name association.

## Consequences for the generator

| Constraint | Where it is handled |
| --- | --- |
| File name length ≤ 100 | `--max-name-len`, tokens are chunked into several identical PNGs |
| File name must be valid on NTFS | ASCII only, no `\ / : * ? " < > \|` |
| Windows device names are illegal | `con`, `prn`, `aux`, `nul`, `com1…9`, `lpt1…9` dropped |
| Matching is case-insensitive | folder names are lower-cased before mapping |
| Missing icons fall back to the built-in set | every Material icon that has no usable token is skipped and reported |
| Default folder icon is not a pack | `MainFolderIcon` is one PNG directly under `Resources\MainFolderIcon\` |

## Default folder icon (`MainFolderIcon`)

Folders whose name has no row in `mappings/folder-icons.tsv` use the icon selected under
**Settings → Theme → Default folder icon**. One Commander scans `Resources\MainFolderIcon\`
for PNGs and shows each file name in that dropdown; it is independent of
`Resources\FolderIcons\MaterialIconTheme`.

`scripts/build.py` renders the pack's entry from the upstream default `icons/folder.svg`
(plain blue-grey Material folder) into:

```
pack/MainFolderIcon/MaterialIconTheme.png   # 64×64, transparent
```

Copy that single file — not the directory — into `<OneCommander>\Resources\MainFolderIcon\`.
The label in the dropdown is the file stem, `MaterialIconTheme`.

## Size and previews

- Pack icons are rendered at **512×512**. One Commander rescales on the fly and caches the
  results in numeric subdirectories (`16/`, `20/`, `24/` …) next to the pack — those are
  ignored by git and by `make clean`.
- `MainFolderIcon/MaterialIconTheme.png` is rendered at **64×64**; One Commander scales it
  for the folder pane like the built-in default icons.
- `Thumbnail.png` must be **420×280**; it is what the Settings dialog shows for the pack.
  `scripts/build.py` builds it with ImageMagick from six representative icons
  (`--thumbnail-icons`).

## Installing by hand

```
<OneCommander>/
└── Resources/
    ├── FileIcons/
    │   └── MaterialIconTheme/
    ├── FolderIcons/
    │   └── MaterialIconTheme/
    └── MainFolderIcon/
        └── MaterialIconTheme.png
```

Restart One Commander (or reopen Settings) and the pack appears in **Settings → Theme**;
`MaterialIconTheme` is also listed under **Default folder icon**.

`scripts/install.ps1` automates the copy, keeps the previous pack as
`MaterialIconTheme.bak` / `MaterialIconTheme.png.bak`, and supports `-DryRun`.
`scripts/uninstall.ps1` reverses it.

## Troubleshooting

- **Pack does not appear in the dropdown** — the folder must be
  `Resources\FileIcons\MaterialIconTheme` (the pack name is the directory name); reopen the
  Settings dialog.
- **Icons look stale after a rebuild** — delete the numeric cache directories inside the
  two pack folders, or run `make clean` before copying.
- **Default folder icon is missing from the dropdown** — the PNG must sit directly in
  `Resources\MainFolderIcon\MaterialIconTheme.png`, not inside a subdirectory; reopen the
  Settings dialog after copying it.
- **A file type uses the wrong icon** — check the row in `mappings/file-icons.tsv`; the
  first claim wins, so a more specific icon may need to be moved earlier in the definitions.
