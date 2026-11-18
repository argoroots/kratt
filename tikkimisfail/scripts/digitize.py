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
                    if LineString(tp).length < 4 * seg.length + 2: pts += tp[1:-1]
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
    satin_spacing=0.4,  # satin: distance between stitches on the same side, mm
    satin_max=2.8,      # wider shapes (2*area/perimeter, mm) get tatami instead of satin
    run_passes=3,       # thin strokes: running stitch passes
    run_step=2.0,       # running stitch length, mm
    run_tol=0.1,        # running stitch may stray at most this far from a curved path, mm
    stroke_as_fill=0.8, # strokes at least this wide (mm) are stitched as shapes
    overlap=0.3,        # colour overlap under the shape on top, mm
    trim=2.0,           # cut the thread when the next start is farther, mm
    fill_staggers=4,    # tatami: rows before the hole pattern repeats
    satin_pull_pct=0.0, # satin: widen columns by this % of their width (pull compensation)
    satin_push=0.0,     # satin: shorten free column ends by this many mm (push compensation)
    satin_short=0.25,   # satin curves: inner points closer than this (mm) get a short stitch
    satin_min=1.0,      # satin columns narrower than this (mm) are made this wide
    satin_contour_from=2.0,  # satin underlay: columns this wide (mm) get edge runs instead of a centre walk
    satin_german_from=4.0,   # ... and from this width edge runs + low zigzag
    satin_split=7.0,    # satin stitches longer than this (mm) are split (wide columns)
    satin_reach=1.5,    # stroke ending against a slanted one leaving a thin wedge runs on at most this many widths
    satin_gap=0.3,      # uncovered gaps in letters at least this wide (mm) get a small tatami
    satin_mitre=60.0,   # satin corners turning up to this many degrees: stitches turn round the corner (sharper: split)
)

PLAN_KEYS = set(DEFAULTS) | {'stitch', 'underlay'}

# starting points per fabric (TEADMISED.md, section 8); everything else stays at DEFAULTS
FABRICS = {
    'linane':  dict(),
    'puuvill': dict(),
    'teksas':  dict(fill_spacing=0.4, comp=0.15),
    'kanvas':  dict(fill_spacing=0.4, comp=0.15),
    'trikoo':  dict(fill_spacing=0.4, satin_spacing=0.45, comp=0.30, fill_under_spacing=0.75, satin_min=1.2),
    'fliis':   dict(fill_spacing=0.4, satin_spacing=0.4, comp=0.25, fill_under_spacing=0.75, satin_min=1.5, satin_contour_from=1.5, satin_german_from=3.0),
    'frotee':  dict(fill_spacing=0.4, satin_spacing=0.4, comp=0.25, fill_under_spacing=0.75, satin_min=1.5, satin_contour_from=1.5, satin_german_from=3.0),
    'nahk':    dict(fill_spacing=0.5, satin_spacing=0.45, comp=0.12, fill_under_spacing=0, satin_min=1.2),
    'vinüül':  dict(fill_spacing=0.5, satin_spacing=0.45, comp=0.12, fill_under_spacing=0, satin_min=1.2),
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
        SAT.OPTS.update(pull_mm=float(c['comp']), pull_pct=float(c['satin_pull_pct']), push_mm=float(c['satin_push']),
                        short_dist=float(c['satin_short']), split_len=float(c['satin_split']), mitre_max=float(c['satin_mitre']), reach=float(c['satin_reach']), gap_min=float(c['satin_gap']), min_width=float(c['satin_min']),
                        contour_from=float(c['satin_contour_from']), german_from=float(c['satin_german_from']),
                        underlay=c.get('underlay'))
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
            ws = [2 * p.area / p.length for p in polys(affinity.scale(e['geom'], sr / s, sr / s, origin=(0, 0)).buffer(c['comp'], join_style=2))]
            e['stitch'] = 'satin' if ws and max(ws) <= c['satin_max'] else 'tatami'
            if e['cfg'].get('stitch') in ('satin', 'tatami'): e['stitch'] = e['cfg']['stitch']
        if e['cfg'].get('stitch') == 'run' and e['kind'] == 'run': e['stitch'] = 'run'
        els.append(e)
    els = knockout(els, c['overlap'])

    pat = pe.EmbPattern()
    KINDS = set()
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
        for q in polys(p.buffer(-0.35)):                         # edge underlay
            rr = run(list(q.exterior.coords), 1, 2.0); stitch_block(rr, under=(0, len(rr)))
        for q in (polys(p.buffer(-0.4)) if c['fill_under_spacing'] > 0 else []):   # cross underlay
            for blk in ordered_fill(q, c['fill_angle'] + 90, c['fill_under_spacing'], c['fill_maxlen'], cur[0]):
                if cur[0] is not None and math.dist(cur[0], blk[0]) > 0.6: blk = travel_path(cur[0], blk[0], p)[1:-1] + blk
                stitch_block(blk, connect=True, under=(0, len(blk)))
        global ROWCOMP
        ROWCOMP = c['comp']                                       # top rows only: longer by comp at both ends
        top = ordered_fill(p, c['fill_angle'], c['fill_spacing'], c['fill_maxlen'], cur[0], down=True)
        ROWCOMP = 0.0
        for k, blk in enumerate(top):
            if k > 0 and math.dist(cur[0], blk[0]) > 0.6: tie_off(); stitch_block(blk)   # each part from its top
            else: stitch_block(blk, connect=k > 0)
        tie_off()

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

    # colour groups in order of first appearance; inside a group: document order,
    # narrow shapes (text) in reading order
    colors = []
    for e in els:
        if e['color'] not in colors: colors.append(e['color'])
    for ci, col in enumerate(colors):
        if ci > 0:
            pat.add_command(pe.TRIM); pat.add_command(pe.COLOR_CHANGE); cur[0] = None
        pat.add_thread({'color': int(col[1:], 16), 'name': threads.get(col, col)})
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
    pat.kinds = sorted(KINDS)                        # stitch types used: run, satin, tatami          # shape in pattern units = SVG * scale_mm * 10 + offset
    pat.underlay = [(round(x * 10 + tx), round(y * 10 + ty)) for x, y in UL]
    return pat
