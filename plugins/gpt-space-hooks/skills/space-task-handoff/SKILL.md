---
name: space-task-handoff
description: Use when reading an assigned task queue in Spaces or preparing an evidence-backed handoff proposal for its designated arbiter.
---

# Space task handoffs

Start with the explicitly assigned queue, its newest verified snapshot and current human requests or cancellations. Follow verified segment continuation links. If access, freshness or the assigned arbiter is unclear, report the gap and keep the proposal pending.

For a handoff, record a stable operation ID, the exact task and workstream, expected task and queue revisions, the intended consumer, relevant evidence, acceptance criteria and the requested transition. Use the existing authorized proposal route and preserve the workstream's coordinator ownership. Keep owner-only content out of project handoffs.

The queue's designated arbiter alone applies changes and issues claims. Distinguish proposal, acknowledgment, acceptance, claim and evidence-backed completion. Execution requires independent authority, satisfied dependencies and the exact current claim. A stale snapshot, expired claim, mention or successful Page write cannot establish execution authority or notification delivery.

When tools or access are missing, return a manual proposal suitable for the approved audience. The repository defines the queue protocol and local helper. Installing this skill provides no local hook, timer or second queue writer.
