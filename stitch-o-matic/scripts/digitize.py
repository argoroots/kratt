"""Stitch generation: tatami fill, satin columns, running stitch and the other techniques -> a
pyembroidery pattern.

Units: mm inside, 0.1 mm in the pattern. The entry point is build(); DEFAULTS, FABRICS and THREADS
hold the settings.
"""
import math

import pyembroidery as pe
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import polylabel, unary_union

import satin as SAT
from design import knockout
from texts import TEXT


def polys(geometry):
    """the polygons of a Polygon or MultiPolygon (empty: none)"""
    if geometry.is_empty:
        return []
    return list(geometry.geoms) if isinstance(geometry, MultiPolygon) else [geometry]


# ---------------------------------------------------------------- tatami rows

# Settings of fill() that change with the technique calling it (set by build()):
FILL_OVERLAP = True      # each block runs one row on into its neighbour, so no gap is left where blocks meet
FILL_STAGGERS = 4        # rows before the needle-hole pattern repeats
ROW_COMPENSATION = 0.0   # pull compensation: rows are made this much longer at both ends


def row_segments(shape, y, x_min, x_max):
    """(x_start, x_end) of every piece of the horizontal line at y inside the shape, longer than 0.05 mm"""
    crossing = shape.intersection(LineString([(x_min - 1, y), (x_max + 1, y)]))
    pieces = crossing.geoms if hasattr(crossing, 'geoms') else [crossing]
    return [tuple(sorted([g.coords[0][0], g.coords[-1][0]])) for g in pieces if g.length > 0.05]


def fill(poly, angle, spacing, max_stitch):
    """Tatami (scan-line) fill: returns blocks, each a list of points in mm. A block is a run of rows
    that can be sewn back and forth without a jump."""
    angle = ((angle + 90) % 180) - 90   # rows at 135 deg = rows at -45 deg; keeps cos(angle) >= 0
    rotated = affinity.rotate(poly, -angle, origin=(0, 0), use_radians=False)
    min_x, min_y, max_x, max_y = rotated.bounds

    # rows: vertical step 'spacing' (multiple of 0.1 mm), intercepts on the 0.1 mm grid
    cos_angle = math.cos(math.radians(angle))
    on_grid = abs(cos_angle) >= 0.5          # top fills (10 deg, 45 deg); underlay keeps plain spacing
    if on_grid:
        spacing = max(1, round(spacing / 0.1)) * 0.1 * cos_angle       # whole 0.1 mm steps (else stripes)
        y = (math.floor(min_y / cos_angle / 0.1) + 1) * 0.1 * cos_angle
    else:
        y = min_y + spacing / 2
    rows = []
    while y < max_y:
        segments = sorted(row_segments(rotated, y, min_x, max_x))
        if ROW_COMPENSATION:
            segments = [(a - ROW_COMPENSATION, b + ROW_COMPENSATION) for a, b in segments]
        rows.append((y, segments))
        y += spacing

    # blocks: chains of overlapping segments in consecutive rows
    blocks = []
    open_blocks = []
    for y, segments in rows:
        still_open = []
        used = set()
        for block in open_blocks:
            _, (a, b) = block[-1]
            candidates = [i for i, (c, d) in enumerate(segments) if i not in used and c < b and d > a]
            if len(candidates) == 1:
                i = candidates[0]
                # continue only if this segment overlaps this block alone
                overlapping = sum(1 for other in open_blocks
                                  if other[-1][1][0] < segments[i][1] and other[-1][1][1] > segments[i][0])
                if overlapping == 1:
                    used.add(i)
                    block.append((y, segments[i]))
                    still_open.append(block)
                    continue
            blocks.append(block)
        for i, segment in enumerate(segments):
            if i not in used:
                still_open.append([(y, segment)])
        open_blocks = still_open
    blocks += open_blocks

    inside = rotated.buffer(ROW_COMPENSATION + 0.05)
    if FILL_OVERLAP:   # extend each block at its end by one row into the neighbouring area (a start row made a back-hop)
        for block in blocks:
            last_y, (a0, b0) = block[-1]
            next_y = last_y + spacing
            for s0, s1 in [(a - ROW_COMPENSATION, b + ROW_COMPENSATION) for a, b in row_segments(rotated, next_y, min_x, max_x)]:
                lo, hi = max(a0, s0), min(b0, s1)
                if hi - lo > 0.3:
                    block.append((next_y, (lo, hi)))
                    break

    result = []
    for block in blocks:
        points = []
        for k, (y, (a, b)) in enumerate(block):
            if points:   # start each row at the end nearest to where the previous row stopped
                ends = [a, b] if math.dist(points[-1], (a, y)) <= math.dist(points[-1], (b, y)) else [b, a]
            else:
                ends = [a, b] if k % 2 == 0 else [b, a]
            # needle points on a shared grid: every row uses x = (j + phase) * max_stitch, the phase
            # steps by 1/FILL_STAGGERS from row to row, so the needle holes form even diagonal lines
            phase = (round(y / spacing) % FILL_STAGGERS) / FILL_STAGGERS
            j0, j1 = math.ceil(a / max_stitch - phase), math.floor(b / max_stitch - phase)
            inner = [(j + phase) * max_stitch for j in range(j0, j1 + 1)]
            inner = [x for x in inner if a + 0.4 < x < b - 0.4]
            row = [ends[0]] + (inner if ends[1] > ends[0] else inner[::-1]) + [ends[1]]
            if points and math.dist(points[-1], (row[0], y)) > 1.0:
                hop = LineString([points[-1], (row[0], y)])
                if not inside.contains(hop):          # a straight hop would leave the shape: go along the edge
                    path = travel_path(points[-1], (row[0], y), inside)
                    if len(path) > 1 and LineString(path).length < 4 * hop.length + 2:
                        points += path[1:-1]
                else:                                 # long hop inside the shape: stitches <= max_stitch
                    n = math.ceil(hop.length / max_stitch)
                    points += [(points[-1][0] + (row[0] - points[-1][0]) * i / n, points[-1][1] + (y - points[-1][1]) * i / n)
                               for i in range(1, n)]
            points += [(x, y) for x in row]
        result.append([snap_to_grid(rotate_back(p, angle), angle) if on_row and on_grid else rotate_back(p, angle)
                       for p, on_row in zip(points, on_row_flags(points, block))])
    return result


