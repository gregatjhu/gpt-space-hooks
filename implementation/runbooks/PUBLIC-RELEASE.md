# Public source preparation

Keep one reusable source repository. Keep private destination bindings, checkpoint histories, receipts, backups, coordinator instructions and exclusions outside it. Each installation uses its own existing authentication and explicitly approved personal or project registry; copying code does not transfer access or authorization.

## Review the selected export

1. Review the explicit source allowlist and verify the archive built with `python3 build_package.py` against its SHA-256 manifest. For a source repository release, also review the root README, repository metadata and any plugin source. Build the plugin ZIP separately using `plugins/README.md` from the source repository. Do not copy an operator checkout or its whole Git history.
2. Review all selected source files, including tests and runbooks, for personal identifiers, private destinations, credentials and private excerpts. Regex checks help find known patterns; they are not a complete disclosure review.
3. Start the public repository with the reviewed source files and a fresh signed root commit. Preserve the operator repository locally. Do not push operator branches, tags or history to the public repository, and do not use a mirror push. Signed commits expose the signing key fingerprint and author identity as public provenance; confirm those are intended.
4. Verify the export has only the intended branch and commits, and that its archive matches the reviewed source. Use a separately trusted maintainer key fingerprint to verify signatures; a signature does not decide license or prove absence of secrets.

## When the repository endpoint arrives

Confirm the exact repository identity and visibility. Add only that endpoint to the prepared source repository. Fetch its current `main` if present, inspect any existing collaborators' work, and reconcile before pushing an explicitly scoped feature branch. Use review/PR to merge; do not force-push or replace an existing default branch. A URL alone is not proof the repository is empty.

If reusing the URL of a renamed repository, first update and verify every active checkout, integration and link that should still resolve to the original repository. A new repository at the former URL takes over that address. Keep the candidate repository private during review and native OS acceptance. Verify its refs and visibility again before any public release.

Future shared releases come from this one core. Each machine uses the bounded installer/runbook and hash-checked upgrades. Local configuration and personal instructions remain separate; private forks, branch synchronization and deployment hooks are not required. Source review and per-OS acceptance still apply to each relevant change.

## Capability limits

This is a filesystem skill plus local command hooks, not a public-directory plugin or a generic cloud delivery service. Publication depends on native ChatGPT Page tools exposed in the running task. CLI or cloud tasks without those tools retain pending checkpoints. Cloud readers need explicit registry context; delivery, reader consumption and task dispatch are separate checks.

Use `ACCEPTANCE.md` after installation on each machine/runtime. Linux results cannot establish native Windows/macOS/WSL behavior. Preserve existing nudges; the cadence instructions create no background timer.
