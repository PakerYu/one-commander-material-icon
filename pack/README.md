# Generated pack — do not edit by hand

Everything in this directory is produced by `scripts/build.py` from the upstream SVGs in
`vendor/material-icon-theme/icons/`:

```
pack/
├── FileIcons/MaterialIconTheme/    # 403 PNGs named after their extension token lists
│   └── Thumbnail.png               # 420×280 preview for Settings → Theme
└── FolderIcons/MaterialIconTheme/  # 925 PNGs named after folder names
    └── Thumbnail.png
```

The files are committed so the pack can be downloaded without building, and so changes show
up in review. Regenerate them instead of editing them:

```bash
make build     # re-render every PNG (needs Inkscape, or --renderer copy)
make verify    # sizes, file names, thumbnails, mapping ↔ file consistency
```

One Commander writes numeric scale caches (`64/`, `128/`, …) into these folders at runtime;
they are gitignored and `python3 scripts/build.py --prune` removes them. See
[`docs/one-commander.md`](../docs/one-commander.md) for the naming contract and
[`docs/mappings.md`](../docs/mappings.md) for how the associations are derived.
