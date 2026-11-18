#!/usr/bin/env python3
"""Store prepared work summaries. No network, credentials, transcripts, or discovery."""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import project_scope as projects
from platform_io import private_dir, open_read, secure, file_lock, assert_private, check_path

VERSION = '0.3.4'
# In an installed skills tree, resolve the store from that explicit installation.
_skill_home = Path(__file__).resolve().parents[3]
DEFAULT_STORE = (_skill_home if _skill_home.name == '.codex' or _skill_home.joinpath('skills/work-checkpoint/scripts/checkpoint.py') == Path(__file__).resolve()
                 else Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))) / 'checkpoints'
FIELDS = ('task_id', 'project', 'goal', 'status', 'repo', 'branch', 'commit',
          'decisions', 'tests', 'deployment', 'blocker', 'owner', 'next_step',
          'resume_point', 'attention', 'observed_at', 'machine_id', 'chat_id',
          'parent_chat_id', 'package_version', 'project_id', 'workstream_id', 'disclosure', 'artifacts')
REQUIRED = ('task_id', 'project', 'goal', 'status', 'next_step', 'resume_point')
STATUSES = {'working', 'blocked', 'needs_input', 'ready_for_review', 'complete', 'paused'}


def timestamp(value):
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps require a timezone')
    return parsed


def read(path):
    fd = open_read(path)
    with os.fdopen(fd, encoding='utf-8') as f:
        return json.load(f)


