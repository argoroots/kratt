"""Satin columns for strokes (letters, lines, borders).

    skeleton of the shape -> branches (centre lines of the strokes) -> columns: pairs of edge points
    -> zigzag; per letter an order of columns with as few trims as possible, underlay first.

letter() is the entry point. All units mm. OPTS holds the settings (digitize.satin_options fills it).
"""
import math

import networkx as nx
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union
from skimage.draw import polygon as fill_polygon_pixels
from skimage.morphology import skeletonize

PIXEL = 0.02  # mm per pixel of the skeleton raster

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
    mitre_max=60.0,      # corners turning up to this many degrees: one column, stitches turn round the corner
    reach=1.5,           # stroke ending against another runs on at most this many widths
    gap_min=0.3,         # uncovered gaps at least this wide (mm) get a small fill
)

TRIM_COST = 8.0          # column order: a trim costs as much as 40 mm of travel


def pull_for(dx, dy):
    """pull compensation for a stitch in direction (dx, dy): on a stretchy fabric (knit) the fabric gives
    most along its stretch direction, so stitches lying that way are pulled in most"""
    if not OPTS['stretch']:
        return OPTS['pull_mm']
    length = math.hypot(dx, dy) or 1
    angle = math.radians(OPTS['stretch_angle'])
    along = abs(dx / length * math.cos(angle) + dy / length * math.sin(angle))      # 1 along the stretch, 0 across it
    return OPTS['pull_mm'] * (1 + OPTS['stretch'] * (along - 0.5))


def unit(vector):
    length = math.hypot(*vector) or 1
    return vector[0] / length, vector[1] / length


def turn_degrees(v1, v2):
    """angle between two direction vectors, degrees"""
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / ((math.hypot(*v1) * math.hypot(*v2)) or 1)
    return math.degrees(math.acos(max(-1, min(1, cos))))


# ---------------------------------------------------------------- skeleton

def _raster(poly):
    """the shape as a boolean pixel mask (PIXEL mm), with the mm position of pixel (0, 0)"""
    min_x, min_y, max_x, max_y = poly.bounds
    origin_x, origin_y = min_x - 0.2, min_y - 0.2
    width = int((max_x - origin_x + 0.2) / PIXEL) + 1
    height = int((max_y - origin_y + 0.2) / PIXEL) + 1
    mask = np.zeros((height, width), bool)
    for ring, value in [(poly.exterior, True)] + [(r, False) for r in poly.interiors]:
        xs, ys = ring.xy
        rows, cols = fill_polygon_pixels((np.array(ys) - origin_y) / PIXEL, (np.array(xs) - origin_x) / PIXEL, mask.shape)
        mask[rows, cols] = value
    return mask, origin_x, origin_y


def _pixel_graph(skeleton):
    """graph of skeleton pixels (row, col), neighbours linked; weight = distance in pixels"""
    graph = nx.Graph()
    ys, xs = np.nonzero(skeleton)
    pixels = set(zip(ys.tolist(), xs.tolist()))
    for (y, x) in pixels:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dy or dx) and (y + dy, x + dx) in pixels:
                    # diagonal link only if no 4-connected detour exists (avoids pixel triangles)
                    if dy and dx and ((y + dy, x) in pixels or (y, x + dx) in pixels):
                        continue
                    graph.add_edge((y, x), (y + dy, x + dx), weight=math.hypot(dy, dx))
    return graph


def _paths(graph, key_nodes):
    """split the skeleton graph into paths between key nodes (and closed loops)"""
    seen = set()
    paths = []
    keys = set(key_nodes)
    for k in keys:
        for neighbour in graph.neighbors(k):
            if (k, neighbour) in seen:
                continue
            path = [k, neighbour]
            seen.add((k, neighbour))
            seen.add((neighbour, k))
            while path[-1] not in keys:
                following = [n for n in graph.neighbors(path[-1]) if n != path[-2]]
                if not following:
                    break
                seen.add((path[-1], following[0]))
                seen.add((following[0], path[-1]))
                path.append(following[0])
                if path[-1] == path[0]:
                    break
            paths.append(path)

    # pure loops (e.g. O without key nodes)
    def unvisited():
        return [n for n in graph if all((n, nb) not in seen for nb in graph.neighbors(n))]

    rest = unvisited()
    while rest:
        first = rest[0]
        path = [first]
        previous = None
        while True:
            following = [n for n in graph.neighbors(path[-1]) if n != previous and (path[-1], n) not in seen]
            if not following:
                break
            seen.add((path[-1], following[0]))
            seen.add((following[0], path[-1]))
            previous = path[-1]
            path.append(following[0])
            if following[0] == first:
                break
        paths.append(path)
        rest = unvisited()
    return paths


def _continues(spur, junction, paths, width):
    """a short end branch that carries on straight from another branch at its junction is the real end
    of a stroke (stem of d or b just below the bowl), not a corner artefact: keep it"""
    def direction(path):                # direction away from the junction, over ~1.5 widths (pixels)
        if path[0] != junction:
            path = path[::-1]
        k = min(len(path) - 1, max(1, int(1.5 * width / PIXEL)))
        dy, dx = path[k][0] - path[0][0], path[k][1] - path[0][1]
        length = math.hypot(dx, dy) or 1
        return dx / length, dy / length

    a = direction(list(spur))
    for other in paths:
        if other is spur or junction not in (other[0], other[-1]) or len(other) < 2 or other[0] == other[-1]:
            continue
        b = direction(list(other))
        if a[0] * b[0] + a[1] * b[1] < -0.97:     # within ~14°: corner spurs (M, A tips) bend away more
            return True
    return False


# ---------------------------------------------------------------- branches

