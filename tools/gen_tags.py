#!/usr/bin/env python3
"""Generate engine/src/html/tagnames.mx — interned tag names.

Tree construction compares tag names constantly, and the spec is full of
"if the tag name is one of: address, article, aside, ..." lists. Comparing
byte strings for those would be both slow and unreadable, so every tag name
the HTML spec mentions gets a small integer id here, and the tree builder
works in ids.

Ids are assigned in sorted order so they stay stable as names are added, and
lookup is the same shape as the entity table: a per-first-byte bucket plus a
binary search. Names not in the list get TAG_UNKNOWN, which is correct — an
unknown element is just an ordinary element to the parser.

    python tools/gen_tags.py
    python tools/gen_tags.py --check
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT = os.path.join(ROOT, "engine", "src", "html", "tagnames.mx")

# Every tag name named by the HTML parsing spec (§13.2.6 element lists, the
# void/special/formatting sets, and the elements with parser-visible
# behaviour), plus the foreign-content roots.
TAGS = """
a abbr address applet area article aside audio
b base basefont bdi bdo bgsound big blockquote body br button
canvas caption center cite code col colgroup
data datalist dd del details dfn dialog dir div dl dt
em embed
fieldset figcaption figure font footer form frame frameset
h1 h2 h3 h4 h5 h6 head header hgroup hr html
i iframe image img input ins
kbd keygen
label legend li link listing
main map mark marquee math menu meta
nav nobr noembed noframes noscript
object ol optgroup option output
p param picture plaintext pre progress
q
rb rp rt rtc ruby
s samp script search section select slot small source span strike strong
style sub summary sup svg
table tbody td template textarea tfoot th thead time title tr track tt
u ul
var video
wbr
xmp
""".split()


def emit(names):
    names = sorted(set(names))
    if any(not n.isascii() or not n.replace("-", "").isalnum() for n in names):
        raise SystemExit("tag names must be ASCII alphanumerics")

    blob = "".join(names)
    offsets = []
    cursor = 0
    for name in names:
        offsets.append(cursor)
        cursor += len(name)

    first_lo = [0] * 128
    first_hi = [0] * 128
    for index, name in enumerate(names):
        code = ord(name[0])
        if first_hi[code] == 0:
            first_lo[code] = index
        first_hi[code] = index + 1

    def rows(values, per_line):
        lines = []
        for start in range(0, len(values), per_line):
            chunk = values[start:start + per_line]
            lines.append("    " + ", ".join(str(v) for v in chunk) + ",")
        text = "\n".join(lines)
        return text[:-1] if text.endswith(",") else text

    count = len(names)
    longest = max(len(n) for n in names)

    # Id 0 is reserved for "not a known tag", so ids start at 1.
    accessors = "\n".join(
        f"pub fn tag_{name}() -> u32 {{ return {index + 1} as u32; }}"
        for index, name in enumerate(names))

    return f"""// Interned HTML tag names.
//
// GENERATED FILE — do not edit by hand.
// Regenerate with: python tools/gen_tags.py
//
// Tree construction (§13.2.6) compares tag names on nearly every token and
// tests membership in long spec lists, so names are interned to small integer
// ids here. Id 0 is TAG_UNKNOWN — an element the spec never names by hand,
// which the parser treats as an ordinary element.
//
// Lookup mirrors the entity table: names are stored concatenated in sorted
// order, with a per-first-byte bucket and a binary search inside it.
module engine.html.tagnames;

const TAG_COUNT: u64 = {count};
pub fn tag_unknown() -> u32 {{ return 0 as u32; }}
pub fn longest_tag_name() -> u64 {{ return {longest}; }}

let TAG_NAMES: *u8 = "{blob}";

let TAG_OFF: [u32; {count}] = [
{rows(offsets, 16)}
];

let TAG_LEN: [u8; {count}] = [
{rows([len(n) for n in names], 32)}
];

let TAG_FIRST_LO: [u32; 128] = [
{rows(first_lo, 16)}
];

let TAG_FIRST_HI: [u32; 128] = [
{rows(first_hi, 16)}
];

{accessors}

fn compare(index: u64, probe: []const u8) -> i64 {{
    let off: u64 = TAG_OFF[index] as u64;
    let name_len: u64 = TAG_LEN[index] as u64;
    let shared: u64 = name_len;
    if len(probe) < shared {{
        shared = len(probe);
    }}
    for step: u64 in 0..shared {{
        let a: u8 = TAG_NAMES[off + step];
        let b: u8 = probe[step];
        if a < b {{
            return -1;
        }}
        if a > b {{
            return 1;
        }}
    }}
    if name_len < len(probe) {{
        return -1;
    }}
    if name_len > len(probe) {{
        return 1;
    }}
    return 0;
}}

// Intern an already-lowercased tag name. Returns tag_unknown() when the name
// is not one the spec names.
pub fn lookup(probe: []const u8) -> u32 {{
    if len(probe) == 0 || len(probe) > {longest} {{
        return 0 as u32;
    }}
    let first: u8 = probe[0];
    if first >= 128 as u8 {{
        return 0 as u32;
    }}
    let low: u64 = TAG_FIRST_LO[first as u64] as u64;
    let high: u64 = TAG_FIRST_HI[first as u64] as u64;
    while low < high {{
        let mid: u64 = low + (high - low) / 2;
        let order: i64 = compare(mid, probe);
        if order == 0 {{
            return (mid + 1) as u32;
        }}
        if order < 0 {{
            low = mid + 1;
        }} else {{
            high = mid;
        }}
    }}
    return 0 as u32;
}}

// The interned name for an id, as a byte view. An unknown id yields an empty
// view; callers hold the original bytes for those.
pub fn name_of(id: u32) -> []const u8 {{
    if id == 0 as u32 || (id as u64) > TAG_COUNT {{
        return slice(TAG_NAMES as *const u8, 0);
    }}
    let index: u64 = (id as u64) - 1;
    let base: *const u8 = TAG_NAMES as *const u8;
    return slice((&base[TAG_OFF[index] as u64]) as *const u8,
        TAG_LEN[index] as u64);
}}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail if the generated file is out of date")
    args = parser.parse_args()

    text = emit(TAGS)
    if args.check:
        with open(OUTPUT, "r", encoding="utf-8", newline="") as handle:
            current = handle.read()
        if current.replace("\r\n", "\n") != text:
            print("tagnames.mx is out of date; run python tools/gen_tags.py",
                  file=sys.stderr)
            return 1
        print(f"tagnames.mx is up to date ({len(set(TAGS))} tags)")
        return 0

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {OUTPUT} ({len(set(TAGS))} tags)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
