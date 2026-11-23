"""Project PDF: <Name> - Projekt.pdf from out/meta.json (written by gen.py).

    python3 pdfcad.py

Page 1 (portrait, more if it does not fit): files, colours, the user's choices, how it is made,
how to test. Then for every file three landscape drawings at 1:1: expected look, stitch path,
thread density.

Environment (for one PDF made of several designs):
  NO_COVER=1      leave the cover out
  PAGE_OFFSET=n   number the drawing pages from n + 1
  PAGE_TOTAL=n    total page count printed on every page
  PDF_OUT=path    output file
  FABRIC=#rrggbb  fabric colour in the expected-look drawing
"""
import datetime
import io
import json
import math
import os

import pyembroidery as pe
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph, Spacer, Table, TableStyle

from texts import TEXT

OUT_DIR = 'out/'
META = json.load(open(OUT_DIR + 'meta.json'))
NAME = META['name']
EXTENSION = '.pes' if META['format'] else '.jef'
FILES = [f['file'] + EXTENSION for f in META['files']]
FORMAT_NAME = (('Brother ' + META['format'] + (' + Janome JEF' if META.get('jef') else ''))
               if META['format'] else 'Janome JEF')
COLOURS = META['colors']
DATE = datetime.date.fromisoformat(META['date']).strftime('%d.%m.%Y')
PARAMS = META['params']
CHOICES = META.get('choices', {})
TECHNIQUES = set(META.get('kinds') or ['run', 'satin', 'tatami'])   # older meta.json: mention everything
THREAD_WEIGHT = int(META.get('thread', 40))
FABRIC_COLOUR = os.environ.get('FABRIC', '#f2efe8')

INK = HexColor('#1a1a1a')
GREY = HexColor('#8a8a8a')
LIGHT = HexColor('#d0d0d0')

SHEET_KINDS = TEXT['sheet_kinds']     # page order: appearance, stitches, density


def outline_passes():
    """outline passes: the global setting, or the largest per-shape value in the plan"""
    passes = int(PARAMS.get('fill_outline') or 0)
    if not passes and META.get('plan'):
        try:
            shapes = json.load(open(META['plan'])).get('shapes', {}).values()
            passes = max([int(v.get('fill_outline', 0)) for v in shapes] + [0])
        except (OSError, ValueError):
            pass
    return passes or 1


OUTLINE_PASSES = outline_passes()


def number(value):
    """number in Estonian notation: decimal comma, no trailing zeros"""
    text = f'{value:.2f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value)
    return text.replace('.', ',')


def one_decimal(value):
    return f'{value:.1f}'.replace('.', ',')


def load_design(file_name):
    """stitch runs of one file, in mm: dict(f, st=[(colour row, [points])], U=underlay points,
    x0, y0, w, h, n=stitch count, t=trim count)"""
    pattern = pe.read(OUT_DIR + file_name)
    runs = []
    current = []
    trims = 0
    last_command = None
    block = 0
    block_colours = META.get('blocks')   # thread block -> colour row (a machine stop repeats a colour)

    def colour_row(block_index):
        if block_colours:
            return block_colours[min(block_index, len(block_colours) - 1)]
        return min(block_index, len(COLOURS) - 1)

    for x, y, command in pattern.stitches:
        command &= pe.COMMAND_MASK
        if command == pe.STITCH:
            current.append((x / 10, y / 10))
        else:
            if len(current) > 1:
                runs.append((colour_row(block), current))
            current = []
        if command == pe.COLOR_CHANGE:
            block += 1
        if command == pe.TRIM and last_command == pe.STITCH:
            trims += 1
        if command in (pe.STITCH, pe.TRIM):
            last_command = command
    if len(current) > 1:
        runs.append((colour_row(block), current))

    xs = [x for _, run in runs for x, y in run]
    ys = [y for _, run in runs for x, y in run]
    underlay_file = 'outpos/' + file_name[:-4] + '.under.json'
    underlay = set(tuple(v) for v in json.load(open(underlay_file))) if os.path.exists(underlay_file) else set()
    return dict(f=file_name, st=runs, U=underlay, x0=min(xs), y0=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys),
                n=pattern.count_stitch_commands(pe.STITCH), t=trims)


DESIGNS = {f: load_design(f) for f in FILES}


