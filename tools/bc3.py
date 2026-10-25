"""BC3 (DXT5) for white-on-alpha font pages: colour block constant white, alpha block fitted per 4x4 block.
1 byte per pixel, a quarter of RGBA8 - a 2048 page then takes what a 1024 RGBA8 page did."""
import numpy as np

WHITE = np.frombuffer(bytes([0xFF, 0xFF, 0xFF, 0xFF, 0, 0, 0, 0]), np.uint8)   # c0 = c1 = 0xFFFF, indices 0


def _palettes(a0, a1):
    a0 = a0.astype(np.int32)[:, None]; a1 = a1.astype(np.int32)[:, None]
    eight = np.concatenate([a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)], 1)
    six = np.concatenate([a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)]
                         + [np.zeros_like(a0), np.full_like(a0, 255)], 1)
    return eight, six


def _fit(v, pal):
    err = np.abs(v[:, :, None] - pal[:, None, :])        # (n, 16, 8)
    idx = err.argmin(2)
    return idx, (np.take_along_axis(err, idx[:, :, None], 2)[:, :, 0] ** 2).sum(1)


def encode_alpha_blocks(alpha):
    """alpha uint8 (h, w), h and w multiples of 4 -> (h/4 * w/4, 16) uint8 BC3 blocks, row-major."""
    h, w = alpha.shape
    v = alpha.reshape(h // 4, 4, w // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16).astype(np.int32)
    hi, lo = v.max(1), v.min(1)
    # 8-value mode: endpoints max > min
    pal8, _ = _palettes(hi, lo)
    i8, e8 = _fit(v, pal8)
    # 6-value mode with exact 0 and 255: endpoints span the values strictly between them
    mid = np.where((v > 0) & (v < 255), v, -1)
    mhi = mid.max(1)
    mlo = np.where(mid >= 0, mid, 256).min(1)
    has = mhi >= 0
    mlo = np.where(has, mlo, 0); mhi = np.where(has, mhi, 0)
    _, pal6 = _palettes(mlo, mhi)
    i6, e6 = _fit(v, pal6)
    use6 = e6 < e8
    a0 = np.where(use6, mlo, hi).astype(np.uint8)
    a1 = np.where(use6, mhi, lo).astype(np.uint8)
    idx = np.where(use6[:, None], i6, i8).astype(np.uint64)
    flat = hi == lo                                          # one value: a0 = a1 = it, every index 0
    a0 = np.where(flat, hi, a0).astype(np.uint8); a1 = np.where(flat, hi, a1).astype(np.uint8)
    idx[flat] = 0
    # a0 == a1 in 8-value mode would mean 6-value mode: only reachable through `flat`, where index 0 = a0 anyway
    bits = (idx << (3 * np.arange(16, dtype=np.uint64))).sum(1)
    out = np.empty((v.shape[0], 16), np.uint8)
    out[:, 0], out[:, 1] = a0, a1
    for k in range(6):
        out[:, 2 + k] = (bits >> np.uint64(8 * k)) & np.uint64(0xFF)
    out[:, 8:] = WHITE
    return out


def decode_alpha_blocks(blocks, h, w):
    """For checking: BC3 blocks -> alpha uint8 (h, w)."""
    a0 = blocks[:, 0].astype(np.int32); a1 = blocks[:, 1].astype(np.int32)
    p8, p6 = _palettes(a0, a1)
    pal = np.where((a0 > a1)[:, None], p8, p6)
    bits = sum(blocks[:, 2 + k].astype(np.uint64) << np.uint64(8 * k) for k in range(6))
    idx = ((bits[:, None] >> (3 * np.arange(16, dtype=np.uint64))) & np.uint64(7)).astype(np.int64)
    v = np.take_along_axis(pal, idx, 1)
    return v.reshape(h // 4, w // 4, 4, 4).transpose(0, 2, 1, 3).reshape(h, w).astype(np.uint8)


def mip_chain(alpha, levels):
    """Box-filtered alpha mips, each at least 4x4 (BC blocks), as uint8 arrays."""
    out = [alpha]
    a = alpha.astype(np.float32)
    for _ in range(1, levels):
        h, w = a.shape
        if h >= 2 and w >= 2:
            a = a.reshape(h // 2, 2, w // 2, 2).mean((1, 3))
        out.append(np.round(a).astype(np.uint8))
    return out
