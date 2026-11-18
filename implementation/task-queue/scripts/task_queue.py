#!/usr/bin/env python3
"""Single-arbiter file task queues. No network, subprocess task execution or transcripts."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import platform_io as io
import queue_history as history

VERSION = '0.1.2'
UTC = dt.timezone.utc
TERMINAL = {'completed', 'cancelled'}
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,159}')
TASK_FIELDS = {'id', 'scope', 'project_id', 'kind', 'action', 'owner', 'consumer', 'due_at', 'due_date',
               'timezone', 'timing', 'dependencies', 'source_refs', 'observed_at', 'authority',
               'acceptance', 'scheduler', 'project_safe'}


def now():
    return dt.datetime.now(UTC)


def stamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def label(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Invalid explicit ID')
    return value


def strings(value, nonempty=False):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value) or (nonempty and not value):
        raise ValueError('Expected array of nonempty strings')
    return value


def read(path):
    return json.loads(history.raw_read(path))


def write(path, value):
    history.atomic_bytes(path, history.encoded(value))


def config(value):
    required = {'schema_version', 'queue_id', 'scope', 'project_id', 'arbiter_id',
                'coordinators', 'destination', 'approved_audience'}
    if not isinstance(value, dict) or set(value) != required or value['schema_version'] != 1:
        raise ValueError('Explicit queue config schema 1 required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',value['queue_id']):
        raise ValueError('Queue ID must be a portable directory label')
    label(value['arbiter_id']); label(value['project_id'])
    strings(value['coordinators'], True)
    if value['scope'] not in ('personal', 'project'):
        raise ValueError('Unsupported scope')
    dest = value['destination']
    if set(dest) != {'page_id', 'space_id', 'url'} or not re.fullmatch(r'page_[a-f0-9]{32}', dest['page_id']) or dest['url'] != 'https://chatgpt.com/space/' + dest['page_id']:
        raise ValueError('Exact destination Page required')
    if value['scope'] == 'project' and not re.fullmatch(r'page_space_[a-f0-9]{32}', dest['space_id'] or ''):
        raise ValueError('Project Space required')
    if value['scope'] == 'personal' and dest['space_id'] is not None:
        raise ValueError('Personal queue requires owner-private destination')
    grants = value['approved_audience']
    if not isinstance(grants, list) or not grants or any(set(g) != {'principal_type', 'principal_id', 'role'} or g['principal_type'] not in ('user', 'group', 'workspace') for g in grants):
        raise ValueError('Explicit native audience required')
    if value['scope'] == 'personal' and (len(grants) != 1 or grants[0]['role'] != 'owner'):
        raise ValueError('Personal audience must be owner-only')
    return value


def validate_task(t, c):
    if set(t) - TASK_FIELDS:
        raise ValueError('Unknown task fields; review disclosure')
    for k in ('id', 'action', 'owner', 'consumer', 'kind'):
        if not isinstance(t.get(k), str) or not t[k].strip():
            raise ValueError('Missing task ' + k)
    label(t['id'])
    if t.get('scope') != c['scope'] or t.get('project_id') != c['project_id']:
        raise ValueError('Task scope/project must match assigned queue')
    if c['scope'] == 'project' and t.get('project_safe') is not True:
        raise ValueError('Explicit project-safe disclosure required')
    strings(t.get('acceptance'), True); strings(t.get('source_refs'), True)
    strings(t.get('dependencies', []))
    if t['id'] in t.get('dependencies', []):
        raise ValueError('Task cannot depend on itself')
    a = t.get('authority')
    if not isinstance(a, dict) or set(a) != {'requirements', 'allowed_actions', 'approval_state'} or a['approval_state'] not in ('pending', 'granted'):
        raise ValueError('Explicit authority/approval requirements required')
    strings(a['requirements'], True); strings(a['allowed_actions'], True)
    if t.get('observed_at'):
        stamp(t['observed_at'])
    if t.get('due_at'):
        due = stamp(t['due_at']); zone = ZoneInfo(t.get('timezone', 'America/New_York'))
        if due.utcoffset() != due.astimezone(zone).utcoffset():
            raise ValueError('Due-time offset does not match declared timezone')
        if t.get('timing') not in ('exact', 'approximate', 'deadline'):
            raise ValueError('Due time needs exact/approximate/deadline timing')
    elif t.get('timing') not in (None, 'unspecified'):
        raise ValueError('No invented clock time for an unscheduled task')
    if t.get('due_date'):
        dt.date.fromisoformat(t['due_date'])
        if t.get('due_at'):raise ValueError('Choose due date or exact time, not both')
    # Producers remain responsible for semantic privacy review.
    if re.search(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})|-----BEGIN .*PRIVATE KEY-----', json.dumps(t)):
        raise ValueError('Possible credential in task')
    return copy.deepcopy(t)


class Queue:
    def __init__(self, store, cfg):
        self.c = config(cfg)
        self.root = Path(store) / label(cfg['queue_id'])
        self.path = self.root / 'state.json'

    def empty(self):
        return {'schema_version': 1, 'binding': digest(self.c), 'queue_id': self.c['queue_id'],
                'revision': 0, 'tasks': {}, 'mirrors': {}, 'events': [], 'operations': {}, 'publications': {}}

    def state(self):
        io.check_path(self.root)
        raw = history.raw_read(self.path) if self.path.exists() else None
        self._state_bytes = len(raw) if raw is not None else 0
        value = history.hydrate(self.root, json.loads(raw)) if raw is not None else self.empty()
        if value['binding'] != digest(self.c):
            raise ValueError('Frozen queue binding changed; reconcile, never redirect')
        return value

    def apply(self, request, arbiter, at=None, dry_run=False):
        if arbiter != self.c['arbiter_id']:
            raise ValueError('Only designated arbiter/store may commit transitions')
        at = at or now()
        label(request['operation_id'])
        if not isinstance(request.get('actor'), str) or not request['actor'].strip():
            raise ValueError('Verified actor assertion required')
        if not isinstance(request.get('evidence'), str) or not request['evidence'].strip():
            raise ValueError('Transition evidence required')
        if dry_run:
            if not self.path.exists():
                raise ValueError('Preflight requires an existing assigned queue')
        else:
            io.private_dir(self.root)
        with io.file_lock(self.root / 'queue.lock'):
            history.assert_writable(self)
            s = self.state()
            old = s['operations'].get(request['operation_id'])
            if old is None:
                prior = history.previous_operation(self, request['operation_id'], s)
                old = prior['record'] if prior else None
            if old:
                if old['digest'] != digest(request):
                    raise ValueError('Operation ID reused with different content')
                result=copy.deepcopy(old['result'])
                current=s['tasks'].get(result['id'])
                if current and current['revision'] != result.get('revision'):
                    result.pop('claim',None)
                    result.update(historical_result=True,current_revision=current['revision'],current_status=current['status'])
                elif result.get('claim') and stamp(result['claim']['expires_at'])<=at:
                    result['claim'].pop('token',None);result['claim_expired']=True
                if dry_run:
                    return dict(history.capacity_for(self, s), preflight=True, replay=True)
                return result
            result = self.transition(s, request, at)
            s['revision'] += 1
            event = {'queue_revision': s['revision'], 'at': at.isoformat(), 'actor': request['actor'],
                     'operation': request['op'], 'operation_id': request['operation_id'],
                     'task_id': result['id'], 'task_revision': result.get('revision'),
                     'evidence': request['evidence']}
            s['events'].append(event)
            result = copy.deepcopy(result)
            s['operations'][request['operation_id']] = {'digest': digest(request), 'result': result}
            if dry_run:
                return dict(history.capacity_for(self, s), preflight=True, replay=False)
            history.save(self.path, s)
            return result

    def transition(self, s, r, at):
        op, actor = r['op'], r['actor']
        coordinator = actor in self.c['coordinators']
        if op == 'request':
            if not coordinator:
                raise ValueError('Only configured coordinator may queue a reconciled request')
            t = validate_task(r['task'], self.c)
            if t['id'] in s['tasks'] or t['id'] in s['mirrors']:
                raise ValueError('Task already exists; use expected revision, never replace')
            t.update(status='requested', revision=1, ack=None, accepted=None, claim=None, completion=None,
                     created_at=at.isoformat(), updated_at=at.isoformat(), blocked_reason=None)
            s['tasks'][t['id']] = t
            return t
        if op == 'mirror':
            if not coordinator or self.c['scope'] != 'personal':
                raise ValueError('Mirrors are private reference-only views')
            m = r['mirror']; label(m['id']); label(m['authority_queue_id'])
            if set(m) != {'id', 'authority_queue_id', 'authority_url'} or m['authority_queue_id'] == self.c['queue_id'] or not m['authority_url'].startswith('https://chatgpt.com/space/page_'):
                raise ValueError('Mirror must reference another authoritative queue')
            if m['id'] in s['tasks'] or m['id'] in s['mirrors']:
                raise ValueError('Existing task/mirror cannot be overwritten')
            s['mirrors'][m['id']] = dict(m, executable=False)
            return s['mirrors'][m['id']]
        ident = label(r['id'])
        if ident in s['mirrors']:
            raise ValueError('Mirror is not executable; use its authoritative arbiter')
        t = s['tasks'][ident]
        if r.get('expected_revision') != t['revision']:
            raise ValueError('Revision conflict; reread human/coordinator changes')
        if t['status'] in TERMINAL:
            raise ValueError('Terminal task cannot be reopened by a retry')
        receipt = {'actor': actor, 'at': at.isoformat(), 'evidence': r['evidence']}
        consumer = actor == t['consumer']
        if op == 'ack':
            if not consumer or t['status'] not in ('requested', 'acknowledged'):
                raise ValueError('Only intended consumer acknowledges a pending request')
            t['ack'] = receipt; t['status'] = 'acknowledged'
        elif op == 'accept':
            if not consumer or t['status'] != 'acknowledged':
                raise ValueError('Consumer must acknowledge before accepting')
            t['accepted'] = receipt; t['status'] = 'accepted'
        elif op == 'claim':
            if not consumer or t['status'] != 'accepted' or t['authority']['approval_state'] != 'granted' or not r.get('authority_evidence'):
                raise ValueError('Accepted task and current independent authority evidence required')
            review=r.get('input_review',{})
            if review.get('queue_page_id')!=self.c['destination']['page_id'] or review.get('human_requests_reconciled') is not True or not review.get('evidence') or not 0 <= (at-stamp(review.get('reviewed_at',''))).total_seconds() <= 300:
                raise ValueError('Fresh native queue/human-request reconciliation required before claim')
            if any(s['tasks'].get(dep, {}).get('status') != 'completed' for dep in t.get('dependencies', [])):
                raise ValueError('Dependencies unsatisfied or unknown')
            seconds = r.get('lease_seconds', 900)
            if not isinstance(seconds, int) or isinstance(seconds, bool) or not 30 <= seconds <= 3600:
                raise ValueError('Lease must be between 30 and 3600 seconds')
            t['claim'] = dict(receipt, token=secrets.token_hex(24), expires_at=(at + dt.timedelta(seconds=seconds)).isoformat(),
                              authority_evidence=r['authority_evidence'])
            t['status'] = 'in_progress'
        elif op == 'complete':
            claim = t.get('claim') or {}
            if not consumer or t['status'] != 'in_progress' or r.get('claim_token') != claim.get('token') or stamp(claim['expires_at']) <= at:
                raise ValueError('Current unexpired claim token required')
            evidence = r.get('acceptance_evidence')
            if not isinstance(evidence, dict) or set(evidence) != set(t['acceptance']) or any(not isinstance(v, str) or not v.strip() for v in evidence.values()) or r.get('acceptance_verified') is not True:
                raise ValueError('Explicit evidence and acceptance verification for every criterion required')
            t['completion'] = dict(receipt, acceptance_evidence=evidence); t['status'] = 'completed'; t['claim'] = None
        elif op == 'block':
            if not (coordinator or consumer) or not isinstance(r.get('reason'), str) or not r['reason'].strip():
                raise ValueError('Consumer/coordinator and block reason required')
            t['blocked_reason'] = r['reason']; t['status'] = 'blocked'
            # Preserve any outstanding execution token until explicit recovery.
        elif op == 'recover':
            if not coordinator or t['status'] not in ('in_progress', 'blocked') or r.get('prior_execution_stopped') is not True or not r.get('reconciliation_evidence'):
                raise ValueError('Coordinator reconciliation and confirmed stopped execution required')
            t['claim'] = None; t['status'] = 'requested'; t['accepted'] = None; t['ack'] = None
            t['blocked_reason'] = None
        elif op == 'cancel':
            if not coordinator:
                raise ValueError('Only coordinator cancels')
            t['status'] = 'cancelled'; t['cancelled'] = receipt
            t['execution_stop_required'] = bool(t.get('claim')); t['claim'] = None
        elif op == 'edit':
            if not coordinator or t.get('claim') or t['status'] not in ('requested', 'acknowledged', 'accepted', 'blocked'):
                raise ValueError('Reconcile/stop outstanding execution before editing')
            patch = r['patch']
            if not isinstance(patch, dict) or set(patch) - (TASK_FIELDS - {'id', 'scope', 'project_id'}):
                raise ValueError('Cannot change stable identity/scope')
            core = {k:v for k,v in t.items() if k in TASK_FIELDS}; core.update(patch)
            validate_task(core, self.c); t.update(patch)
            t['status'] = 'requested'; t['ack'] = None; t['accepted'] = None
        else:
            raise ValueError('Unsupported transition')
        t['revision'] += 1; t['updated_at'] = at.isoformat()
        return t

    def snapshot(self, at=None):
        s = self.state(); at = at or now()
        # Strip live claim tokens, internal operation retries and authority assertions.
        public = copy.deepcopy({k:s[k] for k in ('schema_version', 'queue_id', 'revision', 'tasks', 'mirrors', 'events')})
        for t in public['tasks'].values():
            if t.get('claim'):
                t['claim'] = {k:v for k,v in t['claim'].items() if k not in ('token', 'authority_evidence')}
        public['arbiter_id'] = self.c['arbiter_id']; public['generated_at'] = at.isoformat()
        public['scope'] = self.c['scope']; public['project_id'] = self.c['project_id']
        public['destination'] = self.c['destination']
        public['snapshot_id'] = digest(public)
        return public

    def check(self, consumer=None, at=None):
        at = at or now(); s = self.state(); items = []
        for t in s['tasks'].values():
            if t['status'] in TERMINAL or (consumer and t['consumer'] != consumer):
                continue
            due = stamp(t['due_at']) if t.get('due_at') else None
            items.append({'id':t['id'], 'revision':t['revision'], 'action':t['action'],
                          'status':t['status'], 'due_at':t.get('due_at'), 'due_date':t.get('due_date'),
                          'overdue':bool((due and due < at) or (t.get('due_date') and dt.date.fromisoformat(t['due_date']) < at.astimezone(ZoneInfo(t.get('timezone','America/New_York'))).date())),
                          'claim_expired':bool(t.get('claim') and stamp(t['claim']['expires_at']) <= at),
                          'blocked_reason':t.get('blocked_reason'), 'consumer':t['consumer']})
        return {'queue_id':self.c['queue_id'], 'revision':s['revision'], 'items':items,
                'mirrors':list(s['mirrors'].values()), 'cached_local_view':True,
                'storage':history.capacity(self._state_bytes),
                'frozen':(self.root/'FROZEN-SEGMENT.json').exists()}


def access(c, proof, page_id, at=None):
    at = at or now()
    required = {'page_id', 'space_id', 'audience', 'observed_at', 'complete'}
    if not isinstance(proof, dict) or set(proof) != required or proof['complete'] is not True or proof['page_id'] != page_id or proof['space_id'] != c['destination']['space_id']:
        raise ValueError('Complete native access proof required')
    age = (at - stamp(proof['observed_at'])).total_seconds()
    if not 0 <= age <= 300 or sorted(proof['audience'], key=digest) != sorted(c['approved_audience'], key=digest):
        raise ValueError('Stale or changed audience; do not publish')


def publication(q, op, value):
    io.private_dir(q.root)
    with io.file_lock(q.root / 'queue.lock'):
        history.assert_writable(q)
        s = q.state()
        if op == 'prepare-publication':
            snapshot = q.snapshot(); md = '# Task queue snapshot\n\n```json\n' + json.dumps(snapshot, indent=2) + '\n```\n'
            ident = snapshot['snapshot_id']
            # Snapshot capture happens once; repeated preparation at same queue revision deduplicates.
            found = next((p for p in s['publications'].values() if p['revision'] == s['revision']), None)
            if found:
                return found
            record = {'id':ident, 'revision':s['revision'], 'markdown':md, 'sha256':hashlib.sha256(md.encode()).hexdigest(), 'state':'pending'}
            s['publications'][ident] = record
        else:
            record = s['publications'][value['id']]
            if op == 'claim-publication':
                access(q.c, value['access'], q.c['destination']['page_id'])
                if record['state'] != 'pending':
                    raise ValueError('Not pending: reconcile prior publication; never blind retry')
                if record['revision'] != s['revision']:
                    raise ValueError('Snapshot superseded by task changes; prepare current revision')
                record['state'] = 'publishing'
            elif op == 'uncertain-publication':
                if record['state'] != 'publishing':
                    raise ValueError('Only publishing can become uncertain')
                record['state'] = 'uncertain'
            elif op == 'ack-publication':
                if record['state'] not in ('publishing', 'uncertain'):
                    raise ValueError('Publication not claimable')
                if value.get('content_verified') is not True or value.get('sha256') != record['sha256'] or value.get('parent_page_id') != q.c['destination']['page_id'] or value.get('url') != 'https://chatgpt.com/space/' + value['page_id']:
                    raise ValueError('Exact child readback receipt required')
                access(q.c, value['access'], value['page_id'])
                record.update(state='published', receipt={k:v for k,v in value.items() if k!='id'})
            else:
                raise ValueError('Unsupported publication transition')
        history.save(q.path, s)
        return record


def hook(routes_path, payload, start=False):
    # Only session_id/cwd are examined; transcript_path and assistant content are ignored.
    if not routes_path.exists():
        return {}
    routes = read(routes_path)
    if routes.get('enabled') is not True:
        return {}
    cwd = payload.get('cwd'); selected = []
    if isinstance(cwd, str) and Path(cwd).is_absolute():
        absolute = os.path.abspath(cwd)
        if os.name == 'nt':
            absolute = os.path.normcase(absolute)
        for route in routes['projects']:
            prefixes = route['folder_prefixes']
            if os.name == 'nt':
                # Windows folder identity is case/slash insensitive; keep this lexical.
                prefixes = [os.path.normcase(os.path.abspath(p)) for p in prefixes]
            if any(absolute == p or absolute.startswith(p.rstrip(os.sep) + os.sep) for p in prefixes):
                selected.append(route)
    if len(selected) > 1:
        return {'systemMessage':'Task queue route is ambiguous; select an explicit workstream before pickup.'}
    route = selected[0] if selected else routes.get('default')
    if not route:
        return {}
    c = config(read(Path(route['config']))); q = Queue(route['store'], c)
    result = q.check(consumer=None if start else payload.get('session_id', '__unverified__'))
    if start:
        skill = Path(__file__).parents[1] / 'SKILL.md'
        text = skill.read_text() + '\n\nAssigned queue: ' + c['destination']['url'] + '\nExact config: ' + route['config'] + '\nPrivate store: ' + route['store']
        text += '\nRead the latest native Page snapshot and human requests before acting. Local cache is not current cloud state. Pending count: ' + str(len(result['items']))
        text += '\nLocal storage pressure: ' + result['storage']['pressure'] + '; remaining bytes: ' + str(result['storage']['remaining_bytes'])
        if result['frozen']:
            text += '\nThis segment is frozen: reconcile the verified successor route before any write.'
        return {'hookSpecificOutput':{'hookEventName':'SessionStart', 'additionalContext':text}}
    if result['frozen']:
        return {'systemMessage':'Assigned queue segment is frozen. Reconcile the verified successor route; do not write or repeat unchanged notices.'}
    if result['storage']['pressure'] != 'normal':
        return {'systemMessage':'Task queue storage pressure is ' + result['storage']['pressure'] + '. Inspect storage-status and preflight at a safe boundary; no automatic migration or cap increase. Do not repeat unchanged notices.'}
    if result['items']:
        return {'systemMessage':'Task queue has ' + str(len(result['items'])) + ' nonterminal items for this exact chat. Read the assigned current queue before pickup; do not repeat unchanged notices or execute without a claim and independent authority.'}
    return {}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path); p.add_argument('--store', type=Path)
    p.add_argument('--routes', type=Path)
    p.add_argument('--arbiter'); p.add_argument('--consumer')
    p.add_argument('command', choices=['apply','check','snapshot','prepare-publication','claim-publication','uncertain-publication','ack-publication','session-start','hook-check','migrate-history','verify-history','restore-history','storage-status','preflight'])
    a = p.parse_args()
    try:
        data = None
        if a.command not in ('check','snapshot','prepare-publication','verify-history','storage-status'):
            raw = sys.stdin.buffer.read(131073)
            if len(raw)>131072:
                raise ValueError('Input exceeds bounded size')
            data = json.loads(raw or '{}')
        if a.command in ('session-start','hook-check'):
            routes = a.routes or Path(__file__).resolve().parents[3] / 'checkpoints/task-queues/routes.json'
            expected = 'SessionStart' if a.command=='session-start' else 'Stop'
            if data.get('hook_event_name') != expected:
                raise ValueError('Unexpected hook event')
            result = hook(routes, data, a.command=='session-start')
        else:
            if not a.config or not a.store:
                raise ValueError('Exact assigned config/store required')
            q = Queue(a.store, read(a.config))
            if a.command=='migrate-history': result=history.migrate(q,data,a.arbiter)
            elif a.command=='restore-history': result=history.restore(q,data,a.arbiter)
            elif a.command=='verify-history': result=history.verify(q)
            elif a.command=='storage-status': result=history.status(q)
            elif a.command=='preflight': result=q.apply(data,a.arbiter,dry_run=True)
            elif a.command=='apply': result=q.apply(data,a.arbiter)
            elif a.command=='check': result=q.check(a.consumer)
            elif a.command=='snapshot': result=q.snapshot()
            else:
                if a.arbiter != q.c['arbiter_id']:
                    raise ValueError('Only arbiter publishes authoritative snapshots')
                result=publication(q,a.command,data)
        print(json.dumps(result,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print('Task queue: '+str(e),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
