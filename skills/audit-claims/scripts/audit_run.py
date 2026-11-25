#!/usr/bin/env python3
"""Portable, offline, single-coordinator run ledger for audit-claims (Python 3.9+)."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sys
from zoneinfo import ZoneInfo

import _common as common
import audit_pipeline as pipeline

VERSION = 1
TASK_STATES = {"pending", "running", "completed", "failed", "blocked"}
SOURCE_STATES = {"ready", "pending", "failed", "skipped", "truncated", "segmented"}
LOCATOR_LINE = re.compile(r"^(?:\[#(?:p|cue)-\d{6}[^\]]*\]|<!--\s*audit-claims-locator:\s*\{.*?\}\s*-->)\n?", re.MULTILINE)


def canonical(value):
    return common.canonical(value)


def digest(value):
    return common.digest(value)


def now():
    return common.now()


def atomic_text(path, text):
    common.atomic_text(path, text)


def write_json(path, value):
    common.write_json(path, value)


def read_json(path):
    return common.read_json(path)


def read_jsonl(path):
    return common.read_jsonl(path)


def write_jsonl(path, rows):
    common.write_jsonl(path, rows)


def inside(run, name):
    return common.inside(run, name)


def coordinator_lock(run):
    """OS releases this advisory lock after crashes; no stale PID lock to delete."""
    return common.advisory_lock(run, ".coordinator.lock", "Another coordinator is writing this run")


def _tail_event_sha(events_path):
    if not events_path.exists():
        return None
    size = events_path.stat().st_size
    if size == 0:
        return None
    with events_path.open("rb") as stream:
        if size > 8192:
            stream.seek(size - 8192)
        lines = [line for line in stream.read().splitlines() if line.strip()]
    return hashlib.sha256(lines[-1]).hexdigest() if lines else None


def event(run, kind, **data):
    events_path = Path(run) / "events.jsonl"
    prev_sha = _tail_event_sha(events_path)
    payload = {"at": now(), "event": kind, "prev_sha256": prev_sha, **data}
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(canonical(payload) + "\n")
        stream.flush()
        __import__("os").fsync(stream.fileno())


def as_of_time(value, zone):
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time.max, zone)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Datetime --as-of must include a UTC offset; dates use local end-of-day")
    return parsed.astimezone(zone)


def resolve_as_of_time(value, zone, *, allow_future=False, now_utc=None):
    """Resolve --as-of for init/assess; clamp date-only today to current wall-clock time."""
    now_utc = now_utc or datetime.now(timezone.utc)
    if len(value) == 10:
        target_day = date.fromisoformat(value)
        today_local = now_utc.astimezone(zone).date()
        if target_day > today_local:
            if not allow_future:
                raise ValueError("--as-of cannot be in the future without --allow-future-as-of")
            return datetime.combine(target_day, time.max, zone)
        if target_day == today_local and not allow_future:
            return now_utc.astimezone(zone)
        return datetime.combine(target_day, time.max, zone)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Datetime --as-of must include a UTC offset; dates use local end-of-day")
    if not allow_future and parsed.astimezone(timezone.utc) > now_utc + timedelta(minutes=5):
        raise ValueError("--as-of cannot be in the future without --allow-future-as-of")
    return parsed.astimezone(zone)


def publication_day(value, zone):
    if not isinstance(value, str):
        raise ValueError("Missing publication date")
    if len(value) == 10:
        return date.fromisoformat(value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Publication datetime needs a UTC offset")
    return parsed.astimezone(zone).date()


def estimate_source_tokens(text):
    """Script-aware conservative token bound excluding frontmatter and locator tags."""
    body = text
    if body.startswith("---\n"):
        end = body.find("\n---\n\n", 4)
        if end != -1:
            body = body[end + 6 :]
    body = LOCATOR_LINE.sub("", body)
    raw = body.encode("utf-8")
    ascii_bytes = sum(1 for b in raw if b < 128)
    non_ascii_bytes = len(raw) - ascii_bytes
    return math.ceil(ascii_bytes / 4) + non_ascii_bytes + 128


def config_body(config):
    return {"schema_version": config["schema_version"], "subject": config["subject"],
            "scope": config["scope"], "cutoff_mode": config.get("cutoff_mode", "retrospective"),
            "rules": config.get("rules", {}), "models": config.get("models", {})}


def config(run):
    result = read_json(Path(run) / "run.json")
    if result.get("schema_version") != VERSION or result.get("config_hash") != digest(config_body(result)):
        raise ValueError("run.json scope/config changed or schema unsupported; create a new run")
    return result


def unique(rows, key, label):
    identifiers = [row.get(key) for row in rows]
    if any(not isinstance(value, str) or not value for value in identifiers):
        raise ValueError(f"Every {label} requires a nonempty {key}")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"Duplicate {key} in {label}")
    return {row[key]: row for row in rows}


def inventory(run, cfg):
    rows = read_jsonl(Path(run) / "sources.jsonl")
    unique(rows, "source_id", "sources")
    zone = ZoneInfo(cfg["scope"]["timezone"])
    start, end = date.fromisoformat(cfg["scope"]["start"]), date.fromisoformat(cfg["scope"]["end"])
    cutoff = datetime.fromisoformat(cfg["scope"]["as_of"]).astimezone(zone)
    selected, excluded, snapshot = [], [], []
    for original in sorted(rows, key=lambda row: row["source_id"]):
        row = dict(original)
        sid = row["source_id"]
        reason = None
        actual_hash = None
        try:
            day = publication_day(row.get("published_at"), zone)
            if not start <= day <= end:
                reason = "outside_publication_range"
            elif len(row["published_at"]) > 10 and datetime.fromisoformat(row["published_at"].replace("Z", "+00:00")).astimezone(zone) > cutoff:
                reason = "after_as_of"
            elif len(row["published_at"]) == 10 and day == cutoff.date() and cutoff.timetz().replace(tzinfo=None) != time.max:
                reason = "publication_time_unknown_at_cutoff"
        except (ValueError, TypeError):
            reason = "unknown_publication_date"
        state = row.get("status", "pending")
        if not reason and state not in SOURCE_STATES:
            reason = "unknown_source_status"
        if not reason and state != "ready":
            reason = state
        if not reason:
            try:
                path = inside(run, row.get("content_path"))
                data = path.read_bytes()
                text = data.decode("utf-8")
                if not text.strip():
                    raise ValueError("Empty source")
                actual_hash = hashlib.sha256(data).hexdigest()
                expected = row.get("content_hash")
                if expected and (not isinstance(expected, str) or expected.removeprefix("sha256:") != actual_hash):
                    raise ValueError(f"Content hash mismatch for source {sid}")
                estimate = row.get("estimated_tokens")
                if estimate is None:
                    estimate = estimate_source_tokens(text)
                    method = "script_aware_tokens_plus_128"
                elif isinstance(estimate, bool) or not isinstance(estimate, int) or estimate <= 0:
                    raise ValueError(f"estimated_tokens must be a positive integer for {sid}")
                else:
                    estimate += 128
                    method = "provided_plus_128"
                row.update(content_hash=actual_hash, estimated_tokens=estimate, token_estimation=method)
            except (OSError, UnicodeDecodeError):
                reason = "missing_or_unreadable_content"
            except ValueError as exc:
                if "hash mismatch" in str(exc) or "estimated_tokens" in str(exc):
                    raise
                reason = "invalid_content_path_or_empty"
        snapshot.append({"metadata": original, "actual_content_hash": actual_hash, "exclusion": reason})
        if reason:
            excluded.append({"source_id": sid, "reason": reason})
        else:
            selected.append(row)
    return selected, excluded, digest({"config_hash": cfg["config_hash"], "sources": snapshot})


def summary(run):
    run = Path(run)
    cfg = config(run)
    sources = read_jsonl(run / "sources.jsonl")
    tasks = read_jsonl(run / "tasks.jsonl")
    plan = read_json(run / "plan.json") if (run / "plan.json").exists() else None
    result = {"run_id": cfg["run_id"], "scope": cfg["scope"], "sources": len(sources),
              "source_states": dict(Counter(row.get("status", "pending") for row in sources)),
              "tasks": len(tasks), "task_states": dict(Counter(row.get("status", "unknown") for row in tasks))}
    if plan:
        result["batch_plan"] = {key: plan[key] for key in ("inventory_sources", "in_scope_sources", "eligible_sources", "batched_sources", "excluded", "needs_segmentation", "parameters")}
    return result


def progress(run):
    run = Path(run)
    data = summary(run)
    lines = ["# Claim audit progress", "", f"Updated: {now()}", "", f"Run: `{data['run_id']}`",
             f"Publication range: {data['scope']['start']} through {data['scope']['end']} (inclusive, {data['scope']['timezone']})",
             f"Evidence as-of: {data['scope']['as_of']}", "", "## Counts", "",
             f"- Inventoried sources: {data['sources']}", f"- Source states: {canonical(data['source_states'])}",
             f"- Tasks: {data['tasks']}; states: {canonical(data['task_states'])}"]
    if "batch_plan" in data:
        plan = data["batch_plan"]
        lines += [f"- Batched sources: {plan['batched_sources']} / {plan['eligible_sources']} eligible",
                  f"- Needs segmentation: {len(plan['needs_segmentation'])}", f"- Excluded/unavailable: {len(plan['excluded'])}"]
    lines += ["", "## Resume", "", "1. Read run.json, plan.json, tasks.jsonl and this file.",
              "2. Run validate before resuming; inspect failed, blocked and interrupted running tasks.",
              "3. Reuse completed results. Dispatch pending tasks only after dependencies complete.",
              "4. Workers write private result shards; only the coordinator checkpoints and merges ledgers.",
              "5. Reconcile source coverage and claim counts before scoring. Empty or unfinished work is not success.", ""]
    atomic_text(run / "progress.md", "\n".join(lines))


def init(args):
    run = Path(args.run).resolve()
    zone = ZoneInfo(args.timezone)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    as_of = resolve_as_of_time(args.as_of, zone, allow_future=bool(getattr(args, "allow_future_as_of", False)))
    if start > end or end > as_of.date():
        raise ValueError("Require start <= end <= the local as-of date")
    body = {"schema_version": VERSION, "subject": args.subject,
            "scope": {"start": str(start), "end": str(end), "timezone": args.timezone,
                      "as_of": as_of.astimezone(timezone.utc).isoformat()},
            "cutoff_mode": args.cutoff_mode, "rules": {}, "models": {}}
    with coordinator_lock(run):
        if (run / "run.json").exists():
            cfg = config(run)
            if cfg["config_hash"] != digest(body):
                raise ValueError("Run already exists with another scope; create a different directory")
        else:
            cfg = {**body, "run_id": f"run_{digest(body)[:12]}_{secrets.token_hex(3)}",
                   "config_hash": digest(body), "created_at": now(),
                   "execution": {"mode": "auto", "max_workers": 4}}
            write_json(run / "run.json", cfg)
        for directory in ("sources", "work/batches", "work/results", "reports", "criteria", "history/claims", "reviews/facts", "reviews/decisions", "reviews/reports"):
            (run / directory).mkdir(parents=True, exist_ok=True)
        for name in ("sources.jsonl", "tasks.jsonl", "claims.jsonl", "occurrences.jsonl", "evidence.jsonl", "events.jsonl"):
            if not (run / name).exists():
                atomic_text(run / name, "")
        event(run, "initialized", config_hash=cfg["config_hash"])
        progress(run)
    return summary(run)


def _build_batches(rows, token_budget, max_items):
    batches, current, tokens, oversized = [], [], 0, []
    for row in rows:
        count = row["estimated_tokens"]
        if count > token_budget:
            oversized.append({"source_id": row["source_id"], "estimated_tokens": count, "reason": "needs_segmentation"})
            continue
        if current and (len(current) >= max_items or tokens + count > token_budget):
            batches.append(current)
            current, tokens = [], 0
        current.append(row)
        tokens += count
    if current:
        batches.append(current)
    return batches, oversized


def plan_batches(args):
    if args.token_budget <= 128 or args.max_items <= 0:
        raise ValueError("Use positive --max-items and --token-budget greater than 128")
    run = Path(args.run).resolve()
    append_mode = bool(getattr(args, "append", False))
    with coordinator_lock(run):
        cfg = config(run)
        selected, excluded, fingerprint = inventory(run, cfg)
        if not selected and not excluded:
            raise ValueError("Source inventory is empty; inventory and acquire the corpus before planning")
        parameters = {"input_token_budget": args.token_budget, "max_items": args.max_items}
        old_plan = read_json(run / "plan.json") if (run / "plan.json").exists() else None
        if old_plan and not append_mode and (old_plan["corpus_fingerprint"] != fingerprint or old_plan["parameters"] != parameters):
            raise ValueError("Corpus or batching parameters changed; pass --append for new sources or initialize a new run")
        tasks = read_jsonl(run / "tasks.jsonl")
        existing = unique(tasks, "task_id", "tasks")
        if append_mode and old_plan:
            if old_plan["parameters"] != parameters:
                raise ValueError("Batching parameters cannot change during --append")
            # Preserve existing planned extract tasks and verify their input payloads remain unchanged.
            already_planned_sids = set()
            planned_ids = list(old_plan["task_ids"])
            for tid in planned_ids:
                if tid not in existing:
                    raise ValueError(f"Missing planned task during --append: {tid}")
                check_payload(run, cfg, existing[tid])
                already_planned_sids.update(existing[tid].get("source_ids", []))
            remaining = [row for row in selected if row["source_id"] not in already_planned_sids]
            batches, oversized = _build_batches(remaining, args.token_budget, args.max_items)
            # Retain still-unsegmented oversized items from prior plan if still in selected.
            selected_ids = {r["source_id"] for r in selected}
            prior_oversized = [o for o in old_plan.get("needs_segmentation", []) if o["source_id"] in selected_ids and o["source_id"] not in already_planned_sids]
            oversized = list({o["source_id"]: o for o in prior_oversized + oversized}.values())
            batched_total = len(already_planned_sids) + sum(len(b) for b in batches)
        else:
            batches, oversized = _build_batches(selected, args.token_budget, args.max_items)
            planned_ids = []
            batched_total = sum(len(b) for b in batches)
        for batch in batches:
            input_fp = digest({"config_hash": cfg["config_hash"], "stage": "extract", "sources": batch})
            tid = "extract_" + input_fp[:20]
            planned_ids.append(tid)
            payload_name = f"work/batches/{tid}.json"
            payload = {"schema_version": VERSION, "run_id": cfg["run_id"], "task_id": tid, "stage": "extract",
                       "input_fingerprint": input_fp, "sources": batch}
            payload_path = inside(run, payload_name)
            if payload_path.exists() and read_json(payload_path) != payload:
                raise ValueError(f"Immutable payload changed: {tid}")
            if not payload_path.exists():
                write_json(payload_path, payload)
            if tid not in existing:
                task = {"task_id": tid, "stage": "extract", "batch_id": tid.removeprefix("extract_"),
                        "source_ids": [row["source_id"] for row in batch], "dependencies": [], "status": "pending",
                        "attempts": 0, "payload_path": payload_name, "result_path": None,
                        "input_fingerprint": input_fp,
                        "payload_hash": hashlib.sha256(payload_path.read_bytes()).hexdigest()}
                tasks.append(task)
                existing[tid] = task
            elif existing[tid].get("input_fingerprint") != input_fp:
                raise ValueError(f"Existing task input changed: {tid}")
        if not append_mode:
            stale_extractions = [row["task_id"] for row in tasks if row.get("stage") == "extract" and row["task_id"] not in planned_ids]
            if stale_extractions:
                raise ValueError("Existing extraction tasks do not match this corpus; create a new run")
        plan = {"schema_version": VERSION, "corpus_fingerprint": fingerprint, "parameters": parameters,
                "inventory_sources": len(selected) + len(excluded),
                "in_scope_sources": len(selected) + sum(row["reason"] not in {"outside_publication_range", "unknown_publication_date", "after_as_of", "publication_time_unknown_at_cutoff"} for row in excluded),
                "eligible_sources": len(selected), "batched_sources": batched_total,
                "excluded": excluded, "needs_segmentation": oversized, "task_ids": planned_ids}
        write_jsonl(run / "tasks.jsonl", tasks)
        write_json(run / "plan.json", plan)
        if old_plan != plan:
            event(run, "batches_planned", task_count=len(planned_ids), corpus_fingerprint=fingerprint, append=append_mode)
        progress(run)
    return summary(run)


def check_plan_tasks(run, tasks):
    if not (Path(run) / "plan.json").exists():
        return
    planned = read_json(Path(run) / "plan.json")["task_ids"]
    actual = [task["task_id"] for task in tasks if task.get("stage") == "extract"]
    if len(planned) != len(set(planned)) or set(actual) != set(planned) or len(actual) != len(planned):
        raise ValueError("Extraction tasks do not match immutable plan.task_ids")


def check_payload(run, cfg, task):
    payload_bytes = inside(run, task["payload_path"]).read_bytes()
    payload_hash = task.get("payload_hash")
    if payload_hash is None and task.get("stage") != "extract":
        raise ValueError(f"Non-extraction task needs immutable payload_hash: {task['task_id']}")
    if payload_hash is not None and hashlib.sha256(payload_bytes).hexdigest() != payload_hash:
        raise ValueError(f"Payload hash changed: {task['task_id']}")
    payload = common.strict_json(payload_bytes.decode("utf-8"))
    if payload.get("task_id") != task["task_id"] or payload.get("input_fingerprint") != task.get("input_fingerprint"):
        raise ValueError(f"Payload identity mismatch: {task['task_id']}")
    if task.get("stage") == "extract":
        payload_source_ids = [row["source_id"] for row in payload["sources"]]
        if task.get("source_ids") != payload_source_ids:
            raise ValueError(f"Task source_ids differ from immutable payload: {task['task_id']}")
        if digest({"config_hash": cfg["config_hash"], "stage": "extract", "sources": payload["sources"]}) != task["input_fingerprint"]:
            raise ValueError(f"Payload content changed: {task['task_id']}")
        for row in payload["sources"]:
            actual = hashlib.sha256(inside(run, row["content_path"]).read_bytes()).hexdigest()
            if actual != row["content_hash"]:
                raise ValueError(f"Input content changed: {row['source_id']}")
    return payload


def check_result(run, task, result_name):
    path = inside(run, result_name)
    data = path.read_bytes()
    value = common.strict_json(data.decode("utf-8"))
    if not isinstance(value, dict) or value.get("complete") is not True:
        raise ValueError("Result must be a complete JSON object with complete=true")
    if value.get("task_id") != task["task_id"] or value.get("input_fingerprint") != task.get("input_fingerprint"):
        raise ValueError("Result task_id/input_fingerprint mismatch")
    if task.get("stage") == "extract":
        coverage = value.get("processed_source_ids")
        expected = task.get("source_ids", [])
        if not isinstance(coverage, list) or len(coverage) != len(set(coverage)) or set(coverage) != set(expected):
            raise ValueError("Result does not cover exactly the batch's sources")
        if not isinstance(value.get("claims"), list) or any(not isinstance(row, dict) for row in value["claims"]):
            raise ValueError("Extraction result needs a claims array of objects, possibly empty")
    return hashlib.sha256(data).hexdigest()


def checkpoint(args):
    run = Path(args.run).resolve()
    with coordinator_lock(run):
        cfg = config(run)
        tasks = read_jsonl(run / "tasks.jsonl")
        by_id = unique(tasks, "task_id", "tasks")
        check_plan_tasks(run, tasks)
        if args.task_id not in by_id:
            raise ValueError("Unknown task_id")
        task = by_id[args.task_id]
        before = task["status"]
        if before == "completed" and args.status != "completed":
            raise ValueError("Completed tasks are immutable; create new tasks/runs for revisions")
        if before in {"failed", "blocked"} and args.status == "completed":
            raise ValueError("Transition failed/blocked task to pending or running before completing")
        if args.status in {"running", "completed"}:
            for dependency in task.get("dependencies", []):
                if dependency not in by_id or by_id[dependency]["status"] != "completed":
                    raise ValueError(f"Unfinished dependency: {dependency}")
            check_payload(run, cfg, task)
        if args.status == "completed":
            result_name = args.result or task.get("result_path")
            result_hash = check_result(run, task, result_name)
            if before == "completed" and result_hash != task.get("result_hash"):
                raise ValueError("Completed result changed; preserve old result and create a revision task")
            task.update(result_path=result_name, result_hash=result_hash)
            if task.get("attempts", 0) == 0:
                task["attempts"] = 1
        if args.status == "running" and before != "running":
            task["attempts"] = task.get("attempts", 0) + 1
        task["status"] = args.status
        if args.note:
            task["note"] = args.note
        task["updated_at"] = now()
        write_jsonl(run / "tasks.jsonl", tasks)
        event(run, "checkpoint", task_id=task["task_id"], previous_status=before, status=args.status,
              result_path=task.get("result_path"), note=args.note)
        progress(run)
    return task


def validate(run):
    run = Path(run)
    cfg = config(run)
    selected, excluded, fingerprint = inventory(run, cfg)
    tasks = read_jsonl(run / "tasks.jsonl")
    by_id = unique(tasks, "task_id", "tasks")
    check_plan_tasks(run, tasks)
    warnings = []
    if not selected and not excluded:
        warnings.append("No source inventory exists; this is not a completed audit")
    if selected and not tasks:
        warnings.append("Ready sources have no extraction tasks yet")
    if (run / "plan.json").exists():
        plan = read_json(run / "plan.json")
        if plan["corpus_fingerprint"] != fingerprint:
            raise ValueError("Corpus changed since planning")
        if plan["needs_segmentation"]:
            warnings.append(f"{len(plan['needs_segmentation'])} oversized sources require segmentation")
    remaining = {task["task_id"]: set(task.get("dependencies", [])) for task in tasks}
    finished = set()
    while remaining:
        ready = {task_id for task_id, deps in remaining.items() if deps <= finished}
        if not ready:
            raise ValueError("Task dependencies contain a cycle or missing task")
        finished.update(ready)
        remaining = {task_id: deps for task_id, deps in remaining.items() if task_id not in ready}
    for task in tasks:
        if task.get("status") not in TASK_STATES:
            raise ValueError(f"Unknown task status: {task['task_id']}")
        if any(dependency not in by_id for dependency in task.get("dependencies", [])):
            raise ValueError(f"Missing dependency: {task['task_id']}")
        check_payload(run, cfg, task)
        if task["status"] == "completed":
            if check_result(run, task, task.get("result_path")) != task.get("result_hash"):
                raise ValueError(f"Completed result changed: {task['task_id']}")
    source_rows = read_jsonl(run / "sources.jsonl")
    sources_by_id = {row["source_id"]: row for row in source_rows}
    source_ids = set(sources_by_id)
    occurrences = read_jsonl(run / "occurrences.jsonl") if (run / "occurrences.jsonl").exists() else []
    occ_by_id = unique(occurrences, "occurrence_id", "occurrences")
    occ_ids = set(occ_by_id)
    for occ in occurrences:
        if occ.get("source_id") not in source_ids:
            raise ValueError(f"Occurrence refers to a missing source: {occ['occurrence_id']}")
    claims = read_jsonl(run / "claims.jsonl")
    unique(claims, "claim_id", "claims")
    evidence_ids = {row["evidence_id"] for row in read_jsonl(run / "evidence.jsonl")} if (run / "evidence.jsonl").exists() else set()
    for claim in claims:
        if "source_id" in claim and claim["source_id"] not in source_ids:
            raise ValueError(f"Claim refers to a missing source: {claim['claim_id']}")
        if occ_ids:
            for oid in claim.get("occurrence_ids", []):
                if oid not in occ_ids:
                    raise ValueError(f"Claim {claim['claim_id']} refers to missing occurrence: {oid}")
        if evidence_ids:
            for eid in claim.get("evidence_ids", []):
                if eid not in evidence_ids:
                    raise ValueError(f"Claim {claim['claim_id']} refers to missing evidence: {eid}")
        if claim.get("claim_type") == "prediction":
            stated_at = common.earliest_stated_at(claim, occ_by_id, sources_by_id, cfg["scope"]["timezone"])
            target_end = common.claim_target_deadline(claim)
            if stated_at and target_end:
                ok, _, detail = common.check_prediction_temporal_order(
                    stated_at, target_end, common.claim_criteria_timezone(claim, cfg["scope"]["timezone"])
                )
                if not ok:
                    if claim.get("criteria") is not None or claim.get("accountability_eligible"):
                        raise ValueError(
                            f"Prediction {claim['claim_id']} violates temporal guard ({detail}); reclassify as factual or fix window_end"
                        )
                    warnings.append(
                        f"Temporal guard warning for unfrozen prediction {claim['claim_id']}: {detail}; reclassify as factual before freezing criteria"
                    )
    if excluded:
        warnings.append(f"{len(excluded)} sources are excluded or unavailable; see plan.json")
    if any(task["status"] != "completed" for task in tasks):
        warnings.append("Tasks remain unfinished; integrity validation is not completion")
    return {"valid": True, "warnings": warnings, "sources_ready": len(selected), "claims": len(claims),
            "note": "Checks file/state integrity only; evidence truth and semantic coverage need agent review."}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("init", help="Create an immutable scope and resumable local run")
    create.add_argument("--run", required=True)
    create.add_argument("--subject", required=True)
    create.add_argument("--start", required=True)
    create.add_argument("--end", required=True)
    create.add_argument("--as-of", required=True)
    create.add_argument("--timezone", default="UTC")
    create.add_argument("--cutoff-mode", choices=["retrospective", "knowledge_as_of"], default="retrospective")
    create.add_argument("--allow-future-as-of", action="store_true")
    batches = commands.add_parser("plan-batches", help="Batch the acquired corpus without truncation")
    batches.add_argument("--run", required=True)
    batches.add_argument("--token-budget", type=int, default=40000, help="Usable INPUT tokens after context/output reserves")
    batches.add_argument("--max-items", type=int, default=10)
    batches.add_argument("--append", action="store_true", help="Plan batches only for newly ready sources without invalidating existing tasks")
    check = commands.add_parser("checkpoint", help="Coordinator-only durable task update")
    check.add_argument("--run", required=True)
    check.add_argument("--task-id", required=True)
    check.add_argument("--status", choices=sorted(TASK_STATES), required=True)
    check.add_argument("--result", help="Run-relative path to a worker result JSON envelope")
    check.add_argument("--note")
    for name in ("status", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--run", required=True)
    seg = commands.add_parser("segment", help="Deterministically segment an oversized source at unit boundaries")
    seg.add_argument("--run", required=True)
    seg.add_argument("--source-id", required=True)
    seg.add_argument("--token-budget", type=int, default=40000)
    seg.add_argument("--overlap-units", type=int, default=2)
    bind = commands.add_parser("bind-policy", help="Bind frozen model policy/rules into run.json and recompute config_hash")
    bind.add_argument("--run", required=True)
    bind.add_argument("--model-policy", default="config/model-policy.json")
    bind.add_argument("--rules-json")
    bind.add_argument("--allow-rebind", action="store_true")
    bind.add_argument("--reason")
    freeze = commands.add_parser("freeze-criteria", help="Freeze operational criteria snapshot with server timestamp and hash")
    freeze.add_argument("--run", required=True)
    freeze.add_argument("--claim-id", required=True)
    freeze.add_argument("--definition", required=True)
    freeze.add_argument("--version", default="1")
    freeze.add_argument("--difficulty", choices=list(common.DIFFICULTY_TIERS), help="Optional pre-outcome prediction difficulty tier")
    freeze.add_argument("--difficulty-score", type=int, choices=[1, 2, 3, 4, 5], help="Optional pre-outcome prediction difficulty score (1=trivial..5=non_consensus)")
    freeze.add_argument("--difficulty-rationale", help="Optional pre-outcome rationale explaining baseline/consensus difficulty")
    merge = commands.add_parser("merge-extraction", help="Merge completed extraction shards and verify quotes against sources")
    merge.add_argument("--run", required=True)
    merge.add_argument("--results", nargs="*")
    merge.add_argument("--strict-quotes", action="store_true")
    cov = commands.add_parser("coverage", help="Compute coverage.json deterministically from ledger records")
    cov.add_argument("--run", required=True)
    cov.add_argument("--out", default="coverage.json")
    cov.add_argument("--inventory-incomplete", action="store_true")
    assess = commands.add_parser("assess", help="Start a new assessment round with an updated as-of timestamp")
    assess.add_argument("--run", required=True)
    assess.add_argument("--as-of", required=True)
    assess.add_argument("--reason", default="scheduled_reassessment")
    rep = commands.add_parser("build-report-data", help="Assemble reports/report-data.json from run artifacts")
    rep.add_argument("--run", required=True)
    rep.add_argument("--out", default="reports/report-data.json")
    rep.add_argument("--metrics", default="reports/metrics.json")
    rep.add_argument("--coverage", default="coverage.json")
    rep.add_argument("--rubric", help="Optional custom rubric JSON path (defaults to assets/evaluation-rubric.json)")
    rep.add_argument("--subject-id", help="Filter claims and cases to a single subject_id")
    rep.add_argument("--title")
    rep.add_argument("--synthetic", action="store_true")
    rhash = commands.add_parser("report-hashes", help="Print exact data_hash and rubric_hash required by Phase 7 model reviews before build-report-data")
    rhash.add_argument("--run", required=True)
    rhash.add_argument("--metrics", default="reports/metrics.json")
    rhash.add_argument("--coverage", default="coverage.json")
    rhash.add_argument("--rubric", help="Optional custom rubric JSON path (defaults to assets/evaluation-rubric.json)")
    rhash.add_argument("--subject-id", help="Filter claims to a single subject_id (must match build-report-data)")
    hexp = commands.add_parser("handoff-export", help="Export a self-contained external AI handoff packet")
    hexp.add_argument("--run", required=True)
    hexp.add_argument("--task-ids", nargs="+", required=True)
    hexp.add_argument("--packet-id")
    himp = commands.add_parser("handoff-import", help="Verify and import an external AI handoff result")
    himp.add_argument("--run", required=True)
    himp.add_argument("--packet-id", required=True)
    himp.add_argument("--result-file", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            output = init(args)
        elif args.command == "plan-batches":
            output = plan_batches(args)
        elif args.command == "checkpoint":
            output = checkpoint(args)
        elif args.command == "segment":
            output = pipeline.segment_source(sys.modules[__name__], args.run, args.source_id, args.token_budget, args.overlap_units)
        elif args.command == "bind-policy":
            output = pipeline.bind_policy(sys.modules[__name__], args.run, args.model_policy, args.rules_json, args.allow_rebind, args.reason)
        elif args.command == "freeze-criteria":
            output = pipeline.freeze_criteria(
                sys.modules[__name__], args.run, args.claim_id, args.definition, args.version,
                difficulty=args.difficulty, difficulty_score=args.difficulty_score,
                difficulty_rationale=args.difficulty_rationale,
            )
        elif args.command == "merge-extraction":
            output = pipeline.merge_extraction(sys.modules[__name__], args.run, args.results, args.strict_quotes)
        elif args.command == "coverage":
            output = pipeline.compute_coverage(sys.modules[__name__], args.run, args.out, not args.inventory_incomplete)
        elif args.command == "assess":
            output = pipeline.new_assessment_round(sys.modules[__name__], args.run, args.as_of, args.reason)
        elif args.command == "build-report-data":
            output = pipeline.build_report_data(
                sys.modules[__name__], args.run, args.out, args.metrics, args.coverage,
                args.title, args.synthetic, rubric_path=args.rubric, subject_id=args.subject_id,
            )
        elif args.command == "report-hashes":
            output = pipeline.report_hashes(
                sys.modules[__name__], args.run, args.metrics, args.coverage,
                rubric_path=args.rubric, subject_id=args.subject_id,
            )
        elif args.command == "handoff-export":
            output = pipeline.handoff_export(sys.modules[__name__], args.run, args.task_ids, args.packet_id)
        elif args.command == "handoff-import":
            output = pipeline.handoff_import(sys.modules[__name__], args.run, args.packet_id, args.result_file)
        else:
            run = Path(args.run).resolve()
            with coordinator_lock(run):
                output = validate(run) if args.command == "validate" else summary(run)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
