# Roadmap

The goal is a production-grade engine, which for a from-scratch project means:
spec-driven implementations, conformance suites wired into CI, and no stage
that is throwaway. Ladybird's trajectory is the reference point — this is a
years-long road, and every milestone below is real engine code.

## Milestone 1 — static renderer

HTML + CSS in, pixels in a window out. No JavaScript.

- [x] Repo + package layout (engine as an embeddable Mort package)
- [x] Input preprocessing (§13.2.3.5: BOM, newlines)
- [x] HTML tokenizer — **every state in §13.2.5**: tags, attributes, comments,
      doctypes, RCDATA/RAWTEXT/PLAINTEXT, script data, CDATA, numeric + named
      character references, spec-named parse errors
- [x] Full named-entity table generated from entities.json (2231 names,
      `tools/gen_entities.py` → `engine/src/html/entities.mx`)
- [x] html5lib-tests tokenizer conformance harness — **7032/7032 tokens and
      1799/1799 parse-error codes, nothing skipped**
- [x] Tree construction → DOM (§13.2.6): document-structure modes, "in body",
      text modes, frameset modes, scopes, implied end tags, active formatting
      elements, adoption agency
- [x] Table insertion modes (in table / in caption / in column group / in
      table body / in row / in cell) with foster parenting
- [x] Foreign content: SVG and MathML namespaces, name adjustment tables,
      integration points, breakout rules, and CDATA sections
- [x] The script-data tokenizer states (§13.2.5.15–31), including double
      escaping
- [x] The `select` insertion modes (§13.2.6.4.16–17) and select scope
- [x] `template` contents: the separate contents fragment, the "in template"
      mode and the stack of template insertion modes, and the template arms of
      the insertion-location and adoption agency algorithms
- [x] Fragment parsing (§13.4, what `innerHTML` does): the context element,
      the adjusted current node, and the fragment cases scattered through tree
      construction — **html5lib tree construction 1434/1434 (100%)**, all 42
      suites, with only the 8 `#script-on` cases skipped and reported
- [x] CSS tokenizer (css-syntax-3 §4) and parser (§5): rules, at-rules,
      declarations, `!important`
- [x] Selectors (selectors-4): type/universal/class/id/attribute/pseudo,
      the four combinators, selector lists, specificity
- [x] Selector matching against the DOM, right to left with backtracking
- [x] Style cascade: origin, importance, specificity, document order,
      inheritance, and a UA stylesheet written as real CSS
- [x] Property value parsing: lengths (absolute and font-relative), colors
      (hex, rgb(), named), keywords, and the box shorthands
- [x] The CSS-wide keywords (`inherit`, `initial`, `unset`, `revert`), custom
      properties and `var()` with fallback, and the `style=` attribute at its
      own place in the cascade
- [x] `@media` query evaluation: media types, `and`/`or`/`not` with nesting,
      the discrete features, and the range features in all three spellings
- [x] Layout: the box tree with anonymous boxes, block formatting (widths,
      auto margins, heights, sibling margin collapsing) and inline formatting
      (line boxes, white-space collapsing, line breaking, text-align)
- [x] Real text: TrueType parsing (`cmap`, `hmtx`, `glyf` including composite
      glyphs), an anti-aliased scanline rasterizer using the nonzero winding
      rule, and font selection across three generic families in regular, bold
      and italic
- [x] Floats with `clear` and line boxes that shorten around them, margin
      collapsing in all three forms (siblings, parent/child, and through an
      empty box), horizontal borders and padding on inline boxes, and
      `visibility`
- [ ] Positioning other than static, vertical-align other than baseline,
      nested block formatting contexts, and real table layout
- [x] Paint: software rasterizer with alpha blending, backgrounds, borders,
      outline text, and a BMP writer
- [x] Window: Win32 via `extern fn` FFI, with scrolling

**Milestone 1 is complete: HTML + CSS render to pixels in a window.**

## Milestone 2 — a usable document viewer

- [x] Kerning, from both the `kern` table and GPOS pair positioning in both
      its formats
- [ ] **The rest of shaping.** Ligatures, and the scripts that need reordering
      or contextual forms, are still missing — as is fallback to another family
      for a glyph the selected face does not have, which is why CJK text renders
      blank under a Latin font.
- [x] A glyph cache, keyed on (face, glyph, size) — about 3x faster on a
      text-heavy page
- [x] CFF/Type-2 outlines, so OpenType fonts without a `glyf` table render
- [x] Re-layout on window resize — the whole cascade, since the viewport width
      decides which `@media` queries match
- [x] Charset sniffing (§13.2.3) and every decoder in the Encoding Standard
- [x] Line breaking per UAX #14, with the unimplemented rules named
- [x] Images: a PNG decoder, and the DEFLATE decompressor under it, both from
      scratch; `<img>` as a replaced element
- [x] URL parsing, and fetching over http and https with redirects, chunked
      responses, linked stylesheets and remote images
- [ ] A response cache, so a page's subresources are not refetched
- [x] Scrolling, hit testing, and links (fragment links navigate; the cursor
      changes over any link)
- [x] web-platform-tests reftest harness — **16/43 (37%)**, with what is not
      vendored counted by reason

## Milestone 3 and beyond

- [ ] JavaScript engine (own lexer/parser/interpreter; JIT is a non-goal for
      a long time)
- [ ] DOM bindings + events
- [ ] Incremental relayout/repaint
- [ ] MortOS port (the engine core has no OS dependencies; the platform layer
      is the only Windows-specific code)
- [ ] Vex integration — if Vex ever swaps Chromium for Rigor, it happens here

## Standing rules

- New spec areas start from the spec text, with section numbers in comments.
- Conformance suites are wired in as soon as a stage can run them; pass rates
  are tracked in the README, including failures.
- Compiler gaps found while building Rigor get filed as Mort issues, not
  worked around silently. Current wishlist: argv access for CLI programs
  (`std.env.args()`), string escape documentation.
