"""Test swatch: the same design several times with one parameter changed, numbered.

python3 swatch.py logo.svg --name Proov --size 60 --vary satin_spacing=0.35,0.4,0.45 --machines brother
       [--working toimiv.pes] [--angle 45] [--background "#ffffff"] [--set fill_spacing=0.3] [--gap 8]
       [--only 0,2,5] [--list]

--list   prints the shapes of the SVG with numbers and positions (mm at --size), the stitch type the rules
         pick and other techniques worth offering (with the measured reason), then stops. Needs only --size.
--only   uses only these shapes, in one row, at the scale they have when the whole design is
         --size mm (e.g. only the difficult letters of a 150 mm logo).

Each variant gets a number stitched under it (running stitch, first colour).
Writes out/<Nimi>.pes / .jef (one file, all variants), out/<Nimi>.txt (number -> value)
and out/<Nimi>.thread.png (thread preview with the numbers).
"""
import argparse, json, math, os
import pyembroidery as pe
import design, digitize, gen

# digits as strokes on a 2 x 4 box (x right, y down)
SEG = {'a': ((0, 0), (2, 0)), 'b': ((2, 0), (2, 2)), 'c': ((2, 2), (2, 4)), 'd': ((2, 4), (0, 4)),
       'e': ((0, 4), (0, 2)), 'f': ((0, 2), (0, 0)), 'g': ((0, 2), (2, 2))}
DIG = {'0': 'fabcde', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd',
       '6': 'afedcg', '7': 'abc', '8': 'abcdefg', '9': 'gfabcd'}


def digit_path(ch):
    """one continuous path through the segments (segments may be walked twice)"""
    segs = [SEG[s] for s in DIG[ch]]
    path = [segs[0][0], segs[0][1]]
    todo = segs[1:]
    while todo:
        cur = path[-1]
        nxt = next((s for s in todo if cur in s), None)
        if nxt is None:      # walk back along drawn lines to an end of a remaining segment
            nxt = todo[0]; tgt = nxt[0]
            path += back_to(path, tgt)
            cur = path[-1]
        todo.remove(nxt)
        path.append(nxt[1] if nxt[0] == cur else nxt[0])
    return path


def back_to(path, tgt):
    i = max(k for k, q in enumerate(path) if q == tgt) if tgt in path else 0
    return path[i:-1][::-1] if tgt in path else [tgt]


def number_stitches(text, x, y, h=6.0, step=1.0):
    """running stitch (there, back, there) for a number; top-left corner at x, y (mm)"""
    s = h / 4; out = []
    for i, ch in enumerate(text):
        pts = [(x + i * 3.2 * s + px * s, y + py * s) for px, py in digit_path(ch)]
        run = []
        for a, b in zip(pts, pts[1:]):
            n = max(1, math.ceil(math.dist(a, b) / step))
            run += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
        run.append(pts[-1])
        out.append(run + run[-2::-1] + run[1:])
    return out


