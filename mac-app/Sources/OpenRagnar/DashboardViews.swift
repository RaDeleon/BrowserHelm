import SwiftUI
import AppKit

struct MetricCard: View {
    var title: String; var value: String; var note: String; var symbol: String
    var tint: Color = .cyan
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Label(title, systemImage: symbol).font(.callout).foregroundStyle(.secondary)
            Text(value).font(.system(size: 28, weight: .semibold, design: .rounded)).foregroundStyle(tint).textSelection(.enabled)
            Text(note).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(18)
            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 14))
    }
}
struct StatsBar: View {
    var data: Dashboard
    var body: some View {
        let t = data.totals
        HStack(spacing: 12) {
            MetricCard(title: "Tokens used · est.", value: "~" + number(estimate(t.inputBytes + t.clientText)), note: "Text token equivalents used", symbol: "text.alignleft")
            MetricCard(title: "Tokens saved · est.", value: "~" + number(estimate(t.netTextSaved)), note: savingsNote(t), symbol: "arrow.down.right", tint: t.netTextSaved >= 0 ? .green : .orange)
            MetricCard(title: "Browser calls", value: number(t.upstreamCalls), note: "From \(number(t.toolRequests)) agent requests", symbol: "cursorarrow.click")
            MetricCard(title: "Decision provider", value: number(t.providerTokens), note: t.providerUnknown > 0 ? "Reported tokens; \(t.providerUnknown) calls lack totals" : "Provider-reported tokens · \(t.providerCalls) calls", symbol: "cpu", tint: .purple)
        }
    }
}
func savingsNote(_ counters: Counters) -> String {
    let baseline = counters.upstreamInputBytes + counters.upstreamText
    guard baseline > 0 else { return "Awaiting forwarded replies" }
    let ratio = abs(Double(counters.netTextSaved) / Double(baseline) * 100)
    return String(format: "%.1f%% %@ text · same calls", ratio, counters.netTextSaved >= 0 ? "less" : "more")
}
struct DashboardView: View {
    @ObservedObject var store: Store
    @State private var period = 0
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Text("See what your agent actually sends").font(.title2.bold())
                Text("Live counters across your MCP clients. BrowserOS Neo supplies browser execution; OpenRagnar keeps the agent's results smaller.").foregroundStyle(.secondary)
                if let d = store.dashboard {
                    let t = d.totals
                    GroupBox {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack { Text("Same browser calls, compact and raw context").font(.headline); Spacer(); Text("ESTIMATE").font(.caption.monospaced()).foregroundStyle(.secondary) }
                            comparison("OpenRagnar → agent", value: "~" + number(estimate(t.inputBytes+t.clientText)), note: "Recorded request text + compacted reply text")
                            comparison("Raw Neo browser-call equivalent", value: "~" + number(estimate(t.upstreamInputBytes+t.upstreamText)), note: "Original forwarded call text + replies; modeled, not a separate task run")
                            comparison("Net savings from OpenRagnar", value: "~" + number(estimate(t.netTextSaved)), note: "Includes catalog and instructions; artifact reads and local replies reduce savings")
                            Divider()
                            Text("Estimates use text UTF-8 bytes ÷ 3. They exclude image/audio billing, hidden reasoning, repeated conversation history and Claude's quota weighting. Decision-provider tokens are shown separately above.")
                                .font(.caption).foregroundStyle(.secondary)
                            if t.mediaCount > 0 { Text("\(t.mediaCount) image/audio blocks passed through. Their billed tokens are unknown.").font(.caption).foregroundStyle(.secondary) }
                        }.padding(10)
                    }
                    HStack(alignment: .top, spacing: 18) {
                        GroupBox {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("BrowserOS Neo's own savings").font(.headline)
                                Picker("Window", selection: $period) { Text("All time").tag(0); Text("30 days").tag(1); Text("7 days").tag(2) }.pickerStyle(.segmented)
                                if let stats = d.neo.stats, stats.hasMeasuredStats {
                                    let w = period == 0 ? stats.allTime : period == 1 ? stats.last30Days : stats.last7Days
                                    comparison("Neo tokens used", value: "~"+number(w.browserClawTokenEstimate), note: "Neo's estimate")
                                    comparison("Neo tokens saved", value: "~"+number(w.rawTokenSavingsEstimate), note: "Versus Neo's screenshot-first model")
                                    Text("\(number(w.sessionCount)) sessions · \(number(w.toolCallCount)) dispatches").font(.caption).foregroundStyle(.secondary)
                                    Text("All Neo traffic, including OpenRagnar. This is not an independent Claude-alone run, and these savings are not added to OpenRagnar's savings.").font(.caption).foregroundStyle(.secondary)
                                } else { Text(d.neo.error ?? "Neo has no measured history yet.").foregroundStyle(.secondary) }
                            }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        }
                        GroupBox {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Claude alone · matched trials").font(.headline)
                                let matched = d.benchmarks.filter { $0.claudeTokens != nil && $0.gatewayTokens != nil }
                                if !matched.isEmpty {
                                    comparison("Claude alone", value: number(matched.reduce(0){$0+($1.claudeTokens ?? 0)}), note: "User-entered totals for \(matched.count) matched trials")
                                    comparison("Claude with OpenRagnar", value: number(matched.reduce(0){$0+($1.gatewayTokens ?? 0)}), note: "User-entered end-to-end totals")
                                    comparison("Tokens saved", value: number(matched.reduce(0){$0+($1.claudeTokens ?? 0)-($1.gatewayTokens ?? 0)}), note: "Can be negative; actual entered totals")
                                } else { Text("Needs a matched benchmark").font(.title3.weight(.medium)); Text("MCP does not report Claude's billed usage. In Sessions, enter token totals from the same task run with Claude alone, Neo alone and OpenRagnar.").foregroundStyle(.secondary) }
                                let neoTrials = d.benchmarks.filter { $0.neoTokens != nil && $0.gatewayTokens != nil }
                                if !neoTrials.isEmpty {
                                    Divider()
                                    comparison("Neo directly", value: number(neoTrials.reduce(0){$0+($1.neoTokens ?? 0)}), note: "User-entered totals for \(neoTrials.count) matched trials")
                                    comparison("OpenRagnar savings vs Neo", value: number(neoTrials.reduce(0){$0+($1.neoTokens ?? 0)-($1.gatewayTokens ?? 0)}), note: "Same matched trials; can be negative")
                                }
                                Button("Open sessions") { store.selectedTab = 2 }
                            }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    GroupBox {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Neo without OpenRagnar · recent session history").font(.headline)
                            let direct = (d.neo.sessions ?? []).filter { !$0.viaGateway }
                            if d.neo.available {
                            HStack {
                                Label("\(direct.count) sessions", systemImage: "globe")
                                Spacer()
                                Text("~\(number(direct.compactMap(\.tokens).reduce(0,+))) tokens used · \(number(direct.reduce(0){$0+$1.moves})) moves")
                            }
                            Text("Reported Neo estimates for sessions not identified as OpenRagnar in the latest 100 records. \(d.neo.hasMore == true ? "Older sessions exist." : "") Direct-session savings need matched baselines; Neo's aggregate savings above cover all traffic.").font(.caption).foregroundStyle(.secondary)
                            if direct.contains(where: { $0.tokens == nil }) { Text("Some sessions lack token counters; the total includes only reported estimates.").font(.caption).foregroundStyle(.secondary) }
                            } else { Text(d.neo.error ?? "Neo history unavailable.").foregroundStyle(.secondary) }
                        }.padding(10)
                    }
                    HStack {
                        Label("Full Neo read/write tools", systemImage: "checkmark.shield")
                        Spacer()
                        Button("Check browser") { store.test("--test-browser") }.disabled(store.busy)
                    }
                    Text("Gateway statistics retain 90 days. The session list shows the latest 100 sessions and 1,000 requests. API keys, tool code and page contents are not stored in the metrics database.").font(.caption).foregroundStyle(.secondary)
                } else { ProgressView("Loading local counters…") }
            }.padding(24)
        }
    }
    func comparison(_ label: String, value: String, note: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack { Text(label); Spacer(); Text(value).font(.system(.body, design: .monospaced).weight(.semibold)).textSelection(.enabled) }
            Text(note).font(.caption).foregroundStyle(.secondary)
        }
    }
}

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
                        Image(systemName: "globe").font(.largeTitle).foregroundStyle(.cyan)
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
    @State private var benchmarkSession: GatewaySession?
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Sessions & requests").font(.title2.bold())
                Spacer()
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
                        let rows = d.requests.filter { selected.isEmpty || $0.sessionId == selected }
                        Table(rows) {
                            TableColumn("Request") { r in VStack(alignment: .leading, spacing: 3) { Text(r.tool.isEmpty ? r.method : r.tool).font(.system(.body, design: .monospaced)); Text(timestamp(r.started)).font(.caption).foregroundStyle(.secondary) } }.width(min: 170, ideal: 220)
                            TableColumn("Context est.") { r in Text("~"+number(estimate(r.inputBytes+r.clientText))) }.width(min: 90, ideal: 110)
                            TableColumn("Saved est.") { r in Text("~"+number(estimate(r.upstreamInputBytes+r.upstreamText-r.inputBytes-r.clientText))).foregroundStyle(r.upstreamInputBytes+r.upstreamText >= r.inputBytes+r.clientText ? .green : .orange) }.width(min: 80, ideal: 100)
                            TableColumn("Calls / moves") { r in Text("\(r.upstreamCalls) / \(r.moves.map { "≈\($0)" } ?? "—")") }.width(min: 95, ideal: 110)
                            TableColumn("Provider") { r in Text(r.providerUnknown > 0 ? "\(r.providerTokens)+?" : number(r.providerTokens)) }.width(min: 65, ideal: 80)
                            TableColumn("Seconds") { r in Text(String(format: "%.2f", max(0,r.finished-r.started))) }.width(min: 60, ideal: 75)
                            TableColumn("Status") { r in Text(r.status).foregroundStyle(r.status == "ok" ? Color.secondary : Color.orange) }.width(min: 50, ideal: 65)
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
struct MainView: View {
    @ObservedObject var store: Store
    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 22) {
                Label("OpenRagnar", systemImage: "bolt.shield.fill").font(.title3.bold()).foregroundStyle(.cyan)
                VStack(spacing: 6) {
                    page("Dashboard", icon: "chart.bar.xaxis", tag: 0)
                    page("Connectors", icon: "point.3.connected.trianglepath.dotted", tag: 1)
                    page("Sessions", icon: "clock.arrow.circlepath", tag: 2)
                    page("Memory", icon: "brain", tag: 4)
                    page("Settings", icon: "gearshape", tag: 3)
                }
                Spacer()
                Text("NEO EXECUTION\nOPENRAGNAR CONTEXT").font(.caption2.monospaced()).foregroundStyle(.secondary)
                Text("Personal build 0.4.0").font(.caption).foregroundStyle(.secondary)
            }.padding(20).frame(width: 195).frame(maxHeight: .infinity).background(.quaternary.opacity(0.4))
            Divider()
            VStack(spacing: 0) {
                HStack {
                    Text(["Overview", "Connections", "Activity", "Configuration", "Experience memory"][store.selectedTab]).font(.headline)
                    Spacer()
                    if let d = store.dashboard { Text("Updated \(Date(timeIntervalSince1970:d.updatedAt).formatted(date:.omitted,time:.shortened))").font(.caption).foregroundStyle(.secondary) }
                    Button { store.refreshDashboard() } label: { Image(systemName: "arrow.clockwise") }.help("Refresh local statistics").disabled(store.loadingDashboard)
                }.padding(20)
                Divider()
                if let d = store.dashboard { StatsBar(data: d).padding(20) }
                switch store.selectedTab {
                case 1: ConnectorsView(store: store)
                case 2: SessionsView(store: store)
                case 3: SettingsView(store: store)
                case 4: MemoryView(store: store)
                default: DashboardView(store: store)
                }
                Divider()
                HStack(alignment: .top) {
                    Image(systemName: store.dashboardError.isEmpty ? "info.circle" : "exclamationmark.triangle")
                    Text(store.dashboardError.isEmpty ? store.status : store.dashboardError).font(.caption).textSelection(.enabled).lineLimit(4)
                    Spacer()
                }.foregroundStyle(.secondary).padding(14)
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }.frame(minWidth: 1120, minHeight: 740)
    }
    func page(_ title: String, icon: String, tag: Int) -> some View {
        Button { store.selectedTab = tag } label: {
            Label(title, systemImage: icon).frame(maxWidth: .infinity, alignment: .leading).padding(10)
                .background(store.selectedTab == tag ? Color.cyan.opacity(0.13) : Color.clear, in: RoundedRectangle(cornerRadius: 8))
        }.buttonStyle(.plain)
    }
}
