import Foundation

struct DiagnosticBuild: Codable {
    var version: String
    var buildId: String
    var launcherPath: String
}

struct DiagnosticEvent: Codable, Identifiable {
    var id: String
    var sessionId: String?
    var requestId: String?
    var created: Double
    var source: String
    var severity: String
    var method: String
    var tool: String
    var category: String
    var summary: String
    var advice: String
    var code: Int?
    var httpStatus: Int?
    var exceptionType: String?
    var duration: Double
    var upstreamCalls: Int
    var inputBytes: Int
    var clientBytes: Int
}

struct DiagnosticConnection: Codable, Identifiable {
    var id: String
    var client: String
    var started: Double
    var updated: Double
    var closed: Int
    var pid: Int
    var launcherPid: Int
    var launcherPath: String
    var version: String
    var buildId: String
    var `protocol`: String
    var active: Bool
}

struct DiagnosticProcess: Codable, Identifiable {
    var pid: Int
    var launcherPath: String
    var tracked: Bool
    var buildId: String?
    var matchesConfigured: Bool?
    var id: Int { pid }
}

struct DiagnosticsSnapshot: Codable {
    var currentBuild: DiagnosticBuild
    var configuredLauncher: String?
    var connections: [DiagnosticConnection]
    var processes: [DiagnosticProcess]
    var events: [DiagnosticEvent]
    var errorCount: Int
    var warningCount: Int
    var storedEventCount: Int
    var eventLimit: Int
    var displayLimit: Int
    var retentionDays: Int
    var updatedAt: Double
    var warnings: [String]
    var privacy: String
}
