import base64
import errno
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch
import subprocess

spec = importlib.util.spec_from_file_location('platform_adapter', Path(__file__).parent / 'work-checkpoint/scripts/platform_io.py')
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)


class Adapters(unittest.TestCase):
    def test_windows_hook_encodes_paths_as_data_without_shell_interpolation(self):
        python = PureWindowsPath("C:/Users/Example Name/$literal's tools/python.exe")
        helper = PureWindowsPath('C:/Users/Example Name/.codex/skills/work-checkpoint/scripts/checkpoint.py')
        cmd = io.hook_command(python, helper, 'session-start', platform='nt')
        outer = cmd.split()
        self.assertEqual(outer[:5], ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand'])
        decoded = base64.b64decode(outer[5]).decode('utf-16-le')
        data = json.loads(base64.b64decode(decoded.split("FromBase64String('")[1].split("')")[0]))
        self.assertEqual(data['python'], str(python))
        self.assertEqual(data['helper'], str(helper))
        self.assertNotIn('Example Name', cmd)
        self.assertNotIn('ExecutionPolicy', cmd)
        self.assertNotIn('Bypass', decoded)
        self.assertIn('exit $LASTEXITCODE', decoded)
        self.assertIn('$payload | & $d.python $d.helper $d.command', decoded)
        self.assertIn('[Console]::InputEncoding=$OutputEncoding', decoded)

    def test_windows_acl_contract_requires_local_ntfs_existing_owner_exact_current_user_rule(self):
        script = io.windows_acl_script(PureWindowsPath('C:/Users/Example/.codex/checkpoints'), 'secure')
        self.assertIn("DriveFormat -ne 'NTFS'", script)
        self.assertIn('UNC/network', script)
        self.assertIn('ReparsePoint', script)
        self.assertIn('must already be owned', script)
        self.assertIn('SetAccessRuleProtection($true, $false)', script)
        self.assertIn('$rules.Count -ne 1', script)
        self.assertIn('$rules[0].IsInherited', script)
        self.assertNotIn('takeown', script)
        self.assertNotIn('BUILTIN', script)
        verify = io.windows_acl_script('C:/test', 'verify')
        self.assertIn("if ($d.action -eq 'secure')", verify)

    def test_windows_acl_failures_and_timeouts_do_not_fall_back_to_chmod(self):
        with patch.object(io.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'Denied sensitive text')):
            with self.assertRaisesRegex(ValueError, 'Windows ACL check failed') as error:
                io.windows_acl(Path('/simulated'), 'secure')
            self.assertNotIn('sensitive', str(error.exception))
        with patch.object(io.subprocess, 'run', side_effect=subprocess.TimeoutExpired('powershell', 4)):
            with self.assertRaisesRegex(ValueError, 'unavailable or timed out'):
                io.windows_acl(Path('/simulated'), 'verify')
        with patch.object(io.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps({'owned': True, 'private': False}), '')):
            with self.assertRaises(ValueError):
                io.windows_acl(Path('/simulated'), 'verify')

    def test_windows_lock_retries_busy_with_bounded_timeout_and_preserves_data(self):
        class API:
            LK_NBLCK = 2
            attempts = 0
            def locking(self, fd, mode, count):
                self.attempts += 1
                if self.attempts < 3:
                    raise OSError(errno.EACCES, 'busy')
                self.offset = os.lseek(fd, 0, os.SEEK_CUR)
        with tempfile.TemporaryFile() as f:
            f.write(b'unchanged');f.flush();f.seek(3)
            api = API()
            io.lock_windows(f.fileno(), api, sleep=lambda _: None)
            self.assertEqual(api.attempts, 3)
            self.assertEqual(api.offset, 0)
            f.seek(0);self.assertEqual(f.read(), b'unchanged')
            class Busy:
                LK_NBLCK = 2
                def locking(self, *args): raise OSError(errno.EACCES, 'busy')
            times = iter([0, 10])
            with self.assertRaisesRegex(ValueError, 'busy'):
                io.lock_windows(f.fileno(), Busy(), monotonic=lambda: next(times), sleep=lambda _: None)
            class Broken:
                LK_NBLCK = 2
                def locking(self, *args): raise OSError(errno.EBADF, 'invalid descriptor')
            with self.assertRaises(OSError):
                io.lock_windows(f.fileno(), Broken())

    def test_posix_modes_and_locking_or_native_windows_acl(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'private'
            io.private_dir(p)
            io.assert_private(p)
            with io.file_lock(p / '.lock'):
                io.assert_private(p / '.lock')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows ACL execution requires a Windows host')
    def test_native_windows_acl_rejects_an_extra_grant_then_restores_exact_private_acl(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'disposable-private.txt'
            p.write_bytes(b'')
            io.secure(p)
            io.assert_private(p)
            data = base64.b64encode(str(p).encode()).decode()
            script = "$ErrorActionPreference='Stop'; Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop; $p=[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + data + "')); $a=Get-Acl -LiteralPath $p; $s=[System.Security.Principal.SecurityIdentifier]::new('S-1-1-0'); $r=[System.Security.AccessControl.FileSystemAccessRule]::new($s,'Read','Allow'); $a.AddAccessRule($r); (Get-Item -LiteralPath $p).SetAccessControl($a)"
            subprocess.run(io.windows_command(script), capture_output=True, check=True)
            with self.assertRaises(ValueError):
                io.assert_private(p)
            io.secure(p)
            io.assert_private(p)


if __name__ == '__main__':
    unittest.main()
