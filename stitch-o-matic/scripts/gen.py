"""Make embroidery files from an SVG.

python3 gen.py logo.svg --name "Name" --sizes 100,150,200 --machines brother,janome [--working working.pes]
       [--color "#rrggbb=Thread name"] [--angle 45] [--background "#ffffff"] [--set satin_max=2.5] [--plan plan.json]
       [--exact] [--scales 0.5688,0.86]

--sizes: longer side of the design in mm (stitches come out a little bigger: pull compensation).
--exact: --sizes are the stitched size (longer side of the stitches); the scale is adjusted until
         the stitches measure that, to 0.05 mm.
--scales: mm per SVG unit, one per file, instead of --sizes: the same scale as another design drawn
         in the same SVG coordinates (e.g. the mark alone, as big as in the logo with text). gen.py
         prints the scale of every file and keeps it in meta.json.

Writes out/<Name> <size>.pes (+ .jef, .bmp), outpos/ (PES v6, underlay points), out/meta.json.
<size> = longer side in mm, 3 places padded with spaces.
"""
import argparse, json, math, os, datetime
import pyembroidery as pe
from pyembroidery.EmbThreadPec import get_thread_set as pec_threads
from pyembroidery.EmbThreadJef import get_thread_set as jef_threads
import design, digitize
from shapely import affinity

# machines we make files for: format, largest embroidery area (mm)
STABILIZERS = ('cutaway', 'mesh', 'tearaway', 'washaway-film', 'washaway-fiber', 'fusible', 'sticky')
MACHINES = {'brother': ('pes', 'Brother Innov-is V3', (300, 180)), 'janome': ('jef', 'Janome Memory Craft 550E', (200, 360))}



def ascii_name(s):
    """machine screen name in plain ASCII: the PES header stores its length in characters, so a UTF-8
    letter (ä, õ) shifts everything after it and the file is unreadable"""
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFKD', s) if ord(ch) < 128)

def nearest(hexcol, palette):
    t = pe.EmbThread(); t.set_hex_color(hexcol)
    i = t.find_nearest_color_index(palette); n = palette[i]
    return dict(code=str(n.catalog_number) if n.catalog_number else f'nr {i}', name=n.description, hex=n.hex_color())


