#!/usr/bin/env python3
"""Generate engine/src/html/encodings.mx from the Encoding Standard's tables.

Two inputs, both vendored under tools/vendor/encoding (pinned in PINNED):

    encodings.json   the label table (§4.2), mapping every recognised label
                     such as "latin1" or "sjis" to its encoding
    indexes.json     the index tables (§5), mapping each encoding's byte
                     values to code points

The generated module is parallel scalar globals, because Mort permits global
arrays of scalars only — the same shape tools/gen_entities.py produces.

    python tools/gen_encodings.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENDOR = os.path.join(HERE, "vendor", "encoding")
OUT = os.path.join(ROOT, "engine", "src", "html", "encodings.mx")

# Encoding ids. The order is the one the module documents and the decoder
# switches on; it is not the spec's, which has no numbering.
ENCODINGS = [
    "UTF-8",
    "IBM866", "ISO-8859-2", "ISO-8859-3", "ISO-8859-4", "ISO-8859-5",
    "ISO-8859-6", "ISO-8859-7", "ISO-8859-8", "ISO-8859-8-I", "ISO-8859-10",
    "ISO-8859-13", "ISO-8859-14", "ISO-8859-15", "ISO-8859-16", "KOI8-R",
    "KOI8-U", "macintosh", "windows-874", "windows-1250", "windows-1251",
    "windows-1252", "windows-1253", "windows-1254", "windows-1255",
    "windows-1256", "windows-1257", "windows-1258", "x-mac-cyrillic",
    "GBK", "gb18030", "Big5", "EUC-JP", "ISO-2022-JP", "Shift_JIS", "EUC-KR",
    "replacement", "UTF-16BE", "UTF-16LE", "x-user-defined",
]

# Which index table each single-byte encoding reads. ISO-8859-8-I shares
# ISO-8859-8's table; ISO-8859-1 is not a separate encoding at all (its labels
# map to windows-1252, which is the whole point of the label table).
SINGLE_BYTE_INDEX = {
    "IBM866": "ibm866",
    "ISO-8859-2": "iso-8859-2", "ISO-8859-3": "iso-8859-3",
    "ISO-8859-4": "iso-8859-4", "ISO-8859-5": "iso-8859-5",
    "ISO-8859-6": "iso-8859-6", "ISO-8859-7": "iso-8859-7",
    "ISO-8859-8": "iso-8859-8", "ISO-8859-8-I": "iso-8859-8",
    "ISO-8859-10": "iso-8859-10", "ISO-8859-13": "iso-8859-13",
    "ISO-8859-14": "iso-8859-14", "ISO-8859-15": "iso-8859-15",
    "ISO-8859-16": "iso-8859-16",
    "KOI8-R": "koi8-r", "KOI8-U": "koi8-u",
    "macintosh": "macintosh", "windows-874": "windows-874",
    "windows-1250": "windows-1250", "windows-1251": "windows-1251",
    "windows-1252": "windows-1252", "windows-1253": "windows-1253",
    "windows-1254": "windows-1254", "windows-1255": "windows-1255",
    "windows-1256": "windows-1256", "windows-1257": "windows-1257",
    "windows-1258": "windows-1258", "x-mac-cyrillic": "x-mac-cyrillic",
}

# A missing index entry. No index maps to U+0000, so zero is unambiguous.
MISSING = 0


def rows(values, per_line=16, indent="    "):
    out = []
    for start in range(0, len(values), per_line):
        chunk = values[start:start + per_line]
        out.append(indent + ", ".join(str(v) for v in chunk) + ",")
    return "\n".join(out)


def scalar_table(name, kind, values):
    return (f"let {name}: [{kind}; {len(values)}] = [\n"
            f"{rows(values)}\n"
            f"];\n")


def main():
    with open(os.path.join(VENDOR, "encodings.json"), encoding="utf-8") as handle:
        groups = json.load(handle)
    with open(os.path.join(VENDOR, "indexes.json"), encoding="utf-8") as handle:
        indexes = json.load(handle)

    by_name = {}
    for group in groups:
        for entry in group["encodings"]:
            by_name[entry["name"]] = entry["labels"]

    missing = [name for name in ENCODINGS if name not in by_name]
    if missing:
        raise SystemExit(f"encodings.json has no entry for {missing}")

    # --- Labels --------------------------------------------------------------
    # Every label, sorted, so lookup is a binary search. Labels are matched
    # ASCII case-insensitively after stripping leading and trailing whitespace,
    # so they are stored lowercased.
    labels = []
    for index, name in enumerate(ENCODINGS):
        for label in by_name[name]:
            labels.append((label.lower(), index))
    labels.sort()
    seen = set()
    for label, _ in labels:
        if label in seen:
            raise SystemExit(f"duplicate label {label!r}")
        seen.add(label)

    label_text = "".join(label for label, _ in labels)
    label_off = []
    label_len = []
    offset = 0
    for label, _ in labels:
        label_off.append(offset)
        label_len.append(len(label))
        offset += len(label)
    label_encoding = [index for _, index in labels]

    # --- Single-byte indexes -------------------------------------------------
    # One flat table of 128 entries per encoding, addressed by a base offset,
    # so the decoder is a single array read.
    single_names = [name for name in ENCODINGS if name in SINGLE_BYTE_INDEX]
    single_base = {}
    single_values = []
    for name in single_names:
        single_base[name] = len(single_values)
        table = indexes[SINGLE_BYTE_INDEX[name]]
        if len(table) != 128:
            raise SystemExit(f"{name}: expected 128 entries, got {len(table)}")
        single_values.extend(MISSING if v is None else v for v in table)
    # Encodings with no single-byte table get a base that the decoder never
    # reads; -1 would need a signed type, so the count is the sentinel.
    single_base_by_id = [
        single_base.get(name, len(single_values)) for name in ENCODINGS
    ]

    def flat(index_name):
        return [MISSING if v is None else v for v in indexes[index_name]]

    big5 = flat("big5")
    euc_kr = flat("euc-kr")
    gb18030 = flat("gb18030")
    jis0208 = flat("jis0208")
    jis0212 = flat("jis0212")
    ranges = indexes["gb18030-ranges"]
    range_pointer = [entry[0] for entry in ranges]
    range_code = [entry[1] for entry in ranges]

    parts = []
    parts.append(f'''// Character encodings — the WHATWG Encoding Standard
// (https://encoding.spec.whatwg.org/).
//
// GENERATED FILE — do not edit by hand.
// Regenerate with: python tools/gen_encodings.py
// Sources: tools/vendor/encoding/encodings.json (§4.2, {len(labels)} labels)
//          tools/vendor/encoding/indexes.json (§5, the index tables)
//
// The tables are parallel scalar globals rather than arrays of structs,
// because Mort permits global arrays of scalars only.
//
// Every index entry is a Unicode code point, or 0 for "this byte sequence
// decodes to nothing" — no index maps to U+0000, so zero is unambiguous.
module engine.html.encodings;

// --- Encoding ids ------------------------------------------------------------
''')

    for index, name in enumerate(ENCODINGS):
        ident = name.lower().replace("-", "_").replace(".", "_")
        parts.append(f"pub fn enc_{ident}() -> u32 {{ return {index} as u32; }}\n")

    parts.append(f"""
