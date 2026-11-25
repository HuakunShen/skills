#!/usr/bin/env python3
"""Shared offline utilities for audit-claims scripts (Python 3.9+ stdlib)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata

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
