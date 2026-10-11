import SwiftUI

struct VisionSettingsSection: View {
    @ObservedObject var store: Store
    private var presets: [VisionPreset] { VisionPreset.recommendations }
    private var cloud: Bool { store.config.vision.provider == "openrouter" }
    private var preset: VisionPreset? { presets.first { $0.id == store.config.vision.model } }
    private var providerSelection: Binding<String> {
        Binding(get: { store.config.vision.provider }, set: { store.selectVisionProvider($0) })
    }
    private var modelSelection: Binding<String> {
        Binding(get: { preset?.id ?? "custom" }, set: { store.config.vision.model = $0 == "custom" ? "" : $0 })
    }

    var body: some View {
        Section("Vision") {
            Toggle("Enable visual target grounding", isOn: $store.config.vision.enabled)
            Picker("Vision provider", selection: providerSelection) {
                Text("Ollama · local").tag("ollama")
                Text("LM Studio · local").tag("lmstudio")
                Text("OpenRouter · cloud").tag("openrouter")
            }
            if cloud {
                Picker("Vision model", selection: modelSelection) {
                    ForEach(presets) { model in Text(model.name).tag(model.id) }
                    Text("Custom OpenRouter model").tag("custom")
                }
                if let model = preset {
                    Label(model.purpose, systemImage: "viewfinder").foregroundStyle(RagnarTheme.bronze)
                    Text(model.detail).font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Text(model.id).font(.caption.monospaced()).textSelection(.enabled)
                        Spacer()
                        Link("Model details & pricing", destination: model.url).font(.caption)
                    }
                } else {
                    TextField("OpenRouter model ID (author/model)", text: $store.config.vision.model)
                    Text("Choose a model accepting images with structured JSON and reasoning controls.").font(.caption).foregroundStyle(.secondary)
                }
                SecureField(store.storedVisionKey ? "New OpenRouter key (blank keeps saved key)" : "OpenRouter API key", text: $store.visionKey)
                HStack {
                    Label(store.storedVisionKey ? "OpenRouter key saved in macOS Keychain" : "No saved OpenRouter key", systemImage: store.storedVisionKey ? "lock.fill" : "key")
                        .font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    if store.storedVisionKey { Button("Remove shared key", role: .destructive) { store.removeVisionKey() } }
                }
                Text("This key is shared with the OpenRouter decision provider. Jev and other providers keep their own keys.").font(.caption).foregroundStyle(.secondary)
                Label("Screenshots and target instructions go to OpenRouter and its selected provider. Calls use your OpenRouter credit.", systemImage: "cloud")
                    .font(.caption).foregroundStyle(.secondary)
                Text("Three recommended candidates for browser work; their accuracy and speed in OpenRagnar have not been ranked by a matched benchmark. Follow the pricing link for current rates.").font(.caption).foregroundStyle(.secondary)
            } else {
                TextField("Local API URL", text: $store.config.vision.endpoint)
                TextField("Downloaded vision model", text: $store.config.vision.model)
                Text("Ollama: ollama pull qwen3-vl:2b-instruct. For a larger candidate, use qwen3-vl:8b-instruct. LM Studio: start its local server and enter the loaded vision model ID.")
                    .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                Label("Screenshots stay on this Mac through the configured local server.", systemImage: "desktopcomputer")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("Save to use this model on the next vision request. Your last model for each provider is remembered. Reconnect your MCP client after first enabling vision to expose its tool.").font(.caption).foregroundStyle(.secondary)
            Text("The agent uses openragnar_visual_act for targets that need vision. It receives a compact point/click report. Jev remains the separate text decision provider. Verified experience reuse is scoped to the selected model; no automatic provider switch or retry.").font(.caption).foregroundStyle(.secondary)
            Button(cloud ? "Test OpenRouter vision" : "Test local vision server") { store.test("--test-vision") }
            Text("The test checks availability and capabilities without screenshots or paid inference. It does not prove click accuracy.").font(.caption).foregroundStyle(.secondary)
        }
    }
}
