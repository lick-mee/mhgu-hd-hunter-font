"""Export font_festa pages from a resident.arc as PNGs for upscaling: white glyphs on black, 1024x1024 gray.
Also writes a reference image of page 00 with every glyph box outlined (English uses only rows 0-175).
Usage: export_pages.py <resident.arc> <out dir> [pages, e.g. 0 or 0-9]"""
import os, struct, sys, zlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_font2x as B
from pngio import write_png

src, out = sys.argv[1], sys.argv[2]
sel = sys.argv[3] if len(sys.argv) > 3 else '0'
lo, hi = (int(v) for v in sel.split('-')) if '-' in sel else (int(sel), int(sel))
os.makedirs(out, exist_ok=True)
d = open(src, 'rb').read()
E = {}
for i in range(struct.unpack_from('<H', d, 6)[0]):
    o = 12 + i * 80
    name = d[o:o + 64].split(b'\0')[0].decode().split(chr(92))[-1]
    typ, csz, dsz, off = struct.unpack_from('<IIII', d, o + 64)
    if name.startswith('font_festa'):
        E[name] = zlib.decompress(d[off:off + csz])
boxes = B.glyph_boxes(E['font_festa'])
for pg in range(lo, hi + 1):
    t = E['font_festa_%02d_HQ' % pg]
    m, w, h, hdr, offs = B.tex_info(t)
    alpha = np.frombuffer(B.deswizzle(t[hdr + offs[0]:hdr + offs[1]], w, h), np.uint8)[3::4].reshape(h, w)
    write_png(os.path.join(out, 'font_festa_%02d.png' % pg), alpha)
    print('page', pg, w, 'x', h)
    if pg == 0:
        ref = np.repeat(alpha[:, :, None], 3, 2).copy()
        for x, y, bw, bh in boxes[0]:
            if bw and bh:
                ref[y, x:x + bw] = ref[y + bh - 1, x:x + bw] = (200, 40, 40)
                ref[y:y + bh, x] = ref[y:y + bh, x + bw - 1] = (200, 40, 40)
        write_png(os.path.join(out, 'font_festa_00_glyph_boxes.png'), ref[:176].repeat(2, 0).repeat(2, 1))
