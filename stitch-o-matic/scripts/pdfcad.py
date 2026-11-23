import math
import os
import datetime
import pyembroidery as pe
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.platypus import Paragraph, Table, TableStyle, Frame, Spacer
from reportlab.lib.styles import ParagraphStyle

import json
O = 'out/'
META = json.load(open(O + 'meta.json'))          # written by gen.py
NAME = META['name']
EXT = '.pes' if META['format'] else '.jef'
FILES = [f['file'] + EXT for f in META['files']]
FMT = ('Brother ' + META['format'] + (' + Janome JEF' if META.get('jef') else '')) if META['format'] else 'Janome JEF'
COLS = META['colors']
DATE = datetime.date.fromisoformat(META['date']).strftime('%d.%m.%Y')
PR = META['params']
# outline passes: global setting, or the largest per-shape value from the plan
OUTLINE_N = int(PR.get('fill_outline') or 0)
if not OUTLINE_N and META.get('plan'):
    try:
        OUTLINE_N = max([int(v.get('fill_outline', 0)) for v in json.load(open(META['plan'])).get('shapes', {}).values()] + [0])
    except (OSError, ValueError):
        pass
OUTLINE_N = OUTLINE_N or 1
KIND = set(META.get('kinds') or ['run', 'satin', 'tatami'])   # older meta.json: say everything
num = lambda v: (f'{v:.2f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v)).replace('.', ',')
INK = HexColor('#1a1a1a'); GREY = HexColor('#8a8a8a'); LIGHT = HexColor('#d0d0d0')

def load(f):
    p = pe.read(O + f); st = []; cur = []; trims = 0; last = None; ci = 0
    BL = META.get('blocks')   # thread block -> colour row, from gen.py (a machine stop repeats a colour)
    col = lambda i: BL[min(i, len(BL) - 1)] if BL else min(i, len(COLS) - 1)
    for x, y, c in p.stitches:
        c &= pe.COMMAND_MASK
        if c == pe.STITCH: cur.append((x / 10, y / 10))
        else:
            if len(cur) > 1: st.append((col(ci), cur))
            cur = []
        if c == pe.COLOR_CHANGE: ci += 1
        if c == pe.TRIM and last == pe.STITCH: trims += 1
        if c in (pe.STITCH, pe.TRIM): last = c
    if len(cur) > 1: st.append((col(ci), cur))
    xs = [x for _, s in st for x, y in s]; ys = [y for _, s in st for x, y in s]
    import json, os
    uf = 'outpos/' + f[:-4] + '.under.json'
    U = set(tuple(v) for v in json.load(open(uf))) if os.path.exists(uf) else set()
    return dict(f=f, st=st, U=U, x0=min(xs), y0=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys),
                n=p.count_stitch_commands(pe.STITCH), t=trims)
D = {f: load(f) for f in FILES}
fmt = lambda v: f'{v:.1f}'.replace('.', ',')
COVER = 1                       # cover pages; found by a trial run below (many colours spill to page 2)
PAGES = COVER + 3 * len(FILES)
FABRIC = os.environ.get('FABRIC', '#f2efe8')   # fabric colour in the look drawing

