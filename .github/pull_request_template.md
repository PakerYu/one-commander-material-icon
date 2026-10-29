## What this changes

<!-- one or two sentences -->

## Type

- [ ] mapping table (`mappings/*.tsv`, regenerated)
- [ ] build / verify scripts
- [ ] documentation
- [ ] CI / release
- [ ] upstream version bump

## Checklist

- [ ] `make check verify` passes locally
- [ ] `make dist` produces a zip with the expected file counts (if `pack/` changed)
- [ ] `git diff --stat mappings/` only contains rows I intended to change
- [ ] `CHANGELOG.md` updated (user-visible change)
- [ ] `upstream.lock.json` bumped if the vendored icons changed

## Screenshots

<!-- optional: before/after of the affected icons, or the Thumbnail.png preview -->
