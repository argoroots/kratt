"""Try many digitizing variants per shape and keep the best (writes plan.json for gen.py --plan).

python3 optimize.py image.svg --size 150 [--fabric linen] [--angle 45] [--set k=v] [--plan old.json]
       [--only 10,11,0] [--angles] [--ref-size 200] [--out plan.json]

Every shape is stitched alone in every variant and measured (thread counted 0.3 mm wide):
  uncovered  area of the shape the thread does not cover, mm2
  spill      thread outside the shape beyond the compensation (+0.1 mm), mm2
  thick      area with more than 8.5 mm of thread per mm2
  trims, stitches
score = sum of WEIGHTS * measure; the lowest wins. Identical shapes (same letter) are tried once.
Satin shapes: corner handling, wedge reach, gap fill. Tatami: with --angles also the row angle
(otherwise the angle stays as given - it changes the look, so it is the user's choice).
"""
import argparse
import itertools
import json

import pyembroidery as pe
from shapely import affinity
from shapely.geometry import LineString
from shapely.ops import unary_union

import design
import digitize
import preview

WEIGHTS = dict(uncovered=40.0, spill=15.0, thick=10.0, trims=1.0, stitches=0.002)

# underlay is not tried: its effect (fabric held, stitches raised) cannot be measured here; it follows the rules
SATIN_VARIANTS = dict(satin_mitre=[0, 70, 100, 130], satin_reach=[0, 1.5], satin_gap=[0.15, 0.3])
TATAMI_ANGLE_STEPS = (0, 15, -15, 30, -30, 45, -45, 90)


def measure(element, cfg, scale, ref_scale, plan_shape):
    """stitch one element alone with a plan entry and measure it (see the module description)"""
    plan = {'shapes': {'0': plan_shape}} if plan_shape else None
    pattern = digitize.build([element], 0, {}, cfg, plan=plan, scale=scale, ref_scale=ref_scale)
    tx, ty = pattern.offset
    shape = affinity.translate(affinity.scale(element['geom'], pattern.scale_mm, pattern.scale_mm, origin=(0, 0)), tx / 10, ty / 10)
    if element['kind'] == 'run':
        shape = shape.buffer(0.2)
    underlay = set(map(tuple, pattern.underlay))
    top_segments, previous, trims, last_command = [], None, 0, None
    for x, y, command in pattern.stitches:
        command &= pe.COMMAND_MASK
        if command == pe.STITCH:
            if previous and not ((previous[0] * 10, previous[1] * 10) in underlay and (x, y) in underlay):
                top_segments.append((previous, (x / 10, y / 10)))
            previous = (x / 10, y / 10)
        else:
            if command == pe.TRIM and last_command == pe.STITCH:
                trims += 1
            if command == pe.TRIM:
                previous = None
            elif command == pe.JUMP:
                previous = (x / 10, y / 10)
        if command in (pe.STITCH, pe.TRIM):
            last_command = command
    stitches = sum(1 for q in pattern.stitches if (q[2] & pe.COMMAND_MASK) == pe.STITCH)
    if not top_segments:
        return dict(uncovered=shape.area, spill=0, thick=0, trims=trims, stitches=stitches)
    # thread counted narrower than it is (0.3 mm): on fabric it is pulled in, so a corner that 0.4 mm thread
    # only just reaches stays open in the stitch-out
    covered = unary_union([LineString([a, b]).buffer(0.15, cap_style=1) for a, b in top_segments if a != b])
    inner = shape.buffer(-0.05)
    uncovered = inner.difference(covered).area if not inner.is_empty else 0.0
    comp = float(cfg.get('comp', digitize.DEFAULTS['comp']))
    spill = covered.difference(shape.buffer(0.2 + comp + 0.1)).area   # beyond compensation
    box = (min(min(a[0], b[0]) for a, b in top_segments), min(min(a[1], b[1]) for a, b in top_segments),
           max(max(a[0], b[0]) for a, b in top_segments), max(max(a[1], b[1]) for a, b in top_segments))
    grid, _, _ = preview.density([(a, b, '#000') for a, b in top_segments], box)
    thick = float((grid > 8.5).sum()) * 0.25 * 0.25
    return dict(uncovered=round(uncovered, 3), spill=round(spill, 3), thick=round(thick, 3), trims=trims, stitches=stitches)