def branches(poly, width):
    """centre lines (mm) of the strokes, ends extended to the outline.
    Returns ([(points, cap start, cap end, closed start, closed end)], skeleton graph in mm) where cap =
    a free end, closed = the end is on the outline (free or through to the outer edge). The graph
    carries .graph['jends']: (branch index, end) of the ends that stop against another stroke."""
    mask, origin_x, origin_y = _raster(poly)
    graph = _pixel_graph(skeletonize(mask))
    if graph.number_of_nodes() == 0:
        c = poly.centroid
        return [([(c.x, c.y)], False, False)], None

    def to_mm(node):
        return (origin_x + node[1] * PIXEL, origin_y + node[0] * PIXEL)

    _remove_spurs(graph, width)
    key_nodes = [n for n in graph if graph.degree(n) != 2]
    cluster, cluster_count = _junction_clusters(graph, width)

    # segments: [centre line, start end, finish end]; an end is ('e', None) free, ('j', cluster) at a
    # junction, ('x', None) elsewhere (loop), later ('t', cluster) through to the outer edge
    segments = []
    for path in _paths(graph, key_nodes):
        points = [to_mm(n) for n in path]
        if len(points) < 2:
            continue

        def end_of(node):
            if node in cluster:
                return ('j', cluster[node])
            return ('e', None) if graph.degree(node) == 1 else ('x', None)

        start, finish = end_of(path[0]), end_of(path[-1])
        if start[0] == 'j' and finish[0] == 'j' and start[1] == finish[1] and len(points) * PIXEL < 2 * width:
            continue   # inside one junction (a longer one is a loop: bowl of a, b, d)
        line = LineString(points).simplify(0.04)
        if line.length < 0.05:
            continue
        # split at sharp corners (E, L-type corners): direction change > 50 deg within ~1 width
        parts = _split_corners(line, width, poly=poly)
        for k, part in enumerate(parts):
            part_start = start if k == 0 else ('j', cluster_count + k - 1)
            part_finish = finish if k == len(parts) - 1 else ('j', cluster_count + k)
            segments.append([part, part_start, part_finish])
        cluster_count += len(parts) - 1

    bend = 0.9 * width
    _join_hairpins(segments, cluster_count, poly, width, bend)
    _join_through_strokes(segments, cluster_count, width, bend)
    for c in range(cluster_count):      # a junction of two strokes: the longer one goes through to the outer edge
        ends = _ends_at(segments, c)
        if len(ends) == 2 and ends[0][0] != ends[1][0]:
            (i, ki), (j, kj) = ends
            through = i if segments[i][0].length >= segments[j][0].length else j
            segments[through][ki if through == i else kj] = ('t', c)

    result = []
    junction_ends = []
    for line, start, finish in segments:
        points = _shape_ends(line, start, finish, poly, width, bend)
        if points is None:
            continue
        result.append((points, start[0] == 'e', finish[0] == 'e', start[0] in 'et', finish[0] in 'et'))
        junction_ends += [(len(result) - 1, end) for end, e in ((0, start), (-1, finish)) if e[0] == 'j']

    # skeleton pixel graph in mm, for travel along the letter
    travel = nx.Graph()
    for a, b, data in graph.edges(data=True):
        travel.add_edge(to_mm(a), to_mm(b), weight=data['weight'] * PIXEL)
    travel.graph['jends'] = junction_ends
    return result, travel


def _remove_spurs(graph, width):
    """remove short end branches (corner artefacts of the skeleton), up to three rounds"""
    for _ in range(3):
        key_nodes = [n for n in graph if graph.degree(n) != 2]
        paths = _paths(graph, key_nodes)
        removed = False
        for path in paths:
            length = sum(math.dist(a, b) for a, b in zip(path, path[1:])) * PIXEL
            degrees = [graph.degree(path[0]), graph.degree(path[-1])]
            junction = path[0] if degrees[0] > 2 else path[-1]
            if (length < 1.8 * width and min(degrees) == 1 and max(degrees) > 2
                    and not (length > 0.9 * width and _continues(path, junction, paths, width))):
                graph.remove_nodes_from([n for n in path if graph.degree(n) <= 2])
                removed = True
        if not removed:
            break


def _junction_clusters(graph, width):
    """junction pixels grouped (a junction is often several neighbouring pixels): {pixel: cluster}, count"""
    junctions = [n for n in graph if graph.degree(n) > 2]
    cluster = {}
    count = 0
    for n in junctions:
        if n in cluster:
            continue
        stack = [n]
        cluster[n] = count
        while stack:
            u = stack.pop()
            for v in junctions:
                if v not in cluster and math.dist(u, v) * PIXEL < 0.8 * width:
                    cluster[v] = count
                    stack.append(v)
        count += 1
    return cluster, count


def _ends_at(segments, cluster):
    """(segment index, 1 = start / 2 = finish) of the segment ends at a junction cluster"""
    return [(i, k) for i, segment in enumerate(segments) for k in (1, 2) if segment[k] == ('j', cluster)]


def _trim_at_junction(line, at_start, length):
    """drop `length` mm of a centre line at one end (the bent part near a junction)"""
    if line.length <= length + 0.3:
        return line
    return substring(line, length, line.length) if at_start else substring(line, 0, line.length - length)


def _out_direction(line, at_start, width):
    """unit direction of a centre line leaving one of its ends, over 1.5 widths"""
    length = line.length
    p0 = line.interpolate(0 if at_start else length)
    p1 = line.interpolate(min(length, 1.5 * width) if at_start else max(0, length - 1.5 * width))
    return unit((p1.x - p0.x, p1.y - p0.y))


def _into_junction(segments, i, k, bend):
    """segment i trimmed at its junction end k, as points ending at the junction"""
    points = list(_trim_at_junction(segments[i][0], k == 1, bend).coords)
    return points[::-1] if k == 1 else points


def _out_of_junction(segments, i, k, bend):
    """segment i trimmed at its junction end k, as points starting at the junction"""
    points = list(_trim_at_junction(segments[i][0], k == 1, bend).coords)
    return points[::-1] if k == 2 else points


def _far_end(segments, i, k):
    """the other end of segment i (k = the end at the junction)"""
    return segments[i][2] if k == 1 else segments[i][1]


