#!/usr/bin/env python3
"""Build the PNG files the image tests decode.

Written with zlib and struct only — no image library — so the test inputs are
produced by code as independent of rigor's decoder as the decoder is of them.
Between them they cover every colour type, every bit depth the format allows
for it, both interlace methods, tRNS transparency in all three of its forms,
and each of the five scanline filters.

    python tools/gen_test_images.py
"""

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "tests", "images")


def chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def png(width, height, bit_depth, colour_type, raw, palette=None, trns=None,
        interlace=0):
    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth,
                                      colour_type, 0, 0, interlace))
    if palette is not None:
        out += chunk(b"PLTE", palette)
    if trns is not None:
        out += chunk(b"tRNS", trns)
    out += chunk(b"IDAT", zlib.compress(raw, 9))
    out += chunk(b"IEND", b"")
    return out


def pack_samples(samples, depth):
    """Pack a row of samples at 1, 2, 4, 8 or 16 bits each."""
    if depth == 8:
        return bytes(samples)
    if depth == 16:
        return b"".join(struct.pack(">H", s) for s in samples)
    per_byte = 8 // depth
    out = bytearray()
    for start in range(0, len(samples), per_byte):
        byte = 0
        for index in range(per_byte):
            value = samples[start + index] if start + index < len(samples) else 0
            byte = (byte << depth) | value
        out.append(byte)
    return bytes(out)


def scanlines(rows, depth, filter_type=0):
    """Prefix each packed row with a filter byte. Filter 0 keeps it simple."""
    return b"".join(bytes([filter_type]) + pack_samples(row, depth)
                    for row in rows)


