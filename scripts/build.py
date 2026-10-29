#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py — turn material-icon-theme into a One Commander icon pack.

Pipeline
--------
1. Read the icon associations from material-icon-theme (TypeScript definitions,
   or an already generated ``material-icons.json``).
2. Rewrite the associations for One Commander: file icons are named after the
   extension list they cover (``py,pyw.png``), folder icons after the real
   folder name they match (``src.png``).
3. Rasterise the SVGs to PNG with the selected renderer (inkscape /
   rsvg-convert / cairosvg / imagemagick / copy).
4. Write ``file-icons.tsv`` / ``folder-icons.tsv`` (mapping tables),
   ``pack.json`` (build manifest) and optionally rebuild the ``Thumbnail.png``
   previews.

Standard library only; renderers are external commands (or the ``cairosvg``
module).

Usage
-----
    # render into pack/ with the vendored upstream checkout
    python3 scripts/build.py

    # explicit upstream checkout and size
    python3 scripts/build.py --material-icons ../vscode-material-icon-theme --size 512

    # parallel rendering with rsvg-convert
    python3 scripts/build.py --renderer rsvg-convert --jobs 16

    # validate the committed mappings against the source, write nothing
    python3 scripts/build.py --check

    # reuse upstream PNGs (no Inkscape needed)
    python3 scripts/build.py --renderer copy --size 512

