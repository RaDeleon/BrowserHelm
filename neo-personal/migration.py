"""Conservative BrowserHelm identity migration; private backups, no credential export."""
import json
import os
import pathlib
import re
import shutil
import sqlite3
import tempfile
import uuid

OLD_COMMAND = '/Applications/OpenRagnar.app/Contents/MacOS/OpenRagnar'
NEW_COMMAND = '/Applications/BrowserHelm.app/Contents/MacOS/BrowserHelm'


def owned_entry(entry):
    return (isinstance(entry, dict) and isinstance(entry.get('command'), str)
            and entry['command'].endswith('/OpenRagnar.app/Contents/MacOS/OpenRagnar')
            and entry.get('args') == ['--mcp'] and 'url' not in entry)


def migrate_servers(servers, command=NEW_COMMAND):
    if not isinstance(servers, dict): raise ValueError('Unexpected MCP servers format. No changes made.')
    result = dict(servers)
    if 'openragnar' not in servers: return result
    if not owned_entry(servers['openragnar']):
        raise ValueError('The old openragnar entry is not a recognized app launcher. No changes made.')
    if 'browserhelm' in servers:
        raise ValueError('Both old and new MCP entries exist. Resolve the conflict before migrating.')
    entry = dict(result.pop('openragnar'))
    entry['command'] = command
    result['browserhelm'] = entry
    return result


def migrate_json_text(text, command=NEW_COMMAND):
    data = json.loads(text)
    if not isinstance(data, dict): raise ValueError('MCP configuration is not an object.')
    changed = False
    nodes = [data]
    projects = data.get('projects', {})
    if isinstance(projects, dict): nodes += [p for p in projects.values() if isinstance(p, dict)]
    for node in nodes:
        if 'mcpServers' in node:
            old = node['mcpServers']; new = migrate_servers(old, command)
            if new != old: node['mcpServers'] = new; changed = True
        # Preserve user enable/disable choices under the new server identity.
        for key in ('enabledMcpjsonServers', 'disabledMcpjsonServers'):
            if isinstance(node.get(key), list) and 'openragnar' in node[key]:
                node[key] = ['browserhelm' if n == 'openragnar' else n for n in node[key]]; changed = True
    return json.dumps(data, indent=2, ensure_ascii=False)+'\n' if changed else text


def migrate_codex_text(text, command=NEW_COMMAND):
    import tomllib
    data = tomllib.loads(text)
    servers = data.get('mcp_servers', {})
    expected = dict(data, mcp_servers=migrate_servers(servers, command))
    if expected['mcp_servers'] == servers: return text
    # Only our tables change; comments, permissions, timeout fields and unrelated bytes survive.
    header = re.compile(r'^\s*\[mcp_servers\.(?:openragnar|"openragnar")(?:\.[^\]]+)?\]\s*(?:#.*)?$', re.M)
    matches = list(header.finditer(text))
    if not matches: raise ValueError('Unsupported old TOML table syntax. No changes made.')
    result = text
    for match in reversed(matches):
        tail = re.search(r'^\s*\[', text[match.end():], re.M)
        end = match.end()+tail.start() if tail else len(text)
        block = text[match.start():end]
        block = block.replace('mcp_servers.openragnar', 'mcp_servers.browserhelm', 1).replace('mcp_servers."openragnar"', 'mcp_servers.browserhelm', 1)
        if re.search(r'^\s*command\s*=', block, re.M):
            block = re.sub(r'^(\s*command\s*=)[^\n]*', lambda m:m[1]+' '+json.dumps(command), block, count=1, flags=re.M)
        result = result[:match.start()]+block+result[end:]
    if tomllib.loads(result) != expected:
        raise ValueError('Could not preserve Codex settings. No changes made.')
    return result


def atomic_update(path, original, updated):
    path = pathlib.Path(path)
    if original == updated: return None
    if path.is_symlink(): raise ValueError('Configuration is a symlink. No changes made.')
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.browserhelm-', delete=False) as file:
        temp = pathlib.Path(file.name)
        file.write(updated); file.flush(); os.fsync(file.fileno())
    backup = None
    try:
        if path.is_symlink() or (path.read_bytes() if path.exists() else None) != original:
            raise ValueError('Configuration changed. No changes made.')
        if original is not None:
            backup = path.with_name(path.name+'.browserhelm-'+uuid.uuid4().hex+'.bak')
            with backup.open('xb') as file:
                os.chmod(backup, 0o600); file.write(original)
        os.chmod(temp, 0o600); os.replace(temp, path)
    finally: temp.unlink(missing_ok=True)
    return backup


def migrate_support(old, new):
    """Copy all state; SQLite backup includes WAL. The old directory is retained for rollback."""
    old, new = pathlib.Path(old), pathlib.Path(new)
    if not old.exists(): return False
    if new.exists():
        raise ValueError('BrowserHelm data already exists. Refusing to overwrite or merge histories.')
    if old.is_symlink(): raise ValueError('Old data directory is a symlink. Inspect it before migrating.')
    temp = new.with_name('.browserhelm-migration-'+uuid.uuid4().hex)
    try:
        shutil.copytree(old, temp, ignore=shutil.ignore_patterns('*.sqlite-wal', '*.sqlite-shm'))
        os.chmod(temp, 0o700)
        for source in old.rglob('*.sqlite'):
            target = temp/source.relative_to(old)
            target.unlink()
            with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
                src.backup(dst)
            os.chmod(target, 0o600)
        os.rename(temp, new)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--support', nargs=2, metavar=('OLD', 'NEW'), required=True)
    args = parser.parse_args()
    migrate_support(*args.support)