# ---------------- cover (portrait)
def cover(c):
    W, H = A4
    st = ParagraphStyle('b', fontName='Helvetica', fontSize=9.5, leading=13, spaceAfter=3)
    sm = ParagraphStyle('s', parent=st, fontSize=8.5, leading=11)
    h1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=17, leading=21, spaceAfter=4)
    h2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=28, spaceAfter=8)
    bl = ParagraphStyle('bl', parent=st, leftIndent=12, bulletIndent=2, spaceAfter=2)
    B = lambda x: Paragraph(x, bl, bulletText='•')
    def tbl(rows, widths, right=()):
        t = Table(rows, colWidths=widths, hAlign='LEFT', repeatRows=1)
        sty = [('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8.5), ('FONT', (0, 1), (-1, -1), 'Helvetica', 8.5),
               ('LINEBELOW', (0, 0), (-1, 0), 0.6, black), ('LINEBELOW', (0, 1), (-1, -1), 0.25, LIGHT),
               ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
        for col in right: sty.append(('ALIGN', (col, 0), (col, -1), 'RIGHT'))
        t.setStyle(TableStyle(sty)); return t
    rows = [['Leht', 'Fail', 'Mõõdud (L × K)', 'Pisted', 'Lõiked']]
    for i, f in enumerate(FILES):
        d = D[f]; rows.append([f'{COVER + 1 + 3 * i}–{COVER + 3 + 3 * i}', f, f"{fmt(d['w'])} × {fmt(d['h'])} mm", str(d['n']), str(d['t'])])
    files_t = tbl(rows, [16 * mm, 58 * mm, 38 * mm, 20 * mm, 18 * mm], right=(3, 4))
    crow = [['Nr', '', 'Originaal', '', 'Brother', '', 'Janome']]
    for i, k in enumerate(COLS, start=1):
        crow.append([str(i), '', f"{k['name']}  {k['hex'].upper()}" if k['name'] != k['hex'] else k['hex'].upper(), '',
                     f"{k['brother']['code']} {k['brother']['name']}", '', f"{k['janome']['code']} {k['janome']['name']}"])
    col_t = tbl(crow, [9 * mm, 6 * mm, 45 * mm, 6 * mm, 50 * mm, 6 * mm, 48 * mm])
    cst = []
    for r, k in enumerate(COLS, start=1):
        cst += [('BACKGROUND', (1, r), (1, r), HexColor(k['hex'])), ('BACKGROUND', (3, r), (3, r), HexColor(k['brother']['hex'])),
                ('BACKGROUND', (5, r), (5, r), HexColor(k['janome']['hex']))]
    col_t.setStyle(TableStyle(cst))
    test_t = tbl([[Paragraph('<b>Proovil näed</b>', sm), Paragraph('<b>Muuda failis</b>', sm)]] + [[Paragraph(a, sm), Paragraph(b, sm)] for a, b in [
        ('Täidis hõre, kangas paistab läbi', f"Reavahe {num(PR['fill_spacing'])} → väiksemaks (0,1 mm kaupa)"),
        ('Satiin hõre', f"Satiini tihedus {num(PR['satin_spacing'])} → 0,35 mm"),
        ('Kitsad kohad, servas vahed', f"Tõmbekompensatsioon {num(PR['comp'])} → +0,05 mm"),
        ('Tähtede augud kinni', f"Tõmbekompensatsioon {num(PR['comp'])} → −0,05 mm"),
        ('Kangas kortsub', 'Reavahe suuremaks, tugevam tugimaterjal'),
        ('Niit katkeb / nõel murdub ühes kohas', 'Hõrenda seda kohta'),
        ('Kinnitus harutub', 'Kinnitus 3× edasi-tagasi, 0,7–1,0 mm'),
        ('Väike kiri loetamatu', 'Suurem suurus')]],
        [80 * mm, 90 * mm])
    test_t.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2)]))
    labels = ' / '.join(f['label'] for f in META['files'])
    story = [Paragraph(f'{NAME} – tikkimisfailid', h1),
             Paragraph(f"{FMT} · {len(FILES)} faili · {DATE}", sm),
             Paragraph('Failid', h2), files_t, Spacer(1, 3),
             Paragraph(f'Nimi masinas: {labels}.', sm),
             Paragraph('Värvid', h2), col_t,
             Paragraph('Kuidas on tehtud', h2),
             *([B(f"Laiad kujundid: servaalustikk + ristialustikk ({num(PR.get('fill_under_spacing', 2.0))} mm) + tatami {num(PR['fill_angle'])}°, reavahe {num(PR['fill_spacing'])} mm (0,1 mm sammul), osad ülevalt alla, osade vahel niidilõige.")] if 'tatami' in KIND else []),
             *([B(f"Kitsad kujundid ja tekst: satiin {num(PR['satin_spacing'])} mm, alustikk laiuse järgi (kitsal keskjoon, laiemal servad); sama kuju tikitakse alati ühtemoodi.")] if 'satin' in KIND else []),
             *([B(f"Peened jooned: {int(PR['run_passes'])}× sirgpiste.")] if 'run' in KIND else []),
             *([B(f"Ääris: täidise serval satiinriba {num(PR.get('fill_border', 0) or PR.get('applique_border', 3))} mm, nurgad pöördega; varjab täidise serva ja tõmbe.")] if 'border' in KIND else []),
             *([B(f"Serv: kujundi peale {OUTLINE_N}× sirgpiste mööda serva; teeb serva teravaks ja peidab ridade otsad.")] if 'outline' in KIND else []),
             *([B(f"Kangas: {FABRIC_ET.get(META['fabric'], META['fabric'])}; tugimaterjal: {STABILIZER_ET.get(META['fabric'], 'rebitav või lõigatav')}.")] if META.get('fabric') else []),
             *([B("Niit: 60 wt (peenem kui tavaline 40 wt), nõel 65/9; pisted tihedamad ja kitsamad, et väike kiri jääks lahti. 40 wt niidiga see fail ei sobi.")] if int(META.get('thread', 40)) == 60 else []),
             *([B(f"Kontuuritäide: read käivad kujundi servaga paralleelselt, reavahe {num(PR['fill_spacing'])} mm, üks pidev spiraal (ilma õmbluseta).")] if 'contour' in KIND else []),
             *([B(f"Ristpiste: ruut {num(PR.get('cross_size', 2.0))} mm, ruudustik ühine kogu tikandil; rist = kaks diagonaali.")] if 'cross' in KIND else []),
             *([B("Aplikatsioon: masin peatub 2 korda – (1) pärast paigutusjoont: aseta kangatükk joone peale; (2) pärast kinnitusjoont: lõika kangas joone lähedalt ära, siis ääris. Peatus näeb välja nagu värvivahetus sama niidiga.")] if 'applique' in KIND else []),
             B(f"Tõmbekompensatsioon {num(PR['comp'])} mm piste suunas (tatami read pikemad, satiin laiem). Kinnitus niidilõike ees ja järel."),
             B(('PES: nullpunkt mustri vasakus ülanurgas.' if META['format'] else '') + (' JEF: keskpunktiga.' if META.get('jef') else '')),
             B(f"Iga suuruse kohta 3 joonist: <b>eeldatav välimus</b> (pärast tikkimist: kangas tõmbab satiinipistete otsi umbes {num(PR['comp'])} mm sisse ja lükkab sambaid veidi pikemaks – hinnang, tegeliku näitab proov), <b>pistete käik</b> (alustikk helesinine; hilisem piste on valge äärisega ja jääb peale) ja <b>niidi tihedus</b> (roheline õhuke … punane liiga paks; kollased ja punased kohad vaata proovil üle)."),
             Paragraph('Kuidas testida', h2),
             B('Masinas: kontrolli suurust ja raami, tee jälgimine (trace).'),
             B(f"Tiki jäägile: sama kangas, tugimaterjal {STABILIZER_ET.get(META.get('fabric'), 'rebitav või lõigatav')}, uus tikkimisnõel {'65/9' if int(META.get('thread', 40)) == 60 else '75/11'}."),
             B('Jälgi tikkimist; terava heli või niidi katkemise korral peata ja märgi koht. Võrdle tulemust 1:1 joonisega.'),
             Spacer(1, 3), test_t]
    disc = Paragraph('<b>Märkus.</b> Joonised on mõõtkavas 1 : 1: prindi 100 % (mitte „Fit to page“), mõõtjoonlaud = 50 mm. Mõõdud on pistete äärmiste punktide järgi, telgjooned = raami kese. Tee enne kasutamist proovitikkimine.', ParagraphStyle('d', parent=sm, textColor=GREY))
    dw, dh = disc.wrap(W - 36 * mm, 40 * mm); disc.drawOn(c, 18 * mm, 14 * mm)
    c.setStrokeColor(LIGHT); c.setLineWidth(0.4); c.line(18 * mm, 14 * mm + dh + 2.5 * mm, W - 18 * mm, 14 * mm + dh + 2.5 * mm)
    FW, FH = W - 36 * mm, H - 29 * mm - dh - 5 * mm
    for gap in (28, 20, 14, 9):                          # more techniques = more text: tighten headings until it fits
        h2.spaceBefore = gap
        need = sum(f.wrap(FW - 12, FH)[1] + f.getSpaceBefore() + f.getSpaceAfter() for f in story)
        if need < FH - 18: break
    fr = Frame(18 * mm, 14 * mm + dh + 5 * mm, FW, FH, showBoundary=0); fr.addFromList(story, c)
    c.setFont('Helvetica', 7); c.setFillColor(GREY); c.drawRightString(W - 18 * mm, 9 * mm, f'1 / {PAGES}')
    page = 1
    while story:                                        # what did not fit goes on the next portrait page
        c.showPage(); page += 1
        Frame(18 * mm, 14 * mm, W - 36 * mm, H - 29 * mm, showBoundary=0).addFromList(story, c)
        c.setFont('Helvetica', 7); c.setFillColor(GREY); c.drawRightString(W - 18 * mm, 9 * mm, f'{page} / {PAGES}')
    return page