# ---------------------------------------------------------------- the user's choices

def stabilizer_text(value):
    """'cutaway+fusible' -> 'lõigatav + kinnituv (triigitav)'"""
    if not value:
        return ''
    return ' + '.join(TEXT['stabilizers'].get(part, part) for part in value.split('+'))


def backing():
    """the backing the user chose, else the fabric's usual one marked as a suggestion"""
    if CHOICES.get('stabilizer'):
        return stabilizer_text(CHOICES['stabilizer'])
    return TEXT['usual_backing'].get(META.get('fabric'), TEXT['backing_unknown']) + TEXT['suggested']


def choice_rows():
    """everything the user chose or set, for the cover: [(label, value)]"""
    machines = TEXT['machines']
    rows = []
    if CHOICES.get('machines'):
        rows.append((TEXT['choice_machine'], ', '.join(machines.get(m, (m,))[0] for m in CHOICES['machines'])))
        if CHOICES.get('hoop'):
            hoop = TEXT['choice_hoop_chosen'].format(hoop=CHOICES['hoop'].replace('x', ' × '))
        else:
            hoops = '; '.join(f'{machines[m][1]} mm' for m in CHOICES['machines'] if m in machines)
            hoop = TEXT['choice_hoop_largest'].format(hoops=hoops)
        rows.append((TEXT['choice_hoop'], hoop))
    if CHOICES.get('sizes'):
        template = TEXT['choice_sizes_exact'] if CHOICES.get('exact') else TEXT['choice_sizes_picture']
        rows.append((TEXT['choice_sizes'], template.format(sizes=CHOICES['sizes'].replace(',', ', '))))
    if CHOICES.get('scales'):
        rows.append((TEXT['choice_scales'], TEXT['choice_scales_value'].format(scales=CHOICES['scales'].replace(',', ', '))))
    fabric = META.get('fabric')
    rows.append((TEXT['choice_fabric'], TEXT['fabrics'].get(fabric, fabric) if fabric else TEXT['choice_fabric_none']))
    rows.append((TEXT['choice_backing'], backing()))
    rows.append((TEXT['choice_topping'], stabilizer_text(CHOICES.get('topping', '')) or '–'))
    rows.append((TEXT['choice_thread'], f'{THREAD_WEIGHT} wt'))
    if 'angle' in CHOICES:
        rows.append((TEXT['choice_angle'], f"{number(CHOICES['angle'])}°"))
    if CHOICES.get('colors'):
        rows.append((TEXT['choice_thread_names'], ', '.join(c.replace('=', ' → ', 1) for c in CHOICES['colors'])))
    if CHOICES.get('plan'):
        rows.append((TEXT['choice_plan'], TEXT['choice_plan_value'].format(plan=CHOICES['plan'])))
    if CHOICES.get('sets'):
        rows.append((TEXT['choice_sets'], ', '.join(CHOICES['sets'])))
    if CHOICES.get('working'):
        rows.append((TEXT['choice_working'], TEXT['choice_working_value'].format(file=CHOICES['working'])))
    return rows


# ---------------------------------------------------------------- cover (portrait)

def how_made_bullets(bullet):
    """'How it is made': one bullet per technique used, then the general notes"""
    stabilizer = CHOICES.get('stabilizer', '')
    knit_on_washaway = (META.get('fabric') in ('jersey', 'fleece') and 'washaway' in stabilizer
                        and 'cutaway' not in stabilizer and 'mesh' not in stabilizer)
    items = []
    if 'tatami' in TECHNIQUES:
        items.append(TEXT['made_tatami'].format(under_spacing=number(PARAMS.get('fill_under_spacing', 2.0)),
                                                angle=number(PARAMS['fill_angle']), spacing=number(PARAMS['fill_spacing'])))
    if 'satin' in TECHNIQUES:
        items.append(TEXT['made_satin'].format(spacing=number(PARAMS['satin_spacing'])))
    if 'run' in TECHNIQUES:
        items.append(TEXT['made_run'].format(passes=int(PARAMS['run_passes'])))
    if 'border' in TECHNIQUES:
        items.append(TEXT['made_border'].format(width=number(PARAMS.get('fill_border', 0) or PARAMS.get('applique_border', 3))))
    if 'outline' in TECHNIQUES:
        items.append(TEXT['made_outline'].format(passes=OUTLINE_PASSES))
    if knit_on_washaway:
        items.append(TEXT['made_knit_washaway'])
    if THREAD_WEIGHT == 60:
        items.append(TEXT['made_thread_60'])
    if 'contour' in TECHNIQUES:
        items.append(TEXT['made_contour'].format(spacing=number(PARAMS['fill_spacing'])))
    if 'cross' in TECHNIQUES:
        items.append(TEXT['made_cross'].format(size=number(PARAMS.get('cross_size', 2.0))))
    if 'applique' in TECHNIQUES:
        items.append(TEXT['made_applique'])
    items.append(TEXT['made_compensation'].format(comp=number(PARAMS['comp'])))
    items.append((TEXT['made_origin_pes'] if META['format'] else '') + (TEXT['made_origin_jef'] if META.get('jef') else ''))
    items.append(TEXT['made_drawings'].format(comp=number(PARAMS['comp'])))
    return [bullet(text) for text in items]


