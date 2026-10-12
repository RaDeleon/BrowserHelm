"""Install a local Codex MCP entry without rewriting unrelated TOML."""
import json
import os
import pathlib
import tempfile
import uuid


def codex_config_path():
    root = os.environ.get('CODEX_HOME')
    return (pathlib.Path(root).expanduser() if root else pathlib.Path.home()/'.codex')/'config.toml'


def connect_codex(command, path=None):
    import tomllib
    path = pathlib.Path(path) if path is not None else codex_config_path()
    if not isinstance(command, str) or not command.endswith('/BrowserHelm.app/Contents/MacOS/BrowserHelm'):
        raise ValueError('Install BrowserHelm in Applications before connecting Codex.')
    if not pathlib.Path(command).is_file() or not os.access(command, os.X_OK):
        raise ValueError('BrowserHelm launcher is missing or not executable.')
    if path.is_symlink():
        raise ValueError('Codex configuration is a symlink. Use Copy Codex MCP config to review it.')
    original = path.read_bytes() if path.exists() else None
    text = (original or b'').decode('utf-8')
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        raise ValueError('Codex configuration is invalid TOML. No changes made.') from None
    servers = config.get('mcp_servers', {})
    if not isinstance(servers, dict):
        raise ValueError('Unexpected Codex mcp_servers format. No changes made.')
    if 'browserhelm' in servers:
        entry = servers['browserhelm']
        if isinstance(entry, dict) and entry.get('command') == command and entry.get('args') == ['--mcp'] and 'url' not in entry:
            if entry.get('enabled') is False:
                raise ValueError('BrowserHelm is configured but disabled in Codex. Enable it in Codex MCP settings.')
            return 'BrowserHelm is already configured for Codex. Open a new chat or restart Codex to load its tools.'
        raise ValueError('Another browserhelm entry already exists. Use Copy Codex MCP config to review it. No changes made.')
    from migration import migrate_codex_text
    migrated = migrate_codex_text(text, command)
    if migrated != text:
        from migration import atomic_update
        backup = atomic_update(path, original, migrated.encode('utf-8'))
        return f'BrowserHelm migrated in Codex. Backup: {backup}. Open a new chat or restart Codex to load its tools.'
    updated = text + '\n\n[mcp_servers.browserhelm]\ncommand = ' + json.dumps(command, ensure_ascii=False) + '\nargs = ["--mcp"]\n'
    try:
        parsed = tomllib.loads(updated)
    except tomllib.TOMLDecodeError:
        raise ValueError('Codex configuration needs a manual merge. Use Copy Codex MCP config. No changes made.') from None
    expected = dict(config)
    expected['mcp_servers'] = dict(servers, browserhelm={'command':command, 'args':['--mcp']})
    if parsed != expected:
        raise ValueError('Could not preserve Codex settings. No changes made.')
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.browserhelm-', delete=False) as file:
        temp = pathlib.Path(file.name)
        file.write(updated.encode('utf-8')); file.flush(); os.fsync(file.fileno())
    try:
        # Refuse edits if another writer changed the configuration while parsing.
        if path.is_symlink() or (path.read_bytes() if path.exists() else None) != original:
            raise ValueError('Codex configuration changed. Try again. No changes made.')
        if original is not None:
            backup = path.with_name(path.name+'.browserhelm-'+uuid.uuid4().hex+'.bak')
            with backup.open('xb') as file:
                os.chmod(backup, 0o600); file.write(original)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    suffix = f' Backup: {backup}.' if backup else ''
    return f'BrowserHelm added to Codex. Existing settings and MCP entries preserved.{suffix} Open a new chat or restart Codex to load its tools.'