# ---------------- CAD sheet (landscape)
def arrow(c, x, y, ang):
    import math
    L = 2.2 * mm; a = 0.35
    p = c.beginPath(); p.moveTo(x, y)
    p.lineTo(x - L * math.cos(ang - a), y - L * math.sin(ang - a)); p.lineTo(x - L * math.cos(ang + a), y - L * math.sin(ang + a)); p.close()
    c.drawPath(p, stroke=0, fill=1)
def dim_h(c, x1, x2, yref, ydim, text):
    import math
    c.setLineWidth(0.18); c.setStrokeColor(INK); c.setFillColor(INK)
    c.line(x1, yref, x1, ydim - 1.5 * mm); c.line(x2, yref, x2, ydim - 1.5 * mm)
    c.line(x1, ydim, x2, ydim); arrow(c, x1, ydim, math.pi); arrow(c, x2, ydim, 0)
    c.setFont('Helvetica', 8); c.drawCentredString((x1 + x2) / 2, ydim + 1.2 * mm, text)
def dim_v(c, y1, y2, xref, xdim, text):
    import math
    c.setLineWidth(0.18); c.setStrokeColor(INK); c.setFillColor(INK)
    c.line(xref, y1, xdim - 1.5 * mm, y1); c.line(xref, y2, xdim - 1.5 * mm, y2)
    c.line(xdim, y1, xdim, y2); arrow(c, xdim, y1, -math.pi / 2); arrow(c, xdim, y2, math.pi / 2)
    c.saveState(); c.translate(xdim - 1.2 * mm, (y1 + y2) / 2); c.rotate(90); c.setFont('Helvetica', 8); c.drawCentredString(0, 0, text); c.restoreState()

