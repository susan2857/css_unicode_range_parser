import unittest

from css_unicode_range_parser import (
    CodePointRange,
    ParseError,
    normalize,
    parse,
)


class TestSingleCodePoint(unittest.TestCase):
    def test_basic_single(self):
        r = parse("U+416")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].start, 0x416)
        self.assertEqual(r[0].end, 0x416)

    def test_single_uppercase_hex(self):
        r = parse("U+1F600")
        self.assertEqual(r[0].start, 0x1F600)

    def test_single_zero(self):
        r = parse("U+0")
        self.assertEqual(r[0].start, 0)
        self.assertEqual(r[0].end, 0)


class TestExplicitRange(unittest.TestCase):
    def test_basic_range(self):
        r = parse("U+400-4FF")
        self.assertEqual(r[0].start, 0x400)
        self.assertEqual(r[0].end, 0x4FF)

    def test_range_single_point_coincides(self):
        r = parse("U+100-100")
        self.assertEqual(r[0].start, 0x100)
        self.assertEqual(r[0].end, 0x100)

    def test_range_reversed_rejected(self):
        with self.assertRaises(ParseError):
            parse("U+500-400")


class TestWildcard(unittest.TestCase):
    def test_single_question_group(self):
        r = parse("U+4??")
        self.assertEqual(r[0].start, 0x400)
        self.assertEqual(r[0].end, 0x4FF)

    def test_two_question_groups(self):
        r = parse("U+4???")
        self.assertEqual(r[0].start, 0x4000)
        self.assertEqual(r[0].end, 0x4FFF)

    def test_pure_questions(self):
        r = parse("U+??")
        self.assertEqual(r[0].start, 0)
        self.assertEqual(r[0].end, 0xFF)

    def test_six_questions(self):
        # Six question marks spans 24 bits but the Unicode ceiling is
        # U+10FFFF, so the range is clamped.
        r = parse("U+??????")
        self.assertEqual(r[0].start, 0)
        self.assertEqual(r[0].end, 0x10FFFF)


class TestMultipleRanges(unittest.TestCase):
    def test_two_ranges(self):
        r = parse("U+400-4FF, U+1F600")
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0].start, 0x400)
        self.assertEqual(r[1].start, 0x1F600)

    def test_whitespace_around_tokens(self):
        r = parse("  U+416  ,  U+500-50F  ")
        self.assertEqual(len(r), 2)
        self.assertEqual(r[1].end, 0x50F)


class TestNormalize(unittest.TestCase):
    def test_normalizes_single(self):
        self.assertEqual(normalize("u+416"), "U+416")

    def test_normalizes_range(self):
        self.assertEqual(normalize("U+400-4ff"), "U+400-4FF")

    def test_normalizes_wildcard(self):
        self.assertEqual(normalize("U+4??"), "U+400-4FF")

    def test_normalizes_multiple_with_spaces(self):
        self.assertEqual(
            normalize("  U+4?? , U+1F600 "),
            "U+400-4FF, U+1F600",
        )

    def test_normalize_zero(self):
        self.assertEqual(normalize("U+0"), "U+0")


class TestErrors(unittest.TestCase):
    def test_missing_prefix(self):
        with self.assertRaises(ParseError):
            parse("416")

    def test_empty_string(self):
        with self.assertRaises(ParseError):
            parse("")

    def test_empty_token_between_commas(self):
        with self.assertRaises(ParseError):
            parse("U+416,,U+500")

    def test_trailing_comma(self):
        with self.assertRaises(ParseError):
            parse("U+416,")

    def test_bad_hex(self):
        with self.assertRaises(ParseError):
            parse("U+GGGG")

    def test_incomplete_range(self):
        with self.assertRaises(ParseError):
            parse("U+400-")

    def test_above_max_code_point(self):
        with self.assertRaises(ParseError):
            parse("U+110000")

    def test_range_endpoint_above_max(self):
        with self.assertRaises(ParseError):
            parse("U+10FFFF-110000")

    def test_prefix_only(self):
        with self.assertRaises(ParseError):
            parse("U+")

    def test_wildcards_not_trailing(self):
        # ``?4`` is not legal; wildcards must be a trailing run.
        with self.assertRaises(ParseError):
            parse("U+?4")

    def test_parse_error_is_value_error(self):
        self.assertTrue(issubclass(ParseError, ValueError))


class TestCodePointRangeDataclass(unittest.TestCase):
    def test_contains_int(self):
        r = CodePointRange(0x400, 0x4FF)
        self.assertIn(0x450, r)
        self.assertNotIn(0x500, r)

    def test_contains_rejects_non_int(self):
        r = CodePointRange(0, 0x10)
        self.assertNotIn("x", r)

    def test_iter_yields_endpoints(self):
        r = CodePointRange(5, 9)
        self.assertEqual(list(r), [5, 9])

    def test_frozen(self):
        r = CodePointRange(1, 2)
        with self.assertRaises(Exception):
            r.start = 3  # type: ignore[misc]

    def test_as_css_single(self):
        self.assertEqual(CodePointRange(0x416, 0x416).as_css(), "U+416")

    def test_as_css_range(self):
        self.assertEqual(CodePointRange(0x400, 0x4FF).as_css(), "U+400-4FF")

    def test_invalid_range_in_constructor(self):
        with self.assertRaises(ParseError):
            CodePointRange(10, 5)

    def test_negative_start_rejected(self):
        with self.assertRaises(ParseError):
            CodePointRange(-1, 5)


class TestSurrogatesAccepted(unittest.TestCase):
    """Surrogates (U+D800-U+DFFF) are intentionally permitted.

    CSS does not forbid them in ``unicode-range``. Rejecting them would
    be stricter than the spec and would break callers handling raw font
    metadata. Documented in the README.
    """

    def test_surrogate_point(self):
        r = parse("U+D800")
        self.assertEqual(r[0].start, 0xD800)

    def test_surrogate_range(self):
        r = parse("U+D800-DFFF")
        self.assertEqual(r[0].start, 0xD800)
        self.assertEqual(r[0].end, 0xDFFF)


if __name__ == "__main__":
    unittest.main()
