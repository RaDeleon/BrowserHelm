// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "BrowserHelm", platforms: [.macOS(.v14)], products: [.executable(name: "BrowserHelm", targets: ["BrowserHelm"])], targets: [.executableTarget(name: "BrowserHelm")])
