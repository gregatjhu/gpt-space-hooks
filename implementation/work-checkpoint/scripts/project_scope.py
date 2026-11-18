"""Explicit project disclosure policy and receipts. No discovery or network calls."""
import datetime
import hashlib
import json
import re

PROJECT_FIELDS = {'project_id', 'workstream_id', 'disclosure', 'artifacts'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def stamp(value):
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed


def audience(value):
    if not isinstance(value, list) or not value:
        raise ValueError('Explicit nonempty approved audience is required')
    result = []
    for grant in value:
        if not isinstance(grant, dict) or set(grant) != {'principal_type', 'principal_id', 'role'}:
            raise ValueError('Audience requires typed principals and exact native roles')
        if grant['principal_type'] not in ('user', 'group', 'workspace'):
            raise ValueError('Anonymous/link audiences are unsupported')
        if any(not isinstance(v, str) or not v.strip() for v in grant.values()):
            raise ValueError('Invalid audience principal or role')
        result.append(grant)
    result.sort(key=lambda g: (g['principal_type'], g['principal_id'], g['role']))
    if len({digest(g) for g in result}) != len(result):
        raise ValueError('Duplicate audience grants')
    return result


def profile(value):
    required = {'schema_version', 'kind', 'profile_id', 'project_id', 'space_id',
                'parent_page_id', 'url', 'approved_audience', 'publisher_id'}
    if not isinstance(value, dict) or set(value) != required or value['schema_version'] != 1 or value['kind'] != 'project':
        raise ValueError('Expected explicit project profile schema 1')
    for key in required - {'schema_version', 'approved_audience'}:
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError('Invalid profile field: ' + key)
    for key in ('profile_id', 'project_id'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', value[key]):
            raise ValueError('Profile/project IDs must be safe explicit labels')
    if not re.fullmatch(r'page_[a-f0-9]{32}', value['parent_page_id']):
        raise ValueError('Project profile needs a real parent Page ID')
    if not re.fullmatch(r'page_space_[a-f0-9]{32}', value['space_id']):
        raise ValueError('Project profile needs a real Space ID')
    if value['url'] != 'https://chatgpt.com/space/' + value['parent_page_id']:
        raise ValueError('Profile URL must identify its parent Page')
    result = dict(value, approved_audience=audience(value['approved_audience']))
    return result


def binding(value):
    return {key: value[key] for key in ('profile_id', 'project_id', 'space_id', 'parent_page_id', 'publisher_id')} | {
        'profile_sha256': digest(value), 'audience_sha256': digest(value['approved_audience'])}


def native_access(metadata, sharing, observed_at):
    """Normalize complete native read results, not Page prose or a saved claim."""
    inherited = sharing.get('inherited_access', {})
    if sharing.get('sharing_available') is not True or inherited.get('complete') is not True or sharing.get('next_cursor') or not isinstance(inherited.get('sources'), list) or not isinstance(sharing.get('shares'), list):
        raise ValueError('Native audience is unavailable or incomplete')
    if sharing.get('page_id') != metadata.get('page_id') or not metadata.get('drive_space_id'):
        raise ValueError('Native Page and sharing evidence do not identify one project Page')
    owner = sharing.get('owner', {})
    grants = [{'principal_type': owner.get('principal_type'), 'principal_id': owner.get('principal_id'), 'role': 'owner'}]
    def add(recipient, role):
        role = role.removeprefix('role-library-folder-') if isinstance(role, str) else role
        if role not in ('viewer', 'commenter', 'editor'):
            raise ValueError('Unrecognized native role; reconcile explicitly')
        grants.append({'principal_type': recipient.get('principal_type'), 'principal_id': recipient.get('principal_id'), 'role': role})
    for share in sharing.get('shares', []):
        if share.get('status') not in ('active', 'pending'):
            raise ValueError('Unrecognized share lifecycle; reconcile explicitly')
        add(share.get('recipient', {}), share.get('role_id'))
    for source in inherited.get('sources', []):
        add(source.get('recipient', {}), source.get('role'))
    # Multiple ancestors can confer the same grant. Deduplicate identical effective grants.
    unique = {digest(grant): grant for grant in grants}
    return {'resource_page_id': metadata['page_id'], 'space_id': metadata['drive_space_id'],
            'observed_at': observed_at, 'complete': True, 'audience': audience(list(unique.values()))}


def validate_summary(summary, selected):
    if summary.get('disclosure') != 'project' or summary.get('project_id') != selected['project_id']:
        raise ValueError('Explicit project disclosure and matching project ID are required')
    for field in ('workstream_id', 'owner', 'chat_id', 'machine_id', 'repo', 'commit'):
        if not isinstance(summary.get(field), str) or not summary[field].strip():
            raise ValueError('Project checkpoint requires explicit ' + field)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', summary['workstream_id']):
        raise ValueError('Invalid workstream ID')
    if summary['commit'] != 'unknown' and not re.fullmatch(r'[a-f0-9]{40,64}', summary['commit']):
        raise ValueError('Commit must be an actual SHA or explicitly unknown')
    if 'attention' in summary:
        raise ValueError('Personal attention fields are excluded from project checkpoints')
    if summary.get('observed_at') and stamp(summary['observed_at']) > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
        raise ValueError('Evidence observation is in the future')
    artifacts = summary.get('artifacts', [])
    if not isinstance(artifacts, list):
        raise ValueError('Artifacts must be an array')
    ids = set()
    for artifact in artifacts:
        fields = {'artifact_id', 'name', 'location', 'sha256', 'size_bytes', 'state'}
        if not isinstance(artifact, dict) or set(artifact) != fields:
            raise ValueError('Artifact requires identity, location, digest, bytes and state')
        if any(not isinstance(artifact[k], str) or not artifact[k].strip() for k in fields - {'size_bytes'}):
            raise ValueError('Invalid artifact strings')
        if artifact['artifact_id'] in ids or not re.fullmatch(r'[a-f0-9]{64}', artifact['sha256']):
            raise ValueError('Duplicate artifact identity or invalid digest')
        if type(artifact['size_bytes']) is not int or artifact['size_bytes'] < 0 or artifact['state'] not in ('prepared', 'uploaded'):
            raise ValueError('Invalid artifact bytes or state')
        ids.add(artifact['artifact_id'])


def access(proof, selected, resource_page_id, now=None):
    fields = {'resource_page_id', 'space_id', 'observed_at', 'complete', 'audience'}
    if not isinstance(proof, dict) or set(proof) != fields or proof['complete'] is not True:
        raise ValueError('Complete fresh native sharing evidence is required')
    if proof['resource_page_id'] != resource_page_id or proof['space_id'] != selected['space_id']:
        raise ValueError('Sharing evidence belongs to another resource')
    if audience(proof['audience']) != selected['approved_audience']:
        raise ValueError('Effective audience differs from approved project audience')
    age = ((now or datetime.datetime.now(datetime.timezone.utc)) - stamp(proof['observed_at'])).total_seconds()
    if age < -60 or age > 300:
        raise ValueError('Sharing evidence is stale or in the future; recheck native sharing')
    return {'audience_sha256': digest(selected['approved_audience']), 'access_verified_at': proof['observed_at']}


def claim_proof(value, selected):
    if not isinstance(value, dict) or set(value) != {'publisher_id', 'access'} or value['publisher_id'] != selected['publisher_id']:
        raise ValueError('Use the designated project publisher and its single owned store')
    return access(value['access'], selected, selected['parent_page_id'])


def receipt(value, selected, record):
    fields = {'page_id', 'url', 'sha256', 'content_verified', 'parent_page_id', 'space_id', 'published_at', 'access'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Project receipt needs exact revision, parent, Space, publication time and sharing readback')
    if not isinstance(value['page_id'], str) or not re.fullmatch(r'page_[a-f0-9]{32}', value['page_id']):
        raise ValueError('Invalid checkpoint Page ID')
    if value['url'] != 'https://chatgpt.com/space/' + value['page_id'] or value['sha256'] != record['sha256'] or value['content_verified'] is not True:
        raise ValueError('Checkpoint revision or canonical URL mismatch')
    if value['parent_page_id'] != selected['parent_page_id'] or value['space_id'] != selected['space_id']:
        raise ValueError('Checkpoint was delivered to another project destination')
    published = stamp(value['published_at'])
    if published > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
        raise ValueError('Publication timestamp is in the future')
    if published < stamp(record['recorded_at']) - datetime.timedelta(seconds=60):
        raise ValueError('Publication predates this prepared revision')
    checked = access(value['access'], selected, value['page_id'])
    return {k: v for k, v in value.items() if k != 'access'} | checked


def workstreams(items):
    # Keep parallel chats/forks separately, even when they use the same workstream label.
    groups = {}
    for item in items:
        key = (item['project_id'], item['workstream_id'], item.get('machine_id'), item.get('chat_id'), item.get('repo'))
        groups.setdefault(key, []).append(item)
    tasks = []
    for key, values in sorted(groups.items(), key=lambda x: str(x[0])):
        latest = max(values, key=lambda x: (x['recorded_at'], x['id']))
        delivered = [v for v in values if v['delivery']['state'] == 'published']
        tasks.append({'project_id': key[0], 'workstream_id': key[1], 'machine_id': key[2], 'chat_id': key[3], 'repo': key[4],
                      'owner': latest.get('owner'), 'parent_chat_id': latest.get('parent_chat_id'), 'commit': latest.get('commit'),
                      'latest_captured': latest, 'latest_published': max(delivered, key=lambda x: (x['recorded_at'], x['id'])) if delivered else None})
    return tasks
