"""Check embroidery files: size, stitch lengths, trims, density, coverage.

    python3 check.py out/*.pes out/*.jef

Prints per file: size (mm), top left of the stitches, stitch count, trims, longest stitch (mm),
short stitches (0.05-0.3 mm), most needle points in one mm2; with outpos/<file>.shapes.json also
holes (uncovered spots, [] = fully covered) and over_edge (needle points past comp + 0.3 mm).
"""
import collections
import math
import os
import sys

import pyembroidery as pe

import coverage


def check(file_name):
    pattern = pe.read(file_name)
    lengths = []
    previous = None
    trims = 0
    last_command = None
    for x, y, command in pattern.stitches:
        command &= pe.COMMAND_MASK
        if command == pe.STITCH:
            if previous:
                lengths.append(math.dist(previous, (x, y)) / 10)
            previous = (x, y)
        elif command == pe.JUMP:
            previous = (x, y)
        elif command == pe.TRIM:
            if last_command == pe.STITCH:
                trims += 1
            previous = None
        if command in (pe.STITCH, pe.TRIM):
            last_command = command
    points = [(x, y) for x, y, c in pattern.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    per_mm2 = collections.Counter((int(x // 10), int(y // 10)) for x, y in points)
    return dict(size=(round((max(xs) - min(xs)) / 10, 1), round((max(ys) - min(ys)) / 10, 1)),
                min_xy=(min(xs) / 10, min(ys) / 10),
                stitches=len(points), trims=trims, max_len=round(max(lengths), 1),
                short=sum(0.05 <= length < 0.3 for length in lengths), max_per_mm2=per_mm2.most_common(1)[0][1])


def main():
    for file_name in sys.argv[1:]:
        result = check(file_name)
        # coverage is checked on the PES in outpos/ (also for a JEF)
        position_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(file_name))), 'outpos', os.path.basename(file_name))
        position_file = os.path.splitext(position_file)[0] + '.pes'
        if os.path.exists(position_file[:-4] + '.shapes.json') and os.path.exists(position_file):
            loaded = coverage.load(position_file)
            result['holes'] = coverage.holes(position_file, _d=loaded)          # [] = fully covered
            result['over_edge'] = coverage.overflow(position_file, _d=loaded)   # [] = no needle point past comp + 0.3 mm
        print(file_name, result)


if __name__ == '__main__':
    main()
