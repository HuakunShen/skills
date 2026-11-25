#!/usr/bin/env python3
"""Offline checks: explicit choices, fixed panel denominators and no majority fallback."""
import copy
from pathlib import Path
import tempfile
import unittest

import model_panel as panel


class ModelPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.path = self.run / 'config/model-policy.json'
        panel.init(self.run)
        self.policy = panel.read_json(self.path)
        self.policy.update(status='confirmed', selected_models=[
            {'id': m, 'provider': 'fixture', 'api_model': 'model-' + m, 'availability': 'available',
             'cost': {'mode': 'included', 'estimate_usd': 0, 'pricing_checked_at': None}}
            for m in ['a', 'b', 'c']])
        self.policy['roles'] = {'lookup': ['a'], 'extract': ['b'], 'verify': ['a', 'b'], 'report': ['a', 'b', 'c'], 'judge': ['c']}
        self.policy['verification'] = {'mode': 'unanimous', 'required_reviewers': ['a', 'b'], 'judge_model_id': 'c'}
        self.policy['report'] = {'reviewers': ['a', 'b', 'c'], 'judge_model_id': None}
        self.seal()

    def seal(self):
        self.policy.pop('policy_hash', None)
        self.policy['policy_hash'] = panel.policy_hash(self.policy)
        panel.write_json(self.path, self.policy)

    def review(self, model, score=60, **changes):
        return {'review_id': 'r-' + model, 'model_id': model, 'model_version': 'fixture',
                'data_hash': 'frozen-data', 'rubric_hash': 'frozen-rubric', 'score_scale': {'min': 0, 'max': 100},
                'scores': {'clarity': score}, 'status': 'completed', 'independent': True, **changes}

    def vote(self, model, verdict='supported', **changes):
        return {'vote_id': 'v-' + model, 'reviewer_id': model, 'claim_id': 'claim-1', 'criteria_hash': 'criteria-1',
                'input_hash': 'input-1', 'as_of': '2026-11-25T12:00:00+08:00', 'verdict': verdict,
                'normalized_result': {'event_occurred': True}, 'evidence_ids': ['e-' + model],
                'rationale': 'Fixture evidence assessment', 'independent': True, **changes}

    def decision(self):
        return {'decision_id': 'decision-1', 'actor_type': 'model', 'actor_id': 'c', 'claim_id': 'claim-1',
                'criteria_hash': 'criteria-1', 'input_hash': 'input-1', 'as_of': '2026-11-25T12:00:00+08:00',
                'verdict': 'supported', 'normalized_result': {'event_occurred': True}, 'evidence_ids': ['e-judge'],
                'rationale': 'Reviewed both rationales', 'considered_vote_ids': ['v-a', 'v-b']}

    def test_init_preserves_existing_selection(self):
        before = self.path.read_bytes()
        result = panel.init(self.run)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(result['calls_authorized'])
        self.assertEqual(len(result['preserved']), 2)

    def test_draft_does_not_authorize_models(self):
        self.policy.update(status='draft', selected_models=[])
        with self.assertRaisesRegex(ValueError, 'draft'):
            panel.validate_policy(self.policy)

    def test_freeze_is_idempotent_and_detects_change(self):
        panel.freeze(self.run)
        panel.freeze(self.run)
        self.policy['roles']['lookup'] = ['b']
        self.seal()
        with self.assertRaisesRegex(ValueError, 'immutable lock'):
            panel.validate_run(self.run)

    def test_unavailable_requested_model_rejected(self):
        self.policy['selected_models'][0]['availability'] = 'unverified'
        with self.assertRaisesRegex(ValueError, 'availability'):
            panel.validate_policy(self.policy)

    def test_aliases_cannot_inflate_model_count(self):
        self.policy['selected_models'][1]['api_model'] = 'model-a'
        with self.assertRaisesRegex(ValueError, 'masquerade'):
            panel.validate_policy(self.policy)

    def test_model_cap_enforced(self):
        self.policy['max_models'] = 2
        with self.assertRaisesRegex(ValueError, 'max_models'):
            panel.validate_policy(self.policy)

    def test_known_sample_statistics_and_raw_scores(self):
        reviews = [self.review('a', 50), self.review('b', 60), self.review('c', 70)]
        result = panel.summarize(self.policy, reviews)
        metric = result['metrics']['clarity']
        self.assertEqual(metric, {'n': 3, 'planned_n': 3, 'mean': 60, 'median': 60, 'min': 50, 'max': 70,
                                  'range': 20, 'sample_variance': 100, 'sd': 10.0})
        self.assertEqual(result['reviews'], reviews)
        self.assertEqual(result['interpretation'], 'model_disagreement_not_confidence_interval')

    def test_failed_abstained_missing_not_zero_scores(self):
        result = panel.summarize(self.policy, [self.review('a', 80), self.review('b', None, status='abstained')])
        metric = result['metrics']['clarity']
        self.assertEqual((metric['n'], metric['planned_n'], metric['mean']), (1, 3, 80))
        self.assertIsNone(metric['sample_variance'])
        self.assertIsNone(metric['sd'])
        self.assertEqual(result['missing_models'], ['c'])

    def test_duplicate_model_report_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inflate'):
            panel.summarize(self.policy, [self.review('a'), self.review('a', review_id='another-call')])

    def test_report_hash_or_scale_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            panel.summarize(self.policy, [self.review('a'), self.review('b', rubric_hash='different')])
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            panel.summarize(self.policy, [self.review('a'), self.review('b', score_scale={'min': 0, 'max': 10}, scores={})])

    def test_unanimity_accepts_independently_found_evidence(self):
        votes = [self.vote('a'), self.vote('b')]
        saved = copy.deepcopy(votes)
        result = panel.consensus(self.policy, votes)
        self.assertTrue(result['accepted'])
        self.assertEqual(votes, saved)
        self.assertFalse(result['evidence_truth_verified'])

    def test_no_majority_or_missing_reviewer_fallback(self):
        result = panel.consensus(self.policy, [self.vote('a'), self.vote('b', 'contradicted')])
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'reviewer_disagreement')
        result = panel.consensus(self.policy, [self.vote('a')])
        self.assertEqual(result['reason'], 'missing_required_reviewers')

    def test_outcome_match_without_numeric_match_is_not_consensus(self):
        result = panel.consensus(self.policy, [self.vote('a'), self.vote('b', normalized_result={'event_occurred': False})])
        self.assertEqual(result['reason'], 'reviewer_disagreement')

    def test_abstention_does_not_count_as_agreement(self):
        result = panel.consensus(self.policy, [self.vote('a'), self.vote('b', 'abstain', normalized_result=None, evidence_ids=[])])
        self.assertEqual(result['reason'], 'abstention_or_indeterminate')

    def test_evidence_and_cutoff_required(self):
        with self.assertRaisesRegex(ValueError, 'evidence'):
            panel.consensus(self.policy, [self.vote('a', evidence_ids=[]), self.vote('b')])
        with self.assertRaisesRegex(ValueError, 'cutoff'):
            panel.consensus(self.policy, [self.vote('a'), self.vote('b', as_of='2026-11-26')])

    def test_judge_is_explicit_and_must_consider_abstentions(self):
        self.policy['verification']['mode'] = 'judge'
        self.seal()
        votes = [self.vote('a'), self.vote('b', 'abstain', normalized_result=None, evidence_ids=[])]
        self.assertFalse(panel.consensus(self.policy, votes)['accepted'])
        self.assertTrue(panel.consensus(self.policy, votes, self.decision())['accepted'])
        decision = self.decision()
        decision['considered_vote_ids'] = ['v-a']
        with self.assertRaisesRegex(ValueError, 'every submitted vote'):
            panel.consensus(self.policy, votes, decision)

    def test_unanimous_human_fallback_must_be_preconfigured(self):
        votes = [self.vote('a'), self.vote('b', 'contradicted')]
        decision = self.decision()
        decision.update(actor_type='human', actor_id='user', user_approval_reference='actual-message')
        with self.assertRaisesRegex(ValueError, 'not preconfigured'):
            panel.consensus(self.policy, votes, decision)
        self.policy['verification']['escalation'] = 'human'
        self.seal()
        result = panel.consensus(self.policy, votes, decision)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['mode'], 'unanimous')
        self.assertEqual(result['resolution_route'], 'human_escalation')
        self.assertEqual(result['escalation_reason'], 'reviewer_disagreement')

    def test_fallback_cannot_override_clear_unanimity(self):
        self.policy['verification']['escalation'] = 'human'
        self.seal()
        decision = self.decision()
        decision.update(actor_type='human', actor_id='user', user_approval_reference='actual-message')
        with self.assertRaisesRegex(ValueError, 'Clear unanimity'):
            panel.consensus(self.policy, [self.vote('a'), self.vote('b')], decision)

    def test_judge_human_fallback_preserves_unresolved_judge(self):
        self.policy['verification'].update(mode='judge', escalation='human')
        self.seal()
        votes = [self.vote('a'), self.vote('b', 'contradicted')]
        prior = self.decision()
        prior.update(verdict='indeterminate', normalized_result=None, evidence_ids=[])
        decision = self.decision()
        decision.update(actor_type='human', actor_id='user', user_approval_reference='actual-message', prior_judge_decision=prior)
        result = panel.consensus(self.policy, votes, decision)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['escalation_reason'], 'judge_indeterminate')
        self.assertEqual(result['decision']['prior_judge_decision'], prior)
        decision['prior_judge_decision']['actor_id'] = 'unselected-model'
        with self.assertRaises(ValueError):
            panel.consensus(self.policy, votes, decision)

    def test_human_attribution_requires_approval_reference(self):
        self.policy['verification']['mode'] = 'human'
        self.seal()
        decision = self.decision()
        decision.update(actor_type='human', actor_id='user')
        votes = [self.vote('a'), self.vote('b')]
        with self.assertRaisesRegex(ValueError, 'approval reference'):
            panel.consensus(self.policy, votes, decision)
        decision['user_approval_reference'] = 'actual-user-message-reference'
        self.assertTrue(panel.consensus(self.policy, votes, decision)['accepted'])

    def test_numeric_normalization_and_judge_isolation_and_longitudinal_only(self):
        # 10 vs 10.0 should agree cleanly rather than trigger spurious disagreement.
        res = panel.consensus(self.policy, [self.vote('a', normalized_result={'value': 10}),
                                            self.vote('b', normalized_result={'value': 10.0})])
        self.assertTrue(res['accepted'])
        # Judge cannot equal sole reviewer unless allow_self_judge=true.
        self.policy['roles']['verify'] = ['a', 'b', 'c']
        self.policy['verification'] = {'mode': 'judge', 'required_reviewers': ['c'], 'judge_model_id': 'c'}
        with self.assertRaisesRegex(ValueError, 'sole required reviewer'):
            panel.validate_policy(self.policy)
        # Longitudinal-only policy allows empty lookup/extract/verify roles.
        long_pol = copy.deepcopy(self.policy)
        long_pol.pop('policy_hash', None)
        long_pol['analysis_modules'] = ['longitudinal', 'qualitative']
        long_pol['roles'] = {'lookup': [], 'extract': [], 'verify': [], 'report': ['a', 'b', 'c'], 'judge': []}
        long_pol['verification'] = {'mode': 'human', 'required_reviewers': [], 'judge_model_id': None}
        self.assertTrue(panel.validate_policy(long_pol)['valid'])

    def test_cli_help_clarifies_jsonl_and_array_error_mentions_jsonl(self):
        p = panel.parser()
        sub_actions = {a.dest: a for a in p._subparsers._group_actions}['command'].choices
        self.assertIn('JSONL', sub_actions['summarize'].format_help())
        self.assertIn('JSONL', sub_actions['consensus'].format_help())
        arr_path = self.run / 'array.json'
        arr_path.write_text('[{"a": 1}]\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'JSONL'):
            panel.read_rows(arr_path)


if __name__ == '__main__':
    unittest.main()