def _join_hairpins(segments, cluster_count, poly, width, bend):
    """hairpin: two strokes leaving a junction side by side (narrow V), maybe with a short free stem out
    of the junction the other way (the closed tip): one column round the bend, the stitches fan at the
    corner. The stem goes; both arms run on straight to where their centre lines meet. 'auto' joins only
    when the outline is rounded there, 'split' never."""
    mode = OPTS.get('hairpin', 'auto')
    for c in range(cluster_count if mode != 'split' else 0):
        ends = _ends_at(segments, c)
        if len(ends) not in (2, 3) or len({i for i, _ in ends}) != len(ends):
            continue
        stems = [(i, k) for i, k in ends if segments[i][2 if k == 1 else 1][0] == 'e' and segments[i][0].length < 5 * width]
        if len(ends) == 3 and len(stems) != 1:
            continue
        stem = stems[0][0] if len(ends) == 3 else None                    # (a short stem may be gone already)
        (ai, ak), (bi, bk) = [e for e in ends if e[0] != stem]
        da = _out_direction(segments[ai][0], ak == 1, width)
        db = _out_direction(segments[bi][0], bk == 1, width)
        if da[0] * db[0] + da[1] * db[1] < math.cos(math.radians(70)):
            continue                                                      # not a narrow V
        if stem is not None:
            sk = stems[0][1]
            ds = _out_direction(segments[stem][0], sk == 1, width)
            mx, my = da[0] + db[0], da[1] + db[1]
            mn = math.hypot(mx, my) or 1
            if (mx * ds[0] + my * ds[1]) / mn > -0.8:
                continue                                                  # stem not out of the V
            tip = segments[stem][0].coords[-1 if sk == 1 else 0]
        else:
            tip = segments[ai][0].coords[0 if ak == 1 else -1]
        arm_a = _into_junction(segments, ai, ak, bend)
        arm_b = _out_of_junction(segments, bi, bk, bend)
        pa, pb = arm_a[-1], arm_b[0]

        def straight_direction(points):     # direction of the straight part, past the bend into the junction
            line = LineString(points)
            q0 = line.interpolate(min(line.length, 2 * width))
            q1 = line.interpolate(min(line.length, 5 * width))
            return unit((q0.x - q1.x, q0.y - q1.y))

        ua = straight_direction(arm_a[::-1])                              # along A into the corner
        ub = straight_direction(arm_b)
        ub = (-ub[0], -ub[1])                                             # along B out of it
        determinant = ua[0] * ub[1] - ua[1] * ub[0]
        if abs(determinant) < 1e-6:
            continue
        t = ((pb[0] - pa[0]) * ub[1] - (pb[1] - pa[1]) * ub[0]) / determinant
        corner = (pa[0] + ua[0] * t, pa[1] + ua[1] * t)
        if t < 0 or math.dist(corner, tip) > 3 * width:
            continue
        if mode == 'auto' and not _smooth_turn(poly, corner, width):
            continue                                                      # sharp tip: split (the default)
        joined = [LineString(arm_a + [corner] + arm_b), _far_end(segments, ai, ak), _far_end(segments, bi, bk)]
        for k in sorted([x for x in (ai, bi, stem) if x is not None], reverse=True):
            segments.pop(k)
        segments.append(joined)


def _join_through_strokes(segments, cluster_count, width, bend):
    """through-strokes: at each junction join the two most opposite branches into one column"""
    for c in range(cluster_count):
        while True:
            ends = _ends_at(segments, c)
            best = None
            for x in range(len(ends)):
                for y in range(x + 1, len(ends)):
                    (i, ki), (j, kj) = ends[x], ends[y]
                    if i == j:
                        continue
                    di = _out_direction(segments[i][0], ki == 1, width)
                    dj = _out_direction(segments[j][0], kj == 1, width)
                    dot = di[0] * dj[0] + di[1] * dj[1]
                    # three-way junction of long strokes (the U of a tuning fork curves into it): join more readily
                    long_strokes = min(segments[i][0].length, segments[j][0].length) >= 8 * width
                    limit = -0.65 if len(ends) == 3 and long_strokes else -0.85
                    if dot < limit and (best is None or dot < best[0]):
                        best = (dot, i, ki, j, kj)
            if best is None:
                break
            _, i, ki, j, kj = best
            joined = [LineString(_into_junction(segments, i, ki, bend) + _out_of_junction(segments, j, kj, bend)),
                      _far_end(segments, i, ki), _far_end(segments, j, kj)]
            for k in sorted([i, j], reverse=True):
                segments.pop(k)
            segments.append(joined)


def _shape_ends(line, start, finish, poly, width, bend):
    """points of one branch with its ends placed: free ends out to the outline, ends through to the outer
    edge at the outline, ends against another stroke straight on into it. None if too short."""
    cut = 1.0 * width
    if start[0] == 'e' and line.length > 2 * cut + 0.2:
        line = substring(line, cut, line.length)
    if finish[0] == 'e' and line.length > cut + 0.2:
        line = substring(line, 0, line.length - cut)
    # stroke meeting another stroke: drop the bent skeleton part, run straight up to the other stroke
    if start[0] in 'jt':
        line = _trim_at_junction(line, True, bend)
    if finish[0] in 'jt':
        line = _trim_at_junction(line, False, bend)
    points = list(line.coords)
    if len(points) < 2:
        return None
    for end, e in ((0, start), (-1, finish)):
        # a stroke going through to the outer edge ends at it like a free end: a column end is not pulled
        # in (its stitches run along the edge) but pushed out, while the side edges of the stroke it
        # crosses are pulled back to the outline. Past it by the compensation the E stem stood out on top.
        if e[0] == 't':
            widen = min(OPTS['max_widen'] / 2, max(0.0, (OPTS['min_width'] - width) / 2))
            points[end] = _extend(_back(points, end, width), points[end], poly, width, inset=0.1 - widen)
        elif e[0] == 'j':
            points[end] = _straight_on(_back(points, end, width), points[end], bend - 0.4 * width, poly)
    if width >= 2.5:                 # wide column: the skeleton tail bends to a corner of the end;
        for end, e in ((0, start), (-1, finish)):    # drop the bent last piece, the end runs straight on (below)
            if e[0] != 'e':
                continue
            tail = points if end == -1 else points[::-1]

            def angle(a, b):
                return math.atan2(b[1] - a[1], b[0] - a[0])

            while len(tail) >= 3:
                last_length = math.dist(tail[-2], tail[-1])
                bend_angle = abs((angle(tail[-2], tail[-1]) - angle(tail[-3], tail[-2]) + math.pi) % (2 * math.pi) - math.pi)
                if last_length < 1.5 * width and bend_angle > math.radians(15):
                    tail = tail[:-1]
                else:
                    break
            points = tail if end == -1 else tail[::-1]
    if start[0] == 'e':
        points[0] = _extend(_back(points, 0, width), points[0], poly, width)
    if finish[0] == 'e':
        points[-1] = _extend(_back(points, -1, width), points[-1], poly, width)
    return points


