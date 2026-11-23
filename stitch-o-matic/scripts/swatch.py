"""Test swatch: the same design several times with one parameter changed, numbered.

python3 swatch.py logo.svg --name Proov --size 60 --vary satin_spacing=0.35,0.4,0.45 --machines brother
       [--working working.pes] [--angle 45] [--background "#ffffff"] [--set fill_spacing=0.3] [--gap 8]
       [--fabric linen] [--plan plan.json] [--only 0,2,5] [--list]

--list   prints the shapes of the SVG with numbers and positions (mm at --size), the stitch type the rules
         pick and other techniques worth offering (with the measured reason), then stops. Needs only --size.
--only   uses only these shapes, in one row, at the scale they have when the whole design is
         --size mm (e.g. only the difficult letters of a 150 mm logo).

Each variant gets a number stitched under it (running stitch, first colour).
Writes out/<Name>.pes / .jef (one file, all variants), out/<Name>.txt (number -> value)
and out/<Name>.thread.png (thread preview with the numbers).
"""
import argparse
import json
import math
import os
import shutil

import pyembroidery as pe
from shapely import affinity
from shapely.ops import unary_union

import design
import digitize
import gen
import pes10
import preview
from texts import TEXT

# digits as strokes on a 2 x 4 box (x right, y down), seven-segment style
SEGMENTS = {'a': ((0, 0), (2, 0)), 'b': ((2, 0), (2, 2)), 'c': ((2, 2), (2, 4)), 'd': ((2, 4), (0, 4)),
            'e': ((0, 4), (0, 2)), 'f': ((0, 2), (0, 0)), 'g': ((0, 2), (2, 2))}
DIGITS = {'0': 'fabcde', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd',
          '6': 'afedcg', '7': 'abc', '8': 'abcdefg', '9': 'gfabcd'}
NUMBER_HEIGHT = 6.0      # mm
NUMBER_GAP = 3.0         # mm between a variant and its number


def digit_path(digit):
    """one continuous path through the segments (segments may be walked twice)"""
    segments = [SEGMENTS[s] for s in DIGITS[digit]]
    path = [segments[0][0], segments[0][1]]
    todo = segments[1:]
    while todo:
        current = path[-1]
        following = next((s for s in todo if current in s), None)
        if following is None:      # walk back along drawn lines to an end of a remaining segment
            following = todo[0]
            path += back_to(path, following[0])
            current = path[-1]
        todo.remove(following)
        path.append(following[1] if following[0] == current else following[0])
    return path


def back_to(path, target):
    """points walking back along the path to its last visit of target (or straight there)"""
    if target not in path:
        return [target]
    i = max(k for k, q in enumerate(path) if q == target)
    return path[i:-1][::-1]


def number_stitches(text, x, y, height=NUMBER_HEIGHT, step=1.0):
    """running stitch (there, back, there) for a number; top-left corner at x, y (mm)"""
    unit = height / 4
    runs = []
    for i, digit in enumerate(text):
        points = [(x + i * 3.2 * unit + px * unit, y + py * unit) for px, py in digit_path(digit)]
        run = []
        for a, b in zip(points, points[1:]):
            n = max(1, math.ceil(math.dist(a, b) / step))
            run += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
        run.append(points[-1])
        runs.append(run + run[-2::-1] + run[1:])
    return runs


def colour_blocks(pattern):
    """split a pattern into colour blocks of commands (x, y, command) in 0.1 mm"""
    blocks = [[]]
    for x, y, command in pattern.stitches:
        command &= pe.COMMAND_MASK
        if command == pe.COLOR_CHANGE:
            blocks.append([])
            continue
        if command == pe.END:
            continue
        blocks[-1].append((x, y, command))
    return blocks


def extent(elements):
    """bounds of all elements, strokes with their width"""
    return unary_union([e['geom'] if e['kind'] == 'fill' else e['geom'].buffer(e.get('width', 0) / 2) for e in elements]).bounds


def list_shapes(elements, size, cfg):
    """--list: every shape with its number, position, the rule's stitch type and suggestions"""
    x0, y0, x1, y1 = extent(elements)
    mm_per_unit = size / max(x1 - x0, y1 - y0)
    for i, element in enumerate(elements):
        b = element['geom'].bounds
        print(f'{i:3}  {element["kind"]:4} {element["color"]}  x {(b[0] - x0) * mm_per_unit:6.1f}–{(b[2] - x0) * mm_per_unit:6.1f}'
              f'  y {(b[1] - y0) * mm_per_unit:6.1f}–{(b[3] - y0) * mm_per_unit:6.1f} mm')
        if element['kind'] == 'fill':           # what the rules pick, and what else to offer (KNOWLEDGE 10)
            rule, hints = digitize.suggest(affinity.scale(element['geom'], mm_per_unit, mm_per_unit, origin=(0, 0)), dict(digitize.DEFAULTS, **cfg))
            print(f'       rule: {rule}' + ''.join(f'\n       suggest: {technique} – {why}' for technique, why in hints))


