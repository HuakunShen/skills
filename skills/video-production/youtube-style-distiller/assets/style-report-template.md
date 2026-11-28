# Style report: <subject>

- Run: `<run-id>` · as-of `<YYYY-MM-DD>` · seed `<seed>`
- Corpus: `<n_videos>` videos in `<date range>`; sample `<n_sampled>` stratified over quarter × topic (see `sample.jsonl`)
- Ads excluded: `<excluded_ad_segments>` segments · STT loops collapsed: `<count>`
- Video pass: `<not run | n videos, approved by <who> at <resolution>/<effort>>`

## Summary

3–6 bullets. Each bullet is a finding, its confidence (`stable` / `tentative`), and one citation.

## 1. Narrative arc
<finding> — `video_id @ mm:ss` …

## 2. Opening hooks
| Hook type | Share of videos | Example (verbatim) | Citation |
| --- | --- | --- | --- |

## 3. Intro and outro formulae
<exact lines that recur in ≥ 3 videos, with counts> …

## 4. Catchphrases and recurring phrases
| Phrase | Videos | Function | Citation |
| --- | --- | --- | --- |

## 5. Sentence rhythm and diction
- Median sentence length: `<stats.sentence_length.median>` (`<unit>`)
- Question rate: `<stats.question_rate>` · Exclamation rate: `<stats.exclamation_rate>`
- Sentence starters: `<stats.top_sentence_starters>`
- Qualitative notes with citations …

## 6. Rhetorical and argument patterns
| Move | Definition | Videos | Example | When it fails |
| --- | --- | --- | --- | --- |

## 7. Humour, tone and stance
<findings with citations>

## 8. Never-say rules
| Rule | Reason | Observed avoidance | Source |
| --- | --- | --- | --- |
Structural bans: <list>

## 9. Visual and editing
<only if the video pass ran; otherwise write "Not analysed: no video input approved.">

## Limits
- Sample size and eras covered; topics not covered.
- Dimensions not analysed, and why.

## Blind evaluation log
| Round | N | Accuracy | p (one-sided) | Tells found | Action |
| --- | --- | --- | --- | --- | --- |

## Appendix: method
Commands run, seeds, model names and versions used, and where each artifact lives in the run directory.