pub fn encoding_count() -> u32 {{ return {len(ENCODINGS)} as u32; }}

// The name a label resolved to, for the debug dump and for <meta> round trips.
pub fn encoding_name(id: u32) -> *u8 {{
""")
    for index, name in enumerate(ENCODINGS):
        parts.append(f'    if id == {index} as u32 {{ return "{name}"; }}\n')
    parts.append('    return "UTF-8";\n}\n')

    parts.append(f"""
// True when the encoding is one of the {len(single_names)} legacy single-byte
// encodings, whose decoder is a table lookup on the high half of the byte
// range (§9.1 "single-byte decoder").
pub fn is_single_byte(id: u32) -> bool {{
    return SINGLE_BASE[id as u64] < {len(single_values)};
}}

// --- Labels (§4.2) -----------------------------------------------------------

const LABEL_COUNT: u64 = {len(labels)};

""")
    parts.append(f'let LABEL_TEXT: *u8 = "{label_text}";\n\n')
    parts.append(scalar_table("LABEL_OFF", "u32", label_off) + "\n")
    parts.append(scalar_table("LABEL_LEN", "u8", label_len) + "\n")
    parts.append(scalar_table("LABEL_ENC", "u8", label_encoding) + "\n")

    parts.append("""
fn ascii_lower(c: u8) -> u8 {
    if c >= 'A' && c <= 'Z' {
        return c + 32 as u8;
    }
    return c;
}

fn is_ws(c: u8) -> bool {
    return c == 9 as u8 || c == 10 as u8 || c == 12 as u8
        || c == 13 as u8 || c == 32 as u8;
}

// Compare a candidate label against table entry `index`. Negative when the
// candidate sorts first.
fn compare_label(view: []const u8, index: u64) -> i64 {
    let off: u64 = LABEL_OFF[index] as u64;
    let length: u64 = LABEL_LEN[index] as u64;
    let shared: u64 = len(view);
    if length < shared {
        shared = length;
    }
    for step: u64 in 0..shared {
        let a: u8 = ascii_lower(view[step]);
        let b: u8 = LABEL_TEXT[off + step];
        if a < b { return -1; }
        if a > b { return 1; }
    }
    if len(view) < length { return -1; }
    if len(view) > length { return 1; }
    return 0;
}

// The result of looking a label up: `found` is false for a label the standard
// does not list, which §4.2 says makes the whole declaration ignored.
struct EncodingLookup {
    found: bool,
    id: u32,
}

// §4.2 "get an encoding": strip leading and trailing ASCII whitespace, then
// match the label ASCII case-insensitively.
pub fn lookup_label(label: []const u8) -> EncodingLookup {
    let start: u64 = 0;
    let end: u64 = len(label);
    while start < end && is_ws(label[start]) {
        start = start + 1;
    }
    while end > start && is_ws(label[end - 1]) {
        end = end - 1;
    }
    if end == start {
        return EncodingLookup { found: false, id: 0 as u32 };
    }
    let trimmed: []const u8 = slice((&label[start]) as *const u8, end - start);

    let low: u64 = 0;
    let high: u64 = LABEL_COUNT;
    while low < high {
        let mid: u64 = low + (high - low) / 2;
        let order: i64 = compare_label(trimmed, mid);
        if order == 0 {
            return EncodingLookup { found: true, id: LABEL_ENC[mid] as u32 };
        }
        if order < 0 {
            high = mid;
        } else {
            low = mid + 1;
        }
    }
    return EncodingLookup { found: false, id: 0 as u32 };
}

// --- Index tables (§5) -------------------------------------------------------

""")

    parts.append(scalar_table("SINGLE_BASE", "u32", single_base_by_id) + "\n")
    parts.append(scalar_table("SINGLE_INDEX", "u32", single_values) + "\n")
    parts.append("""
// §9.1: a byte below 0x80 is its own code point; above it, the table decides.
pub fn single_byte(id: u32, byte: u8) -> u32 {
    if byte < 0x80 as u8 {
        return byte as u32;
    }
    let base: u64 = SINGLE_BASE[id as u64] as u64;
    return SINGLE_INDEX[base + ((byte as u64) - 128)];
}

""")

    parts.append(scalar_table("BIG5_INDEX", "u32", big5) + "\n")
    parts.append(scalar_table("EUC_KR_INDEX", "u32", euc_kr) + "\n")
    parts.append(scalar_table("GB18030_INDEX", "u32", gb18030) + "\n")
    parts.append(scalar_table("JIS0208_INDEX", "u32", jis0208) + "\n")
    parts.append(scalar_table("JIS0212_INDEX", "u32", jis0212) + "\n")
    parts.append(scalar_table("GB18030_RANGE_POINTER", "u32", range_pointer) + "\n")
    parts.append(scalar_table("GB18030_RANGE_CODE", "u32", range_code) + "\n")

    parts.append(f"""
// Index lookups. A pointer outside the table decodes to nothing, which the
// decoders report as an error rather than a code point.
pub fn big5(pointer: u64) -> u32 {{
    if pointer >= {len(big5)} {{ return 0 as u32; }}
    return BIG5_INDEX[pointer];
}}

pub fn euc_kr(pointer: u64) -> u32 {{
    if pointer >= {len(euc_kr)} {{ return 0 as u32; }}
    return EUC_KR_INDEX[pointer];
}}

pub fn gb18030(pointer: u64) -> u32 {{
    if pointer >= {len(gb18030)} {{ return 0 as u32; }}
    return GB18030_INDEX[pointer];
}}

pub fn jis0208(pointer: u64) -> u32 {{
    if pointer >= {len(jis0208)} {{ return 0 as u32; }}
    return JIS0208_INDEX[pointer];
}}

pub fn jis0212(pointer: u64) -> u32 {{
    if pointer >= {len(jis0212)} {{ return 0 as u32; }}
    return JIS0212_INDEX[pointer];
}}

// §5.1 "index gb18030 ranges code point": the four-byte gb18030 sequences
// cover the rest of Unicode as a set of contiguous ranges.
pub fn gb18030_ranges(pointer: u32) -> u32 {{
    if pointer > (39419 as u32) && pointer < (189000 as u32) {{
        return 0 as u32;
    }}
    if pointer > (1237575 as u32) {{
        return 0 as u32;
    }}
    if pointer == (7457 as u32) {{
        return 0xE7C7 as u32;
    }}
    // The largest range whose pointer is at or below the one asked for.
    let best: u64 = 0;
    for index: u64 in 0..{len(range_pointer)} {{
        if GB18030_RANGE_POINTER[index] <= pointer {{
            best = index;
        }}
    }}
    return GB18030_RANGE_CODE[best]
        + (pointer - GB18030_RANGE_POINTER[best]);
}}
""")

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(parts))
    size = os.path.getsize(OUT)
    print(f"wrote {OUT} ({size} bytes, {len(labels)} labels, "
          f"{len(single_values)} single-byte entries, "
          f"{len(big5) + len(euc_kr) + len(gb18030) + len(jis0208) + len(jis0212)} "
          f"multi-byte entries)")


if __name__ == "__main__":
    main()
