"""Stitch generation: tatami fill, satin columns, running stitch -> pyembroidery pattern.
Units: mm inside, 0.1 mm in the pattern."""
import math
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely import affinity
import pyembroidery as pe
import satin as SAT
from design import knockout

def polys(g):
    if g.is_empty: return []
    return list(g.geoms) if isinstance(g, MultiPolygon) else [g]

OVERLAP = True
STAGGERS = 4
ROWCOMP = 0.0   # pull compensation: tatami rows are made this much longer at both ends
def fill(poly, angle, spacing, maxlen, offset_row=0):
    """Tatami/scanline fill; returns list of blocks (lists of points) in mm."""
    angle = ((angle + 90) % 180) - 90   # rows at 135 deg = rows at -45 deg; keeps cos(angle) >= 0
    rp = affinity.rotate(poly, -angle, origin=(0, 0), use_radians=False)
    minx, miny, maxx, maxy = rp.bounds
    rows = []
    # rows: vertical step 'spacing' (multiple of 0.1 mm), intercepts on the 0.1 mm grid
    ca = math.cos(math.radians(angle))
    grid = abs(ca) >= 0.5          # top fills (10 deg, 45 deg); underlay keeps plain spacing
    if grid:
        spacing = max(1, round(spacing / 0.1)) * 0.1 * ca          # row step must be whole 0.1 mm steps (else stripes)
        y = (math.floor(miny / ca / 0.1) + 1) * 0.1 * ca
    else:
        y = miny + spacing / 2
    while y < maxy:
        ln = LineString([(minx - 1, y), (maxx + 1, y)])
        inter = rp.intersection(ln)
        segs = [g for g in (inter.geoms if hasattr(inter, 'geoms') else [inter]) if g.length > 0.05]
        segs = sorted([tuple(sorted([g.coords[0][0], g.coords[-1][0]])) for g in segs])
        if ROWCOMP: segs = [(a_ - ROWCOMP, b_ + ROWCOMP) for a_, b_ in segs]
        rows.append((y, segs))
        y += spacing
    # build blocks: chains of overlapping segments in consecutive rows
    blocks = []; open_ = []
    for y, segs in rows:
        new_open = []; used = set()
        for blk in open_:
            ly, (a, b) = blk[-1]
            cands = [i for i, (c, d) in enumerate(segs) if i not in used and c < b and d > a]
            if len(cands) == 1:
                i = cands[0]
                # only continue if this segment overlaps only this block
                if sum(1 for bb in open_ if bb[-1][1][0] < segs[i][1] and bb[-1][1][1] > segs[i][0]) == 1:
                    used.add(i); blk.append((y, segs[i])); new_open.append(blk); continue
            blocks.append(blk)
        for i, s in enumerate(segs):
            if i not in used:
                b = [(y, s)]; new_open.append(b)
        open_ = new_open
    blocks += open_
    rpc = rp.buffer(ROWCOMP + 0.05)
    # overlap: extend each block by one row into the neighbouring area (avoids gaps where blocks meet)
    def rowsegs(yy):
        inter = rp.intersection(LineString([(minx - 1, yy), (maxx + 1, yy)]))
        return [(a_ - ROWCOMP, b_ + ROWCOMP) for a_, b_ in (tuple(sorted([g.coords[0][0], g.coords[-1][0]])) for g in (inter.geoms if hasattr(inter, 'geoms') else [inter]) if g.length > 0.05)]
    if OVERLAP:
        for blk in blocks:
            for idx, dy in ((-1, spacing),):   # extend at the block's end only (a start row made a back-hop)
                y0r, (a0, b0) = blk[idx]
                for s0, s1 in rowsegs(y0r + dy):
                    lo, hi = max(a0, s0), min(b0, s1)
                    if hi - lo > 0.3:
                        if idx == 0: blk.insert(0, (y0r + dy, (lo, hi)))
                        else: blk.append((y0r + dy, (lo, hi)))
                        break
    out = []
    for blk in blocks:
        pts = []
        for k, (y, (a, b)) in enumerate(blk):
            if pts:   # start each row at the end nearest to where the previous row stopped
                xs = [a, b] if math.dist(pts[-1], (a, y)) <= math.dist(pts[-1], (b, y)) else [b, a]
            else: xs = [a, b] if k % 2 == 0 else [b, a]
            # penetrations on a shared grid: every row uses x = (j + phase) * maxlen, the phase
            # steps by 1/STAGGERS from row to row, so the needle holes form even diagonal lines
            ph = (round(y / spacing) % STAGGERS) / STAGGERS
            j0, j1 = math.ceil(a / maxlen - ph), math.floor(b / maxlen - ph)
            mid = [(j + ph) * maxlen for j in range(j0, j1 + 1)]
            mid = [x for x in mid if a + 0.4 < x < b - 0.4]
            row = [xs[0]] + (mid if xs[1] > xs[0] else mid[::-1]) + [xs[1]]
            if pts and math.dist(pts[-1], (row[0], y)) > 1.0:
                seg = LineString([pts[-1], (row[0], y)])
                if not rpc.contains(seg):          # straight hop would leave the shape
                    tp = travel_path(pts[-1], (row[0], y), rpc)
                    if len(tp) > 1 and LineString(tp).length < 4 * seg.length + 2: pts += tp[1:-1]
                else:                                       # long hop inside the shape: stitches <= maxlen
                    k = math.ceil(seg.length / maxlen)
                    pts += [(pts[-1][0] + (row[0] - pts[-1][0]) * i / k, pts[-1][1] + (y - pts[-1][1]) * i / k) for i in range(1, k)]
            pts += [(x, y) for x in row]
        out.append([snap(rot_back(p, angle), angle) if on_row and grid else rot_back(p, angle) for p, on_row in zip(pts, rowflags(pts, blk))])
    return out

def rowflags(pts, blk):
    ys = set(round(y, 9) for y, _ in blk)
    return [round(p[1], 9) in ys for p in pts]

