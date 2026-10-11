import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from client_setup import connect_codex, codex_config_path
try:
    import tomllib
except ImportError:
    tomllib = None


@unittest.skipIf(tomllib is None, 'Packaged Python 3.12 provides tomllib')
class CodexSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        launcher = self.root/'OpenRagnar.app/Contents/MacOS/OpenRagnar'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('fixture'); launcher.chmod(0o700)
        self.command = str(launcher)
        self.path = self.root/'.codex/config.toml'
        self.path.parent.mkdir()

    def tearDown(self): self.tmp.cleanup()

    def test_preserves_existing_bytes_and_values_and_private_backup(self):
        old = '# keep comment\nmodel = "example"\n[mcp_servers.neo]\nurl = "http://localhost:9010/mcp"\n[projects."/a"]\ntrust_level = "trusted"\n'
        self.path.write_text(old)
        connect_codex(self.command, self.path)
        self.assertTrue(self.path.read_text().startswith(old))
        data = tomllib.loads(self.path.read_text())
        self.assertEqual(data['mcp_servers']['neo']['url'], 'http://localhost:9010/mcp')
        self.assertEqual(data['mcp_servers']['openragnar']['args'], ['--mcp'])
        backups = list(self.path.parent.glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), old)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_new_file_and_second_click_idempotent(self):
        connect_codex(self.command, self.path)
        old = self.path.read_bytes()
        self.assertIn('already configured', connect_codex(self.command, self.path))
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(list(self.path.parent.glob('*.bak')), [])

    def test_conflicts_and_invalid_toml_unchanged(self):
        for text in ['[mcp_servers.openragnar]\ncommand="other"\n', 'mcp_servers="bad"\n', 'broken=[', 'mcp_servers={}\n']:
            self.path.write_text(text)
            with self.assertRaises(ValueError): connect_codex(self.command, self.path)
            self.assertEqual(self.path.read_text(), text)
            self.assertEqual(list(self.path.parent.glob('*.bak')), [])

    def test_disabled_existing_entry_stays_disabled(self):
        connect_codex(self.command, self.path)
        self.path.write_text(self.path.read_text()+'enabled=false\n')
        with self.assertRaisesRegex(ValueError, 'disabled'): connect_codex(self.command, self.path)
        self.assertFalse(tomllib.loads(self.path.read_text())['mcp_servers']['openragnar']['enabled'])

    def test_symlink_not_replaced(self):
        target = self.root/'actual.toml'; target.write_text('model="keep"\n')
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'): connect_codex(self.command, self.path)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_text(), 'model="keep"\n')

    def test_changed_config_not_overwritten(self):
        self.path.write_text('model="old"\n')
        original_temp = tempfile.NamedTemporaryFile
        def raced_temp(*args, **kwargs):
            self.path.write_text('model="new"\n')
            return original_temp(*args, **kwargs)
        with patch('client_setup.tempfile.NamedTemporaryFile', side_effect=raced_temp):
            with self.assertRaisesRegex(ValueError, 'changed'): connect_codex(self.command, self.path)
        self.assertEqual(self.path.read_text(), 'model="new"\n')
        self.assertEqual(list(self.path.parent.glob('.openragnar-*')), [])

    def test_custom_codex_home(self):
        with patch.dict(os.environ, {'CODEX_HOME':str(self.root/'custom')}):
            self.assertEqual(codex_config_path(), self.root/'custom/config.toml')
