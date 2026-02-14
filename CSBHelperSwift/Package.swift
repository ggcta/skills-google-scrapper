// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CSBHelperSwift",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "CSBHelperCLI",
            targets: ["CSBHelperCLI"]
        ),
        .library(
            name: "CSBHelperCore",
            targets: ["CSBHelperCore"]
        )
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser", from: "1.2.0")
    ],
    targets: [
        .target(
            name: "CSBHelperCore",
            dependencies: []
        ),
        .executableTarget(
            name: "CSBHelperCLI",
            dependencies: [
                "CSBHelperCore",
                .product(name: "ArgumentParser", package: "swift-argument-parser")
            ]
        ),
        .testTarget(
            name: "CSBHelperCoreTests",
            dependencies: ["CSBHelperCore"]
        )
    ]
)
