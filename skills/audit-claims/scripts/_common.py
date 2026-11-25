#!/usr/bin/env python3
"""Shared offline utilities for audit-claims scripts (Python 3.9+ stdlib)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from zoneinfo import ZoneInfo

DIFFICULTY_TIERS = ("trivial", "moderate", "hard", "non_consensus")
DIFFICULTY_SCORE_TO_TIER = {1: "trivial", 2: "moderate", 3: "moderate", 4: "hard", 5: "non_consensus"}
HORIZON_BUCKETS = ("le_30d", "31_90d", "91_180d", "181_365d", "gt_365d")

BIDI_CONTROLS = frozenset({
    "\u200e", "\u200f", "\u061c",
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
})
QUOTE_TRANSLATION = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ",
})


def reject_constant(value):
    raise ValueError("Non-finite JSON constant is not supported: " + str(value))


def strict_json(text):
    return json.loads(text, parse_constant=reject_constant)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def atomic_bytes(path, data):
    path = Path(path)
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


def atomic_text(path, text):
    atomic_bytes(path, text.encode("utf-8"))


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def read_json(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = strict_json(line)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid JSON ({exc})") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number}: expected an object")
            rows.append(value)
    return rows


def write_jsonl(path, rows):
    atomic_text(path, "".join(canonical(row) + "\n" for row in rows))


def inside(run, name):
    if not isinstance(name, str) or not name:
        raise ValueError("Missing run-relative file path")
    run_root = Path(run).resolve()
    relative = Path(name)
    target = (run_root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(run_root):
        raise ValueError("Paths must remain inside the run directory")
    return target


@contextmanager
def advisory_lock(directory, filename=".coordinator.lock", busy_message="Another coordinator is writing this run"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / filename).open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError(busy_message) from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError(busy_message) from exc
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def strip_bidi_controls(text):
    removed = sum(1 for ch in text if ch in BIDI_CONTROLS)
    if not removed:
        return text, 0
    return "".join(ch for ch in text if ch not in BIDI_CONTROLS), removed


def normalize_quote_text(text):
    cleaned, _ = strip_bidi_controls(unicodedata.normalize("NFKC", str(text)).translate(QUOTE_TRANSLATION))
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_tz_datetime(value, label):
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{label} datetime requires a UTC offset")
    return parsed


def _timestamp_sort_key(value, zone):
    text = str(value).strip()
    if len(text) == 10:
        dt = datetime.combine(date.fromisoformat(text), time.min, zone)
        return dt.astimezone(timezone.utc)
    return _parse_tz_datetime(text, "timestamp").astimezone(timezone.utc)


def earliest_stated_at(claim, occurrences_by_id=None, sources_by_id=None, tz_name="UTC"):
    for field in ("first_stated_at", "published_at"):
        val = claim.get(field)
        if nonempty(val):
            return val.strip()
    if occurrences_by_id and sources_by_id:
        zone = ZoneInfo(tz_name or "UTC")
        candidates = []
        for oid in claim.get("occurrence_ids") or []:
            occ = occurrences_by_id.get(oid)
            if not isinstance(occ, dict):
                continue
            src = sources_by_id.get(occ.get("source_id"))
            if not isinstance(src, dict):
                continue
            pub = src.get("published_at")
            if nonempty(pub):
                try:
                    candidates.append((_timestamp_sort_key(pub, zone), pub.strip()))
                except ValueError:
                    continue
        if candidates:
            candidates.sort(key=lambda pair: pair[0])
            return candidates[0][1]
    return None


def claim_target_deadline(claim):
    crit = claim.get("criteria")
    if isinstance(crit, dict):
        defn = crit.get("definition")
        if isinstance(defn, dict) and nonempty(defn.get("window_end")):
            return defn["window_end"].strip()
    if nonempty(claim.get("target_date")):
        return claim["target_date"].strip()
    return None


def claim_criteria_timezone(claim, default="UTC"):
    crit = claim.get("criteria")
    if isinstance(crit, dict):
        defn = crit.get("definition")
        if isinstance(defn, dict) and nonempty(defn.get("timezone")):
            return defn["timezone"].strip()
    return default


def check_prediction_temporal_order(stated_at, target_end, tz_name="UTC"):
    """Validate target_end > stated_at for predictions and return (is_valid, lead_time_days, detail).

    When both timestamps carry explicit time+timezone, compares exact UTC instants.
    When either is date-only (YYYY-MM-DD), compares local calendar dates in tz_name
    and requires target_day > stated_day so same-day or retroactive targets are caught.
    """
    if not nonempty(stated_at) or not nonempty(target_end):
        return True, None, None
    stated_str = stated_at.strip()
    target_str = target_end.strip()
    zone = ZoneInfo(tz_name or "UTC")
    stated_is_date = len(stated_str) == 10
    target_is_date = len(target_str) == 10
    if not stated_is_date and not target_is_date:
        stated_dt = _parse_tz_datetime(stated_str, "stated_at")
        target_dt = _parse_tz_datetime(target_str, "target_end")
        delta_days = (target_dt - stated_dt).total_seconds() / 86400.0
        if delta_days <= 0:
            return False, round(delta_days, 2), f"target_date ({target_str}) <= stated_at ({stated_str})"
        return True, round(delta_days, 2), None
    stated_day = date.fromisoformat(stated_str) if stated_is_date else _parse_tz_datetime(stated_str, "stated_at").astimezone(zone).date()
    target_day = date.fromisoformat(target_str) if target_is_date else _parse_tz_datetime(target_str, "target_end").astimezone(zone).date()
    delta_days = float((target_day - stated_day).days)
    if delta_days <= 0:
        return False, delta_days, f"target_date ({target_str}) <= stated_at ({stated_str}) in {tz_name or 'UTC'}"
    return True, delta_days, None


def horizon_bucket_for_days(days):
    if days is None:
        return None
    if days <= 30:
        return "le_30d"
    if days <= 90:
        return "31_90d"
    if days <= 180:
        return "91_180d"
    if days <= 365:
        return "181_365d"
    return "gt_365d"


def resolve_difficulty_tier(claim):
    tier = claim.get("difficulty")
    if tier in DIFFICULTY_TIERS:
        return tier
    score = claim.get("difficulty_score")
    if type(score) is int and score in DIFFICULTY_SCORE_TO_TIER:
        return DIFFICULTY_SCORE_TO_TIER[score]
    return "unrated"
