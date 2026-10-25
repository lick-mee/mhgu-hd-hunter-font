"""Minimal PNG read/write with numpy (no Pillow here). Reads 8/16-bit gray, gray+alpha, RGB, RGBA, non-interlaced."""
import struct, zlib
import numpy as np


def write_png(path, img):
    img = np.ascontiguousarray(img, np.uint8)
    h, w = img.shape[:2]
    ctype = {2: 0, 3: {3: 2, 4: 6}.get(img.shape[2] if img.ndim == 3 else 0)}[img.ndim]
    rows = img.reshape(h, -1)
    raw = b''.join(b'\0' + rows[y].tobytes() for y in range(h))

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def read_png(path):
    """Returns uint8 array (h, w, channels)."""
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', '%s is not a PNG' % path
    i, idat, plte = 8, b'', None
    while i < len(d):
        n, t = struct.unpack('>I4s', d[i:i + 8])
        body = d[i + 8:i + 8 + n]
        if t == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif t == b'IDAT':
            idat += body
        elif t == b'PLTE':
            plte = np.frombuffer(body, np.uint8).reshape(-1, 3)
        i += 12 + n
    assert interlace == 0, '%s: save it without interlacing' % path
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, ch * depth // 8)
    stride = (w * ch * depth + 7) // 8
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, stride + 1)
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.int32)
    for y in range(h):
        f, line = raw[y, 0], raw[y, 1:].astype(np.int32)
        if f == 0:
            cur = line
        elif f == 2:
            cur = (line + prev) & 255
        elif f == 1:
            cur = np.zeros(stride, np.int32)
            for k in range(bpp):
                cur[k::bpp] = np.cumsum(line[k::bpp]) & 255
        else:
            cur = np.zeros(stride, np.int32)
            for x in range(stride):   # sub / average / paeth depend on the pixel to the left
                a = cur[x - bpp] if x >= bpp else 0
                if f == 1:
                    cur[x] = (line[x] + a) & 255
                elif f == 3:
                    cur[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
                else:
                    b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    cur[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out[y] = cur
        prev = cur
    if depth == 16:
        px = out.reshape(h, w, ch * 2)[:, :, 0::2]
    elif depth == 8:
        px = out.reshape(h, w, ch)
    else:
        bits = np.unpackbits(out, axis=1)[:, :w * depth].reshape(h, w, depth)
        px = (bits * (1 << np.arange(depth - 1, -1, -1))).sum(2).astype(np.uint8)[:, :, None]
        if ctype == 0:
            px = (px.astype(np.int32) * 255 // ((1 << depth) - 1)).astype(np.uint8)
    if ctype == 3:
        px = plte[px[:, :, 0]]
    return px


def coverage(px):
    """Glyph coverage 0..255 from an image: its alpha if that varies, else its brightness (white glyphs on black)."""
    if px.shape[2] in (2, 4) and px[:, :, -1].min() < 250:
        return px[:, :, -1]
    rgb = px[:, :, :3] if px.shape[2] >= 3 else px[:, :, :1]
    return rgb.astype(np.float32).mean(2).round().astype(np.uint8)
