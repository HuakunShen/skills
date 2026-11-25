#!/usr/bin/env python3
"""Deterministic pipeline helpers for audit_run.py (Python 3.9+ stdlib).

Handles source segmentation, policy binding, criteria freezing, extraction shard
merging with mechanical quote verification, ledger-backed coverage computation,
assessment round updates, report-data assembly, and external handoff packets.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import _common as common

UNIT_HEADER = re.compile(r"^(?:\[#((?:p|cue)-\d{6})[^\]]*\]|<!--\s*audit-claims-locator:\s*(\{.*?\})\s*-->)\n", re.MULTILINE)
DEFAULT_RUBRIC_PATH = Path(__file__).resolve().parent.parent / "assets/evaluation-rubric.json"
EXTRACTION_PROTECTED_CLAIM_FIELDS = frozenset({
    "occurrences", "occurrence", "outcome", "resolved_at", "acceptance",
    "evidence_ids", "evidence_quality", "evidence_exception",
    "accountability_eligible", "due_for_assessment", "event_occurred",
    "reopen_history", "quote_verified", "trigger_assessment",
})
OPTIONAL_OCCURRENCE_FIELDS = (
    "technical_duplicate_of", "raw_locator", "normalized_locator", "transcript_uncertain",
)


def _extract_frontmatter_and_units(text):
    frontmatter = ""
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n\n", 4)
        if end != -1:
            frontmatter = text[: end + 6]
            body = text[end + 6 :]
    matches = list(UNIT_HEADER.finditer(body))
    if not matches:
        return frontmatter, [{"unit_id": "u-000001", "header": "", "body": body}]
    units = []
    for i, m in enumerate(matches):
        uid = m.group(1)
        if uid is None and m.group(2):
            try:
                uid = common.strict_json(m.group(2)).get("id")
            except (json.JSONDecodeError, ValueError):
                uid = None
        uid = uid or f"u-{i + 1:06d}"
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        units.append({"unit_id": uid, "header": m.group(0), "body": body[m.end() : next_start]})
    return frontmatter, units


def segment_source(ledger, run, source_id, token_budget, overlap_units=2):
    if token_budget <= 256:
        raise ValueError("--token-budget for segmentation must be > 256")
    if overlap_units < 0:
        raise ValueError("--overlap-units must be nonnegative")
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        sources = ledger.read_jsonl(run / "sources.jsonl")
        by_id = ledger.unique(sources, "source_id", "sources")
        if source_id not in by_id:
            raise ValueError(f"Unknown source_id: {source_id}")
        parent = by_id[source_id]
        if parent.get("status") != "ready":
            raise ValueError(f"Source {source_id} must have status=ready before segmentation")
        text = ledger.inside(run, parent["content_path"]).read_text(encoding="utf-8")
        frontmatter, units = _extract_frontmatter_and_units(text)
        unit_budget = max(128, token_budget - 256)
        unit_tokens = [max(1, ledger.estimate_source_tokens(u["header"] + u["body"]) - 128) for u in units]
        if any(t > unit_budget for t in unit_tokens):
            raise ValueError(f"A single unit in {source_id} exceeds token_budget={token_budget}; split paragraphs first")
        chunks = []
        idx = 0
        while idx < len(units):
            end = idx
            acc = 0
            while end < len(units) and (end == idx or acc + unit_tokens[end] <= unit_budget):
                acc += unit_tokens[end]
                end += 1
            chunks.append((idx, end))
            if end >= len(units):
                break
            next_idx = max(idx + 1, end - overlap_units)
            idx = next_idx
        parent_root = parent.get("parent_source_id") or source_id
        created_rows = []
        for seg_no, (start_i, end_i) in enumerate(chunks, 1):
            seg_id = f"{source_id}__seg{seg_no:03d}"
            if seg_id in by_id:
                raise ValueError(f"Segment id already exists: {seg_id}")
            seg_units = units[start_i:end_i]
            seg_meta = {
                "source_id": seg_id, "parent_source_id": parent_root, "segment_index": seg_no,
                "segment_count": len(chunks), "segment_start_unit": seg_units[0]["unit_id"],
                "segment_end_unit": seg_units[-1]["unit_id"], "overlap_units": overlap_units if seg_no > 1 else 0,
                "published_at": parent.get("published_at"), "source_url": parent.get("source_url"),
                "title": f"{parent.get('title', source_id)} [Segment {seg_no}/{len(chunks)}]",
                "language": parent.get("language"), "transcript_method": parent.get("transcript_method"),
            }
            seg_fm = "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in seg_meta.items()) + "---\n\n"
            seg_body = "".join(u["header"] + u["body"] for u in seg_units)
            seg_bytes = (seg_fm + seg_body).encode("utf-8")
            seg_rel = f"sources/{seg_id}.md"
            common.atomic_bytes(ledger.inside(run, seg_rel), seg_bytes)
            seg_row = {
                **seg_meta, "status": "ready", "content_path": seg_rel,
                "content_hash": hashlib.sha256(seg_bytes).hexdigest(),
                "raw_path": parent.get("raw_path"), "raw_hash": parent.get("raw_hash"),
                "locators_path": parent.get("locators_path"),
                "locator_kind": parent.get("locator_kind"), "locator_count": len(seg_units),
            }
            created_rows.append(seg_row)
        # Prove union of segments covers every parent unit.
        covered = set()
        for start_i, end_i in chunks:
            covered.update(range(start_i, end_i))
        if len(covered) != len(units):
            raise ValueError("Segmentation failed coverage proof")
        parent["status"] = "segmented"
        parent["segment_ids"] = [r["source_id"] for r in created_rows]
        sources.extend(created_rows)
        ledger.write_jsonl(run / "sources.jsonl", sources)
        ledger.event(run, "source_segmented", source_id=source_id, segment_ids=parent["segment_ids"], unit_count=len(units))
        ledger.progress(run)
        return {"source_id": source_id, "segments": parent["segment_ids"], "units_covered": len(covered)}


def bind_policy(ledger, run, model_policy_path=None, rules_json=None, allow_rebind=False, reason=None):
    import model_panel as panel

    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        has_plan = (run / "plan.json").exists() or bool(ledger.read_jsonl(run / "tasks.jsonl"))
        if has_plan and not allow_rebind:
            raise ValueError("Run is already planned; create a new run or pass --allow-rebind with --reason")
        if allow_rebind and not common.nonempty(reason):
            raise ValueError("--allow-rebind requires a nonempty --reason")
        if model_policy_path:
            pol_path = ledger.inside(run, model_policy_path) if not Path(model_policy_path).is_absolute() else Path(model_policy_path).resolve()
            policy = panel.load_policy(pol_path)
            cfg.setdefault("models", {})["policy_hash"] = policy["policy_hash"]
            cfg["models"]["policy_path"] = model_policy_path
            if "analysis_modules" in policy:
                cfg["rules"]["analysis_modules"] = policy["analysis_modules"]
        if rules_json:
            rules = common.read_json(Path(rules_json))
            if not isinstance(rules, dict):
                raise ValueError("rules JSON must be an object")
            cfg["rules"] = {**cfg.get("rules", {}), **rules}
        cfg["config_hash"] = ledger.digest(ledger.config_body(cfg))
        common.write_json(run / "run.json", cfg)
        ledger.event(run, "policy_bound", config_hash=cfg["config_hash"], reason=reason or "initial_binding")
        ledger.progress(run)
        return {"run_id": cfg["run_id"], "config_hash": cfg["config_hash"], "models": cfg["models"], "rules": cfg["rules"]}


def freeze_criteria(ledger, run, claim_id, definition_path, version="1", *,
                    difficulty=None, difficulty_score=None, difficulty_rationale=None):
    run = Path(run).resolve()
    definition = common.read_json(Path(definition_path))
    if not isinstance(definition, dict):
        raise ValueError("Criteria definition must be a JSON object")
    required = {"target", "predicate", "window_start", "window_end", "timezone", "condition", "resolution_basis"}
    missing = sorted(required - set(definition))
    if missing:
        raise ValueError(f"Criteria definition missing fields: {missing}")
    if any(not common.nonempty(definition.get(k)) for k in ("target", "predicate", "timezone")):
        raise ValueError("Criteria target, predicate and timezone must be nonempty strings")
    if definition["resolution_basis"] not in {"explicit", "interpretation"}:
        raise ValueError("resolution_basis must be explicit or interpretation")
    if difficulty is not None and difficulty not in common.DIFFICULTY_TIERS:
        raise ValueError(f"difficulty must be one of {common.DIFFICULTY_TIERS}")
    if difficulty_score is not None and (type(difficulty_score) is not int or not 1 <= difficulty_score <= 5):
        raise ValueError("difficulty_score must be an integer from 1 to 5")
    if difficulty_rationale is not None and not isinstance(difficulty_rationale, str):
        raise ValueError("difficulty_rationale must be a string")
    crit_zone = ZoneInfo(definition["timezone"])
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        claims = ledger.read_jsonl(run / "claims.jsonl")
        by_id = ledger.unique(claims, "claim_id", "claims")
        if claim_id not in by_id:
            raise ValueError(f"Unknown claim_id: {claim_id}")
        claim = by_id[claim_id]
        if claim.get("criteria") is not None:
            raise ValueError(f"Claim {claim_id} already has frozen criteria; use reopen for revisions")
        end = definition.get("window_end")
        lead_time_days = None
        if claim.get("claim_type") == "prediction" and end:
            occ_rows = ledger.read_jsonl(run / "occurrences.jsonl") if (run / "occurrences.jsonl").exists() else []
            occ_by_id = {o["occurrence_id"]: o for o in occ_rows if isinstance(o, dict) and o.get("occurrence_id")}
            src_rows = ledger.read_jsonl(run / "sources.jsonl") if (run / "sources.jsonl").exists() else []
            src_by_id = {s["source_id"]: s for s in src_rows if isinstance(s, dict) and s.get("source_id")}
            stated_at = common.earliest_stated_at(claim, occ_by_id, src_by_id, cfg["scope"]["timezone"])
            if stated_at:
                ok, lead_time_days, detail = common.check_prediction_temporal_order(
                    stated_at, end, definition["timezone"]
                )
                if not ok:
                    raise ValueError(
                        f"Prediction {claim_id} violates temporal guard ({detail}); reclassify as factual or fix window_end"
                    )
        sha = hashlib.sha256(common.canonical(definition).encode("utf-8")).hexdigest()
        frozen_at = common.now()
        criteria_obj = {"version": str(version), "frozen_at": frozen_at, "definition": definition, "sha256": sha}
        snap_rel = f"criteria/{sha}.json"
        snap_path = ledger.inside(run, snap_rel)
        if not snap_path.exists():
            common.write_json(snap_path, criteria_obj)
        as_of_dt = datetime.fromisoformat(cfg["scope"]["as_of"].replace("Z", "+00:00"))
        due = True if not end else ledger.as_of_time(end, crit_zone) <= as_of_dt
        if definition.get("condition") not in (None, "unconditional", "") and definition.get("trigger_state") in {"unmet", "unknown"}:
            due = False
        claim["criteria"] = criteria_obj
        if difficulty is not None:
            claim["difficulty"] = difficulty
        if difficulty_score is not None:
            claim["difficulty_score"] = difficulty_score
        if difficulty_rationale is not None:
            claim["difficulty_rationale"] = difficulty_rationale
        claim["accountability_eligible"] = bool(claim.get("empirical")) and claim.get("verifiability") in {"verifiable", "conditional"}
        claim["operationalization_status"] = "operationalized" if claim["accountability_eligible"] else "not_operationalizable"
        claim["due_for_assessment"] = due if claim["accountability_eligible"] else False
        if claim.get("lifecycle") in {"pending", "ready"}:
            claim["lifecycle"] = "ready" if claim["due_for_assessment"] else "pending"
        ledger.write_jsonl(run / "claims.jsonl", claims)
        ledger.event(run, "criteria_frozen", claim_id=claim_id, criteria_sha256=sha, frozen_at=frozen_at, due=claim["due_for_assessment"])
        res = {"claim_id": claim_id, "criteria_sha256": sha, "frozen_at": frozen_at, "due_for_assessment": claim["due_for_assessment"]}
        if lead_time_days is not None:
            res["lead_time_days"] = lead_time_days
        return res


def _verify_quote_in_source(source_text, locator, quote):
    norm_quote = common.normalize_quote_text(quote)
    if not norm_quote:
        return False, "empty_quote"
    _, units = _extract_frontmatter_and_units(source_text)
    if isinstance(locator, dict):
        uid = locator.get("unit_id") or locator.get("id")
        start_u = locator.get("start_unit") or uid
        end_u = locator.get("end_unit") or start_u
        if start_u:
            id_to_idx = {u["unit_id"]: idx for idx, u in enumerate(units)}
            if start_u in id_to_idx:
                i0 = id_to_idx[start_u]
                i1 = id_to_idx.get(end_u, i0)
                if i1 < i0:
                    i0, i1 = i1, i0
                window = " ".join(u["body"] for u in units[max(0, i0 - 1) : min(len(units), i1 + 2)])
                if norm_quote in common.normalize_quote_text(window):
                    return True, "matched_locator_unit"
        if locator.get("kind") == "paragraph" and isinstance(locator.get("start"), int):
            p_start = max(1, locator["start"])
            p_end = max(p_start, locator.get("end") or p_start)
            p_slice = units[max(0, p_start - 1) : min(len(units), p_end)]
            if norm_quote in common.normalize_quote_text(" ".join(u["body"] for u in p_slice)):
                return True, "matched_paragraph_range"
    if norm_quote in common.normalize_quote_text(source_text):
        return True, "matched_source_fallback"
    return False, "quote_not_found_in_source"


def merge_extraction(ledger, run, result_paths=None, strict_quotes=False):
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        sources = ledger.unique(ledger.read_jsonl(run / "sources.jsonl"), "source_id", "sources")
        tasks = ledger.read_jsonl(run / "tasks.jsonl")
        if result_paths:
            paths = [ledger.inside(run, p) if not Path(p).is_absolute() else Path(p).resolve() for p in result_paths]
        else:
            paths = [ledger.inside(run, t["result_path"]) for t in tasks if t.get("stage") == "extract" and t.get("status") == "completed" and t.get("result_path")]
        if not paths:
            raise ValueError("No completed extraction result shards found to merge")
        occurrences = ledger.read_jsonl(run / "occurrences.jsonl") if (run / "occurrences.jsonl").exists() else []
        occ_by_id = ledger.unique(occurrences, "occurrence_id", "occurrences")
        claims = ledger.read_jsonl(run / "claims.jsonl")
        claim_by_id = ledger.unique(claims, "claim_id", "claims")
        source_texts = {}
        added_occ = added_claims = unverified_quotes = temporal_warnings = 0
        for p in paths:
            shard = common.read_json(p)
            if shard.get("complete") is not True:
                raise ValueError(f"Extraction shard is not complete=true: {p}")
            for raw_claim in shard.get("claims", []):
                occ_list = raw_claim.get("occurrences") or ([raw_claim["occurrence"]] if "occurrence" in raw_claim else [])
                occ_ids = list(raw_claim.get("occurrence_ids", []))
                all_quotes_ok = True
                for raw_occ in occ_list:
                    sid = raw_occ.get("source_id")
                    if sid not in sources:
                        raise ValueError(f"Extraction occurrence refers to unknown source_id: {sid}")
                    if sid not in source_texts:
                        source_texts[sid] = ledger.inside(run, sources[sid]["content_path"]).read_text(encoding="utf-8")
                    quote = raw_occ.get("original_quote", "")
                    ok, match_reason = _verify_quote_in_source(source_texts[sid], raw_occ.get("locator"), quote)
                    if not ok:
                        all_quotes_ok = False
                        unverified_quotes += 1
                        if strict_quotes:
                            raise ValueError(f"Quote verification failed for {sid}: {quote[:80]!r}")
                    oid = raw_occ.get("occurrence_id") or "occ_" + common.digest({"source_id": sid, "locator": raw_occ.get("locator"), "quote": common.normalize_quote_text(quote)})[:16]
                    occ_ids.append(oid)
                    if oid not in occ_by_id:
                        occ_rec = {
                            "schema_version": 1, "occurrence_id": oid, "claim_id": raw_claim.get("claim_id", ""),
                            "source_id": sid, "speaker": raw_occ.get("speaker") or cfg["subject"],
                            "original_quote": quote, "context_before": raw_occ.get("context_before", ""),
                            "context_after": raw_occ.get("context_after", ""), "locator": raw_occ.get("locator", {"kind": "paragraph", "start": 1, "end": 1}),
                            "endorsement": raw_occ.get("endorsement", raw_claim.get("endorsement", "endorsed")),
                            "language": raw_occ.get("language") or sources[sid].get("language") or "unknown",
                            "quote_verified": ok, "quote_match_basis": match_reason,
                        }
                        for opt_key in OPTIONAL_OCCURRENCE_FIELDS:
                            if opt_key in raw_occ and raw_occ[opt_key] is not None:
                                occ_rec[opt_key] = raw_occ[opt_key]
                        occ_by_id[oid] = occ_rec
                        occurrences.append(occ_rec)
                        added_occ += 1
                occ_ids = list(dict.fromkeys(occ_ids))
                if not occ_ids:
                    raise ValueError(f"Claim has no occurrences: {raw_claim.get('text', '')[:60]}")
                cid = raw_claim.get("claim_id") or "clm_" + common.digest({"subject_id": raw_claim.get("subject_id", cfg["subject"]), "text": raw_claim.get("text"), "occ": sorted(occ_ids)})[:16]
                for oid in occ_ids:
                    if oid in occ_by_id and not occ_by_id[oid].get("claim_id"):
                        occ_by_id[oid]["claim_id"] = cid
                if cid not in claim_by_id:
                    c_rec = {
                        "schema_version": 1, "claim_id": cid, "subject_id": raw_claim.get("subject_id", cfg["subject"]),
                        "occurrence_ids": occ_ids, "text": raw_claim["text"], "domain": raw_claim.get("domain", "general"),
                        "claim_type": raw_claim.get("claim_type", "factual"),
                        "empirical": bool(raw_claim.get("empirical", False)),
                        "endorsement": raw_claim.get("endorsement", "endorsed"),
                        "attribution_confidence": raw_claim.get("attribution_confidence", "high"),
                        "accountability_eligible": False,
                        "quantifiability": raw_claim.get("quantifiability", "unclear"),
                        "verifiability": raw_claim.get("verifiability", "unclear"),
                        "lifecycle": raw_claim.get("lifecycle", "pending"),
                        "outcome": None, "due_for_assessment": False,
                        "evaluation_mode": raw_claim.get("evaluation_mode", "none"),
                        "probability": raw_claim.get("probability"),
                        "probability_origin": raw_claim.get("probability_origin", "none"),
                        "event_occurred": None, "criteria": raw_claim.get("criteria"),
                        "evidence_ids": [], "evidence_quality": None,
                        "review_state": "needs_review" if not all_quotes_ok else raw_claim.get("review_state", "unreviewed"),
                        "quote_verified": all_quotes_ok,
                    }
                    # Preserve optional schema fields (reason, certainty_text, first_stated_at,
                    # supersedes, next_check_at, family_id, operationalization_status, etc.)
                    # while blocking shards from forging post-adjudication fields.
                    for key, value in raw_claim.items():
                        if key in c_rec or key in EXTRACTION_PROTECTED_CLAIM_FIELDS or value is None:
                            continue
                        if key == "family_id" and not value:
                            continue
                        c_rec[key] = value
                    if not c_rec.get("first_stated_at"):
                        inferred_stated = common.earliest_stated_at(c_rec, occ_by_id, sources, cfg["scope"]["timezone"])
                        if inferred_stated:
                            c_rec["first_stated_at"] = inferred_stated
                    if c_rec.get("claim_type") == "prediction":
                        stated = common.earliest_stated_at(c_rec, occ_by_id, sources, cfg["scope"]["timezone"])
                        target_end = common.claim_target_deadline(c_rec)
                        if stated and target_end:
                            ok_t, _, detail_t = common.check_prediction_temporal_order(
                                stated, target_end, common.claim_criteria_timezone(c_rec, cfg["scope"]["timezone"])
                            )
                            if not ok_t:
                                c_rec["review_state"] = "needs_review"
                                c_rec["temporal_guard_warning"] = detail_t
                                temporal_warnings += 1
                    claim_by_id[cid] = c_rec
                    claims.append(c_rec)
                    added_claims += 1
        ledger.write_jsonl(run / "occurrences.jsonl", occurrences)
        ledger.write_jsonl(run / "claims.jsonl", claims)
        ledger.event(run, "extraction_merged", added_occurrences=added_occ, added_claims=added_claims,
                     unverified_quotes=unverified_quotes, temporal_warnings=temporal_warnings)
        return {"added_occurrences": added_occ, "added_claims": added_claims,
                "unverified_quotes": unverified_quotes, "temporal_warnings": temporal_warnings,
                "total_occurrences": len(occurrences), "total_claims": len(claims)}


def compute_coverage(ledger, run, out_path="coverage.json", inventory_complete=True):
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        selected, excluded, _ = ledger.inventory(run, cfg)
        sources = ledger.read_jsonl(run / "sources.jsonl")
        tasks = ledger.read_jsonl(run / "tasks.jsonl")
        claims = ledger.read_jsonl(run / "claims.jsonl")
        occurrences = ledger.read_jsonl(run / "occurrences.jsonl") if (run / "occurrences.jsonl").exists() else []
        by_id = ledger.unique(sources, "source_id", "sources")
        # Roll up segmented children to parent_source_id so parents aren't double-counted.
        in_scope_parents = set()
        acquired_parents = set()
        for r in selected:
            pid = r.get("parent_source_id") or r["source_id"]
            in_scope_parents.add(pid)
            acquired_parents.add(pid)
        for ex in excluded:
            sid = ex["source_id"]
            r = by_id.get(sid, {})
            if ex["reason"] in {"outside_publication_range", "unknown_publication_date", "after_as_of", "publication_time_unknown_at_cutoff"}:
                continue
            pid = r.get("parent_source_id") or sid
            in_scope_parents.add(pid)
            if r.get("status") == "segmented":
                acquired_parents.add(pid)
        completed_extract_sids = {
            sid for t in tasks if t.get("stage") == "extract" and t.get("status") == "completed"
            for sid in t.get("source_ids", [])
        }
        extracted_parents = set()
        for sid in completed_extract_sids:
            r = by_id.get(sid, {})
            pid = r.get("parent_source_id") or sid
            extracted_parents.add(pid)
        # Ensure segmented parent counts as extracted only when all its child segments finished extraction.
        for r in sources:
            if r.get("status") == "segmented" and r.get("segment_ids"):
                if not all(seg_id in completed_extract_sids for seg_id in r["segment_ids"]):
                    extracted_parents.discard(r["source_id"])
        unresolved = sum(
            1 for c in claims
            if c.get("review_state") == "needs_review"
            or (c.get("lifecycle") == "resolved" and c.get("outcome") in {"supported", "contradicted", "mixed"} and c.get("review_state") != "accepted")
        )
        unverified_q = sum(1 for o in occurrences if o.get("quote_verified") is False)
        coverage = {
            "schema_version": 1,
            "eligible_sources": len(in_scope_parents),
            "acquired_sources": len(acquired_parents),
            "extracted_sources": len(extracted_parents),
            "inventory_complete": bool(inventory_complete),
            "unresolved_review_issues": unresolved,
            "unverified_quotes": unverified_q,
            "generated_from_ledger": True,
            "generated_at": common.now(),
        }
        target = ledger.inside(run, out_path)
        common.write_json(target, coverage)
        ledger.event(run, "coverage_computed", **{k: coverage[k] for k in ("eligible_sources", "acquired_sources", "extracted_sources", "unresolved_review_issues")})
        return coverage


def new_assessment_round(ledger, run, new_as_of, reason="scheduled_reassessment"):
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        zone = ZoneInfo(cfg["scope"]["timezone"])
        as_of_dt = ledger.resolve_as_of_time(new_as_of, zone)
        rounds = cfg.setdefault("assessment_rounds", [])
        rounds.append({"as_of": cfg["scope"]["as_of"], "config_hash": cfg["config_hash"], "closed_at": common.now()})
        cfg["scope"]["as_of"] = as_of_dt.astimezone(timezone.utc).isoformat()
        cfg["config_hash"] = ledger.digest(ledger.config_body(cfg))
        common.write_json(run / "run.json", cfg)
        claims = ledger.read_jsonl(run / "claims.jsonl")
        updated_due = 0
        for c in claims:
            if c.get("accountability_eligible") and c.get("criteria") and c.get("lifecycle") in {"pending", "ready"}:
                if c.get("reason") == "trigger_unmet" or (c.get("trigger_assessment") or {}).get("state") == "unmet":
                    continue
                defn = c["criteria"]["definition"]
                end = defn.get("window_end")
                due = True if not end else ledger.as_of_time(end, ZoneInfo(defn["timezone"])) <= as_of_dt
                if due and not c.get("due_for_assessment"):
                    c["due_for_assessment"] = True
                    c["lifecycle"] = "ready"
                    updated_due += 1
        ledger.write_jsonl(run / "claims.jsonl", claims)
        ledger.event(run, "assessment_round_started", new_as_of=cfg["scope"]["as_of"], newly_due=updated_due, reason=reason)
        ledger.progress(run)
        return {"as_of": cfg["scope"]["as_of"], "config_hash": cfg["config_hash"], "newly_due_claims": updated_due}


def _resolve_rubric(rubric_path=None):
    path = Path(rubric_path).resolve() if rubric_path else DEFAULT_RUBRIC_PATH
    rubric = common.read_json(path)
    return path, rubric, common.digest(rubric)


def _format_seconds_clock(value):
    total = int(round(float(value)))
    hours, rem = divmod(max(0, total), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _format_locator(locator):
    if not isinstance(locator, dict):
        return ""
    kind = locator.get("kind") or ""
    start, end = locator.get("start"), locator.get("end")
    parts = []
    if kind in {"cue", "timestamp"} and common.finite_number(start):
        span = _format_seconds_clock(start)
        if common.finite_number(end):
            span += "–" + _format_seconds_clock(end)
        parts.append(span)
    elif start is not None:
        span = f"{kind} {start}".strip()
        if end is not None and end != start:
            span += f"–{end}"
        parts.append(span)
    start_u = locator.get("start_unit") or locator.get("unit_id") or locator.get("id")
    end_u = locator.get("end_unit")
    if start_u:
        unit_span = f"{start_u}–{end_u}" if end_u and end_u != start_u else str(start_u)
        parts.append(unit_span)
    return " · ".join(parts)


def _extract_decision_rationale(ledger, run, claim):
    acceptance = claim.get("acceptance")
    if isinstance(acceptance, dict) and common.nonempty(acceptance.get("decision_path")):
        try:
            dec_path = ledger.inside(run, acceptance["decision_path"])
            if dec_path.is_file():
                artifact = common.read_json(dec_path)
                cons = artifact.get("consensus") or {}
                dec = cons.get("decision")
                if isinstance(dec, dict) and common.nonempty(dec.get("rationale")):
                    return dec["rationale"].strip()
                votes = cons.get("votes") or []
                vote_rationales = []
                seen = set()
                for vote in votes:
                    rat = (vote.get("rationale") or "").strip() if isinstance(vote, dict) else ""
                    if rat and rat not in seen:
                        seen.add(rat)
                        rid = vote.get("reviewer_id")
                        vote_rationales.append((rid, rat))
                if len(vote_rationales) == 1:
                    return vote_rationales[0][1]
                if len(vote_rationales) > 1:
                    return "; ".join(f"[{rid}] {rat}" if rid else rat for rid, rat in vote_rationales)
        except (ValueError, OSError, KeyError, TypeError):
            pass
    return f"lifecycle={claim['lifecycle']}, mode={claim['evaluation_mode']}"


def _compute_report_inputs(ledger, run, metrics_path="reports/metrics.json", coverage_path="coverage.json",
                           rubric_path=None, subject_id=None):
    metrics_file = ledger.inside(run, metrics_path)
    cov_file = ledger.inside(run, coverage_path)
    metrics = common.read_json(metrics_file) if metrics_file.exists() else None
    coverage = common.read_json(cov_file) if cov_file.exists() else {}
    claims = ledger.read_jsonl(run / "claims.jsonl")
    if subject_id is not None:
        claims = [c for c in claims if c.get("subject_id") == subject_id]
        if not claims:
            raise ValueError(f"No claims found for selected subject_id: {subject_id}")
    r_path, rubric, rubric_hash = _resolve_rubric(rubric_path)
    data_hash = common.digest({"claims": claims, "coverage": coverage, "metrics": metrics})
    return {
        "metrics": metrics, "metrics_present": metrics_file.exists(),
        "coverage": coverage, "coverage_present": cov_file.exists(),
        "claims": claims, "rubric": rubric, "rubric_path": str(r_path),
        "rubric_hash": rubric_hash, "data_hash": data_hash,
    }


def report_hashes(ledger, run, metrics_path="reports/metrics.json", coverage_path="coverage.json",
                  rubric_path=None, subject_id=None):
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        ledger.config(run)
        computed = _compute_report_inputs(ledger, run, metrics_path, coverage_path, rubric_path, subject_id=subject_id)
        return {
            "data_hash": computed["data_hash"],
            "rubric_hash": computed["rubric_hash"],
            "rubric_path": computed["rubric_path"],
            "score_scale": computed["rubric"].get("scale"),
            "claims_count": len(computed["claims"]),
            "subject_id": subject_id,
            "metrics_present": computed["metrics_present"],
            "coverage_present": computed["coverage_present"],
        }


def build_report_data(ledger, run, out_path="reports/report-data.json", metrics_path="reports/metrics.json",
                      coverage_path="coverage.json", title=None, synthetic=False, rubric_path=None, subject_id=None):
    import model_panel as panel
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        computed = _compute_report_inputs(ledger, run, metrics_path, coverage_path, rubric_path, subject_id=subject_id)
        metrics = computed["metrics"]
        coverage = computed["coverage"]
        claims = computed["claims"]
        rubric = computed["rubric"]
        data_hash = computed["data_hash"]
        sources_rows = ledger.read_jsonl(run / "sources.jsonl")
        sources_by_id = {s["source_id"]: s for s in sources_rows if isinstance(s, dict) and s.get("source_id")}
        evidence_rows = ledger.read_jsonl(run / "evidence.jsonl")
        occurrences_rows = ledger.read_jsonl(run / "occurrences.jsonl") if (run / "occurrences.jsonl").exists() else []
        occ_by_id = {o["occurrence_id"]: o for o in occurrences_rows if isinstance(o, dict) and o.get("occurrence_id")}
        costs_rows = ledger.read_jsonl(run / "costs.jsonl") if (run / "costs.jsonl").exists() else []
        est_usd = sum(r.get("estimated_usd") or 0 for r in costs_rows) if costs_rows else None
        obs_vals = [r["actual_usd"] for r in costs_rows if r.get("actual_usd") is not None]
        obs_usd = sum(obs_vals) if obs_vals else None
        report_sources = []
        seen_sids = set()
        for s in sources_rows:
            sid = s["source_id"]
            if sid in seen_sids:
                continue
            seen_sids.add(sid)
            report_sources.append({
                "id": sid, "title": s.get("title") or sid,
                "url": s.get("source_url"), "published_at": s.get("published_at"),
                "locator": s.get("content_path") or "", "excerpt": s.get("notes") or "",
            })
        for e in evidence_rows:
            eid = e["evidence_id"]
            if eid in seen_sids:
                continue
            seen_sids.add(eid)
            report_sources.append({
                "id": eid, "title": e.get("title") or eid,
                "url": e.get("source_url"), "published_at": e.get("published_at"),
                "locator": e.get("local_path") or e.get("source_family") or "", "excerpt": e.get("excerpt") or "",
            })
        cases = []
        for c in claims:
            lifecycle = c.get("lifecycle")
            is_resolved = lifecycle == "resolved"
            is_notable_pending = lifecycle == "pending" and (
                c.get("reason") == "trigger_unmet" or c.get("criteria") is not None
            )
            is_notable_hypothetical = lifecycle == "unscorable" and c.get("claim_type") == "hypothetical"
            if not (is_resolved or is_notable_pending or is_notable_hypothetical):
                continue
            occ_details = []
            occ_source_ids = []
            for oid in c.get("occurrence_ids") or []:
                occ = occ_by_id.get(oid)
                if not occ:
                    continue
                ts = _format_locator(occ.get("locator"))
                occ_details.append({
                    "occurrence_id": oid,
                    "source_id": occ.get("source_id"),
                    "speaker": occ.get("speaker"),
                    "endorsement": occ.get("endorsement"),
                    "original_quote": occ.get("original_quote") or "",
                    "locator": occ.get("locator"),
                    "timestamp": ts,
                })
                if occ.get("source_id") in seen_sids and occ["source_id"] not in occ_source_ids:
                    occ_source_ids.append(occ["source_id"])
            first_quote = next((o["original_quote"] for o in occ_details if o["original_quote"]), None)
            primary_speaker = next((o["speaker"] for o in occ_details if common.nonempty(o.get("speaker"))), None) or c.get("subject_id")
            timestamps = [o["timestamp"] for o in occ_details if o["timestamp"]]
            ts_summary = ", ".join(dict.fromkeys(timestamps))
            if is_resolved:
                status = c.get("outcome") or "not_checked"
                assessment = _extract_decision_rationale(ledger, run, c)
            elif is_notable_pending:
                status = "pending"
                if c.get("reason") == "trigger_unmet":
                    trig_note = ((c.get("trigger_assessment") or {}).get("note") or "").strip()
                    cond = ((c.get("criteria") or {}).get("definition") or {}).get("condition")
                    cond_text = cond.get("trigger") if isinstance(cond, dict) else (cond if isinstance(cond, str) else "")
                    assessment = "Conditional trigger unmet (pending, not scored as error)."
                    if cond_text:
                        assessment += f" Condition: {cond_text}."
                    if trig_note:
                        assessment += f" {trig_note}"
                else:
                    reason = c.get("reason") or "not_yet_due"
                    assessment = f"Pending assessment ({reason}; not scored as error)."
            else:
                status = "not_checked"
                reason = c.get("reason") or "hypothetical_scenario"
                assessment = f"Unscorable hypothetical scenario ({reason}); excluded from empirical accuracy denominators."
            ev_ids = [eid for eid in c.get("evidence_ids", []) if eid in seen_sids]
            if not ev_ids:
                ev_ids = occ_source_ids
            lead_time_days = None
            if c.get("claim_type") == "prediction":
                stated_at = common.earliest_stated_at(c, occ_by_id, sources_by_id, cfg["scope"]["timezone"])
                target_end = common.claim_target_deadline(c)
                if stated_at and target_end:
                    try:
                        ok_lt, lt_val, _ = common.check_prediction_temporal_order(
                            stated_at, target_end, common.claim_criteria_timezone(c, cfg["scope"]["timezone"])
                        )
                        if ok_lt:
                            lead_time_days = lt_val
                    except ValueError:
                        lead_time_days = None
            diff_tier = common.resolve_difficulty_tier(c)
            note_parts = [c["claim_id"], c.get("claim_type") or "claim"]
            if diff_tier != "unrated":
                note_parts.append(f"difficulty={diff_tier}")
            if lead_time_days is not None:
                note_parts.append(f"lead={lead_time_days:g}d")
            if c.get("reason"):
                note_parts.append(f"reason={c['reason']}")
            if ts_summary:
                note_parts.append(ts_summary)
            case_obj = {
                "id": c["claim_id"],
                "title": c["text"][:80],
                "claim": c["text"],
                "claim_type": c.get("claim_type"),
                "subject_id": c.get("subject_id"),
                "speaker": primary_speaker,
                "endorsement": c.get("endorsement"),
                "lifecycle": lifecycle,
                "status": status,
                "assessment": assessment,
                "evidence_ids": ev_ids,
                "notes": " · ".join(note_parts),
            }
            if diff_tier != "unrated":
                case_obj["difficulty"] = diff_tier
            if c.get("difficulty_score") is not None:
                case_obj["difficulty_score"] = c["difficulty_score"]
            if c.get("difficulty_rationale"):
                case_obj["difficulty_rationale"] = c["difficulty_rationale"]
            if lead_time_days is not None:
                case_obj["lead_time_days"] = lead_time_days
            if first_quote:
                case_obj["original_quote"] = first_quote
            if ts_summary:
                case_obj["timestamps"] = ts_summary
            if occ_details:
                case_obj["occurrences"] = occ_details
            cases.append(case_obj)
        panel_obj = None
        pol_path = run / "config/model-policy.json"
        rep_dir = run / "reviews/reports"
        if pol_path.exists() and rep_dir.exists():
            rep_files = sorted(rep_dir.glob("*.json"))
            if rep_files:
                pol = panel.load_policy(pol_path)
                reviews = [common.read_json(f) for f in rep_files]
                panel_obj = {"policy": pol, "reviews": reviews}
        summary_lines = [f"Total canonical claims: {len(claims)}."]
        if isinstance(metrics, dict):
            sr = metrics.get("strict_support_rate") or {}
            if sr.get("denominator"):
                summary_lines.append(
                    f"Strict support rate: {sr['value'] * 100:.1f}% ({sr['numerator']}/{sr['denominator']} adjudicated categorical claims)."
                )
            by_type = metrics.get("by_claim_type") or {}
            splits = []
            for ctype in ("factual", "prediction"):
                tsr = (by_type.get(ctype) or {}).get("strict_support_rate") or {}
                if tsr.get("denominator"):
                    splits.append(f"{ctype}: {tsr['value'] * 100:.1f}% ({tsr['numerator']}/{tsr['denominator']})")
            if splits:
                summary_lines.append("Claim-type split — " + "; ".join(splits) + ".")
            pdiff = metrics.get("prediction_difficulty") or {}
            nt_sr = pdiff.get("non_trivial_strict_support_rate") or {}
            if pdiff.get("rated_n") and nt_sr.get("denominator"):
                summary_lines.append(
                    f"Non-trivial prediction support rate: {nt_sr['value'] * 100:.1f}% ({nt_sr['numerator']}/{nt_sr['denominator']}; {pdiff['rated_n']} rated predictions)."
                )
            phor = metrics.get("prediction_horizon") or {}
            if phor.get("dated_n") and phor.get("mean_lead_time_days") is not None:
                summary_lines.append(
                    f"Dated predictions ({phor['dated_n']}): mean lead time {phor['mean_lead_time_days']:.1f}d, median {phor['median_lead_time_days']:.1f}d."
                )
        report_subject = subject_id or cfg["subject"]
        payload = {
            "schema_version": 1, "synthetic": bool(synthetic), "data_hash": data_hash,
            "rubric": rubric,
            "report": {
                "title": title or f"Claim Audit: {report_subject}",
                "subject": report_subject,
                "period_start": cfg["scope"]["start"], "period_end": cfg["scope"]["end"],
                "as_of": cfg["scope"]["as_of"][:10], "generated_at": common.now()[:10],
                "summary": summary_lines,
            },
            "metrics": metrics, "panel": panel_obj, "topics": [], "cases": cases,
            "coverage": coverage,
            "costs": {"estimated_usd": est_usd, "observed_usd": obs_usd, "budget_usd": (cfg.get("costs") or {}).get("approved_budget_usd")},
            "sources": report_sources,
        }
        target = ledger.inside(run, out_path)
        common.write_json(target, payload)
        return {"report_data_path": str(target), "data_hash": data_hash, "rubric_hash": computed["rubric_hash"],
                "cases": len(cases), "sources": len(report_sources)}


def handoff_export(ledger, run, task_ids, packet_id=None):
    run = Path(run).resolve()
    with ledger.coordinator_lock(run):
        cfg = ledger.config(run)
        tasks = ledger.read_jsonl(run / "tasks.jsonl")
        by_id = ledger.unique(tasks, "task_id", "tasks")
        selected_tasks = []
        for tid in task_ids:
            if tid not in by_id:
                raise ValueError(f"Unknown task_id: {tid}")
            t = by_id[tid]
            if t.get("status") == "completed":
                raise ValueError(f"Task {tid} is already completed")
            selected_tasks.append(t)
        pid = packet_id or "pkt_" + common.digest({"tasks": task_ids, "at": common.now()})[:12]
        out_dir = ledger.inside(run, f"handoff/outbound/{pid}")
        if out_dir.exists():
            raise ValueError(f"Handoff packet already exists: {pid}")
        out_dir.mkdir(parents=True, exist_ok=True)
        payloads = []
        for t in selected_tasks:
            p_bytes = ledger.inside(run, t["payload_path"]).read_bytes()
            payloads.append({"task_id": t["task_id"], "stage": t.get("stage"), "input_fingerprint": t.get("input_fingerprint"),
                             "payload_hash": t.get("payload_hash"), "payload": json.loads(p_bytes)})
            t["status"] = "blocked"
            t["note"] = f"external_handoff:{pid}"
            t["updated_at"] = common.now()
        manifest = {"schema_version": 1, "packet_id": pid, "run_id": cfg["run_id"], "config_hash": cfg["config_hash"],
                    "subject": cfg["subject"], "scope": cfg["scope"], "cutoff_mode": cfg["cutoff_mode"],
                    "task_ids": [t["task_id"] for t in selected_tasks], "created_at": common.now()}
        common.write_json(out_dir / "manifest.json", manifest)
        common.write_json(out_dir / "tasks-bundle.json", payloads)
        common.write_json(out_dir / "result-template.json", {
            "packet_id": pid, "executor": {"platform": "external_web_or_human", "model_identity": "unknown"},
            "results": [{"task_id": p["task_id"], "input_fingerprint": p["input_fingerprint"], "complete": True,
                         "processed_source_ids": p["payload"].get("source_ids") or [s["source_id"] for s in p["payload"].get("sources", [])],
                         "claims": []} for p in payloads]})
        common.atomic_text(out_dir / "instructions.md",
            f"# External Handoff Packet `{pid}`\n\n- Subject: `{cfg['subject']}`\n- Scope: `{cfg['scope']['start']}..{cfg['scope']['end']}` (as_of `{cfg['scope']['as_of']}`, `{cfg['cutoff_mode']}`)\n- Fill `result-template.json` without changing `task_id` or `input_fingerprint`, then import via `audit_run.py handoff-import`.\n")
        ledger.write_jsonl(run / "tasks.jsonl", tasks)
        ledger.event(run, "handoff_exported", packet_id=pid, task_ids=task_ids)
        ledger.progress(run)
        return {"packet_id": pid, "packet_dir": str(out_dir), "tasks_blocked": len(selected_tasks)}


def handoff_import(ledger, run, packet_id, result_file):
    run = Path(run).resolve()
    src = Path(result_file).resolve()
    data = common.read_json(src)
    with ledger.coordinator_lock(run):
        manifest = common.read_json(ledger.inside(run, f"handoff/outbound/{packet_id}/manifest.json"))
        if data.get("packet_id") != packet_id:
            raise ValueError("Handoff result packet_id mismatch")
        inbound_rel = f"handoff/inbound/{packet_id}-raw.json"
        common.atomic_bytes(ledger.inside(run, inbound_rel), src.read_bytes())
        tasks = ledger.read_jsonl(run / "tasks.jsonl")
        by_id = ledger.unique(tasks, "task_id", "tasks")
        imported = []
        for res in data.get("results", []):
            tid = res.get("task_id")
            if tid not in manifest["task_ids"] or tid not in by_id:
                raise ValueError(f"Unexpected task_id in handoff result: {tid}")
            task = by_id[tid]
            if res.get("input_fingerprint") != task.get("input_fingerprint"):
                raise ValueError(f"input_fingerprint mismatch for {tid}")
            res_rel = f"work/results/{tid}_handoff.json"
            common.write_json(ledger.inside(run, res_rel), res)
            ledger.check_result(run, task, res_rel)
            task["status"] = "completed"
            task["attempts"] = max(1, task.get("attempts", 0))
            task["result_path"] = res_rel
            task["result_hash"] = hashlib.sha256(ledger.inside(run, res_rel).read_bytes()).hexdigest()
            task["updated_at"] = common.now()
            imported.append(tid)
        ledger.write_jsonl(run / "tasks.jsonl", tasks)
        receipt = {"schema_version": 1, "packet_id": packet_id, "inbound_raw": inbound_rel,
                   "inbound_sha256": common.file_sha(ledger.inside(run, inbound_rel)),
                   "executor": data.get("executor", {}), "imported_tasks": imported, "imported_at": common.now()}
        with (run / "handoff/receipts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(common.canonical(receipt) + "\n")
        ledger.event(run, "handoff_imported", packet_id=packet_id, imported_tasks=imported)
        ledger.progress(run)
        return receipt
