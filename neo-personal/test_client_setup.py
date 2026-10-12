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
        launcher = self.root/'BrowserHelm.app/Contents/MacOS/BrowserHelm'
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
        self.assertEqual(data['mcp_servers']['browserhelm']['args'], ['--mcp'])
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
        for text in ['[mcp_servers.browserhelm]\ncommand="other"\n', 'mcp_servers="bad"\n', 'broken=[', 'mcp_servers={}\n']:
            self.path.write_text(text)
            with self.assertRaises(ValueError): connect_codex(self.command, self.path)
            self.assertEqual(self.path.read_text(), text)
            self.assertEqual(list(self.path.parent.glob('*.bak')), [])

    def test_disabled_existing_entry_stays_disabled(self):
        connect_codex(self.command, self.path)
        self.path.write_text(self.path.read_text()+'enabled=false\n')
        with self.assertRaisesRegex(ValueError, 'disabled'): connect_codex(self.command, self.path)
        self.assertFalse(tomllib.loads(self.path.read_text())['mcp_servers']['browserhelm']['enabled'])

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
        self.assertEqual(list(self.path.parent.glob('.browserhelm-*')), [])

    def test_custom_codex_home(self):
        with patch.dict(os.environ, {'CODEX_HOME':str(self.root/'custom')}):
            self.assertEqual(codex_config_path(), self.root/'custom/config.toml')


@unittest.skipIf(tomllib is None, 'Packaged Python 3.12 provides tomllib')
class DisconnectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.command = str(self.root/'BrowserHelm.app/Contents/MacOS/BrowserHelm')
        self.path = self.root/'config.toml'

    def tearDown(self): self.tmp.cleanup()

    def remove(self, client='codex'):
        from client_setup import disconnect_client
        return disconnect_client(self.command, client, self.path)

    def test_codex_removes_owned_and_nested_tables_preserving_unrelated_bytes(self):
        import json
        prefix = '# keep\nmodel="same"\n[mcp_servers.neo]\nurl="http://localhost:9010/mcp"\n'
        suffix = '[projects."/repo"]\ntrust_level="trusted"\n'
        own = '[mcp_servers."browserhelm"]\ncommand='+json.dumps(self.command)+'\nargs=["--mcp"]\nenabled=false\n[mcp_servers.browserhelm.tools.run]\nenabled=false\n'
        original=prefix+own+suffix;self.path.write_text(original)
        self.assertIn('removed from Codex',self.remove())
        self.assertEqual(self.path.read_text(),prefix+suffix)
        backup=list(self.root.glob('*.bak'))[0]
        self.assertEqual(backup.read_text(),original)
        self.assertEqual(backup.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_claude_keeps_other_servers_and_app_preferences(self):
        import json
        self.path=self.root/'claude.json'
        other={'theme':'dark','mcpServers':{'neo':{'url':'keep'},'browserhelm':{'command':self.command,'args':['--mcp'],'enabled':False}}}
        self.path.write_text(json.dumps(other))
        self.remove('claude');other['mcpServers'].pop('browserhelm')
        self.assertEqual(json.loads(self.path.read_text()),other)

    def test_remove_twice_and_absent_file_do_not_create_or_rewrite(self):
        self.assertIn('not configured',self.remove());self.assertFalse(self.path.exists())
        self.path.write_text('model="keep"\n');original=self.path.read_bytes()
        self.assertIn('not configured',self.remove());self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(list(self.root.glob('*.bak')),[])

    def test_codex_only_entry_leaves_valid_empty_config(self):
        import json
        self.path.write_text('[mcp_servers.browserhelm]\ncommand='+json.dumps(self.command)+'\nargs=["--mcp"]\n')
        self.remove();self.assertEqual(tomllib.loads(self.path.read_text()),{})

    def test_conflicts_invalid_format_and_inline_table_fail_without_writing(self):
        for text in ['[mcp_servers.browserhelm]\ncommand="other"\nargs=["--mcp"]\n','broken=[','mcp_servers="bad"', 'mcp_servers={browserhelm={command='+repr(self.command)+',args=["--mcp"]}}']:
            self.path.write_text(text)
            with self.assertRaises(ValueError):self.remove()
            self.assertEqual(self.path.read_text(),text)
            self.assertEqual(list(self.root.glob('*.bak')),[])

    def test_symlink_refused(self):
        target=self.root/'actual.toml';target.write_text('model="keep"\n');self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'symlink'):self.remove()
        self.assertTrue(self.path.is_symlink());self.assertEqual(target.read_text(),'model="keep"\n')

    def test_racing_writer_preserved(self):
        import json
        self.path.write_text('[mcp_servers.browserhelm]\ncommand='+json.dumps(self.command)+'\nargs=["--mcp"]\n')
        original_temp=tempfile.NamedTemporaryFile
        def race(*args,**kwargs):
            self.path.write_text('model="new"\n');return original_temp(*args,**kwargs)
        with patch('migration.tempfile.NamedTemporaryFile',side_effect=race):
            with self.assertRaisesRegex(ValueError,'changed'):self.remove()
        self.assertEqual(self.path.read_text(),'model="new"\n')
        self.assertEqual(list(self.root.glob('*.bak')),[])
