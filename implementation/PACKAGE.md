# Work checkpoint workflow 0.3.4

A reusable Codex skill and small local hook helper for prepared work handoffs. No server, database, daemon, transcript reader, credential bridge or recurring scheduler. Cloud publication uses the connected Page tools already available to an authorized task. The package does not include a registry binding, checkpoint history, credentials, config backups or session inventory.

## Behavior

- SessionStart supplies the skill, exact helper invocation and actual session ID when the runtime supplies it.
- New checkpoints carry an explicit machine label and actual chat ID when known. Forks stay separate. Labels and legacy records remain unverified.
- Schema 2 index/status separates capture time, evidence time, delivery state and the last published checkpoint. Upgrading never changes old record IDs, Markdown or receipts.
- Milestones should be delivered at the next safe agent boundary, aiming within five minutes. Changed active work should checkpoint about every 30 minutes at a natural boundary. These are instructions, not timing guarantees.
- Optional Stop checks emit a nonblocking read-only reminder. They ignore raw assistant text, transcript paths and cwd, and cannot publish, write metadata or force continuation. A separately authorized `note ID` records that the reminder was reported, suppressing unchanged state.
- Pending/publishing/uncertain/published delivery states retain the existing claim, exact readback, private-sharing verification and acknowledgement rules. Unknown outcomes are never automatically retried.
- Explicit project profiles isolate per-user project stores, bind a Space/registry/audience, and require fresh sharing proof at claim and acknowledgement. Capture, publication, reader consumption and artifact download remain separate evidence.

## Requirements and installation

Version 0.3.4 includes adapters for Linux, macOS, WSL and native Windows, with Python 3.11 or later. Linux/POSIX execution is tested here. Windows ACL/command/locking contracts are simulated here; real Windows, macOS and WSL acceptance remain pending. POSIX uses UID ownership, modes 0700/0600 and flock. Native Windows uses current-user-only protected NTFS ACLs and msvcrt byte-range locking. Local NTFS, existing ownership and ordinary Windows PowerShell policy are required; failures stop without broadening access. A working local Codex config with explicit `sandbox_mode = "workspace-write"` is required. The installer refuses other/managed permission profiles rather than silently changing them. Hook support and trust must be checked in the installed runtime, independently of skill discovery or newer docs.

Inspect the package, then run from its extracted directory:

```sh
python3 install.py --codex-home "$HOME/.codex"
python3 install.py --codex-home "$HOME/.codex" --install
```

The first command is a dry run. The installer uses the invoking Python executable by default; `--python` can specify its absolute installed path. `CODEX_HOME` can choose a custom home, or use `--codex-home` explicitly. The helper resolves the checkpoint store from its installed skills tree. No fixed username/home path is embedded in this package. See the bounded [Windows runbook](runbooks/INSTALL-WINDOWS.md), [POSIX runbook](runbooks/INSTALL-POSIX.md) and [per-machine acceptance](runbooks/ACCEPTANCE.md). The packaging session performs no remote installation.

The installer preserves unrelated config, developer instructions, writable roots and hook entries. It adds a global instruction link, the checkpoint store writable root and SessionStart hook. It refuses symlinked/unowned target paths and unexpected existing skill files. Backups stay in the private local checkpoint store; the package builder never includes them. This is a multi-file update with input concurrency checks and backups, not an atomic transaction across all files.

To add the optional Stop reminder, include `--enable-stop-check`. Review changed hook definitions in Codex through its normal trust flow; installation does not grant trust. Public-directory plugin packaging is not used because lifecycle-hook distribution has additional restrictions. Filesystem skill installation, plugin installation, cloud task context and workspace-managed skills are separate mechanisms.

For an upgrade, inspect the exact existing `SKILL.md`, `scripts/checkpoint.py`, `scripts/platform_io.py`, `scripts/project_scope.py` and `references/project.md` when present; make a JSON file mapping those relative names to their SHA-256 hashes. Use `--upgrade --expected-hashes /absolute/path/to/hashes.json`, first as a dry run and then with `--install`. Modified or mismatched installed files stop the upgrade. The installer does not edit trust stores or connector settings.

## Bind the private destination separately

Supply a user-approved owner-only registry. Reuse it if already configured; provisioning a new registry is a separate authorized action. An authorized Page-capable session must verify the Page owner and complete sharing/inherited-access information before supplying `set-destination` with `page_id`, canonical `url` and `owner_only: true`. Each machine keeps its own private local store and binding. Do not copy authentication, config backups or checkpoint histories through this package.

The helper has no network access. CLI/cloud environments without connected Page tools retain prepared checkpoints as pending. A Page-capable authorized session can deliver them. File replication alone does not make a local index cloud-readable. Cloud coordinators need explicit registry-reading instructions and independent readback acceptance. This package does not repair task dispatch.

## Verification and release

```sh
python3 -m unittest test_checkpoint.py test_platform_io.py test_project_scope.py
python3 build_package.py
```

