# Windows checkpoint and task-queue pilot

Use this procedure to test a candidate revision on native Windows. Record the exact source tested and installed. Run it with a disposable fixture before applying any update to a live installation.

## Pin source and preserve local work

Fetch the candidate and the repository's `main`, if present, and record their commit IDs. For a source archive, verify its SHA-256 and record the source revision supplied with it. Preserve existing work with an isolated branch, worktree or extracted archive. Read [native Windows installation](INSTALL-WINDOWS.md), [task queues](TASK-QUEUES.md), [project selection](SELECT-PROJECT.md) and [cloud bootstrap](CLOUD-SESSION-START.md). Keep local configuration, profiles, source manifests, receipts and personal Page links out of Git. Resolve existing bindings on this Windows host; never copy credentials, Linux paths or the whole Codex home.

The queue installer uses PowerShell for NTFS access control and encoded hook commands. When an encoded invocation changes, for example because the Python path changes, the installer stops for reconciliation to avoid duplicate handlers. This check also applies to disable operations. The hook-toggle test identifies encoded handlers by their role.

Windows folder routes also compare case and slash styles using native lexical path rules, including trailing separators. A case variant must not fall through from an assigned project queue to the personal queue. Directory boundaries remain strict and overlapping normalized routes remain ambiguous. This matching does not read the hook payload's working folder or transcript path; POSIX matching is unchanged.

## Native preflight, tests and upgrade

Use an existing approved native Python 3.11+ and local NTFS Codex home owned by the current user. Identify desktop-bundled and PATH CLI versions separately. No policy bypass, privilege elevation, ownership takeover, trust-store edits or automatic dependency installation. Named meeting zones require an IANA timezone database; if missing, report that prerequisite or use an already approved Python with `tzdata`. Do not substitute a fixed EST offset for America/New_York.

Run PowerShell from `implementation/` (replace paths and meeting zone with the actual approved local values):

```powershell
$queuePython = (py -3 -c 'import sys; print(sys.executable)').Trim()
$queueHome = Join-Path $env:USERPROFILE '.codex'
& $queuePython windows_queue_pilot.py --codex-home $queueHome --timezone America/New_York
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed; preserve existing configuration' }
& $queuePython -m unittest -v test_checkpoint.py test_platform_io.py test_project_scope.py test_task_queue.py test_queue_history.py
if ($LASTEXITCODE -ne 0) { throw 'Native tests failed; fix this same PR branch before installation' }
```

Use the explicitly known custom Codex home/Python if applicable; do not scan the profile or dump environments. Preflight reads only the exact home/config and known installed skill files; it checks native ownership/NTFS and named-zone availability. It does not read credentials, transcripts or alter hooks. Inspect the named installed files before accepting their hashes for an upgrade. Then:

```powershell
& $queuePython windows_queue_pilot.py --codex-home $queueHome --timezone America/New_York --write-hashes
if ($LASTEXITCODE -ne 0) { throw 'Hash preparation failed' }
$pilotHashes = Join-Path $queueHome 'checkpoints/windows-task-queue-pilot'
$checkpointHashes = Join-Path $pilotHashes 'work-checkpoint-hashes.json'
$queueHashes = Join-Path $pilotHashes 'task-queue-hashes.json'
& $queuePython install.py --codex-home $queueHome --python $queuePython --upgrade --expected-hashes $checkpointHashes --enable-stop-check
if ($LASTEXITCODE -ne 0) { throw 'Checkpoint upgrade dry run failed' }
& $queuePython install_task_queue.py --codex-home $queueHome --python $queuePython --expected-hashes $queueHashes
if ($LASTEXITCODE -ne 0) { throw 'Queue dry run failed' }
```

If checkpoint installation is absent, omit `--upgrade --expected-hashes`; bind only an explicitly approved existing registry. If the checkpoint writable root is absent, apply the reviewed checkpoint install first and repeat the queue dry run. If an installed skill is byte-identical, no upgrade is needed. After reviewing the concrete changes under the user's installation authorization, rerun the corresponding command with `--install`, checking each exit code. Reuse the reviewed manifests only while their installed inputs still match. No-op queue reinstalls are supported; do not blindly regenerate hashes to accept unexplained changes. Existing hash manifests are not overwritten.

Review changed SessionStart/Stop definitions in the runtime's normal hook UI. The queue handlers are independently toggleable from checkpoint handlers. Global links/config apply across working folders in supported local sessions; already-running sessions may need resume/reload or the exact guidance explicitly supplied. Do not promise every active session reloaded it. Cloud sessions still need the explicit bootstrap.

## Queue routing and single-arbiter ownership

Prepare owner-private Windows configs and folder-prefix routes using the actual Windows paths and verified native Page/Space/audience. Personal registry access and each project audience are independent checks. Do not copy Linux paths or discover unrelated profiles. Choose one explicit queue role:

- **Consumer/producer for the existing queues:** read approved cloud snapshots and return proposals through the authorized handoff to the existing designated arbiter. Do NOT open a new writable Windows store for the same queue ID. The read-only hook may load an explicit route with an empty local store; its pending count is only that cache's count, not evidence the cloud queue is empty. Read the actual newest Page snapshots before pickup.
- **New machine-owned arbiter:** only with an explicit new queue assignment or controlled arbiter migration after old claims/publications are reconciled. It needs one designated store, current audience binding and independently verified publication. Installing the package does not migrate ownership.

The checkpoint workflow can have machine-specific producer histories under its existing delivery protocol. The task-queue arbiter is different: two independent machine stores are not a distributed claim lock. Never clone queue history to make Windows a competing arbiter.

## Required handback and same-PR fixes

1. Record machine, OS, actual Python/PowerShell, desktop runtime and PATH CLI; source branch/commit, installed hashes and backup/rollback paths. Exclude credentials, applicant details, raw logs/transcripts and personal paths from shared evidence.
2. Run the native suite, actual private ACL/locking and Unicode/space-path cases. Verify checkpoint settings/history preserved and all four queue/checkpoint hook enable/disable combinations. Record bootstrap context, exact actual session IDs and handler invocation, not skill-catalog presence alone.
3. Test fresh desktop and CLI sessions in two unrelated disposable folders through normal hook trust. Verify real SessionStart and Stop callbacks separately; a direct helper test is insufficient. Preserve existing schedules.
4. Exercise the installed synthetic queue lifecycle and mirrored-task rejection locally; then verify approved Page publication/readback or a consumer proposal to the existing arbiter, according to the assigned role. Never send test assignments to teammates or execute production work. Windows readback/pickup and cloud notifications are separate outcomes.
5. Patch native issues on a feature or fix branch based on the candidate. Include relevant regressions and docs, reconcile with current `main` before pushing, and open a PR according to the project's contribution rules. Return a patch if you have a source archive or lack repository access. Repeat the affected native checks on the final revision before release.

Use [task-queue disable/rollback](TASK-QUEUES.md#roll-back) if needed; do not reset unrelated config or delete histories. Publish a sanitized checkpoint and return tested/installed head, passed/pending checks and the next concrete gate.
