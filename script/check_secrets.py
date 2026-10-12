"""Offline secret detection; download a pinned, verified scanner on first use.

No credentials or source files are uploaded. --staged is suitable for pre-commit;
--history scans all locally available refs. Reports redact matching values.
"""
import argparse
import hashlib
import os
import pathlib
import platform
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from artifact_policy import is_private_artifact

VERSION = '8.30.1'
ARCHIVES = {
    ('Darwin', 'arm64'): ('darwin_arm64', 'b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5'),
    ('Darwin', 'x86_64'): ('darwin_x64', 'dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709'),
    ('Linux', 'x86_64'): ('linux_x64', '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'),
    ('Linux', 'aarch64'): ('linux_arm64', 'e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080'),
}


def scanner(root):
    target = ARCHIVES.get((platform.system(), platform.machine()))
    if target is None:
        raise ValueError('Secret scanner supports macOS and Linux on ARM64/x86-64.')
    name, digest = target
    cache = root / '.tools' / 'gitleaks' / VERSION / name
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive = cache / 'gitleaks.tar.gz'
    if not archive.is_file():
        url = f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_{name}.tar.gz'
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Secret-scanner download failed checksum/size validation.')
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as file:
            temporary = pathlib.Path(file.name)
            file.write(data)
        try:
            os.replace(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError('Cached scanner archive failed checksum validation; commit blocked.')
    # Re-extract only this verified member. Do not trust an overwritten cache binary.
    with tarfile.open(archive) as package:
        member = package.getmember('gitleaks')
        if not member.isfile():
            raise ValueError('Scanner archive has no regular executable.')
        data = package.extractfile(member).read()
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as file:
        executable = pathlib.Path(file.name)
        file.write(data)
    executable.chmod(0o700)
    return executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--staged', action='store_true')
    modes.add_argument('--history', action='store_true')
    args = parser.parse_args()
    executable = None
    try:
        root = pathlib.Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip())
        if args.staged:
            paths = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'], cwd=root, capture_output=True, check=True).stdout.split(b'\0')
            blocked = []
            for raw in paths:
                if not raw:
                    continue
                path = pathlib.PurePosixPath(os.fsdecode(raw))
                if is_private_artifact(path):
                    blocked.append(str(path))
            if blocked:
                print('Commit blocked: private configuration, signing material or local state file is staged.', file=sys.stderr)
                for path in blocked:
                    print(repr(path), file=sys.stderr)
                return 1
        executable = scanner(root)
        command = [str(executable), 'git', str(root), '--redact=100', '--no-banner', '--no-color', '--ignore-gitleaks-allow']
        command += ['--pre-commit', '--staged'] if args.staged else ['--log-opts=--all --full-history']
        environment = dict(os.environ)
        # Ambient overrides must not silently change the installed guard's rules.
        environment.pop('GITLEAKS_CONFIG', None)
        environment.pop('GITLEAKS_CONFIG_TOML', None)
        return subprocess.run(command, env=environment).returncode
    except Exception as error:
        print('Secret check could not complete; commit/check blocked (' + type(error).__name__ + ').', file=sys.stderr)
        return 2
    finally:
        if executable is not None:
            executable.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
