#!/usr/bin/env python3
"""Build the tiny fonts the text tests need, from scratch.

Two things in engine.text cannot be tested against the fonts a machine happens
to have installed: CFF outlines (Windows ships no .otf files) and a kerning
table with known values. So this builds them.

    python tools/gen_test_font.py

Writes tests/fonts/cff-test.otf and tests/fonts/kern-test.ttf. Both are real
files a font library would accept, small enough to vendor and simple enough to
assert exact numbers about.
"""

import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "tests", "fonts")

UNITS_PER_EM = 1000
ASCENDER = 800
DESCENDER = -200


# --- SFNT container ----------------------------------------------------------

def sfnt(version, tables):
    """Assemble a font file from {tag: bytes}."""
    count = len(tables)
    search_range = 1
    entry_selector = 0
    while search_range * 2 <= count:
        search_range *= 2
        entry_selector += 1
    search_range *= 16
    range_shift = count * 16 - search_range

    header = struct.pack(">4sHHHH", version, count, search_range,
                         entry_selector, range_shift)
    offset = len(header) + 16 * count
    directory = b""
    body = b""
    for tag in sorted(tables):
        data = tables[tag]
        padded = data + b"\0" * (-len(data) % 4)
        checksum = sum(struct.unpack(">%dI" % (len(padded) // 4), padded)) & 0xFFFFFFFF
        directory += struct.pack(">4sIII", tag.encode("ascii"), checksum,
                                 offset, len(data))
        body += padded
        offset += len(padded)
    return header + directory + body


def head_table():
    return struct.pack(
        ">IIIIHHQQhhhhHHhhh",
        0x00010000,          # version
        0x00010000,          # fontRevision
        0,                   # checkSumAdjustment
        0x5F0F3CF5,          # magicNumber
        0,                   # flags
        UNITS_PER_EM,
        0, 0,                # created, modified
        0, DESCENDER, UNITS_PER_EM, ASCENDER,   # bounding box
        0,                   # macStyle
        8,                   # lowestRecPPEM
        0,                   # fontDirectionHint
        0,                   # indexToLocFormat (short)
        0,                   # glyphDataFormat
    )


def hhea_table(num_h_metrics):
    return struct.pack(
        ">IhhhHhhhhhhhhhhhH",
        0x00010000,
        ASCENDER, DESCENDER, 0,
        UNITS_PER_EM,        # advanceWidthMax
        0, 0, 0,             # min side bearings, xMaxExtent
        1, 0, 0,             # caret slope and offset
        0, 0, 0, 0,          # four reserved
        0,                   # metricDataFormat
        num_h_metrics,
    )


def maxp_table(num_glyphs, cff):
    if cff:
        return struct.pack(">IH", 0x00005000, num_glyphs)
    return struct.pack(">IH", 0x00010000, num_glyphs) + b"\0" * 26


def hmtx_table(advances):
    return b"".join(struct.pack(">Hh", advance, 0) for advance in advances)


def cmap_table(mapping):
    """A format 4 subtable covering the code points in `mapping`."""
    points = sorted(mapping)
    segments = [(cp, cp, mapping[cp]) for cp in points]
    segments.append((0xFFFF, 0xFFFF, 0))
    seg_count = len(segments)

    ends = b"".join(struct.pack(">H", end) for _, end, _ in segments)
    starts = b"".join(struct.pack(">H", start) for start, _, _ in segments)
    deltas = b"".join(
        struct.pack(">h", ((glyph - start) & 0xFFFF) - (0x10000 if ((glyph - start) & 0xFFFF) > 0x7FFF else 0))
        for start, _, glyph in segments)
    range_offsets = b"\0\0" * seg_count

    search_range = 2
    entry_selector = 0
    while search_range * 2 <= seg_count * 2:
        search_range *= 2
        entry_selector += 1
    subtable = struct.pack(">HHHHHH", 4, 16 + 8 * seg_count, 0,
                           seg_count * 2, search_range, entry_selector)
    subtable += struct.pack(">H", seg_count * 2 - search_range)
    subtable += ends + b"\0\0" + starts + deltas + range_offsets
    header = struct.pack(">HHHHI", 0, 1, 3, 1, 12)
    return header + subtable


# --- CFF ----------------------------------------------------------------------

def cff_index(items):
    if not items:
        return struct.pack(">H", 0)
    offsets = [1]
    for item in items:
        offsets.append(offsets[-1] + len(item))
    size = 1
    while offsets[-1] > (1 << (8 * size)) - 1:
        size += 1
    data = struct.pack(">HB", len(items), size)
    for offset in offsets:
        data += offset.to_bytes(size, "big")
    return data + b"".join(items)


def dict_operand(value):
    value = int(value)
    if -107 <= value <= 107:
        return bytes([value + 139])
    if 108 <= value <= 1131:
        value -= 108
        return bytes([(value >> 8) + 247, value & 0xFF])
    if -1131 <= value <= -108:
        value = -value - 108
        return bytes([(value >> 8) + 251, value & 0xFF])
    if -32768 <= value <= 32767:
        return b"\x1c" + struct.pack(">h", value)
    return b"\x1d" + struct.pack(">i", value)


def dict_entry(operator, *values):
    body = b"".join(dict_operand(value) for value in values)
    if operator >= 1200:
        return body + bytes([12, operator - 1200])
    return body + bytes([operator])


def t2_operand(value):
    value = int(value)
    if -107 <= value <= 107:
        return bytes([value + 139])
    if 108 <= value <= 1131:
        value -= 108
        return bytes([(value >> 8) + 247, value & 0xFF])
    if -1131 <= value <= -108:
        value = -value - 108
        return bytes([(value >> 8) + 251, value & 0xFF])
    return b"\x1c" + struct.pack(">h", value)


def charstring(*tokens):
    out = b""
    for token in tokens:
        if isinstance(token, str):
            out += {
                "rmoveto": b"\x15", "hmoveto": b"\x16", "vmoveto": b"\x04",
                "rlineto": b"\x05", "hlineto": b"\x06", "vlineto": b"\x07",
                "rrcurveto": b"\x08", "endchar": b"\x0e",
                "hstem": b"\x01", "callsubr": b"\x0a", "return": b"\x0b",
            }[token]
        else:
            out += t2_operand(token)
    return out


def cff_table(charstrings, subrs):
    name = cff_index([b"RigorTest"])
    strings = cff_index([])
    gsubrs = cff_index([])

    charstrings_index = cff_index(charstrings)
    local_subrs = cff_index(subrs)
    header = bytes([1, 0, 4, 2])

    # The Private DICT's Subrs offset is relative to the DICT itself, and the
    # subroutines follow it immediately, so that offset is its own size.
    def private_dict(size):
        return dict_entry(20, 0) + dict_entry(21, 0) + dict_entry(19, size)

    private_size = len(private_dict(0))
    while len(private_dict(private_size)) != private_size:
        private_size = len(private_dict(private_size))
    private_body = private_dict(private_size)

    # The Top DICT holds absolute offsets, and its own size depends on how big
    # those offsets are — so the layout is iterated to a fixed point rather
    # than guessed at.
    def top_dict(charstrings_offset, private_offset):
        return (dict_entry(15, 0)                       # charset: ISOAdobe
                + dict_entry(16, 0)                     # encoding: standard
                + dict_entry(17, charstrings_offset)
                + dict_entry(18, private_size, private_offset))

    charstrings_offset = 0
    private_offset = 0
    for _ in range(8):
        top = cff_index([top_dict(charstrings_offset, private_offset)])
        prefix = len(header) + len(name) + len(top) + len(strings) + len(gsubrs)
        next_charstrings = prefix
        next_private = next_charstrings + len(charstrings_index)
        if (next_charstrings, next_private) == (charstrings_offset, private_offset):
            break
        charstrings_offset = next_charstrings
        private_offset = next_private

    top = cff_index([top_dict(charstrings_offset, private_offset)])
    body = (header + name + top + strings + gsubrs + charstrings_index
            + private_body + local_subrs)
    # The layout has to agree with itself, or the parser reads the wrong bytes.
    assert body[charstrings_offset:charstrings_offset + len(charstrings_index)] \
        == charstrings_index, "CharStrings offset did not converge"
    assert body[private_offset:private_offset + private_size] == private_body, \
        "Private DICT offset did not converge"
    assert body[private_offset + private_size:] == local_subrs, \
        "Subrs offset did not converge"
    return body


def build_cff_font():
    # Glyph 0 .notdef (empty), 1 a 600x600 square, 2 a triangle drawn with a
    # subroutine call, 3 a curved shape so the Bézier path is exercised.
    square = charstring(
        100, 100, "rmoveto",
        600, "hlineto",
        600, "vlineto",
        -600, "hlineto",
        "endchar")
    # A subroutine is called by its biased number: with fewer than 1240 local
    # subroutines the bias is 107, so subroutine 0 is called as -107.
    triangle = charstring(-107, "callsubr", "endchar")
    curve = charstring(
        100, 100, "rmoveto",
        200, 0, 200, 400, 0, 400, "rrcurveto",
        "endchar")
    subr = charstring(
        100, 100, "rmoveto",
        600, 0, "rlineto",
        -300, 600, "rlineto",
        "return")

    charstrings = [charstring("endchar"), square, triangle, curve]
    tables = {
        "head": head_table(),
        "hhea": hhea_table(4),
        "hmtx": hmtx_table([500, 800, 800, 800]),
        "maxp": maxp_table(4, cff=True),
        "cmap": cmap_table({ord("A"): 1, ord("B"): 2, ord("C"): 3}),
        "CFF ": cff_table(charstrings, [subr]),
    }
    return sfnt(b"OTTO", tables)


# --- A TrueType font with a known kern table ---------------------------------

def glyf_square():
    """One contour: a square from (100,100) to (700,700), as a simple glyph."""
    header = struct.pack(">hhhhh", 1, 100, 100, 700, 700)
    end_points = struct.pack(">H", 3)
    instructions = struct.pack(">H", 0)
    # All four points on-curve, with x and y as signed 16-bit deltas.
    flags = bytes([0x01, 0x01, 0x01, 0x01])
    xs = struct.pack(">hhhh", 100, 600, 0, -600)
    ys = struct.pack(">hhhh", 100, 0, 600, 0)
    return header + end_points + instructions + flags + xs + ys


def kern_table(pairs):
    """A format 0 subtable, which is a sorted array of (left, right, value)."""
    entries = sorted(pairs)
    search_range = 2
    entry_selector = 0
    while search_range * 2 <= len(entries) * 6:
        search_range *= 2
        entry_selector += 1
    subtable = struct.pack(">HHHHHHH",
                           0,                       # version
                           14 + 6 * len(entries),   # length
                           0x0001,                  # coverage: horizontal, fmt 0
                           len(entries), search_range, entry_selector,
                           len(entries) * 6 - search_range)
    for left, right, value in entries:
        subtable += struct.pack(">HHh", left, right, value)
    return struct.pack(">HH", 0, 1) + subtable


def build_kern_font():
    empty = b""
    square = glyf_square()
    glyf = empty + square + square
    loca = struct.pack(">HHH", 0, 0, len(square) // 2)
    loca += struct.pack(">H", (len(square) * 2) // 2)
    tables = {
        "head": head_table(),
        "hhea": hhea_table(3),
        "hmtx": hmtx_table([500, 700, 700]),
        "maxp": maxp_table(3, cff=False),
        "cmap": cmap_table({ord("A"): 1, ord("V"): 2}),
        "loca": loca,
        "glyf": glyf,
        # A large negative kern for A followed by V, and a positive one the
        # other way round, so a test can tell direction from the sign.
        "kern": kern_table([(1, 2, -120), (2, 1, 40)]),
    }
    return sfnt(b"\x00\x01\x00\x00", tables)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cff_path = os.path.join(OUT_DIR, "cff-test.otf")
    with open(cff_path, "wb") as handle:
        handle.write(build_cff_font())
    kern_path = os.path.join(OUT_DIR, "kern-test.ttf")
    with open(kern_path, "wb") as handle:
        handle.write(build_kern_font())
    print(f"wrote {cff_path} ({os.path.getsize(cff_path)} bytes)")
    print(f"wrote {kern_path} ({os.path.getsize(kern_path)} bytes)")


if __name__ == "__main__":
    main()
