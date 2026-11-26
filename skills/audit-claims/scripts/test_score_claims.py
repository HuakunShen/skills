#!/usr/bin/env python3
"""Behavioral checks for fair scoring denominators, evidence and audit integrity."""
import copy
import csv
import hashlib
import io
import unittest

import score_claims as scoring


def claim(cid='c1', **updates):
    definition = {'target': f'The event described by {cid}', 'predicate': 'Occurred within the stated period',
                  'window_start': '2025-01-01T00:00:00Z', 'window_end': '2025-12-31T23:59:59Z',
                  'timezone': 'UTC', 'condition': 'unconditional', 'resolution_basis': 'explicit'}
    result = {'schema_version': 1, 'claim_id': cid, 'subject_id': 'speaker', 'occurrence_ids': ['o_' + cid],
              'text': f'Event {cid} will occur by the end of 2025.', 'domain': 'general',
              'claim_type': 'prediction', 'empirical': True, 'endorsement': 'endorsed',
              'attribution_confidence': 'high', 'accountability_eligible': True,
              'quantifiability': 'operationalizable', 'verifiability': 'verifiable',
              'lifecycle': 'resolved', 'outcome': 'supported', 'due_for_assessment': True,
              'evaluation_mode': 'categorical', 'probability': None, 'probability_origin': 'none',
              'event_occurred': None, 'criteria': {'definition': definition, 'version': '1',
                  'frozen_at': '2026-01-01T10:00:00Z',
                  'sha256': hashlib.sha256(scoring.canonical(definition)).hexdigest()},
              'resolved_at': '2026-01-01T12:00:00Z', 'evidence_ids': ['e_' + cid],
              'evidence_quality': {'directness': 1, 'independence': 1, 'traceability': 1},
              'review_state': 'accepted'}
    result.update(updates)
    return result


def vague(cid='v', **updates):
    return claim(cid, **{'text': 'It will eventually work in an invisible way.',
                        'criteria': None, 'lifecycle': 'unscorable', 'outcome': None,
                        'due_for_assessment': False, 'accountability_eligible': False,
                        'evaluation_mode': 'none', 'evidence_ids': [], 'evidence_quality': None,
                        'quantifiability': 'none', 'verifiability': 'unverifiable',
                        'review_state': 'accepted', **updates})


def occurrence(oid, cid, **updates):
    return {'schema_version': 1, 'occurrence_id': oid, 'claim_id': cid, 'source_id': 'source',
            'speaker': 'speaker', 'original_quote': 'Original quote.', 'context_before': '',
            'context_after': '', 'locator': {'kind': 'paragraph', 'start': 1, 'end': 1},
            'endorsement': 'endorsed', 'language': 'en', **updates}


COVERAGE = {'eligible_sources': 100, 'acquired_sources': 100, 'extracted_sources': 100,
            'inventory_complete': True, 'unresolved_review_issues': 0}


