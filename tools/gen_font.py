#!/usr/bin/env python3
"""Generate engine/src/paint/font.mx from the vendored font8x8 bitmap font.

Source is tools/vendor/font8x8/font8x8_basic.h — Daniel Hepper's public-domain
8x8 monochrome font, itself derived from Marcel Sondaar's work. It is vendored
rather than fetched at build time so builds stay offline and reproducible.

The header stores each glyph as eight bytes, one per row, with bit 0 as the
leftmost pixel. That bit order is preserved here so the renderer's inner loop
is a shift and mask.

    python tools/gen_font.py
    python tools/gen_font.py --check
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(HERE, "vendor", "font8x8", "font8x8_basic.h")
OUTPUT = os.path.join(ROOT, "engine", "src", "paint", "font.mx")


def load_glyphs():
    with open(SOURCE, "r", encoding="utf-8") as handle:
        text = handle.read()
    # Each glyph is a brace-delimited run of eight hex bytes.
    rows = re.findall(r"\{([^{}]*0x[^{}]*)\}", text)
    glyphs = []
    for row in rows:
        values = re.findall(r"0x([0-9A-Fa-f]{2})", row)
        if len(values) == 8:
            glyphs.append([int(v, 16) for v in values])
    if len(glyphs) != 128:
        raise SystemExit(f"expected 128 glyphs, parsed {len(glyphs)}")
    return glyphs


def emit(glyphs):
    flat = [byte for glyph in glyphs for byte in glyph]
    lines = []
    for start in range(0, len(flat), 16):
        chunk = flat[start:start + 16]
        lines.append("    " + ", ".join(f"0x{b:02X}" for b in chunk) + ",")
    table = "\n".join(lines)
    if table.endswith(","):
        table = table[:-1]

    return f"""// An 8x8 bitmap font.
//
// GENERATED FILE — do not edit by hand.
// Regenerate with: python tools/gen_font.py
//
// Source: tools/vendor/font8x8/font8x8_basic.h, Daniel Hepper's public-domain
// 8x8 monochrome font (based on work by Marcel Sondaar). Vendored so builds
// are offline and reproducible.
//
// This is a stand-in until real font parsing lands: glyphs are monospaced and
// only cover ASCII, so text rendered through it is legible but neither shaped
// nor metrically matched to the advances engine.layout.metrics reports. Paint
// scales each glyph to the nearest whole multiple of 8 pixels and positions it
// using the layout advance, so the two stay in step even though the shapes are
// not proportional.
//
// Each glyph is eight bytes, one per row, with bit 0 the leftmost pixel.
module engine.paint.font;

const FONT_GLYPH_HEIGHT: u64 = 8;
const FONT_GLYPH_WIDTH: u64 = 8;

pub fn glyph_height() -> u64 {{ return FONT_GLYPH_HEIGHT; }}
pub fn glyph_width() -> u64 {{ return FONT_GLYPH_WIDTH; }}

let FONT_ROWS: [u8; {len(flat)}] = [
{table}
];

// One row of a glyph's bitmap. Code points outside ASCII render as blank,
// which is honest: this font has no glyphs for them.
pub fn glyph_row(code: u32, row: u64) -> u8 {{
    if code >= 128 as u32 || row >= FONT_GLYPH_HEIGHT {{
        return 0 as u8;
    }}
    return FONT_ROWS[(code as u64) * FONT_GLYPH_HEIGHT + row];
}}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail if the generated file is out of date")
    args = parser.parse_args()

    if not os.path.isfile(SOURCE):
        raise SystemExit(f"missing {SOURCE}")
    text = emit(load_glyphs())

    if args.check:
        with open(OUTPUT, "r", encoding="utf-8", newline="") as handle:
            current = handle.read()
        if current.replace("\r\n", "\n") != text:
            print("font.mx is out of date; run python tools/gen_font.py",
                  file=sys.stderr)
            return 1
        print("font.mx is up to date (128 glyphs)")
        return 0

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {OUTPUT} (128 glyphs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
