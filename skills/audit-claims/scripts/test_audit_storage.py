#!/usr/bin/env python3
"""Offline storage/Git boundary and transactional round-trip checks."""
from argparse import Namespace
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

import audit_storage as storage
import audit_run as ledger
import normalize_sources


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / 'run'

    def init(self, backend='jsonl', media=None, link=False):
        return storage.init(Namespace(run=str(self.run), backend=backend,
                                      media_root=str(media) if media else None, link_media=link))

    def import_rows(self, database=None):
        return storage.import_jsonl(Namespace(run=str(self.run), database=database))

    def export(self, out):
        return storage.export_jsonl(Namespace(run=str(self.run), database=None, out=str(out)))

    def git(self, *args, input=None):
        return subprocess.run(['git', '-C', str(self.base), *args], input=input, capture_output=True, check=True)

    def track(self, path):
        # Only this temporary test repository; avoid any add/commit/push commands.
        value = self.git('hash-object', '-w', '--stdin', input=(self.base / path).read_bytes()).stdout.decode().strip()
        self.git('update-index', '--add', '--cacheinfo', f'100644,{value},{path}')

    def test_defaults_retain_media_and_do_not_overwrite_selections(self):
        result = self.init()
        self.assertTrue(result['initialized'])
        media = self.run / 'media'
        media.joinpath('keep.mp3').write_bytes(b'original media bytes')
        selection = self.run / 'config/storage-selection.md'
        selection.write_text('User edited choices')
        self.init()
        self.assertEqual(selection.read_text(), 'User edited choices')
        self.assertEqual(media.joinpath('keep.mp3').read_bytes(), b'original media bytes')
        self.assertFalse(storage.load_policy(self.run)['media']['automatic_deletion'])

    def test_different_policy_is_not_silently_overwritten(self):
        self.init()
        original = (self.run / 'config/storage-policy.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.init('sqlite')
        self.assertEqual((self.run / 'config/storage-policy.json').read_bytes(), original)

    def test_explicit_external_symlink_does_not_copy_or_delete_media(self):
        external = self.base / 'mounted-drive'
        external.mkdir()
        external.joinpath('episode.mp3').write_bytes(b'media')
        self.init(media=external, link=True)
        self.assertTrue((self.run / 'media').is_symlink())
        self.assertEqual((self.run / 'media').resolve(), external.resolve())
        self.assertEqual(external.joinpath('episode.mp3').read_bytes(), b'media')
        self.assertFalse(storage.check(self.run)['git_repository'])

    def test_unapproved_root_and_link_collisions_fail_without_replacement(self):
        with self.assertRaisesRegex(ValueError, 'existing directory'):
            self.init(media=self.base / 'missing', link=True)
        self.run.mkdir()
        (self.run / 'media').write_text('valuable original file')
        external = self.base / 'mounted'
        external.mkdir()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.init(media=external, link=True)
        self.assertEqual((self.run / 'media').read_text(), 'valuable original file')
        self.assertFalse((self.run / 'config/storage-policy.json').exists())

    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_git_ignores_media_symlink_binary_extensions_and_database(self):
        self.git('init', '-q')
        external = self.base.parent / (self.base.name + '-external')
        external.mkdir()
        self.addCleanup(shutil.rmtree, external)
        self.init(media=external, link=True)
        check = storage.check(self.run)
        self.assertTrue(check['ok'], check)
        self.assertEqual(check['unignored_test_paths'], [])

    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_already_tracked_media_is_detected_despite_ignores(self):
        self.git('init', '-q')
        self.run.mkdir()
        (self.run / 'media').mkdir()
        (self.run / 'media/audio.mp3').write_bytes(b'audio')
        self.track('run/media/audio.mp3')
        self.init()
        check = storage.check(self.run)
        self.assertFalse(check['ok'])
        self.assertIn('media/audio.mp3', check['tracked_sensitive_paths'])
        self.assertEqual((self.run / 'media/audio.mp3').read_bytes(), b'audio')

    def test_jsonl_sqlite_roundtrip_preserves_full_records(self):
        self.init('sqlite')
        source = {'source_id': 's', 'title': '中文', 'custom': {'language': ['zh', 'en']}}
        claim = {'claim_id': 'c', 'details': [1, {'unknown_future_field': True}]}
        occurrence = {'occurrence_id': 'o', 'source_id': 's', 'claim_id': 'c', 'original_quote': '原话'}
        media = {'media_id': 'm', 'source_id': 's', 'path_or_uri': 'media/never-open.mp3',
                 'sha256': 'a'*64, 'size_bytes': 999, 'retention': 'keep', 'deletion_history': []}
        ledger.write_jsonl(self.run / 'sources.jsonl', [source])
        ledger.write_jsonl(self.run / 'claims.jsonl', [claim])
        ledger.write_jsonl(self.run / 'occurrences.jsonl', [occurrence])
        ledger.write_jsonl(self.run / 'media_assets.jsonl', [media])
        result = self.import_rows()
        self.assertFalse(result['media_opened'])
        out = self.base / 'snapshot-001'
        self.export(out)
        self.assertEqual(ledger.read_jsonl(out / 'sources.jsonl'), [source])
        self.assertEqual(ledger.read_jsonl(out / 'claims.jsonl'), [claim])
        self.assertEqual(ledger.read_jsonl(out / 'occurrences.jsonl'), [occurrence])
        self.assertEqual(ledger.read_jsonl(out / 'media_assets.jsonl'), [media])
        self.assertFalse((out / 'media').exists())
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.export(out)

    def test_duplicate_ids_fail_preflight_without_changing_database(self):
        self.init('sqlite')
        ledger.write_jsonl(self.run / 'sources.jsonl', [{'source_id': 'original'}])
        self.import_rows()
        ledger.write_jsonl(self.run / 'sources.jsonl', [{'source_id': 'new'}, {'source_id': 'new'}])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.import_rows()
        with sqlite3.connect(self.run / 'state/audit.sqlite') as conn:
            self.assertEqual(conn.execute('SELECT id FROM sources').fetchall(), [('original',)])

    def test_foreign_key_failure_rolls_back_every_imported_table(self):
        self.init('sqlite')
        ledger.write_jsonl(self.run / 'sources.jsonl', [{'source_id': 'original'}])
        self.import_rows()
        ledger.write_jsonl(self.run / 'sources.jsonl', [{'source_id': 'replacement'}])
        ledger.write_jsonl(self.run / 'occurrences.jsonl', [{'occurrence_id': 'o', 'source_id': 'missing'}])
        with self.assertRaises(sqlite3.IntegrityError):
            self.import_rows()
        with sqlite3.connect(self.run / 'state/audit.sqlite') as conn:
            self.assertEqual(conn.execute('SELECT id FROM sources').fetchall(), [('original',)])
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM occurrences').fetchone()[0], 0)

    def test_absent_ledgers_are_preserved_and_explicit_empty_ledger_clears_table(self):
        self.init('sqlite')
        ledger.write_jsonl(self.run / 'sources.jsonl', [{'source_id': 's'}])
        ledger.write_jsonl(self.run / 'claims.jsonl', [{'claim_id': 'c'}])
        self.import_rows()
        (self.run / 'claims.jsonl').unlink()
        self.import_rows()
        with sqlite3.connect(self.run / 'state/audit.sqlite') as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM claims').fetchone()[0], 1)
        ledger.write_jsonl(self.run / 'claims.jsonl', [])
        self.import_rows()
        with sqlite3.connect(self.run / 'state/audit.sqlite') as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM claims').fetchone()[0], 0)

    def test_database_override_cannot_escape_run(self):
        self.init('sqlite')
        ledger.write_jsonl(self.run / 'sources.jsonl', [])
        with self.assertRaisesRegex(ValueError, 'inside'):
            self.import_rows('../outside.sqlite')

    def test_language_list_normalizes_without_relaxing_input_path_confinement(self):
        ledger.init(Namespace(run=str(self.run), subject='subject', start='2025-01-01', end='2026-11-25',
                              as_of='2026-11-25', timezone='UTC', cutoff_mode='retrospective'))
        inputs = self.base / 'inputs'
        inputs.mkdir()
        (inputs / 'text.txt').write_text('Hello 世界')
        record = {'source_id': 's', 'title': 'Multilingual', 'source_url': None,
                  'published_at': '2025-03-01', 'path': 'text.txt', 'language': ['zh', 'en']}
        row, _, _ = normalize_sources.normalize(record, inputs, self.run, ledger.config(self.run), 1000)
        self.assertEqual(row['language'], ['zh', 'en'])
        record['path'] = '../outside.txt'
        with self.assertRaisesRegex(ValueError, 'manifest directory'):
            normalize_sources.normalize(record, inputs, self.run, ledger.config(self.run), 1000)


if __name__ == '__main__':
    unittest.main()
