"""SVG -> list of elements to embroider (document order = layer order).

Each element: dict(geom, color, kind)
  kind 'fill' : geom is a (Multi)Polygon
  kind 'run'  : geom is a LineString (thin stroke), with 'width' (SVG units)
Background-coloured shapes are not stitched: they cut away what lies under them.
Shapes of another colour on top cut away the part below them (with an overlap), see knockout().
"""
import svgelements as se
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

CURVE_STEPS = 24       # points per curve segment


def _subpath_points(path, steps=CURVE_STEPS):
    """for every subpath: its points, curves sampled in `steps` pieces"""
    for subpath in path.as_subpaths():
        points = []
        for segment in se.Path(subpath):
            if isinstance(segment, (se.Move, se.Line, se.Close)):
                if segment.end is not None:
                    points.append((segment.end.x, segment.end.y))
                continue
            for i in range(1, steps + 1):
                q = segment.point(i / steps)
                points.append((q.x, q.y))
        yield points


def _polygon(path):
    """even-odd fill: biggest rings first, contained rings become holes"""
    rings = sorted((Polygon(points).buffer(0) for points in _subpath_points(path) if len(points) >= 3), key=lambda g: -g.area)
    shape = None
    for ring in rings:
        if shape is None:
            shape = ring
        elif shape.buffer(-1e-6).contains(ring):
            shape = shape.difference(ring)
        else:
            shape = shape.union(ring)
    return shape


def _polylines(path):
    return [LineString(points) for points in _subpath_points(path) if len(points) >= 2]


def _hex(colour):
    """svgelements colour -> '#rrggbb', None when there is none or it is transparent"""
    if colour is None or colour.value is None or colour.alpha == 0:
        return None
    return '#%02x%02x%02x' % (colour.red, colour.green, colour.blue)


def load(svg_file, background='#ffffff'):
    """read the SVG; returns elements in sewing (document) order, in SVG units"""
    raw = []
    for shape in se.SVG.parse(svg_file).elements():
        if not isinstance(shape, se.Shape):
            continue
        if shape.values.get('display') == 'none' or shape.values.get('visibility') == 'hidden':
            continue
        path = se.Path(shape)
        path.reify()
        fill, stroke = _hex(shape.fill), _hex(shape.stroke)
        if fill:
            geometry = _polygon(path)
            if geometry is not None and not geometry.is_empty:
                raw.append(dict(geom=geometry, color=fill, kind='fill'))
        if stroke and (shape.stroke_width or 0) > 0:
            for line in _polylines(path):
                raw.append(dict(geom=line, color=stroke, kind='run', width=shape.stroke_width))
    background = background.lower() if background else None
    # background shapes cut away everything below them, and are not stitched
    elements = []
    for i, element in enumerate(raw):
        if element['color'] == background:
            continue
        if element['kind'] == 'fill':
            cut = [r['geom'] for r in raw[i + 1:] if r['kind'] == 'fill' and r['color'] == background]
            if cut:
                element['geom'] = element['geom'].difference(unary_union(cut))
            if element['geom'].is_empty:
                continue
        elements.append(element)
    return elements


def knockout(elements, overlap):
    """a fill of another colour lying on top cuts away the part below it, keeping `overlap` (scaled units)"""
    for i, element in enumerate(elements):
        if element['kind'] != 'fill':
            continue
        on_top = [t['geom'].buffer(-overlap) for t in elements[i + 1:] if t['kind'] == 'fill' and t['color'] != element['color']]
        on_top = [t for t in on_top if not t.is_empty]
        if on_top:
            element['geom'] = element['geom'].difference(unary_union(on_top))
    return [e for e in elements if not e['geom'].is_empty]
