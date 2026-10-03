# css-unicode-range-parser

Parses CSS `unicode-range` values (the `U+` notation, explicit ranges,
and `?` wildcards) into a list of inclusive integer code-point ranges,
and re-emits them in canonical form.

```python
from css_unicode_range_parser import parse, normalize, CodePointRange

ranges = parse("U+4??, U+1F600-1F64F, U+0")
# [CodePointRange(start=0x400, end=0x4FF),
#  CodePointRange(start=0x1F600, end=0x1F64F),
#  CodePointRange(start=0, end=0)]

normalize("  u+4?? , U+1F600-1f64f ")
# 'U+400-4FF, U+1F600-1F64F'
```

Exports: `parse(value: str) -> list[CodePointRange]`,
`normalize(value: str) -> str`, `CodePointRange` (frozen dataclass with
`start`, `end`, `as_css()`), and `ParseError` (subclass of
`ValueError`).

## Why this exists

Font subsetting and CSS tooling both need to know which code points a
`unicode-range` declaration actually covers. The notation is small but
has three syntactic shapes (single point, `lo-hi`, `?` wildcards) that
are fiddly to expand correctly by hand. This library does the expansion
once and returns plain integers so downstream code never has to touch
the `U+` syntax again.

The trade-off: wildcards are expanded at parse time and the original
sugar is discarded. If you need to round-trip the exact input text,
this is the wrong library — use it when you want canonical ranges.

## Awkward edges

- Surrogate code points (U+D800 through U+DFFF) are accepted. CSS does
  not forbid them in `unicode-range`; rejecting them would be stricter
  than the spec and would surprise callers handling raw font metadata.

- `U+??????` (six question marks) nominally spans 24 bits, but Unicode
  tops out at U+10FFFF. The range is clamped to that ceiling rather
  than rejected, because the intent — "everything" — is unambiguous.

- Ranges are not merged across commas. `U+400-4FF, U+450-500` stays as
  two ranges. Merging changes caller-visible ordering and is a separate
  concern from parsing.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