# PDF text is Estonian: density legend and fabric names as the reader sees them
LEVEL_LABELS_ET = ['alla 2', '2–4', '4–5,5', '5,5–7', '7–8,5', '8,5–10', 'üle 10']
FABRIC_ET = {'linen': 'linane', 'cotton': 'puuvill', 'denim': 'teksas', 'canvas': 'kanvas', 'jersey': 'trikoo',
             'fleece': 'fliis', 'terry': 'frotee', 'leather': 'nahk', 'vinyl': 'vinüül'}
STABILIZER_ET = {'linen': 'rebitav', 'cotton': 'rebitav', 'denim': 'rebitav', 'canvas': 'rebitav',
                 'jersey': 'lõigatav + kinnitus', 'fleece': 'lõigatav, peale vees lahustuv kile',
                 'terry': 'lõigatav, peale vees lahustuv kile', 'leather': 'rebitav', 'vinyl': 'rebitav'}
KINDS = {'appearance': 'EELDATAV VÄLIMUS', 'stitches': 'PISTETE KÄIK', 'density': 'NIIDI TIHEDUS'}   # page order


def segs_of(d):
    """[(q0, q1, colour index, underlay?)] in sewing order, mm"""
    isU = lambda q: (round(q[0] * 10), round(q[1] * 10)) in d['U']
    return [(q0, q1, ci, isU(q0) and isU(q1)) for ci, s in d['st'] for q0, q1 in zip(s, s[1:])]


