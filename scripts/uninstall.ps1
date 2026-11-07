<#
.SYNOPSIS
    Remove the MaterialIconTheme pack from One Commander.

.DESCRIPTION
    Deletes Resources\FileIcons\MaterialIconTheme,
    Resources\FolderIcons\MaterialIconTheme and
    Resources\MainFolderIcon\MaterialIconTheme.png. If a *.bak backup from
    install.ps1 exists it is restored.

.PARAMETER Target
    One Commander install directory (default: %LOCALAPPDATA%\OneCommander).

.PARAMETER DryRun
    Print what would happen without touching anything.
#>
[CmdletBinding()]
param(
    [string]$Target = (Join-Path $env:LOCALAPPDATA 'OneCommander'),
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path (Join-Path $Target 'Resources'))) {
    throw "not a One Commander directory (Resources\ missing): $Target"
}

foreach ($kind in 'FileIcons', 'FolderIcons') {
    $dest = Join-Path $Target "Resources\$kind\MaterialIconTheme"
    $backup = "$dest.bak"

    if (Test-Path $dest) {
        Write-Host "remove $dest"
        if (-not $DryRun) { Remove-Item -Recurse -Force $dest }
    }
    if (Test-Path $backup) {
        Write-Host "restore $backup"
        if (-not $DryRun) { Move-Item -Path $backup -Destination $dest }
    }
}

$mainDest = Join-Path $Target 'Resources\MainFolderIcon\MaterialIconTheme.png'
$mainBackup = "$mainDest.bak"
if (Test-Path $mainDest) {
    Write-Host "remove $mainDest"
    if (-not $DryRun) { Remove-Item -Force $mainDest }
}
if (Test-Path $mainBackup) {
    Write-Host "restore $mainBackup"
    if (-not $DryRun) { Move-Item -Path $mainBackup -Destination $mainDest }
}

Write-Host 'Restart One Commander and choose another icon pack in Settings -> Theme.'
if ($DryRun) { Write-Host '(dry run, nothing changed)' }