def _reach(branch_list, junction_ends, poly, width):
    """a stroke that ends against another one runs on until both of its sides are inside the other
    stroke, so no wedge is left between its square end and a slanted neighbour (middle of M, V, K)"""
    for k, end in junction_ends:
        points = branch_list[k][0]
        b = points[end]
        a = _back(points, end, width)
        u = unit((b[0] - a[0], b[1] - a[1]))
        n = (-u[1], u[0])
        others = [LineString(o[0]) for i, o in enumerate(branch_list)
                  if i != k and len(o[0]) > 1 and LineString(o[0]).distance(Point(b)) < width]
        if not others:
            continue
        # stop as soon as the side lagging behind is 0.15 mm inside the other stroke (just enough, little overlap)
        other = unary_union(others)
        half = 0.5 * width
        limit = 0.5 * width - 0.15
        t = 0.0
        while t < OPTS['reach'] * width:
            q = (b[0] + u[0] * t, b[1] + u[1] * t)
            if all(other.distance(Point(q[0] + side * n[0] * half, q[1] + side * n[1] * half)) <= limit for side in (1, -1)):
                break
            t += 0.05
        else:
            q = (b[0] + u[0] * t, b[1] + u[1] * t)   # not reached: go as far as allowed
        inside = poly.buffer(0.02)
        while t > 0 and not inside.contains(Point(q)):        # past the outline (top of A): as far as it stays inside
            t -= 0.05
            q = (b[0] + u[0] * t, b[1] + u[1] * t)
        if t > 0:
            points[end] = q


def _straight_on(a, b, length, poly):
    """b moved on by `length` in direction a->b, if that stays inside the shape"""
    d = math.dist(a, b) or 1
    q = (b[0] + (b[0] - a[0]) / d * length, b[1] + (b[1] - a[1]) / d * length)
    return q if poly.buffer(0.02).contains(Point(q)) else b


def _smooth_turn(poly, point, width):
    """a hairpin bend: the outline on the outside of the turn is a smooth curve (no vertex turning more
    than 40 deg). The inside may come to a point - the stitches pivot there, fanning round the bend."""
    radius = 1.2 * width + 0.3
    near = poly.buffer(0).boundary.intersection(Point(point).buffer(radius))
    for piece in getattr(near, 'geoms', [near]):
        if piece.is_empty or piece.geom_type != 'LineString':
            continue
        coords = list(piece.simplify(0.03).coords)
        if len(coords) < 5:
            continue                                   # a short piece: the inside point
        turns = []
        for a, b, d in zip(coords, coords[1:], coords[2:]):
            v1 = (b[0] - a[0], b[1] - a[1])
            v2 = (d[0] - b[0], d[1] - b[1])
            l1, l2 = math.hypot(*v1), math.hypot(*v2)
            if l1 < 1e-6 or l2 < 1e-6:
                continue
            turns.append(math.degrees(math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2))))))
        if turns and max(turns) <= 40 and sum(turns) >= 90:
            return True                                 # a real bend, rounded on the outside
    return False


def _corner_positions(line, width, threshold, poly=None):
    """distances along a centre line where it turns a corner: chord directions 1.2 widths before and
    after a point differ by more than `threshold` deg (local maximum, angle concentrated there - curves
    such as S, U, D, J turn evenly). With the outline given ('auto' hairpins), a turn whose outline is
    a smooth curve (a hairpin bend, not a corner) is no corner: the stitches fan round it."""
    length = line.length
    h = 1.2 * width
    if length < 2 * h + 0.2:
        return []
    distances = np.arange(h, length - h, 0.05)

    def turn_at(d):
        p0, p1, p2 = (line.interpolate(v).coords[0] for v in (d - h, d, d + h))
        return turn_degrees((p1[0] - p0[0], p1[1] - p0[1]), (p2[0] - p1[0], p2[1] - p1[1]))

    turns = [turn_at(d) for d in distances]
    candidates = []
    for i in range(len(turns)):
        if turns[i] > threshold and turns[i] == max(turns[max(0, i - 20):i + 21]):
            if not candidates or distances[i] - candidates[-1] > 2 * h:
                candidates.append(float(distances[i]))
    corners = []
    for c in candidates:
        i = int(round((c - h) / 0.05))
        before = turn_at(max(h, c - h)) if c - h >= h else 0
        after = turn_at(min(length - h, c + h)) if c + h <= length - h else 0
        if turns[i] > 1.8 * max(before, after) and 1.4 * width < c < length - 1.4 * width:
            if poly is not None and OPTS.get('hairpin', 'auto') == 'auto' and _smooth_turn(poly, line.interpolate(c).coords[0], width):
                continue
            corners.append(c)
    return corners


def _split_corners(line, width, poly=None):
    """split a centre line at corners turning more than mitre_max (and 25 deg)"""
    cuts = _corner_positions(line, width, max(25, OPTS['mitre_max']), poly)
    if not cuts:
        return [line]
    parts = []
    previous = 0.0
    for d in cuts + [line.length]:
        if d - previous > 0.05:
            parts.append(substring(line, previous, d))
        previous = d
    return parts


def _corners(line, width):
    """corners kept inside one column (turn between 25 deg and mitre_max): distance along the line,
    direction before and after (unit vectors)"""
    if OPTS['mitre_max'] <= 25:
        return []
    result = []
    h = 1.2 * width
    length = line.length
    for d in _corner_positions(line, width, 25):
        p0, p1, p2 = (line.interpolate(v).coords[0] for v in (max(0, d - h), d, min(length, d + h)))
        u1 = (p1[0] - p0[0], p1[1] - p0[1])
        u2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*u1) or 1, math.hypot(*u2) or 1
        u1 = (u1[0] / l1, u1[1] / l1)
        u2 = (u2[0] / l2, u2[1] / l2)
        turn = math.degrees(math.acos(max(-1, min(1, u1[0] * u2[0] + u1[1] * u2[1]))))
        if turn <= OPTS['mitre_max']:
            result.append((d, u1, u2))
    return result


def _back(points, end, width):
    """a point about one stroke width back from the end, for a straight end direction"""
    line = LineString(points if end == -1 else points[::-1])
    return line.interpolate(max(0, line.length - width)).coords[0]


