// Editable, deterministic macOS icon artwork. No downloaded fonts or assets.
// Run from the repository root: swift script/generate_icon.swift
import AppKit

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
let output = root.appendingPathComponent("mac-app/Artwork")
let fileManager = FileManager.default
try fileManager.createDirectory(at: output, withIntermediateDirectories: true)

func color(_ hex: UInt32, _ alpha: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 255) / 255,
            green: CGFloat((hex >> 8) & 255) / 255,
            blue: CGFloat(hex & 255) / 255, alpha: alpha)
}

func drawIcon(size: Int) throws -> Data {
    let space = CGColorSpace(name: CGColorSpace.sRGB)!
    let context = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                            bytesPerRow: 0, space: space,
                            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    context.translateBy(x: 0, y: CGFloat(size))
    context.scaleBy(x: CGFloat(size) / 1024, y: -CGFloat(size) / 1024)
    context.setAllowsAntialiasing(true)
    let tile = CGPath(roundedRect: CGRect(x: 80, y: 80, width: 864, height: 864),
                      cornerWidth: 190, cornerHeight: 190, transform: nil)
    context.saveGState()
    context.setShadow(offset: CGSize(width: 0, height: -16), blur: 24, color: color(0x000000, 0.30))
    context.addPath(tile); context.setFillColor(color(0x16212C)); context.fillPath()
    context.restoreGState()
    context.saveGState(); context.addPath(tile); context.clip()
    let stone = CGGradient(colorsSpace: space, colors: [color(0x303D49), color(0x111B26)] as CFArray,
                           locations: [0, 1])!
    context.drawLinearGradient(stone, start: CGPoint(x: 240, y: 80), end: CGPoint(x: 760, y: 944), options: [])
    context.restoreGState()
    context.addPath(CGPath(roundedRect: CGRect(x: 82, y: 82, width: 860, height: 860),
                          cornerWidth: 188, cornerHeight: 188, transform: nil))
    context.setStrokeColor(color(0xD9E1E5, 0.13)); context.setLineWidth(2); context.strokePath()

    // A browser-shaped gateway joins two nodes; the central R echoes the sidebar mark.
    let gate = CGMutablePath()
    gate.move(to: CGPoint(x: 350, y: 724)); gate.addLine(to: CGPoint(x: 294, y: 724))
    gate.addLine(to: CGPoint(x: 294, y: 358))
    gate.addCurve(to: CGPoint(x: 354, y: 298), control1: CGPoint(x: 294, y: 325), control2: CGPoint(x: 321, y: 298))
    gate.addLine(to: CGPoint(x: 670, y: 298))
    gate.addCurve(to: CGPoint(x: 730, y: 358), control1: CGPoint(x: 703, y: 298), control2: CGPoint(x: 730, y: 325))
    gate.addLine(to: CGPoint(x: 730, y: 724)); gate.addLine(to: CGPoint(x: 674, y: 724))
    context.addPath(gate); context.setStrokeColor(color(0xB8915E)); context.setLineWidth(16)
    context.setLineCap(.round); context.setLineJoin(.round); context.strokePath()
    context.move(to: CGPoint(x: 294, y: 390)); context.addLine(to: CGPoint(x: 730, y: 390))
    context.setStrokeColor(color(0xB8915E, 0.45)); context.setLineWidth(10); context.strokePath()
    if size >= 64 {
        for x: CGFloat in [338, 370, 402] {
            context.setFillColor(color(0xD5B783, x == 338 ? 0.9 : 0.35))
            context.fillEllipse(in: CGRect(x: x - 6, y: 344, width: 12, height: 12))
        }
    }
    for (node, edge): (CGFloat, CGFloat) in [(214, 294), (810, 730)] {
        context.move(to: CGPoint(x: node, y: 530)); context.addLine(to: CGPoint(x: edge, y: 530))
        context.setStrokeColor(color(0xB8915E)); context.setLineWidth(14); context.strokePath()
        context.setFillColor(color(0xD5B783))
        context.fillEllipse(in: CGRect(x: node - 16, y: 514, width: 32, height: 32))
    }
    let rune = CGMutablePath()
    rune.move(to: CGPoint(x: 412, y: 706)); rune.addLine(to: CGPoint(x: 412, y: 450))
    rune.addLine(to: CGPoint(x: 620, y: 519)); rune.addLine(to: CGPoint(x: 412, y: 588))
    rune.addLine(to: CGPoint(x: 620, y: 706))
    context.saveGState()
    context.addPath(rune); context.setLineWidth(42); context.setLineCap(.square); context.setLineJoin(.miter)
    context.replacePathWithStrokedPath(); context.clip()
    let metal = CGGradient(colorsSpace: space, colors: [color(0xF1DCB6), color(0xBE945E)] as CFArray,
                           locations: [0, 1])!
    context.drawLinearGradient(metal, start: CGPoint(x: 412, y: 430), end: CGPoint(x: 620, y: 740), options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
    context.restoreGState()
    return NSBitmapImageRep(cgImage: context.makeImage()!).representation(using: .png, properties: [:])!
}

let work = fileManager.temporaryDirectory.appendingPathComponent("openragnar-icon-\(UUID().uuidString)")
let iconset = work.appendingPathComponent("AppIcon.iconset")
try fileManager.createDirectory(at: iconset, withIntermediateDirectories: true)
defer { try? fileManager.removeItem(at: work) }
for points in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let suffix = scale == 2 ? "@2x" : ""
        try drawIcon(size: points * scale).write(to: iconset.appendingPathComponent("icon_\(points)x\(points)\(suffix).png"))
    }
}
try drawIcon(size: 1024).write(to: output.appendingPathComponent("AppIcon.png"))
let process = Process()
process.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
process.arguments = ["-c", "icns", iconset.path, "-o", output.appendingPathComponent("AppIcon.icns").path]
try process.run(); process.waitUntilExit()
guard process.terminationStatus == 0 else { exit(process.terminationStatus) }
print(output.path)