def draw_path(c, d, P):
    """thread path: underlay light and thin; top stitches one by one in sewing order, each with a
    white edge, so where threads cross the later (upper) one is drawn over the earlier one"""
    c.setLineCap(1); c.setLineJoin(1)
    S = segs_of(d)
    c.setStrokeColor(HexColor('#c3c9e6')); c.setLineWidth(0.08 * mm)
    for q0, q1, ci, u in S:
        if u: c.line(*P(*q0), *P(*q1))
    for q0, q1, ci, u in S:
        if u: continue
        c.setStrokeColor(HexColor('#ffffff')); c.setLineWidth(0.30 * mm); c.line(*P(*q0), *P(*q1))
        c.setStrokeColor(HexColor(COLS[ci]['hex'])); c.setLineWidth(0.12 * mm); c.line(*P(*q0), *P(*q1))


def _shade(hx, f):
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    if f < 1: r, g, b = (int(v * f) for v in (r, g, b))
    else: r, g, b = (int(v + (255 - v) * (f - 1)) for v in (r, g, b))
    return HexColor(f'#{r:02x}{g:02x}{b:02x}')


def draw_look(c, d, P, X0, Y1, w, h):
    """expected look on the fabric (preview.look): stitches where they lie after the fabric pulled in and
    pushed out, satin sheen, fabric texture; drawn as a picture at 16 px/mm"""
    import preview
    from reportlab.lib.utils import ImageReader
    c.setFillColor(HexColor(FABRIC)); c.rect(X0 - 3 * mm, Y1 - h - 3 * mm, w + 6 * mm, h + 6 * mm, stroke=0, fill=1)
    preview.THREAD = 0.28 if int(META.get('thread', 40)) == 60 else 0.4
    S = [(q0, q1, COLS[ci]['hex'], u) for q0, q1, ci, u in segs_of(d)]
    px = 16
    im, x0, y0 = preview.look(S, px, float(PR.get('comp', 0.2)), float(PR.get('comp_stretch', 0)), float(PR.get('stretch_angle', 0)),
                              FABRIC, META.get('fabric', ''), margin=2)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=88); buf.seek(0)     # JPEG: a raster of this size as PNG would make the PDF megabytes
    c.drawImage(ImageReader(buf), X0 + (x0 - d['x0']) * mm, Y1 - (y0 - d['y0']) * mm - im.height / px * mm,
                im.width / px * mm, im.height / px * mm)


