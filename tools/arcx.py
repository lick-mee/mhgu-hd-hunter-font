import struct, sys, zlib, os

# MT Framework ARC v0x11: "ARC\0", u16 ver, u16 count, u32 pad, then 80-byte entries
arc, out, pat = sys.argv[1], sys.argv[2], sys.argv[3]
d = open(arc, 'rb').read()
ver, n = struct.unpack_from('<HH', d, 4)
os.makedirs(out, exist_ok=True)
for i in range(n):
    o = 12 + i * 80
    name = d[o:o + 64].split(b'\0')[0].decode()
    typ, csz, dsz, off = struct.unpack_from('<IIII', d, o + 64)
    if pat.lower() not in name.lower():
        continue
    raw = d[off:off + csz]
    try:
        data = zlib.decompress(raw)
    except Exception:
        data = raw
    fn = os.path.join(out, name.replace('\\', '_') + f'.{typ:08X}')
    open(fn, 'wb').write(data)
    print(f'{name:50s} type={typ:08X} csz={csz} dsz={dsz & 0x1FFFFFFF} flags={dsz >> 29} got={len(data)}')
