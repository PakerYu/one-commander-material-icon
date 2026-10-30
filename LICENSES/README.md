# Third-party license texts

One file per external work whose terms this repository has to carry. These copies are
shipped inside every release archive so a downloaded zip is self-describing.

| File | Covers | Origin |
| --- | --- | --- |
| `material-icon-theme-MIT.txt` | `vendor/material-icon-theme/**` and the rendered `pack/**` artwork | <https://github.com/material-extensions/vscode-material-icon-theme> (v5.39.0) |

Rules:

- The files here are **verbatim copies** of the upstream license text. Do not add headers or
  reformat them — `make notices` compares them byte for byte against `vendor/`.
- Refresh them with `make licenses` after bumping `upstream.lock.json`.
- This project's own license is the [`LICENSE`](../LICENSE) in the repository root; the
  origin and scope of each work is described in [`ATTRIBUTION.md`](../ATTRIBUTION.md).
