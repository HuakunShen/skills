#!/usr/bin/env python3
"""Compute transparent descriptive audit metrics. No model or network calls."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import random
import statistics

import _common as common

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
Z_95 = 1.959963984540054
# Per-claim credit for factual honesty: a contradicted claim with no citation (造谣/无据传谣)
# loses more than a contradicted claim that cited something (honest error), and mixed
# verdicts (conflation) sit in between.
FACTUAL_CREDIT = {"supported": 1.0, "mixed": 0.5, "contradicted": 0.0, "contradicted_uncited": -0.5}
UNSUBSTANTIATED_STATUSES = {"uncited_specific", "uncited_vague"}
# Difficulty weights so trivial-only forecasters cannot score high; the score divides by the max weight.
DIFFICULTY_WEIGHTS = {"trivial": 0.5, "moderate": 1.0, "hard": 2.0, "non_consensus": 3.0}
DIFFICULTY_MAX_WEIGHT = max(DIFFICULTY_WEIGHTS.values())
LEAD_TIME_HALF_SCALE_DAYS = 30
HIGH_CERTAINTY_MARKERS = ("一定", "肯定", "必然", "毫无疑问", "百分之百", "板上钉钉", "100%",
                          "definitely", "certainly", "certain", "no doubt", "guarantee", "sure")
HEDGE_MARKERS = ("不一定", "不确定", "可能", "或许", "也许", "unsure", "uncertain", "not sure", "might", "may", "possibly", "perhaps")
TRAFFIC_LIGHTS = ("green", "yellow", "red")


def canonical(obj):
    return common.canonical(obj).encode("utf-8")


def strict_json(text):
    return common.strict_json(text)


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
    return common.finite_number(value)


def wilson_ci(n, d, z=Z_95):
    if d <= 0:
        return None
    p = n / d
    denom = 1 + (z * z) / d
    center = (p + (z * z) / (2 * d)) / denom
    half = (z * math.sqrt((p * (1 - p) + (z * z) / (4 * d)) / d)) / denom
    return {
        "low": max(0.0, round(center - half, 6)),
        "high": min(1.0, round(center + half, 6)),
        "level": 0.95,
        "small_sample": d < 10,
        "method": "wilson_score_exchangeable_claims_no_adjudication_error",
    }


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
    frozen = None
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
        is_indet = c["outcome"] == "indeterminate"
        if not c["due_for_assessment"] or criteria is None or (not c["evidence_ids"] and not is_indet):
            raise ValueError(f"{cid}: resolved claim requires due status, criteria and evidence")
        if not c.get("resolved_at"):
            raise ValueError(f"{cid}: resolved_at required")
        resolved = datetime.fromisoformat(c["resolved_at"].replace("Z", "+00:00"))
        if resolved.tzinfo is None or (frozen is not None and resolved < frozen):
            raise ValueError(f"{cid}: resolution must have timezone and follow criteria freeze")
        if c["evaluation_mode"] == "categorical" and c["outcome"] is None:
            raise ValueError(f"{cid}: categorical verdict missing")
        if c["evaluation_mode"] == "probabilistic" and type(c["event_occurred"]) is not bool and not is_indet:
            raise ValueError(f"{cid}: resolved probability requires event outcome")
        if c["evaluation_mode"] == "none" and not is_indet:
            raise ValueError(f"{cid}: cannot resolve evaluation_mode=none")
    quality = c["evidence_quality"]
    if quality is not None:
        if not isinstance(quality, dict) or any(
                not finite_number(quality.get(k)) or quality[k] not in (0, 0.5, 1)
                for k in ("directness", "independence", "traceability")):
            raise ValueError(f"{cid}: evidence_quality requires three scores from 0,0.5,1")
    difficulty = c.get("difficulty")
    if difficulty is not None and difficulty not in common.DIFFICULTY_TIERS:
        raise ValueError(f"{cid}: invalid difficulty tier (expected one of {common.DIFFICULTY_TIERS})")
    diff_score = c.get("difficulty_score")
    if diff_score is not None and (type(diff_score) is not int or not 1 <= diff_score <= 5):
        raise ValueError(f"{cid}: difficulty_score must be an integer from 1 to 5")
    diff_rat = c.get("difficulty_rationale")
    if diff_rat is not None and not isinstance(diff_rat, str):
        raise ValueError(f"{cid}: difficulty_rationale must be a string or null")
    cit_status = c.get("citation_status")
    if cit_status is not None and cit_status not in common.CITATION_STATUSES:
        raise ValueError(f"{cid}: invalid citation_status")
    cit_text = c.get("citation_text")
    if cit_text is not None and not isinstance(cit_text, str):
        raise ValueError(f"{cid}: citation_text must be a string or null")
    if c["claim_type"] == "prediction":
        stated_at = common.earliest_stated_at(c)
        target_end = common.claim_target_deadline(c)
        if stated_at and target_end:
            ok, _, detail = common.check_prediction_temporal_order(
                stated_at, target_end, common.claim_criteria_timezone(c)
            )
            if not ok:
                raise ValueError(
                    f"{cid}: prediction violates temporal guard ({detail}); reclassify as factual or fix window_end"
                )


def ratio(n, d, with_ci=False):
    res = {"value": n / d if d else None, "numerator": n, "denominator": d}
    if with_ci:
        res["ci_95"] = wilson_ci(n, d) if d else None
    return res


def quality_allows_verdict(c):
    q = c["evidence_quality"]
    if q is None:
        return False
    if min(q[k] for k in ("directness", "independence", "traceability")) >= 0.5:
        return True
    exception = c.get("evidence_exception", {})
    return isinstance(exception, dict) and exception.get("reviewed") is True and bool(str(exception.get("reason", "")).strip())


def _calibration_bins(probability_claims, num_bins):
    bins = [{"bin_low": i / num_bins, "bin_high": (i + 1) / num_bins, "n": 0, "mean_pred": None, "observed_rate": None}
            for i in range(num_bins)]
    grouped = [[] for _ in range(num_bins)]
    for c in probability_claims:
        p = c["probability"]
        idx = min(num_bins - 1, int(p * num_bins))
        grouped[idx].append((p, int(c["event_occurred"])))
    for i, pairs in enumerate(grouped):
        if pairs:
            bins[i]["n"] = len(pairs)
            bins[i]["mean_pred"] = sum(p for p, _ in pairs) / len(pairs)
            bins[i]["observed_rate"] = sum(y for _, y in pairs) / len(pairs)
    return bins


def _family_stats(categorical_claims, bootstrap=False, seed=2026):
    if not categorical_claims:
        return {"family_count": 0, "max_family_share": None, "effective_n": 0.0,
                "family_weighted_strict_support_rate": None, "family_vs_claim_divergence": None,
                "bootstrap_95_ci": None}
    families = {}
    for c in categorical_claims:
        fid = c.get("family_id") or c["claim_id"]
        families.setdefault(fid, []).append(c)
    f_count = len(families)
    max_share = max(len(v) for v in families.values()) / len(categorical_claims)
    weights = [1.0 / len(families[c.get("family_id") or c["claim_id"]]) for c in categorical_claims]
    w_sum = sum(weights)
    eff_n = (w_sum * w_sum) / sum(w * w for w in weights)
    fam_scores = [sum(1 for c in group if c["outcome"] == "supported") / len(group) for group in families.values()]
    fam_rate = sum(fam_scores) / f_count
    claim_rate = sum(1 for c in categorical_claims if c["outcome"] == "supported") / len(categorical_claims)
    boot_ci = None
    if bootstrap and f_count >= 5:
        rng = random.Random(seed)
        draws = []
        for _ in range(1000):
            sample = rng.choices(fam_scores, k=f_count)
            draws.append(sum(sample) / f_count)
        draws.sort()
        boot_ci = {"low": round(draws[25], 6), "high": round(draws[975], 6), "level": 0.95,
                   "method": "cluster_bootstrap_by_family_id", "seed": seed, "clusters": f_count}
    return {
        "family_count": f_count,
        "max_family_share": round(max_share, 6),
        "effective_n": round(eff_n, 4),
        "family_weighted_strict_support_rate": fam_rate,
        "family_vs_claim_divergence": round(abs(claim_rate - fam_rate), 6),
        "bootstrap_95_ci": boot_ci,
    }


def _sourcing_rigor(claims):
    """Claim-level citation and checkability over endorsed empirical claims (legacy untagged runs stay valid)."""
    population = [c for c in claims if c["empirical"] and c["endorsement"] == "endorsed"]
    counts = {k: sum(c.get("citation_status") == k for c in population) for k in common.CITATION_STATUSES}
    counts["untagged"] = sum(c.get("citation_status") is None for c in population)
    tagged_n = len(population) - counts["untagged"]
    checkable_n = sum(c["verifiability"] in {"verifiable", "conditional"} for c in population)
    primary_n = counts["primary_cited"]
    cited_n = primary_n + counts["secondary_cited"]
    unsubstantiated_n = counts["uncited_specific"] + counts["uncited_vague"]
    return {
        "population_n": len(population), "tagged_n": tagged_n, "counts": counts,
        "shares": {k: ratio(counts[k], tagged_n) for k in common.CITATION_STATUSES},
        "untagged_share": ratio(counts["untagged"], len(population)),
        "citation_rate": ratio(cited_n, tagged_n, with_ci=True),
        "primary_citation_rate": ratio(primary_n, tagged_n, with_ci=True),
        "unsubstantiated_rate": ratio(unsubstantiated_n, tagged_n, with_ci=True),
        "checkable_rate": ratio(checkable_n, len(population), with_ci=True),
    }


def traffic_light(value, *, error_rate=False, scale=1.0):
    """Green/yellow/red tier for a fraction, or for a 0-100 score with scale=100.

    Higher-is-better: green >= 80%, yellow 60-79.9%, red < 60%.
    Error rates (error_rate=True): green < 5%, yellow 5-15%, red > 15%.
    """
    if not finite_number(value):
        return None
    fraction = value / scale
    if error_rate:
        return "green" if fraction < 0.05 else "yellow" if fraction <= 0.15 else "red"
    return "green" if fraction >= 0.80 else "yellow" if fraction >= 0.60 else "red"


def _with_light(ratio_obj, *, error_rate=False):
    ratio_obj["traffic_light"] = traffic_light(ratio_obj["value"], error_rate=error_rate)
    return ratio_obj


def _is_high_certainty(claim):
    text = claim.get("certainty_text")
    if not isinstance(text, str) or not text.strip():
        return False
    lowered = text.lower()
    if any(hedge in lowered for hedge in HEDGE_MARKERS):
        return False
    return any(marker.lower() in lowered for marker in HIGH_CERTAINTY_MARKERS)


def _factual_credibility(claims):
    """Anti-misinformation view over adjudicated factual claims only (predictions are scored separately)."""
    factual = [c for c in claims if c["claim_type"] == "factual"]
    categorical = _adjudication_sets(factual)[3]
    n = len(categorical)
    counts = {v: sum(c["outcome"] == v for c in categorical) for v in ("supported", "contradicted", "mixed")}
    contradicted = [c for c in categorical if c["outcome"] == "contradicted"]
    uncited = [c for c in contradicted if c.get("citation_status") in UNSUBSTANTIATED_STATUSES]
    cited_or_untagged = len(contradicted) - len(uncited)
    credit_sum = (counts["supported"] * FACTUAL_CREDIT["supported"]
                  + counts["mixed"] * FACTUAL_CREDIT["mixed"]
                  + cited_or_untagged * FACTUAL_CREDIT["contradicted"]
                  + len(uncited) * FACTUAL_CREDIT["contradicted_uncited"])
    score = round(min(100.0, max(0.0, 100 * credit_sum / n)), 2) if n else None
    return {
        "factual_categorical_n": n,
        "counts": {**counts, "contradicted_uncited": len(uncited)},
        "small_sample": n < POLICY["minimum_categorical_sample"],
        "contradiction_rate": _with_light(ratio(len(contradicted), n, with_ci=True), error_rate=True),
        "misinformation_rate": _with_light(ratio(len(uncited), n, with_ci=True), error_rate=True),
        "factual_honesty_score": {
            "value": score, "scale": [0, 100], "traffic_light": traffic_light(score, scale=100),
            "credit": dict(FACTUAL_CREDIT), "untagged_contradicted_n": sum(c.get("citation_status") is None for c in contradicted),
            "formula": "100 * mean(credit): supported 1.0, mixed 0.5, cited or untagged contradicted 0.0, uncited contradicted -0.5, clipped to 0-100",
            "label": "heuristic_credibility_index_not_truth_verdict",
        },
    }


def _lead_time_weight(days):
    return math.log2(1 + max(0.0, days) / LEAD_TIME_HALF_SCALE_DAYS)


def _difficulty_adjusted(claims):
    """Forecast accuracy that rewards hard calls and penalizes trivial-only track records."""
    preds = [c for c in claims if c["claim_type"] == "prediction"]
    categorical = _adjudication_sets(preds)[3]
    rated = [c for c in categorical if common.resolve_difficulty_tier(c) in DIFFICULTY_WEIGHTS]
    n = len(rated)
    weight_total = sum(DIFFICULTY_WEIGHTS[common.resolve_difficulty_tier(c)] for c in rated)
    weight_hit = sum(DIFFICULTY_WEIGHTS[common.resolve_difficulty_tier(c)] for c in rated if c["outcome"] == "supported")
    by_tier = {}
    for tier, weight in DIFFICULTY_WEIGHTS.items():
        group = [c for c in rated if common.resolve_difficulty_tier(c) == tier]
        by_tier[tier] = {"weight": weight, "n": len(group), "supported": sum(c["outcome"] == "supported" for c in group)}
    score = round(100 * weight_hit / (n * DIFFICULTY_MAX_WEIGHT), 2) if n else None
    dated = [(c, days) for c in categorical for days in [_lead_time_days(c)] if days is not None]
    lead_den = sum(_lead_time_weight(days) for _, days in dated)
    lead_num = sum(_lead_time_weight(days) for c, days in dated if c["outcome"] == "supported")
    overall = ratio(sum(c["outcome"] == "supported" for c in categorical), len(categorical))["value"]
    high = [c for c in categorical if _is_high_certainty(c)]
    high_rate = ratio(sum(c["outcome"] == "supported" for c in high), len(high))["value"]
    gap = round(overall - high_rate, 6) if overall is not None and high_rate is not None else None
    return {
        "weights": dict(DIFFICULTY_WEIGHTS), "max_weight": DIFFICULTY_MAX_WEIGHT,
        "weighted_n": n, "unrated_excluded_n": len(categorical) - n, "by_tier": by_tier,
        "weighted_strict_support_rate": round(weight_hit / weight_total, 6) if weight_total else None,
        "difficulty_exposure": round(weight_total / (n * DIFFICULTY_MAX_WEIGHT), 6) if n else None,
        "difficulty_adjusted_score": {
            "value": score, "scale": [0, 100], "traffic_light": traffic_light(score, scale=100),
            "formula": "100 * sum(weight * supported) / (n * max_weight)",
        },
        "lead_time_weighted_support_rate": {
            "value": round(lead_num / lead_den, 6) if lead_den else None,
            "numerator": round(lead_num, 4), "denominator": round(lead_den, 4), "dated_n": len(dated),
            "weight": "log2(1 + max(0, lead_time_days) / 30)",
        },
        "overconfidence_gap": {
            "value": gap, "overall_strict_support_rate": overall, "high_certainty_strict_support_rate": high_rate,
            "high_certainty_n": len(high), "certainty_text_n": sum(bool(str(c.get("certainty_text") or "").strip()) for c in categorical),
            "definition": "overall minus high-certainty strict support; positive means high-certainty calls underperform",
            "marker_source": "heuristic_certainty_text_markers",
        },
    }


def _adjudication_sets(claims):
    eligible = [c for c in claims if c["empirical"] and c["endorsement"] == "endorsed"
                and c["attribution_confidence"] == "high"]
    # Exclude exploratory inferred-probability claims from the due denominator so they don't depress coverage.
    due = [c for c in eligible if c["accountability_eligible"] and c["due_for_assessment"]
           and not (c["evaluation_mode"] == "probabilistic" and c["probability_origin"] != "explicit")]
    resolved = [c for c in due if c["lifecycle"] == "resolved" and c["review_state"] == "accepted"
                and quality_allows_verdict(c)]
    categorical = [c for c in resolved if c["evaluation_mode"] == "categorical"
                   and c["outcome"] in {"supported", "contradicted", "mixed"}]
    probability = [c for c in resolved if c["evaluation_mode"] == "probabilistic"
                   and c["probability_origin"] == "explicit" and type(c["event_occurred"]) is bool]
    return eligible, due, resolved, categorical, probability


def core_metrics(claims, *, bootstrap_clusters=False):
    eligible, due, resolved, categorical, probability = _adjudication_sets(claims)
    indeterminate_resolved = [c for c in due if c["lifecycle"] == "resolved" and c["outcome"] == "indeterminate"]
    adjudicated = categorical + probability
    counts = {v: sum(c["outcome"] == v for c in categorical)
              for v in ("supported", "contradicted", "mixed")}
    s, bad, partial = (counts[k] for k in ("supported", "contradicted", "mixed"))
    qualities = [sum(c["evidence_quality"][k] for k in ("directness", "independence", "traceability")) / 3
                 for c in adjudicated if c["evidence_quality"] is not None]
    briers = [(c["probability"] - int(c["event_occurred"])) ** 2 for c in probability]
    brier_val = statistics.mean(briers) if briers else None
    base_rate = statistics.mean(int(c["event_occurred"]) for c in probability) if probability else None
    clim_brier = base_rate * (1 - base_rate) if base_rate is not None else None
    bss = (1 - brier_val / clim_brier) if (brier_val is not None and clim_brier and clim_brier > 0) else None
    cal_bins = _calibration_bins(probability, 10 if len(probability) >= 50 else 5) if len(probability) >= 20 else None
    # Accountability excludes claims explicitly marked not_assessed (audit backlog, not speaker vagueness).
    assessed_for_accountability = [c for c in eligible if c.get("operationalization_status") != "not_assessed"]
    not_assessed_count = len(eligible) - len(assessed_for_accountability)
    # Only count unreviewed/needs_review determinate resolutions or needs_review items as unaccepted blockers;
    # confirmed indeterminate and awaiting_evidence do not deadlock composite.
    unaccepted_due = sum(
        1 for c in due
        if c["review_state"] == "needs_review"
        or (c["lifecycle"] == "resolved" and c["outcome"] in {"supported", "contradicted", "mixed"} and c["review_state"] != "accepted")
    )
    return {
        "total_canonical_claims": len(claims), "endorsed_empirical_claims": len(eligible),
        "categorical_n": len(categorical), "categorical_counts": counts,
        "strict_support_rate": ratio(s, s + bad + partial, with_ci=True),
        "partial_share": ratio(partial, s + bad + partial),
        "binary_accuracy_excluding_mixed": ratio(s, s + bad, with_ci=True),
        "accountability": ratio(sum(c["accountability_eligible"] for c in assessed_for_accountability), len(assessed_for_accountability), with_ci=True),
        "not_assessed_operationalization_count": not_assessed_count,
        "adjudication_coverage": ratio(len(adjudicated), len(due), with_ci=True),
        "indeterminate_resolved_n": len(indeterminate_resolved),
        "family_metrics": _family_stats(categorical, bootstrap=bootstrap_clusters),
        "brier": {"value": brier_val, "n": len(briers),
                  "base_rate": base_rate, "climatology_brier": clim_brier, "brier_skill_score": bss,
                  "naive_025_reference": 0.25, "small_sample": len(briers) < 20,
                  "calibration_bins": cal_bins,
                  "lower_is_better": True, "explicit_probabilities_only": True},
        "evidence_quality": {"mean": statistics.mean(qualities) if qualities else None,
                             "assessed_n": len(qualities), "expected_n": len(adjudicated)},
        "lifecycle_counts": {v: sum(c["lifecycle"] == v for c in eligible) for v in sorted(LIFECYCLES)},
        "excluded_from_categorical_accuracy": len(claims) - len(categorical),
        "unaccepted_due_claims": unaccepted_due,
        "quality_blocked_resolutions": sum(c["lifecycle"] == "resolved" and c["outcome"] in {"supported", "contradicted", "mixed"} and not quality_allows_verdict(c) for c in due),
        "sourcing_rigor": _sourcing_rigor(claims),
    }


def _lead_time_days(c):
    stated_at = common.earliest_stated_at(c)
    target_end = common.claim_target_deadline(c)
    if not stated_at or not target_end:
        return None
    try:
        ok, days, _ = common.check_prediction_temporal_order(
            stated_at, target_end, common.claim_criteria_timezone(c)
        )
    except ValueError:
        return None
    return days if ok else None


def _horizon_bucket(c):
    target_end = common.claim_target_deadline(c)
    if not target_end:
        return "undated"
    stated_at = common.earliest_stated_at(c)
    if not stated_at:
        return "unknown_stated_at"
    days = _lead_time_days(c)
    if days is None:
        return "unknown"
    return common.horizon_bucket_for_days(days)


def _prediction_difficulty_stats(claims, bootstrap_clusters=False):
    preds = [c for c in claims if c["claim_type"] == "prediction"]
    ordered_tiers = (*common.DIFFICULTY_TIERS, "unrated")
    grouped = {tier: [] for tier in ordered_tiers}
    for c in preds:
        grouped[common.resolve_difficulty_tier(c)].append(c)
    by_tier = {}
    for tier in ordered_tiers:
        group = grouped[tier]
        if not group:
            continue
        tier_metrics = core_metrics(group, bootstrap_clusters=bootstrap_clusters)
        t_scores = [c["difficulty_score"] for c in group if type(c.get("difficulty_score")) is int]
        tier_metrics["mean_difficulty_score"] = round(statistics.mean(t_scores), 3) if t_scores else None
        by_tier[tier] = tier_metrics
    rated = [c for c in preds if common.resolve_difficulty_tier(c) != "unrated"]
    # Difficulty ratings are subjective: count them per recorded rater model so reports can attribute them.
    rated_by_model = {}
    for c in rated:
        rater = c.get("difficulty_model_id")
        key = rater if isinstance(rater, str) and rater.strip() else "unrecorded"
        rated_by_model[key] = rated_by_model.get(key, 0) + 1
    non_trivial = [c for c in preds if common.resolve_difficulty_tier(c) in {"moderate", "hard", "non_consensus"}]
    trivial = grouped["trivial"]
    non_trivial_m = core_metrics(non_trivial, bootstrap_clusters=bootstrap_clusters)
    trivial_m = core_metrics(trivial, bootstrap_clusters=bootstrap_clusters)
    scores = [c["difficulty_score"] for c in preds if type(c.get("difficulty_score")) is int]
    rated_cat_denom = trivial_m["categorical_n"] + non_trivial_m["categorical_n"]
    return {
        "total_predictions": len(preds),
        "rated_n": len(rated),
        "unrated_n": len(preds) - len(rated),
        "rated_by_model_id": dict(sorted(rated_by_model.items())),
        "subjective_rating": True,
        "mean_difficulty_score": round(statistics.mean(scores), 3) if scores else None,
        "non_trivial_strict_support_rate": non_trivial_m["strict_support_rate"],
        "trivial_strict_support_rate": trivial_m["strict_support_rate"],
        "trivial_share_of_rated_categorical": ratio(trivial_m["categorical_n"], rated_cat_denom),
        "by_tier": by_tier,
    }


def _prediction_horizon_stats(claims, bootstrap_clusters=False):
    preds = [c for c in claims if c["claim_type"] == "prediction"]
    dated = []
    undated_n = unknown_stated_at_n = 0
    for c in preds:
        target_end = common.claim_target_deadline(c)
        if not target_end:
            undated_n += 1
            continue
        stated_at = common.earliest_stated_at(c)
        if not stated_at:
            unknown_stated_at_n += 1
            continue
        days = _lead_time_days(c)
        if days is not None:
            dated.append((c, days))
    all_days = [d for _, d in dated]
    supported_days = [
        d for c, d in dated
        if c["empirical"] and c["endorsement"] == "endorsed" and c["attribution_confidence"] == "high"
        and c["accountability_eligible"] and c["due_for_assessment"]
        and c["lifecycle"] == "resolved" and c["review_state"] == "accepted"
        and quality_allows_verdict(c) and c["evaluation_mode"] == "categorical" and c["outcome"] == "supported"
    ]
    buckets = {}
    for b in common.HORIZON_BUCKETS:
        b_items = [(c, d) for c, d in dated if common.horizon_bucket_for_days(d) == b]
        b_claims = [c for c, _ in b_items]
        b_days = [d for _, d in b_items]
        cm = core_metrics(b_claims, bootstrap_clusters=bootstrap_clusters)
        buckets[b] = {
            "count": len(b_claims),
            "categorical_n": cm["categorical_n"],
            "categorical_counts": cm["categorical_counts"],
            "strict_support_rate": cm["strict_support_rate"],
            "mean_lead_time_days": round(statistics.mean(b_days), 2) if b_days else None,
            "median_lead_time_days": round(statistics.median(b_days), 2) if b_days else None,
        }
    return {
        "total_predictions": len(preds),
        "dated_n": len(dated),
        "undated_n": undated_n,
        "unknown_stated_at_n": unknown_stated_at_n,
        "mean_lead_time_days": round(statistics.mean(all_days), 2) if all_days else None,
        "median_lead_time_days": round(statistics.median(all_days), 2) if all_days else None,
        "min_lead_time_days": round(min(all_days), 2) if all_days else None,
        "max_lead_time_days": round(max(all_days), 2) if all_days else None,
        "supported_mean_lead_time_days": round(statistics.mean(supported_days), 2) if supported_days else None,
        "supported_median_lead_time_days": round(statistics.median(supported_days), 2) if supported_days else None,
        "buckets": buckets,
    }


def _period_key(c):
    ts = c.get("first_stated_at") or c.get("published_at")
    if isinstance(ts, str) and len(ts) >= 4 and ts[:4].isdigit():
        return ts[:4]
    return "unknown"


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


def calculate(claims, coverage, *, composite=False, policy=None, occurrences=None, subject_id=None, bootstrap_clusters=False):
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
    metrics = core_metrics(claims, bootstrap_clusters=bootstrap_clusters)
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
    metrics["by_claim_type"] = {k: core_metrics([c for c in claims if c["claim_type"] == k], bootstrap_clusters=bootstrap_clusters)
                                for k in sorted({c["claim_type"] for c in claims})}
    metrics["by_domain"] = {d: core_metrics([c for c in claims if c["domain"] == d], bootstrap_clusters=bootstrap_clusters)
                            for d in sorted({c["domain"] for c in claims})}
    metrics["by_period"] = {p: core_metrics([c for c in claims if _period_key(c) == p])
                            for p in sorted({_period_key(c) for c in claims})}
    horizon_order = (*common.HORIZON_BUCKETS, "undated", "unknown_stated_at", "unknown")
    present_horizons = {_horizon_bucket(c) for c in claims}
    metrics["by_horizon"] = {
        h: core_metrics([c for c in claims if _horizon_bucket(c) == h])
        for h in horizon_order if h in present_horizons
    }
    diff_order = (*common.DIFFICULTY_TIERS, "unrated")
    present_diffs = {common.resolve_difficulty_tier(c) for c in claims}
    metrics["by_difficulty"] = {
        tier: core_metrics([c for c in claims if common.resolve_difficulty_tier(c) == tier], bootstrap_clusters=bootstrap_clusters)
        for tier in diff_order if tier in present_diffs
    }
    metrics["prediction_difficulty"] = _prediction_difficulty_stats(claims, bootstrap_clusters=bootstrap_clusters)
    metrics["prediction_horizon"] = _prediction_horizon_stats(claims, bootstrap_clusters=bootstrap_clusters)
    metrics["factual_credibility"] = _factual_credibility(claims)
    metrics["difficulty_adjusted"] = _difficulty_adjusted(claims)
    metrics["selection_funnel"] = {
        "total_canonical_claims": len(claims),
        "empirical": sum(1 for c in claims if c["empirical"]),
        "endorsed_empirical": sum(1 for c in claims if c["empirical"] and c["endorsement"] == "endorsed"),
        "high_attribution": metrics["endorsed_empirical_claims"],
        "accountability_eligible": sum(1 for c in claims if c["empirical"] and c["endorsement"] == "endorsed" and c["attribution_confidence"] == "high" and c["accountability_eligible"]),
        "due_for_assessment": metrics["adjudication_coverage"]["denominator"],
        "adjudicated_total": metrics["adjudication_coverage"]["numerator"],
        "categorical_n": metrics["categorical_n"],
        "probabilistic_n": metrics["brier"]["n"],
        "indeterminate_resolved_n": metrics["indeterminate_resolved_n"],
        "excluded_low_medium_attribution": sum(1 for c in claims if c["empirical"] and c["endorsement"] == "endorsed" and c["attribution_confidence"] != "high"),
    }
    warnings = []
    fam_div = metrics["family_metrics"].get("family_vs_claim_divergence")
    if fam_div is not None and fam_div > 0.10:
        warnings.append(f"family_vs_claim_divergence={fam_div:.3f}: repeated correlated claims shift support rate")
    pred_rate = (metrics["by_claim_type"].get("prediction") or {}).get("strict_support_rate", {}).get("value")
    fact_rate = (metrics["by_claim_type"].get("factual") or {}).get("strict_support_rate", {}).get("value")
    if pred_rate is not None and fact_rate is not None and abs(pred_rate - fact_rate) > 0.15:
        warnings.append(f"prediction_vs_factual_gap={abs(pred_rate - fact_rate):.3f}: inspect prediction and factual metrics separately")
    if metrics["not_assessed_operationalization_count"]:
        warnings.append(f"{metrics['not_assessed_operationalization_count']} claims marked not_assessed for operationalization")
    pdiff = metrics["prediction_difficulty"]
    triv_share = pdiff["trivial_share_of_rated_categorical"]["value"]
    triv_rate = pdiff["trivial_strict_support_rate"]["value"]
    nontriv_rate = pdiff["non_trivial_strict_support_rate"]["value"]
    if triv_share is not None and triv_share >= 0.30 and (nontriv_rate is None or (triv_rate is not None and triv_rate - nontriv_rate > 0.10)):
        warnings.append(
            f"trivial_prediction_inflation: trivial predictions are {triv_share * 100:.1f}% of rated predictions; inspect non_trivial_strict_support_rate separately"
        )
    metrics["warnings"] = warnings
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
    metrics["uncertainty_note"] = "Descriptive corpus metrics; Wilson intervals assume exchangeable claims without adjudication error. Model spread is separate."
    return metrics


def atomic_write(path, text):
    common.atomic_text(path, text)


def csv_text(claims):
    cols = ["claim_id", "text", "domain", "claim_type", "family_id", "difficulty", "difficulty_score",
            "lead_time_days", "quantifiability", "verifiability",
            "lifecycle", "outcome", "probability", "citation_status", "occurrence_ids", "evidence_ids"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=cols)
    writer.writeheader()
    for c in claims:
        row = {}
        for k in cols:
            if k == "lead_time_days":
                v = c.get(k) if c.get(k) is not None else (_lead_time_days(c) if c.get("claim_type") == "prediction" else None)
            else:
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
        # Enrich working copies with earliest source published_at when first_stated_at is absent
        # so temporal guards and lead-time statistics use real source publication timestamps.
        occ_by_id = {o["occurrence_id"]: o for o in (occurrences or []) if isinstance(o, dict) and o.get("occurrence_id")}
        sources_path = run / "sources.jsonl"
        src_by_id = {s["source_id"]: s for s in audit.read_jsonl(sources_path) if isinstance(s, dict) and s.get("source_id")} if sources_path.exists() else {}
        enriched_claims = []
        for c in claims:
            if not c.get("first_stated_at") and occ_by_id and src_by_id:
                stated = common.earliest_stated_at(c, occ_by_id, src_by_id, cfg["scope"]["timezone"])
                if stated:
                    c = {**c, "first_stated_at": stated}
            enriched_claims.append(c)
        enriched_selected = [c for c in enriched_claims if args.subject_id is None or c.get("subject_id") == args.subject_id]
        metrics = calculate(enriched_claims, coverage, composite=args.composite, policy=policy,
                            occurrences=occurrences, subject_id=args.subject_id,
                            bootstrap_clusters=getattr(args, "bootstrap_clusters", False))
        metrics["acceptance_verification"] = {
            "verified_resolutions": verified, "as_of": cfg["scope"]["as_of"],
            "policy": "recomputed_consensus_and_bound_evidence",
            "semantic_evidence_truth_verified_by_script": False,
        }
        metrics["input_sha256"] = {Path(x).name: hashlib.sha256(Path(x).read_bytes()).hexdigest()
                                   for x in [args.claims, args.coverage, args.occurrences] if x}
        atomic_write(args.out, json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        if args.csv:
            atomic_write(args.csv, csv_text(enriched_selected))
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
    p.add_argument("--bootstrap-clusters", action="store_true", help="Compute family_id cluster bootstrap 95%% CI")
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
