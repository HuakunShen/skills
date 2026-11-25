#!/usr/bin/env python3
"""Adopt only reproducible, evidenced panel decisions into the canonical claim ledger.

The v1 automatic gate conservatively waits for window_end; it does not implement
irreversible early-event adoption. A VerificationSnapshot is only valid during
one coordinator-locked, read-only scoring pass; discard it before any mutation.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import _common as common
import audit_run as audit
import model_panel as panel

SEMANTIC_FIELDS = ("claim_id", "subject_id", "text", "domain", "claim_type", "empirical",
                   "endorsement", "attribution_confidence", "accountability_eligible", "quantifiability",
                   "verifiability", "evaluation_mode", "probability", "probability_origin", "due_for_assessment")


class VerificationSnapshot:
    """Per-pass cache, never global/persisted. Caller holds coordinator_lock."""
    def __init__(self, run):
        self.run = Path(run).resolve()
        self.rows = {}
        self.file_hashes = {}
        self.policies = {}
        self.config = None

    def check_run(self, run):
        if Path(run).resolve() != self.run:
            raise ValueError("VerificationSnapshot belongs to a different run")


def hashed(value):
    return common.digest(value)


def file_sha(path, snapshot=None):
    path = Path(path).resolve()
    if snapshot is not None and path in snapshot.file_hashes:
        return snapshot.file_hashes[path]
    value = common.file_sha(path)
    if snapshot is not None:
        snapshot.file_hashes[path] = value
    return value


def rows_by_id(run, filename, key, snapshot=None):
    if snapshot is not None:
        snapshot.check_run(run)
        if (filename, key) in snapshot.rows:
            return snapshot.rows[filename, key]
    value = audit.unique(audit.read_jsonl(Path(run) / filename), key, filename)
    if snapshot is not None:
        snapshot.rows[filename, key] = value
    return value


def run_config(run, snapshot=None):
    if snapshot is None:
        return audit.config(run)
    snapshot.check_run(run)
    if snapshot.config is None:
        snapshot.config = audit.config(run)
    return snapshot.config


def instant(value, label):
    if not isinstance(value, str):
        raise ValueError(label + " requires an observed ISO timestamp with timezone")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError(label + " requires timezone")
    return result


def verification_fingerprint(run, claim, snapshot=None):
    """Hash semantic inputs, attribution and actual source content; exclude mutable verdicts."""
    run = Path(run).resolve()
    cfg = run_config(run, snapshot)
    occurrences = rows_by_id(run, "occurrences.jsonl", "occurrence_id", snapshot)
    sources = rows_by_id(run, "sources.jsonl", "source_id", snapshot)
    selected, bound_sources = [], {}
    for oid in sorted(claim["occurrence_ids"]):
        if oid not in occurrences:
            raise ValueError("Missing original occurrence: " + oid)
        occurrence = occurrences[oid]
        if occurrence.get("claim_id") != claim["claim_id"] or any(k not in occurrence for k in
                ("speaker", "original_quote", "context_before", "context_after", "locator")):
            raise ValueError("Occurrence attribution/context does not match the claim")
        if not panel.nonempty(occurrence["original_quote"]):
            raise ValueError("Original quote must not be empty")
        if occurrence.get("quote_verified") is False:
            raise ValueError("Occurrence original_quote failed source grounding verification: " + oid)
        sid = occurrence.get("source_id")
        if sid not in sources:
            raise ValueError("Occurrence refers to a missing source")
        source = sources[sid]
        actual = None
        if source.get("content_path"):
            actual = file_sha(audit.inside(run, source["content_path"]), snapshot)
            expected = source.get("content_hash")
            if expected and (not isinstance(expected, str) or expected.removeprefix("sha256:") != actual):
                raise ValueError("Original source content hash changed")
        bound_sources[sid] = {k: source.get(k) for k in
                            ("source_id", "source_url", "published_at", "content_path", "content_hash", "raw_hash", "parent_source_id")}
        bound_sources[sid]["actual_content_sha256"] = actual
        selected.append(occurrence)
    if not selected:
        raise ValueError("A verification input requires at least one original occurrence")
    return hashed({"claim": {k: claim.get(k) for k in SEMANTIC_FIELDS}, "criteria": claim.get("criteria"),
                   "occurrences": selected, "sources": bound_sources,
                   "as_of": cfg["scope"]["as_of"], "cutoff_mode": cfg["cutoff_mode"]})


def evidence_bindings(run, claim_id, evidence_ids, cfg, snapshot=None, *, criteria_timezone=None,
                      frozen_at=None, verdict=None, strict_freeze_order=False):
    evidence = rows_by_id(run, "evidence.jsonl", "evidence_id", snapshot)
    cutoff = instant(cfg["scope"]["as_of"], "as_of")
    frozen_dt = instant(frozen_at, "frozen_at") if frozen_at else None
    default_obs_tz = ZoneInfo(criteria_timezone or cfg["scope"]["timezone"])
    bindings = {}
    bound_rows = []
    post_hoc_criteria = False
    for eid in sorted(evidence_ids):
        if eid not in evidence:
            raise ValueError("Missing evidence record: " + eid)
        row = evidence[eid]
        if claim_id not in row.get("claim_ids", []) and row.get("claim_id") != claim_id:
            raise ValueError("Evidence is not linked to this claim: " + eid)
        retrieved = instant(row.get("retrieved_at"), "retrieved_at")
        if retrieved > datetime.now(__import__("datetime").timezone.utc):
            raise ValueError("Evidence retrieval timestamp is in the future")
        if frozen_dt is not None and retrieved < frozen_dt:
            post_hoc_criteria = True
            if strict_freeze_order:
                raise ValueError(f"Evidence {eid} was retrieved before criteria were frozen")
        source_url, local_path = row.get("source_url"), row.get("local_path")
        valid_url = False
        if source_url:
            parsed = urlsplit(source_url)
            valid_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password
            if not valid_url:
                raise ValueError("Invalid evidence source URL")
        local_hash = None
        if local_path:
            local_hash = file_sha(audit.inside(run, local_path), snapshot)
        if not valid_url and local_hash is None:
            raise ValueError("Evidence needs an observed source_url or an existing run-local file")
        if not (panel.nonempty(row.get("excerpt")) or row.get("structured_data") is not None):
            raise ValueError("Evidence requires an observed excerpt or structured_data")
        if cfg["cutoff_mode"] == "knowledge_as_of":
            if instant(row.get("available_at"), "available_at") > cutoff:
                raise ValueError("Evidence was not available at the knowledge cutoff")
        if row.get("observation_end") is not None:
            obs_tz = ZoneInfo(row["observation_timezone"]) if row.get("observation_timezone") else default_obs_tz
            end = audit.as_of_time(row["observation_end"], obs_tz)
            if end > cutoff:
                raise ValueError("Evidence observation extends beyond the outcome cutoff")
        bindings[eid] = {"record_sha256": hashed(row), "local_file_sha256": local_hash}
        bound_rows.append(row)
    relations = [r.get("relation") for r in bound_rows if r.get("relation") is not None]
    if relations and verdict in {"supported", "contradicted"}:
        if verdict == "supported" and "supports" not in relations:
            raise ValueError("Verdict 'supported' requires at least one evidence record with relation='supports'")
        if verdict == "contradicted" and "contradicts" not in relations:
            raise ValueError("Verdict 'contradicted' requires at least one evidence record with relation='contradicts'")
    families = sorted({r["source_family"] for r in bound_rows if panel.nonempty(r.get("source_family"))})
    meta = {
        "distinct_source_families": families,
        "distinct_source_family_count": len(families),
        "post_hoc_criteria": post_hoc_criteria,
    }
    return bindings, meta


def recompute(run, claim, saved, policy, snapshot=None, *, strict_freeze_order=False):
    import score_claims as scoring
    scoring.validate_claim(claim)
    cfg = run_config(run, snapshot)
    if not claim["due_for_assessment"] or claim["lifecycle"] in {"pending", "unscorable"}:
        raise ValueError("Pending or unscorable claims cannot receive an adopted verdict")
    if claim["criteria"] is None:
        raise ValueError("Frozen operational criteria are required")
    definition = claim["criteria"]["definition"]
    crit_tz_name = definition["timezone"]
    crit_zone = ZoneInfo(crit_tz_name)
    end = definition.get("window_end")
    if end and audit.as_of_time(end, crit_zone) > instant(cfg["scope"]["as_of"], "as_of"):
        raise ValueError("Prediction deadline has not arrived; the v1 automatic gate does not adopt early resolutions")
    allow_indet = bool(saved.get("terminal_indeterminate")) or (
        isinstance(saved.get("decision"), dict) and saved["decision"].get("verdict") == "indeterminate"
    )
    result_contract = definition.get("result_contract")
    result = panel.consensus(policy, saved.get("votes", []), saved.get("decision"),
                             allow_terminal_indeterminate=allow_indet, result_contract=result_contract)
    if not result["accepted"]:
        raise ValueError("Panel decision is not accepted: " + result["reason"])
    if claim.get("claim_type") == "prediction" and end is None and result["verdict"] == "contradicted":
        if not definition.get("early_falsifiable"):
            raise ValueError("Undated predictions (window_end=null) cannot be adopted as contradicted unless early_falsifiable=true")
    expected = {"claim_id": claim["claim_id"], "criteria_hash": claim["criteria"]["sha256"],
                "as_of": cfg["scope"]["as_of"], "policy_hash": policy["policy_hash"],
                "input_hash": verification_fingerprint(run, claim, snapshot)}
    for key, value in expected.items():
        if result.get(key) != value or saved.get(key) != value:
            raise ValueError("Decision binding mismatch: " + key)
    normalized = result["normalized_result"]
    if result.get("terminal_indeterminate"):
        # Confirmed indeterminate archival does not enter accuracy denominators.
        pass
    elif claim["evaluation_mode"] == "probabilistic":
        if type((normalized or {}).get("event_occurred")) is not bool or result["verdict"] != "supported" or (normalized or {}).get("outcome") is not None:
            raise ValueError("Probabilistic resolution needs a supported event observation, Boolean event_occurred and no categorical outcome")
    elif claim["evaluation_mode"] == "categorical":
        if (normalized or {}).get("outcome", result["verdict"]) != result["verdict"] or (normalized or {}).get("verdict", result["verdict"]) != result["verdict"]:
            raise ValueError("Normalized categorical outcome disagrees with the accepted verdict")
    else:
        raise ValueError("An adopted verdict requires a scoring evaluation mode")
    if not result.get("terminal_indeterminate") and not scoring.quality_allows_verdict(claim):
        raise ValueError("Coordinator evidence quality review is missing or blocks a definite verdict")
    ids = set(claim["evidence_ids"])
    if result.get("decision"):
        # Do not force overruled minority votes' evidence into validation or canonical claim evidence_ids.
        ids.update(result["decision"].get("evidence_ids", []))
    else:
        for vote in result["votes"]:
            ids.update(vote["evidence_ids"])
    if not ids and not result.get("terminal_indeterminate"):
        raise ValueError("Accepted verdict has no evidence")
    bindings, ev_meta = evidence_bindings(
        run, claim["claim_id"], ids, cfg, snapshot,
        criteria_timezone=crit_tz_name, frozen_at=claim["criteria"].get("frozen_at"),
        verdict=result["verdict"], strict_freeze_order=strict_freeze_order,
    )
    return result, bindings, ev_meta


def verify_acceptance(run, claim, policy_path=None, snapshot=None):
    """Raise on any broken acceptance chain; return the recomputed accepted panel result."""
    run = Path(run).resolve()
    policy_path = Path(policy_path or run / "config/model-policy.json").resolve()
    if snapshot is not None:
        snapshot.check_run(run)
        if policy_path not in snapshot.policies:
            snapshot.policies[policy_path] = panel.load_policy(policy_path)
        policy = snapshot.policies[policy_path]
    else:
        policy = panel.load_policy(policy_path)
    acceptance = claim.get("acceptance")
    if not isinstance(acceptance, dict):
        raise ValueError("Scored resolution has no adopted panel acceptance")
    path = audit.inside(run, acceptance.get("decision_path"))
    if file_sha(path, snapshot) != acceptance.get("decision_sha256") or acceptance.get("policy_hash") != policy["policy_hash"]:
        raise ValueError("Accepted decision/policy fingerprint changed")
    artifact = audit.read_json(path)
    result, bindings, _ = recompute(run, claim, artifact["consensus"], policy, snapshot)
    adopted = artifact["adoption"]
    if bindings != adopted["evidence_bindings"] or set(claim["evidence_ids"]) != set(bindings):
        raise ValueError("Accepted evidence records or references changed")
    if claim["evidence_quality"] != adopted["evidence_quality"] or claim.get("evidence_exception") != adopted.get("evidence_exception"):
        raise ValueError("Evidence quality review changed after adoption")
    if claim["lifecycle"] != "resolved" or claim["review_state"] != "accepted" or claim.get("resolved_at") != adopted["adopted_at"]:
        raise ValueError("Claim state does not match its adoption")
    if result.get("terminal_indeterminate"):
        if claim["outcome"] != "indeterminate":
            raise ValueError("Canonical verdict differs from confirmed indeterminate decision")
    elif claim["evaluation_mode"] == "probabilistic":
        if claim["outcome"] is not None or claim["event_occurred"] != result["normalized_result"]["event_occurred"]:
            raise ValueError("Probabilistic outcome differs from the accepted observation")
    elif claim["outcome"] != result["verdict"]:
        raise ValueError("Canonical verdict differs from the accepted panel decision")
    history = audit.inside(run, adopted["history_path"])
    if hashed(audit.read_json(history)) != adopted["before_claim_hash"]:
        raise ValueError("Pre-adoption claim history changed or disappeared")
    return result


def immutable_json(run, folder, value):
    data = panel.canonical(value) + "\n"
    sha = hashlib.sha256(data.encode("utf-8")).hexdigest()
    name = folder + "/" + sha + ".json"
    path = audit.inside(run, name)
    if path.exists():
        if path.read_text(encoding="utf-8") != data:
            raise ValueError("Immutable history path has conflicting bytes")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        audit.atomic_text(path, data)
    return name, sha


def adopt(run, claim_id, consensus_path, policy_path=None, strict_freeze_order=False):
    import score_claims as scoring
    run = Path(run).resolve()
    with audit.coordinator_lock(run):
        claims = rows_by_id(run, "claims.jsonl", "claim_id")
        if claim_id not in claims:
            raise ValueError("Unknown claim_id")
        claim = claims[claim_id]
        policy = panel.load_policy(policy_path or run / "config/model-policy.json")
        saved = audit.read_json(Path(consensus_path))
        result, bindings, ev_meta = recompute(run, claim, saved, policy, strict_freeze_order=strict_freeze_order)
        if claim.get("acceptance"):
            verify_acceptance(run, claim, policy_path)
            prior = audit.read_json(audit.inside(run, claim["acceptance"]["decision_path"]))
            if hashed(prior["consensus"]) != hashed(saved):
                raise ValueError("Different verdict already adopted; use `reopen` first or create a new run/version")
            return {"adopted": True, "idempotent": True, "claim_id": claim_id, "acceptance": claim["acceptance"]}
        candidate = copy.deepcopy(claim)
        candidate.update(lifecycle="resolved", review_state="accepted", evidence_ids=sorted(bindings), resolved_at=audit.now())
        if result.get("terminal_indeterminate"):
            candidate.update(outcome="indeterminate", event_occurred=None)
        elif claim["evaluation_mode"] == "probabilistic":
            candidate.update(outcome=None, event_occurred=result["normalized_result"]["event_occurred"])
        else:
            candidate.update(outcome=result["verdict"], event_occurred=None)
        scoring.validate_claim(candidate)
        history_path, _ = immutable_json(run, "history/claims", claim)
        warnings = []
        if ev_meta["distinct_source_family_count"] == 1 and (claim.get("evidence_quality") or {}).get("independence") == 1:
            warnings.append("single_source_family")
        if ev_meta["post_hoc_criteria"]:
            warnings.append("post_hoc_criteria")
        supersedes = None
        if claim.get("reopen_history"):
            supersedes = claim["reopen_history"][-1].get("prior_decision_sha256")
        artifact = {"schema_version": 1, "consensus": saved, "adoption": {
            "adopted_at": candidate["resolved_at"], "before_claim_hash": hashed(claim), "history_path": history_path,
            "evidence_bindings": bindings, "evidence_quality": claim["evidence_quality"],
            "evidence_exception": claim.get("evidence_exception"),
            "distinct_source_families": ev_meta["distinct_source_families"],
            "distinct_source_family_count": ev_meta["distinct_source_family_count"],
            "post_hoc_criteria": ev_meta["post_hoc_criteria"],
            "supersedes_decision_sha256": supersedes,
            "warnings": warnings}}
        decision_path, decision_sha = immutable_json(run, "reviews/decisions", artifact)
        candidate["acceptance"] = {"decision_path": decision_path, "decision_sha256": decision_sha, "policy_hash": policy["policy_hash"]}
        verify_acceptance(run, candidate, policy_path)
        claims[claim_id] = candidate
        audit.write_jsonl(run / "claims.jsonl", list(claims.values()))
        audit.event(run, "verdict_adopted", claim_id=claim_id, decision_sha256=decision_sha,
                    policy_hash=policy["policy_hash"], supersedes=supersedes, warnings=warnings)
        return {"adopted": True, "idempotent": False, "claim_id": claim_id, "acceptance": candidate["acceptance"], "warnings": warnings}


def reopen(run, claim_id, reason, actor, note="", refreeze=False):
    allowed_reasons = {"data_revision", "new_evidence", "attribution_error", "human_override", "criteria_defect"}
    if reason not in allowed_reasons:
        raise ValueError(f"reopen reason must be one of {sorted(allowed_reasons)}")
    if not panel.nonempty(actor):
        raise ValueError("reopen requires nonempty actor")
    run = Path(run).resolve()
    with audit.coordinator_lock(run):
        claims = rows_by_id(run, "claims.jsonl", "claim_id")
        if claim_id not in claims:
            raise ValueError("Unknown claim_id")
        claim = claims[claim_id]
        if not claim.get("acceptance"):
            raise ValueError("Claim has no adopted verdict to reopen")
        prior_sha = claim["acceptance"]["decision_sha256"]
        history_path, _ = immutable_json(run, "history/claims", claim)
        reopened = copy.deepcopy(claim)
        reopened.setdefault("reopen_history", []).append({
            "reopened_at": audit.now(), "reason": reason, "actor": actor,
            "note": note, "prior_decision_sha256": prior_sha, "history_path": history_path,
        })
        reopened["acceptance"] = None
        reopened["outcome"] = None
        reopened["event_occurred"] = None
        reopened["resolved_at"] = None
        reopened["review_state"] = "needs_review"
        if refreeze:
            reopened["criteria"] = None
            reopened["accountability_eligible"] = False
            reopened["due_for_assessment"] = False
            reopened["lifecycle"] = "pending"
            reopened["operationalization_status"] = "not_assessed"
        else:
            reopened["lifecycle"] = "ready"
        claims[claim_id] = reopened
        audit.write_jsonl(run / "claims.jsonl", list(claims.values()))
        audit.event(run, "verdict_reopened", claim_id=claim_id, reason=reason, actor=actor,
                    prior_decision_sha256=prior_sha, refreeze=refreeze)
        return {"reopened": True, "claim_id": claim_id, "prior_decision_sha256": prior_sha, "lifecycle": reopened["lifecycle"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fingerprint", "adopt"):
        command = sub.add_parser(name)
        command.add_argument("--run", required=True)
        command.add_argument("--claim-id", required=True)
        if name == "adopt":
            command.add_argument("--consensus", required=True)
            command.add_argument("--policy")
            command.add_argument("--strict-freeze-order", action="store_true")
    reopen_cmd = sub.add_parser("reopen", help="Reopen an adopted verdict with immutable history and audit log")
    reopen_cmd.add_argument("--run", required=True)
    reopen_cmd.add_argument("--claim-id", required=True)
    reopen_cmd.add_argument("--reason", required=True, choices=["data_revision", "new_evidence", "attribution_error", "human_override", "criteria_defect"])
    reopen_cmd.add_argument("--actor", required=True)
    reopen_cmd.add_argument("--note", default="")
    reopen_cmd.add_argument("--refreeze", action="store_true")
    args = parser.parse_args(argv)
    try:
        run = Path(args.run).resolve()
        if args.command == "reopen":
            result = reopen(run, args.claim_id, args.reason, args.actor, args.note, args.refreeze)
        elif args.command == "fingerprint":
            claim = rows_by_id(run, "claims.jsonl", "claim_id")[args.claim_id]
            result = {"claim_id": args.claim_id, "input_hash": verification_fingerprint(run, claim)}
        else:
            result = adopt(run, args.claim_id, args.consensus, args.policy, strict_freeze_order=args.strict_freeze_order)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
