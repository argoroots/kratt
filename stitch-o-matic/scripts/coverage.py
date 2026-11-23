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

Positions are in PES units (0.1 mm) inside, reported in mm from the top left of the PES.
"""
import json
import os
import sys

import numpy as np
import pyembroidery as pe
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely import wkt
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

THREAD = 0.35      # mm, drawn thread width (real thread 0.35-0.4)
EDGE = 0.25        # mm the filled area is shrunk by: the outline itself is not a hole
PX = 20            # pixels per mm
FILLED = ('satin', 'tatami', 'contour')


def load(pes_file):
    """(shapes data, top stitch segments, top needle points) of a PES and its outpos/ files"""
    base = os.path.splitext(pes_file)[0]
    data = json.load(open(base + '.shapes.json'))
    if isinstance(data, list):
        data = dict(comp=0.2, shapes=data)          # older files
    underlay = set(map(tuple, json.load(open(base + '.under.json')))) if os.path.exists(base + '.under.json') else set()
    segments = []
    points = []
    previous = None
    for x, y, command in pe.read(pes_file).stitches:
        command &= pe.COMMAND_MASK
        if command != pe.STITCH:
            previous = None
            continue
        top = not (previous is not None and previous in underlay and (x, y) in underlay)
        if previous is not None and top:
            segments.append((previous, (x, y)))
        if (x, y) not in underlay:
            points.append((x, y))
        previous = (x, y)
    return data, segments, points


def holes(pes_file, min_mm=0.25, picture=None, _d=None):
    """uncovered spots: dict(x, y, size) in mm from the top left of the PES; size = widest circle inside.
    picture: also save a picture (covered grey, holes red, over the edge blue). _d: load() result."""
    data, segments, points = _d or load(pes_file)
    fills = [wkt.loads(s['wkt']) for s in data['shapes'] if s.get('stitch') in FILLED]
    if not fills or not segments:
        return []
    all_x = [q[0] for s in segments for q in s]
    all_y = [q[1] for s in segments for q in s]
    width, height = int((max(all_x) / 10 + 2) * PX), int((max(all_y) / 10 + 2) * PX)

    def to_px(x, y):
        return (x / 10 * PX, y / 10 * PX)

    target = Image.new('1', (width, height), 0)
    draw = ImageDraw.Draw(target)
    area = unary_union(fills).buffer(-EDGE * 10)          # the union: seams between touching parts count
    for part in getattr(area, 'geoms', [area]):
        if part.is_empty or part.geom_type != 'Polygon':
            continue
        draw.polygon([to_px(x, y) for x, y in part.exterior.coords], fill=1)
        for ring in part.interiors:
            draw.polygon([to_px(x, y) for x, y in ring.coords], fill=0)
    cover = Image.new('1', (width, height), 0)
    draw = ImageDraw.Draw(cover)
    thread = max(1, round(float(data.get('thread_mm', THREAD)) * PX))
    for a, b in segments:
        draw.line([to_px(*a), to_px(*b)], fill=1, width=thread)
    should = np.array(target, bool)
    covered = np.array(cover, bool)
    gap = should & ~covered
    labels, count = ndimage.label(gap)
    found = []
    if count:
        distance = ndimage.distance_transform_edt(gap)
        for i, box in enumerate(ndimage.find_objects(labels), start=1):
            d = distance[box] * (labels[box] == i)
            size = 2 * float(d.max()) / PX
            if size >= min_mm:
                yy, xx = np.unravel_index(np.argmax(d), d.shape)
                found.append(dict(x=round(float(xx + box[1].start) / PX, 1), y=round(float(yy + box[0].start) / PX, 1),
                                  size=round(size, 2), _label=i))
    if picture:
        image = np.full((height, width, 3), 255, np.uint8)
        image[should & covered] = (170, 170, 170)
        image[gap] = (255, 205, 205)
        for hole in found:
            image[labels == hole['_label']] = (220, 0, 0)
        for place in overflow(pes_file, _d=(data, segments, points)):
            cx, cy = int(place['x'] * PX), int(place['y'] * PX)
            image[max(0, cy - 6):cy + 7, max(0, cx - 6):cx + 7] = (0, 60, 220)
        os.makedirs(os.path.dirname(picture) or '.', exist_ok=True)
        Image.fromarray(image).save(picture)
    for hole in found:
        hole.pop('_label')
    return sorted(found, key=lambda h: -h['size'])


def overflow(pes_file, tol_mm=0.3, _d=None):
    """needle points farther than comp + tol_mm from the design: dict(x, y, dist) in mm, one per 1 mm cell"""
    data, segments, points = _d or load(pes_file)
    shapes = []
    for s in data['shapes']:
        shape = wkt.loads(s['wkt'])
        if s.get('kind') == 'run':
            shape = shape.buffer(max(s.get('width', 0), 0.1) * 10 / 2)
        if s.get('margin'):
            shape = shape.buffer(float(s['margin']) * 10)    # cross squares, borders: reach past the shape by design
        shapes.append(shape)
    if not shapes:
        return []
    tree = STRtree(shapes)
    limit = (float(data.get('comp', 0.2)) + tol_mm) * 10
    worst = {}
    for x, y in points:
        point = Point(x, y)
        near = tree.query(point.buffer(limit))
        if len(near) and min(shapes[i].distance(point) for i in near) <= limit:
            continue
        d = min(s.distance(point) for s in shapes)
        if d > limit:
            cell = (int(x // 10), int(y // 10))
            if cell not in worst or d > worst[cell][2]:
                worst[cell] = (x, y, d)
    return sorted((dict(x=round(x / 10, 1), y=round(y / 10, 1), dist=round(d / 10, 2)) for x, y, d in worst.values()),
                  key=lambda o: -o['dist'])


def report(pes_file):
    """warning lines for gen.py / by hand; empty when all is well"""
    loaded = load(pes_file)
    lines = []
    found = holes(pes_file, _d=loaded)
    if found:
        lines.append(f'{len(found)} uncovered spot(s): ' + ', '.join(f"{h['size']} mm at x {h['x']}, y {h['y']}" for h in found[:8]))
    over = overflow(pes_file, _d=loaded)
    if over:
        lines.append(f'{len(over)} place(s) over the edge: ' + ', '.join(f"{o['dist']} mm at x {o['x']}, y {o['y']}" for o in over[:8]))
    return lines


def main():
    bad = 0
    for pes_file in sys.argv[1:]:
        picture = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(pes_file))), 'check',
                               os.path.basename(os.path.splitext(pes_file)[0]) + '.holes.png')
        holes(pes_file, picture=picture, _d=load(pes_file))
        lines = report(pes_file)
        if lines:
            bad += 1
            for line in lines:
                print(f'WARNING: {pes_file}: {line}')
        else:
            print(f'{pes_file}: covered, nothing over the edge')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
