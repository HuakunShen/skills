#!/usr/bin/env python3
"""Compute transparent descriptive audit metrics. No model or network calls."""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import tempfile


POLICY = {
    "minimum_categorical_sample": 30,
    "minimum_empirical_claims": 30,
    "minimum_adjudication_coverage": 0.70,
    "minimum_source_availability": 0.80,
    "minimum_extraction_coverage": 0.90,
    "minimum_evidence_quality": 2 / 3,
    "support_weight": 0.75,
    "accountability_weight": 0.25,
}
KINDS = {"factual", "prediction", "causal", "recommendation", "value_judgment",
         "preference", "hypothetical", "rhetorical", "reported", "ambiguous"}
LIFECYCLES = {"pending", "ready", "awaiting_evidence", "resolved", "unscorable", "disputed"}
OUTCOMES = {"supported", "contradicted", "mixed", "indeterminate", None}


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(text):
    def bad(value):
        raise ValueError("Non-finite JSON constant: " + value)
    return json.loads(text, parse_constant=bad)


def load_rows(path, key):
    rows, seen = [], set()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = strict_json(line)
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key]:
            raise ValueError(f"Line {n}: nonempty {key} required")
        if row[key] in seen:
            raise ValueError(f"Duplicate {key}: {row[key]}")
        seen.add(row[key])
        rows.append(row)
    return rows


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_claim(c):
    cid = c.get("claim_id", "unknown")
    required = {"schema_version", "claim_id", "claim_type", "subject_id", "occurrence_ids", "text", "domain",
                "empirical", "endorsement", "attribution_confidence", "accountability_eligible",
                "quantifiability", "verifiability", "lifecycle", "outcome", "due_for_assessment",
                "evaluation_mode", "probability", "probability_origin", "event_occurred",
                "criteria", "evidence_ids", "evidence_quality", "review_state"}
    missing = sorted(required - set(c))
    if missing:
        raise ValueError(f"{cid}: missing {missing}")
    if c["schema_version"] != 1:
        raise ValueError(f"{cid}: unsupported schema_version")
    for key in ("empirical", "accountability_eligible", "due_for_assessment"):
        if type(c[key]) is not bool:
            raise ValueError(f"{cid}: {key} must be boolean")
    enums = {
        "claim_type": KINDS, "lifecycle": LIFECYCLES, "outcome": OUTCOMES,
        "quantifiability": {"numeric", "operationalizable", "qualitative", "none", "unclear"},
        "verifiability": {"verifiable", "conditional", "unverifiable", "unclear"},
        "endorsement": {"endorsed", "quoted", "rejected", "unclear"},
        "attribution_confidence": {"high", "medium", "low"},
        "evaluation_mode": {"categorical", "probabilistic", "none"},
        "probability_origin": {"explicit", "inferred", "none"},
        "review_state": {"unreviewed", "accepted", "needs_review"},
    }
    for key, allowed in enums.items():
        if c[key] not in allowed:
            raise ValueError(f"{cid}: invalid {key}")
    for key in ("claim_id", "subject_id", "text", "domain"):
        if not isinstance(c[key], str) or not c[key].strip():
            raise ValueError(f"{cid}: {key} must be nonempty text")
    for key in ("occurrence_ids", "evidence_ids"):
        if not isinstance(c[key], list) or any(not isinstance(x, str) or not x for x in c[key]):
            raise ValueError(f"{cid}: invalid {key}")
        if len(set(c[key])) != len(c[key]):
            raise ValueError(f"{cid}: duplicate {key}")
    if not c["occurrence_ids"]:
        raise ValueError(f"{cid}: no original occurrences")
    p = c["probability"]
    if p is not None and (not finite_number(p) or not 0 <= p <= 1):
        raise ValueError(f"{cid}: probability must be null or in [0,1]")
    if c["probability_origin"] == "explicit" and p is None:
        raise ValueError(f"{cid}: explicit probability missing")
    if c["probability_origin"] == "none" and p is not None:
        raise ValueError(f"{cid}: probability origin missing")
    if c["probability_origin"] == "explicit" and c["evaluation_mode"] != "probabilistic":
        raise ValueError(f"{cid}: explicit probability belongs to probabilistic evaluation")
    if c["claim_type"] in {"preference", "value_judgment", "hypothetical", "rhetorical"} and c["empirical"]:
        raise ValueError(f"{cid}: split empirical premises from subjective/hypothetical expressions")
    if c["event_occurred"] is not None and type(c["event_occurred"]) is not bool:
        raise ValueError(f"{cid}: event_occurred must be boolean or null")
    criteria = c["criteria"]
    if criteria is not None:
        if not isinstance(criteria, dict) or not isinstance(criteria.get("definition"), dict):
            raise ValueError(f"{cid}: invalid criteria")
        definition = criteria["definition"]
        if not {"target", "predicate", "window_start", "window_end", "timezone", "condition", "resolution_basis"} <= set(definition):
            raise ValueError(f"{cid}: criteria missing operational definition fields")
        if any(not isinstance(definition[k], str) or not definition[k].strip() for k in ("target", "predicate", "timezone")):
            raise ValueError(f"{cid}: criteria target/predicate/timezone required")
        if definition["resolution_basis"] not in {"explicit", "interpretation"}:
            raise ValueError(f"{cid}: invalid criteria resolution_basis")
        expected = hashlib.sha256(canonical(criteria["definition"])).hexdigest()
        if criteria.get("sha256") != expected or not criteria.get("frozen_at") or not criteria.get("version"):
            raise ValueError(f"{cid}: missing or mismatched frozen criteria fingerprint")
        frozen = datetime.fromisoformat(criteria["frozen_at"].replace("Z", "+00:00"))
        if frozen.tzinfo is None:
            raise ValueError(f"{cid}: frozen_at requires timezone")
    if c["accountability_eligible"] and (not c["empirical"] or criteria is None or
            c["verifiability"] not in {"verifiable", "conditional"}):
        raise ValueError(f"{cid}: accountability requires empirical, operationalized criteria")
    if c["lifecycle"] == "pending" and c["due_for_assessment"]:
        raise ValueError(f"{cid}: pending cannot be due_for_assessment")
    if c["due_for_assessment"] and not c["accountability_eligible"]:
        raise ValueError(f"{cid}: due_for_assessment requires operationalized accountable claim")
    if c["lifecycle"] != "resolved" and c["outcome"] is not None:
        raise ValueError(f"{cid}: unresolved current verdict must be null; retain old verdict in history")
    if c["lifecycle"] == "resolved":
        if not c["due_for_assessment"] or criteria is None or not c["evidence_ids"]:
            raise ValueError(f"{cid}: resolved claim requires due status, criteria and evidence")
        if not c.get("resolved_at"):
            raise ValueError(f"{cid}: resolved_at required")
        resolved = datetime.fromisoformat(c["resolved_at"].replace("Z", "+00:00"))
        if resolved.tzinfo is None or resolved < frozen:
            raise ValueError(f"{cid}: resolution must have timezone and follow criteria freeze")
        if c["evaluation_mode"] == "categorical" and c["outcome"] is None:
            raise ValueError(f"{cid}: categorical verdict missing")
        if c["evaluation_mode"] == "probabilistic" and type(c["event_occurred"]) is not bool:
            raise ValueError(f"{cid}: resolved probability requires event outcome")
        if c["evaluation_mode"] == "none":
            raise ValueError(f"{cid}: cannot resolve evaluation_mode=none")
    quality = c["evidence_quality"]
    if quality is not None:
        if not isinstance(quality, dict) or any(
                not finite_number(quality.get(k)) or quality[k] not in (0, 0.5, 1)
                for k in ("directness", "independence", "traceability")):
            raise ValueError(f"{cid}: evidence_quality requires three scores from 0,0.5,1")


