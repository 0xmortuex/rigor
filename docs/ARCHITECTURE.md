# Rigor architecture

## The pipeline

Rigor is the classic engine pipeline, each stage an independent module of the
`engine` package:

```
 bytes ──► preprocess ──► tokenizer ──► tree builder ──► DOM
                (§13.2.3.5)   (§13.2.5)      (§13.2.6)
 CSS  ──► css tokenizer ──► parser ──► cascade ──► computed style
                                   (css-syntax-3)   (css-cascade)
 DOM + style ──► layout tree ──► paint ──► framebuffer ──► window
```

Only the stages up to the tokenizer exist today; the pipeline shape is the
contract the rest is built into. See ROADMAP.md for sequencing.

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
attributes, parse errors, and one byte pool. The DOM will be the second.

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

## Mort-specific conventions

- **Type names are globally scoped in Mort** (only functions live in module
  namespaces), so every engine type carries a domain prefix: `HtmlToken`,
  `HtmlAttr`, `HtmlTokenizer`, later `DomNode`, `CssToken`, …
- **Globals are file-scope.** Cross-module constants are exposed as functions
  (`tokens.kind_start_tag()`, `tokens.err_eof_in_tag()`).
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
