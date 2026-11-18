"""Shared helpers: ascii names, size from stitches, preview rendering."""
import os, unicodedata
import pyembroidery as pe
from PIL import Image, ImageDraw

DESIGN_EXT = ('.jef', '.pes', '.dst', '.exp', '.vp3', '.xxx', '.hus', '.vip', '.sew', '.pec')
BG = (236, 236, 236)

# machines in use: file format and largest embroidery area (mm)
MACHINES = {'janome': dict(model='Janome Memory Craft 550E', format='jef', hoop=(200, 360)),
            'brother': dict(model='Brother Innov-is V3', format='pes', hoop=(300, 180))}


def ascii_name(s):
    """file names without diacritics: õ->o, ä->a, ü->u, š->s ..."""
    s = unicodedata.normalize('NFKD', s)
    return ''.join(ch for ch in s if not unicodedata.combining(ch))


def stitch_box(p):
    """extent from stitches only (extents() also counts jumps and commands), 0.1 mm units"""
    st = [(x, y) for x, y, c in p.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
    if not st: return 0, 0, 0, 0
    xs = [x for x, y in st]; ys = [y for x, y in st]
    return min(xs), min(ys), max(xs), max(ys)


def size_mm(p):
    x0, y0, x1, y1 = stitch_box(p)
    return (x1 - x0) / 10, (y1 - y0) / 10


def fits(w, h, hoop):
    W, H = hoop
    return (w <= W and h <= H) or (w <= H and h <= W)


def render(p, dst, S=400, ss=3):
    """preview: light grey background, rounded line in thread colours, broken at jumps"""
    x0, y0, x1, y1 = stitch_box(p)
    W = S * ss; pad = W * 0.05; sc = (W - 2 * pad) / max(x1 - x0, y1 - y0, 1)
    ox = (W - (x1 - x0) * sc) / 2; oy = (W - (y1 - y0) * sc) / 2
    im = Image.new('RGB', (W, W), BG); d = ImageDraw.Draw(im)
    for blk, th in p.get_as_colorblocks():
        c = th.color if th else 0; col = ((c >> 16) & 255, (c >> 8) & 255, c & 255)
        pts = []
        for x, y, cm in blk:
            if (cm & pe.COMMAND_MASK) == pe.STITCH: pts.append((ox + (x - x0) * sc, oy + (y - y0) * sc))
            else:
                if len(pts) > 1: d.line(pts, fill=col, width=4)
                pts = []
        if len(pts) > 1: d.line(pts, fill=col, width=4)
    im = im.resize((S, S), Image.LANCZOS)
    im.save(dst, 'BMP' if dst.lower().endswith('.bmp') else None)
