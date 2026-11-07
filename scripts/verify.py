#!/usr/bin/env python3
"""Validate the built One Commander icon pack.

Checks
------
1. ``pack/<Kind>/<PackName>/`` exists and is not empty for both kinds, and
   ``pack/MainFolderIcon/<PackName>.png`` exists as the default folder icon.
2. Every PNG decodes (header + IHDR), is square and matches the expected size
   (``pack.json`` when present, otherwise ``--size``).
3. File names stay within One Commander's length limit and avoid Windows
   reserved device names.
4. Both ``Thumbnail.png`` previews exist and are 420x280.
5. The committed mapping tables exist and every row points at a real PNG.
6. Counts agree with ``pack.json`` and no numbered scale-cache directories are
   left behind.

Exit code 0 means the pack is publishable.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KINDS = (("FileIcons", "file-icons.tsv", 1), ("FolderIcons", "folder-icons.tsv", 2))
MAIN_FOLDER_DIR = "MainFolderIcon"
MAIN_FOLDER_SIZE = (64, 64)
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {
    f"lpt{i}" for i in range(1, 10)
}
THUMBNAIL_SIZE = (420, 280)


def png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        head = handle.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", head[16:24])


def read_tsv(path: Path) -> list[list[str]]:
    if not path.is_file():
        return []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(line.split("\t"))
    return rows[1:] if rows and rows[0][0] == "material_icon" else rows


def parse_size(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)(?:\s*[xX*]\s*(\d+))?\s*", text)
    if not match:
        raise argparse.ArgumentTypeError(f"cannot parse size {text!r} (example: 64 or 64x64)")
    width = int(match.group(1))
    height = int(match.group(2) or width)
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size must be greater than 0")
    return width, height


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the One Commander icon pack.")
    parser.add_argument(
        "--pack",
        default=str(REPO / "pack"),
        help="pack root (contains FileIcons/, FolderIcons/ and MainFolderIcon/)",
    )
    parser.add_argument("--name", default="MaterialIconTheme", help="pack directory name")
    parser.add_argument("--mappings", default=str(REPO / "mappings"), help="mapping table directory")
    parser.add_argument("--manifest", default=str(REPO / "dist" / "pack.json"), help="build manifest (optional)")
    parser.add_argument("--size", default=None, help="expected pixel size when no manifest is present")
    parser.add_argument(
        "--main-name",
        default=None,
        help="MainFolderIcon PNG stem (default: --name)",
    )
    parser.add_argument(
        "--main-size",
        type=parse_size,
        default=None,
        help="expected MainFolderIcon size when no manifest is present (default: 64x64)",
    )
    parser.add_argument("--max-name-len", type=int, default=100)
    args = parser.parse_args(argv)

    pack = Path(args.pack).expanduser().resolve()
    mappings = Path(args.mappings).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser()

    expected: tuple[int, int] | None = None
    manifest: dict = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            size = manifest.get("size")
            if isinstance(size, list) and len(size) == 2:
                expected = (int(size[0]), int(size[1]))
        except (OSError, ValueError):
            print(f"WARN cannot read {manifest_path}, falling back to --size")
    if expected is None:
        raw = args.size or "512"
        side = int(raw.split("x")[0])
        expected = (side, side)

    main_name = args.main_name or args.name
    main_expected = args.main_size or MAIN_FOLDER_SIZE
    main_meta = manifest.get("mainFolderIcon")
    if isinstance(main_meta, dict):
        main_size = main_meta.get("size")
        if isinstance(main_size, list) and len(main_size) == 2:
            main_expected = (int(main_size[0]), int(main_size[1]))

    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    if not pack.is_dir():
        print(f"FAIL pack directory not found: {pack}")
        return 1

    for kind, tsv_name, name_index in KINDS:
        kind_dir = pack / kind / args.name
        if not kind_dir.is_dir():
            errors.append(f"{kind}: directory missing ({kind_dir.relative_to(pack)})")
            continue

        pngs = sorted(p for p in kind_dir.iterdir() if p.suffix.lower() == ".png")
        counts[kind] = len([p for p in pngs if p.name != "Thumbnail.png"])
        if not counts[kind]:
            errors.append(f"{kind}: no PNGs found")
            continue

        for png in pngs:
            if png.name == "Thumbnail.png":
                continue  # checked separately (420x280 preview)
            stem = png.stem
            if len(png.name) > args.max_name_len + 4:
                errors.append(f"{kind}: name too long ({len(png.name)}): {png.name[:40]}…")
            if stem.lower() in WINDOWS_RESERVED:
                errors.append(f"{kind}: Windows reserved device name: {png.name}")
            dims = png_size(png)
            if dims is None:
                errors.append(f"{kind}: not a PNG: {png.name}")
                continue
            if dims[0] != dims[1]:
                errors.append(f"{kind}: not square {dims}: {png.name}")
            elif dims != expected:
                errors.append(f"{kind}: {dims} but expected {expected}: {png.name}")

        thumbnail = kind_dir / "Thumbnail.png"
        if not thumbnail.is_file():
            errors.append(f"{kind}: Thumbnail.png missing")
        elif png_size(thumbnail) != THUMBNAIL_SIZE:
            errors.append(f"{kind}: Thumbnail.png is {png_size(thumbnail)}, expected {THUMBNAIL_SIZE}")

        stray = [d.name for d in kind_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        if stray:
            warnings.append(f"{kind}: numbered scale-cache directories left behind: {', '.join(stray[:5])}")

        rows = read_tsv(mappings / tsv_name)
        if not rows:
            errors.append(f"{kind}: mapping table missing or empty ({tsv_name})")
        else:
            missing = [row[name_index] for row in rows if not (kind_dir / row[name_index]).is_file()]
            if missing:
                errors.append(f"{kind}: {len(missing)} mapped PNGs missing (e.g. {', '.join(missing[:3])})")
            expected_count = manifest.get("counts", {}).get(
                "filePngs" if kind == "FileIcons" else "folderPngs"
            )
            if expected_count is not None and expected_count != counts[kind]:
                errors.append(
                    f"{kind}: {counts[kind]} PNGs on disk but manifest says {expected_count}"
                )
            if len(rows) != counts[kind]:
                errors.append(f"{kind}: {len(rows)} mapping rows for {counts[kind]} PNGs")

    # MainFolderIcon is not a pack folder: One Commander reads the PNGs directly from
    # Resources\MainFolderIcon\, so the file lives at pack/MainFolderIcon/<name>.png.
    main_dir = pack / MAIN_FOLDER_DIR
    main_png = main_dir / f"{main_name}.png"
    counts[MAIN_FOLDER_DIR] = 0
    if not main_dir.is_dir():
        errors.append(f"{MAIN_FOLDER_DIR}: directory missing ({MAIN_FOLDER_DIR})")
    else:
        main_pngs = sorted(p for p in main_dir.iterdir() if p.suffix.lower() == ".png")
        counts[MAIN_FOLDER_DIR] = len(main_pngs)
        if not main_png.is_file():
            errors.append(f"{MAIN_FOLDER_DIR}: {main_png.name} missing")
        else:
            dims = png_size(main_png)
            if dims is None:
                errors.append(f"{MAIN_FOLDER_DIR}: not a PNG: {main_png.name}")
            elif dims[0] != dims[1]:
                errors.append(f"{MAIN_FOLDER_DIR}: not square {dims}: {main_png.name}")
            elif dims != main_expected:
                errors.append(
                    f"{MAIN_FOLDER_DIR}: {dims} but expected {main_expected}: {main_png.name}"
                )
        extra = [p.name for p in main_pngs if p.name != main_png.name]
        if extra:
            warnings.append(
                f"{MAIN_FOLDER_DIR}: unexpected PNGs next to {main_png.name}: "
                f"{', '.join(extra[:5])}"
            )
        stray = [d.name for d in main_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        if stray:
            warnings.append(
                f"{MAIN_FOLDER_DIR}: numbered scale-cache directories left behind: "
                f"{', '.join(stray[:5])}"
            )
        expected_count = manifest.get("counts", {}).get("mainFolderPngs")
        if expected_count is not None and expected_count != counts[MAIN_FOLDER_DIR]:
            errors.append(
                f"{MAIN_FOLDER_DIR}: {counts[MAIN_FOLDER_DIR]} PNGs on disk "
                f"but manifest says {expected_count}"
            )

    print(f"pack: {pack}")
    for kind, _tsv, _idx in KINDS:
        print(f"  {kind}: {counts.get(kind, 0)} icons, expected {expected[0]}x{expected[1]}")
    print(
        f"  {MAIN_FOLDER_DIR}: {counts.get(MAIN_FOLDER_DIR, 0)} icon, "
        f"expected {main_expected[0]}x{main_expected[1]} ({main_name}.png)"
    )
    if manifest:
        print(f"  manifest: {manifest_path} (upstream {manifest.get('sourceVersion', '?')})")
    else:
        print(f"  manifest: none (using --size {expected[0]})")
    for warning in warnings:
        print(f"WARN {warning}")
    if errors:
        for error in errors[:40]:
            print(f"FAIL {error}")
        if len(errors) > 40:
            print(f"FAIL … and {len(errors) - 40} more")
        return 1
    print("OK pack validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
