#!/usr/bin/env python3
"""Install/disable queue hooks independently; preserve checkpoint and unrelated settings."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tomllib

SOURCE = Path(__file__).parent / 'task-queue'
spec = importlib.util.spec_from_file_location('task_queue_engine', SOURCE / 'scripts/task_queue.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
FILES = ('scripts/queue_history.py', 'scripts/platform_io.py', 'scripts/task_queue.py', 'references/protocol.md', 'references/storage.md', 'SKILL.md')
MARKER = '[Task queue pickup]'


def configure(text, home, enabled=True):
    before = tomllib.loads(text)
    if before.get('sandbox_mode') != 'workspace-write' or 'default_permissions' in before:
        raise ValueError('Managed/other permission profiles require a targeted adapter; no permission changes')
    store = str(home / 'checkpoints')
    if store not in before.get('sandbox_workspace_write', {}).get('writable_roots', []):
        raise ValueError('Approve the private checkpoint root separately; installer will not widen permissions')
    old = before.get('developer_instructions', '')
    instruction = (MARKER + '\nAt local session start read ' + str(home / 'skills/task-queue/SKILL.md')
                   + ' once for explicitly assigned queues. Queue pickup is separate from checkpoints. '
                   'Check current queue access and human requests before acting; require independent authority '
                   'and one designated arbiter claim. Preserve existing schedules and coordinator ownership. '
                   'Cloud tasks require explicit bootstrap; installation does not grant dispatch or publication authority.\n')
    if MARKER in old:
        if str(home / 'skills/task-queue/SKILL.md') not in old:
            raise ValueError('Conflicting installed queue guidance')
        if enabled:return text
        if instruction not in old:raise ValueError('Queue instruction changed; reconcile before disabling')
        new=old.replace('\n\n'+instruction,'').replace(instruction,'')
    elif not enabled:return text
    else:new = old + '\n\n' + instruction if old else instruction
    match = re.search(r'^developer_instructions\s*=', text, re.M)
    if match:
        if re.search(r'^\[',text[:match.start()],re.M):
            raise ValueError('Instruction assignment is not top-level')
        statement = ''
        for line in text[match.start():].splitlines(keepends=True):
            statement += line
            try:
                if isinstance(tomllib.loads(statement).get('developer_instructions'),str): break
            except tomllib.TOMLDecodeError: pass
        else: raise ValueError('Cannot parse instruction assignment')
        result = text[:match.start()] + 'developer_instructions = ' + json.dumps(new) + '\n' + text[match.start()+len(statement):]
    else:
        result = 'developer_instructions = '+json.dumps(new)+'\n'+text
    if tomllib.loads(result) != dict(before,developer_instructions=new):
        raise ValueError('Unexpected config mutation')
    return result


def hooks(existing, home, python, enabled=True):
    value = json.loads(json.dumps(existing)); all_hooks=value.setdefault('hooks',{})
    script=home/'skills/task-queue/scripts/task_queue.py'
    for event,command in [('SessionStart','session-start'),('Stop','hook-check')]:
        invocation=engine.io.hook_command(python,script,command)
        status='Load task queue guidance' if event=='SessionStart' else 'Check assigned task queue'
        entries=all_hooks.get(event,[])
        retained=[]
        for entry in entries:
            other=[h for h in entry.get('hooks',[]) if h.get('command')!=invocation]
            if any((h.get('statusMessage')==status or 'task-queue/scripts/task_queue.py' in h.get('command','')) and h.get('command')!=invocation for h in other):
                raise ValueError('Conflicting queue invocation needs reconciliation')
            if other: retained.append(dict(entry,hooks=other))
        if enabled:
            definition={'type':'command','command':invocation,'timeout':5,
                        'statusMessage':status}
            if event=='SessionStart': definition['additionalContextLimit']=6000
            retained.append({'hooks':[definition]})
        if retained: all_hooks[event]=retained
        elif event in all_hooks: del all_hooks[event]
    return value


def plan(home,python,enabled=True,expected=None):
    home=home.absolute(); skill=home/'skills/task-queue'
    if not python.is_absolute() or not python.is_file(): raise ValueError('Absolute installed Python required')
    paths=[home/'config.toml',home/'hooks.json']+[skill/f for f in FILES]
    for p in [home,home/'checkpoints',skill,*paths]: engine.io.assert_owned(p)
    originals={str(p):p.read_bytes() if p.exists() else None for p in paths}
    if originals[str(home/'config.toml')] is None: raise ValueError('Existing Codex config required')
    installed={f:originals[str(skill/f)] for f in FILES if originals[str(skill/f)] is not None}
    source={f:(SOURCE/f).read_bytes() for f in FILES}
    if installed and installed!=source:
        if not expected or set(expected)!=set(installed) or any(hashlib.sha256(v).hexdigest()!=expected[k] for k,v in installed.items()):
            raise ValueError('Installed queue skill differs; inspect and supply exact expected hashes')
    config=configure(originals[str(home/'config.toml')].decode(),home,enabled)
    prior=json.loads(originals[str(home/'hooks.json')] or '{}')
    proposed={str(skill/f):v for f,v in source.items()}
    proposed[str(home/'config.toml')]=config.encode()
    updated=hooks(prior,home,python,enabled)
    proposed[str(home/'hooks.json')]=(json.dumps(updated,indent=2)+'\n').encode() if updated!=prior else originals[str(home/'hooks.json')]
    return originals,proposed


def install(home,python,enabled=True,expected=None):
    raw,proposed=plan(home,python,enabled,expected)
    changed=[p for p in proposed if raw[p]!=proposed[p]]
    if not changed:return {'changed_files':[],'applied':True}
    backup=home/'checkpoints/backups'/('task-queue-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    engine.io.private_dir(backup)
    manifest=[]
    for i,p in enumerate(changed):
        previous=raw[p]
        if previous is not None: engine.write(backup/str(i),{'bytes_hex':previous.hex()})
        manifest.append({'path':p,'backup':str(i) if previous is not None else None,
                         'installed_sha256':hashlib.sha256(proposed[p]).hexdigest()})
    engine.write(backup/'manifest.json',manifest)
    for p,v in raw.items():
        engine.io.assert_owned(Path(p))
        if (Path(p).read_bytes() if Path(p).exists() else None)!=v: raise ValueError('Concurrent installation; targets unchanged')
    # Writes use private temporary files; preserve raw TOML/JSON bytes, not JSON string values.
    for p in changed: atomic_bytes(Path(p),proposed[p])
    return {'changed_files':changed,'backup':str(backup),'applied':True,
            'queue_hooks_enabled':enabled,'hook_trust':'Normal review required; trust store unchanged'}


def atomic_bytes(path,value):
    import tempfile
    engine.io.assert_owned(path); engine.io.private_dir(path.parent)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.queue-install-')
    try:
        with os.fdopen(fd,'wb') as f:
            engine.io.secure(Path(name)); f.write(value); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def rollback(backup):
    manifest=engine.read(backup/'manifest.json')
    # Stop rather than overwrite any later human or installer edit.
    for m in manifest:
        p=Path(m['path']); engine.io.assert_owned(p)
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=m['installed_sha256']:
            raise ValueError('Later edit detected; manual targeted rollback required')
    for m in reversed(manifest):
        p=Path(m['path'])
        if m['backup'] is None:p.unlink()
        else:atomic_bytes(p,bytes.fromhex(engine.read(backup/m['backup'])['bytes_hex']))
    return {'rolled_back':len(manifest),'queue_data':'Retained; no checkpoint or queue history deleted'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codex-home',type=Path,required=True)
    p.add_argument('--python',type=Path,default=Path(sys.executable))
    p.add_argument('--install',action='store_true'); p.add_argument('--disable',action='store_true')
    p.add_argument('--expected-hashes',type=Path); p.add_argument('--rollback',type=Path)
    a=p.parse_args()
    try:
        expected=engine.read(a.expected_hashes) if a.expected_hashes else None
        if a.rollback:
            if not a.install:raise ValueError('Rollback requires --install')
            result=rollback(a.rollback)
        elif a.install:result=install(a.codex_home,a.python,not a.disable,expected)
        else:
            raw,proposed=plan(a.codex_home,a.python,not a.disable,expected)
            result={'applied':False,'changed_files':[p for p in proposed if proposed[p]!=raw[p]]}
        print(json.dumps(result,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(str(e),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
