# HD Hunter Font: builds the mod from your own game files and installs it into the recomp's mods folder.
#   .\build.ps1                     (repo inside the recomp folder, or run from the recomp folder)
#   .\build.ps1 -Game 'D:\MHGURecomp'
# Pages you upscaled yourself (upscale\upscaled\font_festa_NN.png, see export.ps1) replace the built-in upscale.
param([string]$Game = '')

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
if (-not $Game) {
    foreach ($c in @((Split-Path -Parent $repo), (Get-Location).Path)) {
        if (Test-Path (Join-Path $c 'mhgurecomp.exe')) { $Game = $c; break }
    }
}
if (-not $Game -or -not (Test-Path (Join-Path $Game 'mhgurecomp.exe'))) {
    throw 'MHGU Recomp not found: put this folder inside the recomp folder, or pass -Game <recomp folder>.'
}

# The HD mod replaces the same archive, so build on top of its copy when it is installed.
$hd = Join-Path $Game 'mods\HD\romfs\nativeNX\loc\arc\resident.arc'
$vanilla = Join-Path $Game 'data\romfs\nativeNX\loc\arc\resident.arc'
$base = if (Test-Path $hd) { $hd } else { $vanilla }
if (-not (Test-Path $base)) { throw "Game files not found: $vanilla" }
Write-Host "Base archive: $base"

python -I -c "import numpy" 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Python 3 with numpy is needed: pip install numpy' }

$tmp = Join-Path $env:TEMP 'hd-hunter-font-build'
New-Item -ItemType Directory -Force $tmp | Out-Null
python -I "$repo\tools\build_font2x.py" $base "$tmp\resident.arc" --scale-floats --sharp=0.25 --bc3 `
    "--pages-dir=$repo\upscale\upscaled" "--gfd-out=$tmp\font_festa.gfd"
if ($LASTEXITCODE -ne 0) { throw 'Build failed: nothing installed.' }

# zz- so it loads after the HD mod (both replace resident.arc)
$mod = Join-Path $Game 'mods\zz-hd-hunter-font\romfs\nativeNX'
New-Item -ItemType Directory -Force "$mod\loc\arc", "$mod\eng\GUI\02_common\font" | Out-Null
Copy-Item "$tmp\resident.arc" "$mod\loc\arc\resident.arc" -Force
# the English game reads this loose glyph table, not the copy inside resident.arc
Copy-Item "$tmp\font_festa.gfd" "$mod\eng\GUI\02_common\font\font_festa.gfd" -Force
Write-Host "Installed to $(Split-Path (Split-Path $mod))"