def on_row_flags(points, block):
    """True for points that lie on one of the block's rows (not on a hop between rows)"""
    row_ys = set(round(y, 9) for y, _ in block)
    return [round(p[1], 9) in row_ys for p in points]


def snap_to_grid(point, angle):
    """put a row point on the 0.1 mm grid, keeping it on its row line"""
    x, y = point
    if abs(angle % 180) < 1e-9:
        return (round(x, 1), round(y, 1))
    slope = math.tan(math.radians(angle))
    intercept = round((y - x * slope) / 0.1) * 0.1          # row intercept (already on the grid)
    x_rounded = round(x, 1)
    return (x_rounded, round(intercept + x_rounded * slope, 1))


def rotate_back(point, angle):
    a = math.radians(angle)
    x, y = point
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def travel_path(start, end, poly):
    """points from start to end running along the inside of poly's boundary (the shorter way round)"""
    inner = poly.buffer(-0.25, join_style=2)
    if inner.is_empty:
        return [end]
    best = None
    for part in polys(inner):
        for ring in [part.exterior] + list(part.interiors):
            score = ring.distance(Point(start)) + ring.distance(Point(end))
            if best is None or score < best[0]:
                best = (score, ring)
    ring = best[1]
    length = ring.length
    at_start, at_end = ring.project(Point(start)), ring.project(Point(end))
    forward = (at_end - at_start) % length
    backward = (at_start - at_end) % length
    if forward <= backward:
        n = max(1, math.ceil(forward / 1.0))
        distances = [at_start + forward * i / n for i in range(n + 1)]
    else:
        n = max(1, math.ceil(backward / 1.0))
        distances = [at_start - backward * i / n for i in range(n + 1)]
    return [ring.interpolate(d % length).coords[0] for d in distances] + [end]


def even_run(points, step, tolerance=0.1):
    """running stitch along a path: stitches up to `step` long, shorter where the path bends so that
    no stitch strays more than `tolerance` mm from the path; on straight paths all stitches are equal"""
    path = LineString(points)
    length = path.length
    if length < 1e-6:
        return [tuple(points[0])]
    dense = [path.interpolate(min(length, i * 0.05)).coords[0] for i in range(int(length / 0.05) + 2)]
    result = [dense[0]]
    i = 0
    while i < len(dense) - 1:
        j = i + 1
        while j + 1 < len(dense) and math.dist(dense[i], dense[j + 1]) <= step:
            stitch = LineString([dense[i], dense[j + 1]])
            if max(stitch.distance(Point(q)) for q in dense[i + 1:j + 1]) > tolerance:
                break
            j += 1
        result.append(dense[j])
        i = j
    # a straight path (the stitches cover its whole length): spread the stitches evenly
    if len(result) > 2 and LineString(result).length > 0.999 * length:
        n = len(result) - 1
        result = [path.interpolate(length * k / n).coords[0] for k in range(n + 1)]
    return result


def ordered_fill(poly, angle, spacing, max_stitch, start, top_down=False):
    """fill() blocks in sewing order: top_down = each block from its top, blocks by their top edge;
    else each next block is the one starting (either end) nearest to where the last one ended"""
    blocks = fill(poly, angle, spacing, max_stitch)
    if top_down:
        blocks = [b if b[0][1] <= b[-1][1] else b[::-1] for b in blocks]
        return sorted(blocks, key=lambda b: b[0][1])
    result = []
    position = start
    while blocks:
        best = None
        for i, block in enumerate(blocks):
            for reverse in (False, True):
                first = block[-1] if reverse else block[0]
                distance = math.dist(position, first) if position else 0
                if best is None or distance < best[0]:
                    best = (distance, i, reverse)
        _, i, reverse = best
        block = blocks.pop(i)
        if reverse:
            block = block[::-1]
        result.append(block)
        position = block[-1]
    return result


# ---------------------------------------------------------------- settings

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

# what a plan may set per shape: stitch type, underlay (satin: centre / contour / german / none) and any DEFAULTS key
PLAN_KEYS = set(DEFAULTS) | {'stitch', 'underlay'}
FILL_STITCHES = ('satin', 'tatami', 'contour', 'applique', 'cross')   # plan "stitch" values for shapes

# thread weight: 40 wt is the normal embroidery thread (all settings above are for it). 60 wt is
# thinner (about 0.25 mm): for small text (< 4-5 mm) and fine detail, with a 65/9 needle. Settings
# scale from the fabric's 40 wt values; `thread_mm` is the drawn width in the coverage check.
THREADS = {
    40: dict(scale=dict(), thread_mm=0.35),
    60: dict(scale=dict(satin_spacing=0.7, fill_spacing=0.75, satin_min=0.6, satin_widen_max=0.6, comp=0.7, run_step=0.75), thread_mm=0.25),
}

# starting points per fabric (KNOWLEDGE.md, section 8); everything else stays at DEFAULTS
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


def thread_cfg(cfg, weight):
    """settings for a thread weight, starting from cfg (fabric + user settings)"""
    thread = THREADS[int(weight)]
    merged = dict(DEFAULTS, **cfg)
    result = dict(cfg)
    for key, factor in thread['scale'].items():
        result[key] = round(float(merged[key]) * factor, 3)
    result['thread_mm'] = thread['thread_mm']
    return result


