#!/usr/bin/env python3
"""Export an explicit code-only allowlist; never recurse through local operator data."""
import hashlib
import io
import json
from pathlib import Path
import tarfile

FILES = ('PACKAGE.md', 'VERSION', 'install.py', 'test_checkpoint.py', 'build_package.py',
         'work-checkpoint/SKILL.md', 'work-checkpoint/scripts/checkpoint.py',
         'work-checkpoint/scripts/platform_io.py', 'work-checkpoint/scripts/project_scope.py', 'work-checkpoint/references/project.md', 'test_platform_io.py', 'test_project_scope.py',
         'runbooks/INSTALL-WINDOWS.md', 'runbooks/INSTALL-POSIX.md', 'runbooks/ACCEPTANCE.md',
         'runbooks/PUBLIC-RELEASE.md', 'runbooks/PROJECT-CLOUD.md', 'runbooks/SELECT-PROJECT.md',
         'runbooks/CLOUD-SESSION-START.md', 'runbooks/DOT-SPACES-HANDOFF.md', 'LICENSE',
         'install_task_queue.py', 'test_task_queue.py', 'test_queue_history.py', 'task-queue/SKILL.md',
         'task-queue/scripts/task_queue.py', 'task-queue/scripts/queue_history.py', 'task-queue/scripts/platform_io.py',
         'task-queue/references/protocol.md', 'task-queue/references/storage.md', 'runbooks/TASK-QUEUES.md',
         'windows_queue_pilot.py', 'runbooks/WINDOWS-TASK-QUEUE-PILOT.md')


def build(root, output):
    version = (root / 'VERSION').read_text().strip()
    if version != '0.3.4':
        raise ValueError('Unexpected source version')
    contents = {name: (root / name).read_bytes() for name in FILES}
    manifest = {'version': version, 'task_queue_version': '0.1.2', 'files': {name: hashlib.sha256(value).hexdigest() for name, value in contents.items()},
                'license': 'MIT',
                'excluded': ['registry binding', 'checkpoints', 'credentials', 'backups', 'session inventory']}
    contents['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive = output / ('work-checkpoint-workflow-' + version + '.tar.gz')
    with tarfile.open(archive, 'w:gz') as tar:
        for name, value in contents.items():
            info = tarfile.TarInfo('work-checkpoint-workflow-' + version + '/' + name)
            info.size, info.mode, info.mtime = len(value), 0o600, 0
            tar.addfile(info, io.BytesIO(value))
    archive.chmod(0o600)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'manifest.json').chmod(0o600)
    return {'archive': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'source_files': list(FILES)}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    print(json.dumps(build(root, root / 'dist'), indent=2))
