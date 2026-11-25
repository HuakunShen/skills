#!/usr/bin/env python3
"""Offline model-selection, consensus and report-disagreement helpers.

No model calls, network requests, keys or automatic spending authorization.
Python 3.10+ standard library.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import os
import statistics
import sys
import tempfile

ROLES = ("lookup", "extract", "verify", "report", "judge")
MODES = ("single", "unanimous", "judge", "human")
VERDICTS = {"supported", "contradicted", "mixed", "indeterminate", "abstain"}
DETERMINATE = {"supported", "contradicted", "mixed"}
TASK_IDENTITY = ("claim_id", "criteria_hash", "input_hash", "as_of")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def policy_hash(policy):
    return hashlib.sha256(canonical({k: v for k, v in policy.items() if k != "policy_hash"}).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_rows(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Line {number} must contain a JSON object")
            rows.append(value)
    return rows


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".panel-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def strings(value, name, nonempty_list=False):
    if not isinstance(value, list) or any(not nonempty(x) for x in value) or len(set(value)) != len(value):
        raise ValueError(f"{name} must be an array of distinct, nonempty strings")
    if nonempty_list and not value:
        raise ValueError(f"{name} must not be empty")
    return value


def init(run):
    folder = Path(run).resolve() / "config"
    folder.mkdir(parents=True, exist_ok=True)
    policy = {"schema_version": 1, "status": "draft", "selected_models": [],
              "roles": {role: [] for role in ROLES},
              "verification": {"mode": "single", "required_reviewers": [], "judge_model_id": None, "escalation": "hold"},
              "report": {"reviewers": [], "judge_model_id": None},
              "max_models": 5, "allow_unlisted_models": False}
    template = """# 模型选择问卷

先列出宿主真实可用的模型与调用能力，再让用户选定。此文件和 draft 配置不授权模型调用或付费。

1. 本次选择哪些具体模型？记录 provider、真实 API model/snapshot、可用性与价格依据。不要把 Luna/Haiku/Sonnet 等系列别名猜成 API ID。
2. lookup、extract、verify、report 分别用哪些已选模型？judge 是否需要？同一个模型可担任多个角色。
   每个阶段在本地自动跑、导出给网页/其他 AI，还是人工执行？在 config/execution-selection.md 记录，run.json.execution 保存机器配置；参考 external-handoff.md。
3. 核验采用 single、全员 unanimous、指定 judge，还是 human？明确 required_reviewers；不能因超时而偷偷减员或改成多数票。若希望 unresolved unanimous/judge 结果可转人工，预先设置 verification.escalation=human；默认 hold，不自动启用。
4. 哪些模型独立评价同一个冻结报告数据与 rubric？是否另指定复核 judge？重复调用同一模型不是新增独立模型。
5. 是否已有覆盖本次任务的费用授权、预算与并发限制？预算授权另记；配置本身不代表同意收费。

每个 selected_models 条目格式：

```json
{"id":"user-chosen-alias","provider":"actual-provider","api_model":"actual-model-or-snapshot","availability":"available","cost":{"mode":"metered","estimate_usd":null,"pricing_checked_at":null}}
```

availability 可用 available/unverified/unavailable；只有已确认 available 的模型可进入 confirmed policy。
cost.mode 可用 metered/included/local/unknown；未知费用写 null，并由总预算流程处理。不要写密钥。
roles 映射是角色分配唯一来源，不在 model 条目重复写 roles。