def how_to_test_bullets(bullet):
    topping = TEXT['test_scrap_topping'].format(topping=stabilizer_text(CHOICES['topping'])) if CHOICES.get('topping') else ''
    needle = '65/9' if THREAD_WEIGHT == 60 else '75/11'
    return [bullet(TEXT['test_machine']),
            bullet(TEXT['test_scrap'].format(backing=backing(), topping=topping, needle=needle)),
            bullet(TEXT['test_watch'])]


def cover(c):
    """draw the cover; returns the number of portrait pages it took"""
    width, height = A4
    body = ParagraphStyle('b', fontName='Helvetica', fontSize=9.5, leading=13, spaceAfter=3)
    small = ParagraphStyle('s', parent=body, fontSize=8.5, leading=11)
    heading1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=17, leading=21, spaceAfter=4)
    heading2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=28, spaceAfter=8)
    bullet_style = ParagraphStyle('bl', parent=body, leftIndent=12, bulletIndent=2, spaceAfter=2)

    def bullet(text):
        return Paragraph(text, bullet_style, bulletText='•')

    def table(rows, widths, right_aligned=()):
        t = Table(rows, colWidths=widths, hAlign='LEFT', repeatRows=1)
        style = [('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8.5), ('FONT', (0, 1), (-1, -1), 'Helvetica', 8.5),
                 ('LINEBELOW', (0, 0), (-1, 0), 0.6, black), ('LINEBELOW', (0, 1), (-1, -1), 0.25, LIGHT),
                 ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
        for column in right_aligned:
            style.append(('ALIGN', (column, 0), (column, -1), 'RIGHT'))
        t.setStyle(TableStyle(style))
        return t

    # files
    rows = [list(TEXT['files_columns'])]
    for i, f in enumerate(FILES):
        d = DESIGNS[f]
        pages = f'{COVER_PAGES + 1 + 3 * i}–{COVER_PAGES + 3 + 3 * i}'
        rows.append([pages, f, f"{one_decimal(d['w'])} × {one_decimal(d['h'])} mm", str(d['n']), str(d['t'])])
    files_table = table(rows, [16 * mm, 58 * mm, 38 * mm, 20 * mm, 18 * mm], right_aligned=(3, 4))

    # colours: original, Brother and Janome thread with a swatch beside each
    rows = [list(TEXT['colours_columns'])]
    for i, colour in enumerate(COLOURS, start=1):
        original = f"{colour['name']}  {colour['hex'].upper()}" if colour['name'] != colour['hex'] else colour['hex'].upper()
        rows.append([str(i), '', original, '',
                     f"{colour['brother']['code']} {colour['brother']['name']}", '',
                     f"{colour['janome']['code']} {colour['janome']['name']}"])
    colour_table = table(rows, [9 * mm, 6 * mm, 45 * mm, 6 * mm, 50 * mm, 6 * mm, 48 * mm])
    swatches = []
    for row, colour in enumerate(COLOURS, start=1):
        swatches += [('BACKGROUND', (1, row), (1, row), HexColor(colour['hex'])),
                     ('BACKGROUND', (3, row), (3, row), HexColor(colour['brother']['hex'])),
                     ('BACKGROUND', (5, row), (5, row), HexColor(colour['janome']['hex']))]
    colour_table.setStyle(TableStyle(swatches))

    # what to change when the test shows a problem
    values = dict(fill_spacing=number(PARAMS['fill_spacing']), satin_spacing=number(PARAMS['satin_spacing']),
                  comp=number(PARAMS['comp']))
    seen, change = TEXT['test_table_columns']
    rows = [[Paragraph(f'<b>{seen}</b>', small), Paragraph(f'<b>{change}</b>', small)]]
    rows += [[Paragraph(a.format(**values), small), Paragraph(b.format(**values), small)] for a, b in TEXT['test_table']]
    test_table = table(rows, [80 * mm, 90 * mm])
    test_table.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2)]))

    # the user's choices
    choices = choice_rows()
    choice_table = None
    if choices:
        choice_table = Table([[Paragraph(k, small), Paragraph(v, small)] for k, v in choices],
                             colWidths=[38 * mm, width - 36 * mm - 38 * mm])
        choice_table.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                                          ('LEFTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    labels = ' / '.join(f['label'] for f in META['files'])
    story = [Paragraph(TEXT['title'].format(name=NAME), heading1),
             Paragraph(TEXT['subtitle'].format(format=FORMAT_NAME, count=len(FILES), date=DATE), small),
             Paragraph(TEXT['files_heading'], heading2), files_table, Spacer(1, 3),
             Paragraph(TEXT['machine_names'].format(labels=labels), small),
             Paragraph(TEXT['colours_heading'], heading2), colour_table,
             *([Paragraph(TEXT['choices_heading'], heading2), choice_table] if choice_table else []),
             Paragraph(TEXT['how_made_heading'], heading2),
             *how_made_bullets(bullet),
             Paragraph(TEXT['how_to_test_heading'], heading2),
             *how_to_test_bullets(bullet),
             Spacer(1, 3), test_table]

    # disclaimer at the foot of the page, the story above it
    disclaimer = Paragraph(TEXT['disclaimer'], ParagraphStyle('d', parent=small, textColor=GREY))
    _, disclaimer_height = disclaimer.wrap(width - 36 * mm, 40 * mm)
    disclaimer.drawOn(c, 18 * mm, 14 * mm)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.4)
    rule_y = 14 * mm + disclaimer_height + 2.5 * mm
    c.line(18 * mm, rule_y, width - 18 * mm, rule_y)
    frame_width, frame_height = width - 36 * mm, height - 29 * mm - disclaimer_height - 5 * mm
    for gap in (28, 20, 14, 9):                  # more techniques = more text: tighten headings until it fits
        heading2.spaceBefore = gap
        need = sum(f.wrap(frame_width - 12, frame_height)[1] + f.getSpaceBefore() + f.getSpaceAfter() for f in story)
        if need < frame_height - 18:
            break
    Frame(18 * mm, 14 * mm + disclaimer_height + 5 * mm, frame_width, frame_height, showBoundary=0).addFromList(story, c)
    c.setFont('Helvetica', 7)
    c.setFillColor(GREY)
    c.drawRightString(width - 18 * mm, 9 * mm, f'1 / {PAGES}')
    page = 1
    while story:                                 # what did not fit goes on the next portrait page
        c.showPage()
        page += 1
        Frame(18 * mm, 14 * mm, width - 36 * mm, height - 29 * mm, showBoundary=0).addFromList(story, c)
        c.setFont('Helvetica', 7)
        c.setFillColor(GREY)
        c.drawRightString(width - 18 * mm, 9 * mm, f'{page} / {PAGES}')
    return page


