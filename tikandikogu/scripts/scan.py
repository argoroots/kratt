"""Inventory of a design folder (read only).

python3 scan.py <source folder> --machine janome|brother [--hoop 200x200] [--sheets sheets/]

Writes inventory.json: one entry per design file (path, format, size mm, stitches, colours,
fits hoop, companion files) and, with --sheets, contact sheets (PNG, 6x5 previews with file
names) for looking at the designs and deciding categories and names.
"""
import argparse, json, os, sys
import pyembroidery as pe
from common import MACHINES, DESIGN_EXT, size_mm, fits, render


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('--machine', choices=sorted(MACHINES), required=True); ap.add_argument('--hoop', help='override, e.g. 200x200')
    ap.add_argument('--sheets'); ap.add_argument('--out', default='inventory.json')
    a = ap.parse_args()
    hoop = tuple(float(v) for v in a.hoop.lower().split('x')) if a.hoop else MACHINES[a.machine]['hoop']
    inv = []
    for r, ds, fs in os.walk(a.src):
        ds.sort()
        low = {f.lower(): f for f in fs}
        for f in sorted(fs):
            if not f.lower().endswith(DESIGN_EXT): continue
            path = os.path.join(r, f)
            try: p = pe.read(path)
            except Exception as e: p = None
            if p is None or not p.stitches:
                inv.append(dict(path=os.path.relpath(path, a.src), error='ei loe')); continue
            w, h = size_mm(p)
            stem = os.path.splitext(f)[0].lower()
            extra = [low[k] for k in low if k.startswith(stem + '.') and not k.endswith(DESIGN_EXT)]
            inv.append(dict(path=os.path.relpath(path, a.src), format=os.path.splitext(f)[1].lower()[1:],
                            w=round(w, 1), h=round(h, 1), stitches=p.count_stitch_commands(pe.STITCH),
                            colors=len(p.threadlist), fits=fits(w, h, hoop), extra=extra))
    json.dump(inv, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(len(inv), 'faili;', sum(1 for i in inv if not i.get('fits', True)), 'ei mahu raami;',
          sum(1 for i in inv if 'error' in i), 'ei loe')
    if a.sheets:
        from PIL import Image, ImageDraw
        os.makedirs(a.sheets, exist_ok=True)
        ok = [i for i in inv if 'error' not in i]
        T = 200; C, R = 6, 5
        for k in range(0, len(ok), C * R):
            sheet = Image.new('RGB', (C * T, R * (T + 28)), 'white'); d = ImageDraw.Draw(sheet)
            for j, it in enumerate(ok[k:k + C * R]):
                tmp = '/tmp/_scan_prev.png'
                render(pe.read(os.path.join(a.src, it['path'])), tmp, S=T)
                x, y = (j % C) * T, (j // C) * (T + 28)
                sheet.paste(Image.open(tmp), (x, y))
                d.text((x + 3, y + T + 2), f"{k + j}: {it['path'][-30:]}", fill='black')
                d.text((x + 3, y + T + 14), f"{it['w']} x {it['h']} mm", fill='gray')
            sheet.save(os.path.join(a.sheets, f'leht_{k // (C * R) + 1:02d}.png'))


if __name__ == '__main__':
    main()
