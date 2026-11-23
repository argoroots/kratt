"""Pictures of an embroidery file: how it looks and where the thread piles up.

python3 preview.py "out/Nimi 150.pes" [--fabric "#f2efe8"] [--px 10 | --long 1200]

Working pictures for checking (not for the user: the user gets the project PDF and the machine files).
Writes to check/ (--dir):
  <file>.thread.png    stitches drawn as thread exactly where the file puts them (0.4 mm wide, thread colour)
  <file>.look.png      expected look on the fabric: pulled in, pushed out, satin sheen, fabric texture (see look())
  <file>.density.png thread length per mm2 (smoothed over ~1 mm), 7 levels from green to red
  <file>.line.png    with --line: 400x400 line picture, only when the design goes into a collection
Prints the share of the design on each level.
"""
import argparse, json, math, os
import pyembroidery as pe
from PIL import Image, ImageDraw, ImageFont

THREAD = 0.4                         # thread width on fabric, mm
# thread length per mm2 (smoothed over ~1 mm). One layer of tatami (0.3 mm rows) + underlay is about 4-5,
# satin (0.4 mm) + underlay about 5-6; more than ~8.5 means layers piling up.
LEVELS = [(2.0, '#1a9850', 'under 2 – edge or sparse'),
          (4.0, '#66bd63', '2–4 – thin'),
          (5.5, '#a6d96a', '4–5.5 – normal fill'),
          (7.0, '#fee08b', '5.5–7 – dense satin'),
          (8.5, '#fdae61', '7–8.5 – two layers'),
          (10., '#f46d43', '8.5–10 – thick, check'),
          (1e9, '#d73027', 'over 10 – too thick')]
BANDS = LEVELS   # old name


def meta_colours(p, fn):
    """gen.py's meta.json beside the file knows each thread block's colour; a PES read back loses it
    when a machine stop repeats a colour (appliqué)"""
    import os, json
    mf = os.path.join(os.path.dirname(fn) or '.', 'meta.json')
    try: m = json.load(open(mf))
    except (OSError, ValueError): return
    if not m.get('blocks'): return
    for i, t in enumerate(p.threadlist):
        if i < len(m['blocks']): t.set_hex_color(m['colors'][m['blocks'][i]]['hex'])


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



# ---------- expected look on the fabric ----------
# The file is not what lands on the fabric: satin and fill stitches pull the fabric in along the stitch
# (that is why the file makes them longer by the pull compensation) and push it out along the column.
# The look picture undoes that with the fabric's own numbers, so it shows the design after sewing:
#   pull  per stitch end = comp x (1 + comp_stretch x (c - 0.5)), c = |cos| to the stretch direction;
#         stitches under 1.5 mm pull in proportionally less; running stitches keep their length
#   push  a satin column grows along its length by PUSH_K x comp at each end
# These are estimates (comp is the expected pull), not measurements: a test sew-out decides.
PUSH_K = 0.4
KNIT = ('jersey', 'fleece', 'terry')
WOVEN = ('linen', 'cotton', 'denim', 'canvas')


def satin_columns(S):
    """index lists: consecutive top stitches > 0.8 mm that go back and forth (each turns more than 120 deg)
    to a new needle point; a stitch that goes back over the last one is a triple running stitch, not satin"""
    import numpy as np
    runs, cur = [], []
    for i, (a, b, col, u) in enumerate(S):
        v = np.subtract(b, a); ok = not u and math.hypot(*v) > 0.8
        if ok and cur:
            pa, pb = S[cur[-1]][0], S[cur[-1]][1]; w = np.subtract(pb, pa)
            retrace = math.dist(a, pb) < 0.05 and math.dist(b, pa) < 0.05      # triple running stitch goes back over itself
            if retrace or np.dot(v, w) / (math.hypot(*v) * math.hypot(*w)) >= -0.5:
                if len(cur) > 3: runs.append(cur)
                cur = []
        if ok: cur.append(i)
        else:
            if len(cur) > 3: runs.append(cur)
            cur = []
    if len(cur) > 3: runs.append(cur)
    return runs


