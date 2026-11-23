"""Stitch-to-shape checks on a finished PES.

1. Coverage: are the filled shapes (satin, tatami, contour fill) fully covered by top stitches?
   Every top stitch (underlay left out: the top covers it) is drawn as a thread 0.35 mm wide and
   compared with the shapes. Touching shapes are checked as one area, so a seam between two parts
   that should meet counts too. A place no stitch covers, wider than `min_mm`, is a hole: a crack
   between satin columns, a wedge where stitches turn too fast, a gap between fill parts.
2. Overflow: does a needle point land outside the design? Every top needle point is measured from
   the nearest shape (filled shapes, lines with their width). Farther than pull compensation +
   `tol_mm` is reported: tips and corners that shoot over the edge.

gen.py writes the shapes beside each PES (outpos/<name>.shapes.json) and prints warnings;
check.py adds the results; run by hand for pictures (check/<name>.holes.png, red = hole,
blue = over the edge):
    python3 coverage.py outpos/<name>.pes
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely import wkt
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.geometry import Point

THREAD = 0.35      # mm, drawn thread width (real thread 0.35-0.4)
EDGE = 0.25        # mm the filled area is shrunk by: the outline itself is not a hole
PX = 20            # pixels per mm
FILLED = ('satin', 'tatami', 'contour')


def _load(pes_file):
    import pyembroidery as pe
    base = os.path.splitext(pes_file)[0]
    data = json.load(open(base + '.shapes.json'))
    if isinstance(data, list): data = dict(comp=0.2, shapes=data)          # older files
    und = set(map(tuple, json.load(open(base + '.under.json')))) if os.path.exists(base + '.under.json') else set()
    p = pe.read(pes_file)
    segs = []; pts = []; prev = None
    for x, y, c in p.stitches:
        c &= pe.COMMAND_MASK
        if c != pe.STITCH: prev = None; continue
        top = not (prev is not None and prev in und and (x, y) in und)
        if prev is not None and top: segs.append((prev, (x, y)))
        if (x, y) not in und: pts.append((x, y))
        prev = (x, y)
    return data, segs, pts


def holes(pes_file, min_mm=0.25, picture=None, _d=None):
    """uncovered spots: dict(x, y, size) in mm from the top left of the PES; size = widest circle inside"""
    data, segs, pts = _d or _load(pes_file)
    fills = [wkt.loads(s['wkt']) for s in data['shapes'] if s.get('stitch') in FILLED]
    if not fills or not segs: return []
    allx = [q[0] for sg in segs for q in sg]; ally = [q[1] for sg in segs for q in sg]
    W = int((max(allx) / 10 + 2) * PX); H = int((max(ally) / 10 + 2) * PX)
    target = Image.new('1', (W, H), 0); dt = ImageDraw.Draw(target)
    area = unary_union(fills).buffer(-EDGE * 10)          # the union: seams between touching parts count
    for q in getattr(area, 'geoms', [area]):
        if q.is_empty or q.geom_type != 'Polygon': continue
        dt.polygon([(x / 10 * PX, y / 10 * PX) for x, y in q.exterior.coords], fill=1)
        for r in q.interiors: dt.polygon([(x / 10 * PX, y / 10 * PX) for x, y in r.coords], fill=0)
    cover = Image.new('1', (W, H), 0); dc = ImageDraw.Draw(cover); w = max(1, round(float(data.get('thread_mm', THREAD)) * PX))
    for a, b in segs: dc.line([(a[0] / 10 * PX, a[1] / 10 * PX), (b[0] / 10 * PX, b[1] / 10 * PX)], fill=1, width=w)
    t = np.array(target, bool); cv = np.array(cover, bool)
    gap = t & ~cv
    lab, n = ndimage.label(gap)
    out = []
    if n:
        dist = ndimage.distance_transform_edt(gap)
        for i, sl in enumerate(ndimage.find_objects(lab), start=1):
            d = dist[sl] * (lab[sl] == i)
            size = 2 * float(d.max()) / PX
            if size >= min_mm:
                yy, xx = np.unravel_index(np.argmax(d), d.shape)
                out.append(dict(x=round(float(xx + sl[1].start) / PX, 1), y=round(float(yy + sl[0].start) / PX, 1), size=round(size, 2), _l=i))
    if picture:
        im = np.full((H, W, 3), 255, np.uint8)
        im[t & cv] = (170, 170, 170); im[gap] = (255, 205, 205)
        for h in out: im[lab == h['_l']] = (220, 0, 0)
        for o in overflow(pes_file, _d=(data, segs, pts)):
            cx, cy = int(o['x'] * PX), int(o['y'] * PX)
            im[max(0, cy - 6):cy + 7, max(0, cx - 6):cx + 7] = (0, 60, 220)
        os.makedirs(os.path.dirname(picture) or '.', exist_ok=True)
        Image.fromarray(im).save(picture)
    for h in out: h.pop('_l')
    return sorted(out, key=lambda h: -h['size'])


def overflow(pes_file, tol_mm=0.3, _d=None):
    """needle points farther than comp + tol_mm from the design: dict(x, y, dist) in mm, one per 1 mm cell"""
    data, segs, pts = _d or _load(pes_file)
    geo = []
    for s in data['shapes']:
        g = wkt.loads(s['wkt'])
        if s.get('kind') == 'run': g = g.buffer(max(s.get('width', 0), 0.1) * 10 / 2)
        if s.get('margin'): g = g.buffer(float(s['margin']) * 10)    # cross squares, borders: reach past the shape by design
        geo.append(g)
    if not geo: return []
    tree = STRtree(geo); lim = (float(data.get('comp', 0.2)) + tol_mm) * 10
    worst = {}
    for x, y in pts:
        pt = Point(x, y)
        near = tree.query(pt.buffer(lim))
        if len(near) and min(geo[i].distance(pt) for i in near) <= lim: continue
        d = min(g.distance(pt) for g in geo)
        if d > lim:
            k = (int(x // 10), int(y // 10))
            if k not in worst or d > worst[k][2]: worst[k] = (x, y, d)
    return sorted((dict(x=round(x / 10, 1), y=round(y / 10, 1), dist=round(d / 10, 2)) for x, y, d in worst.values()), key=lambda o: -o['dist'])


def report(pes_file):
    """warning lines for gen.py / by hand; empty when all is well"""
    d = _load(pes_file); out = []
    hs = holes(pes_file, _d=d)
    if hs: out.append(f'{len(hs)} uncovered spot(s): ' + ', '.join(f"{h['size']} mm at x {h['x']}, y {h['y']}" for h in hs[:8]))
    ov = overflow(pes_file, _d=d)
    if ov: out.append(f'{len(ov)} place(s) over the edge: ' + ', '.join(f"{o['dist']} mm at x {o['x']}, y {o['y']}" for o in ov[:8]))
    return out


if __name__ == '__main__':
    bad = 0
    for f in sys.argv[1:]:
        pic = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(f))), 'check', os.path.basename(os.path.splitext(f)[0]) + '.holes.png')
        d = _load(f); holes(f, picture=pic, _d=d)
        lines = report(f)
        if lines: bad += 1; [print(f'WARNING: {f}: {l}') for l in lines]
        else: print(f'{f}: covered, nothing over the edge')
    sys.exit(1 if bad else 0)
