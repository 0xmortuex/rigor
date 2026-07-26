# Rigor

**A browser engine written from scratch in [Mort](https://github.com/0xmortuex/Mort).**

Rigor is a standalone, embeddable web engine built the way the big ones are —
spec-driven, tested from commit one — in a programming language that is itself
built from scratch. The name is from *rigor mortis*, and from the discipline
this project runs on: every algorithm is implemented from the WHATWG/CSSWG
specification it cites, error recovery included, and progress is measured in
passing conformance tests, not vibes.

> **Status: pre-alpha.** HTML parses end to end — tokenizer at 100% and tree
> construction at 65% of the html5lib conformance suites. CSS, layout and
> paint are roadmap. See [docs/ROADMAP.md](docs/ROADMAP.md) for the honest
> ledger.

```
> '<b>1<p>2</b>3</p>' | rigor
| <html>
|   <head>
|   <body>
|     <b>
|       "1"
|     <p>
|       <b>
|         "2"
|       "3"
```

That is the adoption agency algorithm doing what browsers do with misnested
formatting markup.

## Conformance

### Tree construction

`python tools/run_tree_conformance.py` against the html5lib-tests
tree-construction suites: **848/1304 (65%)**, 26 skipped.

Everything below is the current shape of the gap, and it is concentrated
exactly where the unimplemented modes are — the table mode family, foreign
content (SVG/MathML), select, and template contents:

| suite | passing | |
| --- | ---: | --- |
| blocks, comments01, doctype01, entities01/02 | 100% | core parsing |
| adoption01/02 | 15/19 | misnested formatting |
| tests1–tests5, tests19–tests25 | 78–100% | general |
| tables01, tests9–tests12, tests21 | 0–8% | tables, foreign content, CDATA |

### Tokenizer

Against the [html5lib-tests](https://github.com/html5lib/html5lib-tests)
tokenizer suites (vendored, pinned), via `python tools/run_conformance.py`:

| suite | cases | passing |
| --- | ---: | ---: |
| contentModelFlags | 24 | 100% |
| domjs | 25 | 100% |
| entities | 80 | 100% |
| escapeFlag | 9 | 100% |
| namedEntities | 4210 | 100% |
| numericEntities | 336 | 100% |
| pendingSpecChanges | 1 | 100% |
| test1–test4 | 1874 | 100% |
| unicodeChars (+ problematic) | 328 | 100% |
| **total** | **6887** | **100%** |
| parse-error codes | 1737 | 100% |

145 cases are **skipped, not passed**: they need the script-data or CDATA
tokenizer states, which arrive with tree construction (those states are driven
by the tree builder). The harness prints the skip count on every run.

## What works today

- **Byte stream decoding** (§13.2.3.3) and **input preprocessing** (§13.2.3.5):
  BOM removal, newline normalization, and the surrogate / noncharacter /
  control input-stream parse errors.
- **HTML tokenizer** (§13.2.5): data / RCDATA / RAWTEXT / PLAINTEXT, tags and
  attributes (duplicate dropping, ASCII lowercasing), comments including the
  `<!` corner cases, the complete DOCTYPE state family, bogus comment, and
  character references — numeric fully (C1 remapping table included) and all
  2231 named references, generated from the spec's `entities.json`.
- **Parse errors** carry the spec's own identifiers
  (`unexpected-null-character`, `abrupt-doctype-public-identifier`, …) plus a
  byte offset.
- **Tree construction** (§13.2.6): the document-structure insertion modes,
  "in body", raw-text/RCDATA handling, the frameset modes, the scope
  algorithms, implied end tags, active formatting elements, and the adoption
  agency algorithm.
- **DOM**: a flat-arena tree with elements, text, comments, doctypes and
  attributes, plus a serializer that emits the html5lib tree format.
- **`rigor` CLI**: pipe HTML in, get the token stream and the parsed tree out.

```
> '<!DOCTYPE html><p class="x">Hi &amp; bye</p>' | rigor
doctype <!DOCTYPE html>
start   <p class="x">
text    "Hi & bye"
end     </p>
eof
-- tree --
| <!DOCTYPE html>
| <html>
|   <head>
|   <body>
|     <p>
|       class="x"
|       "Hi & bye"
```

## Build

Requires the [Mort toolchain](https://github.com/0xmortuex/Mort) (`mortc`).

```
mortc build      # build the rigor CLI  -> build/rigor.exe
mortc test       # run the engine's test suite
mortc fmt        # format sources

cd conformance && mortc build             # build the conformance harness
python tools/run_conformance.py           # html5lib tokenizer suites
python tools/run_tree_conformance.py      # html5lib tree-construction suites
python tools/gen_entities.py --check      # verify generated tables are current
python tools/gen_tags.py --check
```

## Layout

```
engine/            the engine library (Mort package `engine`) — embeddable
  src/html/        preprocessing, tokenizer, entities, tag names, tree builder
  src/dom/         the DOM arena and its html5lib-format serializer
src/main.mx        the rigor developer CLI
tests/             spec-behavior tests (mortc test)
conformance/       batch driver binary for the html5lib suites
tools/             generators, conformance drivers, vendored suites
docs/              ARCHITECTURE.md, ROADMAP.md
```

`engine/src/html/entities.mx` and `tagnames.mx` are generated — edit the
generators in `tools/`, not the tables.

Design notes live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT.
