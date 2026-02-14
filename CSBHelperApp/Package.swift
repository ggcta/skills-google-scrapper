// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CSBHelperApp",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "CSBHelperApp",
            targets: ["CSBHelperApp"]
        )
    ],
    dependencies: [
        .package(path: "../CSBHelperSwift")
    ],
    targets: [
        .executableTarget(
            name: "CSBHelperApp",
            dependencies: [
                .product(name: "CSBHelperCore", package: "CSBHelperSwift")
            ],
            resources: [
                .process("Resources")
            ]
        )
    ]
)
