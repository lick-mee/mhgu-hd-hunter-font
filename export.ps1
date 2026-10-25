# Exports font page 00 (the one English uses) to upscale\original, for upscaling it yourself.
#   .\export.ps1                    (or -Game <recomp folder>; -Pages 0-9 for every page)
param([string]$Game = '', [string]$Pages = '0')

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
if (-not $Game) {
    foreach ($c in @((Split-Path -Parent $repo), (Get-Location).Path)) {
        if (Test-Path (Join-Path $c 'mhgurecomp.exe')) { $Game = $c; break }
    }
}
if (-not $Game) { throw 'MHGU Recomp not found: pass -Game <recomp folder>.' }
$hd = Join-Path $Game 'mods\HD\romfs\nativeNX\loc\arc\resident.arc'
$base = if (Test-Path $hd) { $hd } else { Join-Path $Game 'data\romfs\nativeNX\loc\arc\resident.arc' }
python -I "$repo\tools\export_pages.py" $base "$repo\upscale\original" $Pages
if ($LASTEXITCODE -ne 0) { throw 'Export failed.' }
Write-Host "Exported to $repo\upscale\original"
