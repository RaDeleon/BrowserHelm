"""Install a verified BrowserHelm build and migrate local state/configuration with rollback."""
import argparse
import datetime
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'neo-personal'))
from migration import migrate_codex_text, migrate_json_text, migrate_support, atomic_update
from release_support import verify_app


def prepare(home):
    configs = [home/'.codex/config.toml', home/'.claude.json', home/'Library/Application Support/Claude/claude_desktop_config.json']
    changes = []
    for path in configs:
        if not path.exists(): continue
        if path.is_symlink(): raise ValueError('Client configuration is a symlink: '+str(path))
        original = path.read_bytes()
        text = original.decode('utf-8')
        updated = (migrate_codex_text(text) if path.suffix == '.toml' else migrate_json_text(text)).encode('utf-8')
        if updated != original: changes.append((path, original, updated))
    return changes


def stop_idle_launchers():
    # Explicit --idle-confirmed is required. No BrowserOS or client app is terminated.
    rows = subprocess.check_output(['/bin/ps','-axo','pid=,command='], text=True)
    import re,signal
    pids=[]
    for line in rows.splitlines():
        match=re.fullmatch(r'\s*(\d+) (/Applications/(?:OpenRagnar|BrowserHelm)\.app/Contents/MacOS/(?:OpenRagnar|BrowserHelm))( --mcp)?\s*',line)
        if match:
            pid=int(match[1]);os.kill(pid,signal.SIGTERM);pids.append(pid)
    for _ in range(30):
        remaining=[]
        for pid in pids:
            try:os.kill(pid,0);remaining.append(pid)
            except ProcessLookupError:pass
        if not remaining:return pids
        time.sleep(0.2)
    raise ValueError('A gateway launcher did not exit. Installation stopped before replacing apps or state.')


def counts(folder):
    report={}
    if not folder.exists():return report
    for file in folder.glob('*.sqlite'):
        with sqlite3.connect(file.as_uri()+'?mode=ro',uri=True) as db:
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            report[file.name]={table:db.execute('SELECT COUNT(*) FROM "'+table.replace('"','""')+'"').fetchone()[0] for table in tables}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--idle-confirmed',action='store_true')
    args=parser.parse_args()
    home=pathlib.Path.home();source=ROOT/'dist/BrowserHelm.app';target=pathlib.Path('/Applications/BrowserHelm.app');legacy=pathlib.Path('/Applications/OpenRagnar.app')
    # Synced checkout folders may attach FinderInfo; verify a clean distribution copy.
    with tempfile.TemporaryDirectory(prefix='browserhelm-install-verify-', dir='/private/tmp') as folder:
        clean = pathlib.Path(folder)/'BrowserHelm.app'
        subprocess.run(['/usr/bin/ditto','--norsrc','--noextattr',str(source),str(clean)],check=True)
        verify_app(clean,release=False)
    changes=prepare(home)
    old=home/'Library/Application Support/OpenRagnar';new=home/'Library/Application Support/BrowserHelm'
    if new.exists():raise ValueError('BrowserHelm support directory already exists. Review it before migration.')
    if target.exists():raise ValueError('BrowserHelm is already installed. Review it before migration.')
    if not args.apply:
        print(json.dumps({'install':str(target),'clientConfigsToMigrate':[str(p) for p,_,_ in changes],'stateSource':str(old),'stateTarget':str(new),'requiresIdleConfirmation':True},indent=2));return
    if not args.idle_confirmed:raise ValueError('Wait for all active browser work before installing; pass --idle-confirmed only after verifying it is finished.')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    rollback=home/'Library/Application Support/BrowserHelm Migration Backups'/stamp
    rollback.mkdir(parents=True,mode=0o700)
    stopped=stop_idle_launchers()
    before=counts(old)
    settings_before=(old/'settings.json').read_bytes() if (old/'settings.json').exists() else None
    migrate_support(old,new)
    if before!=counts(new):raise ValueError('SQLite histories changed during migration. Installation stopped.')
    if settings_before is not None and (new/'settings.json').read_bytes()!=settings_before:raise ValueError('Settings did not migrate exactly.')
    backups=[]
    try:
        subprocess.run(['/usr/bin/ditto','--norsrc','--noextattr',str(source),str(target)],check=True)
        metadata=verify_app(target,release=False)
        for path,original,updated in changes:
            backup=atomic_update(path,original,updated);backups.append((path,original,updated,backup))
    except Exception:
        for path,original,updated,_ in reversed(backups):atomic_update(path,updated,original)
        # Keep all artifacts for inspection rather than deleting any installation.
        if target.exists():shutil.move(str(target),str(rollback/'BrowserHelm-failed.app'))
        raise
    # Retain the original app privately; Applications has one product entry.
    if legacy.exists():shutil.move(str(legacy),str(rollback/'OpenRagnar.app'))
    report={'version':metadata['version'],'installed':str(target),'rollback':str(rollback),'settingsPreservedExactly':True,'sqliteRowsPreserved':before,'clientBackups':[str(b) for *_,b in backups], 'stoppedIdleLaunchers':stopped,'clientRestartRequired':True}
    (rollback/'migration-report.json').write_text(json.dumps(report,indent=2)+'\n')
    os.chmod(rollback/'migration-report.json',0o600)
    (ROOT/'dist/browserhelm-install-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
