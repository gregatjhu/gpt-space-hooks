# Linux macOS and WSL installation

Run locally on the chosen machine. Packaging does not authorize a remote install. Linux execution is tested; macOS and WSL require independent acceptance. WSL uses the Linux adapter and its own Codex home, not native Windows hooks/config. Use a Linux filesystem in WSL; do not assume `/mnt/c` honors private POSIX modes and flock semantics.

Identify the exact Codex home and installed Python 3.11+ executable without scanning home or dumping environment variables. Respect exact-file approval boundaries for config/hooks and prior skill files. Inspect installed runtime help and versions, distinguishing the desktop runtime from PATH CLI. Do not install prerequisites or change managed settings silently.

From an extracted package directory (or `implementation` in a Git clone):

```sh
python3 -m unittest test_checkpoint.py test_platform_io.py
python3 install.py --codex-home "$HOME/.codex"
python3 install.py --codex-home "$HOME/.codex" --install
```

The dry run must precede the authorized application. Use `--python /absolute/installed/python3` when needed. For a known custom Codex home, pass it explicitly; do not discover it by searching. The installer requires an existing explicit workspace-write config and preserves unrelated instructions, writable roots and hooks. It refuses symlinked/unowned targets and permission profiles it cannot safely preserve.

The package uses UID ownership, directories 0700, files 0600, safe opens and flock. On macOS `/tmp` can itself be a symlink; use its resolved `/private/tmp` path for disposable tests rather than weakening path checks. The installer intentionally rejects symlink/reparse ancestors; choose an explicitly approved real local path. An installer failure is a gap to reconcile, not permission to bypass checks.

Add `--enable-stop-check` only when wanted. Review changed hook definitions through normal Codex trust; do not edit trust settings or use a bypass. The Stop check is read-only and cannot publish or force continuation. Separately authorized `note ID` suppresses a reported unchanged reminder.

For upgrades, inspect the exact known installed skill files and provide their hashes via `--upgrade --expected-hashes /approved/hashes.json`. Existing IDs and receipts remain untouched. Backups stay private in the checkpoint store and are excluded from the package.

Bind the existing owner-only registry separately using its approved link and live Page sharing verification. Do not copy authentication/config backups from another machine. CLI environments without Page tools remain pending. Complete `ACCEPTANCE.md`; no successful file copy, instruction link or CLI test alone proves desktop/cloud compatibility.