# ---------------------------------------------------------------- drawing sheets (landscape)

def arrow(c, x, y, angle):
    """filled arrow head with its tip at (x, y), pointing along angle"""
    length = 2.2 * mm
    spread = 0.35
    path = c.beginPath()
    path.moveTo(x, y)
    path.lineTo(x - length * math.cos(angle - spread), y - length * math.sin(angle - spread))
    path.lineTo(x - length * math.cos(angle + spread), y - length * math.sin(angle + spread))
    path.close()
    c.drawPath(path, stroke=0, fill=1)


def dimension_horizontal(c, x1, x2, y_from, y_line, text):
    c.setLineWidth(0.18)
    c.setStrokeColor(INK)
    c.setFillColor(INK)
    c.line(x1, y_from, x1, y_line - 1.5 * mm)
    c.line(x2, y_from, x2, y_line - 1.5 * mm)
    c.line(x1, y_line, x2, y_line)
    arrow(c, x1, y_line, math.pi)
    arrow(c, x2, y_line, 0)
    c.setFont('Helvetica', 8)
    c.drawCentredString((x1 + x2) / 2, y_line + 1.2 * mm, text)


def dimension_vertical(c, y1, y2, x_from, x_line, text):
    c.setLineWidth(0.18)
    c.setStrokeColor(INK)
    c.setFillColor(INK)
    c.line(x_from, y1, x_line - 1.5 * mm, y1)
    c.line(x_from, y2, x_line - 1.5 * mm, y2)
    c.line(x_line, y1, x_line, y2)
    arrow(c, x_line, y1, -math.pi / 2)
    arrow(c, x_line, y2, math.pi / 2)
    c.saveState()
    c.translate(x_line - 1.2 * mm, (y1 + y2) / 2)
    c.rotate(90)
    c.setFont('Helvetica', 8)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def segments(design):
    """[(start, end, colour row, underlay?)] in sewing order, mm"""
    def is_underlay(point):
        return (round(point[0] * 10), round(point[1] * 10)) in design['U']
    return [(a, b, colour, is_underlay(a) and is_underlay(b))
            for colour, run in design['st'] for a, b in zip(run, run[1:])]