def filtered_rgb(rows, filters):
    """Apply a different filter to each row, so all five are exercised.

    Filtering works on bytes, using the byte one pixel to the left and the
    reconstructed byte above — the same neighbours the decoder will use.
    """
    stride = len(rows[0]) * 3
    out = bytearray()
    previous = bytes(stride)
    for row, filter_type in zip(rows, filters):
        raw = bytearray()
        for pixel in row:
            raw += bytes(pixel)
        encoded = bytearray()
        for index in range(stride):
            a = raw[index - 3] if index >= 3 else 0
            b = previous[index]
            c = previous[index - 3] if index >= 3 else 0
            x = raw[index]
            if filter_type == 0:
                encoded.append(x)
            elif filter_type == 1:
                encoded.append((x - a) & 0xFF)
            elif filter_type == 2:
                encoded.append((x - b) & 0xFF)
            elif filter_type == 3:
                encoded.append((x - (a + b) // 2) & 0xFF)
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                encoded.append((x - pred) & 0xFF)
        out += bytes([filter_type]) + encoded
        previous = bytes(raw)
    return bytes(out)


def adam7_passes(width, height):
    starts = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
              (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    for x0, y0, dx, dy in starts:
        columns = 0 if width <= x0 else (width - x0 + dx - 1) // dx
        rows = 0 if height <= y0 else (height - y0 + dy - 1) // dy
        yield x0, y0, dx, dy, columns, rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []

    def write(name, data):
        path = os.path.join(OUT_DIR, name)
        with open(path, "wb") as handle:
            handle.write(data)
        written.append((name, len(data)))

    # 4x4 truecolour: a red/green/blue/white quadrant pattern.
    quad = [
        [(255, 0, 0), (255, 0, 0), (0, 255, 0), (0, 255, 0)],
        [(255, 0, 0), (255, 0, 0), (0, 255, 0), (0, 255, 0)],
        [(0, 0, 255), (0, 0, 255), (255, 255, 255), (255, 255, 255)],
        [(0, 0, 255), (0, 0, 255), (255, 255, 255), (255, 255, 255)],
    ]
    flat = [[c for pixel in row for c in pixel] for row in quad]
    write("rgb8.png", png(4, 4, 8, 2, scanlines(flat, 8)))

    # The same image with a different filter on each row.
    write("rgb8-filters.png",
          png(4, 4, 8, 2, filtered_rgb(quad, [0, 1, 2, 3])))
    write("rgb8-paeth.png",
          png(4, 4, 8, 2, filtered_rgb(quad, [4, 4, 4, 4])))

    # Truecolour with alpha: the same quadrants, with the bottom half at half
    # opacity.
    rgba = []
    for y, row in enumerate(quad):
        out = []
        for pixel in row:
            out.extend(pixel)
            out.append(255 if y < 2 else 128)
        rgba.append(out)
    write("rgba8.png", png(4, 4, 8, 6, scanlines(rgba, 8)))

    # Greyscale at 8 and 16 bits.
    grey = [[0, 85, 170, 255], [255, 170, 85, 0],
            [0, 85, 170, 255], [255, 170, 85, 0]]
    write("grey8.png", png(4, 4, 8, 0, scanlines(grey, 8)))
    grey16 = [[v * 257 for v in row] for row in grey]
    write("grey16.png", png(4, 4, 16, 0, scanlines(grey16, 16)))

    # Greyscale at the sub-byte depths, which pack several pixels per byte.
    write("grey1.png", png(8, 2, 1, 0,
                          scanlines([[0, 1, 0, 1, 1, 1, 0, 0],
                                     [1, 0, 1, 0, 0, 0, 1, 1]], 1)))
    write("grey2.png", png(4, 2, 2, 0,
                          scanlines([[0, 1, 2, 3], [3, 2, 1, 0]], 2)))
    write("grey4.png", png(4, 2, 4, 0,
                          scanlines([[0, 5, 10, 15], [15, 10, 5, 0]], 4)))

    # Greyscale with alpha.
    grey_alpha = [[0, 255, 255, 0], [128, 255, 200, 128]]
    write("greya8.png", png(2, 2, 8, 4, scanlines(grey_alpha, 8)))

    # Palette, at 8 bits and at 4.
    palette = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0])
    write("palette8.png", png(4, 2, 8, 3,
                             scanlines([[0, 1, 2, 3], [3, 2, 1, 0]], 8),
                             palette=palette))
    write("palette4.png", png(4, 2, 4, 3,
                             scanlines([[0, 1, 2, 3], [3, 2, 1, 0]], 4),
                             palette=palette))
    # The same palette with the first entry transparent.
    write("palette8-trns.png", png(4, 2, 8, 3,
                                   scanlines([[0, 1, 2, 3], [3, 2, 1, 0]], 8),
                                   palette=palette,
                                   trns=bytes([0, 255, 255, 255])))

    # tRNS on greyscale and on truecolour: one value becomes transparent.
    write("grey8-trns.png", png(4, 2, 8, 0,
                                scanlines([[0, 85, 170, 255],
                                           [255, 170, 85, 0]], 8),
                                trns=struct.pack(">H", 0)))
    write("rgb8-trns.png", png(2, 2, 8, 2,
                               scanlines([[255, 0, 0, 0, 255, 0],
                                          [0, 0, 255, 255, 255, 255]], 8),
                               trns=struct.pack(">HHH", 255, 0, 0)))

    # Interlaced, so the Adam7 path runs. Each pixel is its own colour, so a
    # pass landing in the wrong place is visible.
    width, height = 8, 8
    pixels = [[((x * 32) % 256, (y * 32) % 256, ((x + y) * 16) % 256)
               for x in range(width)] for y in range(height)]
    raw = b""
    for x0, y0, dx, dy, columns, rows in adam7_passes(width, height):
        if columns == 0 or rows == 0:
            continue
        lines = []
        for row in range(rows):
            line = []
            for column in range(columns):
                line.extend(pixels[y0 + row * dy][x0 + column * dx])
            lines.append(line)
        raw += scanlines(lines, 8)
    write("rgb8-interlaced.png", png(width, height, 8, 2, raw, interlace=1))
    # And the same image without interlacing, so a test can compare them.
    write("rgb8-progressive.png",
          png(width, height, 8, 2,
              scanlines([[c for pixel in row for c in pixel] for row in pixels], 8)))

    # A larger image, so the inflater meets a dynamic Huffman block rather than
    # only the fixed one small inputs get.
    big = []
    for y in range(64):
        line = []
        for x in range(64):
            line.extend(((x * y) % 256, (x ^ y) % 256, (x + y) % 256))
        big.append(line)
    write("rgb8-large.png", png(64, 64, 8, 2, scanlines(big, 8)))

    for name, size in written:
        print(f"wrote {os.path.join('tests', 'images', name)} ({size} bytes)")


if __name__ == "__main__":
    main()
