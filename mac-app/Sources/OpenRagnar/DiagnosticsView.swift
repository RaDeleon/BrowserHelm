import SwiftUI
import UniformTypeIdentifiers

struct DiagnosticReport: FileDocument {
    static var readableContentTypes: [UTType] { [.json] }
    var data: Data
    init(data: Data = Data()) { self.data = data }
    init(configuration: ReadConfiguration) throws { data = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

struct DiagnosticsView: View {
    @ObservedObject var store: Store
    @State private var query = ""
    @State private var severity = "problems"
    @State private var session = "all"
    @State private var selected: String?
    @State private var export = false
    @State private var report = DiagnosticReport()

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Diagnostics").font(.title2.bold())
                    Text("Find the failure, connection and next step.").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Check Neo connection", systemImage: "stethoscope") { store.checkDiagnosticsConnection() }.disabled(store.busy)
                Button("Export report", systemImage: "square.and.arrow.up") { exportReport() }.disabled(store.dashboard?.diagnostics == nil)
            }
            if let data = store.dashboard?.diagnostics {
                HStack(spacing: 12) {
                    MetricCard(title: "Errors", value: number(data.errorCount), note: "In displayed records", symbol: "exclamationmark.triangle", tint: .orange)
                    MetricCard(title: "Warnings", value: number(data.warningCount), note: "Includes expected handoffs", symbol: "exclamationmark.circle")
                    MetricCard(title: "MCP processes", value: number(data.processes.count), note: "\(data.processes.filter { !$0.tracked }.count) without new diagnostics", symbol: "point.3.connected.trianglepath.dotted")
                }
                ForEach(data.warnings, id: \.self) { warning in
                    Label(warning, systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.orange).textSelection(.enabled)
                }
                DisclosureGroup("App builds & connections") { DiagnosticConnections(data: data) }
                HStack(spacing: 12) {
                    TextField("Search tool, category, code or correlation ID", text: $query).textFieldStyle(.roundedBorder)
                    Picker("Severity", selection: $severity) {
                        Text("Errors & warnings").tag("problems"); Text("Errors").tag("error"); Text("All events").tag("all")
                    }.labelsHidden().frame(width: 160)
                    Picker("Connection", selection: $session) {
                        Text("All connections").tag("all")
                        ForEach(data.connections) { connection in
                            Text("\(connection.client) · \(timestamp(connection.started)) · \(connection.id.prefix(6))").tag(connection.id)
                        }
                    }.labelsHidden().frame(width: 235)
                }
                let rows = filtered(data)
                if rows.isEmpty {
                    ContentUnavailableView("No matching events", systemImage: "checkmark.circle", description: Text("New MCP connections record diagnostics. Existing clients need a restart after their active tasks finish."))
                        .frame(maxHeight: .infinity)
                } else {
                    Table(rows, selection: $selected) {
                        TableColumn("Time") { event in Text(timestamp(event.created)).font(.caption) }.width(min: 120, ideal: 150)
                        TableColumn("Level") { event in Text(event.severity).foregroundStyle(event.severity == "error" ? .orange : .secondary) }.width(65)
                        TableColumn("Tool / category") { event in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(event.tool == "unknown" ? event.method : event.tool).font(.body.monospaced())
                                Text(event.category.replacingOccurrences(of: "_", with: " ")).font(.caption).foregroundStyle(.secondary)
                            }
                        }.width(min: 140, ideal: 190)
                        TableColumn("Code") { event in Text(code(event)).font(.caption.monospaced()) }.width(95)
                        TableColumn("Source") { event in Text(event.source).font(.caption) }.width(min: 100, ideal: 120)
                        TableColumn("Correlation") { event in Text(String((event.requestId ?? event.id).prefix(10))).font(.caption.monospaced()) }.width(100)
                    }.frame(minHeight: 130)
                    if let event = rows.first(where: { $0.id == selected }) {
                        DiagnosticDetail(event: event)
                    } else {
                        Text("Select an event to see its explanation and suggested next step.").font(.caption).foregroundStyle(.secondary)
                    }
                }
                Text("\(rows.count) matching / \(data.events.count) displayed events · New diagnostics retain \(data.retentionDays) days, up to \(number(data.eventLimit)) events. Older counter and Claude log entries may describe the same failure.")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                ContentUnavailableView("Diagnostics not loaded", systemImage: "stethoscope", description: Text("Refresh to load local diagnostics from this build."))
            }
        }.padding(24).onAppear { query = store.diagnosticQuery }
            .fileExporter(isPresented: $export, document: report, contentType: .json, defaultFilename: "OpenRagnar-diagnostics") { result in
                switch result {
                case .success: store.status = "Diagnostics report saved locally. Review it before sharing; it contains app paths, client names and timestamps."
                case .failure: store.status = "Diagnostics report could not be saved."
                }
            }
    }

    private func filtered(_ data: DiagnosticsSnapshot) -> [DiagnosticEvent] {
        data.events.filter { event in
            (severity == "all" || (severity == "problems" ? event.severity != "info" : event.severity == severity)) &&
            (session == "all" || event.sessionId == session) &&
            (query.isEmpty || [event.tool, event.category, event.summary, event.source, event.requestId ?? event.id, code(event)].joined(separator: " ").localizedCaseInsensitiveContains(query))
        }
    }
    private func code(_ event: DiagnosticEvent) -> String {
        [event.code.map { "MCP \($0)" }, event.httpStatus.map { "HTTP \($0)" }].compactMap { $0 }.joined(separator: " / ")
    }
    private func exportReport() {
        guard let data = store.dashboard?.diagnostics else { return }
        do {
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            report = DiagnosticReport(data: try encoder.encode(data)); export = true
        } catch { store.status = "Diagnostics report could not be prepared." }
    }
}

private struct DiagnosticDetail: View {
    var event: DiagnosticEvent
    var body: some View {
        RagnarPanel {
            VStack(alignment: .leading, spacing: 8) {
                Text(event.summary).font(.headline)
                Text(event.advice).font(.callout)
                Text("Correlation: \(event.requestId ?? event.id) · \(event.source)").font(.caption.monospaced())
                if let type = event.exceptionType { Text("Exception: \(type)").font(.caption.monospaced()) }
                if event.source == "gateway" {
                    Text("\(String(format: "%.2f", event.duration)) s · \(event.upstreamCalls) browser \(event.upstreamCalls == 1 ? "attempt" : "attempts") · \(number(event.inputBytes)) input bytes · \(number(event.clientBytes)) reply bytes").font(.caption).foregroundStyle(.secondary)
                }
            }.textSelection(.enabled)
        }
    }
}

private struct DiagnosticConnections: View {
    var data: DiagnosticsSnapshot
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("This app: \(data.currentBuild.version) · build \(data.currentBuild.buildId)").font(.caption.monospaced())
                Text(data.currentBuild.launcherPath).font(.caption.monospaced())
                if let path = data.configuredLauncher { Text("Claude configured launcher: \(path)").font(.caption.monospaced()) }
                ForEach(data.processes) { process in
                    Label("PID \(process.pid) · \(process.tracked ? "Diagnostics connected" : "Older connection, details unavailable") · \(process.launcherPath)", systemImage: process.matchesConfigured == false ? "exclamationmark.triangle" : "network").font(.caption)
                }
                ForEach(data.connections.prefix(12)) { connection in
                    Text("\(connection.active ? "Live" : "Ended") · \(connection.client) · \(connection.version) / \(connection.buildId) · MCP \(connection.protocol) · \(connection.id.prefix(8))").font(.caption.monospaced())
                }
                Text(data.privacy).font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
        }.frame(maxHeight: 170)
    }
}
