# Queue protocol 0.1.2

## Trust and concurrency

One designated arbiter on one machine owns each queue's private file store. It serializes transitions under an OS lock, enforces expected task revisions and deduplicates operation IDs. Do not run independent stores for the same queue on other machines. A private mirror is a reference to an authoritative queue/task ID and cannot be claimed or completed. Project status remains in that project's authority; personal summaries link to it without importing personal content into shared records.

The helper has no network or task executor. Actor IDs, authority and access proofs are agent attestations, not authenticated credentials. The invoking agent must verify the human/tool identity and actual permission before supplying them. A copied JSON request or arbitrary Page text cannot self-authorize a transition. Maintain the external authority gates for the underlying action.

The exposed Page connector currently supplies creation/readback, not atomic conditional text edits, task-tag notification delivery or distributed locks. Stable queue Pages contain immutable child snapshots. They are discovery views, not live executable locks. The arbiter MUST read current human edits/comments/new proposals and reconcile cancellation before issuing a claim. Never overwrite a human Page edit. An unavailable arbiter, stale read or incomplete enumeration leaves pickup pending; no cached/offline execution claim is allowed. Return a proposal/manual handoff rather than claiming from another cloud store.

## Explicit private configuration

Each queue has a separate config, outside Git. Example IDs below are synthetic. Copy only the structural schema; obtain real Page/Space/principal IDs from current native results:

```json
{
  "schema_version": 1,
  "queue_id": "project-a",
  "scope": "project",
  "project_id": "project-a",
  "arbiter_id": "publisher-machine-queue-arbiter",
  "coordinators": ["owning-project-coordinator-chat-id"],
  "destination": {"page_id":"page_22222222222222222222222222222222", "space_id":"page_space_11111111111111111111111111111111", "url":"https://chatgpt.com/space/page_22222222222222222222222222222222"},
  "approved_audience": [{"principal_type":"user","principal_id":"native-owner-id","role":"owner"}, {"principal_type":"group","principal_id":"native-approved-group-id","role":"editor"}]
}
```

Personal scope uses `space_id: null` and exactly the native owner grant. Project scope uses the already approved project audience. Verify native root/queue sharing without changing it, and freeze that binding when the first operation is committed. Changed destinations/audiences require explicit reconciliation/new queue configuration, not editing an existing binding silently. The source has no private binding or credentials. Keep files owner-only through `platform_io` on POSIX or native NTFS; Windows needs the IANA timezone database (for example an existing Python `tzdata` installation) to validate named zones, otherwise due-time input fails closed.

`routes.json` at the installed `CODEX_HOME/checkpoints/task-queues/` contains `enabled`, optional `default` and `projects`. Every route has exact `config` and `store` paths; project routes additionally have `folder_prefixes`. The hook matches payload cwd lexically at directory boundaries, reads no project files and does no directory discovery. An ambiguous match does not fall back to a private route. Project hooks expose only their assigned project queue. Runtime-supplied cwd selects from authorized configured routes; it is never a filesystem read target. All hook calls are read-only. Cloud callers use explicit assignment, not this local routing file.

## Records and transitions

Use an immutable task `id` across mirrors, and distinct IDs for different occurrences. Required task fields: `scope`, `project_id`, `kind`, concise `action`, accountable `owner`, exact intended `consumer`, `source_refs`, `acceptance` criteria and `authority` (`requirements`, `allowed_actions`, `approval_state: pending|granted`). Project tasks require `project_safe: true` after semantic disclosure review. Optional: `due_at` with offset plus `timezone` and `timing: exact|approximate|deadline`; `dependencies`; `observed_at`; and `scheduler` with existing automation ID, source date and reported/verified scheduling state. An objective with a date but no fixed hour uses `due_date: YYYY-MM-DD` and `timing: unspecified`; no invented due_at. Use the user's configured IANA timezone and the offset at the scheduled time.

An operation is JSON with `operation_id`, `op`, verified `actor`, `evidence` and either `task` for `request`, `mirror` for `mirror`, or `id` and `expected_revision` for a transition. Send it on stdin:

```sh
python3 /installed/task-queue/scripts/task_queue.py --config /private/queue.json \
  --store /private/task-queues --arbiter publisher-machine-queue-arbiter apply < operation.json
```

