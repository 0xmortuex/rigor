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
- [ ] `inherit` / `initial` / `unset` keywords and custom properties
- [ ] `@media` query evaluation (rules inside one currently always apply)
- [x] Layout: the box tree with anonymous boxes, block formatting (widths,
      auto margins, heights, sibling margin collapsing) and inline formatting
      (line boxes, white-space collapsing, line breaking, text-align)
- [x] Real text: TrueType parsing (`cmap`, `hmtx`, `glyf` including composite
      glyphs), an anti-aliased scanline rasterizer using the nonzero winding
      rule, and font selection across three generic families in regular, bold
      and italic
- [ ] Floats, static positioning beyond normal flow, parent/child margin
      collapsing, inline borders and padding
- [x] Paint: software rasterizer with alpha blending, backgrounds, borders,
      outline text, and a BMP writer
- [x] Window: Win32 via `extern fn` FFI, with scrolling

**Milestone 1 is complete: HTML + CSS render to pixels in a window.**

## Milestone 2 — a usable document viewer

- [ ] **Text shaping.** Glyphs are placed at their nominal advances, so there
      is no kerning (`kern`/`GPOS`), no ligatures, and no support for scripts
      needing reordering or contextual forms. This is the largest remaining
      typography gap now that outlines are real.
- [x] A glyph cache, keyed on (face, glyph, size) — about 3x faster on a
      text-heavy page
- [ ] CFF/Type-2 outlines, so OpenType fonts without a `glyf` table render
      rather than falling back
- [ ] Re-layout on window resize (the viewer keeps its initial width)
- [ ] Charset sniffing + non-UTF-8 decoding (§13.2.3)
- [ ] Line breaking per a UAX #14 subset (currently breaks at spaces only)
- [ ] Images: PNG decoder first (from scratch, like everything else)
- [ ] `std.net`/`std.https`-backed fetching: URLs, http(s), redirects, cache
- [ ] Scrolling, hit testing, links
- [ ] web-platform-tests harness for parsing + CSS subsets

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
