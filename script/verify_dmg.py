"""Verify a read-only DMG. Browser/network checks require --live."""
import argparse
import json
import pathlib
import subprocess
from release_support import ROOT, app_metadata, mounted_dmg, run, verify_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dmg', nargs='?', type=pathlib.Path)
    parser.add_argument('--live', action='store_true', help='Test relocated browser connection and public HTTPS; no provider call.')
    parser.add_argument('--require-notarized', action='store_true', help='Require Developer ID, Hardened Runtime, ticket and Gatekeeper acceptance.')
    args = parser.parse_args()
    if args.dmg is None:
        metadata = app_metadata(ROOT / 'dist/OpenRagnar.app')
        args.dmg = ROOT / ('dist/OpenRagnar-%s-%s.dmg' % (metadata['version'], metadata['architecture']))
    run(['/usr/bin/hdiutil', 'verify', args.dmg], capture_output=True)
    if args.require_notarized:
        from notarize_dmg import preflight
        preflight(args.dmg)
        run(['/usr/bin/xcrun', 'stapler', 'validate', args.dmg], capture_output=True)
    with mounted_dmg(args.dmg) as mount:
        app = mount / 'OpenRagnar.app'
        metadata = verify_app(app, release=args.require_notarized)
        if (mount / 'Applications').readlink() != pathlib.Path('/Applications'):
            raise ValueError('DMG Applications shortcut is incorrect.')
        if args.require_notarized:
            run(['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=2', app], capture_output=True)
        runtime = app / 'Contents/Resources/runtime/bin/python3.12'
        run([runtime, '-I', '-B', '-c', 'import ssl, sqlite3, urllib.request; assert ssl.OPENSSL_VERSION'], capture_output=True)
        report = {'dmg': str(args.dmg), 'mountedReadOnly': True, 'bundledRuntimeImports': True,
                  'app': metadata, 'notarizationVerified': args.require_notarized, 'liveChecksRun': args.live}
        if args.live:
            result = run([app / 'Contents/MacOS/OpenRagnar', '--test-browser'], capture_output=True, text=True, timeout=40)
            output = json.loads(result.stdout)
            if not output.get('connected') or output.get('tools', 0) < 26:
                raise ValueError('Relocated MCP browser connection failed.')
            result = run([runtime, '-I', '-B', '-c', 'import urllib.request;print(urllib.request.urlopen("https://docs.typesafe.ai",timeout=20).status)'], capture_output=True, text=True, timeout=30)
            if result.stdout.strip() != '200':
                raise ValueError('Relocated HTTPS check failed.')
            report.update(relocatedBundledRuntimeHTTPS=True, relocatedMCPBrowserConnection=output)
        verify_app(app, release=args.require_notarized)
        report['signatureVerifiedBeforeAndAfterLaunch'] = True
    args.dmg.with_suffix('.verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