def snap(p, angle):
    """put a row point on the 0.1 mm grid, keeping it on its row line"""
    x, y = p
    if abs(angle % 180) < 1e-9: return (round(x, 1), round(y, 1))
    t = math.tan(math.radians(angle))
    c = round((y - x * t) / 0.1) * 0.1          # row intercept (already on grid)
    xr = round(x, 1)
    return (xr, round(c + xr * t, 1))

def rot_back(p, angle):
    a = math.radians(angle); x, y = p
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def travel_path(a, b, poly):
    """points from a to b running along the inside of poly's boundary"""
    ins = poly.buffer(-0.25, join_style=2)
    if ins.is_empty: return [b]
    best = None
    for g in polys(ins):
        for ring in [g.exterior] + list(g.interiors):
            da = ring.distance(Point(a)) ; db = ring.distance(Point(b))
            sc = da + db
            if best is None or sc < best[0]: best = (sc, ring)
    ring = best[1]; L = ring.length
    pa, pb = ring.project(Point(a)), ring.project(Point(b))
    fwd = (pb - pa) % L; bwd = (pa - pb) % L
    if fwd <= bwd: ds = [pa + fwd * i / max(1, math.ceil(fwd / 1.0)) for i in range(max(1, math.ceil(fwd / 1.0)) + 1)]
    else: ds = [pa - bwd * i / max(1, math.ceil(bwd / 1.0)) for i in range(max(1, math.ceil(bwd / 1.0)) + 1)]
    pts = [ring.interpolate(d % L).coords[0] for d in ds]
    return pts + [b]

def even_run(pts, step, tol=0.1):
    """running stitch along a path: stitches up to `step` long, shorter where the path bends so that
    no stitch strays more than `tol` mm from the path; on straight parts all stitches are equal"""
    ls = LineString(pts); L = ls.length
    if L < 1e-6: return [tuple(pts[0])]
    dense = [ls.interpolate(min(L, i * 0.05)).coords[0] for i in range(int(L / 0.05) + 2)]
    out = [dense[0]]; i = 0
    while i < len(dense) - 1:
        j = i + 1
        while j + 1 < len(dense) and math.dist(dense[i], dense[j + 1]) <= step:
            seg = LineString([dense[i], dense[j + 1]])
            if max(seg.distance(Point(q)) for q in dense[i + 1:j + 1]) > tol: break
            j += 1
        out.append(dense[j]); i = j
    # even out: same number of stitches, equal length between bends would need a second pass;
    # straight runs: spread evenly
    if len(out) > 2 and LineString(out).length > 0.999 * L:
        n = len(out) - 1; out = [ls.interpolate(L * k / n).coords[0] for k in range(n + 1)]
    return out


def ordered_fill(poly, angle, spacing, maxlen, start, down=False):
    blocks = fill(poly, angle, spacing, maxlen)
    if down:   # every block top -> bottom, blocks in order of their top edge
        blocks = [b if b[0][1] <= b[-1][1] else b[::-1] for b in blocks]
        return sorted(blocks, key=lambda b: b[0][1])
    out = []; cur = start
    while blocks:
        best = None
        for i, b in enumerate(blocks):
            for rev in ((False,) if down else (False, True)):
                s0 = b[-1] if rev else b[0]
                d = math.dist(cur, s0) if cur else 0
                if best is None or d < best[0]: best = (d, i, rev)
        _, i, rev = best; b = blocks.pop(i)
        if rev: b = b[::-1]
        out.append(b); cur = b[-1]
    return out

# what a plan may set per shape: stitch type, underlay (satin: centre / contour / german / none) and any DEFAULTS key
PLAN_KEYS = None   # filled below

DEFAULTS = dict(
    comp=0.18,          # pull compensation, mm per side: tatami rows longer, satin wider (not the whole shape)
    fill_angle=45,      # tatami row angle, degrees
    fill_spacing=0.3,   # tatami row step, mm (multiple of 0.1)
    fill_maxlen=4.0,    # longest tatami stitch, mm
    fill_under_spacing=0.9,  # tatami cross underlay row step, mm (about 3x fill_spacing)
    fill_border=0.0,    # satin border round tatami / contour fills, mm wide (0 = none); hides the fill's edge
    fill_outline=0,     # running stitch along the edge after a tatami / contour fill: 0 = none, 1 or 3 passes;
                        # makes the edge sharp and hides the jagged row ends
    applique_border=3.0,  # appliqué: width of the satin covering the cut fabric edge, mm
    cross_size=2.0,     # cross stitch: cell size, mm (grid starts at the design's top left corner)
    satin_spacing=0.4,  # satin: distance between stitches on the same side, mm
    satin_max=2.8,      # wider shapes (2*area/perimeter, mm) get tatami instead of satin
    run_passes=3,       # thin strokes: running stitch passes
    run_step=2.0,       # running stitch length, mm
    thread_mm=0.35,     # thread width drawn in the coverage check (40 wt; 60 wt: 0.25, see THREADS)
    comp_stretch=0.0,   # stretchy fabric: compensation varies with stitch direction, comp x (1 -/+ s/2);
    stretch_angle=0.0,  # ... most along this direction (degrees in the design; 0 = across, as a T-shirt front
                        # hooped straight: knit stretches most along its courses)
    run_tol=0.05,       # running stitch may stray at most this far from a curved path, mm (+ up to 0.07 from the 0.1 mm grid)
    stroke_as_fill=0.8, # strokes at least this wide (mm) are stitched as shapes
    overlap=0.3,        # colour overlap under the shape on top, mm
    trim=2.0,           # cut the thread when the next start is farther, mm
    fill_staggers=4,    # tatami: rows before the hole pattern repeats
    satin_pull_pct=0.0, # satin: widen columns by this % of their width (pull compensation)
    satin_push=0.0,     # satin: shorten free column ends by this many mm (push compensation)
    satin_short=0.25,   # satin curves: inner points closer than this (mm) get a short stitch
    satin_short_inset=(0.15, 0.3),  # ... shortened by these shares of the stitch, in turn
    satin_hairpin='auto',   # narrow U-turns: 'auto' (one fanned column when rounded outside, else split), 'fan' or 'split'
    satin_min=1.0,      # satin columns narrower than this (mm) are made this wide ...
    satin_widen_max=0.3,  # ... but at most this much wider (mm), so small text keeps its counters open
    satin_force_max=10.0,  # even a plan cannot force satin on a shape wider than this (mm, average): tatami
    satin_blob=1.9,     # a part whose largest inscribed circle is wider than this x its average width is not a
                        # stroke (disc, blob, comb with a wide bar): tatami, else satin follows a skeleton that is a point
    satin_contour_from=2.0,  # satin underlay: columns this wide (mm) get edge runs instead of a centre walk
    satin_german_from=4.0,   # ... and from this width edge runs + low zigzag
    satin_split=7.0,    # satin stitches longer than this (mm) are split (wide columns)
    satin_reach=1.5,    # stroke ending against a slanted one leaving a thin wedge runs on at most this many widths
    satin_gap=0.3,      # uncovered gaps in letters at least this wide (mm) get a small tatami
    satin_mitre=60.0,   # satin corners turning up to this many degrees: stitches turn round the corner (sharper: split)
)

