import SwiftUI
struct MemoryView: View {
    @ObservedObject var store: Store
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Browser experience memory").font(.title2.bold())
                Text("Jev and other decision providers use small past outcomes to inform their next choice. Every selected link is checked against the current page, and success is verified by finding your requested text.").foregroundStyle(.secondary)
                if let memory = store.dashboard?.memory {
                    GroupBox {
                        VStack(alignment: .leading, spacing: 8) {
                            Label(memory.enabled ? memory.connection : "Memory disabled", systemImage: "brain").font(.headline)
                            Text(memory.endpoint).font(.caption.monospaced()).textSelection(.enabled)
                            Text(memory.collection).font(.caption.monospaced()).textSelection(.enabled)
                            HStack(spacing: 30) {
                                metric("Uploaded", memory.saved)
                                metric("Pending", memory.pending)
                                metric("Tasks with recalled hints", memory.tasksWithRecall)
                            }.padding(.vertical, 8)
                            Text("Uploaded means OpenViking accepted the file. Semantic indexing may finish later. Counts cover this Mac's retained records; service and embedding token costs are not reported here.").font(.caption).foregroundStyle(.secondary)
                        }.padding(12).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    HStack {
                        Button("Test connection") { store.test("--test-memory") }.disabled(store.busy)
                        Button("Sync pending") { store.test("--sync-memory") }.disabled(store.busy || !store.config.memory.enabled)
                        Button("Memory settings") { store.selectedTab = 3 }
                    }
                    Text("Recent outcomes").font(.headline)
                    if memory.recent.isEmpty { Text("Delegated navigation outcomes will appear here. Direct browser tools continue to work without recording page contents.").foregroundStyle(.secondary) }
                    ForEach(memory.recent) { experience in
                        GroupBox {
                            HStack {
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(experience.goal).lineLimit(2)
                                    Text(timestamp(experience.created)).font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(experience.verified ? "Text verified" : "Escalated").foregroundStyle(experience.verified ? .green : .orange)
                                Text(experience.synced ? "Uploaded" : "Queued").font(.caption).foregroundStyle(.secondary)
                            }.padding(8)
                        }
                    }
                }
                Text("No self-training or extra reflection calls. Hints are limited to two routes and 1.6 KB per decision. Experience uploads use vector-only processing. Outcomes queue privately when the service is offline and retry while a new MCP session is running. Disable memory in Settings to stop new recall and uploads; retained records remain available.").font(.callout).foregroundStyle(.secondary)
            }.padding(24)
        }
    }
    private func metric(_ label: String, _ value: Int) -> some View {
        VStack(alignment: .leading) { Text(number(value)).font(.title2.monospacedDigit()); Text(label).font(.caption).foregroundStyle(.secondary) }
    }
}
