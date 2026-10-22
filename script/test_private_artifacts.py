"""Public-repository exclusions must agree with the commit/packaging guard."""
import pathlib
import subprocess
import unittest
from artifact_policy import is_private_artifact

ROOT = pathlib.Path(__file__).resolve().parent.parent

class PrivateArtifactTests(unittest.TestCase):
    def test_sensitive_paths_are_ignored_and_rejected_by_guard(self):
        paths = ['generated_images/capture.png', 'private/client-notes.md',
                 'secrets/api.txt', 'credentials/account.json', 'backups/state.json',
                 '.agents/session.md', '.aws/credentials', '.ssh/config',
                 '.azure/account.json', '.gcloud/token.json', '.config/gcloud/config.json',
                 '.auth/session.json', 'browser-profiles/Default/Cookies',
                 'user-data/Default/History', 'login.keychain-db', 'signing.p8',
                 'app.mobileprovision', 'id_rsa', 'id_ed25519', 'credentials.json',
                 'service-account-prod.json', 'client_secret_app.json', 'cookies.json',
                 'cookies.txt', 'storage-state-prod.json', 'storageState.json', '.env.production']
        result = subprocess.run(['git','check-ignore','--no-index','--stdin'],
                                cwd=ROOT,input='\n'.join(paths)+'\n',text=True,capture_output=True,check=True)
        self.assertEqual(set(result.stdout.splitlines()),set(paths))
        for path in paths:
            with self.subTest(path=path): self.assertTrue(is_private_artifact(path))

    def test_public_source_and_sanitized_examples_remain_allowed(self):
        for path in ['.env.example', 'neo-personal/vision-models.json',
                     'neo-personal/test_metrics.py', 'docs/benchmarks.md',
                     'mac-app/Artwork/AppIcon.png']:
            with self.subTest(path=path): self.assertFalse(is_private_artifact(path))
