"""Pictures of an embroidery file: how it looks and where the thread piles up.

python3 preview.py "out/Name 150.pes" [--fabric "#f2efe8"] [--px 10 | --long 1200] [--line] [--dir check]

Working pictures for checking (not for the user: the user gets the project PDF and the machine files).
Writes to check/ (--dir):
  <file>.thread.png    stitches drawn as thread exactly where the file puts them (0.4 mm wide, thread colour)
  <file>.look.png      expected look on the fabric: pulled in, pushed out, satin sheen, fabric texture (see look())
  <file>.density.png   thread length per mm2 (smoothed over ~1 mm), 7 levels from green to red
  <file>.line.png      with --line: 400x400 line picture, only when the design goes into a collection
Prints the share of the design on each level.
"""
import argparse
import json
import math
import os

import numpy as np
import pyembroidery as pe
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter

THREAD = 0.4                         # thread width on fabric, mm (60 wt: 0.28)
# thread length per mm2 (smoothed over ~1 mm). One layer of tatami (0.3 mm rows) + underlay is about 4-5,
# satin (0.4 mm) + underlay about 5-6; more than ~8.5 means layers piling up.
LEVELS = [(2.0, '#1a9850', 'under 2 – edge or sparse'),
          (4.0, '#66bd63', '2–4 – thin'),
          (5.5, '#a6d96a', '4–5.5 – normal fill'),
          (7.0, '#fee08b', '5.5–7 – dense satin'),
          (8.5, '#fdae61', '7–8.5 – two layers'),
          (10., '#f46d43', '8.5–10 – thick, check'),
          (1e9, '#d73027', 'over 10 – too thick')]
BARE = 0.6                           # below this many mm/mm2 there is no thread (not shown, not counted)


def find_meta(file_name):
    """gen.py's meta.json: beside the file (out/) or in ../out/ (for a file in outpos/); {} if none"""
    folder = os.path.dirname(file_name) or '.'
    for candidate in (os.path.join(folder, 'meta.json'), os.path.join(folder, '..', 'out', 'meta.json')):
        try:
            return json.load(open(candidate))
        except (OSError, ValueError):
            pass
    return {}


def meta_colours(pattern, file_name):
    """gen.py's meta.json beside the file knows each thread block's colour; a PES read back loses it
    when a machine stop repeats a colour (appliqué)"""
    try:
        meta = json.load(open(os.path.join(os.path.dirname(file_name) or '.', 'meta.json')))
    except (OSError, ValueError):
        return
    if not meta.get('blocks'):
        return
    for i, thread in enumerate(pattern.threadlist):
        if i < len(meta['blocks']):
            thread.set_hex_color(meta['colors'][meta['blocks'][i]]['hex'])


def segments(pattern):
    """stitched segments in mm with their thread colour: [(a, b, '#rrggbb')]"""
    result = []
    thread = 0
    previous = None
    colours = [t.hex_color() for t in pattern.threadlist] or ['#000000']
    for x, y, command in pattern.stitches:
        command &= pe.COMMAND_MASK
        if command == pe.COLOR_CHANGE:
            thread = min(thread + 1, len(colours) - 1)
            previous = None
            continue
        if command == pe.STITCH:
            if previous:
                result.append((previous, (x / 10, y / 10), colours[thread]))
            previous = (x / 10, y / 10)
        else:
            previous = None
    return result


def segments_under(pattern, file_name):
    """segments() with the underlay flag, read from outpos/<name>.under.json when there is one"""
    base = os.path.splitext(file_name)[0]
    candidates = [base + '.under.json',
                  os.path.join(os.path.dirname(file_name) or '.', '..', 'outpos', os.path.basename(base) + '.under.json')]
    underlay = set()
    for candidate in candidates:
        if os.path.exists(candidate):
            underlay = {(x / 10, y / 10) for x, y in json.load(open(candidate))}
            break
    return [(a, b, c, a in underlay and b in underlay) for a, b, c in segments(pattern)]