Output layout (``--out`` defaults to ``<repo>/pack``):

    <out>/FileIcons/<pack-name>/*.png
    <out>/FolderIcons/<pack-name>/*.png

and, outside the pack directory:

    <repo>/mappings/file-icons.tsv
    <repo>/mappings/folder-icons.tsv
    <repo>/dist/pack.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

#: Repository root (this file lives in <repo>/scripts/).
REPO = Path(__file__).resolve().parent.parent
#: Vendored upstream checkout (`make vendor` refreshes it).
VENDOR = REPO / "vendor" / "material-icon-theme"

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #

#: One Commander 的图标文件名（含 .png）长度上限，超长会拆成多个同名副本。
MAX_NAME_LEN = 100

#: Windows 保留设备名，不能作为文件名（否则 ls/dir 都无法列出该文件）。
WINDOWS_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

FOLDER_PREFIX = "folder-"

FILE_TSV_NAME = "file-icons.tsv"
FOLDER_TSV_NAME = "folder-icons.tsv"

TSV_FILE_HEADER = ("material_icon", "onecommander_file", "extensions")
TSV_FOLDER_HEADER = ("material_icon", "folder_name", "onecommander_file")

#: 预览图默认使用的图标（与归档版本的 Thumbnail.png 一致）
DEFAULT_THUMBNAIL_ICONS = ("python", "react", "docker", "json", "markdown", "image")


# --------------------------------------------------------------------------- #
# 极简 TypeScript 字面量解析
#
# material-icon-theme 的 icons 定义是「对象数组字面量 + 少量函数包装」，
# 这里只需要能吃掉字符串/数字/布尔/数组/对象/成员引用这些结构，
# 不需要完整的 TS 语法。
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(
    r"""
      \s+
    | (?P<string>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
    | (?P<number>-?\d+(?:\.\d+)?)
    | (?P<ident>[A-Za-z_$][\w$]*)
    | (?P<punct>[{}\[\](),:;.])
    """,
    re.VERBOSE,
)


def _strip_comments(src: str) -> str:
    """去掉 // 与 /* */ 注释，保留字符串内容。"""
    out: List[str] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j == -1 else j
        elif ch == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j == -1 else j + 2
        elif ch in "'\"`":
            quote = ch
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == quote:
                    break
                j += 1
            out.append(src[i : j + 1])
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _tokenize(src: str) -> List[Tuple[str, str]]:
    src = _strip_comments(src)
    tokens: List[Tuple[str, str]] = []
    pos = 0
    while pos < len(src):
        match = _TOKEN_RE.match(src, pos)
        if not match:  # 遇到无法识别的字符时跳过，保证脚本向前推进
            pos += 1
            continue
        pos = match.end()
        kind = match.lastgroup
        if not kind:
            continue
        if kind == "punct" and match.group() == ";":
            continue
        tokens.append((kind, match.group()))
    return tokens


class _LiteralParser:
    """把 token 序列折叠成 Python 数据结构。"""

    def __init__(self, tokens: Sequence[Tuple[str, str]]) -> None:
        self._tokens = list(tokens)
        self._pos = 0

    def _peek(self) -> Tuple[Optional[str], Optional[str]]:
        if self._pos >= len(self._tokens):
            return None, None
        return self._tokens[self._pos]

    def parse(self):
        return self._value()

    def _value(self):
        kind, value = self._peek()
        if kind == "punct" and value == "{":
            return self._object()
        if kind == "punct" and value == "[":
            return self._array()
        if kind == "punct" and value == "(":
            self._pos += 1
            inner = self._value()
            if self._peek()[1] == ")":
                self._pos += 1
            return inner
        if kind == "string":
            self._pos += 1
            return _unquote(value or "")
        if kind == "number":
            self._pos += 1
            text = value or "0"
            return float(text) if "." in text else int(text)
        if kind == "ident":
            self._pos += 1
            name = value or ""
            if name in ("true", "false"):
                return name == "true"
            # 成员引用（FileNamePattern.Cosmiconfig 等）或函数调用
            while self._peek()[1] == ".":
                self._pos += 1
                nxt = self._peek()
                if nxt[0] is None:
                    break
                name += "." + (nxt[1] or "")
                self._pos += 1
            if self._peek()[1] == "(":  # parseByPattern([...]) 之类的包装
                self._pos += 1
                inner = self._value()
                if self._peek()[1] == ")":
                    self._pos += 1
                return inner
            return {"__ref__": name}
        # 其它情况：推进一个 token 防止死循环
        self._pos += 1
        return None

    def _object(self) -> dict:
        self._pos += 1  # '{'
        result: dict = {}
        while True:
            kind, value = self._peek()
            if kind is None:
                return result
            if kind == "punct" and value == "}":
                self._pos += 1
                return result
            if kind == "punct" and value == ",":
                self._pos += 1
                continue
            if kind in ("ident", "string"):
                key = _unquote(value or "") if kind == "string" else (value or "")
                self._pos += 1
            else:
                self._pos += 1
                continue
            if self._peek()[1] == ":":
                self._pos += 1
                result[key] = self._value()

    def _array(self) -> list:
        self._pos += 1  # '['
        result: list = []
        while True:
            kind, value = self._peek()
            if kind is None:
                return result
            if kind == "punct" and value == "]":
                self._pos += 1
                return result
            if kind == "punct" and value == ",":
                self._pos += 1
                continue
            result.append(self._value())


def _unquote(text: str) -> str:
    body = text[1:-1]
    if "\\" not in body:
        return body
    try:
        return body.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return body


def parse_ts_export(path: Path, variable: str):
    """解析 ``export const <variable> ... = <字面量>``。"""
    src = path.read_text(encoding="utf-8")
    match = re.search(r"export\s+const\s+%s\b[^=]*=" % re.escape(variable), src)
    if not match:
        raise ValueError(f"{path}: no `export const {variable}` found")
    body = src[match.end() :]
    starts = [index for index in (body.find("["), body.find("{")) if index >= 0]
    if not starts:
        raise ValueError(f"{path}: no literal after `{variable}`")
    return _LiteralParser(_tokenize(body[min(starts) :])).parse()


# --------------------------------------------------------------------------- #
# 关联定义（material-icon-theme 一侧）
# --------------------------------------------------------------------------- #


@dataclass
class FileIconSpec:
    name: str
    extensions: List[str] = field(default_factory=list)
    file_names: List[str] = field(default_factory=list)
    is_clone: bool = False
    enabled_for: List[str] = field(default_factory=list)

    def dotfile_tokens(self) -> List[str]:
        """点文件名 → 扩展名 token（``.gitignore`` → ``gitignore``）。"""
        tokens = []
        for name in self.file_names:
            if not name.startswith("."):
                continue  # ``Dockerfile``、``package.json`` 这类无法被扩展名规则命中
            tokens.append(name.lstrip(".").lower())
        return tokens

    def extension_tokens(self) -> List[str]:
        return [ext.lower() for ext in self.extensions]


@dataclass
class FolderIconSpec:
    name: str
    folder_names: List[str] = field(default_factory=list)
    is_clone: bool = False
    enabled_for: List[str] = field(default_factory=list)

    @property
    def suffix(self) -> str:
        return self.name[len(FOLDER_PREFIX) :] if self.name.startswith(FOLDER_PREFIX) else self.name


def _refs(value) -> List[str]:
    """把 enabledFor 里的 {"__ref__": "IconPack.Ngrx"} 变成可读字符串列表。"""
    if not isinstance(value, list):
        return []
    refs = []
    for item in value:
        if isinstance(item, dict) and "__ref__" in item:
            refs.append(str(item["__ref__"]).split(".")[-1])
        elif isinstance(item, str):
            refs.append(item)
    return refs


def _string_list(value) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _find_definition_file(root: Path, filename: str) -> Optional[Path]:
    direct = [
        root / "src" / "core" / "icons" / filename,
        root / "src" / "icons" / filename,
        root / filename,
    ]
    for candidate in direct:
        if candidate.is_file():
            return candidate
    for candidate in sorted(root.rglob(filename)):
        return candidate
    return None


def load_from_definitions(root: Path) -> Tuple[List[FileIconSpec], List[FolderIconSpec], Dict[str, str]]:
    """从 material-icon-theme 仓库的 TypeScript 定义中读取关联。"""
    file_def = _find_definition_file(root, "fileIcons.ts")
    folder_def = _find_definition_file(root, "folderIcons.ts")
    if not file_def or not folder_def:
        raise SystemExit(
            f"{root}: fileIcons.ts / folderIcons.ts not found. "
            "Point --material-icons at a material-icon-theme checkout "
            "(or pass --manifest-json a material-icons.json)."
        )

    file_tree = parse_ts_export(file_def, "fileIcons") or {}
    file_specs = [
        FileIconSpec(
            name=str(icon.get("name", "")),
            extensions=_string_list(icon.get("fileExtensions")),
            file_names=_string_list(icon.get("fileNames")),
            is_clone="clone" in icon,
            enabled_for=_refs(icon.get("enabledFor")),
        )
        for icon in (file_tree.get("icons") or [])
        if isinstance(icon, dict) and icon.get("name")
    ]

    themes = parse_ts_export(folder_def, "folderIcons") or []
    specific = next(
        (theme for theme in themes if isinstance(theme, dict) and theme.get("name") == "specific"),
        None,
    )
    if specific is None:
        raise SystemExit(f"{folder_def}: no folder theme named `specific`")
    folder_specs = [
        FolderIconSpec(
            name=str(icon.get("name", "")),
            folder_names=_string_list(icon.get("folderNames")),
            is_clone="clone" in icon,
            enabled_for=_refs(icon.get("enabledFor")),
        )
        for icon in (specific.get("icons") or [])
        if isinstance(icon, dict) and icon.get("name")
    ]

    meta = {"source": "typescript", "definitions": f"{file_def.name}, {folder_def.name}"}
    return file_specs, folder_specs, meta


def load_from_manifest(manifest_path: Path) -> Tuple[List[FileIconSpec], List[FolderIconSpec], Dict[str, str]]:
    """从 material-icon-theme 生成的 ``material-icons.json`` 清单中读取关联。

    清单里是已经展开好的映射（``fileExtensions`` / ``fileNames`` /
    ``folderNames``），因此不需要 TS 定义。清单不包含 clone 信息，
    缺失的图标资源会在渲染阶段被报出来。
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    file_specs_map: Dict[str, FileIconSpec] = {}
    for ext, icon in (data.get("fileExtensions") or {}).items():
        spec = file_specs_map.setdefault(icon, FileIconSpec(name=icon))
        spec.extensions.append(ext)
    for name, icon in (data.get("fileNames") or {}).items():
        spec = file_specs_map.setdefault(icon, FileIconSpec(name=icon))
        spec.file_names.append(name)

    folder_specs_map: Dict[str, FolderIconSpec] = {}
    for folder_name, icon in (data.get("folderNames") or {}).items():
        spec = folder_specs_map.setdefault(icon, FolderIconSpec(name=icon))
        spec.folder_names.append(folder_name)

    meta = {"source": "manifest", "definitions": manifest_path.name}
    return list(file_specs_map.values()), list(folder_specs_map.values()), meta


