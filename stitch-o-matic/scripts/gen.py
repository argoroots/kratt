"""Make embroidery files from an SVG.

python3 gen.py logo.svg --name "Name" --sizes 100,150,200 --machines brother,janome [--working working.pes]
       [--color "#rrggbb=Thread name"] [--angle 45] [--background "#ffffff"] [--set satin_max=2.5] [--plan plan.json]
       [--exact] [--scales 0.5688,0.86] [--fabric jersey] [--thread 60] [--hoop 130x180]
       [--stabilizer cutaway] [--topping washaway-film]

--sizes: longer side of the design in mm (stitches come out a little bigger: pull compensation).
--exact: --sizes are the stitched size (longer side of the stitches); the scale is adjusted until
         the stitches measure that, to 0.05 mm.
--scales: mm per SVG unit, one per file, instead of --sizes: the same scale as another design drawn
         in the same SVG coordinates (e.g. the mark alone, as big as in the logo with text). gen.py
         prints the scale of every file and keeps it in meta.json.

Writes out/<Name> <size>.pes (+ .jef, .bmp), outpos/ (PES v6, underlay points, shapes), out/meta.json.
<size> = longer side in mm, 3 places padded with spaces.
"""
import argparse
import datetime
import json
import math
import os
import shutil
import unicodedata

import pyembroidery as pe
from pyembroidery.EmbThreadJef import get_thread_set as jef_threads
from pyembroidery.EmbThreadPec import get_thread_set as pec_threads
from shapely import affinity

import coverage
import design
import digitize
import pes10

STABILIZERS = ('cutaway', 'mesh', 'tearaway', 'washaway-film', 'washaway-fiber', 'fusible', 'sticky')
# machines we make files for: file format, name, largest embroidery area (mm)
MACHINES = {'brother': ('pes', 'Brother Innov-is V3', (300, 180)), 'janome': ('jef', 'Janome Memory Craft 550E', (200, 360))}


def ascii_name(text):
    """machine screen name in plain ASCII: the PES header stores its length in characters, so a UTF-8
    letter (ä, õ) shifts everything after it and the file is unreadable"""
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text) if ord(ch) < 128)


def nearest_thread(hex_colour, palette):
    """the machine maker's thread closest to a colour: code, name, hex"""
    thread = pe.EmbThread()
    thread.set_hex_color(hex_colour)
    i = thread.find_nearest_color_index(palette)
    match = palette[i]
    return dict(code=str(match.catalog_number) if match.catalog_number else f'nr {i}', name=match.description, hex=match.hex_color())


def bmp(pattern, file_name):
    """preview: 400x400, light grey background, line broken at jumps"""
    from PIL import Image, ImageDraw
    stitches = [(x, y, c & pe.COMMAND_MASK) for x, y, c in pattern.stitches]
    xs = [x for x, y, c in stitches if c == pe.STITCH]
    ys = [y for x, y, c in stitches if c == pe.STITCH]
    size = 400
    margin = 20
    scale = (size - 2 * margin) / max(max(xs) - min(xs), max(ys) - min(ys))
    ox = (size - (max(xs) - min(xs)) * scale) / 2 - min(xs) * scale
    oy = (size - (max(ys) - min(ys)) * scale) / 2 - min(ys) * scale
    image = Image.new('RGB', (size, size), (236, 236, 236))
    draw = ImageDraw.Draw(image)
    thread = 0
    colour = pattern.threadlist[0].hex_color()
    previous = None
    for x, y, command in stitches:
        if command == pe.COLOR_CHANGE:
            thread += 1
            colour = pattern.threadlist[min(thread, len(pattern.threadlist) - 1)].hex_color()
        if command == pe.STITCH:
            if previous:
                draw.line([previous, (ox + x * scale, oy + y * scale)], fill=colour, width=1)
            previous = (ox + x * scale, oy + y * scale)
        else:
            previous = None
    image.save(file_name, 'BMP')


def stitch_points(pattern):
    return [(x, y) for x, y, c in pattern.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]


