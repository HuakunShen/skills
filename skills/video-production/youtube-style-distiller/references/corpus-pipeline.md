# Corpus pipeline: cleaning, sampling, statistics

## Caption cleaning (`clean`)

- Accepts SRT and WebVTT. Inline tags (`<c>…</c>`, timestamps) are removed.
- **Rolling captions.** Auto-captions often repeat the previous cue as a prefix. Only the fresh suffix is kept,
  and exact repeats are dropped.
- **Sound tags.** Bracketed or parenthesised tags of ≤ 30 characters (`[Music]`, `(applause)`) are removed and
  flagged `sound_tag_removed`. Real parentheticals in speech are also removed, so check the output on a few files.
- **STT loops.** A 2–40 character unit repeated 4+ times in a row is collapsed to one copy and flagged
  `stt_loop_collapsed`. This catches decoder hallucination loops in Whisper-style output.
- **Ads.** Segments matching `assets/ad-patterns.json` (or a custom `--ad-patterns` file) are kept but flagged
  `ad_candidate`. Review flagged segments by hand; false positives are common for words like "affiliate" in
  ordinary speech.

Caption files with word-level timing or speaker labels need the host's own converter first. This tool does not
diarise.

## Sampling (`sample`)

- Input: JSONL manifest with `video_id`, `published` (`YYYY-MM-DD`), `topic`.
- Strata are quarter × topic. Allocation is proportional with a minimum of one per non-empty stratum.
- If the budget is smaller than the number of strata, a seeded random subset of strata gets one slot each.
- The same seed and manifest always give the same sample. Record the seed in `run.json`.
- Choose `n` so that each era has at least three videos. If the corpus is small, sample everything.

## Statistics (`stats`)

- Sentence splitting keeps the terminal punctuation. CJK and Latin punctuation are both recognised.
- Sentence length: characters for CJK-heavy sentences, words otherwise. Compare across runs only if the
  language mix is the same.
- Recurring phrases: word/character 2–4-grams with document frequency across videos, excluding n-grams made
  only of stopwords (`assets/stopwords.json`). Top 50 with `videos ≥ min_videos`.
- Opening hooks: segment text with `start < hook_seconds` (default 30), per video.
- Ad-flagged segments are excluded and counted in `excluded_ad_segments`.
