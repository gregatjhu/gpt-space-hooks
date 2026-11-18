# ChatGPT workspace pilot

The `gpt-space-hooks/` package distributes two cloud-facing skills for checkpoints and task handoffs. The [repository](../README.md) is the authoritative source. The pilot uses only the native capabilities already available to the chat and the destinations explicitly assigned to it.

Build the archive from the `plugins` directory with Python 3.11 or later:

```sh
python -m zipfile -c ../gpt-space-hooks-plugin.zip gpt-space-hooks
python -m zipfile -t ../gpt-space-hooks-plugin.zip
```

The archive contains one enclosing `gpt-space-hooks` directory with its portable `plugin.json`, two skills, and the license. Review the members before importing it as a private workspace plugin. Share it only with the pilot audience after verifying both skills load in a fresh chat. Use a test registry or queue with explicitly approved access to verify reading, a prepared checkpoint and a manual handoff. Confirm that a chat without Page tools reports the missing capability accurately.

The plugin has no bundled MCP server. Direct chat delivery requires an exposed native Codex send-message capability, a verified destination and explicit user authorization. This capability is optional for skills that draft, read or publish through other approved paths. For a private pilot, verify that a chat without send access returns a copyable handoff. Test a real send only to an explicitly authorized test chat. [Pipeline requirements and fallbacks](../implementation/runbooks/DOT-SPACES-HANDOFF.md#capabilities-by-step)

The local Codex workflow uses Python, machine-specific permissions and hook trust. Install or update it using the [POSIX](../implementation/runbooks/INSTALL-POSIX.md) or [Windows](../implementation/runbooks/INSTALL-WINDOWS.md) runbook. A future Codex bundle with lifecycle hooks would need separate per-runtime testing, including duplicate-handler checks for hosts that already use the installer. Personal bindings, application IDs, queue data and credentials belong outside the portable package.
