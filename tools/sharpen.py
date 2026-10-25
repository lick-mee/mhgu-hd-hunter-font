"""Sharp 2x upscale of anti-aliased glyph masks.

Each glyph box is upscaled on its own (outside = transparent), with a Catmull-Rom cubic, then the edge ramp is
steepened around 50% coverage. The 50% contour - the letter's outline - stays where it was, so stroke weight
is kept; only the soft 2-3 px fringe of the 2x image becomes a ~1 px one.
"""
import numpy as np


def _cr(t):
    return np.array([(-t ** 3 + 2 * t ** 2 - t) / 2, (3 * t ** 3 - 5 * t ** 2 + 2) / 2,
                     (-3 * t ** 3 + 4 * t ** 2 + t) / 2, (t ** 3 - t ** 2) / 2])


# output pixel 2k samples source k-0.25 (taps k-2..k+1, t=.75); 2k+1 samples k+0.25 (taps k-1..k+2, t=.25)
W_EVEN, W_ODD = _cr(0.75), _cr(0.25)


def _up_axis0(a):
    p = np.pad(a, ((2, 2), (0, 0)))
    n = a.shape[0]
    even = sum(W_EVEN[i] * p[i:i + n] for i in range(4))
    odd = sum(W_ODD[i] * p[i + 1:i + 1 + n] for i in range(4))
    out = np.empty((2 * n,) + a.shape[1:], a.dtype)
    out[0::2], out[1::2] = even, odd
    return out


def upscale_glyph(a, edge=0.28):
    """a: float32 alpha 0..1 (h, w). Returns (2h, 2w) float32."""
    up = _up_axis0(_up_axis0(a).T).T
    lo, hi = 0.5 - edge, 0.5 + edge
    t = np.clip((up - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def upscale_page(alpha, glyphs, edge=0.28):
    """alpha: uint8 (H, W) page; glyphs: [(x, y, w, h)] boxes at 1x. Returns uint8 (2H, 2W)."""
    H, W = alpha.shape
    out = np.zeros((2 * H, 2 * W), np.float32)
    src = alpha.astype(np.float32) / 255
    for x, y, w, h in glyphs:
        if w == 0 or h == 0:
            continue
        g = upscale_glyph(src[y:y + h, x:x + w], edge)
        o = out[2 * y:2 * y + 2 * h, 2 * x:2 * x + 2 * w]
        np.maximum(o, g, out=o)   # boxes can share pixels (e.g. reused glyphs); keep the stronger ink
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
