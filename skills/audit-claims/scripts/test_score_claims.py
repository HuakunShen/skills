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


if __name__ == '__main__':
    unittest.main()
