#!/usr/bin/env python3
"""Offline model-selection, consensus and report-disagreement helpers.

No model calls, network requests, keys or automatic spending authorization.
Python 3.9+ standard library.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys

import _common as common

ROLES = ("lookup", "extract", "verify", "report", "judge")
MODES = ("single", "unanimous", "judge", "human", "tiered")
MODULES = ("fact_check", "longitudinal", "qualitative")
VERDICTS = {"supported", "contradicted", "mixed", "indeterminate", "abstain"}
DETERMINATE = {"supported", "contradicted", "mixed"}
TASK_IDENTITY = ("claim_id", "criteria_hash", "input_hash", "as_of")


def canonical(value):
    return common.canonical(value)


def policy_hash(policy):
    return hashlib.sha256(canonical({k: v for k, v in policy.items() if k != "policy_hash"}).encode()).hexdigest()


def read_json(path):
    return common.read_json(path)


def read_rows(path):
    try:
        return common.read_jsonl(path)
    except ValueError as exc:
        raise ValueError(f"{exc} (expected JSONL: one JSON object per line, not a JSON array)") from exc


def atomic_text(path, text):
    common.atomic_text(path, text)


def write_json(path, value):
    common.write_json(path, value)


def nonempty(value):
    return common.nonempty(value)


def finite(value):
    return common.finite_number(value)


def strings(value, name, nonempty_list=False):
    if not isinstance(value, list) or any(not nonempty(x) for x in value) or len(set(value)) != len(value):
        raise ValueError(f"{name} must be an array of distinct, nonempty strings")
    if nonempty_list and not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _normalize_scalar(value, tolerance=None):
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if tolerance and tolerance > 0:
            return round(value / tolerance) * tolerance
        if value.is_integer():
            return int(value)
        return round(value, 12)
    if isinstance(value, str):
        # Canonicalize equivalent UTC timestamps (e.g. Z vs +00:00).
        if len(value) >= 20 and ("T" in value) and (value.endswith("Z") or "+" in value[10:] or "-" in value[10:]):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    return dt.astimezone(__import__("datetime").timezone.utc).isoformat()
            except ValueError:
                pass
    return value


def normalize_result_payload(payload, result_contract=None):
    if payload is None:
        return None
    if isinstance(payload, dict):
        items = payload.items()
        if isinstance(result_contract, dict) and isinstance(result_contract.get("fields"), list):
            allowed = set(result_contract["fields"])
            items = [(k, v) for k, v in items if k in allowed]
        tol = result_contract.get("tolerance") if isinstance(result_contract, dict) else None
        return {k: normalize_result_payload(v, {"tolerance": tol} if tol else None) for k, v in items}
    if isinstance(payload, list):
        return [normalize_result_payload(x, result_contract) for x in payload]
    tol = result_contract.get("tolerance") if isinstance(result_contract, dict) else None
    return _normalize_scalar(payload, tolerance=tol)


def init(run):
    folder = Path(run).resolve() / "config"
    folder.mkdir(parents=True, exist_ok=True)
    policy = {"schema_version": 1, "status": "draft", "selected_models": [],
              "analysis_modules": list(MODULES),
              "roles": {role: [] for role in ROLES},
              "verification": {"mode": "single", "required_reviewers": [], "judge_model_id": None, "escalation": "hold"},
              "report": {"reviewers": [], "judge_model_id": None},
              "max_models": 5, "allow_unlisted_models": False}
    template = """# 模型选择问卷

先列出宿主真实可用的模型与调用能力，再让用户选定。此文件和 draft 配置不授权模型调用或付费。

1. 本次选择哪些具体模型？记录 provider、真实 API model/snapshot、可用性与价格依据。不要把 Luna/Haiku/Sonnet 等系列别名猜成 API ID。
2. lookup、extract、verify、report 分别用哪些已选模型？judge 是否需要？同一个模型可担任多个角色。
   每个阶段在本地自动跑、导出给网页/其他 AI，还是人工执行？在 config/execution-selection.md 记录，run.json.execution 保存机器配置；参考 external-handoff.md。
