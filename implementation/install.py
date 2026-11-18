#!/usr/bin/env python3
"""Install or upgrade a private checkpoint workflow; preserve unrelated settings."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib
import importlib.util

_adapter_path = Path(__file__).parent / 'work-checkpoint/scripts/platform_io.py'
_spec = importlib.util.spec_from_file_location('checkpoint_platform_io', _adapter_path)
_io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_io)

VERSION = '0.3.4'
HOME = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
SKILL = HOME / 'skills/work-checkpoint'
STORE = HOME / 'checkpoints'
CONFIG = HOME / 'config.toml'
HOOKS = HOME / 'hooks.json'
MARKER = '[Work checkpoints]'
FILES = ('SKILL.md', 'scripts/checkpoint.py', 'scripts/platform_io.py', 'scripts/project_scope.py', 'references/project.md')
INSTALL_ORDER = ('scripts/platform_io.py', 'scripts/project_scope.py', 'scripts/checkpoint.py', 'references/project.md', 'SKILL.md')


def instructions(home):
    return (MARKER + '\nAt the start of each local session, regardless of working folder, read '
            + str(home / 'skills/work-checkpoint/SKILL.md')
            + ' once. Use work-checkpoint for prepared sanitized summaries at meaningful milestones and task switches. '
            'Respect read-only and disclosure restrictions; verify private cloud readback before claiming delivery. '
            'Publication does not authorize dispatch, messaging, or production changes.\n')


def configure(text, home=HOME):
    original = tomllib.loads(text)
    if original.get('sandbox_mode') != 'workspace-write' or 'default_permissions' in original:
        raise ValueError('This installer requires explicit workspace-write configuration; it will not change a permission profile')
    store = str(home / 'checkpoints')
    existing = original.get('developer_instructions', '')
    # Recognize prior instruction blocks by their exact installed link and workflow,
    # not a personal marker. Preserve approved legacy text rather than rewriting it.
    skill_link = str(home / 'skills/work-checkpoint/SKILL.md')
    prior_link = skill_link in existing and 'Use work-checkpoint ' in existing
    if MARKER in existing or prior_link:
        if str(home / 'skills/work-checkpoint/SKILL.md') not in existing or store not in original.get('sandbox_workspace_write', {}).get('writable_roots', []):
            raise ValueError('Existing checkpoint link or writable root requires targeted reconciliation')
        return text  # Preserve the already installed link byte for byte, including unrelated instructions.
    added = instructions(home)
    expected = dict(original)
    merged = (existing.rstrip() + '\n\n' if existing else '') + added
    if existing:
        # Only replace a complete top-level assignment; never a similarly named nested key.
        match = re.search(r'^developer_instructions\s*=', text, re.M)
        if not match or re.search(r'^\[', text[:match.start()], re.M):
            raise ValueError('Cannot safely locate top-level developer_instructions')
        statement = ''
        for line in text[match.start():].splitlines(keepends=True):
            statement += line
            try:
                parsed = tomllib.loads(statement)
                if isinstance(parsed.get('developer_instructions'), str):
                    break
            except tomllib.TOMLDecodeError:
                continue
        else:
            raise ValueError('Cannot parse complete developer_instructions assignment')
        result = text[:match.start()] + 'developer_instructions = ' + json.dumps(merged) + '\n' + text[match.start() + len(statement):]
    else:
        result = 'developer_instructions = ' + json.dumps(merged) + '\n\n' + text
    table = original.get('sandbox_workspace_write', {})
    roots = table.get('writable_roots', [])
    if store not in roots:
        match = re.search(r'^\[sandbox_workspace_write\]\s*(?:#.*)?$', result, re.M)
        if match:
            start = match.end()
            after = re.search(r'^\[', result[start:], re.M)
            end = start + after.start() if after else len(result)
            section = result[start:end]
            root_match = re.search(r'^writable_roots\s*=.*$', section, re.M)
            if root_match:
                a = root_match.start()
                statement = ''
                for line in section[a:].splitlines(keepends=True):
                    statement += line
                    try:
                        if isinstance(tomllib.loads(statement).get('writable_roots'), list):
                            break
                    except tomllib.TOMLDecodeError:
                        continue
                else:
                    raise ValueError('Cannot parse writable_roots')
                section = section[:a] + 'writable_roots = ' + json.dumps(roots + [store]) + '\n' + section[a + len(statement):]
            else:
                section = '\nwritable_roots = ' + json.dumps(roots + [store]) + '\n' + section
            result = result[:start] + section + result[end:]
        else:
            result += '\n[sandbox_workspace_write]\nwritable_roots = ' + json.dumps([store]) + '\n'
    expected['developer_instructions'] = merged
    expected['sandbox_workspace_write'] = dict(table, writable_roots=roots if store in roots else roots + [store])
    if tomllib.loads(result) != expected:
        raise ValueError('Configuration changes exceeded intended scope')
    return result


def proposed_hooks(existing, home, python, enable_stop=False):
    value = json.loads(json.dumps(existing))
    hooks = value.setdefault('hooks', {})
    script = home / 'skills/work-checkpoint/scripts/checkpoint.py'
    for event, command in [('SessionStart', 'session-start')] + ([('Stop', 'stop-check')] if enable_stop else []):
        definition = {'type': 'command', 'command': _io.hook_command(python, script, command),
                      'timeout': 5, 'statusMessage': 'Load work checkpoint guidance' if event == 'SessionStart' else 'Check prepared checkpoint delivery'}
        if event == 'SessionStart':
            definition['additionalContextLimit'] = 2500
        entries = hooks.setdefault(event, [])
        matches = [h for entry in entries for h in entry.get('hooks', []) if h.get('command') == definition['command']]
        conflicts = [h for entry in entries for h in entry.get('hooks', [])
                     if h.get('statusMessage') == definition['statusMessage'] and h.get('command') != definition['command']]
        if conflicts:
            raise ValueError('An existing checkpoint hook uses a different invocation; reconcile its exact definition before installing')
        if len(matches) > 1:
            raise ValueError('Duplicate checkpoint hook commands require reconciliation')
        if not matches:
            entries.append({'hooks': [definition]})
    return value


def safe_path(path):
    # Fail on symlinked ancestors too, so global config/skill/store writes stay bounded.
    _io.assert_owned(path)


def atomic(path, value):
    safe_path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-install-')
    try:
        with os.fdopen(fd, 'wb') as f:
            _io.secure(Path(temporary))
            f.write(value if isinstance(value, bytes) else value.encode())
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def plan(home, python, upgrade=False, expected=None, enable_stop=False):
    if os.name not in ('posix', 'nt') or sys.version_info < (3, 11):
        raise ValueError('Version 0.3 requires Python 3.11+ on Linux/macOS or native Windows with local NTFS')
    if not python.is_absolute() or not python.is_file():
        raise ValueError('Supply the absolute installed Python executable path')
    home = home.absolute()
    skill, store, config, hook_file = home / 'skills/work-checkpoint', home / 'checkpoints', home / 'config.toml', home / 'hooks.json'
    paths = [config, hook_file] + [skill / f for f in FILES]
    for p in [home, store, store / 'backups', skill, *paths]:
        safe_path(p)
    raw = {str(p): p.read_bytes() if p.exists() else None for p in paths}
    if raw[str(config)] is None:
        raise ValueError('Existing local config.toml is required; configure Codex authentication/permissions separately')
    proposed_config = configure(raw[str(config)].decode('utf-8'), home)
    previous_hooks = json.loads(raw[str(hook_file)]) if raw[str(hook_file)] is not None else {}
    hooks = proposed_hooks(previous_hooks, home, python, enable_stop)
    existing_skill = {f: raw[str(skill / f)] for f in FILES if raw[str(skill / f)] is not None}
    if existing_skill and not upgrade:
        raise ValueError('Skill already exists; use an explicit hash-checked upgrade')
    if upgrade:
        expected = expected or {}
        if set(expected) != set(existing_skill) or any(hashlib.sha256(content).hexdigest() != expected[f] for f, content in existing_skill.items()):
            raise ValueError('Installed skill changed or expected hashes are missing; inspect exact files before upgrading')
    source = Path(__file__).parent / 'work-checkpoint'
    proposed = {str(config): proposed_config.encode(), str(hook_file): (json.dumps(hooks, indent=2) + '\n').encode()}
    if hooks == previous_hooks and raw[str(hook_file)] is not None:
        proposed[str(hook_file)] = raw[str(hook_file)]
    proposed.update({str(skill / f): (source / f).read_bytes() for f in FILES})
    return raw, proposed, store


def install(home, python, upgrade=False, expected=None, enable_stop=False):
    raw, proposed, store = plan(home, python, upgrade, expected, enable_stop)
    # Dependencies first, then helper/guidance, then the global links that expose them.
    skill = home / 'skills/work-checkpoint'
    ordered = [str(skill / f) for f in INSTALL_ORDER] + [str(home / 'config.toml'), str(home / 'hooks.json')]
    changed = [p for p in ordered if raw[p] != proposed[p]]
    _io.private_dir(store)
    backup = store / 'backups' / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(mode=0o700, parents=True)
    _io.secure(store / 'backups')
    _io.secure(backup)
    for i, p in enumerate(changed):
        if raw[p] is not None:
            atomic(backup / ('original-' + str(i)), raw[p])
    atomic(backup / 'manifest.json', json.dumps({'paths': changed, 'version': VERSION}))
    # Check every planned input before mutation. Backups permit recovery after an interrupted multi-file update.
    for p, content in raw.items():
        safe_path(Path(p))
        if (Path(p).read_bytes() if Path(p).exists() else None) != content:
            raise ValueError('Installation changed concurrently; no target files modified')
    for p in changed:
        atomic(Path(p), proposed[p])
    return {'version': VERSION, 'changed_files': changed, 'backup': str(backup),
            'hook_definition_changed': str(home / 'hooks.json') in changed,
            'hook_trust': 'Review changed hook definitions in Codex; installer never edits trust settings',
            'private_destination': 'Not included in package; bind separately after owner-only verification'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, default=HOME)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--install', action='store_true', help='Apply; otherwise print a bounded dry run')
    parser.add_argument('--upgrade', action='store_true')
    parser.add_argument('--expected-hashes', type=Path, help='Approved JSON mapping of exact existing skill file hashes')
    parser.add_argument('--enable-stop-check', action='store_true', help='Add a nonblocking reminder; requires normal hook trust review')
    args = parser.parse_args()
    expected = json.loads(args.expected_hashes.read_text()) if args.expected_hashes else None
    try:
        if args.install:
            result = install(args.codex_home, args.python, args.upgrade, expected, args.enable_stop_check)
        else:
            raw, proposed, _ = plan(args.codex_home, args.python, args.upgrade, expected, args.enable_stop_check)
            result = {'version': VERSION, 'changed_files': [p for p in proposed if raw[p] != proposed[p]], 'applied': False}
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
