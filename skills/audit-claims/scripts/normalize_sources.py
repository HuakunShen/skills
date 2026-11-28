#!/usr/bin/env python3
"""Bulk, offline text/transcript ingestion with immutable raw copies (Python 3.9+)."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys

import _common as common
import audit_run as ledger

VERSION = 2
FORMATS = {"txt", "md", "srt", "vtt", "json"}
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
TIMING = re.compile(r"^\s*((?:\d+:)?\d{2}:\d{2}(?:[.,]\d{1,3})?)\s+-->\s+((?:\d+:)?\d{2}:\d{2}(?:[.,]\d{1,3})?)(?:\s+.*)?$")
VTT_INLINE_TAG = re.compile(r"</?(?:c(?:\.[^>\s]+)?|\d{2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?|b|i|u|v(?:\s+[^>]*)?|lang(?:\s+[^>]*)?)>", re.IGNORECASE)
SPOOFED_LOCATOR = re.compile(r"<!--\s*audit-claims-locator:|^\[#(?:p|cue)-\d{6}[^\]]*\]", re.MULTILINE)
STT_NORM_STRIP = re.compile(r"[\s\.,!?，。！？、；;：:…~\-—\"'“”‘’()（）\[\]【】]+")
STT_REPEAT_MIN_RUN = 5
STT_SHORT_CUE_MAX_CHARS = 40


def detect_stt_quality_issues(cues, media_duration_seconds=None):
    """Detect Whisper/STT tail-hallucination loops and duration overflow without dropping raw cues."""
    flags = []
    diagnostics = {}
    if not cues:
        return flags, diagnostics
    repeated_runs = []
    idx = 0
    total = len(cues)
    while idx < total:
        norm = STT_NORM_STRIP.sub("", str(cues[idx].get("text", "")).lower())
        if not norm or len(norm) > STT_SHORT_CUE_MAX_CHARS:
            idx += 1
            continue
        end = idx + 1
        while end < total:
            nxt = STT_NORM_STRIP.sub("", str(cues[end].get("text", "")).lower())
            if nxt != norm:
                break
            end += 1
        run_len = end - idx
        if run_len >= STT_REPEAT_MIN_RUN:
            at_tail = end == total
            entry = {
                "start_index": idx,
                "end_index": end - 1,
                "count": run_len,
                "text": str(cues[idx].get("text", "")).strip(),
                "at_tail": at_tail,
            }
            if "start_seconds" in cues[idx]:
                entry["start_seconds"] = cues[idx]["start_seconds"]
            if "end_seconds" in cues[end - 1]:
                entry["end_seconds"] = cues[end - 1]["end_seconds"]
            repeated_runs.append(entry)
        idx = end
    if repeated_runs:
        diagnostics["repeated_short_cue_runs"] = repeated_runs
        if any(r["at_tail"] for r in repeated_runs):
            flags.append("stt_tail_hallucination")
        if any(not r["at_tail"] for r in repeated_runs):
            flags.append("stt_repeated_cue_hallucination")
    if media_duration_seconds is not None:
        overflow_cues = [
            cue for cue in cues
            if cue.get("end_seconds") is not None and cue["end_seconds"] > media_duration_seconds
        ]
        if overflow_cues:
            max_end = max(cue["end_seconds"] for cue in overflow_cues)
            flags.append("stt_duration_overflow")
            diagnostics["duration_overflow"] = {
                "overflow_cue_count": len(overflow_cues),
                "max_end_seconds": round(max_end, 3),
                "media_duration_seconds": media_duration_seconds,
                "overflow_seconds": round(max_end - media_duration_seconds, 3),
            }
    return flags, diagnostics


def sha(data):
    return common.digest(data) if isinstance(data, dict) else __import__("hashlib").sha256(data).hexdigest()


def finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid nonnegative {label}")
    return value


def seconds(value):
    parts = value.replace(",", ".").split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Invalid cue timestamp")
    second = float(parts[-1])
    minute = int(parts[-2])
    if second >= 60 or (len(parts) == 3 and minute >= 60):
        raise ValueError("Invalid cue timestamp component")
    return round(second + 60 * minute + (3600 * int(parts[0]) if len(parts) == 3 else 0), 6)


def sanitize_body_text(text):
    cleaned, bidi_removed = common.strip_bidi_controls(text)
    escaped = SPOOFED_LOCATOR.sub(lambda m: "[escaped-marker] " + m.group(0).lstrip("<!-#["), cleaned)
    return escaped, bidi_removed


def compact_marker(location):
    lid = location["id"]
    parts = [f"#{lid}"]
    if "start_seconds" in location:
        end = location.get("end_seconds")
        span = f"{location['start_seconds']:.3f}".rstrip("0").rstrip(".")
        if end is not None:
            end_s = f"{end:.3f}".rstrip("0").rstrip(".")
            span = f"{span}-{end_s}"
        parts.append(span + "s")
    if location.get("speaker"):
        speaker = re.sub(r"[\]\s]+", "_", str(location["speaker"]).strip())
        if speaker:
            parts.append("@" + speaker)
    return "[" + " ".join(parts) + "]\n"


def paragraphs(text, locator_mode="compact"):
    """Keep original text, including original frontmatter; emit compact tags + sidecar metadata."""
    lines = text.splitlines(keepends=True)
    output, locators, index, counter = [], [], 0, 0
    while index < len(lines):
        if not lines[index].strip():
            output.append(lines[index])
            index += 1
            continue
        start = index
        kind = "paragraph"
        if start == 0 and lines[0].strip() in {"---", "+++"}:
            delimiter = lines[0].strip()
            closing = next((i for i in range(1, len(lines)) if lines[i].strip() == delimiter), None)
            if closing is not None:
                index = closing + 1
                kind = "original_frontmatter"
            else:
                while index < len(lines) and lines[index].strip():
                    index += 1
        else:
            while index < len(lines) and lines[index].strip():
                index += 1
        counter += 1
        location = {"id": f"p-{counter:06d}", "kind": kind,
                    "original_line_start": start + 1, "original_line_end": index}
        locators.append(location)
        output.append(marker(location) if locator_mode == "inline" else compact_marker(location))
        original = "".join(lines[start:index])
        output.append(original)
        if not original.endswith("\n"):
            output.append("\n")
    if not counter:
        raise ValueError("Empty text source")
    return "".join(output), "paragraph", counter, locators


def marker(location):
    encoded = json.dumps(location, ensure_ascii=False, sort_keys=True).replace("-->", "\\u002d\\u002d\\u003e")
    return "<!-- audit-claims-locator: " + encoded + " -->\n"


def cue_body(cues, locator_mode="compact"):
    if not cues:
        raise ValueError("Transcript has no nonempty cues")
    output, locators = [], []
    for index, cue in enumerate(cues, 1):
        location = {"id": f"cue-{index:06d}", "kind": "cue", **{key: value for key, value in cue.items() if key != "text"}}
        locators.append(location)
        output += [marker(location) if locator_mode == "inline" else compact_marker(location), cue["text"], "\n\n"]
    return "".join(output), "cue", len(cues), locators


def subtitles(text, fmt, locator_mode="compact", clean_youtube_vtt=False):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, current, start = [], [], 0
    for index, line in enumerate(lines):
        # Per WebVTT spec, blocks are separated only by completely empty lines;
        # real YouTube auto-VTT files emit whitespace-only lines (" ") inside cue payloads.
        is_separator = (line == "") if fmt == "vtt" else (not line.strip())
        if is_separator:
            if current:
                blocks.append((start, current))
                current = []
        elif not current and not line.strip():
            continue
        else:
            if not current:
                start = index + 1
            current.append(line)
    if current:
        blocks.append((start, current))
    cues, skipped_empty = [], 0
    prev_raw_lines = []
    if fmt == "vtt" and (not blocks or not blocks[0][1][0].startswith("WEBVTT")):
        raise ValueError("VTT input must have WEBVTT header")
    for block_number, (line_start, block) in enumerate(blocks):
        if fmt == "vtt":
            first = block[0]
            if block_number == 0 and first.startswith("WEBVTT"):
                if any("-->" in line for line in block):
                    raise ValueError("VTT header must be separated from cues by a blank line")
                continue
            if first == "NOTE" or first.startswith("NOTE ") or first.startswith("NOTE\t") or first in {"STYLE", "REGION"}:
                continue
        timing_index = 0 if TIMING.match(block[0]) else 1
        if timing_index >= len(block) or not TIMING.match(block[timing_index]):
            raise ValueError(f"Malformed {fmt.upper()} cue near original line {line_start}")
        match = TIMING.match(block[timing_index])
        payload_lines = block[timing_index + 1:]
        if clean_youtube_vtt:
            cleaned_lines = [VTT_INLINE_TAG.sub("", line).strip() for line in payload_lines]
            cleaned_lines = [line for line in cleaned_lines if line]
            if not cleaned_lines:
                skipped_empty += 1
                continue
        else:
            cleaned_lines = [line for line in payload_lines if line.strip()]
            if not cleaned_lines:
                skipped_empty += 1
                continue
        start_seconds, end_seconds = seconds(match.group(1)), seconds(match.group(2))
        if end_seconds < start_seconds:
            raise ValueError("Subtitle cue ends before it starts")
        emitted_lines = cleaned_lines
        if clean_youtube_vtt and cues and start_seconds <= cues[-1]["end_seconds"] + 1.0:
            overlap = 0
            for k in range(min(len(prev_raw_lines), len(cleaned_lines)), 0, -1):
                if prev_raw_lines[-k:] == cleaned_lines[:k]:
                    overlap = k
                    break
            if overlap == len(cleaned_lines):
                cues[-1]["end_seconds"] = max(cues[-1]["end_seconds"], end_seconds)
                cues[-1].setdefault("collapsed_cue_lines", [cues[-1]["original_line_start"]]).append(line_start)
                prev_raw_lines = cleaned_lines
                continue
            if overlap > 0:
                emitted_lines = cleaned_lines[overlap:]
        cue_text = "\n".join(emitted_lines)
        entry = {"text": cue_text, "original_id": block[0] if timing_index else None,
                 "original_line_start": line_start, "original_line_end": line_start + len(block) - 1,
                 "start_seconds": start_seconds, "end_seconds": end_seconds}
        cues.append(entry)
        prev_raw_lines = cleaned_lines
    body, kind, count, locators = cue_body(cues, locator_mode=locator_mode)
    return body, kind, count, locators, skipped_empty, cues


def json_transcript(text, locator_mode="compact"):
    value = common.strict_json(text)
    prefix = "$"
    if isinstance(value, dict) and "response" in value:
        value = value["response"]
        prefix = "$.response"
    full_text = None
    if isinstance(value, dict):
        full_text = value.get("text")
        if full_text is not None and not isinstance(full_text, str):
            raise ValueError("Transcript text must be a string")
        if value.get("segments") is not None and not isinstance(value["segments"], list):
            raise ValueError("Transcript segments must be an array")
        if "segments" in value and value["segments"]:
            segments, prefix = value["segments"], prefix + ".segments"
        elif isinstance(full_text, str) and full_text.strip():
            body, kind, count, locators = paragraphs(full_text, locator_mode=locator_mode)
            return body, kind, count, locators, 0, []
        else:
            raise ValueError("Unrecognized/empty transcript JSON; expected text or segments")
    elif isinstance(value, list) and value:
        segments = value
    else:
        raise ValueError("Unrecognized/empty transcript JSON")
    cues, skipped_empty = [], 0
    for index, row in enumerate(segments):
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            raise ValueError(f"Transcript segment {index} must contain text")
        if not row["text"].strip():
            skipped_empty += 1
            continue
        cue = {"text": row["text"], "original_json_path": f"{prefix}[{index}]"}
        if "id" in row:
            cue["original_id"] = row["id"]
        speaker = row.get("speaker") or row.get("speaker_id") or row.get("speaker_label")
        if isinstance(speaker, str) and speaker.strip():
            cue["speaker"] = speaker.strip()
        start, end, duration = row.get("start"), row.get("end"), row.get("duration")
        if start is not None:
            cue["start_seconds"] = finite_number(start, "start")
        if end is not None:
            cue["end_seconds"] = finite_number(end, "end")
        if duration is not None:
            duration = finite_number(duration, "duration")
            cue["duration_seconds"] = duration
            if start is not None:
                derived = round(start + duration, 9)
                if end is not None and abs(end - derived) > 0.001:
                    raise ValueError("Transcript segment has inconsistent end/duration")
                if end is None:
                    cue["end_seconds"] = derived
                    cue["end_basis"] = "start_plus_duration"
        if "start_seconds" in cue and "end_seconds" in cue and cue["end_seconds"] < cue["start_seconds"]:
            raise ValueError("Transcript segment ends before it starts")
        cues.append(cue)
    # Compare ignoring all whitespace so CJK text without spaces between segments passes reliably.
    if full_text and "".join(full_text.split()) != "".join("".join(cue["text"].split()) for cue in cues):
        raise ValueError("JSON text disagrees with segments; resolve alignment before normalization")
    body, kind, count, locators = cue_body(cues, locator_mode=locator_mode)
    return body, kind, count, locators, skipped_empty, cues


def source_description(record, sid, manifest_dir):
    """Uploader-written description from the manifest `description` or a yt-dlp `info_json` file.

    Returns (text, origin) or (None, None). Descriptions are written text, not speech, so the caller
    keeps them in a separate paragraph that extraction must cite with its own locator.
    """
    if record.get("description") is not None:
        value, origin = record["description"], "manifest"
    elif record.get("info_json") is not None:
        value, origin = None, "info_json"
        info_path = manifest_path(record["info_json"], sid, manifest_dir, "info_json")
        if not info_path.is_file():
            raise ValueError(f"Source {sid} info_json file is missing")
        if info_path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError(f"Source {sid} info_json exceeds 16 MiB; pass description in the manifest instead")
        info = json.loads(info_path.read_text(encoding="utf-8-sig"))
        if not isinstance(info, dict):
            raise ValueError(f"Source {sid} info_json must contain an object")
        value = info.get("description")
    else:
        return None, None
    if value is None:
        return None, None
    if not isinstance(value, str):
        raise ValueError(f"Source {sid} description must be a string or null")
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return (text or None), origin


def manifest_path(value, sid, manifest_dir, label):
    """Resolve a manifest-relative path; refuse absolute paths and anything outside the manifest directory."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Source {sid} {label} must be a relative path string")
    manifest_root = Path(manifest_dir).resolve()
    path = Path(value)
    resolved = (manifest_root / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(manifest_root):
        raise ValueError(f"Source {sid} {label} must remain under the manifest directory")
    return resolved


def normalize(record, manifest_dir, run, cfg, max_bytes, locator_mode="compact", clean_youtube_vtt=False):
    sid = record.get("source_id")
    if not isinstance(sid, str) or not SAFE_ID.fullmatch(sid):
        raise ValueError("source_id must be 1-128 ASCII letters, digits, underscores or hyphens")
    title, url, published = record.get("title"), record.get("source_url"), record.get("published_at")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"Source {sid} needs a nonempty title")
    if "source_url" not in record or (url is not None and (not isinstance(url, str) or not url.strip())):
        raise ValueError(f"Source {sid} needs source_url (a string or null for local inputs)")
    if published is not None:
        ledger.publication_day(published, ledger.ZoneInfo(cfg["scope"]["timezone"]))
    path_value = record.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise ValueError(f"Source {sid} needs an input path relative to the manifest")
    manifest_root = Path(manifest_dir).resolve()
    path = Path(path_value)
    resolved = (manifest_root / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(manifest_root):
        raise ValueError(f"Source {sid} input path must remain under the manifest directory")
    if not resolved.is_file():
        raise ValueError(f"Source {sid} input file is missing")
    if resolved.stat().st_size > max_bytes:
        raise ValueError(f"Source {sid} exceeds --max-bytes; verify this is text, not audio")
    fmt = record.get("format") or resolved.suffix.lstrip(".").lower()
    fmt = {"markdown": "md", "text": "txt"}.get(fmt, fmt)
    if fmt not in FORMATS:
        raise ValueError(f"Source {sid} format must be txt/md/srt/vtt/json")
    with resolved.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"Source {sid} grew beyond --max-bytes")
    text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text or not text.strip():
        raise ValueError(f"Source {sid} is binary or empty")
    text, bidi_removed = sanitize_body_text(text)
    language = record.get("language")
    method = record.get("transcript_method", "provided_text" if fmt in {"txt", "md"} else "provided_transcript")
    if language is not None and not (isinstance(language, str) or
            isinstance(language, list) and language and all(isinstance(item, str) and item.strip() for item in language)):
        raise ValueError(f"Source {sid} language must be a string, nonempty list of language strings, or null")
    if not isinstance(method, str) or not method:
        raise ValueError(f"Source {sid} transcript_method must be a nonempty string")
    skipped_empty = 0
    cues = []
    if fmt in {"txt", "md"}:
        body, locator_kind, locator_count, locators = paragraphs(text, locator_mode=locator_mode)
    elif fmt in {"srt", "vtt"}:
        body, locator_kind, locator_count, locators, skipped_empty, cues = subtitles(
            text, fmt, locator_mode=locator_mode, clean_youtube_vtt=clean_youtube_vtt)
    else:
        body, locator_kind, locator_count, locators, skipped_empty, cues = json_transcript(text, locator_mode=locator_mode)
    description, description_origin = source_description(record, sid, manifest_dir)
    description_locator = None
    if description:
        description, _ = sanitize_body_text(description)
        # Paragraph-kind locator so extraction can cite it like any paragraph; the heading makes it clear
        # the words were written by the uploader and were not spoken in the video.
        description_locator = {"id": f"p-{locator_count + 1:06d}", "kind": "paragraph",
                               "original_line_start": None, "original_line_end": None, "origin": "video_description"}
        body = (body.rstrip("\n") + "\n\n" + compact_marker(description_locator)
                + "Uploader description (written text, not spoken in the video):\n" + description + "\n")
        locators = list(locators) + [description_locator]
        locator_count += 1
    transcription = record.get("transcription")
    if transcription is not None and not isinstance(transcription, dict):
        raise ValueError(f"Source {sid} transcription metadata must be an object or null")
    media_duration = record.get("media_duration_seconds")
    if media_duration is None and isinstance(transcription, dict):
        media_duration = transcription.get("media_duration_seconds")
    if media_duration is None:
        media_duration = record.get("duration_seconds")
    if media_duration is not None:
        media_duration = finite_number(media_duration, f"media_duration_seconds for {sid}")
    provided_flags = record.get("quality_flags")
    if provided_flags is not None:
        if not isinstance(provided_flags, list) or any(not isinstance(f, str) or not f.strip() for f in provided_flags):
            raise ValueError(f"Source {sid} quality_flags must be a list of nonempty strings or null")
        provided_flags = [f.strip() for f in provided_flags]
    detected_flags, stt_diagnostics = detect_stt_quality_issues(cues, media_duration_seconds=media_duration)
    merged_flags = list(dict.fromkeys((provided_flags or []) + detected_flags))
    speakers_observed = sorted({loc["speaker"] for loc in locators if loc.get("speaker")})
    metadata = {"source_id": sid, "title": title, "source_url": url, "published_at": published,
                "language": language, "transcript_method": method, "format": fmt,
                "raw_path": f"raw/{sid}.{fmt}", "raw_hash": __import__("hashlib").sha256(data).hexdigest(),
                "locator_mode": locator_mode, "normalization_version": VERSION}
    if record.get("speakers") is not None:
        metadata["speakers"] = record["speakers"]
    if speakers_observed:
        metadata["speakers_observed"] = speakers_observed
    if media_duration is not None:
        metadata["media_duration_seconds"] = media_duration
    if transcription is not None:
        metadata["transcription"] = transcription
    if description_locator is not None:
        metadata["description_origin"] = description_origin
        metadata["description_locator_id"] = description_locator["id"]
        metadata["description_sha256"] = __import__("hashlib").sha256(description.encode("utf-8")).hexdigest()
    if merged_flags or provided_flags is not None:
        metadata["quality_flags"] = merged_flags
    fingerprint = ledger.digest(metadata)
    frontmatter = "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n" for key, value in metadata.items()) + "---\n\n"
    normalized = (frontmatter + body).encode("utf-8")
    sidecar_obj = {"schema_version": 1, "source_id": sid, "locator_kind": locator_kind,
                   "locators": locators, "skipped_empty_cues": skipped_empty,
                   "bidi_controls_stripped": bidi_removed}
    if merged_flags:
        sidecar_obj["quality_flags"] = merged_flags
    if stt_diagnostics:
        sidecar_obj["stt_quality_diagnostics"] = stt_diagnostics
    sidecar = json.dumps(sidecar_obj, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    row = {**metadata, "status": "ready", "content_path": f"sources/{sid}.md",
           "locators_path": f"sources/{sid}.locators.json",
           "content_hash": __import__("hashlib").sha256(normalized).hexdigest(),
           "normalization_fingerprint": fingerprint, "locator_kind": locator_kind,
           "locator_count": locator_count, "skipped_empty_cues": skipped_empty,
           "bidi_controls_stripped": bidi_removed, "_locators_bytes": sidecar}
    return row, data, normalized


def ingest(args):
    run, manifest = Path(args.run).resolve(), Path(args.manifest).resolve()
    locator_mode = getattr(args, "locator_mode", "compact")
    clean_youtube_vtt = bool(getattr(args, "clean_youtube_vtt", False))
    allow_append = bool(getattr(args, "append", False))
    if args.max_bytes <= 0 or args.max_batch_bytes <= 0:
        raise ValueError("Size limits must be positive")
    if not manifest.is_file() or manifest.stat().st_size > args.max_bytes:
        raise ValueError("Manifest missing or too large")
    with manifest.open("rb") as stream:
        manifest_bytes = stream.read(args.max_bytes + 1)
    if len(manifest_bytes) > args.max_bytes:
        raise ValueError("Manifest grew beyond --max-bytes")
    records = []
    for number, line in enumerate(manifest_bytes.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = common.strict_json(line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid manifest JSON at line {number}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Manifest line {number} must be an object")
        records.append(record)
    if not records:
        raise ValueError("Manifest is empty")
    ledger.unique(records, "source_id", "manifest")
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        existing_rows = ledger.read_jsonl(run / "sources.jsonl")
        existing = ledger.unique(existing_rows, "source_id", "source inventory")
        prepared, total_bytes = [], 0
        for record in records:
            row, raw, normalized = normalize(
                record, manifest.parent, run, cfg, args.max_bytes,
                locator_mode=locator_mode, clean_youtube_vtt=clean_youtube_vtt)
            locators_bytes = row.pop("_locators_bytes")
            total_bytes += len(raw) + len(normalized)
            if total_bytes > args.max_batch_bytes:
                raise ValueError("Batch exceeds --max-batch-bytes; split the ingestion manifest")
            sid, old = row["source_id"], existing.get(row["source_id"])
            unchanged = old is not None and all(old.get(key) == value for key, value in row.items())
            if old and old.get("status") == "ready" and not unchanged:
                raise ValueError(f"Ready source {sid} differs; preserve originals and use a new run")
            for name, content in ((row["raw_path"], raw), (row["content_path"], normalized)):
                target = ledger.inside(run, name)
                if target.exists():
                    if not target.is_file() or target.read_bytes() != content:
                        raise ValueError(f"Immutable output differs for {sid}; use a new run")
                elif unchanged:
                    raise ValueError(f"Ready source {sid} is missing an immutable output; recover it separately")
            prepared.append((row, raw, normalized, locators_bytes, unchanged))
        changed = [item for item in prepared if not item[4]]
        has_plan = (run / "plan.json").exists() or bool(ledger.read_jsonl(run / "tasks.jsonl"))
        if changed and has_plan and not allow_append:
            raise ValueError("Corpus is already planned; pass --append to add new/pending sources or use a new run")
        if changed:
            merged = {row["source_id"]: dict(row) for row in existing_rows}
            for row, raw, normalized, locators_bytes, unchanged in prepared:
                if unchanged:
                    continue
                for name, content in ((row["raw_path"], raw), (row["content_path"], normalized), (row["locators_path"], locators_bytes)):
                    target = ledger.inside(run, name)
                    if not target.exists():
                        common.atomic_bytes(target, content)
                previous = dict(merged.get(row["source_id"], {}))
                previous.pop("estimated_tokens", None)
                previous.pop("token_estimation", None)
                merged[row["source_id"]] = {**previous, **row}
            ledger.write_jsonl(run / "sources.jsonl", list(merged.values()))
            ledger.event(run, "sources_normalized", source_ids=[item[0]["source_id"] for item in changed], append=allow_append)
            ledger.progress(run)
        flagged = [{"source_id": item[0]["source_id"], "quality_flags": item[0]["quality_flags"]}
                   for item in prepared if item[0].get("quality_flags")]
        res = {"normalized": len(changed), "unchanged": len(prepared) - len(changed),
               "source_ids": [item[0]["source_id"] for item in prepared],
               "inventory_sources": len(existing_rows) + sum(item[0]["source_id"] not in existing for item in changed),
               "network_calls": 0}
        if flagged:
            res["flagged_sources"] = flagged
        return res


def atomic_bytes(path, data):
    common.atomic_bytes(path, data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--max-bytes", type=int, default=16 * 1024 * 1024, help="Maximum input/manifest bytes per file")
    parser.add_argument("--max-batch-bytes", type=int, default=256 * 1024 * 1024, help="Maximum combined raw/normalized bytes")
    parser.add_argument("--locator-mode", choices=["compact", "inline"], default="compact")
    parser.add_argument("--clean-youtube-vtt", action="store_true", help="Strip inline VTT tags and collapse rolling repeats")
    parser.add_argument("--append", action="store_true", help="Allow adding new or previously pending sources after initial planning")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(ingest(args), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
