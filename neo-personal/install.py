#!/usr/bin/env python3
"""Legacy Neo-entry migration helpers retained for rollback regression tests.

The direct CLI is disabled. Current connections use a separate OpenRagnar entry.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "installation.json"
SECTION = re.compile(r'^\[mcp_servers\.browseros-neo\]\s*\n.*?(?=^\[|\Z)', re.M | re.S)

def atomic_write(path, text, expected):
    if path.read_text() != expected:
        raise RuntimeError("Configuration changed during preparation; rerun to preserve concurrent edits")
    descriptor, temp = tempfile.mkstemp(prefix=".neo-personal-", dir=str(path.parent))
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def backup(path, text, suffix):
    target = path.with_name(path.name + ".neo-personal-" + suffix + ".bak")
    fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(text)
    return str(target)

def prepare(restore=False):
    codex_path = pathlib.Path.home() / ".codex/config.toml"
    claude_path = pathlib.Path.home() / ".claude.json"
    codex = codex_path.read_text()
    claude = claude_path.read_text()
    match = SECTION.search(codex)
    data = json.loads(claude)
    if not match or "browseros-neo" not in data.get("mcpServers", {}):
        raise RuntimeError("Existing browseros-neo entry missing; refusing to invent or replace unrelated settings")
    original_block = match.group()
    original_claude = data["mcpServers"]["browseros-neo"]
    if restore:
        saved = json.loads(MANIFEST.read_text())
        # Restore only our entry; unrelated settings made after installation survive.
        if str(ROOT / "gateway.py") not in original_block or original_claude.get("args", []) != saved["installedClaude"]["args"]:
            raise RuntimeError("Gateway entries changed since installation; inspect before restoring")
        new_block = saved["originalCodexBlock"]
        new_claude = saved["originalClaude"]
    else:
        if MANIFEST.exists():
            raise RuntimeError("Installation manifest already exists; restore first rather than overwriting rollback data")
        upstream = original_claude.get("url")
        if upstream != "http://127.0.0.1:9010/mcp" or not re.search(r'^url\s*=\s*"http://127\.0\.0\.1:9010/mcp"', original_block, re.M):
            raise RuntimeError("Neo upstream differs from the tested endpoint; inspect before installing")
        new_claude = {"type": "stdio", "command": sys.executable, "args": [str(ROOT / "gateway.py"), "--upstream", upstream, "--profile", "efficient"]}
        # Preserve existing timeouts and other supported fields in this exact block.
        remaining = [line for line in original_block.splitlines()[1:] if line.strip() and not re.match(r'^(url|command|args|env|http_headers|bearer_token_env_var)\s*=', line)]
        new_block = '[mcp_servers.browseros-neo]\ncommand = ' + json.dumps(sys.executable) + '\nargs = ' + json.dumps(new_claude["args"]) + '\n' + '\n'.join(remaining) + '\n\n'
        saved = {"originalCodexBlock": original_block, "originalClaude": original_claude, "installedClaude": new_claude}
    updated_codex = codex[:match.start()] + new_block + codex[match.end():]
    data["mcpServers"]["browseros-neo"] = new_claude
    updated_claude = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    changes = [(codex_path, codex, updated_codex), (claude_path, claude, updated_claude)]
    desktop_path = pathlib.Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if desktop_path.exists():
        desktop = desktop_path.read_text()
        desktop_data = json.loads(desktop)
        original_desktop = desktop_data.get("mcpServers", {}).get("browserclaw")
        if restore and "originalDesktop" in saved:
            if not original_desktop or original_desktop.get("args") != saved["installedClaude"]["args"]:
                raise RuntimeError("Desktop gateway entry changed since installation; inspect before restoring")
            desktop_data["mcpServers"]["browserclaw"] = saved["originalDesktop"]
            changes.append((desktop_path, desktop, json.dumps(desktop_data, indent=2, ensure_ascii=False) + "\n"))
        elif not restore and original_desktop:
            if "http://127.0.0.1:9010/mcp" not in original_desktop.get("args", []):
                raise RuntimeError("Desktop browserclaw targets a different endpoint; inspect before installing")
            saved["originalDesktop"] = original_desktop
            desktop_data["mcpServers"]["browserclaw"] = new_claude
            changes.append((desktop_path, desktop, json.dumps(desktop_data, indent=2, ensure_ascii=False) + "\n"))
    elif restore and "originalDesktop" in saved:
        raise RuntimeError("Desktop config disappeared; inspect before restoring")
    return changes, saved

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    changes, saved = prepare(args.restore)
    print("Restore" if args.restore else "Install", "personal gateway; only the existing Neo MCP entries change.")
    for path, _, _ in changes:
        print(str(path))
    if not args.apply:
        print("Dry run only; add --apply to save. Existing sessions keep their current connection until restarted.")
        return
    suffix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backups = [backup(path, original, suffix) for path, original, _ in changes]
    completed = []
    try:
        for path, original, updated in changes:
            atomic_write(path, updated, original)
            completed.append((path, original, updated))
    except Exception:
        for path, original, updated in reversed(completed):
            atomic_write(path, original, updated)
        raise
    if args.restore:
        MANIFEST.unlink()
    else:
        saved["backups"] = backups
        fd = os.open(str(MANIFEST), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(saved, output, indent=2)
    print("Saved and backed up. Restart/reconnect clients to load the new transport; no browser restart required.")

if __name__ == "__main__":
    raise SystemExit('Legacy Neo-entry replacement installer is disabled. Use OpenRagnar Settings and Connectors, or the separate openragnar MCP entry documented in README-OpenRagnar.md. Its helpers remain only for rollback regression tests.')
