# Builds the release zip from your own game files (needs Python 3 + numpy).
#   tools\make_release.ps1 -Game <recomp folder> [-Version 1.0.0]
# A hand-upscaled page 00 in upscale\upscaled\font_festa_00.png is used when present.
param([Parameter(Mandatory)][string]$Game, [string]$Version = '1.0.0')

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$base = Join-Path $Game 'data\romfs\nativeNX\loc\arc\resident.arc'
if (-not (Test-Path $base)) { throw "Game files not found: $base" }
$tmp = Join-Path $env:TEMP 'hd-hunter-font-release'
New-Item -ItemType Directory -Force $tmp, "$repo\dist" | Out-Null
python -I "$PSScriptRoot\build_font2x.py" $base "$tmp\resident.arc" --scale-floats --sharp=0.25 --bc3 `
    "--pages-dir=$repo\upscale\upscaled" "--gfd-out=$tmp\font_festa.gfd"
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
python -I "$PSScriptRoot\make_release.py" "$tmp\resident.arc" "$tmp\font_festa.gfd" "$repo\mod" "$repo\dist\hd-hunter-font-v$Version.zip"
if ($LASTEXITCODE -ne 0) { throw 'Packing failed.' }
