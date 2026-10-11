import Foundation
let service = "com.techinsf.openragnar"
let support = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/OpenRagnar")
let settingsURL = support.appendingPathComponent("settings.json")
let providers = ["none", "typesafe", "openrouter", "ollama", "lmstudio", "custom"]
let names = ["none": "Gateway only", "typesafe": "TypeSafe AI / Jev", "openrouter": "OpenRouter", "ollama": "Ollama", "lmstudio": "LM Studio", "custom": "Custom OpenAI-compatible"]
struct Profile: Codable { var endpoint: String; var model: String }
struct MemoryConfiguration: Codable { var enabled = false }
struct VisionPreset: Codable, Identifiable {
    let id: String
    let name: String
    let purpose: String
    let detail: String
    let url: URL
    static var recommendations: [VisionPreset] {
        let path = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/engine/vision-models.json")
        guard let data = try? Data(contentsOf: path), let models = try? JSONDecoder().decode([VisionPreset].self, from: data) else { return [] }
        return models
    }
}
struct VisionConfiguration: Codable {
    var enabled = false
    var provider = "ollama"
    var endpoint = "http://127.0.0.1:11434"
    var model = "qwen3-vl:2b-instruct"
    var profiles: [String: Profile] = [:]
    static let defaults: [String: Profile] = [
        "ollama": Profile(endpoint: "http://127.0.0.1:11434", model: "qwen3-vl:2b-instruct"),
        "lmstudio": Profile(endpoint: "http://127.0.0.1:1234/v1", model: ""),
        "openrouter": Profile(endpoint: "https://openrouter.ai/api/v1", model: "qwen/qwen3.8-flash")]
    init() {}
    mutating func selectProvider(_ next: String) {
        guard let fallback = Self.defaults[next] else { return }
        profiles[provider] = Profile(endpoint: endpoint, model: model)
        let profile = profiles[next] ?? fallback
        provider = next; endpoint = profile.endpoint; model = profile.model
    }
    enum CodingKeys: String, CodingKey { case enabled, provider, endpoint, model, profiles }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        enabled = try values.decodeIfPresent(Bool.self, forKey: .enabled) ?? false
        provider = try values.decodeIfPresent(String.self, forKey: .provider) ?? "ollama"
        let fallback = Self.defaults[provider] ?? Self.defaults["ollama"]!
        endpoint = try values.decodeIfPresent(String.self, forKey: .endpoint) ?? fallback.endpoint
        model = try values.decodeIfPresent(String.self, forKey: .model) ?? fallback.model
        profiles = try values.decodeIfPresent([String: Profile].self, forKey: .profiles) ?? [:]
        profiles[provider] = Profile(endpoint: endpoint, model: model)
    }
}
struct Configuration: Codable {
    var provider = "none"
    var upstream = "http://127.0.0.1:9010/mcp"
    var compactCatalog = false
    var delegationEnabled = true
    var agentTaskMarkers = false
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
              let config = try? decode(data) else { return Self() }
        return config
    }
    static func decode(_ data: Data) throws -> Configuration {
        guard var root = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw CocoaError(.coderReadCorrupt)
        }
        if (root["configVersion"] as? Int ?? 0) < 3 { root["compactCatalog"] = false; root["configVersion"] = 3 }
        if root["delegationEnabled"] == nil { root["delegationEnabled"] = true }
        if root["agentTaskMarkers"] == nil { root["agentTaskMarkers"] = false }
        if root["memory"] == nil { root["memory"] = ["enabled": false] }
        if root["vision"] == nil {
            root["vision"] = ["enabled": false, "provider": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "qwen3-vl:2b-instruct"]
        }
        return try JSONDecoder().decode(Self.self, from: JSONSerialization.data(withJSONObject: root))
    }
    func save() throws {
        try FileManager.default.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(self).write(to: settingsURL, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: settingsURL.path)
    }
}
