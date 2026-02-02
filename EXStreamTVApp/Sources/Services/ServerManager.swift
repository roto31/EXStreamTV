//
//  ServerManager.swift
//  EXStreamTVApp
//
//  Manages the EXStreamTV Python server process - starting, stopping, and monitoring.
//

import Foundation
import Combine

@MainActor
class ServerManager: ObservableObject {
    // MARK: - Published Properties
    
    @Published var isRunning = false
    @Published var isStarting = false
    @Published var isStopping = false
    @Published var serverURL: URL?
    @Published var lastError: String?
    @Published var activeStreams: Int = 0
    @Published var uptime: TimeInterval = 0
    @Published var cpuUsage: Double = 0
    @Published var memoryUsage: Double = 0
    
    // MARK: - Private Properties
    
    private var serverProcess: Process?
    private var outputPipe: Pipe?
    private var errorPipe: Pipe?
    private var monitorTimer: Timer?
    private var uptimeTimer: Timer?
    private var startTime: Date?
    
    private let healthCheckInterval: TimeInterval = 5.0
    
    // MARK: - Computed Properties
    
    var port: Int {
        UserDefaults.standard.integer(forKey: "serverPort")
    }
    
    var pythonPath: String {
        UserDefaults.standard.string(forKey: "pythonPath") ?? "/usr/bin/python3"
    }
    
    var serverPath: String {
        if let path = UserDefaults.standard.string(forKey: "serverPath"), !path.isEmpty {
            return path
        }
        // Default to parent directory of the app
        return findServerPath()
    }
    
    var statusText: String {
        if isStarting { return "Starting..." }
        if isStopping { return "Stopping..." }
        if isRunning { return "Running" }
        return "Stopped"
    }
    
    var statusColor: String {
        if isStarting || isStopping { return "yellow" }
        if isRunning { return "green" }
        return "gray"
    }
    
    var formattedUptime: String {
        let hours = Int(uptime) / 3600
        let minutes = Int(uptime) % 3600 / 60
        let seconds = Int(uptime) % 60
        
        if hours > 0 {
            return String(format: "%dh %dm", hours, minutes)
        } else if minutes > 0 {
            return String(format: "%dm %ds", minutes, seconds)
        } else {
            return String(format: "%ds", seconds)
        }
    }
    
    // MARK: - Initialization
    
    init() {
        // Check if server is already running
        Task {
            await checkServerStatus()
        }
    }
    
    deinit {
        monitorTimer?.invalidate()
        uptimeTimer?.invalidate()
    }
    
    // MARK: - Server Control
    
    func start() async {
        guard !isRunning && !isStarting else { return }
        
        isStarting = true
        lastError = nil
        
        do {
            try await startServer()
            isRunning = true
            startTime = Date()
            startUptimeTimer()
            
            // Notify success
            sendNotification(
                title: "EXStreamTV Started",
                body: "Server is now running on port \(port)"
            )
        } catch {
            lastError = error.localizedDescription
            sendNotification(
                title: "EXStreamTV Failed to Start",
                body: error.localizedDescription
            )
        }
        
        isStarting = false
    }
    
    func stop() async {
        guard isRunning && !isStopping else { return }
        
        isStopping = true
        
        await stopServer()
        
        isRunning = false
        startTime = nil
        uptime = 0
        activeStreams = 0
        uptimeTimer?.invalidate()
        
        sendNotification(
            title: "EXStreamTV Stopped",
            body: "Server has been stopped"
        )
        
        isStopping = false
    }
    
    func restart() async {
        await stop()
        try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second delay
        await start()
    }
    
    // MARK: - Private Methods
    
    private func startServer() async throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-m", "exstreamtv"]
        process.currentDirectoryURL = URL(fileURLWithPath: serverPath)
        
        // Set environment
        var environment = ProcessInfo.processInfo.environment
        environment["EXSTREAMTV_PORT"] = String(port)
        process.environment = environment
        
