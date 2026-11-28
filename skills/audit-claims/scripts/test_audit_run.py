#!/usr/bin/env python3
"""Offline regressions for checkpoint integrity, coverage and batch bounds."""
from argparse import Namespace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import audit_run as audit


class AuditRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / 'run'
        self.args = Namespace(run=str(self.run), subject='Example speaker', start='2021-11-25',
                              end='2026-11-25', as_of='2026-11-25', timezone='Asia/Singapore',
                              cutoff_mode='retrospective')
        audit.init(self.args)

    def sources(self, rows):
        audit.write_jsonl(self.run / 'sources.jsonl', rows)

    def source(self, sid, text='A concrete claim.', **overrides):
        name = f'sources/{sid}.md'
        audit.atomic_text(self.run / name, text)
        return {'source_id': sid, 'title': sid, 'source_url': f'https://example.test/{sid}',
                'published_at': '2024-01-01', 'content_path': name, 'status': 'ready', **overrides}

    def plan(self, budget=500, max_items=10):
        return audit.plan_batches(Namespace(run=str(self.run), token_budget=budget, max_items=max_items))

    def task(self):
        return audit.read_jsonl(self.run / 'tasks.jsonl')[0]

    def result(self, task=None, **overrides):
        task = task or self.task()
        name = f"work/results/{task['task_id']}.json"
        body = {'task_id': task['task_id'], 'input_fingerprint': task['input_fingerprint'],
                'complete': True, 'processed_source_ids': task['source_ids'], 'claims': [], **overrides}
        audit.write_json(self.run / name, body)
        return name

    def checkpoint(self, state, result=None):
        return audit.checkpoint(Namespace(run=str(self.run), task_id=self.task()['task_id'],
                                         status=state, result=result, note=None))

    def test_reinit_does_not_reset_tasks(self):
        self.sources([self.source('a')])
        self.plan()
        self.checkpoint('running')
        audit.init(self.args)
        self.assertEqual(self.task()['status'], 'running')
        self.assertEqual(self.task()['attempts'], 1)

    def test_as_of_date_is_local_end_of_day(self):
        cfg = audit.config(self.run)
        self.assertEqual(cfg['scope']['as_of'], '2026-11-25T15:59:59.999999+00:00')
        self.assertEqual(cfg['cutoff_mode'], 'retrospective')

    def test_naive_as_of_datetime_rejected(self):
        self.args.run = str(self.run.parent / 'other')
        self.args.as_of = '2026-11-25T12:00:00'
        with self.assertRaisesRegex(ValueError, 'UTC offset'):
            audit.init(self.args)

    def test_scope_dates_use_local_timezone_and_are_inclusive(self):
        self.sources([self.source('start', published_at='2021-11-24T16:00:00Z'),
                      self.source('end', published_at='2026-11-25T15:59:59Z'),
                      self.source('before', published_at='2021-11-24T15:59:59Z'),
                      self.source('after', published_at='2026-11-25T16:00:00Z'),
                      self.source('naive', published_at='2026-11-25T12:00:00')])
        output = self.plan(2000)['batch_plan']
        self.assertEqual(output['batched_sources'], 2)
        reasons = {row['source_id']: row['reason'] for row in output['excluded']}
        self.assertEqual(reasons['naive'], 'unknown_publication_date')
        self.assertEqual(reasons['before'], 'outside_publication_range')
        self.assertEqual(reasons['after'], 'outside_publication_range')

    def test_cjk_bound_and_large_sources_are_not_truncated(self):
        self.sources([self.source('small', text='汉字'*20), self.source('large', text='汉字'*100)])
        output = self.plan(400)['batch_plan']
        self.assertEqual(output['batched_sources'], 1)
        self.assertEqual(output['needs_segmentation'][0]['source_id'], 'large')
        payload = audit.read_json(self.run / self.task()['payload_path'])
        self.assertEqual(payload['sources'][0]['estimated_tokens'], 248)
        self.assertEqual((self.run / 'sources/large.md').read_text(), '汉字'*100)

    def test_failures_missing_and_truncated_not_success(self):
        missing = self.source('missing')
        (self.run / missing['content_path']).unlink()
        self.sources([self.source('ok'), self.source('failed', status='failed'),
                      self.source('truncated', status='truncated'), missing])
        output = self.plan()['batch_plan']
        self.assertEqual(output['in_scope_sources'], 4)
        self.assertEqual(output['eligible_sources'], 1)
        self.assertEqual(len(output['excluded']), 3)

    def test_planning_is_idempotent_after_completion(self):
        self.sources([self.source('a'), self.source('b')])
        self.plan()
        path = self.result()
        self.checkpoint('running')
        self.checkpoint('completed', path)
        old_task = self.task()
        self.plan()
        self.assertEqual(self.task(), old_task)
        self.assertTrue(audit.validate(self.run)['valid'])

    def test_content_change_blocks_resume(self):
        self.sources([self.source('a')])
        self.plan()
        (self.run / 'sources/a.md').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.plan()
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.checkpoint('running')

    def test_supplied_hash_cannot_mask_content_change(self):
        row = self.source('a')
        row['content_hash'] = hashlib.sha256(b'wrong').hexdigest()
        self.sources([row])
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.plan()

    def test_partial_worker_coverage_is_rejected(self):
        self.sources([self.source('a'), self.source('b')])
        self.plan()
        with self.assertRaisesRegex(ValueError, 'cover exactly'):
            self.checkpoint('completed', self.result(processed_source_ids=['a']))
        self.assertEqual(self.task()['status'], 'pending')

    def test_partial_worker_output_is_rejected(self):
        self.sources([self.source('a')])
        self.plan()
        with self.assertRaisesRegex(ValueError, 'complete=true'):
            self.checkpoint('completed', self.result(complete=False))

    def test_completed_artifact_change_detected(self):
        self.sources([self.source('a')])
        self.plan()
        name = self.result()
        self.checkpoint('completed', name)
        value = audit.read_json(self.run / name)
        value['claims'] = [{'claim_id': 'invented'}]
        audit.write_json(self.run / name, value)
        with self.assertRaisesRegex(ValueError, 'result changed'):
            audit.validate(self.run)

    def test_max_items_and_token_budget_both_bound_batches(self):
        self.sources([self.source(str(i), estimated_tokens=100) for i in range(7)])
        self.plan(500, 2)
        tasks = audit.read_jsonl(self.run / 'tasks.jsonl')
        self.assertEqual([len(task['source_ids']) for task in tasks], [2, 2, 2, 1])
        for task in tasks:
            payload = audit.read_json(self.run / task['payload_path'])
            self.assertLessEqual(sum(source['estimated_tokens'] for source in payload['sources']), 500)

    def test_scope_change_and_input_rebatch_need_new_run(self):
        self.sources([self.source('a')])
        self.plan()
        with self.assertRaisesRegex(ValueError, 'parameters changed'):
            self.plan(600)
        cfg = audit.read_json(self.run / 'run.json')
        cfg['scope']['end'] = '2026-11-24'
        audit.write_json(self.run / 'run.json', cfg)
        with self.assertRaisesRegex(ValueError, 'scope/config changed'):
            audit.validate(self.run)

    def test_runtime_budget_changes_do_not_invalidate_semantics(self):
        cfg = audit.read_json(self.run / 'run.json')
        cfg['execution']['max_workers'] = 1
        cfg['costs'] = {'approved_budget_usd': 3}
        audit.write_json(self.run / 'run.json', cfg)
        self.assertTrue(audit.validate(self.run)['valid'])

    def test_two_coordinators_cannot_write_simultaneously(self):
        with audit.coordinator_lock(self.run):
            with self.assertRaisesRegex(ValueError, 'Another coordinator'):
                with audit.coordinator_lock(self.run):
                    pass

    def test_paths_cannot_escape_run(self):
        self.sources([self.source('a', content_path='../private.txt')])
        output = self.plan()['batch_plan']
        self.assertEqual(output['eligible_sources'], 0)
        self.assertEqual(output['excluded'][0]['reason'], 'invalid_content_path_or_empty')

    def test_exact_as_of_excludes_later_publication(self):
        self.args.run = str(self.run.parent / 'midday')
        self.args.as_of = '2026-11-25T12:00:00+08:00'
        audit.init(self.args)
        self.run = Path(self.args.run)
        self.sources([self.source('early', published_at='2026-11-25T03:00:00Z'),
                      self.source('late', published_at='2026-11-25T05:00:00Z'),
                      self.source('date_only', published_at='2026-11-25')])
        output = self.plan()['batch_plan']
        self.assertEqual(output['eligible_sources'], 1)
        self.assertEqual({x['reason'] for x in output['excluded']}, {'after_as_of', 'publication_time_unknown_at_cutoff'})


    def test_missing_planned_task_is_not_completed_coverage(self):
        self.sources([self.source('a'), self.source('b')])
        self.plan(500, 1)
        tasks = audit.read_jsonl(self.run / 'tasks.jsonl')
        audit.write_jsonl(self.run / 'tasks.jsonl', tasks[:1])
        with self.assertRaisesRegex(ValueError, 'plan.task_ids'):
            audit.validate(self.run)
        with self.assertRaisesRegex(ValueError, 'plan.task_ids'):
            self.checkpoint('completed', self.result())

    def test_task_cannot_reduce_immutable_source_coverage(self):
        self.sources([self.source('a'), self.source('b')])
        self.plan()
        tasks = audit.read_jsonl(self.run / 'tasks.jsonl')
        tasks[0]['source_ids'] = ['a']
        audit.write_jsonl(self.run / 'tasks.jsonl', tasks)
        with self.assertRaisesRegex(ValueError, 'source_ids differ'):
            self.checkpoint('completed', self.result())
        with self.assertRaisesRegex(ValueError, 'source_ids differ'):
            audit.validate(self.run)

    def test_generic_verification_payload_is_immutable(self):
        payload_path = self.run / 'work/batches/verify-1.json'
        payload = {'task_id': 'verify-1', 'input_fingerprint': 'frozen-rule-1',
                   'criterion': 'Measure the original stated threshold.'}
        audit.write_json(payload_path, payload)
        task = {'task_id': 'verify-1', 'stage': 'verify', 'input_fingerprint': 'frozen-rule-1',
                'status': 'pending', 'dependencies': [], 'payload_path': 'work/batches/verify-1.json',
                'payload_hash': hashlib.sha256(payload_path.read_bytes()).hexdigest()}
        audit.write_jsonl(self.run / 'tasks.jsonl', [task])
        self.assertTrue(audit.validate(self.run)['valid'])
        payload['criterion'] = 'Move the threshold after observing the outcome.'
        audit.write_json(payload_path, payload)
        with self.assertRaisesRegex(ValueError, 'Payload hash changed'):
            audit.validate(self.run)

    def test_verification_without_payload_hash_is_rejected(self):
        payload = {'task_id': 'v', 'input_fingerprint': 'f'}
        audit.write_json(self.run / 'work/batches/v.json', payload)
        task = {'task_id': 'v', 'stage': 'verify', 'input_fingerprint': 'f',
                'status': 'pending', 'dependencies': [], 'payload_path': 'work/batches/v.json'}
        audit.write_jsonl(self.run / 'tasks.jsonl', [task])
        with self.assertRaisesRegex(ValueError, 'payload_hash'):
            audit.validate(self.run)

    def test_future_as_of_and_nan_rejected_and_unique_run_id(self):
        other = Namespace(**vars(self.args))
        other.run = str(self.run.parent / 'run_same_scope')
        audit.init(other)
        self.assertNotEqual(audit.config(self.run)['run_id'], audit.config(Path(other.run))['run_id'])
        bad = Namespace(**vars(self.args))
        bad.run = str(self.run.parent / 'future_run')
        bad.as_of = '2099-01-01'
        with self.assertRaisesRegex(ValueError, 'future'):
            audit.init(bad)
        with self.assertRaisesRegex(ValueError, 'Out of range|allow_nan'):
            audit.canonical({'x': float('nan')})

    def test_deterministic_glue_pipeline_segment_merge_freeze_coverage_and_handoff(self):
        import audit_pipeline as pipeline
        import model_panel as panel
        # Segment an oversized source, plan, run extraction, verify quotes, freeze criteria, compute coverage & handoff.
        long_text = '\n\n'.join(f'Sentence {i} states fact {i}.' for i in range(1, 35))
        import normalize_sources as norm
        inp = self.run.parent / 'inp'
        inp.mkdir()
        (inp / 'long.txt').write_text(long_text, encoding='utf-8')
        norm.ingest(Namespace(manifest=str(self._write_manifest(inp, 'long.txt')), run=str(self.run),
                              max_bytes=1024*1024, max_batch_bytes=1024*1024, locator_mode='compact',
                              clean_youtube_vtt=False, append=False))
        seg_res = pipeline.segment_source(audit, self.run, 's1', token_budget=320, overlap_units=1)
        self.assertGreaterEqual(len(seg_res['segments']), 2)
        self.plan(budget=400, max_items=10)
        tasks = audit.read_jsonl(self.run / 'tasks.jsonl')
        first_task = tasks[0]
        # Test external handoff export/import on second task if present, or checkpoint first task + merge quote check.
        bad_shard = {'task_id': first_task['task_id'], 'input_fingerprint': first_task['input_fingerprint'],
                     'complete': True, 'processed_source_ids': first_task['source_ids'],
                     'claims': [
                         {'text': 'Real fact 1', 'claim_type': 'factual', 'empirical': True, 'verifiability': 'verifiable',
                          'occurrences': [{'source_id': first_task['source_ids'][0], 'original_quote': 'Sentence 1 states fact 1.',
                                           'locator': {'kind': 'paragraph', 'unit_id': 'p-000001', 'start': 1, 'end': 1}}]},
                         {'text': 'Hallucinated quote', 'claim_type': 'factual', 'empirical': True,
                          'occurrences': [{'source_id': first_task['source_ids'][0], 'original_quote': 'Never said this.',
                                           'locator': {'kind': 'paragraph', 'unit_id': 'p-000001', 'start': 1, 'end': 1}}]},
                     ]}
        res_rel = f"work/results/{first_task['task_id']}.json"
        audit.write_json(self.run / res_rel, bad_shard)
        audit.checkpoint(Namespace(run=str(self.run), task_id=first_task['task_id'], status='completed', result=res_rel, note=None))
        merged = pipeline.merge_extraction(audit, self.run)
        self.assertEqual(merged['unverified_quotes'], 1)
        claims = {c['text']: c for c in audit.read_jsonl(self.run / 'claims.jsonl')}
        self.assertTrue(claims['Real fact 1']['quote_verified'])
        self.assertFalse(claims['Hallucinated quote']['quote_verified'])
        self.assertEqual(claims['Hallucinated quote']['review_state'], 'needs_review')
        def_path = self.run / 'crit_def.json'
        audit.write_json(def_path, {'target': 'fact 1', 'predicate': 'true', 'window_start': '2024-01-01',
                                    'window_end': '2024-12-31', 'timezone': 'UTC', 'condition': 'unconditional',
                                    'resolution_basis': 'explicit'})
        frozen = pipeline.freeze_criteria(audit, self.run, claims['Real fact 1']['claim_id'], def_path)
        self.assertTrue(frozen['due_for_assessment'])
        cov = pipeline.compute_coverage(audit, self.run)
        self.assertEqual(cov['eligible_sources'], 1)
        self.assertEqual(cov['acquired_sources'], 1)
        if len(tasks) > 1:
            t2 = tasks[1]
            pkt = pipeline.handoff_export(audit, self.run, [t2['task_id']], packet_id='pkt1')
            self.assertEqual(pkt['tasks_blocked'], 1)
            ret = self.run / 'ret.json'
            audit.write_json(ret, {'packet_id': 'pkt1', 'results': [{
                'task_id': t2['task_id'], 'input_fingerprint': t2['input_fingerprint'],
                'complete': True, 'processed_source_ids': t2['source_ids'], 'claims': []}]})
            imp = pipeline.handoff_import(audit, self.run, 'pkt1', ret)
            self.assertEqual(imp['imported_tasks'], [t2['task_id']])

    def test_merge_extraction_preserves_optional_fields_and_blocks_forged_verdicts(self):
        import audit_pipeline as pipeline
        self.sources([self.source('s1', text='[#cue-000001 10-15s]\nBitcoin might hit 120k.\n')])
        self.plan(budget=2000, max_items=10)
        task = self.task()
        shard = {
            'task_id': task['task_id'], 'input_fingerprint': task['input_fingerprint'],
            'complete': True, 'processed_source_ids': ['s1'],
            'claims': [{
                'claim_id': 'clm_opt_1', 'text': 'Hypothetical BTC 120k scenario',
                'claim_type': 'hypothetical', 'empirical': False, 'verifiability': 'unverifiable',
                'lifecycle': 'unscorable', 'reason': 'hypothetical_scenario',
                'certainty_text': 'dubious speculation', 'first_stated_at': '2025-01-07T00:08:56+00:00',
                'supersedes': ['clm_old_0'], 'next_check_at': '2026-01-01T00:00:00+00:00',
                'family_id': 'fam_btc_hyp',
                # Protected fields that an extraction shard must not be able to forge:
                'outcome': 'supported', 'evidence_ids': ['ev_forged'], 'acceptance': {'decision_path': 'x'},
                'occurrences': [{'source_id': 's1', 'original_quote': 'Bitcoin might hit 120k.',
                                 'locator': {'kind': 'cue', 'unit_id': 'cue-000001', 'start': 10.0, 'end': 15.0}}],
            }],
        }
        res_rel = f"work/results/{task['task_id']}.json"
        audit.write_json(self.run / res_rel, shard)
        audit.checkpoint(Namespace(run=str(self.run), task_id=task['task_id'], status='completed', result=res_rel, note=None))
        pipeline.merge_extraction(audit, self.run)
        merged_claim = audit.read_jsonl(self.run / 'claims.jsonl')[0]
        self.assertEqual(merged_claim['reason'], 'hypothetical_scenario')
        self.assertEqual(merged_claim['certainty_text'], 'dubious speculation')
        self.assertEqual(merged_claim['first_stated_at'], '2025-01-07T00:08:56+00:00')
        self.assertEqual(merged_claim['supersedes'], ['clm_old_0'])
        self.assertEqual(merged_claim['next_check_at'], '2026-01-01T00:00:00+00:00')
        self.assertEqual(merged_claim['family_id'], 'fam_btc_hyp')
        self.assertIsNone(merged_claim['outcome'])
        self.assertEqual(merged_claim['evidence_ids'], [])
        self.assertNotIn('acceptance', merged_claim)

    def _merge_single_claim(self, claim_fields):
        import audit_pipeline as pipeline
        self.sources([self.source('s1', text='[#cue-000001 10-15s]\nBitcoin might hit 120k.\n')])
        self.plan(budget=2000, max_items=10)
        task = self.task()
        claim = {
            'claim_id': 'clm_cite_1', 'text': 'Bitcoin hits 120k next year',
            'claim_type': 'factual', 'empirical': True, 'verifiability': 'verifiable',
            'occurrences': [{'source_id': 's1', 'original_quote': 'Bitcoin might hit 120k.',
                             'locator': {'kind': 'cue', 'unit_id': 'cue-000001', 'start': 10.0, 'end': 15.0}}],
            **claim_fields,
        }
        shard = {'task_id': task['task_id'], 'input_fingerprint': task['input_fingerprint'],
                 'complete': True, 'processed_source_ids': ['s1'], 'claims': [claim]}
        res_rel = f"work/results/{task['task_id']}.json"
        audit.write_json(self.run / res_rel, shard)
        audit.checkpoint(Namespace(run=str(self.run), task_id=task['task_id'], status='completed', result=res_rel, note=None))
        pipeline.merge_extraction(audit, self.run)
        return audit.read_jsonl(self.run / 'claims.jsonl')[0]

    def test_merge_extraction_preserves_citation_status_and_text(self):
        merged = self._merge_single_claim({'citation_status': 'secondary_cited', 'citation_text': '据某媒体报道'})
        self.assertEqual(merged['citation_status'], 'secondary_cited')
        self.assertEqual(merged['citation_text'], '据某媒体报道')

    def test_merge_extraction_keeps_legacy_claims_without_citation_tags(self):
        merged = self._merge_single_claim({})
        self.assertNotIn('citation_status', merged)
        self.assertNotIn('citation_text', merged)

    def test_merge_extraction_rejects_unknown_citation_status(self):
        with self.assertRaisesRegex(ValueError, 'invalid citation_status'):
            self._merge_single_claim({'citation_status': 'trust_me_bro'})

    def test_merge_extraction_carries_cited_source_tier_and_mocked_endorsement(self):
        merged = self._merge_single_claim({'cited_source_tier': 'unnamed_insider', 'endorsement': 'mocked'})
        self.assertEqual(merged['cited_source_tier'], 'unnamed_insider')
        self.assertEqual(merged['endorsement'], 'mocked')

    def test_merge_extraction_rejects_unknown_cited_source_tier(self):
        with self.assertRaisesRegex(ValueError, 'invalid cited_source_tier'):
            self._merge_single_claim({'cited_source_tier': 'tabloid'})

    def test_build_report_data_no_20_truncation_loads_rationale_quotes_and_hashes(self):
        import audit_pipeline as pipeline
        self.sources([self.source('s1', text='Source text')])
        audit.write_jsonl(self.run / 'evidence.jsonl', [
            {'evidence_id': 'ev1', 'title': 'Primary data', 'source_url': 'https://example.test/ev1',
             'published_at': '2025-01-02', 'excerpt': 'Observed value 4.1%.'},
        ])
        dec_rel = 'reviews/decisions/dec_late.json'
        audit.write_json(self.run / dec_rel, {
            'schema_version': 1,
            'consensus': {
                'decision': None,
                'votes': [{'reviewer_id': 'm1', 'rationale': 'Verified directly against primary data at index 23.'}],
            },
        })
        claims = []
        occs = []
        # Create 22 filler unscorable non-hypothetical claims first so resolved/notable claims sit past index 19.
        for i in range(22):
            cid, oid = f'clm_filler_{i:02d}', f'occ_filler_{i:02d}'
            claims.append({
                'schema_version': 1, 'claim_id': cid, 'subject_id': 'Example speaker',
                'occurrence_ids': [oid], 'text': f'General value judgment {i}', 'domain': 'general',
                'claim_type': 'value_judgment', 'empirical': False, 'endorsement': 'endorsed',
                'attribution_confidence': 'high', 'accountability_eligible': False,
                'quantifiability': 'none', 'verifiability': 'unverifiable',
                'lifecycle': 'unscorable', 'outcome': None, 'due_for_assessment': False,
                'evaluation_mode': 'none', 'probability': None, 'probability_origin': 'none',
                'event_occurred': None, 'criteria': None, 'evidence_ids': [],
                'evidence_quality': None, 'review_state': 'unreviewed',
            })
            occs.append({
                'schema_version': 1, 'occurrence_id': oid, 'claim_id': cid, 'source_id': 's1',
                'speaker': 'Example speaker', 'original_quote': f'Quote {i}',
                'context_before': '', 'context_after': '', 'locator': {'kind': 'cue', 'start': float(i * 10), 'end': float(i * 10 + 5)},
                'endorsement': 'endorsed', 'language': 'en',
            })
        # Index 22: resolved claim with decision rationale.
        claims.append({
            'schema_version': 1, 'claim_id': 'clm_resolved_late', 'subject_id': 'Example speaker',
            'occurrence_ids': ['occ_resolved_late'], 'text': 'Resolved late claim past index 20', 'domain': 'macro',
            'claim_type': 'prediction', 'empirical': True, 'endorsement': 'endorsed',
            'attribution_confidence': 'high', 'accountability_eligible': True,
            'quantifiability': 'numeric', 'verifiability': 'verifiable',
            'lifecycle': 'resolved', 'outcome': 'supported', 'due_for_assessment': True,
            'evaluation_mode': 'categorical', 'probability': None, 'probability_origin': 'none',
            'event_occurred': None, 'criteria': None, 'evidence_ids': ['ev1'],
            'evidence_quality': None, 'review_state': 'accepted',
            'acceptance': {'decision_path': dec_rel, 'decision_sha256': '0' * 64, 'policy_hash': 'p'},
        })
        occs.append({
            'schema_version': 1, 'occurrence_id': 'occ_resolved_late', 'claim_id': 'clm_resolved_late', 'source_id': 's1',
            'speaker': 'Example speaker', 'original_quote': 'Exact late quote from video.',
            'context_before': '', 'context_after': '',
            'locator': {'kind': 'cue', 'start': 73.08, 'end': 80.6, 'start_unit': 'cue-000031', 'end_unit': 'cue-000032'},
            'endorsement': 'endorsed', 'language': 'en',
        })
        # Index 23: pending trigger_unmet claim.
        claims.append({
            'schema_version': 1, 'claim_id': 'clm_pending_unmet', 'subject_id': 'Example speaker',
            'occurrence_ids': ['occ_pending_unmet'], 'text': 'Conditional claim with unmet trigger', 'domain': 'macro',
            'claim_type': 'prediction', 'empirical': True, 'endorsement': 'endorsed',
            'attribution_confidence': 'high', 'accountability_eligible': True,
            'quantifiability': 'operationalizable', 'verifiability': 'conditional',
            'lifecycle': 'pending', 'reason': 'trigger_unmet', 'outcome': None, 'due_for_assessment': False,
            'evaluation_mode': 'categorical', 'probability': None, 'probability_origin': 'none',
            'event_occurred': None, 'criteria': {'definition': {'condition': {'trigger': 'UNRATE == 4.3%'}}},
            'evidence_ids': ['ev1'], 'evidence_quality': None, 'review_state': 'unreviewed',
        })
        occs.append({
            'schema_version': 1, 'occurrence_id': 'occ_pending_unmet', 'claim_id': 'clm_pending_unmet', 'source_id': 's1',
            'speaker': 'Example speaker', 'original_quote': 'If unemployment is 4.3 percent we chop.',
            'context_before': '', 'context_after': '',
            'locator': {'kind': 'cue', 'start': 125.0, 'end': 132.0}, 'endorsement': 'endorsed', 'language': 'en',
        })
        # Index 24: unscorable hypothetical claim.
        claims.append({
            'schema_version': 1, 'claim_id': 'clm_hyp_late', 'subject_id': 'Example speaker',
            'occurrence_ids': ['occ_hyp_late'], 'text': 'Hypothetical 120k scenario', 'domain': 'crypto',
            'claim_type': 'hypothetical', 'empirical': False, 'endorsement': 'endorsed',
            'attribution_confidence': 'high', 'accountability_eligible': False,
            'quantifiability': 'numeric', 'verifiability': 'unverifiable',
            'lifecycle': 'unscorable', 'reason': 'hypothetical_scenario', 'outcome': None, 'due_for_assessment': False,
            'evaluation_mode': 'none', 'probability': None, 'probability_origin': 'none',
            'event_occurred': None, 'criteria': None, 'evidence_ids': [],
            'evidence_quality': None, 'review_state': 'unreviewed',
        })
        occs.append({
            'schema_version': 1, 'occurrence_id': 'occ_hyp_late', 'claim_id': 'clm_hyp_late', 'source_id': 's1',
            'speaker': 'Example speaker', 'original_quote': 'This is dubious speculation not the base case.',
            'context_before': '', 'context_after': '',
            'locator': {'kind': 'cue', 'start': 610.0, 'end': 620.0}, 'endorsement': 'endorsed', 'language': 'en',
        })
        audit.write_jsonl(self.run / 'claims.jsonl', claims)
        audit.write_jsonl(self.run / 'occurrences.jsonl', occs)
        audit.write_json(self.run / 'coverage.json', {
            'schema_version': 1, 'eligible_sources': 1, 'acquired_sources': 1,
            'extracted_sources': 1, 'inventory_complete': True, 'unresolved_review_issues': 0,
        })
        hashes = pipeline.report_hashes(audit, self.run)
        built = pipeline.build_report_data(audit, self.run)
        self.assertEqual(hashes['data_hash'], built['data_hash'])
        self.assertEqual(hashes['rubric_hash'], built['rubric_hash'])
        report_data = audit.read_json(self.run / 'reports/report-data.json')
        by_cid = {c['id']: c for c in report_data['cases']}
        # Dashboard ships every canonical claim (fillers included); only notable ones get narrative cards.
        self.assertEqual(len(by_cid), len(claims))
        self.assertTrue({'clm_resolved_late', 'clm_pending_unmet', 'clm_hyp_late'} <= set(by_cid))
        self.assertTrue(by_cid['clm_resolved_late']['notable'])
        self.assertFalse(by_cid['clm_filler_00']['notable'])
        self.assertEqual(by_cid['clm_resolved_late']['assessment'], 'Verified directly against primary data at index 23.')
        self.assertEqual(by_cid['clm_resolved_late']['original_quote'], 'Exact late quote from video.')
        self.assertIn('01:13–01:21', by_cid['clm_resolved_late']['timestamps'])
        self.assertEqual(by_cid['clm_pending_unmet']['status'], 'pending')
        self.assertIn('UNRATE == 4.3%', by_cid['clm_pending_unmet']['assessment'])
        self.assertEqual(by_cid['clm_hyp_late']['status'], 'not_checked')
        self.assertEqual(by_cid['clm_hyp_late']['evidence_ids'], ['s1'])
        self.assertEqual(by_cid['clm_resolved_late']['verdict'], 'supported')
        self.assertIn('citation_status', by_cid['clm_resolved_late'])
        self.assertIn('evidence_urls', by_cid['clm_resolved_late'])
        # No panel run yet: rubric attribution is null, difficulty attribution is still labelled subjective.
        self.assertIsNone(report_data['subjective_attribution']['rubric'])
        self.assertTrue(report_data['subjective_attribution']['difficulty']['subjective'])

    def test_same_day_as_of_clamped_to_wall_clock_time_across_timezones(self):
        from datetime import timezone, timedelta
        from zoneinfo import ZoneInfo
        import audit_pipeline as pipeline

        # Deterministic check at 04:00 UTC on 2026-11-26 (where 23:59:59 UTC would be +20h in the future).
        fixed_now = datetime(2026, 11, 26, 4, 0, 0, tzinfo=timezone.utc)
        utc_zone = ZoneInfo('UTC')
        la_zone = ZoneInfo('America/Los_Angeles')
        # Today in UTC (2026-11-26) clamps to 04:00 UTC rather than failing as future.
        clamped_utc = audit.resolve_as_of_time('2026-11-26', utc_zone, now_utc=fixed_now)
        self.assertEqual(clamped_utc, fixed_now)
        # Past date in UTC stays 23:59:59.999999.
        past_utc = audit.resolve_as_of_time('2026-11-25', utc_zone, now_utc=fixed_now)
        self.assertEqual(past_utc.hour, 23)
        self.assertEqual(past_utc.minute, 59)
        # Today in LA at 04:00 UTC is still 2026-11-25 20:00 PST -> clamps to fixed_now.
        clamped_la = audit.resolve_as_of_time('2026-11-25', la_zone, now_utc=fixed_now)
        self.assertEqual(clamped_la.astimezone(timezone.utc), fixed_now)
        # Tomorrow in UTC (2026-11-27) still fails without --allow-future-as-of.
        with self.assertRaisesRegex(ValueError, 'future'):
            audit.resolve_as_of_time('2026-11-27', utc_zone, now_utc=fixed_now)
        # End-to-end init with real wall-clock today in UTC and America/Los_Angeles succeeds.
        for tz_name in ('UTC', 'America/Los_Angeles', 'Asia/Singapore'):
            zone = ZoneInfo(tz_name)
            today_str = datetime.now(timezone.utc).astimezone(zone).date().isoformat()
            run_dir = self.run.parent / f'today_{tz_name.replace("/", "_")}'
            audit.init(Namespace(run=str(run_dir), subject='Today', start='2024-01-01',
                                 end=today_str, as_of=today_str, timezone=tz_name,
                                 cutoff_mode='retrospective'))
            cfg = audit.config(run_dir)
            saved_dt = datetime.fromisoformat(cfg['scope']['as_of'])
            self.assertLessEqual(saved_dt, datetime.now(timezone.utc) + timedelta(seconds=5))
            self.assertEqual(saved_dt.astimezone(zone).date().isoformat(), today_str)
            # assess with today date-only also succeeds without future failure.
            round_out = pipeline.new_assessment_round(audit, run_dir, today_str, reason='same_day_recheck')
            self.assertEqual(round_out['newly_due_claims'], 0)

    def test_temporal_guard_in_merge_freeze_criteria_and_validate(self):
        import audit_pipeline as pipeline
        self.sources([self.source('oct1', text='[#p-000001]\nYesterday Sept 30 closed above 500.\nNext year hits 700.\n',
                                  published_at='2025-10-01')])
        self.plan(budget=2000, max_items=10)
        task = self.task()
        shard = {
            'task_id': task['task_id'], 'input_fingerprint': task['input_fingerprint'],
            'complete': True, 'processed_source_ids': ['oct1'],
            'claims': [
                {'claim_id': 'c_retro', 'text': 'Event on Sept 30 happened', 'claim_type': 'prediction',
                 'empirical': True, 'verifiability': 'verifiable', 'target_date': '2025-09-30',
                 'occurrences': [{'source_id': 'oct1', 'original_quote': 'Yesterday Sept 30 closed above 500.',
                                  'locator': {'kind': 'paragraph', 'unit_id': 'p-000001', 'start': 1, 'end': 1}}]},
                {'claim_id': 'c_future', 'text': 'Next year hits 700', 'claim_type': 'prediction',
                 'empirical': True, 'verifiability': 'verifiable',
                 'occurrences': [{'source_id': 'oct1', 'original_quote': 'Next year hits 700.',
                                  'locator': {'kind': 'paragraph', 'unit_id': 'p-000001', 'start': 1, 'end': 1}}]},
            ],
        }
        res_rel = f"work/results/{task['task_id']}.json"
        audit.write_json(self.run / res_rel, shard)
        audit.checkpoint(Namespace(run=str(self.run), task_id=task['task_id'], status='completed', result=res_rel, note=None))
        merged = pipeline.merge_extraction(audit, self.run)
        self.assertEqual(merged['temporal_warnings'], 1)
        by_id = {c['claim_id']: c for c in audit.read_jsonl(self.run / 'claims.jsonl')}
        self.assertEqual(by_id['c_retro']['first_stated_at'], '2025-10-01')
        self.assertEqual(by_id['c_retro']['review_state'], 'needs_review')
        self.assertIn('temporal_guard_warning', by_id['c_retro'])
        # Unfrozen retroactive prediction triggers a warning in validate.
        val = audit.validate(self.run)
        self.assertTrue(any('Temporal guard warning' in w for w in val['warnings']))
        # Freezing retroactive criteria on a prediction is rejected.
        bad_def = self.run / 'bad_def.json'
        audit.write_json(bad_def, {'target': 'Sept 30 close', 'predicate': '>500', 'window_start': '2025-09-01',
                                   'window_end': '2025-09-30', 'timezone': 'UTC', 'condition': 'unconditional',
                                   'resolution_basis': 'explicit'})
        with self.assertRaisesRegex(ValueError, 'temporal guard'):
            pipeline.freeze_criteria(audit, self.run, 'c_retro', bad_def)
        # Freezing valid future criteria with difficulty metadata succeeds and reports lead_time_days.
        ok_def = self.run / 'ok_def.json'
        audit.write_json(ok_def, {'target': 'Index', 'predicate': '>=700', 'window_start': '2025-10-02',
                                  'window_end': '2026-01-29', 'timezone': 'UTC', 'condition': 'unconditional',
                                  'resolution_basis': 'explicit'})
        frozen = pipeline.freeze_criteria(audit, self.run, 'c_future', ok_def,
                                          difficulty='hard', difficulty_score=4,
                                          difficulty_rationale='Above consensus price target.',
                                          difficulty_model_id='model-a')
        self.assertEqual(frozen['lead_time_days'], 120.0)
        updated = {c['claim_id']: c for c in audit.read_jsonl(self.run / 'claims.jsonl')}
        self.assertEqual(updated['c_future']['difficulty'], 'hard')
        self.assertEqual(updated['c_future']['difficulty_score'], 4)
        # Subjective difficulty rating is attributed to the model that assigned it.
        self.assertEqual(updated['c_future']['difficulty_model_id'], 'model-a')
        with self.assertRaises(ValueError):
            pipeline.freeze_criteria(audit, self.run, 'c_future', ok_def, difficulty_model_id='   ')
        # Hand-tampered frozen retroactive prediction fails audit.validate hard.
        updated['c_retro']['criteria'] = {'definition': {'target': 't', 'predicate': 'p', 'window_start': '2025-09-01',
                                                         'window_end': '2025-09-30', 'timezone': 'UTC',
                                                         'condition': 'unconditional', 'resolution_basis': 'explicit'},
                                          'version': '1', 'frozen_at': '2025-10-02T00:00:00Z', 'sha256': '0'*64}
        audit.write_jsonl(self.run / 'claims.jsonl', list(updated.values()))
        with self.assertRaisesRegex(ValueError, 'temporal guard'):
            audit.validate(self.run)

    def test_build_report_data_subject_id_filter_and_case_card_metadata(self):
        import audit_pipeline as pipeline
        self.sources([self.source('s1', text='Source text', published_at='2025-01-01')])
        audit.write_jsonl(self.run / 'evidence.jsonl', [
            {'evidence_id': 'ev1', 'title': 'Ev1', 'source_url': 'https://example.test/ev1',
             'published_at': '2025-06-01', 'excerpt': 'Observed.'},
        ])
        claims = [
            {
                'schema_version': 1, 'claim_id': 'c_alice', 'subject_id': 'Alice',
                'occurrence_ids': ['o_alice'], 'text': 'Alice predicts X by May 1', 'domain': 'macro',
                'claim_type': 'prediction', 'empirical': True, 'endorsement': 'endorsed',
                'attribution_confidence': 'high', 'accountability_eligible': True,
                'quantifiability': 'numeric', 'verifiability': 'verifiable',
                'lifecycle': 'resolved', 'outcome': 'supported', 'due_for_assessment': True,
                'evaluation_mode': 'categorical', 'probability': None, 'probability_origin': 'none',
                'event_occurred': None, 'first_stated_at': '2025-01-01',
                'difficulty': 'hard', 'difficulty_score': 4, 'difficulty_rationale': 'Non-consensus call.',
                'criteria': {'definition': {'target': 'X', 'predicate': 'occurred', 'window_start': '2025-01-02',
                                            'window_end': '2025-05-01', 'timezone': 'UTC', 'condition': 'unconditional',
                                            'resolution_basis': 'explicit'}, 'version': '1',
                             'frozen_at': '2025-01-02T00:00:00Z', 'sha256': '0'*64},
                'evidence_ids': ['ev1'], 'evidence_quality': None, 'review_state': 'accepted',
            },
            {
                'schema_version': 1, 'claim_id': 'c_bob', 'subject_id': 'Bob',
                'occurrence_ids': ['o_bob'], 'text': 'Bob predicts Y', 'domain': 'macro',
                'claim_type': 'prediction', 'empirical': True, 'endorsement': 'quoted',
                'attribution_confidence': 'high', 'accountability_eligible': True,
                'quantifiability': 'numeric', 'verifiability': 'verifiable',
                'lifecycle': 'resolved', 'outcome': 'contradicted', 'due_for_assessment': True,
                'evaluation_mode': 'categorical', 'probability': None, 'probability_origin': 'none',
                'event_occurred': None, 'criteria': None,
                'evidence_ids': ['ev1'], 'evidence_quality': None, 'review_state': 'accepted',
            },
        ]
        occs = [
            {'schema_version': 1, 'occurrence_id': 'o_alice', 'claim_id': 'c_alice', 'source_id': 's1',
             'speaker': 'Alice Host', 'original_quote': 'X will happen by May 1.',
             'context_before': '', 'context_after': '', 'locator': {'kind': 'cue', 'start': 10.0, 'end': 15.0},
             'endorsement': 'endorsed', 'language': 'en'},
            {'schema_version': 1, 'occurrence_id': 'o_bob', 'claim_id': 'c_bob', 'source_id': 's1',
             'speaker': 'Bob Guest', 'original_quote': 'Y will happen.',
             'context_before': '', 'context_after': '', 'locator': {'kind': 'cue', 'start': 20.0, 'end': 25.0},
             'endorsement': 'quoted', 'language': 'en'},
        ]
        audit.write_jsonl(self.run / 'claims.jsonl', claims)
        audit.write_jsonl(self.run / 'occurrences.jsonl', occs)
        audit.write_json(self.run / 'coverage.json', {
            'schema_version': 1, 'eligible_sources': 1, 'acquired_sources': 1,
            'extracted_sources': 1, 'inventory_complete': True, 'unresolved_review_issues': 0,
        })
        hashes = pipeline.report_hashes(audit, self.run, subject_id='Alice')
        built = pipeline.build_report_data(audit, self.run, subject_id='Alice')
        self.assertEqual(hashes['data_hash'], built['data_hash'])
        self.assertEqual(hashes['claims_count'], 1)
        data = audit.read_json(self.run / 'reports/report-data.json')
        self.assertEqual(data['report']['subject'], 'Alice')
        self.assertEqual([c['id'] for c in data['cases']], ['c_alice'])
        card = data['cases'][0]
        self.assertEqual(card['subject_id'], 'Alice')
        self.assertEqual(card['speaker'], 'Alice Host')
        self.assertEqual(card['endorsement'], 'endorsed')
        self.assertEqual(card['difficulty'], 'hard')
        self.assertEqual(card['difficulty_score'], 4)
        self.assertEqual(card['difficulty_rationale'], 'Non-consensus call.')
        self.assertEqual(card['lead_time_days'], 120.0)
        self.assertEqual(card['occurrences'][0]['speaker'], 'Alice Host')
        with self.assertRaisesRegex(ValueError, 'No claims found'):
            pipeline.build_report_data(audit, self.run, subject_id='NonExistent')

    def _write_manifest(self, inp, filename):
        m = inp / 'manifest.jsonl'
        audit.write_jsonl(m, [{'source_id': 's1', 'title': 'Long', 'source_url': None,
                               'published_at': '2024-06-01', 'path': filename}])
        return m


if __name__ == '__main__':
    unittest.main()
