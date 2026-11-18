# Shared project and cloud checkpoints

Use the same engine with an explicit project profile. Default invocation remains the personal owner-only workflow. Project invocation never falls back to personal routing. Apply an explicit approved route from current task context or host instructions; match exact repository identity or directory ancestry, not similar names. If routing is ambiguous, ask for assignment while preserving a pending handoff. Each user has a registry Page beneath the project Space, a separate local profile store, and a designated publisher. The project coordinator reads these approved per-user registries to assemble current project state.

## Profile setup

Locate the Space by exact name and read its root. Reuse or create the user's checkpoint registry only within that approved Space. Read registry metadata and complete native sharing, including direct, inherited and pending grants. The intended audience is the project Space's approved participants. Do not change sharing to make a check pass.

Keep the profile JSON outside the shared engine source and out of public Git. It contains destination and approved audience, not authentication. Use these schema fields:

```json
{
  "schema_version": 1,
  "kind": "project",
  "profile_id": "project-user-a",
  "project_id": "project-a",
  "space_id": "page_space_11111111111111111111111111111111",
  "parent_page_id": "page_22222222222222222222222222222222",
  "url": "https://chatgpt.com/space/page_22222222222222222222222222222222",
  "publisher_id": "designated-publisher-a",
  "approved_audience": [
    {"principal_type": "user", "principal_id": "approved-owner-id", "role": "owner"},
    {"principal_type": "group", "principal_id": "approved-project-group-id", "role": "editor"}
  ]
}
```

The IDs above are synthetic examples. Use exact IDs from native results. Group approval covers that group; group membership is governed separately and is not expanded or monitored by this helper. `project_scope.native_access(metadata, sharing, observed_at)` normalizes complete native Page read/sharing responses. A proof reports resource Page ID, Space ID, complete effective audience and the time of that native read. It is an agent attestation, not an authentication token.

Invoke the engine explicitly:

```sh
python3 /approved/path/work-checkpoint/scripts/checkpoint.py \
  --store /approved/private/checkpoint-store \
  --profile /approved/private/project-profile.json prepare < project-summary.json
```

The actual project store is `STORE/profiles/PROFILE_ID`, protected by the platform adapter. Its frozen binding prevents silently redirecting an existing store or index to another audience. Changing audience/destination requires a new explicitly reviewed profile ID or a deliberate reconciliation; editing a profile is not an automatic migration.

Project summaries require `disclosure: "project"`, matching `project_id`, a stable `workstream_id`, owner, real owning chat/task ID, machine label, repository and commit. Use `unknown` for unavailable commits; unknown evidence/identity cannot support reliable dispatch. Forks retain their own chat IDs and optional `parent_chat_id`. Exclude personal attention fields, private coordinator notes, secrets and applicant details. Free text still needs human/agent review; field filtering cannot recognize every private detail.

## Cloud deployment and loading

Cloud-orchestrated tasks do not execute local command hooks. Repository skills are available in cloud tasks; personal local skills do not sync. Place the reviewed `work-checkpoint` skill directory, including all three helper modules, at the project's `.agents/skills/work-checkpoint` through a reviewed project-repository change. Keep the private profile/store ignored and supply the user's exact approved binding through task/project context. A workspace Skill is another distribution option with separate administration and authorization.

Add this bounded instruction to existing project `AGENTS.md` or supported project instructions, preserving the existing guidance:

> For this project's authorized work, read `.agents/skills/work-checkpoint/SKILL.md` once. Use the exact assigned project-profile path and private store for start, decisions, blockers, test/deployment results and handoff. Read the current approved project registry before resuming. Keep owner/chat/machine/repo/commit and source observation dates explicit. If profile, identity, tool or audience evidence is missing, retain a prepared handoff and report the gap; do not use personal routing, discover credentials, or claim delivery. Optional personal coordination is a separate user-authorized route; never copy personal notes into the project summary.

