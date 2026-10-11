import SwiftUI
import AppKit

/// Bronze and stone adapt to the Mac's appearance; functional colors remain semantic.
enum RagnarTheme {
    static let bronze = adaptive(light: NSColor(red: 0.48, green: 0.29, blue: 0.10, alpha: 1), dark: NSColor(red: 0.82, green: 0.65, blue: 0.40, alpha: 1))
    static let surface = adaptive(light: NSColor(red: 0.97, green: 0.96, blue: 0.94, alpha: 1), dark: NSColor(red: 0.12, green: 0.14, blue: 0.16, alpha: 1))
    static let muted = adaptive(light: NSColor(red: 0.91, green: 0.89, blue: 0.86, alpha: 1), dark: NSColor(red: 0.17, green: 0.19, blue: 0.21, alpha: 1))
    static let ink = adaptive(light: NSColor(red: 0.27, green: 0.30, blue: 0.32, alpha: 1), dark: NSColor(red: 0.60, green: 0.64, blue: 0.66, alpha: 1))
    private static func adaptive(light: NSColor, dark: NSColor) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
        })
    }
}

struct RagnarMark: View {
    var size: CGFloat = 38
    var body: some View {
        ZStack {
            Circle().strokeBorder(RagnarTheme.bronze.opacity(0.5), lineWidth: 1)
            RunicMark().stroke(RagnarTheme.bronze, style: StrokeStyle(lineWidth: 2, lineCap: .square, lineJoin: .miter)).padding(size * 0.23)
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}
private struct RunicMark: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let x = rect.minX + rect.width * 0.23
        path.move(to: CGPoint(x: x, y: rect.maxY))
        path.addLine(to: CGPoint(x: x, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY + rect.height * 0.27))
        path.addLine(to: CGPoint(x: x, y: rect.minY + rect.height * 0.53))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        return path
    }
}

struct RagnarPanel<Content: View>: View {
    var accent = false
    @ViewBuilder var content: Content
    var body: some View {
        content.padding(22).frame(maxWidth: .infinity, alignment: .leading)
            .background(RagnarTheme.surface, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(accent ? RagnarTheme.bronze.opacity(0.4) : Color.primary.opacity(0.07), lineWidth: 1))
    }
}

struct EvidenceLabel: View {
    var title: String
    var body: some View {
        Text(title).font(.system(size: 10, weight: .medium, design: .monospaced)).tracking(0.7)
            .foregroundStyle(.secondary).padding(.horizontal, 8).padding(.vertical, 4)
            .background(RagnarTheme.muted, in: RoundedRectangle(cornerRadius: 4))
    }
}

struct StatDetail: View {
    var title: String
    var value: String
    var note: String = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).foregroundStyle(.secondary)
                Spacer(minLength: 10)
                Text(value).font(.system(.body, design: .monospaced).weight(.medium)).textSelection(.enabled)
            }
            if !note.isEmpty { Text(note).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
        }
    }
}

struct SectionHeading: View {
    var title: String
    var symbol: String
    var evidence: String
    var body: some View {
        HStack {
            Label(title, systemImage: symbol).font(.headline)
            Spacer(minLength: 12)
            EvidenceLabel(title: evidence)
        }
    }
}

struct RagnarAppearance: ViewModifier {
    @AppStorage("openragnar.appearance") private var appearance = "system"
    func body(content: Content) -> some View {
        content.tint(RagnarTheme.bronze).preferredColorScheme(appearance == "dark" ? .dark : appearance == "light" ? .light : nil)
    }
}
