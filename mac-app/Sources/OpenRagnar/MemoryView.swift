import SwiftUI
struct MemoryView: View {
    @ObservedObject var store: Store
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Browser experience memory").font(.title2.bold())
                Text("Learn from outcomes, then verify again. Delegated navigation recalls relevant routes and failure lessons. After two local successes on the same task, a current observed link can bypass a provider decision. Direct tools remember request failures; they cannot infer whether the whole task succeeded.").foregroundStyle(.secondary)
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
                    GroupBox("Learning in use") {
                        VStack(alignment: .leading, spacing: 14) {
                            HStack(spacing: 30) {
                                metric("Tasks using a proven route", memory.tasksWithReuse ?? 0)
                                metric("Provider calls avoided", memory.providerCallsAvoided ?? 0)
                                metric("Reused tasks with text verified", memory.reusedTasksVerified ?? 0)
                            }
                            HStack(spacing: 30) {
                                metric("Retained direct requests", memory.toolRequestsSeen ?? 0)
                                metric("Retained failed requests", memory.toolFailures ?? 0)
                                metric("Repeat failure hints shown", memory.repeatFailureHints ?? 0)
                            }
                            Text("Last recall: \(memory.recallSource ?? "Not used"). Calls avoided count skipped decision requests, not measured tokens or speed. Reuse requires matching intent and two local text-verified runs in 30 days; a later failed route removes eligibility until two new successes.")
                                .font(.caption).foregroundStyle(.secondary)
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
                                Text(outcome(experience)).foregroundStyle(experience.verified ? .green : .orange)
                                Text(experience.synced ? "Uploaded" : "Queued").font(.caption).foregroundStyle(.secondary)
                            }.padding(8)
                        }
                    }
                }
                Text("OpenViking stores scoped experiences and supplies advisory hints; the gateway applies the learning policy. Local cache hits avoid a memory-service round trip. Hints stay within 1.6 KB. No retraining, extra reflection model or automatic replay of browser writes. Navigation outcomes and direct-request failure/recovery lessons sync with vector-only processing. Local direct-request fingerprints use HMAC; arguments and raw errors are never saved in experience memory. Disable memory in Settings to stop capture, reuse, recall and uploads.").font(.callout).foregroundStyle(.secondary)
            }.padding(24)
        }
    }
    private func outcome(_ experience: MemoryExperience) -> String {
        if experience.test == true { return "Validation record" }
        if experience.kind == "tool_outcome" { return experience.status == "error" ? "Request failed" : "Request accepted" }
        return experience.verified ? "Text verified" : "Escalated"
    }
    private func metric(_ label: String, _ value: Int) -> some View {
        VStack(alignment: .leading) { Text(number(value)).font(.title2.monospacedDigit()); Text(label).font(.caption).foregroundStyle(.secondary) }
    }
}