        // Setup pipes for output
        outputPipe = Pipe()
        errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        
        // Handle output
        outputPipe?.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                print("[EXStreamTV] \(output)")
            }
        }
        
        errorPipe?.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                print("[EXStreamTV Error] \(output)")
            }
        }
        
        // Handle termination
        process.terminationHandler = { [weak self] process in
            Task { @MainActor in
                self?.handleTermination(exitCode: process.terminationStatus)
            }
        }
        
        try process.run()
        serverProcess = process
        
        // Wait for server to be ready
        try await waitForServer(timeout: 30)
        
        serverURL = URL(string: "http://localhost:\(port)")
    }
    
    private func stopServer() async {
        // Try graceful shutdown via API first
        if let url = URL(string: "http://localhost:\(port)/api/shutdown") {
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.timeoutInterval = 5
            
            do {
                let _ = try await URLSession.shared.data(for: request)
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            } catch {
                // API shutdown failed, terminate process
            }
        }
        
        // Terminate process if still running
        if let process = serverProcess, process.isRunning {
            process.terminate()
            
            // Wait for termination
            for _ in 0..<10 {
                if !process.isRunning { break }
                try? await Task.sleep(nanoseconds: 500_000_000)
            }
            
            // Force kill if needed
            if process.isRunning {
                process.interrupt()
            }
        }
        
        serverProcess = nil
        outputPipe = nil
        errorPipe = nil
        serverURL = nil
    }
    
    private func waitForServer(timeout: TimeInterval) async throws {
        let startTime = Date()
        let url = URL(string: "http://localhost:\(port)/health")!
        
        while Date().timeIntervalSince(startTime) < timeout {
            do {
                var request = URLRequest(url: url)
                request.timeoutInterval = 2
                let (_, response) = try await URLSession.shared.data(for: request)
                
                if let httpResponse = response as? HTTPURLResponse,
                   httpResponse.statusCode == 200 {
                    return
                }
            } catch {
                // Server not ready yet
            }
            
            try await Task.sleep(nanoseconds: 500_000_000)
        }
        
        throw ServerError.startupTimeout
    }
    
    private func handleTermination(exitCode: Int32) {
        isRunning = false
        serverProcess = nil
        
        if exitCode != 0 {
            lastError = "Server exited with code \(exitCode)"
            sendNotification(
                title: "EXStreamTV Crashed",
                body: "Server exited unexpectedly (code \(exitCode))"
            )
        }
    }
    
    // MARK: - Monitoring
    
    func startMonitoring() {
        monitorTimer = Timer.scheduledTimer(withTimeInterval: healthCheckInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.checkServerStatus()
            }
        }
    }
    
    func stopMonitoring() {
        monitorTimer?.invalidate()
        monitorTimer = nil
    }
    
    private func checkServerStatus() async {
        guard let url = URL(string: "http://localhost:\(port)/health") else { return }
        
        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 3
            let (data, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 {
                isRunning = true
                
                // Parse health data
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    // Update stats from health endpoint
                }
            } else {
                isRunning = false
            }
        } catch {
            // Only mark as not running if we're not explicitly controlling it
            if serverProcess == nil {
                isRunning = false
            }
        }
        
        // Fetch dashboard stats if running
        if isRunning {
            await fetchDashboardStats()
        }
    }
    
    private func fetchDashboardStats() async {
        guard let url = URL(string: "http://localhost:\(port)/api/dashboard/quick-stats") else { return }
        
        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 3
            let (data, _) = try await URLSession.shared.data(for: request)
            
            if let stats = try? JSONDecoder().decode([QuickStat].self, from: data) {
                for stat in stats {
                    if stat.label == "Active Streams" {
                        activeStreams = Int(stat.value) ?? 0
                    }
                }
            }
        } catch {
            // Ignore errors
        }
    }
    
    private func startUptimeTimer() {
        uptimeTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                if let startTime = self?.startTime {
                    self?.uptime = Date().timeIntervalSince(startTime)
                }
            }
        }
    }
    
    // MARK: - Helpers
    
    private func findServerPath() -> String {
        // Try to find the exstreamtv package relative to the app
        let fileManager = FileManager.default
        let appPath = Bundle.main.bundlePath
        
        // Check parent directories
        var currentPath = URL(fileURLWithPath: appPath)
        for _ in 0..<5 {
            currentPath = currentPath.deletingLastPathComponent()
            let serverPath = currentPath.appendingPathComponent("exstreamtv")
            if fileManager.fileExists(atPath: serverPath.path) {
                return currentPath.path
            }
        }
        
        // Default to current directory
        return fileManager.currentDirectoryPath
    }
    
    private func sendNotification(title: String, body: String) {
        guard UserDefaults.standard.bool(forKey: "showNotifications") else { return }
        
        let notification = NSUserNotification()
        notification.title = title
        notification.informativeText = body
        notification.soundName = NSUserNotificationDefaultSoundName
        
        NSUserNotificationCenter.default.deliver(notification)
    }
}

// MARK: - Supporting Types

enum ServerError: LocalizedError {
    case startupTimeout
    case processNotFound
    case invalidConfiguration
    
    var errorDescription: String? {
        switch self {
        case .startupTimeout:
            return "Server failed to start within the timeout period"
        case .processNotFound:
            return "Python executable not found"
        case .invalidConfiguration:
            return "Invalid server configuration"
        }
    }
}

struct QuickStat: Codable {
    let label: String
    let value: String
    let icon: String?
    let color: String?
}
