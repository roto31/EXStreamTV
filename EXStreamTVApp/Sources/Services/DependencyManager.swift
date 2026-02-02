//
//  DependencyManager.swift
//  EXStreamTVApp
//
//  Manages checking and installing dependencies (Python, FFmpeg).
//

import Foundation

/// Status of a dependency
enum DependencyStatus: Equatable {
    case installed(version: String)
    case notInstalled
    case checking
    case installing
    case failed(error: String)
    
    var isInstalled: Bool {
        if case .installed = self { return true }
        return false
    }
    
    var displayText: String {
        switch self {
        case .installed(let version):
            return "Installed (v\(version))"
        case .notInstalled:
            return "Not Installed"
        case .checking:
            return "Checking..."
        case .installing:
            return "Installing..."
        case .failed(let error):
            return "Failed: \(error)"
        }
    }
}

/// Information about a dependency
struct DependencyInfo {
    let name: String
    let command: String
    let versionFlag: String
    let minVersion: String?
    let brewPackage: String
    let description: String
}

/// Manages checking and installing Python and FFmpeg dependencies
@MainActor
class DependencyManager: ObservableObject {
    
    // MARK: - Singleton
    
    static let shared = DependencyManager()
    
    // MARK: - Published Properties
    
    @Published var pythonStatus: DependencyStatus = .checking
    @Published var ffmpegStatus: DependencyStatus = .checking
    @Published var ollamaStatus: DependencyStatus = .checking
    @Published var homebrewInstalled: Bool = false
    @Published var isCheckingAll: Bool = false
    
    // MARK: - Dependencies
    
    static let python = DependencyInfo(
        name: "Python",
        command: "python3",
        versionFlag: "--version",
        minVersion: "3.10",
        brewPackage: "python@3.11",
        description: "Python 3.10+ is required to run the EXStreamTV backend."
    )
    
    static let ffmpeg = DependencyInfo(
        name: "FFmpeg",
        command: "ffmpeg",
        versionFlag: "-version",
        minVersion: nil,
        brewPackage: "ffmpeg",
        description: "FFmpeg is required for video transcoding and streaming."
    )
    
    static let ollama = DependencyInfo(
        name: "Ollama",
        command: "ollama",
        versionFlag: "--version",
        minVersion: nil,
        brewPackage: "ollama",
        description: "Ollama is optional, required for local AI models."
    )
    
    // MARK: - Initialization
    
    private init() {}
    
    // MARK: - Public Methods
    
    /// Check all dependencies
    func checkAllDependencies() async {
        isCheckingAll = true
        
        // Check Homebrew first
        homebrewInstalled = await checkHomebrew()
        
        // Check dependencies in parallel
        async let pythonCheck = checkDependency(Self.python)
        async let ffmpegCheck = checkDependency(Self.ffmpeg)
        async let ollamaCheck = checkDependency(Self.ollama)
        
        pythonStatus = await pythonCheck
        ffmpegStatus = await ffmpegCheck
        ollamaStatus = await ollamaCheck
        
        isCheckingAll = false
    }
    
    /// Check if all required dependencies are installed
    var allRequiredInstalled: Bool {
        pythonStatus.isInstalled && ffmpegStatus.isInstalled
    }
    
    /// Install a specific dependency
    func installDependency(_ info: DependencyInfo) async -> DependencyStatus {
        // Update status
        switch info.name {
        case "Python": pythonStatus = .installing
        case "FFmpeg": ffmpegStatus = .installing
        case "Ollama": ollamaStatus = .installing
        default: break
        }
        
        // Try Homebrew installation
        if homebrewInstalled {
            let result = await installViaHomebrew(info.brewPackage)
            if result {
                let status = await checkDependency(info)
                updateStatus(for: info.name, status: status)
                return status
            }
        }
        
        // Homebrew not available or failed
        let status = DependencyStatus.failed(error: "Homebrew installation failed. Please install manually.")
        updateStatus(for: info.name, status: status)
        return status
    }
    
