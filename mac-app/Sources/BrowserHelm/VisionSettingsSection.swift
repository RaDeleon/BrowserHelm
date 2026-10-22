import SwiftUI

struct VisionSettingsSection: View {
    @ObservedObject var store: Store
    private var presets: [VisionPreset] { VisionPreset.recommendations }
    private var jev: Bool { store.config.vision.provider == "typesafe" }
    private var cloud: Bool { ["openrouter", "typesafe"].contains(store.config.vision.provider) }
    private var cloudName: String { jev ? "TypeSafe" : "OpenRouter" }
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
                Text("TypeSafe / Jev · experimental cloud").tag("typesafe")
            }
            if jev {
                Label("Experimental Jev image grounding", systemImage: "viewfinder")
                    .foregroundStyle(HelmTheme.accent)
                Text("Pinned model: jev-1.14.0. One request checks for exactly one matching visible target and returns its bounding box. Uncertain or ambiguous results stop before clicking.")
                    .font(.caption).foregroundStyle(.secondary)
                Stepper(value: $store.config.vision.minConfidence, in: 0.5...1, step: 0.05) {
                    Text("Minimum target probability and box confidence: \(store.config.vision.minConfidence, format: .percent.precision(.fractionLength(0)))")
                }
                Text("90% is a starting threshold, not a validated accuracy guarantee. TypeSafe labels images and boxes experimental; compare verified outcomes on your own tasks before relying on them.")
                    .font(.caption).foregroundStyle(.secondary)
                Link("Jev image capabilities and limits", destination: URL(string: "https://docs.typesafe.ai/images")!).font(.caption)
            } else if cloud {
                Picker("Vision model", selection: modelSelection) {
                    ForEach(presets) { model in Text(model.name).tag(model.id) }
                    Text("Custom OpenRouter model").tag("custom")
                }
                if let model = preset {
                    Label(model.purpose, systemImage: "viewfinder").foregroundStyle(HelmTheme.accent)
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
                Text("DeepSeek is the current cloud default. Other presets are experimental; no matched full-task ranking is established. Resolve ambiguous targets before requesting coordinates.").font(.caption).foregroundStyle(.secondary)
            } else {
                TextField("Local API URL", text: $store.config.vision.endpoint)
                TextField("Downloaded vision model", text: $store.config.vision.model)
                Text("Ollama: ollama pull qwen3-vl:2b-instruct. For a larger candidate, use qwen3-vl:8b-instruct. LM Studio: start its local server and enter the loaded vision model ID.")
                    .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                Label("Screenshots stay on this Mac through the configured local server.", systemImage: "desktopcomputer")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if cloud {
                SecureField(store.storedVisionKey ? "New \(cloudName) key (blank keeps saved key)" : "\(cloudName) API key", text: $store.visionKey)
                HStack {
                    Label(store.storedVisionKey ? "\(cloudName) key saved in macOS Keychain" : "No saved \(cloudName) key", systemImage: store.storedVisionKey ? "lock.fill" : "key")
                        .font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    if store.storedVisionKey { Button("Remove shared key", role: .destructive) { store.removeVisionKey() } }
                }
                Text("This key is shared with the \(cloudName) decision provider. Other providers keep their own keys.").font(.caption).foregroundStyle(.secondary)
                Label(jev ? "Screenshots and target instructions go to TypeSafe and use your TypeSafe credit." : "Screenshots and target instructions go to OpenRouter and its selected provider. Calls use your OpenRouter credit.", systemImage: "cloud")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("Save to use this model on the next vision request. Your last model for each provider is remembered. Reconnect your MCP client after first enabling vision to expose its tool.").font(.caption).foregroundStyle(.secondary)
            Text("The agent uses browserhelm_visual_act for targets that need vision. It receives a compact point/click report. Decision and vision providers are selected separately. Verified experience reuse is scoped to the selected model and Jev threshold; no automatic provider switch or retry.").font(.caption).foregroundStyle(.secondary)
            Button(cloud ? "Test \(cloudName) vision connection" : "Test local vision server") { store.test("--test-vision") }
            Text("The test checks availability without screenshots or paid inference. It does not prove click accuracy or experimental image access.").font(.caption).foregroundStyle(.secondary)
        }
    }
}
