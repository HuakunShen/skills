#!/usr/bin/env python3
"""Offline JSONL/SQLite reference adapters; other backends use their chosen connector."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import audit_run as ledger

TABLES = {
    'sources': ('sources.jsonl', 'source_id', []),
    'claims': ('claims.jsonl', 'claim_id', []),
    'occurrences': ('occurrences.jsonl', 'occurrence_id', ['source_id', 'claim_id']),
    'evidence': ('evidence.jsonl', 'evidence_id', []),
    'review_votes': ('review_votes.jsonl', 'vote_id', ['claim_id']),
    'decisions': ('decisions.jsonl', 'decision_id', ['claim_id']),
    'tasks': ('tasks.jsonl', 'task_id', []),
    'cost_events': ('costs.jsonl', 'cost_event_id', []),
    'source_access': ('source_access.jsonl', 'access_id', ['source_id']),
    'media_assets': ('media_assets.jsonl', 'media_id', ['source_id']),
}
MEDIA_EXTENSIONS = {'wav', 'mp3', 'm4a', 'flac', 'ogg', 'oga', 'opus', 'aac', 'mp4', 'webm', 'mkv',
                    'mov', 'm4v', 'avi', 'wmv', 'mpeg', 'mpg', 'aiff', 'aif', 'caf', 'wma', 'pcm', 'amr'}
IGNORE_HEADER = '# audit-claims: metadata may be versioned; media and local state must stay outside Git'


def encode(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def reject_constant(value):
    raise ValueError('Non-finite JSON is not supported: ' + value)


def strict_json(text):
    return json.loads(text, parse_constant=reject_constant)


def load_policy(run):
    value = strict_json((run / 'config/storage-policy.json').read_text(encoding='utf-8'))
    if value.get('schema_version') != 1 or value.get('local_reference_adapter', value.get('backend')) not in {'jsonl', 'sqlite'}:
        raise ValueError('This helper needs a jsonl/sqlite local reference adapter; use the chosen backend connector otherwise')
    if not isinstance(value.get('canonical_backend', value.get('source_of_truth')), str):
        raise ValueError('Storage policy needs canonical_backend')
    return value


def media_root(run, policy):
    stored = policy['media']['root']
    return (run / stored).resolve() if not Path(stored).is_absolute() else Path(stored).resolve()


def ignore_patterns():
    insensitive = lambda ext: ''.join('[' + c.lower() + c.upper() + ']' if c.isalpha() else c for c in ext)
    return ['/media', '/.coordinator.lock', '.env', '.env.*', '/.cache/', '/cache/', '/tmp/', '/temp/',
            '__pycache__/', '*.pyc', '*.tmp', '*.part', '.DS_Store', '*.sqlite', '*.sqlite3', '*.db',
            '*.sqlite-*', '*.sqlite3-*', '*.db-*'] + ['*.' + insensitive(ext) for ext in sorted(MEDIA_EXTENSIONS)]


def append_ignores(run):
    path = run / '.gitignore'
    if path.is_symlink():
        raise ValueError('Do not rewrite a symlinked .gitignore')
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    missing = [line for line in ignore_patterns() if line not in original.splitlines()]
    if missing:
        text = original + ('\n' if original and not original.endswith('\n') else '') + '\n' + IGNORE_HEADER + '\n' + '\n'.join(missing) + '\n'
        ledger.atomic_text(path, text)


def git(run, *arguments):
    return subprocess.run(['git', '-C', str(run), *arguments], capture_output=True, check=False)


def check(run):
    run = Path(run).resolve()
    policy = load_policy(run)
    root = media_root(run, policy)
    issues, warnings = [], []
    if not root.is_dir():
        issues.append('Configured media root is missing or not a directory')
    link = run / 'media'
    if policy['media']['symlink']:
        if not link.is_symlink() or link.resolve() != root:
            issues.append('run/media no longer matches the authorized media symlink')
    elif policy['media']['root'] == 'media' and link.is_symlink():
        issues.append('Local media directory unexpectedly became a symlink')
    if not shutil.which('git'):
        return {'ok': not issues, 'issues': issues, 'warnings': ['Git is unavailable; tracking/ignores were not verified'], 'git_repository': False, 'media_root': str(root)}
    repo = git(run, 'rev-parse', '--show-toplevel')
    if repo.returncode:
        return {'ok': not issues, 'issues': issues, 'warnings': ['Run is not in a Git worktree; .gitignore is ready for later use'], 'git_repository': False, 'media_root': str(root)}
    repository = Path(os.fsdecode(repo.stdout).strip()).resolve()
    tracked = git(run, 'ls-files', '-z', '--', '.')
    if tracked.returncode:
        issues.append('Could not inspect tracked paths')
        names = []
    else:
        names = [os.fsdecode(part) for part in tracked.stdout.split(b'\0') if part]
    dangerous = []
    for name in names:
        path = Path(name)
        lower = path.name.lower()
        if (name == 'media' or name.startswith('media/') or path.suffix.lstrip('.').lower() in MEDIA_EXTENSIONS
                or lower.endswith(('.sqlite', '.sqlite3', '.db', '.sqlite-wal', '.sqlite-shm', '.sqlite3-wal', '.sqlite3-shm', '.db-wal', '.db-shm'))
                or lower == '.env' or lower.startswith('.env.')):
            dangerous.append(name)
    if dangerous:
        issues.append('Already tracked media/database/secret paths remain tracked despite ignore rules')
    sentinels = ['media', 'media/ignore-check.mp3', '.env', '.env.local', 'state/audit.sqlite',
                 'state/audit.sqlite-wal', 'state/audit.sqlite-shm', 'temporary-test.Mp3', 'tmp/check.part']
    if link.is_symlink():
        sentinels.remove('media/ignore-check.mp3')  # Git refuses paths beyond a symlink; the link itself must be ignored.
    not_ignored = [name for name in sentinels if git(run, 'check-ignore', '--no-index', '-q', '--', name).returncode != 0]
    if not_ignored:
        issues.append('Some required media/state/secret paths are not ignored')
    external_tracked = []
    if policy['media']['root'] != 'media' and root.is_relative_to(repository):
        relative = root.relative_to(repository).as_posix()
        external = git(repository, 'ls-files', '-z', '--', relative)
        external_tracked = [os.fsdecode(part) for part in external.stdout.split(b'\0') if part]
        if external.returncode:
            issues.append('Could not inspect the external media root in this Git worktree')
        if external_tracked:
            issues.append('Configured external media root contains tracked files')
        if git(repository, 'check-ignore', '--no-index', '-q', '--', relative).returncode != 0:
            issues.append('External media root is inside this Git worktree but is not ignored; configure its owner-level ignore rule')
    return {'ok': not issues, 'issues': issues, 'warnings': warnings, 'git_repository': True,
            'tracked_sensitive_paths': dangerous, 'unignored_test_paths': not_ignored,
            'external_tracked_paths': external_tracked, 'media_root': str(root),
            'cloud_upload_verified': False}


def init(args):
    if args.backend not in {'jsonl', 'sqlite'}:
        raise ValueError('This local reference helper implements jsonl/sqlite only; use your connector or AI adapter for postgres, notion, sheets, obsidian or custom storage (see storage-adapters.md)')
    run = Path(args.run).resolve()
    if args.link_media and not args.media_root:
        raise ValueError('--link-media requires an explicitly supplied existing --media-root')
    external = Path(args.media_root).expanduser().resolve() if args.media_root else None
    if external is not None and not external.is_dir():
        raise ValueError('--media-root must be an existing directory, such as an already mounted drive')
    proposed = {'schema_version': 1, 'backend': args.backend, 'local_reference_adapter': args.backend,
        'canonical_backend': args.backend, 'working_format': 'jsonl', 'presentation_backend': None,
        'source_of_truth': 'sqlite' if args.backend == 'sqlite' else 'jsonl',
        'media': {'root': str(external) if external is not None else 'media',
                  'explicit_external_root': external is not None, 'symlink': bool(args.link_media),
                  'retention': 'keep', 'automatic_deletion': False, 'automatic_upload': False},
        'sqlite': {'database': 'state/audit.sqlite', 'jsonl_role': 'staging_and_snapshots' if args.backend == 'sqlite' else 'canonical',
                   'binary_database_in_git': False},
        'git': {'text_versioning': 'optional', 'media_must_be_ignored': True, 'automatic_add_commit_push': False}}
    with ledger.coordinator_lock(run):
        config_path = ledger.inside(run, 'config/storage-policy.json')
        if config_path.exists():
            if load_policy(run) != proposed:
                raise ValueError('Storage policy already exists with different selections; preserve it and make an explicit reviewed migration')
        link = run / 'media'
        if args.link_media:
            if os.path.lexists(link):
                if not link.is_symlink() or link.resolve() != external:
                    raise ValueError('run/media already exists with another target/type; nothing was replaced')
            else:
                try:
                    link.symlink_to(external, target_is_directory=True)
                except OSError as exc:
                    raise ValueError('Cannot create media symlink; on Windows enable symlink privileges or omit --link-media and use the configured path directly') from exc
        elif external is None:
            if link.is_symlink() or (link.exists() and not link.is_dir()):
                raise ValueError('run/media is not an ordinary local directory; nothing was replaced')
            link.mkdir(exist_ok=True)
        if not config_path.exists():
            ledger.write_json(config_path, proposed)
        selection = ledger.inside(run, 'config/storage-selection.md')
        if not selection.exists():
            ledger.atomic_text(selection, '# Storage selections and remaining decisions\n\n'
                f'- Canonical metadata backend selected for this local reference adapter: `{args.backend}`.\n'
                '- Supported architectural choices: JSONL, SQLite, Postgres, Notion databases, Sheets tabs, Obsidian Markdown, or a custom backend.\n'
                '- Existing local helper commands implement JSONL/SQLite only; use the chosen connector or AI adapter for other backends.\n'
                '- Working snapshot format for bundled scripts: JSONL; this does not make JSONL the canonical database.\n'
                '- Optional presentation backend: record separately; it need not be the canonical backend.\n'
                f'- Media location: `{str(external) if external else "run/media"}`.\n'
                f'- Optional run/media symlink: `{bool(args.link_media)}`.\n'
                '- Retention: keep media; no automatic deletion or cloud upload.\n'
                '- Text versioning: optional Git; no automatic add, commit or push.\n\n'
                'Before large acquisition, record the user\'s choices: local or mounted media directory; '
                'available disk space; keep originals after verified transcription or an explicitly authorized retention policy; '
                'whether text snapshots should be versioned; who may access any synced directory. '
                'An existing mounted Google Drive path is only a filesystem destination; this helper does not verify upload/sync.\n\n'
                'With SQLite canonical, export a consistent JSONL staging view, run JSONL-oriented helpers, '
                'then transactionally import the reviewed results. Never edit two independent masters. '
                'Keep a live SQLite database local; synchronize immutable text snapshots rather than concurrently editing a database through sync software.\n')
        append_ignores(run)
    return {'initialized': True, 'policy_path': str(config_path), 'validation': check(run)}


def database_path(run, value):
    path = ledger.inside(run, value or 'state/audit.sqlite')
    if path.suffix.lower() not in {'.sqlite', '.sqlite3', '.db'}:
        raise ValueError('Use a run-relative .sqlite, .sqlite3 or .db path')
    return path


def read_table(path, key, table):
    rows, seen = [], set()
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        row = strict_json(line)
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key]:
            raise ValueError(f'{path.name}:{number}: nonempty {key} required')
        if row[key] in seen:
            raise ValueError(f'{path.name}: duplicate {key}')
        seen.add(row[key])
        version = row.get('schema_version', 1)
        if type(version) is not int or version < 1:
            raise ValueError(f'{path.name}:{number}: positive schema_version required')
        if table == 'media_assets' and any(k in row for k in ('media_bytes', 'data_base64', 'audio_base64', 'video_base64', 'blob')):
            raise ValueError('media_assets stores paths, hashes and retention metadata, not media bytes')
        rows.append(row)
    return rows


def import_jsonl(args):
    run = Path(args.run).resolve()
    with ledger.coordinator_lock(run):
        policy = load_policy(run)
        path = database_path(run, args.database)
        prepared = {}
        for table, (filename, key, edges) in TABLES.items():
            input_path = ledger.inside(run, filename)
            if input_path.exists():
                prepared[table] = read_table(input_path, key, table)
        if not prepared:
            raise ValueError('No canonical JSONL ledgers found')
        schema = (Path(__file__).resolve().parent.parent / 'assets/storage.sql').read_text(encoding='utf-8')
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        try:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=5000')
            connection.executescript(schema)
            connection.execute('BEGIN IMMEDIATE')
            for table, rows in prepared.items():
                filename, key, edges = TABLES[table]
                connection.execute(f'DELETE FROM {table}')
                columns = ['id', 'schema_version', *edges, 'payload_json']
                sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
                for row in rows:
                    values = [row[key], row.get('schema_version', 1)]
                    for edge in edges:
                        value = row.get(edge)
                        if value is not None and (not isinstance(value, str) or not value):
                            raise ValueError(f'{table}.{edge} must be a nonempty ID or null')
                        values.append(value)
                    connection.execute(sql, [*values, encode(row)])
            connection.execute('INSERT OR REPLACE INTO storage_metadata(key,value_json) VALUES (?,?)',
                ('last_import', encode({'at': datetime.now(timezone.utc).isoformat(), 'backend': policy['backend'],
                                       'table_counts': {table: len(rows) for table, rows in prepared.items()}})))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    return {'database': str(path), 'imported_tables': {table: len(rows) for table, rows in prepared.items()},
            'absent_ledgers': 'unchanged', 'source_of_truth': policy['source_of_truth'], 'media_opened': False}


def export_jsonl(args):
    run = Path(args.run).resolve()
    destination = Path(args.out).expanduser().resolve()
    if destination.exists() or os.path.lexists(destination):
        raise ValueError('Snapshot destination already exists; use a new directory')
    with ledger.coordinator_lock(run):
        policy = load_policy(run)
        path = database_path(run, args.database)
        if not path.is_file():
            raise ValueError('Database does not exist')
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix='.audit-snapshot-', dir=destination.parent))
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            connection.execute('BEGIN')
            manifest = {}
            for table, (filename, key, edges) in TABLES.items():
                rows = [strict_json(row[0]) for row in connection.execute(f'SELECT payload_json FROM {table} ORDER BY id')]
                content = ''.join(encode(row) + '\n' for row in rows)
                ledger.atomic_text(temporary / filename, content)
                manifest[filename] = {'records': len(rows), 'sha256': digest_bytes(content.encode('utf-8'))}
            connection.commit()
            ledger.write_json(temporary / 'storage-snapshot.json', {'schema_version': 1,
                'created_at': datetime.now(timezone.utc).isoformat(), 'source_of_truth': policy['source_of_truth'],
                'files': manifest, 'snapshot_hash': digest_bytes(encode(manifest).encode('utf-8')),
                'includes_media_bytes': False})
            os.rename(temporary, destination)
        except Exception:
            connection.rollback()
            shutil.rmtree(temporary)
            raise
        finally:
            connection.close()
    return {'snapshot': str(destination), 'files': manifest, 'includes_media_bytes': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('init')
    create.add_argument('--run', required=True)
    create.add_argument('--backend', default='jsonl', help='Local reference adapter: jsonl/sqlite; other canonical backends use their chosen connector')
    create.add_argument('--media-root')
    create.add_argument('--link-media', action='store_true')
    inspect = commands.add_parser('check')
    inspect.add_argument('--run', required=True)
    for name in ('import-jsonl', 'export-jsonl'):
        sub = commands.add_parser(name)
        sub.add_argument('--run', required=True)
        sub.add_argument('--database', help='Run-relative database file; default state/audit.sqlite')
        if name == 'export-jsonl':
            sub.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = init(args)
        elif args.command == 'check':
            result = check(args.run)
        elif args.command == 'import-jsonl':
            result = import_jsonl(args)
        else:
            result = export_jsonl(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        valid = result.get('ok', result.get('validation', {}).get('ok', True))
        return 0 if valid else 2
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
