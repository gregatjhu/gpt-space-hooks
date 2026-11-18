---
name: task-queue
description: Read explicitly assigned task queues, propose or acknowledge handoffs, and reconcile evidence-backed task transitions. Use alongside checkpoints for authorized task pickup and delegation; queue entries never grant execution or messaging authority.
---

# Task queues

Read the exact assigned queue and newest verified snapshot before pickup. Use only assigned routes; a project session must not search a personal queue or infer access from repository membership. Read [the protocol](references/protocol.md) for configuration, transitions, publication, mirrors or cloud pickup.

This skill records explicit next actions; work-checkpoint records progress/evidence. Local SessionStart and Stop queue handlers are separate from checkpoint handlers. They perform bounded read-only checks and never execute tasks, contact anyone, acknowledge on a reader's behalf or create timers. Independently enable/disable either workflow through its installer/runbook. Cloud orchestration does not inherit local hooks; load this skill explicitly there.

Use `scripts/task_queue.py --config /exact/assigned/queue.json --store /exact/private/store`. A queue has one designated arbiter/store. Only that arbiter serializes accepted changes using expected revisions and stable operation IDs. Other machines/cloud tasks send change proposals, not independent executable claims. Do not replicate an arbiter store to create a second writer. Verify native identity/access before attesting to an actor or remote proposal; CLI actor fields are assertions, not authentication.

At start, task switches and meaningful changes, surface relevant pending, due, overdue or blocked work. Report unknown/stale observations. Record acknowledgment separately from acceptance, claim, dispatch, notification delivery and completion. To execute, require current independent task authority, satisfied dependencies and the arbiter's exact current claim/token. Re-read pending human requests/cancellations first. If either the queue or arbiter cannot be reached, continue other authorized work and retain a pending proposal; do not claim from a cached Page.

Preserve project coordinator ownership of engineering sequencing and the personal assistant's reminder ownership. Resolve collaborators through supported identity/access tools, recording verified IDs rather than guessing from names. Tagging is only a request; do not claim notification delivery without evidence. If native tagging/messaging is absent, return a project-safe manual handoff. Do not send live assignments to test this skill.

For direct chat delivery, use the native Codex send-message capability only when it is exposed to the sending chat, the existing destination chat and host are verified, and the user explicitly authorized that send. Carry the existing task/operation IDs and approved handoff. If a requirement is missing, keep the proposal pending and return a copyable handoff. A successful send records prompt submission; queue acknowledgment and authority still come from the queue protocol.

Complete only with evidence for every acceptance criterion, a current matching claim and explicit acceptance attestation. Expiry never makes unknown work safe to retry: freeze it until the prior execution is reconciled as stopped and a coordinator explicitly recovers it. Cancellation fences old tokens immediately, but cannot stop an already-running external action; obtain a stop/settlement receipt before another execution. Human edits/cancellation are never overwritten by snapshots.

Hook events are not timers. Before scheduling, reconcile existing automation IDs and canceled or tentative meetings. For meeting prep, use the verified start time, its named timezone and the lead time configured by the user. Report what the source said, what was scheduled, what ran and what was delivered. Never create a recurring schedule from a meeting title. Preserve existing reminders.

For storage pressure or an explicitly authorized segment rollover, read [storage and continuity](references/storage.md). Use `storage-status` and operation `preflight` before capacity-sensitive writes. A frozen predecessor is read-only; preserve claim/replay continuity through the verified segment chain. History migration is explicit, never a hook side effect.
