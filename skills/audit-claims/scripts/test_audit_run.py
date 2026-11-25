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


if __name__ == '__main__':
    unittest.main()