def ratio(n, d):
    return {"value": n / d if d else None, "numerator": n, "denominator": d}


def quality_allows_verdict(c):
    q = c["evidence_quality"]
    if q is None:
        return False
    if min(q[k] for k in ("directness", "independence", "traceability")) >= 0.5:
        return True
    exception = c.get("evidence_exception", {})
    return isinstance(exception, dict) and exception.get("reviewed") is True and bool(str(exception.get("reason", "")).strip())


def core_metrics(claims):
    eligible = [c for c in claims if c["empirical"] and c["endorsement"] == "endorsed"
                and c["attribution_confidence"] == "high"]
    due = [c for c in eligible if c["accountability_eligible"] and c["due_for_assessment"]]
    resolved = [c for c in due if c["lifecycle"] == "resolved" and c["review_state"] == "accepted"
                and quality_allows_verdict(c)]
    categorical = [c for c in resolved if c["evaluation_mode"] == "categorical"
                   and c["outcome"] in {"supported", "contradicted", "mixed"}]
    probability = [c for c in resolved if c["evaluation_mode"] == "probabilistic"
                   and c["probability_origin"] == "explicit"]
    adjudicated = categorical + probability
    counts = {v: sum(c["outcome"] == v for c in categorical)
              for v in ("supported", "contradicted", "mixed")}
    s, bad, partial = (counts[k] for k in ("supported", "contradicted", "mixed"))
    qualities = [sum(c["evidence_quality"][k] for k in ("directness", "independence", "traceability"))/3
                 for c in adjudicated if c["evidence_quality"] is not None]
    briers = [(c["probability"] - int(c["event_occurred"])) ** 2 for c in probability]
    return {
        "total_canonical_claims": len(claims), "endorsed_empirical_claims": len(eligible),
        "categorical_n": len(categorical), "categorical_counts": counts,
        "strict_support_rate": ratio(s, s + bad + partial),
        "partial_share": ratio(partial, s + bad + partial),
        "binary_accuracy_excluding_mixed": ratio(s, s + bad),
        "accountability": ratio(sum(c["accountability_eligible"] for c in eligible), len(eligible)),
        "adjudication_coverage": ratio(len(adjudicated), len(due)),
        "brier": {"value": statistics.mean(briers) if briers else None, "n": len(briers),
                  "lower_is_better": True, "explicit_probabilities_only": True},
        "evidence_quality": {"mean": statistics.mean(qualities) if qualities else None,
                             "assessed_n": len(qualities), "expected_n": len(adjudicated)},
        "lifecycle_counts": {v: sum(c["lifecycle"] == v for c in eligible) for v in sorted(LIFECYCLES)},
        "excluded_from_categorical_accuracy": len(claims) - len(categorical),
        "unaccepted_due_claims": sum(c["review_state"] != "accepted" for c in due),
        "quality_blocked_resolutions": sum(c["lifecycle"] == "resolved" and not quality_allows_verdict(c) for c in due),
    }


