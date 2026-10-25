"""Rebuild loc/arc/resident.arc with the font_festa pages at 2x and the glyph table doubled.

Follows what the HD mod did for button_festa (256 -> 512): GFD header +0x14 24 -> 48, glyph x/y/w/h doubled.
Usage: build_font2x.py <source resident.arc> <output resident.arc> --scale-floats --sharp[=edge]
       [--pages-dir=dir] [--gfd-out=path] [--marker] [--scale-ascent]
build.ps1 (repo root) runs it with the settings that work and installs the result.
"""
import os, struct, sys, zlib

TEX_TYPE, GFD_TYPE = 0x241F5DEB, 0x2D462600
MARKER = '--marker' in sys.argv          # bar under 'M' so you can tell the mod is active
SCALE_ASCENT = '--scale-ascent' in sys.argv  # also double c's top byte (20, same for every glyph)
# The game divides glyph x/y/w/h by (size / 24) when sampling festa, so doubling the size field cancels the 2x
# coordinates (in game: glyphs read from the wrong half-scale spot). Keep size 24 and leave layout (c, e) alone.
KEEP_SIZE = '--keep-size' in sys.argv
NO_GFD = '--no-gfd' in sys.argv  # diagnostic: leave the glyph table as it is
SCALE_FLOATS = '--scale-floats' in sys.argv  # also double the six header floats
# --sharp[=edge]: cubic 2x per glyph with a steepened edge (sharpen.py) instead of pixel doubling
SHARP_EDGE = next((float(a.split('=')[1]) if '=' in a else 0.25 for a in sys.argv if a.startswith('--sharp')), None)
# --gfd-out=path: also write the patched glyph table there (the English game reads a loose
# eng/GUI/02_common/font/font_festa.gfd, not the copy in resident.arc)
GFD_OUT = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--gfd-out=')), None)
# --pages-dir=dir: font_festa_NN.png found there (upscaled by hand, white glyphs on black) replace page NN
PAGES_DIR = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--pages-dir=')), None)
# --bc3: store the 2x pages compressed (1 byte/pixel, the original pages' size). As RGBA8 they take 4x the memory,
# which corrupts other textures in game (armour drawn with wrong/garbage textures).
BC3 = '--bc3' in sys.argv


def glyph_boxes(g):
    """{page: [(x, y, w, h)]} at 1x from an unpatched GFD."""
    n = struct.unpack_from('<I', g, 0x1C)[0]
    p = 0x48 + struct.unpack_from('<I', g, 0x44)[0] + 1
    boxes = {}
    for i in range(n):
        ch, a, b, c, e = struct.unpack_from('<5I', g, p + i * 20)
        boxes.setdefault(a & 0xFF, []).append(((a >> 8) & 0xFFF, a >> 20, b & 0xFFF, (b >> 12) & 0xFFF))
    return boxes


# ---- Tegra block-linear (GOB = 64 bytes x 8 rows) ----
def block_height(h):
    bh = 1
    while bh < 16 and bh * 8 < h:
        bh *= 2
    return bh


