<#
.SYNOPSIS
    Install the MaterialIconTheme pack into One Commander.

.DESCRIPTION
    Copies FileIcons\MaterialIconTheme and FolderIcons\MaterialIconTheme into the
    One Commander resources directory, and MainFolderIcon\MaterialIconTheme.png into
    Resources\MainFolderIcon. Existing packs/files are moved aside to *.bak.

.PARAMETER Target
    One Commander install directory. Defaults to
    %LOCALAPPDATA%\OneCommander (MSI install). For the portable build pass the
    extracted OneCommander folder.

.PARAMETER DryRun
    Print what would happen without touching anything.

.EXAMPLE
    .\scripts\install.ps1
    .\scripts\install.ps1 -Target "D:\Apps\OneCommander" -DryRun
#>
[CmdletBinding()]
param(
    [string]$Target = (Join-Path $env:LOCALAPPDATA 'OneCommander'),
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Pack = Join-Path $Repo 'pack'

if (-not (Test-Path (Join-Path $Pack 'FileIcons\MaterialIconTheme'))) {
    throw "pack not found: run 'make build' first ($Pack)"
}
$mainSource = Join-Path $Pack 'MainFolderIcon\MaterialIconTheme.png'
if (-not (Test-Path $mainSource)) {
    throw "MainFolderIcon not found: run 'make build' first ($mainSource)"
}
if (-not (Test-Path (Join-Path $Target 'Resources'))) {
    throw "not a One Commander directory (Resources\ missing): $Target"
}

foreach ($kind in 'FileIcons', 'FolderIcons') {
    $source = Join-Path $Pack "$kind\MaterialIconTheme"
    $destDir = Join-Path $Target "Resources\$kind"
    $dest = Join-Path $destDir 'MaterialIconTheme'

    Write-Host "install $kind -> $dest"
    if ($DryRun) { continue }

    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    if (Test-Path $dest) {
        $backup = "$dest.bak"
        if (Test-Path $backup) { Remove-Item -Recurse -Force $backup }
        Move-Item -Path $dest -Destination $backup
        Write-Host "  previous pack moved to $(Split-Path -Leaf $backup)"
    }
    Copy-Item -Path $source -Destination $dest -Recurse
}

$mainDestDir = Join-Path $Target 'Resources\MainFolderIcon'
$mainDest = Join-Path $mainDestDir 'MaterialIconTheme.png'
Write-Host "install MainFolderIcon -> $mainDest"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $mainDestDir | Out-Null
    if (Test-Path $mainDest) {
        $mainBackup = "$mainDest.bak"
        if (Test-Path $mainBackup) { Remove-Item -Force $mainBackup }
        Move-Item -Path $mainDest -Destination $mainBackup
        Write-Host "  previous file moved to $(Split-Path -Leaf $mainBackup)"
    }
    Copy-Item -Path $mainSource -Destination $mainDest
}

Write-Host ''
Write-Host 'Restart One Commander, then open Settings -> Theme and pick:'
Write-Host '  File icons pack:      MaterialIconTheme'
Write-Host '  Folder icon pack:     MaterialIconTheme'
Write-Host '  Default folder icon:  MaterialIconTheme'
if ($DryRun) { Write-Host '(dry run, nothing changed)' }