def read_material_version(root: Optional[Path]) -> Optional[str]:
    if not root:
        return None
    package_json = root / "package.json"
    if not package_json.is_file():
        return None
    try:
        return str(json.loads(package_json.read_text(encoding="utf-8")).get("version") or "") or None
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# 映射生成
# --------------------------------------------------------------------------- #


def is_simple_token(token: str) -> bool:
    """能作为 One Commander 图标文件名的一部分：单段、ASCII、非保留名。"""
    if not token:
        return False
    if "." in token or "/" in token or "\\" in token:
        return False
    if any(ord(char) > 127 for char in token):
        return False
    return token not in WINDOWS_RESERVED


def is_simple_folder_name(name: str) -> bool:
    if not name or "/" in name or "\\" in name:
        return False
    if any(ord(char) > 127 for char in name):
        return False
    return name.lower() not in WINDOWS_RESERVED


def chunk_tokens(tokens: Sequence[str], max_len: int = MAX_NAME_LEN) -> List[List[str]]:
    """把 token 列表切成若干段，保证 ``','.join(chunk)`` 不超过 max_len。"""
    chunks: List[List[str]] = []
    current: List[str] = []
    for token in tokens:
        candidate = current + [token]
        if current and len(",".join(candidate)) > max_len:
            chunks.append(current)
            current = [token]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def build_file_mapping(
    specs: Sequence[FileIconSpec], max_len: int = MAX_NAME_LEN
) -> Tuple[List[Tuple[str, str, str]], Dict[str, str]]:
    """生成 (material_icon, onecommander_file, extensions) 行。

    两轮认领（与归档版本一致）：

    1. 先认领所有点文件名（``.npmrc`` → ``npmrc``），这类 token 优先级更高，
       因此 ``npm`` 能拿到 ``npmrc``，而不是被后面的 ``settings`` 扩展名抢走。
    2. 再按定义顺序认领 ``fileExtensions``；同一 token 先到先得，
       所以 ``tsx`` 归 ``react_ts`` 而不是 ``qwik``。
    """
    reasons: Dict[str, str] = {}
    claims: Dict[str, str] = {}

    live_specs = []
    for spec in specs:
        if spec.is_clone:
            reasons[spec.name] = "clone"  # 需要 material 的 generateClones，仓库里没有资源
            continue
        live_specs.append(spec)

    for spec in live_specs:
        for token in spec.dotfile_tokens():
            if is_simple_token(token):
                claims.setdefault(token, spec.name)

    for spec in live_specs:
        for token in spec.extension_tokens():
            if is_simple_token(token):
                claims.setdefault(token, spec.name)

    rows: List[Tuple[str, str, str]] = []
    for spec in live_specs:
        tokens = sorted(token for token, owner in claims.items() if owner == spec.name)
        if not tokens:
            reasons.setdefault(spec.name, "no-usable-token")
            continue
        for chunk in chunk_tokens(tokens, max_len):
            joined = ",".join(chunk)
            rows.append((spec.name, joined + ".png", joined))

    rows.sort(key=lambda row: (row[0], row[1]))
    return rows, reasons


def build_folder_mapping(specs: Sequence[FolderIconSpec]) -> Tuple[List[Tuple[str, str, str]], Dict[str, str]]:
    """生成 (material_icon, folder_name, onecommander_file) 行。

    认领顺序：先让「图标名后缀 == 文件夹名」的图标认领（``folder-store`` 拿
    ``store``），再按定义顺序认领剩余别名（``folder-vuex-store`` 拿 ``stores``）。
    """
    reasons: Dict[str, str] = {}
    claims: Dict[str, str] = {}

    live_specs = []
    for spec in specs:
        if spec.is_clone:
            reasons[spec.name] = "clone"
            continue
        if not spec.folder_names:
            reasons[spec.name] = "no-folder-name"
            continue
        live_specs.append(spec)

    # 第一轮：图标名与文件夹名完全对应的优先
    for spec in live_specs:
        suffix = spec.suffix
        for name in spec.folder_names:
            if is_simple_folder_name(name) and name == suffix:
                claims.setdefault(name, spec.name)

    # 第二轮：其余别名按定义顺序
    for spec in live_specs:
        for name in spec.folder_names:
            if is_simple_folder_name(name):
                claims.setdefault(name, spec.name)

    rows = [(icon, name, name + ".png") for name, icon in claims.items()]

    for spec in live_specs:
        if not any(icon == spec.name for icon, _, _ in rows):
            reasons.setdefault(spec.name, "name-conflict")

    rows.sort(key=lambda row: row[1])
    return rows, reasons


# --------------------------------------------------------------------------- #
# 资源定位
# --------------------------------------------------------------------------- #


@dataclass
class Asset:
    path: Path
    is_svg: bool


def resolve_asset(name: str, kind: str, icons_dir: Optional[Path], prefer_svg: bool) -> Optional[Asset]:
    """找到某个 material 图标对应的 SVG/PNG 资源。"""
    if icons_dir is None:
        return None
    png_candidates = [
        icons_dir / "png" / f"{name}.png",
        icons_dir / f"{name}.png",
        icons_dir / ("file" if kind == "file" else "folder") / f"{name}.png",
    ]
    svg_candidates = [icons_dir / f"{name}.svg"]
    ordered = svg_candidates + png_candidates if prefer_svg else png_candidates + svg_candidates
    for candidate in ordered:
        if candidate.is_file():
            return Asset(candidate, candidate.suffix.lower() == ".svg")
    return None


