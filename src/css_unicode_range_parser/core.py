"""Parse and normalize CSS ``unicode-range`` values.

The CSS Fonts Level 3 specification defines ``unicode-range`` using a
notation built on top of ``U+``. Four concrete shapes are legal:

    U+416
    U+400-4FF
    U+4??
    U+??????

A single declaration may list any number of these separated by commas.
This module turns such a string into a list of :class:`CodePointRange`
objects whose endpoints are closed, inclusive integers. Normalization
outputs a canonical, whitespace-stable comma-separated string.

Design decisions worth stating plainly:

* Wildcards (``U+4??``) and trailing-question forms (``U+??????``) are
  expanded at parse time into the explicit closed interval they denote.
  We do not preserve the original syntactic sugar because the whole
  point of this library is a canonical representation.

* Leading digits in the hex portion are required. ``U+`` alone is not a
  valid range and is rejected. This matches every browser we checked.

* Surrogate code points (U+D800 through U+DFFF) are accepted as-is.
  CSS does not forbid them in ``unicode-range``; rejecting them would be
  stricter than the spec and would surprise users feeding in raw font
  data. The README calls this out.

* Code points above U+10FFFF are rejected. That is the Unicode ceiling
  and there is no useful interpretation for a higher value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

__all__ = [
    "CodePointRange",
    "ParseError",
    "normalize",
    "parse",
]

MAX_CODE_POINT = 0x10FFFF
_PREFIX = "U+"


class ParseError(ValueError):
    """Raised when a unicode-range value is malformed.

    Subclasses ``ValueError`` so callers catching ``ValueError`` for
    input validation continue to work.
    """


@dataclass(frozen=True)
class CodePointRange:
    """A single closed, inclusive range of Unicode code points.

    ``start`` and ``end`` are plain integers in the inclusive range
    ``[0, 0x10FFFF]`` with ``start <= end``.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if not (0 <= self.start <= self.end <= MAX_CODE_POINT):
            raise ParseError(
                f"invalid range [{self.start:#x}, {self.end:#x}]"
            )

    def __contains__(self, point: object) -> bool:
        if isinstance(point, int):
            return self.start <= point <= self.end
        return False

    def __iter__(self):
        yield self.start
        yield self.end

    def as_css(self) -> str:
        """Return the canonical CSS representation of this range.

        Single-point ranges render as ``U+XXXX``; multi-point ranges as
        ``U+XXXX-XXXX``. Hex digits are uppercase and never padded past
        what is needed to express the value, except that ``U+0`` is used
        for the single code point zero so the output always carries at
        least one digit.
        """
        if self.start == self.end:
            return f"{_PREFIX}{self.start:X}"
        return f"{_PREFIX}{self.start:X}-{self.end:X}"


def _expand_wildcard(hex_part: str) -> CodePointRange:
    """Expand a hex-with-``?`` form into an explicit closed range.

    ``4??`` means "every code point whose hex representation, when
    padded to the width of the token, matches ``4`` in the leading digit
    and anything in the others" — i.e. ``[0x400, 0x4FF]``. Each ``?``
    spans one hex digit, so the number of question marks determines the
    span width. We implement this with bit shifts rather than string
    formatting because it is exact and immune to odd widths.
    """
    q_count = hex_part.count("?")
    if q_count == 0:
        raise ParseError(f"no wildcards in {hex_part!r}")
    if not all(c == "?" for c in hex_part[-q_count:]):
        raise ParseError(f"wildcards must be trailing in {hex_part!r}")
    prefix = hex_part[:-q_count]
    if not prefix:
        # Pure question marks, e.g. ``U+??``. Covers the whole space
        # implied by the width: ``??`` is [0, 0xFF].
        start = 0
    else:
        try:
            start = int(prefix, 16)
        except ValueError as exc:
            raise ParseError(f"bad hex prefix {prefix!r}") from exc
    span = 1 << (4 * q_count)
    start <<= 4 * q_count
    end = start + span - 1
    if end > MAX_CODE_POINT:
        end = MAX_CODE_POINT
    return CodePointRange(start, end)


def _parse_single(token: str) -> CodePointRange:
    """Parse one ``U+...`` token (already stripped of surrounding space)."""
    if not token[:2].upper() == _PREFIX:
        raise ParseError(f"missing U+ prefix in {token!r}")
    body = token[2:]
    if not body:
        raise ParseError("empty range after U+")
    if "?" in body:
        return _expand_wildcard(body)
    if "-" in body:
        lo, _, hi = body.partition("-")
        if not lo or not hi:
            raise ParseError(f"incomplete range in {token!r}")
        try:
            start = int(lo, 16)
            end = int(hi, 16)
        except ValueError as exc:
            raise ParseError(f"bad hex in {token!r}") from exc
        if start > end:
            raise ParseError(f"range endpoint order in {token!r}")
        return CodePointRange(start, end)
    try:
        point = int(body, 16)
    except ValueError as exc:
        raise ParseError(f"bad hex in {token!r}") from exc
    return CodePointRange(point, point)


def parse(value: str) -> List[CodePointRange]:
    """Parse a CSS ``unicode-range`` declaration.

    Accepts a comma-separated list of ``U+`` tokens and returns a list
    of :class:`CodePointRange` in the order they appeared. Whitespace
    around tokens is ignored. An empty string is rejected: an empty
    ``unicode-range`` is not legal CSS and accepting it here would mask
    caller bugs.
    """
    if value is None:
        raise ParseError("value is None")
    stripped = value.strip()
    if not stripped:
        raise ParseError("empty unicode-range")
    ranges: List[CodePointRange] = []
    for raw in stripped.split(","):
        token = raw.strip()
        if not token:
            raise ParseError("empty token in unicode-range")
        ranges.append(_parse_single(token))
    return ranges


def normalize(value: str) -> str:
    """Parse ``value`` and re-emit it in canonical form.

    The output is a single comma-separated string of ``U+XXXX`` or
    ``U+XXXX-XXXX`` tokens, uppercase, no redundant whitespace. Adjacent
    or overlapping ranges are *not* merged: merging changes the meaning
    of caller-supplied data (e.g. ordering for diagnostics) and is a
    distinct operation that belongs in a separate function.
    """
    return ", ".join(r.as_css() for r in parse(value))
