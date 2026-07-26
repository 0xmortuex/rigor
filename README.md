# Rigor

**A browser engine written from scratch in [Mort](https://github.com/0xmortuex/Mort).**

Rigor is a standalone, embeddable web engine built the way the big ones are —
spec-driven, tested from commit one — in a programming language that is itself
built from scratch. The name is from *rigor mortis*, and from the discipline
this project runs on: every algorithm is implemented from the WHATWG/CSSWG
specification it cites, error recovery included, and progress is measured in
passing conformance tests, not vibes.

> **Status: pre-alpha.** The HTML tokenizer is done and passes the html5lib
> conformance suites at 100%. Everything after it is roadmap. See
> [docs/ROADMAP.md](docs/ROADMAP.md) for the honest ledger.

## Conformance

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

cd conformance && mortc build          # build the conformance harness
python tools/run_conformance.py        # run html5lib-tests
python tools/gen_entities.py --check   # verify the entity table is current
```

## Layout

```
engine/            the engine library (Mort package `engine`) — embeddable
  src/html/        tokenizer, token arena, entities, preprocessing
src/main.mx        the rigor developer CLI (token dump)
tests/             spec-behavior tests (mortc test)
conformance/       batch driver binary for the html5lib suites
tools/             gen_entities.py, run_conformance.py, vendored suites
docs/              ARCHITECTURE.md, ROADMAP.md
```

`engine/src/html/entities.mx` is generated — edit `tools/gen_entities.py`, not
the table.

Design notes live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT.
