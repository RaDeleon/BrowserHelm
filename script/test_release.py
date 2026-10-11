"""Offline release policy tests. Apple tools are mocked; no signing credentials."""
import contextlib
import hashlib
import json
import pathlib
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import notarize_dmg
import release_support as release
import release_metadata


def developer_signature(**overrides):
    value = {'authority': 'Developer ID Application: Fixture (TESTTEAM01)', 'team': 'TESTTEAM01',
             'timestamp': True, 'hardenedRuntime': True}
    return {**value, **overrides}


class ReleaseTests(unittest.TestCase):
    def test_tag_must_match_source_version(self):
        self.assertEqual(release_metadata.validate_tag('v0.4.3', '0.4.3'), 'v0.4.3')
        for tag in ('v0.4.2', 'main', '0.4.3', 'v0.4.3\nextra', 'v0.4.3;echo nope'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release_metadata.validate_tag(tag, '0.4.3')

    def test_source_version_is_read_without_executing_code(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'version.py'
            source.write_text("raise RuntimeError('must not execute')\nVERSION='0.4.3'\nBUILD='8'\n")
            self.assertEqual(release_metadata.build_metadata(source), {'VERSION': '0.4.3', 'BUILD': '8'})
            source.write_text("VERSION='../other'\nBUILD='8'\n")
            with self.assertRaises(ValueError):
                release_metadata.build_metadata(source)

    def test_adhoc_cannot_pass_release_policy(self):
        with self.assertRaisesRegex(ValueError, 'local/test'):
            release.require_developer_id(developer_signature(authority=None))

    def test_other_certificate_type_cannot_pass_release_policy(self):
        with self.assertRaises(ValueError):
            release.require_developer_id(developer_signature(authority='Apple Development: Fixture'))

    def test_release_requires_secure_timestamp(self):
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            release.require_developer_id(developer_signature(timestamp=False))

    def test_release_requires_team(self):
        for team in (None, '', 'not set'):
            with self.subTest(team=team), self.assertRaises(ValueError):
                release.require_developer_id(developer_signature(team=team))

    def test_runtime_must_be_hardened(self):
        with self.assertRaisesRegex(ValueError, 'Hardened Runtime'):
            release.require_developer_id(developer_signature(hardenedRuntime=False), hardened=True)

    def test_mixed_signing_team_rejected(self):
        with self.assertRaisesRegex(ValueError, 'same signing team'):
            release.require_developer_id(developer_signature(), team='OTHERTEAM1')

    def test_apple_anchor_required_even_with_developer_id_display_name(self):
        with patch.object(release, 'signature', return_value=developer_signature()), patch.object(release, 'run') as run:
            run.side_effect = subprocess.CalledProcessError(1, ['codesign'])
            with self.assertRaises(subprocess.CalledProcessError):
                release.verify_developer_signature('fixture.app', hardened=True)
            self.assertIn(release.DEVELOPER_ID_REQUIREMENT, run.call_args.args[0])

    def test_identity_rejects_wrong_kind_or_multiline(self):
        for value in ('Apple Development: Fixture', '', 'Developer ID Application: Fixture\nextra'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release.signing_identity(value)

    def test_codesign_output_classifies_local_and_release(self):
        adhoc = 'Signature=adhoc\nTeamIdentifier=not set\nCodeDirectory flags=0x2(adhoc)\n'
        public = 'Authority=Developer ID Application: Fixture (TESTTEAM01)\nAuthority=Developer ID Certification Authority\nTeamIdentifier=TESTTEAM01\nCodeDirectory flags=0x10000(runtime)\nTimestamp=Oct 10, 2026\n'
        with patch.object(release, 'run', return_value=subprocess.CompletedProcess([], 0, '', adhoc)):
            self.assertIsNone(release.signature('fixture')['authority'])
        with patch.object(release, 'run', return_value=subprocess.CompletedProcess([], 0, '', public)):
            release.require_developer_id(release.signature('fixture'), hardened=True)

    def test_macho_discovery_includes_extensionless_binaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'python3.12').write_bytes(bytes.fromhex('cffaedfe') + b'fixture')
            (root / 'module.so').write_bytes(bytes.fromhex('cffaedfe'))
            (root / 'plain.txt').write_text('not executable')
            (root / 'alias').symlink_to(root / 'python3.12')
            self.assertEqual({p.name for p in release.macho_files(root)}, {'python3.12', 'module.so'})

    def test_metadata_rejects_filename_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            app = pathlib.Path(directory)
            (app / 'Contents').mkdir()
            with (app / 'Contents/Info.plist').open('wb') as file:
                plistlib.dump({'CFBundleShortVersionString': '../../other'}, file)
            with patch.object(release, 'run') as run, self.assertRaises(ValueError):
                release.app_metadata(app)
            run.assert_not_called()

    def test_metadata_names_image_from_actual_version_and_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            app = pathlib.Path(directory)
            (app / 'Contents').mkdir()
            with (app / 'Contents/Info.plist').open('wb') as file:
                plistlib.dump({'CFBundleShortVersionString': '1.2.3-beta.1', 'CFBundleIdentifier': 'com.techinsf.openragnar', 'CFBundleExecutable': 'OpenRagnar'}, file)
            with patch.object(release, 'run', return_value=subprocess.CompletedProcess([], 0, 'arm64\n', '')):
                self.assertEqual(release.app_metadata(app), {'version': '1.2.3-beta.1', 'architecture': 'arm64'})

    def test_checksum_reflects_modified_stapled_image(self):
        with tempfile.TemporaryDirectory() as directory:
            image = pathlib.Path(directory) / 'fixture.dmg'
            image.write_bytes(b'before ticket')
            first = release.checksum(image)
            image.write_bytes(b'after ticket')
            second = release.checksum(image)
            self.assertNotEqual(first, second)
            self.assertEqual(image.with_suffix('.dmg.sha256').read_text(), hashlib.sha256(b'after ticket').hexdigest() + '  fixture.dmg\n')

    def test_failed_preflight_never_submits(self):
        with patch.object(sys, 'argv', ['notarize_dmg.py', 'fixture.dmg', '--submit', '--profile', 'fixture']), patch.object(notarize_dmg, 'preflight', side_effect=ValueError('local build')), patch.object(notarize_dmg, 'run') as run:
            with self.assertRaises(ValueError):
                notarize_dmg.main()
            run.assert_not_called()

    def test_check_only_never_submits(self):
        with patch.object(sys, 'argv', ['notarize_dmg.py', 'fixture.dmg', '--check']), patch.object(notarize_dmg, 'preflight', return_value={}), patch.object(notarize_dmg, 'run') as run, contextlib.redirect_stdout(None):
            notarize_dmg.main()
            run.assert_not_called()

    def test_rejected_notarization_never_staples_or_updates_checksum(self):
        with patch.object(sys, 'argv', ['notarize_dmg.py', 'fixture.dmg', '--submit', '--profile', 'fixture']), patch.object(notarize_dmg, 'preflight', return_value={}), patch.object(notarize_dmg, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps({'id': 'fixture-id', 'status': 'Invalid'}), '')) as run, patch.object(notarize_dmg, 'checksum') as checksum:
            with self.assertRaisesRegex(ValueError, 'not accepted'):
                notarize_dmg.main()
            self.assertEqual(run.call_count, 1)
            checksum.assert_not_called()

    def test_only_accepted_notarization_staples_and_updates_checksum(self):
        accepted = subprocess.CompletedProcess([], 0, json.dumps({'id': 'fixture-id', 'status': 'Accepted'}), '')
        with patch.object(sys, 'argv', ['notarize_dmg.py', 'fixture.dmg', '--submit', '--profile', 'fixture']), patch.object(notarize_dmg, 'preflight', return_value={}), patch.object(notarize_dmg, 'run', return_value=accepted) as run, patch.object(notarize_dmg, 'checksum', return_value='fixture-sha') as checksum, contextlib.redirect_stdout(None):
            notarize_dmg.main()
            self.assertEqual([call.args[0][1:3] for call in run.call_args_list], [['notarytool', 'submit'], ['stapler', 'staple'], ['stapler', 'validate']])
            checksum.assert_called_once()


if __name__ == '__main__':
    unittest.main()
