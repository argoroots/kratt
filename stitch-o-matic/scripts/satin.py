"""Satin columns for thin letter strokes: skeleton -> branches -> centre-walk underlay + satin back."""
import math
import numpy as np
import networkx as nx
from skimage.draw import polygon as skpoly
from skimage.morphology import skeletonize
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring

RES = 0.02  # mm per pixel

# satin options (mm unless noted)
OPTS = dict(
    short_dist=0.25,     # same-side needle points closer than this (inside of curves) ...
    hairpin='auto',           # sharp U-turns: 'auto' (one fanned column when the outside is rounded, else split),
                              # 'fan' (always one column), 'split' (always two)
    short_inset=(0.15, 0.3),  # ... those stitches are shortened by these shares of the width, in turn
    pull_mm=0.0,         # widen columns by this many mm on each side (pull compensation)
    stretch=0.0,         # stretchy fabric: compensation is (1 - s/2 .. 1 + s/2) x pull_mm, the most for
    stretch_angle=0.0,   # ... stitches along the stretch direction (degrees; 0 = across the garment)
    min_width=1.0,       # columns narrower than this (mm, median) are widened to it (thin text, towel)
    max_widen=0.3,       # ... but by at most this much in all (mm): small text keeps its counters open
    pull_pct=0.0,        # widen columns by this % of their width (half on each side)
    push_mm=0.0,         # shorten free stroke ends by this much (pull along the column)
    contour_from=2.0,    # column width from which underlay is contour (edge runs) instead of centre walk
    german_from=4.0,     # ... and from which contour + low zigzag underlay is used
    split_len=7.0,       # satin stitches longer than this (mm) are split ...
    split_staggers=4,    # ... with the split point moving 1/4 from stitch to stitch
    mitre_max=60.0,     # corners turning up to this many degrees: one column, stitches turn round the corner
    reach=1.5,           # stroke ending against another runs on at most this many widths
    gap_min=0.3,         # uncovered gaps at least this wide (mm) get a small fill
)


def pull_for(dx, dy):
    """pull compensation for a stitch in direction (dx, dy): on a stretchy fabric (knit) the fabric gives
    most along its stretch direction, so stitches lying that way are pulled in most"""
    if not OPTS['stretch']: return OPTS['pull_mm']
    l_ = math.hypot(dx, dy) or 1
    a = math.radians(OPTS['stretch_angle'])
    c = abs(dx / l_ * math.cos(a) + dy / l_ * math.sin(a))      # 1 along the stretch, 0 across it
    return OPTS['pull_mm'] * (1 + OPTS['stretch'] * (c - 0.5))


def _mask(poly):
    minx, miny, maxx, maxy = poly.bounds
    ox, oy = minx - 0.2, miny - 0.2
    W = int((maxx - ox + 0.2) / RES) + 1; H = int((maxy - oy + 0.2) / RES) + 1
    m = np.zeros((H, W), bool)
    for ring, val in [(poly.exterior, True)] + [(r, False) for r in poly.interiors]:
        xs, ys = ring.xy
        rr, cc = skpoly((np.array(ys) - oy) / RES, (np.array(xs) - ox) / RES, m.shape)
        m[rr, cc] = val
    return m, ox, oy


def _graph(sk):
    G = nx.Graph()
    ys, xs = np.nonzero(sk)
    S = set(zip(ys.tolist(), xs.tolist()))
    for (y, x) in S:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dy or dx) and (y + dy, x + dx) in S:
                    # diagonal link only if no 4-connected detour exists (avoids pixel triangles)
                    if dy and dx and ((y + dy, x) in S or (y, x + dx) in S): continue
                    G.add_edge((y, x), (y + dy, x + dx), weight=math.hypot(dy, dx))
    return G