class ScoreClaimTests(unittest.TestCase):
    def calculate(self, rows, **kwargs):
        return scoring.calculate(rows, copy.deepcopy(COVERAGE), **kwargs)

    def test_pending_values_and_quotes_do_not_distort_accuracy(self):
        rows = [claim(), claim('pending', lifecycle='pending', outcome=None, due_for_assessment=False,
                               evidence_ids=[], evidence_quality=None, review_state='unreviewed'),
                vague('preference', empirical=False, claim_type='preference'),
                claim('quoted', endorsement='quoted', outcome='contradicted')]
        result = self.calculate(rows)
        self.assertEqual(result['categorical_n'], 1)
        self.assertEqual(result['strict_support_rate']['value'], 1)
        self.assertEqual(result['adjudication_coverage']['denominator'], 1)

    def test_partial_is_visible_and_not_silently_half_credit(self):
        result = self.calculate([claim(), claim('bad', outcome='contradicted'), claim('partial', outcome='mixed')])
        self.assertAlmostEqual(result['strict_support_rate']['value'], 1 / 3)
        self.assertAlmostEqual(result['partial_share']['value'], 1 / 3)
        self.assertEqual(result['binary_accuracy_excluding_mixed']['value'], 0.5)

    def test_no_eligible_records_produce_null_not_perfect_score(self):
        result = self.calculate([vague('value', empirical=False, claim_type='value_judgment')], composite=True)
        self.assertIsNone(result['strict_support_rate']['value'])
        self.assertIsNone(result['accountability']['value'])
        self.assertIsNone(result['composite']['value'])

    def test_only_high_attribution_enters_personal_score(self):
        result = self.calculate([claim(), claim('uncertain', attribution_confidence='medium', outcome='contradicted')])
        self.assertEqual(result['categorical_n'], 1)
        self.assertEqual(result['strict_support_rate']['value'], 1)

    def test_unscorable_claim_cannot_dilute_due_verification_coverage(self):
        try:
            result = self.calculate([claim(), vague(due_for_assessment=True)])
        except ValueError:
            return  # Rejecting the contradictory lifecycle/due combination is also safe.
        self.assertEqual(result['adjudication_coverage']['denominator'], 1)
        self.assertEqual(result['adjudication_coverage']['value'], 1)

    def test_explicit_probabilities_get_brier_not_categorical_accuracy(self):
        rows = [claim('p70', evaluation_mode='probabilistic', probability=.7, probability_origin='explicit',
                      event_occurred=False, outcome=None),
                claim('p20', evaluation_mode='probabilistic', probability=.2, probability_origin='explicit',
                      event_occurred=False, outcome=None),
                claim('inferred', evaluation_mode='probabilistic', probability=.9, probability_origin='inferred',
                      event_occurred=True, outcome=None)]
        result = self.calculate(rows)
        self.assertEqual(result['categorical_n'], 0)
        self.assertEqual(result['brier']['n'], 2)
        self.assertAlmostEqual(result['brier']['value'], .265)

    def test_explicit_probability_cannot_masquerade_as_binary_verdict(self):
        row = claim(probability=.7, probability_origin='explicit', evaluation_mode='categorical')
        with self.assertRaises(ValueError):
            self.calculate([row])

    def test_repeating_a_view_changes_expression_share_not_accuracy_sample(self):
        bad_ids = [f'v{i}' for i in range(20)]
        rows = [claim(), vague(occurrence_ids=bad_ids)]
        occurrences = [occurrence('o_c1', 'c1')] + [occurrence(oid, 'v') for oid in bad_ids]
        result = self.calculate(rows, occurrences=occurrences)
        self.assertEqual(result['categorical_n'], 1)
        self.assertEqual(result['accountability']['value'], .5)
        self.assertAlmostEqual(result['noncheckable_expression_share']['value'], 20/21)

    def test_one_occurrence_cannot_back_two_canonical_claims(self):
        rows = [claim('a', occurrence_ids=['same']), claim('b', occurrence_ids=['same'])]
        with self.assertRaises(ValueError):
            self.calculate(rows, occurrences=[occurrence('same', 'a')])

    def test_invalid_technical_duplicate_references_cannot_hide_expressions(self):
        for target in ['absent', 'o_c1']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.calculate([claim()], occurrences=[occurrence('o_c1', 'c1', technical_duplicate_of=target)])
        row = claim(occurrence_ids=['a', 'b'])
        with self.assertRaises(ValueError):
            self.calculate([row], occurrences=[occurrence('a', 'c1', technical_duplicate_of='b'),
                                               occurrence('b', 'c1', technical_duplicate_of='a')])

    def test_zero_or_missing_quality_does_not_become_definite_support(self):
        for quality in [None, {'directness': 1, 'independence': 1, 'traceability': 0}]:
            with self.subTest(quality=quality):
                result = self.calculate([claim(evidence_quality=quality)])
                self.assertEqual(result['categorical_n'], 0)
                self.assertIsNone(result['strict_support_rate']['value'])

    def test_aggregate_quality_average_cannot_hide_a_zero_axis(self):
        rows = [claim(str(i), evidence_quality={'directness': 1, 'independence': 1, 'traceability': 0}) for i in range(30)]
        result = self.calculate(rows, composite=True)
        self.assertIsNone(result['composite']['value'])

    def test_composite_requires_coverage_sample_and_resolved_reviews(self):
        full = [claim(str(i)) for i in range(30)]
        self.assertEqual(self.calculate(full, composite=True)['composite']['value'], 100)
        self.assertIsNone(self.calculate(full[:29], composite=True)['composite']['value'])
        coverage = {**COVERAGE, 'acquired_sources': 90, 'extracted_sources': 85}
        self.assertIsNone(scoring.calculate(full, coverage, composite=True)['composite']['value'])
        coverage = {**COVERAGE, 'unresolved_review_issues': 1}
        self.assertIsNone(scoring.calculate(full, coverage, composite=True)['composite']['value'])

    def test_empty_criteria_hash_is_not_a_meaningful_frozen_rule(self):
        row = claim()
        row['criteria']['definition'] = {}
        row['criteria']['sha256'] = hashlib.sha256(scoring.canonical({})).hexdigest()
        with self.assertRaises(ValueError):
            self.calculate([row])

    def test_different_speakers_are_not_silently_merged_into_one_score(self):
        with self.assertRaises(ValueError):
            self.calculate([claim(), claim('guest', subject_id='guest', outcome='contradicted')])

    def test_unaccepted_and_disputed_verdicts_are_not_accuracy_samples(self):
        disputed = claim('disputed', lifecycle='disputed', outcome=None, review_state='needs_review')
        result = self.calculate([claim(), claim('draft', review_state='unreviewed', outcome='contradicted'), disputed])
        self.assertEqual(result['categorical_n'], 1)
        self.assertEqual(result['adjudication_coverage']['denominator'], 3)
        self.assertAlmostEqual(result['adjudication_coverage']['value'], 1/3)

    def test_missing_evidence_and_inconsistent_subjective_assertion_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate([claim(evidence_ids=[])])
        with self.assertRaises(ValueError):
            self.calculate([claim(claim_type='preference', empirical=True)])

    def test_csv_cells_neutralize_formulas_and_preserve_original_claims(self):
        values = ['=HYPERLINK("https://example.invalid")', '  +SUM(1,2)', '-1+1', '@SUM(1,2)', '\t=1+1', '\r=1+1']
        rows = [claim(str(i), text=value) for i, value in enumerate(values)]
        exported = list(csv.DictReader(io.StringIO(scoring.csv_text(rows))))
        self.assertEqual([row['text'] for row in exported], ["'" + value for value in values])
        self.assertEqual([row['text'] for row in rows], values)

    def test_claim_type_split_family_weighting_and_indeterminate_non_deadlock(self):
        # 40 factual supported + 10 same-family prediction contradicted:
        # pooled rate is 0.80, but prediction=0/10 and family_weighted separates the inflation.
        facts = [claim(f'f{i}', claim_type='factual') for i in range(40)]
        preds = [claim(f'p{i}', claim_type='prediction', family_id='btc-200k', outcome='contradicted') for i in range(10)]
        indet = claim('indet', lifecycle='resolved', outcome='indeterminate', review_state='accepted',
                      evidence_ids=[], evidence_quality=None)
        awaiting = claim('wait', lifecycle='awaiting_evidence', outcome=None, review_state='unreviewed',
                         evidence_ids=[], evidence_quality=None)
        result = self.calculate(facts + preds + [indet, awaiting], composite=True, bootstrap_clusters=True)
        self.assertAlmostEqual(result['by_claim_type']['factual']['strict_support_rate']['value'], 1.0)
        self.assertAlmostEqual(result['by_claim_type']['prediction']['strict_support_rate']['value'], 0.0)
        self.assertEqual(result['family_metrics']['family_count'], 41)
        self.assertAlmostEqual(result['family_metrics']['family_weighted_strict_support_rate'], 40 / 41)
        self.assertIsNotNone(result['family_metrics']['bootstrap_95_ci'])
        self.assertIsNotNone(result['composite']['value'])
        self.assertNotIn('unresolved_review_issues', result['composite']['blockers'])
        self.assertTrue(any('prediction_vs_factual_gap' in w for w in result['warnings']))

    def test_not_assessed_operationalization_and_inferred_prob_excluded_from_due(self):
        rows = [
            claim('c1'),
            claim('na', criteria=None, accountability_eligible=False, due_for_assessment=False,
                  lifecycle='pending', outcome=None, evidence_ids=[], evidence_quality=None,
                  review_state='unreviewed', operationalization_status='not_assessed'),
            claim('inf', evaluation_mode='probabilistic', probability=0.8, probability_origin='inferred',
                  lifecycle='resolved', outcome=None, event_occurred=True),
        ]
        result = self.calculate(rows)
        self.assertEqual(result['accountability']['numerator'], 2)
        self.assertEqual(result['accountability']['denominator'], 2)
        self.assertEqual(result['not_assessed_operationalization_count'], 1)
        self.assertEqual(result['adjudication_coverage']['denominator'], 1)

    def test_prediction_difficulty_tiers_validation_and_non_trivial_breakdown(self):
        rows = [
            claim('t1', difficulty='trivial', difficulty_score=1,
                  difficulty_rationale='Near-100% baseline: sun rises in the east.', outcome='supported'),
            claim('t2', difficulty_score=1, outcome='supported'),
            claim('m1', difficulty='moderate', difficulty_score=3, outcome='supported'),
            claim('h1', difficulty='hard', difficulty_score=4, outcome='contradicted'),
            claim('nc1', difficulty='non_consensus', difficulty_score=5, outcome='contradicted'),
            claim('f1', claim_type='factual', outcome='supported'),
        ]
        result = self.calculate(rows)
        pdiff = result['prediction_difficulty']
        self.assertEqual(pdiff['total_predictions'], 5)
        self.assertEqual(pdiff['rated_n'], 5)
        self.assertEqual(pdiff['unrated_n'], 0)
        self.assertAlmostEqual(pdiff['trivial_strict_support_rate']['value'], 1.0)
        self.assertEqual(pdiff['trivial_strict_support_rate']['denominator'], 2)
        self.assertAlmostEqual(pdiff['non_trivial_strict_support_rate']['value'], 1 / 3)
        self.assertEqual(pdiff['non_trivial_strict_support_rate']['denominator'], 3)
        self.assertAlmostEqual(pdiff['trivial_share_of_rated_categorical']['value'], 0.4)
        self.assertIn('trivial', pdiff['by_tier'])
        self.assertIn('non_consensus', pdiff['by_tier'])
        self.assertTrue(any('trivial_prediction_inflation' in w for w in result['warnings']))
        for bad_kwargs in (
            {'difficulty': 'impossible'},
            {'difficulty_score': 0},
            {'difficulty_score': 6},
            {'difficulty_score': True},
            {'difficulty_rationale': 123},
        ):
            with self.subTest(bad=bad_kwargs), self.assertRaises(ValueError):
                self.calculate([claim('bad', **bad_kwargs)])

    def test_temporal_guard_rejects_retroactive_and_same_day_date_only_predictions(self):
        def pred_with_dates(cid, stated, end, ctype='prediction'):
            c = claim(cid, claim_type=ctype, first_stated_at=stated)
            c['criteria']['definition']['window_end'] = end
            c['criteria']['sha256'] = hashlib.sha256(scoring.canonical(c['criteria']['definition'])).hexdigest()
            return c

        # Oct 1 video talking about Sept 30 event cannot be a prediction.
        with self.assertRaisesRegex(ValueError, 'temporal guard'):
            self.calculate([pred_with_dates('retro_date', '2025-10-01', '2025-09-30')])
        # Same-day date-only target cannot be proven post-statement.
        with self.assertRaisesRegex(ValueError, 'temporal guard'):
            self.calculate([pred_with_dates('same_day', '2025-10-01T14:00:00Z', '2025-10-01')])
        # Exact datetime on or before statement time is rejected.
        with self.assertRaisesRegex(ValueError, 'temporal guard'):
            self.calculate([pred_with_dates('retro_dt', '2025-10-01T14:00:00Z', '2025-10-01T14:00:00Z')])
        # Exact intraday datetime strictly after statement is allowed.
        intraday = pred_with_dates('intraday_ok', '2025-10-01T09:00:00-04:00', '2025-10-01T16:00:00-04:00')
        res = self.calculate([intraday])
        self.assertEqual(res['prediction_horizon']['dated_n'], 1)
        self.assertAlmostEqual(res['prediction_horizon']['mean_lead_time_days'], 0.29, places=2)
        # Factual claim about a past event is completely valid.
        fact = pred_with_dates('fact_past', '2025-10-01', '2025-09-30', ctype='factual')
        self.assertEqual(self.calculate([fact])['categorical_n'], 1)

    def test_prediction_lead_time_and_horizon_buckets(self):
        def dated_pred(cid, stated, end, outcome='supported', difficulty=None, score=None):
            c = claim(cid, first_stated_at=stated, outcome=outcome)
            if difficulty is not None:
                c['difficulty'] = difficulty
            if score is not None:
                c['difficulty_score'] = score
            c['criteria']['definition']['window_end'] = end
            c['criteria']['sha256'] = hashlib.sha256(scoring.canonical(c['criteria']['definition'])).hexdigest()
            return c

        undated = claim('u1', first_stated_at='2025-01-01', outcome='supported')
        undated['criteria']['definition']['window_end'] = None
        undated['criteria']['sha256'] = hashlib.sha256(scoring.canonical(undated['criteria']['definition'])).hexdigest()

        rows = [
            dated_pred('p15', '2025-01-01', '2025-01-16', 'supported', 'moderate', 3),       # 15d -> le_30d
            dated_pred('p60', '2025-01-01', '2025-03-02', 'contradicted', 'hard', 4),         # 60d -> 31_90d
            dated_pred('p120', '2025-01-01', '2025-05-01', 'supported', 'hard', 4),           # 120d -> 91_180d
            dated_pred('p240', '2025-01-01', '2025-08-29', 'supported', 'non_consensus', 5),  # 240d -> 181_365d
            dated_pred('p400', '2024-01-01', '2025-02-04', 'contradicted', 'non_consensus', 5),  # 400d -> gt_365d
            undated,
        ]
        res = self.calculate(rows)
        ph = res['prediction_horizon']
        self.assertEqual(ph['total_predictions'], 6)
        self.assertEqual(ph['dated_n'], 5)
        self.assertEqual(ph['undated_n'], 1)
        self.assertAlmostEqual(ph['mean_lead_time_days'], 167.0)
        self.assertAlmostEqual(ph['median_lead_time_days'], 120.0)
        self.assertAlmostEqual(ph['min_lead_time_days'], 15.0)
        self.assertAlmostEqual(ph['max_lead_time_days'], 400.0)
        # Supported predictions: 15, 120, 240 -> mean 125.0, median 120.0
        self.assertAlmostEqual(ph['supported_mean_lead_time_days'], 125.0)
        self.assertAlmostEqual(ph['supported_median_lead_time_days'], 120.0)
        self.assertEqual(ph['buckets']['le_30d']['count'], 1)
        self.assertEqual(ph['buckets']['le_30d']['strict_support_rate']['value'], 1.0)
        self.assertEqual(ph['buckets']['31_90d']['strict_support_rate']['value'], 0.0)
        self.assertEqual(ph['buckets']['91_180d']['strict_support_rate']['value'], 1.0)
        self.assertEqual(ph['buckets']['181_365d']['strict_support_rate']['value'], 1.0)
        self.assertEqual(ph['buckets']['gt_365d']['strict_support_rate']['value'], 0.0)
        self.assertEqual(set(res['by_horizon']), {'le_30d', '31_90d', '91_180d', '181_365d', 'gt_365d', 'undated'})
        exported = list(csv.DictReader(io.StringIO(scoring.csv_text(rows))))
        by_id = {r['claim_id']: r for r in exported}
        self.assertEqual(by_id['p120']['difficulty'], 'hard')
        self.assertEqual(by_id['p120']['difficulty_score'], '4')
        self.assertEqual(float(by_id['p120']['lead_time_days']), 120.0)


