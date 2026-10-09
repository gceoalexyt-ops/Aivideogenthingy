"""Measure camera shake in a clip: per-frame global shift (phase correlation), split into the
smooth trend and the jitter around it. Prints jitter in pixels per frame at 720x1280 scale.

Usage: python3 shake.py CLIP [CLIP ...]
"""
import subprocess
import sys

import numpy as np

W, H = 360, 640  # analysis size (1/2 of 720x1280)


def frames(path):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"scale={W}:{H},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W).astype(np.float32)


def shift(a, b):
    win = np.outer(np.hanning(H), np.hanning(W))
    fa, fb = np.fft.fft2(a * win), np.fft.fft2(b * win)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-6
    c = np.fft.ifft2(r).real
    y, x = np.unravel_index(np.argmax(c), c.shape)

    def sub(m, p, z):  # parabolic sub-pixel refinement of the peak
        d = m - 2 * p + z
        return 0.0 if abs(d) < 1e-9 else 0.5 * (m - z) / d
    dx = sub(c[y, (x - 1) % W], c[y, x], c[y, (x + 1) % W])
    dy = sub(c[(y - 1) % H, x], c[y, x], c[(y + 1) % H, x])
    x, y = x + dx, y + dy
    if y > H // 2:
        y -= H
    if x > W // 2:
        x -= W
    return x, y


def measure(path):
    f = frames(path)
    d = np.array([shift(f[i], f[i - 1]) for i in range(1, len(f))], float) * 2  # back to full-res pixels
    k = 9
    pad = np.pad(d, ((k // 2, k // 2), (0, 0)), mode="edge")
    trend = np.stack([np.convolve(pad[:, j], np.ones(k) / k, mode="valid") for j in range(2)], 1)
    jitter = d - trend
    rms = float(np.sqrt((jitter ** 2).sum(1).mean()))
    p95 = float(np.percentile(np.sqrt((jitter ** 2).sum(1)), 95))
    speed = float(np.sqrt((trend ** 2).sum(1)).mean())
    diff = np.abs(f[1:] - f[:-1]).mean((1, 2))
    moving = np.sqrt((trend ** 2).sum(1)) > 1.0
    dup = float(((diff < 0.5) & moving).sum() / max(1, moving.sum()) * 100)
    return rms, p95, speed, dup


for path in sys.argv[1:]:
    rms, p95, speed, dup = measure(path)
    print(f"{path.split('/')[-1]:28s} jitter rms {rms:5.2f}px  p95 {p95:5.2f}px  motion {speed:5.2f}px/f  "
          f"duplicate frames while moving {dup:4.1f}%")
