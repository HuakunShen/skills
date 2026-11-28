#!/usr/bin/env python3
"""Deterministic helpers for distilling a creator's speaking and editing style (Python 3.9+ stdlib).

Subcommands:
  clean       SRT/VTT -> cleaned JSONL segments (rolling-caption dedupe, STT loop and tag removal, ad flags)
  sample      stratified, seeded sampling of a video manifest across quarter x topic
  stats       sentence rhythm, recurring phrases, and opening hooks over cleaned segments
  ban-check   scan text against a Never-say rule file and report matches with line/column
  blind-pack  shuffle labelled excerpts into an opaque blind set plus a separate key
  blind-score score a blind guess file against the key with an exact binomial test
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import re
import sys

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TIME_RE = re.compile(r"^\s*((?:\d+:)?\d{1,2}:\d{2}[,.]\d{1,3})\s+-->\s+((?:\d+:)?\d{1,2}:\d{2}[,.]\d{1,3})")
TAG_RE = re.compile(r"<[^>]+>")
BRACKET_RE = re.compile(r"\[[^\]\n]{1,30}\]|\([^)\n]{1,30}\)")
LOOP_RE = re.compile(r"(.{2,40}?)\1{3,}", re.S)
SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]*|[.!?。！？]+")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z']*|[一-鿿]")
CJK_RE = re.compile(r"[一-鿿]")


def parse_time(raw: str) -> float:
    raw = raw.replace(",", ".")
    parts = [float(p) for p in raw.split(":")]
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def parse_captions(text: str) -> list[dict]:
    """Parse SRT or WebVTT text into cues: {start, end, text}. Ignores headers, notes and indexes."""
    cues: list[dict] = []
    current: dict | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = TIME_RE.match(line)
        if match:
            current = {"start": parse_time(match.group(1)), "end": parse_time(match.group(2)), "lines": []}
            cues.append(current)
            continue
        if current is None:
            continue
        if not line.strip():
            current = None
            continue
        current["lines"].append(line.strip())
    return [{"start": c["start"], "end": c["end"], "text": " ".join(c["lines"])} for c in cues]


def dedupe_rolling(cues: list[dict]) -> list[dict]:
    """Remove the repeated prefix that rolling auto-captions carry over from the previous cue."""
    out: list[dict] = []
    previous = ""
    for cue in cues:
        text = TAG_RE.sub("", cue["text"]).strip()
        if not text:
            continue
        if text == previous:
            continue
        fresh = text[len(previous):].strip() if previous and text.startswith(previous) else text
        previous = text
        if fresh:
            out.append({**cue, "text": fresh})
    return out


def strip_stt_artifacts(text: str) -> tuple[str, list[str]]:
    """Drop bracketed sound tags and collapse runaway repetition; return cleaned text and flags."""
    flags: list[str] = []
    cleaned, n_tags = BRACKET_RE.subn(" ", text)
    if n_tags:
        flags.append("sound_tag_removed")
    looped, n_loops = LOOP_RE.subn(r"\1", cleaned)
    if n_loops:
        flags.append("stt_loop_collapsed")
    return re.sub(r"\s+", " ", looped).strip(), flags


def load_ad_patterns(path: Path | None) -> list[re.Pattern]:
    source = path or ASSETS / "ad-patterns.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    return [re.compile(item, re.I) for item in data["patterns"]]


def clean_captions(text: str, ad_patterns: list[re.Pattern], video_id: str) -> list[dict]:
    segments = []
    for cue in dedupe_rolling(parse_captions(text)):
        body, flags = strip_stt_artifacts(cue["text"])
        if not body:
            continue
        if any(p.search(body) for p in ad_patterns):
            flags.append("ad_candidate")
        segments.append({"video_id": video_id, "start": round(cue["start"], 2), "end": round(cue["end"], 2),
                         "text": body, "flags": flags})
    return segments


def quarter_of(published: str) -> str:
    year, month = int(published[:4]), int(published[5:7])
    return f"{year}Q{(month - 1) // 3 + 1}"


def allocate(sizes: dict[tuple, int], n: int, rng: random.Random) -> dict[tuple, int]:
    """Largest-remainder proportional allocation; every non-empty stratum gets one slot when n allows.

    When n is smaller than the stratum count, a seeded random subset of strata gets one slot each, so
    no date range is systematically dropped.
    """
    total = sum(sizes.values())
    if n >= total:
        return dict(sizes)
    keys = sorted(sizes)
    if n < len(keys):
        return {k: 1 for k in rng.sample(keys, n)}
    ideal = {k: sizes[k] * n / total for k in keys}
    alloc = {k: max(1, int(ideal[k])) for k in keys}
    while sum(alloc.values()) > n:
        victim = max((k for k in keys if alloc[k] > 1), key=lambda k: alloc[k] - ideal[k])
        alloc[victim] -= 1
    while sum(alloc.values()) < n:
        grow = [k for k in keys if alloc[k] < sizes[k]]
        pick = max(grow, key=lambda k: ideal[k] - alloc[k])
        alloc[pick] += 1
    return alloc


def stratified_sample(manifest: list[dict], n: int, seed: int) -> list[dict]:
    strata: dict[tuple, list[dict]] = defaultdict(list)
    for video in manifest:
        strata[(quarter_of(video["published"]), video["topic"])].append(video)
    rng = random.Random(seed)
    alloc = allocate({k: len(v) for k, v in strata.items()}, n, rng)
    chosen: list[dict] = []
    for key in sorted(strata):
        pool = sorted(strata[key], key=lambda v: v["video_id"])
        picks = rng.sample(pool, alloc.get(key, 0))
        chosen.extend({**v, "stratum": f"{key[0]}/{key[1]}"} for v in picks)
    return sorted(chosen, key=lambda v: (v["published"], v["video_id"]))


def split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping the mark so question/exclamation rates can read it."""
    return [s.strip() for s in SENTENCE_RE.findall(text) if s.strip()]


