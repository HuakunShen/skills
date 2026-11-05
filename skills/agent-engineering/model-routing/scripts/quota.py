#!/usr/bin/env python3
"""Query live subscription quota across agent harnesses (Antigravity agy, Codex, Claude Code).
Python standard library only.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def parse_iso_or_timestamp(val):
    """Normalize integer unix timestamp or ISO string to ISO 8601 UTC string."""
    if not val:
        return None
    if isinstance(val, (int, float)):
        # If milliseconds (> 1e11), convert to seconds
        ts = val / 1000.0 if val > 1e11 else float(val)
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(val, str):
        return val
    return None


def load_raw_input(raw_input):
    """Safely parse raw_input whether it is a file path or direct JSON string."""
    if not raw_input:
        return None
    raw_str = raw_input.strip()
    if raw_str.startswith("{") or raw_str.startswith("["):
        return json.loads(raw_str)
    try:
        p = Path(raw_input).expanduser()
        if len(raw_input) < 1024 and p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        pass
    return json.loads(raw_str)


def parse_agy_json(raw_data, observed_at=None):
    """Parse agy -p "/usage" --output-format json payload into standard QuotaWindow list."""
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    data = raw_data
    if isinstance(raw_data, str):
        data = load_raw_input(raw_data)

    command_data = (data.get("command") or {}).get("data") or {}
    groups = command_data.get("groups") or []

    results = []
    for group in groups:
        group_name = group.get("name", "Default")
        for bucket in group.get("buckets") or []:
            window_id = bucket.get("window") or bucket.get("id") or "unknown"
            remaining_frac = bucket.get("remaining_fraction")
            if remaining_frac is not None:
                rem_pct = round(remaining_frac * 100.0, 2)
                used_pct = round(100.0 - rem_pct, 2)
            else:
                rem_pct = None
                used_pct = None

            window_mins = None
            if window_id == "5h":
                window_mins = 300
            elif window_id in ("weekly", "gemini-weekly", "3p-weekly"):
                window_mins = 10080

            results.append({
                "provider": "antigravity",
                "account_id": None,
                "model_group": group_name,
                "window_name": bucket.get("name") or window_id,
                "window_id": window_id,
                "window_minutes": window_mins,
                "used_percent": used_pct,
                "remaining_percent": rem_pct,
                "resets_at": parse_iso_or_timestamp(bucket.get("reset_time")),
                "observed_at": observed_at,
                "source": "cli"
            })
    return results


def fetch_agy_quota(raw_input=None, timeout_seconds=15):
    """Fetch live Antigravity quota via agy CLI or parse supplied raw JSON."""
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if raw_input:
        return parse_agy_json(load_raw_input(raw_input), observed_at)

    cmd = ["agy", "-p", "/usage", "--output-format", "json"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_seconds, check=True)
        return parse_agy_json(proc.stdout, observed_at)
    except FileNotFoundError:
        raise RuntimeError("Antigravity CLI ('agy') not found in PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timed out after {timeout_seconds}s waiting for agy CLI")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"agy CLI failed (exit {exc.returncode}): {exc.stderr.strip()}")


def parse_codex_response(data, account_id=None, observed_at=None):
    """Parse Codex app-server account/rateLimits/read response."""
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if isinstance(data, str):
        data = json.loads(data)

    res = data.get("result") or data
    limits_by_id = res.get("rateLimitsByLimitId") or {}
    codex_limits = limits_by_id.get("codex") or {}

    results = []
    for tier_key in ("primary", "secondary"):
        tier = codex_limits.get(tier_key)
        if not tier:
            continue
        window_mins = tier.get("windowDurationMins")
        used_pct = tier.get("usedPercent")
        rem_pct = round(100.0 - used_pct, 2) if used_pct is not None else None

        window_id = f"{window_mins}m" if window_mins else tier_key
        if window_mins == 300:
            window_id = "5h"
        elif window_mins == 10080:
            window_id = "weekly"

        results.append({
            "provider": "codex",
            "account_id": account_id,
            "model_group": "codex",
            "window_name": f"Codex {tier_key.capitalize()} ({window_id})",
            "window_id": window_id,
            "window_minutes": window_mins,
            "used_percent": round(used_pct, 2) if used_pct is not None else None,
            "remaining_percent": rem_pct,
            "resets_at": parse_iso_or_timestamp(tier.get("resetsAt")),
            "observed_at": observed_at,
            "source": "cli"
        })
    return results


def fetch_codex_quota(codex_home=None, raw_input=None, timeout_seconds=15):
    """Fetch live Codex quota via codex app-server JSON-RPC or parse supplied raw JSON."""
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    account_id = Path(codex_home).name if codex_home else None

    if raw_input:
        return parse_codex_response(load_raw_input(raw_input), account_id, observed_at)

    env = os.environ.copy()
    if codex_home:
        env["CODEX_HOME"] = str(Path(codex_home).expanduser().resolve())

    cmd = ["codex", "-c", "features.plugins=false", "app-server"]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    except FileNotFoundError:
        raise RuntimeError("Codex CLI ('codex') not found in PATH")

    init_req = json.dumps({
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {"name": "model-routing", "title": "Model Routing Quota Monitor", "version": "1.0.0"},
            "capabilities": None
        }
    }) + "\n"
    notify = json.dumps({"method": "initialized", "params": {}}) + "\n"
    query_req = json.dumps({"id": 2, "method": "account/rateLimits/read", "params": {}}) + "\n"

    try:
        proc.stdin.write(init_req + notify + query_req)
        proc.stdin.flush()

        response_line = None
        start = datetime.now()
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.strip())
                if msg.get("id") == 2:
                    response_line = msg
                    break
            except json.JSONDecodeError:
                continue
            if (datetime.now() - start).total_seconds() > timeout_seconds:
                raise subprocess.TimeoutExpired(cmd, timeout_seconds)

        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

        if not response_line:
            raise RuntimeError("Did not receive account/rateLimits/read response from codex app-server")

        return parse_codex_response(response_line, account_id, observed_at)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Timed out after {timeout_seconds}s querying codex app-server")


def parse_claude_response(data, account_id=None, observed_at=None):
    """Parse Claude Code control_request get_usage response."""
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if isinstance(data, str):
        data = json.loads(data)

    response = data.get("response") or data.get("result") or data
    rate_limits = response.get("rate_limits") or {}

    results = []
    window_map = [
        ("five_hour", "Five Hour Limit", 300),
        ("seven_day", "Seven Day Limit", 10080),
        ("seven_day_opus", "Seven Day Opus Limit", 10080),
        ("seven_day_sonnet", "Seven Day Sonnet Limit", 10080)
    ]

    for win_key, win_label, win_mins in window_map:
        limit = rate_limits.get(win_key)
        if not limit:
            continue
        util = limit.get("utilization")
        if util is None:
            continue
        used_pct = round(float(util), 2)
        rem_pct = round(100.0 - used_pct, 2)

        results.append({
            "provider": "claude",
            "account_id": account_id,
            "model_group": "claude",
            "window_name": win_label,
            "window_id": win_key,
            "window_minutes": win_mins,
            "used_percent": used_pct,
            "remaining_percent": rem_pct,
            "resets_at": parse_iso_or_timestamp(limit.get("resets_at")),
            "observed_at": observed_at,
            "source": "cli"
        })
    return results


def parse_claude_history_file(history_path=None, account_id=None, observed_at=None):
    """Parse local Claude Desktop plan-usage-history.json as fallback."""
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if history_path is None:
        history_path = Path.home() / "Library/Application Support/Claude/plan-usage-history.json"
    else:
        history_path = Path(history_path).expanduser().resolve()

    if not history_path.is_file():
        raise RuntimeError(f"Claude plan usage history file not found: {history_path}")

    records = json.loads(history_path.read_text(encoding="utf-8"))
    if not records or not isinstance(records, list):
        raise RuntimeError("No records in Claude plan usage history")

    latest = records[-1]
    u = latest.get("u") or {}
    sample_time = parse_iso_or_timestamp(latest.get("t"))

    results = []
    metric_map = [
        ("fh", "Five Hour Limit (history)", "five_hour", 300),
        ("sd", "Seven Day Limit (history)", "seven_day", 10080),
        ("so", "Seven Day Opus Limit (history)", "seven_day_opus", 10080),
        ("sn", "Seven Day Sonnet Limit (history)", "seven_day_sonnet", 10080)
    ]

    for key, label, win_id, win_mins in metric_map:
        val = u.get(key)
        if val is None:
            continue
        used_pct = round(float(val), 2)
        rem_pct = round(100.0 - used_pct, 2)
        results.append({
            "provider": "claude",
            "account_id": account_id,
            "model_group": "claude",
            "window_name": label,
            "window_id": win_id,
            "window_minutes": win_mins,
            "used_percent": used_pct,
            "remaining_percent": rem_pct,
            "resets_at": None,
            "observed_at": sample_time or observed_at,
            "source": "local_file"
        })
    return results


def fetch_claude_quota(claude_config_dir=None, fallback_history=True, history_path=None, raw_input=None, timeout_seconds=15):
    """Fetch live Claude quota via Claude CLI get_usage control request, falling back to local file."""
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    account_id = Path(claude_config_dir).name if claude_config_dir else None

    if raw_input:
        return parse_claude_response(load_raw_input(raw_input), account_id, observed_at)

    env = os.environ.copy()
    if claude_config_dir:
        env["CLAUDE_CONFIG_DIR"] = str(Path(claude_config_dir).expanduser().resolve())

    cmd = [
        "claude",
        "--print",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--tools", "",
        "--strict-mcp-config",
        "--mcp-config", '{"mcpServers":{}}',
        "--setting-sources", "",
        "--settings", '{"disableAllHooks":true}'
    ]

    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        init_req = json.dumps({"type": "control_request", "request_id": "initialize", "request": {"subtype": "initialize"}}) + "\n"
        usage_req = json.dumps({"type": "control_request", "request_id": "usage", "request": {"subtype": "get_usage", "skip_behaviors": True}}) + "\n"

        proc.stdin.write(init_req + usage_req)
        proc.stdin.flush()

        response_obj = None
        start = datetime.now()
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.strip())
                if msg.get("request_id") == "usage" or "rate_limits" in (msg.get("response") or {}):
                    response_obj = msg
                    break
            except json.JSONDecodeError:
                continue
            if (datetime.now() - start).total_seconds() > timeout_seconds:
                raise subprocess.TimeoutExpired(cmd, timeout_seconds)

        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

        if response_obj:
            return parse_claude_response(response_obj, account_id, observed_at)
        raise RuntimeError("No get_usage response received from Claude CLI")

    except Exception as exc:
        if fallback_history:
            try:
                return parse_claude_history_file(history_path, account_id, observed_at)
            except Exception as hist_err:
                raise RuntimeError(f"Claude CLI failed ({exc}) and history fallback failed: {hist_err}") from exc
        raise


def format_table(windows):
    """Format QuotaWindow items as an ASCII / Markdown table."""
    headers = ["Provider", "Group / Account", "Window", "Used %", "Remaining %", "Resets At", "Source"]
    rows = []
    for w in windows:
        group = w.get("model_group") or ""
        if w.get("account_id"):
            group = f"{group} ({w['account_id']})"
        rem = f"{w['remaining_percent']}%" if w.get("remaining_percent") is not None else "-"
        used = f"{w['used_percent']}%" if w.get("used_percent") is not None else "-"
        resets = w.get("resets_at") or "-"
        rows.append([
            w.get("provider", ""),
            group,
            w.get("window_name", ""),
            used,
            rem,
            resets,
            w.get("source", "")
        ])

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, col in enumerate(row):
            widths[idx] = max(widths[idx], len(str(col)))

    lines = []
    lines.append(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("-+-".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        lines.append(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="provider", required=True)

    p_agy = sub.add_parser("agy", help="Fetch Antigravity live quota")
    p_agy.add_argument("--raw-json", help="Path to raw JSON file or string for offline parsing")
    p_agy.add_argument("--timeout", type=int, default=15, help="CLI timeout in seconds")

    p_codex = sub.add_parser("codex", help="Fetch Codex live quota via app-server")
    p_codex.add_argument("--codex-home", help="Path to custom CODEX_HOME for multi-account")
    p_codex.add_argument("--raw-json", help="Path to raw JSON file or string for offline parsing")
    p_codex.add_argument("--timeout", type=int, default=15, help="CLI timeout in seconds")

    p_claude = sub.add_parser("claude", help="Fetch Claude Code live quota via CLI get_usage")
    p_claude.add_argument("--claude-config-dir", help="Path to custom CLAUDE_CONFIG_DIR for multi-account")
    p_claude.add_argument("--no-fallback", action="store_true", help="Do not fall back to plan-usage-history.json")
    p_claude.add_argument("--history-path", help="Custom path to plan-usage-history.json")
    p_claude.add_argument("--raw-json", help="Path to raw JSON file or string for offline parsing")
    p_claude.add_argument("--timeout", type=int, default=15, help="CLI timeout in seconds")

    p_all = sub.add_parser("all", help="Fetch quota from all installed providers")
    p_all.add_argument("--format", choices=["json", "table"], default="json", help="Output format")
    p_all.add_argument("--timeout", type=int, default=15, help="Per-provider CLI timeout")

    args = parser.parse_args()

    try:
        if args.provider == "agy":
            results = fetch_agy_quota(raw_input=args.raw_json, timeout_seconds=args.timeout)
            print(json.dumps(results, indent=2))
        elif args.provider == "codex":
            results = fetch_codex_quota(codex_home=args.codex_home, raw_input=args.raw_json, timeout_seconds=args.timeout)
            print(json.dumps(results, indent=2))
        elif args.provider == "claude":
            results = fetch_claude_quota(
                claude_config_dir=args.claude_config_dir,
                fallback_history=not args.no_fallback,
                history_path=args.history_path,
                raw_input=args.raw_json,
                timeout_seconds=args.timeout
            )
            print(json.dumps(results, indent=2))
        elif args.provider == "all":
            all_results = []
            errors = {}

            # AGY
            try:
                all_results.extend(fetch_agy_quota(timeout_seconds=args.timeout))
            except Exception as e:
                errors["antigravity"] = str(e)

            # Codex
            try:
                all_results.extend(fetch_codex_quota(timeout_seconds=args.timeout))
            except Exception as e:
                errors["codex"] = str(e)

            # Claude
            try:
                all_results.extend(fetch_claude_quota(timeout_seconds=args.timeout))
            except Exception as e:
                errors["claude"] = str(e)

            if args.format == "table":
                print(format_table(all_results))
                if errors:
                    print("\nProvider Errors:")
                    for prov, err in errors.items():
                        print(f"  - {prov}: {err}")
            else:
                out = {"quotas": all_results, "errors": errors}
                print(json.dumps(out, indent=2))

    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
