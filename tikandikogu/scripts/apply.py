"""Build the sorted library from a plan. The source folder is only read.

python3 apply.py <source> <target> plan.json --machine janome|brother [--hoop 200x200] [--go]

plan.json: [{"src": "kaust/fail.jef", "category": "Lilled/Aster", "name": "Aster", "variant": "1"}, ...]
  category  folder path in the target (diacritics are removed)
  name      design name; sizes of one design share name + variant
  variant   optional; when one name has several variants they get letters A, B, C ...
File name: "<name> [A] <size>", size = longer side in whole mm, padded to 3 places with spaces.
Without --go only prints what it would do.
"""
import argparse, json, os, shutil, sys
from collections import defaultdict
import pyembroidery as pe
from common import MACHINES, ascii_name, size_mm, fits, render

COMPANION = {'jef': ['.jbf']}   # extra machine files kept next to the design


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('plan')
    ap.add_argument('--machine', choices=sorted(MACHINES), required=True); ap.add_argument('--hoop', help='override, e.g. 200x200')
    ap.add_argument('--go', action='store_true')
    a = ap.parse_args()
    src, dst = os.path.realpath(a.src), os.path.realpath(a.dst)
    if dst == src or dst.startswith(src + os.sep):
        sys.exit('Sihtkaust ei tohi olla lähtekausta sees.')
    hoop = tuple(float(v) for v in a.hoop.lower().split('x')) if a.hoop else MACHINES[a.machine]['hoop']
    a.format = MACHINES[a.machine]['format']
    print(f"{MACHINES[a.machine]['model']}: {a.format.upper()}, raam {hoop[0]:g} x {hoop[1]:g} mm")
    plan = json.load(open(a.plan))
    # variant letters per (category, name)
    variants = defaultdict(list)
    for it in plan:
        key = (it['category'], it['name']); v = str(it.get('variant', ''))
        if v not in variants[key]: variants[key].append(v)
    letter = {}
    for key, vs in variants.items():
        vs.sort(key=lambda v: (v != '', v.zfill(6)))      # no number first -> A
        for i, v in enumerate(vs): letter[key + (v,)] = chr(65 + i) if len(vs) > 1 else ''
    seen = {}; report = defaultdict(list)
    for it in plan:
        sp = os.path.join(src, it['src'])
        p = pe.read(sp)
        if p is None: report['ei loe'].append(it['src']); continue
        w, h = size_mm(p)
        if not fits(w, h, hoop): report['ei mahu raami'].append(f"{it['src']} ({w:.0f} x {h:.0f} mm)"); continue
        let = letter[(it['category'], it['name'], str(it.get('variant', '')))]
        base = ascii_name(it['name']) + (f' {let}' if let else '') + f' {round(max(w, h)):>3}'
        folder = os.path.join(dst, *[ascii_name(c) for c in it['category'].split('/')])
        out = os.path.join(folder, base)
        if out in seen: report['sama nimi'].append(f"{it['src']} ja {seen[out]} -> {base}"); continue
        seen[out] = it['src']
        ext = os.path.splitext(sp)[1].lower()[1:]
        conv = ext != a.format
        print(('TEISENDA ' if conv else '') + f"{it['src']} -> {os.path.relpath(out, dst)}.{a.format}")
        if not a.go: continue
        os.makedirs(folder, exist_ok=True)
        if conv:
            if a.format == 'pes':   # Brother needs the origin at the top left corner
                from common import stitch_box
                x0, y0, _, _ = stitch_box(p); p.translate(-x0, -y0)
                pe.write_pes(p, f'{out}.pes', {'version': 6})
            else:
                pe.write(p, f'{out}.{a.format}', {'trims': True} if a.format == 'jef' else None)
            report['teisendatud'].append(it['src'])
        else: shutil.copyfile(sp, f'{out}.{a.format}')          # bytes unchanged
        for cx in COMPANION.get(a.format, []):
            stem = os.path.splitext(sp)[0]
            for f in os.listdir(os.path.dirname(sp)):
                if os.path.join(os.path.dirname(sp), f).lower() == (stem + cx).lower():
                    shutil.copyfile(os.path.join(os.path.dirname(sp), f), out + cx)
        render(p, out + '.bmp')
    for k, v in report.items():
        print(f'\n{k}: {len(v)}'); [print('  ' + x) for x in v]
    if not a.go: print('\nProovisõit. Käivita --go, et failid teha.')


if __name__ == '__main__':
    main()