The tests cover concurrent claims, uncertain outcomes, matching receipts, legacy compatibility, identity separation, evidence timestamps, the nonblocking guard, bounded path handling and preserving installations/upgrades. A fresh-session acceptance must also test desktop and bundled CLI in two unrelated folders. Skill discovery or an instruction link alone is not proof a hook executed.

Windows paths/Unicode are encoded as data, and files receive private ACLs before sensitive bytes are written. No execution-policy bypass, ownership takeover or credential transfer is used. NTFS access control does not encrypt data or exclude a privileged OS administrator.

The archive contains only the builder's explicit source allowlist and a SHA-256 manifest. Inspect the archive manifest before sharing. A local signed Git commit records the source release; no remote upload or repository publication is implied. Other-machine acceptance and actual Stop-hook execution remain required after installation and trust review.

## Personalization and public sharing

The code resolves the installing user's paths, identity and OS permissions. It has no fixed private Page ID, home path, account SID or connector credential. Destination bindings, prepared checkpoints, publication receipts, backups and session coverage evidence live outside the release source. Copying this package does not transfer authentication, Page ownership/sharing or cloud-task capabilities.

Version 0.3.4 uses neutral recipient and permission wording. Installation is not authorization to publish; the user supplies standing or task-specific scope. Fresh installs use a neutral instruction marker. Upgrades recognize an existing instruction link and preserve its approved text byte for byte, including older personal customizations, without adding a duplicate block.

Use one shared source repository and signed releases. Keep each installation's destination, machine/coordinator labels and local permissions in private local configuration or a small local instruction overlay, outside Git. Put personal authorization, recipient labels and exclusions in existing local Codex developer instructions or an optional separately installed personal skill. The core does not discover or load arbitrary overlay files. Preserve such instructions through the hash-checked upgrade instead of editing the shared core. A private fork, branch synchronization or deployment hooks are unnecessary for this separation. Ordinary release tests and the explicit archive allowlist are useful; publication/deployment automation can wait until a destination and release policy are chosen.

Shared releases require a review of the exported source and honest per-OS acceptance results. The public export starts a fresh signed Git history containing only the source allowlist; operator history is retained locally. Native Windows/macOS/WSL execution remains unverified; Linux simulation is not a substitute. Only reviewed source belongs in a distribution repository.

Default personal mode targets an owner-only ChatGPT Page registry. Explicit project mode targets a per-user registry beneath an approved project Space with its declared audience. The routes use separate stores and receipts; personal notes/attention fields are excluded from project summaries. Native Page tools must be supplied by the task environment. It is not a generic delivery client for every provider. A repository/filesystem-skill installer is the current distribution route: OpenAI's public plugin directory presently excludes plugins with lifecycle hooks, even though manual Codex desktop plugin installation can support them.

Follow [project/cloud setup](runbooks/PROJECT-CLOUD.md) for profile schema, repository skill loading, original-record bridge, per-user indexes and live team acceptance. Cloud orchestration does not run local command hooks. Per-profile locking is local; safe delivery requires one designated publisher/store per profile. There is no distributed Page lock or automatic multi-publisher retry. Project-wide index reconciliation across per-user registries is an explicit consumer workflow.

For explicit cloud-session onboarding, use the [first-prompt template](runbooks/CLOUD-SESSION-START.md). Configure private destinations in task context; verify loaded guidance, route/access, preparation, publication, index freshness and consumer readback separately. A missing helper yields an explicitly unprepared handoff, not an invented receipt.

For the source export and repository handoff, follow [public-release preparation](runbooks/PUBLIC-RELEASE.md).

Optional task-queue 0.1.2 is included in the archive as a separate skill and installer; installing/upgrading checkpoints does not enable it. Follow [task queues](runbooks/TASK-QUEUES.md) for installation, independent hook controls, rollback, cloud pickup and acceptance. The queue installer preserves the checkpoint skill and checkpoint hook definitions. Queue state, routes, bindings and personal notes remain outside the archive. `task_queue_version` in the manifest identifies this companion; the existing checkpoint runtime version remains 0.3.4.

The [Dot/Spaces handoff](runbooks/DOT-SPACES-HANDOFF.md) is included in the source/archive. It documents coordinator prompts, local agent-led pickup, proposal/receipt conventions and exact revision/ownership boundaries. It adds no network importer, scheduler or runtime handler; installable engine versions are unchanged.

Official references: [Codex hooks](https://learn.chatgpt.com/docs/hooks), [protected Windows ACLs](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.objectsecurity.setaccessruleprotection), [Windows locking](https://docs.python.org/3/library/msvcrt.html), [plugin lifecycle hooks](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks), [skill distribution](https://learn.chatgpt.com/docs/enterprise/skills#skill-distribution-and-administration).

Storage capacity: task-queue 0.1.2 adds [bounded history and segment continuity](task-queue/references/storage.md). Use `storage-status` and exact-operation `preflight`; migration is explicit and reversible only before later logical writes. Upgrade all writers together before relying on frozen-segment guards. No live queue migration is performed by installation.
