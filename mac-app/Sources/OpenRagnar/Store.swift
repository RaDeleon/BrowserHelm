import SwiftUI
import AppKit
import OSLog
@MainActor final class Store: ObservableObject {
    @Published var config = Configuration.load()
    @Published var key = ""
    @Published var storedKey = false
    @Published var visionKey = ""
    @Published var storedVisionKey = false
    @Published var status = "Full read/write browser tools are ready. Reconnect your MCP client to record new sessions."
    @Published var busy = false
    @Published var selectedTab = 0
    @Published var diagnosticQuery = ""
    @Published var dashboard: Dashboard?
    @Published var loadingDashboard = false
    @Published var dashboardError = ""
    private let logger = Logger(subsystem: service, category: "dashboard")
    private var timer: Timer?
    init() {
        refreshKey()
        refreshVisionKey()
        refreshDashboard()
        timer = Timer.scheduledTimer(withTimeInterval: 6, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshDashboard() }
        }
        logger.info("OpenRagnar dashboard opened")
    }
    func refreshDashboard() {
        guard !loadingDashboard else { return }
        loadingDashboard = true
        DispatchQueue.global().async {
            do {
                let json = try Runner.test("--dashboard")
                let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
                let data = try decoder.decode(Dashboard.self, from: Data(json.utf8))
                DispatchQueue.main.async { self.dashboard = data; self.dashboardError = ""; self.loadingDashboard = false }
            } catch {
                DispatchQueue.main.async { self.dashboardError = error.localizedDescription; self.loadingDashboard = false }
            }
        }
    }
    func saveBenchmark(session: String, claude: String, neo: String, gateway: String) {
        do {
            var value: [String: Any] = ["sessionId": session]
            for (key, text) in [("claudeTokens",claude),("neoTokens",neo),("gatewayTokens",gateway)] {
                if !text.isEmpty {
                    guard let n = Int(text), n >= 0, n <= 1_000_000_000_000 else { throw AppError(text: "Enter nonnegative whole token totals, or leave a value blank.") }
                    value[key] = n
                }
            }
            let json = String(data: try JSONSerialization.data(withJSONObject: value), encoding: .utf8)!
            busy = true
            DispatchQueue.global().async {
                let message: String
                do { _ = try Runner.test("--benchmark", extra: [json]); message = "Matched benchmark saved. These totals were entered by you." }
                catch { message = error.localizedDescription }
                DispatchQueue.main.async { self.status = message; self.busy = false; self.refreshDashboard() }
            }
        } catch { status = error.localizedDescription }
    }
    func taskCommand(_ value: [String: Any]) {
        guard !busy else { return }
        do {
            let raw = String(data: try JSONSerialization.data(withJSONObject: value), encoding: .utf8)!
            busy = true
            DispatchQueue.global().async {
                let message: String
                do { _ = try Runner.test("--task", extra: [raw]); message = "Task record saved." }
                catch { message = error.localizedDescription }
                DispatchQueue.main.async { self.status = message; self.busy = false; self.refreshDashboard() }
            }
        } catch { status = error.localizedDescription }
    }
    func refreshKey() { storedKey = Keys.has(config.provider); key = "" }
    func refreshVisionKey() { storedVisionKey = Keys.has("openrouter"); visionKey = "" }
    func selectVisionProvider(_ provider: String) {
        config.vision.selectProvider(provider)
        // Keep a typed key when switching providers before saving.
        storedVisionKey = Keys.has("openrouter")
    }
    func checkDiagnosticsConnection() {
        guard !busy else { return }
        busy = true; status = "Checking a fresh Neo connection without changing browser tabs…"
        DispatchQueue.global().async {
            let message: String
            do { _ = try Runner.test("--test-browser"); message = "A fresh Neo connection passed MCP negotiation and tool discovery. Existing client connections may still need a restart." }
            catch { message = "Neo connection check failed. See Diagnostics for the recorded error." }
            DispatchQueue.main.async { self.status = message; self.busy = false; self.refreshDashboard() }
        }
    }
    @discardableResult func save() -> Bool {
        do {
            if config.provider == "openrouter" && !key.isEmpty && !visionKey.isEmpty && key.trimmingCharacters(in: .whitespacesAndNewlines) != visionKey.trimmingCharacters(in: .whitespacesAndNewlines) {
                throw AppError(text: "Decision and vision share the saved OpenRouter key. Enter the same key in both fields, or fill only one.")
            }
            if config.provider != "none" && !key.isEmpty { try Keys.save(key.trimmingCharacters(in: .whitespacesAndNewlines), account: config.provider) }
            if !visionKey.isEmpty { try Keys.save(visionKey.trimmingCharacters(in: .whitespacesAndNewlines), account: "openrouter") }
            config.vision.profiles[config.vision.provider] = Profile(endpoint: config.vision.endpoint, model: config.vision.model)
            try config.save(); refreshKey(); refreshVisionKey(); logger.info("Gateway settings saved")
            status = "Settings saved. Delegation off blocks new delegated requests immediately. Reconnect after changing delegation or task markers, first enabling vision or changing the decision provider."
            return true
        } catch { status = error.localizedDescription; return false }
    }
    func removeKey() { do { try Keys.remove(config.provider); refreshKey(); refreshVisionKey(); status = "API key removed." } catch { status = error.localizedDescription } }
    func removeVisionKey() { do { try Keys.remove("openrouter"); refreshVisionKey(); refreshKey(); status = "Shared OpenRouter key removed." } catch { status = error.localizedDescription } }
    func test(_ mode: String) {
        guard save() else { return }; busy = true; status = "Checking connection…"
        DispatchQueue.global().async {
            let result: String
            do { result = try Runner.test(mode) } catch { result = error.localizedDescription }
            DispatchQueue.main.async { self.status = result; self.busy = false; self.refreshDashboard() }
        }
    }
    func profileBinding(_ field: WritableKeyPath<Profile, String>) -> Binding<String> {
        Binding(get: { self.config.providers[self.config.provider]?[keyPath: field] ?? "" }, set: { new in
            var profile = self.config.providers[self.config.provider] ?? Profile(endpoint: "", model: "")
            profile[keyPath: field] = new; self.config.providers[self.config.provider] = profile
        })
    }
    var mcpEntry: [String: Any] { ["command": Bundle.main.executableURL!.path, "args": ["--mcp"]] }
    func copyCodex() {
        let path = Bundle.main.executableURL!.path
        // JSON strings share TOML basic-string escaping for file paths.
        let quoted = String(data: try! JSONSerialization.data(withJSONObject: [path]), encoding: .utf8)!
        let command = String(quoted.dropFirst().dropLast())
        let config = "[mcp_servers.openragnar]\ncommand = \(command)\nargs = [\"--mcp\"]\n"
        NSPasteboard.general.clearContents(); NSPasteboard.general.setString(config, forType: .string)
        status = "Codex MCP entry copied. Merge it into ~/.codex/config.toml, then restart Codex to load the tools."
    }
    func connectCodex() {
        guard !busy else { return }
        let command = Bundle.main.executableURL!.path
        busy = true; status = "Adding OpenRagnar to Codex…"
        DispatchQueue.global().async {
            let result: String
            do { result = try Runner.test("--connect-codex", extra: [command]) }
            catch { result = error.localizedDescription }
            DispatchQueue.main.async {
                self.busy = false; self.refreshDashboard(); self.status = result
            }
        }
    }
    func copyMCP() {
        do { let data = try JSONSerialization.data(withJSONObject: ["mcpServers": ["openragnar": mcpEntry]], options: [.prettyPrinted, .sortedKeys]); NSPasteboard.general.clearContents(); NSPasteboard.general.setString(String(data: data, encoding: .utf8)!, forType: .string); status = "MCP configuration copied. Merge the openragnar entry into your client's configuration." } catch { status = error.localizedDescription }
    }
    func connectClaude() {
        do {
            let path = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Claude/claude_desktop_config.json")
            try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
            let existing = try? Data(contentsOf: path)
            var root: [String: Any] = [:]
            if let data = existing {
                guard let parsed = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw AppError(text: "Claude configuration is not an object. No changes made.") }; root = parsed
            }
            guard root["mcpServers"] == nil || root["mcpServers"] is [String: Any] else { throw AppError(text: "Unexpected mcpServers format. No changes made.") }
            var servers = root["mcpServers"] as? [String: Any] ?? [:]
            if let old = servers["openragnar"] as? [String: Any], let command = old["command"] as? String, !command.hasSuffix("/OpenRagnar.app/Contents/MacOS/OpenRagnar") { throw AppError(text: "Another openragnar entry already exists. Use Copy MCP config to review it.") }
            servers["openragnar"] = mcpEntry; root["mcpServers"] = servers
            let updated = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
            if let old = existing {
                guard try Data(contentsOf: path) == old else { throw AppError(text: "Claude configuration changed. Try again.") }
                let backup = path.appendingPathExtension("openragnar-\(Int(Date().timeIntervalSince1970)).bak")
                try old.write(to: backup, options: .withoutOverwriting)
                try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: backup.path)
            }
            try updated.write(to: path, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path.path)
            logger.info("Claude Desktop MCP configuration updated")
            refreshDashboard()
            status = "OpenRagnar added to Claude Desktop. Existing MCP entries preserved. Quit and reopen Claude Desktop, then enable OpenRagnar's tools."
        } catch { status = error.localizedDescription }
    }
}
