# Codex work checkpoints

A reusable filesystem skill and local hooks for sanitized work handoffs to a user-approved ChatGPT Page registry. Personal mode stays owner-only; explicit project profiles use separate per-user registries in approved project Spaces. It keeps captured state, source observation dates, publication and consumer evidence separate. It has no server or database deployment, background scheduler, transcript reader or credential bridge.

Start with [the package guide](implementation/PACKAGE.md), then the [Linux/macOS/WSL runbook](implementation/runbooks/INSTALL-POSIX.md) or [Windows runbook](implementation/runbooks/INSTALL-WINDOWS.md). Run commands from `implementation/`. Python 3.11+, a supported local Codex runtime, normal hook trust review and an existing explicit workspace-write configuration are required. Cloud publication additionally needs the task's native Page tools and the user's disclosure authorization.

The shared source contains the skill, helper, OS adapters, installer, tests and runbooks. Each user keeps authentication, registry bindings, checkpoint history, receipts, exclusions and personal coordinator instructions private. Use one shared core with hash-checked local upgrades; no private fork or synchronization hooks are required.

For assigning projects to Spaces and keeping distribution repositories aligned, follow [project selection](implementation/runbooks/SELECT-PROJECT.md). For shared environments, follow [project/cloud setup](implementation/runbooks/PROJECT-CLOUD.md). Repository skills and project instructions are the cloud path; local command hooks do not run under cloud orchestration. Page-tool absence retains a prepared handoff for an authorized local publisher. Each user profile has a designated publisher/store; independent multi-publisher retries are unsupported.

For a new or existing cloud chat, use the [copyable cloud-session first prompt and visibility checks](implementation/runbooks/CLOUD-SESSION-START.md). Supply approved destinations in private task/project context; the shared template contains no personal Page IDs. It distinguishes missing guidance, inaccessible destinations, unpublished checkpoints and untested coordinator consumption.

Version 0.3.4 corrects placeholder identity reporting without rewriting original checkpoints. Linux execution is tested. The earlier 0.3.3 Windows patch has native installation and startup evidence; 0.3.4 needs its own Windows acceptance. macOS and WSL acceptance remain pending. Fresh desktop execution and actual runtime Stop-event execution require separate acceptance. Source tests, skill discovery and successful publication do not prove independent cloud consumption or task dispatch.

Review [per-machine acceptance](implementation/runbooks/ACCEPTANCE.md) and [public-release preparation](implementation/runbooks/PUBLIC-RELEASE.md).

The [ChatGPT plugin pilot](plugins/README.md) packages the checkpoint and queue guidance for an internal workspace. This repository remains the source for the local Python helpers, installers, and hook configuration.

For Dot/coordinator onboarding and local pickup, use the [Spaces coordination handoff](implementation/runbooks/DOT-SPACES-HANDOFF.md). It includes copyable prompts, the child-Page proposal/receipt convention, sole-arbiter reconciliation and the limits of local hook discovery. Supply actual destinations privately.

## Task queues and delegation

For a Windows update or pilot of both workflows, use the [Windows pilot procedure](implementation/runbooks/WINDOWS-TASK-QUEUE-PILOT.md) against the exact candidate revision.

The optional [task-queue workflow](implementation/runbooks/TASK-QUEUES.md) 0.1.2 ships beside checkpoint 0.3.4. It has its own skill, SessionStart/Stop handlers, installer and enable/disable controls. Checkpoints report progress; queues record explicit actions, intended consumers, approval requirements and evidence-backed lifecycle transitions. One designated arbiter/store serializes claims; immutable Page snapshots and private mirrors are discovery views, never independent execution locks. No distributed Page lock, automatic cross-host dispatch or collaborator notification service is implied. Existing schedules remain separate and are reconciled before any new reminder.

Storage capacity: task-queue 0.1.2 adds [bounded history and segment continuity](implementation/task-queue/references/storage.md). Use `storage-status` and exact-operation `preflight`; migration is explicit and reversible only before later logical writes. Upgrade all writers together before relying on frozen-segment guards. No live queue migration is performed by installation.
