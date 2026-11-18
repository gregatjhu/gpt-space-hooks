# Task queues and delegation 0.1.2

Use this optional companion when a user authorizes explicit task-queue coordination. It does not replace work-checkpoint. Read the [protocol](../task-queue/references/protocol.md) for schema, safe claims, project/private routing, publication receipts and cloud bootstrap. No database, server, credentials, background worker or OS timer is installed.

## Install on one arbiter host

1. Fetch/review the source and preserve dirty checkouts. Supply the real queue, existing approved Space/audience, designated arbiter and intended coordinator identities through private configuration. Reconcile existing Pages/reminders before creating anything. Repository access is not queue access.
2. Use Python 3.11+ and an existing `workspace-write` configuration whose approved private checkpoint root is already writable. Current managed permission-profile configurations require a separate targeted adapter: this installer refuses to widen them. Linux, macOS and WSL use the existing POSIX adapter; native Windows uses current-user-only local NTFS ACLs/locking. Named-zone due times require an available IANA timezone database; on Windows, use an already approved Python `tzdata` installation or arrange it separately. Do not bypass PowerShell policy or take ownership.
3. From `implementation/`, dry-run, inspect, then install:

```sh
python3 install_task_queue.py --codex-home "$HOME/.codex"
python3 install_task_queue.py --codex-home "$HOME/.codex" --install
```

On Windows use the full paths to the installed Python and Codex home. Hook commands use the same Windows encoding/ACL adapter as checkpoints. Existing differing queue skill files require a private JSON mapping of their exact hashes supplied with `--expected-hashes`; unknown changes stop installation. The package does not install software or copy credentials.

4. Review the TWO new queue hook definitions through Codex's normal `/hooks` flow. Their names are `Load task queue guidance` (SessionStart) and `Check assigned task queue` (Stop). No trust stores are edited. Checkpoint hook definitions and trust remain separate. Global `[Task queue pickup]` guidance loads the skill even where hook execution has not yet been established; that is not proof of a hook callback.
5. Bind exact queue configs privately under `CODEX_HOME/checkpoints/task-queues/config/`. Use a single arbiter store for each queue. Add a private `routes.json` with `enabled: true`, a `default` personal route and explicit project `folder_prefixes`, `config`, `store` fields. Do not commit personal binding/route files, histories or claim tokens. Nothing automatically discovers profiles or matches repository aliases.

Independent queue disable removes only the queue hook definitions and exact generated global instruction block, retaining the skill, data, personal/project bindings and unrelated checkpoint configuration:

```sh
python3 install_task_queue.py --codex-home "$HOME/.codex" --disable
python3 install_task_queue.py --codex-home "$HOME/.codex" --disable --install
```

Re-enable with the install command and normal hook trust review. Checkpoints can be independently disabled through the runtime's individual checkpoint-hook controls; preserve other definitions. Test all four hook combinations in fixtures. `routes.json` `enabled: false` is a read-only queue-hook no-op and leaves checkpoint hooks alone. Global guidance can remain discoverable while routes are paused; it never grants authority to execute.

## Roll back

Each mutation records a private backup manifest and exact installed hashes. Supply its printed path:

```sh
python3 install_task_queue.py --codex-home "$HOME/.codex" --rollback /exact/printed/backup --install
```

Rollback refuses if a target changed afterward, so it cannot overwrite concurrent human/configuration edits. Otherwise it restores only changed files and removes newly installed files; it retains queue/checkpoint data. For later edits, disable the two exact queue hooks and reconcile the affected instruction block manually using the backup. Normal trust review applies after restoring hook definitions.

## Daily/cloud use

Use the [Dot/Spaces handoff](DOT-SPACES-HANDOFF.md) for reusable coordinator/local-reader prompts and the agent-led proposal ingestion contract. SessionStart/Stop read only local routes/cache: they do not enumerate or import child Pages. Proposal titles are a human/agent convention; real consumer acknowledgment requires an arbiter transition.

Queue requests are REQUESTED until a verified consumer acknowledges and accepts. The arbiter issues a single fenced claim only after independent authority/dependencies/current human changes are checked. A project-safe task intended for a collaborator is not a message or notification. Resolve that person and access first, then use an explicitly authorized supported assignment path or a manual handoff. Fixture tests never assign live teammates.

