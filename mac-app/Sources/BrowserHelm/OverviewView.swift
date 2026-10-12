import SwiftUI

struct DashboardView: View {
    @ObservedObject var store: Store
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Every request, in view.").font(.system(size: 32, weight: .semibold, design: .default))
                        Text("Browser execution with less context overhead.").foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 16)
                    if let d = store.dashboard {
                        VStack(alignment: .trailing, spacing: 8) {
                            Label(d.neo.available ? "Neo online" : "Neo unavailable", systemImage: "circle.fill")
                                .font(.caption).foregroundStyle(d.neo.available ? Color.green : Color.orange)
                            Text("\(d.sessions.filter(\.active).count) live MCP sessions").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                if let d = store.dashboard {
                    HStack(spacing: 16) {
                        MetricCard(title: "Gateway requests", value: number(d.totals.toolRequests), note: "Across recorded sessions", symbol: "network")
                        MetricCard(title: "Context reduction", value: "~" + number(estimate(d.totals.netTextSaved)), note: savingsNote(d.totals), symbol: "arrow.down.right")
                        MetricCard(title: "Provider usage", value: providerValue(d.totals), note: providerNote(d.totals), symbol: "cpu", tint: HelmTheme.ink)
                    }
                    ContextSavingsPanel(totals: d.totals)
                    RecentContextChart(requests: d.requests)
                    HStack(alignment: .top, spacing: 16) {
                        NeoOverviewPanel(neo: d.neo)
                        BenchmarkOverviewPanel(benchmarks: d.benchmarks) { store.selectedTab = 2 }
                    }
                    HStack(alignment: .top, spacing: 16) {
                        DirectNeoPanel(neo: d.neo)
                        MemoryOverviewPanel(memory: d.memory) { store.selectedTab = 4 }
                    }
                    HStack {
                        Label("Full browser read/write access", systemImage: "checkmark.circle")
                        Spacer()
                        Button("Check browser") { store.test("--test-browser") }.disabled(store.busy)
                    }.font(.callout)
                    DisclosureGroup("How to read these numbers") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Context estimates use text UTF-8 bytes ÷ 3. They exclude hidden reasoning, full conversation replay, cache treatment, media billing and Claude's quota weighting. Provider-reported tokens are separate.")
                            Text("Neo's totals include BrowserHelm traffic. They are not added to gateway savings. Claude-alone comparisons require matched totals entered by you.")
                            Text("Local gateway counters retain \(d.retentionDays) days. Lists show up to \(d.sessionLimit) sessions and \(d.requestLimit) requests. Metrics exclude API keys, tool code and page contents.")
                        }.font(.caption).foregroundStyle(.secondary).padding(.top, 8)
                    }.font(.caption).foregroundStyle(.secondary)
                } else if !store.dashboardError.isEmpty {
                    ContentUnavailableView("Statistics unavailable", systemImage: "chart.bar.xaxis", description: Text("Use Refresh to reload local counters. Browser tools can continue running."))
                } else {
                    ProgressView("Loading your browser activity…").frame(maxWidth: .infinity, minHeight: 260)
                }
            }.padding(24).frame(maxWidth: 1440, alignment: .leading).frame(maxWidth: .infinity)
        }
    }
    private func providerValue(_ t: Counters) -> String {
        t.providerCalls == 0 ? "—" : number(t.providerTokens) + (t.providerUnknown > 0 ? "+?" : "")
    }
    private func providerNote(_ t: Counters) -> String {
        t.providerCalls == 0 ? "No decisions recorded" : t.providerUnknown > 0 ? "\(t.providerUnknown) totals unknown" : "Reported · \(t.providerCalls) \(t.providerCalls == 1 ? "decision" : "decisions")"
    }
}