def branches(poly, width):
    """centre lines (mm) of the strokes, ends extended to the outline"""
    m, ox, oy = _mask(poly)
    G = _graph(skeletonize(m))
    if G.number_of_nodes() == 0:
        c = poly.centroid; return [([(c.x, c.y)], False, False)], None
    to_mm = lambda n: (ox + n[1] * RES, oy + n[0] * RES)
    # remove short spurs (corner artefacts) repeatedly
    for _ in range(3):
        key = [n for n in G if G.degree(n) != 2]
        segs = _split(G, key)
        removed = False
        for s in segs:
            L = sum(math.dist(a, b) for a, b in zip(s, s[1:])) * RES
            ends = [G.degree(s[0]), G.degree(s[-1])]
            if L < 1.8 * width and min(ends) == 1 and max(ends) > 2 and not (L > 0.9 * width and _continues(s, s[0] if ends[0] > 2 else s[-1], segs, width)):
                G.remove_nodes_from([n for n in s if G.degree(n) <= 2]); removed = True
        if not removed: break
    key = [n for n in G if G.degree(n) != 2]
    # junction clusters (a junction is often several neighbouring pixels)
    J = [n for n in G if G.degree(n) > 2]
    cl = {}
    cid = 0
    for n in J:
        if n in cl: continue
        stack = [n]; cl[n] = cid
        while stack:
            u = stack.pop()
            for v in J:
                if v not in cl and math.dist(u, v) * RES < 0.8 * width: cl[v] = cid; stack.append(v)
        cid += 1
    segs = []
    for s in _split(G, key):
        pts = [to_mm(n) for n in s]
        if len(pts) < 2: continue
        e0 = ('j', cl[s[0]]) if s[0] in cl else ('e', None) if G.degree(s[0]) == 1 else ('x', None)
        e1 = ('j', cl[s[-1]]) if s[-1] in cl else ('e', None) if G.degree(s[-1]) == 1 else ('x', None)
        if e0[0] == 'j' and e1[0] == 'j' and e0[1] == e1[1] and len(pts) * RES < 2 * width: continue   # inside one junction (a longer one is a loop: bowl of a, b, d)
        ls = LineString(pts).simplify(0.04)
        if ls.length < 0.05: continue
        # split at sharp corners (E, L-type corners): direction change > 50 deg within ~1 width
        parts = _split_corners(ls, width, poly=poly)
        for k_, part in enumerate(parts):
            a_ = e0 if k_ == 0 else ('j', cid + k_ - 1)
            b_ = e1 if k_ == len(parts) - 1 else ('j', cid + k_)
            segs.append([part, a_, b_])
        cid += len(parts) - 1
    jc = 0.4 * width; bend = 0.9 * width
    def trim_j(ls, at_start, d):
        if ls.length <= d + 0.3: return ls
        return substring(ls, d, ls.length) if at_start else substring(ls, 0, ls.length - d)
    def outdir(ls, at_start):
        L = ls.length; p0 = ls.interpolate(0 if at_start else L); p1 = ls.interpolate(min(L, 1.5 * width) if at_start else max(0, L - 1.5 * width))
        dx, dy = p1.x - p0.x, p1.y - p0.y; d = math.hypot(dx, dy) or 1
        return dx / d, dy / d
    # hairpin: two strokes leaving a junction side by side (narrow V) with a short free stem out of the
    # junction the other way (the closed tip): one column round the bend, the stitches fan at the corner.
    # The stem goes; both arms run on straight to where their centre lines meet. 'split' keeps them apart.
    hp = OPTS.get('hairpin', 'auto')
    for c in range(cid if hp != 'split' else 0):
        ends = [(i, k) for i, sg in enumerate(segs) for k in (1, 2) if sg[k] == ('j', c)]
        if len(ends) not in (2, 3) or len({i for i, _ in ends}) != len(ends): continue
        stems = [(i, k) for i, k in ends if segs[i][2 if k == 1 else 1][0] == 'e' and segs[i][0].length < 5 * width]
        if len(ends) == 3 and len(stems) != 1: continue
        si = stems[0][0] if len(ends) == 3 else None                                # (a short stem may be gone already)
        (ai, ak), (bi, bk) = [e for e in ends if e[0] != si]
        da = outdir(segs[ai][0], ak == 1); db = outdir(segs[bi][0], bk == 1)
        if da[0] * db[0] + da[1] * db[1] < math.cos(math.radians(70)): continue     # not a narrow V
        if si is not None:
            sk = stems[0][1]; ds_ = outdir(segs[si][0], sk == 1)
            mx, my = da[0] + db[0], da[1] + db[1]; mn = math.hypot(mx, my) or 1
            if (mx * ds_[0] + my * ds_[1]) / mn > -0.8: continue                    # stem not out of the V
            stip = segs[si][0].coords[-1 if sk == 1 else 0]
        else:
            stip = segs[ai][0].coords[0 if ak == 1 else -1]
        A = trim_j(segs[ai][0], ak == 1, bend); B = trim_j(segs[bi][0], bk == 1, bend)
        ca = list(A.coords); cb = list(B.coords)
        if ak == 1: ca = ca[::-1]
        if bk == 2: cb = cb[::-1]
        pa, pb = ca[-1], cb[0]
        def far_dir(cs):                    # direction of the straight part, past the bend into the junction
            l_ = LineString(cs); q0 = l_.interpolate(min(l_.length, 2 * width)); q1 = l_.interpolate(min(l_.length, 5 * width))
            dx, dy = q0.x - q1.x, q0.y - q1.y; n_ = math.hypot(dx, dy) or 1
            return dx / n_, dy / n_
        ua = far_dir(ca[::-1]); ub = far_dir(cb); ub = (-ub[0], -ub[1])             # along A into the corner, along B out of it
        den = ua[0] * ub[1] - ua[1] * ub[0]
        if abs(den) < 1e-6: continue
        t = ((pb[0] - pa[0]) * ub[1] - (pb[1] - pa[1]) * ub[0]) / den
        P = (pa[0] + ua[0] * t, pa[1] + ua[1] * t)
        if t < 0 or math.dist(P, stip) > 3 * width: continue
        if hp == 'auto' and not _smooth_turn(poly, P, width): continue             # sharp tip: split (the default)
        ea = segs[ai][2] if ak == 1 else segs[ai][1]; eb = segs[bi][2] if bk == 1 else segs[bi][1]
        new_ = [LineString(ca + [P] + cb), ea, eb]
        for k_ in sorted([x for x in (ai, bi, si) if x is not None], reverse=True): segs.pop(k_)
        segs.append(new_)
    # through-strokes: at each junction join the two most opposite branches into one column
    for c in range(cid):
        while True:
            ends = [(i, k) for i, sg in enumerate(segs) for k in (1, 2) if sg[k] == ('j', c)]
            best = None
            for x in range(len(ends)):
                for y in range(x + 1, len(ends)):
                    (i, ki), (j, kj) = ends[x], ends[y]
                    if i == j: continue
                    di = outdir(segs[i][0], ki == 1); dj = outdir(segs[j][0], kj == 1)
                    dot = di[0] * dj[0] + di[1] * dj[1]
                    # three-way junction of long strokes (the U of a tuning fork curves into it): join more readily
                    long_ = min(segs[i][0].length, segs[j][0].length) >= 8 * width
                    lim = -0.65 if len(ends) == 3 and long_ else -0.85
                    if dot < lim and (best is None or dot < best[0]): best = (dot, i, ki, j, kj)
            if best is None: break
            _, i, ki, j, kj = best
            A = trim_j(segs[i][0], ki == 1, bend); B = trim_j(segs[j][0], kj == 1, bend)
            ca = list(A.coords); cb = list(B.coords)
            if ki == 1: ca = ca[::-1]          # A must end at the junction
            if kj == 2: cb = cb[::-1]          # B must start at the junction
            ea = segs[i][2] if ki == 1 else segs[i][1]; eb = segs[j][2] if kj == 1 else segs[j][1]
            new = [LineString(ca + cb), ea, eb]
            for k_ in sorted([i, j], reverse=True): segs.pop(k_)
            segs.append(new)
    for c in range(cid):
        ends = [(i, k) for i, sg in enumerate(segs) for k in (1, 2) if sg[k] == ('j', c)]
        if len(ends) == 2 and ends[0][0] != ends[1][0]:
            (i, ki), (j, kj) = ends
            thr = i if segs[i][0].length >= segs[j][0].length else j
            k_ = ki if thr == i else kj
            segs[thr][k_] = ('t', c)            # through to the outer edge
    out = []; jends = []
    for ls, e0, e1 in segs:
        cut = 1.0 * width
        if e0[0] == 'e' and ls.length > 2 * cut + 0.2: ls = substring(ls, cut, ls.length)
        if e1[0] == 'e' and ls.length > cut + 0.2: ls = substring(ls, 0, ls.length - cut)
        # stroke meeting another stroke: drop the bent skeleton part, run straight up to the other stroke
        if e0[0] in 'jt': ls = trim_j(ls, True, bend)
        if e1[0] in 'jt': ls = trim_j(ls, False, bend)
        c = list(ls.coords)
        if len(c) < 2: continue
        for end, e in ((0, e0), (-1, e1)):
            # a stroke going through to the outer edge ends at it like a free end: a column end is not pulled
            # in (its stitches run along the edge) but pushed out, while the side edges of the stroke it
            # crosses are pulled back to the outline. Past it by the compensation the E stem stood out on top.
            if e[0] == 't': c[end] = _extend(_back(c, end, width), c[end], poly, width,
                                             inset=0.1 - min(OPTS['max_widen'] / 2, max(0.0, (OPTS['min_width'] - width) / 2)))
            elif e[0] == 'j': c[end] = _straight(_back(c, end, width), c[end], bend - jc, poly)
        if width >= 2.5:                 # wide column: the skeleton tail bends to a corner of the end;
            for end, e in ((0, e0), (-1, e1)):    # drop the bent last piece, the end runs straight on (below)
                if e[0] != 'e': continue
                pts_ = c if end == -1 else c[::-1]
                ang = lambda a_, b_: math.atan2(b_[1] - a_[1], b_[0] - a_[0])
                while len(pts_) >= 3:
                    tl = math.dist(pts_[-2], pts_[-1])
                    da = abs((ang(pts_[-2], pts_[-1]) - ang(pts_[-3], pts_[-2]) + math.pi) % (2 * math.pi) - math.pi)
                    if tl < 1.5 * width and da > math.radians(15): pts_ = pts_[:-1]
                    else: break
                c = pts_ if end == -1 else pts_[::-1]
        if e0[0] == 'e': c[0] = _extend(_back(c, 0, width), c[0], poly, width)
        if e1[0] == 'e': c[-1] = _extend(_back(c, -1, width), c[-1], poly, width)
        out.append((c, e0[0] == 'e', e1[0] == 'e', e0[0] in 'et', e1[0] in 'et'))   # caps, closed ends
        jends += [(len(out) - 1, end) for end, e in ((0, e0), (-1, e1)) if e[0] == 'j']
    # skeleton pixel graph in mm for travel
    H = nx.Graph()
    for a, b, d in G.edges(data=True): H.add_edge(to_mm(a), to_mm(b), weight=d['weight'] * RES)
    H.graph['jends'] = jends
    return out, H