def write(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            secure(Path(temporary))
            f.write(value if isinstance(value, str) else json.dumps(value, indent=2) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def stdin_json(limit=32768):
    raw = sys.stdin.buffer.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Prepared input exceeds its bounded size limit')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def validate(value):
    if set(value) - set(FIELDS):
        raise ValueError('Unknown checkpoint fields')
    for key in REQUIRED:
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError('Missing string field: ' + key)
    if value['status'] not in STATUSES:
        raise ValueError('Unsupported work status')
    for key, item in value.items():
        if key == 'artifacts':
            if not isinstance(item, list):
                raise ValueError('Artifacts must be an array')
        elif key in ('decisions', 'tests'):
            if not isinstance(item, list) or any(not isinstance(x, str) for x in item):
                raise ValueError(key + ' must be an array of strings')
        elif key == 'attention':
            allowed = {'current_focus', 'deadline', 'action', 'reason', 'switch_when'}
            if not isinstance(item, dict) or set(item) - allowed or any(not isinstance(x, str) for x in item.values()):
                raise ValueError('Invalid attention fields')
        elif not isinstance(item, str):
            raise ValueError(key + ' must be a string')
    if 'observed_at' in value:
        timestamp(value['observed_at'])
    if 'machine_id' in value and not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', value['machine_id']):
        raise ValueError('Machine ID must be an explicit short label')
    for key in ('chat_id', 'parent_chat_id'):
        if key in value and not re.fullmatch(r'(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})', value[key]):
            raise ValueError(key + ' must be an actual supported chat ID')
    if 'chat_id' in value and value['task_id'] != value['chat_id']:
        raise ValueError('Use the actual chat ID as task_id when chat_id is known')
    serialized = json.dumps(value)
    if re.search(r'-----BEGIN .*PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})', serialized):
        raise ValueError('Possible credential detected; sanitize the summary')


def markdown(record):
    lines = ['Checkpoint ID: ' + record['id'], '', 'Recorded at: ' + record['recorded_at'], '']
    for key, item in record['summary'].items():
        label = key.replace('_', ' ').capitalize()
        if isinstance(item, list):
            lines += [label + ':', ''] + ['- ' + (x if isinstance(x, str) else json.dumps(x, sort_keys=True)) for x in item] + ['']
        elif isinstance(item, dict):
            lines += [label + ':', ''] + ['- ' + k.replace('_', ' ') + ': ' + v for k, v in item.items()] + ['']
        else:
            lines += [label + ': ' + item, '']
    return '\n'.join(lines).rstrip() + '\n'


def record_path(store, ident):
    if not re.fullmatch(r'[a-f0-9]{64}', ident or ''):
        raise ValueError('Invalid checkpoint ID')
    return store / 'records' / (ident + '.json')


def identity_complete(summary):
    # Preserve reported identity in immutable records; placeholders cannot prove it.
    machine, chat = summary.get('machine_id'), summary.get('chat_id')
    return (isinstance(machine, str) and machine.strip().casefold() != 'unknown'
            and bool(machine.strip()) and isinstance(chat, str)
            and re.fullmatch(r'[a-f0-9-]{32,36}', chat) is not None)


def update_index(store, selected=None):
    records = [read(p) for p in sorted((store / 'records').glob('*.json'))]
    if selected and any(r.get('profile_binding') != projects.binding(selected) for r in records):
        raise ValueError('Store contains another project destination; reconcile without exporting')
    items = [{key: r[key] for key in ('id', 'recorded_at', 'sha256', 'delivery')} |
             {key: r['summary'][key] for key in ('task_id', 'project', 'goal', 'status', 'next_step')} |
             {key: r['summary'].get(key) for key in ('machine_id', 'chat_id', 'parent_chat_id', 'package_version', 'observed_at')} |
             {'identity_complete': identity_complete(r['summary'])} |
             ({key: r['summary'].get(key) for key in ('project_id', 'workstream_id', 'disclosure', 'repo', 'commit', 'owner', 'artifacts')} |
              {'profile_binding': r.get('profile_binding'), 'consumer_events': r.get('consumer_events', [])} if selected else {})
             for r in records]
    index = {'schema_version': 2, 'producer_version': VERSION, 'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'checkpoints': sorted(items, key=lambda r: (r['recorded_at'], r['id']))}
    if selected:
        index.update(schema_version=3, profile_binding=projects.binding(selected), workstreams=projects.workstreams(index['checkpoints']))
    write(store / 'index.json', index)
    return index


def freshness(index, task_id=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    groups = {}
    for item in index['checkpoints']:
        if task_id and item['task_id'] != task_id:
            continue
        # Labels and missing machine IDs remain explicitly unverified, never inferred.
        key = (item.get('machine_id'), item['task_id'])
        groups.setdefault(key, []).append(item)
    tasks = []
    for (machine, task), items in sorted(groups.items(), key=lambda x: str(x[0])):
        latest = max(items, key=lambda x: (x['recorded_at'], x['id']))
        published = [x for x in items if x['delivery']['state'] == 'published']
        last_published = max(published, key=lambda x: (x['recorded_at'], x['id'])) if published else None
        age = max(0, (now - timestamp(latest['recorded_at'])).total_seconds())
        observed = latest.get('observed_at')
        try:
            evidence_age = round(max(0, (now - timestamp(observed)).total_seconds()) / 60, 1) if observed else None
            evidence_timestamp_valid = True if observed else None
        except (ValueError, TypeError):
            evidence_age, evidence_timestamp_valid = None, False
        tasks.append({'machine_id': machine, 'task_id': task,
                      'identity_complete': identity_complete(latest),
                      'latest_checkpoint_id': latest['id'], 'status': latest['status'],
                      'recorded_at': latest['recorded_at'], 'checkpoint_age_minutes': round(age / 60, 1),
                      'observed_at': observed,
                      'evidence_age_minutes': evidence_age, 'evidence_timestamp_valid': evidence_timestamp_valid,
                      'delivery_state': latest['delivery']['state'],
                      'latest_published_id': last_published['id'] if last_published else None,
                      'delivery_gap': latest['delivery']['state'] != 'published',
                      'review_due_if_work_changed': latest['status'] == 'working' and age >= 1800,
                      'next_step': latest['next_step']})
    return {'generated_at': now.isoformat(), 'producer_version': VERSION, 'tasks': tasks,
            'cadence': 'Milestones promptly; about 30 minutes only during changed active work; no idle wakeups'}


def notice(item, now=None):
    if not identity_complete(item):
        return None
    age = ((now or datetime.datetime.now(datetime.timezone.utc)) - timestamp(item['recorded_at'])).total_seconds()
    reason = ('Latest prepared checkpoint has not been verified as published.' if item['delivery']['state'] != 'published' else (
        'Review whether active work changed since the last checkpoint.' if item['status'] == 'working' and age >= 1800 else None))
    if reason is None:
        return None
    token = hashlib.sha256(json.dumps([reason, item['id'], item['delivery']['state']]).encode()).hexdigest()
    return reason, token


def stop_check(store, event):
    if event.get('hook_event_name') != 'Stop':
        raise ValueError('Expected a Stop event')
    # Never use cwd, transcript_path, last_assistant_message, or arbitrary event text.
    session = event.get('session_id')
    if not isinstance(session, str) or not re.fullmatch(r'[a-f0-9-]{32,36}', session):
        return {}
    # Entire hook is read-only, including when no store/checkpoint exists. Never mkdir,
    # chmod, lock/create files, refresh the index, or follow a payload-supplied path.
    check_path(store)
    path = store / 'index.json'
    if not path.exists():
        return {}
    assert_private(path)
    items = [x for x in read(path)['checkpoints'] if x.get('chat_id') == session and x.get('machine_id')]
    if not items:
        return {}
    latest = max(items, key=lambda x: (x['recorded_at'], x['id']))
    reminder = notice(latest)
    if reminder is None or latest['delivery'].get('notice_token') == reminder[1]:
        return {}
    return {'systemMessage': 'Work checkpoint reminder: ' + reminder[0] + ' Use prepared summaries and the normal private Page readback workflow at the next safe opportunity. Do not repeat an already reported issue to the user. This reminder does not publish, block stopping, or authorize another action.'}


@contextlib.contextmanager
def lock(store):
    private_dir(store)
    private_dir(store / 'records')
    private_dir(store / 'markdown')
    with file_lock(store / '.lock'):
        yield


def run(args):
    if args.profile:
        assert_private(Path(args.profile))
    selected = projects.profile(read(Path(args.profile))) if args.profile else None
    base_store = Path(args.store)
    store = base_store / 'profiles' / selected['profile_id'] if selected else base_store
    if args.command == 'session-start':
        event = stdin_json()
        if event.get('hook_event_name') != 'SessionStart':
            raise ValueError('Expected a SessionStart event')
        # Only our installed skill is read. Payload paths and text are never opened.
        skill = Path(__file__).resolve().parents[1] / 'SKILL.md'
        invocation = [sys.executable, str(Path(__file__).resolve()), '--store', str(base_store)]
        if selected:
            invocation += ['--profile', str(Path(args.profile).absolute())]
        ident = event.get('session_id')
        identity = '\nActual chat ID from SessionStart: ' + ident if isinstance(ident, str) and re.fullmatch(r'[a-f0-9-]{32,36}', ident) else '\nActual chat ID was not supplied in this hook event.'
        return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': skill.read_text(encoding='utf-8') + '\nExact helper invocation (argument array): ' + json.dumps(invocation) + identity}}
    if args.command == 'stop-check':
        if selected and (store / 'profile-binding.json').exists() and read(store / 'profile-binding.json') != projects.binding(selected):
            raise ValueError('Profile changed; use a new profile ID or reconcile explicitly')
        return stop_check(store, stdin_json())
    with lock(store):
        if selected:
            binding_file = store / 'profile-binding.json'
            if binding_file.exists():
                if read(binding_file) != projects.binding(selected):
                    raise ValueError('Profile changed; use a new profile ID or reconcile explicitly')
            elif any((store / 'records').glob('*.json')):
                raise ValueError('Existing records lack a matching project binding; reconcile explicitly')
            else:
                write(binding_file, projects.binding(selected))
        if args.command == 'prepare':
            summary = stdin_json()
            validate(summary)
            if selected:
                projects.validate_summary(summary, selected)
            elif projects.PROJECT_FIELDS.intersection(summary):
                raise ValueError('Project fields require an explicit --profile; no personal fallback')
            ident = projects.digest({'summary': summary, 'profile_binding': projects.binding(selected)}) if selected else projects.digest(summary)
            path = record_path(store, ident)
            if path.exists():
                record = read(path)
            else:
                record = {'id': ident, 'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'summary': summary, 'delivery': {'state': 'pending'}}
            if selected:
                record['profile_binding'] = projects.binding(selected)
            body = markdown(record)
            record['sha256'] = hashlib.sha256(body.encode()).hexdigest()
            write(store / 'markdown' / (ident + '.md'), body)
            write(path, record)
            update_index(store, selected)
            return {'id': ident, 'sha256': record['sha256'], 'file': str(store / 'markdown' / (ident + '.md')), 'delivery': record['delivery']}
        if args.command == 'index':
            return update_index(store, selected)
        if args.command == 'status':
            return freshness(update_index(store, selected), args.task_id)
        if args.command == 'pending':
            records = [read(p) for p in sorted((store / 'records').glob('*.json'))]
            return [{'id': r['id'], 'project': r['summary']['project'], 'status': r['summary']['status'], 'delivery': r['delivery']} for r in records if r['delivery']['state'] != 'published']
        if args.command == 'destination':
            if selected:
                return selected
            path = store / 'destination.json'
            return read(path) if path.exists() else {'configured': False}
        if args.command == 'set-destination':
            if selected:
                raise ValueError('Project destination is bound by the explicit profile; do not change it implicitly')
            value = stdin_json()
            if set(value) != {'page_id', 'url', 'owner_only'} or value['owner_only'] is not True or not isinstance(value['page_id'], str) or not re.fullmatch(r'https://(?:chatgpt\.com|chat\.openai\.com)/[^\s]+', value['url']):
                raise ValueError('Destination requires a verified private Page and canonical URL')
            path = store / 'destination.json'
            if path.exists() and read(path) != value:
                raise ValueError('Destination already configured; reconcile explicitly')
            write(path, value)
            return value
        if args.command == 'import':
            if not selected:
                raise ValueError('Bridge import requires an explicit project profile')
            imported = stdin_json(65536)
            if set(imported) != {'id', 'recorded_at', 'summary', 'sha256', 'profile_binding', 'delivery'} or imported['delivery'] != {'state': 'pending'}:
                raise ValueError('Import only a pending prepared record, never reset publishing or uncertain state')
            validate(imported['summary']); projects.validate_summary(imported['summary'], selected)
            if imported['profile_binding'] != projects.binding(selected) or imported['id'] != projects.digest({'summary': imported['summary'], 'profile_binding': projects.binding(selected)}):
                raise ValueError('Imported checkpoint belongs to another profile or summary')
            timestamp(imported['recorded_at'])
            if timestamp(imported['recorded_at']) > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
                raise ValueError('Imported capture is in the future')
            if hashlib.sha256(markdown(imported).encode()).hexdigest() != imported['sha256']:
                raise ValueError('Imported checkpoint digest mismatch')
            path = record_path(store, imported['id'])
            if path.exists():
                previous = read(path)
                if previous['sha256'] != imported['sha256'] or previous.get('profile_binding') != imported['profile_binding']:
                    raise ValueError('Existing revision differs; reconcile before importing')
                return {'id': previous['id'], 'delivery': previous['delivery'], 'imported': False}
            write(path, imported); write(store / 'markdown' / (imported['id'] + '.md'), markdown(imported))
            update_index(store, selected)
            return {'id': imported['id'], 'delivery': imported['delivery'], 'imported': True}
        path = record_path(store, args.id)
        record = read(path)
        if record.get('profile_binding') != (projects.binding(selected) if selected else None):
            raise ValueError('Checkpoint destination/profile changed; reconcile without rerouting')
        state = record['delivery']['state']
        if args.command == 'show':
            return {**record, 'markdown': markdown(record)}
        if args.command == 'export':
            if not selected or state != 'pending':
                raise ValueError('Export only pending project records to the designated publisher')
            return {k: record[k] for k in ('id', 'recorded_at', 'summary', 'sha256', 'profile_binding')} | {'delivery': {'state': 'pending'}}
        if args.command == 'claim':
            if state != 'pending':
                return {'claimed': False, 'delivery': record['delivery']}
            checked = projects.claim_proof(stdin_json(), selected) if selected else {}
            record['delivery'] = {'state': 'publishing', 'attempts': record['delivery'].get('attempts', 0) + 1, **checked}
        elif args.command == 'uncertain':
            if state != 'publishing':
                raise ValueError('Only an active publication can become uncertain')
            record['delivery']['state'] = 'uncertain'
        elif args.command == 'release':
            if state != 'publishing':
                raise ValueError('Only a definitely rejected publication can be released')
            record['delivery']['state'] = 'pending'
        elif args.command == 'ack':
            receipt = stdin_json()
            if state not in ('publishing', 'uncertain'):
                raise ValueError('Checkpoint has no active or uncertain publication')
            if selected:
                receipt = projects.receipt(receipt, selected, record)
            elif set(receipt) != {'page_id', 'url', 'sha256', 'owner_only', 'content_verified'} or receipt['sha256'] != record['sha256'] or receipt['owner_only'] is not True or receipt['content_verified'] is not True or not isinstance(receipt['page_id'], str) or not re.fullmatch(r'https://(?:chatgpt\.com|chat\.openai\.com)/[^\s]+', receipt['url']):
                raise ValueError('Receipt requires matching content and verified owner-only access')
            record['delivery'].update({'state': 'published', **receipt})
        elif args.command == 'consume':
            if not selected or state != 'published':
                raise ValueError('Consumer evidence requires a published project revision')
            event = stdin_json()
            required = {'kind', 'actor', 'at', 'sha256', 'evidence'}
            allowed = required | {'artifact_id', 'artifact_sha256'}
            if not required.issubset(event) or set(event) - allowed or any(not isinstance(v, str) or not v.strip() for v in event.values()):
                raise ValueError('Consumer evidence requires actor, time, exact revision and supporting reference')
            if event['sha256'] != record['sha256'] or event['kind'] not in ('read', 'acted', 'artifact_read'):
                raise ValueError('Consumer event belongs to another revision or kind')
            timestamp(event['at'])
            if timestamp(event['at']) > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
                raise ValueError('Consumer event timestamp is in the future')
            if event['kind'] == 'artifact_read':
                artifacts = [a for a in record['summary'].get('artifacts', []) if a['artifact_id'] == event.get('artifact_id') and a['sha256'] == event.get('artifact_sha256') and a['state'] == 'uploaded']
                if not artifacts:
                    raise ValueError('Artifact read needs its own uploaded artifact and matching byte digest')
            elif set(event) != required:
                raise ValueError('Artifact fields belong only to artifact_read evidence')
            events = record.setdefault('consumer_events', [])
            if event not in events:
                events.append(event)
        elif args.command == 'note':
            reminder = notice({**record['summary'], **record})
            if reminder:
                record['delivery']['notice_token'] = reminder[1]
        record['delivery']['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(path, record)
        update_index(store, selected)
        return {'id': record['id'], 'claimed': args.command == 'claim', 'delivery': record['delivery']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', default=str(DEFAULT_STORE))
    parser.add_argument('--profile', help='Exact approved project-profile JSON path; no automatic discovery')
    parser.add_argument('--task-id', help='Limit status to an exact task/chat ID')
    parser.add_argument('command', choices=['session-start', 'stop-check', 'prepare', 'pending', 'index', 'status', 'show', 'claim', 'uncertain', 'release', 'ack', 'note', 'destination', 'set-destination', 'export', 'import', 'consume'])
    parser.add_argument('id', nargs='?')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