def shade(hex_colour, factor):
    """darker (factor < 1) or lighter (towards white, factor > 1) as an RGB tuple"""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    if factor < 1:
        return tuple(int(v * factor) for v in (r, g, b))
    return tuple(int(v + (255 - v) * (factor - 1)) for v in (r, g, b))


# ---------------------------------------------------------------- the stitches as thread

def thread_picture(stitches, box, px, fabric):
    """stitches drawn as thread where the file puts them: dark edge, thread, highlight, rounded ends"""
    x0, y0, x1, y1 = box
    margin = 3
    image = Image.new('RGB', (int((x1 - x0 + 2 * margin) * px), int((y1 - y0 + 2 * margin) * px)), fabric)
    draw = ImageDraw.Draw(image)
    thread = max(1, round(THREAD * px))

    def to_px(q):
        return ((q[0] - x0 + margin) * px, (q[1] - y0 + margin) * px)

    for a, b, colour in stitches:
        A, B = to_px(a), to_px(b)
        draw.line([A, B], fill=shade(colour, 0.55), width=thread + 2)          # shadow edge
        r = (thread + 2) / 2
        for q in (A, B):
            draw.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=shade(colour, 0.55))
        draw.line([A, B], fill=shade(colour, 1.0), width=thread)               # thread
        length = math.dist(A, B)
        if length > 2 and thread >= 3:                                         # highlight on the side facing the light
            nx, ny = -(B[1] - A[1]) / length, (B[0] - A[0]) / length
            if nx + ny > 0:
                nx, ny = -nx, -ny
            offset = thread * 0.22
            draw.line([(A[0] + nx * offset, A[1] + ny * offset), (B[0] + nx * offset, B[1] + ny * offset)],
                      fill=shade(colour, 1.35), width=max(1, thread // 3))
        r = thread / 2                                                          # rounded thread ends
        for q in (A, B):
            draw.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=shade(colour, 0.9))
    return image


# ---------------------------------------------------------------- expected look on the fabric
# The file is not what lands on the fabric: satin and fill stitches pull the fabric in along the stitch
# (that is why the file makes them longer by the pull compensation) and push it out along the column.
# The look picture undoes that with the fabric's own numbers, so it shows the design after sewing:
#   pull  per stitch end = comp x (1 + comp_stretch x (c - 0.5)), c = |cos| to the stretch direction;
#         stitches under 1.5 mm pull in proportionally less; running stitches keep their length
#   push  a satin column grows along its length by PUSH_K x comp at each end
# These are estimates (comp is the expected pull), not measurements: a test sew-out decides.
PUSH_K = 0.4
KNIT = ('jersey', 'fleece', 'terry')
WOVEN = ('linen', 'cotton', 'denim', 'canvas')


def satin_columns(stitches):
    """index lists: consecutive top stitches > 0.8 mm that go back and forth (each turns more than 120 deg)
    to a new needle point; a stitch that goes back over the last one is a triple running stitch, not satin"""
    columns, current = [], []
    for i, (a, b, colour, underlay) in enumerate(stitches):
        v = np.subtract(b, a)
        long_top = not underlay and math.hypot(*v) > 0.8
        if long_top and current:
            pa, pb = stitches[current[-1]][0], stitches[current[-1]][1]
            w = np.subtract(pb, pa)
            retrace = math.dist(a, pb) < 0.05 and math.dist(b, pa) < 0.05      # triple running stitch goes back over itself
            if retrace or np.dot(v, w) / (math.hypot(*v) * math.hypot(*w)) >= -0.5:
                if len(current) > 3:
                    columns.append(current)
                current = []
        if long_top:
            current.append(i)
        else:
            if len(current) > 3:
                columns.append(current)
            current = []
    if len(current) > 3:
        columns.append(current)
    return columns


def settle(stitches, comp, stretch=0.0, angle=0.0, push_k=PUSH_K):
    """[(a, b, colour, underlay?)] in mm -> the same stitches where they lie after sewing, and the set
    of satin stitch indices"""
    columns = satin_columns(stitches)
    satin = {i for column in columns for i in column}
    result = [[np.array(a, float), np.array(b, float), c, u] for a, b, c, u in stitches]
    cos_angle, sin_angle = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for i in satin:                                  # pull: each satin stitch shorter at both ends
        a, b = result[i][0], result[i][1]
        v = b - a
        length = float(np.linalg.norm(v))
        direction = v / length
        along_stretch = abs(direction[0] * cos_angle + direction[1] * sin_angle)
        pull = min(comp * (1 + stretch * (along_stretch - 0.5)) * min(1.0, length / 1.5), 0.3 * length)
        result[i][0], result[i][1] = a + direction * pull, b - direction * pull
    for column in columns:                           # push: the column grows along its length
        middles = np.array([(result[i][0] + result[i][1]) / 2 for i in column])
        along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(middles, axis=0), axis=1))]
        if along[-1] < 1:
            continue
        for k, i in enumerate(column):
            tangent = middles[min(len(column) - 1, k + 3)] - middles[max(0, k - 3)]
            n = float(np.linalg.norm(tangent))
            if n < 1e-6:
                continue
            shift = tangent / n * push_k * comp * (2 * along[k] / along[-1] - 1)
            result[i][0] = result[i][0] + shift
            result[i][1] = result[i][1] + shift
    return [(tuple(a), tuple(b), c, u) for a, b, c, u in result], satin


