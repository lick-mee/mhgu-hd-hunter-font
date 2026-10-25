# HD Hunter Font

Sharp, high-resolution in-game text for **Monster Hunter Generations Ultimate** on the PC recompilation (MHGU Recomp).

At 1440p and 4K the game stretches its Switch-sized font, so every menu, item name and dialogue line comes out soft and pixelly, even with HD texture packs. HD Hunter Font rebuilds the game's font at twice the resolution: same typeface, same layout, just crisp.

![Vanilla vs HD Hunter Font: the Bherna Chief's dialogue at 4K](docs/compare_dialogue.png)

*In game at 3840×2160, shown pixel for pixel. Same scene, same line.*

## What it does

- Doubles the resolution of all ten font pages (1024 → 2048), letter by letter, with no change of typeface.
- Keeps every letter's position, size, spacing and line placement exactly as in the original game.
- Uses **no extra video memory**: the pages are stored compressed (BC3), so a 2048 page takes what an original 1024 page did.
- Builds on top of the **HD** texture mod if you have it (both replace the same archive), or on the vanilla files if you don't.
- Optionally takes a font page you upscaled yourself (for example with Upscayl). See [Use your own upscale](#use-your-own-upscale).

No game files are included. The build script makes the mod from your own copy of the game.

## Requirements

- MHGU Recomp with your game dump in its `data` folder (version 1.4.0, as the recomp requires)
- Windows PowerShell
- Python 3 with numpy (`pip install numpy`)
- Optional: the HD texture mod in `mods\HD`

## Install

1. Download or clone this repository into your recomp folder (next to `mhgurecomp.exe`).
2. In that folder, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\build.ps1
   ```

   If the repository is somewhere else, add `-Game "D:\path\to\recomp"`.
3. Start the game.

The mod is installed as `mods\zz-hd-hunter-font`. The `zz-` prefix makes it load after the HD mod. **If you update or reinstall the HD mod, run `build.ps1` again.**

To uninstall, delete `mods\zz-hd-hunter-font`.

## Use your own upscale

The built-in upscale redraws each letter with smooth, sharp edges. If you'd like to use an AI upscaler instead:

1. Run `.\export.ps1`. It writes `upscale\original\font_festa_00.png`: 1024×1024, white letters on black. English only uses the top 176 rows (Latin, accented letters, Greek, Cyrillic, symbols). The rest of the page is kanji.
   `font_festa_00_glyph_boxes.png` shows every letter's box. Letters must stay inside their boxes.
2. Upscale it 2× or 4× with a **real upscaler**, such as Upscayl, chaiNNer, waifu2x or Real-ESRGAN. Upscayl's `digital-art-4x` model works well.
   Don't use an image *generator* (ChatGPT, Gemini…): those redraw the page and swap characters (`¼` becomes `½`, `¡` becomes `]`).
3. Save the result as `upscale\upscaled\font_festa_00.png`. It must be exactly 2048×2048 or 4096×4096, with no cropping or padding.
4. Run `.\build.ps1` again.

## How it works

For anyone curious, or modding other MT Framework games:

- **Font pages:** the font is ten 1024×1024 pages (`GUI\02_common\font\font_festa_00_HQ` to `_09_HQ` in `loc\arc\resident.arc`). On the Switch they're uncompressed RGBA8 in the Tegra block-linear layout. English uses only page 00.
- **Glyph table:** each letter's page, position, size and spacing live in `font_festa.gfd`. The English game reads a **loose** copy at `eng\GUI\02_common\font\font_festa.gfd`, not the one inside the archive, so both copies are patched.
- **Scaling:** the game sizes letters by their box ÷ the table's size field. Doubling the size field (24 → 48), every glyph box, the glyph offsets and the six line-metric floats after the size field gives a 2× font that lays out exactly like the original.
- **Memory:** as uncompressed RGBA8, ten 2048 pages need about 224 MB instead of 55 MB. That overflows memory the game shares with other textures, and armour starts rendering with garbage textures. Storing the pages as BC3 (DXT5: white colour block, fitted alpha block) brings them back to the original size exactly.
- **Upscaling:** each glyph is upscaled inside its own box, with a cubic filter followed by a steepened edge around 50% coverage. That keeps the outline and stroke weight while removing the blur.

## Limitations

- Only English is set up. French, German, Italian and Spanish each read their own loose `font_festa.gfd`.
- Text drawn into images (title logos, banners) and the big-monster intro names use other fonts and aren't changed.

## Credits

- Built for MHGU Recomp; uses the HD texture mod's archive as a base when it's installed.
- Monster Hunter Generations Ultimate © CAPCOM. This project contains no game assets.

## License

MIT for the code in this repository. See [LICENSE](LICENSE).