def _continues(s, J, segs, width):
    """a short end branch that carries on straight from another branch at its junction J is the real end
    of a stroke (stem of d or b just below the bowl), not a corner artefact: keep it"""
    def d(path):                       # direction away from J, over ~1.5 widths (pixels)
        if path[0] != J: path = path[::-1]
        k = min(len(path) - 1, max(1, int(1.5 * width / RES)))
        dy, dx = path[k][0] - path[0][0], path[k][1] - path[0][1]; L = math.hypot(dx, dy) or 1
        return dx / L, dy / L
    a = d(list(s))
    for t in segs:
        if t is s or J not in (t[0], t[-1]) or len(t) < 2 or t[0] == t[-1]: continue
        b = d(list(t))
        if a[0] * b[0] + a[1] * b[1] < -0.97: return True     # within ~14°: corner spurs (M, A tips) bend away more
    return False


def _reach(out, jends, poly, width):
    """a stroke that ends against another one runs on until both of its sides are inside the other
    stroke, so no wedge is left between its square end and a slanted neighbour (middle of M, V, K)"""
    from shapely.ops import unary_union
    for k, end in jends:
        c = out[k][0]; b = c[end]; a = _back(c, end, width)
        d = math.dist(a, b) or 1; u = ((b[0] - a[0]) / d, (b[1] - a[1]) / d); n = (-u[1], u[0])
        others = [LineString(o[0]) for i, o in enumerate(out) if i != k and len(o[0]) > 1 and LineString(o[0]).distance(Point(b)) < width]
        if not others: continue
        # stop as soon as the side lagging behind is 0.15 mm inside the other stroke (just enough, little overlap)
        O = unary_union(others); h = 0.5 * width; lim = 0.5 * width - 0.15; t = 0.0
        while t < OPTS['reach'] * width:
            q = (b[0] + u[0] * t, b[1] + u[1] * t)
            if all(O.distance(Point(q[0] + sg * n[0] * h, q[1] + sg * n[1] * h)) <= lim for sg in (1, -1)): break
            t += 0.05
        else: q = (b[0] + u[0] * t, b[1] + u[1] * t)   # not reached: go as far as allowed
        inside = poly.buffer(0.02)
        while t > 0 and not inside.contains(Point(q)):        # past the outline (top of A): as far as it stays inside
            t -= 0.05; q = (b[0] + u[0] * t, b[1] + u[1] * t)
        if t > 0: c[end] = q


def _split(G, key):
    """split the skeleton graph into paths between key nodes (and closed loops)"""
    seen = set(); segs = []
    keys = set(key)
    for k in keys:
        for nb in G.neighbors(k):
            if (k, nb) in seen: continue
            path = [k, nb]; seen.add((k, nb)); seen.add((nb, k))
            while path[-1] not in keys:
                nxt = [n for n in G.neighbors(path[-1]) if n != path[-2]]
                if not nxt: break
                seen.add((path[-1], nxt[0])); seen.add((nxt[0], path[-1])); path.append(nxt[0])
                if path[-1] == path[0]: break
            segs.append(path)
    # pure loops (e.g. O without key nodes)
    rest = [n for n in G if all((n, nb) not in seen for nb in G.neighbors(n))]
    while rest:
        n0 = rest[0]; path = [n0]; prev = None
        while True:
            nxt = [n for n in G.neighbors(path[-1]) if n != prev and (path[-1], n) not in seen]
            if not nxt: break
            seen.add((path[-1], nxt[0])); seen.add((nxt[0], path[-1])); prev = path[-1]; path.append(nxt[0])
            if nxt[0] == n0: break
        segs.append(path)
        rest = [n for n in G if all((n, nb) not in seen for nb in G.neighbors(n))]
    return segs