# ---------------------------------------------------------------- satin or tatami

def stroke_like(part, cfg):
    """satin fits a part that is a stroke: narrow on average and nowhere much wider than that"""
    average_width = 2 * part.area / part.length
    if average_width > cfg['satin_max']:
        return False
    centre = polylabel(part, 0.01)
    widest = 2 * min([part.exterior.distance(centre)] + [r.distance(centre) for r in part.interiors])
    # nowhere much wider than its average, and nowhere wider than 1.5 x satin_max (the wide bar of a comb)
    return widest <= cfg['satin_blob'] * average_width and widest <= 1.5 * cfg['satin_max']


def suggest(shape, cfg=None):
    """measured hints for the plan (shape in mm at the largest size): what the rules pick and which
    other technique is worth offering, with the reason. Hints only: the person decides (KNOWLEDGE 10).
    Returns (rule, [(technique, reason)])."""
    cfg = cfg or DEFAULTS
    if shape.is_empty or shape.area <= 0:
        return 'run', []
    average_width = 2 * shape.area / shape.length
    rule = 'satin' if all(stroke_like(part, cfg) for part in polys(shape)) else 'tatami'
    hints = []
    if rule == 'tatami':
        parts = list(shape.geoms) if hasattr(shape, 'geoms') else [shape]
        roundness = max(4 * math.pi * part.area / part.length ** 2 for part in parts)
        edges = []
        for part in parts:
            ring = list(part.simplify(0.05).exterior.coords)
            edges += [(ring[i], ring[i + 1]) for i in range(len(ring) - 1)]

        def turn(i):
            (a0, a1), (b0, b1) = edges[i - 1], edges[i]
            u = math.atan2(a1[1] - a0[1], a1[0] - a0[0])
            v = math.atan2(b1[1] - b0[1], b1[0] - b0[0])
            return abs((math.degrees(v - u) + 180) % 360 - 180)

        sharp_corners = sum(1 for i in range(len(edges)) if turn(i) > 40)
        axis_parallel = all(min(abs(a[0] - b[0]), abs(a[1] - b[1])) < 0.05 for a, b in edges)
        stepped = axis_parallel and len(edges) >= 8
        if stepped:
            hints.append(('cross', 'only horizontal and vertical edges, stepped like a grid: cross stitch, if it is a folk or grid pattern'))
        elif roundness >= 0.8 and sharp_corners == 0:
            hints.append(('contour', f'round (roundness {roundness:.2f}, no sharp corners): contour fill looks domed and pulls evenly'))
        if shape.area >= 1500:
            hints.append(('applique', f'large area ({shape.area / 100:.0f} cm²): appliqué is softer, faster and fewer stitches (~{shape.area * 6 / 1000:.0f}k as tatami)'))
        if average_width >= 6 and not stepped:
            hints.append(('fill_border', 'wide fill: a satin border (2–3 mm) makes the edge sharp, if the edge matters in the design'))
    return rule, hints


# ---------------------------------------------------------------- the pattern

def satin_options(cfg):
    """satin.py settings from a configuration"""
    inset = cfg['satin_short_inset']
    return dict(pull_mm=float(cfg['comp']), stretch=float(cfg['comp_stretch']), stretch_angle=float(cfg['stretch_angle']),
                pull_pct=float(cfg['satin_pull_pct']), push_mm=float(cfg['satin_push']),
                short_dist=float(cfg['satin_short']), split_len=float(cfg['satin_split']), mitre_max=float(cfg['satin_mitre']),
                reach=float(cfg['satin_reach']), gap_min=float(cfg['satin_gap']), min_width=float(cfg['satin_min']),
                max_widen=float(cfg['satin_widen_max']),
                contour_from=float(cfg['satin_contour_from']), german_from=float(cfg['satin_german_from']),
                short_inset=tuple(inset) if isinstance(inset, (list, tuple)) else (float(inset),),
                hairpin=cfg['satin_hairpin'], underlay=cfg.get('underlay'))


def start_on_side(ring, near, min_side):
    """rotate a closed ring to start in the middle of a straight side (not on a corner), the side
    nearest to `near`; sides shorter than min_side are skipped when possible"""
    sides = [(k, math.dist(ring[k], ring[k + 1])) for k in range(len(ring) - 1)]
    long_sides = [k for k, length in sides if length >= min_side] or [max(sides, key=lambda t: t[1])[0]]

    def middle(k):
        return ((ring[k][0] + ring[k + 1][0]) / 2, (ring[k][1] + ring[k + 1][1]) / 2)

    k = min(long_sides, key=lambda k: math.dist(near, middle(k))) if near else long_sides[0]
    mid = middle(k)
    return [mid] + ring[k + 1:-1] + ring[:k + 1] + [mid]


