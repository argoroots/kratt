"""Satin columns for thin letter strokes: skeleton -> branches -> centre-walk underlay + satin back."""
import math
import numpy as np
import networkx as nx
from skimage.draw import polygon as skpoly
from skimage.morphology import skeletonize
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring

RES = 0.02  # mm per pixel


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
            if L < 1.8 * width and min(ends) == 1 and max(ends) > 2:
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
        if e0[0] == 'j' and e1[0] == 'j' and e0[1] == e1[1]: continue   # inside one junction
        ls = LineString(pts).simplify(0.04)
        if ls.length < 0.05: continue
        # split at sharp corners (E, L-type corners): direction change > 50 deg within ~1 width
        parts = _split_corners(ls, width)
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
                    if dot < -0.85 and (best is None or dot < best[0]): best = (dot, i, ki, j, kj)
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
    out = []
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
            if e[0] == 't': c[end] = _extend(_back(c, end, width), c[end], poly, width)
            elif e[0] == 'j': c[end] = _straight(_back(c, end, width), c[end], bend - jc, poly)
        if e0[0] == 'e': c[0] = _extend(_back(c, 0, width), c[0], poly, width)
        if e1[0] == 'e': c[-1] = _extend(_back(c, -1, width), c[-1], poly, width)
        out.append((c, e0[0] == 'e', e1[0] == 'e'))
    # skeleton pixel graph in mm for travel
    H = nx.Graph()
    for a, b, d in G.edges(data=True): H.add_edge(to_mm(a), to_mm(b), weight=d['weight'] * RES)
    return out, H


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


def _split_corners(ls, width):
    """split a centre line where it turns a corner: chord directions 1.2 widths before and after
    a point differ by more than 25 deg (local maximum)"""
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
        if A[i] > 25 and A[i] == max(A[max(0, i - 20):i + 21]):
            if not cuts or ds[i] - cuts[-1] > 2 * h: cuts.append(float(ds[i]))
    # curves (S, U, D, J) turn evenly: only keep sharp turns (angle concentrated, not spread out)
    keep = []
    for c in cuts:
        i = int(round((c - h) / 0.05))
        lo = ang(max(h, c - h)) if c - h >= h else 0; hi = ang(min(L - h, c + h)) if c + h <= L - h else 0
        if A[i] > 1.8 * max(lo, hi) and 1.4 * width < c < L - 1.4 * width: keep.append(c)
    if not keep: return [ls]
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
    """satin zigzag along a centre line; spacing = distance between stitches on the same side.
    Side distances are clamped to 1.25x the column's median, so junctions don't make spikes."""
    ls = LineString(line)
    L = ls.length
    n = max(2, int(round(L / (spacing / 2))) + 1)
    samples = []
    for i in range(n):
        d = L * i / (n - 1)
        p = ls.interpolate(d).coords[0]
        p0 = ls.interpolate(max(0, d - 0.15)).coords[0]; p1 = ls.interpolate(min(L, d + 0.15)).coords[0]
        tx, ty = p1[0] - p0[0], p1[1] - p0[1]; tl = math.hypot(tx, ty) or 1
        nrm = (-ty / tl, tx / tl)
        e = _edges(poly, p, nrm)
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
    pairs = []; last = (-np.median(neg), np.median(pos))
    for p, nrm, a, b in samples:
        if a is None: a, b = last
        a = max(a, -mn); b = min(b, mp)
        if b - a < 0.2: m_ = (a + b) / 2; a, b = m_ - 0.1, m_ + 0.1
        last = (a, b)
        pairs.append(((p[0] + nrm[0] * a, p[1] + nrm[1] * a), (p[0] + nrm[0] * b, p[1] + nrm[1] * b)))
    # end caps: carry both sides along the outline to the corners of the stroke end (square or oblique)
    if pairs and caps[0]: pairs = _cap(poly, pairs[::-1], spacing, width)[::-1]
    if pairs and caps[1]: pairs = _cap(poly, pairs, spacing, width)
    pts = []
    for k, (l, r) in enumerate(pairs): pts.append(l if k % 2 == 0 else r)
    return pts


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


def _plan(poly, br, caps, G, start, spacing, width):
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
                else:
                    end = e; mode = 'back'
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
        pth = centre_run(list(path.coords), 1.5) if path is not None else []
        if mode == 'back':
            und = centre_run(c, 1.5)
            sat = column(poly, c[::-1], spacing, width=width, caps=(c1, c0))
        else:
            und = []
            sat = column(poly, c, spacing, width=width, caps=(c0, c1))
        seq.append((pth + und + sat, (0, len(pth) + len(und)), trim and not first))   # travel lies under later satin too
        first = False
    return seq


def letter(poly, start, spacing=0.4, fill=None):
    """stitch sequence for one letter: list of point lists (each continuous)"""
    width = 2 * poly.area / poly.length
    br, G = branches(poly, width)
    if G is None: return [(br[0][0], (0, 0), False)]
    caps = {id(b[0]): (b[1], b[2]) for b in br}
    br = [b[0] for b in br]
    def cols(cur):
        return _plan(poly, br, caps, G, cur, spacing, width)
    seq = cols(start)
    # gaps the columns don't reach (apex of A, corners of M): small fill, sewn first (under the satin)
    if fill is not None:
        cov = coverage([blk[u1:] for blk, (u0, u1), _j in seq])
        rest = poly.buffer(-0.05).difference(cov)
        pre = []
        for g in getattr(rest, 'geoms', [rest]):
            if g.geom_type != 'Polygon' or g.area < 0.15 or g.buffer(-0.15).is_empty: continue
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
