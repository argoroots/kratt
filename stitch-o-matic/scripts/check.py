"""Kontroll: python3 check.py out/*.pes"""
import sys, math, collections
import pyembroidery as pe


def check(fn):
    p = pe.read(fn); lens = []; prev = None; trims = 0; last_cmd = None
    for x, y, c in p.stitches:
        c &= pe.COMMAND_MASK
        if c == pe.STITCH:
            if prev: lens.append(math.dist(prev, (x, y)) / 10)
            prev = (x, y)
        elif c == pe.JUMP: prev = (x, y)
        elif c == pe.TRIM:
            if last_cmd == pe.STITCH: trims += 1
            prev = None
        if c in (pe.STITCH, pe.TRIM): last_cmd = c
    st = [(x, y) for x, y, c in p.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
    cell = collections.Counter((int(x // 10), int(y // 10)) for x, y in st)
    return dict(size=(round((max(a for a, b in st) - min(a for a, b in st)) / 10, 1), round((max(b for a, b in st) - min(b for a, b in st)) / 10, 1)),
                min_xy=(min(a for a, b in st) / 10, min(b for a, b in st) / 10),
                stitches=len(st), trims=trims, max_len=round(max(lens), 1),
                short=sum(0.05 <= l < 0.3 for l in lens), max_per_mm2=cell.most_common(1)[0][1])


if __name__ == '__main__':
    import os, coverage
    for f in sys.argv[1:]:
        r = check(f)
        pos = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(f))), 'outpos', os.path.basename(f))
        pos = os.path.splitext(pos)[0] + '.pes'                 # coverage is checked on the PES in outpos/ (also for a JEF)
        if os.path.exists(pos[:-4] + '.shapes.json') and os.path.exists(pos):
            d = coverage._load(pos)
            r['holes'] = coverage.holes(pos, _d=d)          # [] = fully covered
            r['over_edge'] = coverage.overflow(pos, _d=d)   # [] = no needle point past comp + 0.3 mm
        print(f, r)
