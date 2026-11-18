"""POSIX and native Windows adapters. No credentials, discovery, services or networking."""
import base64
import contextlib
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import time


def windows_command(script):
    # Encoded data avoids cmd/PowerShell interpolation of paths, quotes and Unicode.
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    return ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded]


def windows_acl_script(path, action):
    if action not in ('owner', 'verify', 'secure'):
        raise ValueError('Unsupported ACL action')
    encoded = base64.b64encode(json.dumps({'path': str(path), 'action': action}, ensure_ascii=True).encode()).decode()
    return r'''$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
# Python inherits PowerShell 7 module paths; load the Windows PowerShell module explicitly.
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
$d = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(''' + "'" + encoded + "'" + r''')) | ConvertFrom-Json
$p = $d.path
if ($p.StartsWith('\\')) { throw 'UNC/network checkpoint paths are unsupported' }
$root = [System.IO.Path]::GetPathRoot($p)
if ([System.IO.DriveInfo]::new($root).DriveFormat -ne 'NTFS') { throw 'Private checkpoint storage requires local NTFS' }
$item = Get-Item -LiteralPath $p -Force
if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse points are unsupported' }
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = Get-Acl -LiteralPath $p
$owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
if ($owner -ne $sid.Value) { throw 'Path must already be owned by the current user; ownership will not be taken' }
if ($d.action -eq 'secure') {
    if ($item.PSIsContainer) {
        $new = [System.Security.AccessControl.DirectorySecurity]::new()
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    } else {
        $new = [System.Security.AccessControl.FileSecurity]::new()
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow')
    }
    $new.SetAccessRuleProtection($true, $false)
    $new.SetOwner($sid)
    $new.AddAccessRule($rule)
    # Persist only modified owner/DACL sections; Set-Acl can request SACL privilege.
    $item.SetAccessControl($new)
    $acl = Get-Acl -LiteralPath $p
}
if ($d.action -ne 'owner') {
    if (-not $acl.AreAccessRulesProtected) { throw 'Private ACL must disable inheritance' }
    $rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 1 -or $rules[0].IdentityReference.Value -ne $sid.Value -or $rules[0].AccessControlType -ne 'Allow' -or $rules[0].IsInherited -or $rules[0].FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl) {
        throw 'Private ACL verification failed; only the current user may have an explicit FullControl rule'
    }
}
@{owned=$true;private=($d.action -ne 'owner');filesystem='NTFS'} | ConvertTo-Json -Compress
'''


def windows_acl(path, action):
    try:
        result = subprocess.run(windows_command(windows_acl_script(path, action)), capture_output=True, text=True, encoding='utf-8', timeout=4)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Windows ACL verification unavailable or timed out; no access was granted') from error
    if result.returncode:
        # Do not echo arbitrary PowerShell output, paths or caller input in hook diagnostics.
        raise ValueError('Windows ACL check failed: local NTFS, existing ownership and normal PowerShell policy are required; no policy or ownership was changed')
    value = json.loads(result.stdout.strip())
    if value.get('owned') is not True or (action != 'owner' and value.get('private') is not True):
        raise ValueError('Windows ACL verification did not confirm the required access')


def check_path(path):
    path = Path(path)
    for p in (path, *path.parents):
        if p.is_symlink() or (p.exists() and getattr(p.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError('Symlink/reparse installation paths require reconciliation')


def assert_owned(path):
    check_path(path)
    if not path.exists():
        return
    if os.name == 'nt':
        windows_acl(path, 'owner')
    elif path.stat().st_uid != os.getuid():
        raise ValueError('Path must belong to the current user')


def assert_private(path):
    check_path(path)
    if os.name == 'nt':
        windows_acl(path, 'verify')
    else:
        assert_owned(path)
        if path.stat().st_mode & 0o077:
            raise ValueError('Path must be owner-only')


def secure(path):
    check_path(path)
    if os.name == 'nt':
        windows_acl(path, 'secure')
    else:
        assert_owned(path)
        path.chmod(0o700 if path.is_dir() else 0o600)


def private_dir(path):
    check_path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    secure(path)


def open_read(path):
    check_path(path)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    return os.open(path, flags)


def lock_windows(fd, api, timeout=5, sleep=time.sleep, monotonic=time.monotonic):
    deadline = monotonic() + timeout
    while True:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            api.locking(fd, api.LK_NBLCK, 1)
            return
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            if monotonic() >= deadline:
                raise ValueError('Checkpoint store is busy; try again later')
            sleep(0.05)


@contextlib.contextmanager
def file_lock(path):
    check_path(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        secure(path)
        if os.name == 'nt':
            import msvcrt
            # Windows permits locking a byte beyond EOF; no write is needed to seed it.
            lock_windows(fd, msvcrt)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def hook_command(python, script, command, platform=None):
    platform = platform or os.name
    if platform == 'nt':
        data = base64.b64encode(json.dumps({'python': str(python), 'helper': str(script), 'command': command}, ensure_ascii=True).encode()).decode()
        ps = "$ErrorActionPreference='Stop'; $OutputEncoding=[System.Text.UTF8Encoding]::new($false); [Console]::InputEncoding=$OutputEncoding; $d=[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + data + "')) | ConvertFrom-Json; $payload=[Console]::In.ReadToEnd(); $payload | & $d.python $d.helper $d.command; exit $LASTEXITCODE"
        # Only fixed executable/options and Base64 occur in the outer shell command.
        return ' '.join(windows_command(ps))
    import shlex
    return shlex.quote(str(python)) + ' ' + shlex.quote(str(script)) + ' ' + command
