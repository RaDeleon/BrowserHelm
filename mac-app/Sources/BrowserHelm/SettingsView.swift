import SwiftUI
struct SettingsView: View {
    @ObservedObject var store: Store
    @AppStorage("browserhelm.appearance") private var appearance = "system"
    var body: some View {
        Form {
            Section("Appearance") {
                Picker("Theme", selection: $appearance) { Text("System").tag("system"); Text("Light").tag("light"); Text("Dark").tag("dark") }
                Text("Packet Studio graphite and cyan. System follows your Mac's appearance.").font(.caption).foregroundStyle(.secondary)
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
                    Text("Use the exact model ID from your provider. Jev decisions default to pinned jev-1.13.0 for stable behavior; experimental Jev vision is separate. Local models must support structured JSON output.").font(.caption).foregroundStyle(.secondary)
                } else {
                    Text("All Neo read and write tools remain available. Autonomous navigation requires a decision provider.").foregroundStyle(.secondary)
                }
            }
            VisionSettingsSection(store: store)
            Section("Browser execution") {
                Toggle("Delegate routine browser steps", isOn: $store.config.delegationEnabled)
                Text("On: BrowserHelm runs bounded plans, using the selected decision and vision providers when needed. Off: Claude/Codex performs browser steps through direct tools; compact results remain enabled. Save, then reconnect to refresh available tools.").font(.caption).foregroundStyle(.secondary)
                Toggle("Ask agent to mark tasks", isOn: $store.config.agentTaskMarkers)
                Text("Optional start/finish tracking adds two agent calls per task. Off by default; manual Tasks controls still work. Save and reconnect to apply the agent guidance.").font(.caption).foregroundStyle(.secondary)
                Text("Keep planning, judgment and recovery with Claude/Codex. Use DOM refs for ordinary controls and batch deterministic reads. Delegate bounded multi-step plans when useful; request vision only for a unique target that DOM refs cannot identify. These are conservative workflow settings, not a measured optimum.").font(.caption).foregroundStyle(.secondary)
            }
            Section("Browser gateway") {
                TextField("Neo MCP endpoint", text: $store.config.upstream)
                Toggle("Compact catalog (optional; full read/write still available through run)", isOn: $store.config.compactCatalog)
                Stepper("Result budget: ~\(store.config.maxOutputTokens) tokens", value: $store.config.maxOutputTokens, in: 200...10000, step: 200)
                Text("The result budget is a byte estimate, not provider billing. The full tool catalog is enabled by default. Complete omitted output stays available locally. BrowserOS Neo must remain running.").font(.caption).foregroundStyle(.secondary)
            }
            Section("MCP clients") {
                ClientConnectionActions(store: store, client: "Claude Desktop")
                ClientConnectionActions(store: store, client: "Codex")
                Text("Connect or remove BrowserHelm’s MCP entry. Restart the client after changing a connection; existing sessions keep their tools until restarted.").font(.caption).foregroundStyle(.secondary)
            }
            Section("OpenViking memory") {
                Toggle("Learn from navigation, vision and request outcomes", isOn: $store.config.memory.enabled)
                Text("Uses your existing ~/.openviking/ovcli.conf connection and credential. Keys stay in that private file. BrowserHelm reads and writes only its own browser experience collection.").font(.caption).foregroundStyle(.secondary)
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