def swizzle(lin, w, h, bpp=4):
    wb = w * bpp
    bh = block_height(h)
    gobs_x = (wb + 63) // 64
    rows_pad = ((h + 8 * bh - 1) // (8 * bh)) * 8 * bh
    out = bytearray(gobs_x * 64 * rows_pad)
    for y in range(h):
        base = (y // (8 * bh)) * gobs_x * bh * 512 + ((y % (8 * bh)) // 8) * 512 + ((y % 8) // 2) * 64 + (y % 2) * 16
        row = y * wb
        for xb in range(0, wb, 16):
            o = base + (xb // 64) * bh * 512 + ((xb % 64) // 32) * 256 + ((xb % 32) // 16) * 32
            out[o:o + 16] = lin[row + xb:row + xb + 16]
    return bytes(out)


def deswizzle(sw, w, h, bpp=4):
    wb = w * bpp
    bh = block_height(h)
    gobs_x = (wb + 63) // 64
    out = bytearray(wb * h)
    for y in range(h):
        base = (y // (8 * bh)) * gobs_x * bh * 512 + ((y % (8 * bh)) // 8) * 512 + ((y % 8) // 2) * 64 + (y % 2) * 16
        row = y * wb
        for xb in range(0, wb, 16):
            o = base + (xb // 64) * bh * 512 + ((xb % 64) // 32) * 256 + ((xb % 32) // 16) * 32
            out[row + xb:row + xb + 16] = sw[o:o + 16]
    return bytes(out)


# ---- rTexture (NX): "TEX\0", u32, u32 mips|w<<6|h<<19, u32 fmt, u32 data size, u32 mip offsets[mips], data ----
def tex_info(t):
    w2 = struct.unpack_from('<I', t, 8)[0]
    mips, w, h = w2 & 63, (w2 >> 6) & 0x1FFF, w2 >> 19
    hdr = 0x14 + 4 * mips
    offs = list(struct.unpack_from('<%dI' % mips, t, 0x14)) + [struct.unpack_from('<I', t, 0x10)[0]]
    return mips, w, h, hdr, offs


def load_user_page(path, W, H, boxes):
    """A 2x page someone upscaled (any multiple of the 1x size; reduced to 2x by averaging). Coverage outside the
    glyph boxes is cleared, so upscaler bleed or noise can't show up next to a letter."""
    import os
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pngio import read_png, coverage
    a = coverage(read_png(path)).astype(np.float32)
    k = a.shape[1] / W
    if a.shape[0] / H != k or k < 1 or k != int(k):
        raise SystemExit('%s is %dx%d: it must be %dx%d (or 2x / 4x that)' % (path, a.shape[1], a.shape[0], W, H))
    k = int(k)
    if k > 1:
        a = a.reshape(H, k, W, k).mean((1, 3))
    keep = np.zeros((H, W), bool)
    for x, y, bw, bh in boxes:
        keep[2 * y:2 * y + 2 * bh, 2 * x:2 * x + 2 * bw] = True
    return np.where(keep, a, 0).round().clip(0, 255).astype(np.uint8)


def bc3_tex(t, alpha, W, H, mips):
    """rTexture in BC3 (format 0x17) from a 2x alpha page, with its own box-filtered mips."""
    import os
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bc3 import encode_alpha_blocks, mip_chain
    levels = mip_chain(np.frombuffer(alpha, np.uint8).reshape(H, W), mips)
    body, new_offs = b'', []
    for lv in levels:
        h, w = lv.shape
        if h < 4 or w < 4:
            lv = np.pad(lv, ((0, max(0, 4 - h)), (0, max(0, 4 - w))), mode='edge')
        blocks = encode_alpha_blocks(lv)
        new_offs.append(len(body))
        body += swizzle(blocks.tobytes(), lv.shape[1] // 4, lv.shape[0] // 4, bpp=16)
    w2 = mips | (W << 6) | (H << 19)
    head = t[0:8] + struct.pack('<I', w2) + t[12:13] + b'\x17' + t[14:16] + struct.pack('<I', len(body)) \
        + struct.pack('<%dI' % mips, *new_offs)
    return head + body


def upscale_tex(t, marker_rect=None, boxes=None, user_png=None):
    mips, w, h, hdr, offs = tex_info(t)
    assert t[0:4] == b'TEX\0' and t[13] == 0x07, 'expected RGBA8'
    data = t[hdr:]
    mip0 = deswizzle(data[offs[0]:offs[1]], w, h)
    assert swizzle(mip0, w, h) == data[offs[0]:offs[1]], 'swizzle round trip failed'
    W, H = w * 2, h * 2
    if user_png:
        import numpy as np
        rgba = np.full((H, W, 4), 255, np.uint8)
        rgba[:, :, 3] = load_user_page(user_png, W, H, boxes)
        big = bytearray(rgba.tobytes())
    elif boxes is not None:
        # sharp: the pages are white with the glyphs in alpha; redo the alpha glyph by glyph
        import os
        import numpy as np
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sharpen import upscale_page
        alpha = np.frombuffer(mip0, np.uint8)[3::4].reshape(h, w)
        rgba = np.full((H, W, 4), 255, np.uint8)
        rgba[:, :, 3] = upscale_page(alpha, boxes, SHARP_EDGE)
        big = bytearray(rgba.tobytes())
    else:
        big = bytearray(W * H * 4)
        for y in range(h):
            src_row = mip0[y * w * 4:(y + 1) * w * 4]
            dbl = bytearray(w * 8)
            for x in range(w):
                px = src_row[x * 4:x * 4 + 4]
                dbl[x * 8:x * 8 + 4] = px
                dbl[x * 8 + 4:x * 8 + 8] = px
            big[(2 * y) * W * 4:(2 * y + 1) * W * 4] = dbl
            big[(2 * y + 1) * W * 4:(2 * y + 2) * W * 4] = dbl
    if marker_rect:
        x, y, mw, mh = marker_rect
        for yy in range(y + mh - 4, y + mh - 1):
            for xx in range(x + 2, x + mw - 2):
                big[(yy * W + xx) * 4:(yy * W + xx) * 4 + 4] = b'\xff\xff\xff\xff'
    if BC3:
        return bc3_tex(t, bytes(big)[3::4], W, H, mips)
    new0 = swizzle(bytes(big), W, H)
    # 2x page keeps the same mip count: its mip n (n >= 1) is the original's mip n-1, byte for byte.
    sizes = [len(new0)] + [offs[i + 1] - offs[i] for i in range(mips - 1)]
    body = new0 + data[offs[0]:offs[mips - 1]]
    new_offs, o = [], 0
    for s in sizes:
        new_offs.append(o)
        o += s
    w2 = mips | (W << 6) | (H << 19)
    head = t[0:8] + struct.pack('<I', w2) + t[12:16] + struct.pack('<I', len(body)) + struct.pack('<%dI' % mips, *new_offs)
    return head + body


# ---- GFD: glyphs of 20 bytes: char, a = page | x<<8 | y<<20, b = w | h<<12 | flags<<24,
#      c = w | h<<12 | 20<<24, e = s8 xoff | s8 yoff<<8 | 0xFFFF<<16 ----
def scale_gfd(g):
    g = bytearray(g)
    assert struct.unpack_from('<I', g, 0x14)[0] == 24
    if not KEEP_SIZE:
        struct.pack_into('<I', g, 0x14, 48)
        if SCALE_FLOATS:
            # 24, 24, 21, 3, 3, 2.375: line metrics in font units, like the size field
            struct.pack_into('<6f', g, 0x28, *(v * 2 for v in struct.unpack_from('<6f', g, 0x28)))
    n = struct.unpack_from('<I', g, 0x1C)[0]
    namelen = struct.unpack_from('<I', g, 0x44)[0]
    p = 0x48 + namelen + 1
    assert p + n * 20 == len(g)
    m_rect = None
    for i in range(n):
        o = p + i * 20
        ch, a, b, c, e = struct.unpack_from('<5I', g, o)
        page, x, y = a & 0xFF, (a >> 8) & 0xFFF, a >> 20
        a = page | (x * 2) << 8 | (y * 2) << 20
        b = (b & 0xFFF) * 2 | ((b >> 12) & 0xFFF) * 2 << 12 | (b & 0xFF000000)
        if not KEEP_SIZE:
            top = (c >> 24) * 2 if SCALE_ASCENT else c >> 24
            c = (c & 0xFFF) * 2 | ((c >> 12) & 0xFFF) * 2 << 12 | top << 24
            e0, e1 = struct.unpack('<bb', struct.pack('<I', e)[:2])
            e = struct.unpack('<I', struct.pack('<bb', e0 * 2, e1 * 2) + struct.pack('<I', e)[2:])[0]
        struct.pack_into('<5I', g, o, ch, a, b, c, e)
        if ch == ord('M'):
            m_rect = (page, x * 2, y * 2, (b & 0xFFF), (b >> 12) & 0xFFF)
    return bytes(g), m_rect


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    # ---- ARC v0x11: "ARC\0", u16 ver, u16 n, u32 pad; 80-byte entries: name[64], type, csize, dsize|flags<<29, offset ----
    d = open(src, 'rb').read()
    ver, n = struct.unpack_from('<HH', d, 4)
    entries = []
    for i in range(n):
        o = 12 + i * 80
        name = d[o:o + 64]
        typ, csz, dsz, off = struct.unpack_from('<IIII', d, o + 64)
        entries.append([name, typ, dsz >> 29, zlib.decompress(d[off:off + csz])])

    names = [e[0].split(b'\0')[0].decode() for e in entries]
    gi = names.index('GUI\\02_common\\font\\font_festa')
    boxes = glyph_boxes(entries[gi][3])
    gfd, m_rect = scale_gfd(entries[gi][3])
    if not NO_GFD:
        entries[gi][3] = gfd
    if GFD_OUT:
        open(GFD_OUT, 'wb').write(gfd)
    if MARKER:
        print('M glyph (page, x, y, w, h) at 2x:', m_rect)
    for i, nm in enumerate(names):
        if nm.startswith('GUI\\02_common\\font\\font_festa_') and nm.endswith('_HQ'):
            page = int(nm.split('_')[-2])
            mr = m_rect[1:] if MARKER and m_rect[0] == page else None
            user = PAGES_DIR and os.path.join(PAGES_DIR, 'font_festa_%02d.png' % page)
            user = user if user and os.path.exists(user) else None
            if user:
                print('page %02d from %s' % (page, user))
            entries[i][3] = upscale_tex(entries[i][3], mr, boxes.get(page, []) if SHARP_EDGE is not None or user else None, user)
            print('upscaled', nm, len(entries[i][3]))

    data_start = struct.unpack_from('<I', d, 12 + 76)[0]  # first entry's offset: keep the same header area
    out = bytearray(d[:data_start])
    blob = bytearray()
    for i, (name, typ, flags, raw) in enumerate(entries):
        comp = zlib.compress(raw, 6)
        struct.pack_into('<IIII', out, 12 + i * 80 + 64, typ, len(comp), len(raw) | flags << 29, data_start + len(blob))
        blob += comp
    open(dst, 'wb').write(bytes(out) + bytes(blob))
    print('wrote', dst, len(out) + len(blob))
