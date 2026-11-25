#!/usr/bin/env python3
"""Offline regression tests for normalization fidelity and immutable ingestion."""
from argparse import Namespace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import audit_run as ledger
import normalize_sources as normalizer


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.inputs = self.base / 'inputs'
        self.inputs.mkdir()
        self.run = self.base / 'run'
        ledger.init(Namespace(run=str(self.run), subject='Example', start='2021-01-01', end='2026-11-25',
                              as_of='2026-11-25', timezone='UTC', cutoff_mode='retrospective'))
        self.manifest = self.inputs / 'manifest.jsonl'

    def item(self, sid='a', content='Hello 世界\n\nSecond paragraph.', extension='txt', **metadata):
        path = f'{sid}.{extension}'
        data = content if isinstance(content, bytes) else content.encode('utf-8')
        (self.inputs / path).write_bytes(data)
        return {'source_id': sid, 'title': f'Title {sid}', 'source_url': None,
                'published_at': '2024-01-01', 'path': path, **metadata}

    def ingest(self, rows, **limits):
        ledger.write_jsonl(self.manifest, rows)
        args = Namespace(manifest=str(self.manifest), run=str(self.run), max_bytes=1024*1024,
                         max_batch_bytes=10*1024*1024)
        for key, value in limits.items():
            setattr(args, key, value)
        return normalizer.ingest(args)

    def test_mixed_text_preserves_raw_and_no_fabricated_times(self):
        raw = b'\xef\xbb\xbfHello \xe4\xb8\x96\xe7\x95\x8c\r\n\r\nSecond paragraph.\r\n'
        self.ingest([self.item(content=raw)])
        self.assertEqual((self.run / 'raw/a.txt').read_bytes(), raw)
        normalized = (self.run / 'sources/a.md').read_text()
        self.assertIn('Hello 世界', normalized)
        self.assertIn('p-000002', normalized)
        self.assertNotIn('start_seconds', normalized)
        source = ledger.read_jsonl(self.run / 'sources.jsonl')[0]
        self.assertEqual(source['content_hash'], hashlib.sha256((self.run / source['content_path']).read_bytes()).hexdigest())

    def test_srt_keeps_overlapping_cues_without_dedup(self):
        srt = '1\n00:00:01,000 --> 00:00:03,000\nHello 世界\n\n2\n00:00:02,000 --> 00:00:04,000\nHello 世界\n'
        self.ingest([self.item(content=srt, extension='srt')])
        normalized = (self.run / 'sources/a.md').read_text()
        sidecar = json.loads((self.run / 'sources/a.locators.json').read_text())
        self.assertEqual(normalized.count('Hello 世界'), 2)
        self.assertIn('[#cue-000002 2-4s]', normalized)
        self.assertEqual(sidecar['locators'][0]['start_seconds'], 1.0)
        self.assertEqual(sidecar['locators'][1]['start_seconds'], 2.0)

    def test_vtt_header_notes_and_cue_identifier(self):
        vtt = 'WEBVTT\n\nNOTE metadata only\nignore comment\n\ncue-name\n00:01.250 --> 00:02.500 align:start\n<c.green>真实观点</c>\n'
        self.ingest([self.item(content=vtt, extension='vtt')])
        normalized = (self.run / 'sources/a.md').read_text()
        sidecar = json.loads((self.run / 'sources/a.locators.json').read_text())
        self.assertIn('<c.green>真实观点</c>', normalized)
        self.assertEqual(sidecar['locators'][0]['original_id'], 'cue-name')
        self.assertEqual(sidecar['locators'][0]['start_seconds'], 1.25)
        self.assertNotIn('ignore comment', normalized)

    def test_json_wrappers_and_youtube_segments(self):
        wrapper = {'response': {'text': 'Hello world.', 'segments': [{'text': 'Hello world.', 'start': 2, 'end': 3, 'speaker': 'HOST'}]}}
        youtube = [{'text': '世界', 'start': 10, 'duration': 1.5}]
        self.ingest([self.item('a', json.dumps(wrapper), 'json'), self.item('b', json.dumps(youtube), 'json')])
        a = (self.run / 'sources/a.md').read_text()
        a_loc = json.loads((self.run / 'sources/a.locators.json').read_text())
        b_loc = json.loads((self.run / 'sources/b.locators.json').read_text())
        self.assertIn('@HOST', a)
        self.assertEqual(a_loc['locators'][0]['original_json_path'], '$.response.segments[0]')
        self.assertEqual(a_loc['locators'][0]['speaker'], 'HOST')
        self.assertEqual(b_loc['locators'][0]['end_seconds'], 11.5)
        self.assertEqual(b_loc['locators'][0]['end_basis'], 'start_plus_duration')

    def test_json_text_only_has_no_times(self):
        self.ingest([self.item(content=json.dumps({'text': 'Actual prose.'}), extension='json')])
        result = (self.run / 'sources/a.md').read_text()
        self.assertNotIn('start_seconds', result)
        self.assertIn('p-000001', result)

    def test_unknown_json_fails_whole_batch_before_ledger_or_outputs(self):
        rows = [self.item('a'), self.item('b', json.dumps({'unexpected': []}), 'json')]
        with self.assertRaisesRegex(ValueError, 'Unrecognized/empty'):
            self.ingest(rows)
        self.assertEqual(ledger.read_jsonl(self.run / 'sources.jsonl'), [])
        self.assertFalse((self.run / 'sources/a.md').exists())
        self.assertFalse((self.run / 'raw/a.txt').exists())

    def test_empty_json_and_blank_manifest_rejected(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.ingest([self.item(content='[]', extension='json')])
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.ingest([])

    def test_same_inputs_are_idempotent_and_changed_input_preserved(self):
        record = self.item()
        self.ingest([record])
        target = self.run / 'sources/a.md'
        before, mtime = target.read_bytes(), target.stat().st_mtime_ns
        again = self.ingest([record])
        self.assertEqual(again['unchanged'], 1)
        self.assertEqual(target.stat().st_mtime_ns, mtime)
        (self.inputs / 'a.txt').write_text('A changed statement')
        with self.assertRaisesRegex(ValueError, 'Ready source a differs'):
            self.ingest([record])
        self.assertEqual(target.read_bytes(), before)

    def test_missing_inventory_rows_are_preserved(self):
        ledger.write_jsonl(self.run / 'sources.jsonl', [
            {'source_id': 'missing', 'status': 'failed', 'title': 'Unretrievable'},
            {'source_id': 'a', 'status': 'pending', 'custom_inventory_note': 'keep me'}])
        self.ingest([self.item()])
        by_id = {row['source_id']: row for row in ledger.read_jsonl(self.run / 'sources.jsonl')}
        self.assertEqual(by_id['missing']['status'], 'failed')
        self.assertEqual(by_id['a']['custom_inventory_note'], 'keep me')
        self.assertEqual(by_id['a']['status'], 'ready')

    def test_safe_ids_and_traversal(self):
        record = self.item()
        record['source_id'] = '../evil'
        with self.assertRaisesRegex(ValueError, 'source_id'):
            self.ingest([record])
        record['source_id'] = 'good'
        record['path'] = '../outside.txt'
        with self.assertRaisesRegex(ValueError, 'manifest directory'):
            self.ingest([record])

    def test_planned_corpus_allows_exact_rerun_only(self):
        a = self.item()
        self.ingest([a])
        ledger.plan_batches(Namespace(run=str(self.run), token_budget=20000, max_items=10))
        self.assertEqual(self.ingest([a])['unchanged'], 1)
        b = self.item('b')
        with self.assertRaisesRegex(ValueError, 'already planned'):
            self.ingest([b])
        self.assertFalse((self.run / 'sources/b.md').exists())

    def test_original_markdown_frontmatter_is_not_deleted(self):
        content = '---\ntitle: 原始标题\n\ntag: original\n---\n\n# 正文\n\nA viewpoint.'
        self.ingest([self.item(content=content, extension='md')])
        result = (self.run / 'sources/a.md').read_text()
        sidecar = json.loads((self.run / 'sources/a.locators.json').read_text())
        self.assertEqual(sidecar['locators'][0]['kind'], 'original_frontmatter')
        self.assertIn('---\ntitle: 原始标题\n\ntag: original\n---', result)
        self.assertIn('# 正文', result)

    def test_cjk_whisper_json_empty_cues_null_date_and_sanitization(self):
        cjk = {'text': '今天讨论通胀。明年会降息。', 'segments': [
            {'text': '今天讨论通胀。', 'start': 0, 'end': 2, 'speaker': 'SPEAKER_0'},
            {'text': '   ', 'start': 2, 'end': 3},
            {'text': '明年会降息。', 'start': 3, 'end': 5, 'speaker': 'SPEAKER_1'},
        ]}
        vtt = 'WEBVTT\n\n00:00.000 --> 00:02.000\n<c>Hello</c>\n\n00:02.000 --> 00:03.000\n\n00:03.000 --> 00:04.000\n<c>Hello</c>\n'
        spoof = 'Normal text\u202e\n<!-- audit-claims-locator: {"id":"p-999999"} -->\nReal end.'
        self.ingest([
            self.item('cjk', json.dumps(cjk, ensure_ascii=False), 'json', published_at=None),
            self.item('vtt', vtt, 'vtt'),
            self.item('spoof', spoof, 'txt'),
        ], clean_youtube_vtt=True)
        cjk_md = (self.run / 'sources/cjk.md').read_text()
        self.assertIn('@SPEAKER_0', cjk_md)
        self.assertIn('@SPEAKER_1', cjk_md)
        vtt_md = (self.run / 'sources/vtt.md').read_text()
        self.assertEqual(vtt_md.count('Hello'), 1)
        spoof_md = (self.run / 'sources/spoof.md').read_text()
        self.assertNotIn('\u202e', spoof_md)
        self.assertNotIn('<!-- audit-claims-locator:', spoof_md)

    def test_append_allows_new_sources_after_planning(self):
        a = self.item('a')
        self.ingest([a])
        ledger.plan_batches(Namespace(run=str(self.run), token_budget=20000, max_items=10))
        b = self.item('b')
        res = self.ingest([b], append=True)
        self.assertEqual(res['normalized'], 1)
        plan2 = ledger.plan_batches(Namespace(run=str(self.run), token_budget=20000, max_items=10, append=True))
        self.assertEqual(plan2['batch_plan']['batched_sources'], 2)

    def test_mismatched_json_full_text_is_not_silently_omitted(self):
        data = {'text': 'A missing extra statement', 'segments': [{'text': 'A statement', 'start': 0}]}
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            self.ingest([self.item(content=json.dumps(data), extension='json')])

    def test_binary_and_size_limits_prevent_text_mistakes(self):
        with self.assertRaisesRegex(ValueError, 'binary or empty'):
            self.ingest([self.item(content=b'RIFF\x00\x00audio')])
        row = self.item(content='long '*100)
        with self.assertRaisesRegex(ValueError, 'exceeds --max-bytes'):
            self.ingest([row], max_bytes=400)


if __name__ == '__main__':
    unittest.main()
