"""Stage a relocatable local macOS app with a standalone Python stdlib runtime."""
import os
import pathlib
import plistlib
import shutil
import subprocess
import sys
import tempfile
from release_support import sign, signing_identity, macho_files
root = pathlib.Path(__file__).resolve().parent.parent
identity = signing_identity(os.environ.get('OPENRAGNAR_SIGNING_IDENTITY', '-'))
destination = pathlib.Path(os.environ.get('OPENRAGNAR_APP_OUTPUT', str(root / 'dist/OpenRagnar.app'))).expanduser().resolve()
work = pathlib.Path(tempfile.mkdtemp(prefix='openragnar-stage-', dir='/private/tmp'))
app = work / 'OpenRagnar.app'
contents = app / 'Contents'
macos = contents / 'MacOS'; resources = contents / 'Resources'
macos.mkdir(parents=True); resources.mkdir()
binary = root / 'mac-app/.build/release/OpenRagnar'
shutil.copy2(binary, macos / 'OpenRagnar')
runtime_source = pathlib.Path(os.environ.get('OPENRAGNAR_RUNTIME_SOURCE', str(root / '.runtime/python'))).expanduser().resolve()
if not (runtime_source / 'bin/python3.12').is_file() and 'OPENRAGNAR_RUNTIME_SOURCE' not in os.environ:
    # Compatibility for the original developer workstation; not a build requirement.
    runtime_source = pathlib.Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python'
if not (runtime_source / 'bin/python3.12').is_file():
    raise SystemExit('Relocatable Python 3.12 runtime missing. Extract an Apple Silicon python-build-standalone install_only archive into .runtime/python, or set OPENRAGNAR_RUNTIME_SOURCE. See README.md.')
if not (runtime_source / 'lib/python3.12/LICENSE.txt').is_file():
    raise SystemExit('Runtime license notices missing. Use a complete python-build-standalone installation.')
runtime = resources / 'runtime'
(runtime / 'bin').mkdir(parents=True); (runtime / 'lib').mkdir()
shutil.copy2(runtime_source / 'bin/python3.12', runtime / 'bin/python3.12')
shutil.copytree(runtime_source / 'lib/python3.12', runtime / 'lib/python3.12', ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip'))
# Python-build-standalone's executable and extension modules are relocatable.
# Keep its license and compiled dependency license notices from LICENSE.txt.
engine = resources / 'engine'; engine.mkdir()
for name in ['gateway.py', 'decision.py', 'openragnar.py', 'launch.py', 'metrics.py', 'experience.py']:
    shutil.copy2(root / 'neo-personal' / name, engine / name)
shutil.copy2(root / 'README-OpenRagnar.md', resources / 'README.md')
for name in ('LICENSE', 'NOTICE'):
    shutil.copy2(root / name, resources / name)
plist = dict(CFBundleExecutable='OpenRagnar', CFBundleIdentifier='com.techinsf.openragnar', CFBundleName='OpenRagnar', CFBundleDisplayName='OpenRagnar', CFBundlePackageType='APPL', CFBundleShortVersionString='0.4.0', CFBundleVersion='5', LSMinimumSystemVersion='14.0', NSPrincipalClass='NSApplication', NSHighResolutionCapable=True)
with (contents / 'Info.plist').open('wb') as file: plistlib.dump(plist, file)
subprocess.run(['/usr/bin/xattr', '-cr', str(app)], check=True)
# Sign bundled executables/libraries before the app. Public builds use the same
# Developer ID identity, Hardened Runtime and secure timestamps throughout.
for path in macho_files(runtime):
    sign(path, identity, executable=True)
sign(app, identity, executable=True)
destination.parent.mkdir(parents=True, exist_ok=True)
if destination.exists(): shutil.rmtree(destination)
subprocess.run(['/usr/bin/ditto', '--norsrc', '--noextattr', str(app), str(destination)], check=True)
subprocess.run(['/usr/bin/xattr', '-d', 'com.apple.FinderInfo', str(destination)], capture_output=True)
subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(destination)], check=True)
shutil.rmtree(work)
print(destination)