def score(measures):
    return sum(WEIGHTS[k] * measures[k] for k in WEIGHTS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('svg')
    parser.add_argument('--size', type=float, required=True, help='size of the whole design, mm')
    parser.add_argument('--fabric')
    parser.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    parser.add_argument('--background', default='#ffffff')
    parser.add_argument('--set', action='append', default=[])
    parser.add_argument('--plan', help='start from this plan')
    parser.add_argument('--only', help='shape numbers (swatch.py --list)')
    parser.add_argument('--angles', action='store_true')
    parser.add_argument('--ref-size', type=float, help='largest size you will make (satin or tatami is chosen there)')
    parser.add_argument('--out', default='plan.json')
    args = parser.parse_args()
    cfg = dict(digitize.FABRICS[args.fabric]) if args.fabric else {}
    cfg['fill_angle'] = args.angle
    for pair in args.set:
        key, value = pair.split('=')
        cfg[key] = float(value)
    plan = json.load(open(args.plan)) if args.plan else {'shapes': {}}
    plan.setdefault('shapes', {})
    elements = design.load(args.svg, args.background)
    everything = unary_union([e['geom'] if e['kind'] == 'fill' else e['geom'].buffer(e.get('width', 0) / 2) for e in elements])
    x0, y0, x1, y1 = everything.bounds
    scale = args.size / max(x1 - x0, y1 - y0)
    reference_scale = (args.ref_size or args.size) / max(x1 - x0, y1 - y0)
    shape_numbers = [int(i) for i in args.only.split(',')] if args.only else range(len(elements))
    merged = dict(digitize.DEFAULTS, **cfg)
    done = []    # (normalised shape, best plan entry) – same letter, same answer
    for i in shape_numbers:
        element = elements[i]
        if element['kind'] != 'fill':
            continue
        at_reference = affinity.scale(element['geom'], reference_scale, reference_scale, origin=(0, 0))
        widths = [2 * q.area / q.length for q in digitize.polys(at_reference.buffer(merged['comp'], join_style=2))]
        kind = plan['shapes'].get(str(i), {}).get('stitch') or ('satin' if widths and max(widths) <= merged['satin_max'] else 'tatami')
        normalised = affinity.translate(element['geom'], -element['geom'].bounds[0], -element['geom'].bounds[1])
        same = next((best for shape, best in done if shape.symmetric_difference(normalised).area < 0.02 * normalised.area), None)
        if same is not None:
            plan['shapes'][str(i)] = dict(plan['shapes'].get(str(i), {}), **same)
            print(f'{i:3} = same shape')
            continue
        base = dict(plan['shapes'].get(str(i), {}))      # stitch type stays as the rules (or the given plan) say
        if kind == 'satin':
            keys = list(SATIN_VARIANTS)
            variants = [dict(zip(keys, values)) for values in itertools.product(*SATIN_VARIANTS.values())]
        elif args.angles and kind == 'tatami':
            variants = [dict(fill_angle=(args.angle + d)) for d in TATAMI_ANGLE_STEPS]
        else:
            variants = [{}]
        results = []
        for variant in variants:
            entry = dict(base, **{k: v for k, v in variant.items() if v is not None})
            measures = measure(element, cfg, scale, reference_scale, entry)
            changed = sum(1 for k, v in variant.items() if v is not None and v != merged.get(k))   # ties: stay near the defaults
            results.append((round(score(measures), 2), changed, entry, measures))
        results.sort(key=lambda r: (r[0], r[1]))
        best_score, _, best, measures = results[0]
        plan['shapes'][str(i)] = best
        done.append((normalised, best))
        print(f'{i:3} {kind:6} {len(variants):3} variants, best {best_score:7.2f} {measures}  {({k: best[k] for k in best if k != "stitch"})}')
    json.dump(plan, open(args.out, 'w'), ensure_ascii=False, indent=1)
    print('->', args.out)


if __name__ == '__main__':
    main()