class SourcingRigorTests(unittest.TestCase):
    def test_citation_counts_rates_and_checkability_with_untagged_legacy_claims(self):
        rows = [
            claim('primary', citation_status='primary_cited', verifiability='verifiable'),
            claim('secondary', citation_status='secondary_cited', verifiability='unverifiable'),
            claim('specific', citation_status='uncited_specific', verifiability='conditional'),
            claim('vague', citation_status='uncited_vague', verifiability='unverifiable'),
            claim('legacy', verifiability='verifiable'),
            # Quoted or non-empirical statements are outside the speaker's own endorsed empirical population.
            claim('quoted', citation_status='primary_cited', endorsement='quoted'),
            claim('opinion', citation_status='uncited_vague', empirical=False, claim_type='preference'),
        ]
        sr = scoring.core_metrics(rows)['sourcing_rigor']
        self.assertEqual(sr['population_n'], 5)
        self.assertEqual(sr['tagged_n'], 4)
        self.assertEqual(sr['counts'], {'primary_cited': 1, 'secondary_cited': 1, 'uncited_specific': 1,
                                        'uncited_vague': 1, 'untagged': 1})
        self.assertAlmostEqual(sr['citation_rate']['value'], 0.5)
        self.assertAlmostEqual(sr['primary_citation_rate']['value'], 0.25)
        self.assertAlmostEqual(sr['unsubstantiated_rate']['value'], 0.5)
        self.assertAlmostEqual(sr['checkable_rate']['value'], 3 / 5)
        self.assertAlmostEqual(sr['untagged_share']['value'], 1 / 5)
        self.assertAlmostEqual(sr['shares']['uncited_specific']['value'], 0.25)
        self.assertIsNotNone(sr['citation_rate']['ci_95'])

    def test_sourcing_rigor_is_reported_overall_and_per_group(self):
        rows = [claim('p1', claim_type='prediction', citation_status='uncited_specific'),
                claim('p2', claim_type='prediction', citation_status='primary_cited'),
                claim('f1', claim_type='factual', citation_status='secondary_cited')]
        result = scoring.calculate(rows, copy.deepcopy(COVERAGE))
        self.assertEqual(result['sourcing_rigor']['tagged_n'], 3)
        self.assertAlmostEqual(result['by_claim_type']['prediction']['sourcing_rigor']['unsubstantiated_rate']['value'], 0.5)
        self.assertAlmostEqual(result['by_claim_type']['factual']['sourcing_rigor']['citation_rate']['value'], 1.0)
        self.assertEqual(result['by_claim_type']['factual']['sourcing_rigor']['tagged_n'], 1)

    def test_legacy_ledger_without_citation_tags_is_not_a_zero_rate(self):
        rows = [claim('a'), vague('b')]
        result = scoring.calculate(rows, copy.deepcopy(COVERAGE))
        sr = result['sourcing_rigor']
        self.assertEqual(sr['tagged_n'], 0)
        self.assertEqual(sr['counts']['untagged'], 2)
        self.assertIsNone(sr['citation_rate']['value'])
        self.assertIsNone(sr['unsubstantiated_rate']['value'])
        self.assertAlmostEqual(sr['checkable_rate']['value'], 1 / 2)

    def test_citation_fields_are_validated_and_exported(self):
        with self.assertRaises(ValueError):
            scoring.validate_claim(claim('bad_status', citation_status='hearsay'))
        with self.assertRaises(ValueError):
            scoring.validate_claim(claim('bad_text', citation_status='primary_cited', citation_text=['x']))
        scoring.validate_claim(claim('ok', citation_status='primary_cited', citation_text='Reuters report'))
        exported = list(csv.DictReader(io.StringIO(scoring.csv_text(
            [claim('ok', citation_status='uncited_vague')]))))
        self.assertEqual(exported[0]['citation_status'], 'uncited_vague')




