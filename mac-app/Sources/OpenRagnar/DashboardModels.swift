import Foundation
struct Counters: Decodable {
    var requests: Int; var toolRequests: Int; var inputBytes: Int
    var upstreamInputBytes: Int; var upstreamBytes: Int; var clientBytes: Int; var upstreamText: Int; var clientText: Int
    var upstreamCalls: Int; var providerTokens: Int; var providerCalls: Int; var providerUnknown: Int
    var mediaCount: Int; var netTextSaved: Int
}
struct GatewaySession: Decodable, Identifiable {
    var id: String; var client: String; var label: String; var started: Double; var updated: Double
    var closed: Int; var upstreamHash: String?; var compact: Int; var active: Bool
    var requests: Int; var toolRequests: Int; var textBytes: Int; var savedText: Int
    var upstreamCalls: Int; var providerTokens: Int; var providerUnknown: Int
}
struct GatewayRequest: Decodable, Identifiable {
    var id: String; var sessionId: String; var method: String; var tool: String
    var started: Double; var finished: Double; var status: String
    var inputBytes: Int; var upstreamInputBytes: Int; var upstreamBytes: Int; var clientBytes: Int
    var upstreamText: Int; var clientText: Int; var upstreamCalls: Int
    var providerTokens: Int; var providerCalls: Int; var providerUnknown: Int; var mediaCount: Int
    var moves: Int?; var movesStatus: String?
}
struct Benchmark: Decodable {
    var sessionId: String; var claudeTokens: Int?; var neoTokens: Int?; var gatewayTokens: Int?
}
struct ClientConnector: Decodable, Identifiable {
    var name: String; var configured: Bool; var activeSessions: Int; var path: String
    var otherConnectors: [String]?
    var id: String { name }
}
struct NeoWindow: Decodable {
    var browserClawTokenEstimate: Int; var screenshotFirstTokenEstimate: Int
    var rawTokenSavingsEstimate: Int; var humanTimeSavedMs: Int; var sessionCount: Int; var toolCallCount: Int
}
struct NeoStats: Decodable {
    var hasMeasuredStats: Bool; var allTime: NeoWindow; var last30Days: NeoWindow; var last7Days: NeoWindow
}
struct NeoSession: Decodable, Identifiable {
    var id: String; var client: String; var label: String; var viaGateway: Bool
    var started: Double; var moves: Int; var tokens: Int?; var status: String; var errors: Int
}
struct NeoSnapshot: Decodable {
    var available: Bool; var stats: NeoStats?; var sessions: [NeoSession]?; var hasMore: Bool?; var error: String?
}
struct Dashboard: Decodable {
    var diagnostics: DiagnosticsSnapshot?
    var memory: MemorySnapshot?
    var totals: Counters; var sessions: [GatewaySession]; var requests: [GatewayRequest]
    var benchmarks: [Benchmark]; var connectors: [ClientConnector]; var neo: NeoSnapshot
    var retentionDays: Int; var requestLimit: Int; var sessionLimit: Int; var updatedAt: Double
}
struct MemoryExperience: Decodable, Identifiable {
    var id: String; var goal: String; var verified: Bool; var created: Double; var synced: Bool
    var kind: String?; var status: String?; var failureCategory: String?; var test: Bool?
}
struct MemorySnapshot: Decodable {
    var enabled: Bool; var endpoint: String; var collection: String; var connection: String
    var saved: Int; var pending: Int; var tasksWithRecall: Int; var lastRecalled: Int
    var recent: [MemoryExperience]
    var tasksWithReuse: Int?; var reusedSteps: Int?; var reusedTasksVerified: Int?; var providerCallsAvoided: Int?
    var repeatFailureHints: Int?; var toolRequestsSeen: Int?; var toolFailures: Int?; var recallSource: String?
}
func number(_ value: Int) -> String { value.formatted(.number) }
func estimate(_ bytes: Int) -> Int { Int((Double(bytes) / 3).rounded()) }
func timestamp(_ value: Double) -> String { Date(timeIntervalSince1970: value).formatted(date: .abbreviated, time: .shortened) }
