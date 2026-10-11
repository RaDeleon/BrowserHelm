import SwiftUI
import AppKit

struct ProviderTaskUsage: Decodable {
    var calls: Int; var tokens: Int?; var knownTokens: Int; var unknownUsageCalls: Int
    var cost: Double?; var knownCost: Double; var unknownCostCalls: Int; var costBasis: String
}
struct PromptTask: Decodable, Identifiable {
    var id: String; var label: String; var started: Double; var finished: Double?
    var status: String; var boundarySource: String; var model: String; var effort: String; var verification: String
    var elapsedSeconds: Double; var toolCalls: Int; var failures: Int; var browserCalls: Int; var toolSeconds: Double
    var trackingCalls: Int; var trackingSeconds: Double; var mainAgentTurns: Int?
    var textTokenEquivalents: Int; var usageSource: String; var usage: [String: Int?]
    var providerRates: [String:Double?]; var pricingRates: [Double]?
    var pricingDate: String; var pricingSource: String; var claudeCost: Double?
    var decision: ProviderTaskUsage; var vision: ProviderTaskUsage; var memoryCost: Double?
    var totalCost: Double?; var knownCost: Double; var sessionIds: [String]
}
func taskDollars(_ value: Double?) -> String { value.map { String(format: "$%.5f", $0) } ?? "Unknown" }

