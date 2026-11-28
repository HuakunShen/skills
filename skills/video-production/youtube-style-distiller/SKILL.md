---
name: youtube-style-distiller
description: Use when distilling any YouTube creator's complete on-camera and editing style from a transcript corpus and/or video files, producing an evidence-backed style report and a reusable persona prompt with visual/editing spec, few-shot examples and a blind evaluation loop. Triggers on style distillation, persona cloning from videos, voice and tone extraction, hook/intro/outro patterns, catchphrases, sentence rhythm, Never-say anti-slop rules, subtitle or B-roll style, and blind test of an imitation.
---

# YouTube Style Distiller

Turn a creator's back catalogue into two deliverables:

- `style-report.md` — what the creator does, with timestamped evidence for every claim.
- `persona-prompt.md` — an actionable prompt, visual/editing spec, few-shot examples, and a closed-loop blind evaluation protocol.

The skill is creator-agnostic. Every subject-specific fact comes from the run's own inputs, never from this file.

## Non-negotiable rules

1. **Evidence or silence.** Every style claim cites at least one `video_id @ mm:ss` (or a segment id). Claims with fewer than the minimum number of supporting videos are reported as `tentative`, not as traits.
2. **Stratify before you read.** Sample across time and topic first (`sample`), then analyse. Never just read the newest or most-viewed videos.
3. **Ads and sponsor reads are not voice.** Flag and exclude them from style statistics; describe them only as a separate "sponsor segment" pattern if asked.
4. **Video input is opt-in and gated.** Direct multimodal video analysis costs far more than transcripts. Estimate first, get approval, and use low resolution and low reasoning effort by default. See [multimodal-video.md](references/multimodal-video.md).
5. **Never invent quotes.** Quoted catchphrases and examples must match cleaned segments exactly. `ban-check` and `stats` output is the source of truth for frequencies.
6. **Close the loop.** A persona is not done until blind evaluation shows reviewers cannot reliably tell generated scripts from real excerpts. See [persona-and-eval.md](references/persona-and-eval.md).
7. **Keep the artifact generic.** Do not paste the creator's name into the skill's own docs, code, or tests when working on this skill itself; run-specific output belongs in the run directory.

## Workflow

| Phase | Action | Output |
| --- | --- | --- |
| 0. Scope | Record subject, date range, topic taxonomy, budget, and whether video input is approved. | `run.json` in the run dir |
| 1. Manifest | List in-scope videos with `video_id`, `published` (YYYY-MM-DD), `topic`, `duration_s`. Keep out-of-range items in the manifest with a reason. | `manifest.jsonl` |
| 2. Sample | `python3 scripts/style_distill.py sample --manifest manifest.jsonl -n 30 --seed 7 --out sample.jsonl` | `sample.jsonl`, stratified over quarter x topic |
| 3. Captions | Fetch captions with the host's tools, then `python3 scripts/style_distill.py clean <files...> --out segments.jsonl [--ad-patterns custom.json]`. | `segments.jsonl` with `ad_candidate` and `stt_loop_collapsed` flags |
| 4. Quantify | `python3 scripts/style_distill.py stats --segments segments.jsonl --stopwords assets/stopwords.json --min-videos 3 --out stats.json` | sentence rhythm, question/exclamation rates, recurring phrases, opening hooks |
| 5. Qualitative read | Read a sample of segments per topic and per era. Fill the dimensions in [style-dimensions.md](references/style-dimensions.md), each with citations. | draft findings |
| 6. Video (optional, gated) | Only if approved: run the multimodal pass in [multimodal-video.md](references/multimodal-video.md) on the sampled videos, validating each record against `assets/video-observation.schema.json`. | `video-observations/*.json` |
| 7. Write deliverables | Fill [style-report-template.md](assets/style-report-template.md) → `style-report.md`. Fill [persona-prompt-template.md](assets/persona-prompt-template.md) → `persona-prompt.md`. | both deliverables |
| 8. Self-check | `python3 scripts/style_distill.py ban-check persona-prompt-sample.md` and check every quote against `segments.jsonl`. | zero unexplained hits |
| 9. Blind eval | Generate N scripts from the persona, mix with N real excerpts, run `blind-pack`, collect blind guesses, run `blind-score`. Iterate on the prompt until accuracy is near chance. | `blind/` results appended to the report |

## Commands

All commands run from the skill directory, or with the absolute path to `scripts/style_distill.py`. Python 3.9+ stdlib only.

```bash
python3 scripts/style_distill.py sample --manifest manifest.jsonl -n 30 --seed 7 --out sample.jsonl
python3 scripts/style_distill.py clean captions/*.srt --out segments.jsonl
python3 scripts/style_distill.py stats --segments segments.jsonl --out stats.json
python3 scripts/style_distill.py ban-check draft.md            # exit 1 on hits
python3 scripts/style_distill.py blind-pack --items items.jsonl --seed 7 --out-dir blind/
python3 scripts/style_distill.py blind-score --key blind/key.json --answers answers.jsonl
```

Run tests: `python3 -m unittest discover -s scripts -p 'test_*.py'`.

## Where to look

- Dimensions and evidence rules (narrative arc, hooks, catchphrases, rhythm, rhetoric, Never-say): [style-dimensions.md](references/style-dimensions.md)
- Caption cleaning, ad handling, sampling rules, and stats semantics: [corpus-pipeline.md](references/corpus-pipeline.md)
- Multimodal video pass (intro/outro, layout, B-roll, motion graphics, typography, pacing, BGM/SFX): [multimodal-video.md](references/multimodal-video.md)
- Persona prompt structure and blind evaluation protocol: [persona-and-eval.md](references/persona-and-eval.md)
- Anti-slop Never-say seed: [never-say.json](assets/never-say.json)

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Reading only the top or newest videos | Use `sample`; report the stratum counts in the report |
| Treating sponsor reads as the voice | Keep `ad_candidate` segments out of `stats`; check the ad patterns cover the creator's sponsor language |
| Quoting an auto-caption that was never spoken exactly | Quote from `segments.jsonl`; mark the line as a caption if the text is ambiguous |
| Single-video "catchphrase" | Require the `--min-videos` threshold |
| Persona that reads as an essay | Run `ban-check`; check sentence-length median against `stats.json` |
| Declaring success without blind eval | Accuracy near 0.5 with a high p-value is the only pass signal |