def _straight(a, b, L, poly):
    d = math.dist(a, b) or 1
    q = (b[0] + (b[0] - a[0]) / d * L, b[1] + (b[1] - a[1]) / d * L)
    return q if poly.buffer(0.02).contains(Point(q)) else b


def _smooth_turn(poly, p, width):
    """a hairpin bend: the outline on the outside of the turn is a smooth curve (no vertex turning more
    than 40 deg). The inside may come to a point - the stitches pivot there, fanning round the bend."""
    r = 1.2 * width + 0.3
    near = poly.buffer(0).boundary.intersection(Point(p).buffer(r))
    for g in getattr(near, 'geoms', [near]):
        if g.is_empty or g.geom_type != 'LineString': continue
        c = list(g.simplify(0.03).coords)
        if len(c) < 5: continue                                   # a short piece: the inside point
        turns = []
        for a, b, d in zip(c, c[1:], c[2:]):
            v1 = (b[0] - a[0], b[1] - a[1]); v2 = (d[0] - b[0], d[1] - b[1])
            l1, l2 = math.hypot(*v1), math.hypot(*v2)
            if l1 < 1e-6 or l2 < 1e-6: continue
            turns.append(math.degrees(math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2))))))
        if turns and max(turns) <= 40 and sum(turns) >= 90: return True   # a real bend, rounded on the outside
    return False


def _split_corners(ls, width, mitre=True, poly=None):
    """split a centre line where it turns a corner: chord directions 1.2 widths before and after
    a point differ by more than 25 deg (local maximum). With the outline given, a turn whose outline
    is a smooth curve (a hairpin bend, not a corner) stays one column: the stitches fan round it."""
    L = ls.length; h = 1.2 * width
    if L < 2 * h + 0.2: return [ls]
    ds = np.arange(h, L - h, 0.05)
    def ang(d):
        p0, p1, p2 = (ls.interpolate(v).coords[0] for v in (d - h, d, d + h))
        v1 = (p1[0] - p0[0], p1[1] - p0[1]); v2 = (p2[0] - p1[0], p2[1] - p1[1])
        c = (v1[0] * v2[0] + v1[1] * v2[1]) / ((math.hypot(*v1) * math.hypot(*v2)) or 1)
        return math.degrees(math.acos(max(-1, min(1, c))))
    A = [ang(d) for d in ds]
    cuts = []
    for i in range(len(A)):
        if A[i] > max(25, OPTS['mitre_max'] if mitre else 25) and A[i] == max(A[max(0, i - 20):i + 21]):
            if not cuts or ds[i] - cuts[-1] > 2 * h: cuts.append(float(ds[i]))
    # curves (S, U, D, J) turn evenly: only keep sharp turns (angle concentrated, not spread out)
    keep = []
    for c in cuts:
        i = int(round((c - h) / 0.05))
        lo = ang(max(h, c - h)) if c - h >= h else 0; hi = ang(min(L - h, c + h)) if c + h <= L - h else 0
        if A[i] > 1.8 * max(lo, hi) and 1.4 * width < c < L - 1.4 * width:
            hp = OPTS.get('hairpin', 'auto')
            if mitre and poly is not None and hp == 'auto' and _smooth_turn(poly, ls.interpolate(c).coords[0], width): continue
            keep.append(c)
    if not keep: return [ls]
    if not mitre: return keep
    out = []; prev = 0.0
    for d_ in keep + [L]:
        if d_ - prev > 0.05: out.append(substring(ls, prev, d_))
        prev = d_
    return out


def _back(c, end, width):
    """a point about one stroke width back from the end, for a straight end direction"""
    ls = LineString(c if end == -1 else c[::-1]); L = ls.length
    return ls.interpolate(max(0, L - width)).coords[0]


def _extend(a, b, poly, width, inset=0.1):
    """extend from b in direction a->b while a normal across the stroke still meets the shape
    (covers square, oblique and slightly curved stroke ends)"""
    d = math.dist(a, b) or 1
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    nx_, ny_ = -uy, ux
    h = 0.6 * width; L = 0.0; step = 0.05
    while L < 3 * width:
        q = (b[0] + ux * (L + step), b[1] + uy * (L + step))
        seg = LineString([(q[0] - nx_ * h, q[1] - ny_ * h), (q[0] + nx_ * h, q[1] + ny_ * h)])
        if seg.intersection(poly).length < 0.12: break
        L += step
    L = max(0, L - inset)
    return (b[0] + ux * L, b[1] + uy * L)


def _edges(poly, p, n, reach=2.5):
    """points where the normal through p meets the outline on both sides"""
    a = (p[0] - n[0] * reach, p[1] - n[1] * reach); b = (p[0] + n[0] * reach, p[1] + n[1] * reach)
    inter = LineString([a, b]).intersection(poly)
    parts = [g for g in getattr(inter, 'geoms', [inter]) if g.geom_type == 'LineString' and not g.is_empty]
    if not parts: return None
    seg = min(parts, key=lambda g: g.distance(Point(p)))
    c = list(seg.coords)
    return c[0], c[-1]


def column(poly, line, spacing=0.4, inset=0.0, width=None, caps=(False, False)):
    """satin zigzag along a centre line (needle points)"""
    return zig(column_pairs(poly, line, spacing, width, caps), spacing)


