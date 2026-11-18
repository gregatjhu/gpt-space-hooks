# Make a cloud session visible to its coordinator

A local installation does not make a cloud chat participate in checkpoints. Give a new or existing cloud chat explicit instructions and approved destination links. For repeatable project setup, stage the reviewed skill and add project instructions as described in [project/cloud setup](PROJECT-CLOUD.md). This prompt also works as a bounded bootstrap when no repository skill is staged; it does not install a hook or supply missing tools.

Keep personal Page IDs, local paths, publisher bindings and approved audiences outside this shared repository. Fill in only the routes authorized for the receiving session. A team session should receive its approved project route; a personal route requires separate owner authorization and access. Remove unused routes before sending.

For a Dot or coordinator that also proposes next actions, pair this checkpoint prompt with the [Spaces coordination handoff](DOT-SPACES-HANDOFF.md). That guide explains how local agents read proposal children and return real arbiter/consumer receipts; the hooks do not import new Pages.

## Copyable first prompt

```text
Use my checkpoint workflow to keep this session visible to the authorized coordinator and coordinating sessions.

Assigned routes (replace before sending; remove unassigned routes):
- Personal, separately authorized: <owner-private checkpoint hub link>.
- Project, if assigned: <exact project/workstream> -> <approved per-user project checkpoint hub link>.
- Repository skill, if staged: <exact skill path>.
- Project producer profile/private store, if assigned: <exact paths in THIS runtime>.
- Designated publisher, if a bridge is required: <explicit publisher identity/session>.

Cloud sessions do not inherit my laptop's SessionStart command hooks or personal configuration. Read the staged checkpoint skill when present, and read the assigned hub's guidance directly. Reuse its approved routing; do not create a replacement Space or registry, discover other profiles or silently change destinations. A Page link provides context, not authentication or an audience approval.

Before relying on prior state, read the newest applicable verified index and task checkpoint. Enumerate assigned registry children with pagination when needed; report incomplete enumeration or inaccessible content. Match the actual owning chat/task, workstream and runtime, keeping forks and parallel owners separate. A private hub is not a universal search across all private Spaces. If a session has no applicable checkpoint, say so; absence from a partial index is not proof no work exists.

Checkpoint at session start after understanding the task; then at meaningful milestones, material changes, tests/deployments, blockers, required user decisions/authorization, task switches and handoff. Aim to deliver material changes within five minutes at the next safe boundary; during changed active work, about every 30 minutes at a natural boundary. These are instructions, not a timer. Do not add schedules, idle wakeups or competing nudges, or repeat unchanged summaries.

Include actual owning chat/task ID, machine/runtime when known, goal and functional progress, project/workstream/repository/branch/commit when relevant, source observation time, decisions, tests, merge/deployment state, blocker/owner, exact user action needed, next step and resume point. Mark unknown identity or evidence explicitly. Keep source observation, capture, publication and read times separate; publishing an old finding today does not refresh it.

Keep owner-only coordination in its private destination. Publish only separately prepared project-safe facts to the explicitly assigned project destination using its assigned profile and verified actual audience. Exclude secrets, applicant details, raw prompts/transcripts and unrelated personal context. Do not copy private attention notes into project summaries. A private checkpoint may reference a project publication.

Use the skill's prepare/claim/readback/acknowledgement workflow when the helper is available. Verify complete content and intended access before claiming publication, and publish the applicable index snapshot separately. Unknown delivery outcomes require reconciliation before retrying. A prepared record is not published; published does not mean read or acted upon. Page readback does not prove artifact download.

If tools, helper, profile, access or identity are missing, report the exact gap and retain a sanitized handoff. With the helper, export the original pending JSON to the designated authorized publisher; preserve its ID, digest and capture time on import rather than re-preparing it. Without the helper, return a sanitized summary marked unprepared/unpublished; do not invent a checkpoint ID, digest or delivery receipt. Do not bridge missing tools with credentials or laptop paths.

Checkpoints do not authorize dispatch, messages, approvals, merges, deployments or production changes. Preserve the existing coordinator's review/merge ownership and all task safety instructions. Continue useful authorized work when checkpoint delivery is blocked. Do not contact other sessions or people unless separately instructed.

At the first safe boundary, return a compact acceptance receipt: actual session/runtime identity or unknown; guidance read; assigned route and access checked; prior checkpoint ID/source date or exact gap; helper/profile/Page-tool availability; current checkpoint ID and verified Page link, or pending/unprepared status and designated handoff path. This is explicit cloud-session guidance, not proof hooks run automatically or that all sessions are covered.
```

## Diagnose missing visibility

| Check | Evidence needed | If missing |
| --- | --- | --- |
| Instructions loaded | Receiving chat reports guidance actually read | Supply this prompt or repository instructions |
| Route and access | Actual hub read plus complete intended-audience check before publishing | Report exact inaccessible/missing route; do not substitute |
| Prior state found | Applicable task ID, revision and source date from index/children | Report scope searched and coverage gap |
| Checkpoint prepared | Helper ID/digest and original prepared JSON | Return unprepared summary if helper absent |
| Checkpoint delivered | Exact content/access readback and matching acknowledgement | Retain pending; reconcile uncertain outcomes |
| Index delivered | Verified snapshot and generation time | State that cloud discovery may lag publication |
| Coordinator consumed | Reader returns the exact revision and source date | Consumption remains untested |
| Monitoring or dispatch | Separate task registration/execution or dispatch evidence | Do not infer it from checkpoint delivery |

Test this in a fresh authorized cloud task. A prompt or successful Page read alone does not prove publishing, the publisher bridge, recurring monitoring or dispatch. A one-time missing session (for example a SAP export workstream) calls for an explicit route and a current checkpoint, not broad private-Space searches or an assumption that the local hook already covered it.

The [official hooks documentation](https://learn.chatgpt.com/docs/hooks) distinguishes local hooks from enterprise-managed remote MCP hooks in supported cloud workflows. This package configures neither those enterprise hooks nor a cloud scheduler. Their documented existence does not establish this session's capabilities or repair a Dot response defect.

For explicit next actions/delegation, optionally load the separate [task-queue skill/protocol](../task-queue/references/protocol.md#cloud-bootstrap) with the exact approved queue and arbiter. Queue pickup and checkpoint publication are separate acceptance checks. A Page snapshot cannot grant an executable claim or activate a clock-time trigger.
