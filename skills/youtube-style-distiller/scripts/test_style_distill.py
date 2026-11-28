#!/usr/bin/env python3
"""Behavioral checks for caption cleaning, sampling, style statistics, ban-check and blind scoring."""
import json
import random
import tempfile
import unittest
from pathlib import Path

import style_distill as sd

ADS = sd.load_ad_patterns(None)
RULES = sd.load_rules(sd.ASSETS / "never-say.json")

SRT = """1
00:00:00,000 --> 00:00:02,000
[Music]

2
00:00:02,000 --> 00:00:04,000
Welcome back to the show.

3
00:00:04,000 --> 00:00:06,000
Welcome back to the show. Today we talk about cats.

4
00:00:06,000 --> 00:00:08,000
This video is brought to you by ExampleCo, use code SAVE10.
"""

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>hello</c> there friend

00:00:03.000 --> 00:00:05.000
hello there friend how are you
"""


class CleanTests(unittest.TestCase):
    def test_srt_drops_sound_tags_and_rolling_duplicates(self):
        segs = sd.clean_captions(SRT, ADS, "vid1")
        texts = [s["text"] for s in segs]
        self.assertEqual(texts[0], "Welcome back to the show.")
        self.assertEqual(texts[1], "Today we talk about cats.")
        self.assertNotIn("[Music]", " ".join(texts))

    def test_ad_segments_are_flagged_not_deleted(self):
        segs = sd.clean_captions(SRT, ADS, "vid1")
        ad = [s for s in segs if "ad_candidate" in s["flags"]]
        self.assertEqual(len(ad), 1)
        self.assertIn("use code", ad[0]["text"].lower())

    def test_vtt_strips_inline_tags_and_rolling_prefix(self):
        segs = sd.clean_captions(VTT, ADS, "vid2")
        self.assertEqual([s["text"] for s in segs], ["hello there friend", "how are you"])

    def test_runaway_repetition_is_collapsed_and_flagged(self):
        text, flags = sd.strip_stt_artifacts("the cat the cat the cat the cat sat down")
        self.assertIn("stt_loop_collapsed", flags)
        self.assertEqual(text.count("the cat"), 1)

    def test_cjk_repetition_is_collapsed(self):
        text, flags = sd.strip_stt_artifacts("我们今天聊聊猫我们今天聊聊猫我们今天聊聊猫我们今天聊聊猫")
        self.assertIn("stt_loop_collapsed", flags)
        self.assertEqual(text.count("我们今天聊聊猫"), 1)


class SampleTests(unittest.TestCase):
    def manifest(self):
        rows = []
        for year in (2021, 2023, 2025):
            for i in range(10):
                rows.append({"video_id": f"v{year}{i:02d}", "published": f"{year}-0{(i % 9) + 1}-15",
                             "topic": "alpha" if i % 2 else "beta"})
        return rows

    def test_sample_size_and_determinism(self):
        a = sd.stratified_sample(self.manifest(), 12, seed=3)
        b = sd.stratified_sample(self.manifest(), 12, seed=3)
        self.assertEqual(len(a), 12)
        self.assertEqual([v["video_id"] for v in a], [v["video_id"] for v in b])

    def test_every_year_is_represented_when_budget_covers_all_strata(self):
        manifest = self.manifest()
        strata = {(sd.quarter_of(v["published"]), v["topic"]) for v in manifest}
        picked = sd.stratified_sample(manifest, len(strata) * 2, seed=1)
        self.assertEqual({v["published"][:4] for v in picked}, {"2021", "2023", "2025"})

    def test_small_budget_is_seeded_not_biased_to_earliest_dates(self):
        manifest = self.manifest()
        picked = sd.stratified_sample(manifest, 3, seed=11)
        self.assertEqual(len(picked), 3)
        self.assertEqual(picked, sd.stratified_sample(manifest, 3, seed=11))

    def test_small_n_takes_one_per_stratum_without_overflow(self):
        alloc = sd.allocate({("2024Q1", "a"): 5, ("2024Q2", "a"): 5, ("2024Q3", "b"): 5}, 2, random.Random(1))
        self.assertEqual(sum(alloc.values()), 2)

    def test_allocation_never_exceeds_stratum_size(self):
        alloc = sd.allocate({("2024Q1", "a"): 1, ("2024Q2", "a"): 50}, 20, random.Random(1))
        self.assertLessEqual(alloc[("2024Q1", "a")], 1)
        self.assertEqual(sum(alloc.values()), 20)


class StatsTests(unittest.TestCase):
    def segments(self):
        base = [
            {"video_id": "a", "start": 0.0, "end": 5.0, "text": "Why does this happen? It happens because of heat.", "flags": []},
            {"video_id": "a", "start": 40.0, "end": 45.0, "text": "Sponsor break here.", "flags": ["ad_candidate"]},
        ]
        for vid in ("b", "c", "d"):
            base.append({"video_id": vid, "start": 0.0, "end": 5.0,
                         "text": "Here is the thing you need to know. Stop right there!", "flags": []})
        return base

    def test_question_and_exclamation_rates_and_ad_exclusion(self):
        stats = sd.style_stats(self.segments(), set(), min_videos=3, hook_seconds=30)
        self.assertEqual(stats["excluded_ad_segments"], 1)
        self.assertGreater(stats["question_rate"], 0)
        self.assertGreater(stats["exclamation_rate"], 0)

    def test_recurring_phrase_needs_min_videos(self):
        stats = sd.style_stats(self.segments(), set(), min_videos=3, hook_seconds=30)
        phrases = {p["phrase"] for p in stats["recurring_phrases"]}
        self.assertIn("you need", phrases)
        self.assertNotIn("why does", phrases)

    def test_opening_hook_stops_at_hook_window(self):
        segs = [{"video_id": "x", "start": 1.0, "end": 2.0, "text": "early", "flags": []},
                {"video_id": "x", "start": 90.0, "end": 91.0, "text": "late", "flags": []}]
        hooks = sd.style_stats(segs, set(), 1, hook_seconds=30)["opening_hooks"]
        self.assertEqual(hooks[0]["opening"], "early")


class BanCheckTests(unittest.TestCase):
    def test_reports_line_and_column(self):
        hits = sd.ban_check("Fine line.\nLet's dive in now.", RULES)
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["line"], hits[0]["column"]), (2, 1))

    def test_cjk_rules_match(self):
        self.assertTrue(sd.ban_check("综上所述，我们结束。", RULES))

    def test_clean_text_has_no_hits(self):
        self.assertEqual(sd.ban_check("Cats knock things off tables.", RULES), [])


class BlindTests(unittest.TestCase):
    def test_key_is_separate_and_scoring_is_exact(self):
        items = [{"id": "real-1", "label": "real", "text": "a"}, {"id": "gen-1", "label": "generated", "text": "b"},
                 {"id": "real-2", "label": "real", "text": "c"}, {"id": "gen-2", "label": "generated", "text": "d"}]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "items.jsonl"
            src.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
            sd.main(["blind-pack", "--items", str(src), "--seed", "5", "--out-dir", str(tmp / "out")])
            blind = [json.loads(l) for l in (tmp / "out" / "blind.jsonl").read_text().splitlines()]
            key = json.loads((tmp / "out" / "key.json").read_text())
            self.assertNotIn("label", blind[0])
            self.assertTrue(all(b["id"] in key for b in blind))
            answers = tmp / "answers.jsonl"
            answers.write_text("".join(json.dumps({"id": b["id"], "guess": key[b["id"]]}) + "\n" for b in blind))
            self.assertEqual(sd.main(["blind-score", "--key", str(tmp / "out" / "key.json"),
                                      "--answers", str(answers)]), 0)

    def test_binomial_tail(self):
        self.assertAlmostEqual(sd.binomial_tail(4, 4), 1 / 16)
        self.assertAlmostEqual(sd.binomial_tail(0, 4), 1.0)


if __name__ == "__main__":
    unittest.main()