def draw_density(c, d, X0, Y1, ax0, ax1, ay0):
    """thread length per mm2, smoothed over ~1 mm, 7 levels green -> red"""
    import preview
    from reportlab.lib.utils import ImageReader
    segs = [(q0, q1, '#000000') for q0, q1, ci, u in segs_of(d)]
    xs = [q[0] for s in segs for q in s[:2]]; ys = [q[1] for s in segs for q in s[:2]]
    g, gx, gy = preview.density(segs, (min(xs), min(ys), max(xs), max(ys)), 0.25)
    im = preview.density_image(g, 4)
    c.drawImage(ImageReader(im), X0 + (gx - d['x0']) * mm, Y1 - (gy - d['y0']) * mm - g.shape[0] * 0.25 * mm,
                g.shape[1] * 0.25 * mm, g.shape[0] * 0.25 * mm, mask='auto')
    # legend, bottom right of the drawing area
    n = len(preview.LEVELS); bw = 13 * mm; lx = ax1 - n * bw - 2 * mm; ly = ay0 + 5 * mm
    c.setFont('Helvetica', 6.5); c.setFillColor(INK)
    c.drawString(lx, ly + 5.5 * mm, 'Niidi pikkus mm/mm² (~1 mm ala keskmine): roheline õhuke … punane liiga paks')
    for i, (hi, col, txt) in enumerate(preview.LEVELS):
        c.setFillColor(HexColor(col)); c.rect(lx + i * bw, ly, bw, 3.5 * mm, stroke=0, fill=1)
        c.setFillColor(INK); c.drawCentredString(lx + (i + 0.5) * bw, ly - 3 * mm, LEVEL_LABELS_ET[i])


