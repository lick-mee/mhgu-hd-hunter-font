# HD Hunter Font installer: puts the sharp font pages into your own resident.arc.
# The font pages live inside that archive (the game ignores them as loose files), so instead of shipping the
# whole archive, this copies yours - from the HD mod if you have it, else from the game - swaps in the font,
# and saves the result in this mod's romfs folder. Run it again after updating the HD mod.
#   install.bat                         (double-click)
#   install.ps1 -Source <resident.arc>  (use a specific archive, e.g. from an emulator romfs dump)
param([string]$Source = '')

$ErrorActionPreference = 'Stop'
$mod = $PSScriptRoot
$mods = Split-Path -Parent $mod
$rel = 'romfs\nativeNX\loc\arc\resident.arc'
$out = Join-Path $mod $rel

function Find-Source {
    # 1. another mod that replaces resident.arc (the HD mod), 2. the recomp's game files
    foreach ($d in Get-ChildItem -LiteralPath $mods -Directory) {
        $p = Join-Path $d.FullName $rel
        if ($d.FullName -ne $mod -and (Test-Path -LiteralPath $p)) { return $p }
    }
    $p = Join-Path (Split-Path -Parent $mods) "data\$rel"
    if (Test-Path -LiteralPath $p) { return $p }
    return $null
}

if (-not $Source) { $Source = Find-Source }
if (-not $Source) {
    Write-Host 'Could not find resident.arc (no HD mod next to this one, and no recomp data folder).'
    $Source = (Read-Host 'Path to your resident.arc (romfs\nativeNX\loc\arc\resident.arc)').Trim('"')
}
if (-not (Test-Path -LiteralPath $Source)) { throw "Not found: $Source" }
if ((Resolve-Path -LiteralPath $Source).Path -eq $out) { throw 'That is this mod''s own output; pick the original archive.' }
Write-Host "Base archive: $Source"

# Font pages and the archive's glyph table, already zlib-compressed as they sit in the archive:
# name|decompressed size|file
$font = Join-Path $mod 'font'
$pages = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $font 'pages.txt')) {
    if (-not $line.Trim()) { continue }
    $name, $size, $file = $line.Split('|')
    $pages[$name] = @{ Size = [uint32]$size; Data = [IO.File]::ReadAllBytes((Join-Path $font $file)) }
}

# MT Framework ARC: "ARC\0", u16 version, u16 count, u32; then 80-byte entries:
# name[64], type u32, compressed size u32, decompressed size | flags << 29 u32, offset u32
$arc = [IO.File]::ReadAllBytes($Source)
if ([Text.Encoding]::ASCII.GetString($arc, 0, 4) -ne "ARC`0") { throw "$Source is not an ARC file" }
$count = [BitConverter]::ToUInt16($arc, 6)
$dataStart = [BitConverter]::ToUInt32($arc, 12 + 76)
$header = New-Object byte[] $dataStart
[Array]::Copy($arc, $header, $dataStart)
$body = New-Object IO.MemoryStream
$replaced = 0
for ($i = 0; $i -lt $count; $i++) {
    $e = 12 + $i * 80
    $name = [Text.Encoding]::ASCII.GetString($arc, $e, 64).Split([char]0)[0]
    $csize = [BitConverter]::ToUInt32($arc, $e + 68)
    $dsize = [BitConverter]::ToUInt32($arc, $e + 72)
    $offset = [BitConverter]::ToUInt32($arc, $e + 76)
    if ($pages.ContainsKey($name)) {
        $p = $pages[$name]
        $bytes = $p.Data
        $dsize = ($dsize -band 0xE0000000) -bor $p.Size
        $replaced++
    } else {
        $bytes = New-Object byte[] $csize
        [Array]::Copy($arc, $offset, $bytes, 0, $csize)
    }
    [BitConverter]::GetBytes([uint32]$bytes.Length).CopyTo($header, $e + 68)
    [BitConverter]::GetBytes([uint32]$dsize).CopyTo($header, $e + 72)
    [BitConverter]::GetBytes([uint32]($dataStart + $body.Length)).CopyTo($header, $e + 76)
    $body.Write($bytes, 0, $bytes.Length)
}
if ($replaced -ne $pages.Count) { throw "Found $replaced of $($pages.Count) font files in $Source - is it MHGU's loc\arc\resident.arc?" }

New-Item -ItemType Directory -Force (Split-Path -Parent $out) | Out-Null
$fs = [IO.File]::Create($out)
$fs.Write($header, 0, $header.Length)
$body.WriteTo($fs)
$fs.Close()

# The English game reads its glyph table as a loose file, so it goes next to the archive's folder tree.
$gfd = Join-Path $mod 'romfs\nativeNX\eng\GUI\02_common\font'
New-Item -ItemType Directory -Force $gfd | Out-Null
Copy-Item -LiteralPath (Join-Path $font 'font_festa.gfd') -Destination $gfd -Force

Write-Host "Done: font installed. Start the game."
