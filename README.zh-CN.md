# Material 图标包（One Commander 版）

把 [`vscode-material-icon-theme`](https://github.com/material-extensions/vscode-material-icon-theme)
的图标转换成 [One Commander](https://onecommander.com/) 可直接使用的图标包。

One Commander 的规则是：**文件图标按「扩展名列表」命名**（`py,pyw.png`），
**文件夹图标按「真实文件夹名」命名**（`src.png`）。本项目把 Material 的关联关系重写成
这种形式，并按 512×512 从上游 SVG 渲染全部图标。

![预览](docs/preview.png)

## 内容

| 项目    | 数值                                                                 |
| ----- | ------------------------------------------------------------------ |
| 上游版本  | `vscode-material-icon-theme` **v5.39.0**（固定在 `upstream.lock.json`） |
| 文件图标  | **403** 个 PNG，覆盖 **1308** 个扩展名/文件名 token（来自 380 个 Material 图标）     |
| 文件夹图标 | **925** 个 PNG（来自 264 个 Material 文件夹图标）                             |
| 默认文件夹图标 | **1** 个 PNG（`MainFolderIcon/MaterialIconTheme.png`，用于 *Default folder icon*） |
| 尺寸    | 图标包为 512×512 RGBA，默认文件夹图标为 64×64，另有 2 张 420×280 `Thumbnail.png` |
| 构建依赖  | Python 3.10+（纯标准库）与 Inkscape 1.x                                   |

## 安装

### 用 Release 包（推荐）

1. 下载 `MaterialIconTheme-<version>.zip` 并解压（`<version>` 是去掉前导 `v` 的 release
   tag，例如 `MaterialIconTheme-1.1.0.zip`）。Release 页面只提供该压缩包与 `SHA256SUMS`，
   授权声明文件都在压缩包内；
2. 复制图标包与默认文件夹图标：
   - `FileIcons\MaterialIconTheme` → `<OneCommander>\Resources\FileIcons\`
   - `FolderIcons\MaterialIconTheme` → `<OneCommander>\Resources\FolderIcons\`
   - `MainFolderIcon\MaterialIconTheme.png` → `<OneCommander>\Resources\MainFolderIcon\`
     （这是一个单独的 PNG，不是图标包目录；目录不存在就新建）
3. 重启 One Commander，打开 **Settings → Theme**，把 *File icons pack*、*Folder icon pack*
   与 *Default folder icon* 都选成 `MaterialIconTheme`。

`MainFolderIcon` 是 One Commander 对「没有匹配到具体文件夹名」的文件夹使用的全局兜底图标；
它独立于 `FolderIcons\MaterialIconTheme`，在同一个 Settings → Theme 对话框里选择。

`<OneCommander>` 位置：

| 安装方式 | 路径 |
| --- | --- |
| MSI 安装版 | `%LOCALAPPDATA%\OneCommander` |
| 便携版 | 解压出来的 `OneCommander` 目录 |
| Microsoft Store 版 | **About → Settings Location** 里显示的数据目录 |

如果下拉框里没出现，关掉设置窗口再打开一次。

### PowerShell 安装

```powershell
.\scripts\install.ps1                       # 默认 MSI 安装路径
.\scripts\install.ps1 -Target D:\Apps\OneCommander
.\scripts\install.ps1 -DryRun               # 只打印将要执行的操作
```

旧的 `MaterialIconTheme` 会被改名为 `MaterialIconTheme.bak`，卸载时自动恢复：

```powershell
.\scripts\uninstall.ps1
```

## 从源码构建

```bash
git clone https://github.com/<your-org>/one-commander-material-icon-pack.git
cd one-commander-material-icon-pack

make check     # 校验 mappings/ 与 pack/、vendor 上游是否一致（秒级）
make build     # 重新渲染 1329 个 PNG 到 pack/（需要 Inkscape）
make verify    # 尺寸、文件名、预览图、默认文件夹图标、映射与文件一致性
make notices   # 校验许可声明；dist/ 里已有 zip 时连包内声明一起查
make dist      # 构建 + 校验 + dist/MaterialIconTheme-<version>.zip 与 SHA256SUMS
```

`vendor/material-icon-theme/` 里固定了上游的 SVG、两个 TypeScript 定义文件与
`package.json`，因此构建完全离线；`make vendor` 会按 tag 重新拉取，但会保留
`icons/folder.svg`——它是上游 npm 构建生成、不在 git tag 里的默认文件夹图标。

没有 Inkscape 时可以直接复用上游 PNG：

```bash
python3 scripts/build.py --renderer copy --size 512
```

默认文件夹图标只有 SVG，所以 `--renderer copy` 会为这一个文件自动回退到可用的 SVG 渲染器。

## 命名规则

- **文件图标**：一个 Material 图标收集它能覆盖的扩展名，输出一个以逗号连接命名的 PNG
  （`py,pyw.png`、`ts,tsx.png`）。点文件名优先认领（`.gitignore` → `gitignore`），
  其余按定义顺序认领，一个 token 只属于一个图标。
- 超过 100 字符的文件名会拆成多个同内容副本（One Commander 的文件名上限）。
- 会与 Windows 设备名冲突的 token（`con`、`nul`、`com1`…）直接跳过。
- **文件夹图标**：先让「图标名后缀 == 文件夹名」的图标认领（`folder-src` → `src.png`），
  其余别名按定义顺序认领（`folder-vuex-store` → `stores.png`）。
- **默认文件夹图标**：`MainFolderIcon/MaterialIconTheme.png`，由上游默认的
  `icons/folder.svg`（Material 蓝灰纯文件夹）按 64×64 渲染；直接放进
  `Resources\MainFolderIcon\`，文件名就是 *Default folder icon* 下拉框里的名字。

两张映射表是确定性生成的，并且**提交进仓库**，任何改动都能在 diff 里看到。细节见
[docs/mappings.md](docs/mappings.md) 与 [docs/one-commander.md](docs/one-commander.md)。

## 目录结构

```
├── docs/                        # 映射、One Commander、许可说明与 README 预览图
├── mappings/                    # 生成并提交的映射表（TSV）
├── pack/                        # 生成并提交的图标包（可直接复制）
│   ├── FileIcons/MaterialIconTheme/
│   ├── FolderIcons/MaterialIconTheme/
│   └── MainFolderIcon/MaterialIconTheme.png
├── LICENSES/                    # 随每个副本一起分发的第三方许可全文
├── scripts/                     # build.py、verify.py、package.sh、check-notices.sh、install/uninstall.ps1 …
├── vendor/material-icon-theme/  # 固定的上游子集（SVG + TS 定义）
├── .github/workflows/           # CI（check/verify/notices/package）、Release（打 tag 出 zip）、上游监控
├── dist/                        # 构建清单、zip 与 SHA256SUMS（不入库）
└── Makefile
```

## 更新上游

```bash
# 先改 upstream.lock.json 里的 tag/version
make vendor
make check      # 查看映射表变化
make build
make verify
make dist
```

## 被跳过的图标

只在上游构建里以 clone 形式生成的图标（`nest-*`、`angular-*`、`advpl-*` 等）在本仓库没有
源 SVG，会被跳过；`dist/pack.json` 的 `skipped` 字段会列出原因。没有任何可用扩展名或
文件夹名 token 的图标同理。

## 许可

**MIT。** 生成脚本、映射表与文档是本项目的成果；图标是 Material Extensions 的 Material
Icon Theme（MIT）的衍生作品，沿用同一套条款。

- [`LICENSE`](LICENSE) — MIT，`Copyright (c) 2026 PakerYu` 与 `Copyright (c) 2025 Material Extensions`
- [`ATTRIBUTION.md`](ATTRIBUTION.md) — 各部分来源、范围与商标说明
- [`LICENSES/`](LICENSES/README.md) — 第三方许可全文，随每个发布包一起分发
- [`docs/licensing.md`](docs/licensing.md) — 为什么选 MIT，以及被排除的选项

MIT 要求版权声明随每个副本一起分发，所以发布 zip 里和图标放在一起的是 `LICENSE`、
`ATTRIBUTION.md` 和 `LICENSES/material-icon-theme-MIT.txt`。这份声明一旦漂移，`make notices`
（CI 也会跑）就会失败。

图标里的第三方产品名称与标志归各自所有者，仅用于标识文件类型；One Commander 与 Material
Design 都是描述性提及，本项目与它们没有隶属或背书关系。

---

[English](README.md)
