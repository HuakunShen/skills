#!/usr/bin/env python3
"""Manifest-based OpenAI transcription with estimate approval and resumable files.

Python 3.10+ standard library. Network calls occur only in `run`; there are no
implicit retries. See ../references/transcription.md before using paid APIs.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
MAX_FILE_BYTES = 25_000_000
EXTENSIONS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}


class StopRun(Exception):
    """Safe, user-facing error; never include request headers or provider bodies."""


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(canonical(value) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def append_event(path, event):
    with Path(path).open("ab") as f:
        f.write(canonical(event) + b"\n")
        f.flush()
        os.fsync(f.fileno())


def positive(value, label, allow_zero=False):
    if isinstance(value, bool):
        raise StopRun(f"{label} must be a finite number")
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise StopRun(f"{label} must be a finite number") from None
    if not math.isfinite(result) or result < 0 or (result == 0 and not allow_zero):
        raise StopRun(f"{label} must be {'nonnegative' if allow_zero else 'positive'} and finite")
    return result


def probe_duration(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise StopRun("Unknown duration: supply duration_seconds or install ffprobe and use --probe-duration") from None
    return positive(result.stdout.strip(), "ffprobe duration")


def request_fields(model, response_format, language_field, languages, timestamps):
    fields = [("model", model), ("response_format", response_format)]
    if response_format == "verbose_json" and model != "whisper-1":
        raise StopRun("This sample supports verbose_json/timestamps only for whisper-1; check current model docs")
    if timestamps and (model != "whisper-1" or response_format != "verbose_json"):
        raise StopRun("Timestamps require whisper-1 with --response-format verbose_json in this sample")
    if language_field == "auto":
        if model == "gpt-transcribe" or model.startswith("gpt-transcribe-"):
            language_field = "languages[]"
        elif model == "whisper-1" or model.startswith(("gpt-4o-transcribe", "gpt-4o-mini-transcribe")):
            language_field = "language"
        else:
            raise StopRun("Unknown model language field; verify its docs and pass --language-field explicitly")
    if language_field == "language" and len(languages) > 1:
        raise StopRun("This model accepts one language hint; omit hints for mixed-language audio or choose a compatible model")
    fields.extend((language_field, language) for language in languages)
    fields.extend(("timestamp_granularities[]", item) for item in timestamps)
    if model == "gpt-4o-transcribe-diarize":
        fields.append(("chunking_strategy", "auto"))
    return fields


def load_items(manifest, model, response_format="json", language_field="auto", timestamps=(), probe=False):
    manifest = Path(manifest).resolve()
    rows, ids, request_keys = [], set(), {}
    with manifest.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                item_id, raw_path = row["id"], row["path"]
            except (json.JSONDecodeError, KeyError, TypeError):
                raise StopRun(f"Invalid manifest record at line {line_number}") from None
            if not isinstance(item_id, str) or not item_id.strip() or item_id in ids:
                raise StopRun(f"Missing/duplicate id at line {line_number}")
            ids.add(item_id)
            if not isinstance(raw_path, str):
                raise StopRun(f"Invalid path at line {line_number}")
            path = (manifest.parent / raw_path).resolve()
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                raise StopRun(f"Missing file or unsupported audio extension at line {line_number}")
            size = path.stat().st_size
            if size <= 0 or size > MAX_FILE_BYTES:
                raise StopRun(f"File at line {line_number} is empty or exceeds 25,000,000 bytes; split/compress it before estimating")
            duration = probe_duration(path) if probe else positive(row.get("duration_seconds"), "duration_seconds")
            languages = row.get("language") or []
            if isinstance(languages, str):
                languages = [languages]
            if not isinstance(languages, list) or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,3})?", x) for x in languages):
                raise StopRun(f"Invalid language hint at line {line_number}")
            fields = request_fields(model, response_format, language_field, languages, timestamps)
            sha = file_sha(path)
            key = digest({"audio_sha256": sha, "fields": fields})
            if key in request_keys:
                previous = request_keys[key]
                if abs(previous["duration_seconds"] - duration) > 0.01:
                    raise StopRun("Identical audio has inconsistent durations; correct the manifest")
                previous["aliases"].append(item_id)
                continue
            item = {"id": item_id, "aliases": [], "path": str(path), "size_bytes": size,
                    "sha256": sha, "duration_seconds": duration, "duration_source": "ffprobe" if probe else "manifest",
                    "language": languages, "source_url": row.get("source_url"), "request_fields": fields, "request_key": key}
            rows.append(item)
            request_keys[key] = item
    if not rows:
        raise StopRun("Manifest contains no audio records")
    return rows


def make_estimate(args):
    rate = positive(args.usd_per_minute, "usd_per_minute")
    budget = None if args.budget_usd is None else positive(args.budget_usd, "budget_usd")
    margin = positive(args.safety_multiplier, "safety_multiplier")
    if margin < 1:
        raise StopRun("safety_multiplier must be at least 1")
    try:
        checked = dt.date.fromisoformat(args.price_checked_at)
    except ValueError:
        raise StopRun("price_checked_at must use YYYY-MM-DD") from None
    if checked > dt.datetime.now(dt.timezone.utc).date():
        raise StopRun("price_checked_at cannot be in the future")
    if not args.price_source.strip():
        raise StopRun("Record the verified pricing source")
    valid_hours = positive(args.valid_hours, "valid_hours")
    if (dt.datetime.now(dt.timezone.utc).date() - checked).days > 7:
        raise StopRun("Pricing check is older than 7 days; verify the rate again")
    manifest = Path(args.manifest).resolve()
    items = load_items(manifest, args.model, args.response_format, args.language_field, args.timestamps, args.probe_duration)
    total = sum(x["duration_seconds"] for x in items) / 60 * rate
    plan = {"schema_version": 1, "created_at": now(),
            "valid_until": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=valid_hours)).isoformat(), "manifest_path": str(manifest),
            "manifest_sha256": file_sha(manifest), "model": args.model,
            "response_format": args.response_format, "usd_per_minute": rate,
            "price_source": args.price_source, "price_checked_at": args.price_checked_at,
            "budget_usd": budget, "safety_multiplier": margin,
            "deviation_fraction": positive(args.deviation_fraction, "deviation_fraction"),
            "deviation_floor_usd": positive(args.deviation_floor_usd, "deviation_floor_usd", True),
            "estimated_usd": total, "estimated_upper_usd": total * margin,
            "actual_usd": None, "items": items}
    envelope = {"estimate_id": digest(plan), "plan": plan}
    atomic_json(args.output, envelope)
    print(json.dumps({"estimate_file": str(Path(args.output).resolve()), "estimate_id": envelope["estimate_id"],
                      "unique_requests": len(items), "minutes": sum(i["duration_seconds"] for i in items) / 60,
                      "estimated_usd": total, "estimated_upper_usd": total * margin,
                      "budget_usd": budget, "network_calls": 0}, ensure_ascii=False))
    return envelope


@contextlib.contextmanager
def run_lock(state_dir):
    lock = state_dir / ".run.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise StopRun("State directory is locked. Check for a running process; only remove a stale .run.lock after confirming it stopped") from None
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"pid": os.getpid(), "started_at": now()}))
        yield
    finally:
        lock.unlink(missing_ok=True)


def multipart(item):
    boundary = "auditclaims-" + uuid.uuid4().hex
    blocks = []
    for key, value in item["request_fields"]:
        blocks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n".encode(), value.encode("utf-8"), b"\r\n"])
    path = Path(item["path"])
    # Use a generated ASCII name; paths and untrusted filenames never become headers.
    filename = "audio" + path.suffix.lower()
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    blocks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode(), path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()])
    return b"".join(blocks), "multipart/form-data; boundary=" + boundary


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StopRun("Unexpected redirect; stopped without forwarding credentials")


def call_openai(item, api_key, timeout):
    body, content_type = multipart(item)
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + api_key, "Content-Type": content_type,
        "User-Agent": "audit-claims-transcribe/1"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024:
                raise StopRun("Response exceeds local size limit; inspect request before retrying")
            result = json.loads(raw.decode("utf-8"))
            request_id = response.headers.get("x-request-id")
    except urllib.error.HTTPError as error:
        raise StopRun(f"HTTP {error.code}; no automatic retry. Inspect provider usage before reconciling this request") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise StopRun("Network/response failure; billing outcome unknown. No automatic retry") from None
    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise StopRun("Unexpected response schema; billing outcome unknown. No automatic retry")
    return result, request_id


def snapshot(plan, states):
    complete = [i for i in plan["items"] if states.get(i["request_key"], {}).get("status") == "succeeded"]
    complete_seconds = sum(i["duration_seconds"] for i in complete)
    measured_seconds = sum(states[i["request_key"]]["cost_duration_seconds"] for i in complete)
    ratio = max(1.0, measured_seconds / complete_seconds) if complete_seconds else 1.0
    estimated_spent = sum(states[i["request_key"]]["estimated_usd"] for i in complete)
    remaining = [i for i in plan["items"] if i not in complete]
    estimated_remaining = sum(i["duration_seconds"] for i in remaining) / 60 * plan["usd_per_minute"] * ratio
    projection = estimated_spent + estimated_remaining
    return {"completed": len(complete), "remaining": len(remaining), "estimated_spent_usd": estimated_spent,
            "estimated_remaining_usd": estimated_remaining, "projected_usd": projection,
            "projected_upper_usd": projection * plan["safety_multiplier"], "actual_usd": None,
            "billing_verified": False, "observed_duration_multiplier": ratio}


def check_cost(plan, summary, waiver):
    warning = None
    over_budget = plan["budget_usd"] is not None and summary["projected_upper_usd"] > plan["budget_usd"]
    if over_budget:
        warning = "Projected cost including safety margin exceeds approved budget"
    threshold = max(plan["estimated_usd"] * plan["deviation_fraction"], plan["deviation_floor_usd"])
    if summary["projected_usd"] - plan["estimated_usd"] > threshold:
        warning = "Projected cost materially deviates from the initial estimate"
    if warning:
        print(json.dumps({"warning": warning, "cost_waiver": waiver, **summary}), file=sys.stderr)
        if over_budget or not waiver:
            raise StopRun(warning + "; obtain revised approval before further paid requests")


def check_freshness(plan):
    if dt.datetime.fromisoformat(plan["valid_until"]) <= dt.datetime.now(dt.timezone.utc):
        raise StopRun("Estimate expired; refresh prices and estimate. Reuse existing authorization when its scope and budget still cover the work")
    if (dt.datetime.now(dt.timezone.utc).date() - dt.date.fromisoformat(plan["price_checked_at"])).days > 7:
        raise StopRun("Pricing check is stale; verify the rate and re-estimate within the existing authorization")


def execute(args, transport=None):
    envelope = read_json(args.approve_estimate or args.cost_waiver)
    plan = envelope["plan"]
    if envelope.get("estimate_id") != digest(plan):
        raise StopRun("Estimate hash does not match; regenerate and verify coverage by the user's authorization")
    if not args.approval_note.strip():
        raise StopRun("Record the user's actual approval or explicit cost waiver in --approval-note")
    waiver = bool(args.cost_waiver)
    if not waiver and plan["budget_usd"] is None:
        raise StopRun("Approved estimate needs a budget_usd; regenerate with --budget-usd")
    if file_sha(plan["manifest_path"]) != plan["manifest_sha256"]:
        raise StopRun("Manifest changed since estimate; re-estimate and check the existing authorization scope")
    for item in plan["items"]:
        p = Path(item["path"])
        if p.stat().st_size != item["size_bytes"] or file_sha(p) != item["sha256"]:
            raise StopRun("Audio changed since estimate; re-estimate and check the existing authorization scope")
    state_dir = Path(args.state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "items").mkdir(exist_ok=True)
    (state_dir / "responses").mkdir(exist_ok=True)
    with run_lock(state_dir):
        event_path = state_dir / "events.jsonl"
        append_event(event_path, {"type": "approval", "at": now(), "estimate_id": envelope["estimate_id"], "mode": "waiver" if waiver else "approved_estimate", "note": args.approval_note})
        states = {}
        for item in plan["items"]:
            key = item["request_key"]
            path = state_dir / "items" / (key + ".json")
            if path.exists():
                state = read_json(path)
                if state.get("request_key") != key:
                    raise StopRun("State request identity mismatch; inspect state before resuming")
                # A complete response written before a crash is recoverable without another API call.
                response_path = state_dir / "responses" / (key + ".json")
                if state["status"] != "succeeded" and response_path.exists():
                    response_saved = read_json(response_path)
                    if response_saved.get("request_key") != key:
                        raise StopRun("Saved response identity mismatch; inspect before resuming")
                    state = success_state(item, plan, response_saved["response"], response_saved.get("request_id"))
                    atomic_json(path, state)
                if state["status"] != "succeeded":
                    raise StopRun("An earlier request is incomplete/uncertain. Reconcile provider usage and local responses before any retry")
                if not response_path.exists() or file_sha(response_path) != state.get("response_sha256"):
                    # Reconstructed state receives its hash here; do not resend paid calls for a missing artifact.
                    if response_path.exists() and "response_sha256" not in state:
                        state["response_sha256"] = file_sha(response_path)
                        atomic_json(path, state)
                    else:
                        raise StopRun("A completed response is missing or changed; restore it instead of retranscribing")
                states[key] = state
        summary = snapshot(plan, states)
        check_cost(plan, summary, waiver)
        if summary["remaining"]:
            check_freshness(plan)
        if summary["remaining"] and transport is None and not os.environ.get("OPENAI_API_KEY"):
            raise StopRun("Set OPENAI_API_KEY in the environment; do not paste it into task files")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        for item in plan["items"]:
            key = item["request_key"]
            if key in states:
                continue
            check_cost(plan, snapshot(plan, states), waiver)
            check_freshness(plan)
            # Recheck immediately before upload so an intervening edit cannot invalidate approval.
            if file_sha(item["path"]) != item["sha256"]:
                raise StopRun("Audio changed before upload; re-estimate and check the existing authorization scope")
            path = state_dir / "items" / (key + ".json")
            submitting = {"status": "submitting", "at": now(), "request_key": key, "id": item["id"],
                          "estimate_id": envelope["estimate_id"], "reserved_estimate_usd": item["duration_seconds"] / 60 * plan["usd_per_minute"], "actual_usd": None}
            atomic_json(path, submitting)
            append_event(event_path, {"type": "request_started", **submitting})
            try:
                response, request_id = (transport or call_openai)(item, api_key, args.timeout)
                if not isinstance(response, dict) or not isinstance(response.get("text"), str):
                    raise StopRun("Unexpected response; inspect before any retry")
                response_path = state_dir / "responses" / (key + ".json")
                atomic_json(response_path, {"response": response, "request_id": request_id, "request_key": key, "saved_at": now()})
                state = success_state(item, plan, response, request_id)
                state["response_sha256"] = file_sha(response_path)
                atomic_json(path, state)
                states[key] = state
                append_event(event_path, {"type": "request_completed", **state})
            except BaseException:
                # Includes interruption. Do not expose exception bodies/headers or retry automatically.
                atomic_json(path, {**submitting, "status": "uncertain", "at": now()})
                append_event(event_path, {"type": "request_uncertain", "request_key": key, "at": now(), "actual_usd": None})
                atomic_json(state_dir / "cost-summary.json", {"estimate_id": envelope["estimate_id"], "updated_at": now(),
                    **snapshot(plan, states), "uncertain_request_key": key,
                    "uncertain_reserved_estimate_usd": submitting["reserved_estimate_usd"], "action": "reconcile_before_retry"})
                raise
            summary = snapshot(plan, states)
            atomic_json(state_dir / "cost-summary.json", {"estimate_id": envelope["estimate_id"], "updated_at": now(), **summary})
            print(json.dumps({"id": item["id"], **summary}, ensure_ascii=False))
            check_cost(plan, summary, waiver)
        summary = snapshot(plan, states)
        atomic_json(state_dir / "cost-summary.json", {"estimate_id": envelope["estimate_id"], "updated_at": now(), **summary})
        return summary


def success_state(item, plan, response, request_id):
    usage = response.get("usage") or {}
    seconds = item["duration_seconds"]
    basis = "manifest_duration"
    if isinstance(usage, dict) and usage.get("type") == "duration" and usage.get("seconds") is not None:
        seconds = positive(usage["seconds"], "provider duration", True)
        basis = "provider_usage_duration"
    return {"status": "succeeded", "at": now(), "request_key": item["request_key"], "id": item["id"],
            "aliases": item["aliases"], "request_id": request_id, "provider_usage": usage,
            "cost_duration_seconds": seconds, "estimated_usd": seconds / 60 * plan["usd_per_minute"],
            "cost_basis": basis, "actual_usd": None}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    estimate = sub.add_parser("estimate", help="Validate files and write a cost plan; makes no API calls")
    estimate.add_argument("--manifest", required=True)
    estimate.add_argument("--model", required=True)
    estimate.add_argument("--usd-per-minute", type=float, required=True)
    estimate.add_argument("--price-source", required=True)
    estimate.add_argument("--price-checked-at", required=True)
    estimate.add_argument("--budget-usd", type=float)
    estimate.add_argument("--output", required=True)
    estimate.add_argument("--valid-hours", type=float, default=24.0, help="Estimate validity; default 24 hours")
    estimate.add_argument("--response-format", choices=["json", "verbose_json"], default="json")
    estimate.add_argument("--language-field", choices=["auto", "language", "languages[]"], default="auto")
    estimate.add_argument("--timestamps", nargs="*", choices=["word", "segment"], default=[])
    estimate.add_argument("--probe-duration", action="store_true", help="Use ffprobe for every file instead of trusting manifest durations")
    estimate.add_argument("--safety-multiplier", type=float, default=1.3)
    estimate.add_argument("--deviation-fraction", type=float, default=0.25)
    estimate.add_argument("--deviation-floor-usd", type=float, default=1.0)
    run = sub.add_parser("run", help="Run only after actual user approval; resume uses the SAME state directory")
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--approve-estimate", metavar="FILE", help="Approved estimate JSON; user must have reviewed its cost and budget")
    mode.add_argument("--cost-waiver", metavar="FILE", help="Estimate JSON; use ONLY after an explicit user waiver of cost limits")
    run.add_argument("--approval-note", required=True)
    run.add_argument("--state-dir", required=True)
    run.add_argument("--timeout", type=float, default=180.0)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "estimate":
            make_estimate(args)
        else:
            positive(args.timeout, "timeout")
            execute(args)
    except StopRun as error:
        print("STOP: " + str(error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("STOP: Interrupted; inspect persisted state before resuming", file=sys.stderr)
        return 130
    except Exception:
        print("STOP: Local operation failed; inspect files and state. No automatic retry. Sensitive error details suppressed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