def validate_coverage(c):
    keys = ("eligible_sources", "acquired_sources", "extracted_sources", "unresolved_review_issues")
    for key in keys:
        if type(c.get(key)) is not int or c[key] < 0:
            raise ValueError(f"coverage: {key} must be a nonnegative integer")
    if not 0 <= c["extracted_sources"] <= c["acquired_sources"] <= c["eligible_sources"]:
        raise ValueError("coverage: require extracted <= acquired <= eligible")
    if type(c.get("inventory_complete")) is not bool:
        raise ValueError("coverage: inventory_complete boolean required")


def validate_policy(p):
    if set(p) != set(POLICY):
        raise ValueError("Scoring policy keys must exactly match default keys")
    for k, v in p.items():
        if not finite_number(v) or v < 0:
            raise ValueError(f"Scoring policy {k}: finite nonnegative number required")
        if k in {"minimum_categorical_sample", "minimum_empirical_claims"}:
            if type(v) is not int or v < 1:
                raise ValueError(f"Scoring policy {k}: positive integer required")
        elif v > 1:
            raise ValueError(f"Scoring policy {k}: must be <=1")
    if not math.isclose(p["support_weight"] + p["accountability_weight"], 1):
        raise ValueError("Composite weights must sum to one")


def calculate(claims, coverage, *, composite=False, policy=None, occurrences=None, subject_id=None):
    policy = POLICY.copy() if policy is None else policy
    validate_policy(policy)
    seen = set()
    referenced_occurrences = set()
    for c in claims:
        validate_claim(c)
        if c["claim_id"] in seen:
            raise ValueError("Duplicate canonical claim ID")
        seen.add(c["claim_id"])
        if referenced_occurrences.intersection(c["occurrence_ids"]):
            raise ValueError("An occurrence_id cannot belong to multiple canonical claims")
        referenced_occurrences.update(c["occurrence_ids"])
    if subject_id is not None:
        claims = [c for c in claims if c["subject_id"] == subject_id]
        if not claims:
            raise ValueError("No claims found for selected subject_id")
        selected_ids = {c["claim_id"] for c in claims}
        if occurrences is not None:
            occurrences = [o for o in occurrences if o.get("claim_id") in selected_ids]
    elif len({c["subject_id"] for c in claims}) > 1:
        raise ValueError("Multiple subject_id values: select one subject to avoid combining speakers")
    validate_coverage(coverage)
    metrics = core_metrics(claims)
    metrics["subject_id"] = claims[0]["subject_id"] if claims else subject_id
    source = ratio(coverage["acquired_sources"], coverage["eligible_sources"])
    extraction = ratio(coverage["extracted_sources"], coverage["eligible_sources"])
    metrics["source_availability"] = source
    metrics["extraction_coverage"] = extraction
    blockers = []
    checks = [
        (metrics["categorical_n"], "minimum_categorical_sample"),
        (metrics["endorsed_empirical_claims"], "minimum_empirical_claims"),
        (metrics["adjudication_coverage"]["value"], "minimum_adjudication_coverage"),
        (source["value"], "minimum_source_availability"),
        (extraction["value"], "minimum_extraction_coverage"),
        (metrics["evidence_quality"]["mean"], "minimum_evidence_quality"),
    ]
    for value, key in checks:
        if value is None or value < policy[key]:
            blockers.append(key)
    if not coverage["inventory_complete"]:
        blockers.append("inventory_incomplete")
    if coverage["unresolved_review_issues"] or metrics["unaccepted_due_claims"]:
        blockers.append("unresolved_review_issues")
    if metrics["quality_blocked_resolutions"]:
        blockers.append("evidence_quality_floor")
    if metrics["evidence_quality"]["assessed_n"] != metrics["evidence_quality"]["expected_n"]:
        blockers.append("missing_evidence_quality")
    value = None
    if composite and not blockers:
        value = 100 * (policy["support_weight"] * metrics["strict_support_rate"]["value"] +
                       policy["accountability_weight"] * metrics["accountability"]["value"])
    metrics["composite"] = {"value": value, "requested": composite, "scale": [0, 100],
        "blockers": blockers, "policy": policy, "label": "custom_descriptive_index_not_personal_truth"}
    metrics["by_domain"] = {d: core_metrics([c for c in claims if c["domain"] == d])
                            for d in sorted({c["domain"] for c in claims})}
    metrics["noncheckable_expression_share"] = None
    if occurrences is not None:
        index = {c["claim_id"]: c for c in claims}
        count = numerator = 0
        ids = set()
        occurrence_map = {o.get("occurrence_id"): o for o in occurrences}
        for o in occurrences:
            oid = o.get("occurrence_id")
            if not oid or oid in ids:
                raise ValueError("Missing or repeated occurrence_id")
            ids.add(oid)
            c = index.get(o.get("claim_id"))
            if c is None or oid not in c["occurrence_ids"]:
                raise ValueError(f"Occurrence {oid} has an invalid canonical reference")
            if o.get("technical_duplicate_of"):
                target = occurrence_map.get(o["technical_duplicate_of"])
                if target is None or target.get("technical_duplicate_of") or target.get("claim_id") != o["claim_id"]:
                    raise ValueError("Technical duplicate must reference a retained original occurrence of the same claim")
                continue
            if c["empirical"] and c["endorsement"] == "endorsed" and c["attribution_confidence"] == "high" and o.get("endorsement") == "endorsed":
                count += 1
                numerator += not c["accountability_eligible"]
        expected = {o for c in claims for o in c["occurrence_ids"]}
        if expected != ids:
            raise ValueError("Occurrences ledger must cover every canonical occurrence exactly")
        metrics["noncheckable_expression_share"] = ratio(numerator, count)
    metrics["uncertainty_note"] = "Descriptive corpus metrics; no normal-distribution or independent-sample claim. Model spread is separate."
    return metrics


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".metrics-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def csv_text(claims):
    cols = ["claim_id", "text", "domain", "claim_type", "quantifiability", "verifiability",
            "lifecycle", "outcome", "probability", "occurrence_ids", "evidence_ids"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=cols)
    writer.writeheader()
    for c in claims:
        row = {}
        for k in cols:
            v = c.get(k)
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            if isinstance(v, str) and (v.lstrip().startswith(("=", "+", "-", "@")) or v.startswith(("\t", "\r", "\n"))):
                v = "'" + v
            row[k] = v
        writer.writerow(row)
    return stream.getvalue()


