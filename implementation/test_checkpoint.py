import concurrent.futures
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
import datetime
import hashlib
import os
import sys
import tarfile
from unittest.mock import patch

SCRIPT = Path(__file__).parent / 'work-checkpoint/scripts/checkpoint.py'
spec = importlib.util.spec_from_file_location('installer', Path(__file__).parent / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Checkpoints(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name) / 'store'
        self.summary = dict(task_id='pilot', project='/tmp/pilot', goal='Verify checkpoint delivery', status='working', next_step='Read cloud copy', resume_point='Prepared summary')

    def tearDown(self):
        self.temp.cleanup()

    def call(self, command, ident=None, payload=None, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), '--store', str(self.store), command] + ([ident] if ident else []), input=json.dumps(payload) if payload is not None else '', text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stderr)
        return json.loads(result.stdout) if expected == 0 else result.stderr

    def test_deduplication_and_private_files(self):
        first = self.call('prepare', payload=self.summary)
        self.assertEqual(first, self.call('prepare', payload=self.summary))
        installer._io.assert_private(self.store)
        installer._io.assert_private(Path(first['file']))

    def test_concurrent_claim_and_uncertain_no_retry(self):
        record = self.call('prepare', payload=self.summary)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _: self.call('claim', record['id']), range(4)))
        self.assertEqual(sum(c['claimed'] for c in claims), 1)
        self.call('uncertain', record['id'])
        self.assertFalse(self.call('claim', record['id'])['claimed'])
        self.call('release', record['id'], expected=1)

    def test_stable_index_tracks_delivery_and_retry_attempts(self):
        record = self.call('prepare', payload=self.summary)
        self.assertEqual(self.call('index')['checkpoints'][0]['delivery']['state'], 'pending')
        self.call('claim', record['id'])
        self.call('release', record['id'])
        self.call('claim', record['id'])
        self.call('uncertain', record['id'])
        item = self.call('index')['checkpoints'][0]
        self.assertEqual(item['id'], record['id'])
        self.assertEqual(item['delivery']['attempts'], 2)
        self.assertEqual(item['delivery']['state'], 'uncertain')
        self.assertIn('updated_at', item['delivery'])
        installer._io.assert_private(self.store / 'index.json')

    def test_receipt_requires_readback_and_matching_hash(self):
        record = self.call('prepare', payload=self.summary)
        self.call('claim', record['id'])
        receipt = dict(page_id='page_test', url='https://chatgpt.com/canvas/test', sha256='wrong', owner_only=True, content_verified=True)
        self.call('ack', record['id'], receipt, expected=1)
        receipt['sha256'] = record['sha256']
        receipt['owner_only'] = False
        self.call('ack', record['id'], receipt, expected=1)
        receipt['owner_only'] = True
        self.call('ack', record['id'], receipt)
        self.assertEqual(self.call('pending'), [])
        self.assertFalse(self.call('claim', record['id'])['claimed'])

    def test_invalid_fields_and_credentials_are_rejected(self):
        self.call('prepare', payload={**self.summary, 'transcript_path': '/secret'}, expected=1)
        self.call('prepare', payload={**self.summary, 'goal': 'sk-' + 'x' * 30}, expected=1)
        self.assertEqual(list((self.store / 'records').iterdir()), [])

    def test_symlink_store_rejected(self):
        try:
            self.store.symlink_to(Path(self.temp.name), target_is_directory=True)
        except OSError:
            self.skipTest('Creating a Windows symlink requires separate OS permission; no permission is changed by tests')
        self.call('prepare', payload=self.summary, expected=1)

    def test_session_start_injects_guidance_without_opening_payload_paths(self):
        event = {'hook_event_name': 'SessionStart', 'cwd': '/denied', 'transcript_path': '/denied/secret.jsonl'}
        output = self.call('session-start', payload=event)
        context = output['hookSpecificOutput']['additionalContext']
        self.assertIn('name: work-checkpoint', context)
        self.assertNotIn('/denied', context)
        self.assertFalse(self.store.exists())

    def test_config_preserves_existing_values_and_is_not_duplicated(self):
        text = 'sandbox_mode = "workspace-write"\napprovals_reviewer = "auto_review"\n[sandbox_workspace_write]\nwritable_roots = [\n "/tmp/existing",\n]\nnetwork_access = true\n[projects."/tmp/pilot"]\ntrust_level = "trusted"\n'
        import tomllib
        result = installer.configure(text)
        before, after = tomllib.loads(text), tomllib.loads(result)
        self.assertEqual(after['projects'], before['projects'])
        self.assertTrue(after['sandbox_workspace_write']['network_access'])
        self.assertEqual(after['sandbox_workspace_write']['writable_roots'], ['/tmp/existing', str(installer.STORE)])
        self.assertEqual(installer.configure(result), result)

    def test_identity_requires_actual_id_and_timezone(self):
        chat = '11111111-2222-3333-4444-555555555555'
        self.call('prepare', payload={**self.summary, 'chat_id': chat}, expected=1)
        self.call('prepare', payload={**self.summary, 'observed_at': '2026-10-08T10:00:00'}, expected=1)
        self.call('prepare', payload={**self.summary, 'task_id': chat, 'chat_id': chat,
                                     'machine_id': 'desktop-a', 'package_version': '0.3.4',
                                     'observed_at': '2026-10-08T10:00:00Z'})
        task = self.call('status')['tasks'][0]
        self.assertTrue(task['identity_complete'])
        self.assertTrue(task['delivery_gap'])
        self.assertGreater(task['evidence_age_minutes'], task['checkpoint_age_minutes'])

    def test_upgrade_recognizes_older_instruction_link_without_rewriting_private_guidance(self):
        home = Path(self.temp.name) / 'codex home'
        # Existing users may have an earlier personal marker and approved standing scope.
        # The reusable installer must neither replace that scope nor add a second block.
        import tomllib
        old = installer.instructions(home).replace(installer.MARKER, '[Previous work checkpoints]')
        # Both released installer wording and the earlier manually installed wording.
        for block in (old, old.replace('Use work-checkpoint for prepared sanitized summaries',
                                      'Use work-checkpoint to inform the private cloud registry')):
            with self.subTest(block=block):
                existing = 'Local user-authorized coordinator and exclusions.\n\n' + block
                text = ('sandbox_mode = "workspace-write"\ndeveloper_instructions = ' + json.dumps(existing)
                        + '\n[sandbox_workspace_write]\nwritable_roots = ' + json.dumps([str(home / 'checkpoints')]) + '\n')
                self.assertEqual(installer.configure(text, home), text)
                configured = tomllib.loads(installer.configure(text, home))
                self.assertEqual(configured['developer_instructions'], existing)
                incomplete = text.replace(json.dumps([str(home / 'checkpoints')]), '[]')
                with self.assertRaisesRegex(ValueError, 'targeted reconciliation'):
                    installer.configure(incomplete, home)

    def test_placeholder_machine_is_unverified_without_rewriting_revision(self):
        chat = 'c' * 32
        for machine in ('unknown', 'Unknown'):
            with self.subTest(machine=machine):
                record = self.call('prepare', payload={**self.summary, 'task_id': chat,
                                   'chat_id': chat, 'machine_id': machine,
                                   'observed_at': '2026-10-08T10:00:00Z'})
                before = self.call('show', record['id'])
                index = self.call('index')
                item = next(x for x in index['checkpoints'] if x['id'] == record['id'])
                self.assertFalse(item['identity_complete'])
                self.assertEqual(item['machine_id'], machine)
                self.assertEqual(item['observed_at'], '2026-10-08T10:00:00Z')
                self.assertFalse(next(x for x in self.call('status')['tasks']
                                      if x['machine_id'] == machine)['identity_complete'])
                self.assertEqual(self.call('stop-check', payload={'hook_event_name': 'Stop',
                                                                'session_id': chat}), {})
                self.assertEqual(self.call('show', record['id']), before)

    def test_same_folder_forks_and_machines_remain_distinct(self):
        for chat, machine in [('a' * 32, 'desktop-a'), ('b' * 32, 'desktop-a'), ('a' * 32, 'second-host')]:
            self.call('prepare', payload={**self.summary, 'task_id': chat, 'chat_id': chat, 'machine_id': machine})
        self.assertEqual(len(self.call('status')['tasks']), 3)

    def test_legacy_receipt_and_markdown_survive_index_upgrade(self):
        record = self.call('prepare', payload=self.summary)
        self.call('claim', record['id'])
        receipt = dict(page_id='page_test', url='https://chatgpt.com/space/page_test', sha256=record['sha256'], owner_only=True, content_verified=True)
        self.call('ack', record['id'], receipt)
        before = self.call('show', record['id'])
        index = self.call('index')
        self.assertEqual(index['schema_version'], 2)
        self.assertFalse(index['checkpoints'][0]['identity_complete'])
        self.call('prepare', payload=self.summary)
        self.assertEqual(self.call('show', record['id']), before)
        path = self.store / 'records' / (record['id'] + '.json')
        old = json.loads(path.read_text())
        old['summary']['observed_at'] = 'legacy unknown time'
        path.write_text(json.dumps(old))
        self.assertFalse(self.call('status')['tasks'][0]['evidence_timestamp_valid'])

    def test_stop_guard_is_nonblocking_suppresses_duplicates_and_ignores_raw_paths(self):
        chat = 'c' * 32
        event = {'hook_event_name': 'Stop', 'session_id': chat, 'cwd': '/denied',
                 'transcript_path': '/denied/secret', 'last_assistant_message': 'SECRET RAW TEXT'}
        self.assertEqual(self.call('stop-check', payload=event), {})
        self.assertFalse(self.store.exists())
        record = self.call('prepare', payload={**self.summary, 'task_id': chat, 'chat_id': chat, 'machine_id': 'desktop-a'})
        before = {p: p.stat().st_mtime_ns for p in self.store.rglob('*')}
        reminder = self.call('stop-check', payload=event)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.store.rglob('*')})
        self.assertIn('systemMessage', reminder)
        self.assertNotIn('decision', reminder)
        self.assertNotIn('SECRET', json.dumps(reminder))
        self.call('note', record['id'])
        self.assertEqual(self.call('stop-check', payload=event), {})
        self.call('claim', record['id'])
        self.call('release', record['id'])
        self.assertIn('systemMessage', self.call('stop-check', payload=event))
        self.call('claim', record['id'])
        self.call('ack', record['id'], dict(page_id='page_test', url='https://chatgpt.com/space/page_test', sha256=record['sha256'], owner_only=True, content_verified=True))
        self.assertEqual(self.call('stop-check', payload=event), {})
        self.assertEqual(self.call('stop-check', payload={**event, 'session_id': 'unknown'}), {})
        self.assertFalse((self.store / 'guards').exists())

    def test_changed_work_due_does_not_turn_capture_time_into_evidence_time(self):
        record = self.call('prepare', payload=self.summary)
        path = self.store / 'records' / (record['id'] + '.json')
        value = json.loads(path.read_text())
        value['recorded_at'] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        path.write_text(json.dumps(value))
        status = self.call('status')['tasks'][0]
        self.assertTrue(status['review_due_if_work_changed'])
        self.assertIsNone(status['evidence_age_minutes'])
        value['summary']['status'] = 'paused'
        path.write_text(json.dumps(value))
        self.assertFalse(self.call('status')['tasks'][0]['review_due_if_work_changed'])

    def test_portable_install_and_hash_checked_upgrade_preserve_settings_and_hooks(self):
        home = Path(self.temp.name) / 'other machine codex home'
        home.mkdir()
        config = home / 'config.toml'
        config.write_text('sandbox_mode = "workspace-write"\ndeveloper_instructions = "Existing guidance"\n[sandbox_workspace_write]\nwritable_roots = ["/tmp/existing"]\nnetwork_access = true\n')
        hooks = home / 'hooks.json'
        foreign = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'existing-user-command'}]}]}}
        hooks.write_text(json.dumps(foreign))
        installer.install(home, Path(sys.executable), enable_stop=True)
        import tomllib
        configured = config.read_bytes()
        self.assertIn('Existing guidance', tomllib.loads(configured.decode())['developer_instructions'])
        current_hooks = json.loads(hooks.read_text())
        self.assertEqual(current_hooks['hooks']['Stop'][0], foreign['hooks']['Stop'][0])
        self.assertIn('EncodedCommand' if os.name == 'nt' else "'", current_hooks['hooks']['SessionStart'][0]['hooks'][0]['command'])
        skill = home / 'skills/work-checkpoint'
        hashes = {f: hashlib.sha256((skill / f).read_bytes()).hexdigest() for f in installer.FILES}
        result = installer.install(home, Path(sys.executable), upgrade=True, expected=hashes, enable_stop=True)
        self.assertEqual(result['changed_files'], [])
        self.assertEqual(config.read_bytes(), configured)
        (skill / 'SKILL.md').write_text('Concurrent customization')
        with self.assertRaises(ValueError):
            installer.install(home, Path(sys.executable), upgrade=True, expected=hashes)
        self.assertEqual(config.read_bytes(), configured)

    def test_installer_rejects_symlinked_parent_and_nonmatching_permission_profile(self):
        target = Path(self.temp.name) / 'real'
        target.mkdir()
        link = Path(self.temp.name) / 'linked'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Creating a Windows symlink requires separate OS permission')
        with self.assertRaises(ValueError):
            installer.safe_path(link / 'config.toml')
        with self.assertRaises(ValueError):
            installer.configure('sandbox_mode = "read-only"\n')

    def test_release_archive_is_an_exact_code_allowlist_without_private_operator_data(self):
        spec = importlib.util.spec_from_file_location('builder', Path(__file__).parent / 'build_package.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        result = builder.build(Path(__file__).parent, Path(self.temp.name) / 'dist')
        with tarfile.open(result['archive']) as tar:
            prefix = 'work-checkpoint-workflow-0.3.4/'
            names = [m.name.removeprefix(prefix) for m in tar.getmembers()]
            self.assertEqual(set(names), set(builder.FILES) | {'manifest.json'})
            manifest = json.load(tar.extractfile(prefix + 'manifest.json'))
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(tar.extractfile(prefix + name).read()).hexdigest(), digest)
            self.assertFalse(any('backups' in name or 'destination' in name or 'catchup' in name for name in names))

    def test_unicode_markdown_digest_is_utf8_lf_on_every_os(self):
        prepared = self.call('prepare', payload={**self.summary, 'goal': 'Résumé handoff 東京'})
        content = Path(prepared['file']).read_bytes()
        self.assertNotIn(b'\r\n', content)
        self.assertIn('東京'.encode('utf-8'), content)
        self.assertEqual(hashlib.sha256(content).hexdigest(), prepared['sha256'])

    def test_changed_checkpoint_hook_invocation_is_reconciled_without_duplicates(self):
        home = Path(self.temp.name) / 'codex'
        hooks = installer.proposed_hooks({}, home, Path(sys.executable), True)
        hooks['hooks']['SessionStart'][0]['hooks'][0]['command'] = 'old-checkpoint-invocation'
        with self.assertRaisesRegex(ValueError, 'different invocation'):
            installer.proposed_hooks(hooks, home, Path(sys.executable), True)

    def test_upgrade_helper_can_execute_at_each_intermediate_source_write(self):
        home = Path(self.temp.name) / 'old-codex-home'
        old_skill = home / 'skills/work-checkpoint'
        (old_skill / 'scripts').mkdir(parents=True)
        (old_skill / 'SKILL.md').write_text('Old compatible guidance')
        (old_skill / 'scripts/checkpoint.py').write_text('Old helper')
        (home / 'config.toml').write_text('sandbox_mode = "workspace-write"\n')
        hashes = {f: hashlib.sha256((old_skill / f).read_bytes()).hexdigest()
                  for f in ('SKILL.md', 'scripts/checkpoint.py')}
        original = installer.atomic
        observed = []
        def checked(path, value):
            original(path, value)
            if path == old_skill / 'scripts/checkpoint.py' or path == old_skill / 'SKILL.md':
                # An active session may invoke the helper between file replacements.
                result = subprocess.run([sys.executable, str(old_skill / 'scripts/checkpoint.py'), 'session-start'],
                    input=json.dumps({'hook_event_name': 'SessionStart'}), text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed.append(path.name)
            if path == home / 'hooks.json':
                self.assertEqual(observed, ['checkpoint.py', 'SKILL.md'])
        with patch.object(installer, 'atomic', side_effect=checked):
            installer.install(home, Path(sys.executable), upgrade=True, expected=hashes)
        self.assertEqual(observed, ['checkpoint.py', 'SKILL.md'])


if __name__ == '__main__':
    unittest.main()
