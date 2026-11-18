# Storage capacity and segment continuity — task-queue 0.1.2

Use this reference for a near-capacity queue, a versioned history upgrade or an explicitly authorized rollover. Read current native queue requests/cancellations separately. Storage maintenance never grants task execution or scheduling authority.

## Before a write

The primary state, each immutable object and each exact backup retain the **8 MiB byte limit**. UTF-8 bytes are counted, not characters. History remains private under the same store/arbiter. No records are pruned and no claim/token/owner/status/task revision is renewed or invented.

```sh
python3 /installed/task-queue/scripts/task_queue.py --config /private/queue.json --store /private/store storage-status
python3 /installed/task-queue/scripts/task_queue.py --config /private/queue.json --store /private/store --arbiter exact-arbiter preflight < exact-operation.json
```

`storage-status` reports physical bytes/headroom, logical collection sizes/counts and normal/warning/critical pressure (80% / 95% thresholds). `preflight` validates the exact proposed operation and estimates its next primary/object bytes, without recording an operation or returning a claim token. It can report `fits: false`. This is a revision-scoped estimate, not a reservation, grant or execution receipt; normal apply still rechecks the revision, current authority and byte limit. SessionStart includes bounded local capacity context and Stop can surface warning/critical pressure or a frozen route even without a pending task. Suppress unchanged notices through normal agent judgment; no hook polls, imports, migrates or rolls over queues automatically.

## Format compatibility

| Physical schema | Stored inline | Hash-referenced immutable objects |
| --- | --- | --- |
| 1 | All records | None |
| 2 (existing local publication-history patch) | Tasks, mirrors, events, operation replays | Publications |
| 3 | Current tasks, mirrors, events and record indexes | Publications and operation replay records |

The logical API and published task snapshot stay schema 1. Version 0.1.2 reads all three physical formats. Normal writes preserve schema 1/2; schema 3 is entered only through an explicitly authorized migration. Immutable objects are named by SHA-256 under `history/objects`; exact originals under `history/backups`. Reference size/hash and owner-only access are checked before use. The source includes the earlier local publication patch and preserves the merged Windows routing fixes.

Moving operation replay bodies removes the incident's main source of growth without discarding deduplication records. The indexes, current tasks and events still grow, so this is **not unlimited storage**. Inspect pressure at maintenance boundaries and before large transition batches. A single object or remaining primary above 8 MiB still refuses safely; plan an explicitly reconciled rollover rather than silently raising the limit.

## Explicit migration and restore

1. Reconcile and briefly freeze **all queue writers**, including detached commands and old helper processes. Running work may keep its existing claim only if no other command can change the queue during the cutover. Record the current sole arbiter, config/store, exact helper versions and original state hash/revision. Retain every existing route, audience and task identity.
2. Upgrade every participating writer/helper through the guarded installer. Inspect differing installed files and supply their exact expected hashes; do not overwrite the local publication-history patch blindly. Native hook review remains normal. Changing the helper does not migrate data. Old 0.1.0/0.1.1 helpers cannot operate schema 3; keep them stopped and do not revert binaries on a migrated store.
3. Run `verify-history` / `storage-status`. On an **owner-private exact backup/copy**, with its complete history tree and isolated config/store, rehearse migration and exact-byte restore first. Keep the live arbiter authoritative; an isolated fixture is never another execution store. Compare logical task, claim, operation, event, publication and mirror content, not just counts. Do not output claim tokens or commit operator data.
4. With the live writers still frozen and task-specific maintenance authority, supply JSON `{"expected_sha256":"<fresh state bytes digest>","expected_revision":123}` on stdin to `migrate-history`, with the exact `--config`, `--store` and `--arbiter`. It accepts schema 1 or 2 and creates schema 3 without incrementing logical revisions. Exact backups and immutable objects are flushed/read back before atomic primary replacement; parent directories are fsynced on POSIX. Native Windows uses the existing local NTFS privacy/locking adapters; new storage behavior still needs native acceptance.
5. Run `verify-history`, compare full logical digests and claim continuity, then resume only the verified current writers. Publish sanitized maintenance evidence and current queue snapshot through the existing separate Page workflow. A successful file migration does not prove Page publication or consumer readback.

