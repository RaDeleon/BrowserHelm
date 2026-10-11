import SwiftUI
struct SettingsView: View {
    @ObservedObject var store: Store
    @AppStorage("openragnar.appearance") private var appearance = "system"
    var body: some View {
        Form {
            Section("Appearance") {
                Picker("Theme", selection: $appearance) { Text("System").tag("system"); Text("Light").tag("light"); Text("Dark").tag("dark") }
                Text("Bronze and stone tones. System follows your Mac's appearance.").font(.caption).foregroundStyle(.secondary)
            }
            Section("Decision provider") {
                Picker("Provider", selection: $store.config.provider) { ForEach(providers, id: \.self) { Text(names[$0]!).tag($0) } }
                    .onChange(of: store.config.provider) { _, _ in store.refreshKey() }
                if store.config.provider != "none" {
                    TextField("API base URL", text: store.profileBinding(\.endpoint))
                    TextField("Model ID", text: store.profileBinding(\.model))
                    SecureField(store.storedKey ? "New key (leave blank to keep saved key)" : "API key (optional for local servers)", text: $store.key)
                    HStack {
                        Label(store.storedKey ? "Key saved in macOS Keychain" : "No saved API key", systemImage: store.storedKey ? "lock.fill" : "key")
                            .font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        if store.storedKey { Button("Remove key", role: .destructive) { store.removeKey() } }
                    }
                    Text("Use the exact model ID from your provider. Local models must support structured JSON output. LM Studio supplies the local API; Bionic is its separate agent app.").font(.caption).foregroundStyle(.secondary)
                } else {
                    Text("All Neo read and write tools remain available. Autonomous navigation requires a decision provider.").foregroundStyle(.secondary)
                }
            }
            Section("Local vision") {
                Toggle("Ground visual targets on this Mac", isOn: $store.config.vision.enabled)
                Picker("Vision server", selection: $store.config.vision.provider) {
                    Text("Ollama").tag("ollama"); Text("LM Studio").tag("lmstudio")
                }.onChange(of: store.config.vision.provider) { _, provider in
                    store.config.vision.endpoint = provider == "ollama" ? "http://127.0.0.1:11434" : "http://127.0.0.1:1234/v1"
                    store.config.vision.model = provider == "ollama" ? "qwen3-vl:2b-instruct" : ""
                }
                TextField("Local API URL", text: $store.config.vision.endpoint)
                TextField("Downloaded vision model", text: $store.config.vision.model)
                Text("Ollama setup: ollama pull qwen3-vl:2b-instruct (about 1.9 GB). LM Studio: load a vision model supporting normalized 0–1000 coordinates and JSON output. Keep the local server running.").font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                Text("The agent calls openragnar_visual_act for a visual target. Screenshots go to the local server; the client receives a small point/click report. Jev remains the text decision provider. Point is the default; clicks check for stale pages. Save and reconnect your MCP client to update its tool list.").font(.caption).foregroundStyle(.secondary)
                Text("This uses Qwen3-VL, not unreleased BrowserVLM weights. Latency and accuracy depend on the model and page. Local server availability does not prove pointing accuracy. No 10× speed or quota claim.").font(.caption).foregroundStyle(.secondary)
                Button("Test vision server") { store.test("--test-vision") }
            }
            Section("Browser gateway") {
                TextField("Neo MCP endpoint", text: $store.config.upstream)
                Toggle("Compact catalog (optional; full read/write still available through run)", isOn: $store.config.compactCatalog)
                Stepper("Result budget: ~\(store.config.maxOutputTokens) tokens", value: $store.config.maxOutputTokens, in: 200...10000, step: 200)
                Text("The result budget is a byte estimate, not provider billing. The full tool catalog is enabled by default. Complete omitted output stays available locally. BrowserOS Neo must remain running.").font(.caption).foregroundStyle(.secondary)
            }
            Section("OpenViking memory") {
                Toggle("Learn from navigation and request outcomes", isOn: $store.config.memory.enabled)
                Text("Uses your existing ~/.openviking/ovcli.conf connection and credential. Keys stay in that private file. OpenRagnar reads and writes only its own browser experience collection.").font(.caption).foregroundStyle(.secondary)
                Text("Recalls bounded routes and failure lessons. Two local text-verified runs can skip a provider choice, with fresh link and text checks. Direct requests retain metadata-only outcomes and private fingerprints; repeated failures return guidance. No browser write replay or model training.").font(.caption).foregroundStyle(.secondary)
                HStack {
                    Button("Test OpenViking") { store.test("--test-memory") }
                    Button("Sync pending outcomes") { store.test("--sync-memory") }.disabled(!store.config.memory.enabled)
                    Button("View memory") { store.selectedTab = 4 }
                }
            }
            HStack {
                Button("Save settings") { store.save() }.buttonStyle(.borderedProminent)
                Button("Test provider") { store.test("--test-provider") }.disabled(store.config.provider == "none" || store.busy)
                Spacer()
            }
            Text("Cloud providers receive task goals, page URLs, titles and link labels during delegated navigation. Choose a local server to keep those decisions on your Mac. API keys are never written to MCP configuration.").font(.caption).foregroundStyle(.secondary)
        }.formStyle(.grouped).padding(8).disabled(store.busy)
    }
}
