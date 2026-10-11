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
    if not isinstance(command, str) or not command.endswith('/OpenRagnar.app/Contents/MacOS/OpenRagnar'):
        raise ValueError('Install OpenRagnar in Applications before connecting Codex.')
    if not pathlib.Path(command).is_file() or not os.access(command, os.X_OK):
        raise ValueError('OpenRagnar launcher is missing or not executable.')
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
    if 'openragnar' in servers:
        entry = servers['openragnar']
        if isinstance(entry, dict) and entry.get('command') == command and entry.get('args') == ['--mcp'] and 'url' not in entry:
            if entry.get('enabled') is False:
                raise ValueError('OpenRagnar is configured but disabled in Codex. Enable it in Codex MCP settings.')
            return 'OpenRagnar is already configured for Codex. Open a new chat or restart Codex to load its tools.'
        raise ValueError('Another openragnar entry already exists. Use Copy Codex MCP config to review it. No changes made.')
    updated = text + '\n\n[mcp_servers.openragnar]\ncommand = ' + json.dumps(command, ensure_ascii=False) + '\nargs = ["--mcp"]\n'
    try:
        parsed = tomllib.loads(updated)
    except tomllib.TOMLDecodeError:
        raise ValueError('Codex configuration needs a manual merge. Use Copy Codex MCP config. No changes made.') from None
    expected = dict(config)
    expected['mcp_servers'] = dict(servers, openragnar={'command':command, 'args':['--mcp']})
    if parsed != expected:
        raise ValueError('Could not preserve Codex settings. No changes made.')
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.openragnar-', delete=False) as file:
        temp = pathlib.Path(file.name)
        file.write(updated.encode('utf-8')); file.flush(); os.fsync(file.fileno())
    try:
        # Refuse edits if another writer changed the configuration while parsing.
        if path.is_symlink() or (path.read_bytes() if path.exists() else None) != original:
            raise ValueError('Codex configuration changed. Try again. No changes made.')
        if original is not None:
            backup = path.with_name(path.name+'.openragnar-'+uuid.uuid4().hex+'.bak')
            with backup.open('xb') as file:
                os.chmod(backup, 0o600); file.write(original)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    suffix = f' Backup: {backup}.' if backup else ''
    return f'OpenRagnar added to Codex. Existing settings and MCP entries preserved.{suffix} Open a new chat or restart Codex to load its tools.'
