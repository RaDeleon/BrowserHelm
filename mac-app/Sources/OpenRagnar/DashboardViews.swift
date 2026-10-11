import SwiftUI
import AppKit

struct ConnectorsView: View {
    @ObservedObject var store: Store
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("MCP connectors").font(.title2.bold())
                Text("Your client apps connect to OpenRagnar over MCP. OpenRagnar forwards browser work to your running Neo instance.").foregroundStyle(.secondary)
                GroupBox("OpenViking · experience memory") {
                    HStack {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(store.dashboard?.memory?.endpoint ?? "Existing OpenViking connection")
                            Text(store.config.memory.enabled ? store.dashboard?.memory?.connection ?? "Not checked" : "Disabled").foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("View memory") { store.selectedTab = 4 }
                    }.padding(12)
                }
                GroupBox {
                    HStack(spacing: 20) {
                        Image(systemName: "globe").font(.largeTitle).foregroundStyle(RagnarTheme.bronze)
                        VStack(alignment: .leading, spacing: 6) {
                            Text("BrowserOS Neo").font(.headline)
                            Text(store.config.upstream).font(.caption.monospaced()).textSelection(.enabled)
                            Text(store.dashboard?.neo.available == true ? "Online · read/write browser backend" : "Statistics endpoint unavailable · check connection").foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Check connection") { store.test("--test-browser") }.disabled(store.busy)
                    }.padding(12)
                }
                ForEach(store.dashboard?.connectors ?? []) { client in
                    GroupBox {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Label(client.name, systemImage: "desktopcomputer").font(.headline)
                                Spacer()
                                Text(client.activeSessions > 0 ? "\(client.activeSessions) live sessions" : client.configured ? "Configured" : "Not configured")
                                    .foregroundStyle(client.activeSessions > 0 ? .green : .secondary)
                            }
                            Text(client.path).font(.caption.monospaced()).foregroundStyle(.secondary).textSelection(.enabled)
                            Text("Configured means a local entry exists. A live session means OpenRagnar recorded an open MCP process; it does not imply a request is currently running.").font(.caption).foregroundStyle(.secondary)
                            HStack {
                                if client.name == "Claude Desktop" { Button("Connect Claude Desktop") { if store.save() { store.connectClaude() } }.buttonStyle(.borderedProminent) }
                                Button(client.name == "Codex" ? "Copy Codex MCP config" : "Copy MCP config") { client.name == "Codex" ? store.copyCodex() : store.copyMCP() }
                            }
                            if let others = client.otherConnectors, !others.isEmpty {
                                Divider()
                                Text("Other MCP entries in this client").font(.subheadline.weight(.medium))
                                Text(others.joined(separator: "  ·  ")).font(.callout).textSelection(.enabled)
                                Text("These connect directly to the client. OpenRagnar does not route or meter their requests. Cloud connectors may not appear in local configuration.").font(.caption).foregroundStyle(.secondary)
                            }
                        }.padding(12)
                    }
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Observed MCP clients").font(.headline)
                        let clients = Dictionary(grouping: store.dashboard?.sessions ?? [], by: \.client)
                        if clients.isEmpty { Text("No new sessions recorded yet. Restart your client after installing this update.").foregroundStyle(.secondary) }
                        ForEach(clients.keys.sorted(), id: \.self) { name in
                            HStack { Text(name); Spacer(); Text("\(clients[name]?.count ?? 0) recorded sessions").foregroundStyle(.secondary) }
                        }
                    }.padding(12)
                }
                Text("Install the app in Applications before copying configuration. Enable OpenRagnar's tools in the client. Keep BrowserOS Neo running, and disable its duplicate direct connector in a chat when testing gateway savings.").font(.callout).foregroundStyle(.secondary)
            }.padding(24)
        }
    }
}

