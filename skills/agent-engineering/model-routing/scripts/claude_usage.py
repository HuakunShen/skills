#!/usr/bin/env python3
"""Where did Claude Code usage go on one day? Main sessions vs subagents, per project and model.

Reads ~/.claude/projects/**.jsonl (Claude Code session transcripts) and never exports prompts.
Costs are relative "input-token equivalents" using API price ratios that hold for Sonnet and Opus:
input 1, 5-minute cache write 1.25, 1-hour cache write 2, cache read 0.1, output 5. Subscription
quota weighting is not published, so compare shares, not absolute quota.

Newer Claude Code versions write zeros in the top-level usage fields and the real numbers in
usage.iterations; both layouts are handled. One API response can appear in several transcript
entries; responses are de-duplicated by message id.
"""
import argparse
import collections
from datetime import date, datetime, timedelta
import glob
import json
import os
import re

WEIGHTS = {"inp": 1, "w5": 1.25, "w1h": 2, "read": 0.1, "out": 5}
POLL = re.compile(r"\bsleep\b|\buntil\b|\bwait\b")


def usage(message):
    total = collections.Counter()
    raw = message.get("usage") or {}
    for part in raw.get("iterations") or [raw]:
        created = part.get("cache_creation") or {}
        w1h = created.get("ephemeral_1h_input_tokens", 0)
        w5 = part.get("cache_creation_input_tokens", 0) - w1h
        total.update(inp=part.get("input_tokens", 0), w5=max(w5, 0), w1h=w1h,
                     read=part.get("cache_read_input_tokens", 0), out=part.get("output_tokens", 0))
    return total


def cost(tokens):
    return sum(WEIGHTS[k] * tokens[k] for k in WEIGHTS)


def context(tokens):
    return tokens["inp"] + tokens["w5"] + tokens["w1h"] + tokens["read"]


def responses(path, day):
    """Assistant responses of one local day, de-duplicated, in time order."""
    seen = {}
    with open(path, errors="ignore") as stream:
        for line in stream:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "assistant" or not entry.get("timestamp"):
                continue
            when = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).astimezone()
            if when.date() != day:
                continue
            message = entry.get("message") or {}
            if not str(message.get("model", "")).startswith("<") and message.get("id"):
                seen[message["id"]] = (when, message)
    return sorted(seen.values(), key=lambda pair: pair[0])


def analyse(base, day, project_prefix=""):
    groups = collections.defaultdict(collections.Counter)
    calls, contexts, agents = collections.Counter(), collections.defaultdict(list), []
    rewrites = {"events": 0, "tokens": 0, "all_writes": 0, "gaps": []}
    bash = {"total": 0, "poll": 0, "heads": collections.Counter()}
    cutoff = datetime.combine(day, datetime.min.time()).timestamp()
    for path in glob.glob(os.path.join(base, "**", "*.jsonl"), recursive=True):
        if os.path.getmtime(path) < cutoff:
            continue
        project = os.path.relpath(path, base).split(os.sep)[0]
        if project_prefix and project.startswith(project_prefix):
            project = project[len(project_prefix):]
        sub = f"{os.sep}subagents{os.sep}" in path
        meta = {}
        if sub:
            try:
                with open(path[:-len(".jsonl")] + ".meta.json") as stream:
                    meta = json.load(stream)
            except (OSError, ValueError):
                pass
        items = responses(path, day)
        if not items:
            continue
        previous, total, ctxs = None, 0.0, []
        for when, message in items:
            tokens = usage(message)
            key = (project, "sub" if sub else "main", str(message.get("model", "?")).replace("claude-", ""))
            groups[key].update(tokens)
            calls[key] += 1
            contexts[key].append(context(tokens))
            total += cost(tokens)
            ctxs.append(context(tokens))
            if sub:
                written = tokens["w5"] + tokens["w1h"]
                rewrites["all_writes"] += written
                if previous is not None and written > 50000 and written > tokens["read"]:
                    rewrites["events"] += 1
                    rewrites["tokens"] += written
                    rewrites["gaps"].append((when - previous).total_seconds())
                for block in message.get("content") or []:
                    if block.get("type") == "tool_use" and block.get("name") == "Bash":
                        command = (block.get("input") or {}).get("command", "")
                        bash["total"] += 1
                        bash["poll"] += bool(POLL.search(command))
                        stripped = re.sub(r"^((cd|export) [^;&]+(&&|;)\s*)+", "", command.strip())
                        bash["heads"][" ".join(stripped.split()[:2])[:30]] += 1
            previous = when
        if sub:
            agents.append({"project": project, "model": meta.get("model"), "type": meta.get("agentType"),
                           "effort": meta.get("effort"), "description": (meta.get("description") or "")[:60],
                           "calls": len(ctxs), "first_context": ctxs[0], "peak_context": max(ctxs), "cost": total})
    return groups, calls, contexts, agents, rewrites, bash