def measure(pattern):
    """(width, height) of the stitches, mm"""
    points = stitch_points(pattern)
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    return (max(xs) - min(xs)) / 10, (max(ys) - min(ys)) / 10


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('svg')
    parser.add_argument('--name', required=True)
    parser.add_argument('--sizes', help='longer side in mm, e.g. 100,150')
    parser.add_argument('--exact', action='store_true', help='--sizes are the stitched size, not the design size')
    parser.add_argument('--scales', help='mm per SVG unit, one per file (instead of --sizes)')
    parser.add_argument('--working', help='working PES v10 file for the target machine')
    parser.add_argument('--color', action='append', default=[], help='"#rrggbb=thread name"')
    parser.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    parser.add_argument('--background', default='#ffffff')
    parser.add_argument('--fabric', help='fabric: ' + ', '.join(digitize.FABRICS))
    parser.add_argument('--thread', type=int, default=40, choices=sorted(digitize.THREADS), help='thread weight: 40 (normal) or 60 (thin, small text)')
    parser.add_argument('--plan', help='plan.json: decisions per shape (see digitize.build)')
    parser.add_argument('--set', action='append', default=[], help='parameter=value (see digitize.DEFAULTS)')
    parser.add_argument('--stabilizer', help='backing under the fabric: ' + ', '.join(STABILIZERS) + '; combine with +, e.g. cutaway+fusible')
    parser.add_argument('--topping', help='topping on the fabric: ' + ', '.join(STABILIZERS))
    parser.add_argument('--hoop', help='embroidery area of the hoop in mm, e.g. 130x180 (default: the largest hoop of the machine)')
    parser.add_argument('--machines', required=True, help='brother, janome or both: brother,janome')
    args = parser.parse_args()
    for option in (args.stabilizer, args.topping):
        for value in (option or '').split('+'):
            if value and value not in STABILIZERS:
                parser.error(f'unknown stabilizer {value}: ' + ', '.join(STABILIZERS))
    if bool(args.sizes) == bool(args.scales):
        parser.error('give --sizes or --scales')
    return args


def settings(args):
    """digitizing settings: fabric, row angle, thread weight, then --set"""
    cfg = dict(digitize.FABRICS[args.fabric]) if args.fabric else {}
    cfg['fill_angle'] = args.angle
    cfg = digitize.thread_cfg(cfg, args.thread)              # 60 wt: denser, narrower (scaled from the fabric's values)
    for pair in args.set:
        key, value = pair.split('=')
        cfg[key] = float(value)
    return cfg


def build_at_size(elements, job, names, cfg, plan, exact):
    """one pattern: at a fixed scale, at a design size, or (exact) until the stitches measure the size"""
    if 'scale' in job:
        return digitize.build(elements, 1.0, names, cfg, plan=plan, scale=job['scale'], ref_scale=job['ref_scale'])
    wanted = size = job['size']
    pattern = digitize.build(elements, size, names, cfg, ref_size=job['ref_size'], plan=plan)
    for _ in range(4 if exact else 0):          # stitched size = wanted: scale by the measured ratio
        got = max(measure(pattern))
        if abs(got - wanted) < 0.05:
            break
        size *= wanted / got
        pattern = digitize.build(elements, size, names, cfg, ref_size=job['ref_size'], plan=plan)
    if exact and abs(max(measure(pattern)) - wanted) >= 0.05:
        print(f'WARNING: {wanted} mm: stitches {max(measure(pattern)):.2f} mm after 4 tries')
    return pattern


def check_hoops(file_name, width, height, machines, hoop):
    for machine in machines:
        _, machine_name, (hoop_w, hoop_h) = MACHINES[machine]
        if hoop:
            hoop_w, hoop_h = (float(v) for v in hoop.lower().replace('×', 'x').split('x'))
            machine_name = 'chosen'
        if not ((width <= hoop_w and height <= hoop_h) or (width <= hoop_h and height <= hoop_w)):
            print(f'WARNING: {file_name} ({width:.0f} x {height:.0f} mm) does not fit the {machine_name} hoop {hoop_w:g} x {hoop_h:g} mm')


def write_check_data(pattern, file_name, dx, dy):
    """outpos/<file>.under.json (underlay points) and .shapes.json (shapes, for coverage.py)"""
    json.dump([(x + dx, y + dy) for x, y in pattern.underlay], open(f'outpos/{file_name}.under.json', 'w'))
    shapes = [dict(id=s['id'], kind=s['kind'], stitch=s['stitch'], width=s['width'], margin=s.get('margin', 0),
                   wkt=affinity.translate(s['geom'], dx, dy).wkt) for s in getattr(pattern, 'shapes', [])]
    json.dump(dict(comp=getattr(pattern, 'comp', 0.2), thread_mm=getattr(pattern, 'thread_mm', 0.35), shapes=shapes),
              open(f'outpos/{file_name}.shapes.json', 'w'))