PLAN_KEYS = set(DEFAULTS) | {'stitch', 'underlay'}


def stroke_like(q, c):
    """satin fits a part that is a stroke: narrow on average and nowhere much wider than that"""
    w = 2 * q.area / q.length
    if w > c['satin_max']: return False
    from shapely.ops import polylabel
    pt = polylabel(q, 0.01)
    d = 2 * min([q.exterior.distance(pt)] + [r.distance(pt) for r in q.interiors])
    # nowhere much wider than its average, and nowhere wider than 1.5 x satin_max (the wide bar of a comb)
    return d <= c['satin_blob'] * w and d <= 1.5 * c['satin_max']


def suggest(g, c=None):
    """measured hints for the plan (shape g in mm at the largest size): what the rules pick and which
    other technique is worth offering, with the reason. Hints only: the person decides (KNOWLEDGE 10)."""
    c = c or DEFAULTS
    if g.is_empty or g.area <= 0: return 'run', []
    w = 2 * g.area / g.length
    rule = 'satin' if all(stroke_like(q, c) for q in polys(g)) else 'tatami'
    out = []
    if rule == 'tatami':
        parts = list(g.geoms) if hasattr(g, 'geoms') else [g]
        circ = max(4 * math.pi * q.area / q.length ** 2 for q in parts)
        segs = []
        for q in parts:
            r = list(q.simplify(0.05).exterior.coords)
            segs += [(r[i], r[i + 1]) for i in range(len(r) - 1)]
        def turn(i):
            (a0, a1), (b0, b1) = segs[i - 1], segs[i]
            u = math.atan2(a1[1] - a0[1], a1[0] - a0[0]); v = math.atan2(b1[1] - b0[1], b1[0] - b0[0])
            return abs((math.degrees(v - u) + 180) % 360 - 180)
        sharp = sum(1 for i in range(len(segs)) if turn(i) > 40)
        axis = all(min(abs(a[0] - b[0]), abs(a[1] - b[1])) < 0.05 for a, b in segs)
        grid = axis and len(segs) >= 8
        if grid:
            out.append(('cross', 'only horizontal and vertical edges, stepped like a grid: cross stitch, if it is a folk or grid pattern'))
        elif circ >= 0.8 and sharp == 0:
            out.append(('contour', f'round (roundness {circ:.2f}, no sharp corners): contour fill looks domed and pulls evenly'))
        if g.area >= 1500:
            out.append(('applique', f'large area ({g.area / 100:.0f} cm²): appliqué is softer, faster and fewer stitches (~{g.area * 6 / 1000:.0f}k as tatami)'))
        if w >= 6 and not grid:
            out.append(('fill_border', 'wide fill: a satin border (2–3 mm) makes the edge sharp, if the edge matters in the design'))
    return rule, out
FILL_STITCHES = ('satin', 'tatami', 'contour', 'applique', 'cross')   # plan "stitch" values for shapes

# starting points per fabric (KNOWLEDGE.md, section 8); everything else stays at DEFAULTS
# thread weight: 40 wt is the normal embroidery thread (all settings above are for it). 60 wt is
# thinner (about 0.25 mm): for small text (< 4-5 mm) and fine detail, with a 65/9 needle. Settings
# scale from the fabric's 40 wt values; `thread_mm` is the drawn width in the coverage check.
THREADS = {
    40: dict(scale=dict(), thread_mm=0.35),
    60: dict(scale=dict(satin_spacing=0.7, fill_spacing=0.75, satin_min=0.6, satin_widen_max=0.6, comp=0.7, run_step=0.75), thread_mm=0.25),
}

def thread_cfg(cfg, weight):
    """settings for a thread weight, starting from cfg (fabric + user settings)"""
    t = THREADS[int(weight)]; c = dict(DEFAULTS, **cfg)
    out = dict(cfg)
    for k, f in t['scale'].items(): out[k] = round(float(c[k]) * f, 3)
    out['thread_mm'] = t['thread_mm']
    return out

FABRICS = {
    'linen':   dict(),
    'cotton':  dict(),
    'denim':   dict(fill_spacing=0.4, comp=0.15),
    'canvas':  dict(fill_spacing=0.4, comp=0.15),
    'jersey':  dict(fill_spacing=0.4, satin_spacing=0.45, comp=0.30, comp_stretch=0.5, fill_under_spacing=0.75, satin_min=1.2),
    'fleece':  dict(fill_spacing=0.4, satin_spacing=0.4, comp=0.25, comp_stretch=0.3, fill_under_spacing=0.75, satin_min=1.5, satin_contour_from=1.5, satin_german_from=3.0),
    'terry':   dict(fill_spacing=0.4, satin_spacing=0.4, comp=0.25, fill_under_spacing=0.75, satin_min=1.5, satin_contour_from=1.5, satin_german_from=3.0),
    'leather': dict(fill_spacing=0.5, satin_spacing=0.45, comp=0.12, fill_under_spacing=0, satin_min=1.2),
    'vinyl':   dict(fill_spacing=0.5, satin_spacing=0.45, comp=0.12, fill_under_spacing=0, satin_min=1.2),
}


