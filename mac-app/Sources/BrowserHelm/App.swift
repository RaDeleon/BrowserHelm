import SwiftUI
import AppKit
struct BrowserHelmApp: App {
    @StateObject var store = Store()
    var body: some Scene {
        WindowGroup { MainView(store: store).modifier(HelmAppearance()).onAppear { NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true) } }
            .defaultSize(width: 1260, height: 940)
        Settings { SettingsView(store: store).modifier(HelmAppearance()).frame(width: 680, height: 820) }
    }
}