def main():
    args = parse_arguments()
    machines = [m.strip().lower() for m in args.machines.split(',') if m.strip()]
    formats = [MACHINES[m][0] for m in machines]
    cfg = settings(args)
    names = {k.lower(): v for k, v in (pair.split('=', 1) for pair in args.color)}
    elements = design.load(args.svg, args.background)
    os.makedirs('outpos', exist_ok=True)
    os.makedirs('out', exist_ok=True)
    choices = dict(machines=machines, hoop=args.hoop or '', sizes=args.sizes or '', scales=args.scales or '', exact=args.exact,
                   fabric=args.fabric or '', stabilizer=args.stabilizer or '', topping=args.topping or '', thread=args.thread,
                   angle=args.angle, sets=args.set, colors=args.color,
                   plan=os.path.basename(args.plan) if args.plan else '', working=os.path.basename(args.working) if args.working else '')
    meta = dict(name=args.name, date=datetime.date.today().isoformat(), params=dict(digitize.DEFAULTS, **cfg),
                fabric=args.fabric or '', thread=args.thread, plan=args.plan or '', choices=choices,
                format=('PES v10' if args.working else 'PES v6') if 'pes' in formats else '', jef='jef' in formats,
                files=[], colors=[])
    for colour in dict.fromkeys(e['color'] for e in elements):
        meta['colors'].append(dict(hex=colour, name=names.get(colour, colour), brother=nearest_thread(colour, pec_threads()),
                                   janome=nearest_thread(colour, jef_threads())))
    plan = json.load(open(args.plan)) if args.plan else None
    if args.scales:
        scales = [float(v) for v in args.scales.split(',')]
        jobs = [dict(scale=s, ref_scale=max(scales)) for s in scales]
    else:
        sizes = [float(v) for v in args.sizes.split(',')]
        jobs = [dict(size=s, ref_size=max(sizes)) for s in sizes]

    for job in jobs:
        pattern = build_at_size(elements, job, names, cfg, plan, args.exact)
        points = stitch_points(pattern)
        width, height = measure(pattern)
        longer = round(max(width, height))
        file_name = f'{args.name} {longer:>3}'
        label = f'{ascii_name(args.name)[:8 - len(str(longer)) - 1]} {longer}'[:8]   # name on the machine screen (8 chars)
        check_hoops(file_name, width, height, machines, args.hoop)
        if 'jef' in formats:                                    # Janome: centred
            pe.write_jef(pattern, f'out/{file_name}.jef', {'trims': True})
            bmp(pattern, f'out/{file_name}.bmp')
        # Brother: origin top left (the minimum rounds to 0)
        dx = -math.floor(min(x for x, y in points) + 0.5)
        dy = -math.floor(min(y for x, y in points) + 0.5)
        pattern.translate(dx, dy)
        write_check_data(pattern, file_name, dx, dy)
        pattern.metadata('name', label)
        pe.write_pes(pattern, f'outpos/{file_name}.pes', {'version': 6})
        for line in coverage.report(f'outpos/{file_name}.pes'):     # uncovered spots inside shapes (cracks, wedges, gaps)
            print(f'WARNING: {file_name}: {line}')
        if 'pes' in formats:
            if args.working:
                pes10.to_v10(f'outpos/{file_name}.pes', f'out/{file_name}.pes', args.working, label)
            else:
                shutil.copy(f'outpos/{file_name}.pes', f'out/{file_name}.pes')
        meta['kinds'] = sorted(set(meta.get('kinds', [])) | set(getattr(pattern, 'kinds', [])))
        colour_rows = [c['hex'].lower() for c in meta['colors']]   # thread block -> colour row (a machine stop repeats a colour)
        meta['blocks'] = [colour_rows.index(t.hex_color().lower()) if t.hex_color().lower() in colour_rows else min(i, len(colour_rows) - 1)
                          for i, t in enumerate(pattern.threadlist)]
        meta['stops'] = list(getattr(pattern, 'stops', []))
        meta['files'].append(dict(file=file_name, w=round(width, 1), h=round(height, 1), label=label, scale=round(pattern.scale_mm, 6)))
        print(file_name, f'{width:.1f} x {height:.1f} mm', len(points), 'stitches', f'scale {pattern.scale_mm:.6f} mm/unit')
    json.dump(meta, open('out/meta.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
