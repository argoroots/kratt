"""Try many digitizing variants per shape and keep the best (writes plan.json for gen.py --plan).

python3 optimize.py pilt.svg --size 150 [--fabric linane] [--angle 45] [--set k=v] [--plan vana.json]
       [--only 10,11,0] [--angles] [--out plan.json]

Every shape is stitched alone in every variant and measured (thread counted 0.3 mm wide):
  uncovered  area of the shape the thread does not cover, mm2
  spill      thread outside the shape beyond the compensation (+0.1 mm), mm2
  thick      area with more than 8.5 mm of thread per mm2
  trims, stitches
score = sum of WEIGHTS * measure; the lowest wins. Identical shapes (same letter) are tried once.
Satin shapes: corner handling, wedge reach, gap fill, underlay. Tatami: with --angles also the row angle
(otherwise the angle stays as given - it changes the look, so it is the user's choice).
"""
import argparse, itertools, json, math
import pyembroidery as pe
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely import affinity
import design, digitize, preview

WEIGHTS = dict(uncovered=40.0, spill=15.0, thick=10.0, trims=1.0, stitches=0.002)

# underlay is not tried: its effect (fabric held, stitches raised) cannot be measured here; it follows the rules
SATIN_VARIANTS = dict(satin_mitre=[0, 70, 100, 130], satin_reach=[0, 1.5], satin_gap=[0.15, 0.3])


def measure(e, cfg, scale, ref_scale, plan_shape):
    p = digitize.build([e], 0, {}, cfg, plan={'shapes': {'0': plan_shape}} if plan_shape else None,
                       scale=scale, ref_scale=ref_scale)
    s = p.scale_mm; tx, ty = p.offset
    shape = affinity.translate(affinity.scale(e['geom'], s, s, origin=(0, 0)), tx / 10, ty / 10)
    if e['kind'] == 'run': shape = shape.buffer(0.2)
    U = set(map(tuple, p.underlay))
    segs, prev, trims, last = [], None, 0, None
    for x, y, c in p.stitches:
        c &= pe.COMMAND_MASK
        if c == pe.STITCH:
            if prev and not ((prev[0] * 10, prev[1] * 10) in U and (x, y) in U): segs.append((prev, (x / 10, y / 10)))
            prev = (x / 10, y / 10)
        else:
            if c == pe.TRIM and last == pe.STITCH: trims += 1
            prev = None if c == pe.TRIM else ((x / 10, y / 10) if c == pe.JUMP else prev)
        if c in (pe.STITCH, pe.TRIM): last = c
    n = sum(1 for q in p.stitches if (q[2] & pe.COMMAND_MASK) == pe.STITCH)
    if not segs: return dict(uncovered=shape.area, spill=0, thick=0, trims=trims, stitches=n)
    # thread counted narrower than it is (0.3 mm): on fabric it is pulled in, so a corner that 0.4 mm thread
    # only just reaches stays open in the stitch-out
    cov = unary_union([LineString([a, b]).buffer(0.15, cap_style=1) for a, b in segs if a != b])
    inner = shape.buffer(-0.05)
    unc = inner.difference(cov).area if not inner.is_empty else 0.0
    spill = cov.difference(shape.buffer(0.2 + float(cfg.get('comp', digitize.DEFAULTS['comp'])) + 0.1)).area   # beyond compensation
    g, _, _ = preview.density([(a, b, '#000') for a, b in segs],
                              (min(min(a[0], b[0]) for a, b in segs), min(min(a[1], b[1]) for a, b in segs),
                               max(max(a[0], b[0]) for a, b in segs), max(max(a[1], b[1]) for a, b in segs)))
    thick = float((g > 8.5).sum()) * 0.25 * 0.25
    return dict(uncovered=round(unc, 3), spill=round(spill, 3), thick=round(thick, 3), trims=trims, stitches=n)


def score(m):
    return sum(WEIGHTS[k] * m[k] for k in WEIGHTS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('svg'); ap.add_argument('--size', type=float, required=True, help='size of the whole design, mm')
    ap.add_argument('--fabric'); ap.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    ap.add_argument('--background', default='#ffffff')
    ap.add_argument('--set', action='append', default=[]); ap.add_argument('--plan', help='start from this plan')
    ap.add_argument('--only', help='shape numbers (swatch.py --list)'); ap.add_argument('--angles', action='store_true')
    ap.add_argument('--ref-size', type=float, help='largest size you will make (satin or tatami is chosen there)')
    ap.add_argument('--out', default='plan.json')
    a = ap.parse_args()
    cfg = dict(digitize.FABRICS[a.fabric]) if a.fabric else {}
    cfg['fill_angle'] = a.angle
    for kv in a.set:
        k, v = kv.split('='); cfg[k] = float(v)
    plan = json.load(open(a.plan)) if a.plan else {'shapes': {}}
    plan.setdefault('shapes', {})
    els = design.load(a.svg, a.background)
    allg = unary_union([e['geom'] if e['kind'] == 'fill' else e['geom'].buffer(e.get('width', 0) / 2) for e in els])
    x0, y0, x1, y1 = allg.bounds; scale = a.size / max(x1 - x0, y1 - y0)
    rscale = (a.ref_size or a.size) / max(x1 - x0, y1 - y0)
    ids = [int(i) for i in a.only.split(',')] if a.only else range(len(els))
    c = dict(digitize.DEFAULTS, **cfg)
    done = []    # (normalised shape, best plan entry) – same letter, same answer
    for i in ids:
        e = els[i]
        if e['kind'] != 'fill': continue
        ws = [2 * q.area / q.length for q in digitize.polys(affinity.scale(e['geom'], rscale, rscale, origin=(0, 0)).buffer(c['comp'], join_style=2))]
        kind = plan['shapes'].get(str(i), {}).get('stitch') or ('satin' if ws and max(ws) <= c['satin_max'] else 'tatami')
        g0 = affinity.translate(e['geom'], -e['geom'].bounds[0], -e['geom'].bounds[1])
        hit = next((best for g, best in done if g.symmetric_difference(g0).area < 0.02 * g0.area), None)
        if hit is not None:
            plan['shapes'][str(i)] = dict(plan['shapes'].get(str(i), {}), **hit); print(f'{i:3} = sama kuju'); continue
        base = dict(plan['shapes'].get(str(i), {}))      # stitch type stays as the rules (or the given plan) say
        if kind == 'satin':
            keys = list(SATIN_VARIANTS); combos = [dict(zip(keys, v)) for v in itertools.product(*SATIN_VARIANTS.values())]
        elif a.angles:
            combos = [dict(fill_angle=(a.angle + d)) for d in (0, 15, -15, 30, -30, 45, -45, 90)]
        else: combos = [{}]
        res = []
        for v in combos:
            ent = dict(base, **{k: x for k, x in v.items() if x is not None})
            m = measure(e, cfg, scale, rscale, ent)
            changed = sum(1 for k, x in v.items() if x is not None and x != c.get(k))   # ties: stay near the defaults
            res.append((round(score(m), 2), changed, ent, m))
        res.sort(key=lambda r: (r[0], r[1])); sc, _, best, m = res[0]
        plan['shapes'][str(i)] = best; done.append((g0, best))
        print(f'{i:3} {kind:6} {len(combos):3} varianti, parim {sc:7.2f} {m}  {({k: best[k] for k in best if k != "stitch"})}')
    json.dump(plan, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('->', a.out)


if __name__ == '__main__':
    main()
