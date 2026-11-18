"""Capacity, durable history and same-arbiter rollover regression fixtures."""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_task_queue import cfg, qmod, AT

h = qmod.history


class History(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.c = cfg()
        self.q = qmod.Queue(self.base, self.c)
        self.n = 0
        self.task = {'id':'fixture','scope':'personal','project_id':'private','kind':'review',
                     'action':'Review fixture','owner':'coordinator','consumer':'consumer',
                     'source_refs':['https://example.test/source'],'acceptance':['evidence'],
                     'authority':{'requirements':['fixture authority'],'allowed_actions':['read fixture'],
                                  'approval_state':'granted'}}
        self.request = self.op('request', task=self.task)
        self.q.apply(self.request, 'one-machine', AT)

    def tearDown(self):
        self.temp.cleanup()

    def op(self, op, actor='coordinator', **fields):
        self.n += 1
        return {'operation_id':'op-'+str(self.n),'op':op,'actor':actor,
                'evidence':'fixture evidence',**fields}

    def transition(self, op, **fields):
        r = self.op(op, 'consumer', id='fixture',
                    expected_revision=self.q.state()['tasks']['fixture']['revision'], **fields)
        return self.q.apply(r, 'one-machine', AT)

    def grant(self):
        self.transition('ack'); self.transition('accept')
        self.claim_request = self.op('claim','consumer',id='fixture',expected_revision=3,
            authority_evidence='fixture approved',input_review={
            'queue_page_id':self.c['destination']['page_id'],'reviewed_at':AT.isoformat(),
            'human_requests_reconciled':True,'evidence':'native fixture review'})
        return self.q.apply(self.claim_request,'one-machine',AT)

    def guard(self, q=None):
        q = q or self.q
        return {'expected_sha256':h.checksum(h.raw_read(q.path)),
                'expected_revision':q.state()['revision']}

    def missing_history_error(self):
        # Windows rejects the missing path during private ACL validation first.
        if qmod.os.name == 'nt':
            return self.assertRaisesRegex(ValueError, 'Windows ACL check failed')
        return self.assertRaises(OSError)

    def schema2(self):
        logical = self.q.state()
        logical['publications'] = {'kept':{'markdown':'exact text\n'+'x'*10000,'state':'published'}}
        migration = {'original':h.put(self.q.root,h.encoded(logical),backup=True),
                     'revision':logical['revision']}
        physical = copy.deepcopy(logical)
        physical['publications'] = {k:h.put(self.q.root,h.encoded(v))
                                    for k,v in logical['publications'].items()}
        physical.update(schema_version=2,history_migration=migration)
        qmod.write(self.q.path,physical)
        return logical

    def test_live_claim_all_logical_fields_and_exact_restore(self):
        grant = self.grant(); before = self.q.state(); raw = h.raw_read(self.q.path)
        h.migrate(self.q,self.guard(),'one-machine')
        self.assertEqual(json.loads(h.raw_read(self.q.path))['schema_version'],3)
        self.assertEqual(self.q.state(),before)
        self.assertEqual(self.q.state()['tasks']['fixture']['claim'],grant['claim'])
        self.assertTrue(h.verify(self.q)['matches_original'])
        h.restore(self.q,self.guard(),'one-machine')
        self.assertEqual(h.raw_read(self.q.path),raw)

    def test_schema2_upgrade_restore_and_subsequent_write_guard(self):
        before = self.schema2(); raw = h.raw_read(self.q.path)
        h.migrate(self.q,self.guard(),'one-machine')
        self.assertEqual(self.q.state(),before)
        h.restore(self.q,self.guard(),'one-machine')
        self.assertEqual(h.raw_read(self.q.path),raw)
        self.transition('ack')
        self.assertEqual(json.loads(h.raw_read(self.q.path))['schema_version'],2)
        h.migrate(self.q,self.guard(),'one-machine'); self.transition('accept')
        with self.assertRaisesRegex(ValueError,'Later queue'):
            h.restore(self.q,self.guard(),'one-machine')

    def test_near_limit_history_shrinks_without_deleting_replays(self):
        if qmod.os.name == 'nt':
            self.skipTest('Bulk 1000-object regression uses POSIX; native NTFS acceptance is separate')
        s = self.q.state()
        for n in range(1000):
            s['operations']['retained-'+str(n)] = {'digest':'a'*64,
                'result':{'id':'fixture','detail':'x'*8100}}
        qmod.write(self.q.path,s); raw = h.raw_read(self.q.path)
        self.assertGreater(len(raw),8_000_000)
        h.migrate(self.q,self.guard(),'one-machine')
        self.assertLess(len(h.raw_read(self.q.path)),250_000)
        self.assertEqual(self.q.state(),s)
        self.assertEqual(self.q.apply(self.request,'one-machine',AT),
                         s['operations'][self.request['operation_id']]['result'])
        h.restore(self.q,self.guard(),'one-machine')
        self.assertEqual(h.raw_read(self.q.path),raw)

    def test_missing_tampered_and_invalid_object_refs_fail_closed(self):
        h.migrate(self.q,self.guard(),'one-machine')
        state = json.loads(h.raw_read(self.q.path))
        obj = h.object_path(self.q.root,next(iter(state['operations'].values())))
        raw = obj.read_bytes(); obj.write_bytes(raw+b'x')
        with self.assertRaisesRegex(ValueError,'size/hash'): self.q.state()
        obj.write_bytes(raw); obj.unlink()
        with self.missing_history_error(): self.q.state()
        with self.assertRaisesRegex(ValueError,'reference'):
            h.get(self.q.root,{'sha256':'../../escape','bytes':1})

    def test_symlink_refused(self):
        if qmod.os.name == 'nt': self.skipTest('POSIX symlink fixture')
        target = self.base/'outside'; target.mkdir()
        (self.q.root/'history').symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Symlink'): h.put(self.q.root,b'{}')

    def test_stale_guards_wrong_arbiter_and_no_blind_migration_retry(self):
        raw = h.raw_read(self.q.path)
        for guard,actor in [(dict(self.guard(),expected_revision=999),'one-machine'),
                            (dict(self.guard(),expected_sha256='0'*64),'one-machine'),
                            (self.guard(),'other-machine')]:
            with self.assertRaises(ValueError): h.migrate(self.q,guard,actor)
            self.assertEqual(h.raw_read(self.q.path),raw)
        h.migrate(self.q,self.guard(),'one-machine')
        with self.assertRaises(ValueError): h.migrate(self.q,self.guard(),'one-machine')

    def test_failure_before_and_after_primary_replace_is_reconcilable(self):
        original = h.raw_read(self.q.path); real = h.atomic_bytes
        def fail_before(path, raw):
            if path == self.q.path: raise OSError('fixture before replace')
            real(path,raw)
        with patch.object(h,'atomic_bytes',side_effect=fail_before):
            with self.assertRaises(OSError): h.migrate(self.q,self.guard(),'one-machine')
        self.assertEqual(h.raw_read(self.q.path),original)
        def fail_after(path, raw):
            real(path,raw)
            if path == self.q.path: raise OSError('fixture after replace')
        with patch.object(h,'atomic_bytes',side_effect=fail_after):
            with self.assertRaises(OSError): h.migrate(self.q,self.guard(),'one-machine')
        self.assertTrue(h.verify(self.q)['matches_original'])
        h.restore(self.q,self.guard(),'one-machine')
        self.assertEqual(h.raw_read(self.q.path),original)

    def test_utf8_byte_limit_and_exact_limit_read(self):
        raw = h.raw_read(self.q.path)
        with self.assertRaises(ValueError): qmod.write(self.q.path,{'text':'é'*(h.LIMIT//2)})
        self.assertEqual(h.raw_read(self.q.path),raw)
        h.atomic_bytes(self.q.root/'exact.bin',b'a'*h.LIMIT)
        self.assertEqual(len(h.raw_read(self.q.root/'exact.bin')),h.LIMIT)

    def test_preflight_measures_overflow_without_claim_or_write(self):
        self.transition('ack'); self.transition('accept')
        r = self.op('claim','consumer',id='fixture',expected_revision=3,
            authority_evidence='fixture',input_review={'queue_page_id':self.c['destination']['page_id'],
            'reviewed_at':AT.isoformat(),'human_requests_reconciled':True,'evidence':'fixture'})
        raw = h.raw_read(self.q.path)
        result = self.q.apply(r,'one-machine',AT,dry_run=True)
        self.assertTrue(result['fits']); self.assertNotIn('token',json.dumps(result))
        with patch.object(h,'LIMIT',len(raw)+1):
            self.assertFalse(self.q.apply(r,'one-machine',AT,dry_run=True)['fits'])
            with self.assertRaisesRegex(ValueError,'8 MiB'): self.q.apply(r,'one-machine',AT)
        self.assertEqual(h.raw_read(self.q.path),raw)

    def test_frozen_marker_fences_every_mutating_entrypoint(self):
        h.migrate(self.q,self.guard(),'one-machine')
        qmod.write(self.q.root/'FROZEN-SEGMENT.json',{'partial':'intent also fences'})
        raw = h.raw_read(self.q.path)
        calls = [lambda:self.q.apply(self.request,'one-machine',AT),
                 lambda:self.q.apply(self.request,'one-machine',AT,dry_run=True),
                 lambda:qmod.publication(self.q,'prepare-publication',None),
                 lambda:h.migrate(self.q,self.guard(),'one-machine'),
                 lambda:h.restore(self.q,self.guard(),'one-machine')]
        for call in calls:
            with self.assertRaisesRegex(ValueError,'frozen'): call()
        self.assertEqual(h.raw_read(self.q.path),raw)
        self.assertTrue(h.status(self.q)['frozen'])

    def successor(self):
        c = copy.deepcopy(self.c); c['queue_id'] = 'successor'
        c['destination']['page_id'] = 'page_'+'3'*32
        c['destination']['url'] = 'https://chatgpt.com/space/'+c['destination']['page_id']
        q = qmod.Queue(self.base,c); qmod.io.private_dir(q.root)
        state = self.q.state()
        state.update(queue_id='successor',binding=qmod.digest(c),events=[],operations={},publications={})
        qmod.write(q.path,state); raw = h.raw_read(self.q.path)
        qmod.write(q.root/'SEGMENT-CONTINUITY.json',{'schema_version':1,'sole_arbiter':'one-machine',
            'previous':{'queue_id':self.c['queue_id'],'root':str(self.q.root),
                        'state_sha256':h.checksum(raw),'state_bytes':len(raw),'revision':self.q.state()['revision']},
            'successor':{'queue_id':'successor','root':str(q.root)}})
        qmod.write(self.q.root/'FROZEN-SEGMENT.json',{'previous_state_sha256':h.checksum(raw),
            'successor_queue_id':'successor','successor_root':str(q.root),
            'sole_arbiter':'one-machine','all_writes_must_use_successor':True})
        return q

    def test_successor_preserves_claim_completion_and_deduplicates_old_operations(self):
        grant = self.grant(); q = self.successor(); raw = h.raw_read(q.path)
        result = q.apply(self.request,'one-machine',AT)
        self.assertTrue(result['historical_result']); self.assertNotIn('claim',result)
        self.assertEqual(h.raw_read(q.path),raw)
        with self.assertRaisesRegex(ValueError,'different content'):
            q.apply(dict(self.request,evidence='changed'),'one-machine',AT)
        self.assertEqual(q.state()['tasks']['fixture']['claim'],grant['claim'])
        result = q.apply(self.op('complete','consumer',id='fixture',expected_revision=4,
            claim_token=grant['claim']['token'],acceptance_verified=True,
            acceptance_evidence={'evidence':'verified fixture'}),'one-machine',AT)
        self.assertEqual(result['status'],'completed')

    def test_successor_claim_retry_respects_expiry(self):
        self.grant(); q = self.successor()
        self.assertIn('token',q.apply(self.claim_request,'one-machine',AT)['claim'])
        expired = q.apply(self.claim_request,'one-machine',AT+dt.timedelta(hours=2))
        self.assertTrue(expired['claim_expired']); self.assertNotIn('token',expired['claim'])

    def test_successor_changed_predecessor_or_escape_fails_closed(self):
        q = self.successor(); raw = h.raw_read(self.q.path)
        h.atomic_bytes(self.q.path,raw+b' ')
        with self.assertRaisesRegex(ValueError,'predecessor changed'):
            q.apply(self.op('ack','consumer',id='fixture',expected_revision=1),'one-machine',AT)
        h.atomic_bytes(self.q.path,raw)
        p = q.root/'SEGMENT-CONTINUITY.json'; note = json.loads(h.raw_read(p))
        note['previous']['queue_id'] = '../escape'; qmod.write(p,note)
        with self.assertRaisesRegex(ValueError,'predecessor'): q.apply(self.request,'one-machine',AT)

    def test_schema3_new_writes_retain_old_immutable_objects(self):
        h.migrate(self.q,self.guard(),'one-machine')
        old = set((self.q.root/'history/objects').iterdir())
        self.transition('ack')
        self.assertTrue(old <= set((self.q.root/'history/objects').iterdir()))
        self.assertTrue(self.q.apply(self.request,'one-machine',AT)['historical_result'])

    def test_verify_checks_retained_predecessor_publication_objects(self):
        self.schema2(); q = self.successor()
        physical = json.loads(h.raw_read(self.q.path))
        ref = next(iter(physical['publications'].values()))
        h.object_path(self.q.root,ref).unlink()
        with self.missing_history_error(): h.verify(q)

    def test_successor_cycle_and_lost_claim_are_refused(self):
        self.grant(); q = self.successor()
        raw = h.raw_read(q.path); s = q.state()
        s['tasks']['fixture']['claim']['token'] = 'incorrect-carried-claim'
        qmod.write(q.path,s)
        with self.assertRaisesRegex(ValueError,'lost or rewound'):
            q.apply(self.request,'one-machine',AT)
        h.atomic_bytes(q.path,raw)
        p = q.root/'SEGMENT-CONTINUITY.json'; note = json.loads(h.raw_read(p))
        note['previous']['queue_id'] = 'successor'; qmod.write(p,note)
        with self.assertRaisesRegex(ValueError,'cyclic'):
            q.apply(self.request,'one-machine',AT)

    def test_preflight_schema3_equals_actual_write_and_history_is_private(self):
        h.migrate(self.q,self.guard(),'one-machine')
        r = self.op('ack','consumer',id='fixture',expected_revision=1)
        result = self.q.apply(r,'one-machine',AT,dry_run=True)
        self.q.apply(r,'one-machine',AT)
        self.assertEqual(result['projected_state_bytes'],len(h.raw_read(self.q.path)))
        for p in (self.q.root/'history').rglob('*'):
            qmod.io.assert_private(p)

    def test_hooks_surface_pressure_without_network_or_new_timers(self):
        routes = self.base/'routes.json'; config_path = self.base/'config.json'
        qmod.write(config_path,self.c)
        qmod.write(routes,{'enabled':True,'projects':[],
            'default':{'config':str(config_path),'store':str(self.base)}})
        raw = h.raw_read(self.q.path)
        with patch.object(h,'LIMIT',int(len(raw)/.96)):
            check = self.q.check()
            self.assertEqual(check['storage']['pressure'],'critical')
            start = qmod.hook(routes,{'session_id':'unassigned'},True)
            self.assertIn('storage pressure: critical',start['hookSpecificOutput']['additionalContext'])
            stop = qmod.hook(routes,{'session_id':'unassigned'})
            self.assertIn('storage pressure is critical',stop['systemMessage'])
        self.assertEqual(h.raw_read(self.q.path),raw)


if __name__ == '__main__': unittest.main()
