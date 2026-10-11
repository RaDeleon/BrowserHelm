import Foundation
import Security
struct AppError: LocalizedError { var text: String; var errorDescription: String? { text } }
enum Keys {
    static func query(_ account: String) -> [String: Any] { [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account] }
    static func has(_ account: String) -> Bool {
        var q = query(account); q[kSecReturnAttributes as String] = true
        return SecItemCopyMatching(q as CFDictionary, nil) == errSecSuccess
    }
    static func read(_ account: String) throws -> String {
        var q = query(account); q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?; let status = SecItemCopyMatching(q as CFDictionary, &item)
        if status == errSecItemNotFound { return "" }
        guard status == errSecSuccess, let data = item as? Data, let key = String(data: data, encoding: .utf8) else { throw AppError(text: "Keychain access failed (\(status)). Allow OpenRagnar to access its saved key.") }
        return key
    }
    static func save(_ key: String, account: String) throws {
        let data = Data(key.utf8); let q = query(account)
        var status = SecItemUpdate(q as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecItemNotFound {
            var add = q; add[kSecValueData as String] = data
            status = SecItemAdd(add as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw AppError(text: "Could not save API key to Keychain (\(status)).") }
    }
    static func remove(_ account: String) throws {
        let status = SecItemDelete(query(account) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw AppError(text: "Could not remove key (\(status)).") }
    }
}
enum Runner {
    static func process(_ mode: String, extra: [String] = []) throws -> Process {
        let resources = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources")
        let python = resources.appendingPathComponent("runtime/bin/python3.12")
        guard FileManager.default.isExecutableFile(atPath: python.path) else { throw AppError(text: "Bundled Python runtime is missing. Reinstall OpenRagnar from its DMG.") }
        let config = Configuration.load()
        let process = Process(); process.executableURL = python
        process.arguments = ["-I", "-B", resources.appendingPathComponent("engine/launch.py").path, "--settings", settingsURL.path, "--output-dir", support.appendingPathComponent("outputs").path]
        if mode != "--mcp" { process.arguments!.append(mode) }
        var environment = ProcessInfo.processInfo.environment
        for key in ["PYTHONHOME", "PYTHONPATH", "OPENRAGNAR_API_KEY", "OPENRAGNAR_VISION_API_KEY"] { environment.removeValue(forKey: key) }
        if config.provider != "none" && mode == "--test-provider" { environment["OPENRAGNAR_API_KEY"] = try Keys.read(config.provider) }
        if config.vision.provider == "openrouter" && mode == "--test-vision" { environment["OPENRAGNAR_VISION_API_KEY"] = try Keys.read("openrouter") }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        // Browser tools do not need a decision-provider credential. Fetch lazily via a private child pipe.
        if mode == "--mcp" { environment["OPENRAGNAR_KEY_HELPER"] = Bundle.main.executableURL!.path }
        else { environment.removeValue(forKey: "OPENRAGNAR_KEY_HELPER") }
        process.arguments! += extra
        process.environment = environment
        return process
    }
    static func test(_ mode: String, extra: [String] = []) throws -> String {
        let process = try self.process(mode, extra: extra)
        let output = Pipe(); let errors = Pipe()
        process.standardInput = FileHandle.nullDevice; process.standardOutput = output; process.standardError = errors
        // Drain both streams concurrently to avoid pipe deadlocks.
        var result = Data(), error = Data()
        let group = DispatchGroup()
        try process.run()
        group.enter(); DispatchQueue.global().async { result = output.fileHandleForReading.readDataToEndOfFile(); group.leave() }
        group.enter(); DispatchQueue.global().async { error = errors.fileHandleForReading.readDataToEndOfFile(); group.leave() }
        process.waitUntilExit(); group.wait()
        guard process.terminationStatus == 0 else { throw AppError(text: String(data: error, encoding: .utf8) ?? "Connection test failed") }
        return String(data: result, encoding: .utf8) ?? "Test completed"
    }
}