def _extend(a, b, poly, width, inset=0.1):
    """extend from b in direction a->b while a normal across the stroke still meets the shape
    (covers square, oblique and slightly curved stroke ends), stopping `inset` mm short"""
    d = math.dist(a, b) or 1
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    nx_, ny_ = -uy, ux
    half = 0.6 * width
    length = 0.0
    step = 0.05
    while length < 3 * width:
        q = (b[0] + ux * (length + step), b[1] + uy * (length + step))
        across = LineString([(q[0] - nx_ * half, q[1] - ny_ * half), (q[0] + nx_ * half, q[1] + ny_ * half)])
        if across.intersection(poly).length < 0.12:
            break
        length += step
    length = max(0, length - inset)
    return (b[0] + ux * length, b[1] + uy * length)


# ---------------------------------------------------------------- columns

def _edges(poly, point, normal, reach=2.5):
    """points where the normal through point meets the outline on both sides"""
    a = (point[0] - normal[0] * reach, point[1] - normal[1] * reach)
    b = (point[0] + normal[0] * reach, point[1] + normal[1] * reach)
    crossing = LineString([a, b]).intersection(poly)
    pieces = [g for g in getattr(crossing, 'geoms', [crossing]) if g.geom_type == 'LineString' and not g.is_empty]
    if not pieces:
        return None
    nearest = min(pieces, key=lambda g: g.distance(Point(point)))
    coords = list(nearest.coords)
    return coords[0], coords[-1]


def column_pairs(poly, line, spacing=0.4, width=None, caps=(False, False)):
    """(left, right) edge points along a centre line; spacing = distance between stitches on the same side.
    The next stitch is placed where the side that moves most (the outside of a curve, the long side of
    a slanted end) has moved spacing/2 away from the previous stitch, measured square to that stitch;
    so curves are as dense on the outside as straight parts, and the inside gets short stitches (zig).
    Side distances are clamped to 1.12x the column's median, so junctions don't make spikes."""
    centre = LineString(line)
    length = centre.length
    n = max(2, int(math.ceil(length / (spacing / 16))) + 1)         # dense samples, picked from below
    corners = _corners(centre, width or 1)
    end_edges = [(d, _end_edge(poly, centre.interpolate(d).coords[0], width or 1))
                 for d, capped in ((0.0, caps[0]), (length, caps[1])) if capped]
    end_edges = [(d, e) for d, e in end_edges if e is not None]

    # samples: (point, stitch direction, distance to the outline on the negative / positive side)
    samples = []
    stretch = []                      # how much longer than square a stitch may be (turned stitches)
    for i in range(n):
        d = length * i / (n - 1)
        p = centre.interpolate(d).coords[0]
        # direction from the line over +-half a width: a kink in the centre line (where a branch joins)
        # turns the stitches gradually instead of all at once, which would open a wedge on the outside
        half = max(0.15, 0.5 * (width or 0))
        p0 = centre.interpolate(max(0, d - half)).coords[0]
        p1 = centre.interpolate(min(length, d + half)).coords[0]
        tx, ty = p1[0] - p0[0], p1[1] - p0[1]
        tl = math.hypot(tx, ty) or 1
        normal, allowed_longer = _stitch_direction(-ty / tl, tx / tl, d, corners, width, end_edges)
        stretch.append(allowed_longer)
        edges = _edges(poly, p, normal, max(2.5, 1.5 * (width or 1)))
        if edges is not None and LineString(edges).distance(Point(p)) > 0.7 * (width or 1):
            edges = None
        if edges is None:
            samples.append((p, normal, None, None))
            continue
        a, b = edges
        da = (a[0] - p[0]) * normal[0] + (a[1] - p[1]) * normal[1]
        db = (b[0] - p[0]) * normal[0] + (b[1] - p[1]) * normal[1]
        samples.append((p, normal, min(da, db), max(da, db)))
    negative = [-s[2] for s in samples if s[2] is not None and s[2] < 0]
    positive = [s[3] for s in samples if s[3] is not None and s[3] > 0]
    if not negative or not positive:
        return []
    limit_neg, limit_pos = 1.12 * float(np.median(negative)), 1.12 * float(np.median(positive))
    if width:
        limit_neg, limit_pos = min(limit_neg, 0.62 * width), min(limit_pos, 0.62 * width)
    local_limits = _taper_limits(samples, n, length, width, limit_neg, limit_pos)
    widths = [s[3] - s[2] for s in samples if s[2] is not None]
    widen = min(OPTS['max_widen'] / 2, max(0.0, (OPTS['min_width'] - float(np.median(widths))) / 2)) if widths else 0.0

    dense = []
    last = (-np.median(negative), np.median(positive))
    for i, ((p, normal, a, b), allowed_longer) in enumerate(zip(samples, stretch)):
        if a is None:
            a, b = last          # past the outline (through-going end): keep the last full width
        cap_neg, cap_pos = local_limits[i] if local_limits else (limit_neg, limit_pos)
        a = max(a, -cap_neg * allowed_longer)
        b = min(b, cap_pos * allowed_longer)
        if b - a < 0.2:
            middle = (a + b) / 2
            a, b = middle - 0.1, middle + 0.1
        if b - a >= 0.8 * (limit_neg + limit_pos) / 1.12:
            last = (a, b)   # only full-width stitches are carried on
        if OPTS['pull_pct']:
            g = (b - a) * OPTS['pull_pct'] / 200
            a, b = a - g, b + g
        pull = pull_for(*normal)
        a, b = a - pull - widen, b + pull + widen
        dense.append(((p[0] + normal[0] * a, p[1] + normal[1] * a), (p[0] + normal[0] * b, p[1] + normal[1] * b)))
    _clip_to_outline(dense, samples, poly, widen)

    # free ends: the column runs on to the tip and every stitch is cut by the outline, so a square
    # or slanted end is filled with stitches getting shorter, parallel to the others (no fan)
    full = [s[2] is not None and s[3] - s[2] >= 0.25 for s in samples]
    i0, i1 = 0, len(dense)
    if caps[0]:
        while i0 < i1 and not full[i0]:
            i0 += 1
    if caps[1]:
        while i1 > i0 and not full[i1 - 1]:
            i1 -= 1
    dense = dense[i0:i1]
    if not dense:
        return []

    # pick stitches: the next one when the side moving most is spacing/2 from the previous stitch
    step = spacing / 2
    # stitches that must be there: the one along the bisector of each kept corner (reaches the outer corner)
    required = set()
    if corners:
        positions = [length * i / (n - 1) for i in range(n)][i0:i1]
        for at, _, _ in corners:
            required.add(min(range(len(positions)), key=lambda k: abs(positions[k] - at)))
    pairs = [dense[0]]
    for qi, q in enumerate(dense[1:], start=1):
        if qi in required:
            pairs.append(q)
            continue
        l0, r0 = pairs[-1]
        vx, vy = r0[0] - l0[0], r0[1] - l0[1]
        vl = math.hypot(vx, vy)
        if vl < 0.01:
            moved = max(math.dist(q[0], l0), math.dist(q[1], r0))
        else:
            nx_, ny_ = -vy / vl, vx / vl
            moved = max(abs((q[0][0] - l0[0]) * nx_ + (q[0][1] - l0[1]) * ny_), abs((q[1][0] - r0[0]) * nx_ + (q[1][1] - r0[1]) * ny_))
        if moved >= step - spacing / 32:
            pairs.append(q)     # within half a dense step
    if dense[-1] is not pairs[-1]:
        l0, r0 = pairs[-1]
        if max(math.dist(dense[-1][0], l0), math.dist(dense[-1][1], r0)) > 0.1:
            pairs.append(dense[-1])
    if OPTS['push_mm'] > 0:    # shorten free ends
        k = int(OPTS['push_mm'] / step)
        if caps[1] and len(pairs) > 2 * k + 4:
            pairs = pairs[:len(pairs) - k]
        if caps[0] and len(pairs) > 2 * k + 4:
            pairs = pairs[k:]
    return pairs


