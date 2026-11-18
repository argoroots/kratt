"""Pictures of an embroidery file: how it looks and where the thread piles up.

python3 preview.py "out/Nimi 150.pes" [--fabric "#f2efe8"] [--px 10 | --long 1200]

Writes next to the file:
  <file>.niit.png    stitches drawn as thread (0.4 mm wide, thread colour, light from top left)
  <file>.tihedus.png thread length per mm2 (smoothed over ~1 mm), 7 levels from green to red
Prints the share of the design on each level.
"""
import argparse, math, os
import pyembroidery as pe
from PIL import Image, ImageDraw, ImageFont

THREAD = 0.4                         # thread width on fabric, mm
# thread length per mm2 (smoothed over ~1 mm). One layer of tatami (0.3 mm rows) + underlay is about 4-5,
# satin (0.4 mm) + underlay about 5-6; more than ~8.5 means layers piling up.
LEVELS = [(2.0, '#1a9850', 'alla 2 – serv või hõre'),
          (4.0, '#66bd63', '2–4 – õhuke'),
          (5.5, '#a6d96a', '4–5,5 – tavaline täidis'),
          (7.0, '#fee08b', '5,5–7 – tihe satiin'),
          (8.5, '#fdae61', '7–8,5 – kaks kihti'),
          (10., '#f46d43', '8,5–10 – paks, vaata üle'),
          (1e9, '#d73027', 'üle 10 – liiga paks')]
BANDS = LEVELS   # old name


def segments(p):
    """stitched segments in mm with their thread colour"""
    out = []; ti = 0; prev = None
    cols = [t.hex_color() for t in p.threadlist] or ['#000000']
    for x, y, c in p.stitches:
        c &= pe.COMMAND_MASK
        if c == pe.COLOR_CHANGE: ti = min(ti + 1, len(cols) - 1); prev = None; continue
        if c == pe.STITCH:
            if prev: out.append((prev, (x / 10, y / 10), cols[ti]))
            prev = (x / 10, y / 10)
        else: prev = None
    return out


def shade(hexcol, f):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    if f < 1: return tuple(int(v * f) for v in (r, g, b))
    return tuple(int(v + (255 - v) * (f - 1)) for v in (r, g, b))


