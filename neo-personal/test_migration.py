"""Identity migration preserves user configuration, history and legacy tool access."""
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from migration import (OLD_COMMAND, NEW_COMMAND, migrate_codex_text, migrate_json_text,
                       migrate_support, atomic_update)
from browserhelm import BrowserHelmGateway
try:
    import tomllib
except ImportError:
    tomllib = None


class MigrationTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, 'Packaged Python 3.12 provides tomllib')
    def test_codex_preserves_unrelated_bytes_disabled_state_and_nested_tool_settings(self):
        text = '# private config\nmodel="keep"\n[mcp_servers.neo]\nurl="http://localhost:9010/mcp"\n[mcp_servers.openragnar]\ncommand='+json.dumps(OLD_COMMAND)+'\nargs=["--mcp"]\nenabled=false\nstartup_timeout_sec=40\n[mcp_servers.openragnar.tools.run]\nenabled=true\n[projects."/other"]\ntrust_level="trusted"\n'
        updated = migrate_codex_text(text)
        old, new = tomllib.loads(text), tomllib.loads(updated)
        expected = old['mcp_servers'].pop('openragnar'); expected['command'] = NEW_COMMAND
        self.assertEqual(new['mcp_servers'].pop('browserhelm'), expected)
        self.assertEqual(old, new)
        self.assertTrue(updated.startswith(text[:text.index('[mcp_servers.openragnar]')]))
        self.assertEqual(migrate_codex_text(updated), updated)

    def test_json_migrates_global_project_entries_and_enable_choices_without_other_edits(self):
        entry={'command':OLD_COMMAND,'args':['--mcp'],'enabled':False}
        original={'other':{'unchanged':[1,2]},'mcpServers':{'neo':{'url':'keep'},'openragnar':entry},'projects':{'/repo':{'mcpServers':{'openragnar':entry},'disabledMcpjsonServers':['openragnar','neo']}}}
        new=json.loads(migrate_json_text(json.dumps(original)))
        self.assertEqual(new['other'],original['other'])
        self.assertEqual(new['mcpServers']['neo'],original['mcpServers']['neo'])
        self.assertFalse(new['mcpServers']['browserhelm']['enabled'])
        self.assertEqual(new['projects']['/repo']['disabledMcpjsonServers'],['browserhelm','neo'])
        text=json.dumps(new); self.assertEqual(migrate_json_text(text),text)

    def test_conflicting_or_unowned_entries_are_rejected(self):
        for entries in ({'openragnar':{'command':'other','args':['--mcp']}},
                        {'openragnar':{'command':OLD_COMMAND,'args':['--mcp']},'browserhelm':{'command':'other'}}):
            with self.assertRaises(ValueError): migrate_json_text(json.dumps({'mcpServers':entries}))

    def test_atomic_update_keeps_private_backup_and_refuses_races(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'config';path.write_bytes(b'old')
            backup=atomic_update(path,b'old',b'new')
            self.assertEqual(backup.read_bytes(),b'old');self.assertEqual(backup.stat().st_mode & 0o777,0o600)
            with self.assertRaises(ValueError):atomic_update(path,b'old',b'bad')
            self.assertEqual(path.read_bytes(),b'new')

    def test_sqlite_wal_and_all_files_preserved_without_overwriting_new_data(self):
        with tempfile.TemporaryDirectory() as folder:
            old=pathlib.Path(folder)/'OpenRagnar';new=pathlib.Path(folder)/'BrowserHelm';old.mkdir()
            (old/'settings.json').write_text('{"vision":{"model":"deepseek"}}')
            (old/'outputs').mkdir();(old/'outputs'/'saved.txt').write_text('retained')
            db=sqlite3.connect(old/'metrics.sqlite');db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE history(value)');db.execute('INSERT INTO history VALUES (42)');db.commit()
            try:
                self.assertTrue(migrate_support(old,new))
                with sqlite3.connect(new/'metrics.sqlite') as copied:self.assertEqual(copied.execute('SELECT value FROM history').fetchone()[0],42)
                self.assertEqual((new/'settings.json').read_bytes(),(old/'settings.json').read_bytes())
                self.assertEqual((new/'outputs'/'saved.txt').read_text(),'retained')
                with self.assertRaises(ValueError):migrate_support(old,new)
                self.assertTrue(old.exists())
            finally:db.close()

    def test_legacy_status_tool_still_works_but_catalog_uses_new_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway=BrowserHelmGateway({'provider':'none'},folder)
            try:
                result=gateway._handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'openragnar_status','arguments':{}}})
                self.assertFalse(result['result'].get('isError',False))
                self.assertIn('browserhelm_status',gateway.docs)
                self.assertNotIn('openragnar_status',gateway.docs)
            finally: gateway.moves_pool.shutdown(wait=True)
