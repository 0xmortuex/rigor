# Rigor

**A browser engine written from scratch in [Mort](https://github.com/0xmortuex/Mort).**

Rigor is a standalone, embeddable web engine built the way the big ones are —
spec-driven, tested from commit one — in a programming language that is itself
built from scratch. The name is from *rigor mortis*, and from the discipline
this project runs on: every algorithm is implemented from the WHATWG/CSSWG
specification it cites, error recovery included, and progress is measured in
passing conformance tests, not vibes.

> **Status: pre-alpha.** The HTML tokenizer is real (WHATWG §13.2.5,
> state-for-state, with spec-named parse errors). Everything after it is
> roadmap. See [docs/ROADMAP.md](docs/ROADMAP.md) for the honest ledger.

## What works today

- **Input preprocessing** (§13.2.3.5): BOM stripping, newline normalization.
- **HTML tokenizer** (§13.2.5): data / RCDATA / RAWTEXT / PLAINTEXT, tags and
  attributes (duplicate dropping, ASCII lowercasing), comments including the
  `<!` corner cases, the complete DOCTYPE state family, bogus comment, and
  character references — numeric fully (C1 remapping table included), named
  via a core entity table (full 2231-name table is generated next).
- **Parse errors** carry the spec's own identifiers
  (`unexpected-null-character`, `abrupt-doctype-public-identifier`, …) plus a
  byte offset.
- **`rigor` CLI**: pipe HTML in, get the token stream and error list out.

```
> '<!DOCTYPE html><p class="x">Hi &amp; bye</p>' | rigor
doctype <!DOCTYPE html>
start   <p class="x">
text    "Hi & bye"
end     </p>
eof
```

## Build

Requires the [Mort toolchain](https://github.com/0xmortuex/Mort) (`mortc`).

```
mortc build      # build the rigor CLI  -> build/rigor.exe
mortc test       # run the engine's test suite
mortc fmt        # format sources
```

## Layout

```
engine/          the engine library (Mort package `engine`) — embeddable, no CLI
  src/html/     tokenizer, token arena, entities, preprocessing
src/main.mx     the rigor developer CLI (token dump)
tests/           spec-behavior tests (mortc test)
docs/            ARCHITECTURE.md, ROADMAP.md
```

Design notes live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT.
