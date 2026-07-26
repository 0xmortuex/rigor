# Rigor architecture

## The pipeline

Rigor is the classic engine pipeline, each stage an independent module of the
`engine` package:

```
 bytes ──► preprocess ──► tokenizer ──► tree builder ──► DOM
                (§13.2.3.5)   (§13.2.5)      (§13.2.6)
 CSS  ──► css tokenizer ──► parser ──► cascade ──► computed style
              (§4)          (§5)      (css-cascade)
 DOM + style ──► layout tree ──► paint ──► framebuffer ──► window
```

Every stage above exists today. See ROADMAP.md for what each one does not yet
cover.

## The platform boundary is one file

The engine renders into a BGRA byte buffer and knows nothing about any
operating system: no windowing, no file I/O, no clock. `viewer/src/win32.mx`
is the only file in the project that names a platform API, and all it does is
open a window and blit that buffer. Porting rigor — to X11, to Wayland, to
MortOS — replaces that file and nothing else. The BMP writer exists partly to
prove the point: it consumes the same canvas with no platform involved at all.

## The user-agent stylesheet is CSS

`engine/src/style/ua.mx` holds the default styles as **CSS text**, parsed by
the same parser author sheets go through. Nothing in the parser or the layout
engine knows that `<div>` is a block or that `<b>` is bold — that is a rule in
that sheet, and it wins or loses against author rules through the ordinary
cascade. Hard-coding those defaults would mean a second, invisible styling
path that authors could not override correctly.

The two preprocessing stages stay separate rather than sharing code, because
the specs genuinely differ: HTML normalizes newlines but passes U+0000 through
for the tokenizer to report as a parse error, while CSS folds NUL to U+FFFD
before the tokenizer ever sees it, and also folds form feeds.

## Arenas, not object graphs

Every data structure that crosses a stage boundary is a **flat arena**:
plain-data records in a `Vec`, all string bytes in one shared byte pool
addressed by `(offset, length)`, children linked by index. The pattern comes
from Mort's own `std.json` and it is load-bearing twice over:

1. **It fits Mort's ownership model.** Nothing nested owns a resource, so
   arenas move as one value, destroy in one place, and never fight the
   move-checker.
2. **It is how fast engines actually lay out memory.** Index-linked nodes in
   contiguous storage beat pointer-chasing object graphs on locality, and
   growing an arena never invalidates a reference.

The tokenizer's output (`HtmlTokenSink`) is the first instance: tokens,
attributes, parse errors, and one byte pool. The DOM (`DomDocument`) is the
second: nodes, attributes, and a byte pool, with parents, children and
siblings as node indices. Index 0 is always the Document, which is never
anyone's child or sibling — so 0 doubles as the "no node" sentinel and no
separate null value is needed. `CssTokenSink` and `CssStylesheet` are the
third and fourth.

The one place a stage does *not* copy is CSS declaration values: a declaration
holds a token range into the sink that produced it, rather than a copy. Values
are parsed lazily and per property, and most declarations lose the cascade, so
copying every value token up front would be work thrown away. Names are copied,
which keeps a stylesheet self-contained enough to outlive its sink and to be
cascaded against sheets from other origins.

String pieces accumulate **append-only at the pool's end**, so a maximal text
run stays one contiguous span even when character references are decoded into
the middle of it. Speculative bytes that may be thrown away (RCDATA/RAWTEXT
end-tag candidates) go to a scratch buffer instead, and only committed bytes
reach the pool.

## Spec discipline

- Every state function cites its spec section (`// §13.2.5.42`).
- Error recovery is the spec's, not best-effort: malformed input takes exactly
  the recovery transition the spec defines.
- Parse errors are first-class values carrying the spec's own error names.
- Deviations are deliberate, local, and documented where they occur. Current
  list: character tokens are coalesced into runs (observably equivalent);
  input is assumed UTF-8 (charset sniffing is a future stage); script-data
  and CDATA states await tree construction.

## Interned tag names

`engine/src/html/tagnames.mx` (generated) gives every tag name the spec
mentions a small integer id. Tree construction compares tag names on nearly
every token and tests membership in long spec lists — "if the tag name is one
of: address, article, aside, …" — and doing that with byte comparisons would
be both slow and unreadable. Names the spec never mentions intern to
`tag_unknown()`, which is correct: an unknown element is just an ordinary
element to the parser.

## Mort-specific conventions

- **Type names are globally scoped in Mort** (only functions live in module
  namespaces), so every engine type carries a domain prefix: `HtmlToken`,
  `HtmlAttr`, `HtmlTokenizer`, `DomNode`, `DomDocument`, later `CssToken`, …
- **Globals share one namespace too**, which is why the generated tables use
  `ENTITY_NAMES` / `TAG_NAMES` rather than a bare `NAMES` each.
- **Globals may not be arrays of structs**, only of scalars, so generated
  tables are parallel scalar arrays.
- **Cross-module constants are exposed as functions**
  (`tokens.kind_start_tag()`, `tagnames.tag_p()`), since globals are
  file-scope for reads.
- **Imports resolve relative to the importing file** with no `..`, so a module
  in `src/dom/` reaches one in `src/html/` through the package alias
  (`import engine.html.tagnames;`).
- The engine is a Mort **path dependency** (`engine = "engine"` in the root
  manifest); the CLI and the tests import it as `engine.html.…` exactly the
  way any embedder would.
- Modules declare `module engine.html.…;` so functions are private by default
  and the public API is explicit (`pub fn`).

## Testing

`mortc test` runs spec-behavior tests that pin down tokenizer output token by
token, including the ugly paths (duplicate attributes, abrupt comments,
force-quirks doctypes, legacy no-semicolon entities in attribute values,
RCDATA end-tag flushing). Next step is wiring the html5lib-tests tokenizer
JSON suites as a conformance metric, then web-platform-tests once there is a
DOM to assert against.
