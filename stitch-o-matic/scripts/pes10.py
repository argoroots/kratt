"""PES v6 (pyembroidery) -> PES v10 using the header of a v10 file that works on the target machine.
Stitches and the PEC block (what the machine sews) stay unchanged."""
import struct
import pyembroidery as pe


def _pstr(s):
    b = s.encode('latin-1', 'replace')[:255]
    return bytes([len(b)]) + b


def _skip_str(b, pos):
    return pos + 1 + b[pos]


def _v10_layout(b):
    """positions in a #PES0100 header: metadata strings, hoop name string, thread count"""
    assert b[:8] == b'#PES0100', 'working file is not PES v10'
    meta = 16                       # 5 strings: name, category, author, keywords, comments
    pos = meta
    for _ in range(5): pos = _skip_str(b, pos)
    meta_end = pos
    hoop = pos + 14; hoop_end = _skip_str(b, hoop)
    img = hoop_end + 38; img_end = _skip_str(b, img)
    threads = img_end + 34 + 6      # programmable fills, motifs, feather patterns (2 bytes each)
    return meta, meta_end, hoop, hoop_end, threads


def _v6_threads(b):
    """thread section (count + threads) and the start of the CEmbOne block in a #PES0060 file"""
    assert b[:8] == b'#PES0060'
    pos = 16
    for _ in range(5): pos = _skip_str(b, pos)
    pos += 36; pos = _skip_str(b, pos); pos += 24 + 6
    ce = b.find(b'\x07\x00CEmbOne')
    return pos, ce


def to_v10(src, dst, working, name):
    v6 = open(src, 'rb').read(); W = open(working, 'rb').read()
    pec6 = struct.unpack('<I', v6[8:12])[0]
    th6, ce6 = _v6_threads(v6)
    meta, meta_end, hoop, hoop_end, thw = _v10_layout(W)
    head = (W[:meta] + _pstr(name) + _pstr('') * 4 + W[meta_end:hoop] + _pstr('') + W[hoop_end:thw])
    out = bytearray(head + v6[th6:ce6] + v6[ce6:])
    out[0:8] = b'#PES0100'
    out[8:12] = struct.pack('<I', pec6 + len(head) - th6)
    open(dst, 'wb').write(out)
    a, b = pe.read(src), pe.read(dst)
    if [s[:] for s in a.stitches] != [s[:] for s in b.stitches]:
        raise RuntimeError(f'{dst}: stitches differ after v10 conversion')
    return b