def column_pairs(poly, line, spacing=0.4, width=None, caps=(False, False)):
    """(left, right) edge points along a centre line; spacing = distance between stitches on the same side.
    The next stitch is placed where the side that moves most (the outside of a curve, the long side of
    a slanted end) has moved spacing/2 away from the previous stitch, measured square to that stitch;
    so curves are as dense on the outside as straight parts, and the inside gets short stitches (zig).
    Side distances are clamped to 1.12x the column's median, so junctions don't make spikes."""
    ls = LineString(line)
    L = ls.length
    n = max(2, int(math.ceil(L / (spacing / 16))) + 1)         # dense samples, picked from below
    corners = _corners(ls, width or 1)
    ends = [(dd, _end_edge(poly, ls.interpolate(dd).coords[0], width or 1)) for dd, cp in ((0.0, caps[0]), (L, caps[1])) if cp]
    ends = [(dd, e_) for dd, e_ in ends if e_ is not None]
    samples = []; allow = []
    for i in range(n):
        d = L * i / (n - 1)
        p = ls.interpolate(d).coords[0]
        # direction from the line over +-half a width: a kink in the centre line (where a branch joins)
        # turns the stitches gradually instead of all at once, which would open a wedge on the outside
        hw = max(0.15, 0.5 * (width or 0))
        p0 = ls.interpolate(max(0, d - hw)).coords[0]; p1 = ls.interpolate(min(L, d + hw)).coords[0]
        tx, ty = p1[0] - p0[0], p1[1] - p0[1]; tl = math.hypot(tx, ty) or 1
        nrm, f = _turn(-ty / tl, tx / tl, d, corners, width, ends)
        allow.append(f)
        e = _edges(poly, p, nrm, max(2.5, 1.5 * (width or 1)))
        if e is not None and LineString(e).distance(Point(p)) > 0.7 * (width or 1): e = None
        if e is None: samples.append((p, nrm, None, None)); continue
        a, b = e
        da = (a[0] - p[0]) * nrm[0] + (a[1] - p[1]) * nrm[1]
        db = (b[0] - p[0]) * nrm[0] + (b[1] - p[1]) * nrm[1]
        samples.append((p, nrm, min(da, db), max(da, db)))   # negative side, positive side
    neg = [-s[2] for s in samples if s[2] is not None and s[2] < 0]
    pos = [s[3] for s in samples if s[3] is not None and s[3] > 0]
    if not neg or not pos: return []
    mn, mp = 1.12 * float(np.median(neg)), 1.12 * float(np.median(pos))
    if width: mn, mp = min(mn, 0.62 * width), min(mp, 0.62 * width)
    # a column whose width changes along it (taper, wedge): clamp to the local median instead, over
    # +-1.5 widths, else the wide end is cut down to the column's middle width and left to gap fill
    loc = None
    ok_ = [s_ for s_ in samples if s_[2] is not None and s_[2] < 0 < s_[3]]
    if width and len(ok_) > 8:
        wl = np.array([s_[3] - s_[2] for s_ in ok_])
        ix = np.arange(len(wl))
        # only a real taper (width grows steadily along the column), not the bulges at junctions of K or M
        if np.percentile(wl, 90) > 1.6 * np.percentile(wl, 10) and abs(np.corrcoef(ix, wl)[0, 1]) > 0.85:
            idx = [i for i, s_ in enumerate(samples) if s_[2] is not None and s_[2] < 0 < s_[3]]
            step = L / (n - 1); win = max(1, int(1.5 * width / step))
            ng = np.full(n, np.nan); ps = np.full(n, np.nan)
            for i in idx: ng[i] = -samples[i][2]; ps[i] = samples[i][3]
            loc = []
            for i in range(n):
                a_, b_ = ng[max(0, i - win): i + win + 1], ps[max(0, i - win): i + win + 1]
                a_, b_ = a_[~np.isnan(a_)], b_[~np.isnan(b_)]
                loc.append((1.12 * float(np.median(a_)) if len(a_) else mn, 1.12 * float(np.median(b_)) if len(b_) else mp))
    ws_ = [s_[3] - s_[2] for s_ in samples if s_[2] is not None]
    extra = min(OPTS['max_widen'] / 2, max(0.0, (OPTS['min_width'] - float(np.median(ws_))) / 2)) if ws_ else 0.0
    dense = []; last = (-np.median(neg), np.median(pos))
    for i_, ((p, nrm, a, b), f) in enumerate(zip(samples, allow)):
        if a is None: a, b = last          # past the outline (through-going end): keep the last full width
        cn, cp_ = loc[i_] if loc else (mn, mp)
        a = max(a, -cn * f); b = min(b, cp_ * f)
        if b - a < 0.2: m_ = (a + b) / 2; a, b = m_ - 0.1, m_ + 0.1
        if b - a >= 0.8 * (mn + mp) / 1.12: last = (a, b)   # only full-width stitches are carried on
        if OPTS['pull_pct']: g = (b - a) * OPTS['pull_pct'] / 200; a, b = a - g, b + g
        pm = pull_for(*nrm)
        a, b = a - pm - extra, b + pm + extra
        dense.append(((p[0] + nrm[0] * a, p[1] + nrm[1] * a), (p[0] + nrm[0] * b, p[1] + nrm[1] * b)))
    # no stitch reaches past the outline by more than the compensation: where the centre line runs on
    # past the shape (sharp tips of M, N, W, A; ends that carry the last full width), a stitch is cut
    # back to the outline + compensation instead of sticking out
    allowed = poly.buffer(OPTS['pull_mm'] * (1 + OPTS['stretch'] / 2) + extra + 0.1, join_style=1)   # round: a mitre would spike out at sharp tips
    for k, (l_, r_) in enumerate(dense):
        if allowed.contains(Point(l_)) and allowed.contains(Point(r_)): continue
        seg = LineString([l_, r_]); cut = seg.intersection(allowed)
        parts_ = [g for g in getattr(cut, 'geoms', [cut]) if g.geom_type == 'LineString' and not g.is_empty]
        if not parts_: continue
        mid = samples[k][0]
        g = min(parts_, key=lambda g_: g_.distance(Point(mid)))
        c0, c1 = g.coords[0], g.coords[-1]
        if math.dist(c0, l_) > math.dist(c1, l_): c0, c1 = c1, c0
        dense[k] = (c0, c1)
    # free ends: the column runs on to the tip and every stitch is cut by the outline, so a square
    # or slanted end is filled with stitches getting shorter, parallel to the others (no fan)
    ok = [s_[2] is not None and s_[3] - s_[2] >= 0.25 for s_ in samples]
    i0, i1 = 0, len(dense)
    if caps[0]:
        while i0 < i1 and not ok[i0]: i0 += 1
    if caps[1]:
        while i1 > i0 and not ok[i1 - 1]: i1 -= 1
    dense = dense[i0:i1]
    if not dense: return []
    # pick stitches: next one when the side moving most is spacing/2 from the previous stitch
    step = spacing / 2
    # stitches that must be there: the one along the bisector of each kept corner (reaches the outer corner)
    must = set()
    if corners:
        ds_ = [L * i / (n - 1) for i in range(n)][i0:i1]
        for dc, _, _ in corners:
            must.add(min(range(len(ds_)), key=lambda k: abs(ds_[k] - dc)))
    pairs = [dense[0]]
    for qi, q in enumerate(dense[1:], start=1):
        if qi in must: pairs.append(q); continue
        l0, r0 = pairs[-1]
        vx, vy = r0[0] - l0[0], r0[1] - l0[1]; vl = math.hypot(vx, vy)
        if vl < 0.01: dist = max(math.dist(q[0], l0), math.dist(q[1], r0))
        else:
            nx_, ny_ = -vy / vl, vx / vl
            dist = max(abs((q[0][0] - l0[0]) * nx_ + (q[0][1] - l0[1]) * ny_), abs((q[1][0] - r0[0]) * nx_ + (q[1][1] - r0[1]) * ny_))
        if dist >= step - spacing / 32: pairs.append(q)     # within half a dense step
    if dense[-1] is not pairs[-1]:
        l0, r0 = pairs[-1]
        if max(math.dist(dense[-1][0], l0), math.dist(dense[-1][1], r0)) > 0.1: pairs.append(dense[-1])
    if OPTS['push_mm'] > 0:    # shorten free ends
        k = int(OPTS['push_mm'] / step)
        if caps[1] and len(pairs) > 2 * k + 4: pairs = pairs[:len(pairs) - k]
        if caps[0] and len(pairs) > 2 * k + 4: pairs = pairs[k:]
    return pairs