def bmp(p, fn):
    """preview: 400x400, light grey background, line broken at jumps"""
    from PIL import Image, ImageDraw
    st = [(x, y, c & pe.COMMAND_MASK) for x, y, c in p.stitches]
    xs = [x for x, y, c in st if c == pe.STITCH]; ys = [y for x, y, c in st if c == pe.STITCH]
    W = 400; m = 20; s = (W - 2 * m) / max(max(xs) - min(xs), max(ys) - min(ys))
    ox = (W - (max(xs) - min(xs)) * s) / 2 - min(xs) * s; oy = (W - (max(ys) - min(ys)) * s) / 2 - min(ys) * s
    im = Image.new('RGB', (W, W), (236, 236, 236)); d = ImageDraw.Draw(im)
    ti = 0; col = p.threadlist[0].hex_color(); prev = None
    for x, y, c in st:
        if c == pe.COLOR_CHANGE:
            ti += 1; col = p.threadlist[min(ti, len(p.threadlist) - 1)].hex_color()
        if c == pe.STITCH:
            if prev: d.line([prev, (ox + x * s, oy + y * s)], fill=col, width=1)
            prev = (ox + x * s, oy + y * s)
        else: prev = None
    im.save(fn, 'BMP')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('svg'); ap.add_argument('--name', required=True)
    ap.add_argument('--sizes', help='longer side in mm, e.g. 100,150')
    ap.add_argument('--exact', action='store_true', help='--sizes are the stitched size, not the design size')
    ap.add_argument('--scales', help='mm per SVG unit, one per file (instead of --sizes)')
    ap.add_argument('--working', help='working PES v10 file for the target machine')
    ap.add_argument('--color', action='append', default=[], help='"#rrggbb=thread name"')
    ap.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    ap.add_argument('--background', default='#ffffff')
    ap.add_argument('--fabric', help='fabric: ' + ', '.join(digitize.FABRICS))
    ap.add_argument('--thread', type=int, default=40, choices=sorted(digitize.THREADS), help='thread weight: 40 (normal) or 60 (thin, small text)')
    ap.add_argument('--plan', help='plan.json: decisions per shape (see digitize.build)')
    ap.add_argument('--set', action='append', default=[], help='parameter=value (see digitize.DEFAULTS)')
    ap.add_argument('--stabilizer', help='backing under the fabric: ' + ', '.join(STABILIZERS) + '; combine with +, e.g. cutaway+fusible')
    ap.add_argument('--topping', help='topping on the fabric: ' + ', '.join(STABILIZERS))
    ap.add_argument('--hoop', help='embroidery area of the hoop in mm, e.g. 130x180 (default: the largest hoop of the machine)')
    ap.add_argument('--machines', required=True, help='brother, janome or both: brother,janome')
    a = ap.parse_args()
    mach = [m.strip().lower() for m in a.machines.split(',') if m.strip()]
    for opt in (a.stabilizer, a.topping):
        for v in (opt or '').split('+'):
            if v and v not in STABILIZERS: ap.error(f'unknown stabilizer {v}: ' + ', '.join(STABILIZERS))
    fmts = [MACHINES[m][0] for m in mach]
    cfg = dict(digitize.FABRICS[a.fabric]) if a.fabric else {}
    cfg['fill_angle'] = a.angle
    cfg = digitize.thread_cfg(cfg, a.thread)              # 60 wt: denser, narrower (scaled from the fabric's values)
    for kv in a.set:
        k, v = kv.split('='); cfg[k] = float(v)
    names = {k.lower(): v for k, v in (kv.split('=', 1) for kv in a.color)}
    els = design.load(a.svg, a.background)
    os.makedirs('outpos', exist_ok=True); os.makedirs('out', exist_ok=True)
    meta = dict(name=a.name, date=datetime.date.today().isoformat(), params=dict(digitize.DEFAULTS, **cfg),
                fabric=a.fabric or '', thread=a.thread, plan=a.plan or '',
                choices=dict(machines=mach, hoop=a.hoop or '', sizes=a.sizes or '', scales=a.scales or '', exact=a.exact, fabric=a.fabric or '',
                             stabilizer=a.stabilizer or '', topping=a.topping or '', thread=a.thread, angle=a.angle, sets=a.set,
                             colors=a.color, plan=os.path.basename(a.plan) if a.plan else '', working=os.path.basename(a.working) if a.working else ''), format=('PES v10' if a.working else 'PES v6') if 'pes' in fmts else '', jef='jef' in fmts, files=[], colors=[])
    for col in dict.fromkeys(e['color'] for e in els):
        meta['colors'].append(dict(hex=col, name=names.get(col, col), brother=nearest(col, pec_threads()),
                                   janome=nearest(col, jef_threads())))
    if bool(a.sizes) == bool(a.scales): ap.error('give --sizes or --scales')
    plan = json.load(open(a.plan)) if a.plan else None
    measure = lambda p_: (lambda st_: ((max(x for x, y in st_) - min(x for x, y in st_)) / 10, (max(y for x, y in st_) - min(y for x, y in st_)) / 10))(
        [(x, y) for x, y, c in p_.stitches if (c & pe.COMMAND_MASK) == pe.STITCH])
    if a.scales:
        scales = [float(v) for v in a.scales.split(',')]
        jobs = [dict(scale=sc, ref_scale=max(scales)) for sc in scales]
    else:
        sizes = [float(v) for v in a.sizes.split(',')]
        jobs = [dict(size=sz, ref_size=max(sizes)) for sz in sizes]
    for job in jobs:
        if 'scale' in job:
            p = digitize.build(els, 1.0, names, cfg, plan=plan, scale=job['scale'], ref_scale=job['ref_scale'])
        else:
            want = job['size']; size = want
            p = digitize.build(els, size, names, cfg, ref_size=job['ref_size'], plan=plan)
            for _ in range(4 if a.exact else 0):          # stitched size = want: scale by the measured ratio
                got = max(measure(p))
                if abs(got - want) < 0.05: break
                size *= want / got
                p = digitize.build(els, size, names, cfg, ref_size=job['ref_size'], plan=plan)
            if a.exact and abs(max(measure(p)) - want) >= 0.05:
                print(f'WARNING: {want} mm: stitches {max(measure(p)):.2f} mm after 4 tries')
        st = [(x, y) for x, y, c in p.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
        w, h = measure(p)
        n = round(max(w, h)); fn = f'{a.name} {n:>3}'
        label = f'{ascii_name(a.name)[:8 - len(str(n)) - 1]} {n}'[:8]   # name on the machine screen (8 chars)
        for m in mach:
            _, mname, (HW, HH) = MACHINES[m]
            if a.hoop: HW, HH = (float(v) for v in a.hoop.lower().replace('×', 'x').split('x')); mname = 'chosen'
            if not ((w <= HW and h <= HH) or (w <= HH and h <= HW)):
                print(f'WARNING: {fn} ({w:.0f} x {h:.0f} mm) does not fit the {mname} hoop {HW:g} x {HH:g} mm')
        if 'jef' in fmts:                                    # Janome: centred
            pe.write_jef(p, f'out/{fn}.jef', {'trims': True}); bmp(p, f'out/{fn}.bmp')
        dx, dy = -math.floor(min(x for x, y in st) + 0.5), -math.floor(min(y for x, y in st) + 0.5)   # min rounds to 0
        p.translate(dx, dy)                                  # Brother: origin top left
        json.dump([(x + dx, y + dy) for x, y in p.underlay], open(f'outpos/{fn}.under.json', 'w'))
        json.dump(dict(comp=getattr(p, 'comp', 0.2), thread_mm=getattr(p, 'thread_mm', 0.35), shapes=[dict(id=sh['id'], kind=sh['kind'], stitch=sh['stitch'], width=sh['width'], margin=sh.get('margin', 0),
                   wkt=affinity.translate(sh['geom'], dx, dy).wkt) for sh in getattr(p, 'shapes', [])]), open(f'outpos/{fn}.shapes.json', 'w'))
        p.metadata('name', label)
        pe.write_pes(p, f'outpos/{fn}.pes', {'version': 6})
        import coverage                                      # uncovered spots inside shapes (cracks, wedges, gaps)
        for line in coverage.report(f'outpos/{fn}.pes'): print(f'WARNING: {fn}: {line}')
        if 'pes' not in fmts:
            pass
        elif a.working:
            import pes10
            pes10.to_v10(f'outpos/{fn}.pes', f'out/{fn}.pes', a.working, label)
        else:
            import shutil; shutil.copy(f'outpos/{fn}.pes', f'out/{fn}.pes')
        meta['kinds'] = sorted(set(meta.get('kinds', [])) | set(getattr(p, 'kinds', [])))
        hx = [k['hex'].lower() for k in meta['colors']]        # thread block -> colour row (a machine stop repeats a colour)
        meta['blocks'] = [hx.index(t.hex_color().lower()) if t.hex_color().lower() in hx else min(i, len(hx) - 1)
                          for i, t in enumerate(p.threadlist)]
        meta['stops'] = list(getattr(p, 'stops', []))
        meta['files'].append(dict(file=fn, w=round(w, 1), h=round(h, 1), label=label, scale=round(p.scale_mm, 6)))
        print(fn, f'{w:.1f} x {h:.1f} mm', len(st), 'stitches', f'scale {p.scale_mm:.6f} mm/unit')
    json.dump(meta, open('out/meta.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
