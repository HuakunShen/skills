#!/usr/bin/env python3
"""Adopt only reproducible, evidenced panel decisions into the canonical claim ledger.

The v1 automatic gate conservatively waits for window_end; it does not implement
irreversible early-event adoption. A VerificationSnapshot is only valid during
one coordinator-locked, read-only scoring pass; discard it before any mutation.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import audit_run as audit
import model_panel as panel

SEMANTIC_FIELDS = ("claim_id", "subject_id", "text", "domain", "claim_type", "empirical",
                   "endorsement", "attribution_confidence", "accountability_eligible", "quantifiability",
                   "verifiability", "evaluation_mode", "probability", "probability_origin", "due_for_assessment")


class VerificationSnapshot:
    """Per-pass cache, never global/persisted. Caller holds coordinator_lock.

    Use only for one read-only pass over one run. Discard before mutations;
    other writers must honor the same coordinator lock. Failed reads/checks are
    not cached. This is not a filesystem change watcher or a transaction engine.
    """
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
    return hashlib.sha256(panel.canonical(value).encode("utf-8")).hexdigest()


def file_sha(path, snapshot=None):
    path = Path(path).resolve()
    if snapshot is not None and path in snapshot.file_hashes:
        return snapshot.file_hashes[path]
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    if snapshot is not None:
        snapshot.file_hashes[path] = value
    return value


def rows_by_id(run, filename, key, snapshot=None):
    if snapshot is not None:
        snapshot.check_run(run)
        if (filename, key) in snapshot.rows:
            return snapshot.rows[filename, key]
    value = audit.unique(audit.read_jsonl(run / filename), key, filename)
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


def evidence_bindings(run, claim_id, evidence_ids, cfg, snapshot=None):
    evidence = rows_by_id(run, "evidence.jsonl", "evidence_id", snapshot)
    cutoff = instant(cfg["scope"]["as_of"], "as_of")
    bindings = {}
    for eid in sorted(evidence_ids):
        if eid not in evidence:
            raise ValueError("Missing evidence record: " + eid)
        row = evidence[eid]
        if claim_id not in row.get("claim_ids", []) and row.get("claim_id") != claim_id:
            raise ValueError("Evidence is not linked to this claim: " + eid)
        retrieved = instant(row.get("retrieved_at"), "retrieved_at")
        if retrieved > datetime.now(timezone.utc):
            raise ValueError("Evidence retrieval timestamp is in the future")
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
            end = audit.as_of_time(row["observation_end"], ZoneInfo(cfg["scope"]["timezone"]))
            if end > cutoff:
                raise ValueError("Evidence observation extends beyond the outcome cutoff")
        bindings[eid] = {"record_sha256": hashed(row), "local_file_sha256": local_hash}
    return bindings


def recompute(run, claim, saved, policy, snapshot=None):
    import score_claims as scoring
    scoring.validate_claim(claim)
    cfg = run_config(run, snapshot)
    if not claim["due_for_assessment"] or claim["lifecycle"] in {"pending", "unscorable"}:
        raise ValueError("Pending or unscorable claims cannot receive an adopted verdict")
    if claim["criteria"] is None:
        raise ValueError("Frozen operational criteria are required")
    end = claim["criteria"]["definition"].get("window_end")
    if end and audit.as_of_time(end, ZoneInfo(cfg["scope"]["timezone"])) > instant(cfg["scope"]["as_of"], "as_of"):
        raise ValueError("Prediction deadline has not arrived; the v1 automatic gate does not adopt early resolutions")
    result = panel.consensus(policy, saved.get("votes", []), saved.get("decision"))
    if not result["accepted"]:
        raise ValueError("Panel decision is not accepted: " + result["reason"])
    expected = {"claim_id": claim["claim_id"], "criteria_hash": claim["criteria"]["sha256"],
                "as_of": cfg["scope"]["as_of"], "policy_hash": policy["policy_hash"],
                "input_hash": verification_fingerprint(run, claim, snapshot)}
    for key, value in expected.items():
        if result.get(key) != value or saved.get(key) != value:
            raise ValueError("Decision binding mismatch: " + key)
    normalized = result["normalized_result"]
    if claim["evaluation_mode"] == "probabilistic":
        if type(normalized.get("event_occurred")) is not bool or result["verdict"] != "supported" or normalized.get("outcome") is not None:
            raise ValueError("Probabilistic resolution needs a supported event observation, Boolean event_occurred and no categorical outcome")
    elif claim["evaluation_mode"] == "categorical":
        if normalized.get("outcome", result["verdict"]) != result["verdict"] or normalized.get("verdict", result["verdict"]) != result["verdict"]:
            raise ValueError("Normalized categorical outcome disagrees with the accepted verdict")
    else:
        raise ValueError("An adopted verdict requires a scoring evaluation mode")
    if not scoring.quality_allows_verdict(claim):
        raise ValueError("Coordinator evidence quality review is missing or blocks a definite verdict")
    ids = set(claim["evidence_ids"])
    for vote in result["votes"]:
        ids.update(vote["evidence_ids"])
    if result.get("decision"):
        ids.update(result["decision"].get("evidence_ids", []))
        prior = result["decision"].get("prior_judge_decision")
        if isinstance(prior, dict):
            ids.update(prior.get("evidence_ids", []))
    if not ids:
        raise ValueError("Accepted verdict has no evidence")
    return result, evidence_bindings(run, claim["claim_id"], ids, cfg, snapshot)


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
    result, bindings = recompute(run, claim, artifact["consensus"], policy, snapshot)
    adopted = artifact["adoption"]
    if bindings != adopted["evidence_bindings"] or set(claim["evidence_ids"]) != set(bindings):
        raise ValueError("Accepted evidence records or references changed")
    if claim["evidence_quality"] != adopted["evidence_quality"] or claim.get("evidence_exception") != adopted.get("evidence_exception"):
        raise ValueError("Evidence quality review changed after adoption")
    if claim["lifecycle"] != "resolved" or claim["review_state"] != "accepted" or claim.get("resolved_at") != adopted["adopted_at"]:
        raise ValueError("Claim state does not match its adoption")
    if claim["evaluation_mode"] == "probabilistic":
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


def adopt(run, claim_id, consensus_path, policy_path=None):
    import score_claims as scoring
    run = Path(run).resolve()
    with audit.coordinator_lock(run):
        claims = rows_by_id(run, "claims.jsonl", "claim_id")
        if claim_id not in claims:
            raise ValueError("Unknown claim_id")
        claim = claims[claim_id]
        policy = panel.load_policy(policy_path or run / "config/model-policy.json")
        saved = audit.read_json(Path(consensus_path))
        result, bindings = recompute(run, claim, saved, policy)
        if claim.get("acceptance"):
            verify_acceptance(run, claim, policy_path)
            prior = audit.read_json(audit.inside(run, claim["acceptance"]["decision_path"]))
            if hashed(prior["consensus"]) != hashed(saved):
                raise ValueError("Different verdict already adopted; preserve history and create a new run/version")
            return {"adopted": True, "idempotent": True, "claim_id": claim_id, "acceptance": claim["acceptance"]}
        candidate = copy.deepcopy(claim)
        candidate.update(lifecycle="resolved", review_state="accepted", evidence_ids=sorted(bindings), resolved_at=audit.now())
        if claim["evaluation_mode"] == "probabilistic":
            candidate.update(outcome=None, event_occurred=result["normalized_result"]["event_occurred"])
        else:
            candidate.update(outcome=result["verdict"], event_occurred=None)
        scoring.validate_claim(candidate)
        history_path, _ = immutable_json(run, "history/claims", claim)
        artifact = {"schema_version": 1, "consensus": saved, "adoption": {
            "adopted_at": candidate["resolved_at"], "before_claim_hash": hashed(claim), "history_path": history_path,
            "evidence_bindings": bindings, "evidence_quality": claim["evidence_quality"],
            "evidence_exception": claim.get("evidence_exception")}}
        decision_path, decision_sha = immutable_json(run, "reviews/decisions", artifact)
        candidate["acceptance"] = {"decision_path": decision_path, "decision_sha256": decision_sha, "policy_hash": policy["policy_hash"]}
        verify_acceptance(run, candidate, policy_path)
        claims[claim_id] = candidate
        audit.write_jsonl(run / "claims.jsonl", list(claims.values()))
        audit.event(run, "verdict_adopted", claim_id=claim_id, decision_sha256=decision_sha, policy_hash=policy["policy_hash"])
        return {"adopted": True, "idempotent": False, "claim_id": claim_id, "acceptance": candidate["acceptance"]}


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
    args = parser.parse_args(argv)
    try:
        if args.command == "adopt":
            result = adopt(args.run, args.claim_id, args.consensus, args.policy)
        else:
            run = Path(args.run).resolve()
            with audit.coordinator_lock(run):
                claim = rows_by_id(run, "claims.jsonl", "claim_id")[args.claim_id]
                result = {"claim_id": args.claim_id, "input_hash": verification_fingerprint(run, claim)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