def connect_claude(command, path=None):
    from migration import migrate_json_text, atomic_update
    path = pathlib.Path(path) if path else pathlib.Path.home()/'Library/Application Support/Claude/claude_desktop_config.json'
    if not command.endswith('/BrowserHelm.app/Contents/MacOS/BrowserHelm') or not os.access(command, os.X_OK):
        raise ValueError('Install BrowserHelm in Applications before connecting Claude.')
    if path.is_symlink(): raise ValueError('Claude configuration is a symlink. No changes made.')
    original = path.read_bytes() if path.exists() else None
    text = (original or b'{}').decode('utf-8')
    data = json.loads(migrate_json_text(text, command))
    servers = data.setdefault('mcpServers', {})
    if not isinstance(servers, dict): raise ValueError('Unexpected mcpServers format. No changes made.')
    if 'browserhelm' in servers and servers['browserhelm'].get('command') != command:
        raise ValueError('Another browserhelm entry already exists. No changes made.')
    servers['browserhelm'] = dict(servers.get('browserhelm', {}), command=command, args=['--mcp'])
    updated = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    backup = atomic_update(path, original, updated)
    return f'BrowserHelm connected to Claude Desktop. Backup: {backup}. Quit and reopen Claude Desktop to load its tools.'


def disconnect_client(command, client, path=None):
    """Remove only this app's matching MCP entry, with a private backup."""
    import re
    import tomllib
    from migration import atomic_update
    if client not in ('codex', 'claude'):
        raise ValueError('Unsupported MCP client.')
    if not isinstance(command, str) or not command.endswith('/BrowserHelm.app/Contents/MacOS/BrowserHelm'):
        raise ValueError('Expected the BrowserHelm launcher path.')
    label = 'Codex' if client == 'codex' else 'Claude Desktop'
    path = pathlib.Path(path) if path is not None else codex_config_path() if client == 'codex' else pathlib.Path.home()/'Library/Application Support/Claude/claude_desktop_config.json'
    if path.is_symlink(): raise ValueError('Client configuration is a symlink. No changes made.')
    if not path.exists(): return f'BrowserHelm is not configured in {label}. No changes made.'
    original = path.read_bytes()
    text = original.decode('utf-8')
    data = tomllib.loads(text) if client == 'codex' else json.loads(text)
    key = 'mcp_servers' if client == 'codex' else 'mcpServers'
    if not isinstance(data, dict) or not isinstance(data.get(key, {}), dict):
        raise ValueError('Unexpected client configuration format. No changes made.')
    servers = data.get(key, {})
    if 'browserhelm' not in servers: return f'BrowserHelm is not configured in {label}. No changes made.'
    entry = servers['browserhelm']
    if not isinstance(entry, dict) or entry.get('command') != command or entry.get('args') != ['--mcp'] or 'url' in entry:
        raise ValueError('The browserhelm entry belongs to another command. No changes made.')
    expected = dict(data)
    expected[key] = {name:value for name,value in servers.items() if name != 'browserhelm'}
    if client == 'claude':
        updated = json.dumps(expected, indent=2, ensure_ascii=False)+'\n'
    else:
        headers = list(re.finditer(r'^[ \t]*\[.+?\][ \t]*(?:#.*)?$', text, re.M))
        own = re.compile(r'^[ \t]*\[mcp_servers\.(?:browserhelm|"browserhelm")(?:\.[^\]\n]+)?\][ \t]*(?:#.*)?$')
        ranges = [(h.start(), headers[i+1].start() if i+1<len(headers) else len(text)) for i,h in enumerate(headers) if own.fullmatch(h.group())]
        if not ranges: raise ValueError('Unsupported TOML table syntax. Remove this entry manually; no changes made.')
        updated = text
        for start,end in reversed(ranges): updated = updated[:start]+updated[end:]
        parsed = tomllib.loads(updated)
        if not expected[key] and key not in parsed: expected.pop(key)
        if parsed != expected: raise ValueError('Could not preserve Codex settings. No changes made.')
    backup = atomic_update(path, original, updated.encode('utf-8'))
    restart = 'Open a new chat or restart Codex' if client == 'codex' else 'Quit and reopen Claude Desktop'
    return f'BrowserHelm removed from {label}. Other settings and MCP entries preserved. Backup: {backup}. {restart} to unload its tools. Existing sessions continue until restarted.'
