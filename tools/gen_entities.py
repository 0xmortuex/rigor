#!/usr/bin/env python3
"""Generate engine/src/html/entities.mx from the WHATWG named character
reference table.

Source of truth is https://html.spec.whatwg.org/entities.json, vendored at
tools/vendor/entities.json so builds are offline and reproducible. Refresh it
with --download, then re-run to regenerate.

The emitted Mort module stores the table as parallel scalar globals, because
Mort allows global arrays of scalars but not of structs:

    ENTITY_NAMES     one string literal holding every entity name, concatenated,
              in lexicographic order (names include their trailing ';' when
              they have one; the leading '&' is not stored)
    ENTITY_OFF/ENTITY_LEN   where each name sits in ENTITY_NAMES
    ENTITY_CP1/ENTITY_CP2   the code points it expands to (ENTITY_CP2 == 0 when there is only one)
    ENTITY_FIRST_LO/ENTITY_FIRST_HI/ENTITY_FIRST_MAXLEN
              per first byte: the index range of names starting with that
              byte, and the longest such name

Lookup is longest-match: for L descending from the first byte's longest name
down to 1, binary search that first-byte range for an exact L-byte match. The
first hit is by construction the longest one.
"""

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENDORED = os.path.join(HERE, "vendor", "entities.json")
OUTPUT = os.path.join(ROOT, "engine", "src", "html", "entities.mx")
SOURCE_URL = "https://html.spec.whatwg.org/entities.json"


def download():
    os.makedirs(os.path.dirname(VENDORED), exist_ok=True)
    with urllib.request.urlopen(SOURCE_URL) as response:
        payload = response.read()
    with open(VENDORED, "wb") as handle:
        handle.write(payload)
    print(f"downloaded {len(payload)} bytes -> {VENDORED}")


