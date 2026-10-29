#!/usr/bin/env python3
"""Read task usage metadata without exporting prompts. Python standard library only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote


def codex(path):
    session_id = None
    usage = None
    receipt_at = None
    model_ids = set()
    with Path(path).expanduser().open() as stream:
        for line in stream:
            event = json.loads(line)
            payload = event.get('payload') or {}
            if event.get('type') == 'session_meta':
                session_id = payload.get('id') or session_id
            if event.get('type') == 'turn_context' and payload.get('model'):
                model_ids.add(payload['model'])
            if event.get('type') == 'event_msg' and payload.get('type') == 'token_count':
                total = (payload.get('info') or {}).get('total_token_usage')
                if total:
                    usage = total
                    receipt_at = event.get('timestamp')
    if not session_id or usage is None:
        raise ValueError('No session identity and cumulative token receipt found')
    counters = {k: usage[k] for k in (
        'input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
        'output_tokens', 'reasoning_output_tokens', 'total_tokens') if k in usage}
    return dict(source='codex_rollout', session_id=session_id, models=sorted(model_ids),
                token_semantics='inclusive; cache subset of input; reasoning subset of output',
                counters=counters, last_receipt_at=receipt_at,
                attribution='own session; cumulative snapshot; model attribution may be mixed')


def opencode(db, session):
    db_path = Path(db).expanduser().resolve()
    connection = sqlite3.connect('file:' + quote(str(db_path), safe='/') + '?mode=ro', uri=True)
    try:
        columns = {r[1] for r in connection.execute('PRAGMA table_info(session_message)')}
        if not {'session_id', 'type', 'data'} <= columns:
            raise ValueError('Unsupported OpenCode schema; inspect the installed version')
        exists = connection.execute('SELECT 1 FROM session_v2 WHERE id=?', (session,)).fetchone()
        if not exists:
            raise ValueError('Session not found; use the exact task-owned session ID')
        counters = dict(input_uncached=0, output_visible=0, reasoning=0, cache_read=0, cache_write=0)
        models = set()
        rows = 0
        missing = 0
        for (raw,) in connection.execute('SELECT data FROM session_message WHERE session_id=? AND type=?', (session, 'assistant')):
            message = json.loads(raw)
            tokens = message.get('tokens')
            if not tokens:
                missing += 1
                continue
            cache = tokens.get('cache') or {}
            values = dict(input_uncached=tokens.get('input'), output_visible=tokens.get('output'),
                          reasoning=tokens.get('reasoning'), cache_read=cache.get('read'), cache_write=cache.get('write'))
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 for value in values.values()):
                raise ValueError('Incomplete/invalid token buckets; cannot safely sum this session')
            for key, value in values.items():
                counters[key] += value
            model = message.get('model') or {}
            models.add('/'.join(str(model.get(k, 'unknown')) for k in ('providerID', 'id', 'variant')))
            rows += 1
        if not rows:
            raise ValueError('No measured assistant receipts in this session')
        return dict(source='opencode_session_message_v2', session_id=session,
                    models=sorted(models), token_semantics='exclusive buckets', counters=counters,
                    attribution='own session; measured assistant receipts only; excludes descendants',
                    measured_receipts=rows, unmeasured_assistant_records=missing)
    finally:
        connection.close()


def difference(before_path, after_path):
    before, after = [json.loads(Path(p).read_text()) for p in (before_path, after_path)]
    for key in ('source', 'session_id', 'token_semantics'):
        if before[key] != after[key]:
            raise ValueError('Snapshots have different ' + key)
    if before.get('scope') != 'session_snapshot' or after.get('scope') != 'session_snapshot':
        raise ValueError('Delta requires two cumulative session snapshots')
    if after['captured_at'] <= before['captured_at']:
        raise ValueError('After snapshot must be later than before snapshot')
    if before['counters'].keys() != after['counters'].keys():
        raise ValueError('Counter coverage changed; do not infer missing counts')
    counters = {key: after['counters'][key] - value for key, value in before['counters'].items()}
    if any(value < 0 for value in counters.values()):
        raise ValueError('Counters reset/decreased; use exact task turns instead')
    warnings = []
    if before.get('last_receipt_at') and before.get('last_receipt_at') == after.get('last_receipt_at'):
        warnings.append('No new receipt timestamp; unchanged counters do not prove zero task usage.')
    if before.get('unmeasured_assistant_records', 0) or after.get('unmeasured_assistant_records', 0):
        warnings.append('Unmeasured assistant records exist. Counts cover measured receipts only; late historical receipts can affect attribution.')
    return dict(source=after['source'], session_id=after['session_id'], scope='task_delta',
                token_semantics=after['token_semantics'], counters=counters,
                interval=dict(start=before['captured_at'], end=after['captured_at']),
                models=sorted(set(before['models']) | set(after['models'])),
                warnings=warnings,
                attribution='Valid only if this interval contains solely the assigned task; excludes descendants. Models list covers session history, not per-model delta.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('codex'); c.add_argument('--path', required=True)
    o = sub.add_parser('opencode'); o.add_argument('--db', required=True); o.add_argument('--session', required=True)
    d = sub.add_parser('diff'); d.add_argument('before'); d.add_argument('after')
    args = parser.parse_args()
    try:
        if args.command == 'codex':
            result = codex(args.path)
        elif args.command == 'opencode':
            result = opencode(args.db, args.session)
        else:
            result = difference(args.before, args.after)
        if args.command != 'diff':
            result.update(scope='session_snapshot', captured_at=datetime.now(timezone.utc).isoformat())
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, sqlite3.Error, KeyError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