def _taper_limits(samples, n, length, width, limit_neg, limit_pos):
    """a column whose width changes along it (taper, wedge): clamp each sample to the local median over
    +-1.5 widths instead, else the wide end is cut down to the column's middle width and left to gap
    fill. Only a real taper (width grows steadily), not the bulges at junctions of K or M. None if not."""
    good = [s for s in samples if s[2] is not None and s[2] < 0 < s[3]]
    if not width or len(good) <= 8:
        return None
    widths = np.array([s[3] - s[2] for s in good])
    index = np.arange(len(widths))
    if not (np.percentile(widths, 90) > 1.6 * np.percentile(widths, 10) and abs(np.corrcoef(index, widths)[0, 1]) > 0.85):
        return None
    step = length / (n - 1)
    window = max(1, int(1.5 * width / step))
    neg = np.full(n, np.nan)
    pos = np.full(n, np.nan)
    for i, s in enumerate(samples):
        if s[2] is not None and s[2] < 0 < s[3]:
            neg[i] = -s[2]
            pos[i] = s[3]
    limits = []
    for i in range(n):
        a, b = neg[max(0, i - window): i + window + 1], pos[max(0, i - window): i + window + 1]
        a, b = a[~np.isnan(a)], b[~np.isnan(b)]
        limits.append((1.12 * float(np.median(a)) if len(a) else limit_neg, 1.12 * float(np.median(b)) if len(b) else limit_pos))
    return limits


def _clip_to_outline(dense, samples, poly, widen):
    """no stitch reaches past the outline by more than the compensation: where the centre line runs on
    past the shape (sharp tips of M, N, W, A; ends that carry the last full width), a stitch is cut
    back to the outline + compensation instead of sticking out"""
    allowed = poly.buffer(OPTS['pull_mm'] * (1 + OPTS['stretch'] / 2) + widen + 0.1, join_style=1)   # round: a mitre would spike out at sharp tips
    for k, (left, right) in enumerate(dense):
        if allowed.contains(Point(left)) and allowed.contains(Point(right)):
            continue
        inside = LineString([left, right]).intersection(allowed)
        pieces = [g for g in getattr(inside, 'geoms', [inside]) if g.geom_type == 'LineString' and not g.is_empty]
        if not pieces:
            continue
        middle = samples[k][0]
        piece = min(pieces, key=lambda g: g.distance(Point(middle)))
        c0, c1 = piece.coords[0], piece.coords[-1]
        if math.dist(c0, left) > math.dist(c1, left):
            c0, c1 = c1, c0
        dense[k] = (c0, c1)


def _end_edge(poly, tip, width):
    """direction of the outline edge closing a free stroke end (the longest straight piece of
    outline near the tip), or None"""
    ring = list(poly.exterior.coords)
    best = None
    for a, b in zip(ring, ring[1:]):
        edge = LineString([a, b])
        if edge.distance(Point(tip)) < 0.35 * width and edge.length > 0.3 * width:
            if best is None or edge.length > best[0]:
                best = (edge.length, a, b)
    if best is None:
        return None
    _, a, b = best
    length = math.dist(a, b)
    return ((b[0] - a[0]) / length, (b[1] - a[1]) / length)


def _stitch_direction(nx_, ny_, d, corners, width, end_edges=()):
    """stitch direction at distance d along the column. Near a free end it turns over about one width
    to lie along the end edge (square ends, slanted ends like K and A feet), so the last stitches close
    the end exactly. Returns (direction, how much longer the stitch may be than a square one)."""
    reach = 0.9 * (width or 1)
    for at, edge in end_edges:
        if abs(d - at) < reach:
            t = 1 - abs(d - at) / reach
            cos = edge[0] * nx_ + edge[1] * ny_
            if cos < 0:
                edge = (-edge[0], -edge[1])
                cos = -cos
            if cos < 0.5:
                break                       # end edge more than 60 deg off: leave square
            a1 = math.atan2(ny_, nx_)
            a2 = math.atan2(edge[1], edge[0])
            da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            a = a1 + da * t
            n = (math.cos(a), math.sin(a))
            return n, 1 / max(abs(n[0] * nx_ + n[1] * ny_), 0.5)
    return _stitch_direction_at_corner(nx_, ny_, d, corners, width)


def _stitch_direction_at_corner(nx_, ny_, d, corners, width):
    """stitch direction: square to the column, except around a kept corner, where it turns from
    square-before through the corner bisector to square-after over about one column width.
    Returns (direction, how much longer the stitch may be than a square one)."""
    reach = 0.7 * (width or 1)
    for at, u1, u2 in corners:
        if abs(d - at) < reach:
            t = (d - (at - reach)) / (2 * reach)
            a1 = math.atan2(u1[0], -u1[1])          # normals (-uy, ux) as angles
            a2 = math.atan2(u2[0], -u2[1])
            da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            a = a1 + da * t
            n = (math.cos(a), math.sin(a))
            if n[0] * nx_ + n[1] * ny_ < 0:
                n = (-n[0], -n[1])
            return n, 1 / max(abs(n[0] * nx_ + n[1] * ny_), 0.5)
    return (nx_, ny_), 1.0