def load_entities():
    with open(VENDORED, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    entries = []
    for key, value in raw.items():
        if not key.startswith("&"):
            raise SystemExit(f"unexpected entity key {key!r}")
        name = key[1:]
        if not name or not all(c.isalnum() or c == ";" for c in name):
            raise SystemExit(f"entity name {name!r} needs escaping; generator assumes ASCII alphanumerics and ';'")
        if not name.isascii():
            raise SystemExit(f"non-ASCII entity name {name!r}")
        points = value["codepoints"]
        if len(points) not in (1, 2):
            raise SystemExit(f"{name!r} expands to {len(points)} code points")
        if 0 in points:
            raise SystemExit(f"{name!r} contains U+0000, which the generator uses as a sentinel")
        entries.append((name, points))
    entries.sort(key=lambda item: item[0].encode("ascii"))
    return entries


def emit(entries):
    blob = "".join(name for name, _ in entries)
    offsets = []
    cursor = 0
    for name, _ in entries:
        offsets.append(cursor)
        cursor += len(name)

    first_lo = [0] * 128
    first_hi = [0] * 128
    first_maxlen = [0] * 128
    for index, (name, _) in enumerate(entries):
        code = ord(name[0])
        if first_hi[code] == 0 and first_lo[code] == 0:
            first_lo[code] = index
        first_hi[code] = index + 1
        first_maxlen[code] = max(first_maxlen[code], len(name))
    # A first byte with no entities keeps lo == hi == 0, which reads as an
    # empty range; fix up the ones that never got a lo.
    for code in range(128):
        if first_hi[code] == 0:
            first_lo[code] = 0

    def rows(values, per_line, formatter=str):
        lines = []
        for start in range(0, len(values), per_line):
            chunk = values[start:start + per_line]
            lines.append("    " + ", ".join(formatter(v) for v in chunk) + ",")
        text = "\n".join(lines)
        return text[:-1] if text.endswith(",") else text

    def hex4(value):
        return f"0x{value:04X}"

    count = len(entries)
    longest = max(len(name) for name, _ in entries)
    two_cp = sum(1 for _, points in entries if len(points) == 2)

    return f"""// Named character references — WHATWG HTML §13.2.5.73 and the named character
// reference table (https://html.spec.whatwg.org/entities.json).
//
// GENERATED FILE — do not edit by hand.
// Regenerate with: python tools/gen_entities.py
// Source: tools/vendor/entities.json ({count} names, longest {longest} bytes,
// {two_cp} of which expand to two code points).
//
// The table is parallel scalar globals rather than an array of structs,
// because Mort permits global arrays of scalars only. ENTITY_NAMES holds every name
// concatenated in lexicographic order, without the leading '&' and with the
// trailing ';' where the name has one.
module engine.html.entities;

// A table match. len == 0 means no entity name matched. `semicolon` reports
// whether the matched name is terminated by ';' (the legacy names are not).
// cp2 is 0 when the entity maps to a single code point; no entity expands to
// U+0000, so 0 is a safe sentinel.
struct HtmlEntityMatch {{
    len: u64,
    cp1: u32,
    cp2: u32,
    semicolon: bool,
}}

const ENTITY_COUNT: u64 = {count};
const ENTITY_LONGEST: u64 = {longest};

let ENTITY_NAMES: *u8 = "{blob}";

let ENTITY_OFF: [u32; {count}] = [
{rows(offsets, 16)}
];

let ENTITY_LEN: [u8; {count}] = [
{rows([len(name) for name, _ in entries], 32)}
];

let ENTITY_CP1: [u32; {count}] = [
{rows([points[0] for _, points in entries], 12, hex4)}
];

let ENTITY_CP2: [u32; {count}] = [
{rows([points[1] if len(points) == 2 else 0 for _, points in entries], 12, hex4)}
];

// Index range of names beginning with each ASCII byte, and the longest such
// name — lookup only ever searches one first-byte bucket.
let ENTITY_FIRST_LO: [u32; 128] = [
{rows(first_lo, 16)}
];

let ENTITY_FIRST_HI: [u32; 128] = [
{rows(first_hi, 16)}
];

let ENTITY_FIRST_MAXLEN: [u8; 128] = [
{rows(first_maxlen, 32)}
];

// Compare table entry `index` against the `length` input bytes at `pos`:
// negative when the entry sorts first, positive when it sorts after, zero on
// an exact match.
fn compare(index: u64, input: *const u8, pos: u64, length: u64) -> i64 {{
    let off: u64 = ENTITY_OFF[index] as u64;
    let name_len: u64 = ENTITY_LEN[index] as u64;
    let shared: u64 = name_len;
    if length < shared {{
        shared = length;
    }}
    for step: u64 in 0..shared {{
        let a: u8 = ENTITY_NAMES[off + step];
        let b: u8 = input[pos + step];
        if a < b {{
            return -1;
        }}
        if a > b {{
            return 1;
        }}
    }}
    if name_len < length {{
        return -1;
    }}
    if name_len > length {{
        return 1;
    }}
    return 0;
}}

// Exact-match binary search for the `length` input bytes at `pos`, within
// [lo, hi). Returns ENTITY_COUNT when absent.
fn find_exact(
    input: *const u8,
    pos: u64,
    length: u64,
    lo: u64,
    hi: u64
) -> u64 {{
    let low: u64 = lo;
    let high: u64 = hi;
    while low < high {{
        let mid: u64 = low + (high - low) / 2;
        let order: i64 = compare(mid, input, pos, length);
        if order == 0 {{
            return mid;
        }}
        if order < 0 {{
            low = mid + 1;
        }} else {{
            high = mid;
        }}
    }}
    return ENTITY_COUNT;
}}

// Longest match of any table name against the input at `pos`, which sits just
// after the '&'. Entity names are matched case-sensitively, per spec.
pub fn lookup(input: *const u8, length: u64, pos: u64) -> HtmlEntityMatch {{
    let miss: HtmlEntityMatch =
        HtmlEntityMatch {{ len: 0, cp1: 0 as u32, cp2: 0 as u32, semicolon: false }};
    if pos >= length {{
        return miss;
    }}
    let first: u8 = input[pos];
    if first >= 128 as u8 {{
        return miss;
    }}
    let lo: u64 = ENTITY_FIRST_LO[first as u64] as u64;
    let hi: u64 = ENTITY_FIRST_HI[first as u64] as u64;
    if lo >= hi {{
        return miss;
    }}
    let available: u64 = length - pos;
    let longest: u64 = ENTITY_FIRST_MAXLEN[first as u64] as u64;
    if available < longest {{
        longest = available;
    }}
    let size: u64 = longest;
    while size > 0 {{
        let found: u64 = find_exact(input, pos, size, lo, hi);
        if found < ENTITY_COUNT {{
            return HtmlEntityMatch {{
                len: size,
                cp1: ENTITY_CP1[found],
                cp2: ENTITY_CP2[found],
                semicolon: ENTITY_NAMES[(ENTITY_OFF[found] as u64) + size - 1] == ';',
            }};
        }}
        size = size - 1;
    }}
    return miss;
}}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true",
                        help="refresh tools/vendor/entities.json from the spec")
    parser.add_argument("--check", action="store_true",
                        help="fail if the generated file is out of date")
    args = parser.parse_args()

    if args.download:
        download()
    if not os.path.isfile(VENDORED):
        raise SystemExit(f"missing {VENDORED}; run with --download")

    entries = load_entities()
    text = emit(entries)

    if args.check:
        with open(OUTPUT, "r", encoding="utf-8", newline="") as handle:
            current = handle.read()
        if current.replace("\r\n", "\n") != text:
            print("entities.mx is out of date; run python tools/gen_entities.py",
                  file=sys.stderr)
            return 1
        print(f"entities.mx is up to date ({len(entries)} names)")
        return 0

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {OUTPUT} ({len(entries)} names)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
