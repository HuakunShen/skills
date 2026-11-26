#!/usr/bin/env python3
"""Offline renderer regressions using manual synthetic fixtures, never real panel runs."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import html
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

import model_panel as panel
import render_report as renderer

ROOT = Path(__file__).resolve().parent.parent
SVG = '{http://www.w3.org/2000/svg}'


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class RenderReportTests(unittest.TestCase):
    def setUp(self):
        self.data = renderer.load_json(ROOT / 'assets/report-sample.json')
        self.rubric = renderer.load_json(ROOT / 'assets/evaluation-rubric.json')
        self.dimensions = [dimension['id'] for dimension in self.rubric['dimensions']]

    def set_missing(self, review, dimension):
        review['scores'][dimension] = None
        review['rationales'][dimension] = {
            'rationale': None, 'supporting_evidence_ids': [], 'counter_evidence_ids': [],
            'missing_reason': 'Manual synthetic fixture: insufficient observations; not a zero rating.'}

    def rebind_rubric(self, data, rubric):
        data['rubric'] = rubric
        digest = hashlib.sha256(panel.canonical(rubric).encode('utf-8')).hexdigest()
        for review in data['panel']['reviews']:
            review['rubric_hash'] = digest
        if data['panel'].get('judge'):
            data['panel']['judge']['rubric_hash'] = digest

    def test_sample_is_explicitly_manual_synthetic_in_html_and_svg(self):
        self.assertIs(self.data['synthetic'], True)
        reviews = self.data['panel']['reviews']
        self.assertEqual(len(reviews), 3)
        self.assertTrue(all(review.get('synthetic') is True for review in reviews))
        self.assertTrue(all('manual' in review.get('provenance', '').lower() or
                            'hand-constructed' in review.get('provenance', '').lower() for review in reviews))
        page, radar = renderer.render_report(self.data), renderer.render_radar(self.data)
        self.assertIn('合成演示数据', page)
        self.assertIn('未调用真实模型', page)
        self.assertIn('合成演示数据', radar)
        self.assertIn('未调用真实模型', radar)

    def test_external_html_and_svg_text_is_escaped_in_all_rendered_contexts(self):
        payload = '</text><script>alert("X")</script><img src=x onerror="bad()"> & injected'
        data, rubric = copy.deepcopy(self.data), copy.deepcopy(self.rubric)
        data['report']['title'] = payload
        data['report']['summary'][0] = payload
        data['sources'][0]['title'] = payload
        data['sources'][0]['excerpt'] = payload
        data['topics'][0]['entries'][0]['quote'] = payload
        data['panel']['reviews'][0]['rationales'][self.dimensions[0]]['rationale'] = payload
        data['panel']['policy']['selected_models'][0]['display_name'] = payload
        data['panel']['policy']['policy_hash'] = panel.policy_hash(data['panel']['policy'])
        rubric['dimensions'][0]['label'] = payload
        self.rebind_rubric(data, rubric)
        page = renderer.render_report(data)
        self.assertIn(html.escape(payload, quote=True), page)
        parsed = Tags()
        parsed.feed(page)
        self.assertFalse({'img', 'iframe', 'object', 'embed', 'foreignobject'} &
                         {tag for tag, _ in parsed.elements})
        # Only the bundled, static explorer script may appear; payload text must never become script.
        self.assertEqual([tag for tag, _ in parsed.elements].count('script'), 1)
        self.assertNotIn('alert("X")', page)
        self.assertFalse(any(name.lower().startswith('on') for _, attrs in parsed.elements for name in attrs))
        radar = renderer.render_radar(data)
        root = ET.fromstring(radar)
        self.assertIn(html.escape(payload, quote=True), radar)
        self.assertFalse(any(node.tag.split('}')[-1] in {'script', 'image', 'foreignObject'} for node in root.iter()))
        self.assertFalse(any(name.lower().startswith('on') for node in root.iter() for name in node.attrib))

    def test_unsafe_source_urls_are_rejected(self):
        urls = ['javascript:alert(1)', 'data:text/html,<script>x</script>', 'file:///etc/passwd',
                '//example.org/path', 'https://user:password@example.org/',
                'https://example.org/\nmalicious', 'https:\\example.org\\path']
        for url in urls:
            with self.subTest(url=url):
                data = copy.deepcopy(self.data)
                data['sources'][0]['url'] = url
                with self.assertRaises(ValueError):
                    renderer.render_report(data)
        data = copy.deepcopy(self.data)
        data['sources'][0]['url'] = 'https://example.org/?a=1&b=%22quoted%22'
        self.assertIn('href="https://example.org/?a=1&amp;b=%22quoted%22"', renderer.render_report(data))

    def test_theme_tokens_reject_css_injection(self):
        invalid = [
            {'light': {'foreground': '#FFFFFF; background:url(https://example.invalid)'}},
            {'dark': {'surface': '</style><script>x</script>'}},
            {'font': 'system;src:url(https://example.invalid)'},
            {'radius': '8px; color:red'}, {'radius': True},
            {'custom_css': '@import url(https://example.invalid)'},
        ]
        for theme in invalid:
            with self.subTest(theme=theme), self.assertRaises(ValueError):
                renderer.render_report(self.data, theme=theme)
        valid = renderer.validate_theme({'light': {'accent': '#123ABC'}, 'radius': 6, 'font': 'sans'})
        self.assertEqual(valid['light']['accent'], '#123ABC')

    def test_scores_require_finite_numbers_on_the_agreed_scale(self):
        for bad in ['8', True, float('nan'), float('inf'), -0.1, 10.1]:
            with self.subTest(score=bad):
                data = copy.deepcopy(self.data)
                data['panel']['reviews'][0]['scores'][self.dimensions[0]] = bad
                with self.assertRaises(ValueError):
                    renderer.render_report(data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nonfinite.json'
            for literal in ['NaN', 'Infinity', '-Infinity']:
                path.write_text('{"value":' + literal + '}', encoding='utf-8')
                with self.assertRaises(ValueError):
                    renderer.load_json(path)

    def test_missing_scores_are_explicit_and_do_not_become_zero_vertices(self):
        data = copy.deepcopy(self.data)
        one, none = self.dimensions[:2]
        original_score = data['panel']['reviews'][0]['scores'][one]
        for review in data['panel']['reviews'][1:]:
            self.set_missing(review, one)
        for review in data['panel']['reviews']:
            self.set_missing(review, none)
        metrics = renderer.validate_report(data)['stats']['metrics']
        self.assertEqual(metrics[one]['n'], 1)
        self.assertEqual(metrics[one]['mean'], original_score)
        self.assertIsNone(metrics[one]['sample_variance'])
        self.assertIsNone(metrics[one]['sd'])
        self.assertEqual(metrics[none]['n'], 0)
        self.assertIsNone(metrics[none]['mean'])
        self.assertIsNone(metrics[none]['sample_variance'])
        root = ET.fromstring(renderer.render_radar(data))
        expected_points = sum(value is not None for r in data['panel']['reviews'] for value in r['scores'].values())
        self.assertEqual(len(root.findall('.//' + SVG + "circle[@class='model']")), expected_points)
        expected_mean_points = sum(metrics[dimension]['mean'] is not None for dimension in self.dimensions)
        self.assertEqual(len(root.findall('.//' + SVG + "circle[@class='mean']")), expected_mean_points)
        self.assertEqual(len(root.findall('.//' + SVG + "polygon[@class='mean']")), 0)
        del data['panel']['reviews'][0]['scores'][one]
        with self.assertRaisesRegex(ValueError, 'explicit null'):
            renderer.validate_report(data)

    def test_unperformed_fact_check_is_not_displayed_as_zero_accuracy(self):
        for absent in (True, False):
            with self.subTest(absent=absent):
                data = copy.deepcopy(self.data)
                if absent:
                    data.pop('metrics')
                else:
                    data['metrics'] = None
                self.assertIn('未执行事实核验', renderer.render_report(data))
                self.assertNotIn('0.0%', renderer.objective_metrics(data))
                self.assertIn('未执行事实核验', renderer.render_report(data, view='longitudinal'))

    def test_statistics_require_matching_frozen_data_rubric_and_scale(self):
        for field, different in [('data_hash', 'another-frozen-input'), ('rubric_hash', 'another-rubric'),
                                  ('score_scale', {'min': 0, 'max': 100})]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data['panel']['reviews'][1][field] = different
                with self.assertRaises(ValueError):
                    renderer.validate_report(data)
        for field in ('data_hash', 'rubric_hash'):
            with self.subTest(all_same_but_wrong_binding=field):
                data = copy.deepcopy(self.data)
                for review in data['panel']['reviews']:
                    review[field] = 'shared-but-not-the-rendered-input'
                with self.assertRaises(ValueError):
                    renderer.validate_report(data)

    def test_judge_stays_outside_reviewer_mean_and_variance(self):
        before = renderer.validate_report(self.data)['stats']
        data = copy.deepcopy(self.data)
        dimension = self.dimensions[0]
        data['panel']['judge']['scores'][dimension] = 0
        data['panel']['judge']['rationales'][dimension]['rationale'] = 'Manual synthetic judge boundary; no real model was called.'
        after = renderer.validate_report(data)['stats']
        self.assertEqual(after['metrics'], before['metrics'])
        self.assertEqual(after['metrics'][dimension]['n'], 3)
        self.assertIn('Judge 不参与均值与方差', renderer.render_report(data))
        for field, wrong in [('data_hash', 'wrong'), ('rubric_hash', 'wrong'),
                              ('score_scale', {'min': 0, 'max': 100})]:
            altered = copy.deepcopy(data)
            altered['panel']['judge'][field] = wrong
            with self.subTest(judge_binding=field), self.assertRaises(ValueError):
                renderer.validate_report(altered)

    def test_unfinished_judge_cannot_display_final_numeric_scores(self):
        for status in ('pending', 'abstained', 'not_requested'):
            with self.subTest(status=status):
                data = copy.deepcopy(self.data)
                data['panel']['judge']['status'] = status
                with self.assertRaises(ValueError):
                    renderer.render_report(data)
                data['panel']['judge']['scores'] = {dimension: None for dimension in self.dimensions}
                page = renderer.render_report(data)
                self.assertIn('未完成或未请求', page)
                self.assertNotIn('class="judge"', page)

    def test_numeric_ratings_and_nulls_require_traceable_explanations(self):
        dimension = self.dimensions[0]
        data = copy.deepcopy(self.data)
        data['panel']['reviews'][0]['rationales'][dimension]['supporting_evidence_ids'] = []
        data['panel']['reviews'][0]['rationales'][dimension]['counter_evidence_ids'] = []
        with self.assertRaises(ValueError):
            renderer.validate_report(data)
        data = copy.deepcopy(self.data)
        self.set_missing(data['panel']['reviews'][0], dimension)
        data['panel']['reviews'][0]['rationales'][dimension]['missing_reason'] = None
        with self.assertRaises(ValueError):
            renderer.validate_report(data)
        data = copy.deepcopy(self.data)
        data['panel']['reviews'][0]['rationales'][dimension]['supporting_evidence_ids'] = ['missing-source']
        with self.assertRaises(ValueError):
            renderer.validate_report(data)

    def test_coverage_metrics_cannot_switch_to_an_easier_denominator(self):
        data = copy.deepcopy(self.data)
        coverage = data['coverage']
        data['metrics']['extraction_coverage'] = {
            'numerator': coverage['extracted_sources'], 'denominator': coverage['acquired_sources'],
            'value': coverage['extracted_sources'] / coverage['acquired_sources']}
        with self.assertRaises(ValueError):
            renderer.validate_report(data)

    def test_output_collisions_never_overwrite_inputs_or_other_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, output = folder / 'report.json', folder / 'report.html'
            source.write_text(json.dumps(self.data, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            original = source.read_bytes()
            invocations = [
                ['--input', str(source), '--out', str(source)],
                ['--input', str(source), '--out', str(output), '--radar-out', str(source)],
                ['--input', str(source), '--out', str(output), '--radar-out', str(output)],
            ]
            for argv in invocations:
                with self.subTest(argv=argv), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    self.assertEqual(renderer.main(argv), 2)
                self.assertEqual(source.read_bytes(), original)
                self.assertFalse(output.exists())

    def test_null_fields_english_i18n_case_validation_and_dark_contrast(self):
        data = copy.deepcopy(self.data)
        data['coverage'] = None
        data['costs'] = None
        data['sources'][0]['published_at'] = None
        page_en = renderer.render_report(data, lang='en')
        self.assertIn('<html lang="en">', page_en)
        self.assertIn('Date unknown', page_en)
        self.assertNotIn('None ·', page_en)
        self.assertIn('#F87171', page_en)
        bad_case = copy.deepcopy(self.data)
        del bad_case['cases'][0]['title']
        with self.assertRaisesRegex(ValueError, 'case.title'):
            renderer.validate_report(bad_case)

    def test_english_lang_renders_english_rubric_labels_in_html_and_svg(self):
        data = copy.deepcopy(self.data)
        data['cases'][0]['original_quote'] = 'BTC <100k> "quote" check.'
        page_en = renderer.render_report(data, lang='en')
        radar_en = renderer.render_radar(data, standalone=True, lang='en')
        panel_start = page_en.index('<section id="model-panel"')
        panel_end = page_en.index('</section>', panel_start)
        panel_en = page_en[panel_start:panel_end]
        for dim in self.rubric['dimensions']:
            self.assertIn('label_en', dim)
            self.assertIn('description_en', dim)
            self.assertIn(dim['label_en'], panel_en)
            self.assertNotIn(dim['label'], panel_en)
            self.assertIn(f'<title>{dim["label_en"]}</title>', radar_en)
            self.assertNotIn(dim['label'], radar_en)
        self.assertIn('BTC &lt;100k&gt; &quot;quote&quot; check.', page_en)
        # Ensure SVG parses cleanly and wraps English words without splitting mid-word.
        ET.fromstring(radar_en)
        self.assertIn('>Counterargument</tspan>', radar_en)
        self.assertIn('>Engagement</tspan>', radar_en)

    def test_renders_prediction_difficulty_horizon_and_case_metadata_in_zh_and_en(self):
        data = copy.deepcopy(self.data)
        data['metrics']['prediction_difficulty'] = {
            'total_predictions': 5, 'rated_n': 5, 'unrated_n': 0,
            'mean_difficulty_score': 3.2,
            'non_trivial_strict_support_rate': {'value': 0.5, 'numerator': 1, 'denominator': 2},
            'trivial_strict_support_rate': {'value': 1.0, 'numerator': 2, 'denominator': 2},
            'trivial_share_of_rated_categorical': {'value': 0.5, 'numerator': 2, 'denominator': 4},
            'by_tier': {
                'trivial': {'total_canonical_claims': 2, 'mean_difficulty_score': 1.0,
                            'strict_support_rate': {'value': 1.0, 'numerator': 2, 'denominator': 2}},
                'hard': {'total_canonical_claims': 2, 'mean_difficulty_score': 4.0,
                         'strict_support_rate': {'value': 0.5, 'numerator': 1, 'denominator': 2}},
            },
        }
        data['metrics']['prediction_horizon'] = {
            'total_predictions': 5, 'dated_n': 4, 'undated_n': 1, 'unknown_stated_at_n': 0,
            'mean_lead_time_days': 135.5, 'median_lead_time_days': 120.0,
            'min_lead_time_days': 15.0, 'max_lead_time_days': 380.0,
            'supported_mean_lead_time_days': 160.0, 'supported_median_lead_time_days': 160.0,
            'buckets': {
                'le_30d': {'count': 1, 'categorical_n': 1, 'strict_support_rate': {'value': 1.0, 'numerator': 1, 'denominator': 1}, 'mean_lead_time_days': 15.0},
                '31_90d': {'count': 0, 'categorical_n': 0, 'strict_support_rate': {'value': None, 'numerator': 0, 'denominator': 0}, 'mean_lead_time_days': None},
                '91_180d': {'count': 2, 'categorical_n': 2, 'strict_support_rate': {'value': 0.5, 'numerator': 1, 'denominator': 2}, 'mean_lead_time_days': 120.0},
                '181_365d': {'count': 0, 'categorical_n': 0, 'strict_support_rate': {'value': None, 'numerator': 0, 'denominator': 0}, 'mean_lead_time_days': None},
                'gt_365d': {'count': 1, 'categorical_n': 1, 'strict_support_rate': {'value': 0.0, 'numerator': 0, 'denominator': 1}, 'mean_lead_time_days': 380.0},
            },
        }
        data['cases'][0].update({
            'speaker': 'Host <A>', 'subject_id': 'Host <A>', 'endorsement': 'endorsed',
            'difficulty': 'hard', 'difficulty_score': 4,
            'difficulty_rationale': 'Pre-outcome rationale <escaped>.', 'lead_time_days': 120,
        })
        page_zh = renderer.render_report(data, lang='zh')
        page_en = renderer.render_report(data, lang='en')
        self.assertIn('预测难度分层', page_zh)
        self.assertIn('非平凡预测支持率: 50.0% (1/2)', page_zh)
        self.assertIn('预测提前期分布', page_zh)
        self.assertIn('135.5d', page_zh)
        self.assertIn('91–180天', page_zh)
        self.assertIn('较难 (4/5)', page_zh)
        self.assertIn('120d', page_zh)
        self.assertIn('Host &lt;A&gt;', page_zh)
        self.assertIn('Pre-outcome rationale &lt;escaped&gt;.', page_zh)
        self.assertIn('Prediction Difficulty Breakdown', page_en)
        self.assertIn('Non-trivial prediction support rate: 50.0% (1/2)', page_en)
        self.assertIn('Prediction Lead-Time / Horizon', page_en)
        self.assertIn('Hard (4/5)', page_en)
        self.assertIn('91–180d', page_en)

    def test_colorful_charts_valid_svg_xml_and_boxplot_threshold(self):
        import re
        for lang in ('zh', 'en'):
            with self.subTest(lang=lang):
                page = renderer.render_report(self.data, lang=lang)
                radar = renderer.render_radar(self.data, standalone=True, lang=lang)
                # Multi-stop gradient & score badges in colorful radar
                self.assertIn('id="radar-mean-fill"', radar)
                self.assertIn('id="radar-mean-stroke"', radar)
                self.assertIn('class="score-badge', radar)
                ET.fromstring(radar)
                # All inline SVGs in the report parse as clean XML with no unsafe elements
                svgs = re.findall(r'<svg\b.*?</svg>', page, flags=re.DOTALL)
                self.assertGreaterEqual(len(svgs), 5)  # stacked verdict, difficulty, histogram, boxplot, radar
                for raw_svg in svgs:
                    root = ET.fromstring(raw_svg)
                    self.assertFalse(any(node.tag.split('}')[-1] in {'script', 'image', 'foreignObject'} for node in root.iter()))
                    self.assertFalse(any(name.lower().startswith('on') for node in root.iter() for name in node.attrib))
                # Stacked verdict breakdown, difficulty chart, histogram, and box plot present
                self.assertIn('id="vb-title"', page)
                self.assertIn('#10B981', page)
                self.assertIn('#F59E0B', page)
                self.assertIn('#F43F5E', page)
                self.assertIn('id="diff-chart-title"', page)
                self.assertIn('viz-trend-line', page)
                self.assertIn('viz-ci', page)
                self.assertIn('id="hor-hist-title"', page)
                self.assertIn('viz-acc-line', page)
                self.assertIn('id="bp-title"', page)
                self.assertIn('viz-mean-diamond', page)

        # Box plot falls back gracefully to empty-state note when <3 dated predictions exist
        sparse = copy.deepcopy(self.data)
        sparse['cases'] = [c for c in sparse['cases'] if c.get('lead_time_days') is None][:2]
        sparse['cases'].append({
            'id': 'C_ONLY1', 'title': 'Single dated', 'claim': 'Only one dated prediction.',
            'claim_type': 'prediction', 'status': 'supported', 'lead_time_days': 45,
            'assessment': 'Supported.', 'evidence_ids': ['S01'],
        })
        page_sparse_zh = renderer.render_report(sparse, lang='zh')
        page_sparse_en = renderer.render_report(sparse, lang='en')
        self.assertNotIn('id="bp-title"', page_sparse_zh)
        self.assertIn('至少 3 条带提前期的预测样本（当前可用：1 条）', page_sparse_zh)
        self.assertNotIn('id="bp-title"', page_sparse_en)
        self.assertIn('at least 3 dated predictions (available: 1)', page_sparse_en)

    def test_five_num_summary_and_english_zero_cjk_leak(self):
        import re
        s = renderer._five_num_summary([10, 20, 30, 40, 50])
        self.assertEqual((s['min'], s['q1'], s['median'], s['q3'], s['max'], s['mean']), (10.0, 20.0, 30.0, 40.0, 50.0, 30.0))
        self.assertIsNone(renderer._five_num_summary([]))

        # Build a clean English data payload and confirm zero CJK characters leak in --lang en
        en_data = copy.deepcopy(self.data)
        en_data['report'].update({
            'title': 'English Audit Report', 'longitudinal_title': 'English Timeline',
            'subject': 'Sample Creator', 'subtitle': 'Subtitle', 'summary': ['Summary line.'],
            'scope_note': 'Scope note.',
        })
        en_data['metrics']['composite']['reason'] = 'Withheld for demo.'
        for m in en_data['panel']['policy']['selected_models']:
            m['display_name'] = f"Model {m['id'].upper()}"
        en_data['panel']['policy']['policy_hash'] = panel.policy_hash(en_data['panel']['policy'])
        for rev in en_data['panel']['reviews'] + [en_data['panel']['judge']]:
            if rev.get('summary'):
                rev['summary'] = 'Judge summary.'
            for dim, rat in rev['rationales'].items():
                if rat.get('rationale'):
                    rat['rationale'] = f'Rationale for {dim}.'
                if rat.get('missing_reason'):
                    rat['missing_reason'] = f'Missing reason for {dim}.'
        en_data['topics'] = [{
            'id': 't1', 'label': 'Topic One', 'summary': 'Summary.', 'assessment': 'Assessment.',
            'entries': [{
                'id': 'E1', 'date': '2024-01-01', 'stance': 'Bullish', 'claim': 'Claim text.',
                'quote': 'Direct quote.', 'context': 'Context.', 'status': 'supported',
                'source_ids': ['S01'], 'evidence_ids': ['E01'],
                'transition': {'kind': 'genuine_change', 'label': 'Updated', 'explanation': 'Explained.'},
            }],
        }]
        en_data['sources'] = [
            {'id': s['id'], 'title': f"Source {s['id']}", 'url': None, 'published_at': s.get('published_at'), 'locator': 'loc', 'excerpt': 'Excerpt.'}
            for s in en_data['sources']
        ]
        en_data['cases'] = [
            {
                'id': c['id'], 'title': f"Case {c['id']}", 'claim': 'Claim text.', 'claim_type': c.get('claim_type'),
                'status': c['status'], 'difficulty': c.get('difficulty'), 'difficulty_score': c.get('difficulty_score'),
                'lead_time_days': c.get('lead_time_days'), 'assessment': 'Assessment.', 'evidence_ids': ['S01'], 'notes': 'Note.',
            }
            for c in en_data['cases']
        ]
        en_data['coverage']['notes'] = ['Coverage note.']
        en_data['costs']['notes'] = ['Cost note.']
        en_data['limitations'] = ['Limitation note.']

        page_en = renderer.render_report(en_data, lang='en')
        radar_en = renderer.render_radar(en_data, standalone=True, lang='en')
        self.assertIsNone(re.search(r'[\u4e00-\u9fff]', page_en), 'Found leaked CJK characters in --lang en HTML')
        self.assertIsNone(re.search(r'[\u4e00-\u9fff]', radar_en), 'Found leaked CJK characters in --lang en SVG')

        # Even if an older frozen rubric lacks label_en/description_en, --lang en must not leak Chinese labels
        legacy_rubric = copy.deepcopy(self.rubric)
        for dim in legacy_rubric['dimensions']:
            dim.pop('label_en', None)
            dim.pop('description_en', None)
        self.rebind_rubric(en_data, legacy_rubric)
        legacy_page_en = renderer.render_report(en_data, lang='en')
        legacy_radar_en = renderer.render_radar(en_data, standalone=True, lang='en')
        self.assertIsNone(re.search(r'[\u4e00-\u9fff]', legacy_page_en), 'Found leaked CJK characters with legacy rubric in --lang en HTML')
        self.assertIsNone(re.search(r'[\u4e00-\u9fff]', legacy_radar_en), 'Found leaked CJK characters with legacy rubric in --lang en SVG')



class SourcingRigorRenderTests(unittest.TestCase):
    def metrics(self):
        import score_claims as scoring
        import test_score_claims as fixtures
        rows = [
            fixtures.claim('p1', claim_type='prediction', citation_status='uncited_specific', citation_text=None),
            fixtures.claim('p2', claim_type='prediction', citation_status='primary_cited', citation_text='Fed Beige Book, 2026-03'),
            fixtures.claim('f1', claim_type='factual', citation_status='secondary_cited', citation_text='据媒体报道'),
            fixtures.claim('f2', claim_type='factual', citation_status='uncited_vague', citation_text=None),
            fixtures.claim('f3', claim_type='factual'),
        ]
        return {'sourcing_rigor': scoring.core_metrics(rows)['sourcing_rigor'],
                'by_claim_type': {ct: scoring.core_metrics([r for r in rows if r['claim_type'] == ct])
                                  for ct in ('factual', 'prediction')}}

    def test_sourcing_svg_is_valid_xml_in_zh_and_en_without_cjk_leaks_in_english(self):
        import re
        import xml.etree.ElementTree as ET
        m = self.metrics()
        for lang in ('zh', 'en'):
            rows = renderer._sourcing_rows(m, renderer.I18N[lang])
            svg = renderer.render_sourcing_rigor_svg(rows, lang=lang)
            root = ET.fromstring(svg)
            self.assertEqual(root.tag, SVG + 'svg')
            fills = {el.get('fill') for el in root.iter(SVG + 'rect') if el.get('fill')}
            for color in ('#10B981', '#0EA5E9', '#F59E0B', '#F43F5E'):
                self.assertIn(color, fills)
            if lang == 'en':
                self.assertIsNone(re.search(r'[\u3400-\u9fff\uff00-\uffef]', svg))
        self.assertIn('出处构成', renderer.render_sourcing_rigor_svg(renderer._sourcing_rows(m, renderer.I18N['zh']), lang='zh'))

    def test_sourcing_section_renders_chips_table_and_legacy_note_in_zh_and_en(self):
        import re
        m = self.metrics()
        zh = renderer.render_sourcing_rigor_section(m, lang='zh')
        self.assertIn('出处与可查证度', zh)
        self.assertIn('张口就来率', zh)
        self.assertIn('<svg', zh)
        en = renderer.render_sourcing_rigor_section(m, lang='en')
        self.assertIn('Sourcing Rigor &amp; Checkability', en)
        self.assertIn('Unsubstantiated rate', en)
        self.assertIn('Primary cited', en)
        self.assertIsNone(re.search(r'[\u3400-\u9fff\uff00-\uffef]', en))
        self.assertIn('chip-rose', en)
        # Legacy ledger: no citation tags -> explicit note, no bar chart, no invented zero rate.
        legacy = renderer.render_sourcing_rigor_section({'sourcing_rigor': {'population_n': 3, 'tagged_n': 0,
                                                                            'counts': {'untagged': 3}}}, lang='en')
        self.assertIn('legacy ledger', legacy)
        self.assertNotIn('<svg', legacy)
        self.assertEqual(renderer.render_sourcing_rigor_section({}, lang='en'), '')

    def test_objective_metrics_places_sourcing_section_for_both_languages(self):
        m = self.metrics()
        html_zh = renderer.objective_metrics({'metrics': m}, lang='zh')
        html_en = renderer.objective_metrics({'metrics': m}, lang='en')
        self.assertIn('出处与可查证度', html_zh)
        self.assertIn('Sourcing Rigor', html_en)


class CredibilityDashboardRenderTests(unittest.TestCase):
    def setUp(self):
        self.data = renderer.load_json(ROOT / 'assets/report-sample.json')

    def full_metrics(self):
        import score_claims as scoring
        import test_score_claims as fixtures
        rows = [
            fixtures.claim('f1', claim_type='factual', outcome='supported', citation_status='primary_cited'),
            fixtures.claim('f2', claim_type='factual', outcome='contradicted', citation_status='uncited_specific'),
            fixtures.claim('f3', claim_type='factual', outcome='mixed', citation_status='secondary_cited'),
            fixtures.claim('p1', first_stated_at='2025-01-01', difficulty='trivial', outcome='supported'),
            fixtures.claim('p2', first_stated_at='2025-01-01', difficulty='hard', outcome='contradicted',
                           certainty_text='我一定会做到'),
        ]
        return scoring.calculate(rows, copy.deepcopy(fixtures.COVERAGE))

    def test_kpi_cards_and_tables_carry_traffic_lights_for_credibility_and_forecasts(self):
        m = self.full_metrics()
        zh = renderer.objective_metrics({'metrics': m}, lang='zh')
        en = renderer.objective_metrics({'metrics': m}, lang='en')
        for page in (zh, en):
            self.assertRegex(page, r'class="tl tl-(green|yellow|red)"')
            self.assertIn('tl-red', page)
            self.assertIn('badge negative', page)
        self.assertIn('事实诚信分', zh)
        self.assertIn('无据传谣率', zh)
        self.assertIn('难度加权预测分', zh)
        self.assertIn('高确信度差距', zh)
        self.assertIn('Misinformation rate', en)
        self.assertIn('Difficulty-adjusted score', en)
        self.assertIsNone(re.search(r'[\u3400-\u9fff]', en))
        self.assertIn('客观事实核查', zh)
        self.assertIn('evidence-backed', en)

    def test_rate_badges_map_error_rates_inverted(self):
        self.assertIn('badge ok', renderer.rate_badge({'value': 0.02, 'numerator': 1, 'denominator': 50}, renderer.I18N['en'], error_rate=True))
        self.assertIn('badge negative', renderer.rate_badge({'value': 0.5, 'numerator': 5, 'denominator': 10}, renderer.I18N['en'], error_rate=True))
        self.assertIn('badge muted', renderer.rate_badge(None, renderer.I18N['en']))

    def test_legacy_metrics_without_new_fields_explain_recompute_instead_of_zeroes(self):
        legacy = {k: v for k, v in self.data['metrics'].items() if k not in {'factual_credibility', 'difficulty_adjusted'}}
        page = renderer.objective_metrics({'metrics': legacy}, lang='en')
        self.assertIn('predates factual credibility', page)
        self.assertNotIn('Factual honesty score', page)

    def test_subjective_ratings_name_every_scoring_model_with_provider_and_average_note(self):
        page = renderer.render_report(self.data, lang='en')
        self.assertIn('Subjective rating', page)
        self.assertIn('Scoring models', page)
        for model in self.data['panel']['policy']['selected_models']:
            if any(r['model_id'] == model['id'] and r['status'] == 'completed' for r in self.data['panel']['reviews']):
                self.assertIn(model['display_name'], page)
                self.assertIn(model['api_model'], page)
        completed = [r for r in self.data['panel']['reviews'] if r['status'] == 'completed']
        expected_note = 'Per-dimension average shown' if len(completed) > 1 else 'Single model scored'
        self.assertIn(expected_note, page)

    def test_all_claims_explorer_is_offline_filterable_and_cards_stay_notable_only(self):
        data = copy.deepcopy(self.data)
        data['cases'].append(copy.deepcopy(data['cases'][0]))
        data['cases'][-1].update({'id': 'clm_quiet_filler', 'claim': 'Quiet filler claim text', 'notable': False,
                                  'status': 'pending', 'citation_status': 'uncited_vague'})
        page = renderer.render_report(data, lang='en')
        self.assertIn('id="explorer"', page)
        self.assertEqual(page.count('<tr data-status='), len(data['cases']))
        self.assertIn('data-unsub="1"', page)
        self.assertIn('data-filter="unsubstantiated"', page)
        self.assertIn('Quiet filler claim text', page)
        notable_cards = sum(1 for case in data['cases'] if case.get('notable', True))
        self.assertEqual(page.count('class="card case '), notable_cards)
        parsed = Tags()
        parsed.feed(page)
        self.assertEqual([tag for tag, _ in parsed.elements].count('script'), 1)
        self.assertIn('data-template="Showing {n} of {total}"', page)
        self.assertNotIn('<script>alert', page)

    def test_explorer_is_absent_from_longitudinal_view_and_empty_without_cases(self):
        data = copy.deepcopy(self.data)
        self.assertNotIn('id="explorer"', renderer.render_report(data, view='longitudinal', lang='en'))
        data['cases'] = []
        self.assertEqual(renderer.render_explorer(data, renderer.I18N['en']), '')


if __name__ == '__main__':
    unittest.main()
