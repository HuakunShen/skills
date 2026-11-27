#!/usr/bin/env python3
"""Offline regression tests for mechanical quote verification in audit_pipeline."""
import unittest

import audit_pipeline as pipeline


def cue_text(*bodies):
    return "".join(f"[#cue-{i:06d}]\n{body}\n\n" for i, body in enumerate(bodies, 1))


class VerifyQuoteTests(unittest.TestCase):
    def test_cjk_quote_spanning_two_cues_matches_without_space(self):
        source = cue_text("我们今天", "讨论问题")
        ok, basis = pipeline._verify_quote_in_source(source, {"unit_id": "cue-000001"}, "我们今天讨论问题")
        self.assertTrue(ok)
        self.assertEqual(basis, "matched_locator_unit_cjk_join")

    def test_cjk_quote_spanning_paragraphs_matches_through_source_fallback(self):
        source = "第一段结尾\n\n第二段开始\n\n第三段\n"
        ok, basis = pipeline._verify_quote_in_source(source, None, "结尾第二段开始")
        self.assertTrue(ok)
        self.assertEqual(basis, "matched_source_fallback_cjk_join")

    def test_cjk_quote_spanning_a_cjk_punctuation_boundary_matches(self):
        source = cue_text("今天天气很好。", "我们去公园")
        ok, basis = pipeline._verify_quote_in_source(source, {"unit_id": "cue-000001"}, "天气很好。我们去公园")
        self.assertTrue(ok)
        self.assertEqual(basis, "matched_locator_unit_cjk_join")

    def test_cjk_quote_spanning_paragraph_range_matches(self):
        source = cue_text("甲乙丙", "丁戊己", "庚辛壬")
        locator = {"kind": "paragraph", "start": 1, "end": 2}
        ok, basis = pipeline._verify_quote_in_source(source, locator, "甲乙丙丁戊己")
        self.assertTrue(ok)
        self.assertEqual(basis, "matched_paragraph_range_cjk_join")

    def test_verbatim_space_joined_match_still_reports_plain_basis(self):
        source = cue_text("我们讨论", "Python 问题")
        ok, basis = pipeline._verify_quote_in_source(source, {"unit_id": "cue-000001"}, "我们讨论 Python 问题")
        self.assertTrue(ok)
        self.assertEqual(basis, "matched_locator_unit")

    def test_cjk_fallback_is_not_fuzzy_and_rejects_a_changed_character(self):
        source = cue_text("我们今天", "讨论问题")
        ok, basis = pipeline._verify_quote_in_source(source, {"unit_id": "cue-000001"}, "我们今天讨论答案")
        self.assertFalse(ok)
        self.assertEqual(basis, "quote_not_found_in_source")

    def test_cjk_fallback_does_not_drop_whitespace_next_to_latin(self):
        source = cue_text("讨论 Python", "问题")
        ok, basis = pipeline._verify_quote_in_source(source, {"unit_id": "cue-000001"}, "讨论Python问题")
        self.assertFalse(ok)
        self.assertEqual(basis, "quote_not_found_in_source")

    def test_latin_cross_cue_quote_without_space_is_still_rejected(self):
        source = cue_text("Hello", "world")
        ok, basis = pipeline._verify_quote_in_source(source, {"unit_id": "cue-000001"}, "Helloworld")
        self.assertFalse(ok)
        self.assertEqual(basis, "quote_not_found_in_source")

    def test_empty_quote_is_rejected(self):
        ok, basis = pipeline._verify_quote_in_source(cue_text("甲乙"), None, "   ")
        self.assertFalse(ok)
        self.assertEqual(basis, "empty_quote")


if __name__ == "__main__":
    unittest.main()