def sentence_length(sentence: str) -> int:
    """Characters for CJK-heavy text, words otherwise, so both languages land on a comparable rhythm axis."""
    if CJK_RE.search(sentence):
        return len(re.sub(r"\s", "", sentence))
    return len(sentence.split())


def ngrams(tokens: list[str], sizes: tuple[int, ...]) -> set[str]:
    grams = set()
    for size in sizes:
        for i in range(len(tokens) - size + 1):
            grams.add(" ".join(tokens[i:i + size]))
    return grams


def style_stats(segments: list[dict], stopwords: set[str], min_videos: int, hook_seconds: float) -> dict:
    kept = [s for s in segments if "ad_candidate" not in s["flags"]]
    by_video: dict[str, list[dict]] = defaultdict(list)
    for seg in kept:
        by_video[seg["video_id"]].append(seg)

    lengths: list[int] = []
    questions = exclamations = sentence_count = 0
    starters: Counter = Counter()
    doc_freq: Counter = Counter()
    for vid, segs in by_video.items():
        text = " ".join(s["text"] for s in segs)
        sentences = split_sentences(text)
        for sent in sentences:
            sentence_count += 1
            lengths.append(sentence_length(sent))
            if sent.rstrip().endswith(("?", "？")):
                questions += 1
            if sent.rstrip().endswith(("!", "！")):
                exclamations += 1
            first = TOKEN_RE.findall(sent)[:1]
            if first:
                starters[first[0].lower()] += 1
        tokens = [t.lower() for t in TOKEN_RE.findall(text)]
        doc_freq.update(g for g in ngrams(tokens, (2, 3, 4))
                        if not all(w in stopwords for w in g.split()))

    lengths.sort()
    median = lengths[len(lengths) // 2] if lengths else 0
    recurring = [{"phrase": p, "videos": c} for p, c in doc_freq.most_common()
                 if c >= min_videos][:50]
    hooks = []
    for vid, segs in sorted(by_video.items()):
        head = [s["text"] for s in segs if s["start"] < hook_seconds]
        hooks.append({"video_id": vid, "opening": " ".join(head)})
    return {
        "videos": len(by_video),
        "segments": len(kept),
        "excluded_ad_segments": len(segments) - len(kept),
        "sentences": sentence_count,
        "sentence_length": {"median": median, "mean": round(sum(lengths) / len(lengths), 2) if lengths else 0},
        "question_rate": round(questions / sentence_count, 4) if sentence_count else 0,
        "exclamation_rate": round(exclamations / sentence_count, 4) if sentence_count else 0,
        "top_sentence_starters": starters.most_common(15),
        "recurring_phrases": recurring,
        "opening_hooks": hooks,
    }


def load_rules(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data["never_say"]
    for rule in rules:
        re.compile(rule["pattern"])
    return rules


def ban_check(text: str, rules: list[dict]) -> list[dict]:
    hits = []
    for rule in rules:
        for match in re.finditer(rule["pattern"], text, re.I):
            line = text.count("\n", 0, match.start()) + 1
            col = match.start() - (text.rfind("\n", 0, match.start()) + 1) + 1
            hits.append({"rule": rule["pattern"], "reason": rule.get("reason", ""), "line": line,
                         "column": col, "match": match.group(0)})
    return sorted(hits, key=lambda h: (h["line"], h["column"]))


def binomial_tail(correct: int, n: int) -> float:
    """One-sided exact p-value: probability of >= correct successes if guessing at 0.5."""
    return sum(math.comb(n, k) for k in range(correct, n + 1)) / 2 ** n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("clean", help="clean SRT/VTT files into JSONL segments")
    p.add_argument("captions", nargs="+", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--ad-patterns", type=Path, help="JSON {patterns: [...]}; defaults to assets/ad-patterns.json")

    p = sub.add_parser("sample", help="stratified sample of a video manifest (JSONL)")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("-n", type=int, required=True)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", required=True, type=Path)

    p = sub.add_parser("stats", help="style statistics over cleaned segments (JSONL)")
    p.add_argument("--segments", required=True, type=Path)
    p.add_argument("--stopwords", type=Path)
    p.add_argument("--min-videos", type=int, default=3)
    p.add_argument("--hook-seconds", type=float, default=30.0)
    p.add_argument("--out", required=True, type=Path)

    p = sub.add_parser("ban-check", help="scan text against Never-say rules")
    p.add_argument("text", type=Path)
    p.add_argument("--rules", type=Path, default=ASSETS / "never-say.json")

    p = sub.add_parser("blind-pack", help="build an opaque blind set and a separate key")
    p.add_argument("--items", required=True, type=Path, help="JSONL with {id, label, text}")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out-dir", required=True, type=Path)

    p = sub.add_parser("blind-score", help="score guesses against the blind key")
    p.add_argument("--key", required=True, type=Path)
    p.add_argument("--answers", required=True, type=Path, help="JSONL with {id, guess}")

    args = parser.parse_args(argv)
    if args.cmd == "clean":
        patterns = load_ad_patterns(args.ad_patterns)
        rows = []
        for path in args.captions:
            rows.extend(clean_captions(path.read_text(encoding="utf-8"), patterns, path.stem))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} segments -> {args.out}")
    elif args.cmd == "sample":
        manifest = [json.loads(l) for l in args.manifest.read_text(encoding="utf-8").splitlines() if l.strip()]
        chosen = stratified_sample(manifest, args.n, args.seed)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in chosen), encoding="utf-8")
        print(f"sampled {len(chosen)} of {len(manifest)} -> {args.out}")
    elif args.cmd == "stats":
        segments = [json.loads(l) for l in args.segments.read_text(encoding="utf-8").splitlines() if l.strip()]
        stopwords = set()
        if args.stopwords:
            stopwords = {w.lower() for w in json.loads(args.stopwords.read_text(encoding="utf-8"))}
        result = style_stats(segments, stopwords, args.min_videos, args.hook_seconds)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"stats for {result['videos']} videos -> {args.out}")
    elif args.cmd == "ban-check":
        hits = ban_check(args.text.read_text(encoding="utf-8"), load_rules(args.rules))
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return 1 if hits else 0
    elif args.cmd == "blind-pack":
        items = [json.loads(l) for l in args.items.read_text(encoding="utf-8").splitlines() if l.strip()]
        rng = random.Random(args.seed)
        rng.shuffle(items)
        blind, key = [], {}
        for index, item in enumerate(items, 1):
            opaque = f"item-{index:03d}"
            blind.append({"id": opaque, "text": item["text"]})
            key[opaque] = item["label"]
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "blind.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in blind), encoding="utf-8")
        (args.out_dir / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"blind set of {len(blind)} -> {args.out_dir / 'blind.jsonl'} (key kept separate)")
    elif args.cmd == "blind-score":
        key = json.loads(args.key.read_text(encoding="utf-8"))
        answers = [json.loads(l) for l in args.answers.read_text(encoding="utf-8").splitlines() if l.strip()]
        scored = [a for a in answers if a["id"] in key]
        correct = sum(1 for a in scored if a["guess"] == key[a["id"]])
        n = len(scored)
        report = {"n": n, "correct": correct, "accuracy": round(correct / n, 4) if n else None,
                  "p_value_one_sided": round(binomial_tail(correct, n), 4) if n else None,
                  "missing_or_unknown_ids": len(answers) - n}
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
