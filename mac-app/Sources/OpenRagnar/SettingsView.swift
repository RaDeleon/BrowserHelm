import SwiftUI
struct SettingsView: View {
    @ObservedObject var store: Store
    var body: some View {
        Form {
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
            Section("Browser gateway") {
                TextField("Neo MCP endpoint", text: $store.config.upstream)
                Toggle("Compact catalog (optional; full read/write still available through run)", isOn: $store.config.compactCatalog)
                Stepper("Result budget: ~\(store.config.maxOutputTokens) tokens", value: $store.config.maxOutputTokens, in: 200...10000, step: 200)
                Text("The result budget is a byte estimate, not provider billing. The full tool catalog is enabled by default. Complete omitted output stays available locally. BrowserOS Neo must remain running.").font(.caption).foregroundStyle(.secondary)
            }
            Section("OpenViking memory") {
                Toggle("Learn from delegated navigation outcomes", isOn: $store.config.memory.enabled)
                Text("Uses your existing ~/.openviking/ovcli.conf connection and credential. Keys stay in that private file. OpenRagnar reads and writes only its own browser experience collection.").font(.caption).foregroundStyle(.secondary)
                Text("Recalls at most two past routes, with a 1.6 KB hint budget. Saves goals, public routes and verified outcomes; excludes page bodies, screenshots and form contents. Memory provides advice, not automatic approval or model training.").font(.caption).foregroundStyle(.secondary)
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
