# Build and install GPT Space Hooks

The `gpt-space-hooks/` package distributes two cloud-facing skills for checkpoints and task handoffs. The [repository](../README.md) is the authoritative source. The pilot uses only the native capabilities already available to the chat and the destinations explicitly assigned to it.

## Build the portable ZIP

From the repository root, use Python 3.11 or later:

```sh
python plugins/build_plugin.py
python -m zipfile -t plugins/dist/gpt-space-hooks-plugin-0.1.1.zip
```

The manifest sets the version in the filename. Use `--output-dir PATH` to build elsewhere. Edit `plugins/gpt-space-hooks/` to change the skills and manifest. If you add a supporting file, include its reviewed relative path in the builder's `FILES` list. The output is reproducible for identical source bytes and includes only the approved plugin files. Attach the versioned ZIP to a GitHub Release for the corresponding signed source tag. Use the named plugin asset, which has the expected layout, when creating a plugin from an archive. GitHub's automatic source ZIP contains the full repo.

## Install from a repo in Codex

From a reviewed checkout, register the repository marketplace and install its plugin on clients with these commands:

```sh
codex plugin marketplace add .
codex plugin add gpt-space-hooks@gpt-space-hooks-marketplace
```

You can also register a GitHub repository URL with `codex plugin marketplace add <repo-url> --ref <reviewed-ref>`. Existing GitHub access is required for private repos. In ChatGPT desktop, use the repo marketplace in **Plugins** and install GPT Space Hooks. Check availability on the installed client and start a fresh chat after installing. The marketplace resolves its local plugin path from the checkout root.

## Import into Enterprise or create a private copy

- **Enterprise workspace administrator:** Use **Admin → Plugins → Add → Import marketplace**. Enter the approved GitHub repository URL, leave **Path** empty, and start with the reviewed tag or commit. The GitHub account must have repo access. Review import results and select the pilot roles. Use a tracked branch only when that branch is ready for workspace sync. [Enterprise marketplace import](https://learn.chatgpt.com/docs/enterprise/plugin-management)
- **Private ZIP copy:** In a workspace where private plugin creation is available, select the intended workspace and provide the versioned ZIP to the supported plugin-creation flow. With Plugin Creator available, give it the ZIP and ask it to save a private GPT Space Hooks plugin in that workspace. Resolve an existing plugin before creating another copy. Workspace sharing and permissions require their own setup.

Verify both skills load in a fresh chat. In an approved test registry or queue, check reading, a prepared checkpoint and a handoff. A chat without native Page/send access should return a copyable draft or handoff and identify the missing capability.

The GitHub marketplace and release ZIP support distribution without a public ChatGPT listing. A future public directory listing is a separate submission.

The plugin has no bundled MCP server. Direct chat delivery requires an exposed native Codex send-message capability, a verified destination and explicit user authorization. This capability is optional for skills that draft, read or publish through other approved paths. For a private pilot, verify that a chat without send access returns a copyable handoff. Test a real send only to an explicitly authorized test chat. [Pipeline requirements and fallbacks](../implementation/runbooks/DOT-SPACES-HANDOFF.md#capabilities-by-step)

The local Codex workflow uses Python, machine-specific permissions and hook trust. Install or update it using the [POSIX](../implementation/runbooks/INSTALL-POSIX.md) or [Windows](../implementation/runbooks/INSTALL-WINDOWS.md) runbook. A future Codex bundle with lifecycle hooks would need separate per-runtime testing, including duplicate-handler checks for hosts that already use the installer. Personal bindings, application IDs, queue data and credentials belong outside the portable package.