def fabric_texture(width, height, px, colour, kind):
    """knit: wales ~0.7 mm with V loops; woven: plain weave ~0.5 mm; others plain with slight noise"""
    base = np.array([int(colour[i:i + 2], 16) for i in (1, 3, 5)], float)
    yy, xx = np.mgrid[0:height, 0:width] / px
    noise = np.random.default_rng(1).normal(0, 0.008, (height, width))
    if kind in KNIT:
        v = np.abs((xx % 0.7) / 0.7 - 0.5) * 2
        light = 1 - 0.035 * (0.5 + 0.5 * np.cos(2 * np.pi * (yy / 0.55 + 0.5 * v))) - 0.025 * v + noise
    elif kind in WOVEN:
        light = 1 - 0.03 * np.abs(np.sin(np.pi * xx / 0.5)) * (((xx // 0.5 + yy // 0.5) % 2) * 0.6 + 0.4) \
                  - 0.03 * np.abs(np.sin(np.pi * yy / 0.5)) * ((((xx // 0.5 + yy // 0.5) + 1) % 2) * 0.6 + 0.4) + noise
    else:
        light = 1 + noise
    image = Image.fromarray((base[None, None, :] * light[..., None]).clip(0, 255).astype('uint8'))
    return image.filter(ImageFilter.GaussianBlur(px * 0.05))


def look(stitches, px, comp, stretch=0.0, angle=0.0, fabric='#f2efe8', kind='', margin=3):
    """expected look: stitches = [(a, b, colour, underlay?)] in mm. Returns (image, x0, y0): the image's
    top left corner in the stitches' mm coordinates"""
    settled, satin = settle(stitches, comp, stretch, angle)
    xs = [q[0] for s in settled for q in s[:2]]
    ys = [q[1] for s in settled for q in s[:2]]
    x0, y0 = min(xs) - margin, min(ys) - margin
    width, height = int((max(xs) - x0 + margin) * px), int((max(ys) - y0 + margin) * px)
    thread = max(1, round(THREAD * px))

    def to_px(q):
        return ((q[0] - x0) * px, (q[1] - y0) * px)

    shadow = Image.new('L', (width, height), 0)
    shadow_draw = ImageDraw.Draw(shadow)
    offset = px * 0.12
    for a, b, colour, underlay in settled:
        A, B = to_px(a), to_px(b)
        shadow_draw.line([(A[0] + offset, A[1] + offset), (B[0] + offset, B[1] + offset)], fill=110, width=thread + 2)
    image = fabric_texture(width, height, px, fabric, kind)
    image.paste((40, 40, 50), (0, 0), shadow.filter(ImageFilter.GaussianBlur(px * 0.12)))
    draw = ImageDraw.Draw(image)
    for i, (a, b, colour, underlay) in enumerate(settled):
        A, B = to_px(a), to_px(b)
        length = math.dist(A, B)
        if underlay:
            draw.line([A, B], fill=shade(colour, 0.6), width=thread)
            continue
        if i not in satin or length < thread * 3:          # running stitch: even thread with a twist highlight
            draw.line([A, B], fill=shade(colour, 0.92), width=thread)
            draw.line([A, B], fill=shade(colour, 1.12), width=max(1, thread // 3))
            continue
        pieces = 14                                         # satin: dome, light on top, darker into the needle holes
        for k in range(pieces):
            t0, t1 = k / pieces, (k + 1) / pieces
            light = 0.62 + 0.62 * math.sin(math.pi * (t0 + t1) / 2) ** 0.8
            draw.line([(A[0] + (B[0] - A[0]) * t0, A[1] + (B[1] - A[1]) * t0), (A[0] + (B[0] - A[0]) * t1, A[1] + (B[1] - A[1]) * t1)],
                      fill=shade(colour, light), width=thread)
        nx, ny = -(B[1] - A[1]) / length, (B[0] - A[0]) / length      # fine groove to the next stitch
        r = thread / 2
        draw.line([(A[0] + nx * r, A[1] + ny * r), (B[0] + nx * r, B[1] + ny * r)], fill=shade(colour, 0.7), width=1)
    return image, x0, y0


# ---------------------------------------------------------------- catalogue picture

def line_picture(pattern, size=400, supersample=3):
    """catalogue picture: stitch lines in thread colour on light grey, size x size (as the library previews)"""
    points = [(x, y) for x, y, c in pattern.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
    x0, y0 = min(x for x, y in points), min(y for x, y in points)
    x1, y1 = max(x for x, y in points), max(y for x, y in points)
    canvas_size = size * supersample
    pad = canvas_size * 0.05
    scale = (canvas_size - 2 * pad) / max(x1 - x0, y1 - y0, 1)
    ox, oy = (canvas_size - (x1 - x0) * scale) / 2, (canvas_size - (y1 - y0) * scale) / 2
    image = Image.new('RGB', (canvas_size, canvas_size), (236, 236, 236))
    draw = ImageDraw.Draw(image)
    for block, thread in pattern.get_as_colorblocks():
        c = thread.color if thread else 0
        colour = ((c >> 16) & 255, (c >> 8) & 255, c & 255)
        line = []
        for x, y, command in block:
            if (command & pe.COMMAND_MASK) == pe.STITCH:
                line.append((ox + (x - x0) * scale, oy + (y - y0) * scale))
            else:
                if len(line) > 1:
                    draw.line(line, fill=colour, width=4)
                line = []
        if len(line) > 1:
            draw.line(line, fill=colour, width=4)
    return image.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- thread density

def density(stitches, box, cell=0.25, smooth=0.5):
    """thread length per mm2 on a grid of `cell` mm, smoothed (gaussian, `smooth` mm). Returns (grid, x0, y0)."""
    x0, y0, x1, y1 = box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2
    grid = np.zeros((int((y1 - y0) / cell) + 1, int((x1 - x0) / cell) + 1))
    for a, b, _ in stitches:
        length = math.dist(a, b)
        n = max(1, int(length / 0.05))
        t = (np.arange(n) + 0.5) / n
        column = ((a[0] + (b[0] - a[0]) * t - x0) / cell).astype(int)
        row = ((a[1] + (b[1] - a[1]) * t - y0) / cell).astype(int)
        np.add.at(grid, (row, column), length / n)
    return gaussian_filter(grid, smooth / cell) / (cell * cell), x0, y0


def density_image(grid, px_per_cell=1):
    """RGBA image: level colours, transparent where there is no thread"""
    rgba = np.zeros(grid.shape + (4,), dtype=np.uint8)
    low = BARE
    for high, colour, _ in LEVELS:
        mask = (grid > low) & (grid <= high)
        rgba[mask] = [int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16), 255]
        low = high
    image = Image.fromarray(rgba, 'RGBA')
    if px_per_cell > 1:
        return image.resize((image.width * px_per_cell, image.height * px_per_cell), Image.NEAREST)
    return image


def density_picture(grid, cell, px):
    """density image with its legend below"""
    image = density_image(grid, max(1, round(cell * px)))
    legend_height = 26 + 18 * len(LEVELS)
    picture = Image.new('RGB', (image.width, image.height + legend_height), (255, 255, 255))
    picture.paste(image, (0, 0), image)
    draw = ImageDraw.Draw(picture)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 13)
    except OSError:
        font = ImageFont.load_default()
    y = image.height + 6
    draw.text((8, y), 'thread length mm/mm²', fill=(0, 0, 0), font=font)
    y += 20
    for _, colour, label in LEVELS:
        draw.rectangle([8, y, 24, y + 13], fill=colour)
        draw.text((32, y), label, fill=(0, 0, 0), font=font)
        y += 18
    return picture


def level_shares(grid):
    """'under 2: 3.1%, 2–4: 20.0%, ... (max 8.8 mm/mm2)': share of the threaded area on each level"""
    values = grid[grid > BARE]
    low = BARE
    parts = []
    for high, _, label in LEVELS:
        share = ((values > low) & (values <= high)).sum() / len(values) * 100
        low = high
        if share >= 0.05:
            parts.append(f'{label.split(" – ")[0]}: {share:.1f}%')
    return ', '.join(parts) + f' (max {values.max():.1f} mm/mm2)'


def main():
    global THREAD
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')
    parser.add_argument('--fabric', default='#f2efe8', help='fabric colour')
    parser.add_argument('--px', type=float, default=10, help='pixels per mm')
    parser.add_argument('--line', action='store_true', help='also <file>.line.png: catalogue picture 400x400')
    parser.add_argument('--long', type=int, help='thread picture: longer side in pixels (instead of --px), e.g. 1200')
    parser.add_argument('--dir', default='check', help='folder for the pictures (default check/)')
    args = parser.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    for file_name in args.files:
        pattern = pe.read(file_name)
        meta_colours(pattern, file_name)
        stitches = segments(pattern)
        meta = find_meta(file_name)
        THREAD = 0.28 if int(meta.get('thread', 40)) == 60 else 0.4         # 60 wt is thinner
        xs = [q[0] for s in stitches for q in s[:2]]
        ys = [q[1] for s in stitches for q in s[:2]]
        box = (min(xs), min(ys), max(xs), max(ys))
        base = os.path.join(args.dir, os.path.splitext(os.path.basename(file_name))[0])
        px = args.long / max(box[2] - box[0], box[3] - box[1]) if args.long else args.px
        thread_picture(stitches, box, px, args.fabric).save(base + '.thread.png', optimize=True)
        params = meta.get('params', {})
        image, _, _ = look(segments_under(pattern, file_name), px, float(params.get('comp', 0.2)),
                           float(params.get('comp_stretch', 0)), float(params.get('stretch_angle', 0)),
                           args.fabric, meta.get('fabric', ''))
        image.save(base + '.look.png', optimize=True)
        if args.line:
            line_picture(pattern).save(base + '.line.png')
        grid, _, _ = density(stitches, box)
        density_picture(grid, 0.25, args.px).save(base + '.density.png')
        print(f'{file_name}: ' + level_shares(grid))


if __name__ == '__main__':
    main()
