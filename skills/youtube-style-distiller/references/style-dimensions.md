# Style dimensions and evidence rules

Each dimension needs: a plain-language finding, at least one timestamped citation, the number of videos
that show it, and a confidence tag (`stable` ≥ 3 videos across ≥ 2 eras, `tentative` otherwise).

## 1. Narrative arc

- Map the beats of a typical episode (hook → setup → development → turn → payoff → close) with the
  median timestamp of each beat as a fraction of duration.
- Note which beats are optional and what triggers their absence (topic type, length).
- Evidence: `video_id @ mm:ss` for the first and last line of each beat.

## 2. Opening hooks

- Read `stats.json → opening_hooks` for the first 30 s of each sampled video.
- Classify hook types (question, contrarian claim, cold open on a scene, stake statement, direct address).
- Report the share of each type and two verbatim examples per type.

## 3. Intro and outro formulae

- Identify fixed lines that recur (greetings, sign-offs, calls to action). Count exact or near-exact repeats.
- Report exact wording only when it appears in ≥ 3 videos; otherwise describe the pattern.

## 4. Catchphrases and recurring phrases

- Start from `stats.json → recurring_phrases` (n-grams with document frequency ≥ `--min-videos`).
- Drop generic phrases a reader would expect from any speaker; keep phrases that are distinctive for this creator.
- For each keeper: frequency, number of videos, one citation, and the function it serves (signpost, emphasis, transition, sign-off).

## 5. Sentence rhythm and diction

- From `stats.json`: median and mean sentence length, question rate, exclamation rate, sentence starters.
- Describe rhythm qualitatively too: short punch lines after long setups, rhetorical pairs, lists of three.
- Note register (colloquial, formal, mixed) and code-switching if the corpus is multilingual.

## 6. Rhetorical and argument patterns

- Common moves: concession then rebuttal, analogy, numbered structure, reductio, "what most people get wrong",
  sourcing habits (names sources, reads numbers aloud, admits uncertainty).
- For each move: definition, frequency (videos), one timestamped example, and a short "when it fails" note.

## 7. Humour, tone, and stance

- Self-deprecation, callbacks, teasing of the audience, sarcasm, earnestness. Give frequency and examples.
- Stance toward the audience (peer, teacher, host, provocateur) with evidence.

## 8. Never-say rules (anti-slop)

- Start from [never-say.json](../assets/never-say.json) and extend with creator-specific bans that are
  observed as *absent* in the corpus (phrases the creator never uses even when the topic invites them).
- Each rule needs a reason and, for observed bans, a count of how often the creator avoids it.
- Also list structural bans: no essay closers, no stock metaphors, no empty superlatives, no hedging openers.

## 9. Visual and editing (only with multimodal observations)

Visual layout, B-roll, motion graphics, typography, pacing, and BGM/SFX come from
[multimodal-video.md](multimodal-video.md). Without video input, state explicitly that these dimensions were
not analysed; do not infer them from transcripts.

## Reporting rules

- Every finding lists its sample: "n videos, eras X–Y, topics A/B".
- Separate what is observed (with citations) from what is inferred (labelled as inference).
- Never report a number that `stats.json` does not contain. Recompute, don't estimate.