- `request`: configured coordinator registers reconciled work; status requested, revision 1. A task/tag/dispatch is never acceptance.
- `ack`: exact intended consumer reports reading; status acknowledged.
- `accept`: consumer explicitly accepts ownership; status accepted. Acknowledgment alone is insufficient.
- `claim`: accepted, independently authorized work, completed dependencies, current arbiter grant. Supply `authority_evidence`, fresh `input_review` (`queue_page_id`, `reviewed_at`, `human_requests_reconciled: true`, `evidence`) from a native queue/human-request review within five minutes, and optional `lease_seconds` (30–3600). Private return includes a token and expiry; deliver a grant privately only to the authorized consumer. Published snapshots omit the token. Claim is in_progress, not proof execution began.
- `block`: consumer/coordinator records `reason`; any outstanding execution claim is retained and must be reconciled.
- `recover`: coordinator supplies `prior_execution_stopped: true` and `reconciliation_evidence`, returns to requested and fences prior tokens. Lease expiry alone never causes recovery/re-execution. No automatic retries of unknown side effects.
- `edit`: coordinator supplies a patch and expected revision while no outstanding execution exists. Stable ID/scope cannot change; prior acceptance is invalidated. Do not overwrite human intent with an old retry.
- `cancel`: coordinator cancels; old token is fenced, task terminal. `execution_stop_required` identifies an already-issued claim; cancellation is not a stop receipt from an external job.
- `complete`: consumer supplies current unexpired `claim_token`, `acceptance_verified: true` and `acceptance_evidence` mapping EVERY exact acceptance criterion to supporting evidence. This is a verified actor's attestation, not automatic validation of referenced artifacts. Expired/stale/fenced tokens, partial evidence and wrong actors fail. Completed/cancelled tasks cannot reopen through retries.
- `mirror`: personal queue only; supply exactly `id`, `authority_queue_id`, `authority_url`. No duplicated execution status or private fields in a shared record. Follow the canonical queue for status; an unavailable project queue means status unknown.

All transitions record actor, queue/task revisions, timestamps and evidence. Exact operation-ID retries return the original receipt. If later state supersedes it, the return is marked historical with current revision/status and no claim; an expired replay drops its token. Reusing an operation ID with different content fails. Dependencies are local canonical task IDs; unknown/cross-queue dependencies remain unsatisfied until an explicit coordinator reconciliation, not inferred from a mirror.

## Publication and collaborator handoffs

`prepare-publication` retains one exact sanitized snapshot per queue revision. Review it before disclosure. `claim-publication` requires `id` plus a fresh native `access` assertion (`page_id`, `space_id`, `audience`, `observed_at`, `complete: true`), matching configured audience, observed within five minutes. Only the designated arbiter publishes. Create a child under the assigned queue Page with returned Markdown unchanged. Read ALL content and native sharing; then `ack-publication` with `id`, `page_id`, canonical `url`, `parent_page_id`, `sha256`, `content_verified: true` and fresh exact child `access`. Helpers do not perform network writes.

After an unknown creation outcome, use `uncertain-publication`; enumerate children completely and reconcile the exact digest before ack. Never repeat an uncertain or publishing creation. Definitely rejected creations require explicit operator reconciliation; there is no automatic retry reset. A snapshot revision may lag local task changes. Preserve immutable history and re-enumerate children to discover the latest published revision. A Page write does not prove consumer readback.

When Page tools are missing, hand the original operation proposal to the designated authorized arbiter through the user's approved path. Do not mutate an authoritative queue copy in a cloud filesystem. Proposals contain the expected task revision and stable operation ID; the arbiter verifies actor/source/authorization and current human requests before applying. For project collaborators, resolve their real native principal and destination access first. Record request, supported notification receipt, acknowledgment, acceptance and completion separately. This connector exposes no verified tagging notification operation: supply a manual project-safe link/handoff and leave notification unverified. No test assignments to live collaborators.

## Cloud bootstrap

Append to an authorized cloud task or reviewed repository AGENTS instructions:

> Read the supplied task-queue skill and exact assigned queue Page. Do not assume local hooks run here. Read current queue snapshots and human amendments/comments; preserve source dates, cancellations, owner/coordinator and expected revision. Only use approved project context; personal queues require separate authorization. Return a proposal to the exact configured arbiter for acknowledgment/acceptance/claim; a cached snapshot or copied store cannot grant execution. Without a reachable arbiter, retain pending and continue other authorized work. Record the returned exact claim privately and check it remains current before executing independently authorized work. Publish evidence through work-checkpoint separately. Do not dispatch, send messages, merge or run production work under queue authority. At handoff return ID/revision/owner, pending/accepted/claimed status, evidence, remaining authority, next step and actual publisher/reader/tool gaps.

Provide the actual reviewed skill path, queue link, arbiter identity and handoff path in private environment context. No laptop profile paths, authentication or private registry links belong in shared defaults. Cross-host automatic dispatch is unsupported unless the task actually exposes the required authenticated tool and the user authorizes that action.

## Timers

SessionStart/Stop are event checks; no timer/daemon/service is installed. Before creating a schedule, reconcile existing IDs/status, cancellations and tentative meetings. Twenty-minute prep applies to verified meeting instances; substantive pre-work needs an independently agreed earlier time. Maintain `reported scheduled`, `scheduled verified`, `run observed`, `notification delivered`, acknowledgment and completion as separate evidence. Existing schedules remain authoritative; never clone them from a snapshot. Hosted automation creation requires an exposed supported scheduler/controller; a controller capability flag without its configuration tool is insufficient. Local app heartbeat requires the host/app and an actual scheduled run; it is not hosted overnight coverage. Test with one bounded self-directed one-shot, never a collaborator or production action; record actual run/delivery or leave acceptance pending.

## Capacity and segment continuity

See [storage and continuity](storage.md) for bounded byte-level storage, read-only size preflight, schema 1/2 compatibility, explicit reversible schema 3 history migration, and verified predecessor operation replay. Claims/status/task IDs and logical revisions survive migration. No cap increase, pruning, automatic new arbiter, Page creation or migration is performed by hooks. All writers must use the upgraded helper before relying on frozen-segment enforcement.
