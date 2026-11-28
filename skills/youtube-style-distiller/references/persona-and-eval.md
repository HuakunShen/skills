# Persona prompt and closed-loop blind evaluation

## Persona prompt structure

`persona-prompt.md` must contain, in this order:

1. **Role and audience**: who the speaker is to the viewer, and what the viewer comes for. Keep it to a few lines.
2. **Voice rules**: sentence rhythm targets from `stats.json` (median length, question rate), diction, register,
   stance, humour rules, and code-switching if relevant.
3. **Structure rules**: the narrative arc as an ordered list, opening hook types with their shares, outro formula.
4. **Rhetorical moves**: each with a one-line trigger condition and a "when not to use" note.
5. **Catchphrases**: only the keepers from the style report, each with its function. Use sparingly; state a cap.
6. **Never-say list**: the combined generic and creator-specific bans, plus structural bans.
7. **Visual and editing spec** (only if the multimodal pass ran): layout, B-roll cue rules, motion graphics,
   typography, pacing targets, audio. Each item traces to observed timestamps in the report.
8. **Few-shot examples**: 3–5 short excerpts drawn from real segments, labelled by type (hook, explanation,
   transition, outro). Use real text; keep each under ~120 words.
9. **Output contract**: the format of a generated script (sections, timing, subtitles) and length targets.
10. **Self-check**: the persona must run the Never-say list against its own draft before returning.

Do not include the creator's real name in the prompt unless the user is producing content for that creator's
own channel with permission. Describe the voice, not the person.

## Blind evaluation loop

1. **Build the test set.** Write N = 20–40 items. Half are real excerpts (`label: real`) taken from held-out
   segments the persona never saw. Half are generated scripts for matching topics (`label: generated`) of
   similar length. Keep the excerpts' era and topic mix close to the generated set.
2. **Pack blind.** `python3 scripts/style_distill.py blind-pack --items items.jsonl --seed <S> --out-dir blind/`
   produces `blind/blind.jsonl` (opaque ids, no labels) and `blind/key.json`. Give reviewers only `blind.jsonl`.
3. **Collect guesses.** Each reviewer writes `{"id": "...", "guess": "real" | "generated"}` per item into
   `answers.jsonl`. Reviewers do not see the key. Use a different reviewer than the one who wrote the persona.
4. **Score.** `python3 scripts/style_distill.py blind-score --key blind/key.json --answers answers.jsonl`.
   Read `accuracy` and `p_value_one_sided`.
5. **Decide.**
   - Accuracy ≈ 0.5 with p > 0.05: the imitation is not distinguishable on this sample. Pass.
   - Accuracy significantly above 0.5: the reviewer found tells. Read the misses and the hits, list the tells,
     fix the prompt, and run a new blind round with new held-out items.
   - Do not re-use an item across rounds that you have already tuned against.
6. **Log the round.** Append the round number, N, accuracy, p-value, and the tells found to `style-report.md`.

## Pitfalls

- A reviewer who has read the persona will judge by rules, not by voice. Use reviewers who have not.
- Small N gives unstable accuracy. Below ~20 items, report the result as inconclusive.
- Length alone can give away generated text. Match length ranges before packing.
