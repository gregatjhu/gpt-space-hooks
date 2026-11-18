# Dot coordination through Spaces

Use this guide to inform a Dot or cloud coordinator about checkpoints and task queues, and to tell local sessions how to pick up its proposals. This is the reusable repository counterpart of an owner-private handoff. Fill in approved routes in private context; do not commit personal Page links, identities, reminder details or local bindings.

## Bind routes and owners once

Give each participant only its assigned routes:

| Binding | Value supplied privately |
| --- | --- |
| Checkpoint registry | Existing approved hub; personal owner-only or project-safe per-user hub |
| Task queue | Existing approved queue parent Page and queue ID |
| Audience | Verified effective owner/group grants for each destination |
| Coordinator | Actual configured coordinator identity, separate from the proposing Dot when applicable |
| Arbiter | Exact designated arbiter identity and authoritative host/store |
| Consumer | Actual intended chat/task identity; unresolved identity stays pending |
| Local pickup | Approved queue config/store and folder routes on this host |
| Cloud pickup | Explicit reader/publisher/arbiter bridge and supported tools |

Personal coordination stays private. A project session receives its project routes and approved audience only. A private mirror may link to a canonical project task; it never duplicates execution. Exclude credentials, applicant details, raw prompts/transcripts and unrelated personal context from all publications. Reuse existing destinations and reminder IDs. Missing access, tools or bindings are explicit gaps, not reasons to create replacement Spaces or a second arbiter.

## Copyable Dot handoff

Replace the angle-bracket fields and remove unassigned routes:

```text
Coordinate through the existing Spaces workflow in DOT-SPACES-HANDOFF.md and the supplied checkpoint/task-queue guidance.
Assigned checkpoint hub: <approved link and audience>.
Assigned task queue: <approved parent link and queue ID>.
Coordinator / sole arbiter / intended consumer: <verified identities and approved bridge>.

Read the newest applicable checkpoints and queue snapshot, keeping source observation dates distinct from capture/publication/read times. Enumerate assigned children with pagination and reconcile human amendments/cancellations. Summarize next actions and decisions without taking over the project coordinator's engineering/review ownership.

For a new action, create an immutable child titled "Task queue proposal — <scope> — <action> — <UTC capture time>" under the assigned queue. Include the stable task/operation IDs, source links, intended consumer, acceptance criteria, timing/conditions, independent authority and the last observed queue/task revisions. Existing tasks/reminders retain their IDs. Never label a proposal an authoritative snapshot or invent a revision. Verify saved content, parent and effective audience; reconcile unknown outcomes before retrying.

A proposal is pending until the designated arbiter returns a linked receipt. Local hooks do not fetch or ingest Space Pages, wake idle sessions or schedule reminders. The local reader must explicitly read and reconcile the proposal. Do not claim acknowledgment, acceptance, scheduling, notification or completion from a Page write. When pickup is absent, return the proposal link and exact gap through this conversation; do not message sessions, create timers or duplicate work without separate authorization.

Publish sanitized checkpoints at material milestones, blockers, decisions and handoff. Keep personal notes private and project facts project-safe. Report actual read/create/edit capabilities separately; native creation can support immutable handoffs even when editing is unavailable. Checkpoint publication, consumption and task dispatch are separate outcomes.
```

