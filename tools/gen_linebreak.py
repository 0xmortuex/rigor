#!/usr/bin/env python3
"""Generate engine/src/text/linebreak_data.mx from the Unicode Character Database.

Inputs, vendored under tools/vendor/ucd (pinned in PINNED):

    LineBreak.txt               each code point's Line_Break property
    EastAsianWidth.txt          needed by LB19a and LB30, which only apply to
                                characters that are not East Asian wide
    DerivedGeneralCategory.txt  needed by LB1, which resolves SA to CM rather
                                than AL for the combining marks

LB1's resolution of the "unknown" classes happens here rather than at run time,
so the generated table holds only classes the pair rules actually name.

    python tools/gen_linebreak.py
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UCD = os.path.join(HERE, "vendor", "ucd")
OUT = os.path.join(ROOT, "engine", "src", "text", "linebreak_data.mx")

# The classes the rules name, after LB1. The numbering is this file's own; the
# generated module exposes it through accessors.
CLASSES = [
    "XX",   # 0 — the resolved default, never appears after LB1
    "BK", "CR", "LF", "NL", "SP", "ZW", "ZWJ", "CM", "WJ", "GL",
    "OP", "CL", "CP", "QU", "NS", "EX", "SY", "IS", "PR", "PO",
    "NU", "AL", "HL", "ID", "IN", "HY", "BA", "BB", "B2", "CB",
    "H2", "H3", "JL", "JV", "JT", "RI", "EB", "EM",
    "AK", "AP", "AS", "VI", "VF", "HH",
]
CLASS_ID = {name: index for index, name in enumerate(CLASSES)}


def read_ranges(path):
    """Yield (start, end, value) from a UCD-style semicolon file."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(";")]
            span = parts[0]
            if ".." in span:
                low, high = span.split("..")
                yield int(low, 16), int(high, 16), parts[1]
            else:
                point = int(span, 16)
                yield point, point, parts[1]


def build_map(path):
    table = {}
    for low, high, value in read_ranges(path):
        for cp in range(low, high + 1):
            table[cp] = value
    return table


def merge(pairs):
    """Collapse a sorted [(cp, value)] list into (start, end, value) runs."""
    runs = []
    for cp, value in pairs:
        if runs and runs[-1][2] == value and runs[-1][1] + 1 == cp:
            runs[-1] = (runs[-1][0], cp, value)
        else:
            runs.append((cp, cp, value))
    return runs


def rows(values, per_line=16, indent="    "):
    out = []
    for start in range(0, len(values), per_line):
        chunk = values[start:start + per_line]
        out.append(indent + ", ".join(str(v) for v in chunk) + ",")
    return "\n".join(out)


def table(name, kind, values):
    return (f"let {name}: [{kind}; {len(values)}] = [\n"
            f"{rows(values)}\n"
            f"];\n\n")