def draw_stitch_path(c, design, to_page):
    """thread path: underlay light and thin; top stitches one by one in sewing order, each with a
    white edge, so where threads cross the later (upper) one is drawn over the earlier one"""
    c.setLineCap(1)
    c.setLineJoin(1)
    stitches = segments(design)
    c.setStrokeColor(HexColor('#c3c9e6'))
    c.setLineWidth(0.08 * mm)
    for a, b, colour, underlay in stitches:
        if underlay:
            c.line(*to_page(*a), *to_page(*b))
    for a, b, colour, underlay in stitches:
        if underlay:
            continue
        c.setStrokeColor(HexColor('#ffffff'))
        c.setLineWidth(0.30 * mm)
        c.line(*to_page(*a), *to_page(*b))
        c.setStrokeColor(HexColor(COLOURS[colour]['hex']))
        c.setLineWidth(0.12 * mm)
        c.line(*to_page(*a), *to_page(*b))


def draw_look(c, design, left, top, width, height):
    """expected look on the fabric (preview.look): stitches where they lie after the fabric pulled in and
    pushed out, satin sheen, fabric texture; drawn as a picture at 16 px/mm"""
    import preview
    c.setFillColor(HexColor(FABRIC_COLOUR))
    c.rect(left - 3 * mm, top - height - 3 * mm, width + 6 * mm, height + 6 * mm, stroke=0, fill=1)
    preview.THREAD = 0.28 if THREAD_WEIGHT == 60 else 0.4
    stitches = [(a, b, COLOURS[colour]['hex'], underlay) for a, b, colour, underlay in segments(design)]
    px_per_mm = 16
    image, image_x0, image_y0 = preview.look(
        stitches, px_per_mm, float(PARAMS.get('comp', 0.2)), float(PARAMS.get('comp_stretch', 0)),
        float(PARAMS.get('stretch_angle', 0)), FABRIC_COLOUR, META.get('fabric', ''), margin=2)
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=88)       # JPEG: a raster of this size as PNG would make the PDF megabytes
    buffer.seek(0)
    c.drawImage(ImageReader(buffer),
                left + (image_x0 - design['x0']) * mm,
                top - (image_y0 - design['y0']) * mm - image.height / px_per_mm * mm,
                image.width / px_per_mm * mm, image.height / px_per_mm * mm)