Supply [the checkpoint first prompt](CLOUD-SESSION-START.md) when the receiving session also needs the complete capture/publication workflow. Supply the [queue protocol](../task-queue/references/protocol.md) when it needs to prepare operation proposals. Cloud orchestration does not inherit local command hooks. Enterprise-managed remote hooks are a different mechanism, not configured by this package; see the [official hooks documentation](https://learn.chatgpt.com/docs/hooks#managed-hooks-from-requirementstoml).

## What local sessions actually read

| Stage | Implemented behavior | Work left to the authorized agent |
| --- | --- | --- |
| SessionStart | Selects an explicit local folder route; supplies the queue skill, destination/config/store paths and cached nonterminal count | Read current native queue children, snapshots, proposals and human changes |
| Stop | Checks local cached nonterminal tasks for the exact runtime session ID; may emit a nonblocking reminder | Reconcile relevant current state at a safe boundary; suppress unchanged notices through judgment |
| No active turn | No polling, network access, Page enumeration, import or scheduling by these handlers | Pickup waits for an authorized active reader or a separately configured scheduler |
| Cloud task | No inherited laptop command callbacks | Read explicitly supplied guidance/routes and use the designated arbiter bridge |

The helper has no network, proposal importer or title parser. `Task queue proposal` is a discovery convention for people/agents, not a machine ingestion trigger. A new child can exist while the local cached count remains unchanged. In particular, a proposal for a different or unresolved consumer does not trigger this chat's Stop reminder. Five-minute checkpoint freshness guidance is not a five-minute consumer polling service.

For an existing local session that has not loaded this procedure, use:

```text
Read DOT-SPACES-HANDOFF.md from the reviewed repository and the task-queue protocol. Use only this session's explicitly assigned queue/config/store. With native Page tools, enumerate that queue's children through all cursors and read current proposals plus human amendments/cancellations. Reconcile them with the sole arbiter; do not infer ingestion from a hook or cached count. Return a linked discovered/recorded/acknowledged/rejected/pending receipt for the exact proposal and task ID. Do not execute or schedule proposed work without separate authority and the required ownership/claim checks.
```

## Proposal contract and arbiter pickup

There is no automatic child-Page import API in task-queue 0.1.0. The supported ingestion path is an authorized agent reviewing native Pages, then submitting the existing `apply` operation to the configured arbiter. Prose-only Pages are reviewable proposals, not directly executable JSON. A proposal may contain the following sections without inventing a new engine schema:

- Stable task ID, proposed operation ID/type, queue ID and source proposal link.
- Source observation/capture times in UTC; last observed queue revision, and expected **task** revision for an existing-task transition.
- Action, accountable owner, exact consumer, acceptance criteria, dependencies, authority requirements and allowed actions. Unknown owner/consumer/authority stays pending for reconciliation.
- Due time with offset and named zone, or date-only objective; conditional reminders state the condition and any existing scheduler ID. Evidence of a prior schedule remains source-dated.
- An optional fenced JSON operation in the existing [protocol format](../task-queue/references/protocol.md#records-and-transitions). Keep routing metadata outside that operation; task fields are strictly allowlisted. Project requests require `project_safe: true` after disclosure review.

A new `request` operation has `operation_id`, `op: "request"`, verified `actor`, `evidence` and `task`; it does **not** require `expected_revision`. Existing-task transitions use `id` and the current **task** `expected_revision`. A snapshot's queue revision is not a task revision or a queue-wide compare-and-swap field. Do not blindly turn a source-dated queue revision (for example 18) into an operation precondition.

The designated reader/arbiter follows this sequence:

1. Read the assigned parent, complete child inventory, relevant proposals and latest authoritative snapshot; inspect accessible human edits/comments/cancellations. Report incomplete coverage. Verify actual source identity and audience; a Page's asserted actor is not authentication.
2. Reconcile with the current authoritative store: task ID, prior operation IDs/content, consumer, independent authority, existing scheduler IDs and terminal/canceled work. Do not create a second task because the first is missing from a stale snapshot.
3. For a new request, a configured coordinator must reconcile and register it. If the Dot is not that coordinator, do not impersonate it or silently add it to the allowlist: the configured coordinator authors the operation and cites the original proposal/user authority in `evidence`/`source_refs`. Unresolved routing or authority remains pending with a concrete reason.
4. For a stale existing-task revision, reread and reconcile current intent before a new operation. If content changes, use a new operation ID and cite the superseded proposal/operation; the same ID with different content is rejected. An exact retry returns its original receipt, which can be historical. Never rebase a cancellation or human edit away.
5. Use the existing helper only on the sole authoritative store. Registering `requested` is not consumer acknowledgment. Only the exact intended consumer can `ack`, then `accept`; independently authorized execution additionally requires satisfied dependencies and a current claim/token. If that consumer/bridge is unavailable, publish a pending receipt rather than acknowledging on its behalf.
6. Publish and verify the authoritative snapshot with the queue protocol's access/claim/readback/acknowledgment steps. Then create a sanitized immutable receipt child under the same assigned queue and return its link through the approved handoff path. No direct session message is implied.

Receipt convention (agent-authored Markdown, not an engine parser): title `Task queue receipt — <task ID> — <UTC time>`. Include proposal Page link, task and proposed/applied operation IDs, disposition (`discovered`, `recorded/requested`, `acknowledged`, `rejected`, or `pending`), actual actor/consumer, resulting task and queue revisions when a transition occurred, authoritative snapshot link, UTC read/transition/publication times, and exact next owner/action or rejection reason. Mark unknowns. Verify full content, parent and audience before calling the receipt published. Never put private claim tokens in a Page.

An acknowledgment receipt must cite a real successful `ack` transition by the intended consumer. A maintainer discovering a proposal, a coordinator registering it, and a helper accepting JSON are different events. The **receipt convention is newly documented**; it is not evidence that any previous proposal has been imported or acknowledged.

## Reminders and acceptance

Queue entries do not wake agents or install timers. Personal reminder delivery remains with the explicitly assigned personal coordinator; project engineering remains with its project coordinator. If no exact reminder consumer and supported scheduler are bound, say `reminder delivery unconfigured/pending`. Do not assume the repository maintainer is a permanent reminder worker. Reconcile existing automation IDs before any separately authorized scheduling action; preserve all current nudges. Use UTC for evidence/reporting and the declared local zone for meeting/reminder times. Do not infer notification delivery from scheduling or a local run.

For one separately authorized real proposal or isolated fixture, verify these gates individually:

| Gate | Required evidence |
| --- | --- |
| Proposal published | Exact content, approved parent/audience and stable IDs read back |
| Reader discovered | Actual reader identity, proposal link and UTC read time |
| Arbiter reconciled | Duplicate/current-revision/human-change review and real registration or concrete rejection/pending reason |
| Consumer acknowledged/accepted | Actual matching transitions; no coordinator impersonation |
| Claimed/executed | Current private claim plus independent authority and execution evidence, if execution was authorized |
| Reminder scheduled/run/delivered | Existing ID reconciliation and separate supported configuration/run/delivery receipts, if scheduling was authorized |
| Coordinator informed | Exact receipt/snapshot revision and source date returned by the consuming coordinator |

Do not use a documentation update as authority to execute a live proposal, notify collaborators, create a reminder or claim that these gates passed. Historical adoption reports should retain their observation dates; source commits, deployment, local hook execution, independent cloud pickup and consumer readback each need their own current evidence.