def settle(S, comp, stretch=0.0, angle=0.0, push_k=PUSH_K):
    """[(a, b, colour, underlay?)] in mm -> the same stitches where they lie after sewing"""
    import numpy as np
    cols = satin_columns(S); sat = {i for r in cols for i in r}
    out = [[np.array(a, float), np.array(b, float), c, u] for a, b, c, u in S]
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for i in sat:
        a, b = out[i][0], out[i][1]; v = b - a; L = float(np.linalg.norm(v)); uv = v / L
        k = abs(uv[0] * ca + uv[1] * sa)
        pm = min(comp * (1 + stretch * (k - 0.5)) * min(1.0, L / 1.5), 0.3 * L)
        out[i][0], out[i][1] = a + uv * pm, b - uv * pm
    for run in cols:
        mids = np.array([(out[i][0] + out[i][1]) / 2 for i in run])
        dd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(mids, axis=0), axis=1))]
        if dd[-1] < 1: continue
        for k, i in enumerate(run):
            t = mids[min(len(run) - 1, k + 3)] - mids[max(0, k - 3)]; n = float(np.linalg.norm(t))
            if n < 1e-6: continue
            sh = t / n * push_k * comp * (2 * dd[k] / dd[-1] - 1)
            out[i][0] = out[i][0] + sh; out[i][1] = out[i][1] + sh
    return [(tuple(a), tuple(b), c, u) for a, b, c, u in out], sat


