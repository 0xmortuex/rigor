# Rigor

**A browser engine written from scratch in [Mort](https://github.com/0xmortuex/Mort).**

Rigor is a standalone, embeddable web engine built the way the big ones are —
spec-driven, tested from commit one — in a programming language that is itself
built from scratch. The name is from *rigor mortis*, and from the discipline
this project runs on: every algorithm is implemented from the WHATWG/CSSWG
specification it cites, error recovery included, and progress is measured in
passing conformance tests, not vibes.

> **Status: pre-alpha.** HTML parses end to end (tokenizer at 100% and tree
> construction at 81% of the html5lib conformance suites) and CSS parses into
> rules, selectors and declarations. The cascade, layout and paint are
> roadmap. See [docs/ROADMAP.md](docs/ROADMAP.md) for the honest ledger.

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
tree-construction suites: **1058/1304 (81%)**, 26 skipped.

The remaining gap is concentrated in features that are not implemented yet,
and the driver prints the per-suite numbers so it stays visible:

| suite | passing | what it covers |
| --- | ---: | --- |
| blocks, comments01, doctype01, entities01/02 | 100% | core parsing |
| tables01, tests6–tests8 | 94–100% | tables and foster parenting |
| adoption01/02 | 16/19 | misnested formatting |
| tests1–tests5, tests14–tests25 | 73–100% | general |
| tests9–tests12 | 0–7% | **foreign content (SVG/MathML)** |
| tests21 | 4% | **CDATA sections** |

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
  "in body", raw-text/RCDATA handling, the full table mode family with foster
  parenting, the frameset modes, the scope algorithms, implied end tags,
  active formatting elements, and the adoption agency algorithm.
- **DOM**: a flat-arena tree with elements, text, comments, doctypes and
  attributes, plus a serializer that emits the html5lib tree format.
- **CSS tokenizer** (Syntax Level 3 §4): every token type, the escape and
  numeric algorithms, url vs function disambiguation, and bad-string/bad-url
  recovery.
- **CSS parser** (§5): stylesheets, style rules, at-rules (with `@media` and
  friends keeping their nested rules), declarations and `!important`.
- **Selectors** (Selectors Level 4): type, universal, class, id, attribute
  (all six matchers plus the `i` flag), pseudo-classes and pseudo-elements,
  the four combinators, selector lists, and specificity.
- **`rigor` CLI**: pipe HTML in, get the token stream, the parsed tree, and
  the parsed stylesheet out.

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

CSS in a `<style>` element is parsed too:

```
-- stylesheet --
body
  margin: 0
  font-family: "Inter", sans-serif
#main > p.intro, h1
  color: #333
  font-size: 1.5em !important
a[href^="https"]:hover
  color: rgb(0, 100, 200)
@media screen
  .wide
    width: 60%
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
  src/css/         preprocessing, tokenizer, parser, selectors, stylesheet
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