def sheet(c, d, page, total, kind):
    W, H = landscape(A4); M = 10 * mm
    # frame
    c.setStrokeColor(INK); c.setLineWidth(0.7); c.rect(M, M, W - 2 * M, H - 2 * M)
    c.setLineWidth(0.25); c.rect(M + 2 * mm, M + 2 * mm, W - 2 * M - 4 * mm, H - 2 * M - 4 * mm)
    # zone ticks
    c.setFont('Helvetica', 6); c.setFillColor(GREY)
    for i in range(1, 6):
        x = M + (W - 2 * M) * i / 6; c.line(x, M, x, M + 2 * mm); c.line(x, H - M, x, H - M - 2 * mm)
    # title block (right column)
    tx = M + (W - 2 * M) * 5 / 6; TBW = (W - M - 2 * mm) - tx; ty0 = M + 2 * mm; ty1 = H - M - 2 * mm
    c.setStrokeColor(INK); c.setLineWidth(0.4); c.line(tx, ty0, tx, ty1)
    k0 = COLS[0]
    thread = (k0['name'] + ' ' + k0['hex'].upper()) if len(COLS) == 1 else f'{len(COLS)} värvi (lk 1)'
    rows = [('PROJEKT', NAME), ('JOONIS', KINDS[kind]), ('FAIL', d['f']), ('FORMAAT', FMT),
            ('MÕÕDUD', f"{fmt(d['w'])} × {fmt(d['h'])} mm"), ('PISTED', str(d['n'])), ('NIIDILÕIKED', str(d['t'])),
            ('NIIT', thread), ('BROTHER', f"{k0['brother']['code']} {k0['brother']['name']}" if len(COLS) == 1 else '–'), ('MÕÕTKAVA', '1 : 1'),
            ('KUUPÄEV', DATE), ('LEHT', f'{page} / {total}')]
    rh = (ty1 - ty0) / len(rows); y = ty0
    for lab, val in reversed(rows):
        if y + rh < ty1 - 0.1: c.setLineWidth(0.25); c.line(tx, y + rh, tx + TBW, y + rh)
        c.setFont('Helvetica', 5.5); c.setFillColor(GREY); c.drawString(tx + 2 * mm, y + rh - 4.0 * mm, lab)
        c.setFillColor(INK); fn = 'Helvetica-Bold' if lab in ('FAIL', 'LEHT', 'JOONIS') else 'Helvetica'; fs = 8.5
        lim = TBW - (12 if lab in ('NIIT', 'BROTHER') else 4) * mm
        while c.stringWidth(val, fn, fs) > lim and fs > 5: fs -= 0.25
        c.setFont(fn, fs); c.drawString(tx + 2 * mm, y + rh / 2 - 4.5 * mm, val)
        if lab == 'NIIT' and len(COLS) == 1:
            c.setFillColor(HexColor(k0['hex'])); c.rect(tx + TBW - 9 * mm, y + rh / 2 - 5.0 * mm, 6 * mm, 4 * mm, stroke=0, fill=1)
        if lab == 'BROTHER' and len(COLS) == 1:
            c.setFillColor(HexColor(k0['brother']['hex'])); c.rect(tx + TBW - 9 * mm, y + rh / 2 - 5.0 * mm, 6 * mm, 4 * mm, stroke=0, fill=1)
        y += rh
    # drawing area
    ax0, ax1 = M + 4 * mm, tx - 2 * mm; ay0, ay1 = M + 4 * mm, ty1 - 2 * mm
    cx = (ax0 + 12 * mm + ax1 - 2 * mm) / 2; cy = (ay0 + 12 * mm + ay1 - 12 * mm) / 2
    w, h = d['w'] * mm, d['h'] * mm; X0, Y1 = cx - w / 2, cy + h / 2  # top-left of design
    # center lines (dash-dot)
    c.setStrokeColor(GREY); c.setLineWidth(0.18); c.setDash([6, 2, 1, 2])
    c.line(max(ax0, X0 - 6 * mm), cy, min(ax1, X0 + w + 6 * mm), cy); c.line(cx, min(ay1 - 1 * mm, Y1 + 6 * mm), cx, max(ay0 + 10 * mm, Y1 - h - 6 * mm)); c.setDash()
    # bounding box (thin dashed)
    c.setStrokeColor(LIGHT); c.setDash([2, 2]); c.rect(X0, Y1 - h, w, h); c.setDash()
    P = lambda a, b: (X0 + (a - d['x0']) * mm, Y1 - (b - d['y0']) * mm)
    if kind == 'stitches': draw_path(c, d, P)
    elif kind == 'appearance': draw_look(c, d, P, X0, Y1, w, h)
    else: draw_density(c, d, X0, Y1, ax0, ax1, ay0)
    # dimensions
    dim_h(c, X0, X0 + w, Y1 + 1.5 * mm, Y1 + 8 * mm, fmt(d['w']))
    dim_v(c, Y1 - h, Y1, X0 - 1.5 * mm, X0 - 8 * mm, fmt(d['h']))
    # scale bar 50 mm
    sx, sy = ax0 + 4 * mm, ay0 + 5 * mm
    c.setStrokeColor(INK); c.setFillColor(INK); c.setLineWidth(0.3)
    for i in range(5):
        if i % 2 == 0: c.rect(sx + i * 10 * mm, sy, 10 * mm, 1.6 * mm, stroke=1, fill=1)
        else: c.rect(sx + i * 10 * mm, sy, 10 * mm, 1.6 * mm, stroke=1, fill=0)
    c.setFont('Helvetica', 6.5)
    for i in range(0, 6): c.drawCentredString(sx + i * 10 * mm, sy - 3 * mm, str(i * 10))
    c.drawString(sx + 52 * mm, sy - 3 * mm, 'mm')

import io
# for one PDF made of several designs: NO_COVER=1 leaves the cover out, PAGE_OFFSET/PAGE_TOTAL number the pages
NO_COVER = os.environ.get('NO_COVER') == '1'
OFF = int(os.environ.get('PAGE_OFFSET', '0'))
COVER = 0 if NO_COVER else cover(canvas.Canvas(io.BytesIO(), pagesize=A4))   # trial run
PAGES = int(os.environ.get('PAGE_TOTAL', '0')) or COVER + 3 * len(FILES)
c = canvas.Canvas(os.environ.get('PDF_OUT', f'{NAME} - Projekt.pdf'), pagesize=A4)
c.setTitle(f'{NAME} – tikkimisfailid')
if not NO_COVER: cover(c); c.showPage()
for i, f in enumerate(FILES):
    for j, kind in enumerate(KINDS):
        c.setPageSize(landscape(A4)); sheet(c, D[f], OFF + COVER + 1 + 3 * i + j, PAGES, kind); c.showPage()
c.save()
for f in FILES: print(f, fmt(D[f]['w']), fmt(D[f]['h']))
