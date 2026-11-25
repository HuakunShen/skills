#!/usr/bin/env python3
"""Offline integration tests for adopting only evidence-bound accepted decisions."""
from argparse import Namespace
import copy
import csv
from contextlib import redirect_stdout
import io
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import adopt_verdict as bridge
import audit_run as audit
import model_panel as panel
import score_claims as scoring
from test_score_claims import claim, occurrence, COVERAGE


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        audit.init(Namespace(run=str(self.run), subject='speaker', start='2021-01-01', end='2026-01-01',
                             as_of='2026-01-01T23:59:59+00:00', timezone='UTC', cutoff_mode='retrospective'))
        self.claim = claim(lifecycle='ready', outcome=None, resolved_at=None, evidence_ids=[], review_state='unreviewed')
        audit.write_jsonl(self.run / 'claims.jsonl', [self.claim])
        audit.write_jsonl(self.run / 'occurrences.jsonl', [occurrence('o_c1', 'c1')])
        audit.atomic_text(self.run / 'sources/source.md', 'Original quote.\n')
        audit.write_jsonl(self.run / 'sources.jsonl', [{'source_id': 'source', 'source_url': 'https://example.org/talk',
            'published_at': '2025-01-01', 'status': 'ready', 'content_path': 'sources/source.md',
            'content_hash': bridge.file_sha(self.run / 'sources/source.md')}])
        panel.init(self.run)
        self.policy = panel.read_json(self.run / 'config/model-policy.json')
        self.policy.update(status='confirmed', selected_models=[{'id': m, 'provider': 'fixture', 'api_model': m,
            'availability': 'available', 'cost': {'mode': 'included', 'estimate_usd': 0}} for m in ['a', 'b']])
        self.policy['roles'] = {'lookup': ['a'], 'extract': ['a'], 'verify': ['a', 'b'], 'report': ['a', 'b'], 'judge': []}
        self.policy['verification'] = {'mode': 'unanimous', 'required_reviewers': ['a', 'b'], 'judge_model_id': None}
        self.policy['report'] = {'reviewers': ['a', 'b'], 'judge_model_id': None}
        panel.write_json(self.run / 'config/model-policy.json', self.policy)
        panel.freeze(self.run)
        self.policy = panel.load_policy(self.run / 'config/model-policy.json')
        self.evidence = [{'evidence_id': 'e-' + m, 'claim_ids': ['c1'], 'source_url': 'https://example.org/evidence-' + m,
                         'retrieved_at': '2026-01-02T10:00:00Z', 'available_at': '2025-12-31T20:00:00Z',
                         'observation_end': '2025-12-31T20:00:00Z', 'excerpt': 'The event occurred.'} for m in ['a', 'b']]
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
        self.consensus_path = self.run / 'consensus.json'
        self.refresh_votes()

    def refresh_votes(self, normalized=None):
        fp = bridge.verification_fingerprint(self.run, self.claim)
        self.votes = [{'vote_id': 'v-' + m, 'reviewer_id': m, 'claim_id': 'c1', 'criteria_hash': self.claim['criteria']['sha256'],
                       'input_hash': fp, 'as_of': audit.config(self.run)['scope']['as_of'], 'verdict': 'supported',
                       'normalized_result': normalized or {'outcome': 'supported'}, 'evidence_ids': ['e-' + m],
                       'rationale': 'Fixture observation', 'independent': True} for m in ['a', 'b']]
        self.saved = panel.consensus(self.policy, self.votes)
        audit.write_json(self.consensus_path, self.saved)

    def adopted(self):
        return audit.read_jsonl(self.run / 'claims.jsonl')[0]

    def adopt(self):
        return bridge.adopt(self.run, 'c1', self.consensus_path)

    def assert_rejected_without_claim_write(self):
        before = (self.run / 'claims.jsonl').read_bytes()
        with self.assertRaises(ValueError):
            self.adopt()
        self.assertEqual((self.run / 'claims.jsonl').read_bytes(), before)

    def test_adoption_verifies_then_scores_and_preserves_history(self):
        result = self.adopt()
        c = self.adopted()
        self.assertTrue(result['adopted'])
        self.assertEqual(c['evidence_ids'], ['e-a', 'e-b'])
        self.assertEqual(c['outcome'], 'supported')
        self.assertTrue(bridge.verify_acceptance(self.run, c)['accepted'])
        self.assertEqual(scoring.calculate([c], copy.deepcopy(COVERAGE))['categorical_n'], 1)
        self.assertEqual(len(list((self.run / 'history/claims').glob('*.json'))), 1)

    def test_fake_accepted_flag_cannot_override_disagreement(self):
        self.saved['votes'][1]['verdict'] = 'contradicted'
        self.saved['accepted'] = True
        audit.write_json(self.consensus_path, self.saved)
        self.assert_rejected_without_claim_write()

    def test_changed_criteria_rejected(self):
        self.claim['criteria']['definition']['predicate'] = 'Altered after seeing the result'
        self.claim['criteria']['sha256'] = bridge.hashed(self.claim['criteria']['definition'])
        audit.write_jsonl(self.run / 'claims.jsonl', [self.claim])
        self.assert_rejected_without_claim_write()

    def test_missing_evidence_rejected(self):
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence[:1])
        self.assert_rejected_without_claim_write()

    def test_probability_maps_observation_not_categorical_accuracy(self):
        self.claim.update(evaluation_mode='probabilistic', probability=.7, probability_origin='explicit')
        audit.write_jsonl(self.run / 'claims.jsonl', [self.claim])
        self.refresh_votes({'event_occurred': False})
        self.adopt()
        c = self.adopted()
        self.assertIsNone(c['outcome'])
        self.assertEqual(c['probability'], .7)
        self.assertIs(c['event_occurred'], False)
        bridge.verify_acceptance(self.run, c)
        metrics = scoring.calculate([c], copy.deepcopy(COVERAGE))
        self.assertEqual(metrics['categorical_n'], 0)
        self.assertAlmostEqual(metrics['brier']['value'], .49)

    def test_repeated_adoption_is_idempotent(self):
        self.adopt()
        before = (self.run / 'claims.jsonl').read_bytes()
        events = (self.run / 'events.jsonl').read_bytes()
        self.assertTrue(self.adopt()['idempotent'])
        self.assertEqual((self.run / 'claims.jsonl').read_bytes(), before)
        self.assertEqual((self.run / 'events.jsonl').read_bytes(), events)

    def test_pending_and_missing_quality_rejected(self):
        for update in ({'lifecycle': 'pending', 'due_for_assessment': False}, {'evidence_quality': None}):
            candidate = {**self.claim, **update}
            audit.write_jsonl(self.run / 'claims.jsonl', [candidate])
            self.assert_rejected_without_claim_write()

    def test_original_source_or_occurrence_change_invalidates_acceptance(self):
        self.adopt()
        audit.atomic_text(self.run / 'sources/source.md', 'Changed attribution.\n')
        with self.assertRaisesRegex(ValueError, 'source content hash'):
            bridge.verify_acceptance(self.run, self.adopted())

    def test_evidence_change_after_adoption_invalidates_scoring(self):
        self.adopt()
        self.evidence[0]['excerpt'] = 'Completely changed evidence'
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
        with self.assertRaisesRegex(ValueError, 'evidence records'):
            bridge.verify_acceptance(self.run, self.adopted())

    def test_local_evidence_supported_and_content_bound(self):
        path = self.run / 'local-evidence.txt'
        path.write_text('Observed data', encoding='utf-8')
        self.evidence[0].pop('source_url')
        self.evidence[0]['local_path'] = 'local-evidence.txt'
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
        self.adopt()
        bridge.verify_acceptance(self.run, self.adopted())
        path.write_text('Changed data', encoding='utf-8')
        with self.assertRaises(ValueError):
            bridge.verify_acceptance(self.run, self.adopted())

    def test_future_observation_rejected(self):
        self.evidence[0]['observation_end'] = '2026-01-03T00:00:00Z'
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
        self.assert_rejected_without_claim_write()

    def test_knowledge_cutoff_requires_known_available_evidence(self):
        cfg = audit.config(self.run)
        cfg['cutoff_mode'] = 'knowledge_as_of'
        cfg['config_hash'] = audit.digest(audit.config_body(cfg))
        audit.write_json(self.run / 'run.json', cfg)
        self.refresh_votes()
        for available in (None, '2026-01-03T00:00:00Z'):
            self.evidence[0]['available_at'] = available
            audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
            self.assert_rejected_without_claim_write()

    def test_conflicting_second_adoption_requires_new_version(self):
        self.adopt()
        for vote in self.votes:
            vote.update(verdict='contradicted', normalized_result={'outcome': 'contradicted'})
        audit.write_json(self.consensus_path, panel.consensus(self.policy, self.votes))
        self.assert_rejected_without_claim_write()

    def test_scoped_snapshot_reads_shared_files_and_indexes_once(self):
        evidence_path = self.run / 'shared-evidence.txt'
        evidence_path.write_text('Observed event data', encoding='utf-8')
        for evidence in self.evidence:
            evidence['local_path'] = 'shared-evidence.txt'
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
        self.adopt()
        c = self.adopted()
        reads = {}
        original_read = Path.read_bytes
        def counted(path):
            reads[path.resolve()] = reads.get(path.resolve(), 0) + 1
            return original_read(path)
        with audit.coordinator_lock(self.run):
            snapshot = bridge.VerificationSnapshot(self.run)
            with mock.patch.object(Path, 'read_bytes', new=counted), mock.patch.object(audit, 'read_jsonl', wraps=audit.read_jsonl) as ledger_reads:
                bridge.verify_acceptance(self.run, c, snapshot=snapshot)
                bridge.verify_acceptance(self.run, c, snapshot=snapshot)
            self.assertEqual(reads[evidence_path.resolve()], 1)
            self.assertEqual(reads[(self.run / 'sources/source.md').resolve()], 1)
            read_names = [call.args[0].name for call in ledger_reads.call_args_list]
            for name in ('occurrences.jsonl', 'sources.jsonl', 'evidence.jsonl'):
                self.assertEqual(read_names.count(name), 1)
        # The prior snapshot is deliberately discarded after leaving the pass.
        evidence_path.write_text('Mutated event data', encoding='utf-8')
        with audit.coordinator_lock(self.run):
            with self.assertRaisesRegex(ValueError, 'evidence records'):
                bridge.verify_acceptance(self.run, c, snapshot=bridge.VerificationSnapshot(self.run))
            with self.assertRaisesRegex(ValueError, 'evidence records'):
                bridge.verify_acceptance(self.run, c)

    def test_snapshot_cannot_be_reused_for_another_run(self):
        snapshot = bridge.VerificationSnapshot(self.run / 'different-run')
        with self.assertRaisesRegex(ValueError, 'different run'):
            bridge.verification_fingerprint(self.run, self.claim, snapshot=snapshot)

    def test_policy_changed_after_adoption_rejected(self):
        self.adopt()
        self.policy['roles']['extract'] = ['b']
        self.policy['policy_hash'] = panel.policy_hash(self.policy)
        panel.write_json(self.run / 'config/model-policy.json', self.policy)
        with self.assertRaisesRegex(ValueError, 'immutable lock'):
            bridge.verify_acceptance(self.run, self.adopted())


    def score_args(self, *, subject_id=None, csv_export=False):
        coverage = {**COVERAGE, 'eligible_sources': 1, 'acquired_sources': 1, 'extracted_sources': 1}
        audit.write_json(self.run / 'coverage.json', coverage)
        return Namespace(run=str(self.run), claims=str(self.run / 'claims.jsonl'),
                         coverage=str(self.run / 'coverage.json'), occurrences=str(self.run / 'occurrences.jsonl'),
                         out=str(self.run / 'reports/metrics.json'),
                         csv=str(self.run / 'reports/claims.csv') if csv_export else None,
                         composite=False, scoring_policy=None, model_policy=None, subject_id=subject_id)

    def test_score_cli_verifies_adoption_before_writing_metrics(self):
        self.adopt()
        args = self.score_args()
        with redirect_stdout(io.StringIO()) as output:
            scoring.main(['--run', args.run, '--claims', args.claims, '--coverage', args.coverage,
                          '--occurrences', args.occurrences, '--out', args.out])
        metrics = audit.read_json(Path(args.out))
        self.assertEqual(metrics['acceptance_verification']['verified_resolutions'], 1)
        self.assertEqual(metrics['categorical_n'], 1)
        self.assertEqual(metrics['strict_support_rate']['value'], 1)
        self.assertFalse(metrics['acceptance_verification']['semantic_evidence_truth_verified_by_script'])
        self.assertIn('metrics_path', output.getvalue())

    def test_score_run_rejects_forged_accepted_claim_without_acceptance(self):
        forged = {**self.claim, 'lifecycle': 'resolved', 'outcome': 'supported',
                  'review_state': 'accepted', 'resolved_at': '2026-01-02T12:00:00Z',
                  'evidence_ids': ['e-a'], 'acceptance': None}
        audit.write_jsonl(self.run / 'claims.jsonl', [forged])
        args = self.score_args()
        with self.assertRaisesRegex(ValueError, 'adopted panel acceptance'):
            scoring.score_run(args)
        self.assertFalse(Path(args.out).exists())

    def test_score_run_rejects_later_evidence_or_source_changes_without_report_overwrite(self):
        self.adopt()
        args = self.score_args(csv_export=True)
        scoring.score_run(args)
        reports = {Path(args.out): Path(args.out).read_bytes(), Path(args.csv): Path(args.csv).read_bytes()}
        evidence_path, source_path = self.run / 'evidence.jsonl', self.run / 'sources/source.md'
        original_evidence, original_source = evidence_path.read_bytes(), source_path.read_bytes()
        for mutation in ('evidence', 'source'):
            with self.subTest(mutation=mutation):
                evidence_path.write_bytes(original_evidence)
                source_path.write_bytes(original_source)
                if mutation == 'evidence':
                    changed = copy.deepcopy(self.evidence)
                    changed[0]['excerpt'] = 'A different observation after adoption'
                    audit.write_jsonl(evidence_path, changed)
                else:
                    source_path.write_text('Changed source text after adoption', encoding='utf-8')
                with self.assertRaises(ValueError):
                    scoring.score_run(args)
                for path, prior in reports.items():
                    self.assertEqual(path.read_bytes(), prior)

    def test_score_run_subject_filter_exports_only_selected_subject(self):
        self.adopt()
        guest = claim('guest', subject_id='guest', lifecycle='ready', outcome=None,
                      resolved_at=None, evidence_ids=[], review_state='unreviewed')
        audit.write_jsonl(self.run / 'claims.jsonl', [self.adopted(), guest])
        audit.write_jsonl(self.run / 'occurrences.jsonl', [occurrence('o_c1', 'c1'),
                          occurrence('o_guest', 'guest', speaker='guest')])
        args = self.score_args(subject_id='speaker', csv_export=True)
        metrics = scoring.score_run(args)
        with Path(args.csv).open(encoding='utf-8', newline='') as stream:
            exported = list(csv.DictReader(stream))
        self.assertEqual([row['claim_id'] for row in exported], ['c1'])
        self.assertEqual(metrics['subject_id'], 'speaker')
        self.assertEqual(metrics['total_canonical_claims'], 1)
        self.assertEqual(metrics['acceptance_verification']['verified_resolutions'], 1)

    def test_cross_timezone_deadline_uses_criteria_timezone(self):
        # Run in Asia/Singapore at 2025-12-31T20:00:00Z (2026-01-01 04:00 SGT, still 2025-12-31 15:00 NYT).
        run2 = self.run.parent / 'tz_run'
        audit.init(Namespace(run=str(run2), subject='speaker', start='2025-01-01', end='2025-12-31',
                             as_of='2025-12-31T20:00:00Z', timezone='Asia/Singapore', cutoff_mode='retrospective'))
        defn = {'target': 'US close', 'predicate': 'Closed higher', 'window_start': '2025-01-01',
                'window_end': '2025-12-31', 'timezone': 'America/New_York', 'condition': 'unconditional', 'resolution_basis': 'explicit'}
        c = claim(lifecycle='ready', outcome=None, resolved_at=None, evidence_ids=[], review_state='unreviewed',
                  criteria={'definition': defn, 'version': '1', 'frozen_at': '2025-01-01T00:00:00Z',
                            'sha256': bridge.hashed(defn)})
        audit.write_jsonl(run2 / 'claims.jsonl', [c])
        audit.write_jsonl(run2 / 'occurrences.jsonl', [occurrence('o_c1', 'c1')])
        audit.atomic_text(run2 / 'sources/source.md', 'Original quote.\n')
        audit.write_jsonl(run2 / 'sources.jsonl', [{'source_id': 'source', 'source_url': 'https://example.org/talk',
            'published_at': '2025-01-01', 'status': 'ready', 'content_path': 'sources/source.md',
            'content_hash': bridge.file_sha(run2 / 'sources/source.md')}])
        panel.init(run2)
        pol = panel.read_json(run2 / 'config/model-policy.json')
        pol.update(status='confirmed', selected_models=[{'id': 'a', 'provider': 'fixture', 'api_model': 'a',
                   'availability': 'available', 'cost': {'mode': 'included', 'estimate_usd': 0}}])
        pol['roles'] = {'lookup': ['a'], 'extract': ['a'], 'verify': ['a'], 'report': ['a'], 'judge': []}
        pol['verification'] = {'mode': 'single', 'required_reviewers': ['a'], 'judge_model_id': None}
        pol['report'] = {'reviewers': ['a'], 'judge_model_id': None}
        panel.write_json(run2 / 'config/model-policy.json', pol)
        panel.freeze(run2)
        pol = panel.load_policy(run2 / 'config/model-policy.json')
        audit.write_jsonl(run2 / 'evidence.jsonl', [{
            'evidence_id': 'e-a', 'claim_ids': ['c1'], 'source_url': 'https://example.org/e',
            'retrieved_at': '2025-12-31T20:00:00Z', 'available_at': '2025-12-31T19:00:00Z',
            'excerpt': 'Closed higher.', 'relation': 'supports', 'source_family': 'nyse'}])
        fp = bridge.verification_fingerprint(run2, c)
        cons = panel.consensus(pol, [{'vote_id': 'v1', 'reviewer_id': 'a', 'claim_id': 'c1',
                                      'criteria_hash': c['criteria']['sha256'], 'input_hash': fp,
                                      'as_of': audit.config(run2)['scope']['as_of'], 'verdict': 'supported',
                                      'normalized_result': {'outcome': 'supported'}, 'evidence_ids': ['e-a'],
                                      'rationale': 'ok', 'independent': True}])
        audit.write_json(run2 / 'cons.json', cons)
        with self.assertRaisesRegex(ValueError, 'deadline has not arrived'):
            bridge.adopt(run2, 'c1', run2 / 'cons.json')

    def test_judge_adoption_ignores_overruled_vote_post_cutoff_evidence_and_reopen(self):
        cfg = audit.config(self.run)
        cfg['cutoff_mode'] = 'knowledge_as_of'
        cfg['config_hash'] = audit.digest(audit.config_body(cfg))
        audit.write_json(self.run / 'run.json', cfg)
        pol = copy.deepcopy(self.policy)
        pol['selected_models'].append({'id': 'j', 'provider': 'fixture', 'api_model': 'j',
                                       'availability': 'available', 'cost': {'mode': 'included', 'estimate_usd': 0}})
        pol['roles']['judge'] = ['j']
        pol['verification'] = {'mode': 'judge', 'required_reviewers': ['a', 'b'], 'judge_model_id': 'j'}
        pol.pop('policy_hash', None)
        (self.run / 'config/model-policy.lock.json').unlink()
        panel.write_json(self.run / 'config/model-policy.json', pol)
        panel.freeze(self.run)
        pol = panel.load_policy(self.run / 'config/model-policy.json')
        ev_bad = {'evidence_id': 'e-a', 'claim_ids': ['c1'], 'source_url': 'https://example.org/bad',
                  'retrieved_at': '2026-01-02T10:00:00Z', 'available_at': '2026-01-05T00:00:00Z',
                  'excerpt': 'Post-cutoff', 'relation': 'contradicts', 'source_family': 'late'}
        ev_good = {'evidence_id': 'e-b', 'claim_ids': ['c1'], 'source_url': 'https://example.org/good',
                   'retrieved_at': '2026-01-02T10:00:00Z', 'available_at': '2025-12-31T20:00:00Z',
                   'excerpt': 'In-cutoff support', 'relation': 'supports', 'source_family': 'primary'}
        audit.write_jsonl(self.run / 'evidence.jsonl', [ev_bad, ev_good])
        fp = bridge.verification_fingerprint(self.run, self.claim)
        votes = [
            {'vote_id': 'v-a', 'reviewer_id': 'a', 'claim_id': 'c1', 'criteria_hash': self.claim['criteria']['sha256'],
             'input_hash': fp, 'as_of': cfg['scope']['as_of'], 'verdict': 'contradicted',
             'normalized_result': {'outcome': 'contradicted'}, 'evidence_ids': ['e-a'],
             'rationale': 'Used late source', 'independent': True},
            {'vote_id': 'v-b', 'reviewer_id': 'b', 'claim_id': 'c1', 'criteria_hash': self.claim['criteria']['sha256'],
             'input_hash': fp, 'as_of': cfg['scope']['as_of'], 'verdict': 'supported',
             'normalized_result': {'outcome': 'supported'}, 'evidence_ids': ['e-b'],
             'rationale': 'Valid source', 'independent': True},
        ]
        dec = {'decision_id': 'd-1', 'actor_type': 'model', 'actor_id': 'j', 'claim_id': 'c1',
               'criteria_hash': self.claim['criteria']['sha256'], 'input_hash': fp, 'as_of': cfg['scope']['as_of'],
               'verdict': 'supported', 'normalized_result': {'outcome': 'supported'}, 'evidence_ids': ['e-b'],
               'rationale': 'Overruled vote A post-cutoff evidence', 'considered_vote_ids': ['v-a', 'v-b']}
        cons = panel.consensus(pol, votes, dec)
        audit.write_json(self.consensus_path, cons)
        res = self.adopt()
        self.assertTrue(res['adopted'])
        self.assertEqual(self.adopted()['evidence_ids'], ['e-b'])
        reopened = bridge.reopen(self.run, 'c1', 'new_evidence', 'reviewer_human', 'Test reopen')
        self.assertTrue(reopened['reopened'])
        self.assertIsNone(self.adopted()['acceptance'])

    def test_relation_mismatch_and_undated_contradicted_rejected(self):
        self.evidence[0]['relation'] = 'contradicts'
        self.evidence[1]['relation'] = 'contradicts'
        audit.write_jsonl(self.run / 'evidence.jsonl', self.evidence)
        self.assert_rejected_without_claim_write()
        # Undated prediction cannot be adopted as contradicted.
        self.claim['criteria']['definition']['window_end'] = None
        self.claim['criteria']['sha256'] = bridge.hashed(self.claim['criteria']['definition'])
        audit.write_jsonl(self.run / 'claims.jsonl', [self.claim])
        for v in self.votes:
            v.update(verdict='contradicted', normalized_result={'outcome': 'contradicted'},
                     input_hash=bridge.verification_fingerprint(self.run, self.claim))
        audit.write_json(self.consensus_path, panel.consensus(self.policy, self.votes))
        with self.assertRaisesRegex(ValueError, 'Undated predictions'):
            self.adopt()


if __name__ == '__main__':
    unittest.main()
