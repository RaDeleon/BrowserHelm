import SwiftUI

struct MainView: View {
    @ObservedObject var store: Store
    @AppStorage("browserhelm.appearance") private var appearance = "dark"
    var body: some View {
        HStack(spacing: 0) {
            sidebar
            Divider()
            VStack(spacing: 0) {
                HStack(spacing: 14) {
                    Text(["Overview", "Connections", "Activity", "Configuration", "Experience memory", "Diagnostics", "Tasks"][store.selectedTab]).font(.headline)
                    Spacer()
                    if let d = store.dashboard { Text("Updated \(Date(timeIntervalSince1970: d.updatedAt).formatted(date: .omitted, time: .shortened))").font(.caption).foregroundStyle(.secondary) }
                    if store.loadingDashboard { ProgressView().controlSize(.mini).accessibilityLabel("Refreshing statistics") }
                    Menu {
                        Picker("Appearance", selection: $appearance) {
                            Text("System").tag("system"); Text("Light").tag("light"); Text("Dark").tag("dark")
                        }
                    } label: { Image(systemName: "circle.lefthalf.filled") }.menuStyle(.borderlessButton).fixedSize().help("Appearance").accessibilityLabel("Appearance")
                    Button { store.refreshDashboard() } label: { Image(systemName: "arrow.clockwise") }.help("Refresh local statistics").disabled(store.loadingDashboard).keyboardShortcut("r", modifiers: [.command])
                }.padding(.horizontal, 24).padding(.vertical, 16)
                Divider()
                if store.selectedTab != 0 && store.selectedTab != 5, let d = store.dashboard { StatsBar(data: d).padding(.horizontal, 24).padding(.top, 18) }
                switch store.selectedTab {
                case 1: ConnectorsView(store: store)
                case 2: SessionsView(store: store)
                case 3: SettingsView(store: store)
                case 4: MemoryView(store: store)
                case 5: DiagnosticsView(store: store)
                case 6: TasksView(store: store)
                default: DashboardView(store: store)
                }
                Divider()
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: store.dashboardError.isEmpty ? "info.circle" : "exclamationmark.triangle")
                    Text(store.dashboardError.isEmpty ? store.status : store.dashboardError).font(.caption).textSelection(.enabled).lineLimit(3)
                    Spacer()
                }.foregroundStyle(.secondary).padding(.horizontal, 24).padding(.vertical, 12)
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }.frame(minWidth: 1120, minHeight: 740).background(HelmTheme.background)
    }
    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack(spacing: 10) {
                HelmMark()
                VStack(alignment: .leading, spacing: 2) {
                    Text("BrowserHelm").font(.system(size: 20, weight: .semibold))
                    Text("Agent execution gateway").font(.system(size: 11)).foregroundStyle(.secondary)
                }
            }.padding(.horizontal, 18).padding(.top, 24)
            List(selection: $store.selectedTab) {
                Label("Dashboard", systemImage: "square.grid.2x2").tag(0)
                Label("Tasks", systemImage: "checklist").tag(6)
                Label("Connectors", systemImage: "cable.connector").tag(1)
                Label("Sessions", systemImage: "clock.arrow.circlepath").tag(2)
                Label("Memory", systemImage: "externaldrive").tag(4)
                Label("Diagnostics", systemImage: "waveform.path.ecg").tag(5)
                Label("Settings", systemImage: "gearshape").tag(3)
            }.listStyle(.sidebar)
            VStack(alignment: .leading, spacing: 12) {
                Divider()
                Text("Local gateway · " + (Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "development")).font(.caption2.monospaced()).foregroundStyle(.secondary)
            }.padding(18)
        }.frame(width: 222).frame(maxHeight: .infinity).background(HelmTheme.sidebar)
    }
}
