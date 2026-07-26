# Roadmap

The goal is a production-grade engine, which for a from-scratch project means:
spec-driven implementations, conformance suites wired into CI, and no stage
that is throwaway. Ladybird's trajectory is the reference point — this is a
years-long road, and every milestone below is real engine code.

## Milestone 1 — static renderer

HTML + CSS in, pixels in a window out. No JavaScript.

- [x] Repo + package layout (engine as an embeddable Mort package)
- [x] Input preprocessing (§13.2.3.5: BOM, newlines)
- [x] HTML tokenizer (§13.2.5) — tags, attributes, comments, doctypes,
      RCDATA/RAWTEXT/PLAINTEXT, numeric + named character references,
      spec-named parse errors
- [x] Full named-entity table generated from entities.json (2231 names,
      `tools/gen_entities.py` → `engine/src/html/entities.mx`)
- [x] html5lib-tests tokenizer conformance harness — **6887/6887 tokens and
      1737/1737 parse-error codes**; 145 cases skipped pending script-data
      and CDATA states
- [ ] Tree construction → DOM (§13.2.6): insertion modes, open-elements stack,
      active formatting elements; script-data tokenizer states land here
- [ ] CSS tokenizer + parser (css-syntax-3), selectors (selectors-4 subset)
- [ ] Style cascade: matching, specificity, inheritance, computed values
- [ ] Layout: block + inline formatting, box model
- [ ] Paint: software rasterizer, bitmap font text first
- [ ] Window: Win32 via `extern fn` FFI (CreateWindowExA + StretchDIBits)

## Milestone 2 — a usable document viewer

- [ ] Charset sniffing + non-UTF-8 decoding (§13.2.3)
- [ ] Real text: font loading (TrueType parsing), shaping for Latin scripts,
      line breaking per UAX #14 subset
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
