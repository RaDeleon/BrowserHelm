"""Check a release DMG, or explicitly submit it using a stored notarytool profile."""
import argparse
import json
import pathlib
import subprocess
from release_support import checksum, mounted_dmg, require_developer_id, run, verify_app, verify_developer_signature


def preflight(dmg):
    run(['/usr/bin/hdiutil', 'verify', dmg], capture_output=True)
    image_signature = verify_developer_signature(dmg)
    with mounted_dmg(dmg) as mount:
        metadata = verify_app(mount / 'OpenRagnar.app', release=True)
        require_developer_id(image_signature, team=metadata['signature']['team'])
        if not (mount / 'Applications').is_symlink() or (mount / 'Applications').readlink() != pathlib.Path('/Applications'):
            raise ValueError('DMG is missing its Applications shortcut.')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dmg', type=pathlib.Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true', help='Local release preflight only; no upload.')
    action.add_argument('--submit', action='store_true', help='Upload this signed DMG to Apple and wait for acceptance.')
    parser.add_argument('--profile', help='Existing notarytool Keychain profile name; no passwords on the command line.')
    args = parser.parse_args()
    if args.submit and not args.profile:
        parser.error('--submit requires --profile with a stored notarytool profile')
    metadata = preflight(args.dmg)
    if args.check:
        print(json.dumps({'releasePreflight': True, 'notarized': False, 'app': metadata}))
        return
    # Only network/upload step; never automatically repeat an uncertain submission.
    result = run(['/usr/bin/xcrun', 'notarytool', 'submit', args.dmg, '--keychain-profile', args.profile,
                  '--wait', '--output-format', 'json'], capture_output=True, text=True)
    submission = json.loads(result.stdout)
    if submission.get('status') != 'Accepted':
        raise ValueError('Notarization was not accepted (submission %s, status %s). Inspect its notarytool log before retrying.' %
                         (submission.get('id', 'unknown'), submission.get('status', 'unknown')))
    run(['/usr/bin/xcrun', 'stapler', 'staple', args.dmg], capture_output=True)
    run(['/usr/bin/xcrun', 'stapler', 'validate', args.dmg], capture_output=True)
    print(json.dumps({'dmg': str(args.dmg), 'notarized': True, 'submission': submission['id'],
                      'sha256': checksum(args.dmg)}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