def zig(pairs, spacing=0.4, close=(True, True)):
    """zigzag through the pairs. Where needle points on one side crowd (inside of a curve or a corner),
    a point closer than short_dist to the last full-length point on that side is moved inwards along
    its stitch by the next share from short_inset (cycling), so the thread spreads instead of piling up."""
    points = [p[k % 2] for k, p in enumerate(pairs)]
    insets = OPTS['short_inset'] if isinstance(OPTS['short_inset'], (list, tuple)) else (OPTS['short_inset'],)
    last_full = [None, None]
    next_inset = [0, 0]
    for k in range(len(points)):
        side = k % 2
        if last_full[side] is None or math.dist(points[k], last_full[side]) >= OPTS['short_dist']:
            last_full[side] = points[k]
            next_inset[side] = 0
            continue
        a, b = pairs[k][side], pairs[k][1 - side]
        share = insets[next_inset[side] % len(insets)]
        next_inset[side] += 1
        points[k] = (a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share)
    # close the ends that are on the outline (free ends, strokes going through to the outer edge): the
    # first and last pair are stitched fully, else a corner stays open. Ends inside another stroke stay open.
    if len(pairs) > 1:
        if close[0]:
            points = [pairs[0][1]] + points
        last = pairs[-1][(len(pairs) - 1) % 2 ^ 1]
        if close[1] and math.dist(last, points[-1]) > 0.05:
            points.append(last)
    return _split_long(points)


def _split_long(points):
    """satin stitches longer than split_len (wide columns) get extra needle points; their place
    shifts by 1/split_staggers from stitch to stitch, so no ridge forms along the column"""
    longest = OPTS['split_len']
    if not longest:
        return points
    result = points[:1]
    for k in range(1, len(points)):
        a, b = points[k - 1], points[k]
        d = math.dist(a, b)
        if d > longest:
            phase = (k % OPTS['split_staggers']) / OPTS['split_staggers']
            shares = [(j + phase) * longest / d for j in range(int(d / longest) + 1)]
            shares = [t for t in shares if 0.25 * longest / d < t < 1 - 0.25 * longest / d]
            result += [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in shares]
        result.append(b)
    return result


def rails(pairs, width):
    """edge runs a little inside the column, for contour underlay"""
    inset = max(0.2, 0.15 * width) + OPTS['pull_mm']     # from the drawn edge, not the compensated one

    def moved_in(a, b):
        d = math.dist(a, b) or 1
        t = min(inset, d / 2.5) / d
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    left = [moved_in(l, r) for l, r in pairs]
    right = [moved_in(r, l) for l, r in pairs]
    return left, right


def underlay_kind(width):
    """satin underlay for a column of this drawn width: centre walk, contour (edge runs) or german"""
    if OPTS.get('underlay'):
        return OPTS['underlay']
    if width >= OPTS['german_from']:
        return 'german'
    if width >= OPTS['contour_from']:
        return 'contour'
    return 'centre'


def centre_run(line, step=1.5):
    """running stitch along a line, equal stitches up to `step` long"""
    path = LineString(line)
    length = path.length
    n = max(1, math.ceil(length / step))
    return [path.interpolate(length * i / n).coords[0] for i in range(n + 1)]


def covered_area(columns):
    """area the zigzags cover (each triangle of consecutive needle points), grown by 0.15 mm"""
    triangles = []
    for points in columns:
        for a, b, c in zip(points, points[1:], points[2:]):
            triangle = Polygon([a, b, c])
            if triangle.area > 1e-4:
                triangles.append(triangle)
    return unary_union(triangles).buffer(0.15) if triangles else Polygon()


# ---------------------------------------------------------------- one letter

