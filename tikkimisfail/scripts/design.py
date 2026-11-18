"""SVG -> list of elements to embroider (document order = layer order).

Each element: dict(geom, color, kind)
  kind 'fill' : geom is a (Multi)Polygon
  kind 'run'  : geom is a LineString (thin stroke)
Background-coloured shapes are not stitched: they cut away what lies under them.
Shapes of another colour on top cut away the part below them (with an overlap).
"""
import svgelements as se
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union


def _rings(path, steps=24):
    rings = []
    for sub in path.as_subpaths():
        pts = []
        for seg in se.Path(sub):
            if isinstance(seg, (se.Move, se.Line, se.Close)):
                if seg.end is not None: pts.append((seg.end.x, seg.end.y))
                continue
            for i in range(1, steps + 1):
                q = seg.point(i / steps); pts.append((q.x, q.y))
        if len(pts) >= 3:
            rings.append(Polygon(pts).buffer(0))
    return rings


def _polygon(path):
    """even-odd fill: biggest rings first, contained rings become holes"""
    rings = sorted(_rings(path), key=lambda g: -g.area)
    geom = None
    for r in rings:
        if geom is None: geom = r
        elif geom.buffer(-1e-6).contains(r): geom = geom.difference(r)
        else: geom = geom.union(r)
    return geom


def _polyline(path, steps=24):
    out = []
    for sub in path.as_subpaths():
        pts = []
        for seg in se.Path(sub):
            if isinstance(seg, (se.Move, se.Line, se.Close)):
                if seg.end is not None: pts.append((seg.end.x, seg.end.y))
                continue
            for i in range(1, steps + 1):
                q = seg.point(i / steps); pts.append((q.x, q.y))
        if len(pts) >= 2: out.append(LineString(pts))
    return out


def _hex(c):
    return None if c is None or c.value is None or c.alpha == 0 else '#%02x%02x%02x' % (c.red, c.green, c.blue)


def load(svg_file, background='#ffffff'):
    """read the SVG; returns elements in sewing (document) order, in SVG units"""
    raw = []
    for e in se.SVG.parse(svg_file).elements():
        if not isinstance(e, se.Shape): continue
        if e.values.get('display') == 'none' or e.values.get('visibility') == 'hidden': continue
        path = se.Path(e); path.reify()
        fill, stroke = _hex(e.fill), _hex(e.stroke)
        if fill:
            g = _polygon(path)
            if g is not None and not g.is_empty: raw.append(dict(geom=g, color=fill, kind='fill'))
        if stroke and (e.stroke_width or 0) > 0:
            w = e.stroke_width
            for ln in _polyline(path):
                raw.append(dict(geom=ln, color=stroke, kind='run', width=w))
    bg = background.lower() if background else None
    # background shapes cut away everything below them, and are not stitched
    out = []
    for i, el in enumerate(raw):
        if el['color'] == bg: continue
        if el['kind'] == 'fill':
            cut = [r['geom'] for r in raw[i + 1:] if r['kind'] == 'fill' and r['color'] == bg]
            if cut: el['geom'] = el['geom'].difference(unary_union(cut))
            if el['geom'].is_empty: continue
        out.append(el)
    return out


def knockout(elements, overlap):
    """a fill of another colour lying on top cuts away the part below it, keeping `overlap` (scaled units)"""
    for i, el in enumerate(elements):
        if el['kind'] != 'fill': continue
        top = [t['geom'].buffer(-overlap) for t in elements[i + 1:] if t['kind'] == 'fill' and t['color'] != el['color']]
        top = [t for t in top if not t.is_empty]
        if top: el['geom'] = el['geom'].difference(unary_union(top))
    return [e for e in elements if not e['geom'].is_empty]


def polys(g):
    if g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    if isinstance(g, MultiPolygon): return list(g.geoms)
    return [p for p in getattr(g, 'geoms', []) if isinstance(p, Polygon)]