def median(values):
    values = sorted(values)
    return values[len(values) // 2] if values else 0


def percentile(values, fraction):
    values = sorted(values)
    return values[min(int(len(values) * fraction), len(values) - 1)] if values else 0


def report(base, day, top, prefix):
    groups, calls, contexts, agents, rewrites, bash = analyse(base, day, prefix)
    grand = sum(cost(t) for t in groups.values())
    if not grand:
        print(f"No Claude Code usage found for {day}.")
        return
    print(f"Claude Code usage on {day}: {grand / 1e6:.1f}M input-token equivalents\n")
    print(f"{'project':24} {'kind':4} {'model':12} {'calls':>6} {'share':>6} {'medCtx':>7} {'p90Ctx':>7} | read  w5m  w1h  out")
    for key, tokens in sorted(groups.items(), key=lambda kv: -cost(kv[1])):
        part = cost(tokens)
        if part / grand < 0.005:
            continue
        split = " ".join(f"{100 * WEIGHTS[k] * tokens[k] / part:4.0f}" for k in ("read", "w5", "w1h", "out"))
        print(f"{key[0][:24]:24} {key[1]:4} {key[2][:12]:12} {calls[key]:6} {100 * part / grand:5.1f}% "
              f"{median(contexts[key]) / 1e3:6.0f}k {percentile(contexts[key], 0.9) / 1e3:6.0f}k | {split}")
    totals = collections.Counter()
    for (_, kind, model), tokens in groups.items():
        totals[kind] += cost(tokens)
        totals["model " + model] += cost(tokens)
    print("\n" + "  ".join(f"{name}: {100 * value / grand:.0f}%" for name, value in totals.most_common()))
    if not agents:
        return
    firsts = [a["first_context"] for a in agents]
    turns = [a["calls"] for a in agents]
    print(f"\nSubagents: {len(agents)}; start-up context median {median(firsts) / 1e3:.0f}k "
          f"(min {min(firsts) / 1e3:.0f}k, max {max(firsts) / 1e3:.0f}k); calls each median {median(turns)}, "
          f"p90 {percentile(turns, 0.9)}, max {max(turns)}")
    print("by model:", dict(collections.Counter(a["model"] for a in agents)),
          " by type:", dict(collections.Counter(a["type"] for a in agents)))
    if rewrites["all_writes"]:
        gaps = rewrites["gaps"]
        over = 100 * sum(g > 300 for g in gaps) / len(gaps) if gaps else 0
        print(f"Full cache re-writes after idle: {rewrites['events']} events = "
              f"{100 * rewrites['tokens'] / rewrites['all_writes']:.0f}% of subagent cache writes; "
              f"idle gap median {median(gaps) / 60:.1f} min, {over:.0f}% over 5 min")
    if bash["total"]:
        print(f"Subagent Bash calls: {bash['total']}, {100 * bash['poll'] / bash['total']:.0f}% sleep/until/wait; "
              f"top: {bash['heads'].most_common(8)}")
    agent_total = sum(a["cost"] for a in agents)
    agents.sort(key=lambda a: -a["cost"])
    print(f"\nTop {top} subagents (share of subagent cost):")
    for a in agents[:top]:
        print(f"{100 * a['cost'] / agent_total:5.1f}% {a['project'][:14]:14} {str(a['model']):7} {str(a['effort']):6} "
              f"calls {a['calls']:4} start {a['first_context'] / 1e3:4.0f}k peak {a['peak_context'] / 1e3:4.0f}k  {a['description']}")
    print(f"top {top} = {100 * sum(a['cost'] for a in agents[:top]) / agent_total:.0f}% of subagent cost")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--day", help="Local date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--projects-dir", default="~/.claude/projects")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--strip-prefix", default="", help="Remove this prefix from project folder names")
    args = parser.parse_args()
    day = date.fromisoformat(args.day) if args.day else date.today() - timedelta(days=1)
    report(os.path.expanduser(args.projects_dir), day, args.top, args.strip_prefix)


if __name__ == "__main__":
    main()