class CredibilityAndDifficultyTests(unittest.TestCase):
    def calculate(self, rows):
        return scoring.calculate(rows, copy.deepcopy(COVERAGE))

    def test_traffic_light_thresholds_for_rates_scores_and_error_rates(self):
        self.assertEqual(scoring.traffic_light(0.80), 'green')
        self.assertEqual(scoring.traffic_light(0.7999), 'yellow')
        self.assertEqual(scoring.traffic_light(0.60), 'yellow')
        self.assertEqual(scoring.traffic_light(0.5999), 'red')
        self.assertEqual(scoring.traffic_light(85, scale=100), 'green')
        self.assertEqual(scoring.traffic_light(59.9, scale=100), 'red')
        self.assertEqual(scoring.traffic_light(0.04, error_rate=True), 'green')
        self.assertEqual(scoring.traffic_light(0.05, error_rate=True), 'yellow')
        self.assertEqual(scoring.traffic_light(0.15, error_rate=True), 'yellow')
        self.assertEqual(scoring.traffic_light(0.1501, error_rate=True), 'red')
        self.assertIsNone(scoring.traffic_light(None))

    def test_factual_credibility_ignores_predictions_and_penalizes_uncited_contradictions(self):
        rows = [
            claim('fs', claim_type='factual', outcome='supported', citation_status='primary_cited'),
            claim('fm', claim_type='factual', outcome='mixed', citation_status='secondary_cited'),
            claim('fc', claim_type='factual', outcome='contradicted', citation_status='secondary_cited'),
            claim('fu', claim_type='factual', outcome='contradicted', citation_status='uncited_specific'),
            claim('p1', outcome='contradicted', citation_status='uncited_specific'),
        ]
        fc = self.calculate(rows)['factual_credibility']
        self.assertEqual(fc['factual_categorical_n'], 4)
        self.assertEqual(fc['counts'], {'supported': 1, 'mixed': 1, 'contradicted': 2, 'contradicted_uncited': 1})
        self.assertAlmostEqual(fc['contradiction_rate']['value'], 0.5)
        self.assertAlmostEqual(fc['misinformation_rate']['value'], 0.25)
        self.assertEqual(fc['contradiction_rate']['traffic_light'], 'red')
        self.assertEqual(fc['misinformation_rate']['traffic_light'], 'red')
        # credit = 1.0 (supported) + 0.5 (mixed) + 0.0 (cited contradiction) - 0.5 (uncited) = 1.0 of 4
        self.assertAlmostEqual(fc['factual_honesty_score']['value'], 25.0)
        self.assertEqual(fc['factual_honesty_score']['traffic_light'], 'red')

    def test_honesty_penalty_orders_uncited_below_cited_contradiction_below_mixed(self):
        def score(outcome, status):
            # A supported anchor keeps the population above the 0-100 clipping floor.
            rows = [claim('anchor', claim_type='factual', outcome='supported', citation_status='primary_cited'),
                    claim('f', claim_type='factual', outcome=outcome, citation_status=status)]
            return self.calculate(rows)['factual_credibility']['factual_honesty_score']['value']
        self.assertAlmostEqual(score('mixed', 'secondary_cited'), 75.0)
        self.assertAlmostEqual(score('contradicted', 'secondary_cited'), 50.0)
        self.assertAlmostEqual(score('contradicted', 'uncited_vague'), 25.0)
        self.assertGreater(score('mixed', 'secondary_cited'), score('contradicted', 'primary_cited'))
        self.assertGreater(score('contradicted', 'primary_cited'), score('contradicted', 'uncited_vague'))

    def test_difficulty_weighting_stops_trivial_only_track_records_from_scoring_high(self):
        def pred(cid, tier, outcome='supported'):
            return claim(cid, first_stated_at='2025-01-01', difficulty=tier, outcome=outcome)
        trivial_only = [pred(f't{i}', 'trivial') for i in range(3)]
        hard_only = [pred(f'h{i}', 'hard') for i in range(3)]
        trivial = self.calculate(trivial_only)['difficulty_adjusted']
        hard = self.calculate(hard_only)['difficulty_adjusted']
        self.assertAlmostEqual(trivial['difficulty_adjusted_score']['value'], round(100 * 0.5 / 3, 2))
        self.assertAlmostEqual(hard['difficulty_adjusted_score']['value'], round(100 * 2.0 / 3, 2))
        self.assertEqual(trivial['weighted_strict_support_rate'], 1.0)
        self.assertLess(trivial['difficulty_exposure'], hard['difficulty_exposure'])
        self.assertLess(trivial['difficulty_adjusted_score']['value'], hard['difficulty_adjusted_score']['value'])

    def test_unrated_predictions_are_excluded_from_weighted_score_but_counted(self):
        rows = [claim('r1', first_stated_at='2025-01-01', difficulty='non_consensus', outcome='supported'),
                claim('u1', first_stated_at='2025-01-01', outcome='contradicted')]
        da = self.calculate(rows)['difficulty_adjusted']
        self.assertEqual(da['weighted_n'], 1)
        self.assertEqual(da['unrated_excluded_n'], 1)
        self.assertAlmostEqual(da['difficulty_adjusted_score']['value'], 100.0)

    def test_overconfidence_gap_uses_certainty_markers_and_respects_hedges(self):
        rows = [
            claim('c1', first_stated_at='2025-01-01', outcome='contradicted', certainty_text='我一定会做到'),
            claim('c2', first_stated_at='2025-01-01', outcome='supported', certainty_text='毫无疑问'),
            claim('p1', first_stated_at='2025-01-01', outcome='supported'),
            claim('p2', first_stated_at='2025-01-01', outcome='supported', certainty_text='不一定'),
        ]
        gap = self.calculate(rows)['difficulty_adjusted']['overconfidence_gap']
        self.assertEqual(gap['high_certainty_n'], 2)
        self.assertAlmostEqual(gap['high_certainty_strict_support_rate'], 0.5)
        self.assertAlmostEqual(gap['overall_strict_support_rate'], 0.75)
        self.assertAlmostEqual(gap['value'], 0.25)
        self.assertFalse(scoring._is_high_certainty(claim('h', certainty_text='不一定会发生')))
        self.assertIsNone(self.calculate([claim('n1', first_stated_at='2025-01-01')])['difficulty_adjusted']['overconfidence_gap']['value'])

    def test_lead_time_weighted_support_uses_log_weights_on_dated_predictions(self):
        rows = [claim('a', first_stated_at='2025-01-01', outcome='supported'),
                claim('b', first_stated_at='2025-01-01', outcome='contradicted')]
        lead = self.calculate(rows)['difficulty_adjusted']['lead_time_weighted_support_rate']
        self.assertEqual(lead['dated_n'], 2)
        self.assertGreater(lead['denominator'], 0)
        self.assertGreater(lead['value'], 0)
        self.assertLess(lead['value'], 1)
        self.assertEqual(lead['weight'], 'log2(1 + max(0, lead_time_days) / 30)')

    def test_legacy_runs_without_new_fields_report_null_not_zero(self):
        m = self.calculate([claim('legacy', claim_type='factual', outcome='supported')])
        self.assertIsNone(m['difficulty_adjusted']['difficulty_adjusted_score']['value'])
        self.assertAlmostEqual(m['factual_credibility']['factual_honesty_score']['value'], 100.0)
        self.assertIsNone(self.calculate([claim('p')])['factual_credibility']['factual_honesty_score']['value'])

    def test_difficulty_ratings_are_attributed_to_recording_models(self):
        rows = [claim('m1', first_stated_at='2025-01-01', difficulty='hard', difficulty_model_id='model_a'),
                claim('m2', first_stated_at='2025-01-01', difficulty='hard', difficulty_model_id='model_a'),
                claim('m3', first_stated_at='2025-01-01', difficulty='moderate')]
        raters = self.calculate(rows)['prediction_difficulty']['rated_by_model_id']
        self.assertEqual(raters, {'model_a': 2, 'unrecorded': 1})


if __name__ == '__main__':
    unittest.main()
