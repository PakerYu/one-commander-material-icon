# Licensing decision record

Why this repository is **MIT all the way down**, and what that rules out.

## The short version

Everything here is MIT: the generator and tooling, the mapping tables, the documentation,
and the 1329 rendered PNGs. The full upstream notice travels with the code and with every
release archive.

```
LICENSE                              MIT, © PakerYu + © Material Extensions
ATTRIBUTION.md                       origin + scope of every work
LICENSES/material-icon-theme-MIT.txt verbatim upstream MIT text
pack/**                              derivative of the upstream artwork → MIT
```

## Why MIT and not something else

**1. The derivative constraint leaves almost no freedom.** Every file in `pack/` is a raster
of an upstream SVG: identical geometry, only the resolution and the file name change. That is
a derivative work, so the upstream MIT terms apply to the output as well — including the
requirement that the copyright line and permission text accompany every copy. Choosing a
different license for the PNGs would mean distributing MIT artwork under terms that drop its
notice, which the upstream license does not allow.

**2. MIT is the friendliest option for the thing being distributed.** An icon pack is
consumed by a proprietary file manager (One Commander) and by people who mix it with other
packs and themes. MIT imposes no obligations on either: no source disclosure, no copyleft
questions about the surrounding application, no NOTICE file bookkeeping.

**3. One license, one boundary.** `scripts/`, `mappings/` and `docs/` are original work, so
they could carry a different license — but splitting the repository into "MIT here, X there"
buys nothing and creates a boundary contributors have to reason about. A single MIT grant
with two copyright lines covers our code and the upstream artwork without ambiguity.

## Options that were considered and rejected

| Option | Why not |
| --- | --- |
| CC0 / public domain | Has to erase the upstream copyright line, which the MIT terms require us to keep. |
| CC BY 4.0 | Same problem: relicensing MIT artwork as CC BY is not a permitted path, and attribution-only does not reproduce the permission text in the way MIT asks. |
| Apache-2.0 | Not the upstream license; adds a NOTICE obligation and patent terms to artwork that needs neither. |
| GPL-3.0 | MIT may be upgraded to GPL-3.0, so it is *possible*, but it buys nothing here and makes downstream bundling harder — icon packs are routinely mixed into distributable themes. Only worth it if the goal is to force downstream modifications open, which is not this project's goal. |
| Dual MIT / Apache-2.0 | Extra surface for no benefit; nothing in the repository comes from an Apache-2.0 source. |

## Trademarks are not licensed

MIT covers the artwork, not the brands inside it. Icons for VS Code, React, Docker, Adobe and
friends are trademarked by their owners and are used only to identify file types. The same
goes for the name "One Commander": it appears descriptively, to say which file manager the
pack is formatted for. See the trademark section of [`ATTRIBUTION.md`](../ATTRIBUTION.md).

## Keeping it correct

```bash
make notices    # copyright lines, verbatim upstream text, attribution + trademark sections
make licenses   # refresh LICENSES/ from vendor/ after bumping upstream.lock.json
make package    # zip the committed pack/ and assert the notices are inside the archive
```

CI runs the same checks (`.github/workflows/ci.yml`) and the release workflow refuses to
publish an archive that is missing them.

## If you need to change this later

Changing the license of the **pack** means a new agreement with the upstream artwork terms —
in practice, do not. Changing the license of **our own code** is a normal `LICENSE` edit plus
a CHANGELOG entry; contributors' past work stays under the terms it was submitted under, so
record the change instead of rewriting history.