def blocks(p):
    """split a pattern into colour blocks of commands (x, y, cmd) in 0.1 mm"""
    res = [[]]
    for x, y, c in p.stitches:
        c &= pe.COMMAND_MASK
        if c == pe.COLOR_CHANGE: res.append([]); continue
        if c == pe.END: continue
        res[-1].append((x, y, c))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('svg'); ap.add_argument('--name')
    ap.add_argument('--size', type=float, required=True, help='longer side of one variant, mm')
    ap.add_argument('--vary', help='parameter=v1,v2,... (see digitize.DEFAULTS)')
    ap.add_argument('--machines')
    ap.add_argument('--working'); ap.add_argument('--angle', type=float, default=digitize.DEFAULTS['fill_angle'])
    ap.add_argument('--background', default='#ffffff')
    ap.add_argument('--fabric', help='fabric: ' + ', '.join(digitize.FABRICS))
    ap.add_argument('--plan', help='plan.json: decisions per shape (see digitize.build)')
    ap.add_argument('--set', action='append', default=[])
    ap.add_argument('--gap', type=float, default=8.0, help='space between variants, mm')
    ap.add_argument('--only', help='shape numbers from --list, e.g. 0,2,5')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if not a.list and not (a.name and a.vary and a.machines): ap.error('--name, --vary and --machines are required (except with --list)')
    key, vals = (a.vary or 'comp=0').split('=', 1)
    if key == 'angle': key = 'fill_angle'
    if key not in digitize.DEFAULTS: raise SystemExit(f'unknown parameter {key}; choose from: {", ".join(digitize.DEFAULTS)}')
    vals = [float(v) for v in vals.split(',')]
    mach = [m.strip().lower() for m in (a.machines or '').split(',') if m.strip()]
    cfg = dict(digitize.FABRICS[a.fabric]) if a.fabric else {}
    cfg['fill_angle'] = a.angle
    for kv in a.set:
        k, v = kv.split('='); cfg[k] = float(v)
    els = design.load(a.svg, a.background)
    size = a.size
    if a.list or a.only:
        from shapely.ops import unary_union
        from shapely import affinity
        ext = lambda es: unary_union([e['geom'] if e['kind'] == 'fill' else e['geom'].buffer(e.get('width', 0) / 2) for e in es]).bounds
        x0, y0, x1, y1 = ext(els); k = a.size / max(x1 - x0, y1 - y0)       # mm per SVG unit
        if a.list:
            for i, e in enumerate(els):
                b = e['geom'].bounds
                print(f'{i:3}  {e["kind"]:4} {e["color"]}  x {(b[0] - x0) * k:6.1f}–{(b[2] - x0) * k:6.1f}  y {(b[1] - y0) * k:6.1f}–{(b[3] - y0) * k:6.1f} mm')
                if e['kind'] == 'fill':           # what the rules pick, and what else to offer (KNOWLEDGE 10)
                    rule, hints = digitize.suggest(affinity.scale(e['geom'], k, k, origin=(0, 0)), dict(digitize.DEFAULTS, **cfg))
                    print(f'       rule: {rule}' + ''.join(f'\n       suggest: {t} – {why}' for t, why in hints))
            return
        pick = [els[int(i)] for i in a.only.split(',')]
        cur = None; out_ = []; base = pick[0]['geom'].bounds[3]
        for e in pick:                       # in one row, 3 mm apart, bottoms on one line
            b = e['geom'].bounds
            dx = 0 if cur is None else cur - b[0]
            out_.append(dict(e, geom=affinity.translate(e['geom'], dx, base - b[3])))
            cur = b[2] + dx + 3 / k
        els = out_
        x0, y0, x1, y1 = ext(els); size = max(x1 - x0, y1 - y0) * k
    plan = json.load(open(a.plan)) if a.plan else None
    if plan and a.only:   # plan numbers are the original shape numbers; here shapes are renumbered 0..n-1
        ids = [int(i) for i in a.only.split(',')]
        plan = dict(plan, shapes={str(ids.index(int(k))): v for k, v in (plan.get('shapes') or {}).items() if int(k) in ids},
                    order=[ids.index(int(k)) for k in plan.get('order') or [] if int(k) in ids])
    pats = [digitize.build(els, size, {}, dict(cfg, **{key: v}), ref_size=size, plan=plan) for v in vals]
    # cell size = largest variant + room for the number
    def box(p):
        st = [(x, y) for x, y, c in p.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
        return min(x for x, y in st), min(y for x, y in st), max(x for x, y in st), max(y for x, y in st)
    bx = [box(p) for p in pats]
    cw = max(b[2] - b[0] for b in bx) / 10 + a.gap
    ch = max(b[3] - b[1] for b in bx) / 10 + 3 + 6 + a.gap
    hoops = [gen.MACHINES[m][2] for m in mach]
    n = len(vals); best = None
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols); W, H = cols * cw - a.gap, rows * ch - a.gap
        ok = all((W <= hw and H <= hh) or (W <= hh and H <= hw) for hw, hh in hoops)
        sc = (not ok, max(W, H))
        if best is None or sc < best[0]: best = (sc, cols, W, H)
    (bad, _), cols, W, H = best
    if bad: print(f'WARNING: {n} variants ({W:.0f} x {H:.0f} mm) do not fit the hoop; reduce --size or the number of values')
    # assemble: colour by colour, every variant, numbers with the first colour
    ncol = len(blocks(pats[0]))
    out = pe.EmbPattern()
    for t in pats[0].threadlist: out.add_thread(t)
    first = True
    def go(x, y):
        nonlocal first
        if not first: out.add_stitch_absolute(pe.TRIM, x, y)
        out.add_stitch_absolute(pe.JUMP, x, y); first = False
    for ci in range(ncol):
        if ci: out.add_stitch_absolute(pe.COLOR_CHANGE, *out.stitches[-1][:2])
        for k, p in enumerate(pats):
            r, c = divmod(k, cols)
            ox = c * cw * 10 - bx[k][0] + (cw - a.gap) * 5 - (bx[k][2] - bx[k][0]) / 2
            oy = r * ch * 10 - bx[k][1]
            blk = blocks(p)[ci]
            st = [q for q in blk if q[2] == pe.STITCH]
            if not st: continue
            go(st[0][0] + ox, st[0][1] + oy)
            for x, y, cmd in blk:
                if cmd in (pe.STITCH, pe.JUMP, pe.TRIM): out.add_stitch_absolute(cmd, x + ox, y + oy)
            if ci == 0:
                txt = str(k + 1)
                nx = c * cw + (cw - a.gap) / 2 - len(txt) * 3.2 * 1.5 / 2
                ny = r * ch + (bx[k][3] - bx[k][1]) / 10 + 3
                for run in number_stitches(txt, nx, ny):
                    go(run[0][0] * 10, run[0][1] * 10)
                    for x, y in run: out.add_stitch_absolute(pe.STITCH, round(x * 10), round(y * 10))
    out.add_stitch_absolute(pe.TRIM, *out.stitches[-1][:2]); out.add_stitch_absolute(pe.END, *out.stitches[-1][:2])
    os.makedirs('out', exist_ok=True); os.makedirs('outpos', exist_ok=True)
    st = [(x, y) for x, y, c in out.stitches if c == pe.STITCH]
    mx, my = min(x for x, y in st), min(y for x, y in st)
    w, h = (max(x for x, y in st) - mx) / 10, (max(y for x, y in st) - my) / 10
    if 'janome' in mach:
        cx, cy = mx + w * 5, my + h * 5
        j = pe.EmbPattern(); j.threadlist = list(out.threadlist)
        j.stitches = [[x - round(cx), y - round(cy), c] for x, y, c in out.stitches]
        pe.write_jef(j, f'out/{a.name}.jef', {'trims': True}); gen.bmp(j, f'out/{a.name}.bmp')
    out.translate(-mx, -my)
    label = gen.ascii_name(a.name)[:8]; out.metadata('name', label)
    if 'brother' in mach:
        pe.write_pes(out, f'outpos/{a.name}.pes', {'version': 6})
        if a.working:
            import pes10; pes10.to_v10(f'outpos/{a.name}.pes', f'out/{a.name}.pes', a.working, label)
        else:
            import shutil; shutil.copy(f'outpos/{a.name}.pes', f'out/{a.name}.pes')
    with open(f'out/{a.name}.txt', 'w') as f:
        f.write(f'{a.name}: {a.svg}, {a.size:g} mm, muudetud {key}\n')
        for k, v in enumerate(vals): f.write(f'{k + 1}: {key} = {v:g}\n')
    import preview
    segs = preview.segments(out)
    preview.thread_picture(segs, (0, 0, w, h), 8, '#f2efe8').save(f'out/{a.name}.thread.png')
    print(f'{a.name}: {n} variants, {w:.0f} x {h:.0f} mm, {len(st)} stitches')
    for k, v in enumerate(vals): print(f'  {k + 1}: {key} = {v:g}')


if __name__ == '__main__':
    main()
