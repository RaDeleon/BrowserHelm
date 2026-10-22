"""Shared macOS packaging checks; no credential reads or network requests."""
import contextlib
import hashlib
import pathlib
import plistlib
import re
import subprocess
import tempfile
from artifact_policy import is_private_artifact

ROOT = pathlib.Path(__file__).resolve().parent.parent
MACHO_MAGIC = {bytes.fromhex(value) for value in
               ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}
DEVELOPER_ID_REQUIREMENT = 'anchor apple generic and certificate leaf[field.1.2.840.113635.100.6.1.13] exists'


def run(arguments, **kwargs):
    return subprocess.run([str(value) for value in arguments], check=True, **kwargs)


def signing_identity(value):
    if value == '-':
        return value
    if not value.startswith('Developer ID Application: ') or '\n' in value or '\r' in value:
        raise ValueError('Use "-" for local builds or the full "Developer ID Application: …" certificate name.')
    return value


def sign(target, identity, executable=False):
    identity = signing_identity(identity)
    arguments = ['/usr/bin/codesign', '--force', '--sign', identity]
    if identity != '-':
        arguments += ['--timestamp']
        if executable:
            arguments += ['--options', 'runtime']
    run(arguments + [target], capture_output=True, text=True)


def macho_files(directory):
    for path in sorted(pathlib.Path(directory).rglob('*')):
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as file:
                if file.read(4) in MACHO_MAGIC:
                    yield path


def signature(target):
    result = run(['/usr/bin/codesign', '-dvvv', target], capture_output=True, text=True)
    details = result.stderr + result.stdout
    authorities = re.findall(r'^Authority=(.+)$', details, re.MULTILINE)
    team = re.search(r'^TeamIdentifier=(.+)$', details, re.MULTILINE)
    return {'authority': authorities[0] if authorities else None,
            'team': team.group(1) if team else None,
            'hardenedRuntime': bool(re.search(r'flags=.*\([^\n]*\bruntime\b', details)),
            'timestamp': bool(re.search(r'^Timestamp=.+$', details, re.MULTILINE))}


def require_developer_id(details, hardened=False, team=None):
    if not (details.get('authority') or '').startswith('Developer ID Application: '):
        raise ValueError('Public release requires Developer ID Application signing; this is a local/test build.')
    if details.get('team') in (None, '', 'not set') or not details.get('timestamp'):
        raise ValueError('Public release requires a Team ID and secure signing timestamp.')
    if hardened and not details.get('hardenedRuntime'):
        raise ValueError('Public release executable is missing Hardened Runtime.')
    if team and details['team'] != team:
        raise ValueError('Bundled code and DMG must belong to the same signing team.')
    return details


def verify_developer_signature(target, hardened=False, team=None):
    try:
        details = require_developer_id(signature(target), hardened=hardened, team=team)
    except subprocess.CalledProcessError as error:
        raise ValueError('Public release requires a signed Developer ID artifact; unsigned/local builds cannot be notarized.') from error
    # Certificate display names alone are not proof of an Apple-issued identity.
    run(['/usr/bin/codesign', '--verify', '--strict', '-R', DEVELOPER_ID_REQUIREMENT, target], capture_output=True, text=True)
    return details


def app_metadata(app):
    app = pathlib.Path(app)
    with (app / 'Contents/Info.plist').open('rb') as file:
        info = plistlib.load(file)
    version = info.get('CFBundleShortVersionString', '')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', version):
        raise ValueError('App has an invalid version for a DMG filename.')
    if info.get('CFBundleIdentifier') != 'com.techinsf.browserhelm' or info.get('CFBundleExecutable') != 'BrowserHelm':
        raise ValueError('Expected the BrowserHelm app bundle.')
    executable = app / 'Contents/MacOS/BrowserHelm'
    architectures = run(['/usr/bin/lipo', '-archs', executable], capture_output=True, text=True).stdout.split()
    if set(architectures) == {'arm64'}:
        architecture = 'arm64'
    elif set(architectures) == {'x86_64'}:
        architecture = 'x86_64'
    elif set(architectures) == {'arm64', 'x86_64'}:
        architecture = 'universal'
    else:
        raise ValueError('Unsupported or missing app architecture.')
    return {'version': version, 'architecture': architecture}


ENGINE_FILES = {
    'gateway.py', 'decision.py', 'vision.py', 'executor.py', 'browserhelm.py',
    'openragnar.py', 'launch.py', 'metrics.py', 'task_metrics.py', 'sqlite_support.py', 'client_setup.py',
    'migration.py', 'experience.py', 'diagnostics.py', 'version.py', 'vision-models.json',
}
RESOURCE_ENTRIES = {'engine', 'runtime', 'README.md', 'LICENSE', 'NOTICE', 'AppIcon.icns', 'AppIcon.png'}


def verify_distribution_contents(app):
    """Reject development/user artifacts without reading their contents."""
    app = pathlib.Path(app)
    for path in app.rglob('*'):
        relative = path.relative_to(app)
        if (is_private_artifact(relative.as_posix()) or
            any(part in ('test', 'tests', 'fixtures', 'benchmarks', 'design', '__pycache__', '.git') for part in relative.parts)):
            raise ValueError('Local/test artifact is not distributable: ' + relative.as_posix())
    contents = app / 'Contents'
    for directory, allowed in ((app, {'Contents'}),
                               (contents, {'MacOS', 'Resources', 'Info.plist', 'PkgInfo', '_CodeSignature'}),
                               (contents / 'MacOS', {'BrowserHelm'}),
                               (contents / 'Resources', RESOURCE_ENTRIES),
                               (contents / 'Resources/engine', ENGINE_FILES)):
        if not directory.is_dir():
            raise ValueError('Missing distribution directory: ' + str(directory.relative_to(app)))
        for child in directory.iterdir():
            if child.name not in allowed:
                raise ValueError('Unexpected distribution entry: ' + child.relative_to(app).as_posix())


def verify_app(app, release=False):
    app = pathlib.Path(app)
    verify_distribution_contents(app)
    metadata = app_metadata(app)
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app], capture_output=True, text=True)
    resources = app / 'Contents/Resources'
    for notice in ('LICENSE', 'NOTICE', 'runtime/lib/python3.12/LICENSE.txt'):
        if not (resources / notice).is_file():
            raise ValueError('Missing bundled license notice: ' + notice)
    details = signature(app)
    if release:
        verify_developer_signature(app, hardened=True)
        files = list(macho_files(resources / 'runtime'))
        python = resources / 'runtime/bin/python3.12'
        if python not in files:
            raise ValueError('Missing bundled Python executable.')
        for path in files:
            verify_developer_signature(path, hardened=True, team=details['team'])
    return {**metadata, 'signature': details}


@contextlib.contextmanager
def mounted_dmg(dmg):
    with tempfile.TemporaryDirectory(prefix='browserhelm-mount-', dir='/private/tmp') as mount:
        run(['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse', '-quiet', '-mountpoint', mount, dmg])
        try:
            yield pathlib.Path(mount)
        finally:
            run(['/usr/bin/hdiutil', 'detach', '-quiet', mount])


def checksum(dmg):
    dmg = pathlib.Path(dmg)
    digest = hashlib.sha256()
    with dmg.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    dmg.with_suffix(dmg.suffix + '.sha256').write_text(digest.hexdigest() + '  ' + dmg.name + '\n')
    return digest.hexdigest()
