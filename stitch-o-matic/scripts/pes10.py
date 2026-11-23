"""PES v6 (pyembroidery) -> PES v10 using the header of a v10 file that works on the target machine.
Stitches and the PEC block (what the machine sews) stay unchanged."""
import struct

import pyembroidery as pe


def _pascal_string(text):
    """length byte + latin-1 bytes, as the PES header stores strings"""
    data = text.encode('latin-1', 'replace')[:255]
    return bytes([len(data)]) + data


def _skip_string(data, position):
    return position + 1 + data[position]


def _v10_layout(data):
    """positions in a #PES0100 header: metadata strings, hoop name string, thread count"""
    assert data[:8] == b'#PES0100', 'working file is not PES v10'
    metadata = 16                       # 5 strings: name, category, author, keywords, comments
    position = metadata
    for _ in range(5):
        position = _skip_string(data, position)
    metadata_end = position
    hoop = position + 14
    hoop_end = _skip_string(data, hoop)
    image = hoop_end + 38
    image_end = _skip_string(data, image)
    threads = image_end + 34 + 6        # programmable fills, motifs, feather patterns (2 bytes each)
    return metadata, metadata_end, hoop, hoop_end, threads


def _v6_threads(data):
    """thread section (count + threads) and the start of the CEmbOne block in a #PES0060 file"""
    assert data[:8] == b'#PES0060'
    position = 16
    for _ in range(5):
        position = _skip_string(data, position)
    position += 36
    position = _skip_string(data, position)
    position += 24 + 6
    emb_one = data.find(b'\x07\x00CEmbOne')
    return position, emb_one


def to_v10(source, destination, working, name):
    """write destination: the v10 header of `working` (name = `name`) + the threads and blocks of the
    v6 `source`; checks that the stitches read back unchanged"""
    v6 = open(source, 'rb').read()
    working_data = open(working, 'rb').read()
    pec_offset = struct.unpack('<I', v6[8:12])[0]
    threads_v6, emb_one_v6 = _v6_threads(v6)
    metadata, metadata_end, hoop, hoop_end, threads_working = _v10_layout(working_data)
    header = (working_data[:metadata] + _pascal_string(name) + _pascal_string('') * 4 + working_data[metadata_end:hoop]
              + _pascal_string('') + working_data[hoop_end:threads_working])
    result = bytearray(header + v6[threads_v6:emb_one_v6] + v6[emb_one_v6:])
    result[0:8] = b'#PES0100'
    result[8:12] = struct.pack('<I', pec_offset + len(header) - threads_v6)
    open(destination, 'wb').write(result)
    before, after = pe.read(source), pe.read(destination)
    if [s[:] for s in before.stitches] != [s[:] for s in after.stitches]:
        raise RuntimeError(f'{destination}: stitches differ after v10 conversion')
    return after