Package availability alone is not proof that startup loaded the skill. Record fresh cloud context receipt and an actual prepared summary before declaring loading tested. Setup scripts can stage files during authorized environment preparation; they are not completion hooks. This package does not modify project repositories or shared cloud environment settings automatically.

Official references: [cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments), [hooks and cloud orchestration](https://learn.chatgpt.com/docs/hooks), [skill distribution](https://learn.chatgpt.com/docs/enterprise/skills).

## Delivery and publisher bridge

Use one designated publisher identity and one owned publisher store per profile. All producers for that profile hand prepared records to that publisher. Multiple independent publisher stores are not a distributed lock and are unsupported for safe automatic retry. The project can have different per-user publishers/stores because their registries and revisions are distinct.

`claim ID` takes JSON with `publisher_id` and `access`. The access proof must identify the configured parent Page and Space, match the approved effective audience exactly and be no older than five minutes. Create a child text Page with the prepared Markdown unchanged. Read the complete child content/metadata/sharing and use `ack ID` only with:

- `page_id`, canonical `url`, matching `sha256`, and `content_verified: true`;
- exact `parent_page_id`, `space_id`, and native Page creation time as `published_at`;
- `access` from fresh complete native sharing for that child Page.

`release` is only for a definitely rejected creation. Timeouts/unknown outcomes become `uncertain`; reconcile the returned Page or complete registry child enumeration before acknowledging. A fresh claim cannot reset uncertainty. Native text Page creation has no demonstrated cross-publisher idempotency guarantee here.

Without Page tools, `export ID` emits the original pending record as data. An authorized Page-capable publisher uses the same profile and `import` on that exact JSON. Import preserves capture time, checkpoint ID, Markdown and digest, and never resets a previously imported publishing/uncertain/published record. Do not re-run `prepare` on a transferred summary: it would create a different capture/Markdown revision. No transcript or cloud filesystem discovery is needed if the prepared JSON is returned in the task handoff through supported access.

## Index and consumers

Project `index` is schema 3 and contains only that profile's metadata. It reports latest captured and latest published checkpoints separately per project/workstream/machine/chat/repository, with owners and fork lineage. Publish immutable per-user index snapshots alongside checkpoints. A newer snapshot does not refresh observations, and local indexes are unavailable remotely until verified publication.

A project coordinator enumerates the Space's approved per-user registries and all child pages, verifies their placement/audience and exact revisions, and groups by these explicit keys. Keep parallel owners/forks separate, even with the same workstream label. Conflicting ownership is a decision to resolve, not permission to merge tasks or overwrite someone else's index. The current helper computes a per-profile index; project-wide reconciliation across publishers remains a consumer workflow, not a mutable last-writer-wins index file.

`consume ID` records supplied evidence for a published exact revision: `kind` (`read`, `acted`, `artifact_read`), `actor`, timezone-aware `at`, checkpoint `sha256`, and supporting `evidence`. `artifact_read` additionally requires `artifact_id` and matching `artifact_sha256` for an artifact explicitly reported uploaded. These are reported evidence, not polling or telemetry. Published does not imply read; read does not imply acted; reading a Page does not imply downloading an artifact.

Artifacts require `artifact_id`, name, approved location, SHA-256 digest, byte count and `prepared`/`uploaded` state. The helper does not upload/download files. Verify actual consumer download bytes separately, through existing authorized artifact tools. Record missing capability/access rather than substituting filesystem paths that do not resolve for the consumer.

## Live acceptance

Two authorized people use different workstreams and per-user registries in the same project Space. Include an old observation published now, a fork, a pending handoff, and an independently uploaded artifact. A fresh cloud reader must identify each owning chat/machine, latest captured and published evidence, source dates, next actions and artifact accessibility without seeing a personal sentinel. Test Page-tool absence through the local publisher bridge and reconcile an unknown delivery outcome without a duplicate. Record group audience and runtime versions. Source tests are simulations; they do not establish this live team/cloud result.