def main():
    line_break = build_map(os.path.join(UCD, "LineBreak.txt"))
    east_asian = build_map(os.path.join(UCD, "EastAsianWidth.txt"))
    category = build_map(os.path.join(UCD, "DerivedGeneralCategory.txt"))

    # LB1: resolve the classes that cannot appear in the rules.
    resolved = {}
    for cp, cls in line_break.items():
        if cls in ("AI", "SG", "XX"):
            cls = "AL"
        elif cls == "SA":
            # Southeast Asian scripts need dictionary breaking, which UAX #14
            # leaves to a tailoring; the marks become CM and the rest AL.
            cls = "CM" if category.get(cp) in ("Mn", "Mc") else "AL"
        elif cls == "CJ":
            # Conditional Japanese starters break like a non-starter in the
            # default (strict) tailoring.
            cls = "NS"
        resolved[cp] = cls

    unknown = sorted(set(resolved.values()) - set(CLASS_ID))
    if unknown:
        raise SystemExit(f"unhandled line break classes: {unknown}")

    runs = merge(sorted(resolved.items()))
    starts = [start for start, _, _ in runs]
    ends = [end for _, end, _ in runs]
    ids = [CLASS_ID[value] for _, _, value in runs]

    # East Asian width only matters for the three classes whose rules mention
    # it, so the table covers those code points and nothing else.
    wide = []
    for cp, cls in resolved.items():
        if cls in ("QU", "OP", "CP") and east_asian.get(cp) in ("F", "W", "H"):
            wide.append((cp, "W"))
    wide_runs = merge(sorted(wide))
    wide_starts = [start for start, _, _ in wide_runs]
    wide_ends = [end for _, end, _ in wide_runs]

    parts = [f'''// Line breaking properties — Unicode Annex #14, from the Unicode Character
// Database.
//
// GENERATED FILE — do not edit by hand.
// Regenerate with: python tools/gen_linebreak.py
// Sources: tools/vendor/ucd/LineBreak.txt (Line_Break)
//          tools/vendor/ucd/EastAsianWidth.txt (LB19a, LB30)
//          tools/vendor/ucd/DerivedGeneralCategory.txt (LB1's SA resolution)
//
// LB1 is applied here rather than at run time: AI, SG and XX become AL, CJ
// becomes NS, and SA becomes CM for the combining marks and AL otherwise. So
// every class in this table is one the pair rules actually name.
//
// The tables are parallel scalar globals rather than arrays of structs,
// because Mort permits global arrays of scalars only. Ranges are sorted and
// disjoint, so lookup is a binary search.
module engine.text.linebreak_data;

// --- Line_Break classes ------------------------------------------------------
''']

    for index, name in enumerate(CLASSES):
        ident = name.lower()
        parts.append(f"pub fn lb_{ident}() -> u8 {{ return {index} as u8; }}\n")

    parts.append(f"""
pub fn class_name(id: u8) -> *u8 {{
""")
    for index, name in enumerate(CLASSES):
        parts.append(f'    if id == {index} as u8 {{ return "{name}"; }}\n')
    parts.append('    return "AL";\n}\n\n')

    parts.append(f"const RANGE_COUNT: u64 = {len(runs)};\n\n")
    parts.append(table("RANGE_START", "u32", starts))
    parts.append(table("RANGE_END", "u32", ends))
    parts.append(table("RANGE_CLASS", "u8", ids))

    parts.append(f"""// The Line_Break class of `cp`, already resolved per LB1. A code point with no
// assignment at all is AL, which is what LB1 does with Unicode's own XX.
pub fn class_of(cp: u32) -> u8 {{
    let low: u64 = 0;
    let high: u64 = RANGE_COUNT;
    while low < high {{
        let mid: u64 = low + (high - low) / 2;
        if cp < RANGE_START[mid] {{
            high = mid;
        }} else if cp > RANGE_END[mid] {{
            low = mid + 1;
        }} else {{
            return RANGE_CLASS[mid];
        }}
    }}
    return {CLASS_ID['AL']} as u8;
}}

// --- East Asian width (LB19a, LB30) ------------------------------------------

const WIDE_COUNT: u64 = {len(wide_runs)};

""")
    parts.append(table("WIDE_START", "u32", wide_starts))
    parts.append(table("WIDE_END", "u32", wide_ends))

    parts.append("""// True when `cp` is East Asian Fullwidth, Wide or Halfwidth. Only the QU, OP
// and CP code points are recorded, because they are the only ones whose rules
// ask — LB19a's quotation marks and LB30's brackets.
pub fn is_east_asian(cp: u32) -> bool {
    let low: u64 = 0;
    let high: u64 = WIDE_COUNT;
    while low < high {
        let mid: u64 = low + (high - low) / 2;
        if cp < WIDE_START[mid] {
            high = mid;
        } else if cp > WIDE_END[mid] {
            low = mid + 1;
        } else {
            return true;
        }
    }
    return false;
}
""")

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(parts))
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes, {len(runs)} class ranges, "
          f"{len(wide_runs)} east-asian ranges)")


if __name__ == "__main__":
    main()
