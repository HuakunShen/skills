#!/usr/bin/env python3
"""Bulk, offline text/transcript ingestion with immutable raw copies (Python 3.9+)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import audit_run as ledger

VERSION = 1
FORMATS = {"txt", "md", "srt", "vtt", "json"}
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
TIMING = re.compile(r"^\s*((?:\d+:)?\d{2}:\d{2}(?:[.,]\d{1,3})?)\s+-->\s+((?:\d+:)?\d{2}:\d{2}(?:[.,]\d{1,3})?)(?:\s+.*)?$")


def sha(data):
    return hashlib.sha256(data).hexdigest()


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


def paragraphs(text):
    """Keep original text, including original frontmatter; annotate original line ranges."""
    lines = text.splitlines(keepends=True)
    output, index, counter = [], 0, 0
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
        output.append(marker(location))
        original = "".join(lines[start:index])
        output.append(original)
        if not original.endswith("\n"):
            output.append("\n")
    if not counter:
        raise ValueError("Empty text source")
    return "".join(output), "paragraph", counter


def marker(location):
    encoded = json.dumps(location, ensure_ascii=False, sort_keys=True).replace("-->", "\\u002d\\u002d\\u003e")
    return "<!-- audit-claims-locator: " + encoded + " -->\n"


def cue_body(cues):
    if not cues:
        raise ValueError("Transcript has no nonempty cues")
    output = []
    for index, cue in enumerate(cues, 1):
        location = {"id": f"cue-{index:06d}", "kind": "cue", **{key: value for key, value in cue.items() if key != "text"}}
        output += [marker(location), cue["text"], "\n\n"]
    return "".join(output), "cue", len(cues)


def subtitles(text, fmt):
    lines = text.split("\n")
    blocks, current, start = [], [], 0
    for index, line in enumerate(lines):
        if line.strip():
            if not current:
                start = index + 1
            current.append(line)
        elif current:
            blocks.append((start, current))
            current = []
    if current:
        blocks.append((start, current))
    cues = []
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
        cue_text = "\n".join(block[timing_index + 1:])
        if not cue_text.strip():
            raise ValueError(f"Empty subtitle cue near original line {line_start}")
        start_seconds, end_seconds = seconds(match.group(1)), seconds(match.group(2))
        if end_seconds < start_seconds:
            raise ValueError("Subtitle cue ends before it starts")
        cues.append({"text": cue_text, "original_id": block[0] if timing_index else None,
                     "original_line_start": line_start, "original_line_end": line_start + len(block) - 1,
                     "start_seconds": start_seconds, "end_seconds": end_seconds})
    return cue_body(cues)


def json_transcript(text):
    value = json.loads(text)
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
            if not isinstance(value["segments"], list):
                raise ValueError("Transcript segments must be an array")
            segments, prefix = value["segments"], prefix + ".segments"
        elif isinstance(full_text, str) and full_text.strip():
            return paragraphs(full_text)
        else:
            raise ValueError("Unrecognized/empty transcript JSON; expected text or segments")
    elif isinstance(value, list) and value:
        segments = value
    else:
        raise ValueError("Unrecognized/empty transcript JSON")
    cues = []
    for index, row in enumerate(segments):
        if not isinstance(row, dict) or not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError(f"Transcript segment {index} must contain nonempty text")
        cue = {"text": row["text"], "original_json_path": f"{prefix}[{index}]"}
        if "id" in row:
            cue["original_id"] = row["id"]
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
    if full_text and " ".join(full_text.split()) != " ".join(" ".join(cue["text"] for cue in cues).split()):
        raise ValueError("JSON text disagrees with segments; resolve alignment before normalization")
    return cue_body(cues)


def normalize(record, manifest_dir, run, cfg, max_bytes):
    sid = record.get("source_id")
    if not isinstance(sid, str) or not SAFE_ID.fullmatch(sid):
        raise ValueError("source_id must be 1-128 ASCII letters, digits, underscores or hyphens")
    title, url, published = record.get("title"), record.get("source_url"), record.get("published_at")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"Source {sid} needs a nonempty title")
    if "source_url" not in record or (url is not None and (not isinstance(url, str) or not url.strip())):
        raise ValueError(f"Source {sid} needs source_url (a string or null for local inputs)")
    ledger.publication_day(published, ledger.ZoneInfo(cfg["scope"]["timezone"]))
    path_value = record.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise ValueError(f"Source {sid} needs an input path relative to the manifest")
    path = Path(path_value)
    resolved = (manifest_dir / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(manifest_dir):
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
    language = record.get("language")
    method = record.get("transcript_method", "provided_text" if fmt in {"txt", "md"} else "provided_transcript")
    if language is not None and not (isinstance(language, str) or
            isinstance(language, list) and language and all(isinstance(item, str) and item.strip() for item in language)):
        raise ValueError(f"Source {sid} language must be a string, nonempty list of language strings, or null")
    if not isinstance(method, str) or not method:
        raise ValueError(f"Source {sid} transcript_method must be a nonempty string")
    if fmt in {"txt", "md"}:
        body, locator_kind, locator_count = paragraphs(text)
    elif fmt in {"srt", "vtt"}:
        body, locator_kind, locator_count = subtitles(text, fmt)
    else:
        body, locator_kind, locator_count = json_transcript(text)
    metadata = {"source_id": sid, "title": title, "source_url": url, "published_at": published,
                "language": language, "transcript_method": method, "format": fmt,
                "raw_path": f"raw/{sid}.{fmt}", "raw_hash": sha(data), "normalization_version": VERSION}
    fingerprint = ledger.digest(metadata)
    frontmatter = "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n" for key, value in metadata.items()) + "---\n\n"
    normalized = (frontmatter + body).encode("utf-8")
    row = {**metadata, "status": "ready", "content_path": f"sources/{sid}.md", "content_hash": sha(normalized),
           "normalization_fingerprint": fingerprint, "locator_kind": locator_kind, "locator_count": locator_count}
    return row, data, normalized


def ingest(args):
    run, manifest = Path(args.run).resolve(), Path(args.manifest).resolve()
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
            record = json.loads(line)
        except json.JSONDecodeError as exc:
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
            row, raw, normalized = normalize(record, manifest.parent, run, cfg, args.max_bytes)
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
            prepared.append((row, raw, normalized, unchanged))
        changed = [item for item in prepared if not item[3]]
        if changed and ((run / "plan.json").exists() or ledger.read_jsonl(run / "tasks.jsonl")):
            raise ValueError("Corpus is already planned; do not add/change normalized sources in this run")
        if changed:
            merged = {row["source_id"]: dict(row) for row in existing_rows}
            for row, raw, normalized, unchanged in prepared:
                if unchanged:
                    continue
                for name, content in ((row["raw_path"], raw), (row["content_path"], normalized)):
                    target = ledger.inside(run, name)
                    if not target.exists():
                        # Bytes are UTF-8, but raw BOM/newline bytes must remain exact.
                        atomic_bytes(target, content)
                previous = dict(merged.get(row["source_id"], {}))
                previous.pop("estimated_tokens", None)
                previous.pop("token_estimation", None)
                merged[row["source_id"]] = {**previous, **row}
            ledger.write_jsonl(run / "sources.jsonl", list(merged.values()))
            ledger.event(run, "sources_normalized", source_ids=[item[0]["source_id"] for item in changed])
            ledger.progress(run)
        return {"normalized": len(changed), "unchanged": len(prepared) - len(changed),
                "source_ids": [item[0]["source_id"] for item in prepared],
                "inventory_sources": len(existing_rows) + sum(item[0]["source_id"] not in existing for item in changed),
                "network_calls": 0}


def atomic_bytes(path, data):
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--max-bytes", type=int, default=16 * 1024 * 1024, help="Maximum input/manifest bytes per file")
    parser.add_argument("--max-batch-bytes", type=int, default=256 * 1024 * 1024, help="Maximum combined raw/normalized bytes")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(ingest(args), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
