import Foundation
let service = "com.techinsf.openragnar"
let support = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/OpenRagnar")
let settingsURL = support.appendingPathComponent("settings.json")
let providers = ["none", "typesafe", "openrouter", "ollama", "lmstudio", "custom"]
let names = ["none": "Gateway only", "typesafe": "TypeSafe AI / Jev", "openrouter": "OpenRouter", "ollama": "Ollama", "lmstudio": "LM Studio", "custom": "Custom OpenAI-compatible"]
struct Profile: Codable { var endpoint: String; var model: String }
struct MemoryConfiguration: Codable { var enabled = false }
struct VisionConfiguration: Codable {
    var enabled = false
    var provider = "ollama"
    var endpoint = "http://127.0.0.1:11434"
    var model = "qwen3-vl:2b-instruct"
}
struct Configuration: Codable {
    var provider = "none"
    var upstream = "http://127.0.0.1:9010/mcp"
    var compactCatalog = false
    var configVersion = 3
    var maxOutputTokens = 2000
    var memory = MemoryConfiguration()
    var vision = VisionConfiguration()
    var providers: [String: Profile] = [
        "typesafe": Profile(endpoint: "https://api.typesafe.ai/v1", model: "jev-latest"),
        "openrouter": Profile(endpoint: "https://openrouter.ai/api/v1", model: ""),
        "ollama": Profile(endpoint: "http://127.0.0.1:11434/v1", model: ""),
        "lmstudio": Profile(endpoint: "http://127.0.0.1:1234/v1", model: ""),
        "custom": Profile(endpoint: "", model: "")]
    static func load() -> Configuration {
        guard let data = try? Data(contentsOf: settingsURL),
              var root = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return Self() }
        if (root["configVersion"] as? Int ?? 0) < 3 { root["compactCatalog"] = false; root["configVersion"] = 3 }
        if root["memory"] == nil { root["memory"] = ["enabled": false] }
        if root["vision"] == nil {
            root["vision"] = ["enabled": false, "provider": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "qwen3-vl:2b-instruct"]
        }
        guard let updated = try? JSONSerialization.data(withJSONObject: root),
              let config = try? JSONDecoder().decode(Self.self, from: updated) else { return Self() }
        return config
    }
    func save() throws {
        try FileManager.default.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(self).write(to: settingsURL, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: settingsURL.path)
    }
}
