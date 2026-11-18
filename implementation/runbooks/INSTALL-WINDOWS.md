# Native Windows installation

For an existing Windows installation adding/updating the separate task-queue workflow, follow the [Windows queue pilot](WINDOWS-TASK-QUEUE-PILOT.md). Keep its native fixes/evidence on the assigned pilot PR until the final head is proven on Windows.

Run this locally on the chosen Windows PC; the packaging session does not connect to it or perform remote installation. Native Windows ACL, locking and checkpoint-helper tests are validated with Python 3.12 launched from PowerShell 7. Full fresh CLI/desktop acceptance and normal hook trust remain separate checks. Native Windows and WSL are separate Codex installations and checkpoint stores. Use the POSIX runbook for WSL, with files inside its Linux filesystem; do not mix its config with native Windows.

## Before changing anything

1. Open the source repository/package in the local Codex session. Identify the exact Codex home, installed Python executable and existing config/hooks/skill files. Respect any outside-folder approval boundary before reading those exact files. Never search the user profile or inspect credentials, environment dumps or transcripts.
2. Check installed help and versions for desktop's runtime and PATH CLI separately. A connected desktop and a separate CLI may use different binaries. Check normal hook review/support in that installed runtime. A global instruction or newer docs do not prove a hook executes.
3. This package requires existing native Python 3.11+ and Windows PowerShell. Identify them with `Get-Command python`, `Get-Command py` and `Get-Command powershell.exe`; do not install missing software automatically. Resolve the actual Python executable, not a Microsoft Store launch alias. If prerequisites or policy block execution, report the exact prerequisite and stop.
4. Use a local NTFS Codex home already owned by the signed-in user. UNC paths, non-NTFS drives, junctions/reparse points, symlinked ancestors and different owners fail closed. Do not take ownership, elevate, alter execution policy or edit hook trust to make installation pass.
5. Review `PACKAGE.md`, source allowlist and manifest. In a Git clone verify the signed release commit against a maintainer public-key fingerprint obtained through a separately trusted channel using the normal Git/GPG installation. Never import a private key from another computer.

## Test and dry run

In PowerShell, from the extracted package directory (or use `implementation` in the Git repository):

```powershell
$checkpointPython = (py -3 -c 'import sys; print(sys.executable)').Trim()
$checkpointHome = Join-Path $env:USERPROFILE '.codex'
& $checkpointPython --version
& $checkpointPython -m unittest test_checkpoint.py test_platform_io.py test_project_scope.py
& $checkpointPython install.py --codex-home $checkpointHome --python $checkpointPython
```

If `py` is unavailable, set `$checkpointPython` to the approved absolute existing Python executable. If a custom Codex home is configured, explicitly set `$checkpointHome` to that known path; do not guess or scan for it. These commands read named variables only; do not dump environments. The tests create disposable local files and exercise native NTFS ACLs and concurrency; request the normal permission required to run them.

The dry run preserves settings and does not write installation targets. It reads only the explicitly named config/hooks and known installed skill files. Stop on errors; do not substitute a less restrictive permission mode. An explicit workspace-write config is currently required; the installer does not rewrite managed/default permission profiles.

## Apply after the concrete dry run is approved

```powershell
& $checkpointPython install.py --codex-home $checkpointHome --python $checkpointPython --install
```

Include `--enable-stop-check` only if the nonblocking reminder is wanted and the installed runtime supports it. Codex's normal hook review must approve changed definitions. No bypass flag or trust-store edit is part of this package.

Existing skill installations require `--upgrade --expected-hashes <approved JSON path>` mapping the exact existing known skill files to SHA-256 digests. Inspect those exact files first. Older releases have two or three known files; this release has five. Supply hashes only for the exact known files that already exist. Conflicting files or modifications stop the upgrade.

The Windows ACL adapter explicitly loads the security module shipped with Windows PowerShell 5.1, so a Python process launched from PowerShell 7 cannot select the incompatible PowerShell 7 module. It persists only modified owner and DACL sections through .NET, avoiding Set-Acl's audit-privilege requirement on directories created with Python's 0700 mode. Existing-owner checks and exact private-ACL readback remain mandatory.

The adapter sets/reads ACLs on exact owned target files/directories only, not whole drives. Private stores, backups and temporary output files get a protected current-user-only FullControl DACL, with no inherited entries. ACL verification must succeed before sensitive content is written. It does not take ownership or grant administrator/SYSTEM/public ACEs. Local administrators retain OS-level takeover capabilities, as root does on POSIX; this is access control, not password encryption or protection from a privileged compromised OS. Enterprise endpoint/PowerShell restrictions may prevent the adapter from running; report them without changing policy.

## Bind and prove delivery

Supply the existing private registry link separately through the approved local task. Use exposed Page read/sharing tools to verify owner-only access before setting the destination. The package contains no Page IDs, connector authentication or machine-specific bindings. Do not copy another machine's credentials or complete `.codex` directory.

Run `ACCEPTANCE.md` on this Windows installation. Record installed runtime versions, native ACL verification, two-folder desktop/CLI loading, read-only Stop behavior, prepared/published delivery and independent cloud readback as separate results. A Windows runbook or successful Linux simulation is not Windows acceptance.

References: [Microsoft Set-Acl](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-acl), [protected ACL inheritance](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.objectsecurity.setaccessruleprotection), [Python Windows byte-range locking](https://docs.python.org/3/library/msvcrt.html), [Codex hooks](https://learn.chatgpt.com/docs/hooks).
