"""Catalogue PDF of a sorted library.

python3 catalog.py <library> [--out Tikandimustrid.pdf] [--title Tikandimustrid] [--subtitle "masin, raam"]
                   [--names names.json] [--ext jef]

Sections = folders, one tile per design (preview + name + sizes in mm).
names.json maps words without diacritics to how they are shown, e.g. {"Ounapuu": "Õunapuu"}.
"""
import argparse, json, os, re
from collections import OrderedDict
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

RX = re.compile(r'^(.*?) +(\d{1,3})$')


def font():
    """a TTF font with Estonian letters if available, else Helvetica"""
    for reg, bold in [('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                      ('/Library/Fonts/Arial Unicode.ttf', '/Library/Fonts/Arial Unicode.ttf')]:
        if os.path.exists(reg):
            pdfmetrics.registerFont(TTFont('F', reg)); pdfmetrics.registerFont(TTFont('FB', bold)); return 'F', 'FB'
    return 'Helvetica', 'Helvetica-Bold'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('lib'); ap.add_argument('--out', default='Tikandimustrid.pdf')
    ap.add_argument('--title', default='Tikandimustrid'); ap.add_argument('--subtitle', default='')
    ap.add_argument('--names'); ap.add_argument('--ext', default='jef')
    a = ap.parse_args()
    DIA = json.load(open(a.names)) if a.names else {}
    et = lambda t: ' '.join(DIA.get(w, w) for w in t.split(' '))
    groups = OrderedDict()
    for r, ds, fs in sorted(os.walk(a.lib)):
        ds.sort()
        sec = os.path.relpath(r, a.lib).replace(os.sep, ' / ')
        for f in sorted(fs):
            if not f.lower().endswith('.' + a.ext): continue
            stem = f[:-len(a.ext) - 1]; m = RX.match(stem)
            base, val = (m.group(1), int(m.group(2))) if m else (stem, 0)
            groups.setdefault(sec, OrderedDict()).setdefault(base, []).append((val, os.path.join(r, stem + '.bmp')))
    R, B = font()
    W, H = A4; M = 36; cols = 4; G = 16; img = (W - 2 * M - (cols - 1) * G) / cols; RG = 12
    c = canvas.Canvas(a.out, pagesize=A4); c.setTitle(a.title)
    st = dict(y=H - M, page=1, n=0)

    def footer():
        c.setFont(R, 8); c.setFillColor(HexColor('#888888')); c.drawCentredString(W / 2, M / 2 - 3, str(st['page'])); c.setFillColor(HexColor('#000000'))

    def newpage():
        footer(); c.showPage(); st['page'] += 1; st['y'] = H - M

    def rowh(row):   # sizes: up to 5 per line, height grows with the longest list
        return img + 22 + 9 * (max(min(3, (len(l) + 4) // 5) for _, l in row) - 1) + 3

    c.setFont(B, 22); c.drawString(M, st['y'] - 20, a.title)
    c.setFont(R, 10)
    if a.subtitle: c.drawString(M, st['y'] - 38, a.subtitle)
    c.drawString(M, st['y'] - 52, 'Suurused on millimeetrites (mustri pikem külg).')
    st['y'] -= 72
    for sec, items in groups.items():
        its = list(items.items()); rows = [its[k:k + cols] for k in range(0, len(its), cols)]
        if st['y'] - 28 - rowh(rows[0]) < M: newpage()
        c.setFont(B, 14); c.drawString(M, st['y'] - 16, et(sec)); c.setLineWidth(0.5); c.line(M, st['y'] - 20, W - M, st['y'] - 20); st['y'] -= 28
        for row in rows:
            h = rowh(row)
            if st['y'] - h < M: newpage()
            y = st['y']
            for col, (base, lst) in enumerate(row):
                lst.sort(key=lambda t: t[0]); st['n'] += 1
                x = M + col * (img + G); prev = lst[len(lst) // 2][1]
                if os.path.exists(prev):
                    c.saveState(); pth = c.beginPath(); pth.roundRect(x, y - img, img, img, 7)
                    c.clipPath(pth, stroke=0, fill=0); c.drawImage(ImageReader(prev), x, y - img, img, img); c.restoreState()
                c.setFont(B, 8.5); c.drawCentredString(x + img / 2, y - img - 11, et(base)[:32])
                parts = [('%g' % v if v else '') for v, _ in lst]
                lines = [parts[k:k + 5] for k in range(0, len(parts), 5)]
                c.setFont(R, 7.5); slot = img / 5
                for li, ln in enumerate(lines[:3]):
                    x0 = x + (5 - len(ln)) * slot / 2
                    for j, t in enumerate(ln): c.drawCentredString(x0 + j * slot + slot / 2, y - img - 22 - li * 9, t)
            st['y'] -= h + RG
        st['y'] -= 10
    footer(); c.save(); print('mustreid', st['n'], 'lehti', st['page'])


if __name__ == '__main__':
    main()