def _corners(ls, width):
    """corners kept inside one column (turn between 25 deg and mitre_max): distance along the line,
    direction before and after (unit vectors)"""
    if OPTS['mitre_max'] <= 25: return []
    saved = OPTS['mitre_max']; OPTS['mitre_max'] = 25
    try: ds = _split_corners(ls, width, mitre=False)
    finally: OPTS['mitre_max'] = saved
    if isinstance(ds, list) and ds and not isinstance(ds[0], (int, float)): return []
    out = []; h = 1.2 * width; L = ls.length
    for d in ds:
        p0, p1, p2 = (ls.interpolate(v).coords[0] for v in (max(0, d - h), d, min(L, d + h)))
        u1 = (p1[0] - p0[0], p1[1] - p0[1]); u2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*u1) or 1, math.hypot(*u2) or 1; u1 = (u1[0] / l1, u1[1] / l1); u2 = (u2[0] / l2, u2[1] / l2)
        turn = math.degrees(math.acos(max(-1, min(1, u1[0] * u2[0] + u1[1] * u2[1]))))
        if turn <= OPTS['mitre_max']: out.append((d, u1, u2))
    return out


def _end_edge(poly, tip, width):
    """direction of the outline edge closing a free stroke end (the longest straight piece of
    outline near the tip), or None"""
    ring = list(poly.exterior.coords); best = None
    for a, b in zip(ring, ring[1:]):
        seg = LineString([a, b])
        if seg.distance(Point(tip)) < 0.35 * width and seg.length > 0.3 * width:
            if best is None or seg.length > best[0]: best = (seg.length, a, b)
    if best is None: return None
    _, a, b = best; l_ = math.dist(a, b)
    return ((b[0] - a[0]) / l_, (b[1] - a[1]) / l_)


def _turn(nx_, ny_, d, corners, width, ends=()):
    """stitch direction near a free end: turns over about one width to lie along the end edge
    (square ends, slanted ends like K and A feet), so the last stitches close the end exactly"""
    R_ = 0.9 * (width or 1)
    for de, ev in ends:
        if abs(d - de) < R_:
            t = 1 - abs(d - de) / R_
            ca = ev[0] * nx_ + ev[1] * ny_
            if ca < 0: ev = (-ev[0], -ev[1]); ca = -ca
            if ca < 0.5: break                       # end edge more than 60 deg off: leave square
            a1 = math.atan2(ny_, nx_); a2 = math.atan2(ev[1], ev[0])
            da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            a = a1 + da * t
            n = (math.cos(a), math.sin(a))
            return n, 1 / max(abs(n[0] * nx_ + n[1] * ny_), 0.5)
    return _turn_corner(nx_, ny_, d, corners, width)


def _turn_corner(nx_, ny_, d, corners, width):
    """stitch direction: square to the column, except around a kept corner, where it turns from
    square-before through the corner bisector to square-after over about one column width.
    Returns (direction, how much longer the stitch may be than a square one)."""
    R_ = 0.7 * (width or 1)
    for dc, u1, u2 in corners:
        if abs(d - dc) < R_:
            t = (d - (dc - R_)) / (2 * R_)
            a1 = math.atan2(u1[0], -u1[1]); a2 = math.atan2(u2[0], -u2[1])   # normals (-uy, ux) as angles
            da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            a = a1 + da * t
            n = (math.cos(a), math.sin(a))
            if n[0] * nx_ + n[1] * ny_ < 0: n = (-n[0], -n[1])
            c = abs(n[0] * nx_ + n[1] * ny_)
            return n, 1 / max(c, 0.5)
    return (nx_, ny_), 1.0


def zig(pairs, spacing=0.4, close=(True, True)):
    """zigzag through the pairs. Where needle points on one side crowd (inside of a curve or a corner),
    a point closer than short_dist to the last full-length point on that side is moved inwards along
    its stitch by the next share from short_inset (cycling), so the thread spreads instead of piling up."""
    pts = [p[k % 2] for k, p in enumerate(pairs)]
    seq = OPTS['short_inset'] if isinstance(OPTS['short_inset'], (list, tuple)) else (OPTS['short_inset'],)
    full = [None, None]; idx = [0, 0]
    for k in range(len(pts)):
        sd = k % 2
        if full[sd] is None or math.dist(pts[k], full[sd]) >= OPTS['short_dist']:
            full[sd] = pts[k]; idx[sd] = 0; continue
        a, b = pairs[k][sd], pairs[k][1 - sd]
        f = seq[idx[sd] % len(seq)]; idx[sd] += 1
        pts[k] = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
    # close the ends that are on the outline (free ends, strokes going through to the outer edge): the
    # first and last pair are stitched fully, else a corner stays open. Ends inside another stroke stay open.
    if len(pairs) > 1:
        if close[0]: pts = [pairs[0][1]] + pts
        last = pairs[-1][(len(pairs) - 1) % 2 ^ 1]
        if close[1] and math.dist(last, pts[-1]) > 0.05: pts.append(last)
    return _split_long(pts)