用户已有明确选择且配置有效时直接复用，不反复询问。没有明确选择时保持 draft；可展示建议但不能自行启用收费模型。
按选择填写 model-policy.json，设置 status=confirmed，然后运行 validate 和 freeze。之后若要换模型、改 reviewer 集合或规则，创建新 run/policy 并关联旧版本，不覆写已冻结决策。
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
    models = policy.get("selected_models")
    if not isinstance(models, list) or not models or len(models) > cap:
        raise ValueError("Select at least one model without exceeding max_models")
    identities, by_id, warnings = set(), {}, []
    for model in models:
        if not isinstance(model, dict) or any(not nonempty(model.get(k)) for k in ("id", "provider", "api_model")):
            raise ValueError("Each model needs explicit id, provider and actual api_model")
        if model["id"] in by_id:
            raise ValueError("Duplicate model id")
        identity = (model["provider"], model["api_model"])
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
        ids = strings(roles[role], "roles." + role, nonempty_list=role != "judge")
        if any(model_id not in by_id for model_id in ids):
            raise ValueError("A role references an unselected model")
    verification, report = policy.get("verification"), policy.get("report")
    if not isinstance(verification, dict) or verification.get("mode") not in MODES or not isinstance(report, dict):
        raise ValueError("Invalid verification/report policy")
    if verification.get("escalation", "hold") not in {"hold", "human"}:
        raise ValueError("verification.escalation must be hold or human")
    reviewers = strings(verification.get("required_reviewers"), "verification.required_reviewers", True)
    if any(m not in roles["verify"] for m in reviewers):
        raise ValueError("Every fact reviewer must be assigned the verify role")
    if verification["mode"] == "single" and len(reviewers) != 1:
        raise ValueError("single mode requires exactly one named reviewer")
    if verification["mode"] == "unanimous" and len(reviewers) < 2:
        raise ValueError("Use single mode for one reviewer; unanimous requires at least two")
    reports = strings(report.get("reviewers"), "report.reviewers", True)
    if any(m not in roles["report"] for m in reports):
        raise ValueError("Every report reviewer must be assigned the report role")
    for label, section in (("verification", verification), ("report", report)):
        judge = section.get("judge_model_id")
        if judge is not None and judge not in roles["judge"]:
            raise ValueError(label + " judge must be selected and assigned the judge role")
    if verification["mode"] == "judge" and verification.get("judge_model_id") is None:
        raise ValueError("judge mode requires an explicit judge_model_id")
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
    folder = Path(run).resolve() / "config"
    policy = read_json(folder / "model-policy.json")
    result = validate_run(run)
    policy["policy_hash"] = result["policy_hash"]
    lock = folder / "model-policy.lock.json"
    if not lock.exists():
        # Exclusive creation avoids replacing a previously frozen policy.
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(policy, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
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


def consensus(policy, votes, decision=None):
    validate_policy(policy, require_sealed=True)
    settings = policy["verification"]
    planned = settings["required_reviewers"]
    seen, vote_ids, identity = set(), set(), None
    for row in votes:
        validate_vote(row)
        if row["reviewer_id"] not in planned:
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
    result = {"schema_version": 1, "policy_hash": policy["policy_hash"], "mode": settings["mode"],
              **(dict(zip(TASK_IDENTITY, identity)) if identity else {}), "accepted": False,
              "planned_reviewers": planned, "missing_reviewers": missing, "votes": votes,
              "decision": decision, "verdict": None, "normalized_result": None,
              "evidence_truth_verified": False, "actor_authentication_verified": False,
              "resolution_route": settings["mode"], "escalation_reason": None}
    if missing:
        return {**result, "reason": "missing_required_reviewers"}
    if not votes:
        return {**result, "reason": "no_votes"}
    same = len({canonical({"verdict": v["verdict"], "normalized_result": v.get("normalized_result")}) for v in votes}) == 1
    determinate = all(v["verdict"] in DETERMINATE for v in votes)
    mode = settings["mode"]
    if isinstance(decision, dict) and decision.get("actor_type") == "human" and mode != "human":
        if settings.get("escalation", "hold") != "human":
            raise ValueError("Human escalation was not preconfigured; hold the unresolved result")
        if mode == "unanimous":
            if determinate and same:
                raise ValueError("Clear unanimity cannot be overridden through unresolved-result escalation")
            reason = "abstention_or_indeterminate" if not determinate else "reviewer_disagreement"
        elif mode == "judge":
            prior = decision.get("prior_judge_decision")
            if not isinstance(prior, dict) or prior.get("actor_type") != "model":
                raise ValueError("Judge escalation requires the full prior_judge_decision")
            prior_result = consensus(policy, votes, prior)
            if prior_result["accepted"] or prior_result["reason"] != "decision_remains_indeterminate":
                raise ValueError("Human fallback requires an unresolved valid selected-judge decision")
            reason = "judge_indeterminate"
        else:
            raise ValueError("Human fallback is supported only for unresolved unanimous or judge modes")
        mode = "human"
        result.update(resolution_route="human_escalation", escalation_reason=reason)
    if mode in {"single", "unanimous"}:
        if decision is not None:
            raise ValueError("A decision cannot bypass single/unanimous mode; change policy only with user authorization")
        if not determinate:
            return {**result, "reason": "abstention_or_indeterminate"}
        if not same:
            return {**result, "reason": "reviewer_disagreement"}
        return {**result, "accepted": True, "reason": "single_evidence_vote" if mode == "single" else "unanimous_determinate_votes",
                "verdict": votes[0]["verdict"], "normalized_result": votes[0]["normalized_result"]}
    if decision is None:
        return {**result, "reason": "explicit_judge_or_human_decision_required"}
    if not isinstance(decision, dict) or any(not nonempty(decision.get(k)) for k in ("decision_id", "actor_id", "rationale", *TASK_IDENTITY)):
        raise ValueError("Decision requires declared actor, rationale and all task identity fields")
    if tuple(decision[k] for k in TASK_IDENTITY) != identity:
        raise ValueError("Decision task identity does not match the votes")
    considered = strings(decision.get("considered_vote_ids"), "considered_vote_ids")
    if set(considered) != vote_ids:
        raise ValueError("Decision must consider every submitted vote, including abstentions")
    if mode == "judge":
        if decision.get("actor_type") != "model" or decision["actor_id"] != settings["judge_model_id"]:
            raise ValueError("Decision actor is not the selected judge model")
    elif decision.get("actor_type") != "human" or not nonempty(decision.get("user_approval_reference")):
        raise ValueError("Human decision needs human attribution and an actual user approval reference")
    if decision.get("verdict") not in VERDICTS:
        raise ValueError("Unknown decision verdict")
    if decision["verdict"] not in DETERMINATE:
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
    report = sub.add_parser("summarize")
    report.add_argument("--policy", required=True)
    report.add_argument("--reviews", required=True)
    report.add_argument("--out", required=True)
    fact = sub.add_parser("consensus")
    fact.add_argument("--policy", required=True)
    fact.add_argument("--votes", required=True)
    fact.add_argument("--decision")
    fact.add_argument("--out", required=True)
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
        else:
            policy = load_policy(args.policy)
            if args.command == "summarize":
                result = summarize(policy, read_rows(args.reviews))
            else:
                result = consensus(policy, read_rows(args.votes), read_json(args.decision) if args.decision else None)
            output = Path(args.out).resolve()
            protected = {Path(args.policy).resolve(), (Path(args.policy).parent / "model-policy.lock.json").resolve(),
                         Path(args.reviews if args.command == "summarize" else args.votes).resolve()}
            if args.command == "consensus" and args.decision:
                protected.add(Path(args.decision).resolve())
            if output in protected:
                raise ValueError("Output must not overwrite policy, votes, reviews or decision source")
            write_json(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