Cloud sessions receive the [explicit bootstrap](../task-queue/references/protocol.md#cloud-bootstrap). They may read approved queues and return proposals, but cannot claim from snapshots or run a second arbiter store. If the arbiter or required authenticated dispatch tools are missing, retain pending. Continue unrelated authorized work. The app's create/send tools, when exposed, are optional separate actions subject to their human authorization; a Dot room ID is not assumed to be a Codex thread ID. This package does not repair missing Dot dispatch actions or text replies.

Meeting reminders need a verified meeting instance and timing. Reconcile existing automation IDs first; keep canceled meetings excluded and tentative ones held. Source-reported scheduling, observed configuration, actual run, notification delivery and user acknowledgment are distinct. Local SessionStart/Stop have no idle wakeups. The local app's heartbeat scheduler requires an available host/app; hosted Page automation requires actual controller and scheduler operations, not merely `can_enable: true`. Do not create a duplicate local reminder because the hosted scheduler is inaccessible. Test one self-directed one-shot separately from real reminders and record whether it actually ran; a registration card alone is not delivery.

Keep reporting/evidence timestamps in UTC unless the task explicitly supplies another reporting basis. Meeting/reminder dates use their declared local timezone; a UTC report does not change a local meeting's start. Preserve both the offset and named zone, converting explicitly when relating them. A review/settlement delay, business-day calendar or delivery-approval requirement is separate task policy, never inferred from choosing UTC or from a queue entry. Personal timezone defaults belong in private instructions; do not bake one person's calendar into the shared engine.

## Verify

```sh
python3 -m unittest -v test_task_queue.py test_checkpoint.py test_platform_io.py test_project_scope.py test_queue_history.py
python3 build_package.py
```

Fixtures verify claims/concurrency, stale recovery, mirrors, revisions/human changes, cancellation, acceptance evidence, due/DST semantics, access boundaries, exact publication receipts, credential-pattern rejection, independent hook toggles and guarded rollback. Run installed helper/route tests with synthetic tasks in a separate owner-private test store. Then prove fresh-session hook execution in the actual runtime without a trust bypass, correct project/private Page audiences and exact snapshot readback. Fresh context receipt, callback execution, cloud pickup, timer run, notification and task execution each need their own evidence. Linux fixture success does not establish native Windows/macOS/WSL acceptance. Preserve existing schedules.

## Linux acceptance, November 2, 2026

58 tests ran successfully with one native Windows ACL integration test skipped on Linux. Skill validation, archive manifest hashes, selected documentation links and private-binding exclusion checks passed. Installed synthetic CLI transitions completed requested → acknowledged → accepted → in_progress → completed; direct installed handler contracts selected separate private/project queues without private-route leakage. Actual project/private snapshot content and inherited audiences were read back before acknowledgement.

Bundled CLI 0.166.0-alpha.5.1 first loaded the existing checkpoint hook only. After the user reviewed the two new queue definitions in an existing desktop session, a fresh ephemeral CLI with global developer instructions omitted received both full skill bodies, the exact queue route and cached pending count. No hook-trust bypass was used. This demonstrates SessionStart queue-context delivery in that CLI; separate desktop callback execution, useful Stop reminder delivery, fresh independent cloud pickup, native Windows/macOS/WSL and autonomous dispatch remain separate tests. The initial one-shot local timing probe was registered, but no actual scheduler-run/delivery receipt was observed during implementation. Existing hosted reminders were preserved and retained by their source-reported IDs; their delivery was not inferred from the ledger.

The subsequent local heartbeat receipt arrived November 2 at 15:42:51.213 UTC for a 15:31:00 UTC schedule: **711.213 seconds late**. The target chat was busy with implementation and the heartbeat arrived after that turn ended. This is evidence of local scheduler pickup, not punctual notification delivery; busy-chat waiting is a hypothesis, not a measured root cause. The completed test automation was deleted. Keep exact-time acceptance failed/unproven until an idle-target control and additional actual-run observations separate schedule dispatch, target availability, agent processing and user notification. Do not shorten all polling intervals or shift real meeting reminders based on one late sample.

The idle-target control subsequently reached the same local chat at 15:55:21.225 UTC for a 15:55:00 UTC schedule: **21.225 seconds late**. No intervening active work occurred in that chat after the preceding final response. The receipt was saved and that one-shot deleted. This supports testing an available/idle coordination target, but does not prove causation, backend dispatch time, hosted coverage, user notification delivery or a timing guarantee. Existing reminders were unchanged.

Checkpoint publication's five-minute material-change aim does not make a consumer poll or wake every five minutes. For routine queue freshness, five-minute consumer polling is a reasonable explicit target to test separately, not a guarantee or an already-installed timer. Preserve deduplication and meaningful-change-only notifications. Meeting prep uses its verified meeting schedule rather than relying on that poll. A dedicated idle coordinator target can be considered through a separately authorized supported session/scheduler path; no new chat or hosted service is created by this package.

Storage capacity: task-queue 0.1.2 adds [bounded history and segment continuity](../task-queue/references/storage.md). Use `storage-status` and exact-operation `preflight`; migration is explicit and reversible only before later logical writes. Upgrade all writers together before relying on frozen-segment guards. No live queue migration is performed by installation.