def _split_long(pts):
    """satin stitches longer than split_len (wide columns) get extra needle points; their place
    shifts by 1/split_staggers from stitch to stitch, so no ridge forms along the column"""
    Lm = OPTS['split_len']
    if not Lm: return pts
    out = pts[:1]
    for k in range(1, len(pts)):
        a, b = pts[k - 1], pts[k]; d = math.dist(a, b)
        if d > Lm:
            ph = (k % OPTS['split_staggers']) / OPTS['split_staggers']
            ts = [(j + ph) * Lm / d for j in range(int(d / Lm) + 1)]
            ts = [t for t in ts if 0.25 * Lm / d < t < 1 - 0.25 * Lm / d]
            out += [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in ts]
        out.append(b)
    return out


def rails(pairs, width):
    """edge runs a little inside the column, for contour underlay"""
    ins = max(0.2, 0.15 * width) + OPTS['pull_mm']     # from the drawn edge, not the compensated one
    def inset(a, b):
        d = math.dist(a, b) or 1; t = min(ins, d / 2.5) / d
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    left = [inset(l, r) for l, r in pairs]; right = [inset(r, l) for l, r in pairs]
    return left, right


def underlay_kind(width):
    if OPTS.get('underlay'): return OPTS['underlay']
    if width >= OPTS['german_from']: return 'german'
    if width >= OPTS['contour_from']: return 'contour'
    return 'centre'


def _corner_walk(ring, p, away_from, maxlen):
    """from p walk along ring, in the direction leading away from 'away_from', up to the next corner"""
    L = ring.length; s0 = ring.project(Point(p))
    best = None
    for sgn in (1, -1):
        q = ring.interpolate((s0 + sgn * 0.1) % L)
        dd = math.dist((q.x, q.y), away_from)
        if best is None or dd > best[0]: best = (dd, sgn)
    sgn = best[1]; s = 0.0; step = 0.1
    pts = [p]; prev_dir = None
    while s < maxlen:
        a = ring.interpolate((s0 + sgn * s) % L); b = ring.interpolate((s0 + sgn * (s + step)) % L)
        d = (b.x - a.x, b.y - a.y); n = math.hypot(*d) or 1; d = (d[0] / n, d[1] / n)
        # a corner = sudden turn between two neighbouring 0.1 mm pieces (curves turn slowly)
        if prev_dir is not None and d[0] * prev_dir[0] + d[1] * prev_dir[1] < math.cos(math.radians(30)): break
        prev_dir = d; s += step; pts.append((b.x, b.y))
    return pts


def _cap(poly, pairs, spacing, width):
    full = float(np.median([math.dist(a, b) for a, b in pairs]))
    while len(pairs) > 4 and math.dist(*pairs[-1]) < 0.85 * full: pairs.pop()   # drop stitches already cut by the end
    l, r = pairs[-1]
    ref = ((pairs[-3][0][0] + pairs[-3][1][0]) / 2, (pairs[-3][0][1] + pairs[-3][1][1]) / 2) if len(pairs) > 3 else l
    ring = poly.exterior
    wl = _corner_walk(ring, l, ref, 1.5 * width); wr = _corner_walk(ring, r, ref, 1.5 * width)
    ll = LineString(wl) if len(wl) > 1 else None; lr = LineString(wr) if len(wr) > 1 else None
    Lm = max(ll.length if ll else 0, lr.length if lr else 0)
    n = int(Lm / (spacing / 2))
    for k in range(1, n + 1):
        f = k / n
        pl = ll.interpolate(f, normalized=True).coords[0] if ll else l
        pr = lr.interpolate(f, normalized=True).coords[0] if lr else r
        pairs.append((pl, pr))
    return pairs


def centre_run(line, step=1.5):
    ls = LineString(line); L = ls.length; n = max(1, math.ceil(L / step))
    return [ls.interpolate(L * i / n).coords[0] for i in range(n + 1)]


def coverage(cols):
    from shapely.ops import unary_union
    quads = []
    for pts in cols:
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            q = Polygon([a, b, c])
            if q.area > 1e-4: quads.append(q)
    return unary_union(quads).buffer(0.15) if quads else Polygon()