3. 核验采用 single、全员 unanimous、指定 judge、tiered 还是 human？明确 required_reviewers；不能因超时而偷偷减员或改成多数票。若希望 unresolved unanimous/judge 结果可转人工，预先设置 verification.escalation=human；默认 hold，不自动启用。
4. 哪些模型独立评价同一个冻结报告数据与 rubric？是否另指定复核 judge？重复调用同一模型不是新增独立模型。
5. 是否已有覆盖本次任务的费用授权、预算与并发限制？预算授权另记；配置本身不代表同意收费。

每个 selected_models 条目格式：

```json
{"id":"user-chosen-alias","provider":"actual-provider","api_model":"actual-model-or-snapshot","availability":"available","cost":{"mode":"metered","estimate_usd":null,"pricing_checked_at":null}}
```

availability 可用 available/unverified/unavailable；只有已确认 available 的模型可进入 confirmed policy。
cost.mode 可用 metered/included/local/unknown；未知费用写 null，并由总预算流程处理。不要写密钥。
roles 映射是角色分配唯一来源，不在 model 条目重复写 roles。
"""
    created, preserved = [], []
    for name, content in (("model-policy.json", json.dumps(policy, ensure_ascii=False, indent=2) + "\n"),
                          ("model-selection.md", template)):
        path = folder / name
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(content)
            created.append(str(path))
        except FileExistsError:
            preserved.append(str(path))
    return {"created": created, "preserved": preserved, "calls_authorized": False}


def validate_policy(policy, require_sealed=False):
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise ValueError("Unsupported model policy schema")
    if policy.get("status") != "confirmed":
        raise ValueError("Model selection is still draft; obtain explicit user choices before confirming")
    cap = policy.get("max_models")
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("max_models must be a positive integer")
    modules = policy.get("analysis_modules", list(MODULES))
    if not isinstance(modules, list) or not modules or any(m not in MODULES for m in modules):
        raise ValueError("analysis_modules must be a nonempty subset of fact_check, longitudinal, qualitative")
    fact_enabled = "fact_check" in modules
    qual_enabled = "qualitative" in modules
    verification = policy.get("verification")
    report = policy.get("report")
    if not isinstance(verification, dict) or verification.get("mode") not in MODES or not isinstance(report, dict):
        raise ValueError("Invalid verification/report policy")
    if verification.get("escalation", "hold") not in {"hold", "human"}:
        raise ValueError("verification.escalation must be hold or human")
    pure_human_verify = verification["mode"] == "human"
    models = policy.get("selected_models")
    if not isinstance(models, list) or len(models) > cap or (not models and (qual_enabled or (fact_enabled and not pure_human_verify))):
        raise ValueError("Select at least one model without exceeding max_models")
    identities, by_id, warnings = set(), {}, []
    for model in models:
        if not isinstance(model, dict) or any(not nonempty(model.get(k)) for k in ("id", "provider", "api_model")):
            raise ValueError("Each model needs explicit id, provider and actual api_model")
        if model["id"] in by_id:
            raise ValueError("Duplicate model id")
        identity = (model["provider"].strip().lower(), model["api_model"].strip().lower())
        if identity in identities:
            raise ValueError("The same provider/model cannot masquerade as multiple panel members")
        if model.get("availability") != "available":
            raise ValueError("Requested model availability is not confirmed; do not substitute silently")
        if "roles" in model:
            raise ValueError("Use only the top-level roles mapping; duplicated per-model roles are ambiguous")
        cost = model.get("cost")
        if not isinstance(cost, dict) or cost.get("mode") not in {"metered", "included", "local", "unknown"}:
            raise ValueError("Each selected model needs explicit cost.mode; unknown is permitted but is not free")
        if "estimate_usd" not in cost or (cost["estimate_usd"] is not None and (not finite(cost["estimate_usd"]) or cost["estimate_usd"] < 0)):
            raise ValueError("cost.estimate_usd must be null or a finite nonnegative amount")
        if cost["mode"] == "unknown" or cost["estimate_usd"] is None:
            warnings.append(f"Cost is unknown for {model['id']}; consult the separate budget authorization")
        identities.add(identity)
        by_id[model["id"]] = model
    if policy.get("allow_unlisted_models") is not False:
        raise ValueError("This helper requires allow_unlisted_models=false; select every actual model explicitly")
    roles = policy.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(ROLES):
        raise ValueError("roles must contain lookup, extract, verify, report and judge")
    for role in ROLES:
        need_nonempty = False
        if role in {"lookup", "extract", "verify"}:
            need_nonempty = fact_enabled and not (role == "verify" and pure_human_verify)
        elif role == "report":
            need_nonempty = qual_enabled
        ids = strings(roles[role], "roles." + role, nonempty_list=need_nonempty)
        if any(model_id not in by_id for model_id in ids):
            raise ValueError("A role references an unselected model")
    reviewers = strings(verification.get("required_reviewers"), "verification.required_reviewers", fact_enabled and not pure_human_verify)
    if any(m not in roles["verify"] for m in reviewers):
        raise ValueError("Every fact reviewer must be assigned the verify role")
    if verification["mode"] == "single" and len(reviewers) != 1:
        raise ValueError("single mode requires exactly one named reviewer")
    if verification["mode"] == "unanimous" and len(reviewers) < 2:
        raise ValueError("Use single mode for one reviewer; unanimous requires at least two")
    if verification["mode"] == "tiered" and fact_enabled and not reviewers:
        raise ValueError("tiered mode requires at least one initial reviewer")
    reports = strings(report.get("reviewers"), "report.reviewers", qual_enabled)
    if any(m not in roles["report"] for m in reports):
        raise ValueError("Every report reviewer must be assigned the report role")
    for label, section in (("verification", verification), ("report", report)):
        judge = section.get("judge_model_id")
        if judge is not None and judge not in roles["judge"]:
            raise ValueError(label + " judge must be selected and assigned the judge role")
    if verification["mode"] == "judge":
        judge_id = verification.get("judge_model_id")
        if judge_id is None:
            raise ValueError("judge mode requires an explicit judge_model_id")
        if len(reviewers) == 1 and judge_id == reviewers[0] and not verification.get("allow_self_judge", False):
            raise ValueError("judge_model_id cannot equal the sole required reviewer unless allow_self_judge=true")
    expected_hash = policy_hash(policy)
    if "policy_hash" in policy and policy["policy_hash"] != expected_hash:
        raise ValueError("Frozen model policy changed; use a new run/policy version")
    if require_sealed and "policy_hash" not in policy:
        raise ValueError("Freeze the confirmed policy before accepting panel results")
    return {"valid": True, "policy_hash": expected_hash, "model_count": len(models),
            "roles": roles, "warnings": warnings, "calls_authorized": False}


def load_policy(path):
    policy = read_json(path)
    validate_policy(policy, require_sealed=True)
    lock = Path(path).parent / "model-policy.lock.json"
    if lock.exists() and policy_hash(read_json(lock)) != policy_hash(policy):
        raise ValueError("Policy differs from its immutable lock; start a new policy version")
    return policy


def validate_run(run):
    folder = Path(run).resolve() / "config"
    policy = read_json(folder / "model-policy.json")
    result = validate_policy(policy)
    lock = folder / "model-policy.lock.json"
    if lock.exists() and policy_hash(read_json(lock)) != result["policy_hash"]:
        raise ValueError("Policy differs from its immutable lock; start a new policy version")
    return result


def freeze(run):
    run_path = Path(run).resolve()
    with common.advisory_lock(run_path):
        folder = run_path / "config"
        policy = read_json(folder / "model-policy.json")
        result = validate_run(run_path)
        policy["policy_hash"] = result["policy_hash"]
        lock = folder / "model-policy.lock.json"
        if not lock.exists():
            # Exclusive creation avoids replacing a previously frozen policy.
            with lock.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(policy, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
                stream.flush()
                __import__("os").fsync(stream.fileno())
        write_json(folder / "model-policy.json", policy)
        return {**result, "frozen": True, "lock_path": str(lock)}


def summarize(policy, reviews):
    validate_policy(policy, require_sealed=True)
    planned = policy["report"]["reviewers"]
    seen_models, seen_reviews = set(), set()
    identity, metrics = None, set()
    statuses = {"completed", "failed", "abstained"}
    for row in reviews:
        if not nonempty(row.get("review_id")) or row["review_id"] in seen_reviews:
            raise ValueError("Missing/duplicate review_id")
        if row.get("model_id") not in planned:
            raise ValueError("Report review is from an unplanned model")
        if row["model_id"] in seen_models:
            raise ValueError("Use one terminal review per model; repeated calls cannot inflate panel n")
        if row.get("status") not in statuses:
            raise ValueError("Unknown review status")
        scale = row.get("score_scale")
        if not isinstance(scale, dict) or not finite(scale.get("min")) or not finite(scale.get("max")) or scale["min"] >= scale["max"]:
            raise ValueError("score_scale must have finite min < max")
        if any(not nonempty(row.get(k)) for k in ("data_hash", "rubric_hash")):
            raise ValueError("Every review must bind data_hash and rubric_hash")
        current = (row["data_hash"], row["rubric_hash"], scale["min"], scale["max"])
        if identity is None:
            identity = current
        elif identity != current:
            raise ValueError("Review data, rubric or score scale mismatch")
        scores = row.get("scores")
        if not isinstance(scores, dict) or any(not nonempty(k) for k in scores):
            raise ValueError("scores must map named metrics to numbers or null")
        if row["status"] == "completed" and row.get("independent") is not True:
            raise ValueError("Completed reviews must be produced independently before seeing peer ratings")
        for name, value in scores.items():
            if value is not None and (not finite(value) or not scale["min"] <= value <= scale["max"]):
                raise ValueError("Score outside agreed scale or non-finite")
            if row["status"] != "completed" and value is not None:
                raise ValueError("Failed/abstained reviews cannot contribute numeric scores")
            metrics.add(name)
        seen_models.add(row["model_id"])
        seen_reviews.add(row["review_id"])
    results = {}
    for metric in sorted(metrics):
        values = [r["scores"][metric] for r in reviews if r["status"] == "completed" and r["scores"].get(metric) is not None]
        n = len(values)
        results[metric] = {"n": n, "planned_n": len(planned),
                           "mean": statistics.mean(values) if n else None,
                           "median": statistics.median(values) if n else None,
                           "min": min(values) if n else None, "max": max(values) if n else None,
                           "range": max(values) - min(values) if n else None,
                           "sample_variance": statistics.variance(values) if n > 1 else None,
                           "sd": statistics.stdev(values) if n > 1 else None}
    return {"schema_version": 1, "policy_hash": policy["policy_hash"],
            "interpretation": "model_disagreement_not_confidence_interval", "independence_caveat": "Models may share training data and correlated errors",
            "data_hash": identity[0] if identity else None, "rubric_hash": identity[1] if identity else None,
            "score_scale": {"min": identity[2], "max": identity[3]} if identity else None,
            "planned_models": planned, "missing_models": [m for m in planned if m not in seen_models],
            "status_counts": {s: sum(r["status"] == s for r in reviews) for s in sorted(statuses)},
            "metrics": results, "reviews": reviews, "judge_decision": None,
            "score_truth_verified": False}


def validate_vote(row):
    if any(not nonempty(row.get(k)) for k in ("vote_id", "reviewer_id", *TASK_IDENTITY)):
        raise ValueError("Each vote requires identity, criteria, input and as_of bindings")
    if row.get("verdict") not in VERDICTS:
        raise ValueError("Unknown vote verdict")
    strings(row.get("evidence_ids"), "evidence_ids")
    if not nonempty(row.get("rationale")) or row.get("independent") is not True:
        raise ValueError("Each initial vote needs rationale and independent=true")
    if row["verdict"] in DETERMINATE:
        if not row["evidence_ids"] or not isinstance(row.get("normalized_result"), dict) or not row["normalized_result"]:
            raise ValueError("Determinate votes require evidence references and a nonempty normalized_result object")
    canonical(row)


def consensus(policy, votes, decision=None, *, allow_terminal_indeterminate=False, result_contract=None):
    validate_policy(policy, require_sealed=True)
    settings = policy["verification"]
    planned = settings["required_reviewers"]
    seen, vote_ids, identity = set(), set(), None
    allowed_voters = set(planned) | (set(settings.get("escalation_reviewers", [])) if settings["mode"] == "tiered" else set())
    for row in votes:
        validate_vote(row)
        if row["reviewer_id"] not in allowed_voters:
            raise ValueError("Vote from an unplanned reviewer")
        if row["reviewer_id"] in seen or row["vote_id"] in vote_ids:
            raise ValueError("Duplicate reviewer/vote; one initial terminal vote per selected reviewer")
        current = tuple(row[k] for k in TASK_IDENTITY)
        if identity is None:
            identity = current
        elif identity != current:
            raise ValueError("Votes differ in claim, criteria, input or cutoff; they cannot be compared")
        seen.add(row["reviewer_id"])
        vote_ids.add(row["vote_id"])
    missing = [m for m in planned if m not in seen]
    model_families = {m["id"]: (m.get("canonical_model_family") or f"{m['provider']}:{m['api_model']}").strip().lower()
                      for m in policy.get("selected_models", [])}
    effective_models = len({model_families.get(m, m) for m in seen})
    result = {"schema_version": 1, "policy_hash": policy["policy_hash"], "mode": settings["mode"],
              **(dict(zip(TASK_IDENTITY, identity)) if identity else {}), "accepted": False,
              "terminal_indeterminate": False,
              "planned_reviewers": planned, "missing_reviewers": missing,
              "effective_independent_models": effective_models, "votes": votes,
              "decision": decision, "verdict": None, "normalized_result": None,
              "evidence_truth_verified": False, "actor_authentication_verified": False,
              "resolution_route": settings["mode"], "escalation_reason": None}
    if missing and settings["mode"] != "human":
        return {**result, "reason": "missing_required_reviewers"}
    if not votes and settings["mode"] != "human":
        return {**result, "reason": "no_votes"}
    normalized_pairs = [
        canonical({"verdict": v["verdict"], "normalized_result": normalize_result_payload(v.get("normalized_result"), result_contract)})
        for v in votes
    ]
    same = len(set(normalized_pairs)) == 1 if votes else False
    determinate = all(v["verdict"] in DETERMINATE for v in votes) if votes else False
    all_indeterminate = bool(votes) and all(v["verdict"] == "indeterminate" for v in votes)
    mode = settings["mode"]
    if isinstance(decision, dict) and decision.get("actor_type") == "human" and mode != "human":
        if settings.get("escalation", "hold") != "human":
            raise ValueError("Human escalation was not preconfigured; hold the unresolved result")
        if mode in {"unanimous", "tiered"}:
            if determinate and same and mode == "unanimous":
                raise ValueError("Clear unanimity cannot be overridden through unresolved-result escalation")
            reason = "abstention_or_indeterminate" if not determinate else "reviewer_disagreement"
        elif mode == "judge":
            prior = decision.get("prior_judge_decision")
            if not isinstance(prior, dict) or prior.get("actor_type") != "model":
                raise ValueError("Judge escalation requires the full prior_judge_decision")
            prior_result = consensus(policy, votes, prior, result_contract=result_contract)
            if prior_result["accepted"] or prior_result["reason"] != "decision_remains_indeterminate":
                raise ValueError("Human fallback requires an unresolved valid selected-judge decision")
            reason = "judge_indeterminate"
        else:
            raise ValueError("Human fallback is supported only for unresolved unanimous, tiered or judge modes")
        mode = "human"
        result.update(resolution_route="human_escalation", escalation_reason=reason)
    if mode in {"single", "unanimous"}:
        if decision is not None:
            raise ValueError("A decision cannot bypass single/unanimous mode; change policy only with user authorization")
        if not determinate:
            if allow_terminal_indeterminate and all_indeterminate:
                return {**result, "accepted": True, "terminal_indeterminate": True,
                        "reason": "confirmed_indeterminate", "verdict": "indeterminate",
                        "normalized_result": votes[0].get("normalized_result")}
            return {**result, "reason": "abstention_or_indeterminate"}
        if not same:
            return {**result, "reason": "reviewer_disagreement"}
        return {**result, "accepted": True, "reason": "single_evidence_vote" if mode == "single" else "unanimous_determinate_votes",
                "verdict": votes[0]["verdict"], "normalized_result": votes[0]["normalized_result"]}
    if mode == "tiered" and decision is None:
        if determinate and same:
            return {**result, "accepted": True, "reason": "tiered_consensus",
                    "verdict": votes[0]["verdict"], "normalized_result": votes[0]["normalized_result"]}
        if allow_terminal_indeterminate and all_indeterminate:
            return {**result, "accepted": True, "terminal_indeterminate": True,
                    "reason": "confirmed_indeterminate", "verdict": "indeterminate",
                    "normalized_result": votes[0].get("normalized_result")}
        return {**result, "reason": "tiered_escalation_required"}
    if decision is None:
        return {**result, "reason": "explicit_judge_or_human_decision_required"}
    if not isinstance(decision, dict) or any(not nonempty(decision.get(k)) for k in ("decision_id", "actor_id", "rationale", *TASK_IDENTITY)):
        raise ValueError("Decision requires declared actor, rationale and all task identity fields")
    if identity is not None and tuple(decision[k] for k in TASK_IDENTITY) != identity:
        raise ValueError("Decision task identity does not match the votes")
    considered = strings(decision.get("considered_vote_ids"), "considered_vote_ids")
    if set(considered) != vote_ids:
        raise ValueError("Decision must consider every submitted vote, including abstentions")
    if mode in {"judge", "tiered"} and decision.get("actor_type") == "model":
        if decision["actor_id"] != settings.get("judge_model_id"):
            raise ValueError("Decision actor is not the selected judge model")
    elif decision.get("actor_type") != "human" or not nonempty(decision.get("user_approval_reference")):
        raise ValueError("Human decision needs human attribution and an actual user approval reference")
    if decision.get("verdict") not in VERDICTS:
        raise ValueError("Unknown decision verdict")
    if decision["verdict"] not in DETERMINATE:
        if allow_terminal_indeterminate and decision["verdict"] == "indeterminate":
            return {**result, "accepted": True, "terminal_indeterminate": True,
                    "reason": "confirmed_indeterminate", "verdict": "indeterminate",
                    "normalized_result": decision.get("normalized_result")}
        return {**result, "reason": "decision_remains_indeterminate"}
    strings(decision.get("evidence_ids"), "decision.evidence_ids", True)
    if not isinstance(decision.get("normalized_result"), dict) or not decision["normalized_result"]:
        raise ValueError("Determinate decision requires normalized_result")
    canonical(decision)
    return {**result, "accepted": True, "reason": "explicit_" + mode + "_decision",
            "verdict": decision["verdict"], "normalized_result": decision["normalized_result"]}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("init", "validate", "freeze"):
        command = sub.add_parser(name)
        command.add_argument("--run", required=True)
    report = sub.add_parser("summarize", help="Summarize independent qualitative model reviews from a JSONL file")
    report.add_argument("--policy", required=True, help="Path to frozen model-policy.json")
    report.add_argument("--reviews", required=True, help="JSONL file (one review JSON object per line, NOT a JSON array)")
    report.add_argument("--out", required=True, help="Output JSON path for panel summary")
    fact = sub.add_parser("consensus", help="Compute verification consensus from a JSONL votes file")
    fact.add_argument("--policy", required=True, help="Path to frozen model-policy.json")
    fact.add_argument("--votes", required=True, help="JSONL file (one vote JSON object per line, NOT a JSON array)")
    fact.add_argument("--decision", help="Optional JSON file containing a judge or human decision object")
    fact.add_argument("--allow-indeterminate", action="store_true", help="Allow terminal indeterminate consensus")
    fact.add_argument("--out", required=True, help="Output JSON path for consensus result")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init(args.run)
        elif args.command == "validate":
            result = validate_run(args.run)
        elif args.command == "freeze":
            result = freeze(args.run)
        elif args.command == "summarize":
            result = summarize(load_policy(args.policy), read_rows(args.reviews))
            write_json(Path(args.out), result)
        else:
            decision = read_json(args.decision) if args.decision else None
            result = consensus(load_policy(args.policy), read_rows(args.votes), decision,
                               allow_terminal_indeterminate=args.allow_indeterminate)
            write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