`restore-history` requires a fresh exact current hash/revision and refuses any intervening logical queue/publication change. It restores the immediately prior physical bytes, retaining all backups/objects. A schema 2 → 3 restore returns to schema 2, not all the way back to an older schema 1 backup. After any timeout, replacement/fsync error or interrupted migration, keep writers frozen and inspect the primary schema/hash and retained objects; **verify before retry or restore**. An uncertain write may already have committed. No automatic retry, deletion or rollback occurs.

## Same-arbiter segment rollover

A new Space Page alone does not free local storage. When explicitly authorized, a coordinator may create a successor Page **in the existing approved Space/audience**, with forward/back links, while making a successor local segment under the same authoritative store/arbiter. This release does not automate Page creation or the multi-file cutover. Do not copy a second executable store or auto-follow an arbitrary Page link.

The November 2026 manual convention uses `FROZEN-SEGMENT.json` in the predecessor and `SEGMENT-CONTINUITY.json` in the successor. Version 0.1.2 enforces the frozen marker on operation writes, publication-state changes, preflight, migration and restore. Read/verify remains allowed. Marker presence alone refuses mutation even if its JSON is incomplete. **Older helpers ignore the marker**: stop/reconcile them and upgrade all writers before relying on this protection. Filesystem modes on the old state alone do not fence atomic replacement in a writable parent.

For the reader's supported minimal continuity format (additional audit fields are permitted), all paths below are exact private local paths; never publish them in shared defaults:

```json
{
  "schema_version": 1,
  "sole_arbiter": "exact-arbiter",
  "previous": {
    "queue_id": "segment-one", "root": "/private/store/segment-one",
    "state_sha256": "<64 lowercase hex>", "state_bytes": 12345, "revision": 123
  },
  "successor": {"queue_id": "segment-two", "root": "/private/store/segment-two"}
}
```

Predecessor frozen marker: `previous_state_sha256`, `successor_queue_id`, `successor_root`, `sole_arbiter` and `all_writes_must_use_successor: true`. The helper derives predecessor locations only from portable queue IDs beneath the **same assigned store**; it does not open arbitrary root/config paths supplied by a note. It checks root/backlink/arbiter, old exact bytes/hash/revision, same project/scope and task/revision/claim continuity. All task IDs and mirrors must survive; unchanged task revisions require identical content, and old terminal states cannot reopen. Links with cycles, path escapes, altered predecessors or more than 32 predecessors fail closed.

New operations are checked against retained predecessor replay receipts as well as the active segment. An exact retry returns its recorded result with the existing historical/expiry safeguards; an operation ID with changed content is rejected. It never issues a second claim merely because the active segment's operation map started empty. A valid carried claim may complete against its preserved task revision; expired/canceled/stale claims remain unusable. Never reset revisions, re-ACK on somebody's behalf or reissue authority during rollover.

Before routing writers to a successor, under a coherent freeze and the same queue lock, preserve all logical task/mirror content, task IDs/revisions, owners, statuses, acceptance and exact claim tokens/expiry; retain old state/history and both continuity notes durably. Verify exact Page content/audience and both direction links independently. Route/config replacement is an explicit multi-file maintenance operation with a written recovery point; a half-finished cutover stays frozen pending reconciliation. The coordinator owns sequencing. Do not “roll back” by restoring an old config after successor writes—this would create competing histories. Reconcile forward to the sole current segment.

## Acceptance evidence

Use isolated fixtures for byte limits, near-limit migration, schema 1/2/3 compatibility, exact restore/refusal after later changes, before/after-replace failures, object corruption/missing refs, frozen old writers, predecessor retry conflicts, live-claim completion and expiry. Then record actual installed/tested/source commits and native OS acceptance during a separately coordinated upgrade. Synthetic tests do not establish that today's running sessions have changed helpers or that a live queue was migrated.


## Copyable session upgrade handoff

```text
Fetch reviewed main from the workflow repository and read task-queue/references/storage.md (under implementation/ in a checkout). Upgrade to task-queue 0.1.2 using the guarded installer and exact installed-file hashes, preserving all private routes, histories and normal hook trust. Coordinate a brief writer freeze with the sole arbiter; stop old helper processes before relying on segment fencing. Verify the assigned current segment, predecessor chain, preserved claims and storage pressure; rehearse migration/restore only on an isolated private copy. Installation alone must not migrate live data, renew/replay claims, create a queue or timer, dispatch work or change schedules. Return source/tested/installed commit, OS, passed/pending checks and the exact maintenance step needing separate authority.
```
