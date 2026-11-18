#!/usr/bin/env python3
"""Bounded native-Windows preflight and optional private upgrade-hash manifests."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tomllib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

spec=importlib.util.spec_from_file_location('queue_pilot_installer',Path(__file__).with_name('install_task_queue.py'))
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

CHECKPOINT_FILES=('SKILL.md','scripts/checkpoint.py','scripts/platform_io.py','scripts/project_scope.py','references/project.md')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codex-home',type=Path,required=True)
    p.add_argument('--timezone',default='UTC',help='Explicit meeting/reminder IANA zone; reporting stays UTC')
    p.add_argument('--write-hashes',action='store_true',help='Write only private hash manifests, not hooks/config/skill files')
    a=p.parse_args()
    try:
        if sys.platform!='win32':raise ValueError('Run this preflight on native Windows, not Linux/WSL')
        if sys.version_info<(3,11):raise ValueError('Existing Python3.11+ required')
        python=Path(sys.executable);home=a.codex_home.absolute()
        io=installer.engine.io
        io.assert_owned(home)  # Includes native NTFS, reparse and current-owner checks.
        ps=shutil.which('powershell.exe')
        if not ps:raise ValueError('Existing Windows PowerShell executable unavailable; no installation performed')
        try:ZoneInfo(a.timezone)
        except ZoneInfoNotFoundError as e:
            raise ValueError('Named-zone database unavailable for '+a.timezone+'; use an approved Python with IANA/tzdata support or arrange that prerequisite. No fixed-offset fallback.') from e
        config_path=home/'config.toml';io.assert_owned(config_path)
        current=tomllib.loads(config_path.read_text(encoding='utf-8'))
        if current.get('sandbox_mode')!='workspace-write' or 'default_permissions' in current:
            raise ValueError('Existing managed/other permission profile needs targeted review; no permission rewrite')
        manifests={}
        for kind,names in [('work-checkpoint',CHECKPOINT_FILES),('task-queue',installer.FILES)]:
            values={}
            for name in names:
                f=home/'skills'/kind/name;io.assert_owned(f)
                if f.exists():values[name]=hashlib.sha256(f.read_bytes()).hexdigest()
            manifests[kind]=values
        result={'platform':'native Windows','python':str(python),'python_version':sys.version.split()[0],
                'powershell':ps,'codex_home':str(home),'meeting_timezone':a.timezone,
                'checkpoint_root_already_writable':str(home/'checkpoints') in current.get('sandbox_workspace_write',{}).get('writable_roots',[]),
                'installed_file_hashes':manifests,'installation_performed':False}
        if a.write_hashes:
            root=home/'checkpoints/windows-task-queue-pilot'
            for kind,values in manifests.items():
                path=root/(kind+'-hashes.json')
                if path.exists():raise ValueError('Existing pilot hash manifest preserved; inspect before choosing a fresh output')
            for kind,values in manifests.items():installer.engine.write(root/(kind+'-hashes.json'),values)
            result['hash_directory']=str(root)
        print(json.dumps(result,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print('Windows pilot preflight: '+str(e),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
