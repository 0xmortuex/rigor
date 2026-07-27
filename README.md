# Rigor

**A browser engine written from scratch in [Mort](https://github.com/0xmortuex/Mort).**

Rigor is a standalone, embeddable web engine built the way the big ones are —
spec-driven, tested from commit one — in a programming language that is itself
built from scratch. The name is from *rigor mortis*, and from the discipline
this project runs on: every algorithm is implemented from the WHATWG/CSSWG
specification it cites, error recovery included, and progress is measured in
passing conformance tests, not vibes.

> **Status: pre-alpha, and it renders.** HTML and CSS go in, pixels come out
> in a real window — parse, DOM, cascade, layout, paint, all from scratch with
> no libraries underneath. What it does *not* do yet is at least as
> interesting as what it does; see [docs/ROADMAP.md](docs/ROADMAP.md) for the
> honest ledger.

```
Get-Content examples/demo.html | rigor-view     # a window
Get-Content examples/demo.html | rigor          # tokens, tree, styles, layout
$env:RIGOR_URL = "https://example.com"; rigor   # fetch a page and render it
```

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
tree-construction suites: **1434/1434 (100%)**, all 42 suites.

Eight cases are skipped and reported, never silently counted as passes: they
are the suites' `#script-on` cases, and rigor has no scripting engine, so the
behaviour they test does not exist here. Fragment cases (`#document-fragment`)
are run, with the fragment parsing algorithm and the case's context element.

### Reftests

`python tools/run_wpt.py` against a vendored subset of the
[web-platform-tests](https://github.com/web-platform-tests/wpt) reftests — a
test page and the page it names with `<link rel=match>`, which must render
identically: **16/43 (37%)**.

| suite | passing |
| --- | ---: |
| css/CSS2/floats | 7/16 |
| css/CSS2/normal-flow | 5/19 |
| css/CSS2/text | 4/8 |

The failures are the features rigor does not have — nested block formatting
contexts, `overflow`, table sizing, block-in-inline splitting. The runner also
counts what was not vendored, by reason, so the denominator is not quietly
flattering: 58 tests need JavaScript, 52 have a reference outside their own
directory, and 11 need the Ahem font.

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
| **total** | **7032** | **100%** |
| parse-error codes | 1799 | 100% |

Nothing is skipped: every state the suites exercise is implemented.

## What works today

- **The input byte stream** (§13.2.3): the encoding sniffing algorithm, with
  the `<meta>` prescan, and every decoder in the WHATWG Encoding Standard —
  UTF-8, UTF-16, all 28 legacy single-byte encodings, GBK, gb18030, Big5,
  EUC-JP, Shift_JIS, EUC-KR, ISO-2022-JP and x-user-defined. Then input
  preprocessing (§13.2.3.5): newline normalization and the surrogate /
  noncharacter / control input-stream parse errors.
- **HTML tokenizer** (§13.2.5), every state: data / RCDATA / RAWTEXT /
  PLAINTEXT, the script-data family including double escaping, tags and
  attributes (duplicate dropping, ASCII lowercasing), comments including the
  `<!` corner cases, the complete DOCTYPE state family, bogus comment, CDATA
  sections, and character references — numeric fully (C1 remapping table
  included) and all 2231 named references, generated from the spec's
  `entities.json`.
- **Parse errors** carry the spec's own identifiers
  (`unexpected-null-character`, `abrupt-doctype-public-identifier`, …) plus a
  byte offset.
- **Tree construction** (§13.2.6): the document-structure insertion modes,
  "in body", raw-text/RCDATA handling, the full table mode family with foster
  parenting, the select modes, the frameset modes, the scope algorithms
  (including the foreign integration points that terminate them), implied end
  tags, active formatting elements, and the adoption agency algorithm.
- **Foreign content** (§13.2.6.5): SVG and MathML subtrees with their own
  namespaces, the tag and attribute case fix-up tables, XML-namespaced
  attributes such as `xlink:href`, HTML and MathML-text integration points,
  the breakout rules, self-closing foreign tags, and CDATA sections.
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
  document order, inheritance, `style=` attributes at their own place in the
  sort order, the CSS-wide keywords (`inherit`, `initial`, `unset`, `revert`),
  custom properties with `var()` and fallback, and a real user-agent stylesheet
  written as CSS and parsed by the same parser — which is what makes `<div>` a
  block and `<b>` bold.
- **`@media` evaluation** (mediaqueries-4): media types, `and`/`or`/`not` with
  nesting, the discrete features, and the range features in all three
  spellings, including `400px <= width <= 900px`.
- **Computed values**: lengths resolved to pixels (em, rem, pt, cm, …),
  percentages kept for layout, colors from hex/rgb()/named, and the margin,
  padding and border shorthands.
- **Layout** (CSS 2.1 §9–§10): the box tree with anonymous block boxes, the
  block width constraint including `auto` margins centring a box, auto and
  fixed heights, margin collapsing in all three forms (siblings, parent/child,
  and through an empty box), floats with `clear` and line boxes that shorten
  around them, and inline formatting with line boxes, white-space collapsing,
  horizontal borders and padding on inline boxes, and `text-align`.
- **Line breaking** per UAX #14 rather than at spaces, so a run of Chinese
  wraps and `3.5`, `(parenthesised)` and `100km` do not.
- **Real text**: TrueType and OpenType parsing — `cmap` for
  character-to-glyph mapping, `hmtx` for advances, `glyf` for outlines
  including composite glyphs, and `CFF ` Type 2 charstrings for the OpenType
  flavour — with an anti-aliased scanline rasterizer using the nonzero winding
  rule, and kerning from `kern` or GPOS. Bold, italic and monospace resolve to
  the system's actual faces, and non-ASCII renders.
- **Images**: a PNG decoder written from scratch, DEFLATE included — every
  colour type at every bit depth, all five filters, tRNS transparency and
  Adam7 interlacing — with `<img>` laid out as a replaced element.
- **Networking**: a URL parser and http/https fetching with redirects and
  chunked responses, so `RIGOR_URL` loads a page from the web along with its
  linked stylesheets and images.
- **Paint**: a software rasterizer with source-over alpha blending, drawing
  backgrounds, borders and text into a BGRA canvas, plus a BMP writer so a
  render can be diffed without a window.
- **A window**: `rigor-view` opens a Win32 window and blits the canvas, with
  arrow-key and mouse-wheel scrolling, re-rendering on resize (the whole
  cascade, since the viewport width decides which `@media` queries match), and
  hit testing — the cursor changes over a link and fragment links navigate.
  Win32 is confined to one file — `viewer/src/win32.mx` — so a port replaces
  that and nothing else.
- **`rigor` CLI**: pipe HTML in, get the token stream, the parsed tree, the
  parsed stylesheet, the computed style of every element, the laid-out box
  tree with its geometry, and `rigor.bmp`.

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

cd viewer && mortc build               # the windowed viewer -> rigor-view

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
  src/text/        TrueType parsing, outlines, the glyph rasterizer
  src/paint/       the canvas, box painting, a BMP writer, a fallback font
src/main.mx        the rigor developer CLI
viewer/            the windowed viewer; viewer/src/win32.mx is all the
                   platform-specific code in the project
tests/             spec-behavior tests (mortc test)
conformance/       batch driver binary for the html5lib suites
tools/             generators, conformance drivers, vendored suites
examples/          demo.html
docs/              ARCHITECTURE.md, ROADMAP.md
```

`engine/src/html/entities.mx` and `tagnames.mx` are generated — edit the
generators in `tools/`, not the tables.

Design notes live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT.