def draw_density(c, design, left, top, area_right, area_bottom):
    """thread length per mm2, smoothed over ~1 mm, 7 levels green -> red, with a legend"""
    import preview
    stitches = [(a, b, '#000000') for a, b, colour, underlay in segments(design)]
    xs = [q[0] for s in stitches for q in s[:2]]
    ys = [q[1] for s in stitches for q in s[:2]]
    grid, grid_x0, grid_y0 = preview.density(stitches, (min(xs), min(ys), max(xs), max(ys)), 0.25)
    image = preview.density_image(grid, 4)
    c.drawImage(ImageReader(image),
                left + (grid_x0 - design['x0']) * mm, top - (grid_y0 - design['y0']) * mm - grid.shape[0] * 0.25 * mm,
                grid.shape[1] * 0.25 * mm, grid.shape[0] * 0.25 * mm, mask='auto')
    # legend, bottom right of the drawing area
    box_width = 13 * mm
    legend_x = area_right - len(preview.LEVELS) * box_width - 2 * mm
    legend_y = area_bottom + 5 * mm
    c.setFont('Helvetica', 6.5)
    c.setFillColor(INK)
    c.drawString(legend_x, legend_y + 5.5 * mm, TEXT['density_legend'])
    for i, (_, colour, _) in enumerate(preview.LEVELS):
        c.setFillColor(HexColor(colour))
        c.rect(legend_x + i * box_width, legend_y, box_width, 3.5 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.drawCentredString(legend_x + (i + 0.5) * box_width, legend_y - 3 * mm, TEXT['density_levels'][i])


def title_block(c, design, page, total, kind, left, bottom, top, block_width):
    """the title block in the right column: label above, value below, a thread swatch where useful"""
    labels = TEXT['sheet_rows']
    first = COLOURS[0]
    if len(COLOURS) == 1:   # a colour without a name is shown once
        same = first['name'].lower() == first['hex'].lower()
        thread = first['hex'].upper() if same else first['name'] + ' ' + first['hex'].upper()
        brother = f"{first['brother']['code']} {first['brother']['name']}"
    else:
        thread = TEXT['file_count_colours'].format(count=len(COLOURS))
        brother = '–'
    rows = [('project', NAME), ('drawing', SHEET_KINDS[kind]), ('file', design['f']), ('format', FORMAT_NAME),
            ('size', f"{one_decimal(design['w'])} × {one_decimal(design['h'])} mm"), ('stitches', str(design['n'])),
            ('trims', str(design['t'])), ('thread', thread), ('brother', brother), ('scale', '1 : 1'),
            ('date', DATE), ('sheet', f'{page} / {total}')]
    row_height = (top - bottom) / len(rows)
    y = bottom
    for key, value in reversed(rows):
        if y + row_height < top - 0.1:
            c.setLineWidth(0.25)
            c.line(left, y + row_height, left + block_width, y + row_height)
        c.setFont('Helvetica', 5.5)
        c.setFillColor(GREY)
        c.drawString(left + 2 * mm, y + row_height - 4.0 * mm, labels[key])
        c.setFillColor(INK)
        font = 'Helvetica-Bold' if key in ('file', 'sheet', 'drawing') else 'Helvetica'
        size = 8.5
        room = block_width - (12 if key in ('thread', 'brother') else 4) * mm
        while c.stringWidth(value, font, size) > room and size > 5:
            size -= 0.25
        c.setFont(font, size)
        c.drawString(left + 2 * mm, y + row_height / 2 - 4.5 * mm, value)
        swatch = {'thread': first['hex'], 'brother': first['brother']['hex']}.get(key)
        if swatch and len(COLOURS) == 1:
            c.setFillColor(HexColor(swatch))
            c.rect(left + block_width - 9 * mm, y + row_height / 2 - 5.0 * mm, 6 * mm, 4 * mm, stroke=0, fill=1)
        y += row_height


def sheet(c, design, page, total, kind):
    """one landscape drawing sheet: frame, title block, the design at 1:1 with dimensions and a scale bar"""
    width, height = landscape(A4)
    margin = 10 * mm
    # frame
    c.setStrokeColor(INK)
    c.setLineWidth(0.7)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)
    c.setLineWidth(0.25)
    c.rect(margin + 2 * mm, margin + 2 * mm, width - 2 * margin - 4 * mm, height - 2 * margin - 4 * mm)
    # zone ticks
    c.setFont('Helvetica', 6)
    c.setFillColor(GREY)
    for i in range(1, 6):
        x = margin + (width - 2 * margin) * i / 6
        c.line(x, margin, x, margin + 2 * mm)
        c.line(x, height - margin, x, height - margin - 2 * mm)
    # title block (right column)
    block_left = margin + (width - 2 * margin) * 5 / 6
    block_width = (width - margin - 2 * mm) - block_left
    block_bottom = margin + 2 * mm
    block_top = height - margin - 2 * mm
    c.setStrokeColor(INK)
    c.setLineWidth(0.4)
    c.line(block_left, block_bottom, block_left, block_top)
    title_block(c, design, page, total, kind, block_left, block_bottom, block_top, block_width)
    # drawing area; the design centred in it
    area_left, area_right = margin + 4 * mm, block_left - 2 * mm
    area_bottom, area_top = margin + 4 * mm, block_top - 2 * mm
    centre_x = (area_left + 12 * mm + area_right - 2 * mm) / 2
    centre_y = (area_bottom + 12 * mm + area_top - 12 * mm) / 2
    design_width, design_height = design['w'] * mm, design['h'] * mm
    left, top = centre_x - design_width / 2, centre_y + design_height / 2     # top left corner of the design
    # centre lines (dash-dot)
    c.setStrokeColor(GREY)
    c.setLineWidth(0.18)
    c.setDash([6, 2, 1, 2])
    c.line(max(area_left, left - 6 * mm), centre_y, min(area_right, left + design_width + 6 * mm), centre_y)
    c.line(centre_x, min(area_top - 1 * mm, top + 6 * mm), centre_x, max(area_bottom + 10 * mm, top - design_height - 6 * mm))
    c.setDash()
    # bounding box (thin dashed)
    c.setStrokeColor(LIGHT)
    c.setDash([2, 2])
    c.rect(left, top - design_height, design_width, design_height)
    c.setDash()

    def to_page(x, y):
        return left + (x - design['x0']) * mm, top - (y - design['y0']) * mm

    if kind == 'stitches':
        draw_stitch_path(c, design, to_page)
    elif kind == 'appearance':
        draw_look(c, design, left, top, design_width, design_height)
    else:
        draw_density(c, design, left, top, area_right, area_bottom)
    # dimensions
    dimension_horizontal(c, left, left + design_width, top + 1.5 * mm, top + 8 * mm, one_decimal(design['w']))
    dimension_vertical(c, top - design_height, top, left - 1.5 * mm, left - 8 * mm, one_decimal(design['h']))
    # scale bar 50 mm
    bar_x, bar_y = area_left + 4 * mm, area_bottom + 5 * mm
    c.setStrokeColor(INK)
    c.setFillColor(INK)
    c.setLineWidth(0.3)
    for i in range(5):
        c.rect(bar_x + i * 10 * mm, bar_y, 10 * mm, 1.6 * mm, stroke=1, fill=1 if i % 2 == 0 else 0)
    c.setFont('Helvetica', 6.5)
    for i in range(0, 6):
        c.drawCentredString(bar_x + i * 10 * mm, bar_y - 3 * mm, str(i * 10))
    c.drawString(bar_x + 52 * mm, bar_y - 3 * mm, 'mm')