struct SessionList: View {
    var sessions: [GatewaySession]
    @Binding var selected: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack { Text("\(sessions.count) recorded sessions").font(.subheadline.weight(.medium)); Spacer(); Button("All recent requests") { selected = "" } }
            Table(sessions, selection: Binding<String?>(get: { selected.isEmpty ? nil : selected }, set: { selected = $0 ?? "" })) {
                TableColumn("Session") { s in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(s.label.isEmpty ? s.client : s.label)
                        Text("\(s.client) · \(timestamp(s.started)) · \(s.id.prefix(6))").font(.caption).foregroundStyle(.secondary)
                    }
                }.width(min: 250, ideal: 350)
                TableColumn("State") { s in Text(s.active ? "Live" : "Ended").foregroundStyle(s.active ? .green : .secondary) }.width(65)
                TableColumn("Requests") { s in Text(number(s.toolRequests)) }.width(75)
                TableColumn("Context est.") { s in Text("~"+number(estimate(s.textBytes))) }.width(min: 95, ideal: 105)
                TableColumn("Saved est.") { s in Text("~"+number(estimate(s.savedText))) }.width(min: 85, ideal: 105)
                TableColumn("Browser calls") { s in Text(number(s.upstreamCalls)) }.width(min: 90, ideal: 100)
            }.frame(height: 155)
        }
    }
}
struct SessionsView: View {
    @ObservedObject var store: Store
    @State private var selected = ""
    @State private var source = 0
    @State private var problemsOnly = false
    @State private var selectedRequest: String?
    @State private var choseInitialSession = false
    @State private var benchmarkSession: GatewaySession?
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Sessions & requests").font(.title2.bold())
                Spacer()
                if source == 0 { Toggle("Problems only", isOn: $problemsOnly).toggleStyle(.checkbox) }
                Picker("Source", selection: $source) { Text("OpenRagnar").tag(0); Text("Neo history").tag(1) }.pickerStyle(.segmented).frame(width: 280)
            }
            if let d = store.dashboard {
                if source == 0 {
                    if d.sessions.isEmpty { ContentUnavailableView("No new sessions yet", systemImage: "clock", description: Text("Restart your MCP client after installing this update. Existing Neo sessions are available in Neo history.")) }
                    else {
                        SessionList(sessions: d.sessions, selected: $selected)
                        if let s = d.sessions.first(where: { $0.id == selected }) {
                            HStack {
                                Label(s.active ? "Live connection" : "Ended", systemImage: s.active ? "circle.fill" : "clock").foregroundStyle(s.active ? .green : .secondary)
                                Text("\(s.toolRequests) requests · \(s.upstreamCalls) browser calls · ~\(number(estimate(s.textBytes))) context tokens · ~\(number(estimate(s.savedText))) saved")
                                Spacer()
                                Button("Enter benchmark") { benchmarkSession = s }
                            }.font(.caption)
                            if let b = d.benchmarks.first(where: { $0.sessionId == s.id }) {
                                Text("Matched trial totals entered by you: Claude alone \(b.claudeTokens.map(number) ?? "—") · Neo alone \(b.neoTokens.map(number) ?? "—") · Claude + OpenRagnar \(b.gatewayTokens.map(number) ?? "—") tokens").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        let rows = d.requests.filter { (selected.isEmpty || $0.sessionId == selected) && (!problemsOnly || $0.status != "ok") }
                        Table(rows, selection: $selectedRequest) {
                            TableColumn("Request") { r in VStack(alignment: .leading, spacing: 3) { Text(r.tool.isEmpty ? r.method : r.tool).font(.system(.body, design: .monospaced)); Text(timestamp(r.started)).font(.caption).foregroundStyle(.secondary) } }.width(min: 170, ideal: 220)
                            TableColumn("Context est.") { r in Text("~"+number(estimate(r.inputBytes+r.clientText))) }.width(min: 90, ideal: 110)
                            TableColumn("Saved est.") { r in Text("~"+number(estimate(r.upstreamInputBytes+r.upstreamText-r.inputBytes-r.clientText))).foregroundStyle(r.upstreamInputBytes+r.upstreamText >= r.inputBytes+r.clientText ? .green : .orange) }.width(min: 80, ideal: 100)
                            TableColumn("Calls / moves") { r in Text("\(r.upstreamCalls) / \(r.moves.map { "≈\($0)" } ?? "—")") }.width(min: 95, ideal: 110)
                            TableColumn("Provider") { r in Text(r.providerUnknown > 0 ? "\(r.providerTokens)+?" : number(r.providerTokens)) }.width(min: 65, ideal: 80)
                            TableColumn("Seconds") { r in Text(String(format: "%.2f", max(0,r.finished-r.started))) }.width(min: 60, ideal: 75)
                            TableColumn("Status") { r in Text(r.status).foregroundStyle(r.status == "ok" ? Color.secondary : Color.orange) }.width(min: 50, ideal: 65)
                        }
                        HStack {
                            Text(selected.isEmpty ? "Showing all recent sessions" : "Showing selected session").font(.caption).foregroundStyle(.secondary)
                            Spacer()
                            Button("View request diagnostics", systemImage: "stethoscope") {
                                store.diagnosticQuery = selectedRequest ?? ""; store.selectedTab = 5
                            }.disabled(selectedRequest == nil)
                        }
                        Text("Calls are measured upstream MCP calls. ≈ moves are Neo's actual dispatch records matched by time, including internal SDK steps. Overlapping requests or missing records show —. The newest \(rows.count) retained requests are shown; text estimates exclude images and Claude billing.").font(.caption).foregroundStyle(.secondary)
                    }
                } else {
                    Table(d.neo.sessions ?? []) {
                        TableColumn("Session") { s in VStack(alignment: .leading, spacing: 3) { Text(s.label); Text(timestamp(s.started)).font(.caption).foregroundStyle(.secondary) } }.width(min: 200, ideal: 300)
                        TableColumn("Client") { s in Text(s.client) }.width(min: 120, ideal: 180)
                        TableColumn("Route") { s in Text(s.viaGateway ? "OpenRagnar" : "Direct / other") }.width(min: 100, ideal: 130)
                        TableColumn("Tokens est.") { s in Text(s.tokens.map { "~"+number($0) } ?? "—") }
                        TableColumn("Moves") { s in Text(number(s.moves)) }.width(70)
                        TableColumn("Status") { s in Text(s.status) }.width(80)
                    }
                    Text("Latest 100 sessions reported by Neo, including your previous OpenRagnar sessions. Neo counts SDK dispatches as moves and reports estimated tool tokens. Old sessions do not have gateway savings counters.").font(.caption).foregroundStyle(.secondary)
                }
            } else { ProgressView("Loading sessions…"); Spacer() }
        }.padding(24).sheet(item: $benchmarkSession) { BenchmarkView(store: store, session: $0) }
            .onAppear { chooseInitialSession() }
            .onChange(of: store.dashboard?.sessions.first?.id) { chooseInitialSession() }
    }
    private func chooseInitialSession() {
        guard !choseInitialSession, let latest = store.dashboard?.sessions.first(where: { $0.toolRequests > 0 }) else { return }
        selected = latest.id; choseInitialSession = true
    }
}
struct BenchmarkView: View {
    @ObservedObject var store: Store
    var session: GatewaySession
    @Environment(\.dismiss) private var dismiss
    @State private var claude = ""
    @State private var neo = ""
    @State private var gateway = ""
    var valid: Bool {
        [claude,neo,gateway].allSatisfy { $0.isEmpty || (Int($0).map { $0 >= 0 && $0 <= 1_000_000_000_000 } ?? false) }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Matched task benchmark").font(.title2.bold())
            Text("Enter end-to-end token totals you obtained from the client or provider for the same task, model, starting state and success criteria. These are user-entered measurements; gateway text estimates are not billed totals.").foregroundStyle(.secondary)
            TextField("Claude alone · total tokens", text: $claude)
            TextField("Claude + Neo directly · total tokens", text: $neo)
            TextField("Claude + OpenRagnar · total tokens", text: $gateway)
            Text(valid ? "Leave unavailable totals blank. Entering zero records an actual zero." : "Enter nonnegative whole token totals, or leave the field blank.").font(.caption).foregroundStyle(valid ? Color.secondary : Color.orange)
            HStack { Button("Cancel") { dismiss() }; Spacer(); Button("Save benchmark") { store.saveBenchmark(session: session.id, claude: claude, neo: neo, gateway: gateway); if store.busy { dismiss() } }.buttonStyle(.borderedProminent).disabled(!valid) }
        }.padding(28).frame(width: 580).onAppear {
            if let b = store.dashboard?.benchmarks.first(where: { $0.sessionId == session.id }) {
                claude = b.claudeTokens.map(String.init) ?? ""; neo = b.neoTokens.map(String.init) ?? ""; gateway = b.gatewayTokens.map(String.init) ?? ""
            }
        }
    }
}
