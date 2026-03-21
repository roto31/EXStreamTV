// swift-tools-version:5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "EXStreamTVApp",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "EXStreamTVApp",
            targets: ["EXStreamTVApp"]
        ),
    ],
    dependencies: [
        // No external dependencies - using native SwiftUI and AppKit
    ],
    targets: [
        .executableTarget(
            name: "EXStreamTVApp",
            dependencies: [],
            path: "Sources",
            resources: [
                .process("Resources/Assets.xcassets"),
                .copy("Resources/EXStreamTV.entitlements")
            ]
        ),
    ]
)
