import SwiftUI
import AppKit

/// Packet Studio: graphite surfaces, clear cyan accents and semantic status colors.
enum HelmTheme {
    static let accent = adaptive(light: 0x087D93, dark: 0x57D7ED)
    static let background = adaptive(light: 0xF3F6FA, dark: 0x0B121A)
    static let sidebar = adaptive(light: 0xE8EEF4, dark: 0x101923)
    static let surface = adaptive(light: 0xFFFFFF, dark: 0x141F2B)
    static let muted = adaptive(light: 0xE0E8F0, dark: 0x1F2B38)
    static let ink = adaptive(light: 0x506476, dark: 0x9CACBD)
    private static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let hex = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
            return NSColor(red: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: 1)
        })
    }
}

struct HelmMark: View {
    var size: CGFloat = 38
    var body: some View {
        Group {
            if let image = NSImage(contentsOf: Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/AppIcon.png")) {
                Image(nsImage: image).resizable().interpolation(.high).scaledToFit()
            } else {
                Image(systemName: "network").resizable().scaledToFit().padding(6).foregroundStyle(HelmTheme.accent)
            }
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}

struct HelmPanel<Content: View>: View {
    var accent = false
    @ViewBuilder var content: Content
    var body: some View {
        content.padding(22).frame(maxWidth: .infinity, alignment: .leading)
            .background(HelmTheme.surface, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(accent ? HelmTheme.accent.opacity(0.4) : Color.primary.opacity(0.07), lineWidth: 1))
    }
}

struct EvidenceLabel: View {
    var title: String
    var body: some View {
        Text(title).font(.system(size: 10, weight: .medium, design: .monospaced)).tracking(0.7)
            .foregroundStyle(.secondary).padding(.horizontal, 8).padding(.vertical, 4)
            .background(HelmTheme.muted, in: RoundedRectangle(cornerRadius: 4))
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

struct HelmAppearance: ViewModifier {
    @AppStorage("browserhelm.appearance") private var appearance = "dark"
    func body(content: Content) -> some View {
        content.tint(HelmTheme.accent).preferredColorScheme(appearance == "dark" ? .dark : appearance == "light" ? .light : nil)
    }
}
