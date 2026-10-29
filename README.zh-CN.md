# Material 图标包（One Commander 版）

把 [`vscode-material-icon-theme`](https://github.com/material-extensions/vscode-material-icon-theme)
的图标转换成 [One Commander](https://onecommander.com/) 可直接使用的图标包。

One Commander 的规则是：**文件图标按「扩展名列表」命名**（`py,pyw.png`），
**文件夹图标按「真实文件夹名」命名**（`src.png`）。本项目把 Material 的关联关系重写成
这种形式，并按 512×512 从上游 SVG 渲染全部图标。

![预览](docs/preview.png)

## 内容

| 项目 | 数值 |
| --- | --- |
| 上游版本 | `vscode-material-icon-theme` **v5.39.0**（固定在 `upstream.lock.json`） |
| 文件图标 | **403** 个 PNG，覆盖 **1308** 个扩展名/文件名 token（来自 380 个 Material 图标） |
| 文件夹图标 | **925** 个 PNG（来自 264 个 Material 文件夹图标） |
| 尺寸 | 512×512 RGBA，另有 2 张 420×280 `Thumbnail.png` |
| 构建依赖 | Python 3.10+（纯标准库）与 Inkscape 1.x |

## 安装

### 用 Release 包（推荐）

1. 下载 `MaterialIconTheme-1.0.0.zip` 并解压；
2. 复制两个目录：
   - `FileIcons\MaterialIconTheme` → `<OneCommander>\Resources\FileIcons\`
   - `FolderIcons\MaterialIconTheme` → `<OneCommander>\Resources\FolderIcons\`
3. 重启 One Commander，打开 **Settings → Theme**，把 *File icons pack* 与
   *Folder icon pack* 都选成 `MaterialIconTheme`。

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
make build     # 重新渲染 1328 个 PNG 到 pack/（需要 Inkscape）
make verify    # 尺寸、文件名、预览图、映射与文件一致性
make dist      # 生成 dist/MaterialIconTheme-<version>.zip
```

`vendor/material-icon-theme/` 里固定了上游的 SVG、两个 TypeScript 定义文件与
`package.json`，因此构建完全离线；`make vendor` 会按 tag 重新拉取。

没有 Inkscape 时可以直接复用上游 PNG：

```bash
python3 scripts/build.py --renderer copy --size 512
```

## 命名规则

- **文件图标**：一个 Material 图标收集它能覆盖的扩展名，输出一个以逗号连接命名的 PNG
  （`py,pyw.png`、`ts,tsx.png`）。点文件名优先认领（`.gitignore` → `gitignore`），
  其余按定义顺序认领，一个 token 只属于一个图标。
- 超过 100 字符的文件名会拆成多个同内容副本（One Commander 的文件名上限）。
- 会与 Windows 设备名冲突的 token（`con`、`nul`、`com1`…）直接跳过。
- **文件夹图标**：先让「图标名后缀 == 文件夹名」的图标认领（`folder-src` → `src.png`），
  其余别名按定义顺序认领（`folder-vuex-store` → `stores.png`）。

两张映射表是确定性生成的，并且**提交进仓库**，任何改动都能在 diff 里看到。细节见
[docs/mappings.md](docs/mappings.md) 与 [docs/one-commander.md](docs/one-commander.md)。

## 目录结构

```
├── docs/                        # 映射与 One Commander 说明、README 预览图
├── mappings/                    # 生成并提交的映射表（TSV）
├── pack/                        # 生成并提交的图标包（可直接复制）
│   ├── FileIcons/MaterialIconTheme/
│   └── FolderIcons/MaterialIconTheme/
├── scripts/                     # build.py、verify.py、package.sh、install/uninstall.ps1 …
├── vendor/material-icon-theme/  # 固定的上游子集（SVG + TS 定义）
├── .github/workflows/           # CI（check+verify）与 Release（打 tag 出 zip）
├── dist/                        # 构建清单与 zip（不入库）
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

MIT，见 [LICENSE](LICENSE)。图标衍生自 Material Extensions 的 Material Icon Theme，
详见 [ATTRIBUTION.md](ATTRIBUTION.md)。

---

[English](README.md)