struct TasksView: View {
    @ObservedObject var store: Store
    @State private var showStart = false
    @State private var editTask: PromptTask?
    @State private var selected: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("One prompt · one task").font(.title2.bold())
                Spacer()
                Button("Export JSON") { export() }.disabled(store.dashboard?.tasks == nil)
                Button("Start task", systemImage: "plus") { showStart = true }.buttonStyle(.borderedProminent)
            }
            Text("Start just before submitting your prompt; finish after checking the result. MCP task markers also work, but their timing starts when Claude calls the tool. Attach another connection when the same task spans a reconnect or a design subprocess.").font(.caption).foregroundStyle(.secondary)
            let rows = store.dashboard?.tasks ?? []
            Table(rows, selection: $selected) {
                TableColumn("Task") { t in VStack(alignment: .leading) { Text(t.label); Text(timestamp(t.started)).font(.caption).foregroundStyle(.secondary) } }.width(min: 160, ideal: 230)
                TableColumn("Time") { t in Text((t.boundarySource == "retrospective_tool_window" ? "Tool window " : "") + String(format: "%.1fs", t.elapsedSeconds)) }.width(105)
                TableColumn("Calls / failed") { t in Text("\(t.toolCalls) / \(t.failures)") }.width(90)
                TableColumn("Claude API equiv.") { t in Text(taskDollars(t.claudeCost)) }.width(110)
                TableColumn("Jev / decision") { t in Text(taskDollars(t.decision.cost)) }.width(100)
                TableColumn("Vision API") { t in Text(taskDollars(t.vision.cost)) }.width(90)
                TableColumn("Status") { t in Text(t.status).foregroundStyle(t.status == "failed" ? Color.orange : Color.secondary) }.width(110)
            }
            if let t = rows.first(where: { $0.id == selected }) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("\(t.model.isEmpty ? "Model unknown" : t.model) · \(t.effort.isEmpty ? "Effort unknown" : t.effort) · \(t.verification)").font(.headline)
                        Spacer()
                        Button("Usage & connections") { editTask = t }
                        if t.status == "running" {
                            Menu("Finish task") {
                                Button("Complete · verified by me") { finish(t, "complete", "independent") }
                                Button("Awaiting approval") { finish(t, "awaiting_approval", "unverified") }
                                Button("Failed") { finish(t, "failed", "unverified") }
                                Button("Cancelled") { finish(t, "cancelled", "unverified") }
                            }
                        }
                    }
                    Text("\(t.toolCalls) gateway work calls + \(t.trackingCalls) tracking calls · \(t.browserCalls) upstream calls · \(String(format: "%.2fs", t.toolSeconds)) summed tool time · ~\(t.textTokenEquivalents) gateway text token equivalents").font(.caption)
                    Text("Claude usage: \(t.usageSource). Decision: \(t.decision.tokens.map(number) ?? "Unknown") tokens / \(t.decision.calls) calls. Vision: \(t.vision.tokens.map(number) ?? "Unknown") tokens / \(t.vision.calls) calls.").font(.caption)
                    Text("Cost basis: decision \(t.decision.costBasis); vision \(t.vision.costBasis). Usage: input \(t.usage["input_tokens"].flatMap { $0 }.map(number) ?? "Unknown"), output \(t.usage["output_tokens"].flatMap { $0 }.map(number) ?? "Unknown").").font(.caption)
                    Text("Total: \(taskDollars(t.totalCost)) · known subtotal: \(taskDollars(t.knownCost)) · memory: \(taskDollars(t.memoryCost)). API-equivalent Claude cost uses \(t.pricingDate) prices, not your Max bill. Effort changes usage, not the list rate.").font(.caption)
                    Text("Boundary: \(t.boundarySource). Other connectors, conversation replay, reasoning and media usage are unknown unless included in entered Claude totals. Missing values stay unknown. Local inference has $0 API fees, excluding machine/electricity costs.").font(.caption).foregroundStyle(.secondary)
                }.padding(14).background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
            }
        }.padding(24)
        .sheet(isPresented: $showStart) { StartPromptTask(store: store) }
        .sheet(item: $editTask) { TaskUsageEditor(store: store, task: $0) }
    }
    private func finish(_ task: PromptTask, _ status: String, _ verification: String) {
        store.taskCommand(["action":"finish","task_id":task.id,"status":status,"verification":verification])
    }
    private func export() {
        let panel = NSSavePanel(); panel.nameFieldStringValue = "OpenRagnar-tasks.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        // Full metadata-only export comes from the engine, not a UI subset.
        do { let raw = try Runner.test("--dashboard"); let data = Data(raw.utf8)
            let obj = try JSONSerialization.jsonObject(with: data) as? [String:Any]
            let output = try JSONSerialization.data(withJSONObject: obj?["tasks"] ?? [], options: [.prettyPrinted,.sortedKeys])
            try output.write(to: url)
        } catch { store.status = error.localizedDescription }
    }
}
struct StartPromptTask: View {
    @ObservedObject var store: Store
    @Environment(\.dismiss) var dismiss
    @State private var label = ""
    @State private var session = ""
    @State private var model = "claude-opus-5.5"
    @State private var effort = "high"
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Start a prompt task").font(.title2.bold())
            TextField("Short task label, without private content", text: $label)
            Picker("MCP connection", selection: $session) {
                Text("Choose connection").tag("")
                ForEach(store.dashboard?.sessions.filter { $0.active } ?? []) { s in Text(s.client + " · " + String(s.id.prefix(8))).tag(s.id) }
            }
            TextField("Claude API model ID", text: $model)
            Picker("Effort", selection: $effort) { ForEach(["unknown","low","medium","high","max"], id: \.self) { Text($0).tag($0) } }
            Text("Model and effort are entered by you. Start immediately before sending the prompt. No prompt text is stored.").font(.caption).foregroundStyle(.secondary)
            HStack { Button("Cancel") { dismiss() }; Spacer(); Button("Start") { store.taskCommand(["action":"start","label":label,"session_id":session,"model":model,"effort":effort]); dismiss() }.disabled(label.trimmingCharacters(in: .whitespaces).isEmpty || session.isEmpty || store.busy) }
        }.padding(24).frame(width: 520)
    }
}
struct TaskUsageEditor: View {
    @ObservedObject var store: Store
    var task: PromptTask
    @Environment(\.dismiss) var dismiss
    @State private var values: [String:String] = [:]
    @State private var source = "manual"
    @State private var attach = ""
    @State private var memory = ""
    @State private var turns = ""
    let keys = ["input_tokens","output_tokens","cache_read_tokens","cache_write_5m_tokens","cache_write_1h_tokens"]
    let rateKeys = ["decision_input_rate","decision_output_rate","vision_input_rate","vision_output_rate"]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(task.label).font(.title2.bold())
                Text("Claude token totals for this task").font(.headline)
                Text("Include all model turns, reasoning and media in client totals when available. Blank means unknown; enter 0 only when confirmed. API pricing alone cannot recover missing tokens.").font(.caption).foregroundStyle(.secondary)
                ForEach(keys, id: \.self) { key in TextField(key.replacingOccurrences(of: "_", with: " "), text: binding(key)) }
                Picker("Usage basis", selection: $source) { Text("Entered client totals").tag("manual"); Text("Estimate").tag("estimated") }
                Text("Optional provider rates, USD per million tokens").font(.headline)
                Text("Used only when the provider omits its cost. Reported costs take precedence. Jev and vision are recorded separately.").font(.caption)
                ForEach(rateKeys, id: \.self) { key in TextField(key.replacingOccurrences(of: "_", with: " "), text: binding(key)) }
                TextField("Main-agent turns (blank = unknown)", text: $turns)
                TextField("Memory cost USD (blank = unknown)", text: $memory)
                HStack { Button("Cancel") { dismiss() }; Spacer(); Button("Save usage") { save() }.disabled(!valid || store.busy) }
                if task.status == "running" {
                    Divider()
                    Picker("Additional MCP connection", selection: $attach) {
                        Text("Choose connection").tag("")
                        ForEach(store.dashboard?.sessions.filter { $0.active && !task.sessionIds.contains($0.id) } ?? []) { s in Text(s.client + " · " + String(s.id.prefix(8))).tag(s.id) }
                    }
                    Button("Attach connection to this task") { store.taskCommand(["action":"attach","task_id":task.id,"session_id":attach]); dismiss() }.disabled(attach.isEmpty)
                }
            }.padding(24)
        }.frame(width: 540, height: 640)
        .onAppear { for key in keys { if let optional = task.usage[key], let value = optional { values[key] = String(value) } }; for key in rateKeys { if let optional = task.providerRates[key], let value = optional { values[key] = String(value) } }; if let value = task.memoryCost { memory = String(value) }; turns = task.mainAgentTurns.map(String.init) ?? ""; source = task.usageSource == "estimated" ? "estimated" : "manual" }
    }
    private func binding(_ key: String) -> Binding<String> { Binding(get: { values[key] ?? "" }, set: { values[key] = $0 }) }
    private var valid: Bool {
        (turns.isEmpty || (Int(turns).map { $0 >= 0 } ?? false)) && keys.allSatisfy { let v = values[$0] ?? ""; return v.isEmpty || (Int(v).map { $0 >= 0 && $0 <= 1_000_000_000_000 } ?? false) } &&
        (rateKeys.map { values[$0] ?? "" } + [memory]).allSatisfy { $0.isEmpty || (Double($0).map { $0.isFinite && $0 >= 0 } ?? false) }
    }
    private func save() {
        var usage: [String:Any] = [:]
        for key in keys { if let value = Int(values[key] ?? "") { usage[key] = value } }
        var data: [String:Any] = ["action":"usage","task_id":task.id,"usage":usage,"usage_source":source]
        for key in rateKeys { if let value = Double(values[key] ?? "") { data[key] = value } }
        if let value = Int(turns) { data["main_agent_turns"] = value }
        if let value = Double(memory) { data["memory_cost"] = value }
        store.taskCommand(data); dismiss()
    }
}