def build(elements, size_mm, threads, cfg=None, ref_size=None, plan=None, scale=None, ref_scale=None):
    """elements: design.load() output (SVG units, sewing order); size_mm: longer side;
    threads: {'#rrggbb': 'name'}; ref_size: size used to choose satin or tatami for each shape
    (the largest size, so every size is stitched the same way).
    plan: digitizing decisions per shape (numbers as in swatch.py --list), see PLAN_KEYS:
      {"shapes": {"5": {"stitch": "satin", "satin_spacing": 0.35, "underlay": "contour"}, ...},
       "order": [30, 0, 1, ...]}   (order inside each colour; shapes not listed follow in the usual order)
    Returns a centred pattern with .underlay (points, 0.1 mm)."""
    global OVERLAP, STAGGERS
    c = dict(DEFAULTS, **(cfg or {}))
    STAGGERS = max(1, int(c['fill_staggers']))
    def set_satin(c):
        SAT.OPTS.update(pull_mm=float(c['comp']), stretch=float(c['comp_stretch']), stretch_angle=float(c['stretch_angle']), pull_pct=float(c['satin_pull_pct']), push_mm=float(c['satin_push']),
                        short_dist=float(c['satin_short']), split_len=float(c['satin_split']), mitre_max=float(c['satin_mitre']), reach=float(c['satin_reach']), gap_min=float(c['satin_gap']), min_width=float(c['satin_min']), max_widen=float(c['satin_widen_max']),
                        contour_from=float(c['satin_contour_from']), german_from=float(c['satin_german_from']),
                        short_inset=tuple(c['satin_short_inset']) if isinstance(c['satin_short_inset'], (list, tuple)) else (float(c['satin_short_inset']),),
                        hairpin=c['satin_hairpin'], underlay=c.get('underlay'))
    set_satin(c)
    # scale so the longer side of the whole design = size_mm
    from shapely.ops import unary_union
    allg = unary_union([e['geom'] if e['kind'] == 'fill' else e['geom'].buffer(e.get('width', 0) / 2) for e in elements])
    x0, y0, x1, y1 = allg.bounds
    s = scale or size_mm / max(x1 - x0, y1 - y0)                 # mm per SVG unit (scale: fixed, for single shapes)
    sr = ref_scale or (ref_size or size_mm) / max(x1 - x0, y1 - y0)
    shp = {int(k): v for k, v in ((plan or {}).get('shapes') or {}).items()}
    bad = [k for v in shp.values() for k in v if k not in PLAN_KEYS]
    if bad: raise ValueError(f'unknown plan keys: {bad}; allowed: {sorted(PLAN_KEYS)}')
    els = []
    for idx, e in enumerate(elements):
        g = affinity.scale(e['geom'], s, s, origin=(0, 0))
        e = dict(e, geom=g, id=idx, cfg=shp.get(idx, {}))
        if e['kind'] == 'run' and e.get('width', 0) * s >= c['stroke_as_fill']:
            e = dict(e, kind='fill', geom=g.buffer(e['width'] * s / 2, cap_style=2, join_style=2))
        if e['kind'] == 'fill':   # satin or tatami, decided at the reference size
            parts = polys(affinity.scale(e['geom'], sr / s, sr / s, origin=(0, 0)).buffer(c['comp'], join_style=2))
            e['stitch'] = 'satin' if parts and all(stroke_like(q, c) for q in parts) else 'tatami'
            if e['cfg'].get('stitch') in FILL_STITCHES: e['stitch'] = e['cfg']['stitch']
            if e['stitch'] == 'satin' and any(2 * q.area / q.length > c['satin_force_max'] for q in polys(e['geom'])):
                print(f"WARNING: shape {idx} is too wide for satin at this size; tatami instead")
                e['stitch'] = 'tatami'
        if e['cfg'].get('stitch') == 'run' and e['kind'] == 'run': e['stitch'] = 'run'
        els.append(e)
    els = knockout(els, c['overlap'])
    GRID0 = (x0 * s, y0 * s)                        # cross stitch grid origin: design's top left corner

    pat = pe.EmbPattern()
    KINDS = set(); CUR = [None]; STOPS = []
    cur = [None]; prevpt = [None]; UL = []

    def stitch_block(pts, connect=False, under=None, force_trim=False):
        if not pts: return
        if under is not None and connect and cur[0] is not None: under = (under[0] + 1, under[1] + 1)
        if under is not None:
            q = list(([cur[0]] + list(pts)) if connect and cur[0] is not None else pts)
            UL.extend(q[under[0]:under[1]])
        if connect and cur[0] is not None: pts = [cur[0]] + list(pts)
        x0, y0 = pts[0]
        far = cur[0] is not None and (math.dist(cur[0], (x0, y0)) > c['trim'] or force_trim)
        if far: pat.add_command(pe.TRIM)
        if cur[0] is None or far:
            pat.add_stitch_absolute(pe.JUMP, x0 * 10, y0 * 10)
            if len(pts) > 1:   # tie-in along the first stitch
                x1, y1 = pts[1]; d = math.dist((x0, y0), (x1, y1)) or 1
                Lt = min(0.7, d * 0.9); ux, uy = (x1 - x0) / d * Lt, (y1 - y0) / d * Lt
                for (a, b) in [(x0 + ux, y0 + uy), (x0, y0), (x0 + ux, y0 + uy), (x0, y0)]:
                    pat.add_stitch_absolute(pe.STITCH, a * 10, b * 10)
        last = (x0, y0)
        for idx, (x, y) in enumerate(pts[1:], start=1):
            d = math.dist(last, (x, y)); n = max(1, math.ceil(d / 7.0))
            for j in range(1, n + 1):
                pat.add_stitch_absolute(pe.STITCH, (last[0] + (x - last[0]) * j / n) * 10, (last[1] + (y - last[1]) * j / n) * 10)
                if under is not None and under[0] < idx < under[1] and j < n:
                    UL.append((last[0] + (x - last[0]) * j / n, last[1] + (y - last[1]) * j / n))
            if math.dist(last, (x, y)) > 0.05: prevpt[0] = last
            last = (x, y)
        cur[0] = last

    def tie_off():
        # lock stitches back along the last stitch, so they stay inside the shape
        if cur[0] is None: return
        x, y = cur[0]; px, py = prevpt[0] if prevpt[0] else (x - 1, y)
        d = math.dist((x, y), (px, py)) or 1; L = min(0.5, d * 0.8)
        ux, uy = (px - x) / d * L, (py - y) / d * L
        for (a, b) in [(x + ux, y + uy), (x, y), (x + ux, y + uy), (x, y)]:
            pat.add_stitch_absolute(pe.STITCH, a * 10, b * 10)

    def run(pts, passes, step):
        fwd = even_run(pts, step, c['run_tol'])
        seq = fwd
        for k in range(1, passes): seq = seq + (fwd[::-1] if k % 2 else fwd)[1:]
        return seq

    def tatami(p, c=c):
        global OVERLAP
        OVERLAP = True
        full = p
        if c['fill_border'] > 0:                                 # fill goes 0.3 mm under the border
            p = p.buffer(-(c['fill_border'] - 0.3), join_style=2)
            # sharp tips (< 60 deg): the border's corner stitch may be at most twice the column's
            # half width, so it stops short of the tip; the fill runs out to the tip there instead
            from shapely.ops import unary_union
            hw = c['fill_border'] / 2; tips = []
            for q in polys(full):
                pts = list(q.exterior.coords)[:-1]
                for i, v in enumerate(pts):
                    a, b = pts[i - 1], pts[(i + 1) % len(pts)]
                    u1 = (a[0] - v[0], a[1] - v[1]); u2 = (b[0] - v[0], b[1] - v[1])
                    l1, l2 = math.hypot(*u1), math.hypot(*u2)
                    if l1 < 1e-6 or l2 < 1e-6: continue
                    th = math.acos(max(-1, min(1, (u1[0] * u2[0] + u1[1] * u2[1]) / l1 / l2)))
                    if th < math.radians(60) and q.buffer(-0.05).contains(Point(v[0] + (u1[0] / l1 + u2[0] / l2) * 0.1, v[1] + (u1[1] / l1 + u2[1] / l2) * 0.1)):
                        r = hw / math.sin(th / 2) - 2 * hw + 0.4          # part of the tip the border cannot reach
                        tips.append(q.intersection(Point(v).buffer(r)))
            if tips: p = unary_union([p] + tips)
            if p.is_empty: p = full
        for q in polys(p.buffer(-0.35)):                         # edge underlay
            rr = run(list(q.exterior.coords), 1, 2.0); stitch_block(rr, under=(0, len(rr)))
        for q in (polys(p.buffer(-0.4)) if c['fill_under_spacing'] > 0 else []):   # cross underlay
            for blk in ordered_fill(q, c['fill_angle'] + 90, c['fill_under_spacing'], c['fill_maxlen'], cur[0]):
                if cur[0] is not None and math.dist(cur[0], blk[0]) > 0.6: blk = travel_path(cur[0], blk[0], p)[1:-1] + blk
                stitch_block(blk, connect=True, under=(0, len(blk)))
        global ROWCOMP
        SAT.OPTS.update(pull_mm=float(c['comp']), stretch=float(c['comp_stretch']), stretch_angle=float(c['stretch_angle']))
        ROWCOMP = SAT.pull_for(math.cos(math.radians(c['fill_angle'])), math.sin(math.radians(c['fill_angle'])))   # top rows only: longer at both ends, by comp along the rows' direction
        top = ordered_fill(p, c['fill_angle'], c['fill_spacing'], c['fill_maxlen'], cur[0], down=True)
        ROWCOMP = 0.0
        for k, blk in enumerate(top):
            if k > 0 and math.dist(cur[0], blk[0]) > 0.6: tie_off(); stitch_block(blk)   # each part from its top
            else: stitch_block(blk, connect=k > 0)
        tie_off()
        if c['fill_outline'] > 0: outline(full, c)
        if c['fill_border'] > 0: border(full, c)

    def outline(p, c=c):
        """running stitch round every edge of the shape, each ring starting next to where the last one ended"""
        rings = [r for q in polys(p) for r in [q.exterior] + list(q.interiors) if r.length > 1.0]
        while rings:
            rings.sort(key=lambda r: r.distance(Point(cur[0])) if cur[0] else 0)
            r = rings.pop(0)
            line = start_on_side(list(r.coords), cur[0], 1.0)
            pts = run(line, int(c['fill_outline']), 2.0)
            near = cur[0] is not None and math.dist(cur[0], pts[0]) <= c['trim']
            if not near and cur[0] is not None: tie_off()
            stitch_block(pts, connect=near)
        tie_off()
        KINDS.add('outline')

    def border_band(p, c=c, w=None):
        """area the border satin covers (outline rings, w wide, centre line as in border())"""
        from shapely.ops import unary_union
        w = w or c['fill_border']; out = []
        for q in polys(p):
            for k, ring in enumerate([q.exterior] + list(q.interiors)):
                rp = Polygon(ring)
                mid = rp.buffer(-w / 2, join_style=1) if k == 0 else rp.buffer(w / 2, join_style=1)
                out += [m.exterior.buffer(w / 2 + 0.01, cap_style=2, join_style=2) for m in polys(mid)]
        return unary_union(out) if out else Polygon()

    def border(p, c=c, w=None):
        """satin border along every outline ring: outer edge = outline + comp, inner edge w inside"""
        w = w or c['fill_border']; KINDS.add('border')
        set_satin(c); saved = SAT.OPTS['mitre_max']; SAT.OPTS['mitre_max'] = 135.0   # a ring turns every corner
        try:
            for q in polys(p):
                for k, ring in enumerate([q.exterior] + list(q.interiors)):
                    rp = Polygon(ring)
                    # round join: at an inward corner (heart notch) the centre line arcs round the corner
                    # instead of a mitre spike; outward corners (rectangle) stay sharp either way
                    mid = rp.buffer(-w / 2, join_style=1) if k == 0 else rp.buffer(w / 2, join_style=1)
                    for m in polys(mid):
                        line = start_on_side(list(m.exterior.coords), cur[0], 3 * w)
                        band = LineString(line).buffer(w / 2 + 0.01, cap_style=2, join_style=2)
                        prs = SAT.column_pairs(band, line, c['satin_spacing'], width=w, caps=(False, False))
                        if not prs: continue
                        und = run(line, 1, 2.0)
                        stitch_block(und + SAT.zig(prs, c['satin_spacing']), under=(0, len(und)))
                        tie_off()
        finally:
            SAT.OPTS['mitre_max'] = saved

    def contour(p, c=c):
        """contour fill: rows follow the outline inwards (rounded shapes look domed, pull is even).
        While the shape stays one piece without holes the rows form one spiral (no seam of hops); a band
        with one hole is two spirals (from the outer edge in, then from the middle out to the hole);
        otherwise each ring is sewn on its own, starting next to where the last one ended."""
        sp = c['fill_spacing']
        for q in polys(p.buffer(-0.35)):                           # edge underlay
            rr = run(list(q.exterior.coords), 1, 2.0); stitch_block(rr, under=(0, len(rr)))
        levels = []; k = 0
        while k < 2000:
            off = sp / 2 + k * sp - c['comp']
            inner = p.buffer(-off, join_style=1) if off > 0 else p.buffer(-off, join_style=2)
            if inner.is_empty: break
            levels.append(polys(inner)); k += 1
        first = True; i = 0
        while i < len(levels):
            simple = lambda L: len(L) == 1 and not list(L[0].interiors)
            if simple(levels[i]):
                j = i
                while j + 1 < len(levels) and simple(levels[j + 1]): j += 1
                pts = spiral([levels[t][0].exterior for t in range(i, j + 1)], cur[0], c['fill_maxlen'])
                stitch_block(pts, connect=not first and cur[0] is not None and math.dist(cur[0], pts[0]) <= c['trim'])
                first = False; i = j + 1; continue
            # a ring-shaped band (one piece, one hole): the rows from the outer edge and the rows around the
            # hole are two concentric families; each is sewn as one spiral (no seam where a ring would start)
            annulus = lambda L: len(L) == 1 and len(L[0].interiors) == 1
            if annulus(levels[i]):
                j = i
                while j + 1 < len(levels) and annulus(levels[j + 1]): j += 1
                if j > i:
                    outer_r = [levels[t][0].exterior for t in range(i, j + 1)]
                    inner_r = [levels[t][0].interiors[0] for t in range(j, i - 1, -1)]   # from the middle out to the hole
                    for fam in (outer_r, inner_r):
                        pts = spiral(fam, cur[0], c['fill_maxlen'])
                        stitch_block(pts, connect=not first and cur[0] is not None and math.dist(cur[0], pts[0]) <= c['trim'])
                        first = False
                    i = j + 1; continue
            rings = [r for q in levels[i] for r in [q.exterior] + list(q.interiors) if r.length > 0.6]
            rings.sort(key=lambda r: r.distance(Point(cur[0])) if cur[0] else 0)
            for r in rings:
                line = start_on_side(list(r.coords), cur[0], 0)
                pts = run(line, 1, c['fill_maxlen'])
                stitch_block(pts, connect=not first and cur[0] is not None and math.dist(cur[0], pts[0]) <= c['trim'])
                first = False
            i += 1
        # the middle: the last ring leaves an opening up to one row spacing wide (an ellipse leaves a
        # slot along its long axis); a running stitch down the middle of that opening closes it
        if levels:
            for q in levels[-1]:
                if list(q.interiors): continue                      # a ring (shape with a hole) ends in a ring, no middle
                core = q.buffer(-sp / 2)
                if core.is_empty: core = q
                rr = core.minimum_rotated_rectangle
                xy = list(rr.exterior.coords)[:4]
                e1 = (xy[0], xy[1]); e2 = (xy[1], xy[2])
                lng, sht = (e1, e2) if math.dist(*e1) >= math.dist(*e2) else (e2, e1)
                half = ((sht[1][0] - sht[0][0]) / 2, (sht[1][1] - sht[0][1]) / 2)
                a_ = (lng[0][0] + half[0], lng[0][1] + half[1]); b_ = (lng[1][0] + half[0], lng[1][1] + half[1])
                # run on along the axis to where the rings' pointed ends still stand apart (3 rings out)
                outer = [g for g in levels[max(0, len(levels) - 4)] if g.intersects(q)]
                reach = outer[0].buffer(-sp / 2) if outer else q
                ext = 0.5 * max(reach.bounds[2] - reach.bounds[0], reach.bounds[3] - reach.bounds[1])
                dx_, dy_ = b_[0] - a_[0], b_[1] - a_[1]; dl = math.hypot(dx_, dy_) or 1
                a_ = (a_[0] - dx_ / dl * ext, a_[1] - dy_ / dl * ext); b_ = (b_[0] + dx_ / dl * ext, b_[1] + dy_ / dl * ext)
                mid_line = LineString([a_, b_]).intersection(reach if not reach.is_empty else q)
                if mid_line.is_empty or mid_line.length < 0.3: continue
                ml = max(getattr(mid_line, 'geoms', [mid_line]), key=lambda g: g.length)
                pts = list(ml.coords)
                if cur[0] is not None and math.dist(cur[0], pts[-1]) < math.dist(cur[0], pts[0]): pts = pts[::-1]
                stitch_block(run(pts, 1, c['fill_maxlen'] / 2), connect=cur[0] is not None and math.dist(cur[0], pts[0]) <= c['trim'])
        tie_off()
        if c['fill_outline'] > 0: outline(p, c)
        if c['fill_border'] > 0: border(p, c)

    def spiral(rings, near, step):
        """one continuous path from the outer ring inwards: along ring k the path drifts to ring k+1.
        The first ring is sewn once in full before the drift starts, otherwise the edge just behind the
        start would be one row spacing short (a thin wedge of bare fabric)."""
        if len(rings) > 1: rings = [rings[0]] + list(rings)
        out = []
        start = Point(near) if near else Point(rings[0].coords[0])
        for k, r in enumerate(rings):
            nxt = rings[k + 1] if k + 1 < len(rings) else None
            L = r.length; s0 = r.project(start)
            n = max(8, int(L / 0.5))
            if nxt is not None:
                t0 = nxt.project(Point(r.interpolate(s0).coords[0])); Ln = nxt.length
            for m in range(n):
                f = m / n
                a_ = r.interpolate((s0 + f * L) % L).coords[0]
                if nxt is not None:
                    b_ = nxt.interpolate((t0 + f * Ln) % Ln).coords[0]
                    out.append((a_[0] + (b_[0] - a_[0]) * f, a_[1] + (b_[1] - a_[1]) * f))
                else: out.append(a_)
            if nxt is not None: start = Point(nxt.interpolate(t0).coords[0])
            else: out.append(r.interpolate(s0).coords[0])
        return even_run(out, step, c['run_tol'])

    def start_on_side(line, near, minlen):
        """rotate a closed ring to start in the middle of a straight side (not on a corner),
        the side nearest to `near`; sides shorter than minlen are skipped when possible"""
        segs = [(k, math.dist(line[k], line[k + 1])) for k in range(len(line) - 1)]
        long_ = [k for k, L in segs if L >= minlen] or [max(segs, key=lambda t: t[1])[0]]
        k = min(long_, key=lambda k: math.dist(near, ((line[k][0] + line[k + 1][0]) / 2, (line[k][1] + line[k + 1][1]) / 2))) if near else long_[0]
        mid = ((line[k][0] + line[k + 1][0]) / 2, (line[k][1] + line[k + 1][1]) / 2)
        return [mid] + line[k + 1:-1] + line[:k + 1] + [mid]

    def stop(label):
        """machine stop (a colour change to the same thread) with a note for the person at the machine"""
        tie_off(); pat.add_command(pe.TRIM); pat.add_command(pe.COLOR_CHANGE); cur[0] = None
        pat.add_thread({'color': int(CUR[0][1:], 16), 'name': label})
        STOPS.append(label)

    def applique(p, c=c):
        """appliqué: placement line, stop (lay the fabric), tack-down, stop (cut the fabric), satin cover"""
        for q in polys(p):
            for ring in [q.exterior] + list(q.interiors):
                stitch_block(run(list(ring.coords), 1, 2.0)); tie_off()
        stop('Aplikatsioon: aseta kangas')   # label shown to the person at the machine (Estonian, like the PDF)
        for q in polys(p.buffer(-0.5, join_style=2)):
            for ring in [q.exterior] + list(q.interiors):
                stitch_block(run(list(ring.coords), 1, 1.5)); tie_off()
        stop('Aplikatsioon: lõika kangas')
        border(p, c, c['applique_border'])

    def cross(p, c=c):
        """cross stitch on a grid: '/' under '\\', travel only along the diagonals (hidden)"""
        a = c['cross_size']; ox, oy = GRID0
        x0_, y0_, x1_, y1_ = p.bounds
        cells = []
        for j in range(int((y0_ - oy) // a), int((y1_ - oy) // a) + 1):
            row = []
            for i in range(int((x0_ - ox) // a), int((x1_ - ox) // a) + 1):
                cx, cy = ox + i * a, oy + j * a
                b = Polygon([(cx, cy), (cx + a, cy), (cx + a, cy + a), (cx, cy + a)])
                if p.intersection(b).area >= 0.5 * a * a: row.append((i, j))
            cells.append(row if (j % 2 == 0) else row[::-1])            # rows back and forth
        corner = lambda i, j, u, v: (ox + (i + u) * a, oy + (j + v) * a)
        blk = []; prev = None
        for (i, j) in [cell for row in cells for cell in row]:
            C = corner(i, j, 0.5, 0.5)
            if prev is not None and abs(prev[0] - i) <= 1 and abs(prev[1] - j) <= 1 and prev != (i, j):
                # go from the previous centre over a shared corner into this centre (both on diagonals)
                pi, pj = prev
                shared = [corner(pi, pj, u, v) for u in (0, 1) for v in (0, 1)
                          if abs(pi + u - i - 0.5) <= 0.5 + 1e-9 and abs(pj + v - j - 0.5) <= 0.5 + 1e-9]
                blk.append(shared[0])
            elif blk:
                stitch_block(blk); tie_off(); blk = []
            blk += [C, corner(i, j, 0, 1), corner(i, j, 1, 0), C, corner(i, j, 0, 0), corner(i, j, 1, 1), C]
            prev = (i, j)
        if blk: stitch_block(blk); tie_off()

    cache = []   # identical shapes get identical stitches

    def satin_seq(p, c=c):
        global OVERLAP
        OVERLAP = False
        ox, oy = math.floor(p.bounds[0] * 10) / 10, math.floor(p.bounds[1] * 10) / 10
        q = affinity.translate(p, -ox, -oy)
        key = tuple(sorted((k, str(v)) for k, v in c.items()))
        for g, k_, seq in cache:
            if k_ == key and g.symmetric_difference(q).area < 0.02 * q.area: break
        else:
            seq = SAT.letter(q, None, c['satin_spacing'], fill=lambda g: [b for r in polys(g) for b in fill(r, 45, 0.4, 3.5)])
            seq = [([(round(x, 1), round(y, 1)) for x, y in blk], ur, j) for blk, ur, j in seq]
            cache.append((q, key, seq))
        return [([(x + ox, y + oy) for x, y in blk], ur, j) for blk, ur, j in seq]

    def satin(p, c=c):
        set_satin(c)
        for k, (blk, ur, jump) in enumerate(satin_seq(p, c)):
            if k > 0 and jump: tie_off(); stitch_block(blk, under=ur, force_trim=True)
            else: stitch_block(blk, connect=k > 0, under=ur)
        tie_off()
        if c['fill_outline'] > 0: outline(p, c)        # running stitch along the satin's edge, if asked

    # colour groups in order of first appearance; inside a group: document order,
    # narrow shapes (text) in reading order
    colors = []
    for e in els:
        if e['color'] not in colors: colors.append(e['color'])
    for ci, col in enumerate(colors):
        if ci > 0:
            pat.add_command(pe.TRIM); pat.add_command(pe.COLOR_CHANGE); cur[0] = None
        pat.add_thread({'color': int(col[1:], 16), 'name': threads.get(col, col)}); CUR[0] = col
        items = []
        for e in els:
            if e['color'] != col: continue
            ce = dict(c, **{k: v for k, v in e['cfg'].items() if k != 'stitch'})
            if e['kind'] == 'run':
                items.append(('run', e['geom'], ce, e['id'])); continue
            for p in polys(e['geom']):     # pull compensation: along tatami rows / across satin stitches
                items.append((e['stitch'], p, ce, e['id']))
        order = [int(v) for v in ((plan or {}).get('order') or [])]
        if order:   # planned order first (stable for pieces of one shape), the rest after in the usual order
            rank = {v: i for i, v in enumerate(order)}
            planned = sorted([it for it in items if it[3] in rank], key=lambda it: rank[it[3]])
            items = [it for it in items if it[3] not in rank]
        else: planned = []
        # reading order for consecutive satin pieces: rows by vertical position, then left to right
        out = []; i = 0
        while i < len(items):
            if items[i][0] != 'satin': out.append(items[i]); i += 1; continue
            j = i
            while j < len(items) and items[j][0] == 'satin': j += 1
            grp = items[i:j]
            hs = sorted(it[1].bounds[3] - it[1].bounds[1] for it in grp); tol = 0.6 * hs[len(hs) // 2]
            rows = []
            for it in sorted(grp, key=lambda t: (t[1].bounds[1] + t[1].bounds[3]) / 2):
                yc = (it[1].bounds[1] + it[1].bounds[3]) / 2
                if rows and abs(yc - rows[-1][0]) <= tol: rows[-1][1].append(it)
                else: rows.append([yc, [it]])
            for _, r in rows: out += sorted(r, key=lambda t: t[1].bounds[0])
            i = j
        for kind, g, ce, _id in planned + out:
            KINDS.add(kind)
            if kind == 'run':
                stitch_block(run(list(g.coords), ce['run_passes'], ce['run_step'])); tie_off()
            elif kind == 'tatami': tatami(g, ce)
            elif kind == 'contour': contour(g, ce)
            elif kind == 'applique': applique(g, ce)
            elif kind == 'cross': cross(g, ce)
            else: satin(g, ce)

    # clean: drop duplicates / stitches < 0.15 mm, keep the last stitch before any command
    cleaned = []; last = None; S = pat.stitches
    for i, (x, y, cmd) in enumerate(S):
        if (cmd & pe.COMMAND_MASK) == pe.STITCH:
            nxt_cmd = i + 1 >= len(S) or (S[i + 1][2] & pe.COMMAND_MASK) != pe.STITCH
            if last is not None and math.dist(last, (x, y)) < 1.5 and not nxt_cmd: continue
            if last is not None and math.dist(last, (x, y)) < 5.0 and nxt_cmd and cleaned and (cleaned[-1][2] & pe.COMMAND_MASK) == pe.STITCH:
                cleaned[-1] = [x, y, cmd]; last = (x, y); continue
            cleaned.append([x, y, cmd]); last = (x, y)
        else:
            cleaned.append([x, y, cmd])
            if (cmd & pe.COMMAND_MASK) == pe.JUMP: last = (x, y)
    pat.stitches = cleaned
    pat.add_command(pe.END)
    # centre (whole 0.1 mm steps keep the grid)
    st = [(x, y) for x, y, cmd in pat.stitches if (cmd & pe.COMMAND_MASK) == pe.STITCH]
    x0, x1 = min(x for x, y in st), max(x for x, y in st); y0, y1 = min(y for x, y in st), max(y for x, y in st)
    tx, ty = -round((x0 + x1) / 2), -round((y0 + y1) / 2)
    pat.translate(tx, ty)
    pat.scale_mm, pat.offset = s, (tx, ty)
    pat.kinds = sorted(KINDS)                        # stitch types used: run, satin, tatami, contour, applique, cross, border
    pat.stops = STOPS                                # machine stops inside a colour (appliqué), in order          # shape in pattern units = SVG * scale_mm * 10 + offset
    pat.underlay = [(round(x * 10 + tx), round(y * 10 + ty)) for x, y in UL]
    # visible area of every filled shape, in pattern units: for the coverage check (coverage.py)
    # (fills: the coverage target is satin, tatami and contour; every element bounds where stitches may go)
    def margin(e):    # how far this stitch type may reach past the shape by design (mm)
        st_ = e.get('stitch')
        if st_ == 'cross': return float({**c, **e['cfg']}.get('cross_size', 2.0))          # whole grid squares
        return 0.0
    pat.shapes = [dict(id=e['id'], kind=e['kind'], stitch=e.get('stitch', e['kind']), width=e.get('width', 0) * s, margin=margin(e),
                       geom=affinity.affine_transform(e['geom'], [10, 0, 0, 10, tx, ty]))
                  for e in els if not e['geom'].is_empty]
    pat.comp = float(c['comp']) * (1 + float(c['comp_stretch']) / 2) + float(c['satin_widen_max']) / 2
    pat.thread_mm = float(c['thread_mm'])    # how far stitches may reach out: compensation + widening of thin satin
    return pat
