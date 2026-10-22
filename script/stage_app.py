"""Stage a relocatable local macOS app with a standalone Python stdlib runtime."""
import os
import pathlib
import plistlib
import shutil
import subprocess
import sys
import tempfile
from release_support import sign, signing_identity, macho_files, verify_distribution_contents
from release_metadata import build_metadata
root = pathlib.Path(__file__).resolve().parent.parent
version = build_metadata()
identity = signing_identity(os.environ.get('BROWSERHELM_SIGNING_IDENTITY', '-'))
destination = pathlib.Path(os.environ.get('BROWSERHELM_APP_OUTPUT', str(root / 'dist/BrowserHelm.app'))).expanduser().resolve()
work = pathlib.Path(tempfile.mkdtemp(prefix='browserhelm-stage-', dir='/private/tmp'))
app = work / 'BrowserHelm.app'
contents = app / 'Contents'
macos = contents / 'MacOS'; resources = contents / 'Resources'
macos.mkdir(parents=True); resources.mkdir()
binary = root / 'mac-app/.build/release/BrowserHelm'
shutil.copy2(binary, macos / 'BrowserHelm')
runtime_source = pathlib.Path(os.environ.get('BROWSERHELM_RUNTIME_SOURCE', str(root / '.runtime/python'))).expanduser().resolve()
if not (runtime_source / 'bin/python3.12').is_file() and 'BROWSERHELM_RUNTIME_SOURCE' not in os.environ:
    # Compatibility for the original developer workstation; not a build requirement.
    runtime_source = pathlib.Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python'
if not (runtime_source / 'bin/python3.12').is_file():
    raise SystemExit('Relocatable Python 3.12 runtime missing. Extract an Apple Silicon python-build-standalone install_only archive into .runtime/python, or set BROWSERHELM_RUNTIME_SOURCE. See README.md.')
if not (runtime_source / 'lib/python3.12/LICENSE.txt').is_file():
    raise SystemExit('Runtime license notices missing. Use a complete python-build-standalone installation.')
runtime = resources / 'runtime'
(runtime / 'bin').mkdir(parents=True); (runtime / 'lib').mkdir()
shutil.copy2(runtime_source / 'bin/python3.12', runtime / 'bin/python3.12')
shutil.copytree(runtime_source / 'lib/python3.12', runtime / 'lib/python3.12', ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip'))
# Python-build-standalone's executable and extension modules are relocatable.
# Keep its license and compiled dependency license notices from LICENSE.txt.
engine = resources / 'engine'; engine.mkdir()
for name in ['gateway.py', 'decision.py', 'vision.py', 'executor.py', 'browserhelm.py', 'openragnar.py', 'launch.py', 'metrics.py', 'task_metrics.py', 'sqlite_support.py', 'client_setup.py', 'migration.py', 'experience.py', 'diagnostics.py', 'version.py']:
    shutil.copy2(root / 'neo-personal' / name, engine / name)
shutil.copy2(root / 'neo-personal/vision-models.json', engine / 'vision-models.json')
shutil.copy2(root / 'README-BrowserHelm.md', resources / 'README.md')
for name in ('LICENSE', 'NOTICE'):
    shutil.copy2(root / name, resources / name)
for icon in ('AppIcon.icns', 'AppIcon.png'):
    shutil.copy2(root / 'mac-app/Artwork' / icon, resources / icon)
plist = dict(CFBundleExecutable='BrowserHelm', CFBundleIdentifier='com.techinsf.browserhelm', CFBundleName='BrowserHelm', CFBundleDisplayName='BrowserHelm', CFBundleIconFile='AppIcon', CFBundlePackageType='APPL', CFBundleShortVersionString=version['VERSION'], CFBundleVersion=version['BUILD'], LSMinimumSystemVersion='14.0', NSPrincipalClass='NSApplication', NSHighResolutionCapable=True)
with (contents / 'Info.plist').open('wb') as file: plistlib.dump(plist, file)
verify_distribution_contents(app)
subprocess.run(['/usr/bin/xattr', '-cr', str(app)], check=True)
# Sign bundled executables/libraries before the app. Public builds use the same
# Developer ID identity, Hardened Runtime and secure timestamps throughout.
for path in macho_files(runtime):
    sign(path, identity, executable=True)
sign(app, identity, executable=True)
subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
destination.parent.mkdir(parents=True, exist_ok=True)
if destination.exists(): shutil.rmtree(destination)
subprocess.run(['/usr/bin/ditto', '--norsrc', '--noextattr', str(app), str(destination)], check=True)
subprocess.run(['/usr/bin/xattr', '-d', 'com.apple.FinderInfo', str(destination)], capture_output=True)
# Verify a clean copy of the destination: synced folders can immediately add
# FinderInfo to a bundle, although its signed contents are unchanged.
verification = work / 'verification/BrowserHelm.app'
subprocess.run(['/usr/bin/ditto', '--norsrc', '--noextattr', str(destination), str(verification)], check=True)
subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(verification)], check=True)
shutil.rmtree(work)
print(destination)
