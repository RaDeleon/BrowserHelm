import SwiftUI
import AppKit
struct OpenRagnarApp: App {
    @StateObject var store = Store()
    var body: some Scene {
        WindowGroup { MainView(store: store).onAppear { NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true) } }
            .defaultSize(width: 1180, height: 850)
        Settings { SettingsView(store: store).frame(width: 680, height: 820) }
    }
}