def score_run(args):
    """Verify accepted resolutions and calculate from one coordinator-locked snapshot."""
    import audit_run as audit
    from adopt_verdict import VerificationSnapshot, verify_acceptance

    run = Path(args.run).resolve() if args.run else Path(args.claims).resolve().parent
    inputs = {Path(x).resolve() for x in
              [args.claims, args.coverage, args.occurrences, args.scoring_policy, args.model_policy] if x}
    outputs = [Path(x).resolve() for x in [args.out, args.csv] if x]
    if any(x in inputs for x in outputs) or len(set(outputs)) != len(outputs):
        raise ValueError("Outputs must not overwrite inputs or each other")
    protected = {"config", "sources", "raw", "state", "batches", "tasks", "reviews", "history", "evidence", "media", "work", "sync"}
    for path in outputs:
        try:
            relative = path.relative_to(run)
        except ValueError:
            continue
        if len(relative.parts) <= 1 or relative.parts[0] in protected:
            raise ValueError("Write metrics/exports to reports/ or another output directory, not audit records")
    with audit.coordinator_lock(run):
        cfg = audit.config(run)
        claims = load_rows(args.claims, "claim_id")
        coverage = strict_json(Path(args.coverage).read_text(encoding="utf-8"))
        occurrences = load_rows(args.occurrences, "occurrence_id") if args.occurrences else None
        policy = strict_json(Path(args.scoring_policy).read_text(encoding="utf-8")) if args.scoring_policy else None
        selected = [c for c in claims if args.subject_id is None or c.get("subject_id") == args.subject_id]
        snapshot = VerificationSnapshot(run)
        verified = 0
        for claim in selected:
            if claim.get("lifecycle") == "resolved" and claim.get("review_state") == "accepted":
                verify_acceptance(run, claim, policy_path=args.model_policy, snapshot=snapshot)
                verified += 1
        metrics = calculate(claims, coverage, composite=args.composite, policy=policy,
                            occurrences=occurrences, subject_id=args.subject_id)
        metrics["acceptance_verification"] = {
            "verified_resolutions": verified, "as_of": cfg["scope"]["as_of"],
            "policy": "recomputed_consensus_and_bound_evidence",
            "semantic_evidence_truth_verified_by_script": False,
        }
        metrics["input_sha256"] = {Path(x).name: hashlib.sha256(Path(x).read_bytes()).hexdigest()
                                   for x in [args.claims, args.coverage, args.occurrences] if x}
        atomic_write(args.out, json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        if args.csv:
            atomic_write(args.csv, csv_text(selected))
    return metrics


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--claims", required=True)
    p.add_argument("--run", help="Audit run directory; defaults to the claims file's parent")
    p.add_argument("--coverage", required=True)
    p.add_argument("--occurrences")
    p.add_argument("--subject-id", help="Required when the corpus contains multiple speakers' canonical claims")
    p.add_argument("--out", required=True)
    p.add_argument("--csv")
    p.add_argument("--composite", action="store_true")
    p.add_argument("--scoring-policy", help="Full JSON override of the documented heuristic scoring gates")
    p.add_argument("--model-policy", help="Frozen model policy; defaults to RUN/config/model-policy.json")
    args = p.parse_args(argv)
    try:
        metrics = score_run(args)
        print(json.dumps({"metrics_path": str(Path(args.out).resolve()),
                          "categorical_n": metrics["categorical_n"],
                          "composite": metrics["composite"]["value"]}, ensure_ascii=False))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        p.exit(2, "Error: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
