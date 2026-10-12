"""Package an existing app. Developer ID builds produce a signed DMG."""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile
from release_support import ROOT, checksum, run, sign, signing_identity, verify_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=pathlib.Path, default=ROOT / 'dist/BrowserHelm.app')
    parser.add_argument('--output-dir', type=pathlib.Path, default=ROOT / 'dist')
    args = parser.parse_args()
    identity = signing_identity(os.environ.get('BROWSERHELM_SIGNING_IDENTITY', '-'))
    with tempfile.TemporaryDirectory(prefix='browserhelm-dmg-', dir='/private/tmp') as work:
        stage = pathlib.Path(work) / 'contents'
        stage.mkdir()
        run(['/usr/bin/ditto', '--norsrc', '--noextattr', args.app, stage / 'BrowserHelm.app'])
        # File providers can attach FinderInfo after an app was signed. Validate
        # the clean distribution copy; never strip metadata from the input app.
        metadata = verify_app(stage / 'BrowserHelm.app', release=identity != '-')
        if identity == '-' and metadata['signature']['authority']:
            raise ValueError('Set BROWSERHELM_SIGNING_IDENTITY to package a certificate-signed app; do not silently produce an unsigned DMG.')
        args.output_dir.mkdir(parents=True, exist_ok=True)
        dmg = args.output_dir / ('BrowserHelm-%s-%s.dmg' % (metadata['version'], metadata['architecture']))
        (stage / 'Applications').symlink_to('/Applications')
        run(['/bin/cp', ROOT / 'README-BrowserHelm.md', stage / 'START-HERE.md'])
        image = pathlib.Path(work) / dmg.name
        run(['/usr/bin/hdiutil', 'create', '-volname', 'BrowserHelm', '-srcfolder', stage, '-format', 'UDZO', image], capture_output=True)
        if identity != '-':
            sign(image, identity)
            from release_support import verify_developer_signature
            verify_developer_signature(image, team=metadata['signature']['team'])
        run(['/usr/bin/hdiutil', 'verify', image], capture_output=True)
        run(['/usr/bin/ditto', '--norsrc', '--noextattr', image, str(dmg) + '.partial'])
        pathlib.Path(str(dmg) + '.partial').replace(dmg)
    print(json.dumps({'dmg': str(dmg), 'sha256': checksum(dmg),
                      'signing': 'Developer ID; notarization pending' if identity != '-' else 'Ad-hoc; local testing only'}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