def fabric_texture(W, H, px, colour, kind):
    """knit: wales ~0.7 mm with V loops; woven: plain weave ~0.5 mm; others plain with slight noise"""
    import numpy as np
    from PIL import ImageFilter
    base = np.array([int(colour[i:i + 2], 16) for i in (1, 3, 5)], float)
    yy, xx = np.mgrid[0:H, 0:W] / px
    noise = np.random.default_rng(1).normal(0, 0.008, (H, W))
    if kind in KNIT:
        v = np.abs((xx % 0.7) / 0.7 - 0.5) * 2
        f = 1 - 0.035 * (0.5 + 0.5 * np.cos(2 * np.pi * (yy / 0.55 + 0.5 * v))) - 0.025 * v + noise
    elif kind in WOVEN:
        f = 1 - 0.03 * np.abs(np.sin(np.pi * xx / 0.5)) * (((xx // 0.5 + yy // 0.5) % 2) * 0.6 + 0.4) \
              - 0.03 * np.abs(np.sin(np.pi * yy / 0.5)) * ((((xx // 0.5 + yy // 0.5) + 1) % 2) * 0.6 + 0.4) + noise
    else:
        f = 1 + noise
    im = Image.fromarray((base[None, None, :] * f[..., None]).clip(0, 255).astype('uint8'))
    return im.filter(ImageFilter.GaussianBlur(px * 0.05))


def look(S, px, comp, stretch=0.0, angle=0.0, fabric='#f2efe8', kind='', margin=3):
    """expected look: S = [(a, b, colour, underlay?)] in mm. Returns (image, x0, y0): the image's top left
    corner in the stitches' mm coordinates"""
    from PIL import ImageFilter
    T, sat = settle(S, comp, stretch, angle)
    xs = [q[0] for s in T for q in s[:2]]; ys = [q[1] for s in T for q in s[:2]]
    x0, y0 = min(xs) - margin, min(ys) - margin
    W, H = int((max(xs) - x0 + margin) * px), int((max(ys) - y0 + margin) * px)
    tw = max(1, round(THREAD * px))
    P = lambda q: ((q[0] - x0) * px, (q[1] - y0) * px)
    shadow = Image.new('L', (W, H), 0); ds = ImageDraw.Draw(shadow); o = px * 0.12
    for a, b, col, u in T:
        A, B = P(a), P(b); ds.line([(A[0] + o, A[1] + o), (B[0] + o, B[1] + o)], fill=110, width=tw + 2)
    im = fabric_texture(W, H, px, fabric, kind)
    im.paste((40, 40, 50), (0, 0), shadow.filter(ImageFilter.GaussianBlur(px * 0.12)))
    d = ImageDraw.Draw(im)
    for i, (a, b, col, u) in enumerate(T):
        A, B = P(a), P(b); L = math.dist(A, B)
        if u: d.line([A, B], fill=shade(col, 0.6), width=tw); continue
        if i not in sat or L < tw * 3:          # running stitch: even thread with a twist highlight
            d.line([A, B], fill=shade(col, 0.92), width=tw)
            d.line([A, B], fill=shade(col, 1.12), width=max(1, tw // 3)); continue
        n = 14                                   # satin: dome, light on top, darker into the needle holes
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            f = 0.62 + 0.62 * math.sin(math.pi * (t0 + t1) / 2) ** 0.8
            d.line([(A[0] + (B[0] - A[0]) * t0, A[1] + (B[1] - A[1]) * t0), (A[0] + (B[0] - A[0]) * t1, A[1] + (B[1] - A[1]) * t1)],
                   fill=shade(col, f), width=tw)
        nx, ny = -(B[1] - A[1]) / L, (B[0] - A[0]) / L; r = tw / 2      # fine groove to the next stitch
        d.line([(A[0] + nx * r, A[1] + ny * r), (B[0] + nx * r, B[1] + ny * r)], fill=shade(col, 0.7), width=1)
    return im, x0, y0


def segments_under(p, fn):
    """segments() with the underlay flag, read from outpos/<name>.under.json when there is one"""
    base = os.path.splitext(fn)[0]
    cand = [base + '.under.json', os.path.join(os.path.dirname(fn) or '.', '..', 'outpos', os.path.basename(base) + '.under.json')]
    und = set()
    for cf in cand:
        if os.path.exists(cf): und = {(x / 10, y / 10) for x, y in json.load(open(cf))}; break
    return [(a, b, c, a in und and b in und) for a, b, c in segments(p)]

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
    ap.add_argument('--line', action='store_true', help='also <file>.line.png: catalogue picture 400x400')
    ap.add_argument('--long', type=int, help='thread picture: longer side in pixels (instead of --px), e.g. 1200')
    ap.add_argument('--dir', default='check', help='folder for the pictures (default check/)')
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    for fn in a.files:
        p = pe.read(fn); meta_colours(p, fn); segs = segments(p)
        global THREAD
        THREAD = 0.4
        for mf in (os.path.join(os.path.dirname(fn) or '.', 'meta.json'), os.path.join(os.path.dirname(fn) or '.', '..', 'out', 'meta.json')):
            try: THREAD = 0.28 if int(json.load(open(mf)).get('thread', 40)) == 60 else 0.4; break   # 60 wt is thinner
            except (OSError, ValueError): pass
        xs = [q[0] for s in segs for q in s[:2]]; ys = [q[1] for s in segs for q in s[:2]]
        box = (min(xs), min(ys), max(xs), max(ys))
        base = os.path.join(a.dir, os.path.splitext(os.path.basename(fn))[0])
        px = a.long / max(box[2] - box[0], box[3] - box[1]) if a.long else a.px
        thread_picture(segs, box, px, a.fabric).save(base + '.thread.png', optimize=True)
        mt = {}
        for mf in (os.path.join(os.path.dirname(fn) or '.', 'meta.json'), os.path.join(os.path.dirname(fn) or '.', '..', 'out', 'meta.json')):
            try: mt = json.load(open(mf)); break
            except (OSError, ValueError): pass
        pr = mt.get('params', {})
        look(segments_under(p, fn), px, float(pr.get('comp', 0.2)), float(pr.get('comp_stretch', 0)), float(pr.get('stretch_angle', 0)),
             a.fabric, mt.get('fabric', ''))[0].save(base + '.look.png', optimize=True)
        if a.line: line_picture(p).save(base + '.line.png')
        g, _, _ = density(segs, box)
        density_picture(g, 0.25, a.px).save(base + '.density.png')
        v = g[g > 0.6]; lo = 0.6; parts = []
        for hi, _, txt in LEVELS:
            share = ((v > lo) & (v <= hi)).sum() / len(v) * 100; lo = hi
            if share >= 0.05: parts.append(f'{txt.split(" – ")[0]}: {share:.1f}%')
        print(f'{fn}: ' + ', '.join(parts) + f' (max {v.max():.1f} mm/mm2)')


if __name__ == '__main__':
    main()
