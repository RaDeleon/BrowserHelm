"""Native legacy-settings migration and model switching; no user settings writes."""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


class VisionSettingsTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swiftc'), 'Requires native macOS Swift compiler')
    def test_legacy_configuration_and_provider_profiles_survive_round_trips(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        probe = r'''import Foundation
let old = Data("{\"enabled\":true,\"provider\":\"ollama\",\"endpoint\":\"http://127.0.0.1:11434\",\"model\":\"my-local-model\"}".utf8)
var vision = try JSONDecoder().decode(VisionConfiguration.self, from: old)
precondition(vision.enabled && vision.model == "my-local-model" && vision.minConfidence == 0.9)
vision.selectProvider("typesafe")
precondition(vision.endpoint == "https://api.typesafe.ai/v1" && vision.model == "jev-1.14.0")
vision.minConfidence = 0.95
vision.selectProvider("ollama")
precondition(vision.model == "my-local-model")
vision.selectProvider("openrouter")
precondition(vision.endpoint == "https://openrouter.ai/api/v1")
vision.model = "deepseek/deepseek-v4.1-flash"
vision.selectProvider("lmstudio"); vision.model = "studio-model"
vision.selectProvider("ollama"); precondition(vision.model == "my-local-model")
vision.selectProvider("openrouter"); precondition(vision.model == "deepseek/deepseek-v4.1-flash")
var restored = try JSONDecoder().decode(VisionConfiguration.self, from: JSONEncoder().encode(vision))
restored.selectProvider("lmstudio"); precondition(restored.model == "studio-model")
restored.selectProvider("typesafe")
precondition(restored.model == "jev-1.14.0" && restored.minConfidence == 0.95)
restored.selectProvider("openrouter")
precondition(restored.model == "deepseek/deepseek-v4.1-flash")
precondition(VisionConfiguration().provider == "ollama" && !VisionConfiguration().enabled)
let migrated = try JSONDecoder().decode(VisionConfiguration.self, from: Data("{\"provider\":\"openrouter\"}".utf8))
precondition(migrated.model == "deepseek/deepseek-v4.1-flash" && !migrated.enabled)
let explicitOldCloud = try JSONDecoder().decode(VisionConfiguration.self, from: Data("{\"provider\":\"openrouter\",\"model\":\"qwen/qwen3.8-flash\"}".utf8))
precondition(explicitOldCloud.model == "qwen/qwen3.8-flash")
var configuration = Configuration()
precondition(configuration.providers["typesafe"]?.model == "jev-1.13.0")
configuration.provider = "typesafe"
configuration.vision = restored
configuration.memory.enabled = true
var legacy = try JSONSerialization.jsonObject(with: JSONEncoder().encode(configuration)) as! [String: Any]
legacy.removeValue(forKey: "delegationEnabled")
legacy.removeValue(forKey: "agentTaskMarkers")
let upgraded = try Configuration.decode(JSONSerialization.data(withJSONObject: legacy))
precondition(!upgraded.agentTaskMarkers)
precondition(upgraded.delegationEnabled && upgraded.provider == "typesafe" && upgraded.memory.enabled)
configuration.agentTaskMarkers = true
configuration.delegationEnabled = false
let saved = try Configuration.decode(JSONEncoder().encode(configuration))
precondition(saved.agentTaskMarkers)
precondition(!saved.delegationEnabled && saved.vision.model == configuration.vision.model)
configuration.agentTaskMarkers = false
configuration.delegationEnabled = true
let reenabled = try Configuration.decode(JSONEncoder().encode(configuration))
precondition(reenabled.delegationEnabled && !reenabled.agentTaskMarkers)
print("settings checks passed")
'''
        with tempfile.TemporaryDirectory(prefix='browserhelm-settings-') as directory:
            folder = pathlib.Path(directory)
            main = folder / 'main.swift'; main.write_text(probe)
            binary = folder / 'check'
            subprocess.run(['swiftc', str(root / 'mac-app/Sources/BrowserHelm/Configuration.swift'), str(main), '-o', str(binary)], check=True, capture_output=True, timeout=60)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.stdout.strip(), 'settings checks passed')


if __name__ == '__main__': unittest.main()
