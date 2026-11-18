"""Same-arbiter immutable history. No network, pruning, execution or second store."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import platform_io as io

LIMIT = 8 * 1024 * 1024
SHA = re.compile(r'[a-f0-9]{64}')
COLLECTIONS = ('publications', 'operations')
SCHEMAS = {1: (), 2: ('publications',), 3: COLLECTIONS}


def reference(raw):
    return {'sha256': checksum(raw), 'bytes': len(raw)}


def encoded(value):
    # Retain object order, all values and exact Markdown strings.
    return (json.dumps(value, separators=(',', ':')) + '\n').encode('utf-8')


def checksum(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_read(path):
    io.assert_private(path)
    with os.fdopen(io.open_read(path), 'rb') as f:
        raw = f.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('Queue data exceeds bounded size')
    return raw


def sync_dir(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def private_dir_durable(path):
    io.private_dir(path)
    # Existing directories may be leftovers from an interrupted staging attempt.
    # Persist their entries too; existence alone is not proof of durability.
    sync_dir(path)
    sync_dir(path.parent)


def atomic_bytes(path, raw):
    if len(raw) > LIMIT:
        raise ValueError('Queue data exceeds bounded size')
    io.assert_owned(path)
    io.private_dir(path.parent)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.queue-')
    try:
        with os.fdopen(fd, 'wb') as f:
            io.secure(Path(name))
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def checked_ref(ref):
    if (not isinstance(ref, dict) or set(ref) != {'sha256', 'bytes'}
            or not isinstance(ref['sha256'], str) or not SHA.fullmatch(ref['sha256'])
            or type(ref['bytes']) is not int or not 0 < ref['bytes'] <= LIMIT):
        raise ValueError('Invalid immutable history reference')
    return ref


def object_path(root, ref, backup=False):
    checked_ref(ref)
    # Never accept a caller-supplied path or use operation IDs as filenames.
    directory = root / 'history' / ('backups' if backup else 'objects')
    io.check_path(directory)
    return directory / (ref['sha256'] + '.json')


def get(root, ref, backup=False):
    path = object_path(root, ref, backup)
    io.assert_private(root / 'history')
    io.assert_private(path.parent)
    raw = raw_read(path)
    if len(raw) != ref['bytes'] or checksum(raw) != ref['sha256']:
        raise ValueError('Immutable history size/hash mismatch')
    return raw


def put(root, raw, backup=False):
    if len(raw) > LIMIT:
        raise ValueError('Queue data exceeds bounded size')
    ref = {'sha256': checksum(raw), 'bytes': len(raw)}
    path = object_path(root, ref, backup)
    private_dir_durable(root / 'history')
    private_dir_durable(path.parent)
    if path.exists():
        if get(root, ref, backup) != raw:
            raise ValueError('Immutable history content changed')
    else:
        # All callers hold the existing queue.lock. An interrupted staging write
        # leaves only an unreferenced temp/object; existing objects never change.
        atomic_bytes(path, raw)
    if get(root, ref, backup) != raw:
        raise ValueError('Immutable history readback failed')
    return ref


def hydrate(root, physical):
    if physical.get('schema_version') == 1:
        return physical
    if physical.get('schema_version') not in (2, 3):
        raise ValueError('Unsupported queue storage schema')
    checked_ref(physical['history_migration']['original'])
    value = copy.deepcopy(physical)
    for collection in SCHEMAS[physical['schema_version']]:
        value[collection] = {key: json.loads(get(root, ref))
                             for key, ref in physical[collection].items()}
    value.pop('history_migration')
    value['schema_version'] = 1  # Logical API and published snapshot stay unchanged.
    return value


def pack(root, logical, migration, existing=None):
    if logical.get('schema_version') != 1 or 'history_migration' in logical:
        raise ValueError('Logical queue schema 1 required')
    value = copy.deepcopy(logical)
    staged = []
    existing = existing or {}
    for collection in COLLECTIONS:
        refs = {}
        for key, record in logical[collection].items():
            raw = encoded(record)
            if len(raw) > LIMIT:
                raise ValueError('Immutable record exceeds 8 MiB; state unchanged')
            ref = reference(raw)
            refs[key] = ref
            if (existing.get('schema_version') not in (2, 3)
                    or collection not in SCHEMAS[existing['schema_version']]
                    or existing.get(collection, {}).get(key) != ref):
                staged.append(raw)
        value[collection] = refs
    value['schema_version'] = 3
    value['history_migration'] = copy.deepcopy(migration)
    # Capacity refusal must precede staging as well as the primary replacement.
    bounded(encoded(value))
    for raw in staged:
        put(root, raw)
    if hydrate(root, value) != logical:
        raise ValueError('History roundtrip changed queue records')
    return value


def bounded(raw):
    if len(raw) > LIMIT:
        raise ValueError('Queue write would exceed 8 MiB by ' + str(len(raw) - LIMIT)
                         + ' bytes; state unchanged. Inspect storage-status and plan history migration/rollover.')


def assert_writable(q):
    marker = q.root / 'FROZEN-SEGMENT.json'
    io.check_path(marker)
    if marker.exists():
        # Presence alone fences writes, including malformed or partly staged markers.
        raise ValueError('Queue segment is frozen; reconcile its verified successor before writing')


def save(path, logical):
    # The Queue caller holds queue.lock and has already checked its frozen binding.
    physical = json.loads(raw_read(path)) if path.exists() else None
    if physical and physical.get('schema_version') in (2, 3):
        # Keep publication-only schema 2 readable/writable until an explicit migration.
        if physical['schema_version'] == 2:
            value = copy.deepcopy(logical)
            value['publications'] = {k: reference(encoded(v)) for k, v in logical['publications'].items()}
            value['schema_version'] = 2
            value['history_migration'] = physical['history_migration']
            bounded(encoded(value))
            for v in logical['publications'].values():
                ref = reference(encoded(v))
                if ref not in physical['publications'].values():
                    put(path.parent, encoded(v))
            if hydrate(path.parent, value) != logical:
                raise ValueError('History roundtrip changed queue records')
            logical = value
        else:
            logical = pack(path.parent, logical, physical['history_migration'], physical)
    elif physical and physical.get('schema_version') != 1:
        raise ValueError('Unsupported queue storage schema')
    bounded(encoded(logical))
    atomic_bytes(path, encoded(logical))


def guarded(q, value, arbiter):
    if arbiter != q.c['arbiter_id']:
        raise ValueError('Only designated arbiter/store may migrate history')
    assert_writable(q)
    raw = raw_read(q.path)
    if (checksum(raw) != value.get('expected_sha256')
            or json.loads(raw)['revision'] != value.get('expected_revision')):
        raise ValueError('Queue changed; reconcile before migration or restore')
    return raw


def migrate(q, value, arbiter):
    with io.file_lock(q.root / 'queue.lock'):
        original = guarded(q, value, arbiter)
        physical = json.loads(original)
        if physical.get('schema_version') not in (1, 2):
            raise ValueError('Already migrated/unknown outcome; verify instead of retrying')
        logical = q.state()  # Includes frozen binding validation.
        migration = {'original': put(q.root, original, backup=True),
                     'revision': logical['revision'], 'source_schema': physical['schema_version']}
        proposed = pack(q.root, logical, migration)
        target = encoded(proposed)
        # Everything is durable and independently read back before this commit.
        atomic_bytes(q.path, target)
        if raw_read(q.path) != target or q.state() != logical:
            raise ValueError('Migration outcome needs reconciliation; do not retry')
        return {'migrated': True, 'revision': logical['revision'],
                'original_sha256': checksum(original), 'state_sha256': checksum(target),
                'original_bytes': len(original), 'state_bytes': len(target),
                'backup': str(object_path(q.root, migration['original'], backup=True))}


def restore(q, value, arbiter):
    with io.file_lock(q.root / 'queue.lock'):
        current = guarded(q, value, arbiter)
        physical = json.loads(current)
        if physical.get('schema_version') not in (2, 3):
            raise ValueError('Restore requires migrated state')
        original = get(q.root, physical['history_migration']['original'], backup=True)
        if q.state() != hydrate(q.root, json.loads(original)):
            raise ValueError('Later queue/publication edits exist; do not restore old state')
        # Restore exact original bytes, retaining every backup and history object.
        atomic_bytes(q.path, original)
        if raw_read(q.path) != original:
            raise ValueError('Restore outcome needs reconciliation; do not retry')
        return {'restored': True, 'revision': physical['revision'],
                'state_sha256': checksum(original), 'state_bytes': len(original)}


def verify(q):
    # Lock for a coherent state/backup observation; no file or record is changed.
    with io.file_lock(q.root / 'queue.lock'):
        raw = raw_read(q.path)
        physical = json.loads(raw)
        logical = q.state()
        previous_operation(q, '', logical, verify_objects=True)
        result = {'schema_version': physical['schema_version'], 'revision': logical['revision'],
                  'state_sha256': checksum(raw), 'state_bytes': len(raw),
                  'logical_sha256': checksum(encoded(logical)),
                  'counts': {key: len(logical[key]) for key in COLLECTIONS}}
        if physical['schema_version'] in (2, 3):
            verify_backups(q.root, physical)
            original = get(q.root, physical['history_migration']['original'], backup=True)
            result.update(original_sha256=checksum(original), original_bytes=len(original),
                          original_revision=json.loads(original)['revision'],
                          matches_original=(logical == hydrate(q.root, json.loads(original))))
        return result


def previous_operation(q, operation_id, current_state=None, verify_objects=False):
    """Resolve retained replay records through verified same-store segment links.

    This does not follow arbitrary roots/config paths from a continuity note.
    It understands the explicit manual segment format, without making a new arbiter.
    """
    current_state = current_state if current_state is not None else q.state()
    current = q.root
    seen = {q.c['queue_id']}
    for _ in range(32):
        note_path = current / 'SEGMENT-CONTINUITY.json'
        io.check_path(note_path)
        if not note_path.exists():
            return None
        note = json.loads(raw_read(note_path))
        previous = note['previous']
        queue_id = previous['queue_id']
        if (not isinstance(queue_id, str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', queue_id)
                or queue_id in seen):
            raise ValueError('Invalid/cyclic predecessor queue segment')
        seen.add(queue_id)
        old_root = q.root.parent / queue_id
        if (note.get('schema_version') != 1 or note.get('sole_arbiter') != q.c['arbiter_id']
                or Path(note['successor']['root']) != current
                or note['successor']['queue_id'] != current.name
                or Path(previous['root']) != old_root):
            raise ValueError('Segment continuity does not match assigned store/arbiter')
        frozen = json.loads(raw_read(old_root / 'FROZEN-SEGMENT.json'))
        raw = raw_read(old_root / 'state.json')
        if (checksum(raw) != previous['state_sha256']
                or len(raw) != previous['state_bytes']
                or frozen.get('previous_state_sha256') != previous['state_sha256']
                or frozen.get('successor_queue_id') != current.name
                or Path(frozen['successor_root']) != current
                or frozen.get('sole_arbiter') != q.c['arbiter_id']
                or frozen.get('all_writes_must_use_successor') is not True):
            raise ValueError('Frozen predecessor changed or successor fence is unverified')
        state = json.loads(raw)
        if (state['queue_id'] != queue_id or state['revision'] != previous['revision']
                or any(t['project_id'] != q.c['project_id'] or t['scope'] != q.c['scope']
                       for t in state['tasks'].values())):
            raise ValueError('Predecessor scope/revision mismatch')
        if verify_objects:
            hydrate(old_root, state)
            verify_backups(old_root, state)
        for ident, task in state['tasks'].items():
            latest = current_state['tasks'].get(ident)
            if (latest is None or latest['revision'] < task['revision']
                    or (latest['revision'] == task['revision'] and latest != task)
                    or (task['status'] in ('completed', 'cancelled') and latest['status'] != task['status'])):
                raise ValueError('Successor lost or rewound predecessor task/claim state')
        if not set(state['mirrors']) <= set(current_state['mirrors']):
            raise ValueError('Successor lost predecessor mirrors')
        op = state['operations'].get(operation_id)
        if op is not None:
            if state['schema_version'] == 3:
                op = json.loads(get(old_root, op))
            elif state['schema_version'] not in (1, 2):
                raise ValueError('Unsupported predecessor schema')
            return {'record': op, 'queue_id': queue_id}
        current = old_root
    raise ValueError('Queue segment chain exceeds bounded traversal; reconcile before pickup')


def status(q):
    with io.file_lock(q.root / 'queue.lock'):
        raw = raw_read(q.path)
        physical = json.loads(raw)
        logical = q.state()
        previous_operation(q, '', logical)
        size = len(raw)
        return {'schema_version': physical['schema_version'], 'revision': logical['revision'],
                'state_sha256': checksum(raw), 'state_bytes': size, 'limit_bytes': LIMIT,
                **capacity(size),
                'frozen': (q.root / 'FROZEN-SEGMENT.json').exists(),
                'has_predecessor': (q.root / 'SEGMENT-CONTINUITY.json').exists(),
                'counts': {key: len(logical[key]) for key in ('tasks', 'events', 'operations', 'publications')},
                'logical_collection_bytes': {key: len(encoded(logical[key]))
                                             for key in ('tasks', 'events', 'operations', 'publications')},
                'next_step': 'No automatic mutation. Inspect growth; migrate history or plan a reconciled rollover before capacity is exhausted.'}


def capacity_for(q, logical):
    """Measure a validated proposed transition; never stage objects or expose a token."""
    physical = json.loads(raw_read(q.path))
    value = copy.deepcopy(logical)
    schema = physical['schema_version']
    if schema not in SCHEMAS:
        raise ValueError('Unsupported queue storage schema')
    largest = 0
    for collection in SCHEMAS[schema]:
        refs = {}
        for key, record in logical[collection].items():
            raw = encoded(record)
            largest = max(largest, len(raw))
            refs[key] = reference(raw)
        value[collection] = refs
    value['schema_version'] = schema
    if schema in (2, 3):
        value['history_migration'] = physical['history_migration']
    size = len(encoded(value))
    return {'revision': logical['revision'], 'projected_state_bytes': size,
            'largest_external_record_bytes': largest, 'limit_bytes': LIMIT,
            'remaining_bytes': LIMIT-size,
            'fits': size <= LIMIT and largest <= LIMIT,
            'caution': 'Read-only size estimate at this revision, not a reservation, claim or permission to execute.'}


def capacity(size):
    return {'state_bytes': size, 'limit_bytes': LIMIT, 'remaining_bytes': LIMIT-size,
            'pressure': 'critical' if size >= LIMIT*.95 else 'warning' if size >= LIMIT*.80 else 'normal'}


def verify_backups(root, physical):
    for _ in range(32):
        if physical['schema_version'] == 1:
            return
        if physical['schema_version'] not in (2, 3):
            raise ValueError('Unsupported backup schema')
        physical = json.loads(get(root, physical['history_migration']['original'], backup=True))
        hydrate(root, physical)
    raise ValueError('History backup chain exceeds bounded traversal')
