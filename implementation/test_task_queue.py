import concurrent.futures
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('queue_installer',ROOT/'install_task_queue.py')
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
qmod=install.engine
AT=dt.datetime(2026,11,2,15,0,tzinfo=dt.timezone.utc)


def cfg(scope='personal',ident='private'):
    return {'schema_version':1,'queue_id':ident,'scope':scope,'project_id':ident,'arbiter_id':'one-machine',
            'coordinators':['coordinator'],'destination':{'page_id':'page_'+'1'*32,'space_id':None if scope=='personal' else 'page_space_'+'2'*32,'url':'https://chatgpt.com/space/page_'+'1'*32},
            'approved_audience':[{'principal_type':'user','principal_id':'owner','role':'owner'}]}


class Queues(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.c=cfg();self.q=qmod.Queue(self.root/'queues',self.c);self.sequence=0
        self.task={'id':'task-a','scope':'personal','project_id':'private','kind':'review','action':'Review fixture',
                   'owner':'coordinator','consumer':'consumer','source_refs':['https://example.test/source'],
                   'acceptance':['review recorded','results read back'],'authority':{'requirements':['fixture-only user approval'],
                   'allowed_actions':['read fixture'],'approval_state':'granted'},'due_at':'2026-11-02T09:45:00-05:00',
                   'timezone':'America/New_York','timing':'exact','dependencies':[]}

    def tearDown(self):self.tmp.cleanup()

    def op(self,op,actor='coordinator',at=AT,**extra):
        self.sequence+=1
        r={'operation_id':'op-'+str(self.sequence),'op':op,'actor':actor,'evidence':'fixture receipt',**extra}
        if op not in ('request','mirror'):
            r.setdefault('id','task-a');r.setdefault('expected_revision',self.q.state()['tasks']['task-a']['revision'])
        return self.q.apply(r,'one-machine',at)

    def requested(self):return self.op('request',task=self.task)

    def accepted(self):
        self.requested();self.op('ack','consumer');return self.op('accept','consumer')

    def claim_data(self):
        return {'authority_evidence':'verified fixture authority','input_review':{'queue_page_id':self.c['destination']['page_id'],
                'reviewed_at':AT.isoformat(),'human_requests_reconciled':True,'evidence':'native fixture input review'}}

    def claimed(self):
        self.accepted();return self.op('claim','consumer',**self.claim_data())

    def test_lifecycle_and_evidence_required(self):
        self.assertEqual(self.requested()['status'],'requested')
        with self.assertRaises(ValueError):self.op('claim','consumer',**self.claim_data())
        self.assertEqual(self.op('ack','consumer')['status'],'acknowledged')
        with self.assertRaises(ValueError):self.op('complete','consumer',acceptance_verified=True)
        self.op('accept','consumer');claimed=self.op('claim','consumer',**self.claim_data())
        token=claimed['claim']['token']
        with self.assertRaises(ValueError):self.op('complete','consumer',claim_token=token,acceptance_verified=True,acceptance_evidence={'review recorded':'x'})
        done=self.op('complete','consumer',claim_token=token,acceptance_verified=True,acceptance_evidence={k:'actual fixture evidence' for k in self.task['acceptance']})
        self.assertEqual(done['status'],'completed');self.assertTrue(done['completion'])
        self.assertEqual(len(self.q.state()['events']),5)

    def test_concurrent_claims_only_one(self):
        task=self.accepted()
        def claim(i):
            try:return self.q.apply({'operation_id':'claim-'+str(i),'op':'claim','actor':'consumer','evidence':'fixture',
                 'id':'task-a','expected_revision':task['revision'],**self.claim_data()},'one-machine',AT)['status']
            except ValueError:return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(claim,range(8)))
        self.assertEqual(results.count('in_progress'),1)

    def test_idempotent_operation_content_conflict_and_cancelled_replay(self):
        r={'operation_id':'stable','op':'request','actor':'coordinator','evidence':'fixture','task':self.task}
        first=self.q.apply(r,'one-machine',AT)
        self.assertEqual(first,self.q.apply(r,'one-machine',AT))
        with self.assertRaises(ValueError):self.q.apply(dict(r,evidence='different'),'one-machine',AT)
        self.op('cancel')
        replay=self.q.apply(r,'one-machine',AT)
        self.assertTrue(replay['historical_result']);self.assertEqual(replay['current_status'],'cancelled')

    def test_claim_cancellation_fences_token(self):
        claim=self.claimed();cancel=self.op('cancel')
        self.assertTrue(cancel['execution_stop_required'])
        with self.assertRaises(ValueError):self.op('complete','consumer',claim_token=claim['claim']['token'],acceptance_verified=True,acceptance_evidence={k:'evidence' for k in self.task['acceptance']})
        with self.assertRaises(ValueError):self.op('recover',prior_execution_stopped=True,reconciliation_evidence='x')

    def test_stale_recovery_is_explicit_and_reaccepts(self):
        self.claimed();late=AT+dt.timedelta(hours=1)
        self.assertTrue(self.q.check('consumer',late)['items'][0]['claim_expired'])
        with self.assertRaises(ValueError):self.op('recover',at=late)
        recovered=self.op('recover',at=late,prior_execution_stopped=True,reconciliation_evidence='prior operation reconciled stopped')
        self.assertEqual(recovered['status'],'requested');self.assertIsNone(recovered['accepted'])

    def test_ack_is_not_acceptance_wrong_consumer_no_authority(self):
        self.requested()
        with self.assertRaises(ValueError):self.op('ack','someone-else')
        self.op('ack','consumer')
        with self.assertRaises(ValueError):self.op('claim','consumer',**self.claim_data())
        self.op('edit',patch={'authority':dict(self.task['authority'],approval_state='pending')})
        self.op('ack','consumer');self.op('accept','consumer')
        with self.assertRaises(ValueError):self.op('claim','consumer',**self.claim_data())

    def test_dependencies_and_human_edit_conflicts(self):
        self.task['dependencies']=['not-finished'];self.accepted()
        with self.assertRaises(ValueError):self.op('claim','consumer',**self.claim_data())
        self.op('edit',patch={'action':'Human changed action'})
        with self.assertRaises(ValueError):self.op('ack','consumer',expected_revision=3)
        self.assertEqual(self.q.state()['tasks']['task-a']['action'],'Human changed action')

    def test_mirrors_cannot_execute_or_duplicate(self):
        m={'id':'project-task','authority_queue_id':'project-a','authority_url':'https://chatgpt.com/space/page_'+'3'*32}
        self.op('mirror',mirror=m)
        for op in ('claim','complete','ack'):
            with self.assertRaises(ValueError):self.q.apply({'operation_id':'mirror-'+op,'op':op,'id':m['id'],'expected_revision':1,'actor':'consumer','evidence':'fixture'},'one-machine',AT)
        with self.assertRaises(ValueError):self.op('mirror',mirror=m)

    def test_private_project_separation_and_binding(self):
        project=qmod.Queue(self.root/'queues',cfg('project','project-a'))
        with self.assertRaises(ValueError):project.apply({'op':'request','operation_id':'a','actor':'coordinator','evidence':'fixture','task':self.task},'one-machine',AT)
        self.requested();changed=copy.deepcopy(self.c);changed['arbiter_id']='another-machine'
        with self.assertRaises(ValueError):qmod.Queue(self.root/'queues',changed).state()
        with self.assertRaises(ValueError):self.q.apply({'operation_id':'b','op':'request','actor':'coordinator','evidence':'fixture','task':self.task},'another-machine',AT)

    def test_due_timezone_dst_and_unknown_time(self):
        self.requested();self.assertTrue(self.q.check(at=AT)['items'][0]['overdue'])
        for due in ('2026-11-02T09:45:00','2026-11-02T09:45:00-04:00'):
            t=dict(self.task,due_at=due)
            with self.assertRaises(ValueError):qmod.validate_task(t,self.c)
        t=dict(self.task);t.pop('due_at');t['timing']='unspecified'
        self.assertNotIn('due_at',qmod.validate_task(t,self.c))

    def test_fresh_human_review_required(self):
        self.accepted();data=self.claim_data();data['input_review']['reviewed_at']=(AT-dt.timedelta(minutes=6)).isoformat()
        with self.assertRaises(ValueError):self.op('claim','consumer',**data)

    def test_credentials_and_date_only_deadline(self):
        with self.assertRaises(ValueError):qmod.validate_task(dict(self.task,action='sk-'+'a'*32),self.c)
        task=dict(self.task,due_date='2026-11-06',timing='unspecified');task.pop('due_at')
        self.task=task;self.requested()
        self.assertFalse(self.q.check(at=AT)['items'][0]['overdue'])
        self.assertTrue(self.q.check(at=AT+dt.timedelta(days=5))['items'][0]['overdue'])

    def test_superseded_snapshot_cannot_be_claimed(self):
        self.requested();pub=qmod.publication(self.q,'prepare-publication',None)
        self.op('cancel')
        proof={'page_id':self.c['destination']['page_id'],'space_id':None,'audience':self.c['approved_audience'],
               'complete':True,'observed_at':qmod.now().isoformat()}
        with self.assertRaises(ValueError):qmod.publication(self.q,'claim-publication',{'id':pub['id'],'access':proof})

    def test_snapshots_do_not_leak_claim_tokens(self):
        token=self.claimed()['claim']['token'];snapshot=self.q.snapshot(AT)
        self.assertNotIn(token,json.dumps(snapshot));self.assertNotIn('operations',snapshot)

    def test_publication_dedup_uncertainty_content_and_access(self):
        self.requested();pub=qmod.publication(self.q,'prepare-publication',None)
        self.assertEqual(pub,qmod.publication(self.q,'prepare-publication',None))
        proof={'page_id':self.c['destination']['page_id'],'space_id':None,'audience':self.c['approved_audience'],
               'complete':True,'observed_at':qmod.now().isoformat()}
        with self.assertRaises(ValueError):qmod.publication(self.q,'claim-publication',{'id':pub['id'],'access':dict(proof,audience=[])})
        qmod.publication(self.q,'claim-publication',{'id':pub['id'],'access':proof})
        qmod.publication(self.q,'uncertain-publication',{'id':pub['id']})
        with self.assertRaises(ValueError):qmod.publication(self.q,'claim-publication',{'id':pub['id'],'access':proof})
        receipt={'id':pub['id'],'page_id':'page_'+'4'*32,'url':'https://chatgpt.com/space/page_'+'4'*32,
                 'parent_page_id':self.c['destination']['page_id'],'sha256':pub['sha256'],'content_verified':True,
                 'access':dict(proof,page_id='page_'+'4'*32)}
        with self.assertRaises(ValueError):qmod.publication(self.q,'ack-publication',dict(receipt,sha256='wrong'))
        self.assertEqual(qmod.publication(self.q,'ack-publication',receipt)['state'],'published')

    def test_hooks_read_only_route_boundaries_and_no_payload_file_reads(self):
        config_path=self.root/'config.json';qmod.write(config_path,self.c)
        routes=self.root/'routes.json';qmod.write(routes,{'enabled':True,'default':{'config':str(config_path),'store':str(self.root/'queues')},'projects':[]})
        event={'session_id':'consumer','cwd':'/tmp/other','transcript_path':'/denied/never-open'}
        before=set(self.root.rglob('*'))
        self.assertIn('hookSpecificOutput',qmod.hook(routes,event,True))
        self.assertEqual(before,set(self.root.rglob('*')))
        self.requested();self.assertIn('systemMessage',qmod.hook(routes,event))
        event['session_id']='other';self.assertEqual(qmod.hook(routes,event),{})
        qmod.write(routes,{'enabled':False});self.assertEqual(qmod.hook(routes,event,True),{})

    def test_symlink_store_rejected(self):
        if os.name=='nt':self.skipTest('POSIX symlink fixture')
        self.root.joinpath('queues').symlink_to(self.root/'actual',target_is_directory=True)
        with self.assertRaises(ValueError):self.requested()

    @unittest.skipUnless(os.name == 'nt', 'Native Windows path comparison')
    def test_windows_project_route_case_slashes_and_boundaries(self):
        private_config = self.root / 'private.json'
        project_config = self.root / 'project.json'
        project = cfg('project', 'project-a')
        project['destination']['page_id'] = 'page_' + '3' * 32
        project['destination']['url'] = 'https://chatgpt.com/space/' + project['destination']['page_id']
        qmod.write(private_config, self.c)
        qmod.write(project_config, project)
        prefix = str(self.root / 'Project space caf\u00e9')
        route = {'folder_prefixes': [prefix], 'config': str(project_config), 'store': str(self.root / 'project-cache')}
        routes = self.root / 'routes.json'
        settings = {'enabled': True, 'default': {'config': str(private_config), 'store': str(self.root / 'private-cache')}, 'projects': [route]}
        qmod.write(routes, settings)
        before = set(self.root.rglob('*'))
        for cwd in (prefix.swapcase(), prefix.replace('\\', '/'), prefix + '\\', prefix.swapcase() + '/child'):
            with self.subTest(cwd=cwd):
                result = qmod.hook(routes, {'cwd': cwd}, True)['hookSpecificOutput']['additionalContext']
                self.assertIn('Assigned queue: ' + project['destination']['url'], result)
                self.assertNotIn('Assigned queue: ' + self.c['destination']['url'], result)
        sibling = qmod.hook(routes, {'cwd': prefix + '-other'}, True)['hookSpecificOutput']['additionalContext']
        self.assertIn('Assigned queue: ' + self.c['destination']['url'], sibling)
        self.assertEqual(before, set(self.root.rglob('*')))
        settings['projects'] = [dict(route, folder_prefixes=[prefix.replace('\\', '/') + '/'])]
        qmod.write(routes, settings)
        normalized = qmod.hook(routes, {'cwd': prefix.swapcase()}, True)['hookSpecificOutput']['additionalContext']
        self.assertIn('Assigned queue: ' + project['destination']['url'], normalized)
        settings['projects'].append(dict(route, folder_prefixes=[prefix.swapcase().replace('\\', '/')]))
        qmod.write(routes, settings)
        ambiguous = qmod.hook(routes, {'cwd': prefix}, True)
        self.assertIn('ambiguous', ambiguous['systemMessage'])
        self.assertNotIn('hookSpecificOutput', ambiguous)