# ---------------------------------------------------------------- the PDF

NO_COVER = os.environ.get('NO_COVER') == '1'
PAGE_OFFSET = int(os.environ.get('PAGE_OFFSET', '0'))
COVER_PAGES = 1                                    # trial run below finds the real count (many colours spill over)
PAGES = COVER_PAGES + 3 * len(FILES)
COVER_PAGES = 0 if NO_COVER else cover(canvas.Canvas(io.BytesIO(), pagesize=A4))
PAGES = int(os.environ.get('PAGE_TOTAL', '0')) or COVER_PAGES + 3 * len(FILES)

pdf = canvas.Canvas(os.environ.get('PDF_OUT', f'{NAME} - Projekt.pdf'), pagesize=A4)
pdf.setTitle(TEXT['title'].format(name=NAME))
if not NO_COVER:
    cover(pdf)
    pdf.showPage()
for i, f in enumerate(FILES):
    for j, kind in enumerate(SHEET_KINDS):
        pdf.setPageSize(landscape(A4))
        sheet(pdf, DESIGNS[f], PAGE_OFFSET + COVER_PAGES + 1 + 3 * i + j, PAGES, kind)
        pdf.showPage()
pdf.save()
for f in FILES:
    print(f, one_decimal(DESIGNS[f]['w']), one_decimal(DESIGNS[f]['h']))