def png_size(path: Path) -> Optional[Tuple[int, int]]:
    try:
        with path.open("rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


# --------------------------------------------------------------------------- #
# 渲染器
# --------------------------------------------------------------------------- #


#: 单次外部命令的超时（秒），防止个别 SVG 卡死整个构建
RENDER_TIMEOUT = 600.0


def _run(
    command: Sequence[str],
    input_text: Optional[str] = None,
    timeout: Optional[float] = None,
) -> subprocess.CompletedProcess:
    """跑一条外部命令；stdout/stderr 以文本返回。"""
    try:
        return subprocess.run(
            list(command),
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=RENDER_TIMEOUT if timeout is None else timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            list(command), 124, "", f"timeout (>{RENDER_TIMEOUT:.0f}s)"
        )
    except FileNotFoundError as error:
        return subprocess.CompletedProcess(list(command), 127, "", str(error))


class Renderer:
    """渲染器接口：``render`` 渲染单个图标，``render_batch`` 渲染一批。"""

    name = "base"
    supports_batch = False
    prefer_single_process = False

    def available(self) -> bool:
        raise NotImplementedError

    def render(self, asset: Asset, target: Path, size: Tuple[int, int]) -> None:
        raise NotImplementedError

    def render_batch(self, tasks: Sequence["BuildTask"], size: Tuple[int, int]) -> None:
        """默认实现：逐个调用 ``render``。"""
        for task in tasks:
            if task.asset is not None:
                self.render(task.asset, task.output, size)


class InkscapeRenderer(Renderer):
    name = "inkscape"
    supports_batch = True
    #: 并发启动多个 Inkscape 在部分 Linux 环境会崩溃；批处理已经把单图标
    #: 开销压到十几毫秒，因此默认只用一个进程（--jobs 可覆盖）。
    prefer_single_process = True

    def available(self) -> bool:
        return shutil.which("inkscape") is not None

    def render(self, asset: Asset, target: Path, size: Tuple[int, int]) -> None:
        if not asset.is_svg:
            CopyRenderer().render(asset, target, size)
            return
        width, height = size
        result = _run(
            [
                "inkscape",
                str(asset.path),
                "--export-type=png",
                f"--export-filename={target}",
                f"--export-width={width}",
                f"--export-height={height}",
            ]
        )
        if result.returncode == 0:
            return
        if re.search(r"[Uu]nknown option|[Uu]nrecogni[sz]ed option", result.stderr):
            # Inkscape 0.9x 的老参数
            result = _run(
                [
                    "inkscape",
                    "-z",
                    "-e",
                    str(target),
                    "-w",
                    str(width),
                    "-h",
                    str(height),
                    str(asset.path),
                ]
            )
            if result.returncode == 0:
                return
        raise RuntimeError(f"inkscape exited with {result.returncode}: {result.stderr.strip()[:300]}")

    def render_batch(self, tasks: Sequence["BuildTask"], size: Tuple[int, int]) -> None:
        """用一个 Inkscape 进程连续导出多个 SVG（``--shell`` 批处理）。

        并发启动多个 Inkscape 实例时，部分 Linux 环境会在 GIO/D-Bus 初始化阶段
        崩溃（SIGABRT，``Gio::DBus::Error``）；把导出命令喂进同一个进程既绕开
        该问题，也省掉了每个图标 0.3 秒左右的启动开销。
        """
        width, height = size
        script: List[str] = []
        for task in tasks:
            if task.asset is None:
                continue
            if not task.asset.is_svg:  # 已经是 PNG，直接拷贝
                CopyRenderer().render(task.asset, task.output, size)
                continue
            script.extend(
                [
                    f"file-open:{task.asset.path}",
                    f"export-filename:{task.output}",
                    f"export-width:{width}",
                    f"export-height:{height}",
                    "export-do",
                ]
            )
        if not script:
            return
        script.append("quit")
        result = _run(["inkscape", "--shell"], input_text="\n".join(script) + "\n")
        if result.returncode != 0:
            raise RuntimeError(
                f"inkscape --shell exited with {result.returncode}: {result.stderr.strip()[:300]}"
            )


class RsvgRenderer(Renderer):
    name = "rsvg-convert"

    def available(self) -> bool:
        return shutil.which("rsvg-convert") is not None

    def render(self, asset: Asset, target: Path, size: Tuple[int, int]) -> None:
        if not asset.is_svg:
            CopyRenderer().render(asset, target, size)
            return
        width, height = size
        result = _run(
            [
                "rsvg-convert",
                "-w",
                str(width),
                "-h",
                str(height),
                "-o",
                str(target),
                str(asset.path),
            ]
        )
        if result.returncode != 0:
            raise RuntimeError(f"rsvg-convert exited with {result.returncode}: {result.stderr.strip()[:300]}")


class CairoSvgRenderer(Renderer):
    name = "cairosvg"

    def available(self) -> bool:
        try:
            import cairosvg  # noqa: F401
        except ImportError:
            return False
        return True

    def render(self, asset: Asset, target: Path, size: Tuple[int, int]) -> None:
        import cairosvg

        if not asset.is_svg:
            CopyRenderer().render(asset, target, size)
            return
        width, height = size
        cairosvg.svg2png(
            url=str(asset.path),
            write_to=str(target),
            output_width=width,
            output_height=height,
        )


class ImageMagickRenderer(Renderer):
    name = "imagemagick"

    def _binary(self) -> Optional[str]:
        return shutil.which("magick") or shutil.which("convert")

    def available(self) -> bool:
        return self._binary() is not None

    def render(self, asset: Asset, target: Path, size: Tuple[int, int]) -> None:
        binary = self._binary()
        if not binary:
            raise RuntimeError("magick/convert not found")
        width, height = size
        density = max(96, int(round(width * 96 / 24)))  # material 图标 viewBox 为 24
        prefix = [binary] + (["convert"] if os.path.basename(binary) == "magick" else [])
        result = _run(
            prefix
            + [
                "-background",
                "none",
                "-density",
                str(density),
                str(asset.path),
                "-resize",
                f"{width}x{height}!",
                str(target),
            ]
        )
        if result.returncode != 0:
            raise RuntimeError(f"{binary} exited with {result.returncode}: {result.stderr.strip()[:300]}")


class CopyRenderer(Renderer):
    """直接使用 material 仓库里已有的 PNG（要求尺寸与 --size 一致）。"""

    name = "copy"

    def available(self) -> bool:
        return True

    def render(self, asset: Asset, target: Path, size: Tuple[int, int]) -> None:
        if asset.is_svg:
            raise RuntimeError("copy mode needs PNG assets but only SVGs were found")
        current = png_size(asset.path)
        if current == size:
            shutil.copyfile(asset.path, target)
            return
        # material 仓库自带的 PNG 可能不是正方形（自家脚本只固定了宽度），
        # 有 ImageMagick 时顺手缩放/补白到目标尺寸。
        resizer = ImageMagickRenderer()
        if resizer.available():
            resizer.render(asset, target, size)
            return
        raise RuntimeError(
            f"existing PNG is {current}, which does not match --size {size[0]}x{size[1]}"
            " (install ImageMagick to rescale, or use --renderer inkscape)"
        )


RENDERERS: Dict[str, Renderer] = {
    renderer.name: renderer
    for renderer in (
        InkscapeRenderer(),
        RsvgRenderer(),
        CairoSvgRenderer(),
        ImageMagickRenderer(),
        CopyRenderer(),
    )
}

AUTO_RENDER_ORDER = ("inkscape", "rsvg-convert", "cairosvg", "imagemagick", "copy")


def pick_renderer(requested: str) -> Tuple[Renderer, List[str]]:
    notes: List[str] = []
    if requested != "auto":
        renderer = RENDERERS.get(requested)
        if renderer is None:
            raise SystemExit(f"unknown renderer {requested!r}, choose one of: {', '.join(RENDERERS)}, auto")
        if not renderer.available():
            missing = {"inkscape": "inkscape", "rsvg-convert": "rsvg-convert", "imagemagick": "magick/convert", "cairosvg": "python 包 cairosvg", "copy": ""}[
                renderer.name
            ]
            raise SystemExit(f"renderer {renderer.name} is unavailable (missing {missing})")
        return renderer, notes
    for name in AUTO_RENDER_ORDER:
        renderer = RENDERERS[name]
        if renderer.available():
            notes.append(f"auto-selected renderer: {name}")
            return renderer, notes
    raise SystemExit("no usable renderer found")


# --------------------------------------------------------------------------- #
# TSV / 构建信息
# --------------------------------------------------------------------------- #


def write_tsv(path: Path, header: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    lines = ["\t".join(header)]
    lines.extend("\t".join(row) for row in rows)
    # One Commander / Excel 友好：CRLF 行尾（newline="" 防止被平台转换）
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\r\n".join(lines) + "\r\n")


def read_tsv(path: Path) -> List[Tuple[str, ...]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    rows: List[Tuple[str, ...]] = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        rows.append(tuple(line.split("\t")))
    return rows[1:] if rows else []


# --------------------------------------------------------------------------- #
# 预览图
# --------------------------------------------------------------------------- #


def make_thumbnail(sources: Sequence[Path], target: Path, size: Tuple[int, int]) -> None:
    """用 ImageMagick 拼一张 cols×rows 的预览图（One Commandant 会显示它）。"""
    binary = shutil.which("magick") or shutil.which("convert")
    if not binary or not sources:
        raise RuntimeError("ImageMagick is required to build Thumbnail.png")
    width, height = size
    columns = 3 if len(sources) > 2 else 2
    rows_count = (len(sources) + columns - 1) // columns
    cell_w, cell_h = width // columns, height // rows_count
    icon_box = int(min(cell_w, cell_h) * 0.86)
    prefix = [binary] + (["convert"] if os.path.basename(binary) == "magick" else [])
    with tempfile.TemporaryDirectory() as tmp:
        command = prefix + ["-size", f"{width}x{height}", "xc:white"]
        for index, source in enumerate(sources[: columns * rows_count]):
            cell = Path(tmp) / f"cell-{index}.png"
            _run(prefix + [str(source), "-resize", f"{icon_box}x{icon_box}", str(cell)])
            column, row = index % columns, index // columns
            x = column * cell_w + (cell_w - icon_box) // 2
            y = row * cell_h + (cell_h - icon_box) // 2
            command += [str(cell), "-geometry", f"+{x}+{y}", "-composite"]
        command.append(str(target))
        result = _run(command)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip()[:400])


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #


def parse_size(text: str) -> Tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)(?:\s*[xX*]\s*(\d+))?\s*", text)
    if not match:
        raise argparse.ArgumentTypeError(f"cannot parse size {text!r} (example: 256 or 256x256)")
    width = int(match.group(1))
    height = int(match.group(2) or width)
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size must be greater than 0")
    return width, height


@dataclass
class BuildTask:
    icon: str
    kind: str
    output: Path
    asset: Optional[Asset]


def collect_tasks(
    rows: Sequence[Tuple[str, str, str]],
    kind: str,
    target_dir: Path,
    icons_dir: Optional[Path],
    prefer_svg: bool,
) -> Tuple[List[BuildTask], Dict[str, int]]:
    """把映射行翻译成渲染任务。

    两种映射行的列布局不同：
    文件图标 ``(material_icon, onecommander_file, extensions)``，
    文件夹图标 ``(material_icon, folder_name, onecommander_file)``。
    """
    name_index = 1 if kind == "file" else 2
    tasks: List[BuildTask] = []
    stats = {"missing-asset": 0}
    for row in rows:
        icon = row[0]
        file_name = row[name_index]
        asset = resolve_asset(icon, kind, icons_dir, prefer_svg)
        if asset is None:
            stats["missing-asset"] += 1
        tasks.append(BuildTask(icon=icon, kind=kind, output=target_dir / file_name, asset=asset))
    return tasks, stats


def _split_chunks(tasks: Sequence[BuildTask], pieces: int) -> List[List[BuildTask]]:
    pieces = max(1, min(pieces, len(tasks)))
    step = (len(tasks) + pieces - 1) // pieces
    return [list(tasks[index : index + step]) for index in range(0, len(tasks), step)]


def _render_chunk(
    chunk: Sequence[BuildTask], renderer: Renderer, size: Tuple[int, int]
) -> List[Tuple[BuildTask, str]]:
    """渲染一批任务，返回没成功的那几个。"""
    for task in chunk:
        if task.output.exists():  # 清掉上次残留的半成品
            task.output.unlink()
    message = None
    try:
        renderer.render_batch(chunk, size)
    except Exception as error:  # noqa: BLE001 - 整批失败时逐个复查
        message = str(error)
    failures: List[Tuple[BuildTask, str]] = []
    for task in chunk:
        if task.asset is None:
            continue
        if png_size(task.output) != size:
            failures.append((task, message or "renderer produced a PNG with the wrong size"))
    return failures


def run_render(
    tasks: Sequence[BuildTask],
    renderer: Renderer,
    size: Tuple[int, int],
    jobs: int,
    force: bool,
    quiet: bool,
    retries: int = 2,
) -> Tuple[int, int, List[Tuple[BuildTask, str]]]:
    """渲染所有任务，返回 (已渲染数, 跳过数, 失败列表)。"""
    pending: List[BuildTask] = []
    skipped = 0
    for task in tasks:
        if task.asset is None:
            continue
        if not force and png_size(task.output) == size:
            skipped += 1
            continue
        pending.append(task)

    failures: List[Tuple[BuildTask, str]] = []
    total = len(pending)
    if total == 0:
        return 0, skipped, failures

    started = time.time()
    done = 0
    last_report = 0.0
    chunks = _split_chunks(pending, max(1, min(64, jobs * 8)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(jobs, len(chunks)))) as pool:
        futures = {
            pool.submit(_render_chunk, chunk, renderer, size): chunk for chunk in chunks
        }
        for future in concurrent.futures.as_completed(futures):
            chunk = futures[future]
            done += len(chunk)
            try:
                failures.extend(future.result())
            except Exception as error:  # noqa: BLE001
                failures.extend((task, str(error)) for task in chunk if task.asset is not None)
            now = time.time()
            if not quiet and (now - last_report > 0.2 or done == total):
                last_report = now
                elapsed = now - started
                rate = done / elapsed if elapsed else 0
                sys.stdout.write(
                    f"\r  rendered {done}/{total} ({rate:.1f}/s, {len(failures)} failed)"
                )
                sys.stdout.flush()
    if not quiet:
        sys.stdout.write("\n")

    # 失败的图标逐个串行重试：崩溃/超时通常是并发或个别 SVG 引起的，串行多半就过了
    attempt = 0
    while failures and attempt < retries:
        attempt += 1
        if not quiet:
            print(f"  serial retry {attempt}: {len(failures)} icon(s) left")
        retry_tasks = [task for task, _ in failures]
        failures = []
        for task in retry_tasks:
            try:
                _render_one(task, renderer, size)
            except Exception as error:  # noqa: BLE001
                failures.append((task, str(error)))

    return total, skipped, failures


def _render_one(task: BuildTask, renderer: Renderer, size: Tuple[int, int]) -> None:
    task.output.parent.mkdir(parents=True, exist_ok=True)
    assert task.asset is not None
    if task.output.exists():
        task.output.unlink()
    renderer.render(task.asset, task.output, size)
    rendered = png_size(task.output)
    if rendered != size:
        raise RuntimeError(f"rendered size {rendered} does not match the requested {size}")


def prune(target_dir: Path, keep: Iterable[str], protected: Sequence[str] = ()) -> List[str]:
    """删除本脚本不认识的旧 PNG，以及 One Commander 生成的数字缓存目录。"""
    keep_set = set(keep) | set(protected)
    removed: List[str] = []
    if target_dir.is_dir():
        for entry in sorted(target_dir.iterdir()):
            if entry.is_dir() and entry.name.isdigit():
                shutil.rmtree(entry, ignore_errors=True)
                removed.append(entry.name + "/")
            elif entry.is_file() and entry.suffix.lower() == ".png" and entry.name not in keep_set:
                entry.unlink()
                removed.append(entry.name)
    return removed


def summarize(rows: Sequence[Sequence[str]], key_index: int) -> int:
    return len({row[key_index] for row in rows})


def main(argv: Optional[Sequence[str]] = None) -> int:
    global RENDER_TIMEOUT

    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Convert material-icon-theme into a One Commander icon pack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/build.py                  # render into pack/ with inkscape\n"
            "  python3 scripts/build.py --size 512       # size of the shipped pack\n"
            "  python3 scripts/build.py --check          # validate mappings, write nothing\n"
            "  python3 scripts/build.py --renderer copy  # reuse upstream PNGs instead of rendering\n"
        ),
    )
    parser.add_argument(
        "--material-icons",
        type=Path,
        default=VENDOR,
        help=f"material-icon-theme checkout or icons directory (default: {VENDOR})",
    )
    parser.add_argument(
        "--manifest-json",
        type=Path,
        help="read a generated material-icons.json instead of the TypeScript definitions",
    )
    parser.add_argument(
        "--renderer",
        default="auto",
        choices=sorted(RENDERERS) + ["auto"],
        help="renderer (default: auto — inkscape, rsvg-convert, cairosvg, imagemagick, copy)",
    )
    parser.add_argument(
        "--size",
        type=parse_size,
        default=(512, 512),
        help="output size, e.g. 256 or 256x256 (default: 512x512)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO / "pack",
        help=f"output directory (default: {REPO / 'pack'})",
    )
    parser.add_argument("--pack-name", default="MaterialIconTheme", help="icon pack directory name")
    parser.add_argument(
        "--mappings-dir",
        type=Path,
        default=REPO / "mappings",
        help=f"where file-icons.tsv / folder-icons.tsv live (default: {REPO / 'mappings'})",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=REPO / "dist" / "pack.json",
        help=f"build manifest path (default: {REPO / 'dist' / 'pack.json'})",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help=(
            "worker processes (default: 1 for inkscape — concurrent instances are unstable "
            "on some systems and the batch mode is fast; min(16, CPU) otherwise)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=RENDER_TIMEOUT,
        help=f"per-command timeout in seconds (default {RENDER_TIMEOUT:.0f})",
    )
    parser.add_argument("--only", choices=("all", "files", "folders"), default="all", help="render file icons, folder icons, or both")
    parser.add_argument("--force", action="store_true", help="re-render even when a correct PNG exists")
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="serial retry rounds for icons that failed during parallel rendering (default 2)",
    )
    parser.add_argument("--prune", action="store_true", help="delete unmapped PNGs and numbered cache dirs")
    parser.add_argument("--max-name-len", type=int, default=MAX_NAME_LEN, help="maximum icon file name length")
    parser.add_argument(
        "--thumbnail",
        choices=("auto", "none", "force"),
        default="auto",
        help="Thumbnail.png policy: auto (create when missing), none, force",
    )
    parser.add_argument(
        "--thumbnail-icons",
        default=",".join(DEFAULT_THUMBNAIL_ICONS),
        help="comma separated Material icon names used for the thumbnail",
    )
    parser.add_argument("--no-manifest", action="store_true", help="do not write the build manifest")
    parser.add_argument("--check", action="store_true", help="validate mappings and PNGs against the source, write nothing")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    parser.add_argument("--limit", type=int, default=0, help="render at most N icons (debug/smoke runs)")
    args = parser.parse_args(argv)

    RENDER_TIMEOUT = args.timeout

    out_dir: Path = args.out.resolve()
    icons_dir: Optional[Path] = None
    material_root: Optional[Path] = None

    # ---- 1. 关联定义 ----------------------------------------------------- #
    if args.manifest_json:
        manifest_path = args.manifest_json.resolve()
        if not manifest_path.is_file():
            raise SystemExit(f"{manifest_path}: file not found")
        file_specs, folder_specs, meta = load_from_manifest(manifest_path)
        candidate = manifest_path.parent
        icons_dir = next(
            (path for path in (candidate.parent / "icons", candidate / "icons") if path.is_dir()),
            None,
        )
        material_root = candidate.parent if (candidate.parent / "package.json").is_file() else None
    else:
        if not args.material_icons:
            raise SystemExit("need --material-icons (repo root or icons dir) or --manifest-json")
        given = args.material_icons.resolve()
        if not given.exists():
            raise SystemExit(f"{given}: path does not exist")
        if (given / "src").is_dir() or (given / "fileIcons.ts").is_file():
            material_root = given
            file_specs, folder_specs, meta = load_from_definitions(given)
            icons_dir = given / "icons" if (given / "icons").is_dir() else given
        else:
            # 指向 icons 目录（或任意含 SVG 的目录）时，向上找仓库定义
            icons_dir = given
            root = given.parent if given.name == "icons" else given
            file_specs, folder_specs, meta = load_from_definitions(root)
            material_root = root if (root / "src").is_dir() else None

    material_version = read_material_version(material_root)

    # ---- 2. 映射 --------------------------------------------------------- #
    file_rows, file_skips = build_file_mapping(file_specs, args.max_name_len)
    folder_rows, folder_skips = build_folder_mapping(folder_specs)

    if not args.quiet:
        print(f"material-icon-theme: {material_version or 'unknown version'}")
        print(f"source: {meta['source']} ({meta['definitions']})")
        print(
            f"file icons: {summarize(file_rows, 0)} icons -> {len(file_rows)} PNGs, "
            f"covering {len({t for row in file_rows for t in row[2].split(',')})} tokens"
        )
        print(f"folder icons: {summarize(folder_rows, 0)} icons -> {len(folder_rows)} PNGs")

    # ---- 3. 校验模式 ----------------------------------------------------- #
    if args.check:
        return run_check(
            out_dir,
            args.mappings_dir,
            args.pack_name,
            file_rows if args.only in ("all", "files") else [],
            folder_rows if args.only in ("all", "folders") else [],
            args.size,
            args.quiet,
        )

    # ---- 4. 渲染 --------------------------------------------------------- #
    renderer, notes = pick_renderer(args.renderer)
    jobs = args.jobs or (1 if renderer.prefer_single_process else min(16, os.cpu_count() or 4))
    if not args.quiet:
        for note in notes:
            print(note)
        batch_note = " (batched)" if renderer.supports_batch else ""
        print(
            f"renderer: {renderer.name}{batch_note}, size: {args.size[0]}x{args.size[1]}, "
            f"workers: {jobs}"
        )

    prefer_svg = renderer.name != "copy"
    file_dir = out_dir / "FileIcons" / args.pack_name
    folder_dir = out_dir / "FolderIcons" / args.pack_name

    all_failures: List[Tuple[str, str, str]] = []
    missing_total = 0
    started = time.time()

    for kind, rows, target_dir in (
        ("file", file_rows, file_dir),
        ("folder", folder_rows, folder_dir),
    ):
        if args.only != "all" and args.only != kind + "s":
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        render_rows = rows[: args.limit] if args.limit else rows
        tasks, stats = collect_tasks(render_rows, kind, target_dir, icons_dir, prefer_svg)
        missing_total += stats["missing-asset"]
        if not args.quiet and stats["missing-asset"]:
            print(f"  {stats['missing-asset']} icons have no asset in {icons_dir}, skipped")
        rendered, skipped, failures = run_render(
            tasks, renderer, args.size, jobs, args.force, args.quiet, args.retries
        )
        if not args.quiet:
            print(f"  {kind}: rendered {rendered}, cached {skipped}, failed {len(failures)}")
        all_failures.extend((kind, task.icon, message) for task, message in failures)

    # ---- 5. 映射表 / 构建信息 ------------------------------------------- #
    mappings_dir: Path = args.mappings_dir.resolve()
    mappings_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(mappings_dir / FILE_TSV_NAME, TSV_FILE_HEADER, file_rows)
    write_tsv(mappings_dir / FOLDER_TSV_NAME, TSV_FOLDER_HEADER, folder_rows)

    # ---- 6. 预览图 ------------------------------------------------------- #
    for kind, kind_dir in (("file", file_dir), ("folder", folder_dir)):
        if not kind_dir.is_dir():
            continue
        target = kind_dir / "Thumbnail.png"
        if args.thumbnail == "none":
            continue
        if args.thumbnail == "auto" and target.is_file():
            continue
        sources = []
        for name in [part.strip() for part in args.thumbnail_icons.split(",") if part.strip()]:
            asset = resolve_asset(name, kind, icons_dir, False)
            if asset and asset.path.is_file():
                sources.append(asset.path)
        if len(sources) < 2:
            continue
        try:
            make_thumbnail(sources, target, (420, 280))
            if not args.quiet:
                print(f"  thumbnail: {target.relative_to(out_dir)}")
        except Exception as error:  # noqa: BLE001
            print(f"  thumbnail failed ({target.name}): {error}", file=sys.stderr)

    # ---- 7. 清理 --------------------------------------------------------- #
    if args.prune:
        removed_files = prune(file_dir, {row[1] for row in file_rows}, ("Thumbnail.png",))
        removed_folders = prune(folder_dir, {row[2] for row in folder_rows}, ("Thumbnail.png",))
        if not args.quiet:
            print(f"  pruned {len(removed_files)} file icons and {len(removed_folders)} folder icons")

    # ---- 8. pack.json ---------------------------------------------------- #
    if not args.no_manifest:
        manifest = {
            "pack": args.pack_name,
            "source": "material-icon-theme",
            "sourceVersion": material_version,
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "generator": "build-pack.py",
            "renderer": renderer.name,
            "size": [args.size[0], args.size[1]],
            "counts": {
                "fileIcons": summarize(file_rows, 0),
                "filePngs": len(file_rows),
                "folderIcons": summarize(folder_rows, 0),
                "folderPngs": len(folder_rows),
                "extensions": len({t for row in file_rows for t in row[2].split(",")}),
            },
            "skipped": {
                "file": dict(sorted(file_skips.items())),
                "folder": dict(sorted(folder_skips.items())),
            },
        }
        manifest_path: Path = args.manifest_out.resolve()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # ---- 9. 汇总 --------------------------------------------------------- #
    elapsed = time.time() - started
    if not args.quiet:
        print(
            f"done: {len(file_rows)} + {len(folder_rows)} PNGs, "
            f"{elapsed:.1f}s, output {out_dir}"
        )
        if missing_total:
            print(f"note: {missing_total} icons have no asset (clone icons need upstream generateClones)")
    if all_failures:
        print(f"{len(all_failures)} icon(s) failed:", file=sys.stderr)
        for kind, icon, message in all_failures[:20]:
            print(f"  [{kind}] {icon}: {message}", file=sys.stderr)
        return 1
    return 0