    /// Open the installation script in Terminal
    func runInstallScript() {
        let scriptPath = Bundle.main.bundlePath
            .replacingOccurrences(of: "/EXStreamTVApp.app/Contents/MacOS", with: "")
            + "/scripts/install_macos.sh"
        
        let script = """
        tell application "Terminal"
            activate
            do script "cd '\(scriptPath.replacingOccurrences(of: "/scripts/install_macos.sh", with: ""))' && bash scripts/install_macos.sh"
        end tell
        """
        
        if let appleScript = NSAppleScript(source: script) {
            var error: NSDictionary?
            appleScript.executeAndReturnError(&error)
        }
    }
    
    // MARK: - Private Methods
    
    private func updateStatus(for name: String, status: DependencyStatus) {
        switch name {
        case "Python": pythonStatus = status
        case "FFmpeg": ffmpegStatus = status
        case "Ollama": ollamaStatus = status
        default: break
        }
    }
    
    private func checkHomebrew() async -> Bool {
        return await withCheckedContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/which")
            process.arguments = ["brew"]
            
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            
            do {
                try process.run()
                process.waitUntilExit()
                continuation.resume(returning: process.terminationStatus == 0)
            } catch {
                continuation.resume(returning: false)
            }
        }
    }
    
    private func checkDependency(_ info: DependencyInfo) async -> DependencyStatus {
        return await withCheckedContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = [info.command, info.versionFlag]
            
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            
            do {
                try process.run()
                process.waitUntilExit()
                
                if process.terminationStatus == 0 {
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    let output = String(data: data, encoding: .utf8) ?? ""
                    let version = extractVersion(from: output, command: info.command)
                    
                    // Check minimum version if specified
                    if let minVersion = info.minVersion {
                        if compareVersions(version, minVersion) >= 0 {
                            continuation.resume(returning: .installed(version: version))
                        } else {
                            continuation.resume(returning: .failed(error: "Version \(version) < \(minVersion)"))
                        }
                    } else {
                        continuation.resume(returning: .installed(version: version))
                    }
                } else {
                    continuation.resume(returning: .notInstalled)
                }
            } catch {
                continuation.resume(returning: .notInstalled)
            }
        }
    }
    
    private func extractVersion(from output: String, command: String) -> String {
        // Python: "Python 3.11.5"
        // FFmpeg: "ffmpeg version 6.0 ..."
        // Ollama: "ollama version 0.1.17"
        
        let patterns = [
            "Python (\\d+\\.\\d+\\.?\\d*)",
            "ffmpeg version (\\d+\\.\\d+\\.?\\d*)",
            "ollama version (\\d+\\.\\d+\\.?\\d*)",
            "(\\d+\\.\\d+\\.?\\d*)"  // Fallback
        ]
        
        for pattern in patterns {
            if let regex = try? NSRegularExpression(pattern: pattern, options: []),
               let match = regex.firstMatch(in: output, options: [], range: NSRange(output.startIndex..., in: output)),
               let range = Range(match.range(at: 1), in: output) {
                return String(output[range])
            }
        }
        
        return "unknown"
    }
    
    private func compareVersions(_ v1: String, _ v2: String) -> Int {
        let parts1 = v1.split(separator: ".").compactMap { Int($0) }
        let parts2 = v2.split(separator: ".").compactMap { Int($0) }
        
        for i in 0..<max(parts1.count, parts2.count) {
            let p1 = i < parts1.count ? parts1[i] : 0
            let p2 = i < parts2.count ? parts2[i] : 0
            
            if p1 > p2 { return 1 }
            if p1 < p2 { return -1 }
        }
        
        return 0
    }
    
    private func installViaHomebrew(_ package: String) async -> Bool {
        return await withCheckedContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["brew", "install", package]
            
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            
            do {
                try process.run()
                process.waitUntilExit()
                continuation.resume(returning: process.terminationStatus == 0)
            } catch {
                continuation.resume(returning: false)
            }
        }
    }
}