def thread_picture(segs, box, px, fabric):
    x0, y0, x1, y1 = box; m = 3
    W, H = int((x1 - x0 + 2 * m) * px), int((y1 - y0 + 2 * m) * px)
    im = Image.new('RGB', (W, H), fabric); d = ImageDraw.Draw(im)
    tw = max(1, round(THREAD * px))
    P = lambda q: ((q[0] - x0 + m) * px, (q[1] - y0 + m) * px)
    for a, b, col in segs:
        A, B = P(a), P(b)
        d.line([A, B], fill=shade(col, 0.55), width=tw + 2)          # shadow edge
        r2 = (tw + 2) / 2
        for q in (A, B): d.ellipse([q[0] - r2, q[1] - r2, q[0] + r2, q[1] + r2], fill=shade(col, 0.55))
        d.line([A, B], fill=shade(col, 1.0), width=tw)               # thread
        L = math.dist(A, B)
        if L > 2 and tw >= 3:                                        # highlight on the side facing the light
            nx, ny = -(B[1] - A[1]) / L, (B[0] - A[0]) / L
            if nx + ny > 0: nx, ny = -nx, -ny
            o = tw * 0.22
            d.line([(A[0] + nx * o, A[1] + ny * o), (B[0] + nx * o, B[1] + ny * o)], fill=shade(col, 1.35), width=max(1, tw // 3))
        r = tw / 2                                                   # rounded thread ends
        for q in (A, B): d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=shade(col, 0.9))
    return im


def line_picture(p, S=400, ss=3):
    """catalogue picture: stitch lines in thread colour on light grey, S x S (as the library previews)"""
    st = [(x, y) for x, y, c in p.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
    x0, y0 = min(x for x, y in st), min(y for x, y in st); x1, y1 = max(x for x, y in st), max(y for x, y in st)
    W = S * ss; pad = W * 0.05; sc = (W - 2 * pad) / max(x1 - x0, y1 - y0, 1)
    ox, oy = (W - (x1 - x0) * sc) / 2, (W - (y1 - y0) * sc) / 2
    im = Image.new('RGB', (W, W), (236, 236, 236)); d = ImageDraw.Draw(im)
    for blk, th in p.get_as_colorblocks():
        c = th.color if th else 0; col = ((c >> 16) & 255, (c >> 8) & 255, c & 255); pts = []
        for x, y, cm in blk:
            if (cm & pe.COMMAND_MASK) == pe.STITCH: pts.append((ox + (x - x0) * sc, oy + (y - y0) * sc))
            else:
                if len(pts) > 1: d.line(pts, fill=col, width=4)
                pts = []
        if len(pts) > 1: d.line(pts, fill=col, width=4)
    return im.resize((S, S), Image.LANCZOS)


def density(segs, box, cell=0.25, smooth=0.5):
    """thread length per mm2 on a grid of `cell` mm, smoothed (gaussian, `smooth` mm). Returns (grid, x0, y0)."""
    import numpy as np
    from scipy.ndimage import gaussian_filter
    x0, y0, x1, y1 = box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2
    g = np.zeros((int((y1 - y0) / cell) + 1, int((x1 - x0) / cell) + 1))
    for a, b, _ in segs:
        L = math.dist(a, b); n = max(1, int(L / 0.05)); t = (np.arange(n) + 0.5) / n
        px = ((a[0] + (b[0] - a[0]) * t - x0) / cell).astype(int); py = ((a[1] + (b[1] - a[1]) * t - y0) / cell).astype(int)
        np.add.at(g, (py, px), L / n)
    return gaussian_filter(g, smooth / cell) / (cell * cell), x0, y0


def density_image(g, px_per_cell=1):
    """RGBA image: level colours, transparent where there is no thread"""
    import numpy as np
    rgba = np.zeros(g.shape + (4,), dtype=np.uint8)
    lo = 0.6
    for i, (hi, col, _) in enumerate(LEVELS):
        m = (g > lo) & (g <= hi)
        rgba[m] = [int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16), 255]
        lo = hi
    im = Image.fromarray(rgba, 'RGBA')
    return im.resize((im.width * px_per_cell, im.height * px_per_cell), Image.NEAREST) if px_per_cell > 1 else im


def density_picture(g, cell, px):
    k = max(1, round(cell * px)); im = density_image(g, k); leg = 26 + 18 * len(LEVELS)
    out = Image.new('RGB', (im.width, im.height + leg), (255, 255, 255)); out.paste(im, (0, 0), im)
    d = ImageDraw.Draw(out)
    try: f = ImageFont.truetype('DejaVuSans.ttf', 13)
    except OSError: f = ImageFont.load_default()
    y = im.height + 6; d.text((8, y), 'niidi pikkus mm/mm²', fill=(0, 0, 0), font=f); y += 20
    for _, col, txt in LEVELS:
        d.rectangle([8, y, 24, y + 13], fill=col); d.text((32, y), txt, fill=(0, 0, 0), font=f); y += 18
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--fabric', default='#f2efe8', help='fabric colour')
    ap.add_argument('--px', type=float, default=10, help='pixels per mm')
    ap.add_argument('--line', action='store_true', help='also <file>.joon.png: catalogue picture 400x400')
    ap.add_argument('--long', type=int, help='thread picture: longer side in pixels (instead of --px), e.g. 1200')
    a = ap.parse_args()
    for fn in a.files:
        p = pe.read(fn); segs = segments(p)
        xs = [q[0] for s in segs for q in s[:2]]; ys = [q[1] for s in segs for q in s[:2]]
        box = (min(xs), min(ys), max(xs), max(ys))
        base = os.path.splitext(fn)[0]
        px = a.long / max(box[2] - box[0], box[3] - box[1]) if a.long else a.px
        thread_picture(segs, box, px, a.fabric).save(base + '.niit.png', optimize=True)
        if a.line: line_picture(p).save(base + '.joon.png')
        g, _, _ = density(segs, box)
        density_picture(g, 0.25, a.px).save(base + '.tihedus.png')
        v = g[g > 0.6]; lo = 0.6; parts = []
        for hi, _, txt in LEVELS:
            share = ((v > lo) & (v <= hi)).sum() / len(v) * 100; lo = hi
            if share >= 0.05: parts.append(f'{txt.split(" – ")[0]}: {share:.1f}%')
        print(f'{fn}: ' + ', '.join(parts) + f' (max {v.max():.1f} mm/mm2)')


if __name__ == '__main__':
    main()
