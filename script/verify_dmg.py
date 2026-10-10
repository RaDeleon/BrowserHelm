"""Verify a read-only mounted DMG and relocated CLI/runtime connection."""
import json
import pathlib
import subprocess
import tempfile
root=pathlib.Path(__file__).resolve().parent.parent
dmg=root/'dist/OpenRagnar-0.4.0-arm64.dmg'
with tempfile.TemporaryDirectory(prefix='openragnar-mount-',dir='/private/tmp') as mount:
    subprocess.run(['/usr/bin/hdiutil','attach','-readonly','-nobrowse','-quiet','-mountpoint',mount,str(dmg)],check=True)
    try:
        app=pathlib.Path(mount)/'OpenRagnar.app'
        subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
        target=app/'Contents/MacOS/OpenRagnar'
        result=subprocess.run([str(target),'--test-browser'],capture_output=True,text=True,timeout=40,check=True)
        output=json.loads(result.stdout)
        assert output['connected'] and output['tools']>=26
        runtime=app/'Contents/Resources/runtime/bin/python3.12'
        result=subprocess.run([str(runtime),'-I','-B','-c','import ssl,urllib.request;print(urllib.request.urlopen("https://docs.typesafe.ai",timeout=20).status)'],capture_output=True,text=True,timeout=30,check=True)
        assert result.stdout.strip()=='200'
        assert (pathlib.Path(mount)/'Applications').is_symlink()
        subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
        report={'dmg':str(dmg),'mountedReadOnly':True,'signatureVerifiedBeforeAndAfterLaunch':True,'relocatedBundledRuntimeHTTPS':True,'relocatedMCPBrowserConnection':output,'signing':'Ad-hoc, not notarized','architecture':'arm64'}
        (root/'dist/verification.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        subprocess.run(['/usr/bin/hdiutil','detach','-quiet',mount],check=True)
