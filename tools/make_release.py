"""Packs a release: the font pages out of a built resident.arc (still zlib-compressed, as install.ps1 splices them
in), the glyph table, and the installer, as zz-hd-hunter-font/ in a zip.
Usage: make_release.py <built resident.arc> <font_festa.gfd> <mod dir with install.ps1> <out zip>"""
import os, struct, sys, zipfile

arc, gfd, mod_src, out_zip = sys.argv[1:5]
d = open(arc, 'rb').read()
n = struct.unpack_from('<H', d, 6)[0]
pages = []
for i in range(n):
    o = 12 + i * 80
    name = d[o:o + 64].split(b'\0')[0].decode()
    typ, csz, dsz, off = struct.unpack_from('<IIII', d, o + 64)
    base = name.split(chr(92))[-1]
    if base.startswith('font_festa_') and base.endswith('_HQ'):
        pages.append((name, dsz & 0x1FFFFFFF, base + '.tex.z', d[off:off + csz]))
    elif base == 'font_festa':   # the archive's own copy of the glyph table (languages without a loose one)
        pages.append((name, dsz & 0x1FFFFFFF, base + '.gfd.z', d[off:off + csz]))
assert len(pages) == 11, 'expected 10 font pages and the glyph table, found %d' % len(pages)

root = 'zz-hd-hunter-font/'
with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_STORED) as z:   # pages are compressed already
    for f in ('install.bat', 'install.ps1', 'README.txt'):
        z.write(os.path.join(mod_src, f), root + f, zipfile.ZIP_DEFLATED)
    z.writestr(root + 'font/pages.txt', ''.join('%s|%d|%s\r\n' % (nm, size, fn) for nm, size, fn, _ in pages))
    for nm, size, fn, blob in pages:
        z.writestr(root + 'font/' + fn, blob)
    z.write(gfd, root + 'font/font_festa.gfd', zipfile.ZIP_DEFLATED)
print('wrote %s (%.1f MB)' % (out_zip, os.path.getsize(out_zip) / 1e6))
