import SwiftUI
import Charts

private struct ContextPoint: Identifiable {
    var id: String
    var request: Int
    var tokens: Int
    var route: String
    var tool: String
}
struct RecentContextChart: View {
    var requests: [GatewayRequest]
    private var recent: [GatewayRequest] {
        Array(requests.filter { $0.method == "tools/call" }.sorted { $0.started < $1.started }.suffix(24))
    }
    private var points: [ContextPoint] {
        recent.enumerated().flatMap { index, request in
            [ContextPoint(id: request.id + "-raw", request: index + 1, tokens: estimate(request.upstreamInputBytes + request.upstreamText), route: "Direct Neo equivalent", tool: request.tool),
             ContextPoint(id: request.id + "-compact", request: index + 1, tokens: estimate(request.inputBytes + request.clientText), route: "BrowserHelm", tool: request.tool)]
        }
    }
    var body: some View {
        HelmPanel {
            VStack(alignment: .leading, spacing: 16) {
                SectionHeading(title: "Recent request footprint", symbol: "waveform.path", evidence: "TEXT ESTIMATE")
                if recent.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "waveform.path").font(.largeTitle).foregroundStyle(HelmTheme.accent)
                        Text("Your next browser requests will appear here").font(.callout)
                        Text("Connect an MCP client and use a browser tool.").font(.caption).foregroundStyle(.secondary)
                    }.frame(maxWidth: .infinity, minHeight: 130)
                } else {
                    Chart(points) { point in
                        LineMark(x: .value("Request", point.request), y: .value("Text token equivalents", point.tokens))
                            .foregroundStyle(by: .value("Route", point.route))
                            .lineStyle(StrokeStyle(lineWidth: point.route == "BrowserHelm" ? 2.5 : 1.5))
                            .symbol(by: .value("Route", point.route))
                            .symbolSize(recent.count < 5 ? 24 : 0)
                            .accessibilityLabel("Request \(point.request), \(point.tool), \(point.route)")
                            .accessibilityValue("Approximately \(point.tokens) text token equivalents")
                    }
                    .chartForegroundStyleScale(["Direct Neo equivalent": HelmTheme.ink, "BrowserHelm": HelmTheme.accent])
                    .chartXAxis(.hidden)
                    .chartYAxis { AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) }
                    .chartYScale(domain: 0...max(1, points.map(\.tokens).max() ?? 1))
                    .chartLegend(position: .bottom, alignment: .leading, spacing: 12)
                    .frame(height: 145)
                    Text("Latest \(recent.count) retained tool requests, oldest to newest. Includes local replies; the direct Neo line is a same-call equivalent, not an independent run.").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }
}
