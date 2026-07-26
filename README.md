# Rigor

**A browser engine written from scratch in [Mort](https://github.com/0xmortuex/Mort).**

Rigor is a standalone, embeddable web engine built the way the big ones are —
spec-driven, tested from commit one — in a programming language that is itself
built from scratch. The name is from *rigor mortis*, and from the discipline
this project runs on: every algorithm is implemented from the WHATWG/CSSWG
specification it cites, error recovery included, and progress is measured in
passing conformance tests, not vibes.

> **Status: pre-alpha.** The front end is complete: HTML parses to a DOM
> (tokenizer at 100% and tree construction at 81% of the html5lib conformance
> suites), CSS parses to rules and selectors, and the cascade produces
> computed styles for every element. Layout and paint are next. See
> [docs/ROADMAP.md](docs/ROADMAP.md) for the honest ledger.

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
- **Selector matching** against the DOM, right to left with backtracking, plus
  the structural pseudo-classes.
- **The cascade** (CSS Cascade §6): origin and importance, specificity,
  document order, inheritance, and a real user-agent stylesheet written as
  CSS and parsed by the same parser — which is what makes `<div>` a block and
  `<b>` bold.
- **Computed values**: lengths resolved to pixels (em, rem, pt, cm, …),
  percentages kept for layout, colors from hex/rgb()/named, and the margin,
  padding and border shorthands.
- **Layout** (CSS 2.1 §9–§10): the box tree with anonymous block boxes, the
  block width constraint including `auto` margins centring a box, auto and
  fixed heights, adjacent-sibling margin collapsing, and inline formatting
  with line boxes, white-space collapsing, line breaking and `text-align`.
- **`rigor` CLI**: pipe HTML in, get the token stream, the parsed tree, the
  parsed stylesheet, the computed style of every element, and the laid-out
  box tree with its geometry.

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

…and cascaded into computed styles, user-agent stylesheet included:

```
-- computed style --
<html>  display:block font:16px/400 color:rgb(0 0 0) margin:0px 0px 0px 0px
  <head>  display:none ...
  <body>  display:block font:16px/400 color:rgb(34 34 34) margin:8px 8px 8px 8px
    <h1>  display:block font:32px/700 color:rgb(0 0 139) margin:21.44px 0px 21.44px 0px
    <div>  display:block ... background:rgb(245 245 245) border:2px width:60%
      <p>  display:block font:16px/700 color:rgb(80 80 80) margin:8px 0px 8px 0px
```

…and laid out to real geometry:

```
-- layout --
block <html> at (0,0) size 800x179.68
  block <body> at (8,8) size 784x171.68 margin 8 8 8 8
    block <h1> at (8,29.44) size 784x38.4 margin 21.44 0 21.44 0
      text "Rigor" at (8,29.44) size 72x38.4
    block <div> at (8,89.28) size 470.4x54.4 margin 0 277.6 0 0 border 2 padding 16 16
      block <p> at (26,115.28) size 470.4x19.2 margin 8 0 8 0
        text "A browser engine." at (26,115.28) size 126.08x19.2
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
  src/css/         preprocessing, tokenizer, parser, selectors, matching
  src/style/       the cascade, computed values, the UA stylesheet
  src/layout/      the box tree, normal flow, font metrics
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
