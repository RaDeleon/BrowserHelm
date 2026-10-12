import Foundation
import SwiftUI
// Preserve explicit appearance choices while defaulting new installations to Packet Studio dark.
let defaults = UserDefaults.standard
if defaults.object(forKey: "browserhelm.appearance") == nil,
   let old = UserDefaults(suiteName: "com.techinsf.openragnar")?.string(forKey: "openragnar.appearance") {
    defaults.set(old, forKey: "browserhelm.appearance")
}
if CommandLine.arguments.contains("--provider-key") {
    // Internal IPC only: stdout is captured by the engine, never logged or sent to MCP clients.
    do {
        guard let index = CommandLine.arguments.firstIndex(of: "--provider-key"),
              CommandLine.arguments.count > index + 1 else { exit(1) }
        let provider = CommandLine.arguments[index+1]
        guard providers.contains(provider), provider != "none" else { exit(1) }
        FileHandle.standardOutput.write(Data(try Keys.read(provider).utf8))
    } catch { fputs("Provider Keychain access failed\n", stderr); exit(1) }
} else if CommandLine.arguments.contains("--mcp") {
    do {
        let process = try Runner.process("--mcp")
        process.standardInput = FileHandle.standardInput; process.standardOutput = FileHandle.standardOutput; process.standardError = FileHandle.standardError
        signal(SIGTERM, SIG_IGN); signal(SIGINT, SIG_IGN)
        let termination = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .global())
        termination.setEventHandler { if process.isRunning { process.terminate() } }; termination.resume()
        let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: .global())
        interrupt.setEventHandler { if process.isRunning { process.terminate() } }; interrupt.resume()
        try process.run(); process.waitUntilExit(); exit(process.terminationStatus)
    } catch { fputs("BrowserHelm: \(error.localizedDescription)\n", stderr); exit(1) }
} else if let mode = CommandLine.arguments.first(where: { ["--connect-codex", "--connect-claude", "--disconnect-codex", "--disconnect-claude"].contains($0) }) {
    do { print(try Runner.test(mode, extra: [Bundle.main.executableURL!.path])) } catch { fputs("\(error.localizedDescription)\n", stderr); exit(1) }
} else if let index = CommandLine.arguments.firstIndex(of: "--task"), CommandLine.arguments.count > index + 1 {
    do { print(try Runner.test("--task", extra: [CommandLine.arguments[index+1]])) } catch { fputs("\(error.localizedDescription)\n", stderr); exit(1) }
} else if let mode = CommandLine.arguments.first(where: { ["--test-browser", "--test-provider", "--test-vision", "--dashboard", "--diagnostics", "--test-memory", "--sync-memory"].contains($0) }) {
    do { print(try Runner.test(mode)) } catch { fputs("\(error.localizedDescription)\n", stderr); exit(1) }
} else { BrowserHelmApp.main() }