def only_shapes(elements, numbers, size):
    """--only: these shapes in one row, 3 mm apart, bottoms on one line, at the whole design's scale.
    Returns (elements, size of the row)."""
    x0, y0, x1, y1 = extent(elements)
    mm_per_unit = size / max(x1 - x0, y1 - y0)
    picked = [elements[i] for i in numbers]
    right = None
    row = []
    bottom = picked[0]['geom'].bounds[3]
    for element in picked:
        b = element['geom'].bounds
        dx = 0 if right is None else right - b[0]
        row.append(dict(element, geom=affinity.translate(element['geom'], dx, bottom - b[3])))
        right = b[2] + dx + 3 / mm_per_unit
    x0, y0, x1, y1 = extent(row)
    return row, max(x1 - x0, y1 - y0) * mm_per_unit


def stitch_box(pattern):
    points = [(x, y) for x, y, c in pattern.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
    return min(x for x, y in points), min(y for x, y in points), max(x for x, y in points), max(y for x, y in points)


def grid_columns(count, cell_w, cell_h, gap, hoops):
    """columns of the variant grid: fits every hoop if possible, then the smallest longer side.
    Returns (fits, columns, width, height)."""
    best = None
    for columns in range(1, count + 1):
        rows = math.ceil(count / columns)
        width, height = columns * cell_w - gap, rows * cell_h - gap
        fits = all((width <= hw and height <= hh) or (width <= hh and height <= hw) for hw, hh in hoops)
        rank = (not fits, max(width, height))
        if best is None or rank < best[0]:
            best = (rank, columns, width, height)
    (bad, _), columns, width, height = best
    return not bad, columns, width, height


def assemble(patterns, boxes, columns, cell_w, cell_h, gap):
    """one pattern: colour by colour, every variant in its grid cell, numbers with the first colour"""
    result = pe.EmbPattern()
    for thread in patterns[0].threadlist:
        result.add_thread(thread)
    first = [True]

    def move_to(x, y):
        if not first[0]:
            result.add_stitch_absolute(pe.TRIM, x, y)
        result.add_stitch_absolute(pe.JUMP, x, y)
        first[0] = False

    for colour in range(len(colour_blocks(patterns[0]))):
        if colour:
            result.add_stitch_absolute(pe.COLOR_CHANGE, *result.stitches[-1][:2])
        for k, pattern in enumerate(patterns):
            row, column = divmod(k, columns)
            box = boxes[k]
            ox = column * cell_w * 10 - box[0] + (cell_w - gap) * 5 - (box[2] - box[0]) / 2
            oy = row * cell_h * 10 - box[1]
            block = colour_blocks(pattern)[colour]
            stitches = [q for q in block if q[2] == pe.STITCH]
            if not stitches:
                continue
            move_to(stitches[0][0] + ox, stitches[0][1] + oy)
            for x, y, command in block:
                if command in (pe.STITCH, pe.JUMP, pe.TRIM):
                    result.add_stitch_absolute(command, x + ox, y + oy)
            if colour == 0:
                text = str(k + 1)
                nx = column * cell_w + (cell_w - gap) / 2 - len(text) * 3.2 * 1.5 / 2
                ny = row * cell_h + (box[3] - box[1]) / 10 + NUMBER_GAP
                for run in number_stitches(text, nx, ny):
                    move_to(run[0][0] * 10, run[0][1] * 10)
                    for x, y in run:
                        result.add_stitch_absolute(pe.STITCH, round(x * 10), round(y * 10))
    result.add_stitch_absolute(pe.TRIM, *result.stitches[-1][:2])
    result.add_stitch_absolute(pe.END, *result.stitches[-1][:2])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('svg')
    parser.add_argument('--name')
    parser.add_argument('--size', type=float, required=True, help='longer side of one variant, mm')
    parser.add_argument('--vary', help='parameter=v1,v2,... (see digitize.DEFAULTS)')
    parser.add_argument('--machines')
    parser.add_argument('--working')
    parser.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    parser.add_argument('--background', default='#ffffff')
    parser.add_argument('--fabric', help='fabric: ' + ', '.join(digitize.FABRICS))
    parser.add_argument('--plan', help='plan.json: decisions per shape (see digitize.build)')
    parser.add_argument('--set', action='append', default=[])
    parser.add_argument('--gap', type=float, default=8.0, help='space between variants, mm')
    parser.add_argument('--only', help='shape numbers from --list, e.g. 0,2,5')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if not args.list and not (args.name and args.vary and args.machines):
        parser.error('--name, --vary and --machines are required (except with --list)')
    key, values = (args.vary or 'comp=0').split('=', 1)
    if key == 'angle':
        key = 'fill_angle'
    if key not in digitize.DEFAULTS:
        raise SystemExit(f'unknown parameter {key}; choose from: {", ".join(digitize.DEFAULTS)}')
    values = [float(v) for v in values.split(',')]
    machines = [m.strip().lower() for m in (args.machines or '').split(',') if m.strip()]
    cfg = dict(digitize.FABRICS[args.fabric]) if args.fabric else {}
    cfg['fill_angle'] = args.angle
    for pair in args.set:
        k, v = pair.split('=')
        cfg[k] = float(v)
    elements = design.load(args.svg, args.background)
    if args.list:
        list_shapes(elements, args.size, cfg)
        return
    size = args.size
    plan = json.load(open(args.plan)) if args.plan else None
    if args.only:
        numbers = [int(i) for i in args.only.split(',')]
        elements, size = only_shapes(elements, numbers, args.size)
        if plan:   # plan numbers are the original shape numbers; here shapes are renumbered 0..n-1
            plan = dict(plan, shapes={str(numbers.index(int(k))): v for k, v in (plan.get('shapes') or {}).items() if int(k) in numbers},
                        order=[numbers.index(int(k)) for k in plan.get('order') or [] if int(k) in numbers])
    patterns = [digitize.build(elements, size, {}, dict(cfg, **{key: v}), ref_size=size, plan=plan) for v in values]

    # cell size = largest variant + room for the number
    boxes = [stitch_box(p) for p in patterns]
    cell_w = max(b[2] - b[0] for b in boxes) / 10 + args.gap
    cell_h = max(b[3] - b[1] for b in boxes) / 10 + NUMBER_GAP + NUMBER_HEIGHT + args.gap
    fits, columns, width, height = grid_columns(len(values), cell_w, cell_h, args.gap, [gen.MACHINES[m][2] for m in machines])
    if not fits:
        print(f'WARNING: {len(values)} variants ({width:.0f} x {height:.0f} mm) do not fit the hoop; reduce --size or the number of values')
    result = assemble(patterns, boxes, columns, cell_w, cell_h, args.gap)

    os.makedirs('out', exist_ok=True)
    os.makedirs('outpos', exist_ok=True)
    points = [(x, y) for x, y, c in result.stitches if c == pe.STITCH]
    min_x, min_y = min(x for x, y in points), min(y for x, y in points)
    width, height = (max(x for x, y in points) - min_x) / 10, (max(y for x, y in points) - min_y) / 10
    if 'janome' in machines:                       # Janome: centred
        cx, cy = min_x + width * 5, min_y + height * 5
        janome = pe.EmbPattern()
        janome.threadlist = list(result.threadlist)
        janome.stitches = [[x - round(cx), y - round(cy), c] for x, y, c in result.stitches]
        pe.write_jef(janome, f'out/{args.name}.jef', {'trims': True})
        gen.bmp(janome, f'out/{args.name}.bmp')
    result.translate(-min_x, -min_y)                # Brother: origin top left
    label = gen.ascii_name(args.name)[:8]
    result.metadata('name', label)
    if 'brother' in machines:
        pe.write_pes(result, f'outpos/{args.name}.pes', {'version': 6})
        if args.working:
            pes10.to_v10(f'outpos/{args.name}.pes', f'out/{args.name}.pes', args.working, label)
        else:
            shutil.copy(f'outpos/{args.name}.pes', f'out/{args.name}.pes')
    with open(f'out/{args.name}.txt', 'w') as f:
        f.write(TEXT['swatch_title'].format(name=args.name, svg=args.svg, size=f'{args.size:g}', key=key) + '\n')
        for k, v in enumerate(values):
            f.write(f'{k + 1}: {key} = {v:g}\n')
    preview.thread_picture(preview.segments(result), (0, 0, width, height), 8, '#f2efe8').save(f'out/{args.name}.thread.png')
    print(f'{args.name}: {len(values)} variants, {width:.0f} x {height:.0f} mm, {len(points)} stitches')
    for k, v in enumerate(values):
        print(f'  {k + 1}: {key} = {v:g}')


if __name__ == '__main__':
    main()
