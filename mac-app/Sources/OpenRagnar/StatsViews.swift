import SwiftUI

struct MetricCard: View {
    var title: String; var value: String; var note: String; var symbol: String
    var tint: Color = RagnarTheme.bronze
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title).font(.caption.weight(.medium)).foregroundStyle(.secondary)
                Spacer(minLength: 6)
                Image(systemName: symbol).foregroundStyle(tint).font(.caption)
            }
            Text(value).font(.system(size: 27, weight: .semibold)).monospacedDigit().minimumScaleFactor(0.7).lineLimit(1).textSelection(.enabled)
            Text(note).font(.caption).foregroundStyle(.secondary).lineLimit(2).frame(minHeight: 28, alignment: .topLeading)
        }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(RagnarTheme.surface, in: RoundedRectangle(cornerRadius: 12))
            .overlay(alignment: .topLeading) { RoundedRectangle(cornerRadius: 2).fill(tint.opacity(0.7)).frame(width: 26, height: 2).padding(.leading, 16) }
    }
}
struct StatsBar: View {
    var data: Dashboard
    var body: some View {
        let t = data.totals
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { metrics(t) }
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) { metrics(t) }
        }
    }
    @ViewBuilder private func metrics(_ t: Counters) -> some View {
        MetricCard(title: "Agent context", value: "~" + number(estimate(t.inputBytes + t.clientText)), note: "Text token equivalents used", symbol: "text.alignleft")
        MetricCard(title: "Context saved", value: "~" + number(estimate(t.netTextSaved)), note: savingsNote(t), symbol: "arrow.down.right", tint: t.netTextSaved >= 0 ? RagnarTheme.bronze : .orange)
        MetricCard(title: "Browser calls", value: number(t.upstreamCalls), note: "\(number(t.toolRequests)) agent requests", symbol: "cursorarrow.click", tint: RagnarTheme.ink)
        MetricCard(title: "Provider tokens", value: t.providerCalls == 0 ? "—" : number(t.providerTokens) + (t.providerUnknown > 0 ? "+?" : ""), note: t.providerCalls == 0 ? "No decision calls recorded" : t.providerUnknown > 0 ? "\(t.providerUnknown) calls lack usage totals" : "Reported · \(t.providerCalls) \(t.providerCalls == 1 ? "decision" : "decisions")", symbol: "cpu", tint: RagnarTheme.ink)
    }
}
func savingsNote(_ counters: Counters) -> String {
    let baseline = counters.upstreamInputBytes + counters.upstreamText
    guard baseline > 0 else { return "Awaiting forwarded replies" }
    let ratio = abs(Double(counters.netTextSaved) / Double(baseline) * 100)
    return String(format: "%.1f%% %@ text · same calls", ratio, counters.netTextSaved >= 0 ? "less" : "more")
}

struct ContextSavingsPanel: View {
    var totals: Counters
    private var baseline: Int { totals.upstreamInputBytes + totals.upstreamText }
    private var current: Int { totals.inputBytes + totals.clientText }
    private var ratio: Double { baseline > 0 ? Double(totals.netTextSaved) / Double(baseline) : 0 }
    var body: some View {
        RagnarPanel(accent: true) {
            VStack(alignment: .leading, spacing: 20) {
                SectionHeading(title: "Context savings", symbol: "arrow.down.right", evidence: "TEXT ESTIMATE")
                HStack(alignment: .center, spacing: 22) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(baseline > 0 ? "~" + number(abs(estimate(totals.netTextSaved))) : "—")
                            .font(.system(size: 43, weight: .semibold)).monospacedDigit().minimumScaleFactor(0.65).lineLimit(1).textSelection(.enabled)
                        Text(totals.netTextSaved < 0 ? "extra text token equivalents" : "text token equivalents saved").foregroundStyle(.secondary).font(.callout)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    SavingsRing(ratio: ratio, available: baseline > 0)
                }
                VStack(spacing: 15) {
                    comparisonBar("Direct Neo equivalent", bytes: baseline, tint: RagnarTheme.ink)
                    comparisonBar("Through OpenRagnar", bytes: current, tint: RagnarTheme.bronze)
                }
                Text("Same forwarded calls, before and after compaction. Includes catalog and instruction overhead; this is not a separate task run.").font(.caption).foregroundStyle(.secondary)
                if totals.mediaCount > 0 { Text("\(totals.mediaCount) image/audio blocks passed through; billed media tokens are unknown.").font(.caption).foregroundStyle(.secondary) }
            }
        }
    }
    private func comparisonBar(_ label: String, bytes: Int, tint: Color) -> some View {
        VStack(spacing: 6) {
            HStack { Text(label).font(.caption); Spacer(); Text("~" + number(estimate(bytes))).font(.caption.monospaced()).foregroundStyle(.secondary) }
            GeometryReader { geometry in
                let fraction = Double(max(0, bytes)) / Double(max(1, max(baseline, current)))
                ZStack(alignment: .leading) {
                    Capsule().fill(RagnarTheme.muted)
                    Capsule().fill(tint).frame(width: geometry.size.width * fraction)
                }
            }.frame(height: 7)
        }.accessibilityElement(children: .ignore).accessibilityLabel(label + ", approximately " + number(estimate(bytes)) + " text token equivalents")
    }
}
private struct SavingsRing: View {
    var ratio: Double
    var available: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var body: some View {
        ZStack {
            Circle().stroke(RagnarTheme.muted, lineWidth: 6)
            Circle().trim(from: 0, to: min(1, abs(ratio))).stroke(ratio < 0 ? Color.orange : RagnarTheme.bronze, style: StrokeStyle(lineWidth: 6, lineCap: .round)).rotationEffect(.degrees(-90))
            VStack(spacing: 3) {
                Text(available ? String(format: "%.1f%%", abs(ratio) * 100) : "—").font(.system(size: 22, weight: .semibold)).monospacedDigit()
                Text(!available ? "waiting" : ratio < 0 ? "more text" : "less text").font(.system(size: 10)).foregroundStyle(.secondary)
            }
        }.frame(width: 104, height: 104).animation(reduceMotion ? nil : .easeOut(duration: 0.25), value: ratio)
            .help("Change in text context for the same recorded calls. Negative savings mean extra context. The ring caps at 100%; the number shows the full change.")
            .accessibilityElement(children: .combine)
    }
}
