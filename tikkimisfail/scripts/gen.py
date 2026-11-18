"""Make embroidery files from an SVG.

python3 gen.py logo.svg --name "Nimi" --sizes 100,150,200 --machines brother,janome [--working toimiv.pes]
       [--color "#rrggbb=Niidi nimi"] [--angle 45] [--background "#ffffff"] [--set satin_max=2.5]

Writes out/<Nimi> <size>.pes (+ .jef, .bmp), outpos/ (PES v6, underlay points), out/meta.json.
<size> = longer side in mm, 3 places padded with spaces.
"""
import argparse, json, math, os, datetime
import pyembroidery as pe
from pyembroidery.EmbThreadPec import get_thread_set as pec_threads
from pyembroidery.EmbThreadJef import get_thread_set as jef_threads
import design, digitize

# machines we make files for: format, largest embroidery area (mm)
MACHINES = {'brother': ('pes', 'Brother Innov-is V3', (300, 180)), 'janome': ('jef', 'Janome Memory Craft 550E', (200, 360))}


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
    ap.add_argument('--sizes', required=True, help='longer side in mm, e.g. 100,150')
    ap.add_argument('--working', help='working PES v10 file for the target machine')
    ap.add_argument('--color', action='append', default=[], help='"#rrggbb=thread name"')
    ap.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    ap.add_argument('--background', default='#ffffff')
    ap.add_argument('--set', action='append', default=[], help='parameter=value (see digitize.DEFAULTS)')
    ap.add_argument('--machines', required=True, help='brother, janome or both: brother,janome')
    a = ap.parse_args()
    mach = [m.strip().lower() for m in a.machines.split(',') if m.strip()]
    fmts = [MACHINES[m][0] for m in mach]
    cfg = {'fill_angle': a.angle}
    for kv in a.set:
        k, v = kv.split('='); cfg[k] = float(v)
    names = {k.lower(): v for k, v in (kv.split('=', 1) for kv in a.color)}
    els = design.load(a.svg, a.background)
    os.makedirs('outpos', exist_ok=True); os.makedirs('out', exist_ok=True)
    meta = dict(name=a.name, date=datetime.date.today().isoformat(), params=dict(digitize.DEFAULTS, **cfg),
                format=('PES v10' if a.working else 'PES v6') if 'pes' in fmts else '', jef='jef' in fmts, files=[], colors=[])
    for col in dict.fromkeys(e['color'] for e in els):
        meta['colors'].append(dict(hex=col, name=names.get(col, col), brother=nearest(col, pec_threads()),
                                   janome=nearest(col, jef_threads())))
    sizes = [float(v) for v in a.sizes.split(',')]
    for size in sizes:
        p = digitize.build(els, size, names, cfg, ref_size=max(sizes))
        st = [(x, y) for x, y, c in p.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
        w = (max(x for x, y in st) - min(x for x, y in st)) / 10; h = (max(y for x, y in st) - min(y for x, y in st)) / 10
        n = round(max(w, h)); fn = f'{a.name} {n:>3}'
        label = f'{a.name[:8 - len(str(n)) - 1]} {n}'[:8]   # name on the machine screen (8 chars)
        for m in mach:
            _, mname, (HW, HH) = MACHINES[m]
            if not ((w <= HW and h <= HH) or (w <= HH and h <= HW)):
                print(f'HOIATUS: {fn} ({w:.0f} x {h:.0f} mm) ei mahu {mname} raami {HW} x {HH} mm')
        if 'jef' in fmts:                                    # Janome: centred
            pe.write_jef(p, f'out/{fn}.jef', {'trims': True}); bmp(p, f'out/{fn}.bmp')
        dx, dy = -math.floor(min(x for x, y in st) + 1e-6), -math.floor(min(y for x, y in st) + 1e-6)
        p.translate(dx, dy)                                  # Brother: origin top left
        json.dump([(x + dx, y + dy) for x, y in p.underlay], open(f'outpos/{fn}.under.json', 'w'))
        p.metadata('name', label)
        pe.write_pes(p, f'outpos/{fn}.pes', {'version': 6})
        if 'pes' not in fmts:
            pass
        elif a.working:
            import pes10
            pes10.to_v10(f'outpos/{fn}.pes', f'out/{fn}.pes', a.working, label)
        else:
            import shutil; shutil.copy(f'outpos/{fn}.pes', f'out/{fn}.pes')
        meta['files'].append(dict(file=fn, w=round(w, 1), h=round(h, 1), label=label))
        print(fn, f'{w:.1f} x {h:.1f} mm', len(st), 'stitches')
    json.dump(meta, open('out/meta.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