class PatternBuilder:
    """Sews the techniques into one pyembroidery pattern. Keeps the needle position, the underlay
    points, the stitch types used and the machine stops."""

    def __init__(self, cfg, grid_origin):
        self.cfg = cfg
        self.grid_origin = grid_origin            # cross stitch grid origin: the design's top left corner
        self.pattern = pe.EmbPattern()
        self.position = None                      # where the needle is (mm), None after a colour change
        self.previous = None                      # the point before it (for the tie-off direction)
        self.underlay = []                        # underlay points (mm)
        self.kinds = set()                        # stitch types used
        self.stops = []                           # machine stops inside a colour (appliqué), in order
        self.colour = None                        # current thread colour
        self.satin_cache = []                     # identical shapes get identical stitches

    # -------------------------------------------------- low level

    def stitch_block(self, points, connect=False, under=None, force_trim=False):
        """sew points in order. connect: go on from the needle position (else jump, with a trim when far,
        and a tie-in). under=(i, j): points i..j-1 are underlay. Stitches longer than 7 mm are split."""
        if not points:
            return
        if under is not None and connect and self.position is not None:
            under = (under[0] + 1, under[1] + 1)
        if under is not None:
            sewn = list(([self.position] + list(points)) if connect and self.position is not None else points)
            self.underlay.extend(sewn[under[0]:under[1]])
        if connect and self.position is not None:
            points = [self.position] + list(points)
        x0, y0 = points[0]
        far = self.position is not None and (math.dist(self.position, (x0, y0)) > self.cfg['trim'] or force_trim)
        if far:
            self.pattern.add_command(pe.TRIM)
        if self.position is None or far:
            self.pattern.add_stitch_absolute(pe.JUMP, x0 * 10, y0 * 10)
            if len(points) > 1:   # tie-in along the first stitch
                x1, y1 = points[1]
                d = math.dist((x0, y0), (x1, y1)) or 1
                tie = min(0.7, d * 0.9)
                ux, uy = (x1 - x0) / d * tie, (y1 - y0) / d * tie
                for (a, b) in [(x0 + ux, y0 + uy), (x0, y0), (x0 + ux, y0 + uy), (x0, y0)]:
                    self.pattern.add_stitch_absolute(pe.STITCH, a * 10, b * 10)
        last = (x0, y0)
        for index, (x, y) in enumerate(points[1:], start=1):
            n = max(1, math.ceil(math.dist(last, (x, y)) / 7.0))
            for j in range(1, n + 1):
                self.pattern.add_stitch_absolute(pe.STITCH, (last[0] + (x - last[0]) * j / n) * 10, (last[1] + (y - last[1]) * j / n) * 10)
                if under is not None and under[0] < index < under[1] and j < n:
                    self.underlay.append((last[0] + (x - last[0]) * j / n, last[1] + (y - last[1]) * j / n))
            if math.dist(last, (x, y)) > 0.05:
                self.previous = last
            last = (x, y)
        self.position = last

    def tie_off(self):
        """lock stitches back along the last stitch, so they stay inside the shape"""
        if self.position is None:
            return
        x, y = self.position
        px, py = self.previous if self.previous else (x - 1, y)
        d = math.dist((x, y), (px, py)) or 1
        length = min(0.5, d * 0.8)
        ux, uy = (px - x) / d * length, (py - y) / d * length
        for (a, b) in [(x + ux, y + uy), (x, y), (x + ux, y + uy), (x, y)]:
            self.pattern.add_stitch_absolute(pe.STITCH, a * 10, b * 10)

    def run(self, points, passes, step):
        """running stitch: `passes` times along the path, back and forth"""
        forward = even_run(points, step, self.cfg['run_tol'])
        sequence = forward
        for k in range(1, passes):
            sequence = sequence + (forward[::-1] if k % 2 else forward)[1:]
        return sequence

    def connects(self, first_point, first, cfg):
        """go on without a trim: not the first ring of the shape, and the next start is near"""
        return not first and self.position is not None and math.dist(self.position, first_point) <= cfg['trim']

    def edge_underlay(self, poly):
        for part in polys(poly.buffer(-0.35)):
            points = self.run(list(part.exterior.coords), 1, 2.0)
            self.stitch_block(points, under=(0, len(points)))

    def new_colour(self, colour, name):
        if self.colour is not None:
            self.pattern.add_command(pe.TRIM)
            self.pattern.add_command(pe.COLOR_CHANGE)
            self.position = None
        self.pattern.add_thread({'color': int(colour[1:], 16), 'name': name})
        self.colour = colour

    def stop(self, label):
        """machine stop (a colour change to the same thread) with a note for the person at the machine"""
        self.tie_off()
        self.pattern.add_command(pe.TRIM)
        self.pattern.add_command(pe.COLOR_CHANGE)
        self.position = None
        self.pattern.add_thread({'color': int(self.colour[1:], 16), 'name': label})
        self.stops.append(label)

    # -------------------------------------------------- techniques

    def running(self, line, cfg):
        self.stitch_block(self.run(list(line.coords), cfg['run_passes'], cfg['run_step']))
        self.tie_off()

    def tatami(self, poly, cfg):
        """edge underlay, cross underlay, then the top rows from the top down; outline and border if asked"""
        global FILL_OVERLAP, ROW_COMPENSATION
        FILL_OVERLAP = True
        full = poly
        if cfg['fill_border'] > 0:                       # the fill goes 0.3 mm under the border
            poly = poly.buffer(-(cfg['fill_border'] - 0.3), join_style=2)
            tips = self.border_unreachable_tips(full, cfg['fill_border'] / 2)
            if tips:
                poly = unary_union([poly] + tips)
            if poly.is_empty:
                poly = full
        self.edge_underlay(poly)
        for part in (polys(poly.buffer(-0.4)) if cfg['fill_under_spacing'] > 0 else []):   # cross underlay
            for block in ordered_fill(part, cfg['fill_angle'] + 90, cfg['fill_under_spacing'], cfg['fill_maxlen'], self.position):
                if self.position is not None and math.dist(self.position, block[0]) > 0.6:
                    block = travel_path(self.position, block[0], poly)[1:-1] + block
                self.stitch_block(block, connect=True, under=(0, len(block)))
        # top rows only: longer at both ends, by the compensation along the rows' direction
        SAT.OPTS.update(pull_mm=float(cfg['comp']), stretch=float(cfg['comp_stretch']), stretch_angle=float(cfg['stretch_angle']))
        ROW_COMPENSATION = SAT.pull_for(math.cos(math.radians(cfg['fill_angle'])), math.sin(math.radians(cfg['fill_angle'])))
        top = ordered_fill(poly, cfg['fill_angle'], cfg['fill_spacing'], cfg['fill_maxlen'], self.position, top_down=True)
        ROW_COMPENSATION = 0.0
        for k, block in enumerate(top):
            if k > 0 and math.dist(self.position, block[0]) > 0.6:   # each part from its top
                self.tie_off()
                self.stitch_block(block)
            else:
                self.stitch_block(block, connect=k > 0)
        self.tie_off()
        if cfg['fill_outline'] > 0:
            self.outline(full, cfg)
        if cfg['fill_border'] > 0:
            self.border(full, cfg)

    @staticmethod
    def border_unreachable_tips(shape, half_width):
        """sharp tips (< 60 deg): the border's corner stitch may be at most twice the column's half
        width, so it stops short of the tip; the fill runs out to the tip there instead"""
        tips = []
        for part in polys(shape):
            corners = list(part.exterior.coords)[:-1]
            for i, v in enumerate(corners):
                a, b = corners[i - 1], corners[(i + 1) % len(corners)]
                u1 = (a[0] - v[0], a[1] - v[1])
                u2 = (b[0] - v[0], b[1] - v[1])
                l1, l2 = math.hypot(*u1), math.hypot(*u2)
                if l1 < 1e-6 or l2 < 1e-6:
                    continue
                opening = math.acos(max(-1, min(1, (u1[0] * u2[0] + u1[1] * u2[1]) / l1 / l2)))
                inward = Point(v[0] + (u1[0] / l1 + u2[0] / l2) * 0.1, v[1] + (u1[1] / l1 + u2[1] / l2) * 0.1)
                if opening < math.radians(60) and part.buffer(-0.05).contains(inward):
                    radius = half_width / math.sin(opening / 2) - 2 * half_width + 0.4   # part of the tip the border cannot reach
                    tips.append(part.intersection(Point(v).buffer(radius)))
        return tips

    def outline(self, poly, cfg):
        """running stitch round every edge of the shape, each ring starting next to where the last one ended"""
        rings = [r for part in polys(poly) for r in [part.exterior] + list(part.interiors) if r.length > 1.0]
        while rings:
            rings.sort(key=lambda r: r.distance(Point(self.position)) if self.position else 0)
            ring = rings.pop(0)
            line = start_on_side(list(ring.coords), self.position, 1.0)
            points = self.run(line, int(cfg['fill_outline']), 2.0)
            near = self.position is not None and math.dist(self.position, points[0]) <= cfg['trim']
            if not near and self.position is not None:
                self.tie_off()
            self.stitch_block(points, connect=near)
        self.tie_off()
        self.kinds.add('outline')

    def border(self, poly, cfg, width=None):
        """satin border along every outline ring: outer edge = outline + comp, inner edge `width` inside"""
        width = width or cfg['fill_border']
        self.kinds.add('border')
        SAT.OPTS.update(satin_options(cfg))
        saved = SAT.OPTS['mitre_max']
        SAT.OPTS['mitre_max'] = 135.0             # a ring turns every corner
        try:
            for part in polys(poly):
                for k, ring in enumerate([part.exterior] + list(part.interiors)):
                    ring_area = Polygon(ring)
                    # round join: at an inward corner (heart notch) the centre line arcs round the corner
                    # instead of a mitre spike; outward corners (rectangle) stay sharp either way
                    middle = ring_area.buffer(-width / 2, join_style=1) if k == 0 else ring_area.buffer(width / 2, join_style=1)
                    for centre in polys(middle):
                        line = start_on_side(list(centre.exterior.coords), self.position, 3 * width)
                        band = LineString(line).buffer(width / 2 + 0.01, cap_style=2, join_style=2)
                        pairs = SAT.column_pairs(band, line, cfg['satin_spacing'], width=width, caps=(False, False))
                        if not pairs:
                            continue
                        underlay = self.run(line, 1, 2.0)
                        self.stitch_block(underlay + SAT.zig(pairs, cfg['satin_spacing']), under=(0, len(underlay)))
                        self.tie_off()
        finally:
            SAT.OPTS['mitre_max'] = saved

    def contour(self, poly, cfg):
        """contour fill: rows follow the outline inwards (rounded shapes look domed, pull is even).
        While the shape stays one piece without holes the rows form one spiral (no seam of hops); a band
        with one hole is two spirals (from the outer edge in, then from the middle out to the hole);
        otherwise each ring is sewn on its own, starting next to where the last one ended."""
        spacing = cfg['fill_spacing']
        self.edge_underlay(poly)
        levels = []                                  # the shape shrunk by one row spacing at a time
        k = 0
        while k < 2000:
            offset = spacing / 2 + k * spacing - cfg['comp']
            inner = poly.buffer(-offset, join_style=1) if offset > 0 else poly.buffer(-offset, join_style=2)
            if inner.is_empty:
                break
            levels.append(polys(inner))
            k += 1

        def simple(level):
            return len(level) == 1 and not list(level[0].interiors)

        def annulus(level):
            return len(level) == 1 and len(level[0].interiors) == 1

        first = True
        i = 0
        while i < len(levels):
            if simple(levels[i]):
                j = i
                while j + 1 < len(levels) and simple(levels[j + 1]):
                    j += 1
                points = self.spiral([levels[t][0].exterior for t in range(i, j + 1)], self.position, cfg['fill_maxlen'])
                self.stitch_block(points, connect=self.connects(points[0], first, cfg))
                first = False
                i = j + 1
                continue
            # a ring-shaped band (one piece, one hole): the rows from the outer edge and the rows around the
            # hole are two concentric families; each is sewn as one spiral (no seam where a ring would start)
            if annulus(levels[i]):
                j = i
                while j + 1 < len(levels) and annulus(levels[j + 1]):
                    j += 1
                if j > i:
                    outer_rings = [levels[t][0].exterior for t in range(i, j + 1)]
                    inner_rings = [levels[t][0].interiors[0] for t in range(j, i - 1, -1)]   # from the middle out to the hole
                    for family in (outer_rings, inner_rings):
                        points = self.spiral(family, self.position, cfg['fill_maxlen'])
                        self.stitch_block(points, connect=self.connects(points[0], first, cfg))
                        first = False
                    i = j + 1
                    continue
            rings = [r for part in levels[i] for r in [part.exterior] + list(part.interiors) if r.length > 0.6]
            rings.sort(key=lambda r: r.distance(Point(self.position)) if self.position else 0)
            for ring in rings:
                line = start_on_side(list(ring.coords), self.position, 0)
                points = self.run(line, 1, cfg['fill_maxlen'])
                self.stitch_block(points, connect=self.connects(points[0], first, cfg))
                first = False
            i += 1
        if levels:
            self.contour_middle(levels, spacing, cfg)
        self.tie_off()
        if cfg['fill_outline'] > 0:
            self.outline(poly, cfg)
        if cfg['fill_border'] > 0:
            self.border(poly, cfg)

    def contour_middle(self, levels, spacing, cfg):
        """the last ring leaves an opening up to one row spacing wide (an ellipse leaves a slot along its
        long axis); a running stitch down the middle of that opening closes it"""
        for part in levels[-1]:
            if list(part.interiors):
                continue                                    # a ring (shape with a hole) ends in a ring, no middle
            core = part.buffer(-spacing / 2)
            if core.is_empty:
                core = part
            corners = list(core.minimum_rotated_rectangle.exterior.coords)[:4]
            side1 = (corners[0], corners[1])
            side2 = (corners[1], corners[2])
            long_side, short_side = (side1, side2) if math.dist(*side1) >= math.dist(*side2) else (side2, side1)
            half = ((short_side[1][0] - short_side[0][0]) / 2, (short_side[1][1] - short_side[0][1]) / 2)
            a = (long_side[0][0] + half[0], long_side[0][1] + half[1])
            b = (long_side[1][0] + half[0], long_side[1][1] + half[1])
            # run on along the axis to where the rings' pointed ends still stand apart (3 rings out)
            outer = [g for g in levels[max(0, len(levels) - 4)] if g.intersects(part)]
            reach = outer[0].buffer(-spacing / 2) if outer else part
            extend = 0.5 * max(reach.bounds[2] - reach.bounds[0], reach.bounds[3] - reach.bounds[1])
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy) or 1
            a = (a[0] - dx / length * extend, a[1] - dy / length * extend)
            b = (b[0] + dx / length * extend, b[1] + dy / length * extend)
            middle = LineString([a, b]).intersection(reach if not reach.is_empty else part)
            if middle.is_empty or middle.length < 0.3:
                continue
            longest = max(getattr(middle, 'geoms', [middle]), key=lambda g: g.length)
            points = list(longest.coords)
            if self.position is not None and math.dist(self.position, points[-1]) < math.dist(self.position, points[0]):
                points = points[::-1]
            near = self.position is not None and math.dist(self.position, points[0]) <= cfg['trim']
            self.stitch_block(self.run(points, 1, cfg['fill_maxlen'] / 2), connect=near)

    def spiral(self, rings, near, step):
        """one continuous path from the outer ring inwards: along ring k the path drifts to ring k+1.
        The first ring is sewn once in full before the drift starts, otherwise the edge just behind the
        start would be one row spacing short (a thin wedge of bare fabric)."""
        if len(rings) > 1:
            rings = [rings[0]] + list(rings)
        path = []
        start = Point(near) if near else Point(rings[0].coords[0])
        for k, ring in enumerate(rings):
            following = rings[k + 1] if k + 1 < len(rings) else None
            length = ring.length
            at = ring.project(start)
            n = max(8, int(length / 0.5))
            if following is not None:
                following_at = following.project(Point(ring.interpolate(at).coords[0]))
                following_length = following.length
            for m in range(n):
                share = m / n
                a = ring.interpolate((at + share * length) % length).coords[0]
                if following is not None:
                    b = following.interpolate((following_at + share * following_length) % following_length).coords[0]
                    path.append((a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share))
                else:
                    path.append(a)
            if following is not None:
                start = Point(following.interpolate(following_at).coords[0])
            else:
                path.append(ring.interpolate(at).coords[0])
        return even_run(path, step, self.cfg['run_tol'])

    def applique(self, poly, cfg):
        """appliqué: placement line, stop (lay the fabric), tack-down, stop (cut the fabric), satin cover"""
        for part in polys(poly):
            for ring in [part.exterior] + list(part.interiors):
                self.stitch_block(self.run(list(ring.coords), 1, 2.0))
                self.tie_off()
        self.stop(TEXT['stop_applique_place'])
        for part in polys(poly.buffer(-0.5, join_style=2)):
            for ring in [part.exterior] + list(part.interiors):
                self.stitch_block(self.run(list(ring.coords), 1, 1.5))
                self.tie_off()
        self.stop(TEXT['stop_applique_cut'])
        self.border(poly, cfg, cfg['applique_border'])

    def cross(self, poly, cfg):
        """cross stitch on a grid: '/' under '\\', travel only along the diagonals (hidden)"""
        size = cfg['cross_size']
        origin_x, origin_y = self.grid_origin
        x0, y0, x1, y1 = poly.bounds
        rows = []
        for j in range(int((y0 - origin_y) // size), int((y1 - origin_y) // size) + 1):
            row = []
            for i in range(int((x0 - origin_x) // size), int((x1 - origin_x) // size) + 1):
                cx, cy = origin_x + i * size, origin_y + j * size
                cell = Polygon([(cx, cy), (cx + size, cy), (cx + size, cy + size), (cx, cy + size)])
                if poly.intersection(cell).area >= 0.5 * size * size:
                    row.append((i, j))
            rows.append(row if (j % 2 == 0) else row[::-1])            # rows back and forth

        def corner(i, j, u, v):
            return (origin_x + (i + u) * size, origin_y + (j + v) * size)

        block = []
        previous = None
        for (i, j) in [cell for row in rows for cell in row]:
            centre = corner(i, j, 0.5, 0.5)
            if previous is not None and abs(previous[0] - i) <= 1 and abs(previous[1] - j) <= 1 and previous != (i, j):
                # go from the previous centre over a shared corner into this centre (both on diagonals)
                pi, pj = previous
                shared = [corner(pi, pj, u, v) for u in (0, 1) for v in (0, 1)
                          if abs(pi + u - i - 0.5) <= 0.5 + 1e-9 and abs(pj + v - j - 0.5) <= 0.5 + 1e-9]
                block.append(shared[0])
            elif block:
                self.stitch_block(block)
                self.tie_off()
                block = []
            block += [centre, corner(i, j, 0, 1), corner(i, j, 1, 0), centre, corner(i, j, 0, 0), corner(i, j, 1, 1), centre]
            previous = (i, j)
        if block:
            self.stitch_block(block)
            self.tie_off()

    def satin_sequence(self, poly, cfg):
        """satin.letter() blocks for a shape, from the cache when an identical shape was done already"""
        global FILL_OVERLAP
        FILL_OVERLAP = False
        ox, oy = math.floor(poly.bounds[0] * 10) / 10, math.floor(poly.bounds[1] * 10) / 10
        moved = affinity.translate(poly, -ox, -oy)
        key = tuple(sorted((k, str(v)) for k, v in cfg.items()))
        for shape, cached_key, sequence in self.satin_cache:
            if cached_key == key and shape.symmetric_difference(moved).area < 0.02 * moved.area:
                break
        else:
            def gap_fill(gap):
                return [block for part in polys(gap) for block in fill(part, 45, 0.4, 3.5)]
            sequence = SAT.letter(moved, None, cfg['satin_spacing'], fill=gap_fill)
            sequence = [([(round(x, 1), round(y, 1)) for x, y in block], under, jump) for block, under, jump in sequence]
            self.satin_cache.append((moved, key, sequence))
        return [([(x + ox, y + oy) for x, y in block], under, jump) for block, under, jump in sequence]

    def satin(self, poly, cfg):
        SAT.OPTS.update(satin_options(cfg))
        for k, (block, under, jump) in enumerate(self.satin_sequence(poly, cfg)):
            if k > 0 and jump:
                self.tie_off()
                self.stitch_block(block, under=under, force_trim=True)
            else:
                self.stitch_block(block, connect=k > 0, under=under)
        self.tie_off()
        if cfg['fill_outline'] > 0:
            self.outline(poly, cfg)        # running stitch along the satin's edge, if asked

    def sew(self, kind, geometry, cfg):
        self.kinds.add(kind)
        technique = {'run': self.running, 'tatami': self.tatami, 'contour': self.contour,
                     'applique': self.applique, 'cross': self.cross}.get(kind, self.satin)
        technique(geometry, cfg)


def reading_order(items):
    """consecutive satin pieces (text) in reading order: rows by vertical position, then left to right;
    everything else keeps its place"""
    result = []
    i = 0
    while i < len(items):
        if items[i][0] != 'satin':
            result.append(items[i])
            i += 1
            continue
        j = i
        while j < len(items) and items[j][0] == 'satin':
            j += 1
        group = items[i:j]
        heights = sorted(item[1].bounds[3] - item[1].bounds[1] for item in group)
        tolerance = 0.6 * heights[len(heights) // 2]
        rows = []
        for item in sorted(group, key=lambda t: (t[1].bounds[1] + t[1].bounds[3]) / 2):
            y_centre = (item[1].bounds[1] + item[1].bounds[3]) / 2
            if rows and abs(y_centre - rows[-1][0]) <= tolerance:
                rows[-1][1].append(item)
            else:
                rows.append([y_centre, [item]])
        for _, row in rows:
            result += sorted(row, key=lambda t: t[1].bounds[0])
        i = j
    return result


def clean_stitches(stitches):
    """drop duplicates and stitches < 0.15 mm, keep the last stitch before any command"""
    cleaned = []
    last = None
    for i, (x, y, command) in enumerate(stitches):
        if (command & pe.COMMAND_MASK) == pe.STITCH:
            before_command = i + 1 >= len(stitches) or (stitches[i + 1][2] & pe.COMMAND_MASK) != pe.STITCH
            if last is not None and math.dist(last, (x, y)) < 1.5 and not before_command:
                continue
            if (last is not None and math.dist(last, (x, y)) < 5.0 and before_command and cleaned
                    and (cleaned[-1][2] & pe.COMMAND_MASK) == pe.STITCH):
                cleaned[-1] = [x, y, command]
                last = (x, y)
                continue
            cleaned.append([x, y, command])
            last = (x, y)
        else:
            cleaned.append([x, y, command])
            if (command & pe.COMMAND_MASK) == pe.JUMP:
                last = (x, y)
    return cleaned


def build(elements, size_mm, threads, cfg=None, ref_size=None, plan=None, scale=None, ref_scale=None):
    """elements: design.load() output (SVG units, sewing order); size_mm: longer side;
    threads: {'#rrggbb': 'name'}; ref_size: size used to choose satin or tatami for each shape
    (the largest size, so every size is stitched the same way).
    plan: digitizing decisions per shape (numbers as in swatch.py --list), see PLAN_KEYS:
      {"shapes": {"5": {"stitch": "satin", "satin_spacing": 0.35, "underlay": "contour"}, ...},
       "order": [30, 0, 1, ...]}   (order inside each colour; shapes not listed follow in the usual order)
    Returns a centred pattern with .underlay (points, 0.1 mm), .shapes, .kinds, .stops, .scale_mm,
    .offset, .comp and .thread_mm."""
    global FILL_STAGGERS
    cfg = dict(DEFAULTS, **(cfg or {}))
    FILL_STAGGERS = max(1, int(cfg['fill_staggers']))
    SAT.OPTS.update(satin_options(cfg))

    # scale so the longer side of the whole design = size_mm
    everything = unary_union([e['geom'] if e['kind'] == 'fill' else e['geom'].buffer(e.get('width', 0) / 2) for e in elements])
    x0, y0, x1, y1 = everything.bounds
    mm_per_unit = scale or size_mm / max(x1 - x0, y1 - y0)                    # scale: fixed, for single shapes
    reference_scale = ref_scale or (ref_size or size_mm) / max(x1 - x0, y1 - y0)
    shape_plans = {int(k): v for k, v in ((plan or {}).get('shapes') or {}).items()}
    unknown = [k for v in shape_plans.values() for k in v if k not in PLAN_KEYS]
    if unknown:
        raise ValueError(f'unknown plan keys: {unknown}; allowed: {sorted(PLAN_KEYS)}')

    # every element in mm with its stitch type
    shapes = []
    for index, element in enumerate(elements):
        geometry = affinity.scale(element['geom'], mm_per_unit, mm_per_unit, origin=(0, 0))
        element = dict(element, geom=geometry, id=index, cfg=shape_plans.get(index, {}))
        if element['kind'] == 'run' and element.get('width', 0) * mm_per_unit >= cfg['stroke_as_fill']:
            element = dict(element, kind='fill', geom=geometry.buffer(element['width'] * mm_per_unit / 2, cap_style=2, join_style=2))
        if element['kind'] == 'fill':   # satin or tatami, decided at the reference size
            at_reference = affinity.scale(element['geom'], reference_scale / mm_per_unit, reference_scale / mm_per_unit, origin=(0, 0))
            parts = polys(at_reference.buffer(cfg['comp'], join_style=2))
            element['stitch'] = 'satin' if parts and all(stroke_like(part, cfg) for part in parts) else 'tatami'
            if element['cfg'].get('stitch') in FILL_STITCHES:
                element['stitch'] = element['cfg']['stitch']
            if element['stitch'] == 'satin' and any(2 * part.area / part.length > cfg['satin_force_max'] for part in polys(element['geom'])):
                print(f"WARNING: shape {index} is too wide for satin at this size; tatami instead")
                element['stitch'] = 'tatami'
        if element['cfg'].get('stitch') == 'run' and element['kind'] == 'run':
            element['stitch'] = 'run'
        shapes.append(element)
    shapes = knockout(shapes, cfg['overlap'])

    builder = PatternBuilder(cfg, grid_origin=(x0 * mm_per_unit, y0 * mm_per_unit))
    # colour groups in order of first appearance; inside a group: document order, text in reading order
    colours = []
    for shape in shapes:
        if shape['color'] not in colours:
            colours.append(shape['color'])
    planned_order = [int(v) for v in ((plan or {}).get('order') or [])]
    for colour in colours:
        builder.new_colour(colour, threads.get(colour, colour))
        items = []
        for shape in shapes:
            if shape['color'] != colour:
                continue
            shape_cfg = dict(cfg, **{k: v for k, v in shape['cfg'].items() if k != 'stitch'})
            if shape['kind'] == 'run':
                items.append(('run', shape['geom'], shape_cfg, shape['id']))
                continue
            for part in polys(shape['geom']):
                items.append((shape['stitch'], part, shape_cfg, shape['id']))
        planned = []
        if planned_order:   # planned order first (stable for pieces of one shape), the rest after in the usual order
            rank = {v: i for i, v in enumerate(planned_order)}
            planned = sorted([item for item in items if item[3] in rank], key=lambda item: rank[item[3]])
            items = [item for item in items if item[3] not in rank]
        for kind, geometry, shape_cfg, _ in planned + reading_order(items):
            builder.sew(kind, geometry, shape_cfg)

    pattern = builder.pattern
    pattern.stitches = clean_stitches(pattern.stitches)
    pattern.add_command(pe.END)
    # centre (whole 0.1 mm steps keep the grid)
    points = [(x, y) for x, y, command in pattern.stitches if (command & pe.COMMAND_MASK) == pe.STITCH]
    left, right = min(x for x, y in points), max(x for x, y in points)
    top, bottom = min(y for x, y in points), max(y for x, y in points)
    tx, ty = -round((left + right) / 2), -round((top + bottom) / 2)
    pattern.translate(tx, ty)
    pattern.scale_mm, pattern.offset = mm_per_unit, (tx, ty)       # shape in pattern units = SVG * scale_mm * 10 + offset
    pattern.kinds = sorted(builder.kinds)            # stitch types used: run, satin, tatami, contour, applique, cross, border
    pattern.stops = builder.stops                    # machine stops inside a colour (appliqué), in order
    pattern.underlay = [(round(x * 10 + tx), round(y * 10 + ty)) for x, y in builder.underlay]

    # visible area of every shape, in pattern units, for the coverage check (coverage.py)
    def margin(shape):    # how far this stitch type may reach past the shape by design (mm)
        if shape.get('stitch') == 'cross':
            return float({**cfg, **shape['cfg']}.get('cross_size', 2.0))          # whole grid squares
        return 0.0
    pattern.shapes = [dict(id=s['id'], kind=s['kind'], stitch=s.get('stitch', s['kind']), width=s.get('width', 0) * mm_per_unit,
                           margin=margin(s), geom=affinity.affine_transform(s['geom'], [10, 0, 0, 10, tx, ty]))
                      for s in shapes if not s['geom'].is_empty]
    # how far stitches may reach out: compensation + widening of thin satin
    pattern.comp = float(cfg['comp']) * (1 + float(cfg['comp_stretch']) / 2) + float(cfg['satin_widen_max']) / 2
    pattern.thread_mm = float(cfg['thread_mm'])
    return pattern
