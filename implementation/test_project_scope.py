import concurrent.futures
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parent / 'work-checkpoint/scripts/checkpoint.py'
spec = importlib.util.spec_from_file_location('scope', SCRIPT.with_name('project_scope.py'))
scope = importlib.util.module_from_spec(spec); spec.loader.exec_module(scope)
io_spec = importlib.util.spec_from_file_location('project_io', SCRIPT.with_name('platform_io.py'))
io = importlib.util.module_from_spec(io_spec); io_spec.loader.exec_module(io)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ProjectProfiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = self.root / 'checkpoints'
        self.profile = {'schema_version': 1, 'kind': 'project', 'profile_id': 'project-user-a', 'project_id': 'project-a',
                        'space_id': 'page_space_' + '1' * 32, 'parent_page_id': 'page_' + '2' * 32,
                        'url': 'https://chatgpt.com/space/page_' + '2' * 32,
                        'publisher_id': 'publisher-a', 'approved_audience': [
                            {'principal_type': 'group', 'principal_id': 'team-a', 'role': 'editor'},
                            {'principal_type': 'user', 'principal_id': 'owner-a', 'role': 'owner'}]}
        self.profile_path = self.root / 'project.json'
        self.save_profile()
        chat = 'a' * 32
        self.summary = {'task_id': chat, 'chat_id': chat, 'machine_id': 'cloud-a', 'project': '/workspace/project',
                        'goal': 'Verify a project handoff', 'status': 'working', 'next_step': 'Review evidence',
                        'resume_point': 'Prepared evidence', 'project_id': 'project-a', 'workstream_id': 'migration',
                        'disclosure': 'project', 'owner': 'Member A', 'repo': 'https://github.com/example/project',
                        'commit': 'f' * 40, 'package_version': '0.3.3',
                        'observed_at': (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()}

    def test_unknown_machine_preserves_project_revision_and_is_unverified(self):
        record = self.call('prepare', value={**self.summary, 'machine_id': 'unknown'})
        before = self.call('show', record['id'])
        index = self.call('index')
        self.assertFalse(index['checkpoints'][0]['identity_complete'])
        self.assertFalse(index['workstreams'][0]['latest_captured']['identity_complete'])
        self.assertEqual(self.call('show', record['id']), before)

    def tearDown(self):
        self.temp.cleanup()

    def save_profile(self):
        self.profile_path.write_text(json.dumps(self.profile))
        io.secure(self.profile_path)

    def call(self, command, ident=None, value=None, personal=False, store=None, expected=0):
        cmd = [sys.executable, str(SCRIPT), '--store', str(store or self.store)]
        if not personal:
            cmd += ['--profile', str(self.profile_path)]
        cmd += [command] + ([ident] if ident else [])
        r = subprocess.run(cmd, input=json.dumps(value) if value is not None else '', text=True, capture_output=True)
        self.assertEqual(r.returncode, expected, r.stderr)
        return json.loads(r.stdout) if expected == 0 else r.stderr

    def proof(self, page=None):
        return {'resource_page_id': page or self.profile['parent_page_id'], 'space_id': self.profile['space_id'],
                'observed_at': now(), 'complete': True, 'audience': self.profile['approved_audience']}

    def claim(self, ident):
        return self.call('claim', ident, {'publisher_id': self.profile['publisher_id'], 'access': self.proof()})

    def ack(self, record):
        page = 'page_' + '3' * 32
        receipt = {'page_id': page, 'url': 'https://chatgpt.com/space/' + page, 'sha256': record['sha256'],
                   'content_verified': True, 'parent_page_id': self.profile['parent_page_id'], 'space_id': self.profile['space_id'],
                   'published_at': now(), 'access': self.proof(page)}
        return receipt

    def test_personal_notes_and_indexes_cannot_fall_through_to_project(self):
        personal = {k: self.summary[k] for k in ('task_id', 'project', 'goal', 'status', 'next_step', 'resume_point')}
        personal['attention'] = {'current_focus': 'PRIVATE_COORDINATION_SENTINEL'}
        self.call('prepare', value=personal, personal=True)
        r = self.call('prepare', value=self.summary)
        index = self.call('index')
        self.assertEqual(index['schema_version'], 3)
        self.assertEqual(len(index['checkpoints']), 1)
        self.assertNotIn('PRIVATE_COORDINATION_SENTINEL', json.dumps(index))
        self.assertNotIn('PRIVATE_COORDINATION_SENTINEL', Path(r['file']).read_text())
        self.call('prepare', value={**self.summary, 'attention': personal['attention']}, expected=1)
        self.call('prepare', value=self.summary, personal=True, expected=1)
        self.call('prepare', value={**self.summary, 'personal_notes': 'Private'}, expected=1)
        self.assertEqual(len(self.call('index', personal=True)['checkpoints']), 1)

    def test_audience_scope_and_freshness_gate_before_claim(self):
        r = self.call('prepare', value=self.summary)
        for changes in ({'complete': False}, {'space_id': 'page_space_' + '0' * 32},
                        {'observed_at': (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)).isoformat()},
                        {'audience': self.profile['approved_audience'] + [{'principal_type': 'user', 'principal_id': 'outsider', 'role': 'viewer'}]}):
            proof = self.proof();proof.update(changes)
            self.call('claim', r['id'], {'publisher_id': 'publisher-a', 'access': proof}, expected=1)
            self.assertEqual(self.call('show', r['id'])['delivery']['state'], 'pending')
        self.call('claim', r['id'], {'publisher_id': 'other-publisher', 'access': self.proof()}, expected=1)
        self.assertTrue(self.claim(r['id'])['claimed'])

    def test_exact_revision_parent_and_audience_required_for_receipt(self):
        r = self.call('prepare', value=self.summary);self.claim(r['id'])
        for field, value in [('sha256', '0' * 64), ('parent_page_id', 'page_' + '4' * 32), ('space_id', 'page_space_' + '4' * 32)]:
            receipt = self.ack(r);receipt[field] = value
            self.call('ack', r['id'], receipt, expected=1)
        receipt = self.ack(r);receipt['access']['audience'] = [{'principal_type': 'user', 'principal_id': 'owner-a', 'role': 'owner'}]
        self.call('ack', r['id'], receipt, expected=1)
        self.call('ack', r['id'], self.ack(r))
        record = self.call('show', r['id'])
        self.assertEqual(record['delivery']['state'], 'published')
        self.assertEqual(record.get('consumer_events', []), [])
        self.assertEqual(self.call('status')['tasks'][0]['observed_at'], self.summary['observed_at'])
        self.assertGreater(self.call('status')['tasks'][0]['evidence_age_minutes'], 2800)

    def test_two_owners_workstreams_forks_and_source_dates_stay_separate(self):
        first = self.call('prepare', value=self.summary)
        self.claim(first['id']);self.call('ack', first['id'], self.ack(first))
        second = {**self.summary, 'task_id': 'b' * 32, 'chat_id': 'b' * 32, 'machine_id': 'cloud-b',
                  'owner': 'Member B', 'workstream_id': 'diagnostics'}
        self.call('prepare', value=second)
        fork = {**self.summary, 'task_id': 'c' * 32, 'chat_id': 'c' * 32, 'parent_chat_id': 'a' * 32}
        self.call('prepare', value=fork)
        index = self.call('index');self.assertEqual(len(index['workstreams']), 3)
        original = next(x for x in index['workstreams'] if x['chat_id'] == 'a' * 32)
        self.assertEqual(original['latest_published']['observed_at'], self.summary['observed_at'])
        self.assertEqual(next(x for x in index['workstreams'] if x['chat_id'] == 'c' * 32)['parent_chat_id'], 'a' * 32)
        # A new capture with old observation evidence remains visibly old and pending.
        self.call('prepare', value={**self.summary, 'next_step': 'Recheck current parity'})
        original = next(x for x in self.call('index')['workstreams'] if x['chat_id'] == 'a' * 32)
        self.assertEqual(original['latest_captured']['delivery']['state'], 'pending')
        self.assertEqual(original['latest_published']['id'], first['id'])

    def test_original_bridge_revision_is_preserved_and_unknown_outcomes_never_reset(self):
        r = self.call('prepare', value=self.summary)
        exported = self.call('export', r['id'])
        target = self.root / 'publisher-store'
        self.assertTrue(self.call('import', value=exported, store=target)['imported'])
        imported = self.call('show', r['id'], store=target)
        source = self.call('show', r['id'])
        self.assertEqual(imported['recorded_at'], source['recorded_at'])
        self.assertEqual(imported['sha256'], source['sha256'])
        self.assertEqual(imported['markdown'], source['markdown'])
        self.call('claim', r['id'], {'publisher_id': 'publisher-a', 'access': self.proof()}, store=target)
        self.call('uncertain', r['id'], store=target)
        self.assertEqual(self.call('import', value=exported, store=target)['delivery']['state'], 'uncertain')
        self.assertFalse(self.call('claim', r['id'], store=target)['claimed'])
        bad = copy.deepcopy(exported);bad['recorded_at'] = now()
        self.call('import', value=bad, store=self.root / 'bad-store', expected=1)

    def test_cross_profile_rerouting_and_same_label_deduplication_are_prevented(self):
        r = self.call('prepare', value=self.summary)
        self.profile['parent_page_id'] = 'page_' + '4' * 32
        self.profile['url'] = 'https://chatgpt.com/space/' + self.profile['parent_page_id'];self.save_profile()
        self.call('show', r['id'], expected=1)
        self.call('index', expected=1)
        self.call('prepare', value=self.summary, expected=1)
        self.profile['profile_id'] = 'new-reviewed-destination';self.save_profile()
        changed = self.call('prepare', value=self.summary)
        self.assertNotEqual(r['id'], changed['id'])

    def test_single_publisher_concurrent_claim_deduplicates(self):
        r = self.call('prepare', value=self.summary)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _: self.claim(r['id']), range(4)))
        self.assertEqual(sum(x['claimed'] for x in claims), 1)

    def test_artifact_download_read_and_action_are_independent_evidence(self):
        summary = {**self.summary, 'artifacts': [{'artifact_id': 'package', 'name': 'package.zip',
                    'location': 'library-file:example', 'sha256': 'd' * 64, 'size_bytes': 20, 'state': 'uploaded'}]}
        r = self.call('prepare', value=summary)
        self.claim(r['id']);self.call('ack', r['id'], self.ack(r))
        event = {'kind': 'read', 'actor': 'cloud-reader-b', 'at': now(), 'sha256': r['sha256'], 'evidence': 'native exact Page readback'}
        self.call('consume', r['id'], {**event, 'sha256': '0' * 64}, expected=1)
        self.call('consume', r['id'], event);self.call('consume', r['id'], event)
        self.assertEqual(len(self.call('show', r['id'])['consumer_events']), 1)
        artifact = {**event, 'kind': 'artifact_read', 'artifact_id': 'package', 'artifact_sha256': '0' * 64}
        self.call('consume', r['id'], artifact, expected=1)
        artifact['artifact_sha256'] = 'd' * 64;artifact['evidence'] = 'Downloaded bytes compared SHA-256'
        self.call('consume', r['id'], artifact)
        self.call('consume', r['id'], {**event, 'kind': 'acted', 'evidence': 'https://github.com/example/project/pull/1'})
        self.assertEqual({e['kind'] for e in self.call('show', r['id'])['consumer_events']}, {'read', 'artifact_read', 'acted'})

    def test_native_readback_requires_complete_sharing_and_page_space_identity(self):
        metadata = {'page_id': self.profile['parent_page_id'], 'drive_space_id': self.profile['space_id']}
        sharing = {'page_id': metadata['page_id'], 'sharing_available': True, 'owner': {'principal_type': 'user', 'principal_id': 'owner-a'},
                   'shares': [], 'next_cursor': None, 'inherited_access': {'complete': True, 'sources': [
                       {'recipient': {'principal_type': 'group', 'principal_id': 'team-a'}, 'role': 'editor'}]}}
        proof = scope.native_access(metadata, sharing, now())
        self.assertEqual(scope.audience(proof['audience']), scope.audience(self.profile['approved_audience']))
        incomplete = copy.deepcopy(sharing);incomplete['inherited_access']['complete'] = False
        with self.assertRaises(ValueError): scope.native_access(metadata, incomplete, now())
        mismatched = copy.deepcopy(sharing);mismatched['page_id'] = 'page_' + '0' * 32
        with self.assertRaises(ValueError): scope.native_access(metadata, mismatched, now())

    def test_project_session_start_and_stop_are_read_only_and_keep_explicit_routing(self):
        output = self.call('session-start', value={'hook_event_name': 'SessionStart', 'session_id': 'a' * 32,
                                                'transcript_path': '/denied', 'cwd': '/denied'})
        self.assertIn('--profile', output['hookSpecificOutput']['additionalContext'])
        self.assertNotIn('/denied', output['hookSpecificOutput']['additionalContext'])
        self.assertFalse(self.store.exists())
        event = {'hook_event_name': 'Stop', 'session_id': 'a' * 32, 'transcript_path': '/denied'}
        self.assertEqual(self.call('stop-check', value=event), {})
        self.assertFalse(self.store.exists())
        self.call('prepare', value=self.summary)
        before = {str(p): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                  for p in self.store.rglob('*') if p.is_file()}
        self.assertIn('systemMessage', self.call('stop-check', value=event))
        after = {str(p): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                 for p in self.store.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