def run_check(
    out_dir: Path,
    mappings_dir: Path,
    pack_name: str,
    file_rows: Sequence[Tuple[str, str, str]],
    folder_rows: Sequence[Tuple[str, str, str]],
    size: Tuple[int, int],
    quiet: bool,
) -> int:
    """对比磁盘上的映射表与 PNG，报告差异。"""
    problems = 0
    for label, rows, tsv_name, dir_name, name_index in (
        ("file icons", file_rows, FILE_TSV_NAME, "FileIcons", 1),
        ("folder icons", folder_rows, FOLDER_TSV_NAME, "FolderIcons", 2),
    ):
        if not rows:  # --only 限制的类别不校验
            continue
        existing = read_tsv(mappings_dir / tsv_name)
        if not existing:
            print(f"{label}: {tsv_name} is missing or empty (normal on a first run)")
        else:
            old_set, new_set = set(existing), {tuple(row) for row in rows}
            added, removed = new_set - old_set, old_set - new_set
            if added or removed:
                problems += 1
                print(f"{label}: mapping drifted from the source (+{len(added)} / -{len(removed)} rows)")
                for row in sorted(added)[:5]:
                    print(f"  + {row[0]} → {row[name_index]}")
                for row in sorted(removed)[:5]:
                    print(f"  - {row[0]} → {row[name_index]}")
            elif not quiet:
                print(f"{label}: mapping matches the source ({len(rows)} rows)")

        target_dir = out_dir / dir_name / pack_name
        missing, wrong_size = [], []
        for row in rows:
            png = target_dir / row[name_index]
            if not png.is_file():
                missing.append(row[name_index])
                continue
            current = png_size(png)
            if current != size:
                wrong_size.append((row[name_index], current))
        if missing:
            problems += 1
            print(f"{label}: {len(missing)} PNGs missing (e.g. {', '.join(missing[:3])})")
        if wrong_size:
            problems += 1
            sample = ", ".join(f"{name}={dims}" for name, dims in wrong_size[:3])
            print(f"{label}: {len(wrong_size)} PNGs are not {size[0]}x{size[1]} (e.g. {sample})")
        if not missing and not wrong_size and not quiet:
            print(f"{label}: all PNGs present with the expected size ({len(rows)})")

    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