struct NeoOverviewPanel: View {
    var neo: NeoSnapshot
    @State private var period = 0
    var body: some View {
        HelmPanel {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeading(title: "BrowserOS Neo", symbol: "globe", evidence: "NEO ESTIMATE")
                Picker("History window", selection: $period) { Text("All time").tag(0); Text("30 days").tag(1); Text("7 days").tag(2) }.pickerStyle(.segmented)
                if let stats = neo.stats, stats.hasMeasuredStats {
                    let window = period == 0 ? stats.allTime : period == 1 ? stats.last30Days : stats.last7Days
                    StatDetail(title: "Tokens used", value: "~" + number(window.browserClawTokenEstimate))
                    StatDetail(title: "Tokens saved", value: "~" + number(window.rawTokenSavingsEstimate), note: "Versus Neo's screenshot-first model")
                    Divider()
                    HStack { Label(number(window.sessionCount) + " sessions", systemImage: "rectangle.stack"); Spacer(); Text(number(window.toolCallCount) + " moves") }.font(.caption).foregroundStyle(.secondary)
                    Text("All Neo traffic, including BrowserHelm. These savings are separate and are not added to gateway savings.").font(.caption).foregroundStyle(.secondary)
                } else { Text(neo.error ?? "No measured Neo history yet.").font(.callout).foregroundStyle(.secondary) }
            }
        }
    }
}
struct BenchmarkOverviewPanel: View {
    var benchmarks: [Benchmark]
    var openSessions: () -> Void
    var body: some View {
        HelmPanel {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeading(title: "Claude comparison", symbol: "equal.square", evidence: "ENTERED TOTALS")
                let matched = benchmarks.filter { $0.claudeTokens != nil && $0.gatewayTokens != nil }
                if matched.isEmpty {
                    HStack(alignment: .top, spacing: 14) {
                        Image(systemName: "chart.bar.doc.horizontal").font(.system(size: 29, weight: .light)).foregroundStyle(HelmTheme.accent)
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Start a matched trial").font(.title3.weight(.medium))
                            Text("Run the same task with Claude alone and with BrowserHelm, then enter the client's totals in Sessions.").font(.callout).foregroundStyle(.secondary)
                        }
                    }.padding(.vertical, 8)
                } else {
                    StatDetail(title: "Claude alone", value: number(matched.reduce(0) { $0 + ($1.claudeTokens ?? 0) }))
                    StatDetail(title: "With BrowserHelm", value: number(matched.reduce(0) { $0 + ($1.gatewayTokens ?? 0) }))
                    StatDetail(title: "Net tokens saved", value: number(matched.reduce(0) { $0 + ($1.claudeTokens ?? 0) - ($1.gatewayTokens ?? 0) }), note: "\(matched.count) matched trials · can be negative")
                }
                let neoTrials = benchmarks.filter { $0.neoTokens != nil && $0.gatewayTokens != nil }
                if !neoTrials.isEmpty {
                    Divider()
                    StatDetail(title: "Neo directly", value: number(neoTrials.reduce(0) { $0 + ($1.neoTokens ?? 0) }))
                    StatDetail(title: "Saved versus Neo", value: number(neoTrials.reduce(0) { $0 + ($1.neoTokens ?? 0) - ($1.gatewayTokens ?? 0) }), note: "\(neoTrials.count) matched trials · can be negative")
                }
                Button("Open sessions", action: openSessions)
                Text("MCP does not report Claude's billed usage. These comparisons use your entered end-to-end totals.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}
struct DirectNeoPanel: View {
    var neo: NeoSnapshot
    var body: some View {
        HelmPanel {
            VStack(alignment: .leading, spacing: 16) {
                SectionHeading(title: "Neo without BrowserHelm", symbol: "arrow.up.forward", evidence: "RECENT HISTORY")
                let direct = (neo.sessions ?? []).filter { !$0.viaGateway }
                if neo.available {
                    let reported = direct.compactMap(\.tokens)
                    HStack(alignment: .firstTextBaseline) {
                        Text(!direct.isEmpty && reported.isEmpty ? "—" : "~" + number(reported.reduce(0, +))).font(.title2.weight(.semibold)).monospacedDigit()
                        Text("tokens used").font(.caption).foregroundStyle(.secondary)
                    }
                    Text("\(direct.count) sessions · \(number(direct.reduce(0) { $0 + $1.moves })) moves").font(.caption).foregroundStyle(.secondary)
                    Text("Sessions not identified as BrowserHelm in Neo's latest 100 records. Direct-session savings need a matched baseline.").font(.caption).foregroundStyle(.secondary)
                    if direct.contains(where: { $0.tokens == nil }) { Text("Some token estimates are missing; only reported values are included.").font(.caption).foregroundStyle(.secondary) }
                    if neo.hasMore == true { Text("Older Neo sessions exist.").font(.caption).foregroundStyle(.secondary) }
                } else { Text(neo.error ?? "Neo history unavailable.").font(.callout).foregroundStyle(.secondary) }
            }
        }
    }
}
struct MemoryOverviewPanel: View {
    var memory: MemorySnapshot?
    var openMemory: () -> Void
    var body: some View {
        HelmPanel {
            VStack(alignment: .leading, spacing: 16) {
                SectionHeading(title: "Experience memory", symbol: "brain", evidence: "OPENVIKING")
                if let memory {
                    HStack(alignment: .firstTextBaseline, spacing: 26) {
                        memoryCount("Uploaded", value: memory.saved)
                        memoryCount("Pending", value: memory.pending)
                        memoryCount("Tasks with recall", value: memory.tasksWithRecall)
                    }
                    Text(memory.enabled ? memory.connection : "Disabled in Settings").font(.caption).foregroundStyle(.secondary)
                } else { Text("Connect OpenViking in Settings to reuse verified browser routes.").font(.callout).foregroundStyle(.secondary) }
                Button("View memory", action: openMemory)
                Text("Past outcomes inform choices. Current pages still determine what can run; embedding costs are not counted here.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    private func memoryCount(_ label: String, value: Int) -> some View {
        VStack(alignment: .leading, spacing: 4) { Text(number(value)).font(.title2.weight(.semibold)).monospacedDigit(); Text(label).font(.caption).foregroundStyle(.secondary) }
    }
}