def _plan(poly, branch_lines, caps, graph, start, spacing, width, closes=None):
    """order + direction of the columns of one letter with as few cuts as possible.
    Rules: travel runs along the letter's centre line and never over satin already sewn
    (else: cut + jump); a column's satin always comes after its underlay.
    Returns [(points, (underlay start, underlay end), trim before?)]."""
    columns = [b for b in branch_lines if len(b) > 1]
    n = len(columns)
    nodes = list(graph.nodes)
    nearest_cache = {}

    def nearest_node(p):
        k = (round(p[0], 3), round(p[1], 3))
        if k not in nearest_cache:
            nearest_cache[k] = min(nodes, key=lambda q: math.dist(p, q))
        return nearest_cache[k]

    # by the drawn width: the pairs include the pull compensation (a 1.7 mm stroke would count as 2.4 mm)
    kinds = [underlay_kind(float(np.median([math.dist(l, r) for l, r in column_pairs(poly, c, spacing, width)] or [width]))
                           - 2 * OPTS['pull_mm']) for c in columns]
    satin_areas = [LineString(c).buffer(0.62 * width, cap_style=2) for c in columns]
    travel_cache = {}

    def travel(a, b):
        """path along the skeleton from a to b: None = no travel needed, 'none' = not connected"""
        k = (a, b)
        if k in travel_cache:
            return travel_cache[k]
        if math.dist(a, b) <= 0.4:
            result = None
        else:
            try:
                path = nx.shortest_path(graph, nearest_node(a), nearest_node(b), weight='weight')
                result = LineString(path).simplify(0.05) if len(path) > 1 else None
            except nx.NetworkXNoPath:
                result = 'none'
        travel_cache[k] = result
        return result

    def underlays(path, i):
        """the travel runs along (almost) all of column i: it is its underlay"""
        if path is None or path == 'none':
            return False
        c = LineString(columns[i])
        return c.difference(path.buffer(0.3)).length < 0.15 * c.length

    best = [None]

    def search(position, done, underlaid, cost, steps):
        """depth-first over column orders, cheapest first, cutting off what costs more than the best"""
        if best[0] is not None and cost >= best[0][0]:
            return
        if len(done) == n:
            best[0] = (cost, steps)
            return
        options = []
        for i in range(n):
            if i in done:
                continue
            for reverse in (False, True):
                c = columns[i][::-1] if reverse else columns[i]
                begin, finish = c[0], c[-1]
                if position is None:
                    path, trim, travel_length = None, False, 0
                else:
                    path = travel(position, begin)
                    if path == 'none':
                        trim, path, travel_length = True, None, 0
                    else:
                        travel_length = path.length if path is not None else math.dist(position, begin)
                        trim = path is not None and any(path.intersection(satin_areas[j]).length > 0.3 for j in done)
                        if trim:
                            path = None
                now_underlaid = set(underlaid)
                if path is not None:
                    for j in range(n):
                        if j not in done and underlays(path, j):
                            now_underlaid.add(j)
                if i in now_underlaid:
                    end, mode = finish, 'fwd'       # already underlaid on the way: satin straight on to the far end
                elif kinds[i] == 'contour':
                    end, mode = finish, 'contour'   # edge run out and back, satin out
                else:
                    end, mode = begin, 'back'       # (centre walk | contour + zigzag) out, satin back
                option_cost = cost + (TRIM_COST if trim else 0) + (0 if trim else travel_length) * 0.2
                options.append((option_cost, i, reverse, path, trim, mode, end, now_underlaid))
        options.sort(key=lambda x: x[0])
        for option_cost, i, reverse, path, trim, mode, end, now_underlaid in options:
            search(end, done | {i}, now_underlaid, option_cost, steps + [(i, reverse, path, trim, mode)])

    search(start, frozenset(), set(), 0.0, [])

    sequence = []
    first = True
    for i, reverse, path, trim, mode in best[0][1]:
        c = columns[i][::-1] if reverse else columns[i]
        cap0, cap1 = caps.get(id(columns[i]), (False, False))
        close0, close1 = (closes or {}).get(id(columns[i]), (True, True))
        if reverse:
            cap0, cap1 = cap1, cap0
            close0, close1 = close1, close0
        travel_points = centre_run(list(path.coords), 1.5) if path is not None else []
        pairs = column_pairs(poly, c, spacing, width=width, caps=(cap0, cap1))
        if mode == 'fwd':
            underlay = []
            satin = zig(pairs, spacing, (close0, close1))
        elif mode == 'contour':
            left, right = rails(pairs, width)
            underlay = centre_run(left, 1.5) + centre_run(right[::-1], 1.5)[1:]
            satin = zig(pairs, spacing, (close0, close1))
        elif kinds[i] == 'german':
            left, right = rails(pairs, width)
            underlay = centre_run(left, 1.5) + centre_run(right[::-1], 1.5)[1:]
            picks = list(range(0, len(pairs), max(1, int(2.0 / (spacing / 2))))) + [len(pairs) - 1]
            underlay += [(left if j % 2 == 0 else right)[k] for j, k in enumerate(picks)]   # low zigzag, 2 mm
            satin = zig(pairs[::-1], spacing, (close1, close0))
        else:
            underlay = centre_run(c, 1.5)
            satin = zig(pairs[::-1], spacing, (close1, close0))
        # the travel lies under later satin too: counted as underlay
        sequence.append((travel_points + underlay + satin, (0, len(travel_points) + len(underlay)), trim and not first))
        first = False
    return sequence


def letter(poly, start, spacing=0.4, fill=None):
    """stitch sequence for one letter (or any stroke shape): [(points, (underlay start, underlay end),
    trim before?)], each block continuous. fill(gap) -> blocks of a small tatami for gaps the columns
    don't reach."""
    width = 2 * poly.area / poly.length
    branch_list, graph = branches(poly, width)
    if graph is None:
        return [(branch_list[0][0], (0, 0), False)]
    caps = {id(b[0]): (b[1], b[2]) for b in branch_list}
    closes = {id(b[0]): (b[3], b[4]) for b in branch_list if len(b) > 4}
    lines = [b[0] for b in branch_list]

    def columns_from(position):
        return _plan(poly, lines, caps, graph, position, spacing, width, closes)

    def uncovered(sequence):
        covered = covered_area([block[under_end:] for block, (under_start, under_end), _ in sequence])
        rest = poly.buffer(-0.05).difference(covered)
        return [g for g in getattr(rest, 'geoms', [rest]) if g.geom_type == 'Polygon']

    sequence = columns_from(start)
    # a stroke ending against a slanted neighbour leaves a thin wedge too small for a fill (middle of M):
    # only those ends run on into the neighbour; wider gaps (apex of A) keep their small fill
    if fill is not None:
        thin = [g for g in uncovered(sequence) if g.area >= 0.02 and (g.area < 0.15 or g.buffer(-OPTS['gap_min'] / 2).is_empty)]
        ends = [(k, e) for k, e in graph.graph.get('jends', [])
                if any(g.distance(Point(branch_list[k][0][e])) < 0.4 * width for g in thin)]
        if ends:
            _reach(branch_list, ends, poly, width)
            sequence = columns_from(start)
    # gaps the columns don't reach (apex of A, corners of M): small fill, sewn first (under the satin)
    if fill is not None:
        gap_blocks = []
        for g in uncovered(sequence):
            if g.area < 0.15 or g.buffer(-OPTS['gap_min'] / 2).is_empty:
                continue
            gap_blocks += fill(g.buffer(0.1).intersection(poly))
        if gap_blocks:
            # nearest-neighbour order, travel along the skeleton between the pieces
            nodes = list(graph.nodes)

            def nearest_node(p):
                return min(nodes, key=lambda q: math.dist(p, q))

            ordered = []
            position = start
            while gap_blocks:
                i = min(range(len(gap_blocks)),
                        key=lambda k: math.dist(position, gap_blocks[k][0]) if position else gap_blocks[k][0][0] + gap_blocks[k][0][1])
                block = gap_blocks.pop(i)
                path = []
                if position is not None and math.dist(position, block[0]) > 0.4:
                    skeleton_path = nx.shortest_path(graph, nearest_node(position), nearest_node(block[0]), weight='weight')
                    if len(skeleton_path) > 1:
                        path = centre_run(list(LineString(skeleton_path).simplify(0.05).coords), 1.5)
                ordered.append((path + block, (0, len(path)), False))
                position = block[-1]
            # gap fills first (under the satin), then the columns, travelling on from the last fill
            sequence = ordered + columns_from(ordered[-1][0][-1])
    return sequence
