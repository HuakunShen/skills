#!/usr/bin/env python3
"""Portable, offline, single-coordinator run ledger for audit-claims (Python 3.9+)."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo

VERSION = 1
TASK_STATES = {"pending", "running", "completed", "failed", "blocked"}
SOURCE_STATES = {"ready", "pending", "failed", "skipped", "truncated"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number}: expected an object")
            rows.append(value)
    return rows


def write_jsonl(path, rows):
    atomic_text(path, "".join(canonical(row) + "\n" for row in rows))


def inside(run, name):
    if not isinstance(name, str) or not name:
        raise ValueError("Missing run-relative file path")
    relative = Path(name)
    target = (run / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(run.resolve()):
        raise ValueError("Paths must remain inside the run directory")
    return target


@contextmanager
def coordinator_lock(run):
    """OS releases this advisory lock after crashes; no stale PID lock to delete."""
    run.mkdir(parents=True, exist_ok=True)
    handle = (run / ".coordinator.lock").open("a+b")
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
                raise ValueError("Another coordinator is writing this run") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Another coordinator is writing this run") from exc
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


def event(run, kind, **data):
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(canonical({"at": now(), "event": kind, **data}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def as_of_time(value, zone):
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time.max, zone)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Datetime --as-of must include a UTC offset; dates use local end-of-day")
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


def config_body(config):
    return {"schema_version": config["schema_version"], "subject": config["subject"],
            "scope": config["scope"], "cutoff_mode": config.get("cutoff_mode", "retrospective"),
            "rules": config.get("rules", {}), "models": config.get("models", {})}


def config(run):
    result = read_json(run / "run.json")
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
    rows = read_jsonl(run / "sources.jsonl")
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
                    # UTF-8 byte count is intentionally conservative for CJK/mixed text.
                    estimate = len(data) + 128
                    method = "utf8_bytes_plus_128"
                elif isinstance(estimate, bool) or not isinstance(estimate, int) or estimate <= 0:
                    raise ValueError(f"estimated_tokens must be a positive integer for {sid}")
                else:
                    estimate += 128
                    method = "provided_plus_128"
                row.update(content_hash=actual_hash, estimated_tokens=estimate, token_estimation=method)
            except (OSError, UnicodeDecodeError) as exc:
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
    as_of = as_of_time(args.as_of, zone)
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
            cfg = {**body, "run_id": "run_" + digest(body)[:16], "config_hash": digest(body), "created_at": now(),
                   "execution": {"mode": "auto", "max_workers": 4}}
            write_json(run / "run.json", cfg)
        for directory in ("sources", "work/batches", "work/results", "reports"):
            (run / directory).mkdir(parents=True, exist_ok=True)
        for name in ("sources.jsonl", "tasks.jsonl", "claims.jsonl", "evidence.jsonl", "events.jsonl"):
            if not (run / name).exists():
                atomic_text(run / name, "")
        event(run, "initialized", config_hash=cfg["config_hash"])
        progress(run)
    return summary(run)


def plan_batches(args):
    if args.token_budget <= 128 or args.max_items <= 0:
        raise ValueError("Use positive --max-items and --token-budget greater than 128")
    run = Path(args.run).resolve()
    with coordinator_lock(run):
        cfg = config(run)
        selected, excluded, fingerprint = inventory(run, cfg)
        if not selected and not excluded:
            raise ValueError("Source inventory is empty; inventory and acquire the corpus before planning")
        parameters = {"input_token_budget": args.token_budget, "max_items": args.max_items}
        old_plan = read_json(run / "plan.json") if (run / "plan.json").exists() else None
        if old_plan and (old_plan["corpus_fingerprint"] != fingerprint or old_plan["parameters"] != parameters):
            raise ValueError("Corpus or batching parameters changed; preserve this run and initialize a new run")
        batches, current, tokens, oversized = [], [], 0, []
        for row in selected:
            count = row["estimated_tokens"]
            if count > args.token_budget:
                oversized.append({"source_id": row["source_id"], "estimated_tokens": count, "reason": "needs_segmentation"})
                continue
            if current and (len(current) >= args.max_items or tokens + count > args.token_budget):
                batches.append(current)
                current, tokens = [], 0
            current.append(row)
            tokens += count
        if current:
            batches.append(current)
        tasks = read_jsonl(run / "tasks.jsonl")
        existing = unique(tasks, "task_id", "tasks")
        planned_ids = []
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
            elif existing[tid].get("input_fingerprint") != input_fp:
                raise ValueError(f"Existing task input changed: {tid}")
        stale_extractions = [row["task_id"] for row in tasks if row.get("stage") == "extract" and row["task_id"] not in planned_ids]
        if stale_extractions:
            raise ValueError("Existing extraction tasks do not match this corpus; create a new run")
        plan = {"schema_version": VERSION, "corpus_fingerprint": fingerprint, "parameters": parameters,
                "inventory_sources": len(selected) + len(excluded),
                "in_scope_sources": len(selected) + sum(row["reason"] not in {"outside_publication_range", "unknown_publication_date", "after_as_of", "publication_time_unknown_at_cutoff"} for row in excluded),
                "eligible_sources": len(selected), "batched_sources": sum(len(batch) for batch in batches),
                "excluded": excluded, "needs_segmentation": oversized, "task_ids": planned_ids}
        write_jsonl(run / "tasks.jsonl", tasks)
        write_json(run / "plan.json", plan)
        if old_plan != plan:
            event(run, "batches_planned", task_count=len(planned_ids), corpus_fingerprint=fingerprint)
        progress(run)
    return summary(run)


def check_plan_tasks(run, tasks):
    if not (run / "plan.json").exists():
        return
    planned = read_json(run / "plan.json")["task_ids"]
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
    payload = json.loads(payload_bytes)
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
    value = json.loads(data)
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
        if (run / "plan.json").exists():
            _, _, fingerprint = inventory(run, cfg)
            if fingerprint != read_json(run / "plan.json")["corpus_fingerprint"]:
                raise ValueError("Corpus changed since planning; do not reuse this checkpoint")
        tasks = read_jsonl(run / "tasks.jsonl")
        by_id = unique(tasks, "task_id", "tasks")
        check_plan_tasks(run, tasks)
        if args.task_id not in by_id:
            raise ValueError("Unknown task_id")
        task = by_id[args.task_id]
        before = task["status"]
        if before == "completed" and args.status != "completed":
            raise ValueError("Completed tasks are immutable; create new tasks/runs for revisions")
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
    claims = read_jsonl(run / "claims.jsonl")
    unique(claims, "claim_id", "claims")
    source_ids = {row["source_id"] for row in read_jsonl(run / "sources.jsonl")}
    for claim in claims:
        if "source_id" in claim and claim["source_id"] not in source_ids:
            raise ValueError(f"Claim refers to a missing source: {claim['claim_id']}")
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
    batches = commands.add_parser("plan-batches", help="Batch the fully acquired corpus, never silently truncate")
    batches.add_argument("--run", required=True)
    batches.add_argument("--token-budget", type=int, default=40000, help="Usable INPUT tokens after context/output reserves")
    batches.add_argument("--max-items", type=int, default=10)
    check = commands.add_parser("checkpoint", help="Coordinator-only durable task update")
    check.add_argument("--run", required=True)
    check.add_argument("--task-id", required=True)
    check.add_argument("--status", choices=sorted(TASK_STATES), required=True)
    check.add_argument("--result", help="Run-relative path to a worker result JSON envelope")
    check.add_argument("--note")
    for name in ("status", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--run", required=True)
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