class Installation(unittest.TestCase):
    def test_independent_hook_combinations(self):
        for checkpoint in (False,True):
            existing={'hooks':{'SessionStart':[{'hooks':[{'type':'command','command':'checkpoint-session'}]}]}} if checkpoint else {'hooks':{}}
            for queue in (False,True):
                result=install.hooks(existing,Path('/synthetic/codex'),Path('/synthetic/python'),queue)
                handlers=[h for groups in result['hooks'].values() for g in groups for h in g['hooks']]
                cmds=[h['command'] for h in handlers]
                self.assertEqual('checkpoint-session' in cmds,checkpoint)
                self.assertEqual(sum(h.get('statusMessage') in ('Load task queue guidance','Check assigned task queue') for h in handlers),2 if queue else 0)
                self.assertEqual(install.hooks(result,Path('/synthetic/codex'),Path('/synthetic/python'),False),existing)

    def test_encoded_windows_hook_change_is_not_duplicated_or_silently_removed(self):
        command=install.engine.io.hook_command
        def encoded(python,script,verb):return command(python,script,verb,platform='nt')
        with patch.object(install.engine.io,'hook_command',side_effect=encoded):
            first=install.hooks({'hooks':{}},Path('/synthetic/codex'),Path('/python-one.exe'))
            self.assertEqual(first,install.hooks(first,Path('/synthetic/codex'),Path('/python-one.exe')))
            with self.assertRaisesRegex(ValueError,'Conflicting queue invocation'):
                install.hooks(first,Path('/synthetic/codex'),Path('/python-two.exe'))
            with self.assertRaisesRegex(ValueError,'Conflicting queue invocation'):
                install.hooks(first,Path('/synthetic/codex'),Path('/python-two.exe'),False)

    def test_install_disable_and_guarded_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)/'codex';qmod.io.private_dir(home)
            raw='developer_instructions = "Existing checkpoint guidance"\nsandbox_mode = "workspace-write"\n[sandbox_workspace_write]\nwritable_roots = '+json.dumps([str(home/'checkpoints')])+'\n'
            (home/'config.toml').write_text(raw);(home/'hooks.json').write_text('{"hooks":{"SessionStart":[{"hooks":[{"command":"checkpoint"}]}]}}')
            before=(home/'hooks.json').read_bytes()
            result=install.install(home,Path(os.sys.executable))
            self.assertIn(install.MARKER,(home/'config.toml').read_text())
            self.assertEqual(install.install(home,Path(os.sys.executable))['changed_files'],[])
            disabled=install.install(home,Path(os.sys.executable),False)
            self.assertNotIn(install.MARKER,(home/'config.toml').read_text())
            self.assertEqual(json.loads((home/'hooks.json').read_text()),json.loads(before))
            install.rollback(Path(disabled['backup']))
            install.rollback(Path(result['backup']))
            self.assertEqual((home/'config.toml').read_text(),raw)
            self.assertEqual((home/'hooks.json').read_bytes(),before)

    def test_managed_permission_profile_not_rewritten(self):
        with self.assertRaises(ValueError):install.configure('default_permissions="managed"\n',Path('/synthetic'))


if __name__=='__main__':unittest.main()