def _plan(poly, br, caps, G, start, spacing, width, closes=None):
    """order + direction of the columns of one letter with as few cuts as possible.
    Rules: travel runs along the letter's centre line and never over satin already sewn
    (else: cut + jump); a column's satin always comes after its underlay."""
    import itertools
    cols = [b for b in br if len(b) > 1]
    n = len(cols)
    nodes = list(G.nodes)
    near_cache = {}
    def near(p):
        k = (round(p[0], 3), round(p[1], 3))
        if k not in near_cache: near_cache[k] = min(nodes, key=lambda q: math.dist(p, q))
        return near_cache[k]
    # by the drawn width: the pairs include the pull compensation (a 1.7 mm stroke would count as 2.4 mm)
    kinds = [underlay_kind(float(np.median([math.dist(l, r) for l, r in column_pairs(poly, c, spacing, width)] or [width])) - 2 * OPTS['pull_mm']) for c in cols]
    sat_cov = []
    for c in cols:
        sat_cov.append(LineString(c).buffer(0.62 * width, cap_style=2))
    path_cache = {}
    def travel(a, b):
        k = (a, b)
        if k in path_cache: return path_cache[k]
        if math.dist(a, b) <= 0.4: res = None
        else:
            try:
                sp = nx.shortest_path(G, near(a), near(b), weight='weight')
                res = LineString(sp).simplify(0.05) if len(sp) > 1 else None
            except nx.NetworkXNoPath:
                res = 'none'
        path_cache[k] = res; return res
    def covers(path, i):
        if path is None or path == 'none': return False
        c = LineString(cols[i])
        return c.difference(path.buffer(0.3)).length < 0.15 * c.length
    TRIM = 8.0
    best = [None]
    def rec(pos, done, under, cost, steps):
        if best[0] is not None and cost >= best[0][0]: return
        if len(done) == n:
            best[0] = (cost, steps); return
        cands = []
        for i in range(n):
            if i in done: continue
            for rev in (False, True):
                c = cols[i][::-1] if rev else cols[i]
                e, e2 = c[0], c[-1]
                if pos is None: path = None; trim = False; plen = 0
                else:
                    path = travel(pos, e)
                    if path == 'none': trim = True; path = None; plen = 0
                    else:
                        plen = path.length if path is not None else math.dist(pos, e)
                        crosses = path is not None and any(path.intersection(sat_cov[j]).length > 0.3 for j in done)
                        trim = crosses
                        if trim: path = None
                new_under = set(under)
                if path is not None:
                    for j in range(n):
                        if j not in done and covers(path, j): new_under.add(j)
                if i in new_under:
                    # already underlaid on the way: satin straight on to the far end
                    end = e2; mode = 'fwd'
                elif kinds[i] == 'contour':
                    end = e2; mode = 'contour'       # edge run out and back, satin out
                else:
                    end = e; mode = 'back'           # (centre walk | contour + zigzag) out, satin back
                cst = cost + (TRIM if trim else 0) + (0 if trim else plen) * 0.2
                cands.append((cst, i, rev, path, trim, mode, end, new_under))
        cands.sort(key=lambda x: x[0])
        for cst, i, rev, path, trim, mode, end, nu in cands:
            rec(end, done | {i}, nu, cst, steps + [(i, rev, path, trim, mode)])
    rec(start, frozenset(), set(), 0.0, [])
    seq = []; first = True
    for i, rev, path, trim, mode in best[0][1]:
        c = cols[i][::-1] if rev else cols[i]
        c0, c1 = caps.get(id(cols[i]), (False, False))
        if rev: c0, c1 = c1, c0
        k0, k1 = (closes or {}).get(id(cols[i]), (True, True))
        if rev: k0, k1 = k1, k0
        pth = centre_run(list(path.coords), 1.5) if path is not None else []
        prs = column_pairs(poly, c, spacing, width=width, caps=(c0, c1))
        if mode == 'fwd':
            und = []; sat = zig(prs, spacing, (k0, k1))
        elif mode == 'contour':
            lft, rgt = rails(prs, width)
            und = centre_run(lft, 1.5) + centre_run(rgt[::-1], 1.5)[1:]
            sat = zig(prs, spacing, (k0, k1))
        elif kinds[i] == 'german':
            lft, rgt = rails(prs, width)
            und = centre_run(lft, 1.5) + centre_run(rgt[::-1], 1.5)[1:]
            idx = list(range(0, len(prs), max(1, int(2.0 / (spacing / 2))))) + [len(prs) - 1]
            und += [(lft if j % 2 == 0 else rgt)[k] for j, k in enumerate(idx)]   # low zigzag, 2 mm
            sat = zig(prs[::-1], spacing, (k1, k0))
        else:
            und = centre_run(c, 1.5)
            sat = zig(prs[::-1], spacing, (k1, k0))
        seq.append((pth + und + sat, (0, len(pth) + len(und)), trim and not first))   # travel lies under later satin too
        first = False
    return seq


def letter(poly, start, spacing=0.4, fill=None):
    """stitch sequence for one letter: list of point lists (each continuous)"""
    width = 2 * poly.area / poly.length
    br, G = branches(poly, width)
    if G is None: return [(br[0][0], (0, 0), False)]
    caps = {id(b[0]): (b[1], b[2]) for b in br}
    closes = {id(b[0]): (b[3], b[4]) for b in br if len(b) > 4}
    brt = br; br = [b[0] for b in br]
    def cols(cur):
        return _plan(poly, br, caps, G, cur, spacing, width, closes)
    seq = cols(start)
    # a stroke ending against a slanted neighbour leaves a thin wedge too small for a fill (middle of M):
    # only those ends run on into the neighbour; wider gaps (apex of A) keep their small fill
    if fill is not None:
        cov = coverage([blk[u1:] for blk, (u0, u1), _j in seq])
        rest = poly.buffer(-0.05).difference(cov)
        thin = [g for g in getattr(rest, 'geoms', [rest]) if g.geom_type == 'Polygon' and g.area >= 0.02
                and (g.area < 0.15 or g.buffer(-OPTS['gap_min'] / 2).is_empty)]
        near = [(k, e) for k, e in G.graph.get('jends', []) if any(g.distance(Point(brt[k][0][e])) < 0.4 * width for g in thin)]
        if near:
            _reach(brt, near, poly, width)
            seq = cols(start)
    # gaps the columns don't reach (apex of A, corners of M): small fill, sewn first (under the satin)
    if fill is not None:
        cov = coverage([blk[u1:] for blk, (u0, u1), _j in seq])
        rest = poly.buffer(-0.05).difference(cov)
        pre = []
        for g in getattr(rest, 'geoms', [rest]):
            if g.geom_type != 'Polygon' or g.area < 0.15 or g.buffer(-OPTS['gap_min'] / 2).is_empty: continue
            pre += fill(g.buffer(0.1).intersection(poly))
        if pre:
            # nearest-neighbour order, travel along the skeleton between the pieces
            nodes = list(G.nodes)
            near = lambda p: min(nodes, key=lambda q: math.dist(p, q))
            out = []; cur = start
            while pre:
                i = min(range(len(pre)), key=lambda k: math.dist(cur, pre[k][0]) if cur else pre[k][0][0] + pre[k][0][1])
                blk = pre.pop(i); path = []
                if cur is not None and math.dist(cur, blk[0]) > 0.4:
                    sp = nx.shortest_path(G, near(cur), near(blk[0]), weight='weight')
                    if len(sp) > 1: path = centre_run(list(LineString(sp).simplify(0.05).coords), 1.5)
                out.append((path + blk, (0, len(path)), False)); cur = blk[-1]
            pre = out
            # gap fills first (under the satin), then the columns, travelling on from the last fill
            seq = pre + cols(pre[-1][0][-1])
    return seq
